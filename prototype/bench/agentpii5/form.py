"""The form comparator: is the FORM of one string the form of another.

`form_match(type, produced, reference) -> FormVerdict` is the one new axis of
v5 (spec §1, §1.1, §8.4). v4 compared two live arms and the comparison GASILO
the form — two live models normalise the same way, so a gateway that hands the
agent «Иванову Петру» as «Иванов Пётр» and a control that never saw a
substitute both end up writing «Иванов Пётр» into the tool. The check that
sees it is inside one arm: the substitute against the source on the way IN,
the real value against the substitute AS THE AGENT WROTE IT on the way OUT.

WHY THIS FILE IMPORTS NO `pseudex`. The engine has an opinion about every
question here — `pseudex.morph_names.to_nominative`, `pseudex.agent_form`,
`pseudex.date_form.notation_of`, `pseudex.translit.table_for` — and each one
is the very judgement being measured. An instrument that asked the engine
whether the engine's output is in the right case cannot fail the engine. Only
pymorphy3 is allowed, and only for `gram_case`: a third-party morphological
dictionary is evidence, not the defendant. `bench.agentpii4.parts` is allowed
for the same reason it exists there — it is the benchmark's own reading of an
unknown string.

THE ABSTAIN LIST IS CLOSED AND IT IS NOT OURS: `contracts.FORM_ABSTAIN`
(ruling R-05). It used to be a local `ABSTAIN_LABELS` here, and a second copy
of it is a second opinion about which differences are reportable — the
observer slices `form_hIN`/`form_hOUT` by the same features, so the two halves
have to read one table. A feature that one of the two strings does not carry
cannot be evidence of a form violation, and reporting it would double-count a
difference another feature already names:

  * `NAME.gram_case` = `unknown` — a Latin rendering has no Russian case, and
    a case «difference» against a Cyrillic reference is `script` counted
    twice. The brief's own acceptance pair («Ivanov Petr», «Иванов Пётр») →
    exactly {script} says so.
  * `LOC.generic_position` = `none` — with no generic word there is no
    position; («Ленина 14», «ул. Ленина 14») → exactly {generic}.
  * `case_class` (NAME/LOC/EMAIL/PLATE) and `NAME.script` = `none` — a string
    with no letters carries neither. The extractors below RETURN `none` on
    letterless input rather than the vacuous `lower`/`cyrillic` they used to:
    «14» and «7» are not two strings agreeing that they are lower case, they
    are two strings with nothing to say, and an agreement neither supports is
    a check that cannot fail.

`LOC.city_position` deliberately does NOT abstain: dropping the city changes
both whether a city is there and where it stood, and the spec names
«city_present/city_position» as one pair describing the city–street order.

Run the test: cd prototype && source .venv/bin/activate
                && python3 -m bench.agentpii5.test_form
"""
import re

import pymorphy3

from bench.agentpii4.parts import _PATRONYMIC_TAIL
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import FORM_ABSTAIN, FormVerdict
from bench.agentpii5.form_tables import (
    CYRILLIC_SURNAME_SUFFIX,
    GENERIC_ABBREVIATIONS,
    GENERIC_STEM_CANON,
    GENERIC_STEMS,
    LATIN_SURNAME_SUFFIX,
    MARKER_WORDS,
    MONTH_GENITIVE,
    MONTH_NOMINATIVE,
    MONTH_WORDS,
    NAME_PARTICLES,
    TRANSLIT_SIGNATURES,
)

# One analyzer for the process: pymorphy3 loads a dictionary from disk and
# building one per call would make the comparator's cost quadratic in a run of
# 1 500 cases. It is read-only, so sharing it keeps the function pure.
_ANALYZER = pymorphy3.MorphAnalyzer()

# The six cases the spec names. pymorphy3 also produces `voct`, `gen2`,
# `acc2`, `loc2`; they are not labels of FEATURE_LABELS[("NAME","gram_case")],
# so a parse landing on one does not vote — a vote that cannot be printed is
# a vote that silently becomes `unknown` on one side only.
_GRAM_CASES: frozenset[str] = frozenset({"nomn", "gent", "datv", "accs", "ablt", "loct"})

# A word: letters, digits, hyphens, apostrophes, maximal. `[^\W_]` is
# «alphanumeric, any script» — `\w` would swallow the underscore, which is a
# field separator in the tool arguments we meet, not a letter.
_WORD = re.compile(r"(?:[^\W_]|['\-])+")
_DIGIT_RUN = re.compile(r"\d+")
_INITIAL = re.compile(r"^(?:[А-ЯЁA-Z]\.){1,3}$")
_INNER_HYPHEN = re.compile(r"[^\W_]-[^\W_]")
_CYRILLIC_SURNAME = re.compile(CYRILLIC_SURNAME_SUFFIX, re.IGNORECASE)
_LATIN_SURNAME = re.compile(LATIN_SURNAME_SUFFIX, re.IGNORECASE)

# The label a letterless string carries for every feature that reads letters.
# Named once so an extractor cannot invent a second spelling of «nothing to
# say»; `contracts.FORM_ABSTAIN` maps the feature to it.
NO_LETTERS: str = "none"


# --- shared readers --------------------------------------------------------------------

def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _is_cyrillic(char: str) -> bool:
    return "Ѐ" <= char <= "ӿ"


