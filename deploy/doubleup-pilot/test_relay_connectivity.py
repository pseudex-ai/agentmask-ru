"""Zero-network proof that the live relay classifies, records and never repeats.

Every test here runs against ``httpx.MockTransport``: no socket is opened, no
credential is used and no model call is made. What the file pins, in the order
the failures actually happened:

1. a TLS/connect stall is typed, durable and never re-delivered, and the
   reservation it created stays held (never refunded);
2. the diagnostic survives a dead or hostile directory, because a diagnostic
   that raises would replace the classified 502 with an unhandled 500;
3. the route is a literal, redirects are not followed, and neither the caller's
   Authorization nor any cookie reaches the upstream;
4. the deadlines say what they mean: a bounded connect/TLS phase and a 300 s read
   deadline that stays below the caller's wait.
"""

import ast
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

import httpx
from fastapi import HTTPException
import gateway

# Captured BEFORE any patch: gateway.httpx is the real module object, so patching
# AsyncClient on it would otherwise make this builder call itself.
_REAL_ASYNC_CLIENT = httpx.AsyncClient

PRIVATE_SENTINEL = "SYNTHETIC_PRIVATE_TEXT_MUST_NOT_LEAK"
UPSTREAM_KEY = "sk-synthetic-upstream-key-0123456789abcdef"

CONFIG = {"model": "deepseek-v4-flash", "request_key": "r" * 32, "upstream_key": UPSTREAM_KEY}
BODY = {"model": "deepseek-v4-flash", "messages": [{"role": "user", "content": "Synthetic fixture"}]}


def _client_builder(handler, seen):
    """Replace AsyncClient with an in-memory transport, keeping every kwarg."""
    def build(**kwargs):
        seen["kwargs"].update(kwargs)
        kwargs.pop("transport", None)

        def record(request):
            seen["requests"].append(request)
            return handler(request)

        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(record), **kwargs)
    return build


def _request():
    return SimpleNamespace(headers={"authorization": "Bearer " + CONFIG["request_key"],
                                    "cookie": "session=synthetic",
                                    "x-request-id": "synthetic-request-id"})


async def _relay(handler, *, ledger=None, directory=None):
    ledger = Mock() if ledger is None else ledger
    ledger.reserve.return_value = "synthetic-budget-id"
    ledger.settle.return_value = None
    ledger.unknown.return_value = None
    seen = {"requests": [], "kwargs": {}}
    patches = [
        patch.object(gateway, "_live_config", return_value=dict(CONFIG)),
        patch.object(gateway, "load_pricing", return_value={}),
        patch.object(gateway, "quote", return_value={"reserved_nano": 1}),
        patch.object(gateway, "Ledger", return_value=ledger),
        patch.object(gateway.httpx, "AsyncClient", _client_builder(handler, seen)),
        patch.dict(os.environ, {"PILOT_GATEWAY_MODE": "live"}),
    ]
    if directory is not None:
        patches.append(patch.object(gateway, "DIAGNOSTIC_DIRECTORY", directory))
    for item in patches:
        item.start()
    try:
        with patch("builtins.print") as printed:
            try:
                result = await gateway._live(_request(), dict(BODY))
            except HTTPException as error:
                result = error
    finally:
        for item in reversed(patches):
            item.stop()
    return result, ledger, seen, printed


async def _check(handler, *, mode="live"):
    seen = {"requests": [], "kwargs": {}}
    with patch.object(gateway, "_live_config", return_value=dict(CONFIG)), \
         patch.object(gateway.httpx, "AsyncClient", _client_builder(handler, seen)), \
         patch.dict(os.environ, {"PILOT_GATEWAY_MODE": mode}):
        return await gateway.upstream_check(_request()), seen


class RelayFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_stall_is_typed_durable_and_never_redelivered(self):
        def dead(_request):
            raise httpx.ConnectTimeout(PRIVATE_SENTINEL)

        with tempfile.TemporaryDirectory() as directory:
            result, ledger, seen, printed = await _relay(dead, directory=Path(directory))
            self.assertEqual(result.status_code, 502)
            self.assertEqual(result.headers["X-Pilot-Transport-Error"], "ConnectTimeout")
            self.assertEqual(result.headers["X-Pilot-Reservation"], "delivery_unknown")
            self.assertEqual(result.headers["Cache-Control"], "no-store")
            self.assertEqual(result.detail, "live_delivery_unknown_reservation_retained")
            # Two handshakes, zero re-delivery: a stalled TLS handshake never
            # put the HTTP request on the wire, so the second connection is not
            # a repeat of a paid call. The reservation is still single/unknown.
            self.assertEqual(len(seen["requests"]), 2)
            ledger.reserve.assert_called_once()
            ledger.unknown.assert_called_once_with("synthetic-budget-id")
            ledger.settle.assert_not_called()

            written = list(Path(directory).glob("transport-*.json"))
            self.assertEqual(len(written), 1)
            self.assertEqual(stat.S_IMODE(written[0].stat().st_mode), 0o600)
            record = json.loads(written[0].read_text())
            self.assertEqual(record["error_type"], "ConnectTimeout")
            self.assertEqual(record["budget_id"], "synthetic-budget-id")
            self.assertEqual(record["reservation"], "delivery_unknown")
            self.assertEqual(record["event"], "pilot_upstream_transport_error")
            self.assertIsInstance(record["elapsed_seconds"], float)

            # Exactly these fields: no message, headers, URL params or key.
            self.assertEqual(set(record), {"event", "error_type", "elapsed_seconds",
                                           "budget_id", "reservation"})
            for leaked in (PRIVATE_SENTINEL, UPSTREAM_KEY):
                self.assertNotIn(leaked, written[0].read_text())
            self.assertNotIn(PRIVATE_SENTINEL, str(printed.call_args))
            self.assertNotIn(PRIVATE_SENTINEL, str(result.detail) + str(result.headers))
            self.assertNotIn(UPSTREAM_KEY, str(result.headers))

    async def test_failed_ledger_transition_still_holds_the_reservation(self):
        from budget import BudgetRefused
        ledger = Mock()
        ledger.reserve.return_value = "synthetic-budget-id"
        ledger.unknown.side_effect = BudgetRefused("ledger_transition_invalid")

        def dead(_request):
            raise httpx.ReadTimeout(PRIVATE_SENTINEL)

        with tempfile.TemporaryDirectory() as directory:
            result, ledger, seen, _printed = await _relay(dead, ledger=ledger,
                                                          directory=Path(directory))
            self.assertEqual(result.status_code, 502)
            self.assertEqual(result.headers["X-Pilot-Transport-Error"], "ReadTimeout")
            # The row stays 'reserved', which is still accounted for: never a refund.
            self.assertEqual(result.headers["X-Pilot-Reservation"], "reservation_unchanged")
            record = json.loads(next(Path(directory).glob("transport-*.json")).read_text())
            self.assertEqual(record["reservation"], "reservation_unchanged")
            ledger.settle.assert_not_called()
            self.assertEqual(len(seen["requests"]), 1)

    async def test_unwritable_diagnostic_cannot_mask_the_classified_502(self):
        def dead(_request):
            raise httpx.ConnectError(PRIVATE_SENTINEL)

        with tempfile.TemporaryDirectory() as directory:
            blocking = Path(directory) / "not-a-directory"
            blocking.write_text("x")
            result, ledger, _seen, printed = await _relay(
                dead, directory=blocking / "transport")
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.headers["X-Pilot-Transport-Error"], "ConnectError")
        ledger.unknown.assert_called_once()
        self.assertNotIn(PRIVATE_SENTINEL, str(printed.call_args))

    async def test_upstream_answer_is_not_a_transport_failure(self):
        def answer(_request):
            return httpx.Response(200, json={"choices": [],
                                             "usage": {"prompt_tokens": 2, "completion_tokens": 1}})

        result, ledger, seen, _printed = await _relay(answer)
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("X-Pilot-Transport-Error", result.headers)
        ledger.settle.assert_called_once()
        ledger.unknown.assert_not_called()
        self.assertEqual(len(seen["requests"]), 1)


