"""The v5 mock backend under test: forms, item-id tags, forced errors, seeding.

EVERY CHECK HERE IS SHOWN A WRONG INPUT AS WELL AS A RIGHT ONE. A shape
comparison that only ever sees matching shapes proves nothing about the shapes
— `test_shape_check_can_fail` hands it a doctored example and demands a red.

This module also owns the SEEDED WORLD the tool tests read: one backend with a
row in every table, so `test_each_form_renders` can produce all 66 declared
(tool, form) pairs and `test_tools` can assert the exact notations §2 of the
ТЗ names. It is not a fixture file because a benchmark's fixtures are data, and
this one is a state machine: the record a lookup returns is the record an
upsert wrote.
"""
import json
from dataclasses import replace
import random
import sys

from bench.agentpii4 import pools
from bench.agentpii4.schema import (Case, Expectation, Locus, Message, PiiItem, Provenance,
                                    SeedRecord)
from bench.agentpii4.tools import CSV_HEADER
from bench.agentpii5.contracts import (ECHO_TAG_PREFIX, CaseV5, ForcedError, Hop,
                                       ReturnExpectation)
from bench.agentpii5.scenarios5 import rag, retry_same_tool, user_in_loop
from bench.agentpii5.mock import (BackendV5, render_problems, seed_backend_v5,
                                  snils_spaced)
from bench.agentpii5.tools import ISSUE_ID_RE, REGISTRY_V5, generic_paths

NOW = "2026-09-02"
# The build seed every generator in this package is driven at.
SEED: int = 4
PHONE = "+79164021187"
PHONE_DOCTOR = "+79161112233"
PHONE_OPERATOR = "+79161112244"
PHONE_SHARED = "+79031234567"
PHONE_UNKNOWN = "+79991112233"
EMAIL = "grom@mail.ru"
# Checksum-valid by CONSTRUCTION, from v4's own generators on a fixed seed: a
# hand-typed СНИЛС or ИНН that failed mod-101 would be refused by the parser
# and the test would be measuring the wrong thing.
STREAM = random.Random(20260922)
CARD = pools.card_digits(STREAM)
CARD_SHARED = pools.card_digits(STREAM)
SNILS_VALID = pools.snils_digits(STREAM)
SNILS_REVOKED = pools.snils_digits(STREAM)
SNILS_UNSEEDED = pools.snils_digits(STREAM)
INN_ACTIVE = pools.inn12_digits(STREAM)
INN_BLOCKED = pools.inn12_digits(STREAM)
INN_UNSEEDED = pools.inn12_digits(STREAM)
FORM_TEXT = ("Анкета: Кузнецова Ангелина Тарасовна, дата рождения 1990-07-02, "
             "паспорт 9204 551133, СНИЛС, адрес Воронеж, Кольцовская 18, квартира 44")


