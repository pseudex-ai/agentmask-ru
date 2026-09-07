"""What every scenario module shares: drawing, rendering, laying text down.

A scenario builds a case in three moves, and the moves are the discipline:

  1. DRAW values from `pools` — a `Person`, an `Address`, digits — and RENDER
     them for the register. The `Rendered` carries the typed parts the value
     was built from.
  2. WRITE messages with `MessageDraft`: ordinary words go through the
     register's noise ONE CHUNK AT A TIME before they are put; a value is put
     keyed and untouched. Offsets exist the moment the chunk lands.
  3. FINISH with `CaseBuilder`, which turns keys into `PiiItem`s with a
     `Locus`, attaches seeds, negatives and expectations, and stamps the trace.

Nothing here searches a finished message. `validate.prove_no_search` watches.
"""
import random
from dataclasses import dataclass, field, replace

from bench.agentpii4 import pools
from bench.agentpii4.pools import Address, Person, Rendered
from bench.agentpii4.schema import (Case, Expectation, Locus, Message, Negative,
                                    PiiItem, PlainValue, Provenance, SeedRecord,
                                    TraceRow)
from bench.agentpii4.scenarios import negatives
from bench.agentpii4.writer import Writer

NOW = "2026-09-02"
# `clean` is 0 here: the six clean cases of the corpus are forced by
# `summary` and `decompose`, and a per-family 5% would push the whole above the
# cap the register split exists for.
REGISTER_MIX: tuple[tuple[str, float], ...] = (
    ("voice_raw", 0.33), ("voice_itn", 0.22), ("chat", 0.30), ("sloppy", 0.15), ("clean", 0.0))


def registers_for(count: int, rng: random.Random) -> list[str]:
    """A register per case, in the planned proportions, then shuffled."""
    out: list[str] = []
    for register, share in REGISTER_MIX:
        out.extend([register] * round(count * share))
    while len(out) < count:
        out.append("chat")
    out = out[:count]
    rng.shuffle(out)
    return out


@dataclass
class Ctx:
    kind: str
    index: int
    register: str
    rng: random.Random
    seed: int

    @property
    def spoken(self) -> bool:
        return self.register == "voice_raw"

    @property
    def speech(self) -> bool:
        return self.register in pools.SPEECH_REGISTERS


def ctx_for(kind: str, seed: int, index: int, register: str) -> Ctx:
    return Ctx(kind=kind, index=index, register=register,
               rng=random.Random(f"v4:{kind}:{seed}:{index}"), seed=seed)


# --- system prompts ------------------------------------------------------------

_ROLE_PROMPTS: dict[str, str] = {
    # The weight and the postcode are named here because the live pilot showed
    # the model asking for both in EVERY arm of the summary family — a schema
    # field the utterance never carries measures nothing about the gateway.
    "delivery": "Ты оператор службы доставки. Оформляй заказы и вызовы курьера инструментами, "
                "переспрашивай только то, чего не хватает для вызова. Вес посылки, если не "
                "назван, — 1000 г; почтовый индекс подбери сам по городу получателя.",
    "clinic": "Ты администратор клиники. Записывай пациентов инструментом clinic_book; "
              "возраст и пол пациента вычисли сам из даты рождения и имени.",
    "crm": "Ты оператор CRM. Находи и обновляй карточки клиентов инструментами; "
           "инициалы и латинское написание имени заполняй сам по ФИО.",
    "bank": "Ты оператор платёжного сервиса. Создавай платежи инструментом payment_create; "
            "держатель карты — латиницей заглавными, как на карте.",
    "gov": "Ты оператор МФЦ. Сверяй паспортные данные инструментом passport_verify; "
           "серию и номер передавай отдельными полями.",
    "callcenter": "Ты оператор колл-центра. Планируй обратные звонки и отправляй смс инструментами.",
}

VALIDATE_CLAUSE = ("Перед вызовом инструмента проверь контрольную сумму продиктованных "
                   "идентификаторов: СНИЛС — по алгоритму ПФР, ИНН — по весовым коэффициентам, "
                   "номер карты — по алгоритму Луна. Если контрольная сумма не сходится, "
                   "инструмент НЕ вызывай и попроси клиента продиктовать заново.")


def system_prompt(role: str, now: str, validate_types: tuple[str, ...] = (),
                  rule: str = "") -> str:
    text = f"{_ROLE_PROMPTS[role]} Сегодня {now}."
    if validate_types:
        text = f"{text} {VALIDATE_CLAUSE}"
    # A BUSINESS RULE THE AGENT MUST APPLY, and the substitute may break it.
    # It goes in the SYSTEM prompt because that is where a customer puts one,
    # and the prompt passes through the gateway like everything else — so a
    # rule the masking rewrote is a rule the agent never received.
    return f"{text} {rule}" if rule else text


