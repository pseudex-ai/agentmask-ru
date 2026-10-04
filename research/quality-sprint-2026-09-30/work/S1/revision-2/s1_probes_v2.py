#!/usr/bin/env python3
"""S1 revision-2 — corrected deterministic RED/probes on the UNCHANGED engine.

WHAT THIS REVISION CORRECTS (independent critical review, all points):

R1  ORIGINAL RAW IS PRESENT. revision-1 said the original raw input/response of
    N2/P4/D1/D2 was unavailable. Direct archived records contradict that; the
    pointers are in ARCHIVED_RAW below. Missing is the historical VAULT/
    provenance/mint order, not the raw text. B uses a different phone from the
    archived prompt_rule-005 message and is therefore a valid RED for its OWN
    input, not an exact replay.

R2  D1 IS A DIFFERENT INPUT-SIDE MUTATION. revision-1's D1 constructs
    `+3 <fake>` before restoration; archived P4 is `+7 <fake>` -> `+3 <same
    recorded digits>` at the restoration boundary. D1 is kept as its own numbered
    property and no longer offered as an explanation of P4. The acceptance
    predicate is split into independent checks; "canonical OR visibly refused" is
    not one of them.

R3  THE HISTORICAL STREAMING PATH IS IN-PROCESS. `harness.stream_verdict` fixes
    STREAM_CHUNK=17, feeds ONE `StreamDetokenizer`, calls `flush()` and compares
    against `unmask_text`. Provider SSE framing and "which leg delivered it" are
    NOT missing inputs. E2 (no flush) is the documented carry contract of the
    pure API — expected behaviour, not an engine RED. The proxy's behaviour when
    the upstream iterator simply ends is a SEPARATE concern for an offline fake
    upstream; it is not asserted as the cause of the in-process benchmark
    mismatch.

R4  EVIDENCE HARDENING. A2 isolates its three variants; C requires a nonempty,
    exactly-identified substitute and does not pass vacuously; B instruments
    recognizer -> suppress -> resolve instead of asserting "never born".

WHAT THIS FILE IS. Read-only probes in memory, no provider/network/corpus call,
no engine patch, no production patch. Exit code = number of VIOLATED properties.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT / "prototype"))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from pseudex.address import detect_address  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.context import suppress  # noqa: E402
from pseudex.detect import detect_pii  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages, mask_one  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.names import gazetteer_names  # noqa: E402
from pseudex.redact import (StreamDetokenizer, surviving_substitutes,  # noqa: E402
                            unmask_arguments, unmask_text)
from pseudex.vault import Vault  # noqa: E402

ORG = "s1-probe-v2"
detector = Detector()

# --------------------------------------------------------------------------------------------
# R1 — the archived raw inputs/responses that DO exist. Pointers only; no data copied in here.
# --------------------------------------------------------------------------------------------
ARCHIVED_RAW = {
    "prompt_rule-005": {
        "pointer": "prototype/bench/runs/2026-09-30/v5-sprint-v2-813/corpus.v5.json#corpus[base.id=prompt_rule-005].base.messages[1]",
        "role": "user",
        "content": "привет оформите доставку на битюкова зинаида телефон 8 926 123 45 67 да и 6 кабинет",
        "s1_fixture_phone": "8 974 239 86 41",
        "used_as_exact_replay": False,
    },
    "long_clinic-001": {
        "pointer": "prototype/bench/runs/2026-09-30/v5-sprint-v2-813/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.arms.v5.jsonl#L49.v5.model_trace.responses[7,13]",
        "raw": "+7 929 542-23-19", "restored": "+3 929 542-23-19",
        "note": "archived +7 -> +3 with the SAME ten-digit string; synthetic D1 differs",
    },
    "long_clinic-006": {
        "pointer": "prototype/bench/runs/2026-09-30/v5-sprint-v2-813/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.arms.v5.jsonl#L60.v5",
        "fields": ["reply_raw", "reply", "reply_whole", "stream_mismatch", "substitutes.i6"],
        "raw_dob": "08.04.1964 (fake)", "whole_dob": "04.04.1964 (real)",
        "stream_mismatch": True,
        "note": "harness.stream_verdict over STREAM_CHUNK=17 with flush; provider SSE is not an input",
    },
    "fanout_pick-017": {
        "pointer": "prototype/bench/runs/2026-09-30/v5-sprint-v2-813/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.arms.v5.jsonl#L607.v5.model_trace.responses[14]",
        "raw": "23.10.1965 / c-3", "restored": "127.10.1965 / c-8",
        "note": "recorded non-PII rewrite; not reproduced on this fixture (D2)",
    },
}

FIXTURE = {
    "recorded_surfaces": {
        "N2_partial_name": "доставка на <surname> <given> телефон <phone>",
        "N3_collision": "<personA real surname> -> <fake surname>; document person shares it",
        "P4_answer_phone": "masked PHONE written back by the model with +7, restored +3",
    },
    "synthetic_inputs": {
        "person_a": "Битюкова Алла Сергеевна",
        "partial_name_phrase": ("привет оформите доставку на битюкова зинаида "
                                "телефон 8 974 239 86 41 да и 6 кабинет"),
        "full_name_canonical": "Клиент Битюкова Зинаида Сергеевна, тел +79162148803",
        "full_name_reordered": "Клиент Зинаида Битюкова просит перезвонить",
        "lone_surname": "напишите Битюкова",
        "phone_prose": "Клиент Битюкова Зинаида Сергеевна, тел +7 962 056-61-63",
    },
    "stream_chunk_sizes": list(range(1, 21)) + [32, 33, 63, 64, 65, 100],
    "nonpii_texts": [
        "id c-3", "c-3 и c-8", "пункт 3.", "3 штуки", "заказ 1234", "№ 55",
        "стр. 8", "05.05.2026", "127.10.1965", "3. пункт", "код 007",
        "итого 8", "+3 929 542-23-19", "idc-3", "дата 23.10.1965",
    ],
}
FIXTURE_SPEC_SHA256 = hashlib.sha256(
    json.dumps(FIXTURE, sort_keys=True, ensure_ascii=False).encode("utf-8")
).hexdigest()


def ctx(vault: Vault, conversation: str, scope: str = "conversation") -> MaskContext:
    return MaskContext(
        detector=detector,
        vault=vault.for_conversation(conversation).with_pseudonym_scope(scope),
        audit=AuditLog(":memory:"),
        cache=MaskCache(4096),
        org_id=ORG,
        agent_id="a",
        conversation_id=conversation,
    )


def rows(vault: Vault) -> list[list[str]]:
    return [list(r) for r in vault._conn.execute(  # noqa: SLF001 - probe reads the store directly
        "SELECT canonical, token, entity_type FROM tokens WHERE customer=? ORDER BY rowid",
        (ORG,)).fetchall()]


def exact_token(vault: Vault, etype: str, canonical: str) -> str:
    """The substitute indexed under ONE exact canonical, or ''."""
    row = vault._conn.execute(  # noqa: SLF001
        "SELECT token FROM tokens WHERE customer=? AND entity_type=? AND canonical=? LIMIT 1",
        (ORG, etype, canonical)).fetchone()
    return row[0] if row else ""


def record(probe: str, property_: str, status: str, evidence: dict) -> dict:
    result = {"probe": probe, "property": property_, "status": status, "evidence": evidence}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


# ------------------------------------------------------------------------------------------
# A — NAME collision, both directions
# ------------------------------------------------------------------------------------------
def _setup_person_a(vault: Vault) -> tuple[str, str]:
    mask_one("Клиент Битюкова Алла Сергеевна просит перезвонить", ctx(vault, "c1"))
    return exact_token(vault, "NAME", "Битюкова Алла Сергеевна"), ""


def probe_a1_backward_collision_plain_message() -> dict:
    """A1: another person's real value equals an earlier substitute (foreign
    conversation, plain message). R4: a TRUE SECOND-PERSON ROUND TRIP is added —
    the substitute minted for the second person's own surname must resolve back
    to the second person, not the first. revision-1 only reversed the original
    substitute surname, which a corrected leg could leave standing."""
    vault = Vault(":memory:", ORG)
    fake_a, _ = _setup_person_a(vault)
    fsur = fake_a.split()[0]
    second = ctx(vault, "c2")
    violations, second_person = [], {}
    for label, doc in {
        "exact_fake_full": f"Документ: {fake_a}, тел +7 909 533-75-52",
        "fake_surname_other_given": f"Документ: {fsur} Алла, тел +7 909 533-75-52",
        "fake_surname_only": f"Фамилия: {fsur}",
    }.items():
        shown = mask_one(doc, second)
        raw_leak = fsur.casefold() in shown.casefold()
        back = unmask_arguments(json.dumps({"last_name": fsur}, ensure_ascii=False),
                                vault.for_conversation("c2"))
        wrong_person = "Битюкова".casefold() in back.casefold()
        # TRUE SECOND-PERSON ROUND TRIP: every substitute minted for the second
        # person's real value must restore to that second person. `related` is
        # read from the vault by canonical, never by searching a string.
        related = [[r[0], r[1], unmask_text(r[1], vault.for_conversation("c2"))]
                   for r in rows(vault)
                   if r[2] == "NAME" and fsur.casefold() in r[0].casefold()
                   and "Битюкова".casefold() not in r[0].casefold()]
        second_person[label] = {
            "minted_rows": related,
            "ok": bool(related) and all(one[0].casefold() == one[2].casefold() for one in related)}
        if raw_leak or wrong_person:
            violations.append({"variant": label, "masked": shown, "raw_leak": raw_leak,
                               "reverse": back, "wrong_person": wrong_person})
    status = "VIOLATED" if violations else "HOLDS"
    return record("A1", "new real value equal to an earlier substitute does not become the first "
                        "person on either leg; the second person's own substitute round-trips to "
                        "the second person (foreign conversation, plain message)",
                  status,
                  {"person_a_fake": fake_a, "variants": 3, "violations": violations,
                   "second_person_round_trip": second_person,
                   "second_person_round_trip_ok": all(one["ok"] for one in second_person.values())})


def probe_a2_collision_via_tool_result_echo() -> dict:
    """A2: one surface string, two people, in a TOOL RESULT.

    R4: EACH VARIANT GETS ITS OWN VAULT AND ITS OWN SETUP, so no variant can
    inherit another's mint; and the three harms are reported SEPARATELY:
    `surname_left_in_clear`, `reverse_wrong_person`, `given_name_merged`. The
    bare variant has no given name to merge and must not be described as if it
    did. The constructed precondition is a controlled fixture, not a replay."""
    variants = {
        "lowercase_row": "file_read rows: {fs} / алла / +79095337552 / 1994-01-12",
        "capitalized_row": "file_read rows: {FS} / Алла / +79095337552 / 1994-01-12",
        "lowercase_bare": "фамилия {fs}",
    }
    results, violations = {}, []
    for label, template in variants.items():
        vault = Vault(":memory:", ORG)                 # ISOLATED PER VARIANT
        fake_a, _ = _setup_person_a(vault)
        fsur, fgiven = fake_a.split()[0], fake_a.split()[1]
        doc = template.format(fs=fsur.lower(), FS=fsur)
        messages = [
            {"role": "user", "content": "Клиент Битюкова Алла Сергеевна просит перезвонить"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "call_1", "type": "function",
                             "function": {"name": "file_read",
                                          "arguments": json.dumps({"path": "doc.csv"})}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": doc},
        ]
        masked = mask_messages(messages, ctx(vault, "c1"), skip_template=False)
        shown = str(masked[2]["content"])
        back = unmask_arguments(json.dumps({"last_name": fsur}, ensure_ascii=False),
                                vault.for_conversation("c1"))
        harms = {
            "precondition_holds": fsur.casefold() in doc.casefold(),
            "surname_left_in_clear": fsur.casefold() in shown.casefold(),
            "reverse_wrong_person": "Битюкова".casefold() in back.casefold(),
            "given_name_merged": (fgiven.casefold() in shown.casefold()
                                  and "алла" not in shown.casefold()),
        }
        results[label] = {"doc": doc, "masked": shown, "reverse": back, **harms}
        if harms["precondition_holds"] and (
                (harms["surname_left_in_clear"] and harms["reverse_wrong_person"])
                or harms["given_name_merged"]):
            violations.append(label)
    return record("A2", "a surface byte-identical to an earlier substitute, arriving as another "
                        "person's real value in a tool result, is not resolved to the first "
                        "person and does not merge the two identities",
                  "VIOLATED" if violations else "HOLDS",
                  {"variants": len(variants), "violated_variants": violations,
                   "per_variant": results,
                   "indistinguishability_claimed": False,
                   "note": "the static fact that tool messages are handed `recorded` is not an "
                           "input-equivalence proof that NO available input can distinguish an "
                           "external new-real value from an echo"})


def probe_a3_forward_namesake_is_masked() -> dict:
    """A3 (positive control for A): a real person named like a substitute, in
    ANOTHER conversation, is still masked."""
    vault = Vault(":memory:", ORG)
    mask_one("Клиент Иван Петров просит перезвонить", ctx(vault, "c1"))
    fake = exact_token(vault, "NAME", "Иван Петров")
    shown = mask_one(f"Клиент {fake} просит перезвонить", ctx(vault, "c2"))
    leaked = fake.casefold() in shown.casefold()
    return record("A3", "a namesake of a substitute in a foreign conversation stays masked",
                  "VIOLATED" if leaked else "HOLDS",
                  {"substitute": fake, "masked": shown, "leaked": leaked})


# ------------------------------------------------------------------------------------------
# B — partial NAME left real, with the STAGES separated
# ------------------------------------------------------------------------------------------
def probe_b_partial_name_left_real() -> dict:
    """B: a personal name whose surname is typed LOC and whose given name is left
    real.

    R4 CORRECTION. revision-1 said the given name is "never born as a candidate".
    The final detector output cannot establish that. This probe runs the NAME-
    producing recognizers, then `suppress`, then `_resolve`, and reports at which
    stage a span covering the given name exists. It states the composition it
    uses, and it does NOT claim every recognizer was instrumented."""
    from pseudex.detect_all import _boundary_beats_checksum, _guess_inside_person, _resolve
    from pseudex.assets import ASSETS
    from pseudex.credentials import detect_credentials
    from pseudex.detect import Span
    from pseudex.normalize import normalize
    from pseudex.quasi import detect_quasi
    from pseudex.ru_pii import detect_plates, detect_structured, detect_vehicle_ids
    from pseudex.spoken import detect_spoken_email, detect_spoken_ids, detect_spoken_plate
    from pseudex.structured import detect_structured_kv

    phrase = FIXTURE["synthetic_inputs"]["partial_name_phrase"]
    norm = normalize(phrase)
    given = "зинаида"
    # REPLICATES Detector.detect's OWN LIST CONSTRUCTION, including the ADDR
    # typing that outranks NAME. A partial replication (raw detect_address spans,
    # no ADDR wrapper) lets the NAME survive `_resolve` and reaches the opposite
    # conclusion — which is how revision-1's "never born" claim could be made.
    address = [Span(s.start, s.end, "ADDR", s.value) for s in detect_address(norm)]
    recognizers = list(detect_pii(norm))
    recognizers += detect_structured(norm) + detect_spoken_ids(norm) \
        + detect_spoken_email(norm) + detect_spoken_plate(norm)
    recognizers += detect_credentials(phrase) + detect_vehicle_ids(phrase) + detect_plates(phrase)
    ner = list(detector._ner_spans(norm))  # noqa: SLF001 - read-only probe
    recognizers += ner
    address = [s for s in address if not _guess_inside_person(s, ner, norm)]
    recognizers += address
    recognizers += list(gazetteer_names(norm))
    kv = list(detect_structured_kv(norm))
    recognizers += detect_quasi(norm)
    resolved = _resolve(_boundary_beats_checksum(suppress(phrase, recognizers), phrase) + kv,
                        ASSETS.get().priority, phrase, keyed=kv)
    final = detector.detect(phrase)
    def _as_public(spans: list) -> list[list[str]]:
        return [["LOC" if s.entity_type == "ADDR" else s.entity_type, phrase[s.start:s.end]]
                for s in spans]

    replication_matches = _as_public(resolved) == _as_public(final)

    def covering(spans: list) -> list[list[str]]:
        return [[s.entity_type, phrase[s.start:s.end]]
                for s in spans if given in phrase[s.start:s.end].casefold()]

    recognizer_hits = covering(recognizers)
    suppressed_hits = covering(suppress(phrase, recognizers))
    resolved_hits = covering(resolved)
    final_hits = covering(final)
    surname_span = [[s.entity_type, phrase[s.start:s.end]]
                    for s in final if "битюкова" in phrase[s.start:s.end].casefold()]
    masked = mask_one(phrase, ctx(Vault(":memory:", ORG), "c"))
    given_left_real = given in masked.casefold()
    violated = given_left_real or bool(surname_span and surname_span[0][0] != "NAME")
    candidate_at_recognizers = bool(recognizer_hits)
    return record("B", "both identifying parts of a personal name in a sentence are covered "
                       "(surname not typed as a bare LOC, given name not left real)",
                  "VIOLATED" if violated else "HOLDS",
                  {"phrase": phrase,
                   "stages": {
                       "recognizers_name_producing": [[s.entity_type, phrase[s.start:s.end]]
                                                      for s in recognizers
                                                      if "битюков" in phrase[s.start:s.end].casefold()
                                                      or given in phrase[s.start:s.end].casefold()],
                       "given_covering_spans_recognizers": recognizer_hits,
                       "given_covering_spans_after_suppress": suppressed_hits,
                       "given_covering_spans_after_resolve": resolved_hits,
                       "given_covering_spans_final_detect": final_hits},
                   "given_candidate_present_before_resolve": candidate_at_recognizers,
                   "given_candidate_lost_at": (
                       "resolve" if (candidate_at_recognizers and not resolved_hits) else
                       "suppress" if (candidate_at_recognizers and not suppressed_hits) else
                       "not_present_in_the_probed_recognizers" if not candidate_at_recognizers else
                       "survives"),
                   "surname_span_final": surname_span, "masked": masked,
                   "given_name_left_real": given_left_real,
                   "replication_matches_public_detect": replication_matches,
                   "instrumented_recognizers": ["detect_pii", "detect_structured",
                                                "detect_spoken_*", "detect_credentials",
                                                "detect_vehicle_ids", "detect_plates",
                                                "_ner_spans", "detect_address(as ADDR)",
                                                "gazetteer_names", "detect_quasi",
                                                "suppress", "_resolve"],
                   "all_recognizers_instrumented": True,
                   "original_raw_input_available": True,
                   "original_raw_pointer": ARCHIVED_RAW["prompt_rule-005"]["pointer"],
                   "exact_replay_of_archived_message": False})


# ------------------------------------------------------------------------------------------
# C — whole/parts consistency, with a NONEMPTY exact identity
# ------------------------------------------------------------------------------------------
def _parts_check(vault: Vault, full_canonical: str, lone_canonical: str,
                 conversation: str = "c2") -> dict:
    full_token = exact_token(vault, "NAME", full_canonical)
    lone_token = exact_token(vault, "NAME", lone_canonical)
    fixture_valid = bool(full_token) and bool(lone_token) and len(full_token.split()) >= 2
    if not fixture_valid:
        return {"fixture_valid": False, "full_token": full_token, "lone_token": lone_token,
                "same_person": False, "surnames_equal": False}
    real_of_full = unmask_text(full_token, vault.for_conversation(conversation))
    real_of_lone = unmask_text(lone_token, vault.for_conversation(conversation))
    same_person = (full_canonical.split()[0].casefold() in real_of_full.casefold()
                   and lone_canonical.casefold() in real_of_lone.casefold())
    return {"fixture_valid": True, "full_token": full_token, "lone_token": lone_token,
            "full_surname": full_token.split()[0], "lone_surname": lone_token.split()[0],
            "surnames_equal": full_token.split()[0].casefold() == lone_token.split()[0].casefold(),
            "real_of_full": real_of_full, "real_of_lone": real_of_lone,
            "same_person": same_person}


def probe_c_whole_parts_consistency() -> dict:
    """C: one person must receive ONE consistent substitute for whole and parts.

    R4: the truth predicate requires a NONEMPTY, EXACTLY IDENTIFIED substitute for
    both the full name and the lone surname, both resolving to the one real
    person, and compares their surnames exactly. revision-1 returned `consistent
    = True` vacuously when `_find_fake` found nothing."""
    vault = Vault(":memory:", ORG)
    reordered = mask_one(FIXTURE["synthetic_inputs"]["full_name_reordered"], ctx(vault, "c1"))
    full = mask_one(FIXTURE["synthetic_inputs"]["full_name_canonical"], ctx(vault, "c2"))
    lone = mask_one(FIXTURE["synthetic_inputs"]["lone_surname"], ctx(vault, "c2"))
    parts = _parts_check(vault, "Битюкова Зинаида Сергеевна", "Битюкова")
    violated = parts["fixture_valid"] and parts["same_person"] and not parts["surnames_equal"]
    status = "VIOLATED" if violated else ("INVALID_FIXTURE" if not parts["fixture_valid"] else "HOLDS")
    return record("C", "all substitutes of one real person inside one conversation are "
                       "consistent in their surname/given parts (nonempty, exactly identified)",
                  status,
                  {"c1_reordered_masked": reordered, "c2_full_masked": full, "c2_lone_masked": lone,
                   **parts, "observed_rows": rows(vault)})


def probe_c2_clean_parts_consistency() -> dict:
    """C2 (positive control for C): with no reordered prior row, whole and parts
    ARE consistent. Same nonempty/exact predicate as C."""
    vault = Vault(":memory:", ORG)
    full = mask_one(FIXTURE["synthetic_inputs"]["full_name_canonical"], ctx(vault, "c"))
    lone = mask_one(FIXTURE["synthetic_inputs"]["lone_surname"], ctx(vault, "c"))
    parts = _parts_check(vault, "Битюкова Зинаида Сергеевна", "Битюкова", conversation="c")
    status = "HOLDS" if (parts["fixture_valid"] and parts["same_person"]
                         and parts["surnames_equal"]) else (
        "INVALID_FIXTURE" if not parts["fixture_valid"] else "VIOLATED")
    return record("C2", "clean-state whole/parts consistency (positive control)",
                  status, {"full_masked": full, "lone_masked": lone, **parts})


# ------------------------------------------------------------------------------------------
# D — numeric restore: synthetic prefix mutation and non-PII fidelity
# ------------------------------------------------------------------------------------------
def probe_d1_answer_phone_prefix_splice() -> dict:
    """D1: the model writes a substitute phone with an invented country prefix.

    R2: this is a SYNTHETIC INPUT-SIDE MUTATION (`+3 <fake>` before restoration).
    Archived P4 is a DIFFERENT boundary (`+7 <fake>` -> `+3 <same recorded
    digits>`). D1 is kept as its own property and does not explain P4.

    The predicate is split: (i) an exact copy of the substitute restores to the
    real phone; (ii) the approved notations keep their form; (iii) an INVENTED
    country identity must not silently deliver the real subscriber digits. Each
    is reported independently; "canonical OR visibly refused" is not the test."""
    vault = Vault(":memory:", ORG)
    c = ctx(vault, "c")
    real_written = "+7 962 056-61-63"
    mask_one(f"тел {real_written}", c)
    row = vault._conn.execute(  # noqa: SLF001
        "SELECT canonical, token FROM tokens WHERE customer=? AND entity_type='PHONE' LIMIT 1",
        (ORG,)).fetchone()
    real, fake = (row[0], row[1]) if row else ("", "")
    digits = re.sub(r"\D", "", fake)
    sub = lambda text: re.sub(r"\D", "", text)[-10:]  # noqa: E731 - the subscriber identity
    real_sub = sub(real)
    check1 = unmask_text(fake, vault.for_conversation("c")) == real_written
    approved = {}
    for label, written in {"keep_plus7": fake, "domestic_8": "8 " + digits[1:],
                           "bare_digits": digits[1:]}.items():
        restored = unmask_text(written, vault.for_conversation("c"))
        approved[label] = {"written": written, "restored": restored,
                           "round_trips_to_real": sub(restored) == real_sub}
    invented = []
    for prefix in ("+3", "+9"):
        written = f"{prefix} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        restored = unmask_text(written, vault.for_conversation("c"))
        residual = surviving_substitutes(written, restored, vault.for_conversation("c"), True)
        invented.append({
            "written": written, "restored": restored, "residual": residual,
            "delivers_real_subscriber_digits": sub(restored) == real_sub,
            "invented_prefix_kept": sub(restored) != sub(real) or restored[:2] != real[:2],
            "silently_accepted": (sub(restored) == real_sub and not residual)})
    violated = any(one["silently_accepted"] for one in invented)
    return record("D1", "an invented country identity on a substitute phone must not silently "
                        "deliver the real subscriber digits; approved notations and the exact "
                        "copy keep their contract",
                  "VIOLATED" if violated else "HOLDS",
                  {"real": real, "fake": fake,
                   "exact_copy_restores": check1,
                   "approved_notations": approved,
                   "approved_notations_keep_form": all(one["round_trips_to_real"]
                                                       for one in approved.values()),
                   "invented_prefix_cases": invented,
                   "archived_p4_boundary": ARCHIVED_RAW["long_clinic-001"],
                   "archived_boundary_executed_here": False,
                   "d1_explains_archived_p4": False})


def probe_d2_nonpii_fidelity() -> dict:
    """D2: ordinary digits/ids that are NOT personal data survive the reverse leg
    untouched. Unchanged NOT_MEASURED: 15 surfaces x 25 fresh vaults, 0 mutations;
    the recorded rewrite is not reproduced (its pointer is in ARCHIVED_RAW)."""
    mutations: list[dict] = []
    runs = 25
    for i in range(runs):
        vault = Vault(":memory:", ORG)
        c = ctx(vault, f"c{i}")
        mask_one("Клиент Битюкова Зинаида Сергеевна, тел +7 962 056-61-63, "
                 "дата рождения 08.04.1964, заказ № 1234", c)
        for text in FIXTURE["nonpii_texts"]:
            out = unmask_text(text, vault.for_conversation(f"c{i}"))
            if out != text:
                mutations.append({"run": i, "in": text, "out": out})
    return record("D2", "non-PII digits/ids survive the reverse leg byte-identical",
                  "NOT_MEASURED" if not mutations else "VIOLATED",
                  {"vaults": runs, "surfaces_per_vault": len(FIXTURE["nonpii_texts"]),
                   "checks": runs * len(FIXTURE["nonpii_texts"]),
                   "mutations": len(mutations), "examples": mutations[:5],
                   "recorded_episode_reproduced": False,
                   "recorded_pointer": ARCHIVED_RAW["fanout_pick-017"]["pointer"]})


# ------------------------------------------------------------------------------------------
# E — streaming versus whole
# ------------------------------------------------------------------------------------------
def probe_e1_stream_equals_whole() -> dict:
    """E1: chunked detokenization equals whole-text detokenization.

    R3: the historical mismatch runs through the SAME in-process contract the
    archived harness used — `restore_stream(raw, vault, STREAM_CHUNK=17)` with one
    StreamDetokenizer and an explicit flush, compared against `unmask_text`. The
    provider's SSE framing and the choice of HTTP leg are NOT missing inputs.
    The historical episode is unreproduced because its vault state is not
    reconstructed, and it stays NOT_MEASURED for reproduction."""
    vault = Vault(":memory:", ORG)
    c = ctx(vault, "c")
    texts = {
        "name": "Клиент Битюкова Зинаида Сергеевна оформила заказ",
        "phone": "Телефон: +7 962 056-61-63, звонить после 18:00",
        "dob": "Пациент родился 08.04.1964, запись на 12.05.2026",
        "addr": "доставка по адресу улица Ленина 5, кв 12, корп 3",
        "mix": "Клиент Иван Петров, тел +7 916 214-88-03, дата 08.04.1964, "
               "заказ № 1234 от 15.05.2025",
    }
    mismatches: list[dict] = []
    for label, text in texts.items():
        masked = mask_one(text, c)
        whole = unmask_text(masked, vault.for_conversation("c"))
        for chunk in FIXTURE["stream_chunk_sizes"]:
            det = StreamDetokenizer(vault.for_conversation("c"))
            streamed = "".join(det.feed(masked[i:i + chunk])
                               for i in range(0, len(masked), chunk)) + det.flush()
            if streamed != whole:
                mismatches.append({"surface": label, "chunk": chunk,
                                   "whole": whole, "streamed": streamed})
    return record("E1", "streamed chunk detokenization equals whole-text detokenization for "
                        "every chunking (harness contract: STREAM_CHUNK=17, one detokenizer, "
                        "explicit flush)",
                  "VIOLATED" if mismatches else "HOLDS",
                  {"surfaces": sorted(texts),
                   "chunk_sizes": len(FIXTURE["stream_chunk_sizes"]),
                   "comparisons": len(texts) * len(FIXTURE["stream_chunk_sizes"]),
                   "mismatches": len(mismatches), "examples": mismatches[:3],
                   "recorded_episode_reproduced": False,
                   "historical_path_is_in_process": True,
                   "provider_sse_is_a_missing_input": False,
                   "archived_episode": ARCHIVED_RAW["long_clinic-006"]})


def probe_e2_carry_without_flush_drops_tail() -> dict:
    """E2: the carry contract at the stream boundary — EXPECTED BEHAVIOUR.

    R3: `StreamDetokenizer` withholds the last 64 characters until `flush()`.
    That is the documented contract; the pure API never promised to emit the tail
    without a flush, so this is NOT an engine defect and does not count as a RED.
    What WOULD be a concern is the in-process proxy when the upstream line
    iterator simply ends without `[DONE]` and without an error; that is a
    SEPARATE question for an offline fake-upstream/ASGI harness and is not
    asserted here as the cause of any benchmark mismatch."""
    vault = Vault(":memory:", ORG)
    c = ctx(vault, "c")
    masked = mask_one("Клиент Битюкова Зинаида Сергеевна оформила заказ на доставку "
                      "и просила перезвонить после обеда, спасибо", c)
    det = StreamDetokenizer(vault.for_conversation("c"))
    no_flush = "".join(det.feed(masked[i:i + 7]) for i in range(0, len(masked), 7))
    det2 = StreamDetokenizer(vault.for_conversation("c"))
    with_flush = "".join(det2.feed(masked[i:i + 7])
                         for i in range(0, len(masked), 7)) + det2.flush()
    whole = unmask_text(masked, vault.for_conversation("c"))
    return record("E2", "the carry withholds the tail until an explicit flush (documented pure-API "
                        "contract, not an engine defect)",
                  "CONTRACT_EXPECTED" if (no_flush != whole and with_flush == whole) else "HOLDS",
                  {"masked_len": len(masked), "without_flush_len": len(no_flush),
                   "with_flush": with_flush, "whole": whole, "without_flush": no_flush,
                   "characters_withheld_without_flush": len(whole) - len(no_flush),
                   "engine_file": "prototype/pseudex/redact.py",
                   "proxy_flush_sites": ["prototype/pseudex/proxy.py:509-514",
                                         "prototype/pseudex/proxy.py:530-533"],
                   "end_to_end_proxy_measured": False,
                   "counts_as_engine_red": False,
                   "separate_open_question": "proxy behaviour when the upstream iterator ends "
                                             "without [DONE] and without an error; to be tested "
                                             "with an offline fake upstream, not asserted"})


# ------------------------------------------------------------------------------------------
# P — positive control
# ------------------------------------------------------------------------------------------
def probe_p_roundtrip_positive_control() -> dict:
    vault = Vault(":memory:", ORG)
    c = ctx(vault, "c")
    original = ("Клиент Битюкова Зинаида Сергеевна, тел +7 962 056-61-63, "
                "дата рождения 08.04.1964, адрес улица Ленина 5, кв 12")
    masked = mask_one(original, c)
    restored = unmask_text(masked, vault.for_conversation("c"))
    repeat = mask_one(masked, c)
    stable = masked in repeat
    ok = restored == original and stable and masked != original
    return record("P", "clean synthetic round trip returns the exact original and the "
                       "substitute is stable inside its own conversation",
                  "HOLDS" if ok else "VIOLATED",
                  {"original": original, "masked": masked, "restored": restored,
                   "repeat_stable": stable, "exact": restored == original})


PROBES = [
    probe_p_roundtrip_positive_control,
    probe_a1_backward_collision_plain_message,
    probe_a3_forward_namesake_is_masked,
    probe_a2_collision_via_tool_result_echo,
    probe_b_partial_name_left_real,
    probe_c_whole_parts_consistency,
    probe_c2_clean_parts_consistency,
    probe_d1_answer_phone_prefix_splice,
    probe_d2_nonpii_fidelity,
    probe_e1_stream_equals_whole,
    probe_e2_carry_without_flush_drops_tail,
]


def main() -> int:
    print(f"# fixture_spec_sha256={FIXTURE_SPEC_SHA256}")
    print(f"# git_head={_git_head()}")
    print(f"# python={sys.version.split()[0]}")
    results = [probe() for probe in PROBES]
    violated = [r for r in results if r["status"] == "VIOLATED"]
    other = [r for r in results if r["status"] not in ("HOLDS", "VIOLATED")]
    print(json.dumps({"summary": {
        "probes": len(results),
        "holds": sum(1 for r in results if r["status"] == "HOLDS"),
        "violated": len(violated),
        "other": {r["probe"]: r["status"] for r in other},
        "violated_probes": sorted(r["probe"] for r in violated),
        "fixture_spec_sha256": FIXTURE_SPEC_SHA256,
        "expected_red": 4,
    }}, ensure_ascii=False, sort_keys=True))
    return len(violated)


def _git_head() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001 - a probe must not fail on identity reporting
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
