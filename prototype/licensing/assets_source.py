"""THE authored detection assets. This file never ships to a customer.

Everything here was tuned against benchmarks and false-positive reports: name
gazetteers, street vocabulary, cue words, the priority table. It is the product.
The engine (`pseudex/`) knows the SCHEMA of these assets and how to compile them,
but holds none of the values — it receives them as a leased bundle at runtime.

The split rule (docs/tz-license-packaging.md §2.2):

    In the bundle — everything we tuned.
    In the binary — everything published, and every algorithm.

So the СНИЛС checksum and the card regex stay in `pseudex/ru_pii.py` (published
formats, nothing to steal), while the 28k first names, the street gazetteer and
the phone-deny list live here.

Regex SOURCE STRINGS rather than compiled patterns: the bundle is JSON, and the
engine compiles them once at load. Building them here keeps the vocabulary and
the pattern that consumes it in one place — a street marker added to `_ST` with
no matching change in the engine is impossible by construction.
"""

# --- names ---------------------------------------------------------------

SEED_FIRST_NAMES: tuple[str, ...] = (
    "александр", "алексей", "анатолий", "андрей", "антон", "артур", "артём",
    "артем", "борис",
    "вадим", "валентин", "валерий", "василий", "виктор", "виталий", "владимир",
    "владислав", "вячеслав", "геннадий", "георгий", "глеб", "григорий", "даниил",
    "денис", "дмитрий", "евгений", "егор", "иван", "игорь", "илья", "кирилл",
    "константин", "леонид", "максим", "марк", "михаил", "никита", "николай",
    "олег", "павел", "пётр", "петр", "роман", "руслан", "сергей", "станислав",
    "степан", "тимофей", "фёдор", "федор", "юрий", "ярослав",
    "александра", "алёна", "алина", "алиса", "анастасия", "анна", "валентина",
    "валерия", "вера", "вероника", "виктория", "галина", "дарья", "екатерина",
    "елена", "елизавета", "ирина", "карина", "кристина", "ксения", "лариса",
    "любовь", "людмила", "маргарита", "марина", "мария", "надежда", "наталья",
    "нина", "оксана", "ольга", "полина", "светлана", "софия", "татьяна", "юлия",
    # Given names of Russian citizens that are not Slavic. Measured on
    # AgentPII-RU: with only the Slavic list, a lower-case «тимур абдуллаев» or
    # «ашот мкртчян» produced NOTHING — the given name is the anchor the
    # adjacent-surname rule needs, and without it both halves leak. On NEREL the
    # same gap shows as foreign-name recall.
    #
    # Short ambiguous forms («ли», «ким», «ань») are deliberately absent: as a
    # bare word each is a conjunction, a surname or a particle far more often
    # than a given name, and the cost of masking them is a broken sentence.
    "тимур", "рустам", "ашот", "эльдар", "карен", "ильдар", "марат", "ринат",
    "айдар", "амир", "самир", "арсен", "армен", "ваган", "сурен", "тигран",
    "мурад", "заур", "аслан", "магомед", "ахмед", "юсуф", "фарид", "камиль",
    "лейла", "алия", "мадина", "зарина", "диана", "амина", "эльвира", "гульнара",
    "олесь", "остап", "тарас", "богдан", "майкл", "джон", "дэвид", "роберт",
    "томас", "анджей", "марек", "нино", "гоча", "заза",
    # Ordinary Russian given names the seed simply did not have. They are needed
    # in BOTH directions and that is not a coincidence: the substitute pool and
    # the recognition pool have to be the same set. A fake name our own detector
    # cannot see is found only by its surname, is therefore not a minted token,
    # gets masked a second time, and the person drifts mid-conversation.
    "аркадий", "вениамин", "всеволод", "герман", "гордей", "демьян", "захар",
    "игнат", "кузьма", "лев", "макар", "матвей", "мирон", "мирослав",
    "назар", "платон", "прохор", "радислав", "ратмир", "родион", "савва",
    "савелий", "святослав", "семён", "трофим", "филипп", "харитон", "эдуард",
    "эмиль", "яков", "ян", "агата", "аглая", "алевтина", "алиса",
    "алла", "альбина", "амелия", "ангелина", "антонина", "арина", "белла",
    "богдана", "валерия", "варвара", "василиса", "влада", "власта", "гелена",
    "диана", "дина", "ева", "евгения", "елизавета", "жанна", "зинаида",
    "злата", "зоя", "иванна", "инга", "инна", "иоланта", "капитолина",
    "клавдия", "лада", "лидия", "лилия", "майя", "милана", "милена",
    "мирослава", "нелли", "николь", "олеся", "прасковья", "раиса", "регина",
    "римма", "роза", "руслана", "сабина", "серафима", "снежана", "стелла",
    "таисия", "тамара", "ульяна", "фаина", "христина", "эвелина", "эмилия",
    "ярослава",
)
DIMINUTIVES: tuple[str, ...] = (
    "саша", "лёша", "леша", "толя", "андрюша", "тоша", "вадик", "валя", "вася",
    "витя", "вова", "влад", "слава", "гена", "гоша", "гриша", "даня", "дениска",
    "дима", "женя", "ваня", "игорёк", "костя", "лёня", "макс", "миша", "коля",
    "паша", "петя", "рома", "сергунь", "серёжа", "сережа", "стёпа", "юра",
    "настя", "аня", "валя", "вика", "галя", "даша", "катя", "лена", "лиза",
    "ира", "кристи", "ксюша", "люба", "люда", "рита", "маша", "надя", "наташа",
    "оля", "поля", "света", "соня", "таня", "юля",
    # THE SECOND TIER, and it is the register the product is actually sold into.
    # The list above is the polite diminutive («Саша», «Катя»); a support chat
    # writes the familiar one. Measured by a persona running a barbershop bot:
    # of fourteen colloquial names, TEN went to the model in the clear —
    # «виталик», «димон», «серёга», «колян», «танюха», «вовчик», «ленка»,
    # «стас», «алёнка» — while «макс», «юля», «паша» were caught. The type
    # «ФИО» was reported as supported and the example beside it was «Иванову
    # Петру Сергеевичу»; that is not what a telegram bot receives.
    #
    # These are productive suffixes (-ик, -он, -ян, -уха, -чик, -ка, -ёк) on
    # names the first tier already knows, so the layer is closed enough to list.
    # Entries that are ORDINARY RUSSIAN WORDS are dropped when the bundle is
    # built — «мишка» is a teddy bear before it is anybody — so the filter that
    # protects the first tier protects this one unchanged.
    "виталик", "толик", "славик", "костик", "эдик", "гарик", "русик",
    "димон", "вован", "колян", "толян", "антоха", "серёга", "серега",
    "андрюха", "ванюха", "лёха", "леха", "санёк", "саня", "вовчик", "димчик",
    "стас", "гриня", "рома", "тёма", "тема", "артём", "жека",
    "танюха", "катюха", "надюха", "любаша", "катюша", "ленка", "светка",
    "танька", "юлька", "олька", "иринка", "настюха", "алёнка", "аленка",
    "ленуся", "машуля", "дашка", "наташка",
)
SURNAME_SUFFIXES: tuple[str, ...] = (
    "ов", "ова", "ев", "ева", "ёв", "ёва", "ин", "ина", "ын", "ына",
    "ский", "ская", "цкий", "цкая", "ко", "ук", "юк", "ян", "дзе", "швили", "ич",
)
PATRONYMIC_SUFFIXES: tuple[str, ...] = (
    "ович", "евич", "ич", "овна", "евна", "ична", "инична",
)
# Whole patronymics for building a substitute that MIRRORS the original's shape.
# «Иванов Пётр Сергеевич» replaced by a two-part «Андрей Шилов» leaves the model
# looking at a different number of words than the sentence was built around, and
# a model that notices a mismatch is a model that rewrites it.
#
# Real forms rather than derived ones: a patronymic belongs to the FATHER's name,
# so it need not agree with the given name we pick, and derivation rules for -ий,
# -ь and -а endings produce «Андрейович» often enough to matter.
PATRONYMICS_MASC: tuple[str, ...] = (
    "Александрович", "Алексеевич", "Андреевич", "Борисович", "Валентинович",
    "Валерьевич", "Васильевич", "Викторович", "Владимирович", "Геннадьевич",
    "Григорьевич", "Дмитриевич", "Евгеньевич", "Иванович", "Игоревич",
    "Ильич", "Кириллович", "Константинович", "Леонидович", "Максимович",
    "Михайлович", "Николаевич", "Олегович", "Павлович", "Петрович",
    "Романович", "Семёнович", "Сергеевич", "Степанович", "Фёдорович",
    "Юрьевич", "Ярославович",
)
PATRONYMICS_FEMN: tuple[str, ...] = (
    "Александровна", "Алексеевна", "Андреевна", "Борисовна", "Валентиновна",
    "Валерьевна", "Васильевна", "Викторовна", "Владимировна", "Геннадьевна",
    "Григорьевна", "Дмитриевна", "Евгеньевна", "Ивановна", "Игоревна",
    "Ильинична", "Кирилловна", "Константиновна", "Леонидовна", "Максимовна",
    "Михайловна", "Николаевна", "Олеговна", "Павловна", "Петровна",
    "Романовна", "Семёновна", "Сергеевна", "Степановна", "Фёдоровна",
    "Юрьевна", "Ярославовна",
)
TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
# Cues that the next word is a person's name. Only the text BEFORE the word is
# examined: looking after it as well made `начнём роман с клиентом` match on
# `клиентом` and mask `роман` again.
NAME_CUES: tuple[str, ...] = (
    "имя", "имени", "зовут", "фио", "клиент", "получател", "заказчик",
    "контакт", "на кого", "оформить на",
    # VERBS THAT TAKE A PERSON. An ambiguous lower-case name — «ира», «вика»,
    # «света» are all ordinary words too — needs a capital or a cue, and in a
    # booking bot it gets neither: «запиши иру на 12» leaked the name whole
    # while «запиши лену» was caught, purely because «лена» is not ambiguous.
    #
    # These verbs are the cue that register actually supplies. They are also
    # what keeps the plant out: «посадил вику» is vetch and stays unmasked,
    # «запиши вику» is a customer. The distinguishing evidence is the verb, not
    # the noun, which is why a deny-list of plants could never have worked.
    "запиши", "запишите", "перезвони", "перезвоните", "позвони", "позвоните",
    "набери", "наберите", "свяжись", "свяжитесь", "напомни", "напомните",
    "отправь", "отправьте", "передай", "передайте", "пригласи", "пригласите",
)
# Sentence-initial imperatives / fillers NER mislabels as a person or place.
STOPWORDS: tuple[str, ...] = (
    "доставьте", "оформите", "проверьте", "запишите", "уточните", "верните",
    "отмените", "перенесите", "подскажите", "помогите", "скажите", "найдите",
    "сделайте", "добавьте", "измените", "пришлите", "не", "да", "здравствуйте",
    "спасибо", "пожалуйста", "клиент", "заказ",
)

