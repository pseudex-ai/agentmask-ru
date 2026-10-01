#!/usr/bin/env python3
"""A1: derive DATA-GAPS.csv and DATA-GAPS-SUMMARY.json from INVENTORY.json.

Pure derivation, no new source reads, no detector.  Independence estimate for every
authored row is the count of distinct gold *identities* of that type inside the slice
(a repeated mention of one person is one independent unit, per the owner's rule that
repetitions/templates are not independent N).  For third-party corpora the independence
unit is the document / row, because those corpora carry no stable identity key.

Run:
    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
        research/quality-sprint-2026-09-30/work/A1/derive_gaps.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

A1 = Path(__file__).resolve().parent
ROOT = Path("/Users/igor/Projects/Obscura-hop-audit")
TARGET = 300
MAIN_TYPES = ["NAME", "LOC", "PHONE", "EMAIL", "PASSPORT", "SNILS", "INN", "CARD",
              "PLATE", "DOB"]
TEMP_SECRET_TYPES = ["CVC", "CVV", "CID", "OTP", "SMS_CODE", "THREEDS"]

BLIND_CLASS = {
    "v5_corpus_1800": "known_diagnostic",
    "run_2026_09_30_813": "known_diagnostic_measured",
    "legacy_dataset": "known_diagnostic",
    "legacy_dirty": "known_diagnostic",
    "legacy_stress": "known_diagnostic",
    "legacy_stress2": "known_diagnostic",
    "gate_instrument": "known_diagnostic_hand_labeled",
    "nerel": "external_already_measured_strict_only",
    "piibench": "external_already_measured_strict_only",
    "massive": "external_already_measured_slot_not_pii",
    "voice_addresses": "external_already_measured_strict_only",
    "rudevices_addresses": "external_already_measured_strict_only",
    "v6_registry": "not_built",
    "temporary_secrets": "not_built_synthetic_only",
}

ROWS: list[dict] = []


def row(dataset, slice_type, slice_value, pii_type, items, independent, cases,
        note, dataset_hash=""):
    ROWS.append({
        "dataset": dataset,
        "blind_status": BLIND_CLASS.get(dataset, "unknown"),
        "slice_type": slice_type,
        "slice_value": slice_value,
        "pii_type": pii_type,
        "available_occurrences": items,
        "independent_units_estimate": independent,
        "cases_or_documents": cases,
        "target_units": TARGET,
        "gap_units": max(0, TARGET - independent) if independent is not None else "",
        "independence_note": note,
        "source_sha256": dataset_hash,
    })


def main() -> int:
    inv = json.loads((A1 / "INVENTORY.json").read_text())

    for key in ("v5_corpus_1800", "run_2026_09_30_813"):
        src = inv[key]
        sha = src["sha256"]
        note = ("identity cluster = unique gold 'identity' of the type inside the slice; "
                "one person mentioned N times counts once")
        for t, d in src["per_type"].items():
            row(key, "type_total", "all", t, d["items"], d["unique_identities"],
                d["cases"], note, sha)
        for k, items in src["register_type_items"].items():
            reg, t = k.split("|")
            row(key, "register", reg, t, items,
                src["register_type_unique_identities"].get(k, 0), "", note, sha)
        for k, items in src["kind_type_items"].items():
            kind, t = k.split("|")
            row(key, "surface_kind", kind, t, items,
                src["kind_type_unique_identities"].get(k, 0), "", note, sha)
        # negatives / specificity support at case level
        row(key, "specificity_negative", "all", "HARD_NEGATIVE",
            src["negatives_total"], src["negatives_total"], src["cases"],
            "authored negatives, one per case; NOT independent hard-negative text",
            sha)

    for key in ("legacy_dataset", "legacy_dirty", "legacy_stress", "legacy_stress2"):
        src = inv[key]
        sha = src["sha256"]
        for t, d in src["per_type"].items():
            row(key, "type_total", "all", t, d["items"], d["cases"], d["cases"],
                "no identity key in set; case = independence unit", sha)
        row(key, "specificity_negative", "all", "HARD_NEGATIVE",
            src["negatives_total"], src["negatives_total"], "",
            "explicit negatives field; dirty.json hard negatives are the only pre-registered ones",
            sha)

    g = inv["gate_instrument"]
    for label, n in g["label_distribution"].items():
        row("gate_instrument", "label_stratum", "hand_labeled", label.upper(), n, n, "",
            "hand-labelled occurrence, snapshot-pinned; 587 labelled of 3054 candidates",
            g["labels_sha256"])
    row("gate_instrument", "coverage", "candidates", "ALL",
        g.get("candidate_occurrences", 0), g.get("candidate_occurrences", 0), "",
        "candidate occurrences extracted from 55902 utterances; labels exist for 587",
        g.get("candidates_sha256", ""))

    n = inv["nerel"]
    for split, d in n.items():
        row("nerel", "split", split, "PERSON", d.get("person_rows", 0),
            d.get("docs_with_person", 0), d.get("docs", 0),
            "document = independence unit; annotation rows are not independent persons",
            "")
    p = inv["piibench"]
    for part, d in p.items():
        for t, cnt in (d.get("per_type") or {}).items():
            row("piibench", "part", part, t, cnt, cnt, d.get("rows", 0),
                "row = independence unit; corpus annotates legal entities too (KPP/OGRN)",
                d.get("sha256", ""))
    m = inv["massive"]
    for part, d in m.items():
        slots = d.get("slot_occurrences") or {}
        uniq = d.get("slot_unique_values") or {}
        row("massive", "split", part, "NAME", slots.get("person", 0),
            uniq.get("person", 0), d.get("rows", 0),
            "slot value is NOT automatically PII NAME (owner P16); unique surface string used",
            d.get("sha256", ""))
        row("massive", "split", part, "LOC", slots.get("place_name", 0),
            uniq.get("place_name", 0), d.get("rows", 0),
            "bare toponym is not PII by product decision", d.get("sha256", ""))
        row("massive", "split", part, "EMAIL", slots.get("email_address", 0),
            uniq.get("email_address", 0), d.get("rows", 0),
            "slot value", d.get("sha256", ""))

    for key, label_pos in (("voice_addresses", "адрес с номером"),
                           ("rudevices_addresses", "адрес с номером")):
        src = inv[key]
        dist = src.get("label_distribution") or {}
        for lab, cnt in dist.items():
            row(key, "label_stratum", "dictated_speech", lab.upper(), cnt, cnt, "",
                "dictated address labelling; positives are 'адрес с номером'",
                src.get("sha256", ""))

    v6 = inv["v6_registry"]
    for t in v6["new_v6_types"]:
        row("v6_registry", "registry_type", "v6_new", t, 0, 0, 0,
            "registry/contract visible; generated v6 corpus absent on host",
            "")
    for t in TEMP_SECRET_TYPES:
        row("temporary_secrets", "registry_type", "temporary_secret", t, 0, 0, 0,
            "no corpus; synthetic isolated fixtures only (owner P14)", "")

    out = A1 / "DATA-GAPS.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ROWS[0].keys()))
        w.writeheader()
        w.writerows(ROWS)

    # summary: total independent units per pii_type across all sources
    per_type: dict[str, dict] = {}
    for r in ROWS:
        t = r["pii_type"]
        agg = per_type.setdefault(t, {"occurrences": 0, "independent": 0,
                                      "sources": set(), "blind": set()})
        if isinstance(r["available_occurrences"], int):
            agg["occurrences"] += r["available_occurrences"]
        if isinstance(r["independent_units_estimate"], int):
            agg["independent"] += r["independent_units_estimate"]
        agg["sources"].add(r["dataset"])
        agg["blind"].add(r["blind_status"])
    summary = {
        "target_units_per_main_type_slice": TARGET,
        "main_types": MAIN_TYPES,
        "rows": len(ROWS),
        "per_type": {
            t: {"occurrences_across_sources": v["occurrences"],
                "independent_units_naive_sum": v["independent"],
                "note": "sum across sources double-counts reused authored templates; "
                        "use the per-slice rows, not this sum, for support claims",
                "sources": sorted(v["sources"]),
                "blind_status": sorted(v["blind"])}
            for t, v in sorted(per_type.items())
        },
        "main_type_gap_from_single_largest_known_source": {
            t: {
                "v5_corpus_1800_unique_identities": (
                    inv["v5_corpus_1800"]["per_type"].get(t, {}).get("unique_identities", 0)
                ),
                "run_813_unique_identities": (
                    inv["run_2026_09_30_813"]["per_type"].get(t, {}).get("unique_identities", 0)
                ),
                "gap_to_target_using_v5_corpus": max(
                    0, TARGET - inv["v5_corpus_1800"]["per_type"].get(t, {}).get("unique_identities", 0)
                ),
            }
            for t in MAIN_TYPES
        },
    }
    (A1 / "DATA-GAPS-SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    print(f"rows={len(ROWS)} -> {out}")
    for t in MAIN_TYPES:
        e = summary["main_type_gap_from_single_largest_known_source"][t]
        print(f"  {t:9s} v5_unique_identities={e['v5_corpus_1800_unique_identities']:5d} "
              f"run813_unique_identities={e['run_813_unique_identities']:5d} "
              f"gap_to_{TARGET}={e['gap_to_target_using_v5_corpus']:5d}")
    print("v6 new types with 0 generated units:",
          len([r for r in ROWS if r["dataset"] == "v6_registry"]))
    print("temporary-secret types with 0 generated units:",
          len([r for r in ROWS if r["dataset"] == "temporary_secrets"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
