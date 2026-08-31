"""The v2 tool surface: 25 functions whose arguments ARE personal data.

WHY THIS FILE EXISTS AT ALL. Seven family generators were written in parallel and
each defined its own schemas locally, which was the right call while they were
being written — a shared module edited by seven authors at once is a merge
conflict, not a contract. It is the wrong call once they land: `update_delivery_address`
is offered by five families and they wrote it four different ways, and a benchmark
whose published claim is «replay this against any provider, score any gateway»
cannot mean four things by one function name.

WHAT THIS FILE IS AND IS NOT. It is the canonical registry and the drift check.
It is NOT a rewriter: `build.py` reports divergence between a case's embedded
schema and the entry here, and ships the case exactly as its author validated it.
Silently swapping a schema underneath a family would change what its cases demand
of a model — `required` in particular tells the model which arguments it MUST
supply — and a corpus assembler is not the right place to make that decision for
five other authors. The drift list is a work item with names and numbers on it,
which is more useful than a quiet repair.

HOW THE CANONICAL ENTRY IS DERIVED, and both halves cost something:

  properties  the UNION over every variant observed in the corpus. A parameter
              absent from the offered schema is a value the model has nowhere to
              put, so the widest surface is the one that never forces a correct
              agent to drop a datum it was given.
  required    the UNION as well, and this is the arguable half. A family that
              marked a parameter required did so because its own cases determine
              that value; the intersection would be safer for a case that does
              not, but it also lets a model omit an argument the round trip pins
              — `send_invoice.email` is exactly that, 45 gold EMAIL items in
              `transfer` — and an omitted argument is scored `model_absent`,
              which moves a gateway result into the model's column. Union keeps
              the failure where it can be seen. The price is named in the drift
              report: a case whose conversation does not determine a required
              parameter invites an invented value, and `book_appointment.phone`
              is the one live instance.

Plain OpenAI function-calling JSON, typed exactly as loosely as the provider's
own contract, so the corpus replays with no translation layer and a competing
gateway can be scored on it without adopting anything of ours.

`PII_PARAMS` names the arguments that carry a real personal value. It is metadata
for the scorer and never goes on the wire: those are the arguments the round-trip
axis checks, and the ones where a fake value silently reaching the tool is the
exact failure the product exists to prevent.
"""

from typing import Any

from bench.agentpii2.schema import Case, ToolSchema


def _tool(name: str, description: str, params: dict[str, tuple[str, str]],
          required: list[str]) -> ToolSchema:
    """One schema, built fresh. Callers get a deep copy from `schema_for` rather
    than this object: the schemas travel into a JSON corpus AND into a provider
    call, and one shared mutable dict would let a scorer's edit reach every case
    that offers the tool."""
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


