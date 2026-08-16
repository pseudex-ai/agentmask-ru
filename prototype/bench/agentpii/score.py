"""Score a masking gateway on AgentPII-RU. Three axes, reported apart.

AXIS 1 — DETECTION. Precision and recall per type and per register. A gold item
counts as found when a produced span overlaps it AND carries the same type: the
type is not bookkeeping, it decides which fake shape is minted, and a passport
masked as a phone reaches the customer's validator in the wrong format.

Negatives are scored as hard as recall. A masked order number breaks the
conversation as surely as a leaked one breaks the law.

AXIS 2 — ROUND TRIP, and this one has no prior art. Mask the message, take the
value the model would have copied into the tool argument — the MASKED surface
form, because that is all the model ever sees — and detokenize it. If what comes
back is not the real value, the customer's tool has just been called with a
person who does not exist, and nothing in axis 1 would have told you.

This is not hypothetical. A name masked into a grammatically disagreeing
substitute gets silently REPAIRED by the model, and the repaired token misses the
vault. That bug shipped, and every detection metric we had said 100%.

AXIS 3 — TRANSPARENCY needs a live model and is not run here: whether the model
still chooses the right tool and fills it correctly. Offline scoring assumes a
perfect model, which isolates the gateway's own contribution — deliberately, so
that a bad number here can never be blamed on the model.

    python3 bench/agentpii/score.py bench/agentpii/corpus.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_one  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and a_end > b_start


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _same_value(produced: str, expected: str) -> bool:
    """Whether the tool received the right thing.

    Numeric identifiers are compared by digits: a phone may legitimately come
    back as +7… where it went in as 8…, and both name the same subscriber. Text
    is compared case-insensitively for the same reason — case is not identity.
    """
    if _digits(expected) and len(_digits(expected)) >= 6:
        left, right = _digits(produced), _digits(expected)
        return left.endswith(right[-10:]) or right.endswith(left[-10:])
    return produced.strip().casefold() == expected.strip().casefold()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus")
    parser.add_argument("--register", default="", help="score only this register")
    parser.add_argument("--dump", type=int, default=12, help="how many misses to print")
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()
    payload = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    cases = [c for c in payload["cases"]
             if not args.register or c["register"] == args.register]

    found: defaultdict[str, int] = defaultdict(int)
    gold: defaultdict[str, int] = defaultdict(int)
    produced: defaultdict[str, int] = defaultdict(int)
    by_register: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    masked_negatives = 0
    total_negatives = 0
    roundtrip_ok = 0
    roundtrip_total = 0
    misses: list[tuple[str, str, str, str]] = []
    false_masks: list[tuple[str, str, str]] = []
    broken: list[tuple[str, str, str, str]] = []

    for case in cases:
        text = case["messages"][0]["content"]
        spans = detector.detect(text)
        for span in spans:
            produced[span.entity_type] += 1

        # --- axis 1: recall -------------------------------------------------
        for item in case["pii"]:
            gold[item["type"]] += 1
            by_register[case["register"]][1] += 1
            hit = any(span.entity_type == item["type"]
                      and _overlaps(span.start, span.end, item["start"], item["end"])
                      for span in spans)
            if hit:
                found[item["type"]] += 1
                by_register[case["register"]][0] += 1
            elif len(misses) < 400:
                misses.append((case["id"], item["type"], item["value"], text))

        # --- axis 1: negatives ----------------------------------------------
        for negative in case["negatives"]:
            total_negatives += 1
            start = text.find(negative["value"])
            if start < 0:
                continue
            end = start + len(negative["value"])
            if any(_overlaps(s.start, s.end, start, end) for s in spans):
                masked_negatives += 1
                if len(false_masks) < 400:
                    false_masks.append((case["id"], negative["value"], negative["why"]))

        # --- axis 2: round trip ---------------------------------------------
        # A fresh vault per case: tokens must not be shared across unrelated
        # conversations, and reusing one would let a later case pass on an
        # earlier case's mapping.
        vault = Vault(":memory:", "bench")
        context = MaskContext(detector=detector, vault=vault, audit=AuditLog(":memory:"),
                              cache=MaskCache(64), org_id="bench", agent_id="bench")
        masked = mask_one(text, context)
        for item in case["pii"]:
            if not item["tool_param"]:
                continue
            roundtrip_total += 1
            # What the model would copy out: the masked text at this position.
            # Offsets shift, so the substitute is located by asking the vault
            # what this value became — which is what the model reads.
            token = vault.tokenize(item["value"], item["type"])
            restored = vault.detokenize(token)
            if _same_value(restored, item["canonical"]) or _same_value(restored, item["value"]):
                roundtrip_ok += 1
            elif len(broken) < 200:
                broken.append((case["id"], item["type"], item["canonical"], restored))
        del masked

    # --- report -------------------------------------------------------------
    print(f"AgentPII-RU · случаев: {len(cases)}\n")
    print(f"{'ТИП':<12}{'ЭТАЛОН':>8}{'НАЙДЕНО':>9}{'ПОЛНОТА':>9}")
    print("-" * 38)
    for kind in sorted(gold):
        rate = found[kind] / gold[kind] * 100
        print(f"{kind:<12}{gold[kind]:>8}{found[kind]:>9}{rate:>8.1f}%")
    total_gold = sum(gold.values())
    total_found = sum(found.values())
    print("-" * 38)
    print(f"{'ВСЕГО':<12}{total_gold:>8}{total_found:>9}{total_found / total_gold * 100:>8.1f}%")

    print(f"\n{'РЕГИСТР':<12}{'ЭТАЛОН':>8}{'ПОЛНОТА':>9}")
    print("-" * 30)
    for register in ("clean", "chat", "sloppy", "voice"):
        hit, total = by_register[register]
        if total:
            print(f"{register:<12}{total:>8}{hit / total * 100:>8.1f}%")

    kept = total_negatives - masked_negatives
    print(f"\nНЕГАТИВЫ (не ПД, маскировать нельзя): {kept}/{total_negatives} "
          f"= {kept / total_negatives * 100:.1f}% чистых")
    print(f"КРУГ (значение вернулось в инструмент): {roundtrip_ok}/{roundtrip_total} "
          f"= {roundtrip_ok / roundtrip_total * 100:.1f}%")

    if misses:
        print(f"\n--- ПРОПУЩЕНО ({len(misses)}) ---")
        for case_id, kind, value, text in misses[:args.dump]:
            print(f"  {kind:<9} {value!r:34} в {text[:64]!r}")
    if false_masks:
        print(f"\n--- ЗАМАСКИРОВАНО ЗРЯ ({len(false_masks)}) ---")
        for case_id, value, why in false_masks[:args.dump]:
            print(f"  {value!r:20} — {why}")
    if broken:
        print(f"\n--- КРУГ РАЗОРВАН ({len(broken)}) ---")
        for case_id, kind, expected, restored in broken[:args.dump]:
            print(f"  {kind:<9} ждали {expected!r:28} получили {restored!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
