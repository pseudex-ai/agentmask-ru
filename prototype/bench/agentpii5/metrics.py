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
import ipaddress
from collections.abc import Sequence
from dataclasses import replace

from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import Locus, PiiItem
from bench.agentpii4.stats import zero_failure_floor
from bench.agentpii4.tools import FieldSpec, flatten
from bench.agentpii5 import checksum_v6, contracts, pii_types
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
    digits_of,
    fold,
    glyph_fold,
    item_survives_in,
    items_by_id,
    occurrences_of,
    own_stems,
    part_matches,
    result_for_hop,
    span_of_item,
    residual_answer_items,
    substitute_surfaces,
    squeeze,
    survives_in,
    value_needles,
    values_equal,
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

# --- the v6 registry surface (TZ §1.0, §5.5, §6.2, §6.3, §6.5) -------------------
#
# Everything here reads the ONE home (`pii_types`) and never restates a fact it
# owns: the value comparison keyed by `value_notation`, the alias table for
# `typed`/`typed_user`, the `type_class` axis, and the three OD-54 rows. The v5
# path is untouched — a v5 type is not in these branches, so an old-corpus run
# prints the SAME bytes as before (F7).
_SPECS: dict[str, pii_types.TypeSpec] = {t.id: t for t in pii_types.TYPE_REGISTRY}
_TYPE_CLASS: dict[str, str] = {t.id: t.type_class for t in pii_types.TYPE_REGISTRY}
# The v6 report axes (TZ §6.5). Kept OUT of `contracts.AXES`; `by_axis` accepts
# them only when a v6 caller asks, so the old report's `_axis_rows` over
# `contracts.AXES` is unchanged.
V6_AXES: tuple[str, ...] = contracts.V6_AXES
# The tag a v6 result slot wears to mark a NEGATIVE inside a result (TZ §6.3
# `overmask_result`, CQ-11). Mirrors `contracts.ECHO_TAG_PREFIX` for echoes: a
# tag that is not an item id, so the observer never confuses it with a positive.
NEG_TAG_PREFIX: str = "neg:"
# The fixed BIK `gen_v6` mints BANK_ACCOUNT values against (the pair check of
# CBR 515 needs the BIK; there is exactly one in the corpus). Named here rather
# than imported so this module stays a CALLER of `checksum_v6` only (R6-07).
_BANK_ACCOUNT_BIK: str = "049805746"


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
    """Did the consumer receive THE SAME VALUE, whatever notation wrote it.

    A THIN CALLER OF `observe.values_equal`, which reads the closed table
    `contracts.VALUE_NORMALISERS` (SPIKE-Ж, Ж-1). It used to be a SECOND
    implementation — `fold(produced) == fold(target)` with a LOC exception — and
    the choice between it and the needle layer's copy was made by whether a
    leaf's `FieldSpec.role` was empty, so a PLATE written «в 163 оу 23» against
    the canonical «В163ОУ23» read as the gateway's miss on a value the tool's
    own parser had accepted. The LOC exception did not disappear: it is the
    table's `place_roles` reading, and `test_spike_zh` pins that both former
    copies now answer it the same way (they disagreed in BOTH directions).

    THE v6 BRANCH IS ADDITIVE AND LEAVES THE v5 PATH BYTE-FOR-BYTE (SPEC §2.1
    C07: keep_v5 + adopt_v6). A v6 type compares by its registry `value_notation`
    (TZ §5.5, R6-38): digits, a date, a squeezed/glyph-folded spelling, or a
    strict IP address — never a byte comparison, so a substitute with the right
    digits and wrong separators still IS the value. The eleven v5 types are
    `ORIGIN_V5` and fall straight through to `values_equal`, so the old-corpus
    replay prints the same bytes as before (F7). The v6 side is deliberately NOT
    a second LOC branch: the v5 table already answers LOC through `place_roles`,
    and a hand-written copy beside it is exactly the drift class Ж removed."""
    spec = _SPECS.get(pii_type)
    if spec is not None and spec.origin == pii_types.ORIGIN_V6:
        return _v6_value_matches(spec, produced, target)
    return values_equal(pii_type, produced, target)


def _notation_equal(spec: pii_types.TypeSpec, left: str, right: str) -> bool:
    """Two renderings of one v6 value, compared in the notation the registry
    declares (`value_notation`, TZ §5.5). THE LETTERS ENTER for a glyph-folded
    type: a substitution of the SERIES is a miss, the correct series a hit. An
    IPv4 with a leading zero is a DIFFERENT host (`ip_strict`), so the padded
    spelling is a miss even though `octets` still finds it as a LEAK."""
    if not left or not right:
        return False
    notation = spec.value_notation
    if notation == "digits":
        return bool(digits_of(left)) and digits_of(left) == digits_of(right)
    if notation == "date":
        return bool(parts_of("DOB", left)) and parts_of("DOB", left) == parts_of("DOB", right)
    if notation == "squeezed":
        return bool(squeeze(left)) and squeeze(left) == squeeze(right)
    if notation == "glyph_fold":
        return bool(glyph_fold(left)) and glyph_fold(left) == glyph_fold(right)
    if notation == "ip_strict":
        return _ip_strict_equal(left, right)
    return fold(left.strip()) == fold(right.strip())


def _ip_strict_equal(left: str, right: str) -> bool:
    """Strict `ipaddress` equality of both sides (TZ §5.5). `ipaddress` refuses
    a padded IPv4 octet, so «192.168.010.024» is NOT «192.168.10.24» here —
    the value comparison is strict where the `octets` LEAK needle is lenient."""
    try:
        return ipaddress.ip_address(left.strip()) == ipaddress.ip_address(right.strip())
    except ValueError:
        return False


