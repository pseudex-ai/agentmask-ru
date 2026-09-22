"""From the run's RECORDS to one `HopObservation` per crossing. Pure, offline.

`observe(case, run, ic, cc)` is the whole measuring front end of v5: it takes
the case's DECLARED hops (§1 of `contracts.py`) and the records the harness
wrote for the gateway arm, and decides, for each one, what the model read, what
the consumer received, and whether the crossing happened at all. Everything
downstream — every metric, every fixture, the report — reads only what this
file produced, so a metric can never reach for the engine or for a model.

THREE RULES DECIDE EVERYTHING HERE, AND THEY ARE NOT SYMMETRIC.

  * ORIENTATION. On the way IN the owner of the form is the SOURCE, so
    `produced` is the substitute the model read and `reference` is the
    source's own surface. On the way OUT the owner is the AGENT, so `produced`
    is the real value the consumer received and `reference` is the substitute
    EXACTLY as the agent wrote it — read off its output, never canonicalised
    first, because the agent's spelling is the thing being measured.
  * COVERAGE, NOT OVERLAP. A piece of a real value that survived is a leak.
    An IN/tool hop whose span is only PARTIALLY covered by a replaced piece is
    `leaked`, never `observed` with a note; v1 of AgentPII scored 97.6% recall
    against 95.0% coverage and the difference was 69 real leaks.
  * AN OPTIONAL HOP THAT DID NOT HAPPEN IS NOT EMITTED; a required one is
    `absent` and counts as a miss. Emitting both as «observed with nothing to
    compare» is v4's D1 defect — `values_ok` was `not any(...)` over an empty
    list and a triple that made no call passed five levels.

WHY `difflib` FOR THE ANSWER. The engine restores the reply in one pass and
records no spans for it; asking the engine where it substituted would be the
instrument reading the defendant's notes. `SequenceMatcher` over
(`reply_raw`, `reply`) is a pure alignment of two strings this file did not
write: every `replace` opcode is a candidate crossing, and a substitute
standing inside an `equal` opcode is a substitute that SURVIVED into what the
customer reads — `residual`, the product's own critical defect.

Run the test: cd prototype && source .venv/bin/activate
                && python3 -m bench.agentpii5.test_observe
"""
import difflib
from collections.abc import Sequence
from dataclasses import dataclass

from bench.agentpii4.compare import ObservedCall, PairVerdict
from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import PiiItem
from bench.agentpii4.tools import flatten
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import (
    ArmRunV5,
    CaseV5,
    FormVerdict,
    Hop,
    HopObservation,
    RunObservation,
    ToolResultRecord,
)
from bench.agentpii5.form import form_match
from bench.agentpii5.tools import REGISTRY_V5, spec_v5_for

# A piece of a substitute short enough to stand inside an unrelated word is not
# evidence that the substitute was there. Four characters is v4's own floor in
# `residual` detection and the public harness's; a shorter one matched «Лев»
# inside «Лебедева» and attributed one person's answer span to another.
MIN_PIECE = 4
# Roles `parts_of` returns that are NOT the personal datum: the settlement is a
# place reference every Russian city shares (`docs/…` and v4's own rule), and
# the generic word and the markers are grammar, not identity. Used by
# `pieces_of` so `coverage` does not call a surviving «Ижевск» a leak.
EXEMPT_ROLES: frozenset[str] = frozenset({"city", "gender"})
# An `equal` run shorter than this INSIDE a rewritten region is noise, not
# shared text: «ПАХОМОВА» → «ИВАНОВА» aligns as replace/«О»/replace because the
# two words share one letter, and the raw spans that come out carry no whole
# substitute at all — every answer hop then looks `absent`. The runs are merged
# before anything reads them, and the floor is `MIN_PIECE` for the same reason
# `MIN_PIECE` is four: below it a match is a coincidence.
MIN_EQUAL_RUN = 4


class ObserveError(ValueError):
    """A case that declares a crossing its own tools cannot carry. Raised, never
    swallowed: a silently dropped hop shrinks a denominator, and a denominator
    that moves with the data is how an instrument flatters itself."""


@dataclass(frozen=True)
class AttributedSpan:
    """One `replace` opcode of the answer alignment, with the items whose
    substitute stood inside its RAW half. Several items share one span when the
    agent wrote «Кудрявцевой Диане» as one phrase — that is `shared_block`, and
    the metric needs the grouping, so the observer keeps it instead of throwing
    it away after emitting the hops."""

    raw_start: int
    raw_end: int
    restored_start: int
    restored_end: int
    item_ids: tuple[str, ...]


