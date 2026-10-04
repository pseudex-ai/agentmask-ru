"""Edge-case stress test — FREE (no model): how stable is the substitution across
form transformations, mutable parts, identity collisions and round-trip robustness.

WHAT IT MEASURES, AND WHAT IT DOES NOT. For every check the REAL value is masked by
the engine, the FAKE is reformatted the way a chat model reformats a value it was
handed (notation, case, initials, word->digit, structured decomposition, separators,
leading zeros), and the result is unmasked through the REAL product path. The check
PASSES when the REAL value — or its correct derived form (initials, 8-notation,
nominative, digit form of a dictated number) — comes back, compared with +7<->8 and
case/initials awareness. A case where the real came back in another NOTATION is a
PASS: notation is presentation, the value is the identity.

The engine is NOT modified and NOT imported for the reformatting OR for the grading.
The reformatters are the instrument's own (a model can only work with the string it was
shown), and so are the address reader, the numeral reader and the equivalences that
grade the output — an instrument that grades with the engine's own parser measures its
own parser. ONE exception, named where it happens: `_address_case` renders the fake in
another case with `pseudex.morph_places.inflect_place`, because a hand-rolled Russian
suffix rule produced "Ивоваяой" and the harness would have reported its own grammar as
an engine defect. The grading of those two checks still uses the instrument's reader.

TWO UNMASK LEGS, AND THEY DIFFER. `/unmask`+`/unmask_chunk` (streaming content) go
through `redact.unmask_text`; `/unmask_arguments` (a tool call) goes through
`redact.unmask_arguments`, which parses the JSON and detokenises leaf by leaf. Both
are measured: several checks below pass on one leg and fail on the other, and a
single number would hide exactly that.

RANDOMNESS IS MEASURED, NOT AVERAGED AWAY. A substitute is minted from secrets, so a
check that depends on the fake carrying a leading zero samples 60 independent mints
and reports the RATE; every other check stops at the first failing mint and prints the
instance. Three consecutive runs of this file produce the same PASS/FAIL set.

ISOLATION. Every check gets a FRESH `Vault(':memory:')`. A shared vault makes one
check resolve through a token another check minted, which turns a measurement into
a measurement of the instrument's own case order (the naive version did this and
cross-contaminated its NAME cases).

Run:
    cd prototype && .venv/bin/python bench/edge_case_stress.py
    cd prototype && .venv/bin/python bench/edge_case_stress.py --json /tmp/ecs.json
    cd prototype && .venv/bin/python bench/edge_case_stress.py --selftest

Exit codes: 0 every check passes, 1 at least one REAL weakness (the run is a
measurement, so red is a result and not a broken run), 2 the instrument itself is
broken — its readers disagree with known answers, or a check that must be able to go
red no longer does. An instrument that cannot fail is not an instrument.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from testkit import load_dev_bundle  # noqa: E402

load_dev_bundle()

from pseudex import redact  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

DETECTOR = Detector()
CUSTOMER = "edge-stress"


# =====================================================================================
# 1. The instrument's own readers — correct by construction, self-tested at the end.
# =====================================================================================

# --- numeral words -> digits ---------------------------------------------------------
# Russian numerals inside one to three digits are ADDITIVE ("двести двадцать семь" =
# 200+20+7). The naive version substituted word by word from a dict, so the longer
# compound was rewritten first or the shorter word split the run and a dictated
# "шестьдесят шесть" became "60 6". Here a RUN of numeral words separated only by
# spaces/hyphens is summed once, and a non-numeral token ends the run.
_ONES = {
    "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2, "три": 3, "четыре": 4,
    "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
    "девятнадцать": 19,
}
_TENS = {
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60,
    "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
}
_HUNDREDS = {
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400, "пятьсот": 500,
    "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
}
_NUMERAL = {**_ONES, **_TENS, **_HUNDREDS}

_TOKEN_RE = re.compile(r"[А-Яа-яЁё]+|[^\sА-Яа-яЁё]+|\s+")


def words_to_digits(text: str) -> str:
    """Rewrite every maximal run of numeral words as one decimal number.

    "шестьдесят шесть" -> "66", "двадцать семь" -> "27", "двести двадцать семь" -> "227".
    """
    tokens = [(m.start(), m.end(), m.group(0)) for m in _TOKEN_RE.finditer(text)]
    out: list[str] = []
    i = 0
    while i < len(tokens):
        _, _, token = tokens[i]
        if token.lower() in _NUMERAL:
            values: list[int] = []
            j = i
            while j < len(tokens):
                _, _, token2 = tokens[j]
                if token2.lower() in _NUMERAL:
                    values.append(_NUMERAL[token2.lower()])
                    j += 1
                elif re.fullmatch(r"[\s\-]+", token2):
                    j += 1
                else:
                    break
            out.append(str(sum(values)))
            i = j
            continue
        out.append(token)
        i += 1
    return "".join(out)


def digits_of(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def fold_digits(text: str) -> str:
    """Digits only, with the +7<->8 fold applied to an 11-digit run: the country code
    written as 8 and as +7 is the SAME number, and treating that as a failure would
    report a notation difference as a defect."""
    d = digits_of(text)
    if len(d) == 11 and d[0] in "78":
        return "7" + d[1:]
    return d


def fold_phone(text: str) -> str:
    """Fold a phone to comparable digits, accepting the country code being absent:
    a model that drops the leading 7/8 still wrote the same subscriber number."""
    d = digits_of(text)
    if len(d) == 11 and d[0] in "78":
        d = d[1:]
    return d


# --- the address reader --------------------------------------------------------------
# One marker table, longest form first inside each group, each anchored so a marker
# cannot match inside a word ("пл" must not fire inside "теперь"). The value of a
# marker runs to the next marker or the sentence's comma.
_MARKERS: list[tuple[str, str]] = [
    ("flat", r"(?:квартир[а-яё]*|кв)(?![\-А-Яа-яЁё])\.?\s*№?\s*"),
    ("entrance", r"(?:подъезд[а-яё]*|под)(?![\-А-Яа-яЁё])\.?\s*№?\s*"),
    ("floor", r"(?:этаж[а-яё]*|эт)(?![\-А-Яа-яЁё])\.?\s*№?\s*"),
    ("office", r"(?:офис[а-яё]*|оф)(?![\-А-Яа-яЁё])\.?\s*№?\s*"),
    ("corpus", r"(?:корпус[а-яё]*|корп|строени[а-яё]*|стр)(?![\-А-Яа-яЁё])\.?\s*№?\s*"),
    ("house", r"(?:дом[а-яё]*|д)(?![\-А-Яа-яЁё])\.?\s*№?\s*"),
    ("street", r"(?:улиц[а-яё]*|ул|переул[а-яё]*|пер|проспект[а-яё]*|пр-?т|"
               r"бульвар[а-яё]*|б-?р|шоссе|набережн[а-яё]*|площад[а-яё]*|пл|"
               r"аллея|аллеи|тракт[а-яё]*|проезд[а-яё]*)(?![\-А-Яа-яЁё])\.?\s*№?\s*"),
]
_MARKER_RE = re.compile(
    r"(?<![А-Яа-яЁё])(" + "|".join(f"(?P<m{i}>{p})" for i, (_, p) in enumerate(_MARKERS)) + r")",
    re.IGNORECASE,
)
_MARKER_ROLE = {f"m{i}": role for i, (role, _) in enumerate(_MARKERS)}

_CYRILLIC_WORD_RE = re.compile(r"[А-Яа-яЁё]+")
_ADDRESS_NUMERIC_ROLES = ("house", "corpus", "flat", "entrance", "floor", "office")


def _numeric_or_word(chunk: str) -> str | None:
    """The value a numeric role carries: digits ("10", "10А"), a dictated numeral run
    ("двадцать семь" -> "27") or a letter group (a corpus "А")."""
    chunk = chunk.strip()
    m = re.match(r"(\d+[А-Яа-яЁё]?)", chunk)
    if m:
        return m.group(1)
    m = re.match(r"([А-Яа-яЁё][А-Яа-яЁё\-]*(?:[\s\-]+[А-Яа-яЁё\-]+)*)", chunk)
    if not m:
        return None
    words = [w for w in re.split(r"[\s\-]+", m.group(0).strip()) if w]
    if words and all(w.lower() in _NUMERAL for w in words):
        return words_to_digits(" ".join(words))
    return words[0]


def _take_value(role: str, chunk: str) -> str | None:
    """The value a role's chunk carries, or None when the chunk is another role's tail."""
    chunk = chunk.strip().strip(",;.").strip()
    if not chunk:
        return None
    if role == "street":
        # A street name is capitalised in the customer's writing and lower-case when
        # the model lowercases the fake — both are the same identity, so both are read.
        # A numeral where a name belongs is the house of the previous marker.
        m = re.match(r"([А-Яа-яЁё][А-Яа-яЁё\-]*(?:\s+[А-ЯЁа-яё][А-Яа-яЁё\-]*)*)", chunk)
        if not m or m.group(1).lower() in _NUMERAL:
            return None
        return m.group(1).strip()
    return _numeric_or_word(chunk)


_MARKER_WORD_RE = re.compile(r"[А-Яа-яЁё]+")
_MARKER_WORDS = {"улица", "улицы", "улице", "улицу", "ул", "переулок", "пер", "проспект",
                 "пр", "бульвар", "б", "шоссе", "набережная", "площадь", "пл", "аллея",
                 "тракт", "проезд", "дом", "д", "корпус", "корп", "строение", "стр",
                 "подъезд", "под", "этаж", "эт", "квартира", "кв", "офис", "оф", "адрес",
                 "доставка", "город", "г", "нет", "и"}


def parse_address(text: str) -> dict[str, str]:
    """Role -> value for an address in a sentence, JSON or a bare tool field.

    The naive version grabbed fields POSITIONALLY (`parts[1]` was "the house"), so a
    street written as two words ("Сиреневый бульвар") put the type word in the house
    slot. Here the marker names the role and the value is read from the marker's own
    chunk; a bare street with its type dropped is read backwards from the house.
    """
    found: list[tuple[int, int, str]] = []
    for m in _MARKER_RE.finditer(text):
        role = next((_MARKER_ROLE[g] for g, value in m.groupdict().items()
                     if value is not None), "")
        found.append((m.start(), m.end(), role))
    out: dict[str, str] = {}
    for idx, (start, value_start, role) in enumerate(found):
        next_start = found[idx + 1][0] if idx + 1 < len(found) else len(text)
        chunk = text[value_start:next_start]
        value = _take_value(role, chunk)
        if value is not None and role:
            out.setdefault(role, value)

    if "street" not in out:
        # The type word was dropped by the model ("Сосновая 67, кв 7"). The street is
        # the last capitalised word that is not a marker word, immediately before the
        # house; when the house has no marker either, it is the first word followed by
        # a number — and both rules require a number, so a sentence with no address in
        # it does not grow one.
        house_pos = next((start for start, _, role in found if role == "house"), None)
        if house_pos is not None:
            candidates = [m for m in _MARKER_WORD_RE.finditer(text[:house_pos])
                          if m.group(0)[:1].isupper()
                          and m.group(0).lower() not in _MARKER_WORDS]
            if candidates:
                out["street"] = candidates[-1].group(0)
        if "street" not in out:
            bare = re.search(r"([А-ЯЁ][А-Яа-яЁё\-]+)\s*,?\s+(\d+[А-Яа-яЁё]?)", text)
            if bare:
                out["street"] = bare.group(1)
                out.setdefault("house", bare.group(2))
    if "house" not in out and "street" in out:
        # "Сосновая 67" / "улица Сосновая 67" with no house marker.
        street_match = re.search(re.escape(out["street"]), text)
        if street_match:
            tail = re.match(r"\s*,?\s*(\d+[А-Яа-яЁё]?)", text[street_match.end():])
            if tail:
                out["house"] = tail.group(1)
    return out


_FIELD_ALIASES = {
    "street": "street", "street_name": "street", "streetname": "street",
    "ulica": "street", "ulitsa": "street", "sstreet": "street",
    "build": "house", "building": "house", "house": "house", "dom": "house",
    "housenumber": "house", "house_number": "house", "sbuild": "house",
    "nbuild": "house", "home": "house",
    "flat": "flat", "apartment": "flat", "apt": "flat", "kvartira": "flat",
    "kv": "flat", "sflat": "flat", "nflat": "flat", "room": "flat",
    "corpus": "corpus", "korpus": "corpus", "block": "corpus", "case": "corpus",
    "entrance": "entrance", "podezd": "entrance", "porch": "entrance",
    "floor": "floor", "etazh": "floor",
}
_FIELD_RE = re.compile(r'"([A-Za-zА-Яа-яЁё_]+)"\s*:\s*"([^"]*)"')


def parse_fields(text: str) -> dict[str, str]:
    """Role -> value out of a structured tool argument, keyed by the schema's own
    field names (street/build/flat, sflat/nflat, dom/korpus), with the address reader
    as the fallback for a value written as prose."""
    out: dict[str, str] = {}
    for key, value in _FIELD_RE.findall(text):
        role = _FIELD_ALIASES.get(key.lower().replace(".", "_"))
        if role and role not in out:
            out[role] = value.strip()
    for role, value in parse_address(text).items():
        out.setdefault(role, value)
    return out


# --- equivalence ---------------------------------------------------------------------
_STEM = 4


def _stem(word: str) -> str:
    """A four-letter stem with ё folded: "Иванову"/"Иванов" and "Петру"/"Пётр" are one
    word in different cases, which is what the round trip must be judged on."""
    return word.lower().replace("ё", "е")[:_STEM]


def _cyr_words(text: str) -> list[str]:
    return [w.lower() for w in _CYRILLIC_WORD_RE.findall(text)]


def name_equiv(region: str, expected: str, real_full: str) -> bool:
    """Initials-aware, order-tolerant name comparison.

    A full word in the region counts when it shares its stem with a word of the real
    name; a one-letter word counts when it is that word's initial. Every initial the
    expected form names must be present, and every full word in the region must belong
    to the real name — the second rule is what catches a FAKE left in place, which a
    "does the surname appear" test would happily pass.
    """
    region_words = _cyr_words(region)
    expected_words = _cyr_words(expected)
    real_words = _cyr_words(real_full)
    if not region_words or not expected_words or not real_words:
        return False

    def matches(word: str, pool: list[str]) -> bool:
        return any(_stem(word) == _stem(p) for p in pool)

    for word in region_words:
        if len(word) >= 3:
            if not matches(word, real_words):
                return False
        elif word not in {p[0] for p in real_words}:
            return False
    for word in expected_words:
        if len(word) >= 3:
            if not any(_stem(word) == _stem(r) for r in region_words):
                return False
        elif word not in {r[0] for r in region_words}:
            return False
    return True


def digits_equiv(region: str, expected: str, phone: bool = False) -> bool:
    fold = fold_phone if phone else fold_digits
    got, want = fold(region), fold(expected)
    return bool(got) and got == want


def numeric_equiv(region: str, expected: str) -> bool:
    """A number written in words is the same number: fold both sides first."""
    return digits_of(words_to_digits(region)) == digits_of(words_to_digits(expected))


def field_equiv(region: dict[str, str], expected: dict[str, str],
                real_full: str) -> bool:
    for role, want in expected.items():
        got = region.get(role)
        if not got:
            return False
        if role == "street":
            if not any(_stem(got) == _stem(w) for w in _cyr_words(want)):
                return False
        elif role == "name":
            if not name_equiv(got, want, real_full):
                return False
        elif not numeric_equiv(got, want):
            return False
    return True


# =====================================================================================
# 2. The reformatters — what a model does to the string it was shown.
# =====================================================================================

def to_8(masked: str) -> str:
    return re.sub(r"\+7", "8", masked, count=1)


def to_7(masked: str) -> str:
    return re.sub(r"(?<![\d])8(?=[\s\-(]*\d)", "+7", masked, count=1)


def strip_separators(masked: str) -> str:
    return re.sub(r"(?<=\d)[\s\-\(\)](?=\d)", "", masked)


def tighten(masked: str) -> str:
    """Digits only, keeping whatever country code was written."""
    return re.sub(r"[^\d+]", "", masked)


def drop_country_code(masked: str) -> str:
    return re.sub(r"\+?[78](?=[\s\-(]*\d)", "", masked, count=1)


def _name_parts(masked: str) -> list[str]:
    return re.findall(r"[А-ЯЁ][а-яё\-]+", masked)


def _replace_last_words(text: str, count: int, build) -> str:
    """Rewrite the LAST `count` capitalised words of the frame in place.

    A reformatter must keep the sentence around the value: the naive version returned
    the bare name, so the harness could not find its own prefix in the output and
    reported an engine failure that was the instrument's.
    """
    parts = list(re.finditer(r"[А-ЯЁ][а-яё\-]+", text))
    if len(parts) < count:
        return text
    window = parts[-count:]
    words = [p.group(0) for p in window]
    replace = build(words)
    if replace is None:
        return text
    return text[:window[0].start()] + replace + text[window[-1].end():]


def initials(masked: str, dots: bool = True, first: bool = False) -> str:
    def build(parts: list[str]) -> str | None:
        if len(parts) < 3:
            return None
        surname, given, patronymic = parts[-3], parts[-2], parts[-1]
        ini = f"{given[0]}.{patronymic[0]}." if dots else f"{given[0]}{patronymic[0]}"
        return f"{ini} {surname}" if first else f"{surname} {ini}"

    return _replace_last_words(masked, 3, build)


def without_patronymic(masked: str) -> str:
    def build(parts: list[str]) -> str | None:
        return f"{parts[-3]} {parts[-2]}" if len(parts) >= 3 else None

    return _replace_last_words(masked, 3, build)


def reversed_name(masked: str) -> str:
    def build(parts: list[str]) -> str | None:
        return f"{parts[-2]} {parts[-3]}" if len(parts) >= 3 else (
            f"{parts[-1]} {parts[-2]}" if len(parts) >= 2 else None)

    parts = list(re.finditer(r"[А-ЯЁ][а-яё\-]+", masked))
    count = 3 if len(parts) >= 3 else 2
    return _replace_last_words(masked, count, build)


def _address_case(masked: str, case: str) -> str:
    """The fake written in another case: use the REAL Russian morphology rather than a
    hand-rolled suffix rule, which produced "Ивоваяой" in the naive version."""
    from pseudex import morph_places

    phrase = re.search(r"(?:улиц[а-яё]*|ул|переул[а-яё]*|проспект[а-яё]*|бульвар[а-яё]*|"
                       r"шоссе|набережн[а-яё]*|проезд[а-яё]*)\s+[А-ЯЁ][а-яё\-]+", masked)
    if not phrase:
        return masked
    try:
        inflected = morph_places.inflect_place(phrase.group(0), case)
    except Exception:  # noqa: BLE001 — an instrument failure must show as SKIP, not a crash
        return masked
    if not inflected or inflected == phrase.group(0):
        return masked
    return masked.replace(phrase.group(0), inflected)


def address_structured(masked: str, fields: tuple[str, ...]) -> str:
    """The decomposition a model performs when the tool schema wants separate fields.

    The naive version emitted `{street: parts[0], build: parts[1], flat: parts[-1]}`
    and so put the street TYPE word in the house slot and the house in the flat slot
    for any two-word street name. Here the roles come from the address reader.
    """
    roles = parse_address(masked)
    payload = {name: roles.get(role, "") for name, role in
               (("street", "street"), ("build", "house"), ("flat", "flat"),
                ("corpus", "corpus"), ("entrance", "entrance"), ("floor", "floor"))}
    keep = [f for f in fields]
    return json.dumps({k: payload[k] for k in keep}, ensure_ascii=False)


def _strip_leading_zeros(masked: str) -> str:
    """Every numeric group loses its leading zeros — what a spreadsheet or a JSON number
    does to an identifier it stores as a number."""
    return re.sub(r"(?<![\d])0+(\d)", r"\1", masked)


def _strip_one_leading_zero(masked: str) -> str:
    """The single leading zero of the whole value — what a model does when it "cleans
    up" a card number it was handed."""
    return re.sub(r"(?<![\d])0", "", masked, count=1)


