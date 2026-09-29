"""AgentPII-RU v6 — the corpus rules K6-01 … K6-22 (TZ §11.2, §4.5, §4.8).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_schema_v6

WHAT THIS FILE IS. `validate_corpus_v5` says whether a v5 corpus is a v5 corpus;
this says whether a v6 corpus is a v6 corpus. It mirrors the v5 discipline:
every rule of the corpus is one rule id, every problem is one string that STARTS
WITH ITS RULE ID, and every problem is reported — never the first one only. A
reviewer maps a line of output to a line of §11.2 without reading this file.

WHAT IS NEW AND WHY IT CANNOT REUSE v5 AS-IS. v5's `validate_corpus_v5` is keyed
to the 55 pinned tool names, the v4 register shares and the v4 type counts — all
numbers a v6 corpus deliberately moves. The v6 corpus adds an `industry` axis, a
`provenance` tag, the 55 `TypeSpec` records and the v6 tool registry, so the
floors here come from `FLOORS` (§4.5) instead of `BEHAVIOUR_FLOORS`, and the
tool coverage is read off the MERGED registry (v5's 55 plus `TOOLS_V6`), never
off `REGISTRY_V5` alone.

THE PHASE PARAMETER. `phase` is ``"pilot"`` or ``"full"``; every floor with a
"/" in §11.2 reads its ``pilot`` column in the pilot and its ``full`` column in
the full. `FLOORS` is the one table `test_contracts_v6.test_pilot_floors_subset`
imports to prove the pilot table is a strict subset of the full one (K6-23).

THE v5 CHECKSUMS ARE RE-DERIVED HERE, never imported. K6-21 must judge whether a
v6 value or negative of digit length 11/12/13/15/16 would be masked by the
engine's CONTRACT checksum (СНИЛС mod 101, ИНН weights, ОГРН/ОГРНИП mod 11/13,
Luhn). Those validators live in `pseudex.ru_pii`, and `pseudex` is a forbidden
import for every pure module (FORBIDDEN_IMPORT_PREFIX). The arithmetic is the
published algorithm, so it is restated here byte-for-byte from the engine and
pinned by `test_k6_21`'s red demonstration.

NOTHING HERE IMPORTS `pseudex`.
"""
import re
from collections import Counter
from collections.abc import Sequence

from bench.agentpii5 import contracts as c
from bench.agentpii5 import pii_types
from bench.agentpii5.contracts import CaseV5
from bench.agentpii5.tools import REGISTRY_V5
from bench.agentpii5.tools_v6 import TOOLS_V6, V6_META


# --- the v5 checksum arithmetic, restated (K6-21; see the module docstring) -------

def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _snils_ok(digits: str) -> bool:
    """СНИЛС mod 101, exactly the engine's rule (pseudex/ru_pii.py)."""
    if len(digits) != 11:
        return False
    base = [int(ch) for ch in digits[:9]]
    control = int(digits[9:])
    total = sum(num * (9 - index) for index, num in enumerate(base))
    if total < 100:
        check = total
    elif total in (100, 101):
        check = 0
    else:
        check = total % 101
        if check == 100:
            check = 0
    return check == control


def _inn_ok(digits: str) -> bool:
    """ИНН weight vectors, exactly the engine's rule."""
    if len(digits) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        control = sum(int(digits[i]) * weights[i] for i in range(9)) % 11 % 10
        return control == int(digits[9])
    if len(digits) == 12:
        weights_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        weights_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        control_11 = sum(int(digits[i]) * weights_11[i] for i in range(10)) % 11 % 10
        control_12 = sum(int(digits[i]) * weights_12[i] for i in range(11)) % 11 % 10
        return control_11 == int(digits[10]) and control_12 == int(digits[11])
    return False


def _ogrn_ok(digits: str) -> bool:
    """ОГРН (13) mod 11 / ОГРНИП (15) mod 13, exactly the engine's rule."""
    if len(digits) == 13:
        return int(digits[:12]) % 11 % 10 == int(digits[12])
    if len(digits) == 15:
        return int(digits[:14]) % 13 % 10 == int(digits[14])
    return False


def _luhn_ok(digits: str) -> bool:
    """The published Luhn digit-sum (CARD, and the three v6 Luhn types)."""
    if len(digits) < 2:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        num = int(char)
        if index % 2 == 1:
            num *= 2
            if num > 9:
                num -= 9
        total += num
    return total % 10 == 0


