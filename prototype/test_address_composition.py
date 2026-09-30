#!/usr/bin/env python3
"""Class Б — the address COMPOSES (sprint pseudex; owner decision in DECISIONS-SPRINT.md).

    cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_address_composition.py

Self-contained: no model, no network, no leasing server — an explicit `Span`, a
real `Vault`, the real legs (`mask_text`, `unmask_text`, `unmask_arguments`,
`surviving_substitutes`) and the dev bundle loaded exactly as the other scripts
load it. Every contract below is written from a WITNESS in
`research/hop-format-audit/agents/`, never from what the engine happens to do.

The mass rule it pins (SPIKE-Б «подход как грамотно» + the owner's answer):

* THE STREET TYPE IS CONTENT, NOT POSITION. Presence and the word come from the
  record (the customer wrote «переулок» or wrote nothing); the marker's form,
  its position, the case and the letter-case belong to whoever is writing. One
  renderer serves both legs, so the type survives in prose, in a schema field
  and through a dotted path alike.
* THE TYPE IS ALSO PART OF THE IDENTITY — «переулок Пушкина» and «улица Пушкина»
  are two places and get two substitutes — while ONE place written with the type
  and without it is linked by a separate rule (the same settlement, street stem
  and numbers), which is what keeps A2 («переулок Мончегорская 10» /
  «Мончегорская 10») one street and one house.
* ONE REAL STREET IS ONE FAKE STREET, whatever the house: the reuse key is the
  street stem WITHOUT the house, and the house LITERA is part of the house's
  identity («34 в» is not «34»).
* A FRAGMENT RESOLVES AS A WHOLE OR IS REPORTED LOUDLY. A real street with a
  fake house is data corruption at 200 with an empty journal, and it is what
  g08/single-005 reported as «дом 22 остался подстановкой, residual {}».
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testkit  # noqa: E402

testkit.load_dev_bundle()          # the bundle first, everything else after it

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect import Span  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.redact import (mask_text, surviving_substitutes, unmask_arguments,  # noqa: E402
                            unmask_text)
from pseudex.vault import Vault  # noqa: E402

# The street-type vocabulary, written out here rather than asked of the engine: a
# test that reads its expectation out of the code under test cannot fail.
TYPE_WORDS = frozenset({
    "улица", "ул", "переулок", "пер", "проспект", "пр-т", "пр-кт", "просп", "пр",
    "бульвар", "б-р", "проезд", "площадь", "пл", "набережная", "наб", "шоссе", "ш",
    "тупик", "аллея", "линия", "квартал", "микрорайон", "мкр", "просека",
})
MARKERS = frozenset({"г", "гор", "город", "д", "дом", "кв", "корп", "стр",
                     "подъезд", "этаж", "офис"})
RESULTS: list[tuple[bool, str, str]] = []


def _check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'RED '}  {name}" + (f"   {detail}" if detail else ""))


def _vault(customer: str) -> Vault:
    return Vault(":memory:", customer).for_conversation("c1")


def _span(text: str, value: str, entity: str = "LOC") -> Span:
    start = text.index(value)
    return Span(start, start + len(value), entity, value)


def _show(text: str, value: str, vault: Vault, fake: str | None = None) -> str:
    """Mask one known span and return what the model was shown."""
    if fake is None:
        masked = mask_text(text, vault, [_span(text, value)])
    else:
        with patch("pseudex.vault._fake_place", return_value=fake):
            masked = mask_text(text, vault, [_span(text, value)])
    return masked.split(": ", 1)[1] if ": " in masked else masked


def _tool(written: object, vault: Vault) -> object:
    raw = json.dumps(written, ensure_ascii=False)
    return json.loads(unmask_arguments(raw, vault))


def _words(phrase: str) -> list[str]:
    return [word.strip(" .,").lower() for word in phrase.replace(",", " ").split()
            if word.strip(" .,")]


def _street_name(phrase: str) -> str:
    """The street's NAME — its type word and every marker taken out."""
    return " ".join(word for word in _words(phrase)
                    if word not in TYPE_WORDS and word not in MARKERS
                    and not word.isdigit())


def _street_type(phrase: str) -> str:
    return " ".join(word for word in _words(phrase) if word in TYPE_WORDS)


def _digits(phrase: str) -> list[str]:
    return [chunk for chunk in "".join(c if c.isdigit() else " " for c in phrase).split()]


