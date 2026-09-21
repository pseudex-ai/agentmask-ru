"""A sidecar that exposes explicit mask / unmask endpoints.

Written against the Pseudex sidecar contract, because that is the sidecar
this benchmark's authors can run; any gateway with the same three endpoints
works unchanged.

    POST /mask              {org_id, messages, tools, conversation_id} -> {messages, tools}
    POST /unmask_arguments  {org_id, arguments: [str]} -> {arguments: [str], residual_tokens?}
    POST /spans             {org_id, texts: [str]} -> {results: [[{start, end, type, ...}]]}

    agentmask run --adapter pseudex_sidecar --base-url http://localhost:8000 --api-key $TOKEN

FAIL-CLOSED IS PART OF THE MEASUREMENT. A gateway that answers 5xx when it
cannot mask has refused to leak; the adapter records the error as the turn's
outcome, and the report counts it. A gateway that answers 200 with the text
unchanged has leaked. The benchmark distinguishes them.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from agentmask_ru.adapters.base import MaskedView, Span, TwoPhaseSession


def _post(url: str, token: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"{url} -> {exc.code}: {detail}") from exc


@dataclass
class SidecarSession(TwoPhaseSession):
    base_url: str
    token: str
    org_id: str
    conversation_id: str
    timeout: float

    def mask(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> MaskedView:
        payload = {
            "org_id": self.org_id,
            "conversation_id": self.conversation_id,
            "messages": messages,
            "tools": tools,
        }
        answer = _post(f"{self.base_url}/mask", self.token, payload, self.timeout)
        returned = answer.get("messages")
        return MaskedView(
            messages=[dict(m) for m in returned] if isinstance(returned, list) else messages,
            tools=[dict(t) for t in answer["tools"]] if isinstance(answer.get("tools"), list) else tools,
        )

    def restore_arguments(self, arguments: str) -> str:
        payload = {"org_id": self.org_id, "conversation_id": self.conversation_id, "arguments": [arguments]}
        answer = _post(f"{self.base_url}/unmask_arguments", self.token, payload, self.timeout)
        restored = answer.get("arguments")
        if isinstance(restored, list) and restored:
            return str(restored[0])
        return arguments

    def spans(self, text: str) -> list[Span] | None:
        payload = {"org_id": self.org_id, "conversation_id": self.conversation_id, "texts": [text]}
        try:
            answer = _post(f"{self.base_url}/spans", self.token, payload, self.timeout)
        except RuntimeError:
            return None
        results = answer.get("results")
        if not isinstance(results, list) or not results:
            return None
        first = results[0]
        if not isinstance(first, list):
            return None
        return [Span(start=int(s["start"]), end=int(s["end"]), type=str(s["type"])) for s in first]


class PseudexSidecarMasker:
    def __init__(self, base_url: str, token: str, org_id: str, name: str, timeout: float) -> None:
        self.name = name
        self.config: dict[str, object] = {
            "adapter": "pseudex_sidecar", "base_url": base_url, "org_id": org_id, "timeout_s": timeout,
        }
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._org_id = org_id
        self._timeout = timeout

    def open(self, case_id: str) -> SidecarSession:
        return SidecarSession(base_url=self._base_url, token=self._token, org_id=self._org_id,
                              conversation_id=case_id, timeout=self._timeout)
