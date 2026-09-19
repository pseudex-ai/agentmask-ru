"""Structured identifiers, generated so that they belong to nobody.

PHONES. Russian numbering has no fictitious range like the American 555, so a
random «+7 926 …» is somebody's phone. The numbering plan (Приказ Минцифры
России от 31.01.2022 № 75 «Об утверждении российской системы и плана
нумерации», ред. от 17.06.2025, таблица 8) lists the DEF codes that are
RESERVED and assigned to no operator. Every phone in this corpus is drawn from
them. libphonenumber treats all 9xx codes as valid Russian mobiles, so a
detector that validates numbers sees an ordinary phone — which is the point:
the value must be detectable and must belong to no subscriber. Re-check the
list against the current edition at every release; the edition is recorded
below so a reader can see which one was used.

CHECKSUMS. СНИЛС, ИНН and card numbers are generated checksum-VALID because
this benchmark measures checksum-gated detectors, and a detector that
rejects an invalid checksum is right to do so. The probability that a random
valid value coincides with a real one is on the order of 1e-9 to 1e-11 per
value; the dataset card states it.

PASSPORTS have no public existence check; the series is a region code and a
year, the number is random, and the card says so.
"""

import random

NUMBERING_PLAN_EDITION = "Приказ Минцифры России № 75 от 31.01.2022, ред. от 17.06.2025"
RESERVE_DEF_CODES: tuple[str, ...] = (
    "907", "935", "943", "944", "945", "946", "947", "948", "972", "973", "974", "975", "976",
)


def phone_digits(rng: random.Random) -> str:
    """Ten national digits: a reserve DEF code and seven random digits."""
    return rng.choice(RESERVE_DEF_CODES) + "".join(rng.choice("0123456789") for _ in range(7))


def snils(rng: random.Random) -> str:
    """Nine digits plus the mod-101 check number, formatted «123-456-789 01».

    The check is the weighted sum (weights 9..1) mod 101; 100 folds to 00.
    Numbers below 001-001-998 are not issued, so the first digit is never 0.
    """
    while True:
        digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(8)]
        total = sum(d * (9 - i) for i, d in enumerate(digits))
        check = total % 101
        if check == 100:
            check = 0
        body = "".join(map(str, digits))
        return f"{body[:3]}-{body[3:6]}-{body[6:9]} {check:02d}"


def inn12(rng: random.Random) -> str:
    """A natural person's 12-digit ИНН with both check digits valid."""
    w11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    w12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    base = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(9)]
    c11 = sum(d * w for d, w in zip(base, w11)) % 11 % 10
    c12 = sum(d * w for d, w in zip(base + [c11], w12)) % 11 % 10
    return "".join(map(str, base + [c11, c12]))


def card(rng: random.Random) -> str:
    """Sixteen digits passing Luhn, formatted in groups of four. The leading
    «2200» prefix belongs to the domestic Мир scheme — a shape every Russian
    validator knows."""
    body = [2, 2, 0, 0] + [rng.randint(0, 9) for _ in range(11)]
    total = 0
    for i, d in enumerate(reversed(body)):
        d2 = d * 2 if i % 2 == 0 else d
        total += d2 - 9 if d2 > 9 else d2
    check = (10 - total % 10) % 10
    digits = "".join(map(str, body + [check]))
    return " ".join(digits[i:i + 4] for i in range(0, 16, 4))


# Region codes of the passport series are the same two digits the regions use
# elsewhere; the second pair is the year of issue.
_REGIONS: tuple[str, ...] = ("45", "40", "46", "50", "63", "66", "24", "92", "77", "16", "52", "54")


def passport(rng: random.Random) -> str:
    """«45 19 123456» — series (region, year) and a six-digit number."""
    series = rng.choice(_REGIONS) + str(rng.randint(10, 24))
    number = f"{rng.randint(100000, 999999)}"
    return f"{series[:2]} {series[2:]} {number}"


def dob(rng: random.Random) -> tuple[int, int, int]:
    """A date of birth of an adult: (day, month, year) with 28 days in every
    month so no register can produce an impossible date."""
    return rng.randint(1, 28), rng.randint(1, 12), rng.randint(1955, 2004)


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def snils_ok(value: str) -> bool:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 11:
        return False
    body, check = digits[:9], int(digits[9:])
    total = sum(int(d) * (9 - i) for i, d in enumerate(body))
    expected = total % 101
    if expected == 100:
        expected = 0
    return check == expected
