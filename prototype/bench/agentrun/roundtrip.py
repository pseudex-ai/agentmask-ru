"""Круг: получил ли инструмент НАСТОЯЩИЕ значения. Одно плечо, без сравнения.

WHY THIS AXIS AND NOT THE A/B. The transparency comparison asks whether masking
changed what the model did, and it can only answer that if the model is stable.
It is not: the two arms send DIFFERENT text — masked and raw — so the prompts
tokenise differently and a small model diverges at temperature 0 for reasons
that have nothing to do with us. Measured on 50 real dialogues, the arms agreed
on 64% of call sequences, and the disagreements were the model's.

This axis has no such weakness. It reads ONE arm and asks a question the model
cannot influence: after detokenisation, is there still a token in the arguments?
A leftover means a fake reached the tool — the exact failure the product exists
to prevent — and it is decided by the vault, not by anyone's opinion.

THE VAULT IS READ, NEVER WRITTEN. Copy it out of the container and open it here:
minting a fresh token to compare against would measure this script against
itself, and would also bill the customer for our own evaluation.

    docker cp pseudex:/data/vault.db /tmp/vault.db
    python3 bench/agentrun/roundtrip.py masked.result.jsonl --vault /tmp/vault.db
"""

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pseudex.redact import residual_tokens  # noqa: E402
from pseudex.vault import Vault  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", help="*.result.jsonl маскированного плеча")
    parser.add_argument("--vault", required=True, help="копия vault.db из контейнера")
    parser.add_argument("--org", default="default")
    parser.add_argument("--corpus", default="",
                        help="исходный jsonl: без него всякий остаток считается "
                             "разрывом круга, с ним — только свой")
    parser.add_argument("--dump", type=int, default=20)
    args = parser.parse_args()

    load_dev_bundle()
    vault = Vault(args.vault, args.org)

    # WHOSE FAKE IS IT. A leftover token only means a BROKEN ROUND TRIP if the
    # fake was minted for a value THIS dialogue actually contained. The corpus
    # is a thousand conversations, so the vault holds hundreds of ordinary
    # Russian first names as substitutes — and an 8B model asked not to invent
    # data invents it anyway. «Иван» in a call can therefore be either our fake
    # failing to resolve, or the model making up a name that happens to collide
    # with someone else's substitute.
    #
    # Counting both as breaks understates the product; counting neither hides
    # real ones. So each leftover is traced back through the vault to its real
    # value, and it counts against us only when that real value appears in this
    # dialogue's own text.
    own_text: dict[str, str] = {}
    for line in Path(args.corpus).read_text(encoding="utf-8").splitlines() if args.corpus else []:
        if line.strip():
            rec = json.loads(line)
            own_text[str(rec.get("deal_id"))] = " ".join(
                m.get("text") or "" for s in rec.get("sessions", [])
                for m in s.get("messages", [])).casefold()

    calls = broken = collided = dialogues = failed_dialogues = 0
    by_tool: collections.Counter[str] = collections.Counter()
    examples: list[tuple[str, str, list[str]]] = []

    for line in Path(args.result).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("error"):
            failed_dialogues += 1
            continue
        dialogues += 1
        deal = str(record.get("deal"))
        for call in record.get("calls", []):
            calls += 1
            raw = json.dumps(call.get("arguments", {}), ensure_ascii=False)
            left = residual_tokens(raw, vault)
            if not left:
                continue
            here = own_text.get(deal, "")
            ours = []
            for token in left:
                value, _ = vault.reveal(token)
                # No corpus given, or the dialogue really did contain the value
                # behind this token -> our fake failed to come back.
                if not here or (value and value.casefold() in here):
                    ours.append(token)
            if ours:
                broken += 1
                by_tool[call.get("name", "?")] += 1
                if len(examples) < args.dump:
                    examples.append((deal, call.get("name", "?"), ours[:3]))
            else:
                collided += 1

    if not calls:
        print("вызовов инструментов нет — сравнивать нечего")
        return 1

    print(f"диалогов: {dialogues}   с ошибкой: {failed_dialogues}")
    print(f"вызовов инструментов: {calls}\n")
    print(f"КРУГ: {calls - broken}/{calls} = {(calls - broken) / calls * 100:.1f}% "
          f"вызовов получили настоящие значения")
    if collided:
        print(f"      (ещё {collided} вызовов содержат подмену ДРУГОГО диалога — "
              f"модель выдумала имя, круг тут ни при чём)")
    if broken:
        print(f"\n--- ПОДМЕНА ДОЕХАЛА ДО ИНСТРУМЕНТА ({broken}) ---")
        for tool, count in by_tool.most_common():
            print(f"  {tool}: {count}")
        print()
        for deal, tool, left in examples:
            print(f"  {deal} {tool}: осталось {left}")
    return 0 if not broken else 1


if __name__ == "__main__":
    sys.exit(main())