# The v5 [C]-type whose checksum a value of a given digit length would collide
# with. The exception is the same-algorithm case: a v6 type whose OWN checksum is
# Luhn (IMEI/ICCID/ЕНП) is allowed to be Luhn-valid where the v5 type is CARD,
# because that collision is a declared cluster (K1/K6) resolved by cue or key.
_V5_CHECKSUM_BY_LENGTH: dict[int, tuple[str, object]] = {
    11: ("SNILS", _snils_ok),
    12: ("INN", _inn_ok),
    13: ("OGRN", _ogrn_ok),
    15: ("OGRNIP", _ogrn_ok),
    16: ("CARD", _luhn_ok),
}
_LUHN_V6_TYPES: frozenset[str] = frozenset(
    t.id for t in pii_types.TYPE_REGISTRY if t.generated_checksum == "luhn")
_OGRNIP_V6_TYPES: frozenset[str] = frozenset(
    t.id for t in pii_types.TYPE_REGISTRY if t.generated_checksum == "ogrnip")


# --- the floor table (K6-23: pilot is a strict subset of full) --------------------

FLOORS: dict[str, dict[str, int | float]] = {
    "type_elements": {"full": 60, "pilot": 0},       # elements of an admitted type
    "type_cases": {"full": 34, "pilot": 10},         # distinct cases carrying a type
    "in_tool_hops": {"full": 5, "pilot": 3},         # IN/tool hops per type
    "out_tool_arg_hops": {"full": 5, "pilot": 3},    # OUT/tool_arg hops per type
    "behaviour": {"full": 20, "pilot": 3},           # cases per behaviour
    "cluster_cases": {"full": 20, "pilot": 1},       # collision-cluster cases
    "cluster_member": {"full": 5, "pilot": 1},       # each cluster member as a positive
    "negative_family": {"full": 20, "pilot": 3},     # negatives per family
    "streaming": {"full": 20, "pilot": 1},           # streaming cases
    "retry_new_type": {"full": 10, "pilot": 1},      # retry_same_tool with a new type
}

# The §4.8 floors that are NOT phase-split (they are a claim about the whole
# corpus in either phase, or are a share rather than a count).
MIN_SHARE_WITH_RESULT_V6: float = 0.75
BARE_SHARE: float = 0.20                      # [C] bare floor and bare_typed floor
SHARE_TOLERANCE: float = 0.03                 # ±3pp, inherited from v5's SHARE_TOLERANCE

# OD-05 industry weights: five heavy at 12%, ten light at 4% (TZ §4.4).
HEAVY_INDUSTRIES: tuple[str, ...] = (
    "retail", "logistics", "banks_mfo_collectors", "medicine", "internal_bi")
LIGHT_INDUSTRIES: tuple[str, ...] = tuple(i for i in c.INDUSTRIES if i not in HEAVY_INDUSTRIES)
INDUSTRY_WEIGHTS: dict[str, float] = {
    industry: 0.12 if industry in HEAVY_INDUSTRIES else 0.04 for industry in c.INDUSTRIES}
# The types that live only in a LIGHT industry and may therefore lift it above its
# 4% weight (TZ §4.4 — the named list).
LIGHT_ONLY_TYPES: tuple[str, ...] = (
    "IMSI", "SUBSCRIBER_ACCOUNT", "DIPLOMA_NUMBER", "SCHOOL_CERT_NUMBER",
    "EMPLOYMENT_CONTRACT_NUMBER")

# OD-07 register mix (TZ §4.8): chat 0.40 / voice 0.30 / sloppy 0.20 / clean 0.10.
REGISTER_SHARES_V6: dict[str, float] = {"chat": 0.40, "voice": 0.30, "sloppy": 0.20,
                                        "clean": 0.10}

# The pilot's three industries (TZ §4.5): the pilot holdout and the per-industry
# `retry_same_tool` floor key on these.
PILOT_INDUSTRIES: tuple[str, ...] = ("retail", "banks_mfo_collectors", "medicine")


# --- reading the corpus: admitted types, stats, merged registry -------------------

def _admitted_types(cases: Sequence[CaseV5]) -> tuple[str, ...]:
    """The v6 item types a case of this corpus actually carries.

    «Admitted» is presence, not registry membership (TZ §4.5's last row): a
    registered type with no case in this phase is printed as «registered, no
    cases» and must NOT redden. A type present in at least one case owes the
    floor.
    """
    present = {item.type for case in cases for item in case.base.pii}
    return tuple(t.id for t in pii_types.TYPE_REGISTRY
                 if t.item_type and t.origin == pii_types.ORIGIN_V6 and t.id in present)


