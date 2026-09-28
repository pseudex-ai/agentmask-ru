"""Transformations over the OpenAI chat wire envelope — the part both deployment
shapes share.

`proxy.py` (we call the provider) and `service.py` (a host gateway calls us) each
carried their own copy of this traversal and DRIFTED: multi-part content blocks,
the mask cache and the template skip existed only in the sidecar, so the proxy leg
silently masked less than the sidecar did. Owning the traversal here means a newly
handled message field lands on both legs at once, or on neither — never on one.

The envelope is walked, not the transport: nothing here knows whether the caller
forwards the request itself or hands it back to a host gateway.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

from pseudex.audit import AuditLog
from pseudex.detect import Span
from pseudex.detect_all import Detector
from pseudex.maskcache import MaskCache, content_key
from pseudex.profiling import stage
from pseudex.redact import (_digits_in_form_of, is_own_substitute, mask_text,
                            tokenize_span, unmask_arguments, unmask_text)
from pseudex.vault import Vault, canonicalize, fold_key


@dataclass(frozen=True)
class MaskContext:
    """Everything one masking pass needs. Grouped so the traversal functions stay
    readable and a new dependency doesn't ripple through every signature."""

    detector: Detector
    vault: Vault
    audit: AuditLog
    cache: MaskCache
    org_id: str
    agent_id: str
    # The conversation this pass belongs to, empty when the caller names none.
    # Part of the cache key and the vault view — see `content_key` and
    # `Vault.for_conversation` for why a link decided here must not escape it.
    conversation_id: str


@dataclass(frozen=True)
class ToolCallContext:
    """An earlier wire call, not an inferred provider ID or a restored value."""

    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ToolResultContext:
    """Association evidence for one message; uncertainty is not a matched call."""

    status: Literal["not_result", "matched", "missing", "ambiguous", "invalid"]
    call: ToolCallContext | None


def _read_tool_call(call: dict[str, object], call_id: str) -> ToolCallContext | None:
    function = call.get("function")
    if call.get("type") != "function" or not isinstance(function, dict):
        return None
    name = function.get("name")
    arguments = function.get("arguments")
    if not isinstance(name, str) or not name or not isinstance(arguments, str):
        return None
    try:
        parsed: object = json.loads(arguments)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return ToolCallContext(call_id=call_id, name=name, arguments=arguments)


def tool_result_contexts(messages: list[dict[str, object]]) -> tuple[ToolResultContext, ...]:
    """Bind each result to its unique preceding standard assistant call.

    This pure transcript reader holds no cross-request or cross-conversation
    state. IDs, never function names or adjacency, bind parallel calls. A
    repeated ID poisons subsequent associations even when both calls look
    identical. Future declarations cannot establish or rewrite past evidence.

    Arguments retain their wire representation. This function neither unmasks
    them nor grants permission to treat every matching substring as PII. The
    caller still needs typed value/field evidence before masking an echo.
    """
    seen: dict[str, ToolCallContext | None] = {}
    duplicated: set[str] = set()
    contexts: list[ToolResultContext] = []
    for message in messages:
        if message.get("role") == "assistant":
            calls = message.get("tool_calls")
            if isinstance(calls, list):
                for call in calls:
                    if not isinstance(call, dict):
                        continue
                    call_id = call.get("id")
                    if not isinstance(call_id, str) or not call_id:
                        continue
                    if call_id in seen:
                        duplicated.add(call_id)
                    else:
                        seen[call_id] = _read_tool_call(call, call_id)
        if message.get("role") != "tool":
            contexts.append(ToolResultContext(status="not_result", call=None))
            continue
        result_id = message.get("tool_call_id")
        if not isinstance(result_id, str) or not result_id or result_id not in seen:
            contexts.append(ToolResultContext(status="missing", call=None))
        elif result_id in duplicated:
            contexts.append(ToolResultContext(status="ambiguous", call=None))
        else:
            earlier: ToolCallContext | None = seen[result_id]
            # `name` IS OPTIONAL ON THE WIRE, AND `null` SPELLS ITS ABSENCE. A
            # provider that writes `"name": null` is saying what a provider that
            # omits the key says; only a present, non-null, different name is a
            # disagreement that costs a result its unique matched id.
            foreign_name: object = message.get("name")
            if earlier is None or (foreign_name is not None and foreign_name != earlier.name):
                contexts.append(ToolResultContext(status="invalid", call=None))
            else:
                contexts.append(ToolResultContext(status="matched", call=earlier))
    return tuple(contexts)


@dataclass(frozen=True)
class _InjectedValue:
    """A typed value one tool call actually carried, and the substitute the model
    was already shown for it.

    `real` is the value the tool ran on; `substitute` is the string that stands
    for it on the model's side. Both are needed: the first locates the echo, the
    second replaces it, and neither is inferred from the echo itself.
    """

    real: str
    entity_type: str
    substitute: str


# A TOOL ECHOES BACK WHAT IT WAS HANDED, TRUNCATED. The mock's refusal body is
# `raw[:80]`, so the result can carry the first 80 characters of a value this
# same call injected — and the rescan declines it. The dossier's echo reads as
# ten dictated digits, and ten digits is not a Russian number, so teaching the
# detector to accept it would be exactly the generic fragment masking the audit
# forbids (`research/hop-format-audit/s0-reproduction.md`, H1).
#
# THE EVIDENCE IS THE CALL, AND THE CALL CARRIES WHAT THE MODEL WAS SHOWN. A
# unique preceding assistant call (the reader above) names one dialogue-scoped
# substitution: `redact.mask_text` writes the exact string it handed the model
# into `Vault.shown_forms` at the moment of the swap, and that row also holds the
# customer's own literal and the type. The production transcript replays that
# string in `tool_calls`, so the leaf is resolved by RENDERING — the spoken
# substitute and the numeric one in the customer's own separators alike — and
# never by running the detector over it: a substitute is OUR string, and the
# detector exists to decline the invalid shapes ours are built from.
#
# THE TRUNCATION POINT BELONGS TO THE TOOL, NOT TO US. `Refusal.as_error` cuts at
# 80, another mock cuts at 70, a timeout cuts wherever the buffer filled — so the
# contract cannot be "the length the dossier happened to have". What is protected
# is every token-bounded PREFIX of a value THIS call carried, down to the floor at
# which a prefix still identifies the value: below it the overlap is a shared word
# or a shared digit head, which ordinary text has too. The floor is applied to the
# VALUE's own prefix, never to a shape, so nothing generic is masked.
_ECHO_FLOOR: int = 8
# THE DIGIT BOUNDARY IS TYPED, BECAUSE «THE SAME DIGITS» IS NOT EVIDENCE ON ITS
# OWN. What a result repeats can be written three ways, and each says something
# different about whether it is a cut of this value or an ordinary number that
# happens to share a head:
#
#   * a GROUPED run kept at least two digit groups, so the separators the tool
#     cut through are still visible — the strongest rendering evidence, and the
#     ordinary floor applies;
#   * a run written with an explicit international `+` names a phone by itself,
#     and is read at the same floor;
#   * a FLAT run has thrown that evidence away. Its digits alone must carry the
#     identity, so only a run long enough to BE the whole significant number is
#     accepted — ten digits — because a seven-digit head (`код 7926547`) is an
#     ordinary code far more often than it is a truncation.
#
# The boundary is per type because a phone's leading groups (trunk, area code)
# are structure an ordinary six-digit quantity does not have, while a card has no
# such structure at all. This is the agreed safe evidence boundary, pinned from
# both sides in `test_error_echo_privacy.py`; below it the honest answer is that
# privacy and transparency are ambiguous and the policy says which one wins.
_ECHO_DIGIT_FLOOR: int = 7
_ECHO_DIGIT_BOUNDARY: dict[str, tuple[int, int]] = {
    # entity type: (grouped or signed floor, flat floor)
    "PHONE": (_ECHO_DIGIT_FLOOR, 10),
    "CARD": (10, 10),
}
_ECHO_DIGIT_BOUNDARY_DEFAULT: tuple[int, int] = (_ECHO_DIGIT_FLOOR, 10)
# A ONE-LETTER LAST WORD MEANS DIFFERENT THINGS PER TYPE, and the literal floor
# alone cannot tell a cut from a complete mention. «абдулина м.» and «абдулина
# мария львовна» share their first eight characters, so the floor reads the
# initial as a truncation and rewrites it with the full substitute — an EXPANSION
# of a mention the dialogue never made, which is exactly the over-masking the
# product forbids. A one-letter fragment of a NAME word is an INITIAL: a complete
# way to write the person, handled by the name machinery. The same fragment of a
# dictated PHONE word is digit material — «д…» for «девятьсот» — and a mid-word
# cut there still leaks digits, so the reading is per type rather than global.
_ECHO_INITIAL_TYPES: frozenset[str] = frozenset({"NAME"})
# A rendered number: the digits of an identifier with the separators a person or
# a tool writes between them — space, `-`, `(`, `)`, `.` and `/` are all in use —
# bounded on BOTH sides so it can never be a slice of a longer token
# (`ord89265478238`, `8 926 547 82 38 12`).
_NUMBER_RE = re.compile(r"(?<!\w)\+?\d(?:[\s()\-\u00a0./]*\d)*(?!\w)")
# The digit GROUPS of such a run. A run is a sequence of numbers written with only
# separators between them (`заказ 12 8 926 547-82`), and a group boundary is where
# one may end and the next begin — the segmentation point the merge hides.
_DIGIT_GROUP_RE = re.compile(r"\d+")
# An email is not delimited by `.` or `-`: a truncated `a@b` must not rewrite the
# head of `a@b.com`, so those characters continue the token for that type.
_EMAIL_CONTINUES = frozenset("._%+-@")
# Characters a number may be written with; a run of them only continues the
# number when a digit follows, so a full stop ending a sentence does not.
_NUMBER_SEPARATORS = frozenset(" \t()-\u00a0./")


