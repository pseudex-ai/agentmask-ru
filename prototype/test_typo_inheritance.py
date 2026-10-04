#!/usr/bin/env python3
"""Class А — a substitute inherits the customer's TYPO, not just the name.

    cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_typo_inheritance.py

`DECISIONS-SPRINT.md` §А and the owner's literal example: «меня зовут игрь» →
the substitute carries the SAME typo («егрь» instead of «егор»), so the agent's
clarifying question does not change. REVIEW-SPRINT.md point 1 named two gaps:
(a) the single damaged name «игрь» was not detected at all (`_damaged_name_pairs`
requires a pair), and (b) the mint took a clean dictionary name («игрь павлов» →
«георгий мухин») and silently dropped the typo.

Self-contained: no LLM, no network — the dev bundle, a real `Detector` and a real
`Vault`, plus the public `mask_text` leg.

The mass rule, stated as a rule rather than as the owner's one example:

  * А-1  A damaged name standing alone after a naming cue is a NAME. The cue is
         the anchor that licenses the four-letter neighbourhood («игрь» is one
         deletion from «игорь»), the same argument `_cued_misspelt_names` already
         makes for «запишите свтлана».
  * А-2  The mint applies the SAME edit to the drawn fake: the word standing in
         the damaged slot of the surface comes back one edit away from a clean
         dictionary name, so a model reading it still asks «вы имели в виду…?».
  * А-3  The damaged word is not eaten by an address/document context: «улица
         игрь» stays a place, not a person.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from pseudex.assets import ASSETS  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.fuzzy import edit_from  # noqa: E402
from pseudex.morph_names import name_shape  # noqa: E402
from pseudex.names import recover_damaged_name  # noqa: E402
from pseudex.redact import mask_text  # noqa: E402
from pseudex.vault import Vault, _apply_name_typos, _name_typo_edits  # noqa: E402

_FIRST_NAMES = {name.casefold() for name in ASSETS.get().names.dict_first}


def _is_clean_name(word: str) -> bool:
    """A clean dictionary name, not a typo of one."""
    return word.casefold() in _FIRST_NAMES or word.casefold() in {
        name.casefold() for name in ASSETS.get().names.dict_surnames}

RESULTS: list[tuple[bool, str, str]] = []


def _check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'RED '}  {name}" + (f"   {detail}" if detail else ""))


def _vault() -> Vault:
    return Vault(":memory:", "typo").for_conversation("c1")


def _detect(text: str) -> list[tuple[str, str]]:
    return [(s.entity_type, s.value) for s in Detector().detect(text)]


def _mask(text: str, vault: Vault) -> str:
    return mask_text(text, vault, Detector().detect(text))


def a1_the_single_damaged_name_is_detected() -> None:
    # The owner's literal example: one damaged word, no pair.
    spans = _detect("меня зовут игрь")
    _check(any(kind == "NAME" and value == "игрь" for kind, value in spans),
           "А-1 «меня зовут игрь» is detected as a NAME",
           repr(spans))
    _check(recover_damaged_name("игрь") is not None,
           "А-1 «игрь» recovers to a dictionary name",
           repr(recover_damaged_name("игрь")))


def a2_the_substitute_carries_the_typo() -> None:
    # THE MASS RULE, DETERMINISTICALLY: the edit that turned the dictionary name
    # into the damaged surface is read off and applied to the drawn fake, so the
    # fake is one edit from a clean name by the SAME edit the customer made.
    edits = _name_typo_edits("игрь", name_shape("игрь"))
    _check(0 in edits and edits[0] is not None,
           "А-2 «игрь» reads as one edit from its dictionary name",
           repr(edits))
    applied = _apply_name_typos("егор", edits)
    landed = edit_from("егор", applied)
    _check(applied != "егор" and landed is not None
           and landed.op == edits[0].op and landed.pos == edits[0].pos,
           "А-2 the SAME edit lands on the drawn fake («егор» → «егр»-shaped)",
           f"{applied!r}")

    # A clean name gets a clean substitute; a damaged name gets a damaged one.
    vault = _vault()
    clean = _mask("меня зовут егор", vault)
    clean_word = clean.split()[-1]
    _check(_is_clean_name(clean_word),
           "А-2 a CLEAN name's substitute is a clean dictionary word",
           f"{clean_word!r}")

    # The pair case REVIEW-SPRINT.md named: «игрь павлов» used to mint a clean
    # «георгий мухин». The damaged given-name slot is edited, the clean surname
    # slot is not — proven on the SURFACE, not on the random draw.
    pair_edits = _name_typo_edits("игрь павлов", name_shape("игрь павлов"))
    _check(0 in pair_edits and 1 not in pair_edits,
           "А-2 «игрь павлов»: the damaged given name carries the edit, the clean surname does not",
           repr(pair_edits))


def a3_a_damaged_word_in_an_address_is_not_a_person() -> None:
    # The cue is the anchor; without it the same four letters are not a NAME.
    spans = _detect("улица игрь 5")
    _check(not any(kind == "NAME" for kind, _value in spans),
           "А-3 «улица игрь 5» produces no NAME span (place, not person)",
           repr(spans))


def main() -> int:
    print("Class А — the substitute inherits the customer's typo\n")
    a1_the_single_damaged_name_is_detected()
    a2_the_substitute_carries_the_typo()
    a3_a_damaged_word_in_an_address_is_not_a_person()
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
