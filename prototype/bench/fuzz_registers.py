"""Every way one value can be written, mechanically.

WHY THIS EXISTS. The last six defects in this engine were found by building a
table of «the same inputs × writing styles» BY HAND, in ten minutes — glued
names, glued street types, capitalisation splitting a person, ё/е splitting a
person, a lower-case address losing its street, an order number swallowed by an
address. Three persona runs had not found any of them, because a persona has to
be LUCKY: they write what occurs to them.

A machine does not need luck. The transformations below are properties of
Russian writing, not of our detector — case, ё, a missed space, a keyboard that
slipped into Latin, a separator, an oblique case, a word order, a JSON field.
That independence is the same rule `make_stress.py` states: authored from the
DOMAIN, never from what we currently find.

TWO AXES, and they fail separately:

  * DETECTION — is the value found at all, with the right type. A miss is a
    leak, and it is the axis a persona can also see.
  * INDEX — do all the writings of ONE value collapse to ONE substitute. This is
    the axis nothing else measures: masking can be perfect while the model meets
    nine different people, which is precisely what the landing page promises not
    to do.

    python3 bench/fuzz_registers.py [--dump 25]
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pseudex.detect_all import Detector  # noqa: E402
from pseudex.vault import Vault  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# (type, value, frame) — the frame is ordinary traffic around the value, because
# a detector that only works on a bare value is not a gateway.
# A TRANSFORMATION MUST NOT INVALIDATE THE VALUE. Dropping a digit from a СНИЛС
# breaks its checksum, and refusing a broken checksum is CORRECT — a fuzzer that
# counts that as a miss reports the product's own safety rule as a defect. The
# first version of this file did exactly that and cried wolf forty times; it is
# the same failure as a scorer whose fallback forgives the thing it measures.
#
# So the shape-changing transformations are applied ONLY to text-shaped values,
# and the checksummed identifiers get separator and case changes, which a human
# also makes and which leave the number itself intact.
_CHECKSUMMED = frozenset({"SNILS", "INN", "CARD", "PASSPORT", "ACCOUNT", "PLATE"})

# How each document is actually written on the form it comes from.
_GROUPING = {
    "SNILS": lambda d: f"{d[:3]} {d[3:6]} {d[6:9]} {d[9:]}",
    "CARD": lambda d: " ".join(d[i:i + 4] for i in range(0, len(d), 4)),
    "PASSPORT": lambda d: f"{d[:4]} {d[4:]}",
}

# Keys that TYPE the value, for the JSON frame. A field called «field» types
# nothing, so wrapping in it measured the wrapper rather than the detector.
_JSON_KEY = {
    "NAME": "name", "LOC": "address", "PHONE": "phone", "EMAIL": "email",
    "SNILS": "snils", "INN": "inn", "CARD": "card", "PASSPORT": "passport",
    "PLATE": "car_number", "ACCOUNT": "account",
}

SEEDS: tuple[tuple[str, str, str], ...] = (
    ("NAME", "Гончарова Анна Дмитриевна", "клиент {}, оформите заказ"),
    ("NAME", "Соколов Игорь Валентинович", "запишите {} на приём"),
    ("NAME", "Мамедова Лейла", "передайте {} документы"),
    ("NAME", "Ким Виктор", "свяжитесь с {} завтра"),
    ("LOC", "Москва, Ленинский проспект, д. 42, кв. 118", "доставка по адресу {}"),
    ("LOC", "улица Строителей, дом 53", "адрес {}"),
    ("PHONE", "+7 916 214-88-03", "телефон {}"),
    ("EMAIL", "i.petrov@example.ru", "почта {}"),
    ("SNILS", "112-233-445 95", "СНИЛС {}"),
    ("INN", "7707083893", "ИНН {}"),
    ("CARD", "4276 3800 1234 5679", "карта {}"),
    ("PASSPORT", "4509 123456", "паспорт {}"),
    ("PLATE", "А123ВС777", "госномер {}"),
    ("ACCOUNT", "40817810099910004312", "счёт {}"),
)

_LATIN = str.maketrans("аеорсхукАЕОРСХУК", "aeopcxykAEOPCXYK")


def _latin_slip(value: str, rng: random.Random) -> str:
    """ONE letter swapped for its Latin twin — a keyboard slip, not a rewrite.

    Translating every letter produced a string no human types and no detector
    should be judged on; the real shape is a single character in the middle of
    an otherwise Cyrillic word.
    """
    positions = [i for i, ch in enumerate(value) if ch in _LATIN]
    if not positions:
        return value
    at = rng.choice(positions)
    return value[:at] + value[at].translate(_LATIN) + value[at + 1:]


def _drop_char(value: str, rng: random.Random) -> str:
    letters = [i for i, ch in enumerate(value) if ch.isalnum()]
    if len(letters) < 4:
        return value
    cut = rng.choice(letters[1:])
    return value[:cut] + value[cut + 1:]


def _swap_char(value: str, rng: random.Random) -> str:
    letters = [i for i, ch in enumerate(value) if ch.isalpha()]
    if len(letters) < 4:
        return value
    at = rng.choice(letters[1:])
    return value[:at] + ("о" if value[at] != "о" else "а") + value[at + 1:]


def _unspace(value: str) -> str:
    return value.replace(" ", "", 1) if " " in value else value


def _reorder(value: str) -> str:
    parts = value.split()
    return " ".join(parts[1:] + parts[:1]) if len(parts) > 1 else value


def variants(kind: str, value: str, rng: random.Random) -> dict[str, str]:
    """Writings of ONE value. The key names the transformation, for the report."""
    out = {
        "как есть": value,
        "строчными": value.lower(),
        "ЗАГЛАВНЫМИ": value.upper(),
        "ё->е": value.replace("ё", "е").replace("Ё", "Е"),
        "лишний пробел": value.replace(" ", "  ", 1),
        "латиница внутри": _latin_slip(value, rng),
        "в JSON": value,
    }
    if kind not in _CHECKSUMMED and kind != "PHONE":
        # Only where a changed character still leaves a valid value. PHONE is
        # not checksummed but it IS length-defined: a ten-digit «phone» is not
        # one, and refusing it is right.
        out["без пробела"] = _unspace(value)
        out["пропущен символ"] = _drop_char(value, rng)
    if kind in ("NAME", "LOC"):
        out["опечатка"] = _swap_char(value, rng)
        out["другой порядок"] = _reorder(value)
    if kind in _CHECKSUMMED:
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits and kind != "PLATE":
            # Separators only: the digits themselves are untouched, so the
            # checksum still holds and a refusal really is a defect.
            #
            # GROUPED THE WAY PEOPLE GROUP THEM. «770 708 389 3» is not how
            # anybody writes an ИНН, and asking the detector to find it measured
            # my imagination. Each type gets the grouping its own form uses.
            out["только цифры"] = digits
            grouped = _GROUPING.get(kind)
            if grouped:
                out["как в бланке"] = grouped(digits)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260818)
    args = parser.parse_args()

    load_dev_bundle()
    detector = Detector()
    rng = random.Random(args.seed)

    missed: list[tuple[str, str, str, str]] = []
    total = found = 0
    index_rows: list[tuple[int, str, str, list[str]]] = []

    for kind, value, frame in SEEDS:
        vault = Vault(":memory:", "fuzz")
        tokens: dict[str, str] = {}
        for label, written in variants(kind, value, rng).items():
            if label == "в JSON":
                text = '{"%s": "%s"}' % (_JSON_KEY[kind], written)
            else:
                text = frame.format(written)
            # THE POSITION, not a substring match. Comparing the written value
            # against the span's text made every partial detection look like a
            # miss and every over-long span look like a hit — the instrument
            # would then have measured itself.
            at = text.index(written)
            span_start, span_end = at, at + len(written)
            total += 1
            hit = next((s for s in detector.detect(text)
                        if s.entity_type == kind
                        and s.start < span_end and s.end > span_start), None)
            if hit is None:
                missed.append((kind, value, label, text))
                continue
            found += 1
            tokens[label] = vault.tokenize(hit.value, kind)
        # WHICH writings disagreed, not how many. A count says the index is
        # fragmented; the groups say which transformation broke it, and that is
        # the only form of the finding somebody can act on.
        groups: dict[str, list[str]] = {}
        for label, token in tokens.items():
            groups.setdefault(token, []).append(label)
        if len(groups) > 1:
            index_rows.append((len(groups), kind, value,
                               [", ".join(sorted(labels)) for labels in groups.values()]))

    print(f"вариантов: {total}   найдено: {found} = {found / total * 100:.1f}%\n")
    if missed:
        print(f"--- НЕ НАЙДЕНО ({len(missed)}) ---")
        for kind, value, label, text in missed[:args.dump]:
            print(f"  {kind:<9} [{label:<16}] {text[:72]}")
    print(f"\n--- ОДНО ЗНАЧЕНИЕ, НЕСКОЛЬКО ПОДМЕН ({len(index_rows)}) ---")
    for count, kind, value, groups in sorted(index_rows, reverse=True):
        print(f"  {count:>2} подмен  {kind:<9} {value[:44]!r}")
        for group in groups:
            print(f"            · {group}")
    return 1 if missed or index_rows else 0


if __name__ == "__main__":
    sys.exit(main())
