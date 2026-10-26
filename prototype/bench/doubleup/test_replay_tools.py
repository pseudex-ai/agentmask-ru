"""Synthetic fail-capable replay tests. No files, sockets, Docker, models or tools.

Input-contract fixtures copy the actual declarations in backend tools/*:
search_tools.google_search(query, num=5), web_search_tool.internet_search,
read_webpage_tool.read_webpage, project_chat_tools, memory_tools and
personal_storage_tools. Resource bodies are invented TEST DATA, not customers.
Run: python -m bench.doubleup.test_replay_tools
"""
import copy
import unittest
from unittest.mock import patch

from .replay_tools import ReplayError, ReplayTools, check_schema, validate
from .source_resources import (attachment_locators, build_resources, captured_catalog,
                               captured_memory_documents, captured_transcript, declared_schema,
                               normalize_ejson, safe_projection, unique_calls)


def contract(name, fields, required=()):
    return {"name": name, "parameters": {"type": "object", "properties": fields, "required": list(required)},
            "schema_source": "synthetic_fixture_copied_from_backend_declaration"}


def contracts():
    string = {"type": "string"}
    return {
        "google_search": contract("google_search", {"query": string, "num": {"type": "integer", "default": 5}}, ("query",)),
        "internet_search": contract("internet_search", {"query": string, "max_results": {"type": "integer", "default": 5},
            "topic": {"type": "string", "enum": ["general", "news"], "default": "general"},
            "time_range": {"anyOf": [{"type": "string", "enum": ["day", "week", "month", "year"]}, {"type": "null"}], "default": None}}, ("query",)),
        "read_webpage": contract("read_webpage", {"url": string, "max_chars": {"type": "integer", "default": 8000}}, ("url",)),
        "project_chats_list": contract("project_chats_list", {"offset": {"type": "integer", "default": 0}}),
        "project_chat_read": contract("project_chat_read", {"thread_id": string, "last_n": {"type": "integer", "default": 20},
            "query": {"type": "string", "default": ""}}, ("thread_id",)),
        "personal_search": contract("personal_search", {"query": string, "folder": {"type": "string", "default": ""},
            "top_k": {"type": "integer", "default": 5}}, ("query",)),
        "personal_list_folders": contract("personal_list_folders", {}),
        "search_memory": contract("search_memory", {"query": string}, ("query",)),
        "save_to_memory": contract("save_to_memory", {"key": string, "value": string, "tags": {"type": "string", "default": ""},
            "importance": {"type": "integer", "default": 3}}, ("key", "value")),
        "personal_save": contract("personal_save", {"text": string, "folder": {"type": "string", "default": ""},
            "title": {"type": "string", "default": ""}}, ("text",)),
        "dataset_profile": contract("dataset_profile", {"dataset_id": {"type": "string", "default": ""}, "sheet": {"type": "string", "default": ""}}),
        "run_code": contract("run_code", {"code": string, "dataset_id": {"type": "string", "default": ""},
            "title": {"type": "string", "default": ""}}, ("code",)),
    }