# --- register noise on ordinary words --------------------------------------------

def noisy_word(word: str, ctx: Ctx) -> str:
    """One ordinary word as the register writes it. Chunk-level, before `put`."""
    if ctx.register == "sloppy" and ctx.rng.random() < 0.18:
        return pools.typo(word, ctx.rng)
    if ctx.register == "voice_raw":
        return pools.speech_noise(word, ctx.rng)
    return word


OPENERS: dict[str, tuple[str, ...]] = {
    "voice_raw": ("здравствуйте", "алло", "добрый день", "девушка здравствуйте", "аа здравствуйте", ""),
    "voice_itn": ("здравствуйте", "алло", "добрый день", ""),
    "chat": ("здравствуйте", "привет", "добрый день", ""),
    "sloppy": ("здрасте", "привет", "добрый", ""),
    "clean": ("Здравствуйте.", "Добрый день!"),
}


def opener(ctx: Ctx) -> str:
    return ctx.rng.choice(OPENERS[ctx.register])


class MessageDraft:
    """One user message being written. Words get noise; values do not."""

    def __init__(self, ctx: Ctx) -> None:
        self._ctx = ctx
        self._writer = Writer()
        self.values: dict[str, Rendered] = {}
        self.plain: dict[str, tuple[str, str, str]] = {}   # key -> (value, family, why)
        self.negatives: dict[str, tuple[str, str, str]] = {}

    def say(self, text: str) -> "MessageDraft":
        """Ordinary words, each through the register's noise before it lands."""
        if not text:
            return self
        clean = self._ctx.register == "clean"
        for word in text.split():
            self._writer.space().put(word if clean else noisy_word(word, self._ctx),
                                     origin="chunk:noisy_word")
        return self

    def value(self, key: str, rendered: Rendered) -> "MessageDraft":
        self.values[key] = rendered
        self._writer.space().put(rendered.surface, key, f"value:{key}")
        return self

    def plain_value(self, key: str, text: str, family: str, why: str) -> "MessageDraft":
        self.plain[key] = (text, family, why)
        self._writer.space().put(text, key, f"plain:{key}")
        return self

    def negative(self, key: str, text: str, family: str, why: str) -> "MessageDraft":
        self.negatives[key] = (text, family, why)
        self._writer.space().put(text, key, f"negative:{key}")
        return self

    def punct(self, text: str) -> "MessageDraft":
        if self._ctx.register == "clean":
            self._writer.put(text, origin="literal")
        return self

    def finish(self) -> tuple[str, dict[str, tuple[int, int]], tuple]:
        return self._writer.finish()


