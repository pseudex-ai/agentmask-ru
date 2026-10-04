"""In-memory registry of the leased detection assets.

The engine knows the SCHEMA of the assets and how to compile them; it holds none
of the values. They arrive as a bundle from the licensing server, are decrypted
in memory (never written to disk), and are loaded here.

THREE PROPERTIES THIS MODULE HAS TO GUARANTEE:

  1. **Fail-closed on absence.** Asking for assets that are not loaded raises
     `BundleNotLeased`, which the transport turns into a 503. The previous
     behaviour — an empty dictionary treated as a supported state — is exactly
     what must not happen: a PII gateway detecting with half its gazetteer leaks
     silently, and a silent leak is worse than a stopped service.

  2. **No per-request cost.** Every regex is compiled ONCE at load, not per call.
     A detector that recompiles the address grammar per message would make the
     lease the slowest thing in the product. Callers fetch the frozen struct once
     per function invocation and read attributes off it.

  3. **Real unload.** `unload()` drops the references so the strings are actually
     collected — it does not flip an `enabled` flag. A flag is one `if` to patch;
     absent data is not patchable.
"""

import gc
import json
import re
import threading
import zlib
from dataclasses import dataclass

from pseudex import bundle
from pseudex.morph import MORPH


class BundleNotLeased(RuntimeError):
    """Detection assets were requested while no bundle is loaded."""


@dataclass(frozen=True)
class NameAssets:
    dict_first: frozenset[str]
    dict_surnames: frozenset[str]
    # THE SAME TWO DICTIONARIES, READ LATIN. Derived here rather than shipped:
    # the transliteration table is already in the lease, so the Latin reading is
    # a pure function of it and of the Cyrillic bulk — shipping it would put the
    # same facts in the bundle twice and let the two drift apart. The engine
    # «knew» «Кукушкин» and did not know `Kukushkin`, and the evidence lived in
    # the wrong place: the Latin branch was positional (`_LATIN_PAIR_RE`) over a
    # 641-entry seed, while the surname itself sat in `dict_surnames` (196 800).
    latin_first: frozenset[str]
    latin_surnames: frozenset[str]
    name_set: frozenset[str]
    ambiguous: frozenset[str]
    cues: tuple[str, ...]
    # Предлоги, вводящие ЧЕЛОВЕКА («от», «к», «у», «для»), — второй сигнал
    # строчной фамилии, потерявшей заглавную. Арендуются, как и `cues`.
    anchor_preps: tuple[str, ...]
    # …и они же, скомпилированные ВПЛОТНУЮ перед словом: один раз на бандл, не
    # на каждое слово сообщения.
    anchor_re: re.Pattern[str]
    bio_cues: tuple[str, ...]
    never_cues: tuple[str, ...]
    stopwords: frozenset[str]
    surname_suffixes: tuple[str, ...]
    patronymic_suffixes: tuple[str, ...]
    patronymics_masc: tuple[str, ...]
    patronymics_femn: tuple[str, ...]


