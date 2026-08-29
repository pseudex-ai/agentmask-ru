"""Лестница шума, РАЗОБРАННАЯ ПО ТИПАМ. Инструмент, а не второй прибор.

`eval_noise_ladder.py` печатает одну полноту на ступень, и это число —
среднее по девяти типам сразу. Оно скрывает ровно то, ради чего лестницу
строили: типы ломаются на РАЗНЫХ ступенях и по разным причинам. Телефон и
СНИЛС держатся до конца (их держит контрольная сумма и форма), NAME проседает
на опечатке (словарь имён точный), а LOC обваливается там же — потому что
улица ищется точным вхождением в словарь и одна выпавшая буква выключает
поиск целиком.

Усреднённое число падало и не говорило, ЧТО чинить. Разбор по типам называет
виновника одной строкой.

Ступени, порча и подсчёт — те же самые, импортированы из `eval_noise_ladder`:
две копии лестницы разошлись бы на первой же правке, и тогда «до» и «после»
мерили бы разными линейками.

    python3 bench/eval_noise_by_type.py dataset.json
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.eval_noise_ladder import RUNGS, _is_bare_toponym, load  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()
    rows = load(args.dataset)
    if not rows:
        print("в наборе нет размеченных значений — нечего мерить")
        return 1

    types = sorted({span["type"] for row in rows for span in row["spans"]})
    # Полнота по (ступень, тип): найдено и всего.
    tally: dict[tuple[int, str], list[int]] = {
        (rung, kind): [0, 0] for rung in range(len(RUNGS)) for kind in types
    }
    for rung, (_, ladder) in enumerate(RUNGS):
        # Своё зерно на ступень — иначе порча зависела бы от порядка ступеней,
        # и сравнение «до/после» поехало бы от добавления одной строки.
        rng = random.Random(args.seed)
        for row in rows:
            text, spans = row["text"], row["spans"]
            for step in ladder:
                text, spans = step(text, spans, rng)
            detected = [(s.start, s.end) for s in detector.detect(text)]
            for span in spans:
                # ГОЛЫЕ ГОРОДА НЕ СЧИТАЮТСЯ, как и в общей лестнице. Набор
                # размечает «Москва» как LOC; продукт их намеренно не
                # маскирует — город никого не идентифицирует. Считая их
                # пропусками, таблица обвиняла бы правило, которое работает как
                # задумано, и прятала бы цену настоящей поломки улиц за ним.
                if _is_bare_toponym(span, text):
                    continue
                cell = tally[(rung, span["type"])]
                cell[1] += 1
                cell[0] += any(a < span["end"] and span["start"] < b
                               for a, b in detected)

    head = "".join(f"{name.split()[0]:>8}" for name, _ in RUNGS)
    print(f"{'ТИП':<10}{'ВСЕГО':>7}{head}")
    print("-" * (17 + 8 * len(RUNGS)))
    for kind in types:
        total = tally[(0, kind)][1]
        cells = "".join(
            f"{(tally[(rung, kind)][0] / tally[(rung, kind)][1] * 100):>7.0f}%"
            if tally[(rung, kind)][1] else f"{'—':>8}"
            for rung in range(len(RUNGS))
        )
        print(f"{kind:<10}{total:>7}{cells}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
