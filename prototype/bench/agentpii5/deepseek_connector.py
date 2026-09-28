"""Direct DeepSeek Responses API connector for the benchmark agent."""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from openai import APIError, AsyncOpenAI
    from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage
except ModuleNotFoundError as missing:
    if missing.name != "openai":
        raise
    AsyncOpenAI = None

from bench.agentpii5.connectors import (
    ConnectorError,
    ConnectorLimit,
    Conversation,
    DialogueHooks,
    Json,
    ToolSpec,
    Usage,
    json_object,
)
from bench.agentpii5.provider import DEEPSEEK_CACHED_USD_PER_MTOK, PRICE_BY_KEY


@dataclass(frozen=True)
class DeepSeekSettings:
    model: str
    effort: str
    max_tokens: int
    request_limit: int
    max_output_tokens: int
    usage_path: Path | None
    base_url: str


def deepseek_usage(input_tokens: int, cached_tokens: int, output_tokens: int,
                   reasoning_tokens: int) -> Usage:
    """Convert one or more DeepSeek responses to the benchmark accounting shape."""
    values = (input_tokens, cached_tokens, output_tokens, reasoning_tokens)
    if any(value < 0 for value in values):
        raise ConnectorError("DeepSeek returned a negative token count")
    if cached_tokens > input_tokens:
        raise ConnectorError("cached tokens exceed input tokens")
    price = PRICE_BY_KEY["deepseek", "deepseek-flash"].price
    cost = ((input_tokens - cached_tokens) * price.input_usd_per_mtok
            + cached_tokens * DEEPSEEK_CACHED_USD_PER_MTOK
            + output_tokens * price.output_usd_per_mtok) / 1_000_000
    return Usage(input_tokens, cached_tokens, output_tokens, reasoning_tokens, cost,
                 "deepseek_peak_estimate_2026-09-26")


def response_message_text(message: object) -> str:
    if not isinstance(message, ResponseOutputMessage):
        return ""
    parts: list[str] = []
    for content in message.content:
        text = getattr(content, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


class DeepSeekConnector:
    """Own the stateless Responses history and expose only benchmark tools."""

    def __init__(self, settings: DeepSeekSettings) -> None:
        if AsyncOpenAI is None:
            raise ConnectorError(
                "install bench/agentpii5/requirements-codex.txt in a separate environment")
        if settings.model != "deepseek-flash":
            raise ConnectorError("DeepSeek accounting is verified for deepseek-flash only")
        if min(settings.max_tokens, settings.request_limit, settings.max_output_tokens) <= 0:
            raise ConnectorError("connector limits must be positive")
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise ConnectorError("DEEPSEEK_API_KEY is not set")
        self.settings = settings
        self.requests = 0
        self.client = AsyncOpenAI(api_key=key, base_url=settings.base_url,
                                  max_retries=0)

    async def converse(self, system: str, tools: tuple[ToolSpec, ...],
                       user_indices: tuple[int, ...], hooks: DialogueHooks,
                       timeout_s: float, max_calls: int) -> Conversation:
        started = time.monotonic()
        requests_before = self.requests
        history: list[dict[str, Json]] = []
        replies: list[str] = []
        totals = [0, 0, 0, 0]
        calls = 0
        tool_names = {tool.name for tool in tools}
        wire_tools = [{"type": "function", "name": tool.name,
                       "description": tool.description,
                       "parameters": tool.parameters} for tool in tools]

        async def drive() -> None:
            nonlocal calls
            for index in user_indices:
                history.append({"role": "user", "content": hooks.user(index)})
                turn_text: list[str] = []
                while True:
                    if self.requests >= self.settings.request_limit:
                        raise ConnectorLimit("DeepSeek request limit reached")
                    self.requests += 1
                    response = await self.client.responses.create(
                        model=self.settings.model,
                        instructions=system,
                        input=list(history),
                        tools=wire_tools,
                        tool_choice="auto",
                        reasoning={"effort": self.settings.effort},
                        max_output_tokens=self.settings.max_output_tokens,
                        store=False,
                    )
                    if response.status != "completed":
                        raise ConnectorError(
                            f"DeepSeek response ended {response.status}: {response.error}")
                    if response.usage is None:
                        raise ConnectorError("DeepSeek returned no token usage")
                    usage = response.usage
                    totals[0] += usage.input_tokens
                    totals[1] += usage.input_tokens_details.cached_tokens
                    totals[2] += usage.output_tokens
                    totals[3] += usage.output_tokens_details.reasoning_tokens
                    if totals[0] + totals[2] > self.settings.max_tokens:
                        raise ConnectorLimit("DeepSeek session token limit reached")
                    function_calls = [item for item in response.output
                                      if isinstance(item, ResponseFunctionToolCall)]
                    # THE RESPONSE HOOK, ONCE PER COMPLETED PROVIDER RESPONSE
                    # AND BEFORE ITS FUNCTION CALLS. `""` on a pure tool-call
                    # turn is recorded too: the chronology asks what the MODEL
                    # returned, and a turn that returned no prose answers it.
                    # The connector reports the boundary; the gateway owns what
                    # is restored and what was already available.
                    hooks.response("".join(response_message_text(item)
                                           for item in response.output))
                    for item in response.output:
                        history.append(json_object(item.model_dump(mode="json", exclude_none=True)))
                        text = response_message_text(item)
                        if text:
                            turn_text.append(text)
                    if not function_calls:
                        joined = "\n".join(turn_text)
                        replies.append(joined)
                        hooks.assistant(joined)
                        break
                    for call in function_calls:
                        calls += 1
                        if calls > max_calls:
                            raise ConnectorLimit("tool call limit reached")
                        if call.name not in tool_names:
                            history.append({
                                "type": "function_call_output", "call_id": call.call_id,
                                "output": json.dumps({"error": "unknown_tool"})})
                            continue
                        try:
                            arguments = json_object(json.loads(call.arguments))
                        except (ConnectorError, json.JSONDecodeError):
                            history.append({
                                "type": "function_call_output", "call_id": call.call_id,
                                "output": json.dumps({
                                    "error": "invalid_arguments",
                                    "detail": "arguments must be one JSON object"})})
                            continue
                        result = hooks.tool(call.name, arguments)
                        history.append({"type": "function_call_output",
                                        "call_id": call.call_id, "output": result.text})

        try:
            await asyncio.wait_for(drive(), timeout_s)
        except ConnectorError:
            raise
        except APIError as error:
            detail = str(error)
            secret = os.environ.get("DEEPSEEK_API_KEY", "")
            if secret:
                detail = detail.replace(secret, "[redacted]")
            raise ConnectorError(f"{type(error).__name__}: {detail}") from error
        usage = deepseek_usage(*totals)
        session_id = f"deepseek-{time.time_ns()}"
        if self.settings.usage_path is not None:
            row = {"session_id": session_id, "provider": "deepseek",
                   "model": self.settings.model, "effort": self.settings.effort,
                   "cumulative": True, "requests": self.requests,
                   "usage": asdict(usage)}
            with self.settings.usage_path.open("a", encoding="utf-8") as sink:
                sink.write(json.dumps(row) + "\n")
        return Conversation(tuple(replies), usage, self.requests - requests_before, session_id,
                            int((time.monotonic() - started) * 1000))