@dataclass(frozen=True)
class AddressAssets:
    street_gaz: frozenset[str]
    # Real settlements pymorphy reads only as a surname (no `Geox`) — «одоев»,
    # «венёв», «белёв». The ONLY evidence the lowercase settlement variant has,
    # and read only where an address structure (a street-type word or a settlement
    # marker) licenses it: a word on this list is a settlement in an address and a
    # surname elsewhere («фамилия одоев» stays a person). Same shape as
    # `street_gaz`, kept apart because the two lists gate different roles.
    settlement_gaz: frozenset[str]
    # The ГАР street vocabulary, lower-cased. A SEPARATE field from
    # `street_gaz` and never merged into it: `street_gaz` is nineteen
    # hand-tuned words and is the ONLY evidence the lower-case marker-less arm
    # has, which works precisely because a list that small cannot generalise to
    # prose. A vocabulary two orders of magnitude larger can — it contains
    # «Новая», «Мира», «Свободы», «Труда» — so it is only ever read by the arm
    # that also demands a street-type word and address intent.
    street_names: frozenset[str]
    # The names of that vocabulary that occur in a HUNDRED or more places. Read
    # by one caller for one decision — which register entry a mistyped street
    # meant, when several are one edit away. See `assets_source.
    # STREET_FREQUENT_MIN` for the measurement and the residual risk.
    street_frequent: frozenset[str]
    # Multi-word ГАР names, matched as WHOLE phrases. Fifty-five per cent of
    # the register, and kept apart from `street_names` because that set is
    # looked up token by token — «карла» alone must not claim a street.
    street_phrases: frozenset[str]
    # Street-type STEMS for the typo-tolerant arm, in the same two tiers the
    # regexes use: `nohouse` may stand on a cue alone, `house` needs a number.
    street_type_nohouse: frozenset[str]
    street_type_house: tuple[str, ...]
    core_part: tuple[str, ...]
    street_first: re.Pattern[str]
    street_last: re.Pattern[str]
    # Lower-case, marker-and-house anchored: the shape a messenger produces.
    street_lower_first: re.Pattern[str]
    street_lower_last: re.Pattern[str]
    # Same shape with an ABBREVIATED marker («ул. ленина 14»), which the two
    # above cannot carry — see the comment on `_ST_ABBR` in assets_source.
    street_abbr_lower: re.Pattern[str]
    # The same shape with the type word AFTER the name. Russian writes it
    # that way at least as often, and the name-first arm uses the FULL
    # type words only — so an abbreviation there matched nothing at all.
    street_abbr_lower_last: re.Pattern[str]
    # The house number SPOKEN («улица лермонтова тридцать восемь»). Kept apart
    # from the digit arms because a number word cannot hold a match down the
    # way a digit can — the gate lives in the engine, on the vocabulary.
    street_spoken_first: re.Pattern[str]
    street_spoken_last: re.Pattern[str]
    # House, corpus, flat and floor with SPOKEN numbers, and only in a chain
    # of two or more markers — one marker plus a number word is «программу дом
    # два», which is a television show and sits in our own negative set.
    spoken_chain: re.Pattern[str]
    # The address TAIL spoken — «строение пять», «корпус три», «квартира двести
    # двадцать девять». SUPPORT only, exactly like `apt`, whose digit-only shape
    # this fills in: the street arm found the address and stopped at the house
    # number, so the rest of it travelled to the model inside a span that was
    # already reported as found.
    spoken_apt: re.Pattern[str]
    # Marked street, lower case, NO house number — gated on morphology
    # in the engine, because the house number is the guard the others use.
    street_lower_nohouse: re.Pattern[str]
    house: re.Pattern[str]
    apt: re.Pattern[str]
    mkr: re.Pattern[str]
    settlement: re.Pattern[str]
    index: re.Pattern[str]
    markerless: re.Pattern[str]
    # Lower-case marker-less street. Gated on the street VOCABULARY only,
    # never on morphology — the capital is the missing signal and a
    # generalising gate would put it back the wrong way.
    markerless_lower: re.Pattern[str]
    # Строчная улица БЕЗ дома и БЕЗ слова-типа: «адрес репина», «на
    # бибиревская». Номер дома — единственный сигнал, державший предыдущие
    # строчные ветки; здесь его нет, и роль решают ЯКОРЬ и морфология в
    # `address.py` (ни то, ни другое регуляркой не выражается).
    street_nohouse_bare: re.Pattern[str]
    # Местный предлог ВПЛОТНУЮ — «на»/«по». Не весь `prep_before`: «в» и «у»
    # вводят обстоятельство и владельца и адресной роли не дают.
    street_nohouse_prep: re.Pattern[str]
    addr_ctx: re.Pattern[str]
    prep_before: re.Pattern[str]
    numbered_st: re.Pattern[str]
    numbered_marked: re.Pattern[str]
    neg: re.Pattern[str]
    # A unit of measure standing right after a number, which is what says the
    # number is a quantity and not a door. Anchored by the caller with `.match`
    # at the position just past the number, never searched.
    measure_after: re.Pattern[str]
    # A number glued to an age («31-летний»). Anchored by the caller with
    # `.match` just past the number, exactly like `measure_after`, and kept
    # apart from it: adding «лет» there would move arms already measured.
    age_after: re.Pattern[str]
    # A lower-case street name with NO type word, plus a house number — the
    # ordinary shape of a spoken Russian address. Deliberately loose; the four
    # gates that make it safe live in `address.py` because none of them is
    # expressible as a regex.
    street_bare_lower: re.Pattern[str]
    gap: re.Pattern[str]
    trail_house: re.Pattern[str]
    rural: re.Pattern[str]
    district: re.Pattern[str]
    # Month names, so a marker-less street can refuse a number that turns out
    # to be a date. Taken from the SAME list the quasi date pattern uses —
    # two copies of the Russian calendar would be two things to keep in step.
    month_after: tuple[str, ...]


