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
from pseudex.fuzzy import build_index, lookup, within_one_edit, within_one_typo
from pseudex.morph import MORPH, is_stretched_filler
from pseudex import spoken

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


def _names_a_document(word: str) -> bool:
    """Слово называет ТИП ДОКУМЕНТА, а не человека.

    «ИНН», «СНИЛС», «паспорт», «карта» — арендуемый словарь ключей, по которому
    структурный слой уже типизирует значение. Слово из него не бывает частью
    имени ни при каких условиях, и это единственный вид соседа, о котором можно
    сказать так без оговорок.

    Живьём: «ашот инн», «кукушкин инн», «алиса инн» — в аргумент `customer_name`
    уезжало имя вместе со словом «ИНН», и CRM такую запись не находила.
    """
    return word.casefold() in ASSETS.get().structured.key_type


def _is_ordinary_word(word: str) -> bool:
    """Морфология знает слово, и ни одно чтение не называет человека."""
    parses = MORPH.parse(word)
    return bool(parses) and any(parse.is_known for parse in parses) and not any(
        _NAME_TAGS & set(parse.tag.grammemes) for parse in parses)


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
    # НАЗВАНИЕ ДОКУМЕНТА СНИМАЕТСЯ ДО ОДНОГО ТОКЕНА. Словарные циклы выше
    # останавливаются на двух, потому что там не видно, кто из двоих лишний;
    # здесь видно: «ИНН» человеком не бывает.
    while last > first and _names_a_document(tokens[last][2]):
        last -= 1
    while last > first and _names_a_document(tokens[first][2]):
        first += 1
    # A NUMBER WORD IS NEVER PART OF A PERSON — the last word of a dictated
    # СНИЛС («сорок восемсь кукушкин валерий михайлович») was swallowed into
    # the name, the name then overlapped the СНИЛС, lost the overlap, and the
    # whole person went to the model in the clear.
    while last > first and _is_numeral_word(tokens[last][2]):
        last -= 1
    while last > first and _is_numeral_word(tokens[first][2]):
        first += 1
    # ОПЕЧАТКА В ОБЫЧНОМ СЛОВЕ — ТОЖЕ ДО ОДНОГО ТОКЕНА, и видно её так же ясно.
    # «начальниик фёдорова», «мастеер новикова», «дежурныый новиков», «этоо
    # новикова», «фамилиято кузнецова» — NER отдаёт их одним человеком, потому
    # что опечатка делает слово неизвестным, а неизвестное слово с заглавной
    # соседа выглядит как редкая фамилия. Девятнадцать расхождений на плече
    # аргумента: инструмент получал слово, которое человеком не является,
    # приклеенным к настоящему имени.
    while last > first and _typo_of_an_ordinary_word(tokens[last][2]):
        last -= 1
    while last > first and _typo_of_an_ordinary_word(tokens[first][2]):
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
        best = max(parses, key=lambda parse: parse.score).tag.POS
        if best not in _NOT_A_NAME_POS and not is_stretched_filler(tokens[first][2]):
            break
        first += 1
    # ЗВАНИЕ И ДОЛЖНОСТЬ ПЕРЕД ИМЕНЕМ. «полковник Поляков», «дежурная полякова»,
    # «мастер Поляков», «сторож тагиев» — существительные и прилагательные, а
    # словарный цикл выше останавливается на двух токенах, потому что там нет
    # доказательства, кто из двоих лишний.
    #
    # ЗДЕСЬ ДОКАЗАТЕЛЬСТВО ЕСТЬ, И ОНО ДВОЙНОЕ: второе слово словарь ЗНАЕТ как
    # часть имени, а первое морфология знает как обычное слово и ни одно его
    # чтение имени не называет. Без второй половины правило съело бы «Иван
    # Петров», где обе части — имена; без первой — редкую фамилию, которую
    # словарь просто не содержит.
    if (last - first + 1 == 2
            and _is_name_part(tokens[last][2], names)
            and not _is_name_part(tokens[first][2], names)
            and _is_ordinary_word(tokens[first][2])):
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
    if _is_numeral_word(word):
        return False
    if len(word) < 3:
        return False
    # ЧЕТВЁРТЫЙ СТОРОЖ: растянутый филлер. Морфология незнакомое «иии» ни к чему
    # не относит, поэтому все три проверки ниже оно проходит молча, и «иии
    # ерохин» уходило к модели одним именем, а в CRM клиента — вместе с
    # филлером. Форма, а не список: у филлера не больше двух различных букв и
    # словарь его не знает.
    if is_stretched_filler(word):
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
# The inflection tail carries NO «я» and no «и». A patronymic never takes them
# in any case — «Ивановича», «Ивановичу», «Ивановичем», «Ивановиче» — but
# allowing «я» turned the anchor into «any word ending in -овная»: «основная»,
# «условная», «духовная», «церковная» all became somebody's patronymic and the
# sentence around them was destroyed. Found by running the detector over 993
# sentences of ordinary Russian nobody here wrote; our own 27-phrase set had
# never contained one.
_PATRONYMIC_RE = re.compile(
    r"\b[А-ЯЁа-яё]{3,}(?:" + "|".join(_PATRONYMIC_TAIL) + r")(?:[аеоуы]|ем|ым|ой)?\b")


_MISSPELT_PAIR_RE = re.compile(r"(?i)\b([а-яё]{4,})\s+([а-яё]{4,})\b")


def _damaged_name_pairs(text: str) -> list[Span]:
    """Two adjacent lower-case words where one is a name we cannot spell.

    THE GAP THIS CLOSES. `_looks_misspelt_name` is only ever consulted about a
    word standing NEXT TO A NAME WE ALREADY FOUND. In «алексй волков» there is
    no such name: the given name is mistyped so the gazetteer misses it, and the
    surname is lower case so the bulk dictionary — capital-only by design —
    misses it too. Neither word can anchor, the repair rule never runs, and both
    halves of a real person's name went to the model in the clear. Same for
    «игрь павлов». This is the ordinary shape of a chat message, and every set
    of ours writes names properly, so nothing we had could see it.

    THREE SIGNALS, STILL. The rule does not relax the bar, it moves the third
    signal from «next to a known name» to «next to a word that names a person»:

      1. the damaged word is UNKNOWN to pymorphy — the signal that separates
         «Кзнецов» from «заказ», «клиент», «спасибо», all of which sit one edit
         from a real rare surname and all of which the dictionary knows;
      2. it either parses as a person by suffix («игрь» → Name) or lands one
         edit from the gazetteer («алексй» → «алексей»);
      3. its neighbour independently names a person.

    A pair is required precisely because signal 2 alone is weak in lower case.
    One damaged word beside one person-naming word is a far stronger statement
    than either word alone, and it is the statement a mistyped name actually
    makes.
    """
    spans: list[Span] = []
    for match in _MISSPELT_PAIR_RE.finditer(text):
        left, right = match.group(1), match.group(2)
        for damaged, other in ((left, right), (right, left)):
            parses = MORPH.parse(damaged)
            if not parses or parses[0].is_known:
                continue
            # РАСТЯНУТЫЙ ФИЛЛЕР — НЕ ОПЕЧАТКА В ИМЕНИ. «иии» словарю неизвестно
            # и в 197-тысячном словаре лежит в одной правке от настоящего имени,
            # поэтому пара «иии ерохин» проходила все три сигнала и уезжала в
            # CRM клиента одним значением вместе с филлером. Речь тянет гласную,
            # а имя — нет.
            if is_stretched_filler(damaged):
                continue
            if _typo_of_an_ordinary_word(damaged) or _is_numeral_word(damaged) or _is_numeral_word(other):
                continue
            if not (_names_a_person(damaged) or _looks_misspelt_name(damaged)):
                continue
            # THE PREDICTED-PERSON READING IS THE WEAK SIGNAL, and for a LONG
            # word one edit from an ordinary one it is wrong: «выгрузуой
            # воронина елена» — «выгрузкой» with one letter slipped, predicted
            # as a given name, prepended to a real person, and the customer's
            # `first_name` became «выгрузуой». Short damaged names («игрь»,
            # «алексй») are one edit from short ordinary words too, so the
            # veto starts at seven letters, where the collision is the rule.
            if not _names_a_person(other):
                continue
            spans.append(Span(match.start(), match.end(), "NAME", match.group(0)))
            break
    return spans