def _is_latin(char: str) -> bool:
    return "a" <= char.lower() <= "z"


def _letters(text: str) -> list[str]:
    return [char for char in text if char.isalpha()]


def _case_class_titled(words: list[str]) -> str:
    """lower / upper / title / mixed — or `none` when there is no letter to
    read a case off. For the types whose labels include `title`.

    Hyphen halves count as separate words: «Иванов-Петров» is
    capitalised on both sides in every Russian register, and reading it as one
    word would report `mixed` and make a hyphenated surname differ in two
    features where only `hyphen_particle` moved."""
    letters = [char for word in words for char in word if char.isalpha()]
    if not letters:
        # No letters, no case — and no agreement either (R-05). The feature
        # abstains through `FORM_ABSTAIN`, which is why this is `none` and not
        # the `lower` it used to be: «14» against «д. 14» agreeing on a case
        # class neither carries is a check that can never fail.
        return NO_LETTERS
    if all(char.islower() for char in letters):
        return "lower"
    if len(letters) >= 2 and all(char.isupper() for char in letters):
        return "upper"
    for word in words:
        for piece in word.split("-"):
            piece_letters = _letters(piece)
            if not piece_letters:
                continue
            if not piece_letters[0].isupper() or not all(c.islower() for c in piece_letters[1:]):
                return "mixed"
    return "title"


def _case_class_plain(text: str) -> str:
    """lower / upper / mixed — or `none` on letterless input — for EMAIL and
    PLATE, neither of which has a `title` label: neither has words to
    title-case."""
    letters = _letters(text)
    if not letters:
        return NO_LETTERS                                  # R-05, as above
    if all(char.islower() for char in letters):
        return "lower"
    if all(char.isupper() for char in letters):
        return "upper"
    return "mixed"


def _digit_runs(text: str) -> list[str]:
    return _DIGIT_RUN.findall(text)


def _run_gaps(text: str) -> list[str]:
    """The text between consecutive digit runs — where a separator lives."""
    spans = [match.span() for match in _DIGIT_RUN.finditer(text)]
    return [text[spans[i][1]:spans[i + 1][0]] for i in range(len(spans) - 1)]


# --- NAME ------------------------------------------------------------------------------

def name_case_class(text: str) -> str:
    return _case_class_titled(_words(text))


def name_gram_case(text: str) -> str:
    """pymorphy3, by vote of the Cyrillic words (spec §8.4 «по pymorphy3
    голосованием»). Initials never vote — a one-letter «П» parses as anything
    — and a tie goes to the FIRST voting word, because «Иванов Петру» is a
    half-inflected run whose head is what the register chose."""
    votes: list[str] = []
    for word in _words(text):
        for piece in word.split("-"):
            letters = _letters(piece)
            if len(letters) < 2 or not all(_is_cyrillic(char) for char in letters):
                continue
            # `tag.case` is a pymorphy3 grammeme, not a `str`, and comparing
            # one to a plain label raises rather than returning False — the
            # label the comparator prints has to be an ordinary string.
            case = _ANALYZER.parse(piece)[0].tag.case
            label = "" if case is None else str(case)
            if label in _GRAM_CASES:
                votes.append(label)
    if not votes:
        return "unknown"
    return max(set(votes), key=lambda case: (votes.count(case), -votes.index(case)))


# ONE READING of a word: the gender a parse names and the case it names, as
# plain strings. `""` is «this parse names no gender» (a plural, a word the
# analyser tags without one) and it is a WILDCARD, never a fourth gender — a
# reading that says nothing about gender must not fail to meet one that does.
Reading = tuple[str, str]


def _compatible(left: frozenset[Reading], right: frozenset[Reading]) -> frozenset[Reading]:
    """The readings two sets SHARE: same case, and a gender neither contradicts.

    This is set intersection with the wildcard honoured, and it is used twice —
    across the words of one phrase (a run of words is in one case and of one
    gender, or in none) and across the two sides of a comparison."""
    return frozenset((left_gender or right_gender, left_case)
                     for left_gender, left_case in left
                     for right_gender, right_case in right
                     if left_case == right_case
                     and not (left_gender and right_gender and left_gender != right_gender))


def _phrase_readings(text: str) -> frozenset[Reading]:
    """Every (gender, case) reading that could put THIS phrase in one case.

    Per word, the readings its parses carry; over the phrase, the COMPATIBLE
    ones, because a run of words is in one case or in none. Words that carry
    no case at all (an initial, a Latin rendering, a digit) do not narrow it —
    they are silent, not universal denials.

    The set and not the top parse, because the top parse among equally scored
    readings is arbitrary: «Громова» reads `gent`, «Титова» `accs`, «Марина»
    `nomn`, and all three carry {nomn, gent, accs}. `name_gram_case` still
    prints one label for the report's histogram; the COMPARISON is made here
    (`contracts.FORM_LEXEME_READINGS`).

    THE GENDER RIDES WITH THE CASE, and dropping it was a blind spot worth
    more than half the feature. «Иванова» carries {nomn, gent, accs} — but
    `nomn` is the reading of the FEMININE surname and {gent, accs} of the
    MASCULINE one, two different words that happen to be spelled alike. So a
    bare set of cases said that «Иванова» and «Пахомовой» could both be
    genitive and scored them «same», and EVERY Russian female surname in
    -ова/-ева/-ина is built that way: measured on the corpus, a gateway that
    answered the nominative while the agent wrote the dative went uncaught on
    271 of 271 female surname leaves and on 103 of 400 male ones — 374 of 671,
    the very defect the feature exists for (`docs/known-issues.md` Б24). Paired
    with the gender the readings no longer meet, and the residue is 65."""
    out: frozenset[Reading] | None = None
    for word in _words(text):
        for piece in word.split("-"):
            letters = _letters(piece)
            if len(letters) < 2 or not all(_is_cyrillic(char) for char in letters):
                continue
            readings = _word_readings(piece)
            if readings is None:
                continue
            out = readings if out is None else _compatible(out, readings)
    return frozenset() if out is None else out