# THE TEN FROM v1 PLUS FIFTEEN THE v2 FAMILIES NEEDED. The new ones are almost
# all READERS — `find_orders`, `list_clients`, `get_ticket_note` — and that is
# not an accident of authorship: `indirect`, `result` and `rank` all begin with
# the customer's own CRM handing the model personal data it never typed, and v1
# had no such tool because it had no such case.
TOOLS: dict[str, ToolSchema] = {
    "add_contact": _tool(
        "add_contact",
        "Добавить контакт в CRM.",
        {
            "name": ("string", "ФИО контакта"),
            "phone": ("string", "Телефон"),
            "email": ("string", "Электронная почта"),
        },
        ["name", "phone"]),

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

    "cancel_order": _tool(
        "cancel_order",
        "Отменить заказ.",
        {
            "order_id": ("string", "Номер заказа"),
            "reason": ("string", "Причина отмены"),
        },
        ["order_id"]),

    "check_order_status": _tool(
        "check_order_status",
        "Узнать статус заказа по его номеру и телефону покупателя.",
        {
            "order_id": ("string", "Номер заказа, например A-4471"),
            "phone": ("string", "Телефон, указанный при оформлении"),
        },
        ["order_id", "phone"]),

    "create_order": _tool(
        "create_order",
        "Оформить заказ на клиента и отправить его в доставку.",
        {
            "customer_name": ("string", "ФИО получателя как в паспорте"),
            "phone": ("string", "Контактный телефон получателя"),
            "address": ("string", "Адрес доставки с домом и квартирой"),
            "items": ("string", "Артикулы товаров через запятую"),
        },
        ["address", "customer_name", "phone"]),

    "escalate_ticket": _tool(
        "escalate_ticket",
        "Передать обращение старшему специалисту с контактами клиента.",
        {
            "customer_name": ("string", "ФИО клиента"),
            "phone": ("string", "Телефон для обратной связи"),
            "summary": ("string", "Краткое описание проблемы"),
            "order_id": ("string", "Номер заказа, если он известен"),
        },
        ["customer_name", "phone", "summary"]),

    "find_customer": _tool(
        "find_customer",
        "Найти карточку клиента по номеру его заказа.",
        {
            "order_id": ("string", "Номер заказа"),
        },
        ["order_id"]),

    "find_orders": _tool(
        "find_orders",
        "Найти прошлые заказы клиента по номеру заказа.",
        {
            "order_id": ("string", "Номер заказа, например A-4471"),
        },
        ["order_id"]),

    "get_ticket_note": _tool(
        "get_ticket_note",
        "Прочитать заметку оператора по обращению.",
        {
            "ticket_id": ("string", "Номер обращения"),
        },
        ["ticket_id"]),

    "issue_refund": _tool(
        "issue_refund",
        "Вернуть деньги на карту, с которой была оплата.",
        {
            "card_number": ("string", "Номер карты для возврата"),
            "amount": ("number", "Сумма возврата в рублях"),
            "customer_name": ("string", "ФИО держателя карты"),
        },
        ["amount", "card_number"]),

    "list_clients": _tool(
        "list_clients",
        "Показать клиентов филиала с датами рождения.",
        {
            "branch": ("string", "Код филиала"),
        },
        ["branch"]),

    "list_contacts": _tool(
        "list_contacts",
        "Показать контакты, привязанные к аккаунту.",
        {
            "account_id": ("string", "Идентификатор аккаунта"),
        },
        ["account_id"]),

    "list_order_addresses": _tool(
        "list_order_addresses",
        "Показать адреса из прошлых заказов клиента.",
        {
            "order_id": ("string", "Номер текущего заказа"),
            "period": ("string", "Период выборки"),
        },
        ["order_id"]),

    "list_partners": _tool(
        "list_partners",
        "Показать партнёров-ИП с их ИНН.",
        {
            "period": ("string", "Период выборки"),
        },
        ["period"]),

    "list_products": _tool(
        "list_products",
        "Найти товары в каталоге.",
        {
            "query": ("string", "Поисковый запрос"),
        },
        ["query"]),

    "list_recent_orders": _tool(
        "list_recent_orders",
        "Показать последние заказы с телефонами.",
        {
            "period": ("string", "Период выборки"),
        },
        ["period"]),

    "lookup_order": _tool(
        "lookup_order",
        "Найти заказ по его номеру и ФИО получателя.",
        {
            "order_id": ("string", "Номер заказа"),
            "customer_name": ("string", "ФИО получателя"),
        },
        ["customer_name", "order_id"]),

    "notify_customer": _tool(
        "notify_customer",
        "Отправить клиенту сообщение по телефону.",
        {
            "phone": ("string", "Телефон клиента"),
            "text": ("string", "Текст сообщения"),
        },
        ["phone", "text"]),

    "register_address": _tool(
        "register_address",
        "Записать адрес клиента в заявку.",
        {
            "address": ("string", "Адрес клиента дословно, как он прозвучал"),
        },
        ["address"]),

    "register_vehicle": _tool(
        "register_vehicle",
        "Записать автомобиль на сервисное обслуживание.",
        {
            "plate": ("string", "Государственный регистрационный номер"),
            "vin": ("string", "VIN автомобиля, 17 символов"),
            "owner_name": ("string", "ФИО владельца"),
            "owner_phone": ("string", "Телефон владельца"),
        },
        ["owner_phone", "plate"]),

    "schedule_callback": _tool(
        "schedule_callback",
        "Поставить обратный звонок клиенту.",
        {
            "phone": ("string", "Телефон для звонка"),
            "name": ("string", "ФИО клиента"),
            "when": ("string", "Когда позвонить"),
        },
        ["phone"]),

    "schedule_delivery": _tool(
        "schedule_delivery",
        "Поставить доставку по указанному адресу.",
        {
            "order_id": ("string", "Номер заказа"),
            "address": ("string", "Адрес доставки с домом и квартирой"),
            "date": ("string", "Желаемая дата доставки"),
        },
        ["address", "order_id"]),

    "send_invoice": _tool(
        "send_invoice",
        "Выставить счёт индивидуальному предпринимателю и отправить на почту.",
        {
            "email": ("string", "Электронная почта для отправки счёта"),
            "inn": ("string", "ИНН плательщика — физического лица или ИП"),
            "company_name": ("string", "Наименование плательщика"),
            "amount": ("number", "Сумма счёта в рублях"),
        },
        ["amount", "email", "inn"]),

    "update_delivery_address": _tool(
        "update_delivery_address",
        "Изменить адрес доставки у существующего заказа.",
        {
            "order_id": ("string", "Номер заказа"),
            "address": ("string", "Новый адрес с домом и квартирой"),
            "recipient_name": ("string", "ФИО получателя, если он меняется"),
        },
        ["address", "order_id"]),

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

}


