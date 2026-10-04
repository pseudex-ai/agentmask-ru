"""The v6 needle kinds pinned: glyph, octets, ipv6 and the separator class in
the needle (tz-agentpii6.md §1.0, R6-12, R6-41).

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_observe_v6

The needle layer's contract is «does this value survive in this text». The three
v6 kinds are the shapes a v6 value survives being rewritten in that v5 did not
know: `glyph` (a homoglyph rewrite of the letters), `octets` (an IPv4 written
with leading zeros) and `ipv6` (the same address written compressed or full).
R6-12 demands, for EVERY (type, kind) the registry declares, both an occurrence
that IS found and a near-miss that is NOT invented; R6-41 demands the separator
class rides in the needle, so a value respaced from «/» or «:» is not lost.

Follows the v5 convention (`main() -> int`, 1 on failure, no pytest).
"""
import re
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from bench.agentpii5.observe import _needle_spans, survives_in, value_needles
from bench.agentpii5.pii_types import ORIGIN_V6, TYPE_REGISTRY

V6: tuple = tuple(record for record in TYPE_REGISTRY if record.origin == ORIGIN_V6)

# The separators a v6 identifier carries inside its span (R6-35): space, «-»,
# «/», «:», «№». Used to build a respaced rewrite.
_SEP_RUN = re.compile(r"[ .\-/:№]+")


def _digits(text: str) -> str:
    return "".join(character for character in text if character.isdigit())


def _change_a_digit(text: str) -> str:
    """The text with ONE digit changed — a near-miss no needle should invent:
    the digit signature differs, so `whole`, `digits`, `squeezed`, `glyph`,
    `octets` and `ipv6` all fail it."""
    for index, character in enumerate(text):
        if character.isdigit():
            return text[:index] + ("0" if character != "0" else "1") + text[index + 1:]
    return text


def _respace(text: str) -> str:
    """The value respaced: every separator dropped, then re-grouped in twos with
    spaces. A `squeezed`/`glyph` needle drops those spaces again, so this is the
    rewrite a model makes that no `whole` needle can see."""
    solid = _SEP_RUN.sub("", text)
    return " ".join(solid[index:index + 2] for index in range(0, len(solid), 2))


def _occurrence(kind: str, sample: str) -> str:
    """A text where `sample` survives via the needle kind `kind`."""
    if kind == "whole":
        return sample
    if kind == "digits":
        return " ".join(_digits(sample))
    if kind in ("squeezed", "glyph"):
        return _respace(sample)
    if kind == "octets":
        return ".".join(f"{int(octet):03d}" for octet in sample.split("."))
    raise ValueError(f"no occurrence builder for needle kind {kind!r}")


def _case(type_id: str, kind: str, sample: str) -> tuple[str, str, str]:
    """(surface, occurrence, near_miss) for one (type, kind). IP_ADDRESS's
    registry sample is IPv4, so `ipv6` needs its own IPv6 surface; everything
    else uses the record's sample."""
    if type_id == "IP_ADDRESS" and kind == "ipv6":
        return ("2001:0db8:0000:0000:0000:0000:0000:0001",
                "2001:db8::1", "2001:db8::2")
    return sample, _occurrence(kind, sample), _change_a_digit(sample)


def test_every_kind_of_every_type() -> list[str]:
    """R6-12: for every (v6 type, needle kind) the registry declares, the kind
    is BUILT from the value, an occurrence is FOUND, and a one-digit near-miss
    is NOT invented."""
    problems: list[str] = []
    for record in V6:
        for kind in record.needle_kinds:
            surface, occurrence, near_miss = _case(record.id, kind, record.sample)
            needles = [needle for needle in value_needles(record.id, surface)
                       if needle.kind == kind]
            if not needles:
                problems.append(f"{record.id}.{kind}: declared but never built")
                continue
            if not any(_needle_spans(needle, occurrence) for needle in needles):
                problems.append(f"{record.id}.{kind}: occurrence {occurrence!r} not found")
            if survives_in(record.id, surface, near_miss, frozenset()):
                problems.append(f"{record.id}.{kind}: near-miss {near_miss!r} invented")
    return problems


