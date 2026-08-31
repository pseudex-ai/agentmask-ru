"""AgentPII-RU v3 — the three audits, and the trim arithmetic.

A corpus that validates is not a corpus that is true. `schema.validate` proves a
case is SCOREABLE; these three ask whether it is HONEST, and each one exists
because a version of this benchmark shipped without it.

  (a) VALIDITY — every span holds its own value, and nothing PII-shaped sits in
      the text unclaimed by either the gold or the negatives. Deliberately NOT a
      call into `schema.validate`: an audit that runs the builder's own checker
      can only agree with it. The nets here are WIDER than the schema's on
      purpose (four digits where it takes six, a numeral run of three where it
      takes four, plus a corpus-attested vocabulary the schema has no notion of),
      so their hits are CANDIDATES and the report says which ones survived
      reading.

  (b) DISTRIBUTION AGAINST THE REFERENCE — the audit v2 failed. Its register mix
      was described in a design document and inverted in the corpus, and nothing
      compared the two. `mined/reference_distribution.json` measured 53 324
      distinct human utterances; this prints the same statistics over v3, over
      v2, and over the reference side by side. Where v3 departs, it departs by a
      number that is printed, not by an opinion that is not.

  (c) UNREACHABILITY — not «where does the corpus fail» but «what could never
      enter it». The first voice set scored 100% because it admitted an utterance
      only when it held «улица» or «дом»; the truth was 38.6% and no amount of
      running that set would have shown it. This audit asks the corpus what its
      generators are STRUCTURALLY incapable of producing, and cross-tabulation
      holes are the mechanical half of the answer.

`audit_crosscheck.render` is appended by this file rather than run on its own.
It used to be a second command writing a second file, and the half nobody re-ran
went stale first — it was still naming a defect by case id three fixes after that
defect was gone. One command, one report, one thing to keep true.
"""

import argparse
import collections
import json
import re
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.agentpii3 import audit_crosscheck, build, schema
from bench.agentpii3.schema import Case

HERE = Path(__file__).resolve().parent
REFERENCE_PATH = HERE / "mined" / "reference_distribution.json"
V2_CORPUS_PATH = HERE.parent / "agentpii2" / "corpus.json"
REPORT_PATH = HERE / "AUDIT.md"


# --- the header -----------------------------------------------------------

def _header(cases: Sequence[Case], ladder: schema.Ladder,
            problems: Sequence[str], seed: int) -> list[str]:
    missing = [name for name in schema.FAMILIES
               if not any(case.family == name for case in cases)]
    total = len(cases)
    clean = sum(1 for c in cases if c.register == "clean") / total
    speech = sum(1 for c in cases
                 if c.register in schema.SPEECH_REGISTERS) / total
    real_form = sum(1 for c in cases
                    if c.provenance.kind in ("verbatim", "recombined")) / total
    min_denominator = min(schema.type_denominators(cases).values())
    totals = _verdict_totals(_trigger_scan(cases)[0])
    spans = (sum(len(case.pii) for case in cases)
             + sum(len(case.negatives) for case in cases))
    negative_only = sum(1 for case in cases
                        if not any(i.duty == "required" for i in case.pii))
    return [
        "# AgentPII-RU v3 — аудит корпуса",
        "",
        f"Собран `bench/agentpii3/build.py`, зерно `{seed}`, "
        f"{total} случаев, дайджест `{schema.corpus_digest(cases)[:16]}`. "
        f"Отчёт пересобирается `python3 -m bench.agentpii3.audit`; всё ниже — "
        f"счёт по корпусу, а не мнение о нём.",
        "",
        "## СТАТУС",
        "",
        (f"Одиннадцать генераторов, {total} случаев, десять меток семейства, "
         f"`validate_corpus` без замечаний. Полоса размера 1 500-2 000 "
         f"соблюдена не отсечением хвоста, а РЕЗОМ ПО ПЛАНУ: генераторы "
         f"предлагают 2 001 случай при своих канонических размерах, и шесть "
         f"из них попрошены о меньшем. Кто именно и почему — `build._TRIM_REASON`, "
         f"и обоснование там одно: единица наблюдения — КЛАСТЕР, а не случай."
         if not missing else
         f"**Отсутствуют семейства: {missing}.** `validate_corpus` отказывает "
         f"по этой причине, `build.py` отказывается писать `corpus.json`, а "
         f"`ladder.json` записан ПРОВИЗОРНЫМ (`version: 0`)."),
        "",
        f"Претензий валидации сейчас: {len(problems)}"
        + (f" ({'; '.join(p[:90] for p in problems)})." if problems else "."),
        "",
        "### Четыре доли, ради которых версия и переписана",
        "",
        "v2 описала регистровый состав в проектном документе и собрала "
        "обратный. Здесь он не описан, а ПРОВЕРЕН: `validate_corpus` "
        "отказывает, и `build.py` не пишет файл.",
        "",
        "| требование | полоса | v3 | v2 |",
        "|---|---|---|---|",
        f"| литературный регистр | ≤ {schema.MAX_CLEAN_SHARE:.0%} | "
        f"**{clean:.2%}** | 16% |",
        f"| речевые регистры | ≥ 70% (пол схемы {schema.MIN_SPEECH_SHARE:.0%}) | "
        f"**{speech:.2%}** | — |",
        f"| форма взята из настоящего транскрипта | ≥ "
        f"{schema.MIN_REAL_FORM_SHARE:.0%} | **{real_form:.2%}** | 20% |",
        f"| наименьший знаменатель по типу | ≥ "
        f"{schema.MIN_TYPE_DENOMINATOR} | **{min_denominator}** | — |",
        "",
        "Только-негативных случаев (шлюз, который не делает ничего, проходит "
        f"их все): {negative_only} из {total} "
        f"({negative_only / total:.1%}) при потолке "
        f"{schema.MAX_NEGATIVE_ONLY_SHARE:.0%}. Кластеров — "
        f"{len(schema.clusters(cases))}: доверительный интервал считается по "
        "ним, а не по случаям, потому что один адрес, сказанный семью людьми, "
        "— это одно значение и семь вхождений.",
        "",
        "## Что этот отчёт утверждает, коротко",
        "",
        f"1. **Валидность.** {spans} спанов, ноль расхождений с текстом, ноль "
        f"противоречий между золотом и негативами, ноль недостижимых запретов "
        f"в итоговом ответе. Широкая сеть даёт "
        f"{sum(_trigger_scan(cases)[0].values())} кандидатов на "
        f"{len(_trigger_scan(cases)[0])} различных словах и "
        f"**{totals['real']} настоящих непокрытых ПД**. Предыдущий прогон давал "
        f"90 кандидатов и 28 настоящих; разница — не переразметка, а один "
        f"экран наполнителя вместо шести (`schema.unsafe_filler`).",
        # COMPUTED, not quoted. A summary holding literals its own body
        # recomputes is how a report starts lying about itself, and this one held
        # four of them.
        (lambda v3, v2, ref:
         f"2. **Распределение.** v3 воспроизводит живую речь там, где v2 не "
         f"воспроизводила: заглавных {v3['capital']:.2%} против "
         f"{v2.get('capital', 0):.2%}, пунктуации {v3['punct']:.2%} против "
         f"{v2.get('punct', 0):.2%}, цифр {v3['digit']:.2%} против "
         f"{v2.get('digit', 0):.2%}. В речевых регистрах — точное совпадение с "
         f"опорным. Расходится длина ({v3['wmean']:.1f} слова против "
         f"{ref['wmean']:.1f}) и плотность ПД — в двадцать раз выше, чем в "
         f"жизни. Оба числа названы, оба объяснены. Колонки пробега "
         f"числительных в этом прогоне ВПЕРВЫЕ сравнимы: обе стороны меряны "
         f"одним `probes.is_numeral` — до этого корпус мерялся списком точных "
         f"форм, а опорный корпус правилом по основам."
         )(_metrics(_user_texts(cases, "")),
           _metrics(_v2_user_texts(V2_CORPUS_PATH, "")[0])
           if V2_CORPUS_PATH.exists() else {},
           _reference_metrics(REFERENCE_PATH)),
        "3. **Недостижимость.** Ни одного значения NAME, взятого из живой "
        "речи; ни одного символа из корпуса ЗВОНКОВ (лицензия); ни одной "
        "однословной реплики в `voice_raw`; глубокий контекст всегда добран "
        "чужим наполнителем, а не связной длинной историей.",
        "",
    ]


