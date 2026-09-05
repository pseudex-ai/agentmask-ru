"""Derived fields: what an agent COMPUTES from personal data, not what it copies.

A tool schema asks for a postcode and the agent derives it from the city it
read; for an age and it derives it from the date of birth; for a cardholder
and it transliterates the name. When the city, the date or the name it read
was a SUBSTITUTE, the derived value is wrong for the real person, and no
restoration can fix it — the fake was consumed by a function, not copied.
`docs/known-issues.md` Б3 names the class; this module is how the benchmark
recognises it.

EVERY FUNCTION RETURNS THE SET OF ACCEPTED ANSWERS, never one string: three
transliteration standards are all correct, «Т.В.» and «Т. В.» are both
initials, and a birthday falling today gives two ages. The comparator tests
membership.

Nothing here imports `pseudex`. A derivation library in the engine would be a
product feature; this one is the instrument's independent reading.
"""
import datetime as dt

from bench.agentpii4.pools import CITIES

Accepted = frozenset[str]


def postcode_zone(city: str) -> Accepted:
    """The postal zone — the first three digits of the index — for a city.

    Three digits and not six: an agent asked for a postcode invents the last
    three (or looks up a street we do not model), and the zone is what the
    city determines. A substitute city in another zone is what `derived` means.
    """
    row = CITIES.get(city.strip().lower())
    return frozenset({row[1]}) if row and row[1] else frozenset()


def postcode_matches(postcode: str, city: str) -> bool | None:
    """True/False when the city is in the table, None when unverifiable."""
    zones = postcode_zone(city)
    if not zones:
        return None
    digits = "".join(ch for ch in postcode if ch.isdigit())
    return any(digits.startswith(zone) for zone in zones)


def timezone(city: str) -> Accepted:
    row = CITIES.get(city.strip().lower())
    return frozenset({row[2]}) if row and row[2] else frozenset()


def region(city: str) -> Accepted:
    row = CITIES.get(city.strip().lower())
    return frozenset({row[0]}) if row and row[0] else frozenset()


def age(dob_iso: str, now_iso: str) -> Accepted:
    """Full years at `now`. A birthday today counts both ways."""
    try:
        born = dt.date.fromisoformat(dob_iso)
        now = dt.date.fromisoformat(now_iso)
    except ValueError:
        return frozenset()
    years = now.year - born.year - ((now.month, now.day) < (born.month, born.day))
    if (now.month, now.day) == (born.month, born.day):
        return frozenset({str(years), str(years - 1)})
    return frozenset({str(years)})


def gender(parts: dict[str, str]) -> Accepted:
    """From the pool's own gender when present; else from name shape.

    A benchmark-side guess for a SUBSTITUTE name (whose pool gender we do not
    have): a given name ending in -а/-я or a patronymic in -вна is female.
    Deliberately crude — it must be wrong the same way for both arms.
    """
    known = parts.get("gender", "")
    if known in ("m", "f"):
        return frozenset({_gender_words(known)})
    patronymic = parts.get("patronymic", "").lower()
    given = parts.get("given", "").lower()
    surname = parts.get("surname", "").lower()
    if patronymic.endswith(("вна", "ична", "чна")):
        return frozenset({_gender_words("f")})
    if patronymic.endswith(("вич", "ич", "ыч")):
        return frozenset({_gender_words("m")})
    if surname.endswith(("ова", "ева", "ина", "ына", "ская", "цкая")):
        return frozenset({_gender_words("f")})
    if surname.endswith(("ов", "ев", "ин", "ын", "ский", "цкий")):
        return frozenset({_gender_words("m")})
    if given.endswith(("а", "я")) and given not in ("илья", "никита", "фома", "кузьма"):
        return frozenset({_gender_words("f")})
    if given:
        return frozenset({_gender_words("m")})
    return frozenset()


def _gender_words(code: str) -> str:
    return "female" if code == "f" else "male"

GENDER_ACCEPTED: dict[str, frozenset[str]] = {
    "female": frozenset({"female", "f", "ж", "женский", "woman", "жен"}),
    "male": frozenset({"male", "m", "м", "мужской", "man", "муж"}),
}


def gender_matches(written: str, expected: Accepted) -> bool:
    low = written.strip().lower()
    return any(low in GENDER_ACCEPTED[code] for code in expected)


def initials(parts: dict[str, str]) -> Accepted:
    """«Т.В.» from given + patronymic; «Т.» when there is no patronymic."""
    given = parts.get("given", "")
    patronymic = parts.get("patronymic", "")
    if not given:
        return frozenset()
    first = given[0].upper()
    if patronymic:
        second = patronymic[0].upper()
        return frozenset({f"{first}.{second}.", f"{first}. {second}.", f"{first}{second}",
                          f"{first}.{second}", f"{first} {second}"})
    return frozenset({f"{first}.", first})


def initials_matches(written: str, expected: Accepted) -> bool:
    squeezed = "".join(ch for ch in written.upper() if ch.isalpha())
    return any("".join(ch for ch in one.upper() if ch.isalpha()) == squeezed
               for one in expected)


# Three transliteration standards a Russian document or card may carry:
# ICAO Doc 9303 (МВД since 2014 for passports), ГОСТ 7.79-2000 system B, and
# the 2010 МВД table. All three are correct answers for a cardholder or a
# Latin name field, so all three are accepted.
_ICAO = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "ie", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
_GOST_B = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "cz", "ч": "ch", "ш": "sh", "щ": "shh",
    "ъ": "``", "ы": "y`", "ь": "`", "э": "e`", "ю": "yu", "я": "ya",
}
_MVD_2010 = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "tc", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
_COMMON = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _apply(table: dict[str, str], word: str) -> str:
    return "".join(table.get(letter, letter) for letter in word.lower())


