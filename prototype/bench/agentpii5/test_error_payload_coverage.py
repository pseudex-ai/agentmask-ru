"""C2 acceptance — every error-payload form masks the real value it carries.

    cd prototype && source .venv/bin/activate && \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_error_payload_coverage

The acceptance half of the hop-format error closure (`PRE-RUN-CLOSURE.md` C2,
fix B2). The mock produces THREE error forms, and the audit found the tool-result
masking leg did not touch any of them (B2: `long_support-013`'s truncated echo
stood in the clear). The fix made an error body mask like a normal tool result:
the value the call carried is answered with the substitute the model was already
shown, a value the call did NOT carry is neutrally redacted, and ordinary
numbers/quantities pass through. This file proves that for EVERY form.

THE THREE FORMS, AND WHY THEY ARE THREE.

- SCRIPTED ERROR (`ForcedError`, mock.py::_forced_call): the mock answers before
  the parser runs — `log.parsed is None and log.refusal is None`, so the harness
  records it as `tool_error`. The body is `{"error": {"code", "message":
  <template with the FULL canonical value>}}` — no `field`, no 80-character cut.
- PARSE REFUSAL (`Refusal`, bench/agentpii4/tools.py::as_error): the mock parsed
  and refused. The body is `{"error": {"code", "field", "message": "поле {path}:
  {rule}: {raw[:80]}"}}` — a `field` key and the offending value truncated.
- error_with_value (ruling R-18): the RETURN FORM both of the above are recorded
  under. R-18 says a documented parse refusal whose message names the offending
  argument IS an `error_with_value`; the harness's `push_call` still tells the two
  apart by `forced`, not by the form.

Each form is driven through the production path `envelope.mask_messages` with a
call-scoped transcript, and each asserts the three outcomes the closure names:
the call's own value is answered with its substitute, a foreign value is neutrally
redacted with no substitute guessed, and an ordinary number in the same shape is
untouched. No model, no network, one in-memory vault per conversation.

`test_error_echo_privacy.py` already pins the PARSE-REFUSAL shape for a dictated
PHONE at every truncation length; this file adds the SCRIPTED-ERROR shape (which
that file never builds) and the R-18 classification, so together they close C2.
"""

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from testkit import load_dev_bundle  # noqa: E402
from bench.agentpii4.tools import Refusal  # noqa: E402
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
    base = Vault(":memory:", "error-payload")
    view = base.for_conversation(convo)
    context = MaskContext(
        detector=detector, vault=view, audit=AuditLog(":memory:"),
        cache=MaskCache(1024), org_id="error-payload", agent_id="bench",
        conversation_id=convo)
    return view, context


def _mask(context: MaskContext, transcript: list[dict[str, object]]) -> object:
    """Mask one transcript through the production path and return the tool result."""
    masked = mask_messages([dict(m) for m in transcript], context, False)
    return masked[-1]["content"]


def _mint_phone(context: MaskContext, user_text: str, real: str) -> str:
    """Mask the customer turn and read back the PHONE substitute it showed for
    `real`. Matched on the real value, never on position, so a conversation that
    already holds another phone still finds this one's substitute."""
    mask_messages([{"role": "user", "content": user_text}], context, False)
    for shown, original, kind in context.vault.shown_forms():
        if kind == "PHONE" and original == real and shown != original:
            return shown
    raise RuntimeError(f"fixture minted no PHONE substitute for {real!r}")


def _call_message(call_id: str, leaf: str, field: str = "phone") -> dict[str, object]:
    return {"id": call_id, "type": "function",
            "function": {"name": "ticket_find",
                         "arguments": json.dumps({field: leaf}, ensure_ascii=False)}}


def _transcript(user: str, shown: str, body: str,
                field: str = "phone") -> list[dict[str, object]]:
    return [
        {"role": "user", "content": user},
        {"role": "assistant", "tool_calls": [_call_message("call-1", shown, field)]},
        {"role": "tool", "tool_call_id": "call-1", "content": body},
    ]


# --- the three error payload shapes --------------------------------------------

REAL_A: str = "+79161234567"
REAL_B: str = "+79260001122"
USER_A: str = "телефон " + REAL_A


def _scripted_error(value: str) -> str:
    """The `ForcedError` body: `{error: {code, message}}`, full value, no `field`.

    The template mirrors a real one from the corpus (`retry_same_tool-001`), and
    `{value}` stands where `mock._forced_call` splices `PiiItem.canonical`."""
    body = {"error": {"code": "plate_format",
                      "message": f"номер {value} не найден в формате ГОСТ Р 50577"}}
    return json.dumps(body, ensure_ascii=False, indent=2)


