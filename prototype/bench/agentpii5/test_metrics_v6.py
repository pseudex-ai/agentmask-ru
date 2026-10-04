"""`metrics.py` v6 pinned: the value_notation comparison, the certificate over
CASES, the three OD-54 rows with their fixtures, and the re-versioned checksum
line (V1 S5 / OC-2 / MUTANT-LINE-REDEFINE).

    cd prototype && source .venv/bin/activate
    && python3 -m bench.agentpii5.test_metrics_v6

Everything here is offline: hand-built observations, the real `metrics`
functions, no model, no engine. The three new rows live in
`metrics.V6_METRIC_FUNCTIONS` + `fixtures.V6_FIXTURES` — OUTSIDE the v5
`METRIC_FUNCTIONS`/`FIXTURES` — so `test_metrics` and `test_fixtures` keep
pinning the closed v5 surface while these rows are gated to a v6 run. The
checksum line is VERSIONED on top of that: v1 is historical and v2 is the
accepted semantics under COV-CHECKSUM-INHERIT.
"""
import sys
from collections.abc import Callable

from bench.agentpii5 import contracts, perfect, pii_types
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    REAL_NAME,
    V6_FIXTURES,
    _case,
    _hop,
    _in_message,
    _item,
    _obs,
    _run,
    _seen,
    _with_subs,
)
from bench.agentpii5.metrics import (
    CHECKSUM_LINE_VERSIONS,
    CHECKSUM_METRIC_FUNCTIONS,
    V6_METRIC_FUNCTIONS,
    certified_over_cases,
    leak,
    value_matches,
)


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_value_notation() -> list[str]:
    """R6-38. A value compared by its registry `value_notation`: LETTERS enter a
    glyph-folded comparison (a letter substitution is a miss, the correct series
    a hit), while a digit type folds to its digit run so a grouped spelling is
    still the value."""
    problems: list[str] = []
    # glyph_fold: the letters enter — a changed letter is a different VIN.
    if not value_matches("VIN", "XTAGFK330LY123456", "XTAGFK330LY123456"):
        problems.append("VIN: the sample did not match itself under glyph_fold")
    if value_matches("VIN", "XTAGFK330LY123456", "XTAHFK330LY123456"):
        problems.append("VIN: a letter substitution (G→H) was read as the same value")
    if value_matches("VIN", "XTAGFK330LY123456", "XTAGFK330LY000000"):
        problems.append("VIN: a digit substitution was read as the same value")
    # A homoglyph rewrite is the SAME value: the glyph fold sees ХТА == XTA.
    if not value_matches("VIN", "ХТАGFK330LY123456", "XTAGFK330LY123456"):
        problems.append("VIN: a Cyrillic homoglyph of the same letters was read as another value")
    # digits: separators are folded away, the digit run is the value.
    if not value_matches("OMS_ENP", "7707 5364 5568 1514", "7707536455681514"):
        problems.append("OMS_ENP: a grouped spelling of one digit run was read as another value")
    return problems


def test_by_fields() -> list[str]:
    """R6-38. A series+number carried in separate leaves arrives joined with
    `FIELD_SEP`; the two parts are compared IN ORDER, so the correct assignment
    is a hit and a swapped series/number is a miss (TZ §5.5)."""
    problems: list[str] = []
    sep = contracts.FIELD_SEP
    if not value_matches("INTL_PASSPORT", f"75{sep}1234567", f"75{sep}1234567"):
        problems.append("the by-fields record did not match itself")
    if not value_matches("INTL_PASSPORT", f"75{sep}1234567", "751234567"):
        problems.append("a by-fields value did not match its one-string spelling")
    if value_matches("INTL_PASSPORT", f"1234567{sep}75", f"75{sep}1234567"):
        problems.append("a swapped series/number was read as the same value")
    return problems


def test_ip_strict() -> list[str]:
    """R6-38. `ip_strict` parses both sides with `ipaddress`: an IPv4 with a
    LEADING ZERO is a DIFFERENT host, so it is a value miss even though the
    `octets` leak needle would still find it."""
    problems: list[str] = []
    if not value_matches("IP_ADDRESS", "192.168.10.24", "192.168.10.24"):
        problems.append("an IPv4 address did not match itself")
    if value_matches("IP_ADDRESS", "192.168.010.024", "192.168.10.24"):
        problems.append("a padded IPv4 octet was read as the same host")
    if value_matches("IP_ADDRESS", "192.168.10.24", "192.168.11.24"):
        problems.append("a different IPv4 host was read as the same value")
    return problems


