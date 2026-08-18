"""Перемаскирование на ОБЪЁМЕ чужого текста.

WHY THIS EXISTS, and it is the same reason `test_overmasking.py` exists one
level down. That file holds 27 sentences written by us, and it read 100% for
months while «Счёт 1234 от 15.05.2025» — one of the commonest sentences in
Russian business writing — was being masked. A corpus we wrote cannot surprise
us; that is the whole problem with it.

This one runs over text somebody else wrote, on topics chosen so that personal
data is rare: accounting, logistics, protocols, car maintenance. There are no
labels, so the number here is not precision — it is a SUSPECT RATE, and the
value of the run is the ranked list underneath it. A real name in a Wikipedia
article about a standard should be masked; «Счёт», «Договор» and «Клиент»
should not, and those are the ones this surfaces.

    python3 bench/eval_overmasking_volume.py <corpus.jsonl> [--dump 40]

The corpus is NOT in the repository: it is fetched text, it is large, and it
changes. `scratchpad/corpora/fetch.py` builds it.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--dump", type=int, default=30)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()

    lines = [json.loads(line) for line in
             Path(args.corpus).read_text(encoding="utf-8").splitlines() if line.strip()]
    by_type: Counter[str] = Counter()
    values: defaultdict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, str] = {}
    touched = 0

    for record in lines:
        text = record["text"]
        spans = detector.detect(text)
        if spans:
            touched += 1
        for span in spans:
            by_type[span.entity_type] += 1
            surface = text[span.start:span.end]
            values[span.entity_type][surface] += 1
            examples.setdefault(f"{span.entity_type}\t{surface}", text)

    print(f"предложений: {len(lines)}   затронуто: {touched} "
          f"({touched / max(1, len(lines)) * 100:.1f}%)")
    print(f"срабатываний: {sum(by_type.values())}\n")
    print(f"{'ТИП':<12}{'СРАБОТАЛО':>10}")
    print("-" * 22)
    for kind, count in by_type.most_common():
        print(f"{kind:<12}{count:>10}")

    print(f"\n--- ЧАЩЕ ВСЕГО (подозреваемые, {args.dump}) ---")
    ranked = [(count, kind, value)
              for kind, counter in values.items()
              for value, count in counter.items()]
    for count, kind, value in sorted(ranked, reverse=True)[:args.dump]:
        context = examples[f"{kind}\t{value}"]
        cut = context.find(value)
        window = context[max(0, cut - 34):cut + len(value) + 34].replace("\n", " ")
        print(f"  {count:>3}x {kind:<9} {value!r:32} … {window} …")
    return 0


if __name__ == "__main__":
    sys.exit(main())
