"""Synthetic-only tests: no credentials, live network, model, business tool or PII labels."""

import copy
import unittest
from unittest.mock import Mock

from .dialogue_intake import (Capture, assess_scope, authoritative_check, collect_pages,
                             error_code, identity_summary, sequence_check, validate_dialogue)
from .storage import PilotError, hashed


def message(role, content, **fields):
    return {"role": role, "content": content, **fields}


def conversation():
    return [message("system", "SYNTHETIC policy", id="s"),
            message("user", "SYNTHETIC first", id="u1"),
            message("assistant", "SYNTHETIC answer", id="a1"),
            message("user", "SYNTHETIC second", id="u2"),
            message("assistant", None, id="a2", tool_calls=[{
                "id": "call-one", "type": "function", "function": {"name": "synthetic_lookup", "arguments": "{}"}}]),
            message("tool", {"synthetic": [1, 2]}, tool_call_id="call-one", id="t1"),
            message("assistant", "SYNTHETIC final", id="a3")]


def history(messages):
    source = {"tenant_id": "synthetic-tenant", "dialog_id": "synthetic-dialog",
              "history_complete": True, "has_more": False, "truncated": False,
              "compacted": False, "state": "closed", "first_sequence": 0,
              "history_origin": "creation", "created_event_id": "event-0",
              "first_event_id": "event-0", "last_event_id": "event-" + str(len(messages) - 1),
              "event_count": len(messages), "events": [{"id": "event-" + str(index),
                  "sequence": index, "message": value} for index, value in enumerate(messages)]}
    return {"source": source, "contract": {"schema": "authoritative-thread-v1",
            "producer_contract_sha256": "a" * 64, "source_response_sha256": hashed(source), "source_pointer": "/"}}


def validate(messages=None, **changes):
    messages = conversation() if messages is None else messages
    kwargs = {"identity": ("synthetic-tenant", "synthetic-dialog"), "capture_complete": True,
              "history": history(messages)}
    kwargs.update(changes)
    return validate_dialogue(messages, **kwargs)


