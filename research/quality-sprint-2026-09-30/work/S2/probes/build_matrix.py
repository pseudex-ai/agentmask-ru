"""Derive S2/GAP-MATRIX.json from the executed probe JSON + the fixture.

Every number in the matrix is computed from probes/semantic_probe.json, which
was produced by semantic_probe.py against the pinned engine. Rows labelled
method=read are facts read from source (with pointers), never measured.
"""

from __future__ import annotations

import json
import os
import re

S2 = "/Users/igor/Projects/Obscura-hop-audit/research/quality-sprint-2026-09-30/work/S2"
PROBE = os.path.join(S2, "probes/semantic_probe.json")
FIXTURE = os.path.join(S2, "EPISODES.jsonl")
OUT = os.path.join(S2, "GAP-MATRIX.json")

# Person-identifying span types the engine can mint for a subject mention.
SUBJECT_TYPES = {"NAME", "PHONE", "SNILS", "INN", "PASSPORT", "INTL_PASSPORT",
                 "CARD", "ACCOUNT", "EMAIL", "OMS", "BIRTH_CERT", "DRIVER_LICENSE"}

# Facts read from source, each with an exact pointer. method=read.
READ_INVENTORY = [
    {"fact": "No semantic key types a salary/income/diagnosis/conviction/debt value.",
     "method": "read", "source": "prototype/licensing/assets_source.py#L1334-L1417",
     "detail": "KEY_TYPE and CTX_TYPES hold identity/document/credentials keys only; "
               "searching both maps for диагноз/зарплат/доход/судим/задолженност/долг returns nothing."},
    {"fact": "The MEDICAL recognizer is a leased stem gazetteer of named conditions.",
     "method": "read", "source": "prototype/licensing/assets_source.py#L1027-L1042",
     "detail": "~24 condition stems + explicit inflection sets for рак/спид; it types a WORD, "
               "with no subject binding and no notion of the relation."},
    {"fact": "The is-no-renderer fallback mints a deterministic REDACTED<digest> marker.",
     "method": "read", "source": "prototype/pseudex/vault.py#L1920-L1929",
     "detail": "MEDICAL and AGE have no format-preserving fake; the model sees REDACTED<6 hex>, "
               "identical for the same value. Restorable through the vault, but not a faithful substitute."},
    {"fact": "AGE/MEDICAL count as sentence-is-about-a-person evidence for the context layer.",
     "method": "read", "source": "prototype/pseudex/context.py#L114-L120",
     "detail": "A diagnosis word licenses person-association for dates nearby; it is used as a signal, "
               "not as a protected relation."},
    {"fact": "The suite asserts isolated MEDICAL must be caught, and legal-person debt must not be.",
     "method": "read", "source": "prototype/test_coverage_152fz.py#L48,L57-L70",
     "detail": "Current contract: the WORD is a type; the legal person has no data subject."},
    {"fact": "Dates follow an ASSOCIATION rule: a bare date is not personal data until tied to a person.",
     "method": "read", "source": "wiki/INVARIANTS.md#L154-L160",
     "detail": "The same structural question S2 asks about attributes is already decided for dates — "
               "and the MEDICAL arm does not follow it (DX-04 measured below is masked standalone)."},
    {"fact": "Prior registry research already classifies salary/conviction as values/categories, not patterns.",
     "method": "read", "source": "research/2026-08-16-vertical-pii-registry.md#L346-L371",
     "detail": "No vendor covers them for Russian; the report explicitly puts them in the detect_quasi-shaped class."},
]


def load() -> tuple[list[dict], list[dict]]:
    episodes = [json.loads(l) for l in open(FIXTURE, encoding="utf-8") if l.strip()]
    probe = json.load(open(PROBE, encoding="utf-8"))
    return episodes, probe["episodes"]


def token_remains(token: str, masked: str) -> bool:
    """Is this attribute token of the written phrase still readable in the output?"""
    if token.isdigit():
        return token in "".join(ch for ch in masked if ch.isdigit())
    stem = token[:5].lower()
    return any(word.lower().startswith(stem)
               for word in re.findall(r"[А-Яа-яЁёA-Za-z]+", masked))


