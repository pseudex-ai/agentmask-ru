"""One real value → one substitute across every context that can carry it.

    cd prototype && source .venv/bin/activate && \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_mint_consistency

The NAME disease (fixed in `5ebc4b2`): one real value canonicalized under
DIFFERENT keys in different contexts is minted TWICE and receives DIFFERENT
substitutes, so the model reads one fake in the call and another in the result
and the parity gate (`bench/agentpii4/gateway.py::_push`) refuses the triple.
The fix made the grown NAME reuse the parts already minted in the conversation.

This file pins the types that STILL carry the disease, as RED tests. Each check
asserts "one token for one value" (or "one surname for one person") and FAILS
today. It drives the vault directly — a fresh vault per check, no model, no
network — so it is a property of canonicalization + minting, not of detection or
the judge. Do not fix the code here; these are the reproductions the fix must
turn green.

Healthy types are deliberately NOT asserted here (they would only mask the RED):
PHONE, SNILS/INN/CARD/PASSPORT, DOB/DATE and EMAIL already collapse every
equivalent writing to one key (verified in the audit that produced this file).
"""

import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from testkit import load_dev_bundle  # noqa: E402
from pseudex.vault import Vault  # noqa: E402


def _vault() -> Vault:
    d = tempfile.mkdtemp()
    return Vault(os.path.join(d, "v.db"), "mint-consistency")


def _check_loc_street_type_word_city_less() -> str | None:
    """«переулок Мончегорская 10» and «Мончегорская 10» are ONE street.

    The type word is metadata the customer may write or omit; the identity is
    the street stem + house, which is exactly what `street_house_key` keeps and
    `address_key` does NOT: it preserves the type word when present and adds
    nothing when absent, so the two writings key apart. `_same_place_written_
    differently` would link them, but only for a CITY-BEARING address — a
    city-less one has no owner in `place_parts` (`_linked_place` links only
    `has_city=1` rows), so within ONE conversation the same street gets two
    substitutes. The parity gate reads the call leg's fake and the result leg's
    fake and sees two streets.
    """
    v = _vault().for_conversation("c-city-less")
    with_type = v.tokenize("переулок Мончегорская 10", "LOC")
    without_type = v.tokenize("Мончегорская 10", "LOC")
    if with_type != without_type:
        return (f"city-less street with/without type word minted two substitutes: "
                f"{with_type!r} vs {without_type!r}")
    return None


def _check_loc_street_type_word_city_bearing() -> str | None:
    """A FULL address is documented «one place, one substitute, for ever and
    across conversations» (`_tokenize_unrecorded`). The full canonical
    (`address_key`) keeps the street-type word, so «г. Уфа, переулок
    Мончегорская 10, кв. 54» and the same address without «переулок» are two
    rows. The conversation-scoped link that would merge them cannot fire here
    (no conversation), and it would not fire across conversations either — so
    one place, written with or without the type word, mints two substitutes for
    ever. Assert one token.
    """
    v = _vault()  # no conversation: the cross-conversation / forever contract
    with_type = v.tokenize("г. Уфа, переулок Мончегорская 10, кв. 54", "LOC")
    without_type = v.tokenize("г. Уфа, Мончегорская 10, кв. 54", "LOC")
    if with_type != without_type:
        return (f"full address with/without type word minted two substitutes: "
                f"{with_type!r} vs {without_type!r}")
    return None


def _check_name_initials_reuse() -> str | None:
    """«Ващенко Таисия Савельевна» and «Ващенко Т. С.» are ONE person.

    The full name and its initial form key apart («ващенко таисия савельевна»
    vs «ващенко т. с.») and nothing links them — `_extends_known_person` reuses
    parts only for a name that GROWS word-by-word, not for an abbreviation. So
    the same person gets two surnames (and the initial form even guesses a
    gender the hidden given name would fix). The model reads one surname in the
    call and another in the result. Assert the initial form reuses the full
    name's surname (the minimal invariant; the initials should also be the
    given/patronymic initials of the full substitute).
    """
    v = _vault().for_conversation("c-initials")
    full = v.tokenize("Ващенко Таисия Савельевна", "NAME")
    initials = v.tokenize("Ващенко Т. С.", "NAME")
    full_surname = full.split()[0].casefold() if full.split() else ""
    initials_surname = initials.split()[0].casefold() if initials.split() else ""
    if full_surname != initials_surname:
        return (f"full name {full!r} and initials {initials!r} share no surname "
                f"({full_surname!r} vs {initials_surname!r})")
    return None


def _check_plate_separator() -> str | None:
    """«А123ВС777» and «А 123 ВС 777» are ONE registration plate.

    CARD/SNILS/INN/PASSPORT collapse every grouping through `_digits_of`; PLATE
    is not in `_NUMERIC_TYPES` and `canonicalize` only uppercases + maps Latin to
    Cyrillic, so the separator survives into the key. The detector emits the
    spaced form (`detect_vehicle_ids`), so the same car, written with and
    without group spaces, mints two tokens. Assert one token.
    """
    v = _vault()
    tight = v.tokenize("А123ВС777", "PLATE")
    spaced = v.tokenize("А 123 ВС 777", "PLATE")
    if tight != spaced:
        return f"plate tight {tight!r} vs spaced {spaced!r} minted two tokens"
    return None


_CHECKS = (
    ("loc_street_type_word_city_less", _check_loc_street_type_word_city_less),
    ("loc_street_type_word_city_bearing", _check_loc_street_type_word_city_bearing),
    ("name_initials_reuse", _check_name_initials_reuse),
    ("plate_separator", _check_plate_separator),
)


def main() -> int:
    load_dev_bundle()
    failures: list[tuple[str, str]] = []
    for name, check in _CHECKS:
        failure = check()
        if failure:
            failures.append((name, failure))
    for name, failure in failures:
        print(f"FAIL {name}: {failure}")
    if failures:
        print(f"mint_consistency: {len(failures)} RED ({len(_CHECKS) - len(failures)} green)")
        return 1
    print("mint_consistency: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
