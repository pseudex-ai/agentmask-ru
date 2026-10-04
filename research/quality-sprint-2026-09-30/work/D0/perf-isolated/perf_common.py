#!/usr/bin/env python3
"""Shared helpers for the O-DETECT isolated perf run (D0/perf-isolated/).

Small on purpose: every value here is either a frozen input identity or a
reporting convention that the two measurement scripts and the summariser must
agree on. Nothing here imports the engine at module import time, so `env.json`
can be written without loading a model.
"""

from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import platform
import resource
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]              # .../Obscura-hop-audit
PROTO = REPO / "prototype"

# The two files the NER arm actually reads. Both live inside the natasha wheel;
# `env.json` records their bytes and sha256 so "which weights" is not folklore.
MODEL_FILES = (
    "natasha/data/model/slovnet_ner_news_v1.tar",
    "natasha/data/emb/navec_news_v1_1B_250K_300d_100q.tar",
)

# Percentile convention, copied from prototype/profile_latency.py::_pct — the
# repo's own nearest-rank form. Kept identical so a number from this run is
# directly comparable with one from that script, and stated in the outputs
# instead of being implied.
PCT_DEFINITION = "nearest-rank: sorted(x)[min(n-1, int(n*p))], no interpolation"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def module_manifest() -> dict[str, str]:
    """sha256 of every engine/licensing module that can influence detection.

    RUNBOOK-PERF §0.2 names `prototype/pseudex/*.py` and `prototype/licensing/*.py`.
    `rglob` is used (not `glob`) so a nested module such as
    `pseudex/localui/*.py` cannot silently escape the freeze; the manifest lists
    relative paths so the same code can be compared across runs and hosts.
    """
    manifest: dict[str, str] = {}
    for root in (PROTO / "pseudex", PROTO / "licensing"):
        for path in sorted(root.rglob("*.py")):
            manifest[str(path.relative_to(REPO))] = sha256_file(path)
    return manifest


def manifest_sha256(manifest: dict[str, str]) -> str:
    blob = "\n".join(f"{k}:{v}" for k, v in sorted(manifest.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def model_files() -> list[dict]:
    import natasha
    base = Path(natasha.__file__).resolve().parent
    out = []
    for rel in MODEL_FILES:
        path = base / Path(rel).relative_to("natasha")
        out.append({"file": rel, "bytes": path.stat().st_size,
                    "sha256": sha256_file(path)})
    return out


def model_bytes_total() -> int:
    return sum(entry["bytes"] for entry in model_files())


def bundle_identity() -> dict:
    """The LEASED bundle as this host builds it — in memory, nothing written."""
    from licensing.pack import build_payload, build_plaintext
    payload = build_payload()
    plain = build_plaintext()
    return {"version": payload["version"], "bytes": len(plain),
            "sha256": hashlib.sha256(plain).hexdigest(),
            "source": "licensing.pack.build_plaintext() in-process"}


def libraries() -> dict[str, str]:
    names = ("natasha", "navec", "slovnet", "pymorphy3", "phonenumbers",
             "numpy", "razdel", "yargy", "ipymarkup", "sqlcipher3", "pymorphy2")
    out: dict[str, str] = {}
    for name in names:
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            out[name] = "NOT_INSTALLED"
    return out


def rss_mb() -> dict:
    """Peak RSS of this process, in MiB.

    `ru_maxrss` is a PEAK, so the four checkpoints are non-decreasing by
    construction; a checkpoint lower than the previous one is impossible and its
    absence is not evidence that memory was returned. macOS reports bytes, Linux
    KiB — converted here and the raw value is kept alongside.

    Because it is a high-water mark, this column can stay flat across a
    checkpoint that genuinely allocated hundreds of MB (the allocator reuses
    pages the model load already faulted in). `current_rss_mb()` below answers
    the other question — how much the process is holding NOW — and both are
    reported, because RUNBOOK-PERF §3 compares against a ~350 MB resident
    baseline that is a CURRENT figure, not a peak.
    """
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    system = platform.system()
    mb = raw / (1024 * 1024) if system == "Darwin" else raw / 1024
    return {"mb": round(mb, 1), "raw": raw,
            "units": "bytes" if system == "Darwin" else "KiB",
            "kind": "peak_ru_maxrss_NOT_current"}


def current_rss_mb() -> float | None:
    """Resident set size right now, in MiB, or None if it cannot be read."""
    import os
    import subprocess
    try:
        statm = Path("/proc/self/statm")           # Linux
        if statm.exists():
            pages = int(statm.read_text().split()[1])
            return round(pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024), 1)
    except Exception:
        pass
    try:                                           # macOS / BSD
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                             capture_output=True, text=True, check=True).stdout
        return round(int(out.strip()) / 1024, 1)   # ps reports KiB
    except Exception:
        return None


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


def load_corpus(path: Path) -> list[dict]:
    """Read corpus.jsonl in file order. Order is the measurement order."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def corpus_sha256(path: Path) -> str:
    return sha256_file(path)


def frozen_inputs() -> dict:
    manifest = module_manifest()
    return {
        "module_manifest_sha256": manifest_sha256(manifest),
        "module_count": len(manifest),
        "model_files": model_files(),
        "libraries": libraries(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
    }
