"""A scripted agent and a fake gateway, so the rig is tested before it costs money.

The scripted agent is NOT a model of the model. It is a set of POLICIES, each
a deliberate exaggeration of one thing a real agent does — copies verbatim,
decomposes into fields, derives a postcode from the city it read, validates a
checksum and refuses, swaps a person, embeds a phone in a URL — so that every
verdict of the taxonomy can be produced on demand and checked against an
expectation. Level A runs it through `FakeGateway` (deterministic substitutes,
no engine); `smoke.py --engine` runs the same policies through `RealGateway`.

The agent reads what the gateway hands it: the real values in the control
arms, the substitutes in the intervention arm — never the case's ground truth
directly. That is the whole point: an agent that reads the answer key cannot
test whether the answer survives the gateway.
"""
import json
import functools
import random
import re
from dataclasses import dataclass

from bench.agentpii4 import derive, pools
from bench.agentpii4.compare import ArmRun, ObservedCall
from bench.agentpii4.mock import Backend
from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import Case, message_text
from bench.agentpii4.tools import CSV_HEADER, REGISTRY, flatten


@dataclass(frozen=True)
class Policy:
    name: str
    decomposes: bool = True          # fill role fields from parts, else whole values
    reformats_phone: bool = True     # write E.164 (else write as read)
    derives: bool = True             # compute postcode/age/gender/initials/translit
    validates_checksum: bool = False # refuse to call when a checksum fails
    drops_optional: bool = False     # leave optional fields empty
    swaps_person: bool = False       # use another identity's value where two exist
    noise: float = 0.0               # probability of skipping a call (C′ floor)
    seed: int = 0


import pymorphy3  # noqa: E402
_MORPH = pymorphy3.MorphAnalyzer()


POLICIES: dict[str, Policy] = {
    "copier": Policy("copier", decomposes=False, reformats_phone=False, derives=False),
    "decomposer": Policy("decomposer"),
    "deriver": Policy("deriver", derives=True),
    "validator": Policy("validator", validates_checksum=True),
    "sloppy": Policy("sloppy", drops_optional=True, swaps_person=True),
    "noisy": Policy("noisy", noise=0.3),
}


