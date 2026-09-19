"""The tool catalogue: six OpenAI-style function schemas.

Each family has one PRIMARY tool the agent is expected to call and two
DISTRACTORS, so a masker that rewrites tool definitions (some mask the
descriptions) is exercised on more than one schema. Parameters are typed as
strings on purpose: the benchmark measures whether the REAL value reaches
the tool, and a numeric type would let a JSON layer normalise a phone before
anyone looks at it.

`PII_PARAMS` says which parameter of which tool carries personal data;
`PLAIN_PARAMS` says which carry the negatives (an order number, an amount)
that must reach the tool untouched.
"""


def _tool(name: str, description: str, params: dict[str, tuple[str, str]], required: tuple[str, ...]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": kind, "description": desc} for key, (kind, desc) in params.items()},
                "required": list(required),
            },
        },
    }


TOOLS: dict[str, dict[str, object]] = {
    "create_order": _tool(
        "create_order",
        "Оформить заказ на доставку. Требует ФИО получателя, контактный телефон и адрес доставки.",
        {
            "name": ("string", "ФИО получателя, как назвал клиент"),
            "phone": ("string", "Контактный телефон получателя"),
            "address": ("string", "Адрес доставки одной строкой"),
            "comment": ("string", "Комментарий курьеру"),
        },
        ("name", "phone", "address"),
    ),
    "check_status": _tool(
        "check_status",
        "Проверить статус заказа по номеру заказа или по телефону клиента.",
        {
            "order_no": ("string", "Номер заказа, если клиент его назвал"),
            "phone": ("string", "Телефон клиента, если номер заказа неизвестен"),
        },
        (),
    ),
    "verify_identity": _tool(
        "verify_identity",
        "Подтвердить личность клиента перед выдачей персональной информации.",
        {
            "name": ("string", "ФИО клиента"),
            "dob": ("string", "Дата рождения, как назвал клиент"),
            "passport": ("string", "Серия и номер паспорта"),
            "snils": ("string", "СНИЛС"),
        },
        ("name",),
    ),
    "refund": _tool(
        "refund",
        "Оформить возврат средств на карту клиента.",
        {
            "order_no": ("string", "Номер заказа"),
            "card": ("string", "Номер карты для возврата"),
            "amount": ("string", "Сумма возврата в рублях"),
        },
        ("order_no", "card", "amount"),
    ),
    "send_sms": _tool(
        "send_sms",
        "Отправить SMS клиенту.",
        {
            "phone": ("string", "Телефон получателя"),
            "text": ("string", "Текст сообщения"),
        },
        ("phone", "text"),
    ),
    "update_contact": _tool(
        "update_contact",
        "Обновить контактные данные клиента в CRM.",
        {
            "name": ("string", "ФИО клиента"),
            "phone": ("string", "Новый телефон"),
            "email": ("string", "Новая электронная почта"),
        },
        ("name",),
    ),
}

PII_PARAMS: dict[str, dict[str, str]] = {
    "create_order": {"name": "NAME", "phone": "PHONE", "address": "ADDRESS"},
    "check_status": {"phone": "PHONE"},
    "verify_identity": {"name": "NAME", "dob": "DOB", "passport": "PASSPORT", "snils": "SNILS"},
    "refund": {"card": "CARD"},
    "send_sms": {"phone": "PHONE"},
    "update_contact": {"name": "NAME", "phone": "PHONE", "email": "EMAIL"},
}

PLAIN_PARAMS: dict[str, tuple[str, ...]] = {
    "create_order": ("comment",),
    "check_status": ("order_no",),
    "verify_identity": (),
    "refund": ("order_no", "amount"),
    "send_sms": ("text",),
    "update_contact": (),
}


def tools_for(primary: str) -> tuple[dict[str, object], ...]:
    """The primary tool plus two distractors, in a fixed order so the corpus
    is deterministic and a masker cannot be helped by position."""
    names = list(TOOLS)
    i = names.index(primary)
    chosen = [primary, names[(i + 1) % len(names)], names[(i + 2) % len(names)]]
    return tuple(TOOLS[n] for n in chosen)
