"""Голосовой набор: находит ли шлюз адрес, произнесённый вслух, и не хватает ли
он лишнего в обычной речи.

ЧЕТЫРЕ ЧИСЛА, И НИ ОДНО НЕ ЗАМЕНЯЕТ ОСТАЛЬНЫЕ:

  полнота     на скольких значениях сработали ХОТЬ КАК-ТО
  ПОКРЫТИЕ    на скольких взяли значение ЦЕЛИКОМ — разница с полнотой утекла
  точность    на скольких обычных репликах НЕ сработали
  различных   сколько РАЗНЫХ адресов стоит за этими значениями

ПОСЛЕДНЕЕ ЧИСЛО ЗАВЕДЕНО ПОТОМУ, ЧТО ПОВТОР — НЕ НАБЛЮДЕНИЕ. Корпус состоит из
розыгрышей военкоматов, и один адрес — «лермонтова тридцать восемь» — сказан в
нём семь раз разными людьми. Доверительный интервал, посчитанный по репликам,
считает эти семь независимыми и врёт в нашу пользу; поэтому интервал печатается
по РАЗЛИЧНЫМ адресам, а по репликам — только само отношение.

ДОВЕРИТЕЛЬНЫЙ ИНТЕРВАЛ ПЕЧАТАЕТСЯ ВСЕГДА. На семнадцати значениях «100%»
означает «не хуже 80.5%», и это не придирка: разница между 80% и 100% — это
разница между продуктом и обещанием. Точный биномиальный (Клоппер–Пирсон), без
scipy — считается на числах такого размера мгновенно.

Негативы здесь не выдуманы: это та же речь из тех же звонков, где адресная
лексика или число есть, а адреса нет — «на территории улицы лермонтова
понимаете о чем мы», «триста четырнадцатый кабинет», «примите сигнал мушка
триста тридцать три». Наши собственные наборы такого не содержат по построению,
и именно поэтому показывали 100%.

    python3 bench/voice/annotate.py     # сначала пересобрать разметку
    python3 bench/voice/score.py
    python3 bench/voice/score.py --dump 20
"""
import argparse
import json
import sys
from math import exp, lgamma, log, log1p
from pathlib import Path

sys.path.insert(0, ".")
from testkit import load_dev_bundle

load_dev_bundle()

from pseudex.detect_all import Detector

DATA = Path.home() / ".cache" / "pseudex-bench" / "voice_addresses.json"


def clopper_pearson(hits: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    """Точный биномиальный интервал. Бисекция по CDF, а не приближение.

    Нормальное приближение на наших размерах даёт границы вне [0,1] и лжёт
    сильнее всего ровно там, где мы стоим — при доле, равной единице.
    """
    if total == 0:
        return 0.0, 1.0

    # В ЛОГАРИФМАХ, А НЕ В ЛОБ. `comb(1300, 650)` — целое на четыреста знаков, и
    # умножение его на float падает с OverflowError ровно тогда, когда набор
    # негативов дорастает до полезного размера. Прибор, который ломается от
    # роста выборки, — это прибор, который придётся чинить в тот момент, когда
    # ему наконец начали верить.
    def _pmf_log(p: float, i: int) -> float:
        return (lgamma(total + 1) - lgamma(i + 1) - lgamma(total - i + 1)
                + i * log(p) + (total - i) * log1p(-p))

    def ge(p: float, k: int) -> float:
        return sum(exp(_pmf_log(p, i)) for i in range(k, total + 1))

    def le(p: float, k: int) -> float:
        return sum(exp(_pmf_log(p, i)) for i in range(0, k + 1))

    low = 0.0
    if hits:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a + b) / 2
            a, b = (mid, b) if ge(mid, hits) < alpha / 2 else (a, mid)
        low = (a + b) / 2
    high = 1.0
    if hits < total:
        a, b = 0.0, 1.0
        for _ in range(80):
            mid = (a + b) / 2
            a, b = (a, mid) if le(mid, hits) < alpha / 2 else (mid, b)
        high = (a + b) / 2
    return low, high


