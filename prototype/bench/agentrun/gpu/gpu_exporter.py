"""Экспортёр метрик железа: nvidia-smi -> формат Prometheus.

WHY NOT dcgm-exporter. It is the right answer on a cluster and the wrong one
here: it is a separate image, and a RunPod pod runs ONE container with no way to
compose a second alongside it. Building a combined image to add six numbers
would put a docker build between us and every run.

WHY NOT the RunPod console. It shows utilisation as a moving bar and keeps no
history, so «упёрлись ли мы в память на третьей сотне диалогов» is unanswerable
after the fact — which is the only time anyone asks it.

The six numbers are the ones that decide whether the rented card was the right
one: utilisation says whether the GPU is the bottleneck at all, memory says
whether the context length and batch fit, power and clocks say whether it is
throttling, and temperature says why.

Serves plain text on /metrics. The port is reachable through RunPod's public
HTTP proxy, so the same api key sglang uses is required here — utilisation is
not a secret, but an open endpoint on a machine processing personal data is a
door nobody needs.
"""

import argparse
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# (nvidia-smi field, prometheus name, help text, type)
_FIELDS = (
    ("utilization.gpu", "gpu_utilization_percent", "Загрузка вычислителя, %", "gauge"),
    ("utilization.memory", "gpu_memory_bandwidth_percent", "Загрузка шины памяти, %", "gauge"),
    ("memory.used", "gpu_memory_used_mib", "Занято видеопамяти, МиБ", "gauge"),
    ("memory.total", "gpu_memory_total_mib", "Всего видеопамяти, МиБ", "gauge"),
    ("temperature.gpu", "gpu_temperature_celsius", "Температура, °C", "gauge"),
    ("power.draw", "gpu_power_watts", "Потребление, Вт", "gauge"),
    ("power.limit", "gpu_power_limit_watts", "Предел потребления, Вт", "gauge"),
    ("clocks.sm", "gpu_clock_sm_mhz", "Частота SM, МГц", "gauge"),
)


def sample() -> str:
    """One scrape. Raises if nvidia-smi is unavailable — a metrics endpoint that
    invents zeros when the driver is gone reports a healthy idle card."""
    query = ",".join(["index", "name"] + [field for field, _, _, _ in _FIELDS])
    result = subprocess.run(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    out: list[str] = []
    for _, name, help_text, kind in _FIELDS:
        out.append(f"# HELP {name} {help_text}")
        out.append(f"# TYPE {name} {kind}")
    for line in lines:
        cells = [cell.strip() for cell in line.split(",")]
        index, model = cells[0], cells[1]
        for position, (_, name, _, _) in enumerate(_FIELDS, start=2):
            raw = cells[position] if position < len(cells) else ""
            try:
                value = float(raw)
            except ValueError:
                # [N/A] is what nvidia-smi returns for a field the card does not
                # report. Skipped rather than zeroed: a missing power limit is
                # not a power limit of zero watts.
                continue
            out.append(f'{name}{{gpu="{index}",model="{model}"}} {value}')
    return "\n".join(out) + "\n"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    api_key = ""

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send(self, code: int, body: str, content_type: str) -> None:
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:                      # noqa: N802
        if self.path.rstrip("/") == "/health":
            self._send(200, "ok\n", "text/plain; charset=utf-8")
            return
        if self.path.rstrip("/") != "/metrics":
            self._send(404, "no route\n", "text/plain; charset=utf-8")
            return
        presented = self.headers.get("Authorization", "")
        presented = presented[7:] if presented.lower().startswith("bearer ") else presented
        if self.api_key and presented.strip() != self.api_key:
            self._send(401, "api key required\n", "text/plain; charset=utf-8")
            return
        try:
            body = sample()
        except (subprocess.SubprocessError, OSError) as error:
            self._send(500, f"nvidia-smi недоступен: {error}\n",
                       "text/plain; charset=utf-8")
            return
        self._send(200, body, "text/plain; version=0.0.4; charset=utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9400)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()
    Handler.api_key = os.environ.get("SGLANG_API_KEY", "")
    if not Handler.api_key:
        print("SGLANG_API_KEY не задан — экспортёр будет открыт всем", file=sys.stderr)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"экспортёр железа на :{args.port}/metrics")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