def date_slash(masked: str) -> str:
    return masked.replace(".", "/")


def date_dash(masked: str) -> str:
    return masked.replace(".", "-")


def glued(masked: str) -> str:
    return re.sub(r"\s+", "", masked)


def dashed(masked: str) -> str:
    return re.sub(r"\s+", "-", masked)


# =====================================================================================
# 3. The check model.
# =====================================================================================

@dataclass
class Case:
    cid: str
    category: str
    title: str
    kind: str                      # roundtrip | identity | collision
    type: str = ""
    pre: str = ""
    post: str = ""
    real: str = ""                 # the value as the customer wrote it
    expected: str = ""             # the derived form that must come back
    transform: object = None       # callable(masked) -> str
    mode: str = "text"             # text | digits | phone | name | address | date | fields
    legs: tuple[str, ...] = ("content",)
    leaf: str = "value"            # the key the args leg wraps a plain value under
    known: str = ""                # "" | "phase4-1" | "phase4-2"
    note: str = ""
    require_change: bool = False   # SKIP when the simulated model transform was a no-op
    value_only: bool = False       # apply the transform to the value, not the cue word
    zero_precondition: bool = False  # SKIP unless the fake carries a leading zero
    repeats: int = 1               # independent mints the check must survive
    skip: str = ""                 # set when the precondition for the check was not met
    # identity/collision
    forms: tuple[str, ...] = ()
    core: str = "street_house"     # what must stay one fake
    part: str = ""                 # the mutable part that must stay distinct
    must_differ: bool = False      # collision: the real cores differ, the fakes must too