def _word_readings(piece: str) -> frozenset[Reading] | None:
    """The (gender, case) readings ONE word can wear, or None when it cannot
    say.

    The parses the analyser tags as a personal name (`Surn` / `Name` / `Patr`)
    are preferred over the rest: «Иванову» is the dative of a surname and the
    dative of a place name at once, and a reading of the place is a reading of
    another word.

    A word the table reads as SURNAME-SHAPED and the analyser knows under no
    name tag is SILENT, and that is the whole reason this helper exists.
    pymorphy3 has no surname «Седых», «Долгих», «Мещеряков»: it parses them as
    the genitive plural of «седой», «долгий», «мещеряк» — oblique-only sets
    with no nominative in them — so a perfect restoration of a nominative
    surname against a nominative minted one scored a case DIFFERENCE. The
    analyser is evidence about the word it recognised, and here it recognised
    a different word.

    A WORD THE ANALYSER DOES NOT KNOW IS SILENT FOR THE SAME REASON, and this
    is the complete statement of the rule above rather than a second one.
    pymorphy3 answers about an unknown string by GUESSING from its ending, out
    of a table that does not contain the word: it reads «удфгей» as
    {gent, accs} and «сергей» as {nomn}, so two strings wearing the same form
    were scored a case difference by a prediction neither supports. A parse
    with `is_known` false is that prediction; a dictionary parse is a reading.
    Nothing a live run produces is affected where it matters — a substitute is
    minted from a pool of real names and a real value is a real name, both
    known — and the defect the feature exists for («Иванову Петру» against
    «Иванов Пётр», known both, {datv, accs} against {nomn}) is untouched."""
    parses = [parse for parse in _ANALYZER.parse(piece) if parse.is_known]
    named = [parse for parse in parses
             if any(tag in parse.tag for tag in ("Surn", "Name", "Patr"))]
    chosen = named or parses
    readings = frozenset(("" if parse.tag.gender is None else str(parse.tag.gender),
                          str(parse.tag.case)) for parse in chosen
                         if parse.tag.case is not None and str(parse.tag.case) in _GRAM_CASES)
    if not readings:
        return None
    if not named and _surname_shaped(piece):
        return None
    return readings


def name_gram_case_same(produced: str, reference: str) -> bool:
    """Could the two strings be in ONE grammatical case.

    Two DIFFERENT lexemes, so the labels are not comparable (the reason is
    written out in `contracts.FORM_LEXEME_READINGS`). A side that reads no
    case at all abstains — a Latin rendering and a bare initial have no
    Russian case, which is the same judgement `FORM_ABSTAIN`'s `unknown`
    makes. Readings that cannot meet are a real difference: «Иванов Пётр»
    {(masc, nomn)} against «Иванову Петру» {(masc, datv)} is the
    nominative-for-the-tool defect (`docs/known-issues.md` Б24) and stays a
    miss, and so now is «Иванова» against «Пахомовой», which the case sets
    alone called «same» (see `_phrase_readings`).

    A GENDER THE TWO SIDES DO NOT SHARE IS NO EVIDENCE, and the last clause
    says what to do then instead of letting the pairing decide. A gateway may
    mint a feminine substitute for a masculine name, and then no reading can
    meet whatever the cases are — «Ивану» (masc datv) against «Елене» (femn
    datv) would read as a case difference no gateway could remove. Where the
    two sides share NO gender the cases are the only evidence there is and are
    compared alone; «Иванов Пётр» {nomn} against «Пахомову Ольгу» {accs} is
    still the Б24 defect and still fires.

    THE ONE PRICE, MEASURED AND STATED. When the sides DO share a gender the
    comparison is made inside it, and a phrase can share one by an accident of
    the dictionary: «Иванова Петра» is masculine accusative, but pymorphy3 also
    reads «Петра» as the feminine given name, so the pair shares `femn` with
    «Пахомову Ольгу» and the two disagree under it — a cross-gender
    restoration that kept the case reads as a difference. It costs nothing
    measurable — a perfect gateway over all 1736 cases prints the same
    form_hOUT 15753/15753 and the same form_hIN 11062/11730 with the rule and
    without it, because the probe mints within gender, as the engine's own
    `docs/tz-name-gender-canonical.md` says it does — and buying the 374
    female-surname misses back is worth a residue that appears only where the
    gateway has ALREADY changed the person's gender."""
    left, right = _phrase_readings(produced), _phrase_readings(reference)
    if not left or not right:
        return True
    if _compatible(left, right):
        return True
    if ({gender for gender, _case in left if gender}
            & {gender for gender, _case in right if gender}):
        return False
    return bool({case for _gender, case in left} & {case for _gender, case in right})


