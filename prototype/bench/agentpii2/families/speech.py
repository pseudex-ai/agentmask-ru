"""The `speech` family: real Russian phone calls, hand-annotated, nobody's
template.

Every other family in this corpus is generated, which means every other family
knows in advance where the personal data is. This one does not: 122 utterances
were pulled out of OpenSTT `asr_calls_2_val` by an address-vocabulary filter and
then read by a human, who decided one at a time whether an address was there.
That is why «на территории улицы лермонтова понимаете о чем мы» is in the set as
a NEGATIVE — a living person said it into a telephone, it names a street, and it
is not an address. No generator writes that sentence, because writing it
requires not knowing where the address is.

THE REGISTER IS THE SOURCE, NOT A TRANSFORM. `voice_raw` is defined by what these
transcripts are: no digits anywhere (measured, 0 of 12 950 utterances), numbers in
words, no punctuation, no capitals except a few proper nouns, and ASR damage left
in place — «улица лермонтова триц восемь», «дом пяесят восемь». v1 built its
`voice` register from the belief that ASR normalises digits and consequently
never tested any of this. Nothing here is rewritten, reflowed or repunctuated;
the strings are the transcripts.

TWO LEGAL CLASSES, CARRIED OVER FROM `bench/voice`, AND THEY ARE NOT TWO LEVELS
OF CONFIDENCE. A street with a house number identifies a building, so it is
`required`. A bare street identifies nobody — hundreds of buildings stand on it,
exactly one step more specific than the city that 152-ФЗ ст. 3 п. 1 already
leaves out — so it is `optional`: masking it is not an error and missing it is
not a leak. Scored as one number those two read 71%, while the real figures were
94% and 47%, and the average described neither. The eleven utterances the
annotator could not place («квартира шестьдесят семь», cut out of a call whose
context is gone) are dropped entirely rather than pushed into a class, which is
why 122 becomes 111 mentions and not 122.

ONE ANNOTATOR, AND THE CASES SAY SO. `duty` here is read straight off that
single human's class, and the schema's own warning — TAB measured the
direct/quasi decision at Fleiss κ 0.46, its least reliable annotation — asks for
two annotators and a tiebreak. There was one, so every case carries
`annotators=1, adjudicated=False` rather than a flattering default: the human
ceiling on this family is not measured, and the field is what will let it be
computed later instead of asserted.

`conversation_id` IS EMPTY IN ALL 96, which is a claim and not a default. A reply
cut out of a call carries no conversation field, so this family scores the path
where the engine DERIVES the identity from the transcript — the path a customer
gateway without a conversation field actually takes, and the one v1 never touched
because it passed `conversation_id=""` while testing nothing that depended on it.

WHY 96 CASES AND NOT THE 111 IN `docs/tz-agentpii2.md`. A case holding nothing
but an `optional` item is unfalsifiable BY THE SCHEMA'S OWN DEFINITION of
`optional`: masking it is not an error, missing it is not a leak, so no gateway
behaviour can fail it — and `validate()` refuses it for exactly that reason. The
fifteen bare streets are still the most interesting mentions in the set, so each
one travels with a real «не адрес» utterance from the same corpus as a second
turn; that utterance carries the falsifiable claim and the bare street rides
along in its own column. Nothing from the source is lost or counted twice: all 17
numbered addresses, all 15 bare streets and all 79 negatives appear exactly once.
79 cases end up with no `required` item, which is the same 6.7% of the 1181-case
corpus the design doc bounds at a tenth.

THE MODULE SHIPS NO TRANSCRIPT TEXT. OpenSTT is CC BY-NC 4.0 — measuring is
allowed, redistributing is not — so a message carries a `Source` (corpus, line,
digest) and no content, and the text is hydrated from `~/.cache/pseudex-bench/`
at score time. What does ship is spans — an address, a street, a vocabulary word
— the same exception `bench/voice` already takes for its seventeen hand-drawn
boundaries, and for thirteen of the shortest utterances («улица пушкина»,
«красная площадь дом один») the span IS the whole thing said. That is why the
negatives below name the vocabulary word rather than the reply: `bench/voice`
measures one label per reply, and reproducing that measure here would mean
carrying all 79 transcripts verbatim.

Run the self-check from `prototype/`:

    python3 -m bench.agentpii2.families.speech
"""