def _v6_value_matches(spec: pii_types.TypeSpec, produced: str, target: str) -> bool:
    """A v6 value compared in its `value_notation` (TZ §5.5, R6-38).

    The by-fields reading needs NO branch of its own: a series and a number
    carried in separate leaves arrive joined with `FIELD_SEP`, and the notation
    fold (digits / squeeze / glyph_fold) drops `FIELD_SEP` and concatenates IN
    ORDER — so the correct assignment folds to the canonical while a swapped
    series/number folds to a different run and is a miss. """
    return _notation_equal(spec, produced, target)


def _checksum_canonical(spec: pii_types.TypeSpec, surface: str) -> str:
    """The surface folded into the shape the published checksum is defined over:
    the internal span separators are dropped (`value_notation` decides which
    fold), so a grouped substitute «7707 5364 …» is validated as its digit run
    and never as the raw string (TZ §6.3 `fake_checksum_invalid`)."""
    notation = spec.value_notation
    if notation == "digits":
        return digits_of(surface)
    if notation == "glyph_fold":
        return glyph_fold(surface)
    if notation == "squeezed":
        return squeeze(surface)
    return surface


def _checksum_valid(spec: pii_types.TypeSpec, surface: str) -> bool:
    """Does `surface` PASS the published checksum the registry names? A caller
    of `checksum_v6` only (R6-07: the arithmetic lives in its two homes); the
    BANK_ACCOUNT key is a (account, BIK) pair, so it takes the fixed corpus BIK.
    """
    canonical = _checksum_canonical(spec, surface)
    if not canonical:
        return False
    if spec.id == "BANK_ACCOUNT":
        return checksum_v6.validate_account(canonical, _BANK_ACCOUNT_BIK)
    try:
        return checksum_v6.validate(spec.id, canonical)
    except KeyError:
        return False


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

    A THIN CALLER OF THE ONE PREDICATE (contracts §4bis, SPIKE-Ж Ж-1). The
    comparison of two renderings of one part belongs to the needle layer —
    `leaf_holds` asks it of a substitute and this line asks it of the real
    value, and two copies of «is this the same part written another way» is
    exactly the shape of the defect round 4 removed. Since class Ж the two
    names call ONE implementation (`observe.values_equal` over
    `contracts.VALUE_NORMALISERS`), so a difference between them can no longer
    be produced by editing one of them. The FORM the leaf wears is
    `form_hOUT`'s question and is not folded in here.

    A v6 part compares by its registry `value_notation` (TZ §5.5, R6-38) — the
    same `_notation_equal` `value_matches` uses, minus the by-fields join: a
    role'd leaf already holds ONE part, so there is nothing to split. The v5
    path stays `part_matches`, untouched, so a v5 type prints the same byte it
    printed before the merge (SPEC §2.1 C07: keep_v5 + adopt_v6)."""
    spec = _SPECS.get(pii_type)
    if spec is not None and spec.origin == pii_types.ORIGIN_V6:
        return _notation_equal(spec, produced, target)
    return part_matches(pii_type, produced, target)


def leaf_value_ok_for_spec(item: PiiItem, spec: FieldSpec | None, produced: str) -> bool:
    """THE PREDICATE, parameterised by the SPEC — «did this leaf receive what it
    asks for».

    IT IS ONE FUNCTION WITH TWO CALLERS AND THAT IS THE WHOLE POINT (SPIKE-Е,
    Е-7). `end_to_end` asks it of a hop, `end_to_end_written` asks it of the
    same hop, and `observe._out_status` asks it to decide between the correct
    real value (`engine_kept` / `not_masked`) and a foreign one
    (`leaf_foreign`). Two copies of «is this the value the tool asked for» is
    exactly the drift R-53 removed: the honest share and the headline would stop
    differing by their population and start differing by their rule.

    THE ROLE PICKS THE TARGET, NEVER THE COMPARATOR (SPIKE-Ж, Ж-3). It used to
    fork — `value_matches` for a role-less leaf, `role_matches` for a role leaf —
    and the fork decided which of two copies of «same value» a hop got. The
    leaves the class-Ж witnesses land on are exactly the role-less ones
    (`calendar_free.person`, `vehicle_check.plate`, `snils_verify.snils`), so
    the fork was not a distinction between two questions: it was a coin. One
    predicate now, and the role still chooses the PART of the value
    (`expected_leaf_value`).
    """
    if spec is not None and spec.kind == "free":
        return item_survives_in(item, item.canonical or item.value, produced)
    target = expected_leaf_value(item, spec) if spec is not None and spec.role \
        else (item.canonical or item.value)
    return values_equal(item.type, produced, target)


def leaf_value_ok(item: PiiItem, tool_name: str, path: str, produced: str) -> bool:
    """Did the leaf receive the value asked of it: its PART when the tool asks
    for a part, the whole value when it asks for the whole.

    IT LOOKS THE SPEC UP AND HANDS IT ON: `leaf_value_ok_for_spec` is where the
    rule lives, and this name is the one every tool-leaf caller uses. The rule
    itself is a thin caller of `tools.expected_leaf_value` (R-53). What a leaf expects is
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
    return leaf_value_ok_for_spec(item, leaf_spec(tool_name, path), produced)


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
    """`value_repaired`, asked of the leaf's own part.

    THE FORK HERE IS ABOUT THE TARGET, NOT THE COMPARATOR (SPIKE-Ж, Ж-3). A
    role-less leaf is still asked the whole `value_repaired` — its lenient
    per-type ladder (a canonical date notation, a declined name, the digits of a
    phone) is the diagnostic's own question and `round_trip_repaired` is
    published apart from `round_trip` precisely because the two differ by what
    normalisation costs. The one way they could ALSO have differed — by their
    RULE — is gone: `role_matches` and `value_matches` are now one predicate, so
    this diagnostic cannot disagree with the line it explains about whether two
    spellings are one value."""
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
    (`engine_kept` / `not_masked` / `leaf_foreign`, the three facts class Е
    split out of `unmasked`) and one the agent never wrote (`absent`) are
    misses inside the denominator."""
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
    (`absent`) and the ones it never masked (`engine_kept` / `not_masked` /
    `leaf_foreign`) included, both as MISSES.

    A PASSTHROUGH SCORES 0 HERE, NOT 100, and this docstring used to say the
    opposite. F1.3 made an OUT leaf carrying no substitute a miss of its own
    status (`unmasked` then, three statuses since class Е), and every form and
    value line counts that as a miss inside the denominator — so «the tool got
    the real value» stopped being the question: the question is whether the
    gateway PUT it there. Measured on the production observer: a gateway that
    masks nothing prints 0/2 (`report --selftest`'s `end_to_end` mutant is that
    old promise, written out).

    THE DENOMINATOR IS THE CORPUS'S AND IS NOT NARROWED BY THIS ROUND, on
    purpose: the honest share over the leaves the engine had to restore is
    `end_to_end_written`, printed BESIDE this line (`report.beside_of`) and
    never instead of it. Narrowing here is the move v4's D3 defect came from
    («did the arm act at all»), and it is what would let a counting fix be read
    as an engine improvement.

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


def _out_leaf_rows(observations: Sequence[RunObservation]) -> list[tuple[RunObservation, HopObservation]]:
    """Declared OUT/tool_arg leaves — `end_to_end`'s population, in the order
    the report reads it. One reader for the strict line and for its honest
    sibling, so the two can differ by their POPULATION and by nothing else."""
    return [(one, hop) for one, hop in _owned(observations, "OUT", ("tool_arg",)) if hop.declared]


def end_to_end_written(observations: Sequence[RunObservation]) -> Line:
    """THE ENGINE'S HONEST SHARE, published BESIDE the strict headline and never
    instead of it (SPIKE-Е, Е-3; the owner's ruling in `DECISIONS-SPRINT.md`).

    WHY THE STRICT LINE STAYS. `end_to_end` counts every declared leaf, `absent`
    (the agent wrote nothing) and `engine_kept` / `not_masked` (there was
    nothing to restore) included, and it must: a denominator that shrinks when
    the agent does less work is v4's D3 defect, and a denominator that drops the
    leaves the engine never masked would let a passthrough earn the line whose
    job is to catch it. Measured on the corpus: 41 % strict against ≈90–96 % of
    the leaves the engine actually had to restore (DIAGNOSIS §Рефрейм). The
    strict number is a statement about the TRAJECTORY OF A FREE AGENT; published
    alone it reads as a statement about the engine, and no engine fix can move
    it — which is why the split comes first.

    THE POPULATION IS `contracts.OUT_HOP_RESTORABLE_STATUSES`, and each status
    is there for a reason the strict line does not share. `observed` and
    `residual` put a substitute in the agent's hand, so the restoration was the
    engine's to perform. `leaf_foreign` says a third value arrived where a datum
    was at stake — leaving it out would hide a wrong value behind the
    denominator. `engine_kept` and `not_masked` are OUT and printed as counts
    (`out_no_mint`, `out_engine_kept`, `out_not_masked`): a leaf that already
    holds the real value proves nothing about restoring it, and `absent` is a
    fact about the agent, printed by `out_absent`.

    THE HIT IS THE STRICT HIT — `status == "observed"` and the SAME
    `leaf_value_ok` (Е-7). The two lines differ by their population and by
    nothing else, which is what lets a reader put them on one page.

    A PASSTHROUGH PRINTS «н/п» HERE AND 0 ON THE STRICT LINE. That is not
    leniency: there was nothing to restore, so there is no share to report, and
    the gateway that protected nothing is caught by `leak` on the IN leg."""
    hits = 0
    total = 0
    for one, hop in _out_leaf_rows(observations):
        if hop.status not in contracts.OUT_HOP_RESTORABLE_STATUSES:
            continue
        total += 1
        item = _item_of(one, hop.hop.item_id)
        hits += 1 if (hop.status == "observed" and item is not None
                      and _item_value_ok(hop, item)) else 0
    return _line("end_to_end_written", hits, total)


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
    context. It is now the ONLY line asking that question: `memory_stability`
    asked it of the items a `MemorySpec` names and that population is empty by
    construction, so it was removed (J1.2, the comment below
    `memory_consistency`)."""
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
    both: a crossing is a crossing whether or not the case foresaw it.

    READ IT ON THE `spoken` AXIS, AND THE WHOLE RESIDUE IS AN ENGINE FINDING.
    The perfect-gateway probe prints 10 812/10 812 on the values the customer
    WROTE and 250/918 on the ones the customer DICTATED — 94.31% overall — and
    the difference is not a gateway that lost a form: our engine mints a
    WRITTEN fake for a spoken value («восемь девятьсот шестнадцать…» → «+7 916
    …»), so the substitute cannot wear the source's form and `form_match` is
    right to say so. That is `docs/known-issues.md` Б27 and it belongs to the
    voice track; the slice is here so the caption is never read as an
    instrument defect (J1.3)."""
    rows = [hop for _one, hop in _hops(observations, "IN") if hop.status == "observed"]
    return _line("form_hIN", sum(1 for hop in rows if hop.verdict is not None and hop.verdict.same), len(rows))


def form_hOUT(observations: Sequence[RunObservation]) -> Line:  # noqa: N802 - the metric's name
    """Did the REAL value come back in the AGENT's form — the form read off the
    agent's own output, never a canonical the benchmark chose.

    OVER THE OUT HOPS THE AGENT WROTE — `contracts.OUT_HOP_WRITTEN_STATUSES`,
    every status but `absent`, and not «all declared tool arguments» as this
    docstring used to promise. A leaf the gateway never masked carried no
    substitute, so there was nothing to restore and the comparison was of a
    string with itself — a MISS, in the denominator, never a hit; the split put
    three names on that fact (`engine_kept`, `not_masked`, `leaf_foreign`) and
    all three stay in. `residual` is in it NOW and was not before: a leaf
    holding a fake the agent wrote is written, and the old pair («observed ∪
    unmasked») spelled the population from the other end and left out the one
    state in which a fake reached the customer's tool. An `absent` leaf was
    never written at all: it is a fact about the AGENT and it is printed on its
    own line (`out_absent`), because a denominator that shrinks when the agent
    does less work is the v4 D3 defect and a denominator that grows with it
    flatters a gateway that protected nothing."""
    rows = [hop for _one, hop in _hops(observations, "OUT")
            if hop.status in contracts.OUT_HOP_WRITTEN_STATUSES]
    return _line("form_hOUT", sum(1 for hop in rows if hop.verdict is not None and hop.verdict.same), len(rows))


def out_absent(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC, printed BESIDE `form_hOUT`: declared OUT hops the agent
    never wrote. It is the number `form_hOUT` leaves out of its denominator,
    and without it a reader cannot tell a gateway that kept every form from an
    agent that wrote almost nothing."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.declared]
    return _line("out_absent", sum(1 for hop in rows if hop.status == "absent"), len(rows))


def out_written(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC, the population `form_hOUT` counts: declared OUT hops the
    agent wrote something in. `out_absent` is its complement over the same
    denominator, and the two together are every declared OUT hop — which is how
    a reader checks that neither line quietly moved."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.declared]
    return _line("out_written", sum(1 for hop in rows if hop.status != "absent"), len(rows))


def out_no_mint(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC: declared OUT hops the engine had NOTHING to restore on —
    `engine_kept` and `not_masked`, both halves in one count. It is exactly the
    population `end_to_end_written` subtracts from «everything the agent
    wrote», and printing it is what makes the subtraction visible instead of
    silent (the precedent is J1.1's `answer_optional_only`)."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.declared]
    return _line("out_no_mint",
                 sum(1 for hop in rows if hop.status in ("engine_kept", "not_masked")), len(rows))


def out_engine_kept(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC: the engine LEFT THE REAL VALUE ON PURPOSE — a generic role
    (`contracts.GENERIC_PIECE_ROLES`) with the mint record proving it was awake
    for this entity. Printed rather than subtracted because it is the one status
    that could hide a real over-masking defect: if the engine started masking
    settlements, these leaves would become `observed` and this count would fall
    (SPIKE-Е risk 2)."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.declared]
    return _line("out_engine_kept", sum(1 for hop in rows if hop.status == "engine_kept"), len(rows))


def out_not_masked(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC: the leaf already held the REAL value and no substitute was
    minted for it — a passthrough, or a leaf naming no generic role. The fact
    that used to be one cell together with `engine_kept` and a third value:
    read beside `out_engine_kept` it says whether «the engine did not mask
    here» was a decision or a failure."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.declared]
    return _line("out_not_masked", sum(1 for hop in rows if hop.status == "not_masked"), len(rows))


def out_leaf_foreign(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC: a THIRD value stands in the leaf — neither this datum's
    substitute nor its real value. `form_match` cannot see it (`verdict` is
    None, `produced == reference`), so before the split the report had no cell
    in which this fact was named at all."""
    rows = [hop for _one, hop in _hops(observations, "OUT") if hop.declared]
    return _line("out_leaf_foreign", sum(1 for hop in rows if hop.status == "leaf_foreign"), len(rows))


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
    """Every TAGGED slot of this result was masked, pieces included.

    A `neg:` slot is a NEGATIVE (a business identifier that must stay), not a
    PII item to mask — `overmask_result` scores it, and a right gateway leaves it
    untouched. Folding it in here would make every result carrying a negative
    read as a `toolresult_masked` miss, which is the defect this line existed to
    prevent in the other direction."""
    for tag, span in record.spans_real.items():
        if tag.startswith(NEG_TAG_PREFIX):
            continue
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
    is asked right beside it.

    AN ANSWER WITH NOTHING TO REQUIRE IS OUTSIDE THE DENOMINATOR (J1.1). It is
    v4's «all() over an empty list» once more: `required` was empty for 720 of
    the 1357 answers the corpus declares an answer hop for, `all([])` is True,
    the residual clause has nothing to find in a reply that was never masked —
    and a FULL PASSTHROUGH scored 53.1% on the line named «the answer carries
    the real value». Skipping the case is the only honest reading: the corpus
    obliges the agent to name nothing, so there is nothing to be right about.
    The count is not swallowed — `answer_optional_only` prints it beside this
    line, and a substitute left in such a reply is still counted by
    `residual`, whose population is every answer."""
    hits = 0
    total = 0
    for one in observations:
        rows = [hop for hop in one.hops
                if hop.declared and hop.hop.kind == "OUT" and hop.hop.owner == "answer"]
        required = [hop for hop in rows if not hop.hop.optional]
        if not required:
            continue
        total += 1
        good = all(_answer_hop_right(one, hop) for hop in required)
        left_over = any(hop.status == "residual" for hop in rows) or bool(
            residual_answer_items(one.case, one.run))
        hits += 1 if good and not left_over else 0
    return _line("answer_real", hits, total)


def answer_optional_only(observations: Sequence[RunObservation]) -> Line:
    """DIAGNOSTIC, printed BESIDE `answer_real`: answers whose case declares
    OUT/answer hops and obliges none of them.

    It is the number `answer_real` leaves out of its denominator, and it is
    printed for the same reason `out_absent` is — a denominator that shrinks
    without saying so is how «all() over an empty list» survived v4. An answer
    the case declares no hop for at all is in NEITHER population: the case is
    not asking the agent to name anything, so there is no answer to judge and
    none to exclude.

    IT IS A FACT ABOUT THE CORPUS AND NO GATEWAY CAN MOVE IT, deliberately.
    `out_absent` shifts when the AGENT skips a declared hop; this counts what
    the CASE obliges, which is fixed before any arm runs (720 of 1357 on the
    current corpus). That is what makes it a caption rather than a result, and
    it is why it is DIAGNOSTIC: read as a score it would say nothing, read
    beside `answer_real` it says which answers the rate above it is over."""
    hits = 0
    total = 0
    for one in observations:
        rows = [hop for hop in one.hops
                if hop.declared and hop.hop.kind == "OUT" and hop.hop.owner == "answer"]
        if not rows:
            continue
        total += 1
        required = [hop for hop in rows if not hop.hop.optional]
        hits += 0 if required else 1
    return _line("answer_optional_only", hits, total)


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


def _written_transitions(observations: Sequence[RunObservation]
                         ) -> list[tuple[RunObservation, HopObservation, HopObservation]]:
    """`_transitions`, restricted to the OUT(B) leaves the engine had something
    to do on — the population rule of `end_to_end_written`, at the transition
    level. `chain_value` / `chain_form` keep the corpus's whole timetable; these
    read the hand-overs the engine was actually asked to perform."""
    return [(one, hop, source) for one, hop, source in _transitions(observations)
            if hop.status in contracts.OUT_HOP_RESTORABLE_STATUSES]


def chain_value_written(observations: Sequence[RunObservation]) -> Line:
    """`chain_value` over the restorable hand-overs. The strict line counts an
    `absent` B as a broken hand-over, which it is not — nothing crossed — and
    744 of the 6 880 scheduled transitions on the saved corpus read that way
    while the same tool worked in another turn (SPIKE-Е, Е-5: the timetable is
    the timetable). This line names what the engine did with what the agent
    wrote; the same identity test and the same value predicate."""
    hits = 0
    rows = _written_transitions(observations)
    for one, hop, source in rows:
        left, right = _item_of(one, hop.hop.item_id), _item_of(one, source.hop.item_id)
        same_identity = left is not None and right is not None and left.identity == right.identity
        arrived = right is not None and leaf_value_ok(
            returned_as_item(right, source.reference),
            hop.hop.tool_name, hop.hop.path, hop.produced)
        hits += 1 if (hop.status == "observed" and same_identity and arrived) else 0
    return _line("chain_value_written", hits, len(rows))


def chain_form_written(observations: Sequence[RunObservation]) -> Line:
    """Same population, the other question: did B receive it in the AGENT's
    form. Read beside `chain_value_written` it separates «the value was lost»
    from «the value arrived canonicalised»."""
    rows = _written_transitions(observations)
    hits = sum(1 for _one, hop, _source in rows
               if hop.status == "observed" and hop.verdict is not None and hop.verdict.same)
    return _line("chain_form_written", hits, len(rows))


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


def multi_all_out_written(observations: Sequence[RunObservation]) -> Line:
    """`multi_all_out` over the turns the agent actually wrote in.

    WHY THE STRICT LINE COULD NOT ANSWER THIS. `_multi_turns` filters on the
    CASE — declared, non-optional, ≥ 2 leaves — and never looks at the status,
    so a turn where the agent wrote one leaf and left the other blank is `0/1`
    for the whole turn. On g02, 55 of 56 multi-hop turns had NEITHER leaf
    written (the scene gives no interval that the `courier_book` schema
    demands) and the headline printed 0/56: a fact about the SCENE, read as a
    defect of the engine.

    THE POPULATION IS THE RESTORABLE LEAVES OF THE TURN, and a turn with none
    is outside the denominator — the strict line still counts it as a miss, so
    the two differ by the population and by nothing else. Order is still not a
    condition and the form verdict is still asked (`multi_all_out`'s own
    ruling)."""
    rows = _multi_turns(observations)
    hits = 0
    total = 0
    for one, _turn, hops in rows:
        written = [hop for hop in hops if hop.status in contracts.OUT_HOP_RESTORABLE_STATUSES]
        if not written:
            continue
        total += 1
        good = True
        for hop in written:
            item = _item_of(one, hop.hop.item_id)
            if not (hop.status == "observed" and hop.verdict is not None and hop.verdict.same
                    and item is not None and _item_value_ok(hop, item)):
                good = False
        hits += 1 if good else 0
    return _line("multi_all_out_written", hits, total)


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


# `memory_stability` STOOD HERE AND IS REMOVED (J1.2). It asked whether the
# substitute of a value the case asks the agent to REMEMBER changed between
# requests, and its population was empty on the whole corpus — 619 of 619
# memory specs have all their mentions in ONE request, because a
# `MentionRecord` is written once per message (`harness.GatewayV5.
# _note_message_mentions`) and a `MemorySpec` recall is anaphoric, so the
# value is spelled once. It printed 0/0 for the perfect gateway and 0/0 for
# every one of the 23 wrong gateways: nothing could make it red. The
# alternatives were a second name for `memory_consistency` (the per-PLACE
# population, 619/619) or a record only the harness can write; the rule from
# H1.4 decides — a public line that can only print «н/п» is worse than no
# line. `stability` still asks the question of EVERY item of the corpus
# (306 in population), which is where the evidence actually is.


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

    A LEAF THAT CARRIES NO SUBSTITUTE IS CLEAN HERE, and the exception is
    deliberate: `not_masked` and `engine_kept` hold the REAL value, so no fake
    reached the consumer (`leak` is where that failure is reported, and firing
    here as well would mean two lines for one defect and a `residual` number
    that no longer means what it says); `leaf_foreign` holds a third value,
    which is neither a residual of this datum nor a restoration of it.
    Everywhere a FORM or a VALUE is asked of an OUT hop, all three are misses.

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


# --- §6.3 the three v6 rows (OD-54) ---------------------------------------------------
#
# Each is a v6-only line, printed on runs with a v6 case and gated by its own
# three fixtures (TZ §6.3: «без трёх фикстур ворота отказывают им в печати»).
# They live OUTSIDE `METRIC_FUNCTIONS` on purpose: `contracts.METRICS` is the
# closed v5 surface and `test_metrics.test_every_metric_registered` pins
# `METRIC_FUNCTIONS` to exactly those names, so a v6 row registered there would
# turn the v5 battery red without a v6 case anywhere in sight.


def _engine_labels(pii_type: str) -> tuple[str, ...]:
    """The engine labels a type accepts for `typed`/`typed_user` (TZ §6.2):
    `engine_labels` from the registry, never another element type. A v5 type has
    no labels and the DOB/DATE equivalence is the one declared exception."""
    spec = _SPECS.get(pii_type)
    return spec.engine_labels if spec is not None else ()


def _covering_message_piece(run: object, item: PiiItem) -> tuple[int, int, int, str] | None:
    """The recorded message piece that covers this item's locus ENTIRELY (OD-76).
    `ArmRunV5.message_pieces` is the IN/user analogue of `ToolResultRecord.pieces`;
    a piece covering only part of the item's span leaves the rest in the model's
    context and is no cover, exactly like `observe.covering_piece`."""
    if item.where.kind != "message" or item.where.msg < 0:
        return None
    for piece in run.message_pieces:  # type: ignore[attr-defined]
        msg, start, end, engine_type = piece
        if msg == item.where.msg and start <= item.where.start and item.where.end <= end:
            return piece
    return None


def typed_user(observations: Sequence[RunObservation]) -> Line:
    """Did the gateway also call an IN/user value the right type (OD-76, §6.3).

    `typed` reads IN/tool and IN/document hops off `ToolResultRecord.pieces`; the
    user leg had no piece record at all, so a message value mistyped as CARD was
    invisible (F21). The denominator is the IN/user hops whose locus a recorded
    piece covers — the value was actually replaced and a type exposed; a hop with
    no covering piece is outside it, the way `typed` skips an uncovered slot."""
    hits = 0
    total = 0
    for one, hop in _hops(observations, "IN"):
        if hop.hop.owner != "user":
            continue
        item = _item_of(one, hop.hop.item_id)
        if item is None:
            continue
        piece = _covering_message_piece(one.run, item)
        if piece is None:
            continue
        total += 1
        labels = _engine_labels(item.type)
        hits += 1 if piece[3] in labels else 0
    return _line("typed_user", hits, total)


def fake_checksum_invalid(observations: Sequence[RunObservation]) -> Line:
    """HISTORICAL v1 — checksum-carrying elements whose SUBSTITUTE fails its own
    checksum (§6.3).

    KEPT AS A VERSIONED ROW, NEVER REWRITTEN IN PLACE (V1 S5, MUTANT-LINE-
    REDEFINE). Its accepted semantics were the R6-39 re-mint-until-invalid rule,
    boundary 1.0; `COV-CHECKSUM-INHERIT` replaces them with inheritance — a VALID
    source mints a VALID substitute — under which this line prints 0/11 for the
    correct arm and an identical 0/11 for the old `valid -> invalid` arm, so it
    cannot separate the behaviour it exists to catch; on a faulty source it
    REWARDS the forbidden repair. The live line is `fake_checksum_inherited`
    (v2). The substitute is folded by `value_notation` before validating — a
    grouped «7707 5364 …» is the digit run, never the raw string."""
    hits = 0
    total = 0
    for one in observations:
        for item in one.case.base.pii:
            spec = _SPECS.get(item.type)
            if spec is None or not spec.generated_checksum:
                continue
            minted = one.run.base.substitutes.get(item.id)
            if minted is None or not minted[0]:
                continue
            total += 1
            hits += 0 if _checksum_valid(spec, minted[0]) else 1
    return _line("fake_checksum_invalid", hits, total)


# --- §6.3 THE CHECKSUM LINE, RE-VERSIONED (V1 S5 / OC-2 / MUTANT-LINE-REDEFINE) ---
#
# THE TWO VERSIONS AND WHY BOTH STAY. v1 (`fake_checksum_invalid`) counts a hit
# when the fake FAILS its checksum; v2 (`fake_checksum_inherited`) counts a hit
# when the fake's verdict MATCHES the source's. `COV-CHECKSUM-INHERIT` decides
# the policy — a VALID source mints a VALID substitute, a faulty source is NOT
# repaired — so v1's accepted semantics are gone while its SAVED results are
# not: the migration keeps the old row under its own version instead of
# reinterpreting a printed number.
#
# THE NEW MUTANT SET (V1 S5): `valid -> invalid` (the old R6-39 arm), `invalid
# -> valid` (a repair), `wrong form`, `unsafe identity/collision`. Each is
# distinct from the correct arm by at least one fixture, reproducibly —
# `test_metrics_v6.test_checksum_line_reversioned` and
# `test_perfect_v6.test_mutants_are_distinct_from_the_correct_arm` hold it.
#
# WIRING NOTE (routed, not hidden): `V6_METRIC_FUNCTIONS` still holds the v1 row
# so a saved v6 report keeps printing exactly what it printed, and the v2 line
# is exposed here plus in `CHECKSUM_METRIC_FUNCTIONS`. Moving the REPORT to v2
# needs a v2 fixture row in `fixtures.py` and a `report.py` edit, neither of
# which is in this stage's write set.
CHECKSUM_LINE_VERSIONS: dict[str, int] = {
    "fake_checksum_invalid": 1,
    "fake_checksum_inherited": 2,
}


def fake_checksum_inherited(observations: Sequence[RunObservation]) -> Line:
    """v2 / LIVE — checksum-carrying elements whose substitute's validity MATCHES
    its SOURCE's (§6.3, COV-CHECKSUM-INHERIT).

    A hit is `validity(substitute) == validity(source)`: a valid source mints a
    valid fake, a faulty source is not repaired. The perfect arm holds 1.0. The
    `invalid -> valid` repair and the `valid -> invalid` flip are the two misses;
    `wrong form` and `unsafe identity/collision` are held by the mint contract
    (`perfect._grammar_holds`, the no-shared-position rule) and named in the S5
    mutant set. Both sides are folded by `value_notation` before validating, the
    same rule v1 used, so a grouped spelling is the digit run and never the raw
    string."""
    hits = 0
    total = 0
    for one in observations:
        for item in one.case.base.pii:
            spec = _SPECS.get(item.type)
            if spec is None or not spec.generated_checksum:
                continue
            minted = one.run.base.substitutes.get(item.id)
            if minted is None or not minted[0]:
                continue
            total += 1
            if _checksum_valid(spec, item.value) == _checksum_valid(spec, minted[0]):
                hits += 1
    return _line("fake_checksum_inherited", hits, total)


# BOTH ROWS, BY VERSION. v1 is historical and must keep answering; v2 is the
# accepted semantics under the owner's inheritance choice.
CHECKSUM_METRIC_FUNCTIONS: dict[str, Metric] = {
    "fake_checksum_invalid": fake_checksum_invalid,
    "fake_checksum_inherited": fake_checksum_inherited,
}


def overmask_result(observations: Sequence[RunObservation]) -> Line:
    """Negatives INSIDE tool results that reached the model untouched (§6.3).

    `overmask` reads message negatives only (F20); a negative the mock renders in
    a result — a BIK in a statement — was measured by nothing. The locus is a
    `NEG_TAG_PREFIX` slot in `ToolResultRecord.spans_real` (CQ-11), and the
    verdict is the SPAN's own coverage, never a needle search of the digits: a
    BIK whose digits open the neighbouring account would make a needle metric
    read a survival that the span says did not happen."""
    hits = 0
    total = 0
    for one in observations:
        for record in one.run.tool_results:
            for tag, span in record.spans_real.items():
                if not tag.startswith(NEG_TAG_PREFIX):
                    continue
                total += 1
                hits += 0 if covering_piece(record, span) is not None else 1
    return _line("overmask_result", hits, total)


# The three OD-54 rows, gated by the report only on a v6 run (F7). Their names
# are deliberately NOT in `contracts.METRIC_NAMES`.
#
# `fake_checksum_invalid` here is the HISTORICAL v1 row (see the re-version block
# above): the report keeps printing what a saved run printed. The LIVE checksum
# semantics under `COV-CHECKSUM-INHERIT` is `fake_checksum_inherited`, exposed in
# `CHECKSUM_METRIC_FUNCTIONS`; moving the report to it needs a v2 fixture row and
# a `report.py` edit beyond this stage's write set.
V6_METRIC_FUNCTIONS: dict[str, Metric] = {
    "typed_user": typed_user,
    "fake_checksum_invalid": fake_checksum_invalid,
    "overmask_result": overmask_result,
}


# --- §6.4 the per-type certificate over CASES, not hops (OD-67, R6-40) ---------------


def case_line(metric: Metric, observations: Sequence[RunObservation]
              ) -> tuple[Line, int, int]:
    """`metric` over a slice, beside the DISTINCT cases and elements behind it.

    The per-type slice prints hops, elements and cases together (TZ §6.4); this
    is the one reader that computes all three, so the report cannot count them
    differently from the metrics. The hop `Line` is `metric`'s own; the case and
    element counts are the slice's distinct `case.base.id` / `hop.item_id`."""
    line = metric(observations)
    case_ids = {one.case.base.id for one in observations}
    element_ids = {hop.hop.item_id for one in observations for hop in one.hops}
    return line, len(case_ids), len(element_ids)


def certified_over_cases(metric: Metric, observations: Sequence[RunObservation]) -> float | None:
    """The one-sided floor of a clean line, computed over DISTINCT CASES (§6.4).

    240 clean hops from 12 cases certify `zero_failure_floor(12)` = 77.9 %, not
    the ~98 % the hop count would claim — the whole of OD-67 / R6-40. None when
    the line is not clean or the slice is empty."""
    line, cases, _elements = case_line(metric, observations)
    if line.total and line.hits == line.total and cases:
        return zero_failure_floor(cases)
    return None


def survival_excluded(observations: Sequence[RunObservation], pii_type: str) -> int:
    """Distinct elements of `pii_type` whose value carries no identifying needle
    (below `SURVIVAL_MIN_CHARS`) — the count every survival denominator leaves
    out (R-58), printed per type as «не оценивается по выживанию: n» (§6.5)."""
    seen: set[str] = set()
    out = 0
    for one in observations:
        for item in one.case.base.pii:
            if item.type != pii_type or item.id in seen:
                continue
            seen.add(item.id)
            surface = item.canonical or item.value
            if surface and not value_needles(pii_type, surface):
                out += 1
    return out


METRIC_FUNCTIONS: dict[str, Metric] = {
    "leak": leak, "coverage": coverage, "typed": typed, "round_trip": round_trip,
    "round_trip_repaired": round_trip_repaired, "end_to_end": end_to_end,
    "end_to_end_written": end_to_end_written, "overmask": overmask,
    "consistency": consistency, "stability": stability, "rewrite_ratio_v5": rewrite_ratio_v5,
    "shared_block_answer": shared_block_answer,
    "form_hIN": form_hIN, "form_hOUT": form_hOUT, "out_absent": out_absent,
    "out_written": out_written, "out_no_mint": out_no_mint, "out_engine_kept": out_engine_kept,
    "out_not_masked": out_not_masked, "out_leaf_foreign": out_leaf_foreign,
    "toolresult_masked": toolresult_masked,
    "answer_real": answer_real, "answer_optional_only": answer_optional_only,
    "chain_value": chain_value, "chain_form": chain_form,
    "chain_value_written": chain_value_written, "chain_form_written": chain_form_written,
    "multi_all_out": multi_all_out, "multi_all_out_written": multi_all_out_written,
    "multi_consistency": multi_consistency,
    "retry_form": retry_form, "memory_consistency": memory_consistency,
    "rag_masked": rag_masked,
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
    "leak", "coverage", "typed", "end_to_end", "end_to_end_written", "form_hIN", "form_hOUT",
    "out_absent", "out_written", "out_no_mint", "out_engine_kept", "out_not_masked",
    "out_leaf_foreign"})
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


