"""Deterministic judge: does the gateway pollute artifacts or change agent behaviour?

The paid LLM judge answers four questions about the FINAL ANSWER TEXT. It never
looks at the tool calls, so «correct_but_bad_artifacts» — an order created
correctly while a fake name/address/date survives in the CRM note, SMS or
escalation summary — scores as success. This module closes that gap DETERMINISTICALLY
from data the run already recorded, before any model is asked for an opinion.

TWO LAYERS, both free:

  artifact purity   — every durable write (note, SMS, escalation, ticket, upsert,
                      cancel/reschedule reason, order recipient/location, clinic
                      slot/patient) whose `residual` still carries a PII-SHAPED
                      string. Technical ids (`c-1`, `t-1`, `ord-1`, bare digits)
                      are NOT PII and are dropped; the residual value is run back
                      through the engine's own Detector, so «what leaked» is typed
                      by the same recogniser that should have caught it.

  behavioural parity — the action sequence of the I arm against BOTH controls:
                      an arm that cancels/recreates/extra-looks while neither
                      control does is the gateway confusing the agent, not the
                      model's own habit.

A divergence HERE is a signal to spend a judge call on attribution, not to score
every case. It never edits the run: read-only over the arm records.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

# Tools whose WRITE becomes a durable artifact a customer keeps reading. A fake
# surviving in one of these is persistent harm; a fake in a read-only search is
# a wrong lookup, still reported but under a separate bucket.
DURABLE_WRITE_TOOLS: frozenset[str] = frozenset({
    "crm_add_note", "notify_sms", "escalate_to_human", "ticket_create",
    "crm_upsert_contact", "order_cancel", "order_reschedule",
    "delivery_create_order", "clinic_book", "appointment_reschedule",
    "payment_create", "referral_create",
})

# Actions whose COUNT matters for behavioural parity. A divergence in these is
# «the gateway made the agent do extra/different work».
ACTION_TOOLS: tuple[str, ...] = (
    "delivery_create_order", "order_cancel", "order_reschedule",
    "clinic_book", "appointment_reschedule", "payment_create", "referral_create",
)


def _residual_leaves(residual: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Flatten `residual` {field: [values]} to [(field, value), ...]."""
    out: list[tuple[str, str]] = []
    for field, values in (residual or {}).items():
        for value in values or []:
            out.append((field, str(value)))
    return out


def _is_technical_id(value: str) -> bool:
    """Technical ids the residual detector flags but that are not PII."""
    v = value.strip()
    if not v:
        return True
    if v.isdigit():
        return True
    if v in ("true", "false", "None"):
        return True
    # c-1, t-1, ord-2, appt-3 — the mock backend's own keys
    if len(v) <= 6 and any(v.startswith(p) for p in ("c-", "t-", "ord-", "appt-", "ord", "appt")):
        return True
    return False


_PHONE_SHAPE = re.compile(r"^\+?\d[\d\s\-()]{5,}$")
_DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}")
# Cyrillic personal-name shape: one or more capitalised words, no digits. Only
# a guess — the run record does not carry the residual's type, and this module
# must NOT import the engine (`PSEUDEX_ALLOWED_MODULES`), so the type is inferred
# from shape, never from the recogniser that minted it.
_NAME_SHAPE = re.compile(r"^[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*$")


def _typed_leak(value: str) -> tuple[str, str] | None:
    """(type, value) if the surviving string is itself PII-shaped, else None.

    A residual that is NOT a technical id is, by the field's own contract, a
    substitute that reached the tool. The type is inferred from shape only, so
    this instrument stays engine-independent and can judge the engine from
    outside; a residual the shapes do not name is still a leak and is reported
    as SUBSTITUTE, never dropped.
    """
    v = value.strip()
    if _is_technical_id(v):
        return None
    if _PHONE_SHAPE.match(v):
        return ("PHONE", value)
    if _DATE_SHAPE.match(v):
        return ("DATE", value)
    if _NAME_SHAPE.match(v):
        return ("NAME", value)
    return ("SUBSTITUTE", value)


def load_arms(run_dir: Path) -> dict[tuple[str, str], dict]:
    arms: dict[tuple[str, str], dict] = {}
    for path in sorted(run_dir.glob("*.arms.jsonl")):
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            arms[(d["case_id"], d["arm"])] = d
    return arms


def artifact_purity(arms: dict) -> list[dict]:
    rows: list[dict] = []
    for (case_id, arm), d in arms.items():
        if arm != "I":
            continue
        for call in d.get("calls", []):
            residual = call.get("residual") or {}
            if not residual:
                continue
            durable = call["name"] in DURABLE_WRITE_TOOLS
            for field, value in _residual_leaves(residual):
                typed = _typed_leak(value)
                if typed is None:
                    continue
                rows.append({
                    "case_id": case_id, "call": call["name"], "field": field,
                    "leak_type": typed[0], "leak": typed[1], "durable": durable,
                })
    return rows


def behavioural_parity(arms: dict) -> list[dict]:
    rows: list[dict] = []
    for (case_id, arm), d in arms.items():
        if arm != "I":
            continue
        c = arms.get((case_id, "C"))
        c2 = arms.get((case_id, "C2"))
        if not (c and c2):
            continue
        i_counts = collections.Counter(x["name"] for x in d.get("calls", []))
        c_counts = collections.Counter(x["name"] for x in c.get("calls", []))
        c2_counts = collections.Counter(x["name"] for x in c2.get("calls", []))
        for tool in ACTION_TOOLS:
            i_n = i_counts.get(tool, 0)
            control_max = max(c_counts.get(tool, 0), c2_counts.get(tool, 0))
            if i_n > control_max:
                rows.append({
                    "case_id": case_id, "tool": tool,
                    "I": i_n, "C": c_counts.get(tool, 0), "C2": c2_counts.get(tool, 0),
                })
    return rows


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", help="a run directory holding *.arms.jsonl")
    ap.add_argument("--json", action="store_true", help="emit one JSON object")
    args = ap.parse_args(argv)
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"no such run dir: {run_dir}", file=sys.stderr)
        return 2
    arms = load_arms(run_dir)
    purity = artifact_purity(arms)
    parity = behavioural_parity(arms)

    durable = [r for r in purity if r["durable"]]
    readonly = [r for r in purity if not r["durable"]]
    if args.json:
        print(json.dumps({
            "artifact_purity": {
                "durable_violations": durable,
                "readonly_violations": readonly,
            },
            "behavioural_parity": parity,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"run: {run_dir}")
    print(f"\n== ARTIFACT PURITY — durable writes carrying a PII-shaped residual: {len(durable)} ==")
    for r in durable:
        print(f"  {r['case_id']:20} {r['call']:24} {r['field']:18} {r['leak_type']:6} {r['leak']!r}")
    print(f"\n== ARTIFACT PURITY — read-only calls carrying a PII-shaped residual: {len(readonly)} ==")
    for r in readonly:
        print(f"  {r['case_id']:20} {r['call']:24} {r['field']:18} {r['leak_type']:6} {r['leak']!r}")
    print(f"\n== BEHAVIOURAL PARITY — I does more of an action than BOTH controls: {len(parity)} ==")
    for r in parity:
        print(f"  {r['case_id']:20} {r['tool']:24} I={r['I']} C={r['C']} C2={r['C2']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
