"""Narrow adversarial reproducers for `_atomic_in_form_of` (current-hop form).

Independent of `test_other_hop_forms.py` / `test_phone_hop_form.py`: each check
states its expected OUTPUT literally, derived from `docs/tz-hop-form-adaptation.md`
§1 (content from the entity, form from the CURRENT sender) and from the ГОСТ
letter map itself — never from `_atomic_in_form_of`, `in_form_of` or
`render_like`. A mismatch is a RED to report, not a new expectation.

The substitutes are pinned (`_fake_*` / `_fake_date`) so the agent's text is
built from digits the vault really holds; every expectation then names the
customer's literal value from a different form, which is the whole contract.

Run from `prototype/`:
    PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_atomic_form_adversarial.py
"""

from __future__ import annotations

import json
from unittest.mock import patch

import testkit

from pseudex.detect import Span
from pseudex.redact import mask_text, unmask_arguments, unmask_text
from pseudex.vault import Vault

_PHONE_REAL = "8 916 214-88-03"
_PHONE_SHOWN = "+79795553322"
_CARD_REAL = "4276 1600 1234 5675"
_CARD_SHOWN = "0418 8633 8391 7819"

_ROWS: list[tuple[str, object, object]] = []


def _check(name: str, got: object, want: object) -> None:
    _ROWS.append((name, got, want))


def _vault(tag: str) -> Vault:
    return Vault(":memory:", tag).for_conversation("c1")


def _mask(text: str, value: str, entity: str, vault: Vault) -> str:
    start: int = text.index(value)
    span = Span(start, start + len(value), entity, value)
    return mask_text(text, vault, [span])[1:-1]


def _tool(written: str, vault: Vault) -> str:
    raw: str = json.dumps({"field": written}, ensure_ascii=False)
    restored: object = json.loads(unmask_arguments(raw, vault))
    if not isinstance(restored, dict) or not isinstance(restored.get("field"), str):
        raise AssertionError("tool restoration changed the JSON field type")
    return restored["field"]


def _prose(written: str, vault: Vault) -> str:
    return unmask_text(f"до {written} после", vault)


def _phone_vault() -> Vault:
    vault: Vault = _vault("acme-phone")
    with patch("pseudex.vault._fake_phone", return_value=_PHONE_SHOWN):
        shown: str = _mask("«" + _PHONE_REAL + "»", _PHONE_REAL, "PHONE", vault)
    if shown != "8 979 555-33-22":
        raise AssertionError(f"PHONE fixture did not mint in the user's form: {shown!r}")
    return vault


def _attack_homoglyph_inside_the_run() -> None:
    """A Cyrillic «О» the agent copied into a numeric run is part of the mention.

    `normalize` folds it for DETECTION, so the user's own typo crosses the mask
    path; the agent copies the substitute and keeps the look-alike. The digit
    signature is then built from the RAW run, the Cyrillic letter is not a
    digit, and the token is never asked for — the customer reads the substitute.
    """
    vault: Vault = _phone_vault()
    grouped: str = "8 (979) 555-33-22"
    _check("control: clean copied digits restore the real value",
           _tool(grouped, vault), "8 (916) 214-88-03")
    _check("control: prose control", _prose(grouped, vault), "до 8 (916) 214-88-03 после")
    # The look-alike truncates `_NUM_RUN` at index 14, so `_same_shape` never
    # reaches the final position: the value comes back as a HYBRID — the real
    # head «8 (916) 214-88» and the FAKE tail «О2». The mention must be the
    # customer's whole number with the typo the agent copied standing in it.
    typo: str = "8 (979) 555-33-О2"
    # Here O means ZERO, not the minted TWO. This is a different identity,
    # not a supported spelling of the fake. Do not invent its owner or turn
    # a recognisable prefix into a hybrid number.
    _check("tool: changed numeric value must not restore a real prefix",
           _tool(typo, vault), typo)
    _check("prose: changed numeric value must not restore a real prefix",
           _prose(typo, vault), f"до {typo} после")
    zero_vault: Vault = _vault("acme-zero")
    with patch("pseudex.vault._fake_phone", return_value="+79795553302"):
        _mask("«" + _PHONE_REAL + "»", _PHONE_REAL, "PHONE", zero_vault)
    _check("tool: O in place of a real zero is a known spelling",
           _tool(typo, zero_vault), "8 (916) 214-88-О3")
    _check("prose: O in place of a real zero is a known spelling",
           _prose(typo, zero_vault), "до 8 (916) 214-88-О3 после")


