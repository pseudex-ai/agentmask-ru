"""The v5 mock backend: the customer's systems, in each API's OWN notation.

WHAT THIS ADDS TO v4's `Backend`, and why each piece exists.

1. EVERY TOOL RETURNS SOMETHING REAL. 22 of v4's 31 tools answered with an id
   and a status, because v4 only asked whether the agent called them right.
   v5 also measures the IN/tool hop — the value coming BACK through the gateway
   — so `_enrich` gives each of those the result its API actually returns (CDEK
   answers a cancellation with the recipient, amoCRM answers an upsert with the
   card, Okdesk answers an escalation with the assignee). A tool with nothing
   in its result has no hop to measure, which is rule V04.

2. THE NOTATION IS THE MEASUREMENT. A DaData canon («г Самара, ул Луговая,
   д 10»), a courier's dotted line («г. Ижевск, ул. Пушкина, д. 41, кв. 7»), an
   ISO birth date, «XXX-XXX-XXX YY», a card in four groups, «+7 (916) 402-11-87»
   — these are not decoration, they are what the substitute has to wear on the
   way in. Rendering everything the way the customer wrote it would make the
   IN/tool hop unfailable and therefore worthless.

3. SLOT TAGS ARE ITEM IDS. v4 tagged result slots with private names
   («c0_phone») that nothing outside the mock could map to a case's datum. Here
   every slot that renders a SEEDED item carries that item's id, the echoed
   value of a `ForcedError` carries `ECHO_TAG_PREFIX + id`, and a tag that
   resolves to no item is dropped rather than left behind — the observer looks
   up `spans_real[item_id]` and nothing else, and a stray tag would read as a
   hop that the case never declared. One tag per item per result: a `dict`
   holds one span per key, so a value rendered twice is tagged once.

4. A VALUE INSIDE PROSE HAS ITS OWN SPAN. `writer.Slot` tags a whole JSON
   string, and a ticket history carries three people inside one sentence. The
   prose is assembled with v4's `Writer` — never searched afterwards, the rule
   v1 learned the hard way — and `_expand_prose` lifts its inner offsets onto
   the serialised result, then removes the outer tag.

5. THE FORCED ERROR MAKES A RETRY DETERMINISTIC WITH A LIVE AGENT. Waiting for
   the model to make a mistake would leave the `retry_same_tool` family with an
   unmeasured denominator.

NOTHING HERE IMPORTS `pseudex`: the mock is the customer's system, and a mock
that shared the engine's validators would make the instrument part of the
detector.
"""
import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from bench.agentpii4.mock import Backend, CallLog, Record
from bench.agentpii4.tools import CSV_HEADER, Refusal
from bench.agentpii4.writer import Slot, Writer, serialise
from bench.agentpii5.contracts import (ACTING_OUT_OWNERS, ECHO_TAG_PREFIX,
                                       PIECE_MIN_CHARS, PIECE_MIN_DIGITS, CaseV5,
                                       ForcedError)
# V05 (`_transition_problems`) asks the question the RUN will ask, so it asks it
# with the run's own comparator rather than a second one written here: two folds
# for «the same value» would have to stay equal for ever, and the one that
# drifted would let the build prove a hand-over the metric then scores as broken.
from bench.agentpii5.metrics import role_matches
from bench.agentpii5.tools import (NEW_REGISTRY, csv_row_path, expected_leaf_value,
                                   field_at, spec_v5_for)

# The tables the twelve new tools read. v4's thirteen stay exactly as they are.
NEW_TABLES: tuple[str, ...] = (
    "kb_chunks", "documents", "bank_clients", "vehicles", "snils_records",
    "calendar", "ticket_events", "emails")
# A value shorter than this is not indexed for tagging by VALUE: «7», «12» and
# «41» occur in half the records of a seeded world, and a tag put on the wrong
# record is worse than no tag — the observer would score a hop on someone
# else's datum. Values reached through (table, id, path) are exact and are not
# subject to this floor.
MIN_TAGGED_VALUE: int = 3
# The v4 tools whose v5 enrichment re-tags the whole result off the RECORD each
# row came out of. `_retag`'s by-value guess must not run over them first: it
# would consume the item into `_used` and the exact map would then answer "".
# Both are the tools a case seeds SEVERAL near-identical rows of — a merge of
# one person's two cards, three suggestions of one street — which is precisely
# where by value is ambiguous and drops the tag.
RECORD_TAGGED: tuple[str, ...] = ("crm_find_contact", "address_suggest")
# The `contacts` columns `crm_find_contact` answers with, in amoCRM's order.
# Named once: the row builder and the node builder must not drift apart.
CONTACT_COLUMNS: tuple[str, ...] = (
    "last_name", "first_name", "middle_name", "phone", "email", "birth_date")
# The columns a CSV document carries, in `CSV_HEADER`'s order. Named once for
# the same reason: `_document_pieces` renders them as prose and `_file_read`
# answers them as a table, and a column present in one and not the other would
# be an item tagged in one reading of the same file and untagged in the other.
CSV_COLUMNS: tuple[str, ...] = ("last_name", "first_name", "phone", "email", "birth_date")
# The id prefix a ticket is minted under, so that `ticket_history` can read
# back what `ticket_create` wrote — see `BackendV5._next_id` (ruling R-26).
# `tools.ISSUE_ID_RE` is the reader; the two must agree, and this is the side
# that moved because the regex is the tool's documented contract.
TICKET_ID_PREFIX: str = "t"
# A prose template's slot, and everything a reader would MISTAKE for one. The
# split keeps the group, so `SLOT.split` alternates literal and slot; anything
# that looks like a slot and is not one is refused by name in
# `_template_pieces` rather than passed through as text (ruling R-28).
SLOT: re.Pattern[str] = re.compile(r"(\{[a-z_]+\})")
BRACE_RUN: re.Pattern[str] = re.compile(r"\{[^{}]*\}")
DOCTORS: dict[str, str] = {
    "терапевт": "Соколов Андрей", "невролог": "Лапина Вера", "хирург": "Мамедов Руслан",
    "кардиолог": "Соколов Андрей", "офтальмолог": "Титова Ольга"}
DUTY_OPERATOR: tuple[str, str] = ("Соколов Андрей", "+79261234567")
# The four Cyrillic letters an OCR confuses with a Latin look-alike, and the
# rates the scan register uses. Kept here rather than in the scenario, because
# a document's noise must be the same in every arm of the same case.
SCAN_LOOKALIKE: dict[str, str] = {"о": "o", "а": "a", "е": "e", "с": "c"}
SCAN_LETTER_RATE: float = 0.05
SCAN_SPACE_RATE: float = 0.03
# What a query must carry before the index decides it NAMES a seeded person.
# Four letters is the stem a Russian word keeps through its six cases
# («Ерохину» → «ерохин», «Тарасовой» → «тарасов»); three would let «пет» pull
# in every Пётр and Петрова the index holds. Six digits is below a phone, an
# ИНН and a СНИЛС and above a house number and a year, so «дом 41» names
# nobody. The tail is what makes one number one number in every notation:
# «8 903 765 43 21» and «+79037654321» share their last ten digits and
# disagree before them.
IDENTITY_STEM: int = 4
IDENTITY_DIGITS: int = 6
IDENTITY_DIGIT_TAIL: int = 10
_QUERY_WORD: re.Pattern[str] = re.compile(r"[^\W\d_]+", re.UNICODE)


def digits_of(text: str) -> str:
    return "".join(character for character in text if character.isdigit())


def fold_word(word: str) -> str:
    return word.casefold().replace("ё", "е")


def identity_stems(value: str) -> tuple[str, ...]:
    """The word stems a seeded value stays recognisable by once a model has
    declined it. Short words are dropped rather than shortened: a two-letter
    stem matches half the language."""
    return tuple(fold_word(word)[:IDENTITY_STEM] for word in _QUERY_WORD.findall(value)
                 if len(word) >= IDENTITY_STEM)


def identity_digits(value: str) -> str:
    """The digit signature a seeded number is recognisable by, or "" when the
    number is too short to name anybody."""
    digits = digits_of(value)
    if len(digits) > IDENTITY_DIGIT_TAIL:
        return digits[-IDENTITY_DIGIT_TAIL:]
    return digits if len(digits) >= IDENTITY_DIGITS else ""


def phone_canon(value: str) -> str:
    """«+7 (916) 402-11-87» — the DaData / directory notation, and the one a
    user register never writes. Anything that is not eleven digits is returned
    untouched: a normaliser that mangles is measuring itself (v4, `normalize_
    contact`)."""
    digits = digits_of(value)
    if len(digits) != 11:
        return value
    return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def snils_spaced(value: str) -> str:
    digits = digits_of(value)
    if len(digits) != 11:
        return value
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"


def card_grouped(value: str) -> str:
    digits = digits_of(value)
    if len(digits) != 16:
        return value
    return " ".join(digits[start:start + 4] for start in range(0, 16, 4))


def canon_layout(city: str, street: str, house: str,
                 flat: str) -> tuple[tuple[str, str], ...]:
    """DaData's «г Самара, ул Луговая, д 10, кв 7» — no dots after the generic
    abbreviations, comma-separated, the house marked «д» — as an alternation of
    (text, column): "" for a literal, and the `addresses` column a value came
    from for a value.

    THE SPELLING IS ONE DEFINITION AND THE TAGGING IS ANOTHER. The same canon is
    rendered from a record the mock holds (tagged exactly) and from parts the
    agent sent (tagged by value, because there is no record); writing the
    commas and the «ул » twice is how the two renderings start to differ.
    """
    pieces: list[tuple[str, str]] = []
    if city:
        pieces.extend((("г ", ""), (capitalised(city), "city")))
    if street:
        pieces.append(((", " if pieces else "") + "ул ", ""))
        pieces.append((capitalised(street), "street"))
    if house:
        pieces.append(((", " if pieces else "") + "д ", ""))
        pieces.append((str(house), "house"))
    if flat:
        pieces.append((", кв ", ""))
        pieces.append((str(flat), "flat"))
    return tuple(pieces)


def _csv_rows(record: Record) -> tuple[tuple[str, dict[str, object]], ...]:
    """The people a CSV document carries, in row order, with the key each one
    is tagged under.

    A MAPPING KEYED BY THE ORDINAL RATHER THAN A LIST (`tools.csv_row_path`):
    v4's seed validator walks «.» alone and a path through a list resolved to
    None, which is how 310 items shipped with the written surface «None». The
    order is the key read as a number, so a row can never be rendered under
    another row's tag because two keys sorted as text.
    """
    rows = record.fields.get("rows")
    if not isinstance(rows, dict):
        raise KeyError(f"documents/{record.id}: neither a template nor rows to render")
    return tuple((key, dict(value))                       # type: ignore[arg-type]
                 for key, value in sorted(rows.items(), key=lambda pair: int(pair[0])))


def capitalised(value: str) -> str:
    """«пушкина» → «Пушкина», «красная площадь» → «Красная площадь». NOT
    `title()`: ФИАС keeps «Красная площадь» with one capital, and a directory
    that invents a second one is reporting a spelling nobody uses."""
    return value[:1].upper() + value[1:] if value else value