@dataclass
class CaseBuilder:
    ctx: Ctx
    role: str
    tools: tuple[str, ...]
    reachable: tuple[str, ...]
    primary_identity: str
    cluster: str
    conversation_id: str = ""
    validate_types: tuple[str, ...] = ()
    rule: str = ""
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    note: str = ""
    messages: list[Message] = field(default_factory=list)
    pii: list[PiiItem] = field(default_factory=list)
    plain: list[PlainValue] = field(default_factory=list)
    negatives: list[Negative] = field(default_factory=list)
    seeds: list[SeedRecord] = field(default_factory=list)
    trace: list[TraceRow] = field(default_factory=list)
    _item_counter: int = 0

    def __post_init__(self) -> None:
        self.messages.append(Message(role="system",
                                     content=system_prompt(self.role, NOW, self.validate_types,
                                                           self.rule),
                                     source=None, name=""))

    def _add_negative(self, draft: MessageDraft,
                      typed: dict[str, tuple[str, str, str, bool]]) -> None:
        """Одно значение, которое ОБЯЗАНО уцелеть, в первую реплику случая.

        ЗДЕСЬ, А НЕ В ДВАДЦАТИ ДВУХ СЦЕНАРИЯХ, потому что правило одно на весь
        корпус и повторять его двадцать два раза значит завести двадцать два
        места, где оно разойдётся. Ровно один негатив на случай: он должен
        мерить точность, а не переписать корпус.

        СВОЙ ПОТОК СЛУЧАЙНОСТИ, А НЕ `ctx.rng`. Взять из общего значит сдвинуть
        КАЖДЫЙ последующий розыгрыш сценария, и пересборка стала бы новым
        корпусом целиком вместо корпуса с добавленной осью. Здесь разница
        ровно в негативах.

        РЯДОМ С АДРЕСОМ РАЗРЕШЕНО НЕ ВСЁ: голый «шестой подъезд» возле
        настоящей улицы — это ЧАСТЬ адреса, и требовать его выживания значит
        требовать от движка ошибки.
        """
        beside = (any(spec[0] == "LOC" for spec in typed.values())
                  or any(item.type == "LOC" for item in self.pii))
        stream = random.Random(f"v4:neg:{self.ctx.kind}:{self.ctx.seed}:{self.ctx.index}")
        before, value, after, family, why = negatives.draw(self.ctx.register, stream, beside)
        # СВЯЗКА ОБЯЗАТЕЛЬНА, И ЭТО НЕ УКРАШЕНИЕ РЕЧИ. Негатив почти всегда несёт
        # числительное, а продиктованный телефон — это ПРОГОН числительных;
        # приклеенный к нему вплотную, негатив продолжает прогон, спан телефона
        # рвётся, и номер уходит открытым. Так вышло 44 утечки из 52 на первой
        # же сборке — дефект корпуса, который читался бы как дефект движка.
        # Слово-связка прогон разрывает и звучит как живая речь, а не как шов.
        draft.say(stream.choice(("кстати", "и ещё", "да и", "а также")))
        if before:
            draft.say(before)
        draft.negative("neg1", value, family, why)
        if after:
            draft.say(after)
        draft.punct(".")

    def user(self, draft: MessageDraft,
             typed: dict[str, tuple[str, str, str, bool]]) -> int:
        """Append a user message. `typed` maps value keys to
        (pii type, identity, duty, stale)."""
        if not self.negatives and not draft.negatives:
            self._add_negative(draft, typed)
        text, spans, trace = draft.finish()
        index = len(self.messages)
        self.messages.append(Message(role="user", content=text, source=None, name=""))
        for row in trace:
            self.trace.append(TraceRow(msg=index, key=row.key, start=row.start,
                                       end=row.end, origin=row.origin))
        for key, rendered in draft.values.items():
            pii_type, identity, duty, stale = typed[key]
            start, end = spans[key]
            self._item_counter += 1
            self.pii.append(PiiItem(
                id=f"i{self._item_counter}", type=pii_type, identity=identity,
                value=rendered.surface, canonical=rendered.canonical,
                parts=dict(rendered.parts),
                where=Locus("message", index, start, end, "", ""),
                duty=duty, spoken=rendered.spoken, stale=stale))
        for key, (value, family, why) in draft.plain.items():
            start, end = spans[key]
            self.plain.append(PlainValue(value=value, where=Locus("message", index, start, end, "", ""),
                                         family=family, why=why))
        for key, (value, family, why) in draft.negatives.items():
            start, end = spans[key]
            self.negatives.append(Negative(value=value, start=start, end=end, msg=index,
                                           family=family, why=why))
        return index

    def seed(self, record_id: str, table: str, fields: dict[str, object],
             typed_paths: dict[str, tuple[str, str, Rendered]]) -> None:
        """A backend row that exists before the run; PII fields become items
        with a seed locus. `typed_paths` maps field path to (type, identity, rendered)."""
        ids: list[str] = []
        for path, (pii_type, identity, rendered) in typed_paths.items():
            self._item_counter += 1
            item_id = f"i{self._item_counter}"
            ids.append(item_id)
            self.pii.append(PiiItem(
                id=item_id, type=pii_type, identity=identity,
                value=str(_seed_field(fields, path)), canonical=rendered.canonical,
                parts=dict(rendered.parts),
                where=Locus("seed", -1, 0, 0, record_id, path),
                duty="required", spoken=False, stale=False))
        self.seeds.append(SeedRecord(id=record_id, table=table, fields=fields, pii_ids=tuple(ids)))

    def build(self) -> Case:
        # THE CLUSTER IS THE PERSON, and the phone is how a person recurs across
        # families: a `LOC:` or `CARD:` key would split one shared person into
        # several clusters and hide the correlation the bootstrap must respect.
        phones = [item for item in self.pii if item.type == "PHONE" and item.where.kind == "message"]
        cluster = f"PHONE:{phones[0].parts.get('digits', phones[0].canonical)}" if phones else self.cluster
        return Case(
            id=f"{self.ctx.kind}-{self.ctx.index:03d}", kind=self.ctx.kind,
            register=self.ctx.register,
            provenance=Provenance(kind="template", corpus="authored", key="", shape="",
                                  selection="rare" if is_rare_stratum(self.ctx) else "authored",
                                  weight=1.0, licence="authored"),
            cluster=cluster, conversation_id=self.conversation_id, now=NOW,
            messages=tuple(self.messages), tools=self.tools,
            seed_records=tuple(self.seeds), pii=tuple(self.pii), plain=tuple(self.plain),
            negatives=tuple(self.negatives),
            expects=Expectation(reachable_tools=self.reachable,
                                primary_identity=self.primary_identity,
                                must_contain=self.must_contain,
                                must_not_contain=self.must_not_contain,
                                validate_types=self.validate_types),
            trace=tuple(self.trace), note=self.note)