@dataclass
class Result:
    cid: str
    category: str
    title: str
    kind: str
    status: str                    # PASS | FAIL | SKIP
    known: str
    type: str = ""
    real: str = ""
    masked: str = ""
    reformed: str = ""
    expected: str = ""
    detail: str = ""
    legs: dict[str, str] = field(default_factory=dict)


def _fresh_vault() -> Vault:
    return Vault(":memory:", CUSTOMER)


def _mask(vault: Vault, value: str) -> str:
    return redact.mask_text(value, vault, DETECTOR.detect(value))


def _region_content(back: str, case: Case) -> str | None:
    """The part of the output that must carry the restored value.

    Searched case-insensitively: a model that lowercases the whole message lowercases
    the inert words too, and failing to find the instrument's own prefix would be
    reported as an engine defect.
    """
    start = 0
    if case.pre:
        m = re.search(re.escape(case.pre), back, re.IGNORECASE)
        if not m:
            return None
        start = m.end()
    end = len(back)
    if case.post:
        ends = list(re.finditer(re.escape(case.post), back, re.IGNORECASE))
        if not ends:
            return None
        end = ends[-1].start()
    if end < start:
        return None
    return back[start:end]


def _args_input(case: Case, transformed: str) -> str:
    if case.mode == "fields":
        return transformed
    return json.dumps({case.leaf: transformed}, ensure_ascii=False)


