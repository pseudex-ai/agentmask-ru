"""Generate the corpus. Deterministic from a seed, so a published number is
reproducible by anyone who has the seed and this file.

WHAT A CASE IS. One user message, a tool set that includes a tool whose arguments
are the personal data in that message, labelled spans for every datum, labelled
non-PII lookalikes, and the tool call a correct agent would make with the REAL
values in it. Scoring that call is how the round-trip axis exists at all.

WHY THE TEMPLATES DIFFER PER REGISTER RATHER THAN BEING POST-PROCESSED. Stripping
punctuation from a finished string changes its length and invalidates every span
already computed against it — the corpus still scores, and scores wrongly. So the
register is chosen first and the message is built once, in it.

    python3 bench/agentpii/build.py --out bench/agentpii/corpus.json --per 12
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.agentpii import registers as R  # noqa: E402
from bench.agentpii.schema import REGISTERS, Case, Negative, PiiItem, validate  # noqa: E402
from bench.agentpii.tools import tools_for  # noqa: E402


def _digits(rng: random.Random, count: int) -> str:
    return "".join(str(rng.randrange(10)) for _ in range(count))


# Identifiers in the corpus must be VALID, or the ground truth claims a document
# that is not one. Every serious Russian identifier is checksum-bearing, and a
# checksum-gated detector is right to reject a random digit string — scoring it
# as a miss would measure the corpus's carelessness, not the detector.
#
# The algorithms are published; these are the same ones the engine validates
# with, which is unavoidable and harmless: a checksum has one definition.

def _snils(rng: random.Random) -> str:
    body = _digits(rng, 9)
    total = sum(int(d) * (9 - i) for i, d in enumerate(body))
    if total in (100, 101):
        check = 0
    elif total > 101:
        total %= 101
        check = 0 if total in (100, 101) else total
    else:
        check = total
    return body + f"{check:02d}"


def _inn10(rng: random.Random) -> str:
    body = _digits(rng, 9)
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    check = sum(int(d) * w for d, w in zip(body, weights)) % 11 % 10
    return body + str(check)


def _card(rng: random.Random) -> str:
    body = "4" + _digits(rng, 14)
    total = 0
    for index, digit in enumerate(reversed(body)):
        value = int(digit)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return body + str((10 - total % 10) % 10)


def _phone_digits(rng: random.Random) -> str:
    return rng.choice(("916", "926", "903", "985", "917")) + _digits(rng, 7)


def _canonical_name(surface: str) -> str:
    """The canonical form of the name AS WRITTEN in this register — the surface.

    Registers drop parts (a messenger drops the patronymic, speech-to-text often
    drops the surname) and they never inflect: `render_name` writes nominative
    parts, reordered, lowercased or misspelt. So what was written IS the
    canonical form of what was written, and there is nothing to reconstruct.

    IT USED TO RECONSTRUCT, and that quietly broke the corpus's own rule. It
    matched each clean part against the surface by substring, so any part the
    register had TOUCHED disappeared from the ground truth: «Иванов Петр» — with
    е for ё, which is 53% of real Russian misspelling and a norm rather than a
    typo — demanded «Иванов» back and marked the full name wrong. 162 of the 183
    sloppy round-trip failures were this, not the gateway.

    The lesson is the one `assemble` already states one file over: derive from
    what you built, never by searching the finished string. Searching finds what
    survived the transform and calls the rest absent.

    NOT A CONCESSION TO THE DETECTOR. The gateway is not a spell-checker: a
    customer who wrote «Петр» is owed «Петр», and returning «Пётр» would be
    inventing a spelling the message did not carry. Demanding the repaired form
    was the corpus scoring us on information nobody supplied.
    """
    return surface


def _person(rng: random.Random, difficulty: str) -> tuple[str, str, str]:
    """Foreign names appear at every difficulty, not only the hard one.

    A shop's foreign customers are not an adversarial case — they are Tuesday.
    Hiding them in `adversarial` would let a summary number look healthy while
    the population it fails on is ordinary.
    """
    pool = R.MALE + R.FEMALE
    weight = 0.4 if difficulty == "adversarial" else 0.2
    if rng.random() < weight:
        pool = R.FOREIGN
    return rng.choice(pool)


def _order_id(rng: random.Random) -> str:
    return rng.choice(R.ORDER_PREFIXES) + _digits(rng, 4)


# --- scenario builders ----------------------------------------------------
#
# Each returns (parts, pii_specs, negatives, call_args). `parts` feeds
# `R.assemble`; a tuple in it is a tracked slot.

def _create_order(rng, register, difficulty):
    surname, first, patronymic = _person(rng, difficulty)
    name = R.render_name(surname, first, patronymic, register, rng)
    phone_digits = _phone_digits(rng)
    phone = R.render_phone(phone_digits, register, rng)
    city, street = rng.choice(R.CITIES), rng.choice(R.STREETS)
    house, flat = rng.randrange(1, 90), rng.randrange(1, 250)
    address = R.render_address(city, street, house, flat, register, rng)
    order = _order_id(rng)

    if register == "clean":
        parts = ["Оформите, пожалуйста, заказ ", order, " на ", ("name", name),
                 ", телефон ", ("phone", phone), ", адрес доставки: ",
                 ("address", address), "."]
    elif register == "chat":
        parts = ["оформите заказ ", order, " на ", ("name", name), " тел ",
                 ("phone", phone), " адрес ", ("address", address)]
    elif register == "sloppy":
        parts = ["заказ ", order, " оформите на ", ("name", name), ", т ",
                 ("phone", phone), ", ", ("address", address)]
    else:
        parts = ["так значит заказ ", order, " на ", ("name", name),
                 " телефон ", ("phone", phone), " адрес ", ("address", address)]

    # THE ADDRESS AS WRITTEN, for the same reason names are. Three of the four
    # registers drop the city — a shop's own chat assumes it — and ground truth
    # that names it anyway scores the gateway on a word the message never
    # carried. `render_address` decides what survived, so it is the only honest
    # source for what must come back.
    pii = [("name", "NAME", _canonical_name(name), "customer_name"),
           ("phone", "PHONE", f"+7{phone_digits}", "phone"),
           ("address", "LOC", address, "address")]
    negatives = [Negative(order, "номер заказа")]
    call = {"customer_name": f"{surname} {first} {patronymic}".strip(),
            "phone": f"+7{phone_digits}",
            "address": f"{city}, {street}, д. {house}, кв. {flat}"}
    return parts, pii, negatives, call


def _check_order_status(rng, register, difficulty):
    phone_digits = _phone_digits(rng)
    phone = R.render_phone(phone_digits, register, rng)
    order = _order_id(rng)
    track = _digits(rng, 14)

    if register == "clean":
        parts = ["Здравствуйте! Где мой заказ ", order, "? Трек-номер ", track,
                 ", телефон при оформлении ", ("phone", phone), "."]
    elif register == "chat":
        parts = ["привет где заказ ", order, " трек ", track, " телефон ",
                 ("phone", phone)]
    elif register == "sloppy":
        parts = ["где заказ ", order, "?? трек ", track, " тлф ", ("phone", phone)]
    else:
        parts = ["здравствуйте я хотел узнать про заказ ", order,
                 " трек номер ", track, " мой телефон ", ("phone", phone)]

    pii = [("phone", "PHONE", f"+7{phone_digits}", "phone")]
    # A 14-digit track sits right next to an 11-digit phone. This is the pair
    # that produced real false positives before the phone deny-gate existed.
    negatives = [Negative(order, "номер заказа"), Negative(track, "трек-номер")]
    return parts, pii, negatives, {"order_id": order, "phone": f"+7{phone_digits}"}


def _verify_identity(rng, register, difficulty):
    surname, first, patronymic = _person(rng, difficulty)
    name = R.render_name(surname, first, patronymic, register, rng)
    series, number = _digits(rng, 4), _digits(rng, 6)
    passport = R.render_passport(series, number, register)
    snils_digits = _snils(rng)
    snils = R.render_snils(snils_digits, register)
    build = _digits(rng, 6)

    if register == "clean":
        parts = ["Клиент ", ("name", name), ", паспорт ", ("passport", passport),
                 ", СНИЛС ", ("snils", snils), ". Версия анкеты ", build, "."]
    elif register == "chat":
        parts = ["клиент ", ("name", name), " паспорт ", ("passport", passport),
                 " снилс ", ("snils", snils), " анкета ", build]
    elif register == "sloppy":
        parts = [("name", name), " пасспорт ", ("passport", passport), " снилс ",
                 ("snils", snils), " сборка ", build]
    else:
        parts = ["клиент ", ("name", name), " паспорт ", ("passport", passport),
                 " снилс ", ("snils", snils), " версия анкеты ", build]

    pii = [("name", "NAME", _canonical_name(name), "full_name"),
           ("passport", "PASSPORT", f"{series} {number}", "passport"),
           ("snils", "SNILS", snils_digits, "snils")]
    negatives = [Negative(build, "номер сборки анкеты")]
    call = {"full_name": f"{surname} {first} {patronymic}".strip(),
            "passport": f"{series} {number}", "snils": snils_digits}
    return parts, pii, negatives, call


def _issue_refund(rng, register, difficulty):
    surname, first, patronymic = _person(rng, difficulty)
    name = R.render_name(surname, first, patronymic, register, rng)
    card_digits = _card(rng)
    card = R.render_card(card_digits, register)
    amount = rng.randrange(500, 40000)
    invoice = _digits(rng, 4)

    if register == "clean":
        parts = ["Верните ", str(amount), " рублей по счёту ", invoice,
                 " на карту ", ("card", card), ", держатель ", ("name", name), "."]
    elif register == "chat":
        parts = ["верните ", str(amount), " по счёту ", invoice, " на карту ",
                 ("card", card), " держатель ", ("name", name)]
    elif register == "sloppy":
        parts = ["возврат ", str(amount), "р счет ", invoice, " карта ",
                 ("card", card), " ", ("name", name)]
    else:
        parts = ["верните пожалуйста ", str(amount), " рублей по счёту ", invoice,
                 " на карту ", ("card", card), " держатель ", ("name", name)]

    pii = [("card", "CARD", card_digits, "card_number"),
           ("name", "NAME", _canonical_name(name), "customer_name")]
    negatives = [Negative(str(amount), "сумма"), Negative(invoice, "номер счёта")]
    call = {"card_number": card_digits, "amount": amount,
            "customer_name": f"{surname} {first} {patronymic}".strip()}
    return parts, pii, negatives, call


def _register_vehicle(rng, register, difficulty):
    surname, first, patronymic = _person(rng, difficulty)
    name = R.render_name(surname, first, patronymic, register, rng)
    letters = "АВЕКМНОРСТУХ"
    plate = (rng.choice(letters) + _digits(rng, 3)
             + "".join(rng.choice(letters) for _ in range(2)) + _digits(rng, 2))
    phone_digits = _phone_digits(rng)
    phone = R.render_phone(phone_digits, register, rng)
    doc_date = f"{rng.randrange(1, 28):02d}.{rng.randrange(1, 12):02d}.2025"

    if register == "clean":
        parts = ["Запишите на сервис автомобиль ", ("plate", plate),
                 ", владелец ", ("name", name), ", телефон ", ("phone", phone),
                 ". Заказ-наряд от ", doc_date, "."]
    elif register == "chat":
        parts = ["запишите машину ", ("plate", plate), " владелец ", ("name", name),
                 " тел ", ("phone", phone), " наряд от ", doc_date]
    elif register == "sloppy":
        parts = ["машина ", ("plate", plate), " ", ("name", name), " ",
                 ("phone", phone), " наряд от ", doc_date]
    else:
        parts = ["запишите машину ", ("plate", plate), " владелец ", ("name", name),
                 " телефон ", ("phone", phone), " заказ наряд от ", doc_date]

    pii = [("plate", "PLATE", plate, "plate"),
           ("name", "NAME", _canonical_name(name), "owner_name"),
           ("phone", "PHONE", f"+7{phone_digits}", "owner_phone")]
    # A document date beside personal data: the shape that made every invoice
    # date look like a date of birth until the association gate existed.
    negatives = [Negative(doc_date, "дата заказ-наряда, не дата рождения")]
    call = {"plate": plate, "owner_name": f"{surname} {first} {patronymic}".strip(),
            "owner_phone": f"+7{phone_digits}"}
    return parts, pii, negatives, call


def _send_invoice(rng, register, difficulty):
    inn = _inn10(rng)
    mailbox = rng.choice(("info", "buh", "office", "zakaz")) + _digits(rng, 2)
    domain = rng.choice(("acme.ru", "romashka.ru", "torgdom.ru"))
    email = f"{mailbox}@{domain}"
    amount = rng.randrange(5000, 900000)
    contract = _digits(rng, 4)

    if register == "clean":
        parts = ["Выставьте счёт по договору ", contract, " на сумму ", str(amount),
                 " рублей, ИНН ", ("inn", inn), ", почта ", ("email", email), "."]
    elif register == "chat":
        parts = ["счет по договору ", contract, " на ", str(amount), " инн ",
                 ("inn", inn), " почта ", ("email", email)]
    elif register == "sloppy":
        parts = ["выставите счет догвор ", contract, " ", str(amount), "р инн ",
                 ("inn", inn), " ", ("email", email)]
    else:
        parts = ["выставьте счёт по договору ", contract, " на сумму ", str(amount),
                 " рублей инн ", ("inn", inn), " почта ", ("email", email)]

    pii = [("inn", "INN", inn, "inn"), ("email", "EMAIL", email, "email")]
    negatives = [Negative(contract, "номер договора"), Negative(str(amount), "сумма")]
    return parts, pii, negatives, {"inn": inn, "email": email, "amount": amount}


BUILDERS = {
    "create_order": _create_order,
    "check_order_status": _check_order_status,
    "verify_identity": _verify_identity,
    "issue_refund": _issue_refund,
    "register_vehicle": _register_vehicle,
    "send_invoice": _send_invoice,
}


def build(per_combination: int, seed: int) -> list[Case]:
    rng = random.Random(seed)
    cases: list[Case] = []
    # Dialogues first, so a shortened run still contains them: they carry the
    # consistency axis, and that is the one nothing else in the corpus tests.
    for scenario, builder in DIALOGUES.items():
        for register in REGISTERS:
            for index in range(per_combination):
                messages, pii, negatives = builder(rng, register, "hard")
                cases.append(Case(
                    id=f"{scenario}-{register}-{index:03d}",
                    scenario=scenario, register=register, difficulty="hard",
                    messages=messages, tools=tools_for("create_order"),
                    pii=pii, negatives=negatives, expected_call=None))
    for scenario, builder in BUILDERS.items():
        for register in REGISTERS:
            for difficulty in ("easy", "hard", "adversarial"):
                for index in range(per_combination):
                    parts, pii_specs, negatives, call = builder(rng, register, difficulty)
                    text, spans = R.assemble(parts)
                    items = [
                        PiiItem(type=kind, value=text[spans[slot][0]:spans[slot][1]],
                                start=spans[slot][0], end=spans[slot][1],
                                canonical=canonical, tool_param=param)
                        for slot, kind, canonical, param in pii_specs
                    ]
                    cases.append(Case(
                        id=f"{scenario}-{register}-{difficulty}-{index:03d}",
                        scenario=scenario, register=register, difficulty=difficulty,
                        messages=[{"role": "user", "content": text}],
                        tools=tools_for(scenario), pii=items, negatives=negatives,
                        expected_call={"name": scenario, "arguments": call,
                                       "pii_params": [i.tool_param for i in items
                                                      if i.tool_param]}))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="bench/agentpii/corpus.json")
    parser.add_argument("--per", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260816)
    args = parser.parse_args()

    cases = build(args.per, args.seed)
    problems = [p for case in cases for p in validate(case)]
    if problems:
        print(f"КОРПУС НЕВАЛИДЕН — {len(problems)} проблем:")
        for problem in problems[:20]:
            print(f"  {problem}")
        return 1

    payload = {
        "name": "AgentPII-RU",
        "version": "0.1",
        "seed": args.seed,
        "cases": [case.to_json() for case in cases],
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    by_register: dict[str, int] = {}
    for case in cases:
        by_register[case.register] = by_register.get(case.register, 0) + 1
    print(f"собрано случаев: {len(cases)} -> {args.out}")
    print(f"размеченных ПД:  {sum(len(c.pii) for c in cases)}")
    print(f"негативов:       {sum(len(c.negatives) for c in cases)}")
    print(f"по регистрам:    {by_register}")
    return 0



# --- multi-turn: the consistency axis ------------------------------------
#
# Support is a CONVERSATION. The same customer is named in the first message and
# referred to again three turns later, often in a different form — «Иванов Пётр
# Сергеевич» then «Петру». The product's own claim is that both get the same
# substitute, and that a second, different person in the same message gets a
# different one. Nothing in the single-turn corpus could test either.

def _dialogue_same_person(rng, register, difficulty):
    """One person, named twice across turns, the second time in a short form."""
    surname, first, patronymic = _person(rng, difficulty)
    full = R.render_name(surname, first, patronymic, register, rng)
    phone_digits = _phone_digits(rng)
    phone = R.render_phone(phone_digits, register, rng)
    order = _order_id(rng)

    if register == "clean":
        first_parts = ["Оформите заказ ", order, " на ", ("name", full),
                       ", телефон ", ("phone", phone), "."]
        second_parts = ["И перезвоните ", ("again", first), " после шести, пожалуйста."]
    elif register == "chat":
        first_parts = ["оформите заказ ", order, " на ", ("name", full), " тел ",
                       ("phone", phone)]
        second_parts = ["и наберите ", ("again", first.lower()), " после шести"]
    elif register == "sloppy":
        first_parts = ["заказ ", order, " на ", ("name", full), ", т ", ("phone", phone)]
        second_parts = ["наберите ", ("again", first), " вечером"]
    else:
        first_parts = ["значит заказ ", order, " на ", ("name", full), " телефон ",
                       ("phone", phone)]
        second_parts = ["и позвоните ", ("again", first.lower()), " после шести"]

    turn_one, spans_one = R.assemble(first_parts)
    turn_two, spans_two = R.assemble(second_parts)
    messages = [
        {"role": "user", "content": turn_one},
        {"role": "assistant", "content": "Заказ принят. Что-то ещё?"},
        {"role": "user", "content": turn_two},
    ]
    canonical = _canonical_name(full)
    pii = [
        PiiItem("NAME", turn_one[slice(*spans_one["name"])], *spans_one["name"],
                canonical=canonical, tool_param="customer_name", turn=0, identity="p1"),
        PiiItem("PHONE", turn_one[slice(*spans_one["phone"])], *spans_one["phone"],
                canonical=f"+7{phone_digits}", tool_param="phone", turn=0, identity="p1phone"),
        PiiItem("NAME", turn_two[slice(*spans_two["again"])], *spans_two["again"],
                canonical=first, tool_param=None, turn=1, identity="p1"),
    ]
    return messages, pii, [Negative(order, "номер заказа")]


def _two_people(rng, register, difficulty):
    """Two DIFFERENT people in one message. They must not collapse into one."""
    a_surname, a_first, a_patr = _person(rng, difficulty)
    b_surname, b_first, b_patr = _person(rng, difficulty)
    while b_surname == a_surname:
        b_surname, b_first, b_patr = _person(rng, difficulty)
    payer = R.render_name(a_surname, a_first, a_patr, register, rng)
    recipient = R.render_name(b_surname, b_first, b_patr, register, rng)
    phone_digits = _phone_digits(rng)
    phone = R.render_phone(phone_digits, register, rng)

    if register == "clean":
        parts = ["Плательщик — ", ("payer", payer), ", а получатель ",
                 ("recipient", recipient), ", телефон получателя ", ("phone", phone), "."]
    elif register == "chat":
        parts = ["плачу я ", ("payer", payer), " а получит ", ("recipient", recipient),
                 " тел ", ("phone", phone)]
    elif register == "sloppy":
        parts = ["плательщик ", ("payer", payer), ", получатель ", ("recipient", recipient),
                 ", т ", ("phone", phone)]
    else:
        parts = ["плательщик ", ("payer", payer), " получатель ", ("recipient", recipient),
                 " телефон ", ("phone", phone)]

    text, spans = R.assemble(parts)
    messages = [{"role": "user", "content": text}]
    pii = [
        PiiItem("NAME", text[slice(*spans["payer"])], *spans["payer"],
                canonical=_canonical_name(payer),
                tool_param=None, turn=0, identity="payer"),
        PiiItem("NAME", text[slice(*spans["recipient"])], *spans["recipient"],
                canonical=_canonical_name(recipient),
                tool_param="customer_name", turn=0, identity="recipient"),
        PiiItem("PHONE", text[slice(*spans["phone"])], *spans["phone"],
                canonical=f"+7{phone_digits}", tool_param="phone", turn=0,
                identity="recipientphone"),
    ]
    return messages, pii, []


def _split_name_anchored(rng, register, difficulty):
    """One person named in PARTS THAT ARE NOT ADJACENT: «с Игорем, фамилия Волков».

    Every other scenario in this corpus names a person in one contiguous run, so
    the corpus could not produce this shape at all — it came from a persona
    running the real product, who noticed the two halves becoming two spans and
    asked whether «один человек — один токен» survives it.

    The full name arrives FIRST, which is what makes the claim testable. With an
    anchor in the vault the two later halves are unambiguously the same person,
    so linking them is required, not guessed. The unanchored shape is a separate
    scenario precisely because it is NOT required — see `_split_name_bare`.
    """
    surname, first, patronymic = _person(rng, difficulty)
    full = R.render_name(surname, first, patronymic, register, rng)
    dative = R.DATIVE.get(first, first)
    phone_digits = _phone_digits(rng)
    phone = R.render_phone(phone_digits, register, rng)
    order = _order_id(rng)

    if register == "clean":
        first_parts = ["Оформите заказ ", order, " на ", ("full", full),
                       ", телефон ", ("phone", phone), "."]
        second_parts = ["И свяжитесь с ", ("given", dative), ", фамилия ",
                        ("surname", surname), ", после шести."]
    elif register == "chat":
        first_parts = ["оформите заказ ", order, " на ", ("full", full), " тел ",
                       ("phone", phone)]
        second_parts = ["наберите ", ("given", dative.lower()), " фамилия ",
                        ("surname", surname.lower()), " вечером"]
    elif register == "sloppy":
        first_parts = ["заказ ", order, " на ", ("full", full), ", т ", ("phone", phone)]
        second_parts = ["наберите ", ("given", dative), ", фамилия ",
                        ("surname", surname), " вечром"]
    else:
        first_parts = ["значит заказ ", order, " на ", ("full", full), " телефон ",
                       ("phone", phone)]
        second_parts = ["и позвоните ", ("given", dative.lower()), " фамилия ",
                        ("surname", surname.lower()), " после шести"]

    turn_one, spans_one = R.assemble(first_parts)
    turn_two, spans_two = R.assemble(second_parts)
    messages = [
        {"role": "user", "content": turn_one},
        {"role": "assistant", "content": "Записал. Что-то ещё?"},
        {"role": "user", "content": turn_two},
    ]
    pii = [
        PiiItem("NAME", turn_one[slice(*spans_one["full"])], *spans_one["full"],
                canonical=_canonical_name(full),
                tool_param="customer_name", turn=0, identity="p1"),
        PiiItem("PHONE", turn_one[slice(*spans_one["phone"])], *spans_one["phone"],
                canonical=f"+7{phone_digits}", tool_param="phone", turn=0,
                identity="p1phone"),
        # BOTH HALVES FEED THE SAME ARGUMENT, and both are checked by the round
        # trip for it. The agent assembles one `customer_name` from them, so a
        # half that comes back as somebody else is a wrong tool call even when
        # the other half is perfect — and a lone surname is exactly where that
        # happened: «Иванова» resolved to «Иванов», a man.
        PiiItem("NAME", turn_two[slice(*spans_two["given"])], *spans_two["given"],
                canonical=first, tool_param="customer_name", turn=1, identity="p1"),
        PiiItem("NAME", turn_two[slice(*spans_two["surname"])], *spans_two["surname"],
                canonical=surname, tool_param="customer_name", turn=1, identity="p1"),
    ]
    return messages, pii, [Negative(order, "номер заказа")]


def _split_name_bare(rng, register, difficulty):
    """The split mention with NO earlier full name to anchor it.

    Deliberately carries NO identity: with nothing in the vault to tie the halves
    together, linking them would be a guess, and our own rule is that merging two
    people is worse than splitting one. Demanding a link here would score the
    gateway on information the conversation never carried.

    What it DOES demand is detection of both halves. A cued surname that arrives
    lower case («фамилия волков») is the shape the chat register actually
    carries, and a missed one is not a consistency defect — it is a leak.
    """
    surname, first, patronymic = _person(rng, difficulty)
    dative = R.DATIVE.get(first, first)
    phone_digits = _phone_digits(rng)
    phone = R.render_phone(phone_digits, register, rng)

    if register == "clean":
        parts = ["Свяжитесь с ", ("given", dative), ", фамилия ", ("surname", surname),
                 ", телефон ", ("phone", phone), "."]
    elif register == "chat":
        parts = ["наберите ", ("given", dative.lower()), " фамилия ",
                 ("surname", surname.lower()), " тел ", ("phone", phone)]
    elif register == "sloppy":
        parts = ["позвоните ", ("given", dative), " фамилия ", ("surname", surname),
                 ", т ", ("phone", phone)]
    else:
        parts = ["позвоните пожалуйста ", ("given", dative.lower()), " фамилия ",
                 ("surname", surname.lower()), " телефон ", ("phone", phone)]

    text, spans = R.assemble(parts)
    messages = [{"role": "user", "content": text}]
    pii = [
        PiiItem("NAME", text[slice(*spans["given"])], *spans["given"],
                canonical=first, tool_param="customer_name", turn=0, identity=""),
        PiiItem("NAME", text[slice(*spans["surname"])], *spans["surname"],
                canonical=surname, tool_param="customer_name", turn=0, identity=""),
        PiiItem("PHONE", text[slice(*spans["phone"])], *spans["phone"],
                canonical=f"+7{phone_digits}", tool_param="phone", turn=0, identity=""),
    ]
    return messages, pii, []


DIALOGUES = {
    "same_person_twice": _dialogue_same_person,
    "two_people": _two_people,
    "split_name_anchored": _split_name_anchored,
    "split_name_bare": _split_name_bare,
}

if __name__ == "__main__":
    sys.exit(main())
