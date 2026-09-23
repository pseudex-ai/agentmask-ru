"""The v5 registry under test: the 55 tools, their forms, their strict parsers.

THE RULES ARE SHOWN FAILING. `registry_problems` is handed five broken copies
of the registry — a vertical with no list, one with no error and no empty, one
whose every result is written the way the user writes it, a tool with an empty
`result_pii`, a tool whose parser accepts anything — and each must come back
red. A rule that has never been red is a rule nobody has tested.

THE NOTATIONS ARE READ OFF A REAL RENDER, never off the declaration: the world
in `test_mock.seeded_world` is driven through the backend and the strings that
come out are compared with what §2 of the ТЗ names («г Самара, ул Луговая,
д 10», «+7 (916) …», ISO dates, «XXX-XXX-XXX YY», a card in four groups). A
declared form nothing can produce would otherwise pass forever.
"""
import json
import re
import sys
from dataclasses import replace

from bench.agentpii4.tools import CSV_HEADER, REGISTRY as V4_REGISTRY, Refusal
from bench.agentpii5 import tools as v5tools
from bench.agentpii5.contracts import (NEW_TOOL_NAMES, NEW_TOOL_RETURN_FORMS, SUITES,
                                       TOOL_SUITE, TOOL_VERTICAL, V4_TOOL_NAMES, VERTICALS)
from bench.agentpii5.mock import snils_spaced
from bench.agentpii5.test_mock import (FORM_TEXT, INN_ACTIVE, PHONE, SNILS_REVOKED,
                                       SNILS_UNSEEDED, SNILS_VALID, bare_world,
                                       seeded_world)
from bench.agentpii5.tools import (NEW_REGISTRY, REGISTRY_V5,
                                   colliding_tool_names, generic_paths, registry_problems)

SUITE_TOOLS: tuple[str, ...] = tuple(
    name for name, suite in TOOL_SUITE.items() if suite == "office")
CANON_ADDRESS = "г Ижевск, ул Пушкина, д 41, кв 7"
COURIER_ADDRESS = "г. Ижевск, ул. Пушкина, д. 41, кв. 7"
CANON_PHONE = "+7 (916) 402-11-87"
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
SNILS_SHAPE = re.compile(r"\d{3}-\d{3}-\d{3} \d{2}")
CARD_SHAPE = re.compile(r"(?:\d{4} ){3}\d{4}")
PLATE_SHAPE = re.compile(r"[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}")


def body(tool: str, arguments: dict[str, object]) -> dict[str, object]:
    """One call against a freshly seeded world, as the model would read it."""
    backend = seeded_world()
    log = backend.call(tool, arguments)
    if log.refusal is not None:
        raise AssertionError(f"{tool} refused its own fixture: {log.refusal}")
    return json.loads(log.result_text)


def test_no_pseudex() -> list[str]:
    leaked = [name for name in sys.modules if name.split(".")[0] == "pseudex"]
    return [f"the registry pulled in {leaked}"] if leaked else []


def test_counts() -> list[str]:
    problems: list[str] = []
    # 55: v4's 31, the thirteen of §8.1, and the OFFICE SUITE's eleven. The
    # suite is the first enterprise customer's own shapes, generalised so the
    # corpus outlives the deal — and it is measurable as a set through
    # `--slice suite=office`, which the vertical could never answer because its
    # eleven tools fall into five different verticals.
    if len(REGISTRY_V5) != 55:
        problems.append(f"{len(REGISTRY_V5)} tools, expected 55")
    suited = sorted(name for name, spec in REGISTRY_V5.items() if spec.suite)
    if len(suited) != len(SUITE_TOOLS) or set(suited) != set(SUITE_TOOLS):
        problems.append(f"the office suite holds {suited}, expected {sorted(SUITE_TOOLS)}")
    for name, spec in REGISTRY_V5.items():
        if spec.suite and spec.suite not in SUITES:
            problems.append(f"{name}: suite {spec.suite!r} is not in contracts.SUITES")
        if spec.suite != TOOL_SUITE.get(name, ""):
            problems.append(f"{name}: suite {spec.suite!r}, contracts says "
                            f"{TOOL_SUITE.get(name, '')!r}")
    # THE SUITE IS NOT A VERTICAL, AND THIS IS THE CHECK THAT SAYS SO. If its
    # eleven tools all sat in one vertical, `--slice vertical=…` would already
    # answer the customer's question and the axis would be decoration.
    if len({REGISTRY_V5[name].vertical for name in SUITE_TOOLS}) < 5:
        problems.append("the office suite fits inside fewer than five verticals — "
                        "then the vertical axis would already isolate it")
    expected = set(V4_TOOL_NAMES) | set(NEW_TOOL_NAMES)
    if set(REGISTRY_V5) != expected:
        problems.append(f"missing {sorted(expected - set(REGISTRY_V5))}, "
                        f"extra {sorted(set(REGISTRY_V5) - expected)}")
    for name, spec in REGISTRY_V5.items():
        if spec.vertical not in VERTICALS:
            problems.append(f"{name}: vertical {spec.vertical!r} is not a contracts vertical")
        if spec.vertical != TOOL_VERTICAL[name]:
            problems.append(f"{name}: filed under {spec.vertical!r}, contracts says "
                            f"{TOOL_VERTICAL[name]!r}")
    if set(TOOL_VERTICAL.values()) != set(VERTICALS):
        problems.append("a vertical of contracts.VERTICALS has no tool at all")
    for name, spec in REGISTRY_V5.items():
        if spec.base.name != name:
            problems.append(f"{name} holds a spec named {spec.base.name!r}")
    return problems


def test_v4_kept() -> list[str]:
    problems: list[str] = []
    for name in V4_TOOL_NAMES:
        if name not in REGISTRY_V5:
            problems.append(f"{name} was dropped")
            continue
        spec = REGISTRY_V5[name]
        # THE SAME OBJECT: a v4 run must offer the model byte-identical tool
        # definitions, or the baseline moved with the treatment.
        if spec.base.schema is not V4_REGISTRY[name].schema:
            problems.append(f"{name}: the schema is not v4's object")
        if spec.base.fields is not V4_REGISTRY[name].fields:
            problems.append(f"{name}: the field specs are not v4's")
        if spec.base.parse is not V4_REGISTRY[name].parse:
            problems.append(f"{name}: the parser is not v4's")
    return problems