def _type_stats(cases: Sequence[CaseV5], admitted: Sequence[str]) -> dict[str, dict[str, int]]:
    """Per admitted type: elements, distinct cases, total hops, IN/tool hops,
    OUT/tool_arg hops — the four counts K6-02/K6-03 print beside their verdicts."""
    admitted_set = set(admitted)
    stats: dict[str, dict[str, int]] = {
        t: {"elements": 0, "cases": 0, "hops": 0, "in_tool": 0, "out_arg": 0}
        for t in admitted}
    for case in cases:
        items = {item.id: item for item in case.base.pii}
        for item in case.base.pii:
            if item.type not in admitted_set:
                continue
            stats[item.type]["elements"] += 1
        carrying = {item.type for item in case.base.pii} & admitted_set
        for t in carrying:
            stats[t]["cases"] += 1
        for hop in case.hops:
            item = items.get(hop.item_id)
            if item is None or item.type not in admitted_set:
                continue
            stats[item.type]["hops"] += 1
            if hop.kind == "IN" and hop.owner == "tool":
                stats[item.type]["in_tool"] += 1
            elif hop.kind == "OUT" and hop.owner == "tool_arg":
                stats[item.type]["out_arg"] += 1
    return stats


def merged_registry() -> dict[str, object]:
    """The v5 55 plus `TOOLS_V6`, the registry K6-14/K6-15 read (TZ §8.1: the old
    checks keep reading the 55 PINNED names; the v6 checks read the merged set).

    Built on call rather than at import: `REGISTRY_V5` widens v4's module object
    at import, and a module-level merge would freeze the order of those two
    side effects against whichever module imported this one first.
    """
    merged: dict[str, object] = dict(REGISTRY_V5)                 # type: ignore[arg-type]
    merged.update({spec.base.name: spec for spec in TOOLS_V6})    # type: ignore[attr-defined]
    return merged


def _merged_vertical() -> dict[str, str]:
    vertical = dict(c.TOOL_VERTICAL)
    vertical.update({spec.base.name: spec.vertical for spec in TOOLS_V6})  # type: ignore[attr-defined]
    return vertical


def _industry(case: CaseV5) -> str:
    return case.v6.industry if case.v6 is not None else ""


# --- the printable table (K6-02 «elements, cases, hops печатаются») -----------------

def type_floor_table(cases: Sequence[CaseV5], phase: str) -> list[str]:
    """One line per admitted type: the three counts and the floor verdict.

    THE COUNTS ARE THE POINT (K6-02). A verdict without the number behind it is a
    number a reviewer has to recompute by hand; the table prints elements, cases
    and hops beside each floor so a red line is legible on its own.
    """
    admitted = _admitted_types(cases)
    stats = _type_stats(cases, admitted)
    lines: list[str] = [f"полы по типу ({phase}):"]
    elements_floor = int(FLOORS["type_elements"][phase])
    cases_floor = int(FLOORS["type_cases"][phase])
    for t in admitted:
        s = stats[t]
        ok_elements = s["elements"] >= elements_floor
        ok_cases = s["cases"] >= cases_floor
        mark = "OK" if (ok_elements and ok_cases) else "!"
        lines.append(
            f"  {mark} {t:<24} {s['elements']:>3} элементов · {s['cases']:>3} случаев · "
            f"{s['hops']:>4} хопов (пол {elements_floor} элементов / {cases_floor} случаев)")
    return lines


# --- the corpus rules --------------------------------------------------------------

