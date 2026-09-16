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
        from PIL import Image
        with Image.open(cover) as opened:
            check(opened.size == (1200, 630),
                  "размер картинки — тот, которого ждут Telegram и поиск",
                  str(opened.size))

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
