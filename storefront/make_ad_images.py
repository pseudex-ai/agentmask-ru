"""Комплект картинок для объявлений Директа — генератором, а не подбором.

ЗАЧЕМ ОТДЕЛЬНЫЙ СКРИПТ, А НЕ КАРТИНКИ В ПАПКЕ. У Директа размеры — не вкус, а
условие приёма: при соотношении от 1:1 до 4:3 сторона от 450 до 5000 пикселей,
при 16:9 — от 1080×607, и картинка вне этих рамок обрезается по смарт-центру.
Карточка ссылки (`og-cover.png`) нарисована 1200×630, то есть 1.9:1 — она не
попадает НИ В ОДИН из двух диапазонов. Перерисовать её «на глаз» в двух
пропорциях и держать четыре файла в согласии друг с другом нельзя; здесь
сообщения и палитра лежат в одном месте, а размеры выводятся из них.

ПОЧЕМУ КЕГЛЬ ПОДБИРАЕТСЯ, А НЕ ЗАДАЁТСЯ. Строка, влезающая в 1920 пикселей,
вылезает из 1080 — а заметить это можно только глазами, и только на той
картинке, которую не откроют. Ширина каждой строки измеряется и кегль
уменьшается до попадания.

ЧИСЕЛ И ОБЕЩАНИЙ В КАРТИНКАХ НЕТ. Число, нарисованное на картинке, устаревает
молча: страница печатает его из кода, а картинку никто не перерисует. Поэтому
здесь только то, что не меняется, — суть продукта.

ЗАПУСКАЕТСЯ РУКАМИ. Pillow и fontTools нужны только здесь, и в
`requirements.txt` их нет: боевой образ не должен носить рисовалку.

    cd storefront && .venv/bin/pip install pillow fonttools
    cd storefront && .venv/bin/python make_ad_images.py
"""

import pathlib
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

BG = "#17171a"
LINE = "#2b2b31"
TEXT = "#e8e7ec"
TEXT_2 = "#cfced6"
DIM = "#8f8e99"
ACCENT = "#b3a0ea"
GLOW = "#221f33"

OUT = pathlib.Path("../brand/ad-images")

# ЧТО ИМЕННО ГОВОРЯТ КАРТИНКИ. Три сообщения, каждое — одна мысль, и все три
# утвердительные: картинка, которая объясняет, чем мы не являемся, читается как
# спор и проигрывает его на чужом поле.
MESSAGES = [
    {
        "slug": "01-model-ne-vidit",
        "head": ("Модель не видит данных.", "Инструменты видят."),
        "sub": "Подмена уходит в модель, настоящие значения — в вызов инструмента.",
    },
    {
        "slug": "02-agent-rabotaet",
        "head": ("Агент работает как обычно.", "Данные — обезличены."),
        "sub": "Вызовы инструментов выполняются на реальных значениях.",
    },
    {
        "slug": "03-v-nashem-konture",
        "head": ("ИИ-агент на данных клиентов.", "В вашем контуре."),
        "sub": "152-ФЗ соблюдён, трансграничной передачи нет.",
    },
]

# ПРОПОРЦИИ, КОТОРЫЕ ПРИНИМАЕТ ДИРЕКТ. 4:3 — стандартное, и его же советуют,
# если картинка одна; 16:9 — широкоформатное. Пара на каждое сообщение даёт
# алгоритму что смешивать, а не заставляет выбирать одну площадку.
SIZES = [
    ("4x3", 1440, 1080),
    ("16x9", 1920, 1080),
]

KICKER = "ОБЕЗЛИЧИВАНИЕ ПД ДЛЯ ИИ-АГЕНТОВ · 152-ФЗ"
FOOT = "ФИО · АДРЕСА · ТЕЛЕФОНЫ · СНИЛС · ИНН · ПАСПОРТ · КАРТЫ"


def _merged(family: str, weight: int, where: pathlib.Path) -> pathlib.Path:
    """Латиница и кириллица одного начертания — в одном файле.

    Подмножества разрезаны по алфавитам (`unicode-range` в CSS), и растровому
    рисовальщику нужен один шрифт: иначе «pseudex», «LLM» и «152» выходят
    пустыми квадратами.
    """
    parts = []
    for subset in ("latin", "cyrillic"):
        font = TTFont(f"static/fonts/{family}-{subset}.woff2")
        font.flavor = None
        font = instancer.instantiateVariableFont(font, {"wght": weight}, inplace=False)
        part = where / f"_{family}-{subset}-{weight}.ttf"
        font.save(str(part))
        parts.append(str(part))
    out = where / f"{family}-{weight}.ttf"
    Merger().merge(parts).save(str(out))
    return out