# --- small readers ---------------------------------------------------------------------

def _as_text(value: object) -> str:
    """A leaf as the consumer received it. A number written into a tool field is
    still a form (padding, separators), so it is rendered, not skipped."""
    return value if isinstance(value, str) else ("" if value is None else str(value))


def fold(text: str) -> str:
    return text.casefold().replace("ё", "е")


def items_by_id(case: CaseV5) -> dict[str, PiiItem]:
    return {item.id: item for item in case.base.pii}


def pieces_of(pii_type: str, surface: str) -> tuple[str, ...]:
    """The pieces of a value whose survival is a leak — the typed parts minus
    the exempt roles, minus anything shorter than `MIN_PIECE`."""
    parts = parts_of(pii_type, surface)
    return tuple(value for role, value in sorted(parts.items())
                 if role not in EXEMPT_ROLES and len(value) >= MIN_PIECE)


def substitute_surfaces(run: ArmRunV5, item_id: str) -> tuple[str, ...]:
    """Every spelling of one item's substitute the run recorded: the one the
    arm record kept and every one a mention saw. A model that read «Кудрявцева»
    in message 1 and «Кудрявцевой» in message 5 read TWO surfaces of one
    substitute, and attributing the answer span needs both."""
    out: list[str] = []
    minted = run.base.substitutes.get(item_id)
    if minted is not None and minted[0]:
        out.append(minted[0])
    for mention in run.mentions:
        if mention.item_id == item_id and mention.substitute and mention.substitute not in out:
            out.append(mention.substitute)
    return tuple(out)


def _field_order(tool_name: str, path: str) -> int:
    spec = spec_v5_for(tool_name, path) if tool_name in REGISTRY_V5 else None
    if spec is None:
        return len(REGISTRY_V5[tool_name].base.fields) if tool_name in REGISTRY_V5 else 0
    fields = REGISTRY_V5[tool_name].base.fields
    return next((index for index, one in enumerate(fields) if one.path == spec.path), len(fields))


def leaf_text(flat: dict[str, object], tool_name: str, path: str) -> str:
    """The argument leaf at `path`, or the join of the leaves UNDER it.

    A value carried by several fields (street / house / flat) is ONE hop, and
    the comparator reads `by_fields` off the separator: joining with a comma
    would make «улица Ленина, 14» and a by-fields write indistinguishable and
    would silently move three LOC features at once (`contracts.FIELD_SEP`)."""
    if path in flat:
        return _as_text(flat[path])
    under = [key for key in flat if key.startswith(path + ".") or key.startswith(path + "[")]
    if not under:
        return ""
    ordered = sorted(under, key=lambda key: (_field_order(tool_name, key), key))
    return contracts.FIELD_SEP.join(text for text in (_as_text(flat[key]) for key in ordered) if text)


def _has_residual(call: ObservedCall, path: str) -> bool:
    """The engine reported a surviving substitute at this leaf or under it."""
    return any(left and (key == path or key.startswith(path + ".") or key.startswith(path + "["))
               for key, left in call.residual.items())


def calls_of_turn(run: ArmRunV5, turn: int) -> tuple[tuple[int, ObservedCall], ...]:
    """(index, call) of every call the arm made inside one turn, in order.

    `call_turns` is parallel to `base.calls`; a record whose two lengths
    disagree is a harness bug that would silently re-attribute every call of the
    run, so it is refused here rather than indexed past."""
    if len(run.call_turns) != len(run.base.calls):
        raise ObserveError(
            f"{run.base.case_id}|{run.base.repeat}: {len(run.call_turns)} call turns for "
            f"{len(run.base.calls)} calls; the two lists are written together and must match")
    return tuple((index, call) for index, call in enumerate(run.base.calls)
                 if run.call_turns[index] == turn)


def call_for_hop(run: ArmRunV5, hop: Hop) -> ObservedCall | None:
    """The `call_ordinal`-th call of `hop.tool_name` inside `hop.turn`."""
    same = [call for _index, call in calls_of_turn(run, hop.turn) if call.name == hop.tool_name]
    return same[hop.call_ordinal] if 0 <= hop.call_ordinal < len(same) else None


def result_for_hop(run: ArmRunV5, hop: Hop) -> ToolResultRecord | None:
    for record in run.tool_results:
        if (record.tool_name == hop.tool_name and record.call_ordinal == hop.call_ordinal
                and record.turn == hop.turn):
            return record
    return None


