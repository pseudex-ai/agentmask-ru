# regress_print.py — the offline product-path printer (tz-agentpii6.md §8.1, §7.1 G4).
#
#     cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.regress_print
#
# Runs the production path WITHOUT a model and WITHOUT a key: the dev bundle, an
# in-memory `Vault`, the `GatewayV5` masking, and every call the case declares
# driven through the real mock. It prints «тип статус число» — the build health
# (cases / exception / absent) until the phase stamp, then the full status table
# — plus «case_id <sha12>» so a line can be traced to a case without printing a
# single value.
#
# DETERMINISM (W0-R7). `pseudex.vault` draws every substitute from the stdlib
# `secrets` module, so this module replaces `vault.secrets` with a seeded stub
# BEFORE the first mint. Two processes print the same bytes, or the printer is
# not a regression instrument.
#
# WHY IT MAY IMPORT THE ENGINE. `contracts.PSEUDEX_ALLOWED_MODULES` lists exactly
# this module and `harness`; no PURE module imports it, which
# `test_harness.test_only_harness_imports_pseudex` and
# `test_pii_types.test_printer_not_imported` pin.

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

import pseudex.vault as vault

from bench.agentpii5.contracts import TYPES
from bench.agentpii5.harness import GatewayV5
from bench.agentpii5.mock import BackendV5, call_arguments, seed_backend_v5
from bench.agentpii5.schema import case_v5_from_json
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.maskcache import MaskCache
from pseudex.vault import Vault
from testkit import load_dev_bundle

_ORG = "agentpii5"
_HERE = Path(__file__).resolve().parent


class _SeededSecrets:
    """A `secrets`-shaped stub over a seeded `random.Random`. `vault` calls only
    `choice` and `randbelow` (grep `pseudex/vault.py`), so those two are the whole
    surface; anything else should raise rather than silently diverge."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def choice(self, seq):            # type: ignore[no-untyped-def]
        return self._rng.choice(seq)

    def randbelow(self, n: int) -> int:
        return self._rng.randrange(n)


def _patch_secrets(seed: int) -> None:
    vault.secrets = _SeededSecrets(seed)          # type: ignore[assignment]


def _thread_state(state: dict[str, str], tool: str, log) -> None:  # type: ignore[no-untyped-def]
    """The same state hand-off `mock._record_call` does: a claim id exists only
    after the booking that minted it, a document text only after the read."""
    result = log.result or {}
    if tool == "courier_book":
        state["claim_id"] = str(result.get("claim_id", ""))
    if tool == "doc_retrieve":
        state["document_text"] = str(result.get("body", ""))
    if tool == "file_read":
        state["document_text"] = str(result.get("text", ""))
    if tool == "mail_search":
        messages = result.get("messages")
        first = dict(messages[0]) if isinstance(messages, list) and messages else {}
        state["message_id"] = str(first.get("id", ""))


def _drive(case, detector: Detector) -> tuple[GatewayV5, BackendV5]:  # type: ignore[no-untyped-def]
    """The offline gateway arm: mask messages, drive every declared call through
    the mock, restoring the argument before the call and masking the result back.
    Faults are recorded on the gateway, never raised — a fault IS the health the
    printer reports."""
    base = Vault(":memory:", _ORG)
    gateway = GatewayV5(case, detector, base, AuditLog(":memory:"), MaskCache(256))
    backend = seed_backend_v5(case)
    gateway.push_system(case.base.messages[0].content)
    gateway.tools()
    for index, message in enumerate(case.base.messages):
        if message.role == "user":
            gateway.push_user(index)
    state: dict[str, str] = {}
    for expectation in case.returns:
        for ordinal in range(expectation.call_ordinal + 1):
            arguments = call_arguments(case, expectation.tool_name, ordinal, state)
            try:
                restored, _residual = gateway.restore_arguments(arguments)
            except Exception as broken:      # noqa: BLE001 — the fault is the datum
                gateway.fault(f"restore_arguments {type(broken).__name__}: {broken}")
                continue
            log = backend.call(expectation.tool_name, restored)
            _thread_state(state, expectation.tool_name, log)
            try:
                gateway.push_call(expectation.tool_name, log, backend.form_of(log.seq), 0, ordinal)
            except Exception as broken:      # noqa: BLE001
                gateway.fault(f"push_call {type(broken).__name__}: {broken}")
    return gateway, backend


def _health_lines(cases) -> list[str]:  # type: ignore[no-untyped-def]
    """«тип статус число» for the build health: cases, exception, absent. The
    full observed/leaked/residual/unmasked table arrives with the phase stamp."""
    detector = Detector()
    tally: dict[str, dict[str, int]] = {}
    for case in cases:
        gateway, _backend = _drive(case, detector)
        exception = 1 if gateway.faults else 0
        for item in case.base.pii:
            row = tally.setdefault(item.type, {"cases": 0, "exception": 0, "absent": 0})
            row["cases"] += 1
            if exception:
                row["exception"] = 1
        # A required IN/tool or IN/document hop is absent when the rendered
        # result carried no span for the item that hop names.
        tagged: dict[str, set[tuple[int, str]]] = {}
        for record in gateway.tool_records():
            for tag in record.spans_real:
                tagged.setdefault(record.tool_name, set()).add((record.call_ordinal, str(tag)))
        for hop in case.hops:
            if hop.kind != "IN" or hop.owner not in ("tool", "document"):
                continue
            if (hop.call_ordinal, hop.item_id) not in tagged.get(hop.tool_name, set()):
                tally[hop_item_type(case, hop.item_id)]["absent"] += 1
    out: list[str] = []
    for pii_type in TYPES:
        row = tally.get(pii_type)
        if not row:
            continue
        for status in ("cases", "exception", "absent"):
            out.append(f"{pii_type} {status} {row[status]}")
    return out


def hop_item_type(case, item_id: str) -> str:  # type: ignore[no-untyped-def]
    for item in case.base.pii:
        if item.id == item_id:
            return item.type
    return ""


def _tier_ids(ladder_path: Path, tier: str) -> set[str]:
    raw = json.loads(ladder_path.read_text(encoding="utf-8"))
    tiers = raw.get("tiers", raw)
    return set(tiers[tier])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="regress_print",
                                     description="offline product-path printer (G4/L9)")
    parser.add_argument("--corpus", default=str(_HERE / "corpus.v5.json"))
    parser.add_argument("--ladder", default=str(_HERE / "ladder.json"))
    parser.add_argument("--tier", default="nano",
                        help="the ladder tier; default nano (the committed one)")
    args = parser.parse_args(argv)

    _patch_secrets(0)
    load_dev_bundle()
    corpus_raw = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    all_cases = [case_v5_from_json(one) for one in corpus_raw["corpus"]]
    ladder_path = Path(args.ladder)
    if ladder_path.exists():
        ids = _tier_ids(ladder_path, args.tier)
        cases = [case for case in all_cases if case.base.id in ids]
    else:
        cases = all_cases
    if not cases:
        print(f"regress_print: tier {args.tier} is empty", file=sys.stderr)
        return 2

    for line in _health_lines(cases):
        print(line)
    for case in cases:
        digest = hashlib.sha256(case.base.id.encode("utf-8")).hexdigest()[:12]
        print(f"case_id {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
