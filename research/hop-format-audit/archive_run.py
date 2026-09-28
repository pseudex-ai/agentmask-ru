#!/usr/bin/env python3
"""Freeze a finished AgentPII-5 run into three places, so its numbers survive.

    python3 archive_run.py <run_dir> [--label <name>]

WHY THREE COPIES, AND WHY A MANIFEST.  Everything we will later claim rests on
these files, and each way of losing them is a different failure: a git history
can be rewritten, a laptop disk dies, and a stray `rm -rf bench/runs` is one
keystroke.  So the run goes

  1. `runs/<run_id>.tar.gz`              the whole directory, committed to git
  2. `runs/<run_id>.manifest.json`       sha256 + byte size of EVERY file, committed
  3. `~/pseudex-run-archives/<run_id>/`  an unpacked copy outside the repository

The manifest is the part that makes the other two worth anything: without a
recorded digest, a copy is just a directory that CLAIMS to be the run.  With it,
a later reader re-hashes what they hold and knows whether it is the artifact the
numbers came from.

The script never touches the run directory — it reads, hashes and copies.  It is
safe to run while a DIFFERENT run is writing (the running one's last triples
simply will not be in this snapshot).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# The third copy lives OUTSIDE the repository by default, but the harness may run
# under a sandbox that only writes inside the workspace — so the location is
# overridable and a refusal falls back rather than losing the copy entirely.
ARCHIVE_ENV = "PSEUDEX_RUN_ARCHIVE_DIR"
DEFAULT_ARCHIVE_ROOT = Path.home() / "pseudex-run-archives"
FALLBACK_ARCHIVE_ROOT = Path(__file__).resolve().parent / ".run-archives"
RUNS_DIR = Path(__file__).resolve().parent / "runs"
CHUNK = 1 << 20


def run_id_of(run_dir: Path) -> str:
    """The run id off any run file (`<run_id>.<suffix>`), so it works even when
    `meta.json` is absent — a killed run still gets archived."""
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and "." in path.name:
            return path.name.split(".", 1)[0]
    raise SystemExit(f"{run_dir}: no run files to archive")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_of(run_dir: Path, run_id: str) -> dict[str, object]:
    """Every file's size and digest, sorted — the thing a later reader checks."""
    files = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        files.append({"path": str(path.relative_to(run_dir)),
                      "bytes": path.stat().st_size,
                      "sha256": sha256_of(path)})
    return {
        "run_id": run_id,
        "source_dir": str(run_dir.resolve()),
        "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "archived_on": socket.gethostname(),
        "files": files,
        "files_total": len(files),
        "bytes_total": sum(int(one["bytes"]) for one in files),
        # The digest of the digest list: one line that changes if ANY byte of
        # ANY file changes, which is what a citation should quote.
        "run_sha256": hashlib.sha256(
            "".join(f"{one['sha256']}  {one['path']}\n" for one in files).encode()
        ).hexdigest(),
    }


def archive(run_dir: Path, label: str | None) -> dict[str, object]:
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"{run_dir}: not a directory")
    run_id = run_id_of(run_dir)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = manifest_of(run_dir, run_id)
    if label:
        manifest["label"] = label

    # 1 + 2: the archive and its manifest, both small enough to live in git.
    tarball = RUNS_DIR / f"{run_id}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(run_dir, arcname=run_id)
    manifest["tarball"] = {"path": tarball.name,
                           "bytes": tarball.stat().st_size,
                           "sha256": sha256_of(tarball)}
    (RUNS_DIR / f"{run_id}.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # 3: the unpacked copy, outside the repository and outside git's reach — the
    # one that survives `rm -rf bench/runs` and a rewritten history at once.
    root = Path(os.environ.get(ARCHIVE_ENV) or DEFAULT_ARCHIVE_ROOT)
    external = root / run_id
    try:
        if external.exists():
            shutil.rmtree(external)
        external.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(run_dir, external)
    except OSError as error:
        print(f"archive: {root} refused ({error}); falling back inside the workspace",
              file=sys.stderr)
        root = FALLBACK_ARCHIVE_ROOT
        external = root / run_id
        if external.exists():
            shutil.rmtree(external)
        external.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(run_dir, external)
    manifest["archive_dir"] = str(external)

    # Prove the copy is the artifact: re-hash the external tree and compare.
    verify_failures = []
    for one in manifest["files"]:
        copy = external / str(one["path"])
        if not copy.exists() or sha256_of(copy) != one["sha256"]:
            verify_failures.append(str(one["path"]))
    manifest["verified_files"] = int(manifest["files_total"]) - len(verify_failures)
    manifest["verify_failures"] = verify_failures

    (RUNS_DIR / f"{run_id}.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--label", default=None, help="человекочитаемая метка прогона")
    args = parser.parse_args()

    manifest = archive(args.run_dir, args.label)
    print(f"run_id      : {manifest['run_id']}")
    print(f"files       : {manifest['files_total']} "
          f"({int(manifest['bytes_total']) / 1e6:.1f} MB)")
    print(f"run_sha256  : {manifest['run_sha256']}")
    print(f"tarball     : {manifest['tarball']['path']} "
          f"({int(manifest['tarball']['bytes']) / 1e6:.1f} MB)")
    print(f"external    : {manifest['archive_dir']}")
    print(f"verified    : {manifest['verified_files']}/{manifest['files_total']} files")
    if manifest["verify_failures"]:
        print(f"FAILED      : {manifest['verify_failures']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
