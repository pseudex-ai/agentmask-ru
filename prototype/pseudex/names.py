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

import functools
import itertools
import re

from pseudex.assets import ASSETS, NameAssets
from pseudex.detect import Span
from pseudex.morph import MORPH

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")
_INITIALS_RE = re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.?")
# Two OR THREE capitalised Latin words: a transliterated Russian name is
# «Ivanov Petr Sergeevich» as often as «Petr Ivanov», and the patronymic is
# the part a two-word pattern silently left in the clear.
_LATIN_PAIR_RE = re.compile(
    r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)(?:\s+([A-Z][a-z]+))?\b")
_INITIAL_RE = re.compile(r"[А-ЯЁA-Z]\.?")
# Tokens WITH their offsets, so a trimmed span can be sliced out of the original
# text instead of rebuilt from pieces — see trim_person_span.
_NON_SPACE_RE = re.compile(r"\S+")
_NAME_TAGS = {"Name", "Surn", "Patr"}


def _lemma(word: str) -> str:
    """Normal form, so declensions match the gazetteer (Ивана -> иван)."""
    return MORPH.parse(word)[0].normal_form


def _lemmas(word: str) -> tuple[str, ...]:
    """EVERY normal form a name reading of this word could have.

    `_lemma` takes `parse(word)[0]`, which this module's own docstring forbids,
    and «марину» is where that bites: pymorphy3 offers «марин» (the man Марин,
    dative) and «марина» (the woman Марина, accusative) with the SAME score of
    0.500, and which one lands first is arbitrary. It landed on «марин», the
    gazetteer had no such entry, and «запишите марину петрову» went to the model
    with both words in the clear — a full name, unmasked, in the register support
    traffic is actually written in.

    The neighbouring surname leaked with it: lower case, it is invisible to the
    bulk dictionary (capital-only by design) and reachable only by extension
    from a given name that was never found.

    ONLY READINGS TIED FOR FIRST, and that bound is what makes this safe. The
    defect being fixed is an arbitrary choice between EQUALLY ranked parses, so
    equal rank is exactly the licence to consider both. Taking every name-tagged
    reading instead admits the ones morphology ranks far below an ordinary word —
    «жене» → «Женя», «юре» → «Юра», «марками» → «Марк», «розами» → «Роза» — and
    those are ordinary words in oblique cases, not people. Measured on NEREL:
    unbounded costs 0.7pp of precision (99.4% -> 98.7%) and buys no recall.
    """
    parses = MORPH.parse(word)
    if not parses:
        return ()
    best = max(parse.score for parse in parses)
    named = tuple(dict.fromkeys(parse.normal_form for parse in parses
                                if parse.score >= best
                                and _NAME_TAGS & set(parse.tag.grammemes)))
    return named or (parses[0].normal_form,)


def _name_set_hit(word: str, low: str, lemmas: tuple[str, ...], before: str,
                  names: NameAssets) -> bool:
    """Seed-list match. An ordinary-word name (вера, роман, света) needs either a
    capital letter or a naming cue right before it — `имя света` is a person,
    `вера в успех` is not. Without the cue path a lowercase diminutive leaked:
    the dirty set's `Оформите заказ, имя света.` went to the model unmasked."""
    for candidate in (low, *lemmas):
        if candidate not in names.name_set:
            continue
        if candidate in names.ambiguous and not word[:1].isupper():
            if not any(cue in before for cue in names.cues):
                continue
        return True
    return False