_ALPHABET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"


def _one_edit_from_known_word(word: str) -> bool:
    """Whether one deletion, substitution or insertion turns the word into a
    word pymorphy3 knows. About 33 × (2n + 1) lookups, asked only of a long
    unknown lower-case word standing next to a name."""
    low = word.lower()
    variants: list[str] = []
    for index in range(len(low)):
        variants.append(low[:index] + low[index + 1:])
        variants.extend(low[:index] + letter + low[index + 1:] for letter in _ALPHABET if letter != low[index])
    for index in range(len(low) + 1):
        variants.extend(low[:index] + letter + low[index:] for letter in _ALPHABET)
    return any(_ordinary_known(variant) for variant in variants if MORPH.word_is_known(variant))


def _ordinary_known(word: str) -> bool:
    """Known to the dictionary as something other than a person. «павлович»
    is a dictionary word too, and «иван павловтч» is a patronymic with a slip,
    not «павлович» the ordinary word — there is no such thing."""
    return any(parse.is_known and not (_PERSON_TAGS & parse.tag.grammemes) for parse in MORPH.parse(word))


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
        # A NUMBER WORD IS NOT A SURNAME: the last word of a dictated СНИЛС
        # («сорок восемсь кукушкин валерий михайлович») passed the part-of-
        # speech guard as a noun and the name then lost its overlap with the
        # СНИЛС — the whole person went to the model in the clear.
        if _is_numeral_word(candidate):
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
    """Names indexed by their deletion neighbourhood, for one-edit lookup.

    FOR FINDING A NAME SOMEBODY MISTYPED. «Кзнецов Дмитрий» is detected as
    «Дмитрий» alone — morphology reads «Кзнецов» as a plural noun, so the
    neighbour rule refuses it — and the surname goes to the model in the clear.
    Half a masked name is a leak, and the benchmark's coverage metric exists
    because recall called that case found.

    This used to bucket by the first three and last three letters, on the
    argument that an edit at position p is caught by the first key when p ≥ 3 and
    by the last when p < len − 3. That argument is sound for insert, delete and
    substitute and was written before the distance widened to Damerau: a
    transposition touches two ADJACENT positions, so it needs one more position
    of separation than the other three kinds, and the two windows have it only at
    length seven. Measured, the scheme reached the source word 77.9% of the time
    at length five and 95.1% at length six — and given names are 49.2% six
    letters or shorter. See `bench/blocking_recall.py`, which still measures both.

    Entries shorter than five characters and the `ambiguous` list stay out. That
    is a PRECISION decision now, not an index limitation: the deletion index is
    complete at every length, so the floor is purely about how much of the
    language a one-edit ball reaches when the word is short.

    Keyed on the BUNDLE VERSION so a re-lease cannot serve an index built from
    the previous dictionary. The version is a content hash, so equal version
    means equal contents.
    """
    names = ASSETS.get().names
    return build_index(word for word in itertools.chain(names.dict_first,
                                                        names.dict_surnames)
                       if len(word) >= 5 and word not in names.ambiguous)


def _looks_misspelt_name(word: str) -> bool:
    """Whether this word is one edit away from a name we know.

    The second signal, and it is needed: the first — sitting next to a name we
    detected — is not enough on its own, because the word after a given name is
    very often an ordinary one. Requiring near-membership in the dictionary is
    the same tolerance the cue-word deny matching already uses, bounded the same
    way at a single edit.
    """
    if _is_numeral_word(word):
        return False
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
    # A DAMAGED CUE WORD IS NOT A NAME. «на имя ирину телефн 89505973171»,
    # «вольнов евгений телфеон» — unknown to morphology because it is
    # misspelt, adjacent to the name because it introduces the next field,
    # and one edit from a rare surname because the neighbourhood is dense.
    # The list is leased and short: the words that open a field.
    if any(within_one_typo(lowered, cue) for cue in ASSETS.get().names.never_cues):
        return False
    return lookup(lowered, _misspelling_index(ASSETS.version or ""))


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


_CUE_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _cue_regex(names: NameAssets) -> re.Pattern[str]:
    """The leased cue vocabulary as one alternation, built once per bundle."""
    key = ASSETS.version or ""
    cached = _CUE_RE_CACHE.get(key)
    if cached is None:
        parts = sorted((re.escape(cue) for cue in names.cues), key=len, reverse=True)
        cached = re.compile(r"(?i)\b(?:" + "|".join(parts) + r")\w*")
        _CUE_RE_CACHE.clear()
        _CUE_RE_CACHE[key] = cached
    return cached


def _cued_misspelt_names(text: str, names: NameAssets) -> list[Span]:
    """A MISSPELT name right after a cue word.

    `_looks_misspelt_name` is consulted in exactly one place — when extending an
    already-detected name to its neighbour — so a misspelt name standing ALONE is
    unreachable however clearly it is one. Measured: «клиент екатрина петрова» is
    found because «петрова» anchors it, and «запишите свтлана на завтра» is not,
    though «свтлана» is one edit from the dictionary, unknown to morphology, and
    sitting directly after a naming cue. In chat the lone form is the common one.

    THE CUE IS THE ANCHOR, and this is the same argument `_cued_name_parts`
    already makes for «фамилия»: the customer has told us the next word names a
    person, which is stronger than capitalisation and stronger than proximity to
    another name. Generalised here from that one word to the cue vocabulary.

    STILL THREE SIGNALS, and the third is inside `_looks_misspelt_name`: the cue,
    one edit from the dictionary, AND unknown to morphology. The last is not
    optional — in a 197k-name dictionary the distance-1 neighbourhood is dense
    enough that ordinary words land in it, and a cue does nothing to exclude them:
    «перезвоните заказу» would otherwise become a person.
    """
    spans: list[Span] = []
    for match in _cue_regex(names).finditer(text):
        tail = text[match.end():match.end() + 40]
        word = _WORD_RE.search(tail)
        if word is None or word.start() > 2:
            continue
        candidate = word.group()
        if len(candidate) < 4 or candidate.lower() in names.stopwords:
            continue
        if not _looks_misspelt_name(candidate):
            continue
        start = match.end() + word.start()
        spans.append(Span(start, match.end() + word.end(), "NAME", candidate))
    return spans


