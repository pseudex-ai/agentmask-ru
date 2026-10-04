"""M1b revision-2 probe — masking parity replay, corrected.

WHAT CHANGED AGAINST revision-1, AND WHY. Four defects, all local to this probe,
none of them a persisted engine edit.

R3.1 CROSS-CASE MONKEYPATCH. revision-1 captured `Vault._unique_token` inside
`primed_vault_class` and installed a fresh patch per case without ever restoring
the original, so a later case's fallback could consult an earlier case's saved
map. Here the original is captured ONCE at import and restored in a `finally`
per case; the order of the cases cannot change a result.

R3.2 MAPPING RECOVERY IS EXPOSED, NOT ASSERTED. `prime_from_captures` is one
greedy pass, not the "four converging sweeps" revision-1's docstring claimed. It
now returns the recovered pairs AND an `ambiguous` list (empty anchors,
non-converging intervals, recovered text equal to the raw item), and a case with
no recovered pair is `MISSING_PRIMED_STATE` rather than a silent unprimed run.

R3.3 A HarnessError IS NOT THE TARGET DIVERGENCE. revision-1 accepted any
`HarnessError` as `REPRODUCED` and only looked at the saved prefixes afterwards.
Here the comparison is recomputed on the same transcript after the attempt and
the verdict requires ALL of: the raise carries the divergence signature, the two
saved 60-character prefixes appear verbatim in the raise, and the recomputed
first differing offset is at or beyond the 60th character. An unrelated harness
failure, a setup failure and a true no-divergence are separate verdicts.

R3.4 CANDIDATE LOOP IS A BOUNDED SEARCH. Trying every declared tool with the
saved arguments does not establish which call was the original failing one; the
output says `original_call_identified: false` and keeps the search honest.

STILL WITHDRAWN. revision-1's `full_prior_state_replayed` boolean
(`len(payloads) == len(have) + 1`) proved visible-prefix agreement, not equality
of token rows, provenance/shown-forms, cache, backend state or RNG state. It is
reported here as `replayed_payload_count_matches_remaining`, a COUNT comparison,
and no state-equivalence claim is drawn from it. The revision-1 conclusion that
the trigger "lives in the failing push's own mint" is withdrawn: 0/4 reproduced
from an incompletely reconstructed state cannot exclude that state as a cause.

READ-ONLY over the run; writes only into this task's revision-2 scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[5]
PROTO = REPO / "prototype"
sys.path.insert(0, str(PROTO))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from bench.agentpii3 import score  # noqa: E402
from bench.agentpii5.harness import GatewayV5, _ORG  # noqa: E402
from bench.agentpii5.mock import seed_backend_v5  # noqa: E402
from bench.agentpii5.schema import case_v5_from_json  # noqa: E402
from bench.agentpii4.gateway import HarnessError  # noqa: E402
from pseudex import envelope  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

DIVERGENCE_SIGNATURE = "маскирование разошлось"
SAVED_PREFIX_CHARS = 60
# R3.1: captured ONCE, before any case installs a patch.
ORIGINAL_UNIQUE_TOKEN = Vault._unique_token


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_corpus(run_dir: pathlib.Path) -> dict[str, Any]:
    raw = json.loads((run_dir / "corpus.v5.json").read_text(encoding="utf-8"))
    return {case["base"]["id"]: case for case in raw["corpus"]}


def load_captures(run_dir: pathlib.Path, case_ids: set[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(run_dir.glob("*.canary.jsonl")):
        with path.open("rb") as source:
            for raw in source:
                head = raw[:400]
                if not any(cid.encode() in head for cid in case_ids):
                    continue
                row = json.loads(raw)
                if row.get("case_id") in case_ids and row.get("arm") == "I":
                    out[row["case_id"]] = row
    return out


def saved_prefixes(reason: str) -> tuple[str, str]:
    """The two saved 60-character prefixes the harness put in the exception."""
    rest = reason.split("производственный путь ", 1)[1]
    production, counting = rest.split(", счётный ", 1)
    return production.strip(), counting.strip()


def prime_from_captures(case, payloads: list[dict]) -> tuple[dict[tuple[str, str], str], list[dict]]:
    """Recover the saved (entity_type, real value) -> fake mapping.

    ONE GREEDY PASS, and the caller is told where it is uncertain. The items of
    a message are disjoint and non-overlapping, so the text before the first
    item, between items and after the last one is unchanged; each item's masked
    interval is bracketed by the lengths of its neighbours' substitutes, which
    are themselves unknown — so the interval is approximated from the running
    delta and the anchor search. An empty anchor, a non-positive interval and a
    recovered string equal to the raw value are all reported as `ambiguous`
    rather than silently accepted. The caller's acceptance is byte-identity of
    the visible replay, so an extraction that did not converge is not mistaken
    for one that did — but it is also not claimed to be unique."""
    fakes: dict[tuple[str, str], str] = {}
    ambiguous: list[dict] = []
    inputs = [one for one in payloads if one["name"] == "model_input"]
    message_index = 0
    for payload in inputs:
        raw, masked = payload["real_text"], payload["text"]
        items = sorted([item for item in case.base.pii
                        if getattr(item.where, "kind", "") == "message"
                        and getattr(item.where, "msg", -1) == message_index],
                       key=lambda one: one.where.start)
        total_delta = len(masked) - len(raw)
        delta_before = 0
        for index, item in enumerate(items):
            start, end = int(item.where.start), int(item.where.end)
            m_start = start + delta_before
            if index + 1 < len(items):
                following = items[index + 1]
                anchor = raw[end:int(following.where.start)]
                if not anchor:
                    ambiguous.append({"msg": message_index, "item": item.id,
                                      "why": "empty anchor before the next item"})
                found = masked.find(anchor, m_start) if anchor else -1
                m_end = found if found >= 0 else end + total_delta
            else:
                m_end = end + total_delta
            fake = masked[m_start:m_end]
            if m_end <= m_start:
                ambiguous.append({"msg": message_index, "item": item.id,
                                  "why": f"non-positive interval {m_start}:{m_end}"})
            if fake and fake != item.value:
                fakes[(item.type, item.value)] = fake
            elif fake == item.value:
                ambiguous.append({"msg": message_index, "item": item.id,
                                  "why": "recovered text equals the raw value"})
            delta_before += len(fake) - (end - start)
        message_index = 1 if message_index == 0 else message_index + 1
    return fakes, ambiguous


def primed_vault_class(fakes: dict[tuple[str, str], str]):
    """A `Vault` whose mint returns the saved substitute for a known pair.

    The run's own `_unique_token` is the fallback for every value this dialogue
    had not yet shown. `ORIGINAL_UNIQUE_TOKEN` is captured at import; the caller
    restores it in `finally` after every case (R3.1)."""
    def patched(self, entity_type, gender=None, original_value="", canonical="", head=""):
        saved = fakes.get((entity_type, original_value))
        if saved:
            return saved
        return ORIGINAL_UNIQUE_TOKEN(self, entity_type, gender, original_value, canonical, head)

    return patched


def observed_boundary(gateway: GatewayV5, text: str) -> dict:
    """The harness's own two-implementation comparison, recomputed exactly.

    Run AFTER the attempt, on the transcript the attempt left behind, so it
    reads the same wire and the same state. `envelope.mask_messages` and
    `score._mask_message` both mint idempotently, so re-running them does not
    change which substitutes exist. This is the only way to get the FIRST
    DIFFERING OFFSET, which the saved 60-character prefixes do not carry."""
    try:
        observed = score._mask_message(text, gateway._detector, gateway._view, "tool")
        masked = envelope.mask_messages([dict(one) for one in gateway._transcript],
                                        gateway._context, False)
        content = masked[-1].get("content")
        if not isinstance(content, str):
            return {"equal": False, "error": "production content is not a string",
                    "first_difference": None}
        if observed.masked == content:
            return {"equal": True, "first_difference": None}
        at = next((k for k, (a, b) in enumerate(zip(observed.masked, content)) if a != b),
                  min(len(observed.masked), len(content)))
        return {"equal": False, "first_difference": at,
                "observed_window": observed.masked[max(0, at - 30):at + 40],
                "production_window": content[max(0, at - 30):at + 40]}
    except Exception as broken:  # noqa: BLE001 — a diagnostic must not hide its own failure
        return {"equal": None, "first_difference": None,
                "error": f"{type(broken).__name__}: {broken}"}


def classify_attempt(raised: str, raised_other: str, first: int | None,
                     saved_production: str, saved_counting: str,
                     signature: bool | None = None) -> str:
    """R3.3, as one pure function so it can be mutation-tested.

    A raise counts as the recorded divergence ONLY when the message carries the
    divergence signature, both saved prefixes appear verbatim in it, and the
    recomputed first difference is at or beyond the 60th character. Everything
    else is named for what it is."""
    if signature is None:
        signature = DIVERGENCE_SIGNATURE in raised
    prefixes_match = bool(saved_production and saved_counting
                          and saved_production in raised and saved_counting in raised)
    beyond = isinstance(first, int) and first >= SAVED_PREFIX_CHARS
    if raised_other:
        return "SETUP_FAILURE"
    if raised:
        if signature and prefixes_match and beyond:
            return "REPRODUCED_EXACT_BOUNDARY"
        if signature and prefixes_match:
            return "RAISE_WITHOUT_BOUNDARY_BEYOND_60"
        if signature:
            return "DIVERGENCE_PREFIX_MISMATCH"
        return "UNRELATED_HARNESS_ERROR"
    if first is not None:
        return "LOCAL_DIVERGENCE_WITHOUT_RAISE"
    return "NO_DIVERGENCE"


def verdict_self_test() -> dict:
    """The rule is an instrument: prove it REJECTS what it must reject.

    Each control is the input an attempt could really produce. A rule that
    accepted any HarnessError would return REPRODUCED_EXACT_BOUNDARY for the
    first control below."""
    prod, cnt = "PROD-PREFIX", "CNT-PREFIX"
    divergence = (f"derive-008: {DIVERGENCE_SIGNATURE} — производственный путь "
                  f"{prod!r}, счётный {cnt!r}")
    controls = [
        ("unrelated_harness_error",
         "derive-008: mask_messages вернул не строку", "", None, "UNRELATED_HARNESS_ERROR"),
        ("non_harness_failure", "", "ValueError: boom", None, "SETUP_FAILURE"),
        ("signature_prefix_mismatch",
         f"derive-008: {DIVERGENCE_SIGNATURE} — производственный путь 'OTHER', счётный 'OTHER2'",
         "", None, "DIVERGENCE_PREFIX_MISMATCH"),
        ("signature_prefix_match_short_offset", divergence, "", 10,
         "RAISE_WITHOUT_BOUNDARY_BEYOND_60"),
        ("signature_prefix_match_long_offset", divergence, "", 80,
         "REPRODUCED_EXACT_BOUNDARY"),
        ("divergence_without_raise", "", "", 80, "LOCAL_DIVERGENCE_WITHOUT_RAISE"),
        ("clean", "", "", None, "NO_DIVERGENCE"),
    ]
    out = []
    ok = True
    for name, raised, raised_other, first, expected in controls:
        got = classify_attempt(raised, raised_other, first, prod, cnt)
        out.append({"control": name, "expected": expected, "got": got, "ok": got == expected})
        ok = ok and got == expected
    return {"controls": out, "all_ok": ok}


def replay(case, detector, tool_name: str, payloads: list[dict],
           saved_production: str, saved_counting: str) -> dict:
    gateway = GatewayV5(case, detector, Vault(":memory:", _ORG), AuditLog(":memory:"),
                        MaskCache(256), capture=True)
    gateway.push_system(case.base.messages[0].content)
    user_indices = [i for i, message in enumerate(case.base.messages)
                    if message.role == "user"]
    first_tool = next((index for index, one in enumerate(payloads)
                       if one["name"] in ("tool_args", "tool_result", "tool_error")),
                      len(payloads))
    inputs_before = sum(1 for one in payloads[:first_tool] if one["name"] == "model_input")
    for index in user_indices[:max(0, inputs_before - 1)]:
        gateway.push_user(index)

    args_payload = next((one for one in reversed(payloads) if one["name"] == "tool_args"), None)
    if args_payload is None:
        return {"verdict": "NO_SAVED_TOOL_ARGS"}

    have = list(gateway.captured_payloads())
    prefix = payloads[:len(have)]
    visible_prefix_agreement = (len(have) == len(prefix) and all(
        one.name == other["name"] and one.text == other["text"]
        and one.real_text == other["real_text"]
        for one, other in zip(have, prefix)))

    arguments = json.loads(args_payload["text"])
    gateway.note_tool_call(tool_name, arguments)
    restored, _residual = gateway.restore_arguments(arguments)
    backend = seed_backend_v5(case)
    try:
        log = backend.call(tool_name, restored)
    except Exception as broken:  # noqa: BLE001 — a tool refusing these args is a candidate miss
        return {"tool_name": tool_name, "verdict": "TOOL_REFUSED_ARGS",
                "raised_other": f"{type(broken).__name__}: {broken}",
                "visible_prefix_agreement": visible_prefix_agreement,
                "restored_args": json.dumps(restored, ensure_ascii=False)}

    raised = ""
    raised_other = ""
    try:
        gateway.push_call(tool_name, log, backend.form_of(log.seq), turn=1, ordinal=0)
    except HarnessError as broken:
        raised = str(broken)
    except Exception as broken:  # noqa: BLE001 — any other failure is a finding too
        raised_other = f"{type(broken).__name__}: {broken}"

    boundary = observed_boundary(gateway, log.result_text)
    first = boundary.get("first_difference")
    signature = DIVERGENCE_SIGNATURE in raised
    prefixes_match = bool(saved_production and saved_counting
                          and saved_production in raised and saved_counting in raised)
    beyond_saved_window = isinstance(first, int) and first >= SAVED_PREFIX_CHARS

    verdict = classify_attempt(raised, raised_other, first, saved_production, saved_counting)

    return {
        "tool_name": tool_name,
        "verdict": verdict,
        "raised": raised,
        "raised_other": raised_other,
        "divergence_signature_present": signature,
        "saved_prefixes_match_raise": prefixes_match,
        "recomputed_first_difference": first,
        "boundary_beyond_saved_60_char_window": beyond_saved_window,
        "boundary_probe": boundary,
        "payloads_in_capture": len(payloads),
        "payloads_replayed": len(have),
        # R3.4/count-only: NOT a state-equivalence claim.
        "replayed_payload_count_matches_remaining": len(payloads) == len(have) + 1,
        "visible_prefix_agreement": visible_prefix_agreement,
        "intermediate_hops_in_capture": sum(
            1 for one in payloads if one["name"] in ("tool_result", "tool_error")),
        "saved_tool_args_sha256": sha256_text(args_payload["text"]),
        "restored_args": json.dumps(restored, ensure_ascii=False),
        "saved_restored_args": args_payload["real_text"],
        "restored_args_match_saved": json.dumps(restored, ensure_ascii=False) == args_payload["real_text"],
        "mock_result_head": log.result_text[:120],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cases", default="tool_chain-037,tool_chain-040,derive-008,"
                                            "sequential_chain:assistant-002")
    parser.add_argument("--reason-source", default="")
    args = parser.parse_args()

    run_dir = pathlib.Path(args.run).resolve()
    case_ids = {one for one in args.cases.split(",") if one}
    corpus = load_corpus(run_dir)
    captures = load_captures(run_dir, case_ids)

    reasons: dict[str, str] = {}
    if args.reason_source:
        excluded = json.loads(pathlib.Path(args.reason_source).read_text(encoding="utf-8"))
        for one in excluded["excluded"]:
            if one["case_id"] in case_ids:
                reasons[one["case_id"]] = one["reason"]

    detector = Detector()
    results: list[dict] = []
    for case_id in sorted(case_ids):
        if case_id not in captures or case_id not in corpus:
            results.append({"case_id": case_id, "verdict": "MISSING_INPUT"})
            continue
        row = captures[case_id]
        payloads = row["capture"]["payloads"]
        case = case_v5_from_json(corpus[case_id])
        fakes, ambiguous = prime_from_captures(case, payloads)
        production, counting = saved_prefixes(reasons.get(case_id, "")) if reasons else ("", "")

        attempts: list[dict] = []
        entry: dict
        try:
            if not fakes:
                # R3.2: no recovered state = not a replay, and said so.
                entry = {"case_id": case_id, "verdict": "MISSING_PRIMED_STATE",
                         "recovered_fake_pairs": 0, "ambiguous_recovery": ambiguous,
                         "candidate_attempts": []}
            else:
                Vault._unique_token = primed_vault_class(fakes)
                for tool_name in list(case.base.tools):
                    attempt = replay(case, detector, tool_name, payloads, production, counting)
                    attempts.append(attempt)
                    if attempt.get("verdict") == "REPRODUCED_EXACT_BOUNDARY":
                        break
                entry = dict(attempts[0] if attempts else {"verdict": "NO_ATTEMPTS"})
                entry["case_id"] = case_id
        except Exception as broken:  # noqa: BLE001 — one broken case must not hide the others
            entry = {"case_id": case_id, "verdict": "SETUP_FAILURE",
                     "raised_other": f"{type(broken).__name__}: {broken}",
                     "candidate_attempts": attempts}
        finally:
            # R3.1: the original is put back for EVERY case, whatever happened.
            Vault._unique_token = ORIGINAL_UNIQUE_TOKEN

        entry["payload_names"] = [one["name"] for one in payloads]
        entry["ambiguous_recovery"] = ambiguous
        entry["recovered_fake_pairs"] = [
            {"type": key[0], "real": key[1], "fake": value} for key, value in fakes.items()]
        entry["candidate_attempts"] = [
            {k: one.get(k) for k in
             ("tool_name", "verdict", "raised", "raised_other",
              "divergence_signature_present", "saved_prefixes_match_raise",
              "recomputed_first_difference", "visible_prefix_agreement",
              "replayed_payload_count_matches_remaining", "restored_args_match_saved")}
            for one in attempts]
        entry["original_call_identified"] = False       # R3.4
        entry["search_is_bounded_over_declared_tools"] = True
        if reasons:
            entry["saved_production_prefix"] = production
            entry["saved_counting_prefix"] = counting
        results.append(entry)

    reproduced = sum(1 for one in results
                     if one.get("verdict") == "REPRODUCED_EXACT_BOUNDARY")
    self_test = verdict_self_test()
    report = {"run_dir": str(run_dir), "cases": results, "reproduced": reproduced,
              "total": len(results),
              "verdict_rule": ("REPRODUCED_EXACT_BOUNDARY requires the divergence signature, "
                               "both saved prefixes verbatim in the raise, and a recomputed "
                               "first difference at or beyond character 60"),
              "verdict_rule_self_test": self_test,
              "state_equivalence_claimed": False,
              "trigger": "UNKNOWN"}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    # The probe's own assertions: the ORIGINAL is back in place, and the verdict
    # rule rejects the controls it must reject.
    return 0 if (Vault._unique_token is ORIGINAL_UNIQUE_TOKEN and self_test["all_ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