# --- address -------------------------------------------------------------

# Street-name gazetteer for toponyms with no morphological signal (genitive
# nouns pymorphy would miss): "улица Мира", "8 Марта", "проспект Победы".
STREET_GAZ: tuple[str, ...] = (
    "мира", "победы", "октября", "космонавтов", "строителей", "энтузиастов",
    "дружбы", "свободы", "труда", "молодёжи", "юности", "гвардии", "марта", "мая",
    "ленина", "гагарина", "пушкина", "кирова", "жукова",
)
# A candidate is CORE (can stand alone) or SUPPORT (only counts when merged with
# a core). City/settlement/apt/index are SUPPORT so lone cities stay unmasked.
CORE_PART: tuple[str, ...] = (
    "улиц", "дом", "микрорайон", "проспект", "переул", "проезд",
    "бульвар", "набереж", "шоссе", "площад", "владени",
)
# Tails of numbered streets ("улица 1905 года", "8 марта"): generic RU pattern.
NUMBERED_TAIL: tuple[str, ...] = (
    "года", "год", "лет", "марта", "мая", "января", "февраля", "апреля", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря", "партсъезда",
)

# Street type markers (used marker-first AND marker-last); each only fires next
# to a Capitalized name, so a bare "пл"/"пр" can't match.
_ST = (
    r"(?:улиц\w+|ул\.?|проспект\w*|просп\.?|пр-?кт\.?|пр-?т\.?|переул\w+|пер\.?"
    r"|проезд\w*|пр-д|бульвар\w*|б-р|набережн\w+|наб\.?|шоссе|ш\.|площад\w+|пл\.?"
    r"|тупик\w*|туп\.?|алле\w+|лини\w+|квартал\w*|кв-л|тракт\w*|просек\w*)"
)
# The street/settlement markers above are case-insensitive (ул/Ул), but the NAME
# must be truly Capitalized — `(?-i:...)` keeps the capital case-sensitive even
# inside an IGNORECASE pattern, so "пер" in "перезвоните" can't grab a lowercase
# tail and "площадью 5 кв" can't pass as a street.
_NAME = r"(?-i:[А-ЯЁ])[а-яё]+(?:[\s-](?-i:[А-ЯЁ])[а-яё]+){0,2}"
_CAP = r"(?:\d+[-\s]?[а-яё]{0,2}\s+)?" + _NAME
_TOK = r"(?:(?<=^)|(?<=[\s,;(№#]))"  # token must start fresh -> excludes "т.д"
# The apartment marker may be GLUED TO THE HOUSE NUMBER, and in real Russian
# addresses it usually is: «д.5кв12», «Строителей 53к193», «Гагарина88кв152».
# `_TOK` alone requires whitespace before the marker, so the flat number simply
# fell outside the span — the street and house were masked and the apartment
# went to the model in the clear, inside an address that now mixed a fake street
# with a real flat.
#
# «кв» after a digit stays safe because the pattern demands DIGITS AFTER the
# marker: «100кв.м» (square metres) has «м» there and still does not match.
_TOK_OR_DIGIT = r"(?:(?<=^)|(?<=[\s,;(№#])|(?<=\d))"
_NUM_NAME = r"\d{1,4}[-\s]?[яейои]?\s+(?:" + "|".join(NUMBERED_TAIL) + r")"

