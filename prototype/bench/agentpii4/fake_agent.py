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
from bench.agentpii4.schema import Case, PiiItem, message_text
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
        forbidden = {one.casefold() for item in case.pii for one in (item.value, item.canonical)}
        for item in case.pii:
            if item.value not in self._map:
                fake = self._unique(item, forbidden)
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

    def _unique(self, item: object, forbidden: set[str]) -> str:
        """A SUBSTITUTE IS DRAWN FROM THE SAME STRING SPACE AS REAL VALUES, so
        sooner or later it IS one — the rule `vault._unique_token` already
        states, which the level-A fake did not follow.

        On `chain-033` it minted «Васильев Иван Павлович» for the customer
        named Васильев Иван Павлович: the arms then agreed on a real name and
        every level called it a pass. Redrawn until it is nobody's real value
        in this case, and it raises rather than returning one — a pool a case
        can exhaust is a defect to see, not to absorb."""
        for _ in range(64):
            fake = self._mint(item.type, item.value, item.parts)          # type: ignore[attr-defined]
            if fake.casefold() not in forbidden:
                return fake
        raise ValueError(f"{self._case.id}: no substitute for {item.type} that is not a real value "  # type: ignore[attr-defined]
                         f"of this case — the pool is too small for {len(forbidden)} values")

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

def call_ceiling(case: Case) -> int:
    """A ceiling, not a budget: the planner is re-run after every tool result,
    so a value whose substitute changed on every turn would plan for ever.

    TIED TO THE TOOLBOX, NOT A CONSTANT. Twelve was four times the busiest
    family when every family had four tools; `long_order` offers twelve and
    legitimately makes thirteen calls — a search repeated with a second
    person's phone, then the writes — so a flat number turned a working family
    into a crash. Twice the offered tools allows every one of them to be called
    once more with a changed argument, which is the only honest repeat."""
    return 2 * len(case.tools) + 4

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
                parts = _merged_parts(item, surface)
        else:
            parts = _merged_parts(item, surface) if surface != item.value else dict(item.parts)
        out[item.id] = (surface, parts)
    return out


def _merged_parts(item: PiiItem, surface: str) -> dict[str, str]:
    """A SUBSTITUTE REPLACES ONE FIELD OF A CARD, NOT THE CARD.

    A seeded record stores `address.street` in one field and `address.house`,
    `address.flat`, `address.city` in siblings; only the street is personal
    data and only the street is masked. Reading the substitute's parts alone
    threw the house and the flat away, and the agent wrote an address with no
    flat in the intervention arm and a flat in the control — a divergence the
    instrument manufactured, on 14 of 30 `lookup_list` cases.

    ONLY A ROLE THE MASKED FIELD DID NOT ITSELF EXPRESS CARRIES OVER, and the
    test is `parts_of` asked of the REAL surface. Without that boundary the
    rule leaks: a spoken birth date substitute («двадцать пятое января») yields
    no `iso`, the real one's `iso` would survive the merge, and the agent would
    write the customer's true date of birth into the tool — with every level
    reporting agreement, because both arms then hold the same value.

    A message item gets nothing: there the span IS the whole value."""
    substitute = {role: value for role, value in parts_of(item.type, surface).items() if value}
    if item.where.kind != "seed":
        # NEVER `or item.parts`: an empty reading means the agent could not
        # parse what it was shown, and falling back to the real value's parts
        # is the leak this function exists to avoid.
        return substitute
    inside = set(parts_of(item.type, item.value))
    # ONLY WHAT IS NOT A VALUE. A sibling field carrying a WORD — the city, the
    # street type — is structure the gateway leaves alone. A sibling carrying a
    # NUMBER is a value, and the engine masks the house and the flat of a card
    # exactly as it masks the street. Carrying those over let the agent write
    # the customer's REAL flat while the model had been shown another one, and
    # both arms then «agreed» on it: the same shape as the spoken birth date
    # this function already guards against, reached by another road. The real
    # numbers come from the tool RESULT (`card_address`), where the model reads
    # them.
    parts = {role: value for role, value in item.parts.items()
             if role not in inside and not any(ch.isdigit() for ch in value)}
    parts.update(substitute)
    return parts


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
        # A GIVEN NAME THAT IS ALSO A SURNAME WINS THE TIE — the reading a
        # speaker takes. «Регину» scores the same as the woman «Регина» in
        # the accusative and the man «Регин» in the dative; the arbitrary
        # winner wrote «Регин», a person the gateway never minted.
        def names(pair: tuple[str, str]) -> int:
            return sum(1 for parses in parsed for p in parses
                       if (p.tag.gender, p.tag.case) == pair and "Name" in p.tag.grammemes)
        # A NAME ALREADY IN THE NOMINATIVE STAYS AS WRITTEN. «Бирюкова Регина»
        # has a masculine genitive reading for both words that outscores the
        # feminine nominative one, and the instrument wrote «Бирюков Регин» —
        # a man the gateway never minted. A reader does not re-gender a name
        # that already parses whole in the nominative.
        best = max(readings, key=lambda pair: (pair[1] == "nomn", score(pair), names(pair)))
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


