#!/usr/bin/env python3
"""Class Д — a substitute's NUMBER survives the spelling, and a refusal is LOUD.

    cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_digit_truncation.py

`research/hop-format-audit/SPIKE-Д.md` (mechanism + approach Д-1…Д-4),
`DIAGNOSIS.md` class Д («резолвить только НОРМАЛИЗУЮЩЕЕ сокращение (разделители/
код/ведущая 7-8), позиционный срез канона запретить; подпись подмены однозначна
после снятия ведущих нулей … при отказе — остаток в `residual_tokens`, а не
молчание»), and the owner's answer in `DECISIONS-SPRINT.md` class Д:

    «Восстановить целиком: то же число (после снятия ведущих нулей) → настоящее
    значение ЦЕЛИКОМ. Контрольная сумма живёт над ЦИФРАМИ (значением), а не над
    форматом; „00“-префикс — часть значения, а не „способ записи“. Место/нотацию
    листа объявляет FieldSpec, не угадываем.»

Self-contained: no LLM, no network, no leasing server — an explicit `Span`, a
real `Vault`, the real legs (`mask_text`, `unmask_text`, `unmask_arguments`,
`surviving_substitutes`) and the dev bundle loaded the way every other script
loads it. The substitutes of the INN cases are PINNED to the witnesses, so the
expectation is the witness's own bytes and not whatever the engine's random mint
produced this run.

The mass rule, stated as a rule rather than as three cases:

  * Д-1  A digit run that is the SAME NUMBER as a substitute's digits, spelled
         with leading zeros dropped, resolves to the substitute's REAL VALUE IN
         FULL — never to a positional slice of it (`canon[2:12]`, the «10 of 12»
         of g03 `retry_same_tool-032/-048/-056`). This holds for EVERY type that
         mints an impossible prefix (ИНН region «00», card MII 0, passport
         «00YY»), because the rule is about the spelling of a NUMBER.
  * Д-2  The digit signature is unambiguous only after the leading zeros are
         dropped: two substitutes sharing that signature are a REFUSAL, not a
         choice — and the run is then NAMED, not swallowed.
  * Д-3  The positional slice of the canon survives ONLY where the removed part
         is a DIFFERENT number (passport series / number, the last four digits):
         that is the one shape whose place the text itself names. A run equal to
         the substitute as a NUMBER is never sliced.
  * Д-4  A refusal is loud. A run that is our substitute's number misspelled —
         leading zeros dropped, or ONE digit rewritten (g12 `long_clinic-005`:
         `+79693604666` for the minted `+79693604066`; g08 `single-039`: the
         model's own reading of a dictated phrase, one digit from ours) — is
         reported in the residual instead of reaching the tool at 200 with an
         empty journal. It is REPORTED, never resolved: fuzzy numeric resolution
         is forbidden here (`spoken.py`), and the ordering is the repository's
         own (`vault.with_spent_signatures`): «порча данных хуже молчаливой
         потери, молчаливая потеря хуже названной, названная хуже ложной
         тревоги».
  * THE NEGATIVES ARE THE HALF THAT KEEPS THE RULE HONEST. A customer's own
         number, a bare quantity, and a run TWO edits away from a substitute must
         neither resolve nor be reported — a rule that names everything it does
         not know is a rule nobody can act on.
"""

from __future__ import annotations

import json
import os
import re
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testkit  # noqa: E402

testkit.load_dev_bundle()          # the bundle first, everything else after it

from pseudex.detect import Span  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import (mask_text, surviving_substitutes,  # noqa: E402
                            unmask_arguments, unmask_text)
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def _check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'RED '}  {name}" + (f"   {detail}" if detail else ""))


def _vault(customer: str) -> Vault:
    return Vault(":memory:", customer).for_conversation("c1")


def _span(text: str, value: str, entity: str) -> Span:
    at = text.index(value)
    return Span(at, at + len(value), entity, value)


def _digits(value: object) -> str:
    return re.sub(r"\D", "", str(value))


