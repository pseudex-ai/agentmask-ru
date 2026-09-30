#!/usr/bin/env python3
"""Class Б — the street TYPE is identity in EVERY linking path.

    cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_type_identity_linking.py

`DECISIONS-SPRINT.md` §Б: «переулок Пушкина» ≠ «улица Пушкина» (две подмены).
The new paths (`_same_place_written_differently`, `_place_family_owner`) already
honour it; the old tolerant paths `_linked_place` and `_extends_linked_place`
keyed on `street_house_key` + `_house_identity`, both of which THROW AWAY the
generic word, so «переулок Пушкина 5» and «улица Пушкина 5» linked into ONE
substitute in both directions (REVIEW-SPRINT.md point 2).

Self-contained: the dev bundle, a real `Vault` and the real `mask_text` leg.

The mass rule: the type is compared by `_same_place_type` — a link is refused
only when BOTH writings name a type and they differ; a writing with no type
still links to a typed one («то же место, написано с типом и без» is the
separate linking rule, not two places).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from pseudex import morph_places  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import mask_text  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def _check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'RED '}  {name}" + (f"   {detail}" if detail else ""))


def _vault() -> Vault:
    return Vault(":memory:", "type").for_conversation("c1")


def _mask(text: str, vault: Vault) -> str:
    return mask_text(text, vault, Detector().detect(text))


def _street_of(masked: str) -> str:
    """The substitute's street NAME, not its house number or type word."""
    street = morph_places.split_roles(masked).get("street", "")
    words = [word for word in street.split()
             if word.casefold() not in morph_places._GENERIC]
    return " ".join(words)


def b1_short_then_short_different_type() -> None:
    # «переулок Пушкина 5» minted first, then «улица Пушкина 5»: the second is
    # a different place and must NOT reuse the first's substitute.
    vault = _vault()
    first = _mask("переулок Пушкина 5", vault)
    second = _mask("улица Пушкина 5", vault)
    _check(_street_of(first) != _street_of(second),
           "Б-1 «переулок Пушкина 5» and «улица Пушкина 5» are TWO substitutes",
           f"{first!r} vs {second!r}")


def b2_short_then_full_different_type() -> None:
    # A short typed mention, then the FULLER form with a different type: the
    # fuller must not grow from the short one (`_extends_linked_place`).
    vault = _vault()
    first = _mask("улица Пушкина 5", vault)
    second = _mask("г Москва, переулок Пушкина 5", vault)
    _check(_street_of(first) != _street_of(second),
           "Б-2 a fuller «переулок» never grows from a short «улица»",
           f"{first!r} vs {second!r}")


def b3_full_then_short_different_type() -> None:
    # The mirror: a full typed mention, then the SHORT form with a different
    # type: the short must not project from the full (`_linked_place`).
    vault = _vault()
    first = _mask("г Москва, переулок Пушкина 5", vault)
    second = _mask("улица Пушкина 5", vault)
    _check(_street_of(first) != _street_of(second),
           "Б-3 a short «улица» never projects from a full «переулок»",
           f"{first!r} vs {second!r}")


def b4_type_without_type_still_links() -> None:
    # «то же место, написано с типом и без» is the separate linking rule: a
    # writing with no type still links to a typed one — one place, one substitute.
    vault = _vault()
    first = _mask("переулок Пушкина 5", vault)
    second = _mask("Пушкина 5", vault)
    _check(_street_of(first) == _street_of(second),
           "Б-4 «Пушкина 5» (no type) still links to «переулок Пушкина 5»",
           f"{first!r} vs {second!r}")


def main() -> int:
    print("Class Б — the street type is identity in every linking path\n")
    b1_short_then_short_different_type()
    b2_short_then_full_different_type()
    b3_full_then_short_different_type()
    b4_type_without_type_still_links()
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
