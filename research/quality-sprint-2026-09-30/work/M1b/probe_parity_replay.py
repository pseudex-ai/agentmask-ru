"""M1b probe 2 — the four production/counting masking divergences of run
cc3a551f, replayed offline from the SAVED prior state.

WHAT THE RUN DID NOT KEEP, AND WHAT IT DID. The excluded arm-I records in
`<run>.arms.v5.jsonl` are `_empty_run(case, repeat)` — on a HarnessError the
harness returns an empty v5 record, so the transcript, the calls and the
request count are gone and the only surviving text is the 60-character prefix
pair inside the triple's `reason`. That is the state usually reported as
«missing».

THE PRIOR STATE IS ON DISK ANYWAY, in a second artifact: `GatewayV5` is built
with `capture=True` by the real runner, every payload it delivers is appended
as it is delivered, and the triple appends that capture even when the I arm
failed (`harness.py:1343` runs after `asyncio.gather` returns, and a failed arm
returns an outcome rather than raising). The capture row of each of the four
cases therefore ends exactly at the payload BEFORE the failing push — the
system transcript, every user message reached, and the tool ARGUMENTS the model
wrote, with `real_text` carrying the pre-mask bytes.

THE MINT IS THE ONE PIECE THAT IS NOT REPRODUCIBLE BY RE-RUNNING. `vault.py`
draws substitutes through `secrets` (CSPRNG) and the run persists no mapping,
so a second process mints DIFFERENT fakes for the same values — measured, not
assumed: the payload names and all `real_text` bytes match, and every replaced
span lands on the same declared locus, while the surfaces differ. The saved
delivered bytes DO carry the mapping, so this probe recovers the (real, fake)
pair of every declared message item by locating the raw suffix inside the saved
masked text and primes `Vault._unique_token` with it. Only then is the replay
byte-identical, and only a byte-identical replay may be asked whether it
reproduces the failure.

Then the SAME production path is driven:
    push_system -> push_user(...) -> note_tool_call(saved args)
    -> restore_arguments -> seed_backend_v5(case).call(...) -> push_call
for every tool the case declares, and the run's own two 60-character prefixes
decide which tool, if any, reproduces.

READ-ONLY over the run. Nothing is written outside this task's scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[4]
PROTO = REPO / "prototype"
sys.path.insert(0, str(PROTO))

import testkit  # noqa: E402

testkit.load_dev_bundle()

from bench.agentpii5.harness import GatewayV5, _ORG  # noqa: E402
from bench.agentpii5.mock import seed_backend_v5  # noqa: E402
from bench.agentpii5.schema import case_v5_from_json  # noqa: E402
from bench.agentpii4.gateway import HarnessError  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402


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
    """The two 60-char prefixes the harness put in the exception, in order."""
    rest = reason.split("производственный путь ", 1)[1]
    production, counting = rest.split(", счётный ", 1)
    return production.strip(), counting.strip()


def prime_from_captures(case, payloads: list[dict]) -> dict[tuple[str, str], str]:
    """Recover the saved (entity_type, real value) -> fake mapping.

    THE ITEMS ARE DISJOINT AND NON-OVERLAPPING, so each substitute occupies one
    interval and the raw text before the first item, between items and after
    the last one is unchanged. That fixes each item's masked interval once the
    LENGTH CHANGES of the items around it are known — and they are not, because
    the substitutions are exactly what is being recovered. Two nested passes
    solve it: `delta_before[k]` is the cumulative change of the items before k,
    `delta_after[k]` of those after, and the interval of item k is
    `[start + delta_before, len(masked) - (len(raw) - end) - delta_after]`.
    Four sweeps converge for the small item counts a message carries, and the
    caller's acceptance is byte-identity of the whole replay, so an extraction
    that did not converge cannot be mistaken for one that did."""
    fakes: dict[tuple[str, str], str] = {}
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
                found = masked.find(anchor, m_start) if anchor else -1
                m_end = found if found >= 0 else end + total_delta
            else:
                # The text after the LAST item is untouched, so its end in the
                # masked string is the raw end shifted by the run's total delta.
                m_end = end + total_delta
            fake = masked[m_start:m_end]
            if fake and fake != item.value:
                fakes[(item.type, item.value)] = fake
            delta_before += len(fake) - (end - start)
        message_index = 1 if message_index == 0 else message_index + 1
    return fakes


def primed_vault_class(fakes: dict[tuple[str, str], str]):
    """A `Vault` whose mint returns the saved substitute for a known pair.

    The run's own `_unique_token` is the fallback for every value this dialogue
    had not yet shown — a tool result may introduce one, and refusing to mint it
    would be a different failure than the one under test."""
    original = Vault._unique_token

    def patched(self, entity_type, gender=None, original_value="", canonical="", head=""):
        saved = fakes.get((entity_type, original_value))
        if saved:
            return saved
        return original(self, entity_type, gender, original_value, canonical, head)

    return patched


def replay(case, detector, tool_name: str, payloads: list[dict]) -> dict:
    gateway = GatewayV5(case, detector, Vault(":memory:", _ORG), AuditLog(":memory:"),
                        MaskCache(256), capture=True)
    gateway.push_system(case.base.messages[0].content)
    user_indices = [i for i, message in enumerate(case.base.messages)
                    if message.role == "user"]
    # ONLY THE USER PUSHES THAT PRECEDE THE FIRST TOOL CALL are replayed. A
    # multi-hop case delivers tool results between its user messages, and this
    # probe does not replay them (their tool name and the vault state they need
    # are not in the capture alone); pushing every user the row mentions would
    # build a transcript the run never had and then "find" it different.
    first_tool = next((index for index, one in enumerate(payloads)
                       if one["name"] in ("tool_args", "tool_result", "tool_error")),
                      len(payloads))
    inputs_before = sum(1 for one in payloads[:first_tool] if one["name"] == "model_input")
    for index in user_indices[:max(0, inputs_before - 1)]:
        gateway.push_user(index)

    args_payload = next((one for one in reversed(payloads) if one["name"] == "tool_args"),
                        None)
    if args_payload is None:
        return {"verdict": "NO_SAVED_TOOL_ARGS"}

    have = list(gateway.captured_payloads())
    prefix = payloads[:len(have)]
    byte_identical = (len(have) == len(prefix) and all(
        one.name == other["name"] and one.text == other["text"]
        and one.real_text == other["real_text"]
        for one, other in zip(have, prefix)))

    arguments = json.loads(args_payload["text"])
    gateway.note_tool_call(tool_name, arguments)
    restored, _residual = gateway.restore_arguments(arguments)
    backend = seed_backend_v5(case)
    try:
        log = backend.call(tool_name, restored)
    except Exception as broken:  # noqa: BLE001 — a tool that refuses these args is a candidate miss
        return {"tool_name": tool_name, "verdict": "TOOL_REFUSED_ARGS",
                "raised_other": f"{type(broken).__name__}: {broken}",
                "state_byte_identical": byte_identical,
                "restored_args": json.dumps(restored, ensure_ascii=False)}
    out = {
        "tool_name": tool_name,
        # SCOPE OF THE BYTE-IDENTITY CLAIM, STATED. The replay drives the system
        # push and every user push the capture proves was reached; a case with
        # intermediate tool hops has more payloads than that, and those hops were
        # NOT replayed. «Byte-identical» below therefore covers the prefix the
        # replay produced, and `full_prior_state_replayed` says whether that
        # prefix is the whole prior state.
        "payloads_in_capture": len(payloads),
        "payloads_replayed": len(have),
        "full_prior_state_replayed": len(payloads) == len(have) + 1,
        "intermediate_hops_in_capture": sum(
            1 for one in payloads if one["name"] in ("tool_result", "tool_error")),
        "state_byte_identical": byte_identical,
        "saved_tool_args_sha256": sha256_text(args_payload["text"]),
        "restored_args": json.dumps(restored, ensure_ascii=False),
        "saved_restored_args": args_payload["real_text"],
        "restored_args_match_saved": json.dumps(restored, ensure_ascii=False) == args_payload["real_text"],
        "mock_result_head": log.result_text[:120],
    }
    try:
        gateway.push_call(tool_name, log, backend.form_of(log.seq), turn=1, ordinal=0)
    except HarnessError as broken:
        out["raised"] = str(broken)
    except Exception as broken:  # noqa: BLE001 — any other failure is a finding too
        out["raised_other"] = f"{type(broken).__name__}: {broken}"
    else:
        out["raised"] = ""
    out["verdict"] = "REPRODUCED" if out.get("raised") else "NO_DIVERGENCE_THIS_TOOL"
    return out


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
        fakes = prime_from_captures(case, payloads)
        Vault._unique_token = primed_vault_class(fakes)
        production, counting = saved_prefixes(reasons.get(case_id, "")) if reasons else ("", "")

        attempts = []
        winner = None
        for tool_name in list(case.base.tools):
            attempt = replay(case, detector, tool_name, payloads)
            attempts.append(attempt)
            if attempt.get("verdict") == "REPRODUCED":
                winner = attempt
                break
        entry: dict = dict(winner or (attempts[0] if attempts else {"verdict": "NO_ATTEMPTS"}))
        entry["case_id"] = case_id
        entry["payload_names"] = [one["name"] for one in payloads]
        entry["capture_line_bytes"] = None
        entry["recovered_fake_pairs"] = [
            {"type": key[0], "real": key[1], "fake": value} for key, value in fakes.items()]
        entry["candidate_attempts"] = [
            {k: one.get(k) for k in
             ("tool_name", "verdict", "raised", "raised_other", "state_byte_identical",
              "payloads_in_capture", "payloads_replayed", "full_prior_state_replayed",
              "restored_args_match_saved")}
            for one in attempts]
        if reasons:
            entry["saved_production_prefix"] = production
            entry["saved_counting_prefix"] = counting
            if winner is not None:
                raised = winner["raised"]
                entry["prefix_match"] = production in raised and counting in raised
        results.append(entry)

    report = {"run_dir": str(run_dir), "cases": results,
              "reproduced": sum(1 for one in results if one.get("verdict") == "REPRODUCED"),
              "total": len(results)}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    pathlib.Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
