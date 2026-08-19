"""Лестница шума: как падает полнота, когда текст пишут как в жизни.

ЗАЧЕМ ОТДЕЛЬНЫЙ ПРИБОР. Наши наборы написаны аккуратно — заглавные на месте,
точки расставлены, слова целые. Живой чат выглядит иначе: «игрь павлв
позвони», «ул ленна 14 кв 3». Фаззер регистров уже проверяет отдельные
написания, но он даёт ДА/НЕТ на горстке значений и не отвечает на вопрос,
который решает: НА КАКОЙ СТУПЕНИ шума детекция ломается.

ЛЕСТНИЦА, А НЕ ОДНА ТОЧКА. Один замер на «грязном» тексте — это число без
производной: непонятно, мы у обрыва или далеко от него. Ступени добавляются по
одной и в том порядке, в каком они встречаются в жизни:

    0. как написано в наборе
    1. + строчными
    2. + без пунктуации
    3. + одна опечатка в слове
    4. + две опечатки

Каждая ступень включает предыдущие, поэтому падение между соседними ступенями
и есть цена именно этого вида шума.

ОПЕЧАТКА ДЕЛАЕТСЯ ТОЛЬКО В БУКВАХ. Удалить цифру из телефона или из СНИЛС —
значит сломать контрольную сумму и померить не устойчивость, а нашу же
проверку числа: такой «пропуск» ловиться и не должен. Тот же урок стоил
первой версии фаззера сорока ложных тревог.

СОПОСТАВЛЕНИЕ ПО ПЕРЕСЕЧЕНИЮ, НЕ ПО РАВЕНСТВУ. Шум меняет само значение, так
что искомое «Иванов» после порчи выглядит как «Ивнов» — сравнивать найденное с
исходным эталоном бессмысленно. Спан считается пойманным, если он накрывает
позицию, где значение стояло: это ровно тот вопрос, который важен — дошло ли до
модели то, что мы обязаны были закрыть.

    python3 bench/eval_noise_ladder.py --dataset dataset.json --per-rung 400
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

_LETTER = re.compile(r"[А-Яа-яЁёA-Za-z]")
_PUNCT = str.maketrans("", "", ".,;:!?()«»\"'")


def lowercase(text: str, spans: list[dict], rng: random.Random) -> tuple[str, list[dict]]:
    """1:1 по длине, поэтому позиции эталона не сдвигаются."""
    return text.lower(), spans


# Знаки, которые НЕСУТ значение внутри самого значения, а не разделяют фразу.
# Почта без точки — не почта, и её никто так не пишет: убрав точку в
# «gmail.com», прибор мерил бы не устойчивость, а собственную порчу. Тот же
# класс ошибки, что удаление цифры из числа с контрольной суммой.
_KEEPS_ITS_PUNCT = frozenset({"EMAIL", "URL", "IP", "SECRET"})


def strip_punct(text: str, spans: list[dict], rng: random.Random) -> tuple[str, list[dict]]:
    """Пунктуация УДАЛЯЕТСЯ, значит позиции едут — пересчитываем их честно."""
    protected = set()
    for span in spans:
        if span["type"] in _KEEPS_ITS_PUNCT:
            protected.update(range(span["start"], span["end"]))
    out: list[str] = []
    shift = [0] * (len(text) + 1)
    for index, char in enumerate(text):
        shift[index] = len(out)
        if index in protected or char.translate(_PUNCT):
            out.append(char)
    shift[len(text)] = len(out)
    moved = [{**span, "start": shift[span["start"]], "end": shift[span["end"]]}
             for span in spans]
    return "".join(out), moved


def _typo(word: str, rng: random.Random) -> str:
    """Одна правка внутри слова: выпавшая буква или переставленная пара.

    Только буквы. Цифра, вынутая из номера с контрольной суммой, делает его
    не «зашумлённым», а недействительным — и тогда прибор меряет валидатор,
    а не устойчивость.
    """
    positions = [i for i, char in enumerate(word) if _LETTER.match(char)]
    if len(positions) < 3:
        return word
    inner = positions[1:-1] or positions
    at = rng.choice(inner)
    if rng.random() < 0.5:
        return word[:at] + word[at + 1:]
    if at + 1 < len(word):
        return word[:at] + word[at + 1] + word[at] + word[at + 2:]
    return word[:at] + word[at + 1:]


def typos(count: int):
    """Опечатки ВНУТРИ значений: шум за пределами спана ничего не проверяет."""
    def apply(text: str, spans: list[dict], rng: random.Random) -> tuple[str, list[dict]]:
        pieces, moved, cursor, drift = [], [], 0, 0
        for span in sorted(spans, key=lambda s: s["start"]):
            pieces.append(text[cursor:span["start"]])
            value = text[span["start"]:span["end"]]
            damaged = value
            for _ in range(count):
                words = damaged.split(" ")
                index = rng.randrange(len(words))
                words[index] = _typo(words[index], rng)
                damaged = " ".join(words)
            start = span["start"] + drift
            pieces.append(damaged)
            drift += len(damaged) - len(value)
            moved.append({**span, "start": start, "end": start + len(damaged)})
            cursor = span["end"]
        pieces.append(text[cursor:])
        return "".join(pieces), moved
    return apply


RUNGS = [
    ("0 как в наборе", []),
    ("1 строчными", [lowercase]),
    ("2 + без пунктуации", [lowercase, strip_punct]),
    ("3 + одна опечатка", [lowercase, strip_punct, typos(1)]),
    ("4 + две опечатки", [lowercase, strip_punct, typos(2)]),
]


_STREET_MARK = re.compile(
    r"\b(ул|улиц\w*|пр-?кт|проспект\w*|пер|переул\w*|б-р|бульвар\w*|ш|шоссе|мкр|"
    r"микрорайон\w*|д|дом|кв|квартир\w*|корп|стр)\b", re.IGNORECASE)


def _is_bare_toponym(span: dict, text: str) -> bool:
    """Голый город: одно слово, без номера дома и без слова-типа улицы."""
    if span["type"] != "LOC":
        return False
    value = text[span["start"]:span["end"]]
    return (len(value.split()) == 1
            and not any(c.isdigit() for c in value)
            and not _STREET_MARK.search(value))


def load(path: str) -> list[dict]:
    """Наборы размечены ЗНАЧЕНИЯМИ, не позициями, — позиция ищется в тексте.

    Каждое значение берётся ОДИН раз и слева направо, иначе два одинаковых
    имени в предложении дали бы один и тот же спан дважды и завысили полноту.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("cases", payload.get("items", []))
    out = []
    for row in rows:
        text = row.get("text") or row.get("message") or ""
        spans, cursor = [], {}
        for entity in row.get("entities") or []:
            value = entity.get("value") or ""
            if not value:
                continue
            at = text.find(value, cursor.get(value, 0))
            if at < 0:
                continue
            cursor[value] = at + len(value)
            spans.append({"start": at, "end": at + len(value),
                          "type": entity.get("type") or "?"})
        if text and spans:
            out.append({"text": text, "spans": sorted(spans, key=lambda s: s["start"])})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--per-rung", type=int, default=0, help="0 = весь набор")
    parser.add_argument("--seed", type=int, default=20260819)
    parser.add_argument("--dump", type=int, default=12)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()
    rows = load(args.dataset)
    if not rows:
        print("в наборе нет размеченных значений — нечего мерить")
        return 1
    if args.per_rung:
        rows = rows[:args.per_rung]

    print(f"случаев: {len(rows)}   значений: {sum(len(r['spans']) for r in rows)}\n")
    print(f"{'СТУПЕНЬ':<22}{'НАЙДЕНО':>10}{'ВСЕГО':>8}{'ПОЛНОТА':>10}{'ЦЕНА':>9}"
          f"{'БЕЗ ГОРОДОВ':>13}")
    print("-" * 69)

    previous = None
    for name, ladder in RUNGS:
        rng = random.Random(args.seed)
        found = total = found_pii = total_pii = 0
        misses: list[tuple[str, str]] = []
        for row in rows:
            text, spans = row["text"], row["spans"]
            for step in ladder:
                text, spans = step(text, spans, rng)
            detected = [(s.start, s.end) for s in detector.detect(text)]
            for span in spans:
                total += 1
                hit = any(a < span["end"] and span["start"] < b for a, b in detected)
                found += hit
                # ВТОРАЯ КОЛОНКА БЕЗ ГОЛЫХ ТОПОНИМОВ. Набор размечает «Москва»
                # и «Екатеринбург» как LOC; продукт их намеренно НЕ маскирует —
                # город никого не идентифицирует, это записанная позиция и
                # отдельная правка. Считая их пропусками, прибор обвиняет за
                # правило, которое работает как задумано.
                if not _is_bare_toponym(span, text):
                    total_pii += 1
                    found_pii += hit
                if not hit and len(misses) < args.dump:
                    misses.append((span["type"], text[span["start"]:span["end"]]))
        rate = found / total * 100 if total else 0.0
        cost = "" if previous is None else f"{rate - previous:+.1f}"
        print(f"{name:<22}{found:>10}{total:>8}{rate:>9.1f}%{cost:>9}"
              f"{(found_pii / total_pii * 100) if total_pii else 0.0:>12.1f}%")
        previous = rate
        if misses and ladder:
            shown = ", ".join(f"[{kind}] {value!r}" for kind, value in misses[:6])
            print(f"{'':<22}пропущено: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
