"""Every v5 metric as ONE pure function of observations, and nothing else.

A metric here takes `Sequence[RunObservation]` and returns one `Line` — two
counters, never a rate. The rate, the Clopper–Pearson interval and the «this
certifies ≥ f%» line are properties of `contracts.Line`, so no caller can
round a number differently from another caller, and «100%» is never printed
for a finite sample.

WHAT A METRIC MAY READ. The observations, and only them: the case's
declarations, the hops `observe.py` produced, and the arm's own records. It
may NOT read `ic` / `cc` — the v4 paired verdicts. That is not tidiness. v4
compared arm I with arm C and the comparison CANCELS form: two live models
normalise a name the same way, so a gateway that hands the agent «Иванову
Петру» scores equal to a control that never saw a substitute. The v5 form axis
exists because the check runs INSIDE arm I (spec §1), and a metric that peeked
at `ic` would quietly restore the defect v5 was built to remove
(`test_metrics.test_form_lines_ignore_controls`).

COUNTERS, NOT RATES; AND `Line(name, 0, 0)` FOR «NOT APPLICABLE». A metric
whose population is empty returns a zero-total line and the report prints
«н/п». Printing 0% instead would say the gateway failed something it was never
asked to do, which is the cheapest way to make a report unreadable.

EVERY DENOMINATOR IS DECLARED BY THE CASE, NOT BY THE AGENT — except the form
lines, which count undeclared crossings too. A denominator the agent can
shrink by acting less is the v4 D3 defect («did the arm act at all») in a new
coat: an absent required hop is a MISS here, never a smaller total.

Run the test: cd prototype && source .venv/bin/activate
                && python3 -m bench.agentpii5.test_metrics
"""
import difflib
from collections.abc import Sequence
from dataclasses import replace

from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import Locus, PiiItem
from bench.agentpii4.tools import FieldSpec, flatten
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import (
    HopObservation,
    Line,
    MentionRecord,
    Metric,
    RunObservation,
    ToolResultRecord,
)
from bench.agentpii5.form_tables import GENERIC_WORDS
from bench.agentpii5.observe import (
    answer_spans,
    calls_of_turn,
    covering_piece,
    fold,
    item_survives_in,
    items_by_id,
    occurrences_of,
    own_stems,
    part_matches,
    result_for_hop,
    span_of_item,
    residual_answer_items,
    substitute_surfaces,
    survives_in,
    value_needles,
)
from bench.agentpii5.tools import expected_leaf_value, spec_v5_for

# Twelve cue words — «the customer named the field». The `cue` axis asks
# whether detection leans on a nearby label, and a longer list would make every
# message cued and the axis a constant. Matched as a prefix so «телефона»,
# «адресу», «родился» all count; `CUE_WINDOW` is the engine's own 60-character
# window, used here as a definition of «nearby», never imported from it.
CUE_WORDS: tuple[str, ...] = (
    "тел", "телефон", "адрес", "улиц", "дом", "кв", "снилс", "инн", "паспорт", "карт",
    "почт", "родил")
CUE_WINDOW = 60
# A reply that rewrote more than 30% of the control's is flagged. The public
# harness's own threshold (`Scores.rewrite_flagged`), kept identical so the two
# numbers can be read side by side.
REWRITE_RATIO_FLOOR = 0.7
# Words that are grammar, not identity: a surviving «улица» or «д.» in a masked
# tool result is not a leak, and counting it as one would make `coverage`
# refuse every address the mock renders with its generic word. THE NAME IS KEPT
# AND THE SET IS NOT SECOND: it is `form_tables.GENERIC_WORDS`, the one
# vocabulary rule N4 of contracts §4bis reads, re-exported here because
# `judge.py` subtracts the same words from its own evidence and two sets that
# must stay equal are one drift away from the judge and the leak lines
# disagreeing about whether «марта» identifies anybody.
GRAMMAR_WORDS: frozenset[str] = GENERIC_WORDS


# --- shared readers --------------------------------------------------------------------

def _line(name: str, hits: int, total: int) -> Line:
    return Line(name=name, hits=hits, total=total)


def _hops(observations: Sequence[RunObservation], kind: str) -> list[tuple[RunObservation, HopObservation]]:
    return [(one, hop) for one in observations for hop in one.hops if hop.hop.kind == kind]


def _owned(observations: Sequence[RunObservation], kind: str,
           owners: tuple[str, ...]) -> list[tuple[RunObservation, HopObservation]]:
    return [(one, hop) for one, hop in _hops(observations, kind) if hop.hop.owner in owners]


def _declared_hop(one: RunObservation, index: int) -> HopObservation | None:
    return next((hop for hop in one.hops if hop.declared and hop.hop.hop_index == index), None)


def _item_of(one: RunObservation, item_id: str) -> PiiItem | None:
    return items_by_id(one.case).get(item_id)


def value_matches(pii_type: str, produced: str, target: str) -> bool:
    """Did the consumer receive THE WHOLE value, byte for byte.

    LOC is the one exception, and it is not leniency: an address is carried by
    several fields and joined with `FIELD_SEP`, so the string can never equal a
    one-line canonical. The roles are compared instead — street, house, flat —
    and the city is left out because a tool that stores the city in its own
    field is not a different address."""
    if pii_type == "LOC":
        left, right = parts_of("LOC", produced.replace(contracts.FIELD_SEP, ", ")), parts_of("LOC", target)
        roles = [role for role in ("street", "house", "flat") if role in right]
        return bool(roles) and all(fold(left.get(role, "")) == fold(right[role]) for role in roles)
    return fold(produced.strip()) == fold(target.strip())


def leaf_spec(tool_name: str, path: str) -> FieldSpec | None:
    """The `FieldSpec` that describes this tool leaf — the registry's own
    statement of what the leaf asks for (`contact.last_name` the surname,
    `address.building` the house number, `patient.birth_date` the ISO date).
    None for an answer hop, which names no tool, and for a leaf no spec
    describes; both take the WHOLE value."""
    if not tool_name or not path:
        return None
    return spec_v5_for(tool_name, path)


# The locus of a value that came back from a TOOL rather than out of the
# corpus. `returned_as_item` needs one to build a `PiiItem`, and no comparison
# ever reads it — the alternative was a second rule for «the value a leaf
# expects», which is the thing R-53 removed.
_RETURNED_LOCUS: Locus = Locus(kind="seed", msg=-1, start=-1, end=-1, record="", path="")


def returned_as_item(source: PiiItem, returned: str) -> PiiItem:
    """What tool A actually returned, read as an item.

    ONE DEFINITION OF «THE VALUE A LEAF EXPECTS» (`tools.expected_leaf_value`,
    ruling R-53) serves both the corpus's own item and the chain's hand-over,
    and it takes an item — so the hand-over's target becomes one. The id and
    the identity stay empty on purpose: this value belongs to no population
    that counts identities, and giving it one would let it be mistaken for a
    corpus item.

    THE ROLES COME FROM THE SOURCE HOP'S OWN DECLARATION, NEVER FROM THE
    STRING. Splitting the returned surface with `parts_of` re-guessed which
    word is a surname from its SUFFIX, and the guess is wrong for every
    surname that does not wear one: `leaf_value_ok` on `patient.last_name`
    called «заболотный» and «миллер» the wrong value while «букин» passed by
    accident of its ending — four transitions of the committed corpus, and the
    class grows with any regeneration that draws a non-suffix-shaped name. The
    corpus BUILT the item from its parts and states which role the result
    rendered; reading them is free and cannot be wrong the way a suffix can."""
    return replace(source, id="", identity="", value=returned, canonical=returned,
                   parts=dict(source.parts), where=_RETURNED_LOCUS)


