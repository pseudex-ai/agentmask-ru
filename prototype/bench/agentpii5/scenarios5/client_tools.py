"""The leaves the five CLIENT-FORM families cross, and the rows they seed.

WHY A TABLE AND NOT ELEVEN LITERALS PER FAMILY. `mail_loop`, `mail_find`,
`tracker`, `office` and `assistant_writes` all cross the eleven leaves the
office suite added to `tools.REGISTRY_V5`, and a leaf spelled in five modules is
five places one rename has to be chased through. Named once here, a rename in the
registry is ONE edit; spelled wrong, it is caught at build rather than read for
ever — `common.arg_hop` raises on an argument leaf the registry does not carry
and `mock.render_problems` reports a result leaf nothing renders.

THE NAMES ARE GENERALISED FORMS, NEVER PRODUCTS (owner's decision). A corpus
outlives a deal and has to be reusable for the next customer, so the eleven
tools are `mail_*`, `tracker_*`, `sheet_*`, `doc_*`, `memory_*`, `reminder_*`,
`calendar_invite` and `crm_upsert_card`. Which real product each form mirrors is
a separate note outside the corpus; nothing in this package names one, and the
`source` line of each spec (the tools component's to write) cites the PUBLIC
documentation of a public API exactly as the 44 existing specs do.

WHAT THIS FILE DOES **NOT** DO. It declares no tool. `ToolSpecV5`, `FieldSpec`,
the strict parse, the return forms and the mock's renderers belong to the tools
component; this is the corpus side's reading of them and nothing more.

NOTHING HERE IMPORTS `pseudex`, AND NOTHING HERE SEARCHES A FINISHED STRING.
"""
from bench.agentpii4 import pools
from bench.agentpii4.pools import Rendered
from bench.agentpii5.scenarios5 import common as c

# --- the eleven tool names ------------------------------------------------------

MAIL_READ: str = "mail_read"
MAIL_SEARCH: str = "mail_search"
MAIL_SEND: str = "mail_send"
CALENDAR_INVITE: str = "calendar_invite"
TRACKER_FIND_USER: str = "tracker_find_user"
TRACKER_ISSUE_CREATE: str = "tracker_issue_create"
CRM_UPSERT_CARD: str = "crm_upsert_card"
SHEET_APPEND_ROW: str = "sheet_append_row"
DOC_APPEND: str = "doc_append"
MEMORY_SAVE: str = "memory_save"
REMINDER_SET: str = "reminder_set"

CLIENT_TOOLS: tuple[str, ...] = (
    MAIL_READ, MAIL_SEARCH, MAIL_SEND, CALENDAR_INVITE, TRACKER_FIND_USER,
    TRACKER_ISSUE_CREATE, CRM_UPSERT_CARD, SHEET_APPEND_ROW, DOC_APPEND,
    MEMORY_SAVE, REMINDER_SET)

# --- result leaves (IN/tool hops read these) ------------------------------------
#
# EVERY NAME BELOW IS READ OFF `tools.REGISTRY_V5`, NOT CHOSEN HERE. The eleven
# specs landed while these families were being written, and a leaf spelled by
# hand is a hop `common.arg_hop` refuses at build (an argument) or that
# `mock.render_problems` reports as a crossing nothing renders (a result). The
# table exists so a rename in the registry is ONE edit here rather than five
# across the families.

