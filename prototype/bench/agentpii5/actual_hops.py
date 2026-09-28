"""M0 — ACTUAL OUT tool crossings, measured without the case's timetable.

ADDITIVE. `observe.observe` and every line in `metrics.py` keep their
declared-hop semantics, their denominators and their numbers; nothing here
replaces them and nothing here replaces their scorer.

WHY THIS EXISTS. The historical OUT estimator starts from `case.hops` — the
timetable the CORPUS wrote — and looks for that tool in that turn. An agent may
act a turn early or late, split one scheduled action into two, or repeat a call;
a timetable can only call that a missing action (744 declared tool-arg hops
read `absent` on the 450 while a same-named tool ran elsewhere in the run).
Matching by tool name in another turn is worse: it can tie a re-search, a second
delivery, or data the agent had not been given to the wrong event. So this
estimator reads only `run.base.calls` — every written and restored leaf of every
ACTUAL call — and asks of each leaf: whose datum is this, and did the right
value come back?

CONTRACT — the order of the branches IS the contract:

  1. THE AGENT-WRITTEN SIDE CHOOSES THE IDENTITY. The substitute in the leaf is
     the evidence; `restored` is never consulted for it, and restoration is
     scored afterwards. A word the customer's OWN values carry in a GENERIC role
     (`contracts.GENERIC_PIECE_ROLES` — the settlement, the street type, the mail
     domain, the gender) is an ordinary token: it can neither prove a minted part
     nor choose an identity (v12).
  2. ONLY WHAT THE AGENT HAD ALREADY SEEN. A mention counts iff its message
     index <= the call's turn, or the recorded model-response boundary proves
     that its result was available. Legacy records use only an EARLIER user
     turn and `seq` as evidence of result availability.
     Two calls executed sequentially can belong to one model response. The
     archived runs lack those response boundaries: same-turn result knowledge
     is `not_identifiable`, never guessed from execution order. The
     run's full-run mint record (`ArmRun.substitutes`) is written at the end
     from everything the arm ever saw, so it is NOT evidence either.
  3. STRICT PARTS. A role leaf is matched by its exact typed part
     (`observe.part_matches`); there is no prefix and no declension guess. One
     entity is `identity + type + value + parts`, so a corrected value or a
     second datum of the same person is a different entity. An unresolved leaf
     is `unattributed`, never an invented match.
  4. FORM IS INDEPENDENT OF THE VALUE. Form is compared only where BOTH sides
     narrow to their own value; a form pass on its own is not a correctness
     pass, and `joint = value_ok and form_ok and not residual`.
  5. THE VALUE COLUMN IS INDEPENDENT OF THE TOOL'S NOTATION (v14). A LOC leaf
     that names no role is scored by the standard predicate first; where the
     tool returned the address components JOINED WITHOUT A SEPARATOR
     («Красноярск Энгельса»), the standard read calls a delivered street wrong.
     The second, narrower reading asks the same role question — every role
     `value_matches` compares — under the same `part_matches` predicate, so it
     can only move a false negative.

STATUSES. `matched`, `mixed`, `residual`, `value_wrong`, `unmasked_known`,
`ambiguous`, `unattributed`, `not_identifiable` are candidates; `not_applicable` is in no
denominator. `absent` does not exist here — an action never taken is not a
crossing. `unmasked_known` is a real corpus value in what the agent wrote (a
no-mask gateway prints zero on value/form/joint). `mixed` is one entity's
substitute standing beside another entity's REAL value in the same leaf. An
unchanged IDENTITY-typed leaf that no available mention explains is
`unattributed`; an enum, a quantity or a generic part (a settlement a tool
stores) is `not_applicable`.

RESIDUAL IS A LEAF FLAG AND THE STATUS IS THE IDENTITY VERDICT (v10, v12).
`residual` is measured on the restored text and the available substitute surfaces
with `_leaf_leak`, the ONE reader of the question — BEFORE any entity is chosen on
a refused leaf, and over EVERY item on a resolved one (v12), so the flag cannot
depend on which identity the branches picked either way. An
`ambiguous`/`unattributed`/`not_identifiable` row may carry `residual=True` with
`item_id=''` and `attributed=False`: the owner may be unresolved, the standing
fake may not. `residual` counts inside the SAME `candidates` denominator as
every other column, so an identity refusal can never be read as a privacy
improvement — and neither can a resolution. A `residual` row also needs
PROVENANCE of a minted part: a token the customer's own values carry in a
generic role is an ordinary word and not a leak
(`_minted_substitute_stands`). THE SAME generic proof is asked by the IDENTITY
reader, and for the same reason (v12): it can neither prove a leak nor choose a
person.

SCOPE. ACTUAL OUT tool-argument leaves only — `tool_arg`, `template` and
`summary`, decided by `contracts.hop_owner_of_leaf` and never by the case. The
IN leg, the answer and the chain are untouched. This is a conservative LOWER
BOUND over actual crossings with visible uncertainty; it is not a universal
causal fix, and it does not claim chains are solved.

`python3 -m bench.agentpii5.test_actual_hops` runs the pinned checks.
"""
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
import re

import pymorphy3

from bench.agentpii4.compare import ObservedCall
from bench.agentpii4.parts import _PATRONYMIC_TAIL, parts_of
from bench.agentpii4.schema import PiiItem
from bench.agentpii4.tools import FieldSpec, flatten
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import ArmRunV5, CaseV5, MentionRecord, Needle
from bench.agentpii5.form import form_match
from bench.agentpii5.metrics import leaf_value_ok
from bench.agentpii5.observe import (
    DERIVED_TYPES,
    carries_any,
    digits_of,
    fold,
    item_needles,
    latin_prefixes,
    own_pair,
    own_stems,
    part_matches,
    spoken_digits_of,
    stem_of,
    # THE NEEDLE LAYER HAS ONE IMPLEMENTATION AND IT IS `observe`, which is why
    # three of its names are read here rather than restated: `_needle_spans` is
    # the ONE answer to «where does this needle stand», `_WORD`/`MIN_PIECE` are
    # the ONE answer to «what is a word, and how much of one identifies». A
    # second copy of any of them would drift, and the witness would then
    # disagree with `residual` about the same span.
    _WORD,
    MIN_PIECE,
    _needle_spans,
)
from bench.agentpii5.tools import REGISTRY_V5, expected_leaf_value, spec_v5_for

