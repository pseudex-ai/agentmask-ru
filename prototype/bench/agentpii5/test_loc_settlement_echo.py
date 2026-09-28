"""C1 privacy leg — a bare settlement in a tool result stays real.

    cd prototype && source .venv/bin/activate && \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_loc_settlement_echo

The over-masking half of the LOC closure. `test_loc_acceptance` pins the MASKING
leg: inside a full address the settlement is kept real while the street, house and
flat are faked. This file pins the PRIVACY leg — `_replace_echoes`'s `recorded`
branch: when a tool result echoes ONLY the settlement of an address the
conversation recorded (`{"city": "сортавала"}` for a recorded «сортавала переулок
мончегорская 10»), the neutral redaction must NOT touch it. A city identifies
nobody (`vault._settlement_of`: «what the law does not protect stays true»), and
hiding it here broke a live run — the scorer kept «сортавала» real while the
production privacy leg wrote `"city": "REDACTED…"`, so the model and the tool
disagreed about the place.

WHY THE ECHO LEG FIRES AT ALL, AND WHY IT MUST NOT HERE. The conversation recorded
the WHOLE address, and `_literal_echo_spans` matches a leading part of it — the
bare settlement is a prefix of the address, so it reads as a cut and is answered
with `_neutral_redaction`. That is correct for a cut of the street or the house
(still personal data) and wrong for the settlement alone (not personal data). The
fix skips an echo span equal to ONLY the settlement, both read to the nominative
so a settlement the dialogue recorded in an oblique case («сортавале…») is
recognised. The full address and the street+house stay masked — the street NAME is
the canary, since a fake street must never equal the real one.

No model, no network, one in-memory vault per conversation, driven through the
production path `envelope.mask_messages`.
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from testkit import load_dev_bundle  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _session(convo: str) -> tuple[Vault, MaskContext]:
    """One conversation view over one tenant store, the production shape."""
    detector = Detector()
    base = Vault(":memory:", "loc-settlement")
    view = base.for_conversation(convo)
    context = MaskContext(
        detector=detector, vault=view, audit=AuditLog(":memory:"),
        cache=MaskCache(1024), org_id="loc-settlement", agent_id="bench",
        conversation_id=convo)
    return view, context


def _call_message(call_id: str) -> dict[str, object]:
    return {"id": call_id, "type": "function",
            "function": {"name": "ticket_find", "arguments": "{}"}}


def _result(context: MaskContext, user_text: str, body: str) -> str:
    """Mask a transcript whose last message is a tool result `body`; return it.

    The result carries a call with empty arguments, so the bound leg has nothing
    of its own to echo and the conservative `recorded` leg is the only one that
    can act on the settlement — the exact leg the live run tripped over. The user
    turn is replayed so the transcript is a realistic accumulated one; it re-mints
    nothing, the address was recorded by the earlier `_record` turn."""
    masked = mask_messages([
        {"role": "user", "content": user_text},
        {"role": "assistant", "tool_calls": [_call_message("call-1")]},
        {"role": "tool", "tool_call_id": "call-1", "content": body},
    ], context, False)
    result = masked[-1]["content"]
    assert isinstance(result, str), "tool result changed its wire type"
    return result


def _record(context: MaskContext, address: str) -> str:
    """Mask one user turn carrying `address`; returns the masked content.

    This is what mints the LOC row the privacy leg then reads back. It runs in a
    SEPARATE `mask_messages` call because the provenance snapshot is frozen before
    a pass masks anything — a value spoken in the SAME transcript as the result is
    not yet recorded when the result is masked (the live failure is a later turn)."""
    masked = mask_messages([{"role": "user", "content": "адрес: " + address}],
                           context, False)[0]["content"]
    assert isinstance(masked, str)
    return masked


REAL_ADDR: str = "сортавала переулок мончегорская 10"


# --- the bare settlement stays real ---------------------------------------------

def _check_bare_settlement() -> None:
    """`{"city": "сортавала"}` stays `сортавала`, not a neutral redaction."""
    _, context = _session("bare")
    _record(context, REAL_ADDR)
    body = json.dumps({"city": "сортавала"}, ensure_ascii=False)
    masked = _result(context, "адрес: " + REAL_ADDR, body)
    check("сортавала" in masked,
          "the bare settlement stays real",
          f"masked={masked!r}")
    check("REDACTED" not in masked,
          "no neutral redaction of the bare settlement",
          f"masked={masked!r}")


# --- the protected part of the address stays masked -----------------------------

def _check_full_address() -> None:
    """The full address is still masked; only the settlement inside it stays real."""
    _, context = _session("full")
    _record(context, REAL_ADDR)
    body = json.dumps({"address": REAL_ADDR}, ensure_ascii=False)
    masked = _result(context, "адрес: " + REAL_ADDR, body)
    check("мончегорская" not in masked.casefold(),
          "the street name inside the full address is still faked",
          f"masked={masked!r}")
    check("сортавала" in masked,
          "the settlement inside the full address stays real",
          f"masked={masked!r}")


def _check_street_house() -> None:
    """The street+house of the recorded address is still masked on its own."""
    _, context = _session("street-house")
    _record(context, REAL_ADDR)
    body = json.dumps({"street": "переулок мончегорская 10"}, ensure_ascii=False)
    masked = _result(context, "адрес: " + REAL_ADDR, body)
    check("мончегорская" not in masked.casefold(),
          "the street name of the street+house echo is still faked",
          f"masked={masked!r}")


# --- the settlement written in an oblique case -----------------------------------

def _check_oblique_settlement() -> None:
    """A settlement the dialogue recorded in an oblique case stays real.

    `split_roles` returns the city exactly as written — «сортавале» in the
    dative — and `_settlement_of` reads it to the nominative «Сортавала». The echo
    span is the same oblique surface, so it must be recognised as the settlement
    too; a casefold against the raw written form would miss it and the city would
    still be redacted."""
    _, context = _session("oblique")
    oblique_addr = "сортавале переулок мончегорская 10"
    _record(context, oblique_addr)
    body = json.dumps({"city": "сортавале"}, ensure_ascii=False)
    masked = _result(context, "адрес: " + oblique_addr, body)
    check("сортавале" in masked,
          "the obliquely written settlement stays real",
          f"masked={masked!r}")
    check("REDACTED" not in masked,
          "no neutral redaction of the obliquely written settlement",
          f"masked={masked!r}")


def main() -> int:
    load_dev_bundle()
    _check_bare_settlement()
    _check_full_address()
    _check_street_house()
    _check_oblique_settlement()
    failures = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 72)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} passed")
    if failures:
        print("LOC settlement privacy NOT in place:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("LOC settlement privacy: the bare settlement stays real, the address stays masked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
