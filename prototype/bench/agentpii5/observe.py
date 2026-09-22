"""From the run's RECORDS to one `HopObservation` per crossing. Pure, offline.

`observe(case, run, ic, cc)` is the whole measuring front end of v5: it takes
the case's DECLARED hops (§1 of `contracts.py`) and the records the harness
wrote for the gateway arm, and decides, for each one, what the model read, what
the consumer received, and whether the crossing happened at all. Everything
downstream — every metric, every fixture, the report — reads only what this
file produced, so a metric can never reach for the engine or for a model.

FOUR RULES DECIDE EVERYTHING HERE, AND THEY ARE NOT SYMMETRIC.

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
  * NOTHING TO COMPARE IS NOT A PASS. An OUT leaf that carries no substitute
    is `unmasked`, never `observed`: `produced == reference` there, so
    `form_match` said «same» and a gateway that masked NOTHING printed 100%
    on `form_hOUT`, `chain_form`, `chain_value` and `multi_all_out`. The same
    rule, one level up, is why D1 was a defect at all.

WHY `difflib` FOR THE ANSWER. The engine restores the reply in one pass and
records no spans for it; asking the engine where it substituted would be the
instrument reading the defendant's notes. `SequenceMatcher` over
(`reply_raw`, `reply`) is a pure alignment of two strings this file did not
write: every `replace` opcode is a candidate crossing. The SURVIVING
substitute — `residual`, the product's own critical defect — is NOT read off
that alignment: it is scanned for in the whole restored reply
(`residual_answer_items`), because «the engine rewrote this region» is not an
alibi for a fake standing three words later, and the declined and reformatted
spellings a model writes are invisible to an equality of raw regions.

Run the test: cd prototype && source .venv/bin/activate
                && python3 -m bench.agentpii5.test_observe
"""
import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

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
    MentionRecord,
    RunObservation,
    ToolResultRecord,
)
from bench.agentpii5.form import form_match
from bench.agentpii5.form_tables import CYRILLIC_TO_LATIN
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
# Roles that belong to EVERYBODY, so a needle built from them proves nothing
# about which value stood in a string: the settlement, the grammatical gender,
# the mail domain («@yandex.ru»), the street's generic word. `EXEMPT_ROLES` is
# the narrower list `coverage` uses (what is not a LEAK); this is the list the
# ATTRIBUTION uses (what is not EVIDENCE) and it is wider — a surviving
# «yandex.ru» is not a leak AND is not proof that a particular address was
# written.
GENERIC_ROLES: frozenset[str] = frozenset({"city", "gender", "domain", "street_type"})
# Types whose identity is a DIGIT SIGNATURE and never a spelling: the model
# reformats «+79990001122» as «8 999 000-11-22» and the letters-and-stems test
# finds nothing at all. PHONE compares the last ten digits, because +7 and 8
# are the same number said twice (`pseudex.vault`'s own canonicalisation rule,
# arrived at here independently — this package never imports the engine).
DIGIT_TYPES: frozenset[str] = frozenset({"PHONE", "CARD", "SNILS", "INN", "PASSPORT"})
PHONE_SIGNATURE_DIGITS = 10
# A date is neither: «14.03.1987» and «1987-03-14» share no substring at all.
DATE_TYPES: frozenset[str] = frozenset({"DOB", "DATE"})

# The three shapes a needle can be found in. `_WORD` is a run of LETTERS, so a
# stem match is anchored at a word start and «Лев» inside «Лебедева» — the
# attribution bug MIN_PIECE exists for — cannot come back through the stems.
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
# A number as a human writes one: digits with the separators a phone, a card
# or a СНИЛС wears. The comma is NOT a separator — «Клубная, 85, кв 14» would
# become one number and every house in the corpus would carry every flat.
_NUMBER_RUN = re.compile(r"\+?\d[\d  ().\-–—]*\d|\d")
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
# Only «.» and «/»: a space would let «+7 916 402…» read as a date and put a
# phone's digits into the date fold.
_RU_DATE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
# A word CHARACTER, for the boundaries the initials needle stands between: the
# same class `_WORD` is built from, so «П.О.» inside «СП.О.» is not a match.
_WORD_CHAR = r"[^\W\d_]"
# Types whose value a model rewrites in another ALPHABET or squeezes to
# initials. NAME only, and deliberately: `contracts.FORM_FEATURES` declares
# `script` and `initials` for NAME alone, the engine ships the leg for names
# (`pseudex.translit.align`, `prototype/test_derived_forms.py`), and a
# transliterated STREET needle would fire on ordinary Latin text in an address
# field without any derived form being there.
DERIVED_TYPES: frozenset[str] = frozenset({"NAME"})
# Two letters is the shortest squeezed initials a needle may carry: one letter
# («П.») stands in front of a third of the Russian alphabet's worth of names
# and in the middle of ordinary abbreviations.
MIN_INITIALS = 2


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


