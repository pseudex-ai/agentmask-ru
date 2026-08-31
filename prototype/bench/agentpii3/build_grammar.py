"""Assemble mined/dispatch_grammar.json out of SOVA RuDevices + the hand labels.

Run: python3 build_grammar.py   (no arguments, no network, no bundle)
"""

import json
import re
import collections
from typing import Callable

import pymorphy3

import mine_dispatch as m

OUT = m.OUT

UNITS_OF_MEASURE: frozenset[str] = frozenset(
    """лет год года годы минут минута минуты рублей рубля рубль раз раза разы
    тысяч тысячи тысяча процентов процента дня дней день часа часов час недели
    неделя месяца месяцев градусов градуса гривен баксов долларов евро копеек
    метров метра километров штук штуки литра литров грамм граммов килограмм
    человек человека людей копейки миллиона миллионов""".split()
)


def _counter_with_examples(
    rows: list[str], predicate: Callable[[str], str]
) -> tuple[collections.Counter, dict[str, str]]:
    counts: collections.Counter = collections.Counter()
    examples: dict[str, str] = {}
    for text in rows:
        key = predicate(text)
        if not key:
            continue
        counts[key] += 1
        examples.setdefault(key, text)
    return counts, examples


def value_shapes(labels: list[dict[str, object]], stratum: str) -> list[dict[str, object]]:
    counts: collections.Counter = collections.Counter()
    example: dict[str, str] = {}
    reply: dict[str, str] = {}
    for row in labels:
        if row["label"] != "адрес с номером" or row["filter"] != stratum:
            continue
        for value in row["spans"]:
            pattern = m.shape(value)
            counts[pattern] += 1
            example.setdefault(pattern, value)
            reply.setdefault(pattern, row["text"])
    total = sum(counts.values())
    return [
        {
            "pattern": p,
            "count": n,
            "share": round(n / total, 4),
            "example": example[p],
            "example_reply": reply[p],
            "carries": m.carried_types(p),
        }
        for p, n in counts.most_common()
    ]


def mined_shapes(rows: list[str]) -> list[dict[str, object]]:
    counts: collections.Counter = collections.Counter()
    example: dict[str, str] = {}
    reply: dict[str, str] = {}
    for text in rows:
        for candidate in m.candidates(text):
            pattern = m.shape(candidate)
            counts[pattern] += 1
            example.setdefault(pattern, candidate)
            reply.setdefault(pattern, text)
    return [
        {
            "pattern": p,
            "count": n,
            "example": example[p],
            "example_reply": reply[p],
            "carries": m.carried_types(p),
        }
        for p, n in counts.most_common()
    ]