def test_v4_tools_revised() -> list[str]:
    """Every v4 tool carries a result the IN/tool hop can be measured on. There
    is no exemption list any more (ruling R-41): a write's result on a SEEDED
    row is the stored card in the system's notation, and on an unseeded row
    R05 forbids the hop — so V04 holds for every tool without a side door."""
    problems: list[str] = []
    for name in V4_TOOL_NAMES:
        spec = REGISTRY_V5[name]
        if not spec.return_forms:
            problems.append(f"{name}: no return form declared")
        if not spec.base.result_pii:
            problems.append(f"{name}: result_pii is still empty")
    empty_in_v4 = [name for name in V4_TOOL_NAMES if not V4_REGISTRY[name].result_pii]
    if len(empty_in_v4) != 22:
        problems.append(f"v4 left {len(empty_in_v4)} tools without result_pii, expected 22 — "
                        f"the baseline changed under us")
    return problems


def test_v4_registry_is_widened() -> list[str]:
    """The twelve are published into v4's in-memory registry, and nothing of
    v4's is overwritten (ruling R-24).

    WHY THIS IS A TEST AND NOT A COMMENT. v4's `validate` refuses a `case.tools`
    name it does not know, so without the widening no v5 case can offer a new
    tool at all; with a colliding name it would score a v4 case against the
    wrong API. The refusal is shown failing on a doctored pair, because after
    the widening the live registries intersect BY DESIGN and the import-time
    answer survives only in `_COLLIDING_TOOL_NAMES`.
    """
    problems: list[str] = []
    if v5tools._COLLIDING_TOOL_NAMES:                      # noqa: SLF001 - the import's own answer
        problems.append(f"the widening overwrote {list(v5tools._COLLIDING_TOOL_NAMES)}")  # noqa: SLF001
    for name in NEW_TOOL_NAMES:
        if V4_REGISTRY.get(name) is not NEW_REGISTRY[name]:
            problems.append(f"{name} did not reach v4's registry as this module's own spec")
    if set(V4_REGISTRY) != set(V4_TOOL_NAMES) | set(NEW_TOOL_NAMES):
        problems.append(f"v4's registry now holds {sorted(set(V4_REGISTRY))}")
    doctored = {"ticket_find": NEW_REGISTRY["kb_search"], "kb_search": NEW_REGISTRY["kb_search"]}
    if colliding_tool_names(doctored, V4_REGISTRY)[:1] != ("kb_search",):
        problems.append("the collision rule did not name a tool that already exists")
    if colliding_tool_names({}, V4_REGISTRY):
        problems.append("the collision rule invented a collision out of nothing")
    return problems


def test_every_tool_has_form() -> list[str]:
    return [f"{name}: {len(spec.return_forms)} forms" for name, spec in REGISTRY_V5.items()
            if not spec.return_forms]


def test_vertical_rules() -> list[str]:
    problems: list[str] = []
    live = registry_problems(REGISTRY_V5)
    if live:
        problems.append(f"the shipped registry is not clean: {live}")

    def without(vertical: str, form: str) -> dict[str, object]:
        broken = dict(REGISTRY_V5)
        for name, spec in REGISTRY_V5.items():
            if spec.vertical != vertical:
                continue
            broken[name] = replace(spec, return_forms=tuple(
                one for one in spec.return_forms if one.form != form))
        return broken

    bank_no_list = without("bank", "list")
    if not any(one.startswith("V01") and "bank" in one
               for one in registry_problems(bank_no_list)):   # type: ignore[arg-type]
        problems.append("V01 stayed silent when a vertical lost every list form")
    support = dict(REGISTRY_V5)
    for name, spec in REGISTRY_V5.items():
        if spec.vertical == "support":
            support[name] = replace(spec, return_forms=tuple(
                one for one in spec.return_forms
                if one.form not in ("error_with_value", "empty")))
    if not any(one.startswith("V02") for one in registry_problems(support)):  # type: ignore[arg-type]
        problems.append("V02 stayed silent when a vertical lost every error and empty form")
    flattened = {name: replace(spec, differs_from_user_form=False)
                 for name, spec in REGISTRY_V5.items()}
    if len([one for one in registry_problems(flattened) if one.startswith("V03")]) != len(VERTICALS):
        problems.append("V03 did not name every vertical when no result differs from the user's")
    hollow = dict(REGISTRY_V5)
    hollow["kb_search"] = replace(REGISTRY_V5["kb_search"],
                                  base=replace(REGISTRY_V5["kb_search"].base, result_pii=()))
    if not any(one.startswith("V04") and "kb_search" in one
               for one in registry_problems(hollow)):          # type: ignore[arg-type]
        problems.append("V04 stayed silent on a tool whose result carries nothing")
    lax = dict(REGISTRY_V5)
    lax["file_read"] = replace(REGISTRY_V5["file_read"],
                               base=replace(REGISTRY_V5["file_read"].base,
                                            parse=lambda arguments: dict(arguments)))
    if not any(one.startswith("V05") and "file_read" in one
               for one in registry_problems(lax)):             # type: ignore[arg-type]
        problems.append("V05 stayed silent on a parser that accepts an empty call")
    # V06 IS SHOWN FAILING ON THE EXACT SHAPE THAT LIVED IN THE REGISTRY: a leaf
    # added to `result_pii` and named by no return form. Before 23.09 five of
    # the 142 declared paths were that shape — `courier_status.recipient.
    # {name,phone}` and `crm_upsert_contact.contact.{first_name,last_name,
    # phone}` — and deleting any of them reddened nothing in the package.
    unpromised = dict(REGISTRY_V5)
    unpromised["snils_verify"] = replace(
        REGISTRY_V5["snils_verify"],
        base=replace(REGISTRY_V5["snils_verify"].base,
                     result_pii=(*REGISTRY_V5["snils_verify"].base.result_pii,
                                 "person.middle_name")))
    if not any(one.startswith("V06") and "person.middle_name" in one
               for one in registry_problems(unpromised)):       # type: ignore[arg-type]
        problems.append("V06 stayed silent on a result_pii path no return form names")
    # And the other direction, so V06 is not simply V04 spelled twice: a form
    # that names a path `result_pii` does not hold is V04's, and V06 must not
    # claim it.
    if any(one.startswith("V06") for one in registry_problems(dict(REGISTRY_V5))):
        problems.append("V06 is red on the registry as it stands")
    return problems


