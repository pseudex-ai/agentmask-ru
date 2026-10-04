"""M03 — CAUSAL hops: WHERE an emission came from, proved by the recorded chronology.

ADDITIVE. `observe.observe`, `metrics.py` and `actual_hops.py` keep their
semantics, denominators and numbers. Nothing here replaces them; the historical
scheduled lines stay separately labelled (see `hop_report.py`).

WHY THIS EXISTS. `actual_hops` (M0) answers «whose datum is in this leaf and did
the right value come back». It deliberately does NOT answer the causal question
the product needs for its chain promise: WHICH earlier artefact the agent was
carrying when it wrote an answer, a summary, a template line or a later call.
The historical `chain_*` lines answer it from `case.hops` — the TIMETABLE the
corpus wrote — and the M01/M02 rulings rejected the timetable as evidence. This
estimator reads only what the run recorded:

  * `run.model_trace` — the PROVIDER chronology: one `ModelResponse` per
    completed response, carrying the request ordinal, the turn, the count of
    tool results ALREADY available to it, and `call_requests` mapping each
    accepted call to the response that emitted it;
  * `run.tool_results` — the RESULT sequence (`seq`, `turn`, `spans_real`), i.e.
    which typed item each result carried;
  * `run.mentions` — what the model READ and where from (`msg >= 0`: a user
    message; `result_seq >= 0`: a named tool result);
  * typed item/version evidence (`PiiItem.type`, `PiiItem.identity`,
    `PiiItem.where`) — never free text as an identity.

FOUR DENOMINATORS, NEVER ONE. Each is reported on its own line with its own
status counts:

  1. `answer` — GENERAL answer mentions: every typed item whose substitute stood
     in the reply the agent wrote, whether or not its origin can be named.
  2. `tool_arg` / `summary` / `template` — the OUT owners of an actual call
     leaf: a plain argument, a retelling for another worker, a slot of a message
     a person reads. `hop_owner_of_leaf` decides, never the case.
  3. `chain` — actual EDGES «result A → later call B»: for one item, one earlier
     result the agent had provably received before the call that re-emitted it.
  4. the causal sub-denominator of 1–3: emissions whose origin is a TOOL RESULT.
     `attributed` counts only the ones bound to exactly ONE result.

THE ORDER OF THE BRANCHES IS THE CONTRACT.

  1. A CARRIER IS AVAILABLE ONLY IF THE RECORD PROVES IT. `result_available`
     returns True (the response that emitted the consuming act had already
     received this result), False (a later result, or a result produced by the
     SAME response — two calls of one response execute sequentially and the
     second's result was NOT visible to the response that asked for both), or
     None (the record cannot prove it: an archived trace with no response
     boundary, or two artefacts of one turn). None is `not_identifiable`, NEVER
     `attributed` and never `absent`.
  2. ONE CARRIER, PROVED, AND NO USER COPY IS `attributed`. A second carrier,
     or the user having supplied the datum in the dialogue as well, is
     `ambiguous` — the record names several sufficient causes and picking one
     would be the optimism this estimator exists to refuse.
  3. AN UNKNOWN CARRIER OUTRANKS A KNOWN ONE, AND THIS IS DECIDED FIRST: while
     ANY carrier's availability is unprovable the emission is
     `not_identifiable`, because uniqueness is not established. One proved
     carrier beside one unprovable same-turn carrier is therefore NOT
     `attributed` — a proved cause is not a unique cause — and it is not
     `user_provided` either, because an unprovable result may be the source the
     user's copy is not. A `False` carrier is evidence AGAINST, not for.
  4. USER-PROVIDED DATA IS ITS OWN STATUS. An emission whose datum the customer
     gave in a message is `user_provided` when no result can explain it — a
     tool that ran beside it explains nothing. The causal denominator excludes
     it; the general mention denominator keeps it.
  5. NO CARRIER AT ALL IS `unattributed` — visible, never a quiet pass.
     The executable order in `_bind` is therefore: unknown → ambiguous (several
     proved carriers, or one proved carrier beside a user copy) → attributed →
     user_provided → unattributed. Rule 3 before rule 2 is what «outranks»
     means, and it is the branch order M03-F1 found the code not keeping.

NO SCHEDULED TURN MATCHING. `case.hops` is never read for a verdict. A call the
corpus did not declare is measured all the same; a declared call the agent never
made produces no event (an action never taken is not a crossing).

VALUE, FORM, RESIDUAL, JOINT are reported WHERE MEASURABLE and divide by
`attributed` ONLY — the emissions bound to exactly ONE proved result, never the
whole candidate set — so a form pass can never be read as a correctness pass.
`joint = value_ok and form_ok and not residual`; `form_unmeasured` counts the
attributed emissions no comparator could read.

`python3 -m bench.agentpii5.test_causal_hops` runs the pinned checks, including
the two mutation guards: deleting the chronology from the availability rule, and
turning `not_identifiable` into a pass, each turn a named check red, plus the
M03-F1 check that an unprovable carrier defeats a proved one.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from bench.agentpii4.tools import flatten
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import ArmRunV5, CaseV5, ModelTrace, ToolResultRecord
from bench.agentpii5.form import form_match
from bench.agentpii5.metrics import leaf_value_ok
from bench.agentpii5.observe import (
    answer_pair,
    answer_span_of,
    answer_spans,
    item_survives_in,
    own_pair,
    residual_answer_items,
    substitute_surfaces,
)

# M01/M02 ruling: an estimator that moves a denominator under the same name lets
# a counting fix be read as an engine improvement. Bump this when a denominator,
# a status or the availability rule moves.
#
# v2 (M03-F1): an UNKNOWN carrier now outranks a proved one, so a single proved
# carrier beside an unprovable same-turn carrier is `not_identifiable` instead of
# `attributed`. That moves archived denominators: `attributed` falls, the
# `not_identifiable` and (for a user copy beside an unprovable carrier)
# `tool_causal` columns rise, and the `attributed`-only value/form/residual/joint
# denominators shrink with them. v1 is kept for history and is not comparable.
ESTIMATOR_VERSION: str = "m03-causal-hops-v2"

# One line per denominator. `answer` is the general mention line; the three
# acting owners are the OUT owners of a leaf the agent wrote; `chain` is the
# result-A -> later-call-B edge line.
CAUSAL_SURFACES: tuple[str, ...] = ("answer", "tool_arg", "summary", "template", "chain")

CAUSAL_STATUSES: tuple[str, ...] = (
    "attributed", "ambiguous", "unattributed", "not_identifiable",
    "user_provided", "not_applicable")
# Emission statuses that divide the causal denominator: every emission whose
# origin is asked to be a TOOL RESULT. `user_provided` is proved NOT to need a
# result; `not_applicable` is no emission at all.
TOOL_CAUSAL_STATUSES: tuple[str, ...] = (
    "attributed", "ambiguous", "unattributed", "not_identifiable")


class CausalHopsError(ValueError):
    """A run whose chronology contradicts its own call record. Raised, never
    swallowed: a silently dropped or re-ordered response would re-attribute
    every edge at once."""


@dataclass(frozen=True)
class Consumer:
    """The act an emission was written by. `kind == "call"` names the actual
    call (`seq`, `turn`); `kind == "answer"` is the final reply, whose response
    is located from the trace per item."""

    kind: str
    seq: int = -1
    turn: int = -1


def call_consumer(seq: int, turn: int) -> Consumer:
    return Consumer(kind="call", seq=seq, turn=turn)


ANSWER: Consumer = Consumer(kind="answer")


# --- THE availability rule ---------------------------------------------------------------

def _call_index(run: ArmRunV5, seq: int) -> int | None:
    return next((index for index, call in enumerate(run.base.calls) if call.seq == seq), None)


def _result_record(run: ArmRunV5, result_seq: int) -> ToolResultRecord | None:
    return next((one for one in run.tool_results if one.seq == result_seq), None)


def _require_mapping(run: ArmRunV5, trace: ModelTrace) -> None:
    if len(trace.call_requests) != len(run.base.calls):
        raise CausalHopsError(
            f"model trace maps {len(trace.call_requests)} calls for "
            f"{len(run.base.calls)} recorded calls; the map is written with the calls")


def _response_for(trace: ModelTrace, request: int) -> Any:
    response = next((row for row in trace.responses if row.request == request), None)
    if response is None:
        raise CausalHopsError(f"call map names response {request}, which the trace does not hold")
    return response


def _answer_response(run: ArmRunV5, item_id: str) -> Any | None:
    """The provider response that wrote THIS item into the final reply.

    Matched by the substitute the model wrote (`response.raw`), because the last
    response of a run that died mid-loop is not the answer. The LAST-RESORT
    fallback below (no response carries a known surface and none equals the
    reply) picks the LAST response, and it is NOT conservative: for a
    single-carrier item the largest `available_results` window turns
    `not_identifiable` into `attributed`, and for a multi-carrier item it turns
    `attributed` into `ambiguous`. It is a best-effort reading of a record that
    cannot be read, and it is untested on real data (M03-F3).
    """
    trace = run.model_trace
    if trace is None:
        return None
    surfaces = substitute_surfaces(run, item_id)
    for response in reversed(trace.responses):
        if any(surface and surface in response.raw for surface in surfaces):
            return response
    for response in reversed(trace.responses):
        if response.raw.strip() and response.raw.strip() == run.reply_raw.strip():
            return response
    return trace.responses[-1]


def result_available(run: ArmRunV5, result_seq: int, consumer: Consumer,
                     item_id: str = "") -> bool | None:
    """Was the result `result_seq` provably in the model's hands when it wrote
    the consumer?

    True / False are PROOFS; None is «this record cannot prove it». The one rule
    that decides a causal verdict is the `available_results` boundary of the
    response that EMITTED the consuming act: `available_results` counts the
    accepted calls whose results existed BEFORE that response's own function
    calls, so a result produced by the same response is not available to it and
    a result produced later never is.
    """
    result_index: int | None = _call_index(run, result_seq)
    if result_index is None:
        raise CausalHopsError(f"result seq {result_seq} names no recorded call")
    trace: ModelTrace | None = run.model_trace
    if consumer.kind == "answer":
        response = _answer_response(run, item_id)
        if response is None:
            # ARCHIVED TRACE: no boundary was recorded. A user message is still
            # provably earlier, but a tool result of the same turn is not, so
            # the answer leg is unprovable rather than guessed.
            return None
        _require_mapping(run, trace)
        return result_index < response.available_results
    call_index: int | None = _call_index(run, consumer.seq)
    if call_index is None:
        raise CausalHopsError(f"call seq {consumer.seq} names no recorded call")
    if result_index >= call_index:
        # A result the call did not precede cannot be its input. This branch
        # needs no trace: the call ORDER is recorded in the run itself.
        return False
    if trace is not None:
        _require_mapping(run, trace)
        request: int = trace.call_requests[call_index]
        response = _response_for(trace, request)
        return (trace.call_requests[result_index] < request
                and result_index < response.available_results)
    record: ToolResultRecord | None = _result_record(run, result_seq)
    if record is None:
        raise CausalHopsError(f"result seq {result_seq} names no recorded tool result")
    if record.turn < consumer.turn:
        return True
    if record.turn > consumer.turn:
        return False
    # SAME TURN, NO RECORDED BOUNDARY: the exact case that makes an archived
    # run's chain `not_identifiable`. Two calls of one turn can belong to one
    # response, so execution order is not evidence of knowledge.
    return None


# --- reading one emission ----------------------------------------------------------------

def _user_provided(case: CaseV5, run: ArmRunV5, item_id: str) -> bool:
    """Typed evidence that the CUSTOMER supplied the datum: the item was seeded
    in a message, or the model read its substitute in one. Both are recorded
    facts; a guess from the surface text is not."""
    item = next((one for one in case.base.pii if one.id == item_id), None)
    if item is not None and item.where.kind == "message":
        return True
    return any(mention.item_id == item_id and mention.msg >= 0 for mention in run.mentions)


def _carriers(run: ArmRunV5, item_id: str) -> tuple[int, ...]:
    """Every recorded tool result that CARRIED the item, in result order. Read
    from the mock's typed `spans_real` tags first — the versioned slot evidence —
    and from a mention that names the result second; free text is never an
    identity."""
    carried: list[int] = []
    for result in run.tool_results:
        tagged: bool = (item_id in result.spans_real
                        or contracts.ECHO_TAG_PREFIX + item_id in result.spans_real)
        mentioned: bool = any(mention.item_id == item_id and mention.result_seq == result.seq
                              for mention in run.mentions)
        if tagged or mentioned:
            carried.append(result.seq)
    return tuple(sorted(carried))


@dataclass(frozen=True)
class _Binding:
    """What the chronology proved about ONE emission's origin."""

    status: str
    source_seq: int
    source_kind: str
    candidate_seqs: tuple[int, ...]
    evidence: str