def seeded_world() -> BackendV5:
    """One customer's systems, with a row in every table the 43 tools read."""
    backend = BackendV5(NOW, (), {})
    backend.seed_contact("c-77", {
        "last_name": "громова", "first_name": "марина", "middle_name": "борисовна",
        "phone": PHONE, "email": EMAIL, "birth_date": "1987-03-14",
        "address": {"city": "ижевск", "street": "клубная", "house": "85", "flat": "12"}})
    # THE DUPLICATE CARD CARRIES AN ADDRESS TOO: a contact whose `address` is
    # an empty object renders as one, and a list whose rows have different
    # SHAPES would make the declared example unmatchable for any seeding.
    backend.seed_contact("c-78", {
        "last_name": "громова", "first_name": "марина", "middle_name": "",
        "phone": PHONE, "email": "", "birth_date": "",
        "address": {"city": "ижевск", "street": "клубная", "house": "85", "flat": ""}})
    backend.seed_contact("c-doc", {"last_name": "соколов", "first_name": "андрей",
                                   "role": "doctor", "phone": PHONE_DOCTOR})
    backend.seed_contact("c-op", {"last_name": "титова", "first_name": "ольга",
                                  "role": "operator", "phone": PHONE_OPERATOR})
    backend.seed_address("a-1", {"value": "г Ижевск, ул Пушкина, д 41, кв 7",
                                 "postal_code": "426034", "region": "Удмуртская Респ",
                                 "city": "ижевск", "street": "пушкина", "house": "41",
                                 "flat": "7", "fias_id": "a1"})
    backend.seed_address("a-2", {"value": "г Ижевск, ул Пушкина, д 41",
                                 "postal_code": "426034", "region": "Удмуртская Респ",
                                 "city": "ижевск", "street": "пушкина", "house": "41",
                                 "flat": "", "fias_id": "a2"})
    order = {"recipient": {"name": "Громова Марина", "phones": [PHONE]},
             "to_location": {"postal_code": "426034", "city": "ижевск",
                             "address": "ул. Клубная, 85, кв. 12"},
             "status": "ACCEPTED", "date": "2026-09-05"}
    for order_id in ("ord-1", "ord-2", "ord-3"):
        backend.seed_record("orders", order_id, dict(order))
    claim = {"address": {"locality": "ижевск", "street": "пушкина", "building": "41",
                         "porch": "", "sflat": "7"},
             "contact": {"name": "Громова Марина", "phone": PHONE}}
    backend.seed_record("claims", "clm-1", {**claim, "status": "delivering"})
    backend.seed_record("claims", "clm-2", {**claim, "status": "failed"})
    appointment = {"patient": {"last_name": "павлова", "first_name": "тамара"},
                   "status": "BOOKED", "slot": "2026-09-05T09:30:00+04:00"}
    backend.seed_record("appointments", "apt-1", dict(appointment))
    backend.seed_record("appointments", "apt-2", dict(appointment))
    payment = {"amount": {"value": "1500.00", "currency": "RUB"}, "status": "pending",
               "receipt": {"customer": {"full_name": "Павлова Тамара", "phone": PHONE}}}
    backend.seed_record("payments", "pay-1", dict(payment))
    backend.seed_record("payments", "pay-2", dict(payment))
    # A RECEIPT WITH AN E-MAIL IS ITS OWN PAYMENT: `receipt_fetch` declares
    # `customer.email` and `payment_status` does not, and one payment carrying
    # both would make one of the two declared shapes unreachable.
    backend.seed_record("payments", "pay-3", {
        "amount": {"value": "1500.00", "currency": "RUB"}, "status": "succeeded",
        "receipt": {"customer": {"full_name": "Павлова Тамара", "phone": PHONE,
                                 "email": "pav@mail.ru"}}})
    backend.seed_record("tickets", "tkt-1", {"phone": PHONE, "subject": "Перенос доставки"})
    backend.seed_bank_client("bc-1", {
        "name": "Громова Марина Борисовна", "inn": INN_ACTIVE, "card": CARD,
        "phone": PHONE, "status": "active",
        "rows": [{"date": "2026-08-03", "amount": "1500.00", "currency": "RUB",
                  "description": "Оплата заказа"},
                 {"date": "2026-08-11", "amount": "420.00", "currency": "RUB",
                  "description": "Доставка"}]})
    backend.seed_bank_client("bc-2", {"name": "Букин Сергей", "inn": INN_BLOCKED,
                                      "card": CARD_SHARED, "status": "blocked"})
    backend.seed_bank_client("bc-3", {"name": "Лапина Вера", "inn": pools.inn12_digits(STREAM),
                                      "card": CARD_SHARED, "phone": PHONE_SHARED,
                                      "status": "active"})
    backend.seed_bank_client("bc-4", {"name": "Лапин Пётр", "inn": pools.inn12_digits(STREAM),
                                      "card": CARD_SHARED, "phone": PHONE_SHARED,
                                      "status": "active"})
    backend.seed_vehicle("veh-1", {"plate": "Х501УН36", "model": "Lada Vesta", "year": "2019",
                                   "owner": {"last_name": "Громова", "first_name": "Марина"}})
    backend.seed_vehicle("veh-2", {"plate": "А123ВС77", "model": "Kia Rio", "year": "2016",
                                   "registrations": [
                                       {"from": "2016-04-01", "to": "2023-02-15",
                                        "owner": {"last_name": "Громова", "first_name": "Марина"}},
                                       {"from": "2023-02-16", "to": "",
                                        "owner": {"last_name": "Букин", "first_name": "Сергей"}}]})
    backend.seed_snils("sn-1", {"snils": SNILS_VALID, "last_name": "Громова",
                                "first_name": "Марина", "birth_date": "1987-03-14",
                                "status": "valid"})
    backend.seed_snils("sn-2", {"snils": SNILS_REVOKED, "last_name": "Букин",
                                "first_name": "Сергей", "birth_date": "1979-11-02",
                                "status": "revoked"})
    backend.seed_calendar("cal-1", {"person": "Громова Марина", "birth_date": "1987-03-14"})
    # The МИС card, in the three notations §2 asks the clinic for. The СНИЛС is
    # stored SEPARATED because that is how a clinic prints it, and the lookup is
    # by digit signature — a card stored in the bare digits the parser hands over
    # would let a string comparison pass and say nothing about the notation.
    backend.seed_patient("pat-1", {"last_name": "Громова", "first_name": "Марина",
                                   "birth_date": "1987-03-14",
                                   "snils": snils_spaced(SNILS_VALID), "phone": PHONE,
                                   "policy": "ОМС pat-1"})
    backend.seed_ticket_event("ev-1", {
        "issue_id": "t-1", "order": 1, "name": "Громова Марина", "phone": PHONE,
        "template": "12.09 клиент {name} ({phone}) просил перенести доставку на пятницу."})
    backend.seed_ticket_event("ev-2", {
        "issue_id": "t-1", "order": 2, "name": "Громова Марина",
        "template": "13.09 перезвонили, {name} подтвердила пятницу."})
    backend.seed_chunk("kb-1", {"identity": "grom", "name": "Громова Марина", "phone": PHONE,
                                "template": "Клиент {name}, телефон {phone}, просила перезвонить."})
    backend.seed_chunk("kb-2", {"identity": "bukin", "name": "Букин Сергей",
                                "template": "Сосед {name} оставил заявку на вывоз."})
    backend.seed_chunk("kb-3", {"identity": "lapina", "name": "Лапина Вера",
                                "phone": PHONE_SHARED,
                                "address": "г Самара, ул Луговая, д 10"})
    backend.seed_document("doc-1", {"path": "/mnt/in/anketa.txt", "format": "txt",
                                    "title": "Анкета клиента", "name": "Громова Марина",
                                    "phone": PHONE,
                                    "template": "Заявитель {name}, телефон {phone}."})
    backend.seed_document("doc-2", {
        "path": "/mnt/in/clients.csv", "format": "csv", "title": "Импорт",
        # The rows are keyed by the ordinal, never a list: v4's seed validator
        # walks «.» alone and a path through a list resolves to None
        # (`tools.csv_row_path`).
        "rows": {"0": {"last_name": "Громова", "first_name": "Марина", "phone": PHONE,
                       "email": EMAIL, "birth_date": "1987-03-14"},
                 "1": {"last_name": "Букин", "first_name": "Сергей", "phone": "+79261234567",
                       "email": "bukin@mail.ru", "birth_date": "1979-11-02"}}})
    backend.seed_document("doc-3", {"path": "/mnt/in/scan.txt", "format": "scan",
                                    "title": "Скан договора", "name": "Громова Марина",
                                    "phone": PHONE,
                                    "template": "Сторона по договору {name}, телефон {phone}, "
                                                "просила подтвердить адрес доставки."})
    backend.seed_document("doc-4", {
        "path": "/mnt/in/form.docx", "format": "form", "title": "Анкета Кузнецовой",
        "last_name": "Кузнецова", "first_name": "Ангелина", "middle_name": "Тарасовна",
        "birth_date": "1990-07-02", "passport_series": "9204", "passport_number": "551133",
        "snils": SNILS_VALID, "city": "Воронеж", "street": "Кольцовская", "house": "18",
        "flat": "44"})
    backend.seed_record("emails", "blocked@mail.ru", {"status": "rejected"})
    # ONE DATUM IN TWO PLACES KEEPS ONE ID: the client's phone sits in the CRM
    # card and inside the ticket history, and binding both to `i_phone` is what
    # tells the by-value index it is not ambiguous.
    backend.seed_item("contacts", "c-77", "phone", "i_phone")
    backend.seed_item("contacts", "c-77", "last_name", "i_last")
    backend.seed_item("ticket_events", "ev-1", "phone", "i_phone")
    backend.seed_item("ticket_events", "ev-1", "name", "i_ev_name")
    backend.seed_item("kb_chunks", "kb-1", "name", "i_kb_name")
    backend.seed_item("documents", "doc-3", "name", "i_scan_name")
    backend.seed_item("documents", "doc-4", "last_name", "i_form_last")
    return backend


