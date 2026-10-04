"""A TOOL ERROR THAT ECHOES THE REAL PHONE THE GATEWAY JUST SENT TO THE TOOL.

Case `long_support-013` (source A, repeat 0), from the hop-format audit. The
customer dictates the phone; the gateway mints a DIGITS fake and shows it to the
model; the model writes the digits fake into `ticket_find.phone`; the arguments
leg hands the tool the customer's DICTATED WORDS; the mock refuses
(`phone_not_e164`) and its error body echoes the offending value truncated to 80
characters (`bench/agentpii4/tools.py::Refusal.as_error`, `raw[:80]`). That
80-character echo is the real customer's phone minus its last word, and the
tool-result masking leg does not touch it: in the dossier both literal fields
`text_real` and `text_masked` are byte-equal.

WHAT THIS FILE PINS, AND WHAT IT REFUSES TO PIN.

- The GATE is the privacy outcome: a real fragment the gateway itself minted and
  itself injected into a tool call must not reach the model through the tool
  result. Feeding the dossier's literal error body to the production masking
  path leaves the fragment standing, so this file is RED on that check.
- The LEADING evidence is the CALL, and the leaf production puts in it is the
  exact rendering this dialogue SHOWED — `vault.shown_forms` records it at the
  moment of the swap, spoken substitute and reformatted numeric substitute alike
  — never the restored real value and never a substring guessed from the echo.
  `test_a_literal_shown_leaf_protects_archived_truncations` reads that leaf back
  out of the vault rather than restating it.
- The cause is NOT pinned as "the detector must detect this fragment". The
  80-character echo concatenates to a ten-digit run, which is not a valid
  Russian number, and the detector declining it is the same validity gate that
  keeps ordinary numbers undetected. A remedy that teaches the detector to call
  an invalid run a phone is broad generic fragment masking; this file does not
  ask for it. See the controls.
- The honest scope is a FRAGMENT, not a whole phone: the echo drops the trailing
  word, so its digits are a strict prefix of the real number. Nothing here claims
  the whole number was disclosed.
- This file does not depend on the arguments-leg FORM. Whether the engine sends
  the tool digits or the customer's dictated words, the tool may echo what it
  received and the masking leg must cope. The reproduced-echo check reads the
  form the engine actually produced, so it stays meaningful either way.

CONTROLS. `test_ordinary_number_stays_unmasked` is the negative: with the real
phone already known to the vault, an ordinary non-personal number in the same
error shape must still pass through untouched. `test_other_conversation_...` is
the false-attribution control, run on ONE tenant store with two conversation
views — the store is where both dialogues' rows live, so a lookup that forgot the
scope would resolve A's person for B. `test_a_typed_echo_never_slices_a_longer_
token` is the boundary control: `Анна` must not rewrite `Аннабель`, `ольховая 10`
must not rewrite `ольховая 105`, an email prefix must not rewrite another domain.
`test_provenance_is_indexed_once_per_pass_...` is the cost control: the shown-form
index is read once per masking pass and the echo pass calls the detector zero
times, where the revision it replaces ran a detection per content block.

THE TRUNCATION LENGTH IS NOT THE CONTRACT, because the tool picks it:
`test_every_truncation_of_the_injected_value_is_protected` drives the dossier's
own value at 80, 79, 70, 40, 20 and 8, a second valid spoken phone 101 characters
long at five cuts of its own, and a NAME (a non-PHONE type with no digit identity
at all); the identity floor is pinned from both sides, and a longer token that
starts alike is pinned as untouched.
`test_truncated_numeric_renderings_with_dots_and_slashes` covers the separators a
tool actually writes, with ordinary dotted and slashed text as the negative, and
`test_only_this_dialogue_s_own_record_grants_provenance` pins the scope of the
identity columns: conversation B carrying A's rendering is refused, because the
columns answer for the customer and the evidence must answer for the dialogue.

THE TOKEN BOUNDARY FOLLOWS THE RENDERING, NOT THE VALUE'S IDENTITY.
`test_a_number_beside_a_dictated_echo_does_not_unbind_it` is the blocker: the
dossier's dictated fragment was protected alone and leaked as soon as the tool
wrote ` 12` after it (` 1x`, `. 12`, ` 12.`, a double space), because the boundary
asked the VALUE's identity — a dictated PHONE canonicalizes to digits — and a space
followed by a digit extends a NUMBER. The matched rendering is words, so the numeric
question was never the right one. `test_the_trailing_neighbour_matrix_follows_the_
rendering` pins the rule for spoken PHONE, numeric PHONE, NAME, LOC and EMAIL
against one generated set of trailing neighbours: a separator or punctuation ends
the token and the echo is protected, while a digit after digits or a letter after
words makes a longer token of that kind and the rule leaves it alone.

F1, F2 AND THE SAFE EVIDENCE BOUNDARY, each with the control the request named.
`test_a_shorter_truncation_never_degrades_the_dialogue_s_evidence` drives the
dossier's own value through a tool cut at 85 characters and then at 86, under the
two mints the cut can produce: the write must never shrink an identity the
dialogue already recorded, and every rendering it holds must protect a LATER,
longer cut — before the guard the 85-character cut replaced the 87-character
value and the 86-character cut escaped. `test_a_leading_number_does_not_swallow_
the_phone_fragment` covers `заказ 12 8 926 547-82`, `счёт 5/8 926 547-82` and
`12/8 926 547-82`, where one rendered run merged an ordinary number with the real
fragment and the whole run matched nothing. `test_an_ordinary_flat_head_is_never_
read_as_a_phone` and `test_a_short_card_head_is_never_read_as_a_card` pin the
TYPED boundary from both sides: a bare seven-digit head of either type stays in
the clear, ten flat digits and a seven-digit grouped cut of a phone are still
protected, and so are twelve digits of a card. `test_an_initial_is_not_a_
truncation_of_a_name` pins the other half of that policy: `абдулина м.` is an
INITIAL and is not expanded into the full substitute, while the whole first word
still is. Where privacy and transparency are mathematically ambiguous at a short
prefix, the policy is stated and pinned rather than both claims being made.

Run:  python3 test_error_echo_privacy.py
"""
import copy
import json
import re
from unittest.mock import patch

import testkit

testkit.load_dev_bundle()

from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect import Span  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import (MaskContext, ToolCallContext, _ECHO_FLOOR,  # noqa: E402
                              _InjectedValue, _Provenance, _echo_spans,
                              _literal_echo_spans, _mask_one, mask_messages,
                              mask_one, unmask_response)
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.redact import mask_text, unmask_arguments  # noqa: E402
from pseudex.vault import Vault, canonicalize  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str) -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


# --- the literal case, character for character ---------------------------------

CASE_ORG: str = "s0-error-echo"
CASE_CONVERSATION: str = "long_support-013"
OTHER_CONVERSATION: str = "s0-other-person"
OTHER_REAL: str = "+79161234567"
OTHER_USER_MESSAGE: str = "телефон " + OTHER_REAL + " звоните"
# A leaf that renders nothing this dialogue ever showed: a substitute for a phone
# that was never minted here.
OTHER_REAL_LEAF: str = "+7 916 123-45-67"

# The customer's dictated phone as written in the first user message, and the
# canonical the engine minted the fake from.
REAL_DICTATED: str = (
    "восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь "
    "двадцать три восемсь"
)
REAL_E164: str = "+79265478238"

USER_MESSAGE: str = (
    "добрый день не пришёл заказ это битюков олег телефон "
    + REAL_DICTATED
    + " кстати заа проезд наличнымии"
)

# The same phone written the other way round: the customer types it in groups, so
# the substitute this dialogue is shown is a REFORMATTED NUMERIC — `8 926 547-82-38`
# is shown as e.g. `8 904 271-19-95`, never as words and never as a bare token.
NUMERIC_REAL: str = "8 926 547-82-38"
NUMERIC_USER_MESSAGE: str = (
    "добрый день не пришёл заказ это битюков олег телефон "
    + NUMERIC_REAL
    + " кстати заа проезд наличнымии"
)

# `Refusal.as_error` echoes the offending value truncated to 80 characters, so
# the echo is the dictated value minus its final word ("восемсь"). That is the
# exact string the dossier's `text_real`/`text_masked` carry, and the fragment
# this file requires to be protected.
TRUNCATED_ECHO: str = REAL_DICTATED[:80]
CANARY_FRAGMENT: str = TRUNCATED_ECHO.strip()
FRAGMENT_DIGITS: str = "8926547823"
REAL_NATIONAL_DIGITS: str = "8" + re.sub(r"\D", "", REAL_E164)[1:]

# The dossier's literal first tool result, copied from
# research/hop-format-audit/evidence/cases/long_support-013.md.
DOSSIER_ERROR_REAL: str = (
    "{\n"
    '  "error": {\n'
    '    "code": "phone_not_e164",\n'
    '    "field": "phone",\n'
    '    "message": "поле phone: phone_not_e164: '
    + TRUNCATED_ECHO
    + '"\n'
    "  }\n"
    "}"
)

MATRIX_CALL: str = "matrix-call"

DETECTOR: Detector = Detector()


# --- helpers -------------------------------------------------------------------

def _store() -> Vault:
    """ONE tenant store, the way production has it. Conversations are views of
    it, not separate stores: the cross-conversation controls below are only a
    claim about scope if both dialogues' rows really live in one place."""
    return Vault(":memory:", CASE_ORG)


def _view(store: Vault, conversation: str) -> MaskContext:
    return MaskContext(
        detector=DETECTOR,
        vault=store.for_conversation(conversation),
        audit=AuditLog(":memory:"),
        cache=MaskCache(256),
        org_id=CASE_ORG,
        agent_id="s0",
        conversation_id=conversation,
    )


def _session(conversation: str) -> tuple[Vault, MaskContext]:
    """A fresh tenant store scoped to one conversation, for the single-dialogue
    controls. `vault` is the conversation view, so `shown_forms` and every
    indexed lookup answer for this dialogue only."""
    context: MaskContext = _view(_store(), conversation)
    return context.vault, context


def _mask(context: MaskContext, transcript: list[dict[str, object]]) -> list[dict[str, object]]:
    return mask_messages([dict(one) for one in transcript], context, False)


def _masked(context: MaskContext, transcript: list[dict[str, object]]) -> list[dict[str, object]]:
    """Mask, and assert the caller's transcript survived byte for byte."""
    before: list[dict[str, object]] = copy.deepcopy(transcript)
    masked: list[dict[str, object]] = _mask(context, transcript)
    if transcript != before:
        raise AssertionError("mask_messages mutated its input transcript")
    return masked


def _showed_phone(context: MaskContext) -> tuple[str, str]:
    """The one (rendering, literal) PHONE row this dialogue recorded."""
    rows: list[tuple[str, str]] = [(shown, original)
                                   for shown, original, kind in context.vault.shown_forms()
                                   if kind == "PHONE"]
    if len(rows) != 1:
        raise RuntimeError(f"fixture minted {len(rows)} PHONE renderings, wanted exactly one")
    return rows[0]


def _showed_name(context: MaskContext) -> tuple[str, str]:
    """The one (rendering, literal) NAME row this dialogue recorded."""
    rows: list[tuple[str, str]] = [(shown, original)
                                   for shown, original, kind in context.vault.shown_forms()
                                   if kind == "NAME"]
    if len(rows) != 1:
        raise RuntimeError(f"fixture minted {len(rows)} NAME renderings, wanted exactly one")
    return rows[0]


# Three ONE-WORD substitutes, the way a CRM card's last/first/middle name fields
# reach the model: shown APART, so no single rendering equals the joined string the
# model writes back.
PART_NAME_WORDS: tuple[str, ...] = ("Чижова", "Эмилия", "Романовна")


def _mint_part_names(context: MaskContext) -> str:
    """Mint one substitute per word and return them joined, as the model would."""
    return " ".join(mask_text(word, context.vault, [Span(0, len(word), "NAME", word)])
                    for word in PART_NAME_WORDS)


def _mint_phone(context: MaskContext, user_text: str) -> tuple[str, str]:
    """Mask the customer turn and read back the LITERAL rendering this dialogue
    was shown — which is the leaf the production transcript carries in the call."""
    masked_user = _mask(context, [{"role": "user", "content": user_text}])[0]["content"]
    if not isinstance(masked_user, str):
        raise RuntimeError("masked user content was not a string")
    return _showed_phone(context)


