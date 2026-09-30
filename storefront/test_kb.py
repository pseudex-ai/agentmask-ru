"""РАЗДЕЛ ПОД ПОИСК: СТРАНИЦЫ, ИХ РАЗМЕТКА И СВЯЗЬ С ОСТАЛЬНЫМ САЙТОМ.

ЗАЧЕМ ПРОВЕРКА. База знаний существует ради одного: чтобы нас находили по
запросам, которые люди печатают, не зная о нас. Ломается это молча и снаружи —
новую статью забыли внести в карту сайта, разметку `Article` набрали руками и
она разошлась с заголовком, страницу закрыли от индексации, из неё убрали
ссылку на продукт. На самой странице всё при этом выглядит perfectly хорошо.

САМАЯ ЦЕННАЯ ПРОВЕРКА ЗДЕСЬ — СОВПАДЕНИЕ `FAQPage` С ВИДИМЫМ ТЕКСТОМ.
Поисковик показывает в сниппете вопросы из разметки. Если разметка отвечает
одно, а человек на странице читает другое, это не «недооптимизация», а
нарушение правил: страницу понижают. Разошедшиеся тексты — ровно то, что
появляется при ручном дублировании, поэтому вопросы живут в ОДНОМ месте
(`KB_ARTICLES`), и тест требует, чтобы страница и разметка совпадали дословно.

Запуск:  cd storefront && .venv/bin/python test_kb.py
"""
import json
import os
import re
import sys

_SITE = "https://pseudex.test"


def _jsonld_blocks(html: str) -> list[dict]:
    out = []
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            out.append({"__broken__": raw[:120]})
    return out


def _graph(block: dict) -> list[dict]:
    if "@graph" in block:
        return block["@graph"]
    return [block]


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "kb-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = "/tmp/pseudex-kb-test.db"
    os.environ["SITE_URL"] = _SITE
    os.environ["PSEUDEX_SITE_URL"] = _SITE
    if os.path.exists("/tmp/pseudex-kb-test.db"):
        os.remove("/tmp/pseudex-kb-test.db")
    import django
    django.setup()
    from django.core.management import call_command
    from django.test.utils import setup_test_environment
    setup_test_environment()
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)

    from django.test import Client
    from storefront_web.views import KB_ARTICLES

    ok = True
    def check(cond, name, detail=""):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
        ok = ok and cond

    client = Client()
    check(bool(KB_ARTICLES), "в разделе есть хотя бы одна статья")

    # ── хаб раздела ────────────────────────────────────────────────────────
    hub = client.get("/baza-znaniy")
    check(hub.status_code == 200, "хаб раздела открывается", str(hub.status_code))
    hub_html = hub.content.decode()
    check("index, follow" in hub_html, "хаб разрешён к индексации")
    check(len(re.findall(r"<h1", hub_html)) == 1, "на хабе ровно один h1")
    for a in KB_ARTICLES:
        check(f'/baza-znaniy/{a["slug"]}' in hub_html,
              f"хаб ссылается на статью «{a['h1']}»")

    # ── каждая статья ──────────────────────────────────────────────────────
    titles = set()
    for a in KB_ARTICLES:
        url = f'/baza-znaniy/{a["slug"]}'
        r = client.get(url)
        check(r.status_code == 200, f"{url} открывается", str(r.status_code))
        html = r.content.decode()
        check("index, follow" in html, f"статья «{a['h1']}» разрешена к индексации")
        check(len(re.findall(r"<h1", html)) == 1, f"на {url} ровно один h1")
        check(a["h1"] in html, "заголовок статьи совпадает с реестром")
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        title = title.group(1).strip() if title else ""
        check(title and title not in titles, "заголовок окна уникален", f"повтор: {title[:60]}")
        titles.add(title)

        graph = [n for b in _jsonld_blocks(html) for n in _graph(b)]
        kinds = {n.get("@type") for n in graph}
        check("Article" in kinds, f"у статьи «{a['h1']}» есть разметка Article")
        check("BreadcrumbList" in kinds, f"у статьи «{a['h1']}» есть хлебные крошки")
        article = next((n for n in graph if n.get("@type") == "Article"), {})
        check(article.get("headline") == a["h1"],
              "headline в разметке равен заголовку страницы",
              f'{article.get("headline")!r} != {a["h1"]!r}')

        # ── САМОЕ ДОРОГОЕ: разметка вопросов равна видимым вопросам ──────
        if a.get("faq"):
            faq = next((n for n in graph if n.get("@type") == "FAQPage"), None)
            check(faq is not None, "разметка FAQPage есть там, где есть вопросы")
            if faq:
                marked = [q["name"] for q in faq.get("mainEntity", [])]
                visible = [re.sub(r"<[^>]+>", "", s).strip()
                           for s in re.findall(r"<summary[^>]*>(.*?)<span", html, re.S)]
                check(len(marked) == len(a["faq"]),
                      "в разметке столько же вопросов, сколько в реестре",
                      f"{len(marked)} против {len(a['faq'])}")
                check(all(q in visible for q in marked),
                      "КАЖДЫЙ вопрос из разметки виден на странице дословно",
                      "разметка, разошедшаяся с текстом, — это нарушение, а не недооптимизация")

        # ── связь с остальным сайтом ──────────────────────────────────────
        check('href="/baza-znaniy"' in html, f"из «{a['h1']}» есть путь назад в раздел")
        check("/#start" in html, f"из «{a['h1']}» есть переход к продукту")
        check("/architecture" in html, f"из «{a['h1']}» есть ссылка на документ для ИБ")

    # ── карта сайта называет раздел и все статьи ───────────────────────────
    xml = client.get("/sitemap.xml").content.decode()
    check(f"<loc>{_SITE}/baza-znaniy</loc>" in xml, "хаб раздела попал в карту сайта")
    for a in KB_ARTICLES:
        loc = f"<loc>{_SITE}/baza-znaniy/{a['slug']}</loc>"
        check(loc in xml, f"статья «{a['h1']}» попала в карту сайта")
        check(client.get(f'/baza-znaniy/{a["slug"]}').status_code == 200,
              "адрес из карты сайта действительно открывается")

    # ── неизвестный адрес не отдаёт 200 ────────────────────────────────────
    check(client.get("/baza-znaniy/net-takoy-statyi").status_code == 404,
          "несуществующая статья отдаёт 404, а не пустую страницу")

    if not ok:
        raise SystemExit("база знаний не в порядке")
    print("baza znaniy OK — статьи отвечают, разметка совпадает с текстом, "
          "карта сайта их знает")
    return 0


if __name__ == "__main__":
    sys.exit(main())
