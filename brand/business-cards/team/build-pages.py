#!/usr/bin/env python3
"""Страницы команды: одна форма на всех, данные — из PEOPLE в print/build.py.

Почему генератор, а не три файла руками: страница и визитка показывают ОДНИ И
ТЕ ЖЕ телефон и почту. Набранные в двух местах, они разъедутся на первой же
правке — и человек получит визитку с одним номером и страницу с другим. Здесь
единственный источник данных, и он же кормит печатный макет.

    PYTHONPATH=/tmp/pylibs python3 team/build-pages.py
"""
import html
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "print"))
import build  # noqa: E402

OUT = ROOT / "nfc"

HELP = {
    "igor": "внедрение в вашем контуре, пилот на вашем трафике, 152-ФЗ "
            "в ИИ-системах и разбор архитектуры",
    "gosha": "разбор вашей задачи, демонстрация на ваших примерах, пилот и условия "
             "работы",
    "slava": "техническая интеграция: подключение к вашему шлюзу, API, развёртывание "
             "в контуре",
}

CSS = """
  :root{
    --bg:#17171a; --panel:#1c1c20; --line:#2b2b31; --line2:#34343b;
    --text:#e8e7ec; --dim:#a9a8b3; --muted:#8f8e99; --ghost:#5c5c66;
    --accent:#b3a0ea; --accent2:#cec0f2;
  }
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--text)}
  body{
    font:400 16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
    padding:28px 20px calc(32px + env(safe-area-inset-bottom));
    display:flex;justify-content:center;
  }
  .wrap{width:100%;max-width:430px;min-width:0}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:26px}
  .brand .word{font-weight:700;font-size:21px;letter-spacing:-.025em}
  .who{margin-bottom:8px}
  .who h1{margin:0 0 4px;font-size:27px;font-weight:600;letter-spacing:-.02em}
  .who p{margin:0;color:var(--dim);font-size:15px}
  .help{color:var(--muted);font-size:14.5px;line-height:1.5;margin:0 0 4px}
  .help b{color:var(--dim);font-weight:500}
  .rule{height:1px;background:var(--line);margin:22px 0;border:0}
  .sec{font:400 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.16em;
       color:var(--ghost);text-transform:uppercase;margin:0 0 14px}
  .rows{display:grid;gap:2px;margin-bottom:22px}
  .row{display:flex;align-items:center;gap:12px;min-height:44px;
       padding:8px 12px;background:var(--panel);border:1px solid var(--line);
       text-decoration:none;color:var(--text)}
  .row:first-child{border-radius:10px 10px 0 0}
  .row:last-child{border-radius:0 0 10px 10px}
  .k{font:400 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.08em;
     color:var(--muted);width:44px;flex:none}
  .v{position:relative;flex:1;min-width:0;font-size:16px;overflow:hidden;white-space:nowrap;
     text-overflow:ellipsis}
  /* Плашка уезжает и открывает значение — та же метафора, что на самой визитке. */
  .v .mask{position:absolute;inset:-6px 0;background:var(--accent);
           transform-origin:left center;animation:unmask .85s cubic-bezier(.2,.85,.15,1) forwards}
  .row:nth-child(2) .v .mask{animation-delay:.15s}
  .row:nth-child(3) .v .mask{animation-delay:.3s}
  @keyframes unmask{to{transform:scaleX(0)}}
  @media (prefers-reduced-motion:reduce){.v .mask{display:none}}
  .btns{display:grid;gap:10px;margin-bottom:26px}
  a.btn{display:flex;align-items:center;justify-content:center;gap:9px;height:52px;
        border-radius:11px;text-decoration:none;font-size:16px;font-weight:600;
        background:var(--accent);color:#17171a;border:1px solid var(--accent)}
  a.btn.ghost{background:transparent;color:var(--text);border:1px solid var(--line2);font-weight:500}
  a.btn:active{transform:translateY(1px)}
  .docs{display:grid;gap:2px;margin-bottom:24px}
  a.doc{display:flex;align-items:center;justify-content:space-between;gap:12px;
        padding:13px 14px;background:var(--panel);border:1px solid var(--line);
        text-decoration:none;color:var(--text);font-size:14.5px}
  a.doc:first-child{border-radius:10px 10px 0 0}
  a.doc:last-child{border-radius:0 0 10px 10px}
  a.doc span.a{color:var(--ghost);font:400 13px/1 ui-monospace,SFMono-Regular,Menlo,monospace}
  .note{color:var(--muted);font-size:13.5px;line-height:1.5;margin:0 0 18px}
  .foot{border-top:1px solid var(--line);padding-top:16px;color:var(--ghost);font-size:12.5px;
        display:flex;justify-content:space-between;gap:12px;align-items:center}
  .foot a{color:var(--ghost);text-decoration:none;border-bottom:1px solid var(--line2)}
  .list{display:grid;gap:2px;margin-bottom:24px}
  a.person{display:flex;align-items:center;justify-content:space-between;gap:14px;
           padding:16px 14px;background:var(--panel);border:1px solid var(--line);
           text-decoration:none;color:var(--text)}
  a.person:first-child{border-radius:10px 10px 0 0}
  a.person:last-child{border-radius:0 0 10px 10px}
  .person .n{font-size:16.5px;font-weight:600;display:block}
  .person .r{font-size:13.5px;color:var(--muted);display:block;margin-top:2px}
  .person .go{color:var(--accent);font:400 15px/1 ui-monospace,SFMono-Regular,Menlo,monospace}
"""