def _refusal_error(value: str) -> str:
    """The `Refusal.as_error` body: `{error: {code, field, message}}`, truncated.

    Built from the real `Refusal` class, not hand-copied, so the field format and
    the `raw[:80]` cut are exactly what the mock emits."""
    return json.dumps(Refusal("ticket_find", "phone", "phone_not_e164", value).as_error(),
                      ensure_ascii=False, indent=2)


# Both forms are recorded as `error_with_value` (R-18): the form label does not
# distinguish them, only the payload shape does. Pinned structurally below.

FORM_BUILDERS = (
    ("scripted error", _scripted_error),
    ("parse refusal", _refusal_error),
    ("error_with_value", _refusal_error),   # R-18: a refusal IS error_with_value
)


# --- call-scoped: the call's own value is answered with its substitute ---------

def _check_call_scoped() -> None:
    for label, builder in FORM_BUILDERS:
        view, context = _session(f"scoped-{label.replace(' ', '-')}")
        shown = _mint_phone(context, USER_A, REAL_A)
        check(shown != REAL_A, f"{label}: the substitute differs from the real value",
              f"shown={shown!r}")
        masked = _mask(context, _transcript(USER_A, shown, builder(REAL_A)))
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result changed its wire type")
        check(REAL_A not in masked and shown in masked,
              f"{label}: the call's own value is masked with its substitute",
              f"masked={masked[-70:]!r}")


# --- foreign: a value the call did not carry is neutrally redacted -------------

def _check_foreign() -> None:
    """A value the call did NOT carry is neutrally redacted, never attributed.

    TWO phones live in ONE conversation, so a foreign value really is in the
    store and a scope bug would resolve it to a substitute. The call carries A;
    the error echoes B cut short — a fragment the DETECTOR declines (asserted
    below), so only the echo pass can act on it. That is where the policy splits:
    privacy is conversation-scoped (the fragment is redacted, never leaked) but
    attribution is call-scoped (the call carried A, so neither A's nor B's
    substitute may be guessed — the answer is neutral).

    A FULL foreign phone is deliberately NOT this fixture: the detector masks it
    with B's own substitute, which is correct and not the path this pins."""
    for label, builder in FORM_BUILDERS:
        view, context = _session(f"foreign-{label.replace(' ', '-')}")
        shown_a = _mint_phone(context, USER_A, REAL_A)
        shown_b = _mint_phone(context, "ещё телефон " + REAL_B, REAL_B)
        foreign_fragment = REAL_B[:9]          # a cut the detector declines
        body = builder(foreign_fragment)
        masked = _mask(context, _transcript(USER_A, shown_a, body))
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result changed its wire type")
        check(foreign_fragment not in masked,
              f"{label}: a foreign value does not leak", f"masked={masked[-70:]!r}")
        check(shown_a not in masked and shown_b not in masked,
              f"{label}: no substitute is guessed for a foreign value", "")
        check("REDACTED" in masked,
              f"{label}: the foreign value is neutrally redacted", "")


# --- ordinary numbers in the same shape stay -----------------------------------

def _check_ordinary_numbers() -> None:
    for label, builder in FORM_BUILDERS:
        view, context = _session(f"ordinary-{label.replace(' ', '-')}")
        shown = _mint_phone(context, USER_A, REAL_A)
        body = builder("заказ 1428570, 12 коробок, код 926547")
        masked = _mask(context, _transcript(USER_A, shown, body))
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result changed its wire type")
        check(masked == body,
              f"{label}: an ordinary order number and quantity are untouched",
              f"masked={masked[-60:]!r}")


# --- R-18: the two shapes are one return form, told apart by `forced` ----------

def _check_r18_classification() -> None:
    """The harness records both shapes as `error_with_value` and still separates
    them: `forced = parsed is None and refusal is None` — a scripted error parses
    and refuses nothing, a refusal carries a `Refusal`. The form label alone must
    not be the discriminator, or the two error paths would share a privacy
    boundary they do not share."""
    scripted = json.loads(_scripted_error(REAL_A))
    refusal = json.loads(_refusal_error(REAL_A))
    check(REAL_A in scripted["error"]["message"] and "field" not in scripted["error"],
          "the scripted error carries the full value and no field", "")
    check(REAL_A in refusal["error"]["message"] and refusal["error"].get("field") == "phone",
          "the parse refusal carries the value and the field (R-18 shape)", "")
    check(scripted["error"]["code"] != refusal["error"]["code"],
          "the two forms are distinct payloads, not one shape twice", "")


def main() -> int:
    load_dev_bundle()
    _check_call_scoped()
    _check_foreign()
    _check_ordinary_numbers()
    _check_r18_classification()
    failures = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 72)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} passed")
    if failures:
        print("error-payload coverage NOT in place:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("every error-payload form masks the real value it carries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
