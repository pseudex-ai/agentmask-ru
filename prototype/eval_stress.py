"""Score the adversarial stress set — the one built to break the detector.

`make_stress.py` produced the cases WITHOUT looking at the detector, and the
rule in CLAUDE.md is that it must not be tuned against. This scorer exists
because the set had no scorer at all, so it was generated and never read.

MATCHING IS TYPE-AWARE, and that is not leniency. Layer 0 folds homoglyphs and
dashes before detection — Cyrillic `О` becomes `0`, an en-dash becomes a hyphen
— so a phone written `89545297О85` is reported as `89545297085`. Comparing the
raw ground-truth string to the reported one would score a correct detection as a
miss, which is exactly the mistake that made this look like a 97.8% recall
problem when the real number was higher.

    python3 make_stress.py && python3 eval_stress.py
"""

import json
import re
import sys
from collections import defaultdict

import testkit
from pseudex.detect_all import Detector
from pseudex.normalize import normalize

_NUMERIC = {"PHONE", "INN", "SNILS", "CARD", "PASSPORT", "OGRN", "OMS"}


def _digits(value: str) -> str:
    """Digits AFTER the same Layer 0 fold the engine applies.

    Without normalising first, a ground-truth phone written with a Cyrillic `О`
    loses that character entirely instead of gaining a `0`, the digit count
    comes out one short, and a perfectly correct detection scores as a miss —
    which is how this set first appeared to have a 97.8% phone recall problem
    that did not exist.
    """
    return re.sub(r"\D", "", normalize(value))


def _matches(expected_type: str, expected: str, found: list[tuple[str, str]]) -> bool:
    """Whether the detector found this value, allowing for normalisation."""
    for found_type, found_value in found:
        if expected_type in _NUMERIC:
            # Digits only, and only the tail: a phone may be reported with or
            # without a country code depending on how it was written.
            want, got = _digits(expected), _digits(found_value)
            if want and got and (want[-10:] in got or got[-10:] in want):
                return True
            continue
        if expected.casefold() in found_value.casefold():
            return True
        if found_value.casefold() in expected.casefold():
            return True
    return False


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    with open("stress.json", encoding="utf-8") as handle:
        cases = json.load(handle)

    hits: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    misses: list[tuple[str, str, str]] = []
    false_masks: list[tuple[str, str]] = []

    for case in cases:
        text = case["text"]
        found = [(span.entity_type, span.value) for span in detector.detect(text)]

        for entity in case.get("entities", []):
            kind, value = entity["type"], entity["value"]
            total[kind] += 1
            if _matches(kind, value, found):
                hits[kind] += 1
            elif len(misses) < 400:
                misses.append((kind, value, text[:70]))

        # A negative is a value that LOOKS like PII and is not. Masking it makes
        # the model blind to something the customer needed.
        for negative in case.get("negatives", []):
            if _matches("OTHER", negative, found) or _matches("PHONE", negative, found):
                false_masks.append((negative, text[:70]))

    print(f"stress set: {len(cases)} cases, built independently of the detector\n")
    print(f"{'TYPE':<10} {'GT':>5} {'RECALL':>8}")
    print("-" * 26)
    for kind in sorted(total):
        rate = hits[kind] / total[kind] * 100
        print(f"{kind:<10} {total[kind]:>5} {rate:>7.1f}%")
    grand_total = sum(total.values())
    grand_hits = sum(hits.values())
    print("-" * 26)
    print(f"{'OVERALL':<10} {grand_total:>5} {grand_hits / grand_total * 100:>7.1f}%")
    print(f"\nfalse masks on negatives: {len(false_masks)}")

    if misses:
        print(f"\n--- MISSES ({len(misses)}) ---")
        for kind, value, text in misses[:25]:
            print(f"  {kind:<9} {value!r:34} in {text!r}")
    if false_masks:
        print(f"\n--- FALSE MASKS ({len(false_masks)}) ---")
        for value, text in false_masks[:15]:
            print(f"  {value!r:34} in {text!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
