#!/usr/bin/env python3
"""Class Д — a positional slice of the canon is forbidden without a NAMED place.

    cd prototype && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_positional_slice_guard.py

`DECISIONS-SPRINT.md` §Д («место/нотацию листа объявляет FieldSpec, не
угадываем») and `REVIEW-SPRINT.md` point 4: `{"inn":"0084999497"}` handed the
tool 10 of 12 REAL digits (`real[start:start+len(digits)]`) with `residual=[]`,
and `{"x":"6984"}` resolved exactly like `{"last4":"6984"}` — the field name was
never read. The positional slice is now licensed only by a NAMED edge
(`series`/`number`/`last4`); a field that names neither restores WHOLE or is
reported, never sliced.

Self-contained: the dev bundle, a real `Vault`, the real JSON leg
`unmask_arguments`, and the public `surviving_substitutes`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from pseudex.detect import Span  # noqa: E402
from pseudex.redact import mask_text, surviving_substitutes, unmask_arguments  # noqa: E402
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


def _tool(payload: dict[str, object], vault: Vault) -> dict[str, object]:
    return json.loads(unmask_arguments(json.dumps(payload, ensure_ascii=False), vault))


def _residual(written: dict[str, object], got: dict[str, object], vault: Vault) -> list[str]:
    return surviving_substitutes(json.dumps(written, ensure_ascii=False),
                                 json.dumps(got, ensure_ascii=False), vault, True)


def d1_an_unnamed_edge_never_slices_the_canon() -> None:
    # REVIEW-SPRINT.md point 4, byte-for-byte: the model dropped the ИНН's
    # checksum, writing the substitute's first ten digits. The tool used to get
    # `390068146509[0:10]` = 10 of 12 real digits. Now the run is not sliced.
    vault = _vault("d1")
    with patch("pseudex.vault._fake_inn", return_value="008499949700"):
        mask_text("инн 390068146509", vault, [_span("инн 390068146509", "390068146509", "INN")])
    written = {"inn": "0084999497"}
    got = _tool(written, vault)
    _check(_digits(got["inn"]) != "3900681465",
           "Д-1 the tool never gets canon[:10] of a 12-digit ИНН",
           repr(got))
    residual = _residual(written, got, vault)
    _check(any(_digits(item) == "0084999497" for item in residual),
           "Д-1 …and the unresolvable run is NAMED, not silent",
           repr(residual))


def d2_an_unnamed_field_does_not_slice_like_a_named_one() -> None:
    # `{"x":"6984"}` must not resolve like `{"last4":"6984"}` — the field name is
    # what names the edge, and «x» names nothing.
    vault = _vault("d2")
    with patch("pseudex.vault._fake_card", return_value="0110183024186984"):
        mask_text("карта 2200666689026161", vault,
                  [_span("карта 2200666689026161", "2200666689026161", "CARD")])
    got = _tool({"x": "6984"}, vault)
    _check(_digits(got["x"]) == "6984",
           "Д-2 «x» names no edge and is never sliced",
           repr(got))


def d3_the_named_place_still_slices() -> None:
    # `last4` and the passport's series/number ARE named places; they stay green.
    vault = _vault("d3")
    with patch("pseudex.vault._fake_card", return_value="0110183024186984"):
        mask_text("карта 2200666689026161", vault,
                  [_span("карта 2200666689026161", "2200666689026161", "CARD")])
    got = _tool({"last4": "6984"}, vault)
    _check(_digits(got["last4"]) == "6161",
           "Д-3 «last4» still resolves to the real last four",
           repr(got))

    vault = _vault("d3b")
    masked = mask_text("паспорт 4608 246256", vault,
                       [_span("паспорт 4608 246256", "4608 246256", "PASSPORT")])
    fake = _digits(masked.split("паспорт ", 1)[1])
    got = _tool({"series": fake[:4], "number": fake[4:10]}, vault)
    _check(_digits(got["series"]) == "4608" and _digits(got["number"]) == "246256",
           "Д-3 the passport's series/number still slice to their own places",
           f"{got!r}")


def d4_the_whole_number_still_restores_whole() -> None:
    # Д-1 from `test_digit_truncation`: the SAME number with zeros dropped still
    # restores WHOLE — this is the whole-value rule, not a slice.
    vault = _vault("d4")
    with patch("pseudex.vault._fake_inn", return_value="008499949700"):
        mask_text("инн 390068146509", vault, [_span("инн 390068146509", "390068146509", "INN")])
    got = _tool({"inn": "8499949700"}, vault)
    _check(_digits(got["inn"]) == "390068146509",
           "Д-4 the same NUMBER without its zeros restores the whole value",
           repr(got))


def main() -> int:
    print("Class Д — a positional slice needs a NAMED place\n")
    d1_an_unnamed_edge_never_slices_the_canon()
    d2_an_unnamed_field_does_not_slice_like_a_named_one()
    d3_the_named_place_still_slices()
    d4_the_whole_number_still_restores_whole()
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