import hashlib
import json
import random
import re
from dataclasses import asdict, replace
from pathlib import Path

from bench.agentpii2.schema import (
    Case,
    ExpectedCall,
    Negative,
    PiiItem,
    Source,
    ToolSchema,
    validate,
)

CACHE: Path = Path.home() / ".cache" / "pseudex-bench"
DATA: Path = CACHE / "voice_addresses.json"

# The hydration key. `line` is the row's `n` — its 1-based position in the
# annotated set, which is also its position in the deterministic candidate list
# `bench/voice/annotate.py` builds. The digest is what actually protects the
# offsets: if the filter or the underlying dump ever shifts by one row, every
# span in this family points at the wrong utterance, and `hydrate` refuses
# instead of scoring.
CORPUS_NAME: str = "voice_addresses"
LICENCE: str = "CC BY-NC 4.0"

# 17 addresses + 15 bare streets + 64 remaining negatives. Asserted at build
# time so a change in the annotation is a loud failure rather than a quietly
# smaller family.
SPEECH_CASE_COUNT: int = 96

# WHAT THE ANNOTATOR DID NOT DRAW. `bench/voice` hand-marks the boundary of the
# seventeen addresses that carry a house number, because полнота («did it fire»)
# and покрытие («did it take the whole thing») came apart on seven of them and
# the difference is the half that leaked. It draws nothing for the bare streets,
# which needed no boundary when the measure was one label per utterance. This
# family scores spans, so the fifteen boundaries are drawn here, by the same
# rule: the street name and its type word, and nothing a person said around it.
#
# KEYED BY THE UTTERANCE'S OWN CONTENT HASH, never by its position. A hand-drawn
# boundary belongs to a TEXT; keying it by a row number binds it to a selection
# instead, and widening that selection then moves every label onto the wrong
# utterance while every check still passes.
#
# Uniqueness inside its own utterance is asserted at build time — a span that
# occurs twice cannot be located by searching, and a wrong offset scores.
BARE_SPANS: dict[str, str] = {
    "0d89b1819d21": "улица пушкина",
    "932600463829": "улица бронетранспортёрная",
    "21dfe7f9bd32": "улица филикаспековская",
    "de97834b0520": "улица пушкина",
    "9df43930b64a": "улица пушкина",
    "6d725164e767": "улица пушкина",
    "8485f65b53da": "абакинская улица",
    "abba8c01cb4b": "улица лермонтова",
    "73db255d8ec0": "улица пушкина",
    "51620ebefa71": "пионерском бульваре",
    "a2423ade9dc2": "керамзитобетонная улица",
    "559f34c1f469": "улица пушкина",
    "35a9ab1d3d82": "милашекова улицу",
    "e0bb7f091374": "улица новосибирская",
    "5558d067d553": "улица лермонтова",
}

# The same two vocabularies `bench/voice/annotate.py` used to SELECT these
# utterances out of 12 950. Restated rather than imported because they live
# inside that module's `candidates()`, and restating them keeps the claim exact:
# the negative names the very word that put the utterance in the set.
_STREET_WORD = (r"улиц\w*|проспект\w*|переул\w*|бульвар\w*|шоссе|набережн\w*"
                r"|площад\w*|проезд\w*|микрорайон\w*|мкр|тупик\w*|аллея"
                r"|квартал\w*")
_HOUSE_WORD = r"дом|корпус|квартир\w*|подъезд\w*|этаж\w*|строени\w*"
_LEXICON = re.compile(rf"\b(?:{_STREET_WORD}|{_HOUSE_WORD})\b", re.IGNORECASE)
_WORD = re.compile(r"[а-яёa-z]+", re.IGNORECASE)
_TOKEN_AFTER = re.compile(r"\s+\S+")
_TOKEN_BEFORE = re.compile(r"\S+\s+$")