def _merge_adjacent(spans: list[Span], text: str) -> list[Span]:
    """Join NAME spans separated only by whitespace into one.

    The parts of a person's name have to arrive as ONE span or the re-masking
    guard cannot recognise a token it minted: it compares a detected span with
    the token, and «Чижов», «Савва», «Романович» as three spans match none of
    them. The token is then masked a second time and the person changes identity
    mid-conversation — the exact failure `mask(mask(x)) != mask(x)` describes.
    """
    # A STRETCHED FILLER IS NEVER PART OF A NAME. «ноль два ии саркисян
    # карен» — «ии» arrived as a NAME span of its own and the merge glued it
    # on as a first name; the agent's CSV then had three cells for two.
    ordered = sorted((span for span in spans
                      if not (span.entity_type == "NAME" and is_stretched_filler(span.value.lower()))),
                     key=lambda span: (span.start, span.end))
    out: list[Span] = []
    for span in ordered:
        # OVERLAPPING SPANS MERGE TOO, not just adjacent ones. The rules produce
        # sliding windows over the same person — «лебедев», «лебедев максим»,
        # «максим олегоич», «олегоич» for one three-part name — and joining only
        # touching spans left the overlap resolver to CHOOSE between «лебедев
        # максим» and «олегоич». It picks both, being non-overlapping, and one
        # person arrives as two spans, two tokens and two pseudonyms. That is the
        # split-identity failure this function exists to prevent; it was closed
        # for the adjacent case and open for the overlapping one.
        if (out and span.entity_type == "NAME" and out[-1].entity_type == "NAME"
                and span.start - out[-1].end <= 1
                and not text[min(out[-1].end, span.start):span.start].strip()):
            end = max(out[-1].end, span.end)
            out[-1] = Span(out[-1].start, end, "NAME", text[out[-1].start:end])
            continue
        out.append(span)
    return out


def _joins_the_name(word: str, anchor: str) -> bool:
    """Whether the word beside a detected name belongs to it.

    Morphology first, as before. A MISSPELT name is admitted too — «Кзнецов
    Дмитрий» read as a plural noun, so morphology refused it and half the person
    went to the model in the clear.

    Still two signals, and the second is deliberately near-membership in the
    gazetteer rather than "capitalised and adjacent": the word after a given name
    is very often an ordinary one, and adjacency alone would mask it.
    """
    if _typo_of_an_ordinary_word(word) or _is_numeral_word(word):
        return False
    return (_names_a_person(word) or _looks_misspelt_name(word)
            or _agrees_as_a_name(word, anchor))


def _is_numeral_word(word: str) -> bool:
    """A number word, spelled right or as the transcript misspells it. A
    numeral is never part of a person: «подлесная тридц один» is a street and
    a house, and the name arm made it a three-word person because «тридц» is
    unknown to morphology and sits beside a word that can be a surname."""
    low = word.lower()
    if low in spoken.CARDINALS:
        return True
    return ASSETS.is_loaded and low in ASSETS.get().spoken.numeral_typos


def _typo_of_an_ordinary_word(word: str) -> bool:
    """Слово в одной ОПЕЧАТКЕ от обычного русского слова — это оно и есть.

    «начальниик фёдорова», «мастеер новикова», «дежурныый новиков», «этоо
    новикова», «фамилиято кузнецова» — девятнадцать расхождений на плече
    аргумента, и каждое отдавало инструменту слово, которое человеком не
    является, приклеенным к настоящему имени.

    ПОЧЕМУ ОНИ ПРОХОДИЛИ. Правило про опечатку в имени требует трёх сигналов, и
    первый из них — слово НЕИЗВЕСТНО морфологии. Опечатка в обычном слове тоже
    делает его неизвестным, и дальше «рядом с именем» и «в одной правке от
    словаря» выполняются сами собой: в 197-тысячном словаре фамилий окрестность
    одной правки плотная — про это в файле уже написано, и здесь тот же долг с
    другой стороны.

    ЧЕТВЁРТЫЙ СИГНАЛ — САМА ОПЕЧАТКА. Удаление одного символа даёт слово,
    которое морфология знает: «начальниик» -> «начальник», «этоо» -> «это»,
    «фамилиято» -> «фамилият»... нет, а вот «фамилиято» -> «фамилиято» без
    буквы «т» не выходит, поэтому проверяются ВСЕ позиции. Именем такое слово
    быть не должно: «Иваанов» удалением даёт «Иванов», у которого есть чтение
    Surn, и он остаётся именем — иначе правило съело бы настоящую опечатку в
    фамилии, ради которой оно и написано.
    """
    if len(word) < 4:
        return False
    lowered = word.lower()
    # A STRETCHED FILLER IS AN ORDINARY WORD: «ноль два ии саркисян карен» —
    # the conjunction held for a beat — joined the name as its first word,
    # and the CSV row the agent built had three cells for two.
    if is_stretched_filler(lowered):
        return True
    # A DAMAGED CUE WORD IS THE COMMONEST TYPO NEXT TO A NAME, and it is not a
    # doubled letter: «телефн», «телфеон» — the word that opens the NEXT field,
    # which pymorphy3 then predicts as a person because it is unknown. One
    # edit from the leased list of field-opening words is an ordinary word.
    if any(within_one_typo(lowered, cue) for cue in ASSETS.get().names.never_cues):
        return True
    # A LONG UNKNOWN WORD ONE EDIT FROM AN ORDINARY WORD IS THAT WORD.
    # «выгрузуой воронина елена» — «выгрузкой» with one letter slipped,
    # predicted as a given name and prepended to a real person, so the
    # customer's `first_name` became «выгрузуой». The general one-edit veto
    # was measured at four real people on NEREL and refused; bounded at seven
    # letters it leaves «игрь», «алексй» and every short mistyped name alone,
    # and long words are where the ordinary vocabulary is dense.
    if len(lowered) >= 7 and not MORPH.word_is_known(lowered) and _one_edit_from_known_word(lowered):
        return True
    # СЛОВО, У КОТОРОГО ЕСТЬ СВОЁ ИМЕННОЕ ЧТЕНИЕ, ОПЕЧАТКОЙ НЕ СЧИТАЕТСЯ.
    # «роману» удалением даёт «роман» — обычное слово, — но само «роману» несёт
    # чтение Name, и правило про опечатку тут ни при чём: это настоящее имя в
    # дательном падеже, ради которого написано согласование выше.
    #
    # ТОЛЬКО ЗНАКОМОЕ СЛОВО. pymorphy3 ПРЕДСКАЗЫВАЕТ любое незнакомое слово с
    # именной флексией как женское имя — «карточкуу», «заведитее», «хочуу»
    # получают NOUN,anim,femn,Name — и этот выход срабатывал раньше цикла
    # удвоения, который ответил бы верно. Живой прогон v4: «заведитее карточкуу
    # букин сергей иванович» стал одним именем из пяти слов, и агент переспросил,
    # какие из них — ФИО. У «роману», ради которого написан выход, чтение
    # настоящее — оно из словаря.
    parses = MORPH.parse(word)
    if parses and parses[0].is_known and any(_PERSON_TAGS & parse.tag.grammemes for parse in parses):
        return False
    # ТОЛЬКО УДВОЕННАЯ БУКВА, И ЭТО ИЗМЕРЕНО. Любая одиночная правка стоила
    # четырёх настоящих людей на NEREL (93.5% -> 93.2%) и 0.4 пункта полноты на
    # MASSIVE ради 19 мусорных слов в аргументе: словарь фамилий плотный, и
    # настоящая редкая фамилия сама лежит в одной правке от обычного слова —
    # тот же долг, о котором файл уже предупреждает, с другой стороны.
    #
    # Удвоение — это ОПЕЧАТКА КЛАВИАТУРЫ, а не сходство: «начальниик»,
    # «мастеер», «дежурныый», «этоо». Настоящая фамилия, у которой снятие
    # удвоения даёт обычное слово, встречается несравнимо реже.
    for index in range(1, len(lowered)):
        if lowered[index] != lowered[index - 1]:
            continue
        repaired = lowered[:index] + lowered[index + 1:]
        if len(repaired) < 3:
            continue
        parses = MORPH.parse(repaired)
        if not parses or not parses[0].is_known:
            continue
        if any(_PERSON_TAGS & parse.tag.grammemes for parse in parses):
            continue
        return True
    return False