GOOD_CALLS: tuple[tuple[str, dict[str, object]], ...] = (
    ("kb_search", {"query": "Громова Марина", "k": 3}),
    ("doc_retrieve", {"doc_id": "doc-1"}),
    ("file_read", {"path": "/mnt/in/clients.csv"}),
    ("form_parse", {"text": FORM_TEXT}),
    ("bank_client_find", {"inn": INN_ACTIVE}),
    ("bank_client_find", {"phone": PHONE}),
    ("account_statement", {"client_id": "bc-1", "from": "2026-08-01", "to": "2026-08-31"}),
    ("vehicle_check", {"plate": "Х501УН36"}),
    ("snils_verify", {"snils": snils_spaced(SNILS_VALID)}),
    ("calendar_free", {"person": "Громова Марина", "date": "2026-09-10"}),
    ("email_send", {"to": "grom@mail.ru", "subject": "Заказ", "body": "Здравствуйте!"}),
    ("ticket_history", {"issue_id": "t-1"}),
    ("courier_status", {"claim_id": "clm-1"}),
    ("patient_find", {"phone": PHONE}),
    ("patient_find", {"snils": snils_spaced(SNILS_VALID)}),
    # --- the office suite ----------------------------------------------------
    ("mail_read", {"message_id": "msg-1"}),
    ("mail_search", {"query": "from:grom@mail.ru", "max_results": 5}),
    ("mail_send", {"to": ["grom@mail.ru", "bukin@mail.ru"], "cc": ["boss@corp.ru"],
                   "subject": "Ответ", "body": "Здравствуйте!"}),
    ("calendar_invite", {"summary": "Встреча",
                         "attendees": [{"email": "grom@mail.ru", "name": "Громова Марина"}],
                         "start": "2026-09-05T09:30:00+04:00",
                         "end": "2026-09-05T10:00:00+04:00", "description": "Повестка"}),
    ("tracker_find_user", {"query": "Соколов"}),
    ("tracker_issue_create", {"project_key": "SUP", "summary": "Перенос",
                              "description": "Клиент просит", "assignee": "Соколов Андрей"}),
    ("crm_upsert_card", {"contact": {"last_name": "Громова", "phone": PHONE},
                         "deal": {"title": "Доставка", "price": "1500.00", "stage": "new",
                                  "contact_name": "Громова Марина", "note": "пятница"}}),
    ("sheet_append_row", {"spreadsheet_id": "sh-1", "range": "Лист1!A1:E1",
                          "values": [["Громова Марина", PHONE]]}),
    ("doc_append", {"document_id": "doc-1", "text": "Дописано."}),
    ("memory_save", {"subject": "Громова Марина", "fact": "Звонить после 18:00"}),
    ("reminder_set", {"remind_at": "2026-09-05T09:00:00+03:00", "text": "Позвонить",
                      "recipient": {"name": "Громова Марина", "phone": PHONE}}),
)
BAD_CALLS: tuple[tuple[str, dict[str, object], str], ...] = (
    ("kb_search", {"query": "   ", "k": 3}, "empty_query"),
    ("kb_search", {"query": "x" * 201, "k": 3}, "too_long"),
    ("kb_search", {"query": 7, "k": 3}, "not_a_string"),
    ("kb_search", {"query": "Громова", "k": 11}, "out_of_range"),
    ("doc_retrieve", {"doc_id": "doc_1"}, "id_format"),
    ("file_read", {"path": "/mnt/in/clients.pdf"}, "path_extension"),
    ("file_read", {"path": "/mnt/in/../../etc/passwd.txt"}, "path_traversal"),
    ("form_parse", {"text": "   "}, "empty_text"),
    ("form_parse", {"text": "x" * 4001}, "too_long"),
    ("bank_client_find", {"inn": INN_ACTIVE, "phone": PHONE}, "exactly_one_key"),
    ("bank_client_find", {}, "exactly_one_key"),
    ("bank_client_find", {"inn": "12345"}, "inn_format"),
    ("bank_client_find", {"inn": INN_ACTIVE[:-1] + str((int(INN_ACTIVE[-1]) + 1) % 10)},
     "inn_checksum"),
    ("bank_client_find", {"phone": "89164021187"}, "phone_not_e164"),
    ("account_statement", {"client_id": "bc_1"}, "id_format"),
    ("account_statement", {"client_id": "bc-1", "from": "10.09.2026"}, "date_not_iso8601"),
    ("account_statement", {"client_id": "bc-1", "from": "2026-09-10", "to": "2026-09-01"},
     "range_order"),
    # A LATIN LOOK-ALIKE IS REFUSED, NOT FOLDED: the ГИБДД service takes the
    # Cyrillic plate, and repairing it here would hide the confusion the PLATE
    # cases exist to provoke.
    ("vehicle_check", {"plate": "X501YH36"}, "plate_format"),
    ("vehicle_check", {"plate": "Х 501 УН 3"}, "plate_format"),
    ("snils_verify", {"snils": "11223344595"}, "snils_format"),
    ("snils_verify", {"snils": "112-233-445 96"}, "snils_checksum"),
    ("calendar_free", {"person": "Громова Марина Борисовна Петровна", "date": "2026-09-10"},
     "name_format"),
    ("calendar_free", {"person": "Громова", "date": "10.09.2026"}, "date_not_iso8601"),
    ("email_send", {"to": "grom@mail", "subject": "x", "body": "y"}, "email_format"),
    ("email_send", {"to": "grom@mail.ru", "subject": "x" * 201, "body": "y"}, "too_long"),
    ("ticket_history", {"issue_id": "tt-1"}, "id_format"),
    ("courier_status", {"claim_id": "clm1"}, "id_format"),
    ("patient_find", {"phone": PHONE, "snils": snils_spaced(SNILS_VALID)}, "exactly_one_key"),
    ("patient_find", {}, "exactly_one_key"),
    ("patient_find", {"phone": "89164021187"}, "phone_not_e164"),
    ("patient_find", {"snils": "112233445 95"}, "snils_format"),
    # --- the office suite ----------------------------------------------------
    ("mail_read", {"message_id": "msg_1"}, "id_format"),
    ("mail_read", {}, "missing_required"),
    ("mail_search", {"query": "   ", "max_results": 5}, "empty_query"),
    ("mail_search", {"query": "x" * 201, "max_results": 5}, "too_long"),
    ("mail_search", {"query": "from:grom@mail.ru", "max_results": 51}, "out_of_range"),
    # THE LIST IS THE NEW SHAPE, so every way it can be wrong is named.
    ("mail_send", {"to": "grom@mail.ru", "subject": "x", "body": "y"}, "recipient_format"),
    ("mail_send", {"to": [], "subject": "x", "body": "y"}, "no_recipients"),
    ("mail_send", {"to": ["a@b.ru"] * 21, "subject": "x", "body": "y"},
     "too_many_recipients"),
    ("mail_send", {"to": ["grom@mail"], "subject": "x", "body": "y"}, "recipient_format"),
    ("mail_send", {"to": ["grom@mail.ru"], "cc": ["boss@corp"], "subject": "x", "body": "y"},
     "recipient_format"),
    ("mail_send", {"to": ["grom@mail.ru"], "subject": "x" * 201, "body": "y"}, "too_long"),
    ("calendar_invite", {"summary": "x", "attendees": [], "start": "2026-09-05T09:30:00+04:00",
                         "end": "2026-09-05T10:00:00+04:00"}, "no_attendees"),
    ("calendar_invite", {"summary": "x", "attendees": [{"email": "grom@mail"}],
                         "start": "2026-09-05T09:30:00+04:00",
                         "end": "2026-09-05T10:00:00+04:00"}, "attendee_format"),
    # THE INTERVAL IS COMPARED AS AN INSTANT, AND THIS PAIR IS THE PROOF: as
    # strings «09:00+00:00» sorts BEFORE «10:00+04:00» and a string comparison
    # would accept it, while as instants it is 09:00 UTC against 06:00 UTC — an
    # hour backwards. A calendar in two time zones is where that happens.
    ("calendar_invite", {"summary": "x", "attendees": [{"email": "grom@mail.ru"}],
                         "start": "2026-09-05T09:00:00+00:00",
                         "end": "2026-09-05T10:00:00+04:00"}, "interval_order"),
    ("calendar_invite", {"summary": "x", "attendees": [{"email": "grom@mail.ru"}],
                         "start": "05.09.2026 09:30", "end": "2026-09-05T10:00:00+04:00"},
     "datetime_not_iso8601"),
    ("tracker_find_user", {"query": "  "}, "empty_query"),
    ("tracker_find_user", {"query": "x" * 101}, "too_long"),
    ("tracker_find_user", {"query": "Соколов", "max_results": 0}, "out_of_range"),
    ("tracker_issue_create", {"project_key": "sup", "summary": "x"}, "project_key"),
    ("tracker_issue_create", {"project_key": "SUP", "summary": "x" * 256}, "summary_too_long"),
    ("crm_upsert_card", {}, "empty_card"),
    ("crm_upsert_card", {"contact": {"last_name": "Громова", "phone": "89164021187"}},
     "phone_not_e164"),
    ("crm_upsert_card", {"deal": {"price": "полторы тысячи"}}, "price_format"),
    ("crm_upsert_card", {"deal": {"stage": "почти"}}, "stage_unknown"),
    ("sheet_append_row", {"spreadsheet_id": "sh-1", "range": "Лист1", "values": [["x"]]},
     "range_format"),
    ("sheet_append_row", {"spreadsheet_id": "sh-1", "range": "A1", "values": ["x"]},
     "not_a_matrix"),
    ("sheet_append_row", {"spreadsheet_id": "sh-1", "range": "A1", "values": []}, "no_rows"),
    ("sheet_append_row", {"spreadsheet_id": "sh-1", "range": "A1",
                          "values": [["x"]] * 51}, "too_many_rows"),
    ("sheet_append_row", {"spreadsheet_id": "sheet1", "range": "A1", "values": [["x"]]},
     "id_format"),
    ("doc_append", {"document_id": "doc_1", "text": "x"}, "id_format"),
    ("doc_append", {"document_id": "doc-1", "text": "   "}, "empty_text"),
    ("doc_append", {"document_id": "doc-1", "text": "x" * 20001}, "too_long"),
    ("memory_save", {"subject": "  ", "fact": "x"}, "empty_subject"),
    ("memory_save", {"subject": "Громова", "fact": "  "}, "empty_fact"),
    ("memory_save", {"subject": "Громова", "fact": "x", "scope": "весь мир"}, "scope_unknown"),
    ("reminder_set", {"remind_at": "05.09.2026", "text": "x",
                      "recipient": {"phone": PHONE}}, "datetime_not_iso8601"),
    ("reminder_set", {"remind_at": "2026-09-05T09:00:00+03:00", "text": "  ",
                      "recipient": {"phone": PHONE}}, "empty_text"),
    ("reminder_set", {"remind_at": "2026-09-05T09:00:00+03:00", "text": "x",
                      "recipient": {"phone": "89164021187"}}, "phone_not_e164"),
)


