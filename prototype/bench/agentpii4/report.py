"""Aggregation and the report. Counters in, sections out; no rates are stored.

Every section prints the two columns the design rests on — I against C and
C′ against C — because a class that appears equally in both is the model,
not the gateway. `derived`, `validated_refused` and `residual` are flagged in
the taxonomy table: the first two the engine cannot fix by construction, the
third is a product defect.
"""
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from bench.agentpii4 import stats
from bench.agentpii4.compare import PairVerdict, Triple, compare_triple
from bench.agentpii4.schema import Case
from bench.agentpii4.taxonomy import DIVERGENCE_KINDS, TRANSFORM_KINDS


@dataclass
class Scored:
    triple: Triple
    ic: PairVerdict
    cc: PairVerdict


def score_triples(cases: dict[str, Case], triples: Sequence[Triple]) -> list[Scored]:
    out: list[Scored] = []
    for triple in triples:
        ic, cc = compare_triple(cases[triple.case_id], triple)
        out.append(Scored(triple, ic, cc))
    return out


def _level_flag(verdict: PairVerdict, level: str) -> bool:
    if level == "tools":
        return verdict.levels.tools
    if level == "keys":
        return verdict.levels.keys
    if level == "state":
        return verdict.levels.state
    return verdict.levels.state_verbatim


def case_effects(cases: dict[str, Case], scored: Sequence[Scored], level: str) -> list[stats.CaseEffect]:
    by_case: dict[str, list[Scored]] = defaultdict(list)
    for one in scored:
        by_case[one.triple.case_id].append(one)
    effects: list[stats.CaseEffect] = []
    for case_id, rows in sorted(by_case.items()):
        effects.append(stats.CaseEffect(
            case_id=case_id, cluster=cases[case_id].cluster,
            ic=sum(1 for row in rows if _level_flag(row.ic, level)),
            cc=sum(1 for row in rows if _level_flag(row.cc, level)),
            n=len(rows)))
    return effects


def _pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:5.1f}%" if whole else "  n/a"


