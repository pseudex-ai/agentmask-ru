"""Comparing arms: the three INV levels and the per-field verdicts of one triple.

An arm-run is what one arm did with one case in one repeat: the calls it
made (as written, as restored, and as the mock parsed or refused them), the
typed state the mock ended in, and the final reply. A triple is C, I and C′
for one (case, repeat). Pairs are compared BY REPEAT INDEX and never
re-paired when an arm fails — the paired-difference argument needs the
pairing fixed before the data exist.

Level 1 is positional (v2's rule): the question is whether the SEQUENCE
changed, and BFCL's unordered leniency answers a different question.
"""
from dataclasses import dataclass, field

from bench.agentpii4 import taxonomy
from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import Case, PiiItem
from bench.agentpii4.taxonomy import FieldObs, FieldVerdict
from bench.agentpii4.tools import REGISTRY, flatten, spec_for, state_spec_for


@dataclass(frozen=True)
class ObservedCall:
    name: str
    written: dict[str, object]
    restored: dict[str, object]
    residual: dict[str, tuple[str, ...]]     # dotted path -> minted strings surviving in that leaf
    refusal_path: str
    refusal_rule: str
    parsed: dict[str, object] | None
    seq: int


@dataclass(frozen=True)
class ArmRun:
    case_id: str
    arm: str
    repeat: int
    calls: tuple[ObservedCall, ...]
    state: tuple[dict[str, object], ...]     # mock.snapshot()
    reply: str                               # final text as the customer reads it
    termination: str
    cost_usd: float
    substitutes: dict[str, tuple[str, dict[str, str]]] = field(default_factory=dict)
    # I only: item id -> (substitute surface the model read, its split parts)


@dataclass(frozen=True)
class Triple:
    case_id: str
    repeat: int
    C: ArmRun
    I: ArmRun  # noqa: E741 - the arm's own name
    C2: ArmRun


@dataclass(frozen=True)
class LevelVerdict:
    tools: bool
    tools_sub: str
    keys: bool
    keys_sub: str
    state: bool
    state_verbatim: bool
    state_diff: tuple[str, ...]
    # THE ONLY LEVEL THAT ASKS WHETHER THE TOOL GOT A DIFFERENT VALUE. `state`
    # counts a field one arm wrote and the other did not, and on an OPTIONAL
    # field that is the model tossing a coin, not the gateway: `contact.gender`
    # diverged in 195 fields on the 06.09 run and was NEVER wrong — only
    # present or absent — and the omission rate is the same on real values
    # (42.3%) as on substitutes (46.9%). `records 2 vs 1` is likewise a
    # different NUMBER of writes, already counted at L1. What is left when
    # both are removed is the product's own promise: the customer's tool
    # received another value because of us.
    state_values: bool = True


@dataclass(frozen=True)
class PairVerdict:
    pair: str                # "IC" | "CC"
    levels: LevelVerdict
    fields: tuple[FieldVerdict, ...]
    plain: tuple[tuple[str, str], ...]   # (value, "intact" | "changed" | "absent")


def _names(run: ArmRun) -> tuple[str, ...]:
    return tuple(call.name for call in run.calls)


def _accepted_names(run: ArmRun) -> tuple[str, ...]:
    """The calls the mock ACCEPTED. A control that fumbled the house format
    twice and got it right on the third attempt used the same tools as an arm
    that got it right first; counting the fumbles as tools made the cleaner
    arm «missing_call» (live v4 04.09: compare-011, two triples). Refusals
    stay visible where they belong — per field, as `validated_refused`."""
    return tuple(call.name for call in run.calls if not call.refusal_rule)


def level_tools(ref: ArmRun, obs: ArmRun) -> tuple[bool, str]:
    left, right = _names(ref), _names(obs)
    if left == right or _accepted_names(ref) == _accepted_names(obs):
        return True, ""
    if left and not right:
        return False, "no_call"
    if not left and right:
        return False, "extra_call"
    if sorted(left) == sorted(right):
        return False, "reordered"
    if len(right) < len(left) and all(name in left for name in right):
        return False, "missing_call"
    if len(right) > len(left) and all(name in right for name in left):
        return False, "extra_call"
    return False, "different_tool"