# M0 §6.2: an estimator that moves a denominator under the same name lets a
# counting fix be read as an engine improvement. The historical lines stay
# reproducible because the code that computed them still computes them.
#
# v8 vs v7 — M02-F1, THE LEAK SIDE'S WHOLE/PART SEPARATION (review §4). v7
# asked `observe.item_survives_in` whether a STEM of a real value stood in the
# agent-written text, and a stem is `PIECE_MIN_CHARS` letters of one role: the
# real surname «фёдорова» fired inside the PATRONYMIC «Фёдоровна» of a
# different person, and the real initials «В. И.» of one entity matched the
# initials of another entity's substitute. Both charged the wrong entity as
# `unmasked_known` and both were present on the saved 450 (chain-033,
# tool_chain-034). v8 asks each needle in the token it landed on and refuses a
# stem that is not the same lexeme — plus a contrary-name check so a written
# span that is a whole rendering of ANOTHER item's substitute cannot be charged
# as this item's leak. The COUNT moves on the saved archive, which is why the
# version moves with it.
#
# v11 vs v10 — THE ROLE BRANCH'S TYPED, PER-ITEM EXEMPTION (M02 third
# independent REJECT, `m02-orthogonal-residual-recheck-20260928.md` §4). v10
# carried the residual answer through unresolved statuses, but
# `_substitute_stands` RETURNS AT THE ROLE BRANCH before either exemption set is
# read, so `_minted_substitute_stands` never consulted `case_own`/`item_own`/
# `generic` on a role-typed leaf. The engine PRESERVES the settlement in an
# address substitute, so the substitute's city part and the customer's own city
# are the same string and the role test fired on the customer's own word: 140 of
# the 205 `residual`-status rows on the saved 450 (113 `to_location.city`, 18
# `contact.address.city`, 9 `address.locality`) had `restored == expected` and
# were printed as the critical defect. v11 adds ONE typed check to the residual
# reader: for a `contracts.GENERIC_PIECE_ROLES` role it declines a role part
# PROVEN to be THIS item's own real part (unchanged), and delegates otherwise.
# The check is deliberately narrow and cannot suppress a genuine leak: a role
# part that differs from the customer's own is a minted part and still stands, a
# surname role (F2's collision) is not generic and is untouched, and the identity
# reader `_written_has_substitute` keeps the v9 role reading unchanged. The
# COUNT moves on the saved 450 (residual status 205 -> 65, residual flag total
# 768 -> 628, matched/value_ok +140, candidate denominator unchanged), which is
# why the version moves with it.
#
# v10 vs v9 — RESIDUAL IS AN ORTHOGONAL LEAF SIGNAL (M02 second independent
# REJECT, `m02-leak-side-v9-recheck-20260928.md` §3/§6). v9 computed `residual`
# inside `_restoration`, which runs only for a CHOSEN entity, so `_unresolved()`
# hard-coded `residual=False`: on `tool_chain-009 seq 15` a byte-identical
# written/restored address whose minted street substitute `Пихтовая` was still
# standing read `ambiguous` with `residual=False`, and the 450 lost 22 residual
# rows to `ambiguous`/`not_identifiable` while the set of leaves holding a
# standing fake did not move. v10 asks the leak question of the RESTORED text and
# the AVAILABLE substitute surfaces BEFORE identity selection and carries the
# answer through an unresolved status with `item_id=''` — the leaf's owner may
# stay unknown, its leak may not. The second half of the repair is provenance: a
# token the customer's own values carry in a GENERIC role (the settlement, the
# street type, the mail domain, the gender — `contracts.GENERIC_PIECE_ROLES`) is
# an ordinary token and cannot prove a MINTED part, which is what kept i8's
# whole-address substitute from owning i7's leaf through the city «Орёл».
# Estimated to raise `residual` on the saved 450 back toward the v7/v8 reading
# without charging any wrong person; the version moves with the number.
#
# v9 vs v8 — THE COLLISION REPAIR (M02-F1/F2, independent recheck 2026-09-28).
# v8 asked every rival for its substitute at `(0, 0)`, so a fake the agent had
# read at message 1 was invisible to the collision guard and a CORRECT
# restoration of A was charged to B as B's real leak; and the role-less fallback
# computed the item's own exemption and then read it backwards, so the branch
# that credits the fake's owner could never run and the leaf stayed
# `unattributed` at best. v9 asks EVERY ownership question with the current
# call's turn and seq — availability means the same thing on both sides of the
# leaf, and a mention after the call is not evidence — and reads the two
# exemption sets in the order that names the substitute's owner. The COUNT moves
# on the saved 450 (residual 235 -> 213, ambiguous 1184 -> 1209,
# not_identifiable 668 -> 716; no new `unmasked_known` and no re-attribution
# between two named entities), which is why the version moves with it.
#
# v12 vs v11 — THE ROLE-LESS BRANCH'S GENERIC-VOCABULARY PROOF (M02's remaining
# blocker after the v11 recheck; read-only E2E on the saved 450). v11 proved that
# a GENERIC role word of the customer's own values cannot make a MINTED part, but
# only inside `_minted_substitute_stands`'s role branch and only for the RESIDUAL
# question. The identity reader `_written_has_substitute` still asked the
# ROLE-LESS question with two exemption sets and read `case_own` cancelled /
# `item_own` standing as «ANOTHER entity's real value explains the word», so
# `tool_chain-036 seq 4 path 'query'` — written == restored == «Челябинск 19
# километров», i8's whole-address substitute «г Челябинск, ул Пихтовая, д 83» —
# was credited to i8 and printed `value_wrong`, although the ONLY matching needle
# was the generic settlement «Челябинск», a city i7 and i9 carry in their OWN
# generic parts. The fallback's premise is sound only for IDENTIFYING customer
# vocabulary (M02-F2's colliding surname): exempting the GENERIC set alone leaves
# every identifying needle standing, so a surface that NO LONGER stands under it
# was kept alive by an ordinary settlement/street-type/domain/gender word and
# proves no minted part and no identity. v12 adds that ONE check to the SHARED
# `_substitute_stands`, so both readers ask it — the residual reader already
# passed `generic` through both sets and reaches the same answer one step
# earlier, so the check itself moves nothing there; the identity reader stops
# crediting a person from a generic word.
#
# THE SECOND HALF OF v12 IS FORCED BY THE FIRST, and it is the same
# orthogonality v10 demanded of a REFUSAL, applied to a RESOLUTION. Once i8's
# generic candidacy is refused, leaves v11 called `ambiguous` resolve to their
# one evidenced owner — and `_restoration` asked the leak question only of that
# winner, so a standing fake of ANOTHER item would vanish with the ambiguity.
# That is not hypothetical: `tool_chain-008 seq 7`, `tool_chain-030 seq 6` and
# `tool_chain-034 seq 10` carry a minted street still standing in the restored
# text on exactly those leaves, and `long_order-018/023/045/048` already hid one
# behind a resolved NAME. `_restoration` now asks `_leaf_leak` — the ONE reader
# of the question, the one the refusal branches already used — so the flag
# cannot depend on which entity the identity branches picked.
#
# THE COUNT MOVES ON THE SAVED 450 (before -> after, same 450 complete triples,
# 11565 actual leaves): candidates 6465 -> 6462 (`.not_applicable` 5100 ->
# 5103), attributed 3855 -> 3895, value_ok 3655 -> 3655 (`matched` unchanged),
# `residual` status 65 -> 102, residual flag 628 -> 639, value_wrong 127 -> 130,
# ambiguous 1209 -> 1184, not_identifiable 716 -> 668, unattributed 685 -> 715,
# unmasked_known 8 -> 8, mixed 0 -> 0, joint 3314 -> 3313. NO ROW THAT CARRIED
# `unmasked_known`/`mixed` MOVED AND NO v11 RESIDUAL FLAG WAS LOST — checked
# row for row against `/private/tmp/m02v11/report-v11/events.jsonl`. The
# version moves with the numbers.
#
# The LOC query rescue is limited to one joined address whose city and street
# type are declared by this item. The first value predicate still decides all
# other fields. Containment alone credited a wrong street followed by the right
# one and charged an undeclared city or a different street type as correct.
# The saved 450 now has 3666 matched/value_ok and 119 value_wrong; the two
# v13 false passes are visible, while identity, residual and denominators stay
# unchanged. These are offline scorer counts, not a new provider result.
ESTIMATOR_VERSION: str = "m0-actual-out-v14"

ACTUAL_STATUSES: tuple[str, ...] = (
    "matched", "mixed", "residual", "value_wrong", "unmasked_known", "ambiguous",
    "unattributed", "not_identifiable", "not_applicable")
# Every denominator. `not_applicable` is the one status that is not a candidate:
# a leaf carrying no known personal datum must not flatter every rate.
CANDIDATE_STATUSES: tuple[str, ...] = (
    "matched", "mixed", "residual", "value_wrong", "unmasked_known", "ambiguous",
    "unattributed", "not_identifiable")


class ActualHopsError(ValueError):
    """`call_turns` and `base.calls` disagree — a run that would silently
    re-attribute every call."""


@dataclass(frozen=True)
class ActualEvent:
    """ONE actual leaf of ONE actual call, and the verdict on it.

    `event_id` is `seq|field|item` and carries NO turn: the same action one turn
    later is the same event. `written`/`restored` are the two sides; `expected`
    is what this leaf asked for (`tools.expected_leaf_value`). `attributed` says
    whether ONE entity could be named — a property of the measurement, not of
    the gateway. `form_measured` is False when either side could not be narrowed
    to its own value, so the form column reports only what it could read.
    """

    event_id: str
    case_id: str
    repeat: int
    call_seq: int
    call_turn: int
    tool_name: str
    owner: str
    path: str
    item_id: str
    identity: str
    pii_type: str
    status: str
    written: str
    restored: str
    expected: str
    candidate_ids: tuple[str, ...]
    evidence: str
    attributed: bool
    value_ok: bool
    form_ok: bool
    form_measured: bool
    residual: bool
    form_differs: tuple[str, ...]


@dataclass(frozen=True)
class ActualRunObservation:
    """Every actual OUT leaf of one (case, repeat) of the gateway arm."""

    case_id: str
    repeat: int
    events: tuple[ActualEvent, ...]


@dataclass(frozen=True)
class TypeAggregate:
    """One line of the versioned table. `candidates` is the ONE denominator of
    `attributed`, `value_ok`, `form_ok`, `residual` and `joint_ok`; sharing it
    is what stops a form rate being read as a joint success. `form_unmeasured`
    counts the candidates whose form could not be read at all."""

    pii_type: str
    candidates: int
    attributed: int
    value_ok: int
    form_ok: int
    form_unmeasured: int
    residual: int
    joint_ok: int
    statuses: tuple[tuple[str, int], ...]

    def count(self, status: str) -> int:
        """How many candidates carry one status; 0 when absent here."""
        return next((count for name, count in self.statuses if name == status), 0)


@dataclass(frozen=True)
class ActualAggregate:
    """The overall line and one line per PII type. An event the estimator could
    not type lands in a `""` line instead of being charged to a real type."""

    estimator: str
    runs: int
    events_total: int
    not_applicable: int
    overall: TypeAggregate
    by_type: tuple[TypeAggregate, ...]