def _attack_bare_ten_digits() -> None:
    """Ten digits with no prefix are the agent's form, not a licence to invent «8»."""
    vault: Vault = _phone_vault()
    _check("an 11-digit mention keeps the agent's separators",
           _tool("8 979 555 33 22", vault), "8 916 214 88 03")
    _check("a 10-digit mention keeps its own (absent) prefix",
           _tool("9795553322", vault), "9162148803")


def _attack_card_forms() -> None:
    vault: Vault = _vault("acme-card")
    with patch("pseudex.vault._fake_card", return_value=_CARD_SHOWN):
        _mask("«" + _CARD_REAL + "»", _CARD_REAL, "CARD", vault)
    _check("card: agent keeps the grouped form", _tool(_CARD_SHOWN, vault), _CARD_REAL)
    _check("card: agent writes bare digits",
           _tool("0418863383917819", vault), "4276160012345675")
    _check("card: agent writes dashes",
           _tool("0418-8633-8391-7819", vault), "4276-1600-1234-5675")


_TO_LATIN = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")


def _attack_plate_alphabet() -> None:
    """The ГОСТ look-alike map mirrors the AGENT's script, letter by letter."""
    vault: Vault = _vault("acme-plates")
    fake: str = _mask("«А123ВС777»", "А123ВС777", "PLATE", vault)
    if len(fake) != 9 or not any(char.isdigit() for char in fake):
        raise AssertionError(f"PLATE mint is not a plate: {fake!r}")
    latin: str = fake.translate(_TO_LATIN)
    _check("plate: agent writes Latin", _tool(latin, vault), "A123BC777")
    _check("plate: agent writes lower Latin", _tool(latin.lower(), vault), "a123bc777")
    _check("plate: agent writes lower Cyrillic", _tool(fake.lower(), vault), "а123вс777")
    _check("plate: agent writes the minted form", _tool(fake, vault), "А123ВС777")


def _attack_date_padding() -> None:
    vault: Vault = _vault("acme-dob")
    with patch("pseudex.vault._fake_date", side_effect=lambda original: "11.07.1975"):
        _mask("«2 июня 1975»", "2 июня 1975", "DOB", vault)
    _check("date: ISO keeps the field order", _tool("1975-07-11", vault), "1975-06-02")
    _check("date: dotted keeps the field order, no invented padding",
           _tool("11.07.75", vault), "2.06.75")
    _check("date: prose keeps the word", _prose("11 июля 1975", vault), "до 2 июня 1975 после")
    _check("date: agent adds the year marker",
           _tool("11 июля 1975 года", vault), "2 июня 1975 года")
    _check("date: current uppercase month",
           _prose("11 ИЮЛЯ 1975", vault), "до 2 ИЮНЯ 1975 после")
    reused: Vault = _vault("acme-dob-reuse")
    with patch("pseudex.vault._fake_date", return_value="11.07.1975"):
        _mask("«02.06.1975»", "02.06.1975", "DOB", reused)
        second: str = _mask("«2.6.1975»", "2.6.1975", "DOB", reused)
    _check("date: later IN has its own zero-padding", second, "11.7.1975")


def _attack_email_case() -> None:
    vault: Vault = _vault("acme-mail")
    shown: str = _mask("«ivan.petrov@mail.ru»", "ivan.petrov@mail.ru", "EMAIL", vault)
    _check("email: agent upper-cases the shown substitute",
           _tool(shown.upper(), vault), "IVAN.PETROV@MAIL.RU")
    _check("email: agent returns the minted lower case",
           _tool(shown, vault), "ivan.petrov@mail.ru")
    mixed: str = shown.split("@")[0] + "@" + shown.split("@")[1].upper()
    _check("email: domain and local part have separate case",
           _tool(mixed, vault), "ivan.petrov@MAIL.RU")


def main() -> int:
    testkit.load_dev_bundle()
    _attack_homoglyph_inside_the_run()
    _attack_bare_ten_digits()
    _attack_card_forms()
    _attack_plate_alphabet()
    _attack_date_padding()
    _attack_email_case()
    bad: list[tuple[str, object, object]] = [row for row in _ROWS if row[1] != row[2]]
    for name, got, want in bad:
        print(f"RED {name}\n    got  {got!r}\n    want {want!r}")
    print(f"atomic_form_adversarial: {len(_ROWS) - len(bad)}/{len(_ROWS)} literal checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
