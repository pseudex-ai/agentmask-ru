"""OpenAI Agents SDK judge backed by ChatGPT-authenticated Codex SDK."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from agents import Agent, ModelSettings, Runner, set_tracing_disabled
    from agents.agent_output import AgentOutputSchemaBase
    from agents.exceptions import AgentsException
    from agents.items import ModelResponse
    from agents.models.interface import Model
    from agents.retry import ModelRetrySettings
    from agents.usage import Usage as AgentsUsage
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText
    from openai_codex.client import CodexClient, CodexConfig
    from openai_codex.errors import CodexError
    from openai_codex.models import UnknownNotification
except ModuleNotFoundError as missing:
    if missing.name not in {"agents", "openai_codex"}:
        raise
    Agent = None
    Runner = None
    Model = object

from bench.agentpii5.connectors import (
    ConnectorError,
    ConnectorLimit,
    Conversation,
    Json,
    Usage,
    json_object,
)


@dataclass(frozen=True)
class CodexSettings:
    model: str
    effort: str
    max_tokens: int
    request_limit: int
    usage_path: Path | None
    codex_home: Path


def clean_runtime_overrides() -> tuple[str, ...]:
    """Remove every Codex-owned instruction and tool from the judge request."""
    disabled = ("shell_tool", "unified_exec", "apps", "plugins", "multi_agent",
                "browser_use", "computer_use", "view_image", "sleep_tool",
                "memories", "skill_search", "tool_suggest", "code_mode_host",
                "unbounded_connection_retries", "hooks", "goals")
    entries = [f"features.{name}=false" for name in disabled]
    entries.extend((
        'web_search="disabled"',
        "project_doc_max_bytes=0",
        "include_environment_context=false",
        "include_permissions_instructions=false",
        "include_apps_instructions=false",
        "include_collaboration_mode_instructions=false",
        "skills.include_instructions=false",
        "features.skip_host_skill_discovery=true",
        "tools.experimental_request_user_input.enabled=false",
        "model_auto_compact_token_limit=1000000",
    ))
    return tuple(entries)


def usage_from_wire(raw: dict[str, Json]) -> Usage:
    values: list[int] = []
    for name in ("inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens"):
        number = raw.get(name)
        if type(number) is not int or number < 0:
            raise ConnectorError(f"missing or invalid usage field: {name}")
        values.append(number)
    input_tokens, cached_tokens, output_tokens, reasoning_tokens = values
    if cached_tokens > input_tokens:
        raise ConnectorError("cached tokens exceed input tokens")
    return Usage(input_tokens, cached_tokens, output_tokens, reasoning_tokens, 0.0,
                 "chatgpt_subscription_quota_not_api_usd")


def exact_user_prompt(value: object) -> str | None:
    """Accept only Agents SDK's lossless normalization of one user string."""
    if isinstance(value, str):
        return value
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        return None
    item = value[0]
    if item.get("role") != "user" or set(item) != {"role", "content"}:
        return None
    content = item.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
        return None
    part = content[0]
    if part.get("type") != "input_text" or set(part) != {"type", "text"}:
        return None
    text = part.get("text")
    return text if isinstance(text, str) else None


class DictOutputSchema(AgentOutputSchemaBase):
    """Keep the existing judge JSON schema authoritative inside Agents SDK."""

    def __init__(self, schema: dict[str, Json]) -> None:
        self.schema = schema

    def is_plain_text(self) -> bool:
        return False

    def name(self) -> str:
        return "agentpii5_judge_verdict"

    def json_schema(self) -> dict[str, object]:
        return dict(self.schema)

    def is_strict_json_schema(self) -> bool:
        return True

    def validate_json(self, json_str: str) -> object:
        try:
            return json_object(json.loads(json_str))
        except json.JSONDecodeError as error:
            raise ConnectorError("Codex judge returned invalid JSON") from error


