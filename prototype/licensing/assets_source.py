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

# HOW MUCH OF ГАР IS WORTH LEASING: a name is kept when at least this many
# streets in Russia carry it. ONE, i.e. all of it — and the measurement that
# says so also says why the obvious answer was wrong.
#
# The expectation was that the tail is the dangerous half: 165 672 names, most
# of them naming one street in one village, and a vocabulary is a GATE, so the
# fewer entries the less of the language walks through it. The frequency curve
# looked like it would pay for that — the top 4 559 names already cover 72.2%
# of every street in Russia against 81.2% for all 65 799 single-word ones.
#
# It is exactly backwards. The share of entries pymorphy3 calls an ordinary word
# RISES as you cut: 22.9% at no cut, 65.1% at twelve. The commonest street names
# in Russia ARE ordinary words — центральная, лесная, новая, садовая, школьная,
# полевая — so a frequency cut concentrates the risk instead of removing it.
# Precision here cannot come from the vocabulary's size, and does not: it comes
# from the conjunction in `_fuzzy_street_candidates`.
#
# The tail is then nearly free and worth having. Measured on 400 sampled tail
# names in the register this exists for — a typo in the type word, and a marked
# street with no house number — cut 12 scored 0% and 66%, cut 1 scored 90% and
# 90%. Nothing moved on the precision side between the two: NEREL 99.4% with the
# same 121 unsupported spans, `test_overmasking` 100%, 4 778 hits over 2 691
# sentences of news prose, identical. The whole cost is 249 KB of compressed
# bundle.
#
# Kept as a knob rather than deleted: if a future measurement finds a corpus
# where the tail does cost precision, this is the one line that answers it.
STREET_MIN_OBJECTS = 1

# --- street types, as STEMS, for the typo-tolerant arm --------------------
#
# The regex arms below carry their own copies of these words, and that is
# deliberate rather than an oversight: each of those patterns has a tuned shape
# around the word (a mandatory dot, a case flag, a house number) and rewriting
# them from one list would undo the tuning. These two tuples exist for
# `_fuzzy_street_candidates`, which does not match with a regex at all — it
# compares a TOKEN against a stem, so it can tolerate a typo and can read a type
# word the regexes never learned.
#
# TWO TIERS, THE SAME SPLIT THE REGEXES ALREADY MAKE. A type word that may
# stand with no house number is one whose only ordinary meaning is a street;
# everything else needs the house number to hold it down, exactly as
# `street_lower_nohouse` and `_ST_FULL` divide them. «съезд» is a party
# congress, «квартал» is a reporting period, «линия» is a cable, «тупик» is
# where negotiations end — each of them is also a ГАР street type, and the
# house number is what tells the two apart.
STREET_TYPE_NOHOUSE: tuple[str, ...] = (
    "улиц", "проспект", "переул", "бульвар", "набережн", "шоссе", "микрорайон",
    "алле",
)
# EVERY ГАР TYPE AT LEVEL 8 THAT NAMES A STREET, and this is where the register
# pays for itself: the engine knew twelve of the forty-two and had never heard of
# «тракт», «спуск», «съезд», «квартал», «линия», «сквер», «территория»,
# «магистраль» or «взвоз». They are not exotic — they are how a третья часть of
# provincial Russia writes its addresses.
#
# ГАР types that are a SETTLEMENT rather than a street (деревня, село, посёлок,
# хутор, станция) are absent: `settlement` and `rural` already own those, and
# adding them here would give one shape two owners. So are the ones whose word
# is ordinary Russian with no street reading a customer would write — «парк»,
# «сад», «зона», «берег», «мост», «остров», «коса», «ряд», «участок»,
# «местность», «километр». Each of those would need the house number AND a
# vocabulary hit to fire, but «дорога» shows why that is not enough on its own:
# the stem also spells «дорогой», and a cheerful letter is not an address.
STREET_TYPE_HOUSE: tuple[str, ...] = STREET_TYPE_NOHOUSE + (
    "площад", "проезд", "тупик", "лини", "квартал", "тракт", "спуск", "съезд",
    "заезд", "въезд", "разъезд", "переезд", "магистрал", "сквер", "кольцо",
    "просек", "просёлок", "проселок", "проулок", "взвоз", "слобод",
    "территори", "площадк",
    # «дорог» ОТСУТСТВОВАЛ, и это стоило ложного адреса. ГАР использует «дорога»
    # как тип улицы, а у нас его в списке не было — поэтому слово попадало в
    # словарь НАЗВАНИЙ (там есть улицы, буквально названные «Дорога») и
    # безмаркерная ветка читала «на дороге семьдесят» как улицу «дороге» с домом
    # семьдесят. Поймано набором над-маскирования в тот час, когда он вырос с
    # сорока двух фраз до пятисот тридцати восьми, на предложении про дорожные
    # работы — тексте, которого ни один наш набор до сих пор не содержал.
    "дорог",
)

# Tails of numbered streets ("улица 1905 года", "8 марта"): generic RU pattern.
NUMBERED_TAIL: tuple[str, ...] = (
    "года", "год", "лет", "марта", "мая", "января", "февраля", "апреля", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря", "партсъезда",
)