def validate_corpus_v6(cases: Sequence[CaseV5], phase: str, total: int) -> list[str]:
    """Every rule of §11.2's K6 table the corpus violates. `phase` is ``"pilot"``
    or ``"full"``; `total` is the phase's case count (180 / 500).

    K6-12/K6-13 (the frozen holdout, the miniature ladder), K6-17 (residue) and
    K6-20 (per-tier type table) are claims about `ladder.json` on disk and live
    in `build_v6.py`, exactly as v5's K12 lives in `build.py` — a corpus-level
    validator that silently passed them would be the worse of the two options.
    """
    if phase not in ("pilot", "full"):
        return [f"K6-00 phase {phase!r} is not one of ('pilot', 'full')"]
    problems: list[str] = []
    n = len(cases)
    admitted = _admitted_types(cases)
    admitted_set = set(admitted)
    stats = _type_stats(cases, admitted)

    # K6-01 size = N of the phase, and every case id unique (two cases under one
    # id are one case counted twice in every share below).
    if n != total:
        problems.append(f"K6-01 corpus holds {n} cases, phase {phase} expects {total}")
    ids = [case.base.id for case in cases]
    if len(set(ids)) != len(ids):
        duplicates = sorted({one for one in ids if ids.count(one) > 1})
        problems.append(f"K6-01 duplicate case ids: {duplicates[:8]}")

    # K6-02 every admitted type at its element AND case floor, counts printed.
    elements_floor = int(FLOORS["type_elements"][phase])
    cases_floor = int(FLOORS["type_cases"][phase])
    for t in admitted:
        s = stats[t]
        if s["elements"] < elements_floor:
            problems.append(f"K6-02 type {t}: {s['elements']} elements, {s['cases']} cases, "
                            f"{s['hops']} hops — floor {elements_floor} elements")
        if s["cases"] < cases_floor:
            problems.append(f"K6-02 type {t}: {s['elements']} elements, {s['cases']} cases, "
                            f"{s['hops']} hops — floor {cases_floor} cases")

    # K6-03 every admitted type crosses ≥1 argument AND ≥1 result path, and at
    # least the phase's IN/tool and OUT/tool_arg hop floors (V6T-08 + §4.5).
    in_tool_floor = int(FLOORS["in_tool_hops"][phase])
    out_arg_floor = int(FLOORS["out_tool_arg_hops"][phase])
    for t in admitted:
        s = stats[t]
        if s["in_tool"] < 1:
            problems.append(f"K6-03 type {t}: 0 IN/tool result paths, needs ≥1")
        if s["out_arg"] < 1:
            problems.append(f"K6-03 type {t}: 0 OUT/tool_arg arguments, needs ≥1")
        if s["in_tool"] < in_tool_floor:
            problems.append(f"K6-03 type {t}: {s['in_tool']} IN/tool hops, "
                            f"floor {in_tool_floor}")
        if s["out_arg"] < out_arg_floor:
            problems.append(f"K6-03 type {t}: {s['out_arg']} OUT/tool_arg hops, "
                            f"floor {out_arg_floor}")

    # K6-04 collision clusters: ≥ cluster_cases cases, each member positive in ≥
    # cluster_member of them. A cluster case carries ≥2 DISTINCT members of the
    # cluster (two same-form values a cue/key must tell apart).
    cluster_cases_floor = int(FLOORS["cluster_cases"][phase])
    cluster_member_floor = int(FLOORS["cluster_member"][phase])
    for cluster_id, members in sorted(pii_types.CLUSTERS.items()):
        member_set = set(members)
        cluster_cases = [case for case in cases
                         if len({item.type for item in case.base.pii} & member_set) >= 2]
        if len(cluster_cases) < cluster_cases_floor:
            problems.append(f"K6-04 cluster {cluster_id}: {len(cluster_cases)} cases carry ≥2 "
                            f"members, floor {cluster_cases_floor}")
        for member in sorted(member_set):
            seen = sum(1 for case in cluster_cases
                       if any(item.type == member for item in case.base.pii))
            if seen < cluster_member_floor:
                problems.append(f"K6-04 cluster {cluster_id} member {member}: {seen} "
                                f"cluster cases carry it, floor {cluster_member_floor}")

    # K6-05 every negative family present in the corpus at its occurrence floor.
    negative_floor = int(FLOORS["negative_family"][phase])
    family_counts: Counter[str] = Counter(
        negative.family for case in cases for negative in case.base.negatives)
    for family, seen in sorted(family_counts.items()):
        if seen < negative_floor:
            problems.append(f"K6-05 negative family {family!r}: {seen} negatives, "
                            f"floor {negative_floor}")

    # K6-07 industry shares ±3pp of the OD-05 weights. Full only: the pilot's
    # composition is fixed (60 / 60 / 60, §4.5), not the OD-05 weights. A light
    # industry lifted by a light-only type may exceed 4% + 3pp.
    if phase == "full" and n:
        for industry in c.INDUSTRIES:
            share = sum(1 for case in cases if _industry(case) == industry) / n
            weight = INDUSTRY_WEIGHTS[industry]
            if industry in HEAVY_INDUSTRIES:
                if abs(share - weight) > SHARE_TOLERANCE + 1e-9:
                    problems.append(f"K6-07 industry {industry}: share {share:.1%}, "
                                    f"weight {weight:.0%} ± {SHARE_TOLERANCE:.0%}")
            elif not _industry_lifted(industry, admitted_set):
                if abs(share - weight) > SHARE_TOLERANCE + 1e-9:
                    problems.append(f"K6-07 industry {industry}: share {share:.1%}, "
                                    f"weight {weight:.0%} ± {SHARE_TOLERANCE:.0%}")
            elif share < weight - SHARE_TOLERANCE - 1e-9:
                problems.append(f"K6-07 industry {industry}: share {share:.1%} below the "
                                f"lifted floor {weight - SHARE_TOLERANCE:.1%}")

    # K6-08 every behaviour at its floor (a floor, no ceiling).
    behaviour_floor = int(FLOORS["behaviour"][phase])
    behaviour_counts = Counter(case.behaviour for case in cases)
    for behaviour in c.BEHAVIOURS:
        seen = behaviour_counts.get(behaviour, 0)
        if seen < behaviour_floor:
            problems.append(f"K6-08 behaviour {behaviour!r}: {seen} cases, "
                            f"floor {behaviour_floor}")

    # K6-09 the tool result is the base loop.
    with_result = sum(1 for case in cases if case.has_result) / max(1, n)
    if with_result < MIN_SHARE_WITH_RESULT_V6:
        problems.append(f"K6-09 {with_result:.1%} of cases reach a tool result, "
                        f"floor {MIN_SHARE_WITH_RESULT_V6:.0%}")

    # K6-10 the register mix, voice as one bucket (OD-07).
    if n:
        registers: Counter[str] = Counter(case.base.register for case in cases)
        seen_registers = {"voice": sum(registers.get(name, 0) for name in c.SPEECH_REGISTERS)}
        for name in c.REGISTERS:
            if name not in c.SPEECH_REGISTERS:
                seen_registers[name] = registers.get(name, 0)
        for name, want in REGISTER_SHARES_V6.items():
            share = seen_registers.get(name, 0) / n
            if abs(share - want) > SHARE_TOLERANCE + 1e-9:
                problems.append(f"K6-10 register {name!r}: share {share:.1%}, "
                                f"want {want:.0%} ± {SHARE_TOLERANCE:.0%}")

    # K6-11 streaming.
    streaming_floor = int(FLOORS["streaming"][phase])
    streaming = sum(1 for case in cases if case.streaming)
    if streaming < streaming_floor:
        problems.append(f"K6-11 {streaming} streaming cases, floor {streaming_floor}")

    # K6-14 every v6 tool reachable in ≥ MIN_TYPE_DENOMINATOR cases.
    v6_tool_names = tuple(spec.base.name for spec in TOOLS_V6)  # type: ignore[attr-defined]
    reach: Counter[str] = Counter()
    for case in cases:
        for name in case.base.expects.reachable_tools:
            if name in v6_tool_names:
                reach[name] += 1
    for name in v6_tool_names:
        if reach.get(name, 0) < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"K6-14 tool {name!r} reachable in {reach.get(name, 0)} cases, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")

    # K6-15 v5's K16/K17 against the MERGED registry: a reading vertical the
    # corpus offers but never reads back, and an IN/tool hop crossing a leaf the
    # tool does not declare.
    problems.extend(_unread_verticals_v6(cases))
    problems.extend(_undeclared_result_paths_v6(cases))

    # K6-16 bare values: [C] ≥ 20% of its cases bare; bare_typed ≥ 20%; every
    # other [K] type 0% bare positives.
    problems.extend(_bare_problems(cases, admitted))

    # K6-18 every industry has ≥1 reading tool and ≥5 IN/tool hops of NEW types.
    if phase == "full" or n:
        problems.extend(_industry_reading_problems(cases))

    # K6-19 a generated value is not repeated across cases, except within one
    # declared person cluster.
    problems.extend(_repeated_value_problems(cases, admitted_set))

    # K6-21 a value or negative of digit length 11/12/13/15/16 is not a valid
    # checksum of the v5 [C]-type of the same length (except same-algorithm Luhn).
    problems.extend(_length_checksum_problems(cases, admitted_set))

    # K6-22 retry_same_tool with a NEW type.
    retry_new = [case for case in cases
                 if case.behaviour == "retry_same_tool"
                 and any(item.type in admitted_set for item in case.base.pii)]
    retry_floor = int(FLOORS["retry_new_type"][phase])
    if phase == "full":
        if len(retry_new) < retry_floor:
            problems.append(f"K6-22 {len(retry_new)} retry_same_tool cases carry a new type, "
                            f"floor {retry_floor}")
    else:
        for industry in PILOT_INDUSTRIES:
            seen = sum(1 for case in retry_new if _industry(case) == industry)
            if seen < 1:
                problems.append(f"K6-22 pilot industry {industry}: {seen} retry_same_tool "
                                f"cases carry a new type, floor 1")
    return problems