class CodexSubscriptionModel(Model):
    """Agents SDK Model adapter whose transport is the official Codex SDK."""

    def __init__(self, settings: CodexSettings, expected_system: str,
                 expected_prompt: str, schema: dict[str, Json]) -> None:
        self.settings = settings
        self.expected_system = expected_system
        self.expected_prompt = expected_prompt
        self.schema = schema
        self.last_usage: Usage | None = None
        self.last_session_id = ""
        self.last_duration_ms = 0

    async def get_response(self, system_instructions: str | None, input: object,
                           model_settings: object, tools: list[object],
                           output_schema: AgentOutputSchemaBase | None,
                           handoffs: list[object], tracing: object, *,
                           previous_response_id: str | None,
                           conversation_id: str | None,
                           prompt: object | None) -> ModelResponse:
        if system_instructions != self.expected_system:
            raise ConnectorError("Agents SDK changed the judge system instructions")
        if exact_user_prompt(input) != self.expected_prompt:
            raise ConnectorError("Agents SDK changed the judge input")
        if tools or handoffs or previous_response_id or conversation_id or prompt:
            raise ConnectorError("Agents SDK added state, handoffs, prompt or tools")
        if output_schema is None or output_schema.json_schema() != self.schema:
            raise ConnectorError("Agents SDK changed the judge output schema")
        text, usage, session_id, duration_ms = await asyncio.to_thread(self._drive)
        self.last_usage = usage
        self.last_session_id = session_id
        self.last_duration_ms = duration_ms
        return ModelResponse(
            output=[ResponseOutputMessage(
                id=f"msg_{session_id}", type="message", role="assistant",
                status="completed", content=[ResponseOutputText(
                    text=text, type="output_text", annotations=[], logprobs=[])])],
            usage=AgentsUsage(requests=1, input_tokens=usage.input_tokens,
                              output_tokens=usage.output_tokens,
                              total_tokens=usage.input_tokens + usage.output_tokens),
            response_id=session_id,
        )

    async def stream_response(self, system_instructions: str | None, input: object,
                              model_settings: object, tools: list[object],
                              output_schema: AgentOutputSchemaBase | None,
                              handoffs: list[object], tracing: object, *,
                              previous_response_id: str | None,
                              conversation_id: str | None,
                              prompt: object | None) -> AsyncIterator[object]:
        if False:
            yield object()
        raise ConnectorError("streaming is not supported by the benchmark judge")

    def _drive(self) -> tuple[str, Usage, str, int]:
        started = time.monotonic()
        environment = dict(os.environ)
        environment["CODEX_HOME"] = str(self.settings.codex_home)
        with tempfile.TemporaryDirectory(prefix="agentpii5-judge-") as cwd:
            client = CodexClient(CodexConfig(
                cwd=cwd, env=environment, config_overrides=clean_runtime_overrides()),
                approval_handler=self._reject_server_request)
            try:
                client.start()
                client.initialize()
                account = client.account_read()
                if account.account is None or account.account.root.type != "chatgpt":
                    raise ConnectorError("judge requires ChatGPT subscription authentication")
                thread = client.thread_start({
                    "model": self.settings.model,
                    "modelProvider": "openai",
                    "baseInstructions": self.expected_system,
                    "developerInstructions": "",
                    "cwd": cwd,
                    "ephemeral": True,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                    "dynamicTools": [],
                })
                if thread.instruction_sources:
                    raise ConnectorError(
                        "Codex loaded hidden instruction sources: "
                        + ", ".join(str(path) for path in thread.instruction_sources))
                if thread.model != self.settings.model or thread.model_provider != "openai":
                    raise ConnectorError("Codex selected a different judge model or provider")
                turn = client.turn_start(thread.thread.id, self.expected_prompt, {
                    "effort": self.settings.effort,
                    "outputSchema": self.schema,
                })
                texts: list[str] = []
                usage: Usage | None = None
                try:
                    while True:
                        event = client.next_turn_notification(turn.turn.id)
                        raw = (event.payload.params if isinstance(event.payload, UnknownNotification)
                               else json_object(event.payload.model_dump(
                                   by_alias=True, mode="json")))
                        if event.method == "thread/tokenUsage/updated":
                            totals = json_object(json_object(raw["tokenUsage"])["total"])
                            usage = usage_from_wire(totals)
                            if usage.input_tokens + usage.output_tokens > self.settings.max_tokens:
                                raise ConnectorLimit("Codex judge token limit reached")
                        if event.method == "item/completed":
                            item = json_object(raw["item"])
                            item_type = item.get("type")
                            if item_type == "agentMessage":
                                if item.get("phase") not in (None, "final_answer"):
                                    raise ConnectorError(
                                        "Codex judge emitted non-final commentary")
                                if item.get("questions"):
                                    raise ConnectorError(
                                        "Codex judge requested user input")
                                text = item.get("text")
                                if isinstance(text, str) and text:
                                    texts.append(text)
                            elif item_type in ("commandExecution", "fileChange", "mcpToolCall",
                                               "webSearch", "dynamicToolCall"):
                                raise ConnectorError(
                                    f"Codex judge used unrequested tool: {item_type}")
                        if event.method == "turn/completed":
                            completed = json_object(raw["turn"])
                            if completed.get("status") != "completed":
                                raise ConnectorError(
                                    f"Codex judge ended {completed.get('status')}: "
                                    f"{json.dumps(completed.get('error'))}")
                            break
                finally:
                    client.unregister_turn_notifications(turn.turn.id)
                if usage is None:
                    raise ConnectorError("Codex judge returned no token usage")
                if not texts:
                    raise ConnectorError("Codex judge returned no final text")
                return "\n".join(texts), usage, thread.thread.id, int(
                    (time.monotonic() - started) * 1000)
            except CodexError as error:
                raise ConnectorError(f"CodexError: {error}") from error
            finally:
                client.close()

    @staticmethod
    def _reject_server_request(method: str,
                               params: dict[str, Json] | None) -> dict[str, Json]:
        raise ConnectorError(f"Codex judge requested forbidden interaction: {method}")