def _agrees_as_a_name(word: str, anchor: str) -> bool:
    """Сосед согласован с найденным именем В ПАДЕЖЕ И РОДЕ — значит это пара.

    ЧТО ЭТО ОБХОДИТ И ПОЧЕМУ ТОЛЬКО ЭТО. `_names_a_person` отвергает слово,
    лучший разбор которого — НЕОДУШЕВЛЁННОЕ существительное, и сторож
    измеренный: «романа» и «слава» — вещи, их именные чтения настоящие, но не то,
    что значит предложение. Он же выбрасывал «роману ерохину» и «лыткиной
    марине» — обычную форму русской диспетчерской записи, где имя стоит в
    косвенном падеже и со строчной.

    Согласование — это тот сигнал, которого сторожу не хватало. Книга рядом с
    человеком в падеже и роде с ним не сходится: «романа ерохина» требует, чтобы
    оба слова несли ИМЕННОЕ чтение в одном падеже и одном роде, а «слава богу» —
    именительный против дательного — не проходит. Остальные три сторожа
    (`длина`, `часть речи`, `филлер`) остаются: предлог рядом с именем ни в
    каком падеже именем не станет.
    """
    if len(word) < 3 or is_stretched_filler(word):
        return False
    parses = MORPH.parse(word)
    if not parses:
        return False
    if max(parses, key=lambda parse: parse.score).tag.POS in _NOT_A_NAME_POS:
        return False
    theirs = {(parse.tag.case, parse.tag.gender) for parse in MORPH.parse(anchor)
              if _PERSON_TAGS & parse.tag.grammemes
              and parse.tag.case and parse.tag.gender}
    if not theirs:
        return False
    return any((parse.tag.case, parse.tag.gender) in theirs
               for parse in parses if _PERSON_TAGS & parse.tag.grammemes)


def _adjacent_surnames(text: str, found: list[Span]) -> list[Span]:
    """Extend a known given name to the person-word beside it."""
    extra: list[Span] = []
    taken = {(span.start, span.end) for span in found}
    for span in found:
        for match in _WORD_RE.finditer(text[span.end:span.end + 24]):
            if match.start() > 1:      # not the immediately adjacent word
                break
            start, end = span.end + match.start(), span.end + match.end()
            if (start, end) not in taken and _joins_the_name(match.group(), span.value):
                extra.append(Span(start, end, "NAME", match.group()))
            break
        for match in reversed(list(_WORD_RE.finditer(text[max(0, span.start - 24):span.start]))):
            offset = max(0, span.start - 24)
            if span.start - (offset + match.end()) > 1:
                break
            start, end = offset + match.start(), offset + match.end()
            if (start, end) not in taken and _joins_the_name(match.group(), span.value):
                extra.append(Span(start, end, "NAME", match.group()))
            break
    return extra


_GLUED_NAME_RE = re.compile(r"\b([А-ЯЁ][а-яё]{2,})([А-ЯЁ][а-яё]{2,})\b")



# OVERLAPPING PAIRS, hence the lookahead. Consuming the match made «Кузнецова
# Ол ьга» try «Кузнецова Ол» — not a name — and never reach «Ол ьга», which is
# one. Every adjacent pair has to be offered, not every second one.
# Parts of speech that a fragment of a surname can never be.
_FUNCTION_WORD = frozenset({"PREP", "CONJ", "PRCL", "NPRO", "INTJ"})

_SPLIT_PAIR_RE = re.compile(
    r"(?=\b([А-Яа-яЁёA-Za-z]{2,})\s([А-Яа-яЁёA-Za-z]{1,})\b)")