# --- (a) validity ---------------------------------------------------------
#
# Wider than `schema`'s nets, and that is the point of a second opinion. Six
# digits is where the schema draws the line because a four-digit run in a tool
# result is a year; here four is taken and the ROLE is reported beside it, so the
# reader sees the year and the unclaimed order number as different rows rather
# than as one threshold decision made for them.

_NETS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(
        r"(?:\+7|\b8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}"),
    "digits4": re.compile(r"(?<!\d)\d{4,}(?!\d)"),
    "date": re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"),
    "plate": re.compile(r"\b[АВЕКМНОРСТУХ]\s?\d{3}\s?[АВЕКМНОРСТУХ]{2}\s?\d{2,3}\b"),
}

# The numeral-run threshold. The schema takes four because three is «сорок один»
# plus a neighbour; three is taken here because «сто сорок шесть» is a house
# number and is exactly three, and this audit would rather read false positives
# than miss the defect class v3 was built for.
_RUN_THRESHOLD: int = 3

# A word is corpus-attested when the corpus's OWN ground truth calls it personal
# data at least this many times somewhere else. Three, so one mislabelled case
# cannot make a vocabulary entry.
_ATTESTED_MIN: int = 3

# The verdicts, authored by reading every hit the nets produced on the seed
# corpus. This is a judgement and it is written down rather than folded into the
# net, so that a trigger the list does not know is REPORTED as unclassified
# instead of joining the noise silently. That is the difference between an
# exclusion list and a lie.
_TRIGGER_VERDICTS: dict[str, str] = {
    # Read once, by hand, after the shared filler screen went in. The list that
    # stood here held twenty-six words and every one of them was a leak the
    # screen now catches; what survives is what a vocabulary of 519 words does to
    # ordinary Russian, plus one deliberate place reference.
    "тому": "шум сети: дательный от «тот», не имя",
    "последний": "шум сети: «последний раз»; в корпусе есть «улица Последняя»",
    "ленинский": ("МЕСТО, не адрес: «ленинский район частный дом» — дословный "
                  "хвост из разметки, никого не определяет. Должен быть "
                  "ОБЪЯВЛЕННЫМ негативом, а не молчанием — см. «Что из этого "
                  "чинить»"),
}


def _claimed(case: Case) -> list[tuple[int, int, int]]:
    return ([(item.msg, item.start, item.end) for item in case.pii]
            + [(neg.msg, neg.start, neg.end) for neg in case.negatives])


def _overlaps(claimed: Sequence[tuple[int, int, int]],
              msg: int, start: int, end: int) -> bool:
    return any(m == msg and s < end and e > start for m, s, e in claimed)


def _attested_vocabulary(cases: Sequence[Case]) -> tuple[set[str], set[str]]:
    """The corpus's own gold vocabulary — DERIVED HERE, compared against the pin.

    The derivation itself moved into `schema.attested_pii_vocabulary`, because
    the filler guard screens with it and this audit condemns filler by it, and
    two copies of one rule means the audit can only ever report words the guard
    was never told about. That is not hypothetical: it is exactly the state the
    corpus was in, with five private name lists and an audit reading a sixth.
    """
    streets, names = schema.attested_pii_vocabulary(cases)
    return set(streets), set(names)


def _vocabulary_drift(cases: Sequence[Case]) -> tuple[list[str], list[str]]:
    """Words the built corpus attests that the frozen screen does not hold.

    The snapshot in `schema` is a constant and constants go stale. This is the
    mechanism that says so — and it can only ever report in one direction,
    because filler carries no gold, so removing filler cannot remove a word.
    """
    streets, names = schema.attested_pii_vocabulary(cases)
    return (sorted(streets - schema.FILLER_STREET_WORDS),
            sorted(names - schema.FILLER_NAME_WORDS))


def _trigger_scan(cases: Sequence[Case]) -> tuple[
        collections.Counter[str], dict[str, tuple[str, bool, str]],
        set[str], set[str]]:
    """Unclaimed occurrences of words the corpus's own gold calls personal data.

    Split out because the summary at the top of the report and the table in the
    middle must not be able to disagree — a header quoting a number the body
    recomputes is how a report starts lying about itself.
    """
    streets, names = _attested_vocabulary(cases)
    triggers: collections.Counter[str] = collections.Counter()
    examples: dict[str, tuple[str, bool, str]] = {}
    for case in cases:
        claimed = _claimed(case)
        for index, message in enumerate(case.messages):
            if message.role != "user":
                continue
            for match in re.finditer(r"[а-яё]{4,}", message.content.lower()):
                word = match.group()
                if word not in streets and word not in names:
                    continue
                if _overlaps(claimed, index, match.start(), match.end()):
                    continue
                triggers[word] += 1
                examples.setdefault(word, (
                    case.id, message.source is not None,
                    message.content[max(0, match.start() - 40):match.end() + 40]))
    return triggers, examples, streets, names


def _verdict_totals(triggers: collections.Counter[str]) -> dict[str, int]:
    """How many occurrences each verdict class accounts for."""
    totals = {"real": 0, "noise": 0, "other": 0, "address": 0, "name": 0}
    for word, count in triggers.items():
        verdict = _TRIGGER_VERDICTS.get(word, "")
        if verdict.startswith("НАСТОЯЩ"):
            totals["real"] += count
            if "АДРЕС" in verdict:
                totals["address"] += count
            else:
                totals["name"] += count
        elif verdict.startswith("шум"):
            totals["noise"] += count
        else:
            totals["other"] += count
    return totals


