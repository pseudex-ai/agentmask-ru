"""Put Russian personal data into BFCL tasks, so the paired run actually
measures masking instead of measuring a network hop.

WHY: BFCL ships English tasks about file systems and trading bots. Running them
through Veilgate fired the detector 6 times in a whole 29-task run — so Δ was
dominated by proxy overhead and said nothing about whether masking breaks agents.
Contact data goes into every task; identifier substitution targets the 50
TravelAPI entries, whose state carries a cardholder name, a card number and a
card id that the ground-truth tool calls pass BY VALUE. Those are the ones where
injected data has to survive the round trip or the task provably fails.

TWO KINDS OF INJECTION, deliberately different:

  1. IDENTIFIERS THAT MUST ROUND-TRIP — cardholder name, card number, card id.
     Substituted CONSISTENTLY across question + initial_config + possible_answer
     by literal string replacement over the serialized JSON, so the ground truth
     stays valid and the task stays solvable. If masking corrupts one of these,
     the tool is called with the wrong value and BFCL's state checker fails the
     entry. That is exactly the signal we want.

  2. CONTACT DATA THAT MUST NOT LEAK — a phone and a street address appended to
     the first user turn. No tool consumes them, so the ground truth is untouched
     and task success cannot change because of them. Their job is to guarantee
     every single request carries real PII on the wire, which makes leak@wire
     measurable and exposes over-masking damage if the detector misfires.

Values are chosen so our own recognizers actually fire: the card passes Luhn, the
card id is a checksum-valid ИНН, names are gazetteer/NER-visible, and the address
is marker-bearing. Generating them with the production validators (rather than
hand-writing digits) is what keeps that true.

usage: python3 inject_ru_pii.py <bfcl_data_dir> [--restore]
"""

import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veilgate.ru_pii import validate_inn, validate_luhn  # noqa: E402

_DATA_FILE = "BFCL_v4_multi_turn_base.json"
_ANSWER_SUBDIR = "possible_answer"

_FIRST = ["Иван", "Сергей", "Дмитрий", "Анна", "Мария", "Ольга", "Павел", "Елена"]
_LAST = ["Петров", "Смирнов", "Кузнецов", "Соколова", "Волкова", "Морозов"]
_STREETS = ["улица Ленина 5, кв 12", "проспект Мира 17 к2, кв 45",
            "улица Гагарина 8, кв 3", "Красный проспект 24, кв 91"]


def _luhn_card(rng: random.Random) -> str:
    """A 16-digit card that PASSES Luhn — our CARD recognizer is checksum-gated,
    so a random number would simply never be detected and the test would be
    vacuous."""
    while True:
        body = "4" + "".join(rng.choice("0123456789") for _ in range(15))
        if validate_luhn(body):
            return f"{body[:4]} {body[4:8]} {body[8:12]} {body[12:]}"


def _valid_inn(rng: random.Random) -> str:
    """A 12-digit ИНН with both check digits correct, for the same reason."""
    while True:
        candidate = "".join(rng.choice("0123456789") for _ in range(12))
        if validate_inn(candidate):
            return candidate


def _phone(rng: random.Random) -> str:
    return f"+7 9{rng.randint(10, 99)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"


def _substitutions(entry: dict, rng: random.Random) -> dict[str, str]:
    """Map every English identity string in this entry to a Russian one. Keys are
    replaced longest-first by the caller so that a full name is rewritten before
    its own first name can be matched separately."""
    travel = entry["initial_config"].get("TravelAPI", {})
    mapping: dict[str, str] = {}
    first, last = rng.choice(_FIRST), rng.choice(_LAST)

    old_first = travel.get("user_first_name")
    old_last = travel.get("user_last_name")
    if isinstance(old_first, str) and isinstance(old_last, str):
        mapping[f"{old_first} {old_last}"] = f"{first} {last}"
        mapping[old_first] = first
        mapping[old_last] = last

    for card_id, card in travel.get("credit_card_list", {}).items():
        mapping[card_id] = _valid_inn(rng)
        if isinstance(card, dict) and isinstance(card.get("card_number"), str):
            mapping[card["card_number"]] = _luhn_card(rng).replace(" ", "")
        if isinstance(card, dict) and isinstance(card.get("cardholder_name"), str):
            mapping.setdefault(card["cardholder_name"], f"{first} {last}")
    return mapping


def _apply(payload: dict, mapping: dict[str, str]) -> dict:
    """Literal substitution over the serialized entry. Serializing first is what
    guarantees the SAME replacement lands in the question, the seed state and the
    ground truth — patching them separately is how ground truth silently drifts
    out of sync with the task."""
    text = json.dumps(payload, ensure_ascii=False)
    for old in sorted(mapping, key=len, reverse=True):
        text = text.replace(old, mapping[old])
    return json.loads(text)


def _append_contact(entry: dict, rng: random.Random) -> None:
    """Add contact PII to the first user turn. No tool reads it, so the ground
    truth is untouched and task success cannot move because of it — it exists so
    that EVERY request carries real PII on the wire."""
    first_turn = entry["question"][0]
    for message in first_turn:
        if message.get("role") == "user":
            message["content"] = (
                f"{message['content']} Мои контакты на всякий случай: "
                f"телефон {_phone(rng)}, адрес {rng.choice(_STREETS)}."
            )
            return


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    data_dir = Path(sys.argv[1])
    data_path = data_dir / _DATA_FILE
    answer_path = data_dir / _ANSWER_SUBDIR / _DATA_FILE
    backups = [Path(f"{p}.orig") for p in (data_path, answer_path)]

    if "--restore" in sys.argv:
        for path, backup in zip((data_path, answer_path), backups):
            if not backup.exists():
                raise SystemExit(f"no backup to restore: {backup}")
            shutil.copy(backup, path)
        print("restored pristine BFCL data")
        return

    for path, backup in zip((data_path, answer_path), backups):
        if not backup.exists():
            shutil.copy(path, backup)

    entries = [json.loads(line) for line in backups[0].read_text().splitlines() if line.strip()]
    answers = [json.loads(line) for line in backups[1].read_text().splitlines() if line.strip()]
    answer_by_id = {a["id"]: a for a in answers}

    patched = identifiers = 0
    for entry in entries:
        # Seed per entry id so a re-run reproduces byte-identical data — the two
        # arms must see the SAME task or the comparison is not paired.
        rng = random.Random(entry["id"])
        # Contact data goes into EVERY task. No tool reads it, so no ground truth
        # moves, and it guarantees each request carries real PII on the wire —
        # which is what makes leak@wire measurable across the whole run rather
        # than only on the tasks that happen to pass identifiers around.
        _append_contact(entry, rng)
        patched += 1
        # Identifier substitution only where the backend actually carries them
        # through tool calls, because it has to stay consistent with the answer.
        if "TravelAPI" not in entry.get("involved_classes", []):
            continue
        mapping = _substitutions(entry, rng)
        if not mapping:
            continue
        entry.update(_apply(entry, mapping))
        answer = answer_by_id.get(entry["id"])
        if answer is not None:
            answer.update(_apply(answer, mapping))
        identifiers += 1

    with data_path.open("w") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    with answer_path.open("w") as handle:
        for answer in answers:
            handle.write(json.dumps(answer, ensure_ascii=False) + "\n")

    print(f"contact PII injected into {patched} entries; "
          f"identifiers substituted in {identifiers} TravelAPI entries; "
          f"originals kept as *.orig")


if __name__ == "__main__":
    main()
