"""Data-only, GET-only dialogue discovery and fail-closed completeness validation.

A Langfuse session is a search scope, NOT a dialogue identity. Source responses
and request provenance go only to immutable encrypted RunStore artifacts. Public
results contain counts, hashes, types and fixed reason codes, never source IDs,
text, tool names, metadata keys/values or exception representations.

A growing model prompt is useful evidence, not proof of original history. The
optional authoritative-thread-v1 adapter below is deliberately NOT inferred from
Langfuse metadata: its schema must be backed by a separately established producer
contract. Without that evidence even an excellent terminal prompt is not_proven.
"""

import argparse
import collections
import datetime as dt
import json
import re
import sys
import urllib.parse

from .corpus import snapshots
from .langfuse import Client, attribution, credentials, iso
from .storage import PilotError, RunStore, canonical, digest, hashed

MAX_DETAILS = 50
MAX_CANDIDATES = 3
MAX_LIST_PAGES = 4
ROLES = {"system", "developer", "user", "assistant", "tool"}


def error_code(exc):
    # Do not stringify arbitrary errors, including bodies/URLs from other libs.
    if isinstance(exc, PilotError) and exc.args and isinstance(exc.args[0], str):
        code = exc.args[0]
        if re.fullmatch(r"(?:http_status_|http_retries_exhausted_)\d{3}", code):
            return code
        if code in {"response_size_cap", "response_json_invalid", "response_schema_invalid",
                    "network_retries_exhausted", "redirect_refused", "detail_budget_exhausted",
                    "pagination_schema_invalid", "pagination_total_invalid", "pagination_total_changed",
                    "pagination_duplicate_id", "pagination_row_id_missing", "pagination_incomplete",
                    "pagination_cap_incomplete", "pagination_count_exceeds_total",
                    "pagination_page_mismatch", "pagination_total_missing", "filter_not_honored",
                    "trace_detail_id_mismatch", "trace_detail_session_mismatch"}:
            return code
    return "intake_error"


class Capture:
    """Only connector state lives here; no alternate HTTP transport/provider path."""

    def __init__(self, client, store, detail_limit=MAX_DETAILS):
        if not 1 <= detail_limit <= MAX_DETAILS:
            raise PilotError("invalid_detail_budget")
        self.client, self.store = client, store
        self.detail_limit = detail_limit
        self.detail_requests = 0
        self.records = []

    def get(self, path, params=None):
        detail = path.startswith("/api/public/traces/") or "observations" in path
        if detail:
            if self.detail_requests >= self.detail_limit:
                raise PilotError("detail_budget_exhausted")
            self.detail_requests += 1
        number = len(self.records)
        record = {"method": "GET", "path": path, "params": params,
                  "request_sha256": hashed([path, params]), "number": number}
        try:
            value = self.client.get(path, params)
        except Exception as exc:
            record["error"] = error_code(exc)
            self.store.encrypt("response-" + str(number).zfill(4) + ".aesgcm", record)
            self.records.append(record)
            raise PilotError(record["error"]) from None
        receipt = self.client.response_receipts[-1] if self.client.response_receipts else None
        record.update({"response": value, "wire_receipt": receipt})
        self.store.encrypt("response-" + str(number).zfill(4) + ".aesgcm", record)
        self.records.append(record)
        return value


def page_total(payload):
    data, meta = payload.get("data"), payload.get("meta")
    if not isinstance(data, list) or not isinstance(meta, dict):
        raise PilotError("pagination_schema_invalid")
    total = meta.get("totalItems", meta.get("totalCount"))
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise PilotError("pagination_total_missing")
    return data, meta, total


def collect_pages(capture, path, params=None, predicate=None, max_pages=MAX_LIST_PAGES):
    """No implicit time window; stop incomplete on cap, drift, duplicate or scope leak."""
    if not 1 <= max_pages <= MAX_LIST_PAGES:
        raise PilotError("invalid_page_cap")
    rows, seen, total, pages = [], set(), None, []
    for page in range(1, max_pages + 1):
        query = dict(params or {}, page=page, limit=100)
        payload = capture.get(path, query)
        data, meta, current = page_total(payload)
        if meta.get("page", page) != page:
            raise PilotError("pagination_page_mismatch")
        if total is not None and total != current:
            raise PilotError("pagination_total_changed")
        total = current
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
                raise PilotError("pagination_row_id_missing")
            if row["id"] in seen:
                raise PilotError("pagination_duplicate_id")
            if predicate is not None and not predicate(row):
                raise PilotError("filter_not_honored")
            rows.append(row)
            seen.add(row["id"])
        pages.append({"page": page, "returned": len(data), "server_total": total,
                      "response_sha256": hashed(payload), "query_sha256": hashed(query)})
        if len(rows) > total:
            raise PilotError("pagination_count_exceeds_total")
        if len(rows) == total:
            return rows, {"complete": True, "mode": "page-total", "pages": pages,
                          "total": total, "no_time_window": True}
        if not data:
            raise PilotError("pagination_incomplete")
    raise PilotError("pagination_cap_incomplete")