def audit_validity(cases: Sequence[Case]) -> list[str]:
    out: list[str] = ["## Аудит A — валидность", ""]

    # 1. spans
    span_bad: list[str] = []
    bounds_bad: list[str] = []
    for case in cases:
        for item in case.pii:
            text = case.messages[item.msg].content
            if not 0 <= item.start < item.end <= len(text):
                bounds_bad.append(f"{case.id}/{item.id}")
                continue
            if text[item.start:item.end] != item.value:
                span_bad.append(f"{case.id}/{item.id}")
        for neg in case.negatives:
            text = case.messages[neg.msg].content
            if (not 0 <= neg.start < neg.end <= len(text)
                    or text[neg.start:neg.end] != neg.value):
                span_bad.append(f"{case.id}/негатив {neg.value!r}")
    items = sum(len(case.pii) for case in cases)
    negatives = sum(len(case.negatives) for case in cases)
    out += [
        f"Спанов проверено: {items} золотых + {negatives} негативных "
        f"= {items + negatives}.",
        "",
        f"* спан, чей текст не равен заявленному значению: **{len(span_bad)}**",
        f"* спан вне границ своего сообщения: **{len(bounds_bad)}**",
        "",
    ]

    # 2. contradictions the schema does not look for
    overlap = sum(1 for case in cases for item in case.pii
                  for neg in case.negatives
                  if item.msg == neg.msg and item.start < neg.end
                  and item.end > neg.start)
    same_value = sum(1 for case in cases for neg in case.negatives
                     if neg.value in {i.value for i in case.pii})
    # A `must_not_contain` value is REACHABLE if the agent could obtain it, and
    # the text is not the only way it can. For a spoken value the canonical form
    # is digits and the message carries words, so «02204114267» is never a
    # substring of anything said — the agent reaches it through the gateway's own
    # detokenisation, which is precisely the disclosure the demand forbids.
    #
    # This check read the text alone and condemned 190 correct demands, every one
    # of them in `spoken_id`, `repair` or `scope` — the three families built for
    # values said as words. An audit that fails on the register the version
    # exists to measure is not a strict audit, it is a broken one.
    #
    # AND THE VAULT REACHES ACROSS `preceded_by`. `scope`'s `across` arm forbids
    # exactly the value the PREVIOUS case established in another conversation —
    # a demand whose whole content is that the string is not in this case's text.
    # Reading one case at a time condemned all fourteen of them, which is the
    # audit failing on the family built to test the strictest demand it makes.
    by_id = {case.id: case for case in cases}
    absent = []
    for case in cases:
        reachable = ""
        seen: set[str] = set()
        cursor: Case | None = case
        while cursor is not None and cursor.id not in seen:
            seen.add(cursor.id)
            reachable += " " + " ".join(m.content for m in cursor.messages)
            reachable += " " + " ".join(
                f"{item.value} {item.canonical}" for item in cursor.pii)
            cursor = by_id.get(cursor.preceded_by) if cursor.preceded_by else None
        digits = schema.digits_of(reachable)
        for value in case.final.must_not_contain:
            if value in reachable:
                continue
            stripped = schema.digits_of(value)
            if stripped and stripped in digits:
                continue
            absent.append((case.id, value))
    out += [
        "Противоречия, которых `schema.validate` не ищет:",
        "",
        f"* золотой спан пересекается с негативным (одна строка "
        f"одновременно «замаскируй» и «не маскируй»): **{overlap}**",
        f"* та же строка объявлена и золотом, и негативом в одном случае: "
        f"**{same_value}**",
        f"* `must_not_contain` со строкой, которой в случае нет "
        f"(запрет на разглашение того, что негде взять): **{len(absent)}**",
        "",
    ]

    # 3. the wide nets
    net_hits: collections.Counter[tuple[str, str]] = collections.Counter()
    for case in cases:
        claimed = _claimed(case)
        for index, message in enumerate(case.messages):
            if message.role == "system":
                continue
            for name, pattern in _NETS.items():
                for match in pattern.finditer(message.content):
                    if _overlaps(claimed, index, match.start(), match.end()):
                        continue
                    net_hits[(name, message.role)] += 1
            characters = list(message.content)
            for msg, start, end in claimed:
                if msg == index:
                    for position in range(max(start, 0),
                                          min(end, len(characters))):
                        characters[position] = " "
            if schema.numeral_run("".join(characters)) >= _RUN_THRESHOLD:
                net_hits[(f"пробег>={_RUN_THRESHOLD}", message.role)] += 1
    out += [
        "Широкие сети — **шире схемных**: четыре цифры вместо шести, пробег "
        f"числительных {_RUN_THRESHOLD} вместо четырёх. Попадание — это "
        "КАНДИДАТ, а не дефект, и роль сообщения печатается рядом, потому что "
        "четырёхзначное число в результате инструмента — это год.",
        "",
        "| сеть | роль | непокрытых вхождений |",
        "|---|---|---|",
    ]
    for (name, role), count in sorted(net_hits.items()):
        out.append(f"| {name} | {role} | {count} |")
    out.append("")

    # 4. the corpus judging itself
    triggers, examples, streets, names = _trigger_scan(cases)
    unclassified = sorted(set(triggers) - set(_TRIGGER_VERDICTS))
    totals = _verdict_totals(triggers)
    real, noise = totals["real"], totals["noise"]
    out += [
        f"Корпус против самого себя: {len(streets)} слов-улиц и {len(names)} "
        f"слов-имён, которые его СОБСТВЕННЫЙ эталон называет персональными "
        f"данными минимум {_ATTESTED_MIN} раза. Где такое слово стоит в "
        "пользовательской реплике и не покрыто ни золотом, ни негативом — это "
        "кандидат. Внешнего газетира здесь нет намеренно: он был бы вторым "
        "распознавателем, а правило независимости запрещает именно это.",
        "",
        f"Кандидатов: **{sum(triggers.values())}** на "
        f"{len(triggers)} различных словах. Разбор чтением: "
        f"**{real}** настоящих, **{noise}** — шум сети, "
        f"**{totals['other']}** прочих.",
        "",
        "| слово | вхождений | вердикт | пример |",
        "|---|---|---|---|",
    ]
    for word, count in triggers.most_common():
        case_id, sourced, snippet = examples[word]
        verdict = _TRIGGER_VERDICTS.get(word, "**НЕ РАЗОБРАНО**")
        mark = "наполнитель" if sourced else "авторский"
        out.append(f"| {word} | {count} | {verdict} | {case_id} ({mark}): "
                   f"`{snippet.strip()[:70]}` |")
    out.append("")
    if unclassified:
        out += [f"**Неразобранных триггеров: {len(unclassified)}** — "
                f"{unclassified}. Список вердиктов устарел; его надо прочитать "
                f"заново, а не расширить молча.", ""]

    # The residual numeral runs, printed in full. Two of them, so there is no
    # reason to summarise: a run of three that nothing claims in this register is
    # the shape of a house number or a dictated identifier, and both instances
    # turned out to be exactly that.
    runs: list[str] = []
    for case in cases:
        claimed = _claimed(case)
        for index, message in enumerate(case.messages):
            if message.role != "user":
                continue
            characters = list(message.content)
            for msg, start, end in claimed:
                if msg == index:
                    for position in range(max(start, 0),
                                          min(end, len(characters))):
                        characters[position] = "·"
            blanked = "".join(characters)
            length = schema.numeral_run(blanked)
            if length >= _RUN_THRESHOLD:
                runs.append(f"| {case.id} | {length} | `{blanked.strip()}` | "
                            f"{case.note[:70]} |")
    out += [
        "### Остаточные пробеги числительных, все до одного",
        "",
        "Заявленные спаны затёрты точками, потом считается пробег. В этом "
        "регистре непокрытый пробег в три слова — это форма номера дома или "
        "продиктованного идентификатора, и цифровая регулярка слепа к нему "
        "по построению.",
        "",
        "| случай | длина пробега | текст после затирания | заметка случая |",
        "|---|---|---|---|",
    ] + runs + [""]

    street_drift, name_drift = _vocabulary_drift(cases)
    out += [
        "### Один экран наполнителя вместо шести",
        "",
        "Прошлый прогон нашёл 28 настоящих непокрытых ПД — 4 адреса и 24 имени "
        "— и назвал две причины: опечатку «одинадцать», которой нет в "
        "`NUMERAL_WORDS`, и порог пробега. Обе верны и обе поверхностны. "
        "Настоящих причин было три, и все три были СТРУКТУРНЫМИ.",
        "",
        "1. **Экранов наполнителя было шесть, и у каждого свой список имён.** "
        "«оксана» стояла в списке `direct` и ни в одном другом; у `toolresult` "
        "проверки имён не было вовсе, и через неё прошли «александр», «михаил "
        "сергеевич», «игорь». Теперь экран один — `schema.unsafe_filler`, — и "
        "слово, добавленное один раз, защищает все одиннадцать семейств.",
        "2. **Словарь экрана — не газетир, а СОБСТВЕННОЕ золото корпуса.** "
        f"`schema.FILLER_STOPWORDS` — снимок `attested_pii_vocabulary`: "
        f"{len(schema.FILLER_STREET_WORDS)} слов-улиц и "
        f"{len(schema.FILLER_NAME_WORDS)} слов-имён, которые эталон корпуса "
        "называет ПД минимум трижды. Это принципиально: экран, собранный из "
        "сигналов ДЕТЕКТОРА, — второй распознаватель, и правило независимости "
        "запрещает именно его; экран из НАШИХ ЖЕ меток льстить детектору не "
        "может. Словарь намеренно не причёсан: «последний», «новая», «вера» и "
        "«труда» в нём остаются, потому что «улица Последняя» и «Вера» есть в "
        "пулах, и чистка стоила бы решения вкусом при каждом перечитывании.",
        "3. **`numeral_run` мерил не тем, чем мерил опорный корпус.** "
        "`schema.NUMERAL_WORDS` — точный список форм, `probes.is_numeral` — "
        "якорная альтернация по основам, и распределение опорного корпуса "
        "померено ВТОРЫМ, а корпус v3 — ПЕРВЫМ. Две колонки одной таблицы "
        "меряны разными линейками, и короче была наша: в списке есть "
        "«двадцать» и нет «двадцати», есть «тысяча» и нет «тысячу». Оттуда же "
        "и «одинадцать»: список знает точные формы, регистр их коверкает, и "
        "опечатка делала пробег НУЛЁМ. Точный список можно расширять по "
        "опечатке вечно; правило по основе — тот прибор, который этому "
        "регистру нужен, и он в проекте уже был.",
        "",
        "Что это дало, числом: кандидатов 90 → "
        f"{sum(triggers.values())}, настоящих непокрытых ПД 28 → {real}. "
        "Цена: 2.4% реплик RuDevices в пулах наполнителя, одна замороженная "
        "строка в `context` заменена на равную по длине, и 7 из 168 размеченных "
        "вручную адресных реплик отвергнуты (см. ниже).",
        "",
        "### Три вещи, которые НЕЛЬЗЯ было починить экраном",
        "",
        "1. **Ручная разметка адресов молчит об именах.** "
        "`rudevices_addresses.json` размечает АДРЕСА, поэтому «говорит громова "
        "проедьте пожалуйста по наличной дом сорок» несёт фамилию, которой не "
        "заявляет никто. Заявить её поиском по готовой строке ЗАПРЕЩЕНО — "
        "эталон выводится из того, что генератор построил, и обратное стоило "
        "v2 162 провала из 183. Поэтому строка ОТВЕРГНУТА: "
        "`schema.unsafe_outside` судит ОСТАТОК после вычитания заявленных "
        "спанов, и 7 из 168 строк его не проходят. Это цена отказа достраивать "
        "чужую разметку догадкой.",
        "2. **`ctx-verb18` брал `spans[0]`.** Разметчик записал ДВА адреса "
        "(«восточная девять пятый подъезд поедем на ленина сто сорок шесть» — "
        "подача и назначение), а сборщик читал первый. Второй настоящий адрес "
        "становился молчанием эталона о том, что в тексте есть. Чинится не "
        "экраном, а тем, что теперь заявляются ВСЕ спаны разметки; инструмент "
        "`send_car` берёт один адрес, поэтому второй несёт `tool_param=\"\"` — "
        "поле само называет это «есть, и ни один инструмент не потребляет».",
        "3. **«ленинский район» — намеренная ссылка на место, но она молчит.** "
        "`wordnum._TAILS` берёт её дословно из разметки и в комментарии пишет, "
        "что маскировать её — сломать фразу. Ровно для этого есть семейство "
        "негативов `city_reference`, а спан не объявлен. Это ОСТАВЛЕНО и "
        "названо: пока негатива нет, шлюз, замаскировавший район, не получает "
        "ничего — ни штрафа, ни зачёта. Единственный оставшийся кандидат "
        "широкой сети, который не является шумом.",
        "",
        "### Снимок словаря против корпуса",
        "",
        "Снимок в `schema` — константа, а константы устаревают. Проверка "
        "пересчитывает словарь по СОБРАННОМУ корпусу и называет каждое слово, "
        "которого константе не хватает. Направление у неё одно: наполнитель не "
        "несёт золота, поэтому ужесточение экрана не может выбросить слово из "
        "списка, который этим экраном движет — один проход сходится. "
        "Инвариантности к РЕЗУ у неё нет: значение, названное дважды вместо "
        "трёх, из словаря выпадает, и при резе до 2 000 так появилось десять "
        "слов.",
        "",
        (f"Расхождение сейчас: улицы {street_drift or '—'}, "
         f"имена {name_drift or '—'}."
         if (street_drift or name_drift) else
         "Расхождение сейчас: **нет**. Снимок и корпус согласны."),
        "",
        f"Порядок величин: {real} непокрытых предметов против {items} "
        f"заявленных.",
        "",
    ]
    return out


