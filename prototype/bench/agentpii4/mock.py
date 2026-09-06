"""The stateful mock backend: the customer's systems, one instance per arm-run.

A CLASS, because it is mutable external state with a lifetime — the record a
lookup returns is the record an upsert wrote, and the id `create` allocated
is the id the next call refers to. This repository's one sanctioned reason
for a class.

WHAT THE COMPARATOR SEES IS THE TYPED STATE, NOT THE ARGUMENT STRINGS. Every
call goes through the registry's strict parser (`tools.py`); what is stored
is the parsed value. Two arms that wrote «ул. Ленина» and «улица Ленина» into
a field the API keeps as free text differ in state; two arms that wrote
«+79161234567» and «+7 916 123-45-67» into an E.164 field — the second is
REFUSED by the parser, as the real API would refuse it, and the refusal is
what is recorded.

IDS ARE ALLOCATED BY WRITES ONLY, in call order. An extra lookup in one arm
does not shift the ids of the other, so level-3 identity does not depend on
the model's exploratory reads.

Results are produced FROM STATE and serialised with the offsets of every PII
value they carry (`writer.serialise`), so the intervention arm can mask them
inbound and the detection axis can score them.
"""
import hashlib
import json
from dataclasses import dataclass, field

from bench.agentpii4.tools import REGISTRY, Refusal
from bench.agentpii4.writer import Slot, serialise


@dataclass(frozen=True)
class Record:
    """One stored effect: the tool, its order among writes, the typed fields."""

    table: str
    id: str
    tool: str
    seq: int
    fields: dict[str, object]


@dataclass
class CallLog:
    tool: str
    seq: int
    parsed: dict[str, object] | None
    refusal: Refusal | None
    result: dict[str, object]
    result_text: str
    result_spans: dict[str, tuple[int, int]] = field(default_factory=dict)