@dataclass(frozen=True)
class _Decision:
    """What `_decide` concluded about one leaf, before it becomes an event."""

    status: str
    item_id: str
    identity: str
    pii_type: str
    expected: str
    candidate_ids: tuple[str, ...]
    evidence: str
    attributed: bool
    value_ok: bool
    form_ok: bool
    form_measured: bool
    residual: bool
    form_differs: tuple[str, ...]


# --- reading the run --------------------------------------------------------------------

def _leaf_str(value: object) -> str:
    """One leaf as the consumer received it; a number is still a form."""
    return value if isinstance(value, str) else ("" if value is None else str(value))


def _mention_available(run: ArmRunV5, mention: MentionRecord, call_turn: int,
                       call_seq: int) -> bool:
    """Prove prior disclosure without inventing missing model-response clocks."""
    if mention.msg >= 0 and mention.msg <= call_turn:
        return True
    if run.model_trace is not None:
        trace = run.model_trace
        if len(trace.call_requests) != len(run.base.calls):
            raise ActualHopsError("model trace does not map every recorded call")
        call_index = next((index for index, call in enumerate(run.base.calls)
                           if call.seq == call_seq), None)
        result_index = next((index for index, call in enumerate(run.base.calls)
                             if call.seq == mention.result_seq), None)
        if call_index is None or result_index is None or result_index >= call_index:
            return False
        request = trace.call_requests[call_index]
        response = next((row for row in trace.responses if row.request == request), None)
        if response is None:
            raise ActualHopsError(f"call {call_seq} refers to missing response {request}")
        return (trace.call_requests[result_index] < request
                and result_index < response.available_results
                and any(result.seq == mention.result_seq for result in run.tool_results))
    return 0 <= mention.result_seq < call_seq and any(
        result.seq == mention.result_seq and result.turn < call_turn
        for result in run.tool_results)


def _available_surfaces(run: ArmRunV5, item_id: str, call_turn: int,
                        call_seq: int) -> tuple[str, ...]:
    """The spellings of one item's substitute the agent had ALREADY read, from
    `run.mentions` alone. `run.base.substitutes` is written at the end of the
    run from everything the arm ever saw, so reading it would hand the agent its
    own future; an item with no earlier mention has no evidence and its leaf
    stays unresolved rather than guessed."""
    out: list[str] = []
    for mention in run.mentions:
        if mention.item_id != item_id or not mention.substitute:
            continue
        if not _mention_available(run, mention, call_turn, call_seq):
            continue
        if mention.substitute not in out:
            out.append(mention.substitute)
    return tuple(out)


def _role_parts(item: PiiItem, role: str, surfaces: Sequence[str]) -> tuple[str, ...]:
    """Every spelling of ONE role of an item's substitute, read off the mentions
    the agent had seen. No run-level mint record and no real value takes part:
    a substitute whose role cannot be read back off an available surface simply
    has no part, and the leaf stays unresolved."""
    out: list[str] = []
    for surface in surfaces:
        declared_roles = {name for name, value in item.parts.items() if value and name != "gender"}
        if declared_roles == {role}:
            # A corpus-declared singleton already has a role; parsing a lone
            # surname as a new full name can silently turn it into a given name.
            part = surface
        elif role not in declared_roles:
            part = ""
        else:
            part = parts_of(item.type, surface).get(role, "")
        if part and part not in out:
            out.append(part)
    return tuple(out)


def _renders_part(pii_type: str, text: str, part: str) -> bool:
    """Is `text` EXACTLY this part, in the part's own notation.

    `part_matches` is the whole rule: digits with digits, a date's ISO fold, a
    squeezed plate, the folded string otherwise. A four-character prefix is NOT
    identity evidence — «Иванов» must not attribute to «Иваненко» — and a
    declined form the tool schema did not write stays unresolved instead of
    being guessed at. That costs matches and is the intended direction."""
    if not text.strip() or not part:
        return False
    return part_matches(pii_type, text, part)


def _substitute_stands(item: PiiItem, spec: FieldSpec | None, surfaces: Sequence[str],
                       text: str, case_own: frozenset[str], item_own: frozenset[str],
                       case: CaseV5, run: ArmRunV5, call_turn: int,
                       call_seq: int) -> bool:
    """Does `text` carry this item's SUBSTITUTE, given the two exemption sets?

    ONE IMPLEMENTATION, TWO EXEMPTION SETS. `case_own`/`item_own` are the only
    arguments that differ between the two questions this layer is asked, so the
    two readers cannot disagree about which needle landed where:

      * `_written_has_substitute` — the IDENTITY question, asked of the text the
        agent WROTE, with the customer's case-wide stems and this item's own
        renderings. That is the reading M02-F1/F2 repaired;
      * `_minted_substitute_stands` — the RESIDUAL question, asked of the text
        the consumer RECEIVED, with the customer's GENERIC-role stems added to
        BOTH sets, so an ordinary settlement/street-type/domain/gender token
        cannot prove a minted part (review §6.2, the i8-vs-i7 refusal).

    A role leaf is asked about that part ALONE: the loose reading would match
    the given name in a surname leaf and attribute `contact.last_name` to a name
    whose surname is nowhere in it. A role-less leaf (a free text, a joined
    address, a transliteration) has no single part to ask about, so the whole
    value's needles are the right question. A short contained substring is not
    identity evidence without a declared role: a phone containing '25' cannot
    own patient.age=25. Only the surfaces AVAILABLE TO THIS CALL may be
    evidence, and `call_turn`/`call_seq` are carried down to every ownership
    question so a rival's substitute disclosed after this call cannot explain
    it (M02-F1).

    TWO EXEMPTION SETS, AND THE DIFFERENCE BETWEEN THEM IS THE WHOLE ANSWER.
    `case_own` is the customer's own words CASE-WIDE (`observe.own_stems(case)`), so a
    fake of this item that is also ANOTHER item's real value is cancelled before
    the question is asked; `item_own` is THIS item's own renderings alone.
    The case-wide question can therefore fail for THREE different reasons, and
    they do not all have the same answer:

      * THIS ITEM'S OWN real value explains the word — the narrowed question
        fails too, so this item's own renderings ALONE cancel every needle the
        word matched. A verbatim surface cannot land here (`whole` is not an
        EXEMPTABLE_KIND and still counts), so this is a DECLINED or initials
        reading whose stem the item's own real value also carries — the engine
        mints from a pool, so a fake may reuse the customer's own surname — and
        the word is then read as the real value rather than the fake;
      * THE CUSTOMER'S OWN GENERIC VOCABULARY explains the word while identifying
        needles would still stand: a settlement/street-type/domain/gender token
        is an ordinary word and proves no minted part (v12). A whole-address
        substitute is read by `parts_of`, which folds the settlement into the
        street blob, so «г Челябинск, ул Пихтовая, д 83» offers a street-role
        stem of the CITY; when the customer's own values carry that city as a
        generic part the needle was never a minted part, and the substitute does
        not stand. The test is exact: with ONLY the generic set exempt, some
        matching needle still stands ⟺ a matching needle is not generic; if NONE
        stands, every matching needle was generic vocabulary;
      * ANOTHER item's real IDENTIFYING value explains the word while the narrowed
        question still passes: review §4's collision, where A's fake «Пахомова»
        is B's real surname and the written word is A's SUBSTITUTE.

    THE GENERIC GATE RUNS BEFORE THE NARROWED FALLBACK, because the fallback's
    premise — «another entity's real IDENTIFYING value explains the case-wide
    cancellation» — is false when an ordinary generic word is the whole
    explanation. Past it, the narrowed question MUST be reachable: it decides
    whether the collision hides this item's fake, and a `True` there means «the
    substitute stands once only this item's own renderings are exempt» — the
    fake's owner is credited. Reading it backwards (refusing the substitute when
    it is the only reading left) made the branch dead and left the role-less
    leaf `unattributed` at best and charged to the colliding real value at
    worst, which is exactly M02-F2.

    `restored` is not read either way: the agent-written side chooses identity."""
    if spec is not None and spec.role:
        return any(_renders_part(item.type, text, part)
                   for part in _role_parts(item, spec.role, surfaces))
    if carries_any(item.type, surfaces, text, case_own):
        return True
    if not carries_any(item.type, surfaces, text, generic_stems_of(case)):
        # THE CANCELLATION WAS THE CUSTOMER'S OWN GENERIC VOCABULARY (v12). With
        # only the generic set exempt nothing stands, so every needle this word
        # matched is settlement/street-type/domain/gender vocabulary the
        # customer's own values already carry: the word proves no minted part and
        # chooses no identity. Asked BEFORE the narrowed fallback, so the
        # collision reading cannot be bought with an ordinary word. The residual
        # reader reaches the same answer one step earlier (it passes `generic`
        # through BOTH sets), which is why its numbers do not move.
        return False
    if not carries_any(item.type, surfaces, text, item_own):
        # THE CANCELLATION WAS THIS ITEM'S OWN REAL VALUE. With only its own
        # renderings exempt the substitute no longer stands either, so the
        # written word is that real value and not this item's fake.
        return False
    # ONLY THIS ITEM'S OWN RENDERINGS ARE EXEMPT AND THE SUBSTITUTE STILL
    # STANDS: the case-wide cancellation came from ANOTHER entity's real value.
    # Whose FAKE the word is decides it; a rival's whole substitute is that
    # item's evidence and not this one's, at the SAME call.
    if _owned_by_substitute(case, run, text, call_turn, call_seq, exclude=item.id):
        return False
    return True


