"""How much latency the gateway itself adds, per hop, with raw samples.

Not a benchmark of the model: it times ONLY the calls the gateway makes on the
customer's path — `/mask` before the provider and `/unmask_arguments` on the tool
hop — so the number is the ADDED cost, not the model's. Raw samples are saved;
percentiles are computed from them, never typed by hand.
"""

import json
import os
import time
import urllib.request
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
STATE = HERE / ".state"
OUT = STATE / "qa" / "latency"
API = "http://127.0.0.1:18862"

TOKENS = STATE / "sidecar.env"


def gateway_token() -> str:
    for line in TOKENS.read_text().splitlines():
        if line.startswith("PSEUDEX_GATEWAY_TOKEN="):
            return line.split("=", 1)[1]
    raise SystemExit("gateway token missing")


def post(path: str, body: dict, headers: dict) -> tuple[dict, float]:
    request = urllib.request.Request(
        API + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode())
    return payload, (time.perf_counter() - started) * 1000.0


def pct(samples: list[float], q: float) -> float:
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, round(q / 100 * (len(ordered) - 1))))
    return ordered[index]


def measure(fn, iterations: int) -> dict:
    samples: list[float] = []
    for _ in range(iterations):
        _, elapsed = fn()
        samples.append(elapsed)
    return {"n": len(samples), "mean": round(mean(samples), 2),
            "p50": round(pct(samples, 50), 2), "p95": round(pct(samples, 95), 2),
            "p99": round(pct(samples, 99), 2), "samples": [round(x, 2) for x in samples]}


PII = ("Меня зовут Иванова Анна Сергеевна, телефон +7 916 123-45-67, "
       "email a.ivanova@example.ru, адрес Москва, ул. Ленина 14, кв. 5.")


def conversation(turns: int) -> list[dict]:
    messages = [{"role": "system", "content": "Ты ассистент локального стенда."}]
    for index in range(turns):
        messages.append({"role": "user", "content": f"Шаг {index + 1}. {PII}"})
        messages.append({"role": "assistant", "content": "Принято, проверяю данные."})
    messages.append({"role": "user", "content": PII})
    return messages


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    token = gateway_token()
    headers = {"Authorization": f"Bearer {token}"}
    org = {"org_id": "doubleup-pilot", "conversation_id": "qa-latency"}
    case = {"model": "pilot/deepseek-v4-flash",
            "messages": [{"role": "user", "content": PII}]}
    for _ in range(5):  # warm the lease, caches and DB handles
        post("/mask", {**org, **case}, headers)

    out: dict = {"api": API, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                 "mask": {}, "unmask_arguments": {}}
    for turns in (1, 5, 10, 20):
        body = {**org, "conversation_id": f"qa-latency-{turns}", "messages": conversation(turns)}
        out["mask"][f"turns_{turns}"] = measure(lambda b=body: post("/mask", b, headers), 30)

    # A realistic tool hop: mask an argument payload, then unmask the shown values.
    arguments = {"query": PII, "contact": "Иванова Анна Сергеевна",
                 "street": "Москва, ул. Ленина 14, кв. 5"}
    masked, _ = post("/mask", {**org, "conversation_id": "qa-latency-tool",
                               "messages": [{"role": "user", "content": PII}]}, headers)
    shown = masked["messages"][0]["content"]
    tool_body = {**org, "conversation_id": "qa-latency-tool",
                 "arguments": [json.dumps({"query": shown, "contact": "Иванова Анна Сергеевна",
                                           "street": shown}, ensure_ascii=False)]}
    out["unmask_arguments"]["one_tool_call"] = measure(
        lambda: post("/unmask_arguments", tool_body, headers), 40)
    # Bigger tool result: ten arguments strings, as a multi-call turn produces.
    big = {**org, "conversation_id": "qa-latency-tool",
           "arguments": [json.dumps({"query": shown, "contact": "Иванова Анна Сергеевна",
                                     "street": shown}, ensure_ascii=False)
                         for _ in range(10)]}
    out["unmask_arguments"]["ten_tool_calls"] = measure(
        lambda: post("/unmask_arguments", big, headers), 30)

    # The model turn itself, from the pilot's own metrics, for the added share.
    import subprocess
    try:
        script = ('const rows=db.turn_metrics.find({}).sort({_id:-1}).limit(20).toArray();'
                  'print(JSON.stringify(rows.map(r=>({latency_ms:r.latency_ms,'
                  'stage_ms:r.stage_ms, graph_id:r.graph_id}))))')
        raw = subprocess.run(
            ["docker", "exec", "obscura-doubleup-pilot-mongodb-1", "mongosh",
             "doubleup_pilot", "--quiet", "--eval", script],
            capture_output=True, text=True, timeout=60, check=False)
        rows = [line for line in (raw.stdout or "").splitlines() if line.startswith("[")]
        out["model_turns"] = json.loads(rows[-1]) if rows else []
    except Exception as error:  # noqa: BLE001
        out["model_turns_error"] = str(error)

    (OUT / "latency.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    lines = ["# Латентность, которую добавляет Pseudex", "",
             "Замер только наших вызовов на пути запроса (`/mask`, `/unmask_arguments`),",
             "без времени модели. Сырые сэмплы — `latency.json`.", "",
             "| операция | n | p50, ms | p95, ms | p99, ms | mean, ms |",
             "|---|---|---|---|---|---|"]
    for name, row in out["mask"].items():
        lines.append(f"| /mask, {name} | {row['n']} | {row['p50']} | {row['p95']} | {row['p99']} | {row['mean']} |")
    for name, row in out["unmask_arguments"].items():
        lines.append(f"| /unmask_arguments, {name} | {row['n']} | {row['p50']} | {row['p95']} | {row['p99']} | {row['mean']} |")
    by_turn = out["mask"]["turns_1"]["p50"] + out["unmask_arguments"]["one_tool_call"]["p50"]
    lines += ["", f"**Добавка на один ход (p50, mask + один tool-hop): {by_turn:.1f} ms**"]
    if out.get("model_turns"):
        model_p50 = pct([row["latency_ms"] for row in out["model_turns"]], 50)
        lines.append(f"Медианный ход модели по `turn_metrics`: {model_p50:.0f} ms → "
                     f"наша добавка ≈ {by_turn / model_p50 * 100:.2f}% от хода.")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