def _surname_shaped(core: str) -> bool:
    letters = _letters(core)
    if not letters:
        return False
    if all(_is_latin(char) for char in letters):
        return _LATIN_SURNAME.search(core) is not None
    return _CYRILLIC_SURNAME.search(core) is not None


def _part_role(part: str) -> str:
    core = "".join(char for char in part if char.isalpha() or char == "-")
    if not core:
        return "G"
    if _PATRONYMIC_TAIL.search(core):
        return "P"
    if _surname_shaped(core):
        return "S"
    return "G"


def name_order(text: str) -> str:
    parts = text.split()
    if len(parts) == 1:
        return "single"
    roles = [_part_role(part) for part in parts]
    if roles in (["S", "G", "P"], ["S", "G"]):
        return "F-I-O"
    if roles == ["G", "S"]:
        return "I-F"
    if roles == ["G", "P", "S"]:
        return "I-O-F"
    return "other"


def name_parts(text: str) -> str:
    count = len(text.split())
    return str(count) if count <= 3 else "4+"


def name_initials(text: str) -> str:
    count = 0
    for token in text.split():
        if _INITIAL.match(token):
            count += token.count(".")
    if count == 0:
        return "none"
    return "given" if count == 1 else "given_patronymic"


def _part_count(text: str) -> int:
    return len(text.split())


# THE SECOND ABSTENTION, AND IT IS A REGISTRY BECAUSE IT WAS PROSE.
# `contracts.FORM_ABSTAIN` is the normative list of «this LABEL says nothing»
# (R-05); a feature that also refuses to answer when the two strings hold a
# different NUMBER of parts was stated only in two docstrings, so «how many
# abstention rules are there» had two answers depending on which file you
# read, and no test could reach the rule apart from the pair table. Named
# here, read by both comparators, and pinned by
# `test_form.test_the_part_count_abstention_is_declared`.
#
# WHY IT EXISTS: «Иванов Пётр» against «Пахомова» differ in a way `parts`
# already names once, and «П.О.» is one part against «Иванова Елена»'s two —
# reporting `order` or `initials` as well would make one violation two or
# three features wide and triple its weight in the report's histogram.
FORM_PART_COUNT_ABSTAIN: frozenset[tuple[str, str]] = frozenset({
    ("NAME", "order"),
    ("NAME", "initials"),
})


def _part_counts_differ(feature: str, produced: str, reference: str) -> bool:
    """Does `("NAME", feature)` abstain on THIS pair for want of a common part
    count? Raises on a feature that is not in the registry rather than
    answering False, so a comparator cannot quietly claim an abstention the
    list does not grant it."""
    if ("NAME", feature) not in FORM_PART_COUNT_ABSTAIN:
        raise ValueError(f"NAME.{feature} asked for the part-count abstention without being "
                         f"in FORM_PART_COUNT_ABSTAIN, which holds "
                         f"{sorted(FORM_PART_COUNT_ABSTAIN)}")
    return _part_count(produced) != _part_count(reference)


def name_order_same(produced: str, reference: str) -> bool:
    """Did the two strings put the surname in the same place.

    Abstains on `other` (through the label in `contracts.FORM_ABSTAIN`) and on
    a pair whose part COUNTS differ (`FORM_PART_COUNT_ABSTAIN`)."""
    if _part_counts_differ("order", produced, reference):
        return True
    left, right = name_order(produced), name_order(reference)
    abstain = FORM_ABSTAIN[("NAME", "order")]
    return left == right or abstain in (left, right)


def name_initials_same(produced: str, reference: str) -> bool:
    """Were initials squeezed the same way. Not comparable across part counts
    (`FORM_PART_COUNT_ABSTAIN`): «П.О.» is one part and «Иванова Елена» two,
    and `parts` says so once."""
    if _part_counts_differ("initials", produced, reference):
        return True
    return name_initials(produced) == name_initials(reference)


def name_script(text: str) -> str:
    letters = _letters(text)
    if not letters:
        # A letterless NAME field («+7…» misrouted, an empty slot) is in no
        # script at all. It used to answer `cyrillic`, which made it AGREE
        # with every Russian name it was compared against (R-05).
        return NO_LETTERS
    cyrillic = any(_is_cyrillic(char) for char in letters)
    latin = any(_is_latin(char) for char in letters)
    if cyrillic and latin:
        return "mixed"
    if cyrillic:
        return "cyrillic"
    lowered = text.lower()
    words = [word.lower() for word in _words(text)]
    for label, alternatives in TRANSLIT_SIGNATURES:
        for alternative in alternatives:
            if all(_signature_holds(kind, needle, lowered, words) for kind, needle in alternative):
                return label
    return "latin:unknown"


def _signature_holds(kind: str, needle: str, lowered: str, words: list[str]) -> bool:
    if kind == "sub":
        return needle in lowered
    if kind == "fin":
        return any(word.endswith(needle) for word in words)
    raise ValueError(f"unknown transliteration signature condition {kind!r} for {needle!r}")