def classify(episode: dict, row: dict) -> dict:
    text, masked = row["text"], row["masked"]
    spans = row["spans"]
    subject_spans = [s for s in spans if s["type"] in SUBJECT_TYPES]
    subject_replaced = bool(subject_spans) and all(
        s["surface"] not in masked for s in subject_spans)

    dim = episode["dimension"]

    # The written attribute phrase is declared in the fixture BEFORE the run,
    # so a leftover token is measured, not chosen after seeing the output.
    attribute_tokens = [
        word
        for phrase in episode.get("attribute_phrase", [])
        for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", phrase)
    ]
    leftovers = [t for t in attribute_tokens if token_remains(t, masked)]

    subject_present = episode["subject_present"]
    if not subject_present:
        relation_state = "not_applicable_no_subject"
    elif not subject_spans:
        relation_state = "subject_not_detected"
    elif leftovers:
        relation_state = "relation_disclosed_by_attribute"
    else:
        relation_state = "relation_closed"

    return {
        "id": row["id"],
        "dimension": dim,
        "pair_role": episode["pair_role"],
        "form": episode["form"],
        "subject_present": subject_present,
        "engine_types": row["types"],
        "subject_span_types": sorted({s["type"] for s in subject_spans}),
        "subject_replaced": subject_replaced,
        "attribute_lexicon_in_clear": leftovers,
        "attribute_fully_masked": bool(leftovers) is False and bool(spans),
        "relation_state_measured": relation_state,
        "masked": masked,
        "roundtrip_identical": row["roundtrip_identical"],
        "marker_substitute": row["redaction_marker_visible"],
    }


def main() -> None:
    episodes, probe_rows = load()
    by_id = {r["id"]: r for r in probe_rows}
    classified = [classify(e, by_id[e["id"]]) for e in episodes]

    classes = {}
    for c in classified:
        dim = c["dimension"]
        bucket = classes.setdefault(dim, {
            "episodes": [], "positive": 0, "negative": 0,
            "relation_closed": 0, "relation_disclosed_by_attribute": 0,
            "subject_not_detected": 0, "not_applicable_no_subject": 0,
            "any_span": 0, "over_masked_negative": 0,
        })
        bucket["episodes"].append(c["id"])
        bucket["positive" if c["pair_role"] == "positive" else "negative"] += 1
        bucket[c["relation_state_measured"]] += 1
        if c["engine_types"]:
            bucket["any_span"] += 1
        if c["pair_role"] == "negative" and c["engine_types"]:
            bucket["over_masked_negative"] += 1

    payload = {
        "generated_from": {
            "probe_json": "work/S2/probes/semantic_probe.json",
            "fixture": "work/S2/EPISODES.jsonl",
            "engine_revision": "0bfda2363ef1a1d552e2ac093129b1026a86ad68",
        },
        "definitions": {
            "unit_of_protection": "the SUBJECT->ATTRIBUTE relation (152-ФЗ ст.3 п.1: information relating to an identifiable natural person), not an isolated word",
            "relation_closed": "subject mention replaced AND no attribute surface left in the masked text",
            "relation_disclosed_by_attribute": "subject replaced or unmatched, but the attribute value/word is still readable by the model",
            "subject_not_detected": "the subject is present in the text but no identifying span was found",
            "not_applicable_no_subject": "negative control; no person is referenced, nothing should be masked",
        },
        "measured_episodes": classified,
        "class_summary": classes,
        "read_inventory": READ_INVENTORY,
        "unknowns": [
            "Whether a host/agent actually re-associates a leftover attribute with the real subject from other fields in the same call is NOT measured here; only the surfaced value is.",
            "No production traffic was read; every episode is synthesized from the approved class list.",
            "Recall of the MEDICAL gazetteer over real Russian medical vocabulary is not measured; the probe tests 4 conditions + 2 lexical negatives.",
            "Whether any customer-facing contract promises semantic coverage is not checked here (no docs scan was in the S2 input scope).",
        ],
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(classes, ensure_ascii=False, sort_keys=True, indent=2))
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()