def _spoken_bucket(one: RunObservation, hop: HopObservation) -> str:
    """Was the value this hop carries one the customer DICTATED or one they
    WROTE — `PiiItem.spoken`, the corpus's own statement about the source.

    Read off the item and never off the surface: a dictated «сто сорок три»
    already reached the tool leg as digits, and guessing the register back from
    a string would bucket the engine's own canonicalisation as speech. An item
    the observation cannot resolve goes to «—» rather than to either side, so a
    bucket is never inflated by a lookup failure (`_return_form_bucket` does
    the same)."""
    item = _item_of(one, hop.hop.item_id)
    if item is None:
        return "—"
    return "продиктовано" if item.spoken else "написано"


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
    if axis == "spoken":
        return _spoken_bucket(one, hop)
    if axis == "type_class":
        # The v6 axis `type_class` is per HOP: the class of the type that crossed
        # the gateway (TZ §14.2). A v5 type files under "v5", a v6 one under its
        # registry `type_class` (C/K/KC) — read off the ONE home, never restated.
        return _TYPE_CLASS.get(hop.pii_type, "v5")
    return _cue_bucket(one, hop)


HOP_AXES: tuple[str, ...] = ("vertical", "hop_owner", "pii_type", "return_form", "cue", "spoken",
                             "type_class")