# EACH PATTERN CARRIES ITS OWN CASE FLAG as a leading `(?i)`, and the engine
# compiles it with no flags of its own.
#
# This is not stylistic. Case sensitivity is load-bearing here and it differs per
# pattern: `markerless` relies on `[А-ЯЁ][а-яё]+` meaning a genuinely Capitalised
# word, and compiling it case-insensitively makes it match ordinary lowercase
# prose — "течение 12" and "Вашингтоне за 8" become addresses. Those inflated LOC
# spans then outrank NAME in overlap resolution (ADDR 4 > NAME 3) and swallow real
# people, so a single wrong flag costs recall on a type it never touched.
# Measured: 12 lost PERSON mentions on NEREL.
#
# Keeping the flag next to the pattern makes that unrepresentable — there is no
# separate list of exceptions for the engine to apply incorrectly.
# Full street-type words only — no abbreviations — followed by a LOWER-CASE name
# and a house number. Support chat has no capitals: «адрес улица строителей 10
# кв 245» is the ordinary way a customer gives an address in a messenger, and
# every capitalisation-dependent pattern above is blind to it. Measured on
# AgentPII-RU, address recall was 36% overall and 100% only on the clean
# register — the gap was entirely this.
#
# The house NUMBER is what makes it safe. Dropping it and matching «улица» plus
# any lower-case word turns «улица была пустой» into an address; requiring the
# digit costs nothing real, because an address without a house number is not one.
# The abbreviations are deliberately excluded here for the same reason the
# marker-less pattern is capital-sensitive: a bare «пр» or «ул» inside ordinary
# prose has nothing else holding it down.
_ST_FULL = (r"(?:улиц\w+|проспект\w*|переул\w+|бульвар\w*|набережн\w+|шоссе"
            r"|площад\w+|проезд\w*|микрорайон\w*|тупик\w*|алле\w+)")
