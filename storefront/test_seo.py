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
import re
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
    favicon = client.get("/favicon.ico")
    check(favicon.status_code == 301
          and favicon.get("Location", "") == "/static/favicon.svg",
          "favicon.ico уведён на настоящую иконку",
          f"{favicon.status_code} {favicon.get('Location', '')}")

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
        import struct
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
