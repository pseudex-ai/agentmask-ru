#!/usr/bin/env python3
"""Сборка печатных файлов визитки Pseudex.

Один источник истины — словарь CARD ниже. Меняете данные, запускаете:

    PYTHONPATH=/tmp/pylibs python3 print/build.py

и получаете в print/ векторные SVG/PDF и PNG 300 dpi, а в preview/ — макет
для показа. Геометрия считается в миллиметрах: карта 85.6x54 мм, вылеты 2 мм
со всех сторон (89.6x58), контент не ближе 5 мм к резу.

Почему так, а не «нарисовать в редакторе»: координаты в мм, шрифты и палитра
взяты из brand/README.md, и любая правка текста не сдвигает сетку.
"""
import os
import pathlib
import subprocess
import sys
import xml.sax.saxutils as sx

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
FONTS = ROOT / "fonts"

# ------------------------------------------------------------- данные людей
# Один список на всех. Вторая визитка — это ЗАПИСЬ ЗДЕСЬ, а не второй макет:
# макет у команды один, меняются имя, должность и контакты. Файлы собираются
# с суффиксом slug, чтобы цех не перепутал комплекты.
#
# Почты — ЛИЧНЫЕ: первая буква имени плюс фамилия (i.afonin, g.tolkachev).
# Ролевой адрес (product@) выглядит корпоративно ровно до второго продакта:
# двум людям один ящик не отдать, а на визитке он обещает не человека, а
# должность, которой завтра может не быть.
# Фамилий пока нет — на карточках только имена, добавим позже одной строкой.
# Должность — функция, а не титул: клиенту важно, с чем к человеку идти.
PEOPLE = [
    {
        "slug": "igor",
        "name": "Игорь",
        "title": "Архитектор · основатель",
        "tel": "+7 993 504-01-47",
        "mail": "i.afonin@pseudex.ru",
        "web": "pseudex.ru",
        "nfc_url": "https://pseudex.ru/i/igor",
    },
    {
        "slug": "gosha",
        "name": "Георгий",
        "title": "Продажи · маркетинг",
        "tel": "+7 965 522-87-58",
        "mail": "g.tolkachev@pseudex.ru",
        "web": "pseudex.ru",
        "nfc_url": "https://pseudex.ru/i/gosha",
    },
    {
        "slug": "slava",
        "name": "Слава",
        "title": "Инженер · разработчик",
        "tel": "+7 993 524-73-03",
        "mail": "s.gabanyan@pseudex.ru",
        "web": "pseudex.ru",
        "nfc_url": "https://pseudex.ru/i/slava",
    },
]

# ------------------------------------------------------------------- брендбук
BG       = "#17171a"   # фон тёмной стороны
PAPER    = "#e8e7ec"   # фон светлой стороны («раскрытие»)
INK      = "#1c1c20"   # текст на светлом
LINE_D   = "#2b2b31"   # линии на тёмном
LINE_L   = "#cfced6"   # линии на светлом
TEXT     = "#e8e7ec"
DIM      = "#a9a8b3"
MUTED    = "#8f8e99"
MUTED2   = "#74737e"
GHOST    = "#5c5c66"
GHOST_D  = "#232329"   # «данные под маской» — почти не видно, фактура
ACCENT   = "#b3a0ea"   # акцент
ACCENT2  = "#cec0f2"   # акцент+ (в брендбуке — второй тон акцента)
ACCENT_L = "#6f6486"   # акцент на светлом (документы, счета)

# -------------------------------------------------------------------- форматы
# Один макет, два носителя. Пластик — карточный размер 85.6x54 (ISO/IEC 7810
# ID-1). Бумага — 90x50: это стандарт бумажных визиток в России, цех режет его
# из своего шаблона, а нестандартный размер считает отдельно и часто дороже.
FORMATS = {
    "plastic": (85.6, 54.0),
    "paper": (90.0, 50.0),
}
FMT = "plastic"
BLEED = 2.0
M = 5.0                      # отступ от реза
_DT, _DBOT = 7.0, 51.0       # рамка, в которой нарисован исходный макет (высота 54)