def _neutral_redaction(entity_type: str, real: str) -> str:
    """A conservative stand-in for an echo whose binding is uncertain.

    When no call can be bound to a result, the product knows the dialogue
    RESTORED this value — but it does not know which person's substitute the
    result is about, and answering with a substitute is how one dialogue ends up
    naming another's subject. The redaction therefore carries NO identity: it is
    derived from the value alone so it is stable within a request, it is the same
    shape the engine's own fallback mint uses (so it reads as a token, not as
    data), and it is deliberately absent from the vault's token index, so the
    restoring leg leaves it exactly as it is. It is not a substitute and never
    becomes one; nothing here mints, audits or writes."""
    digest = hashlib.sha256(entity_type.encode("utf-8") + b"\x00"
                            + real.encode("utf-8")).hexdigest()[:6]
    return f"REDACTED{digest}"


def _identity_key(entity_type: str, value: str) -> tuple[str, str]:
    """The typed identity the vault itself keys this value under.

    `fold_key` after `canonicalize` for a NAME — a person is neither a
    capitalisation nor a diaeresis — the type's own canonical for everything
    else. Used only to ask whether two strings are the same value this dialogue
    handled, never to match text."""
    canonical = canonicalize(entity_type, value)
    return (entity_type, fold_key(canonical) if entity_type == "NAME" else canonical)


def _digit_renderings(digits: str, entity_type: str) -> frozenset[str]:
    """The digit strings a prefix of which is a prefix of this number's rendering.

    A PHONE is written `+7 926…`, `8 926…` or `926…`; comparing only the string
    that happened to sit in the call would miss the echo in the other rendering.
    The set is derived from the value's identity, never searched for in the text.
    """
    if entity_type != "PHONE" or len(digits) != 11 or digits[0] not in "78":
        return frozenset({digits})
    significant = digits[1:]
    return frozenset({digits, significant, "7" + significant, "8" + significant})


def _identity_digits(entity_type: str, value: str) -> str | None:
    """The value's digits under its own type, or None when its identity is not a
    digit string. Read through `canonicalize`, never guessed from the surface."""
    canonical = canonicalize(entity_type, value)
    digits = canonical[1:] if canonical.startswith("+") else canonical
    if not digits or not digits.isdigit():
        return None
    return digits


def _continues(entity_type: str, text: str, at: int, numeric: bool) -> bool:
    """Whether the character at `at` continues the token standing beside it.

    Typed, because "the same token" is a different question per type: a letter
    extends a word, a digit (or a separator with a digit behind it) extends a
    number, and for an email even a dot does. This is the whole reason an echo
    may be truncated at all — the truncation is only accepted where the text
    cannot go on spelling the value.

    `numeric` describes the RENDERING that matched, never the value's identity.
    The same PHONE is written `8 926 547-82` in one dialogue and `восемь
    девятьсот…` in another; the identity is digits in both, but a space before a
    digit extends only the first, and asking the numeric question of the words
    refused a dictated echo that no longer number was continuing.
    """
    if at < 0 or at >= len(text):
        return False
    char = text[at]
    if entity_type == "EMAIL":
        return char.isalnum() or char in _EMAIL_CONTINUES
    if char.isdigit():
        return True
    if numeric and char in _NUMBER_SEPARATORS:
        end = at + 1
        while end < len(text) and text[end] in _NUMBER_SEPARATORS:
            end += 1
        return end < len(text) and text[end].isdigit()
    return char.isalnum() or char in "_-\u2010\u2011"


def _rendered_as_number(fragment: str) -> bool:
    """Whether a matched occurrence READS as a number, whatever the value's identity.

    The boundary question is about the text AROUND the occurrence, so it can only
    be asked about the rendering that occurrence actually is. A dictated PHONE and
    a typed one share an identity of digits, but only the typed rendering is a
    number: a space followed by a digit continues `8 926 547-` and does not
    continue `восемь девятьсот`. Reading the numeric flag off the identity
    (`_identity_digits`) asked the numeric question of word renderings too, and the
    dossier's dictated fragment followed by ` 12` was refused as a slice of a longer
    number that is not there — the customer's own words reached the model.

    A rendering is numeric when every character is a digit, a separator a number is
    written with, or a leading `+`, and at least one digit is present. Anything with
    a letter, or nothing numeric at all, is not: a house number glued to its street
    (`ольховая 10`) and a name (`Битюков`) keep their own boundary rules.
    """
    seen_digit = False
    for index, char in enumerate(fragment):
        if char.isdigit():
            seen_digit = True
        elif char in _NUMBER_SEPARATORS or (index == 0 and char == "+"):
            continue
        else:
            return False
    return seen_digit


def _word_char(char: str) -> bool:
    """Whether a character is part of a word's own body."""
    return char.isalnum() or char in "_-\u2010\u2011"


def _word_continues(text: str, at: int, edge: str) -> bool:
    """Whether `text[at]` continues a WORD rendering whose own edge is `edge`.

    A word is continued only where the two characters touch as one word, so the
    rendering's own edge decides too: `ольховая 105` is one token because the `5`
    touches the `0`, while `шесть 12` is two because the rendering's cut landed on
    the value's own space and the digit stands on the far side of it. The value's
    separator is part of the matched rendering — the extension kept it because the
    value goes on with it — and what the text writes after that separator is the
    next token, not the rest of this one.
    """
    if at < 0 or at >= len(text) or not _word_char(edge):
        return False
    return _word_char(text[at])


def _bounded(text: str, start: int, end: int, entity_type: str, numeric: bool) -> bool:
    """The match stands as a whole token: neither neighbour continues it.

    `Анна` never rewrites `Аннабель`, `ольховая 10` never rewrites `ольховая 105`,
    and an email prefix never rewrites another domain — a truncated echo is only
    ever a truncation of a value, never a slice of somebody else's longer one.

    Which question is asked follows the RENDERING: email characters for an address,
    the number rules when the matched text reads as a number, and the word rules
    otherwise. The value's identity never decides it, because one identity is
    written both ways.
    """
    if numeric or entity_type == "EMAIL":
        return (not _continues(entity_type, text, start - 1, numeric)
                and not _continues(entity_type, text, end, numeric))
    return (not _word_continues(text, start - 1, text[start])
            and not _word_continues(text, end, text[end - 1]))


def _string_leaves(node: object) -> tuple[str, ...]:
    """Every string VALUE in the parsed arguments, at any depth.

    Keys are field names — the tool CONTRACT, not customer content — and numbers
    keep their JSON representation rather than a Python `str()`, so a float never
    becomes a string nobody wrote. Objects and arrays of objects are walked
    because a tool argument is routinely nested.
    """
    found: list[str] = []
    stack: list[object] = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return tuple(found)