def _chosen_record(case: Case, items: tuple[PiiItem, ...],
                   view: dict[str, tuple[str, dict[str, str]]]) -> str:
    """Which seeded card the agent updates — decided by what it was SHOWN.

    With one seeded card the id is that card. With several (`lookup_list`) the
    agent must tell them apart, and it may only use what reached it: the
    substitute standing for the date of birth or the phone the customer named
    has to be the SAME string as the one inside the right card. Picking by
    position would pass the family without reading anything, and picking by the
    real value would read what the model never saw.
    """
    records = case.seed_records
    if not records:
        return ""
    if len(records) == 1:
        return records[0].id
    # THE TWO SIDES ARE WRITTEN DIFFERENTLY AND MEAN THE SAME. A card stores
    # «+79164021187»; the customer says «восемь девятьсот шестнадцать…». Compared
    # as strings the control arm could match neither, fell back to the first
    # card and updated a stranger — while the intervention arm matched, because
    # the vault gives one substitute to one canonical value. That made the
    # gateway look wrong on all 30 `lookup_list` cases when it was the only
    # side reading correctly.
    by_record: dict[str, dict[str, str]] = {}
    for item in items:
        if item.where.kind == "seed" and item.id in view:
            surface, parts = view[item.id]
            by_record.setdefault(item.where.record, {})[item.type] = _match_key(item.type, surface, parts)
    for kind in ("DOB", "PHONE", "EMAIL"):
        said = [_match_key(kind, *view[item.id]) for item in items
                if item.where.kind == "message" and item.type == kind and item.id in view]
        if not said:
            continue
        hits = [record for record, seen in by_record.items() if seen.get(kind) in said]
        if len(hits) == 1:
            return hits[0]
    return records[0].id


def _match_key(kind: str, surface: str, parts: dict[str, str]) -> str:
    """One value, one key, however it was written or said.

    Used only to decide WHICH record the agent is talking about. Deliberately
    not the vault's canonicalisation: the instrument must reach the same answer
    by its own route, or it could not disagree with the engine."""
    if kind == "DOB":
        # «14.03.1987» and «1987-03-14» are one date and eight digits in two
        # orders, so stripping the separators is not enough.
        return parts.get("iso", "") or _digits_of(surface, parts)
    if kind in ("PHONE", "SNILS", "INN", "CARD", "PASSPORT"):
        return _digits_of(surface, parts)
    return surface.casefold().strip()