# HOW A VALUE IS WRITTEN INSIDE PROSE, by the name of the field that holds it.
# A note, a ticket history and a document each put a phone in the notation the
# system that wrote them uses, and that notation is what the IN hop measures.
PROSE_NOTATION: dict[str, Callable[[str], str]] = {
    "phone": phone_canon, "snils": snils_spaced, "card": card_grouped}
MONTHS_GENITIVE: tuple[str, ...] = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря")


def slot_iso(date: str, hour: str) -> str:
    return f"{date}T{hour}:00+03:00"


def slot_dotted(date: str, hour: str) -> str:
    year, month, day = date.split("-")
    return f"{day}.{month}.{year} {hour}"


def slot_words(date: str, hour: str) -> str:
    year, month, day = date.split("-")
    return f"{int(day)} {MONTHS_GENITIVE[int(month) - 1]}, {hour}"


def slot_compact(date: str, hour: str) -> str:
    return f"{date} {hour}"


# The notations one calendar hands back in one answer. Four, so the draw has
# something to choose from; two per answer, so a date form always has a
# disagreement to find.
SLOT_NOTATIONS: tuple[Callable[[str, str], str], ...] = (
    slot_iso, slot_dotted, slot_words, slot_compact)


def scan_noise(text: str, rng: random.Random) -> str:
    """OCR damage, seeded by the document id so every arm reads the same page.

    At least one substitution is FORCED: a noise generator that may return a
    clean page would make the `scan` format a coin toss, and a case declaring
    it would sometimes measure the plain register instead."""
    out: list[str] = []
    touched = False
    for character in text:
        lower = character.lower()
        if lower in SCAN_LOOKALIKE and rng.random() < SCAN_LETTER_RATE:
            latin = SCAN_LOOKALIKE[lower]
            out.append(latin.upper() if character.isupper() else latin)
            touched = True
        elif character == " " and rng.random() < SCAN_SPACE_RATE:
            out.append("  ")
        else:
            out.append(character)
    if touched:
        return "".join(out)
    for index, character in enumerate(out):
        lower = character.lower()
        if lower in SCAN_LOOKALIKE:
            latin = SCAN_LOOKALIKE[lower]
            out[index] = latin.upper() if character.isupper() else latin
            return "".join(out)
    return "".join(out)