def set_format(name):
    """Пересчитывает геометрию под носитель.

    Вертикаль макета нарисована руками под высоту 54 мм. Рисовать бумажный
    макет заново — значит завести ВТОРОЙ дизайн, который разъедется с первым
    при первой же правке телефона. Поэтому все вертикальные координаты и
    размеры пересчитываются одним коэффициентом от высоты контента: на пластике
    он равен ровно 1, и там не меняется ни один пиксель.
    """
    global FMT, TW, TH, CW, CH, X0, Y0, L, R, T, BOT, K
    FMT = name
    TW, TH = FORMATS[name]
    CW, CH = TW + 2 * BLEED, TH + 2 * BLEED
    X0 = Y0 = BLEED
    L, R = X0 + M, X0 + TW - M
    T, BOT = Y0 + M, Y0 + TH - M
    K = (BOT - T) / (_DBOT - _DT)


def vy(y):
    """Вертикальная координата из 54-мм макета — в текущий формат.
    Округление до тысячных: без него 7 + (11.9-7) даёт 11.899999999999999,
    и «не изменившийся» пластик меняет байты в PDF."""
    return round(T + (y - _DT) * K, 3)


def sz(v):
    """Размер (кегль, высота значка, сторона QR) — в текущий формат."""
    return round(v * K, 4)


set_format(FMT)


def pt(p):
    """Пункты в миллиметры — так размеры кегля читаемы."""
    return round(p * 25.4 / 72.0, 4)


def esc(s):
    return sx.escape(str(s))


def swap_mark(x, y, size, back_fill=BG, stroke=ACCENT, solid=ACCENT):
    """Знак 02 · SWAP: две одинаковые формы внахлёст — настоящее и подменённое."""
    s = size / 32.0
    return (
        f'<g transform="translate({x},{y}) scale({s})">'
        f'<rect x="3" y="11" width="18" height="18" rx="5" fill="{solid}"/>'
        f'<rect x="11" y="3" width="18" height="18" rx="5" fill="{back_fill}" '
        f'stroke="{stroke}" stroke-width="2.4"/>'
        "</g>"
    )


def nfc_glyph(cx, cy, h, color, sw=1.5):
    """Бесконтактная метка: точка и три дуги. Мировая система 10x16."""
    s = h / 16.0
    return (
        f'<g transform="translate({cx},{cy}) scale({s})" fill="none" stroke="{color}" '
        f'stroke-width="{sw}" stroke-linecap="round">'
        f'<path d="M1.6 -5.4 A 7.4 7.4 0 0 1 1.6 5.4"/>'
        f'<path d="M4.2 -8.2 A 11.4 11.4 0 0 1 4.2 8.2"/>'
        f'<path d="M6.8 -11.0 A 15.4 15.4 0 0 1 6.8 11.0"/>'
        f'<circle cx="0" cy="0" r="0.9" fill="{color}" stroke="none"/>'
        "</g>"
    )


def mono(text, x, y, size, fill, weight=400, anchor="start", ls=None, opacity=None):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    o = f' opacity="{opacity}"' if opacity is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="JetBrains Mono" font-weight="{weight}" '
        f'font-size="{size}" fill="{fill}"{a}{l}{o}>{esc(text)}</text>'
    )


def sans(text, x, y, size, fill, weight=400, anchor="start", ls=None):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    return (
        f'<text x="{x}" y="{y}" font-family="Inter" font-weight="{weight}" '
        f'font-size="{size}" fill="{fill}"{a}{l}>{esc(text)}</text>'
    )


