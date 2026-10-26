"""Synthetic-only unittest/mock coverage; never uses credentials/network/clientdata.

Run from prototype: python3 -m unittest bench.doubleup.test_intake -v
"""

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import stat
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from . import __main__ as cli
from . import corpus, langfuse, storage
from .storage import PilotError

NOW = dt.datetime.now(dt.timezone.utc)
STAMP = langfuse.iso(NOW - dt.timedelta(days=2))
ORIGINAL = "SYNTHETIC original content, punctuation: é / <>&; do not redact sk-synthetic-fake"


def trace(tid="t1", sid="s1", metadata=None):
    return {"id": tid, "timestamp": STAMP, "sessionId": sid, "userId": "synthetic-user",
            "name": "synthetic-agent", "metadata": metadata if metadata is not None else {"org_id": "synthetic-org"}}


def message(role, content):
    return {"role": role, "content": content}


def response(value, url):
    mock = Mock()
    mock.geturl.return_value = url
    mock.read.return_value = json.dumps(value).encode()
    mock.__enter__ = Mock(return_value=mock)
    mock.__exit__ = Mock(return_value=None)
    return mock


class StateTest(unittest.TestCase):
    def setUp(self):
        parent = storage.PACKAGE / ".test-state"
        parent.mkdir(mode=0o700, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.state_patch = patch.object(storage, "STATE", self.root / "private")
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        # TemporaryDirectory is exclusively created under this package; it never
        # removes a caller-supplied target or traverses a symlink.
        self.assertTrue(self.root.resolve().is_relative_to(storage.PACKAGE))
        self.temp.cleanup()


class CredentialsTests(StateTest):
    def config_file(self, text, mode=0o600):
        path = self.root / "auth.env"
        path.write_text(text)
        path.chmod(mode)
        return path

    def test_private_names_aliases_and_quoted_values(self):
        path = self.config_file("export host='https://langfuse.inf.2up.dev'\npk='p-synthetic'\nsk=secret-synthetic # note\n")
        self.assertEqual(langfuse.credentials(path), (langfuse.HOST, "p-synthetic", "secret-synthetic"))

    def test_host_and_permissions_refused(self):
        path = self.config_file("LANGFUSE_HOST=https://evil.invalid\npk=p\nsk=s\n")
        with self.assertRaisesRegex(PilotError, "host_not_allowlisted"):
            langfuse.credentials(path)
        path.chmod(0o644)
        with self.assertRaisesRegex(PilotError, "not_private"):
            langfuse.credentials(path)

    def test_ambiguous_keys_and_shell_not_executed(self):
        path = self.config_file("pk=p\nLANGFUSE_PUBLIC_KEY=other\nsk=s\n")
        with self.assertRaisesRegex(PilotError, "ambiguous"):
            langfuse.credentials(path)
        path.write_text("pk=p\nsk=s\n$(arbitrary shell text)\n")
        with self.assertRaisesRegex(PilotError, "syntax"):
            langfuse.credentials(path)


class HTTPTests(unittest.TestCase):
    def client(self):
        return langfuse.Client((langfuse.HOST, "synthetic-public", "synthetic-secret"), attempts=2)

    def test_get_only_actual_host_and_no_redirects(self):
        client = self.client()
        url = langfuse.HOST + "/api/public/projects"
        client.opener = Mock()
        client.opener.open.return_value = response({"data": []}, url)
        self.assertEqual(client.get("/api/public/projects"), {"data": []})
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, url)
        with self.assertRaisesRegex(PilotError, "endpoint_not_allowlisted"):
            client.get("https://evil.invalid")
        with self.assertRaisesRegex(PilotError, "host_not_allowlisted"):
            langfuse.Client((langfuse.HOST + ".evil.invalid", "p", "s"))
        with self.assertRaisesRegex(PilotError, "redirect_refused"):
            langfuse.NoRedirect().redirect_request(None, None, 302, None, None, "https://evil.invalid")

    def test_bounded_retries_never_print_raw_error(self):
        client = self.client()
        error = urllib.error.HTTPError(langfuse.HOST, 503, ORIGINAL, {}, io.BytesIO(ORIGINAL.encode()))
        client.opener = Mock()
        client.opener.open.side_effect = error
        with patch.object(langfuse.time, "sleep") as delay:
            with self.assertRaisesRegex(PilotError, "http_retries_exhausted_503") as captured:
                client.get("/api/public/projects")
        self.assertNotIn(ORIGINAL, str(captured.exception))
        self.assertEqual(client.opener.open.call_count, 2)
        self.assertEqual(delay.call_count, 1)
        self.assertEqual(client.retries, 1)

    def test_auth_not_retried(self):
        client = self.client()
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError(langfuse.HOST, 401, ORIGINAL, {}, None)
        with self.assertRaisesRegex(PilotError, "http_status_401"):
            client.get("/api/public/projects")
        self.assertEqual(client.opener.open.call_count, 1)

    def test_pagination_total_two_pages(self):
        client = self.client()
        client.get = Mock(side_effect=[{"data": [{"id": "a"}], "meta": {"totalItems": 2}},
                                       {"data": [{"id": "b"}], "meta": {"totalItems": 2}}])
        rows, proof = client.paginated("/api/public/traces", {})
        self.assertEqual([r["id"] for r in rows], ["a", "b"])
        self.assertTrue(proof["complete"])
        self.assertEqual(proof["pages"], 2)

    def test_missing_truncated_duplicate_drifting_totals_refused(self):
        scenarios = [
            ([{"data": [], "meta": {}}], "total_missing"),
            ([{"data": [], "meta": {"totalItems": 2}}], "incomplete"),
            ([{"data": [{"id": "a"}], "meta": {"totalItems": 2}},
              {"data": [{"id": "a"}], "meta": {"totalItems": 2}}], "duplicate"),
            ([{"data": [{"id": "a"}], "meta": {"totalItems": 2}},
              {"data": [{"id": "b"}], "meta": {"totalItems": 3}}], "changed"),
        ]
        for pages, code in scenarios:
            with self.subTest(code=code):
                client = self.client()
                client.get = Mock(side_effect=pages)
                with self.assertRaisesRegex(PilotError, code):
                    client.paginated("/api/public/traces", {}, 2)

    def test_pagination_cap_not_claimed_complete(self):
        client = self.client()
        client.get = Mock(return_value={"data": [{"id": "a"}], "meta": {"totalItems": 2}})
        with self.assertRaisesRegex(PilotError, "cap_incomplete"):
            client.paginated("/api/public/traces", {}, 1)

    def test_cursor_variants_and_cycle(self):
        for field in ("cursor", "nextCursor"):
            client = self.client()
            client.get = Mock(side_effect=[{"data": [{"id": "a"}], "meta": {field: "next"}},
                                           {"data": [{"id": "b"}], "meta": {field: None}}])
            rows, proof = client.paginated("/api/public/v2/observations", {})
            self.assertEqual(len(rows), 2)
            self.assertEqual(proof["mode"], "cursor")
            self.assertEqual(client.get.call_args_list[1].args[1]["cursor"], "next")
        client = self.client()
        client.get = Mock(side_effect=[{"data": [{"id": "a"}], "meta": {"cursor": "same"}},
                                       {"data": [{"id": "b"}], "meta": {"cursor": "same"}}])
        with self.assertRaisesRegex(PilotError, "cursor_cycle"):
            client.paginated("/api/public/v2/observations", {})

    def test_response_size_and_schema_no_raw_output(self):
        client = self.client()
        client.opener = Mock()
        client.opener.open.return_value = response([], langfuse.HOST + "/api/public/projects")
        with self.assertRaisesRegex(PilotError, "schema_invalid"):
            client.get("/api/public/projects")
        with patch.object(langfuse, "MAX_RESPONSE", 1):
            with self.assertRaisesRegex(PilotError, "size_cap"):
                client.get("/api/public/projects")