MARK = """    <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect x="3" y="11" width="18" height="18" rx="5" fill="#b3a0ea"/>
      <rect x="11" y="3" width="18" height="18" rx="5" fill="#17171a" stroke="#b3a0ea" stroke-width="2.4"/>
    </svg>
    <span class="word">pseudex</span>"""

CARD = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#17171a">
<title>{{NAME}} · Pseudex</title>
<meta property="og:title" content="{{NAME}} — Pseudex">
<meta property="og:description" content="Маскирование персональных данных для LLM-агентов. Модель видит подмену — инструмент получает настоящее значение.">
<meta property="og:type" content="profile">
<!-- Страница карточки: её открывает QR. Отдельный документ БЕЗ общего каркаса
     сайта — человек, отсканировавший визитку, хочет позвонить, а не читать
     меню и баннеры. Ни одного внешнего запроса: строгий CSP витрины
     (и работа в контуре без интернета) — причина, а не вкус.
     Файл СОБРАН из team/build-pages.py: правки вносятся там, а не здесь. -->
<style>{{CSS}}</style>
</head>
<body>
<div class="wrap">

  <div class="brand">
{{MARK}}
  </div>

  <div class="who">
    <h1>{{NAME}}</h1>
    <p>{{TITLE}}</p>
  </div>
  <p class="help"><b>Чем могу помочь:</b> {{HELP}}.</p>

  <hr class="rule">
  <p class="sec">Контакты</p>

  <div class="rows">
    <a class="row" href="tel:{{TEL_DIGITS}}">
      <span class="k">tel</span><span class="v">{{TEL}}<span class="mask"></span></span>
    </a>
    <a class="row" href="mailto:{{MAIL}}">
      <span class="k">mail</span><span class="v">{{MAIL}}<span class="mask"></span></span>
    </a>
    <a class="row" href="https://pseudex.ru">
      <span class="k">web</span><span class="v">pseudex.ru<span class="mask"></span></span>
    </a>
  </div>

  <div class="btns">
    <a class="btn" href="tel:{{TEL_DIGITS}}">Позвонить</a>
    <a class="btn ghost" href="mailto:{{MAIL}}?subject=Pseudex">Написать</a>
    <a class="btn ghost" id="save" href="{{SLUG}}.vcf">Сохранить контакт</a>
  </div>

  <hr class="rule">
  <p class="sec">Для вашего безопасника и юриста</p>

  <div class="docs">
    <a class="doc" href="https://pseudex.ru/architecture">
      Архитектура: что уходит наружу, а что нет <span class="a">→</span></a>
    <a class="doc" href="https://pseudex.ru/policy">
      Политика обработки персональных данных <span class="a">→</span></a>
    <a class="doc" href="https://pseudex.ru/offer">
      Оферта <span class="a">→</span></a>
  </div>

  <p class="note">
    Эти три документа можно переслать внутри компании как есть — с них обычно
    и начинается разговор со службой безопасности. Контейнер работает в вашем
    периметре: персональные данные не покидают его, к нам уходят только счётчики.
  </p>

  <div class="foot">
    <span>152-ФЗ · хостинг в РФ</span>
    <a href="https://pseudex.ru">pseudex.ru</a>
  </div>
</div>

<script>
/* vCard собирается на месте: .vcf, отданный сервером как octet-stream,
   iOS открывает неохотно, а blob с типом text/vcard он распознаёт сам. */
