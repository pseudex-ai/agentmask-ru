"""AgentPII-RU v6 — the deterministic full-corpus allocation (TZ §4.3, §4.4).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.scenarios6.plan_v6

WHAT THIS FILE IS. The table `build_full` consumes: a tuple of `PlanRow`
(`types, industry, behaviour, count`), where `types` is the tuple of v6 type ids
one case carries (1 for a conversational case, 6 for a record/dossier case).
The corpus is DETERMINED here; the sentences are built in `build_full`.

THE SHAPE. Every admitted type appears in 34 distinct cases: 30 «dossier»
slots (a record that reads six types back in one turn) plus four conversational
slots. Because a case seeds the value AND the user dictates it, one appearance
mints TWO items (a seed item and a message item), so 34 appearances are ≥ 60
elements before any behaviour doubles a mint — the K6-02 element floor holds
without inventing extra people. Six chain types (ОСАГО/VIN/ЭПТС/IBAN/ОГРНИП)
also appear in 20 `sequential_chain` cases whose reader returns two types.

THE INDUSTRY AXIS (K6-07). Cases are labelled by a deterministic greedy toward
`INDUSTRY_CASES`: five heavy industries at ~12% and ten light industries at
~4% (±3pp), with the light-only types (IMSI, SUBSCRIBER_ACCOUNT, DIPLOMA_NUMBER,
SCHOOL_CERT_NUMBER, EMPLOYMENT_CONTRACT_NUMBER) lifting telecom/education/hr/
legal above 4%. The label is a truthful home of the case's own types (each case
is offered a label only from its types' `industries`).

NOTHING HERE IMPORTS `pseudex` OR `licensing`, AND NOTHING HERE SEARCHES A
FINISHED STRING.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from bench.agentpii5 import contracts as c
from bench.agentpii5 import pii_types
from bench.agentpii5 import schema_v6 as sv

HEAVY: tuple[str, ...] = ("retail", "logistics", "banks_mfo_collectors", "medicine", "internal_bi")
LIFTED: tuple[str, ...] = ("telecom", "education", "hr", "legal")
NONLIFTED_LIGHT: tuple[str, ...] = ("insurance", "auto", "real_estate", "hospitality",
                                    "government_services", "marketing_cdp")

# The case-count targets the greedy label assignment steers toward. Sum 500;
# the ±3pp tolerance (§4.4) absorbs the greedy's rounding.
INDUSTRY_CASES: dict[str, int] = {i: 58 for i in HEAVY}
INDUSTRY_CASES.update({"telecom": 34, "education": 17, "hr": 51, "legal": 17})
INDUSTRY_CASES.update({i: 15 for i in NONLIFTED_LIGHT})

# The sequential_chain pairs: a READ tool whose ONE result returns two types.
CHAIN_PAIRS: tuple[tuple[str, str], ...] = (
    ("OSAGO_POLICY", "VIN"),
    ("EPTS_NUMBER", "VIN"),
    ("IBAN", "OGRNIP"),
)

DOSSIER_SLOTS: int = 6
DOSSIER_PER_TYPE: int = 30
CHAIN_CASES: int = 20
# The two types whose READ tool declares the forced-error echo `error.subject`
# (diploma_registry_check, hr_employee_get) — the only ones a `retry_same_tool`
# case may cross without an undeclared result leaf (K6-15).
RETRY_TYPES: tuple[str, ...] = ("DIPLOMA_NUMBER", "EMPLOYEE_TAB_NUMBER")
# The single-type behaviours (every non-chain, non-parallel behaviour except
# `retry_same_tool`, which is routed to RETRY_TYPES only).
SINGLE_BEHAVIOURS: tuple[str, ...] = (
    "single", "same_tool_other_target", "fanout_pick", "branching",
    "user_in_loop", "memory_anaphora", "rag", "document")


@dataclass(frozen=True)
class PlanRow:
    """One batch of `count` cases sharing their type tuple, industry and
    behaviour. `types` is 1-long for a conversational case, 2-long for a
    chain, and 6-long for a record/dossier case. `bare` marks the IMEI cases
    whose value is dictated with no cue and stored at a non-key leaf (K6-16)."""

    types: tuple[str, ...]
    industry: str
    behaviour: str
    count: int
    bare: bool = False


def _all_types() -> tuple[str, ...]:
    return tuple(t.id for t in pii_types.TYPE_REGISTRY
                 if t.item_type and t.origin == pii_types.ORIGIN_V6)


def _type_spec(type_id: str) -> pii_types.TypeSpec:
    for spec in pii_types.TYPE_REGISTRY:
        if spec.id == type_id:
            return spec
    raise ValueError(f"{type_id!r} is not a registered type")


def _chain_types() -> frozenset[str]:
    return frozenset(t for pair in CHAIN_PAIRS for t in pair)


def _build_rows() -> list[tuple[tuple[str, ...], str, bool]]:
    """The raw (types, behaviour, bare) cases: 20 chains, 277 dossiers, 202
    singles (of which 7 are bare IMEI)."""
    rows: list[tuple[tuple[str, ...], str, bool]] = []
    all_types = _all_types()

    for k in range(CHAIN_CASES):
        a, b = CHAIN_PAIRS[k % len(CHAIN_PAIRS)]
        rows.append(((a, b), "sequential_chain", False))

    # Thirteen types carry one extra dossier slot (31 instead of 30) and three
    # singles in exchange; IMEI carries seven bare singles and 27 dossier slots.
    extra_dossier = sorted(t for t in all_types
                           if t not in _chain_types() and t not in RETRY_TYPES
                           and t != "IMEI")[:13]
    dossier_counts = {t: DOSSIER_PER_TYPE for t in all_types}
    for t in extra_dossier:
        dossier_counts[t] += 1
    dossier_counts["IMEI"] = 27
    remaining = dict(dossier_counts)
    while any(remaining.values()):
        batch: list[str] = []
        for _ in range(DOSSIER_SLOTS):
            candidates = [t for t in all_types if remaining[t] > 0]
            if not candidates:
                break
            pick = max(candidates, key=lambda t: (remaining[t], t))
            batch.append(pick)
            remaining[pick] -= 1
        rows.append((tuple(batch), "parallel", False))

    single_counts: dict[str, int] = {}
    for t in all_types:
        if t in _chain_types():
            single_counts[t] = 0
        elif t in RETRY_TYPES:
            single_counts[t] = 10
        elif t == "IMEI":
            single_counts[t] = 7
        elif t in extra_dossier:
            single_counts[t] = 3
        else:
            single_counts[t] = 4
    behaviour_at = 0
    for t in sorted(all_types):
        for _ in range(single_counts[t]):
            behaviour = "retry_same_tool" if t in RETRY_TYPES else \
                SINGLE_BEHAVIOURS[behaviour_at % len(SINGLE_BEHAVIOURS)]
            rows.append(((t,), behaviour, t == "IMEI"))
            behaviour_at += 1
    return rows


def _label_cases(rows: list[tuple[tuple[str, ...], str, bool]]) -> list[tuple[tuple[str, ...], str, str, bool]]:
    """Greedily label each case with a truthful home industry, steering the
    industry shares toward INDUSTRY_CASES."""
    cur: Counter = Counter()
    labelled: list[tuple[tuple[str, ...], str, str, bool]] = []
    for types, behaviour, bare in rows:
        candidates = set()
        for t in types:
            candidates.update(_type_spec(t).industries)
        if not candidates:
            candidates = set(c.INDUSTRIES)
        industry = min(candidates, key=lambda i: (-(INDUSTRY_CASES[i] - cur[i]), cur[i], i))
        labelled.append((types, industry, behaviour, bare))
        cur[industry] += 1
    return labelled


def _build() -> tuple[PlanRow, ...]:
    rows = _label_cases(_build_rows())
    total = len(rows)
    if total != 499:
        raise ValueError(f"the plan holds {total} cases, expected 499 (the delivery "
                         f"vertical reader in build_full is the 500th)")
    grouped: dict[tuple[tuple[str, ...], str, str, bool], int] = {}
    for types, industry, behaviour, bare in rows:
        key = (types, industry, behaviour, bare)
        grouped[key] = grouped.get(key, 0) + 1
    return tuple(PlanRow(types, industry, behaviour, count, bare)
                 for (types, industry, behaviour, bare), count in grouped.items())


PLAN_V6: tuple[PlanRow, ...] = _build()


def plan_type_table() -> list[str]:
    counts: Counter = Counter()
    for row in PLAN_V6:
        for t in set(row.types):
            counts[t] += row.count
    lines = ["план по типам (полный корпус):"]
    for type_id in sorted(counts):
        cases = counts[type_id]
        mark = "OK" if cases >= 34 else "!"
        lines.append(f"  {mark} {type_id:<24} {cases:>3} случаев · {cases * 2:>3} элементов "
                     f"(пол 34 / 60)")
    return lines


def plan_industry_table() -> list[str]:
    counts: Counter = Counter()
    for row in PLAN_V6:
        counts[row.industry] += row.count
    lines = ["план по отраслям:"]
    for industry in c.INDUSTRIES:
        share = counts[industry] / 500
        want = sv.INDUSTRY_WEIGHTS[industry]
        heavy = industry in sv.HEAVY_INDUSTRIES
        lifted = sv._industry_lifted(industry, set(pii_types.NEW_ITEM_TYPES))
        note = " (тяжёлая)" if heavy else (" (поднята)" if lifted else "")
        lines.append(f"  {industry:<24} {counts[industry]:>3} ({share:.1%}, вес {want:.0%}){note}")
    return lines


def main() -> int:
    total = sum(row.count for row in PLAN_V6)
    print(f"plan_v6: {len(PLAN_V6)} строк, {total} случаев")
    for line in plan_type_table():
        print(line)
    for line in plan_industry_table():
        print(line)
    problems: list[str] = []
    if total != 499:
        problems.append(f"the plan sums to {total} cases, not 499 (the delivery "
                        f"vertical reader in build_full is the 500th)")
    for type_id in _all_types():
        cases = sum(row.count for row in PLAN_V6 if type_id in row.types)
        if cases < 34:
            problems.append(f"{type_id}: {cases} cases, floor 34")
    print("plan_v6: PASS" if not problems else "plan_v6: FAIL")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