def _bind(case: CaseV5, run: ArmRunV5, item_id: str, consumer: Consumer,
          answer_item: str = "") -> _Binding:
    """THE causal decision, one emission. The branch order is the contract:
    unknown → ambiguous → attributed → user_provided → unattributed. Rule 3 of
    the module contract is read FIRST, so an unprovable carrier defeats
    uniqueness however many carriers are proved available (M03-F1)."""
    carriers: tuple[int, ...] = _carriers(run, item_id)
    user: bool = _user_provided(case, run, item_id)
    available: list[int] = []
    unknown: list[int] = []
    unavailable: list[int] = []
    for seq in carriers:
        proved: bool | None = result_available(run, seq, consumer,
                                               answer_item or item_id)
        if proved is True:
            available.append(seq)
        elif proved is None:
            unknown.append(seq)
        else:
            unavailable.append(seq)
    where: str = "the answer" if consumer.kind == "answer" else f"call {consumer.seq}"
    # RULE 3 FIRST, AND THE ORDER IS THE CONTRACT (M03-F1). While ANY carrier's
    # availability is unprovable, uniqueness is not established, so a proved
    # carrier beside an unprovable one is `not_identifiable` — neither
    # `attributed` (a proved cause is not a unique one) nor `user_provided` (an
    # unprovable result may be the source the user's copy is not). The evidence
    # names the unprovable carrier AND the proved one: the v1 line claimed «no
    # other carrier is available» while one stood right there, unprovable.
    if unknown:
        proved_note: str = (
            f"; result seq {', '.join(str(one) for one in available)} is proved available, "
            f"but a proved cause is not a unique one" if available else "")
        return _Binding("not_identifiable", -1, "", tuple(sorted(available + unknown)),
                        f"result seq {', '.join(str(one) for one in unknown)} carried item "
                        f"{item_id} but {where} has no recorded response boundary{proved_note}; "
                        f"uniqueness is not established")
    if len(available) > 1:
        return _Binding("ambiguous", -1, "", tuple(available),
                        f"{len(available)} results carrying item {item_id} were available to "
                        f"{where} (seq {', '.join(str(one) for one in available)}); "
                        f"the record names several sufficient causes")
    if available and user:
        return _Binding("ambiguous", -1, "", tuple(available),
                        f"item {item_id} is user-provided AND result seq {available[0]} "
                        f"carried it before {where}; the record cannot choose")
    if available:
        seq = available[0]
        # FIRST vs LATER is the RUN's result order, not the item's carrier list:
        # the contract's question is «did this come from the first tool result or
        # a later one», and one item carried by one late result is not a «first».
        first: int = min((one.seq for one in run.tool_results), default=seq)
        kind: str = "first_result" if seq == first else "later_result"
        return _Binding("attributed", seq, kind, tuple(available),
                        f"result seq {seq} ({kind}) carried item {item_id} and was available to "
                        f"{where}; it is the only carrier that could have supplied it (no "
                        f"unprovable carrier, and the datum is not user-provided)")
    if user:
        return _Binding("user_provided", -1, "user", (), 
                        f"item {item_id} came from a user message; no available result "
                        f"carried it, and an unrelated tool explains nothing")
    if unavailable:
        return _Binding("unattributed", -1, "", (),
                        f"item {item_id} was emitted into {where} but every carrier "
                        f"(seq {', '.join(str(one) for one in unavailable)}) came later; "
                        f"no available source explains it")
    return _Binding("unattributed", -1, "", (), 
                    f"item {item_id} was emitted into {where} and no recorded result ever "
                    f"carried it")


