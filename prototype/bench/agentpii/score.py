"""Score a masking gateway on AgentPII-RU. Three axes, reported apart.

AXIS 1 — DETECTION. Precision and recall per type and per register. A gold item
counts as found when a produced span overlaps it AND carries the same type: the
type is not bookkeeping, it decides which fake shape is minted, and a passport
masked as a phone reaches the customer's validator in the wrong format.

Reported beside it is COVERAGE — the share of gold items whose span was found
WHOLE. An overlap is what a detector needs to be credited with finding something;
coverage is what the customer needs, because the uncovered tail went to the model
in the clear. «Кзнецов Дмитрий» detected as «Дмитрий» scores as recall and leaks
a surname, so the two numbers are printed together and never merged.

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


def _names_one_person(tokens: set[str]) -> bool:
    """Whether every substitute for this identity names the SAME fake person.

    Not byte equality — that would be the wrong test. A message that says
    «Иванов Пётр Сергеевич» once and «Петру» later is one person mentioned two
    ways, and the substitute has to follow BOTH rules: same identity, and a
    one-word mention still gets one word. So «Юдин Никита Петрович» and «Никита»
    are consistent, and it is the shorter form being a PART of the longer that
    says so.

    Two substitutes sharing no word at all are a genuine split, and that is what
    this counts.
    """
    if len(tokens) <= 1:
        return True
    ordered = sorted(tokens, key=lambda token: -len(token.split()))
    longest = {word.casefold() for word in ordered[0].split()}
    return all({word.casefold() for word in token.split()} <= longest
               for token in ordered[1:])



# WHY THE BREAKS ARE CLASSIFIED AND NOT FORGIVEN.
#
# «Иванoв Пётр» with a Latin o comes back «Иванов Пётр»; «ИвановПётр» comes back
# «Иванов Пётр». Both differ from what was written, so the strict test calls
# them broken — and both are the product doing exactly what it is built to do:
# normalisation folds a look-alike, `_glued_names` restores a missed space, and
# what reaches the customer's CRM is the form that will actually match a record
# there. Twenty of sixty-four breaks are these.
#
# The temptation is to accept them, and that is the move this file must never
# make: a scorer that forgives a shape stops seeing the real defect wearing it.
# «позвоните Игорю» resolving to «Игорю» has the same shape as a repair and is a
# declined name written into a CRM. So КРУГ stays strict, to the character, and
# the classes are printed BESIDE it — the reader gets both the number and what
# it is made of, and neither is quietly adjusted to look better.
# The seven Latin letters with a Cyrillic twin. Lower case only, because the
# comparison casefolds first, and no duplicates — a repeated key silently
# changes the mapping.
_LOOKALIKE = str.maketrans("acepoxy", "асероху")


def _classify(expected: str, restored: str | None) -> str:
    if restored is None:
        return "токен не нашёлся"
    if restored.replace(" ", "") == expected.replace(" ", ""):
        return "починен пробел"
    if restored.lower().translate(_LOOKALIKE) == expected.lower().translate(_LOOKALIKE):
        return "починена латиница"
    if expected.startswith(restored) or restored.startswith(expected):
        return "вернулась часть"
    return "форма изменена"


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
    fully_covered = 0
    partial: list[tuple[str, str, str, int]] = []
    total_negatives = 0
    roundtrip_ok = 0
    roundtrip_total = 0
    consistency_ok = 0
    consistency_total = 0
    inconsistent: list[tuple[str, str, list[str]]] = []
    collisions: list[tuple[str, str, str, str]] = []
    misses: list[tuple[str, str, str, str]] = []
    false_masks: list[tuple[str, str, str]] = []
    broken: list[tuple[str, str, str, str]] = []
    broken_kinds: dict[str, int] = {}

    for case in cases:
        turns = [m["content"] for m in case["messages"] if m["role"] == "user"]
        # EVERY user turn is detected, not just the first. Recall used to be
        # measured on turn 0 alone, which meant a value leaked in the second
        # message of a dialogue was invisible to the benchmark — and the second
        # message is exactly where a customer refers back to somebody, in the
        # shortened and lower-case forms that are hardest to catch.
        per_turn = [detector.detect(turn) for turn in turns]
        for spans in per_turn:
            for span in spans:
                produced[span.entity_type] += 1

        # --- axis 4: consistency --------------------------------------------
        # One vault for the WHOLE dialogue, because that is what a conversation
        # has. Items sharing an identity must receive the same substitute, items
        # with different identities must not — «один человек, один токен» is the
        # product's own claim and no other axis touches it.
        by_identity: defaultdict[str, set[str]] = defaultdict(set)
        dialogue_vault = Vault(":memory:", "bench")
        for item in case["pii"]:
            if not item.get("identity"):
                continue
            token = dialogue_vault.tokenize(item["value"], item["type"])
            by_identity[item["identity"]].add(token)
        for identity, tokens in by_identity.items():
            consistency_total += 1
            if _names_one_person(tokens):
                consistency_ok += 1
            else:
                inconsistent.append((case["id"], identity, sorted(tokens)))
        # Different identities of the SAME TYPE must not collide.
        minted = [(identity, next(iter(tokens))) for identity, tokens in by_identity.items()]
        for i in range(len(minted)):
            for j in range(i + 1, len(minted)):
                if minted[i][1] == minted[j][1]:
                    collisions.append((case["id"], minted[i][0], minted[j][0], minted[i][1]))

        # --- axis 1: recall -------------------------------------------------
        for item in case["pii"]:
            turn_index = item.get("turn", 0)
            spans = per_turn[turn_index]
            gold[item["type"]] += 1
            by_register[case["register"]][1] += 1
            hit = any(span.entity_type == item["type"]
                      and _overlaps(span.start, span.end, item["start"], item["end"])
                      for span in spans)
            # AN OVERLAP IS NOT COVERAGE, and the difference is a leak. «Кзнецов
            # Дмитрий» with a typo in the surname is detected as «Дмитрий»: the
            # overlap rule scores it found, and the surname goes to the model in
            # the clear. Reported apart rather than replacing recall — the two
            # answer different questions, and collapsing them would hide which
            # of the two a change moved.
            covered = set()
            for span in spans:
                if span.entity_type != item["type"]:
                    continue
                for position in range(max(span.start, item["start"]),
                                      min(span.end, item["end"])):
                    covered.add(position)
            if len(covered) == item["end"] - item["start"]:
                fully_covered += 1
            elif hit and len(partial) < 400:
                partial.append((case["id"], item["type"], item["value"],
                                item["end"] - item["start"] - len(covered)))
            if hit:
                found[item["type"]] += 1
                by_register[case["register"]][0] += 1
            elif len(misses) < 400:
                misses.append((case["id"], item["type"], item["value"],
                               turns[turn_index]))

        # --- axis 1: negatives ----------------------------------------------
        for negative in case["negatives"]:
            total_negatives += 1
            for turn_index, turn in enumerate(turns):
                start = turn.find(negative["value"])
                if start < 0:
                    continue
                end = start + len(negative["value"])
                if any(_overlaps(s.start, s.end, start, end)
                       for s in per_turn[turn_index]):
                    masked_negatives += 1
                    if len(false_masks) < 400:
                        false_masks.append((case["id"], negative["value"],
                                            negative["why"]))
                break

        # --- axis 2: round trip ---------------------------------------------
        # A fresh vault per case: tokens must not be shared across unrelated
        # conversations, and reusing one would let a later case pass on an
        # earlier case's mapping.
        vault = Vault(":memory:", "bench")
        context = MaskContext(detector=detector, vault=vault, audit=AuditLog(":memory:"),
                              cache=MaskCache(64), org_id="bench", agent_id="bench", conversation_id="")
        # Masked IN ORDER, sharing one vault, because that is what a conversation
        # is: the substitute a later turn gets depends on what the earlier turns
        # already put in the vault.
        masked = [mask_one(turn, context) for turn in turns]
        for item in case["pii"]:
            if not item["tool_param"]:
                continue
            # THE VALUE AS DETECTION SAW IT, not as the corpus wrote it. Masking
            # runs on normalised text, so the span carries «8-903-…» where the
            # message carried a Cyrillic О — and handing the raw surface straight
            # to the vault measured a path production never takes. It reported
            # ~180 phone breaks that do not exist: through `mask_one` the same
            # numbers come back dialable.
            turn_index = item.get("turn", 0)
            span = next((s for s in per_turn[turn_index]
                         if s.entity_type == item["type"]
                         and _overlaps(s.start, s.end, item["start"], item["end"])), None)
            if span is None:
                # Undetected, which the recall axis already counts. Counting it
                # again here would make one defect move two numbers and leave a
                # reader unable to tell how many there were.
                continue
            roundtrip_total += 1
            # READ-ONLY: the token was minted by the masking above, and this axis
            # asks whether THAT token resolves — not whether a freshly minted one
            # would.
            token = vault.peek_token(span.value, span.entity_type)
            restored = vault.detokenize(token) if token else None
            # THE CANONICAL, AND ONLY IT. Accepting the surface form as well used
            # to paper over the ground truth being wrong — and it also passed the
            # one thing this axis exists to catch: «позвоните Игорю» resolving to
            # «Игорю» puts a declined name in the customer's CRM, which is a
            # wrong tool call however recognisable it looks to a human reader.
            if _same_value(restored, item["canonical"]):
                roundtrip_ok += 1
            elif len(broken) < 200:
                broken.append((case["id"], item["type"], item["canonical"], restored))
            if not _same_value(restored, item["canonical"]):
                kind = _classify(item["canonical"], restored)
                broken_kinds[kind] = broken_kinds.get(kind, 0) + 1
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
    print(f"{'ПОКРЫТО':<12}{total_gold:>8}{fully_covered:>9}"
          f"{fully_covered / total_gold * 100:>8.1f}%   "
          f"(спан найден ЦЕЛИКОМ; разница с полнотой — утёкшие хвосты)")

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
    if consistency_total:
        print(f"СОГЛАСОВАННОСТЬ (один человек — один псевдоним): "
              f"{consistency_ok}/{consistency_total} "
              f"= {consistency_ok / consistency_total * 100:.1f}%   "
              f"столкновений разных людей: {len(collisions)}")

    if misses:
        print(f"\n--- ПРОПУЩЕНО ({len(misses)}) ---")
        for case_id, kind, value, text in misses[:args.dump]:
            print(f"  {kind:<9} {value!r:34} в {text[:64]!r}")
    if partial:
        print(f"\n--- НАЙДЕНО ЧАСТИЧНО, ОСТАЛЬНОЕ УТЕКЛО ({len(partial)}) ---")
        for case_id, kind, value, lost in partial[:args.dump]:
            print(f"  {kind:<9} {value!r:34} не покрыто символов: {lost}")
    if false_masks:
        print(f"\n--- ЗАМАСКИРОВАНО ЗРЯ ({len(false_masks)}) ---")
        for case_id, value, why in false_masks[:args.dump]:
            print(f"  {value!r:20} — {why}")
    if inconsistent:
        print(f"\n--- ОДИН ЧЕЛОВЕК, РАЗНЫЕ ПСЕВДОНИМЫ ({len(inconsistent)}) ---")
        for case_id, identity, tokens in inconsistent[:args.dump]:
            print(f"  {identity:14} -> {tokens}")
    if collisions:
        print(f"\n--- РАЗНЫЕ ЛЮДИ, ОДИН ПСЕВДОНИМ ({len(collisions)}) ---")
        for case_id, a, b, token in collisions[:args.dump]:
            print(f"  {a} и {b} оба -> {token!r}")
    if broken_kinds:
        print("   из них: " + ", ".join(
            f"{name} {count}" for name, count
            in sorted(broken_kinds.items(), key=lambda pair: -pair[1])))
    if broken:
        print(f"\n--- КРУГ РАЗОРВАН ({len(broken)}) ---")
        for case_id, kind, expected, restored in broken[:args.dump]:
            print(f"  {kind:<9} ждали {expected!r:28} получили {restored!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