# `mail_read` answers a letter in TWO shapes, and the seeded row decides which.
# `format: "raw"` is a real parameter of a real API and gives this corpus the
# thing it had nowhere: a person's own prose arriving from something that is not
# a document, headers and body in ONE untyped string. Anything else hands the
# envelope back typed and the body apart — the easy case, kept beside the hard
# one so a slice can tell which of the two a gateway fails.
MAIL_FROM_NAME: str = "from.name"
MAIL_FROM_EMAIL: str = "from.email"
MAIL_BODY: str = "body"
MAIL_RAW: str = "raw"
# `mail_search` answers a list of envelopes with the first line of each body.
MAIL_HIT_NAME: str = "messages[].from.name"
MAIL_HIT_EMAIL: str = "messages[].from.email"
MAIL_HIT_SNIPPET: str = "messages[].snippet"
# `tracker_find_user` answers the directory rows one free-text query matched.
# `displayName` is the LATIN spelling the tracker prints — a notation no Russian
# speech register produces, which is what makes this IN hop able to fail.
#
# `users[].login` IS NOT HERE AND CANNOT BE. It is not personal data, so V04 and
# V06 refuse it in `result_pii`; the mock renders it deliberately untagged and
# says so in its own comment. Nothing in this package scores it either way, and
# the handover names the contract change it needs rather than calling a login
# personal data to get a number.
TRACKER_USER_NAME: str = "users[].displayName"
TRACKER_USER_EMAIL: str = "users[].emailAddress"
# What the tracker answers a creation with: the assignee AS THE TRACKER SPELLS
# THEM, off the directory row, not as the agent wrote it.
TRACKER_ISSUE_ASSIGNEE_BACK: str = "issue.fields.assignee.displayName"
# What each WRITE answers with — the value the customer's own system now holds.
# Reading a write back is the only way the corpus can tell «it went in» from «it
# went in wrong»: nothing downstream of a bad card, a bad reminder or a bad
# invitation fails, and the agent reports success either way.
CARD_BACK_PHONE: str = "card.contact.phone"
CARD_BACK_EMAIL: str = "card.contact.email"
CARD_BACK_DEAL_NAME: str = "card.deal.contact_name"
# The card prints the address as ONE line in the directory's canon, while the
# agent wrote it by fields — the same value in two shapes, which is what the LOC
# form comparison exists for.
CARD_BACK_ADDRESS: str = "card.contact.address"
MAIL_ACCEPTED: str = "accepted[{index}]"
MEMORY_BACK_SUBJECT: str = "memory.subject"
REMINDER_BACK_NAME: str = "reminder.recipient.name"
REMINDER_BACK_PHONE: str = "reminder.recipient.phone"
INVITE_BACK_EMAIL: str = "event.attendees[{index}].email"
INVITE_BACK_NAME: str = "event.attendees[{index}].displayName"
# What a document answers an append with: the whole page, the seeded prose in it
# tagged and the agent's own paragraph not.
DOC_BODY: str = "document.body"
# What a spreadsheet answers an append with: the range it touched and the cells
# it stored, one slot per cell.
SHEET_ECHO: str = "updated.values[][]"

# --- argument leaves (OUT hops cross these) -------------------------------------

# `mail_send` takes a LIST of recipients in ONE argument and a second list
# beside it — the form the corpus had nowhere: 128 OUT/tool_arg EMAIL hops and
# every one of them a single address. `subject` and `body` are TEMPLATE leaves
# (`contracts.TEMPLATE_FIELDS`): a human reads them, so the form the real value
# must take on the way out is the agent's own.
#
# THE INDEX IS WRITTEN OUT. `mock.put_leaf` grows the list as it writes, so a hop
# names `to[0]` and `to[1]`; `tools.spec_v5_for` erases the index before it looks
# the leaf up, and `contracts.hop_owner_of_leaf` does the same.
MAIL_SEND_TO: str = "to[{index}]"
MAIL_SEND_CC: str = "cc[{index}]"
MAIL_SEND_SUBJECT: str = "subject"
MAIL_SEND_BODY: str = "body"
# `mail_search` searches through ONE free field — the `q` of every mail API,
# where «from:» is a convention and not a column. That is the form and the risk
# at once: the same leaf holds an address, a surname or a topic word, so a
# gateway deciding by the field's NAME is wrong in one direction or the other.
# A substitute here breaks nothing visibly — the call parses, the API answers
# 200, and it answers NOTHING.
MAIL_SEARCH_QUERY: str = "query"

# `tracker_find_user` searches by ONE polymorphic field whose value may be a
# name, a login or an address — the same hazard, one vertical along.
TRACKER_QUERY: str = "query"
TRACKER_ISSUE_SUMMARY: str = "summary"              # SUMMARY leaf
TRACKER_ISSUE_DESCRIPTION: str = "description"      # SUMMARY leaf
# A person in an ARGUMENT, which the corpus has nowhere: every tool it hands a
# person to takes a phone, an ИНН, a plate or a card. The tracker takes the
# person's own name, and the mock matches it against the directory row — so a
# substitute that fails to resolve assigns the task to nobody.
TRACKER_ISSUE_ASSIGNEE: str = "assignee"

