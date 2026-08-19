"""Точность на живой речи: сколько защищённых значений НЕ персональные данные.

МЕРИМ ВОЛТ, А НЕ ТРАФИК. Маскирование дедуплицирует: 993 диалога и 6994
сообщения свернулись в ~1300 значений. Разметить семь тысяч сообщений нельзя,
а тысячу триста значений — можно, и это ровно тот список, который клиент видит
у себя в журнале. Здесь нет разметки и она не нужна: вопрос «человек ли это»
задаётся значению, а не предложению.

ТРИ СЛОЯ, ОТ БЕСПЛАТНОГО К ДОРОГОМУ:

  1. Типы с контрольной суммой (PHONE, INN, SNILS, CARD, EMAIL) не проверяются
     вовсе — там точность почти по определению, и тратить на них глаза значит
     не смотреть на то, что действительно ломается.
  2. NAME и LOC ранжируются сигналами, которых в данных уже достаточно:
     частота по диалогам, регистр, морфология, цифры. Разметки они не требуют.
  3. Глаза — только по верхушке очереди.

ЧАСТОТА ПО ДОКУМЕНТАМ — ГЛАВНЫЙ СИГНАЛ И ОН БЕСПЛАТНЫЙ. Имя человека живёт в
одном-двух диалогах; «Бут», «Оч», «Всё» — в десятках. Она же сортирует очередь
по УЩЕРБУ: фальшивый человек, всплывший сорок раз, это сорок искажённых
сообщений, а разовый — одно.

ЧИСЛО ВЗВЕШЕНО ПО СРАБАТЫВАНИЯМ, НЕ ПО ЗАПИСЯМ. Двадцать мусорных имён из 262
это 8% списка — но если каждое всплывало по тридцать раз, для читающего текст
это совсем другая величина. Вес берётся из журнала аудита, где записано каждое
применение.

    docker cp pseudex:/data/vault.db /tmp/v.db
    docker cp pseudex:/data/audit.db /tmp/a.db
    python3 bench/eval_vault_precision.py --vault /tmp/v.db --audit /tmp/a.db \\
        --corpus dialogues.jsonl
"""

import argparse
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pseudex import _morph_compat  # noqa: F401,E402  ставит pymorphy3 под именем pymorphy2
import pymorphy3  # noqa: E402

_MORPH = pymorphy3.MorphAnalyzer()

# Проверяются только эти. Остальные типы гейтятся контрольной суммой или формой.
_REVIEWED = ("NAME", "LOC")

# Слова, которые ВВОДЯТ место. Список короткий и явный нарочно: это эвристика
# очереди на просмотр, а не распознаватель — прозрачность тут важнее полноты.
_PLACE_MARK = re.compile(
    r"\b(ул|улиц\w*|пр-?кт|проспект\w*|пер|переул\w*|б-р|бульвар\w*|ш|шоссе|"
    r"мкр|микрорайон\w*|д|дом|кв|квартир\w*|г|город\w*|пос|посёл\w*|посел\w*|"
    r"дер|деревн\w*|село|литер\w*|корп\w*|стр)\b",
    re.IGNORECASE,
)


def names_of(value: str) -> list[str]:
    return [part for part in re.split(r"[\s.,]+", value) if part]


def looks_like_person(value: str) -> bool:
    """Хоть одна часть читается морфологией как имя, фамилия или отчество.

    Проверяются ВСЕ разборы, а не лучший: «марину» даёт мужское «марин» и
    женское «марина» с одинаковым весом, и брать первый — это подбрасывать
    монетку (тот же урок, что в names.py).
    """
    for part in names_of(value):
        for parse in _MORPH.parse(part):
            if {"Name", "Surn", "Patr"} & set(parse.tag.grammemes):
                return True
    return False


def is_ordinary_word(value: str) -> bool:
    """Всё значение — обычные слова, знакомые словарю, и ни одно не имя."""
    parts = names_of(value)
    if not parts:
        return False
    known = all(any(p.is_known for p in _MORPH.parse(part)) for part in parts)
    return known and not looks_like_person(value)


def written_forms(value: str, corpus: str) -> tuple[int, bool]:
    """Сколько раз ПЕРВАЯ часть значения встречена в тексте и была ли заглавной.

    Ищется написанное, а не каноническое. Волт хранит «Лена», а клиент писал
    «Лены» — поиск канонического вида по тексту не находил ничего и молча
    докладывал «ни разу не с заглавной» про имя, которое в корпусе с заглавной
    всегда. Сигнал, который срабатывает от НЕНАХОЖДЕНИЯ, обвиняет тем громче,
    чем хуже ищет.
    """
    head = names_of(value)[:1]
    if not head or not corpus:
        return 0, True
    stem = head[0][:-1] if len(head[0]) > 4 else head[0]
    found = list(re.finditer(r"\b" + re.escape(stem) + r"\w*", corpus, re.IGNORECASE))
    if not found:
        return 0, True          # не нашли — молчим, а не обвиняем
    return len(found), any(m.group(0)[:1].isupper() for m in found)


