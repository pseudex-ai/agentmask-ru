#!/usr/bin/env python3
"""Сравнительный лист вариантов: чем закрыты контакты на лице.

Один вопрос — один лист. Рисуется из того же макета, что уйдёт в печать,
поэтому выбранный вариант не придётся перерисовывать: это переключатель
`style` в `front()`, а не отдельная картинка.

    PYTHONPATH=/tmp/pylibs python3 print/variants.py
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "preview" / "varianty-zamazki.png"

VARIANTS = [
    ("bars",   "A · ПЛАШКИ",              "текущий: редакционная замазка"),
    ("pixel",  "B · МОЗАИКА",             "значение рассыпано на квадраты"),
    ("scan",   "C · РАСТР",               "строки, как на сжатом скане"),
    ("double", "D · ДВОЙНАЯ ФОРМА",       "язык знака, без самого знака"),
    ("fake",   "E · ОТКРЫТАЯ ПОДМЕНА",    "показано то, что реально видит модель"),
]


def main():
    env = dict(os.environ, FONTCONFIG_FILE="/tmp/fonts.conf")
    tiles = []
    for style, title, note in VARIANTS:
        svg = pathlib.Path("/tmp") / f"var-{style}.svg"
        png = pathlib.Path("/tmp") / f"var-{style}.png"
        svg.write_text(build.wrap(build.front(style=style)), encoding="utf-8")
        subprocess.run(["rsvg-convert", "-f", "png", "-w", "900", "-o", str(png), str(svg)],
                       check=True, env=env)
        tiles.append((title, note, png))

    from PIL import Image, ImageDraw, ImageFont
    f1 = ImageFont.truetype(str(ROOT / "fonts" / "Inter-SemiBold.ttf"), 34)
    f2 = ImageFont.truetype(str(ROOT / "fonts" / "Inter-Regular.ttf"), 28)
    pad, lab, gap = 60, 92, 40
    w = 900
    card_h = Image.open(tiles[0][2]).size[1]
    h = pad * 2 + len(tiles) * (card_h + lab + gap)

    sheet = Image.new("RGB", (w + pad * 2, h), "#0b0b0e")
    dr = ImageDraw.Draw(sheet)
    y = pad
    for title, note, png in tiles:
        dr.text((pad, y), title, font=f1, fill="#b3a0ea")
        dr.text((pad + dr.textlength(title + "  ", font=f1), y + 6), note, font=f2, fill="#74737e")
        y += lab
        card = Image.open(png).convert("RGB")
        sheet.paste(card, (pad, y))
        y += card.size[1] + gap
    sheet.save(OUT)
    print("готово:", OUT, sheet.size)


if __name__ == "__main__":
    main()