def digits_of(text: str) -> str:
    return "".join(character for character in text if character.isdigit())


def date_folds(text: str) -> tuple[tuple[int, int, str], ...]:
    """Every date in `text`, as (start, end, ISO). The fold is what makes
    «14.03.1987» and «1987-03-14» ONE date: a metric comparing the strings
    would call a correctly restored birth date absent, and the answer leg
    would be blind to every DOB an agent reformatted."""
    out: list[tuple[int, int, str]] = []
    for match in _ISO_DATE.finditer(text):
        out.append((match.start(), match.end(),
                    f"{match.group(1)}-{match.group(2)}-{match.group(3)}"))
    for match in _RU_DATE.finditer(text):
        out.append((match.start(), match.end(),
                    f"{int(match.group(3)):04d}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"))
    return tuple(sorted(out))


def latin_prefixes(word: str, length: int) -> tuple[str, ...]:
    """Every Latin rendering of the first `length` characters of a Cyrillic
    word, under the alternatives of `form_tables.CYRILLIC_TO_LATIN`.

    A PREFIX and not the whole word, for the same reason the Cyrillic needle
    is a stem: a model writes «Pakhomovoy» for the dative and «Pakhomova» for
    the nominative, and a whole-word match would see neither. The expansion
    stops as soon as `length` characters are reached, so the number of
    renderings stays in the dozens whatever the word."""
    out = {""}
    for char in word.casefold():
        if all(len(one) >= length for one in out):
            break
        renderings = CYRILLIC_TO_LATIN.get(char)
        if renderings is None:
            return ()
        out = {one + rendering for one in out for rendering in renderings}
    return tuple(sorted(one[:length] for one in out if len(one) >= length))


def initials_of(pii_type: str, surface: str) -> tuple[str, ...]:
    """The squeezed initials a model writes for this value: «Пахомова Ольга» →
    «ПО», and the Latin «PO» beside it.

    The surname-plus-given pair is emitted for a three-part name too, because
    «И.Е.» is what a model squeezes «Иванова Елена Петровна» to at least as
    often as «И.Е.П.». Fewer than `MIN_INITIALS` letters is not a needle."""
    if pii_type not in DERIVED_TYPES:
        return ()
    words = [word for word in _WORD.findall(surface) if word]
    heads = [word[0] for word in words]
    out: set[str] = set()
    for count in (len(heads), 2):
        if count < MIN_INITIALS or count > len(heads):
            continue
        cyrillic = "".join(heads[:count])
        out.add(cyrillic.casefold())
        latin = [latin_prefixes(head, 1) for head in heads[:count]]
        if all(latin):
            out.add("".join(one[0] for one in latin))
    return tuple(sorted(out))