# WHICH ARGUMENTS CARRY A REAL PERSONAL VALUE, per tool. The round-trip axis
# checks exactly these; everything else — an order number, a period, a summary —
# may be paraphrased by the model without it counting as damage.
#
# A READER'S ARGUMENTS ARE NOT ON THIS LIST even when they look personal.
# `find_customer(order_id)` and `list_clients(branch)` take non-personal keys by
# construction: that is what makes the `indirect` and `result` families able to
# say «the customer never stated the datum». A tool that had to be called WITH a
# personal value to return one would collapse the two paths into the one v1
# already measured.
PII_PARAMS: dict[str, tuple[str, ...]] = {
    "add_contact": ("name", "phone", "email"),
    "book_appointment": ("client_name", "phone", "birth_date"),
    "cancel_order": (),
    "check_order_status": ("phone",),
    "create_order": ("customer_name", "phone", "address"),
    "escalate_ticket": ("customer_name", "phone"),
    "find_customer": (),
    "find_orders": (),
    "get_ticket_note": (),
    "issue_refund": ("card_number", "customer_name"),
    "list_clients": (),
    "list_contacts": (),
    "list_order_addresses": (),
    "list_partners": (),
    "list_products": (),
    "list_recent_orders": (),
    "lookup_order": ("customer_name",),
    "notify_customer": ("phone",),
    "register_address": ("address",),
    "register_vehicle": ("plate", "vin", "owner_name", "owner_phone"),
    "schedule_callback": ("name", "phone"),
    "schedule_delivery": ("address",),
    "send_invoice": ("email", "inn"),
    "update_delivery_address": ("address", "recipient_name"),
    "verify_identity": ("full_name", "passport", "snils", "inn"),
}


def schema_for(name: str) -> ToolSchema:
    """A fresh copy of one canonical schema.

    Deep-copied by reconstruction rather than by `copy.deepcopy` so the shape is
    obvious at the call site: a case's `tools` list is serialised into the corpus
    file, and a shared nested dict there means one edit reaches every case that
    offers the tool.
    """
    source = TOOLS[name]["function"]
    parameters = source["parameters"]
    return {
        "type": "function",
        "function": {
            "name": source["name"],
            "description": source["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    key: dict(value)
                    for key, value in parameters["properties"].items()
                },
                "required": list(parameters["required"]),
            },
        },
    }


def tools_for(primary: str, distractors: tuple[str, ...]) -> list[ToolSchema]:
    """The offered tool set for one case: the primary plus named distractors.

    ALWAYS MORE THAN ONE TOOL, and the distractors are NAMED rather than taken
    off the top of `TOOLS`. v1 took `[name for name in TOOLS if name != primary][:2]`,
    which made the offered set a function of dictionary insertion order — adding a
    tool to the registry silently changed which distractors 1056 cases had seen,
    and the corpus stopped being comparable to its own previous version for a
    reason that had nothing to do with the corpus.

    A single-tool prompt lets a model succeed by having nowhere else to go, which
    hides whether masking damaged its ability to CHOOSE — and choosing is where
    an implausible substitute does its damage.
    """
    return [schema_for(primary)] + [schema_for(name) for name in distractors]


def drift(cases: list[Case]) -> list[str]:
    """Where a case's embedded schema disagrees with the canonical entry.

    NOT A VALIDATION FAILURE, and the distinction is deliberate. Each case is
    internally consistent — `schema.validate` already proved every `tool_param` it
    claims exists in the schema it ships — so a divergence here breaks nothing
    about scoring that case. It breaks the CORPUS-level claim: that a replay
    harness can register one tool surface and run the whole file against it, and
    that two families' numbers for the same tool are about the same contract.

    Reported per (tool, field) rather than per case, because the same divergence
    repeats across hundreds of cases and a per-case list would bury the four
    facts inside four thousand lines.
    """
    problems: list[str] = []
    seen: dict[str, dict[str, set[str]]] = {}
    families: dict[str, set[str]] = {}
    for case in cases:
        for tool in case.tools:
            function = tool["function"]
            name = str(function["name"])
            families.setdefault(name, set()).add(case.family)
            fields = seen.setdefault(name, {})
            fields.setdefault("description", set()).add(str(function["description"]))
            parameters = function["parameters"]
            fields.setdefault("properties", set()).add(
                ",".join(sorted(parameters["properties"])))
            fields.setdefault("required", set()).add(
                ",".join(sorted(parameters.get("required", ()))))
    for name in sorted(seen):
        if name not in TOOLS:
            problems.append(f"tool {name!r} is offered by "
                            f"{sorted(families[name])} and is not in the registry")
            continue
        canonical = TOOLS[name]["function"]
        expected = {
            "description": str(canonical["description"]),
            "properties": ",".join(sorted(canonical["parameters"]["properties"])),
            "required": ",".join(sorted(canonical["parameters"]["required"])),
        }
        for field, values in sorted(seen[name].items()):
            if values == {expected[field]}:
                continue
            problems.append(
                f"{name}.{field}: {len(values)} form(s) across "
                f"{sorted(families[name])} — corpus has {sorted(values)}, "
                f"registry has {expected[field]!r}")
    return problems


__all__ = ["TOOLS", "PII_PARAMS", "schema_for", "tools_for", "drift"]