def _truncated_error_body(echoed: str) -> str:
    """The mock tool's error shape, truncating exactly as `Refusal.as_error`
    does: `поле {path}: {rule}: {raw[:80]}`."""
    return json.dumps(
        {"error": {"code": "phone_not_e164", "field": "phone",
                   "message": f"поле phone: phone_not_e164: {echoed[:80]}"}},
        ensure_ascii=False,
        indent=2,
    )


def _exact_error_body(echoed: str) -> str:
    """The same error shape with NO truncation, for the cause pin."""
    return json.dumps(
        {"error": {"code": "phone_not_e164", "field": "phone",
                   "message": f"поле phone: phone_not_e164: {echoed}"}},
        ensure_ascii=False,
        indent=2,
    )


def _call_message(call_id: str, leaf: str, field: str = "phone",
                  name: str = "ticket_find") -> dict[str, object]:
    """The assistant turn as the wire carries it: the model writes the string it
    was SHOWN into the argument."""
    return {"id": call_id, "type": "function",
            "function": {"name": name,
                         "arguments": json.dumps({field: leaf}, ensure_ascii=False)}}


def _association(leaf: str, body: object, call_id: str = MATRIX_CALL,
                 field: str = "phone") -> list[dict[str, object]]:
    """One associated call/result pair, without a user turn: for the fixtures that
    minted their substitute through `mask_text` and a `Span`."""
    return [
        {"role": "assistant", "tool_calls": [_call_message(call_id, leaf, field)]},
        {"role": "tool", "tool_call_id": call_id, "content": body},
    ]


def _transcript(leaf: str, body: object, call_id: str = MATRIX_CALL) -> list[dict[str, object]]:
    """The user turn that minted the substitute, then one associated call/result."""
    return [{"role": "user", "content": USER_MESSAGE}] + _association(leaf, body, call_id)


def _mask_tool_result(context: MaskContext, body: str) -> str:
    transcript: list[dict[str, object]] = [
        {"role": "tool", "name": "ticket_find", "content": body},
    ]
    masked = _mask(context, transcript)[0]["content"]
    if not isinstance(masked, str):
        raise RuntimeError("masked tool content was not a string")
    return masked


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _leaks(masked: str, shown: str, fragment: str) -> bool:
    """Whether a real fragment survived OUTSIDE the substitute we inserted.

    A short Russian numeral prefix («восемь д…») also occurs inside the fake,
    which is another spoken number, so the substitute is removed before looking:
    what is asked is whether the REAL text is still there, not whether the same
    letters appear somewhere in the answer."""
    return fragment.strip() in masked.replace(shown, "")


# A second, longer valid spoken PHONE: the same eleven digits dictated with the
# hesitations a transcript keeps — 101 characters, its last word starting at 95.
# The contract cannot be "the length the dossier happened to have", so this value
# is protected at every one of ITS truncation lengths too.
LONG_SPOKEN_PHONE: str = (
    "восемь эээ девятьсот двадцать шесть пятьдесят эээ четыре эээ семьдесят "
    "восемь двадцать эээ три восемь"
)

# A non-PHONE literal family: a NAME has no digit identity at all, so only the
# literal rule can protect its truncations.
LITERAL_NAME: str = "Битюков Олег Викторович"

# THE TWO SHAPES F1 TAKES, pinned so the reproduction is not a coin toss. The
# rendering of a dictated phone mirrors the words of the mention, so cutting two
# characters off the last word either leaves the substitute character for
# character what it was (the write mutated the row that already held the value) or
# produces a second rendering (the evidence must still resolve to the longest
# original). Both fakes are ordinary tokens the generator accepts, and neither is
# a fixture value the engine knows about.
SAME_RENDERING_FAKE: str = "+79550017589"
SECOND_RENDERING_FAKE: str = "+79894275108"


# --- the case is a fragment, not a whole phone ---------------------------------

def test_the_leak_is_a_fragment_not_the_whole_number() -> None:
    """The honest scope, pinned so no later claim grows into "the phone leaked".

    The echo is a strict prefix of the dictated value (the refusal truncated it),
    and its digit signature is a strict prefix of the real number's. A test that
    demanded the whole `+79265478238` be absent would be satisfied by masking the
    wrong thing and would overstate what was disclosed."""
    check(
        TRUNCATED_ECHO != REAL_DICTATED and REAL_DICTATED.startswith(TRUNCATED_ECHO),
        "the echoed fragment is a strict prefix of the dictated value",
        f"echo={len(TRUNCATED_ECHO)} chars, value={len(REAL_DICTATED)} chars",
    )
    check(
        REAL_NATIONAL_DIGITS.startswith(FRAGMENT_DIGITS) and FRAGMENT_DIGITS != REAL_NATIONAL_DIGITS,
        "the echoed digits are a strict prefix of the real number",
        f"{FRAGMENT_DIGITS} vs {REAL_NATIONAL_DIGITS}",
    )
    check(
        CANARY_FRAGMENT in DOSSIER_ERROR_REAL,
        "the dossier's literal error body carries the canary fragment",
        repr(CANARY_FRAGMENT[:40]) + "…",
    )


# --- the headline: the tool error must not carry the real fragment -------------

def test_error_echo_is_protected() -> None:
    """The dossier's literal error body through the production path, driven by the
    leaf the production transcript actually carries: the exact rendering this
    dialogue SHOWED, read back out of `shown_forms` — not the restored real value,
    not a canonical token. This is the dossier's literal error body."""
    vault, context = _session(CASE_CONVERSATION)
    shown, real = _mint_phone(context, USER_MESSAGE)

    check(real == REAL_DICTATED,
          "the gateway holds the real dictated value it minted",
          repr(real[:40]) + "…")
    check(shown != real and shown not in DOSSIER_ERROR_REAL,
          "the leaf is the rendering the model was shown, not the real value",
          f"shown={shown!r}")
    transcript: list[dict[str, object]] = _transcript(shown, DOSSIER_ERROR_REAL)
    before: str = json.dumps(transcript, ensure_ascii=False)
    transformed: list[dict[str, object]] = _mask(context, transcript)
    masked: object = transformed[-1]["content"]
    if not isinstance(masked, str):
        raise AssertionError("tool result content changed its wire type")
    check(json.dumps(transcript, ensure_ascii=False) == before,
          "masking does not mutate the raw call/result transcript", "")
    check(transformed[-1]["tool_call_id"] == MATRIX_CALL,
          "the tool-call association remains on the wire", "")
    check(
        CANARY_FRAGMENT not in masked and shown in masked,
        "HEADLINE: the dossier's literal error echo loses the real fragment",
        f"echo={CANARY_FRAGMENT!r}",
    )


def test_a_literal_shown_leaf_protects_archived_truncations() -> None:
    """Requirement, both renderings, leaf read from the vault: the SPOKEN
    substitute protects the dossier's truncated spoken echo, and the REFORMATTED
    NUMERIC substitute protects a truncated digital echo of the same real value.
    Neither leaf is written down here — each is whatever `shown_forms` recorded."""
    spoken_vault, spoken_context = _session(CASE_CONVERSATION)
    spoken_leaf, spoken_real = _mint_phone(spoken_context, USER_MESSAGE)
    spoken_masked = _masked(spoken_context, _transcript(spoken_leaf, DOSSIER_ERROR_REAL))[-1]["content"]
    if not isinstance(spoken_masked, str):
        raise AssertionError("tool result content changed its wire type")
    check(spoken_real == REAL_DICTATED and CANARY_FRAGMENT not in spoken_masked,
          "a literal SPOKEN leaf protects the archived spoken truncation",
          f"leaf={spoken_leaf!r}")
    check(spoken_leaf in spoken_masked,
          "the model reads back the spoken substitute it wrote", "")

    numeric_vault, numeric_context = _session(OTHER_CONVERSATION)
    numeric_leaf, numeric_real = _mint_phone(numeric_context, NUMERIC_USER_MESSAGE)
    cut: str = NUMERIC_REAL[:10]          # `8 926 547-82`, a truncated digital echo
    digital_masked = _masked(numeric_context, _transcript(numeric_leaf, _exact_error_body(cut)))[-1]["content"]
    if not isinstance(digital_masked, str):
        raise AssertionError("tool result content changed its wire type")
    check(numeric_real == NUMERIC_REAL and cut not in digital_masked,
          "a literal REFORMATTED NUMERIC leaf protects a truncated digital echo",
          f"leaf={numeric_leaf!r}")
    check(numeric_leaf in digital_masked,
          "the model reads back the numeric substitute it wrote", "")


def test_a_retyped_substitute_is_still_this_dialogue_s_rendering() -> None:
    """A model may RETYPE the substitute instead of copying it: the canonical token
    the vault minted, or a numeric rewrite of that token. Both are still OUR string
    for this value and are resolved by indexed identity — the token column, then the
    digit-signature columns — rather than by running the detector over the leaf.
    Each protects the archived truncation with the very string the model wrote."""
    vault, context = _session(CASE_CONVERSATION)
    shown, real = _mint_phone(context, USER_MESSAGE)
    token = vault.peek_token(canonicalize("PHONE", real), "PHONE")
    if not token:
        raise RuntimeError("fixture minted no canonical token")
    check(token != shown,
          "the canonical token is a different string from the recorded rendering",
          f"token={token!r} shown={shown!r}")
    for leaf in (token, "8" + _digits(token)[-10:]):
        masked = _masked(context, _transcript(leaf, DOSSIER_ERROR_REAL))[-1]["content"]
        check(CANARY_FRAGMENT not in masked and leaf in masked,
              f"a retyped substitute ({leaf!r}) protects the archived truncation", "")


def test_every_truncation_of_the_injected_value_is_protected() -> None:
    """The truncation point belongs to the TOOL, so no single length is the
    contract. Every token-bounded prefix of a value this call carried is protected
    down to the identity floor — the dossier's own value at 80 AND 79 AND 70, a
    longer valid spoken phone at every one of its cuts, and a non-PHONE literal
    family (a NAME, whose canonical is not a digit string) with the same rule.
    The floor is pinned from both sides so it is a stated policy, not a leak."""
    vault, context = _session(CASE_CONVERSATION)
    shown, real = _mint_phone(context, USER_MESSAGE)
    for cut in (len(real), 80, 79, 70, 40, 20, 8):
        body = _exact_error_body(real[:cut])
        masked = _masked(context, _transcript(shown, body))[-1]["content"]
        check(not _leaks(masked, shown, real[:cut]),
              f"the dossier value is protected at truncate {cut} of {len(real)}",
              f"leaked={_leaks(masked, shown, real[:cut])}")

    long_context = _view(_store(), "long-spoken-phone")
    long_leaf, long_real = _mint_phone(long_context, LONG_SPOKEN_PHONE)
    check(long_real == LONG_SPOKEN_PHONE and len(LONG_SPOKEN_PHONE) == 101,
          "the second fixture is a valid spoken phone 101 characters long",
          f"len={len(LONG_SPOKEN_PHONE)}")
    for cut in (101, 96, 90, 70, 30):
        body = _exact_error_body(long_real[:cut])
        masked = _masked(long_context, _transcript(long_leaf, body))[-1]["content"]
        check(not _leaks(masked, long_leaf, long_real[:cut]),
              f"the 101-character value is protected at truncate {cut}", "")

    name_context = _view(_store(), "literal-name")
    name_leaf = mask_text(LITERAL_NAME, name_context.vault,
                          [Span(0, len(LITERAL_NAME), "NAME", LITERAL_NAME)])
    for cut in (len(LITERAL_NAME), 18, 12, 8):
        body = _exact_error_body(LITERAL_NAME[:cut])
        masked = _masked(name_context, _association(name_leaf, body, field="name"))[-1]["content"]
        check(not _leaks(masked, name_leaf, LITERAL_NAME[:cut]),
              f"a NAME (non-PHONE) literal is protected at truncate {cut}", "")
    longer = "Битюков Олегович пришёл"
    check(mask_one(longer, name_context) != longer,
          "the detector masks the longer token as well, so the public output cannot "
          "show which layer refused it", "")
    injected = _InjectedValue(real=LITERAL_NAME, entity_type="NAME", substitute=name_leaf)
    check(_echo_spans(longer, injected) == (),
          "the echo rule itself does not slice a longer token that starts alike", "")

    floor_cut: int = _ECHO_FLOOR - 1
    body = _exact_error_body(real[:floor_cut])
    masked = _masked(context, _transcript(shown, body))[-1]["content"]
    check(_leaks(masked, shown, real[:floor_cut]),
          f"below the identity floor ({floor_cut} characters) the rule refuses",
          "the floor is the only length bound the contract has")