def _industry_lifted(industry: str, admitted: set[str]) -> bool:
    """An industry lifted above its light weight by a light-only type it hosts.

    The lift is the FLOOR's doing, so it keys on ADMITTED types (present in ≥1
    case) — a registered-but-absent light-only type forces nothing.
    """
    for t in pii_types.TYPE_REGISTRY:
        if t.id not in admitted or t.origin != pii_types.ORIGIN_V6:
            continue
        if industry not in t.industries:
            continue
        if t.industries and all(ind in LIGHT_INDUSTRIES for ind in t.industries):
            return True
    return False


_ARRAY_INDEX = re.compile(r"\[\d+\]")


def _undeclared_result_paths_v6(cases: Sequence[CaseV5]) -> list[str]:
    """K6-15's K17 half: an IN/tool hop whose leaf the tool's `result_pii` does
    not declare (array indexes erased). The merged registry's v6 tools are in
    scope, so a v6 result path the corpus crosses can no longer be deleted in
    silence, and a hop can no longer cross a leaf nothing declares."""
    registry = merged_registry()
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for case in cases:
        for hop in case.hops:
            if hop.kind != "IN" or hop.owner != "tool":
                continue
            spec = registry.get(hop.tool_name)
            if spec is None:
                continue
            leaf = _ARRAY_INDEX.sub("[]", hop.path)
            if leaf in spec.base.result_pii or (hop.tool_name, leaf) in seen:
                continue
            seen.add((hop.tool_name, leaf))
            problems.append(
                f"K6-15 {case.base.id}: hop {hop.hop_index} crosses {hop.tool_name}.{leaf}, "
                f"which the tool's result_pii does not declare — "
                f"declared {list(spec.base.result_pii)}")
    return problems