def name_hyphen_particle(text: str) -> str:
    hyphen = _INNER_HYPHEN.search(text) is not None
    particle = any("".join(c for c in token if c.isalpha()).lower() in NAME_PARTICLES
                   for token in text.split())
    if hyphen and particle:
        return "both"
    if hyphen:
        return "hyphen"
    if particle:
        return "particle"
    return "none"


# --- PHONE -----------------------------------------------------------------------------

# The three prefixes that carry a country code, and therefore the ones whose
# leading digit `grouping` must not count as part of the subscriber number.
_COUNTRY_PREFIXES: frozenset[str] = frozenset({"plus7", "eight", "seven"})


def phone_prefix(text: str) -> str:
    digits = "".join(_digit_runs(text))
    if text.lstrip().startswith("+7"):
        return "plus7"
    if len(digits) == 11 and digits.startswith("8"):
        return "eight"
    if len(digits) == 11 and digits.startswith("7"):
        return "seven"
    if len(digits) == 10:
        return "bare"
    # `other` (ruling R-07), NOT a fall-through into `bare`: a fragment
    # («123»), a foreign number or a field that holds no phone at all is not
    # «a Russian number written without its country code», and labelling it so
    # made the two agree wherever both were malformed in different ways.
    return "other"


def phone_grouping(text: str) -> str:
    dropped = 1 if phone_prefix(text) in _COUNTRY_PREFIXES else 0
    sizes: list[int] = []
    for run in _digit_runs(text):
        if dropped >= len(run):
            dropped -= len(run)
            continue
        sizes.append(len(run) - dropped)
        dropped = 0
    if sizes == [3, 3, 2, 2]:
        return "3-3-2-2"
    if sizes == [3, 3, 4]:
        return "3-3-4"
    if sizes == [10]:
        return "solid"
    return "other"


def _separator_set(text: str) -> set[str]:
    """The separator characters between digit runs. `(`, `)` and `+` are
    excluded by the spec: they are the `parens` and `prefix` features, and
    counting them here would make one difference fire twice."""
    found: set[str] = set()
    for gap in _run_gaps(text):
        for char in gap:
            if char in "()+":
                continue
            found.add(" " if char.isspace() else char)
    return found


def phone_separators(text: str) -> str:
    found = _separator_set(text)
    if not found:
        return "none"
    if found == {" "}:
        return "space"
    if found == {"-"}:
        return "hyphen"
    if found == {"."}:
        return "dot"
    return "mixed"


def phone_parens(text: str) -> str:
    return "yes" if "(" in text else "no"


# --- LOC -------------------------------------------------------------------------------

_HOUSE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # «дом» first: `д` is its prefix, and a first-match loop over an
    # unordered table would read «дом 14» as a dotless `д`.
    ("dom", re.compile(r"(?<![А-Яа-яЁё])дом\s*\d")),
    ("d_dot_space", re.compile(r"(?<![А-Яа-яЁё])д\.\s+\d")),
    ("d_dot_nospace", re.compile(r"(?<![А-Яа-яЁё])д\.\d")),
    ("d_nodot", re.compile(r"(?<![А-Яа-яЁё])д\s+\d")),
    ("other", re.compile(r"(?<![А-Яа-яЁё])(?:влд|владение|уч|участок|№)\.?\s*\d")),
)
_FLAT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("kvartira", re.compile(r"(?<![А-Яа-яЁё])квартира\s*\d")),
    ("kv_dot_space", re.compile(r"(?<![А-Яа-яЁё])кв\.\s+\d")),
    ("kv_dot_nospace", re.compile(r"(?<![А-Яа-яЁё])кв\.\d")),
    ("kv_nodot", re.compile(r"(?<![А-Яа-яЁё])кв\s+\d")),
    ("other", re.compile(r"(?<![А-Яа-яЁё])(?:оф|офис|пом|помещение|апарт)\.?\s*\d")),
)
_BUILDING_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("korp", re.compile(r"(?<![А-Яа-яЁё])(?:корпус|корп|к)\.?\s*\d")),
    ("str", re.compile(r"(?<![А-Яа-яЁё])(?:строение|стр)\.?\s*\d")),
    ("podezd", re.compile(r"(?<![А-Яа-яЁё])(?:подъезд|под|п)\.?\s*\d")),
    ("etazh", re.compile(r"(?<![А-Яа-яЁё])(?:этаж|эт)\.?\s*\d")),
    ("lit", re.compile(r"(?<![А-Яа-яЁё])(?:литера|лит)\.?\s*[А-ЯЁ\d]")),
)
# «д.» before a WORD is a village, before DIGITS it is a house — the same two
# letters, and the spec separates them by what follows.
_SETTLEMENT = re.compile(r"(?<![А-Яа-яЁё])(?:город|г\.|г(?![А-Яа-яЁё])|с\.|село|пос\.|пгт|"
                         r"дер\.|деревня|д\.)\s*(?=[А-Яа-яЁёA-Za-z])")
_ABBREVIATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (abbreviation,
     re.compile(r"(?<![А-Яа-яЁёA-Za-z])" + re.escape(abbreviation)
                + ("" if abbreviation.endswith(".") else r"(?![А-Яа-яЁёA-Za-z.\-])")))
    for abbreviation in GENERIC_ABBREVIATIONS)
_ABBREVIATION_CORES: frozenset[str] = frozenset(
    abbreviation.rstrip(".") for abbreviation in GENERIC_ABBREVIATIONS)