# `crm_upsert_card` writes TWO objects in ONE call — the form `crm_upsert_contact`
# does not have. `deal.note` is a SUMMARY leaf; `deal.contact_name` takes the
# WHOLE name, which is what a letter's envelope carries.
# `contact.last_name` and `contact.first_name` are NOT named here, and the
# instrument is why. A letter's envelope carries ONE name string and
# `mock.call_arguments` writes an item's canonical into whatever leaf a hop
# names, so the whole «Букин Сергей Иванович» landed in `last_name` and the
# parser refused it with `name_cyrillic`. The split leaves belong to a source
# that is already split — a CSV row, a card — and a corpus that declared them
# here would be declaring a call that cannot happen.
CARD_PHONE: str = "contact.phone"
CARD_EMAIL: str = "contact.email"
CARD_STREET: str = "contact.address.street"
CARD_DEAL_TITLE: str = "deal.title"
CARD_DEAL_NAME: str = "deal.contact_name"
CARD_DEAL_NOTE: str = "deal.note"                   # SUMMARY leaf

# `sheet_append_row` is the only TWO-DIMENSIONAL argument in the corpus. Each
# cell is its own hop at its own `values[row][column]`, because a row is not one
# value: a gateway that resolves four cells of five writes a row that looks
# complete, and joining them would give this argument the shape
# `crm_import_csv` already has.
SHEET_VALUES: str = "values[{row}][{column}]"

DOC_TEXT: str = "text"                              # SUMMARY leaf

MEMORY_SUBJECT: str = "subject"
MEMORY_FACT: str = "fact"                           # SUMMARY leaf

REMINDER_PHONE: str = "recipient.phone"
REMINDER_NAME: str = "recipient.name"
REMINDER_TEXT: str = "text"                         # TEMPLATE leaf

INVITE_ATTENDEE_EMAIL: str = "attendees[{index}].email"
INVITE_ATTENDEE_NAME: str = "attendees[{index}].name"
INVITE_DESCRIPTION: str = "description"             # SUMMARY leaf


def at(leaf: str, **positions: int) -> str:
    """One concrete occurrence of a leaf that lives inside a list or a matrix.

    `at(MAIL_SEND_TO, index=1)` is «to[1]», `at(SHEET_VALUES, row=0, column=2)`
    is «values[0][2]». The index is written out rather than left as «[]» because
    `mock.put_leaf` GROWS the list as it writes and a gap is filled with an empty
    string — so «to[]» would be written under the literal key «to[]», where the
    parser never looks, and the call would be refused for a value that was in
    fact supplied. `tools.spec_v5_for` and `contracts.hop_owner_of_leaf` both
    erase the index before they look a leaf up, so the declaration still matches
    the registry.
    """
    return leaf.format(**positions)


# WHY THERE IS NO `sheet_cell_path` HERE. A cell's (row, column) would be needed
# on the day a `sheets` table is SEEDED and read back — `values.<row>.<col>` as
# the item's `Locus.path`, exactly as `tools.csv_row_path` spells a CSV cell.
# Nothing in this half seeds one: the customer's form is writing a row, so the
# two-dimensionality is measured where their pain is, on the ARGUMENT. Writing
# the helper for a reader that does not exist would be a second spelling of one
# fact waiting for its first disagreement; the read side is named in the
# handover instead.


# --- machine identifiers: what must arrive UNTOUCHED -----------------------------

# THE IDENTIFIERS THE CLIENT'S OWN TRAFFIC CARRIES BESIDE EVERY REAL VALUE, and
# the reason they are written into the MESSAGE rather than only into the call:
# `metrics.overmask` reads `case.base.negatives`, and a `Negative` carries `msg`
# — the index of a message. There is no locus for «this argument» or «this
# result», so an identifier that appeared only inside a tool call would be
# measured by nothing at all.
#
# THEY ARE `plain_value`, NOT `negative`, AND THE DIFFERENCE IS HONESTY RATHER
# THAN CONVENIENCE. `agentpii3.NEGATIVE_FAMILIES` is a CLOSED tuple of ten, all
# of them speech («десять пакетов», «к девяти ноль ноль»), and `v4.validate`
# refuses a negative outside it; `PlainValue.family` is open. Declaring an issue
# key as `order_number` to get it counted would file a machine identifier under a
# family that means something else, and the number it bought would be read as
# speech precision. So the value stands where the client's own traffic puts it —
# beside the real values — and the line that counts it is named in the handover
# as the contract change it is.
RECORD_KEY_FAMILY: str = "record_key"
RECORD_KEY_WHY: str = ("ключ записи (задача, сделка, письмо, документ) — не персональные "
                       "данные: подменённый, он ломает вызов молча, и прибор назовёт это "
                       "«агент не действовал»")