def _unread_verticals_v6(cases: Sequence[CaseV5]) -> list[str]:
    """K6-15's K16 half: a vertical whose READING tool (non-mutating, result_pii
    non-empty) the corpus OFFERS is crossed by no case (any PII type) — its return
    notation is checked by nothing. A mutating-only vertical is exempt and named.

    VERTICAL COVERAGE IS COUNTED BY CASE, NOT BY HOP, AND BY ANY PII TYPE. A
    vertical whose reader returns v5 NAME/PHONE is still read back by a case, so
    it crosses the vertical exactly as a v6 type does; counting IN/tool hops of
    v6 types only would call a vertical «unread» while cases read its v5 results
    back, which is coverage, not a gap."""
    registry = merged_registry()
    vertical = _merged_vertical()
    offered: set[str] = {name for case in cases for name in case.base.tools}
    readable: dict[str, list[str]] = {}
    for name, spec in sorted(registry.items()):
        if spec.base.mutating or not spec.base.result_pii or name not in offered:
            continue
        readable.setdefault(vertical.get(name, ""), []).append(name)
    crossed: dict[str, set[str]] = {}
    for case in cases:
        for hop in case.hops:
            if hop.kind != "IN" or hop.owner != "tool":
                continue
            vert = vertical.get(hop.tool_name, "")
            if vert:
                crossed.setdefault(vert, set()).add(case.base.id)
    problems: list[str] = []
    for vert, readers in sorted(readable.items()):
        if not vert:
            continue
        if len(crossed.get(vert, set())) < 1:
            problems.append(
                f"K6-15 vertical {vert!r} is crossed by {len(crossed.get(vert, set()))} "
                f"cases, below 1, while {readers} read personal data back")
    return problems


def _bare_problems(cases: Sequence[CaseV5], admitted: Sequence[str]) -> list[str]:
    """K6-16: the bare-value rule. A value is BARE when its case gives it neither
    a cue word in the message nor a field key at its locus.

    BEST-EFFORT, AND HONEST ABOUT IT. The precise cue-window and key encoding is
    owned by the case builder (`scenarios6/common6.py`, a later phase); until it
    lands the schema approximates «cued» as «the carrying message holds one of
    the type's cue words» and «keyed» as «the locus path is one of the type's
    field keys». The three assertions it can still make are: [C] types owe ≥20%
    bare cases, a `bare_typed` type owes ≥20% bare, and any other [K] type owes
    0% bare positives.

    THE CUE MATCH IS CUE-SIMILAR, NOT EXACT-ONLY (K6-16). The sloppy register
    typos a cue word by one edit (`pools.typo`: swap/drop/double/transpose), so
    «огррнип» must still cue ОГРНИП, «эпьс» cue ЭПТС and «диплм» cue
    DIPLOMA_NUMBER. `_cue_hit` treats a cue as present when it appears exactly OR
    when its tokens appear as a CONTIGUOUS run of message tokens, each token
    matching exactly or — for tokens of four characters or more, the only length
    `pools.typo` edits — within one Damerau edit. A bare digit/hex value shares
    no characters with any cue token, so a genuinely bare value stays bare.
    """
    problems: list[str] = []
    by_type: dict[str, int] = Counter()
    by_type_bare: dict[str, int] = Counter()
    for case in cases:
        messages = [m.content for m in case.base.messages]
        for item in case.base.pii:
            t = item.type
            if t not in set(admitted):
                continue
            spec = _type_spec(t)
            if spec is None:
                continue
            by_type[t] += 1
            if _is_bare(item, spec, messages):
                by_type_bare[t] += 1
    for t in admitted:
        spec = _type_spec(t)
        if spec is None:
            continue
        total = by_type.get(t, 0)
        bare = by_type_bare.get(t, 0)
        if spec.type_class == pii_types.TYPE_CLASS_C:
            if bare < BARE_SHARE * total - 1e-9:
                problems.append(f"K6-16 [C] type {t}: {bare}/{total} bare, "
                                f"floor {BARE_SHARE:.0%}")
        elif spec.bare_typed:
            if bare < BARE_SHARE * total - 1e-9:
                problems.append(f"K6-16 bare_typed type {t}: {bare}/{total} bare, "
                                f"floor {BARE_SHARE:.0%}")
        else:
            if bare > 0:
                problems.append(f"K6-16 [K] type {t}: {bare} bare positives, "
                                f"allowed 0 (no bare_typed)")
    return problems