# --------------------------------------------------------------------------- #
# Б-1 — the street TYPE survives in PROSE, in the agent's own position.
# Witness g02/m-074: the model wrote «Берёзовый переулок, 3», the customer read
# «Смольный, 7?» — « переулок» DELETED. The fake is pinned NAME-FIRST, exactly
# as the witness shows it, because that is the order `_fake_place` mints for
# «проспект» and «бульвар» and the order the old `_leading_generic` could not see.
# --------------------------------------------------------------------------- #
def b1_prose_type_from_the_record() -> None:
    real = "г Торжок, Светлый переулок, д 7, кв 112"
    fake = "г Торжок, Барбарисовый бульвар 3, кв 12"
    talk = _vault("b1")
    _show("адрес: " + real, real, talk, fake=fake)
    _check(unmask_text("Барбарисовый бульвар, 3", talk) == "Светлый переулок, 7",
           "Б-1 prose: the real type survives, in the agent's position",
           repr(unmask_text("Барбарисовый бульвар, 3", talk)))
    # THE CONTROL: a type word the agent put FIRST is his own notation and stays
    # his, abbreviation and all (measured: 25 addresses written «по полям»).
    talk = _vault("b1c")
    _show("адрес: " + real, real, talk, fake=fake)
    _check(unmask_text("бульвар Барбарисовый, 3", talk) == "бульвар Светлый, 7",
           "Б-1 CTRL: a LEADING marker is the agent's own and travels verbatim",
           repr(unmask_text("бульвар Барбарисовый, 3", talk)))
    _check(unmask_text("ул. Барбарисовый, 3", talk) == "ул. Светлый, 7",
           "Б-1 CTRL: his abbreviation, not ours",
           repr(unmask_text("ул. Барбарисовый, 3", talk)))


# --------------------------------------------------------------------------- #
# Б-2 — the ARGUMENT leg of the same defect, in the field the witness names.
# Witness g02/m-112: `courier_book.address.street` got «Светлый» for a record
# that says «Светлый переулок». The dotted path is the part of that witness the
# old reader could not even see (`field_role('address.street') == ('', '')`).
# --------------------------------------------------------------------------- #
def b2_argument_type_in_the_field() -> None:
    real = "г Торжок, Светлый переулок, д 7, кв 112"
    fake = "г Торжок, Барбарисовый бульвар 3, кв 12"
    for label, written in (
        ("nested", {"address": {"street": "Барбарисовый бульвар", "house": "3"}}),
        ("dotted", {"address.street": "Барбарисовый бульвар", "address.house": "3"}),
    ):
        talk = _vault("b2-" + label)
        _show("адрес: " + real, real, talk, fake=fake)
        got = _tool(written, talk)
        street = (got["address"]["street"] if label == "nested"
                  else got["address.street"])
        house = (got["address"]["house"] if label == "nested" else got["address.house"])
        _check((_street_name(street), _street_type(street), house) == ("светлый", "переулок", "7"),
               f"Б-2 tool ({label}): the field keeps the type and the real house",
               f"{street!r} / {house!r}")


# --------------------------------------------------------------------------- #
# Б-3 — TWO schema leaves name ONE street: the name in `street`, the type word in
# `street_type`. Witness g02/m-112 asks for exactly this pair, and the old reader
# gave BOTH leaves the whole street (`field_role('street_type') == ('street','street')`),
# so the customer's street travelled to the tool twice and the type was lost.
# --------------------------------------------------------------------------- #
def b3_two_leaves_one_street() -> None:
    real = "г Торжок, Светлый переулок, д 7, кв 112"
    fake = "г Торжок, Барбарисовый бульвар 3, кв 12"
    for label, written in (
        ("snake", {"address": {"street": "Барбарисовый", "street_type": "бульвар",
                               "house": "3"}}),
        ("camel", {"address": {"street": "Барбарисовый", "streetType": "бульвар",
                               "house": "3"}}),
    ):
        talk = _vault("b3-" + label)
        _show("адрес: " + real, real, talk, fake=fake)
        got = _tool(written, talk)["address"]
        kind = got.get("street_type") or got.get("streetType")
        _check(kind == "переулок",
               f"Б-3 tool ({label}): `street_type` holds the type word alone",
               repr(kind))
        _check((_street_name(str(got.get("street", ""))) + " " + str(kind)).strip()
               == "светлый переулок",
               f"Б-3 tool ({label}): the two leaves compose the real street ONCE",
               repr(f"{got.get('street')!r} + {kind!r}"))