class RouteAndCredentialTests(unittest.IsolatedAsyncioTestCase):
    async def test_route_is_literal_and_caller_credentials_are_not_forwarded(self):
        def answer(_request):
            return httpx.Response(200, json={"choices": [],
                                             "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

        _result, _ledger, seen, _printed = await _relay(answer)
        request = seen["requests"][0]
        self.assertEqual(str(request.url), "https://litellm.inf.2up.dev/v1/chat/completions")
        self.assertEqual(request.headers["x-litellm-api-key"], UPSTREAM_KEY)
        self.assertNotIn("authorization", request.headers)
        self.assertNotIn("cookie", request.headers)
        # The allowlisted tracing header is carried; anything else is not.
        self.assertEqual(request.headers["x-request-id"], "synthetic-request-id")
        self.assertFalse(seen["kwargs"]["follow_redirects"])
        self.assertFalse(seen["kwargs"]["trust_env"])
        self.assertTrue(json.loads(request.content)["no-log"])

    async def test_redirect_is_never_followed(self):
        def redirect(_request):
            return httpx.Response(307, headers={"location": "https://attacker.invalid/collect"})

        result, ledger, seen, _printed = await _relay(redirect)
        # One request only: follow_redirects=False, so the literal route stands.
        self.assertEqual(len(seen["requests"]), 1)
        self.assertEqual(str(seen["requests"][0].url),
                         "https://litellm.inf.2up.dev/v1/chat/completions")
        self.assertEqual(result.status_code, 502)
        ledger.unknown.assert_called_once()
        ledger.settle.assert_not_called()


class DeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_and_read_deadlines_are_deliberate_and_ordered(self):
        self.assertEqual(gateway.READ_DEADLINE_SECONDS, 300)
        self.assertEqual(gateway.CONNECT_DEADLINE_SECONDS, 10)
        self.assertEqual(gateway.WRITE_DEADLINE_SECONDS, 30)
        self.assertEqual(gateway.POOL_DEADLINE_SECONDS, 10)
        self.assertLess(gateway.CONNECT_DEADLINE_SECONDS, gateway.READ_DEADLINE_SECONDS)
        self.assertLess(gateway.WRITE_DEADLINE_SECONDS, gateway.READ_DEADLINE_SECONDS)
        # The pre-flight must answer well inside the caller's patience.
        self.assertLess(gateway.PROBE_CONNECT_DEADLINE_SECONDS, gateway.PROBE_READ_DEADLINE_SECONDS)
        self.assertLess(gateway.PROBE_READ_DEADLINE_SECONDS, gateway.READ_DEADLINE_SECONDS)
        # The caller's wait lives in dialogue_bridge.py (Lead-owned); read the
        # current value instead of restating it, so changing it there cannot make
        # this suite red for the wrong reason.
        tree = ast.parse((Path(__file__).parent / "dialogue_bridge.py").read_text())
        waits = [keyword.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "update"
                 for keyword in node.keywords
                 if keyword.arg == "timeout" and isinstance(keyword.value, ast.Constant)]
        self.assertTrue(waits)
        self.assertGreater(max(waits), gateway.READ_DEADLINE_SECONDS)

    async def test_timeout_object_matches_the_constants(self):
        def answer(_request):
            return httpx.Response(200, json={"choices": [], "usage": {}})

        _result, _ledger, seen, _printed = await _relay(answer)
        timeout = seen["kwargs"]["timeout"]
        self.assertEqual(timeout.read, gateway.READ_DEADLINE_SECONDS)
        self.assertEqual(timeout.connect, gateway.CONNECT_DEADLINE_SECONDS)
        self.assertEqual(timeout.write, gateway.WRITE_DEADLINE_SECONDS)
        self.assertEqual(timeout.pool, gateway.POOL_DEADLINE_SECONDS)


class DiagnosticRecordTests(unittest.TestCase):
    def test_identifier_cannot_escape_the_diagnostic_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway.record_transport_failure("../../etc/passwd", "ConnectTimeout", 1.0,
                                             directory=directory)
            written = list(Path(directory).iterdir())
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0].parent.name, Path(directory).name)
        self.assertNotIn("..", written[0].name)
        self.assertNotIn("/", written[0].name)

    def test_collision_appends_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            first = gateway.record_transport_failure("budget-id", "ReadTimeout", 1.0,
                                                     directory=directory)
            gateway.record_transport_failure("budget-id", "ReadTimeout", 2.0, directory=directory)
            names = sorted(path.name for path in Path(directory).iterdir())
            self.assertEqual(names, ["transport-budget-id-1.json", "transport-budget-id.json"])
            self.assertEqual(first["error_type"], "ReadTimeout")

    def test_record_returns_the_same_mapping_it_writes_and_never_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            record = gateway.record_transport_failure("budget-id", "Bad,Type\n", 1.23456,
                                                      transition="reservation_unchanged",
                                                      directory=directory)
            on_disk = json.loads(next(Path(directory).glob("transport-*.json")).read_text())
        self.assertEqual(record, on_disk)
        self.assertEqual(record["error_type"], "BadType")
        self.assertEqual(record["reservation"], "reservation_unchanged")
        self.assertEqual(record["elapsed_seconds"], 1.235)
        # A directory that cannot exist is not an exception: the caller keeps its 502.
        with tempfile.TemporaryDirectory() as directory:
            blocking = Path(directory) / "file"
            blocking.write_text("x")
            gateway.record_transport_failure("budget-id", "ReadTimeout", 1.0,
                                             directory=blocking / "child")


class UpstreamCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_refuses_in_fixture_mode_without_touching_the_network(self):
        def boom(**_kwargs):
            raise AssertionError("no client may be built in fixture mode")

        with patch.object(gateway.httpx, "AsyncClient", boom), \
             patch.dict(os.environ, {"PILOT_GATEWAY_MODE": "fixture"}):
            with self.assertRaises(HTTPException) as raised:
                await gateway.upstream_check(_request())
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail, "live_mode_required")

    async def test_dead_path_is_reported_as_a_typed_metadata_failure(self):
        def dead(_request):
            raise httpx.ConnectTimeout(PRIVATE_SENTINEL)

        response, seen = await _check(dead)
        body = json.loads(response.body)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(body["transport_ok"])
        self.assertIsNone(body["http_status"])
        self.assertEqual(body["error_type"], "ConnectTimeout")
        self.assertIsInstance(body["elapsed_seconds"], float)
        self.assertNotIn(PRIVATE_SENTINEL, response.body.decode())
        self.assertNotIn(UPSTREAM_KEY, response.body.decode())
        # The approved read-only metadata endpoint, a GET, and nothing else.
        request = seen["requests"][0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(str(request.url), "https://litellm.inf.2up.dev/v1/model/info")
        self.assertEqual(request.headers["x-litellm-api-key"], UPSTREAM_KEY)
        self.assertNotIn("authorization", request.headers)

    async def test_reachable_path_reports_status_without_echoing_the_body(self):
        def answer(_request):
            return httpx.Response(401, json={"error": PRIVATE_SENTINEL, "key": UPSTREAM_KEY})

        response, seen = await _check(answer)
        body = json.loads(response.body)
        # TLS works, the route refused: a dead credential is still not a reason to
        # spend, so the pre-flight fails closed while naming which half failed.
        self.assertEqual(response.status_code, 503)
        self.assertTrue(body["transport_ok"])
        self.assertEqual(body["http_status"], 401)
        self.assertIsNone(body["error_type"])
        self.assertEqual(len(seen["requests"]), 1)
        self.assertNotIn(PRIVATE_SENTINEL, response.body.decode())
        self.assertNotIn(UPSTREAM_KEY, response.body.decode())

    async def test_healthy_metadata_answer_is_the_only_go(self):
        def answer(_request):
            return httpx.Response(200, json={"data": [{"model_name": "synthetic"}]})

        response, _seen = await _check(answer)
        body = json.loads(response.body)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["transport_ok"])
        self.assertEqual(body["http_status"], 200)

    async def test_check_creates_no_reservation(self):
        def answer(_request):
            return httpx.Response(200, json={"data": []})

        with patch.object(gateway, "Ledger") as ledger:
            response, _seen = await _check(answer)
        self.assertEqual(response.status_code, 200)
        ledger.assert_not_called()

    async def test_check_requires_the_live_request_key(self):
        def boom(**_kwargs):
            raise AssertionError("an unauthenticated probe must not reach the network")

        request = SimpleNamespace(headers={"authorization": "Bearer wrong"})
        with patch.object(gateway, "_live_config", return_value=dict(CONFIG)), \
             patch.object(gateway.httpx, "AsyncClient", boom), \
             patch.dict(os.environ, {"PILOT_GATEWAY_MODE": "live"}):
            with self.assertRaises(HTTPException) as raised:
                await gateway.upstream_check(request)
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