def span_of_item(record: ToolResultRecord, item_id: str) -> tuple[int, int] | None:
    """The mock's slot for this item in this result. A forced error echoes the
    offending value under `ECHO_TAG_PREFIX`; it is the SAME crossing (the real
    value is in the error body the model reads), so both tags are looked up."""
    if item_id in record.spans_real:
        return record.spans_real[item_id]
    return record.spans_real.get(contracts.ECHO_TAG_PREFIX + item_id)


def covering_piece(record: ToolResultRecord, span: tuple[int, int]) -> tuple[int, int, str, str] | None:
    """The replaced piece that covers the slot ENTIRELY, or None.

    Partial cover is not cover: «Кузнецов Дмитрий» with only the given name
    replaced leaves the surname in the model's context, and a metric that
    accepted the overlap would report the leak as a success."""
    for piece in record.pieces:
        if piece[0] <= span[0] and span[1] <= piece[1]:
            return piece
    return None


# --- the answer alignment --------------------------------------------------------------

Opcode = tuple[str, int, int, int, int]


def merged_opcodes(raw: str, restored: str) -> tuple[Opcode, ...]:
    """`SequenceMatcher` opcodes with short `equal` islands absorbed.

    `autojunk=False` on purpose: the heuristic drops characters occurring in
    more than 1% of a long string, and a Russian reply is mostly such
    characters — with it on, the opcodes of a 2 000-character answer collapse
    into one `replace` and every span is attributed to every item. The
    absorption is the opposite correction and both are needed: raw alignment
    shatters a rewritten name into letter-sized pieces, and a piece cannot hold
    the substitute it is supposed to prove."""
    opcodes = difflib.SequenceMatcher(None, raw, restored, autojunk=False).get_opcodes()
    out: list[Opcode] = []
    for tag, raw_start, raw_end, new_start, new_end in opcodes:
        island = tag == "equal" and raw_end - raw_start < MIN_EQUAL_RUN
        if out and out[-1][0] != "equal" and (tag != "equal" or island):
            previous = out[-1]
            out[-1] = ("replace", previous[1], raw_end, previous[3], new_end)
            continue
        out.append(("equal" if tag == "equal" else "replace", raw_start, raw_end, new_start, new_end))
    return tuple(out)


def _indexable_fold(text: str) -> str:
    """`fold` for work on OFFSETS. `str.casefold` may change a string's length
    (ß → ss) and every span here is an index into the original; `str.lower` is
    1:1 for Cyrillic and Latin, which is the alphabet the corpus is written in.
    The same rule `pseudex/normalize.py` lives by, arrived at independently."""
    return text.lower().replace("ё", "е")