def _type_spec(type_id: str):
    for t in pii_types.TYPE_REGISTRY:
        if t.id == type_id:
            return t
    return None


_WORD_RE = re.compile(r"[a-zа-яё0-9]+")


def _tokenize(text: str) -> list[str]:
    """The lower-cased word tokens of a message or a cue, split on any run of
    non-alphanumeric characters. A hyphenated cue («вин-код») and the same words
    written with a space or another separator become the same token list."""
    return _WORD_RE.findall(text.lower())


def _damerau(a: str, b: str) -> int:
    """Optimal string alignment distance — insertion, deletion, substitution and
    adjacent transposition each cost 1, exactly `pools.typo`'s four edits.

    Capped at «far apart»: `_cue_hit` only ever asks «within one edit», and a
    length gap larger than one already answers no, so the DP never runs over a
    long digit run against a long cue token.
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 1:
        return 99
    prevprev: list[int] | None = None
    prev = list(range(len(b) + 1))
    curr = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        curr[0] = i
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                curr[j] = min(curr[j], prevprev[j - 2] + 1)  # type: ignore[index]
        prevprev, prev, curr = prev, curr, [0] * (len(b) + 1)
    return prev[len(b)]


def _word_match(cue_word: str, text_word: str) -> bool:
    """A cue token matches a message token exactly, or within one edit when the
    token is long enough for the sloppy register to have typo'd it — `pools.typo`
    never edits a word shorter than four characters, so a short cue token only
    counts when it is written verbatim."""
    if cue_word == text_word:
        return True
    return len(cue_word) >= 4 and _damerau(cue_word, text_word) <= 1


def _cue_hit(cue: str, text: str) -> bool:
    """Whether a registered cue is present in a message, allowing the sloppy
    register's per-word one-edit typo (a CUE-SIMILAR match).

    Exact substring first — the common case, and the only case for a cue whose
    words are written verbatim. Otherwise every cue token must appear as a
    CONTIGUOUS run of message tokens, each matching exactly or within one
    Damerau edit. A bare value is a digit/hex/glyph run that shares no token
    with any cue, so it is never falsely cued by this rule.
    """
    cue = cue.strip().lower()
    if not cue:
        return False
    text = text.lower()
    if cue in text:
        return True
    cue_words = _tokenize(cue)
    text_words = _tokenize(text)
    if not cue_words or len(text_words) < len(cue_words):
        return False
    for start in range(len(text_words) - len(cue_words) + 1):
        window = text_words[start:start + len(cue_words)]
        if all(_word_match(cue_word, text_word)
               for cue_word, text_word in zip(cue_words, window)):
            return True
    return False


def _is_bare(item, spec, messages: Sequence[str]) -> bool:
    """Whether one item's value is carried with neither a cue nor a key."""
    if item.where.kind == "seed" and item.where.path in spec.field_keys:
        return False
    if item.where.kind == "message" and item.where.msg < len(messages):
        text = messages[item.where.msg]
        if any(cue and _cue_hit(cue, text) for cue in spec.cues):
            return False
    return True