_LOWER_NAME = r"[а-яё]{3,}(?:[\s-][а-яё]{3,}){0,2}"
# Between a street and its number: nothing, or a comma and a house marker.
_HOUSE_LEAD = r"(?:\s*,?\s*(?:дом|д)\.?)?\s*"

ADDRESS_PATTERNS: dict[str, str] = {
    # `\s*` before the house number, not `\s+`: «улица Гагарина88кв152» is how a
    # phone keyboard renders an address when the space is missed, and requiring
    # the space dropped the house number out of the span — the street was masked
    # and the building number was not.
    # `\s*` between the name and the TYPE as well, not only before the house
    # number: «ленинскийпроспект 42», «профсоюзнаяулица 63», «улицаЛенина 5» are
    # what a phone keyboard produces when the space is missed, and the whole
    # address then matched nothing at all — street, house and flat went to the
    # model together. A type word cannot begin or end an ordinary Russian word,
    # so gluing it on is not ambiguous the way a missing space between two
    # ordinary words would be.
    # The HOUSE MARKER may stand between the street and its number, and in
    # lower case it usually does: «ленинский проспект, д. 42, кв. 118» matched
    # nothing at all — the span began at «д. 42» and the street went to the
    # model in the clear, while the same address without commas was caught.
    "street_lower_first": rf"(?i)\b{_ST_FULL}\s*{_LOWER_NAME}{_HOUSE_LEAD}\d{{1,4}}",
    "street_lower_last": rf"(?i)\b{_LOWER_NAME}\s*{_ST_FULL}{_HOUSE_LEAD}\d{{1,4}}",
    "street_first": rf"(?i)\b{_ST}\s*\.?\s*{_CAP}",
    "street_last": rf"(?i){_CAP}\s+{_ST}\b",
    "house": (
        r"(?i)" + _TOK + r"(?:дом|д|владени\w*|вл|уч\w*)\.?\s*№?\s*\d+(?:[а-яёА-ЯЁ](?!\d)|/\d+|-\d+)?"
        r"(?:\s*(?:корпус|корп|кор|к)\.?\s*\d+[а-яёА-ЯЁ]?)?"
        r"(?:\s*(?:строени\w*|стр|с)\.?\s*\d+[а-яёА-ЯЁ]?)?"
        r"(?:\s*(?:литер\w*|лит)\.?\s*[а-яёa-z]\b)?"
    ),
    # Two branches, because the markers differ in how much they can be trusted
    # alone. Spelled-out ones may open a token; a bare «к» may not — «за 100к 5
    # штук» would read as an apartment — so it is admitted only when glued to a
    # digit, which is where «Строителей 53к193» puts it.
    #
    # Both are SUPPORT, never core: a match that is not adjacent to a street or a
    # house number is dropped by `detect_address`, so a stray one cannot mask
    # anything by itself.
    "apt": (r"(?i)(?:" + _TOK_OR_DIGIT
            + r"(?:квартир\w*|кв|офис\w*|оф|помещени\w*|пом|комнат\w*|комн"
              r"|корпус\w*|корп|кор)\.?\s*\d+"
            + r"|(?<=\d)к\s*\d+)"),
    "mkr": r"(?i)\b(?:микрорайон\w*|мкрн|мкр)\.?\s*(?:[А-ЯЁ][а-яё]+|\d+[а-яё]?)",
    "settlement": (
        r"(?i)" + _TOK + r"(?:город|гор|г|посёлок|поселок|пос|п|село|деревн\w*|дер|станиц\w*|ст"
        r"|хутор\w*|пгт|снт|днп)\.?\s*" + _NAME
    ),
    # RURAL ADDRESSING IS A CORE PART, because in a village there is no street:
    # the address IS «деревня Горбунки, 24». A settlement was support only, so a
    # span with no street was dropped and the whole address went to the model in
    # the clear. Found in 993 production dialogues of a water delivery company
    # in Leningrad oblast — half their traffic is villages, and no corpus of
    # ours contained one.
    "rural": (
        r"(?i)" + _TOK + r"(?:посёл\w*|посел\w*|пос|село|сел[ае]|деревн\w*|дер|хутор\w*"
        r"|пгт|снт|днп|тсн)\.?\s*" + _NAME + r"[\s,]+(?:д\.?|дом)?\s*\d{1,4}"
    ),
    # District and municipal-settlement names. SUPPORT: on their own they are a
    # region, not somebody's address — but beside a street or a house they are
    # part of it, and leaving them out masked the street while «Всеволожский
    # район, Морозовское городское поселение» stayed in the clear beside it.
    "district": (
        r"(?i)(?-i:[А-ЯЁ])[а-яё]+(?:ый|ий|ое|ая)?\s*"
        r"(?:район\w*|р-н|городско\w+\s+поселени\w+|сельско\w+\s+поселени\w+"
        r"|гор\.?\s*посел\w*|\bгп\b|\bсп\b)"
    ),
    # No (?i): digits only, and adding one would be a lie about intent.
    "index": r"\b\d{6}\b",
    # Marker-less street + house number. Captures an optional leading number
    # ("8 Марта"), 1-3 Capitalized words ("Карла Маркса"), then a 1-3 digit house
    # number with an OPTIONAL letter ("174В") or "/N" form. A trailing negative
    # lookahead replaces \b so the uppercase house letter is not orphaned.
    "markerless": (
        r"(?:(?<=^)|(?<=[\s,;(]))"
        r"(?P<num>\d+[-\s]?[яейои]?\s+)?"
        r"(?P<words>[А-ЯЁ][а-яё]+(?:[\s-][А-ЯЁ][а-яё]+){0,2})"
        r"\s+(\d{1,3}[А-ЯЁа-яё]?(?:/\d+)?)(?![0-9A-Za-zА-Яа-яёЁ])"
    ),
    # Address context (Presidio-style enhancement): when nearby, a marker-less
    # Capitalized/numbered "name + house" is accepted even with no morphology
    # signal. Universal RU address vocabulary, not tied to one phrasing.
    "addr_ctx": (
        r"(?i)адрес|доставк|курьер|приехать|привез|проживает|прописк|получател|посылк"
        r"|живу|квартир|заберите"
    ),
    "prep_before": r"(?i)\b(?:на|по|в|у)\s+$",
    # Numbered street whose name word is lowercase ("1905 года 12") — the
    # capital-name path can't see it, so match the number + a known tail.
    "numbered_st": (
        r"(?i)(?:(?<=^)|(?<=[\s,;(]))(" + _NUM_NAME + r")"
        r"\s+(\d{1,3}[А-ЯЁа-яё]?(?:/\d+)?)(?![0-9A-Za-zА-Яа-яёЁ])"
    ),
    # Numbered street with the type marker present ("1905 года тупик") — the
    # street type makes it unambiguously an address (not "событие 1905 года"),
    # so the numbered NAME is masked too, not just the house number.
    "numbered_marked": (
        r"(?i)(?:(?<=^)|(?<=[\s,;(]))(" + _NUM_NAME + r")\s+" + _ST + r"\b"
        r"|\b" + _ST + r"\s*\.?\s*(" + _NUM_NAME + r")"
    ),
    # "т.д"/"т.п" must be the standalone abbreviation, not "т" inside "ст." etc.
    "neg": r"(?i)кв\.?\s*м|(?<![а-яёА-ЯЁ])т\.\s*[дпке]\b",
    # No (?i): separators only.
    "gap": r"[\s,.;\-/№#()]*",
    # No (?i) — deliberately. `[а-яё]` here is the lowercase letter that can
    # follow a house number ("12а"); made case-insensitive it would also swallow
    # the capital that starts the NEXT word.
    "trail_house": r"[\s,]+\d{1,4}[а-яё]?(?:/\d+)?\b",
}