class FakeGateway:
    """Level A: format-preserving substitutes from a fixed pool, no engine.

    Deterministic per case, gender-preserving for names, checksum-INVALID for
    digits, a different city for addresses — the shape the real vault mints,
    so the scripted agent meets the same provocations."""

    def __init__(self, case: Case, resolve_pieces: bool = True) -> None:
        self._case = case
        self._rng = random.Random(f"fake:{case.id}")
        self._map: dict[str, str] = {}      # real -> fake
        self._back: dict[str, str] = {}     # fake -> real
        self._seen: dict[str, str] = {}
        self._resolve_pieces = resolve_pieces
        for item in case.pii:
            if item.value not in self._map:
                fake = self._mint(item.type, item.value, item.parts)
                self._map[item.value] = fake
                # Restored to the CANONICAL, as the engine does on the tool leg
                # (`_pick_value`): a dictated phone comes back as +7…, not as the
                # words it was said in.
                self._back[fake] = item.canonical if item.type in ("PHONE", "SNILS", "INN", "CARD", "PASSPORT", "DOB", "EMAIL") else item.value
                if self._resolve_pieces:
                    for role, part in parts_of(item.type, fake).items():
                        real_part = item.parts.get(role, "")
                        if part and real_part and part not in self._back:
                            self._back[part] = real_part
            self._seen[item.id] = self._map[item.value]
        self._conversation = case.conversation_id or "fake"

    def _mint(self, kind: str, value: str, parts: dict[str, str]) -> str:
        rng = self._rng
        if kind == "NAME":
            pool = pools.FEMALE if parts.get("gender") == "f" else pools.MALE
            person = rng.choice(pool)
            words = value.split()
            fake = [person.surname[0], person.given[0], person.patronymic[0]][:len(words)]
            return " ".join(word.capitalize() for word in fake)
        if kind == "PHONE":
            return "+7999" + "".join(str(rng.randrange(10)) for _ in range(7))
        if kind == "LOC":
            city = rng.choice(("Тверь", "Тула", "Псков"))
            street = rng.choice(("Ивовая", "Кленовая", "Речная", "Луговая"))
            house = rng.randrange(1, 150)
            out = f"{city}, улица {street} {house}" if "city" in parts else f"улица {street} {house}"
            if "flat" in parts:
                out += f", кв. {rng.randrange(1, 200)}"
            if "entrance" in parts:
                out += f", подъезд {rng.randrange(1, 9)}"
            return out
        if kind in ("SNILS", "INN", "CARD", "PASSPORT"):
            digits = "".join(str(rng.randrange(10)) for _ in range(len(re.sub(r"\D", "", value)) or 10))
            if kind == "PASSPORT":
                return f"{digits[:4]} {digits[4:10]}"
            if kind == "SNILS":
                return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:11]}"
            return digits
        if kind == "DOB":
            return f"{rng.randrange(1, 28):02d}.{rng.randrange(1, 13):02d}.{rng.randrange(1960, 2000)}"
        if kind == "EMAIL":
            return f"user{rng.randrange(100, 999)}@example.ru"
        return value

    @property
    def conversation_id(self) -> str:
        return self._conversation

    def tools(self) -> list[dict[str, object]]:
        return [dict(REGISTRY[name].schema) for name in self._case.tools]

    def _mask(self, text: str) -> str:
        for real, fake in sorted(self._map.items(), key=lambda pair: -len(pair[0])):
            text = text.replace(real, fake)
        return text

    def push_system(self, text: str) -> str:
        return text

    def push_user(self, index: int) -> str:
        return self._mask(message_text(self._case, index))

    def push_tool(self, name: str, text: str) -> str:
        return self._mask(text)

    def note(self, text: str) -> None:
        return None

    def note_tool_call(self, name: str, arguments: dict[str, object]) -> None:
        return None

    def _restore(self, text: str) -> str:
        """A whole value is restored wherever it stands; a PIECE only when it is
        the whole leaf. «12» as a substring of «712» is not the house."""
        if text in self._back:
            return self._back[text]
        for fake in sorted(self._map.values(), key=len, reverse=True):
            if fake in text:
                text = text.replace(fake, self._back[fake])
        return text

    def restore_arguments(self, arguments: dict[str, object]) -> tuple[dict[str, object], dict[str, tuple[str, ...]]]:
        def walk(node: object) -> object:
            if isinstance(node, str):
                return self._restore(node)
            if isinstance(node, list):
                return [walk(one) for one in node]
            if isinstance(node, dict):
                return {key: walk(value) for key, value in node.items()}
            return node
        restored = walk(arguments)
        residual: dict[str, tuple[str, ...]] = {}
        markers = set(self._map.values())
        if not self._resolve_pieces:
            for fake in self._map.values():
                markers.update(part for part in parts_of_any(fake) if len(part) > 2)
        for path, value in flatten(restored).items():
            if isinstance(value, str):
                left = tuple(fake for fake in markers if fake and fake.casefold() in value.casefold())
                if left:
                    residual[path] = left
        return restored, residual  # type: ignore[return-value]

    def restore_text(self, text: str) -> str:
        return self._restore(text)

    def substitutes_seen(self) -> dict[str, str]:
        return dict(self._seen)

    def substitutes(self) -> tuple[str, ...]:
        return tuple(sorted(self._map.values()))

    @property
    def faults(self) -> tuple[str, ...]:
        return ()


def parts_of_any(fake: str) -> tuple[str, ...]:
    out: list[str] = []
    for kind in ("LOC", "NAME", "PASSPORT"):
        out.extend(value for value in parts_of(kind, fake).values() if value)
    return tuple(out)


# --- the scripted agent ------------------------------------------------------