def _written_has_substitute(item: PiiItem, spec: FieldSpec | None, surfaces: Sequence[str],
                            text: str, own: frozenset[str], case: CaseV5,
                            run: ArmRunV5, call_turn: int, call_seq: int) -> bool:
    """THE IDENTITY QUESTION: does the AGENT-WRITTEN text carry this item's fake?

    The reading M02-F1/F2 pinned, plus v12's shared generic-vocabulary proof
    inside `_substitute_stands`: a word the customer's own values carry in a
    GENERIC role proves no minted part, so it cannot choose an identity either.
    It stays the ONLY reading the identity branches of `_decide` may use, and it
    reads the CURRENT call's evidence (`call_turn`/`call_seq`), never
    `restored`."""
    return _substitute_stands(item, spec, surfaces, text, own,
                              own_stems_of(case, item), case, run, call_turn, call_seq)


def _minted_substitute_stands(item: PiiItem, spec: FieldSpec | None,
                              surfaces: Sequence[str], text: str, own: frozenset[str],
                              case: CaseV5, run: ArmRunV5, call_turn: int,
                              call_seq: int) -> bool:
    """THE RESIDUAL QUESTION: does the RECEIVED text carry this item's MINTED fake?

    The same search as the identity question, with the customer's GENERIC-role
    stems added to BOTH exemption sets. A substitute surface a model wrote
    cannot be trusted to type its own address: `parts_of` folds the settlement of
    a whole-address surface into its street blob, so «г Орёл, ул Ольховая, д 163»
    yields a street-role stem «оре» that fires on ANY leaf carrying «Орёл».
    Charging that as residual would mark a leaf residual on an ordinary word the
    customer's own addresses already carry — review §6.2's i8-vs-i7 refusal, and
    the reason the generic-city-only negative exists. A genuinely minted part
    (i7's «Пихтовая») is not in the customer's real vocabulary at all and still
    fires, including through the collision fallback F2 needs.

    Generic means `contracts.GENERIC_PIECE_ROLES` — the settlement, the street
    type, the mail domain, the grammatical gender — read off the customer's OWN
    values. It is deliberately NOT the case-wide `own_stems`: a real surname that
    collides with a fake (M02-F2) is identifying vocabulary, and exempting it
    would silently delete the residual the collision is supposed to show.

    THE ROLE BRANCH LEAVES `_substitute_stands` BEFORE EITHER EXEMPTION SET IS
    READ, so from v11 the role question is asked here first, and only where it
    can be answered from THIS item's own declaration. For a GENERIC role, a role
    part that `part_matches` the customer's OWN real part for that role is the
    customer's own word UNCHANGED — the engine preserves the settlement in an
    address substitute, and v10 charged 140 such city leaves as residual while
    the tool received exactly `expected`. THE CHECK IS TYPED AND PER-ITEM, which
    is the whole reason it cannot over-suppress: a role part that differs from
    the item's real part is a minted part and still stands, a surname role is not
    generic and is untouched (F2), and an item that declares no such part falls
    through to the v9-v10 reading rather than being exempted on a guess. The
    IDENTITY reader never sees THIS branch — `_written_has_substitute` keeps the
    v9 role reading — but from v12 it does ask the same generic-vocabulary
    question on the ROLE-LESS branch, through the shared `_substitute_stands`
    (this reader reaches that answer one step earlier, since `generic` is already
    in both of its exemption sets)."""
    if spec is not None and spec.role in contracts.GENERIC_PIECE_ROLES:
        real_part: str = item.parts.get(spec.role, "")
        if real_part and any(_renders_part(item.type, text, part)
                             and part_matches(item.type, part, real_part)
                             for part in _role_parts(item, spec.role, surfaces)):
            return False
    generic = generic_stems_of(case)
    return _substitute_stands(item, spec, surfaces, text, own | generic,
                              own_stems_of(case, item) | generic, case, run,
                              call_turn, call_seq)


@lru_cache(maxsize=512)
def _generic_stems_of_case(case_id: str,
                           parts: tuple[tuple[str, str], ...]) -> frozenset[str]:
    """`stem_of` of every word the customer's OWN values carry in a GENERIC role.

    Keyed on the (role, value) pairs themselves, not on the case id alone, so a
    fixture and a corpus case that share an id cannot share an answer."""
    out: set[str] = set()
    for role, value in parts:
        if role not in contracts.GENERIC_PIECE_ROLES or not value:
            continue
        for word in _WORD.findall(value):
            if len(fold(word)) < MIN_PIECE:
                continue
            out.add(stem_of(word))
    return frozenset(out)


def generic_stems_of(case: CaseV5) -> frozenset[str]:
    """The case's GENERIC-role stems, cached per case."""
    key = tuple(sorted((role, value) for item in case.base.pii
                       for role, value in item.parts.items()
                       if role in contracts.GENERIC_PIECE_ROLES and value))
    return _generic_stems_of_case(case.base.id, key)


def _entity_of(item: PiiItem) -> str:
    """The ENTITY a corpus record names: identity, TYPE, VALUE and typed parts.

    Type and value are in the key, not only `identity`. One person has several
    data of several types,
    and a corrected value (`stale`, or a `.new` address) is a DIFFERENT entity
    from the value it replaces. Keying on identity alone welded a name, a phone
    and an old address into one entity, chose the lowest id among them, and
    scored a leaf carrying two phone values of one person as one clean match —
    the silent min-id pick this key exists to refuse."""
    parts = "|".join(f"{role}={fold(value)}" for role, value in sorted(item.parts.items()))
    return f"{item.identity}|{item.type}|{fold(item.canonical or item.value)}|{parts}"


def _projection_owner(items: Sequence[PiiItem], spec: FieldSpec | None) -> PiiItem | None:
    """Prove a typed whole/part alias using declared parts, not restored output.

    One candidate must contain every other's declared parts. Conflicting full
    versions, missing identities and different people therefore cannot merge.
    This is deliberately narrower than grouping by identity or a shared surname.
    """
    if spec is None or not spec.role or not items:
        return None
    first = items[0]
    if not first.identity or first.type not in ("NAME", "LOC"):
        return None
    if any(item.identity != first.identity or item.type != first.type or
           item.stale != first.stale or not item.parts.get(spec.role) for item in items):
        return None
    part_sets = tuple(frozenset((role, fold(value)) for role, value in item.parts.items()
                               if value and role != "gender") for item in items)
    maximal = tuple(item for item, parts in zip(items, part_sets)
                    if all(other <= parts for other in part_sets))
    if not maximal:
        return None
    # Different canonical values with equal part sets remain different versions.
    if len({_entity_of(item) for item in maximal}) != 1:
        return None
    return min(maximal, key=lambda item: item.id)


def _one_entity(items: Sequence[PiiItem], spec: FieldSpec | None) -> tuple[PiiItem | None, tuple[PiiItem, ...], str]:
    """Collapse the candidate records to ONE entity, or refuse.

    Returns the representative (the lowest id, so the choice is deterministic),
    every candidate record still visible, and the reason. `None` means the
    candidates name more than one entity and the leaf is `ambiguous` — never a
    coin flip, which is M0 §6.3's «при неоднозначности — unmatched/ambiguous»."""
    ordered = tuple(sorted(items, key=lambda item: item.id))
    groups: dict[str, list[PiiItem]] = {}
    for item in ordered:
        groups.setdefault(_entity_of(item), []).append(item)
    if len(groups) == 1:
        members = next(iter(groups.values()))
        return min(members, key=lambda item: item.id), ordered, "one entity"
    projected = _projection_owner(ordered, spec)
    if projected is not None:
        return projected, ordered, "one declared whole/part projection"
    return None, ordered, f"{len(groups)} entities (" + ", ".join(sorted(groups)) + ")"


def _common_type(items: Sequence[PiiItem]) -> str:
    """The type of an unattributable event, when every candidate agrees on it."""
    types = {item.type for item in items}
    return next(iter(types)) if len(types) == 1 else ""


