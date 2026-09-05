"""Arm records on disk, and back. One line per arm in `<run>.arms.jsonl`.

`ArmRun` is the comparator's input and this is its only serialisation, so
`--report` replays a run from the file without a model and without money —
the same objects, the same `compare_triple`, the same numbers. A field the
record cannot round-trip is a field the replay would silently score
differently, which is why the round trip is asserted in `main()`.

The scrub exists for the licence rule the v3 runner learned: measuring with a
corpus is not permission to ship it, and a results file is shipping. Every v4
case is authored here, so today the scrub blanks nothing; it stays so that
stops being an accident when a case starts quoting a licensed source.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.schema import SHIPPABLE_LICENCES, Case

KEY_SEP = "|"


@dataclass(frozen=True)
class ArmMeta:
    """What the SDK reported about one arm, beside what the comparator reads."""

    model: str
    turns: int
    duration_ms: int
    session_id: str
    subtype: str
    is_error: bool
    api_error_status: int | None
    errors: tuple[str, ...]
    reason: str
    cap_usd: float


def merged_arm_records(run_dir: Path) -> list[dict[str, object]]:
    """Every arm of a run directory, deduplicated, the COMPLETED one winning.

    A run resumed after a provider outage (`harness --resume`) writes a second
    `<run>.arms.jsonl` beside the first, and the same (case, repeat, arm) then
    appears twice: once as the failure that stopped the run, once as the retry
    that succeeded. Readers that take the last file miss the first attempt's
    результаты; readers that concatenate get whichever copy sorts last, which
    on `666…` before `f3f…` is the FAILURE. One rule for every reader: prefer
    `done`, then the later record.
    """
    best: dict[tuple[str, int, str], dict[str, object]] = {}
    for path in sorted(run_dir.glob("*.arms.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (str(row["case_id"]), int(row["repeat"]), str(row["arm"]))  # type: ignore[arg-type]
            previous = best.get(key)
            if previous is None or (previous.get("termination") != "done"
                                    and row.get("termination") == "done"):
                best[key] = row
    return list(best.values())


def record_key(case_id: str, arm: str, repeat: int) -> str:
    return KEY_SEP.join((case_id, arm, str(repeat)))


def shippable(case: Case) -> bool:
    return all(message.source is None or message.source.licence in SHIPPABLE_LICENCES
               for message in case.messages)


def arm_record(run: ArmRun, meta: ArmMeta, case: Case) -> dict[str, object]:
    record: dict[str, object] = {
        "key": record_key(run.case_id, run.arm, run.repeat),
        "case_id": run.case_id, "arm": run.arm, "repeat": run.repeat,
        "kind": case.kind, "register": case.register, "cluster": case.cluster,
        "termination": run.termination, "cost_usd": round(run.cost_usd, 6),
        "calls": [{
            "name": call.name, "seq": call.seq,
            "written": call.written, "restored": call.restored,
            "residual": {path: list(left) for path, left in call.residual.items()},
            "refusal_path": call.refusal_path, "refusal_rule": call.refusal_rule,
            "parsed": call.parsed,
        } for call in run.calls],
        "state": list(run.state),
        "reply": run.reply,
        "substitutes": {item_id: [surface, parts] for item_id, (surface, parts) in run.substitutes.items()},
        "meta": {
            "model": meta.model, "turns": meta.turns, "duration_ms": meta.duration_ms,
            "session_id": meta.session_id, "subtype": meta.subtype, "is_error": meta.is_error,
            "api_error_status": meta.api_error_status, "errors": list(meta.errors),
            "reason": meta.reason, "cap_usd": round(meta.cap_usd, 6),
        },
    }
    return record if shippable(case) else scrub(record)


def scrub(record: dict[str, object]) -> dict[str, object]:
    """Strip every value carried out of a licensed case, keeping the shape."""
    marker = "<лицензионный источник>"
    out = dict(record)
    out["reply"] = marker
    out["calls"] = [{**call, "written": {}, "restored": {}, "parsed": None}  # type: ignore[dict-item]
                    for call in record.get("calls", [])]  # type: ignore[union-attr]
    out["state"] = []
    out["substitutes"] = {}
    return out


def arm_from_record(record: dict[str, object]) -> ArmRun:
    calls = tuple(ObservedCall(
        name=str(call["name"]), written=dict(call["written"]), restored=dict(call["restored"]),  # type: ignore[index,arg-type]
        residual={path: tuple(left) for path, left in dict(call["residual"]).items()},  # type: ignore[index,arg-type]
        refusal_path=str(call["refusal_path"]), refusal_rule=str(call["refusal_rule"]),  # type: ignore[index]
        parsed=call["parsed"] if isinstance(call["parsed"], dict) else None,  # type: ignore[index]
        seq=int(call["seq"]))  # type: ignore[index,arg-type]
        for call in record["calls"])  # type: ignore[union-attr]
    substitutes = {item_id: (str(pair[0]), dict(pair[1]))  # type: ignore[index]
                   for item_id, pair in dict(record.get("substitutes") or {}).items()}
    return ArmRun(case_id=str(record["case_id"]), arm=str(record["arm"]), repeat=int(record["repeat"]),  # type: ignore[arg-type]
                  calls=calls, state=tuple(dict(one) for one in record["state"]),  # type: ignore[union-attr]
                  reply=str(record["reply"]), termination=str(record["termination"]),
                  cost_usd=float(record["cost_usd"]), substitutes=substitutes)  # type: ignore[arg-type]


def main() -> int:
    from bench.agentpii4.fake_agent import POLICIES, FakeGateway, scripted_run, seed_backend
    from bench.agentpii4.smoke import _load
    from pathlib import Path
    cases = _load(Path(__file__).resolve().parent / "corpus.json")
    case = next(one for one in cases if one.kind == "chain")
    run = scripted_run(case, "I", 0, FakeGateway(case), seed_backend(case), POLICIES["decomposer"])
    meta = ArmMeta("scripted", 0, 0, "", "success", False, None, (), "", 0.0)
    back = arm_from_record(json.loads(json.dumps(arm_record(run, meta, case), ensure_ascii=False)))
    same = (back.calls == run.calls and back.state == run.state and back.reply == run.reply
            and back.substitutes == run.substitutes and back.termination == run.termination)
    print("records: PASS" if same else "records: FAIL (round trip differs)")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