def test_parsers_good_bad() -> list[str]:
    problems: list[str] = []
    for tool, arguments in GOOD_CALLS:
        parsed = NEW_REGISTRY[tool].parse(dict(arguments))
        if isinstance(parsed, Refusal):
            problems.append(f"{tool} refused a documented shape: {parsed}")
    for tool, arguments, rule in BAD_CALLS:
        parsed = NEW_REGISTRY[tool].parse(dict(arguments))
        if not isinstance(parsed, Refusal) or parsed.rule != rule:
            problems.append(f"{tool} expected {rule}, got {parsed}")
    covered = {tool for tool, _args in GOOD_CALLS}, {tool for tool, _args, _rule in BAD_CALLS}
    for name in NEW_TOOL_NAMES:
        if name not in covered[0] or name not in covered[1]:
            problems.append(f"{name}: no accepted and refused shape in the table")
    return problems


def test_examples_resolve() -> list[str]:
    problems: list[str] = []
    for name, spec in REGISTRY_V5.items():
        for form in spec.return_forms:
            try:
                example = json.loads(form.example)
            except json.JSONDecodeError as error:
                problems.append(f"{name}/{form.form}: the example is not JSON: {error}")
                continue
            paths = generic_paths(example)
            for path in form.pii_paths:
                if path not in paths:
                    problems.append(f"{name}/{form.form}: pii path {path!r} does not resolve "
                                    f"in the example ({sorted(paths)})")
    for name in NEW_TOOL_NAMES:
        declared = {one.form for one in REGISTRY_V5[name].return_forms}
        missing = set(NEW_TOOL_RETURN_FORMS[name]) - declared
        if missing:
            problems.append(f"{name}: contracts asks for {sorted(missing)}, which is not declared")
    return problems


