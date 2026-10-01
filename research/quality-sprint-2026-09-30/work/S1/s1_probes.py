#!/usr/bin/env python3
"""S1 — executed deterministic RED/probes on the UNCHANGED current engine.

WHAT THIS FILE IS. A read-only probe harness for the four critical classes the
approved sprint plan puts in S1 (`work/FIRST-WAVE-TASKS.json`, id `S1`):
forward/backward NAME collision, partial NAME left real and whole/parts
consistency, numeric prose + non-PII id rewrite, and streaming versus whole.
Every probe runs the REAL pipeline in memory — `testkit.load_dev_bundle()` →
`Detector` → `Vault(":memory:")` → `envelope.mask_messages`/`redact.unmask_*`
— and only synthetic values enter it. Nothing under `prototype/` is imported
for writing, nothing is patched inside the engine, and no provider, network or
corpus call is made.

WHAT THIS FILE IS NOT. It is not a product patch, not an acceptance scorer and
not proof about the recorded production traces. Where a recorded trace's
surface can be reconstructed into a deterministic precondition, the probe says
so and prints `REPRODUCED`; where the original input/state is not available,
the probe prints `NOT_MEASURED` and names exactly what is missing. A property
that HOLDS here means it held for this fixture — never that the class is
closed (see `SPEC.md` §Limits).

EXIT CODE. `main()` returns the number of VIOLATED properties. For the pinned
revision this is expected to be `4` (A2, B, C, D) — i.e. the command is an
intentional RED, not a passing suite. `EXPECTED_RED=4` is printed and also
written into `RED.log` by `run-s1.sh`; a different number means a precondition
drifted and the run must be re-read, not waved through.

FIXTURE PROVENANCE. Values are synthetic. `Битюкова Зинаида Сергеевна`,
`Тарасова Алла`-shaped rows and the collision shape are taken from the
recorded synthetic benchmark surfaces in
`research/hop-format-audit/final-analysis-2026-09-30/traces/TRACE-ANALYSIS.md`
(episodes N2, N3, P4, D1, D2) as SURFACE SHAPES; they are not customer data.
Where a probe needs the precondition "another person's real value equals an
earlier substitute", the second value is built from the substitute THIS run
observed, which is a controlled fixture precondition, documented as such — it
is NOT a replay of the original vault.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
# HERE = <root>/research/quality-sprint-2026-09-30/work/S1/s1_probes.py
ROOT = HERE.parents[4]
# The engine is read-only for this task; the venv is invoked from prototype/.
sys.path.insert(0, str(ROOT / "prototype"))

import testkit  # noqa: E402  (must be imported before the detector is used)

testkit.load_dev_bundle()

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages, mask_one  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.redact import (StreamDetokenizer, surviving_substitutes,  # noqa: E402
                            unmask_arguments, unmask_text)
from pseudex.vault import Vault  # noqa: E402

ORG = "s1-probe"
detector = Detector()

# --------------------------------------------------------------------------
# Fixture specification. Its digest is stable across runs; the observed mint is
# not (the engine mints substitutes with `secrets`), so the observed rows are
# printed and hashed separately for the logged run.
# --------------------------------------------------------------------------
FIXTURE = {
    "recorded_surfaces": {
        "N2_partial_name": "доставка на <surname> <given> телефон 8 974 239 86 41",
        "N3_collision": "<personA real surname> -> <fake surname>; document person shares it",
        "P4_answer_phone": "masked PHONE written back by the model in the agent's own grouping",
    },
    "synthetic_inputs": {
        "person_a": "Битюкова Зинаида Сергеевна",
        "collision_doc_row": "<observed fake surname> / Алла / +79095337552",
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


def one(vault: Vault, etype: str) -> tuple[str, str]:
    row = vault._conn.execute(  # noqa: SLF001
        "SELECT canonical, token FROM tokens WHERE customer=? AND entity_type=? LIMIT 1",
        (ORG, etype)).fetchone()
    return (row[0], row[1]) if row else ("", "")


def record(probe: str, property_: str, status: str, evidence: dict) -> dict:
    result = {"probe": probe, "property": property_, "status": status,
              "evidence": evidence}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


# --------------------------------------------------------------------------
# A — NAME collision, both directions
# --------------------------------------------------------------------------
def probe_a1_backward_collision_plain_message() -> dict:
    """A1: another person's real value that equals an earlier substitute.

    The recorded episode N3 is exactly this shape: the caller's real surname was
    masked to a substitute, and a later document row for a DIFFERENT person
    carried that same surname as its real value. Property: the model-facing
    output for the document must not present a string that the reverse leg
    resolves to the first person ("wrong-person restore").
    """
    vault = Vault(":memory:", ORG)
    first = ctx(vault, "c1")
    mask_one("Клиент Битюкова Алла Сергеевна просит перезвонить", first)
    real_a, fake_a = one(vault, "NAME")
    fsur, fgiven = fake_a.split()[0], fake_a.split()[1]

    second = ctx(vault, "c2")
    variants = {
        "exact_fake_full": f"Документ: {fake_a}, тел +7 909 533-75-52",
        "fake_surname_other_given": f"Документ: {fsur} Алла, тел +7 909 533-75-52",
        "fake_surname_only": f"Фамилия: {fsur}",
    }
    violations = []
    for label, doc in variants.items():
        shown = mask_one(doc, second)
        raw_leak = fsur.casefold() in shown.casefold()
        back = unmask_arguments(json.dumps({"last_name": fsur}, ensure_ascii=False),
                                vault.for_conversation("c2"))
        wrong_person = real_a.split()[0].casefold() in back.casefold()
        if raw_leak or wrong_person:
            violations.append({"variant": label, "masked": shown, "raw_leak": raw_leak,
                               "reverse": back, "wrong_person": wrong_person})
    status = "VIOLATED" if violations else "HOLDS"
    return record("A1", "new real value equal to an earlier substitute does not become the "
                        "first person on either leg (plain /mask message, foreign conversation)",
                  status,
                  {"person_a_real": real_a, "person_a_fake": fake_a,
                   "variants": len(variants), "violations": violations})


def probe_a2_collision_via_tool_result_echo() -> dict:
    """A2: the same surface string in one conversation denotes two people.

    The tool-result leg is handed the dialogue's recorded values as the
    conservative echo set (`envelope.mask_messages` → `message_recorded`). When
    a tool result carries a DIFFERENT person's real surname that is
    byte-identical to the earlier substitute's surname, the masking leg cannot
    tell "our substitute came back" from "this is the other person's real
    value". Property: the model-facing content must not leave that surface in a
    form the reverse leg expands to the first person, and must not silently
    merge the second person into the first (status quo: it does both).
    """
    vault = Vault(":memory:", ORG)
    first = ctx(vault, "c1")
    mask_one("Клиент Битюкова Алла Сергеевна просит перезвонить", first)
    real_a, fake_a = one(vault, "NAME")
    fsur, fgiven = fake_a.split()[0], fake_a.split()[1]

    violations = []
    for label, doc in {
        "lowercase_row": f"file_read rows: {fsur.lower()} / алла / +79095337552 / 1994-01-12",
        "capitalized_row": f"file_read rows: {fsur} / Алла / +79095337552 / 1994-01-12",
        "lowercase_bare": f"фамилия {fsur.lower()}",
    }.items():
        messages = [
            {"role": "user", "content": "Клиент Битюкова Алла Сергеевна просит перезвонить"},
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "call_1", "type": "function",
                             "function": {"name": "file_read",
                                          "arguments": json.dumps({"path": "doc.csv"})}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": doc},
        ]
        masked = mask_messages(messages, first, skip_template=False)
        shown = str(masked[2]["content"])
        # Precondition: the document's real surname is byte-identical to A's
        # substitute surname. It was constructed that way from the observed mint.
        precondition = fsur.casefold() in doc.casefold()
        left_in_clear = fsur.casefold() in shown.casefold()
        back = unmask_arguments(json.dumps({"last_name": fsur}, ensure_ascii=False),
                                vault.for_conversation("c1"))
        wrong_person = real_a.split()[0].casefold() in back.casefold()
        # A second, independent harm: the model is shown the FIRST person's
        # substitute identity for the SECOND person's row.
        merged_identity = (fgiven is not None and
                           fake_a.split()[1].casefold() in shown.casefold() and
                           "алла" not in shown.casefold())
        if precondition and (left_in_clear and wrong_person or merged_identity):
            violations.append({"variant": label, "masked": shown, "reverse": back,
                               "left_in_clear": left_in_clear, "merged": merged_identity})
    status = "VIOLATED" if violations else "HOLDS"
    return record("A2", "a surface byte-identical to an earlier substitute, arriving as another "
                        "person's real value in a tool result, is not resolved to the first "
                        "person and does not merge the two identities",
                  status,
                  {"person_a_real": real_a, "person_a_fake": fake_a,
                   "variants": 3, "violations": violations})


def probe_a3_forward_namesake_is_masked() -> dict:
    """A3 (positive control for A): a real person named like a substitute, in
    ANOTHER conversation, is still masked — the half `test_collisions.py` pins."""
    vault = Vault(":memory:", ORG)
    first = ctx(vault, "c1")
    mask_one("Клиент Иван Петров просит перезвонить", first)
    _, fake = one(vault, "NAME")
    other = ctx(vault, "c2")
    shown = mask_one(f"Клиент {fake} просит перезвонить", other)
    leaked = fake.casefold() in shown.casefold()
    return record("A3", "a namesake of a substitute in a foreign conversation stays masked",
                  "VIOLATED" if leaked else "HOLDS",
                  {"substitute": fake, "masked": shown, "leaked": leaked})


# --------------------------------------------------------------------------
# B — partial NAME left real
# --------------------------------------------------------------------------
def probe_b_partial_name_left_real() -> dict:
    """B: a personal name whose surname is typed LOC and whose given name is
    never born as a candidate.

    The recorded episode N2 hands the masked output
    «… на светлогорск зинаида …» for the source «битюкова зинаида»: the surname
    was replaced by a CITY and the given name stayed real. The original raw
    input bytes are not preserved in the trace, so this probe uses the
    reconstructed phrase in `FIXTURE` ("… на битюкова зинаида …") and reports
    BOTH the detection-level fact (stateless, deterministic) and the masked
    output. Property: every identifying part of the name is covered.
    """
    phrase = FIXTURE["synthetic_inputs"]["partial_name_phrase"]
    spans = [(s.entity_type, phrase[s.start:s.end]) for s in detector.detect(phrase)]
    types = {t for t, _ in spans}
    given_covered = any("зинаида" in text.casefold() for _, text in spans)
    surname_span = [(t, text) for t, text in spans if "битюкова" in text.casefold()]
    vault = Vault(":memory:", ORG)
    masked = mask_one(phrase, ctx(vault, "c"))
    given_left_real = "зинаида" in masked.casefold()
    violated = (not given_covered) or bool(surname_span and surname_span[0][0] != "NAME") \
        or given_left_real
    return record("B", "both identifying parts of a personal name in a sentence are covered "
                       "(surname not typed as a bare LOC, given name not left real)",
                  "VIOLATED" if violated else "HOLDS",
                  {"phrase": phrase, "spans": spans, "span_types": sorted(types),
                   "surname_span": surname_span, "masked": masked,
                   "given_name_left_real": given_left_real,
                   "detection_leg_deterministic": True,
                   "original_raw_input_available": False})


# --------------------------------------------------------------------------
# C — whole/parts consistency
# --------------------------------------------------------------------------
def probe_c_whole_parts_consistency() -> dict:
    """C: one person must receive ONE consistent substitute for whole and parts.

    Precondition (deterministic, from `FIXTURE`): the same person appears in
    conversation c1 in the reordered form «Зинаида Битюкова», and in c2 as the
    canonical «Битюкова Зинаида Сергеевна»; then only the surname is mentioned
    in c2. Property: every substitute in c2 that resolves to that one real
    person carries the same surname/given form. Status quo: the lone surname
    gets a THIRD, different substitute — the model sees two people where the
    customer has one.
    """
    vault = Vault(":memory:", ORG)
    ctx(vault, "c1")
    reordered = mask_one(FIXTURE["synthetic_inputs"]["full_name_reordered"], ctx(vault, "c1"))
    full = mask_one(FIXTURE["synthetic_inputs"]["full_name_canonical"], ctx(vault, "c2"))
    lone = mask_one(FIXTURE["synthetic_inputs"]["lone_surname"], ctx(vault, "c2"))

    full_name_fake = _find_fake(full, vault, "Битюкова Зинаида Сергеевна")
    lone_fake = lone.replace("напишите ", "").strip()
    real_of_full = unmask_text(full_name_fake, vault.for_conversation("c2")) if full_name_fake else ""
    real_of_lone = unmask_text(lone_fake, vault.for_conversation("c2"))
    same_person = ("Битюкова" in real_of_full) and ("Битюкова" in real_of_lone)
    consistent = (full_name_fake.split()[0].casefold() == lone_fake.split()[0].casefold()) \
        if full_name_fake and lone_fake else True
    violated = same_person and not consistent
    return record("C", "all substitutes of one real person inside one conversation are "
                       "consistent in their surname/given parts",
                  "VIOLATED" if violated else "HOLDS",
                  {"c1_reordered_masked": reordered, "c2_full_masked": full,
                   "c2_lone_masked": lone, "full_fake": full_name_fake,
                   "lone_fake": lone_fake, "real_of_full": real_of_full,
                   "real_of_lone": real_of_lone, "same_person": same_person,
                   "consistent": consistent,
                   "observed_rows": rows(vault)})


def _find_fake(masked_text: str, vault: Vault, canonical: str) -> str:
    for row in vault._conn.execute(  # noqa: SLF001
            "SELECT canonical, token FROM tokens WHERE customer=?", (ORG,)).fetchall():
        if row[0] == canonical:
            return row[1]
    return ""


def probe_c2_clean_parts_consistency() -> dict:
    """C2 (positive control for C): with no reordered prior row, whole and parts
    ARE consistent — the defect is state-dependent, not universal."""
    vault = Vault(":memory:", ORG)
    c = ctx(vault, "c")
    full = mask_one(FIXTURE["synthetic_inputs"]["full_name_canonical"], c)
    lone = mask_one(FIXTURE["synthetic_inputs"]["lone_surname"], c)
    full_fake = _find_fake(full, vault, "Битюкова Зинаида Сергеевна")
    lone_fake = lone.replace("напишите ", "").strip()
    consistent = bool(full_fake) and full_fake.split()[0].casefold() == lone_fake.split()[0].casefold()
    return record("C2", "clean-state whole/parts consistency (positive control)",
                  "VIOLATED" if not consistent else "HOLDS",
                  {"full_masked": full, "lone_masked": lone, "full_fake": full_fake,
                   "lone_fake": lone_fake, "consistent": consistent})


# --------------------------------------------------------------------------
# D — numeric prose restore (prefix splice) and non-PII id rewrite
# --------------------------------------------------------------------------
def probe_d1_answer_phone_prefix_splice() -> dict:
    """D1: the model writes a substitute phone with a country prefix it invented.

    The recorded episode P4 is `+79295422319` (masked) → model answer
    `+7 929 542-23-19` → restored `+3 929 542-23-19`: a real subscriber number
    under a prefix no dialer accepts. The restore leg keeps "what stands before
    the last ten digits" as the agent's (`redact._digits_in_form_of`), and only
    `+8` / `++` are guarded (`_malformed_phone_sign`). Property: the restored
    value's canonical must be the real phone, or the run must be visibly
    refused/residual — never a different number silently. Status quo: `+3`/`+9`
    written by the model are preserved into the real digits with `residual=[]`.
    """
    vault = Vault(":memory:", ORG)
    c = ctx(vault, "c")
    mask_one("тел +7 962 056-61-63", c)
    real, fake = one(vault, "PHONE")
    digits = re.sub(r"\D", "", fake)
    violations = []
    for prefix in ("+3", "+9", "+8"):
        written = f"{prefix} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        restored = unmask_text(written, vault.for_conversation("c"))
        residual = surviving_substitutes(written, restored, vault.for_conversation("c"), True)
        can_ok = re.sub(r"\D", "", restored) == re.sub(r"\D", "", real)
        if not can_ok and not residual:
            violations.append({"written": written, "restored": restored,
                               "residual": residual,
                               "real_canonical": real,
                               "prefix_kept": re.sub(r"\D", "", restored)[:1] != re.sub(r"\D", "", real)[:1]})
    exact = unmask_text(fake, vault.for_conversation("c"))
    return record("D1", "a substitute phone written with an invented country prefix either "
                        "restores to the real phone or is visibly refused, never a real "
                        "subscriber number under the invented prefix",
                  "VIOLATED" if violations else "HOLDS",
                  {"real": real, "fake": fake, "exact_write_restores": exact,
                   "violations": violations})


def probe_d2_nonpii_fidelity() -> dict:
    """D2: ordinary digits and ids that are NOT personal data must survive the
    reverse leg untouched (recorded episode D2: `c-3`→`c-8`, `3.`→`8.`).

    Bounded fuzz: 15 non-PII surfaces × 25 fresh in-memory vaults, each holding
    a name, a phone, a DOB and an order number. Property: text with no minted
    token comes back byte-identical. Status quo: 0 mutations; the recorded
    rewrite is NOT reproduced from this fixture (see SPEC.md §NOT_MEASURED).
    """
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
    status = "NOT_MEASURED" if not mutations else "VIOLATED"
    return record("D2", "non-PII digits/ids survive the reverse leg byte-identical",
                  status,
                  {"vaults": runs, "surfaces_per_vault": len(FIXTURE["nonpii_texts"]),
                   "checks": runs * len(FIXTURE["nonpii_texts"]),
                   "mutations": len(mutations), "examples": mutations[:5],
                   "recorded_episode_reproduced": False})


# --------------------------------------------------------------------------
# E — streaming versus whole
# --------------------------------------------------------------------------
def probe_e1_stream_equals_whole() -> dict:
    """E1: chunked detokenization equals whole-text detokenization.

    Sweep over chunk sizes 1–20, 32, 33, 63, 64, 65 and 100 for each masked
    surface. Property: `''.join(feed(chunk)) + flush() == unmask_text(whole)`
    for every chunking. Status quo: HOLDS for this fixture; the recorded
    episode D1 (`long_clinic-006`) is NOT reproduced in-process.
    """
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
    status = "VIOLATED" if mismatches else "HOLDS"
    return record("E1", "streamed chunk detokenization equals whole-text detokenization for "
                        "every chunking",
                  status,
                  {"surfaces": sorted(texts), "chunk_sizes": len(FIXTURE["stream_chunk_sizes"]),
                   "comparisons": len(texts) * len(FIXTURE["stream_chunk_sizes"]),
                   "mismatches": len(mismatches), "examples": mismatches[:3],
                   "recorded_episode_reproduced": False})


def probe_e2_carry_without_flush_drops_tail() -> dict:
    """E2: the carry contract at the stream boundary.

    `unmask_stream_chunk` withholds the last `_STREAM_KEEP` (64) characters from
    the caller until a `flush=True` arrives; `/unmask_chunk` is stateless and
    the CARRY IS THE CALLER'S (`service.unmask_chunk` docstring). The in-process
    proxy flushes on `[DONE]` and on an upstream error, but NOT when the line
    iterator simply ends (`proxy._stream_content`). This probe measures the pure
    engine behaviour the contract rests on: without a flush, the tail is not
    emitted. It is a mechanism fact read from the source, not an end-to-end
    measurement of the proxy leg (no provider call is permitted in this task).
    """
    vault = Vault(":memory:", ORG)
    c = ctx(vault, "c")
    masked = mask_one("Клиент Битюкова Зинаида Сергеевна оформила заказ на доставку "
                      "и просила перезвонить после обеда, спасибо", c)
    det = StreamDetokenizer(vault.for_conversation("c"))
    no_flush = "".join(det.feed(masked[i:i + 7]) for i in range(0, len(masked), 7))
    det2 = StreamDetokenizer(vault.for_conversation("c"))
    with_flush = "".join(det2.feed(masked[i:i + 7]) for i in range(0, len(masked), 7)) + det2.flush()
    whole = unmask_text(masked, vault.for_conversation("c"))
    tail_withheld = len(whole) - len(no_flush)
    return record("E2", "a stream that ends without an explicit flush is delivered complete "
                        "(contract: carry is caller-owned; proxy flushes only on [DONE]/error)",
                  "CONTRACT_GAP" if (no_flush != whole and with_flush == whole) else "HOLDS",
                  {"masked_len": len(masked), "without_flush_len": len(no_flush),
                   "with_flush": with_flush, "whole": whole,
                   "without_flush": no_flush,
                   "characters_withheld_without_flush": tail_withheld,
                   "engine_file": "prototype/pseudex/redact.py:2613-2635",
                   "proxy_flush_sites": ["prototype/pseudex/proxy.py:509-514",
                                         "prototype/pseudex/proxy.py:530-533"],
                   "end_to_end_proxy_measured": False})


# --------------------------------------------------------------------------
# P — positive control
# --------------------------------------------------------------------------
def probe_p_roundtrip_positive_control() -> dict:
    """P: the product's basic promise on a clean synthetic conversation —
    detection covers the values, the round trip returns the exact originals,
    and a repeat in the same conversation is stable."""
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
    print(json.dumps({
        "summary": {
            "probes": len(results),
            "holds": sum(1 for r in results if r["status"] == "HOLDS"),
            "violated": len(violated),
            "other": {r["probe"]: r["status"] for r in other},
            "violated_probes": sorted(r["probe"] for r in violated),
            "fixture_spec_sha256": FIXTURE_SPEC_SHA256,
            "expected_red": 4,
        }
    }, ensure_ascii=False, sort_keys=True))
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
