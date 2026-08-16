"""Precision against a corpus WE DID NOT WRITE — the other half of the bench.

`eval_external_ner.py` answers "do we find real names in real text". This answers
the question that costs the customer their work rather than their privacy: how
much do we mask that a human annotator did not think was an entity at all?

A span of ours that overlaps NO gold annotation of any kind is a candidate false
positive. "Candidate" is honest — NEREL annotates 29 types chosen for information
extraction, not for privacy, so a few genuine PII values may be unlabelled. The
number is therefore a LOWER bound on precision, and the dump below is what makes
it useful: read the actual strings, not the percentage.

usage: python3 bench/eval_external_precision.py <NEREL dir> [--limit N]
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402


def _gold_spans(ann_path: Path) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for line in ann_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("T"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        head = parts[1].split()
        if len(head) < 3:
            continue
        try:
            spans.append((int(head[1]), int(head[-1])))
        except ValueError:
            continue
    return spans


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()

    files = sorted(Path(args.corpus).rglob("*.ann"))
    if args.limit:
        files = files[: args.limit]

    total = 0
    unsupported = 0
    by_type: Counter[str] = Counter()
    samples: list[tuple[str, str, str]] = []

    for ann in files:
        txt = ann.with_suffix(".txt")
        if not txt.exists():
            continue
        text = txt.read_text(encoding="utf-8")
        gold = _gold_spans(ann)
        for span in detector.detect(text):
            total += 1
            overlaps = any(g0 < span.end and g1 > span.start for g0, g1 in gold)
            if overlaps:
                continue
            unsupported += 1
            by_type[span.entity_type] += 1
            if len(samples) < 40:
                snippet = text[max(0, span.start - 35): span.end + 35].replace("\n", " ")
                samples.append((span.entity_type, span.value, snippet))

    supported = total - unsupported
    print(f"документов: {len(files)}   спанов выдано: {total}")
    print(f"подтверждено разметкой: {supported}   без опоры в разметке: {unsupported}")
    if total:
        print(f"ТОЧНОСТЬ (нижняя оценка): {supported / total * 100:.1f}%\n")
    print("без опоры, по типам:")
    for entity_type, count in by_type.most_common():
        print(f"  {entity_type:14} {count:5}")
    print("\n--- примеры (читать глазами, это не все ошибки) ---")
    for entity_type, value, snippet in samples[:25]:
        print(f"  {entity_type:12} {value!r:32} … {snippet.strip()[:70]} …")
    return 0


if __name__ == "__main__":
    sys.exit(main())