# Street type markers (used marker-first AND marker-last); each only fires next
# to a Capitalized name, so a bare "пл"/"пр" can't match.
_ST = (
    # «пр.» С ОБЯЗАТЕЛЬНОЙ ТОЧКОЙ. Голое «пр» — начало «при», «про», «пример»,
    # и пускать его нельзя; с точкой это только «проспект» или «проезд».
    # Без него «г. Казань, пр. Победы 45» распадалось надвое: город находился
    # сам по себе, «Победы 45» — маркерless-веткой, а «, пр. » между ними не
    # схлопывалось (шесть символов, и буквы внутри), так что до модели уходил
    # кусок адреса. Найдено на PII-Bench: покрытие ADDRESS 41.5% при полноте 88.6.
    r"(?:улиц\w+|ул\.?|проспект\w*|просп\.?|пр\.|пр-?кт\.?|пр-?т\.?|переул\w+|пер\.?"
    r"|проезд\w*|пр-д|бульвар\w*|б-р|набережн\w+|наб\.?|шоссе|ш\.|площад\w+|пл\.?"
    r"|тупик\w*|туп\.?|алле\w+|лини\w+|квартал\w*|кв-л|тракт\w*|просек\w*)"
)
# The street/settlement markers above are case-insensitive (ул/Ул), but the NAME
# must be truly Capitalized — `(?-i:...)` keeps the capital case-sensitive even
# inside an IGNORECASE pattern, so "пер" in "перезвоните" can't grab a lowercase
# tail and "площадью 5 кв" can't pass as a street.
_NAME = r"(?-i:[А-ЯЁ])[а-яё]+(?:[\s-](?-i:[А-ЯЁ])[а-яё]+){0,2}"
_CAP = r"(?:\d+[-\s]?[а-яё]{0,2}\s+)?" + _NAME
# A TOOL RESULT ARRIVES AS JSON, AND JSON PUTS A QUOTE WHERE PROSE PUTS A SPACE.
# The left-context set held whitespace, comma, semicolon, paren, № and #, so
# «"addr": "г. Пермь, ул. Добролюбова, д. 154б"» lost its «г. » and
# «{"a": "д. 12, кв. 5"}» was not found at all — the same string is found the
# moment the quote is removed. That leg is where personal data arrives from the
# customer's OWN systems, so it is the last place a delimiter should decide
# whether an address exists. Quotes, brackets and the `=`/`:` of a key-value
# line join the set; letters and the period deliberately do not, which is what
# still keeps «т.д» out.
_TOK = r"(?:(?<=^)|(?<=[\s,;(№#\"'«»\[\]{}<>=:|/\\]))"
# The apartment marker may be GLUED TO THE HOUSE NUMBER, and in real Russian
# addresses it usually is: «д.5кв12», «Строителей 53к193», «Гагарина88кв152».
# `_TOK` alone requires whitespace before the marker, so the flat number simply
# fell outside the span — the street and house were masked and the apartment
# went to the model in the clear, inside an address that now mixed a fake street
# with a real flat.
#
# «кв» after a digit stays safe because the pattern demands DIGITS AFTER the
# marker: «100кв.м» (square metres) has «м» there and still does not match.
_TOK_OR_DIGIT = r"(?:(?<=^)|(?<=[\s,;(№#\"'«»\[\]{}<>=:|/\\])|(?<=\d))"
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
# `№` IS A HOUSE MARKER AND WAS MISSING. Measured on the metamorphic instrument:
# rewriting «д. 14» as «№ 14» kept polnota at 100% and dropped COVERAGE to 0% —
# the street matched every time and the house number never joined the span, so
# it went to the model in the clear while the number said the address was found.
# A defect that only a coverage column can see, which is why that column exists.
_HOUSE_LEAD = r"(?:\s*,?\s*(?:дом|д)\.?|\s*,?\s*№)?\s*"

# THE HOUSE NUMBER, SPOKEN. A call transcript writes «тридцать восемь», not «38»,
# and every address pattern demanded `\d` — so on seven verbatim utterances from
# real Russian phone calls the detector found NOTHING, while the same addresses
# with digits were found every time. The register our own corpus calls «voice»
# asserted that «ASR normalises digits»; two speech corpora say otherwise (in 500
# Golos transcripts: zero digits, 21% spelled-out numbers).
#
# BOUNDED AT NINE HUNDRED AND NINETY-NINE, AND THE NINETY-NINE IT REPLACES WAS
# WRONG ABOUT FLATS. The bound was argued as "house and flat numbers above that
# are vanishingly rare" — true of houses, false of flats: a Russian tower block
# numbers its flats into the hundreds as a matter of course, and the corpus said
# so on the first real call it was measured against. «квартира двести двадцать
# девять» matched «две» — the prefix of «двести» — so the span ended three words
# early and the rest of the flat number went to the model in the clear.
#
# The prefix is why this is one alternation and not a longer list: «два» is a
# prefix of «двести», «три» of «тридцать», «пять» of «пятьсот». Ordering the
# alternation from the longest class down and closing it with `\b` is what makes
# the match the WHOLE numeral rather than its first syllable.
#
# USED ONLY WHERE A STREET-TYPE WORD OR A MARKER IS PRESENT. In the marker-less
# arms there would be nothing holding it down, and «на улице минус десять» — the
# commonest shape in real consumer traffic — would become an address.
_HUNDREDS = (r"(?:сто|двести|триста|четыреста|пятьсот|шестьсот|семьсот"
             r"|восемьсот|девятьсот)")
