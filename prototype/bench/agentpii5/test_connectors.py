"""Offline connector checks: real gateway hooks, no model, no network."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from bench.agentpii5 import harness as h
from bench.agentpii5.codex_connector import (
    CodexJudgeConnector, CodexSettings, CodexSubscriptionModel,
    clean_runtime_overrides, usage_from_wire)
from bench.agentpii5.connectors import (
    ConnectorError, ConnectorLimit, Conversation, DialogueHooks, Json, ToolSpec, Usage, json_object)
from bench.agentpii5.deepseek_connector import DeepSeekConnector, DeepSeekSettings, deepseek_usage
from bench.agentpii5.judge import ConnectedJudgeConfig, JUDGE_TEMPERATURE, _ask, parse_verdict
from bench.agentpii5.mock import seed_backend_v5


class ScriptedAgent:
    """An external connector double, deliberately ignorant of benchmark objects."""

    async def converse(self, system: str, tools: tuple[ToolSpec, ...],
                       user_indices: tuple[int, ...], hooks: DialogueHooks,
                       timeout_s: float, max_calls: int) -> Conversation:
        replies: list[str] = []
        for index in user_indices:
            text = hooks.user(index)
            hooks.assistant(text)
            replies.append(text)
        return Conversation(tuple(replies), Usage(10, 0, 10, 0, 0.001, 'fixture'),
                            len(replies), 'fixture-session', 1)


class ScriptedJudge:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    async def evaluate(self, system: str, prompt: str,
                       schema: dict[str, Json], timeout_s: float) -> Conversation:
        if schema.get('additionalProperties') is not False:
            raise AssertionError('judge schema must forbid extra keys')
        return Conversation((self.reply,), Usage(10, 0, 5, 0, 0.0, 'subscription'),
                            1, 'judge-fixture', 1)


class BrokenAgent:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def converse(self, system: str, tools: tuple[ToolSpec, ...],
                       user_indices: tuple[int, ...], hooks: DialogueHooks,
                       timeout_s: float, max_calls: int) -> Conversation:
        raise self.error


class RecordingHooks:
    def __init__(self) -> None:
        self.assistant_texts: list[str] = []
        self.tool_calls: list[tuple[str, dict[str, Json]]] = []
        # The provider-response hook is part of `DialogueHooks`; a double that
        # omits it would make the connector's new call an AttributeError.
        self.responses: list[str] = []

    def user(self, index: int) -> str:
        return f'user-{index}'

    def assistant(self, text: str) -> None:
        self.assistant_texts.append(text)

    def response(self, text: str) -> None:
        self.responses.append(text)

    def tool(self, name: str, arguments: dict[str, Json]) -> h.ToolResult:
        self.tool_calls.append((name, arguments))
        return h.ToolResult('{"ok":true}', True)


class FakeResponses:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []

    async def create(self, **request: object) -> object:
        self.requests.append(request)
        return self.responses.pop(0)


class FakeOpenAI:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


class ConnectorTests(unittest.TestCase):
    def test_request_limit_precedes_sdk_construction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = CodexSettings('fixture', 'medium', 20000, 1, None, Path(directory))
            connector = CodexJudgeConnector(settings)
            connector.requests = 1
            with self.assertRaises(ConnectorLimit):
                asyncio.run(connector.evaluate('system', 'prompt', {}, 1.0))
        self.assertEqual(connector.requests, 1)

    def test_transport_failure_is_not_a_product_defect(self) -> None:
        cases, _ = h._load_corpus(Path(__file__).with_name('corpus.v5.json'))
        case = next(case for case in cases if case.base.id == 'validate-000')
        for error, termination in ((ConnectorError('offline transport'), 'harness_error'),
                                    (TimeoutError('deadline'), 'timeout')):
            outcome = asyncio.run(h.ConnectedArms(BrokenAgent(error)).control(
                case, 'C', 0, seed_backend_v5(case), 'fixture', 0.15, 'fixture-run'))
            self.assertEqual(outcome.run.termination, termination)
            self.assertEqual(outcome.run.cost_usd, 0.15)
            self.assertIn(str(error), outcome.meta.reason)

    def test_json_boundary(self) -> None:
        original = {'nested': [{'x': 1}]}
        converted = json_object(original)
        self.assertEqual(converted, original)
        self.assertIsNot(converted, original)
        for bad in (object(), [], {1: 'wrong key'}):
            with self.assertRaises(ConnectorError):
                json_object(bad)

    def test_usage_is_not_a_subscription_bill(self) -> None:
        raw: dict[str, Json] = {'inputTokens': 1000, 'cachedInputTokens': 500,
                                'outputTokens': 100, 'reasoningOutputTokens': 30}
        deepseek = deepseek_usage(1000, 500, 100, 30)
        self.assertAlmostEqual(deepseek.cost_usd, 0.000273)
        self.assertIn('estimate', deepseek.cost_basis)
        subscription = usage_from_wire(raw)
        self.assertEqual(subscription.input_tokens, 1000)
        self.assertEqual(subscription.cost_usd, 0.0)
        self.assertIn('quota_not_api_usd', subscription.cost_basis)
        with self.assertRaises(ConnectorError):
            usage_from_wire({**raw, 'cachedInputTokens': 1001})
        with self.assertRaises(ConnectorError):
            usage_from_wire({})

    def test_runtime_overrides_do_not_enable_host_tools(self) -> None:
        overrides = clean_runtime_overrides()
        for feature in ('shell_tool', 'multi_agent', 'goals', 'hooks', 'apps'):
            self.assertIn(f'features.{feature}=false', overrides)
        self.assertIn('web_search="disabled"', overrides)
        self.assertIn('include_environment_context=false', overrides)
        self.assertIn('include_permissions_instructions=false', overrides)
        self.assertIn('include_apps_instructions=false', overrides)
        self.assertIn('include_collaboration_mode_instructions=false', overrides)
        self.assertIn('skills.include_instructions=false', overrides)
        self.assertIn('tools.experimental_request_user_input.enabled=false', overrides)
        self.assertFalse(any('api_key=' in item for item in overrides))

    def test_agents_sdk_preserves_exact_judge_envelope(self) -> None:
        schema: dict[str, Json] = {
            'type': 'object', 'properties': {'label': {'type': 'string'}},
            'required': ['label'], 'additionalProperties': False}
        usage = Usage(12, 2, 4, 1, 0.0, 'subscription')
        with tempfile.TemporaryDirectory() as directory:
            settings = CodexSettings('gpt-5.6-terra', 'medium', 20000, 1, None,
                                     Path(directory))
            with patch.object(CodexSubscriptionModel, '_drive',
                              return_value=('{"label":"ok"}', usage, 'clean', 3)):
                result = asyncio.run(CodexJudgeConnector(settings).evaluate(
                    'ONLY SYSTEM', 'ONLY USER', schema, 5.0))
        self.assertEqual(json.loads(result.replies[0]), {'label': 'ok'})
        self.assertEqual(result.session_id, 'clean')

    def test_deepseek_direct_loop_sends_only_benchmark_envelope(self) -> None:
        usage = SimpleNamespace(
            input_tokens=20, output_tokens=5,
            input_tokens_details=SimpleNamespace(cached_tokens=3),
            output_tokens_details=SimpleNamespace(reasoning_tokens=2))
        call = ResponseFunctionToolCall(
            type='function_call', call_id='call-1', name='lookup', arguments='{"id":"x"}')
        answer = ResponseOutputMessage(
            id='msg-1', type='message', role='assistant', status='completed',
            content=[ResponseOutputText(type='output_text', text='done', annotations=[], logprobs=[])])
        responses = FakeResponses([
            SimpleNamespace(status='completed', error=None, usage=usage, output=[call]),
            SimpleNamespace(status='completed', error=None, usage=usage, output=[answer]),
        ])
        settings = DeepSeekSettings('deepseek-flash', 'low', 1000, 2, 100,
                                    None, 'https://api.deepseek.com')
        hooks = RecordingHooks()
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'fixture'}, clear=False), \
             patch('bench.agentpii5.deepseek_connector.AsyncOpenAI',
                   return_value=FakeOpenAI(responses)):
            result = asyncio.run(DeepSeekConnector(settings).converse(
                'ONLY SYSTEM', (ToolSpec('lookup', 'lookup one', {
                    'type': 'object', 'properties': {'id': {'type': 'string'}}}),),
                (7,), hooks, 5.0, 1))
        self.assertEqual(result.replies, ('done',))
        self.assertEqual(hooks.tool_calls, [('lookup', {'id': 'x'})])
        self.assertEqual(hooks.assistant_texts, ['done'])
        self.assertEqual(len(responses.requests), 2)
        first = responses.requests[0]
        self.assertEqual(first['instructions'], 'ONLY SYSTEM')
        self.assertEqual(first['input'], [{'role': 'user', 'content': 'user-7'}])
        self.assertEqual([tool['name'] for tool in first['tools']], ['lookup'])
        self.assertNotIn('previous_response_id', first)

    def test_deepseek_returns_schema_error_and_allows_argument_repair(self) -> None:
        usage = SimpleNamespace(
            input_tokens=10, output_tokens=2,
            input_tokens_details=SimpleNamespace(cached_tokens=0),
            output_tokens_details=SimpleNamespace(reasoning_tokens=1))
        broken = ResponseFunctionToolCall(
            type='function_call', call_id='broken', name='lookup', arguments='{')
        repaired = ResponseFunctionToolCall(
            type='function_call', call_id='repaired', name='lookup', arguments='{"id":"x"}')
        answer = ResponseOutputMessage(
            id='msg-2', type='message', role='assistant', status='completed',
            content=[ResponseOutputText(type='output_text', text='done', annotations=[], logprobs=[])])
        responses = FakeResponses([
            SimpleNamespace(status='completed', error=None, usage=usage, output=[broken]),
            SimpleNamespace(status='completed', error=None, usage=usage, output=[repaired]),
            SimpleNamespace(status='completed', error=None, usage=usage, output=[answer]),
        ])
        settings = DeepSeekSettings('deepseek-flash', 'low', 1000, 3, 100,
                                    None, 'https://api.deepseek.com')
        hooks = RecordingHooks()
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'fixture'}, clear=False), \
             patch('bench.agentpii5.deepseek_connector.AsyncOpenAI',
                   return_value=FakeOpenAI(responses)):
            result = asyncio.run(DeepSeekConnector(settings).converse(
                'system', (ToolSpec('lookup', 'lookup one', {
                    'type': 'object', 'properties': {'id': {'type': 'string'}}}),),
                (0,), hooks, 5.0, 2))
        self.assertEqual(result.replies, ('done',))
        self.assertEqual(hooks.tool_calls, [('lookup', {'id': 'x'})])
        self.assertIn('invalid_arguments', responses.requests[1]['input'][-1]['output'])

    def test_generic_agent_uses_existing_gateway(self) -> None:
        cases, _ = h._load_corpus(Path(__file__).with_name('corpus.v5.json'))
        case = next(case for case in cases if case.base.id == 'validate-000')
        h.load_dev_bundle()
        gateway = h.GatewayV5(case, h.Detector(), h.Vault(':memory:', 'connector-test'),
                              h.AuditLog(':memory:'), h.MaskCache(256))
        runner = h.ConnectedArms(ScriptedAgent())
        outcome = asyncio.run(runner.intervention(case, 0, gateway, seed_backend_v5(case),
                                                  'scripted', 0.15, 'fixture-run'))
        self.assertEqual(outcome.base.run.termination, 'done')
        self.assertEqual(outcome.base.meta.session_id, 'fixture-session')
        self.assertGreater(len(outcome.run.mentions), 0)
        self.assertNotEqual(outcome.run.reply_raw, outcome.base.run.reply)
        self.assertGreater(len(outcome.run.turn_replies), 0)

    def test_tool_round_trip_records_restored_arguments(self) -> None:
        cases, _ = h._load_corpus(Path(__file__).with_name('corpus.v5.json'))
        case = next(case for case in cases if case.base.id == 'validate-000')
        h.load_dev_bundle()
        gateway = h.GatewayV5(case, h.Detector(), h.Vault(':memory:', 'connector-tools'),
                              h.AuditLog(':memory:'), h.MaskCache(256))
        hooks = h.GatewayHooks(case, gateway, seed_backend_v5(case))
        gateway.push_system(case.base.messages[0].content)
        gateway.tools()
        turn = next(i for i, message in enumerate(case.base.messages) if message.role == 'user')
        hooks.user(turn)
        by_item = h.substitutes_for(case.base, gateway.substitutes_seen())
        substitutes = {item.type: by_item[item.id][0] for item in case.base.pii}
        self.assertTrue(substitutes)
        arguments: dict[str, Json] = {'name': substitutes['NAME'],
                                     'snils': substitutes['SNILS'], 'passport': substitutes['PASSPORT']}
        result = hooks.tool('passport_verify', arguments)
        self.assertIsInstance(result.text, str)
        self.assertEqual(len(hooks.calls), 1)
        self.assertNotEqual(hooks.calls[0].written, hooks.calls[0].restored)
        self.assertEqual(hooks.turns, [turn])
        self.assertEqual(len(gateway.tool_records()), 1)
        self.assertEqual(gateway.tool_records()[0].call_ordinal, 0)
        self.assertEqual(arguments['snils'], substitutes['SNILS'])

    def test_judge_preserves_quote_gate_and_shared_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = h.v3_judge.SpendLedger(Path(directory) / 'spend.tsv', 1.0)
            connector = ScriptedJudge(json.dumps({'label': 'верно', 'quote': 'Готово', 'reason': 'ok'}))
            config = ConnectedJudgeConfig('fixture', ledger, 0.05, 1, None,
                                           JUDGE_TEMPERATURE, connector)
            raw, spent, error = asyncio.run(_ask('evidence', 'fixture', config))
            self.assertIsNotNone(raw)
            self.assertEqual(error, '')
            self.assertEqual(spent, 0.0)
            self.assertIsNotNone(parse_verdict(raw, 'Готово.', spent))
            self.assertIsNone(parse_verdict(raw, 'Другой ответ.', spent))
            broken = ConnectedJudgeConfig('fixture', ledger, 0.05, 1, None,
                                           JUDGE_TEMPERATURE, ScriptedJudge('not JSON'))
            invalid, _, reason = asyncio.run(_ask('evidence', 'broken', broken))
            self.assertIsNone(invalid)
            self.assertIn('JSONDecodeError', reason)


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ConnectorTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