def _in_order(items: tuple[PiiItem, ...]) -> list[PiiItem]:
    """Items as the CONVERSATION delivered them, not as the generator listed them.

    `_pick` took the last element of `case.pii`, which is AUTHORING order. Over
    one or two turns the two coincide; over eight they do not, and the agent
    would answer the sixth message with a value said in the second."""
    spoken = [item for item in items if item.where.kind == "message"]
    seeded = [item for item in items if item.where.kind != "message"]
    spoken.sort(key=lambda item: (item.where.msg, item.where.start))
    return spoken + seeded


def _pick_all(items: tuple[PiiItem, ...], kind: str,
              view: dict[str, tuple[str, dict[str, str]]],
              policy: Policy) -> list[tuple[str, dict[str, str]]]:
    """EVERY current value of a type, in the order the agent heard them.

    One slot per type is a one-turn assumption. A long conversation names two
    addresses (from and to), three people (payer, patient, contact) and two
    phones; a planner that holds one of each cannot express such a case, let
    alone fail it."""
    chosen = [item for item in _in_order(items)
              if item.type == kind and not item.stale and item.id in view]
    return [view[item.id] for item in chosen]


def _pick_item(items: tuple[PiiItem, ...], kind: str, policy: Policy,
               prefer_current: bool = True) -> PiiItem | None:
    """WHICH item the agent uses. Separate from `_pick` because the caller
    sometimes needs the item's LOCUS: a value the customer just said and a
    value read off a card are handled differently, and a guess from the shape
    of the surface gets it wrong — a spoken address carries no digit, so
    «is there a digit» read every voice case as a card and overwrote the new
    address with the old one (80 fields on `chain` alone)."""
    ordered = _in_order(items)
    spoken = [item for item in ordered if item.type == kind and item.where.kind == "message"]
    candidates = spoken or [item for item in ordered if item.type == kind]
    if not candidates:
        return None
    current = [item for item in candidates if not item.stale] or candidates
    chosen = current[-1] if prefer_current else current[0]
    if policy.swaps_person and len({item.identity for item in current}) > 1:
        chosen = [item for item in current if item.identity != chosen.identity][0]
    return chosen


def _pick(items: tuple[PiiItem, ...], kind: str, view: dict[str, tuple[str, dict[str, str]]],
          policy: Policy, prefer_current: bool = True) -> tuple[str, dict[str, str]]:
    """The agent's choice of which item of a type to use."""
    chosen = _pick_item(items, kind, policy, prefer_current)
    return view[chosen.id] if chosen is not None and chosen.id in view else ("", {})


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


def card_address(results: tuple[tuple[str, str], ...], record_id: str) -> dict[str, str]:
    """The address of one card AS THE AGENT WAS SHOWN IT, out of the search result.

    A card's address lives across four fields and the engine masks three of
    them; the corpus marks only the street as personal data, so the item's
    parts carry the REAL house and flat. Reading them from the item let the
    instrument write values the model had never seen. The search result is
    where the model reads them, so it is where the agent reads them."""
    for name, text in reversed(results):
        if name != "crm_find_contact":
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        contacts = payload.get("contacts") if isinstance(payload, dict) else None
        if not isinstance(contacts, list):
            continue
        for row in contacts:
            if not isinstance(row, dict):
                continue
            if record_id and str(row.get("id", "")) != record_id:
                continue
            address = row.get("address")
            if isinstance(address, dict):
                return {key: str(value) for key, value in address.items() if value}
    return {}


def result_field(results: tuple[tuple[str, str], ...], tool: str, key: str) -> str:
    """A value the agent READ BACK out of a tool result, by the tool that made it.

    The order id is not in the case and not in any message: it is allocated by
    the write and comes back in its answer, so a call that refers to it can
    only be planned AFTER that answer. This is the whole reason the planner is
    re-run per result rather than once.

    The text is the MASKED result, byte for byte what the model is handed."""
    for name, text in reversed(results):
        if name != tool:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get(key), str):
            return str(payload[key])
    return ""