CELL_RANGE_FAMILY: str = "cell_range"
CELL_RANGE_WHY: str = ("диапазон ячеек — адрес в таблице, а не адрес человека; подменённый, "
                       "он пишет строку не туда и возвращает 200")

ISSUE_KEY_PREFIXES: tuple[str, ...] = ("CRM", "OPS", "SUP", "FIN")


def issue_key(index: int) -> str:
    """A tracker key as every tracker prints one: «CRM-412»."""
    prefix = ISSUE_KEY_PREFIXES[index % len(ISSUE_KEY_PREFIXES)]
    return f"{prefix}-{100 + (index * 7) % 800}"


def sheet_range(index: int) -> str:
    """«Лист1!A3:E3» — the A1 notation every spreadsheet API takes."""
    line = index + 2                     # row 1 is the header the sheet ships with
    return f"Лист1!A{line}:E{line}"


def say_machine_id(draft: c.MessageDraft, ctx: c.Ctx, words: str, value: str, family: str,
                   why: str) -> c.MessageDraft:
    """Put a machine identifier into the message — in every register that can
    carry THIS value, and no other.

    IT IS NOT A STYLE RULE, IT IS v4's VALIDATOR, AND IT IS DECIDED BY THE VALUE.
    `agentpii3._register_problems` refuses a `voice_raw` message that carries a
    digit («0 of 53 324 measured utterances do, and a spoken number is words») or
    sentence punctuation, and a `voice_itn` message that carries sentence
    punctuation («ITN restores digits, not commas»). «CRM-412» trips the first
    rule; «Лист1!A3:E3» trips both. Asking the VALUE rather than naming the two
    registers is what keeps a family from building today and failing on the next
    seed, which is exactly what a fixed list would have done to `office` — six
    sheet cases and no `voice_itn` among them by luck alone.

    Unlike an order number, which v4 spells out for that register, a key read off
    a screen has NO spoken form the system would take back: «це эр эм четыреста
    двенадцать» is a convention this corpus would be inventing, and a benchmark
    that invents the customer's notation measures its own fiction. So the
    identifier is skipped where it cannot be said, and roughly a quarter of the
    cases of each family carry none — a share of the measurement given up on
    purpose rather than a shape written wrong.
    """
    if ctx.register in _REFUSING_REGISTERS(value):
        return draft
    if words:
        draft.say(words)
    return draft.plain_value(_machine_key(value), value, family, why)


# The two register rules of `agentpii3.schema._register_problems`, read off the
# VALUE. Spelled here rather than imported because v3's are module-private
# regexes and this needs the QUESTION they answer, not their implementation;
# `test_client_families` pins that no machine identifier reaches a register that
# refuses it, so a drift is caught rather than assumed away.
_SENTENCE_PUNCT: str = ".,;:!?"


def _REFUSING_REGISTERS(value: str) -> frozenset[str]:  # noqa: N802 - a table, not a verb
    """Which registers v4's gate would refuse this string in."""
    refusing: set[str] = set()
    if any(char.isdigit() for char in value):
        refusing.add("voice_raw")
    if any(char in _SENTENCE_PUNCT for char in value):
        refusing.update(("voice_raw", "voice_itn"))
    return frozenset(refusing)


def _machine_key(value: str) -> str:
    """A draft key for one machine identifier. Derived from the value so two of
    them in one message cannot collide, and never from a counter a caller would
    have to keep."""
    return "mid_" + "".join(char for char in value.lower() if char.isalnum())


def document_key(index: int) -> str:
    """A document's id, in the shape `tools.DOC_ID_RE` accepts.

    THE RECORD ID IS THE ID THE TOOL IS GIVEN. `mock.call_arguments` hands
    `doc_append` the id of the row the case seeded, and a row named «doc-note»
    would be refused by the reader's own `id_format` rule — a refusal the case
    never declared, which is the defect `document.py` already records for a file
    extension.
    """
    return f"doc-{index}"


def message_key(index: int) -> str:
    """A letter's id — and the record id of its `mailbox` row, on purpose.

    ONE STRING, NOT TWO. `mock.call_arguments` reads `mail_read`'s `message_id`
    off `_seeded_id(case, "mailbox")`, which is the RECORD id, while
    `_mail_read` looks the letter up in the same table by that id. A corpus that
    kept a separate `message_id` column would be describing a letter the driver
    can never open.
    """
    return f"msg-{index}"


# --- the letter a family seeds ---------------------------------------------------

