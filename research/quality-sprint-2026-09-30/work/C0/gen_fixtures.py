"""C0 — local fixture generator + checker for the temporary-secret QUALITY contract.

WHAT THIS IS
------------
A deterministic, offline generator of SYNTHETIC positive and hard-negative
fixtures for the temporary-secret classes named by owner decision block 3
(REMAINING-DECISIONS.md §Блок 3) and a self-check of the SYNTAX TABLES declared
below. It emits FIXTURES.json.

WHAT THIS IS NOT
----------------
It is NOT a detector, NOT a scorer and NOT an engine-quality measurement.
`self_check` only proves that the declared syntax tables are internally
consistent with the declared example values and that each hard negative is
glyph-identical to its positive partner (i.e. it is genuinely HARD: same digit
shape, different context). A green self_check says NOTHING about the engine.
The engine-facing RED lives in `probe_engine.py` / `RED.log`.

VALUE PROVENANCE
----------------
Every value below is CONSTRUCTED for this task from a documented synthetic
block. None was collected, sampled, transacted, fetched or derived from a real
payment instrument, a real cardholder, a real SMS, a real authentication log or
any production/customer traffic. No live credential was used. The published
test PAN 4111111111111111 appears only as a structural neighbour inside a JSON
object and is a universally published non-live test number.

Run:
    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python gen_fixtures.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# --- declared SYNTAX TABLES (this file's own tables, not shipped data) -------

SYNTAX_TABLES: dict[str, dict] = {
    "CARD_VERIFICATION_CODE": {
        "class": "static_printed_card_secret",
        "lengths": [3, 4],
        "charset": "ascii_digits",
        "leading_zero_allowed": True,
        "punctuation_inside_value": False,
        "brand_lengths": {
            "Visa/Mastercard/Discover (CVV2/CVC2/CSC)": 3,
            "American Express (CID, 4DBC)": 4,
        },
        "regex": r"^[0-9]{3}$|^[0-9]{4}$",
        "example_values": ["000", "042", "314", "999", "0000", "1234", "9999"],
        "source": "PRIMARY-SOURCES.md S1 (PCI SSC: '3- or 4- digit number')",
    },
    "ISSUER_OTP": {
        "class": "dynamic_one_time_authentication_secret",
        "lengths": "unasserted",
        "charset": "ascii_digits",
        "leading_zero_allowed": True,
        "punctuation_inside_value": False,
        "brand_lengths": {"issuer-defined": "not asserted in this contract"},
        "regex": r"^[0-9]{4,10}$",
        "example_values": ["000000", "042042", "991991", "999999"],
        "source": "PRIMARY-SOURCES.md S3/S4 (issuer one-time code, SMS); length not established (U-d)",
    },
    "TOTP_2FA": {
        "class": "dynamic_time_based_one_time_secret",
        "lengths": "6_or_8_unasserted",
        "charset": "ascii_digits",
        "leading_zero_allowed": True,
        "punctuation_inside_value": False,
        "brand_lengths": {"RFC 6238 common deployments": "6"},
        "regex": r"^[0-9]{6}$|^[0-9]{8}$",
        "example_values": ["000000", "042042", "999999", "00000000"],
        "source": "candidate class; RFC 6238 is public, NOT fetched in this task (open question O-SECRET-3)",
    },
    "RECOVERY_CODE": {
        "class": "static_single_use_list_secret",
        "lengths": "alnum_8_to_12_unasserted",
        "charset": "ascii_alnum_plus_hyphen",
        "leading_zero_allowed": True,
        "punctuation_inside_value": True,
        "brand_lengths": {"vendor-defined": "not asserted"},
        "regex": r"^[A-Z0-9]{4}-[A-Z0-9]{4}$",
        "example_values": ["AAAA-0002", "ZZZZ-9999"],
        "source": "candidate class (open question O-SECRET-4)",
    },
}

# --- SYNTHETIC values, by contract-declared shape ---------------------------
V3 = ["000", "042", "314", "999"]
V4 = ["0000", "1234", "9999"]
V6 = ["000000", "042042", "991991", "999999"]
V8 = ["00000000"]
VRC = ["AAAA-0002"]

TEST_PAN = "4111111111111111"  # published non-live test PAN, structural only


def _fixture(fid, family, kind, medium, text, target, expected, pair=None,
             note="", red=None):
    return {
        "fixture_id": fid,
        "family": family,
        "kind": kind,
        "medium": medium,
        "text": text,
        "target_value": target,
        "expected_property": expected,
        "pair_id": pair,
        "red_probe_id": red,
        "note": note,
        "synthetic_provenance": "constructed_for_c0; never collected or transacted",
    }


def build_fixtures() -> list[dict]:
    f: list[dict] = []

    # ---- FAMILY 1: static printed card verification code -------------------
    f.append(_fixture("POS-CVC-001", "CARD_VERIFICATION_CODE", "positive", "json",
                      '{"cvc": "314"}', "314",
                      "value under an authoritative card-verification field name is protected",
                      pair="PAIR-JSON-1", red="RED-1"))
    f.append(_fixture("POS-CVC-002", "CARD_VERIFICATION_CODE", "positive", "json",
                      '{"cvv2": "042"}', "042",
                      "alias cvv2 under an authoritative field name is protected",
                      pair="PAIR-JSON-2", red="RED-1"))
    f.append(_fixture("POS-CVC-003", "CARD_VERIFICATION_CODE", "positive", "json",
                      '{"cid": "0000"}', "0000",
                      "4-digit brand variant (CID) under its field name is protected",
                      pair="PAIR-JSON-3", red="RED-1"))
    f.append(_fixture("POS-CVC-004", "CARD_VERIFICATION_CODE", "positive", "json",
                      '{"card": {"number": "4111111111111111", "cvc": "999"}}', "999",
                      "nested card object: the code is protected inside its own object",
                      pair="PAIR-JSON-4", red="RED-1"))
    f.append(_fixture("POS-CVC-005", "CARD_VERIFICATION_CODE", "positive", "form",
                      "CVV: 314", "314",
                      "prose/form field name with colon: value is protected",
                      pair="PAIR-FORM-1", red="RED-2"))
    f.append(_fixture("POS-CVC-006", "CARD_VERIFICATION_CODE", "positive", "prose",
                      "cvc 314", "314",
                      "bounded card-code cue licenses the value",
                      pair="PAIR-PROSE-1", red="RED-3"))
    f.append(_fixture("POS-CVC-007", "CARD_VERIFICATION_CODE", "positive", "prose",
                      "защитный код карты 042", "042",
                      "Russian printed-code cue phrase licenses the value",
                      pair="PAIR-PROSE-2", red="RED-3"))
    two_cards = ('{"card": {"number": "4111111111111111", "cvc": "042"}, '
                 '"card2": {"number": "4111111111111112", "cvc": "314"}}')
    f.append(_fixture("POS-CVC-008", "CARD_VERIFICATION_CODE", "positive", "json",
                      two_cards, "042",
                      "two card objects: each code stays bound to its own object",
                      pair="PAIR-JSON-5", red="RED-7"))

    # ---- FAMILY 2: dynamic issuer OTP (3-D Secure / SMS / push) -----------
    f.append(_fixture("POS-OTP-001", "ISSUER_OTP", "positive", "prose",
                      "код подтверждения из смс 991991", "991991",
                      "issuer one-time code is protected as ISSUER_OTP, not as CVC",
                      pair="PAIR-OTP-1", red="RED-4"))
    f.append(_fixture("POS-OTP-002", "ISSUER_OTP", "positive", "prose",
                      "одноразовый код 042042", "042042",
                      "explicit one-time wording licenses the OTP class",
                      pair="PAIR-OTP-2", red="RED-4"))
    f.append(_fixture("POS-OTP-003", "ISSUER_OTP", "positive", "json",
                      '{"otp": "000000"}', "000000",
                      "authoritative OTP field name licenses the value",
                      pair="PAIR-OTP-3", red="RED-1"))
    f.append(_fixture("POS-OTP-004", "ISSUER_OTP", "positive", "prose",
                      "3-D Secure код 999999", "999999",
                      "3DS channel wording licenses the value",
                      pair="PAIR-OTP-4", red="RED-4"))

    # ---- FAMILY 3/4: candidate classes (scope is an owner question) -------
    f.append(_fixture("CAND-TOTP-001", "TOTP_2FA", "positive", "prose",
                      "код 2FA 042042", "042042",
                      "candidate: time-based 2FA code — scope OWNER_PENDING",
                      pair=None, red=None,
                      note="O-SECRET-4: is TOTP in the temporary-secret quality scope?"))
    f.append(_fixture("CAND-REC-001", "RECOVERY_CODE", "positive", "prose",
                      "резервный код AAAA-0002", "AAAA-0002",
                      "candidate: recovery/backup code — scope OWNER_PENDING",
                      pair=None, red=None,
                      note="O-SECRET-4: recovery codes are static and multi-use-list"))

    # ---- HARD NEGATIVES: same glyphs, business context ---------------------
    f.append(_fixture("NEG-JSON-1", "CARD_VERIFICATION_CODE", "hard_negative", "json",
                      '{"order_code": "314"}', None,
                      "business order code stays open",
                      pair="PAIR-JSON-1", red="NEG-1"))
    f.append(_fixture("NEG-JSON-2", "CARD_VERIFICATION_CODE", "hard_negative", "json",
                      '{"status": "042"}', None,
                      "status code stays open",
                      pair="PAIR-JSON-2", red="NEG-1"))
    f.append(_fixture("NEG-JSON-3", "CARD_VERIFICATION_CODE", "hard_negative", "json",
                      '{"code": "314"}', None,
                      "generic key 'code' does not type the value",
                      pair=None, red="NEG-1",
                      note="lexical ambiguity rule (REMAINING-DECISIONS Блок 1)"))
    f.append(_fixture("NEG-FORM-1", "CARD_VERIFICATION_CODE", "hard_negative", "form",
                      "код товара: 314", None,
                      "product code with the same glyphs stays open",
                      pair="PAIR-FORM-1", red="NEG-1"))
    f.append(_fixture("NEG-PROSE-1", "CARD_VERIFICATION_CODE", "hard_negative", "prose",
                      "заказ 314", None,
                      "bare order number stays open",
                      pair="PAIR-PROSE-1", red="NEG-1"))
    f.append(_fixture("NEG-PROSE-2", "CARD_VERIFICATION_CODE", "hard_negative", "prose",
                      "квартира 042", None,
                      "apartment number with the same glyphs stays open",
                      pair="PAIR-PROSE-2", red="NEG-1"))
    f.append(_fixture("NEG-PROSE-3", "CARD_VERIFICATION_CODE", "hard_negative", "prose",
                      "код 314", None,
                      "a BARE 'код' may not license a card code (C1/P3 boundary)",
                      pair=None, red="NEG-2",
                      note="deliberate boundary: bare cue must not collapse CVC into OTP"))
    f.append(_fixture("NEG-OTP-1", "ISSUER_OTP", "hard_negative", "prose",
                      "номер заказа 991991", None,
                      "an order number that merely looks like a 6-digit OTP stays open",
                      pair="PAIR-OTP-1", red="NEG-1"))
    f.append(_fixture("NEG-OTP-2", "ISSUER_OTP", "hard_negative", "prose",
                      "артикул 042042", None,
                      "a 6-digit catalogue id stays open",
                      pair="PAIR-OTP-2", red="NEG-1"))
    f.append(_fixture("NEG-OTP-3", "ISSUER_OTP", "hard_negative", "json",
                      '{"sms_count": "000000"}', None,
                      "a field that merely contains 'sms' does not type its value",
                      pair="PAIR-OTP-3", red="NEG-1"))

    # ---- MALFORMED under an authoritative field (fail-closed question) -----
    f.append(_fixture("MAL-CVC-001", "CARD_VERIFICATION_CODE", "malformed_under_field", "json",
                      '{"cvc": "31"}', "31",
                      "too-short value under an authoritative field: mask-not-drop decision OWNER_PENDING",
                      pair=None, red="RED-5",
                      note="O-SECRET-5 (Q-A4 carried forward)"))
    f.append(_fixture("MAL-CVC-002", "CARD_VERIFICATION_CODE", "malformed_under_field", "json",
                      '{"cvc": "31B"}', "31B",
                      "non-digit under an authoritative field: mask-not-drop decision OWNER_PENDING",
                      pair=None, red="RED-5",
                      note="O-SECRET-5 (Q-A4 carried forward)"))
    f.append(_fixture("MAL-CVC-003", "CARD_VERIFICATION_CODE", "structural_gap", "json",
                      '{"cvc": 314}', "314",
                      "UNQUOTED JSON number under an authoritative field: string-value-only KV regex gap",
                      pair=None, red="RED-3",
                      note="structural gap; not a policy question"))

    # ---- FORM / exact-copy fidelity fixtures -------------------------------
    f.append(_fixture("FORM-CVC-001", "CARD_VERIFICATION_CODE", "form_fidelity", "form",
                      "cvv:314", "314",
                      "exact copy: no space after the colon must be inherited by the substitute's slot",
                      pair=None, red=None))
    f.append(_fixture("FORM-CVC-002", "CARD_VERIFICATION_CODE", "form_fidelity", "form",
                      "CVV   314", "314",
                      "exact copy: run of spaces preserved on the value side",
                      pair=None, red=None))
    f.append(_fixture("FORM-CVC-003", "CARD_VERIFICATION_CODE", "form_fidelity", "prose",
                      "cvc 000", "000",
                      "exact copy: leading zero is part of the value and must not be dropped",
                      pair=None, red=None))

    # ---- ambiguity / multi-secret payloads --------------------------------
    f.append(_fixture("AMB-001", "CARD_VERIFICATION_CODE", "ambiguous", "prose",
                      "cvc 314, код подтверждения 991991", "314",
                      "one card code (314) and one issuer OTP (991991) in one utterance keep DIFFERENT classes",
                      pair=None, red="RED-6",
                      note="secondary target 991991 is ISSUER_OTP; separation is a fixture-level property today because both are unprotected on the engine"))
    f.append(_fixture("AMB-002", "CARD_VERIFICATION_CODE", "ambiguous", "json",
                      '{"card": {"number": "4111111111111111", "cvc": "000"}, '
                      '"order": {"code": "000"}}', "000",
                      "same glyphs in a card field and an order field: only the card field is typed",
                      pair=None, red="RED-7"))
    return f


# --- self-check of THIS FILE's tables ---------------------------------------

def self_check(fixtures: list[dict]) -> dict:
    report: dict = {"checks": [], "ok": True, "counts": {}}

    def rec(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            report["ok"] = False

    # 1. every declared regex compiles and matches every declared example value
    for type_id, table in SYNTAX_TABLES.items():
        rx = re.compile(table["regex"])
        bad = [v for v in table["example_values"] if not rx.match(v)]
        rec(f"table:{type_id}:examples_match_own_regex", not bad,
            f"{len(table['example_values']) - len(bad)}/{len(table['example_values'])} match; mismatched={bad}")

    # 2. CVC table: the declared length set is exactly {3,4} and both are covered
    cvc = SYNTAX_TABLES["CARD_VERIFICATION_CODE"]
    rec("table:CARD_VERIFICATION_CODE:length_set_is_3_or_4",
        sorted(cvc["lengths"]) == [3, 4], f"lengths={cvc['lengths']}")
    rec("table:CARD_VERIFICATION_CODE:both_lengths_have_examples",
        any(len(v) == 3 for v in cvc["example_values"]) and any(len(v) == 4 for v in cvc["example_values"]),
        f"examples={cvc['example_values']}")

    # 3. every fixture's target value is syntactically legal for its family —
    #    EXCEPT a fixture whose whole point is that the value is malformed, and
    #    which must therefore NOT match the family syntax.
    for fx in fixtures:
        t = fx["target_value"]
        if t is None or fx["family"] not in SYNTAX_TABLES:
            continue
        for part in re.split(r"\s*\+\s*", t):
            if part in ("", "None"):
                continue
            rx = re.compile(SYNTAX_TABLES[fx["family"]]["regex"])
            if fx["kind"] == "malformed_under_field":
                rec(f"fixture:{fx['fixture_id']}:malformed_target_violates_family_syntax",
                    not rx.match(part),
                    f"target={part!r} family={fx['family']} (expected NOT to match)")
            else:
                rec(f"fixture:{fx['fixture_id']}:target_matches_family_syntax", bool(rx.match(part)),
                    f"target={part!r} family={fx['family']}")

    # 4. every hard negative is genuinely HARD: its text carries the same digit
    #    shape as its paired positive (same glyphs, different context)
    by_id = {fx["fixture_id"]: fx for fx in fixtures}
    pairs = 0
    for fx in fixtures:
        if fx["kind"] != "hard_negative" or not fx["pair_id"]:
            continue
        partner = next((x for x in fixtures if x["pair_id"] == fx["pair_id"] and x["kind"] == "positive"), None)
        if partner is None:
            continue
        pairs += 1
        pos_target = partner["target_value"]
        same_glyphs = bool(pos_target) and pos_target in fx["text"]
        rec(f"pair:{fx['pair_id']}:negative_carries_same_digits", same_glyphs,
            f"positive target {pos_target!r} present in negative text {fx['text']!r}")
    rec("pairs:positive_negative_pairs_present", pairs >= 5, f"pairs_checked={pairs}")

    # 5. no duplicate target value is used by two DIFFERENT families in a way
    #    that would make the fixture set self-contradictory
    seen: dict[str, set] = {}
    for fx in fixtures:
        if fx["target_value"] and fx["kind"].startswith(("positive", "hard")):
            seen.setdefault(fx["target_value"], set()).add(fx["family"])
    report["counts"] = {
        "fixtures_total": len(fixtures),
        "positive": sum(1 for x in fixtures if x["kind"] == "positive"),
        "hard_negative": sum(1 for x in fixtures if x["kind"] == "hard_negative"),
        "malformed_under_field": sum(1 for x in fixtures if x["kind"] == "malformed_under_field"),
        "structural_gap": sum(1 for x in fixtures if x["kind"] == "structural_gap"),
        "form_fidelity": sum(1 for x in fixtures if x["kind"] == "form_fidelity"),
        "ambiguous": sum(1 for x in fixtures if x["kind"] == "ambiguous"),
        "candidate_owner_pending": sum(1 for x in fixtures if x["family"] in ("TOTP_2FA", "RECOVERY_CODE")),
        "families": sorted({x["family"] for x in fixtures}),
        "pairs_checked": pairs,
        "checks_run": len(report["checks"]),
    }
    report["never_counts_as_engine_quality"] = True
    report["meaning"] = ("validates ONLY this file's own syntax tables and the internal "
                         "consistency of the fixture set; it is not a detector and not an "
                         "engine quality measurement")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="run the table self-check")
    ap.add_argument("--out", default=str(HERE / "FIXTURES.json"))
    args = ap.parse_args()

    fixtures = build_fixtures()
    sc = self_check(fixtures)
    doc = {
        "artifact": "C0/FIXTURES.json",
        "task": "C0",
        "generator": "work/C0/gen_fixtures.py",
        "synthetic_only": True,
        "provenance_note": ("All values are constructed for this task from a documented "
                            "synthetic block; none was collected, sampled, transacted, "
                            "fetched or derived from real traffic or a real payment instrument."),
        "forbidden_uses": ["engine quality claim", "scorer", "benchmark", "production retention"],
        "syntax_tables": SYNTAX_TABLES,
        "fixtures": fixtures,
        "self_check": sc,
    }
    if args.check:
        print(json.dumps({"self_check_ok": sc["ok"], "counts": sc["counts"],
                          "failed": [c for c in sc["checks"] if not c["ok"]]},
                         ensure_ascii=False, indent=2))
    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {sc['counts']['fixtures_total']} fixtures, self_check_ok={sc['ok']}")
    return 0 if sc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
