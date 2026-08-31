"""Строит лист для ручной разметки и считает по нему потолок гейта.

ВЫБОРКА ПО ВХОЖДЕНИЯМ, А НЕ ПО СЛОВАМ. Вопрос звучит «какая доля замаскированных
вхождений — не человек», и это доля по вхождениям; выборка по словам ответила бы
на другой вопрос и дала бы редкому слову тот же вес, что «капцу», сказанному
шестьдесят раз.

ДВЕ СТРАТЫ, И ОНИ НЕ СКЛАДЫВАЮТСЯ. Замаскированные отвечают за точность,
пропущенные — за полноту; у них разные размеры и разные доли, и общее число по
объединённой выборке не описывало бы ни одну из них.

ВЫБОРКА ЗАКРЕПЛЕНА ЗА СНИМКОМ, А НЕ ЗА ЖИВЫМ ДВИЖКОМ, и это пришлось чинить
сразу же. Страта задавалась тем, что движок делает СЕЙЧАС, — поэтому первая же
починка перетасовала выборку, и из 600 размеченных вручную вхождений в неё
попали 228: прибор развалился ровно от того улучшения, которое должен был
измерить. Теперь страта берётся из снимка `gate_candidates.json`, а живой
детектор запускается на тех же вхождениях заново. Число, которое печатается, —
это ДВИЖЕНИЕ относительно снимка, и разметка переживает любую правку движка.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import random
import sys
from math import exp, lgamma, log, log1p

ROOT = pathlib.Path(__file__).resolve().parents[1].parent
CACHE = pathlib.Path.home() / ".cache" / "pseudex-bench"
SRC = CACHE / "gate_candidates.json"
LABELS = pathlib.Path(__file__).resolve().parent / "labels.json"

# Публичная фигура вынесена в отдельный класс НАМЕРЕННО. По 152-ФЗ имя депутата
# — такие же персональные данные, как имя клиента; по назначению продукта это
# реплика о новостях, а не запись в CRM. Числа печатаются в обе стороны, и выбор
# остаётся за владельцем — ровно как с КПП и ОГРН в eval_piibench.
# АДРЕС И ТОПОНИМ — РАЗНЫЕ КЛАССЫ, И РАЗНИЦА ПРАВОВАЯ, А НЕ ГРАДАЦИЯ
# УВЕРЕННОСТИ. «Лермонтова тридцать восемь» указывает на здание и маскируется;
# «как пройти на улицу Пушкина» не указывает ни на кого — на улице сотни домов,
# это ровно на шаг конкретнее города, который мы уже признали никого не
# определяющим (152-ФЗ ст. 3 п. 1). Пока они считались одним классом, каждый
# правильный отказ от голой улицы выглядел промахом, а каждый найденный адрес —
# лишней маской.
CLASSES = {
    "person":  "живой человек, о котором идёт речь — маскировать надо",
    "address": "адрес с номером дома — тоже маскировать надо",
    "public":  "публичная фигура: политик, артист, историческое лицо",
    "place":   "голый топоним: город, улица без дома — по закону не ПД",
    "other":   "не ПД вовсе: обычное слово, бренд, помощник, кличка",
}
# Что продукт ОБЯЗАН маскировать. Публичная фигура сюда не входит намеренно:
# по 152-ФЗ её имя — такие же персональные данные, по назначению продукта это
# реплика о новостях. Число печатается отдельной строкой в обе стороны.
MUST_MASK = ("person", "address")


def clopper_pearson(hits: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    if total == 0:
        return 0.0, 1.0

    def pmf_log(p: float, i: int) -> float:
        return (lgamma(total + 1) - lgamma(i + 1) - lgamma(total - i + 1)
                + i * log(p) + (total - i) * log1p(-p))

    def ge(p: float, k: int) -> float:
        return sum(exp(pmf_log(p, i)) for i in range(k, total + 1))

    def le(p: float, k: int) -> float:
        return sum(exp(pmf_log(p, i)) for i in range(0, k + 1))

    low, high = 0.0, 1.0
    if hits:
        a, b = 0.0, 1.0
        for _ in range(60):
            mid = (a + b) / 2
            a, b = (mid, b) if ge(mid, hits) < alpha / 2 else (a, mid)
        low = (a + b) / 2
    if hits < total:
        a, b = 0.0, 1.0
        for _ in range(60):
            mid = (a + b) / 2
            a, b = (a, mid) if le(mid, hits) < alpha / 2 else (mid, b)
        high = (a + b) / 2
    return low, high


def key(row: dict) -> str:
    """Ключ метки — ХЕШ слова, позиции и реплики.

    Не номер в списке: номер позиции переживает пересборку выборки молча и
    делает разметку неверной, ничего не сломав, — это уже стоило нам голосового
    набора. И не сам текст: звонки взяты из OpenSTT под CC BY-NC, мерить по ним
    можно, отгружать нельзя. В репозитории лежат хеши и метки, реплики живут в
    ~/.cache/pseudex-bench/, как NEREL и остальные чужие корпуса.
    """
    raw = f"{row['word']}\t{row['start']}\t{row['text']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def sample(rows: list[dict], want: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    picked = rows if len(rows) <= want else rng.sample(rows, want)
    return sorted(picked, key=lambda r: (r["word"], r["start"]))


def load() -> list[dict]:
    if not SRC.exists():
        print(f"нет {SRC} — соберите: python3 bench/gate/extract.py", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(SRC.read_text(encoding="utf-8"))["occurrences"]


def _live_decisions(strata: dict) -> dict:
    """Что ЖИВОЙ детектор делает с каждым закреплённым вхождением сейчас."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from testkit import load_dev_bundle

    load_dev_bundle()
    from pseudex.detect_all import Detector

    detector = Detector()
    out: dict[str, bool] = {}
    for rows in strata.values():
        for row in rows:
            spans = detector.detect(row["text"])
            out[key(row)] = any(
                s.start <= row["start"] and row["end"] <= s.end
                and s.entity_type in ("NAME", "LOC") for s in spans)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument("--print", dest="show", choices=("masked", "missed"))
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--count", type=int, default=60)
    args = parser.parse_args()

    occ = load()
    strata = {
        "masked": sample([r for r in occ if r["masked"]], args.size, args.seed),
        "missed": sample([r for r in occ if not r["masked"]], args.size, args.seed),
    }
    labels = json.loads(LABELS.read_text(encoding="utf-8")) if LABELS.exists() else {}
    now = _live_decisions(strata) if not args.show else {}

    if args.show:
        rows = strata[args.show]
        for i, row in enumerate(rows[args.offset:args.offset + args.count],
                                args.offset):
            text = row["text"]
            marked = (text[:row["start"]] + "«" + row["word"] + "»"
                      + text[row["end"]:])
            got = labels.get(key(row), "")
            print(f"{i:>3} {row['word']:<14} {got:<7} {marked}")
        return 0

    print("ПОТОЛОК ГЕЙТА — размечено вручную, по вхождениям\n")
    totals = {"masked": sum(1 for r in occ if r["masked"]),
              "missed": sum(1 for r in occ if not r["masked"])}
    per_word: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)
    for stratum, rows in strata.items():
        done = [labels[key(r)] for r in rows if key(r) in labels]
        for row in rows:
            got = labels.get(key(row))
            if got:
                per_word[row["word"]][got] += 1
        if not done:
            print(f"  {stratum}: не размечено")
            continue
        counts = collections.Counter(done)
        real = sum(counts[c] for c in MUST_MASK)
        low, high = clopper_pearson(real, len(done))
        head = ("ЗАМАСКИРОВАНО" if stratum == "masked" else "ПРОПУЩЕНО")
        print(f"  {head} — всего {totals[stratum]}, размечено {len(done)}/{len(rows)}")
        print(f"     ОБЯЗАНЫ маскировать {real}/{len(done)} = "
              f"{real / len(done) * 100:5.1f}%"
              f"   95% ДИ [{low * 100:4.1f}, {high * 100:5.1f}]")
        for name in ("person", "address", "public", "place", "other"):
            if counts[name]:
                print(f"     {name:<8} {counts[name]:>4}"
                      f"   {counts[name] / len(done) * 100:5.1f}%"
                      f"   — {CLASSES[name]}")
        wrong = len(done) - real - counts["public"]
        print(f"     -> в пересчёте на корпус: ПД {round(totals[stratum] * real / len(done)):,}"
              f" · НЕ ПД {round(totals[stratum] * wrong / len(done)):,}"
              f" · публичных фигур {round(totals[stratum] * counts['public'] / len(done)):,}")
        moved = [r for r in rows if key(r) in labels
                 and now.get(key(r)) != (stratum == "masked")]
        if moved:
            good = sum(1 for r in moved
                       if (labels[key(r)] in MUST_MASK) == now[key(r)])
            print(f"     СДВИГ ОТ СНИМКА: {len(moved)} вхождений сменили решение,"
                  f" из них ПРАВИЛЬНО {good}, неправильно {len(moved) - good}")
        print()

    mixed = {w: c for w, c in per_word.items()
             if len(c) > 1 and sum(c.values()) > 1}
    decided = {w: c for w, c in per_word.items() if len(c) == 1}
    print(f"РАЗРЕШИМО СПИСКОМ: {len(decided)} слов повели себя одинаково везде")
    print(f"ТРЕБУЕТ КОНТЕКСТА:  {len(mixed)} слов повели себя ПО-РАЗНОМУ:")
    for word, counts in sorted(mixed.items(),
                               key=lambda kv: -sum(kv[1].values()))[:25]:
        print(f"     {word:<14} " + "  ".join(f"{k}={v}" for k, v in counts.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
