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

from bench.agentpii4.mock import Backend, CallLog, Record
from bench.agentpii4.tools import CSV_HEADER, Refusal
from bench.agentpii4.writer import Slot, Writer, serialise
from bench.agentpii5.contracts import ECHO_TAG_PREFIX, CaseV5, ForcedError
from bench.agentpii5.tools import NEW_REGISTRY

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


def digits_of(text: str) -> str:
    return "".join(character for character in text if character.isdigit())


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


def field_at(fields: dict[str, object], path: str) -> object:
    """A seed field by its dotted path, arrays by index («rows[1].phone»)."""
    value: object = fields
    for step in path.split("."):
        name, indexes = step, []
        while name.endswith("]"):
            head, _, raw = name[:-1].rpartition("[")
            indexes.insert(0, int(raw))
            name = head
        if not isinstance(value, dict) or name not in value:
            raise KeyError(f"seed path {path!r} does not exist: no {name!r} in {value!r}")
        value = value[name]
        for index in indexes:
            if not isinstance(value, list) or index >= len(value):
                raise KeyError(f"seed path {path!r} does not exist: no index {index}")
            value = value[index]
    return value


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
                                 (tail, "")))
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

    def _compose(self, pieces: Sequence[tuple[str, str]]) -> Slot:
        """Assemble one string out of tagged and untagged pieces.

        A `Slot` carries ONE tag for a whole JSON string and an address in a
        courier's notation carries three values inside one line, so the offsets
        are taken from v4's `Writer` as the string GROWS and lifted onto the
        result in `_expand_prose`. Nothing is ever searched for afterwards."""
        writer = Writer()
        for text, tag in pieces:
            if not text:
                continue
            writer.put(text, tag)
        text, spans, _trace = writer.finish()
        outer = f"prose:{len(self._prose)}"
        self._prose[outer] = tuple((tag, start, end) for tag, (start, end) in spans.items())
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
        """DaData: «г Самара, ул Луговая, д 10, кв 7» — no dots after the
        generic abbreviations, comma-separated, the house marked «д»."""
        pieces: list[tuple[str, str]] = []
        if city:
            pieces.extend((("г ", ""), self._piece(capitalised(city))))
        if street:
            pieces.append(((", " if pieces else "") + "ул ", ""))
            pieces.append(self._piece(capitalised(street)))
        if house:
            pieces.append(((", " if pieces else "") + "д ", ""))
            pieces.append(self._piece(str(house)))
        if flat:
            pieces.append((", кв ", ""))
            pieces.append(self._piece(str(flat)))
        return tuple(pieces)

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
            address = self._compose(self._courier_parts(city, street, house, flat))
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
            nodes: list[object] = []
            for row in suggestions:
                fields = dict(row["data"])                                     # type: ignore[index]
                canon = self._compose(self._canon_parts(
                    str(fields["city"]), str(fields["street"]), str(fields["house"]),
                    str(fields.get("flat", ""))))
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
            return data, node, "list" if isinstance(contacts, list) and contacts else "empty"
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
            canon = self._compose(self._canon_parts(city, street, house, ""))
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
                    "", str(block["street"]), str(block["house"]), ""))         # type: ignore[index]
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
        rows = record.fields.get("rows")
        if not isinstance(rows, list):
            raise KeyError(f"documents/{record.id}: neither a template nor rows to render")
        pieces: list[tuple[str, str]] = [(CSV_HEADER, "")]
        for index, row in enumerate(rows):
            for key in ("last_name", "first_name", "phone", "email", "birth_date"):
                pieces.append((" | " if key == "last_name" else ";", ""))
                value = str(dict(row).get(key, ""))
                pieces.append((value, self._tag_of(record, f"rows[{index}].{key}")))
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
            body = self._compose(self._document_pieces(record))
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

    def _kb_search(self, query: str, count: int) -> tuple[dict[str, object], object, str]:
        hits = self._ranked("kb_chunks", query, count)
        notes = [(score, record) for score, record in hits if "template" in record.fields]
        if notes:
            # A NOTE AND A CARD ARE BOTH IN THE INDEX, and Elasticsearch hands
            # back whatever `_source` it stored. Text wins when both matched:
            # the RAG families are about prose, and a run that sometimes
            # answered them with rows would measure a different hop.
            rows: list[dict[str, object]] = []
            nodes: list[object] = []
            for score, record in notes:
                text = self._compose(self._template_pieces(record, None))
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
            body = self._compose(self._document_pieces(record))
            head = {"path": path, "format": fmt}
            return {**head, "text": body.text}, {**head, "text": body}, "free_text"
        rows_raw = record.fields.get("rows")
        if not isinstance(rows_raw, list):
            raise KeyError(f"documents/{record.id}: a csv document with no rows")
        rows: list[dict[str, object]] = []
        nodes: list[object] = []
        for index, row in enumerate(rows_raw):
            values = {key: str(dict(row).get(key, ""))
                      for key in ("last_name", "first_name", "phone", "email", "birth_date")}
            rows.append(dict(values))
            nodes.append({key: self._slot_of(record, f"rows[{index}].{key}", value)
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
        history = self._compose(tuple(pieces))
        return ({"issue_id": issue_id, "events": len(events), "history": history.text},
                {"issue_id": issue_id, "events": len(events), "history": history}, "free_text")

    def _courier_status(self, claim_id: str) -> tuple[dict[str, object], object, str]:
        record = self._tables["claims"].get(claim_id)
        if record is None:
            return self._error("CLAIM_NOT_FOUND", claim_id)
        city, street, house, flat = self._address_fields(
            dict(record.fields.get("address") or {}))                          # type: ignore[arg-type]
        address = self._compose(self._courier_parts(city, street, house, flat))
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