_PLAIN_WHY = "адресное слово без адреса — реплика размечена как «не адрес»"

# TWO UTTERANCES WHERE THE NEGATIVE MUST REACH THE NAME NEXT TO THE LEXICON
# WORD. Claiming only «улицы» in «на территории улицы лермонтова» would miss the
# failure that actually happens: «лермонтова» is a surname, and a gateway that
# masks it as a person leaves «улицы» untouched and escapes the claim. Everywhere
# else the single word is enough — masking a wider span always covers it — and
# extending by default would reach «дом даги длиннорукого» or «от борисовны»,
# where the neighbouring word IS a person and masking it is not an error.
_EXTEND: dict[str, tuple[str, str]] = {
    "ef51c1e6091d": ("after", "название улицы вне адреса — на территории, а не по адресу"),
    "59d8bb5b4641": ("before", "городская площадь как ориентир, не адрес"),
}

# ONE VALUE FOR THE WHOLE FAMILY, because difficulty is not a dimension here.
# The design doc crosses it inside `transfer` only — elsewhere the family IS the
# difficulty — and the field has no «not applicable» member, so a spread of
# values would invent a gradient the annotation never drew and let a reader slice
# a difficulty curve out of what is really the source's own variety.
_DIFFICULTY: str = "hard"

# The operator turn between two paired utterances. It exists for the wire
# format, not for realism: some providers refuse two consecutive user messages
# and others MERGE them, and a merged pair concatenates two messages into one —
# which moves every offset in the second one and scores wrongly and silently.
# It carries no data, so nothing about it is a claim.
_OPERATOR_TURN: str = "Слушаю вас."

_SYSTEM: str = ("Ты оператор, принимающий заявки по телефону. Если клиент "
                "называет адрес, вызови register_address и передай адрес "
                "дословно, как он прозвучал.")


def _tool() -> ToolSchema:
    """A fresh dict per case: the schemas travel into a JSON corpus and into a
    provider call, and one shared mutable object would let a scorer's edit reach
    every case in the family."""
    return {
        "type": "function",
        "function": {
            "name": "register_address",
            "description": "Записать адрес клиента в заявку.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Адрес клиента дословно, как он прозвучал",
                    },
                },
                "required": ["address"],
            },
        },
    }


# WHICH SELECTION THIS FAMILY IS ANNOTATED AGAINST, and why it is named rather
# than assumed. `bench/voice/annotate.py` now emits TWO populations out of the
# same 12 950 transcripts:
#
#   marker  122 utterances admitted because they hold a street-type word or a
#           house marker — the selection this family's spans were drawn on.
#   number  1 251 more, admitted by a provable superset (an address with a house
#           number must contain a number), which found 26 further real addresses.
#
# The second is the more honest population and it is NOT used here yet, which is
# a limitation this family must state rather than hide: the `marker` filter
# shares its signals with the detector, so a corpus built on it can only ever
# show cases the detector already handles. Reported coverage 100% is true
# coverage 38.6% once the superset is admitted. Moving is a deliberate
# re-annotation — the bare-street boundaries below are hand-drawn per utterance
# — not a constant edit, so it stays a decision somebody makes on purpose.
_SELECTION: str = "marker"

# THE IDENTITY OF THAT SELECTION, pinned. `n` below is a POSITION in the filtered
# list and positions are exactly what made the previous file un-widenable:
# changing the filter renumbered every row and invalidated every label without
# breaking a single check. Two things stop that being silent now. The annotation
# tables above are keyed by the row's own content hash, so a reorder cannot move
# a span onto the wrong utterance; and this digest pins the ordered selection, so
# a reorder cannot quietly renumber the case ids either. `n` survives only as the
# thing that NAMES a case and orders the pairing, never as what binds an
# annotation to a text.
_SELECTION_DIGEST: str = (
    "979ec970516e92c9d52e51083573d7d681a77687658435a7fc2eca3a01a8693d")