def identity_summary(traces):
    attrs = [attribution(trace) for trace in traces]
    tenants = {key for attr in attrs for key in attr["tenant_evidence"]}
    dialogs = {key for attr in attrs for key in attr["dialog_evidence"]}
    pairs = {(attr["tenant_id"], next(iter(attr["dialog_evidence"]))) for attr in attrs
             if attr["tenant_status"] == "attributed" and len(attr["dialog_evidence"]) == 1}
    all_attributed = bool(traces) and len(pairs) == 1 and all(
        attr["tenant_status"] == "attributed" and len(attr["dialog_evidence"]) == 1 for attr in attrs)
    return {"traces": len(traces), "trusted_tenants": len(tenants), "explicit_dialogs": len(dialogs),
            "trusted_pairs": len(pairs), "unattributed_traces": sum(
                attr["tenant_status"] != "attributed" or len(attr["dialog_evidence"]) != 1 for attr in attrs),
            "single_trusted_identity": all_attributed,
            "identity_sha256": hashed(next(iter(pairs))) if all_attributed else None,
            "aggregate_scope": len(tenants) > 1 or len(dialogs) > 1}


def source_snapshots(traces):
    """Keep exact arrays and source pointers; never concatenate independent traces.

    Generic arrays found under input/output are discovery candidates only. The
    validator additionally requires authoritative source schema/sequence evidence
    before any such candidate can be called a complete chat.
    """
    sources = []
    for trace in traces:
        tid = trace.get("id")
        for field in ("input", "output"):
            sources.append(("trace:" + str(tid) + "/" + field, trace.get(field)))
        for field in ("observations", "pilot_observations_list"):
            for index, obs in enumerate(trace.get(field) or []):
                if isinstance(obs, dict):
                    for side in ("input", "output"):
                        sources.append(("trace:" + str(tid) + "/" + field + "/" + str(index) + "/" + side,
                                        obs.get(side)))
    result = snapshots(sources)
    result["paired_generation_sequences"] = generation_sequences(traces)
    return result


def decoded(value):
    if isinstance(value, str) and value.lstrip().startswith(("[", "{")):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, RecursionError):
            pass
    return value


def generation_sequences(traces):
    """Pair ONLY one generation's exact input and explicit assistant message.

    No prose-to-assistant coercion or guessed custom tool conversion. Both halves
    carry original pointers. These are observed contexts, not certified threads.
    """
    collected = {}
    for trace in traces:
        for field in ("observations", "pilot_observations_list"):
            for index, obs in enumerate(trace.get(field) or []):
                if not isinstance(obs, dict) or obs.get("type") != "GENERATION":
                    continue
                before, after = decoded(obs.get("input")), decoded(obs.get("output"))
                before_pointer = "/input"
                if isinstance(before, dict) and isinstance(before.get("messages"), list):
                    before, before_pointer = before["messages"], "/input/messages"
                if not isinstance(before, list) or not before or not all(
                        isinstance(message, dict) and message.get("role") in ROLES for message in before):
                    continue
                if not isinstance(after, dict) or after.get("role") != "assistant":
                    continue
                messages = before + [after]
                sha = hashed(messages)
                row = collected.setdefault(sha, {"sha256": sha, "messages": messages, "provenance": [],
                    "source_backed_input_output_pair": True, "source_trace_ids": []})
                row["source_trace_ids"].append(trace["id"])
                base = "/" + field + "/" + str(index)
                row["provenance"].append({"trace_id": trace["id"], "observation_id": obs.get("id"),
                    "input_pointer": base + before_pointer, "output_pointer": base + "/output"})
    return list(collected.values())


