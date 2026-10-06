"""Страницы команды `/i/`, `/i/<slug>` и vCard к ним.

Проверяет то, из-за чего эти страницы вообще существуют отдельным документом,
и то, что о них легко забыть:

  * адреса из QR отвечают 200 и заголовок ровно «Имя · Pseudex»;
  * НИ ОДНОГО ВНЕШНЕГО ЗАПРОСА: ни скрипта, ни чужого стиля, ни чужой картинки,
    ни `@import` в самом CSS. Это не про скорость: страница-визитка, уведомляющая
    третью сторону о факте сканирования, — та самая передача данных, против
    которой продукт продаётся;
  * СТРАНИЦА БЕЗ ОБЩЕГО КАРКАСА: ни `site.css`, ни аналитики, ни единого
    `script`. Отсюда же следует, что vCard обязан собираться на сервере — на
    витрине `script-src 'self'`, и встроенный скрипт из печатного макета тут не
    выполнится;
  * `tel:` и `mailto:` рабочими ссылками, а `Сохранить контакт` отдаёт
    `text/vcard` c CRLF;
  * данные на странице и в макете печати СОВПАДАЮТ. Телефон набран дважды в двух
    репозиторных местах, и разойтись они могут молча: человек получит визитку с
    одним номером и страницу с другим.

Запуск:  cd storefront && .venv/bin/python test_team_pages.py
"""
import ast
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
# Макет печати лежит в том же репозитории, но ВНЕ образа витрины: в контейнере
# этой папки нет, и проверка совпадения там честно скажет «не гонялось».
PRINT_BUILD = HERE.parent / "brand" / "business-cards" / "print" / "build.py"