# --------------------------------------------------------------------------- #
# Б-4 — ONE real street, houses 9 / 9а / 11: one fake street, only the numbers
# may differ. Witness g06/search_rank P3: four substitutes for one street
# («депутатская 9» -> «улица Ольховая 3», «… д 9а» -> «ул. Полевая 4»), because
# the reusable head was skipped exactly when its tolerant key matched — which is
# what the litera makes it do.
# --------------------------------------------------------------------------- #
def b4_one_street_one_fake_street() -> None:
    talk = _vault("b4")
    lines = ["г Брянск, ул Депутатская, д 9",
             "г Брянск, ул Депутатская, д 9а",
             "г Брянск, ул Депутатская, д 11"]
    text = "\n".join(lines)
    masked = mask_text(text, talk, [_span(text, line) for line in lines])
    names = {_street_name(line) for line in masked.split("\n")}
    houses = {line.split()[-1] for line in masked.split("\n")}
    _check(len(names) == 1 and "" not in names,
           "Б-4 one real street -> ONE fake street (houses 9 / 9а / 11)",
           f"streets={sorted(names)}")
    _check(len(houses) == 3,
           "Б-4 the three houses keep three numbers (no collapse onto one)",
           f"houses={sorted(houses)}")


# --------------------------------------------------------------------------- #
# Б-5 — TWO real houses («34 в» and «34») must never become ONE substitute.
# Witness g06 P4 / search_rank-008: «толстого 34 в» grew into the full
# «г Краснодар, ул Толстого, д 34», the courier went to 34 instead of 34в.
# The litera is a part of the house's identity, and it is written as a separate
# word half the time — «в/с/к/о» are prepositions AND literas.
# --------------------------------------------------------------------------- #
def b5_two_houses_two_substitutes() -> None:
    from pseudex.morph_places import address_key, street_house_key
    _check(address_key("толстого 34 в") != address_key("толстого 34"),
           "Б-5 identity: «34 в» and «34» are two different houses",
           f"{address_key('толстого 34 в')!r} vs {address_key('толстого 34')!r}")
    _check(address_key("толстого 34в") == address_key("толстого 34 в"),
           "Б-5 identity: the glued and the spaced litera are one house",
           f"{address_key('толстого 34в')!r}")
    _check(street_house_key("толстого 34 в") == street_house_key("толстого 34"),
           "Б-5 linking: the tolerant key still lets a short mention find the place",
           f"{street_house_key('толстого 34 в')!r}")
    talk = _vault("b5")
    a, b = "толстого 34 в", "г Краснодар, ул Толстого, д 34"
    text = f"заказ: {a}\nсклад: {b}"
    masked = mask_text(text, talk, [_span(text, a), _span(text, b)])
    fake_a = masked.split("заказ: ", 1)[1].split("\n", 1)[0]
    fake_b = masked.split("склад: ", 1)[1]
    _check(_digits(fake_a) != _digits(fake_b),
           "Б-5 two real houses -> two different fake houses",
           f"{fake_a!r} / {fake_b!r}")


# --------------------------------------------------------------------------- #
# Б-6 — WHOLE OR LOUD. Witness g08/single-005: «сортавала улица липовая 22»
# came back «сортавала улица вольная 22» — the street real, the HOUSE still a
# substitute, `residual {}`. Two halves: the whole resolves (the city of the
# record is REAL by design and must not be demanded of the fake), and a fake that
# nevertheless stays standing is NAMED in `residual_tokens`.
# --------------------------------------------------------------------------- #
def b6_whole_or_loud() -> None:
    talk = _vault("b6")
    real = "сортавала, улица вольная, 75, кв 82"
    shown = _show("мой адрес " + real, real, talk)
    written = shown.rsplit(",", 1)[0]                  # the flat is dropped
    got = _tool({"address": written}, talk)["address"]
    _check(_digits(got)[:1] == _digits(real)[:1],
           "Б-6 the tool gets the REAL house, never a real street with a fake house",
           f"{written!r} -> {got!r}")
    _check("кв" not in got.lower() and _digits(got) == _digits(real)[:1],
           "Б-6 the flat the agent did not name is not invented either",
           repr(got))
    _check(surviving_substitutes(written, got, talk, True) == [],
           "Б-6 a resolved address raises no alarm",
           repr(surviving_substitutes(written, got, talk, True)))

    # THE LOUD HALF, ON THE EXACT SHAPE THE DEFECT PRODUCED. The engine no longer
    # yields this state for the input above (the whole resolves), so the signal is
    # pinned on the state itself: the written fake with its STREET put back real
    # and its house left standing — the pre-fix output of g08/single-005. A
    # gateway that ever produces it again must name the leftover number rather
    # than hand a mixture to the tool with a 200 and an empty journal.
    from pseudex.morph_places import split_roles
    fake_street = split_roles(shown).get("street", "")
    real_street = split_roles(real).get("street", "")
    leftover = _digits(written)[-1]
    hybrid = written.replace(fake_street, real_street, 1)
    assert fake_street and hybrid != written, f"fixture: {shown!r}"
    _check(surviving_substitutes(written, hybrid, talk, True) == [leftover],
           "Б-6 a fake house left standing is NAMED in residual_tokens",
           f"{hybrid!r} -> {surviving_substitutes(written, hybrid, talk, True)!r}")
    # …and the honest counter-example: the street put back real AND the house
    # replaced by a number no substitute of ours carries — nothing of ours is
    # left, so nothing is reported. Without this half the diagnostic could call
    # the customer's own house a leftover and be believed.
    invented = written.replace(fake_street, real_street, 1).replace(leftover, "13", 1)
    _check(surviving_substitutes(written, invented, talk, True) == [],
           "Б-6 a number no substitute of ours carries is not a residual",
           repr(surviving_substitutes(written, invented, talk, True)))