def test_truncated_numeric_renderings_with_dots_and_slashes() -> None:
    """A typed numeric echo comes back in whichever separators the tool wrote.
    `.` and `/` are renderings a person and a mock both produce, and each must be
    found by the type's digit identity while ordinary dotted and slashed text is
    left alone."""
    vault, context = _session(CASE_CONVERSATION)
    leaf, real = _mint_phone(context, NUMERIC_USER_MESSAGE)
    check(real == NUMERIC_REAL, "the numeric fixture minted the real it wrote", real)
    for echo in ("8.926.547", "8/926/547", "8.926.547-82", "8.926.547/82"):
        body = _exact_error_body(echo)
        check(mask_one(body, context) == body,
              f"the detector declines {echo!r} (the control is not vacuous)", "")
        masked = _masked(context, _transcript(leaf, body))[-1]["content"]
        check(echo not in masked and leaf in masked,
              f"a truncated {echo!r} is replaced by the shown substitute", "")
    for ordinary in ("заказ 12.07.2026 оплачен, 3/4 коробки", "версия 2.0, отдел 1/2"):
        body = _exact_error_body(ordinary)
        masked = _masked(context, _transcript(leaf, body))[-1]["content"]
        check(masked == body,
              f"ordinary dotted/slashed text is untouched ({ordinary[:18]!r})", "")


def test_only_this_dialogue_s_own_record_grants_provenance() -> None:
    """One tenant store with two conversation views. The token and digit-signature
    columns answer for the WHOLE CUSTOMER on purpose, so conversation B can reach
    A's row through them — by A's canonical token, and by A's reformatted NUMERIC
    rendering, which the signature columns resolve although the rendering index
    does not hold it. A result carrying either would then be answered with A's
    substitute. The evidence is gated to what THIS dialogue recorded, so B refuses
    and the result is untouched, while B's own leaf and B's own retyped token still
    protect B's own value."""
    store = _store()
    context_a = _view(store, CASE_CONVERSATION)
    spoken_a, real_a = _mint_phone(context_a, USER_MESSAGE)
    context_n = _view(store, "numeric-a")
    numeric_a, real_n = _mint_phone(context_n, NUMERIC_USER_MESSAGE)
    token_n = context_n.vault.peek_token(canonicalize("PHONE", real_n), "PHONE")
    if not token_n:
        raise RuntimeError("conversation A minted no canonical token")
    context_b = _view(store, OTHER_CONVERSATION)
    shown_b, real_b = _mint_phone(context_b, OTHER_USER_MESSAGE)

    check(context_b.vault.detokenize_many_typed({token_n}) != {},
          "the identity columns DO answer across conversations (the gate is load-bearing)",
          "a customer-wide hit is not evidence about this dialogue")
    # Each cut is one the DETECTOR declines, so only the echo pass can act on it;
    # every case gets a FRESH view of B, so one pass cannot teach the next.
    cases = (("A's spoken rendering", spoken_a, real_a[:80]),
             ("A's numeric rendering", numeric_a, real_n[:10]),
             ("A's canonical token", token_n, real_n[:10]))
    for label, leaf, cut in cases:
        body = _exact_error_body(cut)
        check(mask_one(body, _view(store, OTHER_CONVERSATION)) == body,
              f"the detector declines the echo behind {label} (provenance is measured)", "")
        masked = _masked(_view(store, OTHER_CONVERSATION),
                         _association(leaf, body))[-1]["content"]
        check(masked == body and leaf not in masked,
              f"conversation B refuses a leaf derived from {label}",
              f"masked={masked[-50:]!r}")

    own = _masked(context_b, _association(shown_b, _exact_error_body(real_b[:70])))[-1]["content"]
    check(not _leaks(own, shown_b, real_b[:70]) and shown_b in own,
          "B's own leaf still protects B's own value", "")
    own_token = context_b.vault.peek_token(canonicalize("PHONE", real_b), "PHONE")
    own_retyped = _masked(context_b, _association(own_token, _exact_error_body(real_b[:70])))[-1]["content"]
    check(not _leaks(own_retyped, own_token, real_b[:70]) and own_token in own_retyped,
          "B's own retyped token still protects B's own value", "")


def test_reproduced_error_echo_is_protected() -> None:
    """The LIVE chain, end to end: the model writes the substitute, the arguments
    leg restores it (`unmask_arguments`), the tool echoes what it received
    truncated at 80, and the model must not read the real value back. The echo is
    protected by the call that produced it, with the substitute the model wrote —
    the arguments-leg form is read from the engine, not assumed."""
    vault, context = _session(CASE_CONVERSATION)
    shown, _real = _mint_phone(context, USER_MESSAGE)
    restored = json.loads(unmask_arguments(json.dumps({"phone": shown}), vault))["phone"]
    check(restored == REAL_DICTATED,
          "the arguments leg restored the customer's own dictated words",
          f"restored={restored[:40]!r}…")
    body = _truncated_error_body(restored)
    masked = _masked(context, _transcript(shown, body))[-1]["content"]
    check(
        CANARY_FRAGMENT not in masked and _digits(REAL_E164) not in _digits(masked),
        "the reproduced error echo carries neither the dictated fragment nor the real digits",
        f"restored={restored!r} masked={masked[:140]!r}",
    )


# --- the proxy/sidecar replay: the call carries the RESTORED real value --------

def test_a_restored_real_leaf_grants_provenance() -> None:
    """THE SAME CALL AS THE PROXY AND THE SIDECAR ACTUALLY REPLAY IT, where the
    arguments carry the customer's OWN string and the substitute does not.

    `test_reproduced_error_echo_is_protected` starts from the string the MODEL
    wrote, which is the benchmark transcript's shape. The two shipping legs hand
    the tool the REAL value: the proxy restores the answer with
    `unmask_response` before the customer's SDK sees it, and the sidecar's
    `/unmask_arguments` does the same for the host gateway. An OpenAI SDK appends
    the message it received to the next request VERBATIM, so the replayed
    `tool_calls[].function.arguments` carry the RESTORED REAL string this very
    call injected — the same call, the same value, only written the customer's way.
    The result leg must read that leaf as this call's evidence and answer with the
    substitute the dialogue already showed; today it resolves only leaves that are
    RENDERINGS of a value, so the real leaf names nothing and detection alone is
    left, which declines the 80-character cut.

    The controls are the request's own. An ordinary number in an armed result stays
    in the clear; an unrelated parallel call's result is untouched while its armed
    sibling's is protected; and the same body with its association stripped is
    untouched — so the red is the call binding read in the replayed notation, not
    «mask more numbers»."""
    vault, context = _session(CASE_CONVERSATION)
    shown, real = _mint_phone(context, USER_MESSAGE)
    check(real == REAL_DICTATED, "the fixture minted the dossier's real dictated value",
          repr(real[:40]) + "…")

    # The provider's answer, turned back into the customer's terms by the engine's
    # own restoring leg — this is what the SDK receives, not a fixture string.
    upstream: dict[str, object] = {"choices": [{"index": 0, "message": {
        "role": "assistant", "content": None,
        "tool_calls": [_call_message(MATRIX_CALL, shown)]}}]}
    restored_message: object = unmask_response(upstream, context.vault)["choices"][0]["message"]
    if not isinstance(restored_message, dict):
        raise AssertionError("the restored message changed its wire type")
    calls: object = restored_message.get("tool_calls")
    if not isinstance(calls, list):
        raise AssertionError("the restored message lost its tool_calls")
    replayed: object = json.loads(calls[0]["function"]["arguments"])["phone"]
    check(replayed == real and replayed != shown,
          "the replayed call carries the RESTORED value, not the substitute",
          f"replayed={str(replayed)[:40]!r}…")

    round_two: list[dict[str, object]] = [
        {"role": "user", "content": USER_MESSAGE},
        restored_message,
        {"role": "tool", "tool_call_id": MATRIX_CALL, "content": DOSSIER_ERROR_REAL},
    ]
    masked_transcript: list[dict[str, object]] = _masked(context, round_two)
    visible_calls: object = masked_transcript[1]["tool_calls"]
    if not isinstance(visible_calls, list) or not isinstance(visible_calls[0], dict):
        raise AssertionError("the masked replay lost its tool_calls")
    visible_function = visible_calls[0]["function"]
    if not isinstance(visible_function, dict):
        raise AssertionError("the masked replay lost its function object")
    visible: object = json.loads(str(visible_function["arguments"])).get("phone")
    masked: object = masked_transcript[-1]["content"]
    if not isinstance(masked, str):
        raise AssertionError("tool result content changed its wire type")
    check(CANARY_FRAGMENT not in masked,
          "HEADLINE: a replayed REAL leaf protects this call's truncated echo",
          f"echo={CANARY_FRAGMENT!r}")
    # THE POSITIVE FORM IS THE RENDERING THIS REQUEST CARRIES, NOT THE ONE THE
    # EARLIER TURN SHOWED. The replayed arguments are re-typed by their own JSON
    # key — a dictated value under `phone` is demoted to the opaque type — so the
    # string the model reads in THIS request is that opaque token, not the spoken
    # substitute the first turn displayed. The assertion therefore reads the leaf
    # back OUT of the masked transcript and requires the echo to answer with it,
    # and requires it to differ from the real value: the contract is that the
    # evidence and the answer are the string the current request carries.
    check(isinstance(visible, str) and visible != real and visible in masked,
          "the echo is answered with the model-visible rendering of the replayed call",
          f"visible={visible!r}")

    # The same armed shape with no association at all. THE BINDING IS NOT THE
    # PROTECTION ANY MORE: privacy and attribution are separate boundaries. The
    # conversation itself recorded the value, so the echo is recognised without a
    # person being named and is conservatively redacted — never left raw, and
    # never answered with a substitute somebody else's row happens to hold.
    stripped: object = _masked(context, [
        restored_message,
        {"role": "tool", "content": DOSSIER_ERROR_REAL},
    ])[-1]["content"]
    check(isinstance(stripped, str) and CANARY_FRAGMENT not in stripped,
          "without the association the recorded echo is conservatively redacted",
          f"masked={stripped!r}" if isinstance(stripped, str) else "")
    check(shown not in stripped and real not in stripped,
          "the unbound redaction names no person's substitute",
          "")

    # An ordinary quantity in an armed REAL-leaf result stays byte for byte; the
    # numbers are at the rule's edge (`926`, `926547` are genuine heads of the real
    # number) and below the typed digit floor an ordinary quantity wins.
    ordinary: str = json.dumps(
        {"error": {"code": "not_found", "field": "order_id",
                   "message": "поле order_id: not_found: заказ 1428570, 12 коробок, "
                              "срок 926 дней, код 926547"}},
        ensure_ascii=False, indent=2)
    ordinary_masked: object = _masked(context, [
        restored_message,
        {"role": "tool", "tool_call_id": MATRIX_CALL, "content": ordinary},
    ])[-1]["content"]
    check(ordinary_masked == ordinary,
          "ordinary numbers survive an armed REAL leaf", f"masked={ordinary_masked!r}")

    # Two parallel calls in one assistant message: only the first carried the phone,
    # so only its result may be rewritten.
    armed = _call_message("armed-1", real)
    unrelated = _call_message("unrelated-2", "1428570", field="order", name="order_find")
    unrelated_body: str = "заказ 1428570, 12 коробок, код 926547"
    parallel: list[dict[str, object]] = [
        {"role": "assistant", "tool_calls": [armed, unrelated]},
        {"role": "tool", "tool_call_id": "armed-1", "content": DOSSIER_ERROR_REAL},
        {"role": "tool", "tool_call_id": "unrelated-2", "content": unrelated_body},
    ]
    parallel_masked: list[dict[str, object]] = _masked(context, parallel)
    check(CANARY_FRAGMENT not in parallel_masked[1]["content"],
          "the armed sibling's result loses the fragment", "")
    check(parallel_masked[2]["content"] == unrelated_body,
          "the unrelated parallel call's result is untouched",
          f"masked={parallel_masked[2]['content']!r}")


# --- the mixed replay: one RESTORED leaf beside one ALREADY-SHOWN leaf ----------