def _is_known_name(word: str, names: NameAssets) -> bool:
    low = word.lower()
    return low in names.name_set or any(lemma in names.name_set
                                        for lemma in _lemmas(low))


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
    if not tokens:
        return 0, value
    first, last = 0, len(tokens) - 1
    # The DICTIONARY trims stop at two tokens: below that there is no evidence
    # which of «Имя Фамилия» is the intruder, and dropping the wrong one exposes
    # half of a real name. The verb trim below has that evidence and does not
    # stop there.
    while last - first + 1 > 2 and not _is_name_part(tokens[last][2], names):
        last -= 1
    while last - first + 1 > 2 and not _is_name_part(tokens[first][2], names):
        first += 1
    # DOWN TO ONE TOKEN when the leading word is somebody being asked to do
    # something. The loops above stop at two because a two-token span is
    # presumed to be «Имя Фамилия», and that presumption is what let
    # «Наберите Игорю» through as one name: the sentence lost its verb, and the
    # substitute for the two words together was a person unrelated to the one
    # the same message had already named — so the dialogue held two people where
    # the customer wrote one.
    #
    # The test is the one the patronymic path already uses — the word's BEST
    # reading, not any reading — so a surname that merely has a verb parse
    # somewhere among its readings stays inside the span.
    while last - first + 1 > 1:
        parses = MORPH.parse(tokens[first][2])
        if not parses:
            break
        if max(parses, key=lambda parse: parse.score).tag.POS not in _NOT_A_NAME_POS:
            break
        first += 1
    start, end = tokens[first][0], tokens[last][1]
    return start, value[start:end]


def keep_person(value: str) -> bool:
    """Gate for an NER person span: keep multi-token names, known names,
    surname-shaped tokens, and words doing no other job; drop verb over-tags.

    THE FOURTH CLAUSE IS WHERE FOREIGN NAMES LIVE. «Обама», «Месси», «Акихито»,
    «Бейонсе» are in no gazetteer of ours and carry no Russian surname suffix, so
    the first three clauses dropped every one of them — NER had found the person
    and we threw the answer away. On NEREL that is most of the 19% we miss, and a
    missed name is a leak, not a quality defect.

    Two signals, as everywhere else here: the word must not be doing another job
    (its BEST reading is not a verb or a particle — that is what still drops
    «Оформите» and «Не»), AND the dictionary must not claim it as an ordinary
    word unless it also reads as a surname.

    THAT SECOND HALF IS NOT OPTIONAL. Without it the gate also admitted the
    capitalised nouns Natasha over-tags at a caption boundary in news prose —
    «Цветы», «Девочки», «Дезинфектор», «Назначение» — 72 of them on NEREL, each
    one a word this product would have destroyed in a customer's sentence. With
    it they go and the names stay, because «Обама» carries a `Surn` reading even
    though the dictionary knows the word, and «Месси», «Бейонсе», «Акихито» are
    not in the dictionary at all.

    Measured on NEREL, dev+test: PERSON recall 80.6% -> 91.5% (Cyrillic-only
    subset 81.1% -> 92.3%) at precision 99.4% -> 99.4%, i.e. unchanged. Dropping
    the `is_known` half reaches 94.1% and costs 0.3pp of precision — that is the
    variant those 72 come from, and it was rejected: a miss is a leak, but a
    false mask is a sentence destroyed in front of the customer, and there was
    no need to buy one with the other.
    """
    parts = value.split()
    if len(parts) >= 2:
        return True
    names = ASSETS.get().names
    if _is_known_name(parts[0], names) or _is_surname_shaped(parts[0], names):
        return True
    parses = MORPH.parse(parts[0])
    if not parses:
        return False
    if max(parses, key=lambda parse: parse.score).tag.POS in _NOT_A_NAME_POS:
        return False
    return (not parses[0].is_known
            or any("Surn" in parse.tag.grammemes for parse in parses))


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


_PATRONYMIC_TAIL = ("ович", "евич", "овна", "евна", "ична", "инична",
                    "оглы", "кызы", "улы", "уулу")
_PATRONYMIC_RE = re.compile(
    r"\b[А-ЯЁа-яё]{3,}(?:" + "|".join(_PATRONYMIC_TAIL) + r")(?:[аеиоуыюя]|ем|ым|ой)?\b")