def _rows() -> list[dict[str, object]]:
    if not DATA.exists():
        raise FileNotFoundError(
            f"{DATA} is missing — the `speech` family is not generated, it is "
            f"hand-annotated real speech. Rebuild it with: "
            f"python3 bench/fetch_ru_speech.py --only calls && "
            f"python3 bench/voice/annotate.py")
    everything = json.loads(DATA.read_text(encoding="utf-8"))
    rows = [row for row in everything if row.get("filter") == _SELECTION]
    if not rows:
        raise ValueError(
            f"{DATA} holds no row with filter={_SELECTION!r}; the annotation "
            f"changed shape and this family's 32 hand-drawn spans were drawn "
            f"against the old one")
    digest = hashlib.sha256(
        "".join(str(row["key"]) for row in rows).encode("utf-8")).hexdigest()
    if digest != _SELECTION_DIGEST:
        raise ValueError(
            f"the {_SELECTION!r} selection now hashes to {digest[:12]}, this "
            f"family is annotated against {_SELECTION_DIGEST[:12]} — "
            f"{len(rows)} rows are present and the case ids no longer name the "
            f"utterances they named. Re-annotate deliberately; do not renumber.")
    out: list[dict[str, object]] = []
    for position, row in enumerate(rows, 1):
        spans = row.get("spans", [])
        if not isinstance(spans, list):
            raise TypeError(f"row {row['key']} carries a non-list `spans`")
        # ONE UTTERANCE MAY HOLD TWO ADDRESSES — «ферганская один у нас находится
        # миронова пятьдесят восемь» is two — so the annotation is a LIST and the
        # case builder walks it. A scorer that took one string per row would drop
        # the second address and score the leak as a pass.
        out.append({"key": str(row["key"]), "n": position,
                    "label": str(row["label"]), "text": str(row["text"]),
                    "spans": spans})
    return out


def resolve_source(corpus: str, line: int) -> str:
    """The text behind one `Source`. The signature is `schema.hydrate`'s
    `resolve(corpus, line)`, so a scorer that hydrates the whole corpus through
    one callable can dispatch this family here by `corpus`."""
    if corpus != CORPUS_NAME:
        raise ValueError(f"{corpus!r} is not this family's corpus "
                         f"({CORPUS_NAME!r})")
    for row in _rows():
        if row["n"] == line:
            return str(row["text"])
    raise ValueError(f"{CORPUS_NAME} has no line {line}; the annotation shifted "
                     f"and every offset in this family is now suspect")


def hydrated(cases: list[Case]) -> list[Case]:
    """The cases with their licensed text filled in, for validation and scoring.

    NOT `schema.hydrate`, and both reasons are defects in it rather than
    preferences here. It rebuilds the case through `Case(**asdict(case))`, which
    turns every nested `PiiItem` into a plain dict, so the result cannot be
    validated or scored; and it keeps the `source` key beside the text it just
    filled in, which trips the same validator's rule that a message naming a
    licensed source must ship empty. Dropping `source` is what makes a hydrated
    case a validatable case rather than a licence violation waiting to be
    committed.
    """
    filled: list[Case] = []
    for case in cases:
        messages: list[dict[str, object]] = []
        for message in case.messages:
            source = message.get("source")
            if not isinstance(source, dict):
                messages.append(dict(message))
                continue
            text = resolve_source(str(source["corpus"]), int(source["line"]))
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest != source["sha256"]:
                raise ValueError(
                    f"{case.id}: {source['corpus']} line {source['line']} hashes "
                    f"to {digest[:12]}, the corpus expects "
                    f"{str(source['sha256'])[:12]} — the annotation shifted "
                    f"under the offsets")
            messages.append({"role": message["role"], "content": text})
        filled.append(replace(case, messages=messages))
    return filled


def _source(row: dict[str, object]) -> dict[str, object]:
    text = str(row["text"])
    return asdict(Source(
        corpus=CORPUS_NAME,
        line=int(row["n"]),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        licence=LICENCE))


