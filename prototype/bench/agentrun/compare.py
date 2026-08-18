"""Сравнение двух плеч: сломало ли маскирование поведение модели.

THE DEFECT IS A CHANGED VALUE, not a changed sentence. Two runs of the same
model at temperature 0 still differ in wording sometimes, and a gateway is not
responsible for that. What it IS responsible for:

  * a tool called in one arm and not the other,
  * a tool called with a DIFFERENT value — a name, a phone, an address, a date,
  * an answer to the customer naming a different person or place.

So the comparison is done on VALUES pulled out of both texts, not on the strings.
The masked arm has already been detokenized by the gateway on its way back, so
if the gateway is transparent the two sets are equal.

    python3 bench/agentrun/compare.py masked.result.jsonl direct.result.jsonl
"""

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pseudex.detect_all import Detector  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402


def values(detector: Detector, text: str) -> set[tuple[str, str]]:
    return {(s.entity_type, s.value.casefold()) for s in detector.detect(text or "")}


def load(path: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            out[str(record.get("deal"))] = record
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("masked")
    parser.add_argument("direct")
    parser.add_argument("--dump", type=int, default=15)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()
    left, right = load(args.masked), load(args.direct)
    shared = sorted(set(left) & set(right))

    same_calls = same_values = 0
    call_diffs: list[tuple[str, list[str], list[str]]] = []
    value_diffs: list[tuple[str, set, set]] = []
    errors = collections.Counter()

    for deal in shared:
        a, b = left[deal], right[deal]
        if "error" in a or "error" in b:
            errors["маскированное" if "error" in a else "прямое"] += 1
            continue
        names_a = [c["name"] for c in a.get("calls", [])]
        names_b = [c["name"] for c in b.get("calls", [])]
        if names_a == names_b:
            same_calls += 1
        else:
            call_diffs.append((deal, names_a, names_b))
        # ARGUMENTS AND ANSWERS TOGETHER: a tool called with the right name and
        # the wrong customer is the failure this product exists to prevent.
        text_a = json.dumps(a.get("calls", []), ensure_ascii=False) + " " + " ".join(a.get("answers", []))
        text_b = json.dumps(b.get("calls", []), ensure_ascii=False) + " " + " ".join(b.get("answers", []))
        va, vb = values(detector, text_a), values(detector, text_b)
        if va == vb:
            same_values += 1
        else:
            value_diffs.append((deal, va - vb, vb - va))

    total = len(shared) - sum(errors.values())
    if not total:
        print("нечего сравнивать")
        return 1
    print(f"диалогов в обоих плечах: {len(shared)}   с ошибкой: {dict(errors)}\n")
    print(f"та же последовательность вызовов: {same_calls}/{total} = {same_calls/total*100:.1f}%")
    print(f"те же значения в вызовах и ответах: {same_values}/{total} = {same_values/total*100:.1f}%")

    if call_diffs:
        print(f"\n--- РАЗНЫЕ ВЫЗОВЫ ({len(call_diffs)}) ---")
        for deal, a, b in call_diffs[:args.dump]:
            print(f"  {deal}: маск={a} прям={b}")
    if value_diffs:
        print(f"\n--- РАЗНЫЕ ЗНАЧЕНИЯ ({len(value_diffs)}) ---")
        for deal, only_masked, only_direct in value_diffs[:args.dump]:
            print(f"  {deal}: только в маскированном={sorted(only_masked)[:3]} "
                  f"только в прямом={sorted(only_direct)[:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