class AttributionTests(unittest.TestCase):
    def test_backend_user_is_not_tenant(self):
        result = langfuse.attribution(trace())
        self.assertEqual(result["tenant_id"], "synthetic-org")
        self.assertEqual(result["user_id_not_tenant"], "synthetic-user")
        self.assertEqual(langfuse.attribution(trace(metadata={})) ["tenant_status"], "unknown")

    def test_nested_litellm_json_billing_and_conflict(self):
        metadata = {"attributes": {"metadata": json.dumps({"spend_logs_metadata": {
            "billing_tenant_id": "synthetic-org", "billing_assistant_id": "a", "billing_dialog_id": "d"}})}}
        result = langfuse.attribution(trace(metadata=metadata))
        self.assertEqual(result["tenant_id"], "synthetic-org")
        self.assertIn("a", result["agent_evidence"])
        metadata["org_id"] = "conflicting-org"
        result = langfuse.attribution(trace(metadata=metadata))
        self.assertIsNone(result["tenant_id"])
        self.assertEqual(result["tenant_status"], "ambiguous")

    def test_observation_metadata_attribution_not_input_text(self):
        item = trace(metadata={})
        item["observations"] = [{"id": "o", "metadata": {"org_id": "actual-org"},
                                 "input": {"org_id": "untrusted-prompt-org"}}]
        result = langfuse.attribution(item)
        self.assertEqual(result["tenant_id"], "actual-org")
        self.assertNotIn("untrusted-prompt-org", result["tenant_evidence"])

    def test_group_conflicts_and_window_validation(self):
        group = corpus.normalize_group("session:s1", [trace(), trace("t2", metadata={"org_id": "different"})])
        self.assertEqual(group["tenant_status"], "ambiguous")
        langfuse.validate_window([trace()], NOW - dt.timedelta(days=30), NOW)
        with self.assertRaisesRegex(PilotError, "date_filter_ignored"):
            langfuse.validate_window([trace()], NOW - dt.timedelta(days=1), NOW)
        with self.assertRaisesRegex(PilotError, "timezone_missing"):
            langfuse.utc("2026-01-01T00:00:00")

    def test_no_session_explicit_dialog_group_or_flagged_trace(self):
        a, b = trace("a", None, {"org_id": "x", "billing_dialog_id": "d"}), trace("b", None, {"org_id": "x", "billing_dialog_id": "d"})
        self.assertEqual(langfuse.trace_group(a), langfuse.trace_group(b))
        self.assertTrue(langfuse.trace_group(trace(sid=None, metadata={})).startswith("unscoped-trace:"))