class BackendV5(Backend):
    """v4's backend with the eight new tables, the twelve new tools, the return
    forms, item-id slot tags and the scripted errors."""

    def __init__(self, now_iso: str, forced: tuple[ForcedError, ...],
                 echo_values: dict[str, str]) -> None:
        super().__init__(now_iso)
        for table in NEW_TABLES:
            self._tables[table] = {}
        self._forced = tuple(forced)
        self._echo = dict(echo_values)
        self._items: dict[tuple[str, str, str], str] = {}
        self._by_value: dict[str, str] = {}
        self._by_digits: dict[str, str] = {}
        self._signatures: list[tuple[str, tuple[str, ...], str]] = []
        self._ambiguous: set[str] = set()
        self._used: set[str] = set()
        self._prose: dict[str, tuple[tuple[str, int, int], ...]] = {}
        self._last_form = ""
        self._attempts: dict[str, int] = {}
        self.forms: list[str] = []

    def _next_id(self, table: str, prefix: str) -> str:
        """v4's id allocator, with ONE table renamed (ruling R-26).

        THE WRITER AND THE READER OF `tickets` DISAGREED. `ticket_create`
        minted «tkt-1» (v4, where nothing ever read a ticket id back), while
        `ticket_history` — Okdesk's `GET /issues/{id}/comments` — accepts
        `tools.ISSUE_ID_RE`, «t-N». So an agent that opened a ticket and then
        asked for its history was refused for an id our own mock had just
        handed it, and the `sequential_chain` family had to seed «t-1» by hand
        to take its second step.

        THE PREFIX MOVES, NOT THE READER'S REGEX: «t-» is the id shape the
        tool's schema shows the model and the one its documentation names, and
        widening `ISSUE_ID_RE` to accept both would document a format neither
        Okdesk nor we use. v4's `mock.py` is the frozen baseline and is not
        edited; this override is the v5 subclass's own allocation rule, and it
        touches no other table.
        """
        return super()._next_id(table, TICKET_ID_PREFIX if table == "tickets" else prefix)

    # --- seeding ---------------------------------------------------------

    def seed_record(self, table: str, record_id: str, fields: dict[str, object]) -> None:
        """One row of any table, seeded. `seq == 0`, so `snapshot()` keeps
        treating it as state the world started with rather than an effect."""
        if table not in self._tables:
            raise KeyError(f"unknown table {table!r}; tables are {sorted(self._tables)}")
        self._tables[table][record_id] = Record(table, record_id, "seed", 0, dict(fields))

    def seed_chunk(self, chunk_id: str, fields: dict[str, object]) -> None:
        self.seed_record("kb_chunks", chunk_id, fields)

    def seed_document(self, document_id: str, fields: dict[str, object]) -> None:
        self.seed_record("documents", document_id, fields)

    def seed_bank_client(self, client_id: str, fields: dict[str, object]) -> None:
        self.seed_record("bank_clients", client_id, fields)

    def seed_vehicle(self, vehicle_id: str, fields: dict[str, object]) -> None:
        self.seed_record("vehicles", vehicle_id, fields)

    def seed_snils(self, record_id: str, fields: dict[str, object]) -> None:
        self.seed_record("snils_records", record_id, fields)

    def seed_calendar(self, record_id: str, fields: dict[str, object]) -> None:
        self.seed_record("calendar", record_id, fields)

    def seed_ticket_event(self, record_id: str, fields: dict[str, object]) -> None:
        self.seed_record("ticket_events", record_id, fields)

    def seed_item(self, table: str, record_id: str, path: str, item_id: str) -> None:
        """Bind one seeded field to the case's `PiiItem` id. Two maps come out
        of it: the exact one (table, id, path), used where the mock holds the
        record, and a by-VALUE one, used where a v4 branch produced the slot
        and only the string is known. A value that two items share is dropped
        from the by-value map: an ambiguous tag would put a hop on the wrong
        person, and no tag is the honest answer."""
        record = self._tables[table][record_id]
        text = str(field_at(record.fields, path))
        if not text:
            raise ValueError(f"item {item_id}: seed {table}/{record_id}.{path} is empty")
        self._items[(table, record_id, path)] = item_id
        # THE THIRD INDEX IS THE ONE A SEARCH USES. The two below answer «which
        # item is this exact string», which is a tagging question; a query is
        # written by a model and arrives declined and renotated, so membership
        # in the knowledge base is decided on stems and a digit signature
        # (`identities_in`).
        self._signatures.append((item_id, identity_stems(text), identity_digits(text)))
        for key, index in ((text.lower(), self._by_value), (digits_of(text), self._by_digits)):
            if len(key) < MIN_TAGGED_VALUE:
                continue
            if key in self._ambiguous:
                continue
            if key in index and index[key] != item_id:
                self._ambiguous.add(key)
                del index[key]
                continue
            index[key] = item_id

    # --- calls -----------------------------------------------------------

    def call(self, tool: str, arguments: dict[str, object]) -> CallLog:
        attempt = self._attempts.get(tool, 0)
        self._attempts[tool] = attempt + 1
        self._used = set()
        self._prose = {}
        self._last_form = ""
        forced = self._forced_error(tool, attempt)
        if forced is not None:
            log = self._forced_call(tool, forced)
            form = "error_with_value"
        else:
            # THE TWELVE ARE NAMED, THE REST GO THROUGH v4 UNCHANGED. The test
            # used to be `tool in V4_REGISTRY`, and `tools.py` now widens that
            # very dict with the twelve (ruling R-24) — so the old test sent a
            # v5 tool down v4's path and the condition silently stopped meaning
            # what it said. Asking `NEW_REGISTRY` keeps the answer a property of
            # this package rather than of another package's mutated global.
            log = self._call_new(tool, arguments) if tool in NEW_REGISTRY \
                else super().call(tool, arguments)
            form = self._form_of_log(log)
        self._expand_prose(log)
        self.forms.append(form)
        return log

    def form_of(self, seq: int) -> str:
        """The return form of the call with this `CallLog.seq`."""
        for index, log in enumerate(self.calls):
            if log.seq == seq:
                return self.forms[index]
        raise KeyError(f"no call with seq {seq}; seen {[log.seq for log in self.calls]}")

    def _forced_error(self, tool: str, attempt: int) -> ForcedError | None:
        """A refusal IS an attempt: the ordinal counts every call of the tool,
        parsed or not, because the scripted error scripts the ATTEMPT and an
        agent whose first try was malformed would otherwise get the error on
        its second and the case would measure a different family."""
        for forced in self._forced:
            if forced.tool_name == tool and forced.call_ordinal == attempt:
                return forced
        return None

    def _forced_call(self, tool: str, forced: ForcedError) -> CallLog:
        if forced.message_template.count("{value}") != 1:
            raise ValueError(f"{tool}: message_template needs exactly one {{value}} slot, "
                             f"got {forced.message_template!r}")
        if forced.echo_item_id not in self._echo:
            raise KeyError(f"{tool}: no echo value for item {forced.echo_item_id!r}; "
                           f"have {sorted(self._echo)}")
        value = self._echo[forced.echo_item_id]
        head, tail = forced.message_template.split("{value}")
        message = self._compose(((head, ""), (value, ECHO_TAG_PREFIX + forced.echo_item_id),
                                 (tail, "")), "")
        data: dict[str, object] = {"error": {"code": forced.code, "message": message.text}}
        node: dict[str, object] = {"error": {"code": forced.code, "message": message}}
        self._seq += 1
        text, spans = serialise(node)
        log = CallLog(tool, self._seq, None, None, data, text, spans)
        self.calls.append(log)
        return log

    def _call_new(self, tool: str, arguments: dict[str, object]) -> CallLog:
        spec = NEW_REGISTRY[tool]
        parsed = spec.parse(arguments)
        self._seq += 1
        if isinstance(parsed, Refusal):
            result = parsed.as_error()
            text, spans = serialise(result)
            log = CallLog(tool, self._seq, None, parsed, result, text, spans)
        else:
            result, node = self._apply(tool, parsed)
            text, spans = serialise(node)
            log = CallLog(tool, self._seq, parsed, None, result, text, spans)
        self.calls.append(log)
        return log

    def _form_of_log(self, log: CallLog) -> str:
        if log.refusal is not None:
            # `Refusal.as_error` puts the offending argument into the message,
            # so a documented rejection IS an error carrying a value — the
            # slice `toolresult_masked` needs it counted as one.
            return "error_with_value"
        if not self._last_form:
            raise KeyError(f"{log.tool}: the result was built without recording a return form")
        return self._last_form

    # --- tagging and prose -------------------------------------------------

    def _tag_for_value(self, text: str) -> str:
        """The item id a rendered string belongs to, or "". Matched on the
        lower-cased string and, for anything with enough digits, on the digit
        signature alone — «+79164021187» and «+7 (916) 402-11-87» are one
        datum in two notations, and the notation is exactly what the API just
        changed."""
        if not text:
            return ""
        item = self._by_value.get(text.lower(), "")
        if not item:
            digits = digits_of(text)
            if len(digits) >= 6:
                item = self._by_digits.get(digits, "")
        if not item or item in self._used:
            return ""
        self._used.add(item)
        return item

    def _slot(self, text: str) -> object:
        tag = self._tag_for_value(text)
        return Slot(text, tag) if tag else text

    def _tag_of(self, record: Record, path: str) -> str:
        """The item id bound to a field of a record the mock is holding: the
        exact map, no guessing by value."""
        item = self._items.get((record.table, record.id, path), "")
        if not item or item in self._used:
            return ""
        self._used.add(item)
        return item

    def _slot_of(self, record: Record, path: str, text: str) -> object:
        if not text:
            return text
        tag = self._tag_of(record, path)
        return Slot(text, tag) if tag else text

    def _piece(self, text: str) -> tuple[str, str]:
        return text, self._tag_for_value(text)

    def _compose(self, pieces: Sequence[tuple[str, str]], whole: str) -> Slot:
        """Assemble one string out of tagged and untagged pieces; `whole` is the
        item the FINISHED string belongs to, or "" when it belongs to nobody.

        A `Slot` carries ONE tag for a whole JSON string and an address in a
        courier's notation carries three values inside one line, so the offsets
        are taken from v4's `Writer` as the string GROWS and lifted onto the
        result in `_expand_prose`. Nothing is ever searched for afterwards.

        `whole` EXISTS BECAUSE A COMPOSED STRING CAN ITSELF BE A SEEDED FIELD.
        DaData's `suggestions[].value` is the address row's own `value` column
        rendered in the directory's notation: the street inside it is one item
        and the line is another, and before `whole` the line's item had no span
        at all — the hop the corpus declared on `suggestions[].value` could
        never be observed. The two spans overlap on purpose; that is the truth
        about a street inside an address.
        """
        writer = Writer()
        for text, tag in pieces:
            if not text:
                continue
            writer.put(text, tag)
        text, spans, _trace = writer.finish()
        outer = f"prose:{len(self._prose)}"
        inner = [(tag, start, end) for tag, (start, end) in spans.items()]
        if whole and text:
            inner.append((whole, 0, len(text)))
        self._prose[outer] = tuple(inner)
        return Slot(text, outer)

    def _expand_prose(self, log: CallLog) -> None:
        for outer, inner in self._prose.items():
            if outer not in log.result_spans:
                raise KeyError(f"{log.tool}: composed string {outer!r} did not reach the result")
            base = log.result_spans.pop(outer)[0]
            for tag, start, end in inner:
                log.result_spans[tag] = (base + start, base + end)

    def _retag(self, node: object) -> object:
        """v4's private slot tags («c0_phone») replaced by item ids, and
        dropped where no item answers: the v5 observer resolves by item id
        only, and a tag that resolves to nothing would read as a hop the case
        never declared."""
        if isinstance(node, Slot):
            tag = self._tag_for_value(node.text)
            return Slot(node.text, tag) if tag else node.text
        if isinstance(node, dict):
            return {key: self._retag(value) for key, value in node.items()}
        if isinstance(node, list):
            return [self._retag(value) for value in node]
        return node

    # --- addresses in the notation of each API -----------------------------

    def _canon_parts(self, city: str, street: str, house: str, flat: str) -> tuple[tuple[str, str], ...]:
        """DaData's canon with the tag guessed from the VALUE — for the callers
        that hold no record (`normalize_contact` normalises what the agent
        sent, `delivery_quote` composes a pickup point)."""
        return tuple((text, self._tag_for_value(text) if column else "")
                     for text, column in canon_layout(city, street, house, flat))

    def _canon_parts_of(self, record: Record, city: str, street: str, house: str,
                        flat: str) -> tuple[tuple[str, str], ...]:
        """The same canon, tagged from the RECORD the row came out of.

        BY VALUE IS THE GUESS THAT FAILS EXACTLY WHERE THIS FAMILY LIVES. The
        address fan-out seeds three rows of one street («Дзержинского 44»,
        «44а», another city), so `_by_value` calls the street ambiguous and
        drops it from both — and every hop the corpus declares on
        `suggestions[].data.street` becomes a crossing no gateway could be
        scored on. The (table, id, path) map has no such ambiguity and is what
        `seed_item` built it for.
        """
        return tuple((text, self._tag_of(record, column) if column else "")
                     for text, column in canon_layout(city, street, house, flat))

    def _courier_parts(self, city: str, street: str, house: str, flat: str) -> tuple[tuple[str, str], ...]:
        """CDEK / Boxberry track: «г. Ижевск, ул. Пушкина, д. 41, кв. 7» — the
        dots and the space after each marker are the courier's own spelling,
        and telling it apart from the directory's canon is half of what the
        LOC form features exist for."""
        pieces: list[tuple[str, str]] = []
        if city:
            pieces.extend((("г. ", ""), self._piece(capitalised(city))))
        if street:
            pieces.append(((", " if pieces else "") + "ул. ", ""))
            pieces.append(self._piece(capitalised(street)))
        if house:
            pieces.append(((", " if pieces else "") + "д. ", ""))
            pieces.append(self._piece(str(house)))
        if flat:
            pieces.append((", кв. ", ""))
            pieces.append(self._piece(str(flat)))
        return tuple(pieces)

    def _address_fields(self, fields: dict[str, object]) -> tuple[str, str, str, str]:
        """city / street / house / flat out of whichever spelling a table uses
        (`locality`+`building`+`sflat` is Yandex Delivery's, `city`+`house`+
        `flat` is the CRM's)."""
        city = str(fields.get("city") or fields.get("locality") or "")
        street = str(fields.get("street") or "")
        house = str(fields.get("house") or fields.get("building") or "")
        flat = str(fields.get("flat") or fields.get("sflat") or "")
        return city, street, house, flat

    # --- dispatch ----------------------------------------------------------

    def _apply(self, tool: str, parsed: dict[str, object]) -> tuple[dict[str, object], object]:
        if tool in NEW_REGISTRY:
            data, node, form = self._apply_new(tool, parsed)
        else:
            data, node = super()._apply(tool, parsed)
            if tool not in RECORD_TAGGED:
                node = self._retag(node)
            data, node, form = self._enrich(tool, parsed, data, node)
        self._last_form = form
        return data, node

    def _error(self, code: str, subject: object) -> tuple[dict[str, object], object, str]:
        """A 200 with an error body that ECHOES the offending value, the way a
        real service names what it could not find. `_domain_error` of v4 put a
        bare string there; here the subject is a slot, so the value inside an
        error is a hop like any other — the form `error_with_value` exists for
        exactly this."""
        text = subject if isinstance(subject, str) else str(subject)
        return ({"error": {"code": code, "subject": text}},
                {"error": {"code": code, "subject": self._slot(text)}},
                "error_with_value")

    def _error_slot(self, code: str, slot: Slot) -> tuple[dict[str, object], object, str]:
        return ({"error": {"code": code, "subject": slot.text}},
                {"error": {"code": code, "subject": slot}},
                "error_with_value")

    # --- the v4 tools: the result their API actually returns -----------------

    def _enrich(self, tool: str, parsed: dict[str, object], data: dict[str, object],
                node: object) -> tuple[dict[str, object], object, str]:
        """What v4 left out of each result, and the form the call came back in.

        v4 answered a write with an id and a status because it never scored
        what came BACK. Every block added here is one a real API returns —
        CDEK names the recipient on a cancellation, amoCRM returns the card it
        updated, Okdesk names the assignee — and each one gives its tool the
        IN/tool hop that rule V04 asks for."""
        if "error" in data:
            return data, node, "error_with_value"
        if not isinstance(node, dict):
            raise TypeError(f"{tool}: v4 returned a non-object result node {node!r}")
        if tool == "delivery_create_order":
            return data, node, "single"
        if tool == "courier_book":
            address_fields = parsed["address"]
            city, street, house, flat = self._address_fields(address_fields)   # type: ignore[arg-type]
            address = self._compose(self._courier_parts(city, street, house, flat), "")
            contact = parsed["contact"]
            name, phone = str(contact["name"]), str(contact["phone"])          # type: ignore[index]
            data["contact"] = {"name": name, "phone": phone}
            data["address"] = address.text
            node["contact"] = {"name": self._slot(name), "phone": self._slot(phone)}
            node["address"] = address
            return data, node, "nested"
        if tool == "address_suggest":
            suggestions = data["suggestions"]
            if not isinstance(suggestions, list) or not suggestions:
                return data, {"suggestions": []}, "empty"
            # THE ROW NAMES ITS OWN RECORD AND IS NOT SEARCHED FOR. `fias_id` is
            # the directory key DaData answers with and it is unique per seeded
            # row, so the record a suggestion came out of is read off the
            # suggestion rather than guessed from the street it prints.
            by_fias = {str(record.fields.get("fias_id", "")): record
                       for record in self._tables["addresses"].values()}
            nodes: list[object] = []
            for row in suggestions:
                fields = dict(row["data"])                                     # type: ignore[index]
                record = by_fias.get(str(fields.get("fias_id", "")))
                if record is None:
                    raise KeyError(f"address_suggest: suggestion "
                                   f"{fields.get('fias_id')!r} belongs to no seeded row")
                canon = self._compose(self._canon_parts_of(
                    record, str(fields["city"]), str(fields["street"]),
                    str(fields["house"]), str(fields.get("flat", ""))),
                    self._tag_of(record, "value"))
                row["value"] = canon.text                                      # type: ignore[index]
                nodes.append({"value": canon,
                              "confidence": f"{float(row['confidence']):.2f}",  # type: ignore[index]
                              "data": {key: str(value) for key, value in fields.items()}})
            # ONE ANSWER IS A NORMALISATION, SEVERAL ARE A CHOICE — the agent
            # has to act differently, so the form says which it got.
            return data, {"suggestions": nodes}, "canon" if len(nodes) == 1 else "list"
        if tool == "payment_create":
            customer = self._customer_of(parsed.get("receipt"))
            data["receipt"] = {"customer": dict(customer)}
            node["receipt"] = {"customer": {key: self._slot(value)
                                            for key, value in customer.items()}}
            return data, node, "single"
        if tool == "passport_verify":
            person, passport = parsed["person"], parsed["passport"]
            block = {"last_name": str(person["last_name"]),                    # type: ignore[index]
                     "first_name": str(person["first_name"])}                  # type: ignore[index]
            papers = {"series": str(passport["series"]),                       # type: ignore[index]
                      "number": str(passport["number"])}                       # type: ignore[index]
            # МВД answers with the СНИЛС in ITS spelling, «XXX-XXX-XXX YY»,
            # whatever the caller sent — the notation the IN hop measures.
            snils = snils_spaced(str(parsed["snils"]))
            data["person"], data["passport"], data["snils"] = block, papers, snils
            node["person"] = {key: self._slot(value) for key, value in block.items()}
            node["passport"] = {key: self._slot(value) for key, value in papers.items()}
            node["snils"] = self._slot(snils)
            return data, node, "single"
        if tool == "clinic_book":
            patient = parsed["patient"]
            block = {name: str(patient[name])                                  # type: ignore[index]
                     for name in ("last_name", "first_name", "birth_date")}
            data["patient"] = block
            data["phone"] = parsed["phone"]
            node["patient"] = {key: self._slot(value) for key, value in block.items()}
            node["phone"] = self._slot(str(parsed["phone"]))
            return data, node, "single"
        if tool == "clinic_slots":
            name = self._doctor_for(str(parsed["speciality"]))
            data["doctor"] = {"name": name}
            node["doctor"] = {"name": self._slot(name)}
            return data, node, "list"
        if tool in ("appointment_cancel", "appointment_reschedule"):
            record = self._tables["appointments"][str(data["appointment_id"])]
            patient = record.fields.get("patient") or {}
            block = {name: str(patient.get(name, ""))                          # type: ignore[union-attr]
                     for name in ("last_name", "first_name")}
            data["patient"] = block
            node["patient"] = {key: self._slot_of(record, f"patient.{key}", value)
                               for key, value in block.items()}
            return data, node, "single"
        if tool == "referral_create":
            patient = parsed["patient"]
            block = {name: str(patient[name])                                  # type: ignore[index]
                     for name in ("last_name", "first_name", "birth_date")}
            data["patient"] = block
            node["patient"] = {key: self._slot(value) for key, value in block.items()}
            return data, node, "single"
        if tool == "crm_find_contact":
            contacts = data["contacts"]
            if not isinstance(contacts, list) or not contacts:
                return data, {"contacts": []}, "empty"
            # REBUILT OFF THE RECORDS, not off v4's by-value node. A support
            # case that seeds one person TWICE (the merge families do, and so
            # does every «я заведён два раза») makes every column of both cards
            # ambiguous by value, and v4's tags then resolve to nothing at all
            # — 45 revised cases whose whole tool result was untagged.
            rows: list[object] = []
            for row in contacts:
                record = self._tables["contacts"][str(row["id"])]              # type: ignore[index]
                built: dict[str, object] = {"id": row["id"]}                   # type: ignore[index]
                for column in CONTACT_COLUMNS:
                    built[column] = self._slot_of(record, column,
                                                  str(row.get(column, "")))    # type: ignore[union-attr]
                address = row.get("address") or {}                             # type: ignore[union-attr]
                built["address"] = {
                    "city": str(address.get("city", "")),                      # type: ignore[union-attr]
                    "street": self._slot_of(record, "address.street",
                                            str(address.get("street", ""))),   # type: ignore[union-attr]
                    "house": self._slot_of(record, "address.house",
                                           str(address.get("house", ""))),     # type: ignore[union-attr]
                    "flat": str(address.get("flat", ""))} if address else {}   # type: ignore[union-attr]
                rows.append(built)
            return data, {"contacts": rows}, "list"
        if tool == "crm_upsert_contact":
            record = self._tables["contacts"][str(data["id"])]
            block = {name: str(record.fields.get(name, ""))
                     for name in ("last_name", "first_name", "phone")}
            data["contact"] = block
            node["contact"] = {key: self._slot_of(record, key, value)
                               for key, value in block.items()}
            return data, node, "single"
        if tool == "crm_merge_contacts":
            record = self._tables["contacts"][str(data["primary_id"])]
            block = {name: str(record.fields.get(name, ""))
                     for name in ("last_name", "first_name", "phone")}
            data["contact"] = block
            node["contact"] = {key: self._slot_of(record, key, value)
                               for key, value in block.items()}
            return data, node, "single"
        if tool == "crm_add_note":
            record = self._tables["contacts"].get(str(data["entity_id"]))
            block = {name: str(record.fields.get(name, "")) if record else ""
                     for name in ("last_name", "first_name", "phone")}
            data["entity"] = block
            node["entity"] = {key: (self._slot_of(record, key, value) if record else value)
                              for key, value in block.items()}
            return data, node, "single"
        if tool == "crm_import_csv":
            written = [record for record in self._tables["contacts"].values()
                       if record.seq == self._seq and record.tool == tool]
            rows: list[dict[str, object]] = []
            row_nodes: list[object] = []
            for record in written:
                row = {"id": record.id}
                row.update({name: str(record.fields.get(name, ""))
                            for name in ("last_name", "first_name", "phone", "email",
                                         "birth_date")})
                rows.append(row)
                row_nodes.append({key: (value if key == "id"
                                        else self._slot_of(record, key, str(value)))
                                  for key, value in row.items()})
            data["rows"] = rows
            node["rows"] = row_nodes
            return data, node, "list"
        if tool == "crm_segment_report":
            buckets: list[dict[str, object]] = []
            bucket_nodes: list[object] = []
            for bucket in data["buckets"]:                                     # type: ignore[union-attr]
                sample_record = self._contact_in_city(str(bucket["bucket"]))   # type: ignore[index]
                block = {name: str(sample_record.fields.get(name, "")) if sample_record else ""
                         for name in ("last_name", "first_name", "phone")}
                row = {**bucket, "sample": block}                              # type: ignore[dict-item]
                buckets.append(row)
                bucket_nodes.append({"bucket": str(bucket["bucket"]),          # type: ignore[index]
                                     "count": int(bucket["count"]),            # type: ignore[index,arg-type]
                                     "sample": {key: (self._slot_of(sample_record, key, value)
                                                      if sample_record else value)
                                                for key, value in block.items()}})
            data["buckets"] = buckets
            node["buckets"] = bucket_nodes
            return data, node, "list"
        if tool == "send_template":
            variables = parsed["variables"]
            rows = [{"key": key, "text": str(value)}
                    for key, value in variables.items()]                       # type: ignore[union-attr]
            data["parameters"] = rows
            node["parameters"] = [{"key": str(row["key"]), "text": self._slot(str(row["text"]))}
                                  for row in rows]
            return data, node, "list"
        if tool == "notify_sms":
            data["number"] = parsed["number"]
            node["number"] = self._slot(str(parsed["number"]))
            return data, node, "single"
        if tool == "callback_schedule":
            data["phone"], data["at"] = parsed["phone"], parsed["at"]
            node["phone"] = self._slot(str(parsed["phone"]))
            node["at"] = str(parsed["at"])
            return data, node, "single"
        if tool == "order_status":
            return data, node, "single"
        if tool in ("order_cancel", "order_reschedule"):
            record = self._tables["orders"][str(data["uuid"])]
            recipient = record.fields.get("recipient") or {}
            phones = recipient.get("phones") or [""]                           # type: ignore[union-attr]
            name, phone = str(recipient.get("name", "")), str(phones[0])       # type: ignore[union-attr]
            data["recipient"] = {"name": name, "phone": phone}
            node["recipient"] = {"name": self._slot_of(record, "recipient.name", name),
                                 "phone": self._slot_of(record, "recipient.phones[0]", phone)}
            if tool == "order_reschedule":
                location = record.fields.get("to_location") or {}
                address = str(location.get("address", ""))                     # type: ignore[union-attr]
                data["to_location"] = {"address": address}
                node["to_location"] = {"address": self._slot_of(
                    record, "to_location.address", address)}
            return data, node, "single"
        if tool == "delivery_quote":
            record = self._address_in_city(str(parsed["city"]))
            if record is None:
                data["pickup_point"] = {"address": ""}
                node["pickup_point"] = {"address": ""}
                return data, node, "single"
            city, street, house, flat = self._address_fields(record.fields)
            canon = self._compose(self._canon_parts(city, street, house, ""), "")
            data["pickup_point"] = {"address": canon.text}
            node["pickup_point"] = {"address": canon}
            return data, node, "single"
        if tool == "pickup_points_near":
            points = data["points"]
            return data, node, "list" if isinstance(points, list) and points else "empty"
        if tool == "normalize_contact":
            if "phone" in node:
                formatted = phone_canon(str(data["phone"]["e164"]))            # type: ignore[index]
                data["phone"]["formatted"] = formatted                         # type: ignore[index]
                node["phone"]["formatted"] = self._slot(formatted)             # type: ignore[index]
            if "address" in node:
                block = data["address"]
                canon = self._compose(self._canon_parts(
                    "", str(block["street"]), str(block["house"]), ""), "")     # type: ignore[index]
                block["value"] = canon.text                                     # type: ignore[index]
                node["address"]["value"] = canon                                # type: ignore[index]
            return data, node, "canon"
        if tool == "payment_refund":
            record = self._tables["payments"][str(data["payment_id"])]
            customer = self._customer_of(record.fields.get("receipt"))
            data["receipt"] = {"customer": dict(customer)}
            node["receipt"] = {"customer": {key: self._slot_of(
                record, f"receipt.customer.{key}", value) for key, value in customer.items()}}
            return data, node, "single"
        if tool in ("payment_status", "receipt_fetch"):
            return data, node, "single"
        if tool == "ticket_create":
            phone = str(parsed.get("phone", ""))
            record = self._contact_by_phone(phone)
            name = self._full_name(record) if record else ""
            data["requester"] = {"name": name, "phone": phone}
            node["requester"] = {"name": self._slot(name), "phone": self._slot(phone)}
            return data, node, "single"
        if tool == "ticket_find":
            issues = data["issues"]
            if not isinstance(issues, list) or not issues:
                return data, node, "empty"
            rows = []
            row_nodes = []
            for index, issue in enumerate(issues):
                ticket = self._tables["tickets"][str(issue["ticket_id"])]
                phone = str(ticket.fields.get("phone", ""))
                contact = self._contact_by_phone(phone)
                name = self._full_name(contact) if contact else ""
                rows.append({**issue, "requester": {"name": name, "phone": phone}})
                base = node["issues"][index]                                   # type: ignore[index]
                row_nodes.append({**base, "requester": {"name": self._slot(name),
                                                        "phone": self._slot(phone)}})
            data["issues"] = rows
            node["issues"] = row_nodes
            return data, node, "list"
        if tool == "escalate_to_human":
            name, phone = self._duty_operator()
            data["assignee"] = {"name": name, "phone": phone}
            node["assignee"] = {"name": self._slot(name), "phone": self._slot(phone)}
            return data, node, "single"
        raise KeyError(f"{tool}: no v5 return form declared for a v4 tool")

    # --- small readers the enrichment shares --------------------------------

    def _customer_of(self, receipt: object) -> dict[str, str]:
        if not isinstance(receipt, dict):
            return {}
        customer = receipt.get("customer")
        if not isinstance(customer, dict):
            return {}
        return {str(key): str(value) for key, value in customer.items() if value}

    def _full_name(self, record: Record) -> str:
        parts = [str(record.fields.get(name, ""))
                 for name in ("last_name", "first_name", "middle_name")]
        return " ".join(capitalised(part) for part in parts if part)

    def _contact_by_phone(self, phone: str) -> Record | None:
        if not phone:
            return None
        digits = digits_of(phone)
        for record in self._tables["contacts"].values():
            if digits_of(str(record.fields.get("phone", ""))) == digits:
                return record
        return None

    def _contact_in_city(self, city: str) -> Record | None:
        for record in self._tables["contacts"].values():
            address = record.fields.get("address") or {}
            if str(address.get("city", "")).lower() == city.lower():           # type: ignore[union-attr]
                return record
        return None

    def _address_in_city(self, city: str) -> Record | None:
        for record in self._tables["addresses"].values():
            if str(record.fields.get("city", "")).lower() == city.lower():
                return record
        return None

    def _doctor_for(self, speciality: str) -> str:
        """The clinic always names whose window it is. A seeded doctor (a
        contact with `role` = doctor) wins; otherwise the duty name for the
        speciality, which is a person the case did not label and is therefore
        rendered untagged."""
        for record in self._tables["contacts"].values():
            if str(record.fields.get("role", "")) == "doctor":
                return self._full_name(record)
        return DOCTORS[speciality]

    def _duty_operator(self) -> tuple[str, str]:
        for record in self._tables["contacts"].values():
            if str(record.fields.get("role", "")) == "operator":
                return self._full_name(record), str(record.fields.get("phone", ""))
        return DUTY_OPERATOR

    # --- the twelve new tools ------------------------------------------------

    def _template_pieces(self, record: Record, rng: random.Random | None
                         ) -> tuple[tuple[str, str], ...]:
        """A seeded prose record as (text, tag) pieces: the literals of its
        `template` and the values its `{field}` slots name, each rendered in
        the notation that field carries in prose (a phone as «+7 (916) …», a
        СНИЛС with separators, a card in groups) and tagged with the item id
        bound to that field. `rng` is the scan noise, applied to each PIECE
        before it is written — never to the assembled string, whose offsets are
        already laid down (v1's bug, twice).

        A SLOT NAME IS `[a-z_]+`, AND A NAME OUTSIDE IT IS REFUSED HERE
        (ruling R-28). «{who2}» is not a slot this splitter sees: the template
        would keep it as literal text, the record's `who2` column would never
        be rendered, and every hop and `ReturnExpectation` declared on it would
        be a crossing that never happened — scored as a gateway miss no gateway
        could avoid. It has already cost one family (`test_generator_b.
        test_declared_returns_are_tagged` caught it), so the brace run is
        checked BEFORE the split and named with its record: a seed that names
        a slot the renderer cannot reach is a corpus defect, and the corpus is
        built once while a silent literal is read for ever.
        """
        template = str(record.fields["template"])
        for brace in BRACE_RUN.findall(template):
            if SLOT.fullmatch(brace):
                continue
            raise KeyError(f"{record.table}/{record.id}: {brace} is not a slot — a slot name is "
                           f"[a-z_]+, so this stays literal text and the column it names is "
                           f"never rendered")
        pieces: list[tuple[str, str]] = []
        for part in SLOT.split(template):
            if not part:
                continue
            if part.startswith("{") and part.endswith("}"):
                name = part[1:-1]
                if name not in record.fields:
                    raise KeyError(f"{record.table}/{record.id}: template names {name!r}, "
                                   f"which the record does not carry")
                notation = PROSE_NOTATION.get(name)
                text = str(record.fields[name])
                text = notation(text) if notation is not None else text
                pieces.append((scan_noise(text, rng) if rng is not None else text,
                               self._tag_of(record, name)))
            else:
                pieces.append((scan_noise(part, rng) if rng is not None else part, ""))
        return tuple(pieces)

    def _ranked(self, table: str, query: str, limit: int) -> tuple[tuple[float, Record], ...]:
        """Word-overlap ranking, the same one v4's `address_suggest` uses: a
        substitute that matches fewer words ranks lower, which is the effect
        the fan-out families are built to see."""
        words = [word for word in query.lower().replace(",", " ").split() if len(word) > 2]
        scored: list[tuple[float, Record]] = []
        for record in self._tables[table].values():
            haystack = " ".join(str(value) for value in record.fields.values()).lower()
            hits = sum(1 for word in words if word in haystack)
            if hits:
                scored.append((hits / max(1, len(words)), record))
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        return tuple(scored[:limit])

    def identities_in(self, query: str) -> frozenset[str]:
        """The seeded items a query NAMES, in whatever form the model wrote them.

        A stem match survives the six Russian cases, a digit signature survives
        every notation of a phone — and those are the two ways the same person
        is written by an agent that was not copying.

        THE OBSERVER'S `needles_of` IS NOT IMPORTED HERE. The world is upstream
        of the measurement: a retriever that matched by the metric's own rule
        would make a change to the metric silently change what the customer's
        index answers. The two agree because both are the same four-letter
        stem, and each is pinned on its own side.
        """
        words = [fold_word(word) for word in _QUERY_WORD.findall(query)]
        digits = digits_of(query)
        return frozenset(
            item_id for item_id, stems, signature in self._signatures
            if (signature and signature in digits)
            or any(word.startswith(stem) for stem in stems for word in words))

    def _by_identity(self, query: str, count: int) -> tuple[tuple[float, Record], ...]:
        """The chunks a query retrieves because it NAMES somebody the index knows.

        MEMBERSHIP IS AN IDENTITY, NOT A WORD (F4.5). `_ranked` alone decided
        it, and «Ерохину Петру» — the dative an agent writes after «по клиенту»
        — matched nothing: the declared chunk hops did not happen, the declared
        `chunks` form came back `empty`, and `toolresult_masked` counted the
        call anyway and scored a miss. Retrieval was a property of the model's
        phrasing and the gateway was charged for it.

        THE SCORE STILL ORDERS, THIS ONLY ADMITS: it runs where word overlap
        found nothing at all, so a query that matched a record keeps the
        ranking `_ranked` gave it.
        """
        records = sorted(self._tables["kb_chunks"].values(), key=lambda record: record.id)
        named = self.identities_in(query)
        if not named or not records:
            return ()
        carriers: dict[str, set[str]] = {}
        for (table, record_id, _path), item_id in self._items.items():
            if table == "kb_chunks":
                carriers.setdefault(record_id, set()).add(item_id)
        own = [record for record in records if named & carriers.get(record.id, set())]
        if own:
            return tuple((0.0, record) for record in own)[:count]
        # THE NAMED IDENTITY IS THE CUSTOMER'S OWN, whose card is in the CRM and
        # not in the knowledge base — the index still answers about her, with
        # the chunks of the kind the first record wears. Mixing a note with an
        # index row would make one of the two return forms unreachable, which is
        # the same reason `_retrieved` pads inside one kind.
        prose = "template" in records[0].fields
        return tuple((0.0, record) for record in records
                     if ("template" in record.fields) == prose)[:count]

    def _document_at_path(self, path: str) -> Record | None:
        for record in self._tables["documents"].values():
            if str(record.fields.get("path", "")) == path:
                return record
        return None

    def _document_pieces(self, record: Record) -> tuple[tuple[str, str], ...]:
        """A document as running prose.

        CSV ROWS ARE JOINED WITH « | », NOT WITH A NEWLINE, and that is a
        constraint of the instrument rather than of JSON: `writer._escape_free`
        refuses a control character inside a slot, because an escaped value no
        longer equals the span that was laid down for it. A document read as
        TEXT is therefore one line; a document read as a TABLE comes back as
        `file_read`'s `list` form, with a row per record and no joining at all."""
        fmt = str(record.fields.get("format", "free_text"))
        rng = random.Random(f"scan:{record.id}") if fmt == "scan" else None
        if "template" in record.fields:
            return self._template_pieces(record, rng)
        pieces: list[tuple[str, str]] = [(CSV_HEADER, "")]
        for row_key, row in _csv_rows(record):
            for key in CSV_COLUMNS:
                pieces.append((" | " if key == "last_name" else ";", ""))
                value = str(row.get(key, ""))
                pieces.append((value, self._tag_of(record, csv_row_path(row_key, key))))
        return tuple(pieces)

    def _calendar_slots(self, record: Record, date: str) -> tuple[str, ...]:
        """Free windows, written in at least TWO notations.

        The draw chooses WHICH two, never whether there are two: a calendar
        that might answer in one notation would make `form_hIN[DATE]` a coin
        toss, and the case declaring it would sometimes measure nothing."""
        rng = random.Random(f"calendar:{record.id}:{date}")
        first = rng.randrange(len(SLOT_NOTATIONS))
        second = (first + 1 + rng.randrange(len(SLOT_NOTATIONS) - 1)) % len(SLOT_NOTATIONS)
        hours = ("09:30", "11:00", "14:15", "16:45")
        chosen = (SLOT_NOTATIONS[first], SLOT_NOTATIONS[second])
        return tuple(chosen[index % 2](date, hour) for index, hour in enumerate(hours))

    def _apply_new(self, tool: str, parsed: dict[str, object]
                   ) -> tuple[dict[str, object], object, str]:
        if tool == "kb_search":
            return self._kb_search(str(parsed["query"]), int(parsed["k"]))    # type: ignore[arg-type]
        if tool == "doc_retrieve":
            record = self._tables["documents"].get(str(parsed["doc_id"]))
            if record is None:
                return ({"doc_id": parsed["doc_id"], "found": False},
                        {"doc_id": str(parsed["doc_id"]), "found": False}, "empty")
            body = self._compose(self._document_pieces(record), "")
            head = {"doc_id": str(parsed["doc_id"]), "title": str(record.fields.get("title", "")),
                    "format": str(record.fields.get("format", "free_text"))}
            return {**head, "body": body.text}, {**head, "body": body}, "free_text"
        if tool == "file_read":
            return self._file_read(str(parsed["path"]))
        if tool == "form_parse":
            return self._form_parse(str(parsed["text"]))
        if tool == "bank_client_find":
            return self._bank_client_find(parsed)
        if tool == "account_statement":
            return self._account_statement(parsed)
        if tool == "vehicle_check":
            return self._vehicle_check(str(parsed["plate"]))
        if tool == "snils_verify":
            return self._snils_verify(str(parsed["snils"]))
        if tool == "calendar_free":
            return self._calendar_free(str(parsed["person"]), str(parsed["date"]))
        if tool == "email_send":
            return self._email_send(parsed)
        if tool == "ticket_history":
            return self._ticket_history(str(parsed["issue_id"]))
        if tool == "courier_status":
            return self._courier_status(str(parsed["claim_id"]))
        raise KeyError(tool)

    def _retrieved(self, ranked: Sequence[tuple[float, Record]],
                   count: int) -> tuple[tuple[float, Record], ...]:
        """`ranked` padded to `count` out of the index: RANKING DECIDES THE
        ORDER, NOT THE MEMBERSHIP.

        `_ranked` drops every record with no word overlap, and that turned the
        `rag` family's payload into a property of the model's phrasing: a query
        of «фамилия имя» returned one chunk of five and 257 of the 350 declared
        chunk hops simply did not happen — free credit on `leak`, and
        `rag_masked` denominators that moved when the agent rephrased. A real
        top-k retriever returns `k` and lets the score sort them.

        WHAT STILL DECIDES MEMBERSHIP IS WHAT THE QUERY FOUND: nothing is
        retrieved for a query that matched no seeded record at all, and the
        padding is of the SAME KIND as the matches — prose notes beside prose
        notes, index rows beside index rows. Padding across the two would make
        `kb_search`'s `list` form unreachable in any index that also holds a
        note, because text wins whenever both are present.
        """
        if not ranked:
            return ()
        prose = any("template" in record.fields for _score, record in ranked)
        already = {record.id for _score, record in ranked}
        rest = sorted((record for record in self._tables["kb_chunks"].values()
                       if record.id not in already
                       and ("template" in record.fields) == prose),
                      key=lambda record: record.id)
        return (tuple(ranked) + tuple((0.0, record) for record in rest))[:count]

    def _kb_search(self, query: str, count: int) -> tuple[dict[str, object], object, str]:
        ranked = self._ranked("kb_chunks", query, count)
        if not ranked:
            ranked = self._by_identity(query, count)
        hits = self._retrieved(ranked, count)
        notes = [(score, record) for score, record in hits if "template" in record.fields]
        if notes:
            # A NOTE AND A CARD ARE BOTH IN THE INDEX, and Elasticsearch hands
            # back whatever `_source` it stored. Text wins when both matched:
            # the RAG families are about prose, and a run that sometimes
            # answered them with rows would measure a different hop.
            rows: list[dict[str, object]] = []
            nodes: list[object] = []
            for score, record in notes:
                text = self._compose(self._template_pieces(record, None), "")
                rows.append({"id": record.id, "score": round(score, 2), "text": text.text})
                nodes.append({"id": record.id, "score": f"{score:.2f}", "text": text})
            return ({"query": query, "total": len(rows), "hits": rows},
                    {"query": query, "total": len(rows), "hits": nodes}, "chunks")
        if not hits:
            return ({"query": query, "total": 0, "hits": []},
                    {"query": query, "total": 0, "hits": []}, "empty")
        rows = []
        nodes = []
        for _score, record in hits:
            row = {"id": record.id, "name": str(record.fields.get("name", "")),
                   "phone": phone_canon(str(record.fields.get("phone", ""))),
                   "address": str(record.fields.get("address", ""))}
            rows.append(row)
            nodes.append({"id": record.id,
                          "name": self._slot_of(record, "name", str(row["name"])),
                          "phone": self._slot_of(record, "phone", str(row["phone"])),
                          "address": self._slot_of(record, "address", str(row["address"]))})
        return ({"query": query, "total": len(rows), "records": rows},
                {"query": query, "total": len(rows), "records": nodes}, "list")

    def _file_read(self, path: str) -> tuple[dict[str, object], object, str]:
        record = self._document_at_path(path)
        if record is None:
            return {"path": path, "found": False}, {"path": path, "found": False}, "empty"
        fmt = str(record.fields.get("format", "txt"))
        if fmt != "csv":
            body = self._compose(self._document_pieces(record), "")
            head = {"path": path, "format": fmt}
            return {**head, "text": body.text}, {**head, "text": body}, "free_text"
        rows: list[dict[str, object]] = []
        nodes: list[object] = []
        for row_key, row in _csv_rows(record):
            values = {key: str(row.get(key, "")) for key in CSV_COLUMNS}
            rows.append(dict(values))
            nodes.append({key: self._slot_of(record, csv_row_path(row_key, key), value)
                          for key, value in values.items()})
        head = {"path": path, "format": "csv", "header": CSV_HEADER}
        return {**head, "rows": rows}, {**head, "rows": nodes}, "list"

    def _form_parse(self, text: str) -> tuple[dict[str, object], object, str]:
        hits = self._ranked("documents", text, 1)
        if not hits:
            # THE PARSER NAMES WHAT IT COULD NOT READ, as every form parser
            # does — and that fragment is real personal data inside an error.
            fragment = text.strip().split("\n")[0][:60]
            return self._error("FORM_UNPARSED", fragment)
        score, record = hits[0]
        person = {name: str(record.fields.get(name, ""))
                  for name in ("last_name", "first_name", "middle_name")}
        birth = str(record.fields.get("birth_date", ""))
        passport = {"series": str(record.fields.get("passport_series", "")),
                    "number": str(record.fields.get("passport_number", ""))}
        snils = snils_spaced(str(record.fields.get("snils", "")))
        address = {key: str(record.fields.get(key, ""))
                   for key in ("city", "street", "house", "flat")}
        fields = {"person": person, "birth_date": birth, "passport": passport,
                  "snils": snils, "address": address}
        node_fields = {
            "person": {key: self._slot_of(record, key, value) for key, value in person.items()},
            "birth_date": self._slot_of(record, "birth_date", birth),
            "passport": {"series": self._slot_of(record, "passport_series", passport["series"]),
                         "number": self._slot_of(record, "passport_number", passport["number"])},
            "snils": self._slot_of(record, "snils", snils),
            "address": {key: (value if key == "city" else self._slot_of(record, key, value))
                        for key, value in address.items()}}
        return ({"format": "form", "confidence": round(score, 2), "fields": fields},
                {"format": "form", "confidence": f"{score:.2f}", "fields": node_fields},
                "nested")

    def _bank_row(self, record: Record) -> tuple[dict[str, object], object]:
        row = {"id": record.id, "name": str(record.fields.get("name", "")),
               "inn": str(record.fields.get("inn", "")),
               "card": card_grouped(str(record.fields.get("card", ""))),
               "status": str(record.fields.get("status", "active"))}
        node = {"id": record.id,
                "name": self._slot_of(record, "name", str(row["name"])),
                "inn": self._slot_of(record, "inn", str(row["inn"])),
                "card": self._slot_of(record, "card", str(row["card"])),
                "status": str(row["status"])}
        return row, node

    def _bank_client_find(self, parsed: dict[str, object]
                          ) -> tuple[dict[str, object], object, str]:
        key, value = next(iter(parsed.items()))
        wanted = digits_of(str(value))
        matches = [record for record in self._tables["bank_clients"].values()
                   if digits_of(str(record.fields.get(key, ""))) == wanted]
        if not matches:
            return {"clients": []}, {"clients": []}, "empty"
        if any(str(record.fields.get("status", "")) == "blocked" for record in matches):
            return self._error("CLIENT_BLOCKED", str(value))
        if len(matches) == 1:
            row, node = self._bank_row(matches[0])
            return {"client": row}, {"client": node}, "single"
        rows, nodes = zip(*(self._bank_row(record) for record in matches))
        return {"clients": list(rows)}, {"clients": list(nodes)}, "list"

    def _account_statement(self, parsed: dict[str, object]
                           ) -> tuple[dict[str, object], object, str]:
        client_id = str(parsed["client_id"])
        record = self._tables["bank_clients"].get(client_id)
        rows_raw = record.fields.get("rows") if record is not None else None
        rows_raw = rows_raw if isinstance(rows_raw, list) else []
        start, end = str(parsed.get("from", "")), str(parsed.get("to", ""))
        kept = [dict(row) for row in rows_raw
                if (not start or str(row.get("date", "")) >= start)
                and (not end or str(row.get("date", "")) <= end)]
        if record is None or not kept:
            return ({"client_id": client_id, "rows": []},
                    {"client_id": client_id, "rows": []}, "empty")
        name = str(record.fields.get("name", ""))
        card = card_grouped(str(record.fields.get("card", "")))
        holder = {"name": name, "card": card}
        holder_node = {"name": self._slot_of(record, "name", name),
                       "card": self._slot_of(record, "card", card)}
        rows: list[dict[str, object]] = []
        nodes: list[object] = []
        for row in kept:
            # THE HOLDER REPEATS ON EVERY LINE, the way a statement prints it:
            # several records of ONE person in one result (K15). Only the first
            # rendering carries the tag — a `dict` of spans holds one span per
            # item, and two would silently overwrite each other.
            line = {"date": str(row.get("date", "")), "amount": str(row.get("amount", "")),
                    "currency": str(row.get("currency", "RUB")), "card": card,
                    "holder": name, "description": str(row.get("description", ""))}
            rows.append(line)
            nodes.append({**line, "card": self._slot(card), "holder": self._slot(name)})
        return ({"client_id": client_id, "holder": holder, "rows": rows},
                {"client_id": client_id, "holder": holder_node, "rows": nodes}, "list")

    def _vehicle_check(self, plate: str) -> tuple[dict[str, object], object, str]:
        record = next((one for one in self._tables["vehicles"].values()
                       if str(one.fields.get("plate", "")).upper() == plate), None)
        if record is None:
            return self._error("VEHICLE_NOT_FOUND", plate)
        registrations = record.fields.get("registrations")
        if isinstance(registrations, list) and len(registrations) >= 2:
            rows: list[dict[str, object]] = []
            nodes: list[object] = []
            for index, entry in enumerate(registrations):
                owner = dict(dict(entry).get("owner") or {})
                block = {key: str(owner.get(key, "")) for key in ("last_name", "first_name")}
                rows.append({"from": str(dict(entry).get("from", "")),
                             "to": str(dict(entry).get("to", "")), "owner": block})
                nodes.append({"from": str(dict(entry).get("from", "")),
                              "to": str(dict(entry).get("to", "")),
                              "owner": {key: self._slot_of(
                                  record, f"registrations[{index}].owner.{key}", value)
                                  for key, value in block.items()}})
            return ({"plate": plate, "registrations": rows},
                    {"plate": self._slot_of(record, "plate", plate), "registrations": nodes},
                    "list")
        owner = dict(record.fields.get("owner") or {})                        # type: ignore[arg-type]
        block = {key: str(owner.get(key, "")) for key in ("last_name", "first_name")}
        head = {"model": str(record.fields.get("model", "")),
                "year": str(record.fields.get("year", ""))}
        return ({"plate": plate, "owner": block, **head},
                {"plate": self._slot_of(record, "plate", plate),
                 "owner": {key: self._slot_of(record, f"owner.{key}", value)
                           for key, value in block.items()}, **head}, "single")

    def _snils_verify(self, digits: str) -> tuple[dict[str, object], object, str]:
        spaced = snils_spaced(digits)
        record = next((one for one in self._tables["snils_records"].values()
                       if digits_of(str(one.fields.get("snils", ""))) == digits), None)
        if record is None:
            return ({"snils": spaced, "found": False}, {"snils": spaced, "found": False}, "empty")
        if str(record.fields.get("status", "")) == "revoked":
            return self._error("SNILS_REVOKED", spaced)
        person = {key: str(record.fields.get(key, ""))
                  for key in ("last_name", "first_name", "birth_date")}
        return ({"snils": spaced, "status": "valid", "person": person},
                {"snils": self._slot_of(record, "snils", spaced), "status": "valid",
                 "person": {key: self._slot_of(record, key, value)
                            for key, value in person.items()}}, "single")

    def _calendar_free(self, person: str, date: str) -> tuple[dict[str, object], object, str]:
        record = next((one for one in self._tables["calendar"].values()
                       if str(one.fields.get("person", "")).lower() == person.lower()), None)
        if record is None:
            return ({"person": person, "date": date, "slots": []},
                    {"person": person, "date": date, "slots": []}, "empty")
        shown = str(record.fields.get("person", ""))
        birth = str(record.fields.get("birth_date", ""))
        slots = list(self._calendar_slots(record, date))
        return ({"person": shown, "birth_date": birth, "date": date, "slots": slots},
                {"person": self._slot_of(record, "person", shown),
                 "birth_date": self._slot_of(record, "birth_date", birth),
                 "date": date, "slots": slots}, "list")

    def _email_send(self, parsed: dict[str, object]) -> tuple[dict[str, object], object, str]:
        # THE TRANSFER AGENT STORES THE ADDRESS IN LOWER CASE, so what comes
        # back is not always what was written — the messaging vertical's one
        # notation the user's own register does not produce.
        lowered = str(parsed["to"]).lower()
        blocked = self._tables["emails"].get(lowered)
        if blocked is not None and str(blocked.fields.get("status", "")) == "rejected":
            return self._error("RECIPIENT_REJECTED", lowered)
        record = self._store("emails", "email_send", parsed, "em")
        head = {"message_id": f"<{record.id}@mail.example.ru>", "status": "queued"}
        return ({**head, "accepted": lowered}, {**head, "accepted": self._slot(lowered)},
                "single")

    def _ticket_history(self, issue_id: str) -> tuple[dict[str, object], object, str]:
        events = sorted((record for record in self._tables["ticket_events"].values()
                         if str(record.fields.get("issue_id", "")) == issue_id),
                        key=lambda record: int(record.fields.get("order", 0)))  # type: ignore[arg-type]
        if not events:
            return ({"issue_id": issue_id, "found": False},
                    {"issue_id": issue_id, "found": False}, "empty")
        pieces: list[tuple[str, str]] = []
        for index, record in enumerate(events):
            if index:
                pieces.append((" ", ""))
            pieces.extend(self._template_pieces(record, None))
        history = self._compose(tuple(pieces), "")
        return ({"issue_id": issue_id, "events": len(events), "history": history.text},
                {"issue_id": issue_id, "events": len(events), "history": history}, "free_text")

    def _courier_status(self, claim_id: str) -> tuple[dict[str, object], object, str]:
        record = self._tables["claims"].get(claim_id)
        if record is None:
            return self._error("CLAIM_NOT_FOUND", claim_id)
        city, street, house, flat = self._address_fields(
            dict(record.fields.get("address") or {}))                          # type: ignore[arg-type]
        address = self._compose(self._courier_parts(city, street, house, flat), "")
        if str(record.fields.get("status", "")) == "failed":
            # CDEK NAMES THE ADDRESS IT COULD NOT DELIVER TO — an error body
            # carrying the real value, which is the form the family needs.
            return self._error_slot("CLAIM_ADDRESS_UNKNOWN", address)
        contact = dict(record.fields.get("contact") or {})                     # type: ignore[arg-type]
        name, phone = str(contact.get("name", "")), str(contact.get("phone", ""))
        status = str(record.fields.get("status", "") or "delivering")
        return ({"claim_id": claim_id, "status": status,
                 "recipient": {"name": name, "phone": phone}, "address": address.text},
                {"claim_id": claim_id, "status": status,
                 "recipient": {"name": self._slot_of(record, "contact.name", name),
                               "phone": self._slot_of(record, "contact.phone", phone)},
                 "address": address}, "nested")


