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
            "unattributable": scores.unattributable, "normalised": scores.normalised,
        },
        "observations": [asdict(o) for o in observations],
    }


def write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def observations_of(payload: dict[str, object]) -> list[CaseObservation]:
    """The per-item observations of a run file, back as the dataclasses the
    scorer reads — the reason a run file carries them at all."""
    from agentmask_ru.harness import ItemObservation, NegativeObservation  # noqa: PLC0415 — cycle-free at call time

    out: list[CaseObservation] = []
    for raw in payload.get("observations", []):
        assert isinstance(raw, dict)
        items = [ItemObservation(**item) for item in raw.get("items", [])]
        negatives = [NegativeObservation(**neg) for neg in raw.get("negatives", [])]
        fields = {k: v for k, v in raw.items() if k not in ("items", "negatives")}
        out.append(CaseObservation(**fields, items=items, negatives=negatives))
    return out


def rejudge(observations: list[CaseObservation], cases: list[Case], policy: str = "copier") -> None:
    """Re-apply the CURRENT judge to observations recorded earlier, in place.

    The judge is part of the benchmark, not of the run: when it learns
    something — that «есина рушана» and «Рушан Есин» are one person — every
    system's stored run must be read with the same eyes, or the table would
    compare one masker under the new rule with six under the old one. Only
    the verdicts a judge makes are recomputed (`normalised`, `consistency`);
    what the masker did and what the tool received are the record and stay.
    """
    import json  # noqa: PLC0415

    from agentmask_ru.harness import _normalised, _same_value  # noqa: PLC0415
    from agentmask_ru.parts import cut_address, cut_name  # noqa: PLC0415
    from agentmask_ru.person import looks_like_person, same_person  # noqa: PLC0415
    from agentmask_ru.rewrite import rewrite  # noqa: PLC0415

    gold = {(case.id, item.id): item for case in cases for item in case.pii}
    for observation in observations:
        for item in observation.items:
            if item.round_trip is None or item.delivered is None:
                continue
            key = (item.case_id, item.item_id)
            if key not in gold:
                continue
            owed = rewrite(gold[key].type, gold[key].canonical) if policy == "rewriter" else gold[key].canonical
            parts = gold[key].parts
            if parts:
                try:
                    got_parts = json.loads(item.delivered)
                except (ValueError, TypeError):
                    continue
                owed_parts = (cut_name(owed, tuple(parts)) if gold[key].type == "NAME"
                              else cut_address(owed, "city" in parts))
                present = all(got_parts.get(part) is not None for part in parts)
                item.round_trip = present and all(
                    _same_value(str(got_parts[part]), owed_parts.get(part, "")) if owed_parts.get(part, "")
                    else not str(got_parts[part] or "").strip() for part in parts)
                item.normalised = (not item.round_trip) and present and all(
                    (_same_value(str(got_parts[part]), owed_parts.get(part, ""))
                     or _normalised(str(got_parts[part]), owed_parts.get(part, "")))
                    if owed_parts.get(part, "") else not str(got_parts[part] or "").strip() for part in parts)
                continue
            item.round_trip = _same_value(item.delivered, owed)
            item.normalised = (not item.round_trip) and _normalised(item.delivered, owed)
        if observation.family != "second_mention":
            continue
        by_identity: dict[str, list[object]] = {}
        for item in observation.items:
            if item.type == "NAME":
                by_identity.setdefault(item.identity, []).append(item)
        for mentions in by_identity.values():
            if len(mentions) < 2:
                continue
            first, second = mentions[0], mentions[1]  # type: ignore[assignment]
            if not first.altered and not second.altered:
                continue
            same = (" ".join(first.substitute.split()).casefold() == " ".join(second.substitute.split()).casefold()
                    or (looks_like_person(first.substitute) and looks_like_person(second.substitute)
                        and same_person(first.substitute, second.substitute)))
            observation.consistency = first.altered and second.altered and same


def rescored(payload: dict[str, object], cases: list[Case]) -> dict[str, object]:
    """The same run, its lines re-derived from its observations by the current judge."""
    from agentmask_ru.score import score  # noqa: PLC0415

    observations = observations_of(payload)
    meta = payload["manifest"]
    assert isinstance(meta, dict)
    rejudge(observations, cases, str(meta.get("policy", "copier")))
    scores = score(observations)
    fresh = to_payload(Manifest(**meta), scores, observations)
    fresh["rescored"] = {"benchmark_version": VERSION}
    return fresh