class CorpusTests(unittest.TestCase):
    def test_prefix_growth_and_identical_repeated_turns(self):
        one = [message("user", ORIGINAL)]
        two = one + [message("assistant", "synthetic reply"), message("user", ORIGINAL)]
        result = corpus.snapshots([("first", {"messages": one}), ("second", {"messages": two}),
                                   ("duplicate", json.dumps({"messages": two}))])
        self.assertEqual(len(result["maximal"]), 1)
        self.assertEqual(len(result["superseded"]), 1)
        self.assertEqual(result["unique_message_occurrences"], 3)
        self.assertEqual(result["snapshot_occurrences"], 3)
        self.assertEqual(result["maximal"][0]["messages"][0]["content"], ORIGINAL)

    def test_branches_preserved_not_spliced(self):
        root = [message("user", "synthetic request")]
        result = corpus.snapshots([("a", root + [message("assistant", "branch a")]),
                                   ("b", root + [message("assistant", "branch b")])])
        self.assertEqual(len(result["maximal"]), 2)
        self.assertEqual(result["unique_message_occurrences"], 3)

    def test_exact_schema_args_results_and_provenance(self):
        schema = {"type": "function", "function": {"name": "synthetic_tool", "parameters": {
            "type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}}}
        call = {"id": "call1", "type": "function", "function": {"name": "synthetic_tool", "arguments": json.dumps({"text": ORIGINAL})}}
        payload = {"tools": [schema], "messages": [{"role": "assistant", "tool_calls": [call]},
                   {"role": "tool", "tool_call_id": "call1", "content": ORIGINAL}]}
        result = corpus.tools([("trace:a", payload), ("trace:b", payload)])
        self.assertEqual(result["schemas"][0]["schema"], schema)
        self.assertEqual(len(result["calls"]), 1)
        self.assertEqual(result["calls"][0]["link_status"], "linked")
        self.assertEqual(result["calls"][0]["schema_status"], "present")
        self.assertEqual(len(result["calls"][0]["provenance"]), 2)
        self.assertEqual(json.loads(result["calls"][0]["arguments"])["text"], ORIGINAL)
        self.assertEqual(result["results"][0]["result"], ORIGINAL)

    def test_missing_schema_and_results_never_fabricated(self):
        result = corpus.tools([("x", {"tool_calls": [{"function": {"name": "synthetic", "arguments": "{}"}}]})])
        call = result["calls"][0]
        self.assertEqual(call["schema_status"], "missing")
        self.assertEqual(call["link_status"], "missing_call_id")
        self.assertEqual(result["schemas"], [])
        self.assertEqual(result["results"], [])

    def test_conflicting_call_ids_ambiguous_and_orphan_results(self):
        payload = {"tool_calls": [{"id": "dup", "function": {"name": "t", "arguments": "1"}},
                                  {"id": "dup", "function": {"name": "t", "arguments": "2"}}],
                   "messages": [{"role": "tool", "tool_call_id": "unknown", "content": "synthetic"}]}
        result = corpus.tools([("x", payload)])
        self.assertTrue(all(call["link_status"] == "ambiguous_call_id" for call in result["calls"]))
        self.assertEqual(result["orphan_results"], 1)

    def test_anthropic_and_v3_tool_observation(self):
        payload = [{"type": "tool_use", "id": "c", "name": "t", "input": {"x": ORIGINAL}},
                   {"type": "tool_result", "tool_use_id": "c", "content": ORIGINAL},
                   {"id": "obs", "type": "TOOL", "name": "unlinked", "input": ORIGINAL}]
        result = corpus.tools([("x", payload)])
        self.assertEqual(result["calls"][0]["link_status"], "linked")
        self.assertEqual(len(result["unlinked_tool_observations"]), 1)

    def test_selection_cap_strata_and_whole_dialog_split(self):
        traces = [trace(str(index), "s" + str(index // 2), {"org_id": "org" + str(index % 3), "agent_id": "a" + str(index % 4)})
                  for index in range(500)]
        grouped, chosen, report = corpus.select_groups(traces, 200, "seed")
        self.assertEqual(len(chosen), 200)
        self.assertEqual(len(grouped), 250)
        self.assertIn("tool:unknown", report["available_strata"])
        assignment, counts = corpus.split_groups(chosen, "seed")
        self.assertEqual(counts, {"train": 160, "holdout": 40})
        self.assertEqual(assignment, corpus.split_groups(list(reversed(chosen)), "seed")[0])
        with self.assertRaisesRegex(PilotError, "1_to_200"):
            corpus.select_groups(traces, 201, "seed")

    def test_actual_multilabel_split_balances_common_strata(self):
        keys = [str(i) for i in range(100)]
        features = {key: {"tenant:" + str(int(key) % 2), "tool:" + str(int(key) % 5)} for key in keys}
        assignment, counts = corpus.split_groups(keys, "seed", features)
        self.assertEqual(counts, {"train": 80, "holdout": 20})
        held = [key for key in keys if assignment[key] == "holdout"]
        self.assertEqual(sum("tenant:0" in features[k] for k in held), 10)
        for tool in range(5):
            self.assertEqual(sum("tool:" + str(tool) in features[k] for k in held), 4)


class StorageTests(StateTest):
    def test_aesgcm_original_and_persistent_private_key(self):
        run = storage.RunStore("test-run", True)
        run.encrypt("source.aesgcm", {"input": ORIGINAL, "secret": "synthetic-token"})
        manifest = run.finish({"kind": "test", "counts": {"one": 1}})
        self.assertNotIn(ORIGINAL.encode(), (run.path / "source.aesgcm").read_bytes())
        self.assertNotIn(ORIGINAL, (run.path / "manifest.json").read_text())
        reopened = storage.RunStore("test-run", False)
        self.assertEqual(reopened.verify(), manifest)
        self.assertEqual(reopened.read_encrypted("source.aesgcm")["input"], ORIGINAL)
        self.assertEqual(stat.S_IMODE((storage.STATE / "corpus.key").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(run.path.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((run.path / "source.aesgcm").stat().st_mode), 0o400)
        self.assertEqual(run.key, reopened.key)

    def test_immutable_and_outside_state_writes_refused(self):
        run = storage.RunStore("test-run", True)
        run.encrypt("source.aesgcm", {"x": 1})
        with self.assertRaisesRegex(PilotError, "immutable"):
            run.encrypt("source.aesgcm", {"x": 2})
        with self.assertRaisesRegex(PilotError, "immutable_run"):
            storage.RunStore("test-run", True)
        with self.assertRaisesRegex(PilotError, "outside_pilot"):
            storage.immutable_write(self.root / "outside", b"no")

    def test_symlink_and_weak_directory_refused(self):
        storage.private_dir(storage.STATE)
        link = storage.STATE / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(PilotError, "symlink"):
            storage.immutable_write(link / "no", b"no")
        storage.STATE.chmod(0o755)
        with self.assertRaisesRegex(PilotError, "directory_not_private"):
            storage.load_key(True)
        storage.STATE.chmod(0o700)

    def test_artifact_tamper_and_wrong_context_detected(self):
        run = storage.RunStore("test-run", True)
        run.encrypt("source.aesgcm", {"x": ORIGINAL})
        run.finish({"kind": "test"})
        path = run.path / "source.aesgcm"
        path.chmod(0o600)
        data = path.read_bytes()
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        path.chmod(0o400)
        with self.assertRaisesRegex(PilotError, "hash_mismatch"):
            run.verify()
        with self.assertRaisesRegex(PilotError, "authentication_failed"):
            storage.unseal(run.key, data, "wrong-context")

    def test_manifest_cannot_be_replaced_with_rehashed_forgery(self):
        run = storage.RunStore("test-run", True)
        run.finish({"kind": "test"})
        forged = storage.canonical({"kind": "forged"})
        for name, value in [("manifest.json", forged), ("manifest.sha256", storage.digest(forged).encode())]:
            path = run.path / name
            path.chmod(0o600)
            path.write_bytes(value)
            path.chmod(0o400)
        with self.assertRaisesRegex(PilotError, "authentication_mismatch"):
            run.verify()


class PipelineTests(StateTest):
    def fixture_client(self):
        client = langfuse.Client((langfuse.HOST, "p", "s"))
        traces = [trace("t" + str(index), "s" + str(index)) for index in range(5)]

        def get(path, params=None, record=True):
            client.requests += 1
            if path == "/api/public/projects":
                return {"data": [{"id": "synthetic-project", "name": "synthetic"}]}
            if path == "/api/public/traces":
                rows = traces if "sessionId" not in params else [t for t in traces if t["sessionId"] == params["sessionId"]]
                return {"data": rows, "meta": {"totalItems": len(rows)}}
            if path == "/api/public/observations":
                return {"data": [{"id": "obs-" + params["traceId"], "traceId": params["traceId"],
                                   "type": "GENERATION", "input": {"messages": [message("user", ORIGINAL)]},
                                   "output": {"role": "assistant", "content": "recorded synthetic reply"}}],
                        "meta": {"totalItems": 1}}
            if path.startswith("/api/public/traces/"):
                return dict(next(t for t in traces if t["id"] == path.rsplit("/", 1)[1]))
            raise AssertionError("unexpected endpoint")
        client.get = Mock(side_effect=get)
        return client

    def test_inventory_export_and_recorded_actual_cli(self):
        client = self.fixture_client()
        output = io.StringIO()
        with patch.object(cli, "Client", return_value=client), patch.object(cli, "credentials", return_value=(langfuse.HOST, "p", "s")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.main(["inventory", "--run-id", "fixture-inventory"]), 0)
                self.assertEqual(cli.main(["export", "--inventory", "fixture-inventory", "--run-id", "fixture-export"]), 0)
                self.assertEqual(cli.main(["/recorded", "--source", "fixture-export", "--run-id", "fixture-recorded"]), 0)
                self.assertEqual(cli.main(["verify", "--source", "fixture-export"]), 0)
        self.assertNotIn(ORIGINAL, output.getvalue())
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(lines[1]["split_counts"], {"train": 4, "holdout": 1})
        self.assertEqual(lines[2]["counts"]["traces"], 5)
        self.assertFalse(lines[2]["validation"]["is_causal_replay"])
        export = storage.RunStore("fixture-export", False)
        self.assertTrue(export.verify()["source_completeness"]["selected_visible_sessions_complete"])
        self.assertIn(ORIGINAL, str(export.read_encrypted("corpus.aesgcm")))

    def test_cli_unknown_errors_never_emit_body_or_traceback(self):
        error = io.StringIO()
        with patch.object(cli, "credentials", side_effect=RuntimeError(ORIGINAL)), contextlib.redirect_stderr(error):
            self.assertEqual(cli.main(["probe"]), 2)
        self.assertNotIn(ORIGINAL, error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())

    def test_oversized_export_rejected_before_credentials_or_network(self):
        with patch.object(cli, "credentials") as config, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["export", "--inventory", "none", "--limit", "201"]), 2)
            config.assert_not_called()

    def test_observation_v3_fallback(self):
        client = langfuse.Client((langfuse.HOST, "p", "s"))
        client.paginated = Mock(side_effect=[PilotError("http_status_404"),
            ([{"id": "o", "traceId": "t"}], {"complete": True})])
        rows, proof = cli.observations(client, "t", 100)
        self.assertEqual(rows[0]["id"], "o")
        self.assertEqual(client.paginated.call_args.args[0], "/api/public/v2/observations")
        self.assertTrue(proof["complete"])


if __name__ == "__main__":
    unittest.main()