def bare_world() -> BackendV5:
    """Nothing seeded. v4's `address_suggest` and `pickup_points_near` rank
    whatever the directory holds and never filter by score, so their `empty`
    form is reachable only where the directory itself is empty."""
    return BackendV5(NOW, (), {})


# The scripted refusals `retry_same_tool` puts in front of the four tools it
# retries, with the same codes and message templates that family uses. THIS IS A
# RESULT AND NOT A PARSE ERROR: `mock._forced_call` answers a body the model
# reads, with the offending value tagged inside `error.message`, and 126 IN/tool
# hops of the corpus cross that leaf. Until it was rendered here, the four tools
# declared `error.subject` — the DOMAIN error's body, a different shape — and
# the column «ПД в результате» described the wrong one for every one of them.
SCRIPTED: tuple[ForcedError, ...] = (
    ForcedError("bank_client_find", 0, "invalid_request", "e-inn",
                "invalid_request: параметр inn «{value}» не прошёл проверку."),
    ForcedError("vehicle_check", 0, "plate_format", "e-plate",
                "номер {value} не найден в формате ГОСТ Р 50577."),
    ForcedError("snils_verify", 0, "snils_checksum", "e-snils",
                "СНИЛС {value} не прошёл проверку контрольной суммы ПФР."),
    ForcedError("calendar_free", 0, "employee_unknown", "e-person",
                "сотрудник {value} не найден в расписании."),
)


def scripted_world() -> BackendV5:
    """A world whose FIRST call of each of the four tools is refused the way
    `retry_same_tool` scripts it. Nothing is seeded: `_forced_call` answers
    before the arguments are parsed and before any table is read, so a seeded
    row here would be a row this fixture proves nothing about."""
    return BackendV5(NOW, SCRIPTED, {
        "e-inn": INN_ACTIVE, "e-plate": "Х501УН36",
        "e-snils": snils_spaced(SNILS_VALID), "e-person": "Громова Марина"})