def _segments(text: str) -> list[str]:
    """FIELD_SEP is the STRONGEST separator: a value that arrived as separate
    tool fields was never one string, and treating its sentinel as a comma
    would let `city_present` read a field boundary as a written comma."""
    if contracts.FIELD_SEP in text:
        return [part.strip() for part in text.split(contracts.FIELD_SEP)]
    return [part.strip() for part in text.split(",")]


def _generic_stem(word: str) -> str:
    lowered = word.lower()
    for stem in GENERIC_STEMS:
        if lowered.startswith(stem):
            return GENERIC_STEM_CANON.get(stem, stem)
    return ""


def _is_marker_word(word: str) -> bool:
    lowered = word.lower()
    return bool(_generic_stem(word)) or lowered in MARKER_WORDS or lowered in _ABBREVIATION_CORES


def loc_case_class(text: str) -> str:
    return _case_class_titled([word for word in _words(text) if not _is_marker_word(word)])


def loc_generic(text: str) -> str:
    for word in _words(text):
        stem = _generic_stem(word)
        if stem:
            return f"full:{stem}"
    for abbreviation, pattern in _ABBREVIATION_PATTERNS:
        if pattern.search(text):
            return f"abbr:{abbreviation}"
    return "none"


def _street_word_index(words: list[str]) -> int:
    for index, word in enumerate(words):
        if not _letters(word) or _is_marker_word(word):
            continue
        return index
    return -1


def loc_generic_position(text: str) -> str:
    if loc_generic(text) == "none":
        return "none"
    for segment in _segments(text):
        words = _words(segment)
        generic_index = next((index for index, word in enumerate(words)
                              if _generic_stem(word) or word.lower() in _ABBREVIATION_CORES), -1)
        if generic_index < 0:
            continue
        street_index = _street_word_index(words)
        if street_index < 0:
            return "none"
        return "before" if generic_index < street_index else "after"
    return "none"