def render(cases: dict[str, Case], scored: Sequence[Scored], excluded: Sequence[str],
           header: str, dump: int = 8) -> list[str]:
    lines: list[str] = [header, ""]
    n_triples = len(scored)
    n_cases = len({one.triple.case_id for one in scored})
    lines.append(f"троек: {n_triples} · случаев: {n_cases} · исключено: {len(excluded)}")
    if not scored:
        lines.extend(excluded[:dump])
        return lines

    # 1 — provocation: what the CONTROL arm did to real values
    lines += ["", "1. ПРОВОКАЦИЯ — что модель делает с НАСТОЯЩИМИ значениями (плечо C против C′)"]
    transforms: Counter[str] = Counter()
    for one in scored:
        for field in one.cc.fields:
            transforms[field.transform] += 1
    total_t = sum(transforms.values()) or 1
    lines.append("   " + " · ".join(f"{kind} {transforms.get(kind, 0)} ({_pct(transforms.get(kind, 0), total_t).strip()})"
                                    for kind in TRANSFORM_KINDS if transforms.get(kind)))

    # 2 — noise floor and 3 — effect, per level
    lines += ["", "2–3. ШУМОВОЙ ПОЛ И ЭФФЕКТ ШЛЮЗА — по уровням, никогда одним числом",
              "   уровень          I≈C      C′≈C     эффект   95% ДИ (кластерный бутстрап)   McNemar p (b,c)  ICC(случай) ICC(значение) DEFF"]
    for level, label in (("tools", "L1 инструменты"), ("keys", "L2 ключи"),
                         ("state", "L3 состояние"), ("verbatim", "L3 дословно")):
        effects = case_effects(cases, scored, level)
        interval = stats.cluster_bootstrap(effects, reps=2000)
        b = sum(1 for one in scored if not _level_flag(one.ic, level) and _level_flag(one.cc, level))
        c = sum(1 for one in scored if _level_flag(one.ic, level) and not _level_flag(one.cc, level))
        p = stats.mcnemar_exact(b, c)
        by_case = defaultdict(list)
        by_value = defaultdict(list)
        for one in scored:
            flag = int(_level_flag(one.ic, level))
            by_case[one.triple.case_id].append(flag)
            by_value[cases[one.triple.case_id].cluster].append(flag)
        icc_case = stats.icc_binary(by_case)
        icc_value = stats.icc_binary(by_value)
        sizes = [len(v) for v in by_value.values()]
        deff = stats.design_effect(sum(sizes) / len(sizes) if sizes else 1.0, icc_value)
        lines.append(f"   {label:16} {_pct(stats.agreement(effects, 'ic'), 1)} {_pct(stats.agreement(effects, 'cc'), 1)} "
                     f"{100 * interval.point:+6.1f}pp [{100 * interval.low:+5.1f}, {100 * interval.high:+5.1f}]"
                     f"           {p:5.3f} ({b},{c})   {icc_case:5.2f}       {icc_value:5.2f}      {deff:4.2f}")
    state_effects = case_effects(cases, scored, "state")
    zero = sum(1 for one in scored if not _level_flag(one.ic, "state"))
    if zero == 0:
        lines.append(f"   0 расхождений I≈C на {n_triples} тройках сертифицирует согласие ≥ "
                     f"{100 * stats.zero_failure_floor(n_triples):.2f}%, не 100%")
    icc_v = stats.icc_binary({cases[one.triple.case_id].cluster: [] for one in scored})  # placeholder keeps shape
    del icc_v
    agree_rate = stats.agreement(state_effects, "ic")
    lines.append(f"   для ±2pp на L3 при согласии {100 * agree_rate:.0f}% нужно n ≈ "
                 f"{stats.n_for_halfwidth(min(max(agree_rate, 0.5), 0.99), 0.02)} случаев (iid)")

    # 4 — taxonomy, two columns
    lines += ["", "4. ТАКСОНОМИЯ ПО ПОЛЯМ — I−C рядом с C′−C; разница и есть шлюз",
              "   класс               I−C   C′−C   разн   примечание"]
    ic_kinds: Counter[str] = Counter()
    cc_kinds: Counter[str] = Counter()
    for one in scored:
        for field in one.ic.fields:
            ic_kinds[field.kind] += 1
        for field in one.cc.fields:
            cc_kinds[field.kind] += 1
    notes = {"derived": "движок не чинит — производная от подмены",
             "validated_refused": "движок не чинит — фейк отвергнут валидацией",
             "residual": "ДЕФЕКТ ПРОДУКТА — подмена дошла до инструмента",
             "other_person": "ДЕФЕКТ ПРОДУКТА — чужой человек"}
    for kind in DIVERGENCE_KINDS:
        if ic_kinds.get(kind) or cc_kinds.get(kind):
            lines.append(f"   {kind:18} {ic_kinds.get(kind, 0):5} {cc_kinds.get(kind, 0):6} "
                         f"{ic_kinds.get(kind, 0) - cc_kinds.get(kind, 0):+6}   {notes.get(kind, '')}")
    by_type: dict[str, Counter[str]] = defaultdict(Counter)
    for one in scored:
        for field in one.ic.fields:
            by_type[field.pii_type or "—"][field.kind] += 1
    lines.append("   по типам (I−C): " + " · ".join(
        f"{kind}: agree {counter.get('agree', 0)}/{sum(counter.values())}"
        for kind, counter in sorted(by_type.items())))

    # 5 — derived
    lines += ["", "5. ПРОИЗВОДНЫЕ ПОЛЯ (I−C)"]
    derived: Counter[str] = Counter()
    for one in scored:
        for field in one.ic.fields:
            if field.kind == "derived" or field.sub in ("derived_from_real", "misderived"):
                derived[f"{field.path}:{field.kind}/{field.sub or '-'}"] += 1
    lines.extend(f"   {key} {count}" for key, count in derived.most_common(12)) if derived else lines.append("   —")

    # 6 — validation
    lines += ["", "6. ВАЛИДАЦИЯ — семейство validate"]
    val = [one for one in scored if cases[one.triple.case_id].kind == "validate"]
    if val:
        no_call_i = sum(1 for one in val if one.ic.levels.tools_sub == "no_call")
        no_call_c = sum(1 for one in val if one.cc.levels.tools_sub == "no_call")
        refused_i = sum(1 for one in val for f in one.ic.fields if f.kind == "validated_refused")
        lines.append(f"   троек {len(val)} · агент не вызвал (I−C) {no_call_i} · (C′−C) {no_call_c} · "
                     f"мок отверг в I {refused_i}")
    else:
        lines.append("   —")

    # 7 — plain values
    lines += ["", "7. ПРОСТЫЕ ЗНАЧЕНИЯ (не ПД, обязаны уцелеть) — I−C / C′−C"]
    plain_i: Counter[str] = Counter()
    plain_c: Counter[str] = Counter()
    for one in scored:
        for _path, status in one.ic.plain:
            plain_i[status] += 1
        for _path, status in one.cc.plain:
            plain_c[status] += 1
    lines.append("   " + " · ".join(f"{status}: {plain_i.get(status, 0)} / {plain_c.get(status, 0)}"
                                    for status in ("intact", "changed", "absent")))

    # 8 — cuts
    lines += ["", "8. РАЗРЕЗЫ — согласие I≈C на L3 по регистру и по виду"]
    for label, key in (("регистр", lambda c: c.register), ("вид", lambda c: c.kind)):
        buckets: dict[str, list[int]] = defaultdict(list)
        for one in scored:
            buckets[key(cases[one.triple.case_id])].append(int(one.ic.levels.state))
        lines.append(f"   {label}: " + " · ".join(
            f"{name} {sum(v)}/{len(v)}" for name, v in sorted(buckets.items())))

    # 9 — excluded, 10 — examples
    if excluded:
        lines += ["", f"9. ИСКЛЮЧЕНО ({len(excluded)})"]
        lines.extend(f"   {one}" for one in excluded[:dump])
    lines += ["", f"10. ПРИМЕРЫ РАСХОЖДЕНИЙ (I−C, до {dump})"]
    shown = 0
    for one in scored:
        for field in one.ic.fields:
            if field.kind != "agree" and shown < dump:
                shown += 1
                lines.append(f"   {one.triple.case_id}|{one.triple.repeat} {field.tool}.{field.path} "
                             f"[{field.kind}/{field.sub}] C={field.ref!r} I={field.obs!r} ({field.transform})")
    if not shown:
        lines.append("   нет")
    return lines