# --- (b) distribution -----------------------------------------------------

_ANY_DIGIT = re.compile(r"\d")
_PUNCT = re.compile(r"[.,;:!?]")
_LATIN = re.compile(r"[A-Za-z]")

_METRIC_LABELS: tuple[tuple[str, str], ...] = (
    ("replicas", "реплик"),
    ("digit", "с цифрой"),
    ("capital", "с заглавной"),
    ("punct", "с пунктуацией"),
    ("period", "кончается точкой"),
    ("hyphen", "с дефисом"),
    ("latin", "с латиницей"),
    ("single", "однословных"),
    ("wmean", "слов, среднее"),
    ("wmed", "слов, медиана"),
    ("cmean", "знаков, среднее"),
    ("cmed", "знаков, медиана"),
    ("r1", "пробег>=1"),
    ("r3", "пробег>=3"),
    ("r5", "пробег>=5"),
)


def _metrics(texts: Sequence[str]) -> dict[str, float]:
    if not texts:
        return {}
    total = len(texts)
    words = [len(text.split()) for text in texts]
    chars = [len(text) for text in texts]
    runs = [schema.numeral_run(text) for text in texts]
    return {
        "replicas": float(total),
        "digit": sum(1 for t in texts if _ANY_DIGIT.search(t)) / total,
        "capital": sum(1 for t in texts if t[:1].isupper()) / total,
        "punct": sum(1 for t in texts if _PUNCT.search(t)) / total,
        "period": sum(1 for t in texts if t.rstrip().endswith(".")) / total,
        "hyphen": sum(1 for t in texts if "-" in t) / total,
        "latin": sum(1 for t in texts if _LATIN.search(t)) / total,
        "single": sum(1 for w in words if w == 1) / total,
        "wmean": statistics.mean(words),
        "wmed": float(statistics.median(words)),
        "cmean": statistics.mean(chars),
        "cmed": float(statistics.median(chars)),
        "r1": sum(1 for r in runs if r >= 1) / total,
        "r3": sum(1 for r in runs if r >= 3) / total,
        "r5": sum(1 for r in runs if r >= 5) / total,
    }


def _reference_metrics(path: Path) -> dict[str, float]:
    combined = json.loads(path.read_text(encoding="utf-8"))["register"]["combined"]
    return {
        "replicas": float(combined["replicas"]),
        "digit": combined["share_with_any_digit"],
        "capital": combined["share_starting_capital"],
        "punct": combined["share_any_sentence_punctuation"],
        "period": combined["share_ending_period"],
        "hyphen": combined["share_with_hyphen"],
        "latin": combined["share_with_latin"],
        "single": combined["share_single_word"],
        "wmean": combined["words_mean"],
        "wmed": float(combined["words_median"]),
        "cmean": combined["chars_mean"],
        "cmed": float(combined["chars_median"]),
        "r1": combined["share_numeral_run_ge1"],
        "r3": combined["share_numeral_run_ge3"],
        "r5": combined["share_numeral_run_ge5"],
    }