_TEENS = (r"(?:одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать"
          r"|шестнадцать|семнадцать|восемнадцать|девятнадцать|десять)")
_TENS = (r"(?:двадцать|тридцать|сорок|пятьдесят|шестьдесят|семьдесят"
         r"|восемьдесят|девяносто)")
_UNITS = r"(?:один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять)"
# ONE number word, for the places that have to REFUSE one — `_LOWER_NAME_NONUM`
# needs to know that a street name may not BE a numeral, and it asks this.
_SPELLED = rf"(?:{_HUNDREDS}|{_TEENS}|{_TENS}|{_UNITS})"
_UNDER_HUNDRED = rf"(?:{_TEENS}|{_TENS}(?:\s+{_UNITS})?|{_UNITS})"
_SPELLED_CARD = rf"(?:{_HUNDREDS}(?:\s+{_UNDER_HUNDRED})?|{_UNDER_HUNDRED})\b"
# «два дробь восемь» is 2/8, and the digit arms have carried `(?:/\d+)?` since
# the beginning — spoken, the slash is a word and the arm stopped in the middle
# of the house number. A fraction needs a numeral on BOTH sides, which is what
# keeps «дробь» — also birdshot, also a drum roll — from opening anything.
_SPELLED_NUM = rf"{_SPELLED_CARD}(?:\s+дроб[ьи]\s+{_SPELLED_CARD})?"
# ПОРЯДКОВЫЕ ЧИСЛА, потому что этаж и подъезд называют ими, а не количественными:
# «этаж четвёртый», «подъезд третий», «на втором». Без них цепочка обрывалась на
# предыдущем маркере и этаж оставался снаружи спана.
_ORDINAL = (r"(?:перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|десят"
            r"|одиннадцат|двенадцат|тринадцат|четырнадцат|пятнадцат|шестнадцат"
            r"|семнадцат|восемнадцат|девятнадцат|двадцат|тридцат)\w{2,3}")

# Каждое слово, которым русский адрес отделяет одну свою часть от следующей.
# Оно нужно в трёх местах — цепочка, хвост цепочки и литера дома, — и раньше
# перечислялось в каждом заново, поэтому «строение» стояло в одном списке и не
# стояло в другом.
_CHAIN_MARKER = (r"(?:дом|корпус\w*|корп|кор|квартир\w*|кв|строени\w*|стр"
                 r"|под[ъь]езд\w*|этаж\w*|офис\w*|помещени\w*|литер\w*)")

# ЛИТЕРА ДОМА ЗАКАНЧИВАЕТ АДРЕС ИЛИ ПЕРЕДАЁТ СЛЕДУЮЩЕМУ МАРКЕРУ, и без этого
# условия она съедала обычное слово. «этаж четвёртый я у вас так и быть куплю» —
# «я» уходило в спан как литера, потому что правило спрашивало только «одна
# буква, и за ней не тянется слово». Ровно те же буквы и есть литеры: «двадцать
# пять А», «дом семнадцать В» — обе из настоящих звонков.
#
# Различает их не буква, а то, что стоит справа. Литера — последнее слово
# адреса либо стык с «корпус»/«квартира»; союз «а» и местоимение «я» всегда
# тянут за собой продолжение фразы. Поэтому проверяется хвост, а не список
# допустимых букв: список пришлось бы держать в согласии с ГАР, а хвост —
# свойство самой речи.
# ПОДЪЕЗД НАЗЫВАЮТ ПОРЯДКОВЫМ, И ОНО СТОИТ ПЕРЕД МАРКЕРОМ. «первый подъезд»,
# «второй подъезд», «последний подъезд», «угловой подъезд» — так говорит живая
# диспетчерская речь, а все наши маркерные ветки ждут «подъезд первый». На 400
# размеченных репликах такси это 73 обрезки из 156 адресов: улица с номером
# находилась, а подъезд оставался снаружи спана и уходил в модель.
_ENTRANCE = (r"(?:" + _ORDINAL + r"|последн\w+|крайн\w+|углов\w+)\s*"
             r"(?:подъезд\w*|корпус\w*|этаж\w*|дом)")

# ЛИТЕРА ДОМА — ОДНА БУКВА, И ЗАПРЕЩЕНА ТОЛЬКО «Я». Прежде здесь стоял просмотр
# вперёд: буква принималась лишь в конце фразы, перед знаком или перед
# маркером. На настоящей речи за литерой идёт обычное слово — «сто тридцать
# восемь **а** поедем на энгельса», «семьдесят два **а** магазин», — и правило
# резало номер дома у каждого третьего адреса.
#
# Единственный измеренный вред был «этаж четвёртый **я** у вас так и быть
# куплю»: местоимение, принятое за литеру. «я» и есть та буква, которой в
# нумерации домов не бывает — ГАР ведёт литеры от «а» вглубь алфавита, а «я» в
# русском тексте почти всегда местоимение. Запрет на одну букву честнее
# просмотра вперёд, который запрещал форму, а не то, что ломалось.
_LITERA = r"(?:\s+(?![яЯ](?![а-яё]))[а-яё](?![а-яё]))?"

