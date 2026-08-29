"""Метаморфные отношения на адресах и именах: инвариант, а не разметка.

ЗАЧЕМ ЕЩЁ ОДИН ПРИБОР. Наши наборы меряют полноту на том, что в них написано, и
корпус AgentPII порождает адрес ОДНОЙ строкой `{город}, {улица}, д. {дом}, кв.
{кв}`. По ней мерился круг 97.9%, и число не было ложью — оно отвечало на более
узкий вопрос, чем мы задавали. Метаморфное отношение снимает эту зависимость:
оно не требует новой разметки и не спрашивает «что в наборе», оно спрашивает
«переживает ли правило переписывание, которое живой человек делает не задумываясь».

Формулировка инварианта: если носитель языка называет две строки ОДНИМ адресом,
детектор обязан найти его в обеих. Отношение, которое ломается, называет не
пример, а КЛАСС — и класс чинится один раз.

Отношения выбраны по тому, что реально встречается в русском чате и в
расшифровках звонков, а не по тому, что удобно порождать:

  сокращение маркера      «улица» -> «ул.» / «ул»        письмо с телефона
  падеж маркера           «улица» -> «улицу» / «улице»   разговорная речь
  маркер дома             «д. 14» -> «дом 14» / «14»     как придётся
  номер словами           «14» -> «четырнадцать»         РАСШИФРОВКА ЗВОНКА
  снятая пунктуация       запятые прочь                  чат
  строчные буквы          регистр прочь                  чат
  склейка маркера         «д. 5 кв. 12» -> «д.5кв12»     письмо с телефона
  опечатка                одна замена буквы              всегда

Оценивается ДВА числа, и они не сливаются: спан найден хотя бы частично
(полнота) и найден целиком (покрытие). Разница между ними — это утёкший хвост,
и она была бы невидима под одним числом.

    python3 bench/eval_metamorphic.py
    python3 bench/eval_metamorphic.py --dump 20     # показать поломки
"""
import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, ".")
from testkit import load_dev_bundle

load_dev_bundle()

from pseudex.detect_all import Detector

CORPUS = Path("bench/agentpii/corpus.json")

_UNITS = {1: "один", 2: "два", 3: "три", 4: "четыре", 5: "пять", 6: "шесть",
          7: "семь", 8: "восемь", 9: "девять", 10: "десять", 11: "одиннадцать",
          12: "двенадцать", 13: "тринадцать", 14: "четырнадцать",
          15: "пятнадцать", 16: "шестнадцать", 17: "семнадцать",
          18: "восемнадцать", 19: "девятнадцать"}