def _region_args(back: str, case: Case) -> str | None:
    try:
        payload = json.loads(back)
    except Exception:  # noqa: BLE001
        return None
    if case.mode == "fields":
        if not isinstance(payload, dict):
            return None
        return json.dumps(payload, ensure_ascii=False)
    if not isinstance(payload, dict):
        return None
    value = payload.get(case.leaf)
    return value if isinstance(value, str) else None


def date_equiv(region: str, expected: str) -> bool:
    """Day/month/year as NUMBERS: "05.03.1998" and "5.3.1998" are one date and zero
    padding is notation. Same notation must not be demanded, or a padded real coming
    back unpadded would be reported as a defect."""
    def parts(text: str) -> tuple[int, int, int] | None:
        m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})", text)
        if not m:
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
            if not m:
                return None
            return int(m.group(3)), int(m.group(2)), int(m.group(1))
        day, month, year = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return (day, month, 1900 + year if year < 100 else year)

    got, want = parts(region), parts(expected)
    return got is not None and got == want


def _judge(case: Case, region: str) -> bool:
    if case.mode in ("digits", "phone"):
        return digits_equiv(region, case.expected or case.real,
                            phone=case.mode == "phone")
    if case.mode == "date":
        return date_equiv(region, case.expected or case.real)
    if case.mode == "compact":
        fold = lambda s: re.sub(r"[^0-9A-Za-zА-Яа-яЁё]", "", s).lower()  # noqa: E731
        want = fold(case.expected or case.real)
        return bool(want) and want in fold(region)
    if case.mode == "name":
        return name_equiv(region, case.expected or case.real, case.real)
    if case.mode == "address":
        want = parse_address(case.expected or case.real)
        got = parse_address(region)
        if not want.get("street"):
            return False
        if not got.get("street"):
            return False
        if not any(_stem(got["street"]) == _stem(w) for w in _cyr_words(want["street"])):
            return False
        for role in _ADDRESS_NUMERIC_ROLES:
            if role in want:
                if role not in got or not numeric_equiv(got[role], want[role]):
                    return False
        return True
    want = case.expected or case.real
    norm = lambda s: re.sub(r"\s+", " ", s.lower()).strip()  # noqa: E731
    return norm(want) in norm(region) or norm(region) in norm(want)


def _judge_fields(case: Case, region: str) -> bool:
    want = parse_address(case.expected or case.real)
    if not want:
        return False
    got = parse_fields(region)
    return field_equiv(got, want, case.real)


def _apply_transform(case: Case, masked: str) -> str:
    """The model's reformatting. `value_only` keeps the instrument's cue word out of
    the transform, so "separators stripped" means the VALUE's separators were stripped
    and not the space between the label and the value — otherwise the check would
    measure a glued label, which is a different (and separately reported) weakness."""
    if not case.value_only:
        return case.transform(masked)
    region = _region_content(masked, case)
    if region is None:
        return case.transform(masked)
    return masked.replace(region, case.transform(region), 1)


def _one_roundtrip(case: Case, vault: Vault, masked: str) -> tuple[bool, str, dict[str, str]]:
    transformed = _apply_transform(case, masked)
    verdicts: list[tuple[str, bool, str]] = []
    legs: dict[str, str] = {}
    for leg in case.legs:
        if leg == "content":
            back = redact.unmask_text(transformed, vault)
            region = _region_content(back, case)
        else:
            back = redact.unmask_arguments(_args_input(case, transformed), vault)
            region = _region_args(back, case)
        legs[leg] = back
        if region is None:
            verdicts.append((leg, False, "region not found in the output"))
            continue
        ok = _judge_fields(case, region) if case.mode == "fields" else _judge(case, region)
        verdicts.append((leg, ok, region))
    ok_all = all(ok for _, ok, _ in verdicts)
    detail = ("; ".join(f"{leg}: {why!r}" for leg, ok, why in verdicts if not ok)
              if not ok_all else "; ".join(f"{leg}: ok" for leg, _, _ in verdicts))
    return ok_all, detail, legs


def run_roundtrip(case: Case, corrupt: bool = False) -> Result:
    result = Result(cid=case.cid, category=case.category, title=case.title,
                    kind=case.kind, status="FAIL", known=case.known, type=case.type,
                    real=case.real, expected=case.expected or case.real)
    if case.skip:
        result.status = "SKIP"
        result.detail = case.skip
        return result
    frame = f"{case.pre}{case.real}{case.post}"
    attempts: list[tuple[str, str, dict[str, str]]] = []
    for _ in range(max(case.repeats, 1)):
        vault = _fresh_vault()
        masked = _mask(vault, frame)
        if case.zero_precondition:
            # Bounded re-mint for the SAME vault the check runs against: a leading-zero
            # case that mints no leading zero has not been exercised and must SKIP.
            for _ in range(80):
                region = _region_content(masked, case)
                if region is not None and re.search(r"(?<![\d])0\d", region):
                    break
                vault = _fresh_vault()
                masked = _mask(vault, frame)
            else:
                result.status = "SKIP"
                result.detail = "no fake with a leading zero was minted in 80 tries"
                return result
        if case.require_change and _apply_transform(case, masked) == masked:
            result.status = "SKIP"
            result.masked = masked
            result.detail = ("the simulated model transform did not change the fake "
                             "(instrument precondition)")
            return result
        if corrupt:
            region = _region_content(masked, case)
            if region:
                mangled = re.sub(r"\d", "0", region)
                mangled = re.sub(r"[А-Яа-яЁё]", "Я", mangled)
                masked = masked.replace(region, mangled, 1)
        ok, detail, legs = _one_roundtrip(case, vault, masked)
        attempts.append((masked, _apply_transform(case, masked), legs, ok, detail))
        if not ok and not case.zero_precondition:
            break   # fail fast, except for a sampled rate
    failures = [a for a in attempts if not a[3]]
    result.status = "FAIL" if failures else "PASS"
    result.masked, result.reformed, result.legs = attempts[-1][0], attempts[-1][1], attempts[-1][2]
    result.detail = attempts[-1][4]
    if case.repeats > 1:
        result.detail = f"{len(failures)}/{len(attempts)} mints failed; " + result.detail
    if len(attempts) > 1 and failures:
        first = failures[0]
        result.detail += (f" | first failing mint: masked={first[0]!r} "
                          f"reformed={first[1]!r} back={first[2]}")
    return result


# --- identity / collision -------------------------------------------------------------

def _masked_core(masked: str) -> str:
    """The identity of an address as the model sees it: street + house, the part D-081
    keeps ONE substitute for across mutable details."""
    roles = parse_address(masked)
    street = roles.get("street", "")
    house = roles.get("house", "")
    return f"{street.lower()}|{house}"


def _masked_part(masked: str, part: str) -> str | None:
    return parse_address(masked).get(part)


def _name_core(masked: str) -> str:
    """The identity of a person as the model sees it: the surname's stem plus the given
    name's initial. D-081 renders ONE substitute at the granularity the mention named —
    "Панов Герман Степанович" and "Панов Г. С." are one fake written two ways — so the
    comparison must be at that granularity and not on the raw strings."""
    parts = _name_parts(masked)
    if not parts:
        return ""
    return _stem(parts[0]) + "|" + (parts[1][0].lower() if len(parts) > 1 else "")


def _core_of(case: Case, masked: str) -> str:
    if case.type == "NAME":
        return _name_core(masked)
    if case.type == "LOC":
        return _masked_core(masked)
    return masked