def _identity_shaped(spec: FieldSpec | None) -> bool:
    """Is this leaf typed to carry ONE identity, by a role that identifies?

    True for `contact.last_name` (surname) or `contact.phone` (digits); False
    for an enum, a quantity, a `derived` rendering and for a generic role such
    as `contact.address.city`. Used only to decide whether an UNCHANGED leaf
    that no mention explains is `unattributed` (a crossing we could not resolve)
    or `not_applicable` (ordinary traffic)."""
    if spec is None or spec.kind != "identity":
        return False
    if not spec.role:
        return True
    return spec.role in contracts.IDENTIFYING_ROLES.get(spec.pii_type, ())


def _unresolved(status: str, items: Sequence[PiiItem], evidence: str,
                residual: bool = False) -> _Decision:
    """An unresolved leaf — and, since v10, the leaf's OWN leak answer.

    `residual` is carried, not forced to False: the identity question may refuse
    while the leak question is answered by the restored text and the available
    substitute surfaces. The row keeps `item_id=''` and `attributed=False`, so a
    standing fake is reported WITHOUT naming a person the evidence did not
    choose — never a wrong-person charge, and never a silent pass."""
    return _Decision(status=status, item_id="", identity="",
                     pii_type=_common_type(items), expected="",
                     candidate_ids=tuple(sorted(item.id for item in items)),
                     evidence=evidence, attributed=False, value_ok=False, form_ok=False,
                     form_measured=False, residual=residual, form_differs=())


def _mixed(chosen: PiiItem, involved: Sequence[PiiItem], evidence: str) -> _Decision:
    """One entity's substitute beside another entity's REAL value in one leaf.

    The fake is named and the pass is refused: a free-text leaf that carries a
    clean substitute AND an unrelated real value hides the second, and M0 §6.3
    forbids accepting the one while the other is unmeasured. Splitting the leaf
    into spans is later work; until then this is a visible miss."""
    return _Decision(status="mixed", item_id=chosen.id, identity=chosen.identity,
                     pii_type=_common_type(involved), expected="",
                     candidate_ids=tuple(sorted(item.id for item in involved)),
                     evidence=evidence, attributed=False, value_ok=False, form_ok=False,
                     form_measured=False, residual=False, form_differs=())


def _renders_address(item: PiiItem, spec: FieldSpec | None,
                     produced: str, target: str) -> bool:
    """Recognize a single joined city/street query, with no competing values.

    The standard value predicate runs first. This narrower reading covers the
    saved `address_suggest.query` shape where an optional known city precedes
    the expected street without a separator. Every produced word must belong
    to that one address. Containment alone is unsafe: a wrong street followed
    by the expected street, or a note naming an old address, is not a pass.
    Numeric roles must be declared by the target or by this same item; extra
    numbers and unsupported alphanumeric house forms remain unresolved."""
    if spec is None or spec.kind != "identity" or spec.pii_type != "LOC" or spec.role:
        return False
    expected_parts = parts_of("LOC", target)
    street = expected_parts.get("street", "").strip()
    if not street or re.search(r"\d", street):
        return False
    words = tuple(fold(word) for word in _WORD.findall(produced))
    street_words = tuple(fold(word) for word in _WORD.findall(street))
    city_words = tuple(fold(word) for word in _WORD.findall(item.parts.get("city", "")))
    type_words = tuple(fold(word) for word in _WORD.findall(item.parts.get("street_type", "")))
    if not street_words or re.search(r"\d[^\W\d_]", produced):
        return False
    joined = False
    for repeats in range(3 if city_words else 1):
        for has_type in (False, True) if type_words else (False,):
            prefix = city_words * repeats + (type_words if has_type else ())
            if words == prefix + street_words:
                joined = True
    if not joined:
        return False
    remaining = re.findall(r"\d+", produced)
    for role in ("house", "flat"):
        required = expected_parts.get(role, "").strip()
        known = item.parts.get(role, "").strip()
        if required and not required.isdecimal():
            return False
        if known and not known.isdecimal():
            known = ""
        if required:
            if required not in remaining:
                return False
            remaining.remove(required)
        elif known and known in remaining:
            remaining.remove(known)
    return not remaining


def _value_ok(item: PiiItem, spec: FieldSpec | None, tool_name: str,
              path: str, produced: str) -> bool:
    """Separate full PHONE identity from notation, including dictated values.

    Historical value_matches is notation-sensitive for an unknown field, and
    role_matches reads digits but not spoken numbers. Neither is an independent
    identity metric on those PHONE paths. Reuse the observer's numeral parser
    and part comparator; leave partial/derived/free fields and other types on
    their historical predicate until their own track is accepted.

    THE ONE ADDITION (v14) IS A BOUNDED FALSE-NEGATIVE RESCUE:
    `value_matches` stays the first and only rule, and a role-less LOC leaf
    whose joined city+street blob it cannot split may still be asked whether
    every declared role of the expected address is rendered in the produced
    text (`_renders_address`)."""
    whole_phone = spec is None or (spec.kind == "identity" and spec.role in ("", "digits"))
    if item.type == "PHONE" and whole_phone:
        produced_digits: str = digits_of(produced) or spoken_digits_of(produced)
        expected: str = item.canonical or item.value
        expected_digits: str = digits_of(expected) or spoken_digits_of(expected)
        if len(produced_digits) not in (10, 11) or len(expected_digits) not in (10, 11):
            return False
        return part_matches("PHONE", produced_digits, expected_digits)
    if leaf_value_ok(item, tool_name, path, produced):
        return True
    if tool_name != "address_suggest" or path != "query":
        return False
    return _renders_address(item, spec, produced, item.canonical or item.value)


def _restoration(item: PiiItem, spec: FieldSpec | None, surfaces: Sequence[str],
                 written: str, restored: str, own: frozenset[str], case: CaseV5,
                 run: ArmRunV5, call_turn: int, call_seq: int,
                 tool_name: str, path: str, evidence: str) -> _Decision:
    """Score what the consumer RECEIVED, now that the identity is fixed.

    `residual` first — a fake still standing is the critical defect and no value
    comparison may buy it back. THE LEAK QUESTION IS ASKED OF THE LEAF, not of
    the chosen entity: v12 lets identity RESOLVE where v11 refused, and asking
    only the winner would let the resolution hide a standing fake of another
    item in the same restored text — the mirror of the refusal that v10 already
    forbade from buying a privacy improvement (`tool_chain-008 seq 7`,
    `tool_chain-030 seq 6`, `tool_chain-034 seq 10`). `_leaf_leak` is the ONE
    reader of that question and it scans every item with an available surface, so
    the flag cannot depend on which entity the identity branches picked. Then
    `_value_ok`: full PHONE uses an independent notation fold; other fields use
    the historical registry-aware predicate. A failed comparison is
    `value_wrong`, still subject to that predicate's limitations outside the
    accepted PHONE slice.

    FORM IS MEASURED INDEPENDENTLY OF THE VALUE. `own_pair` narrows each side to
    its own value and falls back to the leaf WHOLE when either side cannot be
    narrowed — narrowed on both sides or on neither, never one against the
    other. A wrong value can therefore carry a form pass (one person written in
    two grammatical forms, or another person's value in the same notation), which
    is exactly why the form column may not be read as a correctness column:
    `joint` is `value_ok and form_ok and not residual`, and all of them divide by
    the same candidate set."""
    expected = expected_leaf_value(item, spec) if spec is not None else (item.canonical or item.value)
    residual, leak_note = _leaf_leak(case, run, spec, restored, own, call_turn, call_seq)
    if residual:
        status = "residual"
    elif _value_ok(item, spec, tool_name, path, restored):
        status = "matched"
    else:
        status = "value_wrong"
    form_ok = False
    form_measured = False
    form_differs: tuple[str, ...] = ()
    if status != "residual" and item.type in contracts.FORM_FEATURES:
        produced, reference = own_pair(item.type, restored, (item.canonical, item.value),
                                       written, surfaces)
        if produced.strip() and reference.strip():
            verdict = form_match(item.type, produced, reference)
            form_ok = verdict.same
            form_measured = True
            form_differs = tuple(sorted(verdict.differs))
    return _Decision(status=status, item_id=item.id, identity=item.identity,
                     pii_type=item.type, expected=expected, candidate_ids=(item.id,),
                     evidence=evidence + leak_note, attributed=True, value_ok=status == "matched",
                     form_ok=form_ok, form_measured=form_measured, residual=residual,
                     form_differs=form_differs)