# (tool, declared form, arguments, world). The order matters: the world is a
# state machine, and `crm_merge_contacts` deletes the duplicate it merges.
RENDERS: tuple[tuple[str, str, dict[str, object], str], ...] = (
    ("delivery_create_order", "single",
     {"recipient": {"name": "Громова Марина", "phones": [{"number": PHONE}]},
      "to_location": {"postal_code": "426034", "city": "Ижевск",
                      "address": "ул. Клубная, 85, кв. 12"},
      "packages": [{"weight": 1200}]}, "full"),
    ("courier_book", "nested",
     {"address": {"locality": "Ижевск", "street": "Пушкина", "building": "41", "sflat": "7"},
      "contact": {"name": "Громова Марина", "phone": PHONE},
      "interval": {"from": "2026-09-03T10:00:00+04:00", "to": "2026-09-03T14:00:00+04:00"}},
     "full"),
    ("courier_status", "nested", {"claim_id": "clm-1"}, "full"),
    ("courier_status", "error_with_value", {"claim_id": "clm-2"}, "full"),
    ("order_status", "single", {"order_id": "ord-1"}, "full"),
    ("order_status", "error_with_value", {"order_id": "ord-9"}, "full"),
    ("order_cancel", "single", {"order_id": "ord-2"}, "full"),
    ("order_reschedule", "single", {"order_id": "ord-3", "date": "2026-09-07"}, "full"),
    ("delivery_quote", "single", {"weight": 1200, "city": "Ижевск"}, "full"),
    ("pickup_points_near", "list", {"address": "Пушкина 41", "limit": 1}, "full"),
    ("pickup_points_near", "empty", {"address": "Пушкина 41", "limit": 1}, "bare"),
    ("address_suggest", "canon", {"query": "Пушкина 41 кв 7", "count": 1}, "full"),
    ("address_suggest", "list", {"query": "Пушкина 41", "count": 2}, "full"),
    ("address_suggest", "empty", {"query": "Пушкина 41", "count": 2}, "bare"),
    ("normalize_contact", "canon",
     {"name": "громова марина борисовна", "phone": "89164021187", "address": "пушкина 41"},
     "full"),
    ("clinic_book", "single",
     {"patient": {"last_name": "Павлова", "first_name": "Тамара", "birth_date": "1987-03-14",
                  "age": 39, "gender": "F"},
      "phone": PHONE, "speciality": "кардиолог", "slot": "2026-09-05T09:30:00+04:00"}, "full"),
    ("clinic_slots", "list", {"speciality": "кардиолог", "date": "2026-09-05"}, "full"),
    ("appointment_cancel", "single", {"appointment_id": "apt-1"}, "full"),
    ("appointment_cancel", "error_with_value", {"appointment_id": "apt-9"}, "full"),
    ("appointment_reschedule", "single",
     {"appointment_id": "apt-2", "slot": "2026-09-06T11:00:00+04:00"}, "full"),
    ("referral_create", "single",
     {"patient": {"last_name": "Павлова", "first_name": "Тамара", "birth_date": "1987-03-14"},
      "speciality": "невролог"}, "full"),
    ("payment_create", "single",
     {"amount": {"value": "1500.00", "currency": "RUB"},
      "payment_method_data": {"type": "bank_card",
                              "card": {"number": CARD, "expiry_month": "09",
                                       "expiry_year": "2028", "cardholder": "TAMARA PAVLOVA"}},
      "receipt": {"customer": {"full_name": "Павлова Тамара", "phone": PHONE}}}, "full"),
    ("payment_status", "single", {"payment_id": "pay-1"}, "full"),
    ("payment_status", "error_with_value", {"payment_id": "pay-9"}, "full"),
    ("payment_refund", "single",
     {"payment_id": "pay-2", "amount": {"value": "1500.00", "currency": "RUB"}}, "full"),
    ("receipt_fetch", "single", {"payment_id": "pay-3"}, "full"),
    ("bank_client_find", "single", {"inn": INN_ACTIVE}, "full"),
    ("bank_client_find", "list", {"phone": PHONE_SHARED}, "full"),
    ("bank_client_find", "empty", {"inn": INN_UNSEEDED}, "full"),
    ("bank_client_find", "error_with_value", {"inn": INN_BLOCKED}, "full"),
    ("account_statement", "list",
     {"client_id": "bc-1", "from": "2026-08-01", "to": "2026-08-31"}, "full"),
    ("account_statement", "empty", {"client_id": "bc-2"}, "full"),
    ("ticket_create", "single",
     {"subject": "Перенос доставки", "text": "Клиент просит перенести на пятницу",
      "phone": PHONE}, "full"),
    ("ticket_find", "list", {"phone": PHONE}, "full"),
    ("ticket_find", "empty", {"phone": PHONE_UNKNOWN}, "full"),
    ("ticket_history", "free_text", {"issue_id": "t-1"}, "full"),
    ("ticket_history", "empty", {"issue_id": "t-9"}, "full"),
    ("escalate_to_human", "single",
     {"summary": "Клиент просит перенести доставку", "queue": "general"}, "full"),
    ("callback_schedule", "single",
     {"phone": PHONE, "at": "2026-09-03T18:00:00+04:00", "timezone": "Europe/Samara"}, "full"),
    ("calendar_free", "list", {"person": "Громова Марина", "date": "2026-09-10"}, "full"),
    ("calendar_free", "empty", {"person": "Букин Сергей", "date": "2026-09-10"}, "full"),
    ("notify_sms", "single", {"number": PHONE, "text": "Заказ принят"}, "full"),
    ("send_template", "list",
     {"template_id": "callback", "number": PHONE,
      "variables": {"name": "Марина", "phone": PHONE, "when": "завтра"}}, "full"),
    ("email_send", "single", {"to": EMAIL, "subject": "Заказ", "body": "Здравствуйте!"}, "full"),
    ("email_send", "error_with_value",
     {"to": "blocked@mail.ru", "subject": "Заказ", "body": "Здравствуйте!"}, "full"),
    ("passport_verify", "single",
     {"passport": {"series": "4509", "number": "123456"}, "snils": snils_spaced(SNILS_VALID),
      "person": {"last_name": "Иванов", "first_name": "Пётр"}}, "full"),
    ("vehicle_check", "single", {"plate": "Х501УН36"}, "full"),
    ("vehicle_check", "list", {"plate": "А123ВС77"}, "full"),
    ("vehicle_check", "error_with_value", {"plate": "Е777КХ99"}, "full"),
    ("snils_verify", "single", {"snils": snils_spaced(SNILS_VALID)}, "full"),
    ("snils_verify", "empty", {"snils": snils_spaced(SNILS_UNSEEDED)}, "full"),
    # The four scripted refusals, in their own world so the retry's first
    # attempt is a refusal and its second is not.
    ("bank_client_find", "error_with_value", {"inn": INN_ACTIVE}, "scripted"),
    ("vehicle_check", "error_with_value", {"plate": "Х501УН36"}, "scripted"),
    ("snils_verify", "error_with_value", {"snils": snils_spaced(SNILS_VALID)}, "scripted"),
    ("calendar_free", "error_with_value",
     {"person": "Громова Марина", "date": "2026-09-10"}, "scripted"),
    ("patient_find", "single", {"phone": PHONE}, "full"),
    ("patient_find", "single", {"snils": snils_spaced(SNILS_VALID)}, "full"),
    ("patient_find", "empty", {"phone": PHONE_UNKNOWN}, "full"),
    ("snils_verify", "error_with_value", {"snils": snils_spaced(SNILS_REVOKED)}, "full"),
    ("kb_search", "chunks", {"query": "Громова Марина", "k": 3}, "full"),
    ("kb_search", "list", {"query": "Лапина Вера", "k": 3}, "full"),
    ("kb_search", "empty", {"query": "щщщ ыыы ююю", "k": 3}, "full"),
    ("doc_retrieve", "free_text", {"doc_id": "doc-1"}, "full"),
    ("doc_retrieve", "empty", {"doc_id": "doc-9"}, "full"),
    ("file_read", "free_text", {"path": "/mnt/in/anketa.txt"}, "full"),
    ("file_read", "list", {"path": "/mnt/in/clients.csv"}, "full"),
    ("file_read", "empty", {"path": "/mnt/in/none.txt"}, "full"),
    ("form_parse", "nested", {"text": FORM_TEXT}, "full"),
    ("form_parse", "error_with_value", {"text": "щщщ ыыы ююю"}, "full"),
    ("crm_find_contact", "list", {"query": {"phone": PHONE}}, "full"),
    ("crm_find_contact", "empty", {"query": {"phone": PHONE_UNKNOWN}}, "full"),
    ("crm_upsert_contact", "single",
     {"id": "c-77", "contact": {"address": {"city": "Ижевск", "street": "Пушкина",
                                            "house": "41", "flat": "7"}}}, "full"),
    ("crm_add_note", "single",
     {"entity_id": "c-77", "note_type": "call_in",
      "text": "Клиент просит перенести доставку на пятницу."}, "full"),
    ("crm_segment_report", "list",
     {"group_by": "city", "members": [{"name": "Громова Марина", "bucket": "Ижевск"}]}, "full"),
    ("crm_import_csv", "list",
     {"csv": f"{CSV_HEADER}\nГромова;Марина;{PHONE};{EMAIL};1987-03-14\n"
             f"Букин;Сергей;+79261234567;bukin@mail.ru;"}, "full"),
    ("crm_merge_contacts", "single", {"primary_id": "c-77", "duplicate_id": "c-78"}, "full"),
    ("crm_merge_contacts", "error_with_value",
     {"primary_id": "c-77", "duplicate_id": "c-99"}, "full"),
)