def _align(ref: ArmRun, obs: ArmRun) -> list[tuple[ObservedCall | None, ObservedCall | None]]:
    """Calls matched by (name, occurrence index)."""
    seen: dict[str, int] = {}
    left: dict[tuple[str, int], ObservedCall] = {}
    for call in ref.calls:
        seen[call.name] = seen.get(call.name, 0)
        left[(call.name, seen[call.name])] = call
        seen[call.name] += 1
    seen = {}
    right: dict[tuple[str, int], ObservedCall] = {}
    for call in obs.calls:
        seen[call.name] = seen.get(call.name, 0)
        right[(call.name, seen[call.name])] = call
        seen[call.name] += 1
    keys = sorted(set(left) | set(right), key=lambda k: (left.get(k) or right[k]).seq)
    return [(left.get(key), right.get(key)) for key in keys]


def level_keys(ref: ArmRun, obs: ArmRun) -> tuple[bool, str]:
    for left, right in _align(ref, obs):
        if left is None or right is None:
            return False, "call_unmatched"
        lk = {_generic(path) for path in flatten(left.written)}
        rk = {_generic(path) for path in flatten(right.written)}
        if lk != rk:
            missing = sorted(lk - rk)
            extra = sorted(rk - lk)
            return False, ("key_missing:" + ",".join(missing)) if missing else ("key_extra:" + ",".join(extra))
    return True, ""


def _generic(path: str) -> str:
    import re
    return re.sub(r"\[\d+\]", "[]", path)


def level_state(ref: ArmRun, obs: ArmRun) -> tuple[bool, bool, tuple[str, ...]]:
    """(typed equal, verbatim equal, diff lines)."""
    diffs: list[str] = []
    if len(ref.state) != len(obs.state):
        diffs.append(f"records {len(ref.state)} vs {len(obs.state)}")
        return False, False, tuple(diffs)
    verbatim = True
    for left, right in zip(ref.state, obs.state):
        if left["tool"] != right["tool"]:
            diffs.append(f"{left['tool']} vs {right['tool']}")
            continue
        lf = flatten(left["fields"])
        rf = flatten(right["fields"])
        for path in sorted(set(lf) | set(rf)):
            field_spec = state_spec_for(str(left["tool"]), path)
            if field_spec is not None and field_spec.kind == "free":
                continue
            lv, rv = lf.get(path), rf.get(path)
            if _norm(lv) != _norm(rv):
                verbatim = False
                if field_spec is None or not taxonomy._typed_equal(str(lv or ""), str(rv or ""), field_spec):
                    diffs.append(f"{left['tool']}.{path}: {lv!r} vs {rv!r}")
    return not diffs, verbatim and not diffs, tuple(diffs)


def _norm(value: object) -> str:
    return " ".join(str(value if value is not None else "").split()).casefold()


def _observe(call: ObservedCall | None, path: str) -> FieldObs:
    if call is None:
        return FieldObs(False, "", "", "", "", ())
    written = flatten(call.written)
    restored = flatten(call.restored)
    parsed = flatten(call.parsed) if call.parsed else {}
    present = path in written and str(written[path]) != ""
    refused = call.refusal_rule if (call.refusal_path == path or (call.refusal_path and not call.parsed and path.startswith(call.refusal_path))) else ""
    return FieldObs(present, str(written.get(path, "")), str(restored.get(path, "")),
                    str(parsed.get(path, "")), refused, tuple(call.residual.get(path, ())))