def _mask(text: str, value: str, entity: str, vault: Vault,
          fake: str | None = None) -> str:
    """Mask one known span, pinning the substitute when the mint allows it."""
    target = {"INN": "pseudex.vault._fake_inn",
              "CARD": "pseudex.vault._fake_card",
              "PHONE": "pseudex.vault._fake_phone"}.get(entity)
    if fake is not None and target is not None:
        with patch(target, return_value=fake):
            return mask_text(text, vault, [_span(text, value, entity)])
    return mask_text(text, vault, [_span(text, value, entity)])


def _tool(payload: dict[str, object], vault: Vault) -> dict[str, object]:
    raw = json.dumps(payload, ensure_ascii=False)
    return json.loads(unmask_arguments(raw, vault))


def _residual(written: dict[str, object], got: dict[str, object], vault: Vault) -> list[str]:
    return surviving_substitutes(json.dumps(written, ensure_ascii=False),
                                 json.dumps(got, ensure_ascii=False), vault, True)


# --------------------------------------------------------------------------- #
# Д-1 — THE NUMBER, NOT THE POSITION. Witnesses g03 `retry_same_tool`:
# `-048` fake `008499949700` → the model wrote `8499949700` → the tool received
# `0068146509` = `390068146509[2:12]`; `-032` `007119594040` → `7119594040` →
# `7168695320` of `877168695320`; `-056` `002247959636` → `2247959636` →
# `9231993306` of `439231993306`. All three: real digits, silently truncated.
# --------------------------------------------------------------------------- #
def d1_the_number_is_not_a_position() -> None:
    for entity, real, fake, written in (
        ("INN", "390068146509", "008499949700", "8499949700"),   # g03/-048
        ("INN", "877168695320", "007119594040", "7119594040"),   # g03/-032
        ("INN", "439231993306", "002247959636", "2247959636"),   # g03/-056
    ):
        vault = _vault("d1")
        masked = _mask(f"проверьте клиента по инн {real}", real, entity, vault, fake=fake)
        _check(fake in masked, f"Д-1 fixture: the substitute is {fake}", repr(masked))
        got = _tool({"inn": written}, vault)["inn"]
        _check(_digits(got) == real,
               f"Д-1 the tool gets the WHOLE {real} for the agent's {written}",
               repr(got))
        _check(_digits(got)[:2] != "00" and _digits(got) != real[2:],
               "Д-1 …and never the positional slice canon[2:12] the class produced",
               repr(got))
        _check(_residual({"inn": written}, {"inn": got}, vault) == [],
               "Д-1 a spelling that RESOLVED raises no alarm",
               repr(_residual({"inn": written}, {"inn": got}, vault)))

    # ONE ZERO OF TWO REMOVED IS STILL THE SAME NUMBER («то же число после снятия
    # ведущих нулей»): the count of stripped zeros is not what makes the identity.
    vault = _vault("d1b")
    masked = _mask("инн 390068146509", "390068146509", "INN", vault, fake="008499949700")
    _check("008499949700" in masked, "Д-1 fixture (one zero kept)", repr(masked))
    got = _tool({"inn": "08499949700"}, vault)["inn"]
    _check(_digits(got) == "390068146509",
           "Д-1 removing ONE of the two leading zeros is the same number",
           repr(got))

    # THE PROSE LEG IS THE SAME RULE: the fake written without its zeros in an
    # answer to the customer is the same fake.
    vault = _vault("d1c")
    _mask("проверьте клиента по инн 390068146509", "390068146509", "INN", vault,
          fake="008499949700")
    _check(_digits(unmask_text("инн 8499949700", vault)) == "390068146509",
           "Д-1 the prose leg resolves the same number to the whole value",
           repr(unmask_text("инн 8499949700", vault)))

    # AND UNDER THE CALL-LEVEL ANCHOR, BEYOND THE CONVERSATION. Where the
    # substitute was minted in another dialogue, the answer is licensed by the
    # numbers of THIS call covering its digits in full (`_digit_fragments_tiled`)
    # — and under that anchor the hole answers WHOLE too: the slice `canon[2:12]`
    # is the same corruption whether or not a call anchored it.
    store = Vault(":memory:", "d1d")
    _mask("инн 390068146509", "390068146509", "INN", store.for_conversation("c1"),
          fake="008499949700")
    anchored = store.for_conversation("c2").with_written_digits(("00", "8499949700"))
    owner = anchored.digit_fragment_owner("8499949700")
    _check(owner is not None and _digits(owner[0]) == "390068146509",
           "Д-1 under the call's own tiling the hole answers the WHOLE value",
           repr(owner))