def hand_case() -> CaseV5:
    """One case built by hand: two seeded data of one identity, one forced
    error on the first call of `crm_find_contact`."""
    locus_phone = Locus("seed", -1, 0, 0, "c-1", "phone")
    locus_name = Locus("seed", -1, 0, 0, "c-1", "last_name")
    items = (
        PiiItem("p1", "PHONE", "grom", "восемь девятьсот шестнадцать…", PHONE, {}, locus_phone,
                "required", True, False),
        PiiItem("n1", "NAME", "grom", "Громовой", "Громова", {"surname": "Громова"}, locus_name,
                "required", False, False))
    seeds = (SeedRecord("c-1", "contacts", {"last_name": "Громова", "first_name": "Марина",
                                            "phone": PHONE, "email": "", "birth_date": "",
                                            "address": {}}, ("p1", "n1")),)
    base = Case(
        id="v5-hand-1", kind="lookup_list", register="chat",
        provenance=Provenance("synthetic", "hand", "test_mock", "case", "fixed", 1.0, "none"),
        cluster="PHONE:+79164021187", conversation_id="conv-1", now=NOW,
        messages=(Message("system", "Ты оператор.", None, ""),
                  Message("user", "Найди меня по телефону.", None, "")),
        tools=("crm_find_contact",), seed_records=seeds, pii=items, plain=(), negatives=(),
        expects=Expectation(("crm_find_contact",), "grom", (), (), ()), trace=(), note="")
    forced = (ForcedError("crm_find_contact", 0, "PHONE_NOT_INDEXED",
                          "p1", "номер {value} ещё не проиндексирован"),)
    hops = (Hop("IN", "user", "p1", 0, 1, "", -1, "", -1, "", False),
            Hop("OUT", "tool_arg", "p1", 1, 1, "crm_find_contact", 0, "", 0, "query.phone", False),
            Hop("IN", "tool", "n1", 2, 1, "crm_find_contact", 1, "", -1,
                "contacts[].last_name", False),
            Hop("OUT", "answer", "n1", 3, 1, "", -1, "", 2, "", False))
    return CaseV5(base=base, behaviour="retry_same_tool", hops=hops,
                  returns=(ReturnExpectation("crm_find_contact", 1, "list", ("p1", "n1")),),
                  forced=forced, memory=(), pick=None, branch=None, loop=None, rag=None,
                  document=None, has_result=True, streaming=False, revised_from_v4=False)


def test_no_pseudex() -> list[str]:
    leaked = [name for name in sys.modules if name.split(".")[0] == "pseudex"]
    return [f"the mock pulled in {leaked}"] if leaked else []


def test_forced_error() -> list[str]:
    problems: list[str] = []
    backend = seed_backend_v5(hand_case())
    first = backend.call("crm_find_contact", {"query": {"phone": PHONE}})
    if backend.form_of(first.seq) != "error_with_value":
        problems.append(f"forced call came back as {backend.form_of(first.seq)!r}")
    if first.refusal is not None or first.parsed is not None:
        problems.append("a forced error is not a parse refusal and carries no parsed arguments")
    tag = ECHO_TAG_PREFIX + "p1"
    if tag not in first.result_spans:
        problems.append(f"no echoed span {tag!r} in {sorted(first.result_spans)}")
    second = backend.call("crm_find_contact", {"query": {"phone": PHONE}})
    if second.parsed is None or backend.form_of(second.seq) != "list":
        problems.append(f"the second attempt did not parse normally: "
                        f"{second.refusal} / {backend.form_of(second.seq)}")
    if [backend.form_of(log.seq) for log in backend.calls] != ["error_with_value", "list"]:
        problems.append("form_of did not report both calls")
    # THE NEGATIVE: an error scripted for the SECOND call must leave the first
    # alone, or «ordinal» would mean nothing.
    late = BackendV5(NOW, (ForcedError("ticket_find", 1, "X", "p1", "{value}"),), {"p1": PHONE})
    late.seed_record("tickets", "tkt-1", {"phone": PHONE, "subject": "x"})
    if late.form_of(late.call("ticket_find", {"phone": PHONE}).seq) == "error_with_value":
        problems.append("an error scripted for ordinal 1 fired on ordinal 0")
    if late.form_of(late.call("ticket_find", {"phone": PHONE}).seq) != "error_with_value":
        problems.append("an error scripted for ordinal 1 did not fire on ordinal 1")
    return problems


def test_error_echoes_value() -> list[str]:
    problems: list[str] = []
    backend = seed_backend_v5(hand_case())
    log = backend.call("crm_find_contact", {"query": {"phone": PHONE}})
    start, end = log.result_spans[ECHO_TAG_PREFIX + "p1"]
    if log.result_text[start:end] != PHONE:
        problems.append(f"echoed {log.result_text[start:end]!r}, expected {PHONE!r}")
    if PHONE not in str(json.loads(log.result_text)["error"]["message"]):
        problems.append("the real value is not inside the error message the model reads")
    # THE NEGATIVE: a template with no slot, or an item with no echo value, is
    # a scripted error nobody can read — both must raise rather than pass.
    for forced, echo, why in (
            (ForcedError("ticket_find", 0, "X", "p1", "нет значения"), {"p1": PHONE},
             "a template without {value}"),
            (ForcedError("ticket_find", 0, "X", "p9", "{value}"), {"p1": PHONE},
             "an item with no echo value")):
        broken = BackendV5(NOW, (forced,), echo)
        try:
            broken.call("ticket_find", {"phone": PHONE})
            problems.append(f"{why} was accepted")
        except (ValueError, KeyError):
            pass
    return problems