def _leaf_leak(case: CaseV5, run: ArmRunV5, spec: FieldSpec | None, restored: str,
               own: frozenset[str], call_turn: int, call_seq: int) -> tuple[bool, str]:
    """THE ORTHOGONAL LEAF SIGNAL: is a MINTED fake still standing in `restored`?

    Asked of the RESTORED text and the substitute surfaces the agent had ALREADY
    read, and of no chosen entity — which is the whole point of v10. `_decide`'s
    identity branches may refuse (`ambiguous`, `not_identifiable`, `unattributed`);
    the leak question is answerable regardless, and deleting it because the owner
    could not be named is how v9 bought a privacy improvement out of an identity
    refusal (review §3). The return names the items whose minted substitute stands
    for the EVIDENCE string only; the decision keeps `item_id=''`, so no person is
    charged on the strength of an ownerless leak."""
    ids: list[str] = []
    for item in case.base.pii:
        surfaces = _available_surfaces(run, item.id, call_turn, call_seq)
        if surfaces and _minted_substitute_stands(item, spec, surfaces, restored, own, case,
                                                  run, call_turn, call_seq):
            ids.append(item.id)
    if not ids:
        return False, ""
    return True, ("; a minted substitute of " + ", ".join(sorted(ids))
                  + " still stands in the restored text")


def _decide(case: CaseV5, run: ArmRunV5, call: ObservedCall, turn: int, path: str,
            written: str, restored: str, spec: FieldSpec | None,
            own: frozenset[str]) -> _Decision:
    """One actual leaf, decided. The order of the branches IS the contract."""
    substituted: list[PiiItem] = []
    unclocked: list[PiiItem] = []
    real: list[PiiItem] = []
    for item in case.base.pii:
        surfaces = _available_surfaces(run, item.id, turn, call.seq)
        if surfaces and _written_has_substitute(item, spec, surfaces, written, own, case, run,
                                                turn, call.seq):
            substituted.append(item)
        else:
            uncertain: tuple[str, ...] = tuple(
                mention.substitute for mention in run.mentions
                if mention.item_id == item.id and mention.substitute
                and 0 <= mention.result_seq < call.seq
                and not _mention_available(run, mention, turn, call.seq))
            if uncertain and _written_has_substitute(item, spec, uncertain, written, own, case,
                                                     run, turn, call.seq):
                unclocked.append(item)
        if _written_has_real(item, spec, case, run, written, turn, call.seq):
            real.append(item)
    if unclocked:
        leak, note = _leaf_leak(case, run, spec, restored, own, turn, call.seq)
        return _unresolved("not_identifiable", tuple(substituted + unclocked),
                           "prior disclosure to this model response is not established" + note,
                           residual=leak)
    if substituted:
        # ONE ENTITY'S SUBSTITUTE BESIDE ANOTHER ENTITY'S REAL VALUE IS `mixed`
        # EVEN WHEN THE REAL ONE IS THE LOWER ID. The free-text leaf that
        # carries a clean substitute AND an unrelated real value hides the
        # second, and M0 §6.3 forbids accepting the one while the other is
        # unmeasured — the lowest-id pick used to do exactly that, and it also
        # named the wrong entity when the written word was one entity's fake and
        # another's real value at once.
        chosen, candidates, evidence = _one_entity(substituted, spec)
        if chosen is None:
            leak, note = _leaf_leak(case, run, spec, restored, own, turn, call.seq)
            return _unresolved("ambiguous", candidates, evidence + note, residual=leak)
        hidden = tuple(item for item in real if _entity_of(item) != _entity_of(chosen))
        if hidden:
            return _mixed(chosen, candidates + hidden,
                          f"item {chosen.id}'s substitute stands beside the REAL value of "
                          f"{', '.join(sorted({_entity_of(one) for one in hidden}))}")
        surfaces = _available_surfaces(run, chosen.id, turn, call.seq)
        decision = _restoration(chosen, spec, surfaces, written, restored, own, case, run,
                                turn, call.seq, call.name, path,
                                f"the written leaf carries item {chosen.id}'s substitute ({evidence})")
        return replace(decision, candidate_ids=tuple(item.id for item in candidates))
    if real:
        chosen, candidates, evidence = _one_entity(real, spec)
        if chosen is None:
            leak, note = _leaf_leak(case, run, spec, restored, own, turn, call.seq)
            return _unresolved("ambiguous", candidates, evidence + note, residual=leak)
        expected = (expected_leaf_value(chosen, spec) if spec is not None
                    else (chosen.canonical or chosen.value))
        return _Decision(status="unmasked_known", item_id=chosen.id, identity=chosen.identity,
                         pii_type=chosen.type, expected=expected,
                         candidate_ids=tuple(sorted(one.id for one in real)),
                         evidence="the REAL value stood in the agent's leaf (" + evidence + ")",
                         attributed=True, value_ok=False, form_ok=False, form_measured=False,
                         residual=False, form_differs=())
    # THE ENGINE CHANGED A LEAF NO SUBSTITUTE OF OURS EXPLAINS: visible, with no
    # identity, rather than hidden as ordinary traffic or matched by guess.
    if written != restored:
        leak, note = _leaf_leak(case, run, spec, restored, own, turn, call.seq)
        return _unresolved("unattributed", (),
                           "written != restored and no available substitute explains the leaf"
                           + note, residual=leak)
    # AN UNCHANGED IDENTITY LEAF NO MENTION EXPLAINS is the same unresolved
    # crossing (a fake whose only mention is still in the future, a value we
    # cannot name) — not ordinary traffic. An enum, a quantity, a derived
    # rendering or a generic part falls through to `not_applicable`.
    if written.strip() and _identity_shaped(spec):
        leak, note = _leaf_leak(case, run, spec, restored, own, turn, call.seq)
        return _unresolved("unattributed", (),
                           "identity-typed leaf holds a value no available mention explains"
                           + note, residual=leak)
    return _unresolved("not_applicable", (), "no substitute, no known real value, unchanged")


@lru_cache(maxsize=4096)
def _own_stems_of_item(case_id: str, item_id: str, value: str, canonical: str,
                       parts: tuple[tuple[str, str], ...], pii_type: str) -> frozenset[str]:
    """`observe.own_stems` for ONE item — the `exempt` set of its own
    renderings, built by the same rule from the same helpers so the two sets
    cannot disagree about what a stem of this value is."""
    out: set[str] = set()
    for word in _WORD.findall(value) + _WORD.findall(canonical):
        if len(fold(word)) < MIN_PIECE:
            continue
        out.add(stem_of(word))
        if pii_type in DERIVED_TYPES:
            out.update(latin_prefixes(word, MIN_PIECE))
    for role, part in parts:
        if role == "gender" or not part:
            continue
        for word in _WORD.findall(part):
            if len(fold(word)) < MIN_PIECE:
                continue
            out.add(stem_of(word))
            if pii_type in DERIVED_TYPES:
                out.update(latin_prefixes(word, MIN_PIECE))
    return frozenset(out)


def own_stems_of(case: CaseV5, item: PiiItem) -> frozenset[str]:
    """The `exempt` set of ONE item's own real renderings, cached per case."""
    return _own_stems_of_item(case.base.id, item.id, item.value, item.canonical,
                              tuple(sorted(item.parts.items())), item.type)


# --- the leak side: which IDENTITY a written span is evidence for ------------------------
#
# WHY THE LEXEME ANALYSIS LIVES HERE AND NOT IN `observe`. The needle layer
# (`observe.item_survives_in` → `needles_of`) is the ONE answer to «does this
# value survive in this text» and it must keep answering it for `residual`, for
# `metrics` and for every historical line. What M02-F1 exposes is narrower: the
# NEEDLE SHAPES a value survives being rewritten in are not all identity
# evidence, and `stem` — four letters of one role, anchored at a word start —
# is the one that is not. «фёдорова» → «федо» fires inside «Фёдоровна», a
# patronymic of a DIFFERENT person; the initials needle of a two-part name
# fires on a third person's «В. И.». The minimal fix is therefore a different
# QUESTION asked of the same spans — «is this span evidence that THIS entity's
# real value is here» — and it is asked on the agent-written side only, where
# the contract says identity is chosen. `pymorphy3` is the evidence and not the
# defendant: the same allowance `form.py` and `contracts` §8.4 already state
# for the morphological dictionary, and no part of the engine is imported.
#
# THE SUBSTITUTE SIDE SAYS WHOSE THE WRITTEN TOKEN IS, and the whole repair
# hangs off one question: is this written word a fake that ANOTHER item already
# had in front of it? The witness says the word carries a real value; the
# substitute side says a fake explains it; only the SECOND reading names an
# identity the written side actually chose.