def needles_of(pii_type: str, surface: str) -> tuple[tuple[str, str], ...]:
    """(kind, needle) pairs that say «this value stood here», in the shapes a
    MODEL writes it — not only the one the gateway minted.

    v1 of this observer looked for whole surfaces and whole parts, so a
    correctly restored «Пахомовой Ольге» (dative) and a reformatted «+7 (999)
    000-11-22» both read `absent`: two of the three registers the corpus is
    built from write exactly that way. The six kinds are the six ways a
    Russian value survives being rewritten — verbatim, declined (a word stem),
    renotated (a digit signature), reformatted (a date fold), TRANSLITERATED
    and SQUEEZED TO INITIALS.

    THE LAST TWO ARE NOT AN EXTRA: without them a substitute the agent wrote
    as «Pakhomova Olga» or «П.О.» matched nothing, `_out_status` called the
    leaf `unmasked`, and `residual` — the line whose whole job is «a fake
    reached the consumer» — printed the leaf CLEAN while the fake sat in the
    customer's CRM. The same blindness scored a CORRECT derived-form round
    trip a miss on `form_hOUT`, `end_to_end` and `round_trip`, on the very
    axis `contracts.FORM_FEATURES["NAME"]` declares (`script` with three
    published tables, `initials`) and the engine ships (`pseudex.translit`).
    The renderings come from this package's own letter table, never from
    `pseudex`."""
    out: list[tuple[str, str]] = [("whole", surface)]
    if pii_type in DIGIT_TYPES:
        digits = digits_of(surface)
        signature = digits[-PHONE_SIGNATURE_DIGITS:] if pii_type == "PHONE" else digits
        if len(signature) >= MIN_PIECE:
            out.append(("digits", signature))
        return tuple(out)
    if pii_type in DATE_TYPES:
        out += [("date", iso) for _start, _end, iso in date_folds(surface)]
        return tuple(out)
    for role, value in sorted(parts_of(pii_type, surface).items()):
        if role in GENERIC_ROLES or len(value) < MIN_PIECE:
            continue
        out.append(("stem", fold(value)[:MIN_PIECE]))
        if pii_type in DERIVED_TYPES:
            # The Latin prefixes ride as `stem` needles ON PURPOSE: `own_stems`
            # collects the stems of the customer's OWN values and
            # `survives_in` skips them, so a real name the agent transliterated
            # cannot be reported as a surviving substitute. A separate kind
            # would need its own copy of that exemption, and a second copy is
            # how the two come to disagree.
            out += [("stem", prefix) for prefix in latin_prefixes(value, MIN_PIECE)]
    out += [("initials", letters) for letters in initials_of(pii_type, surface)]
    return tuple(out)


def _needle_spans(kind: str, needle: str, text: str) -> list[tuple[int, int]]:
    if not needle:
        return []
    if kind == "whole":
        return _occurrences(_indexable_fold(text), _indexable_fold(needle))
    if kind == "stem":
        return [(match.start(), match.end()) for match in _WORD.finditer(text)
                if fold(match.group()).startswith(needle)]
    if kind == "digits":
        return [(match.start(), match.end()) for match in _NUMBER_RUN.finditer(text)
                if needle in digits_of(match.group())]
    if kind == "initials":
        return [(match.start(), match.end()) for match in _initials_re(needle).finditer(text)]
    return [(start, end) for start, end, iso in date_folds(text) if iso == needle]


@lru_cache(maxsize=512)
def _initials_re(needle: str) -> re.Pattern[str]:
    """«П.О.», «П. О.», «П.О» — and nothing without a dot.

    A DOT AFTER EVERY LETTER BUT THE LAST, and word boundaries on both sides.
    Bare «ПО» is a preposition, a two-letter abbreviation and half the
    capitalised acronyms in a Russian reply; a needle that matched it would
    invent a surviving substitute in ordinary prose, which is the one thing
    `residual` must never do."""
    body = r"\s*".join(re.escape(char) + r"\s*\." for char in needle[:-1])
    body += r"\s*" + re.escape(needle[-1]) + r"\s*\.?"
    return re.compile(rf"(?<!{_WORD_CHAR}){body}(?!{_WORD_CHAR})", re.IGNORECASE)


def occurrences_of(pii_type: str, surface: str, text: str) -> tuple[tuple[int, int], ...]:
    """Where `surface` stands in `text`, inflection and notation included."""
    spans = [span for kind, needle in needles_of(pii_type, surface)
             for span in _needle_spans(kind, needle, text)]
    return tuple(sorted(set(spans)))


def own_stems(case: CaseV5) -> frozenset[str]:
    """Word stems the customer's OWN real values already carry.

    A substitute may share a given name with the value it replaced — the
    engine mints from a pool, not from a disjoint alphabet — and the RESTORED
    reply is full of real values. Without this filter «Пахомова Елена»
    standing for «Иванова Елена» would make every correctly restored answer
    read as a surviving substitute, and `residual`, the critical-defect line,
    would fire on the product working."""
    out: set[str] = set()
    for item in case.base.pii:
        for surface in (item.value, item.canonical):
            out.update(needle for kind, needle in needles_of(item.type, surface)
                       if kind in ("stem", "initials"))
        for role, value in item.parts.items():
            if role not in GENERIC_ROLES and len(value) >= MIN_PIECE:
                out.add(fold(value)[:MIN_PIECE])
                if item.type in DERIVED_TYPES:
                    out.update(latin_prefixes(value, MIN_PIECE))
    return frozenset(out)


