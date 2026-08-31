"""AgentPII-RU v3 — the three ground-truth checks `audit.py` does not run.

Not a second audit. `audit.py` covers spans, shapes and the corpus's own
attested vocabulary; this file holds three questions that instrument cannot
reach, each found by asking what a scorer would do with the answer rather than
what a regex would match.

  1. A CLAIMED VALUE REPEATED WHERE NOTHING CLAIMS IT. Not a threshold
     question and not a vocabulary one: the corpus itself says the string is
     personal data, in the same case, and the second occurrence is bare. A
     gateway that masks both is charged a false mask for being right. The
     vocabulary net misses these because it scans user text and these sit in
     tool results.

  2. ONE SURFACE FORM, TWO CANONICAL FORMS. Invisible inside a case and visible
     only across the corpus. Split three ways, because the three mean different
     things: differing only by letter case is one string graded two ways;
     differing by case AND content is a real ambiguity (Громов / Громова);
     differing entirely is expected, because a partial mention belongs to a
     different person in every conversation and the conversation resolves it.

  3. PERSONAL DATA IN AN ARGUMENT NOBODY JUDGES. `judged_args` is what the round
     trip compares. A real value passed in an argument outside it arrives
     unchecked, so a gateway could corrupt it for free — and `validate` checks
     the mirror rule (a judged argument must be derivable) but not this one.

Plus the machine-text half of the precision blind spot: shapes standing in TOOL
output that neither the gold nor a negative claims. Over-masking there cannot be
charged to anything, so half the precision measurement quietly does not happen
on the inbound leg — which is the leg the `result` family exists for.
"""

import argparse
import collections
import re
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.agentpii3 import build, schema
from bench.agentpii3.schema import Case

_DIGITS4 = re.compile(r"\d{4,}")


def _claimed(case: Case) -> dict[int, list[tuple[int, int]]]:
    spans: dict[int, list[tuple[int, int]]] = {}
    for item in case.pii:
        spans.setdefault(item.msg, []).append((item.start, item.end))
    for negative in case.negatives:
        spans.setdefault(negative.msg, []).append((negative.start, negative.end))
    return spans