def _seen_values(case: Case, gateway: object) -> dict[str, tuple[str, dict[str, str]]]:
    """item id -> (what the agent reads, its parts as the agent would split them).

    A NAME IS WRITTEN INTO A FIELD IN THE NOMINATIVE, as a model writes it: the
    live controls put «Марина» into `contact.name` for «на имя марину» (every
    `compare` triple of both live runs). The scripted control copied the
    oblique surface verbatim, so «сергея» met the gateway's «сергей» and 28 of
    42 `compare` triples disagreed on the instrument's own habit, not on the
    engine. The corpus canonical IS the nominative of what was written; for a
    substitute the agent reads, the nominative comes from morphology, which is
    what a model does with a name it has never seen."""
    seen = gateway.substitutes_seen()  # type: ignore[attr-defined]
    out: dict[str, tuple[str, dict[str, str]]] = {}
    for item in case.pii:
        surface = seen.get(item.id, item.value)
        if item.type == "NAME":
            if surface == item.value:
                surface, parts = item.canonical, dict(item.parts)
            else:
                surface = _nominative_name(surface)
                parts = parts_of(item.type, surface)
        else:
            parts = parts_of(item.type, surface) if surface != item.value else dict(item.parts)
        out[item.id] = (surface, parts)
    return out


@functools.lru_cache(maxsize=4096)
def _nominative_name(surface: str) -> str:
    """The name in the nominative, read the way a Russian speaker reads it:
    ONE gender and case for the whole phrase, every word agreeing. Word by
    word, «Щукину Анну» gave «Щукин Анна» — the surname's dative reading of a
    man outscored its accusative reading of a woman, and the instrument wrote
    a person the gateway had never minted. pymorphy3 directly — the instrument
    must not borrow the engine's reading of a name, or it could not disagree
    with it."""
    words = surface.split()
    parsed = []
    for word in words:
        parses = [p for p in _MORPH.parse(word)
                  if {"Surn", "Name", "Patr"} & set(p.tag.grammemes) and p.tag.gender in ("masc", "femn")
                  and p.tag.case and p.tag.number != "plur"]
        parsed.append(parses)
    readings = None
    for parses in parsed:
        if not parses:
            continue
        pairs = {(p.tag.gender, p.tag.case) for p in parses}
        readings = pairs if readings is None else readings & pairs
    best: tuple[str, str] | None = None
    if readings:
        def score(pair: tuple[str, str]) -> float:
            return sum(max((p.score for p in parses if (p.tag.gender, p.tag.case) == pair), default=0.0)
                       for parses in parsed)
        best = max(readings, key=score)
    out: list[str] = []
    for word, parses in zip(words, parsed):
        chosen = None
        if best is not None:
            chosen = next((p for p in sorted(parses, key=lambda p: -p.score)
                           if (p.tag.gender, p.tag.case) == best), None)
        if chosen is None and parses:
            chosen = max(parses, key=lambda p: p.score)
        if chosen is None:
            out.append(word)
            continue
        form = chosen.inflect({"nomn"}) if chosen.tag.case != "nomn" else None
        nominative = form.word if form is not None else word
        out.append(nominative.capitalize() if word[:1].isupper() else nominative)
    return " ".join(out)


def _pick(case: Case, kind: str, view: dict[str, tuple[str, dict[str, str]]],
          policy: Policy, prefer_current: bool = True) -> tuple[str, dict[str, str]]:
    """The agent's choice of which item of a type to use."""
    items = [item for item in case.pii if item.type == kind and item.where.kind == "message"]
    if not items:
        items = [item for item in case.pii if item.type == kind]
    if not items:
        return "", {}
    current = [item for item in items if not item.stale] or items
    chosen = current[-1] if prefer_current else current[0]
    if policy.swaps_person and len({item.identity for item in current}) > 1:
        chosen = [item for item in current if item.identity != chosen.identity][0]
    return view[chosen.id]


def _e164(surface: str, parts: dict[str, str], policy: Policy) -> str:
    digits = _digits_of(surface, parts)
    if not policy.reformats_phone:
        return surface
    if len(digits) >= 10:
        return f"+7{digits[-10:]}"
    return surface


def _digits_of(surface: str, parts: dict[str, str]) -> str:
    """Digits as the agent reads them: from the parts when the value was built
    (a real, possibly spoken value), from the string when it is a substitute."""
    if parts.get("digits"):
        return parts["digits"]
    if parts.get("series") and parts.get("number"):
        return parts["series"] + parts["number"]
    return re.sub(r"\D", "", surface)