def reply_shapes(labels: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: collections.Counter = collections.Counter()
    example: dict[str, str] = {}
    for row in labels:
        if row["label"] != "адрес с номером":
            continue
        pattern = m.reply_shape(row["text"], row["spans"])
        counts[pattern] += 1
        example.setdefault(pattern, row["text"])
    total = sum(counts.values())
    return [
        {"pattern": p, "count": n, "share": round(n / total, 4),
         "example": example[p], "carries": ["LOC"]}
        for p, n in counts.most_common()
    ]


def opener_lexicon(labels: list[dict[str, object]], rows: list[str]) -> dict[str, object]:
    """What a dispatcher reply STARTS with, before the address."""
    gold: collections.Counter = collections.Counter()
    for row in labels:
        if row["label"] != "адрес с номером":
            continue
        words = m.tokens(row["text"])
        head: list[str] = []
        for word in words:
            if m.role(word) in ("greet", "addressee", "filler"):
                head.append(word)
            else:
                break
        gold[" ".join(head) if head else "<без вступления>"] += 1
    corpus: collections.Counter = collections.Counter()
    for text in rows:
        words = m.tokens(text)
        if words and m.role(words[0]) in ("greet", "addressee"):
            corpus[words[0]] += 1
    return {
        "gold_address_replies": gold.most_common(),
        "corpus_first_word": corpus.most_common(25),
    }


def tail_lexicon(labels: list[dict[str, object]]) -> dict[str, object]:
    """What comes AFTER the address value: a landmark, a note, a second trip."""
    tails: list[str] = []
    for row in labels:
        if row["label"] != "адрес с номером":
            continue
        low = row["text"].lower()
        last = row["spans"][-1].lower()
        idx = low.rfind(last)
        rest = low[idx + len(last):].strip()
        if rest:
            tails.append(rest)
    words: collections.Counter = collections.Counter()
    for tail in tails:
        words.update(w for w in m.tokens(tail) if len(w) > 2)
    return {"verbatim_tails": tails, "tail_words": words.most_common(30)}


def context_lexicon(labels: list[dict[str, object]]) -> dict[str, object]:
    """What stands immediately BEFORE an address value, and what joins two of
    them. The dispatcher names the street with no preposition far more often
    than with one — that is the shape a marker-less street detector must face."""
    before: collections.Counter = collections.Counter()
    connector: collections.Counter = collections.Counter()
    preposition: collections.Counter = collections.Counter()
    for row in labels:
        if row["label"] != "адрес с номером":
            continue
        low = row["text"].lower()
        cursor = 0
        for k, span in enumerate(row["spans"]):
            idx = low.find(span.lower(), cursor)
            if idx < 0:
                continue
            head = m.tokens(low[cursor:idx])
            before[" ".join(head[-3:]) if head else "<пусто: адрес открывает реплику>"] += 1
            preposition[head[-1] if head and head[-1] in ("на", "по", "до", "в", "к")
                        else "<без предлога>"] += 1
            if k > 0 and head:
                connector[" ".join(head)] += 1
            cursor = idx + len(span)
    return {
        "immediately_before_the_value": before.most_common(30),
        "preposition_in_front_of_the_value": preposition.most_common(),
        "connector_between_two_destinations": connector.most_common(),
    }


def numeral_lexicon(labels: list[dict[str, object]], rows: list[str]) -> dict[str, object]:
    in_spans: collections.Counter = collections.Counter()
    for row in labels:
        if row["label"] != "адрес с номером":
            continue
        for value in row["spans"]:
            in_spans.update(w for w in m.tokens(value) if w in m.CARDINALS)
    after_numeral: collections.Counter = collections.Counter()
    for text in rows:
        words = m.tokens(text)
        for i in range(len(words) - 1):
            if words[i] in m.CARDINALS and words[i + 1] in UNITS_OF_MEASURE:
                after_numeral[words[i + 1]] += 1
    return {
        "cardinals_in_address_values": in_spans.most_common(),
        "units_that_follow_a_numeral_and_veto_a_house_number": after_numeral.most_common(40),
    }


NEGATIVE_FAMILIES: list[tuple[str, str, str]] = [
    ("улица = двор, не адрес", r"\bна улиц[еу]\b|\bпо улиц[еа]м\b|\bулиц[аы]\b(?!\s+[а-яё]+\s)",
     "«улица» стоит без имени и без номера — говорят про двор, погоду, прогулку"),
    ("квартира = жильё", r"\bквартир[аыуе]\b|\bквартирой\b",
     "«квартира» без номера — покупка, аренда, уборка"),
    ("голый подъезд без улицы", r"\b(перв|втор|трет|четв|пят|шест|седьм|восьм|девят|последн|углов)\w*\s+подъезд\b",
     "порядковое + подъезд, но улицы в реплике нет — форма адресного хвоста без адреса"),
    ("проезд = плата", r"\bпроезд\b",
     "«проезд» как оплата поездки, а не тип улицы"),
    ("корпус = деталь", r"\bкорпус\w*\s+(?:чайник|пластик|металл|телефон|устройств)",
     "«корпус» как деталь прибора"),
    ("этаж в рассказе", r"\bэтаж\w*\b",
     "этаж без дома и улицы"),
    ("площадка/площадь", r"\bплощадк\w+|\bплощад[ьи]\b",
     "детская площадка, рекламная площадка, площадь как место события"),
    ("дом = семья, быт", r"\bдом\b|\bдома\b|\bдомой\b",
     "«дом» без номера — быт, «работа дом», «еду домой»"),
    ("число + единица измерения",
     r"\b(?:" + "|".join(sorted(m.CARDINALS)) + r")\s+(?:" + "|".join(sorted(UNITS_OF_MEASURE)) + r")\b",
     "числительное, за которым стоит единица измерения — не номер дома"),
]


def negatives(labels: list[dict[str, object]], rows: list[str]) -> dict[str, object]:
    families: list[dict[str, object]] = []
    gold_neg = [r for r in labels if r["label"] == "не адрес"]
    for name, pattern, why in NEGATIVE_FAMILIES:
        rx = re.compile(pattern)
        gold_hits = [r["text"] for r in gold_neg if rx.search(r["text"])]
        if name == "голый подъезд без улицы":
            # counting every «первый подъезд» would count the addresses too —
            # the family is the form WITHOUT a street, which is the trap.
            corpus_hits = sum(
                1 for t in rows
                if rx.search(t) and not any(True for _ in m.candidates(t))
            )
        else:
            corpus_hits = sum(1 for t in rows if rx.search(t))
        families.append({
            "family": name,
            "why_it_is_a_trap": why,
            "regex": pattern if len(pattern) < 200 else "<см. CARDINALS x UNITS_OF_MEASURE>",
            "count_in_gold_negatives": len(gold_hits),
            "count_in_corpus_41342": corpus_hits,
            "examples": gold_hits[:8],
        })
    street_no_number = [
        {"text": r["text"], "spans": r["spans"]}
        for r in labels
        if r["label"] == "улица без номера"
    ]
    ambiguous = [r["text"] for r in labels if r["label"] == "неоднозначно"]
    return {
        "families": families,
        "street_without_a_house_number": {
            "note": ("улица без дома никого не определяет — это НЕ персональные данные, "
                     "но она несёт всю адресную лексику. Отдельная необязательная колонка."),
            "count": len(street_no_number),
            "values": street_no_number,
        },
        "ambiguous_even_for_a_human": {"count": len(ambiguous), "examples": ambiguous},
    }


CALLED = re.compile(r"\b(?:меня|его|её|ее|тебя|вас|их)?\s*зовут\s+([а-яё]+(?:\s+[а-яё]+)?)")
_MORPH = pymorphy3.MorphAnalyzer()


def is_patronymic(word: str) -> bool:
    """A suffix regex is not enough: «говна», «царевна» and «гранична» all end
    the way a patronymic does. pymorphy3 carries a `Patr` grammeme, and it is
    read across EVERY parse — the first one is arbitrary among ties."""
    if len(word) < 5:
        return False
    # is_known is the half that matters: pymorphy3 PREDICTS Patr for unknown
    # words that merely end the right way — «твиче» scores 1.0 and is not a
    # person. The dictionary reading keeps «палыч» and «иваныч», which are the
    # colloquial patronymics this register actually uses.
    return any(
        "Patr" in parse.tag and parse.is_known for parse in _MORPH.parse(word)
    )


def looks_like_a_name(word: str) -> bool:
    """Only a dictionary Name/Surn reading counts. Without it «зовут» swallowed
    the rest of the sentence — «его зовут босса вашего»."""
    return any(
        ("Name" in parse.tag or "Surn" in parse.tag) and parse.is_known
        for parse in _MORPH.parse(word)
    )


def find_patronymic(words: list[str]) -> int:
    for i, word in enumerate(words):
        if is_patronymic(word):
            return i
    return -1


def name_forms(rows: list[str]) -> dict[str, object]:
    fio: list[str] = []
    name_patr: list[str] = []
    for text in rows:
        words = m.tokens(text)
        i = find_patronymic(words)
        if i < 0:
            continue
        if i >= 2 and len(words) >= 3:
            fio.append(" ".join(words[i - 2:i + 1]))
        if i >= 1:
            name_patr.append(" ".join(words[i - 1:i + 1]))
    called: list[str] = []
    for text in rows:
        mt = CALLED.search(text)
        if mt:
            kept = [w for w in mt.group(1).split() if looks_like_a_name(w)]
            if kept:
                called.append("зовут " + " ".join(kept))
    shapes: collections.Counter = collections.Counter()
    examples: dict[str, str] = {}
    for text in rows:
        words = m.tokens(text)
        if find_patronymic(words) >= 0:
            if len(words) == 3:
                shapes["<фамилия> <имя> <отчество> (вся реплика)"] += 1
                examples.setdefault("<фамилия> <имя> <отчество> (вся реплика)", text)
            elif len(words) == 2:
                shapes["<имя> <отчество> (вся реплика)"] += 1
                examples.setdefault("<имя> <отчество> (вся реплика)", text)
            else:
                shapes["<отчество> внутри фразы"] += 1
                examples.setdefault("<отчество> внутри фразы", text)
    zovut: collections.Counter = collections.Counter()
    zex: dict[str, str] = {}
    for text in rows:
        mt = CALLED.search(text)
        if not mt:
            continue
        kept = [w for w in mt.group(1).split() if looks_like_a_name(w)]
        if not kept:
            continue
        key = "зовут <имя>" if len(kept) == 1 else "зовут <имя> <фамилия>"
        zovut[key] += 1
        # only an example where nothing was dropped, or the example contradicts
        # the pattern it illustrates
        if len(kept) == len(mt.group(1).split()):
            zex.setdefault(key, text)
    for key in list(zovut):
        zex.setdefault(key, "<нет реплики, где разбор совпал целиком>")
    return {
        "note": ("RuDevices — не только диспетчерская: имена приходят из бытовых реплик. "
                 "Отчество — самый надёжный якорь, и он же самый редкий."),
        "shapes": (
            [{"pattern": p, "count": n, "example": examples[p], "carries": ["PERSON"]}
             for p, n in shapes.most_common()]
            + [{"pattern": p, "count": n, "example": zex[p], "carries": ["PERSON"]}
               for p, n in zovut.most_common()]
        ),
        "patronymic_replies": len(name_patr),
        "verbatim_name_patronymic": sorted(set(name_patr))[:60],
        "verbatim_fio": sorted(set(fio))[:40],
        "verbatim_zovut": sorted(set(called))[:40],
    }


def measured_claims(labels: list[dict[str, object]], rows: list[str]) -> dict[str, object]:
    gold = [s for r in labels if r["label"] == "адрес с номером" for s in r["spans"]]
    no_street_word = sum(
        1 for s in gold if not any(w in m.STREET_TYPES for w in m.tokens(s))
    )
    ord_before: collections.Counter = collections.Counter()
    mark_before_num: collections.Counter = collections.Counter()
    for text in rows:
        words = m.tokens(text)
        for i, word in enumerate(words):
            if word not in m.MARKERS:
                continue
            if i > 0 and words[i - 1] in m.ORDINALS:
                ord_before[words[i - 1] + " " + word] += 1
            if i + 1 < len(words) and words[i + 1] in m.CARDINALS:
                mark_before_num[word + " <число>"] += 1
    multi = [r["text"] for r in labels
             if r["label"] == "адрес с номером" and len(r["spans"]) > 1]
    letters = [s for s in gold if any(
        m.classify(w, "NUM") == "LET" for w in m.tokens(s))]
    return {
        "street_named_without_the_word_ulica": {
            "value": no_street_word,
            "of": len(gold),
            "share": round(no_street_word / len(gold), 3),
            "method": "ни одного слова из STREET_TYPES внутри значения",
        },
        "ordinal_before_marker_vs_marker_before_number": {
            "ordinal_then_marker": sum(ord_before.values()),
            "marker_then_cardinal": sum(mark_before_num.values()),
            "top_ordinal_then_marker": ord_before.most_common(12),
            "top_marker_then_cardinal": mark_before_num.most_common(8),
            "scope": "весь корпус, 41342 уникальные реплики",
        },
        "two_destinations_in_one_reply": {
            "value": len(multi),
            "of": sum(1 for r in labels if r["label"] == "адрес с номером"),
            "examples": multi[:12],
        },
        "house_letter_as_a_separate_word": {
            "value": len(letters),
            "of": len(gold),
            "examples": letters[:12],
        },
    }


def main() -> None:
    labels = m.load_labels()
    rows = m.load_corpus()
    gold_values = sum(len(r["spans"]) for r in labels if r["label"] == "адрес с номером")

    doc: dict[str, object] = {
        "_license": {
            "corpus": "SOVA RuDevices (bond005/sova_rudevices)",
            "license": "CC BY 4.0",
            "attribution": "SOVA Dataset / RuDevices, распространяется по CC BY 4.0",
            "verbatim_ok": True,
            "note": ("Тексты в этом файле приведены ДОСЛОВНО и это разрешено лицензией. "
                     "OpenSTT (speech_calls.jsonl) — CC BY-NC 4.0, оттуда сюда не попало "
                     "ни одной строки."),
        },
        "_provenance": {
            "corpus_file": m.CORPUS,
            "corpus_replies_unique": len(rows),
            "labels_file": m.LABELS,
            "labels_replies": len(labels),
            "gold_address_values": gold_values,
            "built_by": "prototype/bench/agentpii3/build_grammar.py",
        },
        "_method": {
            "two_tiers": ("gold — 169 значений, размеченных человеком; "
                          "mined — тот же экстрактор по всем 41342 репликам. "
                          "Слои НЕ складываются."),
            "two_strata": ("marker (400 реплик, перепись) и number-sample (250 из 4805, "
                           "вес 19.22). Доли по ним тоже не складываются — см. "
                           "rudevices_addresses.README.md."),
            "shape_alphabet": {
                "<улица>": "слово имени улицы (не числительное, не тип, не маркер)",
                "<число прописью>": "непрерывный ряд числительных = ОДНО число",
                "<порядковое>": "первый / второй / последний / угловой",
                "<литера>": "одна буква после числа: «сто тридцать восемь а»",
                "улица|шоссе|переулок|…": "слово-тип, приведённое к именительному",
                "подъезд|дом|корпус|квартира|строение|этаж": "маркер, как сказан",
            },
        },
        "value_shapes": {
            "gold_marker_stratum": value_shapes(labels, "marker"),
            "gold_number_sample_stratum": value_shapes(labels, "number-sample"),
            "mined_whole_corpus": mined_shapes(rows),
        },
        "reply_shapes": reply_shapes(labels),
        "lexicon": {
            "openers": opener_lexicon(labels, rows),
            "context_before_the_value": context_lexicon(labels),
            "tails_after_the_address": tail_lexicon(labels),
            "numerals": numeral_lexicon(labels, rows),
            "street_types_seen": sorted(
                {w for r in labels if r["label"] == "адрес с номером"
                 for s in r["spans"] for w in m.tokens(s) if w in m.STREET_TYPES}
            ),
            "settlement_types_seen": sorted(
                {w for r in labels if r["label"] == "адрес с номером"
                 for s in r["spans"] for w in m.tokens(s) if w in m.SETTLEMENT_TYPES}
            ),
            "markers_seen": sorted(
                {w for r in labels if r["label"] == "адрес с номером"
                 for s in r["spans"] for w in m.tokens(s) if w in m.MARKERS}
            ),
            "ordinals_seen": sorted(
                {w for r in labels if r["label"] == "адрес с номером"
                 for s in r["spans"] for w in m.tokens(s) if w in m.ORDINALS}
            ),
            "house_letters_seen": sorted(
                {w for r in labels if r["label"] == "адрес с номером"
                 for s in r["spans"] for w in m.tokens(s)
                 if len(w) == 1 and w in m.HOUSE_LETTERS}
            ),
            "asr_misspellings_inside_gold_values": sorted(
                {w for r in labels if r["label"] == "адрес с номером"
                 for s in r["spans"] for w in m.tokens(s) if w in m.NUM_TYPOS}
            ),
        },
        "negatives": negatives(labels, rows),
        "name_forms": name_forms(rows),
        "measured_claims": measured_claims(labels, rows),
        "register_notes": {
            "no_punctuation": ("В корпусе нет ни одной запятой, точки или заглавной "
                               "буквы — это расшифровка речи. Любая форма отсюда "
                               "приходит в бенчмарк без пунктуации."),
            "no_digits": ("Числа только прописью. Номер дома, подъезд, квартира, "
                          "корпус — всё словами: «сто тридцать восемь а»."),
            "asr_errors_are_part_of_the_register": (
                "Ошибки распознавания приходят вместе с формой и их нельзя чинить: "
                "«четвёрьый подъезд», «девяеносто семь», «одинадцать», «едим на кирова "
                "пять», «бумашевская», «абазисная». Это ровно тот вход, который "
                "получает шлюз от речевого агента."),
            "street_type_word_is_usually_absent": (
                "Улицу называют голым именем: «барышникова шестьдесят три». Слово "
                "«улица» стоит в меньшинстве значений."),
            "no_preposition_in_front": (
                "159 из 169 значений открываются без предлога. Правило «маркерless "
                "улица требует предлога» на этом регистре не сработает."),
            "types_absent_from_this_corpus": [
                "PHONE (телефон вслух не диктуют — «номер телефона» встречается 9 раз "
                "и ни разу цифрами)",
                "SNILS", "INN", "CARD", "PASSPORT", "EMAIL", "DATE рождения",
            ],
        },
        "generator_recipe": {
            "intent": ("Как из этого собирать v3: форма берётся из value_shapes "
                       "(gold_marker_stratum — веса), обёртка — из reply_shapes, "
                       "лексика вступления и хвоста — из lexicon."),
            "draw_value_shape_from": "value_shapes.gold_marker_stratum[].share",
            "draw_reply_shape_from": "reply_shapes[].share",
            "must_hold": [
                "две трети значений — без слова-типа улицы",
                "порядковое стоит ПЕРЕД маркером подъезда (81 против 36 обратных)",
                "литера дома — отдельным словом после числа, 18 из 169",
                "каждая десятая реплика несёт ДВЕ точки маршрута",
                "у трети реплик перед адресом нет вообще ничего",
            ],
            "negatives_must_come_from": "negatives.families[].examples (дословно из корпуса)",
        },
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