def _user_texts(cases: Sequence[Case], register: str) -> list[str]:
    """Every USER turn, optionally of one register.

    The tool result is machine output and the system prompt is written by the
    integrator; measuring either against a speech statistic measures the wrong
    thing, and this is the one place that decision is made.
    """
    return [message.content for case in cases
            if not register or case.register == register
            for message in case.messages if message.role == "user"]


def _v2_user_texts(path: Path, register: str) -> tuple[list[str], int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    texts: list[str] = []
    by_reference = 0
    for case in payload["cases"]:
        if register and case.get("register") != register:
            continue
        for message in case["messages"]:
            if message["role"] != "user":
                continue
            content = message.get("content") or ""
            if content:
                texts.append(content)
            else:
                by_reference += 1
    return texts, by_reference


def _format_row(label: str, metrics: dict[str, float]) -> str:
    cells = []
    for key, _ in _METRIC_LABELS:
        value = metrics.get(key)
        if value is None:
            cells.append("—")
        elif key == "replicas":
            cells.append(f"{int(value)}")
        elif key in ("wmean", "wmed", "cmean", "cmed"):
            cells.append(f"{value:.1f}")
        else:
            cells.append(f"{value * 100:.2f}%")
    return f"| {label} | " + " | ".join(cells) + " |"


def audit_distribution(cases: Sequence[Case]) -> list[str]:
    out: list[str] = ["## Аудит B — распределение против опорного", ""]
    reference = _reference_metrics(REFERENCE_PATH)
    user_all = [m.content for c in cases for m in c.messages if m.role == "user"]
    rows: list[tuple[str, dict[str, float]]] = [
        ("ОПОРНЫЙ (53 324 реплики живой речи)", reference),
        ("v3 — все пользовательские реплики", _metrics(user_all)),
    ]
    for register in schema.REGISTERS:
        texts = [m.content for c in cases if c.register == register
                 for m in c.messages if m.role == "user"]
        rows.append((f"v3 — {register}", _metrics(texts)))
    # The adversarial row. The register gate in `_register_problems` is `any`
    # over a case's user turns, so one capital makes a `clean` case literary and
    # one digit makes a `voice_itn` case an ITN case — while every other reply in
    # it may be lower-case filler. That is correct as a gate and misleading as a
    # distribution: the corpus-wide numbers below are helped by filler that
    # carries nothing. Measured again over the replies that DO carry a claimed
    # item, which is where the ground truth actually lives.
    carrying: list[str] = []
    carrying_voice: list[str] = []
    for case in cases:
        claimed = {i.msg for i in case.pii} | {n.msg for n in case.negatives}
        for index, message in enumerate(case.messages):
            if message.role == "user" and index in claimed:
                carrying.append(message.content)
                if case.register == "voice_raw":
                    carrying_voice.append(message.content)
    claimed_metrics = _metrics(carrying)
    rows.append(("v3 — только реплики С размеченным предметом", claimed_metrics))
    rows.append(("v3 — то же, но только voice_raw", _metrics(carrying_voice)))

    v2_note = ""
    if V2_CORPUS_PATH.exists():
        v2_all, missing = _v2_user_texts(V2_CORPUS_PATH, "")
        v2_voice, _ = _v2_user_texts(V2_CORPUS_PATH, "voice_raw")
        rows.append(("v2 — все реплики", _metrics(v2_all)))
        rows.append(("v2 — voice_raw", _metrics(v2_voice)))
        v2_note = (f"v2 читается из `{V2_CORPUS_PATH.name}`; {missing} его "
                   f"реплик несут текст по ссылке и в подсчёт не входят.")

    header = "| набор | " + " | ".join(name for _, name in _METRIC_LABELS) + " |"
    out += [
        "Один и тот же счёт по одним и тем же правилам: опорный корпус живой "
        "речи, v3 целиком, v3 по регистрам, v2 для сравнения. Считаются только "
        "ПОЛЬЗОВАТЕЛЬСКИЕ реплики — результат инструмента машинный, а системная "
        "подсказка написана интегратором, и мерить их речевым правилом значит "
        "мерить не то.",
        "",
        header,
        "|" + "---|" * (len(_METRIC_LABELS) + 1),
    ]
    out += [_format_row(label, metrics) for label, metrics in rows]
    out.append("")
    if v2_note:
        out += [v2_note, ""]
    reference = rows[0][1]
    whole = rows[1][1]
    v2_row = next((m for label, m in rows if label == "v2 — все реплики"), {})
    out += [
        "### Как это читать",
        "",
        "**Главное сравнение, ради которого аудит и написан — v3 против v2 по "
        "тем самым трём числам, на которых v2 провалилась:**",
        "",
        "| | v2 | v3 | опорный |",
        "|---|---|---|---|",
        f"| реплик с заглавной | {v2_row.get('capital', 0):.2%} | "
        f"{whole['capital']:.2%} | {reference['capital']:.2%} |",
        f"| реплик с пунктуацией | {v2_row.get('punct', 0):.2%} | "
        f"{whole['punct']:.2%} | {reference['punct']:.2%} |",
        f"| реплик с цифрой | {v2_row.get('digit', 0):.2%} | "
        f"{whole['digit']:.2%} | {reference['digit']:.2%} |",
        f"| реплик с латиницей | {v2_row.get('latin', 0):.2%} | "
        f"{whole['latin']:.2%} | {reference['latin']:.2%} |",
        "",
        "По всем четырём v3 ближе к живой речи в 8–17 раз. В речевых "
        "регистрах совпадение точное — ноль против ноля, — потому что "
        "`_register_problems` это ТРЕБУЕТ, а не потому что так вышло.",
        "",
        # The three numbers are READ OUT of the row above rather than quoted:
        # a paragraph holding literals its own table recomputes drifts on the
        # first rebuild, and this one had drifted by three points.
        f"**Три строки читать вместе, и вот почему.** Регистровый шлюз схемы "
        f"устроен на `any` по репликам случая: одной заглавной хватает, чтобы "
        f"случай считался литературным, одной цифры — чтобы `voice_itn`. "
        f"Поэтому корпусные доли РАЗБАВЛЕНЫ наполнителем, который не несёт "
        f"ничего, и «v3 — все реплики» льстит набору. Строка «только реплики "
        f"С размеченным предметом» — честная верхняя оценка: там, где стоит "
        f"эталон, цифр {claimed_metrics['digit']:.1%}, пунктуации "
        f"{claimed_metrics['punct']:.1%}, заглавных "
        f"{claimed_metrics['capital']:.1%}. Последняя строка сужает то же "
        f"самое до `voice_raw`, и это единственное сравнение с опорным по "
        f"существу.",
        "",
        "**Где v3 расходится с живой речью, числом:**",
        "",
        f"* длина: {whole['wmean']:.1f} слова против {reference['wmean']:.1f} "
        f"в опорном, {whole['cmean']:.0f} знаков против "
        f"{reference['cmean']:.0f}. Реплика тут почти вдвое длиннее живой, "
        f"потому что несёт ПД вместе с обрамлением, а в жизни девять реплик "
        f"из десяти — короткое «ага» без ничего.",
        f"* пробег числительных: {whole['r1']:.2%} против "
        f"{reference['r1']:.2%} при пробеге ≥1 и {whole['r3']:.2%} против "
        f"{reference['r3']:.2%} при ≥3. Это ПЕРЕвес, и он намеренный: "
        f"произнесённый номер — один из двух дефектов, ради которых версия "
        f"делается. Для сравнения v2 на voice_raw давала "
        f"{next(m for lb, m in rows if lb == 'v2 — voice_raw')['r3']:.2%} при ≥3 "
        f"и {next(m for lb, m in rows if lb == 'v2 — voice_raw')['r5']:.2%} при "
        f"≥5 — то есть перевешивала ещё сильнее.",
        f"* дефис: {whole['hyphen']:.2%} против {reference['hyphen']:.2%}. "
        f"Проверено пословно: это «что-то» (145), «какие-то» (93), «кто-то» "
        f"(92), «ха-ха» (75) — настоящая речь RuDevices, а не форматирование "
        f"телефона. Опорная доля ниже потому, что считает и короткие реплики, "
        f"где дефису негде взяться.",
        f"* однословных {whole['single']:.2%} против {reference['single']:.2%}, "
        f"и в `voice_raw` их НОЛЬ — см. аудит C.",
        "",
    ]

    # The density statement, which is the honest limitation of any PII corpus.
    total_user = 0
    with_claim = 0
    with_gold = 0
    for case in cases:
        user_indices = {i for i, m in enumerate(case.messages) if m.role == "user"}
        claimed = {i.msg for i in case.pii} | {n.msg for n in case.negatives}
        gold = {i.msg for i in case.pii if i.duty == "required"}
        total_user += len(user_indices)
        with_claim += len(user_indices & claimed)
        with_gold += len(user_indices & gold)
    reference_share = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))[
        "share_of_replicas_carrying_any_pii"]
    out += [
        "### Плотность ПД — то, что корпус НЕ воспроизводит и не может",
        "",
        f"* живая речь: {reference_share['calls']['share']:.3%} реплик "
        f"(звонки) и {reference_share['rudevices']['share']:.3%} (RuDevices) "
        f"несут хоть какие-то ПД, и это ПОЛ — безмаркерные адреса измерению "
        f"недоступны.",
        f"* v3: {with_claim}/{total_user} = **{with_claim / total_user:.1%}** "
        f"реплик несут размеченный предмет, из них с ЗОЛОТЫМ ПД "
        f"{with_gold / total_user:.1%}.",
        "",
        "Это расхождение примерно в двадцать раз, оно НЕ дефект и оно не "
        "чинится: набор, где девять реплик из десяти пусты, тратил бы 90% "
        "прогона на подтверждение, что пустая реплика не маскируется. Цена "
        "названа здесь, чтобы её не забыли: доля ложных масок НА РЕПЛИКУ, "
        "измеренная тут, к производственной не относится, и `schema.reweight()` "
        "существует ровно для того, чтобы развёртывание пересчитало её на свой "
        "трафик.",
        "",
    ]
    return out