def test_slot_tags_are_item_ids() -> list[str]:
    problems: list[str] = []
    backend = seed_backend_v5(hand_case())
    backend.call("crm_find_contact", {"query": {"phone": PHONE}})       # the forced error
    log = backend.call("crm_find_contact", {"query": {"phone": PHONE}})
    if set(log.result_spans) != {"p1", "n1"}:
        problems.append(f"tags are {sorted(log.result_spans)}, expected the seed items p1, n1")
    for item, expected in (("p1", PHONE), ("n1", "Громова")):
        if item not in log.result_spans:
            continue
        start, end = log.result_spans[item]
        if log.result_text[start:end] != expected:
            problems.append(f"{item} spans {log.result_text[start:end]!r}, not {expected!r}")
    # THE NEGATIVE, WHERE BY-VALUE IS STILL THE ONLY RULE. `notify_sms` echoes
    # the number the AGENT sent and the mock holds no record for it, so the tag
    # can only come from `_by_value` — and a value two items claim would put the
    # hop on the wrong person, so no tag is the honest answer there.
    ambiguous = BackendV5(NOW, (), {})
    ambiguous.seed_contact("c-1", {"last_name": "громова", "first_name": "марина",
                                   "phone": PHONE, "email": "", "birth_date": "", "address": {}})
    ambiguous.seed_chunk("kb-1", {"name": "Громова Марина", "phone": PHONE,
                                  "template": "Клиент {name}, телефон {phone}."})
    ambiguous.seed_item("contacts", "c-1", "phone", "a1")
    ambiguous.seed_item("kb_chunks", "kb-1", "phone", "a2")
    echoed = ambiguous.call("notify_sms", {"number": PHONE, "text": "перезвоните"})
    if "a1" in echoed.result_spans or "a2" in echoed.result_spans:
        problems.append("an ambiguous value was tagged by value anyway")
    # …AND THE POSITIVE THE OLD NEGATIVE WAS HIDING. `crm_find_contact` answers
    # out of the record it found, so the (table, id, path) map knows the span is
    # `contacts/c-1.phone` and no ambiguity exists: refusing to tag it cost 45
    # revised cases their whole tool result, every one of them a support case
    # that seeds one person twice.
    found = ambiguous.call("crm_find_contact", {"query": {"phone": PHONE}})
    if "a1" not in found.result_spans:
        problems.append(f"the record's own phone was left untagged: "
                        f"{sorted(found.result_spans)}")
    if "a2" in found.result_spans:
        problems.append("the CRM card was tagged with the knowledge base's item")
    return problems


def test_ids_by_writes_only() -> list[str]:
    backend = seeded_world()
    backend.call("crm_find_contact", {"query": {"phone": PHONE}})
    backend.call("crm_find_contact", {"query": {"phone": PHONE}})
    backend.call("crm_upsert_contact", {"id": "c-77", "contact": {
        "address": {"city": "Ижевск", "street": "Пушкина", "house": "41", "flat": "7"}}})
    written = [row["id"] for row in backend.snapshot()]
    return [] if written == ["c-77"] else [f"writes allocated {written}, expected ['c-77']"]


def test_snapshot_typed() -> list[str]:
    problems: list[str] = []
    backend = seeded_world()
    if backend.snapshot():
        problems.append(f"seeds reached the snapshot: {backend.snapshot()}")
    backend.call("notify_sms", {"number": PHONE, "text": "Заказ принят"})
    rows = backend.snapshot()
    if [row["tool"] for row in rows] != ["notify_sms"]:
        problems.append(f"snapshot after one write is {rows}")
    if rows and rows[0]["fields"] != {"number": PHONE, "text": "Заказ принят",
                                      "sign": "SMS Aero"}:
        problems.append(f"the snapshot is not the PARSED record: {rows[0]['fields']}")
    return problems


def render(world: str, tool: str, arguments: dict[str, object]) -> tuple[BackendV5, object]:
    backend = WORLDS[world]
    return backend, backend.call(tool, arguments)


WORLDS: dict[str, BackendV5] = {}


def test_each_form_renders() -> list[str]:
    problems: list[str] = []
    WORLDS["full"], WORLDS["bare"] = seeded_world(), bare_world()
    WORLDS["scripted"] = scripted_world()
    seen: set[tuple[str, str]] = set()
    for tool, form, arguments, world in RENDERS:
        backend, log = render(world, tool, arguments)
        if log.refusal is not None:
            problems.append(f"{tool}/{form}: the mock refused its own fixture: {log.refusal}")
            continue
        actual = backend.form_of(log.seq)
        if actual != form:
            problems.append(f"{tool}: expected form {form!r}, got {actual!r}")
            continue
        # A FORM NAME MAY COVER SEVERAL BODIES, and `error_with_value` covers
        # two: the DOMAIN refusal («not found», «blocked») answers under
        # `error.subject` and the SCRIPTED one of `retry_same_tool` under
        # `error.message`. Keying the declarations by name alone let the second
        # silently replace the first, and then a rendered body was compared with
        # a shape nothing renders. The rendered shape must match ONE declared
        # example, and the example it matched is what counts as covered — so
        # «declared but never rendered» still names every body one by one.
        declared = [one for one in REGISTRY_V5[tool].return_forms if one.form == form]
        if not declared:
            problems.append(f"{tool}: rendered {form!r}, which the registry does not declare")
            continue
        rendered = generic_paths(json.loads(log.result_text))
        matched = next((one for one in declared
                        if generic_paths(json.loads(one.example)) == rendered), None)
        if matched is None:
            example = generic_paths(json.loads(declared[0].example))
            problems.append(f"{tool}/{form}: shape matches none of the "
                            f"{len(declared)} declared example(s); against the first, "
                            f"only rendered {sorted(rendered - example)}, "
                            f"only declared {sorted(example - rendered)}")
            continue
        seen.add((tool, form, matched.example))
    declared_pairs = {(name, one.form, one.example) for name, spec in REGISTRY_V5.items()
                      for one in spec.return_forms}
    missing = sorted(declared_pairs - seen)
    if missing:
        problems.append(f"declared but never rendered: {missing}")
    return problems


def test_shape_check_can_fail() -> list[str]:
    """The comparison that guards every row above, shown a wrong shape."""
    backend = seeded_world()
    log = backend.call("courier_status", {"claim_id": "clm-1"})
    doctored = json.loads(log.result_text)
    doctored.pop("address")
    if generic_paths(doctored) == generic_paths(json.loads(log.result_text)):
        return ["the shape check does not see a missing field"]
    return []