class CompletenessTests(unittest.TestCase):
    def test_authoritative_full_multiturn_positive_preserves_source(self):
        original = conversation()
        before = copy.deepcopy(original)
        result = validate(original)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["user_turns"], 2)
        self.assertEqual(result["tool_roundtrips"], 1)
        self.assertEqual(original, before)
        self.assertFalse(result["reasons"])

    def test_system_first_prompt_is_not_beginning_proof(self):
        result = validate(history=None)
        self.assertEqual(result["status"], "not_proven")
        self.assertIn("earliest_history_not_proven", result["reasons"])
        self.assertIn("capture_truncation_or_compaction_unknown", result["reasons"])

    def test_independent_prefixes_corroborate_not_certify(self):
        messages = conversation()
        prefixes = [{"messages": messages[:length]} for length in (2, 4, 6)]
        result = validate(messages, history=None, observed=prefixes)
        self.assertEqual(result["distinct_exact_prefixes"], 3)
        self.assertEqual(result["prefixes_with_message_ids"], 3)
        self.assertEqual(result["status"], "not_proven")

    def test_history_missing_compacted_truncated_or_open_refused(self):
        for key, value, code in (("history_complete", False, "authoritative_history_incomplete"),
                                 ("has_more", True, "authoritative_history_incomplete"),
                                 ("compacted", True, "capture_truncation_or_compaction_unknown"),
                                 ("truncated", None, "capture_truncation_or_compaction_unknown"),
                                 ("state", "open", "terminal_history_not_proven")):
            with self.subTest(key=key):
                source = history(conversation())
                source["source"][key] = value
                source["contract"]["source_response_sha256"] = hashed(source["source"])
                result = validate(history=source)
                self.assertEqual(result["status"], "not_proven")
                self.assertIn(code, result["reasons"])

    def test_event_boundaries_sequence_and_payload_are_checked(self):
        mutations = [lambda obj: obj.update(first_sequence=1),
                     lambda obj: obj.update(first_event_id="not-first"),
                     lambda obj: obj.update(event_count=100),
                     lambda obj: obj["events"][2].update(sequence=4),
                     lambda obj: obj["events"][2].update(id="event-0"),
                     lambda obj: obj["events"][2]["message"].update(content="SYNTHETIC mismatch")]
        for mutate in mutations:
            source = copy.deepcopy(history(conversation()))
            mutate(source["source"])
            source["contract"]["source_response_sha256"] = hashed(source["source"])
            self.assertEqual(validate(history=source)["status"], "not_proven")

    def test_authoritative_source_hash_and_identity_must_match(self):
        source = history(conversation())
        source["source"]["tenant_id"] = "different-synthetic-tenant"
        result = validate(history=source)
        self.assertIn("authoritative_source_hash_mismatch", result["reasons"])
        self.assertIn("authoritative_identity_mismatch", result["reasons"])

    def test_ad_hoc_flag_without_producer_contract_cannot_certify(self):
        source = history(conversation())
        source["contract"] = {}
        self.assertIn("authoritative_contract_not_established", validate(history=source)["reasons"])

    def test_missing_identity_or_capture_refused(self):
        self.assertIn("trusted_tenant_dialog_identity_missing", validate(identity=None)["reasons"])
        self.assertIn("trusted_tenant_dialog_identity_missing", validate(identity=42)["reasons"])
        self.assertIn("trace_or_observation_capture_incomplete", validate(capture_complete=False)["reasons"])
        self.assertFalse(validate(capture_complete=False)["eligible_for_dialogue_corpus"])
        self.assertIn("authoritative_contract_not_established", validate(history=[1])["reasons"])

    def test_qa_fragment_and_missing_final_assistant_refused(self):
        self.assertIn("not_multi_turn_chat", validate(conversation()[:3])["reasons"])
        self.assertIn("terminal_assistant_response_not_captured", validate(conversation()[:-1])["reasons"])

    def test_missing_or_orphan_tool_results_refused(self):
        original = conversation()
        missing = original[:5] + original[6:]
        self.assertIn("unpaired_tool_call", validate(missing)["reasons"])
        orphan = original[:4] + original[5:]
        self.assertIn("orphan_or_out_of_order_tool_result", validate(orphan)["reasons"])

    def test_same_name_content_never_pairs_missing_call_id(self):
        messages = conversation()
        del messages[4]["tool_calls"][0]["id"]
        messages[5]["name"] = "synthetic_lookup"
        result = validate(messages)
        self.assertIn("tool_call_id_missing", result["reasons"])
        self.assertEqual(result["tool_roundtrips"], 0)

    def test_duplicate_call_result_and_out_of_order_refused(self):
        duplicate = conversation()
        duplicate.insert(6, copy.deepcopy(duplicate[5]))
        self.assertIn("duplicate_tool_result", validate(duplicate)["reasons"])
        out_of_order = conversation()
        out_of_order[4], out_of_order[5] = out_of_order[5], out_of_order[4]
        self.assertIn("orphan_or_out_of_order_tool_result", validate(out_of_order)["reasons"])

    def test_parallel_calls_are_linked_by_id_not_order(self):
        messages = conversation()
        call = copy.deepcopy(messages[4]["tool_calls"][0])
        call["id"] = "call-two"
        messages[4]["tool_calls"].append(call)
        messages.insert(5, message("tool", "SYNTHETIC second result", tool_call_id="call-two"))
        result = validate(messages)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["tool_roundtrips"], 2)

    def test_anthropic_tool_blocks_and_repeated_text_preserved(self):
        messages = conversation()[:4] + [message("assistant", [{"type": "tool_use", "id": "use-1",
            "name": "synthetic_lookup", "input": {}}]), message("user", [{"type": "tool_result",
            "tool_use_id": "use-1", "content": "SYNTHETIC result"}]), message("assistant", "SYNTHETIC final")]
        result = validate(messages)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["user_turns"], 2)
        self.assertEqual(result["tool_roundtrips"], 1)
        repeated = [message("user", "SYNTHETIC repeat"), message("assistant", "SYNTHETIC repeat")] * 3
        self.assertEqual(validate(repeated)["user_turns"], 3)

    def test_user_text_summary_is_not_a_compaction_heuristic(self):
        messages = conversation()
        messages[1]["content"] = "SYNTHETIC please write a summary"
        self.assertEqual(validate(messages)["status"], "complete")

    def test_false_beginning_marker_and_bool_sequence_refused(self):
        for key, value in (("history_origin", "unknown"), ("created_event_id", "not-first"),
                           ("first_sequence", False), ("event_count", True)):
            source = history(conversation())
            source["source"][key] = value
            source["contract"]["source_response_sha256"] = hashed(source["source"])
            self.assertEqual(validate(history=source)["status"], "not_proven")

    def test_malformed_authoritative_events_and_messages_fail_closed(self):
        for events in ((None,), ([{}],), ("not-object",)):
            source = history(conversation())
            source["source"]["events"] = list(events)
            source["contract"]["source_response_sha256"] = hashed(source["source"])
            self.assertEqual(validate(history=source)["status"], "not_proven")
        self.assertIn("unsupported_message_role", validate_dialogue([None])["reasons"])

    def test_missing_message_payload_is_not_forgiven(self):
        messages = conversation()
        del messages[1]["content"]
        self.assertIn("message_payload_missing", validate(messages)["reasons"])