# --- value / form / residual -------------------------------------------------------------

def _leaf_measure(item: Any, run: ArmRunV5, name: str, path: str,
                  written: str, restored: str) -> tuple[bool, bool, bool, bool]:
    """(value_ok, form_ok, form_measured, residual) for ONE leaf. Residual is
    first: a substitute still standing in what the consumer received settles the
    verdict and no value comparison may buy it back."""
    surfaces: tuple[str, ...] = substitute_surfaces(run, item.id)
    residual: bool = any(surface and surface in restored for surface in surfaces)
    value_ok: bool = False if residual else leaf_value_ok(item, name, path, restored)
    form_ok = False
    form_measured = False
    if not residual and item.type in contracts.FORM_FEATURES:
        produced, reference = own_pair(item.type, restored, (item.canonical, item.value),
                                       written, surfaces)
        if produced.strip() and reference.strip():
            form_ok = form_match(item.type, produced, reference).same
            form_measured = True
    return value_ok, form_ok, form_measured, residual


def _answer_measure(case: CaseV5, run: ArmRunV5, item: Any, span: Any,
                    residual_items: frozenset[str]) -> tuple[bool, bool, bool, bool]:
    restored, raw = answer_pair(run, item, span)
    residual: bool = item.id in residual_items
    value_ok: bool = False if residual else item_survives_in(item, item.canonical or item.value,
                                                             run.base.reply)
    form_ok = False
    form_measured = False
    if not residual and item.type in contracts.FORM_FEATURES:
        produced, reference = own_pair(item.type, restored, (item.canonical, item.value),
                                       raw, substitute_surfaces(run, item.id))
        if produced.strip() and reference.strip():
            form_ok = form_match(item.type, produced, reference).same
            form_measured = True
    return value_ok, form_ok, form_measured, residual


