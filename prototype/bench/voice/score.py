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

    found = {"адрес": [], "не адрес": [], "неоднозначно": []}
    for row in rows:
        spans = [s for s in detector.detect(row["text"]) if s.entity_type == "LOC"]
        found[row["label"]].append((bool(spans), row["text"], spans))

    hits = sum(1 for hit, _, _ in found["адрес"] if hit)
    total = len(found["адрес"])
    clean = sum(1 for hit, _, _ in found["не адрес"] if not hit)
    negatives = len(found["не адрес"])

    print(f"ГОЛОСОВОЙ НАБОР — расшифровки настоящих звонков\n")
    print(f"  полнота    {hits}/{total}   {hits/total*100:.0f}%")
    print(f"  точность   {clean}/{negatives}   {clean/negatives*100:.0f}%"
          f"   (не сработали там, где адреса нет)")
    unclear_hit = sum(1 for hit, _, _ in found["неоднозначно"] if hit)
    print(f"  неоднозначно: {unclear_hit}/{len(found['неоднозначно'])} сработали"
          f" — в счёт не идут")

    misses = [(t, s) for hit, t, s in found["адрес"] if not hit]
    if misses:
        print(f"\nПРОПУЩЕННЫЕ АДРЕСА ({len(misses)}):")
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