def _fit(draw, text, loader, width: int, start: int) -> ImageFont.FreeTypeFont:
    """Кегль, при котором строка влезает в ширину. Уменьшается, а не обрезается."""
    size = start
    while size > 8:
        font = loader(size)
        if draw.textlength(text, font=font) <= width:
            return font
        size -= 2
    return loader(8)


def build(width: int, height: int, message: dict, fonts: dict,
          destination: pathlib.Path) -> None:
    base = min(width, height)
    margin = int(base * 0.072)
    inner = width - margin * 2

    image = Image.new("RGB", (width, height), BG)
    # Свечение слева сверху — то же, что на самой странице: картинка из ленты
    # должна узнаваться как продолжение сайта, а не как отдельный макет.
    glow = Image.new("RGB", (width, height), BG)
    ImageDraw.Draw(glow).ellipse(
        [-base * 0.25, -base * 0.35, base * 0.7, base * 0.45], fill=GLOW)
    image = Image.blend(image, glow.filter(ImageFilter.GaussianBlur(base // 9)), 0.85)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width - 1, height - 1], outline=LINE, width=1)

    inter = fonts["inter"]
    mono_path = fonts["mono"]
    i = lambda size, weight: inter[weight].font_variant(size=size)  # noqa: E731
    m = lambda size: ImageFont.truetype(str(mono_path), size)  # noqa: E731

    # Знак: два скруглённых квадрата, как в шапке сайта.
    side, shift = int(base * 0.048), int(base * 0.022)
    top = margin
    draw.rounded_rectangle([margin, top + shift, margin + side, top + shift + side],
                           radius=int(side * 0.27), fill=ACCENT)
    draw.rounded_rectangle([margin + shift, top, margin + shift + side, top + side],
                           radius=int(side * 0.27), fill=BG, outline=ACCENT,
                           width=max(2, side // 7))
    draw.text((margin + shift + side + int(base * 0.024), top + int(base * 0.006)),
              "pseudex", font=i(int(base * 0.052), 700), fill=TEXT)

    # Основной блок стоит НА ТРЕТИ ВЫСОТЫ, а не по центру: в ленте у картинки
    # сверху и снизу есть чужая разметка, и центр читается хуже.
    y = int(height * 0.34)
    for index, line in enumerate(message["head"]):
        font = _fit(draw, line, lambda s: i(s, 900), inner, int(base * 0.088))
        draw.text((margin, y), line, font=font,
                  fill=ACCENT if index else TEXT)
        y += int(font.size * 1.12)

    y += int(base * 0.028)
    sub_font = _fit(draw, message["sub"], lambda s: i(s, 400), inner, int(base * 0.030))
    draw.text((margin, y), message["sub"], font=sub_font, fill=TEXT_2)

    draw.text((margin, margin - int(base * 0.030)), KICKER, font=m(int(base * 0.019)),
              fill=DIM)
    draw.line([margin, height - margin - int(base * 0.045),
               width - margin, height - margin - int(base * 0.045)], fill=LINE, width=1)
    foot_font = _fit(draw, FOOT, m, inner, int(base * 0.018))
    draw.text((margin, height - margin - int(base * 0.030)), FOOT, font=foot_font,
              fill=DIM)

    image.save(destination, "PNG", optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    with tempfile.TemporaryDirectory() as tmp:
        where = pathlib.Path(tmp)
        fonts = {
            "inter": {w: ImageFont.truetype(str(_merged("Inter", w, where)), 1)
                      for w in (400, 700, 900)},
            "mono": _merged("JetBrainsMono", 500, where),
        }
        for message in MESSAGES:
            for ratio, width, height in SIZES:
                target = OUT / f"{message['slug']}-{ratio}.png"
                build(width, height, message, fonts, target)
                made.append(target)
    for target in made:
        print(f"  {target.name:38} {Image.open(target).size}  "
              f"{target.stat().st_size // 1024} КБ")


if __name__ == "__main__":
    main()