def run_identity(case: Case) -> Result:
    vault = _fresh_vault()
    masked = [_mask(vault, form) for form in case.forms]
    result = Result(cid=case.cid, category=case.category, title=case.title,
                    kind=case.kind, status="FAIL", known=case.known, type=case.type,
                    real=" || ".join(case.forms), expected=case.core,
                    masked=" || ".join(masked), reformed="")
    cores = {_core_of(case, m) for m in masked}
    problems: list[str] = []
    if len(cores) != 1:
        problems.append(f"core forked: {sorted(cores)}")
    elif not all(cores):
        problems.append(f"core unreadable: {sorted(cores)}")
    if case.part:
        values = [_masked_part(m, case.part) for m in masked]
        if any(value is None for value in values):
            problems.append(f"part {case.part!r} unreadable: {values}")
        elif len(set(values)) != len(values):
            problems.append(f"part {case.part!r} collided: {values}")
    result.status = "PASS" if not problems else "FAIL"
    result.detail = "; ".join(problems) if problems else "one core, parts distinct"
    return result


def run_collision(case: Case) -> Result:
    vault = _fresh_vault()
    masked = [_mask(vault, form) for form in case.forms]
    result = Result(cid=case.cid, category=case.category, title=case.title,
                    kind=case.kind, status="FAIL", known=case.known, type=case.type,
                    real=" || ".join(case.forms), expected="distinct substitutes",
                    masked=" || ".join(masked), reformed="")
    problems: list[str] = []
    if case.part:
        values = [_masked_part(m, case.part) for m in masked]
        if len({v for v in values if v is not None}) != len(case.forms):
            problems.append(f"part {case.part!r} collided: {values}")
    if case.must_differ:
        # Two DIFFERENT identities must not answer as one. For an address the identity
        # is street+house (the mutable parts have their own check above); for every
        # other type the whole substitute is the identity.
        reads = ([_masked_core(m) for m in masked] if case.type == "LOC" else masked)
        if len(set(reads)) != len(reads):
            problems.append(f"cores collided: {reads}")
    if len(set(masked)) != len(masked) and not case.part:
        problems.append(f"substitutes identical: {masked}")
    result.status = "PASS" if not problems else "FAIL"
    result.detail = "; ".join(problems) if problems else "distinct"
    return result


# =====================================================================================
# 4. The checks.
# =====================================================================================

def R(cid, category, title, real, transform, mode, expected="", legs=("content",),
      pre="", post="", type="", leaf="value", known="", note="",
      repeats=1, value_only=False, zero_precondition=False, require_change=False):
    return Case(cid=cid, category=category, title=title, kind="roundtrip", type=type,
                pre=pre, post=post, real=real, expected=expected, transform=transform,
                mode=mode, legs=legs, leaf=leaf, known=known, note=note,
                repeats=repeats, value_only=value_only,
                zero_precondition=zero_precondition, require_change=require_change)


PHONE_REAL = "+7 916 402-11-87"
NAME_REAL = "Иванов Пётр Сергеевич"
ADDR_REAL = "улица Тверитина, дом 10, квартира 7"
ADDR_DICTATED = "улица Тверитина, дом десять, квартира семь"
ADDR_BIG = "улица Тверитина, дом двести двадцать семь, квартира триста шесть"