# --- quasi-identifiers ---------------------------------------------------

BIRTH_CTX: tuple[str, ...] = ("рожд", "г.р", "г р", "родил", "д.р", "появил на свет")
MONTHS: tuple[str, ...] = (
    "января", "февраля", "марта", "апреля", "мая", "июня", "июля",
    "августа", "сентября", "октября", "ноября", "декабря",
)
# МКБ-10-style common diagnosis stems (inflection-tolerant via \w*).
# Two stems here cannot take a free `\w*` tail, and both were found on real
# text (NEREL, 933 documents): «рак» matched «ракета», «ракетного», «ракетой»,
# and «спид» matched «спидометр». Nineteen of the corpus's thirty-eight false
# positives were this one bug. They get an explicit inflection set instead.
MEDICAL_PATTERN = (
    # «гиперт» was the third instance of the free-tail trap the comment above
    # describes: it matched «гипертекста» in a sentence about HTTP. The stems
    # that are actually meant are «гипертония» and «гипертензия», and they need
    # one more letter each to stop being a prefix of an ordinary word.
    r"\b(?:диабет|гиперто\w*|гипертен\w*|астм|онколог|вич|туберкул|гепатит|депресс|"
    r"шизофрен|ковид|covid|инсульт|инфаркт|эпилепс|бронхит|пневмони|артрит|"
    r"гастрит|псориаз|деменци|аутизм|бесплоди)\w*"
    r"|\bрак(?:а|у|ом|е|ов\w*|овы\w*)?\b"
    r"|\bспид(?:а|у|ом|е)?\b"
)

