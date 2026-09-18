"""Растровые иконки сайта — из ТОГО ЖЕ SVG, а не нарисованные заново.

ЗАЧЕМ СКРИПТ, А НЕ ТРИ ФАЙЛА В ПАПКЕ. Вебмастер требует иконку «120 × 120, 32 × 32
или 16 × 16», и он же предупреждает: если ссылок на фавиконку несколько, робот
вправе взять ЛЮБУЮ. Значит дублировать форматы можно ровно до тех пор, пока все
они — одна и та же картинка. Три файла, положенные руками, разойдутся при первой
же правке логотипа: поправят SVG, а PNG останется прежним, и робот возьмёт именно
его. Здесь источник один — `static/favicon.svg`, и всё остальное выводится из него.

ЧЕМ РИСУЕТСЯ. SVG растеризует Chromium через playwright — тот же инструмент, что
в `test_ops_renders.py`, и по той же причине: «нарисовать прямоугольники в PIL»
значило бы завести ВТОРУЮ реализацию логотипа, которая разойдётся с первой.
Pillow нужен только чтобы собрать многоразмерный `.ico` из готовых PNG.

РАЗМЕРЫ И ПОЧЕМУ ИХ ПЯТЬ:
  * 16 / 32 / 48 — в многоразмерный `favicon.ico`: его просят закладки, старые
    браузеры и робот, который рисует иконку в выдаче;
  * 120 — назван в требованиях Вебмастера отдельно: «размер 120 × 120 или формат
    SVG позволяют отображать логотип чётче»;
  * 180 — `apple-touch-icon`; Safari сам просит именно этот размер.

ЗАПУСКАЕТСЯ РУКАМИ. Картинка меняется раз в год, и место ей не в витрине:

    cd storefront && .venv/bin/pip install playwright pillow
    cd storefront && .venv/bin/python make_favicons.py
"""
import io
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
STATIC = HERE / "static"
VECTOR = STATIC / "favicon.svg"

# Многоразмерный ICO: эти три и только эти. Больше — тяжелее файл, а выигрыша
# нет: 48 px уже перекрывает всё, что просят.
ICO_SIZES = (16, 32, 48)
# Отдельные PNG: 120 назван Вебмастером, 180 просит Safari.
PNG_SIZES = (120, 180)


def _svg_source() -> str:
    """SVG без комментария-заголовка: в HTML он не нужен, а вставить мешает."""
    text = VECTOR.read_text(encoding="utf-8")
    return text[text.index("<svg"):]


def _render(sizes: tuple[int, ...]) -> dict[int, bytes]:
    """Растеризовать вектор в каждый размер. Одна страница на размер.

    `device_scale_factor=1` ЯВНО: по умолчанию playwright рисует в масштабе
    экрана, и на машине с Retina вместо 32 × 32 получилось бы 64 × 64 — файл,
    который выглядит правильным и не проходит проверку размера.
    """
    html = ("<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;overflow:hidden}"
            "svg{display:block;width:100vw;height:100vh}</style>" + _svg_source())
    out: dict[int, bytes] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size in sizes:
            page = browser.new_page(viewport={"width": size, "height": size},
                                    device_scale_factor=1)
            page.set_content(html)
            out[size] = page.screenshot()
            page.close()
        browser.close()
    return out


def _image(raw: bytes) -> Image.Image:
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def main() -> None:
    assert VECTOR.exists(), f"нет источника {VECTOR}"
    if 'width="' not in _svg_source().split(">")[0]:
        raise SystemExit(
            "у favicon.svg нет явных width/height — Вебмастер требует размер, "
            "а из одного viewBox его не вывести")

    rendered = _render(tuple(sorted(set(ICO_SIZES) | set(PNG_SIZES))))

    for size in PNG_SIZES:
        target = STATIC / f"favicon-{size}.png"
        _image(rendered[size]).save(target, "PNG", optimize=True)
        print(f"  {target.name:20} {size}×{size}  {target.stat().st_size} Б")

    ico = STATIC / "favicon.ico"
    _image(rendered[48]).save(
        ico, format="ICO", sizes=[(s, s) for s in ICO_SIZES],
        append_images=[_image(rendered[s]) for s in ICO_SIZES if s != 48])
    print(f"  {ico.name:20} {Image.open(ico).size}  {ico.stat().st_size} Б")


if __name__ == "__main__":
    main()
