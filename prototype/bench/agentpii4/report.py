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


# The order is the ladder itself: could the agent act at all, did it reach for
# the same tools, with the same keys, leaving the same state, carrying the same
# VALUES, spelled the same way. One number out of six is a choice of which
# half of the truth to print, and the report makes all six or none.
LEVELS: tuple[tuple[str, str], ...] = (
    ("action", "L0 действие"), ("tools", "L1 инструменты"), ("keys", "L2 ключи"),
    ("state", "L3 состояние"), ("values", "L3 ЗНАЧЕНИЯ"), ("verbatim", "L3 дословно"))

# The equivalence margin the product publishes. Owner's decision, 07.09: one
# margin for every level, so no level can be granted a looser promise than the
# others by a choice made after the numbers were seen.
DELTA = 0.03


def _level_flag(verdict: PairVerdict, level: str) -> bool | None:
    """True, False, or None when this pair had NOTHING to compare at that level."""
    if level not in verdict.levels.comparable:
        return None
    if level == "action":
        return verdict.levels.action
    if level == "tools":
        return verdict.levels.tools
    if level == "keys":
        return verdict.levels.keys
    if level == "state":
        return verdict.levels.state
    if level == "values":
        return verdict.levels.state_values
    return verdict.levels.state_verbatim


def comparable_triples(scored: Sequence[Scored], level: str) -> list[Scored]:
    """The triples on which this level says anything.

    BOTH pairs must be comparable, never one: the effect is a PAIRED
    difference, and a triple that contributes to one column and not the other
    would move the effect without any arm having done anything."""
    return [one for one in scored
            if _level_flag(one.ic, level) is not None and _level_flag(one.cc, level) is not None]