# --------------------------------------------------------------------------- #
# Д-1 — EVERY TYPE WITH AN IMPOSSIBLE PREFIX. The class is not about ИНН: the
# moment the agent's run is the substitute's NUMBER written another way, the
# positional answer hands out a fragment of the real person's data.
# --------------------------------------------------------------------------- #
def d2_any_type_with_an_impossible_prefix() -> None:
    # CARD — MII 0, 16 digits; the witness form was `0110183024186984` → 15 of 16.
    vault = _vault("d2card")
    masked = _mask("карта 2200666689026161", "2200666689026161", "CARD", vault,
                   fake="0110183024186984")
    _check("0110183024186984" in masked, "Д-1 card fixture", repr(masked))
    got = _tool({"card": "110183024186984"}, vault)["card"]
    _check(_digits(got) == "2200666689026161",
           "Д-1 CARD: the tool gets the whole 16-digit value, not 15 of 16",
           repr(got))

    # PASSPORT — series «00YY»; the same class as «00» region, and the witness
    # run gave the tool `08246256` = `4608246256[2:10]` (8 of 10).
    vault = _vault("d2pass")
    masked = _mask("паспорт 4608 246256", "4608 246256", "PASSPORT", vault)
    fake = masked.split("паспорт ", 1)[1]
    fake_digits = _digits(fake)
    _check(fake_digits.startswith("00") and len(fake_digits) == 10,
           "Д-1 passport fixture: the mint carries the impossible series «00»",
           f"{fake!r} → {fake_digits}")
    written = fake_digits.lstrip("0")
    got = _tool({"passport": written}, vault)["passport"]
    _check(_digits(got) == "4608246256",
           "Д-1 PASSPORT: the whole value, not the 8-of-10 slice",
           f"{written!r} -> {got!r}")


# --------------------------------------------------------------------------- #
# Д-2 — THE SIGNATURE IS UNAMBIGUOUS ONLY AFTER THE ZEROS ARE DROPPED. Two
# substitutes of one customer that are the SAME NUMBER are two identities, and
# the number is refused rather than answered with one of them. The refusal is
# NAMED: the ordering above says a named refusal beats a silent corruption.
# --------------------------------------------------------------------------- #
def d3_ambiguity_refuses_and_is_named() -> None:
    vault = _vault("d3")
    # An ИНН substitute whose number, stripped of its zeros, is `8499949700`,
    # and a СНИЛС substitute that carries the SAME NUMBER in one digit less —
    # `08499949700`. Two rows of ONE customer, one number, two identities: the
    # exact-spelling door misses both (neither `digits` column holds the run),
    # and the answer may not be an arbitrary one of the two.
    text = "инн 390068146509 и снилс 112-233-445 95"
    with patch("pseudex.vault._fake_inn", return_value="008499949700"), \
            patch("pseudex.vault._fake_snils", return_value="084-999-497 00"):
        masked = mask_text(text, vault, [_span(text, "390068146509", "INN"),
                                         _span(text, "112-233-445 95", "SNILS")])
    _check("008499949700" in masked and "084-999-497 00" in masked,
           "Д-2 fixture: two substitutes, one NUMBER, two spellings", repr(masked))
    written = {"inn": "8499949700"}
    got = _tool(written, vault)
    _check(_digits(got["inn"]) == "8499949700",
           "Д-2 an ambiguous signature is REFUSED, not answered with one identity",
           repr(got))
    residual = _residual(written, got, vault)
    _check(any(_digits(item) == "8499949700" for item in residual),
           "Д-2 …and the refusal is NAMED in the residual, not silent",
           repr(residual))

    # The control: with ONE substitute holding that number the same run resolves
    # whole — the refusal above is about the duplicate, not about the spelling.
    vault = _vault("d3b")
    _mask("инн 390068146509", "390068146509", "INN", vault, fake="008499949700")
    got = _tool({"inn": "8499949700"}, vault)
    _check(_digits(got["inn"]) == "390068146509",
           "Д-2 control: the same run with ONE owner resolves whole", repr(got))