# --- the estimator -----------------------------------------------------------------------

@dataclass(frozen=True)
class CausalEvent:
    """ONE emission (or ONE chain edge) and the verdict on its origin.

    `event_id` carries no turn: the same action one turn later is the same
    emission. `candidate_seqs` names every recorded carrier the binding looked
    at, so a reader can audit an `ambiguous`/`not_identifiable` verdict without
    re-running the estimator.
    """

    event_id: str
    case_id: str
    repeat: int
    surface: str                    # CAUSAL_SURFACES
    owner: str                      # contracts.OUT_OWNERS for an acting leaf
    tool_name: str
    call_seq: int                   # -1 for the answer
    item_id: str
    identity: str
    pii_type: str
    status: str                     # CAUSAL_STATUSES
    source_seq: int                 # the ONE attributed result, else -1
    source_kind: str                # "", "user", "first_result", "later_result"
    candidate_seqs: tuple[int, ...]
    evidence: str
    attributed: bool
    value_ok: bool
    form_ok: bool
    form_measured: bool
    residual: bool


@dataclass(frozen=True)
class CausalRunObservation:
    """Every causal emission of one (case, repeat) of the gateway arm."""

    case_id: str
    repeat: int
    events: tuple[CausalEvent, ...]


def _event(case: CaseV5, run: ArmRunV5, surface: str, owner: str, tool_name: str,
           call_seq: int, item: Any, binding: _Binding,
           measures: tuple[bool, bool, bool, bool]) -> CausalEvent:
    value_ok, form_ok, form_measured, residual = measures
    return CausalEvent(
        event_id=f"{surface}|{call_seq}|{item.id}",
        case_id=case.base.id, repeat=run.base.repeat, surface=surface, owner=owner,
        tool_name=tool_name, call_seq=call_seq, item_id=item.id, identity=item.identity,
        pii_type=item.type, status=binding.status, source_seq=binding.source_seq,
        source_kind=binding.source_kind, candidate_seqs=binding.candidate_seqs,
        evidence=binding.evidence, attributed=binding.status == "attributed",
        value_ok=value_ok, form_ok=form_ok, form_measured=form_measured,
        residual=residual)