def compare_pair(case: Case, ref: ArmRun, obs: ArmRun, pair: str) -> PairVerdict:
    tools_ok, tools_sub = level_tools(ref, obs)
    keys_ok, keys_sub = level_keys(ref, obs)
    state_ok, verbatim_ok, diff = level_state(ref, obs)

    items = [item for item in case.pii]
    fields: list[FieldVerdict] = []
    plain: list[tuple[str, str]] = []
    for left, right in _align(ref, obs):
        name = (left or right).name  # type: ignore[union-attr]
        spec = REGISTRY.get(name)
        if spec is None:
            continue
        paths = set(flatten(left.written) if left else {}) | set(flatten(right.written) if right else {})
        for path in sorted(paths):
            field_spec = spec_for(name, path)
            if field_spec is None or field_spec.kind == "free":
                continue
            ref_obs = _observe(left, path)
            obs_obs = _observe(right, path)
            if field_spec.kind in ("plain", "enum"):
                status = ("intact" if _norm(ref_obs.written) == _norm(obs_obs.written)
                          else ("absent" if not obs_obs.present else "changed"))
                plain.append((f"{name}.{path}", status))
                continue
            real = taxonomy.bind_item(field_spec, ref_obs, items)
            others = [item for item in items if real is not None and item.identity != real.identity
                      and not item.stale] if real else [item for item in items if not item.stale]
            stale = [item for item in items if item.stale]
            substitute = obs.substitutes.get(real.id) if (real and obs.substitutes) else None
            if substitute is None and obs.substitutes and field_spec.pii_type:
                # No bound item: offer the first substitute of the same type so a
                # derived-from-fake verdict is still reachable.
                for item in items:
                    if item.type == field_spec.pii_type and item.id in obs.substitutes:
                        substitute = obs.substitutes[item.id]
                        break
            # Every substitute the model read for the SAME person and source
            # type: the message's and the tool result's are minted apart.
            identity = real.identity if real else ""
            alternates = tuple(
                obs.substitutes[item.id] for item in items
                if item.id in obs.substitutes and item.type == (field_spec.source_type or field_spec.pii_type)
                and (not identity or item.identity == identity)
                and obs.substitutes[item.id] != substitute)
            fields.append(taxonomy.classify_field(field_spec, ref_obs, obs_obs, real, others, stale,
                                                  substitute, case.now, name, path, alternates))
    # Built here rather than above: the value level is read off the field
    # verdicts, which are only known once the loop has run.
    values_ok = not any(one.kind not in ("agree", "absent", "extra") for one in fields)
    levels = LevelVerdict(tools_ok, tools_sub, keys_ok, keys_sub, state_ok, verbatim_ok,
                          diff, values_ok)
    return PairVerdict(pair, levels, tuple(fields), tuple(plain))


def compare_triple(case: Case, triple: Triple) -> tuple[PairVerdict, PairVerdict]:
    return (compare_pair(case, triple.C, triple.I, "IC"),
            compare_pair(case, triple.C, triple.C2, "CC"))


def pair_runs(runs: list[ArmRun]) -> tuple[list[Triple], list[str]]:
    """Group arm-runs into triples by (case, repeat); an incomplete or excluded
    triple is listed, never scored."""
    from bench.agentpii4.schema import EXCLUDED_TERMINATIONS
    by_key: dict[tuple[str, int], dict[str, ArmRun]] = {}
    for run in runs:
        by_key.setdefault((run.case_id, run.repeat), {})[run.arm] = run
    triples: list[Triple] = []
    excluded: list[str] = []
    for (case_id, repeat), arms in sorted(by_key.items()):
        if not all(arm in arms for arm in ("C", "I", "C2")):
            excluded.append(f"{case_id}|{repeat}: missing {sorted({'C', 'I', 'C2'} - set(arms))}")
            continue
        bad = [arm for arm, run in arms.items() if run.termination in EXCLUDED_TERMINATIONS]
        if bad:
            excluded.append(f"{case_id}|{repeat}: excluded terminations in {bad}")
            continue
        triples.append(Triple(case_id, repeat, arms["C"], arms["I"], arms["C2"]))
    return triples, excluded