# --- driving a case's declared calls, offline -----------------------------------------

# What a call needs BEYOND the values the hops declare: a page size, a day, a
# record id the dialogue never carries. Listed rather than invented per call, so
# a change of tool schema fails HERE instead of silently skipping the tool.
CALL_FILLER: dict[str, dict[str, object]] = {
    "calendar_free": {"date": "2026-09-05"},
    "account_statement": {"client_id": "bc-1"},
    "ticket_history": {"issue_id": "t-1"},
    "doc_retrieve": {"doc_id": "doc-1"},
}
CALL_INTERVAL: dict[str, object] = {"from": "2026-09-05T10:00:00+03:00",
                                    "to": "2026-09-05T14:00:00+03:00"}
# How many chunks a case that declares no `RagSpec` asks the knowledge base for.
# Every `rag` case declares one; this is for a case of another family that
# happens to offer `kb_search`.
KB_SEARCH_K: int = 3
# amoCRM's search takes EXACTLY ONE key (`tools._find_parse`, «exactly_one_key»),
# and the hops declare a leaf per identity field, so a driver that wrote all
# three would be refused on every case that carries a phone AND a surname. The
# order is the parser's own.
FIND_QUERY_KEYS: tuple[str, ...] = ("phone", "email", "last_name")


@dataclass(frozen=True)
class RenderedCall:
    """What ONE declared call DID when the real backend ran it: the form it
    answered in, the case items its result actually tagged with the text each
    one printed, and the refusal if the arguments did not parse.

    `rendered` is the whole of the build-time proof: a `ReturnExpectation` that
    names an item absent from it is a crossing the mock cannot produce, and a
    hop declared on that crossing is a permanent miss no gateway could avoid.
    """

    tool_name: str
    call_ordinal: int
    form: str                                  # "" when the call was refused
    refusal: str                               # "" when it parsed
    rendered: tuple[tuple[str, str], ...]      # (item id, the text the result printed)


