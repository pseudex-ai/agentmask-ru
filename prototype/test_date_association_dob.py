"""A DATE THAT IS PERSONAL ONLY BY ASSOCIATION MUST BE TYPED DOB, NOT DATE.

The residual leak the hop-format audit left open. A bare numeric date is not
personal data on its own — a meeting, invoice or delivery date — so the deny
layer (`context._date_is_personal`) suppresses it unless a birth cue or a subject
identifier is beside it. When it IS personal by ASSOCIATION (next to a СНИЛС, a
card, a passport), the layer KEEPS the span but left its type as `DATE`.

That type is what leaks. The previous parity fix excluded `DATE` from the
envelope's neutral echo leg (`_replace_echoes`) so a meeting date next to a
doctor's name stays real — correct for a meeting, and wrong for a date of birth
whose only evidence is the identifier beside it. The date `21.01.1979` in
«Реквизиты: СНИЛС …, карта …, дата 21.01.1979» is typed `DATE`, so an unbound
tool result echoing `{"date": "21.01.1979"}` reaches the model in the clear
(earlier it was cut to `REDACTED…`, which is the fail-closed answer).

WHAT THIS FILE PINS. The signal is the deny layer's OWN decision, not a new
heuristic: a date `_date_is_personal` already judged personal is a date of birth,
and the type must say so. A date it judged NOT personal stays `DATE`-less (it is
suppressed and stays real), and a birth-cue date is already `DOB` from `quasi`.

Run:  python3 test_date_association_dob.py
"""

import json

import testkit

testkit.load_dev_bundle()

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

ORG: str = "s0-date-assoc"
CONVERSATION: str = "date-assoc-dob"

# The dossier's shape: the date is personal ONLY by the СНИЛС/card beside it —
# no «рождения», no name, no pronoun.
TEXT: str = "Реквизиты: СНИЛС 123-456-789 01, карта 4276 1234 5678 9012, дата 21.01.1979"
DATE_VALUE: str = "21.01.1979"

DETECTOR: Detector = Detector()

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _context() -> MaskContext:
    store = Vault(":memory:", ORG)
    return MaskContext(
        detector=DETECTOR,
        vault=store.for_conversation(CONVERSATION),
        audit=AuditLog(":memory:"),
        cache=MaskCache(256),
        org_id=ORG,
        agent_id="s0",
        conversation_id=CONVERSATION,
    )


def test_associated_date_is_typed_dob() -> None:
    """The unit signal: an identifier-associated date comes back DOB, not DATE."""
    spans = DETECTOR.detect(TEXT)
    dates = [s for s in spans if s.value == DATE_VALUE]
    check(bool(dates), "the associated date is detected at all",
          f"spans={[(s.entity_type, s.value) for s in spans]}")
    if dates:
        check(dates[0].entity_type == "DOB",
              "an identifier-associated date is typed DOB (not DATE)",
              f"type={dates[0].entity_type}")


def test_unbound_echo_of_associated_date_does_not_leak() -> None:
    """The end-to-end leg: after the line is masked, an unbound tool result
    echoing the date must not reach the model in the clear."""
    context = _context()
    masked_user = mask_messages([{"role": "user", "content": TEXT}], context, False)[0]["content"]
    check(DATE_VALUE not in masked_user,
          "the associated date is masked in the user turn",
          f"masked={masked_user!r}")

    tool_body = json.dumps({"date": DATE_VALUE}, ensure_ascii=False)
    masked_tool = mask_messages([{"role": "tool", "content": tool_body}], context, False)[0]["content"]
    check(DATE_VALUE not in masked_tool,
          "an unbound tool result echoing the date does not leak it",
          f"masked={masked_tool!r}")


def test_negatives_stay_real() -> None:
    """The two directions the previous fix opened, kept open by this one."""
    meeting = "встреча с неврологом 2026-09-02"
    meeting_spans = DETECTOR.detect(meeting)
    check(not meeting_spans,
          "a meeting date with no subject identifier stays real (not DOB)",
          f"spans={[(s.entity_type, s.value) for s in meeting_spans]}")

    birth = "дата рождения 15.07.1985"
    birth_spans = DETECTOR.detect(birth)
    dob = [s for s in birth_spans if s.value == "15.07.1985"]
    check(bool(dob) and dob[0].entity_type == "DOB",
          "a birth-cue date is still DOB",
          f"spans={[(s.entity_type, s.value) for s in birth_spans]}")

    doc = "Счёт 1234 от 15.05.2025 оплачен полностью."
    doc_spans = DETECTOR.detect(doc)
    check(not [s for s in doc_spans if s.value == "15.05.2025"],
          "a document date stays real",
          f"spans={[(s.entity_type, s.value) for s in doc_spans]}")


def main() -> None:
    test_associated_date_is_typed_dob()
    test_unbound_echo_of_associated_date_does_not_leak()
    test_negatives_stay_real()
    failed = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