def test_booked_ticket_is_readable() -> list[str]:
    """Book a ticket, then read its history by the id the booking minted.

    THE ROUND TRIP IS THE CHECK (ruling R-26). `ticket_create` and
    `ticket_history` are the same table's writer and reader, and until the
    prefix moved to «t-» the reader refused every id the writer handed out —
    invisible to every other test here, because each one called the two with
    ids of its own. The last two lines are the negative fixture: v4's «tkt-»
    is still refused, so a prefix that drifted back would make this red rather
    than merely unexercised.
    """
    problems: list[str] = []
    backend = seeded_world()
    booked = backend.call("ticket_create", {"phone": PHONE, "subject": "Перенос доставки",
                                            "text": "Клиент просит перенести доставку."})
    if booked.refusal is not None:
        return [f"ticket_create refused its own fixture: {booked.refusal}"]
    minted = str(json.loads(booked.result_text)["ticket_id"])
    if not ISSUE_ID_RE.fullmatch(minted):
        problems.append(f"ticket_create minted {minted!r}, which ticket_history cannot read")
    # The event is seeded against the id the booking produced, so the history
    # has something to answer with; asking for the id alone would pass on the
    # `empty` form and prove only that the parser let it through.
    backend.seed_ticket_event("ev-new", {
        "issue_id": minted, "order": 1, "name": "Громова Марина", "phone": PHONE,
        "template": "12.09 клиент {name} ({phone}) просил перенести доставку."})
    history = backend.call("ticket_history", {"issue_id": minted})
    if history.refusal is not None:
        problems.append(f"ticket_history refused the id ticket_create minted: {history.refusal}")
    else:
        body = json.loads(history.result_text)
        if backend.form_of(history.seq) != "free_text":
            problems.append(f"the booked ticket's history came back as "
                            f"{backend.form_of(history.seq)!r}")
        if "Громова Марина" not in str(body.get("history", "")):
            problems.append(f"the history does not carry the event: {body}")
    stale = seeded_world().call("ticket_history", {"issue_id": "tkt-1"})
    if stale.refusal is None or stale.refusal.rule != "id_format":
        problems.append(f"ticket_history accepted v4's minted prefix: {stale.refusal}")
    return problems


def test_template_slot_names_are_refused_by_name() -> list[str]:
    """A brace run that is not a slot is REFUSED, never passed through as text.

    «{who2}» (ruling R-28) is the shape that cost a family: the splitter does
    not see it, so the column it names is never rendered, and every hop and
    `ReturnExpectation` declared on it is a crossing that never happened —
    charged to the gateway. The positive half is here too: a legal slot still
    renders, so the refusal cannot be bought by refusing everything.
    """
    problems: list[str] = []
    backend = seeded_world()
    backend.seed_chunk("kb-bad", {"identity": "bad", "who2": "Громова Марина",
                                  "template": "Клиент {who2} просил перезвонить."})
    try:
        backend.call("kb_search", {"query": "Громова Марина просил перезвонить", "k": 3})
    except KeyError as error:
        if "{who2}" not in str(error) or "kb-bad" not in str(error):
            problems.append(f"the refusal names neither the slot nor the record: {error}")
    else:
        problems.append("a template naming {who2} rendered as literal text")
    good = seeded_world().call("kb_search", {"query": "Громова Марина перезвонить", "k": 3})
    if "Громова Марина" not in good.result_text:
        problems.append(f"a legal slot stopped rendering: {good.result_text}")
    return problems


def test_scan_noise_is_seeded() -> list[str]:
    problems: list[str] = []
    first = seeded_world().call("file_read", {"path": "/mnt/in/scan.txt"})
    second = seeded_world().call("file_read", {"path": "/mnt/in/scan.txt"})
    if first.result_text != second.result_text:
        problems.append("the scan noise is not deterministic for one document id")
    clean = seeded_world().call("file_read", {"path": "/mnt/in/anketa.txt"})
    body = json.loads(first.result_text)["text"]
    if not any(character in body for character in "oaec"):
        problems.append(f"a scan page carries no OCR look-alike at all: {body!r}")
    if any(character in json.loads(clean.result_text)["text"] for character in "oaec"):
        problems.append("a plain page was noised")
    return problems


# --- the build-time proof (the reviewers' reproductions, turned into checks) ---------

def test_retrieval_does_not_depend_on_the_wording() -> list[str]:
    """`kb_search` returns the case's chunks for a query that names the CUSTOMER.

    THE REPRODUCTION THIS PINS (corpus-lens/t_rag2.py): with the topic word in
    the query 0 of 350 declared chunk hops were missing, with the name alone
    257 were — so every `rag` number was a property of the model's phrasing.
    `_ranked` decided MEMBERSHIP; a top-k retriever decides order.
    """
    problems: list[str] = []
    named = seeded_world().call("kb_search", {"query": "Громова Марина", "k": 3})
    rows = json.loads(named.result_text)
    mine = [str(hit["id"]) for hit in rows["hits"]]
    if len(mine) < 2:
        problems.append(f"a query naming one person retrieved only {mine}")
    everyone = seeded_world().call("kb_search",
                                   {"query": "Громова Марина Букин Сергей", "k": 3})
    theirs = [str(hit["id"]) for hit in json.loads(everyone.result_text)["hits"]]
    if sorted(mine) != sorted(theirs):
        problems.append(f"the payload changes with the wording: {mine} vs {theirs}")
    # THE NEGATIVE: a query that names nobody in the index retrieves nothing, so
    # «everything, always» is not what was built.
    nothing = seeded_world().call("kb_search", {"query": "щщщ ыыы ююю", "k": 3})
    if json.loads(nothing.result_text)["total"] != 0:
        problems.append("a query matching no record retrieved chunks anyway")
    return problems


def _declined(query: str) -> str:
    """The same words as a Russian agent writes them after «по клиенту» — one
    dative ending per word. Not a morphology engine: the point is only that the
    surface differs from the nominative the corpus drove."""
    return " ".join(word + "у" for word in query.split())