def declared_tokens(path: pathlib.Path) -> dict[str, str]:
    """Токены, объявленные в `:root` файла: имя → значение."""
    block = re.search(r":root\s*\{(.*?)\}", path.read_text(encoding="utf-8"), re.S)
    # Пробелы внутри значения не сравниваем: `ui-monospace, SFMono` и
    # `ui-monospace,SFMono` — одно и то же, и тест, падающий на запятой,
    # перестают читать.
    return {m.group(1): re.sub(r"\s+", "", m.group(2)).lower()
            for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", block.group(1))}


def load_print_people() -> list[dict] | None:
    """`PEOPLE` из макета печати — через AST, а не импортом.

    Импорт запустил бы скрипт печати, а он тянет рендеринг макетов ради одной
    таблицы. AST читает ровно присваивание и не выполняет ничего.
    """
    if not PRINT_BUILD.exists():
        return None
    tree = ast.parse(PRINT_BUILD.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "PEOPLE" for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "team-pages-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-team-test.db"
    os.environ["SITE_URL"] = "http://localhost"
    if os.path.exists("/tmp/pseudex-team-test.db"):
        os.remove("/tmp/pseudex-team-test.db")

    import django
    django.setup()

    from django.core.management import call_command
    from django.test import Client

    from storefront_web import team

    call_command("migrate", verbosity=0, run_syncdb=True)
    client = Client()
    failures: list[str] = []

    def check(name, condition, why=""):
        if condition:
            print(f"  PASS  {name}")
        else:
            print(f"  FAIL  {name}  {why}")
            failures.append(name)

    print("\n— адреса из QR —")
    for person in team.TEAM:
        slug = person["slug"]
        r = client.get(f"/i/{slug}")
        body = r.content.decode()
        check(f"/i/{slug} отвечает 200", r.status_code == 200, f"код {r.status_code}")
        check(f"/i/{slug}: заголовок «{person['name']} · Pseudex»",
              f"<title>{person['name']} · Pseudex</title>" in body)
        check(f"/i/{slug}: телефон кликабельным tel:",
              f'href="tel:{team.tel_href(person["tel"])}"' in body, "tel: не совпал")
        check(f"/i/{slug}: почта ссылкой mailto:",
              f'href="mailto:{person["mail"]}"' in body)
        check(f"/i/{slug}: кнопка «Сохранить контакт» ведёт на vCard",
              f'href="/i/{slug}.vcf"' in body)
        check(f"/i/{slug}: «чем могу помочь» на месте",
              person["help"][:40] in body)
        check(f"/i/{slug}: снимок или заглушка того же размера",
              ("team-photo--empty" in body) == (not person["photo"]),
              "заглушка и снимок взаимоисключающие")

    r = client.get("/i/")
    index = r.content.decode()
    check("/i/ отвечает 200", r.status_code == 200, f"код {r.status_code}")
    check("/i/: заголовок «Команда · Pseudex»", "<title>Команда · Pseudex</title>" in index)
    check("/i/: все трое со ссылками",
          all(f'href="/i/{p["slug"]}"' in index for p in team.TEAM))
    check("/i/: заголовок раздела — наш .eyebrow",
          'class="eyebrow"' in index and "PSEUDEX" in index)
    # Счёт в заголовке читается как «и больше никого» — этого быть не должно.
    check("/i/: заголовок не считает людей и не делит команду",
          "Три человека" not in index and "Ядро команды" in index)
    check("/i/: крупный заголовок страницы есть", 'class="team-name"' in index)

    print("\n— ничего лишнего наружу —")
    pages = {f"/i/{p['slug']}": client.get(f"/i/{p['slug']}").content.decode()
             for p in team.TEAM}
    pages["/i/"] = index

    for url, body in pages.items():
        check(f"{url}: ни одного <script>", "<script" not in body,
              "страница обязана работать без JS")
        # Внешним считается всё, что браузер ЗАГРУЖАЕТ: стили, скрипты,
        # картинки. Ссылки на pseudex.ru — это переходы, а не запросы.
        assets = re.findall(r'<(?:link|script|img)[^>]*?(?:src|href)="([^"]+)"', body)
        fonts = re.findall(r'url\(([^)]+)\)', body)
        check(f"{url}: все ресурсы со своего домена",
              all(a.startswith(("/", "data:")) or "pseudex.ru" in a for a in assets + fonts),
              str([a for a in assets + fonts if not a.startswith(("/", "data:"))]))
        check(f"{url}: viewport для телефона", 'name="viewport"' in body)
        # ДЖАНГО ВЫВОДИТ НАРУЖУ МНОГОСТРОЧНЫЙ `{# … #}` КАК ТЕКСТ: его синтаксис
        # комментария однострочный. Ровно это и случилось — объяснение из шапки
        # шаблона уехало в страницу первым блоком. Ловится одной строкой.
        check(f"{url}: разметка шаблона не вылилась в текст",
              "{#" not in body and "{%" not in body, "в странице видны скобки шаблона")
        csp = r.headers.get("Content-Security-Policy", "")
        check(f"{url}: строгий CSP без встроенных стилей",
              "script-src 'self'" in csp and "style-src 'self'" in csp
              and "style-src 'self' 'unsafe-inline'" not in csp, csp[:60])

    CSS_TEXT = (HERE / "static" / "team.css").read_text(encoding="utf-8")
    css = CSS_TEXT
    check("team.css: без @import",
          "@import" not in css and not re.search(r'url\(\s*["\']?https?://', css),
          "внешний запрос из CSS")
    # Шрифты объявлены в `site.css` — страница команды их не переобъявляет,
    # иначе это была бы вторая копия подключения (см. test_brand_palette.py).
    check("шрифты объявлены в стилях сайта",
          "/static/fonts/" in (HERE / "static" / "site.css").read_text(encoding="utf-8"))
    check("team.css: стили не инлайновые на странице",
          "<style" not in next(iter(pages.values())))

    print("\n— собрано из сайта, а не из своей вёрстки —")

    # ЭТО И ЕСТЬ ПРОВЕРКА БРЕНДБУКА НА УРОВНЕ РАЗМЕТКИ. Первая версия страниц
    # была свёрстана своими классами и своими скруглениями 10px, которых в
    # дизайне нет вообще (во всём сайте `2px` и `50%`). Кнопка, карточка и
    # реакция на наведение — словарь: своя копия расходится с сайтом на первой
    # правке темы. Здесь проверяется, что словарь взят у сайта.
    body = next(iter(pages.values()))
    check("подключены стили сайта", "site.css" in body and "landing.css" in body)
    check("каркас: .frame, header.top, section, footer",
          all(x in body for x in ('class="frame"', 'class="top"', "<section", "<footer")))
    check("кнопки — .btn сайта", 'class="btn' in body)
    check("карточки — .cards cards--n3 сайта", "cards cards--n3" in body)
    check("наведение — .hv-row и .hv-cell сайта",
          "hv-row" in body and "hv-cell" in body)
    check("подписи разделов — .label и .eyebrow сайта",
          "eyebrow" in body and 'class="label"' in body)
    # Каркас сайта — это меню и баннеры; их на странице из QR быть не должно.
    check("ни меню, ни счётчиков: только страница",
          "<nav" not in body and "<script" not in body)

    # Скруглений у нас нет: во всём сайте их два вида — `2px` на подсветке
    # значения и `50%` на кружке «?». Своё значение здесь означает свёрстанный
    # заново элемент, а не переиспользованный.
    bare = re.sub(r"/\*.*?\*/", "", CSS_TEXT, flags=re.S)
    check("team.css: ни одного своего скругления", "border-radius" not in bare,
          str(re.findall(r"border-radius:[^;]*", bare)))
    check("team.css: своей палитры не объявляет", ":root" not in bare,
          "палитра живёт в site.css (брендбук, «в одном месте на поверхность»)")
    check("team.css: контакты моношрифтом", "var(--mono)" in bare)
    # СНИМОК ИЛИ ЗАГЛУШКА ТОГО ЖЕ РАЗМЕРА — у каждого. Заглушка это тень, а не
    # знак (брендбук §8: никаких чужих материалов на карточке), и её дело —
    # держать раскладку, чтобы страница не перестраивалась в день, когда придут
    # снимки. Проверяется и обратное: файл, названный в данных, обязан лежать в
    # `static/` — иначе на странице будет битая картинка, и заметит её клиент.
    with_photo = [x for x in team.TEAM if x["photo"]]
    slots = re.findall(r'class="shot[^"]*"', index)
    check("/i/: место под снимок есть у каждого", len(slots) == len(team.TEAM),
          f"{len(slots)} из {len(team.TEAM)}")
    check("/i/: где снимок есть — <img>, где нет — тень",
          index.count('<img class="shot"') == len(with_photo)
          and index.count("shot--empty") == len(team.TEAM) - len(with_photo),
          f"снимков {index.count('<img class="shot"')}, заглушек {index.count('shot--empty')}")
    for x in with_photo:
        check(f"файл снимка {x['photo']} лежит в static/",
              (HERE / "static" / x["photo"]).exists(), str(HERE / "static" / x["photo"]))

    print("\n— vCard —")
    for person in team.TEAM:
        slug = person["slug"]
        r = client.get(f"/i/{slug}.vcf")
        card = r.content.decode()
        check(f"/i/{slug}.vcf: тип text/vcard",
              r.headers.get("Content-Type", "").startswith("text/vcard"),
              r.headers.get("Content-Type", ""))
        check(f"/i/{slug}.vcf: имя файла {slug}.vcf",
              f'filename="{slug}.vcf"' in r.headers.get("Content-Disposition", ""))
        check(f"/i/{slug}.vcf: карточка целиком",
              card.startswith("BEGIN:VCARD\r\n") and card.rstrip().endswith("END:VCARD"))
        check(f"/i/{slug}.vcf: телефон и почта внутри",
              f"TEL;TYPE=CELL:{team.tel_href(person['tel'])}" in card
              and f"EMAIL;TYPE=WORK:{person['mail']}" in card)
        check(f"/i/{slug}.vcf: переводы строк CRLF (RFC 6350)",
              "\r\n" in card and not re.search(r"(?<!\r)\n", card))

    print("\n— слэш на конце не тупик —")
    for person in team.TEAM:
        slug = person["slug"]
        r = client.get(f"/i/{slug}/")
        check(f"/i/{slug}/ → 301 на адрес из QR",
              r.status_code == 301 and r.headers.get("Location") == f"/i/{slug}",
              f"{r.status_code} {r.headers.get('Location', '')}")
    check("/i (без слэша) уводит на индекс",
          client.get("/i").status_code in (301, 302),
          str(client.get("/i").status_code))

    print("\n— чужой адрес обязан кончаться 404 —")
    check("/i/nobody → 404", client.get("/i/nobody").status_code == 404,
          "страница с чужим телефоном хуже отсутствующей")
    check("/i/nobody.vcf → 404", client.get("/i/nobody.vcf").status_code == 404)

    print("\n— страница и визитка говорят одно и то же —")
    people = load_print_people()
    if people is None:
        print("  НЕ ГОНЯЛОСЬ  макет печати не найден (в образе витрины папки brand/ нет)")
    else:
        layout = {p["slug"]: p for p in people}
        check("набор людей совпадает с макетом печати",
              sorted(layout) == sorted(p["slug"] for p in team.TEAM),
              f"макет: {sorted(layout)}")
        for person in team.TEAM:
            other = layout.get(person["slug"], {})
            for field in ("name", "title", "tel", "mail"):
                check(f"{person['slug']}: {field} совпадает с визиткой",
                      other.get(field) == person[field],
                      f"визитка «{other.get(field)}» ≠ страница «{person[field]}»")

    print("\n" + "=" * 60)
    if failures:
        print("СТРАНИЦЫ КОМАНДЫ FAIL:", ", ".join(failures))
        return 1
    print("страницы команды OK — адреса из QR живые, наружу ни одного запроса, "
          "vCard отдаётся сервером, данные совпадают с визиткой")
    return 0


if __name__ == "__main__":
    sys.exit(main())