def _split_name_parts(text: str, found: list[Span], names: NameAssets) -> list[Span]:
    """One name with a stray space INSIDE it.

    «Фёдо ров Кирилл», «Вол ков Сергей», «Куз нецова Ольга», «Ивано в Пётр»,
    «Кузнецова Ол ьга». `_glued_names` handles the missing space; this is the
    same slip in the other direction, and it is worse: the extra space breaks
    the surname into two words that no rule can read, so «Фёдо ров Кирилл» was
    detected as «Кирилл» alone and HALF THE PERSON'S SURNAME went to the model
    in the clear inside a message that looked protected. Twelve of AgentPII's
    broken round trips are this, and every one of them is also a leak.

    TWO SIGNALS, and the second is what makes the first usable. The two
    fragments joined must BE a name we know — «Фёдо»+«ров» is «Фёдоров», while
    «до»+«говор» is «договор» and no name at all. And the pair must stand beside
    a name already detected. The join alone is not enough: «по пова» joins to
    «попова» and «за харов» to «захаров», both real surnames, and both ordinary
    Russian phrases. Measured on the corpus, EVERY split name has a detected
    name touching it — the given name survives because only the surname was cut
    — so the anchor costs no recall and removes the whole false-positive class.
    """
    anchors = [(span.start, span.end) for span in found if span.entity_type == "NAME"]
    if not anchors:
        return []
    extra: list[Span] = []
    for match in _SPLIT_PAIR_RE.finditer(text):
        left, right = match.group(1), match.group(2)
        # THE LEFT FRAGMENT MAY NOT BE A FUNCTION WORD. `_is_surname_shaped`
        # reads the suffix and nothing else, so «на»+«Лебедева» joins to
        # «наЛебедева», ends in «ева» and passes — every «Заказ на Лебедева
        # Ирина Петровна» in the corpus grew a preposition INSIDE the person's
        # name and the tool was called with it. 123 round trips, from one word
        # of slack. Requiring the join to be a name we KNOW was the other
        # candidate and is too narrow: the shipped dictionary is a compact seed
        # and «Фёдоров», «Волков», «Шевчук» are not in it.
        #
        # A stray space never turns a preposition into half a surname, so the
        # rule is the one the neighbour pass already uses: the best reading must
        # not be a function word. «на», «по», «за», «до», «при», «в», «это»,
        # «что» all go out on it; «Фёдо», «Вол», «Куз», «Маме», «Заха» do not.
        if MORPH.parse(left)[0].tag.POS in _FUNCTION_WORD:
            continue
        # ПЯТЫЙ СТОРОЖ: растянутый филлер не половина фамилии. «иии» словарю
        # неизвестно, служебным словом не является, а «иииерохин» кончается на
        # «-ин» — то есть все четыре сигнала правило проходило, и «иии ерохин»
        # уезжало в CRM клиента одним значением. Речь тянет гласную, фамилия —
        # никогда.
        if is_stretched_filler(left) or is_stretched_filler(right):
            continue
        # ОПЕЧАТКА В ОБЫЧНОМ СЛОВЕ — НЕ ОБЛОМОК ФАМИЛИИ. Четвёртый сторож ниже
        # спрашивает «не целое ли это слово», и опечатка целым словом не
        # является: «начальниик фёдорова» склеивалось в «начальниикфёдорова»,
        # проходило все четыре условия и уходило в инструмент одним человеком.
        # То же с «мастеер», «дежурныый», «этоо», «фамилиято» — девятнадцать
        # расхождений на плече аргумента.
        # A numeral is never half of a surname («восемсь» + «кукушкин»).
        if (_typo_of_an_ordinary_word(left) or _typo_of_an_ordinary_word(right)
                or _is_numeral_word(left) or _is_numeral_word(right)):
            continue
        # A FUNCTION WORD ON THE RIGHT NEEDS AN UNKNOWN WORD ON THE LEFT.
        # «Ивано в Пётр» and «Григорье в Никита» are surnames cut before their
        # last letter, and that letter happens to be a preposition — so «в»
        # cannot simply be refused. What separates them from «Иван слово в слово
        # повторил» is the other half: «Ивано» and «Григорье» are not words,
        # «слово» is.
        if (MORPH.parse(right)[0].tag.POS in _FUNCTION_WORD
                and MORPH.parse(left)[0].is_known):
            continue
        if not (_is_known_name(left + right, names)
                or _is_surname_shaped(left + right, names)):
            continue
        # AT LEAST ONE FRAGMENT MUST NOT BE A WORD, and this is the signal that
        # carries the actual information. The shape test above reads the suffix
        # of the JOINED string, which is the suffix of the right fragment and
        # says nothing about whether the two belong together — so «получатель
        # Новикова» and «получит иванов пётр» joined too, and the tool was
        # called with the word «получатель» inside somebody's name.
        #
        # A space typed by accident lands INSIDE a word, so at least one side of
        # it is left as a non-word. Where both halves are ordinary words —
        # «Вол ков», and it is a real case — nothing distinguishes the split
        # from ordinary Russian, and this rule correctly declines to guess.
        if MORPH.parse(left)[0].is_known and MORPH.parse(right)[0].is_known:
            continue
        # THE LEFT FRAGMENT IS A PIECE OF A WORD, not a whole one. A typo in the
        # surname satisfies the test above all by itself — «Влкова» and «Зааров»
        # are unknown because they are misspelt — so «получатель Влкова Татьяна»
        # and «фамилия саркисян» joined their cue word into the person's name
        # and sent it to the tool.
        #
        # A stray space lands INSIDE a word, so what stands to its left is
        # either not a word at all («Фёдо», «Куз», «Ивано», «Григорье») or too
        # short to be the one meant («Шев», «Маме», «Вал»). A complete word of
        # five letters or more is a word, and «получатель», «фамилия» and
        # «слово» are all refused by that.
        if MORPH.parse(left)[0].is_known and len(left) >= 5:
            continue
        # A zero-width match: the pair's own bounds come from its groups.
        pair_start, pair_end = match.start(1), match.end(2)
        # Touching an anchor, on either side. A name split by a space keeps its
        # other part whole, and that part is what was found.
        # OVERLAPPING COUNTS AS TOUCHING. The neighbour pass may already have
        # eaten the pair's second half — in «Маме дова Лейла» it extends «Лейла»
        # left to «дова» — so the pair then sits INSIDE the anchor rather than
        # beside it, and a strict adjacency test left «Маме» outside and leaking.
        touching = [(start, end) for start, end in anchors
                    if start <= pair_end + 1 and pair_start <= end + 1]
        if not touching:
            continue
        # EMITTED WHOLE, anchor included, rather than as the pair alone. The two
        # overlap — «Маме дова» against «дова Лейла» — and overlap resolution
        # keeps the longer and orphans the rest, so «Маме» stayed outside and
        # went to the model. One span covering both cannot be split that way.
        start = min([pair_start] + [a for a, _ in touching])
        end = max([pair_end] + [b for _, b in touching])
        extra.append(Span(start, end, "NAME", text[start:end]))
    return extra


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


_LOWER_WORD_RE = re.compile(r"\b[а-яё]{3,}\b")


def _lowercase_name_pairs(text: str, names: NameAssets) -> list[Span]:
    """Two adjacent LOWER-CASE words that are a surname and a given name.

    The bulk dictionaries are capital-only by design, and that design is right:
    197k surnames matched case-insensitively would mask every sentence holding an
    ordinary word that is also somebody's surname. But it leaves a hole the whole
    chat register falls into — «лебедева ирена», «соколова анна», «морозов
    алексей» are invisible while «Лебедева Ирена» is found, and a customer typing
    on a phone writes the first.

    THE CAPITAL WAS ONE OF TWO SIGNALS. Removing it needs a replacement, not an
    exception, and the replacement is the CONFIGURATION: one word a known
    surname, the OTHER a known given name. Ordinary Russian prose puts those two
    next to each other very rarely, because the pair is a naming pattern rather
    than a grammatical one — which is the same reason the capitalised rule works.

    Both words must additionally pass `_names_a_person`, so a verb, a preposition
    or an inanimate noun cannot take a slot even when the dictionary lists it.
    That is the guard that keeps «роза» and «слава» out: they are in the
    dictionaries and they are things.

    Deliberately NOT extended to (surname, surname) or (given, given): «мороз
    зима», «вера надежда» are ordinary Russian, and the complementary
    configuration is what makes the rule mean something.
    """
    # ВСЕ соседние пары, а не непересекающиеся совпадения regex. `finditer`
    # берёт пары подряд и не возвращается: «позвоните лебедева ирена» отдавало
    # ему «позвоните лебедева», после чего настоящая пара начиналась за границей
    # уже потреблённого куска и не находилась вовсе.
    words = list(_LOWER_WORD_RE.finditer(text))
    spans: list[Span] = []
    for first, second in zip(words, words[1:]):
        if text[first.end():second.start()].strip():
            continue                      # между словами не только пробелы
        left, right = first.group(), second.group()
        # A coherent naming order in EITHER direction — Russian writes both.
        coherent = ((left in names.dict_surnames and right in names.dict_first)
                    or (left in names.dict_first and right in names.dict_surnames))
        if not coherent:
            continue
        if not (_names_a_person(left) and _names_a_person(right)):
            continue
        spans.append(Span(first.start(), second.end(), "NAME",
                          text[first.start():second.end()]))
    return spans


