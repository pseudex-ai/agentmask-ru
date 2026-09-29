"""The v6 mock backend: the 47 §2.3 tools, in the v5 style, on item-id state.

WHAT THIS ADDS TO v5's `BackendV5`, and where the two agree.

The v5 mock renders a tool's result from SEEDED TABLES keyed `(table, record
id, path)`. v6 has no table inventory — the 47 specs are a registry of API
mirrors across fifteen industries, and a case seeds a handful of `PiiItem`s
rather than rows of a shared store. So the v6 state is keyed by ITEM ID and by
IDENTITY, the two keys the case already carries on every datum:

  * `_item_real[item_id]`        — the real value a tool returns (the item's
                                    `canonical`, «what a CRM stores»).
  * `_identity_type[identity]`   — `{pii_type: item_id}` for the datum(s) of
                                    one identity, so a READ tool that answers
                                    with a person's several leaves can find
                                    each one.
  * `_record_fields[record_id]`  — the seeded record's fields IN THE TOOL'S OWN
                                    NOTATION, for the READ tools whose result is
                                    the stored record (R-41 write-echo is the
                                    WRITE half; a read is the stored record).
  * `_path_item[(record_id, path)]` — the exact item binding, so a read renders
                                    the field and tags it with the item id, no
                                    by-value guess (the v5 ambiguity lesson).

The 47 tools split exactly on `base.mutating`: 14 WRITE tools echo the PARSED
arguments back (the parser already applied the tool's notation — «79164021187»
for the fiscal API, E.164 for SMS), tagged by value; 33 READ tools render the
seeded record's fields, tagged by the exact `(record id, path)` binding. A
read tool not finding its record answers the form its registry declares —
`empty` where the API answers an empty set, `error_with_value` where it faults
(R-18: the documented refusal echoes the offending value; here it is the
domain refusal's subject, tagged like any other hop).

ONE TAG PER ITEM PER RESULT (R-20): `_slot_item` tags a value at most once per
call, and `_used` is reset on every call, so an account printed on several rows
carries its tag on the first rendering only. The writer refuses a control
character inside a slot (R-21) — a free-text value with a newline cannot be
laid down, which is the property `test_mock_v6` pins.

NOTHING HERE IMPORTS `pseudex` or the engine's validators. The parsers are
`tools_v6`'s own (the customer's acceptance rules), and the values are the
case's — a mock that shared the engine's checks would make the instrument part
of the detector.
"""
from __future__ import annotations

from bench.agentpii4.mock import CallLog
from bench.agentpii4.tools import Refusal
from bench.agentpii4.writer import Slot, serialise
from bench.agentpii5.mock import MIN_TAGGED_VALUE, BackendV5, digits_of, phone_canon
from bench.agentpii5.tools_v6 import TOOLS_V6, UNSCHEMED_TOOLS

# --- the registry surface mock.py reaches with one line -------------------------

V6_SPECS: dict[str, object] = {spec.base.name: spec for spec in TOOLS_V6}
V6_NAMES: frozenset[str] = frozenset(V6_SPECS)
# The 9 names D-069 left unschemed (closed/synthetic mirrors). NO HANDLER: they
# have no ToolSpecV5, so there is nothing to parse or to render, and this module
# asserts nothing about them — a call to one is a caller bug, not a mock one.
UNSCHEMED_NAMES: frozenset[str] = frozenset(
    entry.partition(":")[0].strip() for entry in UNSCHEMED_TOOLS)


def call_v6(backend: "BackendV6", tool: str, arguments: dict[str, object]) -> CallLog:
    """ONE call of a v6 tool on a v6-seeded backend: parse → apply → record.

    This is the module-level dispatcher `mock.py` wires in with a single line
    (`if tool in V6_NAMES: return call_v6(self, tool, arguments)`). It is the
    whole of the call path — the form is recorded on `backend.forms` beside the
    `CallLog` on `backend.calls`, so `BackendV5.form_of` keeps answering by seq.
    A documented parse refusal is recorded as `error_with_value` (R-18): its
    message names the offending argument, which is the value the model reads.
    """
    spec = V6_SPECS[tool]
    backend._used = set()
    backend._prose = {}
    backend._last_form = ""
    parsed = spec.base.parse(arguments)                       # type: ignore[attr-defined]
    backend._seq += 1
    if isinstance(parsed, Refusal):
        result = parsed.as_error()
        text, spans = serialise(result)
        log = CallLog(tool, backend._seq, None, parsed, result, text, spans)
        form = "error_with_value"
    else:
        result, node, form = backend._apply_v6(tool, parsed)
        text, spans = serialise(node)
        log = CallLog(tool, backend._seq, parsed, None, result, text, spans)
    backend._expand_prose(log)
    backend.calls.append(log)
    backend.forms.append(form)
    return log