class _Provenance:
    """Typed call-scoped evidence for ONE masking pass.

    Every read here is an index the vault already keeps for THIS conversation: the
    substitution table (`shown_forms`), the token column and the digit-signature
    columns. No detector pass, no vault scan, no minting, and nothing survives the
    pass — a new transcript is a new object.

    `values_for` resolves a call id at most once, so a multipart result, a
    repeated reference or a growing transcript pays for that call's leaves once
    per pass instead of once per block. Resolving by RENDERING is also what makes
    the production leaf work at all: what the model wrote in the call is the string
    this dialogue showed it, which the detector is built to decline. The leaf must
    be a rendering this dialogue made — its recorded rendering, the canonical token
    it minted, or a numeric rewrite of either. The restored REAL value is not a
    substitute and is not evidence of one.
    """

    def __init__(self, context: MaskContext) -> None:
        self.context = context
        self._by_rendering: dict[str, _InjectedValue] | None = None
        self._literals: frozenset[str] = frozenset()
        self._identities: frozenset[tuple[str, str]] = frozenset()
        # Every rendering this conversation showed — the exact surface and its
        # case fold — for the guard that refuses to mint a substitute out of a
        # substitute. Frozen with the rest of the record.
        self._own_renderings: frozenset[str] = frozenset()
        self._by_folded: dict[str, _InjectedValue] = {}
        # The exact rendering strings, for the "never rewrite inside our own
        # substitute" exclusion the echo pass applies to both legs.
        self._renderings: tuple[str, ...] = ()
        self._leaves: dict[str, tuple[_InjectedValue, ...]] = {}
        self._calls: dict[tuple[str, str], tuple[_InjectedValue, ...]] = {}
        # The LIVE rendering table, read at most once and only when a value's
        # own rendering is not the string the current request carries.
        self._live: dict[tuple[str, str], tuple[str, ...]] | None = None

    def _index(self) -> dict[str, _InjectedValue]:
        """What THIS dialogue showed where, keyed by the rendering it showed.

        One row per rendering is the table's primary key, so no key can carry two
        claims. A SELF-MAPPING row (`shown == literal`) is the vault's marker for
        a surface two owners claimed — a refusal, not a writing — and is skipped
        rather than offered as evidence.

        THE LITERAL IS THE LONGEST THIS DIALOGUE RECORDED FOR THE IDENTITY, not
        the one row's own. A tool cuts a value at a character position and the
        result leg re-mints the cut, so the same value arrives under more than one
        rendering — the full one the user wrote and a shorter one the cut produced
        — and a rendering that resolves to the SHORT literal would refuse a later,
        longer cut of the same value, because the cut is no longer a prefix of the
        evidence. A literal of another identity is never borrowed: the group is the
        typed canonical the vault itself keys the value by, so only renderings of
        one value are merged, and the substitute stays the row's OWN rendering —
        the string the model was actually shown.

        The same pass also records the typed IDENTITIES this dialogue handled,
        which is what scopes the identity-column evidence below. Those columns are
        customer-wide on purpose — one substitute for one value, for ever — so a
        conversation can reach ANOTHER conversation's row through them, and a
        matched result would then be answered with a substitute this dialogue
        never showed anybody. The wrong person's substitute is fail-closed for
        privacy and wrong for the product, so the answer is refusal.
        """
        if self._by_rendering is None:
            rows: list[tuple[tuple[str, str], str, str, str]] = []
            literals: set[str] = set()
            identities: set[tuple[str, str]] = set()
            own: set[str] = set()
            for rendering, literal, entity_type in self.context.vault.shown_forms():
                if not rendering or rendering == literal:
                    continue
                identity = _identity_key(entity_type, literal)
                rows.append((identity, rendering, literal, entity_type))
                literals.add(literal)
                identities.add(identity)
                # Every rendering THIS conversation showed, in the forms
                # `mask_one` may meet it in: the exact string, its case fold, and
                # the vault's own typed/folded key. A re-cased substitute — or the
                # same substitute re-typed by a JSON field into an opaque span —
                # is then recognised as ours instead of being minted again.
                own.add(rendering)
                own.add(rendering.casefold())
            # The authoritative original per typed identity, computed in one pass
            # so no canonicalization is repeated below.
            authoritative: dict[tuple[str, str], str] = {}
            for identity, _rendering, literal, _entity_type in rows:
                if len(literal) > len(authoritative.get(identity, "")):
                    authoritative[identity] = literal
            index: dict[str, _InjectedValue] = {
                rendering: _InjectedValue(real=authoritative[identity], entity_type=entity_type,
                                          substitute=rendering)
                for identity, rendering, _literal, entity_type in rows}
            self._by_rendering = index
            self._literals = frozenset(literals)
            self._identities = frozenset(identities)
            self._own_renderings = frozenset(own)
            self._renderings = tuple(rendering for _identity, rendering, _literal, _et in rows)
            # A NAME rendering RETYPED IN ANOTHER CASE is still this dialogue's
            # own writing (`Чижова Эмилия` → `чижова эмилия` inside JSON), and the
            # person it names is the one the vault already recorded. The folded
            # index answers that without the detector and without treating the
            # re-cased string as a new value.
            folded: dict[str, _InjectedValue] = {}
            for _identity, rendering, _literal, entity_type in rows:
                if entity_type == "NAME":
                    folded.setdefault(fold_key(canonicalize("NAME", rendering)),
                                      index[rendering])
            self._by_folded = folded
        return self._by_rendering

    def _recorded_here(self, entity_type: str, real: str) -> bool:
        """Whether THIS dialogue recorded that value.

        The token and digit-signature columns answer for the whole customer, so a
        hit is evidence about the customer and not about the conversation. This is
        the second half of the proof: the same string that was recorded, or the
        same typed identity (a NAME is neither a capitalisation nor a diaeresis,
        so `fold_key` — the comparison the vault itself makes between two owners).
        """
        return real in self._literals or _identity_key(entity_type, real) in self._identities

    def _by_minted(self, leaves: list[str]) -> list[_InjectedValue]:
        """Leaves written in a notation this dialogue did not record verbatim.

        A model that retypes the substitute — `+7…` where the dialogue showed
        `8 926…`, separators dropped or moved — is resolved by the SAME indexed
        digit-signature columns the response leg uses, so nothing is scanned and
        nothing is inferred from a substring. The token column is checked first
        because a full signature beats a phone's last-ten alias.

        BOTH columns answer for the customer, so a hit is admitted only when this
        dialogue recorded that value too (`_recorded_here`): otherwise conversation
        B carrying A's rendering would answer with A's substitute.
        """
        found: list[_InjectedValue] = []
        self._index()
        typed = self.context.vault.detokenize_many_typed(set(leaves))
        signature_of: dict[str, str] = {}
        for leaf in leaves:
            resolved = typed.get(leaf)
            if resolved is not None:
                entity_type, real = resolved
                if real and real != leaf and self._recorded_here(entity_type, real):
                    found.append(_InjectedValue(real=real, entity_type=entity_type,
                                                substitute=leaf))
                continue
            digits = re.sub(r"\D", "", leaf)
            if not digits:
                continue
            signature_of.setdefault(digits, leaf)
            if len(digits) >= 10:
                signature_of.setdefault(digits[-10:], leaf)
        if signature_of:
            resolved = self.context.vault.resolve_digit_signatures_typed(
                set(signature_of), False)
            for signature, (entity_type, real) in resolved.items():
                leaf = signature_of[signature]
                if real and real != leaf and self._recorded_here(entity_type, real):
                    found.append(_InjectedValue(real=real, entity_type=entity_type,
                                                substitute=leaf))
        return found

    def snapshot(self) -> None:
        """Freeze this dialogue's own record BEFORE this pass masks anything.

        `_mask_tool_calls` masks a replayed call in the SAME pass, and masking a
        value this dialogue never recorded MINTS a row for it — a replayed real
        value re-typed by its own JSON key lands as `OPAQUE`. Built lazily at the
        first evidence read, the index would then contain that row and
        `_recorded_here` would confirm the very attribution this class exists to
        refuse: a dialogue answering with a substitute for a value it only ever
        saw because the conversion created it. The snapshot is taken once, before
        the loop, and never rebuilt; masking after it cannot rewrite the past."""
        self._index()

    def values_for(self, call: ToolCallContext) -> tuple[_InjectedValue, ...]:
        """The typed values THIS call carried, from its wire arguments only.

        The memo is keyed by the call id AND the arguments it arrived with: the
        same call is read in up to two forms in one pass — the customer's raw
        replay and this pass's model-visible masking of it — and a memo keyed by
        the id alone would answer the second form with the first form's verdict.
        Everything else about the memo is unchanged: a repeated reference and a
        growing transcript still pay for that call's leaves once."""
        key = (call.call_id, call.arguments)
        cached = self._calls.get(key)
        if cached is not None:
            return cached
        with stage("mask.call_provenance"):
            parsed = json.loads(call.arguments)
            if not isinstance(parsed, dict):  # `_read_tool_call` guarantees this
                raise ValueError("a matched call's arguments stopped being a JSON object")
            found: list[_InjectedValue] = []
            unresolved: list[str] = []
            for leaf in dict.fromkeys(_string_leaves(parsed)):
                hit = self._leaves.get(leaf)
                if hit is None:
                    value = self._index().get(leaf)
                    if value is None:
                        # A NAME the model retyped in another case is the same
                        # rendering this dialogue showed, so it names the same
                        # value — the folded index, not the detector, says so.
                        value = self._by_folded.get(
                            fold_key(canonicalize("NAME", leaf)))
                    hit = () if value is None else (value,)
                    self._leaves[leaf] = hit
                if hit:
                    found.extend(hit)
                else:
                    unresolved.append(leaf)
            if unresolved:
                # An unknown leaf resolves to nothing, which is the refusal path,
                # not an error: the arguments routinely carry ids and field words.
                found.extend(self._by_minted(unresolved))
            resolved = tuple(dict.fromkeys(found))
        self._calls[key] = resolved
        return resolved

    def values_for_replayed(self, call: ToolCallContext) -> tuple[_InjectedValue, ...]:
        """Every value THIS call carried, read from BOTH forms of its arguments.

        A REPLAYED CALL HAS TWO FORMS, AND A CALL CAN CARRY ONE OF THEM PER FIELD.
        The app composes `arguments` from its own state, so the wire routinely
        holds the RESTORED real value for one leaf — the customer's own writing,
        which the detector declines exactly where this leg is needed (an
        80-character cut is not a valid number) — beside a leaf the model wrote
        back as the substitute this dialogue showed it. Reading one form as a
        verdict on the WHOLE call is what let `long_support-013` leak again: the
        shown leaf resolved, the raw form was adopted for the call, and the real
        leaf contributed no provenance, so the result leg could not recognise the
        echo of a value this same call had injected. The two forms are the same
        call's own arguments, so every leaf is read in both and the values are
        UNIONED; a leaf that names nothing in either still names nothing.

        THE ANSWER IS THE RENDERING THIS REQUEST CARRIES, NOT THE ONE AN EARLIER
        TURN SHOWED. The identity is established by the FROZEN record above (a
        value this dialogue already recorded, or a token/digit index hit this
        dialogue can also see recorded), so choosing among that identity's
        renderings is not admitting new identity evidence. `_prefer_current`
        therefore reads the LIVE substitution table — rows this very pass minted
        included — and takes the rendering that actually appears in
        `_model_visible_call`'s arguments, which is the string the model is
        reading in this request. A value whose current rendering cannot be found
        is answered with a neutral redaction rather than an older substitute: the
        product never hands the model a person the current request did not name.

        `_model_visible_call` masks the same string `_mask_tool_calls` already
        masked in this pass, so this is the cache hit — no second detection, no
        audit event, no vault row. Neither read can admit a value this dialogue
        never recorded: both go through `_recorded_here`, so an arbitrary real
        value and another conversation's rendering resolve to nothing.
        """
        raw = self.values_for(call)
        visible_call = _model_visible_call(call, self.context, self._own_renderings)
        visible = self.values_for(visible_call)
        return self._prefer_current(tuple(dict.fromkeys(visible + raw)), visible_call.arguments)

    def _prefer_current(self, values: tuple[_InjectedValue, ...],
                        visible_arguments: str) -> tuple[_InjectedValue, ...]:
        """Each identity's substitute AS THIS REQUEST SHOWS IT, or a redaction.

        A value already carrying that rendering is left alone, which is the
        common case and keeps the live table unread (`shown_forms` is read at
        most once per pass). Only a value whose stored substitute is absent from
        the current request's arguments forces the live read — and it is the
        string the model is reading, not the row's identity claim, that decides
        the replacement. Failing to find one is fail-closed: a neutral redaction
        stands for the value instead of a substitute this request never showed.
        """
        out: list[_InjectedValue] = []
        for value in values:
            substitute = value.substitute
            current = _surface_in(substitute, visible_arguments) if substitute != value.real else None
            if current is not None:
                out.append(value if current == substitute else
                           _InjectedValue(real=value.real, entity_type=value.entity_type,
                                          substitute=current))
                continue
            if self._live is None:
                self._live = self._live_renderings()
            identity = _identity_key(value.entity_type, value.real)
            candidates = [surface for rendering in self._live.get(identity, ())
                          if rendering != value.real
                          for surface in (_surface_in(rendering, visible_arguments),)
                          if surface is not None]
            chosen = max(candidates, key=len) if candidates else _neutral_redaction(
                value.entity_type, value.real)
            out.append(_InjectedValue(real=value.real, entity_type=value.entity_type,
                                      substitute=chosen))
        return tuple(out)

    def _live_renderings(self) -> dict[tuple[str, str], tuple[str, ...]]:
        """This dialogue's CURRENT rendering table, keyed by typed identity.

        Read LIVE, after this pass has masked the replayed call, so a rendering
        the pass minted is visible. It is used only to CHOOSE A RENDERING for an
        identity the frozen record already established — never to establish one,
        which is what keeps `snapshot`'s anti-self-attribution intact.
        """
        grouped: dict[tuple[str, str], list[str]] = {}
        for rendering, literal, entity_type in self.context.vault.shown_forms():
            if not rendering or rendering == literal:
                continue
            grouped.setdefault(_identity_key(entity_type, literal), []).append(rendering)
        return {identity: tuple(dict.fromkeys(renderings))
                for identity, renderings in grouped.items()}

    def own_renderings(self) -> frozenset[str]:
        """Folded keys of the renderings THIS conversation showed, frozen."""
        self._index()
        return self._own_renderings

    def renderings(self) -> tuple[str, ...]:
        """The exact rendering strings this conversation showed."""
        self._index()
        return self._renderings

    def recorded_values(self) -> tuple[_InjectedValue, ...]:
        """Every value THIS CONVERSATION recorded, for the UNBOUND result leg.

        The frozen index answers what this dialogue handled before the pass, so a
        tool result with no usable call — a refused binding, a missing id, a
        declaration that arrives later — can still recognise a typed echo of a
        value the dialogue itself restored. The substitute is deliberately NOT
        used by that leg: when the binding is uncertain the product redacts, it
        does not guess a person. Nothing customer-wide is consulted here beyond
        the conversation-scoped view, so a foreign dialogue's value contributes
        nothing.
        """
        seen: dict[tuple[str, str], _InjectedValue] = {}
        for value in self._index().values():
            seen.setdefault((value.entity_type, value.real), value)
        return tuple(seen.values())