CASES: list[Case] = [
    # ------------------------------------------------------------------ A. phone
    R("A1", "A", "PHONE: +7 -> 8, separators kept", PHONE_REAL, to_8, "phone",
      pre="Позвоните мне на ", post=" пожалуйста", type="PHONE"),
    R("A2", "A", "PHONE: +7 -> 8, separators stripped",
      PHONE_REAL, lambda m: strip_separators(to_8(m)), "phone",
      pre="Телефон: ", post="", type="PHONE"),
    R("A3", "A", "PHONE: +7 kept, separators stripped",
      PHONE_REAL, strip_separators, "phone",
      pre="Телефон: ", post="", type="PHONE"),
    R("A4", "A", "PHONE: all separators stripped (digits only)",
      PHONE_REAL, tighten, "phone",
      pre="Телефон: ", post="", type="PHONE", value_only=True),
    R("A5", "A", "PHONE: country code dropped by the model",
      PHONE_REAL, drop_country_code, "phone",
      pre="Телефон: ", post="", type="PHONE"),
    R("A6", "A", "PHONE: human grouping 8 (xxx) xxx-xx-xx",
      PHONE_REAL, lambda m: re.sub(r"\+7", "8", m, count=1).replace(" ", " (", 1).replace("-", " "),
      "phone", pre="Телефон: ", post="", type="PHONE"),
    R("A7", "A", "PHONE: real already in 8-notation, model writes +7",
      "8 916 402-11-87", to_7, "phone",
      pre="Телефон: ", post="", type="PHONE"),

    # ------------------------------------------------------------------ A. name
    R("A8", "A", "NAME -> initials 'Сорокин М.С.'", NAME_REAL, initials, "name",
      expected="Иванов П.С.", pre="Клиент ", post=" оформил заказ", type="NAME"),
    R("A9", "A", "NAME -> initials without dots 'Сорокин МС'",
      NAME_REAL, lambda m: initials(m, dots=False), "name",
      expected="Иванов ПС", pre="Клиент ", post=" оформил заказ", type="NAME"),
    R("A10", "A", "NAME -> initials first 'М.С. Сорокин'",
      NAME_REAL, lambda m: initials(m, first=True), "name",
      expected="П.С. Иванов", pre="Клиент ", post=" оформил заказ", type="NAME"),
    R("A11", "A", "NAME -> reversed order 'Иванов -> Пётр Иванов'", NAME_REAL,
      reversed_name, "name", expected="Пётр Иванов",
      pre="Клиент ", post=" оформил заказ", type="NAME"),
    R("A12", "A", "NAME -> patronymic dropped 'Иванов Пётр'",
      NAME_REAL, without_patronymic, "name", expected="Иванов Пётр",
      pre="Клиент ", post=" оформил заказ", type="NAME"),
    R("A13", "A", "NAME -> nominative (real was declined)",
      "Иванову Петру Сергеевичу", lambda m: m, "name",
      expected="Иванов Пётр Сергеевич",
      pre="Позвоните ", post=" сегодня", type="NAME"),
    R("A14", "A", "NAME lowercased by the model (content leg)", NAME_REAL,
      lambda m: m.lower(), "name", legs=("content",),
      pre="", post="", type="NAME", repeats=3,
      note="the same fake resolves on the tool leg — see A15"),
    R("A15", "A", "NAME lowercased by the model (tool-arg leg)", NAME_REAL,
      lambda m: m.lower(), "name", legs=("args",), leaf="recipient",
      pre="", post="", type="NAME", repeats=3),

    # ------------------------------------------------------------------ A. address
    R("A16", "A", "ADDRESS: dictated house, model writes digits",
      ADDR_DICTATED, words_to_digits, "address", legs=("content", "args"),
      pre="Доставка: ", post="", type="LOC",
      known="phase4-1", note="the exact phase-4 scenario, with the compound numeral reader fixed"),
    R("A17", "A", "ADDRESS: 3-digit dictated number collapses correctly",
      ADDR_BIG, words_to_digits, "address", legs=("content",),
      pre="Доставка: ", post="", type="LOC"),
    R("A18", "A", "ADDRESS: structured {street,build,flat} (tool leg)",
      ADDR_REAL, lambda m: address_structured(m, ("street", "build", "flat")),
      "fields", legs=("args",), pre="", post="", type="LOC"),
    R("A19", "A", "ADDRESS: structured {street,build,flat} (content leg)",
      ADDR_REAL, lambda m: address_structured(m, ("street", "build", "flat")),
      "fields", legs=("content",), pre="", post="", type="LOC"),
    R("A20", "A", "ADDRESS: structured with entrance/floor (tool leg)",
      "улица Тверитина, дом 10, корпус 3, подъезд 2, этаж 5, квартира 7",
      lambda m: address_structured(m, ("street", "build", "corpus", "entrance", "floor", "flat")),
      "fields", legs=("args",), pre="", post="", type="LOC"),
    R("A21", "A", "ADDRESS: structured, dictated house kept in words (tool leg)",
      ADDR_DICTATED, lambda m: address_structured(m, ("street", "build", "flat")),
      "fields", legs=("args",), pre="", post="", type="LOC", known="phase4-1"),
    R("A22", "A", "ADDRESS: separators/abbreviations stripped",
      ADDR_REAL, lambda m: re.sub(r"\bулица\b", "ул.", m).replace("дом ", "д.")
      .replace("квартира ", "кв.").replace(",", ""), "address", legs=("content", "args"),
      pre="Доставка: ", post="", type="LOC"),
    R("A23", "A", "ADDRESS: fake written in the prepositional case",
      ADDR_REAL, lambda m: _address_case(m, "loct"), "address", legs=("content",),
      pre="Доставка: ", post="", type="LOC", require_change=True,
      note="the fake's new case is rendered by the engine's morphology (see the header)"),
    R("A24", "A", "ADDRESS: street-type marker dropped ('Сосновая 67')",
      ADDR_REAL, lambda m: re.sub(r"улиц[а-яё]*\s+", "", m), "address",
      legs=("content",), pre="Доставка: ", post="", type="LOC"),
    R("A25", "A", "ADDRESS: fake street lowercased",
      ADDR_REAL, lambda m: m.lower(), "address", legs=("content",),
      pre="Доставка: ", post="", type="LOC"),

    # ------------------------------------------------- A. structured identifiers
    R("A26", "A", "PASSPORT: separators stripped",
      "паспорт 4512 345678", strip_separators, "digits", expected="4512345678",
      pre="", post="", type="PASSPORT"),
    R("A27", "A", "PASSPORT: leading zeros of the series stripped",
      "паспорт 4512 345678", _strip_leading_zeros, "digits", expected="4512345678",
      pre="", post="", type="PASSPORT", repeats=60, zero_precondition=True),
    R("A28", "A", "SNILS: separators stripped",
      "СНИЛС 123-456-789 01", strip_separators, "digits", expected="12345678901",
      pre="", post="", type="SNILS"),
    R("A29", "A", "SNILS: leading zero of the first group stripped",
      "СНИЛС 123-456-789 01", _strip_leading_zeros, "digits", expected="12345678901",
      pre="", post="", type="SNILS", repeats=60, zero_precondition=True),
    R("A30", "A", "INN: space grouping stripped",
      "ИНН 7784268465", strip_separators, "digits", expected="7784268465",
      pre="", post="", type="INN"),
    R("A31", "A", "CARD: separators stripped",
      "карта 4276 1234 5678 9012", strip_separators, "digits",
      expected="4276123456789012", pre="", post="", type="CARD"),
    R("A32", "A", "CARD: leading zero of the MII group stripped",
      "карта 4276 1234 5678 9012", _strip_leading_zeros, "digits",
      expected="4276123456789012", pre="", post="", type="CARD",
      repeats=60, zero_precondition=True),
    R("A33", "A", "DATE: '.' -> '/' separators",
      "Дата рождения 21.01.1979", date_slash, "digits", expected="21011979",
      pre="", post="", type="DOB"),
    R("A34", "A", "DATE: '.' -> '-' separators",
      "Дата рождения 21.01.1979", date_dash, "digits", expected="21011979",
      pre="", post="", type="DOB"),
    R("A35", "A", "DATE: padded day/month unpadded by the model",
      "Дата рождения 05.03.1998", _strip_leading_zeros, "date", expected="05.03.1998",
      pre="", post="", type="DOB", repeats=60, zero_precondition=True),

    # ------------------------------------------------------- A. v6 document shapes
    R("A36", "A", "OMS_ENP: separators stripped",
      "Полис ОМС 0030869788914847", strip_separators, "digits",
      expected="0030869788914847", pre="", post="", type="OMS_ENP"),
    R("A37", "A", "IBAN: spaces stripped",
      "IBAN RU3178778932879217421809679290810", glued, "compact",
      expected="RU3178778932879217421809679290810", pre="", post="", type="IBAN"),
    R("A38", "A", "IBAN: lowercased",
      "IBAN RU3178778932879217421809679290810", lambda m: m.lower(), "compact",
      expected="ru3178778932879217421809679290810", pre="", post="", type="IBAN"),
    R("A39", "A", "VIN: lowercased",
      "VIN X96WVZCBZXB6V4218", lambda m: m.lower(), "compact",
      expected="x96wvzcbzxb6v4218", pre="", post="", type="VIN"),
    R("A40", "A", "VIN: grouped in fours",
      "X96WVZCBZXB6V4218", lambda v: " ".join(v[i:i + 4] for i in range(0, len(v), 4)),
      "compact", expected="X96WVZCBZXB6V4218", pre="номер кузова ", post="", type="VIN",
      value_only=True),
    R("A41", "A", "PTS_NUMBER: separators stripped",
      "78 ЮЩ 778932", glued, "compact", expected="78ЮЩ778932",
      pre="ПТС ", post="", type="PTS_NUMBER", value_only=True),
    R("A42", "A", "PTS_NUMBER: dashed grouping",
      "78 ЮЩ 778932", dashed, "compact", expected="78ЮЩ778932",
      pre="ПТС ", post="", type="PTS_NUMBER", value_only=True),
    R("A43", "A", "VIN: cue words glued to the value",
      "номер кузова X96WVZCBZXB6V4218", glued, "compact", expected="X96WVZCBZXB6V4218",
      pre="", post="", type="VIN", note="a label glued to its value"),
    R("A44", "A", "PTS_NUMBER: cue word glued to the value",
      "ПТС 78 ЮЩ 778932", glued, "compact", expected="78ЮЩ778932",
      pre="", post="", type="PTS_NUMBER", note="a label glued to its value: 'ПТС78ЮЩ...'"),

    # ----------------------------------------------- B. mutable parts, one identity
    Case(cid="B1", category="B", title="ADDRESS flat change keeps street+house, flat distinct",
         kind="identity", type="LOC", core="street_house", part="flat",
         forms=("улица Тверитина, дом 10, квартира 7",
                "улица Тверитина, дом 10, квартира 42")),
    Case(cid="B2", category="B", title="ADDRESS entrance change keeps street+house, entrance distinct",
         kind="identity", type="LOC", core="street_house", part="entrance",
         forms=("улица Тверитина, дом 10, подъезд 1, квартира 7",
                "улица Тверитина, дом 10, подъезд 3, квартира 7")),
    Case(cid="B3", category="B", title="ADDRESS floor change keeps street+house, floor distinct",
         kind="identity", type="LOC", core="street_house", part="floor",
         forms=("улица Тверитина, дом 10, этаж 2, квартира 7",
                "улица Тверитина, дом 10, этаж 9, квартира 7")),
    Case(cid="B4", category="B", title="ADDRESS corpus change keeps street+house, corpus distinct",
         kind="identity", type="LOC", core="street_house", part="corpus",
         known="phase4-2",
         forms=("улица Тверитина, дом 10, корпус 1",
                "улица Тверитина, дом 10, корпус 2")),
    Case(cid="B5", category="B", title="ADDRESS house change forks the substitute (differ control)",
         kind="collision", type="LOC", must_differ=True,
         forms=("улица Тверитина, дом 10", "улица Тверитина, дом 12")),
    Case(cid="B6", category="B", title="NAME with/without patronymic stays one fake",
         kind="identity", type="NAME", core="name", forms=("Иванов Пётр Сергеевич", "Иванов Пётр")),
    Case(cid="B7", category="B", title="NAME full form and initials stay one fake",
         kind="identity", type="NAME", core="name",
         forms=("Иванов Пётр Сергеевич", "Иванов П. С.")),

    # ----------------------------------------------------------- C. collisions
    Case(cid="C1", category="C", title="two people in one house: flats must differ",
         kind="collision", type="LOC", part="flat",
         forms=("улица Тверитина, дом 10, квартира 7", "улица Тверитина, дом 10, квартира 42")),
    Case(cid="C2", category="C", title="corpus к1 vs к2 must not collapse",
         kind="collision", type="LOC", part="corpus", known="phase4-2",
         forms=("улица Тверитина, дом 10, корпус 1", "улица Тверитина, дом 10, корпус 2")),
    Case(cid="C3", category="C", title="same surname, different given names must differ",
         kind="collision", type="NAME", must_differ=True,
         forms=("Иванов Пётр", "Иванов Николай")),
    Case(cid="C4", category="C", title="two different streets must differ",
         kind="collision", type="LOC", must_differ=True,
         forms=("улица Тверитина, дом 5", "улица Лермонтова, дом 5")),
    Case(cid="C5", category="C", title="near-duplicate street (Шейкмана/Шуйкмана) must differ",
         kind="collision", type="LOC", must_differ=True,
         forms=("улица Шейкмана, дом 5", "улица Шуйкмана, дом 5")),
    Case(cid="C6", category="C", title="two different phones must differ",
         kind="collision", type="PHONE", must_differ=True,
         forms=("+7 916 402-11-87", "+7 916 402-11-88")),
    Case(cid="C7", category="C", title="two different people, same house, must differ",
         kind="collision", type="NAME", part="flat",
         forms=("Иванов Пётр, улица Тверитина, дом 10, квартира 7",
                "Сидорова Анна, улица Тверитина, дом 10, квартира 42")),

    # ---------------------------------------------- D. round-trip robustness
    R("D1", "D", "model strips THE leading zero from a CARD fake",
      "карта 4276 1234 5678 9012", _strip_one_leading_zero, "digits",
      expected="4276123456789012", pre="", post="", type="CARD",
      repeats=60, zero_precondition=True),
    R("D2", "D", "model reformats +7 -> 8 (phone)", PHONE_REAL, to_8, "phone",
      pre="Телефон: ", post="", type="PHONE"),
    R("D3", "D", "model drops the patronymic (name)", NAME_REAL, without_patronymic,
      "name", expected="Иванов Пётр", pre="Клиент ", post=" оформил заказ", type="NAME"),
    R("D4", "D", "model writes the fake address in another case",
      ADDR_REAL, lambda m: _address_case(m, "accs"), "address", legs=("content",),
      pre="Доставка: ", post="", type="LOC", require_change=True,
      note="the fake's new case is rendered by the engine's morphology (see the header)"),
    R("D5", "D", "model lowercases the fake name (content leg)", NAME_REAL,
      lambda m: m.lower(), "name", legs=("content",),
      pre="Клиент ", post=" оформил заказ", type="NAME"),
    R("D6", "D", "phase-4 #1: dictated house, model writes digits",
      ADDR_DICTATED, words_to_digits, "address", legs=("content", "args"),
      pre="Доставка: ", post="", type="LOC", known="phase4-1"),
    R("D7", "D", "phase-4 #1 unmasked with NO model change (verbatim fake)",
      ADDR_DICTATED, lambda m: m, "address", legs=("content", "args"),
      pre="Доставка: ", post="", type="LOC", known="phase4-1"),
    R("D8", "D", "phase-4 #1: build leaf of a decomposed dictated address",
      ADDR_DICTATED, lambda m: address_structured(m, ("street", "build", "flat")),
      "fields", legs=("args",), pre="", post="", type="LOC", known="phase4-1"),
]