def _locate(text: str, span: str, row_number: int) -> tuple[int, int]:
    """Offsets for a span in text this module did not assemble.

    Everywhere else in the corpus offsets are computed DURING assembly, because
    searching a finished string finds the first occurrence and a message that
    says the same thing twice then carries a span pointing at the wrong one.
    Here the text is a transcript nobody assembled, so searching is the only
    option — and the rule is kept by refusing any span that is not unique in its
    own utterance.
    """
    occurrences = text.count(span)
    if occurrences != 1:
        raise ValueError(
            f"utterance {row_number}: {span!r} occurs {occurrences} times in "
            f"{text!r}; a span located by search must be unique or the offsets "
            f"are a guess")
    start = text.index(span)
    return start, start + len(span)


def _negatives(row: dict[str, object], message: int) -> list[Negative]:
    """The address vocabulary in an utterance that holds no address.

    THE CLAIM IS THE WORD, NOT THE UTTERANCE, and that is a licence constraint
    rather than a measurement choice: `bench/voice` scores «did anything fire in
    this reply», which would mean carrying every one of the 79 transcripts
    verbatim inside `Negative.value`, and the corpus may not ship them. Claiming
    the vocabulary word instead keeps the same catch for every plausible failure
    — a span that covers «улицы лермонтова» covers «улицы» — and gives up only
    the case where a gateway masks something in the utterance that has nothing to
    do with an address.

    A NEGATIVE NEVER SHARES A MESSAGE WITH A PII ITEM. «улица филикаспековская
    дом» would otherwise claim both that its street MAY be masked and that the
    «дом» beside it MAY NOT, and a gateway taking the natural maximal span would
    be right and wrong at once. The bare-street utterances therefore carry their
    negative in a separate turn.
    """
    text, key = str(row["text"]), str(row["key"])
    row_number = int(row["n"])
    extension = _EXTEND.get(key)
    matches = list(_LEXICON.finditer(text))
    if not matches:
        raise ValueError(f"utterance {row_number} has no address vocabulary, yet "
                         f"that is what selected it into the set: {text!r}")
    if extension and len(matches) != 1:
        raise ValueError(f"utterance {row_number} is marked for extension but "
                         f"holds {len(matches)} vocabulary words; the extension "
                         f"names one of them and can no longer say which")
    out: list[Negative] = []
    seen: set[str] = set()
    for match in matches:
        start, end = match.span()
        why = _PLAIN_WHY
        if extension:
            direction, why = extension
            if direction == "after":
                tail = _TOKEN_AFTER.match(text, end)
                if tail is None:
                    raise ValueError(f"utterance {row_number}: nothing follows "
                                     f"{match.group()!r} to extend to")
                end = tail.end()
            else:
                head = _TOKEN_BEFORE.search(text[:start])
                if head is None:
                    raise ValueError(f"utterance {row_number}: nothing precedes "
                                     f"{match.group()!r} to extend to")
                start = head.start()
        value = text[start:end]
        if value in seen:
            continue
        seen.add(value)
        out.append(Negative(value=value, why=why, msg=message))
    return out


