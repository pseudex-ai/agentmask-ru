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
    # Testers 3/4/5: several turns each, and every turn ends in a contact the mock
    # CRM is actually keyed by. A one-turn dialogue gave three screenshots and no
    # proof that the substitute survives a second turn — which is the thing the
    # hops are supposed to show.
    3: [
        ("доступ и карточка", [
            "У меня такой вопрос: если я потерял доступ к аккаунту, но у меня есть паспорт "
            "и СНИЛС, я могу восстановить доступ? Мой телефон +7 999 123-45-67.",
            "Спасибо. А какой email записан у меня в карточке? Меня зовут Мария Сидорова.",
            "И продиктуй, пожалуйста, мой номер телефона ещё раз — я его потерял.",
        ]),
    ],
    4: [
        ("задачи и адрес клиента", [
            "Здравствуйте, я Иванова Анна Сергеевна, anna.ivanova@example.ru. "
            "Подскажите, есть ли по мне открытые задачи, и на какую дату они назначены?",
            "А какой телефон у меня записан в карточке?",
            "И запиши, пожалуйста, что я живу в Москве, на улице Ленина 14, квартира 5.",
        ]),
    ],
    5: [
        ("договор по клиенту", [
            "Коллеги, пришлите, пожалуйста, договор на Кузнецова Дмитрия Андреевича, "
            "+7 903 555-12-34, на адрес m.sidorova@example.ru. Срочно, до пятницы.",
            "Уточни, пожалуйста, статус сделки по этому же телефону +7 903 555-12-34.",
            "И скажи, какой email записан у него в карточке.",
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


def scroll_to_latest(page) -> None:
    """Bring the newest message into view in whatever scrolls.

    A full-page screenshot hides the only thing worth looking at: a page that
    never moved has no visible answer. Every scrollable box goes to its bottom,
    which is where a chat puts the message it just received.
    """
    page.evaluate(
        "() => { for (const el of document.querySelectorAll('*')) {"
        "  if (el.scrollHeight > el.clientHeight + 40) el.scrollTop = el.scrollHeight;"
        "} window.scrollTo(0, document.body.scrollHeight); }")
    page.wait_for_timeout(400)


def ensure_highlights(page) -> bool:
    """Turn the substitution highlighting on; without it there is nothing to hover."""
    toggle = page.locator('[data-testid="pseudex-highlight-toggle"]').first
    if not toggle.count():
        return False
    if "выключена" in toggle.inner_text():
        toggle.click()
        page.wait_for_timeout(2_000)
    return True


def refresh_highlights(page) -> None:
    """Ask the panel for the marks of the answer that just arrived.

    Highlighting is a read-only projection requested explicitly; the first turn
    of a fresh thread has nothing to project until it is asked for. The toggle is
    left alone here — clicking it again would switch the marks OFF, and a report
    of screenshots with no marks is exactly what this harness exists to prevent.
    """
    ensure_highlights(page)
    button = page.locator('button:has-text("Обновить подсветку")').first
    if button.count() and button.is_visible():
        try:
            button.click(timeout=5_000)
            page.wait_for_timeout(1_500)
        except Exception:
            pass


def wait_for_marks(page, timeout_ms: int = 25_000) -> int:
    """The marks arrive from their own read-only projection, a beat after the answer.

    The first turn of a fresh thread is the one that loses this race: the answer
    is already on screen while the panel still has no positions to mark. Waiting
    for them (and asking once more if they do not come) is the difference between
    an evidence screenshot and a picture of a chat.
    """
    waited = 0
    refreshed = False
    while waited < timeout_ms:
        count = page.locator('mark[role="button"]').count()
        if count:
            return count
        if not refreshed and waited >= 8_000:
            button = page.locator('button:has-text("Обновить подсветку")').first
            if button.count() and button.is_visible():
                try:
                    button.click(timeout=4_000)
                except Exception:
                    pass
            refreshed = True
        page.wait_for_timeout(500)
        waited += 500
    return page.locator('mark[role="button"]').count()


def capture_reveals(page, folder: Path, prefix: str, limit: int = 6) -> list[dict]:
    """Hover every masked value and photograph what it was replaced with.

    This is the proof the plain screenshots cannot give: the mark shows one side
    of the substitution, the popover the other. The pair is also written to the
    report as text, so the evidence survives even where the tooltip is off-screen
    for a moment.
    """
    total = page.locator('mark[role="button"]').count()
    rows: list[dict] = []
    for index in range(total):
        if len([row for row in rows if row["shot"]]) >= limit:
            break
        try:
            # Re-query every time: the message re-renders as the answer streams
            # in and a held element reference goes "not attached to the DOM".
            mark = page.locator('mark[role="button"]').nth(index)
            if not mark.count() or not mark.is_visible():
                continue
            shown = (mark.inner_text(timeout=5_000) or "").strip()
            if not shown:
                continue
            mark.scroll_into_view_if_needed(timeout=10_000)
            page.wait_for_timeout(250)
            mark.hover(timeout=10_000)
            tooltip = page.locator('[role="tooltip"]').first
            text = ""
            for _ in range(30):
                page.wait_for_timeout(500)
                if tooltip.count():
                    text = (tooltip.inner_text() or "").strip()
                    # «Подробности загружаются…» means the counterpart has not
                    # arrived yet; a screenshot of it would prove nothing.
                    if "Показанный фрагмент" in text and "загружаются" not in text \
                            and "ещё не загружены" not in text:
                        break
            if "Показанный фрагмент" not in text:
                page.keyboard.press("Escape")
                page.wait_for_timeout(200)
                continue
            shot = f"{prefix}-reveal-{len(rows) + 1}.png"
            page.screenshot(path=str(folder / shot))
            rows.append({"mark": shown, "tooltip": text, "shot": shot})
        except Exception:
            # A mark that will not open is skipped, never guessed at: the report
            # shows what actually opened and nothing else.
            pass
        finally:
            page.mouse.move(2, 2)
            page.wait_for_timeout(250)
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
    return rows


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
        steps.append({"kind": "highlights", "enabled": ensure_highlights(page)})
        for title, messages in dialogues:
            prefix = f"{len(steps):02d}"
            scroll_to_latest(page)
            page.screenshot(path=str(folder / f"{prefix}-start.png"))
            for number, message in enumerate(messages, start=1):
                prefix = f"{len(steps):02d}"
                box = page.locator('textarea[placeholder="Введите сообщение..."]').first
                box.fill(message)
                page.wait_for_timeout(400)
                scroll_to_latest(page)
                page.screenshot(path=str(folder / f"{prefix}-typed-{number}.png"))
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
                page.wait_for_timeout(700)
                ensure_highlights(page)
                refresh_highlights(page)
                marks_seen = wait_for_marks(page)
                scroll_to_latest(page)
                page.screenshot(path=str(folder / f"{prefix}-answer-{number}.png"))
                reveals = capture_reveals(page, folder, f"{prefix}-answer-{number}")
                steps.append({"kind": "message", "dialogue": title, "index": number,
                              "request": message, "marks": marks_seen, "reveals": reveals})
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
        "<div><a href='../../index.html'>← ко всем прогонам</a></div>",
        f"<div class='muted'>thread {esc(report['thread'])} · {esc(report['generated_at'])}</div></header>",
    ]
    for step in report["steps"]:
        if step["kind"] in ("login", "highlights"):
            continue
        parts.append("<div class='card'>")
        parts.append(f"<h2>{esc(step['dialogue'])} · шаг {step['index']}</h2>")
        parts.append(f"<pre>{esc(step['request'])}</pre>")
        reveals = step.get("reveals") or []
        if reveals:
            parts.append("<h3>что было подменено — по наведению</h3>")
            parts.append("<table><tr><th>модель увидела</th><th>настоящее значение</th></tr>")
            for reveal in reveals:
                parts.append(f"<tr><td><code>{esc(reveal['mark'])}</code></td>"
                             f"<td><code>{esc(reveal['tooltip'])}</code></td></tr>")
            parts.append("</table>")
            for reveal in reveals:
                if reveal.get("shot"):
                    parts.append(f"<img src='{esc(reveal['shot'])}' alt='{esc(reveal['shot'])}'>")
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