def translit_icao(word: str) -> str:
    """The ICAO spelling («Kuznetsov», not the ГОСТ «Kuzneczov»)."""
    return "".join(ch for ch in _apply(_ICAO, word) if ch.isalpha())


# WHAT A MODEL ACTUALLY WRITES, measured — not a standard. Over 1 812 Latin
# words the CONTROL arm wrote for real names on three live runs (03.09, 04.09,
# 05.09; claude-sonnet-4-6), letter by letter: й→y 112:24, ю→yu 87:0, я→ya
# 37:26, х→kh 93:0, ц→ts 104:0, ё→e 72:24, ь dropped 149:0; endings «-ий»→iy
# 77:51, «-ый»→y 24:2, «-ия»→ia 36:0, «ья»→ia 22:2. The scripted agent wrote
# ICAO before, and the smoke test then scored the engine against a convention
# no model uses: 44 divergences on 474 cases, all of them «SERGEI» against
# «SERGEY». The instrument's habit must be a MODEL's habit, and this is the
# measured one; it is kept here, as the engine's own table is kept there, so
# neither copies the other.
_COMMON_ENDINGS: tuple[tuple[str, str], ...] = (("ий", "iy"), ("ый", "y"), ("ия", "ia"), ("ья", "ia"))
_COMMON_LETTERS: dict[str, str] = dict(_COMMON, **{"щ": "shch"})


def translit_common(word: str) -> str:
    """The everyday spelling a model writes unprompted; see the note above."""
    low = word.lower()
    out: list[str] = []
    i = 0
    while i < len(low):
        for ending, latin in _COMMON_ENDINGS:
            if low.startswith(ending, i):
                out.append(latin)
                i += len(ending)
                break
        else:
            out.append(_COMMON_LETTERS.get(low[i], low[i]))
            i += 1
    return "".join(ch for ch in "".join(out) if ch.isalpha())


def translit_variants(word: str) -> Accepted:
    """Every accepted Latin spelling of one Cyrillic word, lowercased."""
    if not word:
        return frozenset()
    out = {_apply(table, word) for table in (_ICAO, _GOST_B, _MVD_2010, _COMMON)}
    # Case-insensitive and apostrophe-free: cardholder fields are uppercase and
    # the ГОСТ soft-sign marks are dropped on every real card.
    return frozenset("".join(ch for ch in one if ch.isalpha()) for one in out)


def translit_matches(written: str, words: tuple[str, ...]) -> bool:
    """Does a written Latin string spell exactly these Cyrillic words, in any
    order and any accepted standard?"""
    tokens = ["".join(ch for ch in token.lower() if ch.isalpha())
              for token in written.replace("-", " ").split()]
    tokens = [token for token in tokens if token]
    if len(tokens) != len(words):
        return False
    accepted = [translit_variants(word) for word in words]
    used = [False] * len(tokens)
    for options in accepted:
        for index, token in enumerate(tokens):
            if not used[index] and token in options:
                used[index] = True
                break
        else:
            return False
    return True


def e164(digits10: str) -> Accepted:
    digits = "".join(ch for ch in digits10 if ch.isdigit())[-10:]
    return frozenset({f"+7{digits}"}) if len(digits) == 10 else frozenset()


def main() -> int:
    failures = 0
    checks = [
        (postcode_zone("Ижевск"), frozenset({"426"})),
        (postcode_matches("426034", "ижевск"), True),
        (postcode_matches("196655", "ижевск"), False),
        (postcode_matches("123456", "тмутаракань"), None),
        (age("1987-03-14", "2026-09-02"), frozenset({"39"})),
        (age("1987-09-02", "2026-09-02"), frozenset({"39", "38"})),
        (gender({"gender": "f"}), frozenset({"female"})),
        (gender({"given": "тамара", "surname": "павлова"}), frozenset({"female"})),
        (gender({"given": "сергей", "patronymic": "иванович"}), frozenset({"male"})),
        (gender_matches("Ж", frozenset({"female"})), True),
        (initials_matches("Т. В.", initials({"given": "тамара", "patronymic": "владимировна"})), True),
        (initials_matches("ТВ", initials({"given": "тамара", "patronymic": "владимировна"})), True),
        (initials_matches("Т.П.", initials({"given": "тамара", "patronymic": "владимировна"})), False),
        (translit_matches("PAVLOVA TAMARA", ("павлова", "тамара")), True),
        (translit_matches("Tamara Pavlova", ("павлова", "тамара")), True),
        (translit_matches("IUliia Fedorova", ("фёдорова", "юлия")), True),
        (translit_matches("Yulia Fyodorova", ("фёдорова", "юлия")), False),
        (translit_matches("BUKIN", ("букин", "сергей")), False),
        (translit_common("Сергей") == "sergey" and translit_common("Заболотный") == "zabolotny"
         and translit_common("Юлия") == "yulia" and translit_common("Наталья") == "natalia"
         and translit_common("Щукин") == "shchukin" and translit_common("Ерохин") == "erokhin", True),
        (timezone("самара"), frozenset({"Europe/Samara"})),
        (e164("8 916 402 11 87"), frozenset({"+79164021187"})),
    ]
    for got, want in checks:
        if got != want:
            failures += 1
            print(f"FAIL {got!r} != {want!r}")
    print("derive: PASS" if not failures else f"derive: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