def _checksum_ok(kind: str, surface: str, parts: dict[str, str]) -> bool:
    from bench.agentpii4.tools import inn_ok, luhn_ok, snils_ok
    digits = _digits_of(surface, parts)
    if kind == "SNILS":
        return len(digits) == 11 and snils_ok(digits)
    if kind == "INN":
        return inn_ok(digits)
    if kind == "CARD":
        return len(digits) == 16 and luhn_ok(digits)
    return True


def _as_digits(part: str) -> str:
    """A number field gets digits, as a model fills a form: «двадцать три» -> 23.
    Anything the numeral parser does not know is written as read."""
    if not part or any(ch.isdigit() for ch in part):
        return part
    words = tuple(word for word in re.findall(r"[а-яё]+", part.lower()))
    try:
        return pools.parse_numerals(words) or part
    except (KeyError, ValueError):
        return part


def _address_args(surface: str, parts: dict[str, str], policy: Policy) -> dict[str, str]:
    if not policy.decomposes:
        return {"street": surface, "house": "", "flat": ""}
    return {"street": parts.get("street", surface), "house": _as_digits(parts.get("house", "")),
            "flat": _as_digits(parts.get("flat", "")), "entrance": _as_digits(parts.get("entrance", "")),
            "city": parts.get("city", "")}


def _name_args(surface: str, parts: dict[str, str], policy: Policy) -> dict[str, str]:
    if not policy.decomposes:
        return {"last": surface, "first": "", "middle": ""}
    return {"last": parts.get("surname", surface.split()[0] if surface else ""),
            "first": parts.get("given", ""), "middle": parts.get("patronymic", "")}