# Ниже этой длины строчное словарное слово почти всегда что-то другое: словарь
# фамилий содержит 196 800 записей, и короткие из них — «мир», «дом», «пол» —
# сталкиваются с языком чаще, чем называют людей.
#
# ЧЕТЫРЁХБУКВЕННЫЙ ПОРОГ ИЗМЕРЕН И ОТВЕРГНУТ. На 300 размеченных вручную
# вхождениях настоящей речи он находит девять имён (азиз, алик, алсу, илик,
# ирка, лекс, лера, леся, шура) и маскирует тридцать обычных слов — «вейп»,
# «мега», «слыш», «джек», «лайт», «ляма», «раша», «дите». Три лишних маски на
# одного найденного человека.
#
# КАЖДЫЙ ДРУГОЙ ПРИБОР НАЗЫВАЛ ЭТУ ПРАВКУ БЕСПЛАТНОЙ. NEREL дал +3 спана из
# 9 720, набор из 538 фраз не шелохнулся, а полнота имён на MASSIVE выросла
# 76.4% -> 77.1%. Все три написаны прописными буквами или размечены только по
# полноте, а вред живёт в строчной разговорной речи и виден только тому
# прибору, который её и читает — bench/gate.
_LOWER_DICT_MIN = 5

_HYPHENS = "-\u2011"


def _hyphen_token(text: str, start: int, end: int) -> str | None:
    """Весь дефисный токен, если найденное слово — лишь его часть."""
    glued = ((start and text[start - 1] in _HYPHENS)
             or (end < len(text) and text[end] in _HYPHENS))
    if not glued:
        return None
    lo, hi = start, end
    while lo > 1 and text[lo - 1] in _HYPHENS and text[lo - 2].isalpha():
        lo -= 1
        while lo and text[lo - 1].isalpha():
            lo -= 1
    while hi + 1 < len(text) and text[hi] in _HYPHENS and text[hi + 1].isalpha():
        hi += 1
        while hi < len(text) and text[hi].isalpha():
            hi += 1
    return text[lo:hi]


def _whole_token_ok(text: str, start: int, end: int) -> bool:
    """ДЕФИС СКЛЕИВАЕТ ОДИН ТОКЕН, И СУДИТЬ НАДО ТОКЕН, А НЕ ПОЛОВИНУ.

    Словарное попадание на часть составного слова — свидетельство про часть, а
    к модели уходит целое, и там получается чудовище: «Лос-Анджелесе» ->
    «Любовь-Анджелесе», «Алма-Ате» -> «Зоя-Демьяну», «де-юре» -> «де-Ивану».
    Город становится искалеченным человеком, подмена возвращается на обратном
    пути и портит название в вызове инструмента.

    НИ ОДИН НАШ ПРИБОР ЭТОГО НЕ ВИДЕЛ, и в обоих случаях по своей причине.
    Точность на NEREL засчитывает спан, пересёкшийся с любой эталонной
    сущностью, — а «Лос» лежит внутри размеченного города; чистый набор из 538
    фраз не содержит ни одного составного топонима. 86 спанов на 933
    документах, и все до одного — куски топонимов, ни одного человека.

    Тест — тот же, что у `_lowercase_dictionary_ok`, и это не совпадение:
    вопрос дословно тот же, только задан целому слову. «Жан-Клод» и
    «Римский-Корсаков» морфология знает как имена и они проходят; «Петров-то» и
    «Ким-то» она не знает вовсе, но читает как фамилию с частицей — тоже
    проходят, и это важнее, чем кажется: список частиц пришлось бы держать
    вручную, а он здесь получается сам.
    """
    whole = _hyphen_token(text, start, end)
    if whole is None:
        return True
    return not any(
        parse.is_known and not ({"Name", "Surn", "Patr"} & set(parse.tag.grammemes))
        for parse in MORPH.parse(whole))


def _lowercase_dictionary_ok(word: str, low: str) -> bool:
    """Может ли СТРОЧНОЕ слово из большого словаря назвать человека.

    ЗАЧЕМ СНИМАТЬ ЗАГЛАВНУЮ. Измерено на настоящей речи: из 569 промахов по
    именам 474 — слова, которые УЖЕ ЛЕЖАТ В СЛОВАРЕ, и отвергала их только
    заглавная. «морзов по улицам не пройти», «здравствуйте васильев седьмое
    отделение», «а захаров к 10 часам» — в диспетчерской речи слова-подсказки
    нет, а заглавных нет вовсе: ни одной на 16 521 реплику MASSIVE.

    ПРАВИЛО ТО ЖЕ, ЧТО У `ambiguous`, И ЭТО НЕ СОВПАДЕНИЕ. Слово принимается,
    только если pymorphy НЕ знает его как обычное русское слово. Тот же тест
    уже решает, какое семя требует заглавной («вера», «роман», «любовь»), и
    вместо второго списка, который придётся держать в согласии с первым, здесь
    задаётся тот же вопрос большому словарю.

    Измерено на 116 685 словах новостной прозы: правило впускает 38 слов, из
    которых обычными являются «якобы», «данной», «марки» — их этот тест и
    отсеивает; остальные («чехов», «жуков», «акбар») настоящие фамилии.
    """
    if len(word) < _LOWER_DICT_MIN:
        return False
    parses = MORPH.parse(word)
    if not parses:
        return False
    # КАЖДОЕ ЧТЕНИЕ, А НЕ ЛУЧШЕЕ — правило, которое этот репозиторий уже
    # оплатил дважды. `parse[0]` для «жуков» отдаёт фамилию Жуков, и
    # «Рокфеллер коллекционировал жуков» стало человеком; «флору» и «де-юре»
    # тем же путём. Слово отвергается, если ХОТЬ ОДНО его чтение — обычное
    # русское слово, потому что именно это чтение и встретится в прозе.
    # ПРИТЯЖАТЕЛЬНОЕ ОТ ТОЙ ЖЕ ФАМИЛИИ — НЕ СВИДЕТЕЛЬСТВО ПРОТИВ НЕЁ. У каждой
    # русской фамилии на -ов/-ев/-ин есть форма «Иванов дом», и pymorphy3 честно
    # выдаёт её как ADJF,Poss — обычное слово без пометы имени. Тест видел это
    # чтение и отвергал ВСЮ самую частую форму русской фамилии: «господином
    # ивановым», «врачом петровым», «письмо поповой» не находились вовсе.
    #
    # Прощается ровно один случай, и ЛЕММА — то, что его отличает. У «ивановым»
    # притяжательное чтение имеет ту же нормальную форму «иванов», что и
    # фамильное: это одно слово, взятое с другой стороны. У «жуков» обычное
    # чтение даёт «жук», у «попов» — «поп», у «машин» — «машина», у «варя» —
    # «варить»: другое слово, и оно-то и встретится в прозе. Сужено до ADJF,Poss
    # намеренно: без этого «жуков» проходил бы, потому что среди его чтений есть
    # фамильное с леммой «жук», — и это ровно тот дефект, за который репозиторий
    # заплатил трижды.
    name_lemmas = {parse.normal_form for parse in parses
                   if {"Name", "Surn", "Patr"} & set(parse.tag.grammemes)}
    for parse in parses:
        if not parse.is_known:
            continue
        if {"Name", "Surn", "Patr"} & set(parse.tag.grammemes):
            continue
        if ("ADJF" in parse.tag and "Poss" in parse.tag.grammemes
                and parse.normal_form in name_lemmas):
            continue
        return False
    return True