# --------------------------------------------------------------------------- #
# Д-4 — A REFUSAL IS LOUD. Witnesses: g12 `long_clinic-005` («+79693604666» for
# the minted «89693604066», `residual {}`), g12 `long_clinic-043`
# («+79007626578» for «79076265782»), g08 `single-039` (the model's own reading
# of a dictated phrase, one digit from the engine's — engine `89357053610`,
# model `89357553610`). None of these is OUR substitute and none is the real
# value: the fake reached the tool at 200 with an empty journal. They are not
# resolved — numeral fuzz is forbidden — they are NAMED.
# --------------------------------------------------------------------------- #
def d4_a_one_digit_rewrite_is_named() -> None:
    vault = _vault("d4phone")
    fake = "+79693604066"
    masked = _mask("телефон +79031234567", "+79031234567", "PHONE", vault, fake=fake)
    _check("79693604066" in _digits(masked), "Д-4 fixture: the phone substitute", repr(masked))
    written = {"phone": "+79693604666"}       # one digit from the substitute
    got = _tool(written, vault)
    _check(_digits(got["phone"]) == "79693604666",
           "Д-4 a one-digit rewrite is NOT resolved (numeric fuzz is forbidden)",
           repr(got))
    residual = _residual(written, got, vault)
    _check(any(_digits(item) == "79693604666" for item in residual),
           "Д-4 …and it is NAMED in the residual (g12 long_clinic-005)",
           repr(residual))

    vault = _vault("d4inn")
    _mask("инн 390068146509", "390068146509", "INN", vault, fake="008499949700")
    written = {"inn": "008499949710"}         # one digit from the substitute, same length
    got = _tool(written, vault)
    _check(_digits(got["inn"]) == "008499949710",
           "Д-4 an equal-length one-digit rewrite is not resolved either", repr(got))
    residual = _residual(written, got, vault)
    _check(any(_digits(item) == "008499949710" for item in residual),
           "Д-4 …and it is NAMED too, whatever the type", repr(residual))

    # TWO edits away is not «almost our substitute», and a rule that cannot tell
    # one edit from two would name half of the customer's own numbers.
    written = {"inn": "008499949711"}
    got = _tool(written, vault)
    residual = _residual(written, got, vault)
    _check(not any(_digits(item) == "008499949711" for item in residual),
           "Д-4 two digits away from our substitute is NOT ours",
           repr(residual))


# --------------------------------------------------------------------------- #
# Д-3 — THE POSITIONAL SLICE SURVIVES WHERE THE PLACE IS NAMED AND THE NUMBER IS
# DIFFERENT. Passport series and number, and the last four digits of a card, are
# the shapes the cue/schema names; they were green before and must stay green.
# Without this half, Д-1 could «fix» the class by refusing every fragment.
# --------------------------------------------------------------------------- #
def d5_named_places_still_slice() -> None:
    vault = _vault("d5")
    masked = _mask("паспорт 4608 246256", "4608 246256", "PASSPORT", vault)
    fake = _digits(masked.split("паспорт ", 1)[1])
    series, number = fake[:4], fake[4:10]
    got = _tool({"series": series, "number": number}, vault)
    _check(_digits(got["series"]) == "4608" and _digits(got["number"]) == "246256",
           "Д-3 the passport's two named fields still get their own places",
           f"{series!r}/{number!r} -> {got['series']!r}/{got['number']!r}")

    vault = _vault("d5b")
    _mask("карта 2200666689026161", "2200666689026161", "CARD", vault,
          fake="0110183024186984")
    got = _tool({"last4": "6984"}, vault)
    _check(_digits(got["last4"]) == "6161",
           "Д-3 the last four digits of the card are still the last four",
           repr(got))


