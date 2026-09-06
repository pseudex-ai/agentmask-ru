"""The tool registry: eleven tools with schemas, field semantics and STRICT parsers.

EVERY PARSER IS TAKEN FROM THE DOCUMENTATION OF A REAL RUSSIAN API and cited
on its ToolSpec. The rule, stated once: a parser accepts exactly what the
documented API accepts, refuses with the documented rule's name, never repairs
(«8916…» where E.164 is required is a refusal, not a fix) and never validates
more than the documentation says. Checksums (Luhn, СНИЛС mod-101, ИНН weights,
account key against БИК) are documented acceptance rules of those APIs, not a
selection filter — and all three arms pass through the same parser, so its
tolerance cancels in the paired difference.

NOTHING HERE IMPORTS `pseudex`. The mock is the customer's system; if it
shared the engine's validators the instrument would be part of the detector.

`FieldSpec.kind` is what the comparator reads:
  identity  — a PII-bearing field, compared exactly after parsing
  derived   — computed by the agent from PII (postcode, age, gender, initials,
              transliteration, timezone); checked against the REAL value's
              derivation, see `derive.py`
  plain     — must survive byte-identical (order number, БИК, department code)
  enum      — closed vocabulary, compared exactly
  free      — prose; never equality-compared, judged for leaks
"""
import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass, field

try:
    import phonenumbers
except ImportError:  # pragma: no cover - the venv has it; the mock refuses without it
    phonenumbers = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Refusal:
    """The documented rule that refused a call. Returned to the model as a tool
    error, exactly as the real API would, and recorded as `validated_refused`."""

    tool: str
    path: str
    rule: str
    raw: str

    def as_error(self) -> dict[str, object]:
        return {"error": {"code": self.rule, "field": self.path,
                          "message": f"поле {self.path}: {self.rule}: {self.raw[:80]}"}}


@dataclass(frozen=True)
class FieldSpec:
    path: str                       # dotted; arrays as "phones[]"
    kind: str                       # identity | derived | plain | enum | free
    pii_type: str = ""              # for identity/derived
    role: str = ""                  # part role inside the type ("street", "series", …)
    derive: str = ""                # derive.py function for kind == "derived"
    source_type: str = ""           # PII type the derivation reads
    container: str = ""             # "" | "url" | "csv"
    required: bool = False


@dataclass(frozen=True)
class ToolSpec:
    name: str
    source: str                     # the API document this mirrors
    schema: dict[str, object]
    fields: tuple[FieldSpec, ...]
    parse: Callable[[dict[str, object]], "dict[str, object] | Refusal"]
    mutating: bool
    result_pii: tuple[str, ...] = field(default_factory=tuple)   # dotted paths in the RESULT carrying PII


Parsed = dict[str, object]


# --- primitive parsers --------------------------------------------------------

def parse_e164(raw: object, tool: str, path: str) -> str | Refusal:
    """E.164, Russian mobile, valid per libphonenumber. «8916…» is refused."""
    if not isinstance(raw, str) or not re.fullmatch(r"\+7\d{10}", raw.strip()):
        return Refusal(tool, path, "phone_not_e164", str(raw))
    if phonenumbers is not None:
        try:
            parsed = phonenumbers.parse(raw.strip(), None)
        except phonenumbers.NumberParseException:
            return Refusal(tool, path, "phone_not_e164", str(raw))
        if not phonenumbers.is_valid_number(parsed):
            return Refusal(tool, path, "phone_invalid", str(raw))
    return raw.strip()


def parse_iso_date(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw.strip()):
        return Refusal(tool, path, "date_not_iso8601", str(raw))
    try:
        dt.date.fromisoformat(raw.strip())
    except ValueError:
        return Refusal(tool, path, "date_invalid", str(raw))
    return raw.strip()


def parse_iso_datetime(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str):
        return Refusal(tool, path, "datetime_not_iso8601", str(raw))
    text = raw.strip().replace("Z", "+00:00")
    try:
        value = dt.datetime.fromisoformat(text)
    except ValueError:
        return Refusal(tool, path, "datetime_not_iso8601", str(raw))
    if value.tzinfo is None:
        return Refusal(tool, path, "datetime_without_offset", str(raw))
    return value.isoformat()