@dataclass(frozen=True)
class SpokenAssets:
    """How a transcriber misspells a numeral.

    The PARSE of Russian numerals is published grammar and lives in the engine;
    which broken forms real transcripts produce is something we mined out of
    somebody else's corpora, so it is leased. Same split as everywhere: in the
    bundle what we tuned, in the binary every algorithm.
    """
    numeral_typos: dict[str, str]


@dataclass(frozen=True)
class QuasiAssets:
    birth_ctx: tuple[str, ...]
    # Подсказки, которые ищутся ЦЕЛЫМ СЛОВОМ. Отдельный список, а не общий:
    # «др» подстрокой сидит внутри «адрес» и «друг», и одна такая подсказка
    # замаскировала бы дату в каждом втором деловом письме.
    birth_ctx_words: re.Pattern[str] | None
    text_date: re.Pattern[str]
    medical: re.Pattern[str]


@dataclass(frozen=True)
class ContextAssets:
    deny: tuple[str, ...]
    phone_trigger: tuple[str, ...]
    passport_trigger: tuple[str, ...]
    regions: frozenset[str]
    addr_intent: tuple[str, ...]
    place_ref: tuple[str, ...]
    version_ctx: tuple[str, ...]
    org_cue: frozenset[str]
    personnel_cue: tuple[str, ...]


@dataclass(frozen=True)
class CompositeType:
    """РОДИТЕЛЬСКИЙ КЛЮЧ ТИПИЗУЕТ ДЕТЕЙ, и здесь описано КАК.

    `roles` переводит слово поля в роль части документа (series/number), `order`
    называет порядок частей — тождество документа, а не деталь оформления,
    `lengths` — сколько цифр несёт часть, по ним подмена раскладывается обратно
    по полям и листья складываются в целое на восстановлении, `required` — без
    каких частей объекта нет. Всё это leased TUNING: тип уже в `KEY_TYPE`, не
    хватало карты частей."""
    roles: dict[str, str]
    order: tuple[str, ...]
    lengths: dict[str, int]
    required: tuple[str, ...]


@dataclass(frozen=True)
class StructuredAssets:
    key_type: dict[str, str]
    key_stems: tuple[tuple[str, str], ...]
    composites: dict[str, CompositeType]


@dataclass(frozen=True)
class RuPiiAssets:
    ctx_patterns: tuple[tuple[str, re.Pattern[str]], ...]
    inn_context: tuple[str, ...]


@dataclass(frozen=True)
class TranslitAssets:
    """The measured transliteration tables (align/render/fold). Leased, not
    compiled: TUNING mined from control-arm outputs, not a standard. The ALGORITHM
    that uses them lives in pseudex.translit."""
    units: dict[str, tuple[str, ...]]
    default: dict[str, str]
    endings: tuple[str, ...]
    tables: tuple[dict[str, str], ...]
    fold: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FakeAssets:
    """The substitute pools the vault mints from. Leased TUNING — the values a
    competitor would copy; the mint LOGIC (uniqueness, round-trip survival,
    shape-mirroring) stays in pseudex.vault."""
    first: tuple[str, ...]
    last: tuple[str, ...]
    last_invariant: tuple[str, ...]
    cities: tuple[str, ...]
    streets: tuple[str, ...]
    house_max: int


@dataclass(frozen=True)
class DetectionAssets:
    version: str
    # Source lines the upstream licences oblige a running process to carry.
    # ФНС's ОТКРЫТАЯ ЛИЦЕНЗИЯ grants extraction and commercial reuse of ГАР on
    # exactly one condition — «указывать ссылку на источник открытых данных» —
    # and the loaded bundle is the only place where the obligation and the data
    # it applies to are in the same room.
    attribution: tuple[str, ...]
    names: NameAssets
    address: AddressAssets
    quasi: QuasiAssets
    spoken: SpokenAssets
    context: ContextAssets
    structured: StructuredAssets
    ru_pii: RuPiiAssets
    translit: TranslitAssets
    fakes: FakeAssets
    priority: dict[str, int]
    lookalike: dict[str, str]
    # Per-customer watermark (licensing/watermark.py). Inert for detection; it
    # exists so a tuning dump lifted from RAM names whose lease delivered it.
    # Empty when the server ran without PSEUDEX_WATERMARK_SECRET.
    watermark: str = ""