def consumes(name: str) -> frozenset[str]:
    """The PII types a tool's schema says it consumes — declared, not guessed.

    Read off `REGISTRY[name].fields`: `pii_type` for a field that carries a
    value, `source_type` for one derived from it. A list written here would be
    a second copy of the registry, and the two would drift the first time a
    tool gained a field."""
    spec = REGISTRY.get(name)
    if spec is None:
        return frozenset()
    return frozenset(one for field_spec in spec.fields
                     for one in (field_spec.pii_type, field_spec.source_type) if one)


def _still_dictating(case: Case, name: str, upto_msg: int) -> bool:
    """Is the customer still saying things this call would write?

    A MUTATING TOOL IS NOT CALLED WHILE A LATER MESSAGE STILL CARRIES A TYPE IT
    CONSUMES. Without this the turn-by-turn planner booked on the first turn
    with half the request and booked again on the second — 75 cases of `chain`,
    `lookup_list` and `crm_note` grew a second write, and through the real
    gateway the two arms did not even agree on HOW MANY: a substitute the
    engine mints against half a conversation differs from the one it mints
    against the whole, so the second call deduplicated in one arm and not in
    the other. `result_feed` fell to 0 of 36 on the state level from that
    alone.

    The rule is about the conversation, not about a family: an agent writes a
    record when the customer stops dictating it. A READ is not deferred — a
    lookup is exactly what an agent does with the first thing it is told."""
    spec = REGISTRY.get(name)
    if spec is None or not spec.mutating:
        return False
    wanted = consumes(name)
    return any(item.where.kind == "message" and item.where.msg > upto_msg
               and item.type in wanted for item in case.pii)


def call_key(name: str, arguments: dict[str, object]) -> tuple[str, str]:
    """A call's identity: the tool and the arguments it was given.

    Two calls of one tool with the SAME arguments are one call; with different
    ones they are two, which is how «найти по телефону, потом по фамилии» and
    «записать, клиент передумал, записать снова» are expressed at all."""
    return name, json.dumps(arguments, ensure_ascii=False, sort_keys=True)