# --------------------------------------------------------------------------- #
# Б-7 — THE OWNER'S DECISION, both halves.
#   * the type word is IDENTITY: «переулок Пушкина» and «улица Пушкина» are two
#     places, two rows, two substitutes — a CRM that cannot tell them apart
#     sends the courier to the wrong one;
#   * one place written WITH the type and WITHOUT it is ONE substitute, by a
#     separate linking rule (settlement + street stem + numbers) — the A2
#     acceptance, which is also pinned end to end in
#     `bench/agentpii5/test_loc_acceptance.py`.
# --------------------------------------------------------------------------- #
def b7_identity_and_linking() -> None:
    from pseudex.morph_places import address_key
    talk = _vault("b7")
    for line in ("адрес переулок Пушкина 5", "адрес улица Пушкина 5"):
        mask_text(line, talk, [_span(line, line.split(" ", 1)[1])])
    rows = talk._conn.execute(  # noqa: SLF001 — the row IS the identity under test
        "SELECT canonical FROM tokens WHERE entity_type='LOC' ORDER BY rowid").fetchall()
    canonicals = [row[0] for row in rows]
    _check(address_key("переулок Пушкина 5") != address_key("улица Пушкина 5"),
           "Б-7 identity: a переулок and an улица of one name are two keys",
           f"{canonicals!r}")
    _check(len(canonicals) == 2,
           "Б-7 identity: two types named -> TWO substitutes, not one",
           f"{canonicals!r}")

    talk = _vault("b7-link")
    typed = _show("адрес " + "г Уфа, переулок Мончегорская 10, кв. 54",
                  "г Уфа, переулок Мончегорская 10, кв. 54", talk)
    bare = _show("адрес г Уфа, Мончегорская 10, кв. 54",
                 "г Уфа, Мончегорская 10, кв. 54", talk)
    _check(_street_name(typed) == _street_name(bare),
           "Б-7 linking: with the type and without it -> ONE fake street (A2)",
           f"{typed!r} / {bare!r}")
    _check(_digits(typed) == _digits(bare),
           "Б-7 linking: and ONE fake house (A2)",
           f"{typed!r} / {bare!r}")