def test_a_mixed_replayed_call_reads_both_forms_per_leaf() -> None:
    """A CALL THAT CARRIES BOTH FORMS AT ONCE, and both must be read.

    The reproduction the independent review rejected the candidate for. The
    replayed arguments carry the RESTORED REAL dictated phone — the app composed
    them from its own state, so the wire holds the customer's own writing for one
    field — BESIDE a leaf this dialogue already showed (the NAME substitute the
    model wrote back verbatim). The per-CALL gate read `values_for(raw)` as a
    verdict on the whole call: the one resolvable NAME leaf made it non-empty, the
    call was therefore read in its raw form only, and the phone leaf contributed no
    provenance. The result leg then had no value whose echo it could recognise, the
    detector declines the 80-character cut, and the customer's own dictation
    reached the model through the tool error — while the SAME request showed the
    model a masked phone in the call. Silent, no 5xx, no residual.

    Both forms are this call's own arguments, so every leaf is read in both and the
    values are unioned: a leaf that names nothing in either form still names
    nothing (the controls below), and the model-visible form is this pass's own
    masking of the SAME arguments string `_mask_tool_calls` already handled, so it
    is the cache hit — no second detection, no audit event, no vault row.

    The controls are the request's own: an extra leaf that resolves to nothing
    changes nothing, ordinary quantities in an armed result stay in the clear, and
    a leaf from ANOTHER conversation grants nothing even when it rides beside this
    call's own restored real leaf."""
    vault, context = _session(CASE_CONVERSATION)
    shown_phone, real_phone = _mint_phone(context, USER_MESSAGE)
    shown_name, real_name = _showed_name(context)
    check(real_name != shown_name and real_name in USER_MESSAGE,
          "the fixture holds a NAME substitute for a name the customer wrote",
          f"shown={shown_name!r}")

    # The provider's answer restored by the engine's own leg — the string the
    # shipping legs hand the tool — and then the app composes the arguments from
    # its own state: the restored phone in one field, the substitute this dialogue
    # already showed in the other. Both leaves belong to THIS call.
    upstream: dict[str, object] = {"choices": [{"index": 0, "message": {
        "role": "assistant", "content": None,
        "tool_calls": [_call_message(MATRIX_CALL, shown_phone)]}}]}
    restored_message: object = unmask_response(upstream, context.vault)["choices"][0]["message"]
    if not isinstance(restored_message, dict):
        raise AssertionError("the restored message changed its wire type")
    restored_call: dict[str, object] = json.loads(
        restored_message["tool_calls"][0]["function"]["arguments"])
    check(restored_call["phone"] == real_phone and restored_call["phone"] != shown_phone,
          "the restoring leg handed the tool the customer's own dictated words",
          f"replayed={str(restored_call['phone'])[:24]!r}…")

    mixed: dict[str, object] = copy.deepcopy(restored_message)
    mixed_arguments: str = json.dumps({"phone": restored_call["phone"], "client": shown_name},
                                      ensure_ascii=False)
    mixed["tool_calls"][0]["function"]["arguments"] = mixed_arguments

    # THE CAUSE, PINNED BEFORE THE FIX IS BELIEVED: read on its own, the raw form
    # names the shown NAME leaf and NOT the phone, which is exactly why a per-call
    # gate on the raw form abandoned the phone leaf.
    raw_values = _Provenance(context).values_for(
        ToolCallContext(call_id=MATRIX_CALL, name="ticket_find", arguments=mixed_arguments))
    check(sorted(value.entity_type for value in raw_values) == ["NAME"],
          "the raw form alone names the shown NAME leaf and not the real phone leaf",
          f"raw={[value.entity_type for value in raw_values]}")

    round_two: list[dict[str, object]] = [
        {"role": "user", "content": USER_MESSAGE},
        mixed,
        {"role": "tool", "tool_call_id": MATRIX_CALL, "content": DOSSIER_ERROR_REAL},
    ]
    masked_transcript: list[dict[str, object]] = _masked(context, round_two)
    visible_call: dict[str, object] = json.loads(
        masked_transcript[1]["tool_calls"][0]["function"]["arguments"])
    visible_phone: object = visible_call["phone"]
    masked: object = masked_transcript[-1]["content"]
    if not isinstance(masked, str):
        raise AssertionError("tool result content changed its wire type")

    check(CANARY_FRAGMENT not in masked,
          "MIXED CALL: the real dictated fragment does not survive beside a shown leaf",
          f"echo={CANARY_FRAGMENT!r}")
    check(isinstance(visible_phone, str) and visible_phone != real_phone and visible_phone in masked,
          "the echo is answered with the model-visible phone of THIS request",
          f"visible={visible_phone!r}")

    # CONTROL 1 — an extra leaf that resolves to nothing. The phone is still this
    # call's, so its echo is still protected, and the ordinary quantities of the
    # armed result pass through byte for byte: the union reads evidence, it does
    # not mask numbers.
    unresolved: dict[str, object] = copy.deepcopy(mixed)
    unresolved["tool_calls"][0]["function"]["arguments"] = json.dumps(
        {"phone": restored_call["phone"], "order": "1428570"}, ensure_ascii=False)
    ordinary: str = json.dumps(
        {"error": {"code": "not_found", "field": "order_id",
                   "message": "поле order_id: not_found: заказ 1428570, 12 коробок, "
                              "срок 926 дней, код 926547"}},
        ensure_ascii=False, indent=2)
    ordinary_masked: object = _masked(context, [
        unresolved,
        {"role": "tool", "tool_call_id": MATRIX_CALL, "content": ordinary},
    ])[-1]["content"]
    check(ordinary_masked == ordinary,
          "ordinary numbers survive an armed mixed call beside an unresolved leaf",
          f"masked={ordinary_masked!r}")

    # CONTROL 2 — a leaf from ANOTHER conversation grants nothing, even beside this
    # call's own restored real leaf. Without the gate the foreign rendering would
    # resolve the foreign value and rewrite its cut with B's substitute; the cut
    # below is one the detector declines, so provenance is the only layer that
    # could touch it.
    store = _store()
    context_a = _view(store, CASE_CONVERSATION)
    _shown_a, real_a = _mint_phone(context_a, USER_MESSAGE)
    context_b = _view(store, OTHER_CONVERSATION)
    shown_b, real_b = _mint_phone(context_b, OTHER_USER_MESSAGE)
    foreign_message: dict[str, object] = {
        "role": "assistant",
        "tool_calls": [{"id": MATRIX_CALL, "type": "function", "function": {
            "name": "ticket_find",
            "arguments": json.dumps({"phone": real_a, "client": shown_b},
                                    ensure_ascii=False)}}]}
    foreign_body: str = _exact_error_body(real_b[:10])
    check(mask_one(foreign_body, context_a) == foreign_body,
          "the detector declines B's cut (the foreign control is not vacuous)", "")
    foreign_masked: object = _masked(_view(store, CASE_CONVERSATION), [
        foreign_message,
        {"role": "tool", "tool_call_id": MATRIX_CALL, "content": foreign_body},
    ])[-1]["content"]
    check(foreign_masked == foreign_body and shown_b not in str(foreign_masked),
          "a foreign conversation's leaf grants no provenance for its own value",
          f"masked={str(foreign_masked)[-60:]!r}")


# --- cause pin: the rescan happens, and the FULL echo is masked ----------------

def test_untruncated_echo_is_masked() -> None:
    """The tool-result leg DOES re-run detection and DOES mask a full dictated
    run — the failure is the truncation, not a missing rescan. Green today; a
    remedy that dropped the rescan would turn it red."""
    vault, context = _session(CASE_CONVERSATION)
    shown, _real = _mint_phone(context, USER_MESSAGE)
    masked = _mask_tool_result(context, _exact_error_body(REAL_DICTATED))
    check(
        CANARY_FRAGMENT not in masked,
        "an untruncated dictated echo is masked (rescan is present)",
        f"masked={masked[:140]!r}",
    )
    check(
        shown in masked,
        "the untruncated echo is masked with the substitute the model was shown",
        f"shown={shown}",
    )


# --- F1: a tool's cut must not shrink the dialogue's own evidence -------------

def _phone_rows(context: MaskContext) -> list[tuple[str, str]]:
    """Every (rendering, original) PHONE row this dialogue holds."""
    return [(shown, original) for shown, original, kind in context.vault.shown_forms()
            if kind == "PHONE"]


def test_a_shorter_truncation_never_degrades_the_dialogue_s_evidence() -> None:
    """F1, same conversation and pass history. The tool cuts the value it was
    handed at interior character positions, and the tool-result leg re-detects
    each cut as the same phone. The cut is protected — and it used to be recorded
    as the owner of the substitute, shrinking the dialogue's evidence from the
    authoritative 87-character value to the 85-character cut. A LATER cut at 86
    characters is then no longer a prefix of what was recorded and leaks.

    Two mints are pinned, because the defect has two shapes and the fix has two
    halves. When the cut renders to the SAME substitute, the write mutated the row
    that already held the value — the vault must keep the authoritative original.
    When the cut renders to a DIFFERENT substitute, a second row appears holding
    the cut — the evidence must still resolve that rendering to the longest
    original this dialogue recorded. The evidence is read back out of the vault,
    never restated: every rendering the dialogue holds must protect a later,
    longer cut of the same value, and no row that existed before may shrink."""
    for label, fake in (("the cut re-renders the same substitute", SAME_RENDERING_FAKE),
                        ("the cut re-renders a second substitute", SECOND_RENDERING_FAKE)):
        with patch("pseudex.vault._fake_phone", return_value=fake):
            vault, context = _session(CASE_CONVERSATION)
            shown, real = _mint_phone(context, USER_MESSAGE)
            check(real == REAL_DICTATED and len(real) == 87,
                  f"{label}: the dialogue minted the dossier's 87-character value",
                  f"len={len(real)}")
            before: dict[str, str] = dict(_phone_rows(context))
            first: object = _masked(context, _transcript(shown, _exact_error_body(real[:85])))[-1]["content"]
            if not isinstance(first, str):
                raise AssertionError(f"{label}: tool result content changed its wire type")
            check(real[:85] not in first,
                  f"{label}: the shorter cut is protected", f"masked={first[-40:]!r}")
            after: dict[str, str] = dict(_phone_rows(context))
            check(all(after.get(rendering) == original for rendering, original in before.items()),
                  f"{label}: a tool cut never degrades an identity already recorded",
                  f"before={[(len(s), len(o)) for s, o in before.items()]} "
                  f"after={[(len(s), len(o)) for s, o in after.items()]}")

            later: str = real[:86]
            for rendering in after:
                masked: object = _masked(context, _transcript(rendering, _exact_error_body(later)))[-1]["content"]
                if not isinstance(masked, str):
                    raise AssertionError(f"{label}: tool result content changed its wire type")
                check(not _leaks(masked, rendering, later),
                      f"{label}: a LATER, longer cut is protected behind every rendering",
                      f"rendering={rendering[-16:]!r} leaked={_leaks(masked, rendering, later)}")


# --- F2: an unrelated leading number must not swallow the phone fragment -------

def test_a_leading_number_does_not_swallow_the_phone_fragment() -> None:
    """F2. `заказ 12 8 926 547-82` writes an ordinary number immediately before
    the phone with only a separator between them, and the numeric scanner read the
    whole thing as ONE run — `12892654782` names nothing, so the real fragment
    inside it reached the model in the clear (`счёт 5/8 …` and `12/8 …` are the
    same merge). The rule segments a rendered run at its digit-group boundaries
    and protects the segment that carries the value's identity, leaving the
    unrelated head alone. None of these bodies is detected (asserted), so the echo
    pass is the only layer that can protect them."""
    vault, context = _session(CASE_CONVERSATION)
    leaf, real = _mint_phone(context, NUMERIC_USER_MESSAGE)
    check(real == NUMERIC_REAL, "the numeric fixture minted the real it wrote", real)
    fragment: str = "8 926 547-82"
    for label, body_text in (
        ("an order number then the phone", "заказ 12 " + fragment),
        ("a slash code then the phone", "счёт 5/" + fragment),
        ("a slash pair then the phone", "12/" + fragment),
    ):
        body: str = _exact_error_body(body_text)
        check(mask_one(body, context) == body,
              f"the detector declines {label!r} (the control is not vacuous)", "")
        masked: object = _masked(context, _transcript(leaf, body))[-1]["content"]
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result content changed its wire type")
        check(fragment not in masked and leaf in masked,
              f"the phone fragment behind {label} is replaced by the shown substitute",
              f"masked={masked[-60:]!r}")


# --- the trailing-neighbour matrix: the boundary follows the RENDERING ----------

