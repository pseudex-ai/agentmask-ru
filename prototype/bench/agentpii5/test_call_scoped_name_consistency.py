"""Одна персона → один подмен на всех хопах, когда имя разложено по формам.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_call_scoped_name_consistency

The long_order-003 regression: a person arrives as a 2-part mention in the
user's turn («ващенко таисия»), as three SEPARATE seed-card fields
(`last_name`/`first_name`/`middle_name`) in one tool result, and as the full
3-part «Ващенко Таисия Савельевна» in the `create_order` call and result.
Each form used to mint its own substitute, and the full name's patronymic was
drawn FRESH instead of reusing the card's — so the model's composition of the
card's parts («Устинова Ксения Игоревна») no longer equalled what the result
leg minted («Устинова Ксения Сергеевна»), and the production/scorer parity
gate blew up.

This test drives the production path (`envelope.mask_messages` + `MaskContext`)
in-process, no model, and pins the invariant on the NAME only: the substitute
for one person is one family/patronymic across every form, and a tool result
reuses the substitute its preceding call carried instead of re-minting.
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


def _forms(view: Vault) -> dict[str, str]:
    """shown substitute -> its real value, for the NAME rows only."""
    return {shown: original for shown, original, kind in view.shown_forms()
            if kind == "NAME" and shown != original}


def _substitute_for(forms: dict[str, str], original: str) -> str | None:
    """The substitute this conversation minted for a real NAME value, or None.

    Matches on the real value exactly — the card's fields and the message
    mention are the strings the engine recorded, so the test reads them back
    the way the harness does rather than searching the finished text."""
    folded = original.casefold()
    for shown, real in forms.items():
        if real == original or real.casefold() == folded:
            return shown
    return None


class _Session:
    """One masking session over an in-memory vault, mirroring the harness."""

    def __init__(self) -> None:
        self.detector = Detector()
        self.base = Vault(":memory:", "agentpii5-consistency")
        self.audit = AuditLog(":memory:")
        self.cache = MaskCache(1024)
        self.conversation = "conv-long_order-003"
        self.view = self.base.for_conversation(self.conversation)
        self.context = MaskContext(
            detector=self.detector, vault=self.view, audit=self.audit,
            cache=self.cache, org_id="agentpii5", agent_id="bench",
            conversation_id=self.conversation)
        self.transcript: list[dict[str, object]] = []

    def push(self, wire: dict[str, object]) -> dict[str, object]:
        """Append one wire message and re-mask the whole transcript."""
        self.transcript.append(dict(wire))
        masked = mask_messages([dict(m) for m in self.transcript], self.context, False)
        return masked[-1]

    def name_forms(self) -> dict[str, str]:
        return _forms(self.view)


def _drive_long_order(session: _Session) -> tuple[dict[str, str], str, str]:
    """The long_order-003 shape, returning the final name form table plus the
    call and result surfaces the model would read for the full name.

    Returns (forms, call_full_name, result_full_name) where the last two are
    the NAME strings standing in `recipient.name` of the create_order call and
    of its result after masking.
    """
    session.push({"role": "system", "content": "Ты оператор службы доставки."})
    session.push({"role": "user",
                  "content": "здрасье это ващенко таисия телефон +79276170654"})
    forms = session.name_forms()
    two_part = _substitute_for(forms, "ващенко таисия")
    phone = next((s for s, o, k in session.view.shown_forms()
                  if k == "PHONE" and s != o), None)
    assert two_part and phone, "маска не отчеканила подмену для имени/телефона"

    # 1) find the card by phone; the card answers name PARTS separately.
    session.push({"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "crm_find_contact",
         "arguments": json.dumps({"query": {"phone": phone}}, ensure_ascii=False)}}]})
    card = json.dumps({"contacts": [{"id": "c-1", "last_name": "ващенко",
                                     "first_name": "таисия", "middle_name": "савельевна",
                                     "phone": "+79276170654"}]}, ensure_ascii=False)
    session.push({"role": "tool", "tool_call_id": "c1", "name": "crm_find_contact",
                  "content": card})
    forms = session.name_forms()
    surname = _substitute_for(forms, "ващенко")
    given = _substitute_for(forms, "таисия")
    patronymic = _substitute_for(forms, "савельевна")

    # 2) the model composes the full name from the card's three parts.
    call_full = " ".join(word.capitalize() for word in (surname, given, patronymic))
    session.push({"role": "assistant", "content": "", "tool_calls": [
        {"id": "c2", "type": "function", "function": {"name": "delivery_create_order",
         "arguments": json.dumps({"recipient": {"name": call_full,
                                                "phones": [{"number": phone}]}},
                                 ensure_ascii=False)}}]})

    # 3) the tool echoes the REAL full name back.
    result = json.dumps({"uuid": "ord-1", "status": "ACCEPTED",
                         "recipient": {"name": "Ващенко Таисия Савельевна",
                                       "phone": "+79276170654"}},
                        ensure_ascii=False)
    masked = session.push({"role": "tool", "tool_call_id": "c2",
                           "name": "delivery_create_order", "content": result})
    result_body = json.loads(masked["content"])
    result_full = result_body["recipient"]["name"]
    return session.name_forms(), call_full, result_full


def _check_one_person() -> list[str]:
    failures: list[str] = []
    session = _Session()
    forms, call_full, result_full = _drive_long_order(session)

    surname = _substitute_for(forms, "ващенко") or ""
    given = _substitute_for(forms, "таисия") or ""
    patronymic = _substitute_for(forms, "савельевна") or ""
    two_part = _substitute_for(forms, "ващенко таисия") or ""

    # The seed-card's separate fields reuse the message mention's parts: the
    # surname and given name of the 2-part substitute, one word each.
    if two_part.split()[:1] != [surname]:
        failures.append(f"last_name {surname!r} != surname of {two_part!r}")
    if two_part.split()[1:2] != [given]:
        failures.append(f"first_name {given!r} != given name of {two_part!r}")

    # The full name the RESULT carried reuses the same surname and the SAME
    # patronymic the card minted — the regression minted a fresh patronymic.
    result_parts = result_full.split()
    if len(result_parts) != 3:
        failures.append(f"result full name {result_full!r} is not three words")
    elif result_parts[0].casefold() != surname.casefold():
        failures.append(f"result surname {result_parts[0]!r} != card {surname!r}")
    elif result_parts[2].casefold() != patronymic.casefold():
        failures.append(f"result patronymic {result_parts[2]!r} != card {patronymic!r}")

    # The result REUSES the substitute the call carried (same person, same
    # substitute), instead of re-minting: the model's composition and the
    # result surface must be one string, case aside.
    if call_full.casefold() != result_full.casefold():
        failures.append(f"call {call_full!r} != result {result_full!r}")

    # The substitute never shares a word with the real person.
    for fake in (surname, given, patronymic, two_part):
        if fake and fake.casefold() in {"ващенко", "таисия", "савельевна"}:
            failures.append(f"substitute {fake!r} leaks a real word")
    return failures


def _check_form_preserved() -> list[str]:
    """A declined / re-cased mention keeps its own form, not the minted one."""
    failures: list[str] = []
    session = _Session()
    session.push({"role": "system", "content": "sys"})
    # The customer writes the name in the DATIVE, lower-case — the substitute
    # must land in the same case and register, not the nominative the vault
    # stores.
    masked = session.push({"role": "user",
                           "content": "доставьте ващенко таисии на дом"})
    surface = session.name_forms()
    dative = next((s for s, o in surface.items() if o.casefold() == "ващенко таисии"), None)
    if dative is None:
        failures.append("dative mention minted nothing — detector missed the name")
    elif not dative.islower():
        failures.append(f"dative substitute {dative!r} lost the customer's lower case")
    elif dative == _substitute_for(surface, "ващенко таисия"):
        failures.append(f"dative substitute {dative!r} returned the nominative form")
    return failures


def _check_two_people() -> list[str]:
    """Two people in one case must not trade substitutes, including a 3-part
    person and a 2-part one (Ващенко + Мкртчян)."""
    failures: list[str] = []
    session = _Session()
    session.push({"role": "system", "content": "sys"})
    session.push({"role": "user",
                  "content": "отправитель ващенко таисия, получатель мкртчян ашот"})
    forms = session.name_forms()
    v = _substitute_for(forms, "ващенко таисия") or ""
    m = _substitute_for(forms, "мкртчян ашот") or ""
    if not v or not m:
        failures.append("two mentions did not both mint a substitute")
    elif v.split()[0].casefold() == m.split()[0].casefold():
        failures.append(f"two people share a surname substitute: {v!r} / {m!r}")
    return failures


def main() -> int:
    load_dev_bundle()
    failures: list[str] = []
    failures.extend(_check_one_person())
    failures.extend(_check_form_preserved())
    failures.extend(_check_two_people())
    if failures:
        for failure in failures:
            print("FAIL", failure)
        return 1
    print("call_scoped_name_consistency: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
