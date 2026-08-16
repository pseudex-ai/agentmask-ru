"""Name gazetteer + morphology gate — fixes what RU NER misses/over-tags.

NER (trained on capitalized news) misses lowercase diminutives ("света"),
Latin-script names ("Ivan Petrov"), and initials ("Сидоров И.И."), while
over-tagging sentence-initial verbs ("Оформите") as persons.

This module adds a gazetteer (known first names + diminutives + their Latin
transliterations) and a gate: a single-token NER person is kept only if it is a
known name or has a Russian surname shape — otherwise dropped.

The gazetteers themselves are LEASED, not shipped: they arrive in the detection
bundle and live only in memory (`pseudex/assets.py`). This module holds the rules
that consume them. Asking for them without a valid lease raises `BundleNotLeased`
rather than degrading to a smaller list — a half-equipped gazetteer on a PII
gateway leaks silently, which is worse than not answering at all.

The frozen struct is fetched ONCE per public call and threaded down into the
helpers: `gazetteer_names` inspects every word of the message, and re-fetching
per word would put a registry lookup on the hottest loop in the product.
"""

import re

from pseudex.assets import ASSETS, NameAssets
from pseudex.detect import Span
from pseudex.morph import MORPH

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


_PERSON_TAGS = frozenset({"Surn", "Name", "Patr"})


# Readings that mean the word is doing a job other than naming somebody.
_NOT_A_NAME_POS = frozenset({"PREP", "CONJ", "PRCL", "NPRO", "VERB", "INFN",
                             "ADVB", "PRED", "INTJ", "COMP"})


def _names_a_person(word: str) -> bool:
    """Whether this word, in context, is plausibly somebody's surname.

    ANY parse may carry the person tag — for an unusual surname the person
    reading is a low-scoring one, and «Мкртчян» scores 0.14 — but the BEST parse
    decides whether the word is doing something else entirely. Without that
    second half the rule swallowed «В», «из», «по» and «У» standing next to a
    name in news prose: every one of them has some obscure proper-noun reading,
    and 124 false masks on NEREL came from exactly that.

    Three guards, each earning its place:
      * length, because a one- or two-letter neighbour is a preposition;
      * part of speech, because a verb next to a name is what the person DID;
      * animacy, because «романа» and «слава» are things, and their person
        readings (Роман, Слава) are real but not what the sentence means.
    """
    if len(word) < 3:
        return False
    parses = MORPH.parse(word)
    if not parses:
        return False
    best = max(parses, key=lambda parse: parse.score)
    if best.tag.POS in _NOT_A_NAME_POS:
        return False
    if best.tag.POS == "NOUN" and "inan" in best.tag.grammemes:
        return False
    return any(_PERSON_TAGS & parse.tag.grammemes for parse in parses)


def _adjacent_surnames(text: str, found: list[Span]) -> list[Span]:
    """Extend a known given name to the person-word beside it."""
    extra: list[Span] = []
    taken = {(span.start, span.end) for span in found}
    for span in found:
        for match in _WORD_RE.finditer(text[span.end:span.end + 24]):
            if match.start() > 1:      # not the immediately adjacent word
                break
            start, end = span.end + match.start(), span.end + match.end()
            if (start, end) not in taken and _names_a_person(match.group()):
                extra.append(Span(start, end, "NAME", match.group()))
            break
        for match in reversed(list(_WORD_RE.finditer(text[max(0, span.start - 24):span.start]))):
            offset = max(0, span.start - 24)
            if span.start - (offset + match.end()) > 1:
                break
            start, end = offset + match.start(), offset + match.end()
            if (start, end) not in taken and _names_a_person(match.group()):
                extra.append(Span(start, end, "NAME", match.group()))
            break
    return extra


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
    # A given name found in the gazetteer usually has its surname next to it, and
    # in chat that surname is lower case and therefore invisible to every rule
    # above — the bulk dictionary is capital-only by design. So «на дмитрий
    # кузнецов» produced a masked given name and a LEAKED surname, which is the
    # worst of both: the customer sees masking happening and the identifying half
    # still reaches the model.
    #
    # The neighbour is admitted only when morphology says it names a PERSON —
    # `Surn`, `Name` or `Patr` among ANY of its parses, not just the best one,
    # because for an unusual surname the person reading is a low-scoring parse.
    # Checking every parse is what lets «мкртчян» (score 0.14) through while
    # «позвонит» (VERB), «срочно» (ADVB) and «адрес» (inanimate NOUN) stay out.
    spans.extend(_adjacent_surnames(text, spans))
    for match in _LATIN_PAIR_RE.finditer(text):
        if match.group(1).lower() in names.name_set:
            spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    for match in _INITIALS_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    return spans