# Generated ONCE and applied to every family, so no family gets a hand-picked
# cell: the separators and punctuation any rendering ends a token at, plus the two
# neighbours that change the answer — a digit (a longer NUMBER) and a letter (a
# longer WORD).
TRAILING_NEIGHBOURS: tuple[tuple[str, str], ...] = (
    ("nothing", ""),
    ("a space", " "),
    ("a double space", "  "),
    ("a comma", ","),
    ("a full stop", "."),
    ("a slash", "/"),
    ("a tab", "\t"),
    ("a newline", "\n"),
    ("a space and a number", " 12"),
    ("a space, a digit and a letter", " 1x"),
    ("a stop, a space and a number", ". 12"),
    ("a space, a number and a stop", " 12."),
    ("a number", "12"),
    ("letters", "бель"),
    ("a space and a word", " едет"),
)

# What a dictated PHONE looks like when the tool cuts it: whole WORDS, so a number
# written after the cut is a different token and not a continuation. The cut is
# mid-word on purpose so the rendering's own edge is a word character; the cut that
# lands ON the value's space is driven separately below, where it belongs.
SPOKEN_CUT: str = REAL_DICTATED[:40]          # «восемь девятьсот двадцать шесть пятьдеся»
# The same number cut in its DIGITS: the rendering IS a number there, so a digit
# run written after the cut does continue it.
NUMERIC_CUT: str = NUMERIC_REAL[:10]          # «8 926 547-»

# (label, the kind of rendering the cut is, the cut, the value being echoed)
MATRIX_FAMILIES: tuple[tuple[str, str, str, _InjectedValue], ...] = (
    ("spoken PHONE", "word", SPOKEN_CUT,
     _InjectedValue(real=REAL_DICTATED, entity_type="PHONE", substitute="8 900 000-00-00")),
    ("numeric PHONE", "number", NUMERIC_CUT,
     _InjectedValue(real=NUMERIC_REAL, entity_type="PHONE", substitute="+7 900 000-00-00")),
    ("NAME", "word", "Анна",
     _InjectedValue(real="Анна", entity_type="NAME", substitute="Татьяна")),
    ("LOC", "word", "ольховая 10",
     _InjectedValue(real="ольховая 10", entity_type="LOC", substitute="вишнёвая 54")),
    ("EMAIL", "email", "a@b.ru",
     _InjectedValue(real="a@b.ru", entity_type="EMAIL", substitute="q@example.ru")),
)

# The separators a number may be written with, restated for the fixture so the
# expectation is read from the POLICY rather than from the function it checks.
_NUMBER_JOINERS: str = " \t()-\u00a0./"
_WORD_JOINERS: str = "_-\u2010\u2011"


def _neighbour_continues(kind: str, neighbour: str) -> bool:
    """What the rendering's own kind makes of the character touching the echo.

    Three different questions — a word is continued by any letter or digit that
    touches it, a number by a digit or by a separator run with a digit behind it,
    an email by a letter, a digit or a character an address is written with — and
    the matrix's expectation is derived from that policy, not from the code.
    """
    if not neighbour:
        return False
    head = neighbour[0]
    if kind == "email":
        return head.isalnum() or head in "._%+-@"
    if kind == "number" and head in _NUMBER_JOINERS:
        rest = neighbour.lstrip(_NUMBER_JOINERS)
        return bool(rest) and rest[0].isdigit()
    return head.isalnum() or head in _WORD_JOINERS


def test_a_number_beside_a_dictated_echo_does_not_unbind_it() -> None:
    """THE BLOCKER, through the public path. The dossier's dictated fragment was
    protected alone and leaked the moment the tool wrote a number after it:
    `REAL_DICTATED[:80] + " 12"` left the customer's own words in the clear, and
    ` 1x`, `. 12`, ` 12.` and a double space did the same. The cause was not the
    detector and not the quantity — it was the BOUNDARY, which asked the VALUE's
    identity (a dictated PHONE canonicalizes to digits) instead of the rendering
    that actually matched (words), so a space followed by a digit was read as a
    continuation of a longer number that is not there. Each body below is declined
    by the detector (asserted), so the echo pass is the only layer that can protect
    it."""
    vault, context = _session(CASE_CONVERSATION)
    shown, real = _mint_phone(context, USER_MESSAGE)
    fragment: str = real[:80]
    check(fragment == TRUNCATED_ECHO, "the headline cut is the dossier's own", "")
    for label, suffix in (
        ("a space and a number", " 12"),
        ("a space, a digit and a letter", " 1x"),
        ("a stop, a space and a number", ". 12"),
        ("a space, a number and a stop", " 12."),
        ("a double space and a number", "  12"),
    ):
        body: str = _exact_error_body(fragment + suffix)
        check(mask_one(body, context) == body,
              f"the detector declines the dictated echo with {label} "
              f"(the control is not vacuous)", "")
        masked: object = _masked(context, _transcript(shown, body))[-1]["content"]
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result content changed its wire type")
        check(not _leaks(masked, shown, fragment) and shown in masked,
              f"the dictated echo followed by {label} is replaced by the shown substitute",
              f"suffix={suffix!r} masked={masked[-60:]!r}")

    # A cut that lands exactly ON the value's own separating space, so the matched
    # rendering ends at the space and the number after it stands on the far side of
    # a token boundary. This is the same leak one character further in: the digit
    # does not touch the words, and only the rendering's own edge can say so.
    spaced: str = real[:32]
    check(spaced.endswith(" ") and spaced != fragment,
          "the second cut ends on the value's own space", repr(spaced[-8:]))
    for label, suffix in (("a space and a number", " 12"), ("a number", "12")):
        body = _exact_error_body(spaced + suffix)
        check(mask_one(body, context) == body,
              f"the detector declines the space-ending cut with {label} "
              f"(the control is not vacuous)", "")
        masked = _masked(context, _transcript(shown, body))[-1]["content"]
        check(isinstance(masked, str) and not _leaks(masked, shown, spaced) and shown in masked,
              f"the space-ending cut followed by {label} is replaced by the substitute",
              f"suffix={suffix!r} masked={masked[-60:]!r}")

    # The same neighbour against a DIGIT rendering must still refuse: the rendering
    # IS a number there and `8 926 547- 12` is a longer number, not an echo. This is
    # the control that stops the fix from deleting the numeric boundary instead of
    # making it follow the rendering.
    numeric_vault, numeric_context = _session(OTHER_CONVERSATION)
    numeric_leaf, numeric_real = _mint_phone(numeric_context, NUMERIC_USER_MESSAGE)
    check(numeric_real == NUMERIC_REAL,
          "the numeric fixture minted the real it wrote", numeric_real)
    for label, suffix in (("a space and a number", " 12"), ("a number", "12")):
        body = _exact_error_body(NUMERIC_REAL[:10] + suffix)
        check(mask_one(body, numeric_context) == body,
              f"the detector declines the numeric run with {label} "
              f"(the control is not vacuous)", "")
        masked = _masked(numeric_context, _transcript(numeric_leaf, body))[-1]["content"]
        check(masked == body,
              f"a numeric rendering with {label} is still read as a longer number",
              f"masked={masked[-50:]!r}")


def test_the_trailing_neighbour_matrix_follows_the_rendering() -> None:
    """Five families at one whole-token cut each, against the same generated
    neighbours. The rule under test is the literal echo rule on its own
    (`_literal_echo_spans`), because for NAME, LOC and EMAIL the detector masks the
    same text first and the public output would hide which layer wrote; the public
    outcome is pinned separately, and for the two PHONE families end to end.

    A neighbour that does NOT continue the rendering ends the token: the echo is
    protected. A neighbour that DOES — a digit after digits, a letter after words —
    makes the whole thing a longer token of that kind: the rule refuses and the
    ordinary longer token is untouched."""
    for label, kind, render, value in MATRIX_FAMILIES:
        for neighbour_label, neighbour in TRAILING_NEIGHBOURS:
            text: str = render + neighbour + "\n"
            spans = _literal_echo_spans(text, value)
            if _neighbour_continues(kind, neighbour):
                check(spans == (),
                      f"{label}: {neighbour_label} continues the {kind} rendering, so "
                      f"the longer token is untouched", f"spans={spans}")
            else:
                check(spans == ((0, len(render)),),
                      f"{label}: {neighbour_label} ends the {kind} rendering, so the "
                      f"echo is protected", f"spans={spans}")

    # The integrator agrees where nothing else can reach: a dictated value has no
    # digit run to scan, so `_echo_spans` returns exactly the literal span.
    spoken = MATRIX_FAMILIES[0][3]
    check(_echo_spans(TRUNCATED_ECHO + " 12\n", spoken) == ((0, len(TRUNCATED_ECHO)),),
          "the dictated echo beside a number is protected through `_echo_spans`", "")

    # And the ordinary longer tokens the matrix refuses are untouched by the public
    # path too, on the families whose detector declines them (asserted per row).
    spoken_context = _session(CASE_CONVERSATION)[1]
    spoken_leaf, _spoken_real = _mint_phone(spoken_context, USER_MESSAGE)
    longer_body: str = _exact_error_body(SPOKEN_CUT + "бель")
    check(mask_one(longer_body, spoken_context) == longer_body,
          "the detector declines a dictation with letters glued on "
          "(the control is not vacuous)", "")
    masked_longer: object = _masked(spoken_context, _transcript(spoken_leaf, longer_body))[-1]["content"]
    check(masked_longer == longer_body,
          "the echo rule leaves a longer word that starts like the dictation untouched",
          f"masked={masked_longer[-50:]!r}")

    name_context = _view(_store(), "matrix-longer-tokens")
    name_leaf = mask_text("Анна", name_context.vault, [Span(0, 4, "NAME", "Анна")])
    name_body: str = _exact_error_body("Аннабель")
    check(mask_one(name_body, name_context) == name_body,
          "the detector declines `Аннабель` (the control is not vacuous)", "")
    masked_name: object = _masked(
        name_context, _association(name_leaf, name_body, field="name"))[-1]["content"]
    check(masked_name == name_body,
          "the echo rule leaves `Аннабель` untouched", f"masked={masked_name!r}")


# --- the over-mask controls: the safe evidence boundary, typed and pinned ------

def test_an_ordinary_flat_head_is_never_read_as_a_phone() -> None:
    """The digit floor cannot be one number, because «the same digits» is not
    evidence on its own. A run that kept the value's separators (or an explicit
    `+`) is a rendered number the tool cut through; a bare flat run has thrown
    that evidence away, and a short one is an ordinary code far more often than a
    truncation — `код 7926547` is the head of the real number and must stay. The
    boundary is pinned from both sides: ten flat digits (the whole significant
    number) are protected, nine are not, and a grouped cut keeps the lower floor."""
    vault, context = _session(CASE_CONVERSATION)
    leaf, real = _mint_phone(context, NUMERIC_USER_MESSAGE)
    digits: str = _digits(real)
    check(len(digits) == 11 and digits[0] in "78",
          "the fixture's identity is an eleven-digit national number", digits)

    refused: tuple[tuple[str, str], ...] = (
        ("an ordinary seven-digit code", "код 7926547"),
        ("an ordinary nine-digit flat run", "код " + digits[:9]),
        ("a six-digit grouped head", "код 8 926 54"),
    )
    for label, body_text in refused:
        body: str = _exact_error_body(body_text)
        check(mask_one(body, context) == body,
              f"the detector declines {label!r} (the control is not vacuous)", "")
        masked: object = _masked(context, _transcript(leaf, body))[-1]["content"]
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result content changed its wire type")
        check(masked == body, f"{label} stays in the clear", f"masked={masked[-50:]!r}")

    protected: tuple[tuple[str, str], ...] = (
        ("the whole significant number, flat", "код " + digits[:10]),
        ("a seven-digit grouped cut", "код 8 926 547"),
    )
    for label, body_text in protected:
        body = _exact_error_body(body_text)
        check(mask_one(body, context) == body,
              f"the detector declines {label!r} (the control is not vacuous)", "")
        masked = _masked(context, _transcript(leaf, body))[-1]["content"]
        check(isinstance(masked, str) and body_text not in masked and leaf in masked,
              f"{label} is still replaced by the shown substitute",
              f"masked={masked[-50:]!r}")