def _seed_field(fields: dict[str, object], path: str) -> object:
    node: object = fields
    for part in path.split("."):
        node = node.get(part) if isinstance(node, dict) else None  # type: ignore[union-attr]
    return node


# --- drawing values ---------------------------------------------------------------

@dataclass(frozen=True)
class Drawn:
    person: Person
    phone: str                  # ten digits
    address: Address
    dob: tuple[int, int, int]
    email_local: str
    email_domain: str


# EIGHT SHARED PEOPLE. Every fifth case of every family draws one of them, so
# the same phone recurs in three or more cases across kinds and registers —
# the clusters the bootstrap resamples and the ICC is measured on. Without
# them every case is its own cluster and the design effect is an assumption.
_SHARED: tuple[tuple[int, str, tuple[int, int, int]], ...] = (
    (0, "9164021187", (14, 3, 1987)), (17, "9261234567", (2, 11, 1975)),
    (3, "9037654321", (30, 6, 1992)), (20, "9129876543", (8, 1, 1969)),
    (7, "9221112233", (21, 9, 1980)), (24, "9505556677", (5, 5, 1999)),
    (11, "9628889900", (17, 12, 1983)), (26, "9777778899", (28, 2, 1971)),
)


def is_rare_stratum(ctx: Ctx) -> bool:
    """Случай, чьи имя и улица взяты ВНЕ лизованных словарей.

    ОСЬ ДЕТЕКЦИИ ИНАЧЕ НЕ МОЖЕТ ПРОВАЛИТЬСЯ: все 57 улиц пула лежат в словаре
    ГАР, все имена — в словаре имён, и корпус отвечает 100% там, где два
    независимых внешних прибора дают 68–70%. Это тот же дефект, за который
    репозиторий уже заплатил на `bench/voice`, вшитый не в фильтр, а в пулы.

    ОДИН СЛУЧАЙ ИЗ СЕМИ И НИКОГДА — КЛАСТЕРНЫЙ. Восемь общих людей держат
    кластеры, на которых меряется ICC и работает бутстрап; подменить человека в
    таком случае значит развалить кластер и подменить не страту, а design
    effect. Правило детерминировано по индексу, поэтому и `draw`, и `build`
    вычисляют его одинаково, не передавая флаг через полкорпуса.
    """
    return ctx.index % 7 == 3 and ctx.index % 5 != 0


