"""The corpus, the identifiers it is built from, and the statistics.

`test_gates.py` runs the same checks the CI runs; these are the properties
underneath them — that a phone belongs to nobody, that a checksum is real,
that an interval is the interval it claims to be.
"""

import random
from pathlib import Path

import phonenumbers
import pytest

from agentmask_ru import ids
from agentmask_ru.assemble import Slot, assemble
from agentmask_ru.schema import CANARY, load_dir, validate
from agentmask_ru.stats import clopper_pearson, items_for, mcnemar_exact, zero_failure_floor

CASES = Path(__file__).resolve().parents[1] / "cases"


def test_every_case_validates() -> None:
    cases = load_dir(CASES)
    assert cases, "корпус пуст"
    for case in cases:
        assert validate(case) == [], case.id
        assert case.canary == CANARY


def test_phones_are_valid_mobiles_that_belong_to_nobody() -> None:
    rng = random.Random(0)
    for _ in range(200):
        digits = ids.phone_digits(rng)
        assert digits[:3] in ids.RESERVE_DEF_CODES
        parsed = phonenumbers.parse("+7" + digits, "RU")
        # It must look like an ordinary Russian mobile to a validator — a
        # number a detector would refuse is not a test of anything.
        assert phonenumbers.is_valid_number(parsed)
        assert phonenumbers.number_type(parsed) == phonenumbers.PhoneNumberType.MOBILE


def test_checksums_are_real() -> None:
    rng = random.Random(1)
    for _ in range(100):
        assert ids.snils_ok(ids.snils(rng))
        assert ids.luhn_ok(ids.card(rng).replace(" ", ""))
        inn = ids.inn12(rng)
        assert len(inn) == 12 and inn.isdigit()


def test_assemble_records_offsets_of_repeated_values() -> None:
    # The reason offsets are computed at assembly: a search would return the
    # first occurrence for both slots.
    built = assemble(["звонил ", Slot("a", "89071234567"), " и ещё раз ", Slot("b", "89071234567")])
    start_a, end_a = built.spans["a"]
    start_b, end_b = built.spans["b"]
    assert built.text[start_a:end_a] == built.text[start_b:end_b] == "89071234567"
    assert start_a != start_b


def test_assemble_refuses_a_repeated_slot_name() -> None:
    with pytest.raises(ValueError):
        assemble([Slot("a", "x"), Slot("a", "y")])


def test_clopper_pearson_matches_known_values() -> None:
    low, high = clopper_pearson(0, 10)
    assert low == 0.0
    assert abs(high - 0.3085) < 0.001          # textbook value for 0/10
    low, high = clopper_pearson(10, 10)
    assert abs(low - 0.6915) < 0.001
    assert high == 1.0
    low, high = clopper_pearson(5, 10)
    assert abs(low - 0.1871) < 0.001 and abs(high - 0.8129) < 0.001


def test_a_flawless_run_certifies_less_than_a_hundred_percent() -> None:
    assert abs(zero_failure_floor(100) - 0.9705) < 0.001
    assert items_for(0.994) == 498
    assert items_for(0.99) == 299


def test_mcnemar_is_symmetric_and_sane() -> None:
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(10, 0) < 0.01
    assert mcnemar_exact(3, 7) == mcnemar_exact(7, 3)