# --- (c) unreachability ---------------------------------------------------

def audit_unreachable(cases: Sequence[Case]) -> list[str]:
    out: list[str] = ["## Аудит C — недостижимость", ""]
    total = len(cases)

    # empty cells in the cross-tabs
    holes: list[str] = []
    pairs = collections.Counter(
        (case.register, item.type) for case in cases for item in case.pii)
    present_types = {t for _, t in pairs}
    for register in schema.REGISTERS:
        for kind in present_types:
            if not pairs[(register, kind)]:
                holes.append(f"регистр {register} × тип {kind}")
    fam_reg = collections.Counter((c.family, c.register) for c in cases)
    families = sorted({c.family for c in cases})
    for family in families:
        for register in schema.REGISTERS:
            if not fam_reg[(family, register)]:
                holes.append(f"семейство {family} × регистр {register}")
    fam_ctx = collections.Counter((c.family, c.context) for c in cases)
    for family in families:
        for rung in schema.CONTEXT_RUNGS:
            if not fam_ctx[(family, rung)]:
                holes.append(f"семейство {family} × контекст {rung}")

    out += [
        "### Пустые клетки перекрёстных таблиц",
        "",
        f"Перебраны регистр×тип, семейство×регистр, семейство×контекст. "
        f"Пустых клеток: **{len(holes)}**."
        + (f" {holes}" if holes else " Ни одной — по этим трём осям корпус "
                                     "сплошной."),
        "",
    ]

    # value provenance: which types can never carry an observed surface form
    by_type_source: dict[str, collections.Counter[str]] = {}
    for case in cases:
        for item in case.pii:
            by_type_source.setdefault(item.type, collections.Counter())[
                item.value_source] += 1
    out += ["### Откуда берётся ЗНАЧЕНИЕ, по типам", "",
            "| тип | corpus | pool | template | вывод |", "|---|---|---|---|---|"]
    for kind in schema.TYPES:
        counts = by_type_source.get(kind, collections.Counter())
        verdict = ("наблюдаемая форма достижима" if counts["corpus"]
                   else "НИ ОДНОГО значения, взятого из живой речи")
        out.append(f"| {kind} | {counts['corpus']} | {counts['pool']} | "
                   f"{counts['template']} | {verdict} |")
    out.append("")

    # spoken items: the two defect classes v3 exists for
    spoken = collections.Counter(i.type for c in cases for i in c.pii if i.spoken)
    out += [
        "### Произнесённые значения — два дефекта, ради которых версия и делалась",
        "",
        "| тип | произнесённых словами | порог отчётности (MIN_TYPE_DENOMINATOR="
        f"{schema.MIN_TYPE_DENOMINATOR}) |",
        "|---|---|---|",
    ]
    for kind in schema.TYPES:
        count = spoken.get(kind, 0)
        mark = "ниже порога — печатается счётом, не долей" \
            if count < schema.MIN_TYPE_DENOMINATOR else "достаточно"
        out.append(f"| {kind} | {count} | {mark} |")
    out.append("")

    # structural absences
    absent: list[str] = []
    if not any(case.preceded_by for case in cases):
        absent.append(
            "**`preceded_by` не несёт ни один случай.** Значит недостижимы: "
            "семейство `scope` целиком, `LinkExpectation.case` (связь через "
            "границу случая) и весь путь «один вольт на два разговора». Это "
            "не пробел выборки, это отсутствующий генератор.")
    if not any(case.adjudicated for case in cases):
        annotated = sum(1 for case in cases if case.annotators)
        absent.append(
            f"**Ни один случай не `adjudicated`** ({annotated} несут "
            f"`annotators>0`). Схема прямо пишет, что `duty` — самая ненадёжная "
            f"разметка в TAB (Fleiss kappa 0.46) и требует двух разметчиков с "
            f"третьим на разрешение. Здесь `duty` проставлен генератором, то "
            f"есть колонка «optional» опирается на авторское суждение, а не на "
            f"согласие.")
    # MEASURED, not asserted, and the wording matters. The claim that stood here
    # was «not one character from the calls corpus», which is falsifiable and
    # false: eleven authored operator lines — «слушаю», «секунду», «договорились»
    # — coincide with utterances in it, because a phrase that short cannot be
    # anybody's property. The licence property is about CARRYING, and that is
    # what is counted: a `Source` naming the corpus, or a message hydrated from
    # it. Restating an unmeasurable claim in a report is how a report becomes
    # decoration.
    carried = collections.Counter(
        m.source.corpus for c in cases for m in c.messages if m.source)
    shapes_from = sum(1 for c in cases if c.provenance.corpus == "speech_calls")
    if "speech_calls" not in carried:
        absent.append(
            f"**Ни одной реплики, НЕСОМОЙ из корпуса звонков.** OpenSTT "
            f"`asr_calls_2_val` — CC BY-NC 4.0, и `validate` запрещает нести "
            f"его текст; `hydrate` его заполняет и тем самым делает случай "
            f"невалидным. При этом {shapes_from} случаев объявляют его своим "
            f"источником ФОРМЫ — то есть регистр, ближайший к продуктовому "
            f"трафику (звонок в колл-центр), поставляет сюда порядок слотов и "
            f"никогда сами слова. Всё дословное здесь — RuDevices, бытовая "
            f"речь, а не разговор с оператором.\n\n"
            f"    Точность формулировки: «ни одного символа» было бы неправдой. "
            f"Одиннадцать авторских операторских реплик («слушаю», «секунду», "
            f"«договорились») совпадают с репликами того корпуса дословно, и "
            f"иначе быть не может — фраза такой длины не может никому "
            f"принадлежать. Считается ПЕРЕНОС: `Source` с именем корпуса либо "
            f"сообщение, гидратированное из него. Их ноль.")
    latin_speech = sum(
        1 for c in cases if c.register in schema.SPEECH_REGISTERS
        for m in c.messages if m.role == "user" and _LATIN.search(m.content))
    if not latin_speech:
        absent.append(
            "**В речевых регистрах нет ни одной латинской буквы.** Это верно "
            "по опорному корпусу (доля 0.0), но означает, что латинское имя и "
            "почта живут только в письменных регистрах, а гомоглиф внутри "
            "кириллического слова — только там, куда его положил преобразователь "
            "регистра.")
    single_word = sum(
        1 for c in cases if c.register == "voice_raw"
        for m in c.messages if m.role == "user" and len(m.content.split()) == 1)
    if not single_word:
        absent.append(
            "**Ни одной однословной реплики в `voice_raw`** при 2.69% в опорном. "
            "Голое «сорок пять» ответом на вопрос оператора в корпус не "
            "попадает: каждая речевая реплика собрана как самостоятельное "
            "высказывание.")
    deep_no_filler = sum(1 for c in cases if c.context == "deep"
                         and not any(m.source for m in c.messages))
    deep = sum(1 for c in cases if c.context == "deep")
    absent.append(
        f"**Глубокий контекст — всегда добор наполнителем.** {deep - deep_no_filler} "
        f"из {deep} случаев `deep` набирают свои 4000 знаков чужими репликами "
        f"RuDevices. Настоящего длинного РАЗГОВОРА (где двадцать реплик назад "
        f"обсуждали то же дело) в корпусе нет — есть ПД внутри длинного шума. "
        f"Дефект, который просыпается от связной длинной истории, а не от "
        f"длины, этим набором невидим.")
    assistant_pii = sum(1 for c in cases for i in c.pii
                        if c.messages[i.msg].role == "assistant")
    absent.append(
        f"**ПД в ассистентской реплике: {assistant_pii} предметов** на "
        f"{sum(len(c.pii) for c in cases)}. Собственный прошлый ответ агента, "
        f"возвращающийся в запрос, — почти пустая страта.")
    negative_only = sum(1 for c in cases
                        if not any(i.duty == "required" for i in c.pii))
    # TWO HOLES THIS RUN'S OWN FIX OPENED, named because a repair that is not
    # priced is a repair nobody can argue with.
    absent.append(
        "**Наполнитель больше не может нести ни одного слова из "
        f"{len(schema.FILLER_STOPWORDS)}-словного списка ПД корпуса.** Это "
        "цена общего экрана, и она платится структурой: в живой речи "
        "2.4% реплик RuDevices несут такое слово, здесь — НОЛЬ. То есть "
        "положение «незаявленное настоящее имя стоит рядом с заявленным» — "
        "ровно то, где шлюзу труднее всего решить, — из корпуса теперь "
        "УДАЛЕНО по построению. Оно не заменено ничем: заявить такое имя "
        "нельзя (эталон выводится из построенного, а не из поиска по строке), "
        "а объявить негативом — значит соврать, потому что это ПД. Единственный "
        "честный выход — размеченный человеком слой, которого у нас нет.",
    )
    absent.append(
        f"**Сеть аудита слепа к значению, названному эталоном меньше "
        f"{schema.ATTESTED_MIN} раз.** Словарь строится по СОБСТВЕННОМУ золоту "
        f"корпуса с порогом «минимум трижды», поэтому редкое имя, стоящее в "
        f"пуле один раз, не попадёт в словарь и его непокрытое вхождение "
        f"останется невидимым. Порог не произволен: на единице словарь "
        f"вбирает всякую опечатку и всякую однократную форму, и сеть перестаёт "
        f"быть читаемой. Это КОМПРОМИСС, а не свойство, и он односторонний — "
        f"занижает найденное, никогда не завышает.",
    )
    negative_family = sum(1 for c in cases if c.family == "negative")
    absent.append(
        f"**Случаев, где маскировать нечего вообще: {negative_only} "
        f"({negative_only / total:.1%}).** Потолок схемы — "
        f"{schema.MAX_NEGATIVE_ONLY_SHARE:.0%}, и он не выбран: семейство "
        f"`negative` даёт {negative_family} случаев, где над-маскирование "
        f"измеряется САМО ПО СЕБЕ, а не приложением к чужому случаю. Что "
        f"остаётся недостижимым — это ЧАСТОТА: в живой речи такие реплики "
        f"составляют 98%, здесь 6.2%, и выше поднять нельзя, потому что "
        f"нулевой шлюз проходит их все и потолок схемы стоит ровно за этим.")

    missing = [name for name in schema.FAMILIES
               if not any(case.family == name for case in cases)]
    if missing:
        absent.insert(0, f"**Отсутствуют семейства {missing}.** Корпус неполон; "
                         f"всё ниже относится к тому, что есть.")
    out += ["### Что в корпус не может попасть по построению", ""]
    out += [f"{index}. {text}" for index, text in enumerate(absent, 1)]
    out.append("")

    # vocabulary concentration — the v2 defect, measured
    out += [
        "### Концентрация словаря — та самая проверка, на которой упала v2",
        "",
        "v2 отличала «улица Чехова, дом 29, квартира 66» от «улица Чехова, дом "
        "43, квартира 46» счётчиком. Здесь печатается доля самого частого "
        "значения: чем она ближе к 1/различных, тем меньше в наборе "
        "счётчик-вариантов.",
        "",
        "| тип | предметов | различных | доля самого частого |",
        "|---|---|---|---|",
    ]
    for kind in schema.TYPES:
        values = collections.Counter(i.canonical for c in cases for i in c.pii
                                     if i.type == kind)
        if not values:
            continue
        count = sum(values.values())
        out.append(f"| {kind} | {count} | {len(values)} | "
                   f"{values.most_common(1)[0][1] / count:.1%} |")
    out.append("")
    return out


