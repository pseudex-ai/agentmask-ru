"""The six case families. Each builder draws values from the pools, picks a
template for the register, assembles the messages with offsets, and returns
a `Case`.

TEMPLATES ARE THE REGISTER. Nothing is post-processed after assembly: the
clean template writes «Телефон: +7 907 …» and the chat template writes «тел
8907…» because those are different strings, chosen before a single offset
is counted. The `cue` flag on an item records whether the template put a
cue word directly in front of the value — that is where a detector without
context gets its easy cases, and the report prints cue/no-cue apart.

NEGATIVES ARE IN EVERY CASE. An order number, a tracking number, an amount,
a document date, a bare city: values that look like personal data to a
regex and are not. A gateway that masks them breaks the agent's tool call
as surely as a leak breaks the law, and a benchmark without them can be won
by masking everything.

`hard` MARKS THE CASES A NAIVE REGEX IS EXPECTED TO MISS. Gate G7 requires
the reference placeholder masker to alter something in every case unless
the case says why it should not — a lower-case name without a cue word is
the honest example. The flag is set here, at build time, from what the
template knows it wrote.
"""

import hashlib
import random
from dataclasses import dataclass

from agentmask_ru import ids
from agentmask_ru.assemble import Slot, assemble
from agentmask_ru.parts import cut_address, cut_name
from agentmask_ru.pools import Pools, draw_person
from agentmask_ru.pools import Street
from agentmask_ru.registers import (
    declined_name, given_only, name_parts, render_address, render_card, render_dob, render_name, render_passport,
    render_phone, render_snils,
)
from agentmask_ru.schema import CANARY, DATA_LICENSE, VERSION, Case, ExpectedCall, Negative, PiiItem, Source
from agentmask_ru.tools import tools_for

SYSTEM_PROMPT = (
    "Ты — оператор поддержки интернет-магазина «Северный ветер». Отвечай по-русски, коротко. "
    "Для действий с заказами и данными клиента вызывай инструменты; передавай в них значения так, "
    "как их назвал клиент. Служебная метка диалога: [case:{case_id}]."
)


@dataclass(frozen=True)
class Item:
    key: str
    type: str
    value: str
    canonical: str
    tool_param: str | None
    cue: bool
    tier: str | None
    identity: str
    # Could a masker that knows only SHAPES find this value? A capitalised
    # name can be guessed from its capitals; a lower-case one cannot. A
    # phone with its digits intact has a shape; one with a look-alike letter
    # inside them does not. The template knows which it wrote, so the
    # corpus records it rather than asking a detector.
    findable_by_shape: bool
    parts: dict[str, str] | None = None


@dataclass(frozen=True)
class Neg:
    key: str
    value: str
    kind: str


@dataclass(frozen=True)
class Turn:
    parts: list[str | Slot]


@dataclass(frozen=True)
class Draft:
    family: str
    register: str
    subcase: str | None
    turns: list[Turn]                # user turns in order; assistant «Принято.» is inserted between
    items: list[Item]
    negatives: list[Neg]
    expected: ExpectedCall


def _hard_reason(draft: Draft) -> dict[str, str] | None:
    """A case is HARD when nothing in it has a shape to find.

    Gate G7 demands that the naive reference masker leave a mark on every
    case that does not say why it cannot. This is that «why», derived from
    what the templates wrote: not from running a detector over the corpus,
    which would make the corpus a mirror of that detector.
    """
    if not draft.items:
        return {"why": "в сообщении нет персональных данных: случай измеряет только перемаскирование"}
    if any(item.findable_by_shape for item in draft.items):
        return None
    reasons: list[str] = []
    if any(item.type == "NAME" for item in draft.items):
        reasons.append("имя строчными буквами: заглавной, за которую цепляется шаблон, нет")
    if any(item.type != "NAME" for item in draft.items):
        reasons.append("в цифрах стоит буква-двойник или потерян разделитель: формы, которую ищет шаблон, больше нет")
    return {"why": "; ".join(reasons)}