def plan_calls(case: Case, gateway: object, policy: Policy, upto_msg: int,
               done: frozenset[tuple[str, str]], results: tuple[tuple[str, str], ...],
               ) -> list[tuple[str, dict[str, object]]]:
    """The calls the agent makes ONCE THE CONVERSATION HAS REACHED `upto_msg`,
    from what it READS — never from the case's ground truth.

    Called after every user message, the way `harness.drive` hands the model
    one message at a time. Planning once at the end cannot tell a value that
    arrived on the sixth turn from one said on the first, so a case whose whole
    point is WHEN something was said passed without being asked its question.

    SEED ITEMS STAY VISIBLE FROM THE FIRST TURN. Gating them on the tool that
    would return them is the honest rule and belongs with the read-back tools;
    until those exist, a family whose search comes back empty would lose its
    values instead of testing them.

    `results` is what the tools have returned so far, masked exactly as the
    model is handed them — the input a chained family reads.
    """
    view = _seen_values(case, gateway)
    items = tuple(item for item in case.pii
                  if item.where.kind != "message" or upto_msg < 0 or item.where.msg <= upto_msg)
    plain_values = tuple(one for one in case.plain
                         if one.where.kind != "message" or upto_msg < 0 or one.where.msg <= upto_msg)
    calls: list[tuple[str, dict[str, object]]] = []
    planned: set[tuple[str, str]] = set()
    tools = case.expects.reachable_tools

    def maybe(name: str, args: dict[str, object]) -> None:
        # THE NOISE DRAW IS KEYED, NOT SEQUENTIAL. Planning now runs once per
        # turn, so a shared stream would make which call is dropped depend on
        # how many turns a case has rather than on the policy's rate.
        if _still_dictating(case, name, upto_msg):
            return
        key = call_key(name, args)
        if key in done or key in planned:
            return
        if policy.noise and random.Random(
                f"noise:{policy.seed}:{case.id}:{key[0]}:{key[1]}").random() < policy.noise:
            return
        planned.add(key)
        calls.append((name, args))

    name_surface, name_parts = _pick(items, "NAME", view, policy)
    phone_surface, phone_parts = _pick(items, "PHONE", view, policy)
    # WHAT THE CUSTOMER SAID, separately from what a card would tell us. `_pick`
    # falls back to seed items so a family that looks a card up first can use
    # what came back — but a SEARCH KEY may only be something the customer
    # actually uttered. Without this the agent «searched» by a phone it could
    # not know yet, and `lookup_list` never asked its own question.
    said_phone = next((view[item.id][0] for item in _in_order(items)
                       if item.type == "PHONE" and item.where.kind == "message" and item.id in view), "")
    addr_surface, addr_parts = _pick(items, "LOC", view, policy)
    addr_item = _pick_item(items, "LOC", policy)
    if addr_item is not None and addr_item.where.kind == "seed":
        # A BARE STREET CAME OFF A CARD, and the card's numbers are in the
        # RESULT the agent has already read — never in the item, where they are
        # the customer's real ones. Field by field only: composing them into one
        # string was tried and measures our renderer, not the gateway (the two
        # arms compose differently and 80 fields came back
        # `same_person_variant`). A free-text address argument gets the surface
        # as read, and a bare street there is an honest `residual`.
        addr_parts = {**addr_parts, **card_address(results, _chosen_record(case, items, view))}
    dob_surface, dob_parts = _pick(items, "DOB", view, policy)
    phone = _e164(phone_surface, phone_parts, policy) if phone_surface else ""
    name = _name_args(name_surface, name_parts, policy)
    address = _address_args(addr_surface, addr_parts, policy)
    city = address.get("city") or _city_of(case, items)

    if "crm_find_contact" in tools and said_phone:
        maybe("crm_find_contact", {"query": {"phone": _e164(said_phone, phone_parts, policy)}})
    elif "crm_find_contact" in tools and name["last"]:
        # NO PHONE MEANS SEARCHING BY SURNAME, and the answer is then a LIST —
        # the `lookup_list` shape. The tool takes exactly one key, and the
        # surname is the one a customer gives when they do not recite a number.
        maybe("crm_find_contact", {"query": {"last_name": name["last"]}})
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
            contact["name_latin"] = " ".join(derive.translit_common(word) for word in (name["last"], name["first"]) if word).upper()
            gender = derive.gender({"given": name["first"], "surname": name["last"], "patronymic": name["middle"]})
            contact["gender"] = "F" if "female" in gender else "M"
        if phone:
            contact["phone"] = phone
        if address["street"]:
            contact["address"] = {"city": city, "street": address["street"], "house": address["house"] or "1",
                                  "flat": address["flat"]}
        maybe("crm_upsert_contact", {"id": _chosen_record(case, items, view), "contact": contact})
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
        pp_surface, pp_parts = _pick(items, "PASSPORT", view, policy)
        sn_surface, sn_parts = _pick(items, "SNILS", view, policy)
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
            plain = [one.value for one in plain_values]
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
        card_surface, card_parts = _pick(items, "CARD", view, policy)
        digits = _digits_of(card_surface, card_parts)
        if policy.validates_checksum and card_surface and not _checksum_ok("CARD", card_surface, card_parts):
            pass
        elif digits:
            holder = " ".join(derive.translit_common(word) for word in (name["first"], name["last"]) if word).upper() if policy.derives else "CARD HOLDER"
            # THE RECEIPT IS NOT OPTIONAL WHEN A CONTACT IS KNOWN. 54-ФЗ makes
            # one of email/phone mandatory, and both acquirers refuse without
            # it — an agent holding a phone fills it, or the sale stops.
            call: dict[str, object] = {
                "amount": {"value": "780.00", "currency": "RUB"},
                "payment_method_data": {"type": "bank_card",
                                        "card": {"number": digits, "expiry_month": "09", "expiry_year": "2028",
                                                 "cardholder": holder or "CARD HOLDER"}}}
            email_surface, _email_parts = _pick(items, "EMAIL", view, policy)
            if phone or email_surface:
                customer: dict[str, object] = {}
                if name_surface:
                    customer["full_name"] = name_surface
                if phone:
                    customer["phone"] = phone
                elif email_surface:
                    customer["email"] = email_surface
                call["receipt"] = {"customer": customer}
            maybe("payment_create", call)
    if "callback_schedule" in tools and phone:
        zone = sorted(derive.timezone(city))[0] if (policy.derives and derive.timezone(city)) else "Europe/Moscow"
        maybe("callback_schedule", {"phone": phone, "at": "2026-09-03T18:00:00+04:00", "timezone": zone})
    if "crm_segment_report" in tools:
        # ONE ROW PER PERSON, and the bucket is the city the customer named —
        # a real value that must NOT be masked, which is what makes the
        # aggregate meaningful at all.
        spoken = tuple(item for item in items if item.where.kind == "message")
        rows = [{"name": surface, "bucket": _city_of(case, items) or "Москва"}
                for surface, _parts in _pick_all(spoken, "NAME", view, policy)]
        if rows:
            maybe("crm_segment_report", {"group_by": "city", "members": rows})
    if "send_template" in tools:
        # THE AGENT FILLS VARIABLES, never the template body. Which variables
        # exist is the template's business, so the tool is asked for the set it
        # declares rather than guessed at here.
        from bench.agentpii4.tools import TEMPLATES, _TEMPLATE_RE
        template_id = "delivery_eta" if address["street"] else "callback"
        wanted = sorted(set(_TEMPLATE_RE.findall(TEMPLATES[template_id])))
        filled = {"name": name["first"] or name_surface, "phone": phone,
                  "address": addr_surface, "when": "завтра", "code": "1234"}
        variables = {key: filled.get(key, "") for key in wanted}
        if phone and all(variables.values()):
            maybe("send_template", {"template_id": template_id, "number": phone,
                                    "variables": variables})
    if "crm_add_note" in tools:
        # THE AGENT WRITES THE NOTE IN ITS OWN WORDS, and its words are the
        # substitutes it was shown. Deterministic prose, so two control arms
        # agree and the floor measures the policy's noise rather than this line.
        pieces = [f"Клиент {name_surface}." if name_surface else "Клиент.",
                  f"Телефон {phone}." if phone else "",
                  f"Адрес {addr_surface}." if addr_surface else ""]
        maybe("crm_add_note", {"entity_id": _chosen_record(case, items, view) or "c-1",
                               "note_type": "call_in",
                               "text": " ".join(part for part in pieces if part)})
    if "crm_import_csv" in tools:
        rows = []
        spoken = tuple(item for item in items if item.where.kind == "message")
        people = _pick_all(spoken, "NAME", view, policy)
        phones = _pick_all(spoken, "PHONE", view, policy)
        for (n_surface, n_parts), (p_surface, p_parts) in zip(people, phones):
            parts = _name_args(n_surface, n_parts, Policy("x"))
            rows.append(f"{parts['last']};{parts['first']};{_e164(p_surface, p_parts, Policy('x'))};;")
        if rows:
            maybe("crm_import_csv", {"csv": "\n".join([CSV_HEADER, *rows])})
    if "delivery_quote" in tools and city:
        # THE WEIGHT IS THE CUSTOMER'S, THE DEFAULT IS THE PROMPT'S. The system
        # prompt names 1000 g when nobody says otherwise, so a case that omits
        # it still reaches the tool and the two arms still agree on the number.
        said = next((one.value for one in plain_values if one.family == "weight"), "")
        grams = int(_as_digits(said) or 0) * 1000 or 1000
        maybe("delivery_quote", {"weight": grams, "city": city})
    if "pickup_points_near" in tools and addr_surface:
        maybe("pickup_points_near", {"address": addr_surface, "limit": 3})
    order_id = result_field(results, "delivery_create_order", "uuid")
    if "order_status" in tools and order_id:
        maybe("order_status", {"order_id": order_id})
    if "order_reschedule" in tools and order_id:
        maybe("order_reschedule", {"order_id": order_id, "date": "2026-09-10"})
    if "order_cancel" in tools and order_id:
        maybe("order_cancel", {"order_id": order_id, "reason": "клиент передумал"})
    if "notify_sms" in tools and phone:
        order = next((one.value for one in plain_values if one.family == "order_number"), "")
        text = f"Ваш заказ {order or 'оформлен'}"
        if order:
            text += f": https://t.example.ru/o?order={re.sub(r'[^0-9]', '', order) or order}&phone={re.sub(r'[^0-9]', '', phone)}"
        maybe("notify_sms", {"number": phone, "text": text[:400]})
    return calls


