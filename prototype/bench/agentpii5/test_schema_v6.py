"""Every corpus rule of `schema_v6.py`, shown to FAIL on a corpus built to break it.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_schema_v6

THE SHAPE OF EVERY RULE TEST, AND WHY. A CLEAN corpus is built once per phase —
one that satisfies K6-01 … K6-22 with nothing to report — and each `test_kNN`
breaks one thing in a copy of it, then asserts the rule id it broke is the one
the report names and that the clean corpus does not name it. A rule that cannot
be shown to fail, and a baseline already full of problems that hides the failure,
are the two ways an instrument stops being an instrument (CLAUDE.md).

A TINY TOOL REGISTRY, PATCHED IN PER PHASE. The real `TOOLS_V6` is 78 tools, and
the floors (K6-14 reachability, K6-15 reading verticals, K6-18 per-industry
readers) would force the fixture to offer all of them and read every vertical
back. The fixture replaces `schema_v6.TOOLS_V6` / `schema_v6.V6_META` with one
synthetic READING tool per INDUSTRY OF THE PHASE (three for the pilot, fifteen
for the full), so a broken rule is broken in isolation. The ONE admitted type is
IMEI (a [C] Luhn type, 15 digits), the only type the fixture carries.

K6-23 is NOT here: it is the pilot-floors-subset claim over `FLOORS` and lives in
`test_contracts_v6` (this module only EXPORTS the table it imports).
"""
from collections.abc import Callable, Sequence
from dataclasses import replace

from bench.agentpii4.schema import (Case, Expectation, Locus, Message, Negative, PiiItem,
                                    Provenance)
from bench.agentpii4.tools import FieldSpec, ToolSpec
from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema_v6 as sv
from bench.agentpii5.contracts import CaseV6Meta, CaseV5, Hop, ReturnForm, ToolSpecV5
from bench.agentpii5.tools_v6 import V6ToolMeta

TOTAL: dict[str, int] = {"full": 500, "pilot": 180}


# --- the tiny registry (patched into schema_v6 per phase) ---------------------------

def _tool_for(industry: str) -> ToolSpecV5:
    name = f"dev_{industry}"
    base = ToolSpec(
        name=name, source="fixture",
        schema={"type": "object",
                "properties": {"imei": {"type": "string", "description": "IMEI, 15 цифр"}},
                "required": ["imei"]},
        fields=(FieldSpec("imei", "identity", "IMEI", "digits"),),
        parse=lambda args: args, mutating=False, result_pii=("device.imei",))
    return ToolSpecV5(
        base=base, vertical="crm",
        return_forms=(ReturnForm("single", '{"device":{"imei":"356938035643809"}}',
                                 ("device.imei",)),),
        differs_from_user_form=False, suite="")


_TOOLS_BY_INDUSTRY: dict[str, ToolSpecV5] = {ind: _tool_for(ind) for ind in c.INDUSTRIES}


def _phase_tools(phase: str) -> tuple[ToolSpecV5, ...]:
    industries = sv.PILOT_INDUSTRIES if phase == "pilot" else c.INDUSTRIES
    return tuple(_TOOLS_BY_INDUSTRY[ind] for ind in industries)


def _phase_meta(phase: str) -> dict[str, V6ToolMeta]:
    industries = sv.PILOT_INDUSTRIES if phase == "pilot" else c.INDUSTRIES
    return {_TOOLS_BY_INDUSTRY[ind].base.name: V6ToolMeta("primary", "official", ind)
            for ind in industries}


def _patch_tools(phase: str) -> tuple[object, object]:
    """Point `schema_v6` at the phase's tools; return the previous values."""
    old_tools, old_meta = sv.TOOLS_V6, sv.V6_META
    sv.TOOLS_V6 = _phase_tools(phase)
    sv.V6_META = _phase_meta(phase)
    return old_tools, old_meta


# --- the corpus fixture -------------------------------------------------------------

def _imei_value(idx: int) -> str:
    """A unique 15-digit value that is NOT a valid ОГРНИП (mod 13), so K6-21 stays
    quiet while every IMEI stays unique for K6-19."""
    value = 100_000_000_000_000 + idx * 37
    while sv._ogrn_ok(str(value)):
        value += 1
    return str(value)


def _fake_item(idx: int, bare: bool) -> PiiItem:
    where = (Locus("message", 1, 0, 0, "", "") if bare
             else Locus("seed", -1, 0, 0, "r1", "imei"))
    return PiiItem(id=f"imei{idx}", type="IMEI", identity="p1", value=_imei_value(idx),
                   canonical=_imei_value(idx), parts={"digits": _imei_value(idx)},
                   where=where, duty="required", spoken=False, stale=False)