def _industry_reading_problems(cases: Sequence[CaseV5]) -> list[str]:
    """K6-18: every industry PRESENT in the corpus has ≥1 reading tool AND ≥5
    IN/tool hops of NEW types (§2.2 V6T-09 + the §11.2 K6-18 row).

    ONLY PRESENT INDUSTRIES, on purpose. The pilot carries three industries and
    the other twelve are simply not part of this phase; demanding a reading tool
    and five new-type hops of an absent industry would refuse the pilot for the
    twelve industries it was never asked to cover.
    """
    problems: list[str] = []
    present = {_industry(case) for case in cases if _industry(case)}
    v6_names = {spec.base.name for spec in TOOLS_V6}  # type: ignore[attr-defined]
    industry_tools: dict[str, set[str]] = {industry: set() for industry in present}
    for spec in TOOLS_V6:
        meta = V6_META.get(spec.base.name)             # type: ignore[attr-defined]
        if meta is None or meta.industry not in present:
            continue
        industry_tools[meta.industry].add(spec.base.name)  # type: ignore[attr-defined]
    admitted = set(_admitted_types(cases))
    reading = {name for name, spec in merged_registry().items()
               if not spec.base.mutating and spec.base.result_pii}
    in_tool_new: dict[str, int] = {industry: 0 for industry in present}
    for case in cases:
        ind = _industry(case)
        if ind not in in_tool_new:
            continue
        items = {item.id: item for item in case.base.pii}
        for hop in case.hops:
            if hop.kind != "IN" or hop.owner != "tool":
                continue
            item = items.get(hop.item_id)
            if item is not None and item.type in admitted:
                in_tool_new[ind] += 1
    for industry in sorted(present):
        has_reader = any(name in reading for name in industry_tools[industry])
        if not has_reader:
            problems.append(f"K6-18 industry {industry}: no reading tool (mutating-only "
                            f"or no result_pii) among {sorted(industry_tools[industry]) or ['none']}")
        if in_tool_new[industry] < c.MIN_TYPE_DENOMINATOR and v6_names:
            problems.append(f"K6-18 industry {industry}: {in_tool_new[industry]} IN/tool hops "
                            f"of new types, floor {c.MIN_TYPE_DENOMINATOR}")
    return problems


def _repeated_value_problems(cases: Sequence[CaseV5], admitted: set[str]) -> list[str]:
    """K6-19: a generated value must not repeat across cases except within one
    declared person cluster (`case.base.cluster` — the same person in two cases).

    THE KEY IS THE CANONICAL VALUE, not the surface: gen_v6 mints the canonical
    form and two registers may spell it differently; a repeated canonical in two
    DIFFERENT clusters is the defect this rule refuses.
    """
    problems: list[str] = []
    owner: dict[str, tuple[str, str]] = {}
    for case in cases:
        for item in case.base.pii:
            if item.type not in admitted:
                continue
            key = item.canonical or item.value
            if not key:
                continue
            if key in owner and owner[key][0] != case.base.cluster:
                problems.append(f"K6-19 value {key!r} of type {item.type} repeats in "
                                f"{owner[key][1]} and {case.base.id} under different clusters "
                                f"({owner[key][0]!r} vs {case.base.cluster!r})")
            elif key not in owner:
                owner[key] = (case.base.cluster, case.base.id)
    return problems


def _length_checksum_problems(cases: Sequence[CaseV5], admitted: set[str]) -> list[str]:
    """K6-21: a value (positive) or negative of digit length 11/12/13/15/16 must
    NOT be a valid checksum of the v5 [C]-type of the same length, so the engine's
    contract mask (CARD/INN/OGRN) cannot swallow it as an error. A v6 type whose
    OWN checksum is Luhn (IMEI/ICCID/ЕНП) is exempt where the v5 type is CARD —
    that collision is a declared cluster resolved by cue or key."""
    problems: list[str] = []
    for case in cases:
        for item in case.base.pii:
            if item.type not in admitted:
                continue
            problems.extend(_check_digit_value(case.base.id, item.type, item.value))
        for negative in case.base.negatives:
            problems.extend(_check_digit_value(case.base.id, "", negative.value))
    return problems


def _check_digit_value(case_id: str, type_id: str, value: str) -> list[str]:
    digits = _digits(value)
    entry = _V5_CHECKSUM_BY_LENGTH.get(len(digits))
    if entry is None:
        return []
    v5_name, checker = entry
    if not checker(digits):                       # type: ignore[operator]
        return []
    if v5_name == "CARD" and type_id in _LUHN_V6_TYPES:
        return []
    if v5_name == "OGRNIP" and type_id in _OGRNIP_V6_TYPES:
        return []
    return [f"K6-21 {case_id}: {type_id or 'negative'} value {digits!r} is a valid "
            f"{v5_name} checksum of length {len(digits)} — the contract mask would "
            f"swallow it as an error"]
