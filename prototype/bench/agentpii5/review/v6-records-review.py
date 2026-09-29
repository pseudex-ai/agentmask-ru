# v6-records-review.py — Lead's review of the subagent-written TypeSpec records.
# Not a committed test: a one-shot gate I run before merging GROUP_A/B/C into
# pii_types.TYPE_REGISTRY. Checks mechanical consistency against the mapping
# spec; the CARD-level accuracy is reviewed record by record by reading the card.
#
#     cd prototype && source .venv/bin/activate && python3 ../prototype/../bench/agentpii5/review/v6-records-review.py  # noqa
from __future__ import annotations

import sys

sys.path.insert(0, ".")

import bench.agentpii5.pii_types as p  # noqa: E402

EXPECTED = {
    "A": (16, "INTL_PASSPORT BIRTH_CERT CIVIL_ACT_CERT RESIDENCE_PERMIT MILITARY_ID "
          "BANK_ACCOUNT IBAN LOAN_CONTRACT_NUMBER LOAN_UID OGRNIP CREDIT_SUBJECT_CODE "
          "OMS_ENP DMS_POLICY OSAGO_POLICY KASKO_POLICY INSURANCE_CLAIM_NUMBER".split()),
    "B": (15, "VIN EPTS_NUMBER UIN COURT_CASE_UID ARBITRAZH_CASE_NO COURT_CASE_NO_SOU "
          "FSSP_IP_NO EXEC_DOC_NO STS_NUMBER PTS_NUMBER DRIVER_LICENSE CADASTRAL_NUMBER "
          "GIS_ZHKH_ELS UTILITY_ACCOUNT ESIA_OID".split()),
    "C": (24, "IMEI ICCID IMSI MAC IP_ADDRESS SUBSCRIBER_ACCOUNT MEDCARD_NUMBER ELN_NUMBER "
          "PRESCRIPTION_NUMBER REFERRAL_NUMBER DIPLOMA_NUMBER SCHOOL_CERT_NUMBER "
          "STUDENT_ID_NUMBER EMPLOYEE_TAB_NUMBER EMPLOYMENT_CONTRACT_NUMBER ACCESS_PASS_NUMBER "
          "PNR E_TICKET_NUMBER LOYALTY_CARD_NUMBER MOBILE_AD_ID APP_DEVICE_ID "
          "METRICA_CLIENT_ID CDP_CUSTOMER_ID LOGIN".split()),
}

CLASS = {"IMEI": "C", "OMS_ENP": "KC", "BANK_ACCOUNT": "KC", "VIN": "KC",
         "LOYALTY_CARD_NUMBER": "KC"}
CHECKSUM = {"IMEI": "luhn", "OMS_ENP": "luhn", "BANK_ACCOUNT": "cbr515", "VIN": "iso3779",
            "LOYALTY_CARD_NUMBER": "gs1", "IBAN": "mod97", "LOAN_UID": "uid",
            "OGRNIP": "ogrnip", "EPTS_NUMBER": "epts", "UIN": "uin",
            "COURT_CASE_UID": "mod97", "ICCID": "luhn", "INTL_PASSPORT": "icao"}


def main() -> int:
    failures = 0
    for group, (count, ids) in EXPECTED.items():
        module = __import__(f"bench.agentpii5.pii_types_{group.lower()}", fromlist=["GROUP"])
        records = getattr(module, f"GROUP_{group}")
        got = [t.id for t in records]
        if len(records) != count:
            print(f"FAIL {group}: {len(records)} records, expected {count}")
            failures += 1
        if got != ids:
            print(f"FAIL {group}: order {got} != {ids}")
            failures += 1
        for t in records:
            if t.origin != p.ORIGIN_V6:
                print(f"FAIL {t.id}: origin {t.origin}")
                failures += 1
            if t.type_class != CLASS.get(t.id, "K"):
                print(f"FAIL {t.id}: class {t.type_class}, expected {CLASS.get(t.id, 'K')}")
                failures += 1
            if t.generated_checksum != CHECKSUM.get(t.id, ""):
                print(f"FAIL {t.id}: checksum {t.generated_checksum!r}, expected {CHECKSUM.get(t.id, '')!r}")
                failures += 1
            if t.generated_checksum and not t.mint:
                print(f"FAIL {t.id}: checksum without mint (T5)")
                failures += 1
            if t.type_class == "K" and not t.bare_typed and not t.cues and not t.field_keys:
                print(f"FAIL {t.id}: [K] without cue/key (T6)")
                failures += 1
            if "whole" not in t.needle_kinds:
                print(f"FAIL {t.id}: no 'whole' needle (T2)")
                failures += 1
            for feature, labels in t.feature_labels:
                if len(labels) < 2:
                    print(f"FAIL {t.id}.{feature}: <2 labels (T1)")
                    failures += 1
    print("records-review: PASS" if not failures else f"records-review: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
