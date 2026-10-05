from playwright.sync_api import sync_playwright
out = "/Users/igor/Projects/Obscura-storefront/docs/articles/publish-habr-01/habr-READY.html"
with sync_playwright() as pw:
    b = pw.chromium.launch(); p = b.new_page(viewport={"width": 900, "height": 1200})
    p.goto("file:///tmp/render/render.html", wait_until="networkidle"); p.wait_for_timeout(1500)
    print("заголовок:", p.inner_text("#out h1")[:60])
    print("картинок на странице:", p.locator("#out img").count())
    body = p.locator("#out").inner_html()
    html = ("<!doctype html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
            "<style>body{font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:820px;margin:40px auto;color:#111}"
            "img{max-width:100%;border:1px solid #eee}h2{margin-top:34px}table{border-collapse:collapse;width:100%}"
            "td,th{border:1px solid #ddd;padding:7px 9px;font-size:14px}code{background:#f4f4f6;padding:2px 5px}"
            "blockquote{border-left:3px solid #ccc;margin:0;padding-left:14px;color:#555}</style></head><body>" + body + "</body></html>")
    open(out, "w").write(html); print("сохранено:", out)
    b.close()