def resources():
    ref = {"kind": "synthetic"}
    return {
        "coverage": {"web": "captured_documents_only", "threads": "complete", "personal": "complete",
                     "memory": "complete", "folders": "complete"},
        "web_documents": [{"url": "https://fixture.invalid/apples", "title": "Apples", "text": "Orchard harvest green apples", "provenance": ref},
                          {"url": "https://fixture.invalid/bikes", "title": "Bikes", "text": "Bicycle wheels road race", "provenance": ref}],
        "pages": [{"url": "https://fixture.invalid/apples", "title": "Apples", "body": "A" * 1200,
                   "complete": True, "total_chars": 1200, "provenance": ref}],
        "threads": [{"thread_id": "synthetic-thread-a", "title": "Orchard plan", "authorized": True,
                     "complete": True, "messages": [{"role": "user", "content": "plant apples"},
                                                        {"role": "assistant", "content": "buy bicycle"}], "provenance": ref},
                    {"thread_id": "synthetic-thread-private", "title": "Private", "authorized": False,
                     "complete": True, "messages": [], "provenance": ref}],
        "memories": [{"key": "orchard", "value": "green apple trees", "scope": "memory", "provenance": ref},
                     {"key": "bike", "value": "road bicycle", "scope": "personal", "folder": "sports", "provenance": ref}],
        "folders": ["sports"], "datasets": [], "missing": [],
    }


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.seed = resources()
        self.tools = ReplayTools(contracts(), self.seed, "none")

    def error(self, name, args, code):
        answer = self.tools.dispatch(name, args)
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["error"]["code"], code)
        self.assertEqual(answer["remote_mutations"], 0)
        return answer

    def result(self, name, args):
        answer = self.tools.dispatch(name, args)
        self.assertTrue(answer["ok"], answer)
        return answer["result"]

    def test_wrong_query_changes_results_and_can_return_empty(self):
        a = self.result("google_search", {"query": "apples"})["results"]
        b = self.result("google_search", {"query": "bicycle"})["results"]
        c = self.result("google_search", {"query": "unicorn"})["results"]
        self.assertEqual([r["title"] for r in a], ["Apples"])
        self.assertEqual([r["title"] for r in b], ["Bikes"])
        self.assertEqual(c, [])

    def test_internet_search_same_grounded_index_not_recorded_query(self):
        self.assertEqual(self.result("internet_search", {"query": "race"})["results"][0]["title"], "Bikes")
        self.assertEqual(self.result("internet_search", {"query": "none-such"})["results"], [])
        self.error("internet_search", {"query": "apples", "time_range": "day"}, "time_filter_unsupported")
        self.error("internet_search", {"query": "apples", "topic": "news"}, "resource_missing")

    def test_url_exact_not_arbitrary_constant_response(self):
        self.assertEqual(self.result("read_webpage", {"url": "https://fixture.invalid/apples"})["content"], "A" * 1200)
        self.error("read_webpage", {"url": "https://fixture.invalid/apples?different=1"}, "resource_missing")
        self.error("read_webpage", {"url": "file:///etc/passwd"}, "url_invalid")
        self.error("read_webpage", {"url": "https://name:secret@fixture.invalid/apples"}, "url_invalid")

    def test_page_truncation_is_derived_from_actual_body(self):
        result = self.result("read_webpage", {"url": "https://fixture.invalid/apples", "max_chars": 500})
        self.assertEqual(len(result["content"]), 500)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["total_chars"], 1200)

    def test_partial_page_not_fabricated_full_body(self):
        seed = resources(); seed["pages"][0]["complete"] = False; seed["pages"][0]["total_chars"] = 5000
        tools = ReplayTools(contracts(), seed, "test")
        self.assertEqual(tools.dispatch("read_webpage", {"url": "https://fixture.invalid/apples"})["error"]["code"], "resource_incomplete")

    def test_conflicting_pages_not_selected_by_invocation_order(self):
        seed = resources(); other = copy.deepcopy(seed["pages"][0]); other["body"] = "B" * 1200; seed["pages"].append(other)
        tools = ReplayTools(contracts(), seed, "test")
        self.assertEqual(tools.dispatch("read_webpage", {"url": "https://fixture.invalid/apples"})["error"]["code"], "resource_conflict")

    def test_project_wrong_id_and_private_id_both_refused(self):
        self.error("project_chat_read", {"thread_id": "wrong-id"}, "resource_missing")
        self.error("project_chat_read", {"thread_id": "synthetic-thread-private"}, "resource_missing")
        self.assertEqual(len(self.result("project_chats_list", {})["chats"]), 1)

    def test_project_query_and_last_n_recompute(self):
        a = self.result("project_chat_read", {"thread_id": "synthetic-thread-a", "last_n": 1})
        b = self.result("project_chat_read", {"thread_id": "synthetic-thread-a", "query": "apples"})
        c = self.result("project_chat_read", {"thread_id": "synthetic-thread-a", "query": "unicorn"})
        self.assertEqual(a["messages"][0]["content"], "buy bicycle")
        self.assertEqual(b["messages"][0]["content"], "plant apples")
        self.assertEqual(c["messages"], [])

    def test_partial_thread_and_unknown_catalog_refused(self):
        seed = resources(); seed["threads"][0]["complete"] = False; seed["coverage"]["threads"] = "missing"
        tools = ReplayTools(contracts(), seed, "test")
        self.assertEqual(tools.dispatch("project_chat_read", {"thread_id": "synthetic-thread-a"})["error"]["code"], "resource_incomplete")
        self.assertEqual(tools.dispatch("project_chats_list", {})["error"]["code"], "resource_missing")

    def test_personal_query_and_folder_are_not_constant(self):
        self.assertEqual(len(self.result("personal_search", {"query": "bicycle", "folder": "sports"})["results"]), 1)
        self.assertEqual(self.result("personal_search", {"query": "bicycle", "folder": "other"})["results"], [])
        self.assertEqual(self.result("personal_search", {"query": "orchard"})["results"], [])
        self.assertEqual(len(self.result("search_memory", {"query": "orchard"})["results"]), 1)

    def test_local_writes_isolate_arms_and_seed(self):
        builtin = ReplayTools(contracts(), self.seed, "builtin")
        pseudex = ReplayTools(contracts(), self.seed, "pseudex")
        self.result("save_to_memory", {"key": "newkey", "value": "zebramarker"})
        self.assertEqual(len(self.result("search_memory", {"query": "zebramarker"})["results"]), 1)
        for arm in (builtin, pseudex):
            self.assertEqual(arm.dispatch("search_memory", {"query": "zebramarker"})["result"]["results"], [])
        self.assertEqual(self.seed, resources())
        self.result("personal_save", {"text": "freshdoc", "folder": "new-folder", "title": "newtitle"})
        self.assertIn("new-folder", self.result("personal_list_folders", {})["folders"])
        self.assertNotIn("new-folder", builtin.dispatch("personal_list_folders", {})["result"]["folders"])

    def test_clone_is_deterministic_and_never_shared(self):
        clone = self.tools.clone("other")
        self.assertEqual(self.tools.state(), clone.state())
        self.assertEqual(self.tools.dispatch("google_search", {"query": "apples"}), clone.dispatch("google_search", {"query": "apples"}))
        clone.dispatch("save_to_memory", {"key": "private", "value": "onlyclone"})
        self.assertEqual(self.result("search_memory", {"query": "onlyclone"})["results"], [])

    def test_inputs_outputs_and_state_are_defensive_copies(self):
        self.seed["web_documents"][0]["text"] = "tampered"
        result = self.result("project_chat_read", {"thread_id": "synthetic-thread-a"})
        result["messages"][0]["content"] = "tampered"
        state = self.tools.state(); state["threads"][0]["messages"].clear()
        self.assertEqual(self.result("project_chat_read", {"thread_id": "synthetic-thread-a"})["messages"][0]["content"], "plant apples")
        self.assertEqual(self.result("google_search", {"query": "apples"})["results"][0]["title"], "Apples")

    def test_missing_resources_are_not_invented(self):
        seed = resources(); seed["coverage"] = {}; seed["pages"] = []
        tools = ReplayTools(contracts(), seed, "test")
        for name, args in (("search_memory", {"query": "anything"}), ("personal_search", {"query": "anything"}),
                           ("personal_list_folders", {}), ("read_webpage", {"url": "https://fixture.invalid/apples"})):
            self.assertEqual(tools.dispatch(name, args)["error"]["code"], "resource_missing")

    def test_original_outputs_never_used_as_dispatch_fallback(self):
        seed = resources(); seed["recorded_tool_results"] = {"anything": "HISTORICAL ANSWER"}
        tools = ReplayTools(contracts(), seed, "test")
        answer = tools.dispatch("google_search", {"query": "anything"})
        self.assertNotIn("HISTORICAL", str(answer))
        self.assertEqual(answer["result"]["results"], [])

    def test_code_is_not_evaluated_even_when_it_looks_harmless(self):
        with patch("builtins.eval", side_effect=AssertionError("eval forbidden")), patch("subprocess.run", side_effect=AssertionError("shell forbidden")), patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.error("run_code", {"code": "print('synthetic')"}, "executor_unavailable")
            self.error("dataset_profile", {"dataset_id": "unknown"}, "dataset_unavailable")
            self.assertEqual(len(self.result("google_search", {"query": "apples"})["results"]), 1)

    def test_unknown_names_and_missing_contract_fail(self):
        self.error("send_mail", {"to": "not-real"}, "tool_not_allowed")
        self.error([], {}, "tool_not_allowed")
        self.error("dataset_query", {}, "schema_missing")

    def test_argument_strict_types_not_pydantic_coercion(self):
        self.error("google_search", {"query": "apple", "num": True}, "arguments_type_mismatch")
        self.error("google_search", {"query": 123}, "arguments_type_mismatch")
        self.error("google_search", {"query": "apple", "num": "5"}, "arguments_type_mismatch")
        self.error("google_search", {}, "arguments_required_missing")
        self.error("internet_search", {"query": "apple", "topic": "finance"}, "arguments_enum_mismatch")

    def test_unknown_args_identity_and_arm_cannot_be_injected(self):
        for key in ("user_id", "org_id", "arm", "settings"):
            self.error("google_search", {"query": "apple", key: "synthetic"}, "arguments_unknown_property")

    def test_json_ambiguity_nonfinite_and_nonobjects_refused(self):
        self.error("google_search", '{"query":"one","query":"two"}', "duplicate_json_key")
        self.error("google_search", '{"query":NaN}', "non_json_value")
        self.error("google_search", "not json", "arguments_invalid_json")
        self.error("google_search", [], "arguments_type_mismatch")
        self.error("google_search", {1: "notstring"}, "non_json_value")

    def test_error_contains_no_raw_query_or_resource_id(self):
        marker = "PRIVATE_SYNTHETIC_MARKER"
        response = self.error("project_chat_read", {"thread_id": marker}, "resource_missing")
        self.assertNotIn(marker, str(response))
        self.assertNotIn(marker, str(self.tools.events()))

    def test_unknown_schema_feature_fails_closed(self):
        c = contracts(); c["google_search"]["parameters"]["properties"]["query"]["pattern"] = "a+"
        with self.assertRaisesRegex(ReplayError, "schema_unsupported"):
            ReplayTools(c, resources(), "test")
        c = contracts(); c["google_search"]["parameters"]["properties"]["query"] = {"$ref": "https://fixture.invalid/schema"}
        with self.assertRaisesRegex(ReplayError, "schema_reference_unsupported"):
            ReplayTools(c, resources(), "test")

    def test_schema_and_provenance_required(self):
        c = contracts(); c["google_search"].pop("schema_source")
        with self.assertRaisesRegex(ReplayError, "schema_provenance_missing"):
            ReplayTools(c, resources(), "test")
        c = contracts(); c["google_search"]["parameters"]["properties"]["num"]["default"] = "5"
        with self.assertRaisesRegex(ReplayError, "arguments_type_mismatch"):
            ReplayTools(c, resources(), "test")

    def test_resource_types_and_provenance_required(self):
        seed = resources(); seed["pages"][0]["body"] = {"not": "body"}
        with self.assertRaisesRegex(ReplayError, "resource_invalid"):
            ReplayTools(contracts(), seed, "test")
        seed = resources(); seed["pages"][0]["provenance"] = {}
        with self.assertRaisesRegex(ReplayError, "resource_provenance_missing"):
            ReplayTools(contracts(), seed, "test")

    def test_schema_ref_nullable_bounds_and_array_validation(self):
        schema = {"$defs": {"item": {"type": "integer", "minimum": 1}}, "type": "array", "items": {"$ref": "#/$defs/item"}, "uniqueItems": True, "maxItems": 3}
        check_schema(schema); validate([1, 2], schema)
        for value in ([0], [True], [1, 1], [1, 2, 3, 4]):
            with self.assertRaises(ReplayError):
                validate(value, schema)
        validate(None, {"anyOf": [{"type": "string"}, {"type": "null"}]})