def _finish(draft: Draft, index: int, created_at: str, seed: int) -> Case:
    case_id = f"{draft.family}-{draft.register}-{index:03d}"
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT.format(case_id=case_id)}]
    spans_by_key: dict[str, tuple[int, int, int]] = {}
    for n, turn in enumerate(draft.turns):
        if n > 0:
            messages.append({"role": "assistant", "content": "Принято."})
        built = assemble(turn.parts)
        turn_index = len(messages)
        messages.append({"role": "user", "content": built.text})
        for key, (start, end) in built.spans.items():
            if key in spans_by_key:
                raise ValueError(f"{case_id}: slot {key} used in two turns")
            spans_by_key[key] = (turn_index, start, end)
    pii: list[PiiItem] = []
    for k, item in enumerate(draft.items):
        turn_index, start, end = spans_by_key[item.key]
        pii.append(PiiItem(
            id=f"p{k + 1}", type=item.type, value=item.value, canonical=item.canonical, turn=turn_index,
            start=start, end=end, tool_param=item.tool_param, cue=item.cue, tier=item.tier, identity=item.identity,
            parts=item.parts,
        ))
    negatives: list[Negative] = []
    for neg in draft.negatives:
        turn_index, start, end = spans_by_key[neg.key]
        negatives.append(Negative(value=neg.value, kind=neg.kind, turn=turn_index, start=start, end=end))
    return Case(
        id=case_id, version=VERSION, family=draft.family, register=draft.register, subcase=draft.subcase,
        messages=tuple(messages), tools=tools_for(draft.expected.name), expected_call=draft.expected,
        pii=tuple(pii), negatives=tuple(negatives), hard=_hard_reason(draft), created_at=created_at,
        source=Source(generator="agentmask_ru.build", version=VERSION, seed=seed), canary=CANARY, license=DATA_LICENSE,
    )


# --- negatives ---------------------------------------------------------------

def order_no(rng: random.Random, register: str) -> Neg:
    number = f"{rng.randint(1000, 9999)}-{rng.randint(100, 999)}"
    value = f"№ {number}" if register == "clean" else number
    return Neg(key="order_no", value=value, kind="order_no")


def track_no(rng: random.Random) -> Neg:
    # A 14-digit track looks more like an identifier than most identifiers do.
    return Neg(key="track_no", value="".join(rng.choice("0123456789") for _ in range(14)), kind="track_no")


def amount(rng: random.Random, register: str) -> Neg:
    rub = rng.randint(3, 120) * 100 + rng.choice((0, 50, 90))
    value = f"{rub:,}".replace(",", " ") + (" ₽" if register == "clean" else " руб")
    return Neg(key="amount", value=value, kind="amount")