def by_axis(observations: Sequence[RunObservation], axis: str) -> dict[str, list[RunObservation]]:
    """One axis at a time, never two crossed — the public harness's rule, for
    the public harness's reason: a cell of eight items has an interval wider
    than any difference worth reading.

    A HOP-level axis splits the HOPS, not the observations: the bucket gets a
    copy of the observation carrying only its own hops, so `form_hOUT` by
    `pii_type` counts NAME hops under NAME and nowhere else, while the run's
    records stay reachable for the metrics that need them."""
    if axis not in contracts.AXES and axis not in V6_AXES:
        raise ValueError(f"by_axis: {axis!r} is not one of contracts.AXES ∪ V6_AXES "
                         f"({list(contracts.AXES)}, {list(V6_AXES)})")
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
        elif axis == "industry":
            # ONE per case, read off `CaseV5.v6`; a v5 case files under "" so the
            # axis is empty on the old corpus and nothing is printed there (TZ §14.2).
            name = one.case.v6.industry if one.case.v6 is not None else ""
        elif axis == "provenance":
            name = one.case.v6.provenance if one.case.v6 is not None else ""
        else:
            name = "rare" if one.case.base.provenance.selection == "rare" else "authored"
        buckets.setdefault(name, []).append(one)
    return buckets


def main() -> int:
    from bench.agentpii5.test_metrics import main as run_tests
    return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