# --- context suppression -------------------------------------------------

# Words that, directly before a number, mean it is NOT a phone — either a
# non-PII code (order/track/amount) or a DIFFERENT PII type handled by its own
# detector. Dropping the PHONE label is safe: it is either not PII, or the right
# detector already tagged it.
#
# The same list now also gates PASSPORT, which is the one identifier with NO
# checksum: `1234 567890` is a perfectly ordinary build number, part number or
# batch, and without a gate every one of them was masked. The second row exists
# for exactly that — a version string is the shape most likely to collide.
DENY: tuple[str, ...] = (
    "трек", "заказ", "артикул", "сумма", "руб", "чек", "талон", "sku", "№", "арт",
    "паспорт", "инн", "снилс", "счёт", "счет", "imei", "имей", "полис", "омс",
    "версия", "сборка", "ревизия", "билд", "партия", "накладная", "рейс",
    "гост", "ту", "серийный", "модель", "прошивка",
    # Document words that also govern a DATE: «наряд от 10.06.2025». Added when
    # AgentPII-RU showed the association gate masking every document date that
    # happened to share a sentence with the customer it belongs to.
    "наряд", "договор", "акт", "копия", "справк", "заявк", "обращени", "отчёт",
    "отчет", "квитанц", "смет", "приказ", "протокол",
)
# Words that, near a passport-shaped number, mean it really is a passport. The
# type has no checksum, so context is the only evidence there is.
PASSPORT_TRIGGER: tuple[str, ...] = (
    "паспорт", "пасспорт", "документ", "удостовер", "серия", "выдан",
    "предъявител",
)
PHONE_TRIGGER: tuple[str, ...] = (
    "тел", "моб", "звон", "ватсап", "whatsapp", "вайбер", "перезвон", "контакт",
)
# Region/country alone is never PII. A bare city is PII only when tied to a
# person (delivery/address/residence intent), not as a place reference.
REGIONS: tuple[str, ...] = (
    "россия", "рф", "область", "край", "республика", "округ", "регион",
    "сибирь", "урал", "поволжье", "кавказ", "подмосковье",
)
ADDR_INTENT: tuple[str, ...] = (
    "адрес", "доставк", "доставьте", "достав", "привез", "прописан",
    "проживает", "живу", "живёт", "живет", "заберите", "на улиц", "мне на",
    "мой адрес", "куда ехать", "забронир",
)
PLACE_REF: tuple[str, ...] = (
    "час", "режим", "филиал", "магазин", "офис", "находит", "погод",
    "курс", "работаете", "есть ли", "ближайш",
    # A delivery ZONE is a tariff, not somebody's address: «доставка по Москве
    # бесплатная от 3000» names a region of the price list. Masking it makes the
    # model answer about a city the customer does not ship to.
    "доставка по", "доставку по", "доставки по", "отправляем в", "возим в",
    "работаем по", "по всей", "зона доставки", "самовывоз",
)
VERSION_CTX: tuple[str, ...] = (
    "верси", "version", "сборк", "build", "релиз", "release", "v.",
)

