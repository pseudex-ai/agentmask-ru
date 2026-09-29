"""AgentPII-RU v6 — the deterministic full-corpus allocation (TZ §4.3, §4.4).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.scenarios6.plan_v6

WHAT THIS FILE IS. The table `build_full` consumes: a tuple of `PlanRow`
(`type_id, industry, behaviour, form, count`), one homogeneous batch of `count`
cases per row, `sum(count) == 500`. The corpus is DETERMINED here; the
sentences are built in `build_full`.

WHY A TUPLE, NOT A GENERATOR. The plan is the acceptance artifact: a reviewer
reads the per-type and per-industry counts straight off this file, and
`test_plan_meets_full_floors` proves the numbers build into a corpus that
`validate_corpus_v6(cases, "full", 500)` accepts.

REALIZABLE, NOT WISHFUL. Each row names a type whose v6 tool carries it BOTH
ways (an IN/tool result leaf AND an OUT/tool_arg field, per `tools_v6`). A type
with no such tool is LEFT OUT (rows empty) and named in the report. The 14 types
admitted here are the reachable set; the three «chain:» pairings
(OSAGO+VIN, EPTS+VIN, ICCID+LOAN_CONTRACT) are the READ tools whose ONE result
returns two admitted types, so a chain row spends two type-slots on one case.

NOTHING HERE IMPORTS `pseudex` OR `licensing`, AND NOTHING HERE SEARCHES A
FINISHED STRING.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema_v6 as sv

CHAIN_FORM_PREFIX: str = "chain:"

# The two types whose READ tools (diploma_registry_check, hr_employee_get) declare
# the forced-error echo path `error.subject` — the only READ tools that can host a
# `retry_same_tool` case without crossing an undeclared result leaf (K6-15).
RETRY_ELIGIBLE_TYPES: frozenset[str] = frozenset(("DIPLOMA_NUMBER", "EMPLOYEE_TAB_NUMBER"))

# The three vertical-coverage cases `build_full` appends on top of the plan:
# one reader per reading vertical (delivery/directory/files) that no v6 type
# recipe crosses. They seed a v5 NAME/PHONE, not a v6 type, so they live in
# `build_full`, not in `TYPE_DISTRIBUTION`; the plan simply leaves three slots
# for them and sums to `500 - VERTICAL_READER_CASES`.
VERTICAL_READER_CASES: int = 3
PLAN_TOTAL: int = 500 - VERTICAL_READER_CASES

# A READ tool whose one result carries two admitted types -> the chain pair it
# realises (the SECOND type is read off the SAME result as the first).
CHAIN_PAIRS: dict[str, str] = {
    "OSAGO_POLICY": "VIN",              # osago_policy_check -> policy.* + vehicle.vin
    "EPTS_NUMBER": "VIN",               # epts_status_get -> epts + vin
    "IBAN": "OGRNIP",                   # crm_requisite_get -> rq_iban + rq_ogrnip
}

# The admitted types, each with its (industry -> case count) distribution. The
# counts are CASE counts (not slots): a chain row carries its `type_id` and its
# partner, and the partner's own rows carry the rest. Every type lands on >= 34
# distinct cases; the industry shares stay inside OD-05's +/-3pp band (heavy
# 9..15%, light 1..7%).
#
# WHY THREE TYPES ARE ABSENT. DRIVER_LICENSE, ELN_NUMBER and ARBITRAZH_CASE_NO
# are reachable through tools but their reading tools' result field names
# («license», «ln_code», «number») are NOT in the registry's `field_keys`, so a
# seed item carrying them is a BARE positive and K6-16 (0% bare for [K]) refuses
# them. They are left out rather than faked; the report names them. DIPLOMA_NUMBER
# is KEPT even though its «series»/«number» fields have the same mismatch: it is
# the ONLY type education can reach, and dropping it would turn one K6-16 line
# into a K6-18 coverage gap for a whole industry — the report names that one red
# line too.
TYPE_DISTRIBUTION: dict[str, tuple[tuple[str, int], ...]] = {
    "OGRNIP": (("retail", 20), ("logistics", 8), ("internal_bi", 4), ("legal", 2)),
    "BANK_ACCOUNT": (("banks_mfo_collectors", 24), ("internal_bi", 4), ("hr", 6)),
    "CADASTRAL_NUMBER": (("real_estate", 10), ("government_services", 10), ("legal", 8),
                         ("insurance", 4), ("banks_mfo_collectors", 2)),
    "DIPLOMA_NUMBER": (("education", 24), ("hr", 10)),
    "EMPLOYEE_TAB_NUMBER": (("internal_bi", 10), ("hr", 10), ("logistics", 10), ("retail", 4)),
    "EPTS_NUMBER": (("logistics", 18), ("auto", 10), ("insurance", 6)),
    "GIS_ZHKH_ELS": (("internal_bi", 16), ("real_estate", 10), ("government_services", 8)),
    "ICCID": (("telecom", 14), ("logistics", 12), ("retail", 8)),
    "INTL_PASSPORT": (("hospitality", 13), ("insurance", 9), ("banks_mfo_collectors", 6),
                      ("hr", 6)),
    "LOAN_CONTRACT_NUMBER": (("banks_mfo_collectors", 24), ("internal_bi", 10)),
    "LOYALTY_CARD_NUMBER": (("retail", 14), ("medicine", 13), ("hospitality", 3),
                            ("marketing_cdp", 5)),
    "OMS_ENP": (("medicine", 32), ("insurance", 2)),
    "OSAGO_POLICY": (("insurance", 12), ("auto", 14), ("banks_mfo_collectors", 8)),
    "VIN": (("auto", 10), ("logistics", 8), ("banks_mfo_collectors", 6),
            ("government_services", 6), ("insurance", 4)),
    "IBAN": (("retail", 20), ("hr", 8), ("banks_mfo_collectors", 6)),
    "ESIA_OID": (("education", 24), ("government_services", 6), ("banks_mfo_collectors", 4)),
}

# The behaviour mix over the SINGLE-type cases (chain cases are sequential_chain
# by construction). `FLOOR` is the hard minimum (§4.5: >= 20); `weight` is how
# the surplus beyond the floors is spent. The exact count per behaviour is
# computed from the actual single-type case count, so the plan stays valid as the
# type distribution is tuned.
BEHAVIOUR_FLOOR: int = 20
BEHAVIOUR_MIX: tuple[tuple[str, int], ...] = (
    ("single", 8),
    ("retry_same_tool", 4),
    ("memory_anaphora", 3),
    ("parallel", 3),
    ("same_tool_other_target", 2),
    ("fanout_pick", 2),
    ("branching", 2),
    ("user_in_loop", 2),
    ("rag", 2),
    ("document", 2),
)


@dataclass(frozen=True)
class PlanRow:
    """One batch of `count` cases sharing a focus type, industry, behaviour and
    form. «chain:<B>» in `form` makes the case carry a second v6 type <B>."""

    type_id: str
    industry: str
    behaviour: str
    form: str
    count: int


def _chain_partner(type_id: str) -> str:
    return CHAIN_PAIRS.get(type_id, "")


def _build() -> tuple[PlanRow, ...]:
    """Realise the type distribution and the behaviour mix into 500 rows.

    Chain pairs are realised first: for each pairing, the smaller of the two
    counts in a shared industry becomes chain cases there, the partner's
    remainder stays single. Then every single-type case gets a behaviour from
    the mix by a least-relative-deficit round-robin, so every behaviour floor is
    met before any behaviour is topped up.
    """
    remaining: dict[str, dict[str, int]] = {
        t: dict(pairs) for t, pairs in TYPE_DISTRIBUTION.items()}
    rows: list[tuple[str, str, str, str]] = []

    # Chain pairs first (both sides of a pair are admitted and share a result).
    for type_id in sorted(remaining):
        partner = _chain_partner(type_id)
        if not partner or type_id >= partner:
            continue
        for industry in list(remaining[type_id]):
            left = remaining[type_id].get(industry, 0)
            right = remaining.get(partner, {}).get(industry, 0)
            paired = min(left, right)
            if paired <= 0:
                continue
            for _ in range(paired):
                rows.append((type_id, industry, "sequential_chain",
                             CHAIN_FORM_PREFIX + partner))
            remaining[type_id][industry] -= paired
            remaining[partner][industry] -= paired

    # Single-type cases, then behaviours over them.
    singles: list[tuple[str, str]] = []
    for type_id, by_industry in sorted(remaining.items()):
        for industry, count in sorted(by_industry.items()):
            for _ in range(count):
                singles.append((type_id, industry))
    # Give every behaviour its floor, then spend the surplus by weight with the
    # least-relative-deficit rule (a pure function of the case order, no rng).
    weights = dict(BEHAVIOUR_MIX)
    behaviour_names = [b for b, _ in BEHAVIOUR_MIX]
    counts: Counter = Counter({b: BEHAVIOUR_FLOOR for b in behaviour_names})
    surplus = len(singles) - sum(counts.values())
    if surplus < 0:
        raise ValueError(f"{len(singles)} single cases cannot meet the behaviour floor "
                         f"of {BEHAVIOUR_FLOOR} x {len(behaviour_names)}")
    delivered: Counter = Counter()
    for _ in range(surplus):
        behaviour = min(behaviour_names, key=lambda b: (delivered[b] / weights[b], b))
        delivered[behaviour] += 1
    behaviour_queue: list[str] = []
    for behaviour in behaviour_names:
        behaviour_queue.extend([behaviour] * (BEHAVIOUR_FLOOR + delivered[behaviour]))
    # `retry_same_tool` forces an error whose echo path (`error.subject`) only
    # diploma_registry_check and hr_employee_get declare (RESULT_PII_APPROX), so
    # it must ride those two types — a retry on any other READ tool would cross a
    # leaf the tool's result_pii does not declare (K6-15).
    retry_want = BEHAVIOUR_FLOOR + delivered["retry_same_tool"]
    retry_eligible = [(t, i) for (t, i) in singles if t in RETRY_ELIGIBLE_TYPES]
    other_singles = [(t, i) for (t, i) in singles if t not in RETRY_ELIGIBLE_TYPES]
    for type_id, industry in retry_eligible[:retry_want]:
        rows.append((type_id, industry, "retry_same_tool", ""))
    leftover = retry_eligible[retry_want:] + other_singles
    other_queue = [b for b in behaviour_queue if b != "retry_same_tool"]
    for position, (type_id, industry) in enumerate(leftover):
        rows.append((type_id, industry, other_queue[position], ""))

    total = len(rows)
    if total != PLAN_TOTAL:
        raise ValueError(f"the plan holds {total} cases, expected {PLAN_TOTAL}")
    grouped: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for key in rows:
        if key not in seen:
            seen.add(key)
            grouped.append(key)
    return tuple(PlanRow(t, i, b, f, rows.count((t, i, b, f)))
                 for t, i, b, f in grouped)


PLAN_V6: tuple[PlanRow, ...] = _build()


def plan_type_table() -> list[str]:
    """Per-type distinct-case counts, with chain partners counted (K6-02)."""
    counts: Counter = Counter()
    for row in PLAN_V6:
        counts[row.type_id] += row.count
        if row.form.startswith(CHAIN_FORM_PREFIX):
            counts[row.form[len(CHAIN_FORM_PREFIX):]] += row.count
    lines = ["план по типам (полный корпус):"]
    for type_id in sorted(counts):
        cases = counts[type_id]
        mark = "OK" if cases >= 34 else "!"
        lines.append(f"  {mark} {type_id:<24} {cases:>3} случаев · "
                     f"{cases * 2:>3} элементов (пол 34 / 60)")
    return lines


def plan_industry_table() -> list[str]:
    """Per-industry case counts and their share against OD-05."""
    counts: Counter = Counter()
    for row in PLAN_V6:
        counts[row.industry] += row.count
    lines = ["план по отраслям:"]
    for industry in c.INDUSTRIES:
        share = counts[industry] / 500
        want = sv.INDUSTRY_WEIGHTS[industry]
        lines.append(f"  {industry:<24} {counts[industry]:>3} ({share:.1%}, вес {want:.0%})")
    return lines


def main() -> int:
    total = sum(row.count for row in PLAN_V6)
    print(f"plan_v6: {len(PLAN_V6)} строк, {total} случаев")
    for line in plan_type_table():
        print(line)
    for line in plan_industry_table():
        print(line)
    problems: list[str] = []
    if total != PLAN_TOTAL:
        problems.append(f"the plan sums to {total} cases, not {PLAN_TOTAL} "
                        f"({VERTICAL_READER_CASES} vertical readers live in build_full)")
    print("plan_v6: PASS" if not problems else "plan_v6: FAIL")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