def test_directory_canon() -> list[str]:
    problems: list[str] = []
    result = body("address_suggest", {"query": "Пушкина 41 кв 7", "count": 1})
    value = result["suggestions"][0]["value"]                                  # type: ignore[index]
    if value != CANON_ADDRESS:
        problems.append(f"address_suggest rendered {value!r}, expected {CANON_ADDRESS!r}")
    normalised = body("normalize_contact", {"name": "громова марина борисовна",
                                            "phone": "89164021187", "address": "пушкина 41"})
    if normalised["phone"]["formatted"] != CANON_PHONE:                        # type: ignore[index]
        problems.append(f"normalize_contact rendered "
                        f"{normalised['phone']['formatted']!r}, expected {CANON_PHONE!r}")
    if normalised["address"]["value"] != "ул Пушкина, д 41":                   # type: ignore[index]
        problems.append(f"the canon address is {normalised['address']['value']!r}")
    for name in ("address_suggest", "normalize_contact"):
        forms = {one.form for one in REGISTRY_V5[name].return_forms}
        if "canon" not in forms or not REGISTRY_V5[name].differs_from_user_form:
            problems.append(f"{name} does not declare canon / differs_from_user_form")
    return problems


def test_clinic_iso_snils() -> list[str]:
    problems: list[str] = []
    booked = body("clinic_book", {
        "patient": {"last_name": "Павлова", "first_name": "Тамара", "birth_date": "1987-03-14",
                    "age": 39, "gender": "F"},
        "phone": PHONE, "speciality": "кардиолог", "slot": "2026-09-05T09:30:00+04:00"})
    birth = booked["patient"]["birth_date"]                                    # type: ignore[index]
    if not ISO_DATE.fullmatch(str(birth)):
        problems.append(f"clinic_book returned birth_date {birth!r}, expected ISO")
    verified = body("snils_verify", {"snils": snils_spaced(SNILS_VALID)})
    if not SNILS_SHAPE.fullmatch(str(verified["snils"])):
        problems.append(f"snils_verify returned {verified['snils']!r}, "
                        f"expected XXX-XXX-XXX YY")
    if not ISO_DATE.fullmatch(str(verified["person"]["birth_date"])):          # type: ignore[index]
        problems.append("the ПФР record's birth date is not ISO")
    return problems


def test_clinic_reads_a_card_back() -> list[str]:
    """§2's clinic row, and the only tool of the vertical that can answer it.

    THE VERTICAL HAD FIVE TOOLS AND ALL FIVE WROTE. `clinic_book`, `referral_
    create`, `appointment_cancel`/`_reschedule` echo the values the dialogue
    just handed them, and `clinic_slots` answers with a doctor — so «ДР ISO,
    СНИЛС с разделителями» was a promise no call could keep, and the corpus
    declared 584 clinic hops with not one IN/tool among them. This reads a
    STORED card: every notation below is the МИС's own and none of them is one
    a caller's register produces.
    """
    problems: list[str] = []
    found = body("patient_find", {"phone": PHONE})
    if found.get("found") is not True:
        return [f"patient_find did not find the seeded card: {found}"]
    card = found["patient"]                                                    # type: ignore[index]
    if not ISO_DATE.fullmatch(str(card["birth_date"])):                        # type: ignore[index]
        problems.append(f"the card's birth date is {card['birth_date']!r}, expected ISO")
    if not SNILS_SHAPE.fullmatch(str(card["snils"])):                          # type: ignore[index]
        problems.append(f"the card's СНИЛС is {card['snils']!r}, expected XXX-XXX-XXX YY")
    if str(card["phone"]) != PHONE:                                            # type: ignore[index]
        problems.append(f"the card's phone is {card['phone']!r}, expected E.164")
    # THE SEARCH IS BY DIGIT SIGNATURE, WHICH IS WHY THE SECOND KEY MUST FIND
    # THE SAME CARD: the parser hands over bare СНИЛС digits and the card holds
    # the separated spelling, so a string comparison would answer `empty` here
    # and the case would declare a result the backend never produced.
    by_snils = body("patient_find", {"snils": snils_spaced(SNILS_VALID)})
    if by_snils.get("found") is not True:
        problems.append("the card is not findable by the СНИЛС it stores")
    missing = body("patient_find", {"phone": "+79990000000"})
    if missing.get("found") is not False or "patient" in missing:
        problems.append(f"an unknown patient answered {missing!r}, expected an empty match")
    return problems


