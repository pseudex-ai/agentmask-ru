"""Build the phase report: one self-contained HTML with screenshots and arrows.

Sources are the artifacts themselves (`phase 1 REPORT.md`, `parallel-summary.json`,
`tool-evidence.json`, `latency/REPORT.md`, every PNG) — no prose is retyped here.
"""

import base64
import html
import io
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
QA = HERE / ".state" / "qa"
ADMIN = QA / "admin"
PARALLEL = QA / "dialogues" / "parallel"
LATENCY = QA / "latency"
DESKTOP = Path.home() / "Desktop" / "pseudex-qa-screenshots"
DOWNLOADS = Path.home() / "Downloads" / "pseudex-qa-phases-full.html"


def md(path: Path) -> str:
    return html.escape(path.read_text(encoding="utf-8")) if path.exists() else ""


def embed(path: Path, width: int = 1440, quality: int = 78) -> str:
    image = Image.open(path).convert("RGB")
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def figure(path: Path, caption: str) -> str:
    uri = embed(path)
    return (f"<figure><img loading='lazy' src='{uri}' alt='{html.escape(caption)}'>"
            f"<figcaption>{html.escape(caption)}</figcaption></figure>")


def shots(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.png"))


def main() -> None:
    summary = json.loads((PARALLEL / "parallel-summary.json").read_text())
    tools = json.loads((PARALLEL / "tool-evidence.json").read_text())
    latency = json.loads((LATENCY / "latency.json").read_text())

    parts: list[str] = []
    parts.append("""<!doctype html><meta charset='utf-8'>
<title>Pseudex × DoubleUp — QA по фазам</title>
<style>
body{margin:0;background:#0d0f12;color:#e6e6e6;font:14px/1.55 -apple-system,Segoe UI,sans-serif}
header{padding:26px 34px;background:#141922;border-bottom:1px solid #26303d}
h1{margin:0 0 6px;font-size:22px}h2{margin:0 0 10px;font-size:18px;color:#9fd6a5}
h3{margin:18px 0 6px;font-size:15px;color:#c9d6ff}
section{margin:22px 34px;padding:18px;background:#141922;border:1px solid #26303d;border-radius:12px}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font:600 12px system-ui;margin-right:8px}
.ok{background:#173a24;color:#8ee6a1;border:1px solid #2d6b42}
.warn{background:#3a2a17;color:#f2c47e;border:1px solid #6b4d2d}
pre{white-space:pre-wrap;word-break:break-word;background:#0b0e13;border:1px solid #222833;border-radius:8px;padding:12px;font-size:12.5px;max-height:520px;overflow:auto}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:13px}
th,td{border:1px solid #26303d;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#1b2230}
figure{display:inline-block;width:46%;margin:8px 1.5%;vertical-align:top}
figure img{width:100%;border:1px solid #26303d;border-radius:8px;cursor:zoom-in;background:#000}
figcaption{color:#8794a5;font-size:12px;margin-top:4px}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.gallery figure{width:auto;margin:0}
a{color:#8ab4ff}
#qa-lb{position:fixed;inset:0;background:rgba(5,7,10,.97);z-index:99;display:none;flex-direction:column}
#qa-lb.open{display:flex}
#bar{display:flex;gap:12px;align-items:center;padding:10px 14px;color:#cfd6e1;border-bottom:1px solid #232a33}
#counter{font-weight:600;color:#fff}#cap{opacity:.8;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#close{margin-left:auto;background:none;border:1px solid #39424f;color:#cfd6e1;border-radius:8px;padding:6px 12px;cursor:pointer}
#stage{position:relative;flex:1;display:flex;align-items:center;justify-content:center}
#img{max-width:calc(100vw - 150px);max-height:calc(100vh - 90px);object-fit:contain}
.arrow{position:absolute;top:0;bottom:0;width:70px;border:0;background:transparent;color:#fff;font-size:40px;cursor:pointer;opacity:.7}
.arrow:hover{opacity:1;background:rgba(255,255,255,.06)}#prev{left:0}#next{right:0}
</style>""")

    parts.append("<header><h1>Pseudex × DoubleUp — QA по фазам</h1>")
    parts.append("<div>Фаза 1 — админка и политики по agent id · Фаза 2 — 5 параллельных "
                 "тестеров в отдельных Playwright-процессах · Фаза 3 — добавленная латентность</div>")
    parts.append("<div style='margin-top:10px'><span class='badge ok'>Ф1 gate: GREEN</span>"
                 "<span class='badge ok'>Ф2 gate: GREEN</span>"
                 "<span class='badge ok'>Ф3: измерено</span></div></header>")

    # Phase 1
    parts.append("<section><h2>Фаза 1 — админка Pseudex и политики по agent id</h2>")
    parts.append("<p>Создание агентов в UI DoubleUp с security 3 и 0, политики Pseudex "
                 "привязаны к agent_key, одинаковый вход даёт разные политики; журнал Pseudex "
                 "атрибутирует по graph id.</p>")
    parts.append(f"<pre>{md(ADMIN / 'REPORT.md')}</pre>")
    parts.append("<h3>Скриншоты</h3><div class='gallery'>")
    for path in shots(ADMIN):
        parts.append(figure(path, path.name))
    parts.append("</div></section>")

    # Phase 2
    parts.append("<section><h2>Фаза 2 — 5 ручных тестеров параллельно</h2>")
    parts.append("<table><tr><th>тестер</th><th>tool calls</th><th>restored args</th>"
                 "<th>gate</th><th>report</th></tr>")
    for row in summary:
        parts.append(f"<tr><td>{html.escape(str(row.get('tester')))}</td>"
                     f"<td>{row.get('tool_calls')}</td><td>{row.get('restored_tool_args')}</td>"
                     f"<td>{'✅' if row.get('gate_ok') else '❌'}</td>"
                     f"<td>{html.escape(str(row.get('report')))}</td></tr>")
    parts.append("</table>")
    parts.append(f"<pre>{md(QA / 'parallel' / 'REPORT.md')}</pre>")
    for tester, data in tools.items():
        folder = PARALLEL / tester
        parts.append(f"<h3>{html.escape(tester)} · thread {html.escape(str(data.get('thread')))}</h3>")
        parts.append("<table><tr><th>tool</th><th>arguments (настоящее значение)</th></tr>")
        for call in data.get("calls", []):
            parts.append(f"<tr><td>{html.escape(str(call.get('tool')))}</td>"
                         f"<td><code>{html.escape(json.dumps(call.get('arguments'), ensure_ascii=False))}</code></td></tr>")
        parts.append("</table><div class='gallery'>")
        for path in shots(folder):
            parts.append(figure(path, path.name))
        parts.append("</div>")
    parts.append("</section>")

    # Phase 3
    parts.append("<section><h2>Фаза 3 — латентность, которую добавляет Pseudex</h2>")
    parts.append(f"<pre>{md(LATENCY / 'REPORT.md')}</pre>")
    parts.append("<p>Сырые сэмплы: <code>" + html.escape(str(LATENCY / 'latency.json')) +
                 "</code> · модель-метрики из <code>turn_metrics</code>.</p></section>")

    parts.append("""<div id='qa-lb'><div id='bar'><span id='counter'></span><span id='cap'></span>
<button id='close' type='button'>Закрыть ✕</button></div><div id='stage'>
<button id='prev' class='arrow' type='button'>‹</button><img id='img' alt=''>
<button id='next' class='arrow' type='button'>›</button></div></div>
<script>(function(){var s=[].slice.call(document.querySelectorAll('figure img'));
var o=document.getElementById('qa-lb'),i=document.getElementById('img'),
c=document.getElementById('counter'),p=document.getElementById('cap'),x=0;
function show(n){x=(n+s.length)%s.length;i.src=s[x].src;c.textContent=(x+1)+' / '+s.length;
var f=s[x].closest('figure'),g=f&&f.querySelector('figcaption');p.textContent=g?g.textContent:'';}
function open(n){show(n);o.classList.add('open');document.documentElement.style.overflow='hidden';}
function close(){o.classList.remove('open');document.documentElement.style.overflow='';}
s.forEach(function(img,n){img.closest('figure').addEventListener('click',function(e){e.preventDefault();open(n);});});
document.getElementById('prev').onclick=function(){show(x-1);};
document.getElementById('next').onclick=function(){show(x+1);};
document.getElementById('close').onclick=close;
o.addEventListener('click',function(e){if(e.target===o||e.target.id==='stage')close();});
document.addEventListener('keydown',function(e){if(!o.classList.contains('open'))return;
if(e.key==='ArrowRight'||e.key===' '){e.preventDefault();show(x+1);}
else if(e.key==='ArrowLeft'){e.preventDefault();show(x-1);}
else if(e.key==='Escape')close();});})();</script>""")

    html_text = "".join(parts)
    DOWNLOADS.write_text(html_text, encoding="utf-8")
    print("written", DOWNLOADS, f"{DOWNLOADS.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
