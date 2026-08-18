"""Детерминированная заглушка модели: OpenAI-совместимый эндпоинт без модели.

WHY THIS EXISTS. The GPU run has four moving parts that have never run together
— the mock tools, the runner, the comparison, and the operator interface — and
the first run of new instrumentation is always wrong. Renting a GPU to discover
that our own journal writer mislabels a field is paying $0.84/hour for a bug we
can find offline in a second.

WHAT IT IS NOT. It is not an evaluation of anything. It never judges masking and
never looks at the vault. It answers one question: does the harness end to end
carry values from the corpus into tool arguments and back, and does the operator
interface agree with what happened.

THE ONE BEHAVIOUR THAT MATTERS: it copies what it SEES into the arguments,
verbatim. That is the harshest possible client of a tokenizing gateway — a real
model paraphrases and sometimes drops a digit, and forgiving that would hide a
round-trip break. Through the masked arm the stub sees fakes, puts fakes in the
arguments, and the gateway must turn every one of them back before the tool is
called. Anything left over is a leak the run is designed to catch.

Deterministic by construction — a pure function of the messages, no sampling, no
clock, no randomness. Two runs of the same corpus produce identical journals, so
a difference between the arms is the gateway and nothing else.

    python3 bench/agentrun/stub_model.py --port 8099
    python3 bench/agentrun/runner.py corpus.jsonl --base-url http://127.0.0.1:8099/v1 \
        --model stub --limit 3
"""