def _clean_case(case_id: str, hop_count: int) -> object:
    """One case with `hop_count` observed IN/user NAME hops — the clean rows the
    certificate test needs. One item, one message, many declared hops, all
    `observed`."""
    item = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))
    hops = tuple(_hop("IN", "user", "p1", index, 0, "", -1, -1, "") for index in range(hop_count))
    case = _case(case_id, "single", (REAL_NAME,), (item,), hops)
    return _obs(case, _run(case_id),
                tuple(_seen(case, hop, "NAME", FAKE_NAME, REAL_NAME) for hop in hops))


def test_certificate_by_cases() -> list[str]:
    """R6-40. A clean per-type line certifies over DISTINCT CASES, not hops:
    240 clean hops from 12 cases certify `zero_failure_floor(12)` ≈ 77.9 %, never
    the ~98 % the hop count would claim (TZ §6.4, OD-67)."""
    problems: list[str] = []
    observations = tuple(_clean_case(f"cert-{index:02d}", 20) for index in range(12))
    line = leak(observations)
    if (line.hits, line.total) != (240, 240):
        problems.append(f"the fixture is not 240 clean hops: {line.hits}/{line.total}")
    certified = certified_over_cases(leak, observations)
    if certified is None:
        problems.append("a clean line over 12 cases returned no certificate")
        return problems
    if not certified <= 0.78:
        problems.append(f"12 cases certify {certified:.4f}, expected ≤ 0.779 (the hop count "
                        f"would have certified {line.certified:.4f})")
    if certified >= line.certified:  # type: ignore[arg-type] - both floats, hop floor is ~98%
        problems.append("the case floor is not BELOW the hop floor — the certificate is not "
                        "over cases")
    return problems


def test_three_new_rows() -> list[str]:
    """The three OD-54 rows ship zero/one/adversarial each, and their metric
    prints the declared fraction (the same gate shape `test_fixtures` runs on
    the v5 rows, TZ §6.3 / R6-29)."""
    problems: list[str] = []
    if sorted(V6_FIXTURES) != ["fake_checksum_invalid", "overmask_result", "typed_user"]:
        problems.append(f"V6_FIXTURES holds {sorted(V6_FIXTURES)}")
    if sorted(V6_METRIC_FUNCTIONS) != sorted(V6_FIXTURES):
        problems.append("V6_METRIC_FUNCTIONS and V6_FIXTURES disagree about the rows")
    for name in sorted(V6_METRIC_FUNCTIONS):
        fixtures = V6_FIXTURES[name]
        kinds = [fixture.kind for fixture in fixtures]
        if sorted(kinds) != sorted(contracts.FIXTURE_KINDS):
            problems.append(f"{name}: kinds {kinds}, expected {list(contracts.FIXTURE_KINDS)}")
        for fixture in fixtures:
            line = V6_METRIC_FUNCTIONS[name](fixture.input)
            if (line.hits, line.total) != (fixture.expected_hits, fixture.expected_total):
                problems.append(f"{fixture.name}: printed {line.hits}/{line.total}, "
                                f"declared {fixture.expected_hits}/{fixture.expected_total}")
    return problems


def _checksum_obs(pii_type: str, source: str, substitute: str):
    """One observation: a checksum-carrying item whose substitute is `substitute`."""
    item = _item("e1", pii_type, source, source, "i1", _in_message(0, 0, len(source)))
    case = _case("s5-cs", "single", (source,), (item,), ())
    return _obs(case, _with_subs(_run("s5-cs"), {"e1": substitute}), ())


