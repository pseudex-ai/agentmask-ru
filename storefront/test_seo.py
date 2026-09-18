"""ЧТО ПОИСКОВИК ВИДИТ НА САЙТЕ — И ЧЕГО НЕ ДОЛЖЕН ВИДЕТЬ.

ЗАЧЕМ ПРОВЕРКА. Всё в этом файле ломается МОЛЧА и снаружи: канонический адрес,
уехавший на стенд, битая карта сайта, кабинет, попавший в выдачу, цена в
разметке для робота, разошедшаяся с ценой на экране. Ни одно из этого не видно
ни на странице, ни в логе — видно в чужой выдаче через несколько недель, когда
чинить поздно.

САМАЯ ДОРОГАЯ ИЗ НИХ — ПОСЛЕДНЯЯ. `schema.org` ждёт цену ЧИСЛОМ, а русская
локаль печатает «3 900» с неразрывным пробелом внутри; такой оффер поисковик
выбрасывает целиком, и понять это можно только по отсутствию цены в выдаче.

ВТОРАЯ ПО ЦЕНЕ — ИНДЕКСАЦИЯ КАБИНЕТА. Там на экране префиксы ключей, суммы
счетов и названия чужих компаний. Решение об этом принимается в ОДНОМ месте
(`indexable` в контексте шаблона), и здесь проверяется, что оно доходит до
страницы.

Запуск:  cd storefront && .venv/bin/python test_seo.py
"""
import json
import os
import pathlib
import re
import struct
import sys