def survives_in(pii_type: str, surface: str, text: str, own: frozenset[str]) -> bool:
    """Is `surface` — a SUBSTITUTE — still standing in `text`?

    The stems the customer's own values carry are skipped (`own_stems`); the
    whole surface, the digit signature and the date fold are not, because a
    fake phone never wears the real one's digits and a fake name never spells
    the real one."""
    for kind, needle in needles_of(pii_type, surface):
        # `initials` joins `stem` in the exemption: «И.Е.» is the customer's
        # own initials as much as the substitute's when the two share their
        # first letters, and evidence both values support is evidence of
        # neither.
        if kind in ("stem", "initials") and needle in own:
            continue
        if _needle_spans(kind, needle, text):
            return True
    return False


def carries_any(pii_type: str, surfaces: Sequence[str], text: str, own: frozenset[str]) -> bool:
    return any(surface and survives_in(pii_type, surface, text, own) for surface in surfaces)


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


def engine_residual(call: ObservedCall, path: str) -> tuple[str, ...]:
    """What the ENGINE says survived at this leaf. Diagnostic only, and that
    is the whole point: `ObservedCall.residual` is `/unmask_arguments`'s own
    `residual_tokens` report, and a benchmark whose verdict on «did a fake
    reach the customer's CRM» is the gateway's own answer has measured
    nothing. `_out_status` decides; this is printed beside it."""
    return tuple(one for key, left in call.residual.items()
                 for one in left
                 if key == path or key.startswith(path + ".") or key.startswith(path + "["))


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


