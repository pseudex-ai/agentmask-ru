"""Где обрезать словарь улиц ГАР — и чем именно платит каждый вариант.

ВОПРОС НЕ В РАЗМЕРЕ. Все 165 600 названий жмутся меньше чем в мегабайт, так
что «влезет ли» — не тот вопрос. Словарь улиц работает КАЛИТКОЙ: запись в нём
значит «слово такого вида может называть улицу», и хвост реестра — это обычные
русские слова, каждое из которых называет одну улицу в одной деревне. Чем
длиннее хвост, тем больше обычной речи проходит через калитку.

ПОЭТОМУ ДВЕ КОЛОНКИ, А НЕ ОДНА. «Покрытие» — доля всех улиц России, чьё имя
есть в словаре: сколько мы УВИДИМ. «Обычных слов» — сколько записей pymorphy3
знает как рядовое слово без чтения имени, фамилии или топонима: сколько мы
рискуем закрыть лишнего. Они растут вместе, и цена отсечки — это разница между
их приростами, а не одно число.

СЧИТАЕМ ПО ОБЪЕКТАМ, НЕ ПО НАЗВАНИЯМ. «Центральная» — одно название и двадцать
тысяч улиц; «Тупиковый» — одно название и одна улица. Доля названий ответила бы
на вопрос, которого никто не задавал.

    python3 bench/eval_gar_cut.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pseudex.morph import MORPH  # noqa: E402

_TSV = Path(__file__).resolve().parents[1] / "licensing" / "data" / "gar_streets.tsv"
_CUTS = (1, 2, 4, 8, 12, 20, 40, 80, 200, 600, 2000)
# Чтения, при которых слово УЖЕ не рядовое: имя, фамилия, отчество, топоним.
_NAMEY = frozenset({"Name", "Surn", "Patr", "Geox"})


def _usable(name: str) -> bool:
    """Тот же фильтр, что и в `licensing/pack.py`, иначе кривая мерит не то."""
    return (len(name) >= 4 and " " not in name and "-" not in name
            and not any(char.isdigit() for char in name))


def _is_plain_word(word: str) -> bool:
    """Слово, которое морфология знает как рядовое — и только так."""
    parses = MORPH.parse(word)
    known = [parse for parse in parses if parse.is_known]
    if not known:
        return False
    return all(not (_NAMEY & set(parse.tag.grammemes)) for parse in known)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tsv", type=Path, default=_TSV)
    args = parser.parse_args()

    rows: list[tuple[int, str]] = []
    for line in args.tsv.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        count, _, name = line.partition("\t")
        rows.append((int(count), name.strip().lower()))

    objects_all = sum(count for count, _ in rows)
    usable = [(count, name) for count, name in rows if _usable(name)]
    print(f"названий в реестре: {len(rows)}   улиц: {objects_all}")
    print(f"однословных пригодных: {len(usable)}   "
          f"улиц под ними: {sum(c for c, _ in usable)}\n")

    print(f"{'ОТСЕЧКА':>8}{'НАЗВАНИЙ':>10}{'ПОКРЫТИЕ':>11}{'ОБЫЧНЫХ СЛОВ':>15}"
          f"{'ИХ ДОЛЯ':>10}")
    print("-" * 54)
    plain_cache: dict[str, bool] = {}
    for cut in _CUTS:
        kept = [(count, name) for count, name in usable if count >= cut]
        covered = sum(count for count, _ in kept)
        plain = 0
        for _, name in kept:
            if name not in plain_cache:
                plain_cache[name] = _is_plain_word(name)
            plain += plain_cache[name]
        print(f"{cut:>8}{len(kept):>10}{covered / objects_all * 100:>10.1f}%"
              f"{plain:>15}{(plain / len(kept) * 100) if kept else 0:>9.1f}%")

    print("\nсамые частые записи, которые морфология считает рядовым словом:")
    shown = 0
    for count, name in usable:
        if plain_cache.get(name) and shown < 25:
            print(f"  {count:>6}  {name}")
            shown += 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
