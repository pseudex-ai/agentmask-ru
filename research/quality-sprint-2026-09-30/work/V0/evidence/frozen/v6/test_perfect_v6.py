"""The v6 perfect-gateway mint, pinned (TZ §6.2 T8, R6-39).

    cd prototype && source .venv/bin/activate
    && python3 -m bench.agentpii5.test_perfect_v6

Three claims, offline, over the registry's own `sample` per type: a minted
substitute keeps the type's grammar, shares no DIGIT position with the sample
(the fixed structural letters of «А31-…» / «…-ИП» are the type's own shape,
not the customer's data), and FAILS its published `generated_checksum` — where
the first shift still passes (Luhn ~12 %, §6.3), `mint_v6` re-mints until it
fails. Then a WRONG gateway that leaves the checksum standing is caught by
`fake_checksum_invalid` (0/1, not the 1.0 the right gateway holds).
"""
import sys
from collections.abc import Callable

from bench.agentpii5 import contracts, perfect, pii_types
from bench.agentpii5.fixtures import _item, _in_message, _case, _obs, _run, _with_subs
from bench.agentpii5.metrics import V6_METRIC_FUNCTIONS


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_mint_keeps_grammar_breaks_checksum() -> list[str]:
    """R6-39 / T8, over EVERY v6 type that carries a mint rule: the substitute
    differs from the sample, shares no digit position with it, passes the
    grammar, and (for a checksum type) FAILS its own checksum."""
    problems: list[str] = []
    minted = [t for t in pii_types.TYPE_REGISTRY if t.origin == "v6" and t.mint]
    if not minted:
        return ["the registry carries no v6 mint rule — the mint is not exercised"]
    for spec in minted:
        surface, _canonical, _parts = perfect.mint(spec.id, spec.sample, spec.sample, {}, {})
        if surface == spec.sample:
            problems.append(f"{spec.id}: the mint returned the sample unchanged")
        if any(a == b for a, b in zip(_digits(spec.sample), _digits(surface))):
            problems.append(f"{spec.id}: a digit position is shared with the sample")
        if not perfect._grammar_holds(spec, surface):
            problems.append(f"{spec.id}: the substitute broke the grammar ({surface!r})")
        if spec.generated_checksum and perfect._v6_checksum_valid(spec, surface):
            problems.append(f"{spec.id}: the substitute still passes its checksum "
                            f"({surface!r})")
    return problems


def test_luhn_remint_breaks_checksum() -> list[str]:
    """The §6.3 case: a +3 digit shift keeps a Luhn-valid body valid ~12 % of the
    time, so the FIRST mint may still pass. `mint_v6` re-mints until the checksum
    breaks (R6-39) — the substitute for a Luhn type is never checksum-valid."""
    problems: list[str] = []
    spec = pii_types.TYPE_REGISTRY
    enp = next(t for t in spec if t.id == "OMS_ENP")
    # The +3 first-shift of a Luhn body still passes in ~12 % of cases; drive the
    # loop over every seed and confirm the RESULT is always invalid whatever the
    # first shift produced.
    for body in ("770753645568151", "000000000000000", "123456789012345", "999999999999999"):
        surface = perfect.mint_v6(enp, (body,))[0]
        if perfect._v6_checksum_valid(enp, surface):
            problems.append(f"OMS_ENP body {body!r}: the mint left a checksum-valid "
                            f"substitute ({surface!r})")
    return problems


def test_wrong_gateway_that_keeps_the_checksum_is_caught() -> list[str]:
    """A gateway that mints WITHOUT re-minting leaves a checksum-VALID substitute;
    `fake_checksum_invalid` then prints 0/1, not the 1.0 a right gateway holds —
    the line the wrong gateway fails, exactly as §6.3 / M8 name it."""
    problems: list[str] = []
    item = _item("e1", "OMS_ENP", "7707536455681514", "7707536455681514", "i1",
                 _in_message(0, 0, 16))
    case = _case("pfv-wrong", "single", ("7707536455681514",), (item,), ())
    # The wrong substitute IS Luhn-valid (the sample itself); the right one is
    # the mint's checksum-broken substitute.
    wrong = _obs(case, _with_subs(_run("pfv-wrong"), {"e1": "7707536455681514"}), ())
    right = _obs(case, _with_subs(_run("pfv-wrong"),
                                  {"e1": perfect.mint_v6(
                                      next(t for t in pii_types.TYPE_REGISTRY
                                           if t.id == "OMS_ENP"),
                                      ("7707536455681514",))[0]}), ())
    wrong_line = V6_METRIC_FUNCTIONS["fake_checksum_invalid"]((wrong,))
    right_line = V6_METRIC_FUNCTIONS["fake_checksum_invalid"]((right,))
    if (wrong_line.hits, wrong_line.total) != (0, 1):
        problems.append(f"a checksum-valid substitute printed {wrong_line.hits}/{wrong_line.total}, "
                        f"expected 0/1")
    if (right_line.hits, right_line.total) != (1, 1):
        problems.append(f"a checksum-broken substitute printed {right_line.hits}/{right_line.total}, "
                        f"expected 1/1")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("mint_keeps_grammar_breaks_checksum", test_mint_keeps_grammar_breaks_checksum),
        ("luhn_remint_breaks_checksum", test_luhn_remint_breaks_checksum),
        ("wrong_gateway_that_keeps_the_checksum_is_caught",
         test_wrong_gateway_that_keeps_the_checksum_is_caught),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("perfect_v6: PASS" if not failures else "perfect_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