document.getElementById('save').addEventListener('click', function (e) {
  var v = 'BEGIN:VCARD\\r\\nVERSION:3.0\\r\\n'
    + 'N:;{{NAME}};;;\\r\\n'
    + 'FN:{{NAME}}\\r\\n'
    + 'ORG:Pseudex\\r\\n'
    + 'TITLE:{{TITLE}}\\r\\n'
    + 'TEL;TYPE=CELL:{{TEL_DIGITS}}\\r\\n'
    + 'EMAIL;TYPE=WORK:{{MAIL}}\\r\\n'
    + 'URL:https://pseudex.ru\\r\\n'
    + 'NOTE:Маскирование персональных данных для LLM-агентов\\r\\n'
    + 'END:VCARD\\r\\n';
  try {
    var url = URL.createObjectURL(new Blob([v], {type: 'text/vcard;charset=utf-8'}));
    e.currentTarget.href = url;
    e.currentTarget.download = '{{SLUG}}.vcf';
  } catch (err) { /* остаётся обычная ссылка на {{SLUG}}.vcf */ }
});
</script>
</body>
</html>
"""

TEAM_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#17171a">
<title>Команда · Pseudex</title>
<meta property="og:title" content="Команда — Pseudex">
<meta property="og:description" content="Маскирование персональных данных для LLM-агентов.">
<!-- Индекс команды: /i/ без имени. Нужен затем, чтобы персональная страница
     была элементом системы, а не случайной ссылкой. Собран team/build-pages.py. -->
<style>{{CSS}}</style>
</head>
<body>
<div class="wrap">

  <div class="brand">
{{MARK}}
  </div>

  <h1 style="margin:0 0 6px;font-size:27px;font-weight:600;letter-spacing:-.02em">Ядро команды</h1>
  <p style="color:var(--dim);font-size:15px;margin:0 0 24px">Маскирование персональных данных для LLM-агентов.</p>

  <hr class="rule">
  <p class="sec">С кем говорить</p>

  <div class="list">
{{PEOPLE}}
  </div>

  <p class="note">
    Каждый ведёт своё: к одному идут за внедрением и пилотом, к другому — за
    продуктом, к третьему — за технической интеграцией. Визитки ведут на эти же
    страницы.
  </p>

  <div class="foot">
    <span>152-ФЗ · хостинг в РФ</span>
    <a href="https://pseudex.ru">pseudex.ru</a>
  </div>
</div>
</body>
</html>
"""

PERSON_ROW = """    <a class="person" href="/i/{{SLUG}}">
      <span>
        <span class="n">{{NAME}}</span>
        <span class="r">{{TITLE}}</span>
      </span>
      <span class="go">→</span>
    </a>"""

VCF = """BEGIN:VCARD
VERSION:3.0
N:;{name};;;
FN:{name}
ORG:Pseudex
TITLE:{title}
TEL;TYPE=CELL:{digits}
EMAIL;TYPE=WORK:{mail}
URL:https://pseudex.ru
NOTE:Маскирование персональных данных для LLM-агентов. 152-ФЗ, контейнер в контуре клиента.
END:VCARD
"""


def fill(template, **kw):
    out = template
    for k, v in kw.items():
        out = out.replace("{{%s}}" % k, v)
    return out


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    for p in build.PEOPLE:
        slug = p["slug"]
        data = dict(
            NAME=html.escape(p["name"]),
            TITLE=html.escape(p["title"]),
            TEL=html.escape(p["tel"]),
            TEL_DIGITS=p["tel"].replace(" ", "").replace("-", "").replace("(", "").replace(")", ""),
            MAIL=html.escape(p["mail"]),
            SLUG=slug,
            HELP=html.escape(HELP.get(slug, "")),
            CSS=CSS,
            MARK=MARK,
        )
        (OUT / f"card-{slug}.html").write_text(fill(CARD, **data), encoding="utf-8")
        (OUT / f"{slug}.vcf").write_text(
            VCF.format(name=p["name"], title=p["title"],
                       digits=data["TEL_DIGITS"], mail=p["mail"]), encoding="utf-8")
        rows.append(fill(PERSON_ROW, SLUG=slug, NAME=html.escape(p["name"]),
                         TITLE=html.escape(p["title"])))
        print("ok", f"card-{slug}.html")
    (OUT / "team.html").write_text(
        fill(TEAM_PAGE, CSS=CSS, MARK=MARK, PEOPLE="\n".join(rows)), encoding="utf-8")
    print("ok team.html —", len(build.PEOPLE), "человека")


if __name__ == "__main__":
    main()