# НАЗВАНИЕ УЛИЦЫ НЕ ИМЕЕТ ПРАВА СЪЕСТЬ ЧИСЛИТЕЛЬНОЕ. `_LOWER_NAME` берёт до трёх
# слов подряд, и в «улицу культуры восемь» оно забирало «культуры восемь»
# целиком — номеру дома не оставалось ничего, и адрес не находился. С цифрой
# этого не бывает: цифра под шаблон названия не подходит, поэтому дефект жил
# только в голосовом регистре, где номер и есть слово.
_LOWER_NAME_NONUM = (r"(?!" + _SPELLED + r"\b)[а-яё]{3,}"
                     r"(?:[\s-](?!" + _SPELLED + r"\b)[а-яё]{3,}){0,2}")

_HOUSE_NUM = rf"(?:\d{{1,4}}(?!\d)|{_SPELLED_NUM})"

# A TRAILING ABBREVIATED MARKER. `_ST_ABBR` requires a dot or space AFTER it, so
# it can only stand BEFORE the name — «пр-кт Ленинский 55» matched and «Ленинский
# пр-кт 55» did not, because the name-first arm uses `_ST_FULL`, which excludes
# abbreviations by design. Russian writes the type after the name at least as
# often. Measured: abbreviating the marker cost 19% of addresses outright.
# WHITESPACE IS REQUIRED BEFORE IT, and that is the mirror of the rule that
# guards `_ST_ABBR`. There the abbreviation must be FOLLOWED by a dot or a
# space so «улыбка 14» cannot read as «ул» + «ыбка»; here it must be PRECEDED
# by one, because «ул» also ENDS ordinary Russian words — артикул, аул,
# караул. Allowing the glued form for one commit turned «Артикул 2024/117,
# партия 445» and «караул 12» into addresses; `test_overmasking.py` caught the
# first on the next run. A FULL type word may still be glued
# (`street_lower_last` uses `\s*`): «проспект» cannot end a Russian word, a
# two-letter abbreviation can.