def test_glyph_folds_cyrillic_latin() -> list[str]:
    """`glyph` = `squeezed` plus the Cyrillic/Latin/Roman fold (§1.0): a value
    rewritten with homoglyphs is one value. «ХТА» is «XTA», «ХХХ» is «XXX»."""
    problems: list[str] = []
    if not survives_in("VIN", "XTAGFK330LY123456", "номер ХТАGFK330LY123456 в базе", frozenset()):
        problems.append("glyph did not fold the Cyrillic ХТА to the Latin XTA")
    if survives_in("VIN", "XTAGFK330LY123456", "номер XTAGFK330LY123457 в базе", frozenset()):
        problems.append("glyph invented a VIN that is not there")
    if not survives_in("OSAGO_POLICY", "ХХХ 0123456789", "полис XXX 0123456789", frozenset()):
        problems.append("glyph did not fold the Cyrillic ХХХ to the Latin XXX")
    if not survives_in("BIRTH_CERT", "IV-МЮ № 123456", "серия ІV-МЮ № 123456", frozenset()):
        problems.append("glyph did not fold the Roman I to the Cyrillic І")
    return problems


def test_ipv6_matches_compressed_and_full() -> list[str]:
    """`ipv6` parses both sides and compares the ADDRESS, not the string (§1.0):
    the full writing and the compressed writing are one address, and another
    address is not."""
    problems: list[str] = []
    full = "2001:0db8:0000:0000:0000:0000:0000:0001"
    compressed = "2001:db8::1"
    if not survives_in("IP_ADDRESS", full, f"адрес {compressed} клиента", frozenset()):
        problems.append("ipv6 did not find the compressed writing of a full address")
    if not survives_in("IP_ADDRESS", compressed, f"адрес {full} клиента", frozenset()):
        problems.append("ipv6 did not find the full writing of a compressed address")
    if survives_in("IP_ADDRESS", full, "адрес 2001:db8::2 клиента", frozenset()):
        problems.append("ipv6 matched a different address")
    return problems


def test_octets_finds_leading_zero_ipv4() -> list[str]:
    """`octets` = IPv4 without leading zeros, leak-search only (§1.0):
    «192.168.010.024» is a leak of «192.168.10.24», a different host is not."""
    problems: list[str] = []
    if not survives_in("IP_ADDRESS", "192.168.10.24", "адрес 192.168.010.024 клиента", frozenset()):
        problems.append("octets did not find the leading-zero-stripped IPv4")
    if survives_in("IP_ADDRESS", "192.168.10.24", "адрес 192.168.10.25 клиента", frozenset()):
        problems.append("octets invented a different IPv4")
    return problems


def test_separator_class_in_needle() -> list[str]:
    """R6-41 / F28: the separator class rides in the needle, so a value whose
    internal separators are «/» or «:» is still found when respaced. The
    type-blind squeeze that dropped only spaces and dashes lost exactly these."""
    problems: list[str] = []
    cases = (
        ("CADASTRAL_NUMBER", "77:01:0001001:1234", "КН 77 01 0001001 1234"),
        ("MAC", "00:1A:2B:3C:4D:5E", "mac 00-1A-2B-3C-4D-5E"),
        ("FSSP_IP_NO", "1234567/25/77001-ИП", "ИП 1234567 25 77001 ИП"),
    )
    for type_id, surface, text in cases:
        if not survives_in(type_id, surface, text, frozenset()):
            problems.append(f"{type_id}: {surface!r} respaced as {text!r} was lost")
    return problems


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == "pseudex"]
    if bad:
        return [f"the engine is imported: {sorted(bad)}"]
    source = Path(__file__).with_name("observe.py").read_text("utf-8")
    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(("from pseudex", "import pseudex")):
            return [f"observe.py:{number} imports the engine: {stripped}"]
    return []


_TESTS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("every_kind_of_every_type", test_every_kind_of_every_type),
    ("glyph_folds_cyrillic_latin", test_glyph_folds_cyrillic_latin),
    ("ipv6_matches_compressed_and_full", test_ipv6_matches_compressed_and_full),
    ("octets_finds_leading_zero_ipv4", test_octets_finds_leading_zero_ipv4),
    ("separator_class_in_needle", test_separator_class_in_needle),
    ("no_pseudex", test_no_pseudex),
)


def main() -> int:
    failures: list[str] = []
    for name, test in _TESTS:
        found: list[str] = []
        try:
            found = test()
        except Exception as error:               # noqa: BLE001 — appended below, never hidden
            frame = traceback.extract_tb(error.__traceback__)[-1]
            found.append(f"raised {type(error).__name__}: {error} "
                         f"at {Path(frame.filename).name}:{frame.lineno}")
        print(f"  {name:34} {'PASS' if not found else 'FAIL'}")
        failures.extend(f"{name}: {one}" for one in found)
    print("observe_v6: PASS" if not failures else "observe_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