def _negative() -> Negative:
    return Negative("ЗАКАЗ-00412", 0, 11, 0, "order_number", "fixture")


def _v6_case(idx: int, industry: str, register: str, behaviour: str, streaming: bool,
             has_result: bool, carries_imei: bool, bare: bool,
             tool: str, negative: bool) -> CaseV5:
    items = [_fake_item(idx, bare)] if carries_imei else []
    negatives = (_negative(),) if negative else ()
    messages = (Message(role="system", content="s", source=None, name=""),
                Message(role="user", content="найдите устройство", source=None, name=""))
    base = Case(
        id=f"v6-{idx:04d}", kind="chain", register=register,
        provenance=Provenance(kind="template", corpus="authored", key="", shape="",
                              selection="authored", weight=1.0, licence="authored"),
        cluster=f"IMEI:{idx}", conversation_id="", now="2026-09-01",
        messages=messages, tools=(tool,), seed_records=(),
        pii=tuple(items), plain=(),
        negatives=negatives,
        expects=Expectation(reachable_tools=(tool,), primary_identity="p1",
                            must_contain=(), must_not_contain=(), validate_types=()),
        trace=(), note="synthetic v6")
    hops: tuple[Hop, ...] = ()
    if carries_imei:
        hops = (
            Hop("IN", "user", f"imei{idx}", 0, 1, "", -1, "", -1, "", False),
            Hop("OUT", "tool_arg", f"imei{idx}", 1, 1, tool, 0, "", 0, "imei", False),
            Hop("IN", "tool", f"imei{idx}", 2, 1, tool, 0, "", -1, "device.imei", False),
            Hop("OUT", "answer", f"imei{idx}", 3, 1, "", -1, "", 2, "", True),
        )
    return CaseV5(
        base=base, behaviour=behaviour, hops=hops, returns=(), forced=(), memory=(),
        pick=None, branch=None, loop=None, rag=None, document=None,
        has_result=has_result, streaming=streaming, revised_from_v4=False,
        v6=CaseV6Meta(industry=industry, provenance="synthetic", skeleton_ref="",
                      procedure_ref=""))


def _industry_plan(phase: str) -> list[tuple[str, int]]:
    if phase == "full":
        return [(ind, 60 if ind in sv.HEAVY_INDUSTRIES else 20) for ind in c.INDUSTRIES]
    return [(ind, 60) for ind in sv.PILOT_INDUSTRIES]


# 8 chat · 6 voice · 4 sloppy · 2 clean out of 20 == 40/30/20/10 %.
_REGISTERS: tuple[str, ...] = (
    ("chat",) * 8 + ("voice_raw",) * 6 + ("sloppy",) * 4 + ("clean",) * 2)