def _lemma_lookup_ok(low: str) -> bool:
    """Можно ли искать по ЛЕММЕ, а не только по написанному слову."""
    parses = MORPH.parse(low)
    if any(parse.is_known for parse in parses):
        return True
    return any({"Name", "Surn", "Patr"} & set(parse.tag.grammemes)
               for parse in parses)


_POSS_SUFFIXES = ("ин", "ын", "ов", "ев")


def _possessive_base(word: str) -> list[str]:
    """Имя, от которого образовано притяжательное: «женин» -> «женя»."""
    out: set[str] = set()
    for parse in MORPH.parse(word):
        if "Poss" not in parse.tag.grammemes or "ADJF" not in parse.tag:
            continue
        for suffix in _POSS_SUFFIXES:
            if parse.normal_form.endswith(suffix):
                root = parse.normal_form[:-len(suffix)]
                out |= {root + "я", root + "а", root + "ь", root}
    return [name for name in out if len(name) > 2]


def _possessive_names(text: str, names: NameAssets) -> list[Span]:
    """«женин день рождения», «олино письмо», «машиного дня рождения».

    ТАК ПО-РУССКИ ГОВОРЯТ О ЧУЖОМ, и ни одна ветка этого не видела: слово не
    стоит в словаре, не имеет заглавной и морфологически является
    ПРИЛАГАТЕЛЬНЫМ. На MASSIVE ru-RU это самый крупный чинимый класс промахов
    по именам, и каждый из них — частное лицо, а не публичная фигура.

    ДВА ГЕЙТА, И КАЖДЫЙ ОТБИВАЕТ СВОЁ. Притяжательное чтение отбивает «пять
    машин»: у родительного множественного от «машина» чтения `Poss` нет вовсе,
    поэтому кандидат даже не рождается. Словарь базового имени отбивает
    «мамин», «папин», «бабушкин», «дядин», «сестрин», «соседкин» — у всех
    `Poss` есть, и только имя за ними не стоит.

    СОГЛАСОВАНИЕ СО СЛЕДУЮЩИМ СУЩЕСТВИТЕЛЬНЫМ — третий гейт и он про другое:
    притяжательное всегда определяет предмет, и без предмета рядом это другое
    слово. Оно же удерживает разбор от того, чтобы принять за притяжательное
    случайное совпадение формы.

    ЦЕНА НАЗВАНА ВСЛУХ: подмена встаёт в именительном, потому что образовать
    притяжательное от произвольного имени морфология не берётся. Модель читает
    «Оксана чемодан уже собран», и обратный путь возвращает «Женя», а не
    «женин» — формулировка меняется. Это хуже грамматически и лучше по сути:
    иначе «женин» уходит к модели открытым текстом, а из него имя достаёт кто
    угодно. Инструмент при этом получает «Женя» — то есть человека, а не форму
    слова.
    """
    spans: list[Span] = []
    tokens = list(_WORD_RE.finditer(text))
    for index, match in enumerate(tokens):
        low = match.group().lower()
        bases = _possessive_base(low)
        if not any(base in names.dict_first or base in names.name_set
                   for base in bases):
            continue
        if index + 1 >= len(tokens):
            continue
        following = MORPH.parse(tokens[index + 1].group().lower())
        possessive = [parse for parse in MORPH.parse(low)
                      if "Poss" in parse.tag.grammemes and "ADJF" in parse.tag]
        agrees = any(
            "NOUN" in noun.tag and adjective.tag.case == noun.tag.case
            and adjective.tag.number == noun.tag.number
            and (adjective.tag.number == "plur"
                 or adjective.tag.gender == noun.tag.gender)
            for adjective in possessive for noun in following)
        if not agrees:
            continue
        # СПАН НЕСЁТ БАЗОВОЕ ИМЯ, А НЕ НАПИСАННУЮ ФОРМУ, и это не мелочь.
        # `span.value` — одновременно ключ волта и источник рода, поэтому с
        # притяжательной формой «Женя» и «женин» становились ДВУМЯ строками:
        # один человек с двумя подменами, «Лада приедет завтра, Тимофей чемодан
        # уже собран» — и вторая подмена ещё и мужская, потому что род читался с
        # прилагательного. Это тот самый отказ, который продукт считает
        # недопустимым, и ни один наш корпус его не видит: притяжательного
        # регистра нет ни в одном, кроме MASSIVE, а MASSIVE меряет только
        # полноту.
        base = sorted(name for name in bases
                      if name in names.dict_first or name in names.name_set)[0]
        spans.append(Span(match.start(), match.end(), "NAME", base.capitalize()))
    return spans


_STREET_PREP = re.compile(r"(?i)\b(?:на|по)\s+$")
_STREET_REF_NUMBER = re.compile(r"\s*(?:\d|"
                                r"нол|один|дв|тр|четыр|пят|шест|сем|восем|девят|"
                                r"десят|одиннадц|двенадц|тринадц|четырнадц|"
                                r"пятнадц|шестнадц|семнадц|восемнадц|девятнадц|"
                                r"двадц|тридц|сорок|пятьдес|шестьдес|семьдес|"
                                r"восемьдес|девяност|ст[оа]|двест|трист|четырест)")


def _street_reference(text: str, start: int, end: int) -> bool:
    """«на ленина торговый центр» — это улица, а не человек.

    Свежая беда, ровно от предыдущего послабления: строчная фамилия в
    родительном теперь проходит гейт, а половина русских улиц названа именно
    так. «на ленина торговый центр кит» уходило к модели как «на Ткаченко
    торговый центр кит» — место превращалось в несуществующего человека, и это
    хуже обычной лишней маски.

    Разделяют четыре вещи: слово стоит в реестре улиц ГАР, перед ним «на» или
    «по», читается оно как ФАМИЛИЯ и не как личное имя, и после него НЕТ номера.
    С номером это полноценный адрес, и его находит ветка адресов — здесь надо
    только не мешать. Без предлога «передайте петровой» остаётся человеком.

    ПРЕДЛОГИ «В» И «У» ИСКЛЮЧЕНЫ, И ЛИЧНЫЕ ИМЕНА ТОЖЕ — обе оговорки измерены, а
    не предположены. Общий список предлогов из адресной ветки съедал «какой
    номер у евгения», «у светланы есть новый адрес», «какой адрес у антона»: 12
    настоящих имён на MASSIVE. «У» вводит владельца, а не улицу; и «Ивана»,
    «Евгения», «Светланы» стоят в реестре ГАР, потому что там есть улица Ивана
    Франко, — но каждое из них читается ещё и как личное имя, а «Ленина» и
    «Петрова» только как фамилия.
    """
    address = ASSETS.get().address
    word = text[start:end].lower()
    if word not in address.street_names:
        return False
    if not _STREET_PREP.search(text[:start]):
        return False
    parses = MORPH.parse(word)
    if any("Name" in parse.tag for parse in parses):
        return False
    if not any("Surn" in parse.tag for parse in parses):
        return False
    return _STREET_REF_NUMBER.match(text[end:]) is None


_BIO_WINDOW = 60
_CYRILLIC_WORD_RE = re.compile(r"[а-яё]+")


def _not_ordinary(word: str) -> bool:
    parses = MORPH.parse(word)
    return bool(parses) and not any(
        parse.is_known and not ({"Name", "Surn", "Patr"} & set(parse.tag.grammemes))
        for parse in parses)