def _address_case(row: dict[str, object]) -> Case:
    """A spoken address that carries a house number: `required`, and a tool
    consumes it.

    `canonical` IS the surface form. A CRM would store «улица Лермонтова, 38»,
    but nobody in this pipeline converts «тридцать восемь» into digits and
    demanding it back would score the gateway on a normalisation no leg of the
    product performs — v1's own lesson, that the ground truth is the canonical
    form of WHAT WAS SAID.
    """
    number = int(row["n"])
    text = str(row["text"])
    spans = [str(span) for span in row["spans"]]
    if not spans:
        raise ValueError(f"utterance {number} is labelled an address and the "
                         f"annotation draws no boundary for it")
    # ONE ITEM PER ANNOTATED ADDRESS, each with its OWN identity. Two addresses
    # in one utterance are two places, and giving them one identity would demand
    # a single substitute for both — which is the merge the corpus exists to
    # catch, manufactured by us instead of by the gateway.
    items = [
        PiiItem(
            id=f"addr{index}",
            type="LOC",
            value=span,
            start=_locate(text, span, number)[0],
            end=_locate(text, span, number)[1],
            canonical=span,
            msg=1,
            identity=f"place{index}",
            duty="required",
            tool_param="address",
        )
        for index, span in enumerate(spans)
    ]
    return Case(
        id=f"speech_addr_{number:03d}",
        family="speech",
        scenario="call_address",
        register="voice_raw",
        difficulty=_DIFFICULTY,
        length_rung="short",
        conversation_id="",
        relation="equality",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "source": _source(row)},
        ],
        tools=[_tool()],
        pii=items,
        preceded_by="",
        annotators=1,
        adjudicated=False,
        # ONE CALL PER ADDRESS. `register_address` takes one address, so an
        # utterance naming two demands two calls — not one argument holding both,
        # which would make `same_value` compare a concatenation and pass a
        # gateway that lost either half.
        calls=[ExpectedCall(
            name="register_address",
            after_msg=1,
            arguments={"address": entry.value},
            pii_items=[entry.id],
        ) for entry in items],
    )


def _street_case(row: dict[str, object],
                 companion: dict[str, object]) -> Case:
    """A bare street — `optional` — travelling with a real negative utterance.

    The companion is what makes the case falsifiable; the street is measured in
    its own column and can fail nothing. It is chosen so the two utterances share
    no long word, because two mentions of the same street inside one conversation
    are exactly what the engine's conversation scope is built to LINK, and a
    false mask manufactured by our pairing would be charged to the gateway.
    """
    number = int(row["n"])
    text = str(row["text"])
    span = BARE_SPANS[str(row["key"])]
    start, end = _locate(text, span, number)
    item = PiiItem(
        id="street",
        type="LOC",
        value=span,
        start=start,
        end=end,
        canonical=span,
        msg=0,
        identity="place",
        duty="optional",
        tool_param=None,
    )
    return Case(
        id=f"speech_street_{number:03d}",
        family="speech",
        scenario="call_street_no_house",
        register="voice_raw",
        difficulty=_DIFFICULTY,
        length_rung="short",
        conversation_id="",
        relation="equality",
        messages=[
            {"role": "user", "source": _source(row)},
            {"role": "assistant", "content": _OPERATOR_TURN},
            {"role": "user", "source": _source(companion)},
        ],
        tools=[],
        pii=[item],
        preceded_by="",
        annotators=1,
        adjudicated=False,
        negatives=_negatives(companion, 2),
    )


def _plain_case(row: dict[str, object]) -> Case:
    """Address vocabulary, no address. The half of the set no generator writes."""
    number = int(row["n"])
    return Case(
        id=f"speech_plain_{number:03d}",
        family="speech",
        scenario="call_no_address",
        register="voice_raw",
        difficulty=_DIFFICULTY,
        length_rung="short",
        conversation_id="",
        relation="equality",
        messages=[{"role": "user", "source": _source(row)}],
        tools=[],
        pii=[],
        preceded_by="",
        annotators=1,
        adjudicated=False,
        negatives=_negatives(row, 0),
    )


def _long_words(text: str) -> set[str]:
    """Words long enough to be a street name, minus the vocabulary every one of
    these utterances shares. Five letters is deliberately generous — it rejects
    far more pairings than it has to, and with 79 candidates for 15 slots the
    cost of being over-strict is nothing while the cost of one missed collision
    is a link the corpus itself manufactured."""
    return {word for word in _WORD.findall(text.lower())
            if len(word) >= 5 and not _LEXICON.fullmatch(word)}


def _stratified(groups: list[list[Case]]) -> list[Case]:
    """One order whose every PREFIX holds the three classes in proportion.

    `count` is honoured by cutting this order, never by sampling: a tier drawn
    from a prefix must not be all addresses because addresses were built first,
    and a re-drawn sample would answer a different question under the same name
    every time the family grows.
    """
    keyed: list[tuple[float, int, Case]] = []
    for rank, group in enumerate(groups):
        for index, case in enumerate(group):
            keyed.append(((index + 0.5) / len(group), rank, case))
    keyed.sort(key=lambda row: (row[0], row[1]))
    return [case for _, _, case in keyed]


