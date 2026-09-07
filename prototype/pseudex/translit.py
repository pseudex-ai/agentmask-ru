"""Transliteration and initials of a name — the DERIVED forms a model writes.

A model asked for a cardholder or a `name_latin` field transliterates the
substitute it read, and asked for initials it abbreviates it; neither string
is the token, so neither resolved, and the customer's tool or the customer's
reply received «TSVETKOV VSEVOLOD» and «Ж.М.» derived from a person who does
not exist (59 of 355 replies on the v4 small run). The vault indexes these
forms at mint time and the restore leg answers with the SAME derivation of the
real value.

THE MODEL DOES NOT PICK A STANDARD, IT PICKS LETTERS. The first design held
four tables (ICAO Doc 9303, ГОСТ 7.79-2000 B, МВД 2010, the everyday spelling
banks print) and asked which one reproduced the model's word. Measured on
1 812 Latin words the CONTROL arm wrote for real names across three live runs:
no table reproduces «Meshcheryakova» (щ as ICAO's «shch», я as the everyday
«ya»), and «Dmitry», «Yulia», «Maxim» — 96 words — follow endings no standard
lists. Two consequences, both reachable on every run:

  * the substitute's Latin form was indexed under four spellings, so a fifth
    reached the tool unresolved — «Meshcheryakova Anna», half a real person;
  * when several tables explained the model's word equally, the FIRST won,
    and ICAO's «iu» / ГОСТ's «x» were then written into the real name —
    «BITIUKOVA» and «EROXIN» against the control's «BITYUKOVA» and «EROKHIN».
    38 triples on the 05.09 medium run, the largest unexplained class, and 33
    of them with both controls agreeing: the disagreement was ours.

So the unit is the LETTER (or the ending), and three functions replace the
tables: `align` reads which rendering the model used for each unit of the
substitute, `render` writes the real name with those same choices and fills
the units the substitute did not contain from `DEFAULT`, and `fold` is one
canonical spelling under which every rendering of a word collides, so the
vault indexes one row and finds the model's word whatever it chose. `DEFAULT`
is not a standard either: it is what the control arm wrote most often, letter
by letter (й→y 112:24, ю→yu 87:0, я→ya 37:26, х→kh 93:0, ц→ts 104:0, ё→e
72:24), which is the only convention the restored value has to match.

`bench/agentpii4/derive.py` holds its own tables on purpose — the instrument
must not agree with the engine by construction.
"""
from __future__ import annotations

import re

# Every rendering in daily use for one Cyrillic UNIT — a letter, or one of the
# four endings a model spells as a whole. Order within a tuple is the order
# `align` tries them; the first is what `DEFAULT` writes. A rendering is here
# because a standard lists it or the control arm wrote it, never because it
# would be convenient to match.
UNITS: dict[str, tuple[str, ...]] = {
    # The endings, with the control arm's count for the first rendering against
    # the runner-up: «-ий» iy 77 : y 51, «-ый» y 24 : yy 2, «-ия» ia 36 : 0,
    # «ья» ia 22 : ya 2, «кс» ks 25 : x 10.
    "ий": ("iy", "y", "ii", "ij", "yi"),     # Дмитрий → Dmitriy, Dmitry
    "ый": ("y", "yy", "yi", "yj", "iy"),     # Заболотный → Zabolotny
    "ия": ("ia", "iya", "iia", "ija"),        # Юлия → Yulia, Наталия → Natalia
    "ья": ("ia", "ya", "ja"),                 # Наталья → Natalia, Дарья → Daria
    "кс": ("ks", "x"),                        # Максим → Maxim
    # «ей» IS «ei», MEASURED ON THIS MODEL: Sergei 22 : Sergey 12 across the
    # control arms of the 06.09 run. Rendered letter by letter it came out
    # «Sergey» and the tool received a spelling the same model would not have
    # written — «Сергей», «Андрей», «Алексей» all take «ei» in English by
    # convention. The fold already collides the two, so this changes what we
    # WRITE, never what we can find.
    "ей": ("ei", "ey", "ej"),                 # Сергей → Sergei
    # «йя» IS ONE `ya`, NOT TWO. Rendered letter by letter it comes out «yya»
    # and nobody writes «Mayya»; the model wrote «Maya», the fold of the two
    # differed by the orphaned «y», the vault lookup missed, and «Майя» reached
    # the tool as the FAKE given name beside the real surname — a chimera, on
    # three cases of the 06.09 live run.
    "йя": ("ya", "iya", "ja"),                # Майя → Maya, Аглая → Aglaya
    "а": ("a",), "б": ("b",), "в": ("v",), "г": ("g",), "д": ("d",),
    "е": ("e", "ye", "ie", "je"), "ё": ("e", "yo", "io", "jo"),
    "ж": ("zh", "j"), "з": ("z",), "и": ("i",), "й": ("y", "i", "j"),
    "к": ("k",), "л": ("l",), "м": ("m",), "н": ("n",), "о": ("o",),
    "п": ("p",), "р": ("r",), "с": ("s",), "т": ("t",), "у": ("u",),
    "ф": ("f",), "х": ("kh", "h", "x"), "ц": ("ts", "tc", "c", "cz"),
    "ч": ("ch",), "ш": ("sh",), "щ": ("shch", "sch", "shh"),
    "ъ": ("", "ie"), "ы": ("y",), "ь": ("",), "э": ("e",),
    "ю": ("yu", "iu", "ju"), "я": ("ya", "ia", "ja"),
}
DEFAULT: dict[str, str] = {unit: options[0] for unit, options in UNITS.items()}
_ENDINGS: tuple[str, ...] = ("ий", "ый", "ия", "ья", "кс", "йя", "ей")

