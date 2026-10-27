"""Five parallel manual testers, in a real browser, against the live pilot.

WHAT THIS PROVES, AND WHY IT IS THE REPORT RATHER THAN A TEST. The product's
promise is that the model never sees a real value and the tool always receives
one. A unit test can assert that of `/mask`; only a dialogue can assert it of the
whole chain a customer actually exercises — browser session → chat pipeline →
sidecar → live model → tool → restored answer — with screenshots at each hop so
a human can follow it without reading JSON.

Each of the five testers is a SEPARATE browser context with its own account, its
own graph and its own thread, so the five dialogues run in parallel and cannot
see each other's vault rows. Every dialogue records:

  * the screenshot of the typed message,
  * the screenshot of the answer,
  * the inspection receipt: source_request, model_request, model_response,
    restored_response and tool_dispatches.

The receipts are what make the screenshots evidence instead of decoration: the
report prints the real phone the operator typed beside the substitute the model
saw, and the tool argument beside the real value the tool received.

Run from deploy/doubleup-pilot:

    python3 qa_dialogues.py                 # all five testers
    python3 qa_dialogues.py --testers 1,2   # a subset while iterating
"""

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
OUTPUT = STATE / "qa" / "dialogues"
BASE = "http://127.0.0.1:18880"
API = "http://127.0.0.1:18860"

# Each tester's dialogues. The phone numbers are the REAL values the mock CRM is
# keyed by (tools/pseudex_pilot_tools.py): a mask that failed to restore finds
# nothing, which the report shows as «контакт не найден».
TESTERS = {
    1: [
        ("контакт по телефону", [
            "Здравствуйте! Меня зовут Мария Сидорова, мой телефон +7 999 123-45-67. "
            "Найди, пожалуйста, мой контакт в CRM и скажи, по какой сделке мы общались.",
            "Спасибо. А на какой email мне отправлять документы?",
        ]),
        ("сделка по номеру", [
            "Добрый день. Клиент Кузнецов Дмитрий Андреевич, телефон +7 903 555-12-34, "
            "просил уточнить статус сделки по ремонту склада. Найдёшь?",
        ]),
    ],
    2: [
        ("задача по контакту", [
            "Привет! Создай, пожалуйста, задачу «Перезвонить по договору» для Анны Ивановой, "
            "её телефон +7 916 123-45-67.",
            "И отметь, что она просила прислать счёт на anna.ivanova@example.ru.",
        ]),
        # B4: the patterns the real corpus showed to be where re-masking breaks.
        # (a) the tool RETURNS a contact, so the result leg must mask it too;
        # (b) the same phone is said twice, so the substitute must be stable;
        # (c) an address appears after the contact, so the address leg runs.
        ("контакт в результате инструмента", [
            "Найди в CRM контакт человека с телефоном +7 916 123-45-67 и продиктуй, "
            "что у него записано в карточке: имя и email.",
            "Спасибо. А теперь напомни мне, пожалуйста, этот же телефон — я его потерял.",
            "И запиши, что он живёт в Москве, на улице Ленина 14, квартира 5.",
        ]),
    ],
    3: [
        ("личные данные в общем вопросе", [
            "У меня такой вопрос: если я потерял доступ к аккаунту, но у меня есть паспорт "
            "и СНИЛС, я могу восстановить доступ? Мой телефон +7 999 123-45-67.",
        ]),
    ],
    4: [
        ("уточнение по email", [
            "Здравствуйте, я Иванова Анна Сергеевна, anna.ivanova@example.ru. "
            "Подскажите, есть ли по мне открытые задачи, и на какую дату они назначены?",
        ]),
    ],
    5: [
        ("смешанные ПД", [
            "Коллеги, пришлите, пожалуйста, договор на Кузнецова Дмитрия Андреевича, "
            "+7 903 555-12-34, на адрес m.sidorova@example.ru. Срочно, до пятницы.",
        ]),
    ],
}