def sequence_check(messages):
    """ID-linked tools in source order, including Anthropic content blocks.

    Tool names/content equality never link a call. Repeated normal messages are
    retained by position. Unknown formats are evidence gaps, not auto-repaired.
    """
    reasons, calls, results = set(), {}, {}
    users = assistants = 0
    first_dialog_role = None
    pending = set()
    for position, message in enumerate(messages):
        if not isinstance(message, dict) or message.get("role") not in ROLES:
            reasons.add("unsupported_message_role")
            continue
        role = message["role"]
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        block_results = [block for block in blocks if isinstance(block, dict) and block.get("type") == "tool_result"]
        if role == "user" and (not block_results or any(isinstance(block, dict)
                and block.get("type") == "text" and block.get("text") for block in blocks)):
            users += 1
        if "content" not in message and not message.get("tool_calls"):
            reasons.add("message_payload_missing")
        if role == "assistant":
            assistants += 1
        if role not in ("system", "developer") and first_dialog_role is None:
            first_dialog_role = role
        if role == "function" or message.get("function_call"):
            reasons.add("legacy_tools_without_authoritative_call_id")
        if pending and role not in ("tool",) and not block_results:
            reasons.add("tool_result_missing_before_next_message")
        declarations = message.get("tool_calls", [])
        if not isinstance(declarations, list):
            declarations = []
            reasons.add("tool_calls_shape_invalid")
        declarations = declarations + [block for block in blocks if isinstance(block, dict) and block.get("type") == "tool_use"]
        for call in declarations:
            if not isinstance(call, dict):
                reasons.add("tool_call_shape_invalid")
                continue
            cid = call.get("id")
            function = call.get("function", call)
            if role != "assistant":
                reasons.add("tool_call_not_assistant")
            if not isinstance(cid, str) or not cid:
                reasons.add("tool_call_id_missing")
                continue
            if cid in calls:
                reasons.add("tool_call_id_reused")
            if not isinstance(function, dict) or not function.get("name") or not any(
                    key in function for key in ("arguments", "input")):
                reasons.add("tool_call_payload_missing")
            calls[cid] = position
            pending.add(cid)
        result_nodes = ([message] if role == "tool" else []) + block_results
        for node in result_nodes:
            cid = node.get("tool_call_id", node.get("tool_use_id"))
            if not isinstance(cid, str) or not cid:
                reasons.add("tool_result_id_missing")
                continue
            if cid not in calls or calls[cid] >= position:
                reasons.add("orphan_or_out_of_order_tool_result")
            if cid in results:
                reasons.add("duplicate_tool_result")
            if "content" not in node:
                reasons.add("tool_result_payload_missing")
            results[cid] = position
            pending.discard(cid)
    if pending:
        reasons.add("unpaired_tool_call")
    if first_dialog_role != "user":
        reasons.add("first_observed_dialog_message_not_user")
    terminal = messages[-1] if messages and isinstance(messages[-1], dict) else {}
    terminal_blocks = terminal.get("content") if isinstance(terminal.get("content"), list) else []
    if terminal.get("role") != "assistant" or terminal.get("tool_calls") or any(
            isinstance(block, dict) and block.get("type") == "tool_use" for block in terminal_blocks):
        reasons.add("terminal_assistant_response_not_captured")
    if users < 2:
        reasons.add("not_multi_turn_chat")
    return {"messages": len(messages), "user_turns": users, "assistant_messages": assistants,
            "tool_calls": len(calls), "tool_results": len(results),
            "tool_roundtrips": sum(cid in results and calls[cid] < results[cid] for cid in calls),
            "reasons": sorted(reasons)}


def message_call_ids(messages):
    found = set()
    for message in messages:
        if not isinstance(message, dict):
            continue
        calls = message.get("tool_calls") or []
        blocks = message.get("content") if isinstance(message.get("content"), list) else []
        for call in (calls if isinstance(calls, list) else []) + [block for block in blocks
                if isinstance(block, dict) and block.get("type") == "tool_use"]:
            if isinstance(call, dict) and isinstance(call.get("id"), str) and call["id"]:
                found.add(call["id"])
    return found


def prefix_evidence(candidate, observed):
    """Exact prefixes/call IDs corroborate capture, NOT its actual starting point."""
    prefixes, id_prefixes, call_id_prefixes = set(), set(), set()
    for row in observed:
        before = row["messages"]
        if len(before) < len(candidate) and candidate[:len(before)] == before:
            prefixes.add(hashed(before))
            ids = [message.get("id") for message in before]
            if ids and all(isinstance(mid, str) and mid for mid in ids) and len(set(ids)) == len(ids):
                id_prefixes.add(hashed(ids))
            if message_call_ids(before):
                call_id_prefixes.add(hashed(before))
    return {"distinct_exact_prefixes": len(prefixes), "prefixes_with_message_ids": len(id_prefixes),
            "prefixes_with_tool_call_ids": len(call_id_prefixes),
            "prefixes_do_not_prove_beginning": True}