def test_bank_forms() -> list[str]:
    problems: list[str] = []
    found = body("bank_client_find", {"inn": INN_ACTIVE})
    client = found["client"]                                                   # type: ignore[index]
    if not CARD_SHAPE.fullmatch(str(client["card"])):                          # type: ignore[index]
        problems.append(f"the card came back as {client['card']!r}, expected four groups")
    if not str(client["inn"]).isdigit() or len(str(client["inn"])) not in (10, 12):
        problems.append(f"the ИНН came back as {client['inn']!r}, expected bare digits")
    statement = body("account_statement", {"client_id": "bc-1", "from": "2026-08-01",
                                           "to": "2026-08-31"})
    rows = statement["rows"]                                                   # type: ignore[index]
    if len(rows) < 2:                                                          # type: ignore[arg-type]
        problems.append(f"a statement of {len(rows)} rows cannot show many records of one person")
    holders = {row["holder"] for row in rows}                                  # type: ignore[index]
    if len(holders) != 1:
        problems.append(f"the statement rows name {holders}, expected one person")
    return problems


def test_ticket_history_free_text() -> list[str]:
    problems: list[str] = []
    backend = seeded_world()
    log = backend.call("ticket_history", {"issue_id": "t-1"})
    if backend.form_of(log.seq) != "free_text":
        problems.append(f"ticket_history came back as {backend.form_of(log.seq)!r}")
    history = str(json.loads(log.result_text)["history"])
    if "{" in history or ";" in history:
        problems.append(f"the history is not prose: {history!r}")
    if len(log.result_spans) < 2:
        problems.append(f"the prose carries {len(log.result_spans)} PII spans, expected ≥ 2")
    for tag, (start, end) in log.result_spans.items():
        if log.result_text[start:end] not in history:
            problems.append(f"span {tag} does not index the history text")
    return problems


def test_calendar_notations() -> list[str]:
    problems: list[str] = []
    result = body("calendar_free", {"person": "Громова Марина", "date": "2026-09-10"})
    slots = [str(one) for one in result["slots"]]                              # type: ignore[union-attr]
    shapes = {re.sub(r"\d", "0", slot) for slot in slots}
    if len(shapes) < 2:
        problems.append(f"the calendar answered in one notation only: {slots}")
    again = body("calendar_free", {"person": "Громова Марина", "date": "2026-09-10"})
    if again["slots"] != result["slots"]:
        problems.append("the notation draw is not seeded — two runs disagree")
    return problems


def test_government_forms() -> list[str]:
    problems: list[str] = []
    checked = body("vehicle_check", {"plate": "Х501УН36"})
    if not PLATE_SHAPE.fullmatch(str(checked["plate"])):
        problems.append(f"the plate came back as {checked['plate']!r}")
    if not checked["owner"]["last_name"]:                                      # type: ignore[index]
        problems.append("the vehicle came back without an owner")
    missing = body("vehicle_check", {"plate": "Е777КХ99"})
    if missing["error"]["subject"] != "Е777КХ99":                              # type: ignore[index]
        problems.append(f"the not-found error does not echo the plate: {missing}")
    unknown = body("snils_verify", {"snils": snils_spaced(SNILS_UNSEEDED)})
    if unknown.get("found") is not False or "person" in unknown:
        problems.append(f"an unseeded СНИЛС answered {unknown}, expected the empty form")
    revoked = body("snils_verify", {"snils": snils_spaced(SNILS_REVOKED)})
    if revoked["error"]["subject"] != snils_spaced(SNILS_REVOKED):             # type: ignore[index]
        problems.append(f"a revoked СНИЛС does not echo the number: {revoked}")
    for name in ("vehicle_check", "snils_verify", "passport_verify"):
        if REGISTRY_V5[name].vertical != "government":
            problems.append(f"{name} is not in the government vertical")
    return problems


def test_kb_search_chunks() -> list[str]:
    problems: list[str] = []
    backend = seeded_world()
    log = backend.call("kb_search", {"query": "Громова Марина Букин Сергей", "k": 3})
    if backend.form_of(log.seq) != "chunks":
        problems.append(f"kb_search came back as {backend.form_of(log.seq)!r}")
    hits = json.loads(log.result_text)["hits"]
    if len(hits) < 2:
        problems.append(f"{len(hits)} chunks came back, expected the foreign identity too")
    if [hit["score"] for hit in hits] != sorted((hit["score"] for hit in hits), reverse=True):
        problems.append(f"the chunks are not ranked: {[hit['score'] for hit in hits]}")
    for hit in hits:
        if not any(name in hit["text"] for name in ("Громова", "Букин", "Лапина")):
            problems.append(f"chunk {hit['id']} carries no personal datum: {hit['text']!r}")
    if len({hit["text"].split()[1] for hit in hits}) < 2:
        problems.append("every chunk is about the same person — nothing to keep apart")
    over = backend.call("kb_search", {"query": "Громова Марина Букин Сергей", "k": 1})
    if len(json.loads(over.result_text)["hits"]) != 1:
        problems.append("k did not bound the number of chunks")
    return problems


def test_file_forms() -> list[str]:
    problems: list[str] = []
    backend = seeded_world()
    table = backend.call("file_read", {"path": "/mnt/in/clients.csv"})
    if backend.form_of(table.seq) != "list":
        problems.append(f"a csv came back as {backend.form_of(table.seq)!r}")
    rows = json.loads(table.result_text)["rows"]
    if len(rows) != 2:
        problems.append(f"{len(rows)} rows, expected the two records of the file")
    if json.loads(table.result_text)["header"] != CSV_HEADER:
        problems.append("the csv header is not the one crm_import_csv demands")
    if not ISO_DATE.fullmatch(str(rows[0]["birth_date"])):
        problems.append(f"a csv row's birth date is {rows[0]['birth_date']!r}, expected ISO")
    text = backend.call("file_read", {"path": "/mnt/in/anketa.txt"})
    if backend.form_of(text.seq) != "free_text":
        problems.append(f"a txt came back as {backend.form_of(text.seq)!r}")
    form = backend.call("form_parse", {"text": FORM_TEXT})
    fields = json.loads(form.result_text)["fields"]
    for path in ("person", "passport", "address"):
        if path not in fields:
            problems.append(f"form_parse returned no {path}")
    if not SNILS_SHAPE.fullmatch(str(fields["snils"])):
        problems.append(f"the form's СНИЛС is {fields['snils']!r}")
    if REGISTRY_V5["crm_import_csv"].vertical != "files":
        problems.append("crm_import_csv is not in the files vertical")
    return problems