_ANALYZER = pymorphy3.MorphAnalyzer()
_NAME_TAGS: tuple[str, ...] = ("Surn", "Name", "Patr")
_CYRILLIC_WORD = re.compile(r"[А-Яа-яЁё]+")
_INITIAL_FRAGMENT = re.compile(r"(?:[А-ЯЁA-Z]\.)+|[А-Яа-яЁё]+")
# One written token: a squeezed initial («В. И.») or a word. The same two
# halves as `_INITIAL_FRAGMENT`, named apart so `_word_at` and
# `_token_fragments` cannot disagree about where a token begins.
_TOKEN = re.compile(r"(?:[А-ЯЁA-Z]\.)+|[А-Яа-яЁё]+")
# A number as a human writes one; the same class `observe._NUMBER_RUN` uses, so
# a `digits` span is read back as the run it landed in.
_NUMBER_RUN = re.compile(r"\+?\d[\d  ().\-–—]*\d|\d")


@lru_cache(maxsize=4096)
def _parses(word: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """One word's parses as (lemma, POS, name tags). Cached: pymorphy3 loads a
    dictionary from disk, and a leak pass asks about the same tokens many
    times over a corpus."""
    return tuple((parse.normal_form, str(parse.tag.POS),
                  tuple(tag for tag in _NAME_TAGS if tag in parse.tag))
                 for parse in _ANALYZER.parse(word) if parse.is_known)


@lru_cache(maxsize=4096)
def _lemmas(word: str) -> frozenset[tuple[str, str]]:
    """The lexemes a word is KNOWN to be, as (lemma, POS).

    The name-tagged parses are preferred, the way `form._word_readings`
    prefers them: a word the dictionary knows as a surname and as something
    else is, in this conversation, the name. An UNKNOWN word yields nothing —
    pymorphy3 answers about a string it does not know by GUESSING from its
    ending, and a prediction is not evidence."""
    parses = _parses(word)
    named = tuple(one for one in parses if one[2])
    return frozenset((lemma, part) for lemma, part, _tags in (named or parses))


def _same_lexeme(declared: str, token: str) -> bool:
    """Are the two spellings forms of ONE word, or two words sharing a stem.

    «Фёдорова» and «Фёдоровой» are one lexeme and either may stand for the
    other; «Фёдорова» and «Фёдоровна» share five letters and no lexeme, and a
    match on the shared stem named the wrong person. A written token with no
    Cyrillic letters is not judged this way — a transliterated rendering has no
    Russian lexeme and its own needle already states the prefix it accepts."""
    word = token.strip()
    if not _CYRILLIC_WORD.search(word) or not _CYRILLIC_WORD.search(declared.strip()):
        return True
    if _PATRONYMIC_TAIL.search(word) is None and _PATRONYMIC_TAIL.search(declared.strip()):
        # A patronymic is DERIVED from a given name and is not a form of it:
        # «ивановна» is not «иванова» written in another case.
        return False
    have, want = _lemmas(word), _lemmas(declared.strip())
    return bool(have) and bool(want) and not have.isdisjoint(want)


def _token_fragments(token: str) -> tuple[str, ...]:
    """The identity fragments of one written token, case- and ё-folded: its
    dotted initials and its words."""
    return tuple(fragment.lower().replace("ё", "е")
                 for fragment in _INITIAL_FRAGMENT.findall(token))


def _word_at(text: str, offset: int) -> str:
    """The written token the span begins in, or "".

    A needle may land INSIDE a word — that is what a four-letter stem does —
    and the WORD, not the needle, is what the agent wrote: «федо» standing at
    the start of «Фёдоровна» is one written token, and «which word did the
    agent write» has exactly one answer. An initial is a token too, because a
    name is squeezed to «В. И.» and the needles of the squeezed form are
    matched from the initial, not from the letter."""
    for match in _TOKEN.finditer(text):
        if match.start() <= offset < match.end():
            return match.group()
    return ""


def _is_initial(fragment: str) -> bool:
    return len(fragment) == 2 and fragment.endswith(".")


def _owned_by_substitute(case: CaseV5, run: ArmRunV5, token: str,
                         call_turn: int, call_seq: int,
                         exclude: str) -> tuple[str, ...]:
    """The items whose substitute renders this text — WITHOUT FUTURE EVIDENCE.

    Never `restored`, and never the real value's own vocabulary: the question is
    «whose FAKE is this», and the substitute side is the side the contract lets
    choose identity. A text that is one entity's fake and another's real value
    is the FAKE's evidence — a fake is a minted string nobody writes by accident
    and its entity already wrote it — so the other entity is not charged as its
    own leak, and the written side resolves the leaf instead. A text that no
    substitute renders belongs to nobody here and is left to the per-needle
    witness.

    EVERY RIVAL IS ASKED WITH THE CURRENT CALL'S TURN AND SEQ. The same two
    arguments `_decide` asks the item's own substitute with, so availability
    cannot mean one thing on one side of the leaf and another on the other:
    a rival's substitute disclosed at message 1 is in the agent's hands at a
    turn-3 call whether the question is asked about this item or about that one,
    and a mention at message 4 is not evidence for either. Asking at `(0, 0)`
    made a late-but-real disclosure invisible to the collision guard and charged
    the wrong person (M02-F1).

    `exclude` is the item the question is asked ABOUT: it is not a rival to
    itself."""
    if not token:
        return ()
    for other in case.base.pii:
        if other.id == exclude:
            continue
        if any(_surface_renders_token(surface, token)
               for surface in _available_surfaces(run, other.id, call_turn, call_seq)):
            return (other.id,)
    return ()


def _surface_renders_token(surface: str, token: str) -> bool:
    """Is a WHOLE substitute surface one written token?

    Per fragment, never per needle: the surface may be two words («Пахомова
    Ольга») and the token one, so the test is whether every fragment of the
    token is a form of one of the WORDS the surface is built from. The
    comparison is the loose one and it runs against charging a leak: it can
    only cost a missed charge, never buy a false `matched`."""
    fragments = _token_fragments(token)
    words = _token_fragments(surface)
    if not fragments or len(fragments) > len(words):
        return False
    return all(part_matches("NAME", surface, fragment)
               or any(_same_lexeme(word, fragment) for word in words)
               for fragment in fragments)


def _witness_for(item: PiiItem, needle: Needle, text: str, span: tuple[int, int]) -> str:
    """Is ONE needle occurrence evidence that THIS item's real value is here?

    `""` — the occurrence refutes its own needle: a `stem` that landed on a
    word of another lexeme, a `digits` needle inside a longer number run, an
    `initials` needle whose letters name other parts.
    `"real"` — the value itself: the whole surface, the whole role word, its
    initials, its digit signature, its date fold. A PROPERTY of the fragment
    alone is not enough — the substring that identifies a value is the value;
    the substring that merely shares letters with it is what named the wrong
    person in review §4."""
    if needle.kind in ("whole", "squeezed", "date"):
        return "real"
    if needle.kind == "digits":
        # ANY number run the needle stands inside — the same reading
        # `observe._needle_spans` matched on. The span covers the RUN, and the
        # needle is the last ten digits of it, so the two are equal only when
        # the run is already ten digits long.
        for run in _NUMBER_RUN.finditer(text):
            if run.start() <= span[0] and span[1] <= run.end():
                return "real" if needle.text in digits_of(run.group()) else ""
        return ""
    word = _word_at(text, span[0])
    if not word:
        return ""
    if needle.kind == "initials":
        lettered = tuple(fragment for fragment in _token_fragments(word)
                         if _is_initial(fragment))
        letters = "".join(fragment[0] for fragment in lettered)
        return "real" if letters and needle.text.startswith(letters) else ""
    if needle.kind == "stem":
        role = needle.role
        if role and _same_lexeme(item.parts.get(role, ""), word):
            # The whole role word is its own rendering; anything longer is a
            # fragment of it and no leak on its own.
            return "real" if fold(word).startswith(fold(item.parts.get(role, ""))) else ""
        if not role and _same_lexeme(item.value or item.canonical, word):
            return "real"
    return ""


def _written_has_real(item: PiiItem, spec: FieldSpec | None, case: CaseV5, run: ArmRunV5,
                      text: str, call_turn: int, call_seq: int) -> bool:
    """Does the AGENT-WRITTEN text carry this item's REAL value — a leak?

    The leak question is asked of the identity the written side already chose,
    and `restored` is never read here. A needle occurrence counts only when it
    is evidence that THIS entity's value stands in the text: the whole value,
    the whole role word, its initials, its digit signature, its date fold. A
    stem that landed on a word of another lexeme («федо» in the patronymic
    «Фёдоровна») refutes itself, and a whole rendering of another identity's
    substitute is that identity's evidence — so a correct restoration is not
    charged to the wrong person and a collision is not read as a leak.

    NO STEM-ONLY CHARGE. A four-letter fragment of a role word is not
    «the real value stood in the agent's leaf», and the two saved rows review §4
    found are exactly that charge being wrong. A real value written in the
    clear, declined or transliterated, still carries a `whole` needle or its
    initials and is charged as before.

    A part that identifies nobody is still not a leak: the role counts only
    when `contracts.IDENTIFYING_ROLES` names it, so a settlement, a house
    number, a street type or a mail domain kept real inside a minted address is
    not charged as a defect."""
    identifying = contracts.IDENTIFYING_ROLES.get(item.type, ())
    if spec is not None and spec.role and spec.role in identifying:
        real_part = item.parts.get(spec.role, "")
        if real_part and _renders_part(item.type, text, real_part):
            return True
    for surface in (item.value, item.canonical):
        if not surface:
            continue
        for needle in item_needles(item, surface):
            if not needle.role:
                continue
            for span in _needle_spans(needle, text):
                if _witness_for(item, needle, text, span) != "real":
                    continue
                token = _word_at(text, span[0])
                if _fragment_owned_by_another(item, needle, case, run, token,
                                              call_turn, call_seq):
                    # A FRAGMENT OF THIS VALUE that is a WHOLE rendering of
                    # somebody else's. «федо» inside the patronymic «Фёдоровна»
                    # is review §4's row; the charge would name the wrong
                    # entity, so it is dropped rather than moved — the written
                    # side decides the identity, and it already has.
                    continue
                return True
    return False


def _fragment_owned_by_another(item: PiiItem, needle: Needle, case: CaseV5,
                               run: ArmRunV5, token: str, call_turn: int,
                               call_seq: int) -> bool:
    """Is this witness only a FRAGMENT — and another item's whole rendering?

    A WHOLE value, rendered whole, is this item's leak whatever anybody else's
    values also spell: «Иванов» written in the clear is the customer's surname
    even when another record's stem is a prefix of it. What review §4 found is
    narrower, and the guard is narrow to match: `needle` landed on a word that
    is not this role's word, and that word IS a word of another item's real
    value or of another item's substitute — the substitute of a rival ASKED AT
    THIS CALL (`call_turn`/`call_seq`), so a fake disclosed later cannot take a
    charge off the entity that really wrote its real value. Both readings are of
    the same token, and the fragment is the one that loses."""
    whole = fold(needle.text) == fold(token)
    if whole:
        return False
    if _owned_by_substitute(case, run, token, call_turn, call_seq, exclude=item.id):
        return True
    return any(other.id != item.id and _owns_real_token(other, token)
               for other in case.base.pii)


def _owns_real_token(item: PiiItem, token: str) -> bool:
    """Does ONE item's own real value render this token as a word?

    The same `whole`/`stem` vocabulary the witness uses, asked in the other
    direction, and only for a token that is one word."""
    if not token:
        return False
    for surface in (item.value, item.canonical):
        if not surface:
            continue
        for needle in item_needles(item, surface):
            if needle.kind == "whole" and fold(token) == fold(needle.text):
                return True
            if needle.kind == "stem" and _same_lexeme(
                    item.parts.get(needle.role, "") if needle.role else surface, token):
                return True
            if needle.kind == "initials" and all(
                    len(fragment) == 2 and fragment.endswith(".")
                    for fragment in _token_fragments(token)):
                letters = "".join(fragment[0] for fragment in _token_fragments(token))
                if needle.text.startswith(letters) or letters.startswith(needle.text):
                    return True
    return False


def _event_id(call_seq: int, path: str, item_id: str) -> str:
    """`seq|field|item` — the call's own sequence number, the dotted leaf and the
    attributed item. NO TURN: the same action one turn later is the same event,
    which is what makes a clarification and a reordering measurable as nothing."""
    return f"{call_seq}|{path}|{item_id}"


def actual_events(case: CaseV5, run: ArmRunV5) -> ActualRunObservation:
    """THE front end: every written and restored leaf of every ACTUAL call.

    `case.hops` is not read. A call the corpus did not declare is measured all
    the same; a declared call the agent never made produces no event — the
    historical `absent` belongs to the timetable, not to the run."""
    if len(run.call_turns) != len(run.base.calls):
        raise ActualHopsError(
            f"{case.base.id}|{run.base.repeat}: {len(run.call_turns)} call turns for "
            f"{len(run.base.calls)} calls; the two lists are written together")
    own = own_stems(case)
    events: list[ActualEvent] = []
    for index, call in enumerate(run.base.calls):
        turn = run.call_turns[index]
        written_flat = flatten(call.written)
        restored_flat = flatten(call.restored)
        for path in sorted(set(written_flat) | set(restored_flat)):
            written = _leaf_str(written_flat.get(path, ""))
            restored = _leaf_str(restored_flat.get(path, ""))
            spec = spec_v5_for(call.name, path) if call.name in REGISTRY_V5 else None
            decision = _decide(case, run, call, turn, path, written, restored, spec, own)
            events.append(ActualEvent(
                event_id=_event_id(call.seq, path, decision.item_id),
                case_id=case.base.id, repeat=run.base.repeat, call_seq=call.seq,
                call_turn=turn, tool_name=call.name,
                owner=contracts.hop_owner_of_leaf(call.name, path), path=path,
                item_id=decision.item_id, identity=decision.identity,
                pii_type=decision.pii_type, status=decision.status, written=written,
                restored=restored, expected=decision.expected,
                candidate_ids=decision.candidate_ids, evidence=decision.evidence,
                attributed=decision.attributed, value_ok=decision.value_ok,
                form_ok=decision.form_ok, form_measured=decision.form_measured,
                residual=decision.residual, form_differs=decision.form_differs))
    return ActualRunObservation(case_id=case.base.id, repeat=run.base.repeat, events=tuple(events))


# --- the versioned table -----------------------------------------------------------------

def _type_aggregate(pii_type: str, events: Sequence[ActualEvent]) -> TypeAggregate:
    return TypeAggregate(
        pii_type=pii_type,
        candidates=len(events),
        attributed=sum(1 for event in events if event.attributed),
        value_ok=sum(1 for event in events if event.value_ok),
        form_ok=sum(1 for event in events if event.form_ok),
        form_unmeasured=sum(1 for event in events if not event.form_measured),
        residual=sum(1 for event in events if event.residual),
        joint_ok=sum(1 for event in events
                      if event.value_ok and event.form_ok and not event.residual),
        statuses=tuple((status, sum(1 for event in events if event.status == status))
                       for status in CANDIDATE_STATUSES))


def aggregate(observations: Sequence[ActualRunObservation]) -> ActualAggregate:
    """The versioned table over a set of runs, per PII type. ONE denominator
    (`candidates`) for attributed, value, form, residual and joint, and
    `not_applicable` outside every one of them."""
    events = tuple(event for observation in observations for event in observation.events)
    candidates = tuple(event for event in events if event.status in CANDIDATE_STATUSES)
    grouped: dict[str, list[ActualEvent]] = {}
    for event in candidates:
        grouped.setdefault(event.pii_type, []).append(event)
    by_type = tuple(_type_aggregate(name, tuple(grouped[name])) for name in sorted(grouped))
    return ActualAggregate(
        estimator=ESTIMATOR_VERSION, runs=len(observations), events_total=len(events),
        not_applicable=sum(1 for event in events if event.status == "not_applicable"),
        overall=_type_aggregate("all", candidates), by_type=by_type)


def render(report: ActualAggregate) -> tuple[str, ...]:
    """The table as text: version first, the overall line, then each PII type,
    then the status breakdown. A reader who quotes a number from here quotes the
    denominator beside it."""
    header = ("type\tcandidates\tattributed\tvalue\tform\tform_unmeasured\tresidual\tjoint\t"
              + "\t".join(status for status in CANDIDATE_STATUSES))
    lines = [f"M0 actual OUT crossings — estimator {report.estimator}",
             f"runs {report.runs} · events {report.events_total} · "
             f"not_applicable {report.not_applicable} (in no denominator)",
             "lower bound over actual crossings: attributed/value/form/residual/joint all "
             "divide by `candidates`; FORM IS INDEPENDENT OF THE VALUE — a form pass on its "
             "own is not a correctness pass, and joint = value AND form AND not residual; "
             "unresolved events stay in the denominator as mixed/ambiguous/unattributed, "
             "and since v10 an unresolved row may carry residual=True with item_id='' when "
             "a MINTED substitute still stands in the restored text (an ordinary generic "
             "token does not count)",
             header]
    for one in (report.overall,) + report.by_type:
        counts = "\t".join(str(one.count(status)) for status in CANDIDATE_STATUSES)
        label = one.pii_type if one.pii_type else "(untyped)"
        lines.append(f"{label}\t{one.candidates}\t{one.attributed}\t{one.value_ok}\t"
                     f"{one.form_ok}\t{one.form_unmeasured}\t{one.residual}\t{one.joint_ok}\t"
                     f"{counts}")
    return tuple(lines)