def _covers(spans: Sequence[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < high and end > low for low, high in spans)


def _word_bounded(text: str, start: int, end: int) -> bool:
    """Whether the match sits at word edges on both sides.

    `str.find` is a SUBSTRING search and this check condemned four occurrences of
    «тому» — a real claimed NAME, the dative of «Тома» — sitting inside «поэтому»
    and «другому». A report that spends four of its fourteen findings on
    «поэтому» teaches its reader to skim it.
    """
    left = text[start - 1] if start else " "
    right = text[end] if end < len(text) else " "
    return not (left.isalpha() or right.isalpha())


def repeated_unclaimed(cases: Sequence[Case]) -> list[tuple[str, str, str, str]]:
    """Every occurrence of a claimed value that no span covers."""
    rows: list[tuple[str, str, str, str]] = []
    for case in cases:
        spans = _claimed(case)
        for item in case.pii:
            if len(item.value) < 4:
                continue
            for index, message in enumerate(case.messages):
                if message.role == "system":
                    continue
                text = schema.message_text(case, index)
                here = spans.get(index, [])
                position = text.find(item.value)
                while position != -1:
                    end = position + len(item.value)
                    if (not _covers(here, position, end)
                            and _word_bounded(text, position, end)):
                        window = text[max(0, position - 20):position + 40]
                        rows.append((case.id, message.role, item.value,
                                     " ".join(window.split())))
                    position = text.find(item.value, position + 1)
    return rows


def canonical_splits(cases: Sequence[Case]) -> dict[str, list[str]]:
    """One surface form with more than one canonical, split three ways."""
    forms: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for case in cases:
        for item in case.pii:
            forms[(item.type, item.value)].add(item.canonical)
    out: dict[str, list[str]] = collections.defaultdict(list)
    for (kind, value), canonical in sorted(forms.items()):
        if len(canonical) < 2:
            continue
        folded = {" ".join(form.casefold().replace(",", " ").split())
                  for form in canonical}
        if len(folded) == 1:
            bucket = "case_only"
        elif len(folded) < len(canonical):
            bucket = "case_and_content"
        else:
            bucket = "by_conversation"
        out[bucket].append(f"{kind} {value!r} -> {sorted(canonical)}")
    return dict(out)


def unjudged_arguments(cases: Sequence[Case]) -> list[str]:
    rows: list[str] = []
    for case in cases:
        values = {item.value for item in case.pii if item.duty == "required"}
        values |= {item.canonical for item in case.pii
                   if item.duty == "required"}
        values = {value for value in values if len(value) >= 4}
        for call in case.calls:
            for argument, passed in call.arguments.items():
                if argument in call.judged_args:
                    continue
                for value in values:
                    if value in passed:
                        rows.append(f"{case.id}: {call.name}.{argument} "
                                    f"carries {value!r}, unjudged")
    return rows


def tool_output_blind_spot(cases: Sequence[Case]) -> dict[str, int]:
    """Digit shapes in TOOL text that nothing claims, by literal."""
    counts: collections.Counter = collections.Counter()
    for case in cases:
        spans = _claimed(case)
        for index, message in enumerate(case.messages):
            if message.role != "tool":
                continue
            text = schema.message_text(case, index)
            here = spans.get(index, [])
            for match in _DIGITS4.finditer(text):
                if _covers(here, match.start(), match.end()):
                    continue
                literal = match.group()
                kind = "год" if literal in ("2024", "2025", "2026") else (
                    "customer_id" if f"C-{literal}" in text else
                    "сумма в рублях" if f"{literal} руб" in text else "прочее")
                counts[kind] += 1
    return dict(counts)


def render(cases: Sequence[Case]) -> str:
    repeats = repeated_unclaimed(cases)
    splits = canonical_splits(cases)
    unjudged = unjudged_arguments(cases)
    machine = tool_output_blind_spot(cases)

    lines: list[str] = []
    add = lines.append
    add("## Аудит A, продолжение — три расхождения эталона, которых "
        "не ищут ни `schema.validate`, ни `audit.py`")
    add("")
    add(f"Собрано на том же корпусе: {len(cases)} случаев, дайджест "
        f"`{schema.corpus_digest(cases)[:16]}`. Воспроизводится "
        f"`python3 -m bench.agentpii3.audit_crosscheck`.")
    add("")

    add(f"### 1. Заявленное значение, повторённое там, где его никто не "
        f"заявил — **{len(repeats)}**")
    add("")
    if repeats:
        by_role = collections.Counter(role for _, role, _, _ in repeats)
        add(f"По ролям: {dict(by_role)}. Это не порог и не словарь: корпус САМ "
            f"называет эту строку персональными данными, в том же случае, а "
            f"второе её вхождение стоит голым. Шлюз, замаскировавший оба, "
            f"получает попадание за первое и ЛОЖНУЮ МАСКУ за второе.")
        add("")
        add("| случай | роль | значение | контекст |")
        add("|---|---|---|---|")
        for case_id, role, value, window in repeats[:12]:
            add(f"| `{case_id}` | {role} | `{value}` | `{window}` |")
        add("")
        add("Класс закрыт у источника: `context._indirect_case` возвращал карточку "
        "клиента как `{\"passenger\": \"…\", \"last_address\": \"…\"}`, адрес "
        "заявлял, имя пассажира — нет, и десять случаев требовали замаскировать "
        "одну половину карточки, молча о второй. Теперь имя несёт свой спан с "
        "той же `identity`, что и упоминание в пользовательской реплике.")
    add("")

    add(f"### 2. Одна поверхностная форма, два канонических значения")
    add("")
    add("| класс | значений | что это значит |")
    add("|---|---|---|")
    add(f"| различие ТОЛЬКО в регистре букв | "
        f"{len(splits.get('case_only', []))} | скорер приводит регистр, так что "
        f"обе формы оцениваются ОДИНАКОВО — диагностика, не дефект |")
    add(f"| регистр И содержание | {len(splits.get('case_and_content', []))} | "
        f"настоящая неоднозначность рода/падежа (Громов / Громова) |")
    add(f"| разные значения | {len(splits.get('by_conversation', []))} | "
        f"ожидаемо: частичное упоминание принадлежит разным людям в разных "
        f"разговорах |")
    add("")
    for row in splits.get("case_only", [])[:10]:
        add(f"* {row}")
    add("")
    add("ПОПРАВКА К ПРОШЛОЙ РЕДАКЦИИ ЭТОГО ОТЧЁТА. Первый класс был назван "
        "здесь **дефектом**, и это было неверно: `schema.same_value` "
        "заканчивается на `.strip().casefold()`, поэтому «Гусева» и «гусева» "
        "сравниваются РАВНЫМИ и одна строка оценивается одним способом. Аудит "
        "предъявлял корпусу правило, которого у скорера нет, — и это ровно тот "
        "же класс ошибки, что и завышение: прибор, называющий дефектом то, что "
        "им не является, тратит внимание читателя и обесценивает соседнюю "
        "строку, которая настоящая.")
    add("")
    add("Что здесь ОСТАЁТСЯ верным и печатается ради этого: канонизация "
        "регистро-непоследовательна («гусева» в одном семействе, `Гусева` в "
        "другом), и день, когда кто-нибудь решит сравнивать точно — ради "
        "дефекта «имя уехало в CRM строчными», который приведение регистра "
        "прячет, — эти 55 значений станут дефектом в тот же час. Число "
        "печатается, чтобы решение принимали с ним, а не без него.")
    add("")

    add(f"### 3. ПД в аргументе вызова, который никто не судит — "
        f"**{len(unjudged)}**")
    add("")
    add("`judged_args` — это то, что сверяет круговой рейс. Настоящее "
        "значение, переданное в аргументе вне этого списка, приезжает "
        "непроверенным. `validate` проверяет зеркальное правило (судимый "
        "аргумент обязан быть выводим из сказанного) и это — нет.")
    if unjudged:
        add("")
        for row in unjudged[:10]:
            add(f"* {row}")
    add("")

    total = sum(machine.values())
    add(f"### 4. Слепое пятно точности на ВХОДЯЩЕМ плече — {total} вхождений")
    add("")
    add(f"Разбор по смыслу: {machine}. Годы — календарные даты в ответе "
        f"инструмента, `customer_id` — ключ записи в чужой системе, суммы — "
        f"итоги заказов. Ничто из этого не персональные данные, и ничто не "
        f"объявлено негативом, поэтому шлюз, замаскировавший `C-8909`, не "
        f"будет за это наказан. Пользовательское плечо `audit.py` разбирает "
        f"словарём; машинное плечо не разбирает никто, а семейство `result` — "
        f"четверть корпуса.")
    add("")

    # 5. The hand-annotated layer, checked against itself. Filler is expected to
    # carry stray names — it is real speech and the corpus says so. A VERBATIM
    # case is different: its gold IS the hand annotation, so an unlabelled value
    # inside one is the annotation being wrong about the utterance it chose.
    add("### 5. Ручная разметка против самой реплики")
    add("")
    misses: list[str] = []
    for case in cases:
        if case.provenance.kind != "verbatim":
            continue
        spans = _claimed(case)
        for index, message in enumerate(case.messages):
            if message.role != "user":
                continue
            text = schema.message_text(case, index)
            here = spans.get(index, [])
            blanked = list(text)
            for start, end in here:
                for position in range(max(start, 0), min(end, len(blanked))):
                    blanked[position] = " "
            tokens = "".join(blanked).lower().split()
            for position, token in enumerate(tokens):
                tail = tokens[position + 1:position + 4]
                if (token in schema.STREET_TYPE_WORDS
                        or token.endswith(("ова", "ева", "ина", "ского"))):
                    if any(word in schema.NUMERAL_WORDS for word in tail):
                        misses.append(
                            f"`{case.id}` ({case.provenance.selection}): "
                            f"размечено {[i.value for i in case.pii]}, "
                            f"не размечено «"
                            f"{' '.join(tokens[position:position + 4])}» — "
                            f"полная реплика: «{' '.join(text.split())}»")
    add(f"Наполнитель может нести чужое имя — это настоящая речь, и корпус это "
        f"признаёт. `verbatim`-случай — другое дело: его эталон И ЕСТЬ ручная "
        f"разметка, поэтому неразмеченное значение внутри него — это ошибка "
        f"разметки в реплике, которую разметчик выбрал сам. Найдено: "
        f"**{len(misses)}**.")
    add("")
    for row in misses[:6]:
        add(f"* {row}")
    add("")
    if misses:
        # The two classes this check produces are DIFFERENT and must not be
        # summed. A missed GOLD span is a leak the scorer will charge to a
        # gateway that was right; a missed NEGATIVE is over-masking nothing can
        # be charged for. The narrative that stood here named two case ids by
        # hand, and one of them («ctx-verb19», the second address in a two-address
        # annotation) has since been fixed at the source — the builder read
        # `spans[0]` and now claims every span the annotator wrote. A report that
        # names a fixed defect by id is worse than one that names none.
        add("Классы РАЗНЫЕ и не складываются: пропущенный ЭТАЛОН — это утечка, "
            "которую скорер предъявит правому шлюзу; пропущенный НЕГАТИВ — это "
            "над-маскирование, которое предъявить нечему. Оба выше названы "
            "полной репликой, чтобы читатель решил сам, а не поверил ярлыку.")
        add("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=build.SEED)
    parser.add_argument("--append", type=Path,
                        help="append the section to this report instead of "
                             "printing it")
    arguments = parser.parse_args()
    cases = build.build_corpus(arguments.seed)
    report = render(cases)
    if arguments.append:
        with arguments.append.open("a", encoding="utf-8") as handle:
            handle.write("\n\n" + report + "\n")
        print(f"дописано в {arguments.append}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
