"""Лестница шума С РАЗБИВКОЙ ПО ТИПАМ и с отдельной колонкой для NER-модели.

ЗАЧЕМ ОТДЕЛЬНО ОТ eval_noise_ladder.py. Тот печатает одну цифру на ступень, и
«на грязном входе теряем четверть» было известно — а ЧТО теряем, нет. Разрез по
типам отвечает на вопрос, куда имеет смысл ставить модель, и ответ оказался
узким: всё, у чего есть контрольная сумма или жёсткий формат (СНИЛС, ИНН, карта,
телефон, почта, паспорт, дата), держит 100% на любой ступени. Правила там не
слабость, а превосходство: сумма по mod 101 — доказательство, а не догадка, и
модель добавила бы туда только ложные срабатывания. Падают ровно два типа.

ВТОРАЯ КОЛОНКА — ГЛАВНАЯ. Она меряет СЫРУЮ Natasha отдельно от конвейера, и
именно она изменила решение: NewsNERTagger даёт 100% на тексте с заглавными и
РОВНО НОЛЬ на строчном. Не деградирует — исчезает от одного преобразования.
Значит на чатовом трафике вся полнота по именам держится на газетире и
морфологии, а единственная ML-модель продукта не участвует, занимая при этом
память в каждом воркере.

Отсюда критерий отбора любой новой модели: прогнать здесь. Число на чистом
корпусе не значит ничего — на нём справляются все.

    python3 bench/eval_noise_by_type.py dataset.json

Голые топонимы исключены тем же правилом, что в оригинале: продукт не маскирует
город намеренно, и считать его пропуском значит обвинять за работающее решение.
"""
import random
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from testkit import load_dev_bundle

load_dev_bundle()

from bench.eval_noise_ladder import RUNGS, _is_bare_toponym, load
from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter
from pseudex.detect_all import Detector

SEED = 20260819
MIN_SUPPORT = 5


def main() -> int:
    if len(sys.argv) < 2:
        print("использование: eval_noise_by_type.py <dataset.json>")
        return 1

    rows = load(sys.argv[1])
    if not rows:
        print("в наборе нет размеченных значений — нечего мерить")
        return 1

    detector = Detector()
    segmenter, tagger = Segmenter(), NewsNERTagger(NewsEmbedding())

    by_type: dict[str, dict[str, tuple[int, int]]] = {}
    ner_only: dict[str, tuple[int, int]] = {}

    for name, ladder in RUNGS:
        rng = random.Random(SEED)
        per = defaultdict(lambda: [0, 0])
        model = [0, 0]
        for row in rows:
            text, spans = row["text"], row["spans"]
            for step in ladder:
                text, spans = step(text, spans, rng)
            ours = [(s.start, s.end) for s in detector.detect(text)]
            doc = Doc(text)
            doc.segment(segmenter)
            doc.tag_ner(tagger)
            raw = [(s.start, s.stop) for s in doc.spans if s.type == "PER"]
            for span in spans:
                if _is_bare_toponym(span, text):
                    continue
                hit = any(a < span["end"] and span["start"] < b for a, b in ours)
                per[span["type"]][1] += 1
                per[span["type"]][0] += hit
                if span["type"] == "NAME":
                    model[1] += 1
                    model[0] += any(a < span["end"] and span["start"] < b for a, b in raw)
        by_type[name] = {k: tuple(v) for k, v in per.items()}
        ner_only[name] = tuple(model)

    first = RUNGS[0][0]
    types = sorted(by_type[first], key=lambda t: -by_type[first][t][1])

    header = f"{'ТИП':<10}{'N':>5}" + "".join(f"{n.split()[0]:>8}" for n, _ in RUNGS)
    print(header + f"{'ПАДЕНИЕ':>10}")
    print("-" * len(header + "    ПАДЕНИЕ"))

    for kind in types:
        support = by_type[first][kind][1]
        if support < MIN_SUPPORT:
            continue
        rates = []
        line = f"{kind:<10}{support:>5}"
        for name, _ in RUNGS:
            found, total = by_type[name].get(kind, (0, 0))
            rate = found / total * 100 if total else 0.0
            rates.append(rate)
            line += f"{rate:>7.0f}%"
        print(line + f"{rates[-1] - rates[0]:>9.0f}")

    print()
    line = f"{'NAME (NER)':<10}{ner_only[first][1]:>5}"
    rates = []
    for name, _ in RUNGS:
        found, total = ner_only[name]
        rate = found / total * 100 if total else 0.0
        rates.append(rate)
        line += f"{rate:>7.0f}%"
    print(line + f"{rates[-1] - rates[0]:>9.0f}")
    print("^ сырая Natasha без наших правил. Ноль на строчном тексте — это не")
    print("  деградация, а отсутствие модели на том трафике, ради которого её везут.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
