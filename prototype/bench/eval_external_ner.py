"""Recall against a Russian NER corpus WE DID NOT WRITE.

Every recall number this project reports so far comes from datasets its own
`make_*.py` scripts generate. That is circular: the data was written by the same
mind as the detector, so it shares its blind spots by construction, and 100% on
it proves only self-consistency. A customer asking "do you catch everything?"
cannot be answered with our own fixtures.

NEREL (github.com/nerel-ds/NEREL) is independent, human-annotated Russian text in
brat format. It is not a PII corpus — it is news — and that mismatch is exactly
what makes it useful here: it contains names, places and dates chosen by someone
with no knowledge of our recognizers.

READ THE BREAKDOWN, NOT THE TOTAL. Two distortions run in opposite directions and
cancelling them into one number would be dishonest:

  * News is full of FOREIGN figures (Барак Обама, Меркель). Our gazetteer and
    surname-suffix rules target Russian personal names, so misses there are
    expected and say little about a Russian support agent's traffic. Reported
    separately from Cyrillic-Russian-shaped names, which ARE our case.
  * CITY/LOCATION recall is expected to be LOW BY DESIGN. `context.location_is_pii`
    deliberately leaves a bare toponym unmasked unless it is tied to a person —
    a city as a landmark is not personal data (the HIPAA/GDPR granularity rule).
    Counting those as misses would penalise a decision we made on purpose.

usage: python3 eval_external_ner.py <NEREL-v1.1 dir> [--splits dev,test] [--limit N]
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from obscura.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# Gold type -> the type our detector would use. Only types we claim to cover.
_TYPE_MAP = {
    "PERSON": "NAME",
    "CITY": "LOC",
    "LOCATION": "LOC",
    "FACILITY": "LOC",
    "DATE": "DATE",
    "AGE": "AGE",
}
# Gold types whose recall is expected to be low BY DESIGN (see module docstring).
_BY_DESIGN_PARTIAL = {"CITY", "LOCATION", "FACILITY"}

_ANN_LINE = re.compile(r"^T\d+\t(\w+) (\d+) (\d+)\t(.*)$")
_CYRILLIC = re.compile(r"^[А-ЯЁа-яё\s.\-]+$")


def _gold_spans(ann_path: Path) -> list[tuple[str, int, int, str]]:
    spans = []
    for line in ann_path.read_text(encoding="utf-8").splitlines():
        match = _ANN_LINE.match(line)
        if match and match.group(1) in _TYPE_MAP:
            spans.append((match.group(1), int(match.group(2)), int(match.group(3)), match.group(4)))
    return spans


def _covered(gold_start: int, gold_end: int, found: list[tuple[int, int, str]], want: str) -> bool:
    """A gold mention counts as caught if a span of the right type OVERLAPS it.

    Overlap rather than exact match on purpose: masking a superset or a subset of
    the mention still removes the identifying token from what the model sees, and
    boundary disagreements between two annotation schemes are not leaks."""
    return any(entity_type == want and start < gold_end and end > gold_start
               for start, end, entity_type in found)


def main() -> None:
    load_dev_bundle()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus")
    parser.add_argument("--splits", default="dev,test")
    parser.add_argument("--limit", type=int, default=0, help="max docs per split (0 = all)")
    args = parser.parse_args()

    detector = Detector()
    detector.detect("прогрев словарей")

    total: dict[str, int] = defaultdict(int)
    caught: dict[str, int] = defaultdict(int)
    ru_total = ru_caught = 0
    misses: list[str] = []
    docs = 0

    for split in args.splits.split(","):
        paths = sorted((Path(args.corpus) / split).glob("*.txt"))
        if args.limit:
            paths = paths[:args.limit]
        for text_path in paths:
            ann_path = text_path.with_suffix(".ann")
            if not ann_path.exists():
                continue
            gold = _gold_spans(ann_path)
            if not gold:
                continue
            text = text_path.read_text(encoding="utf-8")
            found = [(s.start, s.end, s.entity_type) for s in detector.detect(text)]
            docs += 1
            for gold_type, start, end, value in gold:
                want = _TYPE_MAP[gold_type]
                hit = _covered(start, end, found, want)
                total[gold_type] += 1
                caught[gold_type] += hit
                if gold_type == "PERSON":
                    # Split out the population we actually serve: Cyrillic,
                    # Russian-shaped personal names, not transliterated foreign
                    # public figures.
                    if _CYRILLIC.match(value):
                        ru_total += 1
                        ru_caught += hit
                    if not hit and len(misses) < 25:
                        misses.append(value)

    print(f"corpus: {args.corpus}  splits={args.splits}  docs={docs}\n")
    print(f"{'GOLD TYPE':<12}{'MENTIONS':>10}{'CAUGHT':>9}{'RECALL':>9}   note")
    print("-" * 62)
    for gold_type in sorted(total, key=lambda k: -total[k]):
        note = "low BY DESIGN (bare toponym != PII)" if gold_type in _BY_DESIGN_PARTIAL else ""
        rate = caught[gold_type] / total[gold_type]
        print(f"{gold_type:<12}{total[gold_type]:>10}{caught[gold_type]:>9}{rate:>8.1%}   {note}")
    print("-" * 62)
    if ru_total:
        print(f"\nPERSON, Cyrillic-only subset (our actual population): "
              f"{ru_caught}/{ru_total} = {ru_caught / ru_total:.1%}")
    if misses:
        print(f"\nsample PERSON misses: {misses[:20]}")


if __name__ == "__main__":
    main()
