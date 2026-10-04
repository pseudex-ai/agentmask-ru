"""Phase 4 — hop-style form + edge cases, on a LIVE agent (deepseek) with mocks.

Three scenarios the owner named:
1. hop-style form: a dictated/typo address «теритина десять» must keep ONE fake
   across the user turn, the tool args {street,build}, the api result and the
   final answer.
2. api-list: the maps tool returns 10 addresses — what does the engine do with
   all of them, and can the agent still place the order?
3. near-duplicate: «Шейкмана 5» vs the company's real «Шуйкмана 5» — does the
   agent answer «нет, мы на Шуйкмана 5» because it saw a different fake?
"""
import json
import os
import testkit

testkit.load_dev_bundle()
from pseudex.detect_all import Detector
from pseudex.vault import Vault
from pseudex import redact
from openai import OpenAI

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
MODEL = "deepseek-chat"

TOOLS = [
    {"type": "function", "function": {"name": "geocode",
        "description": "Поиск адреса в картографическом API. Возвращает список кандидатов.",
        "parameters": {"type": "object", "properties": {
            "street": {"type": "string"}, "build": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "company_info",
        "description": "Адрес офиса компании.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "create_order",
        "description": "Создать заказ доставки.",
        "parameters": {"type": "object", "properties": {
            "address": {"type": "string"}, "recipient": {"type": "string"}},
            "required": ["address"]}}},
]

SYSTEM = ("Ты оператор доставки. Клиент пишет небрежно. Найди адрес через geocode, "
          "уточни при необходимости, оформи заказ через create_order. Отвечай коротко по-русски.")


def run(scenario, user_text, tool_impl):
    print("\n" + "=" * 80)
    print(f"СЦЕНАРИЙ: {scenario}")
    print("=" * 80)
    d = Detector()
    v = Vault(":memory:", f"p4-{scenario[:12]}")
    spans = d.detect(user_text)
    masked = redact.mask_text(user_text, v, spans)
    print(f"\n[user raw]    {user_text}")
    print(f"[user masked] {masked}")
    for s in spans:
        print(f"   замены: {s.entity_type:6} {user_text[s.start:s.end]!r} -> {v.tokenize(user_text[s.start:s.end], s.entity_type)}")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": masked}]
    for hop in range(8):
        r = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto")
        msg = r.choices[0].message
        if msg.tool_calls:
            for tc in msg.tool_calls:
                args_fake = tc.function.arguments
                args_real = redact.unmask_text(args_fake, v)
                print(f"\n[агент -> {tc.function.name}] fake args: {args_fake}")
                print(f"    размаскировано (tool видит): {args_real}")
                result = tool_impl(tc.function.name, json.loads(args_real))
                result_json = json.dumps(result, ensure_ascii=False)
                result_masked = redact.mask_text(result_json, v, d.detect(result_json))
                print(f"[tool -> модель] real: {result_json}")
                print(f"[tool -> модель] masked: {result_masked}")
                messages.append({"role": "assistant", "content": None, "tool_calls": [tc.model_dump()]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_masked})
        else:
            final_real = redact.unmask_text(msg.content, v)
            print(f"\n[агент -> пользователь] fake: {msg.content}")
            print(f"[агент -> пользователь] РАЗМАСКИРОВАНО: {final_real}")
            break


# --- scenario 1: hop-style form (dictated address) ---
def geo_single(name, args):
    if name == "geocode":
        return {"candidates": [{"real": True, "address": "ул. Тверитина, д. 10", "confidence": 0.87}]}
    if name == "create_order":
        return {"order_id": "ORD-2000", "status": "created"}
    return {"ok": True}

run("1) hop-style: «теритина десять» -> {street,build} -> api -> ответ",
    "доставка на теритина десять, получатель иванов петр",
    geo_single)


# --- scenario 2: api-list (10 addresses) ---
def geo_list(name, args):
    if name == "geocode":
        return {"candidates": [
            {"real": True, "address": "ул. Тверитина, д. 10", "confidence": 0.87},
            {"real": False, "address": "ул. Тверитина, д. 10к1", "confidence": 0.81},
            {"real": False, "address": "ул. Тверитина, д. 10к2", "confidence": 0.74},
            {"real": False, "address": "ул. Тверитина, д. 12", "confidence": 0.69},
            {"real": False, "address": "ул. Тверитина, д. 8", "confidence": 0.63},
            {"real": False, "address": "ул. Тверитинская, д. 10", "confidence": 0.55},
            {"real": False, "address": "пер. Тверитина, д. 10", "confidence": 0.48},
            {"real": False, "address": "ул. Тверитина, д. 10с1", "confidence": 0.42},
            {"real": False, "address": "ул. Тверитина, д. 11", "confidence": 0.37},
            {"real": False, "address": "ул. Тверитина, д. 9", "confidence": 0.31},
        ]}
    if name == "create_order":
        return {"order_id": "ORD-2001", "status": "created"}
    return {"ok": True}

run("2) api вернул 10 адресов — что мы с ними сделаем?",
    "доставка на теритина 10, получатель кузнецова ольга",
    geo_list)


# --- scenario 3: near-duplicate street ---
def company_addr(name, args):
    if name == "company_info":
        return {"address": "ул. Шуйкмана, д. 5", "city": "Екатеринбург"}
    if name == "create_order":
        return {"order_id": "ORD-2002", "status": "created"}
    return {"ok": True}

run("3) «Шейкмана 5» vs настоящий «Шуйкмана 5»",
    "а вы на шейкмана 5 находитесь?",
    company_addr)