def _patronymic_anchors(text: str) -> list[Span]:
    """Every word shaped like a patronymic, as a NAME span.

    Short stems are excluded («ович» needs three letters before it) so an
    ordinary word ending the same way cannot anchor a person. The merge step
    then joins the anchor to the surname and given name beside it, exactly as it
    does for a gazetteer hit — one mechanism, two ways in.
    """
    spans: list[Span] = []
    for match in _PATRONYMIC_RE.finditer(text):
        start = _extend_left_of_patronymic(text, match.start())
        spans.append(Span(start, match.end(), "NAME", text[start:match.end()]))
    return spans


def _extend_left_of_patronymic(text: str, start: int) -> int:
    """Swallow the up-to-two words before a patronymic.

    A Russian name carrying a patronymic is «Фамилия Имя Отчество» or «Имя
    Отчество» — the patronymic is the strongest person signal the language has,
    and it licenses its neighbours without their needing to be in a dictionary.
    That is the whole point: this path exists for names no gazetteer knows.

    The guard is on PART OF SPEECH only, not on the person tags the general
    neighbour rule uses. «Тест» parses as an inanimate noun and is admitted,
    which is right — it is a surname here. «Позвоните» parses as a verb and is
    not, which is also right: it is what somebody is being asked to do.
    """
    boundary = start
    for _ in range(2):
        head = text[:boundary].rstrip()
        if len(head) == boundary - 1 or head == text[:boundary]:
            pass
        gap = boundary - len(head)
        if gap != 1 or not head:
            break
        word = _WORD_RE.search(head[::-1])
        if word is None or word.start() != 0:
            break
        candidate = head[len(head) - word.end():]
        if len(candidate) < 3:
            break
        parses = MORPH.parse(candidate)
        if not parses:
            break
        best = max(parses, key=lambda parse: parse.score)
        if best.tag.POS in _NOT_A_NAME_POS:
            break
        # AND the role words NER already over-tags. «клиент», «заказ»,
        # «получатель» are ordinary nouns, so a part-of-speech guard admits
        # them, and «клиент ИвановПётр Сергеевич» became one name — the tool
        # was then called with the word «клиент» inside the customer's name.
        # The list is the same one `keep_location` uses; there is no second
        # vocabulary to keep in step.
        if candidate.lower() in ASSETS.get().names.stopwords:
            break
        boundary = len(head) - word.end()
    return boundary


@functools.lru_cache(maxsize=4)
def _misspelling_index(version: str) -> dict[str, tuple[str, ...]]:
    """Names bucketed by their first three and last three letters.

    FOR FINDING A NAME SOMEBODY MISTYPED. «Кзнецов Дмитрий» is detected as
    «Дмитрий» alone — morphology reads «Кзнецов» as a plural noun, so the
    neighbour rule refuses it — and the surname goes to the model in the clear.
    Half a masked name is a leak, and the benchmark's coverage metric exists
    because recall called that case found.

    Why two buckets and why three letters: an edit at position p is caught by the
    first-three key when p ≥ 3 and by the last-three key when p < len − 3, so any
    single edit in a word of six letters or more lands in at least one of them.

    THE LENGTH IS PART OF THE KEY, and without it this was a latency weapon. A
    single edit cannot change a length by more than one, so a bucket holding
    every «…ова» in the dictionary — 28 719 of them — spent almost all of its
    work on candidates the length alone ruled out. Measured before: 13.65 ms for
    one word, a fifth of the whole p50 masking budget, on a lookup that runs per
    neighbouring word. After: three length-sliced buckets, and the comparison
    itself stops at the second difference instead of scanning the whole word.

    WHAT IS LEFT, stated rather than hidden: a word that is unknown to
    morphology, five letters or more, sits beside a detected name AND lands in
    one of the few enormous surname-ending buckets still costs ~4 ms. On real
    traffic that shape is rare enough to be invisible — measured over 1402
    messages from the dirty set and AgentPII-RU, detection went 1.06 -> 1.18 ms
    per message, against a /mask p50 of ~73 ms that the NER model dominates. A
    message built entirely of such words would cost real time; the lever if that
    ever appears is to skip the largest buckets, which trades this recall back.

    Keyed on the BUNDLE VERSION so a re-lease cannot serve an index built from
    the previous dictionary. The version is a content hash, so equal version
    means equal contents.
    """
    names = ASSETS.get().names
    index: dict[tuple[str, int], list[str]] = {}
    for word in itertools.chain(names.dict_first, names.dict_surnames):
        if len(word) < 5 or word in names.ambiguous:
            continue
        index.setdefault((word[:3], len(word)), []).append(word)
        index.setdefault(("\0" + word[-3:], len(word)), []).append(word)
    return {key: tuple(value) for key, value in index.items()}