# =====================================================================================
# 5. Runner.
# =====================================================================================

CATEGORY_TITLES = {
    "A": "A. FORM TRANSFORMATIONS per type",
    "B": "B. MUTABLE PARTS (one street+house core, distinct parts)",
    "C": "C. COLLISIONS (different identities must stay different)",
    "D": "D. ROUND-TRIP ROBUSTNESS",
}


def run_case(case: Case, corrupt: bool = False) -> Result:
    if case.kind == "roundtrip":
        return run_roundtrip(case, corrupt=corrupt)
    if case.kind == "identity":
        return run_identity(case)
    return run_collision(case)


def _print_table(results: list[Result]) -> None:
    print("\n" + "=" * 100)
    print("PER-CATEGORY RESULT")
    print("=" * 100)
    for category in ("A", "B", "C", "D"):
        rows = [r for r in results if r.category == category]
        passed = sum(1 for r in rows if r.status == "PASS")
        failed = [r for r in rows if r.status == "FAIL"]
        skipped = sum(1 for r in rows if r.status == "SKIP")
        verdict = "PASS" if not failed else "FAIL"
        print(f"\n{category}. {CATEGORY_TITLES[category][3:]}   "
              f"[{verdict}] {passed}/{len(rows) - skipped} passed"
              + (f", {skipped} skipped" if skipped else ""))
        for r in rows:
            mark = {"PASS": "OK ", "FAIL": "BAD", "SKIP": "SKP"}[r.status]
            known = f"  <{r.known}>" if r.known and r.status == "FAIL" else ""
            print(f"   [{mark}] {r.cid:4} {r.title}{known}")


def _print_failures(results: list[Result]) -> None:
    failures = [r for r in results if r.status == "FAIL"]
    print("\n" + "=" * 100)
    print(f"FAIL ROWS — {len(failures)} real weakness(es)")
    print("=" * 100)
    for r in failures:
        print(f"\n[{r.cid}] {r.category} — {r.title}   type={r.type or '-'}"
              + (f"   known={r.known}" if r.known else ""))
        print(f"   real         : {r.real!r}")
        if r.kind == "roundtrip":
            print(f"   masked       : {r.masked!r}")
            print(f"   reformatted  : {r.reformed!r}")
            for leg, back in r.legs.items():
                print(f"   back[{leg:7}]: {back!r}")
            print(f"   expected     : {r.expected!r}")
        else:
            print(f"   masked       : {r.masked!r}")
            print(f"   expected     : {r.expected!r}")
        print(f"   why          : {r.detail}")