def role_matches(pii_type: str, produced: str, target: str) -> bool:
    """Did THIS LEAF receive its own part of the value.

    A THIN CALLER OF `observe.part_matches` (contracts §4bis). The comparison
    of two renderings of one part belongs to the needle layer — `leaf_holds`
    asks it of a substitute and this line asks it of the real value, and two
    copies of «is this the same part written another way» is exactly the
    shape of the defect round 4 removed. The FORM the leaf wears is
    `form_hOUT`'s question and is not folded in here."""
    return part_matches(pii_type, produced, target)


def leaf_value_ok(item: PiiItem, tool_name: str, path: str, produced: str) -> bool:
    """Did the leaf receive the value asked of it: its PART when the tool asks
    for a part, the whole value when it asks for the whole.

    A THIN CALLER OF `tools.expected_leaf_value` (R-53). What a leaf expects is
    the registry's business and it is decided there, once; this function only
    compares, and the comparison is per type — digits with digits, an ISO date
    with an ISO date (`role_matches`). Two definitions of the expected value
    would have to stay equal for ever, and the one that drifted would move
    every value line at once.

    The target is an ITEM, which is also how the chain's hand-over reaches
    here (`returned_as_item`): the corpus item carries the parts the corpus
    BUILT it from — a LOC canonical is the street alone while its parts carry
    house, flat and city, so splitting the canonical instead would lose them.

    A role the target has NO part for is a MISS and a corpus defect: the case
    tells the agent to put a patronymic into `contact.middle_name` for a
    customer who never said one, so no string can satisfy both the tool and
    the metric. 793 of 8 399 declared OUT leaves were in that state when this
    rule was written and the rebuilt corpus carries none — which is exactly
    why the verdict stays pinned by a fixture
    (`fx_end_to_end_adversarial`): making it a silent hit would be the v4
    defect «a triple with nothing to compare passed all five levels» with the
    parts table in its hand, and it would come back invisibly.

    A FREE LEAF IS SATISFIED WHEN THE VALUE SURVIVES IN IT. `notify_sms.text`,
    `ticket_create.text`, `escalate_to_human.summary` and `email_send.body`
    are PROSE the agent composes around the value — «Здравствуйте, Миллер
    Валерий! Ваш заказ принят.» — and byte equality with the whole canonical
    is False by construction there: 210 of `chain_value`'s 938 declared
    transitions (22.4 %) landed on such a leaf and could not be earned by any
    gateway. The question that fits a value with prose around it is the needle
    layer's (contracts §4bis, N1–N2), and it is the same one `answer_real`
    asks of the reply, which is the same shape of text. It can still fail: a
    leaf holding another value, an empty leaf, or one where the substitute was
    never restored carries no needle of the expected value."""
    spec = leaf_spec(tool_name, path)
    if spec is not None and spec.kind == "free":
        return item_survives_in(item, item.canonical or item.value, produced)
    if spec is None or not spec.role:
        return value_matches(item.type, produced, item.canonical or item.value)
    return role_matches(item.type, produced, expected_leaf_value(item, spec))


def _item_value_ok(hop: HopObservation, item: PiiItem) -> bool:
    return leaf_value_ok(item, hop.hop.tool_name, hop.hop.path, hop.produced)


def value_repaired(pii_type: str, produced: str, target: str) -> bool:
    """The value arrived REPAIRED rather than as written: the canonical date
    notation, the nominative of a name, the digits of a phone. Diagnostic only
    (`round_trip_repaired`); the promise the product makes is `round_trip`, and
    folding the two would let a normalisation that costs the reader the verbatim
    text be bought back by the same line that measures it."""
    if value_matches(pii_type, produced, target):
        return True
    if pii_type in ("DOB", "DATE"):
        return bool(parts_of("DOB", produced)) and parts_of("DOB", produced) == parts_of("DOB", target)
    if pii_type == "NAME":
        left, right = parts_of("NAME", produced), parts_of("NAME", target)
        roles = sorted(set(left) & set(right))
        return bool(roles) and all(fold(left[role])[:4] == fold(right[role])[:4] for role in roles)
    if pii_type == "PHONE":
        left, right = parts_of("PHONE", produced), parts_of("PHONE", target)
        return bool(left.get("digits")) and left.get("digits") == right.get("digits")
    return False


def _item_value_repaired(hop: HopObservation, item: PiiItem) -> bool:
    """`value_repaired`, asked of the leaf's own part. Without the role the
    diagnostic would answer a different question from the line it explains,
    and the two would stop differing by «what normalisation costs»."""
    spec = leaf_spec(hop.hop.tool_name, hop.hop.path)
    if spec is None or not spec.role:
        return value_repaired(item.type, hop.produced, item.canonical or item.value)
    target = expected_leaf_value(item, spec)
    if role_matches(item.type, hop.produced, target):
        return True
    # A declined part («Ивановой» for «Иванова») is the value repaired, not
    # lost: the same four-character rule `value_repaired` uses on whole names.
    if item.type not in ("NAME", "LOC") or len(target) < 4:
        return False
    return fold(hop.produced.strip())[:4] == fold(target)[:4]


def _mentions_of(one: RunObservation, item_id: str) -> list[MentionRecord]:
    return [mention for mention in one.run.mentions if mention.item_id == item_id]


# --- §4.2 the public lines -------------------------------------------------------------

def leak(observations: Sequence[RunObservation]) -> Line:
    """Values the gateway ALTERED before the model saw them, over every value
    it was shown. Type-blind by construction — «the datum was protected» — and
    never summed with `coverage`, which asks the harder question.

    SHOWN TO THE MODEL = observed ∪ leaked, exactly `coverage`'s population.
    An `absent` hop is a tool call the agent never made: nothing crossed, and
    counting it as «altered» meant an agent that skipped a step RAISED the
    headline leak number. A passthrough whose agent called nothing printed
    2/3 while the only value it ever showed had leaked."""
    rows = [hop for _one, hop in _hops(observations, "IN") if hop.status in ("observed", "leaked")]
    return _line("leak", sum(1 for hop in rows if hop.status != "leaked"), len(rows))


def coverage(observations: Sequence[RunObservation]) -> Line:
    """Values of which NO piece survived. The number `leak` cannot give: a
    «Кузнецов Дмитрий» detected as «Дмитрий» is a leak of the surname that the
    leak line calls a success. City, generic word and markers are exempt — they
    are place references and grammar, not the person (contracts §4bis, N4).

    THREE POPULATIONS, ONE QUESTION, AND THE THIRD USED TO BE UNANSWERABLE.
    A value the model met inside a TOOL RESULT is judged on the text it read;
    a value SAID IN A MESSAGE is judged on whether its own span was replaced —
    the message is on disk and the span check is the strongest evidence there
    is. A value that stood in NO message — a seed the mock returns, recalled
    at turn 7 — has `Locus(kind='seed', msg=-1)`, so `masked_spans.get(-1)`
    was `()` and `inside` was False WHATEVER the gateway did: 70 declared
    hops of the corpus (40 NAME, 20 DOB, 10 LOC) were a forced miss and a
    perfect gateway's ceiling was 11660/11730. «Was its message span masked»
    is a question about nothing for a value no message carried, so the hop is
    decided the way it was OBSERVED: no piece of the real value may survive in
    the substitute the transcript carried into that turn."""
    hits = 0
    total = 0
    for one, hop in _hops(observations, "IN"):
        if hop.status not in ("observed", "leaked"):
            continue
        total += 1
        if hop.status != "observed":
            continue
        item = _item_of(one, hop.hop.item_id)
        if item is None:
            continue
        if hop.hop.owner in ("tool", "document"):
            record = result_for_hop(one.run, hop.hop)
            masked = record.text_masked if record is not None else ""
            hits += 0 if item_survives_in(item, hop.reference, masked) else 1
        elif item.where.kind == "message" and item.where.msg >= 0:
            spans = one.run.base.masked_spans.get(item.where.msg, ())
            inside = any(start <= item.where.start and item.where.end <= end
                         for start, end in spans)
            hits += 1 if inside else 0
        else:
            # The CANONICAL, because a seed value has no written surface: 310
            # items of the corpus carry the literal string «None» as `value`
            # while their canonical is the datum (a `str(None)` that survived
            # the build — reported to the corpus owner), and asking about
            # «None» would ask about nothing.
            hits += 0 if item_survives_in(item, item.canonical or item.value, hop.produced) else 1
    return _line("coverage", hits, total)