def _surface_in(rendering: str, text: str) -> str | None:
    """`rendering` AS `text` writes it, or None when `text` does not carry it.

    THE CURRENT REQUEST'S FORM IS A SURFACE, NOT THE ROW'S STRING. The model
    retypes the substitute this dialogue showed it, and the case it retyped is
    the form the customer is reading in THIS request (`наумов кузьма` in the call
    while the row minted `Наумов Кузьма`). A membership test against the row's
    exact string finds nothing there and the identity falls to a neutral
    redaction — the fail-closed answer, but the wrong one, because the identity
    was already established and the request itself carries the rendering. The
    fold is the same `_by_folded` comparison the resolver already trusts, so this
    can only choose among renderings of an identity the record established; it
    admits no new one. The exact reading is tried first so an as-is leaf keeps
    the row's own bytes."""
    if not rendering:
        return None
    at = text.find(rendering)
    if at >= 0:
        return rendering
    folded = text.casefold()
    at = folded.find(rendering.casefold())
    return None if at < 0 else text[at:at + len(rendering)]


def _echo_spans(text: str, value: _InjectedValue) -> tuple[tuple[int, int], ...]:
    """Where `text` carries this call's value, whole, truncated, or re-rendered.

    Two typed readings of one identity: the literal string the dialogue used, and
    the digits the type's own canonical gives that string. A value whose identity
    is not a digit string (a name, a place, an email) is only ever matched
    literally, so no digit rule can reach it.

    The single-value form. A masking pass resolves its call's values once and
    reuses `_digits` through `_echo_targets`, so the canonical — morphology for a
    NAME — is not recomputed for every content block of one result.
    """
    return _typed_echo_spans(text, value, _identity_digits(value.entity_type, value.real))


def _echo_targets(values: tuple[_InjectedValue, ...]) -> tuple[tuple[_InjectedValue, str | None], ...]:
    """Each of a call's values WITH its identity digits, read once per pass."""
    return tuple((value, _identity_digits(value.entity_type, value.real))
                 for value in values)


def _typed_echo_spans(text: str, value: _InjectedValue,
                      digits: str | None) -> tuple[tuple[int, int], ...]:
    """`_echo_spans` for a value whose identity digits the caller already read."""
    spans = list(_literal_echo_spans(text, value))
    if digits is not None:
        spans.extend(_numeric_echo_spans(text, digits, value.entity_type))
    return tuple(spans)


def _prefix_is_a_cut(real: str, length: int, entity_type: str) -> bool:
    """Whether the first `length` characters of `real` read as its TRUNCATION.

    The floor says how much text a result must repeat before the repetition is
    evidence at all. It cannot say whether the repetition is a cut, and one shape
    is ambiguous: a one-letter last word is an INITIAL in a name — a complete way
    to write the person, which the dialogue never expanded — and the beginning of
    a numeral word in a dictated number, where the digit material is real. The
    reading is per type (`_ECHO_INITIAL_TYPES`) and stated here rather than
    guessed. Above one letter the fragment is a cut for every type: a partial word
    of a name (`абдулина ма`) leaks as surely as a partial word of a dictation.
    """
    if length == len(real):
        return True
    if length < _ECHO_FLOOR:
        return False
    if entity_type not in _ECHO_INITIAL_TYPES:
        return True
    head = real[:length]
    if head[-1].isspace() or head[-1] in "-\u2010\u2011":
        return True
    boundary = max(head.rfind(" "), head.rfind("-"), head.rfind("\u00a0"))
    return length - (boundary + 1) >= 2


def _literal_echo_spans(text: str, value: _InjectedValue) -> tuple[tuple[int, int], ...]:
    """Whole or truncated literal occurrences of the value's own string.

    A match is a leading part of the value at least `_ECHO_FLOOR` characters long
    — or the whole value, however short — it must stand as a whole token on both
    sides, and it must read as a CUT under the type's own policy
    (`_prefix_is_a_cut`). How much the tool cut is the tool's business, and a rule
    keyed to where the value's last word happens to start protects one truncation
    length while leaking the next. Only the value's own leading needles are
    searched for and each occurrence is then extended maximally, so the cost is
    proportional to real occurrences rather than to the value's length.

    The boundary is typed by the OCCURRENCE (`_rendered_as_number`), not by the
    value: one identity has a word rendering and a digit rendering, and which one
    the text carries is what decides whether the neighbour continues the token.
    """
    real = value.real
    needles = [real] if _ECHO_FLOOR >= len(real) else [real, real[:_ECHO_FLOOR]]
    extent: dict[int, int] = {}
    for needle in needles:
        at = text.find(needle)
        while at >= 0:
            length = 0
            # A truncated echo may end exactly at the end of the content, so the
            # extension stops at the text's own end and not only at the value's.
            while (length < len(real) and at + length < len(text)
                   and text[at + length] == real[length]):
                length += 1
            end = at + length
            if (_prefix_is_a_cut(real, length, value.entity_type)
                    and _bounded(text, at, end, value.entity_type,
                                 _rendered_as_number(text[at:end]))):
                extent[at] = max(extent.get(at, 0), length)
            at = text.find(needle, at + 1)
    return tuple(sorted((start, start + length) for start, length in extent.items()))


