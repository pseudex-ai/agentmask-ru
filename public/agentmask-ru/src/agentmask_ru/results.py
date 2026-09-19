"""A run file: the numbers, and everything needed to re-derive them.

A published rate that cannot be re-computed from artefacts is a claim, not
a measurement — the reason Papers with Code closed and the reason MTEB
stopped accepting self-reported numbers. A run file therefore carries the
per-item observations, not only the totals, so anyone can re-score it with
their own arithmetic and get the same lines.

THE MANIFEST SAYS WHAT WAS MEASURED. The corpus digest ties the numbers to
an exact set of cases; a leaderboard groups by it and marks anything older
as stale rather than quietly comparing two different corpora.
"""

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from agentmask_ru.harness import CaseObservation
from agentmask_ru.schema import VERSION, Case
from agentmask_ru.score import Scores


def corpus_digest(cases: list[Case]) -> str:
    """A digest of the case ids and their user text: two runs over the same
    corpus agree, and any edit to a case moves it."""
    hasher = hashlib.sha256()
    for case in sorted(cases, key=lambda c: c.id):
        hasher.update(case.id.encode("utf-8"))
        for message in case.messages:
            if message["role"] == "user":
                hasher.update(message["content"].encode("utf-8"))
    return hasher.hexdigest()[:16]


@dataclass(frozen=True)
class Manifest:
    system: str
    adapter_config: dict[str, object]
    policy: str
    seed: int
    corpus_digest: str
    corpus_cases: int
    benchmark_version: str
    run_at: str
    python: str
    submitted_by: str
    notes: str


def manifest(system: str, config: dict[str, object], policy: str, seed: int, cases: list[Case],
             submitted_by: str, notes: str) -> Manifest:
    return Manifest(
        system=system, adapter_config=config, policy=policy, seed=seed,
        corpus_digest=corpus_digest(cases), corpus_cases=len(cases), benchmark_version=VERSION,
        run_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        python=platform.python_version(), submitted_by=submitted_by, notes=notes,
    )


def to_payload(meta: Manifest, scores: Scores, observations: list[CaseObservation]) -> dict[str, object]:
    return {
        "manifest": asdict(meta),
        "lines": {
            name: {
                "hits": line.hits, "total": line.total, "rate": round(line.rate, 6),
                "ci95": [round(v, 6) for v in line.interval],
                "certifies": round(line.certified, 6) if line.certified is not None else None,
            }
            for name, line in scores.lines.items()
        },
        "run": {
            "cases": scores.cases, "errors": scores.errors, "calls_made": scores.calls_made,
            "calls_parsed": scores.calls_parsed, "rewrite_flagged": scores.rewrite_flagged,
        },
        "observations": [asdict(o) for o in observations],
    }


def write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