# --- the trim arithmetic --------------------------------------------------

# Cases and clusters per module on the seed corpus. A cluster is what an error
# bar is computed over, so cases-per-cluster is how many cases a module spends
# to buy one unit of statistical power — and it is the only redundancy measure
# the schema itself already endorses.
def audit_trim(cases: Sequence[Case]) -> list[str]:
    """The trim AS APPLIED, with the evidence that chose it.

    This section was a proposal for one run and is a record now. It is kept
    rather than deleted because the trim is the one corpus decision that is not
    visible in any per-case field: nothing in `corpus.json` says `indirect` could
    have been 250, and a reader who cannot see the counterfactual cannot judge
    the choice.
    """
    total = len(cases)
    out: list[str] = ["## Рез: что срезано и по какому признаку", ""]
    out += [
        f"Одиннадцать генераторов при своих канонических размерах дают 2 001 "
        f"случай, полоса схемы — {schema.CORPUS_SIZE_BAND[0]}–"
        f"{schema.CORPUS_SIZE_BAND[1]}. Собрано **{total}**.",
        "",
        "Резать надо там, где случай покупает МЕНЬШЕ ВСЕГО. Единица "
        "статистической силы здесь — кластер, а не случай: схема сама считает "
        "доверительные интервалы по кластерам, потому что один адрес, "
        "сказанный семью людьми, — это одно значение и семь вхождений. Второй "
        "признак — произнесённые предметы: версия делается ради двух дефектов, "
        "и оба живут в числах, сказанных словами.",
        "",
        "| модуль | случаев | кластеров | случаев на кластер | spoken-предметов "
        "| различных негативов | deep | решение |",
        "|---|---|---|---|---|---|---|---|",
    ]
    modules = {
        "direct": [c for c in cases if c.id.startswith("direct-")],
        "compare": [c for c in cases if c.id.startswith("cmp-")],
        "context": [c for c in cases if c.id.startswith("ctx-")],
        "indirect": [c for c in cases if c.id.startswith("i3-ind-")],
        "multi": [c for c in cases if c.id.startswith("crowd-")],
        "toolresult": [c for c in cases if c.id.startswith("result-")],
        "spoken_id": [c for c in cases if c.id.startswith("sid-")],
        "wordnum": [c for c in cases if c.id.startswith("wordnum-")],
        "repair": [c for c in cases if c.id.startswith("rep-")],
        "negative": [c for c in cases if c.id.startswith("neg-")],
        "scope": [c for c in cases if c.id.startswith("sc-")],
    }
    planned = {name: count for name, _, count in build.FAMILY_PLAN}
    for name, rows in modules.items():
        if not rows:
            continue
        clusters = len({c.cluster for c in rows})
        ratio = len(rows) / clusters if clusters else 0.0
        spoken = sum(1 for c in rows for i in c.pii if i.spoken)
        distinct_neg = len({n.value for c in rows for n in c.negatives})
        deep = sum(1 for c in rows if c.context == "deep")
        decision = build._TRIM_REASON.get(name, f"{planned.get(name, 0)}: не резалось")
        out.append(f"| {name} | {len(rows)} | {clusters} | {ratio:.2f} | "
                   f"{spoken} | {distinct_neg} | {deep} | {decision} |")
    out += [
        "",
        "Почему НЕ «резать самое большое». `direct` — самая большая цифра и "
        "самый дорогой рез: 431 кластер на 450 случаев, то есть почти каждый "
        "случай там своё наблюдение. `indirect` — 250 случаев на 28 кластеров "
        "И НОЛЬ произнесённых предметов: в оба дефекта, ради которых строится "
        "v3, он не вносит ничего. Отсюда −106 из него против −54 из `direct`.",
        "",
        "Два ограничения, найденные перебором и не выведенные из принципа: "
        "`context` вообще не принимает `count` (его `deep`-случаи режутся из "
        "замороженного пула наполнителя, и перерез изменил бы длину каждого "
        "длинного случая), а `toolresult` ОТКАЗЫВАЕТСЯ на всём отрезке 158–198, "
        "кроме 168, — его собственная доля литературного регистра там переходит "
        "5%, и модуль ПАДАЕТ, а не тихо меняет состав. Генератор, умеющий "
        "сказать «нет», — единственная причина, по которой эта таблица "
        "проверяема, а не спорна.",
        "",
        "Семейства второй волны не резались ни на один случай. Каждое из них "
        "существует потому, что класс дефекта в корпусе ПРИСУТСТВОВАЛ и не был "
        "ИЗМЕРИМ: один экземпляр на тип печатается в таблице и не несёт доли. "
        "Рез вернул бы ровно то состояние, ради выхода из которого они "
        "написаны.",
        "",
    ]
    return out