def _within_one_edit(word: str, other: str) -> bool:
    """Levenshtein distance ≤ 1, decided without building a matrix.

    Stops at the SECOND difference. The whole-word scan it replaced was the
    difference between 13.65 ms and a fraction of one on a large bucket: almost
    every candidate differs immediately, and finishing the word to learn that is
    work spent on a decision already made.
    """
    if abs(len(word) - len(other)) > 1:
        return False
    if len(word) == len(other):
        seen = False
        for left, right in zip(word, other):
            if left == right:
                continue
            if seen:
                return False
            seen = True
        return True
    shorter, longer = (word, other) if len(word) < len(other) else (other, word)
    index = 0
    while index < len(shorter) and shorter[index] == longer[index]:
        index += 1
    return shorter[index:] == longer[index + 1:]


def _looks_misspelt_name(word: str) -> bool:
    """Whether this word is one edit away from a name we know.

    The second signal, and it is needed: the first — sitting next to a name we
    detected — is not enough on its own, because the word after a given name is
    very often an ordinary one. Requiring near-membership in the dictionary is
    the same tolerance the cue-word deny matching already uses, bounded the same
    way at a single edit.
    """
    lowered = word.lower()
    if len(lowered) < 5:
        # Below five letters a single edit reaches too much of the language:
        # «Иван» is one edit from «Иван», «Инан», «Иванк»… and also from ordinary
        # short words. The gazetteer already covers names this short exactly.
        return False
    # UNKNOWN TO MORPHOLOGY, and this is the signal that makes the rest usable.
    # In a 197k-name dictionary the distance-1 neighbourhood is dense enough that
    # ordinary words land in it: «заказ»→«Закар», «адрес»→«Адрей», «клиент»→
    # «Клинт», «спасибо»→«Спасибов» are all real, all rare surnames, and masking
    # them destroys the sentence. Without this line `test_product` returned
    # «Яков Роман Карпов Василий перезвонить» to a tool.
    #
    # The separation is exact on everything measured: every ordinary word above
    # is in pymorphy3's dictionary, and every mistyped name («Кзнецов»,
    # «Захарув», «Волква», «Иваноа») is only PREDICTED from its suffix. It is
    # also the rule `_is_name_part` already states — an unrecognised word is more
    # likely a rare surname than a stray ordinary one.
    parses = MORPH.parse(word)
    if not parses or parses[0].is_known:
        return False
    index = _misspelling_index(ASSETS.version or "")
    for key in (lowered[:3], "\0" + lowered[-3:]):
        # Three lengths, because one edit moves a length by at most one.
        for length in (len(lowered) - 1, len(lowered), len(lowered) + 1):
            for candidate in index.get((key, length), ()):
                if candidate != lowered and _within_one_edit(lowered, candidate):
                    return True
    return False


_SURNAME_CUE_RE = re.compile(r"(?i)\bфамил\w*\s*[:\-—–]?\s*([А-ЯЁа-яё][А-ЯЁа-яё\-]{2,})")