def plan_calls(case: Case, gateway: object, policy: Policy, rng: random.Random,
               ) -> list[tuple[str, dict[str, object]]]:
    """The calls the scripted agent makes for this case, from what it READS."""
    view = _seen_values(case, gateway)
    calls: list[tuple[str, dict[str, object]]] = []
    tools = case.expects.reachable_tools

    def maybe(name: str, args: dict[str, object]) -> None:
        if rng.random() < policy.noise:
            return
        calls.append((name, args))

    name_surface, name_parts = _pick(case, "NAME", view, policy)
    phone_surface, phone_parts = _pick(case, "PHONE", view, policy)
    addr_surface, addr_parts = _pick(case, "LOC", view, policy)
    dob_surface, dob_parts = _pick(case, "DOB", view, policy)
    phone = _e164(phone_surface, phone_parts, policy) if phone_surface else ""
    name = _name_args(name_surface, name_parts, policy)
    address = _address_args(addr_surface, addr_parts, policy)
    city = address.get("city") or _city_of(case)

    if "crm_find_contact" in tools and phone:
        maybe("crm_find_contact", {"query": {"phone": phone}})
    if "crm_upsert_contact" in tools:
        contact: dict[str, object] = {}
        if name["last"]:
            contact["last_name"] = name["last"]
        if name["first"]:
            contact["first_name"] = name["first"]
        if name["middle"]:
            contact["middle_name"] = name["middle"]
        if policy.derives and name["first"]:
            options = derive.initials({"given": name["first"], "patronymic": name["middle"]})
            contact["initials"] = next((one for one in sorted(options) if re.fullmatch(r"[А-ЯЁ]\.(?:[А-ЯЁ]\.)?", one)), "И.")
            contact["name_latin"] = " ".join(derive.translit_icao(word) for word in (name["last"], name["first"]) if word).upper()
            gender = derive.gender({"given": name["first"], "surname": name["last"], "patronymic": name["middle"]})
            contact["gender"] = "F" if "female" in gender else "M"
        if phone:
            contact["phone"] = phone
        if address["street"]:
            contact["address"] = {"city": city, "street": address["street"], "house": address["house"] or "1",
                                  "flat": address["flat"]}
        maybe("crm_upsert_contact", {"id": "c-1" if case.seed_records else "", "contact": contact})
    if "delivery_create_order" in tools and phone:
        # The last three digits are the agent's invention; seeded by the CASE so
        # two control arms of a deterministic agent agree and the noise floor
        # measures the policy's noise, not this line.
        tail = random.Random(f"postcode:{case.id}:{city}").randrange(100, 999)
        postal = f"{sorted(derive.postcode_zone(city))[0]}{tail:03d}" if (policy.derives and derive.postcode_zone(city)) else "000000"
        maybe("delivery_create_order", {
            "recipient": {"name": name_surface, "phones": [{"number": phone}]},
            "to_location": {"postal_code": postal, "city": city, "address": addr_surface},
            "packages": [{"weight": 1000}]})
    if "courier_book" in tools and phone:
        maybe("courier_book", {
            "address": {"locality": city, "street": address["street"], "building": address["house"] or "1",
                        "porch": "" if policy.drops_optional else address.get("entrance", ""),
                        "sflat": "" if policy.drops_optional else address["flat"]},
            "contact": {"name": name_surface, "phone": phone},
            "interval": {"from": "2026-09-03T10:00:00+04:00", "to": "2026-09-03T14:00:00+04:00"}})
    if "address_suggest" in tools:
        maybe("address_suggest", {"query": addr_surface, "count": 3})
    if "passport_verify" in tools:
        pp_surface, pp_parts = _pick(case, "PASSPORT", view, policy)
        sn_surface, sn_parts = _pick(case, "SNILS", view, policy)
        if policy.validates_checksum and sn_surface and not _checksum_ok("SNILS", sn_surface, sn_parts):
            pass   # the validating agent refuses to call
        else:
            digits = _digits_of(pp_surface, pp_parts)
            sn_digits = _digits_of(sn_surface, sn_parts)
            args: dict[str, object] = {
                "passport": {"series": digits[:4], "number": digits[4:10]},
                "person": {"last_name": name["last"], "first_name": name["first"] or "Имя",
                           "middle_name": name["middle"]}}
            if sn_digits:
                args["snils"] = f"{sn_digits[:3]}-{sn_digits[3:6]}-{sn_digits[6:9]} {sn_digits[9:11]}"
            plain = [one.value for one in case.plain]
            code = next((one for one in plain if re.fullmatch(r"\d{3}-\d{3}", one)), "")
            if code:
                args["passport"]["department_code"] = code  # type: ignore[index]
            issued = next((one for one in plain if "уфмс" in one or "мвд" in one), "")
            if issued:
                args["passport"]["issued_by"] = issued  # type: ignore[index]
            maybe("passport_verify", args)
    if "clinic_book" in tools and phone:
        iso = dob_parts.get("iso", "")
        age = sorted(derive.age(iso, case.now))[0] if (policy.derives and iso) else "0"
        gender = derive.gender({"given": name["first"], "surname": name["last"], "patronymic": name["middle"]}) if policy.derives else frozenset({"male"})
        maybe("clinic_book", {
            "patient": {"last_name": name["last"], "first_name": name["first"] or "Имя",
                        "middle_name": name["middle"], "birth_date": iso or "1990-01-01",
                        "age": int(age), "gender": "F" if "female" in gender else "M"},
            "phone": phone, "speciality": "терапевт", "slot": "2026-09-05T09:30:00+04:00"})
    if "payment_create" in tools:
        card_surface, card_parts = _pick(case, "CARD", view, policy)
        digits = _digits_of(card_surface, card_parts)
        if policy.validates_checksum and card_surface and not _checksum_ok("CARD", card_surface, card_parts):
            pass
        elif digits:
            holder = " ".join(derive.translit_icao(word) for word in (name["first"], name["last"]) if word).upper() if policy.derives else "CARD HOLDER"
            maybe("payment_create", {
                "amount": {"value": "780.00", "currency": "RUB"},
                "payment_method_data": {"type": "bank_card",
                                        "card": {"number": digits, "expiry_month": "09", "expiry_year": "2028",
                                                 "cardholder": holder or "CARD HOLDER"}}})
    if "callback_schedule" in tools and phone:
        zone = sorted(derive.timezone(city))[0] if (policy.derives and derive.timezone(city)) else "Europe/Moscow"
        maybe("callback_schedule", {"phone": phone, "at": "2026-09-03T18:00:00+04:00", "timezone": zone})
    if "crm_import_csv" in tools:
        rows = []
        people = [item for item in case.pii if item.type == "NAME" and item.where.kind == "message"]
        phones = [item for item in case.pii if item.type == "PHONE" and item.where.kind == "message"]
        for person, ph in zip(people, phones):
            n_surface, n_parts = view[person.id]
            p_surface, p_parts = view[ph.id]
            parts = _name_args(n_surface, n_parts, Policy("x"))
            rows.append(f"{parts['last']};{parts['first']};{_e164(p_surface, p_parts, Policy('x'))};;")
        if rows:
            maybe("crm_import_csv", {"csv": "\n".join([CSV_HEADER, *rows])})
    if "notify_sms" in tools and phone:
        order = next((one.value for one in case.plain if one.family == "order_number"), "")
        text = f"Ваш заказ {order or 'оформлен'}"
        if order:
            text += f": https://t.example.ru/o?order={re.sub(r'[^0-9]', '', order) or order}&phone={re.sub(r'[^0-9]', '', phone)}"
        maybe("notify_sms", {"number": phone, "text": text[:400]})
    return calls


