#!/usr/bin/env python3
"""Class В — one persona = one substitution set, whatever order the parts arrive.

    cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_one_person_one_mint.py

`DECISIONS-SPRINT.md` §В and `REVIEW-SPRINT.md` point 3: a CRM card
`{"last_name":"Иванов","first_name":"Пётр","middle_name":"Сергеевич"}` and the
same person written as a whole string minted DIFFERENT substitute sets in one
conversation (g10 П2). The reverse order (whole → card) already reused the parts;
the forward order (card → whole) minted a fourth identity. `_tokenize_unrecorded`
now unites a full name whose every part already has a lone substitute in the
conversation, so the parts and the whole collapse to ONE set.

Self-contained: the dev bundle, a real `Vault`, `mask_text`, and the real JSON
leg `unmask_arguments`.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import mask_text, unmask_arguments  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def _check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'RED '}  {name}" + (f"   {detail}" if detail else ""))


def _vault() -> Vault:
    return Vault(":memory:", "person").for_conversation("c1")


def _mask(text: str, vault: Vault) -> str:
    return mask_text(text, vault, Detector().detect(text))


_CARD = '{"last_name":"Иванов","first_name":"Пётр","middle_name":"Сергеевич"}'
_WHOLE = "клиент Иванов Пётр Сергеевич"


def _card_parts(masked: str) -> dict[str, str]:
    return json.loads(masked)


def _whole_words(masked: str) -> list[str]:
    return masked.replace("клиент ", "").split()


def v1_card_then_whole_unites() -> None:
    vault = _vault()
    card = _card_parts(_mask(_CARD, vault))
    whole = _whole_words(_mask(_WHOLE, vault))
    _check(whole == [card["last_name"], card["first_name"], card["middle_name"]],
           "В-1 the whole name after the card is the UNION of the card's parts",
           f"{card!r} vs {whole!r}")


def v2_whole_then_card_unites() -> None:
    vault = _vault()
    whole = _whole_words(_mask(_WHOLE, vault))
    card = _card_parts(_mask(_CARD, vault))
    _check([card["last_name"], card["first_name"], card["middle_name"]] == whole,
           "В-2 the card after the whole name reuses the whole's parts",
           f"{whole!r} vs {card!r}")


def v3_order_does_not_matter() -> None:
    # Both orders end in ONE set: surname+name+patronymic stay consistent.
    vault = _vault()
    a = _card_parts(_mask(_CARD, vault))
    b = _whole_words(_mask(_WHOLE, vault))
    _check((a["last_name"], a["first_name"], a["middle_name"]) == tuple(b),
           "В-3 one persona is one set, card before or after the whole",
           f"{a!r} / {b!r}")


def v4_the_tool_gets_the_real_parts_back() -> None:
    # The one substitute set still round-trips each field to the REAL value.
    vault = _vault()
    _mask(_CARD, vault)
    _mask(_WHOLE, vault)
    card = _card_parts(_mask(_CARD, vault))      # the model echoes the card back
    # Each masked field must resolve to the real part it replaced.
    import re
    raw = json.dumps({k: card[k] for k in ("last_name", "first_name", "middle_name")},
                     ensure_ascii=False)
    restored = json.loads(unmask_arguments(raw, vault))
    _check(restored == {"last_name": "Иванов", "first_name": "Пётр", "middle_name": "Сергеевич"},
           "В-4 the tool receives the real parts, not a mixture",
           repr(restored))


def main() -> int:
    print("Class В — one persona = one substitution set\n")
    v1_card_then_whole_unites()
    v2_whole_then_card_unites()
    v3_order_does_not_matter()
    v4_the_tool_gets_the_real_parts_back()
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