PHONE = re.compile(r"\+7[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


def phones(text: str) -> list[str]:
    return sorted(set(PHONE.findall(json.dumps(text, ensure_ascii=False))))


def esc(value) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def read_password() -> str:
    payload = json.loads((STATE / "runtime" / "browser.json").read_text())
    password = payload.get("password")
    if not isinstance(password, str) or not password:
        raise SystemExit("pilot browser password missing")
    return password


def login(page, user_id: str, password: str) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90_000)
    page.fill('input[name="user_id"]', user_id)
    page.fill('input[name="password"]', password)
    page.click('button:has-text("Войти")')
    page.wait_for_url(lambda url: "/login" not in url, timeout=60_000)
    page.wait_for_timeout(2_500)


def newest_thread_for(user_id: str) -> str | None:
    """The newest thread this tester owns, read from the pilot database.

    The frontend does not put the thread in the URL, and the inspection list is
    keyed by thread, so the id has to come from where the frontend itself reads
    it. Reading the pilot DB (read-only, by user) is the same source the chat
    page uses on load and cannot drift from it.
    """
    script = (
        "const t = db.threads.find({user_id: '" + user_id + "'}).sort({created_at:-1}).limit(1).toArray();"
        "print(t.length ? t[0].thread_id : '')"
    )
    try:
        result = subprocess.run(
            ["docker", "exec", "obscura-doubleup-pilot-mongodb-1", "mongosh", "doubleup_pilot",
             "--quiet", "--eval", script],
            capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    value = (result.stdout or "").strip().splitlines()
    return value[-1].strip() if value and value[-1].strip() else None


def inspection_evidence(context, headers, thread_id: str) -> list[dict]:
    listing = context.request.get(
        f"{API}/api/v1/pseudex/inspections?thread_id={thread_id}", headers=headers)
    if not listing.ok:
        return []
    rows = []
    for item in listing.json().get("items", [])[-6:]:
        detail = context.request.get(
            f"{API}/api/v1/pseudex/inspections/{item['attempt_id']}", headers=headers)
        if not detail.ok:
            continue
        payload = detail.json()
        source = json.dumps(payload.get("source_request"), ensure_ascii=False)
        model = json.dumps(payload.get("model_request"), ensure_ascii=False)
        restored = json.dumps(payload.get("restored_response"), ensure_ascii=False)
        inspection = payload.get("inspection") or {}
        rows.append({
            "attempt_id": item["attempt_id"],
            "status": item.get("status"),
            "source_phones": phones(source),
            "model_phones": phones(model),
            "replacements": len(inspection.get("replacements") or []),
            "complete": inspection.get("complete"),
            "source": source[:4000],
            "model_request": model[:4000],
            "model_response": json.dumps(payload.get("model_response"), ensure_ascii=False)[:4000],
            "restored_response": restored[:4000],
            "tool_dispatches": payload.get("tool_dispatches"),
        })
    return rows


def run_tester(index: int, dialogues, password: str) -> dict:
    user_id = f"pilot-tester-{index}"
    folder = OUTPUT / user_id
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1300}, locale="ru-RU")
        page = context.new_page()
        login(page, user_id, password)
        token = page.evaluate("localStorage.getItem('auth_access_token')")
        org = page.evaluate("JSON.parse(localStorage.getItem('user_info')).org_id")
        headers = {"Authorization": f"Bearer {token}", "X-Org-Id": org}
        steps.append({"kind": "login", "user": user_id, "shot": None})
        for title, messages in dialogues:
            page.screenshot(path=str(folder / f"{len(steps):02d}-start.png"), full_page=True)
            for number, message in enumerate(messages, start=1):
                box = page.locator('textarea[placeholder="Введите сообщение..."]').first
                box.fill(message)
                page.wait_for_timeout(400)
                page.screenshot(path=str(folder / f"{len(steps):02d}-typed-{number}.png"), full_page=True)
                box.press("Enter")
                previous = ""
                for _ in range(90):
                    page.wait_for_timeout(1000)
                    body = page.inner_text("body")
                    if "Ошибка" in body:
                        break
                    if body == previous and number <= len(messages):
                        break
                    previous = body
                page.wait_for_timeout(500)
                page.screenshot(path=str(folder / f"{len(steps):02d}-answer-{number}.png"), full_page=True)
                steps.append({"kind": "message", "dialogue": title, "index": number,
                              "request": message})
        # The thread id lives on the chat request the UI made; take the newest
        # thread for this user from the same API the panel uses.
        page.wait_for_timeout(1000)
        thread_id = newest_thread_for(user_id)
        evidence = inspection_evidence(context, headers, thread_id) if thread_id else []
        browser.close()
    report = {"tester": user_id, "thread": thread_id, "steps": steps, "evidence": evidence,
              "generated_at": datetime.now(timezone.utc).isoformat()}
    (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    write_html(folder, report)
    return report


def write_html(folder: Path, report: dict) -> None:
    parts = [
        "<!doctype html><meta charset='utf-8'>",
        "<title>PSEUDEX · отчёт тестировщика</title>",
        "<style>body{font:14px/1.5 -apple-system,Segoe UI,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}",
        "header{padding:24px 32px;background:#161a22;border-bottom:1px solid #2a2f3a}",
        "h1{margin:0 0 4px;font-size:20px}h2{font-size:16px;margin:0 0 6px;color:#9fd6a5}",
        ".card{background:#161a22;border:1px solid #2a2f3a;border-radius:10px;padding:16px;margin:16px 32px}",
        "pre{white-space:pre-wrap;word-break:break-word;background:#0b0e13;border:1px solid #222833;border-radius:8px;",
        "padding:10px;font-size:12px;max-height:420px;overflow:auto}",
        "img{max-width:100%;border:1px solid #2a2f3a;border-radius:8px;margin:6px 0}",
        ".ok{color:#7ee787}.bad{color:#ff7b72}.muted{color:#8b949e}",
        "</style>",
        f"<header><h1>PSEUDEX · {esc(report['tester'])}</h1>",
        f"<div class='muted'>thread {esc(report['thread'])} · {esc(report['generated_at'])}</div></header>",
    ]
    for step in report["steps"]:
        if step["kind"] == "login":
            continue
        parts.append("<div class='card'>")
        parts.append(f"<h2>{esc(step['dialogue'])} · шаг {step['index']}</h2>")
        parts.append(f"<pre>{esc(step['request'])}</pre>")
        parts.append("</div>")
    for row in report["evidence"]:
        same = set(row["source_phones"]) & set(row["model_phones"])
        verdict = "bad" if same else "ok"
        parts.append("<div class='card'>")
        parts.append(f"<h2>квитанция {esc(row['attempt_id'][:10])} · {esc(row['status'])}</h2>")
        parts.append(f"<div>телефон оператора: <b>{esc(row['source_phones'])}</b> · "
                     f"телефон, который увидела модель: <b class='{verdict}'>{esc(row['model_phones'])}</b></div>")
        parts.append(f"<div class='muted'>замен: {row['replacements']} · complete: {esc(row['complete'])}</div>")
        for key, label in (("source", "исходный запрос"), ("model_request", "запрос к модели"),
                           ("model_response", "ответ модели"), ("restored_response", "восстановленный ответ")):
            parts.append(f"<h3>{label}</h3><pre>{esc(row.get(key))}</pre>")
        if row.get("tool_dispatches"):
            parts.append(f"<h3>вызовы инструментов</h3><pre>{esc(json.dumps(row['tool_dispatches'], ensure_ascii=False, indent=1))}</pre>")
        parts.append("</div>")
    for image in sorted(folder.glob("*.png")):
        parts.append(f"<div class='card'><h2>{esc(image.name)}</h2>"
                     f"<img src='{esc(image.name)}' alt='{esc(image.name)}'></div>")
    (folder / "report.html").write_text("".join(parts))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--testers", default="")
    args = parser.parse_args()
    wanted = [int(part) for part in args.testers.split(",") if part.strip()] or sorted(TESTERS)
    password = read_password()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    for index in wanted:
        print(f"[tester {index}] start", flush=True)
        try:
            results.append(run_tester(index, TESTERS[index], password))
            print(f"[tester {index}] done", flush=True)
        except Exception as error:  # one tester's failure must not sink the run
            print(f"[tester {index}] FAILED: {type(error).__name__}: {error}", flush=True)
    print(json.dumps({"testers": [r["tester"] for r in results],
                      "reports": [str(OUTPUT / r["tester"] / "report.html") for r in results]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