def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases, in a frozen order.

    `rng` IS ACCEPTED AND DELIBERATELY NOT USED, which is the opposite of every
    other family and follows from this one having nothing to draw. The 122
    utterances are fixed, the annotation is fixed, and the only free choice — which
    negative accompanies which bare street — decides nothing that is measured:
    each utterance is claimed exactly once whichever way it falls. Drawing it from
    the seed would move fifteen case ids and fifteen negatives between cases on
    every regeneration, so the corpus's one non-synthetic family would stop being
    comparable to its own previous version to buy nothing. Same argument the tier
    ladder makes for freezing rather than re-sampling.

    THE FAMILY IS BOUNDED BY ITS SOURCE. 122 people said these things once;
    asking for more than the annotation holds is asking for text nobody said, so
    it raises rather than padding the real set with generated speech — which is
    the one thing this family exists not to be.
    """
    if count <= 0:
        raise ValueError(f"count must be positive, got {count}")
    rows = sorted(_rows(), key=lambda row: int(row["n"]))
    addresses = [row for row in rows if row["label"] == "адрес с номером"]
    streets = [row for row in rows if row["label"] == "улица без номера"]
    plain = [row for row in rows if row["label"] == "не адрес"]

    # A companion for every bare street, drawn from the negatives and removed
    # from the pool: an utterance scored twice would count one annotation as two
    # measurements. First fit in annotation order — see the note on `rng` above.
    taken: set[int] = set()
    pairs: list[tuple[dict[str, object], dict[str, object]]] = []
    for street in streets:
        street_words = _long_words(str(street["text"]))
        for candidate in plain:
            if int(candidate["n"]) in taken:
                continue
            if street_words & _long_words(str(candidate["text"])):
                continue
            taken.add(int(candidate["n"]))
            pairs.append((street, candidate))
            break
        else:
            raise ValueError(
                f"utterance {street['n']} found no companion sharing none of its "
                f"words; pairing it anyway would put one street in a "
                f"conversation twice and charge the resulting link to the gateway")

    cases = _stratified([
        [_address_case(row) for row in addresses],
        [_street_case(street, companion) for street, companion in pairs],
        [_plain_case(row) for row in plain if int(row["n"]) not in taken],
    ])
    if len(cases) != SPEECH_CASE_COUNT:
        raise ValueError(f"the annotation now yields {len(cases)} cases, not "
                         f"{SPEECH_CASE_COUNT}; the family's arithmetic is "
                         f"published and a silent change is a different corpus")
    if count > len(cases):
        raise ValueError(
            f"the `speech` family holds {len(cases)} cases and {count} were "
            f"asked for: it is 122 hand-annotated real utterances, not a "
            f"generator, and the missing cases do not exist")
    return cases[:count]


def main() -> int:
    cases = build(random.Random(20260830), SPEECH_CASE_COUNT)
    filled = hydrated(cases)
    problems = [problem for case in filled for problem in validate(case)]

    scenarios: dict[str, int] = {}
    for case in cases:
        scenarios[case.scenario] = scenarios.get(case.scenario, 0) + 1
    required = sum(1 for case in filled for item in case.pii
                   if item.duty == "required")
    optional = sum(1 for case in filled for item in case.pii
                   if item.duty == "optional")
    negatives = sum(len(case.negatives) for case in filled)
    longest = max(sum(len(str(message.get("content", "")))
                      for message in case.messages) for case in filled)

    print(f"speech: {len(cases)} cases")
    for scenario, number in sorted(scenarios.items()):
        print(f"   {scenario:<22} {number}")
    print(f"   required items         {required}")
    print(f"   optional items         {optional}")
    print(f"   negatives              {negatives}")
    print(f"   longest case           {longest} characters")
    print(f"   validate() problems    {len(problems)}")
    for problem in problems[:20]:
        print(f"      {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
