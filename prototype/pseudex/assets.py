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

from pseudex.morph import MORPH


class BundleNotLeased(RuntimeError):
    """Detection assets were requested while no bundle is loaded."""


@dataclass(frozen=True)
class NameAssets:
    dict_first: frozenset[str]
    dict_surnames: frozenset[str]
    name_set: frozenset[str]
    ambiguous: frozenset[str]
    cues: tuple[str, ...]
    stopwords: frozenset[str]
    surname_suffixes: tuple[str, ...]
    patronymic_suffixes: tuple[str, ...]
    patronymics_masc: tuple[str, ...]
    patronymics_femn: tuple[str, ...]


@dataclass(frozen=True)
class AddressAssets:
    street_gaz: frozenset[str]
    core_part: tuple[str, ...]
    street_first: re.Pattern[str]
    street_last: re.Pattern[str]
    # Lower-case, marker-and-house anchored: the shape a messenger produces.
    street_lower_first: re.Pattern[str]
    street_lower_last: re.Pattern[str]
    house: re.Pattern[str]
    apt: re.Pattern[str]
    mkr: re.Pattern[str]
    settlement: re.Pattern[str]
    index: re.Pattern[str]
    markerless: re.Pattern[str]
    addr_ctx: re.Pattern[str]
    prep_before: re.Pattern[str]
    numbered_st: re.Pattern[str]
    numbered_marked: re.Pattern[str]
    neg: re.Pattern[str]
    gap: re.Pattern[str]
    trail_house: re.Pattern[str]
    rural: re.Pattern[str]
    district: re.Pattern[str]
    # Month names, so a marker-less street can refuse a number that turns out
    # to be a date. Taken from the SAME list the quasi date pattern uses —
    # two copies of the Russian calendar would be two things to keep in step.
    month_after: tuple[str, ...]


@dataclass(frozen=True)
class QuasiAssets:
    birth_ctx: tuple[str, ...]
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


@dataclass(frozen=True)
class StructuredAssets:
    key_type: dict[str, str]
    key_stems: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RuPiiAssets:
    ctx_patterns: tuple[tuple[str, re.Pattern[str]], ...]
    inn_context: tuple[str, ...]


@dataclass(frozen=True)
class DetectionAssets:
    version: str
    names: NameAssets
    address: AddressAssets
    quasi: QuasiAssets
    context: ContextAssets
    structured: StructuredAssets
    ru_pii: RuPiiAssets
    priority: dict[str, int]
    lookalike: dict[str, str]


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
        name_set=frozenset(name_set),
        ambiguous=ambiguous,
        cues=tuple(raw["cues"]),
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
        core_part=tuple(raw["core_part"]),
        month_after=tuple(months),
        **compiled,
    )


def _build_quasi(raw: dict[str, object]) -> QuasiAssets:
    months = "|".join(raw["months"])
    # A written-out day+month, optionally with the year: `12 марта`, `3 мая 1985`.
    text_date = re.compile(
        r"\b(\d{1,2})\s+(?:" + months + r")(?:\s+(?:19|20)\d{2}(?:\s*г\w*)?)?",
        re.IGNORECASE,
    )
    return QuasiAssets(
        birth_ctx=tuple(raw["birth_ctx"]),
        text_date=text_date,
        medical=re.compile(raw["medical"], re.IGNORECASE),
    )


def _build_ru_pii(raw: dict[str, object]) -> RuPiiAssets:
    ctx_patterns = tuple(
        (entity_type, re.compile(rf"(?i:{cues})\D{{0,20}}?({shape})\b"))
        for entity_type, cues, shape in raw["ctx_types"]
    )
    return RuPiiAssets(ctx_patterns=ctx_patterns, inn_context=tuple(raw["inn_context"]))


def _build(payload: dict[str, object]) -> DetectionAssets:
    # Ordered pairs on the wire, because the prefix fallback in
    # `structured._key_type` resolves ties by order — see licensing/pack.py.
    key_stems = tuple((str(key), str(value)) for key, value in payload["structured"]["key_type"])
    key_type = dict(key_stems)
    return DetectionAssets(
        version=str(payload["version"]),
        names=_build_names(payload["names"]),
        # Months come from the QUASI section: one Russian calendar, two users.
        address=_build_address(payload["address"], payload["quasi"]["months"]),
        quasi=_build_quasi(payload["quasi"]),
        context=ContextAssets(
            deny=tuple(payload["context"]["deny"]),
            phone_trigger=tuple(payload["context"]["phone_trigger"]),
            passport_trigger=tuple(payload["context"].get("passport_trigger", ())),
            regions=frozenset(payload["context"]["regions"]),
            addr_intent=tuple(payload["context"]["addr_intent"]),
            place_ref=tuple(payload["context"]["place_ref"]),
            version_ctx=tuple(payload["context"]["version_ctx"]),
        ),
        structured=StructuredAssets(key_type=key_type, key_stems=key_stems),
        ru_pii=_build_ru_pii(payload["ru_pii"]),
        priority=dict(payload["priority"]),
        lookalike=dict(payload["lookalike"]),
    )


class Assets:
    """Connector to the leased asset state (external state -> class)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: DetectionAssets | None = None

    def load(self, plaintext: bytes) -> None:
        """Compile a decrypted bundle into the runtime structures.

        Called on the renewal path too, so it must be atomic from a reader's
        point of view: the new struct is built fully before it is published, and
        publishing is a single attribute assignment."""
        payload = json.loads(zlib.decompress(plaintext).decode("utf-8"))
        built = _build(payload)
        with self._lock:
            self._current = built

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