class PreparationTests(unittest.TestCase):
    def test_only_observed_redirect_creates_exact_url_aliases(self):
        case = {"source_context": {"application_activity": {"source_tool_execution_spans": [
            {"name": "read_webpage", "arguments": {"url": "https://fixture.invalid/old"}, "result": {
                "success": True, "url": "https://fixture.invalid/new", "title": "Moved", "content": "real body",
                "truncated": False, "total_chars": 9}}]}}}
        extracted = build_resources(case, 0)
        tools = ReplayTools(contracts(), extracted, "test")
        for url in ('https://fixture.invalid/old', 'https://fixture.invalid/new'):
            result = tools.dispatch('read_webpage', {"url": url})
            self.assertTrue(result['ok'])
            self.assertEqual(result['result']['url'], 'https://fixture.invalid/new')
            self.assertEqual(result['result']['content'], 'real body')
        self.assertFalse(tools.dispatch('read_webpage', {"url": 'https://fixture.invalid/old?unobserved=1'})['ok'])

    def test_full_thread_parser_proves_count_and_never_seeds_current_root(self):
        text = ('Чат «Synthetic» (автор: Tester), последние 2 сообщений из 2:\n'
                '[пользователь · test] apple\n[ассистент · test] bicycle\nСсылка на чат: /synthetic')
        row = captured_transcript(text, {"thread_id": "synthetic-other"}, {"kind": "test"}, "synthetic-current")
        self.assertTrue(row["complete"])
        self.assertEqual(row["messages"][0]["content"], "apple")
        self.assertFalse(captured_transcript(text, {"thread_id": "synthetic-current"}, {"kind": "test"}, "synthetic-current")["complete"])
        self.assertFalse(captured_transcript(text.replace('из 2:', 'из 20:'), {"thread_id": "synthetic-other"}, {"kind": "test"}, "synthetic-current")["complete"])
        self.assertIsNone(captured_transcript('unknown renderer', {"thread_id": "synthetic-other"}, {"kind": "test"}, "synthetic-current"))

    def test_catalog_is_seeded_even_when_a_transcript_precedes_it(self):
        text = ('Чат «Synthetic» (автор: Tester), последние 1 сообщений из 1:\n'
                '[пользователь · test] apple\nСсылка на чат: /synthetic')
        catalog = ('Чаты проекта, доступные пользователю (2, offset=0):\n'
                   '- thread_id=synthetic-other | «Synthetic» | мой\n'
                   '- thread_id=synthetic-two | «Two» | мой\n')
        case = {"thread": {"thread_id": "synthetic-current"}, "source_context": {"application_activity": {"source_tool_execution_spans": [
            {"name": "project_chat_read", "arguments": {"thread_id": "synthetic-other"}, "result": text},
            {"name": "project_chats_list", "arguments": {}, "result": catalog}]}}}
        extracted = build_resources(case, 0)
        self.assertEqual(len(extracted["threads"]), 2)
        self.assertEqual(extracted["coverage"]["threads"], "complete")
        self.assertEqual(sum(t["complete"] for t in extracted["threads"]), 1)
        tools = ReplayTools(contracts(), extracted, "test")
        self.assertTrue(tools.dispatch("project_chats_list", {})["ok"])
        self.assertEqual(len(tools.dispatch("project_chats_list", {})["result"]["chats"]), 2)

    def test_memory_document_boundaries_create_query_dependent_index(self):
        text = 'Найдено в памяти:\n- orchard: apples\nsecond line\n- bike: wheels'
        docs = captured_memory_documents(text, "memory", {"kind": "test"})
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]["value"], 'apples\nsecond line')
        seed = resources(); seed["memories"] = docs
        tools = ReplayTools(contracts(), seed, "test")
        self.assertEqual(tools.dispatch("search_memory", {"query": "wheels"})["result"]["results"][0]["key"], "bike")
        self.assertEqual(tools.dispatch("search_memory", {"query": "unicorn"})["result"]["results"], [])

    def test_catalog_unknown_renderer_is_missing_not_empty_success(self):
        self.assertEqual(captured_catalog('unknown renderer', {}, {"kind": "test"}), ([], False))
        case = {"source_context": {"application_activity": {"source_tool_execution_spans": [
            {"name": "project_chats_list", "arguments": {}, "result": 'unknown renderer'}]}}}
        extracted = build_resources(case, 0)
        tools = ReplayTools(contracts(), extracted, "test")
        self.assertEqual(tools.dispatch("project_chats_list", {})["error"]["code"], "resource_missing")

    def test_attachment_locators_distinguish_original_input_and_generated_history(self):
        case = {"user_turns": [{"attachments": [{"filename": "synthetic-input.xlsx", "file_id": "synthetic-input"}]}],
                "checkpoint_proof": {"generated_documents": [{"filename": "synthetic-output.xlsx", "doc_id": "synthetic-output"}]}}
        refs = attachment_locators(case, 0)
        self.assertEqual([r["role"] for r in refs], ['original_user_attachment', 'historical_generated_output_do_not_seed'])
        self.assertFalse(any(r["bytes_exported"] for r in refs))
        self.assertTrue(all(r["ref"]["artifact"] == 'full-dialogues.aesgcm' for r in refs))

    def test_signature_not_inferred_from_observed_args(self):
        signature = {"fields": [{"name": "query", "annotation": "str", "required": True},
                                {"name": "top_k", "annotation": "int", "required": False, "default": 5}]}
        schema = declared_schema(signature)
        self.assertEqual(schema["required"], ["query"])
        self.assertEqual(schema["properties"]["top_k"]["type"], "integer")
        signature["fields"][0]["annotation"] = "SomeUnknownType"
        with self.assertRaises(Exception):
            declared_schema(signature)

    def test_ejson_normalizes_only_derived_contract(self):
        raw = {"default": {"$numberInt": "5"}}
        self.assertEqual(normalize_ejson(raw), {"default": 5})
        self.assertEqual(raw, {"default": {"$numberInt": "5"}})

    def test_credentials_dropped_even_in_allowed_description_field(self):
        value = {"description": "mongodb://synthetic.invalid/not-real", "schema": {"type": "object"}}
        sanitized = safe_projection(value)
        self.assertEqual(sanitized["description"], {"excluded": "credential_bearing_text"})
        self.assertEqual(sanitized["schema"], value["schema"])

    def test_spans_not_new_calls_and_conflicting_id_refused(self):
        case = {"source_context": {"tool_evidence": {"calls": [
            {"call_id": "synthetic-call", "name": "google_search", "arguments": {"query": "apple"}},
            {"call_id": "synthetic-call", "name": "google_search", "arguments": {"query": "apple"}}]},
            "application_activity": {"source_tool_execution_spans": [{"name": "google_search"}]}}}
        self.assertEqual(len(unique_calls(case)), 1)
        case["source_context"]["tool_evidence"]["calls"][1]["arguments"] = {"query": "bicycle"}
        with self.assertRaises(Exception):
            unique_calls(case)

    def test_resource_extraction_uses_body_and_search_documents_not_call_replies(self):
        spans = [
            {"name": "google_search", "arguments": {"query": "original"}, "result": {"success": True, "results": [
                {"title": "New searchable fact", "link": "https://fixture.invalid/doc", "snippet": "orchard bicycles"}]}},
            {"name": "read_webpage", "arguments": {"url": "https://fixture.invalid/body"}, "result": {
                "success": True, "url": "https://fixture.invalid/body", "content": "body", "title": "Body", "truncated": False, "total_chars": 4}},
            {"name": "dataset_profile", "arguments": {"dataset_id": "synthetic"}, "result": "sample values are NOT data"}]
        extracted = build_resources({"source_context": {"application_activity": {"source_tool_execution_spans": spans}}}, 0)
        tools = ReplayTools(contracts(), extracted, "test")
        self.assertEqual(tools.dispatch("google_search", {"query": "bicycles"})["result"]["results"][0]["title"], "New searchable fact")
        self.assertEqual(tools.dispatch("google_search", {"query": "original"})["result"]["results"], [])
        self.assertEqual(tools.dispatch("dataset_profile", {"dataset_id": "synthetic"})["error"]["code"], "dataset_unavailable")
        self.assertEqual(extracted["datasets"], [])
        self.assertTrue(extracted["missing"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