# --------------------------------------------------------------------------- #
# Б-8 — THE WHOLE ADDRESS IN A TOOL RESULT IS ONE VALUE, REUSED. The result the
# CRM returns re-writes the SAME place on a different surface — a capital street,
# a glued litera («34в»), a short flat marker («кв.») — and the production path
# used to lift the one fragment it recognised (the house) off the text and leave
# the street name and the flat RAW. The whole span must reuse its substitution,
# rendered in the result's own form, with the generic word kept (it is part of
# the substitute, not a redaction).
# --------------------------------------------------------------------------- #
def b8_whole_result_reuse() -> None:
    detector = Detector()
    vault = _vault("b8")
    ctx = MaskContext(detector=detector, vault=vault, audit=AuditLog(":memory:"),
                      cache=MaskCache(4096), org_id="x", agent_id="a",
                      conversation_id="c1")
    transcript: list[dict[str, object]] = []

    def push(message: dict[str, object]) -> dict[str, object]:
        transcript.append(dict(message))
        return mask_messages([dict(m) for m in transcript], ctx, False)[-1]

    user = push({"role": "user",
                 "content": "адрес: переулок лермонтова 34 в, квартира 9"})
    user_content = user.get("content")
    assert isinstance(user_content, str)
    fake_addr = user_content.split("адрес: ", 1)[1]

    push({"role": "assistant", "content": "",
          "tool_calls": [{"id": "t1", "type": "function",
                          "function": {"name": "crm_upsert_contact",
                                       "arguments": json.dumps(
                                           {"street_type": "переулок",
                                            "street": "лермонтова",
                                            "house": "34в", "flat": "9"},
                                           ensure_ascii=False)}}]})
    tool = json.dumps({"address": "переулок Лермонтова 34в, кв. 9"},
                      ensure_ascii=False)
    result = push({"role": "tool", "tool_call_id": "t1",
                   "name": "crm_upsert_contact", "content": tool})
    result_content = result.get("content")
    assert isinstance(result_content, str)
    got = json.loads(result_content)["address"]

    from pseudex.morph_places import split_roles
    _check(split_roles(got).get("street_name", "").casefold()
           == split_roles(fake_addr).get("street_name", "").casefold(),
           "Б-8 the result reuses the SAME fake street name",
           f"{got!r} vs {fake_addr!r}")
    _check(_digits(got) == _digits(fake_addr),
           "Б-8 the same fake house and flat (no leak of «34»/«9»)",
           f"{got!r} vs {fake_addr!r}")
    _check("лермонтова" not in got.casefold(),
           "Б-8 the real street name does not survive",
           repr(got))
    _check(_street_type(got) == "переулок" and "REDACTED" not in got,
           "Б-8 the generic word is part of the substitute, not a redaction",
           repr(got))
    # The result's own surface is authoritative: the street NAME is re-cased to
    # match «Лермонтова», while the generic word stays as the tool wrote it.
    name_word = next((word for word in got.split()
                      if word not in TYPE_WORDS and not word.isdigit()), "")
    _check(bool(name_word) and name_word[:1].isupper(),
           "Б-8 the street name is rendered in the result's case",
           repr(got))


# --------------------------------------------------------------------------- #
# CONTROLS — the instrument must be ABLE to pass. These are green on the same
# legs, the same vault and the same readers as the contracts above.
# --------------------------------------------------------------------------- #
def controls() -> None:
    talk = _vault("ctrl")
    real = "г Торжок, Светлый переулок, д 7, кв 112"
    fake = "г Торжок, Барбарисовый бульвар 3, кв 12"
    shown = _show("адрес: " + real, real, talk, fake=fake)
    _check(unmask_text(shown, talk) == real,
           "CTRL the whole fake copied verbatim comes back whole", repr(shown))
    _check(_tool({"address": shown}, talk)["address"] == real,
           "CTRL and through the argument leg", repr(shown))

    talk = _vault("ctrl2")
    lines = ["г Брянск, ул Депутатская, д 9", "г Брянск, ул Депутатская, д 11"]
    text = "\n".join(lines)
    masked = mask_text(text, talk, [_span(text, line) for line in lines])
    _check(len({_street_name(line) for line in masked.split("\n")}) == 1,
           "CTRL two houses WITHOUT a litera share one fake street",
           repr(masked))

    talk = _vault("ctrl3")
    # A record with NO type word: nobody adds one (the customer either wrote it
    # or did not), even when the agent copied our type-carrying fake verbatim.
    bare_real = "г Тверь, луговая 10, кв 3"
    bare_shown = _show("адрес: " + bare_real, bare_real, talk)
    got = unmask_text(bare_shown, talk)
    _check(_street_type(got) == "" and _street_name(got) == _street_name(bare_real),
           "CTRL the customer wrote no type word -> the tool gets none",
           f"{bare_shown!r} -> {got!r}")


def main() -> int:
    print("class Б — the address composes")
    b1_prose_type_from_the_record()
    b2_argument_type_in_the_field()
    b3_two_leaves_one_street()
    b4_one_street_one_fake_street()
    b5_two_houses_two_substitutes()
    b6_whole_or_loud()
    b7_identity_and_linking()
    b8_whole_result_reuse()
    controls()
    failed = [name for ok, name, _ in RESULTS if not ok]
    print()
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} contract checks passed")
    if failed:
        print("class Б NOT in place:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("class Б: type, keys, houses and the whole-or-loud rule all hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