def typed(observations: Sequence[RunObservation]) -> Line:
    """Did the gateway also call it the right type. Over IN/tool AND IN/document
    hops — a document is a result the model reads like any other — and only
    where a replaced piece covers the slot, so a type was actually exposed:
    `DOB` and `DATE` are one answer (a birth date is a date), and a masker that
    exposes nothing gets `Line(0, 0)` and «н/п», never 0%."""
    hits = 0
    total = 0
    for one, hop in _owned(observations, "IN", ("tool", "document")):
        record = result_for_hop(one.run, hop.hop)
        span = span_of_item(record, hop.hop.item_id) if record is not None else None
        piece = covering_piece(record, span) if record is not None and span is not None else None
        if piece is None:
            continue
        total += 1
        pair = {piece[3], hop.pii_type}
        hits += 1 if piece[3] == hop.pii_type or pair == {"DOB", "DATE"} else 0
    return _line("typed", hits, total)


def _altered_with_parameter(observations: Sequence[RunObservation]) -> list[tuple[RunObservation, HopObservation, PiiItem]]:
    """Items the gateway altered on the way IN and a tool consumes on the way
    OUT. The public denominator, and the reason it is not «all items»:
    restoring a value nobody masked is not an achievement."""
    out: list[tuple[RunObservation, HopObservation, PiiItem]] = []
    for one in observations:
        altered = {hop.hop.item_id for hop in one.hops
                   if hop.hop.kind == "IN" and hop.hop.owner == "user" and hop.status == "observed"}
        for hop in one.hops:
            if not (hop.declared and hop.hop.kind == "OUT" and hop.hop.owner == "tool_arg"):
                continue
            item = _item_of(one, hop.hop.item_id)
            if item is not None and item.id in altered:
                out.append((one, hop, item))
    return out


def round_trip(observations: Sequence[RunObservation]) -> Line:
    """The leaf received the REAL value ASKED OF IT. Absolute, not a comparison
    of arms: v4 could say «the gateway arm wrote what the control wrote» and
    both could be wrong.

    THE LEAF'S OWN PART, not the whole canonical (`leaf_value_ok`, R-53):
    `contact.last_name` is right when it holds the surname and
    `patient.birth_date` when it holds the ISO date, and comparing either with
    the whole canonical topped a PERFECT gateway out at 76.8%. Notation is
    folded per type there and nothing else is: a value that arrived REPAIRED
    (the nominative of a declined name) is counted by `round_trip_repaired`
    and nowhere else (§4.4 «без фолбэков»). A leaf the gateway never masked
    (`unmasked`) and one the agent never wrote (`absent`) are misses inside the
    denominator."""
    rows = _altered_with_parameter(observations)
    hits = sum(1 for _one, hop, item in rows
               if hop.status == "observed" and _item_value_ok(hop, item))
    return _line("round_trip", hits, len(rows))