class Backend:
    """The customer's systems for one arm-run."""

    def __init__(self, now_iso: str) -> None:
        self._now = now_iso
        self._tables: dict[str, dict[str, Record]] = {
            "contacts": {}, "addresses": {}, "orders": {}, "claims": {},
            "payments": {}, "verifications": {}, "appointments": {},
            "sms": {}, "callbacks": {}, "notes": {}}
        self._counters: dict[str, int] = {}
        self._seq = 0
        self.calls: list[CallLog] = []

    # --- seeding ---------------------------------------------------------

    def seed_contact(self, contact_id: str, fields: dict[str, object]) -> None:
        self._tables["contacts"][contact_id] = Record("contacts", contact_id, "seed", 0, dict(fields))

    def seed_address(self, address_id: str, fields: dict[str, object]) -> None:
        self._tables["addresses"][address_id] = Record("addresses", address_id, "seed", 0, dict(fields))

    # --- calls -----------------------------------------------------------

    def call(self, tool: str, arguments: dict[str, object]) -> CallLog:
        spec = REGISTRY[tool]
        parsed = spec.parse(arguments)
        self._seq += 1
        if isinstance(parsed, Refusal):
            result = parsed.as_error()
            text, spans = serialise(result)
            log = CallLog(tool, self._seq, None, parsed, result, text, spans)
        else:
            result, spans_node = self._apply(tool, parsed)
            text, spans = serialise(spans_node)
            log = CallLog(tool, self._seq, parsed, None, result, text, spans)
        self.calls.append(log)
        return log

    def _next_id(self, table: str, prefix: str) -> str:
        self._counters[table] = self._counters.get(table, 0) + 1
        return f"{prefix}-{self._counters[table]}"

    def _store(self, table: str, tool: str, fields: dict[str, object], prefix: str,
               record_id: str = "") -> Record:
        record_id = record_id or self._next_id(table, prefix)
        record = Record(table, record_id, tool, self._seq, dict(fields))
        self._tables[table][record_id] = record
        return record

    def _domain_error(self, code: str, subject: str) -> tuple[dict[str, object], object]:
        """A well-formed call about a state that is not there.

        NOT A `Refusal`: that is the documented rejection of a malformed
        argument and is scored as `validated_refused`. This is a 200 with an
        error body — what a real API answers when the order does not exist —
        and it allocates no id, because ids are allocated by writes only."""
        data = {"error": {"code": code, "subject": subject}}
        return data, {"error": {"code": code, "subject": subject}}

    def _apply(self, tool: str, parsed: dict[str, object]) -> tuple[dict[str, object], object]:
        """Mutate state and return (result as data, result as a Slot tree)."""
        if tool == "delivery_create_order":
            record = self._store("orders", tool, parsed, "ord")
            recipient = parsed["recipient"]  # type: ignore[index]
            location = parsed["to_location"]  # type: ignore[index]
            data = {"uuid": record.id, "status": "ACCEPTED",
                    "recipient": {"name": recipient["name"], "phone": recipient["phones"][0]},
                    "to_location": {"postal_code": location["postal_code"], "city": location["city"],
                                    "address": location["address"]}}
            node = {"uuid": record.id, "status": "ACCEPTED",
                    "recipient": {"name": Slot(str(recipient["name"]), "r_name"),
                                  "phone": Slot(str(recipient["phones"][0]), "r_phone")},
                    "to_location": {"postal_code": str(location["postal_code"]),
                                    "city": Slot(str(location["city"]), "r_city"),
                                    "address": Slot(str(location["address"]), "r_addr")}}
            return data, node
        if tool == "courier_book":
            record = self._store("claims", tool, parsed, "clm")
            data = {"claim_id": record.id, "status": "estimating"}
            return data, dict(data)
        if tool == "address_suggest":
            query = str(parsed["query"]).lower()
            rows = list(self._tables["addresses"].values())
            words = [word for word in query.replace(",", " ").split() if len(word) > 2]
            scored = []
            for row in rows:
                haystack = " ".join(str(value).lower() for value in row.fields.values())
                score = sum(1 for word in words if word in haystack)
                scored.append((score, row))
            scored.sort(key=lambda pair: (-pair[0], pair[1].id))
            chosen = [row for _score, row in scored[: int(parsed["count"])]]  # type: ignore[arg-type]
            suggestions = []
            nodes = []
            for index, row in enumerate(chosen):
                data_row = {"postal_code": row.fields["postal_code"], "region": row.fields["region"],
                            "city": row.fields["city"], "street": row.fields["street"],
                            "house": row.fields["house"], "flat": row.fields.get("flat", ""),
                            "fias_id": row.fields["fias_id"]}
                # THE SCORE WAS COMPUTED AND THROWN AWAY. A suggester that ranks
                # without saying how sure it is cannot be chosen from, and «the
                # agent picks a candidate by confidence» is a whole family of
                # cases that could not be written. Rounded to two places: a
                # float the two arms differ on in the sixteenth digit is noise
                # dressed as a divergence.
                confidence = round(scored[index][0] / max(1, len(words)), 2)
                suggestions.append({"value": row.fields["value"], "data": data_row,
                                    "confidence": confidence})
                nodes.append({"value": Slot(str(row.fields["value"]), f"s{index}_value"),
                              "confidence": f"{confidence:.2f}",
                              "data": {"postal_code": str(row.fields["postal_code"]),
                                       "region": str(row.fields["region"]),
                                       "city": str(row.fields["city"]),
                                       "street": Slot(str(row.fields["street"]), f"s{index}_street"),
                                       "house": Slot(str(row.fields["house"]), f"s{index}_house"),
                                       "flat": str(row.fields.get("flat", "")),
                                       "fias_id": str(row.fields["fias_id"])}})
            return {"suggestions": suggestions}, {"suggestions": nodes}
        if tool == "payment_create":
            record = self._store("payments", tool, parsed, "pay")
            data = {"id": record.id, "status": "pending"}
            return data, dict(data)
        if tool == "passport_verify":
            record = self._store("verifications", tool, parsed, "ver")
            data = {"id": record.id, "valid": True, "checked_at": self._now}
            return data, dict(data)
        if tool == "clinic_book":
            record = self._store("appointments", tool, parsed, "apt")
            data = {"appointment_id": record.id, "slot": parsed["slot"], "status": "booked"}
            return data, dict(data)
        if tool == "crm_find_contact":
            query = parsed["query"]  # type: ignore[index]
            key, value = next(iter(query.items()))  # type: ignore[union-attr]
            found = [row for row in self._tables["contacts"].values()
                     if str(row.fields.get(key, "")).lower() == str(value).lower()]
            contacts = []
            nodes = []
            for index, row in enumerate(found):
                fields = row.fields
                address = fields.get("address") or {}
                contacts.append({"id": row.id, "last_name": fields.get("last_name", ""),
                                 "first_name": fields.get("first_name", ""),
                                 "middle_name": fields.get("middle_name", ""),
                                 "phone": fields.get("phone", ""), "email": fields.get("email", ""),
                                 "birth_date": fields.get("birth_date", ""),
                                 "address": dict(address)})
                node: dict[str, object] = {"id": row.id}
                for name in ("last_name", "first_name", "middle_name"):
                    if fields.get(name):
                        node[name] = Slot(str(fields[name]), f"c{index}_{name}")
                    else:
                        node[name] = ""
                node["phone"] = Slot(str(fields["phone"]), f"c{index}_phone") if fields.get("phone") else ""
                node["email"] = Slot(str(fields["email"]), f"c{index}_email") if fields.get("email") else ""
                node["birth_date"] = (Slot(str(fields["birth_date"]), f"c{index}_birth")
                                      if fields.get("birth_date") else "")
                if address:
                    node["address"] = {"city": str(address.get("city", "")),
                                       "street": Slot(str(address["street"]), f"c{index}_street"),
                                       "house": Slot(str(address["house"]), f"c{index}_house"),
                                       "flat": str(address.get("flat", ""))}
                else:
                    node["address"] = {}
                nodes.append(node)
            return {"contacts": contacts}, {"contacts": nodes}
        if tool == "crm_upsert_contact":
            contact_id = str(parsed.get("id") or "")
            existing = self._tables["contacts"].get(contact_id)
            merged: dict[str, object] = dict(existing.fields) if existing else {}
            updated = list(parsed["contact"].keys())  # type: ignore[union-attr]
            merged.update(parsed["contact"])  # type: ignore[arg-type]
            record = self._store("contacts", tool, merged, "c", contact_id)
            data = {"id": record.id, "updated_fields": updated}
            return data, dict(data)
        if tool == "crm_segment_report":
            # READ-ONLY: no id is allocated, because ids are allocated by writes
            # only. The answer is the count per bucket — a real aggregate, and
            # it carries no personal data of its own.
            counts: dict[str, int] = {}
            for member in parsed["members"]:  # type: ignore[union-attr]
                bucket = str(dict(member)["bucket"])  # type: ignore[arg-type]
                counts[bucket] = counts.get(bucket, 0) + 1
            data = {"group_by": parsed["group_by"],
                    "buckets": [{"bucket": bucket, "count": count}
                                for bucket, count in sorted(counts.items())]}
            return data, {"group_by": str(parsed["group_by"]),
                          "buckets": [{"bucket": str(one["bucket"]), "count": int(one["count"])}
                                      for one in data["buckets"]]}  # type: ignore[index,arg-type]
        if tool == "send_template":
            # THE RENDERED TEXT IS WHAT THE CUSTOMER READS, so it comes back as
            # a Slot: a placeholder left unfilled or a substitute put into one
            # is visible only in the rendered string.
            record = self._store("sms", tool, parsed, "tpl")
            data = {"id": record.id, "status": "queued", "text": parsed["text"]}
            node = {"id": record.id, "status": "queued",
                    "text": Slot(str(parsed["text"]), "tpl_text")}
            return data, node
        if tool == "crm_add_note":
            # A NOTE IS A WRITE WHOSE RESULT CARRIES NOTHING PERSONAL: the text
            # the model wrote is already in `parsed`, and echoing it back would
            # hand the same string to the detector twice. The id and the length
            # are what a CRM returns.
            record = self._store("notes", tool, parsed, "note")
            data = {"id": record.id, "entity_id": parsed["entity_id"],
                    "length": len(str(parsed["text"]))}
            return data, dict(data)
        if tool == "notify_sms":
            record = self._store("sms", tool, parsed, "sms")
            data = {"id": record.id, "status": "queued"}
            return data, dict(data)
        if tool == "callback_schedule":
            record = self._store("callbacks", tool, parsed, "cb")
            data = {"id": record.id, "status": "scheduled"}
            return data, dict(data)
        if tool == "order_status":
            record = self._tables["orders"].get(str(parsed["order_id"]))
            if record is None:
                return self._domain_error("ORDER_NOT_FOUND", str(parsed["order_id"]))
            recipient = record.fields.get("recipient") or {}
            location = record.fields.get("to_location") or {}
            phones = recipient.get("phones") or [""]        # type: ignore[union-attr]
            data = {"uuid": record.id, "status": record.fields.get("status", "ACCEPTED"),
                    "date": record.fields.get("date", ""),
                    "recipient": {"name": recipient.get("name", ""), "phone": phones[0]},  # type: ignore[union-attr]
                    "to_location": {"city": location.get("city", ""),          # type: ignore[union-attr]
                                    "address": location.get("address", "")}}   # type: ignore[union-attr]
            node = {"uuid": record.id, "status": str(data["status"]), "date": str(data["date"]),
                    "recipient": {"name": Slot(str(recipient.get("name", "")), "os_name"),  # type: ignore[union-attr]
                                  "phone": Slot(str(phones[0]), "os_phone")},
                    "to_location": {"city": str(location.get("city", "")),      # type: ignore[union-attr]
                                    "address": Slot(str(location.get("address", "")), "os_addr")}}  # type: ignore[union-attr]
            return data, node
        if tool == "order_cancel":
            record = self._tables["orders"].get(str(parsed["order_id"]))
            if record is None:
                return self._domain_error("ORDER_NOT_FOUND", str(parsed["order_id"]))
            if record.fields.get("status") == "CANCELLED":
                return self._domain_error("ALREADY_CANCELLED", record.id)
            fields = dict(record.fields)
            fields["status"] = "CANCELLED"
            fields["cancel_reason"] = parsed.get("reason", "")
            self._store("orders", tool, fields, "ord", record.id)
            data = {"uuid": record.id, "status": "CANCELLED"}
            return data, dict(data)
        if tool == "order_reschedule":
            record = self._tables["orders"].get(str(parsed["order_id"]))
            if record is None:
                return self._domain_error("ORDER_NOT_FOUND", str(parsed["order_id"]))
            if record.fields.get("status") == "CANCELLED":
                return self._domain_error("ORDER_CANCELLED", record.id)
            fields = dict(record.fields)
            fields["date"] = parsed["date"]
            fields["status"] = "RESCHEDULED"
            self._store("orders", tool, fields, "ord", record.id)
            data = {"uuid": record.id, "status": "RESCHEDULED", "date": parsed["date"]}
            return data, {"uuid": record.id, "status": "RESCHEDULED", "date": str(parsed["date"])}
        if tool == "delivery_quote":
            # READ-ONLY and carrying no personal data: a price and a term. It
            # exists so a long conversation has a step whose answer the customer
            # reacts to without the gateway being involved at all.
            weight = int(parsed["weight"])          # type: ignore[arg-type]
            price = 300 + weight // 100 * 7
            data = {"city": parsed["city"], "weight": weight,
                    "price": f"{price}.00", "currency": "RUB", "days": 2 + weight // 20000}
            return data, {"city": str(parsed["city"]), "weight": str(weight),
                          "price": str(data["price"]), "currency": "RUB", "days": str(data["days"])}
        if tool == "pickup_points_near":
            rows = list(self._tables["addresses"].values())
            words = [word for word in str(parsed["address"]).lower().replace(",", " ").split()
                     if len(word) > 2]
            scored = []
            for row in rows:
                haystack = " ".join(str(value).lower() for value in row.fields.values())
                scored.append((sum(1 for word in words if word in haystack), row))
            scored.sort(key=lambda pair: (-pair[0], pair[1].id))
            points = []
            nodes = []
            for index, (hits, row) in enumerate(scored[: int(parsed["limit"])]):  # type: ignore[arg-type]
                # DISTANCE FROM THE SCORE, so a substitute that matches fewer
                # words ranks further away — the effect the family measures.
                metres = 300 + (len(words) - hits) * 900
                points.append({"code": f"PVZ{index + 1:03d}", "address": row.fields["value"],
                               "distance_m": metres})
                nodes.append({"code": f"PVZ{index + 1:03d}",
                              "address": Slot(str(row.fields["value"]), f"p{index}_addr"),
                              "distance_m": str(metres)})
            return {"points": points}, {"points": nodes}
        if tool == "crm_import_csv":
            imported = 0
            for row in parsed["rows"]:  # type: ignore[union-attr]
                self._store("contacts", tool, dict(row), "c")
                imported += 1
            data = {"imported": imported, "rejected": []}
            return data, dict(data)
        raise KeyError(tool)

    # --- what the comparator reads ------------------------------------------

    def snapshot(self) -> tuple[dict[str, object], ...]:
        """Every WRITE, in order, typed. Seeds and lookups are not effects."""
        rows: list[dict[str, object]] = []
        for table in self._tables.values():
            for record in table.values():
                if record.seq == 0:
                    continue
                rows.append({"table": record.table, "id": record.id, "tool": record.tool,
                             "seq": record.seq, "fields": _plain(record.fields)})
        rows.sort(key=lambda row: int(row["seq"]))
        return tuple(rows)

    def refusals(self) -> tuple[Refusal, ...]:
        return tuple(log.refusal for log in self.calls if log.refusal is not None)

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), ensure_ascii=False,
                                         sort_keys=True).encode()).hexdigest()[:16]


