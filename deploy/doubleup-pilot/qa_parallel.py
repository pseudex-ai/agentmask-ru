"""Five manual testers, five SEPARATE Playwright instances, in parallel.

The previous runner looped over testers inside one process. This one starts one
operating-system process per tester, and each process opens its own
`sync_playwright()` browser: no shared page, context, cookie jar or renderer.
The owner asked for exactly that — "параллельные тестировщики в отдельных
playwright инстансах" — and it also removes the cross-tester timing that made a
base screen land in one tester's report while another was mid-stream.

Same evidence contract as `qa_dialogues.py`: per turn a screenshot of the typed
message, the answer, the hover reveal pairs, and the inspection receipt
(source → model request → model response → restored response → tool dispatches).
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from qa_dialogues import (
    BASE, OUTPUT, STATE, capture_reveals, ensure_highlights,
    inspection_evidence, login, newest_thread_for, read_password,
    refresh_highlights, scroll_to_latest, wait_for_marks, write_html,
)

# One conversation per tester, three consecutive turns, every turn ending in a
# mock tool that consumes PII. The tool names are explicit on purpose: this run
# proves the TOOL HOP, and a model that answers from prose would leave the hop
# untested. Production prompts never name tools; a QA prompt may.
TESTERS = {
    1: [
        ("найти контакт по телефону", [
            "Вызови инструмент pseudex_mock_find_contact с query «+7 999 123-45-67» "
            "и назови имя и email из карточки.",
            "Теперь найди тот же контакт по email: вызови pseudex_mock_find_contact "
            "с query «m.sidorova@example.ru» и подтверди, что это тот же человек.",
            "Создай задачу: вызови pseudex_mock_create_task с contact «Мария Сидорова» "
            "и title «Перезвонить по договору».",
        ]),
    ],
    2: [
        ("сделка по контакту", [
            "Найди контакт по телефону +7 903 555-12-34 через pseudex_mock_find_contact, "
            "затем вызови pseudex_mock_get_deal с deal_id 102 и скажи статус сделки.",
            "Напомни, какой телефон ты передал в инструмент поиска — дословно.",
        ]),
    ],
    3: [
        ("почта и телефон", [
            "Вызови pseudex_mock_find_contact по email «a.ivanova@example.ru» и назови "
            "имя и телефон из карточки.",
            "Создай задачу для Анны Ивановой: pseudex_mock_create_task с contact "
            "«Анна Иванова» и title «Прислать счёт».",
        ]),
    ],
    4: [
        ("контакт и сделка", [
            "Вызови pseudex_mock_find_contact с query «+7 999 123-45-67» и назови "
            "имя и email из карточки.",
            "Теперь вызови pseudex_mock_get_deal для deal_id 102 и назови бюджет и контакт.",
        ]),
    ],
    5: [
        ("контакт и адрес", [
            "Вызови pseudex_mock_find_contact по телефону +7 916 123-45-67 и назови "
            "имя и email из карточки.",
            "Запиши, что клиент живёт в Москве, на улице Ленина 14, квартира 5 — "
            "и повтори адрес дословно.",
        ]),
    ],
}


def graph_id(index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"obscura-doubleup-pilot/tester-{index}/graph"))


def wait_composer(page, timeout_ms: int = 60_000) -> None:
    page.wait_for_selector('textarea[placeholder="Введите сообщение..."]', timeout=timeout_ms)
    # A page that is still hydrating swaps the composer out from under the first
    # screenshot; the stable body + a rendered greeting is the readiness signal.
    previous = ""
    for _ in range(30):
        page.wait_for_timeout(500)
        body = page.inner_text("body")
        if "Загрузка" in body or "Загружаем" in body:
            previous = ""
            continue
        if body and body == previous:
            return
        previous = body


def main_text(page) -> str:
    return page.evaluate("() => (document.querySelector('main') || document.body).innerText")


def streaming(page) -> bool:
    return page.evaluate("""() => {
        const busy = document.querySelector('[aria-busy=true]');
        if (busy) return true;
        for (const el of document.querySelectorAll('[class]')) {
            const c = String(el.className || '');
            if (/stream|loading|typing|spinner|progress/i.test(c)) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) return true;
            }
        }
        const tail = (document.querySelector('main') || document.body).innerText.slice(-1200);
        return /Проверяем|Думаем|Генерируем|Выполняю|Обрабатываю|Секунду|Отправляем|ждём|ожида|Загруж/i.test(tail);
    }""")


def wait_answer(page, expected_messages: int, timeout_ms: int = 240_000) -> tuple[str, int, bool]:
    """Wait for the streaming answer to finish; return main text, msg count, error.

    A tool call pauses the stream, and the pause text is STATIC — body stability
    alone photographed it as the answer. Completion is therefore: no busy/spinner
    element, no tool-stage wording, and six stable seconds of the main pane.
    """
    previous = ""
    stable = 0
    for _ in range(timeout_ms // 1000):
        page.wait_for_timeout(1000)
        text = main_text(page)
        tail = text[-2500:]
        error = any(marker in tail for marker in ("не удалось получить ответ",
                                                  "модель настроена неправильно"))
        count = page.evaluate(
            "() => document.querySelectorAll('[data-role=assistant], .assistant-message, "
            "article').length")
        if error:
            return text, count, True
        if streaming(page):
            stable = 0
            previous = text
            continue
        if text == previous:
            stable += 1
            if stable >= 10:
                return text, count, False
        else:
            stable = 0
            previous = text
    return previous, -1, False


def shot(page, folder: Path, name: str, seen: set[str]) -> str | None:
    path = folder / name
    page.screenshot(path=str(path))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest in seen:
        path.unlink()
        return None
    seen.add(digest)
    return name


def run_tester(index: int, password: str) -> dict:
    user_id = f"pilot-tester-{index}"
    folder = OUTPUT / "parallel" / user_id
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    steps: list[dict] = []
    seen: set[str] = set()
    with __import__("playwright.sync_api", fromlist=["sync_playwright"]).sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1300}, locale="ru-RU")
        page = context.new_page()
        login(page, user_id, password)
        page.goto(f"{BASE}/doubleup-pilot/assistantnew/{graph_id(index)}",
                  wait_until="networkidle", timeout=90_000)
        wait_composer(page)
        token = page.evaluate("localStorage.getItem('auth_access_token')")
        org = page.evaluate("JSON.parse(localStorage.getItem('user_info')).org_id")
        headers = {"Authorization": f"Bearer {token}", "X-Org-Id": org}
        steps.append({"kind": "login", "user": user_id, "shot": None})
        steps.append({"kind": "highlights", "enabled": ensure_highlights(page)})
        for title, messages in TESTERS[index]:
            for number, message in enumerate(messages, start=1):
                box = page.locator('textarea[placeholder="Введите сообщение..."]').first
                box.fill(message)
                page.wait_for_timeout(400)
                scroll_to_latest(page)
                shot(page, folder, f"{title}-{number}-typed.png", seen)
                box.press("Enter")
                body, count, answer_error = wait_answer(page, number)
                ensure_highlights(page)
                refresh_highlights(page)
                marks = wait_for_marks(page)
                scroll_to_latest(page)
                shot(page, folder, f"{title}-{number}-answer.png", seen)
                reveals = capture_reveals(page, folder, f"{title}-{number}", limit=8)
                steps.append({"kind": "message", "dialogue": title, "index": number,
                              "request": message, "marks": marks, "reveals": reveals,
                              "assistant_messages": count,
                              "error": answer_error})
        page.wait_for_timeout(1200)
        thread_id = newest_thread_for(user_id)
        evidence = inspection_evidence(context, headers, thread_id) if thread_id else []
        browser.close()
    tools = [d for row in evidence for d in (row.get("tool_dispatches") or [])
             if isinstance(d, dict) and str(d.get("name", "")).startswith("pseudex_mock_")]
    # THE GATE IS RESTORE IN THE TOOL ARGUMENT: a real phone from the customer's
    # message must appear in what the tool was called with. The receipt's
    # `status` is "dispatching" by design (it is written at dispatch time), so it
    # cannot be the signal.
    restored = 0
    import re as _re
    email_re = _re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
    for row in evidence:
        args = json.dumps([d.get("arguments") for d in (row.get("tool_dispatches") or [])],
                          ensure_ascii=False)
        digits = "".join(ch for ch in args if ch.isdigit())
        phone_ok = any(phone.replace("+", "").replace(" ", "").replace("-", "") in digits
                       for phone in row.get("source_phones") or [])
        source_text = row.get("source") or ""
        email_ok = bool(set(email_re.findall(source_text)) & set(email_re.findall(args)))
        if phone_ok or email_ok:
            restored += 1
    report = {"tester": user_id, "thread": thread_id, "steps": steps, "evidence": evidence,
              "tool_calls": tools, "restored_tool_args": restored,
              "tools_ok": restored,
              "generated_at": datetime.now(timezone.utc).isoformat()}
    (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    write_html(folder, report)
    return {"index": index, "tester": user_id, "thread": thread_id,
            "tool_calls": len(tools), "restored_tool_args": restored,
            "gate_ok": restored >= 1,
            "errors": sum(1 for s in steps if s.get("error")),
            "report": str(folder / "report.html")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--testers", default="")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--foreground", action="store_true",
                        help="run in this process (debugging), one after another")
    args = parser.parse_args()
    wanted = [int(p) for p in args.testers.split(",") if p.strip()] or sorted(TESTERS)
    password = read_password()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    if args.foreground or len(wanted) == 1:
        for index in wanted:
            print(f"[tester {index}] start", flush=True)
            results.append(run_tester(index, password))
            print(f"[tester {index}] done", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=min(args.workers, len(wanted))) as pool:
            futures = {pool.submit(run_tester, i, password): i for i in wanted}
            for future in as_completed(futures):
                index = futures[future]
                try:
                    results.append(future.result())
                    print(f"[tester {index}] done", flush=True)
                except Exception as error:  # noqa: BLE001
                    print(f"[tester {index}] FAILED: {type(error).__name__}: {error}",
                          flush=True)
                    results.append({"index": index, "failed": str(error)})
    results.sort(key=lambda row: row.get("index", 0))
    (OUTPUT / "parallel" / "parallel-summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