def suspicion(value: str, kind: str, documents: int, capitalized: bool) -> list[str]:
    """Почему это, возможно, не персональные данные. Пустой список — вопросов нет."""
    reasons: list[str] = []
    stripped = value.strip()
    if kind == "NAME":
        if any(ch.isdigit() for ch in stripped):
            reasons.append("содержит цифры")
        if len(stripped) <= 3:
            reasons.append("короче четырёх букв")
        if is_ordinary_word(stripped):
            reasons.append("обычное слово, морфология не видит имени")
        if not capitalized and len(stripped) > 3:
            reasons.append("ни разу не написано с заглавной")
    else:
        if not _PLACE_MARK.search(stripped) and not any(c.isdigit() for c in stripped):
            if len(names_of(stripped)) == 1:
                reasons.append("одно слово без признака места и без номера")
    # Частота НЕ ставит диагноз сама — она усиливает уже возникшее подозрение.
    # Фамилия постоянного клиента тоже встречается в десяти диалогах, и записать
    # её в мусор за популярность значит выкинуть ровно тех, кого защищаем.
    if reasons and documents >= 5:
        reasons.append(f"встречается в {documents} диалогах")
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True)
    parser.add_argument("--audit", default="")
    parser.add_argument("--corpus", default="")
    parser.add_argument("--org", default="default")
    parser.add_argument("--dump", type=int, default=30)
    args = parser.parse_args()

    vault = sqlite3.connect(args.vault)
    rows = list(vault.execute(
        "SELECT canonical, entity_type, token FROM tokens WHERE customer=?",
        (args.org,)))

    weight: collections.Counter[str] = collections.Counter()
    if args.audit:
        audit = sqlite3.connect(args.audit)
        for token, count in audit.execute(
                "SELECT token, COUNT(*) FROM events WHERE customer=? GROUP BY token",
                (args.org,)):
            weight[token] = count

    corpus_text = ""
    per_document: list[str] = []
    if args.corpus:
        for line in Path(args.corpus).read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                text = " ".join(m.get("text") or "" for s in record.get("sessions", [])
                                for m in s.get("messages", []))
                per_document.append(text)
        corpus_text = "\n".join(per_document)
    folded = corpus_text.casefold()

    by_type: collections.Counter[str] = collections.Counter()
    for _, kind, _ in rows:
        by_type[kind] += 1
    print("защищено значений по типам:",
          ", ".join(f"{k} {v}" for k, v in sorted(by_type.items())))
    print(f"срабатываний в журнале: {sum(weight.values())}\n")

    flagged: list[tuple[int, str, str, list[str]]] = []
    checked = checked_weight = bad_weight = 0
    for canonical, kind, token in rows:
        if kind not in _REVIEWED:
            continue
        checked += 1
        applied = weight.get(token, 1)
        checked_weight += applied
        low = canonical.casefold()
        documents = sum(1 for t in per_document if low in t.casefold()) if per_document else 0
        _, capitalized = written_forms(canonical, corpus_text)
        reasons = suspicion(canonical, kind, documents, capitalized)
        if reasons:
            bad_weight += applied
            flagged.append((applied, kind, canonical, reasons))

    if not checked:
        print("нечего проверять")
        return 1

    print(f"под вопросом: {len(flagged)}/{checked} значений = "
          f"{len(flagged) / checked * 100:.1f}% списка")
    print(f"ВЗВЕШЕННО по срабатываниям: {bad_weight}/{checked_weight} = "
          f"{bad_weight / checked_weight * 100:.1f}% защит поставлены не на ПД")
    print(f"ТОЧНОСТЬ (нижняя оценка, NAME+LOC): "
          f"{(checked_weight - bad_weight) / checked_weight * 100:.1f}%\n")

    print(f"--- ОЧЕРЕДЬ НА ПРОСМОТР, по ущербу ({min(args.dump, len(flagged))} из {len(flagged)}) ---")
    for applied, kind, canonical, reasons in sorted(flagged, reverse=True)[:args.dump]:
        print(f"  {applied:4}x  [{kind}] {canonical!r}")
        print(f"        {'; '.join(reasons)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