def _emitted_items(case: CaseV5, run: ArmRunV5, written: str) -> tuple[Any, ...]:
    """The items whose substitute the agent WROTE into this leaf. Strict: the
    whole surface a mention recorded must stand in the leaf. A partial-role leaf
    that carries a piece of a value is M0's question and is not claimed here,
    because a piece is not an identity."""
    out: list[Any] = []
    for item in case.base.pii:
        surfaces = tuple(mention.substitute for mention in run.mentions
                         if mention.item_id == item.id and mention.substitute)
        if surfaces and any(surface in written for surface in surfaces):
            out.append(item)
    return tuple(out)


def _answer_events(case: CaseV5, run: ArmRunV5) -> list[CausalEvent]:
    spans = answer_spans(case, run)
    if not spans:
        return []
    residual_items: frozenset[str] = residual_answer_items(case, run)
    events: list[CausalEvent] = []
    for item in case.base.pii:
        span = answer_span_of(run, item, spans)
        if span is None:
            continue
        binding = _bind(case, run, item.id, ANSWER, answer_item=item.id)
        events.append(_event(case, run, "answer", "answer", "", -1, item, binding,
                             _answer_measure(case, run, item, span, residual_items)))
    return events


def _acting_events(case: CaseV5, run: ArmRunV5) -> list[CausalEvent]:
    """The `tool_arg`/`summary`/`template` emissions and the result-A -> call-B
    chain edges, in one walk of the ACTUAL calls. One event per (leaf, item);
    the chain edge is the SAME emission with the binding read against its
    carriers, so the two lines cannot disagree about what was written."""
    events: list[CausalEvent] = []
    for index, call in enumerate(run.base.calls):
        turn: int = run.call_turns[index]
        consumer: Consumer = call_consumer(call.seq, turn)
        written_flat = flatten(call.written)
        restored_flat = flatten(call.restored)
        for path in sorted(set(written_flat) | set(restored_flat)):
            written = "" if written_flat.get(path) is None else str(written_flat.get(path))
            restored = "" if restored_flat.get(path) is None else str(restored_flat.get(path))
            if not written:
                continue
            owner: str = contracts.hop_owner_of_leaf(call.name, path)
            if owner not in contracts.ACTING_OUT_OWNERS:
                continue
            for item in _emitted_items(case, run, written):
                binding = _bind(case, run, item.id, consumer)
                measures = _leaf_measure(item, run, call.name, path, written, restored)
                events.append(_event(case, run, owner, owner, call.name, call.seq,
                                     item, binding, measures))
                events.append(_event(case, run, "chain", owner, call.name, call.seq,
                                     item, binding, measures))
    return events