class ScopeTests(unittest.TestCase):
    def trace(self, tenant="synthetic-tenant", dialog="synthetic-dialog", **fields):
        return {"id": "synthetic-trace", "sessionId": "synthetic-session", "userId": "not-a-tenant",
                "metadata": {"org_id": tenant, "dialog_id": dialog}, **fields}

    def test_aggregate_sessions_refused_not_merged(self):
        traces = [self.trace(input={"messages": conversation()}),
                  self.trace(tenant="other-synthetic", dialog="another-synthetic")]
        result = assess_scope(traces, True)
        self.assertTrue(result["identity"]["aggregate_scope"])
        self.assertEqual(result["complete_dialogues"], 0)
        self.assertIn("session_aggregates_distinct_identities", result["candidates"][0]["reasons"])

    def test_backend_user_id_and_session_never_tenant_or_dialog(self):
        result = identity_summary([self.trace(metadata={})])
        self.assertFalse(result["single_trusted_identity"])
        self.assertEqual(result["trusted_tenants"], 0)
        self.assertEqual(result["explicit_dialogs"], 0)

    def test_terminal_generation_output_is_source_backed_not_invented(self):
        messages = conversation()
        trace = self.trace(observations=[{"id": "synthetic-generation", "type": "GENERATION",
            "input": messages[:-1], "output": messages[-1]}])
        before = copy.deepcopy(trace)
        result = assess_scope([trace], True)
        candidate = result["candidates"][0]
        self.assertTrue(candidate["source_backed_terminal_response"])
        self.assertNotIn("terminal_assistant_response_not_captured", candidate["reasons"])
        self.assertNotIn("trusted_tenant_dialog_identity_missing", candidate["reasons"])
        self.assertIn("earliest_history_not_proven", candidate["reasons"])
        self.assertEqual(candidate["distinct_exact_prefixes"], 0)
        self.assertEqual(candidate["status"], "not_proven")
        self.assertEqual(before, trace)

    def test_plain_output_string_never_fabricated_as_assistant_message(self):
        trace = self.trace(observations=[{"id": "synthetic-generation", "type": "GENERATION",
            "input": conversation()[:-1], "output": "SYNTHETIC response without role"}])
        result = assess_scope([trace], True)
        self.assertFalse(result["candidates"][0]["source_backed_terminal_response"])
        self.assertIn("terminal_assistant_response_not_captured", result["candidates"][0]["reasons"])


