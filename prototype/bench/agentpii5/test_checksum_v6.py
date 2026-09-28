# test_checksum_v6.py — the validator home of the checksum arithmetic is pinned
# to the registry (docs/tz-agentpii6-registry.md §1.8 L7 table) and to the
# "no third implementation / no engine import" rule (L2 / R6-07).
#
#     cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_checksum_v6
#
# No pytest, as everywhere in `prototype/`: `main()` prints PASS/FAIL and returns
# the exit code.

from __future__ import annotations

import pathlib
import subprocess
import sys

import bench.agentpii5.checksum_v6 as csum

_PROTOTYPE = str(pathlib.Path(__file__).resolve().parent.parent.parent)


# --- R6-08: every cited working example must reproduce --------------------------
# Every value comes from the registry card or the §1.8 L7 table. The two homes
# (`checksum_v6` and `gen_v6`) are proven not to share one bug by BOTH agreeing
# with these numbers; this test pins THIS home to them.

def test_primary_examples() -> list[str]:
    problems: list[str] = []

    def ok(cond: bool, label: str) -> None:
        if not cond:
            problems.append(label)

    # IMEI (C-01; TS 23.003 B.3: body 26053179311383 → CD 7).
    ok(csum.luhn_check_digit("26053179311383") == "7", "IMEI body 26053179311383 -> 7")
    ok(csum.validate("IMEI", "260531793113837"), "IMEI 260531793113837 valid")

    # OMS_ENP (A-13): HL7 Mod10 == Luhn; the card's four algorithm examples.
    ok(csum.luhn_check_digit("12345") == "5", "HL7 Mod10 12345 -> 5")
    ok(csum.luhn_check_digit("401") == "0", "HL7 Mod10 401 -> 0")
    ok(csum.luhn_check_digit("9999") == "4", "HL7 Mod10 9999 -> 4")
    ok(csum.luhn_check_digit("99999999") == "8", "HL7 Mod10 99999999 -> 8")
    for full in ("123455", "4010", "99994", "999999998"):
        ok(csum.validate("OMS_ENP", full), f"OMS_ENP body+CD {full} valid")
    ok(csum.validate("OMS_ENP", "5632122330792448"), "OMS_ENP 5632122330792448 valid (16-digit Luhn)")

    # ICCID (C-02): 19-digit Luhn; synthetic C "8970102000000123458" (CD 8).
    ok(csum.validate("ICCID", "8970102000000123458"), "ICCID 8970102000000123458 valid")

    # BANK_ACCOUNT (A-07): the three cited pairs, key position already filled.
    ok(csum.cbr515_account_key("40602810000000000025", "049805746") == 7,
       "BANK_ACCOUNT key 049805746+40602810000000000025 -> 7")
    ok(csum.validate_account("40602810700000000025", "049805746"),
       "BANK_ACCOUNT 049805746 + 40602810700000000025 valid (key 7)")
    ok(csum.validate_account("40102810100000010001", "040305000"),
       "BANK_ACCOUNT 040305000 + 40102810100000010001 valid (key 1)")
    ok(csum.validate_account("30101810800000000746", "049805000"),
       "BANK_ACCOUNT 049805000 + 30101810800000000746 valid (key 8)")

    # IBAN (A-08): the CBR example with key 03 (secondary source, one-source flag).
    ok(csum.validate("IBAN", "RU0304452522540817810538091310419"),
       "IBAN RU0304452522540817810538091310419 valid")

    # LOAN_UID (A-10): synthetic — 32 hex + check, formatted 8-4-4-4-12-C.
    ok(csum.validate("LOAN_UID", "1dcf884c-1e1b-4c3f-a5c9-f0a1b2c3d4e5-9"),
       "LOAN_UID 1dcf884c-1e1b-4c3f-a5c9-f0a1b2c3d4e5-9 valid")

    # OGRNIP (A-11): 304500116000157 (validator-library value, denylist, still
    # checksum-valid per the task and A-11).
    ok(csum.validate("OGRNIP", "304500116000157"), "OGRNIP 304500116000157 valid")

    # EPTS_NUMBER (B-02): factchecker's synthetic 164301000000016.
    ok(csum.validate("EPTS_NUMBER", "164301000000016"), "EPTS_NUMBER 164301000000016 valid")

    # UIN (B-03): no cited example; synthetic (weights 1..10).
    ok(csum.validate("UIN", "18812345678901234565"), "UIN 18812345678901234565 valid")

    # VIN (B-01): 49 CFR 565.15 sum 411 → check 4 at position 9.
    ok(csum.vin_check_digit("1G4AH59H45G118341") == "4", "VIN sum 411 -> 4")
    ok(csum.validate("VIN", "1G4AH59H45G118341"), "VIN 1G4AH59H45G118341 valid")

    # LOYALTY_CARD_NUMBER (C-22): GS1 body 37610425002123456 → sum 101 → 9.
    ok(csum.gs1_check_digit("37610425002123456") == "9", "GS1 37610425002123456 -> 9")
    ok(csum.validate("LOYALTY_CARD_NUMBER", "376104250021234569"),
       "LOYALTY_CARD_NUMBER 376104250021234569 valid")

    # INTL_PASSPORT (A-01): ICAO 7-3-1 over the MRZ; 520727 -> 3, AB2134<<< -> 5.
    ok(csum.icao731_check_digit("520727") == "3", "ICAO 520727 -> 3")
    ok(csum.icao731_check_digit("AB2134<<<") == "5", "ICAO AB2134<<< -> 5")
    ok(csum.validate("INTL_PASSPORT", "5207273"), "MRZ 5207273 valid")
    ok(csum.validate("INTL_PASSPORT", "AB2134<<<5"), "MRZ AB2134<<<5 valid")

    # S10 track (negative; UPU S10-12): 47312482 -> sum 200 -> CD 9.
    ok(csum.upu_check_digit("47312482") == "9", "UPU S10 47312482 -> 9")
    ok(csum.validate("S10", "473124829"), "S10 473124829 valid")

    return problems