# The body of a letter, as the customer's own correspondent wrote it. `{phone}`,
# `{street}` and `{dob}` name COLUMNS of the same row; `mock._template_pieces`
# renders each in that column's prose notation (a phone becomes «+7 (916)
# 402-11-87») and tags the piece with the item bound to the column, so the
# offsets are laid as the body is composed and nothing is ever searched for.
#
# THE SENDER IS NOT IN THE BODY. `from_name` and `from_email` are envelope
# columns; putting the name in the prose as well would give two items one value,
# which the mock's by-value index drops — both would be untagged and every hop on
# them would score as a gateway miss no gateway could avoid.
LETTER_BODY: str = ("Здравствуйте. Прошу оформить заявку. Мой телефон {phone}, "
                    "адрес {street}, дата рождения {dob}. Заранее спасибо.")
LETTER_COMPLAINT: str = ("Добрый день. Курьер не приехал. Телефон для связи {phone}, "
                         "доставка была на {street}, дата рождения для сверки {dob}.")
LETTER_BODIES: tuple[str, ...] = (LETTER_BODY, LETTER_COMPLAINT)
LETTER_SUBJECTS: tuple[str, ...] = ("Заявка на доставку", "Не приехал курьер",
                                    "Перенос доставки", "Уточнение по заказу")
# The two shapes `mail_read` answers a letter in, and the seeded row decides
# which. «full» hands the envelope back typed and the body apart; «raw» hands
# headers and body over as ONE untyped string, which is the shape this corpus
# had nowhere and the harder of the two for a gateway.
LETTER_FORMATS: tuple[str, ...] = ("full", "raw")
# The envelope columns and the result leaf each arrives at in the «full» shape.
LETTER_ENVELOPE: tuple[tuple[str, str], ...] = (
    ("from_name", MAIL_FROM_NAME), ("from_email", MAIL_FROM_EMAIL))
# The columns the BODY carries. Split from the envelope because a typed header
# field and a value inside somebody's prose are two different problems for a
# gateway, and one leaf for both would hide which of the two it fails.
LETTER_INSIDE: tuple[str, ...] = ("phone", "street", "dob")


def letter_seed(builder: c.CaseBuilderV5, index: int, sender: c.Drawn, ctx: c.Ctx,
                identity: str, template: str, shape: str) -> tuple[str, dict[str, str]]:
    """One row of `mailbox`, and the {column: item id} map its readers need.

    Returns `(the letter's id, the map)`.

    THE STORED NOTATIONS ARE THE BACKEND'S, NOT THE CALLER'S. The address is
    stored lower-cased because `mock._mail_head` lower-cases it and a column that
    disagreed with the rendered result would put the item's value beside a span
    that does not equal it; the phone column holds «+79164021187» and the prose
    renders «+7 (916) 402-11-87»; the birth date is ISO. No speech register
    writes any of the three, which is the whole reason a letter is worth reading
    back — `differs_from_user_form` is a property of the RESULT, and a result in
    the register the caller used measures nothing about adaptation.
    """
    if shape not in LETTER_FORMATS:
        raise pools.BuildError(f"unknown letter shape {shape!r}; the two are {LETTER_FORMATS}")
    # THE PARAMETER IS `template` AND NOT `body`, and that is the search proof
    # rather than taste: `build.SEARCHED_SURFACES` watches the name `body`
    # because a FINISHED letter must never be asked what it contains. This is the
    # template BEFORE anything is rendered into it, the same check
    # `common.prose_seed` makes on its own `template`, so the name says which of
    # the two it is.
    missing = tuple(slot for slot in LETTER_INSIDE if f"{{{slot}}}" not in template)
    if missing:
        raise pools.BuildError(f"letter template names no slot for {missing}; every column "
                               f"declared as read from the body must be rendered into it")
    key = message_key(index)
    sender_name = c.full_name(sender.person)
    sender_email = f"{sender.email_local}@{sender.email_domain}".lower()
    phone = f"+7{sender.phone}"
    street = sender.address.street
    iso = c.iso_date(sender.dob)
    fields: dict[str, object] = {
        "format": shape, "thread_id": f"thr-{index}", "date": "2026-09-02",
        "to": "office@example.ru",
        "subject": LETTER_SUBJECTS[index % len(LETTER_SUBJECTS)],
        "from_name": sender_name, "from_email": sender_email, "template": template,
        "phone": phone, "street": street, "dob": iso}
    typed: dict[str, tuple[str, str, Rendered]] = {
        "from_name": ("NAME", identity, Rendered(sender_name, sender_name, False,
                                                 {"surname": sender.person.surname[0],
                                                  "given": sender.person.given[0],
                                                  "gender": sender.person.gender})),
        "from_email": ("EMAIL", identity, Rendered(sender_email, sender_email, False,
                                                   {"local": sender.email_local,
                                                    "domain": sender.email_domain})),
        "phone": ("PHONE", identity, Rendered(phone, phone, False, {"digits": sender.phone})),
        "street": ("LOC", f"{identity}.home", _stored_street(sender)),
        "dob": ("DOB", identity, Rendered(iso, iso, False, {"iso": iso})),
    }
    return key, c.seeded(builder, key, "mailbox", fields, typed)