def put_leaf(arguments: dict[str, object], path: str, value: str) -> None:
    """Write one dotted leaf, growing the nested objects on the way."""
    node = arguments
    parts = path.split(".")
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


# The `documents` columns that describe the FILE rather than the person in it.
# Everything else is the form's own content and is what a parser is handed.
DOCUMENT_STRUCTURE: tuple[str, ...] = ("path", "format", "title", "template", "rows")


def document_words(case: CaseV5) -> str:
    """The flat content columns of the case's seeded document, space-joined —
    the text an agent pastes out of a filled form. "" when the case seeds no
    document, and `form_parse` then refuses on an empty text, which is the
    truth to report rather than a plausible body to invent."""
    document = next((record for record in case.base.seed_records
                     if record.table == "documents"), None)
    if document is None:
        return ""
    return " ".join(str(value) for name, value in document.fields.items()
                    if name not in DOCUMENT_STRUCTURE and isinstance(value, str) and value)


def call_arguments(case: CaseV5, tool: str, ordinal: int,
                   state: dict[str, str]) -> dict[str, object]:
    """The call the case's own OUT hops describe, plus the filler that tool needs.

    THE CASE'S OWN ARGUMENT VALUES, NEVER A PLAUSIBLE ONE. Every identity leaf
    is filled from the item the hop names; only notations a PARSER DEMANDS are
    applied (`parse_snils` takes «XXX-XXX-XXX YY» and nothing else), because a
    driver that quietly repaired an argument would prove a loop the corpus does
    not describe.

    A MISSING PIECE OF STATE IS LEFT EMPTY, NOT INVENTED: the tool then refuses,
    and the refusal is reported — which is the truth, that the chain's earlier
    step did not hand its successor what it needed.
    """
    items = {item.id: item for item in case.base.pii}
    arguments: dict[str, object] = {}
    for hop in case.hops:
        if hop.kind != "OUT" or hop.tool_name != tool or hop.call_ordinal != ordinal:
            continue
        item = items[hop.item_id]
        value = item.canonical or item.value
        if item.type == "SNILS" and len(digits_of(value)) == 11:
            value = snils_spaced(value)
        put_leaf(arguments, hop.path, value)
    arguments.update(CALL_FILLER.get(tool, {}))
    if tool == "kb_search":
        # HOW MANY CHUNKS IS THE CASE'S DECLARATION, NOT A DEFAULT. `RagSpec.k`
        # is what the corpus declares one IN hop per, and a driver that asked
        # for three when the case declares five proves two thirds of a loop.
        arguments["k"] = case.rag.k if case.rag is not None else KB_SEARCH_K
    if tool == "crm_find_contact":
        query = arguments.get("query")
        if isinstance(query, dict):
            chosen = [key for key in FIND_QUERY_KEYS if query.get(key)][:1]
            arguments["query"] = {key: query[key] for key in chosen}
    if tool == "courier_book":
        contact = next((record for record in case.base.seed_records
                        if record.table == "contacts"), None)
        address = dict(contact.fields.get("address") or {}) if contact else {}
        put_leaf(arguments, "address.locality", str(address.get("city", "ижевск")))
        put_leaf(arguments, "address.building", str(address.get("house", "1")))
        put_leaf(arguments, "address.porch", "")
        put_leaf(arguments, "address.sflat", str(address.get("flat", "")))
        arguments["interval"] = dict(CALL_INTERVAL)
    if tool == "file_read":
        document = next(record for record in case.base.seed_records
                        if record.table == "documents")
        arguments["path"] = str(document.fields["path"])
    if tool == "form_parse":
        # `form_parse` takes the TEXT of the document the agent is looking at.
        # When an earlier declared call read it, that reading is what the agent
        # pastes. A filled FORM has no reading tool — `_document_pieces` renders
        # a template or CSV rows and a form is neither — so its own columns are
        # the text, which is what `_form_parse` ranks documents by anyway.
        text = state.get("document_text", "")
        arguments["text"] = text if text else document_words(case)
    if tool == "courier_status":
        arguments["claim_id"] = state.get("claim_id", "")
    if tool == "crm_upsert_contact" and "address" in str(arguments.get("contact", {})):
        # `crm_upsert_contact` refuses an address without its city, and a bare
        # city is not personal data, so no hop declares it — it is business
        # filler like an amount or a page size.
        contact = next((record for record in case.base.seed_records
                        if record.table == "contacts"), None)
        address = dict(contact.fields.get("address") or {}) if contact else {}
        put_leaf(arguments, "contact.address.city", str(address.get("city", "ижевск")))
        put_leaf(arguments, "contact.address.house", str(address.get("house", "1")))
    return arguments


