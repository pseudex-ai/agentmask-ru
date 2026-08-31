"""Полнота на ЧУЖОЙ русской речи, размеченной не нами.

ЗАЧЕМ. Все наши цифры по именам получены на корпусах, которые строили мы сами:
AgentPII-RU v3 порождён нашим генератором, голосовой набор размечен нашей рукой.
Оба могут ошибаться в одну сторону, и заметить это изнутри нельзя.

MASSIVE ru-RU — 16 521 реплика голосового ассистента, размеченная слотами
третьей стороной, CC BY 4.0. Регистр проверен и совпадает с продуктовым: НОЛЬ
реплик начинаются с заглавной буквы, пунктуация в 1.1%. Имена стоят в косвенных
падежах («о дональде трампе»), почта продиктована словами («иван собака gmail
точка com»).

ДВА КОРПУСА СОШЛИСЬ, И ЭТО ГЛАВНЫЙ РЕЗУЛЬТАТ ЭТОГО ФАЙЛА. Полнота по именам:
68.0% здесь против 69.6% на нашем собственном v3. Разные данные, разные
разметчики, разные годы — одна цифра. Значит она описывает движок, а не наш
генератор, и любое будущее улучшение обязано двигать ОБЕ.

place_name ЗДЕСЬ БУДЕТ БЛИЗОК К НУЛЮ, И ЭТО ВЕРНОЕ ПОВЕДЕНИЕ. Слот в MASSIVE —
это голый город: «в москве», «в пензе», «в казани». Город никого не определяет
(152-ФЗ ст. 3 п. 1), и мы его намеренно не маскируем. Читать этот ноль как
провал — значит пойти ломать вето, которое стоит по закону.

    curl -sL --create-dirs -o ~/.cache/pseudex-bench/massive_ru_train.parquet \\
      "https://huggingface.co/api/datasets/AmazonScience/massive/parquet/ru-RU/train/0.parquet"
    (то же для validation и test)
    python3 bench/eval_massive_ru.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, ".")
from testkit import load_dev_bundle

load_dev_bundle()

from pseudex.detect_all import Detector

CACHE = Path.home() / ".cache" / "pseudex-bench"
SLOT = re.compile(r"\[([a-z_]+)\s*:\s*([^\]]+)\]")
# Слот MASSIVE -> наш тип. Больше ничего не сверяется: у остальных слотов нет
# нашего соответствия, и придумывать его значило бы мерить своё воображение.
WANTED = {"person": "NAME", "place_name": "LOC", "email_address": "EMAIL"}


def main() -> int:
    files = [CACHE / f"massive_ru_{part}.parquet"
             for part in ("train", "validation", "test")]
    missing = [f for f in files if not f.exists()]
    if missing:
        print(f"нет {missing[0]} — скачайте, команда в докстринге", file=sys.stderr)
        return 1
    frame = pd.concat([pd.read_parquet(f) for f in files])
    detector = Detector()

    stats: dict[str, list[int]] = {slot: [0, 0, 0] for slot in WANTED}
    misses: dict[str, list[tuple[str, str]]] = {slot: [] for slot in WANTED}
    for utterance, annotated in zip(frame["utt"], frame["annot_utt"]):
        text = str(utterance)
        slots = [(kind, value.strip())
                 for kind, value in SLOT.findall(str(annotated)) if kind in WANTED]
        if not slots:
            continue
        spans = detector.detect(text)
        for kind, value in slots:
            if value not in text:
                continue
            start = text.index(value)
            stop = start + len(value)
            same = [s for s in spans if s.entity_type == WANTED[kind]]
            row = stats[kind]
            row[2] += 1
            if any(s.start <= start and stop <= s.end for s in same):
                row[0] += 1
            elif any(s.start < stop and start < s.end for s in same):
                row[1] += 1
            elif len(misses[kind]) < 10:
                misses[kind].append((value, text))

    print("MASSIVE ru-RU — чужая речь, чужая разметка, наш регистр")
    print(f"реплик в корпусе: {len(frame)}\n")
    print(f"{'слот':16}{'эталонов':>10}{'ЦЕЛИКОМ':>10}{'хотя бы часть':>15}")
    for kind, (whole, partial, total) in sorted(stats.items()):
        if not total:
            continue
        print(f"{kind:16}{total:>10}{whole / total * 100:>9.1f}%"
              f"{(whole + partial) / total * 100:>14.1f}%")
    print("\nplace_name — это голые города, и низкое число здесь ПРАВИЛЬНОЕ:")
    print("город никого не определяет, мы его не маскируем намеренно.")
    for kind in ("person", "email_address"):
        if misses[kind]:
            print(f"\nпромахи {kind}:")
            for value, text in misses[kind][:6]:
                print(f"   {value!r:32} в {text[:60]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
