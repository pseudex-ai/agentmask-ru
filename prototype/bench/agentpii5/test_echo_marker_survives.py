"""E01 precedence — a reserved-echo marker is not absorbed by structured-KV.

    cd prototype && source .venv/bin/activate && \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_echo_marker_survives

The long_order-002 regression, the `recipient.phone` half. `_reserve_echoes`
lifts a bound call's own echo off the result text BEFORE detection and marks the
span with a NUL-delimited nonce (`\\x00EO{nonce}:{index}\\x01`), chosen absent
from the raw text. The marker is invisible to the recognizers — but NOT to the
structured-KV layer, which types a WHOLE value by its key: a marker standing in a
numeric key's value (`"phone": "\\x00EO0:0\\x01"`) carries the nonce/index DIGITS,
so `detect_structured_kv` keeps it PHONE (the numeric demotion only fires when the
value has NO digit) and `_mask_one` mints a fresh phone OVER the reservation. The
echo leg then re-uses that fresh mint instead of the call's substitute, and
production and the scorer (`score._mask_message`, which resolves the real phone to
the SAME vault token) read two different numbers in one request — the byte
divergence that excluded the arm.

WHY THE MARKER MUST WIN OVER THE KEY. The call's evidence is not a guess about
the text; the reservation is the whole point of the E01 precedence. A key that
types its value may not type a value WE inserted as a placeholder, or the
reservation is silently lost and the model sees a substitute nobody showed it.

No model, no network, one in-memory vault per conversation, driven through the
production path `envelope.mask_messages` and compared against the scorer the
harness's parity gate uses.
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from testkit import load_dev_bundle  # noqa: E402
from bench.agentpii3 import score  # noqa: E402
from pseudex import morph_places  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault, canonicalize  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _session(convo: str) -> tuple[Vault, MaskContext, Detector]:
    detector = Detector()
    base = Vault(":memory:", "echo-marker")
    view = base.for_conversation(convo)
    context = MaskContext(
        detector=detector, vault=view, audit=AuditLog(":memory:"),
        cache=MaskCache(1024), org_id="echo-marker", agent_id="bench",
        conversation_id=convo)
    return view, context, detector


def _substitute(view: Vault, real: str) -> str:
    folded = real.casefold()
    for shown, original, _kind in view.shown_forms():
        if shown != original and (original == real or original.casefold() == folded):
            return shown
    raise AssertionError(f"no substitute minted for {real!r}")


def _title(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split())


def _address_parts(view: Vault) -> tuple[str, str]:
    """(city, «улица … д. … кв. …») from the ONE composite LOC substitute.

    «одоев улица солнечная 104 квартира 203» masks as ONE address now — the
    settlement stays real and the street+house+flat are faked (the long_order-*
    city-vs-surname closure). The roles are read through `split_roles`, never a
    substring hunt, exactly as `test_loc_acceptance` does."""
    full_sub = _substitute(view, "одоев улица солнечная 104 квартира 203")
    roles = morph_places.split_roles(full_sub)
    street_name = " ".join(word for word in roles["street"].split()
                           if not morph_places.is_generic_word(word))
    address = f"улица {street_name.capitalize()}, д. {roles['house']}, кв. {roles['flat']}"
    return roles["city"], address


def _drive(view: Vault, context: MaskContext, detector: Detector) -> tuple[str, str, str]:
    """Drive the create_order shape; return (production, scorer, phone-E164)."""
    transcript: list[dict[str, object]] = []

    def push(wire: dict[str, object]) -> dict[str, object]:
        transcript.append(dict(wire))
        return mask_messages([dict(m) for m in transcript], context, False)[-1]

    push({"role": "system", "content": "Ты оператор службы доставки."})
    push({"role": "user", "content": "везите на одоев улица солнечная 104 квартира 203"})
    push({"role": "user", "content": "ой получать будет мкртчян ашот его телефон 8-950-840-78-56"})

    city_sub, addr_reformatted = _address_parts(view)
    name_sub = _substitute(view, "мкртчян ашот")
    phone_sub = next(shown for shown, original, kind in view.shown_forms()
                     if kind == "PHONE" and shown != original and "950" in original)
    phone_e164 = canonicalize("PHONE", phone_sub)  # the form the schema demands

    call = {"recipient": {"name": _title(name_sub), "phones": [{"number": phone_e164}]},
            "to_location": {"postal_code": "301440", "city": _title(city_sub),
                            "address": addr_reformatted},
            "packages": [{"weight": 3000}]}
    push({"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {
            "name": "delivery_create_order",
            "arguments": json.dumps(call, ensure_ascii=False)}}]})

    result = json.dumps({
        "uuid": "ord-1", "status": "ACCEPTED",
        "recipient": {"name": "Мкртчян Ашот", "phone": "+79508407856"},
        "to_location": {"postal_code": "301440", "city": "одоев",
                        "address": "улица Солнечная, д. 104, кв. 203"}},
        ensure_ascii=False, indent=2)
    masked = push({"role": "tool", "tool_call_id": "c1",
                   "name": "delivery_create_order", "content": result})
    prod = masked["content"]
    assert isinstance(prod, str)
    observed = score._mask_message(result, detector, view)
    return prod, observed.masked, phone_e164


def _check_phone_marker_survives() -> None:
    """The reserved phone echo is the call's substitute, not a fresh mint."""
    view, context, detector = _session("phone")
    prod, observed, phone_e164 = _drive(view, context, detector)
    body = json.loads(prod)
    phone = body["recipient"]["phone"]
    check(phone == phone_e164,
          "the reserved phone echo under a numeric key is the call's substitute",
          f"phone={phone!r} want={phone_e164!r}")
    check(json.loads(observed)["recipient"]["phone"] == phone,
          "production and the scorer agree on the reserved phone",
          f"prod={phone!r} scorer={json.loads(observed)['recipient']['phone']!r}")


def main() -> int:
    load_dev_bundle()
    _check_phone_marker_survives()
    failures = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 72)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} passed")
    if failures:
        print("reserved-echo marker precedence NOT in place:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("reserved-echo marker survives structured-KV; the call's substitute wins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