def reader_selftest() -> list[str]:
    """Assert the instrument's OWN readers on known answers, before any engine number is
    believed. A broken address reader or numeral reader would report itself as an engine
    defect, and the two are indistinguishable in the output unless this runs first.

    Returns the list of failures; empty means the instrument measured what it thinks it
    measured.
    """
    failures: list[str] = []

    def check(name: str, got, want) -> None:
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")

    # compound numerals: the exact class the naive version split into "60 6"
    check("w2d 66", words_to_digits("шестьдесят шесть"), "66")
    check("w2d 27", words_to_digits("двадцать семь"), "27")
    check("w2d 227", words_to_digits("двести двадцать семь"), "227")
    check("w2d in sentence", words_to_digits("дом восемьдесят пять, квартира шестьдесят восемь"),
          "дом 85, квартира 68")
    check("w2d leaves digits", words_to_digits("дом 10"), "дом 10")

    # the address reader must put the value in the ROLE the marker names
    check("addr roles", parse_address("улица Смирнова, дом 10, корпус 2, квартира 42"),
          {"street": "Смирнова", "house": "10", "corpus": "2", "flat": "42"})
    check("addr two-word street", parse_address("Сиреневый бульвар, дом 26, кв 81"),
          {"street": "Сиреневый", "house": "26", "flat": "81"})
    check("addr dictated house", parse_address("улица Лермонтова, дом тридцать восемь, квартира семь"),
          {"street": "Лермонтова", "house": "38", "flat": "7"})
    check("addr no type word", parse_address("Сосновая 67 кв 7")["house"], "67")
    check("addr lowercased", parse_address("улица сосновая, дом 67, квартира 7")["street"], "сосновая")
    check("addr does not eat 'Доставка'",
          parse_address("Доставка: улица Сосновая, дом 67")["street"], "Сосновая")
    check("addr does not eat 'оформил'", parse_address("Клиент Ивaнов оформил заказ"), {})
    check("fields english keys",
          parse_fields('{"street": "Сосновая", "build": "67", "flat": "7"}'),
          {"street": "Сосновая", "house": "67", "flat": "7"})
    check("fields sflat/nflat aliases",
          parse_fields('{"sflat": "7", "nflat": "42"}'), {"flat": "7"})

    # equivalence: notation must fold, a different person/street must not
    check("phone +7/8 fold", fold_phone("+7 916 402-11-87"), fold_phone("8 (916) 4021187"))
    check("digits fold", digits_equiv("4512 345678", "4512345678"), True)
    check("name initials pass", name_equiv("Иванов П.С.", "Иванов П.С.",
                                           "Иванов Пётр Сергеевич"), True)
    check("name declined pass", name_equiv("Иванову Петру Сергеевичу", "Иванов Пётр Сергеевич",
                                           "Иванов Пётр Сергеевич"), True)
    check("name fake rejected", name_equiv("Щукин Кузьма", "Иванов Пётр",
                                           "Иванов Пётр"), False)
    check("date padding folds", date_equiv("05.3.1998", "05.03.1998"), True)
    check("date different day rejected", date_equiv("05.3.1998", "06.03.1998"), False)
    return failures


def _selftest(corrupt_cid: str = "A1") -> int:
    """The instrument must be able to FAIL on a corrupted case it normally passes, and
    the same case must pass uncorrupted. Without both halves, a green run proves
    nothing about the engine — it may only prove the harness cannot go red."""
    print("SELFTEST")
    failures = reader_selftest()
    for f in failures:
        print(f"  READER RED: {f}")
    if failures:
        return 2
    print("  readers: green")

    for cid, mode in (("A1", "phone"), ("A8", "name"), ("A26", "digits")):
        case = next(c for c in CASES if c.cid == cid)
        clean = run_case(case)
        dirty = run_case(case, corrupt=True)
        if clean.status != "PASS":
            print(f"  READER RED: control {cid} ({mode}) does not pass uncorrupted: "
                  f"{clean.detail}")
            return 2
        if dirty.status != "FAIL":
            print(f"  READER RED: corrupted {cid} ({mode}) still passed — the instrument "
                  f"cannot fail on this comparison")
            return 2
        original = {"name": name_equiv, "phone": digits_equiv, "digits": digits_equiv}[mode]
        globals()[{"name": "name_equiv", "phone": "digits_equiv",
                   "digits": "digits_equiv"}[mode]] = lambda *a, **k: True
        try:
            loose = run_case(case, corrupt=True)
        finally:
            globals()[{"name": "name_equiv", "phone": "digits_equiv",
                       "digits": "digits_equiv"}[mode]] = original
        if loose.status != "PASS":
            print(f"  READER RED: the loose control for {cid} did not isolate the comparison")
            return 2
        print(f"  {cid} ({mode}): clean PASS, corrupt FAIL, loose PASS")

    # SKIP: a check whose simulated model transform never happened must not be counted
    # as a pass. `require_change` on an identity transform is exactly that situation.
    skipped = run_case(Case(cid="Z1", category="Z", title="skip control", kind="roundtrip",
                            real="+7 916 402-11-87", transform=lambda m: m, mode="phone",
                            pre="Телефон: ", require_change=True))
    if skipped.status != "SKIP":
        print(f"  READER RED: a no-op precondition reported {skipped.status}, not SKIP")
        return 2
    print("  precondition: SKIP")

    # IDENTITY and COLLISION controls: an invariant checked only on what it must find is
    # a rule nobody knows the reach of. A "collapse" group of two DIFFERENT people must
    # go red, and a "must differ" pair of one identity must go red too.
    wrong_collapse = run_case(Case(cid="Z2", category="Z", title="collapse control",
                                   kind="identity", type="NAME",
                                   forms=("Иванов Пётр", "Сидоров Иван")))
    if wrong_collapse.status != "FAIL":
        print("  READER RED: two different people passed a one-fake group")
        return 2
    wrong_differ = run_case(Case(cid="Z3", category="Z", title="differ control",
                                 kind="collision", type="LOC", must_differ=True,
                                 forms=("улица Тверитина, дом 10", "улица Тверитина, дом 10")))
    if wrong_differ.status != "FAIL":
        print("  READER RED: one address passed a must-differ pair")
        return 2
    print("  identity/collision controls: red where they must be")
    print("SELFTEST GREEN: readers agree with known answers, and the harness reports "
          "PASS/FAIL/SKIP for the reason it should")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default="", help="write the machine-readable result here")
    parser.add_argument("--selftest", action="store_true",
                        help="prove the instrument can go red, then exit")
    args = parser.parse_args()

    if args.selftest:
        return _selftest()

    # The instrument checks its own readers on every run: a broken numeral or address
    # reader would otherwise be indistinguishable from an engine defect.
    reader_failures = reader_selftest()
    if reader_failures:
        for failure in reader_failures:
            print(f"INSTRUMENT BROKEN: {failure}")
        print("Refusing to report engine numbers from a broken instrument.")
        return 2

    print("edge-case stress test — FREE (no model, no network, dev bundle only)")
    print(f"checks: {len(CASES)}   fresh Vault(':memory:') per check")
    results = [run_case(c) for c in CASES]

    _print_table(results)
    _print_failures(results)

    failed = [r for r in results if r.status == "FAIL"]
    known = [r for r in failed if r.known]
    print("\n" + "=" * 100)
    print(f"SUMMARY: {sum(1 for r in results if r.status == 'PASS')}/{len(results)} pass, "
          f"{len(failed)} fail ({len(known)} of them phase-4 markers), "
          f"{sum(1 for r in results if r.status == 'SKIP')} skip")
    if failed:
        print("REAL WEAKNESSES (this is a measurement, not a fix):")
        for r in failed:
            tag = f" [{r.known}]" if r.known else " [new]"
            print(f"   {r.cid:4}{tag} {r.title}")
    print("=" * 100)

    if args.json:
        payload = {
            "checks": len(results),
            "pass": sum(1 for r in results if r.status == "PASS"),
            "fail": len(failed),
            "skip": sum(1 for r in results if r.status == "SKIP"),
            "categories": {},
            "results": [
                {"id": r.cid, "category": r.category, "title": r.title, "kind": r.kind,
                 "type": r.type, "status": r.status, "known": r.known,
                 "real": r.real, "masked": r.masked, "reformed": r.reformed,
                 "back": r.legs, "expected": r.expected, "detail": r.detail}
                for r in results
            ],
        }
        for category in ("A", "B", "C", "D"):
            rows = [r for r in results if r.category == category]
            payload["categories"][category] = {
                "total": len(rows),
                "pass": sum(1 for r in rows if r.status == "PASS"),
                "fail": sum(1 for r in rows if r.status == "FAIL"),
                "skip": sum(1 for r in rows if r.status == "SKIP"),
            }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"json -> {args.json}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
