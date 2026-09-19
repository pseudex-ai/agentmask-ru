"""A masking reverse proxy built from the reference placeholder masker.

It exists for one test: run `placeholder_regex` DIRECTLY and then run the
same masker BEHIND HTTP through `openai_proxy` + the fake upstream, and
require the two reports to agree. If they do, the proxy path — the side
channel, the alignment against what the upstream received, the restoration
read off the proxy's answer — measures what the direct path measures, and a
number published for Cloud.ru or LiteLLM means the same thing as a number
published for a library.

It is also the smallest possible example of the shape this benchmark
measures, which makes it worth reading before writing an adapter.
"""

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agentmask_ru.adapters.reference import PlaceholderSession


class ReferenceProxy:
    """Masks the request, forwards it upstream, restores the tool call."""

    def __init__(self, upstream_base_url: str, host: str = "127.0.0.1", port: int = 0) -> None:
        self._upstream = upstream_base_url.rstrip("/")
        self._sessions: dict[str, PlaceholderSession] = {}
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt: str, *args: object) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                answer = proxy.handle(body)
                data = json.dumps(answer, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._server = ThreadingHTTPServer((host, port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[0], self._server.server_address[1]
        return f"http://{host}:{port}/v1"

    def _session_for(self, messages: list[dict[str, object]]) -> PlaceholderSession:
        """A conversation is identified by its system prompt, which is what a
        real proxy would key on when the caller sends no conversation id."""
        key = next((str(m.get("content", "")) for m in messages if m.get("role") == "system"), "")
        if key not in self._sessions:
            self._sessions[key] = PlaceholderSession()
        return self._sessions[key]

    def handle(self, body: dict[str, object]) -> dict[str, object]:
        messages = body.get("messages")
        tools = body.get("tools")
        messages = [dict(m) for m in messages] if isinstance(messages, list) else []
        tools = [dict(t) for t in tools] if isinstance(tools, list) else []
        session = self._session_for(messages)
        masked = session.mask(messages, tools)
        forwarded = dict(body)
        forwarded["messages"] = masked.messages
        forwarded["tools"] = masked.tools
        request = urllib.request.Request(
            self._upstream + "/chat/completions",
            data=json.dumps(forwarded, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            answer = json.loads(response.read().decode("utf-8"))
        for choice in answer.get("choices", []):
            message = choice.get("message", {})
            for call in message.get("tool_calls", []) or []:
                function = call.get("function", {})
                if isinstance(function.get("arguments"), str):
                    function["arguments"] = session.restore_arguments(function["arguments"])
        return answer