def _city_of(case: Case, items: tuple[PiiItem, ...]) -> str:
    for item in items:
        if item.type == "LOC" and item.parts.get("city"):
            return item.parts["city"]
    for record in case.seed_records:
        address = record.fields.get("address")
        if isinstance(address, dict) and address.get("city"):
            return str(address["city"])
    return "москва"


def scripted_run(case: Case, arm: str, repeat: int, gateway: object, backend: Backend,
                 policy: Policy) -> ArmRun:
    """Drive one arm TURN BY TURN, the shape `harness.drive` gives the model:
    push one user message, plan what that message made possible, call it
    (restore -> backend.call -> serialise -> push_tool), feed the result back,
    then take the next message.

    The old order pushed every message first and planned once. That is not a
    smaller version of a conversation, it is a different thing: nothing could
    depend on WHEN a value arrived, and the growing transcript the engine masks
    against was never the one the model actually saw."""
    gateway.push_system(case.messages[0].content)  # type: ignore[attr-defined]
    calls: list[ObservedCall] = []
    done: set[tuple[str, str]] = set()
    results: list[tuple[str, str]] = []
    for index, message in enumerate(case.messages):
        if message.role != "user":
            continue
        gateway.push_user(index)  # type: ignore[attr-defined]
        # ONE CALL, THEN PLAN AGAIN. Planning a whole turn at once reads the
        # agent's view BEFORE that turn's own tool results have arrived, and in
        # the intervention arm a seed value then has no substitute yet — so the
        # scripted agent wrote the customer's REAL name into the tool and both
        # arms «agreed» on it. `result_feed` and `lookup_list` scored 36/36 and
        # 28/30 for four months without their own question ever being asked.
        while True:
            batch = plan_calls(case, gateway, policy, index, frozenset(done), tuple(results))
            if not batch:
                break
            name, arguments = batch[0]
            done.add(call_key(name, arguments))
            ceiling = call_ceiling(case)
            if len(calls) >= ceiling:
                raise RuntimeError(f"{case.id}/{arm}: {ceiling} calls and still planning "
                                   f"({name}) — a substitute that changes every turn would loop here")
            gateway.note_tool_call(name, arguments)  # type: ignore[attr-defined]
            restored, residual = gateway.restore_arguments(arguments)  # type: ignore[attr-defined]
            log = backend.call(name, restored)
            # WHAT THE AGENT READS BACK is the masked result, byte for byte
            # what the model is handed; the next plan may use it.
            results.append((name, gateway.push_tool(name, log.result_text)))  # type: ignore[attr-defined]
            calls.append(ObservedCall(
                name=name, written=arguments, restored=restored, residual=residual,
                refusal_path=log.refusal.path if log.refusal else "",
                refusal_rule=log.refusal.rule if log.refusal else "",
                parsed=log.parsed, seq=len(calls) + 1))
    name_surface, _ = _pick(case.pii, "NAME", _seen_values(case, gateway), policy)
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