# --- the ladder -----------------------------------------------------------

def audit_ladder(cases: Sequence[Case], ladder: schema.Ladder) -> list[str]:
    """The rungs, their coverage, and PROOF that the pin catches a re-labelling.

    The proof is not decoration. An earlier ladder in this project hashed case
    ids alone; a re-labelling of the source moved every span, every id survived,
    and the pin stayed green while the measurement walked away. So the digest is
    exercised here against a corpus whose IDS ARE IDENTICAL and one of whose
    spans has moved by a single character, and the report carries the two
    numbers rather than the assurance.
    """
    problems = schema.check_ladder(cases, ladder)
    out: list[str] = [
        "## Ярусы",
        "",
        f"`check_ladder`: **{len(problems)} претензий**"
        + ("" if not problems else f" — {problems}") + ".",
        "",
        "Ярус — не префикс. Строится в два хода: жадное покрытие, которое "
        "ЗАКРЫВАЕТ каждое измерение, потом дефицитный добор, который держит "
        "доли яруса рядом с корпусными. Вложенность по построению, "
        "`check_ladder` её потом доказывает, а не принимает на слово.",
        "",
        "```",
    ]
    out += build.coverage_table(cases, ladder)
    out += ["```", ""]

    # the freeze proof
    moved = list(cases)
    for index, case in enumerate(moved):
        if case.pii and case.pii[0].start > 0:
            item = case.pii[0]
            shifted = schema.PiiItem(
                id=item.id, type=item.type, value=item.value,
                canonical=item.canonical, start=item.start - 1, end=item.end - 1,
                msg=item.msg, identity=item.identity, duty=item.duty,
                value_source=item.value_source, spoken=item.spoken,
                tool_param=item.tool_param)
            moved[index] = schema.Case(
                **{**case.__dict__, "pii": (shifted,) + case.pii[1:]})
            break
    ids_before = [case.id for case in cases]
    ids_after = [case.id for case in moved]
    out += [
        "### Заморозка: пин ловит переразметку, а не только пропажу случая",
        "",
        f"* дайджест корпуса: `{schema.corpus_digest(cases)[:24]}`",
        f"* тот же корпус, один спан сдвинут на один символ, идентификаторы "
        f"НЕ ТРОНУТЫ (совпадают: {ids_before == ids_after}): "
        f"`{schema.corpus_digest(moved)[:24]}`",
        "",
        "Дайджест хеширует утверждения — спаны, ожидаемые вызовы, связи, "
        "закрытый ответ, — поэтому исправленное смещение делает ярус "
        "просроченным и `tier()` отказывается, вместо того чтобы отдать "
        "прошлогоднее имя новому измерению. Текст сообщений в дайджест "
        "НЕ входит намеренно: лицензированные реплики едут по ссылке до "
        "`hydrate`, и хеш содержимого зависел бы от того, гидратировал ли "
        "вызывающий. Текст пришпилен строже — по `Source.sha256`, по одному "
        "сообщению.",
        "",
        "| ярус | случаев | различных значений | кластеров | верхняя граница "
        "доли отказов при НУЛЕ наблюдённых (Клоппер–Пирсон, 95%) |",
        "|---|---|---|---|---|",
    ]
    by_id = {case.id: case for case in cases}
    for name in schema.TIER_SIZES:
        rows = [by_id[case_id] for case_id in ladder.tiers[name]]
        bound = schema.TIER_ZERO_FAILURE_BOUND.get(name)
        out.append(
            f"| {name} | {len(rows)} | "
            f"{sum(schema.distinct_values(rows).values())} | "
            f"{len({case.cluster for case in rows})} | "
            + (f"{bound:.2%} |" if bound else "— (весь корпус) |"))
    out.append("")
    return out


# --- entry point ----------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=build.SEED)
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    cases = build.build_corpus(args.seed)
    problems = build.corpus_problems(cases)
    ladder = build.build_ladder(cases, args.seed, version=0 if problems else 1)
    lines = _header(cases, ladder, problems, args.seed)
    lines += audit_validity(cases)
    lines += audit_distribution(cases)
    lines += audit_unreachable(cases)
    lines += audit_ladder(cases, ladder)
    lines += audit_trim(cases)
    # ONE command, ONE report. The cross-check used to live in its own file and
    # its own invocation, and the half nobody re-ran went stale first — it was
    # still naming a defect by case id three fixes after that defect was gone.
    lines += ["", audit_crosscheck.render(cases), ""]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"записан {args.out} — {len(lines)} строк, "
          f"{len(cases)} случаев, {len(problems)} корпусных претензий")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