def doc_date(rng: random.Random) -> Neg:
    return Neg(key="doc_date", value=f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.2026", kind="doc_date")


def city_mention(pools: Pools, rng: random.Random, register: str) -> Neg:
    # A bare city identifies nobody (152-ФЗ ст. 3): a customer saying where
    # they are is not stating personal data, and masking it breaks the reply.
    city = rng.choice(pools.cities[:120])
    return Neg(key="city", value=city if register == "clean" else city.lower(), kind="city")


# --- families ------------------------------------------------------------------

def create_order(pools: Pools, rng: random.Random, register: str, tier: str, index: int, created_at: str, seed: int) -> Case:
    person = draw_person(pools, rng, tier)
    name = render_name(person, register, rng)
    phone = render_phone(ids.phone_digits(rng), register, rng)
    street = rng.choice(pools.streets)
    address = render_address(rng.choice(pools.cities[:200]), street, rng.randint(1, 120), rng.randint(1, 240), register, rng)
    prev = order_no(rng, register)
    money = amount(rng, register)
    # Each variant says whether it put a cue word in front of the name; that
    # is recorded on the item, not guessed afterwards.
    if register == "clean":
        variants: list[tuple[list[str | Slot], bool]] = [
            (["Здравствуйте! Хочу оформить доставку, как в прошлый раз (заказ ", Slot("order_no", prev.value), "). ФИО: ",
              Slot("name", name.value), ". Телефон: ", Slot("phone", phone.value), ". Адрес: ", Slot("address", address.value),
              ". Сумма к оплате была ", Slot("amount", money.value), ", оплачу так же."], True),
            (["Добрый день. Оформите, пожалуйста, новый заказ на ", Slot("name", name.value), ", тел. ", Slot("phone", phone.value),
              ", доставка по адресу ", Slot("address", address.value), ". Предыдущий заказ ", Slot("order_no", prev.value),
              " на ", Slot("amount", money.value), " доставили вовремя, спасибо."], False),
        ]
    else:
        variants = [
            (["привет оформите заказ как прошлый ", Slot("order_no", prev.value), " меня зовут ", Slot("name", name.value),
              " тел ", Slot("phone", phone.value), " адрес ", Slot("address", address.value), " там было ", Slot("amount", money.value)], True),
            (["нужна доставка ", Slot("address", address.value), " ", Slot("name", name.value), " ", Slot("phone", phone.value),
              " прошлый заказ ", Slot("order_no", prev.value), " на ", Slot("amount", money.value), " норм пришел"], False),
        ]
    parts, name_cued = variants[rng.randrange(len(variants))]
    items = [
        Item("name", "NAME", name.value, name.value, "name", name_cued, person.tier, "person1", register == "clean"),
        Item("phone", "PHONE", phone.value, phone.value, "phone", True, None, "person1", not phone.shape_broken),
        Item("address", "ADDRESS", address.value, address.value, "address", True, None, "person1", register == "clean"),
    ]
    draft = Draft("create_order", register, None, [Turn(parts)], items, [prev, money],
                  ExpectedCall("create_order", ("name", "phone", "address"), {}))
    return _finish(draft, index, created_at, seed)


def check_status(pools: Pools, rng: random.Random, register: str, tier: str, index: int, created_at: str, seed: int) -> Case:
    # Two sub-shapes: by phone (personal data) or by order number (none) —
    # the second is a whole case of negatives, which is what an agent sees
    # most of the day.
    by_phone = rng.random() < 0.7
    track = track_no(rng)
    date = doc_date(rng)
    if by_phone:
        phone = render_phone(ids.phone_digits(rng), register, rng)
        if register == "clean":
            parts: list[str | Slot] = ["Подскажите, где мой заказ? Оформлял ", Slot("doc_date", date.value), ", трек-номер ",
                                       Slot("track_no", track.value), ". Телефон при заказе: ", Slot("phone", phone.value), "."]
        else:
            parts = ["где заказ, оформлял ", Slot("doc_date", date.value), " трек ", Slot("track_no", track.value),
                     " мой номер ", Slot("phone", phone.value)]
        items = [Item("phone", "PHONE", phone.value, phone.value, "phone", True, None, "person1", not phone.shape_broken)]
        expected = ExpectedCall("check_status", ("phone",), {})
    else:
        order = order_no(rng, register)
        if register == "clean":
            parts = ["Добрый день. Проверьте статус заказа ", Slot("order_no", order.value), " от ", Slot("doc_date", date.value),
                     ", трек ", Slot("track_no", track.value), " не отслеживается."]
        else:
            parts = ["статус заказа ", Slot("order_no", order.value), " от ", Slot("doc_date", date.value), " трек ",
                     Slot("track_no", track.value), " не работает"]
        draft = Draft("check_status", register, None, [Turn(parts)], [], [order, track, date],
                      ExpectedCall("check_status", (), {"order_no": order.value}))
        return _finish(draft, index, created_at, seed)
    draft = Draft("check_status", register, None, [Turn(parts)], items, [track, date], expected)
    return _finish(draft, index, created_at, seed)


def verify_identity(pools: Pools, rng: random.Random, register: str, tier: str, index: int, created_at: str, seed: int) -> Case:
    person = draw_person(pools, rng, tier)
    name = render_name(person, register, rng)
    birth = render_dob(ids.dob(rng), register, rng)
    use_passport = rng.random() < 0.5
    doc = render_passport(ids.passport(rng), register, rng) if use_passport else render_snils(ids.snils(rng), register, rng)
    doc_type = "PASSPORT" if use_passport else "SNILS"
    doc_param = "passport" if use_passport else "snils"
    contract = Neg("contract", f"{rng.randint(100, 999)}/{rng.randint(10, 99)}", "invoice")
    date = doc_date(rng)
    if register == "clean":
        parts: list[str | Slot] = ["Здравствуйте. Хочу узнать баланс по договору ", Slot("contract", contract.value), " от ",
                                   Slot("doc_date", date.value), ". Данные для проверки: ", Slot("name", name.value),
                                   ", дата рождения ", Slot("dob", birth.value), f", {doc.cue} ", Slot("doc", doc.value), "."]
        name_cued = True
    else:
        parts = ["хочу баланс по договору ", Slot("contract", contract.value), " от ", Slot("doc_date", date.value), " ",
                 Slot("name", name.value), " др ", Slot("dob", birth.value), f" {doc.cue} ", Slot("doc", doc.value)]
        name_cued = False
    items = [
        Item("name", "NAME", name.value, name.value, "name", name_cued, person.tier, "person1", register == "clean"),
        Item("dob", "DOB", birth.value, birth.value, "dob", True, None, "person1", "." in birth.value or "/" in birth.value),
        Item("doc", doc_type, doc.value, doc.value, doc_param, True, None, "person1", not doc.shape_broken),
    ]
    draft = Draft("verify_identity", register, None, [Turn(parts)], items, [contract, date],
                  ExpectedCall("verify_identity", ("name", "dob", doc_param), {}))
    return _finish(draft, index, created_at, seed)


def refund(pools: Pools, rng: random.Random, register: str, tier: str, index: int, created_at: str, seed: int) -> Case:
    card = render_card(ids.card(rng), register, rng)
    order = order_no(rng, register)
    money = amount(rng, register)
    date = doc_date(rng)
    if register == "clean":
        parts: list[str | Slot] = ["Прошу оформить возврат по заказу ", Slot("order_no", order.value), " от ", Slot("doc_date", date.value),
                                   " на сумму ", Slot("amount", money.value), ". Карта для возврата: ", Slot("card", card.value), "."]
    else:
        parts = ["верните деньги за заказ ", Slot("order_no", order.value), " от ", Slot("doc_date", date.value), " сумма ",
                 Slot("amount", money.value), " карта ", Slot("card", card.value)]
    items = [Item("card", "CARD", card.value, card.value, "card", True, None, "person1", not card.shape_broken)]
    draft = Draft("refund", register, None, [Turn(parts)], items, [order, money, date],
                  ExpectedCall("refund", ("card",), {"order_no": order.value, "amount": money.value}))
    return _finish(draft, index, created_at, seed)


def send_sms(pools: Pools, rng: random.Random, register: str, tier: str, index: int, created_at: str, seed: int) -> Case:
    person = draw_person(pools, rng, tier)
    who = given_only(person, register, rng)
    phone = render_phone(ids.phone_digits(rng), register, rng)
    order = order_no(rng, register)
    money = amount(rng, register)
    city = city_mention(pools, rng, register)
    if register == "clean":
        parts: list[str | Slot] = ["Отправьте, пожалуйста, СМС курьеру ", Slot("phone", phone.value), ": заказ ",
                                   Slot("order_no", order.value), " оплачен, ", Slot("amount", money.value),
                                   ", город доставки ", Slot("city", city.value),
                                   ", получатель на месте с 10 до 14. Подпись — ", Slot("name", who.value), "."]
        name_cued = False
    else:
        parts = ["кинь смс на ", Slot("phone", phone.value), " что заказ ", Slot("order_no", order.value), " оплачен ",
                 Slot("amount", money.value), " город ", Slot("city", city.value), " буду с 10 до 14, ", Slot("name", who.value)]
        name_cued = False
    items = [
        Item("phone", "PHONE", phone.value, phone.value, "phone", True, None, "person1", not phone.shape_broken),
        # A one-word signature: even capitalised, a two-capitalised-word rule
        # does not reach it, so it is never findable by shape alone.
        Item("name", "NAME", who.value, who.value, None, name_cued, person.tier, "person1", False),
    ]
    draft = Draft("send_sms", register, None, [Turn(parts)], items, [order, money, city],
                  ExpectedCall("send_sms", ("phone",), {}))
    return _finish(draft, index, created_at, seed)


def second_mention(pools: Pools, rng: random.Random, register: str, tier: str, index: int, created_at: str, seed: int) -> Case:
    """Two user turns. The first names the person and the phone; the second
    refers to the same person again — in lower case, declined, or with the
    phone written differently — and asks for the tool call. The gateway must
    give both mentions the same substitute (consistency) and restore the
    second one into the call."""
    person = draw_person(pools, rng, tier)
    subcase = rng.choice(("lower", "declined", "reformatted"))
    digits = ids.phone_digits(rng)
    first_name = render_name(person, "clean" if register == "clean" else register, rng)
    first_phone = render_phone(digits, register, rng)
    order = order_no(rng, register)
    money = amount(rng, register)
    if register == "clean":
        turn1: list[str | Slot] = ["Здравствуйте, меня зовут ", Slot("name1", first_name.value), ", телефон ",
                                   Slot("phone1", first_phone.value), ". Хочу изменить контакты по заказу ", Slot("order_no", order.value), "."]
    else:
        turn1 = ["привет это ", Slot("name1", first_name.value), " тел ", Slot("phone1", first_phone.value),
                 " хочу поменять контакты по заказу ", Slot("order_no", order.value)]
    if subcase == "lower":
        second_name = first_name.value.lower()
        second_phone, second_phone_broken = first_phone.value, first_phone.shape_broken
    elif subcase == "declined":
        second_name = declined_name(person, rng.choice(("acc", "dat")), register != "clean")
        second_phone, second_phone_broken = first_phone.value, first_phone.shape_broken
    else:
        # The model's own habit, written by the customer: the same number in
        # the other format. Rendered in the opposite register, so a sloppy
        # dialogue gets a tidy second mention and vice versa.
        second_name = first_name.value if register == "clean" else first_name.value.lower()
        rendered = render_phone(digits, "chat" if register == "clean" else "clean", rng)
        second_phone, second_phone_broken = rendered.value, rendered.shape_broken
    if register == "clean":
        turn2: list[str | Slot] = ["Да, оформляйте на ", Slot("name2", second_name), ", номер ", Slot("phone2", second_phone),
                                   ". Сумма заказа ", Slot("amount", money.value), " не меняется."]
    else:
        turn2 = ["да пиши на ", Slot("name2", second_name), " номер ", Slot("phone2", second_phone), " сумма ",
                 Slot("amount", money.value), " та же"]
    items = [
        Item("name1", "NAME", first_name.value, first_name.value, None, True, person.tier, "person1", register == "clean"),
        Item("phone1", "PHONE", first_phone.value, first_phone.value, None, True, None, "person1", not first_phone.shape_broken),
        # The second mention is lower-case whenever the register is, and in
        # the «lower» subcase even a clean dialogue writes it in lower case.
        Item("name2", "NAME", second_name, second_name, "name", False, person.tier, "person1",
             register == "clean" and subcase != "lower"),
        Item("phone2", "PHONE", second_phone, second_phone, "phone", True, None, "person1", not second_phone_broken),
    ]
    draft = Draft("second_mention", register, subcase, [Turn(turn1), Turn(turn2)], items, [order, money],
                  ExpectedCall("update_contact", ("name", "phone"), {}))
    return _finish(draft, index, created_at, seed)




def decompose(pools: Pools, rng: random.Random, register: str, tier: str, index: int, created_at: str, seed: int) -> Case:
    """THE TOOL WANTS THE PARTS. A CRM card takes `last_name` / `first_name` /
    `middle_name` and `street` / `house` / `flat`, not one string each. The
    agent has to cut what it was shown, and here the maskers part company: a
    format-preserving substitute cuts the way the original cuts; a placeholder
    («<PERSON_1>», «[ADDRESS]») cannot be cut, lands whole in the first field
    and leaves the rest empty — and on the way back the gateway can only
    restore the whole into that one field. The gold parts are cut from the
    ORIGINAL by the same rule the scripted agent cuts the substitute with
    (`parts.py`), so the family measures what the masker showed, not how the
    benchmark read it."""
    person = draw_person(pools, rng, tier)
    name_written = name_parts(person, register, rng)
    # Which position is which part, as the register writes it (`name_parts`).
    if register == "clean" and len(name_written) == 3:
        order: tuple[str, ...] = ("last_name", "first_name", "middle_name")
    elif register == "clean":
        order = ("first_name", "last_name")
    else:
        order = ("first_name", "last_name")
    name = " ".join(name_written)
    phone = render_phone(ids.phone_digits(rng), register, rng)
    street = rng.choice(pools.streets)
    address = render_address(rng.choice(pools.cities[:200]), street, rng.randint(1, 120), rng.randint(1, 240), register, rng)
    with_city = _address_has_city(address.value, street)
    prev = order_no(rng, register)
    money = amount(rng, register)
    if register == "clean":
        variants: list[tuple[list[str | Slot], bool]] = [
            (["Здравствуйте! Заведите, пожалуйста, карточку клиента по заказу ", Slot("order_no", prev.value),
              ". ФИО: ", Slot("name", name), ". Телефон: ", Slot("phone", phone.value), ". Адрес: ",
              Slot("address", address.value), ". Сумма заказа ", Slot("amount", money.value), "."], True),
            (["Добрый день. Новый клиент — ", Slot("name", name), ", тел. ", Slot("phone", phone.value),
              ", адрес ", Slot("address", address.value), ". Заказ ", Slot("order_no", prev.value), " на ",
              Slot("amount", money.value), ", занесите в базу."], False),
        ]
    else:
        variants = [
            (["привет заведите клиента по заказу ", Slot("order_no", prev.value), " меня зовут ", Slot("name", name),
              " тел ", Slot("phone", phone.value), " адрес ", Slot("address", address.value), " сумма ",
              Slot("amount", money.value)], True),
            (["добавьте в базу ", Slot("name", name), " ", Slot("phone", phone.value), " живу ",
              Slot("address", address.value), " заказ ", Slot("order_no", prev.value), " на ",
              Slot("amount", money.value)], False),
        ]
    parts, name_cued = variants[rng.randrange(len(variants))]
    name_parts_gold = cut_name(name, order)
    address_parts_gold = cut_address(address.value, with_city)
    items = [
        Item("name", "NAME", name, name, "last_name", name_cued, person.tier, "person1", register == "clean",
             parts=name_parts_gold),
        Item("phone", "PHONE", phone.value, phone.value, "phone", True, None, "person1", not phone.shape_broken),
        Item("address", "ADDRESS", address.value, address.value, "street", True, None, "person1", register == "clean",
             parts=address_parts_gold),
    ]
    pii_params = tuple(order) + ("phone",) + tuple(address_parts_gold)
    draft = Draft("decompose", register, None, [Turn(parts)], items, [prev, money],
                  ExpectedCall("create_contact", pii_params, {}))
    return _finish(draft, index, created_at, seed)


def _address_has_city(written: str, street: Street) -> bool:
    """Whether the register wrote the city in front of the street."""
    return not written.lower().lstrip().startswith((street.type.lower(), street.name.lower().split()[0],
                                                     "ул", "пр", "пер", "б-р", "бул", "ш", "наб", "пл"))


BUILDERS = {
    "create_order": create_order,
    "check_status": check_status,
    "verify_identity": verify_identity,
    "refund": refund,
    "send_sms": send_sms,
    "second_mention": second_mention,
    "decompose": decompose,
}


def content_digest(case: Case) -> str:
    """A short digest of the user text, used by the generator to detect two
    draws that produced the same conversation."""
    text = "\n".join(m["content"] for m in case.messages if m["role"] == "user")
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