def _numeric_echo_spans(text: str, digits: str,
                        entity_type: str) -> tuple[tuple[int, int], ...]:
    """Numeric echoes written with separators, compared by the type's identity.

    A run is SEGMENTED AT ITS DIGIT-GROUP BOUNDARIES, because the scanner cannot
    see where one written number ends and the next begins: `заказ 12 8 926 547-82`
    is one run of eleven digits, and read whole it names nothing, so the real
    fragment inside it reached the model. Each group boundary is tried as a start,
    the segment's digits are compared against the renderings this identity has
    under its own type, and the first segment that matches is the span — always a
    whole number of groups, never a slice of one.

    The length the segment must reach is typed by the RENDERING it kept
    (`_ECHO_DIGIT_BOUNDARY`): a grouped run (or one with an explicit `+`) is a
    number the tool cut through and keeps the lower floor, while a flat run is
    held to the whole significant length, so an ordinary seven-digit head
    (`код 7926547`) is never read as a phone. The run's own ends are already
    bounded by `_NUMBER_RE` — no word character touches either side — and every
    segment boundary after the first is a digit-group boundary inside the run,
    which is exactly the place the merge hid.
    """
    renderings = _digit_renderings(digits, entity_type)
    grouped_floor, flat_floor = _ECHO_DIGIT_BOUNDARY.get(
        entity_type, _ECHO_DIGIT_BOUNDARY_DEFAULT)
    spans: list[tuple[int, int]] = []
    for match in _NUMBER_RE.finditer(text):
        run = match.group()
        groups = [(group.start(), group.end()) for group in _DIGIT_GROUP_RE.finditer(run)]
        signed = run.startswith("+")
        for index, (head, _tail) in enumerate(groups):
            fragment = "".join(run[start:end] for start, end in groups[index:])
            if not any(rendering.startswith(fragment) for rendering in renderings):
                continue
            floor = grouped_floor if (index + 1 < len(groups) or signed) else flat_floor
            if len(fragment) >= floor:
                spans.append((match.start() + head, match.end()))
                break
    return tuple(spans)