@lru_cache(maxsize=256)
def merged_opcodes(raw: str, restored: str) -> tuple[Opcode, ...]:
    """`SequenceMatcher` opcodes with short `equal` islands absorbed.

    MEMOISED because it is 40 ms on a 1 600-character reply and pure over its
    two strings: `answer_spans` is recomputed by every metric that reads the
    answer and by every axis bucket the report prints, so one run's replies
    were being aligned tens of times each. A cache on a pure function of two
    strings cannot change a verdict; the size is bounded so a long run does
    not hold every reply it ever saw.

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
    # The occurrences are found ONCE per item, in the shapes `needles_of`
    # knows: a declined name and a reformatted phone are the two commonest
    # things a Russian answer does to a substitute, and looking only for whole
    # surfaces made every such answer hop `absent`.
    placed = {item.id: tuple(span for surface in surfaces[item.id]
                             for span in occurrences_of(item.type, surface, run.reply_raw))
              for item in case.base.pii}
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
            hits = [span for span in placed[item.id]
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
    """Items whose substitute is still standing in the reply the CUSTOMER reads.

    THE WHOLE RESTORED REPLY, not the `equal` regions of the alignment, and
    every needle rather than whole surfaces only. The alignment version could
    see a substitute only where it had been left byte for byte in a region the
    restoration did not touch — so a declined «Пахомовой Ольге», a reformatted
    «+7 (999) 000-11-22» and the substitute of an item the case declared no
    answer hop for were all invisible to the product's critical-defect line.
    The question is not «did the engine touch this text» but «does a fake
    stand in what the customer reads», and that is asked of the finished
    reply."""
    own = own_stems(case)
    kept: set[str] = set()
    for item in case.base.pii:
        if carries_any(item.type, substitute_surfaces(run, item.id), run.base.reply, own):
            kept.add(item.id)
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


def turn_request(run: ArmRunV5, turn: int) -> int:
    """The model REQUEST the recall turn rode in, read off the record.

    `MentionRecord.request_index` is the only clock the harness writes, and a
    message mention carries the request its message was pushed in
    (`harness.GatewayV5._note_message_mentions`). A mention of ANY item in the
    turn's own message gives the request exactly; failing that, the FIRST
    later message bounds it from above, one request short of itself; failing
    that the run's own request count does.

    EVERY FALLBACK IS AN UPPER BOUND, never a lower one. An earlier message's
    request is a floor, not a ceiling — using it would exclude a tool result
    the model really did read before the recall turn and turn a protected
    value into a leak, which is the mirror of the defect this bound exists to
    remove."""
    exact = [mention.request_index for mention in run.mentions if mention.msg == turn]
    if exact:
        return max(exact)
    later = [mention.request_index for mention in run.mentions if mention.msg > turn]
    if later:
        return min(later) - 1
    # NOTHING BOUNDS IT, so nothing is excluded: the ceiling is the highest
    # request the record knows of. `request_count` alone would be that ceiling
    # on a real run (no mention can ride a request the run never made) and a
    # FALSE one on a hand-built record whose counter was left at its default —
    # a bound that fires on the instrument's own fixtures is a bound that will
    # fire on a live run for the same kind of reason.
    return max([run.request_count] + [mention.request_index for mention in run.mentions])


def carried_substitute(run: ArmRunV5, item_id: str, turn: int) -> str:
    """The substitute the transcript carries INTO `turn` for this item.

    The SDK holds the transcript and the gateway masks each message once, as
    it is pushed (`harness.GatewayV5._push` → `_note_message_mentions`), so
    «what the model reads at turn 7» is «the last substitute it was shown at
    or before turn 7» — there is no per-request re-recording, and asking for
    one is what made every memory hop read `leaked`.

    A TOOL RESULT COUNTS, AND ONLY IF THE MODEL HAD ALREADY READ IT. Mentions
    from a result carry `msg == -1`, which used to mean «accept
    unconditionally» — so a substitute first shown at request 9 was «carried
    into turn 4», and `leak` scored as protection a value the model had not
    yet been shown.

    THE RESULT'S OWN TURN DECIDES IT. `harness.push_call` writes the mention
    and the `ToolResultRecord` together, and the record carries the turn the
    call was made in, so «had the model read it» is answered exactly and not
    by arithmetic on request counters. `turn_request` is the fallback for a
    mention whose record is missing, and with no evidence at all nothing is
    excluded — inventing a bound would turn a substitute the model did read
    into a leak, which is the mirror of the defect this bound removes."""
    limit = turn_request(run, turn)
    before: list[MentionRecord] = []
    for mention in run.mentions:
        if mention.item_id != item_id:
            continue
        if mention.msg >= 0:
            if mention.msg <= turn:
                before.append(mention)
            continue
        at = _result_turn(run, mention.result_seq)
        if (turn >= at) if at is not None else (mention.request_index <= limit):
            before.append(mention)
    if not before:
        return ""
    return max(before, key=lambda mention: (mention.request_index, mention.msg)).substitute


def _result_turn(run: ArmRunV5, result_seq: int) -> int | None:
    """The turn a tool result was served in, or None when the run kept no
    record for it — which a live record never does (`harness.push_call` writes
    the two in one breath) and a hand-built one may."""
    for record in run.tool_results:
        if record.seq == result_seq:
            return record.turn
    return None


def _in_memory(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop, item: PiiItem) -> HopObservation:
    """The value said at turn 1 and needed again at turn 7.

    Decided from what the harness ACTUALLY records. `masked_spans` is keyed by
    the index of every message that was pushed, so it is the only evidence on
    disk that the conversation reached a turn at all: a recall turn the run
    never got to is `absent`, and a value whose own message was masked but
    left a mention behind is `leaked` — the real value went into the context
    and every later turn carries it.
    """
    pushed = run.base.masked_spans
    if hop.turn not in pushed:
        return _flat(case, repeat, hop, True, item.type, "", item.value, "absent")
    substitute = carried_substitute(run, item.id, hop.turn)
    if substitute:
        return _observed(case, repeat, hop, True, item.type, substitute, item.value)
    said = item.where.kind == "message" and item.where.msg in pushed and item.where.msg <= hop.turn
    return _flat(case, repeat, hop, True, item.type, "", item.value,
                 "leaked" if said else "absent")


def _out_status(pii_type: str, surfaces: Sequence[str], written: str, restored: str,
                own: frozenset[str]) -> str:
    """The status of an OUT leaf, decided HERE and not by the engine's report.

    Two readings that used to come from elsewhere are made in this file now.
    `unmasked`: the leaf the agent wrote carried no substitute at all, so
    `restored == written` and `form_match` compared a string with itself — a
    gateway that masked NOTHING printed 100% on `form_hOUT`. `residual`: the
    engine's own `ObservedCall.residual` said whether a substitute survived,
    and a benchmark that asks the defendant whether it left a fake in the
    customer's CRM is not measuring anything; the scan of the restored leaf
    is the same one `residual_answer_items` runs on the reply.
    """
    if not carries_any(pii_type, surfaces, written, own):
        return "unmasked"
    return "residual" if carries_any(pii_type, surfaces, restored, own) else "observed"


def _out_call(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop, item: PiiItem,
              own: frozenset[str]) -> HopObservation | None:
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
    status = _out_status(item.type, substitute_surfaces(run, item.id), written, restored, own)
    if status == "observed":
        return _observed(case, repeat, hop, True, item.type, restored, written)
    return _flat(case, repeat, hop, True, item.type, restored, written, status)


def _out_answer(case: CaseV5, run: ArmRunV5, repeat: int, hop: Hop, item: PiiItem,
                spans: Sequence[AttributedSpan], residual: frozenset[str]) -> HopObservation | None:
    for span in spans:
        if item.id in span.item_ids:
            return _observed(case, repeat, hop, True, item.type,
                             run.base.reply[span.restored_start:span.restored_end],
                             run.reply_raw[span.raw_start:span.raw_end])
    if item.id in residual:
        return _flat(case, repeat, hop, True, item.type, "", "", "residual")
    # The agent NAMED the person and wrote the real value: the gateway never
    # minted a substitute, so there is no rewritten span to find. That is
    # `unmasked` — a miss with a cause — and not `absent`, which says the
    # agent said nothing about this datum at all.
    if occurrences_of(item.type, item.value, run.reply_raw):
        return _flat(case, repeat, hop, True, item.type, "", "", "unmasked")
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


def _extra_call_hops(case: CaseV5, run: ArmRunV5, repeat: int, declared: Sequence[Hop],
                     own: frozenset[str]) -> list[HopObservation]:
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
            # Matched with the ITEM's type, not the leaf's: the needle shapes
            # are a property of the value («is this a digit signature or a
            # word stem?»), and an agent that wrote a phone into a name field
            # is exactly the crossing this branch exists to catch.
            item_id = next((item.id for item in case.base.pii
                            if carries_any(item.type, surfaces[item.id], written, own)), "")
            hop = _synthetic("OUT", contracts.hop_owner_of_leaf(call.name, path),
                             item_id, turn, call.name, ordinal, path)
            # No item's substitute is in this leaf: the agent wrote something
            # the gateway never touched. It is still a crossing of the form
            # axis — and it has nothing to compare, so it is `unmasked`.
            status = ("unmasked" if not item_id
                      else _out_status(items_by_id(case)[item_id].type, surfaces[item_id],
                                       written, restored, own))
            out.append(_observed(case, repeat, hop, False, spec.pii_type, restored, written)
                       if status == "observed"
                       else _flat(case, repeat, hop, False, spec.pii_type, restored, written, status))
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
    # Computed ONCE per observation: every OUT leaf and the answer scan ask
    # the same question («is this needle the substitute's or the customer's
    # own?») and the answer depends only on the case.
    own = own_stems(case)
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
            one = _out_call(case, run, run.base.repeat, hop, item, own)
        else:
            raise ObserveError(
                f"{case.base.id}: hop {hop.hop_index} is {hop.kind}/{hop.owner}, which is not a "
                f"pair of contracts.HOP_KINDS × HOP_OWNERS")
        if one is not None:
            observations.append(one)
    observations += _extra_call_hops(case, run, run.base.repeat, case.hops, own)
    observations += _extra_answer_hops(case, run, run.base.repeat, case.hops, spans)
    return RunObservation(case=case, repeat=run.base.repeat, hops=tuple(observations),
                          run=run, ic=ic, cc=cc)


def main() -> int:
    from bench.agentpii5.test_observe import main as run_tests
    return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
