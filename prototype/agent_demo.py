"""A real tool-using agent pointed at the Pseudex proxy.

The agent talks to a real LLM (via OpenRouter, through Pseudex). It proves:
  - the model only ever receives tokens (verified separately by grepping the
    proxy log for the real PII used here, written to used_pii.txt);
  - the agent's tool receives the REAL phone (proxy detokenized the args).
"""

import json

from openai import OpenAI

MODEL = "openai/gpt-4.1-mini"
client = OpenAI(base_url="http://localhost:4000/v1", api_key="pseudex-dev")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_order",
            "description": "Найти заказ клиента по номеру телефона.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Телефон клиента"}
                },
                "required": ["phone"],
            },
        },
    }
]

SYSTEM = (
    "Ты ассистент поддержки магазина. Если клиент просит проверить или найти заказ, "
    "обязательно вызови инструмент find_order с номером телефона клиента из сообщения."
)

# Each case: the message, and the exact real phone substring the tool must receive.
CASES = [
    ("Здравствуйте, не пришёл заказ. Мой телефон +7 999 123-45-67", "+7 999 123-45-67"),
    ("Проверьте статус заказа по номеру 8 (812) 555-22-11", "8 (812) 555-22-11"),
    ("Звоните мне на +79261234567, где моя посылка?", "+79261234567"),
    ("Мой контакт 8-905-777-00-11, почта anna@example.ru — найдите заказ", "8-905-777-00-11"),
    ("Не вижу доставку. Телефон: 89167778899", "89167778899"),
    ("Заказ оформлен на +7 (495) 123 45 67, проверьте пожалуйста", "+7 (495) 123 45 67"),
    ("Здравствуйте! Номер для связи 8 921 000 11 22", "8 921 000 11 22"),
    ("Где заказ? Мой моб +7-916-555-44-33, email ivan.petrov@mail.ru", "+7-916-555-44-33"),
    ("Прошу проверить заказ, тел 8(800)555-35-35", "8(800)555-35-35"),
    ("Контакт: +7 903 1234567, посмотрите статус доставки", "+7 903 1234567"),
]


def find_order(phone: str) -> str:
    """Fake backend tool. Returns a canned order; receives the REAL phone."""
    return json.dumps({"order_id": "A-100500", "status": "в пути", "phone": phone},
                      ensure_ascii=False)


def run_case(user_text: str) -> tuple[bool, str]:
    """Run the 2-turn agent loop. Return (tool_called, phone_the_tool_received)."""
    messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_text},
    ]
    first = client.chat.completions.create(
        model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
    )
    choice = first.choices[0].message
    if not choice.tool_calls:
        return (False, "")
    call = choice.tool_calls[0]
    received_phone = json.loads(call.function.arguments).get("phone", "")
    # Continue the loop so we also exercise re-masking of the tool result.
    messages.append(choice.model_dump())
    messages.append({
        "role": "tool",
        "tool_call_id": call.id,
        "content": find_order(received_phone),
    })
    client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
    return (True, received_phone)


def main() -> None:
    used_pii: list[str] = []
    passed = 0
    for index, (text, real_phone) in enumerate(CASES, start=1):
        used_pii.append(real_phone)
        try:
            called, received = run_case(text)
        except Exception as error:  # noqa: BLE001 — prototype harness
            print(f"CASE {index:2d}: ERROR {error}")
            continue
        ok = called and real_phone in received
        passed += 1 if ok else 0
        flag = "PASS" if ok else "FAIL"
        print(f"CASE {index:2d}: {flag} | called={called} | tool got: {received!r}")
    with open("used_pii.txt", "w", encoding="utf-8") as handle:
        handle.write("\n".join(used_pii))
    print(f"\nTOOL-RECEIVED-REAL-VALUE: {passed}/{len(CASES)} cases")


if __name__ == "__main__":
    main()
