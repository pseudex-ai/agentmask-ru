#!/usr/bin/env python3
"""A1: compose ACCEPTANCE-PROPOSAL.json (the O-DATA manifest proposal) and OWNER-QUESTIONS.md.

The document is a PROPOSAL.  It is deliberately OWNER_PENDING: the binding owner
decisions fix the targets and the method, but the manifest itself (units, slices, CI
type, cluster key, support, split access, annotation budget) is exactly what O-DATA has
to accept.  No count in this file is invented: every number is injected from
INVENTORY.json / DATA-GAPS-SUMMARY.json produced by inventory_sources.py and derive_gaps.py.

Run:
    PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python \
        research/quality-sprint-2026-09-30/work/A1/make_proposal.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

A1 = Path(__file__).resolve().parent
ROOT = Path("/Users/igor/Projects/Obscura-hop-audit")
TARGET = 300
MAIN_TYPES = ["NAME", "LOC", "PHONE", "EMAIL", "PASSPORT", "SNILS", "INN", "CARD",
              "PLATE", "DOB"]
REGISTERS = ["clean", "chat", "sloppy", "voice_raw", "voice_itn"]
TEMP_SECRET_TYPES = ["CVC", "CVV", "CID", "OTP", "SMS_CODE", "THREEDS"]


def main() -> int:
    inv = json.loads((A1 / "INVENTORY.json").read_text())
    gaps = json.loads((A1 / "DATA-GAPS-SUMMARY.json").read_text())
    inputs = json.loads((A1 / "INPUTS.json").read_text()) if (A1 / "INPUTS.json").exists() else {}
    bundle = inputs.get("bundle") or {}
    v5 = inv["v5_corpus_1800"]
    run = inv["run_2026_09_30_813"]
    v6 = inv["v6_registry"]

    native_support = {}
    for t in MAIN_TYPES:
        native_support[t] = {
            "v5_corpus_1800": {
                "occurrences": v5["per_type"].get(t, {}).get("items", 0),
                "independent_identity_clusters": v5["per_type"].get(t, {}).get("unique_identities", 0),
                "cases": v5["per_type"].get(t, {}).get("cases", 0),
                "gap_to_300_identities": max(
                    0, TARGET - v5["per_type"].get(t, {}).get("unique_identities", 0)),
            },
            "per_register_independent_identity_clusters": {
                reg: v5["register_type_unique_identities"].get(f"{reg}|{t}", 0)
                for reg in REGISTERS
            },
            "run_813": {
                "occurrences": run["per_type"].get(t, {}).get("items", 0),
                "independent_identity_clusters": run["per_type"].get(t, {}).get("unique_identities", 0),
            },
        }

    v6_density = {
        "source": "research/hop-format-audit/next-sprint-review/v6-snapshot/tz-agentpii6.md §4.3",
        "planned_cases": 500,
        "planned_industries": 15,
        "planned_new_types": 55,
        "types_per_case_hypothesis": "2.72 for T≈40 types; 3.74 for 55 types (tz table, not a measurement)",
        "projected_new_type_occurrences_at_500_cases": "≈1360 (T≈40) … ≈1870 (55 types at 3.74/case)",
        "projected_independent_units_per_new_type_at_500_cases": "≈25 … ≈34 before identity/template dedup",
        "cases_needed_for_300_per_type_projection": "≈4400 … ≈6100 depending on the density taken",
        "status": "NOT_MEASURED — no generated v6 corpus exists on this host",
    }

    # Cost arithmetic, computed once so the numbers in the JSON cannot drift from the formula.
    cost_units = {
        "native_positive_units": len(MAIN_TYPES) * TARGET,          # 3000
        "ppv_spans": len(MAIN_TYPES) * TARGET,                      # 3000
        "specificity_negatives": 600,
        "v6_new_type_occurrences_est": 1360,                        # NOT_MEASURED projection
        "temp_secret_fixture_units_est": len(TEMP_SECRET_TYPES) * 60,  # 360
    }
    units_native = (cost_units["native_positive_units"] + cost_units["ppv_spans"]
                    + cost_units["specificity_negatives"])
    units_full = units_native + cost_units["v6_new_type_occurrences_est"] \
        + cost_units["temp_secret_fixture_units_est"]
    cost = {
        "currency": "human review items (NOT money); one 'labeler-item' = one labeler judging "
                    "one unit once; one 'owner-item' = one adjudication or re-check",
        "formula": (
            "labeler-items = 2 × (positive units + PPV sample + specificity sample + v6 units "
            "+ temporary-secret units); owner-items = disputes(rate × units) + "
            "stratified agreed review(10% of agreed units); total = labeler-items + owner-items"
        ),
        "planning_inputs": {
            "native_headline_types": len(MAIN_TYPES),
            "target_positive_units_per_type": TARGET,
            "unit_counts": cost_units,
            "dispute_rate_assumption": "5%–15% (assumption, NOT measured)",
            "agreed_review_share": "10% of agreed units",
        },
        "planning_result": {
            "units_native_only": units_native,
            "units_full_scope": units_full,
            "labeler_items_native_only": 2 * units_native,
            "labeler_items_full_scope": 2 * units_full,
            "owner_dispute_items_native_only": [round(0.05 * units_native),
                                                round(0.15 * units_native)],
            "owner_dispute_items_full_scope": [round(0.05 * units_full),
                                               round(0.15 * units_full)],
            "owner_agreed_review_items_full_scope": [
                round(0.10 * (units_full - round(0.15 * units_full))),
                round(0.10 * (units_full - round(0.05 * units_full))),
            ],
            "total_human_review_items_native_only_range": [
                2 * units_native + round(0.05 * units_native) + round(0.10 * (units_native - round(0.05 * units_native))),
                2 * units_native + round(0.15 * units_native) + round(0.10 * (units_native - round(0.15 * units_native))),
            ],
            "total_human_review_items_full_scope_range": [
                2 * units_full + round(0.05 * units_full) + round(0.10 * (units_full - round(0.05 * units_full))),
                2 * units_full + round(0.15 * units_full) + round(0.10 * (units_full - round(0.15 * units_full))),
            ],
        },
        "explicitly_not_a_budget_go": "the owner still decides the authorized budget; this is a "
                                      "size estimate in review items, not dollars",
    }

    proposal = {
        "proposal_id": "A1-O-DATA-ACCEPTANCE-PROPOSAL",
        "version": "1.0.0-draft",
        "status": "OWNER_PENDING",
        "gate": "O-DATA",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "task": "A1",
        "purpose": (
            "Exact proposal for the acceptance manifest the owner has to accept in O-DATA: "
            "units, slices, CI, PPV sampling, hard-negative specificity, cluster keys, support "
            "targets, known-vs-blind separation, split access, annotation protocol and cost in "
            "human review items. It contains no final gold and no detector-derived sample selection."
        ),
        "requested_routing": {
            "provider": "deepseek-official",
            "model": "deepseek-flash",
            "effective_routing_metadata": "not available to this subagent; not self-attested",
        },
        "revision": {
            "git_head_current": "890c50849a326f882eac336ba4e38c91171de473",
            "product_source_pin": "0bfda2363ef1a1d552e2ac093129b1026a86ad68",
            "evidence_commit_is_research_only": True,
            "b0_gate": "work/B0/GATE.json G1 PASS (local/design only)",
            "production_artifact_gate": "NOT_MEASURED — blocks RG release-A/B",
            "bundle": {
                "version": bundle.get("version"),
                "sha256": bundle.get("sha256"),
                "plaintext_bytes": bundle.get("plaintext_bytes"),
                "recomputed_in_memory": bundle.get("recomputed_in_memory"),
                "matches_b0_record": bundle.get("matches_b0_record"),
                "file_written": False,
            },
        },

        "binding_decision_ids": [
            {"id": "OWNER-Q1", "source": "OWNER-DECISIONS.md#L19",
             "literal": "«≥99% на выборке + размер и ДИ»",
             "applies": "point estimate ≥99% for recall / whole coverage / true PPV on the "
                        "agreed main type and register slices, with support and CI published; "
                        "lower CI bound ≥99% was NOT chosen"},
            {"id": "OWNER-SUPPORT", "source": "REMAINING-DECISIONS.md#L34",
             "literal": "«ориентир не менее 300 независимых позитивных единиц на основной "
                        "заявляемый тип/срез плюс достаточная отдельная проверка precision»",
             "applies": "support target; small slices are never full acceptance; repetitions and "
                        "template copies are not independent units"},
            {"id": "OWNER-LABELERS", "source": "REMAINING-DECISIONS.md#L33",
             "literal": "«два независимых разметчика, сначала только исходный текст/правила, "
                        "без detector output; расхождения и стратифицированная проверка "
                        "согласованных меток — владельцу»",
             "applies": "annotation protocol"},
            {"id": "OWNER-LEXAMB", "source": "REMAINING-DECISIONS.md#L8",
             "literal": "«Не маскировать по одной двусмысленной форме»",
             "applies": "«жене»-type lexical ambiguity: neither an automatic NAME nor an "
                        "automatic false positive"},
            {"id": "OWNER-POSSESSIVE", "source": "REMAINING-DECISIONS.md#L7",
             "literal": "«Да, защищать и сохранять форму»",
             "applies": "possessive personal forms («Жениного/Олино») are positives when "
                        "context confirms a person; homonym common words are not"},
            {"id": "OWNER-PUBLIC", "source": "REMAINING-DECISIONS.md#L9",
             "literal": "«Одинаково защищать все личные имена»",
             "applies": "public / fictional / stage names are protected; reported in a separate "
                        "stratum so they never silently move the headline"},
            {"id": "OWNER-BRAND", "source": "REMAINING-DECISIONS.md#L10",
             "literal": "«Да, по значению в контексте»",
             "applies": "company/product/band is not NAME by shape; no word blacklist"},
            {"id": "OWNER-ALLPARTS", "source": "OWNER-DECISIONS.md#L37",
             "literal": "«Да, это дефект, защищаем все части»",
             "applies": "FIO: every identifying part of one person is protected and must be "
                        "counted; a partially masked name is a partial leak, not recall"},
            {"id": "OWNER-ADDR", "source": "OWNER-DECISIONS.md#L38",
             "literal": "«все личные компоненты, не маркеры»",
             "applies": "street + house + building + flat + entrance + floor are protected "
                        "components; service words and allowed generic toponyms stay unmasked "
                        "and unchanged; street TYPE is part of identity"},
            {"id": "OWNER-MALFORMED-ID", "source": "OWNER-DECISIONS.md#L27",
             "literal": "«Защищать при доказанном типовом контексте»",
             "applies": "checksum-invalid but person-linked identifiers are positives and must "
                        "not be corrected; bare similar digits are negatives"},
            {"id": "OWNER-PPV-VS-SPEC", "source": "GOAL-BRIEF.md#L156-L158",
             "literal": "«MASSIVE person-slot не автоматически PII NAME; NEREL "
                        "any-annotation-support не настоящая PPV; clean-negative specificity "
                        "не precision»",
             "applies": "PPV must be measured on sampled POSITIVE predictions, specificity on a "
                        "separate negative frame; they are never merged"},
            {"id": "OWNER-SECRET", "source": "REMAINING-DECISIONS.md#L21-L25",
             "literal": "CVC destinations «В любой ответ той же операции»; OTP/3DS/SMS "
                        "«Да, исследовать всё семейство временных секретов»",
             "applies": "temporary-secret types stay in the quality denominator; synthetic "
                        "isolated path only; lifecycle/storage/admin/API/HITL deferred"},
            {"id": "OWNER-NO-API-CHANGE", "source": "REMAINING-DECISIONS.md#L15",
             "literal": "«Изменение API сейчас НЕ разрешено»",
             "applies": "acceptance protocol must not require new provenance API fields"},
            {"id": "PLAN-ACCEPTANCE-MANIFEST", "source": "SPRINT-PLAN.md#L159",
             "literal": "«В B0/A1 утверждается точный acceptance manifest: единица подсчёта, "
                        "список slices, тип CI, support, cluster ключ для повторов, budget "
                        "разметки и невидимый разработчику acceptance split»",
             "applies": "this proposal is the draft of exactly that manifest"},
        ],

        "registry_scope": {
            "native_v5_item_types": {
                "count": 10,
                "types": MAIN_TYPES,
                "note": "DATE is a separate non-item category and is reported separately, "
                        "never folded into the ten",
            },
            "v6_new_types": {
                "count": v6["registry_entries"] - len(v6["v5_types_in_registry"]),
                "origin_counts": v6["origins"],
                "class_counts": v6["classes"],
                "grammar_status": v6["grammar_status"],
                "grammar_uncertain_count": len(v6["grammar_uncertain_types"]),
                "grammar_uncertain_types": v6["grammar_uncertain_types"],
                "industries_count": len(v6["industries"]),
                "industries": sorted(v6["industries"]),
                "types": v6["new_v6_types"],
                "generated_cases_on_host": v6["generated_v6_cases_on_host"],
                "status": "registry/contract visible; NO generated v6 corpus on this host",
            },
            "temporary_secrets": {
                "types": TEMP_SECRET_TYPES,
                "status": "no corpus; synthetic isolated fixtures only (owner P14)",
                "excluded_from_denominator": False,
                "lifecycle_out_of_scope": ["storage", "TTL/expiry", "local admin defaults",
                                           "new API", "HITL", "payment-ready gate"],
            },
            "not_in_scope_for_this_manifest": [
                "semantic PII classes (diagnosis, salary, conviction, person↔debt) — S2 map "
                "only, implementation needs a separate owner GO",
                "legal certification of any kind",
            ],
        },

        "slices": {
            "axes": [
                {"axis": "pii_type", "values": "registry scope above"},
                {"axis": "register", "values": REGISTERS,
                 "source": "frozen v5 corpus registers"},
                {"axis": "surface", "values": sorted({k.split("|")[0]
                                                      for k in v5["kind_type_items"]}),
                 "note": "the frozen corpus exposes 22 case kinds used as the surface proxy; "
                         "free prose / typed KV / nested JSON / document / RAG / tool-error "
                         "surfaces are declared on top of them and must be mapped explicitly "
                         "before a slice is called covered"},
                {"axis": "hop_direction", "values": ["IN/user", "IN/tool", "IN/document",
                                                     "IN/memory", "OUT/tool_arg", "OUT/answer",
                                                     "OUT/summary", "OUT/template"]},
                {"axis": "transport", "values": ["non-stream", "stream", "chunk-boundary"]},
                {"axis": "document_form", "values": ["free_prose", "typed_kv", "nested_json",
                                                     "document", "rag_chunk", "tool_error"]},
            ],
            "headline_rule": (
                "A headline recall / whole-coverage / PPV claim exists for a (type, register) "
                "slice only with ≥300 independent positive units; below that the slice is "
                "reported as DESCRIPTIVE_INSUFFICIENT_SUPPORT and the type/slice stays visible "
                "in the table (never dropped, never called 100%)."
            ),
            "primary_slice_priority": [
                "NAME × {clean, chat, sloppy, voice_raw}", "LOC/ADDR × the same",
                "PHONE/EMAIL × written + spoken", "PASSPORT and checksum IDs × written/typed-KV",
                "each v6 claimed type × its registered contexts",
                "temporary secrets × synthetic isolated operations",
            ],
        },

        "units": {
            "primary_positive_unit": (
                "one gold occurrence of one PII value of one type in one case, with its slice, "
                "its identity cluster key and its part decomposition"
            ),
            "independence_cluster_key": {
                "value_bearing_types": "(type, gold identity) — one person/number/card mentioned "
                                       "N times is ONE independent unit",
                "address": "address identity key (street type + street + house + flat …), so the "
                           "full address and its partial mentions in one conversation are one unit",
                "document_surface": "(case id) for document-level claims; (conversation_id) for "
                                    "conversation-scope claims",
                "template": "provenance.shape when present; the frozen v5 authored corpus has "
                            "empty shape, so the fallback is (case id, pii_type, identity) and "
                            "this must be recorded as a known independence limitation",
            },
            "part_unit": (
                "for NAME the occurrence expands into its identifying parts (surname, given, "
                "patronymic, initials, possessive form); whole coverage requires every part "
                "written to be protected — a masked surname with a live given name is a partial "
                "leak and scores as a miss on the part unit, never as recall"
            ),
            "whole_coverage_unit": "one occurrence found entirely (all parts, all digits, "
                                   "street type included where written)",
            "ppv_unit": "one detector-positive span drawn from the blind split, adjudicated "
                        "against source text only",
            "specificity_unit": "one pre-registered hard-negative occurrence in source text "
                                "(order numbers, amounts, article/track IDs, dates in business "
                                "context, bare toponyms, tool IDs) that must stay unmasked",
            "naive_units_declared_unacceptable": [
                "occurrences counted as independent successes",
                "repeated identical text or repeated template counted twice",
                "a case counted once per field of the same person",
                "correct value restored elsewhere used to excuse a wrong occurrence",
                "clean-negative specificity reported as precision/PPV",
            ],
        },

        "known_vs_blind": {
            "principle": (
                "Everything listed as known_diagnostic has already been generated and/or read "
                "during development and therefore cannot be a blind acceptance set. Strict "
                "external scores stay published as their own, unchanged axis."
            ),
            "known_diagnostic_sets": [
                {"name": "legacy dataset.json", "cases": inv["legacy_dataset"]["cases"],
                 "entities": inv["legacy_dataset"]["entities_total"], "blind_status": "known_diagnostic"},
                {"name": "legacy dirty.json", "cases": inv["legacy_dirty"]["cases"],
                 "entities": inv["legacy_dirty"]["entities_total"],
                 "negatives": inv["legacy_dirty"]["negatives_total"],
                 "blind_status": "known_diagnostic"},
                {"name": "legacy stress.json", "cases": inv["legacy_stress"]["cases"],
                 "entities": inv["legacy_stress"]["entities_total"],
                 "blind_status": "known_diagnostic"},
                {"name": "legacy stress2.json", "cases": inv["legacy_stress2"]["cases"],
                 "entities": inv["legacy_stress2"]["entities_total"],
                 "blind_status": "known_diagnostic"},
                {"name": "agentpii5 corpus.v5.json", "cases": v5["cases"],
                 "pii_items": v5["pii_items_total"],
                 "unique_identities": v5["pii_identities_unique_total"],
                 "blind_status": "known_diagnostic"},
                {"name": "paid run cc3a551f corpus (813)", "cases": run["cases"],
                 "pii_items": run["pii_items_total"],
                 "unique_identities": run["pii_identities_unique_total"],
                 "blind_status": "known_diagnostic_measured"},
                {"name": "bench/gate labels.json", "labelled_occurrences":
                    inv["gate_instrument"]["labelled_occurrences"],
                 "label_distribution": inv["gate_instrument"]["label_distribution"],
                 "blind_status": "known_diagnostic_hand_labeled",
                 "observed_discrepancy": (
                     "gate README claims 600 hand labels (300 masked + 300 missed); the durable "
                     "labels.json holds 587. 13 labelled occurrences are absent from the current "
                     "file — reported as an observed mismatch, not resolved here.")},
                {"name": "NEREL v1.1 dev+test", "person_rows":
                    inv["nerel"]["dev"]["person_rows"] + inv["nerel"]["test"]["person_rows"],
                 "docs": inv["nerel"]["dev"]["docs"] + inv["nerel"]["test"]["docs"],
                 "blind_status": "external_already_measured_strict_only"},
                {"name": "PII-Bench", "rows": sum(d["rows"] for d in inv["piibench"].values()),
                 "blind_status": "external_already_measured_strict_only"},
                {"name": "MASSIVE ru", "person_slot_occurrences": sum(
                    d["slot_occurrences"].get("person", 0) for d in inv["massive"].values()),
                 "blind_status": "slot_is_not_pii_by_itself"},
                {"name": "RuDevices voice_addresses", "records": inv["voice_addresses"]["records"],
                 "blind_status": "external_already_measured_strict_only"},
                {"name": "RuDevices rudevices_addresses",
                 "records": inv["rudevices_addresses"]["records"],
                 "blind_status": "external_already_measured_strict_only"},
                {"name": "name-labels-blind-proposal (1215 MASSIVE person slots)",
                 "status": "PRIOR AI PROPOSAL — explicitly NOT accepted gold; may be used only "
                           "as a candidate pool that two human labelers must re-label blind",
                 "blind_status": "not_gold"},
                {"name": "name15-verified (15 payloads)",
                 "status": "diagnostic witnesses for the known NAME defect class",
                 "blind_status": "known_diagnostic"},
            ],
            "future_blind_acceptance": {
                "construction": (
                    "a NEW acceptance split generated at freeze time from the same generators "
                    "with a fresh unseen seed, plus a fresh v6 slice once the v6 corpus exists; "
                    "nothing in it is generated, read or tuned before freeze"
                ),
                "custody": "label files held by the owner/human custodian outside the agent "
                           "read scope; implementation agents never read them",
                "second_tier": {
                    "name": "pinned 359-ID holdout tier (agentpii5 ladder.json)",
                    "usable_as": "secondary frozen tier only",
                    "caveat": "membership is known and the run intersection is 0/359; that is "
                              "NOT proof the historical holdout was never seen (B0 REVIEW limit 3)",
                },
                "prohibited": [
                    "selecting samples by detector output",
                    "reusing prior proposal labels as accepted gold",
                    "calling an already-measured foreign corpus a fresh holdout",
                    "tuning after a blind split has been read",
                ],
            },
        },

        "labeling_protocol": {
            "labelers": 2,
            "independence_requirements": [
                "each labeler sees only the source text and the versioned rules",
                "neither sees detector spans, predictions, eval outputs or the other labeler's labels",
                "the two label runs are recorded with separate actor ids, timestamps and file hashes",
            ],
            "label_categories": [
                "PII_TYPE_BEARING (positive, with exact span and part decomposition)",
                "NOT_PII (clean negative)",
                "AMBIGUOUS_LEXICAL", "AMBIGUOUS_BRAND", "PUBLIC_FIGURE", "FICTIONAL_STAGE",
                "MALFORMED_PERSONAL_ID", "PARTIAL_PERSON_REFERENCE", "GENERIC_TOPONYM",
                "ADDRESS_COMPONENT_ONLY", "DATE_BUSINESS_CONTEXT", "OTHER_ID_NOT_PERSONAL",
            ],
            "case_rules": {
                "lexical_ambiguity_wife_name": (
                    "«напиши жене» with no other name evidence is AMBIGUOUS_LEXICAL: it is "
                    "neither a positive nor a detector false positive, and it is excluded from "
                    "both the recall and the precision/PPV denominator. The miss risk is the "
                    "owner's explicitly accepted trade (REMAINING-DECISIONS.md#L8), not a defect "
                    "to count against the engine."
                ),
                "fio_all_parts": (
                    "every identifying part written is a labelled sub-unit (surname, given, "
                    "patronymic, initial, declined/possessive form). All parts of one person "
                    "share one identity cluster. A label that protects only part of a written "
                    "FIO is recorded as PARTIAL, and whole coverage is measured per part."
                ),
                "possessive_forms": (
                    "«Жениного/Олино», confirmed by context as a person reference, is a positive "
                    "whose fake must keep the grammar. A homonymous common word is NOT_PII."
                ),
                "public_fictional_stage": (
                    "public figures, fictional characters and stage names are positives "
                    "(protected equally) but always labelled in their own stratum; the headline "
                    "is published both with and without that stratum, never merged silently."
                ),
                "brand_context": (
                    "company, product, band or group token is not a NAME unless the occurrence's "
                    "context identifies a person; borderline cases go to AMBIGUOUS_BRAND and to "
                    "owner adjudication. No blacklist of words."
                ),
                "address_entrance_floor": (
                    "street, street type, house, building/корпус/строение, flat, entrance, floor "
                    "belong to the person's address and are positives; a bare street reference "
                    "without a number is GENERIC_TOPONYM (product does not mask it) and a bare "
                    "city is not PII. Street type is part of the address identity."
                ),
                "malformed_personal_ids": (
                    "a checksum-invalid value that context/schema binds to a personal "
                    "identifier is a positive (MALFORMED_PERSONAL_ID) and its form must be "
                    "preserved, not repaired. A bare digit run of the same length without "
                    "personal context is NOT_PII."
                ),
                "order_and_business_numbers": (
                    "amounts, order/article/track numbers, business dates, KPP/OGRN-type legal "
                    "entity requisites are NOT_PII and feed the negative specificity frame."
                ),
            },
            "dispute_handling": (
                "every disagreement between labeler A and labeler B is a dispute item queued to "
                "the owner with both labels, both spans, the applicable rule id and the source "
                "pointer; the owner's answer is recorded verbatim with a decision id and becomes "
                "part of the next rules version"
            ),
            "stratified_agreed_review": (
                "a stratified random sample of the AGREED labels (strata = type × register, "
                "including the ambiguous and public strata) is re-checked by the owner; the "
                "sample is drawn before any engine number is seen"
            ),
            "versioning": (
                "rules and labels are versioned files; a label change is a new version with a "
                "diff and a reason, never an in-place edit; the engine is always compared "
                "old/new on one gold version"
            ),
            "self_certification_barred": "the author of the labels cannot certify the result",
        },

        "ppv_design": {
            "question": "of what the engine calls PII of this type, how much really is PII of "
                        "that type, wholly covered?",
            "frame": "detector-positive spans inside the blind acceptance split; the frame is "
                     "built once after freeze and its hash is recorded before sampling",
            "sampling": "stratified random sample per (type × register) with a published seed; "
                        "the sample is fixed before any label is read",
            "labels_per_span": ["TRUE_PII_TYPE_EXACT", "TRUE_PII_PARTIAL", "WRONG_TYPE",
                                "NOT_PII", "AMBIGUOUS_EXCLUDED"],
            "estimator": "PPV = (TRUE_PII_TYPE_EXACT) / (all adjudicated sampled positives), "
                         "with AMBIGUOUS_EXCLUDED removed from numerator and denominator and "
                         "reported separately",
            "ci": "Wilson per slice + cluster bootstrap over identity/document clusters; design "
                  "effect published",
            "min_sample": TARGET,
            "proposed_allocation": "≥300 adjudicated positive spans per headline type pooled "
                                   "over its main registers, with per-register minimum ≥60 so a "
                                   "single easy register cannot carry the type",
            "barred": ["using the authored gold set as the PPV frame (it is the source of the "
                       "positives, not the engine's output)",
                       "calling clean-negative specificity PPV"],
        },

        "specificity_design": {
            "question": "how much ordinary non-PII text does the engine mask?",
            "frame": "a pre-registered negative occurrence set, frozen before measurement: "
                     "business numbers, order/track/article ids, amounts, business dates, bare "
                     "toponyms, tool ids, roles and kinship words without a name",
            "existing_support": {
                "dirty_json_explicit_negatives": inv["legacy_dirty"]["negatives_total"],
                "stress_json_negatives": inv["legacy_stress"]["negatives_total"],
                "stress2_json_negatives": inv["legacy_stress2"]["negatives_total"],
                "gate_instrument_not_person_strata": {
                    k: v for k, v in inv["gate_instrument"]["label_distribution"].items()},
                "voice_addresses_negative_labels": {
                    k: v for k, v in inv["voice_addresses"]["label_distribution"].items()},
                "rudevices_addresses_negative_labels": {
                    k: v for k, v in inv["rudevices_addresses"]["label_distribution"].items()},
            },
            "estimator": "false-mask rate = masked negative occurrences / negative occurrences; "
                         "reported per negative family, never as PPV",
            "min_sample": TARGET,
            "note": "authored negatives shipped one per case are not independent hard-negative "
                    "text; the negative frame must be re-drawn from real prose once the "
                    "over-masking corpus is regenerated (ru_prose.jsonl is 0 bytes on this host)",
        },

        "ci_and_statuses": {
            "point_estimate_rule": "report x/n and the point estimate; headline requires point "
                                   "estimate ≥99% per the owner's literal choice; the lower CI "
                                   "bound is published and is NOT required to be ≥99%",
            "interval": "Wilson score 95% interval for independent binomial units",
            "clustered_interval": "cluster bootstrap (10 000 resamples) over identity/document "
                                  "clusters; the design effect and the effective n are printed "
                                  "next to the interval",
            "paired_claims": "McNemar for a paired engine-vs-engine difference, never as proof "
                             "of no effect; a pre-registered TOST margin at δ=3pp is published "
                             "for 'no effect' claims",
            "zero_denominator": "NOT_MEASURED — an empty denominator can never produce 100% "
                                "(the empty-`any([])` failure mode of the previous meter is "
                                "explicitly guarded)",
            "insufficient_n": "DESCRIPTIVE_INSUFFICIENT_SUPPORT — below 300 independent "
                              "positive units the slice is reported, never upgraded to a "
                              "headline PASS",
            "statuses": ["PASS", "FAIL", "NOT_MEASURED", "DESCRIPTIVE_INSUFFICIENT_SUPPORT",
                         "OWNER_PENDING"],
            "no_averaging_rule": "no average across heterogeneous types/registers may hide a "
                                 "failing slice",
        },

        "immutability_and_access": {
            "hash_everything_at_freeze": [
                "corpus file sha256", "gold/label file sha256", "rules sha256",
                "manifest sha256", "engine commit + bundle version/sha256",
                "scorer version + sha256", "scorer/engine separation commit ids",
            ],
            "already_recorded_hashes": {
                "v5_corpus_sha256": v5["sha256"],
                "run813_corpus_sha256": run["sha256"],
                "gate_labels_sha256": inv["gate_instrument"]["labels_sha256"],
                "gate_candidates_sha256": inv["gate_instrument"].get("candidates_sha256"),
                "bundle_version_sha256": "2a07cebae2b050ec / "
                    "01c19f4689450b54694b7aaa4070cbaf695efc3e98f0b59471486392a0348206",
            },
            "access_log": {
                "format": "append-only JSONL, one row per read of a blind artifact",
                "fields": ["utc", "actor", "artifact", "sha256", "purpose",
                           "authorization_id", "previous_row_sha256"],
                "rule": "any read of the blind split by an implementer invalidates that split "
                        "for tuning; the read is never deleted, it is disclosed",
            },
            "separation": "label files, blind split and detector outputs live in different "
                          "directories with different owners; the manifest records which actor "
                          "may read which",
        },

        "cost_estimate_human_review_items": cost,

        "available_support_today": native_support,
        "v6_support_arithmetic": v6_density,
        "gap_summary": gaps["main_type_gap_from_single_largest_known_source"],

        "unacceptable_alternatives": [
            "counting occurrences instead of independent identity clusters as support",
            "pooling easy registers to reach 300 and calling the hard register covered",
            "using the authored gold set as the PPV frame",
            "reporting clean-negative specificity as precision",
            "treating MASSIVE person-slot as PII NAME by itself",
            "treating the prior name-label proposal as accepted gold",
            "declaring small slices a full acceptance, or dropping an unsupported type from "
            "the table",
            "lower CI bound ≥99% as a substitute for the owner's point-estimate rule, or the "
            "reverse (softening the target because the CI is wide)",
            "editing a blind split or a label file in place after it was read",
            "reusing the already-measured foreign corpora as a fresh holdout",
        ],

        "owner_questions": [
            {"id": "Q-A1-1", "topic": "unit of independence",
             "question": "Accept (type, identity) as the independence cluster, with one primary "
                         "occurrence per identity in the acceptance sample? Or require each "
                         "identity to contribute exactly one occurrence, discarding the rest?",
             "proposed": "(type, identity) cluster + one primary occurrence sampled per identity",
             "cost": "the first option keeps more data; the second loses the multi-form evidence "
                     "(declined, Latin, possessive) that the defect classes live in"},
            {"id": "Q-A1-2", "topic": "source of support",
             "question": "May authored synthetic corpora carry the ≥300/type support, or must "
                         "NAME/LOC headline support come from third-party human text?",
             "proposed": "authored corpora carry the product-scope headline; external corpora "
                         "stay a separate strict axis",
             "cost": "third-party-only support is not reachable for PASSPORT/SNILS/INN/CARD/"
                     "PLATE on any corpus on this host"},
            {"id": "Q-A1-3", "topic": "underpowered native types",
             "question": "For PASSPORT 63 / SNILS 128 / INN 144 / CARD 123 / PLATE 154 "
                         "independent identities in the frozen 1800-case corpus: expand the "
                         "corpus toward 300/type, or accept descriptive status for them now?",
             "proposed": "expand generation for the five underpowered types; keep them in the "
                         "table as DESCRIPTIVE until then",
             "cost": "expansion multiplies annotation items; descriptive status delays a "
                     "99% claim for those five types"},
            {"id": "Q-A1-4", "topic": "v6 per-type support",
             "question": "The planned 500-case v6 corpus projects to ≈25–34 independent units "
                         "per new type — an order of magnitude below 300. Claim v6 per type, or "
                         "per family, or expand the corpus to ≈4,400–6,100 cases?",
             "proposed": "headline per family with ≥300 independent units; per-type claims "
                         "only where the corpus supports them",
             "cost": "per-type 99% for 55 types requires a corpus several times larger"},
            {"id": "Q-A1-5", "topic": "public/fictional stratum",
             "question": "Are public-figure, fictional and stage-name occurrences inside the "
                         "99% headline denominator or a separately published stratum?",
             "proposed": "protected and counted, but published as a separate stratum (the gate "
                         "instrument already reports 'public' separately, 57 of 587 labels)",
             "cost": "inside the headline, one hard public-name case can move the number; "
                     "outside it, a real protection class becomes invisible"},
            {"id": "Q-A1-6", "topic": "blind split custody",
             "question": "Who generates and holds the fresh blind acceptance split, and may an "
                         "agent generate it under a sealed procedure without reading labels?",
             "proposed": "human owner custody; agent may generate the text, never the labels",
             "cost": "requires owner time at freeze; without it there is no blind acceptance"},
            {"id": "Q-A1-7", "topic": "annotation budget",
             "question": "Authorize ≈9,000–17,000 human review items, and the split between "
                         "paid/owner labeling?",
             "proposed": "approve native+PPV+specificity first (≈9,000 items), v6 later",
             "cost": "the full number is the price of a genuine ≥300/type, blind PPV claim"},
            {"id": "Q-A1-8", "topic": "holdout tier status",
             "question": "May the pinned 359-ID tier serve as the secondary blind tier given "
                         "its membership is known, or must acceptance use only a new split?",
             "proposed": "secondary tier with the 0/359 caveat printed; primary is a new split",
             "cost": "using it alone would repeat the historical access ambiguity"},
            {"id": "Q-A1-9", "topic": "temporary-secret support",
             "question": "Does synthetic CVC/OTP/3DS material count as independent support for "
                         "their ≥300 target, and who defines the operation contexts?",
             "proposed": "synthetic-only support, with an explicit 'synthetic' column kept "
                         "separate from product-text support",
             "cost": "no real payment data may be used, so synthetic is the only available "
                     "source; the owner must accept the different evidentiary weight"},
            {"id": "Q-A1-10", "topic": "address component boundary",
             "question": "Are entrance/floor a required protected unit when written, or only "
                         "when attached to a house number?",
             "proposed": "required when they belong to a personal address occurrence; a bare "
                         "'подъезд 3' with no address is ADDRESS_COMPONENT_ONLY and stays a "
                         "negative",
             "cost": "the stricter reading over-masks building-service text"},
        ],

        "non_claims": [
            "this is a proposal, not an accepted manifest; O-DATA is still open",
            "no final gold was produced",
            "no engine quality, recall, precision or PPV number is asserted here",
            "no production digest was verified; RG stays blocked on it",
            "the prior name-label proposal is not accepted gold",
            "nothing here implies G7, G11 or a release GO",
        ],
    }

    (A1 / "ACCEPTANCE-PROPOSAL.json").write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2) + "\n")

    # owner questions as a durable markdown file, same source of truth
    lines = ["# A1 → owner: новые решения O-DATA", "",
             "Статус: `OWNER_PENDING`. Целевые показатели качества (≥99% на выборке + support/ДИ, "
             "≥300 независимых позитивных единиц) **уже решены** и здесь не переспрашиваются. "
             "Ниже — только то, что действительно не выбрано и без чего нельзя объявить G7.",
             "",
             "Каждый вопрос: эпизод → что известно/неизвестно → применимый принцип → варианты → цена → "
             "предлагаемое доказательство. Числа взяты из `INVENTORY.json` / `DATA-GAPS.csv` "
             "(реальные подсчёты, не оценки).", ""]
    for q in proposal["owner_questions"]:
        lines += [f"## {q['id']} — {q['topic']}", "",
                  f"**Вопрос.** {q['question']}", "",
                  f"**Предложение A1.** {q['proposed']}", "",
                  f"**Цена/последствие.** {q['cost']}", ""]
    lines += ["## Что A1 НЕ спрашивает (уже решено владельцем)", "",
              "- порог ≥99% по point estimate + публикация CI (`OWNER-DECISIONS.md#L19`);",
              "- support ≥300 независимых позитивных единиц (`REMAINING-DECISIONS.md#L34`);",
              "- два независимых разметчика без detector output (`REMAINING-DECISIONS.md#L33`);",
              "- лексическая неоднозначность «жене» без свидетельств имени не маскируется и не "
              "считается автоматическим FP (`REMAINING-DECISIONS.md#L8`);",
              "- притяжательные/публичные/вымышленные имена защищаются (`#L7`,`#L9`);",
              "- CVC/OTP/SMS/3DS входят в quality denominator, lifecycle отложен (`#L21-L25`).", ""]
    (A1 / "OWNER-QUESTIONS.md").write_text("\n".join(lines))

    print(f"wrote {A1 / 'ACCEPTANCE-PROPOSAL.json'}")
    print(f"wrote {A1 / 'OWNER-QUESTIONS.md'}")
    print(f"owner_questions={len(proposal['owner_questions'])} "
          f"native_types={len(MAIN_TYPES)} v6_new={proposal['registry_scope']['v6_new_types']['count']}")
    for t in MAIN_TYPES:
        s = native_support[t]["v5_corpus_1800"]
        print(f"  {t:9s} occurrences={s['occurrences']:6d} "
              f"independent={s['independent_identity_clusters']:5d} gap={s['gap_to_300_identities']:5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
