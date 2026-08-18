"""Инструменты водовоза: схемы и заглушки, которые НИКОГДА не падают.

WHY THEY ARE STUPID ON PURPOSE. This run does not ask whether the agent solved
the customer's problem — it asks three things the business logic cannot affect:

  * did the REAL value arrive in the arguments (round trip),
  * did any real value reach the model (leak),
  * did masking change what the model did (transparency).

A tool that fails makes the model retry, apologise and re-plan, and the
transparency axis then measures our mock rather than our gateway. So every tool
succeeds, and its answer is built from the arguments it was given.

STATE IS A DICT, not SQLite. The only thing that has to survive between turns is
«the order I just created» — a customer asking to move the delivery they booked
two messages ago. A database would add schema, migrations and a failure mode, to
store six keys.

The six tools are the intents the corpus actually contains, measured across 993
dialogues: ordering 84%, containers 54%, scheduling 53%, payment 49%, address
46%, cancellation 11%.
"""

from typing import Any

SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Оформить заказ воды на клиента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "ФИО клиента"},
                    "phone": {"type": "string", "description": "Телефон клиента"},
                    "address": {"type": "string", "description": "Адрес доставки"},
                    "bottles": {"type": "integer", "description": "Сколько бутылей"},
                    "delivery_date": {"type": "string", "description": "Дата доставки"},
                },
                "required": ["phone", "address", "bottles"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_orders",
            "description": "Найти заказы клиента по телефону.",
            "parameters": {
                "type": "object",
                "properties": {"phone": {"type": "string"}},
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_order",
            "description": "Перенести или отменить заказ.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "new_date": {"type": "string"},
                    "cancel": {"type": "boolean"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_address",
            "description": "Изменить адрес доставки по заказу.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "address": {"type": "string"},
                },
                "required": ["order_id", "address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_payment_link",
            "description": "Отправить ссылку на оплату заказа.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_container_pickup",
            "description": "Записать возврат пустой тары.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "address": {"type": "string"},
                    "bottles": {"type": "integer"},
                    "pickup_date": {"type": "string"},
                },
                "required": ["address"],
            },
        },
    },
]


class MockTools:
    """Всегда успешен, ответ собран из аргументов, состояние — словарь."""

    def __init__(self) -> None:
        self.orders: dict[str, dict[str, Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self._next = 1

    def _order_id(self) -> str:
        value = f"W-{self._next:05d}"
        self._next += 1
        return value

    def run(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Every call is recorded BEFORE it is answered.

        The record is the measurement: what the model asked for, verbatim, is
        what the round-trip axis inspects. An answer that failed to be produced
        would still have to leave a record, or a crash would look like silence.
        """
        self.calls.append({"name": name, "arguments": arguments})
        handler = getattr(self, f"_{name}", None)
        if handler is None:
            # An unknown tool still succeeds. The model inventing a name is a
            # finding about the MODEL, and turning it into an error here would
            # make the model re-plan and pollute the transparency axis.
            return {"ok": True, "note": f"инструмент {name} выполнен"}
        return handler(arguments)

    def _create_order(self, a: dict[str, Any]) -> dict[str, Any]:
        order_id = self._order_id()
        self.orders[order_id] = dict(a)
        return {"ok": True, "order_id": order_id,
                "delivery_date": a.get("delivery_date") or "завтра",
                "bottles": a.get("bottles", 1), "address": a.get("address", "")}

    def _find_orders(self, a: dict[str, Any]) -> dict[str, Any]:
        phone = a.get("phone", "")
        found = [{"order_id": oid, **data} for oid, data in self.orders.items()
                 if data.get("phone") == phone]
        if not found:
            # A canned order rather than an empty list: «ничего не найдено»
            # sends the model down an apology branch that has nothing to do with
            # masking, and the two arms then diverge for a reason that is ours.
            order_id = self._order_id()
            self.orders[order_id] = {"phone": phone, "address": "", "bottles": 2}
            found = [{"order_id": order_id, "phone": phone, "bottles": 2,
                      "status": "в доставке", "delivery_date": "завтра"}]
        return {"ok": True, "orders": found}

    def _reschedule_order(self, a: dict[str, Any]) -> dict[str, Any]:
        order = self.orders.setdefault(a.get("order_id", "W-00000"), {})
        if a.get("cancel"):
            order["status"] = "отменён"
            return {"ok": True, "order_id": a.get("order_id"), "status": "отменён"}
        order["delivery_date"] = a.get("new_date", "")
        return {"ok": True, "order_id": a.get("order_id"),
                "new_date": a.get("new_date", ""), "status": "перенесён"}

    def _update_address(self, a: dict[str, Any]) -> dict[str, Any]:
        order = self.orders.setdefault(a.get("order_id", "W-00000"), {})
        order["address"] = a.get("address", "")
        return {"ok": True, "order_id": a.get("order_id"),
                "address": a.get("address", "")}

    def _send_payment_link(self, a: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "order_id": a.get("order_id"),
                "sent_to": a.get("email") or a.get("phone") or "",
                "link": f"https://pay.example/{a.get('order_id', 'W-00000')}"}

    def _schedule_container_pickup(self, a: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "address": a.get("address", ""),
                "bottles": a.get("bottles", 0),
                "pickup_date": a.get("pickup_date") or "завтра"}