def test_checksum_line_reversioned() -> list[str]:
    """V1 S5 / OC-2 / MUTANT-LINE-REDEFINE. The checksum line is VERSIONED: v1
    (`fake_checksum_invalid`, "the fake fails its checksum") is kept as the
    HISTORICAL row so no saved result is reinterpreted, and v2
    (`fake_checksum_inherited`, "the fake's verdict matches the SOURCE's") is the
    accepted semantics under COV-CHECKSUM-INHERIT. The new mutant set is
    reproducibly distinct from the correct arm: `valid -> invalid` and
    `invalid -> valid` are misses on v2, while the historical v1 line REWARDS the
    `valid -> invalid` arm — which is exactly why v1 cannot stay the live line."""
    problems: list[str] = []
    if CHECKSUM_LINE_VERSIONS != {"fake_checksum_invalid": 1, "fake_checksum_inherited": 2}:
        problems.append(f"the version map is {CHECKSUM_LINE_VERSIONS}")
    if set(CHECKSUM_METRIC_FUNCTIONS) != set(CHECKSUM_LINE_VERSIONS):
        problems.append("CHECKSUM_METRIC_FUNCTIONS and CHECKSUM_LINE_VERSIONS disagree")
    if CHECKSUM_METRIC_FUNCTIONS.get("fake_checksum_invalid") is not V6_METRIC_FUNCTIONS.get(
            "fake_checksum_invalid"):
        problems.append("the V6 report row is not the historical v1 function")
    if CHECKSUM_METRIC_FUNCTIONS.get("fake_checksum_invalid") is CHECKSUM_METRIC_FUNCTIONS.get(
            "fake_checksum_inherited"):
        problems.append("the two versions are the same function")

    # The historical row still gates on its own fixtures (a saved result reads).
    for fixture in V6_FIXTURES["fake_checksum_invalid"]:
        line = CHECKSUM_METRIC_FUNCTIONS["fake_checksum_invalid"](fixture.input)
        if (line.hits, line.total) != (fixture.expected_hits, fixture.expected_total):
            problems.append(f"the historical fixture {fixture.name} printed "
                            f"{line.hits}/{line.total}, declared "
                            f"{fixture.expected_hits}/{fixture.expected_total}")

    oms = next(t for t in pii_types.TYPE_REGISTRY if t.id == "OMS_ENP")
    ok_src, bad_src = "7707536455681514", "7707536455681515"    # Luhn valid / invalid
    if not (perfect._v6_checksum_valid(oms, ok_src)
            and not perfect._v6_checksum_valid(oms, bad_src)):
        return problems + ["the OMS_ENP fixtures do not carry the expected verdicts"]
    live = CHECKSUM_METRIC_FUNCTIONS["fake_checksum_inherited"]
    historical = CHECKSUM_METRIC_FUNCTIONS["fake_checksum_invalid"]
    correct = perfect.mint_v6(oms, (ok_src,))[0]              # valid -> valid
    old_arm = perfect.mint_v6_remint_invalid(oms, (ok_src,))[0]  # valid -> invalid

    def live_verdicts() -> list[tuple[int, int]]:
        arms = ((ok_src, correct), (ok_src, old_arm), (bad_src, ok_src))
        out = []
        for source, substitute in arms:
            line = live((_checksum_obs("OMS_ENP", source, substitute),))
            out.append((line.hits, line.total))
        return out

    first = live_verdicts()
    if first[0] != (1, 1):
        problems.append(f"the correct arm scored {first[0]} on v2, expected (1, 1)")
    if first[1] != (0, 1):
        problems.append(f"the valid->invalid mutant scored {first[1]} on v2, expected (0, 1)")
    if first[2] != (0, 1):
        problems.append(f"the invalid->valid mutant scored {first[2]} on v2, expected (0, 1)")
    if live_verdicts() != first:
        problems.append("the mutant verdicts are not reproducible across two runs")
    # The historical line is what makes v1 unusable as the live line: it gives
    # the valid->invalid arm the SAME perfect score the correct arm would hold
    # under the old rule (1/1), and 0/1 to the correct inheritance arm.
    if historical((_checksum_obs("OMS_ENP", ok_src, old_arm),)).hits != 1:
        problems.append("the historical v1 line no longer rewards valid->invalid")
    if historical((_checksum_obs("OMS_ENP", ok_src, correct),)).hits != 0:
        problems.append("the historical v1 line unexpectedly accepts the correct arm")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("value_notation", test_value_notation),
        ("by_fields", test_by_fields),
        ("ip_strict", test_ip_strict),
        ("certificate_by_cases", test_certificate_by_cases),
        ("three_new_rows", test_three_new_rows),
        ("checksum_line_reversioned", test_checksum_line_reversioned),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("metrics_v6: PASS" if not failures else "metrics_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