def test_a_short_card_head_is_never_read_as_a_card() -> None:
    """The same control for CARD, and the same typed boundary: a card has no
    trunk and no area code, so a short head of one is any code at all. Ten digits
    of a sixteen-digit card are a real cut and stay protected; seven — flat or
    grouped — do not become a card."""
    value: str = "4111 1111 1111 1111"
    view, context = _session(CASE_CONVERSATION)
    shown: str = mask_text(value, view, [Span(0, len(value), "CARD", value)])

    for label, body_text in (("a flat seven-digit head", "код 4111111"),
                             ("a grouped seven-digit head", "код 4111 111")):
        body: str = _exact_error_body(body_text)
        check(mask_one(body, context) == body,
              f"the detector declines {label!r} (the control is not vacuous)", "")
        masked: object = _masked(context, _association(shown, body, field="card"))[-1]["content"]
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result content changed its wire type")
        check(masked == body, f"{label} stays in the clear", f"masked={masked[-50:]!r}")

    for label, body_text in (("a flat twelve-digit cut", "код 411111111111"),
                             ("a grouped twelve-digit cut", "код 4111 1111 1111")):
        body: str = _exact_error_body(body_text)
        check(mask_one(body, context) == body,
              f"the detector declines {label!r} (the control is not vacuous)", "")
        masked = _masked(context, _association(shown, body, field="card"))[-1]["content"]
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result content changed its wire type")
        check(body_text not in masked and shown in masked,
              f"{label} is still replaced by the shown substitute", f"masked={masked[-50:]!r}")


def test_an_initial_is_not_a_truncation_of_a_name() -> None:
    """The literal floor alone reads any eight-character repetition as a cut, and
    that reading is wrong for a person: «абдулина м.» is an INITIAL — a complete
    way to write the name — and rewriting it with the full substitute expands a
    mention the dialogue never made. The reading is typed, not guessed: for a NAME
    a one-letter last word is an initial, while for a dictated PHONE the same
    fragment is the beginning of a numeral word and carries the digits (the
    truncation ladder above pins that side). A whole-word cut is still protected,
    so the refusal is a policy and not «nothing works here»."""
    value: str = "абдулина мария львовна"
    view, context = _session(CASE_CONVERSATION)
    shown: str = mask_text(value, view, [Span(0, len(value), "NAME", value)])

    initial: str = _exact_error_body("поле name: абдулина м.")
    check(mask_one(initial, context) == initial,
          "the detector declines the initial form (the control is not vacuous)", "")
    masked: object = _masked(context, _association(shown, initial, field="name"))[-1]["content"]
    if not isinstance(masked, str):
        raise AssertionError("tool result content changed its wire type")
    check(masked == initial and value not in masked,
          "an initial is not expanded into the full substitute", f"masked={masked[-50:]!r}")

    whole: str = _exact_error_body("поле name: абдулина")
    check(mask_one(whole, context) == whole,
          "the detector declines the whole first word (the control is not vacuous)", "")
    masked = _masked(context, _association(shown, whole, field="name"))[-1]["content"]
    check(isinstance(masked, str) and "абдулина" not in masked and shown in masked,
          "a whole-word cut is still replaced by the shown substitute",
          f"masked={masked[-50:]!r}")


# --- negative control: an ordinary number is not personal data -----------------

def test_ordinary_number_stays_unmasked() -> None:
    """With the real phone already known to this conversation, an ordinary
    non-personal number in the same error shape must pass through untouched.
    This is the guard against a remedy that masks every digit run."""
    vault, context = _session(CASE_CONVERSATION)
    _mint_phone(context, USER_MESSAGE)
    body = json.dumps(
        {"error": {"code": "not_found", "field": "order_id",
                   "message": "поле order_id: not_found: заказ 1428570, 12 коробок"}},
        ensure_ascii=False,
        indent=2,
    )
    masked = _mask_tool_result(context, body)
    check(masked == body, "an ordinary order number and quantity stay unmasked",
          f"masked={masked!r}")
    check(CANARY_FRAGMENT not in masked, "the ordinary-number body carries no canary", "")


def test_an_armed_call_leaves_ordinary_fields_untouched() -> None:
    """Provenance is live for this call and this result, and the ordinary numbers
    and quantities in it still pass through byte for byte. The numbers are chosen
    at the rule's edge: `926` and `926547` are genuine heads of the real number
    and stay, because below the digit floor an ordinary quantity is at least as
    likely as an echo, and `1428570` is a quantity that is not a head at all."""
    vault, context = _session(CASE_CONVERSATION)
    shown, _real = _mint_phone(context, USER_MESSAGE)
    body = json.dumps(
        {"error": {"code": "not_found", "field": "order_id",
                   "message": "поле order_id: not_found: заказ 1428570, 12 коробок, "
                              "срок 926 дней, код 926547"}},
        ensure_ascii=False,
        indent=2,
    )
    masked = _masked(context, _transcript(shown, body))[-1]["content"]
    check(masked == body, "ordinary numbers survive an armed call", f"masked={masked!r}")
    check(CANARY_FRAGMENT not in masked, "the ordinary body carries no canary", "")


# --- typed boundaries: an echo is a truncation, never a slice -------------------

def test_a_typed_echo_never_slices_a_longer_token() -> None:
    """`Анна` must not rewrite `Аннабель`, `ольховая 10` must not rewrite
    `ольховая 105`, and an email prefix must not rewrite another domain.

    The name is measured through `mask_messages` on a body the detector DECLINES
    (asserted, so the control cannot silently become a test of the detector); the
    other two are measured on the matcher itself, because the detector masks those
    longer tokens first and the public output would hide which layer wrote."""
    store = _store()
    context = _view(store, "boundary-names")
    shown = mask_text("Анна", context.vault, [Span(0, 4, "NAME", "Анна")])
    longer = "Аннабель ответила"
    check(mask_one(longer, context) == longer,
          "the detector declines the longer token (the control is not vacuous)", "")
    masked_longer = _masked(context, _association(shown, longer, field="name"))[-1]["content"]
    check(masked_longer == longer,
          "`Анна` does not rewrite `Аннабель`",
          f"masked={masked_longer!r}")
    bounded = "Анна, добрый день"
    masked_bounded = _masked(context, _association(shown, bounded, field="name"))[-1]["content"]
    check(masked_bounded == shown + ", добрый день",
          "the same value IS rewritten where the token really ends",
          f"masked={masked_bounded!r}")

    place = _InjectedValue(real="ольховая 10", entity_type="LOC", substitute="вишнёвая 54")
    check(_echo_spans("ольховая 105 стоит", place) == (),
          "`ольховая 10` does not rewrite `ольховая 105`", "")
    check(_echo_spans("ольховая 10, кв 5", place) == ((0, 11),),
          "the place is still found where the house number really ends", "")

    mail = _InjectedValue(real="a@b.ru", entity_type="EMAIL", substitute="q@example.ru")
    check(_echo_spans("a@b.ru.com отклонил", mail) == (),
          "an email prefix does not rewrite another domain", "")
    check(_echo_spans("письмо a@b.ru, принято", mail) == ((7, 13),),
          "the email is still found where the address really ends", "")


def test_numeric_echoes_with_separators_are_typed_not_generic() -> None:
    """A typed numeric echo may come back in ANY rendering of the same number —
    separated, re-trunked, contiguous — and must be replaced by the substitute the
    model wrote; an ordinary quantity shares no head with the value and is left
    alone. None of the truncated bodies below is detected (asserted), so the echo
    pass is the only layer that can protect them."""
    vault, context = _session(CASE_CONVERSATION)
    numeric_leaf, real = _mint_phone(context, NUMERIC_USER_MESSAGE)
    check(real == NUMERIC_REAL, "the numeric fixture minted the real it wrote", real)
    for label, echo in (
        ("separated with the other trunk", "7 926 547-82"),
        ("contiguous, no separators", "+792654782"),
        ("national, separated", "8 926 547-82"),
    ):
        body = _exact_error_body(echo)
        check(mask_one(body, context) == body,
              f"the detector declines {label!r} (the control is not vacuous)", "")
        masked = _masked(context, _transcript(numeric_leaf, body))[-1]["content"]
        check(echo not in masked and numeric_leaf in masked,
              f"the {label} echo is replaced by the shown substitute",
              f"masked={masked[-60:]!r}")


# --- cost: one index per pass, and no detector work ----------------------------

def test_provenance_is_indexed_once_per_pass_and_costs_no_detector_work() -> None:
    """Bounded call-count evidence, not a benchmark. The dialogue's shown forms are
    read ONCE per masking pass however many content blocks or associated results
    the pass carries, and the echo pass calls the detector ZERO times: the leaf is
    resolved through the vault's own indexes. The revision this replaces ran a
    full detection over every call's arguments once per content block, which is
    what made a growing transcript quadratic in detector work."""
    detector = Detector()
    plain_detect = detector.detect
    seen = {"detect": 0}

    def counted_detect(text: str) -> list[Span]:
        seen["detect"] += 1
        return plain_detect(text)

    detector.detect = counted_detect           # instance-local, no global state
    store = _store()
    view = store.for_conversation(CASE_CONVERSATION)
    plain_forms = view.shown_forms
    reads = {"shown": 0}

    def counted_forms() -> list[tuple[str, str, str]]:
        reads["shown"] += 1
        return plain_forms()

    view.shown_forms = counted_forms
    context = MaskContext(detector=detector, vault=view, audit=AuditLog(":memory:"),
                          cache=MaskCache(256), org_id=CASE_ORG, agent_id="s0",
                          conversation_id=CASE_CONVERSATION)
    shown, _real = _mint_phone(context, USER_MESSAGE)
    blocks: list[dict[str, object]] = [{"type": "text", "text": DOSSIER_ERROR_REAL}
                                       for _ in range(3)]

    reads["shown"] = 0
    seen["detect"] = 0
    masked = _masked(context, _association(shown, blocks))
    with_association: int = seen["detect"]
    panel = masked[-1]["content"]
    check(reads["shown"] == 1,
          "the shown-form index is read once for a three-block result",
          f"reads={reads['shown']}")
    check(isinstance(panel, list) and all(CANARY_FRAGMENT not in block["text"] for block in panel),
          "every block of the multipart result is protected", "")

    unassociated = _association(shown, blocks)
    del unassociated[-1]["tool_call_id"]
    plain_context = MaskContext(detector=detector, vault=view, audit=AuditLog(":memory:"),
                                cache=MaskCache(256), org_id=CASE_ORG, agent_id="s0",
                                conversation_id=CASE_CONVERSATION)
    seen["detect"] = 0
    _masked(plain_context, unassociated)
    check(seen["detect"] == with_association,
          "the echo pass adds no detector work at all",
          f"{with_association} with association, {seen['detect']} without")

    reads["shown"] = 0
    growing = _association(shown, blocks, call_id="grow-1") + \
        _association(shown, blocks, call_id="grow-2")
    grown = _masked(context, growing)
    check(reads["shown"] == 1,
          "a second associated result in the same pass reuses that index",
          f"reads={reads['shown']}")
    check(CANARY_FRAGMENT not in grown[-1]["content"] and CANARY_FRAGMENT not in grown[-3]["content"],
          "both results of the growing transcript are protected", "")


# --- refusal: only a unique preceding call grants provenance -------------------

def test_only_a_unique_preceding_call_grants_provenance() -> None:
    """Missing, future, duplicate, mismatched, unparseable and unrelated evidence
    must each refuse. The first row proves the same bytes ARE protected when the
    evidence is sound, so the refusals are not vacuous."""
    vault, context = _session(CASE_CONVERSATION)
    shown, _real = _mint_phone(context, USER_MESSAGE)
    user: dict[str, object] = {"role": "user", "content": USER_MESSAGE}
    call = _call_message(MATRIX_CALL, shown)
    result: dict[str, object] = {"role": "tool", "tool_call_id": MATRIX_CALL,
                                 "content": DOSSIER_ERROR_REAL}
    rows: list[tuple[str, list[dict[str, object]], int]] = [
        ("armed control", _transcript(shown, DOSSIER_ERROR_REAL), 2),
        ("unmatched id", [user, {"role": "assistant", "tool_calls": [call]},
                          {**result, "tool_call_id": "never-declared"}], 2),
        ("future declaration", [user, result, {"role": "assistant", "tool_calls": [call]}], 1),
        ("duplicate id", [user, {"role": "assistant", "tool_calls": [call]},
                          {"role": "assistant", "tool_calls": [call]}, result], 3),
        ("mismatched tool name", [user, {"role": "assistant", "tool_calls": [call]},
                                  {**result, "name": "other_tool"}], 2),
        ("unparseable arguments", [user, {"role": "assistant", "tool_calls": [
            {"id": MATRIX_CALL, "type": "function",
             "function": {"name": "ticket_find", "arguments": "{"}}]}, result], 2),
        ("a leaf this call never carried",
         _transcript(OTHER_REAL_LEAF, DOSSIER_ERROR_REAL), 2),
        ("a bare result with no call at all", [user, result], 1),
    ]
    for label, messages, index in rows:
        masked = _masked(context, messages)[index]["content"]
        if not isinstance(masked, str):
            raise AssertionError(f"{label}: tool result content changed its wire type")
        if label == "armed control":
            check(CANARY_FRAGMENT not in masked,
                  "the armed control loses the fragment (so the refusals mean something)",
                  "")
        else:
            # THE REFUSAL BOUNDS ATTRIBUTION, NOT PRIVACY. When the binding is
            # refused the dialogue still recorded this identity itself, so the
            # echo must be conservatively redacted — and because no call was
            # bound, no person's substitute may be guessed. The old suite pinned
            # the opposite (`masked == DOSSIER_ERROR_REAL`); that is the leak
            # S01 exists to remove.
            check(CANARY_FRAGMENT not in masked,
                  f"{label}: the recorded echo is redacted without a binding", "")
            check(shown not in masked and _real not in masked,
                  f"{label}: no person's substitute is guessed", "")