def _choose_spans(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Non-overlapping replacement spans, longest-first at any shared start."""
    chosen: list[tuple[int, int, str]] = []
    for start, end, replacement in sorted(spans, key=lambda span: (span[0], -span[1])):
        if chosen and start < chosen[-1][1]:
            continue
        chosen.append((start, end, replacement))
    return chosen


def _splice_spans(text: str, spans: list[tuple[int, int, str]]) -> str:
    """Replace non-overlapping spans, longest-first at any shared start."""
    return _splice_chosen(text, _choose_spans(spans))


def _splice_chosen(text: str, chosen: list[tuple[int, int, str]]) -> str:
    out: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(chosen, key=lambda span: span[0]):
        out.append(text[cursor:start])
        out.append(replacement)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _substitute_ranges(text: str, renderings: tuple[str, ...]) -> list[tuple[int, int]]:
    """Where `text` already carries one of THIS dialogue's own substitutes.

    A spoken substitute and the real value it stands for open with the same
    words (`восемь девятьсот…`), so a search for the real value's prefix finds
    one INSIDE the substitute. Rewriting there would corrupt the substitute the
    model was already shown — and re-redact text that is already protected. The
    echo pass therefore never writes inside one of its own renderings."""
    ranges: list[tuple[int, int]] = []
    for rendering in renderings:
        if not rendering:
            continue
        at = text.find(rendering)
        while at >= 0:
            ranges.append((at, at + len(rendering)))
            at = text.find(rendering, at + 1)
    return ranges


def _phone_echo_is_a_cut(fragment: str, real: str) -> bool:
    """Whether the tool wrote a TRUNCATION of the dialogue's own number.

    A CUT HAS NO NOTATION TO MIRROR, so it is answered with the whole rendering:
    `_digits_in_form_of` reads a flat run shorter than the real as a national
    number and keeps only the substitute's last ten digits, which would answer
    `+7916123456` with `+9222915885` — the trunk dropped and the field's own
    country code rewritten. The comparison is on the DIGITS and against the
    identity's own RENDERINGS, because the tool cuts across separators and either
    trunk: `8926547823` truncates a real `8 926 547-82-38` whose stored canonical
    is `+79265478238`, so neither surface shares a character prefix with the cut
    while the `8…` rendering does.

    A RE-NOTATION is the whole number in the field's convention — `+79889990949`
    for a real `8 988 999 09 49`, or the bare significant `9265478238` — and it is
    exactly a fragment that IS one of the identity's renderings, so it is the
    form the result keeps. Every echo span is a prefix of some rendering
    (`_numeric_echo_spans`), so this test is total on the numeric leg."""
    written = re.sub(r"\D", "", fragment)
    digits = _identity_digits("PHONE", real)
    if not written or digits is None:
        return False
    renderings = _digit_renderings(digits, "PHONE")
    if written in renderings:
        return False
    return any(len(written) < len(rendering) and rendering.startswith(written)
               for rendering in renderings)


def _project_echo(value: _InjectedValue, fragment: str, as_is: bool) -> str:
    """The CURRENT rendering reduced to the part of the value the tool echoed.

    A tool cuts a value at a character position, so the echo of a NAME is
    routinely one word of it. Handing the whole substitute back would answer a
    one-word mention with a three-word person the request never carried, and the
    customer's own reading of the field changes with it. The substitute is minted
    slot by slot in the ORDER of the real name (`_render_token` -> `_fake_name`),
    so the word standing where the echoed word stood is the same slot — the same
    positional rule `_corresponding_part` uses on the vault side, applied here to
    the rendering THIS request carries, which is why the case the model wrote
    survives. A type with no such structure (a phone cut, an address) keeps the
    whole rendering, which is the behaviour the echo leg always had.

    FOR PHONE THE FRAGMENT'S NOTATION WINS BEFORE `as_is` IS EVEN ASKED, because
    the warm pass is the NORMAL multi-turn case and `as_is` is true on all of it.
    `as_is` means the call leaf is the row's own string; it says nothing about the
    notation the TOOL wrote, and the row's string is the USER's notation. Reading
    it as a verdict on the result is what returned an `8 …` substitute verbatim
    for a `+7…` result (`long_order-058`) as soon as the row existed — the cold
    pass re-notated and the warm one did not, so the same request answered two
    ways. A PHONE's identity here is already established (the echo span matched
    this value's own digit renderings), so the fragment is the field's form and
    the substitute's digits are laid into it; a TRUNCATION keeps the whole
    rendering (`_phone_echo_is_a_cut`), and `_digits_in_form_of` itself returns
    the substitute unchanged when the forms cannot line up, so a cut of a shaped
    type is never spliced into a guess.

    `as_is` therefore governs the NAME cut only: there the request carries the
    row's own string and the previous expansion of a whole-word cut IS the
    rendering this request reads, so it is left alone. The projection exists for
    the E01 lane — a rendering this request re-cased — and only there is the cut
    answered with the part of the substitute that stands where the cut stood."""
    substitute = value.substitute
    real = value.real
    if value.entity_type == "PHONE":
        return (substitute if _phone_echo_is_a_cut(fragment, real)
                else _digits_in_form_of(fragment, substitute))
    if as_is or fragment == real or not real.startswith(fragment.lstrip("+")):
        return substitute
    if value.entity_type != "NAME":
        return substitute
    real_words = real.split(" ")
    fake_words = substitute.split(" ")
    if len(real_words) != len(fake_words):
        return substitute
    covered = len(fragment)
    out: list[str] = []
    start = 0
    for real_word, fake_word in zip(real_words, fake_words):
        if covered <= start:
            break
        take = min(covered, start + len(real_word)) - start
        out.append(fake_word[:take])
        if take < len(real_word):
            break
        start += len(real_word) + 1
    projected = " ".join(out)
    if not projected:
        return substitute
    return projected + " " if fragment.endswith(" ") else projected


_ECHO_RESERVED: str = "\x00EO"


def _echo_marker(nonce: int, index: int) -> str:
    """One generated marker: the reserved prefix, a per-pass nonce, the index.

    THE PAYLOAD CANNOT FORGE THIS ONE. `_reserve_echoes` picks the first nonce
    whose tokens do not occur in the text at all, so a body that carries
    marker-shaped bytes of its own — `\\x00EO0\\x01`, the shape the first scheme
    generated — keeps them (they are not ours) while `_splice_reserved` can only
    ever find the token this pass inserted. Deterministic and not random on
    purpose: the reserved text is the mask cache's key, and a fresh random marker
    per pass would miss the cache every time and re-audit every PII value that
    sits beside an echo."""
    return f"{_ECHO_RESERVED}{nonce}:{index}\x01"


def _free_marker_nonce(text: str, count: int) -> int:
    """The first nonce whose generated tokens are entirely absent from `text`.

    A COLLISION HERE WRITES A SUBSTITUTE OVER THE PAYLOAD. `_splice_reserved`
    finds a token by SEARCH, so a payload that contains the generated token is
    targeted instead of the generated span: the attacker's bytes are replaced
    with a value the request never put in that field, and the engine's own marker
    survives raw into the provider-visible body. Verifying absence is the whole
    guarantee. The scan is bounded by the text — every extra nonce must be forced
    by a distinct marker-shaped literal the payload itself carries."""
    nonce = 0
    while any(_echo_marker(nonce, index) in text for index in range(count)):
        nonce += 1
    return nonce


def _reserve_echoes(text: str,
                    echoes: tuple[tuple[_InjectedValue, str | None], ...],
                    renderings: tuple[str, ...]) -> tuple[str, tuple[str, ...], int]:
    """Lift a bound call's own echoes OFF the text before detection runs.

    THIS IS THE E01 PRECEDENCE, STATED AS AN ORDER OF OPERATIONS. `_mask_content`
    used to mask first and ask about the call second, so the generic detector
    consumed the real span and answered with the vault's mint — `Наумов` in the
    result while the same request's call leaf read `наумов`, two forms of one
    identity in one request and the second never shown to anybody. The call's own
    evidence is not a guess about the text: the association was established by the
    reader and the rendering is the one this request carries, so it is applied to
    the ORIGINAL span and the segment is marked reserved, not masked. Detection
    then runs on the rest — unrelated PII is still found — and the marker is
    replaced afterwards, so no inserted substitute is ever re-detected.

    Reserving also stops the partial-NAME mint: a result echoing `Битюков ` used
    to create a vault row and an audit event for the cut as a value of its own,
    which is the fake-of-a-fake direction the own-rendering guard closes on the
    call leg. The marker is NUL-delimited and carries no word, digit or space, so
    no recogniser can absorb it; it lives inside the text the cache keys on, so
    the cache stays complete without a second discriminator."""
    blocked = _substitute_ranges(text, renderings)

    def _free(start: int, end: int) -> bool:
        return not any(start < stop and begin < end for begin, stop in blocked)

    claims: list[tuple[int, int, str]] = []
    for value, digits in echoes:
        as_is = value.substitute in renderings
        for start, end in _typed_echo_spans(text, value, digits):
            if not _free(start, end):
                continue
            fragment = text[start:end]
            # THE COUNTRY-CODE SIGN BELONGS TO THE NUMBER'S FORM. `_numeric_echo_spans`
            # bounds a run at its digit groups, so a `+7…` echo yields the digits
            # with the sign left standing outside the span; splicing a substitute
            # that carries its own convention over them wrote `+8 (979) 555-33-22`.
            # The sign is claimed with the digits, and `_project_echo` renders the
            # substitute in that form.
            if start > 0 and text[start - 1] == "+" and fragment[:1].isdigit() \
                    and _free(start - 1, end):
                start -= 1
                fragment = "+" + fragment
            claims.append((start, end, _project_echo(value, fragment, as_is)))
    chosen = _choose_spans(claims)
    if not chosen:
        return text, (), 0
    nonce = _free_marker_nonce(text, len(chosen))
    out: list[str] = []
    replacements: list[str] = []
    cursor = 0
    for start, end, replacement in chosen:
        out.append(text[cursor:start])
        out.append(_echo_marker(nonce, len(replacements)))
        replacements.append(replacement)
        cursor = end
    out.append(text[cursor:])
    return "".join(out), tuple(replacements), nonce


def _splice_reserved(text: str, replacements: tuple[str, ...], nonce: int) -> str:
    """Put the call-backed renderings where their markers survived.

    The marker is this pass's own (`_echo_marker`), chosen absent from the raw
    text, so a search cannot land on the payload's bytes. A marker a detected span
    swallowed is simply absent: that span is masked generically, which is
    protected, so the fallback is a narrower projection and never a leak."""
    for index, replacement in enumerate(replacements):
        text = text.replace(_echo_marker(nonce, index), replacement, 1)
    return text


def _replace_echoes(text: str,
                    echoes: tuple[tuple[_InjectedValue, str | None], ...],
                    recorded: tuple[tuple[_InjectedValue, str | None], ...],
                    renderings: tuple[str, ...]) -> str:
    """Replace echoes of values THIS call carried, after detection has run.

    Deliberately after: the substitute is a fresh value nobody has detected yet,
    and running the detector over it again is the re-masking the engine forbids.
    The pass is not audited either — the value was counted when its substitute was
    minted, and this reuses that substitute instead of creating a second one.
    `echoes` is `_echo_targets`' output: one `(value, digits)` pair per resolved
    value, so a multipart result pays for the identity read once, not per block.

    `recorded` is the SECOND, WEAKER leg: values this conversation restored that
    no call was bound to. They are answered with `_neutral_redaction` and never
    with a substitute, and a span the bound leg already claimed is left to it, so
    the specific identity always wins over the conservative answer. Neither leg
    writes inside a rendering this dialogue already showed (`renderings`).
    """
    blocked = _substitute_ranges(text, renderings)

    def _free(start: int, end: int) -> bool:
        return not any(start < stop and begin < end for begin, stop in blocked)

    specific = [(start, end, value.substitute)
                for value, digits in echoes
                for start, end in _typed_echo_spans(text, value, digits)
                if _free(start, end)]
    chosen = _choose_spans(specific)
    if recorded:
        neutral = [(start, end, _neutral_redaction(value.entity_type, value.real))
                   for value, digits in recorded
                   for start, end in _typed_echo_spans(text, value, digits)
                   if _free(start, end)]
        for span in _choose_spans(neutral):
            if not any(span[0] < claim[1] and claim[0] < span[1] for claim in chosen):
                chosen.append(span)
    return text if not chosen else _splice_chosen(text, chosen)


def conversation_key(messages: list[dict[str, object]]) -> str:
    """A conversation identity derived from the transcript itself.

    The caller may name the conversation and should; but neither wire format has
    a field for it — OpenAI's chat API has no conversation id, and a host gateway
    that never needed one will not start sending it because we added a scope. So
    the id is derived when it is not given, and the transcript supplies it: the
    OPENING messages of a conversation do not change as it grows, which is
    exactly the stability an identity needs.

    The first two messages, not one: a system prompt is often shared by every
    conversation an agent has, so hashing it alone would put the whole tenant in
    one scope and defeat the point. The first user turn is what differs.

    Hashed, never stored raw — this runs on customer text and the value is
    carried in cache keys and log-adjacent places where PII must not appear.

    A derived id is WEAKER than a given one and knowingly so: two conversations
    opening with byte-identical messages share a scope. The failure that causes
    is a partial mention resolving against the other conversation's address, so
    the linking rule must stay single-candidate — with two addresses in scope it
    refuses, which is the safe answer.
    """
    digest = hashlib.sha256()
    for message in messages[:2]:
        content = message.get("content")
        if isinstance(content, str):
            digest.update(content.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:32]

def _is_own_rendering(span: Span, own_renderings: frozenset[str]) -> bool:
    """Whether a detected span is a rendering this conversation already showed.

    Two readings of the same surface, because the wire writes it both ways: the
    exact string the dialogue showed, and the same string re-cased (`Чижова` →
    `чижова` inside JSON). A field that RE-TYPES the value (an accepted substitute
    under `phone` becomes an OPAQUE span, so the detector no longer calls it
    PHONE) still spans the SAME surface, so the first reading catches it; the
    numeric re-notations are already `is_own_substitute`'s digit-signature job.
    Membership is surface-based on purpose: it is exactly the condition the cache
    discriminator can reproduce from the text (see `_own_evidence_key`), so the
    guard can never fire on a text whose key did not record the evidence.
    """
    if not own_renderings:
        return False
    return span.value in own_renderings or span.value.casefold() in own_renderings


def _relevant_own_renderings(text: str,
                             own_renderings: frozenset[str]) -> frozenset[str]:
    """The part of the evidence THIS text can actually be affected by.

    `_is_own_rendering` fires only on a span the text contains, so a rendering
    that does not occur in the text (in any case) cannot change this call's
    output. Restricting the evidence to what occurs is what lets the cache key
    stay byte-identical to the old one for ordinary prose: a growing transcript
    resends the same message, its own-rendering set grows as the conversation
    mints, and a key built from the WHOLE set would miss and re-audit the same
    value — measured as `NAME audited 2 times, expected 1`. What is scoped is
    the EVIDENCE, not the guard: an occurring rendering is kept in full.
    """
    if not own_renderings:
        return frozenset()
    folded = text.casefold()
    return frozenset(rendering for rendering in own_renderings
                     if rendering and rendering.casefold() in folded)


def _own_evidence_key(relevant: frozenset[str]) -> str:
    """The cache discriminator for a masking call's OWN-RENDERING evidence.

    THE CACHE KEY MUST CARRY EVERY INPUT THE OUTPUT DEPENDS ON. `content_key` is
    `(org, conversation, raw text)`, and the rejected revision was free to reuse
    it alone because masking was a pure function of the text and the vault. The
    own-rendering guard makes the output depend on one more thing: the same
    string masks differently depending on whether the caller can see that it is
    a rendering this dialogue already showed. A cache hit from the evidence-free
    reading would then serve the re-minted fake to the evidence-bearing caller —
    the fake-of-a-fake the guard exists to prevent, restored through the cache.
    The discriminator is empty when no rendering occurs in the text, which is
    exactly when the guard is a no-op, so the ordinary prose/description path and
    the growing-transcript resend keep the exact key they had before.
    `frozenset.__hash__` is order-independent and cached, so this costs no sort.
    """
    if not relevant:
        return ""
    return f"\x00own\x00{len(relevant):d}\x00{hash(relevant) & 0xFFFFFFFFFFFFFFFF:016x}"


def _mask_one(text: str, context: MaskContext, own_renderings: frozenset[str]) -> str:
    """Mask one text, with the caller's own-rendering evidence made explicit.

    A content-keyed cache makes re-masking the SAME raw text (the O(n^2)
    growing-transcript case) an O(1) hit; the audit is recorded only on the cache
    MISS, so a value is counted once per unique (org, content), not once per
    resend. `own_renderings` is part of the key — see `_own_evidence_key` — and
    is a REQUIRED argument: the safe reading and the evidence-free reading are
    two different computations, and a default would let one silently stand in
    for the other.

    EVERY text goes through full detection — there is NO pre-filter skip. A
    pre-filter would have to stay a perfect superset of every recognizer's
    triggers forever; it silently failed that invariant (single Latin names and
    Latin-keyed KV like {"name":"john"} leaked raw to the model). In a fail-closed
    PII gateway that risk is unacceptable, and the cache already removes the
    repeated-work cost, so detection is never skipped."""
    relevant = _relevant_own_renderings(text, own_renderings)

    def _compute() -> str:
        # Spans whose value is one of OUR OWN tokens are dropped BEFORE anything
        # is minted or recorded. `mask_text` already refuses to replace them, but
        # this loop ran first and did not: an echoed token got a vault row of its
        # own (fake -> another fake, burning a slot in a finite pool) and an audit
        # event, which is the number the licensing server bills on. In a
        # multi-turn agent the model quotes its own tokens constantly, so the
        # inflation was proportional to conversation length. `_is_own_rendering`
        # extends the same refusal to a rendering shown in another CASE or
        # re-typed by a JSON field, which is exact-case `is_own_substitute` misses.
        spans = [span for span in context.detector.detect(text)
                 if not is_own_substitute(span, context.vault)
                 and not _is_own_rendering(span, relevant)]
        with stage("mask.tokenize_and_audit"):
            # Collected first, written once: one commit per MESSAGE instead of one
            # per entity. See AuditLog.record_many — per-span commits made four
            # workers under load fail most requests with `database is locked`.
            events = [
                (span.entity_type, tokenize_span(span, context.vault), span.value)
                for span in spans
            ]
            context.audit.record_many(context.org_id, context.agent_id, events)
        with stage("mask.splice"):
            return mask_text(text, context.vault, spans)

    with stage("mask.one"):
        masked, _hit = context.cache.get_or_compute(
            content_key(context.org_id, context.conversation_id, text)
            + _own_evidence_key(relevant),
            _compute,
        )
    return masked


def mask_one(text: str, context: MaskContext) -> str:
    """Mask one text with NO own-rendering evidence.

    The public entry: prose, system prompts and tool-schema descriptions are
    masked on detection alone, exactly as before. The tool-call/result traversal
    calls `_mask_one` with the conversation's frozen rendering set, because only
    there is the evidence both available and load-bearing."""
    return _mask_one(text, context, frozenset())


def _mask_content(content: object, provenance: _Provenance,
                  result_call: ToolCallContext | None,
                  recorded: tuple[tuple[_InjectedValue, str | None], ...]) -> object:
    """Mask a message's `content`, which is either a plain string or a list of
    content blocks (vision / multi-part). Non-text blocks (image_url,
    input_audio, …) pass through untouched; without the list branch, PII sitting
    in a text block of a multi-part message would reach the provider unmasked.

    `result_call` is the unique preceding call the reader resolved for THIS
    message, or None. Its values are read ONCE here, before the blocks are walked
    — from BOTH forms of its own arguments, see `_Provenance.values_for_replayed` —
    and so is each value's typed identity, so a three-block result does not re-read
    the same canonical three times — and the echo pass then runs after `mask_one`
    so the substitute it inserts is never fed back into detection. Passing no call
    is a parameter, not a default: the caller states the association or states its
    absence.

    `recorded` is the conversation's own restored values, offered as the WEAKER
    PRIVACY leg. It redacts conservatively instead of substituting a person, so a
    result is still protected without the product guessing who it is about.

    THE EXACT POLICY OF THE TWO LEGS, so it is a decision rather than a fallback:

      * ATTRIBUTION IS CALL-SCOPED. A result bound to a call is answered with the
        substitute(s) THAT call carried, as this request shows them; when the
        bound call resolved nothing, no person is named at all.
      * PRIVACY IS CONVERSATION-SCOPED. An echo of a value THIS dialogue restored
        is redacted even on a matched result the echo is not about — leaving it
        raw would put real personal data in the prompt, and the reader's refusal
        concerns WHO the echo belongs to, never WHETHER the dialogue handled it.
        What the conservative leg may never do is answer with a substitute: a
        value the bound call did not carry is not attributed to that call, and it
        is not attributed to any other call either (`_neutral_redaction` carries
        no identity). `recorded` is a conversation VIEW, so a foreign dialogue's
        rows are not in it and contribute nothing.
      * The price is stated: a legitimate non-PII mention of a recorded value in
        an armed result is redacted with it. Over-redaction of a value the
        dialogue itself restored is the fail-closed direction, and the ordinary
        quantities beside it are left to the typed floors and boundaries."""
    values = provenance.values_for_replayed(result_call) if result_call is not None else ()
    echoes = _echo_targets(values)
    own = provenance.own_renderings()
    renderings = provenance.renderings()

    def _mask_text_leg(text: str) -> str:
        """One text of a result, with the call's evidence applied FIRST.

        See `_reserve_echoes` for why the order is the fix rather than a
        performance detail; the fallback keeps the previous behaviour for every
        text whose echoes the reserve pass did not claim (a pure detection case,
        and the `recorded`-only privacy case)."""
        if echoes:
            reserved, replacements, nonce = _reserve_echoes(text, echoes, renderings)
            if replacements:
                masked = _splice_reserved(
                    _mask_one(reserved, provenance.context, own), replacements, nonce)
                return (_replace_echoes(masked, (), recorded, renderings)
                        if recorded else masked)
        masked = _mask_one(text, provenance.context, own)
        return masked if not echoes and not recorded else _replace_echoes(
            masked, echoes, recorded, renderings)

    if isinstance(content, str):
        return _mask_text_leg(content)
    if not isinstance(content, list):
        return content
    blocks: list[object] = []
    for block in content:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            masked_block = dict(block)
            masked_block["text"] = _mask_text_leg(block["text"])
            blocks.append(masked_block)
        else:
            blocks.append(block)
    return blocks


def _model_visible_call(call: ToolCallContext, context: MaskContext,
                        own_renderings: frozenset[str]) -> ToolCallContext:
    """The same call AS THE MODEL READS IT in this request, not as the customer
    replayed it.

    An OpenAI SDK appends the message it received to the next request verbatim,
    and both restoring legs (`unmask_response`, `/unmask_arguments`) hand the tool
    the REAL value, so a replayed `arguments` string carries the customer's own
    writing. Provenance read from THAT string asks the detector to recognise the
    value, which it declines for exactly the fragments this leg exists to protect
    (an 80-character cut is not a valid number), while the substitute the dialogue
    already showed resolves against the vault's own rendering index.

    The association is the reader's and is preserved to the character; only the
    arguments take this pass's masking. That masking already happened for the
    assistant message's own `_mask_tool_calls`, so this is the cache hit, not a
    second detection and not a new audit event. Nothing is inferred: a leaf that
    is neither a detection nor a recorded rendering stays unresolved, which is the
    refusal path, so an arbitrary real leaf still names nothing."""
    return ToolCallContext(
        call_id=call.call_id,
        name=call.name,
        arguments=_mask_one(call.arguments, context, own_renderings),
    )


def _mask_tool_calls(tool_calls: object, context: MaskContext,
                     own_renderings: frozenset[str]) -> object:
    """Mask the arguments of assistant tool calls replayed in the transcript."""
    if not isinstance(tool_calls, list):
        return tool_calls
    masked: list[object] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            masked.append(call)
            continue
        new_call = dict(call)
        function = new_call.get("function")
        if isinstance(function, dict):
            new_function = dict(function)
            if isinstance(new_function.get("arguments"), str):
                new_function["arguments"] = _mask_one(new_function["arguments"], context,
                                                      own_renderings)
            new_call["function"] = new_function
        masked.append(new_call)
    return masked


def mask_messages(
    messages: list[dict[str, object]],
    context: MaskContext,
    skip_template: bool,
) -> list[dict[str, object]]:
    """Mask every message. `skip_template` is OPT-IN and set only by the engine
    leg: there the system prompt is the agent's own template, not user PII, and
    running NER over tens of KB on every call is the bulk of the cost and could
    corrupt instructions. The PUBLIC /v1 leg does NOT skip — there the customer
    writes the system message and may put PII in it, which MUST be masked or it
    reaches the provider raw and breaks the Protected-key promise.

    The call/result association is read from the SAME raw transcript, once, and
    only a unique preceding `tool_calls[].id` grants it. A result with no
    association, a repeated id, a declaration that comes later or a tool name
    that disagrees is left to detection alone — the reader refuses rather than
    inferring from a name or from adjacency. The typed evidence behind that
    association is built once for the whole pass and memoised per call, so the
    number of blocks a result carries cannot multiply the work."""
    associations = tool_result_contexts(messages)
    provenance = _Provenance(context)
    # The record is frozen before the FIRST message is masked, because masking a
    # replayed call can mint a row in this very pass and a lazily built index would
    # read its own writing back as evidence. Built whenever a TOOL message is in
    # the transcript at all: the UNBOUND privacy leg needs the same frozen record
    # a bound one does, and a refused binding is exactly when it is needed.
    has_result = any(message.get("role") == "tool" for message in messages)
    has_calls = any(isinstance(message.get("tool_calls"), list) for message in messages)
    if has_result or has_calls:
        provenance.snapshot()
    own_renderings = provenance.own_renderings() if (has_result or has_calls) else frozenset()
    # The conversation's own restored values, read once for the whole pass and
    # offered to every tool message as the conservative leg. It is a conversation
    # VIEW, so a foreign dialogue's rows are not in it.
    recorded: tuple[tuple[_InjectedValue, str | None], ...] = (
        _echo_targets(provenance.recorded_values()) if has_result else ())
    masked: list[dict[str, object]] = []
    for index, message in enumerate(messages):
        new_message = dict(message)
        if skip_template and message.get("role") == "system":
            masked.append(new_message)
            continue
        # Only touch `content` if the message HAD one. Assigning unconditionally
        # added `"content": null` to assistant turns that carry only `tool_calls`
        # — a message shape neither leg produced before. Strict providers reject
        # the extra null field, and it also perturbs the byte-identical prefix
        # that prefix-cache accounting depends on.
        association = associations[index]
        result_call = association.call if association.status == "matched" else None
        # A REPLAYED CALL HAS TWO FORMS, AND THE RESULT LEG READS BOTH. The
        # customer's SDK appends the message it received verbatim, and both
        # restoring legs hand the tool the REAL value, so the raw `arguments`
        # routinely carry the customer's own writing; the same call can also carry
        # a leaf the model wrote as the substitute this dialogue showed it. Which
        # form a given LEAF is in is not a property of the call, so `_mask_content`
        # unions the values of both forms (`values_for_replayed`) instead of
        # adopting one form for the whole call: the per-call gate that read the
        # raw form first and stopped there let the mixed call answer with the real
        # value in the result while the model read the substitute in the call.
        #
        # THE CONSERVATIVE LEG IS FOR TOOL MESSAGES ONLY. A user or assistant
        # message is masked by detection, which is the right and only rule for
        # prose; handing every message the dialogue's recorded values would mask
        # ordinary text that merely resembles them.
        message_recorded = recorded if message.get("role") == "tool" else ()
        if "content" in new_message:
            new_message["content"] = _mask_content(new_message["content"], provenance,
                                                   result_call, message_recorded)
        if "tool_calls" in new_message:
            new_message["tool_calls"] = _mask_tool_calls(
                new_message["tool_calls"], context, own_renderings
            )
        masked.append(new_message)
    return masked


# Ключи схемы, под которыми лежит ВЛОЖЕННАЯ схема, а не значение. Обход идёт по
# ним, а не «по всем словарям подряд»: `enum` и `default` тоже словари или
# списки, и заходить в них нельзя — это КОНТРАКТ, а не текст.
_SCHEMA_BRANCHES: tuple[str, ...] = ("properties", "$defs", "definitions", "patternProperties")
_SCHEMA_NODES: tuple[str, ...] = ("items", "additionalProperties", "contains", "not")
_SCHEMA_LISTS: tuple[str, ...] = ("anyOf", "oneOf", "allOf", "prefixItems")
# Три формы описания инструмента, которые встречаются в поле. OpenAI кладёт
# схему под `function.parameters`, MCP — под `inputSchema`, Anthropic — под
# `input_schema`.
_SCHEMA_KEYS: tuple[str, ...] = ("parameters", "inputSchema", "input_schema")


def _mask_schema(node: object, context: MaskContext) -> object:
    """Схема JSON, у которой замаскированы все `description`, НА ЛЮБОЙ ГЛУБИНЕ.

    ОБХОД БЫЛ РОВНО ДВА УРОВНЯ, и этого мало для настоящей схемы. Пример с
    телефоном внутри `recipient.phones[].number.description` уходил провайдеру
    сырым на КАЖДОМ вызове — вложенный объект, элемент массива, ветка `anyOf`,
    цель `$ref` из `$defs`: ни одного из них старый обход не видел. Персональные
    данные в описании — это то, что писал разработчик заказчика, а не модель, и
    попадают они туда именно в примерах вложенных полей.

    `enum`, `const` и `default` НЕ ТРОГАЮТСЯ и не обходятся: это множество
    значений, которые модели РАЗРЕШЕНО писать, то есть контракт. Подменить их
    значит изменить контракт — обоснование то же, что было у прежней версии, и
    оно не изменилось от того, что обход стал глубже.
    """
    if isinstance(node, list):
        return [_mask_schema(one, context) for one in node]
    if not isinstance(node, dict):
        return node
    out = dict(node)
    if isinstance(out.get("description"), str):
        out["description"] = mask_one(out["description"], context)
    if isinstance(out.get("title"), str):
        out["title"] = mask_one(out["title"], context)
    for key in _SCHEMA_BRANCHES:
        if isinstance(out.get(key), dict):
            out[key] = {name: _mask_schema(one, context) for name, one in out[key].items()}
    for key in _SCHEMA_NODES:
        if isinstance(out.get(key), (dict, list)):
            out[key] = _mask_schema(out[key], context)
    for key in _SCHEMA_LISTS:
        if isinstance(out.get(key), list):
            out[key] = [_mask_schema(one, context) for one in out[key]]
    return out


def mask_tools(
    tools: object,
    context: MaskContext,
    skip_template: bool,
) -> object:
    """Mask the free-text DESCRIPTIONS of tool schemas.

    Tool descriptions routinely carry worked examples ("найти заказ, например
    phone='+79991234567'") and that phone reaches the provider on every single
    call. Because tokens are format-preserving the example stays a well-formed
    phone, so the model loses nothing.

    Only `description` (and `title`) fields are touched. Names, types and `enum`
    values are the tool CONTRACT: masking an enum would change the set of values
    the model is allowed to emit, and masking a name would break dispatch.

    ТРИ ФОРМЫ, А НЕ ОДНА. Прежняя версия требовала ключ `function` и молча
    пропускала инструмент без него — а это ровно форма MCP (`inputSchema`) и
    форма Anthropic (`input_schema`), у которых описание и схема лежат на
    верхнем уровне. Инструмент такой формы уходил провайдеру НЕТРОНУТЫМ
    целиком.

    `skip_template` follows the same rule as the system prompt — on the engine leg
    the schemas are the agent's own template and are left alone."""
    if skip_template or not isinstance(tools, list):
        return tools
    masked: list[object] = []
    for tool in tools:
        if not isinstance(tool, dict):
            masked.append(tool)
            continue
        new_tool = dict(tool)
        if isinstance(new_tool.get("function"), dict):
            new_tool["function"] = _mask_tool_body(new_tool["function"], context)
        else:
            new_tool = _mask_tool_body(new_tool, context)
        masked.append(new_tool)
    return masked


def _mask_tool_body(body: dict[str, object], context: MaskContext) -> dict[str, object]:
    """Описание инструмента и его схема, в какой бы из трёх форм они ни лежали."""
    out = dict(body)
    if isinstance(out.get("description"), str):
        out["description"] = mask_one(out["description"], context)
    for key in _SCHEMA_KEYS:
        if isinstance(out.get(key), dict):
            out[key] = _mask_schema(out[key], context)
    return out


def unmask_response(response: dict[str, object], vault: Vault) -> dict[str, object]:
    """Detokenize a non-streamed completion: assistant content + tool-call
    arguments. Rebuilt rather than mutated so the caller's object is untouched."""
    result = dict(response)
    choices = result.get("choices")
    if not isinstance(choices, list):
        return result
    new_choices: list[object] = []
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        new_choice = dict(choice)
        message = new_choice.get("message")
        if isinstance(message, dict):
            new_message = dict(message)
            if isinstance(new_message.get("content"), str):
                new_message["content"] = unmask_text(new_message["content"], vault)
            tool_calls = new_message.get("tool_calls")
            if isinstance(tool_calls, list):
                restored: list[object] = []
                for call in tool_calls:
                    if not isinstance(call, dict):
                        restored.append(call)
                        continue
                    new_call = dict(call)
                    function = new_call.get("function")
                    if isinstance(function, dict):
                        new_function = dict(function)
                        if isinstance(new_function.get("arguments"), str):
                            new_function["arguments"] = unmask_arguments(
                                new_function["arguments"], vault
                            )
                        new_call["function"] = new_function
                    restored.append(new_call)
                new_message["tool_calls"] = restored
            new_choice["message"] = new_message
        new_choices.append(new_choice)
    result["choices"] = new_choices
    return result