def _cued_name_parts(text: str) -> list[Span]:
    """The word a person NAMES as their surname, whatever its case.

    «фамилия Волков» is caught already, and only because it is capitalised — the
    bulk surname dictionary is capital-only by design, so «фамилия волков» in a
    messenger found NOTHING and the identifying half of the name reached the
    model in the clear. That is a leak, not a quality defect, and the register it
    lives in is the one real support traffic is written in.

    The customer has told us what the word is. That is a stronger signal than
    capitalisation and stronger than any dictionary, and it is the same shape as
    the patronymic anchor: a cue licenses its neighbour without the neighbour
    needing to be known.

    STILL TWO SIGNALS. The cue alone would mask «фамилия клиента не указана» and
    «фамилия и имя обязательны», so morphology must also say the word can name a
    person. Not «фамилия» + capital, which is what we already had and what missed
    the case; not morphology alone, which admits every noun in the language.

    Only the surname cue, deliberately. «имя» would have to survive «имя
    пользователя», «имя файла», «доменное имя» — the same word doing a different
    job in the traffic of the very customers who integrate us — and a given name
    is the part the seed gazetteer already matches case-insensitively. A cue
    earns its place by reaching what nothing else reaches.
    """
    spans: list[Span] = []
    for match in _SURNAME_CUE_RE.finditer(text):
        word = match.group(1)
        if _names_a_person(word):
            spans.append(Span(match.start(1), match.end(1), "NAME", word))
    return spans


def _merge_adjacent(spans: list[Span], text: str) -> list[Span]:
    """Join NAME spans separated only by whitespace into one.

    The parts of a person's name have to arrive as ONE span or the re-masking
    guard cannot recognise a token it minted: it compares a detected span with
    the token, and «Чижов», «Савва», «Романович» as three spans match none of
    them. The token is then masked a second time and the person changes identity
    mid-conversation — the exact failure `mask(mask(x)) != mask(x)` describes.
    """
    ordered = sorted(spans, key=lambda span: (span.start, span.end))
    out: list[Span] = []
    for span in ordered:
        if (out and span.entity_type == "NAME" and out[-1].entity_type == "NAME"
                and 0 <= span.start - out[-1].end <= 1
                and not text[out[-1].end:span.start].strip()):
            merged = Span(out[-1].start, span.end, "NAME",
                          text[out[-1].start:span.end])
            out[-1] = merged
            continue
        out.append(span)
    return out


def _joins_the_name(word: str) -> bool:
    """Whether the word beside a detected name belongs to it.

    Morphology first, as before. A MISSPELT name is admitted too — «Кзнецов
    Дмитрий» read as a plural noun, so morphology refused it and half the person
    went to the model in the clear.

    Still two signals, and the second is deliberately near-membership in the
    gazetteer rather than "capitalised and adjacent": the word after a given name
    is very often an ordinary one, and adjacency alone would mask it.
    """
    return _names_a_person(word) or _looks_misspelt_name(word)


def _adjacent_surnames(text: str, found: list[Span]) -> list[Span]:
    """Extend a known given name to the person-word beside it."""
    extra: list[Span] = []
    taken = {(span.start, span.end) for span in found}
    for span in found:
        for match in _WORD_RE.finditer(text[span.end:span.end + 24]):
            if match.start() > 1:      # not the immediately adjacent word
                break
            start, end = span.end + match.start(), span.end + match.end()
            if (start, end) not in taken and _joins_the_name(match.group()):
                extra.append(Span(start, end, "NAME", match.group()))
            break
        for match in reversed(list(_WORD_RE.finditer(text[max(0, span.start - 24):span.start]))):
            offset = max(0, span.start - 24)
            if span.start - (offset + match.end()) > 1:
                break
            start, end = offset + match.start(), offset + match.end()
            if (start, end) not in taken and _joins_the_name(match.group()):
                extra.append(Span(start, end, "NAME", match.group()))
            break
    return extra


_GLUED_NAME_RE = re.compile(r"\b([А-ЯЁ][а-яё]{2,})([А-ЯЁ][а-яё]{2,})\b")