# --- structured key->type ------------------------------------------------

KEY_TYPE: dict[str, str] = {
    "имя": "NAME", "фио": "NAME", "клиент": "NAME", "заказчик": "NAME",
    "получатель": "NAME", "name": "NAME",
    "телефон": "PHONE", "тел": "PHONE", "моб": "PHONE", "мобильный": "PHONE",
    "номертелефона": "PHONE", "phone": "PHONE", "контактныйтелефон": "PHONE",
    "снилс": "SNILS", "snils": "SNILS",
    "инн": "INN", "inn": "INN",
    "паспорт": "PASSPORT", "passport": "PASSPORT",
    "карта": "CARD", "карты": "CARD", "card": "CARD",
    "почта": "EMAIL", "email": "EMAIL", "мейл": "EMAIL", "емейл": "EMAIL",
    "адрес": "LOC", "address": "LOC",
    # A bank account has a 20-digit shape and no checksum, so outside a KEY it
    # is anchored to the cue words in CTX_TYPES. That left `{"account": …}`
    # unmasked while the same number after «счёт» was masked.
    #
    # ONLY THE UNAMBIGUOUS KEYS. A key here types the WHOLE value with no shape
    # check at all, so «счёт» and «реквизиты» must stay out however natural they
    # look: «счёт» is an invoice far more often than a bank account in Russian
    # business writing, and «Реквизиты:» introduces a LIST. Adding them cost 12
    # of 298 on the golden set immediately — «Реквизиты: СНИЛС 647-436-713 22,
    # карта …» typed the whole line as one account number and swallowed the
    # СНИЛС inside it. Those two words belong in CTX_TYPES, where the 20-digit
    # shape is what keeps an invoice number out.
    "account": "ACCOUNT", "accountnumber": "ACCOUNT",
    "рс": "ACCOUNT", "расчётныйсчёт": "ACCOUNT", "расчетныйсчет": "ACCOUNT",
    # Credentials named by their key. `detect_credentials` only finds what a
    # vendor stamped with a prefix; a bare `{"password": "qwerty123"}` has no
    # shape at all, and the KEY is the only evidence it is a secret.
    #
    # `auth`/`authorization` are deliberately ABSENT: matching is prefix-based,
    # so they would type `{"author": "Иванов"}` as a credential and replace a
    # person's name with a random token.
    "пароль": "SECRET", "пароля": "SECRET", "password": "SECRET",
    "passwd": "SECRET", "pwd": "SECRET",
    "токен": "SECRET", "token": "SECRET", "apikey": "SECRET",
    "secret": "SECRET", "секрет": "SECRET", "clientsecret": "SECRET",
    "accesskey": "SECRET", "accesstoken": "SECRET", "refreshtoken": "SECRET",
    "privatekey": "SECRET", "secretkey": "SECRET",
}

# --- context-anchored document types -------------------------------------

