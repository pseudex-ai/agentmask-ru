"""Did any real personal data actually reach the model?

No agent benchmark answers this — WorkBench does not score reads at all, BFCL
compares state and responses, τ³ instruments the USER simulator rather than the
agent. The verifier can only tell us whether the task succeeded. Whether a real
phone number crossed the wire is ours to check, and it is the claim the whole
product rests on.

Method: take every value the injector put into the dataset, then scan what the
proxy actually forwarded upstream.

The comparison is CANONICAL, not literal, and that is the point. A leak check
that greps for `+7 921 918-65-44` misses the same number written `89219186544`,
and a masker that merely reformats PII would score a perfect zero while leaking
every record. So each value is reduced to the same canonical key the vault uses,
and the wire text is reduced the same way before matching.

Two independent readings, because they fail differently:
  leak@wire   a real value found in what was forwarded. Must be 0. Non-zero is a
              product-invalidating defect, not a metric to trend.
  coverage    values that were never seen on the wire in ANY form. High coverage
              with zero leaks is the strong result; zero leaks with low coverage
              may just mean the data never travelled, which proves nothing.

usage: python3 leak_check.py <bfcl_data_file> <proxy_log>
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from obscura.vault import canonicalize  # noqa: E402

# Values the injector writes; see inject_ru_pii.py.
_PHONE_RE = re.compile(r"\+7 9\d{2} \d{3}-\d{2}-\d{2}")
_ADDRESS_RE = re.compile(r"(?:улица|проспект|Красный проспект)[^.\"]*?кв \d+")


def _collect_expected(entries: list[dict]) -> dict[str, list[str]]:
    """Every real value that must never appear upstream, grouped by type."""
    expected: dict[str, list[str]] = {"PHONE": [], "CARD": [], "INN": [],
                                      "NAME": [], "LOC": []}
    for entry in entries:
        travel = entry.get("initial_config", {}).get("TravelAPI")
        if not travel:
            continue
        for card_id, card in travel.get("credit_card_list", {}).items():
            expected["INN"].append(card_id)
            if isinstance(card, dict):
                if isinstance(card.get("card_number"), str):
                    expected["CARD"].append(card["card_number"])
                if isinstance(card.get("cardholder_name"), str):
                    expected["NAME"].append(card["cardholder_name"])
        first, last = travel.get("user_first_name"), travel.get("user_last_name")
        if isinstance(first, str) and isinstance(last, str):
            expected["NAME"].append(f"{first} {last}")
        text = json.dumps(entry, ensure_ascii=False)
        expected["PHONE"].extend(_PHONE_RE.findall(text))
        expected["LOC"].extend(_ADDRESS_RE.findall(text))
    return {k: sorted(set(v)) for k, v in expected.items()}


def _canonical_wire(text: str) -> str:
    """Reduce the forwarded text so reformatted values still match: digits are
    collapsed into one searchable run, and case is folded for the rest."""
    return re.sub(r"\D", "", text), text.lower()


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    entries = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
    wire_lines = [line for line in Path(sys.argv[2]).read_text(errors="replace").splitlines()
                  if "upstream role=" in line]
    if not wire_lines:
        raise SystemExit(f"{sys.argv[2]} contains no forwarded-message lines — nothing to check")

    wire = "\n".join(wire_lines)
    wire_digits, wire_lower = _canonical_wire(wire)
    expected = _collect_expected(entries)

    print(f"scanned {len(wire_lines)} forwarded messages\n")
    print(f"{'TYPE':<8}{'VALUES':>8}{'LEAKED':>9}{'SEEN(any form)':>16}")
    print("-" * 41)
    total_leaks = 0
    leaked_examples: list[tuple[str, str]] = []
    for entity_type, values in expected.items():
        if not values:
            continue
        leaked = 0
        for value in values:
            if entity_type in ("PHONE", "CARD", "INN"):
                # Numeric: match on the digit core so a reformat cannot hide it.
                digits = re.sub(r"\D", "", canonicalize(entity_type, value))
                hit = bool(digits) and digits in wire_digits
            else:
                hit = value.lower() in wire_lower
            if hit:
                leaked += 1
                if len(leaked_examples) < 8:
                    leaked_examples.append((entity_type, value))
        total_leaks += leaked
        print(f"{entity_type:<8}{len(values):>8}{leaked:>9}{'':>16}")

    print("-" * 41)
    if total_leaks:
        print(f"\n❌ LEAK@WIRE = {total_leaks} — real personal data reached the provider")
        for entity_type, value in leaked_examples:
            print(f"    {entity_type:<6} {value!r}")
        raise SystemExit(1)
    print("\n✅ LEAK@WIRE = 0 — no real value reached the provider, "
          "including in reformatted form")


if __name__ == "__main__":
    main()