def _glued_names(text: str, names: NameAssets) -> list[Span]:
    """Two name parts typed without the space between them.

    «ГончароваАнна», «СоколоваАнна», «КузнецоваОльга» — a missed space bar, and
    the whole person went to the model in the clear because no rule looks INSIDE
    a word. It is the shape the sloppy register produces most often after the
    Latin slip, and AgentPII's own misses carried it («СоколоваАнна» among them).

    BOTH halves must be name-ish, and that is what keeps brands out: «СберБанк»
    splits into «Сбер» and «Банк», «МосЭнерго» into «Мос» and «Энерго», and
    neither half is a name or a surname shape. Requiring only one half would
    mask every capitalised compound in the language.
    """
    spans: list[Span] = []
    for match in _GLUED_NAME_RE.finditer(text):
        left, right = match.group(1), match.group(2)
        if all(_is_known_name(part, names) or _is_surname_shaped(part, names)
               or part.lower().endswith(names.patronymic_suffixes)
               for part in (left, right)):
            spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    return spans


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
        lemmas = _lemmas(low)
        before = text[max(0, match.start() - 20):match.start()].lower()
        if _name_set_hit(word, low, lemmas, before, names):
            spans.append(Span(match.start(), match.end(), "NAME", word))
        elif word[:1].isupper() and (
            low in names.dict_first or low in names.dict_surnames
            or any(lemma in names.dict_first or lemma in names.dict_surnames
                   for lemma in lemmas)
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
    # A PATRONYMIC IS AN ANCHOR IN ITS OWN RIGHT, and it needs no dictionary.
    # «-ович», «-евич», «-овна», «-евна» mark a person in Russian whatever the
    # stem is, so a name built from words we have never seen is still a name —
    # which is exactly the case a gazetteer cannot reach.
    #
    # Found by a persona typing «Тестов Тест Тестович» to check the product
    # works. It found nothing, and the cost of that is not privacy — a
    # placeholder protects nobody — it is trust: a customer who sees «ничего не
    # найдено» on their own test concludes the product is broken and leaves
    # without writing to support. The same rule reaches real rare and foreign
    # names carrying a patronymic, which the gazetteer also misses.
    # Anchors are added BEFORE the neighbour pass, not alongside it: the pass
    # extends FROM an anchor, so an anchor introduced in the same expression is
    # invisible to it and «Тестов Тест» stays outside the span.
    spans = (spans + _patronymic_anchors(text) + _cued_name_parts(text)
             + _glued_names(text, names))
    spans = _merge_adjacent(spans + _adjacent_surnames(text, spans), text)
    for match in _LATIN_PAIR_RE.finditer(text):
        # ANY part may be the one we know. Requiring it of the FIRST word meant
        # «Ivanov Petr Sergeevich» matched nothing — the given name is in the
        # middle — and only the bare «Petr» was caught by the gazetteer, so the
        # surname and patronymic went to the model in the clear. Half a masked
        # name is worse than none: it looks protected and is not.
        parts = [group for group in match.groups() if group]
        # WHERE the known name stands decides whether the whole run is a name.
        # Opening it means «Petr Ivanov». Sitting second means «Ivanov Petr
        # Sergeevich» — but ONLY when a transliterated patronymic closes the run,
        # because «Dear Anna Kovalenko» has exactly the same shape and «Dear» is
        # not a surname. Without that the run swallowed English politeness and
        # handed «Dear Anna Kovalenko» to the tool as somebody's name.
        #
        # A rejected run is not a leak: the single-word gazetteer still masks the
        # given name inside it.
        first_known = parts[0].lower() in names.name_set
        patronymic_last = len(parts) == 3 and parts[2].lower().endswith(
            ("vich", "vna", "ich", "na"))
        second_known = len(parts) > 1 and parts[1].lower() in names.name_set
        if first_known or (second_known and patronymic_last):
            spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    for match in _INITIALS_RE.finditer(text):
        spans.append(Span(match.start(), match.end(), "NAME", match.group()))
    return spans