def test_courier_status_forms() -> list[str]:
    problems: list[str] = []
    tracked = body("courier_status", {"claim_id": "clm-1"})
    if tracked["address"] != COURIER_ADDRESS:
        problems.append(f"the courier rendered {tracked['address']!r}, "
                        f"expected {COURIER_ADDRESS!r}")
    recipient = tracked["recipient"]                                           # type: ignore[index]
    if not recipient["name"] or not recipient["phone"].startswith("+7"):       # type: ignore[index]
        problems.append(f"the recipient block is {recipient}")
    failed = body("courier_status", {"claim_id": "clm-2"})
    if failed["error"]["subject"] != COURIER_ADDRESS:                          # type: ignore[index]
        problems.append(f"the failed delivery does not echo the address: {failed}")
    forms = {one.form for one in REGISTRY_V5["courier_status"].return_forms}
    if forms < {"nested", "error_with_value"}:
        problems.append(f"courier_status declares {sorted(forms)}")
    return problems


def test_nested_address() -> list[str]:
    problems: list[str] = []
    form = body("form_parse", {"text": FORM_TEXT})["fields"]["address"]        # type: ignore[index]
    for part in ("street", "house", "flat"):
        if part not in form:
            problems.append(f"form_parse's address has no {part}")
    contacts = body("crm_find_contact", {"query": {"phone": PHONE}})["contacts"]  # type: ignore[index]
    address = contacts[0]["address"]                                           # type: ignore[index]
    for part in ("street", "house"):
        if part not in address:
            problems.append(f"crm_find_contact's address has no {part}")
    if REGISTRY_V5["courier_status"].return_forms[0].form != "nested":
        problems.append("courier_status does not lead with its nested form")
    return problems


def test_file_read_scan_noise() -> list[str]:
    problems: list[str] = []
    scanned = str(body("file_read", {"path": "/mnt/in/scan.txt"})["text"])
    clean = str(body("file_read", {"path": "/mnt/in/anketa.txt"})["text"])
    if not any(character in scanned for character in "oaec"):
        problems.append(f"the scan carries no Latin look-alike: {scanned!r}")
    if any(character in clean for character in "oaec"):
        problems.append(f"a plain page was noised: {clean!r}")
    if scanned != str(body("file_read", {"path": "/mnt/in/scan.txt"})["text"]):
        problems.append("the scan noise is not seeded by the document id")
    return problems


def test_empty_world_is_empty() -> list[str]:
    """The directory tools answer `empty` only where the directory is empty —
    the negative that keeps `test_each_form_renders`'s `empty` rows honest."""
    backend = bare_world()
    log = backend.call("address_suggest", {"query": "Пушкина 41", "count": 2})
    if backend.form_of(log.seq) != "empty":
        return [f"an empty directory answered {backend.form_of(log.seq)!r}"]
    return []




# --- the office suite: the notations read off a REAL render --------------------

RFC2822_DATE = re.compile(r"[A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} [+-]\d{4}")


def test_mail_notations() -> list[str]:
    """The mailbox's own notations, which no speech register produces — the
    whole of what `differs_from_user_form` promises about `mail_read`."""
    problems: list[str] = []
    letter = body("mail_read", {"message_id": "msg-1"})
    sender = dict(letter["from"])                                              # type: ignore[arg-type]
    # THE ADDRESS IS STORED MIXED-CASE AND ANSWERED LOWER-CASE. If the mock
    # echoed what was written, the IN hop on an e-mail could not fail and the
    # form line for EMAIL would be free marks for every gateway.
    if sender["email"] != "grom@mail.ru":
        problems.append(f"mail_read answered {sender['email']!r}, expected the lower-case form")
    if not RFC2822_DATE.fullmatch(str(letter["date"])):
        problems.append(f"mail_read answered the date {letter['date']!r}, expected RFC 2822")
    if not REGISTRY_V5["mail_read"].differs_from_user_form:
        problems.append("mail_read does not declare differs_from_user_form")
    raw = body("mail_read", {"message_id": "msg-2"})
    text = str(raw["raw"])
    if "From: " not in text or "Subject: " not in text:
        problems.append(f"the raw form is not an RFC 5322 source: {text[:80]!r}")
    if "\n" in text:
        # `writer._escape_free` refuses a control character inside a slot, so a
        # composed string is one line — the same constraint `_document_pieces`
        # carries, and the reason the headers are joined with spaces.
        problems.append("the raw letter carries a newline, which no span survives")
    return problems


def test_the_missing_transition_has_a_source() -> list[str]:
    """A letter's BODY is prose carrying several values, each with its own span.

    THIS IS THE ONE THE CORPUS HAD NOWHERE. Of 708 IN/tool → OUT/tool_arg
    transitions not one starts in a `free_text` result; prose reached an
    argument only out of a document. A body with ONE span over the whole string
    would be the same gap in a new coat, so the check is on the spans, not on
    the text.
    """
    problems: list[str] = []
    backend = seeded_world()
    log = backend.call("mail_read", {"message_id": "msg-1"})
    text = json.loads(log.result_text)
    if "Клубная 85" not in str(text["body"]) or "+7 (916)" not in str(text["body"]):
        problems.append(f"the letter's body carries no values: {text['body']!r}")
    inside = {tag: log.result_text[start:end]
              for tag, (start, end) in log.result_spans.items()}
    if len(inside) < 4:
        problems.append(f"the letter tagged {inside}, expected the sender and the address "
                        f"in the header and two more inside the prose")
    body_spans = [tag for tag, (start, _end) in log.result_spans.items()
                  if start > log.result_text.index('"body"')]
    if len(body_spans) < 2:
        problems.append(f"only {body_spans} lie inside the prose; a body with one span over "
                        f"the whole string is the gap this tool exists to close")
    if "free_text" not in {one.form for one in REGISTRY_V5["mail_read"].return_forms}:
        problems.append("mail_read does not declare free_text")
    return problems


