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

from pseudex.assets import ASSETS

# The measured tables (UNITS/DEFAULT/ENDINGS/TABLES/FOLD) are LEASED, not compiled
# — read from ASSETS.get().translit at call time. Only the align/render/fold
# ALGORITHM and the `_C_AS_K` rule (which is algorithm, not tuning) live here.


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
    endings = ASSETS.get().translit.endings
    out: list[str] = []
    i = 0
    while i < len(low):
        for ending in endings:
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
    units_map = ASSETS.get().translit.units
    seen: set[tuple[int, int]] = set()

    def go(index: int, at: int) -> dict[str, str] | None:
        if index == len(units):
            return {} if at == len(wanted) else None
        if (index, at) in seen:
            return None
        unit = units[index]
        options = units_map.get(unit)
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
    default = ASSETS.get().translit.default
    out: list[str] = []
    for unit in units_of(cyrillic):
        if unit in learned:
            out.append(learned[unit])
        elif unit in default:
            out.append(default[unit])
        elif unit.isalpha():
            out.append(unit)
    return "".join(out)


def variants(word: str) -> frozenset[str]:
    """Every Latin spelling of one Cyrillic word under the four tables."""
    if not is_cyrillic_word(word):
        return frozenset()
    return frozenset(apply(table, word) for table in ASSETS.get().translit.tables)


def table_for(cyrillic: str, latin: str) -> dict[str, str] | None:
    """The table that spells `cyrillic` as `latin`, or None."""
    wanted = "".join(ch for ch in latin.lower() if ch.isalpha())
    for table in ASSETS.get().translit.tables:
        if apply(table, cyrillic) == wanted:
            return table
    return None



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
    for source, marker in ASSETS.get().translit.fold:
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
    # The tables are leased now, so the self-test loads a dev bundle first. Via
    # testkit (not `import licensing`, which the release build forbids in pseudex/).
    from testkit import load_dev_bundle
    load_dev_bundle()
    tables = ASSETS.get().translit.tables

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
        keys = {fold(apply(table, word)) for table in tables} | {folded(word)}
        check(f"fold invariant {word}: {sorted(keys)}", len(keys) == 1)
        for table in tables:
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