# The four standards, kept for the callers that name one — a test that wants
# «the ICAO spelling», the benchmark's scripted agent — and as the source the
# alternatives above were checked against.
ICAO: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "ie", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
GOST_B: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "cz", "ч": "ch", "ш": "sh", "щ": "shh",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
MVD_2010: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "tc", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
COMMON: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
TABLES: tuple[dict[str, str], ...] = (ICAO, GOST_B, MVD_2010, COMMON)


def apply(table: dict[str, str], word: str) -> str:
    """One word through one table, lowercase, letters only."""
    out = "".join(table.get(letter, letter) for letter in word.lower())
    return "".join(ch for ch in out if ch.isalpha())


def is_cyrillic_word(word: str) -> bool:
    return bool(word) and any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in word)


def units_of(word: str) -> tuple[str, ...]:
    """A Cyrillic word cut into the units `UNITS` knows, endings first.

    Greedy and longest-first: «Юрий» is (ю, р, ий), «Максим» (м, а, кс, и, м),
    «Наталья» (н, а, т, а, л, ья). The endings are tried at every position
    because «Ксения» carries «кс» at the front and «Ильясов» carries «ья» in
    the middle, where the model spells them the same way."""
    low = word.lower()
    out: list[str] = []
    i = 0
    while i < len(low):
        for ending in _ENDINGS:
            if low.startswith(ending, i):
                out.append(ending)
                i += len(ending)
                break
        else:
            out.append(low[i])
            i += 1
    return tuple(out)


def align(cyrillic: str, latin: str) -> dict[str, str] | None:
    """Which rendering the model used for each unit of `cyrillic` to write
    `latin`, or None when no choice of renderings spells it.

    Depth-first over the units, longest rendering first at every step, so the
    answer is deterministic; on 1 812 aligned control-arm words the alignment
    was unique every time. A unit that is not a letter of the language is
    matched literally, so a hyphen or a digit in either string must be in
    both."""
    wanted = "".join(ch for ch in latin.lower() if ch.isalpha())
    units = units_of(cyrillic)
    if not units or not wanted:
        return None
    seen: set[tuple[int, int]] = set()

    def go(index: int, at: int) -> dict[str, str] | None:
        if index == len(units):
            return {} if at == len(wanted) else None
        if (index, at) in seen:
            return None
        unit = units[index]
        options = UNITS.get(unit)
        if options is None:
            options = (unit,) if unit.isalpha() else ("",)
        for option in sorted(options, key=len, reverse=True):
            if wanted.startswith(option, at):
                rest = go(index + 1, at + len(option))
                if rest is not None:
                    rest[unit] = option
                    return rest
        seen.add((index, at))
        return None

    return go(0, 0)


