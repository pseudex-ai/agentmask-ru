"""The calibrated judge: does the gateway break or affect the agent, and HOW.

The deterministic `artifact_parity` gives the objective anchor — a fake that
reached a DURABLE write is a definitive engine break. This layer runs the LLM
ONLY on the flagged cases (durable residual + behavioural parity), blind across
I/C/C2, and returns a STRUCTURED verdict: the effect, the cause, the impact and
a verbatim quote. The structured schema is what makes it calibratable — every
verdict names a cause, so agreement with the objective anchor can be measured
and the prompt can be fixed on the disagreements.

Uses the DeepSeek chat API (the agent connector's wire, no tools).
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from openai import AsyncOpenAI

from bench.agentpii5.artifact_parity import (artifact_purity, behavioural_parity, load_arms)

SYSTEM = (
    "Ты — судья качества обезличивания агента. Тебе даны выдержки трёх плеч одного "
    "кейса: I (движок подставлял фейки вместо ПД), C и C2 (контроли, ПД без подмен). "
    "ВСЕ значения в выдержках УЖЕ ВОССТАНОВЛЕНЫ до настоящих — фейков там нет.\n"
    "Определи, как подмена повлияла на работу агента, и ответь СТРОГО одним JSON-объектом "
    "без пояснений:\n"
    '{"verdict":"<engine_broke|engine_affected|model_noise|neutral|both|unclear>",'
    '"reason":"<substitute_unresolved|phantom_mismatch|wrong_type|wrong_value|over_masked|'
    'date_shifted|model_hallucination|legitimate_variation|none>",'
    '"impact":"<none|minor|major>",'
    '"evidence":"<дословная цитата из выдержек>"}\n\n'
    "Правила определения (СВЕРЯЙСЯ с восстановленными данными, а не с жалобой агента):\n"
    "- substitute_unresolved: в выдержке I остался фейк (поле `residual` непусто) — это ПРОБОЙ, verdict=engine_broke.\n"
    "- phantom_mismatch: агент пишет «не совпадают», НО в восстановленных данных значения ОДИНАКОВЫЕ → агент сам выдумал противоречие, verdict=model_noise (НЕ engine_broke!).\n"
    "- wrong_type/wrong_value: восстановленное значение отличается по ТИПУ/значению от того, что писал клиент (ул. вместо переулок) → verdict=engine_broke.\n"
    "- over_masked: замаскировано не-ПД (операционная дата, номер заказа) → verdict=engine_broke или engine_affected.\n"
    "- date_shifted: операционная дата/слот сдвинулась из-за маски → verdict=engine_affected.\n"
    "- model_hallucination: агент сам выдумал противоречие → verdict=model_noise.\n"
    "- legitimate_variation: агент сделал законное действие (смена получателя), не из-за подмены → verdict=model_noise.\n"
    "- none: расхождения нет → verdict=neutral.\n"
    "Ключ: phantom_mismatch и model_hallucination — это model_noise, НЕ engine_broke, потому что движок "
    "восстановил корректно, а противоречие выдумал агент. engine_broke — только когда движок реально "
    "отдал фейк (residual) или исказил значение (wrong_type/wrong_value)."
)


def _arm_artifacts(d: dict) -> str:
    parts = []
    for call in d.get("calls", [])[:20]:
        restored = call.get("restored") or {}
        residual = call.get("residual") or {}
        text = json.dumps(restored, ensure_ascii=False)[:400]
        if residual:
            text += f" residual={json.dumps(residual, ensure_ascii=False)}"
        parts.append(f"{call.get('name')}: {text}")
    return "\n".join(parts) if parts else "(нет вызовов)"


def _deterministic_labels(arms: dict, case_id: str) -> dict:
    durable = [r for r in artifact_purity(arms) if r["case_id"] == case_id and r["durable"]]
    readonly = [r for r in artifact_purity(arms) if r["case_id"] == case_id and not r["durable"]]
    parity = [r for r in behavioural_parity(arms) if r["case_id"] == case_id]
    return {"durable": durable, "readonly": readonly, "parity": parity}


async def _ask(client: AsyncOpenAI, model: str, prompt: str) -> str:
    # deepseek-flash is a REASONING model: it needs `reasoning.effort` and a
    # large enough `max_output_tokens` (reasoning consumes output budget before
    # the text), otherwise `output_text` is empty. Use the RESPONSES API the same
    # way the agent connector does.
    for _ in range(3):
        resp = await client.responses.create(
            model=model,
            instructions=SYSTEM,
            input=[{"role": "user", "content": prompt}],
            reasoning={"effort": "low"},
            max_output_tokens=8000,
            store=False,
        )
        text = resp.output_text or ""
        if text.strip():
            return text
    return ""


def _parse(answer: str) -> dict:
    m = answer.find("{")
    n = answer.rfind("}")
    try:
        return json.loads(answer[m:n + 1])
    except Exception:
        return {"verdict": "unclear", "reason": "none", "impact": "none", "evidence": answer[:200]}


async def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir")
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--base-url", default="https://api.deepseek.com")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    arms = load_arms(Path(args.run_dir))
    flags = artifact_purity(arms) + behavioural_parity(arms)
    case_ids = sorted({r["case_id"] for r in flags})
    if args.limit:
        case_ids = case_ids[:args.limit]
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("DEEPSEEK_API_KEY is not set", file=sys.stderr)
        return 2
    client = AsyncOpenAI(api_key=key, base_url=args.base_url)

    async def one(case_id: str) -> dict:
        i = arms.get((case_id, "I"))
        c = arms.get((case_id, "C"))
        c2 = arms.get((case_id, "C2"))
        det = _deterministic_labels(arms, case_id)
        if not (i and c and c2):
            return {"case_id": case_id, "verdict": "unclear", "reason": "none",
                    "impact": "none", "evidence": "(нет плеч)", "deterministic": det}
        facts = (f"ДЕТЕРМИНИРОВАННЫЕ ФАКТЫ (проверено движком, не оспаривай):\n"
                 f"  durable residual = {[(r['call'], r['leak_type'], r['leak']) for r in det['durable']]}\n"
                 f"  readonly residual = {[(r['call'], r['leak_type'], r['leak']) for r in det['readonly']]}\n"
                 f"  behavioural parity = {[(r['tool'], r['I'], r['C'], r['C2']) for r in det['parity']]}\n")
        prompt = (f"Кейс {case_id}\n{facts}"
                  f"--- I ---\n{_arm_artifacts(i)}\n"
                  f"--- C ---\n{_arm_artifacts(c)}\n--- C2 ---\n{_arm_artifacts(c2)}\n")
        answer = await _ask(client, args.model, prompt)
        verdict = _parse(answer)
        verdict["case_id"] = case_id
        verdict["deterministic"] = det
        if not args.json:
            print(f"{case_id}: {verdict['verdict']}/{verdict['reason']} "
                  f"dur={len(det['durable'])} par={len(det['parity'])}")
        return verdict

    sem = asyncio.Semaphore(args.concurrency)

    async def bounded(case_id: str) -> dict:
        async with sem:
            return await one(case_id)

    rows = await asyncio.gather(*(bounded(cid) for cid in case_ids))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
