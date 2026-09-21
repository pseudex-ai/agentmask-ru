"""A deterministic OpenAI-compatible «model», so a reverse-proxy masker can
be measured without a model.

HOW A PROXY IS MEASURED AT ALL. A proxy masker (Cloud.ru's Go filter,
LiteLLM, our own proxy leg) never hands the masked text to its caller: it
masks, forwards to the provider, and restores the answer. Put this server
where the provider goes, and the masked text arrives here — which is
exactly what the model would have seen. The harness registers what it
expects before each request; this server looks up that expectation, calls
the harness's decision function with what it received, and returns the
resulting tool call. The proxy then restores the arguments and the harness
reads what the tool would have got.

ROUTING IS A SIDE CHANNEL, NOT A TOKEN IN THE TEXT. The case id also rides
in the system prompt as `[case:…]`, but a masker is free to mask the system
prompt (ours does), so the id in the text is only a cross-check. Requests
are answered one at a time, in the order the harness set them up, and the
tool-call id is derived from the case and turn so a proxy that caches or
reorders is caught rather than silently credited.

NO STREAMING in v0.1: `stream: true` is answered with a single-chunk SSE
body, which is enough for a proxy to parse but does not pretend to measure
incremental detokenisation.
"""

import hashlib
import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from agentmask_ru.adapters.base import MaskedView, ModelReply

Decide = Callable[[MaskedView], ModelReply]


@dataclass
class Expectation:
    case_id: str
    turn: int
    decide: Decide


class FakeUpstream:
    """An OpenAI-compatible endpoint that answers from the expectation the
    harness set. Bind to 0.0.0.0 when a container has to reach it."""

    def __init__(self, host: str, port: int) -> None:
        self._lock = threading.Lock()
        self._expectation: Expectation | None = None
        self._last_seen: MaskedView | None = None
        self._requests = 0
        self._mismatches: list[str] = []
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt: str, *args: object) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's spelling
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw.decode("utf-8"))
                except ValueError:
                    self._reply(400, {"error": {"message": "invalid JSON"}})
                    return
                if not self.path.rstrip("/").endswith("chat/completions"):
                    self._reply(404, {"error": {"message": f"no route for {self.path}"}})
                    return
                payload, status = upstream.answer(body)
                if bool(body.get("stream")):
                    self._reply_sse(payload)
                else:
                    self._reply(status, payload)

            def _reply(self, status: int, payload: dict[str, object]) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _reply_sse(self, payload: dict[str, object]) -> None:
                choice = payload["choices"][0]  # type: ignore[index]
                message = choice["message"]  # type: ignore[index]
                chunk = {
                    "id": payload["id"], "object": "chat.completion.chunk", "created": payload["created"],
                    "model": payload["model"],
                    "choices": [{"index": 0, "delta": message, "finish_reason": choice["finish_reason"]}],  # type: ignore[index]
                }
                body = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    # --- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[0], self._server.server_address[1]
        shown = "127.0.0.1" if host in ("0.0.0.0", "") else host
        return f"http://{shown}:{port}/v1"

    @property
    def requests(self) -> int:
        return self._requests

    @property
    def mismatches(self) -> list[str]:
        return list(self._mismatches)

    # --- the contract with the harness -------------------------------------

    def expect(self, case_id: str, turn: int, decide: Decide) -> None:
        with self._lock:
            self._expectation = Expectation(case_id=case_id, turn=turn, decide=decide)
            self._last_seen = None

    def last_seen(self) -> MaskedView | None:
        with self._lock:
            return self._last_seen

    def answer(self, body: dict[str, object]) -> tuple[dict[str, object], int]:
        with self._lock:
            expectation = self._expectation
            self._requests += 1
            if expectation is None:
                return {"error": {"message": "no expectation registered"}}, 409
            messages = body.get("messages")
            tools = body.get("tools")
            masked = MaskedView(
                messages=[dict(m) for m in messages] if isinstance(messages, list) else [],
                tools=[dict(t) for t in tools] if isinstance(tools, list) else [],
            )
            self._last_seen = masked
            system = " ".join(str(m.get("content", "")) for m in masked.messages if m.get("role") == "system")
            if f"[case:{expectation.case_id}]" not in system:
                # Not an error: a masker may mask the system prompt. Recorded
                # so a run can say how often the cross-check was unavailable.
                self._mismatches.append(expectation.case_id)
            reply = expectation.decide(masked)
            call_id = "call_" + hashlib.sha1(f"{expectation.case_id}:{expectation.turn}".encode("utf-8")).hexdigest()[:16]
            message: dict[str, object] = {"role": "assistant", "content": reply.text}
            finish = "stop"
            if reply.tool_call is not None:
                message["content"] = None
                message["tool_calls"] = [{
                    "id": call_id, "type": "function",
                    "function": {"name": reply.tool_call.name, "arguments": reply.tool_call.arguments},
                }]
                finish = "tool_calls"
            payload = {
                "id": "chatcmpl-" + call_id[5:],
                "object": "chat.completion",
                "created": 1758326400,
                "model": str(body.get("model", "agentmask-fake")),
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            return payload, 200
