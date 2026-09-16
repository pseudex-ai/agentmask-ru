"""Карточка ссылки (`static/og-cover.png`) — генератором, а не файлом из ниоткуда.

ЗАЧЕМ СКРИПТ. Картинка, положенная в репозиторий руками, через год необъяснима:
неизвестно, чем и из чего она сделана, и поправить строчку в ней нельзя — только
перерисовать заново на глаз. Здесь же видно, что она собрана НАШИМИ шрифтами и
НАШЕЙ палитрой, и правится она правкой строки.

ПОЧЕМУ ШРИФТЫ СКЛЕИВАЮТСЯ. `static/fonts/*.woff2` разрезаны по алфавитам
(`unicode-range` в CSS): в кириллическом файле нет ни латиницы, ни цифр, ни
точки. Первый прогон отрисовал «pseudex», «LLM» и «152» пустыми квадратами.
Браузер подставляет нужный файл сам, а растровому рисовальщику нужен один
шрифт — поэтому подмножества сводятся в один временный файл.

ЧИСЕЛ, КОТОРЫЕ МОГУТ УСТАРЕТЬ, В КАРТИНКЕ НЕТ. Страница печатает их из кода и
не может разойтись с ним; картинка — может, и заметить это будет нечем, потому
что смотрят на неё в чужой ленте.

ЗАПУСКАЕТСЯ РУКАМИ И НЕ В СОСТАВЕ ВИТРИНЫ. Pillow и fontTools нужны только
здесь, поэтому их нет в `requirements.txt`: боевой образ не должен носить
рисовалку ради картинки, которая меняется раз в год.

    cd storefront && .venv/bin/pip install pillow fonttools
    cd storefront && .venv/bin/python make_og_cover.py
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
WIDTH, HEIGHT = 1200, 630          # размер, которого ждут Telegram, Slack и поиск
MARGIN = 72


def _merged(family: str, weight: int, where: pathlib.Path) -> pathlib.Path:
    """Латиница и кириллица одного начертания — в одном файле."""
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


def build(destination: pathlib.Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        where = pathlib.Path(tmp)
        inter = {w: ImageFont.truetype(str(_merged("Inter", w, where)), 1)
                 for w in (400, 700, 900)}
        mono_path = _merged("JetBrainsMono", 500, where)

        def i(size: int, weight: int) -> ImageFont.FreeTypeFont:
            return inter[weight].font_variant(size=size)

        def m(size: int) -> ImageFont.FreeTypeFont:
            return ImageFont.truetype(str(mono_path), size)

        image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        # Мягкое свечение слева сверху — то же, что на самой странице.
        glow = Image.new("RGB", (WIDTH, HEIGHT), BG)
        ImageDraw.Draw(glow).ellipse([-260, -320, 700, 420], fill=GLOW)
        image = Image.blend(image, glow.filter(ImageFilter.GaussianBlur(120)), 0.85)
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, WIDTH - 1, HEIGHT - 1], outline=LINE, width=1)

        # Знак: два скруглённых квадрата, как в шапке сайта.
        side, shift = 44, 20
        draw.rounded_rectangle([MARGIN, MARGIN + shift, MARGIN + side,
                                MARGIN + shift + side], radius=12, fill=ACCENT)
        draw.rounded_rectangle([MARGIN + shift, MARGIN, MARGIN + shift + side,
                                MARGIN + side], radius=12, fill=BG,
                               outline=ACCENT, width=6)
        draw.text((MARGIN + shift + side + 22, MARGIN + 6), "pseudex",
                  font=i(46, 700), fill=TEXT)
        draw.text((MARGIN, MARGIN + 104),
                  "ШЛЮЗ ПЕРСОНАЛЬНЫХ ДАННЫХ ДЛЯ LLM-АГЕНТОВ · 152-ФЗ",
                  font=m(19), fill=ACCENT)

        draw.text((MARGIN, 228), "Модель не видит данных.", font=i(72, 900), fill=TEXT)
        draw.text((MARGIN, 314), "Инструменты видят.", font=i(72, 900), fill=ACCENT)
        draw.text((MARGIN, 432),
                  "Подмена уходит в модель, настоящие значения — в вызов инструмента.\n"
                  "Контейнер в вашем контуре: наружу уходят только счётчики.",
                  font=i(25, 400), fill=TEXT_2, spacing=12)

        draw.line([MARGIN, HEIGHT - 108, WIDTH - MARGIN, HEIGHT - 108],
                  fill=LINE, width=1)
        draw.text((MARGIN, HEIGHT - 84),
                  "ФИО · АДРЕСА · СНИЛС · ИНН · ПАСПОРТ · ХОСТИНГ В РФ",
                  font=m(17), fill=DIM)

        image.save(destination, "PNG", optimize=True)


if __name__ == "__main__":
    target = pathlib.Path("static/og-cover.png")
    build(target)
    print(f"{target} — {target.stat().st_size} байт")
