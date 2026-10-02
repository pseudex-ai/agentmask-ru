"""Generate a .md transcript of live dialogues: every message/tool/result with
TWO columns — what the MODEL saw (fakes) vs what the USER/TOOL saw (real).
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
    {"type": "function", "function": {"name": "find_client",
        "description": "Найти клиента по телефону или паспорту.",
        "parameters": {"type": "object", "properties": {
            "phone": {"type": "string"}, "passport": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "create_order",
        "description": "Создать заказ доставки.",
        "parameters": {"type": "object", "properties": {
            "address": {"type": "string"}, "recipient": {"type": "string"},
            "phone": {"type": "string"}}, "required": ["address", "recipient", "phone"]}}},
    {"type": "function", "function": {"name": "update_order",
        "description": "Обновить адрес/получателя заказа.",
        "parameters": {"type": "object", "properties": {
            "order_id": {"type": "string"}, "address": {"type": "string"},
            "recipient": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "verify_identity",
        "description": "Проверить паспорт для отчётности.",
        "parameters": {"type": "object", "properties": {
            "passport": {"type": "string"}, "name": {"type": "string"}}}}},
]

SYSTEM = ("Ты оператор доставки. Клиент пишет небрежно, иногда диктует цифры словами. "
          "Работай с инструментами, можно несколько за один ход, отвечай коротко по-русски.")

DB = {"next_order": 1000}


def mock_tool(name, args):
    if name == "find_client":
        key = args.get("phone") or args.get("passport")
        return {"found": bool(DB.get(key)), "client": DB.get(key)}
    if name == "create_order":
        oid = f"ORD-{DB['next_order']}"
        DB["next_order"] += 1
        DB[args.get("phone")] = {"name": args.get("recipient"), "order": oid}
        return {"order_id": oid, "status": "created", "address": args.get("address")}
    if name == "update_order":
        return {"order_id": args.get("order_id"), "updated": True,
                "address": args.get("address"), "recipient": args.get("recipient")}
    if name == "verify_identity":
        return {"verified": True, "passport_ok": True}
    return {"ok": True}


def run_dialogue(title, turns):
    d = Detector()
    v = Vault(":memory:", f"demo-{title}")
    messages = [{"role": "system", "content": SYSTEM}]
    blocks = [{"kind": "h1", "title": title}]
    for user_raw in turns:
        spans = d.detect(user_raw)
        user_masked = redact.mask_text(user_raw, v, spans)
        blocks.append({"kind": "user", "real": user_raw, "model": user_masked})
        messages.append({"role": "user", "content": user_masked})
        while True:
            r = client.chat.completions.create(model=MODEL, messages=messages,
                                               tools=TOOLS, tool_choice="auto")
            msg = r.choices[0].message
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    args_fake = tc.function.arguments
                    args_real = redact.unmask_text(args_fake, v)
                    result = mock_tool(tc.function.name, json.loads(args_real))
                    result_json = json.dumps(result, ensure_ascii=False)
                    result_masked = redact.mask_text(result_json, v, d.detect(result_json))
                    blocks.append({"kind": "tool", "name": tc.function.name,
                                   "model": args_fake, "real": args_real,
                                   "result_real": result_json, "result_model": result_masked})
                    messages.append({"role": "assistant", "content": None,
                                     "tool_calls": [tc.model_dump()]})
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": result_masked})
            else:
                final_real = redact.unmask_text(msg.content, v)
                blocks.append({"kind": "agent", "model": msg.content, "real": final_real})
                messages.append({"role": "assistant", "content": msg.content})
                break
    return blocks


def render_md(blocks):
    out = ["# Живые диалоги — Pseudex (две стороны каждого сообщения)\n",
           "> **Модель видит** — только фейки (маскированные). **Пользователь/инструмент видят** — реальные данные.\n",
           "> Легенда: `USER` сообщение пользователя · `TOOL` вызов инструмента · `RESULT` результат инструмента · `AGENT` ответ агента.\n"]
    for b in blocks:
        if b["kind"] == "h1":
            out.append(f"\n## {b['title']}\n")
        elif b["kind"] == "user":
            out.append(f"\n**👤 ПОЛЬЗОВАТЕЛЬ**\n\n"
                       f"| что видит | текст |\n|---|---|\n"
                       f"| пользователь (real) | {b['real']} |\n"
                       f"| модель (masked) | {b['model']} |\n")
        elif b["kind"] == "tool":
            out.append(f"\n**🔧 АГЕНТ → {b['name']}**\n\n"
                       f"| что видит | аргументы |\n|---|---|\n"
                       f"| модель (fake) | `{b['model']}` |\n"
                       f"| инструмент (real) | `{b['real']}` |\n\n"
                       f"**↩️ результат {b['name']}**\n\n"
                       f"| что видит | результат |\n|---|---|\n"
                       f"| инструмент (real) | `{b['result_real']}` |\n"
                       f"| модель (masked) | `{b['result_model']}` |\n")
        elif b["kind"] == "agent":
            out.append(f"\n**🤖 АГЕНТ (ответ пользователю)**\n\n"
                       f"| что видит | текст |\n|---|---|\n"
                       f"| модель (fake) | {b['model']} |\n"
                       f"| пользователь (real) | {b['real']} |\n")
    return "\n".join(out)


cases = [
    ("Оформление заказа + смена адреса + паспорт", [
        "привет! оформи доставку: адрес москва тверская 15 кв 42, получатель иванов петр сергеевич, тел +7 916 402-11-87, паспорт серия 4512 номер 345678 для отчета",
        "а можно адрес поменять? на улица ленина 10 кв 3, это к жене",
        "а паспорт точно обязателен? я не хочу его светить лишний раз",
        "ок, получатель не я, а жена — анна иванова, телефон тот же",
    ]),
    ("Поддержка + восстановление заказа", [
        "здравствуйте, я кузнецова ольга, заказ не пришёл, телефон +7 999 123-45-67, адрес у меня улица мира 22 кв 8, паспорт 4509 123456",
        "а можно проверить по паспорту? телефон я могла перепутать",
        "нашли? поменяйте тогда адрес на улица гагарина 5, получатель тот же",
    ]),
    ("Диктовка цифр словами + коррекция имени", [
        "здравствуйте, запишите мой номер: восемь девятьсот шестнадцать, четыреста два, одиннадцать восемьдесят семь. адрес — улица лермонтова, дом тридцать восемь, квартира семь. имя курт кобейн, паспорт сорок пять ноль девять сто двадцать три четыреста пятьдесят шесть",
        "ой, имя неправильно — не курт кобейн, а иванов иван иванович",
        "и квартира не семь, а сорок два, поправьте пожалуйста",
    ]),
]

all_blocks = []
for title, turns in cases:
    all_blocks += run_dialogue(title, turns)

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_dialogue.md")
open(out_path, "w", encoding="utf-8").write(render_md(all_blocks))
print(f"written: {out_path}")