class BackendV6(BackendV5):
    """The customer's v6 systems, seeded from a case's items by id and identity.

    Extends `BackendV5` for the `CallLog` bookkeeping (`_seq`, `calls`, `forms`,
    `form_of`) and the by-value tag index (`_by_value`, `_by_digits`, `_slot`)
    the write tools echo with; it does not use v5's tables.
    """

    def __init__(self, now_iso: str) -> None:
        super().__init__(now_iso, (), {})
        self._item_real: dict[str, str] = {}            # item id -> real (canonical) value
        self._item_type: dict[str, str] = {}            # item id -> pii type
        self._item_identity: dict[str, str] = {}        # item id -> identity
        self._identity_items: dict[str, list[str]] = {}  # identity -> item ids
        self._identity_type: dict[str, dict[str, str]] = {}  # identity -> {type: item id}
        self._record_items: dict[str, list[str]] = {}   # record id -> item ids
        self._record_type: dict[str, dict[str, str]] = {}   # record id -> {type: item id}
        self._record_fields: dict[str, dict[str, object]] = {}  # record id -> tool-notation fields
        self._path_item: dict[tuple[str, str], str] = {}      # (record id, field) -> item id
        self._ambiguous: set[str] = set()

    # --- calls -----------------------------------------------------------

    def call(self, tool: str, arguments: dict[str, object]) -> CallLog:
        if tool in V6_NAMES:
            return call_v6(self, tool, arguments)
        return super().call(tool, arguments)

    # --- seeding ---------------------------------------------------------

    def seed_v6_record(self, record_id: str, fields: dict[str, object]) -> None:
        """One seeded record, its fields in the TOOL'S OWN notation. The id is
        the opaque key a READ tool is looked up by (`bc-1`, `oz-123456`); for a
        PII-keyed tool the key is one of the fields, matched by value."""
        self._record_fields[record_id] = dict(fields)

    def seed_v6_item(self, record_id: str, item: object) -> None:
        """Bind one case item to the record it lives in, and to its identity.

        The REAL value a tool returns is `item.canonical` — «what a CRM stores:
        +7…, dd.mm.yyyy, series number» — never the spoken surface. The item's
        `where.path` names the seed field, so a read renders that field and tags
        it with the item id exactly, with no by-value guess. The by-value and
        by-digit indexes are fed the SAME value, so the write tools' echo
        (`_slot`) resolves a parsed argument to the item it restores, and a value
        two items share is dropped rather than tagged to the wrong person (the
        v5 `_ambiguous` rule).
        """
        value = item.canonical or item.value
        self._item_real[item.id] = value
        self._item_type[item.id] = item.type
        self._item_identity[item.id] = item.identity
        self._identity_items.setdefault(item.identity, []).append(item.id)
        self._identity_type.setdefault(item.identity, {}).setdefault(item.type, item.id)
        self._record_items.setdefault(record_id, []).append(item.id)
        self._record_type.setdefault(record_id, {}).setdefault(item.type, item.id)
        path = item.where.path
        if path:
            self._path_item[(record_id, path)] = item.id
        for key, index in ((value.lower(), self._by_value), (digits_of(value), self._by_digits)):
            if len(key) < MIN_TAGGED_VALUE:
                continue
            if key in self._ambiguous:
                continue
            if key in index and index[key] != item.id:
                self._ambiguous.add(key)
                del index[key]
                continue
            index[key] = item.id

    # --- rendering helpers ------------------------------------------------

    def _real(self, item_id: str) -> str:
        return self._item_real.get(item_id, "")

    def _slot_item(self, item_id: str, text: str) -> object:
        """`Slot(text, item_id)` the FIRST time an item is rendered in this call
        (R-20); a plain string for an unbound field or a repeat."""
        if item_id and item_id in self._item_real and item_id not in self._used:
            self._used.add(item_id)
            return Slot(text, item_id)
        return text

    @staticmethod
    def _get(fields: dict[str, object], path: str) -> object:
        value: object = fields
        for step in path.split("."):
            if not isinstance(value, dict) or step not in value:
                return None
            value = value[step]
        return value

    def _field(self, record_id: str, field: str) -> object:
        """A seed field rendered and tagged with the item bound to that field.
        An unbound field (business filler, a key that is not a result path)
        comes back as a plain string, which is what keeps an undeclared value
        from earning a hop the case never declared."""
        fields = self._record_fields.get(record_id, {})
        value = self._get(fields, field)
        text = str(value) if value not in (None, "") else ""
        item_id = self._path_item.get((record_id, field), "")
        if not text and item_id:
            text = self._real(item_id)
        return self._slot_item(item_id, text)

    def _find_record_by_value(self, value: str) -> str:
        """The record whose fields carry `value`, by digit signature or by the
        folded string — the two ways one datum is written in two notations."""
        wanted_digits = digits_of(value)
        wanted_lower = value.strip().lower()
        for record_id, fields in self._record_fields.items():
            for stored in fields.values():
                if not isinstance(stored, str) or not stored:
                    continue
                if wanted_digits and len(wanted_digits) >= 4 and digits_of(stored) == wanted_digits:
                    return record_id
                if wanted_lower and stored.strip().lower() == wanted_lower:
                    return record_id
        return ""

    def _find_record_mentioned(self, query: str) -> str:
        """The record a free-text query NAMES — the `dwh_sql_query` lookup: a
        digit signature or a folded whole word of the query matches a stored
        field, the way an index admits a row without sharing the engine's
        needle rule."""
        q_digits = digits_of(query)
        q_lower = query.lower()
        for record_id, fields in self._record_fields.items():
            for stored in fields.values():
                if not isinstance(stored, str) or not stored:
                    continue
                digits = digits_of(stored)
                if digits and len(digits) >= 6 and digits in q_digits:
                    return record_id
                if stored.lower() in q_lower:
                    return record_id
        return ""

    def _identity_for(self, value: str) -> str:
        item_id = self._by_digits.get(digits_of(value), "") \
            if len(digits_of(value)) >= 6 else ""
        if not item_id:
            item_id = self._by_value.get(value.strip().lower(), "")
        return self._item_identity.get(item_id, "")

    def _item_of_type(self, type_id: str) -> str:
        for item_id, typ in self._item_type.items():
            if typ == type_id:
                return item_id
        return ""

    def _type_item(self, identity: str, type_id: str) -> str:
        """The item of `type_id` for an identity, with a whole-state fallback
        for a minted value the case seeds without an identity of its own."""
        if identity:
            item_id = self._identity_type.get(identity, {}).get(type_id, "")
            if item_id:
                return item_id
        return self._item_of_type(type_id)

    def _error_v6(self, code: str, subject: object) -> tuple[dict[str, object], str]:
        """A 200 with an error body that echoes the offending value (R-18) — the
        domain refusal, not a parse one. The subject is a slot like any hop."""
        text = str(subject)
        return {"error": {"code": code, "subject": self._slot(text)}}, "error_with_value"

    @staticmethod
    def _plain(node: object) -> dict[str, object]:
        if isinstance(node, Slot):
            return node.text                                  # type: ignore[return-value]
        if isinstance(node, dict):
            return {key: BackendV6._plain(value) for key, value in node.items()}
        if isinstance(node, list):
            return [BackendV6._plain(value) for value in node]  # type: ignore[return-value]
        return node                                           # type: ignore[return-value]

    def _apply_v6(self, tool: str, parsed: dict[str, object]
                  ) -> tuple[dict[str, object], object, str]:
        node, form = getattr(self, "_v6_" + tool)(parsed)
        return self._plain(node), node, form

    # --- the WRITE tools: echo the parsed record (R-41) --------------------------

    def _v6_crm_requisite_set(self, parsed: dict[str, object]) -> tuple[object, str]:
        doc = parsed.get("ident_doc") or {}
        return {"requisite": {
            "id": 7,
            "rq_inn": self._slot(str(parsed["inn"])),
            "rq_ogrnip": self._slot(str(parsed.get("ogrnip", ""))),
            "rq_ident_doc_ser": self._slot(str(doc.get("ser", ""))),
            "rq_ident_doc_num": self._slot(str(doc.get("num", ""))),
        }}, "single"

    def _v6_crm_contact_upsert(self, parsed: dict[str, object]) -> tuple[object, str]:
        fields = parsed.get("custom_fields_values") or []
        field_nodes = [
            {"field_id": int(block["field_id"]),                        # type: ignore[index]
             "values": [{"value": self._slot(str(one["value"])),        # type: ignore[index]
                         "enum_code": str(one.get("enum_code", ""))}    # type: ignore[index]
                        for one in block.get("values", [])]}            # type: ignore[union-attr]
            for block in fields]
        return {"contact": {
            "id": "c-77",
            "first_name": self._slot(str(parsed["first_name"])),
            "last_name": self._slot(str(parsed["last_name"])),
            "custom_fields_values": field_nodes,
        }}, "nested"

    def _v6_email_contacts_import(self, parsed: dict[str, object]) -> tuple[object, str]:
        rows = [{"email": self._slot(str(row["email"])),                # type: ignore[index]
                 "phone": self._slot(str(row["phone"])),                # type: ignore[index]
                 "name": self._slot(str(row["name"]))}                  # type: ignore[index]
                for row in parsed["data"]]                              # type: ignore[union-attr]
        return {"imported": len(rows), "rows": rows}, "single"

    def _receipt(self, parsed: dict[str, object], receipt_id: str) -> tuple[object, str]:
        customer = parsed["customer"]                                   # type: ignore[index]
        block: dict[str, object] = {"full_name": self._slot(str(customer["full_name"]))}  # type: ignore[index]
        if customer.get("email"):                                       # type: ignore[union-attr]
            block["email"] = self._slot(str(customer["email"]))         # type: ignore[index]
        if customer.get("phone"):                                       # type: ignore[union-attr]
            block["phone"] = self._slot(str(customer["phone"]))         # type: ignore[index]
        if customer.get("inn"):                                         # type: ignore[union-attr]
            block["inn"] = self._slot(str(customer["inn"]))             # type: ignore[index]
        return {"receipt": {"id": receipt_id, "status": "succeeded", "customer": block}}, "single"

    def _v6_receipt_create(self, parsed: dict[str, object]) -> tuple[object, str]:
        return self._receipt(parsed, "rt-1")

    def _v6_fiscal_receipt_create(self, parsed: dict[str, object]) -> tuple[object, str]:
        client = parsed["receipt"]["client"]                            # type: ignore[index]
        block: dict[str, object] = {}
        for key in ("name", "email", "phone", "inn", "birthdate",
                    "document_data", "address"):
            if client.get(key):                                         # type: ignore[union-attr]
                block[key] = self._slot(str(client[key]))               # type: ignore[index]
        return {"receipt": {"uuid": "4475d6d8-844d-4d05-aa8b-e3dbdf3defd5",
                            "client": block}}, "single"

    def _v6_sms_send(self, parsed: dict[str, object]) -> tuple[object, str]:
        return {"message_id": "sms-1", "status": "queued",
                "destination": self._slot(str(parsed["destination"]))}, "single"

    def _v6_ruble_transfer_create(self, parsed: dict[str, object]) -> tuple[object, str]:
        recipient = parsed["recipient"]                                 # type: ignore[index]
        return {"paymentId": "p-1", "status": "IN_PROGRESS", "recipient": {
            "name": self._slot(str(recipient["name"])),                 # type: ignore[index]
            "account": self._slot(str(recipient["account"])),           # type: ignore[index]
        }}, "single"

    def _v6_e_prescription_create(self, parsed: dict[str, object]) -> tuple[object, str]:
        # The recipe number is MINTED by the tool, not echoed: it is the seeded
        # PRESCRIPTION_NUMBER item, keyed by the patient's (or policy's) identity.
        patient = parsed["patient"]                                     # type: ignore[index]
        identity = self._identity_for(str(patient["fio"]))              # type: ignore[index]
        if not identity:
            identity = self._identity_for(str(patient.get("oms_policy", "")))  # type: ignore[union-attr]
        number_item = self._type_item(identity, "PRESCRIPTION_NUMBER")
        return {"prescription": {
            "number": self._slot_item(number_item, self._real(number_item)),
            "patient": {
                "fio": self._slot(str(patient["fio"])),                 # type: ignore[index]
                "birth_date": self._slot(str(patient["birth_date"])),   # type: ignore[index]
                "oms_policy": self._slot(str(patient.get("oms_policy", ""))),  # type: ignore[index]
            },
        }}, "single"

    def _v6_loyalty_card_bind(self, parsed: dict[str, object]) -> tuple[object, str]:
        return {"status": "Success", "customer": {"processingStatus": "Found"},
                "discountCard": {"processingStatus": "Bound",
                                 "ids": {"number": self._slot(str(parsed["card_number"]))}}}, "single"

    def _v6_insurance_claim_create(self, parsed: dict[str, object]) -> tuple[object, str]:
        # The claim_id is a minted business id, NOT personal data — the spec's
        # `result_pii` names only `applicant.fio` and `policy` — so it is laid
        # down as a plain string, never tagged.
        applicant = parsed["applicant"]                                 # type: ignore[index]
        return {"claim_id": "У-2026-004512", "status": "registered",
                "applicant": {"fio": self._slot(str(applicant["fio"]))},  # type: ignore[index]
                "policy": self._slot(str(parsed["policy"]))}, "single"

    def _v6_sim_replace_request(self, parsed: dict[str, object]) -> tuple[object, str]:
        return {"request_id": "SR-2026-0912", "status": "accepted",
                "msisdn": self._slot(str(parsed["msisdn"])),
                "iccid": self._slot(str(parsed["new_iccid"]))}, "single"

    def _v6_guest_arrival_notify(self, parsed: dict[str, object]) -> tuple[object, str]:
        guest = parsed["guest"]                                         # type: ignore[index]
        fio = " ".join(str(guest[key]) for key in ("last_name", "first_name")  # type: ignore[index]
                       if guest.get(key))                               # type: ignore[union-attr]
        return {"notification_id": "N-2026-18-004512", "status": "sent",
                "guest": {"fio": self._slot(fio),
                          "document": self._slot(str(guest["document"]["number"]))}}, "single"  # type: ignore[index]

    def _v6_payroll_card_registry(self, parsed: dict[str, object]) -> tuple[object, str]:
        # The account is MINTED by the bank, not echoed: it is the seeded
        # BANK_ACCOUNT item. `status` is a columnar label the registry's
        # `rows[][N]` mapping swept into `result_pii`; it is seeded so the
        # leaf still carries a value the case declared.
        account_item = self._item_of_type("BANK_ACCOUNT")
        rows = [{"tab_number": self._slot(str(row.get("tab_number", ""))),  # type: ignore[index]
                 "fio": self._slot(str(row["fio"])),                    # type: ignore[index]
                 "account": self._slot_item(account_item, self._real(account_item)),
                 "status": self._slot("Открыт")}                        # type: ignore[index]
                for row in parsed["employees"]]                         # type: ignore[union-attr]
        return {"rows": rows}, "list"

    def _v6_audience_segment_upload(self, parsed: dict[str, object]) -> tuple[object, str]:
        return {"segment": {"id": 12345, "name": str(parsed["segment_name"]),
                            "type": "uploading", "status": "uploaded",
                            "hashed": bool(parsed["hashed"])}}, "single"

    # --- the READ tools: the stored record, tagged by the exact binding ----------

    def _v6_crm_requisite_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = "inn" if "inn" in parsed else "ogrnip"
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"requisites": []}, "empty"
        return {"requisite": {
            "id": 7,
            "rq_inn": self._field(rid, "rq_inn"),
            "rq_ogrnip": self._field(rid, "ogrnip"),
            "rq_ident_doc_ser": self._field(rid, "rq_ident_doc_ser"),
            "rq_ident_doc_num": self._field(rid, "rq_ident_doc_num"),
        }}, "single"

    def _v6_bank_accounts_list(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = str(parsed["client_id"])
        if rid not in self._record_fields:
            return {"Data": {"Account": []}}, "empty"
        return {"Data": {"Account": [{
            "AccountDetails": [{
                "identification": self._field(rid, "account"),
                "name": self._field(rid, "name"),
            }],
        }]}}, "list"

    def _v6_credit_report_request(self, parsed: dict[str, object]) -> tuple[object, str]:
        subject = parsed["subject"]                                     # type: ignore[index]
        key = str(subject.get("snils", "") or subject.get("inn", "") or subject.get("passport", ""))  # type: ignore[union-attr]
        rid = self._find_record_by_value(key)
        if not rid:
            return {"subject": None, "contracts": []}, "empty"
        return {"subject": {
            "name": self._field(rid, "name"),
            "birth_date": self._field(rid, "birth_date"),
            "passport": self._field(rid, "passport"),
        }, "contracts": [{"uid": self._field(rid, "loan_uid")}]}, "nested"

    def _v6_debtor_card_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["contract_number"]))
        if not rid:
            return self._error_v6("CONTRACT_NOT_FOUND", str(parsed["contract_number"]))
        return {"debtor": {
            "fio": self._field(rid, "fio"),
            "birth_date": self._field(rid, "birth_date"),
            "phones": [self._field(rid, "phone")],
            "reg_address": self._field(rid, "reg_address"),
        }, "loan": {
            "contract": self._field(rid, "contract_number"),
            "uid": self._field(rid, "loan_uid"),
        }, "third_parties": [{
            "fio": self._field(rid, "tp_fio"),
            "phone": self._field(rid, "tp_phone"),
        }]}, "nested"

    def _v6_eln_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["ln_code"]))
        if not rid:
            return {"status": "1", "data": None}, "empty"
        return {"status": "1", "data": {"row": {
            "snils": self._field(rid, "snils"),
            "surname": self._field(rid, "surname"),
            "name": self._field(rid, "name"),
            "patronymic": self._field(rid, "patronymic"),
            "lnCode": self._field(rid, "ln_code"),
            "birthday": self._field(rid, "birthday"),
            "servFullData": {
                "surname": self._field(rid, "serv_surname"),
                "name": self._field(rid, "serv_name"),
                "birthday": self._field(rid, "serv_birthday"),
            },
        }}}, "nested"

    def _v6_remd_documents_search(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["patient_snils"]))
        if not rid:
            return {"items": [], "has_next": False}, "empty"
        return {"items": [{
            "document_number": self._field(rid, "document_number"),
            "patient": {
                "snils": self._field(rid, "snils"),
                "fio": self._field(rid, "fio"),
                "birth_date": self._field(rid, "birth_date"),
            },
        }], "has_next": False}, "list"

    def _v6_oms_policy_find(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = "enp" if "enp" in parsed else ("snils" if "snils" in parsed else "last_name")
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"person": None}, "empty"
        return {"person": {
            "fam": self._field(rid, "fam"),
            "im": self._field(rid, "im"),
            "ot": self._field(rid, "ot"),
            "dr": self._field(rid, "dr"),
            "enp": self._field(rid, "enp"),
            "snils": self._field(rid, "snils"),
        }}, "single"

    def _v6_marketplace_order_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["posting_number"]))
        if not rid:
            return {"result": None}, "empty"
        return {"result": {
            "posting_number": str(parsed["posting_number"]),
            "customer": {"name": self._field(rid, "name"),
                         "address": {"address_tail": self._field(rid, "address")}},
            "addressee": {"name": self._field(rid, "addressee_name")},
        }}, "nested"

    def _v6_loyalty_customer_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = next(k for k in ("mobile_phone", "email", "discount_card") if k in parsed)
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"status": "Success", "customer": {"processingStatus": "NotFound"}}, "empty"
        return {"status": "Success", "customer": {
            "processingStatus": "Found",
            "lastName": self._field(rid, "last_name"),
            "firstName": self._field(rid, "first_name"),
            "middleName": self._field(rid, "middle_name"),
            "birthDate": self._field(rid, "birth_date"),
            "mobilePhone": self._field(rid, "mobile_phone"),
            "email": self._field(rid, "email"),
            "discountCards": [{"ids": {"number": self._field(rid, "card_number")}}],
        }}, "single"

    def _v6_cdek_order_info(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["cdek_number"]))
        if not rid:
            return self._error_v6("v2_entity_not_found_im_number", str(parsed["cdek_number"]))
        return {"entity": {
            "uuid": "72753031-0000-0000-0000-000000000000",
            "cdek_number": str(parsed["cdek_number"]),
            "recipient": {
                "name": self._field(rid, "name"),
                "passport_series": self._field(rid, "passport_series"),
                "passport_number": self._field(rid, "passport_number"),
                "passport_date_of_birth": self._field(rid, "passport_date_of_birth"),
                "tin": self._field(rid, "tin"),
                "phones": [{"number": self._field(rid, "phone")}],
            },
            "to_location": {"address": self._field(rid, "address")},
        }}, "nested"

    def _v6_osago_policy_check(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = next(k for k in ("plate", "vin", "policy") if k in parsed)
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"policy": None, "message": "Сведения о договоре ОСАГО не найдены"}, "empty"
        return {"policy": {
            "series": self._field(rid, "series"),
            "number": self._field(rid, "osago_number"),
            "status": "Действует",
        }, "vehicle": {
            "plate": self._field(rid, "plate"),
            "vin": self._field(rid, "vin"),
        }}, "single"

    def _v6_traffic_fines_check(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["plate"])) \
            or self._find_record_by_value(str(parsed["sts"]))
        if not rid:
            return {"fines": []}, "empty"
        return {"fines": [{"uin": self._field(rid, "uin"),
                           "vehicle": self._field(rid, "plate")}]}, "list"

    def _v6_epts_status_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = "epts_number" if "epts_number" in parsed else "vin"
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"epts": None}, "empty"
        return {"epts": self._field(rid, "epts"),
                "status": "действующий",
                "vin": self._field(rid, "vin")}, "single"

    def _v6_driver_license_check(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["license_number"]))
        if not rid:
            return self._error_v6("100", str(parsed["license_number"]))
        return {"license": self._field(rid, "license"),
                "issued": "2019-06-11", "valid_to": "2029-06-11",
                "categories": "B, B1, M", "deprivation": []}, "single"

    def _v6_subscriber_profile_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["msisdn"]))
        if not rid:
            return {"individual": None}, "empty"
        return {"individual": {
            "familyName": self._field(rid, "family_name"),
            "givenName": self._field(rid, "given_name"),
            "middleName": self._field(rid, "middle_name"),
            "birthDate": self._field(rid, "birth_date"),
            "individualIdentification": [
                {"identificationId": self._field(rid, "passport")}],
        }, "contract": {
            "number": self._field(rid, "contract_number"),
            "personalAccount": self._field(rid, "personal_account"),
        }, "sim": {
            "msisdn": self._field(rid, "msisdn"),
            "iccid": self._field(rid, "iccid"),
            "imsi": self._field(rid, "imsi"),
        }, "device": {"imei": self._field(rid, "imei")}}, "nested"

    def _v6_egrn_extract_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["cadastral_number"]))
        if not rid:
            return {"object": None}, "empty"
        return {"object": {
            "cadastral_number": self._field(rid, "cadastral_number"),
            "address": self._field(rid, "address"),
        }, "rights": [{
            "holder": self._field(rid, "holder"),
            "birth_date": self._field(rid, "birth_date"),
            "reg_number": self._field(rid, "reg_number"),
        }]}, "nested"

    def _v6_gis_gkh_account_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = "els" if "els" in parsed else "address"
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"account": None}, "empty"
        return {"account": {
            "els": self._field(rid, "els"),
            "zhku_id": self._field(rid, "zhku_id"),
            "personal_account": self._field(rid, "personal_account"),
            "address": self._field(rid, "address"),
            "payer": {"fio": self._field(rid, "fio"),
                      "snils": self._field(rid, "snils")},
        }}, "single"

    def _v6_pms_booking_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = str(parsed["booking_id"])
        if rid not in self._record_fields:
            return {"booking": None}, "empty"
        return {"booking": {
            "id": rid,
            "customer": {"name": self._field(rid, "name"),
                         "surname": self._field(rid, "surname"),
                         "phone": self._field(rid, "phone"),
                         "email": self._field(rid, "email")},
            "guests": [{"surname": self._field(rid, "g_surname"),
                        "name": self._field(rid, "g_name"),
                        "birthdate": self._field(rid, "g_birthdate"),
                        "document": {"series": self._field(rid, "g_series"),
                                     "number": self._field(rid, "g_number")}}],
        }}, "nested"

    def _v6_flight_order_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["flight_order_id"]))
        if not rid:
            return self._error_v6("1797", str(parsed["flight_order_id"]))
        return {"data": {
            "associatedRecords": [{"reference": self._field(rid, "pnr")}],
            "travelers": [{
                "dateOfBirth": self._field(rid, "date_of_birth"),
                "name": {"firstName": self._field(rid, "first_name"),
                         "lastName": self._field(rid, "last_name")},
                "documents": [{"number": self._field(rid, "passport_number")}],
                "contact": {"emailAddress": self._field(rid, "email"),
                            "phones": [{"number": self._field(rid, "phone")}]},
            }],
        }}, "nested"

    def _v6_hr_employee_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = "tab_number" if "tab_number" in parsed else "fio"
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"value": []}, "empty"
        return {"value": [{
            "Description": self._field(rid, "description"),
            "ТабельныйНомер": self._field(rid, "tab_number"),
            "ФизическоеЛицо": {
                "ДатаРождения": self._field(rid, "birth_date"),
                "ИНН": self._field(rid, "inn"),
                "СтраховойНомерПФР": self._field(rid, "snils_pfr"),
            },
        }]}, "single"

    def _v6_resume_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = str(parsed["resume_id"])
        if rid not in self._record_fields:
            return {"id": rid, "last_name": None, "first_name": None,
                    "birth_date": None, "contact": None}, "single"
        return {"id": rid,
                "last_name": self._field(rid, "last_name"),
                "first_name": self._field(rid, "first_name"),
                "middle_name": self._field(rid, "middle_name"),
                "birth_date": self._field(rid, "birth_date"),
                "contact": [
                    {"type": {"id": "cell"},
                     "value": {"formatted": self._field(rid, "phone")}},
                    {"type": {"id": "email"},
                     "value": self._field(rid, "email")},
                ]}, "nested"

    def _v6_arbitration_case_search(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = next(k for k in ("participant", "inn", "case_number") if k in parsed)
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"cases": []}, "empty"
        return {"cases": [{
            "number": self._field(rid, "number"),
            "respondent": {"name": self._field(rid, "name"),
                           "inn": self._field(rid, "inn"),
                           "ogrnip": self._field(rid, "ogrnip"),
                           "address": self._field(rid, "address")},
        }]}, "list"

    def _v6_probate_case_search(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["fio"]))
        if not rid:
            return {"cases": []}, "empty"
        return {"cases": [{
            "deceased": self._field(rid, "deceased"),
            "birth_date": self._field(rid, "birth_date"),
            "death_date": self._field(rid, "death_date"),
            "case_number": self._field(rid, "case_number"),
        }]}, "list"

    def _v6_fns_inn_lookup(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["docno"])) \
            or self._find_record_by_value(str(parsed["fam"]))
        if not rid:
            return {"code": 0, "captchaRequired": False}, "empty"
        return {"code": 1, "inn": self._field(rid, "inn"),
                "captchaRequired": False}, "single"

    def _v6_npd_status_check(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["inn"]))
        if not rid:
            return self._error_v6("validation.failed", str(parsed["inn"]))
        return {"status": True, "message": self._field(rid, "message")}, "single"

    def _v6_budget_charges_find(self, parsed: dict[str, object]) -> tuple[object, str]:
        key = next(k for k in ("payer_snils", "payer_inn", "payer_passport") if k in parsed)
        rid = self._find_record_by_value(str(parsed[key]))
        if not rid:
            return {"charges": []}, "empty"
        return {"charges": [{
            "uin": self._field(rid, "uin"),
            "payer_name": self._field(rid, "payer_name"),
            "payer_identifier": self._field(rid, "payer_identifier"),
        }]}, "list"

    def _v6_diploma_registry_check(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_by_value(str(parsed["blank_number"])) \
            or self._find_record_by_value(str(parsed["blank_series"]))
        if not rid:
            return {"found": False}, "empty"
        return {"found": True, "document": {
            "series": self._field(rid, "series"),
            "number": self._field(rid, "diploma_number"),
            "reg_number": self._field(rid, "reg_number"),
            "holder": self._field(rid, "holder"),
        }}, "single"

    def _v6_exam_results_check(self, parsed: dict[str, object]) -> tuple[object, str]:
        if "reg_code" in parsed:
            rid = self._find_record_by_value(str(parsed["reg_code"]))
        else:
            rid = self._find_record_by_value(str(parsed["document_number"]))
        if not rid:
            return {"participant": None, "results": []}, "empty"
        return {"participant": self._field(rid, "participant"),
                "results": [{"subject": "Математика профильная",
                             "score": "78", "status": "Результат утверждён"}]}, "list"

    def _v6_lms_user_get(self, parsed: dict[str, object]) -> tuple[object, str]:
        values = [str(one) for one in parsed["values"]]                 # type: ignore[union-attr]
        rid = ""
        for value in values:
            rid = self._find_record_by_value(value)
            if rid:
                break
        if not rid:
            return [], "empty"
        return [{"id": 412,
                 "firstname": self._field(rid, "firstname"),
                 "lastname": self._field(rid, "lastname"),
                 "email": self._field(rid, "email"),
                 "idnumber": self._field(rid, "idnumber"),
                 "phone1": self._field(rid, "phone1"),
                 "username": self._field(rid, "username")}], "list"

    def _v6_dwh_sql_query(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = self._find_record_mentioned(str(parsed["sql"]))
        if not rid:
            return {"meta": [], "data": [], "rows": 0}, "empty"
        return {"meta": [], "data": [{
            "client_fio": self._field(rid, "client_fio"),
            "phone": self._field(rid, "phone"),
            "inn": self._field(rid, "inn"),
        }], "rows": 1}, "list"

    def _v6_bi_chart_export(self, parsed: dict[str, object]) -> tuple[object, str]:
        rid = str(parsed["chart_id"])
        if rid not in self._record_fields:
            return {"result": []}, "empty"
        return {"result": [{"colnames": ["manager", "client", "phone", "deal_sum"],
                            "data": [{
                                "manager": self._field(rid, "manager"),
                                "client": self._field(rid, "client"),
                                "phone": self._field(rid, "phone"),
                            }], "rowcount": 1}]}, "list"

    def _v6_web_visits_export(self, parsed: dict[str, object]) -> tuple[object, str]:
        # The TSV `text` leaf carries several values in one prose line. The
        # writer refuses control characters inside a slot (R-21), so the real
        # API's tabs/newlines are rendered as spaces and each value keeps its
        # own span via `_compose` (lifted by `_expand_prose` in `call_v6`).
        rid = next((one for one, fields in self._record_fields.items()
                    if "client_id" in fields), "")
        if not rid:
            return {"text": ""}, "free_text"
        client_id = self._real(self._path_item.get((rid, "client_id"), ""))
        ip = self._real(self._path_item.get((rid, "ip"), ""))
        text = self._compose((("ym:s:clientID ", ""),
                              (client_id, self._path_item.get((rid, "client_id"), "")),
                              (" ym:s:ipAddress ", ""),
                              (ip, self._path_item.get((rid, "ip"), ""))), "")
        return {"text": text}, "free_text"

    def _v6_phone_clean(self, parsed: dict[str, object]) -> tuple[object, str]:
        # DaData answers a source it cannot normalise with an empty item set;
        # a normalisable one comes back in its canon notation.
        source = str(parsed["source"])
        if len(digits_of(source)) != 11:
            return {"items": []}, "empty"
        canonical = phone_canon(source)
        return {"items": [{
            "source": source,
            "phone": self._slot(canonical),
            "number": digits_of(source),
            "provider": "МТС",
            "qc": 0,
        }]}, "canon"


def seed_backend_v6(case: object) -> BackendV6:
    """The world one v6 case starts in: every seeded record and its items.

    The record id is the opaque key a READ tool is looked up by, the fields are
    the stored record in the TOOL's notation, and each item is bound by its
    `where.path` (the seed field) so a read tags the exact value — no by-value
    guess, the v5 ambiguity lesson. The item's `canonical` is the real value a
    tool returns, and the by-value/by-digit indexes are fed the same value so a
    WRITE tool's echo resolves to the item it restores.
    """
    items = {item.id: item for item in case.base.pii}
    backend = BackendV6(case.base.now)
    for record in case.base.seed_records:
        backend.seed_v6_record(record.id, dict(record.fields))
        for item_id in record.pii_ids:
            item = items.get(item_id)
            if item is None:
                raise KeyError(f"seed {record.id} names item {item_id!r}, "
                               f"which the case does not carry")
            backend.seed_v6_item(record.id, item)
    return backend