def causal_events(case: CaseV5, run: ArmRunV5) -> CausalRunObservation:
    """THE front end. `case.hops` is not read: a crossing the corpus did not
    schedule is measured all the same, and a scheduled one the agent never made
    produces no event."""
    if len(run.call_turns) != len(run.base.calls):
        raise CausalHopsError(
            f"{case.base.id}|{run.base.repeat}: {len(run.call_turns)} call turns for "
            f"{len(run.base.calls)} calls; the two lists are written together")
    events = _answer_events(case, run) + _acting_events(case, run)
    return CausalRunObservation(case_id=case.base.id, repeat=run.base.repeat,
                                events=tuple(events))


# --- the versioned table -----------------------------------------------------------------

@dataclass(frozen=True)
class CausalLine:
    """One line of the versioned table. `candidates` is the ONE denominator of
    every STATUS count; `value_ok`/`form_ok`/`form_unmeasured`/`residual`/
    `joint_ok` divide by `attributed` ONLY (the emissions bound to exactly ONE
    proved result), so a form pass can never be read as a correctness pass.
    `tool_causal` is the sub-denominator the causal question is asked over."""

    key: str
    candidates: int
    tool_causal: int
    attributed: int
    first_result: int
    later_result: int
    ambiguous: int
    unattributed: int
    not_identifiable: int
    user_provided: int
    not_applicable: int
    value_ok: int
    form_ok: int
    form_unmeasured: int
    residual: int
    joint_ok: int
    statuses: tuple[tuple[str, int], ...]

    def count(self, status: str) -> int:
        return next((count for name, count in self.statuses if name == status), 0)


@dataclass(frozen=True)
class CausalAggregate:
    """The overall line, one line per surface and one per leaf owner."""

    estimator: str
    runs: int
    events_total: int
    overall: CausalLine
    by_surface: tuple[CausalLine, ...]
    by_owner: tuple[CausalLine, ...]