class CodexJudgeConnector:
    """Run the existing judge rubric through Agents SDK and subscription Codex."""

    def __init__(self, settings: CodexSettings) -> None:
        if Agent is None or Runner is None:
            raise ConnectorError(
                "install bench/agentpii5/requirements-codex.txt in a separate environment")
        if min(settings.max_tokens, settings.request_limit) <= 0:
            raise ConnectorError("connector limits must be positive")
        if not settings.codex_home.is_dir():
            raise ConnectorError(f"AGENTPII5_CODEX_HOME does not exist: {settings.codex_home}")
        if (settings.codex_home / "AGENTS.md").exists():
            raise ConnectorError("dedicated Codex home must not contain AGENTS.md")
        self.settings = settings
        self.requests = 0
        self.lock = asyncio.Lock()
        set_tracing_disabled(disabled=True)

    async def evaluate(self, system: str, prompt: str,
                       schema: dict[str, Json], timeout_s: float) -> Conversation:
        async with self.lock:
            if self.requests >= self.settings.request_limit:
                raise ConnectorLimit("Codex judge request limit reached")
            self.requests += 1
            model = CodexSubscriptionModel(self.settings, system, prompt, schema)
            agent = Agent(name="AgentPII v5 judge", instructions=system, model=model,
                          model_settings=ModelSettings(
                              retry=ModelRetrySettings(max_retries=0)),
                          output_type=DictOutputSchema(schema), tools=[])
            try:
                result = await asyncio.wait_for(
                    Runner.run(agent, prompt, max_turns=1), timeout_s)
            except (ConnectorError, TimeoutError):
                raise
            except (AgentsException, OSError) as error:
                raise ConnectorError(f"{type(error).__name__}: {error}") from error
            if model.last_usage is None:
                raise ConnectorError("Agents SDK completed without Codex usage")
            if not isinstance(result.final_output, dict):
                raise ConnectorError("Agents SDK judge returned a non-object verdict")
            reply = json.dumps(result.final_output, ensure_ascii=False)
            if self.settings.usage_path is not None:
                row = {"session_id": model.last_session_id, "provider": "openai",
                       "model": self.settings.model, "effort": self.settings.effort,
                       "cumulative": True, "usage": asdict(model.last_usage)}
                with self.settings.usage_path.open("a", encoding="utf-8") as sink:
                    sink.write(json.dumps(row) + "\n")
            return Conversation((reply,), model.last_usage, 1, model.last_session_id,
                                model.last_duration_ms)