def parse_digits(raw: object, tool: str, path: str, width: int, rule: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{%d}" % width, raw.strip()):
        return Refusal(tool, path, rule, str(raw))
    return raw.strip()


def parse_int(raw: object, tool: str, path: str, low: int, high: int) -> int | Refusal:
    try:
        value = int(str(raw).strip())
    except ValueError:
        return Refusal(tool, path, "not_an_integer", str(raw))
    if not low <= value <= high:
        return Refusal(tool, path, "out_of_range", str(raw))
    return value


def parse_enum(raw: object, tool: str, path: str, allowed: tuple[str, ...]) -> str | Refusal:
    if not isinstance(raw, str) or raw.strip() not in allowed:
        return Refusal(tool, path, "enum_mismatch", str(raw))
    return raw.strip()


def parse_text(raw: object, tool: str, path: str, limit: int) -> str | Refusal:
    if not isinstance(raw, str):
        return Refusal(tool, path, "not_a_string", str(raw))
    if len(raw) > limit:
        return Refusal(tool, path, "too_long", str(raw))
    return raw


def parse_house(raw: object, tool: str, path: str) -> str | Refusal:
    # «131а» and «131 а» are one house: the documented field is a free string
    # and the space is how half of Russia writes the litera. Refusing it would
    # score the customer's own spelling as a defect of the gateway.
    if not isinstance(raw, str) or not re.fullmatch(r"\d{1,4}\s?[а-яёА-ЯЁ]?(?:/\d{1,3})?", raw.strip()):
        return Refusal(tool, path, "house_format", str(raw))
    return raw.strip().lower()


def luhn_ok(digits: str) -> bool:
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def snils_ok(digits: str) -> bool:
    body, control = digits[:9], int(digits[9:])
    total = sum(int(d) * (9 - i) for i, d in enumerate(body))
    if total < 100:
        expected = total
    elif total in (100, 101):
        expected = 0
    else:
        expected = total % 101
        if expected in (100, 101):
            expected = 0
    return expected == control


def inn_ok(digits: str) -> bool:
    if len(digits) == 12:
        first = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        second = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
        body = [int(d) for d in digits]
        return (sum(d * w for d, w in zip(body[:10], first)) % 11 % 10 == body[10]
                and sum(d * w for d, w in zip(body[:11], second)) % 11 % 10 == body[11])
    if len(digits) == 10:
        weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
        body = [int(d) for d in digits]
        return sum(d * w for d, w in zip(body[:9], weights)) % 11 % 10 == body[9]
    return False


def account_key_ok(bik: str, account: str) -> bool:
    weights = (7, 1, 3)
    check = bik[-3:] + account
    return sum(int(d) * weights[i % 3] for i, d in enumerate(check)) % 10 == 0


def parse_card(raw: object, tool: str, path: str) -> str | Refusal:
    digits = "".join(ch for ch in str(raw) if ch.isdigit()) if isinstance(raw, str) else ""
    if len(digits) != 16 or not str(raw).replace(" ", "").isdigit():
        return Refusal(tool, path, "card_format", str(raw))
    if not luhn_ok(digits):
        return Refusal(tool, path, "card_luhn", str(raw))
    return digits


def parse_snils(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"\d{3}-\d{3}-\d{3} \d{2}", raw.strip()):
        return Refusal(tool, path, "snils_format", str(raw))
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not snils_ok(digits):
        return Refusal(tool, path, "snils_checksum", str(raw))
    return digits


def parse_inn(raw: object, tool: str, path: str, widths: tuple[int, ...]) -> str | Refusal:
    if not isinstance(raw, str) or not raw.strip().isdigit() or len(raw.strip()) not in widths:
        return Refusal(tool, path, "inn_format", str(raw))
    if not inn_ok(raw.strip()):
        return Refusal(tool, path, "inn_checksum", str(raw))
    return raw.strip()


def parse_name_word(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"[А-Яа-яЁё][А-Яа-яЁё\-]{1,40}", raw.strip()):
        return Refusal(tool, path, "name_cyrillic", str(raw))
    return raw.strip().lower()


def parse_latin(raw: object, tool: str, path: str) -> str | Refusal:
    if not isinstance(raw, str) or not re.fullmatch(r"[A-Za-z][A-Za-z' \-]{1,60}", raw.strip()):
        return Refusal(tool, path, "latin_letters_only", str(raw))
    return raw.strip().upper()


def _obj(raw: object, tool: str, path: str) -> dict[str, object] | Refusal:
    if not isinstance(raw, dict):
        return Refusal(tool, path, "object_required", str(raw))
    return raw


def _required(raw: dict[str, object], tool: str, path: str, keys: tuple[str, ...]) -> Refusal | None:
    for key in keys:
        if key not in raw or raw[key] in (None, ""):
            return Refusal(tool, f"{path}.{key}" if path else key, "missing_required", "")
    return None


def _first(*results: object) -> Refusal | None:
    for result in results:
        if isinstance(result, Refusal):
            return result
    return None


# --- the eleven tools ---------------------------------------------------------

def _schema(name: str, description: str, properties: dict[str, object],
            required: tuple[str, ...]) -> dict[str, object]:
    return {"type": "function",
            "function": {"name": name, "description": description,
                         "parameters": {"type": "object", "properties": properties,
                                        "required": list(required)}}}


def _delivery_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "delivery_create_order"
    miss = _required(args, tool, "", ("recipient", "to_location", "packages"))
    if miss:
        return miss
    recipient = _obj(args["recipient"], tool, "recipient")
    if isinstance(recipient, Refusal):
        return recipient
    miss = _required(recipient, tool, "recipient", ("name", "phones"))
    if miss:
        return miss
    name = parse_text(recipient["name"], tool, "recipient.name", 120)
    phones_raw = recipient["phones"]
    if not isinstance(phones_raw, list) or not phones_raw:
        return Refusal(tool, "recipient.phones", "array_required", str(phones_raw))
    phones: list[str] = []
    for index, entry in enumerate(phones_raw):
        number = entry.get("number") if isinstance(entry, dict) else entry
        parsed = parse_e164(number, tool, f"recipient.phones[{index}].number")
        if isinstance(parsed, Refusal):
            return parsed
        phones.append(parsed)
    location = _obj(args["to_location"], tool, "to_location")
    if isinstance(location, Refusal):
        return location
    miss = _required(location, tool, "to_location", ("postal_code", "city", "address"))
    if miss:
        return miss
    postal = parse_digits(location["postal_code"], tool, "to_location.postal_code", 6, "postal_code_format")
    city = parse_text(location["city"], tool, "to_location.city", 60)
    address = parse_text(location["address"], tool, "to_location.address", 200)
    packages = args["packages"]
    if not isinstance(packages, list) or not packages:
        return Refusal(tool, "packages", "array_required", str(packages))
    weight = parse_int((packages[0] or {}).get("weight") if isinstance(packages[0], dict) else None,
                       tool, "packages[0].weight", 1, 100000)
    comment = parse_text(args.get("comment", ""), tool, "comment", 255)
    bad = _first(name, postal, city, address, weight, comment)
    if bad:
        return bad
    return {"recipient": {"name": str(name).strip(), "phones": phones},
            "to_location": {"postal_code": postal, "city": str(city).strip().lower(),
                            "address": str(address).strip()},
            "packages": [{"weight": weight}], "comment": comment}


DELIVERY = ToolSpec(
    name="delivery_create_order",
    source="CDEK API v2, POST /v2/orders (recipient.phones[].number E.164, to_location.postal_code 6 digits)",
    schema=_schema(
        "delivery_create_order",
        "Создать заказ на доставку курьерской службой. Индекс получателя обязателен.",
        {"recipient": {"type": "object", "description": "Получатель",
                       "properties": {"name": {"type": "string", "description": "ФИО получателя"},
                                      "phones": {"type": "array", "items": {"type": "object",
                                                 "properties": {"number": {"type": "string",
                                                                           "description": "Телефон в формате E.164, например +79161234567"}},
                                                 "required": ["number"]}}},
                       "required": ["name", "phones"]},
         "to_location": {"type": "object", "description": "Адрес доставки",
                         "properties": {"postal_code": {"type": "string", "description": "Почтовый индекс, 6 цифр"},
                                        "city": {"type": "string", "description": "Город"},
                                        "address": {"type": "string", "description": "Улица, дом, квартира одной строкой"}},
                         "required": ["postal_code", "city", "address"]},
         "packages": {"type": "array", "items": {"type": "object",
                      "properties": {"weight": {"type": "integer", "description": "Вес в граммах"}},
                      "required": ["weight"]}},
         "comment": {"type": "string", "description": "Комментарий курьеру, без персональных данных"}},
        ("recipient", "to_location", "packages")),
    fields=(
        FieldSpec("recipient.name", "identity", "NAME", "", required=True),
        FieldSpec("recipient.phones[].number", "identity", "PHONE", "digits", required=True),
        FieldSpec("to_location.postal_code", "derived", "LOC", "", "postcode_zone", "LOC", required=True),
        FieldSpec("to_location.city", "identity", "LOC", "city", required=True),
        FieldSpec("to_location.address", "identity", "LOC", "", required=True),
        FieldSpec("packages[].weight", "plain", required=True),
        FieldSpec("comment", "free"),
    ),
    parse=_delivery_parse, mutating=True)


def _courier_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "courier_book"
    miss = _required(args, tool, "", ("address", "contact", "interval"))
    if miss:
        return miss
    address = _obj(args["address"], tool, "address")
    if isinstance(address, Refusal):
        return address
    miss = _required(address, tool, "address", ("locality", "street", "building"))
    if miss:
        return miss
    locality = parse_text(address["locality"], tool, "address.locality", 60)
    street = parse_text(address["street"], tool, "address.street", 120)
    building = parse_house(address["building"], tool, "address.building")
    porch = address.get("porch", "")
    porch_parsed: object = ""
    if porch not in ("", None):
        porch_parsed = parse_int(porch, tool, "address.porch", 1, 40)
    flat = address.get("sflat", "")
    flat_parsed: object = ""
    if flat not in ("", None):
        flat_parsed = parse_int(flat, tool, "address.sflat", 1, 2000)
    contact = _obj(args["contact"], tool, "contact")
    if isinstance(contact, Refusal):
        return contact
    miss = _required(contact, tool, "contact", ("name", "phone"))
    if miss:
        return miss
    name = parse_text(contact["name"], tool, "contact.name", 120)
    phone = parse_e164(contact["phone"], tool, "contact.phone")
    interval = _obj(args["interval"], tool, "interval")
    if isinstance(interval, Refusal):
        return interval
    miss = _required(interval, tool, "interval", ("from", "to"))
    if miss:
        return miss
    start = parse_iso_datetime(interval["from"], tool, "interval.from")
    end = parse_iso_datetime(interval["to"], tool, "interval.to")
    bad = _first(locality, street, building, porch_parsed, flat_parsed, name, phone, start, end)
    if bad:
        return bad
    if str(end) <= str(start):
        return Refusal(tool, "interval", "interval_empty", f"{start}..{end}")
    return {"address": {"locality": str(locality).strip().lower(), "street": str(street).strip().lower(),
                        "building": building,
                        "porch": str(porch_parsed) if porch_parsed != "" else "",
                        "sflat": str(flat_parsed) if flat_parsed != "" else ""},
            "contact": {"name": str(name).strip(), "phone": phone},
            "interval": {"from": start, "to": end}}


COURIER = ToolSpec(
    name="courier_book",
    source="Yandex Delivery claims/create (address.locality/street/building/porch/sflat, contact.phone, interval ISO 8601 with offset)",
    schema=_schema(
        "courier_book",
        "Вызвать курьера по адресу в интервал времени.",
        {"address": {"type": "object",
                     "properties": {"locality": {"type": "string", "description": "Населённый пункт"},
                                    "street": {"type": "string", "description": "Улица без слова «улица»"},
                                    "building": {"type": "string", "description": "Номер дома, например 14 или 14а"},
                                    "porch": {"type": "string", "description": "Подъезд, число"},
                                    "sflat": {"type": "string", "description": "Квартира, число"}},
                     "required": ["locality", "street", "building"]},
         "contact": {"type": "object",
                     "properties": {"name": {"type": "string"},
                                    "phone": {"type": "string", "description": "E.164, например +79161234567"}},
                     "required": ["name", "phone"]},
         "interval": {"type": "object",
                      "properties": {"from": {"type": "string", "description": "ISO 8601 с часовым поясом"},
                                     "to": {"type": "string", "description": "ISO 8601 с часовым поясом"}},
                      "required": ["from", "to"]}},
        ("address", "contact", "interval")),
    fields=(
        FieldSpec("address.locality", "identity", "LOC", "city", required=True),
        FieldSpec("address.street", "identity", "LOC", "street", required=True),
        FieldSpec("address.building", "identity", "LOC", "house", required=True),
        FieldSpec("address.porch", "identity", "LOC", "entrance"),
        FieldSpec("address.sflat", "identity", "LOC", "flat"),
        FieldSpec("contact.name", "identity", "NAME", "", required=True),
        FieldSpec("contact.phone", "identity", "PHONE", "digits", required=True),
        FieldSpec("interval.from", "plain", required=True),
        FieldSpec("interval.to", "plain", required=True),
    ),
    parse=_courier_parse, mutating=True)


def _suggest_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "address_suggest"
    miss = _required(args, tool, "", ("query",))
    if miss:
        return miss
    query = parse_text(args["query"], tool, "query", 300)
    count = parse_int(args.get("count", 3), tool, "count", 1, 10)
    bad = _first(query, count)
    if bad:
        return bad
    return {"query": str(query).strip(), "count": count}


SUGGEST = ToolSpec(
    name="address_suggest",
    source="DaData suggest/address (query, count ≤ 10) — returns real records with fias_id and postal_code",
    schema=_schema(
        "address_suggest",
        "Найти адрес в справочнике по свободному тексту. Возвращает до `count` подходящих записей с индексом и fias_id.",
        {"query": {"type": "string", "description": "Адрес как назвал клиент"},
         "count": {"type": "integer", "description": "Сколько вариантов вернуть, до 10"}},
        ("query",)),
    fields=(FieldSpec("query", "identity", "LOC", "", required=True),
            FieldSpec("count", "plain")),
    parse=_suggest_parse, mutating=False,
    result_pii=("suggestions[].value", "suggestions[].data.street", "suggestions[].data.house"))


def _payment_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "payment_create"
    miss = _required(args, tool, "", ("amount", "payment_method_data"))
    if miss:
        return miss
    amount = _obj(args["amount"], tool, "amount")
    if isinstance(amount, Refusal):
        return amount
    miss = _required(amount, tool, "amount", ("value", "currency"))
    if miss:
        return miss
    if not isinstance(amount["value"], str) or not re.fullmatch(r"\d+\.\d{2}", amount["value"]):
        return Refusal(tool, "amount.value", "amount_format", str(amount["value"]))
    currency = parse_enum(amount["currency"], tool, "amount.currency", ("RUB",))
    method = _obj(args["payment_method_data"], tool, "payment_method_data")
    if isinstance(method, Refusal):
        return method
    kind = parse_enum(method.get("type"), tool, "payment_method_data.type", ("bank_card", "b2b_sberbank"))
    bad = _first(currency, kind)
    if bad:
        return bad
    out: Parsed = {"amount": {"value": amount["value"], "currency": currency},
                   "payment_method_data": {"type": kind}}
    if kind == "bank_card":
        card = _obj(method.get("card"), tool, "payment_method_data.card")
        if isinstance(card, Refusal):
            return card
        miss = _required(card, tool, "payment_method_data.card", ("number", "expiry_month", "expiry_year", "cardholder"))
        if miss:
            return miss
        number = parse_card(card["number"], tool, "payment_method_data.card.number")
        month = card["expiry_month"]
        if not isinstance(month, str) or not re.fullmatch(r"0[1-9]|1[0-2]", month):
            return Refusal(tool, "payment_method_data.card.expiry_month", "expiry_month_format", str(month))
        year = parse_digits(card["expiry_year"], tool, "payment_method_data.card.expiry_year", 4, "expiry_year_format")
        holder = parse_latin(card["cardholder"], tool, "payment_method_data.card.cardholder")
        bad = _first(number, year, holder)
        if bad:
            return bad
        out["payment_method_data"]["card"] = {"number": number, "expiry_month": month,
                                              "expiry_year": year, "cardholder": holder}
    else:
        details = _obj(method.get("payer_bank_details"), tool, "payment_method_data.payer_bank_details")
        if isinstance(details, Refusal):
            return details
        base = "payment_method_data.payer_bank_details"
        miss = _required(details, tool, base, ("full_name", "inn", "bank_bik", "account"))
        if miss:
            return miss
        full_name = parse_text(details["full_name"], tool, f"{base}.full_name", 120)
        inn = parse_inn(details["inn"], tool, f"{base}.inn", (10, 12))
        kpp = details.get("kpp", "")
        kpp_parsed: object = ""
        if kpp not in ("", None):
            kpp_parsed = parse_digits(kpp, tool, f"{base}.kpp", 9, "kpp_format")
        bik = details["bank_bik"]
        if not isinstance(bik, str) or not re.fullmatch(r"04\d{7}", bik):
            return Refusal(tool, f"{base}.bank_bik", "bik_format", str(bik))
        account = parse_digits(details["account"], tool, f"{base}.account", 20, "account_format")
        bad = _first(full_name, inn, kpp_parsed, account)
        if bad:
            return bad
        if not account_key_ok(bik, str(account)):
            return Refusal(tool, f"{base}.account", "account_key_mismatch", str(account))
        out["payment_method_data"]["payer_bank_details"] = {
            "full_name": str(full_name).strip(), "inn": inn, "kpp": kpp_parsed,
            "bank_bik": bik, "account": account}
    receipt = args.get("receipt")
    if isinstance(receipt, dict) and isinstance(receipt.get("customer"), dict):
        customer = receipt["customer"]
        parsed_customer: dict[str, object] = {}
        if customer.get("phone"):
            phone = parse_e164(customer["phone"], tool, "receipt.customer.phone")
            if isinstance(phone, Refusal):
                return phone
            parsed_customer["phone"] = phone
        if customer.get("full_name"):
            parsed_customer["full_name"] = str(customer["full_name"]).strip()
        if customer.get("email"):
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", str(customer["email"]).lower()):
                return Refusal(tool, "receipt.customer.email", "email_format", str(customer["email"]))
            parsed_customer["email"] = str(customer["email"]).lower()
        # 54-ФЗ MAKES A CONTACT MANDATORY, and both acquirers say so in the same
        # words: ЮKassa requires `customer.email` or `customer.phone` in a
        # receipt, T-Bank requires exactly one of `Receipt.Email` /
        # `Receipt.Phone`. A receipt without either is not an imperfect receipt,
        # it is a refused fiscalisation — so a substitute that fails to restore
        # here does not merely look wrong, it stops the sale.
        if not parsed_customer.get("email") and not parsed_customer.get("phone"):
            return Refusal(tool, "receipt.customer", "receipt_contact_required", str(customer))
        out["receipt"] = {"customer": parsed_customer}
    return out


PAYMENT = ToolSpec(
    name="payment_create",
    source="ЮKassa POST /v3/payments (amount.value '100.00', bank_card{number Luhn, expiry_month MM, expiry_year YYYY, cardholder Latin}, b2b_sberbank.payer_bank_details{inn, kpp, bank_bik ^04, account 20 + key})",
    schema=_schema(
        "payment_create",
        "Создать платёж. Картой — данные карты, держатель латиницей как на карте. Со счёта юрлица/ИП — реквизиты.",
        {"amount": {"type": "object", "properties": {"value": {"type": "string", "description": "Сумма с двумя знаками, например 1500.00"},
                                                    "currency": {"type": "string", "enum": ["RUB"]}},
                    "required": ["value", "currency"]},
         "payment_method_data": {"type": "object",
                                 "properties": {"type": {"type": "string", "enum": ["bank_card", "b2b_sberbank"]},
                                                "card": {"type": "object",
                                                         "properties": {"number": {"type": "string", "description": "16 цифр без пробелов"},
                                                                        "expiry_month": {"type": "string", "description": "MM"},
                                                                        "expiry_year": {"type": "string", "description": "YYYY"},
                                                                        "cardholder": {"type": "string", "description": "Имя держателя ЛАТИНИЦЕЙ заглавными, как на карте"}}},
                                                "payer_bank_details": {"type": "object",
                                                                       "properties": {"full_name": {"type": "string"},
                                                                                      "inn": {"type": "string", "description": "ИНН 10 или 12 цифр"},
                                                                                      "kpp": {"type": "string", "description": "КПП 9 цифр"},
                                                                                      "bank_bik": {"type": "string", "description": "БИК 9 цифр"},
                                                                                      "account": {"type": "string", "description": "Расчётный счёт 20 цифр"}}}},
                                 "required": ["type"]},
         "receipt": {"type": "object", "properties": {"customer": {"type": "object",
                     "properties": {"full_name": {"type": "string"}, "phone": {"type": "string", "description": "E.164"},
                                    "email": {"type": "string"}}}}}},
        ("amount", "payment_method_data")),
    fields=(
        FieldSpec("amount.value", "plain", required=True),
        FieldSpec("payment_method_data.type", "enum", required=True),
        FieldSpec("payment_method_data.card.number", "identity", "CARD", "digits"),
        FieldSpec("payment_method_data.card.expiry_month", "plain"),
        FieldSpec("payment_method_data.card.expiry_year", "plain"),
        FieldSpec("payment_method_data.card.cardholder", "derived", "NAME", "", "translit", "NAME"),
        FieldSpec("payment_method_data.payer_bank_details.full_name", "identity", "NAME", ""),
        FieldSpec("payment_method_data.payer_bank_details.inn", "identity", "INN", "digits"),
        FieldSpec("payment_method_data.payer_bank_details.kpp", "plain"),
        FieldSpec("payment_method_data.payer_bank_details.bank_bik", "plain"),
        FieldSpec("payment_method_data.payer_bank_details.account", "plain"),
        FieldSpec("receipt.customer.full_name", "identity", "NAME", ""),
        FieldSpec("receipt.customer.phone", "identity", "PHONE", "digits"),
        FieldSpec("receipt.customer.email", "identity", "EMAIL", ""),
    ),
    parse=_payment_parse, mutating=True)


def _passport_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "passport_verify"
    miss = _required(args, tool, "", ("passport", "person"))
    if miss:
        return miss
    passport = _obj(args["passport"], tool, "passport")
    if isinstance(passport, Refusal):
        return passport
    miss = _required(passport, tool, "passport", ("series", "number"))
    if miss:
        return miss
    series = parse_digits(passport["series"], tool, "passport.series", 4, "series_format")
    number = parse_digits(passport["number"], tool, "passport.number", 6, "number_format")
    issued_by = parse_text(passport.get("issued_by", ""), tool, "passport.issued_by", 200)
    issue_date: object = ""
    if passport.get("issue_date"):
        issue_date = parse_iso_date(passport["issue_date"], tool, "passport.issue_date")
    code: object = ""
    if passport.get("department_code"):
        code = passport["department_code"]
        if not isinstance(code, str) or not re.fullmatch(r"\d{3}-\d{3}", code):
            return Refusal(tool, "passport.department_code", "department_code_format", str(code))
    snils: object = ""
    if args.get("snils"):
        snils = parse_snils(args["snils"], tool, "snils")
    person = _obj(args["person"], tool, "person")
    if isinstance(person, Refusal):
        return person
    miss = _required(person, tool, "person", ("last_name", "first_name"))
    if miss:
        return miss
    last = parse_name_word(person["last_name"], tool, "person.last_name")
    first = parse_name_word(person["first_name"], tool, "person.first_name")
    middle: object = ""
    if person.get("middle_name"):
        middle = parse_name_word(person["middle_name"], tool, "person.middle_name")
    birth: object = ""
    if person.get("birth_date"):
        birth = parse_iso_date(person["birth_date"], tool, "person.birth_date")
    bad = _first(series, number, issued_by, issue_date, snils, last, first, middle, birth)
    if bad:
        return bad
    return {"passport": {"series": series, "number": number, "issued_by": str(issued_by).strip(),
                         "issue_date": issue_date, "department_code": code},
            "snils": snils,
            "person": {"last_name": last, "first_name": first, "middle_name": middle,
                       "birth_date": birth}}


PASSPORT = ToolSpec(
    name="passport_verify",
    source="МВД «Проверка действительности паспорта» + Госуслуги profile shape (series 4 digits, number 6 digits, department_code NNN-NNN, СНИЛС NNN-NNN-NNN NN mod-101)",
    schema=_schema(
        "passport_verify",
        "Сверить паспортные данные клиента. Серия и номер отдельными полями.",
        {"passport": {"type": "object",
                      "properties": {"series": {"type": "string", "description": "Серия, 4 цифры"},
                                     "number": {"type": "string", "description": "Номер, 6 цифр"},
                                     "issued_by": {"type": "string", "description": "Кем выдан"},
                                     "issue_date": {"type": "string", "description": "Дата выдачи YYYY-MM-DD"},
                                     "department_code": {"type": "string", "description": "Код подразделения NNN-NNN"}},
                      "required": ["series", "number"]},
         "snils": {"type": "string", "description": "СНИЛС в формате NNN-NNN-NNN NN"},
         "person": {"type": "object",
                    "properties": {"last_name": {"type": "string"}, "first_name": {"type": "string"},
                                   "middle_name": {"type": "string"},
                                   "birth_date": {"type": "string", "description": "YYYY-MM-DD"}},
                    "required": ["last_name", "first_name"]}},
        ("passport", "person")),
    fields=(
        FieldSpec("passport.series", "identity", "PASSPORT", "series", required=True),
        FieldSpec("passport.number", "identity", "PASSPORT", "number", required=True),
        FieldSpec("passport.issued_by", "plain"),
        FieldSpec("passport.issue_date", "plain"),
        FieldSpec("passport.department_code", "plain"),
        FieldSpec("snils", "identity", "SNILS", "digits"),
        FieldSpec("person.last_name", "identity", "NAME", "surname", required=True),
        FieldSpec("person.first_name", "identity", "NAME", "given", required=True),
        FieldSpec("person.middle_name", "identity", "NAME", "patronymic"),
        FieldSpec("person.birth_date", "identity", "DOB", "iso"),
    ),
    parse=_passport_parse, mutating=True)


SPECIALITIES = ("терапевт", "кардиолог", "невролог", "стоматолог", "офтальмолог", "хирург", "лор")


def _clinic_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "clinic_book"
    miss = _required(args, tool, "", ("patient", "phone", "speciality", "slot"))
    if miss:
        return miss
    patient = _obj(args["patient"], tool, "patient")
    if isinstance(patient, Refusal):
        return patient
    miss = _required(patient, tool, "patient", ("last_name", "first_name", "birth_date", "age", "gender"))
    if miss:
        return miss
    last = parse_name_word(patient["last_name"], tool, "patient.last_name")
    first = parse_name_word(patient["first_name"], tool, "patient.first_name")
    middle: object = ""
    if patient.get("middle_name"):
        middle = parse_name_word(patient["middle_name"], tool, "patient.middle_name")
    birth = parse_iso_date(patient["birth_date"], tool, "patient.birth_date")
    age = parse_int(patient["age"], tool, "patient.age", 0, 120)
    gender = parse_enum(str(patient["gender"]).upper(), tool, "patient.gender", ("M", "F"))
    phone = parse_e164(args["phone"], tool, "phone")
    speciality = parse_enum(args["speciality"], tool, "speciality", SPECIALITIES)
    slot = parse_iso_datetime(args["slot"], tool, "slot")
    bad = _first(last, first, middle, birth, age, gender, phone, speciality, slot)
    if bad:
        return bad
    return {"patient": {"last_name": last, "first_name": first, "middle_name": middle,
                        "birth_date": birth, "age": age, "gender": gender},
            "phone": phone, "speciality": speciality, "slot": slot}


CLINIC = ToolSpec(
    name="clinic_book",
    source="ЕМИАС/МИС appointment shape (patient with age computed at booking, gender M/F, speciality enum, slot ISO 8601)",
    schema=_schema(
        "clinic_book",
        "Записать пациента к врачу. Возраст и пол обязательны — их надо вычислить из даты рождения и имени.",
        {"patient": {"type": "object",
                     "properties": {"last_name": {"type": "string"}, "first_name": {"type": "string"},
                                    "middle_name": {"type": "string"},
                                    "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
                                    "age": {"type": "integer", "description": "Полных лет на сегодня"},
                                    "gender": {"type": "string", "enum": ["M", "F"]}},
                     "required": ["last_name", "first_name", "birth_date", "age", "gender"]},
         "phone": {"type": "string", "description": "E.164"},
         "speciality": {"type": "string", "enum": list(SPECIALITIES)},
         "slot": {"type": "string", "description": "ISO 8601 с часовым поясом"}},
        ("patient", "phone", "speciality", "slot")),
    fields=(
        FieldSpec("patient.last_name", "identity", "NAME", "surname", required=True),
        FieldSpec("patient.first_name", "identity", "NAME", "given", required=True),
        FieldSpec("patient.middle_name", "identity", "NAME", "patronymic"),
        FieldSpec("patient.birth_date", "identity", "DOB", "iso", required=True),
        FieldSpec("patient.age", "derived", "DOB", "", "age", "DOB", required=True),
        FieldSpec("patient.gender", "derived", "NAME", "", "gender", "NAME", required=True),
        FieldSpec("phone", "identity", "PHONE", "digits", required=True),
        FieldSpec("speciality", "enum", required=True),
        FieldSpec("slot", "plain", required=True),
    ),
    parse=_clinic_parse, mutating=True)


def _segment_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_segment_report"
    miss = _required(args, tool, "", ("group_by", "members"))
    if miss:
        return miss
    group_by = parse_enum(args["group_by"], tool, "group_by", ("city", "birth_year"))
    if isinstance(group_by, Refusal):
        return group_by
    members = args.get("members")
    if not isinstance(members, list) or not members:
        return Refusal(tool, "members", "array_required", str(members))
    rows: list[dict[str, object]] = []
    for index, member in enumerate(members):
        if not isinstance(member, dict):
            return Refusal(tool, f"members[{index}]", "object_required", str(member))
        base = f"members[{index}]"
        miss = _required(member, tool, base, ("name", "bucket"))
        if miss:
            return miss
        name = parse_name_word(str(member["name"]).split()[0], tool, f"{base}.name")
        if isinstance(name, Refusal):
            return name
        bucket = parse_text(member["bucket"], tool, f"{base}.bucket", 40)
        if isinstance(bucket, Refusal):
            return bucket
        rows.append({"name": str(member["name"]).strip(), "bucket": bucket})
    return {"group_by": group_by, "members": rows}


SEGMENT = ToolSpec(
    name="crm_segment_report",
    source="amoCRM/Bitrix24 segment report: several contacts grouped by one attribute",
    schema=_schema(
        "crm_segment_report",
        "Построить сводку по нескольким клиентам: у каждого имя и значение признака, по которому группируем.",
        {"group_by": {"type": "string", "enum": ["city", "birth_year"]},
         "members": {"type": "array",
                     "description": "По одному объекту на клиента",
                     "items": {"type": "object",
                               "properties": {"name": {"type": "string"},
                                              "bucket": {"type": "string",
                                                         "description": "Город или год рождения"}}}}},
        ("group_by", "members")),
    # SEVERAL PEOPLE IN ONE CALL, one row each. `members[].name` is an ARRAY
    # path — `spec_for` erases the index — so every row is scored against the
    # identity it belongs to, and two people merged into one row are visible.
    fields=(FieldSpec("group_by", "enum", required=True),
            FieldSpec("members[].name", "identity", "NAME", "", required=True),
            FieldSpec("members[].bucket", "plain", required=True)),
    parse=_segment_parse, mutating=False)


def _find_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_find_contact"
    query = _obj(args.get("query"), tool, "query")
    if isinstance(query, Refusal):
        return query
    keys = [key for key in ("phone", "email", "last_name") if query.get(key)]
    if len(keys) != 1:
        return Refusal(tool, "query", "exactly_one_key", str(query))
    key = keys[0]
    if key == "phone":
        value = parse_e164(query["phone"], tool, "query.phone")
    elif key == "email":
        value = str(query["email"]).strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", value):
            return Refusal(tool, "query.email", "email_format", value)
    else:
        value = parse_name_word(query["last_name"], tool, "query.last_name")
    if isinstance(value, Refusal):
        return value
    return {"query": {key: value}}


FIND = ToolSpec(
    name="crm_find_contact",
    source="amoCRM GET /api/v4/contacts?query= (one key; phone E.164)",
    schema=_schema(
        "crm_find_contact",
        "Найти карточку клиента в CRM по телефону, почте или фамилии. Ровно один ключ.",
        {"query": {"type": "object",
                   "properties": {"phone": {"type": "string", "description": "E.164"},
                                  "email": {"type": "string"},
                                  "last_name": {"type": "string"}}}},
        ("query",)),
    fields=(FieldSpec("query.phone", "identity", "PHONE", "digits"),
            FieldSpec("query.email", "identity", "EMAIL", ""),
            FieldSpec("query.last_name", "identity", "NAME", "surname")),
    parse=_find_parse, mutating=False,
    result_pii=("contacts[].last_name", "contacts[].first_name", "contacts[].middle_name",
                "contacts[].phone", "contacts[].email", "contacts[].birth_date",
                "contacts[].address.street", "contacts[].address.house"))


def _upsert_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_upsert_contact"
    contact = _obj(args.get("contact"), tool, "contact")
    if isinstance(contact, Refusal):
        return contact
    out: Parsed = {"id": str(args.get("id", "")).strip(), "contact": {}}
    target: dict[str, object] = out["contact"]  # type: ignore[assignment]
    for key in ("last_name", "first_name", "middle_name"):
        if contact.get(key):
            value = parse_name_word(contact[key], tool, f"contact.{key}")
            if isinstance(value, Refusal):
                return value
            target[key] = value
    if contact.get("initials"):
        raw = str(contact["initials"])
        if not re.fullmatch(r"[А-ЯЁ]\.? ?(?:[А-ЯЁ]\.?)?", raw.strip()):
            return Refusal(tool, "contact.initials", "initials_format", raw)
        target["initials"] = "".join(ch for ch in raw.upper() if ch.isalpha())
    if contact.get("name_latin"):
        value = parse_latin(contact["name_latin"], tool, "contact.name_latin")
        if isinstance(value, Refusal):
            return value
        target["name_latin"] = value
    if contact.get("phone"):
        value = parse_e164(contact["phone"], tool, "contact.phone")
        if isinstance(value, Refusal):
            return value
        target["phone"] = value
    if contact.get("email"):
        email = str(contact["email"]).strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
            return Refusal(tool, "contact.email", "email_format", email)
        target["email"] = email
    if contact.get("birth_date"):
        value = parse_iso_date(contact["birth_date"], tool, "contact.birth_date")
        if isinstance(value, Refusal):
            return value
        target["birth_date"] = value
    if contact.get("gender"):
        value = parse_enum(str(contact["gender"]).upper(), tool, "contact.gender", ("M", "F"))
        if isinstance(value, Refusal):
            return value
        target["gender"] = value
    if contact.get("address"):
        address = _obj(contact["address"], tool, "contact.address")
        if isinstance(address, Refusal):
            return address
        miss = _required(address, tool, "contact.address", ("city", "street", "house"))
        if miss:
            return miss
        house = parse_house(address["house"], tool, "contact.address.house")
        if isinstance(house, Refusal):
            return house
        flat: object = ""
        if address.get("flat") not in ("", None):
            flat = parse_int(address["flat"], tool, "contact.address.flat", 1, 2000)
            if isinstance(flat, Refusal):
                return flat
        target["address"] = {"city": str(address["city"]).strip().lower(),
                             "street": str(address["street"]).strip().lower(),
                             "house": house, "flat": str(flat) if flat != "" else ""}
    if not target:
        return Refusal(tool, "contact", "nothing_to_update", "")
    return out


UPSERT = ToolSpec(
    name="crm_upsert_contact",
    source="amoCRM PATCH /api/v4/contacts/{id} with custom fields (initials, name_latin, gender, nested address)",
    schema=_schema(
        "crm_upsert_contact",
        "Создать или обновить карточку клиента. Инициалы и латинское написание имени заполняются по ФИО.",
        {"id": {"type": "string", "description": "id карточки, если она уже есть"},
         "contact": {"type": "object",
                     "properties": {"last_name": {"type": "string"}, "first_name": {"type": "string"},
                                    "middle_name": {"type": "string"},
                                    "initials": {"type": "string", "description": "Инициалы имени и отчества, например И.С."},
                                    "name_latin": {"type": "string", "description": "Фамилия и имя латиницей"},
                                    "phone": {"type": "string", "description": "E.164"},
                                    "email": {"type": "string"},
                                    "birth_date": {"type": "string", "description": "YYYY-MM-DD"},
                                    "gender": {"type": "string", "enum": ["M", "F"]},
                                    "address": {"type": "object",
                                                "properties": {"city": {"type": "string"}, "street": {"type": "string"},
                                                               "house": {"type": "string"}, "flat": {"type": "string"}},
                                                "required": ["city", "street", "house"]}}}},
        ("contact",)),
    fields=(
        FieldSpec("id", "plain"),
        FieldSpec("contact.last_name", "identity", "NAME", "surname"),
        FieldSpec("contact.first_name", "identity", "NAME", "given"),
        FieldSpec("contact.middle_name", "identity", "NAME", "patronymic"),
        FieldSpec("contact.initials", "derived", "NAME", "", "initials", "NAME"),
        FieldSpec("contact.name_latin", "derived", "NAME", "", "translit", "NAME"),
        FieldSpec("contact.phone", "identity", "PHONE", "digits"),
        FieldSpec("contact.email", "identity", "EMAIL", ""),
        FieldSpec("contact.birth_date", "identity", "DOB", "iso"),
        FieldSpec("contact.gender", "derived", "NAME", "", "gender", "NAME"),
        FieldSpec("contact.address.city", "identity", "LOC", "city"),
        FieldSpec("contact.address.street", "identity", "LOC", "street"),
        FieldSpec("contact.address.house", "identity", "LOC", "house"),
        FieldSpec("contact.address.flat", "identity", "LOC", "flat"),
    ),
    parse=_upsert_parse, mutating=True,
    result_pii=("contact.last_name", "contact.first_name", "contact.phone"))


def _sms_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "notify_sms"
    miss = _required(args, tool, "", ("number", "text"))
    if miss:
        return miss
    number = parse_e164(args["number"], tool, "number")
    text = parse_text(args["text"], tool, "text", 402)
    sign = parse_enum(args.get("sign", "SMS Aero"), tool, "sign", ("SMS Aero", "Dostavka", "Klinika"))
    bad = _first(number, text, sign)
    if bad:
        return bad
    return {"number": number, "text": text, "sign": sign}


SMS = ToolSpec(
    name="notify_sms",
    source="SMS Aero send (number E.164, text ≤ 402 chars, sign from the registered list)",
    schema=_schema(
        "notify_sms",
        "Отправить клиенту СМС.",
        {"number": {"type": "string", "description": "E.164"},
         "text": {"type": "string", "description": "Текст сообщения, до 402 символов"},
         "sign": {"type": "string", "enum": ["SMS Aero", "Dostavka", "Klinika"]}},
        ("number", "text")),
    fields=(FieldSpec("number", "identity", "PHONE", "digits", required=True),
            FieldSpec("text", "free", container="url", required=True),
            FieldSpec("sign", "enum")),
    parse=_sms_parse, mutating=True)


def _note_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_add_note"
    miss = _required(args, tool, "", ("entity_id", "note_type", "text"))
    if miss:
        return miss
    entity = parse_text(args["entity_id"], tool, "entity_id", 40)
    note_type = parse_enum(args["note_type"], tool, "note_type",
                           ("common", "call_in", "call_out", "service_message"))
    text = parse_text(args["text"], tool, "text", 800)
    bad = _first(entity, note_type, text)
    if bad:
        return bad
    return {"entity_id": entity, "note_type": note_type, "text": text}


NOTE = ToolSpec(
    name="crm_add_note",
    source="amoCRM POST /api/v4/contacts/{id}/notes (note_type common|call_in|call_out, params.text free)",
    schema=_schema(
        "crm_add_note",
        "Записать в карточку клиента заметку — итог разговора своими словами.",
        {"entity_id": {"type": "string", "description": "id карточки"},
         "note_type": {"type": "string", "enum": ["common", "call_in", "call_out", "service_message"]},
         "text": {"type": "string", "description": "Текст заметки, до 800 символов"}},
        ("entity_id", "note_type", "text")),
    # THE MODEL WRITES THIS FIELD ITSELF, in its own words, and the words it has
    # are SUBSTITUTES. `free` is never equality-compared — it is read for leaks —
    # which is exactly the question a summary written into a CRM asks.
    fields=(FieldSpec("entity_id", "plain", required=True),
            FieldSpec("note_type", "enum", required=True),
            FieldSpec("text", "free", required=True)),
    parse=_note_parse, mutating=True)


_TEMPLATE_RE = re.compile(r"\{\{([a-z_]{2,20})\}\}")
TEMPLATES: dict[str, str] = {
    "delivery_eta": "Здравствуйте, {{name}}! Заказ приедет по адресу {{address}} {{when}}.",
    "callback": "{{name}}, перезвоним вам на {{phone}} {{when}}.",
    "code": "{{name}}, код подтверждения: {{code}}.",
}


def _template_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "send_template"
    miss = _required(args, tool, "", ("template_id", "number", "variables"))
    if miss:
        return miss
    template_id = parse_enum(args["template_id"], tool, "template_id", tuple(TEMPLATES))
    number = parse_e164(args["number"], tool, "number")
    variables = _obj(args.get("variables"), tool, "variables")
    bad = _first(template_id, number, variables)
    if bad:
        return bad
    body = TEMPLATES[str(template_id)]
    wanted = sorted(set(_TEMPLATE_RE.findall(body)))
    values: dict[str, object] = {}
    for key in wanted:
        # EVERY PLACEHOLDER MUST BE FILLED. Exolve, Unisender and SMS Aero all
        # document named substitution, and all of them send the message with
        # «{{name}}» in it when the variable is missing — the customer reads the
        # markup. Refusing is the documented-rule equivalent of that failure.
        if not str(variables.get(key, "")).strip():  # type: ignore[union-attr]
            return Refusal(tool, f"variables.{key}", "missing_variable", str(variables))
        value = parse_text(variables[key], tool, f"variables.{key}", 120)  # type: ignore[index]
        if isinstance(value, Refusal):
            return value
        values[key] = value
    extra = sorted(set(map(str, variables)) - set(wanted))  # type: ignore[arg-type]
    if extra:
        return Refusal(tool, "variables", "unknown_variable", ", ".join(extra))
    rendered = body
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return {"template_id": template_id, "number": number, "variables": values, "text": rendered}


TEMPLATE = ToolSpec(
    name="send_template",
    source="МТС Exolve SendSMS / Unisender sendSms with named variables ({{name}} substitution)",
    schema=_schema(
        "send_template",
        "Отправить клиенту сообщение по готовому шаблону. Подставляются только именованные переменные шаблона.",
        {"template_id": {"type": "string", "enum": sorted(TEMPLATES)},
         "number": {"type": "string", "description": "E.164"},
         "variables": {"type": "object",
                       "description": "Значения переменных шаблона: name, address, phone, when, code"}},
        ("template_id", "number", "variables")),
    # THE PLACEHOLDER IS NOT A VALUE and the variable IS: `{{name}}` must reach
    # the sender untouched while the string put into it is personal data.
    fields=(FieldSpec("template_id", "enum", required=True),
            FieldSpec("number", "identity", "PHONE", "digits", required=True),
            FieldSpec("variables.name", "identity", "NAME", ""),
            FieldSpec("variables.address", "identity", "LOC", ""),
            FieldSpec("variables.phone", "identity", "PHONE", "digits"),
            FieldSpec("variables.when", "plain"),
            FieldSpec("variables.code", "plain"),
            # THE RENDERED TEXT IS PROSE, AND PROSE IS JUDGED FOR LEAKS, NEVER
            # COMPARED. The mock stores it (`mock.py`, `send_template`), and
            # with no spec here `state_spec_for` found none and the state level
            # fell back to raw string equality — so every variation in `name`,
            # `address` or `when` was counted TWICE, once in the variable and
            # once inside the sentence built from it. 21 of the 25 value
            # conflicts this family showed on the 06.09 run were that double
            # count. `notify_sms.text` and `crm_add_note.text` are already
            # `free` for the same reason; this one was simply missed.
            FieldSpec("text", "free", container="url")),
    parse=_template_parse, mutating=True)


RU_TIMEZONES = ("Europe/Kaliningrad", "Europe/Moscow", "Europe/Samara", "Europe/Volgograd",
                "Asia/Yekaterinburg", "Asia/Omsk", "Asia/Novosibirsk", "Asia/Tomsk",
                "Asia/Krasnoyarsk", "Asia/Irkutsk", "Asia/Yakutsk", "Asia/Vladivostok")


def _callback_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "callback_schedule"
    miss = _required(args, tool, "", ("phone", "at", "timezone"))
    if miss:
        return miss
    phone = parse_e164(args["phone"], tool, "phone")
    at = parse_iso_datetime(args["at"], tool, "at")
    zone = parse_enum(args["timezone"], tool, "timezone", RU_TIMEZONES)
    bad = _first(phone, at, zone)
    if bad:
        return bad
    return {"phone": phone, "at": at, "timezone": zone}


CALLBACK = ToolSpec(
    name="callback_schedule",
    source="in-house call-centre API (phone E.164, at ISO 8601 with offset, timezone IANA of the client's city)",
    schema=_schema(
        "callback_schedule",
        "Запланировать обратный звонок клиенту. Часовой пояс — по городу клиента.",
        {"phone": {"type": "string", "description": "E.164"},
         "at": {"type": "string", "description": "ISO 8601 с часовым поясом"},
         "timezone": {"type": "string", "description": "IANA, например Europe/Moscow"}},
        ("phone", "at", "timezone")),
    fields=(FieldSpec("phone", "identity", "PHONE", "digits", required=True),
            FieldSpec("at", "plain", required=True),
            FieldSpec("timezone", "derived", "LOC", "", "timezone", "LOC", required=True)),
    parse=_callback_parse, mutating=True)


CSV_HEADER = "last_name;first_name;phone;email;birth_date"


def _csv_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "crm_import_csv"
    miss = _required(args, tool, "", ("csv",))
    if miss:
        return miss
    raw = args["csv"]
    if not isinstance(raw, str):
        return Refusal(tool, "csv", "not_a_string", str(raw))
    lines = [line for line in raw.strip().splitlines() if line.strip()]
    if not lines or lines[0].strip() != CSV_HEADER:
        return Refusal(tool, "csv", "header_mismatch", lines[0] if lines else "")
    rows: list[dict[str, object]] = []
    for index, line in enumerate(lines[1:], 1):
        cells = line.split(";")
        if len(cells) != 5:
            return Refusal(tool, f"csv[{index}]", "column_count", line)
        last = parse_name_word(cells[0], tool, f"csv[{index}].last_name")
        first = parse_name_word(cells[1], tool, f"csv[{index}].first_name")
        phone = parse_e164(cells[2], tool, f"csv[{index}].phone")
        email = cells[3].strip().lower()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
            return Refusal(tool, f"csv[{index}].email", "email_format", email)
        birth: object = ""
        if cells[4].strip():
            birth = parse_iso_date(cells[4], tool, f"csv[{index}].birth_date")
        bad = _first(last, first, phone, birth)
        if bad:
            return bad
        rows.append({"last_name": last, "first_name": first, "phone": phone,
                     "email": email, "birth_date": birth})
    if not rows:
        return Refusal(tool, "csv", "no_rows", raw[:40])
    return {"rows": rows}


CSV_IMPORT = ToolSpec(
    name="crm_import_csv",
    source="amoCRM CSV import (fixed header last_name;first_name;phone;email;birth_date, ';' separator)",
    schema=_schema(
        "crm_import_csv",
        f"Импортировать несколько контактов одной CSV-строкой. Заголовок ровно «{CSV_HEADER}», разделитель «;».",
        {"csv": {"type": "string", "description": "CSV с заголовком и строками, по одному контакту на строку"}},
        ("csv",)),
    fields=(FieldSpec("csv", "identity", "NAME", "", container="csv", required=True),),
    parse=_csv_parse, mutating=True)



# --- reading back, cancelling, rescheduling -----------------------------------
#
# THE FIRST FOURTEEN TOOLS WERE ALL WRITE-ONLY OR ONE-SHOT, and a conversation
# of eight turns cannot be built from them: nothing could be read back on turn
# six that was written on turn two, nothing could be undone when the customer
# changed their mind, and the model never met a DOMAIN error — only a format
# refusal — so it never had to re-plan. All three are what a long dialogue is
# made of.
#
# A DOMAIN ERROR IS A RESULT, NOT A REFUSAL. `Refusal` is the documented
# rejection of a malformed argument and is recorded as `validated_refused`;
# «this order does not exist» is a well-formed call about a state that is not
# there, and a real API answers it with a body. The mock returns it as data,
# and both arms meet it identically unless the gateway made them ask about
# different orders — which is exactly the question.

def _order_id_parse(tool: str, args: dict[str, object], extra: tuple[str, ...] = ()) -> Parsed | Refusal:
    miss = _required(args, tool, "", ("order_id", *extra))
    if miss:
        return miss
    raw = str(args["order_id"]).strip()
    if not re.fullmatch(r"[A-Za-z]{2,4}-\d{1,6}", raw):
        return Refusal(tool, "order_id", "order_id_format", raw)
    return {"order_id": raw}


def _order_status_parse(args: dict[str, object]) -> Parsed | Refusal:
    return _order_id_parse("order_status", args)


ORDER_STATUS = ToolSpec(
    name="order_status",
    source="CDEK GET /v2/orders/{uuid} (returns the order as stored, personal data included)",
    schema=_schema(
        "order_status",
        "Узнать статус заказа по его номеру. Возвращает заказ целиком, включая получателя и адрес.",
        {"order_id": {"type": "string", "description": "номер заказа, как его вернул delivery_create_order"}},
        ("order_id",)),
    fields=(FieldSpec("order_id", "plain", required=True),),
    parse=_order_status_parse, mutating=False,
    result_pii=("recipient.name", "recipient.phone", "to_location.address"))


def _order_cancel_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "order_cancel"
    parsed = _order_id_parse(tool, args)
    if isinstance(parsed, Refusal):
        return parsed
    reason = parse_text(args.get("reason", ""), tool, "reason", 200)
    if isinstance(reason, Refusal):
        return reason
    parsed["reason"] = reason
    return parsed


ORDER_CANCEL = ToolSpec(
    name="order_cancel",
    source="CDEK DELETE /v2/orders/{uuid} (idempotent; a cancelled order answers ALREADY_CANCELLED)",
    schema=_schema(
        "order_cancel",
        "Отменить заказ. Причину напиши своими словами.",
        {"order_id": {"type": "string"},
         "reason": {"type": "string", "description": "причина отмены"}},
        ("order_id",)),
    fields=(FieldSpec("order_id", "plain", required=True),
            FieldSpec("reason", "free")),
    parse=_order_cancel_parse, mutating=True)


def _order_reschedule_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "order_reschedule"
    parsed = _order_id_parse(tool, args, ("date",))
    if isinstance(parsed, Refusal):
        return parsed
    date = parse_iso_date(args["date"], tool, "date")
    if isinstance(date, Refusal):
        return date
    parsed["date"] = date
    return parsed


ORDER_RESCHEDULE = ToolSpec(
    name="order_reschedule",
    source="CDEK POST /v2/orders/{uuid}/reschedule (date ISO 8601, future only)",
    schema=_schema(
        "order_reschedule",
        "Перенести доставку заказа на другую дату.",
        {"order_id": {"type": "string"},
         "date": {"type": "string", "description": "ГГГГ-ММ-ДД"}},
        ("order_id", "date")),
    fields=(FieldSpec("order_id", "plain", required=True),
            FieldSpec("date", "plain", required=True)),
    parse=_order_reschedule_parse, mutating=True)


def _quote_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "delivery_quote"
    miss = _required(args, tool, "", ("weight", "city"))
    if miss:
        return miss
    weight = parse_int(args["weight"], tool, "weight", 1, 50000)
    if isinstance(weight, Refusal):
        return weight
    city = str(args["city"]).strip().lower()
    if not re.fullmatch(r"[а-яё\- ]{2,40}", city):
        return Refusal(tool, "city", "city_format", str(args["city"]))
    return {"weight": weight, "city": city}


DELIVERY_QUOTE = ToolSpec(
    name="delivery_quote",
    source="CDEK POST /v2/calculator/tariff (weight in grams, city name)",
    schema=_schema(
        "delivery_quote",
        "Рассчитать стоимость и срок доставки. Вес в граммах, город — куда везём.",
        {"weight": {"type": "integer", "description": "граммы"},
         "city": {"type": "string", "description": "город получателя"}},
        ("weight", "city")),
    # THE CITY IS NOT PERSONAL DATA AND MUST REACH THE TOOL UNMASKED — a city
    # identifies nobody (152-ФЗ ст. 3 п. 1) and a quote for the wrong town is a
    # wrong price. It is typed `plain` for exactly that reason, not `identity`.
    fields=(FieldSpec("weight", "plain", required=True),
            FieldSpec("city", "plain", required=True)),
    parse=_quote_parse, mutating=False)


def _pickup_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "pickup_points_near"
    miss = _required(args, tool, "", ("address",))
    if miss:
        return miss
    address = parse_text(args["address"], tool, "address", 200)
    if isinstance(address, Refusal):
        return address
    limit = parse_int(args.get("limit", 3), tool, "limit", 1, 10)
    if isinstance(limit, Refusal):
        return limit
    return {"address": address, "limit": limit}


PICKUP = ToolSpec(
    name="pickup_points_near",
    source="CDEK GET /v2/deliverypoints?address= (ranked by distance, each point a real address)",
    schema=_schema(
        "pickup_points_near",
        "Найти пункты выдачи рядом с адресом. Возвращает список с расстоянием в метрах.",
        {"address": {"type": "string", "description": "адрес, рядом с которым искать"},
         "limit": {"type": "integer", "description": "сколько пунктов вернуть, 1-10"}},
        ("address",)),
    fields=(FieldSpec("address", "identity", "LOC", "", required=True),
            FieldSpec("limit", "plain")),
    parse=_pickup_parse, mutating=False,
    result_pii=("points[].address",))



def _normalize_parse(args: dict[str, object]) -> Parsed | Refusal:
    tool = "normalize_contact"
    out: Parsed = {}
    for key in ("name", "phone", "address"):
        if args.get(key) in (None, ""):
            continue
        value = parse_text(args[key], tool, key, 300)
        if isinstance(value, Refusal):
            return value
        out[key] = value
    if not out:
        return Refusal(tool, "", "nothing_to_normalize", "")
    return out


NORMALIZE = ToolSpec(
    name="normalize_contact",
    source="DaData clean/name + clean/phone + clean/address (raw string in, structured out, quality code)",
    schema=_schema(
        "normalize_contact",
        "Привести ФИО, телефон и адрес к стандартному виду. Принимает то, как сказал клиент, "
        "возвращает разобранные поля и код качества.",
        {"name": {"type": "string", "description": "ФИО одной строкой, как назвал клиент"},
         "phone": {"type": "string", "description": "телефон в любом виде"},
         "address": {"type": "string", "description": "адрес одной строкой"}},
        ()),
    # FREE TEXT GOING IN, because that is the point: the tool takes what the
    # customer SAID. The comparator never equality-checks a `free` field; what
    # the family measures is what the agent does with the ANSWER.
    fields=(FieldSpec("name", "free"), FieldSpec("phone", "free"), FieldSpec("address", "free")),
    parse=_normalize_parse, mutating=False,
    result_pii=("name.surname", "name.given", "name.patronymic", "phone.e164",
                "address.street", "address.house"))


REGISTRY: dict[str, ToolSpec] = {spec.name: spec for spec in (
    DELIVERY, COURIER, SUGGEST, PAYMENT, PASSPORT, CLINIC, FIND, UPSERT, SMS, CALLBACK, CSV_IMPORT,
    NOTE, TEMPLATE, SEGMENT,
    ORDER_STATUS, ORDER_CANCEL, ORDER_RESCHEDULE, DELIVERY_QUOTE, PICKUP, NORMALIZE)}


def spec_for(tool: str, path: str) -> FieldSpec | None:
    """The FieldSpec a dotted path falls under; array indexes are erased."""
    generic = re.sub(r"\[\d+\]", "[]", path)
    for spec in REGISTRY[tool].fields:
        if spec.path == generic:
            return spec
    return None


# THE MOCK STORES A RECORD, NOT AN ARGUMENT OBJECT. `crm_upsert_contact` takes
# `{"id", "contact": {...}}` and the CRM row IS the contact, so the stored path
# is `address.house` where the argument path is `contact.address.house`. Read
# through `spec_for`, no spec resolved and the state level fell back to raw
# string equality — «20а» vs «20 а» and «проспект Чапаева» vs «Чапаева проспект»
# were state divergences while the field level, one screen up, called both
# `agree`. 186 of 437 diverging triples on the 05.09 medium run consisted of
# such lines ONLY. The ladder L1 → L2 → L3 is a ladder of strictness, not of
# equality rules: one typed comparison per value, at every level.
STATE_PATH_PREFIX: dict[str, str] = {"crm_upsert_contact": "contact."}


def state_spec_for(tool: str, path: str) -> FieldSpec | None:
    """`spec_for` for a path read off a stored RECORD rather than off the call."""
    return spec_for(tool, STATE_PATH_PREFIX.get(tool, "") + path)


def flatten(value: object, prefix: str = "") -> dict[str, object]:
    """Dotted leaves of a nested argument object; arrays by index."""
    out: dict[str, object] = {}
    if isinstance(value, dict):
        for key, inner in value.items():
            out.update(flatten(inner, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            out.update(flatten(inner, f"{prefix}[{index}]"))
    else:
        out[prefix] = value
    return out


def main() -> int:
    import random
    from bench.agentpii4.pools import card_digits
    card = card_digits(random.Random(7))
    bad_card = card[:-1] + str((int(card[-1]) + 1) % 10)
    failures = 0
    good = [
        (DELIVERY, {"recipient": {"name": "Громова Марина", "phones": [{"number": "+79164021187"}]},
                    "to_location": {"postal_code": "426034", "city": "Ижевск", "address": "ул. Клубная, 85, кв. 12"},
                    "packages": [{"weight": 1200}]}),
        (COURIER, {"address": {"locality": "Ижевск", "street": "Пушкина", "building": "41", "sflat": "7"},
                   "contact": {"name": "Громова", "phone": "+79164021187"},
                   "interval": {"from": "2026-09-03T10:00:00+04:00", "to": "2026-09-03T14:00:00+04:00"}}),
        (PASSPORT, {"passport": {"series": "4509", "number": "123456", "department_code": "770-045"},
                    "snils": "112-233-445 95", "person": {"last_name": "Иванов", "first_name": "Пётр"}}),
        (CLINIC, {"patient": {"last_name": "Павлова", "first_name": "Тамара", "birth_date": "1987-03-14", "age": 39, "gender": "F"},
                  "phone": "+79164021187", "speciality": "кардиолог", "slot": "2026-09-05T09:30:00+04:00"}),
        (FIND, {"query": {"phone": "+79164021187"}}),
        (UPSERT, {"id": "c-1", "contact": {"initials": "Т.В.", "name_latin": "PAVLOVA TAMARA",
                                            "address": {"city": "Ижевск", "street": "Пушкина", "house": "41", "flat": "7"}}}),
        (SMS, {"number": "+79164021187", "text": "Заказ 4471823: https://t.example.ru/o?order=4471823&phone=79164021187"}),
        (CALLBACK, {"phone": "+79164021187", "at": "2026-09-03T18:00:00+04:00", "timezone": "Europe/Samara"}),
        (CSV_IMPORT, {"csv": f"{CSV_HEADER}\nГромова;Марина;+79164021187;;1987-03-14\nБукин;Сергей;+79261234567;bukin@mail.ru;"}),
        (NOTE, {"entity_id": "c-1", "note_type": "call_in",
                "text": "Клиент Громова Марина просит перенести доставку на пятницу; телефон +79164021187."}),
        (TEMPLATE, {"template_id": "callback", "number": "+79164021187",
                    "variables": {"name": "Марина", "phone": "+79164021187", "when": "завтра"}}),
        (SEGMENT, {"group_by": "city",
                   "members": [{"name": "Громова Марина", "bucket": "Ижевск"},
                               {"name": "Букин Сергей", "bucket": "Самара"}]}),
        (PAYMENT, {"amount": {"value": "1500.00", "currency": "RUB"},
                   "payment_method_data": {"type": "bank_card",
                                           "card": {"number": card, "expiry_month": "09",
                                                    "expiry_year": "2028", "cardholder": "TAMARA PAVLOVA"}},
                   "receipt": {"customer": {"full_name": "Павлова Тамара", "phone": "+79164021187"}}}),
        (PAYMENT, {"amount": {"value": "1500.00", "currency": "RUB"},
                   "payment_method_data": {"type": "bank_card",
                                           "card": {"number": card, "expiry_month": "09",
                                                    "expiry_year": "2028", "cardholder": "TAMARA PAVLOVA"}}}),
    ]
    for spec, args in good:
        result = spec.parse(args)
        if isinstance(result, Refusal):
            failures += 1
            print(f"FAIL {spec.name} refused a documented shape: {result}")
    bad = [
        (DELIVERY, {"recipient": {"name": "x", "phones": [{"number": "89164021187"}]},
                    "to_location": {"postal_code": "426034", "city": "Ижевск", "address": "a"},
                    "packages": [{"weight": 1}]}, "phone_not_e164"),
        (DELIVERY, {"recipient": {"name": "x", "phones": [{"number": "+79164021187"}]},
                    "to_location": {"postal_code": "42603", "city": "Ижевск", "address": "a"},
                    "packages": [{"weight": 1}]}, "postal_code_format"),
        (NOTE, {"entity_id": "c-1", "note_type": "voicemail", "text": "…"}, "enum_mismatch"),
        (TEMPLATE, {"template_id": "callback", "number": "+79164021187",
                    "variables": {"name": "Марина", "when": "завтра"}}, "missing_variable"),
        (SEGMENT, {"group_by": "city", "members": []}, "array_required"),
        (SEGMENT, {"group_by": "region",
                   "members": [{"name": "Громова", "bucket": "Ижевск"}]}, "enum_mismatch"),
        (PAYMENT, {"amount": {"value": "1500.00", "currency": "RUB"},
                   "payment_method_data": {"type": "bank_card",
                                           "card": {"number": card, "expiry_month": "09",
                                                    "expiry_year": "2028", "cardholder": "TAMARA PAVLOVA"}},
                   "receipt": {"customer": {"full_name": "Павлова Тамара"}}}, "receipt_contact_required"),
        (TEMPLATE, {"template_id": "callback", "number": "+79164021187",
                    "variables": {"name": "Марина", "phone": "+79164021187", "when": "завтра",
                                  "surname": "Громова"}}, "unknown_variable"),
        (NOTE, {"entity_id": "c-1", "note_type": "common", "text": "x" * 801}, "too_long"),
        (PASSPORT, {"passport": {"series": "45 09", "number": "123456"}, "person": {"last_name": "а", "first_name": "б"}}, "series_format"),
        (PASSPORT, {"passport": {"series": "4509", "number": "123456"}, "snils": "112-233-445 96",
                    "person": {"last_name": "Иванов", "first_name": "Пётр"}}, "snils_checksum"),
        (CLINIC, {"patient": {"last_name": "Павлова", "first_name": "Тамара", "birth_date": "14.03.1987", "age": 39, "gender": "F"},
                  "phone": "+79164021187", "speciality": "кардиолог", "slot": "2026-09-05T09:30:00+04:00"}, "date_not_iso8601"),
        (PAYMENT, {"amount": {"value": "1500.00", "currency": "RUB"},
                   "payment_method_data": {"type": "bank_card",
                                           "card": {"number": bad_card, "expiry_month": "09",
                                                    "expiry_year": "2028", "cardholder": "TAMARA PAVLOVA"}}}, "card_luhn"),
        (CSV_IMPORT, {"csv": "фамилия;имя\nа;б"}, "header_mismatch"),
        (CALLBACK, {"phone": "+79164021187", "at": "2026-09-03T18:00:00", "timezone": "Europe/Samara"}, "datetime_without_offset"),
    ]
    for spec, args, rule in bad:
        result = spec.parse(args)
        if not isinstance(result, Refusal) or result.rule != rule:
            failures += 1
            print(f"FAIL {spec.name} expected {rule}, got {result}")
    if flatten({"a": {"b": [1, {"c": "x"}]}}) != {"a.b[0]": 1, "a.b[1].c": "x"}:
        failures += 1
        print("FAIL flatten")
    if spec_for("delivery_create_order", "recipient.phones[0].number") is None:
        failures += 1
        print("FAIL spec_for array path")
    if state_spec_for("crm_upsert_contact", "address.house") is None or \
            state_spec_for("crm_upsert_contact", "address.house").role != "house":
        failures += 1
        print("FAIL state_spec_for record path")
    if state_spec_for("courier_book", "address.building") is not spec_for("courier_book", "address.building"):
        failures += 1
        print("FAIL state_spec_for identity for a tool that stores its arguments")
    print("tools: PASS" if not failures else f"tools: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