def case_effects(cases: dict[str, Case], scored: Sequence[Scored], level: str) -> list[stats.CaseEffect]:
    by_case: dict[str, list[Scored]] = defaultdict(list)
    for one in comparable_triples(scored, level):
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

    level_lines: list[str] = []
    verdicts: list[str] = []
    for level, label in LEVELS:
        rows = comparable_triples(scored, level)
        effects = case_effects(cases, scored, level)
        interval = stats.cluster_bootstrap(effects, reps=2000)
        verdict, tost_low, tost_high = stats.tost_equivalence(effects, DELTA, reps=2000)
        b = sum(1 for one in rows if not _level_flag(one.ic, level) and _level_flag(one.cc, level))
        c = sum(1 for one in rows if _level_flag(one.ic, level) and not _level_flag(one.cc, level))
        p_value = stats.mcnemar_exact(b, c)
        by_case: dict[str, list[int]] = defaultdict(list)
        by_value: dict[str, list[int]] = defaultdict(list)
        for one in rows:
            flag = int(bool(_level_flag(one.ic, level)))
            by_case[one.triple.case_id].append(flag)
            by_value[cases[one.triple.case_id].cluster].append(flag)
        icc_case = stats.icc_binary(by_case)
        icc_value = stats.icc_binary(by_value)
        sizes = [len(v) for v in by_value.values()]
        deff = stats.design_effect(sum(sizes) / len(sizes) if sizes else 1.0, icc_value)
        level_lines.append(
            f"   {label:16} {len(rows):5}/{n_triples:<5} {_pct(stats.agreement(effects, 'ic'), 1)} "
            f"{_pct(stats.agreement(effects, 'cc'), 1)} {100 * interval.point:+6.1f}pp "
            f"[{100 * interval.low:+5.1f}, {100 * interval.high:+5.1f}]  "
            f"{verdict:15} [{100 * tost_low:+5.1f}, {100 * tost_high:+5.1f}]  "
            f"{p_value:5.3f} ({b},{c})  {icc_case:5.2f} {icc_value:5.2f} {deff:4.2f}")
        verdicts.append(f"{label.split()[0]} {100 * interval.point:+.1f}pp "
                        f"{'=' if verdict == 'эквивалентно' else '≠'}")
    lines.append(f"ВЕРДИКТ ЭКВИВАЛЕНТНОСТИ при δ={100 * DELTA:.0f}pp — " + " · ".join(verdicts))

    # 0 — LEAKS: personal data in a message the gateway arm never substituted.
    # The three levels cannot see this: a value that reached the model in the
    # clear reaches the tool in the clear, and the two arms AGREE. It is the one
    # failure the product exists to prevent, and the first report had no line
    # for it (46 of 723 message values on the 03.09 re-run, found by hand).
    leaks: Counter[str] = Counter()
    seen_values = 0
    leaked_items: list[str] = []
    for one in scored:
        case = cases[one.triple.case_id]
        for item in case.pii:
            if item.where.kind != "message":
                continue
            seen_values += 1
            if item.id not in one.triple.I.substitutes:
                leaks[f"{item.type}/{case.register}"] += 1
                leaked_items.append(f"{one.triple.case_id}|{one.triple.repeat} {item.type} «{item.value[:48]}»")
    lines += ["", f"0. УТЕЧКИ В МОДЕЛЬ — значения из сообщений, для которых плечо шлюза НЕ показало подмену: "
                  f"{sum(leaks.values())} из {seen_values} ({_pct(sum(leaks.values()), seen_values).strip()})"]
    # ДВЕ СТРАТЫ, НИКОГДА ОДНИМ ЧИСЛОМ. Пулы корпуса лежат ВНУТРИ лизованных
    # словарей, поэтому общий процент описывает прежде всего то, насколько
    # корпус похож на словарь. Случаи со `selection == "rare"` берут имя и улицу
    # снаружи — по внешнему критерию, а не по «движок их не находит», — и
    # сложенные с остальными они прячут обе половины сразу.
    strata: dict[str, list[int]] = defaultdict(list)
    for one in scored:
        case = cases[one.triple.case_id]
        for item in case.pii:
            if item.where.kind != "message":
                continue
            strata[case.provenance.selection].append(int(item.id not in one.triple.I.substitutes))
    if len(strata) > 1:
        lines.append("   по страте: " + " · ".join(
            f"{'вне словарей' if name == 'rare' else 'в словарях'} {sum(rows)}/{len(rows)}"
            f" ({_pct(sum(rows), len(rows)).strip()})"
            for name, rows in sorted(strata.items())))
    if leaks:
        lines.append("   " + " · ".join(f"{key} {count}" for key, count in leaks.most_common()))
        lines += [f"   {row}" for row in leaked_items[:dump]]
    # THE LINE ABOVE COVERS 38% OF THE LABELLED VALUES. `where.kind == "message"`
    # is 2444 items against 3998 in the backend records, and a seed value
    # reaches the model too — through a tool RESULT, which `gateway` masks on
    # the same path. What cannot be said from here is which of them a tool
    # actually returned, so the second population measures COVERAGE and is
    # never added to the first: a record the agent did not ask for was never
    # shown to anybody.
    seed_seen = 0
    seed_masked = 0
    for one in scored:
        for item in cases[one.triple.case_id].pii:
            if item.where.kind != "seed":
                continue
            seed_seen += 1
            seed_masked += item.id in one.triple.I.substitutes
    lines.append(f"0б. ЗАПИСИ БЭКЕНДА — подмена показана для {seed_masked} из {seed_seen} значений "
                 f"({_pct(seed_masked, seed_seen).strip()}). ЭТО ПОКРЫТИЕ, НЕ УТЕЧКА: запись, "
                 f"которую агент не запросил, модели не показывали. Со строкой 0 не складывается.")

    # 0в — OVER-MASKING. The other half of the instrument: recall without
    # precision is bought by one line that masks everything, and until now v4
    # measured only recall. A negative is a value the corpus DECLARES must
    # survive — an order number, a track, a city used as a place — and the
    # engine covering it with a span is a false mask.
    negatives = 0
    false_masks: Counter[str] = Counter()
    examples: list[str] = []
    for one in scored:
        case = cases[one.triple.case_id]
        spans = one.triple.I.masked_spans
        for negative in case.negatives:
            negatives += 1
            covered = any(start < negative.end and negative.start < end
                          for start, end in spans.get(negative.msg, ()))
            if covered:
                false_masks[f"{negative.family}/{case.register}"] += 1
                if len(examples) < dump:
                    examples.append(f"{one.triple.case_id} «{negative.value[:40]}» — {negative.why}")
    if negatives:
        lines += ["", f"0в. ПЕРЕМАСКИРОВАНИЕ — значения, которые ОБЯЗАНЫ уцелеть, но движок их накрыл: "
                      f"{sum(false_masks.values())} из {negatives} "
                      f"({_pct(sum(false_masks.values()), negatives).strip()})"]
        if false_masks:
            lines.append("   " + " · ".join(f"{key} {count}" for key, count in false_masks.most_common()))
            lines += [f"   {row}" for row in examples]
    else:
        lines += ["", "0в. ПЕРЕМАСКИРОВАНИЕ — НЕ ИЗМЕРЯЕТСЯ: в корпусе нет ни одного негатива. "
                      "Полнота без точности покупается одной строкой «маскировать всё», так что "
                      "числа выше описывают половину прибора."]

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
              "   уровень         сравнимо   I≈C      C′≈C   эффект  95% ДИ            "
              f"TOST δ={100 * DELTA:.0f}pp  90% ДИ           McNemar p (b,c)  ICC(сл) ICC(зн) DEFF"]
    lines += level_lines
    state_rows = comparable_triples(scored, "state")
    state_effects = case_effects(cases, scored, "state")
    zero = sum(1 for one in state_rows if not _level_flag(one.ic, "state"))
    if zero == 0 and state_rows:
        lines.append(f"   0 расхождений I≈C на {len(state_rows)} сравнимых тройках сертифицирует согласие ≥ "
                     f"{100 * stats.zero_failure_floor(len(state_rows)):.2f}%, не 100%")
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
    notes = {"control_erred": "КОНТРОЛЬ ошибся — шлюз восстановил эталон корпуса",
             "derived": "движок не чинит — производная от подмены",
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

    # 8 — cuts. A CUT WITHOUT THE FLOOR IS NOT A NUMBER: a family whose model
    # is unstable on its own reads as gateway harm, and 89% next to a floor of
    # 89% is the same result as 100% next to 100%.
    lines += ["", "8. РАЗРЕЗЫ — I≈C рядом с полом C′≈C; печатается разность"]
    for level in ("state", "values"):
        rows = comparable_triples(scored, level)
        for label, key in (("регистр", lambda c: c.register), ("вид", lambda c: c.kind)):
            buckets: dict[str, list[tuple[int, int]]] = defaultdict(list)
            for one in rows:
                buckets[key(cases[one.triple.case_id])].append(
                    (int(bool(_level_flag(one.ic, level))), int(bool(_level_flag(one.cc, level)))))
            lines.append(f"   {level}/{label}: " + " · ".join(
                f"{name} {sum(i for i, _ in v)}/{len(v)} пол {sum(c for _, c in v)}/{len(v)} "
                f"({100 * (sum(i for i, _ in v) - sum(c for _, c in v)) / len(v):+.0f}pp)"
                for name, v in sorted(buckets.items())))

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