import argparse
import hashlib
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Naive and INDEPENDENT of pseudex on purpose: importing our own recognisers
# would make the harness agree with itself. These are the shapes a careless
# model would copy, nothing more.
_PHONE = re.compile(r"(?:\+7|\b8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# EVERY MARKER EITHER ENDS IN A DOT OR IS A WHOLE WORD. The abbreviations were
# written bare with an optional dot, and «пер» then matched «переезжаю» — the
# stub called a tool with an address of «переезжаю», in both arms identically,
# so the comparison saw perfect agreement about a value that never existed.
_ADDRESS = re.compile(
    r"(?:(?:ул|пер|пр-?кт|пр|ш|мкр|б-р)\.\s*"
    r"|(?:улиц[аеуы]|проспект\w*|переул\w*|бульвар\w*|шоссе|микрорайон\w*)\s+)"
    r"[^,.;!?\n]{2,60}(?:,?\s*(?:д\.?|дом)?\s*\d+[а-яА-Я]?)?"
    r"(?:,?\s*(?:кв\.?|квартира)\s*\d+)?",
    re.IGNORECASE,
)
_NAME = re.compile(r"\b[А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]{2,}){0,2}\b")
_DATE = re.compile(r"\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b|\bзавтра\b|\bсегодня\b")
_BOTTLES = re.compile(r"\b(\d{1,2})\s*(?:бут|шт|штук|баллон)")

# Words that start a capitalised phrase which is NOT a person. Without this the
# stub calls every greeting a customer name and the arms diverge on our noise.
_NOT_A_NAME = frozenset({
    "Добрый", "Здравствуйте", "Спасибо", "Привет", "Доброе", "Здравствуй",
    "Хорошо", "Заказ", "Адрес", "Телефон", "Ок", "Да", "Нет", "Пожалуйста",
    # Sentence openers. Capitalisation at a full stop carries no information
    # about personhood, and «Меня зовут …» put «Меня» in customer_name.
    "Меня", "Нужна", "Нужно", "Можно", "Прошу", "Уточните", "Подскажите",
    "Сегодня", "Завтра", "Вчера", "Доставка", "Вода", "Оплата", "Извините",
})


def _first(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip(" ,.;") if match else ""


def _person(text: str) -> str:
    """First capitalised phrase that is neither a greeting nor inside the address.

    The address cut-out is not cosmetic: «ул. Ленина 12» would otherwise be read
    as a customer named Ленина, and the same wrong name would then be copied
    into every arm — agreement produced by our own noise, which is the one thing
    an A/B comparison cannot see.
    """
    address = _ADDRESS.search(text)
    span = address.span() if address else (-1, -1)
    for match in _NAME.finditer(text):
        if span[0] <= match.start() < span[1]:
            continue
        if match.group(0).split()[0] not in _NOT_A_NAME:
            return match.group(0)
    return ""


def _intent(text: str) -> str:
    """Fixed precedence — the first rule that fires wins, always in this order.

    Precedence rather than scoring because a tie broken by a float is a tie
    broken differently on another machine, and this endpoint's whole value is
    that two runs cannot disagree.
    """
    low = text.lower()
    if re.search(r"отмен|перенес|перенос|друг(ой|ое) (день|дат)", low):
        return "reschedule_order"
    if re.search(r"смен(ить|а) адрес|нов(ый|ому) адрес|адрес друг", low):
        return "update_address"
    if re.search(r"оплат|счёт на|счет на|ссылк|картой|перевод", low):
        return "send_payment_link"
    if re.search(r"тар[уы]|пуст(ые|ых) бут|забер|заберите|верн(уть|ём) бут", low):
        return "schedule_container_pickup"
    if re.search(r"(найд|найти|проверь|где мой|статус|когда привез)", low):
        return "find_orders"
    if re.search(r"закажи|заказать|привез|доставь|нужн[аоы]|хочу|давайте", low):
        return "create_order"
    return ""


def _arguments(intent: str, text: str, seen_order: str) -> dict[str, Any]:
    phone, address = _first(_PHONE, text), _first(_ADDRESS, text)
    name, date = _person(text), _first(_DATE, text)
    bottles = _BOTTLES.search(text)
    count = int(bottles.group(1)) if bottles else 2

    if intent == "create_order":
        return {"customer_name": name, "phone": phone, "address": address,
                "bottles": count, "delivery_date": date}
    if intent == "find_orders":
        return {"phone": phone}
    if intent == "reschedule_order":
        return {"order_id": seen_order or "W-00001", "new_date": date,
                "cancel": bool(re.search(r"отмен", text.lower()))}
    if intent == "update_address":
        return {"order_id": seen_order or "W-00001", "address": address}
    if intent == "send_payment_link":
        return {"order_id": seen_order or "W-00001",
                "email": _first(_EMAIL, text), "phone": phone, "amount": count * 250}
    if intent == "schedule_container_pickup":
        return {"phone": phone, "address": address, "bottles": count,
                "pickup_date": date}
    return {}


def _order_seen(messages: list[dict[str, Any]]) -> str:
    """The last order id any tool ever answered with — the stub's only memory."""
    found = ""
    for message in messages:
        if message.get("role") == "tool":
            for match in re.finditer(r"W-\d{5}", str(message.get("content") or "")):
                found = match.group(0)
    return found


def _answer(messages: list[dict[str, Any]]) -> str:
    """The customer-facing sentence, built from the last tool result.

    It repeats the values back deliberately: the transparency axis compares the
    VALUES in both arms' answers, so an answer carrying none would pass for free.
    """
    for message in reversed(messages):
        if message.get("role") == "tool":
            try:
                payload = json.loads(message.get("content") or "{}")
            except json.JSONDecodeError:
                payload = {}
            parts = [f"{key}: {value}" for key, value in payload.items()
                     if key not in ("ok",) and value not in ("", [], {}, None)]
            return "Готово. " + "; ".join(str(p) for p in parts[:6])
    return "Принято, уточните телефон и адрес доставки."


def complete(body: dict[str, Any]) -> dict[str, Any]:
    """One completion. Pure: same messages in, same bytes out."""
    messages = body.get("messages") or []
    last_user = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            last_user = str(message.get("content") or "")
            break

    # A tool has just answered -> speak to the customer. Without this the loop
    # would call the same tool again and never terminate.
    tail = messages[-1] if messages else {}
    if tail.get("role") == "tool":
        message: dict[str, Any] = {"role": "assistant", "content": _answer(messages)}
        finish = "stop"
    else:
        intent = _intent(last_user)
        arguments = _arguments(intent, last_user, _order_seen(messages)) if intent else {}
        # An intent whose arguments came out empty is not a call: an empty
        # create_order teaches nothing and pollutes both arms equally, which
        # looks like agreement.
        # DERIVED FIELDS DO NOT COUNT AS EVIDENCE. `bottles` and `amount` always
        # have a default, so testing «any value present» fired on every intent
        # and send_payment_link went out with nothing but amount=500 in it.
        copied = {k: v for k, v in arguments.items()
                  if k not in ("bottles", "amount", "cancel")}
        if intent and any(v not in ("", None, []) for v in copied.values()):
            digest = hashlib.sha1(
                (intent + json.dumps(arguments, ensure_ascii=False, sort_keys=True)
                 ).encode("utf-8")).hexdigest()[:16]
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"call_{digest}",
                    "type": "function",
                    "function": {"name": intent,
                                 "arguments": json.dumps(arguments, ensure_ascii=False)},
                }],
            }
            finish = "tool_calls"
        else:
            message = {"role": "assistant",
                       "content": "Принято, уточните телефон и адрес доставки."}
            finish = "stop"

    text = json.dumps(messages, ensure_ascii=False)
    return {
        "id": "chatcmpl-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:24],
        "object": "chat.completion",
        "created": 0,          # fixed: a timestamp would make runs differ
        "model": body.get("model") or "stub",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": len(text) // 4,
                  "completion_tokens": 16,
                  "total_tokens": len(text) // 4 + 16},
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        return                                    # quiet: the journal is the record

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:                     # noqa: N802
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            self._send(200, {"object": "list",
                             "data": [{"id": "stub", "object": "model"}]})
        elif self.path.rstrip("/") in ("/health", "/v1/health"):
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": {"message": f"no route {self.path}"}})

    def do_POST(self) -> None:                    # noqa: N802
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": {"message": f"no route {self.path}"}})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as error:
            self._send(400, {"error": {"message": f"bad json: {error}"}})
            return
        self._send(200, complete(body))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"заглушка модели на http://{args.host}:{args.port}/v1  (модель «stub»)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
