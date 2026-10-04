"""Layer-3 judge: attribute a divergence to the gateway or to model noise.

The deterministic `artifact_parity` flags every case where a substitute
survived in a durable write or the I arm did more of an action than both
controls. It CANNOT say WHY. This layer runs the LLM ONLY on those flags, blind
(I arm + both controls), and asks one question: «is this divergence caused by
the substitution, or is it the model's own random behaviour?» — with a verbatim
quote. Cheap because it runs on ~30-50 cases, not the whole corpus.

Uses the DeepSeek chat API directly (the agent connector's wire, no tools).
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
    "Ты разбираешь причину расхождения в прогоне агента. Ты получишь выдержки из "
    "трёх плеч одного кейса: I (движок подставлял фейки вместо ПД), C и C2 "
    "(контроли, ПД без подмен). ВАЖНО: все значения в выдержках УЖЕ ВОССТАНОВЛЕНЫ "
    "до настоящих — фейков там нет. Если модель пишет «адрес не совпал» или "
    "«указан X вместо Y», СВЕРЬ, правда ли X и Y различаются В ВОССТАНОВЛЕННОМ "
    "тексте. Если они ОДИНАКОВЫЕ (модель сама выдумала расхождение) — это "
    "«модель», а не «движок». Ответь ОДНИМ словом: «движок» — только если "
    "восстановленные значения РЕАЛЬНО разъехались (подмена не вернулась, или один "
    "адрес стал двумя), «модель» — если модель сама выдумала противоречие или это "
    "её случайный выбор, «оба», «неясно». Потом через «ЦИТАТА:» дай дословный "
    "кусок с причиной."
)


def prompt_for(case_id: str, i_text: str, c_text: str, c2_text: str) -> str:
    return (
        f"Кейс {case_id}\n"
        f"--- ПЛЕЧО I (с подменами) ---\n{i_text}\n"
        f"--- ПЛЕЧО C (контроль) ---\n{c_text}\n"
        f"--- ПЛЕЧО C2 (контроль) ---\n{c2_text}\n"
    )


def _artifacts_text(arms: dict, case_id: str) -> dict[str, str]:
    """The durable-write artifacts of each arm, as compact text."""
    out: dict[str, str] = {}
    for arm in ("I", "C", "C2"):
        d = arms.get((case_id, arm))
        if d is None:
            out[arm] = "(нет записи)"
            continue
        parts = []
        for call in d.get("calls", []):
            name = call.get("name", "")
            restored = call.get("restored") or {}
            residual = call.get("residual") or {}
            if name in ("crm_add_note", "notify_sms", "escalate_to_human", "ticket_create",
                        "crm_upsert_contact", "order_cancel", "order_reschedule",
                        "delivery_create_order", "clinic_book", "appointment_reschedule",
                        "payment_create", "referral_create"):
                parts.append(f"{name}: {json.dumps(restored, ensure_ascii=False)[:300]}"
                             + (f" residual={json.dumps(residual, ensure_ascii=False)}" if residual else ""))
        out[arm] = "\n".join(parts) if parts else "(нет долговечных записей)"
    return out


async def _ask(client: AsyncOpenAI, model: str, prompt: str) -> str:
    resp = await client.chat.completions.create(
        model=model, messages=[{"role": "system", "content": SYSTEM},
                               {"role": "user", "content": prompt}],
        temperature=0.0, max_tokens=300)
    return resp.choices[0].message.content or ""


async def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir")
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--base-url", default="https://api.deepseek.com")
    ap.add_argument("--limit", type=int, default=0, help="max cases (0 = all flags)")
    args = ap.parse_args(argv)
    run_dir = Path(args.run_dir)
    arms = load_arms(run_dir)
    purity = artifact_purity(arms)
    parity = behavioural_parity(arms)
    flagged: set[str] = {r["case_id"] for r in purity if r["durable"]}
    flagged |= {r["case_id"] for r in parity}
    flagged = sorted(flagged)
    if args.limit:
        flagged = flagged[:args.limit]
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("DEEPSEEK_API_KEY is not set", file=sys.stderr)
        return 2
    client = AsyncOpenAI(api_key=key, base_url=args.base_url)
    verdicts = []
    for case_id in flagged:
        texts = _artifacts_text(arms, case_id)
        prompt = prompt_for(case_id, texts["I"], texts["C"], texts["C2"])
        answer = await _ask(client, args.model, prompt)
        verdicts.append({"case_id": case_id, "answer": answer})
        print(f"{case_id}: {answer.splitlines()[0][:80]}")
    print(json.dumps(verdicts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