def _norm(value: str) -> str:
    return value.lower().replace("ё", "е").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=int, default=8)
    args = parser.parse_args()

    if not DATA.exists():
        print(f"нет {DATA} — соберите: python3 bench/voice/annotate.py", file=sys.stderr)
        return 1
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    detector = Detector()

    covered = partial = missed = 0
    tails: list[tuple[str, str]] = []
    gone: list[str] = []
    # По РАЗЛИЧНЫМ адресам: значение засчитывается покрытым, только если КАЖДОЕ
    # его вхождение взято целиком. Одно вхождение из семи — это дефект, который
    # среднее по вхождениям спрятало бы.
    per_value: dict[str, list[bool]] = {}
    for row in rows:
        if row["label"] != "адрес с номером":
            continue
        text = row["text"]
        spans = [s for s in detector.detect(text) if s.entity_type == "LOC"]
        for want in row["spans"]:
            lo = text.index(want)
            hi = lo + len(want)
            whole = any(s.start <= lo and hi <= s.end for s in spans)
            touched = any(s.start < hi and lo < s.end for s in spans)
            per_value.setdefault(_norm(want), []).append(whole)
            if whole:
                covered += 1
            elif touched:
                partial += 1
                got = max((s for s in spans if s.start < hi and lo < s.end),
                          key=lambda s: s.end - s.start)
                tails.append((want, text[got.start:got.end]))
            else:
                missed += 1
                gone.append(f"{want!r}   в {text[:80]!r}")

    values = covered + partial + missed
    distinct_ok = sum(1 for hits in per_value.values() if all(hits))
    distinct = len(per_value)

    negatives = [r for r in rows if r["label"] == "не адрес"]
    clean, false = 0, []
    for row in negatives:
        spans = [s for s in detector.detect(row["text"]) if s.entity_type == "LOC"]
        if spans:
            false.append((row["text"], spans))
        else:
            clean += 1
    bare = [r for r in rows if r["label"] == "улица без номера"]
    bare_hit = sum(1 for r in bare
                   if any(s.entity_type == "LOC" for s in detector.detect(r["text"])))
    unclear = [r for r in rows if r["label"] == "неоднозначно"]
    unclear_hit = sum(1 for r in unclear
                      if any(s.entity_type == "LOC" for s in detector.detect(r["text"])))
    pass2 = sum(1 for r in rows if r.get("pass") == 2)

    def line(name: str, hits: int, total: int, note: str = "") -> None:
        low, high = clopper_pearson(hits, total)
        print(f"     {name:<11} {hits}/{total}   {hits / total * 100:5.1f}%"
              f"   95% ДИ [{low * 100:4.1f}, {high * 100:5.1f}]   {note}")

    print("ГОЛОСОВОЙ НАБОР — расшифровки настоящих звонков")
    print(f"кандидатов {len(rows)} (фильтр: числительное, цифра или слово-маркер)"
          f" · во вторую партию размечено {pass2}\n")
    print("  АДРЕС С НОМЕРОМ ДОМА — персональные данные")
    line("полнота", covered + partial, values, "сработали хотя бы частично")
    line("ПОКРЫТИЕ", covered, values, "взяли значение ЦЕЛИКОМ")
    line("различных", distinct_ok, distinct, "РАЗНЫХ адресов, взятых целиком везде")
    if tails:
        print(f"     обрезано у {partial}:")
        for want, got in tails[:args.dump]:
            print(f"        надо : {want}")
            print(f"        взяли: {got}")
    if gone:
        print(f"     НЕ НАЙДЕНО ВОВСЕ {len(gone)} — это утёкшие ПД:")
        for item in gone[:args.dump]:
            print(f"        {item}")
    print()
    line("улица", bare_hit, len(bare), "без номера — сама по себе НЕ ПД")
    print("     Становится ПД только связкой с полной формой в том же разговоре,")
    print("     а здесь реплики вырезаны по одной и разговора нет по построению.\n")
    line("точность", clean, len(negatives), "не сработали, где адреса нет")
    print(f"  неоднозначно: {unclear_hit}/{len(unclear)} — в счёт не идут")
    if false:
        print(f"\nЛОЖНЫЕ СРАБАТЫВАНИЯ ({len(false)}):")
        for text, spans in false[:args.dump]:
            got = ", ".join(repr(text[s.start:s.end]) for s in spans)
            print(f"   {text[:78]}")
            print(f"      -> {got}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