_TENS = {2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
         6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"}


def _spell(n: int) -> str:
    """Число прописью — так его пишет расшифровка звонка.

    Ограничено сотней намеренно: номера домов и квартир выше почти не
    встречаются в речи целым словом, а точность выше здесь ничего не меряет.
    """
    if n in _UNITS:
        return _UNITS[n]
    if n < 100:
        tens, rest = divmod(n, 10)
        return _TENS[tens] + (f" {_UNITS[rest]}" if rest else "")
    return str(n)


def spell_numbers(text: str) -> str:
    return re.sub(r"\b(\d{1,2})\b", lambda m: _spell(int(m.group(1))), text)


def abbreviate(text: str) -> str:
    for full, short in (("улица", "ул."), ("улицу", "ул."), ("улице", "ул."),
                        ("проспект", "пр-кт"), ("переулок", "пер."),
                        ("бульвар", "б-р"), ("шоссе", "ш."),
                        ("набережная", "наб."), ("квартира", "кв."),
                        ("дом", "д.")):
        text = re.sub(rf"\b{full}\b", short, text, flags=re.IGNORECASE)
    return text


def expand(text: str) -> str:
    for short, full in ((r"ул\.?", "улица"), (r"пр-кт", "проспект"),
                        (r"пер\.?", "переулок"), (r"б-р", "бульвар"),
                        (r"наб\.?", "набережная"), (r"кв\.?", "квартира"),
                        (r"д\.?", "дом")):
        text = re.sub(rf"\b{short}(?=\s)", full, text, flags=re.IGNORECASE)
    return text


def oblique_marker(text: str) -> str:
    """«на улицу Ленина», «по улице Ленина» — как говорят, а не как пишут."""
    return re.sub(r"\bулица\b", "улице", text, flags=re.IGNORECASE)


def house_word(text: str) -> str:
    return re.sub(r"\bд\.\s*", "дом ", text, flags=re.IGNORECASE)


def house_number_sign(text: str) -> str:
    return re.sub(r"\bд\.\s*", "№ ", text, flags=re.IGNORECASE)


def drop_house_marker(text: str) -> str:
    return re.sub(r"\bд\.\s*(?=\d)", "", text, flags=re.IGNORECASE)


def depunctuate(text: str) -> str:
    return text.replace(",", "").replace(".", "")


def lower(text: str) -> str:
    return text.lower()


def glue(text: str) -> str:
    """«д. 5 кв. 12» -> «д.5кв12» — как набирают на телефоне."""
    text = re.sub(r"\b(д|кв|к|корп|стр)\.?\s+(?=\d)", r"\1", text,
                  flags=re.IGNORECASE)
    return re.sub(r"(\d)\s+(кв|к|корп|стр)\b", r"\1\2", text, flags=re.IGNORECASE)


def typo(rng: random.Random):
    """Одна замена буквы в самом длинном слове — там, где она вероятнее всего."""
    def apply(text: str) -> str:
        words = [(i, w) for i, w in enumerate(re.findall(r"\w+|\W+", text))
                 if w.isalpha() and len(w) >= 5]
        if not words:
            return text
        parts = re.findall(r"\w+|\W+", text)
        idx = max(words, key=lambda p: len(p[1]))[0]
        w = parts[idx]
        p = rng.randrange(1, len(w) - 1)
        parts[idx] = w[:p] + ("о" if w[p] != "о" else "а") + w[p + 1:]
        return "".join(parts)
    return apply


def _relations(rng: random.Random) -> list[tuple[str, object]]:
    return [
        ("сокращение маркера",    abbreviate),
        ("развёрнутый маркер",    expand),
        ("падеж маркера",         oblique_marker),
        ("«дом» словом",          house_word),
        ("маркер дома «№»",       house_number_sign),
        ("без маркера дома",      drop_house_marker),
        ("номер прописью",        spell_numbers),
        ("снятая пунктуация",     depunctuate),
        ("строчными",             lower),
        ("склейка маркеров",      glue),
        ("одна опечатка",         typo(rng)),
    ]


def _found(detector: Detector, text: str, needle: str) -> tuple[bool, bool]:
    """Возвращает (найден хотя бы частично, найден целиком)."""
    at = text.find(needle)
    if at < 0:
        return (False, False)
    lo, hi = at, at + len(needle)
    spans = [(s.start, s.end) for s in detector.detect(text)]
    partial = any(a < hi and lo < b for a, b in spans)
    whole = any(a <= lo and hi <= b for a, b in spans)
    return (partial, whole)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=int, default=6)
    parser.add_argument("--types", default="LOC,NAME")
    parser.add_argument("--seed", type=int, default=20260829)
    args = parser.parse_args()

    wanted = set(args.types.split(","))
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    detector = Detector()
    rng = random.Random(args.seed)

    # Одно упоминание на ЗНАЧЕНИЕ, не на случай: корпус повторяет один адрес в
    # нескольких регистрах, и без этого частая форма получила бы лишний вес.
    seen: dict[str, set[str]] = defaultdict(set)
    items: list[tuple[str, str, str]] = []
    for case in payload["cases"]:
        joined = " ".join(m.get("content", "") for m in case["messages"])
        for entry in case.get("pii", []):
            kind, value = entry.get("type"), entry.get("value") or ""
            if kind not in wanted or not value or value in seen[kind]:
                continue
            if value not in joined:
                continue
            seen[kind].add(value)
            items.append((kind, value, joined))

    print(f"уникальных значений: " +
          ", ".join(f"{k} {len(v)}" for k, v in sorted(seen.items())) + "\n")

    rows, broken = [], []
    for name, relation in _relations(rng):
        stat = defaultdict(lambda: [0, 0, 0])   # применимо, полнота, покрытие
        for kind, value, text in items:
            rewritten = relation(value)
            if rewritten == value:
                continue                        # отношение не применимо
            partial, whole = _found(detector, text.replace(value, rewritten),
                                    rewritten)
            s = stat[kind]
            s[0] += 1
            s[1] += partial
            s[2] += whole
            if not partial and len(broken) < args.dump * 4:
                broken.append((name, kind, value, rewritten))
        rows.append((name, dict(stat)))

    kinds = sorted(wanted)
    head = f"{'ОТНОШЕНИЕ':<24}" + "".join(
        f"{k + ' полн':>12}{'покр':>7}" for k in kinds)
    print(head)
    print("-" * len(head))
    for name, stat in rows:
        line = f"{name:<24}"
        for k in kinds:
            n, partial, whole = stat.get(k, [0, 0, 0])
            if not n:
                line += f"{'—':>12}{'—':>7}"
            else:
                line += f"{partial / n * 100:>11.0f}%{whole / n * 100:>6.0f}%"
        print(line)

    if broken:
        print(f"\nСЛОМАНО (первые {args.dump}):")
        for name, kind, before, after in broken[:args.dump]:
            print(f"  [{name}] {kind}")
            print(f"      было : {before!r}")
            print(f"      стало: {after!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
