"""The UNBOUND recorded-privacy leg — an echo of a restored value is redacted.

    cd prototype && source .venv/bin/activate && \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_recorded_echo_privacy

The second, weaker privacy leg of `envelope._mask_content`. A tool result with NO
usable call (no preceding `tool_calls`, a refused binding, a missing id) cannot be
attributed to any one person's substitute, so production answers every echo of a
value THIS conversation already restored with `_neutral_redaction` — a
`REDACTED…` string carrying no identity — instead of a substitute. `recorded` is
read from the same `Vault.shown_forms` rows the conversation-scoped view exposes,
and the pass runs AFTER `mask_one` so the substitute it inserts is never re-fed
into detection.

The scorer (`bench.agentpii3.score._mask_message`) is the arithmetic twin of that
path and must agree byte for byte with `mask_messages` on the result the model
reads; the harness parity gate (`agentpii4/gateway._push`) excludes the arm when
the two disagree. Before the recorded leg was added to the scorer, a lone surname
or a truncated phone echoed by a tool result reached the model in the clear while
production redacted it — ~46 corpus cases excluded. This pins the fix.

The leg has TWO halves and the scorer lost the second one: a PART of a recorded
NAME's substitute standing in the result is the forward collision, and production
answers it with the neutral redaction too. The scorer's `_recorded_values` built
its values with `substitute=""` and so could not see it — `long_order-*`,
`long_clinic-*`, `long_bank-*`, `long_support-*` all diverged. It now delegates
to `envelope._Provenance.recorded_values_of`, which is why the part-level case
below is a pin and not a description.

No model, no network, one in-memory vault per conversation, driven through the
production path and compared against the scorer.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from testkit import load_dev_bundle  # noqa: E402
from bench.agentpii3 import score  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def _session(convo: str) -> tuple[Vault, MaskContext, Detector]:
    detector = Detector()
    base = Vault(":memory:", "recorded-echo")
    view = base.for_conversation(convo)
    context = MaskContext(
        detector=detector, vault=view, audit=AuditLog(":memory:"),
        cache=MaskCache(1024), org_id="recorded-echo", agent_id="bench",
        conversation_id=convo)
    return view, context, detector


def _prod_tool(view: Vault, context: MaskContext, result_text: str) -> str:
    """Mask the result through the production path; the value is recorded FIRST."""
    out = mask_messages([{"role": "tool", "content": result_text}], context, False)
    content = out[-1]["content"]
    assert isinstance(content, str)
    return content


def _check_lone_surname_echo() -> None:
    """A tool result echoing a surname of an already-masked name is redacted.

    The dialogue recorded «Заболотный Руслан»; the result carries only the lone
    surname «Заболотный», which detection declines (a single surname is not a
    person span) but the recorded leg redacts. Production and the scorer must
    agree.
    """
    view, context, detector = _session("name")
    mask_messages([{"role": "user", "content": "клиент Заболотный Руслан"}],
                  context, False)
    result_text = '{"query": "заказ 824 Заболотный"}'
    prod = _prod_tool(view, context, result_text)
    observed = score._mask_message(result_text, detector, view)
    check(prod == observed.masked,
          "a lone surname echoed by a result is redacted, scorer agrees",
          f"prod={prod!r} scorer={observed.masked!r}")
    check("REDACTED" in prod,
          "the redaction is the neutral, identity-free one",
          prod)


def _check_truncated_phone_echo() -> None:
    """A truncated phone the detector declines is still redacted by the leg.

    The recorded PHONE's numeric echo is a prefix of its own digit rendering and
    is answered with a neutral redaction, not a substitute — no call was bound to
    the result, so no person may be named.
    """
    view, context, detector = _session("phone")
    mask_messages([{"role": "user", "content": "телефон 8-926-547-82-38"}],
                  context, False)
    result_text = '{"note": "звонок на 8-926-547-82"}'
    prod = _prod_tool(view, context, result_text)
    observed = score._mask_message(result_text, detector, view)
    check(prod == observed.masked,
          "a truncated numeric echo is redacted, scorer agrees",
          f"prod={prod!r} scorer={observed.masked!r}")


def _check_plain_result_untouched() -> None:
    """A result carrying NO echo of a recorded value stays byte-identical.

    The conservative leg only redacts values the dialogue itself restored; an
    ordinary quantity beside them («заказ 824») is left alone, so the scorer
    must not invent redactions on an empty or unrelated record.
    """
    view, context, detector = _session("plain")
    result_text = '{"query": "заказ 824"}'
    prod = _prod_tool(view, context, result_text)
    observed = score._mask_message(result_text, detector, view)
    check(prod == observed.masked,
          "a result with no echo is untouched, scorer agrees",
          f"prod={prod!r} scorer={observed.masked!r}")


def _check_composed_own_name_echo() -> None:
    """A NAME the model composed from its own substitutes is left, not re-minted.

    Production's detection drops a NAME every word of which is a substitute this
    dialogue showed apart (surname / given / patronymic joined back together),
    so the composed fake is NOT masked a second time — a second mask would turn
    the person into a new one. The scorer must apply the same own-composition
    guard, or the harness parity gate drops the case (`long_support-038`).
    """
    view, context, detector = _session("composed")
    mask_messages([{"role": "user", "content": "клиент боженова милана"}],
                  context, False)
    mask_messages([{"role": "tool",
                    "content": '{"last_name": "боженова", "first_name": "милана",'
                               ' "middle_name": "аркадьевна"}'}],
                  context, False)
    parts = {literal: rendering for rendering, literal, entity_type in view.shown_forms()
             if entity_type == "NAME"}
    composed = (f"{parts['боженова']} {parts['милана']} {parts['аркадьевна']}")
    result_text = f'{{"name": "{composed}"}}'
    prod = _prod_tool(view, context, result_text)
    observed = score._mask_message(result_text, detector, view)
    check(prod == observed.masked,
          "a composed own substitute is left standing, scorer agrees",
          f"prod={prod!r} scorer={observed.masked!r}")
    check(composed in prod,
          "the composed substitute survives, not re-minted into a new person",
          prod)


def _check_part_of_substitute_echo() -> None:
    """A PART of a recorded NAME's substitute echoed by a result is redacted.

    THE FORWARD COLLISION, and the case that made every long arm diverge. The
    dialogue recorded «павлова тамара» and was shown a two-word substitute; the
    CRM result then carries the real surname and given name in separate JSON
    fields, so `_mask_one` writes the two words of that substitute and the result
    holds a part of it. Production's `_replace_echoes` reads `value.substitute` to
    recognise exactly that and answers with the neutral redaction — the byte
    string stands for the real person AND for our fake, and the owner's policy is
    redaction, never a person.

    The scorer used to build its `recorded` values with `substitute=""`, so the
    whole part leg was a no-op there and it left the substitute standing while
    production redacted: `gateway._push` raised on `long_order-*`, `long_clinic-*`,
    `long_bank-*` and `long_support-*`. It now delegates to
    `envelope._Provenance.recorded_values_of`, so the field cannot go missing
    again. The check is the functional one — agreement is not enough, the
    redaction must actually be there.
    """
    view, context, detector = _session("parts")
    mask_messages([{"role": "user", "content": "клиент павлова тамара"}],
                  context, False)
    result_text = ('{"contacts": [{"id": "c-1", "last_name": "павлова",'
                   ' "first_name": "тамара"}]}')
    # THE SCORER READS THE PRE-PASS RECORD, EXACTLY AS `gateway._push` ORDERS IT:
    # production's `_Provenance.snapshot()` is taken after this call, so the compare
    # is between the same two readings of the same record. Observing after the
    # production pass would compare against a record that pass just wrote into.
    observed = score._mask_message(result_text, detector, view)
    prod = _prod_tool(view, context, result_text)
    check(prod == observed.masked,
          "a part of a recorded substitute is redacted, scorer agrees",
          f"prod={prod!r} scorer={observed.masked!r}")
    check(prod.count("REDACTED") == 2,
          "both words of the substitute are answered with the neutral redaction",
          prod)
    parts = [rendering for rendering, literal, entity_type in view.shown_forms()
             if entity_type == "NAME"]
    standing = [part for rendering in parts for part in rendering.split()
                if part in prod]
    check(not standing,
          "no word of the substitute survives the conservative leg",
          f"surviving={standing} prod={prod!r}")


def main() -> int:
    load_dev_bundle()
    _check_lone_surname_echo()
    _check_truncated_phone_echo()
    _check_plain_result_untouched()
    _check_composed_own_name_echo()
    _check_part_of_substitute_echo()
    failures = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 72)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} passed")
    if failures:
        print("the recorded privacy leg is not in the scorer:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("the recorded privacy leg agrees with production on the scorer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
