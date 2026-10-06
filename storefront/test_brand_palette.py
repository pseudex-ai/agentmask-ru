"""Палитра и шрифты: один набор на все наши страницы, а не свой на каждый файл.

Брендбук (`brand/README.md`, «Палитра») и `BRANDBOOK.md` §2 говорят одно и то же:
палитра живёт CSS-переменными «в одном месте на поверхность, не россыпью по
разметке». Файлов у нас теперь несколько — `site.css`, `admin-pseudex.css`,
`team.css`, — и каждый из них соблазн завести своё имя или своё значение.
Расходятся такие копии молча: половина элементов одного цвета, половина
другого, и замечает это клиент, а не мы.

Проверяются три вещи, каждая — на всех CSS витрины сразу:

  * ИМЯ ИЗ `site.css` НЕСЁТ ЕГО ЖЕ ЗНАЧЕНИЕ. Свои имена файл заводить может
    (`admin-pseudex.css` обязан: у Django свои переменные), но переопределять
    чужое имя другим цветом — нет;
  * КАЖДЫЙ `var(--…)` ГДЕ-ТО ОБЪЯВЛЕН. Опечатка в имени — `var(--line2)` вместо
    `var(--line-2)` — не ошибка синтаксиса: свойство просто теряет цвет, и
    страница выглядит почти правильно. Это единственный способ поймать её до
    того, как её увидит человек;
  * НИ ОДНОГО ВНЕШНЕГО ЗАПРОСА. Шрифты и картинки — со своего домена: и CSP
    витрины, и работа в контуре без интернета.

Палитра движка (`prototype/pseudex/localui/static/app.css`) здесь не
проверяется: это другая поверхность и другой образ, у неё свой файл и своя
копия палитры по тому же правилу брендбука.

Запуск:  cd storefront && .venv/bin/python test_brand_palette.py
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
STATIC = HERE / "static"
SITE = STATIC / "site.css"


def strip_comments(css: str) -> str:
    """Комментарии в сторону: в них встречаются и `:root`, и имена переменных."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def tokens(css: str) -> dict[str, str]:
    """Объявленные токены из `:root`. Пробелы внутри значения не значимы."""
    out: dict[str, str] = {}
    for block in re.finditer(r":root[^{]*\{(.*?)\}", strip_comments(css), re.S):
        for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", block.group(1)):
            out[m.group(1)] = re.sub(r"\s+", "", m.group(2)).lower()
    return out


# ИМЕНА, СОВПАДАЮЩИЕ С САЙТОМ НЕ ПО ОШИБКЕ. `--header-bg` — переменная ТЕМЫ
# DJANGO (фон шапки админки), и админка вправе задать её сама: её шапка
# непрозрачная, а у сайта — залипающая с блюром. Оба имени значат «фон шапки»,
# поэтому совпадение неизбежно, а разное значение — решение, а не дрейф.
# Список поимённый и с причиной: всё, чего в нём нет, обязано совпадать.
DELIBERATE = {"admin-pseudex.css": {"--header-bg"}}


def main() -> int:
    site = tokens(SITE.read_text(encoding="utf-8"))
    files = sorted(p for p in STATIC.glob("*.css"))
    failures: list[str] = []

    def check(name, condition, why=""):
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name}  {why}")
            failures.append(name)

    print(f"\n— палитра: {len(files)} файлов против site.css ({len(site)} токенов) —")
    for path in files:
        css = path.read_text(encoding="utf-8")
        mine = tokens(css)
        if not mine:
            continue
        shared = {k: v for k, v in mine.items()
                  if k in site and k not in DELIBERATE.get(path.name, set())}
        diverged = [f"{k}: {v} ≠ {site[k]}" for k, v in shared.items() if v != site[k]]
        check(f"{path.name}: общие имена не расходятся с site.css",
              not diverged, "; ".join(diverged))
        own = sorted(set(mine) - set(site))
        print(f"        (своих имён: {len(own)}"
              + (f" — {', '.join(own[:4])}…)" if len(own) > 4 else
                 (f" — {', '.join(own)})" if own else ")")))

    print("\n— каждый var(--…) где-то объявлен —")
    for path in files:
        css = path.read_text(encoding="utf-8")
        declared = set(tokens(css)) | set(site) | set(re.findall(r"(--[\w-]+)\s*:", strip_comments(css)))
        unresolved = sorted({
            m.group(1) for m in re.finditer(r"var\(\s*(--[\w-]+)\s*\)", strip_comments(css))
            if m.group(1) not in declared
        })
        check(f"{path.name}: нет ссылок на необъявленное", not unresolved, str(unresolved))

    print("\n— ни одного внешнего запроса —")
    for path in files:
        css = strip_comments(path.read_text(encoding="utf-8"))
        external = re.findall(r"url\(\s*['\"]?https?://", css)
        check(f"{path.name}: нет внешних url()", not external, str(external))
        check(f"{path.name}: нет @import", "@import" not in css)

    print("\n— скруглений у нас нет —")
    # ВО ВСЁМ САЙТЕ `border-radius` ВСТРЕЧАЕТСЯ ДВА РАЗА: `2px` на подсветке
    # найденного значения и `50%` на кружке «?». Всё остальное — прямоугольники.
    # Своё значение здесь означает элемент, свёрстанный заново, вместо взятого у
    # сайта; именно так страницы команды и разошлись с сайтом в первой версии.
    ALLOWED = {"0", "0px", "2px", "50%"}
    for path in files:
        values = re.findall(r"border-radius:\s*([^;!]+)",
                            strip_comments(path.read_text(encoding="utf-8")))
        odd = sorted({v.strip() for v in values if v.strip() not in ALLOWED})
        check(f"{path.name}: только 0 / 2px / 50%", not odd, str(odd))

    fonts = sorted(p.name for p in (STATIC / "fonts").glob("*.woff2"))
    check("шрифты лежат у нас", len(fonts) >= 4, str(fonts))
    for path in files:
        css = path.read_text(encoding="utf-8")
        for src in re.findall(r"src:\s*url\('([^']+)'\)", css):
            check(f"{path.name}: шрифт {src.split('/')[-1]} с нашего домена",
                  src.startswith("/static/"), src)

    print("\n" + "=" * 60)
    if failures:
        print("ПАЛИТРА FAIL:", "; ".join(failures))
        return 1
    print("палитра OK — имена и значения из site.css, ссылок в никуда нет, "
          "наружу ни одного запроса")
    return 0


if __name__ == "__main__":
    sys.exit(main())
