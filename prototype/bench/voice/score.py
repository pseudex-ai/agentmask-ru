"""Голосовой набор: находит ли шлюз адрес, произнесённый вслух, и не хватает ли
он лишнего в обычной речи.

МЕРА — ПРЕДЛОЖЕНИЕ, А НЕ СПАН, и это осознанно. Разметка сделана вручную по
реплике: «есть здесь адрес или нет». Размечать границы на слух в чужой
расшифровке значило бы придумывать ту точность, которой у разметчика не было —
а шлюз всё равно решает по факту «маскировать эту реплику или пропустить».

Три числа, и третье важнее первых двух:

  полнота      сколько из 31 настоящего адреса найдено
  точность     на скольких из 79 обычных реплик мы НЕ сработали
  неоднозначно печатается отдельно и ни во что не входит

Негативы здесь не выдуманы: это та же речь из тех же звонков, где адресная
лексика есть, а адреса нет — «на территории улицы лермонтова понимаете о чем
мы», «ну выходи на улицу», «по всему кварталу погас свет». Наши собственные
наборы такого не содержат по построению, и именно поэтому показывали 100%.

    python3 bench/voice/score.py
    python3 bench/voice/score.py --dump 20
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from testkit import load_dev_bundle

load_dev_bundle()

from pseudex.detect_all import Detector

DATA = Path.home() / ".cache" / "pseudex-bench" / "voice_addresses.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=int, default=8)
    args = parser.parse_args()

    if not DATA.exists():
        print(f"нет {DATA} — соберите: python3 bench/voice/annotate.py", file=sys.stderr)
        return 1
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    detector = Detector()

    found = {"адрес с номером": [], "улица без номера": [],
             "не адрес": [], "неоднозначно": []}
    for row in rows:
        spans = [s for s in detector.detect(row["text"]) if s.entity_type == "LOC"]
        found[row["label"]].append((bool(spans), row["text"], spans))

    def rate(key):
        rows_ = found[key]
        hit = sum(1 for h, _, _ in rows_ if h)
        return hit, len(rows_)

    # ПОЛНОТА И ПОКРЫТИЕ РАЗДЕЛЬНО. Полнота отвечает «сработали ли», покрытие —
    # «взяли ли целиком». Они расходились на семи адресах из семнадцати: строение,
    # корпус и название улицы оставались снаружи спана, а полнота считала это
    # успехом. Разница между двумя числами — это утёкший хвост.
    covered = partial = 0
    tails: list[tuple[str, str]] = []
    for _, text, spans in found["адрес с номером"]:
        row = next(r for r in rows if r["text"] == text and "span" in r)
        lo = text.index(row["span"])
        hi = lo + len(row["span"])
        if any(s.start <= lo and hi <= s.end for s in spans):
            covered += 1
        elif spans:
            partial += 1
            got = max(spans, key=lambda s: s.end - s.start)
            tails.append((row["span"], text[got.start:got.end]))

    num_hit, num_all = rate("адрес с номером")
    bare_hit, bare_all = rate("улица без номера")
    clean = sum(1 for h, _, _ in found["не адрес"] if not h)
    negatives = len(found["не адрес"])

    print("ГОЛОСОВОЙ НАБОР — расшифровки настоящих звонков\n")
    print(f"  АДРЕС С НОМЕРОМ ДОМА — персональные данные")
    print(f"     полнота    {num_hit}/{num_all}   {num_hit / num_all * 100:.0f}%"
          f"   (сработали хотя бы частично)")
    print(f"     ПОКРЫТИЕ   {covered}/{num_all}   {covered / num_all * 100:.0f}%"
          f"   (взяли адрес ЦЕЛИКОМ)")
    if tails:
        print(f"     обрезано у {partial}:")
        for want, got in tails[:6]:
            print(f"        надо: {want}")
            print(f"        взяли: {got}")
    print()
    print(f"  улица без номера       {bare_hit}/{bare_all}"
          f"   {bare_hit / bare_all * 100:.0f}%")
    print("     сама по себе никого не определяет — как город. Становится ПД")
    print("     только связкой с полной формой в том же разговоре, а здесь")
    print("     реплики вырезаны по одной и разговора нет по построению.\n")
    print(f"  точность               {clean}/{negatives}"
          f"   {clean / negatives * 100:.0f}%   (не сработали, где адреса нет)")
    unclear_hit = sum(1 for h, _, _ in found["неоднозначно"] if h)
    print(f"  неоднозначно: {unclear_hit}/{len(found['неоднозначно'])} — в счёт не идут")

    misses = [(t, s) for hit, t, s in found["адрес с номером"] if not hit]
    if misses:
        print(f"\nПРОПУЩЕННЫЕ АДРЕСА С НОМЕРОМ — это ПД ({len(misses)}):")
        for text, _ in misses[:args.dump]:
            print(f"   {text[:100]}")
    false = [(t, s) for hit, t, s in found["не адрес"] if hit]
    if false:
        print(f"\nЛОЖНЫЕ СРАБАТЫВАНИЯ ({len(false)}):")
        for text, spans in false[:args.dump]:
            got = ", ".join(repr(text[s.start:s.end]) for s in spans)
            print(f"   {text[:78]}")
            print(f"      -> {got}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