class CollectionTests(unittest.TestCase):
    def capture(self, responses, cap=50):
        client = Mock()
        client.get.side_effect = responses
        client.response_receipts = [{"body_sha256": "a" * 64, "body_bytes": 123}]
        return Capture(client, Mock(), cap)

    def test_original_response_and_provenance_are_encrypted_not_modified(self):
        source = {"data": [{"id": "synthetic", "input": "SYNTHETIC untouched"}], "meta": {"totalItems": 1}}
        capture = self.capture([source])
        result = capture.get("/api/public/traces", {"limit": 1})
        self.assertIs(result, source)
        artifact = capture.store.encrypt.call_args.args[1]
        self.assertEqual(artifact["response"], source)
        self.assertEqual(artifact["method"], "GET")
        self.assertNotIn("authorization", artifact)

    def test_detail_cap_prevents_fifty_first_call(self):
        capture = self.capture([{}] * 50)
        for _ in range(50):
            capture.get("/api/public/traces/synthetic")
        with self.assertRaisesRegex(PilotError, "detail_budget_exhausted"):
            capture.get("/api/public/observations")
        self.assertEqual(capture.client.get.call_count, 50)

    def test_pagination_no_implicit_time_window_and_scope_checked(self):
        capture = self.capture([{"data": [{"id": "one", "sessionId": "s"}], "meta": {"totalItems": 2}},
                                {"data": [{"id": "two", "sessionId": "s"}], "meta": {"totalItems": 2}}])
        rows, proof = collect_pages(capture, "/api/public/traces", {"sessionId": "s"}, lambda row: row["sessionId"] == "s")
        self.assertEqual(len(rows), 2)
        self.assertTrue(proof["complete"])
        self.assertTrue(proof["no_time_window"])
        self.assertNotIn("fromTimestamp", capture.client.get.call_args.args[1])
        self.assertNotIn("toTimestamp", capture.client.get.call_args.args[1])

    def test_ignored_filter_duplicate_drift_cap_and_missing_total_fail(self):
        scenarios = [
            ([{"data": [{"id": "a", "sessionId": "other"}], "meta": {"totalItems": 1}}], "filter_not_honored"),
            ([{"data": [{"id": "a", "sessionId": "s"}], "meta": {"totalItems": 2}}] * 2, "pagination_duplicate_id"),
            ([{"data": [{"id": "a", "sessionId": "s"}], "meta": {"totalItems": 2}},
              {"data": [], "meta": {"totalItems": 3}}], "pagination_total_changed"),
            ([{"data": [], "meta": {}}], "pagination_total_missing"),
            ([{"data": [], "meta": {"totalItems": 1}}], "pagination_incomplete"),
        ]
        for values, code in scenarios:
            with self.subTest(code=code):
                with self.assertRaisesRegex(PilotError, code):
                    collect_pages(self.capture(values), "/api/public/traces", {"sessionId": "s"},
                                  lambda row: row.get("sessionId") == "s", max_pages=2)
        capture = self.capture([{"data": [{"id": "a"}], "meta": {"totalItems": 2}}])
        with self.assertRaisesRegex(PilotError, "pagination_cap_incomplete"):
            collect_pages(capture, "/api/public/traces", max_pages=1)

    def test_exception_content_never_crosses_boundary(self):
        self.assertEqual(error_code(ValueError("SYNTHETIC private body")), "intake_error")
        self.assertEqual(error_code(PilotError("SYNTHETIC private ID")), "intake_error")
        capture = self.capture([ValueError("SYNTHETIC private body")])
        with self.assertRaisesRegex(PilotError, "^intake_error$"):
            capture.get("/api/public/traces")
        self.assertNotIn("SYNTHETIC private body", str(capture.store.encrypt.call_args))


if __name__ == "__main__":
    unittest.main()