_ST_ABBR_LAST = r"\s+(?:ул|просп|пр-?кт|пр-?т|пер|наб|б-р|пл)\.?"
# ABBREVIATED MARKER + LOWER-CASE NAME. `_ST_FULL` deliberately excludes the
# abbreviations because a bare «пр» or «ул» in prose has nothing holding it
# down — but in THIS shape the house number holds it down, exactly as it does
# for the full words. Without this «ул ленина 14» and «ул. ленина 14» matched
# nothing at all while «улица ленина 14» matched: the customer who abbreviates
# — which is most of them — was unprotected, and the inconsistency was
# invisible because our sets write the word out.
#
# Two rules keep it narrow. The abbreviation must be followed by a DOT OR
# SPACE, so «улыбка 14» cannot read as «ул» + «ыбка»; and only abbreviations
# that are not a Russian word in their own right are listed — «туп» (short
# adjective) and the single letters «ш», «д» are left out, since for those the
# house number is the only thing standing between them and ordinary prose.
_ST_ABBR = r"(?:ул|просп|пр-?кт|пр-?т|пер|наб|б-р|пл)(?:\.\s*|\s+)"
# Street types that may stand with NO house number. See `street_lower_nohouse`.
_ST_NOHOUSE = (r"(?:улиц\w+|проспект\w*|переул\w+|бульвар\w*|набережн\w+|шоссе"
               r"|микрорайон\w*|алле\w+)")

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
    # THE HOUSE NUMBER MUST END WHERE THE MATCH DOES. Without `(?!\d)` the arm
    # took the first four digits of a PHONE for a house: «на тверской улице
    # телефон 8104332-18-19», written without the comma a chat drops, matched
    # «улице телефон 8104». That span then overlapped the phone, lost the
    # priority contest to it (PHONE 5 > ADDR 4) and took the real street down
    # with it — so removing punctuation made an address that WAS detected
    # disappear entirely.
    "street_lower_first": rf"(?i)\b{_ST_FULL}\s*{_LOWER_NAME}{_HOUSE_LEAD}\d{{1,4}}(?!\d)",
    "street_lower_last": rf"(?i)\b{_LOWER_NAME}\s*{_ST_FULL}{_HOUSE_LEAD}\d{{1,4}}(?!\d)",
    "street_abbr_lower": rf"(?i)\b{_ST_ABBR}{_LOWER_NAME}{_HOUSE_LEAD}\d{{1,4}}(?!\d)",
    # The same shape with the abbreviation AFTER the name — see `_ST_ABBR_LAST`.
    "street_abbr_lower_last": rf"(?i)\b{_LOWER_NAME}{_ST_ABBR_LAST}{_HOUSE_LEAD}\d{{1,4}}(?!\d)",
    # THE HOUSE NUMBER SPOKEN — a SEPARATE arm, and gated in the engine.
    # Folding `_SPELLED_NUM` into the arms above was measured and rejected: it
    # found all seven verbatim call transcripts AND turned «на улице минус
    # десять», «на улице плюс тридцать», «площадь сто двадцать квадратных
    # метров» and «проспект был построен сорок лет назад» into addresses —
    # four of nine ordinary sentences. A digit after a street type is rare in
    # prose and holds the match down by itself; a number WORD is an ordinary
    # Russian word and holds nothing. So the street name carries the proof
    # instead: `spoken` is admitted only when the leased vocabulary names it,
    # the same rule and the same reason as `markerless_lower`.
    "street_spoken_first": rf"(?i)\b{_ST_FULL}\s*(?P<sfirst>{_LOWER_NAME_NONUM}){_HOUSE_LEAD}{_SPELLED_NUM}{_LITERA}",
    "street_spoken_last": rf"(?i)\b(?P<slast>{_LOWER_NAME_NONUM})\s*{_ST_FULL}{_HOUSE_LEAD}{_SPELLED_NUM}{_LITERA}",
    # A MARKED STREET WITH NO HOUSE NUMBER, IN LOWER CASE. «на тверской улице»
    # and «на проспекте мира» were invisible: the capitalised arm needs its
    # capital and the two arms above need a house number. Every one of the 46
    # values the noise ladder loses at the lower-case rung is a LOC, and these
    # are the half of them that is not a bare city.
    #
    # The house number is what makes the OTHER lower-case arms safe, so with it
    # gone the gate moves into the engine: the name must be a word that can name
    # a street — see `_lower_names_a_street`. Matching «улица» plus any
    # lower-case word is what turns «улица была пустой» into an address, and
    # that is the counterexample the gate is built against.
    # «площад» IS ABSENT HERE and present in every other arm. With a house number
    # beside it, «площадь Ленина 3» is unambiguous; without one, `площад\w+`
    # matches «площадка», «площади», «площадью» and «площадных», which is
    # ordinary business and news vocabulary — «торговая площадка», «посевные
    # площади», «сценические площадки». Measured on NEREL: it was most of the
    # noise this arm produced.
    # THE MARKER-LAST BRANCH MAY NOT EAT THE MARKER, and it may not eat three
    # words. Both halves of that were one bug: alternation in Python picks the
    # EARLIEST position, not the preferred branch, so in «адрес москве проспекте
    # мира» the marker-last branch matched «адрес москве проспекте» first —
    # three words, the cue word among them — and `finditer` then resumed past
    # «проспекте», so «мира» was never looked at. The cue gate reads the text
    # BEFORE the match, and «адрес» was now inside it, so the whole address was
    # refused and the street went to the model in the clear. Ten of the noise
    # ladder's fourteen street values at the no-punctuation rung died exactly
    # there — the same «a cue licenses its neighbour, it does not name it»
    # lesson `markerless_lower` already learned, on the other pattern.
    #
    # A lookahead instead of a match: the marker is left unconsumed, so the
    # marker-FIRST branch fires on it in the same scan and the two adjacent
    # candidates merge into «москве проспекте мира». One word instead of three,
    # because the marker-last form people actually write is «тверской улице».
    "street_lower_nohouse": (rf"(?i)\b(?:{_ST_NOHOUSE}\s+(?P<after>{_LOWER_NAME})\b"
                            rf"|(?P<before>[а-яё]{{3,}})\s+(?={_ST_NOHOUSE}\b))"),
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
    # «строение» и «подъезд» дописаны, и буква после номера тоже: «офис 12А»
    # оставлял «А» снаружи спана, а «стр. 3» и «подъезд 4» не попадали вовсе —
    # адрес маскировался, а его хвост уходил в модель.
    #
    # «подьезд» через «ь» — не опечатка корпуса, а то, как это слово пишут: в
    # PII-Bench оно встречается наравне с правильным. Сокращённое «под» и «эт»
    # тоже: «ул. Кирова 12 под 1 кв 300» — обычная строка адреса, и без них
    # номер подъезда уходил в модель внутри уже замаскированного адреса.
    #
    # «стр» опасно только на вид: это ещё и «страница». Здесь это безвредно,
    # потому что вся ветка — SUPPORT: она считается лишь слитой с ядром адреса,
    # так что «см. стр. 5» рядом с которым нет улицы, не маскирует ничего.
    "apt": (r"(?i)(?:" + _TOK_OR_DIGIT
            + r"(?:квартир\w*|кв|офис\w*|оф|помещени\w*|пом|комнат\w*|комн"
              r"|корпус\w*|корп|кор|строени\w*|стр|под[ъь]езд\w*|под|этаж\w*|эт)\.?\s*\d+[а-яёА-ЯЁ]?"
            + r"|(?<=\d)к\s*\d+)"),
    # ХВОСТ АДРЕСА, СКАЗАННЫЙ СЛОВАМИ. `apt` требует `\d+`, поэтому «улица
    # дербенёвская двадцать четыре строение пять» маскировалась по «четыре», а
    # строение уходило в модель внутри уже найденного адреса — ровно тот разрыв
    # между полнотой и покрытием, ради которого вторая колонка и заведена.
    # Четыре обрезки из шести в голосовом наборе — это она.
    #
    # SUPPORT, как и `apt`, и по той же причине: одного маркера со словесным
    # номером мало, чтобы маскировать («программу дом два» — телепередача, и она
    # в нашем же негативном наборе). Слитый с ядром адреса он безопасен, сам по
    # себе отбрасывается.
    #
    # «дом» в списке нет намеренно. Это самый неоднозначный из маркеров, цепочка
    # из двух его уже берёт, и отдельной поддержкой он добавил бы риск ровно
    # там, где выигрыша не измерено.
    "spoken_apt": (r"(?i)" + _TOK + r"(?:"
                   + r"(?:квартир\w*|кв|офис\w*|помещени\w*|комнат\w*"
                     r"|корпус\w*|корп|кор|строени\w*|стр|под[ъь]езд\w*|этаж\w*)"
                     r"\.?\s*"
                   + r"(?:" + _SPELLED_NUM + _LITERA + r"|" + _ORDINAL + r")"
                   + r"|" + _ENTRANCE + r")"),
    # THE ABBREVIATION NEEDS A DOT OR A SPACE, and the name half must not be
    # case-folded. «мкр» opens ordinary words — «мкртчян» is a surname — and with
    # `(?i)` applied to the whole pattern `[А-ЯЁ][а-яё]+` stopped meaning «a
    # Capitalised word» and started meaning «any word», which is the trap
    # CLAUDE.md records costing 12 real people on NEREL. Together they turned the
    # misspelt surname «мкртчн» into a микрорайон: «мкр» + «тчн». Same shape as
    # «Артикул» reading as «Артик» + «ул», and the same fix — the marker may not
    # be glued to the word it is cutting out of.
    "mkr": (r"\b(?:[Мм]икрорайон\w*|[Мм]крн|[Мм]кр)(?:\.\s*|\s+)"
            r"(?:[А-ЯЁ][а-яё]+|\d+[а-яё]?)"),
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
    # РЕГИОН ведёт адрес чаще, чем район: «Московская обл, Одинцово, Парковая 7»
    # и «Московская область, г. Химки, ул. Победы 12» теряли первое слово, то
    # есть до модели доходило, В КАКОМ РЕГИОНЕ живёт человек, чей адрес мы
    # только что закрыли. Как и район — SUPPORT: голая «Московская область»
    # никого не идентифицирует и сама по себе не маскируется.
    "district": (
        r"(?i)(?-i:[А-ЯЁ])[а-яё]+(?:ый|ий|ое|ая)?\s*"
        r"(?:район\w*|р-н|област\w*|\bобл\.?|\bкра[йея]\b|республик\w*|\bресп\.?"
        r"|городско\w+\s+поселени\w+|сельско\w+\s+поселени\w+"
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
    # MARKER-LESS STREET WRITTEN IN LOWER CASE — «вы находитесь на ленина 14?».
    # The pattern above cannot see it: it spells the name `[А-ЯЁ][а-яё]+`, and
    # that capital is one of its two signals. Compiling that same pattern
    # case-insensitively is the change that cost -12 PERSON on NEREL, because
    # then «течение 12» and «Вашингтоне за 8» are addresses too.
    #
    # So this is a SEPARATE pattern with a DIFFERENT gate, not a relaxed flag.
    # Where the capitalised arm accepts a morphological signal (Surn / ADJF /
    # Geox) as its second signal, this one accepts ONLY explicit membership in
    # the leased street vocabulary — see `_lower_is_street` in address.py.
    # Morphology is what admits «течение»; a vocabulary cannot, because the word
    # is not in it. That asymmetry is the whole point: a capital is evidence, and
    # when it is absent the evidence has to come from somewhere that cannot
    # generalise.
    # ONE WORD, not up to three. The multi-word form is what let ordinary prose
    # in: «в конце марта 55» and «в виде лишения свободы 2» both start at a word
    # that merely FOLLOWS a preposition, and the street vocabulary hit sat at the
    # far end of the span. It also swallowed the cue word it needs — «адрес мира
    # 5» matched from «адрес», leaving no «адрес» in front to be the context.
    # A marker-less lower-case street is «ленина 14»; the multi-word case is
    # «карла маркса 5», and that one still has its capitals in every register
    # where anybody writes it.
    "markerless_lower": (
        r"(?:(?<=^)|(?<=[\s,;(]))"
        r"(?P<lwords>[а-яё]{4,}(?:-[а-яё]{3,})?)"
        r"\s*,?\s*(?:дом|д)?\.?\s*"
        r"(\d{1,3}[А-ЯЁа-яё]?(?:/\d+)?)(?![0-9A-Za-zА-Яа-яёЁ])"
    ),
    # Address context (Presidio-style enhancement): when nearby, a marker-less
    # Capitalized/numbered "name + house" is accepted even with no morphology
    # signal. Universal RU address vocabulary, not tied to one phrasing.
    # THE SPOKEN HALF WAS MISSING. This vocabulary was collected from written
    # traffic — «адрес», «доставка», «проживает» — and on real call transcripts
    # it left the largest single failure class: 13 of 17 missed addresses were a
    # street with no house number, and almost all of them were somebody DICTATING
    # one. «записывай давай улица пушкина», «я ж тебе сказал улица пушкина»,
    # «милашекова улицу знаешь приезжай туда». The intent is unmistakable and
    # none of the written words appear.
    #
    # Added only verbs that mean an address is being GIVEN or USED. «назови» and
    # «скажете» were considered and rejected — «назови улицу» and «если вы
    # скажете улицу я вам скажу номер телефона» are both in the same corpus and
    # both are questions, not addresses. The line is between naming a street and
    # handing one over.
    "addr_ctx": (
        r"(?i)адрес|доставк|курьер|приехать|привез|проживает|прописк|получател|посылк"
        r"|живу|квартир|заберите"
        r"|записыв|записал|продикту|диктую|подъезж|подъехать|приезжай|приедь"
        r"|отвез|отвезти|забер|находится\s+по"
    ),
    # THE HOUSE NUMBER SPOKEN, IN A CHAIN. `house` and `apt` both demand `\d+`,
    # so «дом двадцать пять а корпус два квартира двадцать семь этаж четвёртый»
    # — a complete address minus the street, dictated over the telephone —
    # matched nothing at all.
    #
    # TWO MARKERS MINIMUM, and that is the whole safety argument. One marker with
    # a spoken number is genuinely ambiguous: «программу дом два очень почётно»
    # is a television show and it is in our own negative set, «дом пять» could be
    # either. A CHAIN is not: nobody says «дом двадцать пять корпус два» about
    # anything but a building. The markers carry the proof, so the numbers may be
    # words — which is the opposite of the street arms, where the number is the
    # anchor and a word cannot be one.
    #
    # Digits are admitted alongside words because speech mixes them the moment a
    # transcriber normalises half of them: «дом 25 корпус два» is what a real
    # transcript looks like.
    # НОМЕР ДОМА МОЖЕТ СТОЯТЬ ДО ПЕРВОГО МАРКЕРА, и в живой речи он там и
    # стоит: «так двадцать пять а корпус два квартира двадцать семь». Слово
    # «дом» опускают, потому что курьер и так знает, о чём речь, — и цепочка
    # начиналась с «корпус», оставляя номер дома снаружи. Число берётся только
    # вплотную к цепочке, а цепочка по-прежнему сама себе доказательство: одно
    # число впереди двух маркеров ничего не открывает.
    "spoken_chain": (
        r"(?i)(?:(?<![А-Яа-яЁё])(?:\d{1,4}|" + _SPELLED_NUM + r")"
        + _LITERA + r"\s+)?"
        r"(?:\b" + _CHAIN_MARKER + r"\.?\s*"
        r"(?:(?:\d{1,4}|" + _SPELLED_NUM + r")" + _LITERA
        + r"|" + _ORDINAL + r")"
        r"\s*){2,}"
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
    # A UNIT OF MEASURE AFTER A NUMBER MEANS THE NUMBER IS NOT A HOUSE.
    # «территория завода 5 гектаров» became an address the moment ГАР taught the
    # engine that «территория» is a street type: the type word was there, the
    # name was in the vocabulary, and a bare «5» satisfied the house-number
    # signal because nothing looked at what came AFTER it. This is the same
    # class `neg` already guards with «кв.м» — a quantity wearing an address's
    # shape — and consumer and business Russian is full of it: гектары, сотки,
    # метры, километры, штуки.
    #
    # A VETO ON THE NUMBER, not on the span. «улица Садовая 5 метров» still has
    # a real street in it; what it does not have is a house number, so the match
    # falls back to needing an intent word, exactly as a marked street with no
    # number already does. The two tiers then sort it out on their own: the weak
    # tier has nothing left and drops, the strong tier asks for the cue.
    #
    # «кв» IS NOT LISTED ON ITS OWN, and that is the whole care needed here:
    # after a house number it is КВАРТИРА far more often than it is квадратный
    # метр — «улица Ленина 14 кв 3» is the commonest address line in Russian —
    # so only the glued «кв.м» / «кв м» form counts, which is what `neg`
    # already does one line above.
    # ВОЗРАСТ, А НЕ НОМЕР ДОМА. «Кравцова 31-летний Иван», «со своей 90-летней
    # матерью» — форма, в которой число приклеено к возрасту, и без этого вето
    # она давала половину всех ложных адресов на новостной прозе. Отдельно от
    # `measure_after`, потому что «лет» там изменило бы поведение веток, которые
    # уже измерены и не про это.
    "age_after": r"(?i)\s*-?\s*(?:х\s*)?лет\w*\b",
    # УЛИЦА БЕЗ СЛОВА «УЛИЦА» — и в живой диспетчерской речи это ОСНОВНАЯ форма
    # адреса, а не хвост. Размечено вручную 400 реплик настоящих звонков такси:
    # 156 значений адреса, и в 100 из них нет ни «улицы», ни «проспекта» —
    # «барышникова шестьдесят три первый подъезд», «клубная восемьдесят пять
    # второй подъезд». Ни одна прежняя ветка их не видела: маркированные хотят
    # слово-тип, безмаркерные — заглавную или цифру.
    #
    # Форма здесь нарочно широкая — всё решают четыре гейта в движке, потому что
    # ни один из них не выражается регуляркой: реестр ГАР, морфологическая форма
    # имени, вето на возраст и меру, и согласование числительного со следующим
    # словом. Замерено: 77% этого класса при НУЛЕ ложных на 2691 предложении
    # новостной прозы NEREL.
    "street_bare_lower": (
        r"(?<![А-Яа-яЁё])(?P<bare>[а-яё]{4,})\s+(?:дом\s+)?"
        r"(?P<bnum>\d{1,3}(?!\d)|" + _SPELLED_CARD + r")"
        # ЛИТЕРА ДОМА БЫЛА ДОБАВЛЕНА КО ВСЕМ ВЕТКАМ, КРОМЕ ЭТОЙ, и это стоило
        # 205 обрезанных адресов из 303 — две трети всех утёкших хвостов на
        # корпусе живой речи. «пушкинская двести восемьдесят четыре а»,
        # «котовского девятнадцать а»: улица найдена, дом найден, литера ушла к
        # модели открытой. Ошибка ровно того вида, который ловит только
        # колонка покрытия: полнота считала эти адреса найденными.
        + _LITERA +
        r"(?![А-Яа-яЁё\d])"
    ),
    "measure_after": (
        r"(?i)\s*(?:м²|м2|%"
        r"|(?:кв\.?\s*м|гектар\w*|га|метр\w*|километр\w*|км|сантиметр\w*|см"
        r"|миллиметр\w*|мм|сотк\w+|квадратн\w+|штук\w*|шт|тонн\w*|кг"
        r"|литр\w*|процент\w*|м)\b)"
    ),
    # No (?i): separators only.
    "gap": r"[\s,.;\-/№#()]*",
    # No (?i) — deliberately. `[а-яё]` here is the lowercase letter that can
    # follow a house number ("12а"); made case-insensitive it would also swallow
    # the capital that starts the NEXT word.
    "trail_house": r"[\s,]+\d{1,4}[а-яё]?(?:/\d+)?\b",
}

# --- quasi-identifiers ---------------------------------------------------

# ЧИСЛИТЕЛЬНОЕ, ЗАПИСАННОЕ РАСШИФРОВЩИКОМ С ОШИБКОЙ. Одно испорченное слово в
# пробеге из одиннадцати убивает каждую цифру после него, поэтому таблица — это
# не украшение, а условие того, что произнесённый идентификатор вообще находится.
#
# ДОБЫТО ИЗ РЕЧИ, НЕ ПРИДУМАНО. Каждая форма встречается в OpenSTT или SOVA
# RuDevices и встречается ТОЛЬКО внутри числового пробега; счёт вхождений в
# комментарии. Соответствие поставлено руками, потому что автоматическое врёт:
# оно свело «шестидесятую» к «шестнадцать», а «десятков» — обычное слово, а не
# опечатка.
#
# НЕЧЁТКОЕ СРАВНЕНИЕ ЗДЕСЬ ЗАПРЕЩЕНО, и это измерено. На 58 983 различных словах
# прозы и речи в пределах ОДНОЙ опечатки от числительного лежат 99 обычных слов,
# и среди них «есть» (1947 вхождений) при «шесть», «опять» при «пять», «ночь»
# при «ноль», «семье» при «семь». Расстояние-1 не просто пропустило бы мусор —
# оно ИСКАЗИЛО БЫ цифры внутри настоящего номера, а неверная цифровая строка
# хуже ненайденной: она может пройти контрольную сумму и замаскировать не то.
#
# ЧЕГО ЗДЕСЬ НЕТ НАМЕРЕННО: «семесят», «четверьый», «подъкзд» — формы, которые
# порождает наш собственный бенчмарк и которых в настоящей речи ноль. Гнаться за
# ними значит настраивать движок на воображение прибора.
NUMERAL_TYPOS: dict[str, str] = {
    "песят": "пятьдесят",      # 9
    "пеесят": "пятьдесят",     # 1
    "пийсят": "пятьдесят",     # 1
    "пясят": "пятьдесят",      # 1
    "шесят": "шестьдесят",     # 3
    "семест": "семьдесят",     # 1
    "восемесят": "восемьдесят",  # 1
    "тристо": "триста",        # 7
    "трииста": "триста",       # 1
    "двесте": "двести",        # 1
    "шессот": "шестьсот",      # 1
    "восемьст": "восемьсот",   # 1
    "триц": "тридцать",        # 3
    "тридц": "тридцать",       # 1
    "одинадцать": "одиннадцать",  # 5
    "восем": "восемь",         # 3
    "восемсь": "восемь",       # 1
    "восеь": "восемь",         # 1
    "четыыре": "четыре",       # 1
    "пяять": "пять",           # 1
    "девяно": "девяносто",     # 1
    "девяеносто": "девяносто",  # 1
    "дваа": "два",             # 1
    "деся": "десять",          # 1
    "ноля": "ноль",            # 2
}

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