_SITE = "https://pseudex.test"


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "seo-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-seo-test.db"
    os.environ["SITE_URL"] = _SITE
    os.environ["PSEUDEX_SITE_URL"] = _SITE
    if os.path.exists("/tmp/pseudex-seo-test.db"):
        os.remove("/tmp/pseudex-seo-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    from django.test.utils import setup_test_environment
    setup_test_environment()
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from django.conf import settings
    from django.test import Client
    from billing.models import Plan

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    client = Client()

    # ── robots.txt ─────────────────────────────────────────────────────────
    robots = client.get("/robots.txt")
    body = robots.content.decode()
    check(robots.status_code == 200 and robots["Content-Type"].startswith("text/plain"),
          "robots.txt отдаётся текстом", f"{robots.status_code} {robots['Content-Type']}")
    check(f"Sitemap: {_SITE}/sitemap.xml" in body,
          "и называет карту сайта абсолютным адресом")
    for closed in ("/app/", f"/{settings.ADMIN_PATH}/", "/accounts/"):
        check(f"Disallow: {closed}" in body, f"закрытое не обходится: {closed}")
    check("Clean-param:" in body and "utm_source" in body,
          "метки кампаний склеиваются, а не плодят дубли главной",
          "каждая ссылка из рекламы иначе — отдельный адрес с тем же содержимым")

    # ── sitemap.xml: каждый названный адрес ДЕЙСТВИТЕЛЬНО открывается ──────
    sitemap = client.get("/sitemap.xml")
    check(sitemap.status_code == 200, "sitemap.xml отдаётся", str(sitemap.status_code))
    xml = sitemap.content.decode()
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(xml)
        valid = True
    except ET.ParseError as error:
        valid = False
        print(f"      разбор не удался: {error}")
    check(valid, "и это разбираемый XML")
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    check(len(locs) >= 5, f"адресов в карте: {len(locs)}")
    broken = []
    for loc in locs:
        path = loc[len(_SITE):] or "/"
        code = client.get(path).status_code
        if code != 200:
            broken.append(f"{path} -> {code}")
    check(not broken, "каждый адрес из карты открывается", str(broken))

    # ── адрес со слэшем на конце — не тупик ───────────────────────────────
    # Публичные страницы объявлены БЕЗ слэша, и таков же их канонический адрес.
    # `/detection/` не совпадал ни с одним маршрутом и отдавал 404: адрес,
    # скопированный из письма со слэшем, и внешняя ссылка со слэшем вели в
    # никуда. Проверка идёт ПО КАРТЕ САЙТА, а не по списку внутри теста: список
    # пришлось бы дополнять вместе с каждой новой страницей, и он бы отстал
    # молча — то есть тест перестал бы что-либо значить ровно тогда, когда стал
    # бы нужен.
    slashed = []
    for loc in locs:
        path = loc[len(_SITE):] or "/"
        if path == "/":
            continue
        r = client.get(path + "/")
        if r.status_code != 301 or r.get("Location", "") != path:
            slashed.append(f"{path}/ -> {r.status_code} {r.get('Location', '')}")
    check(not slashed,
          "у каждого адреса из карты слэш уводит на канонический постоянным редиректом",
          str(slashed))

    # Query НЕ ТЕРЯЕТСЯ. `/detection/?utm_source=…` — обычный случай, а не
    # экзотика: ровно такую ссылку собирает рекламный кабинет, и редирект,
    # срезающий строку запроса, обнулил бы разметку кампании.
    tagged_slash = client.get("/detection/?utm_source=yandex")
    check(tagged_slash.status_code == 301
          and tagged_slash.get("Location", "") == "/detection?utm_source=yandex",
          "редирект сохраняет строку запроса",
          f"{tagged_slash.status_code} {tagged_slash.get('Location', '')}")

    # ЗАКОННЫЙ СЛЭШ НЕ СРЕЗАЕТСЯ — и это самая опасная ошибка из возможных.
    # Общее правило «убрать слэш у всего» превратило бы `/accounts/login/` в
    # `/accounts/login`, `APPEND_SLASH` вернул бы слэш обратно, и браузер ходил
    # бы по кругу. Здесь эти адреса объявлены СО слэшем, поэтому редиректа быть
    # не должно.
    for keep in ("/accounts/login/", "/app/"):
        r = client.get(keep)
        looped = (r.status_code == 301
                  and r.get("Location", "").rstrip("/") == keep.rstrip("/"))
        check(not looped, f"законный слэш не срезается: {keep}",
              f"{r.status_code} -> {r.get('Location', '')}")

    # ЧУЖОЙ АДРЕС НЕ ПРЕВРАЩАЕТСЯ В РЕДИРЕКТ. `/wp-admin/` не разрешается ни в
    # каком виде, и подмена ему 404 на 301 была бы услугой сканеру.
    scanner = client.get("/wp-admin/")
    check(scanner.status_code == 404,
          "неизвестный адрес со слэшем остаётся 404, а не редиректом",
          str(scanner.status_code))

    # POST НЕ ПЕРЕИГРЫВАЕТСЯ. 301 на POST клиенты переигрывают как GET, и
    # конфигуратор (`/demand`) потерял бы тело запроса — то есть запись, ради
    # которой он существует, не состоялась бы, а ответ был бы 301.
    posted = client.post("/demand/", data="{}", content_type="application/json")
    check(posted.status_code == 404,
          "POST со слэшем не подменяется редиректом на GET", str(posted.status_code))

    # ── иконка для выдачи ─────────────────────────────────────────────────
    # Браузер и робот вроде YandexFavicons просят `/favicon.ico` сами, без
    # ссылки на него. Без ответа это 404 — а 404 кормит счётчик fail2ban.
    # ИКОНКА ОТДАЁТСЯ, А НЕ ПЕРЕАДРЕСУЕТСЯ. Здесь стоял 301 на SVG, и Вебмастер
    # назвал это ошибкой ОТДЕЛЬНОЙ СТРОКОЙ своей таблицы — «файл перенаправляет
    # на другой адрес»; проверка 17.09.2026 ответила «Добавьте файл favicon в
    # формате SVG или размером 120 × 120 пикселей». То есть эта проверка
    # стерегла ровно то поведение, на которое жаловался робот.
    favicon = client.get("/favicon.ico")
    check(favicon.status_code == 200
          and favicon["Content-Type"] == "image/x-icon",
          "favicon.ico отдаётся файлом с кодом 200, а не редиректом",
          f"{favicon.status_code} {favicon.get('Content-Type', '')}")
    # `FileResponse` потоковый, поэтому тело собирается из `streaming_content`:
    # у него нет `.content`, и обращение к нему падает — а падение в проверке
    # выглядит как красный тест там, где всё в порядке.
    icon_bytes = b"".join(favicon.streaming_content)
    check(len(icon_bytes) > 500 and icon_bytes[:4] == b"\x00\x00\x01\x00",
          "и это настоящая иконка ICO, а не пустышка",
          f"{len(icon_bytes)} Б, начало {icon_bytes[:4]!r}")

    # РАЗМЕР ИЗ ВЕКТОРА НЕ ВЫВОДИТСЯ РОБОТОМ. Требование — 120×120, 32×32 или
    # 16×16; SVG только с `viewBox` размера не несёт, и в браузере он при этом
    # выглядит совершенно правильно.
    vector = pathlib.Path(__file__).resolve().parent / "static" / "favicon.svg"
    svg = vector.read_text(encoding="utf-8")
    check('width="32"' in svg and 'height="32"' in svg,
          "у векторной иконки размер задан явно, а не только viewBox")
    # РАЗМЕР ЧИТАЕТСЯ ИЗ ЗАГОЛОВКА PNG, А НЕ ЧЕРЕЗ Pillow. Pillow намеренно не
    # в `requirements.txt` — он нужен только рисовалке, а боевой образ не должен
    # носить её ради картинки, которая меняется раз в год. Первые 24 байта PNG —
    # сигнатура и IHDR, и там ширина с высотой лежат по фиксированным смещениям.
    for name, size in (("favicon-120.png", (120, 120)),
                       ("favicon-180.png", (180, 180))):
        raster = pathlib.Path(__file__).resolve().parent / "static" / name
        raw = raster.read_bytes()
        check(raw[:8] == b"\x89PNG\r\n\x1a\n" and raw[12:16] == b"IHDR",
              f"{name} — настоящий PNG", raw[:16])
        got = struct.unpack(">II", raw[16:24])
        check(got == size, f"{name} действительно {size[0]}×{size[1]}", str(got))

    # ТРИ ССЫЛКИ — ОДНА И ТА ЖЕ КАРТИНКА. Вебмастер предупреждает: при
    # нескольких ссылках робот вправе взять любую. Дублировать форматы можно,
    # только если все они нарисованы из одного исходника.
    head = client.get("/").content.decode()
    for needle, why in (
            ('rel="icon" href="/static/favicon', "векторная"),
            ('type="image/svg+xml"', "с правильным типом для вектора"),
            ('type="image/png" sizes="120x120"', "растровая 120×120"),
            ('href="/favicon.ico" type="image/x-icon"', "корневой .ico"),
            ('rel="apple-touch-icon"', "иконка для закладок Apple")):
        check(needle in head, f"в <head> объявлена {why}", needle)

    # ── подтверждение прав в Вебмастере ───────────────────────────────────
    # Тег выглядит мусором ровно до дня, когда его удаляют «при рефакторинге
    # `<head>`»: с ним связаны карта сайта и переобход страниц, а без них новых
    # адресов в выдаче не появляется. Ошибка молчаливая и снаружи — заметить её
    # можно только в чужой панели Вебмастера, через недели.
    #
    # КЛЮЧ СВЕРЯЕТСЯ ПОСИМВОЛЬНО, А НЕ ПО НАЛИЧИЮ ТЕГА, и вот почему это не
    # педантизм. 17.09.2026 в TXT-запись домена ушёл ключ с ЛИШНЕЙ БУКВОЙ в
    # середине (`…422f`**`da`**`3a4da` вместо `…422f`**`d`**`3a4da`), и Вебмастер
    # отвечал «Нет записи с ключом для подтверждения». Заметить это глазами
    # практически нельзя, а `dig` показывал «запись на месте» — потому что
    # сверялся с тем же неверным ожиданием. Проверка на наличие тега пропустила
    # бы точно такую же опечатку в шаблоне.
    _VERIFICATION_KEY = "20aee3422fd3a4da"
    landing = client.get("/").content.decode()
    tag = re.search(r'<meta name="yandex-verification" content="([^"]*)"', landing)
    check(tag is not None, "главная подтверждает права в Вебмастере тегом",
          "без него не добавить карту сайта и не запустить переобход")
    check(tag is not None and tag.group(1) == _VERIFICATION_KEY,
          "и ключ в теге совпадает с ключом домена посимвольно",
          f"в теге {tag.group(1) if tag else '—'!r}, ожидается "
          f"{_VERIFICATION_KEY!r} — ключ, отличающийся на символ, не подтверждает "
          f"ничего, а выглядит рабочим")
    check(f'content="{_VERIFICATION_KEY}"' in client.get("/detection").content.decode(),
          "и тег живёт в общем `<head>`, а не в одном шаблоне",
          "иначе проверка пройдёт на главной и упадёт на остальных")

    # ── публичные страницы: свой заголовок и своё описание ────────────────
    seen_titles, seen_descr = {}, {}
    for loc in locs:
        path = loc[len(_SITE):] or "/"
        page = client.get(path).content.decode()
        title = re.search(r"<title>(.*?)</title>", page, re.S)
        descr = re.search(r'name="description" content="(.*?)"', page, re.S)
        check(title is not None and descr is not None,
              f"{path}: заголовок и описание на месте")
        if not (title and descr):
            continue
        seen_titles.setdefault(title.group(1), []).append(path)
        seen_descr.setdefault(descr.group(1), []).append(path)
        canonical = re.search(r'rel="canonical" href="(.*?)"', page)
        check(canonical is not None and canonical.group(1) == f"{_SITE}{path}",
              f"{path}: канонический адрес абсолютный и свой",
              canonical.group(1) if canonical else "нет")
        check('name="robots" content="index' in page,
              f"{path}: разрешена к индексации")
    dupes = {t: p for t, p in seen_titles.items() if len(p) > 1}
    check(not dupes, "заголовки не повторяются между страницами", str(dupes))
    dupes = {t: p for t, p in seen_descr.items() if len(p) > 1}
    check(not dupes, "описания не повторяются между страницами", str(dupes))

    # ── метка кампании НЕ меняет канонический адрес ───────────────────────
    tagged = client.get("/?utm_source=yandex&utm_medium=cpc").content.decode()
    canonical = re.search(r'rel="canonical" href="(.*?)"', tagged).group(1)
    check(canonical == f"{_SITE}/",
          "ссылка из рекламы указывает на чистый адрес, а не на себя", canonical)

    # ── закрытые страницы из выдачи исключены ─────────────────────────────
    from django.contrib.auth import get_user_model
    from accounts.models import Membership
    from billing import services
    org = services.create_account("seo@corp-seo.ru", "", "start", "203.0.113.90")
    user = Membership.objects.get(organization=org).user
    private = Client()
    private.force_login(user)
    cabinet = private.get("/app/").content.decode()
    check('name="robots" content="noindex' in cabinet,
          "кабинет закрыт от индексации",
          "на экране префиксы ключей и суммы счетов")
    login_page = client.get("/accounts/login/code/").content.decode()
    check('name="robots" content="noindex' in login_page,
          "страница входа закрыта от индексации")

    # ── карточка для мессенджеров ─────────────────────────────────────────
    landing = client.get("/").content.decode()
    for prop in ("og:type", "og:title", "og:description", "og:url", "og:image"):
        check(f'property="{prop}"' in landing, f"карточка ссылки несёт {prop}")
    image = re.search(r'property="og:image" content="(.*?)"', landing).group(1)
    check(image.startswith(f"{_SITE}/"), "адрес картинки абсолютный", image)
    from pathlib import Path
    cover = Path(__file__).resolve().parent / "static" / "og-cover.png"
    check(cover.exists(), "и сама картинка лежит в статике", str(cover))
    if cover.exists():
        # РАЗМЕР ЧИТАЕТСЯ ИЗ ЗАГОЛОВКА PNG, БЕЗ БИБЛИОТЕКИ. Pillow нужен только
        # чтобы эту картинку НАРИСОВАТЬ (`make_og_cover.py`, ручной инструмент),
        # и тащить его в зависимости витрины ради одной проверки значило бы
        # положить его в боевой образ. Ширина и высота лежат в байтах 16..24
        # блока IHDR — это часть формата, а не догадка.
        #
        # ИМПОРТ ЗДЕСЬ БЫЛ, И ОН ЖЕ ЛОМАЛ ПРОВЕРКУ ИКОНКИ ВЫШЕ: имя, присвоенное
        # внутри функции, Python считает локальным НА ВСЮ функцию, поэтому
        # обращение к `struct` до этой строки падало с UnboundLocalError. Один
        # импорт на модуль — наверху.
        head = cover.read_bytes()[:24]
        png = head[:8] == b"\x89PNG\r\n\x1a\n"
        size = struct.unpack(">II", head[16:24]) if png else (0, 0)
        check(png and size == (1200, 630),
              "размер картинки — тот, которого ждут Telegram и поиск", str(size))

    # ── структурированные данные ──────────────────────────────────────────
    block = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                      landing, re.S)
    check(block is not None, "на главной есть разметка для поисковика")
    if block is None:
        print("=" * 60)
        raise SystemExit("seo is not correct")
    try:
        data = json.loads(block.group(1))
        parsed = True
    except json.JSONDecodeError as error:
        parsed = False
        print(f"      разбор не удался: {error}")
    check(parsed, "и она разбирается как JSON",
          "нечитаемую разметку поисковик выбрасывает целиком и молча")
    if not parsed:
        print("=" * 60)
        raise SystemExit("seo is not correct")
    types = [node["@type"] for node in data["@graph"]]
    check({"Organization", "SoftwareApplication", "WebSite"} <= set(types),
          "названы организация, продукт и сайт", str(types))
    product = next(n for n in data["@graph"] if n["@type"] == "SoftwareApplication")
    public = list(Plan.objects.filter(is_public=True))
    check(len(product["offers"]) == len(public),
          "офферов столько же, сколько публичных тарифов",
          f"{len(product['offers'])} и {len(public)}")
    # ЦЕНА — ЧИСЛО ДЛЯ МАШИНЫ. «3 900» с неразрывным пробелом это не число, и
    # такой оффер поисковик выбрасывает целиком.
    for offer in product["offers"]:
        clean = offer["price"].replace(" ", "").replace(" ", "")
        check(offer["price"] == clean and offer["price"].isdigit(),
              f"цена «{offer['name']}» — голое число", repr(offer["price"]))
    by_title = {p.title: int(p.monthly_price) for p in public}
    mismatched = [o["name"] for o in product["offers"]
                  if by_title.get(o["name"]) != int(o["price"])]
    check(not mismatched,
          "и она совпадает с ценой в базе, а не живёт отдельной жизнью",
          str(mismatched))

    print("=" * 60)
    if not ok:
        raise SystemExit("seo is not correct")
    print("seo OK — карта сайта живая, закрытое закрыто, цены для робота "
          "совпадают с базой")
    return 0


if __name__ == "__main__":
    sys.exit(main())