def authoritative_check(messages, history, identity):
    """Validate full thread state under an EXTERNALLY established producer schema.

    The descriptor is a trust input, not authentication by itself: a hash cannot
    establish that a producer really promises creation-to-closure event coverage.
    The caller must first review those semantics. Discovery never manufactures a
    descriptor from Langfuse metadata or prompt appearance. No text heuristic
    (including 'summary' in user text) establishes compaction.
    """
    reasons = set()
    if not history:
        return ["earliest_history_not_proven", "terminal_history_not_proven",
                "capture_truncation_or_compaction_unknown", "authoritative_sequence_missing"]
    if not isinstance(history, dict):
        return ["authoritative_contract_not_established"]
    contract = history.get("contract", {})
    source = history.get("source", {})
    if not isinstance(contract, dict) or not isinstance(source, dict):
        return ["authoritative_contract_not_established"]
    if contract.get("schema") != "authoritative-thread-v1" or not all(
            isinstance(contract.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", contract[key])
            for key in ("producer_contract_sha256", "source_response_sha256")) or not (
            isinstance(contract.get("source_pointer"), str) and contract["source_pointer"].startswith("/")):
        reasons.add("authoritative_contract_not_established")
    if contract.get("source_response_sha256") != hashed(source):
        reasons.add("authoritative_source_hash_mismatch")
    expected_identity = tuple(identity) if isinstance(identity, (tuple, list)) else ()
    if (source.get("tenant_id"), source.get("dialog_id")) != expected_identity:
        reasons.add("authoritative_identity_mismatch")
    if source.get("history_complete") is not True or source.get("has_more") is not False:
        reasons.add("authoritative_history_incomplete")
    if source.get("truncated") is not False or source.get("compacted") is not False:
        reasons.add("capture_truncation_or_compaction_unknown")
    if source.get("state") != "closed":
        reasons.add("terminal_history_not_proven")
    events = source.get("events")
    if not isinstance(events, list) or not events:
        return sorted(reasons | {"authoritative_sequence_missing"})
    if not all(isinstance(event, dict) for event in events):
        return sorted(reasons | {"authoritative_event_shape_invalid"})
    event_ids = [event.get("id") for event in events]
    if not all(isinstance(mid, str) and mid for mid in event_ids) or len({hashed(mid) for mid in event_ids}) != len(events):
        reasons.add("authoritative_event_ids_invalid")
    if source.get("first_event_id") != event_ids[0] or source.get("last_event_id") != event_ids[-1]:
        reasons.add("authoritative_boundaries_mismatch")
    if source.get("history_origin") != "creation" or source.get("created_event_id") != event_ids[0]:
        reasons.add("earliest_history_not_proven")
    if type(source.get("event_count")) is not int or source["event_count"] != len(events):
        reasons.add("authoritative_event_count_mismatch")
    sequences = [event.get("sequence") for event in events]
    if type(source.get("first_sequence")) is not int or source["first_sequence"] != 0 or not all(
            type(sequence) is int for sequence in sequences) or sequences != list(range(len(events))):
        reasons.add("earliest_history_or_sequence_gap")
    if [event.get("message") for event in events] != messages:
        reasons.add("authoritative_messages_mismatch")
    return sorted(reasons)


def validate_dialogue(messages, *, identity=None, capture_complete=False, history=None, observed=()):
    measures = sequence_check(messages)
    reasons = set(measures.pop("reasons"))
    if not isinstance(identity, (tuple, list)) or len(identity) != 2 or not all(
            isinstance(value, str) and value for value in identity):
        reasons.add("trusted_tenant_dialog_identity_missing")
    if capture_complete is not True:
        reasons.add("trace_or_observation_capture_incomplete")
    reasons.update(authoritative_check(messages, history, identity))
    prefix = prefix_evidence(messages, observed)
    return {"status": "complete" if not reasons else "not_proven",
            "eligible_for_dialogue_corpus": not reasons, "reasons": sorted(reasons),
            "sequence_sha256": hashed(messages), "identity_sha256": hashed(identity) if identity else None,
            **measures, **prefix}


def assess_scope(traces, capture_complete):
    identity = identity_summary(traces)
    snap = source_snapshots(traces)
    observed = []
    for trace in traces:
        local = source_snapshots([trace])
        observed.extend(local["maximal"] + local["paired_generation_sequences"])
    distinct = {}
    for row in snap["maximal"] + snap["paired_generation_sequences"]:
        # Prefer the pair's stronger input/output provenance for exact duplicates.
        distinct[row["sha256"]] = row
    maximal = [row for row in distinct.values() if not any(
        len(other["messages"]) > len(row["messages"]) and
        other["messages"][:len(row["messages"])] == row["messages"] for other in distinct.values())]
    by_id = {trace["id"]: trace for trace in traces}
    candidates = []
    for row in maximal:
        tids = set(row.get("source_trace_ids", []))
        for provenance in row["provenance"]:
            source = provenance.get("source", "")
            if source.startswith("trace:"):
                tids.add(source[6:].split("/", 1)[0])
        source_traces = [by_id[tid] for tid in tids if tid in by_id]
        source_identity = identity_summary(source_traces)
        trusted = None
        if source_identity["single_trusted_identity"]:
            attr = attribution(source_traces[0])
            trusted = (attr["tenant_id"], next(iter(attr["dialog_evidence"])))
        # Corroboration must be from a different trace, not duplicate list/embed IO.
        independent = []
        for before in observed:
            before_tids = set(before.get("source_trace_ids", []))
            before_tids.update(p.get("source", "")[6:].split("/", 1)[0]
                               for p in before["provenance"] if p.get("source", "").startswith("trace:"))
            if before_tids - tids:
                independent.append(before)
        verdict = validate_dialogue(row["messages"], identity=trusted,
                                    capture_complete=capture_complete, observed=independent)
        verdict["source_trace_count"] = len(tids)
        verdict["source_backed_terminal_response"] = bool(row.get("source_backed_input_output_pair"))
        if identity["aggregate_scope"]:
            verdict["reasons"] = sorted(set(verdict["reasons"]) | {"session_aggregates_distinct_identities"})
            verdict["status"] = "not_proven"
            verdict["eligible_for_dialogue_corpus"] = False
        candidates.append(verdict)
    return {"identity": identity, "distinct_snapshots": snap["distinct_snapshots"],
            "source_backed_generation_sequences": len(snap["paired_generation_sequences"]),
            "maximal_contexts": len(candidates), "candidates": candidates,
            "max_observed_user_turns": max((row["user_turns"] for row in candidates), default=0),
            "max_observed_tool_roundtrips": max((row["tool_roundtrips"] for row in candidates), default=0),
            "complete_dialogues": sum(row["status"] == "complete" for row in candidates)}


def run_discovery(run_id, inventory_id="inventory-local-pilot"):
    prior = RunStore(inventory_id, False)
    parent = prior.verify()
    inventory = prior.read_encrypted("inventory.aesgcm")["traces"]
    store = RunStore(run_id, True)
    capture = Capture(Client(credentials(), attempts=1), store)
    errors, sessions, session_proof, metadata = [], [], None, None
    try:
        sessions, session_proof = collect_pages(capture, "/api/public/sessions")
    except PilotError as exc:
        errors.append({"stage": "sessions", "reason": error_code(exc)})
    try:
        # Default fields are portable on this deployment; the first recorded
        # probe's unsupported field-group combination returned 422 and was NOT
        # retried. Future runs need not repeat that already-refuted combination.
        metadata = capture.get("/api/public/traces", {"limit": 1, "page": 1})
    except PilotError as exc:
        errors.append({"stage": "metadata", "reason": error_code(exc)})
    grouped = collections.defaultdict(list)
    for trace in inventory:
        if trace.get("sessionId"):
            grouped[trace["sessionId"]].append(trace)
    # These counts are inventory selection hints only, not all-history totals.
    eligible = [(sid, rows) for sid, rows in grouped.items() if 5 <= len(rows) <= 99]
    selected = sorted(eligible, key=lambda item: (len(item[1]), hashed(item[0])))[:MAX_CANDIDATES]
    store.encrypt("selection.aesgcm", {"sessions": sessions,
        "selected": [{"session_id": sid, "inventory_traces": rows} for sid, rows in selected]})
    manifest = store.finish({"kind": "dialogue-discovery", "parent_run_id": inventory_id,
        "parent_manifest_sha256": hashed(parent), "sessions": len(sessions),
        "session_listing_proof": session_proof, "preferred_inventory_candidates": len(eligible),
        "selected": [{"session_sha256": hashed(sid), "inventory_traces": len(rows)} for sid, rows in selected],
        "metadata_probe_rows": len(metadata.get("data", [])) if metadata else 0,
        "metadata_nonempty_rows": sum(bool(row.get("metadata")) for row in metadata.get("data", [])) if metadata else 0,
        "requests": capture.client.requests, "detail_requests": capture.detail_requests,
        "retries": capture.client.retries, "errors": errors, "provider_calls": 0, "cost_usd": 0,
        "remote_mutations": 0, "payload_redacted": False,
        "response_capture": "decoded_original_json_with_original_wire_hash_and_size_receipts"})
    return manifest


def run_collection(run_id, discovery_id):
    prior = RunStore(discovery_id, False)
    parent = prior.verify()
    selection = prior.read_encrypted("selection.aesgcm")["selected"]
    store = RunStore(run_id, True)
    capture = Capture(Client(credentials(), attempts=1), store)
    results = []
    for number, chosen in enumerate(selection[:MAX_CANDIDATES]):
        sid = chosen["session_id"]
        rows, details, obs_proofs, errors, proof = [], [], [], [], None
        try:
            # No timestamps: enumerate the entire selected source session.
            rows, proof = collect_pages(capture, "/api/public/traces", {"sessionId": sid,
                "orderBy": "timestamp.asc"}, lambda row: row.get("sessionId") == sid)
            if not {row["id"] for row in chosen["inventory_traces"]}.issubset({row["id"] for row in rows}):
                raise PilotError("filter_not_honored")
            # Refuse to turn a discovery scope into a large unbounded export.
            if not 5 <= len(rows) <= 99 or len(rows) > capture.detail_limit - capture.detail_requests:
                errors.append("candidate_exceeds_remaining_detail_budget")
            else:
                for row in sorted(rows, key=lambda item: (item.get("timestamp", ""), item["id"])):
                    detail = capture.get("/api/public/traces/" + urllib.parse.quote(row["id"], safe=""))
                    if detail.get("id") != row["id"]:
                        raise PilotError("trace_detail_id_mismatch")
                    if detail.get("sessionId") != sid:
                        raise PilotError("trace_detail_session_mismatch")
                    details.append(detail)
                # Spend remaining budget on independently complete observation
                # lists only when the entire candidate can fit. Embeds alone
                # never certify completeness, even when apparently exhaustive.
                if len(rows) <= capture.detail_limit - capture.detail_requests:
                    for detail in details:
                        tid = detail["id"]
                        observations, obs_proof = collect_pages(capture, "/api/public/observations",
                            {"traceId": tid}, lambda obs: obs.get("traceId", obs.get("trace_id")) == tid)
                        embedded = detail.get("observations") or []
                        embedded_ids = {item.get("id") if isinstance(item, dict) else item
                                        for item in embedded if isinstance(item, (str, dict))}
                        if not embedded_ids.issubset({item["id"] for item in observations}):
                            raise PilotError("filter_not_honored")
                        detail["pilot_observations_list"] = observations
                        obs_proofs.append({"trace_sha256": hashed(tid), **obs_proof})
                else:
                    errors.append("independent_observation_lists_not_collected_budget")
        except PilotError as exc:
            errors.append(error_code(exc))
        complete_capture = bool(proof and proof["complete"] and len(details) == len(rows)
                                and len(obs_proofs) == len(rows) and not errors)
        # Each original response was already saved, untouched, before adding the
        # separately identified observation list to the derived source container.
        store.encrypt("candidate-" + str(number).zfill(4) + ".aesgcm", {
            "session_id": sid, "trace_listing": rows, "details": details,
            "trace_listing_proof": proof, "observation_proofs": obs_proofs, "errors": errors})
        result = {"session_sha256": hashed(sid), "inventory_traces": len(chosen["inventory_traces"]),
                  "all_history_traces": len(rows), "detail_traces": len(details),
                  "independent_observation_lists": len(obs_proofs), "capture_complete": complete_capture,
                  "trace_listing_proof": proof, "listing_identity": identity_summary(rows),
                  "errors": errors, **assess_scope(details or rows, complete_capture)}
        results.append(result)
    return store.finish({"kind": "dialogue-candidates", "parent_run_id": discovery_id,
        "parent_manifest_sha256": hashed(parent), "scopes": results,
        "created_utc": iso(dt.datetime.now(dt.timezone.utc)),
        "requests": capture.client.requests, "detail_requests": capture.detail_requests,
        "retries": capture.client.retries, "provider_calls": 0, "cost_usd": 0,
        "remote_mutations": 0, "payload_redacted": False,
        "complete_dialogues": sum(row["complete_dialogues"] for row in results),
        "response_capture": "decoded_original_json_with_original_wire_hash_and_size_receipts",
        "remaining_evidence_needed": ["authoritative_tenant_scoped_thread_identity",
            "producer_contract_for_full_ordered_thread_history_from_creation",
            "authoritative_first_last_event_ids_and_contiguous_sequence_count",
            "all_original_user_assistant_tool_events_including_final_assistant_output",
            "explicit_no_deletion_no_compaction_no_truncation_and_closed_or_versioned_cutoff"]})


def run_assessment(run_id, collection_id):
    """Reprocess retained originals only; never retry or fetch another scope."""
    prior = RunStore(collection_id, False)
    parent = prior.verify()
    if parent.get("kind") != "dialogue-candidates":
        raise PilotError("assessment_requires_candidate_run")
    store = RunStore(run_id, True)
    results = []
    for number in range(len(parent["scopes"])):
        raw = prior.read_encrypted("candidate-" + str(number).zfill(4) + ".aesgcm")
        # Listing's default fields happened to return original IO and metadata.
        # They can REFUTE a session identity without a large full-detail export;
        # a listing alone cannot certify full observation coverage.
        by_id = {row["id"]: row for row in raw["trace_listing"]}
        by_id.update({row["id"]: row for row in raw["details"]})
        traces = list(by_id.values())
        capture_complete = parent["scopes"][number]["capture_complete"]
        result = {"session_sha256": hashed(raw["session_id"]),
                  "listing_identity": identity_summary(raw["trace_listing"]),
                  "all_history_traces": len(raw["trace_listing"]), "detail_traces": len(raw["details"]),
                  "capture_complete": capture_complete,
                  "trace_listing_proof": raw["trace_listing_proof"],
                  **assess_scope(traces, capture_complete)}
        store.encrypt("assessment-" + str(number).zfill(4) + ".aesgcm", result)
        results.append(result)
    return store.finish({"kind": "dialogue-assessment", "parent_run_id": collection_id,
        "parent_manifest_sha256": hashed(parent), "scopes": results,
        "requests": 0, "detail_requests": 0, "retries": 0, "provider_calls": 0, "cost_usd": 0,
        "remote_mutations": 0, "payload_redacted": False,
        "complete_dialogues": sum(row["complete_dialogues"] for row in results),
        "remaining_evidence_needed": parent["remaining_evidence_needed"],
        "authoritative_adapter_trust": "producer_semantics_must_be_established_externally_not_by_a_hash_or_flag"})


def public_summary(manifest):
    summary = {key: manifest[key] for key in ("run_id", "kind", "parent_run_id", "requests",
        "detail_requests", "retries", "provider_calls", "cost_usd", "remote_mutations") if key in manifest}
    if "scopes" not in manifest:
        summary.update({key: manifest[key] for key in ("sessions", "selected", "errors") if key in manifest})
        return summary
    summary["complete_dialogues"] = manifest["complete_dialogues"]
    summary["scopes"] = []
    for row in manifest["scopes"]:
        summary["scopes"].append({key: row[key] for key in ("session_sha256", "all_history_traces",
            "detail_traces", "capture_complete", "identity", "listing_identity", "maximal_contexts",
            "max_observed_user_turns", "max_observed_tool_roundtrips", "complete_dialogues", "errors") if key in row})
        summary["scopes"][-1]["observed_contexts"] = sorted(row["candidates"],
            key=lambda item: (-item["user_turns"], -item["tool_roundtrips"], item["sequence_sha256"]))[:4]
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("discover", "collect", "assess"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--parent", default="inventory-local-pilot")
    args = parser.parse_args(argv)
    try:
        operation = {"discover": run_discovery, "collect": run_collection, "assess": run_assessment}[args.mode]
        result = operation(args.run_id, args.parent)
        print(json.dumps(public_summary(result), sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"error": error_code(exc), "provider_calls": 0, "cost_usd": 0}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