def render(cyrillic: str, learned: dict[str, str]) -> str:
    """`cyrillic` in Latin letters, each unit as `learned` saw the model write
    it and, for a unit the model's own words never contained, as `DEFAULT`
    says. Lowercase; the caller sets the case with `match_case`."""
    out: list[str] = []
    for unit in units_of(cyrillic):
        if unit in learned:
            out.append(learned[unit])
        elif unit in DEFAULT:
            out.append(DEFAULT[unit])
        elif unit.isalpha():
            out.append(unit)
    return "".join(out)


def variants(word: str) -> frozenset[str]:
    """Every Latin spelling of one Cyrillic word under the four tables."""
    if not is_cyrillic_word(word):
        return frozenset()
    return frozenset(apply(table, word) for table in TABLES)


def table_for(cyrillic: str, latin: str) -> dict[str, str] | None:
    """The table that spells `cyrillic` as `latin`, or None."""
    wanted = "".join(ch for ch in latin.lower() if ch.isalpha())
    for table in TABLES:
        if apply(table, cyrillic) == wanted:
            return table
    return None


# ONE SPELLING UNDER WHICH EVERY RENDERING OF A WORD COLLIDES. Applied to the
# Latin side only — to the default rendering of the substitute at mint, and
# to whatever the model wrote at lookup — so the vault stores one row and the
# lookup is one indexed equality, whichever of the renderings above the model
# chose. Order matters: the three-letter «shch» must go before «sch» and «sh»,
# «ch» before the bare «c» that is left for ц, the digraph vowels before the
# single letters they contain. The markers are capitals so a folded string
# can never equal a casefolded Cyrillic or Latin part in the same table.
# «kh», «x» and «ks» fold to one marker on purpose — «Maxim» and «Maksim» must
# meet, and «Eroxin» (ГОСТ) then meets «Erokhin» too; the collision is
# confirmed or refused by `align` before anything is restored.
_FOLD: tuple[tuple[str, str], ...] = (
    ("shch", "S"), ("shh", "S"), ("sch", "S"),
    ("zh", "Z"), ("ch", "C"), ("sh", "H"),
    ("kh", "X"), ("ks", "X"), ("x", "X"),
    ("ts", "T"), ("tc", "T"), ("cz", "T"), ("c", "T"),
    ("yu", "U"), ("iu", "U"), ("ju", "U"),
    ("iya", "A"), ("iia", "A"), ("ija", "A"), ("ya", "A"), ("ia", "A"), ("ja", "A"),
    ("yo", "E"), ("jo", "E"), ("ye", "E"), ("ie", "E"), ("e", "E"),
    ("y", "I"), ("j", "I"), ("i", "I"),
)


# A `c` AFTER A VOWEL IS «к», NOT «ц». The table folds a bare `c` to the «ц»
# marker, which is right for «Цветаева» → «Cvetaeva» and wrong for «Виктория» →
# «Victoria»: the model's spelling folded to `vITtorA` and ours to `vIktorA`,
# so the lookup missed and the fake given name went to the tool. Word-initial
# and post-consonant `c` keep the «ц» reading, which is where that spelling of
# «ц» actually occurs.
# …UNLESS IT OPENS A DIGRAPH THE TABLE ALREADY READS. «Кузнецов» is
# «kuzneczov» in one of the standards: there the `c` also follows a vowel, and
# rewriting it to `k` broke the fold invariant the self-test pins.
_C_AS_K = re.compile(r"(?<=[aeiouy])c(?![hz])")


def fold(latin: str) -> str:
    """The canonical spelling of a Latin rendering; see `_FOLD`."""
    text = "".join(ch for ch in latin.lower() if ch.isalpha())
    text = _C_AS_K.sub("k", text)
    for source, marker in _FOLD:
        text = text.replace(source, marker)
    return re.sub(r"I+", "I", text)


def folded(cyrillic: str) -> str:
    """The index key of a Cyrillic word: its default rendering, folded."""
    return fold(render(cyrillic, {}))


def match_case(pattern: str, produced: str) -> str:
    """`produced` in the letter case `pattern` uses: all caps, capitalised, or lower."""
    letters = [ch for ch in pattern if ch.isalpha()]
    if letters and all(ch.isupper() for ch in letters):
        return produced.upper()
    if letters and letters[0].isupper():
        return produced[:1].upper() + produced[1:]
    return produced