def test_retrieval_is_by_seeded_identity() -> list[str]:
    """The index answers about a PERSON, in whatever form the query names them.

    THE REPRODUCTION THIS PINS (corpus-r2/rag_query.py, F4.5): on rag-010
    «ерохин пётр» retrieved all five declared chunks and «Ерохину Петру» — the
    dative an agent writes after «по клиенту» — retrieved nothing at all; the
    customer's own phone retrieved nothing either. The declared `chunks` form
    came back `empty`, every declared chunk hop went `absent`, and
    `toolresult_masked` counted the call anyway and scored a miss. The old pin
    could not see it: it only ever asked the exact nominative surface.
    """
    problems: list[str] = []
    asked = 0
    for case in rag.build(SEED, 20):
        # `doc_retrieve` takes a document id and not a query: the wording is
        # not a question one can ask of it, and asking it anyway would make
        # this check pass on an error body.
        if case.rag is None or case.rag.tool_name != "kb_search":
            continue
        items = {item.id: item for item in case.base.pii}
        declared = [hop.item_id for hop in case.hops
                    if hop.kind == "IN" and hop.tool_name == case.rag.tool_name]
        said = items[case.rag.query_item_ids[0]]
        phone = next((item.canonical or item.value for item in case.base.pii
                      if item.type == "PHONE" and item.where.kind == "seed"), "")
        for label, query in (("nominative", said.canonical or said.value),
                             ("declined", _declined(said.canonical or said.value)),
                             ("the customer's phone", phone)):
            if not query:
                continue
            asked += 1
            backend = seed_backend_v5(case)
            log = backend.call(case.rag.tool_name, {"query": query, "k": case.rag.k})
            tagged = {tag[len(ECHO_TAG_PREFIX):] if tag.startswith(ECHO_TAG_PREFIX) else tag
                      for tag in (log.result_spans or {})}
            missing = [one for one in declared if one not in tagged]
            if missing:
                problems.append(f"{case.base.id}: {label} query {query!r} lost "
                                f"{missing[:3]} of the declared chunk hops")
    # THE NEGATIVE: a query that names nobody the index knows still retrieves
    # nothing, so «everything, always» is not what replaced the word test.
    nothing = seeded_world().call("kb_search", {"query": "щщщ ыыы ююю", "k": 3})
    if json.loads(nothing.result_text)["total"] != 0:
        problems.append("a query naming nobody retrieved chunks anyway")
    if asked < 6:
        problems.append(f"only {asked} queries were asked: a check that exercised no "
                        f"kb_search case would pass on anything")
    return problems


def test_render_problems_refuses_a_cross_item_handover() -> list[str]:
    """V05: a declared A→B hand-over must be one a COPY of A's result can make.

    THE REPRODUCTION THIS PINS (corpus-r2/cross_item.py, F4.2): ten
    `user_in_loop` transitions fed `clinic_book.patient.first_name` from the IN
    hop that carries the SURNAME, so `chain_value` compared the restored given
    name against the rendered surname and no string could satisfy both the tool
    and the metric. V04 could not see it — the source DOES render a span for
    its own item — and `build --check` was clean.
    """
    problems: list[str] = []
    case = user_in_loop.build(SEED, 1)[0]
    if render_problems(case):
        problems.append(f"a provable case was refused: {render_problems(case)[0]}")
    given = next(hop for hop in case.hops
                 if hop.kind == "OUT" and hop.path == "patient.first_name")
    surname = next(hop for hop in case.hops
                   if hop.kind == "IN" and hop.owner == "tool"
                   and hop.path == "contacts[].last_name")
    crossed = replace(case, hops=tuple(
        replace(one, source_hop=surname.hop_index) if one is given else one
        for one in case.hops))
    if not any(problem.startswith("V05") for problem in render_problems(crossed)):
        problems.append("a leaf fed by another datum of the same person was accepted")
    return problems


def test_render_problems_refuses_an_unprovable_case() -> list[str]:
    """`render_problems` is the build-time refusal, shown failing on each of the
    three ways a declaration can be fiction.

    THE REPRODUCTION THIS PINS (corpus-lens, T1/T4): 42% of the revised half's
    IN/tool hops were crossings the mock never renders, and flipping 1 215 of
    1 594 `return_form`s to a wrong value produced zero problems from every rule
    there was.
    """
    problems: list[str] = []
    # A REAL CASE OF A REAL FAMILY, not the hand fixture above: `hand_case` is a
    # shape for the mock's own checks and does not pass `validate_v5`, so a
    # refusal of it would prove nothing about the corpus.
    case = retry_same_tool.build(SEED, 1)[0]
    if render_problems(case):
        problems.append(f"a provable case was refused: {render_problems(case)[0]}")
    phantom = replace(case, returns=(replace(case.returns[0],
                                             result_item_ids=case.returns[0].result_item_ids
                                             + ("ghost",)),))
    if not any(problem.startswith("V03") for problem in render_problems(phantom)):
        problems.append("a result item the backend never renders was accepted")
    wrong_form = replace(case, returns=(replace(case.returns[0], return_form="empty"),))
    if not any(problem.startswith("V02") for problem in render_problems(wrong_form)):
        problems.append("a return form the backend does not answer in was accepted")
    hop = next(one for one in case.hops if one.kind == "IN" and one.owner == "tool")
    unrendered = replace(case, hops=tuple(
        replace(one, item_id="n1") if one is hop else one for one in case.hops))
    if not any(problem.startswith("V04") for problem in render_problems(unrendered)):
        problems.append("an IN hop with no rendered span was accepted")
    return problems


CHECKS = (test_retrieval_does_not_depend_on_the_wording,
          test_retrieval_is_by_seeded_identity,
          test_render_problems_refuses_an_unprovable_case,
          test_render_problems_refuses_a_cross_item_handover,
          test_no_pseudex, test_forced_error, test_error_echoes_value,
          test_slot_tags_are_item_ids, test_ids_by_writes_only, test_snapshot_typed,
          test_each_form_renders, test_shape_check_can_fail,
          test_booked_ticket_is_readable, test_template_slot_names_are_refused_by_name,
          test_scan_noise_is_seeded)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_mock: PASS" if not failures else f"test_mock: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