def _translit(text: str, table: dict[str, str]) -> str:
    return "".join(table.get(char, char) for char in text.lower())


def _build_names(raw: dict[str, object]) -> NameAssets:
    """Derive the runtime name structures from the leased lists.

    `name_set` and `ambiguous` are DERIVED here rather than shipped: they are a
    pure function of the seed lists plus morphology, so shipping them would put
    the same facts in the bundle twice and let the two drift apart."""
    seed = tuple(raw["seed_first_names"])
    diminutives = tuple(raw["diminutives"])
    translit_table = dict(raw["translit"])

    name_set = set(seed) | set(diminutives)
    name_set |= {_translit(name, translit_table) for name in name_set}
    anchor_preps = tuple(raw.get("anchor_preps", ()))

    # Seed names that are ALSO ordinary Russian words: вера, роман, любовь,
    # надежда. Matching those in any case masked `вера в успех` and `начнём роман
    # с клиентом` — ordinary business text, corrupted for no privacy gain. They
    # need a capital letter, exactly like the bulk dictionary.
    ambiguous = frozenset(
        name for name in name_set
        if (lambda parse: parse.is_known
            and not ({"Name", "Surn", "Patr"} & set(parse.tag.grammemes)))(MORPH.parse(name)[0])
    )
    return NameAssets(
        dict_first=frozenset(raw["dict_first"]),
        dict_surnames=frozenset(raw["dict_surnames"]),
        # ONE TABLE, TWO SCRIPTS. `_translit` is the same function that already
        # reads a seed name in Latin, applied to the bulk; it costs ~0.14 s once
        # per lease and removes the position dependency as a CLASS — `Kukushkin
        # Valeriy`, `Kukushkin`, `Fomin Vyacheslav` are no longer distinguishable
        # by mechanism.
        latin_first=frozenset(
            _translit(name, translit_table) for name in raw["dict_first"]),
        latin_surnames=frozenset(
            _translit(name, translit_table) for name in raw["dict_surnames"]),
        name_set=frozenset(name_set),
        ambiguous=ambiguous,
        cues=tuple(raw["cues"]),
        anchor_preps=anchor_preps,
        anchor_re=re.compile(
            r"(?i)\b(?:" + "|".join(re.escape(p) for p in anchor_preps) + r")\s+$")
        if anchor_preps else re.compile(r"(?!)"),
        bio_cues=tuple(raw["bio_cues"]),
        never_cues=tuple(raw["never_cues"]),
        stopwords=frozenset(raw["stopwords"]),
        surname_suffixes=tuple(raw["surname_suffixes"]),
        patronymic_suffixes=tuple(raw["patronymic_suffixes"]),
        patronymics_masc=tuple(raw["patronymics_masc"]),
        patronymics_femn=tuple(raw["patronymics_femn"]),
    )


def _build_address(raw: dict[str, object], months: list[str]) -> AddressAssets:
    # NO FLAGS HERE ON PURPOSE. Each pattern declares its own case sensitivity
    # with a leading `(?i)`, because it differs per pattern and getting it wrong
    # is silent: compiling the marker-less street pattern case-insensitively
    # turns `[А-ЯЁ][а-яё]+` from "a Capitalised word" into "any word", which made
    # "течение 12" an address, and those inflated LOC spans then outranked and
    # swallowed real NAME spans (measured: -12 PERSON on NEREL).
    compiled = {name: re.compile(source) for name, source in raw["patterns"].items()}
    return AddressAssets(
        street_gaz=frozenset(raw["street_gaz"]),
        settlement_gaz=frozenset(raw["settlement_gaz"]),
        street_names=frozenset(raw["street_names"]),
        street_frequent=frozenset(raw["street_frequent"]),
        street_phrases=frozenset(raw["street_phrases"]),
        street_type_nohouse=frozenset(raw["street_type_nohouse"]),
        # ORDERED, and longest-first, because `_exact_type` returns the FIRST
        # stem the token starts with and the answer decides which tier the
        # match is in. «площадк» and «площад» both prefix «площадка»; taking the
        # shorter one would put a trading platform in the tier that needs no
        # house number.
        street_type_house=tuple(sorted(raw["street_type_house"], key=len, reverse=True)),
        core_part=tuple(raw["core_part"]),
        month_after=tuple(months),
        **compiled,
    )