def substitutes_for(case: Case, seen: dict[str, str]) -> dict[str, tuple[str, dict[str, str]]]:
    """item id -> (substitute surface, parts), from what the I arm read."""
    out: dict[str, tuple[str, dict[str, str]]] = {}
    for item in case.pii:
        surface = seen.get(item.id)
        if surface:
            out[item.id] = (surface, parts_of(item.type, surface))
    return out


def main() -> int:
    from bench.agentpii4.schema import Expectation, Locus, Provenance
    from bench.agentpii3.schema import Message
    failures = 0
    case = Case(
        id="t-0", kind="chain", register="chat",
        provenance=Provenance("template", "authored", "", "", "authored", 1.0, "authored"),
        cluster="PHONE:9164021187", conversation_id="", now="2026-09-02",
        messages=(Message("system", "x", None, ""), Message("user", "y", None, "")),
        tools=("notify_sms",), seed_records=(),
        pii=(PiiItem("i1", "PHONE", "p", "+79164021187", "+79164021187", {"digits": "9164021187"},
                     Locus("message", 1, 0, 1, "", ""), "required", False, False),),
        plain=(), negatives=(),
        expects=Expectation(("notify_sms",), "p", (), (), ()), trace=(), note="t")
    def call(number: str, restored: str, residual: tuple[str, ...] = (), refusal: str = "") -> ObservedCall:
        parsed = None if refusal else {"number": restored, "text": "hi", "sign": "SMS Aero"}
        return ObservedCall("notify_sms", {"number": number, "text": "hi"}, {"number": restored, "text": "hi"},
                            {"number": residual} if residual else {}, "number" if refusal else "", refusal, parsed, 1)
    def state(number: str) -> tuple[dict[str, object], ...]:
        return ({"table": "sms", "id": "sms-1", "tool": "notify_sms", "seq": 1,
                 "fields": {"number": number, "text": "hi", "sign": "SMS Aero"}},)
    C = ArmRun("t-0", "C", 0, (call("+79164021187", "+79164021187"),), state("+79164021187"), "ok", "done", 0.01)
    I = ArmRun("t-0", "I", 0, (call("+79990001122", "+79164021187"),), state("+79164021187"), "ok", "done", 0.01,  # noqa: E741 - the arm's own name
               {"i1": ("+79990001122", {"digits": "9990001122"})})
    C2 = ArmRun("t-0", "C2", 0, (call("+79164021187", "+79164021187"),), state("+79164021187"), "ok", "done", 0.01)
    ic, cc = compare_triple(case, Triple("t-0", 0, C, I, C2))
    if not (ic.levels.tools and ic.levels.keys and ic.levels.state):
        failures += 1
        print("FAIL clean triple", ic.levels)
    if not ic.fields or ic.fields[0].kind != "agree" or ic.fields[0].transform != "verbatim":
        failures += 1
        print("FAIL field agree", ic.fields)
    I_bad = ArmRun("t-0", "I", 0, (call("+79990001122", "+79990001122", ("+79990001122",)),), state("+79990001122"), "ok", "done", 0.01,
                   {"i1": ("+79990001122", {"digits": "9990001122"})})
    ic2, _ = compare_triple(case, Triple("t-0", 0, C, I_bad, C2))
    if ic2.levels.state or ic2.fields[0].kind != "residual":
        failures += 1
        print("FAIL residual triple", ic2.levels, ic2.fields)
    I_refused = ArmRun("t-0", "I", 0, (call("89990001122", "89164021187", (), "phone_not_e164"),), (), "ok", "done", 0.01, {})
    ic3, _ = compare_triple(case, Triple("t-0", 0, C, I_refused, C2))
    if ic3.fields[0].kind != "validated_refused":
        failures += 1
        print("FAIL refused", ic3.fields)
    print("compare: PASS" if not failures else f"compare: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