# (entity type, cue words, digit shape). Their digit shapes collide with each
# other and with ordinary business numbers: a driver's licence, a vehicle
# registration and a passport are all `NN NN NNNNNN`. The cue word is what makes
# the type — and the type matters, not just the masking: mistyping a licence as a
# phone replaces it with a fake PHONE.
CTX_TYPES: tuple[tuple[str, str, str], ...] = (
    ("OMS", r"омс|полис", r"\d{16}"),
    # «реквизиты» belongs here and not only among the KV keys: the KV layer needs
    # a `key: value` shape, and a customer writing prose puts the word and the
    # number a space apart. Persona 1 produced both in ONE sentence — «счёт
    # 4081…, реквизиты 4081…» — and watched the same value be masked once and
    # leak once.
    ("ACCOUNT", r"счёт|счет|р/с|расчётн\w*|расчетн\w*|реквизит\w*", r"\d{20}"),
    ("DRIVER_LICENSE", r"водительск\w*|в/у|удостоверени\w* водител\w*|прав[аои]",
     r"\d{2}\s?\d{2}\s?\d{6}"),
    ("VEHICLE_DOC", r"стс|птс|свидетельств\w* о регистрации", r"\d{2}\s?\d{2}\s?\d{6}"),
    # Two digits of series, seven of number. The separator is OPTIONAL and was
    # missing: `\d{9}` matched only `711234567`, while the form actually printed
    # in the document and typed by people — `71 1234567` — went undetected. The
    # sibling document patterns above always allowed `\s?` between groups; this
    # one did not, and nothing tested the spaced form.
    ("INTL_PASSPORT", r"загранпаспорт\w*|заграничн\w* паспорт\w*", r"\d{2}\s?\d{7}"),
)
# Context words that upgrade a weak INN-10 into a real one. INN-10 has a single
# check digit (~10% of random 10-digit numbers pass), so the checksum alone is
# not enough to separate it from an order number.
INN_CONTEXT: tuple[str, ...] = ("инн", "контрагент", "налогоплательщ", "реквизит")

# --- overlap priority ----------------------------------------------------

# Higher = more trusted; wins overlaps. Checksum-validated IDs outrank phone so
# a valid INN/СНИЛС/card is never mislabeled as a bare phone. A marker/house
# anchored ADDR span must beat a NAME sitting inside it (the street name), so the
# whole address — incl. the house number — is masked, not just the surname.
PRIORITY: dict[str, int] = {
    # Top slot, above the checksum IDs. A Slack token holds a long digit run
    # that libphonenumber reads as a phone, and a JWT body is base64 that can
    # contain anything. A lower-priority recogniser winning a SUB-span of a
    # credential cuts it in half, and both halves then leak.
    "SECRET": 8,
    "OMS": 7, "ACCOUNT": 7, "DRIVER_LICENSE": 7, "VEHICLE_DOC": 7,
    "INTL_PASSPORT": 7, "OGRN": 7, "BIRTH_CERT": 7,
    "SNILS": 6, "INN": 6, "CARD": 6, "VIN": 6,
    "MAC": 5,
    "PHONE": 5, "EMAIL": 5, "IP": 5, "PLATE": 5, "ADDR": 4,
    "NAME": 3, "DATE": 2, "PASSPORT": 2, "LOC": 2,
}

# --- normalization -------------------------------------------------------

# Cyrillic / Greek / Latin glyphs that look like digits.
#
# WRITTEN AS ESCAPES ON PURPOSE. As literals these characters are visually
# identical to each other, and the table shipped with Cyrillic 'о' (U+043E)
# entered TWICE while Greek small omicron (U+03BF) was missing entirely — a
# silent dict overwrite that no reader could see. The cost was real: `+7 9ο9
# 123-45-67` written with the Greek letter never folded to digits, the run never
# reached five digits, and the phone went to the model unmasked.
LOOKALIKE: dict[str, str] = {
    "О": "0",  # CYRILLIC CAPITAL O
    "о": "0",  # CYRILLIC SMALL O
    "O": "0",  # LATIN CAPITAL O
    "o": "0",  # LATIN SMALL O
    "Ο": "0",  # GREEK CAPITAL OMICRON
    "ο": "0",  # GREEK SMALL OMICRON  <- was missing
    "З": "3",  # CYRILLIC CAPITAL ZE
    "з": "3",  # CYRILLIC SMALL ZE
    "б": "6",  # CYRILLIC SMALL BE
    "Б": "6",  # CYRILLIC CAPITAL BE
    "Ч": "4",  # CYRILLIC CAPITAL CHE
    "ч": "4",  # CYRILLIC SMALL CHE
    "I": "1",  # LATIN CAPITAL I
    "l": "1",  # LATIN SMALL L
    "І": "1",  # CYRILLIC CAPITAL BYELORUSSIAN-UKRAINIAN I
    "і": "1",  # CYRILLIC SMALL BYELORUSSIAN-UKRAINIAN I
    "B": "8",  # LATIN CAPITAL B
    "В": "8",  # CYRILLIC CAPITAL VE
}