# --- R6-09: every documented "необнаружимый класс" is ACCEPTED -----------------
# Each tuple is (label, value). The value is a MUTATION of a valid value that the
# checksum MUST NOT reject. The label names the class and cites the §1.8 L7
# table line (col 7) plus the card's «Необнаружимо» line.

def test_mutation_classes() -> list[str]:
    problems: list[str] = []

    # (label, type_id, value) for every class except BANK_ACCOUNT, which needs
    # the pair (account, bik) and is handled separately below.
    cases: list[tuple[str, str, str]] = [
        # IMEI — §1.8:1615 "через одну; 09↔90; гасящие пары" (C-01:913).
        ("IMEI через одну (body 2<->4 of 260531793113837)", "IMEI", "250631793113837"),
        ("IMEI 09<->90 (body ...09, CD 2)", "IMEI", "260531793113092"),
        ("IMEI 09<->90 (body ...90, CD 2)", "IMEI", "260531793113902"),
        ("IMEI гасящие пары (two canceling single errors)", "IMEI", "161531793113837"),
        # OMS_ENP — §1.8:1616 "через одну 100%; 09↔90; близнецы" (A-13:369).
        ("OMS_ENP через одну (body 2<->4 of 5632122330792448)", "OMS_ENP", "5236122330792448"),
        ("OMS_ENP 09<->90 (body ...09)", "OMS_ENP", "3195545904544098"),
        ("OMS_ENP 09<->90 (body ...90)", "OMS_ENP", "3195545904544908"),
        ("OMS_ENP близнецы 22->55", "OMS_ENP", "5632155330792448"),
        # ICCID — §1.8:1617 "как Лун" (C-02:947).
        ("ICCID через одну (body 2<->4 of 8970102000000123458)", "ICCID", "8079102000000123458"),
        # LOAN_UID — §1.8:1619 "одиночные с дельтой 8 на чётных весах" (A-10:277).
        ("LOAN_UID delta-8 on even weight (d->5 at weight 2)", "LOAN_UID",
         "15cf884c-1e1b-4c3f-a5c9-f0a1b2c3d4e5-9"),
        # OGRNIP — §1.8:1620 "r ↔ r±10" (A-11:307): remainders 1 and 11 share low digit.
        ("OGRNIP r=1 (body mod 13 == 1)", "OGRNIP", "300000000000101"),
        ("OGRNIP r=11 == r+10 (same check digit)", "OGRNIP", "300000000000201"),
        # EPTS_NUMBER — §1.8:1621 "свёртка 10→0" (B-02:535).
        ("EPTS_NUMBER remainder 10 folds to 0", "EPTS_NUMBER", "100000000000000"),
        # UIN — §1.8:1622 "i↔i+10 всегда; пути через запасной проход" (B-03:565).
        ("UIN swap i<->i+10 (positions 1<->11)", "UIN", "88812345671901234565"),
        ("UIN reserve pass (first remainder 10 -> shifted weights)", "UIN",
         "10000000000000000014"),
        # VIN — §1.8:1626 "равнозначные буквы; позиции равного веса" (B-01:499).
        ("VIN equal-value letter (A->J, both value 1)", "VIN", "1G4JH59H45G118341"),
        ("VIN equal-weight positions (card's own 1<->11 example)", "VIN", "29S346P3XDL5UT4F5"),
        # LOYALTY_CARD_NUMBER — §1.8:1627 "через одну; разница 5" (C-22:1325).
        ("LOYALTY через одну (body 2<->4 of 376104250021234569)", "LOYALTY_CARD_NUMBER",
         "316704250021234569"),
        ("LOYALTY разница 5 (61->16)", "LOYALTY_CARD_NUMBER", "371604250021234569"),
        # INTL_PASSPORT — §1.8:1628 "соседние с разницей 5; через одну" (A-01:37).
        ("INTL_PASSPORT соседние разница 5 (72->27)", "INTL_PASSPORT", "5202773"),
        ("INTL_PASSPORT через одну (2<->4 of 5207273)", "INTL_PASSPORT", "5702273"),
        # S10 track — §1.8:1629 "остатки 0/1 → 5/0".
        ("S10 remainder 0 -> check 5", "S10", "100000025"),
        ("S10 remainder 1 -> check 0", "S10", "100000140"),
    ]

    for label, type_id, value in cases:
        if not csum.validate(type_id, value):
            problems.append(f"rejected undetectable mutation: {label} ({value!r})")

    # BANK_ACCOUNT — §1.8:1625 "без БИК — всё; с БИК: разница 5 при перестановке"
    # (A-07:166). The bare-value half ("без БИК") is a statement that the gate is
    # empty, not a single value; the testable half is the diff-5 transposition.
    bik = "049805746"
    base, mutated = "29141777231702790743", "29141777231707290743"
    if not csum.validate_account(base, bik):
        problems.append(f"BANK_ACCOUNT base pair not valid: {bik}/{base}")
    if not csum.validate_account(mutated, bik):
        problems.append(
            f"rejected undetectable mutation: BANK_ACCOUNT разница 5 "
            f"(transposition 27->72) ({bik}/{mutated})"
        )

    # IBAN — §1.8:1618 "многосимвольные (доля не мерена); ключ вложенного счёта"
    # (A-08:223). The embedded account's ЦБ 515 key is wrong (6 vs 5), yet the
    # MOD 97-10 key is recomputed to stay valid, so the IBAN passes.
    bad_iban = "RU6204452522540817810638091310419"
    if not csum.validate("IBAN", bad_iban):
        problems.append(f"rejected undetectable mutation: IBAN key of nested account not checked ({bad_iban})")
    embedded_account = bad_iban[4 + 9:]
    embedded_bik = bad_iban[4:4 + 9]
    if csum.validate_account(embedded_account, embedded_bik):
        problems.append("IBAN fixture is wrong: the nested account key should be broken")

    return problems


# --- L2 / R6-07: importing this home loads neither pseudex, gen_v6 nor licensing
# Checked in a FRESH process so an import left behind by the test runner cannot
# both load the module and pass the check (same trick as test_pii_types).

def test_two_homes_by_design() -> list[str]:
    code = (
        "import sys; import bench.agentpii5.checksum_v6; "
        "bad = sorted({m for m in sys.modules "
        "if m.split('.')[0] in ('pseudex', 'gen_v6', 'licensing') "
        "or m == 'bench.agentpii5.gen_v6'}); "
        "print(','.join(bad))"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=_PROTOTYPE)
    if proc.returncode != 0:
        return [f"fresh process failed: {proc.stderr.strip()}"]
    leaked = proc.stdout.strip()
    if leaked:
        return [f"checksum_v6 loads a forbidden module: {leaked}"]
    return []


CHECKS = (test_primary_examples, test_mutation_classes, test_two_homes_by_design)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_checksum_v6: PASS" if not failures else f"test_checksum_v6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