# --- no minting ----------------------------------------------------------------

def test_protecting_an_echo_mints_no_new_substitute() -> None:
    """The same association and the same arguments, with and without the result.
    The only thing the result adds is the echo pass, and it must reuse the
    substitute the model already holds rather than minting a second one."""
    vault, context = _session(CASE_CONVERSATION)
    shown, _real = _mint_phone(context, USER_MESSAGE)
    call = _call_message(MATRIX_CALL, shown)
    user: dict[str, object] = {"role": "user", "content": USER_MESSAGE}
    _masked(context, [user, {"role": "assistant", "tool_calls": [call]}])
    rows: int = len(vault.shown_forms())
    transcript: list[dict[str, object]] = [
        user, {"role": "assistant", "tool_calls": [call]},
        {"role": "tool", "tool_call_id": MATRIX_CALL, "content": DOSSIER_ERROR_REAL}]
    masked = _masked(context, transcript)[-1]["content"]
    check(CANARY_FRAGMENT not in masked, "the result is protected", "")
    check(len(vault.shown_forms()) == rows,
          "the echo pass mints no new substitute",
          f"{rows} row(s) before, {len(vault.shown_forms())} after")


# --- false attribution: one store, two conversation views ----------------------

def test_other_conversation_fragment_is_not_falsely_attributed() -> None:
    """One tenant store with two conversation VIEWS. B has a DIFFERENT real phone
    and never injected the canary fragment into a tool call, so presenting the
    fragment in B must not resolve it to A's person's substitute or to B's:
    the value memory a remedy keys on is scoped to the conversation that
    actually restored it."""
    store = _store()
    context_a = _view(store, CASE_CONVERSATION)
    shown_a, real_a = _mint_phone(context_a, USER_MESSAGE)
    context_b = _view(store, OTHER_CONVERSATION)
    shown_b, real_b = _mint_phone(context_b, OTHER_USER_MESSAGE)

    check(real_a == REAL_DICTATED and real_b == OTHER_REAL and shown_a != shown_b,
          "two different real phones live in one store under two substitutes",
          f"{shown_a} vs {shown_b}")

    body = json.dumps(
        {"error": {"code": "not_found", "field": "phone",
                   "message": "поле phone: not_found: " + TRUNCATED_ECHO}},
        ensure_ascii=False,
        indent=2,
    )
    masked_b = _mask_tool_result(context_b, body)
    check(CANARY_FRAGMENT in masked_b,
          "B does not protect a fragment it never carried", "")
    check(shown_a not in masked_b,
          "conversation B does not attribute the fragment to A's person",
          f"A substitute {shown_a} absent")
    check(shown_b not in masked_b,
          "conversation B does not attribute the fragment to B's own person",
          f"B substitute {shown_b} absent")


def test_another_conversations_value_is_not_attributed_to_this_call() -> None:
    """Conversation B has its OWN armed call in the same store, and the tool echoes
    A's fragment. B's substitute must not land on A's words — and B's own
    truncated echo must still be protected, so the refusal is not "nothing works
    here"."""
    store = _store()
    context_a = _view(store, CASE_CONVERSATION)
    shown_a, _real_a = _mint_phone(context_a, USER_MESSAGE)
    context_b = _view(store, OTHER_CONVERSATION)
    shown_b, real_b = _mint_phone(context_b, OTHER_USER_MESSAGE)

    foreign = _masked(context_b, _transcript(shown_b, DOSSIER_ERROR_REAL))[-1]["content"]
    check(CANARY_FRAGMENT in foreign and shown_a not in foreign and shown_b not in foreign,
          "conversation B's armed call does not reach A's fragment",
          f"B substitute {shown_b!r} absent")

    cut: str = real_b[:11]                 # a truncated digital echo of B's own real
    own = _masked(context_b, _transcript(shown_b, _exact_error_body(cut)))[-1]["content"]
    check(cut not in own and shown_b in own,
          "conversation B's own truncated echo is still protected",
          f"masked={own[-70:]!r}")


def test_an_unbound_result_is_redacted_without_guessing_a_person() -> None:
    """THE UNBOUND LEG. A tool message with no declaration at all, whose body
    echoes a value this conversation itself restored. The dialogue therefore knows
    the value and must not let it through — but it does NOT know whose the result
    is about, so it may not answer with anybody's substitute. The replacement is a
    neutral redaction, and the privacy leg mints no vault row and records no audit
    event: the value was billed when its substitute was minted."""
    vault, context = _session(CASE_CONVERSATION)
    shown, real = _mint_phone(context, USER_MESSAGE)
    rows: int = len(vault.shown_forms())
    events: int = len(context.audit.recent(CASE_ORG, 500))
    masked = _mask_tool_result(context, _exact_error_body(TRUNCATED_ECHO))
    check(CANARY_FRAGMENT not in masked and real not in masked,
          "an unbound result loses the recorded real echo", f"masked={masked[-60:]!r}")
    check(shown not in masked,
          "the unbound redaction is not a person's substitute", "")
    check("REDACTED" in masked,
          "the unbound answer is a neutral redaction", f"masked={masked[-60:]!r}")
    check(len(vault.shown_forms()) == rows and len(context.audit.recent(CASE_ORG, 500)) == events,
          "the unbound redaction mints no vault row and no audit event",
          f"rows {rows}->{len(vault.shown_forms())}")


def test_a_matched_name_replay_uses_the_current_rendering() -> None:
    """THE FORM THE MODEL READS IN THIS REQUEST, for the non-numeric family.

    The transcript replays the dialogue's OWN shown NAME, retyped by the model in
    another case — the shape that used to be re-minted into a second substitute
    (a fake-of-a-fake vault row and a billed audit event). The call is matched, so
    the result is answered with the exact rendering this request carries, for the
    FULL mention and for the 8-character cut; the real name never appears, no row
    is added, and no audit event is recorded by the result leg."""
    vault, context = _session(CASE_CONVERSATION)
    _mint_phone(context, USER_MESSAGE)              # also mints the NAME below
    shown, real = _showed_name(context)
    leaf: str = shown                            # the rendering the model was shown
    rows: int = len(vault.shown_forms())
    events: int = len(context.audit.recent(CASE_ORG, 500))
    for label, echoed in (("full mention", real), ("8-character cut", real[:8])):
        transcript: list[dict[str, object]] = [
            {"role": "user", "content": USER_MESSAGE},
            {"role": "assistant", "tool_calls": [_call_message(MATRIX_CALL, leaf, field="name")]},
            {"role": "tool", "tool_call_id": MATRIX_CALL,
             "content": _exact_error_body(echoed)},
        ]
        masked: list[dict[str, object]] = _masked(context, transcript)
        calls = masked[1]["tool_calls"]
        if not isinstance(calls, list) or not isinstance(calls[0], dict):
            raise AssertionError("the masked call lost its shape")
        visible: object = json.loads(str(calls[0]["function"]["arguments"])).get("name")
        result = masked[-1]["content"]
        check(isinstance(result, str) and real not in result,
              f"{label}: the real name never reaches the model",
              f"result={str(result)[-40:]!r}")
        if label == "full mention":
            check(isinstance(visible, str) and visible in str(result),
                  f"{label}: the echo is the rendering this request reads",
                  f"visible={visible!r}")
            check(shown not in str(result) or shown == visible,
                  f"{label}: no older substitute is re-used", "")
            # Rows are the mint count. `events` moves by the DETECTOR's own
            # event for the real name in the result body — a value that really is
            # personal data — so the echo pass owns the row assertion, and
            # `test_protecting_an_echo_mints_no_new_substitute` pins that the
            # result leg adds no second substitute across two passes.
            check(len(vault.shown_forms()) == rows,
                  "the matched NAME replay adds no fake-of-a-fake row",
                  f"rows {rows}->{len(vault.shown_forms())}")
        # The replay must never make a substitute out of a substitute: the
        # dialogue's own rendering is not a value, and its `original` column may
        # not hold one.
        check(not any(original == shown for _s, original, _k in vault.shown_forms()),
              f"{label}: no fake-of-a-fake vault row", "")
    # The 8-character cut is DETECTED as a partial real name, so detection mints
    # for that partial value — that is the detector's own behaviour and not the
    # echo pass re-minting our substitute. The fake-of-a-fake assertion above
    # states the part this change owns: no row's `original` is one of our
    # renderings, whichever cut the tool wrote.
    check(not any(original == shown for _s, original, _k in vault.shown_forms()),
          "no cut of the replay turns a substitute into a value", "")


def test_a_retyped_name_replay_carries_its_current_case_into_the_result() -> None:
    """E01, the non-numeric family: the CURRENT request's form, not the mint's.

    The call leaf is the dialogue's own shown NAME RETYPED by the model in lower
    or UPPER case, and the tool result echoes the FULL real name and its
    8-character cut. E01's defect is that the generic detector consumes the real
    span first and answers with the substitute's canonical title case, so the
    model reads `наумов мирослав николаевич` in the call and `Наумов …` in the
    result: one identity, two renderings, and the second was never in this
    request. The assertion is a COMPARISON between the two leaves of one request
    — the model-visible call leaf and the result replacement at that mention —
    not a hard-coded substitute.

    The cut is the second half of the rule: the tool cut the value, so only the
    part of the substitute standing where the cut stood may come back, in the
    current case, once. Replacing the cut with the WHOLE substitute, or with a
    title-case word while the leaf is lower, is the P2 residual this closes."""
    for label, recase in (("lower", str.lower), ("upper", str.upper)):
        vault, context = _session(f"e01-name-{label}")
        shown: str = mask_text(LITERAL_NAME, context.vault,
                               [Span(0, len(LITERAL_NAME), "NAME", LITERAL_NAME)])
        leaf: str = recase(shown)
        check(leaf != shown, f"{label}: the lane is a real case retype (not the mint)", f"shown={shown!r}")
        rows: int = len(vault.shown_forms())
        for kind, echoed in (("full mention", LITERAL_NAME), ("8-character cut", LITERAL_NAME[:8])):
            masked: list[dict[str, object]] = _masked(
                context, _association(leaf, _exact_error_body(echoed), field="name"))
            calls = masked[0]["tool_calls"]
            if not isinstance(calls, list) or not isinstance(calls[0], dict):
                raise AssertionError(f"{label}/{kind}: the masked call lost its shape")
            visible: object = json.loads(str(calls[0]["function"]["arguments"])).get("name")
            result: object = masked[-1]["content"]
            if not isinstance(visible, str) or not isinstance(result, str):
                raise AssertionError(f"{label}/{kind}: a leaf changed its wire type")
            check(visible == leaf,
                  f"{label}/{kind}: the model reads the case it wrote",
                  f"leaf={visible!r}")
            check(echoed not in result and not _leaks(result, visible, echoed),
                  f"{label}/{kind}: no raw real fragment survives",
                  f"result={result[-48:]!r}")
            head: str = visible.split(" ")[0]
            if kind == "full mention":
                check(result.count(visible) == 1,
                      f"{label}/{kind}: the result carries the current-case rendering once",
                      f"result={result[-48:]!r}")
                check(shown not in result or shown == visible,
                      f"{label}/{kind}: the mint's canonical case is not re-imposed", "")
            else:
                check(head in result,
                      f"{label}/{kind}: the cut keeps the current case and projection",
                      f"head={head!r} result={result[-48:]!r}")
                check(result.count(head) == 1,
                      f"{label}/{kind}: the cut is not doubled", "")
                check(shown.split(" ")[0] not in result or shown.split(" ")[0] == head,
                      f"{label}/{kind}: the cut does not fall back to the mint's case", "")
        check(len(vault.shown_forms()) == rows,
              f"{label}: a retyped replay adds no fake-of-a-fake row",
              f"rows {rows}->{len(vault.shown_forms())}")