def _clean_corpus(phase: str) -> list[CaseV5]:
    """A corpus that satisfies every K6 rule of its phase with nothing to report."""
    cases: list[CaseV5] = []
    idx = 0
    imei_counter = 0
    behaviour_floor = int(sv.FLOORS["behaviour"][phase])
    per = behaviour_floor * 2
    imei_per_industry = 5
    for industry, count in _industry_plan(phase):
        tool = _TOOLS_BY_INDUSTRY[industry].base.name
        for j in range(count):
            register = _REGISTERS[idx % len(_REGISTERS)]
            behaviour = (c.BEHAVIOURS[(idx // per) % len(c.BEHAVIOURS)]
                         if idx < len(c.BEHAVIOURS) * per else "single")
            streaming = idx % 25 == 0
            has_result = idx % 10 != 0
            carries_imei = j < imei_per_industry
            if carries_imei:
                imei_counter += 1
                if phase == "full" and imei_counter <= 10:
                    behaviour = "retry_same_tool"
                elif phase == "pilot" and j == 0:
                    behaviour = "retry_same_tool"
            bare = carries_imei and (j % imei_per_industry) == 0
            negative = idx < sv.FLOORS["negative_family"][phase]
            cases.append(_v6_case(idx, industry, register, behaviour, streaming,
                                  has_result, carries_imei, bare, tool, negative))
            idx += 1
    return cases


CLEAN_FULL: list[CaseV5] = _clean_corpus("full")
CLEAN_PILOT: list[CaseV5] = _clean_corpus("pilot")


# --- assertion helpers ---------------------------------------------------------------

def _rule_ids(problems: Sequence[str]) -> set[str]:
    return {problem.split()[0] for problem in problems}


def _validate(cases: Sequence[CaseV5], phase: str) -> list[str]:
    old_tools, old_meta = _patch_tools(phase)
    try:
        return sv.validate_corpus_v6(cases, phase, TOTAL[phase])
    finally:
        sv.TOOLS_V6, sv.V6_META = old_tools, old_meta


# The clean baseline, computed once with the phase's tools and the ORIGINAL
# (empty) CLUSTERS — so a test that monkeypatches a registry for its break does
# not move the baseline it is compared against.
CLEAN_FULL_IDS: set[str] = _rule_ids(_validate(CLEAN_FULL, "full"))
CLEAN_PILOT_IDS: set[str] = _rule_ids(_validate(CLEAN_PILOT, "pilot"))


def _expect(broken: Sequence[CaseV5], rule: str, phase: str) -> list[str]:
    """`broken` trips exactly `rule` for its phase; the clean corpus does not."""
    base_ids = CLEAN_FULL_IDS if phase == "full" else CLEAN_PILOT_IDS
    seen = _rule_ids(_validate(broken, phase))
    problems: list[str] = []
    if rule not in seen:
        problems.append(f"{rule}: not in report — {sorted(seen) or 'nothing'}")
    if rule in base_ids:
        problems.append(f"{rule}: the clean corpus already names it")
    return problems


# --- the positive atom ----------------------------------------------------------------

def test_clean_corpus_is_quiet() -> list[str]:
    """The baseline every negative below is measured against."""
    problems: list[str] = []
    for phase in ("full", "pilot"):
        report = _validate(CLEAN_FULL if phase == "full" else CLEAN_PILOT, phase)
        if report:
            problems.append(f"{phase}: the clean corpus should be quiet:\n    "
                            + "\n    ".join(report[:10]))
    return problems


# --- K6-01 … K6-22 -------------------------------------------------------------------

def test_k6_01() -> list[str]:
    problems: list[str] = []
    short = _validate(CLEAN_FULL[:-1], "full")
    if not any(one.startswith("K6-01") for one in short):
        problems.append(f"K6-01 said nothing about {len(CLEAN_FULL) - 1} cases: {short[:2]}")
    dup = CLEAN_FULL + [CLEAN_FULL[0]]
    problems.extend(_expect(dup, "K6-01", "full"))
    return problems


def test_k6_02() -> list[str]:
    """Drop the IMEI item count below 60 elements while keeping the type admitted."""
    broken: list[CaseV5] = []
    dropped = 0
    for case in CLEAN_FULL:
        items = list(case.base.pii)
        if items and dropped < 20:
            items = items[1:]                # strip the IMEI element
            dropped += 1
        broken.append(replace(case, base=replace(case.base, pii=tuple(items))))
    return _expect(broken, "K6-02", "full")


def test_k6_03() -> list[str]:
    """Strip the IN/tool hop, so the type keeps elements and cases but no result."""
    broken: list[CaseV5] = []
    for case in CLEAN_FULL:
        hops = tuple(hop for hop in case.hops if not (hop.kind == "IN" and hop.owner == "tool"))
        broken.append(replace(case, hops=hops))
    return _expect(broken, "K6-03", "full")


def test_k6_04() -> list[str]:
    """A broken collision cluster: declare one, carry it nowhere near the floor."""
    saved = sv.pii_types.CLUSTERS
    sv.pii_types.CLUSTERS = {"K1": frozenset({"IMEI", "OMS_ENP"})}
    try:
        return _expect(CLEAN_FULL, "K6-04", "full")
    finally:
        sv.pii_types.CLUSTERS = saved


def test_k6_05() -> list[str]:
    """Drop the negative family to 1 occurrence."""
    broken: list[CaseV5] = []
    kept = 0
    for case in CLEAN_FULL:
        if case.base.negatives and kept >= 1:
            broken.append(replace(case, base=replace(case.base, negatives=())))
        else:
            broken.append(case)
            kept += 1
    return _expect(broken, "K6-05", "full")


def test_k6_07() -> list[str]:
    """Pour half the corpus into one heavy industry: its share leaves the ±3pp band."""
    broken = [replace(case, v6=replace(case.v6, industry="retail"))
              if idx % 2 == 0 else case for idx, case in enumerate(CLEAN_FULL)]
    return _expect(broken, "K6-07", "full")


def test_k6_08() -> list[str]:
    """Move every `parallel` case to `single`; `parallel` drops below 20."""
    broken = [replace(case, behaviour="single")
              if case.behaviour == "parallel" else case for case in CLEAN_FULL]
    return _expect(broken, "K6-08", "full")


def test_k6_09() -> list[str]:
    broken = list(CLEAN_FULL)
    flipped = 0
    for pos, case in enumerate(broken):
        if case.has_result and flipped < 150:
            broken[pos] = replace(case, has_result=False)
            flipped += 1
    return _expect(broken, "K6-09", "full")


def test_k6_10() -> list[str]:
    """Turn half the chat cases into voice; the chat share leaves its band."""
    broken = [replace(case, base=replace(case.base, register="voice_raw"))
              if case.base.register == "chat" and idx % 2 == 0 else case
              for idx, case in enumerate(CLEAN_FULL)]
    return _expect(broken, "K6-10", "full")


def test_k6_11() -> list[str]:
    broken = [replace(case, streaming=False) for case in CLEAN_FULL]
    return _expect(broken, "K6-11", "full")


def test_k6_14() -> list[str]:
    """One v6 tool is reachable nowhere."""
    target = _phase_tools("full")[-1].base.name
    broken: list[CaseV5] = []
    for case in CLEAN_FULL:
        tools = tuple(t for t in case.base.expects.reachable_tools if t != target)
        broken.append(replace(case, base=replace(
            case.base, expects=replace(case.base.expects, reachable_tools=tools))))
    return _expect(broken, "K6-14", "full")


def test_k6_15() -> list[str]:
    """An IN/tool hop crosses a leaf the tool does not declare."""
    case = next(one for one in CLEAN_FULL if one.base.pii)
    hops = list(case.hops)
    for pos, hop in enumerate(hops):
        if hop.kind == "IN" and hop.owner == "tool":
            hops[pos] = replace(hop, path="device.not_declared")
    broken = [replace(one, hops=tuple(hops)) if one.base.id == case.base.id else one
              for one in CLEAN_FULL]
    return _expect(broken, "K6-15", "full")


def test_k6_16() -> list[str]:
    """Give every IMEI a field key; the [C] type loses its bare share."""
    broken: list[CaseV5] = []
    for case in CLEAN_FULL:
        items = tuple(replace(item, where=Locus("seed", -1, 0, 0, "r1", "imei"))
                      for item in case.base.pii)
        broken.append(replace(case, base=replace(case.base, pii=items)))
    return _expect(broken, "K6-16", "full")


def test_k6_18() -> list[str]:
    """Strip the IMEI item (and its IN/tool hops) from one whole industry."""
    broken: list[CaseV5] = []
    for case in CLEAN_FULL:
        if case.v6.industry == "retail":
            broken.append(replace(case, base=replace(case.base, pii=()),
                                  hops=tuple(hop for hop in case.hops
                                             if not (hop.kind == "IN" and hop.owner == "tool"))))
        else:
            broken.append(case)
    return _expect(broken, "K6-18", "full")


def test_k6_19() -> list[str]:
    """Repeat one IMEI value in a second case under a different cluster."""
    donor = next(case for case in CLEAN_FULL if case.base.pii)
    clone = replace(donor, base=replace(donor.base, id="v6-clone",
                                        cluster="IMEI:other"))
    broken = list(CLEAN_FULL) + [clone]
    return _expect(broken, "K6-19", "full")


def test_k6_21() -> list[str]:
    """A Luhn-valid 16-digit negative: the red demonstration of OD-65."""
    luhn16 = "4111111111111111"                # a valid 16-digit Luhn number
    bad = Negative(luhn16, 0, 16, 0, "order_number", "fixture")
    case = next(one for one in CLEAN_FULL if one.base.negatives)
    broken = [replace(one, base=replace(one.base,
                                        negatives=one.base.negatives + (bad,)))
              if one.base.id == case.base.id else one for one in CLEAN_FULL]
    return _expect(broken, "K6-21", "full")


def test_k6_22() -> list[str]:
    """Un-retry every IMEI case: the new-type retry floor is missed."""
    broken = [replace(case, behaviour="single")
              if case.behaviour == "retry_same_tool" else case for case in CLEAN_FULL]
    return _expect(broken, "K6-22", "full")


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_clean_corpus_is_quiet,
    test_k6_01, test_k6_02, test_k6_03, test_k6_04, test_k6_05,
    test_k6_07, test_k6_08, test_k6_09, test_k6_10, test_k6_11,
    test_k6_14, test_k6_15, test_k6_16, test_k6_18, test_k6_19,
    test_k6_21, test_k6_22,
)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_schema_v6: PASS" if not failures else f"test_schema_v6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
