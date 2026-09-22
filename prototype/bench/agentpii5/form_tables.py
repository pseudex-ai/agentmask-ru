"""The vocabularies the form comparator reads, and nothing else.

They live apart from `form.py` for one reason: every one of them is a claim
about the OUTSIDE world — a published transliteration standard, the generic
words of a Russian address, the month names — and a claim about the world is
checked by reading the standard, not by reading the code that uses it. Mixing
them into the extractors would hide a wrong letter inside a control flow.

NOTHING here comes from `pseudex/`. The engine's own transliteration table
deciding whether the engine's rendering is «ГОСТ» is the instrument judging
itself (`bench/agentpii4/parts.py` says the same about its splitter), so the
three tables below are written from their standards and the address words from
ordinary Russian usage.
"""

# --- transliteration signatures (spec §8.4 «транслит-таблица») ------------------------
#
# We never transliterate; we only have to say WHICH table a Latin rendering
# came from, and that is decided by digraphs the three standards spell
# differently. Each entry is (label, alternatives); an alternative is a tuple
# of conditions that must ALL hold, a condition is ("sub", s) — s anywhere in
# the lower-cased string — or ("fin", s) — s ends a word. The first label
# whose alternatives include a satisfied one wins, so the order of
# TRANSLIT_SIGNATURES is the discriminating order, not a preference:
#
#   * ICAO Doc 9303 Part 3, machine-readable travel documents, Cyrillic
#     table: щ→SHCH, ю→IU, я→IA, ий/ый→II. The four-letter SHCH and the
#     i-digraphs are unique to it among the three.
#   * ГОСТ 7.79-2000 system B (the ASCII-only system): щ→SHH, ц→CZ/C,
#     ю→YU with й→J, я→YA with й→J, э→E'. The apostrophe and CZ exist in no
#     other table here, and the J is what separates it from BGN, which
#     writes й as Y.
#   * BGN/PCGN 1947 romanization of Russian: ю→YU, я→YA, х→KH, ц→TS,
#     ый/ий→Y. Checked last because YU/YA are shared with ГОСТ, which is told
#     apart by its J/CZ/apostrophe.
#
# «Nothing discriminating» is a real answer (`latin:unknown`): «Ivanov Petr»
# contains no letter the three tables spell differently, and a comparator that
# guessed would report a transliteration change that nobody made.
TRANSLIT_SIGNATURES: tuple[tuple[str, tuple[tuple[tuple[str, str], ...], ...]], ...] = (
    ("latin:icao", ((("sub", "shch"),), (("sub", "iu"),), (("sub", "ia"),), (("fin", "ii"),))),
    ("latin:gost", ((("sub", "shh"),), (("sub", "cz"),), (("sub", "yu"), ("sub", "j")),
                    (("sub", "ya"), ("sub", "j")), (("sub", "e'"),))),
    ("latin:bgn", ((("sub", "yu"),), (("sub", "ya"),), (("sub", "kh"),), (("sub", "ts"),),
                   (("fin", "y"),))),
)

# --- NAME ------------------------------------------------------------------------------

# Surname suffixes, Cyrillic, with the oblique endings a substitute reaches the
# model in («Иванову»). Exactly the brief's regex; `order` is a heuristic ON
# PURPOSE — the two strings are the same person, so a consistent reading of
# both compares correctly even where it would mis-label one in isolation.
CYRILLIC_SURNAME_SUFFIX: str = (
    r"(?:ов|ев|ёв|ин|ын|ск|цк|ой|ий|ая|яя|ых|их|ко|ук|юк|енко|ман|ер)"
    r"(?:а|у|ым|ом|е|ой|ую|ая|ие|ых|им|ими|ого|ому)?$")

# The same suffixes transliterated, and DELIBERATELY without `iy`/`ii`/`y`:
# those are how the three tables end a GIVEN name («Yuriy», «Iurii»), and a
# surname test that fired on them would read «Petrov Yuriy» as two surnames
# and «Petrov Iurii» as surname+given — the same person scored as two
# different part orders, which is the one thing `order` must never do.
LATIN_SURNAME_SUFFIX: str = (
    r"(?:ov|ev|yov|iov|ova|eva|yova|in|yn|ina|yna|sky|skiy|skaya|skaia|tsky|tskiy"
    r"|ko|uk|yuk|enko|man)$")