def round_trip_repaired(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC. The same population counting a value that arrived repaired.
    The gap between this line and `round_trip` is exactly what the engine's
    normalisation costs a reader who wanted the text verbatim."""
    rows = _altered_with_parameter(observations)
    hits = sum(1 for _one, hop, item in rows
               if hop.status == "observed" and _item_value_repaired(hop, item))
    return _line("round_trip_repaired", hits, len(rows))


def end_to_end(observations: Sequence[RunObservation]) -> Line:
    """«The agent still works»: the gateway restored the real value at the
    leaf, over ALL declared tool arguments — the ones the agent never wrote
    (`absent`) and the ones it never masked (`unmasked`) included, both as
    MISSES.

    A PASSTHROUGH SCORES 0 HERE, NOT 100, and this docstring used to say the
    opposite. F1.3 made an OUT leaf carrying no substitute `unmasked`, and
    every form and value line counts that as a miss inside the denominator —
    so «the tool got the real value» stopped being the question: the question
    is whether the gateway PUT it there. Measured on the production observer:
    a gateway that masks nothing prints 0/2 (`report --selftest`'s
    `end_to_end` mutant is that old promise, written out).

    The consequence is stated rather than hidden: this line and `leak` are no
    longer independent halves of the promise — one masking failure now shows
    in both, and a reader comparing them must read them as one picture."""
    hits = 0
    total = 0
    for one, hop in _owned(observations, "OUT", ("tool_arg",)):
        if not hop.declared:
            continue
        total += 1
        item = _item_of(one, hop.hop.item_id)
        hits += 1 if (hop.status == "observed" and item is not None
                      and _item_value_ok(hop, item)) else 0
    return _line("end_to_end", hits, total)


def overmask(observations: Sequence[RunObservation]) -> Line:
    """Negatives that survived. Recall without precision is bought by one line
    that masks everything, so this line is scored as hard as `leak`."""
    hits = 0
    total = 0
    for one in observations:
        for negative in one.case.base.negatives:
            total += 1
            spans = one.run.base.masked_spans.get(negative.msg, ())
            covered = any(start < negative.end and negative.start < end for start, end in spans)
            hits += 0 if covered else 1
    return _line("overmask", hits, total)


def _places_of(mentions: Sequence[MentionRecord]) -> set[tuple[int, int]]:
    """The distinct PLACES the model met a value in: a message by its index, a
    tool result by its sequence number.

    THE RESULT IS A PLACE, AND SAYING OTHERWISE EMPTIED THE LINE. The harness
    writes `msg == -1` for every tool-result mention (`harness.push_call`), so
    a population keyed on `msg` alone collapsed every result the model ever
    read into ONE place — and since no corpus item is BOTH said in a message
    and echoed by a tool, `consistency` had an EMPTY population on all 1 736
    cases and could print nothing but «н/п». A line that can only print «н/п»
    is the instrument that cannot fail, which is the one thing this benchmark
    refuses. A value printed in two different tool results was met in two
    places by any reading of the word.

    COUNTING MENTIONS INSTEAD WOULD PRINT THE SAME NUMBER, and that is a
    property of the RECORD rather than a second rule: the harness writes at
    most one mention per item per message and `contracts` allows one tag per
    item per result («the FIRST rendering»), so a place holds one mention. The
    place is still what is counted, because a record that ever wrote two
    mentions for one place would otherwise put a value the model met ONCE into
    a population named «met more than once»."""
    return {(mention.msg, mention.result_seq) for mention in mentions}


def consistency(observations: Sequence[RunObservation]) -> Line:
    """One value, one substitute, across the PLACES the model met it — the
    messages it was said in and the tool results that printed it. The model has
    to believe the second mention is the same person, and it cannot if the
    gateway re-minted.

    THE POPULATION IS DISTINCT PLACES, NOT MENTIONS: counting mentions would
    put a value said once into a population named «met more than once».
    `stability` asks the neighbouring question of REQUESTS, and
    `multi_consistency` of the calls of one turn."""
    hits = 0
    total = 0
    for one in observations:
        for item in one.case.base.pii:
            mentions = _mentions_of(one, item.id)
            if len(_places_of(mentions)) < 2:
                continue
            total += 1
            hits += 1 if len({mention.substitute for mention in mentions}) == 1 else 0
    return _line("consistency", hits, total)


def stability(observations: Sequence[RunObservation]) -> Line:
    """The substitute did not change between REQUESTS, over EVERY item of the
    corpus. A growing transcript re-sends the first message every turn; a
    substitute that moves turns one person into several in the model's
    context. `memory_stability` asks the same question of the items a
    `MemorySpec` names — a different population, and the reason the two lines
    are two lines (they were one function under two names)."""
    hits = 0
    total = 0
    for one in observations:
        for item in one.case.base.pii:
            mentions = _mentions_of(one, item.id)
            if len({mention.request_index for mention in mentions}) < 2:
                continue
            total += 1
            hits += 1 if len({mention.substitute for mention in mentions}) == 1 else 0
    return _line("stability", hits, total)


def rewrite_ratio_v5(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC, AND NOT THE PUBLIC LINE OF THE SAME NAME. How often the
    gateway arm's REPLY is a different text from the control's. Counted from
    `ArmRunV5.control_reply`, never from `ic`: the v4 verdicts are None on
    every fixture by contract, and a diagnostic that can only fire on a live
    run is a diagnostic the gate must refuse.

    `agentmask_ru.align.rewrite_ratio` measures another quantity entirely —
    the share of characters the MASKING changed in the message the model
    reads, OUTSIDE the protected spans, flagged above 0.3 — and it is not
    computable from a v5 record (the masked message text is not kept, only
    its spans). Two numbers under one name would be read as one, so the name
    carries the version."""
    hits = 0
    total = 0
    for one in observations:
        control, gateway = one.run.control_reply, one.run.base.reply
        if not control or not gateway:
            continue
        total += 1
        hits += 1 if difflib.SequenceMatcher(None, control, gateway).ratio() < REWRITE_RATIO_FLOOR else 0
    return _line("rewrite_ratio_v5", hits, total)


def shared_block_answer(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC. ANSWER spans the alignment could not assign to ONE item —
    «Кудрявцевой Диане» rewritten as one block. Not a defect on its own; it is
    the warning that every per-item number over those spans is an attribution,
    and the report says so rather than letting a reader assume otherwise.

    The public harness's `unattributable` counts ITEMS with a tool parameter
    whose substitute it could not place, and uses the answer to decide nothing
    — a different unit on a different leg, so this line does not wear its
    name."""
    hits = 0
    total = 0
    for one in observations:
        for span in answer_spans(one.case, one.run):
            total += 1
            hits += 1 if len(set(span.item_ids)) > 1 else 0
    return _line("shared_block_answer", hits, total)


# --- §4.3 the v5 lines -----------------------------------------------------------------

def form_hIN(observations: Sequence[RunObservation]) -> Line:  # noqa: N802 - the metric's name
    """Did the SUBSTITUTE wear the source's form. Declared and undeclared hops
    both: a crossing is a crossing whether or not the case foresaw it."""
    rows = [hop for _one, hop in _hops(observations, "IN") if hop.status == "observed"]
    return _line("form_hIN", sum(1 for hop in rows if hop.verdict is not None and hop.verdict.same), len(rows))


def form_hOUT(observations: Sequence[RunObservation]) -> Line:  # noqa: N802 - the metric's name
    """Did the REAL value come back in the AGENT's form — the form read off the
    agent's own output, never a canonical the benchmark chose.

    OVER THE OUT HOPS THE AGENT WROTE, which is `observed` ∪ `unmasked` and
    not «all declared tool arguments» as this docstring used to promise. An
    `unmasked` leaf carried no substitute, so there was nothing to restore and
    the comparison was of a string with itself — a MISS, in the denominator,
    never a hit. An `absent` leaf was never written at all: it is a fact about
    the AGENT and it is printed on its own line (`out_absent`), because a
    denominator that shrinks when the agent does less work is the v4 D3
    defect and a denominator that grows with it flatters a gateway that
    protected nothing."""
    rows = [hop for _one, hop in _hops(observations, "OUT")
            if hop.status in ("observed", "unmasked")]
    return _line("form_hOUT", sum(1 for hop in rows if hop.verdict is not None and hop.verdict.same), len(rows))


def out_absent(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC, printed BESIDE `form_hOUT`: declared OUT hops the agent
    never wrote. It is the number `form_hOUT` leaves out of its denominator,
    and without it a reader cannot tell a gateway that kept every form from an
    agent that wrote almost nothing."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.declared]
    return _line("out_absent", sum(1 for hop in rows if hop.status == "absent"), len(rows))


def _span_masked(record: ToolResultRecord, item: PiiItem, span: tuple[int, int]) -> bool:
    """The slot was replaced AND no piece of what stood there survives anywhere
    in the text the model read.

    The span check alone was blind to the second rendering: `contracts` says
    «ONE tag per item per result — the FIRST rendering … leak checks read the
    whole text, so a second rendering can never hide a leak», and the code
    read the tagged span only. A statement that prints the holder on every row
    tags row one; the rest of the customer's name went to the model with a
    clean bill of health.

    THE ITEM AND NOT ITS TYPE, because the piece test is `observe.
    item_survives_in` and that asks the corpus's own roles (contracts §4bis,
    N4): a declared settlement is dropped by name, which a split of the
    rendered surface could not do."""
    if covering_piece(record, span) is None:
        return False
    return not item_survives_in(item, record.text_real[span[0]:span[1]], record.text_masked)


def _record_clean(record: ToolResultRecord, items: dict[str, PiiItem]) -> bool:
    """Every TAGGED slot of this result was masked, pieces included."""
    for tag, span in record.spans_real.items():
        owner = _tagged_item(items, tag)
        if owner is None or not _span_masked(record, owner, span):
            return False
    return True


def toolresult_masked(observations: Sequence[RunObservation]) -> Line:
    """Tool results where not one real value reached the model. The leg v4 could
    not score at all: its `ArmRun` kept no result text, so a mock that answered
    with the customer's real phone was invisible to every level.

    THE DENOMINATOR IS WHAT THE CASE DECLARES, NEVER WHAT THE MOCK HAPPENED TO
    TAG. `[record for record in tool_results if record.spans_real]` left out
    every result the mock tagged nothing in — 540 of 2 483 results on the
    revised half carried a real seed value with zero tags, so 39% of the
    results that actually hold personal data were outside the line that exists
    to score them. `returns[].result_item_ids` is the corpus's own statement of
    which result carries which datum; a declared value the result renders
    untagged is a MISS (the mock dropped the tag or the case declared a
    crossing that does not happen — F4.1 makes that provable at build time), a
    declared result the agent never obtained is outside the denominator, the
    way an `absent` hop is."""
    hits = 0
    total = 0
    for one in observations:
        items = items_by_id(one.case)
        for expect in one.case.returns:
            record = next((got for got in one.run.tool_results
                           if got.tool_name == expect.tool_name
                           and got.call_ordinal == expect.call_ordinal), None)
            if record is None:
                continue
            total += 1
            declared = all(
                item_id in items and span_of_item(record, item_id) is not None
                and _span_masked(record, items[item_id], span_of_item(record, item_id))
                for item_id in expect.result_item_ids)
            hits += 1 if declared and _record_clean(record, items) else 0
    return _line("toolresult_masked", hits, total)


def answer_real(observations: Sequence[RunObservation]) -> Line:
    """Answers where every datum is the REAL value in the agent's own form.
    One observation is one answer: an answer with four data and one substitute
    left in it is not 3/4 right, it is wrong, and the customer sees it.

    THE VALUE IS CHECKED, NOT ONLY THE FORM AND THE RESIDUAL. For 713 of the
    corpus's cases this line could fail in exactly one way — a `residual`
    status — so a wrong value in the answer was invisible and an answer naming
    no personal datum at all scored a hit: v4's «all() over an empty list»,
    reborn on the answer leg.

    THE VALUE TEST IS `answer_value_ok`, NOT EQUALITY WITH THE CANONICAL, and
    that is not leniency — the whole-canonical comparison could not be earned.
    A Russian answer DECLINES the name («передал Ивановой Елене»), names the
    street without the city and re-notates the phone; the needles the observer
    already owns say whether the value is there, and another person's value in
    the same span says it is the wrong one. Only the REQUIRED hops are judged:
    an optional answer hop is one the case does not oblige the agent to make.
    Whether the answer wears the AGENT's form is the verdict's question, and it
    is asked right beside it."""
    hits = 0
    total = 0
    for one in observations:
        rows = [hop for hop in one.hops
                if hop.declared and hop.hop.kind == "OUT" and hop.hop.owner == "answer"]
        if not rows:
            continue
        total += 1
        required = [hop for hop in rows if not hop.hop.optional]
        good = all(_answer_hop_right(one, hop) for hop in required)
        left_over = any(hop.status == "residual" for hop in rows) or bool(
            residual_answer_items(one.case, one.run))
        hits += 1 if good and not left_over else 0
    return _line("answer_real", hits, total)


def _occurrences(item: PiiItem, text: str) -> tuple[tuple[int, int], ...]:
    """Where this item's value stands in `text`, in every shape `needles_of`
    knows — verbatim, declined, renotated, refolded."""
    return tuple(span for surface in (item.canonical, item.value) if surface
                 for span in occurrences_of(item.type, surface, text))


def answer_value_ok(one: RunObservation, item: PiiItem, produced: str) -> bool:
    """Did the ANSWER carry THIS item's value.

    NOT the whole canonical, byte for byte — that rule is the F1.1 defect the
    tool leg was rid of, left standing here, and it is worse on this leg. A
    Russian answer names the PART it needs and declines it: «Передал
    Ивановой» for «Иванова Елена Петровна», «Курьер поедет на Клубную 85» for
    «Ижевск, улица Клубная, 85, кв 14». Measured over the corpus's own 797
    required answer hops, 530 (66%) of ORDINARILY DECLINED correct answers
    failed the old comparison, and a perfect gateway could not earn the line.

    THE RULE IS THE OBSERVER'S OWN NEEDLES (`observe.needles_of`) — the word
    stem, the digit signature, the date fold — asked of the item's canonical
    and of its surface. A PARTIAL mention is not a wrong value: naming the
    street without the city, or the surname without the given name, is what
    the answer was asked for, and the corpus cannot demand information the
    reply never carried (AgentPII-RU v1's ground-truth bug, `CLAUDE.md`).

    A MENTION OF ANOTHER PERSON'S VALUE IS a wrong value, and that is the half
    that keeps the line able to fail. «Another person» is an item of the case
    with a DIFFERENT identity whose value stands where this item's does not —
    the position matters because two identities may share a given name, and a
    correct answer must not be called wrong for the name it got right."""
    if not produced.strip():
        return False
    mine = _occurrences(item, produced)
    if not mine:
        return False
    for other in one.case.base.pii:
        if other.id == item.id or other.identity == item.identity:
            continue
        for span in _occurrences(other, produced):
            if not any(one_span[0] < span[1] and span[0] < one_span[1] for one_span in mine):
                return False
    return True


def _answer_hop_right(one: RunObservation, hop: HopObservation) -> bool:
    item = _item_of(one, hop.hop.item_id)
    return (hop.status == "observed" and hop.verdict is not None and hop.verdict.same
            and item is not None and answer_value_ok(one, item, hop.produced))


def _transitions(observations: Sequence[RunObservation]) -> list[tuple[RunObservation, HopObservation, HopObservation]]:
    """A→B: a declared OUT hop ON A TOOL whose `source_hop` points at an
    IN/tool hop of ANOTHER tool. «Another» is the whole content of the chain
    family — a tool fed its own result back would be measuring nothing.

    B IS AN ACT ON A TOOL, NEVER THE ANSWER. The corpus declares `source_hop`
    on answer hops too, and 3 870 of the 6 880 transitions that matched were
    «the agent told the customer what the tool said» — 56% of a denominator
    named «A→B transitions». `contracts.ACTING_OUT_OWNERS` is the closed list
    and the corpus rules read the same one."""
    out: list[tuple[RunObservation, HopObservation, HopObservation]] = []
    for one in observations:
        for hop in one.hops:
            if not (hop.declared and hop.hop.kind == "OUT" and hop.hop.source_hop != -1):
                continue
            if hop.hop.owner not in contracts.ACTING_OUT_OWNERS:
                continue
            source = _declared_hop(one, hop.hop.source_hop)
            if source is None or source.hop.kind != "IN" or source.hop.owner != "tool":
                continue
            if source.hop.tool_name == hop.hop.tool_name:
                continue
            out.append((one, hop, source))
    return out


def chain_value(observations: Sequence[RunObservation]) -> Line:
    """Did the value survive the hand-over: the real value B received equals the
    real value A returned, and the two hops are the SAME identity. Identity is
    checked because a chain that carried another person's value of the same type
    looks identical on the value axis and is the worst failure the product has."""
    rows = _transitions(observations)
    hits = 0
    for one, hop, source in rows:
        left, right = _item_of(one, hop.hop.item_id), _item_of(one, source.hop.item_id)
        same_identity = left is not None and right is not None and left.identity == right.identity
        arrived = right is not None and leaf_value_ok(
            returned_as_item(right, source.reference),
            hop.hop.tool_name, hop.hop.path, hop.produced)
        hits += 1 if (hop.status == "observed" and same_identity and arrived) else 0
    return _line("chain_value", hits, len(rows))


def chain_form(observations: Sequence[RunObservation]) -> Line:
    """Same population, the other question: did B receive it in the AGENT's
    form. A tool's canon leaking through the agent into the next tool is the
    failure this line exists to name."""
    rows = _transitions(observations)
    hits = sum(1 for _one, hop, _source in rows
               if hop.status == "observed" and hop.verdict is not None and hop.verdict.same)
    return _line("chain_form", hits, len(rows))


def _multi_turns(observations: Sequence[RunObservation]) -> list[tuple[RunObservation, int, list[HopObservation]]]:
    out: list[tuple[RunObservation, int, list[HopObservation]]] = []
    for one in observations:
        turns: dict[int, list[HopObservation]] = {}
        for hop in one.hops:
            if (hop.declared and hop.hop.kind == "OUT" and hop.hop.owner == "tool_arg"
                    and not hop.hop.optional):
                turns.setdefault(hop.hop.turn, []).append(hop)
        for turn, rows in sorted(turns.items()):
            if len(rows) >= 2:
                out.append((one, turn, rows))
    return out


def multi_all_out(observations: Sequence[RunObservation]) -> Line:
    """Turns where EVERY argument is right in value and in form. ORDER IS NOT A
    CONDITION: a model that books the second parcel first has not broken the
    customer's data, and scoring the permutation would make the line a measure
    of the model's taste rather than of the gateway."""
    rows = _multi_turns(observations)
    hits = 0
    for one, _turn, hops in rows:
        good = True
        for hop in hops:
            item = _item_of(one, hop.hop.item_id)
            if not (hop.status == "observed" and hop.verdict is not None and hop.verdict.same
                    and item is not None and _item_value_ok(hop, item)):
                good = False
        hits += 1 if good else 0
    return _line("multi_all_out", hits, len(rows))


def same_substitute(pii_type: str, left: str, right: str) -> bool:
    """Two spellings of ONE mint. «Пахомова Ольга» and «Пахомовой Ольге» are
    one substitute read twice; «Смирнова Анна» is a second mint."""
    if fold(left.strip()) == fold(right.strip()):
        return True
    own = {needle.text for needle in value_needles(pii_type, left) if needle.role}
    theirs = {needle.text for needle in value_needles(pii_type, right) if needle.role}
    return bool(own & theirs)


def multi_consistency(observations: Sequence[RunObservation]) -> Line:
    """Turns where one value got ONE substitute across all the calls of the
    turn. Read off what the agent WROTE, so a second substitute the gateway
    minted for the second call is visible even when both calls parse.

    COUNTED BY THE MINT, NOT BY THE SPELLING. `substitute_surfaces`
    deliberately returns every spelling the model READ of one substitute, so
    an agent that wrote the nominative into a name field and the dative into a
    free-text note of the same turn — ordinary Russian, and exactly what the
    gateway promises to allow — was counted as two substitutes and the turn
    failed. A spelling belongs to the mint it shares a stem, a digit signature
    or a date fold with; only one that shares none is a second substitute."""
    hits = 0
    total = 0
    for one in observations:
        turns = sorted({turn for turn in one.run.call_turns})
        for turn in turns:
            calls = calls_of_turn(one.run, turn)
            if len(calls) < 2:
                continue
            total += 1
            good = True
            own = own_stems(one.case)
            for item in one.case.base.pii:
                minted = one.run.base.substitutes.get(item.id)
                mint = minted[0] if minted is not None else ""
                seen: set[str] = set()
                for _index, call in calls:
                    for spelling in substitute_surfaces(one.run, item.id):
                        if not spelling or not any(survives_in(item.type, spelling, text, own)
                                                   for text in _written_texts(call.written)):
                            continue
                        seen.add(mint if mint and same_substitute(item.type, spelling, mint)
                                 else fold(spelling))
                if len(seen) > 1:
                    good = False
            hits += 1 if good else 0
    return _line("multi_consistency", hits, total)


def _written_texts(written: dict[str, object]) -> list[str]:
    return [value for value in flatten(written).values() if isinstance(value, str)]


def _retries(observations: Sequence[RunObservation]) -> list[tuple[RunObservation, int, str, list[HopObservation]]]:
    """(observation, turn, tool) where the tool was called twice in one turn and
    something REFUSED the earlier attempt — a scripted `ForcedError` or the
    mock's own refusal. Without that condition a model that simply called twice
    would be counted as a retry and the family's denominator would be the
    model's mood."""
    out: list[tuple[RunObservation, int, str, list[HopObservation]]] = []
    for one in observations:
        for turn in sorted({turn for turn in one.run.call_turns}):
            calls = calls_of_turn(one.run, turn)
            names = {call.name for _index, call in calls}
            for name in sorted(names):
                attempts = [call for _index, call in calls if call.name == name]
                if len(attempts) < 2:
                    continue
                forced = any(error.tool_name == name for error in one.case.forced)
                refused = any(call.refusal_rule for call in attempts[:-1])
                if not (forced or refused):
                    continue
                hops = [hop for hop in one.hops
                        if hop.declared and hop.hop.kind == "OUT" and hop.hop.tool_name == name
                        and hop.hop.turn == turn]
                out.append((one, turn, name, hops))
    return out


def retry_form(observations: Sequence[RunObservation]) -> Line:
    """Retries where the form matched the agent's own on EVERY attempt —
    including the attempt where the agent changed its mind and wrote «8 916…»
    after «+7 916…». Following the agent is the promise; following the first
    attempt only is a gateway that stopped listening."""
    rows = _retries(observations)
    hits = sum(1 for _one, _turn, _name, hops in rows
               if hops and all(hop.status == "observed" and hop.verdict is not None
                               and hop.verdict.same for hop in hops))
    return _line("retry_form", hits, len(rows))


def memory_consistency(observations: Sequence[RunObservation]) -> Line:
    """A value mentioned at turn 1 and needed at turn 7 kept ONE substitute.
    An anaphoric recall says no value, so it leaves no mention: the item still
    counts once, judged on the mentions it does have."""
    hits = 0
    total = 0
    for one in observations:
        for spec in one.case.memory:
            total += 1
            seen = {mention.substitute for mention in _mentions_of(one, spec.item_id)}
            hits += 1 if len(seen) == 1 else 0
    return _line("memory_consistency", hits, total)


def memory_stability(observations: Sequence[RunObservation]) -> Line:
    """The substitute of a value the case asks the agent to REMEMBER did not
    change between requests of one conversation. A new conversation is a new
    observation and a new substitute there is the conversation scope working,
    never a miss — which is why the population is per observation and never
    pooled across them.

    ITS OWN POPULATION: the items a `MemorySpec` names. This function and
    `stability` were one body under two names — same code, same counters, same
    fixtures' answers — and a report printing one number twice under two
    headings tells a reader there are two pieces of evidence. `stability` asks
    it of EVERY item of the corpus; this line asks it of the values a long
    dialogue has to carry, which is the family the line was written for, and
    where a re-mint between requests actually costs the agent its memory."""
    hits = 0
    total = 0
    for one in observations:
        for spec in one.case.memory:
            mentions = _mentions_of(one, spec.item_id)
            if len({mention.request_index for mention in mentions}) < 2:
                continue
            total += 1
            hits += 1 if len({mention.substitute for mention in mentions}) == 1 else 0
    return _line("memory_stability", hits, total)


def _rag_chunks(one: RunObservation) -> list[tuple[ToolResultRecord, str, list[tuple[int, int]]]]:
    """(record, chunk id, spans) for each chunk the case's `RagSpec` names. A
    chunk is a SEED RECORD rendered into the result, so its spans are the slots
    of the items that record carries — the mock's own tags, never a split of the
    text by eye."""
    if one.case.rag is None:
        return []
    items = items_by_id(one.case)
    out: list[tuple[ToolResultRecord, str, list[tuple[int, int]]]] = []
    for record in one.run.tool_results:
        if record.tool_name != one.case.rag.tool_name:
            continue
        for chunk_id in one.case.rag.chunk_ids:
            spans = [span for tag, span in sorted(record.spans_real.items())
                     if _tagged_item(items, tag) is not None
                     and _tagged_item(items, tag).where.record == chunk_id]
            out.append((record, chunk_id, spans))
    return out


def _tagged_item(items: dict[str, PiiItem], tag: str) -> PiiItem | None:
    return items.get(tag.removeprefix(contracts.ECHO_TAG_PREFIX))


def _chunk_items(one: RunObservation, chunk_id: str) -> list[PiiItem]:
    """The case's own items that this chunk RENDERS — the seed record's items,
    read off the corpus declaration (`Locus.record`) and never off the mock's
    tags. The declaration is the point: a chunk the mock rendered with no tag
    at all must still be a unit, or «the retriever leaked» and «the retriever
    was never called» print the same number."""
    return [item for item in one.case.base.pii
            if item.where.kind == "seed" and item.where.record == chunk_id]


def _obtained(records: Sequence[ToolResultRecord],
              declared: Sequence[PiiItem]) -> list[ToolResultRecord]:
    """The results that actually carry this chunk or document: a tagged slot
    for one of its declared items, or one of their real values standing in the
    text the model read.

    THE SECOND HALF IS WHAT SEPARATES «rendered untagged» FROM «never
    returned». Without it the two are one state, and F1.7's rule — a declared
    value the result renders untagged is a MISS, a declared result the agent
    never obtained is outside the denominator — cannot be applied at all."""
    return [record for record in records
            if any(span_of_item(record, item.id) is not None
                   or item_survives_in(item, item.value, record.text_masked)
                   for item in declared)]


def rag_masked(observations: Sequence[RunObservation]) -> Line:
    """Retrieval chunks where no real value reached the model — including the
    values of OTHER people the retriever happened to return. A chunk with two
    identities and one of them masked is a miss, not a half.

    THE DENOMINATOR IS WHAT THE CASE DECLARES (F1.7, the half that had been
    applied to `toolresult_masked` only). `if not spans: continue` made «the
    chunk came back untagged» indistinguishable from «the chunk never came
    back», so a declared chunk the mock rendered RAW — the customer's name in
    the model's context, tagged by nothing — left the denominator entirely and
    the line printed «н/п» for a retrieval leg that leaked."""
    hits = 0
    total = 0
    for one in observations:
        if one.case.rag is None:
            continue
        items = items_by_id(one.case)
        results = [record for record in one.run.tool_results
                   if record.tool_name == one.case.rag.tool_name]
        for chunk_id in one.case.rag.chunk_ids:
            declared = _chunk_items(one, chunk_id)
            if not declared:
                continue
            obtained = _obtained(results, declared)
            if not obtained:
                continue
            total += 1
            good = True
            for record in obtained:
                for item in declared:
                    span = span_of_item(record, item.id)
                    if span is None:
                        # Declared, returned, and tagged by nothing: the value
                        # is in the text the model read, so it is a MISS — the
                        # `all([]) == True` v4 defect, on the retrieval leg.
                        if item_survives_in(item, item.value, record.text_masked):
                            good = False
                        continue
                    if not _span_masked(record, item, span):
                        good = False
                # Every OTHER tagged slot of this chunk counts too: the
                # retriever returns whole rows and a foreign person in one is
                # exactly what this line must not forgive.
                for tag, span in record.spans_real.items():
                    owner = _tagged_item(items, tag)
                    if owner is None or owner.where.record != chunk_id:
                        continue
                    if not _span_masked(record, owner, span):
                        good = False
            hits += 1 if good else 0
    return _line("rag_masked", hits, total)


def _type_at(record: ToolResultRecord, items: dict[str, PiiItem], span: tuple[int, int]) -> str:
    """The declared type of the item this slot renders. Read off the tag, never
    guessed from the text: the chunk holds several people and the piece check
    must split the right value into the right parts."""
    for tag, other in record.spans_real.items():
        owner = _tagged_item(items, tag)
        if other == span and owner is not None:
            return owner.type
    return ""


def rag_identity_kept(observations: Sequence[RunObservation]) -> Line:
    """Foreign identities in the chunks kept APART from the customer.

    Two ways to fail, and both are checked: the foreign person's real value
    reaching a tool argument written for the customer, and the customer's own
    substitute standing where the foreign value stood — the gateway deciding
    two people are one."""
    hits = 0
    total = 0
    for one in observations:
        if one.case.rag is None:
            continue
        items = items_by_id(one.case)
        customer = one.case.base.expects.primary_identity
        own_subs = {spelling for item in one.case.base.pii if item.identity == customer
                    for spelling in substitute_surfaces(one.run, item.id) if spelling}
        out_values = [hop.produced for hop in one.hops
                      if hop.hop.kind == "OUT" and (_item_of(one, hop.hop.item_id) is not None
                                                    and _item_of(one, hop.hop.item_id).identity == customer)]
        for identity in one.case.rag.foreign_identities:
            total += 1
            foreign = [item for item in one.case.base.pii if item.identity == identity]
            bled = any(fold(item.value) in fold(text) for item in foreign for text in out_values if text)
            merged = False
            for record in one.run.tool_results:
                for tag, span in record.spans_real.items():
                    owner = _tagged_item(items, tag)
                    if owner is None or owner.identity != identity:
                        continue
                    piece = covering_piece(record, span)
                    if piece is not None and piece[2] in own_subs:
                        merged = True
            hits += 0 if (bled or merged) else 1
    return _line("rag_identity_kept", hits, total)


def doc_masked(observations: Sequence[RunObservation]) -> Line:
    """Documents where every real value was masked. One document is one unit:
    a CSV whose fourth row leaked is a leaked document, and a per-row rate would
    let a hundred clean rows pay for it.

    THE VERDICT IS WHAT THE CASE DECLARES (F1.7, the half that had been applied
    to `toolresult_masked` only). `all(_record_clean(...))` iterates
    `record.spans_real`, so a document the mock rendered with NO tags iterated
    nothing and scored a perfect hit — v4's «all() over an empty list», on the
    document family, and reachable today: the agent reads a wrong path,
    `mock._file_read` answers `{"found": false}`, the record carries no tag,
    and «every real value of this document was masked» is printed about a
    document nobody read.

    So a declared value that reached the model UNTAGGED is now a miss, and a
    document the agent never obtained leaves the denominator instead of
    scoring one — the same two rules `toolresult_masked` follows, with
    `doc_extracted` printing the zero beside an unread document."""
    hits = 0
    total = 0
    for one in observations:
        document = one.case.document
        if document is None:
            continue
        items = items_by_id(one.case)
        declared = [item for item in one.case.base.pii
                    if (item.where.kind == "seed" and item.where.record in document.record_ids)
                    or item.id in document.extracted_item_ids]
        records = [record for record in one.run.tool_results
                   if record.tool_name == document.read_tool]
        obtained = _obtained(records, declared or list(one.case.base.pii))
        if not obtained:
            continue
        total += 1
        good = all(_record_clean(record, items) for record in obtained)
        for record in obtained:
            for item in declared or one.case.base.pii:
                if span_of_item(record, item.id) is not None:
                    continue
                if item_survives_in(item, item.value, record.text_masked):
                    good = False
        hits += 1 if good else 0
    return _line("doc_masked", hits, total)


def doc_extracted(observations: Sequence[RunObservation]) -> Line:
    """Values the agent lifted OUT of the document and into the tool, counted
    on whether the tool got the real one. The other half of `doc_masked`: a
    document perfectly masked whose values never come back is useless.

    THE POPULATION IS THE EXTRACTION THE CASE DECLARES A HOP FOR, not every id
    in `extracted_item_ids`. Two families name an extracted item the corpus
    gives the agent NOWHERE to put — `document-050` i8 into `bank_client_find`
    and `document-075` i8 into `vehicle_check`, 25 cases each — so 50 of 375
    items had no declared OUT hop into `extract_to_tool` and could not be hits
    whatever the gateway or the agent did: a ceiling of 86.7 %, which is
    exactly what a perfect gateway printed. A denominator with an unreachable
    floor in it is the mirror of v4's D1 («nothing to compare passed»): it
    cannot be earned instead of cannot be failed, and both make the number
    mean something other than what it says.

    IT STAYS ABLE TO FAIL, and that is why the declared HOP and not the
    declared item is the unit: the hop is the case's own statement that this
    value must reach that tool, and an agent that never wrote it leaves the
    hop `absent` — inside the denominator, counted as a miss, exactly like
    every other declared OUT hop. What left is only the item the corpus asks
    nobody to carry. The corpus owner is asked to make the two agree
    (`build --check`: an extracted item with no arg hop into `extract_to_tool`
    is a corpus defect); when they do, this denominator is the other one."""
    hits = 0
    total = 0
    for one in observations:
        if one.case.document is None:
            continue
        for item_id in one.case.document.extracted_item_ids:
            # THE CASE'S OWN DECLARATION decides the denominator, never the
            # hops the observer emitted: an OPTIONAL hop the agent skipped is
            # not emitted at all, so counting emitted hops would let the agent
            # shrink the total by doing less — the v4 D3 defect.
            if not any(hop.kind == "OUT" and hop.item_id == item_id
                       and hop.tool_name == one.case.document.extract_to_tool
                       for hop in one.case.hops):
                continue
            total += 1
            item = _item_of(one, item_id)
            hop = next((one_hop for one_hop in one.hops
                        if one_hop.declared and one_hop.hop.kind == "OUT"
                        and one_hop.hop.item_id == item_id
                        and one_hop.hop.tool_name == one.case.document.extract_to_tool), None)
            hits += 1 if (hop is not None and item is not None and hop.status == "observed"
                          and _item_value_ok(hop, item)) else 0
    return _line("doc_extracted", hits, total)


def residual(observations: Sequence[RunObservation]) -> Line:
    """A substitute that reached a tool or the customer. THE critical defect —
    the tool's JSON is well formed, the status is 200, and a fake is now in the
    customer's CRM. Counted per OUT leaf AND per answer, because an answer with
    no declared hop still reaches a human.

    AN `absent` LEAF IS IN NEITHER HALF. It is not a leaf: nothing was written
    there, so it cannot hold a fake, and counting it as clean printed 4/4 for
    an agent that called nothing at all — the critical-defect line certifying
    a run in which nothing happened.

    An `unmasked` leaf IS clean here, and the exception is deliberate: the
    agent wrote the real value because the gateway never minted a substitute,
    so no fake reached the consumer. That failure is `leak`'s to report, and
    making this line fire on it would mean two lines for one defect and a
    `residual` number that no longer means what it says. Everywhere a FORM or
    a VALUE is asked of an OUT hop, `unmasked` is a miss.

    AN EARLIER TURN COUNTS TOO (R-54). `ArmRunV5.turn_residual` is how many of
    the agent's own earlier turns still held a minted substitute when the judge
    prompt was built — the customer read those turns, and a fake that stood in
    turn 2 and not in the final answer reached a human just as surely. The
    number was written on the triple row, where no metric could read it, so the
    defect was counted nowhere; here it is a miss of the observation, in the
    same term as the answer, because it is the same defect one turn sooner."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.status != "absent"]
    hits = sum(1 for hop in rows if hop.status != "residual")
    for one in observations:
        clean = (not any(hop.hop.kind == "OUT" and hop.hop.owner == "answer"
                         and hop.status == "residual" for hop in one.hops)
                 and not residual_answer_items(one.case, one.run)
                 and one.run.turn_residual == 0)
        hits += 1 if clean else 0
    return _line("residual", hits, len(rows) + len(observations))


def stream_fidelity(observations: Sequence[RunObservation]) -> Line:
    """Streaming cases where the chunked restoration equals the whole-text one.

    The harness restores a streaming reply twice — whole (`unmask_text`) and
    chunk by chunk through the sidecar's own `StreamDetokenizer` — and wrote
    the disagreement into `ArmRunV5.stream_mismatch` on all 84 streaming
    cases, where NO metric and no report line ever read it. The product's
    streaming leg was measured and the measurement was thrown away. The
    population is the streaming cases, so a corpus without them prints «н/п»
    rather than a perfect score nobody earned."""
    rows = [one for one in observations if one.case.streaming]
    return _line("stream_fidelity", sum(1 for one in rows if not one.run.stream_mismatch), len(rows))


METRIC_FUNCTIONS: dict[str, Metric] = {
    "leak": leak, "coverage": coverage, "typed": typed, "round_trip": round_trip,
    "round_trip_repaired": round_trip_repaired, "end_to_end": end_to_end, "overmask": overmask,
    "consistency": consistency, "stability": stability, "rewrite_ratio_v5": rewrite_ratio_v5,
    "shared_block_answer": shared_block_answer,
    "form_hIN": form_hIN, "form_hOUT": form_hOUT, "out_absent": out_absent,
    "toolresult_masked": toolresult_masked,
    "answer_real": answer_real, "chain_value": chain_value, "chain_form": chain_form,
    "multi_all_out": multi_all_out, "multi_consistency": multi_consistency,
    "retry_form": retry_form, "memory_consistency": memory_consistency,
    "memory_stability": memory_stability, "rag_masked": rag_masked,
    "rag_identity_kept": rag_identity_kept, "doc_masked": doc_masked,
    "doc_extracted": doc_extracted, "residual": residual, "stream_fidelity": stream_fidelity,
}

# WHICH LINES A HOP AXIS MAY PRINT. `by_axis` on a hop axis hands every bucket
# a COPY of the observation carrying only that bucket's hops — so a metric that
# builds its denominator from `one.run` or `one.case` instead of from
# `one.hops` counts the same answer, the same turn or the same document once
# per bucket, and the column sums to more units than the corpus holds. The
# criterion is mechanical and `test_metrics.test_hop_axis_totals_sum` runs it:
# the bucket totals of a sliceable line must add up to the whole line's total.
# `residual` is NOT here although it reads hops — it adds one answer term per
# observation, and that term would be counted in every bucket.
# `round_trip`, `round_trip_repaired` and the `chain_*` pair are NOT here
# although they iterate hops: their denominator is built from a PAIR of hops —
# an OUT leaf and the IN hop that fed it — and a hop axis puts the two in
# different buckets (`IN/user` and `OUT/tool_arg`), so the pair dissolves and
# the bucket totals add up to less than the line's own.
HOP_SLICEABLE: frozenset[str] = frozenset({
    "leak", "coverage", "typed", "end_to_end", "form_hIN", "form_hOUT", "out_absent"})
AXIS_NOTE: str = "по хоповой оси не печатается: знаменатель — не хопы"


def prints_on_axis(metric: str, axis: str) -> bool:
    """May this line be printed inside a bucket of `axis`? An observation-level
    line on a hop axis must be left out with `AXIS_NOTE` beside it, never
    printed per bucket."""
    return metric in HOP_SLICEABLE if axis in HOP_AXES else True


# --- the axes --------------------------------------------------------------------------

def _cue_bucket(one: RunObservation, hop: HopObservation) -> str:
    item = _item_of(one, hop.hop.item_id)
    if item is None or item.where.kind != "message" or item.where.msg < 0:
        return "нет"
    if item.where.msg >= len(one.case.base.messages):
        return "нет"
    text = fold(one.case.base.messages[item.where.msg].content)
    window = text[max(0, item.where.start - CUE_WINDOW):item.where.end + CUE_WINDOW]
    return "есть" if any(word in window for word in CUE_WORDS) else "нет"


def _return_form_bucket(one: RunObservation, hop: HopObservation) -> str:
    if hop.hop.kind == "IN" and hop.hop.owner in ("tool", "document"):
        record = result_for_hop(one.run, hop.hop)
        return record.return_form if record is not None else "—"
    declared = [expect.return_form for expect in one.case.returns
                if expect.tool_name == hop.hop.tool_name]
    return declared[0] if declared else "—"


def _hop_bucket(axis: str, one: RunObservation, hop: HopObservation) -> str:
    if axis == "vertical":
        return contracts.TOOL_VERTICAL.get(hop.hop.tool_name, "—")
    if axis == "hop_owner":
        return f"{hop.hop.kind}/{hop.hop.owner}"
    if axis == "pii_type":
        return hop.pii_type
    if axis == "return_form":
        return _return_form_bucket(one, hop)
    return _cue_bucket(one, hop)


HOP_AXES: tuple[str, ...] = ("vertical", "hop_owner", "pii_type", "return_form", "cue")


def by_axis(observations: Sequence[RunObservation], axis: str) -> dict[str, list[RunObservation]]:
    """One axis at a time, never two crossed — the public harness's rule, for
    the public harness's reason: a cell of eight items has an interval wider
    than any difference worth reading.

    A HOP-level axis splits the HOPS, not the observations: the bucket gets a
    copy of the observation carrying only its own hops, so `form_hOUT` by
    `pii_type` counts NAME hops under NAME and nowhere else, while the run's
    records stay reachable for the metrics that need them."""
    if axis not in contracts.AXES:
        raise ValueError(f"by_axis: {axis!r} is not one of contracts.AXES ({list(contracts.AXES)})")
    buckets: dict[str, list[RunObservation]] = {}
    if axis in HOP_AXES:
        for one in observations:
            split: dict[str, list[HopObservation]] = {}
            for hop in one.hops:
                split.setdefault(_hop_bucket(axis, one, hop), []).append(hop)
            for name, rows in split.items():
                buckets.setdefault(name, []).append(replace(one, hops=tuple(rows)))
        return buckets
    for one in observations:
        if axis == "register":
            name = one.case.base.register
        elif axis == "family":
            name = one.case.base.kind
        elif axis == "behaviour":
            name = one.case.behaviour
        else:
            name = "rare" if one.case.base.provenance.selection == "rare" else "authored"
        buckets.setdefault(name, []).append(one)
    return buckets


def main() -> int:
    from bench.agentpii5.test_metrics import main as run_tests
    return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