def _line(key: str, events: Sequence[CausalEvent]) -> CausalLine:
    samples = tuple(events)
    attributed = tuple(one for one in samples if one.status == "attributed")
    statuses: dict[str, int] = {name: 0 for name in CAUSAL_STATUSES}
    for one in samples:
        statuses[one.status] = statuses.get(one.status, 0) + 1
    tool_causal = sum(statuses[name] for name in TOOL_CAUSAL_STATUSES)
    first = sum(1 for one in attributed if one.source_kind == "first_result")
    return CausalLine(
        key=key, candidates=len(samples), tool_causal=tool_causal,
        attributed=len(attributed), first_result=first,
        later_result=len(attributed) - first,
        ambiguous=statuses["ambiguous"], unattributed=statuses["unattributed"],
        not_identifiable=statuses["not_identifiable"],
        user_provided=statuses["user_provided"],
        not_applicable=statuses["not_applicable"],
        value_ok=sum(1 for one in attributed if one.value_ok),
        form_ok=sum(1 for one in attributed if one.form_ok),
        form_unmeasured=sum(1 for one in attributed if not one.form_measured),
        residual=sum(1 for one in attributed if one.residual),
        joint_ok=sum(1 for one in attributed
                     if one.value_ok and one.form_ok and not one.residual),
        statuses=tuple((name, statuses[name]) for name in CAUSAL_STATUSES))


def aggregate(observations: Sequence[CausalRunObservation]) -> CausalAggregate:
    """The overall line, one line per surface, one line per owner. A surface
    with no event is ABSENT from the table rather than printed as 0/0 — an
    empty line reads as a measured zero."""
    samples = tuple(observation for observation in observations)
    events = tuple(one for observation in samples for one in observation.events)
    by_surface = tuple(_line(surface, tuple(one for one in events if one.surface == surface))
                       for surface in CAUSAL_SURFACES
                       if any(one.surface == surface for one in events))
    owners = tuple(dict.fromkeys(one.owner for one in events))
    by_owner = tuple(_line(owner, tuple(one for one in events if one.owner == owner))
                     for owner in owners)
    return CausalAggregate(estimator=ESTIMATOR_VERSION, runs=len(samples),
                           events_total=len(events), overall=_line("overall", events),
                           by_surface=by_surface, by_owner=by_owner)


def render(result: CausalAggregate) -> tuple[str, ...]:
    """The lines a report prints; the caller decides where."""
    rows: list[str] = [
        f"Estimator: `{result.estimator}`. Emissions: {result.events_total}; runs: {result.runs}.",
        "Causality is read from the recorded provider chronology only; a missing",
        "boundary is not_identifiable, never a pass. Scheduled hops are not read here.",
        "",
        "| Surface | Emissions | Tool-causal | Attributed | First result | Later result | "
        "Ambiguous | Unattributed | Not identifiable | User-provided |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for line in result.by_surface:
        rows.append(
            f"| {line.key} | {line.candidates} | {line.tool_causal} | {line.attributed} | "
            f"{line.first_result} | {line.later_result} | {line.ambiguous} | "
            f"{line.unattributed} | {line.not_identifiable} | {line.user_provided} |")
    rows.extend([
        "", "Value, form, residual and joint divide by ATTRIBUTED emissions only.",
        "",
        "| Surface | Attributed | Value | Form | Form unmeasured | Residual | Joint |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for line in result.by_surface:
        rows.append(f"| {line.key} | {line.attributed} | {line.value_ok} | {line.form_ok} | "
                    f"{line.form_unmeasured} | {line.residual} | {line.joint_ok} |")
    rows.extend(["", "| Owner | Emissions | Attributed | Ambiguous | Unattributed | "
                     "Not identifiable | User-provided |", "|---|---:|---:|---:|---:|---:|---:|"])
    for line in result.by_owner:
        rows.append(f"| {line.key} | {line.candidates} | {line.attributed} | "
                    f"{line.ambiguous} | {line.unattributed} | {line.not_identifiable} | "
                    f"{line.user_provided} |")
    return tuple(rows)