def _build_quasi(raw: dict[str, object]) -> QuasiAssets:
    months = "|".join(raw["months"])
    # A written-out day+month, optionally with the year: `12 марта`, `3 мая 1985`.
    # AND THE SPOKEN DATE. A birth date said aloud has no digit anywhere —
    # «двадцать первое сентября восьмидесятого года» — and every arm here
    # waited for one, so it reached the model in the clear (live v4,
    # derive-020, three of three repeats). The day is an ordinal, the year an
    # ordinal before «года», with or without the century said out loud. Both
    # still sit behind the birth-context gate below.
    day = (r"(?:(?:двадцать|тридцать)\s+)?(?:перв|втор|трет|четвёрт|четверт|пят|шест|седьм|восьм|девят"
           r"|десят|одиннадцат|двенадцат|тринадцат|четырнадцат|пятнадцат|шестнадцат|семнадцат"
           r"|восемнадцат|девятнадцат|двадцат|тридцат)(?:ое|ого|ый|ым|ой|ий|его|ье|ья|ьего)")
    # …AND «ГОДА» IS OPTIONAL WHEN THE YEAR CANNOT BE MISTAKEN FOR ANYTHING ELSE.
    # «одиннадцатого сентября пятьдесят пятого» and «двадцать третьего марта
    # тысяча девятьсот восемьдесят второго» are how the corpus's voice register
    # says a birth date, and both ended at the month: the year stayed outside
    # the span, next to a substitute carrying another year (seed-6060 run, 9 of
    # 9 spoken dates of birth). A spoken century, or a tens word followed by an
    # ordinal, or a decade ordinal («восьмидесятого») is a year on its own; a
    # bare ordinal («пятого») still needs «года», or «родился третьего марта
    # первого ребёнка» would end at the child.
    century = r"(?:тысяча\s+девятьсот|две\s+тысячи|тысяча|двухтысячн\w+|тысяча\s+девятисот\w+)"
    tens_card = r"(?:двадцать|тридцать|сорок|пятьдесят|шестьдесят|семьдесят|восемьдесят|девяносто)"
    tens_ord = r"(?:двадцат|тридцат|сороков|пятидесят|шестидесят|семидесят|восьмидесят|девяност)(?:ого|его)"
    unit_ord = r"[а-яё]{3,}(?:ого|его)"
    spoken_year = (r"(?:"
                   rf"\s+{century}(?:\s+{tens_card})?(?:\s+{unit_ord})?"
                   rf"|\s+{tens_card}\s+{unit_ord}"
                   rf"|\s+{tens_ord}"
                   rf"|\s+{unit_ord}\s+года?"
                   r")(?:\s+года?)?")
    text_date = re.compile(
        r"\b(\d{1,2})\s+(?:" + months + r")(?:\s+(?:19|20)\d{2}(?:\s*г\w*)?)?"
        r"|\b" + day + r"\s+(?:" + months + r")(?:" + spoken_year + r"|\s+(?:19|20)\d{2}(?:\s*г\w*)?)?",
        re.IGNORECASE,
    )
    words = tuple(raw.get("birth_ctx_words", ()))
    return QuasiAssets(
        birth_ctx=tuple(raw["birth_ctx"]),
        birth_ctx_words=(
            re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\.?\b", re.IGNORECASE)
            if words else None
        ),
        text_date=text_date,
        medical=re.compile(raw["medical"], re.IGNORECASE),
    )


def _build_spoken(raw: dict[str, object]) -> SpokenAssets:
    return SpokenAssets(numeral_typos=dict(raw["numeral_typos"]))