def _plain(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _plain(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(inner) for inner in value]
    return value


def main() -> int:
    failures = 0
    backend = Backend("2026-09-02")
    backend.seed_contact("c-77", {"last_name": "громова", "first_name": "марина", "middle_name": "борисовна",
                                  "phone": "+79164021187", "email": "", "birth_date": "1987-03-14",
                                  "address": {"city": "ижевск", "street": "клубная", "house": "85", "flat": "12"}})
    found = backend.call("crm_find_contact", {"query": {"phone": "+79164021187"}})
    if found.refusal or found.result["contacts"][0]["id"] != "c-77":
        failures += 1
        print("FAIL lookup", found)
    if "c0_phone" not in found.result_spans or found.result_text[slice(*found.result_spans["c0_phone"])] != "+79164021187":
        failures += 1
        print("FAIL result spans", found.result_spans)
    update = backend.call("crm_upsert_contact", {"id": "c-77", "contact": {"address": {"city": "Ижевск", "street": "Пушкина", "house": "41", "flat": "7"}}})
    if update.refusal:
        failures += 1
        print("FAIL upsert", update.refusal)
    again = backend.call("crm_find_contact", {"query": {"phone": "+79164021187"}})
    if again.result["contacts"][0]["address"]["street"] != "пушкина":
        failures += 1
        print("FAIL state did not carry", again.result)
    refused = backend.call("notify_sms", {"number": "89164021187", "text": "x"})
    if refused.refusal is None or refused.refusal.rule != "phone_not_e164":
        failures += 1
        print("FAIL refusal", refused)
    snap = backend.snapshot()
    if [row["tool"] for row in snap] != ["crm_upsert_contact"]:
        failures += 1
        print("FAIL snapshot", snap)
    other = Backend("2026-09-02")
    other.seed_contact("c-77", {"phone": "+79164021187"})
    other.call("crm_find_contact", {"query": {"phone": "+79164021187"}})
    other.call("crm_find_contact", {"query": {"phone": "+79164021187"}})   # an extra lookup
    other.call("crm_upsert_contact", {"id": "c-77", "contact": {"address": {"city": "Ижевск", "street": "Пушкина", "house": "41", "flat": "7"}}})
    if [row["id"] for row in other.snapshot()] != ["c-77"]:
        failures += 1
        print("FAIL ids shift with lookups")
    print("mock: PASS" if not failures else f"mock: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