def test_the_cache_key_carries_the_own_rendering_evidence() -> None:
    """THE CACHE KEY MUST CARRY EVERY INPUT THE OUTPUT DEPENDS ON.

    A NAME JOINED FROM SEPARATE PART-SUBSTITUTES masks DIFFERENTLY depending on
    whether the caller can see that the parts are ours: evidence-free it is
    re-minted (the fake-of-a-fake), evidence-bearing it is left alone. Both orders
    are driven through the public entry points, because a cache keyed on
    `(org, conversation, text)` alone serves whichever ran first — and the answer
    must follow the CURRENT evidence, never the earlier call's.

    THE VEHICLE MOVED WITH CLASS В (`research/hop-format-audit/SPIKE-В.md`), the
    property did not. The vehicle used to be a re-cased WHOLE rendering, and that
    string stopped discriminating when the identity rule landed in
    `is_own_substitute` (`vault.name_rendering_is_ours`): the owner's decision is
    «производная форма СВОЕЙ подмены пропускается как своя», without an evidence
    caveat, so BOTH readings now leave it alone — stated as a check of its own
    below, so the change is pinned rather than merely absent. What still
    discriminates is the case no list of exact renderings can enumerate: parts
    shown APART and joined by the model, which is `_is_own_composition`'s own
    case and stays evidence-gated, because its evidence — which renderings this
    dialogue showed — is what the cache key carries."""
    # ORDER 1 — evidence first, then the evidence-free reading.
    _vault, context = _session(CASE_CONVERSATION)
    _mint_phone(context, USER_MESSAGE)
    text: str = json.dumps({"name": _mint_part_names(context).lower()}, ensure_ascii=False)
    provenance = _Provenance(context)
    provenance.snapshot()
    guarded = _mask_one(text, context, provenance.own_renderings())
    plain = mask_one(text, context)
    check(guarded == text,
          "with evidence a NAME joined from separate parts is left as it is (order 1)",
          f"guarded={guarded!r}")
    check(plain != text,
          "without evidence the same text is NOT served the evidence-bearing result (order 1)",
          f"plain={plain!r}")

    # ORDER 2 — evidence-free first, then the guarded reading.
    _vault2, context2 = _session(CASE_CONVERSATION)
    _mint_phone(context2, USER_MESSAGE)
    text2: str = json.dumps({"name": _mint_part_names(context2).lower()}, ensure_ascii=False)
    plain2 = mask_one(text2, context2)
    provenance2 = _Provenance(context2)
    provenance2.snapshot()
    guarded2 = _mask_one(text2, context2, provenance2.own_renderings())
    check(plain2 != text2,
          "without evidence the joined NAME is re-minted (order 2)", f"plain={plain2!r}")
    check(guarded2 == text2,
          "with evidence the same text is NOT served the evidence-free result (order 2)",
          f"guarded={guarded2!r}")

    # THE CLASS-В RULE THIS VEHICLE USED TO PIN, NOW UNCONDITIONAL. A re-cased
    # rendering of ONE substitute is the string the dialogue itself showed, read
    # through the case axis — and it is OUR rendering whichever reading asks, the
    # evidence-free one included. The decision is the owner's and it is
    # deliberately not gated on the caller's evidence: the frozen benchmark
    # scorer calls the same `is_own_substitute` without it
    # (`bench/agentpii3/score.py`), and a rule that lives in the envelope instead
    # is how production and the instrument came to disagree about one text.
    _vault3, context3 = _session(CASE_CONVERSATION)
    _mint_phone(context3, USER_MESSAGE)
    shown3, _real3 = _showed_name(context3)
    retyped: str = json.dumps({"name": shown3.lower()}, ensure_ascii=False)
    provenance3 = _Provenance(context3)
    provenance3.snapshot()
    check(_mask_one(retyped, context3, provenance3.own_renderings()) == retyped,
          "a re-cased own NAME is a fixed point WITH evidence",
          f"guarded={_mask_one(retyped, context3, provenance3.own_renderings())!r}")
    check(mask_one(retyped, context3) == retyped,
          "a re-cased own NAME is a fixed point WITHOUT evidence (class В)",
          f"plain={mask_one(retyped, context3)!r}")


def test_a_bound_call_never_attributes_a_value_it_did_not_carry() -> None:
    """THE WRONG-CALL NEGATIVE, AND THE EXACT POLICY IT PINS.

    Two phones are recorded in ONE dialogue. The result is bound to call B (its
    leaf is B's substitute, the id matches), and it echoes A's undetectable
    dictated fragment. Policy, stated so it is a decision rather than an accident:

      * attribution is CALL-scoped — the bound call's own value is answered with
        the substitute this request shows (`shown_b`), and nothing else is;
      * privacy is CONVERSATION-scoped — an echo of a value the dialogue itself
        restored is conservatively REDACTED, because leaving it raw would put real
        personal data in the prompt;
      * the conservative answer carries NO identity: neither B's substitute (the
        wrong person for this echo) nor A's substitute (a person this call never
        carried) may appear.

    So the bound call does not license a substitute for A's value, and it does not
    license leaving A's value raw either."""
    store = _store()
    context = _view(store, CASE_CONVERSATION)
    shown_a, real_a = _mint_phone(context, USER_MESSAGE)
    second: dict[str, object] = {"role": "user",
                                 "content": "ещё телефон " + OTHER_REAL + " звоните"}
    _mask(context, [second])
    rows: list[tuple[str, str]] = [(shown, original) for shown, original, kind
                                   in context.vault.shown_forms() if kind == "PHONE"]
    shown_b, real_b = next((shown, original) for shown, original in rows
                           if original == OTHER_REAL)
    ordinary: str = "заказ 1428570, 12 коробок"
    body: str = json.dumps(
        {"error": {"code": "not_found", "field": "phone",
                   "message": f"поле phone: not_found: {CANARY_FRAGMENT}; {ordinary}"}},
        ensure_ascii=False, indent=2)
    masked = _masked(context, [
        second,
        {"role": "assistant", "tool_calls": [_call_message(MATRIX_CALL, shown_b)]},
        {"role": "tool", "tool_call_id": MATRIX_CALL, "content": body},
    ])[-1]["content"]
    check(isinstance(masked, str) and CANARY_FRAGMENT not in masked,
          "the dialogue redacts the echo it recorded, bound call or not",
          f"masked={str(masked)[-70:]!r}")
    check(isinstance(masked, str) and real_a not in masked,
          "the bound call does not license A's real value either", "")
    check(isinstance(masked, str) and shown_b not in masked,
          "the bound call's substitute is NOT attributed to A's echo", "")
    check(isinstance(masked, str) and shown_a not in masked,
          "A's substitute is not attributed to an echo the call never carried", "")
    check(isinstance(masked, str) and ordinary in masked,
          "an ordinary quantity in the same body is untouched", "")

    own = _masked(context, [
        second,
        {"role": "assistant", "tool_calls": [_call_message(MATRIX_CALL, shown_b)]},
        {"role": "tool", "tool_call_id": MATRIX_CALL,
         "content": _exact_error_body(real_b)},
    ])[-1]["content"]
    check(isinstance(own, str) and real_b not in own and shown_b in own,
          "the bound call's OWN echo is still answered with its current substitute",
          f"masked={str(own)[-60:]!r}")


def test_a_payload_marker_neither_survives_nor_displaces_a_substitute() -> None:
    """THE MARKER IS THE ENGINE'S, AND THE PAYLOAD CANNOT FORGE OR REPLACE IT.

    `_reserve_echoes` lifts a bound echo out of the result under a NUL-delimited
    marker and `_splice_reserved` puts the substitute back where the marker
    survived. A tool result that LITERALLY carries marker-shaped bytes used to be
    targeted instead of the generated span: the payload's bytes were overwritten
    with a substitute the request never carried in that field, while the engine's
    own marker survived raw into the provider-visible body — a control byte
    reaching the provider and a substitute mis-positioned.

    The fix must hold two things at once, so both are asserted: every claimed real
    value is ABSENT and the unrelated email in the same body is masked, while the
    bytes the engine did not generate are left exactly where the payload wrote
    them. `NUMERIC_REAL` is a formatted domestic phone, so this fixture isolates
    the marker from the notation clause `envelope_warm_notation` pins."""
    _, context = _session("marker-forgery")
    shown, _real = _mint_phone(context, NUMERIC_USER_MESSAGE)
    marker: str = "\x00EO0\x01"
    body: str = ('{"a": "' + marker + '", "b": "' + NUMERIC_REAL + '", '
                 '"c": "unrelated@mail.ru"}')
    masked = _masked(context, [{"role": "user", "content": NUMERIC_USER_MESSAGE}]
                     + _association(shown, body))[-1]["content"]
    if not isinstance(masked, str):
        raise RuntimeError("masked marker body was not a string")
    fields: dict[str, str] = dict(re.findall(r'"([abc])": "([^"]*)"', masked))
    check(_digits(NUMERIC_REAL) not in _digits(masked),
          "the echoed real phone is absent from the marker body", f"masked={masked!r}")
    check("unrelated@mail.ru" not in masked,
          "the unrelated email beside the marker is still masked", f"masked={masked!r}")
    check(fields.get("a") == marker,
          "the payload's own marker-shaped bytes are NOT overwritten",
          f"a={fields.get('a')!r}")
    check("\x00" not in masked.replace(marker, ""),
          "no engine-generated marker byte survives into the provider body",
          f"masked={masked!r}")
    check(fields.get("b") is not None
          and canonicalize("PHONE", fields["b"]) == canonicalize("PHONE", shown),
          "the substitute landed on the echoed span, not on the payload's literal",
          f"b={fields.get('b')!r} shown={shown!r}")
    lone = _mask_tool_result(context, '{"a": "' + marker + '", "b": "ordinary"}')
    check(marker in lone and "ordinary" in lone,
          "a payload marker with no claim at all is left as the payload wrote it",
          f"masked={lone!r}")


def main() -> int:
    test_the_leak_is_a_fragment_not_the_whole_number()
    test_error_echo_is_protected()
    test_a_literal_shown_leaf_protects_archived_truncations()
    test_a_retyped_substitute_is_still_this_dialogue_s_rendering()
    test_every_truncation_of_the_injected_value_is_protected()
    test_truncated_numeric_renderings_with_dots_and_slashes()
    test_only_this_dialogue_s_own_record_grants_provenance()
    test_reproduced_error_echo_is_protected()
    test_a_restored_real_leaf_grants_provenance()
    test_a_mixed_replayed_call_reads_both_forms_per_leaf()
    test_untruncated_echo_is_masked()
    test_a_shorter_truncation_never_degrades_the_dialogue_s_evidence()
    test_a_leading_number_does_not_swallow_the_phone_fragment()
    test_a_number_beside_a_dictated_echo_does_not_unbind_it()
    test_the_trailing_neighbour_matrix_follows_the_rendering()
    test_an_ordinary_flat_head_is_never_read_as_a_phone()
    test_a_short_card_head_is_never_read_as_a_card()
    test_an_initial_is_not_a_truncation_of_a_name()
    test_ordinary_number_stays_unmasked()
    test_an_armed_call_leaves_ordinary_fields_untouched()
    test_a_typed_echo_never_slices_a_longer_token()
    test_numeric_echoes_with_separators_are_typed_not_generic()
    test_provenance_is_indexed_once_per_pass_and_costs_no_detector_work()
    test_only_a_unique_preceding_call_grants_provenance()
    test_protecting_an_echo_mints_no_new_substitute()
    test_other_conversation_fragment_is_not_falsely_attributed()
    test_another_conversations_value_is_not_attributed_to_this_call()
    test_an_unbound_result_is_redacted_without_guessing_a_person()
    test_a_matched_name_replay_uses_the_current_rendering()
    test_a_retyped_name_replay_carries_its_current_case_into_the_result()
    test_the_cache_key_carries_the_own_rendering_evidence()
    test_a_bound_call_never_attributes_a_value_it_did_not_carry()
    test_a_payload_marker_neither_survives_nor_displaces_a_substitute()
    failed = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 72)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("error echo privacy NOT in place:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("a tool error carrying a known real fragment is masked before the model reads it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