def _city_of(case: Case) -> str:
    for item in case.pii:
        if item.type == "LOC" and item.parts.get("city"):
            return item.parts["city"]
    for record in case.seed_records:
        address = record.fields.get("address")
        if isinstance(address, dict) and address.get("city"):
            return str(address["city"])
    return "москва"


def scripted_run(case: Case, arm: str, repeat: int, gateway: object, backend: Backend,
                 policy: Policy) -> ArmRun:
    """Drive one arm with the scripted agent through the same MCP-shaped path
    the live harness uses: restore -> backend.call -> serialise -> push_tool."""
    rng = random.Random(f"{policy.name}:{case.id}:{arm}:{repeat}:{policy.seed}")
    gateway.push_system(case.messages[0].content)  # type: ignore[attr-defined]
    for index, message in enumerate(case.messages):
        if message.role == "user":
            gateway.push_user(index)  # type: ignore[attr-defined]
    calls: list[ObservedCall] = []
    for seq, (name, arguments) in enumerate(plan_calls(case, gateway, policy, rng), 1):
        gateway.note_tool_call(name, arguments)  # type: ignore[attr-defined]
        restored, residual = gateway.restore_arguments(arguments)  # type: ignore[attr-defined]
        log = backend.call(name, restored)
        gateway.push_tool(name, log.result_text)  # type: ignore[attr-defined]
        calls.append(ObservedCall(
            name=name, written=arguments, restored=restored, residual=residual,
            refusal_path=log.refusal.path if log.refusal else "",
            refusal_rule=log.refusal.rule if log.refusal else "",
            parsed=log.parsed, seq=seq))
    name_surface, _ = _pick(case, "NAME", _seen_values(case, gateway), policy)
    reply_raw = f"Готово. Записал: {name_surface}." if name_surface else "Готово."
    reply = gateway.restore_text(reply_raw)  # type: ignore[attr-defined]
    gateway.note(reply_raw)  # type: ignore[attr-defined]
    substitutes = {}
    if arm == "I":
        seen = gateway.substitutes_seen()  # type: ignore[attr-defined]
        substitutes = {item.id: (seen[item.id], parts_of(item.type, seen[item.id]))
                       for item in case.pii if item.id in seen}
    return ArmRun(case_id=case.id, arm=arm, repeat=repeat, calls=tuple(calls),
                  state=backend.snapshot(), reply=reply, termination="done", cost_usd=0.0,
                  substitutes=substitutes)


def seed_backend(case: Case) -> Backend:
    backend = Backend(case.now)
    for record in case.seed_records:
        if record.table == "contacts":
            backend.seed_contact(record.id, dict(record.fields))
        else:
            backend.seed_address(record.id, dict(record.fields))
    return backend


def main() -> int:
    from bench.agentpii4.build import build_corpus
    cases = build_corpus()
    case = next(one for one in cases if one.kind == "chain")
    gateway = FakeGateway(case)
    run = scripted_run(case, "I", 0, gateway, seed_backend(case), POLICIES["decomposer"])
    ok = bool(run.calls) and all(call.name in case.tools for call in run.calls)
    print(json.dumps([{"name": c.name, "written": c.written, "refused": c.refusal_rule} for c in run.calls],
                     ensure_ascii=False, indent=1)[:1200])
    print("fake_agent: PASS" if ok else "fake_agent: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