# --------------------------------------------------------------------------- #
# NEGATIVES — what the rule must NOT touch. A customer's own number, a quantity,
# and another dialogue's substitute: none of them is resolved, and none of them
# is reported, because nothing of ours is in the text.
# --------------------------------------------------------------------------- #
def d6_negatives() -> None:
    vault = _vault("d6")
    _mask("инн 390068146509", "390068146509", "INN", vault, fake="008499949700")
    written = {"inn": "390068146510"}         # the customer's own number
    got = _tool(written, vault)
    _check(_digits(got["inn"]) == "390068146510",
           "Д-6 a number that is nobody's substitute is left alone", repr(got))
    _check(_residual(written, got, vault) == [],
           "Д-6 …and is not reported as a leftover", repr(_residual(written, got, vault)))

    written = {"quantity": "123456"}
    got = _tool(written, vault)
    _check(_digits(got["quantity"]) == "123456" and _residual(written, got, vault) == [],
           "Д-6 a bare quantity is neither resolved nor reported",
           f"{got!r} {_residual(written, got, vault)!r}")

    # ANOTHER DIALOGUE IS NOT THIS DIALOGUE'S SUBSTITUTE. The value must not come
    # back (that is the conversation scope), and because the fake IS still
    # standing a signal is the right answer, not silence. THE STORE IS THE SAME
    # ONE, only the conversation differs — a fresh store would prove nothing,
    # because the row would not exist to be leaked. This is the shape the
    # whole-customer fallback (`_digit_fragments_tiled`) must not answer through:
    # the number is the same, and the conversation is the only thing that says
    # whose it is.
    store = Vault(":memory:", "d6")
    talk_a = store.for_conversation("c1")
    talk_b = store.for_conversation("c2")
    _mask("инн 390068146509", "390068146509", "INN", talk_a, fake="008499949700")
    written = {"inn": "8499949700"}
    got = _tool(written, talk_b)
    _check(_digits(got["inn"]) != "390068146509",
           "Д-6 another CONVERSATION of the same store never receives the value",
           repr(got))
    _check(_digits(got["inn"]) != "0068146509",
           "Д-6 …and not a slice of it either", repr(got))
    _check(any(_digits(item) == "8499949700"
               for item in _residual(written, got, talk_b)),
           "Д-6 …the standing fake is NAMED instead (the refusal is loud)",
           repr(_residual(written, got, talk_b)))

    # THE CONSEQUENCE THE CLASS RESTS ON: the WHOLE real ИНН is a checksum-valid
    # identifier the detector recognises on the echo leg, while the 10-digit
    # slice it used to receive is not recognised by anything — which is why the
    # truncation was a LEAK and not only a corruption.
    det = Detector()
    real = "390068146509"
    whole = det.detect(f"inn_checksum: {real}")
    slice_ = det.detect(f"inn_checksum: {real[2:]}")
    _check(any(span.entity_type == "INN" for span in whole),
           "Д-6 the whole real ИНН is detectable on the echo leg",
           repr([(s.entity_type, s.value) for s in whole]))
    _check(not slice_,
           "Д-6 the positional slice was undetectable — the leak the class is",
           repr([(s.entity_type, s.value) for s in slice_]))


def main() -> int:
    print("Class Д — silent digit truncation: the NUMBER, not the position\n")
    d1_the_number_is_not_a_position()
    d2_any_type_with_an_impossible_prefix()
    d3_ambiguity_refuses_and_is_named()
    d4_a_one_digit_rewrite_is_named()
    d5_named_places_still_slice()
    d6_negatives()
    red = [name for ok, name, _detail in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(red)}/{len(RESULTS)} checks PASS")
    if red:
        print("RED — the class is not closed:")
        for name in red:
            print(f"  ✗ {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