def letter_leaves(shape: str) -> tuple[tuple[str, str], ...]:
    """Which result leaf each column of a letter arrives at, in THIS shape.

    «raw» puts every one of them in one string, so the leaf is the same for all
    five; «full» separates the envelope from the body. Answered here rather than
    branched on in three families, because the branch is a property of the letter
    and a family that got it wrong would declare crossings the mock never makes.
    """
    if shape == "raw":
        return tuple((column, MAIL_RAW)
                     for column, _leaf in LETTER_ENVELOPE) + tuple(
                         (column, MAIL_RAW) for column in LETTER_INSIDE)
    return LETTER_ENVELOPE + tuple((column, MAIL_BODY) for column in LETTER_INSIDE)


def letter_form(shape: str) -> str:
    """The `ReturnExpectation` form `mail_read` answers this shape in."""
    return "free_text" if shape == "raw" else "nested"


def _stored_street(drawn: c.Drawn) -> Rendered:
    """A street as a backend column holds it: the bare name, no generic word.

    THE SAME FACT AS `plan_b.stored_street`, AND IT IS NOT IMPORTED. This module
    is reached from BOTH plans — `plan_a`'s four client families and `plan_b`'s
    `office` — so importing `plan_b` here would close a cycle through
    `plan_b → office → client_tools → plan_b` in which `plan_a`'s half sees a
    half-initialised module. Two lines, and the day one of the two plans stops
    being a plan they become one.
    """
    street = drawn.address.street
    return Rendered(street, street, False, {"street": street})


def conversation_id(behaviour: str, index: int) -> str:
    """An explicit conversation id on every fifth case, derived on the rest —
    the rule both halves of the corpus already apply (K09 wants both kinds)."""
    return f"conv-{behaviour}-{index}" if index % 5 == 0 else ""


# The registers a written identifier can be SAID in at all. An address carries a
# dot and almost always a digit run, and v4's register gate — 53 324 measured
# utterances — refuses a digit or sentence punctuation in `voice_raw` and
# punctuation in `voice_itn`. The corpus agrees with the gate all by itself:
# of its 1 196 EMAIL items exactly 14 are in a user message, 10 of them `chat`
# and 4 `sloppy`, and none in either speech register.
#
# SO THE OPERATOR'S OWN ADDRESS IS SAID WHERE IT CAN BE SAID AND NOWHERE ELSE.
# The alternative — spelling it out as «оператор сорок собака мейл точка ру» —
# would be this corpus inventing a notation its own measurements say nobody uses,
# and a benchmark that invents the customer's notation measures its own fiction.
# The speech half of each family therefore carries the letter's or the card's
# values and no address of its own, which is a share of one hop given up on
# purpose rather than a shape written wrong.
WRITTEN_REGISTERS: tuple[str, ...] = ("chat", "sloppy", "clean")


def can_say_address(ctx: c.Ctx) -> bool:
    """Whether this case's register can carry an e-mail address in a user
    message at all. See `WRITTEN_REGISTERS`."""
    return ctx.register in WRITTEN_REGISTERS


def operator_email(ctx: c.Ctx, index: int) -> tuple[str, str]:
    """The address the operator asking for the work answers from.

    ITS OWN STREAM, NOT `ctx.rng`, for the reason `extra_people` gives: drawing
    from the case's stream would shift every later draw, so adding the operator
    to a family would silently be a new corpus rather than the same corpus with
    an operator in it. The local part is derived from the index alone, so no two
    cases of one family share it and the mock's by-value index never has to drop
    a tag.
    """
    local = f"operator{ctx.seed}{index}"
    domain = pools.EMAIL_DOMAINS[index % len(pools.EMAIL_DOMAINS)]
    return local, domain