def squeezed_initials(words: tuple[str, ...]) -> str:
    """«жм» for («Жанна», «Михайловна») — the index key of a pair of initials."""
    return "".join(word[:1].lower() for word in words if word)


def main() -> int:
    """Self-test: the fold invariant over the standards and the everyday
    forms, and the alignment on the words that broke the table design."""
    failures = 0

    def check(label: str, ok: bool) -> None:
        nonlocal failures
        if not ok:
            failures += 1
            print(f"FAIL {label}")

    names = ("Дмитрий", "Юлия", "Максим", "Мещерякова", "Заболотный", "Татьяна",
             "Сергей", "Наталия", "Ерохин", "Кузнецов", "Фёдорова", "Евгений",
             "Андрей", "Яков", "Илья", "Игорь", "Ксения", "Цветков", "Щербаков",
             "Михайлович", "Алексей", "Семёнович", "Битюкова", "Шилова", "Ольга",
             "Юрий", "Зоя", "Эдуард", "Всеволод")
    # ъ is the one letter the fold does not unify: ICAO writes it «ie», every
    # other convention drops it, and «ie» must stay a rendering of е. A surname
    # with ъ («Подъячев») under ICAO alone misses — none of the 1 812 control
    # words carried one.
    for word in names:
        keys = {fold(apply(table, word)) for table in TABLES} | {folded(word)}
        check(f"fold invariant {word}: {sorted(keys)}", len(keys) == 1)
        for table in TABLES:
            check(f"align {word} under a standard", align(word, apply(table, word)) is not None)
    for cyrillic, spellings in (
        ("Дмитрий", ("Dmitry", "Dmitriy", "Dmitrii", "Dmitrij")),
        ("Юлия", ("Yulia", "Yuliya", "Iuliia", "Julia")),
        ("Наталья", ("Natalia", "Natalya")),
        ("Максим", ("Maxim", "Maksim")),
        ("Мещерякова", ("Meshcheryakova", "Meshcheriakova", "Mescheryakova", "Meshheryakova")),
        ("Заболотный", ("Zabolotny", "Zabolotnyy", "Zabolotnyi")),
        ("Татьяна", ("Tatiana", "Tatyana")),
        ("Ерохин", ("Erokhin", "Eroxin")),
        ("Евгений", ("Evgeny", "Evgeniy", "Evgenii", "Yevgeny")),
        ("Ксения", ("Ksenia", "Kseniya", "Xenia")),
        ("Фёдорова", ("Fedorova", "Fyodorova")),
    ):
        for spelling in spellings:
            check(f"fold {spelling} meets {cyrillic}", fold(spelling) == folded(cyrillic))
            check(f"align {cyrillic} ~ {spelling}", align(cyrillic, spelling) is not None)
    check("align refuses another name", align("Ерохин", "Bukin") is None)
    check("align refuses a prefix", align("Ерохин", "Erokh") is None)
    # The lesson of the run: what the fake taught is applied, the rest is DEFAULT.
    learned = align("Бирюков", "Biryukov") or {}
    check("learned ю", learned.get("ю") == "yu")
    check("render Ерохин with what Бирюков taught", render("Ерохин", learned) == "erokhin")
    check("render Битюкова from DEFAULT", render("Битюкова", {}) == "bityukova")
    learned = align("Дмитрий", "Dmitry") or {}
    check("learned ending ий→y carries to Юрий", render("Юрий", learned) == "yury")
    learned = align("Мещерякова", "Meshcheryakova") or {}
    check("mixed convention learned", render("Щербакова", learned) == "shcherbakova")
    # «Сергей» was «sergey» here until the 06.09 live run counted the control
    # arms: Sergei 22, Sergey 12. The rule did not change — DEFAULT is what the
    # model writes — only the count behind one ending.
    check("DEFAULT is the control arm's majority, not a standard",
          render("Сергей", {}) == "sergei" and render("Щукин", {}) == "shchukin"
          and render("Юлия", {}) == "yulia" and render("Наталья", {}) == "natalia"
          and render("Заболотный", {}) == "zabolotny" and render("Дмитрий", {}) == "dmitriy")
    print("translit: PASS" if not failures else f"translit: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