def _build_ru_pii(raw: dict[str, object]) -> RuPiiAssets:
    ctx_patterns = tuple(
        (entity_type, re.compile(rf"(?i:{cues})\D{{0,20}}?({shape})\b"))
        for entity_type, cues, shape in raw["ctx_types"]
    )
    return RuPiiAssets(ctx_patterns=ctx_patterns, inn_context=tuple(raw["inn_context"]))


def _build_translit(raw: dict[str, object]) -> TranslitAssets:
    units = {str(unit): tuple(opts) for unit, opts in raw["units"].items()}
    return TranslitAssets(
        units=units,
        # DEFAULT is the first rendering of each unit — derived here, not shipped,
        # exactly as the compiled engine used to derive it from the UNITS literal.
        default={unit: opts[0] for unit, opts in units.items()},
        endings=tuple(raw["endings"]),
        tables=tuple(dict(table) for table in raw["tables"]),
        fold=tuple((str(source), str(marker)) for source, marker in raw["fold"]),
    )


def _build_fakes(raw: dict[str, object]) -> FakeAssets:
    return FakeAssets(
        first=tuple(raw["first"]),
        last=tuple(raw["last"]),
        last_invariant=tuple(raw["last_invariant"]),
        cities=tuple(raw["cities"]),
        streets=tuple(raw["streets"]),
        house_max=int(raw["house_max"]),
    )


def _build_structured(raw: dict[str, object]) -> StructuredAssets:
    key_stems = tuple((str(key), str(value)) for key, value in raw["key_type"])
    composites: dict[str, CompositeType] = {}
    for entity_type, spec in (raw.get("composite_types") or {}).items():
        roles = {word: role for role, words in spec["roles"].items() for word in words}
        composites[str(entity_type)] = CompositeType(
            roles=roles,
            order=tuple(str(role) for role in spec["order"]),
            lengths={str(role): int(size) for role, size in spec["lengths"].items()},
            required=tuple(str(role) for role in spec["required"]),
        )
    return StructuredAssets(key_type=dict(key_stems), key_stems=key_stems,
                            composites=composites)


def _build(payload: dict[str, object]) -> DetectionAssets:
    return DetectionAssets(
        version=str(payload["version"]),
        attribution=tuple(payload["attribution"]),
        names=_build_names(payload["names"]),
        # Months come from the QUASI section: one Russian calendar, two users.
        address=_build_address(payload["address"], payload["quasi"]["months"]),
        quasi=_build_quasi(payload["quasi"]),
        spoken=_build_spoken(payload["spoken"]),
        context=ContextAssets(
            deny=tuple(payload["context"]["deny"]),
            phone_trigger=tuple(payload["context"]["phone_trigger"]),
            passport_trigger=tuple(payload["context"].get("passport_trigger", ())),
            regions=frozenset(payload["context"]["regions"]),
            addr_intent=tuple(payload["context"]["addr_intent"]),
            place_ref=tuple(payload["context"]["place_ref"]),
            version_ctx=tuple(payload["context"]["version_ctx"]),
            org_cue=frozenset(payload["context"]["org_cue"]),
            personnel_cue=tuple(payload["context"].get("personnel_cue", ())),
        ),
        # `_build_structured` is the one builder that reads BOTH halves — the
    # ordered key→type pairs and the composite map — so the pair order that
    # decides prefix ties is preserved by construction.
    structured=_build_structured(payload["structured"]),
        ru_pii=_build_ru_pii(payload["ru_pii"]),
        translit=_build_translit(payload["translit_machine"]),
        fakes=_build_fakes(payload["fakes"]),
        priority=dict(payload["priority"]),
        lookalike=dict(payload["lookalike"]),
        watermark=str(payload.get("_wm", "")),
    )