def _biographic_pairs(text: str, names: NameAssets) -> list[Span]:
    """Иностранное имя, которого нет ни в одном русском словаре.

    «билл гейтс», «шоне коннери», «тейлор свифт», «моргана фримена» — публичные
    фигуры, и по 152-ФЗ их имена такие же персональные данные, как имя клиента.
    Ни один газетир их не содержит, заглавной в чате нет, а морфологически это
    просто два неизвестных слова.

    ДВА СИГНАЛА, И ФОРМЫ ОДНОЙ МАЛО. Пара слов, ни одно из которых не является
    обычным русским словом, — это ещё «доу джонса» и «какеи нибудь»: на 1134
    чистых фразах голая форма срабатывала дважды, а точности у продукта ровно
    столько, сколько обещано, и запаса нет. Биографическая подсказка рядом
    убирает оба и оставляет шесть публичных фигур из семи.

    Подсказка ищется в ОКНЕ и не через границу предложения — то же правило и по
    той же причине, что у адресных подсказок: одно «родился» в начале длинного
    системного промпта иначе лицензирует каждую пару слов до самого конца.

    Первое слово пары, уже лежащее в словаре, пропускается: его находят другие
    ветки, и они знают о нём больше.
    """
    if not names.bio_cues:
        return []
    spans: list[Span] = []
    low = text.lower()
    tokens = list(_WORD_RE.finditer(text))
    for index in range(len(tokens) - 1):
        first, second = tokens[index], tokens[index + 1]
        head, tail = first.group().lower(), second.group().lower()
        if len(head) < 3 or len(tail) < 3:
            continue
        # ТОЛЬКО КИРИЛЛИЦА, И ТОЛЬКО ЧЕРЕЗ ОДИН ПРОБЕЛ. Прочитанные глазами
        # спаны на 933 документах NEREL показали, что без этих двух условий
        # ветка берёт «Associated Press», «Toyota Camry», «Minnesota Wild»,
        # «Pussy Riot» и даже идентификатор ролика на YouTube — латинские
        # названия организаций и произведений морфология тоже не знает, — а
        # также склеивает через точку и перевод строки: «Гейтс.\n\nГейтс»,
        # «WBC).\n\nКличко». Точность на NEREL этого НЕ ПОКАЗАЛА: она
        # засчитывает пересечение с любой эталонной сущностью, а организации в
        # NEREL размечены. Тот же слепой прибор, что утром пропустил
        # «Лос-Анджелесе».
        if not (_CYRILLIC_WORD_RE.fullmatch(head)
                and _CYRILLIC_WORD_RE.fullmatch(tail)):
            continue
        if text[first.end():second.start()] != " ":
            continue
        if head in names.dict_first or head in names.dict_surnames:
            continue
        if not (_not_ordinary(head) and _not_ordinary(tail)):
            continue
        # A MISSPELT ORDINARY WORD IS NOT A FOREIGN NAME, AND A PATRONYMIC IS
        # NOT HALF OF ONE. «миллера валерия леонидовича родилсяя двадцать
        # первого сентября»: «родилсяя» is unknown to morphology, «леонидовича»
        # is in no first-name or surname list, and the cue the pair needed was
        # the misspelt verb ITSELF — so the patient's name grew a fourth word
        # and the agent asked which of them was the surname (live v4 04.09,
        # derive-020). The cue is looked for OUTSIDE the pair.
        if _typo_of_an_ordinary_word(head) or _typo_of_an_ordinary_word(tail):
            continue
        if any("Patr" in parse.tag.grammemes for word in (head, tail) for parse in MORPH.parse(word)):
            continue
        before = low[max(0, first.start() - _BIO_WINDOW):first.start()]
        after = low[second.end():second.end() + _BIO_WINDOW]
        if not any(cue in before or cue in after for cue in names.bio_cues):
            continue
        spans.append(Span(first.start(), second.end(), "NAME",
                          text[first.start():second.end()]))
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
    spans: list[Span] = _lowercase_name_pairs(text, names)
    spans += _cued_misspelt_names(text, names)
    spans += _possessive_names(text, names)
    spans += _biographic_pairs(text, names)
    for match in _WORD_RE.finditer(text):
        word = match.group()
        low = word.lower()
        lemmas = _lemmas(low)
        before = text[max(0, match.start() - 20):match.start()].lower()
        if not _whole_token_ok(text, match.start(), match.end()):
            continue
        if _name_set_hit(word, low, lemmas, before, names):
            spans.append(Span(match.start(), match.end(), "NAME", word))
        elif (word[:1].isupper() or _lowercase_dictionary_ok(word, low)) and (
            # СТОРОЖ ОТНОСИТСЯ ТОЛЬКО К СТРОЧНОЙ СЛОВАРНОЙ ВЕТКЕ, ради которой
            # и заведён. Стоя выше, он отключал и семенной список, и ветку с
            # заглавной — то есть отбирал покрытие, которого послабление
            # никогда не давало: «счёт на Гагарина», «перезвоните на морозова»,
            # «передайте по ивановой» переставали маскироваться, хотя до
            # послабления маскировались. Достаточно поставить «на» перед любой
            # фамилией из реестра ГАР, чтобы снять маску.
            #
            # И слово-подсказка на ЧЕЛОВЕКА отменяет сторожа: «перезвоните на
            # морозова», «передайте по ивановой» — то же «на» перед той же
            # фамилией из того же реестра, и различает их только то, что стоит
            # ПЕРЕД предлогом. Список подсказок уже арендован и уже читается
            # этой веткой в `before`.
            not (word[:1].islower()
                 and not any(cue in before for cue in names.cues)
                 and _street_reference(text, match.start(), match.end()))
        ) and (
            low in names.dict_first or low in names.dict_surnames
            or (_lemma_lookup_ok(low) and any(
                lemma in names.dict_first or lemma in names.dict_surnames
                for lemma in lemmas))
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
             + _glued_names(text, names) + _damaged_name_pairs(text))
    spans = _merge_adjacent(spans + _adjacent_surnames(text, spans), text)
    # AFTER the neighbour pass, because it needs the anchors that pass produces:
    # in «Фёдо ров Кирилл» the anchor is «Кирилл», and the fragments are only
    # reachable from it.
    split = _split_name_parts(text, spans, names)
    if split:
        spans = _merge_adjacent(spans + split, text)
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


def trim_document_words(value: str) -> tuple[int, str]:
    """Снять с краёв только названия документов. Узкая часть `trim_person_span`.

    Существует отдельно, потому что применяется к спанам, которые полную
    обрезку не переживают: измерено, что полная стоит 1.8 пункта полноты имён на
    MASSIVE, а эта не может стоить ничего — «ИНН» и «СНИЛС» именем не бывают.
    """
    tokens = [(match.start(), match.end(), match.group())
              for match in _NON_SPACE_RE.finditer(value)]
    if not tokens:
        return 0, value
    first, last = 0, len(tokens) - 1
    while last > first and _names_a_document(tokens[last][2]):
        last -= 1
    while last > first and _names_a_document(tokens[first][2]):
        first += 1
    start, end = tokens[first][0], tokens[last][1]
    return start, value[start:end]