def drive_returns(case: CaseV5) -> tuple[RenderedCall, ...]:
    """Seed the real backend and make every call the case declares a return for.

    IN THE ORDER THE RETURNS WERE DECLARED, because that order is the order the
    chain needs — a claim id exists only after the booking that minted it. A
    forced ordinal is still CALLED (the refusal has to be consumed for the next
    attempt to be the next attempt) and nothing is asserted about it: the
    `ForcedError`, not the return table, decides what it answers.

    NO SHORTCUT READS THE CASE'S DECLARATION BACK. Every item id below came out
    of `CallLog.result_spans`, which the renderer wrote; `case.returns` is only
    ever the question, never the answer.
    """
    backend = seed_backend_v5(case)
    state: dict[str, str] = {}
    forced = {(one.tool_name, one.call_ordinal) for one in case.forced}
    made: list[RenderedCall] = []
    for expectation in case.returns:
        for ordinal in range(expectation.call_ordinal + 1):
            if (expectation.tool_name, ordinal) in forced:
                # THE SCRIPTED REFUSAL IS A CALL THE CASE DECLARES HOPS ON: the
                # error body echoes the offending value, and `retry_same_tool`
                # puts an IN hop on `error.message` at exactly this ordinal.
                # Driving it without recording it made every one of those 120
                # hops look like a crossing the mock cannot render.
                made.append(_record_call(
                    backend, case, expectation.tool_name, ordinal, state))
        made.append(_record_call(backend, case, expectation.tool_name,
                                 expectation.call_ordinal, state))
    return tuple(made)