class Assets:
    """Connector to the leased asset state (external state -> class)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: DetectionAssets | None = None

    def load(self, plaintext: bytes) -> None:
        """Compile a decrypted bundle into the runtime structures.

        The lease now carries the FULL payload — bulk AND authored tuning (cue
        words, address regex, priority table, look-alike folds). Nothing is
        compiled into the engine, so a process that never leased has no tuning at
        all (load-bearing, fail-closed via `get`), and a memory dump yields only
        the current lease's tuning, not a blob decryptable offline forever (A2,
        docs/tz-tuning-in-lease.md). The bundle itself is age-sealed to the
        process key + nonce-wrapped by the caller, so this plaintext never
        touched disk.

        Called on the renewal path too, so it must be atomic from a reader's
        point of view: the new struct is built fully before it is published, and
        publishing is a single attribute assignment."""
        # SECTIONED framing (pseudex.bundle): the plaintext is a set of separately
        # compressed sections, decompressed → parsed → ZEROED one at a time, so the
        # whole ~8 MB payload never coexists as one contiguous region. A RAM carve
        # of one region yields at most one section, and the authored tuning is split
        # off from the semi-public bulk gazetteers (WS-7 RAM-carve hardening).
        #
        # HONEST LIMIT: this closes the single contiguous artifact and raises the
        # casual/non-root carve from `dd | json.loads` to "find and reassemble N
        # fragments", but it does NOT stop a determined LOCAL ROOT. Each section's
        # decoded JSON `str` still lingers unscrubbably after parse (CPython cannot
        # zero a `str`; only the mutable decompressed `bytearray` is zeroed here),
        # so root that instruments this load path or dumps at the right moment reads
        # a section's plaintext. That residual is the accepted theorem (root reads
        # its own RAM); the compensating controls are attribution + short TTL.
        if bundle.is_framed(plaintext):
            payload = bundle.unframe_payload(plaintext)  # parses + zeros each section
            built = _build(payload)
            del payload
        else:
            # Legacy whole-blob bundle (pre-WS-7 server). Zero the one buffer we can.
            raw = bytearray(zlib.decompress(plaintext))
            try:
                payload = json.loads(raw)
                built = _build(payload)
            finally:
                raw[:] = b"\x00" * len(raw)
            del payload
        with self._lock:
            self._current = built
        # No gc.collect() here: load() runs on every RENEWAL (~ttl/3), and a full-heap
        # collect over the ~350 MB model stack, on N workers sharing one cadence, is a
        # recurring pause. Each branch above already unreferenced `payload` and zeroed
        # the section/blob buffers; natural GC reclaims them. The forced collect stays
        # in unload() only (rare, terminal).

    def unload(self) -> None:
        """Drop the assets so the objects are actually collected.

        `gc.collect()` is deliberate: the frozensets participate in reference
        cycles through the compiled patterns, so without it they would survive
        until the next collection happened to run.

        WHAT THIS DOES NOT DO, despite an earlier comment here claiming it: erase
        the gazetteer from the process's address space. `free()` does not scrub,
        and CPython gives no way to zero a str. Measured on an expired worker: the
        marker word is still findable in freed pages, and RSS falls by 3 MB of
        ~490 MB because pymalloc returns an arena to the OS only when it is
        entirely empty. The guarantee is that the data is unreachable and
        detection refuses — not that a memory dump is clean."""
        with self._lock:
            self._current = None
        # Leased-vocabulary caches in other modules hold a SECOND copy of the
        # gazetteer as plain str tuples, keyed on bundle version and invisible to
        # this method — up to `maxsize` versions survived a revocation (pentest H3:
        # DeletionIndex._words behind address._street_index / names._misspelling_index).
        # Clear every leased-data cache so none outlives the lease. Imported LOCALLY:
        # this runs at unload time, when all modules are loaded, so there is no import
        # cycle with the modules that read ASSETS. A NEW version-keyed leased cache
        # must be added to this list.
        from pseudex import address, names, morph_places, vault
        for clear in (
            address._street_index.cache_clear,
            address._street_stems.cache_clear,
            address._spoken_house_after_for.cache_clear,
            names._misspelling_index.cache_clear,
            morph_places._word_number_for.cache_clear,
            vault._first_names_by_gender.cache_clear,
            vault._usable_streets.cache_clear,
            vault._invariant_last_names.cache_clear,
            vault._round_trip_last_names.cache_clear,
            vault._token_re.cache_clear,
        ):
            clear()
        gc.collect()

    @property
    def is_loaded(self) -> bool:
        return self._current is not None

    @property
    def version(self) -> str | None:
        current = self._current
        return None if current is None else current.version

    def get(self) -> DetectionAssets:
        # Single read into a local: the renewal thread may replace the reference
        # concurrently, and a reader must never see a half-swapped struct.
        current = self._current
        if current is None:
            raise BundleNotLeased(
                "detection assets are not leased — the process has no valid bundle"
            )
        return current


ASSETS = Assets()