def draw(ctx: Ctx, city: str = "", with_flat: bool = True, with_entrance: bool = False,
         with_type: bool = True, foreign: bool = False) -> Drawn:
    rng = ctx.rng
    pool = pools.FOREIGN if foreign else (pools.MALE + pools.FEMALE)
    person = rng.choice(pool)
    phone = pools.mobile_digits(rng)
    dob = pools.draw_dob(rng)
    if ctx.index % 5 == 0 and not foreign:
        slot, phone, dob = _SHARED[(ctx.index // 5) % len(_SHARED)]
        person = (pools.MALE + pools.FEMALE)[slot]
    address = pools.draw_address(rng, city, with_flat, with_entrance, with_type)
    if is_rare_stratum(ctx) and not foreign:
        # Свой поток: взять из общего значило бы сдвинуть каждый последующий
        # розыгрыш и превратить добавление страты в новый корпус целиком.
        stream = random.Random(f"v4:rare:{ctx.kind}:{ctx.seed}:{ctx.index}")
        rare = pools.RARE_MALE + pools.RARE_FEMALE
        person = stream.choice(rare)
        address = replace(address, street=stream.choice(pools.RARE_STREETS))
    return Drawn(
        person=person,
        phone=phone,
        address=address,
        dob=dob,
        email_local=pools.mail_translit(person.surname[0]) + str(rng.randrange(70, 99)),
        email_domain=rng.choice(pools.EMAIL_DOMAINS),
    )


def name(ctx: Ctx, person: Person, layout: tuple[str, ...], grammar: str = "nom",
         damage: bool = False) -> Rendered:
    kind = "none"
    if damage:
        kind = "typo" if ctx.register == "sloppy" else ("slip" if ctx.spoken else "none")
    return pools.render_name(person, layout, grammar, ctx.register, kind, ctx.rng)


def phone(ctx: Ctx, digits: str) -> Rendered:
    return pools.render_phone(digits, ctx.register, ctx.rng, 0.23)


def address(ctx: Ctx, value: Address) -> Rendered:
    return pools.render_address(value, ctx.register, ctx.rng, ctx.spoken)


def dob(ctx: Ctx, value: tuple[int, int, int]) -> Rendered:
    day, month, year = value
    return pools.render_dob(day, month, year, ctx.register)


def snils(ctx: Ctx, digits: str) -> Rendered:
    return pools.render_snils(digits, ctx.register, ctx.rng, 0.23)


def inn(ctx: Ctx, digits: str) -> Rendered:
    return pools.render_inn(digits, ctx.register, ctx.rng, 0.23)


def card(ctx: Ctx, digits: str) -> Rendered:
    return pools.render_card(digits, ctx.register, ctx.rng, 0.23)


def passport(ctx: Ctx, series: str, number: str) -> Rendered:
    return pools.render_passport(series, number, ctx.register, ctx.rng, 0.23)


def email(ctx: Ctx, local: str, domain: str) -> Rendered:
    spoken_local = " ".join(local.replace("_", " ").split())
    return pools.render_email(local, domain, spoken_local, ctx.register)


def order_number(ctx: Ctx) -> str:
    """An order number in the register's notation — plain, must survive."""
    digits = ctx.rng.randrange(1000000, 9999999)
    if ctx.spoken:
        return " ".join(pools.spell_groups(str(digits), (3, 2, 2)))
    return f"ORD-{digits}" if ctx.register in ("chat", "clean") else str(digits)


def time_of_day(ctx: Ctx) -> str:
    hour = ctx.rng.choice((9, 10, 11, 14, 15, 17, 18))
    if ctx.spoken:
        return f"к {pools.spell_cardinal(hour)} ноль ноль"
    return f"к {hour}:00" if ctx.register in ("clean", "chat") else f"к {hour} 00"


def full_name_canonical(person: Person) -> str:
    return " ".join(part for part in (person.surname[0], person.given[0], person.patronymic[0]) if part)


def address_seed_fields(value: Address, city: str) -> dict[str, object]:
    return {"city": city or value.city, "street": value.street,
            "house": f"{value.house}{value.letter}", "flat": str(value.flat) if value.flat else ""}


def contact_seed(record_id: str, drawn: Drawn, city: str, ctx: Ctx,
                 builder: CaseBuilder, identity: str) -> None:
    """A CRM row for a person, its PII fields registered as seed items."""
    person = drawn.person
    day, month, year = drawn.dob
    address_rendered = pools.render_address(drawn.address, "clean", ctx.rng, False)
    fields: dict[str, object] = {
        "last_name": person.surname[0], "first_name": person.given[0],
        "middle_name": person.patronymic[0], "phone": f"+7{drawn.phone}",
        "email": f"{drawn.email_local}@{drawn.email_domain}",
        "birth_date": f"{year:04d}-{month:02d}-{day:02d}",
        "address": address_seed_fields(drawn.address, city),
    }
    name_rendered = pools.render_name(person, ("surname", "given", "patronymic"), "nom", "chat", "none", ctx.rng)
    builder.seed(record_id, "contacts", fields, {
        "last_name": ("NAME", identity, Rendered(person.surname[0], person.surname[0], False,
                                                 {"surname": person.surname[0], "gender": person.gender})),
        "first_name": ("NAME", identity, Rendered(person.given[0], person.given[0], False,
                                                  {"given": person.given[0], "gender": person.gender})),
        "middle_name": ("NAME", identity, Rendered(person.patronymic[0], person.patronymic[0], False,
                                                   {"patronymic": person.patronymic[0], "gender": person.gender})),
        "phone": ("PHONE", identity, Rendered(f"+7{drawn.phone}", f"+7{drawn.phone}", False, {"digits": drawn.phone})),
        "email": ("EMAIL", identity, Rendered(fields["email"], fields["email"], False,  # type: ignore[arg-type]
                                              {"local": drawn.email_local, "domain": drawn.email_domain})),
        "birth_date": ("DOB", identity, Rendered(fields["birth_date"], fields["birth_date"], False,  # type: ignore[arg-type]
                                                 {"iso": fields["birth_date"]})),  # type: ignore[dict-item]
        "address.street": ("LOC", identity + ".home", Rendered(drawn.address.street, drawn.address.street, False,
                                                                 dict(address_rendered.parts))),
    })
    del name_rendered
