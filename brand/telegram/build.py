#!/usr/bin/env python3
"""Аватарки Telegram: группа и два бота, одной семьёй и без ошибок в 40 пикселей.

ЗАЧЕМ ОТДЕЛЬНЫЙ СБОРЩИК, А НЕ ГЕНЕРАТОР КАРТИНОК. Формат задан нашим же
favicon: залитая плитка и вырезанный из неё знак. Это геометрия, а не рисунок,
и у неё нет права «примерно так»: в чате аватарка живёт в 40 пикселях, где
скруглённый угол превращается в два, а цвет плитки — в единственную примету.
Рисовать такое моделью значит получить пятно вместо знака и заново при каждом
изменении палитры. Здесь тот же приём, что в `brand/logo/build.py`: SVG из
координат и `rsvg-convert` в PNG.

ПОЧЕМУ ТРИ РАЗНЫХ ЦВЕТА, А НЕ ТРИ РАЗНЫХ ЗНАКА. Знак у нас один, и это его
сила: две скруглённые формы внахлёст — настоящее и подменённое. Но в списке
чатов три одинаковые фиолетовые плитки неразличимы, а различать их надо на
бегу. Поэтому семья одна (та же плитка, тот же знак, те же поля), а цвет плитки
разный, и все три цвета — из нашей палитры:
  * группа  — акцент `#b3a0ea`, ровно как favicon: это «дом», главная из трёх;
  * support — зелёный `#93cfaa`;
  * ops     — янтарный `#dcbd85`.
Обратный вариант для группы — тёмная плитка с акцентным знаком: он тоже здесь,
потому что в светлом Telegram тёмная аватарка заметнее и выбор стоит делать
глазами, а не по описанию.

    python3 brand/telegram/build.py
"""
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent

ACCENT = "#b3a0ea"   # акцент с тёмного
GREEN = "#93cfaa"
AMBER = "#dcbd85"
DARK = "#17171a"

SIZE = 512


def avatar(tile: str, shape: str, upper: str) -> str:
    """Плитка и вырезанный знак — геометрия favicon один в один.

    `upper` — заливка верхней формы: цвет плитки, чтобы она читалась ДЫРКОЙ, а
    не вторым прямоугольником другого цвета. Это и есть знак: две формы, одна
    из которых показывает фон сквозь себя.
    """
    s = SIZE / 32.0
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" '
        f'viewBox="0 0 {SIZE} {SIZE}">'
        f'<rect width="{SIZE}" height="{SIZE}" fill="{tile}"/>'
        f'<g transform="scale({s})">'
        f'<rect x="4" y="12" width="16" height="16" rx="4.5" fill="{shape}"/>'
        f'<rect x="12" y="4" width="16" height="16" rx="4.5" fill="{upper}" '
        f'stroke="{shape}" stroke-width="2.4"/>'
        "</g></svg>"
    )


# Имя файла — это то, что человек читает в списке чатов, а не «вариант 3».
# Поэтому имена говорят, КУДА аватарку ставить.
SET = [
    ("group", ACCENT, DARK, ACCENT),    # плитка · знак · заливка верхней формы
    ("group-dark", DARK, ACCENT, DARK),
    ("bot-support", GREEN, DARK, GREEN),
    ("bot-ops", AMBER, DARK, AMBER),
]


def main() -> int:
    for name, tile, shape, upper in SET:
        svg = HERE / f"{name}.svg"
        svg.write_text(avatar(tile, shape, upper))
        subprocess.run(
            ["rsvg-convert", "-f", "png", "-o", str(HERE / f"{name}-{SIZE}.png"),
             "-w", str(SIZE), "-h", str(SIZE), str(svg)],
            check=True,
        )
        print(f"  {name}: {tile} · {svg.name} + {name}-{SIZE}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
