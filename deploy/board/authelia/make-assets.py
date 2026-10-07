#!/usr/bin/env python3
"""Portal assets for our identity provider: the mark instead of Authelia's own.

WHY A SCRIPT AND NOT TWO FILES IN GIT. Authelia's portal is compiled into its
binary, so no stylesheet can be dropped in — the only supported branding hook is
`server.asset_path`, and it takes exactly two files: `logo.png` and
`favicon.ico`. Both are DERIVED from the site's own vectors, and a derived binary
committed by hand is a second source of truth that drifts the day the mark
changes. The site's favicon has already been regenerated once for that reason.

WHICH VECTOR GOES WHERE, AND WHY THEY DIFFER:
  - `logo.png` ← `storefront/static/logo.svg`. The transparent mark for a dark
    page, which is what the portal is (`theme: dark`). The solid-tile favicon
    would put a purple square inside the portal's own card, which reads as a
    pasted image rather than a logo.
  - `favicon.ico` ← `storefront/static/favicon.svg`. The tile is what survives at
    16 px inside a browser tab; the outlined mark loses its stroke there.

Run from the storefront venv — it carries Playwright and Pillow, and the same
Chromium rasterizes the site's own icons, so the mark cannot come out subtly
different in the two places:

    cd storefront && .venv/bin/python ../deploy/board/authelia/make-assets.py
"""
import io
import pathlib
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
ASSETS = HERE / "assets"

# Authelia resizes the logo itself, so the source only has to be big enough for
# a retina screen: 512 is 16× the ~32 px it actually renders.
LOGO_SIZE = 512
# `Image.save(..., sizes=...)` builds the multi-size ICO from the largest image,
# so 48 must be rendered and the rest appended, as in storefront/make_favicons.py.
ICO_SIZES = (16, 32, 48)


def _svg(path: pathlib.Path) -> str:
    """The vector without its comment header — a comment cannot be nested in HTML."""
    text = path.read_text(encoding="utf-8")
    return text[text.index("<svg"):]


def _render(vector: pathlib.Path, sizes: tuple[int, ...]) -> dict[int, bytes]:
    """Rasterise at each size. `device_scale_factor=1` EXPLICITLY.

    Playwright defaults to the screen's scale: on a retina machine a 48 px page
    screenshots as 96 px, and the file looks right and is the wrong size.
    """
    html = ("<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;overflow:hidden}"
            "svg{display:block;width:100vw;height:100vh}</style>" + _svg(vector))
    out: dict[int, bytes] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for size in sizes:
            page = browser.new_page(viewport={"width": size, "height": size},
                                    device_scale_factor=1)
            page.set_content(html)
            # `omit_background=True` ОБЯЗАТЕЛЕН. По умолчанию Chromium
            # композитит скриншот на белое, и «прозрачный» логотип приезжает с
            # запечённым белым квадратом: на тёмной карточке портала это
            # выглядит как наш знак, положенный на белый стикер — что и было
            # видно на первом прогоне.
            out[size] = page.screenshot(omit_background=True)
            page.close()
        browser.close()
    return out


def _image(raw: bytes) -> Image.Image:
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def main() -> int:
    logo_vector = REPO / "storefront" / "static" / "logo.svg"
    icon_vector = REPO / "storefront" / "static" / "favicon.svg"
    for path in (logo_vector, icon_vector):
        if not path.exists():
            print(f"нет источника {path}", file=sys.stderr)
            return 1
    ASSETS.mkdir(parents=True, exist_ok=True)

    logo = _image(_render(logo_vector, (LOGO_SIZE,))[LOGO_SIZE])
    # Прозрачный фон — требование Authelia к логотипу: он подставляет его на
    # свою тёмную карточку, и непрозрачный прямоугольник читался бы как заплатка.
    logo.save(ASSETS / "logo.png", "PNG", optimize=True)
    print(f"  logo.png      {logo.size[0]}×{logo.size[1]}  {(ASSETS / 'logo.png').stat().st_size} Б")

    rendered = _render(icon_vector, tuple(sorted(ICO_SIZES)))
    ico = ASSETS / "favicon.ico"
    _image(rendered[48]).save(
        ico, format="ICO", sizes=[(s, s) for s in ICO_SIZES],
        append_images=[_image(rendered[s]) for s in ICO_SIZES if s != 48])
    print(f"  favicon.ico   {Image.open(ico).size}  {ico.stat().st_size} Б")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
