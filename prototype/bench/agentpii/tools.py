"""Tool schemas whose parameters ARE personal data.

This is the part no existing benchmark has. BFCL's tools move files and query
markets; tau-bench's book flights with synthetic English names. Neither has a
schema where the argument is a Russian passport number that must arrive intact
at a system which will reject a malformed one.

The ten scenarios are the ones a Russian SMB actually automates first, chosen by
what the personal data DOES rather than by which entity types we happen to
support — an inventory built from our own type list would test the detector
against itself.

Every schema is plain OpenAI function-calling JSON, so the corpus can be replayed
against any provider without a translation layer, and a competing gateway can be
scored on it without adopting anything of ours.

`pii_params` names the arguments that carry a real value. It is metadata for the
scorer, not part of the wire schema: those are the arguments the round-trip axis
checks, and the ones where a masked value silently reaching the tool is the exact
failure the product exists to prevent.
"""

from typing import Any


def _tool(name: str, description: str, params: dict[str, tuple[str, str]],
          required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    key: {"type": kind, "description": text}
                    for key, (kind, text) in params.items()
                },
                "required": required,
            },
        },
    }


TOOLS: dict[str, dict[str, Any]] = {
    "create_order": _tool(
        "create_order",
        "Оформить заказ на клиента и отправить его в доставку.",
        {
            "customer_name": ("string", "ФИО получателя как в паспорте"),
            "phone": ("string", "Контактный телефон получателя"),
            "address": ("string", "Адрес доставки с домом и квартирой"),
            "items": ("string", "Артикулы товаров через запятую"),
        },
        ["customer_name", "phone", "address"]),

    "book_appointment": _tool(
        "book_appointment",
        "Записать клиента на приём в выбранный филиал.",
        {
            "client_name": ("string", "ФИО клиента"),
            "phone": ("string", "Телефон для подтверждения записи"),
            "birth_date": ("string", "Дата рождения в формате ДД.ММ.ГГГГ"),
            "service": ("string", "Название услуги"),
        },
        ["client_name", "phone"]),

    "check_order_status": _tool(
        "check_order_status",
        "Узнать статус заказа по его номеру и телефону покупателя.",
        {
            "order_id": ("string", "Номер заказа, например A-4471"),
            "phone": ("string", "Телефон, указанный при оформлении"),
        },
        ["order_id", "phone"]),

    "update_delivery_address": _tool(
        "update_delivery_address",
        "Изменить адрес доставки у существующего заказа.",
        {
            "order_id": ("string", "Номер заказа"),
            "address": ("string", "Новый адрес с домом и квартирой"),
            "recipient_name": ("string", "ФИО получателя, если он меняется"),
        },
        ["order_id", "address"]),

    "verify_identity": _tool(
        "verify_identity",
        "Проверить личность клиента по документам перед выдачей займа.",
        {
            "full_name": ("string", "ФИО полностью"),
            "passport": ("string", "Серия и номер паспорта РФ"),
            "snils": ("string", "Номер СНИЛС"),
            "inn": ("string", "ИНН физического лица"),
        },
        ["full_name", "passport"]),

    "issue_refund": _tool(
        "issue_refund",
        "Вернуть деньги на карту, с которой была оплата.",
        {
            "card_number": ("string", "Номер карты для возврата"),
            "amount": ("number", "Сумма возврата в рублях"),
            "customer_name": ("string", "ФИО держателя карты"),
        },
        ["card_number", "amount"]),

    "register_vehicle": _tool(
        "register_vehicle",
        "Записать автомобиль на сервисное обслуживание.",
        {
            "plate": ("string", "Государственный регистрационный номер"),
            "vin": ("string", "VIN автомобиля, 17 символов"),
            "owner_name": ("string", "ФИО владельца"),
            "owner_phone": ("string", "Телефон владельца"),
        },
        ["plate", "owner_phone"]),

    "send_invoice": _tool(
        "send_invoice",
        "Выставить счёт юридическому лицу и отправить его на почту.",
        {
            "email": ("string", "Электронная почта для отправки счёта"),
            "inn": ("string", "ИНН организации"),
            "company_name": ("string", "Наименование организации"),
            "amount": ("number", "Сумма счёта в рублях"),
        },
        ["email", "inn", "amount"]),

    "add_contact": _tool(
        "add_contact",
        "Добавить контакт в CRM.",
        {
            "name": ("string", "ФИО контакта"),
            "phone": ("string", "Телефон"),
            "email": ("string", "Электронная почта"),
        },
        ["name", "phone"]),

    "escalate_ticket": _tool(
        "escalate_ticket",
        "Передать обращение старшему специалисту с контактами клиента.",
        {
            "customer_name": ("string", "ФИО клиента"),
            "phone": ("string", "Телефон для обратной связи"),
            "summary": ("string", "Краткое описание проблемы"),
        },
        ["customer_name", "phone", "summary"]),
}

# Which arguments of each tool carry a real personal value. The round-trip axis
# checks exactly these; everything else may be paraphrased by the model without
# it counting as damage.
PII_PARAMS: dict[str, tuple[str, ...]] = {
    "create_order": ("customer_name", "phone", "address"),
    "book_appointment": ("client_name", "phone", "birth_date"),
    "check_order_status": ("phone",),
    "update_delivery_address": ("address", "recipient_name"),
    "verify_identity": ("full_name", "passport", "snils", "inn"),
    "issue_refund": ("card_number", "customer_name"),
    "register_vehicle": ("plate", "vin", "owner_name", "owner_phone"),
    "send_invoice": ("email", "inn"),
    "add_contact": ("name", "phone", "email"),
    "escalate_ticket": ("customer_name", "phone"),
}


def tools_for(scenario: str) -> list[dict[str, Any]]:
    """The offered tool set for a scenario.

    Always more than one tool. A single-tool prompt lets a model succeed by
    having nowhere else to go, which hides whether masking damaged its ability to
    CHOOSE — and choosing is where an implausible substitute does its damage.
    """
    primary = TOOLS[scenario]
    distractors = [name for name in TOOLS if name != scenario][:2]
    return [primary] + [TOOLS[name] for name in distractors]
