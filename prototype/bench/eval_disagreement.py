"""Что находит НЕЗАВИСИМАЯ линия и не находим мы, на настоящем трафике.

WHY THIS EXISTS. Real production dialogues have no labels, and using our own
detector as the ground truth measures self-consistency and nothing else — it
returns 100% by construction. Labelling seven thousand messages by hand is not
a plan either.

So: run a detector that errs DIFFERENTLY — bare Natasha plus naive regexes, with
none of our leased vocabulary — and look only at where the two disagree. What it
finds and we do not is a candidate miss; the list is a hundred lines instead of
seven thousand, and every line is already worth a human's attention.

The output is grouped BY SHAPE, not printed raw: this runs on real customers'
data, and a work list does not need their values to be readable to be actionable.

    python3 bench/eval_disagreement.py <dialogues.jsonl> [--dump 40]
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench._baseline_independent import spans as baseline_spans  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

_DIGIT = re.compile(r"\d")


def shape_of(value: str) -> str:
    """A class a person can act on, without reading anybody's data."""
    words = value.split()
    if _DIGIT.search(value) and not any(ch.isalpha() for ch in value):
        return f"{len(_DIGIT.findall(value))} цифр"
    if "@" in value:
        return "почта"
    if len(words) == 1:
        low = value.lower()
        if value.isupper():
            return "одно слово ЗАГЛАВНЫМИ"
        if value[:1].isupper():
            return "одно слово с заглавной"
        return "одно слово строчными"
    return f"{len(words)} слова" + (" строчными" if value.islower() else "")


def preview(value: str) -> str:
    return value if len(value) <= 3 else value[:2] + "•" * (len(value) - 3) + value[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--dump", type=int, default=40)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()

    only_baseline: collections.Counter[tuple[str, str]] = collections.Counter()
    only_ours: collections.Counter[tuple[str, str]] = collections.Counter()
    samples: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    messages = 0

    for line in Path(args.corpus).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for session in record.get("sessions", []):
            for message in session.get("messages", []):
                text = (message.get("text") or "").strip()
                if not text:
                    continue
                messages += 1
                ours = [(s.entity_type, s.start, s.end) for s in detector.detect(text)]
                theirs = baseline_spans(text)
                for kind, start, end, value in theirs:
                    if kind == "ORG":
                        continue          # we do not claim organisations
                    if any(s < end and e > start for _k, s, e in ours):
                        continue
                    key = (kind, shape_of(value))
                    only_baseline[key] += 1
                    if len(samples[key]) < 3:
                        samples[key].append(preview(value))
                for kind, start, end in ours:
                    if any(s < end and e > start for _k, s, e, _v in theirs):
                        continue
                    only_ours[(kind, shape_of(text[start:end]))] += 1

    print(f"сообщений: {messages}")
    print(f"нашла только независимая линия: {sum(only_baseline.values())}")
    print(f"нашли только мы:                {sum(only_ours.values())}\n")
    print(f"--- КАНДИДАТЫ В ПРОПУСКИ (нашли они, не нашли мы) ---")
    for (kind, shape), count in only_baseline.most_common(args.dump):
        print(f"  {count:>4}x {kind:<7} {shape:<26} например: {', '.join(samples[(kind, shape)])}")
    print(f"\n--- НАШЛИ ТОЛЬКО МЫ (может быть и правотой, и перемаскированием) ---")
    for (kind, shape), count in only_ours.most_common(15):
        print(f"  {count:>4}x {kind:<7} {shape}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
