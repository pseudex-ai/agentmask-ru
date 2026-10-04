"""The v6 perfect-gateway mint, re-versioned (TZ §6.2 T8; V1 S5 / OC-2 /
MUTANT-LINE-REDEFINE / COV-CHECKSUM-INHERIT).

    cd prototype && source .venv/bin/activate
    && python3 -m bench.agentpii5.test_perfect_v6

THE ACCEPTED SEMANTICS CHANGED. R6-39 re-minted until the published checksum
FAILED, which is the `valid -> invalid` mutant under the owner's choice: a VALID
source mints a VALID substitute, and a faulty source is NOT repaired. So the
claims here are:

  * a minted substitute keeps the type's grammar, shares no DIGIT position with
    the sample (the fixed structural letters of «А31-…» / «…-ИП» are the type's
    own shape, not the customer's data), and INHERITS the source's checksum
    verdict — valid stays valid, faulty is not repaired;
  * the historical `mint_v6_remint_invalid` arm is kept and is DISTINCT from the
    correct arm: for a valid source it produces the `valid -> invalid` mutant;
  * the four mutants (valid->invalid, invalid->valid, wrong form, unsafe
    identity/collision) are each distinct from the correct arm, reproducibly.

Offline, over the registry's own `sample` per type: no model, no engine.
"""
import sys
from collections.abc import Callable

from bench.agentpii5 import contracts, perfect, pii_types
from bench.agentpii5.fixtures import _item, _in_message, _case, _obs, _run, _with_subs
from bench.agentpii5.metrics import CHECKSUM_METRIC_FUNCTIONS


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _checksummed() -> list[pii_types.TypeSpec]:
    return [t for t in pii_types.TYPE_REGISTRY
            if t.origin == pii_types.ORIGIN_V6 and t.mint and t.generated_checksum]


def _minted() -> list[pii_types.TypeSpec]:
    return [t for t in pii_types.TYPE_REGISTRY if t.origin == "v6" and t.mint]


def _obs_with(pii_type: str, source: str, substitute: str):
    """One observation: a checksum-carrying item whose substitute is `substitute`."""
    item = _item("e1", pii_type, source, source, "i1", _in_message(0, 0, len(source)))
    case = _case("pfv", "single", (source,), (item,), ())
    return _obs(case, _with_subs(_run("pfv"), {"e1": substitute}), ())


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_mint_inherits_source_validity() -> list[str]:
    """T8 under COV-CHECKSUM-INHERIT, over EVERY v6 type that carries a mint
    rule: the substitute differs from the sample, shares no digit position with
    it, passes the grammar, and — for a checksum type — carries the SAME
    checksum verdict as the source."""
    problems: list[str] = []
    minted = _minted()
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
        if spec.generated_checksum and (perfect._v6_checksum_valid(spec, surface)
                                        != perfect._v6_checksum_valid(spec, spec.sample)):
            problems.append(f"{spec.id}: the substitute did not inherit the source's "
                            f"checksum verdict ({surface!r})")
    return problems


def test_faulty_source_is_not_repaired() -> list[str]:
    """The other half of inheritance: a source that FAILS its checksum must mint
    a substitute that fails too. `invalid -> valid` (a repair) is a mutant, and
    the mint loop must not fall into it while searching for a valid spelling."""
    problems: list[str] = []
    oms = next(t for t in pii_types.TYPE_REGISTRY if t.id == "OMS_ENP")
    faulty = "7707536455681515"          # Luhn-invalid body
    if perfect._v6_checksum_valid(oms, faulty):
        return ["the fixture is not a faulty source — the test is vacuous"]
    made = perfect.mint_v6(oms, (faulty,))[0]
    if perfect._v6_checksum_valid(oms, made):
        problems.append(f"a faulty source was REPAIRED into a valid fake ({made!r})")
    valid = oms.sample
    if not perfect._v6_checksum_valid(oms, valid):
        problems.append("the registry sample is not a valid source — the test is vacuous")
    if not perfect._v6_checksum_valid(oms, perfect.mint_v6(oms, (valid,))[0]):
        problems.append("a valid source did not mint a valid fake")
    return problems


def test_remint_invalid_arm_is_historical() -> list[str]:
    """R6-39 is KEPT, NAMED, AND NOT THE ACCEPTED SEMANTICS: the historical arm
    still re-mints until the checksum fails, for every checksum type, and for a
    valid source that is exactly the `valid -> invalid` mutant."""
    problems: list[str] = []
    for spec in _checksummed():
        made = perfect.mint_v6_remint_invalid(spec, (spec.sample,))[0]
        if perfect._v6_checksum_valid(spec, made):
            problems.append(f"{spec.id}: the historical arm left a valid substitute ({made!r})")
        if made == perfect.mint_v6(spec, (spec.sample,))[0]:
            problems.append(f"{spec.id}: the historical arm is not distinct from the "
                            f"accepted arm")
    return problems


def test_mutants_are_distinct_from_the_correct_arm() -> list[str]:
    """The four mutants, each separated from the correct arm and reproducible
    across two runs: `valid -> invalid` and `invalid -> valid` by the v2 line,
    `wrong form` by the grammar contract, `unsafe identity/collision` by the
    no-shared-position rule."""
    problems: list[str] = []
    oms = next(t for t in pii_types.TYPE_REGISTRY if t.id == "OMS_ENP")
    ok_src, bad_src = "7707536455681514", "7707536455681515"
    if not (perfect._v6_checksum_valid(oms, ok_src) and not perfect._v6_checksum_valid(oms, bad_src)):
        return ["the OMS_ENP fixtures do not carry the expected verdicts"]
    line = CHECKSUM_METRIC_FUNCTIONS["fake_checksum_inherited"]
    correct = perfect.mint_v6(oms, (ok_src,))[0]

    def verdicts() -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for source, substitute in ((ok_src, correct), (ok_src, bad_src), (bad_src, ok_src)):
            one = line((_obs_with("OMS_ENP", source, substitute),))
            out.append((one.hits, one.total))
        return out

    first = verdicts()
    if first[0] != (1, 1):
        problems.append(f"the correct arm scored {first[0]}, expected (1, 1)")
    if first[1] != (0, 1):
        problems.append(f"the valid->invalid mutant scored {first[1]}, expected (0, 1)")
    if first[2] != (0, 1):
        problems.append(f"the invalid->valid mutant scored {first[2]}, expected (0, 1)")
    if verdicts() != first:
        problems.append("the mutant verdicts are not reproducible across two runs")

    vin = next(t for t in pii_types.TYPE_REGISTRY if t.id == "VIN")
    correct_vin = perfect.mint_v6(vin, (vin.sample,))[0]
    if not perfect._grammar_holds(vin, correct_vin):
        problems.append("the correct arm broke the form — the wrong-form mutant is not distinct")
    if perfect._grammar_holds(vin, "XTAGFK330LY12345!"):
        problems.append("the wrong-form mutant passed the grammar contract")
    if any(a == b for a, b in zip(_digits(vin.sample), _digits(correct_vin))):
        problems.append("the correct arm shares a digit position with the source — the "
                        "unsafe-identity mutant is not distinct")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("mint_inherits_source_validity", test_mint_inherits_source_validity),
        ("faulty_source_is_not_repaired", test_faulty_source_is_not_repaired),
        ("remint_invalid_arm_is_historical", test_remint_invalid_arm_is_historical),
        ("mutants_are_distinct_from_the_correct_arm",
         test_mutants_are_distinct_from_the_correct_arm),
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