def line(x1, y1, x2, y2, stroke, w=0.2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{w}"/>'


def qr_group(x, y, size, url, dark, quiet=3):
    """Настоящий QR (не картинка): сегно даёт матрицу, я рисую её прямоугольниками.

    Ошибкоустойчивость Q — четверть площади можно испортить (матовая ламинация,
    отпечаток пальца), и метка всё ещё читается. Стилизованные QR с логотипом
    внутри для пластика не годятся: они читаются хуже ровно там, где их
    трогают пальцами.
    """
    try:
        import segno
    except ImportError:
        sys.exit("нужен segno: pip install --target=/tmp/pylibs segno "
                 "и PYTHONPATH=/tmp/pylibs")
    q = segno.make(url, error="q")
    m = [list(row) for row in q.matrix]
    n = len(m)
    total = n + 2 * quiet
    s = size / total
    parts = [f'<g transform="translate({x},{y})">',
             f'<rect width="{round(size,3)}" height="{round(size,3)}" fill="none"/>']
    for r, row in enumerate(m):
        for c, v in enumerate(row):
            if v:
                parts.append(
                    f'<rect x="{round((c + quiet) * s, 4)}" y="{round((r + quiet) * s, 4)}" '
                    f'width="{round(s + 0.004, 4)}" height="{round(s + 0.004, 4)}" fill="{dark}"/>'
                )
    parts.append("</g>")
    return "".join(parts)


def _lcg(seed):
    """Детерминированный «шум»: одна и та же карточка должна собираться
    одинаково при каждом прогоне, иначе макет нельзя утвердить — он меняется."""
    return (seed * 1103515245 + 12345) & 0x7FFFFFFF


def fake_value(val):
    """Правдоподобная подмена того же формата — то, что видит модель."""
    h = sum(ord(c) for c in val)
    if "@" in val:
        return f'kuznetsov.{h % 90 + 10}@example.com'
    if val.strip().startswith("+") or val.replace(" ", "").isdigit():
        return f'+7 9{h % 90 + 10:02d} {h % 900 + 100}-{h % 90 + 10:02d}-{h % 90 + 10:02d}'
    return f'primer-{h % 90 + 10}.example.com'


def mask_art(style, rect, val, y):
    """Чем закрыты контакты. Геометрия одна (bar_rects), исполнение разное —
    поэтому варианты можно честно сравнивать, а не перерисовывать заново."""
    x, yy, w, h = rect
    if style == "bars":                      # сплошная плашка — редакционная замазка
        return f'<rect x="{x}" y="{yy}" width="{w}" height="{h}" rx="0.5" fill="{ACCENT}"/>'
    if style == "pixel":                     # мозаика: значение рассыпано на квадраты
        cell, gap, out = 0.58, 0.26, []
        cols = max(1, int((w + gap) // (cell + gap)))
        rws = max(1, int((h + gap) // (cell + gap)))
        s = _lcg(int(x * 100) + len(val) * 7)
        for r in range(rws):
            for c in range(cols):
                s = _lcg(s)
                if s % 100 < 82:
                    out.append(f'<rect x="{round(x + c * (cell + gap), 3)}" '
                               f'y="{round(yy + r * (cell + gap), 3)}" width="{cell}" '
                               f'height="{cell}" rx="0.1" fill="{ACCENT}"/>')
        return "".join(out)
    if style == "scan":                      # растр: строки, как на сжатом скане
        out, step, th = [], 0.5, 0.2
        n = max(1, int(h // step))
        for r in range(n):
            out.append(f'<rect x="{x}" y="{round(yy + r * step, 3)}" width="{w}" '
                       f'height="{th}" rx="0.1" fill="{ACCENT}"/>')
        return "".join(out)
    if style == "double":                    # две одинаковые формы — язык знака SWAP
        d = 1.0
        return (f'<rect x="{round(x + d, 3)}" y="{round(yy - d, 3)}" width="{w}" height="{h}" '
                f'rx="0.5" fill="none" stroke="{ACCENT}" stroke-width="0.3"/>'
                f'<rect x="{x}" y="{yy}" width="{w}" height="{h}" rx="0.5" fill="{ACCENT}"/>')
    if style == "fake":                      # показать саму подмену, а не замазку
        return mono(fake_value(val), x, y, sz(pt(8.6)), ACCENT)
    raise ValueError(style)


def bar_rects(p):
    """Геометрия трёх плашек на лице — единственный источник истины для них.

    Ширина плашки считается от ДЛИНЫ реального значения: подмена совпадает по
    форме с настоящим, поэтому плашка не декоративная. Отсюда же берётся маска
    под spot UV — та же геометрия, а не перерисованная руками копия, которая
    разъедется с макетом при первой же правке телефона.
    """
    ROWF = sz(pt(8.6))
    x_val = L + 8.0
    rows = [p["tel"], p["mail"], p["web"]]
    y_rows = [vy(38.6), vy(43.2), vy(47.8)]
    out = []
    for val, y in zip(rows, y_rows):
        w = len(val) * 0.6 * ROWF
        out.append((round(x_val - 0.3, 3), round(y - ROWF * 0.78, 3),
                    round(w + 0.6, 3), round(ROWF * 1.28, 3)))
    return out


# ---------------------------------------------------------------------- FRONT
def front(p, sticker=False, number=None, style="bars"):
    """Тёмная сторона — «что видит модель». Контакты стоят под плашками.

    sticker=True — вариант для сценария «напечатать карты + наклеить метку
    самому»: в пустоте размечен круг Ø26 мм, куда клеится NFC-наклейка.
    Подписи, которые она перекрыла бы, в этом варианте убраны.

    number — строка вида «№ 004 / 50» для нумерованного тиража. По умолчанию
    номера нет: нумерация — опция, и стоит она цеху отдельного разговора.

    style — чем закрыты контакты: bars | pixel | scan | double | fake.
    """
    ROWF = sz(pt(8.6))
    word, name, title = sz(pt(15)), sz(pt(11)), sz(pt(6.5))
    lbl, sec = sz(pt(5)), sz(pt(4.6))
    claim = sz(pt(7))

    rows = [("tel", p["tel"]), ("mail", p["mail"]), ("web", p["web"])]
    y_rows = [vy(38.6), vy(43.2), vy(47.8)]
    x_lab, x_val = L, L + 8.0

    body = [f'<rect width="{CW}" height="{CH}" fill="{BG}"/>']
    # шапка
    body.append(swap_mark(L, vy(7.0), sz(5.6), back_fill=BG))
    body.append(sans("pseudex", L + 7.2, vy(11.9), word, TEXT, 700, ls="-0.03em"))
    body.append(mono("МАСКИРОВАНИЕ ПД", R - 0.8, vy(10.7), lbl, GHOST, 400, "end", "0.14em"))
    body.append(mono("ДЛЯ LLM-АГЕНТОВ", R - 0.8, vy(14.1), lbl, GHOST, 400, "end", "0.14em"))
    body.append(line(L, vy(16.6), R, vy(16.6), LINE_D))
    # имя
    body.append(sans(p["name"], L, vy(23.8), name, TEXT, 600, ls="-0.02em"))
    body.append(sans(p["title"], L, vy(28.0), title, DIM, 400))
    # раздел: то, что видит модель
    if sticker:
        body.append(f'<circle cx="{(L + R) / 2 + 3.0}" cy="{vy(38.0)}" r="{sz(12.5)}" fill="none" stroke="{LINE_D}" '
                    f'stroke-width="0.25" stroke-dasharray="1.2 1.2"/>')
        body.append(mono("NFC", (L + R) / 2 + 3.0, vy(37.4), sz(pt(5)), GHOST, 400, "middle", "0.16em"))
        body.append(mono("МЕСТО ПОД МЕТКУ Ø26", (L + R) / 2 + 3.0, vy(41.4), sz(pt(3.5)), GHOST, 400, "middle", "0.08em"))
    else:
        body.append(mono("ЧТО ВИДИТ МОДЕЛЬ", R - 0.8, vy(33.8), sec, GHOST, 400, "end", "0.16em"))
    # Свободное поле справа — не пустота под декор. Человек видит три замазанные
    # строки вместо телефона и задаёт один вопрос: почему? Здесь на него отвечает
    # суть продукта, и она же объясняет, почему контакты раскрыты на обороте.
    body.append(sans("Данные нужны", R - 0.8, vy(38.0), claim, MUTED, 400, "end"))
    body.append(sans("функциям, а не модели.", R - 0.8, vy(41.4), claim, MUTED, 400, "end"))
    # замаскированные контакты
    for (lab, val), y, rect in zip(rows, y_rows, bar_rects(p)):
        body.append(mono(lab, x_lab, y, ROWF, MUTED2))
        if style != "fake":
            body.append(mono(val, x_val, y, ROWF, GHOST_D))   # «данные» под плашкой
        body.append(mask_art(style, rect, val, y))
    if number:
        body.append(mono(number, R - 6.2, vy(49.2), sz(pt(4.4)), GHOST, 400, "end", "0.08em"))
    return "".join(body)


# ----------------------------------------------------------------------- BACK
def back(p):
    """Светлая сторона — «что видит инструмент». Контакты раскрыты."""
    ROWF = sz(pt(8.2))
    word, lbl = sz(pt(15)), sz(pt(5))
    x_lab, x_val = L, L + 7.6
    rows = [("tel", p["tel"]), ("mail", p["mail"]), ("web", p["web"])]
    y_rows = [vy(24.0), vy(29.4), vy(34.8)]

    body = [f'<rect width="{CW}" height="{CH}" fill="{PAPER}"/>']
    body.append(swap_mark(L, vy(7.0), sz(5.6), back_fill=PAPER, stroke=ACCENT_L, solid=ACCENT_L))
    body.append(sans("pseudex", L + 7.2, vy(11.9), word, INK, 700, ls="-0.03em"))
    body.append(mono("ЧТО ВИДИТ ИНСТРУМЕНТ", R - 0.8, vy(11.9), lbl, MUTED2, 400, "end", "0.14em"))
    body.append(line(L, vy(16.6), R, vy(16.6), LINE_L))

    for (lab, val), y in zip(rows, y_rows):
        body.append(mono(lab, x_lab, y, ROWF, MUTED2))
        body.append(f'<text x="{x_val}" y="{y}" font-family="JetBrains Mono" '
                    f'font-weight="500" font-size="{ROWF}" fill="{INK}">{esc(val)}</text>')

    body.append(line(L, vy(36.0), R, vy(36.0), LINE_L))
    # На бумаге единственный вход — камера. «Приложите телефон» здесь было бы
    # обещанием чипа, которого нет: инструкция обязана называть то действие,
    # которое человек может выполнить. Модуль QR — 0.36-0.40 мм, выше порога
    # читаемости и на бумаге, и на матовом пластике.
    body.append(qr_group(L, vy(37.0), sz(14.0), p["nfc_url"], INK, quiet=3))
    xr = 23.5
    body.append(mono("НАВЕДИТЕ КАМЕРУ", xr, vy(44.4), sz(pt(6.4)), INK, 500, "start", "0.06em"))
    body.append(mono("ОТКРОЕТСЯ ВИЗИТКА С КОНТАКТАМИ", xr, vy(48.4), sz(pt(5.0)), MUTED2, 400, "start", "0.04em"))
    body.append(mono("pseudex.ru", R - 0.8, vy(48.4), sz(pt(5.0)), GHOST, 400, "end", "0.04em"))
    return "".join(body)


# ------------------------------------------------------------------ SPOT UV
def spot_uv(p):
    """Маска под выборочный лак: только плашки, чистый чёрный #000, без фона.

    Цех просит маску отдельным файлом, когда лак локальный. Здесь нет ни фона,
    ни подписей, ни меток реза — всё, что в файле, попадёт под лак. Поэтому
    никаких пояснительных надписей: они бы тоже залакировались.
    """
    return "".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="0.5" fill="#000000"/>'
        for x, y, w, h in bar_rects(p)
    )


# --------------------------------------------------------------------- сборка
def wrap(body, guides=False, trim=False):
    """trim=True — файл ровно по резу (85.6 × 54), без вылетов.

    Часть карточных цехов просит «макет в размер карты», часть — «карта плюс
    2 мм на вылет». Оба файла собираются из одного тела, поэтому разойтись не
    могут; вылет не нужен только потому, что фон залит целиком и режется
    вместе с картой.
    """
    if trim:
        size = (TW, TH)
        box = f"{X0} {Y0} {TW} {TH}"
    else:
        size = (CW, CH)
        box = f"0 0 {CW} {CH}"
    g = ""
    if guides and not trim:
        # safe-зона — 3 мм от реза (отраслевой минимум), а контент у меня стоит на
        # 5 мм: на превью видно, что между текстом и реза есть воздух.
        si = 3.0
        g = (
            f'<g id="guides" fill="none">'
            f'<rect x="{BLEED}" y="{BLEED}" width="{TW}" height="{TH}" stroke="#00e5ff" stroke-width="0.15"/>'
            f'<rect x="{X0 + si}" y="{Y0 + si}" width="{TW - 2 * si}" height="{TH - 2 * si}" stroke="#ff00d4" stroke-width="0.15" stroke-dasharray="1 1"/>'
            f'<rect x="0.05" y="0.05" width="{CW-0.1}" height="{CH-0.1}" stroke="#00ff85" stroke-width="0.15"/>'
            f'<text x="{BLEED+0.5}" y="{BLEED-0.5}" font-family="JetBrains Mono" font-size="1.4" fill="#00e5ff">РЕЗ 85.6x54 · ВЫЛЕТ 2мм</text>'
            f'<text x="{X0+si+0.3}" y="{Y0+si-0.5}" font-family="JetBrains Mono" font-size="1.4" fill="#ff00d4">SAFE 3мм</text>'
            f'</g>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size[0]}mm" height="{size[1]}mm" '
        f'viewBox="{box}">{body}{g}</svg>'
    )


def render(svg_path, out, fmt, w=None):
    env = dict(os.environ, FONTCONFIG_FILE="/tmp/fonts.conf")
    cmd = ["rsvg-convert", "-f", fmt, "-o", str(out), str(svg_path)]
    if w:
        cmd += ["-w", str(w)]
    subprocess.run(cmd, check=True, env=env)


def mockup(people, suffix="paper"):
    """Лицо и оборот каждого — на тёмном фоне, для показа людям и типографии.

    Собирается здесь, а не «руками один раз»: иначе после правки телефона на
    визитке превью для показа остаётся со старым номером, и никто этого не
    замечает. Нет Pillow — не беда, печатные файлы уже собраны.
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError:
        print("мокап пропущен: нет Pillow")
        return
    sides = []
    for p in people:
        row = []
        for side in ("front", "back"):
            png = pathlib.Path("/tmp") / f"dsh-{p['slug']}-{side}-{suffix}.png"
            render(ROOT / "print" / f"card-{side}-{p['slug']}-{suffix}.svg", png, "png", w=1600)
            row.append(Image.open(png).convert("RGBA"))
        sides.append(row)
    w, h = sides[0][0].size
    pad, gap, gap_y, lab = 90, 60, 80, 74
    cols, rows = 2, len(sides)
    canvas = Image.new("RGB", (pad * 2 + cols * w + (cols - 1) * gap,
                               pad * 2 + rows * (h + lab) + (rows - 1) * gap_y), "#0b0b0e")
    dr = ImageDraw.Draw(canvas)
    try:
        fnt = ImageFont.truetype(str(ROOT / "fonts" / "Inter-SemiBold.ttf"), 40)
        fnt2 = ImageFont.truetype(str(ROOT / "fonts" / "Inter-Regular.ttf"), 30)
    except Exception:
        fnt = fnt2 = None
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], 26, fill=255)
    y = pad
    for r, (p, row) in enumerate(zip(people, sides)):
        if fnt:
            dr.text((pad, y), p["name"], font=fnt, fill="#e8e7ec")
            dr.text((pad + dr.textlength(p["name"] + "   ", font=fnt) + 0, y + 8),
                    p["title"], font=fnt2, fill="#74737e")
        y += lab
        for c, im in enumerate(row):
            x = pad + c * (w + gap)
            sh = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
            sh.paste(Image.new("RGBA", (w, h), (0, 0, 0, 170)), (40, 52))
            sh = sh.filter(ImageFilter.GaussianBlur(26))
            canvas.paste(sh, (x - 40, y - 40), sh)
            layer = im.copy()
            layer.putalpha(mask)
            canvas.paste(layer, (x, y), layer)
        y += h + gap_y
    canvas.save(ROOT / "preview" / f"card-mockup-{suffix}.png")
    print("ok card-mockup", suffix)


def save(name, body, trim_name=None):
    """Один макет — четыре артефакта: PDF с вылетами, PDF по резу, PNG 300 dpi
    и превью с направляющими. Имя несёт slug человека, чтобы комплекты не
    перепутались ни у цеха, ни у нас."""
    svg = ROOT / "print" / f"{name}.svg"
    svg.write_text(wrap(body), encoding="utf-8")
    render(svg, ROOT / "print" / f"{name}.pdf", "pdf")
    render(svg, ROOT / "preview" / f"{name}-300dpi.png", "png", w=1058)
    gsvg = ROOT / "preview" / f"{name}-guides.svg"
    gsvg.write_text(wrap(body, guides=True), encoding="utf-8")
    render(gsvg, ROOT / "preview" / f"{name}-guides.png", "png", w=1058)
    if trim_name:
        tsvg = ROOT / "print" / f"{trim_name}.svg"
        tsvg.write_text(wrap(body, trim=True), encoding="utf-8")
        render(tsvg, ROOT / "print" / f"{trim_name}.pdf", "pdf")
        render(tsvg, ROOT / "preview" / f"{trim_name}-300dpi.png", "png", w=1011)
    print("ok", name)


def main():
    (ROOT / "print").mkdir(exist_ok=True)
    (ROOT / "preview").mkdir(exist_ok=True)
    # Размер выносится в ИМЯ файла: у цеха на столе лежат два формата одного
    # макета, и перепутать их — это напечатать бумагу по карточной сетке.
    for fmt, tag in (("paper", "90x50"), ("plastic", "85x54")):
        set_format(fmt)
        for p in PEOPLE:
            s = p["slug"]
            save(f"card-front-{s}-{fmt}", front(p), f"card-front-{s}-{fmt}-{tag}")
            save(f"card-back-{s}-{fmt}", back(p), f"card-back-{s}-{fmt}-{tag}")
            m = ROOT / "print" / f"spot-uv-mask-{s}-{fmt}.svg"
            m.write_text(wrap(spot_uv(p)), encoding="utf-8")
            render(m, ROOT / "print" / f"spot-uv-mask-{s}-{fmt}.pdf", "pdf")
            render(m, ROOT / "preview" / f"spot-uv-mask-{s}-{fmt}.png", "png", w=1058)
            print("ok spot-uv-mask", s, fmt)
        mockup(PEOPLE, fmt)
    print("поля (мм):", dict(trim=(TW, TH), bleed=BLEED, safe=(round(R - L, 2), round(BOT - T, 2))))


if __name__ == "__main__":
    main()
