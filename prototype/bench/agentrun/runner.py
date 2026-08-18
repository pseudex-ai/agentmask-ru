"""Прогон настоящих диалогов через модель — с маскированием и без, и сравнение.

WHAT IS MEASURED, and none of it needs a label:

  * КРУГ — for every tool call, are the arguments the REAL values. Asked of the
    vault by `residual_tokens`: a leftover means a fake reached the tool.
  * ПРОЗРАЧНОСТЬ — the same dialogue is run twice, through the gateway and
    straight at the model, at temperature 0. The masked arm's answer is
    DETOKENIZED and compared with the direct arm's. Same words: transparent.
    Different wording: tolerable. A different VALUE — a name, a phone, an
    address, a date — is damage, and only that counts as a defect.
  * УТЕЧКА — what actually left for the model, recorded verbatim, so the leak
    question is answered from the wire and not from our own detector.

Every request and every tool call is written to a JSONL journal. That journal is
what the operator interface must agree with, line for line: a screen that shows a
different number from the run is worse than no screen.

    python3 bench/agentrun/runner.py <dialogues.jsonl> --base-url http://gpu:30000/v1 \
        --model Qwen/Qwen3-30B-A3B-Instruct-2507 --gateway http://127.0.0.1:8000 --limit 50
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402

from bench.agentrun.tools import SCHEMAS, MockTools  # noqa: E402

SYSTEM = (
    "Ты оператор службы доставки воды. Отвечай коротко и по делу, по-русски. "
    "Когда нужно оформить, найти, перенести или отменить заказ, изменить адрес, "
    "отправить ссылку на оплату или записать возврат тары — ВЫЗЫВАЙ инструмент, "
    "а не описывай действие словами. Не выдумывай данные клиента: бери их из "
    "переписки."
)


def client_turns(record: dict) -> list[tuple[str, str]]:
    """(роль, текст) по порядку. История нужна целиком: ход зависит от прошлых."""
    out: list[tuple[str, str]] = []
    for session in record.get("sessions", []):
        for message in session.get("messages", []):
            text = (message.get("text") or "").strip()
            if text:
                out.append((message.get("role") or "client", text))
    return out


def ask(base_url: str, model: str, messages: list[dict], api_key: str,
        timeout: float) -> dict:
    """One completion. Temperature 0 and no thinking — the run must repeat.

    `enable_thinking` is off because Qwen3's reasoning multiplies the output by
    five to fifteen times, and we are measuring a gateway, not the model's
    ability to think aloud.
    """
    body = {
        "model": model,
        "messages": messages,
        "tools": SCHEMAS,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 512,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = httpx.post(f"{base_url.rstrip('/')}/chat/completions",
                          json=body, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def run_dialogue(record: dict, base_url: str, model: str, api_key: str,
                 timeout: float, journal) -> dict:
    """Replay one dialogue: every client turn goes to the model, tools answer.

    The operator's real replies are NOT fed back and NOT compared. They are a
    different, harder evaluation — whether the agent is any good — and this run
    asks only whether the gateway kept its promise.
    """
    tools = MockTools()
    messages: list[dict] = [{"role": "system", "content": SYSTEM}]
    answers: list[str] = []
    for role, text in client_turns(record):
        if role != "client":
            continue
        messages.append({"role": "user", "content": text})
        for _ in range(4):        # a bounded tool loop; 4 is beyond anything seen
            data = ask(base_url, model, messages, api_key, timeout)
            choice = data["choices"][0]["message"]
            messages.append(choice)
            journal.write(json.dumps({"deal": record.get("deal_id"),
                                      "sent": messages[-2:], "got": choice},
                                     ensure_ascii=False) + "\n")
            calls = choice.get("tool_calls") or []
            if not calls:
                answers.append(choice.get("content") or "")
                break
            for call in calls:
                name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    arguments = {"_raw": call["function"]["arguments"]}
                result = tools.run(name, arguments)
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": json.dumps(result, ensure_ascii=False)})
    return {"deal": record.get("deal_id"), "answers": answers, "calls": tools.calls}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--gateway", default="",
                        help="адрес pseudex; пусто = плечо БЕЗ маскирования")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    # THE GATEWAY IS SWAPPED IN AT THE BASE URL, exactly as a customer does it.
    # No branch inside the runner: the treatment arm differs from the control
    # arm by one string, so nothing else can differ by accident.
    base_url = f"{args.gateway.rstrip('/')}/v1" if args.gateway else args.base_url

    records = []
    for line in Path(args.corpus).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
        if args.limit and len(records) >= args.limit:
            break

    stem = args.out or ("masked" if args.gateway else "direct")
    started = time.time()
    with open(f"{stem}.journal.jsonl", "w", encoding="utf-8") as journal, \
            open(f"{stem}.result.jsonl", "w", encoding="utf-8") as out:
        for index, record in enumerate(records, 1):
            try:
                result = run_dialogue(record, base_url, args.model, args.api_key,
                                      args.timeout, journal)
            except Exception as error:  # noqa: BLE001
                # A dialogue that dies is RECORDED, never skipped silently: a
                # run that quietly drops the hard cases reports the easy ones.
                result = {"deal": record.get("deal_id"), "error": repr(error)}
            out.write(json.dumps(result, ensure_ascii=False) + "\n")
            if index % 25 == 0:
                rate = index / (time.time() - started)
                print(f"  {index}/{len(records)}  {rate:.1f} диал/с")
    print(f"готово: {len(records)} диалогов за {time.time() - started:.0f} с "
          f"-> {stem}.result.jsonl, {stem}.journal.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
