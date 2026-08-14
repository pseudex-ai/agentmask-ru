"""Live end-to-end eval: real LLM, real tool calls that USE personal data as logic.

For each scenario the model must call the right tool with the customer's PII.
We measure: did the REAL value reach the tool (round-trip), and (separately, via
the proxy log) did anything leak to the model. This is the real test — not a
script run of the detector.
"""

import json
import re

from openai import OpenAI

from make_dataset import (
    CITIES, NAMES, STREETS,
    gen_card, gen_date, gen_email, gen_inn10, gen_passport, gen_phone, gen_snils,
)
from make_addr_real import realistic_address

import random

random.seed(7)
N = 32
MODEL = "openai/gpt-4.1-mini"
client = OpenAI(base_url="http://localhost:4000/v1", api_key="veilgate-dev")

SYSTEM = (
    "Ты ассистент службы поддержки. Тебе даны инструменты. Чтобы выполнить запрос "
    "клиента, ВСЕГДА вызывай подходящий инструмент, передавая в него данные клиента "
    "из сообщения дословно. Не отвечай текстом без вызова инструмента."
)


def _tool(name: str, desc: str, params: list[str]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": {p: {"type": "string"} for p in params},
                "required": params,
            },
        },
    }


TOOLS = [
    _tool("find_order", "Найти заказ по телефону клиента.", ["phone"]),
    _tool("find_client", "Найти клиента по email.", ["email"]),
    _tool("verify_snils", "Проверить клиента по СНИЛС.", ["snils"]),
    _tool("check_inn", "Проверить контрагента по ИНН.", ["inn"]),
    _tool("charge_card", "Списать оплату с банковской карты.", ["card"]),
    _tool("check_passport", "Проверить паспорт клиента.", ["passport"]),
    _tool("schedule_visit", "Записать клиента на визит.", ["name", "phone", "date"]),
    _tool("arrange_delivery", "Оформить доставку по адресу.", ["address"]),
]


def _builders() -> list:
    def phone() -> dict[str, object]:
        v = gen_phone()
        return {"user": f"Не пришёл заказ, мой телефон {v}, проверьте статус.",
                "tool": "find_order", "pii": [("PHONE", v)]}

    def email() -> dict[str, object]:
        v = gen_email()
        return {"user": f"Найдите мой профиль, почта {v}.",
                "tool": "find_client", "pii": [("EMAIL", v)]}

    def snils() -> dict[str, object]:
        v = gen_snils()
        return {"user": f"Проверьте мои начисления, СНИЛС {v}.",
                "tool": "verify_snils", "pii": [("SNILS", v)]}

    def inn() -> dict[str, object]:
        v = gen_inn10()
        return {"user": f"Проверьте контрагента по ИНН {v}.",
                "tool": "check_inn", "pii": [("INN", v)]}

    def card() -> dict[str, object]:
        v = gen_card()
        return {"user": f"Спишите оплату с карты {v}.",
                "tool": "charge_card", "pii": [("CARD", v)]}

    def passport() -> dict[str, object]:
        v = gen_passport()
        return {"user": f"Проверьте мой паспорт {v}.",
                "tool": "check_passport", "pii": [("PASSPORT", v)]}

    def visit() -> dict[str, object]:
        name, ph, dt = random.choice(NAMES), gen_phone(), gen_date()
        return {"user": f"Запишите меня на визит. Я {name}, телефон {ph}, дата {dt}.",
                "tool": "schedule_visit", "pii": [("NAME", name), ("PHONE", ph), ("DATE", dt)]}

    def delivery() -> dict[str, object]:
        addr = realistic_address()  # rich free-form RU address (problem B)
        return {"user": f"Оформите доставку по адресу: {addr}.",
                "tool": "arrange_delivery", "pii": [("LOC", addr)]}

    return [phone, email, snils, inn, card, passport, visit, delivery]


def _delivered(value: str, argstr: str) -> bool:
    if value in argstr:
        return True
    digits = re.sub(r"\D", "", value)
    arg_digits = re.sub(r"\D", "", argstr)
    if digits and digits in arg_digits:
        return True
    # RU phone identity is the last 10 digits — country code 8 / +7 are equivalent,
    # so "85260181590" and the canonical "+75260181590" are the same number.
    return len(digits) >= 10 and digits[-10:] in arg_digits


def main() -> None:
    builders = _builders()
    used_pii: list[str] = []
    per_type: dict[str, list[int]] = {}
    tool_ok = 0
    total = 0

    for index in range(N):
        scenario = builders[index % len(builders)]()
        for _, value in scenario["pii"]:
            used_pii.append(value)
        total += 1
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": scenario["user"]}],
                tools=TOOLS,
                tool_choice="required",
            )
        except Exception as error:  # noqa: BLE001 — eval harness
            print(f"[{index}] ERROR {error}")
            continue
        message = response.choices[0].message
        called = ""
        argstr = "{}"
        if message.tool_calls:
            called = message.tool_calls[0].function.name
            argstr = message.tool_calls[0].function.arguments
        if called == scenario["tool"]:
            tool_ok += 1
        for entity_type, value in scenario["pii"]:
            stat = per_type.setdefault(entity_type, [0, 0])
            stat[0] += 1
            if _delivered(value, argstr):
                stat[1] += 1
            else:
                print(f"MISS {entity_type}: real={value!r} model_arg={argstr}")

    with open("used_pii.txt", "w", encoding="utf-8") as handle:
        handle.write("\n".join(used_pii))

    print(f"\n{'TYPE':<10}{'REQ':>5}{'ROUNDTRIP':>11}")
    treq = tok = 0
    for entity_type in ["PHONE", "EMAIL", "SNILS", "INN", "CARD", "PASSPORT", "NAME", "DATE", "LOC"]:
        if entity_type not in per_type:
            continue
        req, ok = per_type[entity_type]
        treq += req; tok += ok
        print(f"{entity_type:<10}{req:>5}{ok / req:>10.0%}")
    print("-" * 26)
    print(f"{'OVERALL':<10}{treq:>5}{tok / treq:>10.0%}")
    print(f"\nTOOL PICKED CORRECTLY: {tool_ok}/{total}")


if __name__ == "__main__":
    main()
