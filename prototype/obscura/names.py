"""Name gazetteer + morphology gate — fixes what RU NER misses/over-tags.

NER (trained on capitalized news) misses lowercase diminutives ("света"),
Latin-script names ("Ivan Petrov"), and initials ("Сидоров И.И."), while
over-tagging sentence-initial verbs ("Оформите") as persons.

This module adds a gazetteer (known first names + diminutives + their Latin
transliterations) and a gate: a single-token NER person is kept only if it is a
known name or has a Russian surname shape — otherwise dropped.

The gazetteers themselves are LEASED, not shipped: they arrive in the detection
bundle and live only in memory (`obscura/assets.py`). This module holds the rules
that consume them. Asking for them without a valid lease raises `BundleNotLeased`
rather than degrading to a smaller list — a half-equipped gazetteer on a PII
gateway leaks silently, which is worse than not answering at all.

The frozen struct is fetched ONCE per public call and threaded down into the
helpers: `gazetteer_names` inspects every word of the message, and re-fetching
per word would put a registry lookup on the hottest loop in the product.
"""

import re

from obscura.assets import ASSETS, NameAssets
from obscura.detect import Span
from obscura.morph import MORPH

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")
_INITIALS_RE = re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?")
_LATIN_PAIR_RE = re.compile(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b")
_INITIAL_RE = re.compile(r"[А-ЯЁA-Z]\.?")
# Tokens WITH their offsets, so a trimmed span can be sliced out of the original
# text instead of rebuilt from pieces — see trim_person_span.
_NON_SPACE_RE = re.compile(r"\S+")
_NAME_TAGS = {"Name", "Surn", "Patr"}


def _lemma(word: str) -> str:
    """Normal form, so declensions match the gazetteer (Ивана -> иван)."""
    return MORPH.parse(word)[0].normal_form


def _name_set_hit(word: str, low: str, lemma: str, before: str, names: NameAssets) -> bool:
    """Seed-list match. An ordinary-word name (вера, роман, света) needs either a
    capital letter or a naming cue right before it — `имя света` is a person,
    `вера в успех` is not. Without the cue path a lowercase diminutive leaked:
    the dirty set's `Оформите заказ, имя света.` went to the model unmasked."""
    for candidate in (low, lemma):
        if candidate not in names.name_set:
            continue
        if candidate in names.ambiguous and not word[:1].isupper():
            if not any(cue in before for cue in names.cues):
                continue
        return True
    return False


def _is_known_name(word: str, names: NameAssets) -> bool:
    low = word.lower()
    return low in names.name_set or _lemma(low) in names.name_set


def _is_surname_shaped(word: str, names: NameAssets) -> bool:
    low = word.lower()
    if low in names.dict_surnames:
        return True
    return len(low) > 4 and low.endswith(names.surname_suffixes)


def is_known_name(word: str) -> bool:
    return _is_known_name(word, ASSETS.get().names)


def is_surname_shaped(word: str) -> bool:
    return _is_surname_shaped(word, ASSETS.get().names)


def keep_location(value: str) -> bool:
    """Gate for an NER location span: drop single-token imperatives/fillers."""
    parts = value.split()
    if len(parts) >= 2:
        return True
    return parts[0].lower() not in ASSETS.get().names.stopwords


def _is_name_part(word: str, names: NameAssets) -> bool:
    """True if this token can plausibly belong to a person's full name."""
    low = word.lower()
    if (low in names.name_set or _is_surname_shaped(word, names)
            or low.endswith(names.patronymic_suffixes)):
        return True
    if _INITIAL_RE.fullmatch(word):
        return True
    parse = MORPH.parse(word)[0]
    if _NAME_TAGS & set(parse.tag.grammemes):
        return True
    # A word morphology does NOT recognise is more likely a rare surname than a
    # stray ordinary word, so it counts as a name part. Fail-closed: keeping it
    # over-masks, dropping it would leak.
    return not parse.is_known


def trim_person_span(value: str) -> tuple[int, str]:
    """Drop trailing tokens an NER person span swallowed that cannot be part of a name.

    Natasha reads `Получатель Иван Петров Спасибо за помощь` as the three-part
    span `Иван Петров Спасибо`, because a capitalised word right after a surname
    looks exactly like a patronymic. That is not a cosmetic labelling error:
    masking is REVERSIBLE, so the whole swallowed string gets one token and comes
    back attached — the tool is then called with `Иван Петров Спасибо` instead of
    `Иван Петров`, fails its own identity check, and the business operation runs
    against the wrong person. Measured on BFCL as `execution_response_mismatch`
    ("Expected Ольга Смирнов, got Ольга Смирнов Мои").

    Trimmed from BOTH ends — the same swallow happens on the left, where a role
    word precedes the name (`Получатель Цхведиани Ираклий`). Only while at least
    two tokens remain, and only when morphology positively recognises the word as
    an ordinary one. A word it does not know stays in the span: a rare surname
    must not be exposed in order to fix a boundary.

    Returns (leading_offset, trimmed_value) because dropping a leading token
    moves the span start, and the caller mints the token at that offset.

    THE RESULT IS A SLICE OF `value`, never a rebuilt string. It used to be
    `" ".join(parts)`, which silently collapsed runs of whitespace: on
    `Иван  Петров` (double space — ordinary in CRM exports and pasted forms) the
    returned value was one character shorter than the text it came from, the
    caller built the span from `len(trimmed)`, and masking replaced one character
    too few. What went to the model was a fake name with a dangling `в` — a
    fragment of the real surname, left in place by the code meant to remove it.
    The left-hand trim had the same flaw: it advanced the offset by
    `len(token) + 1`, assuming exactly one separator character."""
    names = ASSETS.get().names
    tokens = [(match.start(), match.end(), match.group())
              for match in _NON_SPACE_RE.finditer(value)]
    if len(tokens) <= 2:
        return 0, value
    first, last = 0, len(tokens) - 1
    while last - first + 1 > 2 and not _is_name_part(tokens[last][2], names):
        last -= 1
    while last - first + 1 > 2 and not _is_name_part(tokens[first][2], names):
        first += 1
    start, end = tokens[first][0], tokens[last][1]
    return start, value[start:end]


def keep_person(value: str) -> bool:
    """Gate for an NER person span: keep multi-token names, known names, or
    surname-shaped tokens; drop bare unknown words (verb over-tags)."""
    parts = value.split()
    if len(parts) >= 2:
        return True
    names = ASSETS.get().names
    return _is_known_name(parts[0], names) or _is_surname_shaped(parts[0], names)


def gazetteer_names(text: str) -> list[Span]:
    """Catch names NER misses: known names (any case), Latin pairs, initials,
    and — for CAPITALISED words only — the bulk dictionary.

    The 28k/197k bulk dictionaries are matched only when the word is capitalised.
    The seed lists stay case-insensitive because a diminutive is normally written
    lowercase ("перезвони свете"), but applying that to 225k entries would mask
    every sentence containing an ordinary word that happens to also be a surname.
    Entries that ARE ordinary Russian words are dropped when the bundle is built."""
    names = ASSETS.get().names
    spans: list[Span] = []
    for match in _WORD_RE.finditer(text):
        word = match.group()
        low = word.lower()
        lemma = _lemma(low)
        before = text[max(0, match.start() - 20):match.start()].lower()
        if _name_set_hit(word, low, lemma, before, names):
            spans.append(Span(match.start(), match.end(), "NAME", word))
        elif word[:1].isupper() and (
            low in names.dict_first or low in names.dict_surnames
            or lemma in names.dict_first or lemma in names.dict_surnames
        ):
            spans.append(Span(match.start(), match.end(), "NAME", word))
    for match in _LATIN_PAIR_RE.finditer(text):
        if match.group(1).lower() in names.name_set:
            spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    for match in _INITIALS_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    return spans