def _first_pattern(text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> str:
    for label, pattern in patterns:
        if pattern.search(text):
            return label
    return "none"


def loc_house_marker(text: str) -> str:
    return _first_pattern(text, _HOUSE_PATTERNS)


def loc_flat_marker(text: str) -> str:
    return _first_pattern(text, _FLAT_PATTERNS)


def loc_commas(text: str) -> str:
    return "yes" if "," in text else "no"


def _city(text: str) -> tuple[str, str]:
    """(city_present, city_position) in one reading: the position is the
    position OF the segment the presence test found, and computing them apart
    would let the two disagree about which segment they mean.

    A bare word segment counts as a city only when the REST of the address
    still names a street. «Ленина<FIELD_SEP>14» is a street and a house split
    into fields, not «city Ленина»; without that rule every field-shaped
    address would grow a city the customer never wrote."""
    segments = _segments(text)
    marker = _SETTLEMENT.search(text)
    if marker is not None:
        if marker.start() == 0:
            return "yes", "first"
        marker_segment = _segment_of(text, segments, marker.start())
        if marker_segment == 0:
            return "yes", "first"
        if marker_segment == len(segments) - 1:
            return "yes", "last"
        return "yes", "middle"
    for index, position in ((0, "first"), (len(segments) - 1, "last")):
        if index < 0 or index >= len(segments):
            continue
        if not _is_bare_place(segments[index]):
            continue
        others = [segment for other, segment in enumerate(segments) if other != index]
        if any(_letters(word) and not _is_marker_word(word)
               for segment in others for word in _words(segment)):
            return "yes", position
    return "no", "none"


def _segment_of(text: str, segments: list[str], offset: int) -> int:
    separator = contracts.FIELD_SEP if contracts.FIELD_SEP in text else ","
    return text[:offset].count(separator) if len(segments) > 1 else 0


def _is_bare_place(segment: str) -> bool:
    words = _words(segment)
    if not 1 <= len(words) <= 2:
        return False
    return all(_letters(word) and not _is_marker_word(word) for word in words)


def loc_city_present(text: str) -> str:
    return _city(text)[0]


def loc_city_position(text: str) -> str:
    return _city(text)[1]


def loc_by_fields(text: str) -> str:
    return "fields" if contracts.FIELD_SEP in text else "string"


def loc_building_entrance_markers(text: str) -> str:
    found = sorted(label for label, pattern in _BUILDING_PATTERNS if pattern.search(text))
    return f"markers:{'+'.join(found)}" if found else "none"


# --- DOB / DATE ------------------------------------------------------------------------

_NOTATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dmy_dots", re.compile(r"\d{1,2}\.\d{1,2}\.\d{2,4}")),
    ("dmy_slashes", re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")),
    ("iso", re.compile(r"\d{4}-\d{2}-\d{2}")),
    ("solid", re.compile(r"(?<!\d)\d{8}(?!\d)")),
)
# Digit runs and month words, in the order written. `bench.agentpii4.parts`
# has `_DATE_RU`, and it is NOT reused: it pins a four-digit year, and telling
# «87» from «1987» is exactly the `year_len` feature.
_DATE_GROUP = re.compile(r"\d+|[^\W\d_]+")


def _date_groups(text: str) -> list[tuple[int, int, str]]:
    groups: list[tuple[int, int, str]] = []
    for match in _DATE_GROUP.finditer(text):
        token = match.group()
        if token.isdigit() or token.lower() in MONTH_WORDS:
            groups.append((match.start(), match.end(), token))
    return groups


def _month_word(text: str) -> str:
    for _, _, token in _date_groups(text):
        if not token.isdigit():
            return token.lower()
    return ""


def date_notation(text: str) -> str:
    for label, pattern in _NOTATION_PATTERNS:
        if pattern.search(text):
            return label
    if _month_word(text):
        return "words"
    return "other"


def date_separator(text: str) -> str:
    groups = _date_groups(text)
    if len(groups) < 2:
        return "none"
    between = text[groups[0][1]:groups[1][0]]
    if "." in between:
        return "dot"
    if "/" in between:
        return "slash"
    if "-" in between:
        return "hyphen"
    if between.strip() == "" and between != "":
        return "space"
    return "none"


def date_padding(text: str) -> str:
    groups = [token for _, _, token in _date_groups(text)]
    if not groups:
        return "unpadded"
    notation = date_notation(text)
    if notation == "solid":
        return "padded"
    if notation == "iso":
        numbered = groups[1:3]
    elif notation == "words":
        numbered = groups[:1]
    else:
        numbered = groups[:2]
    numbered = [token for token in numbered if token.isdigit()]
    if not numbered:
        return "unpadded"
    return "padded" if all(len(token) == 2 for token in numbered) else "unpadded"


def date_year_len(text: str) -> str:
    notation = date_notation(text)
    if notation == "solid":
        return "4"
    groups = [token for _, _, token in _date_groups(text)]
    if notation == "iso":
        year = groups[0] if groups else ""
    elif len(groups) >= 3 and groups[2].isdigit():
        year = groups[2]
    else:
        year = ""
    if len(year) == 4:
        return "4"
    if len(year) == 2:
        return "2"
    return "none"


def date_month_form(text: str) -> str:
    word = _month_word(text)
    if not word:
        return "number"
    if word in MONTH_NOMINATIVE:
        return "word_nominative"
    if word in MONTH_GENITIVE:
        return "word_genitive"
    # A form outside the two the spec names («в марте») still has to land on
    # a label; the -а/-я ending is what genitive shares with it.
    return "word_genitive" if word.endswith(("а", "я")) else "word_nominative"


# --- EMAIL, CARD, SNILS, INN, PASSPORT, PLATE -------------------------------------------

def email_case_class(text: str) -> str:
    return _case_class_plain(text)


def card_grouping(text: str) -> str:
    sizes = [len(run) for run in _digit_runs(text)]
    if sizes == [4, 4, 4, 4]:
        return "4x4"
    if sizes == [16]:
        return "solid"
    return "other"


def card_separator(text: str) -> str:
    gaps = [gap for gap in _run_gaps(text) if gap]
    if not gaps:
        return "none"
    first = gaps[0][0]
    if first.isspace():
        return "space"
    if first == "-":
        return "hyphen"
    # `other` (ruling R-07): a card written with dots or slashes is separated,
    # and answering `none` made it agree with the solid form — the one shape
    # this feature exists to tell it apart from.
    return "other"


_SNILS_CANONICAL = re.compile(r"^\D*\d{3}-\d{3}-\d{3}\s\d{2}\D*$")
_SNILS_SOLID = re.compile(r"^\D*\d{11}\D*$")


def snils_separators(text: str) -> str:
    if _SNILS_CANONICAL.match(text):
        return "canonical"
    if _SNILS_SOLID.match(text):
        return "solid"
    return "other"


def inn_length(text: str) -> str:
    count = len("".join(_digit_runs(text)))
    return str(count) if count in (10, 12) else "other"


def inn_separators(text: str) -> str:
    found = _separator_set(text)
    if not found:
        return "none"
    if found == {" "}:
        return "space"
    return "other"


def passport_series_number_split(text: str) -> str:
    sizes = [len(run) for run in _digit_runs(text)]
    if sizes == [2, 2, 6]:
        return "2-2-6"
    if sizes == [4, 6]:
        return "4-6"
    if sizes == [10]:
        return "solid"
    return "other"


def plate_case_class(text: str) -> str:
    return _case_class_plain(text)


def plate_spaces(text: str) -> str:
    return "yes" if any(char.isspace() for char in text) else "no"


_PLATE_REGION = re.compile(r"(.?)(\d{2,3})\s*$")


def plate_region_sep(text: str) -> str:
    match = _PLATE_REGION.search(text.rstrip())
    if match is None:
        return "none"
    before = match.group(1)
    if before == "" or before.isalnum():
        return "none"
    return "space" if before.isspace() else "other"


# --- the registry ----------------------------------------------------------------------

_DATE_EXTRACTORS: dict[str, contracts.FeatureExtractor] = {
    "notation": date_notation,
    "separator": date_separator,
    "padding": date_padding,
    "year_len": date_year_len,
    "month_form": date_month_form,
}

FEATURE_EXTRACTORS: dict[tuple[str, str], contracts.FeatureExtractor] = {
    ("NAME", "case_class"): name_case_class,
    ("NAME", "gram_case"): name_gram_case,
    ("NAME", "order"): name_order,
    ("NAME", "parts"): name_parts,
    ("NAME", "initials"): name_initials,
    ("NAME", "script"): name_script,
    ("NAME", "hyphen_particle"): name_hyphen_particle,
    ("PHONE", "prefix"): phone_prefix,
    ("PHONE", "grouping"): phone_grouping,
    ("PHONE", "separators"): phone_separators,
    ("PHONE", "parens"): phone_parens,
    ("LOC", "case_class"): loc_case_class,
    ("LOC", "generic"): loc_generic,
    ("LOC", "generic_position"): loc_generic_position,
    ("LOC", "house_marker"): loc_house_marker,
    ("LOC", "flat_marker"): loc_flat_marker,
    ("LOC", "commas"): loc_commas,
    ("LOC", "city_present"): loc_city_present,
    ("LOC", "city_position"): loc_city_position,
    ("LOC", "by_fields"): loc_by_fields,
    ("LOC", "building_entrance_markers"): loc_building_entrance_markers,
    **{("DOB", feature): extractor for feature, extractor in _DATE_EXTRACTORS.items()},
    **{("DATE", feature): extractor for feature, extractor in _DATE_EXTRACTORS.items()},
    ("EMAIL", "case_class"): email_case_class,
    ("CARD", "grouping"): card_grouping,
    ("CARD", "separator"): card_separator,
    ("SNILS", "separators"): snils_separators,
    ("INN", "length"): inn_length,
    ("INN", "separators"): inn_separators,
    ("PASSPORT", "series_number_split"): passport_series_number_split,
    ("PLATE", "case_class"): plate_case_class,
    ("PLATE", "spaces"): plate_spaces,
    ("PLATE", "region_sep"): plate_region_sep,
}


# The lexeme-dependent features, one comparator each. The keys are EXACTLY
# `contracts.FORM_LEXEME_READINGS`'s — `test_form.test_comparators_match_the_
# declared_readings` pins the two sets equal, so a comparator without a written
# reason, or a reason without a comparator, is red.
FEATURE_COMPARATORS: dict[tuple[str, str], contracts.FeatureComparator] = {
    ("NAME", "gram_case"): name_gram_case_same,
    ("NAME", "order"): name_order_same,
    ("NAME", "initials"): name_initials_same,
}


def features_of(type: str, text: str) -> dict[str, str]:
    """Every feature of `type`, labelled — what the report's histogram
    (C-181) counts and what a failing hop is explained with."""
    features = contracts.FORM_FEATURES.get(type)
    if features is None:
        raise ValueError(f"features_of: no form features declared for type {type!r}; "
                         f"declared types are {sorted(contracts.FORM_FEATURES)}")
    return {feature: FEATURE_EXTRACTORS[(type, feature)](text) for feature in features}


def form_match(type: str, produced: str, reference: str) -> FormVerdict:
    """The verdict: which features of `type` the two strings disagree on.

    IN hop — produced = the substitute the model read, reference = the
    source's surface. OUT hop — produced = the real value the consumer
    received, reference = the substitute exactly as the agent wrote it."""
    features = contracts.FORM_FEATURES.get(type)
    if features is None:
        raise ValueError(f"form_match: no form features declared for type {type!r}; "
                         f"declared types are {sorted(contracts.FORM_FEATURES)}")
    # NOTHING IS NOT A FORM, and this is the comparator's half of `observe.py`'s
    # fourth rule. A side with no characters carries no feature, so every
    # extractor that reads letters answers `none` and abstains, every extractor
    # that reads digit runs finds none and answers its own «nothing» label — and
    # the two sides «agreed». `form_match("EMAIL", "", "ivan@mail.ru")`,
    # `("PLATE", "", "А123ВС77")` and `("LOC", "", "Ленина 14")` all returned
    # `same`, so a gateway that answered the customer's tool with an EMPTY leaf
    # printed 100% on `form_hOUT` for those types. Measured on the `medium`
    # tier against a gateway that blanks every restored leaf: 400 of its 1 484
    # OUT tool leaves scored «same» on a value that never arrived, and the line
    # read 1727/2811 instead of 1327/2811. The value lines (`end_to_end`,
    # `round_trip`) caught it, the form line by type did not, and a line that
    # cannot fail on nothing at all is not a line.
    #
    # EVERY feature differs rather than the ones the other side happens to read:
    # the claim is not «the case is wrong», it is «no form arrived», and naming
    # a subset would invite a reader to think the rest survived.
    if not produced.strip() or not reference.strip():
        return FormVerdict(same=False, differs=frozenset(features))
    differs: set[str] = set()
    for feature in features:
        # A LEXEME-DEPENDENT feature is decided by its comparator and by
        # nothing else. Falling back to the labels when the comparator says
        # «same» would restore the floor the comparator exists to remove, and
        # falling back the other way would report a difference the comparator
        # has already ruled unreadable.
        comparator = FEATURE_COMPARATORS.get((type, feature))
        if comparator is not None:
            if not comparator(produced, reference):
                differs.add(feature)
            continue
        extractor = FEATURE_EXTRACTORS[(type, feature)]
        left = extractor(produced)
        right = extractor(reference)
        if left == right:
            continue
        abstain = FORM_ABSTAIN.get((type, feature))
        if abstain is not None and abstain in (left, right):
            continue
        differs.add(feature)
    return FormVerdict(same=not differs, differs=frozenset(differs))