# Nobiliary and patronymic particles written as their own token. A hyphen and
# a particle are one feature (`hyphen_particle`) because both answer «is the
# name written as more than one bare word».
NAME_PARTICLES: frozenset[str] = frozenset({
    "де", "фон", "ван", "дер", "оглы", "кызы", "ибн", "бен", "аль", "эль",
    "дель", "ди", "да", "ла", "ле", "ду", "дос",
})

# --- LOC -------------------------------------------------------------------------------

# Stems of the FULL generic word, matched as a prefix of a word so that every
# case form of «улица» folds to one label. Longest first: the label is the
# stem, and a deterministic label needs a deterministic match order.
GENERIC_STEMS: tuple[str, ...] = (
    "микрорайон", "набережн", "проспект", "переулок", "переулк", "бульвар",
    "квартал", "площад", "проезд", "шоссе", "тупик", "тракт", "улиц", "алле",
    "лини",
)
# «переулок» and «переулка» are one generic word in two cases. LOC has no
# `gram_case` feature — the spec does not name one — so folding them is what
# keeps a case inflection of the generic word out of the `generic` feature,
# where it would read as «the agent changed the generic word».
GENERIC_STEM_CANON: dict[str, str] = {"переулок": "переулк"}

# The abbreviations, dot kept: «ул» and «ул.» are different forms and the
# spec's feature is «сокращение, какое». Longest first so «мкр.» is not read
# as «мкр» and «пр-т» not as «пр».
GENERIC_ABBREVIATIONS: tuple[str, ...] = (
    "просп.", "мкр.", "наб.", "пр-т", "пр-д", "кв-л", "пер.", "пл.", "пр.",
    "ул.", "б-р", "ш.", "мкр", "пер", "ул",
)

# A word that names a part of an address rather than a person or a place:
# excluded from `case_class` (the spec asks for the case of the NAME, and
# «ул.» is lower case in every register) and from the street-name search.
MARKER_WORDS: frozenset[str] = frozenset({
    "ул", "улица", "улицы", "улице", "улицу", "улицей",
    "пр", "пр-т", "прт", "просп", "проспект", "проспекта",
    "пер", "переулок", "переулка", "б-р", "бр", "бульвар",
    "ш", "шоссе", "пл", "площадь", "наб", "набережная",
    "пр-д", "проезд", "аллея", "тупик", "мкр", "микрорайон",
    "кв-л", "квартал", "линия", "тракт",
    "д", "дом", "кв", "квартира", "влд", "владение", "уч", "участок",
    "оф", "офис", "пом", "помещение",
    "г", "город", "с", "село", "пос", "посёлок", "поселок", "пгт",
    "дер", "деревня", "ст", "станица",
    "корп", "корпус", "к", "стр", "строение", "под", "подъезд", "п",
    "эт", "этаж", "лит", "литера",
    "обл", "область", "р-н", "район", "рн",
})

# --- DOB / DATE ------------------------------------------------------------------------

# The month words the comparator must recognise, by exact form. A stem match
# would have to accept «ма», which eats «Мария» and every «май» that is not a
# month; the forms are finite, so they are listed.
MONTH_NOMINATIVE: frozenset[str] = frozenset({
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
})
MONTH_GENITIVE: frozenset[str] = frozenset({
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
})
# Other forms a register produces («в марте», «к маю»). They carry no
# nominative/genitive verdict of their own, so `month_form` reads them by
# ending — the feature the spec names is «число/слово/падеж», and a form
# outside the two it lists must still land on one of the two labels.
MONTH_OTHER: frozenset[str] = frozenset({
    "январе", "феврале", "марте", "апреле", "мае", "июне",
    "июле", "августе", "сентябре", "октябре", "ноябре", "декабре",
    "январю", "февралю", "марту", "апрелю", "маю", "июню",
    "июлю", "августу", "сентябрю", "октябрю", "ноябрю", "декабрю",
})
MONTH_WORDS: frozenset[str] = MONTH_NOMINATIVE | MONTH_GENITIVE | MONTH_OTHER