def _occurrences(haystack: str, needle: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    at = haystack.find(needle)
    while at != -1 and needle:
        out.append((at, at + len(needle)))
        at = haystack.find(needle, at + 1)
    return out


def answer_spans(case: CaseV5, run: ArmRunV5) -> tuple[AttributedSpan, ...]:
    """Every rewritten region of the reply, with the items it carries.

    A span is attributed to every item whose substitute — or a piece of it at
    least `MIN_PIECE` long — OVERLAPS the rewritten region, and the region is
    then WIDENED to hold the whole occurrence. Overlap rather than containment,
    because two names that share a suffix align as «ПАХОМ» / «ИВАНО» with «ОВА»
    left in an `equal` run: containment finds no substitute in the span and
    every answer hop reads `absent`. The widening is safe in exactly the
    stretch it uses — inside an `equal` run the two offsets move together, so
    the restored side is widened by the same amounts and still names the same
    text.

    Several items may share one span; that is `shared_block`, kept rather than
    resolved, because an attribution nothing can inspect is one nobody checked.
    """
    surfaces = {item.id: substitute_surfaces(run, item.id) for item in case.base.pii}
    needles = {item.id: tuple(dict.fromkeys(
        (*surfaces[item.id], *(piece for surface in surfaces[item.id]
                               for piece in pieces_of(item.type, surface)))))
        for item in case.base.pii}
    raw_folded = _indexable_fold(run.reply_raw)
    opcodes = merged_opcodes(run.reply_raw, run.base.reply)
    out: list[AttributedSpan] = []
    for index, (tag, raw_start, raw_end, new_start, new_end) in enumerate(opcodes):
        if tag != "replace":
            continue
        left = opcodes[index - 1][1] if index and opcodes[index - 1][0] == "equal" else raw_start
        right = (opcodes[index + 1][2] if index + 1 < len(opcodes)
                 and opcodes[index + 1][0] == "equal" else raw_end)
        carried: list[str] = []
        window_start, window_end = raw_start, raw_end
        for item in case.base.pii:
            hits = [span for needle in needles[item.id]
                    for span in _occurrences(raw_folded, _indexable_fold(needle))
                    if span[0] < raw_end and raw_start < span[1]]
            if not hits:
                continue
            carried.append(item.id)
            window_start = max(left, min(window_start, min(span[0] for span in hits)))
            window_end = min(right, max(window_end, max(span[1] for span in hits)))
        if carried:
            out.append(AttributedSpan(window_start, window_end,
                                      new_start - (raw_start - window_start),
                                      new_end + (window_end - raw_end), tuple(carried)))
    return _merge_overlapping(out)


def _merge_overlapping(spans: list[AttributedSpan]) -> tuple[AttributedSpan, ...]:
    """Two rewritten regions that both sit inside ONE substitute are one
    crossing. «Кудрявцевой Диане» → «Кузнецовой Дарье» aligns as two replaces
    around the shared «вой Д», and each widened window reaches into the other:
    left as two spans the answer hop would report half a name as its produced
    value. Only STRICT overlap merges — two adjacent people's names are
    separated by text neither occurrence covers, so their windows stop short of
    each other and stay two spans (which is what `shared_block` counts)."""
    out: list[AttributedSpan] = []
    for span in spans:
        if out and span.raw_start < out[-1].raw_end:
            previous = out[-1]
            out[-1] = AttributedSpan(
                previous.raw_start, max(previous.raw_end, span.raw_end),
                previous.restored_start, max(previous.restored_end, span.restored_end),
                tuple(dict.fromkeys((*previous.item_ids, *span.item_ids))))
            continue
        out.append(span)
    return tuple(out)


def residual_answer_items(case: CaseV5, run: ArmRunV5) -> frozenset[str]:
    """Items whose substitute stands in a region the restoration did NOT touch.

    Read off the same alignment, so «the engine replaced it elsewhere» cannot
    excuse a copy that survived: an `equal` opcode is text identical in both
    replies, and a substitute inside it is text the customer reads."""
    surfaces = {item.id: substitute_surfaces(run, item.id) for item in case.base.pii}
    kept: set[str] = set()
    for tag, raw_start, raw_end, _new_start, _new_end in merged_opcodes(run.reply_raw, run.base.reply):
        if tag != "equal":
            continue
        raw = fold(run.reply_raw[raw_start:raw_end])
        for item_id, spellings in surfaces.items():
            if any(fold(surface) in raw for surface in spellings if surface):
                kept.add(item_id)
    return frozenset(kept)


# --- per-owner observation -------------------------------------------------------------

def _verdict(pii_type: str, produced: str, reference: str) -> FormVerdict:
    return form_match(pii_type, produced, reference)


def _observed(case: CaseV5, repeat: int, hop: Hop, declared: bool, pii_type: str,
              produced: str, reference: str) -> HopObservation:
    return HopObservation(case_id=case.base.id, repeat=repeat, hop=hop, declared=declared,
                          pii_type=pii_type, produced=produced, reference=reference,
                          status="observed", verdict=_verdict(pii_type, produced, reference))


def _flat(case: CaseV5, repeat: int, hop: Hop, declared: bool, pii_type: str,
          produced: str, reference: str, status: str) -> HopObservation:
    return HopObservation(case_id=case.base.id, repeat=repeat, hop=hop, declared=declared,
                          pii_type=pii_type, produced=produced, reference=reference,
                          status=status, verdict=None)


def _in_user(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop, item: PiiItem) -> HopObservation:
    minted = run.base.substitutes.get(item.id)
    if minted is None or not minted[0]:
        return _flat(case, repeat, hop, True, item.type, "", item.value, "leaked")
    return _observed(case, repeat, hop, True, item.type, minted[0], item.value)


def _in_tool(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop, item: PiiItem) -> HopObservation:
    record = result_for_hop(run, hop)
    if record is None:
        return _flat(case, repeat, hop, True, item.type, "", "", "absent")
    span = span_of_item(record, item.id)
    if span is None:
        # The result exists and carries no slot for this item: the crossing did
        # not happen. NOT `leaked` — there is no real value in the text that
        # could have reached the model — and not silence either, because the
        # case declared it and a required hop that did not happen is a miss.
        return _flat(case, repeat, hop, True, item.type, "", "", "absent")
    reference = record.text_real[span[0]:span[1]]
    piece = covering_piece(record, span)
    if piece is None:
        return _flat(case, repeat, hop, True, item.type, "", reference, "leaked")
    return _observed(case, repeat, hop, True, item.type, piece[2], reference)


def _recall_request(run: ArmRunV5, turn: int) -> int | None:
    """The model request that carried the recall turn.

    The turn's own mentions name it directly. Under anaphora the recall turn
    says no value at all, so there is no mention to read: the request is the one
    AFTER the last mention before the turn — the transcript grew by one request
    and carried the earlier message forward."""
    at_turn = [mention.request_index for mention in run.mentions if mention.msg == turn]
    if at_turn:
        return min(at_turn)
    before = [mention for mention in run.mentions if 0 <= mention.msg < turn]
    if not before:
        return None
    last_msg = max(mention.msg for mention in before)
    return max(mention.request_index for mention in before if mention.msg == last_msg) + 1


def _in_memory(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop, item: PiiItem) -> HopObservation:
    request = _recall_request(run, hop.turn)
    own = [mention for mention in run.mentions if mention.item_id == item.id]
    if request is None or not own:
        return _flat(case, repeat, hop, True, item.type, "", item.value, "absent")
    first_msg = min(mention.msg for mention in own)
    carried = [mention for mention in own
               if mention.request_index == request and mention.msg == first_msg]
    if not carried:
        return _flat(case, repeat, hop, True, item.type, "", item.value, "leaked")
    return _observed(case, repeat, hop, True, item.type, carried[0].substitute, item.value)


def _out_call(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop,
              item: PiiItem) -> HopObservation | None:
    expected_owner = contracts.hop_owner_of_leaf(hop.tool_name, hop.path)
    if hop.owner != expected_owner:
        raise ObserveError(
            f"{case.base.id}: hop {hop.hop_index} declares owner {hop.owner!r} for "
            f"{hop.tool_name}.{hop.path}, which is a {expected_owner!r} leaf "
            f"(contracts.TEMPLATE_FIELDS / SUMMARY_FIELDS decide, not the case)")
    call = call_for_hop(run, hop)
    if call is None:
        return None if hop.optional else _flat(case, repeat, hop, True, item.type, "", "", "absent")
    written = leaf_text(flatten(call.written), hop.tool_name, hop.path)
    restored = leaf_text(flatten(call.restored), hop.tool_name, hop.path)
    if _has_residual(call, hop.path):
        return _flat(case, repeat, hop, True, item.type, restored, written, "residual")
    return _observed(case, repeat, hop, True, item.type, restored, written)


def _out_answer(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop, item: PiiItem,
                spans: Sequence[AttributedSpan], residual: frozenset[str]) -> HopObservation | None:
    for span in spans:
        if item.id in span.item_ids:
            return _observed(case, repeat, hop, True, item.type,
                             run.base.reply[span.restored_start:span.restored_end],
                             run.reply_raw[span.raw_start:span.raw_end])
    if item.id in residual:
        return _flat(case, repeat, hop, True, item.type, "", "", "residual")
    return None if hop.optional else _flat(case, repeat, hop, True, item.type, "", "", "absent")


# --- extra (undeclared) hops -----------------------------------------------------------

def _synthetic(kind: str, owner: str, item_id: str, turn: int, tool_name: str,
               call_ordinal: int, path: str) -> Hop:
    """A crossing the agent made that the case did not declare. `hop_index` is
    -1 so no `source_hop` can ever point at it: an undeclared hop counts in the
    form lines and nowhere else, because a denominator built from what the agent
    happened to do is a denominator the agent chooses."""
    return Hop(kind=kind, owner=owner, item_id=item_id, hop_index=-1, turn=turn,
               tool_name=tool_name, call_ordinal=call_ordinal, parallel_group="",
               source_hop=-1, path=path, optional=False)


def _extra_call_hops(case: CaseV5, run: ArmRunV5, repeat: int,
                     declared: Sequence[Hop]) -> list[HopObservation]:
    taken = {(hop.turn, hop.tool_name, hop.call_ordinal, hop.path)
             for hop in declared if hop.kind == "OUT" and hop.tool_name}
    surfaces = {item.id: substitute_surfaces(run, item.id) for item in case.base.pii}
    out: list[HopObservation] = []
    for index, call in enumerate(run.base.calls):
        if call.name not in REGISTRY_V5:
            continue
        turn = run.call_turns[index]
        ordinal = sum(1 for other, one in enumerate(run.base.calls)
                      if other < index and one.name == call.name and run.call_turns[other] == turn)
        flat_written = flatten(call.written)
        flat_restored = flatten(call.restored)
        for path in sorted(flat_written):
            spec = spec_v5_for(call.name, path)
            if spec is None or spec.kind != "identity" or spec.pii_type not in contracts.FORM_FEATURES:
                continue
            if (turn, call.name, ordinal, path) in taken:
                continue
            written = _as_text(flat_written[path])
            restored = _as_text(flat_restored.get(path, ""))
            if not written:
                continue
            item_id = next((one for one, spellings in surfaces.items()
                            if any(spelling and fold(spelling) in fold(written)
                                   for spelling in spellings)), "")
            hop = _synthetic("OUT", contracts.hop_owner_of_leaf(call.name, path),
                             item_id, turn, call.name, ordinal, path)
            status = "residual" if _has_residual(call, path) else "observed"
            out.append(_flat(case, repeat, hop, False, spec.pii_type, restored, written, status)
                       if status == "residual"
                       else _observed(case, repeat, hop, False, spec.pii_type, restored, written))
    return out


def _extra_answer_hops(case: CaseV5, run: ArmRunV5, repeat: int, declared: Sequence[Hop],
                       spans: Sequence[AttributedSpan]) -> list[HopObservation]:
    claimed = {hop.item_id for hop in declared if hop.kind == "OUT" and hop.owner == "answer"}
    types = {item.id: item.type for item in case.base.pii}
    out: list[HopObservation] = []
    for span in spans:
        for item_id in span.item_ids:
            if item_id in claimed or types.get(item_id) not in contracts.FORM_FEATURES:
                continue
            hop = _synthetic("OUT", "answer", item_id, -1, "", -1, "")
            out.append(_observed(case, repeat, hop, False, types[item_id],
                                 run.base.reply[span.restored_start:span.restored_end],
                                 run.reply_raw[span.raw_start:span.raw_end]))
    return out


# --- the observer ----------------------------------------------------------------------

def observe(case: CaseV5, run: ArmRunV5, ic: PairVerdict | None,
            cc: PairVerdict | None) -> RunObservation:
    """One (case, repeat) of the GATEWAY arm, as the metrics read it.

    `ic` and `cc` ride along untouched: the v4 paired verdicts belong to the
    side-by-side, and nothing in this file or in `metrics.py` may read them —
    the whole point of v5's form axis is that it lives INSIDE arm I, where the
    two live models cannot cancel each other's normalisation (spec §1)."""
    items = items_by_id(case)
    spans = answer_spans(case, run)
    residual = residual_answer_items(case, run)
    observations: list[HopObservation] = []
    for hop in case.hops:
        item = items.get(hop.item_id)
        if item is None:
            raise ObserveError(
                f"{case.base.id}: hop {hop.hop_index} names item {hop.item_id!r}, which the "
                f"case does not carry; R04 should have refused this case at build time")
        if item.type not in contracts.FORM_FEATURES:
            raise ObserveError(
                f"{case.base.id}: hop {hop.hop_index} carries type {item.type!r}, which has no "
                f"form features; contracts.FORM_FEATURES is the closed list")
        one: HopObservation | None
        if hop.kind == "IN" and hop.owner == "user":
            one = _in_user(case, run, run.base.repeat, hop, item)
        elif hop.kind == "IN" and hop.owner in ("tool", "document"):
            one = _in_tool(case, run, run.base.repeat, hop, item)
        elif hop.kind == "IN" and hop.owner == "memory":
            one = _in_memory(case, run, run.base.repeat, hop, item)
        elif hop.kind == "OUT" and hop.owner == "answer":
            one = _out_answer(case, run, run.base.repeat, hop, item, spans, residual)
        elif hop.kind == "OUT":
            one = _out_call(case, run, run.base.repeat, hop, item)
        else:
            raise ObserveError(
                f"{case.base.id}: hop {hop.hop_index} is {hop.kind}/{hop.owner}, which is not a "
                f"pair of contracts.HOP_KINDS × HOP_OWNERS")
        if one is not None:
            observations.append(one)
    observations += _extra_call_hops(case, run, run.base.repeat, case.hops)
    observations += _extra_answer_hops(case, run, run.base.repeat, case.hops, spans)
    return RunObservation(case=case, repeat=run.base.repeat, hops=tuple(observations),
                          run=run, ic=ic, cc=cc)


def main() -> int:
    from bench.agentpii5.test_observe import main as run_tests
    return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