def _record_call(backend: BackendV5, case: CaseV5, tool: str, ordinal: int,
                 state: dict[str, str]) -> RenderedCall:
    """One call made and read back off `CallLog` — the whole of the evidence."""
    log = backend.call(tool, call_arguments(case, tool, ordinal, state))
    if log.refusal is not None:
        return RenderedCall(tool, ordinal, "", f"{log.refusal.path}: {log.refusal.rule}", ())
    result = log.result or {}
    if tool == "courier_book":
        state["claim_id"] = str(result.get("claim_id", ""))
    if tool == "doc_retrieve":
        state["document_text"] = str(result.get("body", ""))
    if tool == "file_read":
        state["document_text"] = str(result.get("text", ""))
    rendered = tuple(
        (tag[len(ECHO_TAG_PREFIX):] if tag.startswith(ECHO_TAG_PREFIX) else tag,
         log.result_text[start:end])
        for tag, (start, end) in sorted(log.result_spans.items()))
    return RenderedCall(tool, ordinal, backend.form_of(log.seq), "", rendered)





def render_problems(case: CaseV5) -> list[str]:
    """Every way the case's declaration and the backend's rendering disagree.

    THIS IS THE REFUSAL, not a report. A declared `result_item_ids` the backend
    never tags, a `return_form` it does not answer in, an IN/tool hop with no
    rendered span — each is a hop that would score as a gateway miss forever,
    and 42% of the revised half's IN/tool hops were exactly that before the
    corpus had to prove itself.
    """
    problems: list[str] = []
    tag = case.base.id
    by_call = {(one.tool_name, one.call_ordinal): one for one in drive_returns(case)}
    for expectation in case.returns:
        made = by_call.get((expectation.tool_name, expectation.call_ordinal))
        if made is None:
            problems.append(f"V01 {tag}: {expectation.tool_name}#"
                            f"{expectation.call_ordinal} was never driven")
            continue
        if made.refusal:
            problems.append(f"V01 {tag}: {expectation.tool_name}#"
                            f"{expectation.call_ordinal} refused the call the hops "
                            f"describe ({made.refusal})")
            continue
        if made.form != expectation.return_form:
            problems.append(f"V02 {tag}: {expectation.tool_name}#"
                            f"{expectation.call_ordinal} answered {made.form!r}, the case "
                            f"declared {expectation.return_form!r}")
        printed = {item_id for item_id, _text in made.rendered}
        missing = [item_id for item_id in expectation.result_item_ids
                   if item_id not in printed]
        if missing:
            problems.append(f"V03 {tag}: {expectation.tool_name}#"
                            f"{expectation.call_ordinal} rendered none of {missing[:4]}")
    for hop in case.hops:
        if hop.kind != "IN" or hop.owner not in ("tool", "document"):
            continue
        made = by_call.get((hop.tool_name, hop.call_ordinal))
        printed = {item_id for item_id, _text in made.rendered} if made else set()
        if hop.item_id not in printed:
            problems.append(f"V04 {tag}: IN hop {hop.hop_index} reads {hop.item_id} from "
                            f"{hop.tool_name}#{hop.call_ordinal}, which renders no span "
                            f"for it")
    problems.extend(_unscorable_problems(case, by_call))
    problems.extend(_transition_problems(case, by_call))
    return problems