def test_tracker_answers_latin_and_renders_a_login() -> list[str]:
    """Jira's own notation, and the pair this package cannot yet separate."""
    problems: list[str] = []
    found = body("tracker_find_user", {"query": "Соколов", "max_results": 5})
    user = dict(list(found["users"])[0])                                       # type: ignore[arg-type]
    if user["displayName"] != "Sokolov Andrey":
        problems.append(f"the tracker answered {user['displayName']!r}, expected the Latin form")
    if user["emailAddress"] != "a.sokolov@corp.ru":
        problems.append(f"the tracker answered {user['emailAddress']!r}, expected lower case")
    # THE LOGIN IS RENDERED AND SCORED BY NOTHING, and that is the gap stated in
    # code rather than in prose: it is not personal data, so `result_pii` may not
    # hold it (V04/V06 would refuse). It CAN be declared — v4's `PlainValue`, off
    # this row's seed locus — and no v5 module reads `case.base.plain`, so a
    # gateway that substituted it would be invisible to this instrument.
    if not user.get("login") or not user.get("accountId"):
        problems.append("the tracker's non-personal identifiers are not even rendered")
    declared = set(REGISTRY_V5["tracker_find_user"].base.result_pii)
    if {"users[].login", "users[].accountId"} & declared:
        problems.append("a login is not personal data and must not be declared as such")
    return problems


def test_sheet_is_two_dimensional() -> list[str]:
    """The one argument in the corpus that is a MATRIX, echoed as one."""
    problems: list[str] = []
    backend = seeded_world()
    log = backend.call("sheet_append_row", {
        "spreadsheet_id": "sh-1", "range": "Лист1!A1:B1",
        "values": [["Громова Марина", PHONE], ["Букин Сергей", "+79261234567"]]})
    rows = json.loads(log.result_text)["updated"]["values"]
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        problems.append(f"the sheet echoed {rows!r}, which is not a matrix")
    elif [len(row) for row in rows] != [2, 2]:
        problems.append(f"the sheet echoed rows of {[len(row) for row in rows]}")
    # ONE CELL IS ONE WHOLE VALUE, and the argument leaf therefore declares no
    # role: `spec_v5_for` erases every index, so all cells share one FieldSpec
    # and a role on it would claim every column holds a surname.
    leaf = v5tools.spec_v5_for("sheet_append_row", "values[1][0]")
    if leaf is None or leaf.path != "values[][]":
        problems.append(f"a cell resolves to {leaf!r}, expected the values[][] leaf")
    elif leaf.role:
        problems.append(f"the cell leaf claims the role {leaf.role!r}")
    return problems


def test_card_carries_a_contact_and_a_deal() -> list[str]:
    """Two different objects in ONE call — the shape nothing in v4 had."""
    problems: list[str] = []
    card = dict(body("crm_upsert_card", {
        "contact": {"last_name": "Громова", "first_name": "Марина", "phone": PHONE,
                    "address": {"city": "Ижевск", "street": "Клубная", "house": "85"}},
        "deal": {"title": "Доставка", "stage": "new", "contact_name": "Громова Марина"}})["card"])
    if "contact" not in card or "deal" not in card:
        problems.append(f"the card came back as {sorted(card)}, expected both objects")
        return problems
    # THE SAME PERSON IS NAMED TWICE IN ONE ARGUMENT — as the contact's parts and
    # as the deal's whole name — which is what makes «one identity, two
    # substitutes inside one call» visible at all.
    if not str(dict(card["deal"]).get("contact_name")):
        problems.append("the deal does not name the person the contact names")
    if str(dict(card["contact"]).get("address")) != "г Ижевск, ул Клубная, д 85":
        problems.append(f"the card printed the address as "
                        f"{dict(card['contact']).get('address')!r}, expected the canon line")
    return problems


def test_doc_append_is_read_back() -> list[str]:
    """Write prose into a document, then read the document: one chain, two
    tools, and the store they share is the one `doc_retrieve` already read."""
    problems: list[str] = []
    backend = seeded_world()
    backend.call("doc_append", {"document_id": "doc-1", "text": "12.09 просила пятницу."})
    again = json.loads(backend.call("doc_retrieve", {"doc_id": "doc-1"}).result_text)
    if "12.09 просила пятницу." not in str(again["body"]):
        problems.append(f"the appended paragraph is not in the document: {again['body']!r}")
    if "Громова Марина" not in str(again["body"]):
        problems.append("the document lost its seeded prose when it was appended to")
    return problems


CHECKS = (test_no_pseudex, test_counts, test_v4_kept, test_v4_tools_revised,
          test_v4_registry_is_widened,
          test_every_tool_has_form, test_vertical_rules, test_parsers_good_bad,
          test_examples_resolve, test_directory_canon, test_clinic_iso_snils,
          test_clinic_reads_a_card_back, test_bank_forms,
          test_ticket_history_free_text, test_calendar_notations, test_government_forms,
          test_kb_search_chunks, test_file_forms, test_courier_status_forms,
          test_nested_address, test_file_read_scan_noise, test_empty_world_is_empty,
          test_mail_notations, test_the_missing_transition_has_a_source,
          test_tracker_answers_latin_and_renders_a_login, test_sheet_is_two_dimensional,
          test_card_carries_a_contact_and_a_deal, test_doc_append_is_read_back)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_tools: PASS" if not failures else f"test_tools: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
