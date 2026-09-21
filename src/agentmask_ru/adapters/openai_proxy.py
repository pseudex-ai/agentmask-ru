"""Any OpenAI-compatible masking proxy, measured through the fake upstream.

    agentmask run --adapter openai_proxy --base-url http://localhost:8080/v1

The adapter posts an ordinary `/chat/completions` request at the proxy. The
proxy masks it, forwards it to whatever it was configured to call — which
the operator points at our fake upstream — and restores the answer. What
comes back to us is therefore the RESTORED tool call, and the masked view
is read off the fake upstream, which saw exactly what the model would have.

CONFIGURATION IS THE OPERATOR'S JOB, AND THE MANIFEST RECORDS IT. This
adapter cannot tell a proxy where its upstream is; every proxy does that
differently (an env var, a YAML file, a compose recipe). `baselines/`
carries one recipe per measured system, and the run manifest stores the
adapter config verbatim so a reader knows what was pointed at what.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from agentmask_ru.adapters.base import Decide, MaskedView, ModelReply, ToolCall, TurnResult
from agentmask_ru.upstream import FakeUpstream


@dataclass
class ProxySession:
    base_url: str
    api_key: str
    model: str
    timeout: float
    upstream: FakeUpstream
    case_id: str
    turn: int = 0

    def spans(self, text: str) -> None:
        return None

    def close(self) -> None:
        return None

    def run_turn(self, messages: list[dict[str, object]], tools: list[dict[str, object]], decide: Decide) -> TurnResult:
        self.upstream.expect(self.case_id, self.turn, decide)
        self.turn += 1
        payload = {"model": self.model, "messages": messages, "tools": tools, "temperature": 0, "stream": False}
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            return TurnResult(masked=self.upstream.last_seen(), reply=None, restored_arguments=None,
                              error=f"proxy returned {exc.code}: {detail}")
        except Exception as exc:  # noqa: BLE001 — a dead proxy is a measurement
            return TurnResult(masked=None, reply=None, restored_arguments=None, error=f"proxy unreachable: {exc}")

        masked = self.upstream.last_seen()
        if masked is None:
            return TurnResult(masked=None, reply=None, restored_arguments=None,
                              error="the proxy answered without calling the upstream")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return TurnResult(masked=masked, reply=None, restored_arguments=None, error="no choices in the proxy answer")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            return TurnResult(masked=masked, reply=None, restored_arguments=None, error="no message in the proxy answer")
        calls = message.get("tool_calls")
        if isinstance(calls, list) and calls:
            function = calls[0].get("function", {}) if isinstance(calls[0], dict) else {}
            name = str(function.get("name", ""))
            arguments = str(function.get("arguments", ""))
            reply = ModelReply(text=None, tool_call=ToolCall(name=name, arguments=arguments))
            return TurnResult(masked=masked, reply=reply, restored_arguments=arguments, error=None)
        text = message.get("content")
        return TurnResult(masked=masked, reply=ModelReply(text=str(text) if text else None, tool_call=None),
                          restored_arguments=None, error=None)


class ProxyMasker:
    """`name` is what appears on the leaderboard, so a run against Cloud.ru
    is submitted as `cloudru`, not as `openai_proxy`."""

    def __init__(self, name: str, base_url: str, upstream: FakeUpstream, api_key: str, model: str, timeout: float) -> None:
        self.name = name
        self.config: dict[str, object] = {
            "adapter": "openai_proxy", "base_url": base_url, "model": model,
            "upstream": upstream.base_url, "timeout_s": timeout,
        }
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._upstream = upstream

    def open(self, case_id: str) -> ProxySession:
        return ProxySession(base_url=self._base_url, api_key=self._api_key, model=self._model,
                            timeout=self._timeout, upstream=self._upstream, case_id=case_id)