def identifies_on_its_own(value: str) -> bool:
    """Is this surface long enough to be LOOKED FOR at all?

    The floors are `contracts`' own (`PIECE_MIN_CHARS`, `PIECE_MIN_DIGITS`),
    read rather than restated: a house number «19» stands inside «1977-01-07»
    and a two-letter stem stands inside half the dictionary, so a needle built
    from one is evidence about nothing. R-58 makes the needle layer answer
    False for such a value everywhere; this is the same question asked at BUILD
    time, of the corpus.

    WHEN THE NEEDLE LAYER EXPOSES «does this value carry a needle», THIS MUST
    BECOME A CALLER OF IT (contract question to FIX-1). Today `needles_of`
    always returns the `whole` needle, so asking it would give a rule that
    cannot fire — a rule that cannot fail is the thing this package refuses to
    ship, and two floors that must stay equal is the lesser of the two evils
    for exactly one round.
    """
    compact = "".join(value.split())
    digits = "".join(ch for ch in compact if ch.isdigit())
    if compact and digits == compact:
        return len(digits) >= PIECE_MIN_DIGITS
    return len(value.strip()) >= PIECE_MIN_CHARS


def _unscorable_problems(case: CaseV5,
                         by_call: dict[tuple[str, int], RenderedCall]) -> list[str]:
    """V06: no declared value may be beyond the reach of BOTH ways of scoring it.

    A value is scored either by its SPAN — the message offsets a coverage check
    reads, or the tag the mock puts on a rendered result — or, where no span
    exists, by the needle layer asking whether it survived in the text. R-58
    gives the needle a floor, so a SHORT value with no span anywhere can be
    scored by neither: it would sit in a denominator that no gateway can move,
    which is the defect `doc_extracted` had in another shape.

    THE CORPUS CARRIES NONE TODAY — 22 short items, every one of them tagged by
    a result a declared call renders — and that is precisely why the rule is
    written now: the next family to seed a house number nobody reads would
    reintroduce it silently.
    """
    tag = case.base.id
    tagged = {item_id for made in by_call.values() for item_id, _text in made.rendered}
    problems: list[str] = []
    for item in case.base.pii:
        if item.where.kind == "message" or item.id in tagged:
            continue
        if identifies_on_its_own(item.value):
            continue
        problems.append(f"V06 {tag}: seed item {item.id} ({item.type} {item.value!r}) is "
                        f"below the identifying floor and no declared call renders it, so "
                        f"neither a span nor a needle can score it")
    return problems


def _transition_problems(case: CaseV5,
                         by_call: dict[tuple[str, int], RenderedCall]) -> list[str]:
    """V05: a declared hand-over A→B must be one a COPY of A's result can make.

    F4.2 PROMISED THIS AND V04 DOES NOT GIVE IT. V04 asks only that the source
    result carries SOME span for the item; nothing compared the string it
    printed with the value the TARGET leaf asks for. Ten of 938 declared
    transitions were unhittable by any gateway — `patient.first_name` fed by
    the hop that carries the SURNAME — and each one read as a hand-over the
    gateway broke, on a line whose whole subject is the hand-over.

    THE POPULATION IS `metrics._transitions`: an OUT hop that ACTS (never the
    answer) whose source is an IN/tool hop of ANOTHER tool. A rule wider than
    the line it protects would refuse cases no line ever scores.

    THE FOLD IS `role_matches`, THE TYPE-AWARE HALF OF THE RUN'S COMPARATOR,
    and not `leaf_value_ok`: its no-role branch compares byte for byte, so a
    phone the source printed as «+7 (925) 634-55-93» against the canonical
    «+79256345593» would be refused here although it is the same number — the
    build would delete a sound transition to pay for a defect of the metric,
    which is the opposite of a proof.
    """
    problems: list[str] = []
    tag = case.base.id
    by_index = {hop.hop_index: hop for hop in case.hops}
    items = {item.id: item for item in case.base.pii}
    for hop in case.hops:
        if hop.kind != "OUT" or hop.source_hop == -1 or hop.owner not in ACTING_OUT_OWNERS:
            continue
        source = by_index.get(hop.source_hop)
        if source is None or source.kind != "IN" or source.owner != "tool":
            continue
        if source.tool_name == hop.tool_name:
            continue
        made = by_call.get((source.tool_name, source.call_ordinal))
        rendered = dict(made.rendered).get(source.item_id) if made is not None else None
        if rendered is None:
            continue                      # V04 already names the unrendered source
        item = items[hop.item_id]
        spec = spec_v5_for(hop.tool_name, hop.path) if hop.tool_name and hop.path else None
        wanted = expected_leaf_value(item, spec) if spec is not None \
            else (item.canonical or item.value)
        if not wanted:
            role = spec.role if spec is not None else ""
            problems.append(f"V05 {tag}: hop {hop.hop_index} feeds {hop.tool_name}."
                            f"{hop.path}, which asks for the {role!r} of {item.id}, "
                            f"and the item has no such part")
            continue
        if not role_matches(item.type, rendered, wanted):
            problems.append(f"V05 {tag}: hop {hop.hop_index} takes {item.id} for "
                            f"{hop.tool_name}.{hop.path} from hop {source.hop_index}, but "
                            f"{source.tool_name}#{source.call_ordinal} renders {rendered!r} "
                            f"there and the leaf expects {wanted!r}")
    return problems


def seed_backend_v5(case: CaseV5) -> BackendV5:
    """The world one case starts in: v4's seed records into v4's tables and the
    new ones into theirs, plus the binding from every seeded field to the
    `PiiItem` that labels it.

    v4's `fake_agent.seed_backend` cannot be called — it builds a v4 `Backend`
    — so its loop is repeated here over the generic seeder, which is also what
    lets a case seed an ORDER or a CLAIM it did not create in the dialogue."""
    items = {item.id: item for item in case.base.pii}
    echo: dict[str, str] = {}
    for forced in case.forced:
        item = items.get(forced.echo_item_id)
        if item is None:
            raise KeyError(f"forced error on {forced.tool_name} echoes {forced.echo_item_id!r}, "
                           f"which is not an item of the case")
        # AN API ECHOES WHAT IT RECEIVED, and what a tool receives is the
        # canonical form its parser accepted — never the surface the customer
        # said, which for a dictated number is words.
        if not item.canonical:
            raise ValueError(f"item {item.id} has no canonical form to echo")
        echo[item.id] = item.canonical
    backend = BackendV5(case.base.now, case.forced, echo)
    for record in case.base.seed_records:
        backend.seed_record(record.table, record.id, dict(record.fields))
    for record in case.base.seed_records:
        for item_id in record.pii_ids:
            item = items.get(item_id)
            if item is None:
                raise KeyError(f"seed {record.table}/{record.id} names item {item_id!r}, "
                               f"which the case does not carry")
            if item.where.kind != "seed" or item.where.record != record.id:
                raise ValueError(f"item {item_id} is listed by seed {record.id} but its locus "
                                 f"is {item.where.kind}/{item.where.record!r}")
            backend.seed_item(record.table, record.id, item.where.path, item.id)
    return backend
