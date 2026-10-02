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
    # THE SHORT DIMINUTIVES THE LENGTH FLOOR THROWS AWAY, and they are a SEED
    # entry rather than a lower floor because the floor is what protects 225k
    # capital-only bulk entries. Measured on the pinned 587-occurrence
    # real-speech frame (`bench/gate`, D1-N): these surfaces carry a Name/Surn
    # reading and are refused by `names.py::_lowercase_dictionary_ok` for one
    # reason only — `len(word) < _LOWER_DICT_MIN (=5)`. Adding them HERE closes
    # 27 person occurrences, 219/271 -> 246/271 = 90.8% whole recall. Lowering
    # `_LOWER_DICT_MIN` to 4 instead is measured at 1.98 false masks per close on
    # the same frame and 3.3 per name in `bench/gate/README.md`, paid three times
    # already («жуков»/«попов»/«машин»); the seed list is the mechanism that
    # exists precisely for lower-case diminutives the capital-only bulk cannot
    # serve (`gazetteer_names` docstring).
    #
    # THE PRICE IS NOT ZERO AND IT IS NOT THE 0.15 fp/close ALONE. `_name_set_hit`
    # runs BEFORE `_lowercase_dictionary_ok`, so membership here is CONTEXT-FREE.
    # «боб», «кац», «гуля», «ежи», «мия» read as ordinary nouns, and pymorphy's
    # FIRST parse carries NOUN and Name/Surn together, so `assets._build_names`
    # does NOT put them in `ambiguous` and no naming cue is demanded. Named
    # honestly: on the same frozen frame the close costs 4 hand-labelled
    # `other`/`place` occurrences («спанч боб», «мама мия», «кац», «ежи») —
    # 0.15 per close by the frame denominator, and a larger number by the
    # detector-span denominator (see work/P1/r1/DELTA.json, which prints both).
    # «гуля» is the dangerous one: a pigeon in ordinary prose and a person in
    # speech. It was measured on MASSIVE/NEREL before shipping (GATE.json).
    "лера", "гуля", "ника", "варя", "илик", "шура", "алсу", "боб", "ирка",
    "мия", "тони", "лех", "азиз", "алик", "лекс", "жора", "тоня", "кац",
    "жан", "ежи",
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
# Real settlements pymorphy3 reads ONLY as a surname (no `Geox`). A bare city is
# detected by the dictionary's `Geox` tag alone, so «самара» and «москва» need no
# list; but «одоев», «венёв» and «белёв» are towns in Tula oblast that pymorphy
# knows only as surnames — the same words, in an address, were minted as a PERSON
# while the street beside them was minted as a LOC, and production parted from the
# scorer (long_order-*, E01 re-case). The lowercase variant needs a DICTIONARY
# rather than morphology (detect-change), and this is that dictionary: a word on
# it is a settlement ONLY when the address structure says so (a street-type word
# or a settlement marker beside it), never on its own — so «фамилия одоев» stays a
# person. Kept apart from `FAKE_CITIES` on purpose: that pool is the substitute
# mint and may change for substitution reasons; this list names what the detector
# may read as a place.
SETTLEMENT_GAZ: tuple[str, ...] = ("одоев", "венёв", "белёв")

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

# --- the frequent tail of the register, for ONE decision -------------------
#
# A SECOND, TINY SET, and it exists to break exactly one tie: when a mistyped
# street reaches SEVERAL register entries one edit away, which one did the
# customer mean. `register_spelling` used to refuse every such word, and that
# is nearly all of them — «садвая» reaches садовая and садвал, «полвая» reaches
# полевая and полная, «неркасова» reaches некрасова and черкасова. Measured on
# the 06.09 live run: the repair fired on 1 of 6 mistyped streets and the other
# five went to the customer's CRM misspelt.
#
# THE MARGIN IS NOT CLOSE, WHICH IS WHY THE TIE-BREAK IS SAFE. садовая has
# 17 325 objects against садвал's 1; полевая 12 087 against полная's 1;
# некрасова 1 565 against черкасова's 24 — the narrowest margin measured, and
# still 65 to one. The register's 99th percentile is 58 objects, so a name
# above a hundred is in a different population from the tail, not merely a
# bigger number in the same one.
#
# THE RESIDUAL RISK, NAMED: a typo of a genuinely rare street that lands one
# edit from a common one is repaired to the common one, and a courier goes
# somewhere the customer did not name. It needs the mistyped word to be absent
# from the register in ALL THREE forms `_gar_reaches` asks — so a correctly
# spelt rare street is never touched — and it is the same bet the agent makes
# on its own when there is no gateway in front of it.
STREET_FREQUENT_MIN = 100

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
# …AND AFTER A HOUSE LITERA, glued or spaced: «зеленоградская 8 бкв150»,
# «тельмана 99 вкв196» — a phone keyboard's «8б, кв. 150», and the flat went
# to the model outside a span already reported as found.
_TOK_OR_DIGIT = r"(?:(?<=^)|(?<=[\s,;(№#\"'«»\[\]{}<>=:|/\\])|(?<=\d)|(?<=\d[а-яё])|(?<=\d\s[а-яё]))"
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
NUMERAL_TYPOS: dict[str, str] = {
    "песят": "пятьдесят",      # 9
    "пеесят": "пятьдесят",     # 1
    "пийсят": "пятьдесят",     # 1
    "пясят": "пятьдесят",      # 1
    "шесят": "шестьдесят",     # 3
    # The contracted «-десят» forms the ASR corpus writes for the two commonest
    # tens (пейсят is the textbook colloquial form); «семест» is left OUT — it
    # is attested once as семьдесят and once as семьсот, and a form with two
    # readings corrupts a digit, which is worse than missing it.
    "пейсят": "пятьдесят",
    "пяесят": "пятьдесят",
    "шеесят": "шестьдесят",
    "шейсят": "шестьдесят",
    "восемест": "восемьсот",
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


def _typo_forms(*canonicals: str) -> str:
    """The attested misspellings of these numerals, as extra alternatives —
    so «подлесная тридц один» is a house number to the address arms and not
    two damaged words the name arm joins to a surname (live v4, compare-006)."""
    return "".join("|" + form for form, canonical in NUMERAL_TYPOS.items() if canonical in canonicals)


_HUNDREDS = (r"(?:сто|двести|триста|четыреста|пятьсот|шестьсот|семьсот"
             r"|восемьсот|девятьсот"
             + _typo_forms("сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
                           "семьсот", "восемьсот", "девятьсот") + ")")
_TEENS = (r"(?:одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать"
          r"|шестнадцать|семнадцать|восемнадцать|девятнадцать|десять"
          + _typo_forms("одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
                        "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать", "десять") + ")")
_TENS = (r"(?:двадцать|тридцать|сорок|пятьдесят|шестьдесят|семьдесят"
         r"|восемьдесят|девяносто"
         + _typo_forms("двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят",
                       "восемьдесят", "девяносто") + ")")
_UNITS = (r"(?:один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять"
          + _typo_forms("один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять") + ")")
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
# …AND NOT «к» OR «с» IN FRONT OF A NUMBER: those are the корпус and строение
# markers («д 65 к 1»), and read as a litera the marker closed the span at
# «65 к» — the корпус went to the model outside an address already reported
# as found, and the directory record keyed without it.
# …AND NOT A PREPOSITION IN FRONT OF WHAT IT GOVERNS. «бульвар комиссарова
# двадцать семь **в** третий подъезд» — the «в» is «in», not house 27в: it
# stands before an ORDINAL («в третий», «к пятому») or before a marker in an
# oblique case («в квартиру», «в подъезде», «к дому»), and a litera is never
# followed by either. The building went to the courier as «27в» on the 05.09
# medium run (decompose-001, three triples, voice register). Only the letters
# that ARE prepositions are tested — «двадцать пять а третий подъезд» keeps
# its «а», which is a litera and never a preposition — and a marker in the
# NOMINATIVE after the letter still reads as a litera («дом семнадцать в
# квартира двести двадцать девять» is a real call and stays whole).
_PREP_GOVERNS = (r"(?:" + _ORDINAL + r"|квартир[уе]|под[ъь]езд[еу]|дом[еу]|корпус[еу]"
                 r"|этаж[еу]|строени[ие]|офис[еу]|помещени[ие])\b")
_LITERA = (r"(?:\s+(?![яЯ](?![а-яё]))(?![кс]\.?\s*\d)(?![вксуо]\s+" + _PREP_GOVERNS + r")"
           r"[а-яё](?=(?:кв|к|стр)\.?\d|[^а-яё]|$))?")

# ЛИТЕРА ПРИ ЦИФРОВОМ НОМЕРЕ ДОМА — ТА ЖЕ БУКВА, НО ДРУГОЙ РЕГИСТР ТЕКСТА.
# «воткинское шоссе 4 а квартира 58» обрывалось на «4»: у речевых арок литера
# есть, у цифровых её не было, и спан кончался перед ней — вместе с литерой
# терялась и квартира, потому что «а» вставало в разрыв и слияние до неё не
# доходило. У безмаркерной арки литера есть давно, поэтому «ленина 14 а
# квартира 58» работало, а то же самое с родовым словом — нет.
#
# ПРОСМОТР ВПЕРЁД ЗДЕСЬ УМЕСТЕН, А У РЕЧЕВОЙ АРКИ БЫЛ НЕТ, и разница не в
# букве, а в том, что вокруг. Цифровая арка срабатывает на письменном тексте —
# новостях, деловой переписке, — где «дом 5 и 7» и «в 2014 а также» встречаются
# постоянно, а речевая живёт в диктовке, где измерено: жёсткий просмотр вперёд
# резал номер дома на каждом третьем настоящем адресе. Условие не может ничего
# сломать по построению: литера необязательна, и когда просмотр не сходится,
# остаётся ровно сегодняшнее поведение.
# …AND THE LITERA MAY HAVE THE FLAT MARKER GLUED TO IT: «зеленоградская 8
# бкв150» — the letter is followed by «кв» and digits, not by a boundary.
_LITERA_WRITTEN = (r"(?:\s+(?![яЯ](?![а-яё]))[а-яё](?=(?:кв|к|стр)\.?\d|[^а-яё]|$)"
                   r"(?=\s*(?:[,;.]|$|\s*" + _CHAIN_MARKER + r"(?:\b|(?=\d)))))?")

# НАЗВАНИЕ УЛИЦЫ НЕ ИМЕЕТ ПРАВА СЪЕСТЬ ЧИСЛИТЕЛЬНОЕ. `_LOWER_NAME` берёт до трёх
# слов подряд, и в «улицу культуры восемь» оно забирало «культуры восемь»
# целиком — номеру дома не оставалось ничего, и адрес не находился. С цифрой
# этого не бывает: цифра под шаблон названия не подходит, поэтому дефект жил
# только в голосовом регистре, где номер и есть слово.
_LOWER_NAME_NONUM = (r"(?!" + _SPELLED + r"\b)[а-яё]{3,}"
                     r"(?:[\s-](?!" + _SPELLED + r"\b)[а-яё]{3,}){0,2}")

# THE GLUED LITERA, IN EITHER CASE. ФИАС and DaData write «д 10А», and the
# arms ended the span at «10»: the capital fell outside the address, outside
# the vault key, and reached the model beside the substitute. Glued only — a
# capital after a SPACE is the next word — and never followed by a letter.
_HOUSE_NUM = rf"(?:\d{{1,4}}(?!\d)(?:[а-яёА-ЯЁ](?![а-яёА-ЯЁ]))?|{_SPELLED_NUM})"

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
    "street_lower_first": rf"(?i)\b{_ST_FULL}\s*{_LOWER_NAME}{_HOUSE_LEAD}\d{{1,4}}(?!\d){_LITERA_WRITTEN}",
    "street_lower_last": rf"(?i)\b{_LOWER_NAME}\s*{_ST_FULL}{_HOUSE_LEAD}\d{{1,4}}(?!\d){_LITERA_WRITTEN}",
    "street_abbr_lower": rf"(?i)\b{_ST_ABBR}{_LOWER_NAME}{_HOUSE_LEAD}\d{{1,4}}(?!\d){_LITERA_WRITTEN}",
    # The same shape with the abbreviation AFTER the name — see `_ST_ABBR_LAST`.
    "street_abbr_lower_last": rf"(?i)\b{_LOWER_NAME}{_ST_ABBR_LAST}{_HOUSE_LEAD}\d{{1,4}}(?!\d){_LITERA_WRITTEN}",
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
    # `(?!\w)` AND NOT `\b`: after an abbreviation's dot («Кирова пр., дом
    # 235», «Ленина ш., д.114») the next character is a comma, and `\b` needs a
    # word character on one side — so the name-then-abbreviation form never
    # matched and the street's name was minted as a PERSON on the hard-negative
    # set. A bare «пер» glued to «езвоните» is still refused by the lookahead.
    "street_last": rf"(?i){_CAP}\s+{_ST}(?!\w)",
    "house": (
        r"(?i)" + _TOK + r"(?:дом|д|владени\w*|вл|уч\w*)\.?\s*№?\s*\d+(?:[а-яёА-ЯЁ](?!\d)|/\d+|-\d+)?"
        r"(?:\s*(?:корпус|корп|кор|к)\.?\s*\d+(?:[а-яёА-ЯЁ](?![а-яё]?\d))?)?"
        r"(?:\s*(?:строени\w*|стр|с)\.?\s*\d+(?:[а-яёА-ЯЁ](?![а-яё]?\d))?)?"
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
              r"|корпус\w*|корп|кор|строени\w*|стр|под[ъь]езд\w*|под|этаж\w*|эт)\.?\s*\d+(?:[а-яёА-ЯЁ](?![а-яё]?\d))?"
            # …AND WITH ONE SPACE, when a digit follows and no word does: «ул.
            # Кирова 12 к 3 кв 300» is how a courier form writes the корпус, and
            # the tail after «12» went to the model. Still SUPPORT — «в 12 к 5
            # часам» has no core address to merge with and is dropped.
            # The spaced form must be FOLLOWED by the end, punctuation or another
            # address marker: «привезите на ленина 14 к 10 часам» is a time,
            # and the bare preposition took eight of v3's time-of-day negatives.
            + r"|(?<=\d)к\.?\s*\d+"
            + r"|(?<=\d)\sк\.?\s*\d+(?=\s*(?:[,;.)]|$"
              r"|(?:кв|квартир\w*|подъезд\w*|под|этаж\w*|эт|стр|строен\w*|литер\w*|лит|оф|офис\w*|пом|комн\w*|дом|д)\b)))"),
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
        # «д. Петрово» — the village marker written the short way; the dot is
        # mandatory and `_NAME` wants a capital, so «д. 14» stays a house.
        r"(?i)" + _TOK + r"(?:город|гор|г|посёлок|поселок|пос|п|село|деревн\w*|дер|д\.|станиц\w*|ст"
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
        # «базисная 152кв7», «химзаводская 3кв170»: the chat register glues the
        # flat to the house, and the number here ended at the first letter.
        r"(?P<bnum>\d{1,3}(?!\d)(?:кв\.?\d{1,4}|к\d{1,3})?|" + _SPELLED_CARD + r")"
        # ЛИТЕРА ДОМА БЫЛА ДОБАВЛЕНА КО ВСЕМ ВЕТКАМ, КРОМЕ ЭТОЙ, и это стоило
        # 205 обрезанных адресов из 303 — две трети всех утёкших хвостов на
        # корпусе живой речи. «пушкинская двести восемьдесят четыре а»,
        # «котовского девятнадцать а»: улица найдена, дом найден, литера ушла к
        # модели открытой. Ошибка ровно того вида, который ловит только
        # колонка покрытия: полнота считала эти адреса найденными.
        + _LITERA +
        # The guard against a partial word after the number stands down for a
        # flat marker glued to the litera («8 бкв150»).
        r"(?!(?!(?:кв|к|стр)\.?\d)[А-Яа-яЁё\d])"
    ),
    "measure_after": (
        r"(?i)\s*(?:м²|м2|%"
        r"|(?:кв\.?\s*м|гектар\w*|га|метр\w*|километр\w*|км|сантиметр\w*|см"
        r"|миллиметр\w*|мм|сотк\w+|квадратн\w+|штук\w*|шт|тонн\w*|кг"
        r"|литр\w*|процент\w*|м)\b)"
    ),
    # СТРОЧНАЯ УЛИЦА БЕЗ НОМЕРА ДОМА И БЕЗ СЛОВА-ТИПА. «адрес репина», «на
    # бибиревская»: слово в нижнем регистре потеряло заглавную — второй сигнал,
    # которым его судили все ветки, — а номер дома, которым держатся
    # `street_bare_lower` и `markerless_lower`, здесь не написан вовсе. Так не
    # принадлежало НИ ОДНОЙ ветке: адрес требовал дом, имена — словарь или
    # заглавную; а ЯКОРЬ перед словом (адресная подсказка или предлог вплотную)
    # в коде уже был — но умел только ЗАПРЕЩАТЬ (`names._street_reference`).
    #
    # Форма даёт слово; роль решают якорь и морфология В ДВИЖКЕ, потому что ни
    # то, ни другое регуляркой не выражается.
    "street_nohouse_bare": (
        r"(?<![А-Яа-яЁё])(?P<bare>[а-яё]{4,})"
        r"(?!\s*,?\s*(?:дом|д)?\.?\s*\d)"
    ),
    # МЕСТНЫЙ ПРЕДЛОГ ВПЛОТНУЮ: «на репина», «на бибиревская». Именно «на»/«по»,
    # а не весь `prep_before`: «в» и «у» вводят обстоятельство и владельца
    # («в марте», «у клиента») и адресной роли не дают.
    "street_nohouse_prep": r"(?i)\b(?:на|по)\s+$",
    # No (?i): separators only.
    "gap": r"[\s,.;\-/№#()]*",
    # No (?i) — deliberately. `[а-яё]` here is the lowercase letter that can
    # follow a house number ("12а"); made case-insensitive it would also swallow
    # the capital that starts the NEXT word.
    "trail_house": r"[\s,]+\d{1,4}(?:[а-яёА-ЯЁ](?![а-яёА-ЯЁ]))?(?:/\d+)?\b",
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

BIRTH_CTX: tuple[str, ...] = ("рожд", "г.р", "г р", "родил", "д.р", "появил на свет")
# ПОДСКАЗКИ, КОТОРЫЕ ИЩУТСЯ ЦЕЛЫМ СЛОВОМ, А НЕ ПОДСТРОКОЙ. «др» — самая частая
# форма в чате («др 13.01.1991»), и подстрокой её искать нельзя: она сидит
# внутри «адрес», «друг», «подробно», «недра» — то есть внутри половины
# делового письма. Публичный бенчмарк показал цену отсутствия: 27 дат рождения
# из 50 не найдено, все 27 — после «др».
#
# «и др.» (= «и другие») — единственное настоящее столкновение, и оно снимается
# в `quasi`: подсказка засчитывается только ПЕРЕД датой и только если перед ней
# самой не стоит «и».
BIRTH_CTX_WORDS: tuple[str, ...] = ("др",)
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
    # «записывайте лермонтого сто а квартира двести шесть» — the dispatcher's
    # word for «here is my address», and the only intent the utterance carries.
    "записывай", "запишите", "запиши",
    # «курькра на совхоззная 146», «курера на зарчная 23» — the courier word
    # is the intent in the delivery register, and here it is misspelt: the
    # exact cue regex already holds it, the fuzzy matcher reads this list.
    "курьер",
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
# The word DIRECTLY before a one-word name that says it is a KIND OF COMPANY, not
# a person. Authored from measured false positives (a curated business register),
# with no public-standard backing — so it is tuning that rides in the lease, unlike
# the published `_DENY_AS_NAME` abbreviations that stay in the engine.
ORG_CUE: tuple[str, ...] = (
    "ооо", "оао", "зао", "пао", "ао", "нко", "ано", "фгуп", "мбу", "гбу",
    "компания", "компании", "фирма", "фирмы", "организация", "организации",
    "поставщик", "поставщика", "магазин", "магазина", "бренд", "бренда",
)
# A ROLE WORD THAT INTRODUCES STAFF, NOT THE SUBJECT. A date beside a name the
# text frames as a doctor / specialist / position holder is a meeting or slot
# date, not that person's date of birth: `context._date_is_personal` must not
# read the DOCTOR's name in a clinic-slot result as evidence the date belongs to
# the patient. The subject is named by nothing or by a subject word («пациент»,
# «клиент»); the role word is what demotes the name. Kept as tuning rather than a
# published abbreviation list because the set is authored from a measured false
# positive (a live clinic run), like `ORG_CUE`.
PERSONNEL_CUE: tuple[str, ...] = (
    "врач", "врача", "врачу", "доктор", "доктора", "специалист", "специалиста",
    "должность", "сотрудник", "сотрудника", "администратор", "администратора",
    "медсестра", "медсестры", "медбрат", "медбрата", "лечащий", "лечащего",
    "doctor", "physician", "specialist", "speciality", "specialty", "nurse",
)

# --- transliteration machinery (align/render/fold) ------------------------
# TUNING-DATA mined from 1 812 aligned control-arm words (counts in the inline
# notes): the per-unit renderings the round-trip learns from and defaults to.
# NOT a standard → rides in the lease, not the binary. The align/render/fold
# ALGORITHM stays in pseudex.translit. Order within a UNITS tuple is the order
# `align` tries them, the first is what DEFAULT writes; the four TABLES order and
# the FOLD sequence are load-bearing (see pseudex.translit for why).
TRANSLIT_UNITS: dict[str, tuple[str, ...]] = {
    # endings: «-ий» iy 77:y 51, «-ый» y 24:yy 2, «-ия» ia 36:0, «ья» ia 22:ya 2,
    # «кс» ks 25:x 10, «ей» ei 22:ey 12, «йя» defaults to ya; table spellings
    # iia/jya/yya are also recognised so a model's standard spelling resolves.
    "ий": ("iy", "y", "ii", "ij", "yi"),
    "ый": ("y", "yy", "yi", "yj", "iy"),
    "ия": ("ia", "iya", "iia", "ija"),
    "ья": ("ia", "ya", "ja"),
    "кс": ("ks", "x"),
    "ей": ("ei", "ey", "ej"),
    "йя": ("ya", "iya", "ja", "iia", "jya", "yya"),
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
TRANSLIT_ENDINGS: tuple[str, ...] = ("ий", "ый", "ия", "ья", "кс", "йя", "ей")
# The four standards, in the order `table_for`/`variants` try them.
TRANSLIT_ICAO: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "ie", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
TRANSLIT_GOST_B: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "cz", "ч": "ch", "ш": "sh", "щ": "shh",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
TRANSLIT_MVD_2010: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "tc", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "iu", "я": "ia",
}
TRANSLIT_COMMON: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
# The canonical-collision fold. ORDER CRITICAL: «shch» before «sch»/«sh», «ch»
# before bare «c» (ц), digraph vowels before their single letters.
TRANSLIT_FOLD: tuple[tuple[str, str], ...] = (
    ("shch", "S"), ("shh", "S"), ("sch", "S"),
    ("zh", "Z"), ("ch", "C"), ("sh", "H"),
    ("kh", "X"), ("ks", "X"), ("x", "X"),
    ("ts", "T"), ("tc", "T"), ("cz", "T"), ("c", "T"),
    ("yu", "U"), ("iu", "U"), ("ju", "U"),
    ("jya", "A"), ("yya", "A"),
    ("iya", "A"), ("iia", "A"), ("ija", "A"), ("ya", "A"), ("ia", "A"), ("ja", "A"),
    ("yo", "E"), ("jo", "E"), ("ye", "E"), ("ie", "E"), ("e", "E"),
    ("y", "I"), ("j", "I"), ("i", "I"),
)

# --- fake substitute pools (vault mint) -----------------------------------
# TUNING-DATA: the substitute values a competitor would copy. Leased, not
# compiled — they used to sit as Python constants in the binary and leaked from
# the constants blob. vault.TOKEN_RE anchors NAME recognition on FAKE_FIRST and
# LOC(city) on FAKE_CITIES, so both must be literal pools (not the 28k dict), and
# the regex rebuilds per bundle version (pseudex.vault._token_re).
FAKE_FIRST: tuple[str, ...] = (
    "Александр", "Алексей", "Андрей", "Антон", "Артур", "Борис", "Вадим",
    "Валерий", "Василий", "Виктор", "Владимир", "Глеб", "Григорий", "Даниил",
    "Денис", "Дмитрий", "Евгений", "Егор", "Иван", "Игорь", "Илья", "Кирилл",
    "Константин", "Леонид", "Максим", "Марк", "Михаил", "Никита", "Николай",
    "Олег", "Павел", "Роман", "Руслан", "Сергей", "Степан", "Тимофей", "Юрий",
    "Александра", "Алина", "Анастасия", "Анна", "Валентина", "Вера", "Виктория",
    "Галина", "Дарья", "Екатерина", "Елена", "Ирина", "Карина", "Кристина",
    "Ксения", "Лариса", "Маргарита", "Марина", "Мария", "Надежда", "Нина",
    "Оксана", "Ольга", "Полина", "Светлана", "София", "Татьяна", "Юлия",
    # Widened: the substitute mirrors the original's SHAPE, so a one-word name is
    # replaced by one word and single-name-contact customers draw from this pool
    # alone (at 65 entries `_unique_token` exhausted → 5xx).
    "Аркадий", "Артём", "Богдан", "Валентин", "Вениамин", "Виталий", "Владислав",
    "Всеволод", "Вячеслав", "Геннадий", "Георгий", "Герман", "Гордей", "Демьян",
    "Захар", "Игнат", "Кузьма", "Лев", "Макар", "Матвей", "Мирон", "Мирослав",
    "Назар", "Остап", "Пётр", "Платон", "Прохор", "Радислав", "Ратмир", "Родион",
    "Савва", "Савелий", "Святослав", "Семён", "Тарас", "Тимур", "Трофим", "Фёдор",
    "Филипп", "Харитон", "Эдуард", "Эмиль", "Яков", "Ян", "Ярослав",
    "Агата", "Аглая", "Алевтина", "Алиса", "Алла", "Альбина", "Амелия", "Ангелина",
    "Антонина", "Арина", "Белла", "Богдана", "Валерия", "Варвара", "Василиса",
    "Вероника", "Влада", "Власта", "Гелена", "Диана", "Дина", "Ева", "Евгения",
    "Елизавета", "Жанна", "Зинаида", "Злата", "Зоя", "Иванна", "Инга", "Инна",
    "Иоланта", "Капитолина", "Клавдия", "Лада", "Лидия", "Лилия", "Любовь",
    "Людмила", "Майя", "Милана", "Милена", "Мирослава", "Наталья",
    "Олеся", "Прасковья", "Раиса", "Регина", "Римма", "Роза", "Руслана",
    "Сабина", "Серафима", "Снежана", "Стелла", "Таисия", "Тамара", "Ульяна",
    "Фаина", "Христина", "Эвелина", "Эльвира", "Эмилия", "Ярослава",
)
FAKE_LAST: tuple[str, ...] = (
    "Лебедев", "Жуков", "Тихонов", "Котов", "Сорокин", "Беляев", "Гущин",
    "Ершов", "Зимин", "Карпов", "Лужин", "Мещеряков", "Наумов", "Осипов",
    "Панов", "Рыбаков", "Сазонов", "Тарасов", "Устинов", "Фомин", "Хвостов",
    "Цветков", "Чижов", "Шилов", "Щукин", "Юдин", "Яровой", "Бирюков",
    "Бобров", "Кудрявцев", "Мухин", "Титов", "Уваров", "Якушев", "Крылов", "Фролов",
)
# A woman named by surname ALONE: -ов/-ин feminines are syncretic and fail
# `survives_round_trip`, so these gender-invariant surnames are the only pool for
# her. A separate list (folded in they would be half of every customer's fakes),
# and its SIZE is load-bearing (six meant the seventh such woman → fail-closed 5xx).
FAKE_LAST_INVARIANT: tuple[str, ...] = (
    "Шевчук", "Ткачук", "Бондарчук", "Кравчук", "Гончарук", "Ковальчук",
    "Павлюк", "Савчук", "Марчук", "Данилюк",
    "Саркисян", "Аванесян", "Петросян", "Акопян", "Григорян", "Арутюнян",
    "Бабаян", "Казарян", "Хачатрян", "Мкртчян",
    "Петренко", "Коваленко", "Савченко", "Бондаренко", "Кравченко", "Ткаченко",
    "Черных", "Белых", "Седых", "Долгих", "Рыжих",
    "Гвелесиани", "Церетели", "Бойко", "Головко",
)
# Cities stay BARE and in the NOMINATIVE (oblique derived by inflect_place); the
# size is combinatorial with streets×houses. TOKEN_RE matches these literally.
FAKE_CITIES: tuple[str, ...] = (
    "Зеленоград", "Светлогорск", "Приозерск", "Гатчина", "Кинешма",
    "Торжок", "Валдай", "Бологое", "Кимры", "Сортавала", "Луга", "Тихвин",
    "Мышкин", "Углич", "Плёс", "Суздаль", "Елец", "Задонск", "Данков",
    "Венёв", "Алексин", "Белёв", "Крапивна", "Одоев", "Чернь",
)
FAKE_STREETS: tuple[str, ...] = (
    "Берёзовой", "Кленовой", "Ольховой", "Рябиновой", "Вязовой", "Тополиной",
    "Липовой", "Ясеневой", "Сосновой", "Еловой", "Кедровой", "Пихтовой",
    "Ивовой", "Вишнёвой", "Грушевой", "Абрикосовой", "Каштановой", "Буковой",
    "Осиновой", "Черёмуховой", "Барбарисовой", "Жасминовой", "Сиреневой",
    "Лавандовой", "Мятной", "Полевой", "Луговой", "Озёрной", "Речной",
    "Родниковой",
)
# 30 streets × 199 numbers + 25 cities = 5995 distinct LOC tokens per customer.
FAKE_HOUSE_MAX: int = 199

# --- structured key->type ------------------------------------------------

# Биографический контекст: вопрос ПРО человека, а не запись о клиенте.
#
# Второй сигнал для пары слов, которых нет ни в одном словаре. Иностранное имя
# — «билл гейтс», «шоне коннери», «тейлор свифт» — не лежит в русских
# газетирах, не имеет заглавной в чате и морфологически выглядит как два
# неизвестных слова. Одной этой формы мало: «доу джонса» и «какеи нибудь»
# выглядят так же, и на 1134 чистых фразах правило без подсказки срабатывало
# дважды. С подсказкой — ни разу, а шесть из семи публичных фигур находятся.
#
# Слова именно биографические, а не транзакционные: «зовут» и «перезвоните»
# уже стоят в `cues` и работают на другой класс. Здесь спрашивают возраст,
# рост, дату рождения, роли и книги — то, о чём спрашивают ЧЕЛОВЕКА.
# WORDS A MISTYPED NAME IS NEVER ONE EDIT FROM. The three-signal rule for a
# mistyped name (adjacent to a name, unknown to morphology, one edit from the
# gazetteer) admitted «телефн» and «телфеон»: a damaged cue word is unknown to
# morphology by definition, and the 197k-surname neighbourhood reaches it. A
# one-edit veto against ORDINARY words was measured at four real people on
# NEREL; against the dozen words that introduce the next field it costs
# nothing, because none of them is ever a person.
NAME_NEVER_CUES = (
    "телефон", "телефона", "телефону", "адрес", "адреса", "паспорт", "паспорта", "снилс",
    "почта", "почту", "индекс", "квартира", "квартиру", "подъезд", "получатель", "получателя",
    "доставка", "доставку", "курьер", "курьера", "заказ", "заказа", "клиент", "клиента",
    "номер", "номера", "оплата", "оплату", "карта", "карту", "договор", "договора",
)
BIO_CUES: tuple[str, ...] = (
    "родил", "умер", "скончал", "биограф", "женат", "замуж", "рост",
    "возраст", "лет", "сколько лет", "кто так", "расскажи о", "расскажи про",
    "день рождения", "снимал", "играл", "написал", "основал", "изобрёл",
    "изобрел", "новости о", "новости про", "фильм", "песн", "альбом",
    "актёр", "актер", "певец", "певиц", "поёт", "поет", "карьер",
)

# ПРЕДЛОГИ, ВВОДЯЩИЕ ЧЕЛОВЕКА: «от аленчиев», «к аленчиеву», «позвоните у».
# Строчное слово потеряло заглавную — второй сигнал, которым его судили
# словари, — и якорь перед ним ровно то, чего не хватает. Список арендуется, а
# не живёт в коде: он настраиваемый, как и всякий другой cue.
#
# «НА» ЗДЕСЬ НЕТ НАМЕРЕННО: оно вводит и улицу («на ленина»), и человека
# («перезвоните на морозова») — различает их слово ПЕРЕД предлогом, и это уже
# работа `NAME_CUES`, а не предлога.
NAME_ANCHOR_PREPS: tuple[str, ...] = (
    "от", "ото", "к", "ко", "у", "для", "о", "об", "обо", "про", "из",
)

# ПРЕДЛОГИ, ВВОДЯЩИЕ ЧЕЛОВЕКА: «от аленчиев», «к аленчиеву», «перезвоните
# у». Строчное слово потеряло заглавную — второй сигнал, которым его судили
# словари, — и ЯКОРЬ здесь ровно то, чего не хватает. Список арендуется, а не
# живёт в коде: он настраиваемый, как и всякий другой cue.
#
# «НА» ЗДЕСЬ НЕТ НАМЕРЕННО: оно вводит и улицу («на ленина»), и человека
# («перезвоните на морозова») — различает их слово ПЕРЕД предлогом, и это уже
# работа `NAME_CUES`, а не предлога.
NAME_ANCHOR_PREPS: tuple[str, ...] = (
    "от", "ото", "к", "ко", "у", "для", "о", "об", "обо", "про", "из",
)

KEY_TYPE: dict[str, str] = {
    "имя": "NAME", "фио": "NAME", "клиент": "NAME", "заказчик": "NAME",
    "получатель": "NAME", "name": "NAME",
    # THE PARTS OF A NAME AS A CRM WRITES THEM. A record answered
    # {"last_name": "кузнецов", "first_name": "дмитрий"} and the surname leaf
    # went to the model in the clear — a lower-case surname alone passes no
    # gate, and the key that names it was not in this map. The model then saw
    # a card whose surname differed from the person it was talking to and
    # asked whose card it was (live v4, chain-014). Keys are matched with
    # separators removed (`_KEY_CLEAN_RE`), so «last_name» is «lastname».
    "фамилия": "NAME", "отчество": "NAME", "lastname": "NAME", "firstname": "NAME",
    "middlename": "NAME", "surname": "NAME", "patronymic": "NAME", "givenname": "NAME",
    "fullname": "NAME", "секондфамилия": "NAME",
    "телефон": "PHONE", "тел": "PHONE", "моб": "PHONE", "мобильный": "PHONE",
    "номертелефона": "PHONE", "phone": "PHONE", "контактныйтелефон": "PHONE",
    "снилс": "SNILS", "snils": "SNILS",
    # ЛАТИНСКИЕ КЛЮЧИ ИНН, КОТОРЫХ НЕТ В РУССКОМ СЛОВЕ. Английская схема
    # русского CRM пишет ИНН как `tax_id`, `taxpayer_id`, `vat_number` — ключи
    # с головой `tax`/`vat`, до которых префиксная ветка `_key_type` не
    # достаёт, потому что стема `tax` в карте не было. `passport_series` в этом
    # смысле УЖЕ покрыт стемом `passport`; дыра была именно здесь.
    #
    # `taxrate` и `taxamount` — ставка и сумма налога, не ПД, поэтому стем
    # взят с разделителем-в-нуле: карта нормализует ключ (`_KEY_CLEAN_RE`), так
    # что «tax_id» это «taxid», а «tax_rate» это «taxrate», и префикс «taxid»
    # первую пару не задевает.
    "инн": "INN", "inn": "INN",
    "taxid": "INN", "taxnumber": "INN", "taxpayerid": "INN",
    "innumber": "INN", "иннклиента": "INN",
    "паспорт": "PASSPORT", "passport": "PASSPORT",
    # THE REQUISITE OBJECT NAMES THE DOCUMENT IN ITS OWN KEYS. Bitrix24's
    # `crm.requisite` is where a Russian CRM keeps identity documents, and it
    # splits the passport across `RQ_IDENT_DOC_SER` and `RQ_IDENT_DOC_NUM` —
    # a four-digit and a six-digit field that no shape rule can claim on its
    # own, arriving from the CUSTOMER'S OWN system. Both went to the model in
    # the clear. Keys are matched with separators removed, so `RQ_IDENT_DOC_SER`
    # is «rqidentdocser».
    #
    # `RQ_KPP` and `RQ_OGRN` are deliberately ABSENT: they identify a legal
    # entity, which 152-ФЗ does not cover, and masking them would break the
    # very requisites the object exists for. `RQ_OGRNIP` is likewise left to
    # the shape recogniser, which already types it — an individual
    # entrepreneur is a physical person.
    "rqidentdocser": "PASSPORT", "rqidentdocnum": "PASSPORT",
    "rqidentdoc": "PASSPORT", "identdocser": "PASSPORT", "identdocnum": "PASSPORT",
    "rqinn": "INN", "rqlastname": "NAME", "rqfirstname": "NAME", "rqsecondname": "NAME",
    "rqname": "NAME", "rqemail": "EMAIL", "rqphone": "PHONE",
    # --- the temporary-secret family: field keys ------------------------------
    #
    # C1 (O-SECRET), on the owner's decision EX-O-SECRET-1: CVC and ISSUER_OTP are
    # measured; TOTP/2FA, recovery codes, transaction authorisation codes and PIN
    # stay a NAMED GAP. A key here types the WHOLE value (P03) with no shape check
    # of its own — the declared LENGTH SET per alias lives in `pseudex/cvc.py`,
    # because the 3-or-4 arithmetic is the payment brands' published grammar
    # (PCI SSC S1), not tuned vocabulary. What is leased is WHICH WORDS NAME THE
    # CLASS, which is exactly this list.
    #
    # WHY THE BLOCK STANDS BEFORE `card`. `_key_type` asks the exact map first and
    # then walks the same dict as PREFIX STEMS IN ORDER, so `card_cvc` — which is
    # not an exact key of the v5 map — reached the `card` stem and was typed CARD:
    # a three-digit field received a SIXTEEN-digit Luhn-valid card number (RED-9,
    # probe `card_renderer_for_3_digits`). Placing the compounds before `card`
    # makes the whole-word reading win over its head. `card_number` is untouched
    # and keeps CARD (`card` is still the only stem it matches).
    #
    # NOT ADDED, deliberately: bare «код»/`code` (it names an order, a status and a
    # product far more often than a secret — P05, OWNER-DECISIONS Q3), `pin`,
    # `2fa`/`totp`, `recovery`/`резервный` and `транзакц`/`transaction` (all four
    # are OWNER_PENDING and stay NOT_MEASURED), and bare `sms` — NEG-OTP-3
    # (`{"sms_count": "000000"}`) is the counter-example: a key that merely
    # contains «sms» names no code.
    "cvc": "CARD_VERIFICATION_CODE", "cvc2": "CARD_VERIFICATION_CODE",
    "cvv": "CARD_VERIFICATION_CODE", "cvv2": "CARD_VERIFICATION_CODE",
    "csc": "CARD_VERIFICATION_CODE", "cav2": "CARD_VERIFICATION_CODE",
    "cv2": "CARD_VERIFICATION_CODE", "cvv4": "CARD_VERIFICATION_CODE",
    "cvvcode": "CARD_VERIFICATION_CODE", "cvvnum": "CARD_VERIFICATION_CODE",
    "cvvnumber": "CARD_VERIFICATION_CODE", "cvv2code": "CARD_VERIFICATION_CODE",
    "cvccode": "CARD_VERIFICATION_CODE", "cvcnum": "CARD_VERIFICATION_CODE",
    "cvc2code": "CARD_VERIFICATION_CODE", "codecvv": "CARD_VERIFICATION_CODE",
    "codecvc": "CARD_VERIFICATION_CODE",
    "securitycode": "CARD_VERIFICATION_CODE",
    "cardsecuritycode": "CARD_VERIFICATION_CODE",
    "cardverificationcode": "CARD_VERIFICATION_CODE",
    "cardverificationvalue": "CARD_VERIFICATION_CODE",
    "cardcvc": "CARD_VERIFICATION_CODE", "cardcvc2": "CARD_VERIFICATION_CODE",
    "cardcvv": "CARD_VERIFICATION_CODE", "cardcvv2": "CARD_VERIFICATION_CODE",
    "cardcvvcode": "CARD_VERIFICATION_CODE",
    "cardcode": "CARD_VERIFICATION_CODE",
    "cid": "CARD_VERIFICATION_CODE", "cidcode": "CARD_VERIFICATION_CODE",
    "cidnumber": "CARD_VERIFICATION_CODE", "4dbc": "CARD_VERIFICATION_CODE",
    "amexcid": "CARD_VERIFICATION_CODE", "cardcid": "CARD_VERIFICATION_CODE",
    "card4dbc": "CARD_VERIFICATION_CODE",
    # Russian spellings: a form field, an OCR'd card or a support script writes
    # these with a space or a hyphen, and `_KEY_CLEAN_RE` removes separators
    # before this map is asked — so «защитный код карты» arrives as one word.
    "цвс": "CARD_VERIFICATION_CODE", "цсв": "CARD_VERIFICATION_CODE",
    "защитныйкод": "CARD_VERIFICATION_CODE",
    "защитныйкодкарты": "CARD_VERIFICATION_CODE",
    "кодбезопасностикарты": "CARD_VERIFICATION_CODE",
    "кодпроверкикарты": "CARD_VERIFICATION_CODE",
    "cvvкод": "CARD_VERIFICATION_CODE", "кодcvv": "CARD_VERIFICATION_CODE",
    "кодcvc": "CARD_VERIFICATION_CODE", "cidкод": "CARD_VERIFICATION_CODE",
    "кодcid": "CARD_VERIFICATION_CODE",
    # ISSUER_OTP — the dynamic one-time value. The LENGTH IS NOT ASSERTED
    # anywhere (see `pseudex/cvc.py`), so these keys are the class's whole
    # evidence: the field names the secret, the value is taken as written.
    "otp": "ISSUER_OTP", "otpcode": "ISSUER_OTP", "otpnumber": "ISSUER_OTP",
    "onetimecode": "ISSUER_OTP", "onetimepassword": "ISSUER_OTP",
    "verificationcode": "ISSUER_OTP", "smscode": "ISSUER_OTP",
    "smsкод": "ISSUER_OTP", "кодsms": "ISSUER_OTP", "кодсмс": "ISSUER_OTP",
    "3dscode": "ISSUER_OTP", "code3ds": "ISSUER_OTP",
    "code3dsecure": "ISSUER_OTP", "authcode": "ISSUER_OTP",
    "authenticationcode": "ISSUER_OTP",
    "карта": "CARD", "карты": "CARD", "card": "CARD",
    "почта": "EMAIL", "email": "EMAIL", "мейл": "EMAIL", "емейл": "EMAIL",
    "адрес": "LOC", "address": "LOC",
    # ОДНОЗНАЧНЫЕ КЛЮЧИ ДАТЫ РОЖДЕНИЯ. Просто «дата»/«date» сюда не годятся —
    # это дата доставки, счёта или встречи в подавляющем большинстве случаев, и
    # маскировать их значило бы ломать те самые вызовы, ради которых продукт
    # существует. А «birth_date» не может держать ничего другого.
    "датарождения": "DOB", "birthdate": "DOB", "dateofbirth": "DOB",
    "dob": "DOB", "birthday": "DOB", "деньрождения": "DOB",
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
    "account": "BANK_ACCOUNT", "accountnumber": "BANK_ACCOUNT",
    "рс": "BANK_ACCOUNT", "расчётныйсчёт": "BANK_ACCOUNT", "расчетныйсчет": "BANK_ACCOUNT",
    # --- the v6 checksum-carrying family: field keys -------------------------
    #
    # A KEY TYPES THE WHOLE VALUE (P03), so these are the registry's own
    # `field_keys`, cleaned the way `_key_type` cleans them (separators go:
    # `deal_uid` → `dealuid`). Two deliberate deviations, both recorded:
    #
    #   * `card_number` is NOT mapped to a loyalty card. `card` is already a
    #     stem above and in Russian traffic a `card_number` is a bank card far
    #     more often than a loyalty card; mistyping a bank card as a loyalty
    #     number would hand the model a 13-18 digit token for a PAN.
    #   * `uid` is safe as a PREFIX stem precisely because «uuid» does not start
    #     with it — an agent's own request id keeps its own type.
    "rqaccnum": "BANK_ACCOUNT", "bankaccount": "BANK_ACCOUNT", "accnum": "BANK_ACCOUNT",
    "ls": "BANK_ACCOUNT", "номерсчета": "BANK_ACCOUNT",
    "iban": "IBAN", "rqiban": "IBAN", "beneficiaryiban": "IBAN",
    "uid": "LOAN_UID", "dealuid": "LOAN_UID", "contractuid": "LOAN_UID",
    "uiddeal": "LOAN_UID", "loanuid": "LOAN_UID",
    "ogrnip": "OGRNIP", "rqogrnip": "OGRNIP",
    "enp": "OMS_ENP", "oms": "OMS_ENP", "omspolicy": "OMS_ENP", "polis": "OMS_ENP",
    "polisnumber": "OMS_ENP", "policynumber": "OMS_ENP",
    "npolis": "OMS_ENP", "spolis": "OMS_ENP", "vpolis": "OMS_ENP",
    "vin": "VIN", "вин": "VIN", "vincode": "VIN", "vehiclevin": "VIN",
    "vinnumber": "VIN",
    "epts": "EPTS_NUMBER", "eptsnumber": "EPTS_NUMBER", "номераптс": "EPTS_NUMBER",
    "uin": "UIN", "supplierbillid": "UIN", "paymentuin": "UIN", "уин": "UIN",
    "imei": "IMEI", "imei1": "IMEI", "imei2": "IMEI", "deviceimei": "IMEI",
    "imeisv": "IMEI",
    "iccid": "ICCID", "simiccid": "ICCID", "simnumber": "ICCID",
    "loyaltycard": "LOYALTY_CARD_NUMBER", "bonuscard": "LOYALTY_CARD_NUMBER",
    "discountcard": "LOYALTY_CARD_NUMBER",
    # --- the v6 identity-document family: field keys -------------------------
    #
    # A KEY TYPES THE WHOLE VALUE (P03), and these are the registry's own
    # `field_keys`, cleaned the way `_key_type` cleans them (`_KEY_CLEAN_RE`
    # removes separators, so `birth_cert_number` is `birthcertnumber`). Every key
    # below is also a PREFIX STEM, which is why four registry keys are DELIBERATELY
    # ABSENT rather than copied:
    #
    #   * `license` alone — a software licence is far commoner in Russian business
    #     traffic than a driver's licence, and a key types the value with no shape
    #     check, so `{"license": "MIT"}` would mint a 2-2-6 document number for it.
    #   * `dl` — a two-letter stem claims every key that begins with it.
    #   * `ву` — same argument, and Russian has words starting with it.
    #   * `doc_type` (BIRTH_CERT) — every schema has one, and it holds «passport»,
    #     not a document number.
    #
    # `sts`/`pts` are safe as stems because no other field key begins with them;
    # `passport` is already a stem above and keeps its v5 meaning (the internal
    # passport), so the international one is reached through its own keys.
    "intlpassport": "INTL_PASSPORT", "foreignpassport": "INTL_PASSPORT",
    "заграничныйпаспорт": "INTL_PASSPORT", "биометрическийпаспорт": "INTL_PASSPORT",
    "birthcert": "BIRTH_CERT", "marriagecertificate": "BIRTH_CERT",
    "marriagecert": "BIRTH_CERT", "divorcecertificate": "BIRTH_CERT",
    "deathcertificate": "BIRTH_CERT", "namechangecertificate": "BIRTH_CERT",
    "civilactcertificate": "BIRTH_CERT",
    "residencepermit": "RESIDENCE_PERMIT", "vnzh": "RESIDENCE_PERMIT",
    "виднажительство": "RESIDENCE_PERMIT", "внж": "RESIDENCE_PERMIT",
    "military": "MILITARY_ID", "военныйбилет": "MILITARY_ID",
    "военник": "MILITARY_ID",
    "driverlicense": "DRIVER_LICENSE", "driverlicence": "DRIVER_LICENSE",
    "dlnumber": "DRIVER_LICENSE",
    "водительскоеудостоверение": "DRIVER_LICENSE",
    "pts": "PTS_NUMBER", "ptsnumber": "PTS_NUMBER",
    "vehiclepassport": "PTS_NUMBER", "номерптс": "PTS_NUMBER",
    "sts": "STS_NUMBER", "stsnumber": "STS_NUMBER",
    "vehicleregistrationcertificate": "STS_NUMBER", "номерстс": "STS_NUMBER",
    # --- the v6 legal/court family: field keys -------------------------------
    #
    # A KEY TYPES THE WHOLE VALUE (P03), cleaned the way `_key_type` cleans it
    # (`_KEY_CLEAN_RE` removes separators, so `case_uid` is `caseuid`). These are
    # the registry's own `field_keys`, EXCEPT where a key names two different
    # things — and those are named below rather than guessed:
    #
    #   * `uid` is DELIBERATELY NOT re-mapped. The registry gives it to BOTH
    #     COURT_CASE_UID and LOAN_UID, and the checksum family already landed it
    #     as the loan УИД (the 33-hex ЦБ form). A key types with no shape check,
    #     so re-pointing it would break the bank identifier instead of separating
    #     the two — the court УИД is reached by `case_uid`/`court_uid`, and in
    #     prose by the «УИД»/«уникальный идентификатор дела» cue.
    #   * `уид` is omitted for the same reason: the registry names it for the
    #     court card only, but «УИД» in Russian business writing is the loan one
    #     at least as often, and the two cards' cues are the SAME word. The cue
    #     path separates them by SHAPE; a key could not.
    #   * `number` (ARBITRAZH) is not a key at all — it names nothing.
    #   * `ip_number`/`номер_ип` — the first is distinctive and mapped; the second
    #     is left out because «номер ИП» also names an individual entrepreneur's
    #     ОГРНИП, and typing a 15-digit ОГРНИП as an enforcement number would
    #     re-shape a document the customer's validator reads. ОГРНИП has its own
    #     key (`ogrnip`) above.
    #   * `case_number`/`номер_дела` are given to COURT_CASE_NO_SOU, the ordinary
    #     general-jurisdiction reading; ARBITRAZH keeps its own distinctive keys.
    #     The two share ONE identity key in `ru_pii_v6.legal_signature` and the
    #     mint preserves the SOURCE's variant, so a generic key can misname a
    #     label but can never re-shape or fork the value.
    "caseuid": "COURT_CASE_UID", "courtuid": "COURT_CASE_UID",
    "courtcaseuid": "COURT_CASE_UID",
    "arbitrcase": "ARBITRAZH_CASE_NO", "arbitrazhcase": "ARBITRAZH_CASE_NO",
    "arbitrazhcasenumber": "ARBITRAZH_CASE_NO",
    "bankruptcycase": "ARBITRAZH_CASE_NO",
    "casenumber": "COURT_CASE_NO_SOU", "courtcase": "COURT_CASE_NO_SOU",
    "номердела": "COURT_CASE_NO_SOU",
    "ipnumber": "FSSP_IP_NO", "fsspip": "FSSP_IP_NO",
    "enforcementnumber": "FSSP_IP_NO", "exeproduction": "FSSP_IP_NO",
    "execlistnumber": "EXEC_DOC_NO", "writnumber": "EXEC_DOC_NO",
    "исполнительныйлист": "EXEC_DOC_NO",
    "cadastralnumber": "CADASTRAL_NUMBER", "cadnum": "CADASTRAL_NUMBER",
    "кадастровыйномер": "CADASTRAL_NUMBER", "cadastral": "CADASTRAL_NUMBER",
    # --- the v6 finance family: field keys ------------------------------------
    #
    # A KEY TYPES THE WHOLE VALUE (P03), cleaned the way `_key_type` cleans it
    # (`_KEY_CLEAN_RE` removes separators, so `loan_id` is `loanid`). These are the
    # registry's own `field_keys`, EXCEPT where one registry key names THREE
    # different documents — and those are named below rather than guessed:
    #
    #   * `policy_number` / `policyNumber` belong to DMS_POLICY, OSAGO_POLICY and
    #     KASKO_POLICY at once, and the key ALREADY EXISTS in this map as `OMS`
    #     (the checksum family landed `policynumber`/`polis` for the ОМС policy).
    #     Re-pointing it would break the ОМС record the engine already protects —
    #     a v5 regression traded for a v6 label — so each finance policy gets its
    #     own distinctive keys (`dmspolicy`, `osagonumber`, `kaskopolicy`, …) and
    #     the shared key keeps its v5 meaning.
    #   * `insurance_policy` (DMS_POLICY) is omitted for the same reason: it names
    #     a health policy and a car policy with one word, and a key types with NO
    #     shape check.
    #   * `policySerial`/`policy_series` are given to OSAGO_POLICY, whose registry
    #     card is the only one that names a SERIES as a separate field.
    #
    # `dogovor` IS A PREFIX STEM and is the registry's own key: every key starting
    # with it is typed as a loan contract. Its price is measured and recorded in
    # TYPES.md — a B2B supply contract under `dogovor_postavki` is over-masked,
    # and the registry itself proposes `CONTRACT_NUMBER_B2B` as a negative that the
    # owner has not decided yet.
    "contractnumber": "LOAN_CONTRACT_NUMBER", "loanid": "LOAN_CONTRACT_NUMBER",
    "loannumber": "LOAN_CONTRACT_NUMBER",
    "creditagreementno": "LOAN_CONTRACT_NUMBER",
    "номердоговора": "LOAN_CONTRACT_NUMBER", "dogovor": "LOAN_CONTRACT_NUMBER",
    "credithistorycode": "CREDIT_SUBJECT_CODE",
    "subjectcode": "CREDIT_SUBJECT_CODE", "kodsubekta": "CREDIT_SUBJECT_CODE",
    "dmspolicy": "DMS_POLICY",
    "osagoseries": "OSAGO_POLICY", "osagonumber": "OSAGO_POLICY",
    "policyserial": "OSAGO_POLICY", "policyseries": "OSAGO_POLICY",
    "kaskopolicy": "KASKO_POLICY",
    "claimnumber": "INSURANCE_CLAIM_NUMBER", "claimid": "INSURANCE_CLAIM_NUMBER",
    "lossnumber": "INSURANCE_CLAIM_NUMBER", "ubytok": "INSURANCE_CLAIM_NUMBER",
    "medcard": "MEDCARD_NUMBER", "medcardnumber": "MEDCARD_NUMBER",
    "patientcard": "MEDCARD_NUMBER", "emkid": "MEDCARD_NUMBER",
    "historynumber": "MEDCARD_NUMBER",
    "lncode": "ELN_NUMBER", "prevlncode": "ELN_NUMBER",
    "nextlncode": "ELN_NUMBER", "eln": "ELN_NUMBER", "elnnumber": "ELN_NUMBER",
    "sickleavenumber": "ELN_NUMBER",
    "prescriptionid": "PRESCRIPTION_NUMBER",
    "recipenumber": "PRESCRIPTION_NUMBER", "rxnumber": "PRESCRIPTION_NUMBER",
    "recipeseries": "PRESCRIPTION_NUMBER",
    "referralid": "REFERRAL_NUMBER", "napravlenienumber": "REFERRAL_NUMBER",
    # --- the v6 telecom/device family: field keys -----------------------------
    #
    # A KEY TYPES THE WHOLE VALUE (P03), cleaned the way `_key_type` cleans it
    # (`_KEY_CLEAN_RE` removes separators, so `mac_address` is `macaddress` and
    # `x_forwarded_for` is `xforwardedfor`). These are the registry's own
    # `field_keys`, EXCEPT where a key already names something the engine
    # protects — and those are named below rather than guessed:
    #
    #   * `account_number` / `contract_number` (SUBSCRIBER_ACCOUNT) are
    #     DELIBERATELY ABSENT. Both already exist: the first is a bank ACCOUNT
    #     (20 digits, cbr515) and the second is the loan CONTRACT_NUMBER above
    #     (where «dogovor» is a prefix stem). A key types with NO shape check, so
    #     re-pointing either would mint a 12-digit operator account where a
    #     20-digit balance account or a loan agreement was meant — a v5
    #     regression traded for a v6 label, which the finance family already
    #     refused once (`policy_number`). The operator account is reached by
    #     `personal_account`/`personalaccount`, which is distinctive, and by its
    #     own cues in CTX_TYPES.
    #   * `ls` is DELIBERATELY ABSENT although the registry names it. It is a
    #     TWO-LETTER STEM: it would claim every key beginning with `ls`, and its
    #     census in this map is already the bank account («л/с» is the commonest
    #     spelling of a расчётный счёт in Russian business writing). The
    #     Russian-account reading is reached by the CTX_TYPES cue «л/с», whose
    #     shape is the 8–12 digit observation — where the bank account's own
    #     shape is twenty digits, so the two never meet.
    #   * `idfa` and `ios_ifa` name the ADVERTISING id (MOBILE_AD_ID); `idfv` and
    #     `app_set_id` name the VENDOR/app id (APP_DEVICE_ID). The registry keeps
    #     them apart and so does this map: an IDFA is a UUID a tracker reads
    #     across apps, an IDFV is one an app reads about itself.
    #   * `ip` is a PREFIX STEM and that is safe HERE for one checked reason:
    #     `ipnumber` is an EXACT key in this same map (FSSP enforcement), and
    #     `_key_type` asks the exact map FIRST — so the only keys the stem claims
    #     are ones beginning with `ip` and not already named.
    #   * `x_forwarded_for` is the proxy header's key, and its VALUE is a LIST of
    #     addresses. The key types it as one IP_ADDRESS; the list separator keeps
    #     the shape from matching across commas, so the first address is typed and
    #     the rest are reached by the bare v5 recognizer. The limit is recorded.
    "imsi": "IMSI", "subscriberimsi": "IMSI",
    "mac": "MAC", "macaddress": "MAC", "clientmac": "MAC", "bssid": "MAC",
    "ip": "IP_ADDRESS", "ipaddress": "IP_ADDRESS", "clientip": "IP_ADDRESS",
    "remoteaddr": "IP_ADDRESS",
    "xforwardedfor": "IP_ADDRESS",
    "oid": "ESIA_OID", "personoid": "ESIA_OID", "prnoid": "ESIA_OID",
    "esiaoid": "ESIA_OID", "sbjid": "ESIA_OID",
    "googleaid": "MOBILE_AD_ID", "iosifa": "MOBILE_AD_ID",
    "advertisingidentifier": "MOBILE_AD_ID", "gaid": "MOBILE_AD_ID",
    "idfa": "MOBILE_AD_ID", "adid": "MOBILE_AD_ID",
    "appmetricadeviceid": "APP_DEVICE_ID", "deviceid": "APP_DEVICE_ID",
    "idfv": "APP_DEVICE_ID", "appsetid": "APP_DEVICE_ID",
    "clientid": "METRICA_CLIENT_ID", "ymuid": "METRICA_CLIENT_ID",
    "ymclientid": "METRICA_CLIENT_ID",
    "personalaccount": "SUBSCRIBER_ACCOUNT",
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
    # --- the v6 utility/account/education/travel family: field keys -----------
    #
    # A KEY TYPES THE WHOLE VALUE (P03), cleaned the way `_key_type` cleans it
    # (`_KEY_CLEAN_RE` removes separators, so `unified_account` is
    # `unifiedaccount`). Every entry is also a PREFIX STEM, and this family adds
    # its stems LAST, so no key an EARLIER family already claimed can move — the
    # exact map is asked first and the stem walk keeps its order. SIX of the
    # registry's own keys are DELIBERATELY ABSENT, each for a reason that is
    # checked rather than guessed:
    #
    #   * `account`, `personal_account` and `ls` (UTILITY_ACCOUNT) already exist:
    #     the first and third are the v5 bank ACCOUNT («л/с» is the commonest
    #     spelling of a расчётный счёт in Russian business writing) and the second
    #     is the telecom family's SUBSCRIBER_ACCOUNT. Re-pointing any of them
    #     would mint a 6–12 digit ЖКХ account where a 20-digit balance account or
    #     an operator account was meant — a v5/telecom regression traded for a
    #     label, which the finance and telecom families already refused once.
    #     UTILITY_ACCOUNT is reached by `abonent_id`/`лицевой_счет`, which are
    #     distinctive, and by the letter-bearing cue.
    #   * `client_id` (CDP_CUSTOMER_ID) is the telecom family's METRICA_CLIENT_ID
    #     stem. The CRM reading keeps `customer_id`, `user_id`, `external_id` and
    #     `crm_id`.
    #   * `card_number` and `card_uid` (ACCESS_PASS_NUMBER) start with the v5
    #     `card` stem: a `card_number` in Russian traffic is a bank card, and
    #     re-pointing it would mint a six-to-twelve digit pass where a PAN was
    #     meant. The pass keeps `pass_number`, `access_card_id` and `badge_id`.
    #   * `account_login` (LOGIN) starts with the v5 `account` stem, and
    #     `diploma_series` (DIPLOMA_NUMBER) names ONE PART of a document, not the
    #     number: a key types the WHOLE value, so a six-digit series would mint a
    #     thirteen-digit diploma number. Both are recorded in TYPES.md; the
    #     composite-part machinery (`COMPOSITE_TYPES`) is the Lead's seam.
    "els": "GIS_ZHKH_ELS", "unifiedaccount": "GIS_ZHKH_ELS",
    "gkuid": "GIS_ZHKH_ELS", "paymentdocumentid": "GIS_ZHKH_ELS",
    "елс": "GIS_ZHKH_ELS",
    "abonentid": "UTILITY_ACCOUNT", "лицевойсчет": "UTILITY_ACCOUNT",
    "customerid": "CDP_CUSTOMER_ID", "userid": "CDP_CUSTOMER_ID",
    "externalid": "CDP_CUSTOMER_ID", "crmid": "CDP_CUSTOMER_ID",
    "login": "LOGIN", "username": "LOGIN",
    "diplomanumber": "DIPLOMA_NUMBER", "educationdocnumber": "DIPLOMA_NUMBER",
    "attestatnumber": "SCHOOL_CERT_NUMBER",
    "schoolcertificatenumber": "SCHOOL_CERT_NUMBER",
    "studentid": "STUDENT_ID_NUMBER", "studentcardnumber": "STUDENT_ID_NUMBER",
    "idnumber": "STUDENT_ID_NUMBER",
    "tabnumber": "EMPLOYEE_TAB_NUMBER", "personnelnumber": "EMPLOYEE_TAB_NUMBER",
    "employeenumber": "EMPLOYEE_TAB_NUMBER", "tabnum": "EMPLOYEE_TAB_NUMBER",
    "табельныйномер": "EMPLOYEE_TAB_NUMBER",
    "employmentcontractnumber": "EMPLOYMENT_CONTRACT_NUMBER",
    "laborcontractno": "EMPLOYMENT_CONTRACT_NUMBER",
    "passnumber": "ACCESS_PASS_NUMBER", "accesscardid": "ACCESS_PASS_NUMBER",
    "badgeid": "ACCESS_PASS_NUMBER",
    "pnr": "PNR", "recordlocator": "PNR", "bookingreference": "PNR",
    "bookingcode": "PNR",
    "ticketnumber": "E_TICKET_NUMBER", "eticket": "E_TICKET_NUMBER",
    "ticketno": "E_TICKET_NUMBER",
}

# --- composite objects: the PARENT KEY types its CHILDREN -----------------
#
# «Родительский ключ типизирует детей» — одно правило, и до сих пор оно было
# написано ровно один раз и жёстко под LOC (`structured._address_object_spans`):
# роли city/street/house/flat, причём street и house обязательны. Поэтому в
# одном и том же payload объект `address` закрывался целиком, а
# `{"passport": {"series": "4608", "number": "246256"}}` уходил открытым: 4 и 6
# цифр без контрольной суммы не берёт НИ ОДИН shape-рекогнайзер, а `_JSON_KV`
# матчит только строковые значения и родительский ключ вовсе не видит.
# 24 утечки g09 (`document-027…-048`), клетка `form:OUT/tool_arg PASSPORT 0/22`.
#
# Здесь — только СЛОВАРЬ ЧАСТЕЙ: тип уже в `KEY_TYPE` («passport» →
# PASSPORT), не хватало карты «тип → роли». Порядок ролей — тождество
# документа, поэтому он объявлен списком, а не выводится из `json.dumps`.
#
# ДЛИНА КАЖДОЙ ЧАСТИ — часть конвенции документа, а не догадка: серия
# российского паспорта 4 цифры, номер 6. По ней подмена раскладывается обратно
# по полям и по ней же листья складываются в целое при восстановлении.
COMPOSITE_TYPES: dict[str, dict[str, object]] = {
    "PASSPORT": {
        "roles": {
            "series": ["series", "ser", "серия", "rqidentdocser", "identdocser"],
            "number": ["number", "num", "номер", "rqidentdocnum", "identdocnum"],
        },
        "lengths": {"series": 4, "number": 6},
        "order": ["series", "number"],
        "required": ["series", "number"],
    },
}

# --- context-anchored document types -------------------------------------

# (entity type, cue words, digit shape). Their digit shapes collide with each
# other and with ordinary business numbers: a driver's licence, a vehicle
# registration and a passport are all `NN NN NNNNNN`. The cue word is what makes
# the type — and the type matters, not just the masking: mistyping a licence as a
# phone replaces it with a fake PHONE.
CTX_TYPES: tuple[tuple[str, str, str], ...] = (
    # THE REGISTRY'S PRINTED VARIANTS ARE PART OF THE GRAMMAR: ОМС «слитно, 4×4»,
    # an account «4×5», an ОГРНИП «324 77 000012345 5», a 19-digit ICCID. A shape
    # that demands the glued form is the shape the customer who copies off their
    # own document does not have — the lesson the СНИЛС separators already taught
    # («112 233 445 95»). Exactly N digits with an OPTIONAL single separator
    # between any two of them; where a checksum exists it is asked of the digits.
    # THE LABEL IS THE REGISTRY ID (G7 follow-up, 02.10.2026). `engine_labels` in
    # `pii_types.py` records that this family used to emit the v5-internal «OMS»
    # while the benchmark's `typed` axis reads `OMS_ENP`: the value was masked,
    # the TYPE was not, and 34 of 34 gold spans scored as misses. The engine's
    # own vocabulary stays available to the vault through
    # `ru_pii_v6.engine_label()`, so the row, the audit trail and every mint
    # branch that used to key on «OMS» are unchanged.
    ("OMS_ENP", r"омс|полис|медполис|мед\.?\s*полис|\bенп\b|номер полиса|единый номер полиса",
     r"\d(?:[ .-]?\d){15}"),
    # «реквизиты» belongs here and not only among the KV keys: the KV layer needs
    # a `key: value` shape, and a customer writing prose puts the word and the
    # number a space apart. Persona 1 produced both in ONE sentence — «счёт
    # 4081…, реквизиты 4081…» — and watched the same value be masked once and
    # leak once.
    # THE NEGATIVE FAMILIES MOVE INTO THE SHAPE. This entry is a v6
    # `BANK_ACCOUNT` (the registry's `engine_labels` for it is «ACCOUNT»), and
    # the v6 negative families `CORR_ACCOUNT`/`LEGAL_ACCOUNT`/`TREASURY_ACCOUNT`
    # are refused by `ru_pii_v6.is_business_account` in `ru_pii.detect_structured`
    # — a guard that keys on the OLD label and therefore no longer sees this
    # entry. The exclusion is stated in the leased shape instead, with the SAME
    # prefix rule and the SAME separator class the shape itself allows, so a
    # legal entity's account is never typed as a person's (152-ФЗ ст. 3 п. 1;
    # the guard and the shape agree by construction — `test_pii_v6` pins it).
    ("BANK_ACCOUNT", r"счёт|счет|р/с|л/с|лицев\w* счёт|номер счёта|текущ\w* счёт|"
                     r"счёт вклада|расчётн\w*|расчетн\w*|реквизит\w*|"
                     r"зачислить на|перевести на счёт",
     r"(?!30[ .-]?1|40[ .-]?7|03100|40[ .-]?10)\d(?:[ .-]?\d){19}"),
    ("DRIVER_LICENSE", r"водительск\w*|в/у|удостоверени\w* водител\w*|прав[аои]",
     r"\d{2}\s?\d{2}\s?\d{6}"),
    # STS_NUMBER (registry id): the digit-only reading. The v5 label was
    # `VEHICLE_DOC`, which covered СТС and ПТС together; see the identity block
    # below for why the two are now separate ids on the span.
    ("STS_NUMBER", r"стс|птс|свидетельств\w* о регистрации", r"\d{2}\s?\d{2}\s?\d{6}"),
    # Two digits of series, seven of number. The separator is OPTIONAL and was
    # missing: `\d{9}` matched only `711234567`, while the form actually printed
    # in the document and typed by people — `71 1234567` — went undetected. The
    # sibling document patterns above always allowed `\s?` between groups; this
    # one did not, and nothing tested the spaced form.
    ("INTL_PASSPORT", r"загранпаспорт\w*|заграничн\w* паспорт\w*", r"\d{2}\s?\d{7}"),
    # --- the v6 checksum-carrying family: cue -> shape -----------------------
    #
    # THE CUE TYPES THE VALUE, THE CHECKSUM ONLY GATES A BARE ONE (the rule
    # already written for СНИЛС above). That is COV-TYPED-INVALID: behind
    # «полис ОМС» a one-digit typo is still the customer's ОМС, and the checksum
    # gate must not send it to the model in the clear. Shapes are the registry
    # cards' own grammar; the checksum arithmetic lives in `pseudex/ru_pii_v6.py`.
    #
    # IBAN: country + key + BBAN, glued or printed in groups of four.
    ("IBAN", r"\biban\b|айбан|международн\w* номер счёта",
     r"(?i:[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,8})"),
    # УИД: the dashed UUID form and the 33-hex glued one.
    ("LOAN_UID", r"\bуид\b|уникальн\w* идентификатор договора|идентификатор сделк\w*|"
                 r"uid договора",
     r"(?i:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}-[0-9a-f]|[0-9a-f]{33})"),
    # ОГРНИП: the cue path protects a faulty check digit; the bare valid form is
    # the v5 recognizer and stays (`COV-INTEGRATION-KEEP-V5`).
    ("OGRNIP", r"огрнип|огрн\s*ип|рег\.?\s*номер\s*ип", r"\d(?:[ -]?\d){14}"),
    # VIN: the ГОСТ form (13 alphanumerics + four digits) AND the Cyrillic
    # look-alikes a keyboard layout leaves behind («ХТА…»), which normalisation
    # does not fold — it folds digits only inside digit-dense runs.
    ("VIN", r"\bvin\b|\bвин\b|вин-код|идентификационн\w* номер|номер кузова|"
            r"номер шасси|\bкузов\b|\bрама\b",
     r"(?i:[0-9A-HJ-NPR-ZА-ЯЁ]{13}[0-9]{4})"),
    ("EPTS_NUMBER", r"эптс|электронн\w* птс|электронн\w* паспорт|номер эп|эпсм",
     r"[123]\d{3}0[1-4]\d{9}"),
    ("UIN", r"\bуин\b|уникальн\w* идентификатор начислени\w*|номер постановлени\w*|"
            r"индекс документа|код \(поле 22\)",
     r"\d(?:[ .-]?\d){19}|\d(?:[ .-]?\d){24}"),
    ("IMEI", r"\bimei\b|\bимей\b|\bimei1\b|\bimei2\b|серийн\w* номер телефона|\*#06#",
     r"\d{2}(?:[ -]?\d{6}){2}[ -]?\d"),
    ("ICCID", r"\biccid\b|\bicc\b|номер сим-карты|номер sim|серийн\w* номер сим",
     r"\d(?:[ .-]?\d){18,19}"),
    ("LOYALTY_CARD_NUMBER", r"карта лояльности|бонусн\w* карта|дисконтн\w* карта|"
                            r"клубн\w* карта|номер карты покупателя",
     r"\d(?:[ .-]?\d){12,17}"),
    # --- the v6 identity-document family: cue -> shape -----------------------
    #
    # NO CHECKSUM EXISTS FOR THESE (the registry gives none), so the cue and the
    # shape are the WHOLE mechanism, and `bare_typed=False` on every one of the
    # eight says a bare value is not typed. Three of them —
    # BIRTH_CERT, CIVIL_ACT_CERT, RESIDENCE_PERMIT — carry
    # `grammar_status == "ГРАММАТИКА?"`, i.e. the ministry order that composes the
    # series was not obtained; their shapes below are exactly what the registry's
    # own sample proves and nothing more (`ru_pii_v6.GRAMMAR_UNASSERTED`). No
    # permissive regex was invented to widen them.
    #
    # The separator class `[ .-]?` is the registry's `form_features`
    # («none/space/hyphen/dot/other») — a shape that demands the glued form is the
    # shape the customer copying off their own document does not have.
    #
    # INTL_PASSPORT: two digits of series, seven of number, and the registry's
    # other cue words. The v5 cue above covered «загранпаспорт»; «биометрический
    # паспорт» and «паспорт для выезда» reached nothing at all.
    ("INTL_PASSPORT", r"биометрическ\w* паспорт|паспорт для выезда|загранник\w*|"
                      r"загран\w*",
     r"\d{2}[ .-]?\d{7}"),
    # BIRTH_CERT / CIVIL_ACT_CERT: <roman>-<2 Cyrillic capitals> № <6 digits>.
    # The Roman numeral may be typed with the Cyrillic «І»/«Х» a Ukrainian layout
    # leaves behind — `_BIRTH_CERT_RE` (the v5 bare recognizer) knows only Latin
    # «IVX», so the cue path is what closes that variant. CIVIL_ACT_CERT shares
    # the engine label: the grammar is literally «как BIRTH_CERT» and the v5 bare
    # recognizer already types this shape BIRTH_CERT at priority 7, so a new label
    # would lose its own overlap (see ru_pii_v6 §identity and DELTA.json).
    ("BIRTH_CERT", r"свидетельств\w* о рождении|св-во о рождении|"
                   r"свид-во о рожд|свидетельство ребенка|\bСОР\b|"
                   r"свидетельств\w* о браке|о заключении брака|"
                   r"о расторжении брака|свидетельств\w* о смерти|о смерти|"
                   r"о перемене имени|об установлении отцовства|об усыновлении|"
                   r"о рождении",
     r"[IVXІХ]{1,4}[ .-]{0,3}[А-ЯЁ]{2}[ .-]{0,3}№?[ .-]{0,3}\d{6}"),
    # RESIDENCE_PERMIT: серия «82»/«83» + seven digits. The series is a CLOSED set
    # in the registry's own grammar, so the shape is conservative by construction.
    ("RESIDENCE_PERMIT", r"вид на жительство|вид на жит\.|\bВНЖ\b|\bвнж\b|"
                         r"residence permit",
     r"8[23][ .-]?\d{7}"),
    # MILITARY_ID: two capitals (Cyrillic on paper, Latin off a keyboard) and
    # seven digits, with or without «№». Only the «№» form is free of the v5 plate
    # recognizer's overlap — see ru_pii_v6 §identity.
    ("MILITARY_ID", r"военн\w* билет|военник|в/б|military id",
     r"[А-ЯЁA-Z]{2}[ .-]?№?[ .-]?\d{7}"),
    # DRIVER_LICENSE: the registry's «вод. удостоверение» reached the phone
    # recognizer instead (ten digits, 2-2-6 — libphonenumber reads it as a number),
    # so the v5 cue list is completed here with the abbreviation it was missing.
    ("DRIVER_LICENSE", r"вод\.?\s*удостоверени\w*|права на управление",
     r"\d{2}[ .-]?\d{2}[ .-]?\d{6}"),
    # PTS_NUMBER: two digits, two letters, six digits. THE v5 ENTRY ABOVE CANNOT
    # SEE IT — its shape is digit-only — so «ПТС 77 УК 123456» was typed PLATE
    # («УК 123456», priority 5) and the series went to the model in the clear.
    # THE v5 LABEL `VEHICLE_DOC` COVERED BOTH DOCUMENTS, AND THE SPAN NOW CARRIES
    # THE REGISTRY ID. G7 (02.10.2026) measured the cost: 35/35 ПТС and 35/35 СТС
    # were masked under `VEHICLE_DOC` and scored 0% recall on the benchmark's
    # `typed` axis. The two entries were ALREADY split by shape — letters vs
    # digits — so naming them is the label change only, and the vault keeps one
    # identity key for both (`ru_pii_v6.engine_label` maps either id back to
    # `VEHICLE_DOC`, which is the label `identity_signature` puts in the key).
    ("PTS_NUMBER", r"\bПТС\b|паспорт транспортного средства|паспорт ТС|"
                   r"\bPTS\b",
     r"\d{2}[ .-]?[А-ЯЁA-Z]{2}[ .-]?\d{6}"),
    # STS_NUMBER: the same document family, digit-only. The v5 entry above allows
    # only WHITESPACE between the groups, so «СТС 77-12-345678» fell through to the
    # phone recognizer (ten digits, 2-2-6) and the customer's licence plate of a
    # certificate was replaced by a fake PHONE. The registry's separators are
    # space/hyphen/dot/other, and its groupings are «2-2-6» and «4-6».
    ("STS_NUMBER", r"\bСТС\b|свидетельств\w* о регистрации ТС|"
                   r"свидетельств\w* о регистрации транспортного средства",
     r"(?:\d{2}[ .-]?\d{2}|\d{4})[ .-]?\d{6}"),
    # --- the v6 legal/court family: cue -> shape -----------------------------
    #
    # ALL SIX ARE `bare_typed=False`, so the cue or the field key is the WHOLE
    # evidence and NOT ONE bare anchor is added here. None carries a checksum
    # (the registry gives `generated_checksum == ""` to every one of them), so
    # there is nothing to gate a bare run with: the shapes below are the
    # registry's own grammar and the arithmetic-free module that reads them is
    # `pseudex/ru_pii_v6.py` §legal.
    #
    # EXEC_DOC_NO is `grammar_status == "ГРАММАТИКА?"` (ПП № 579 describes the
    # blank, the series composition was not asserted): its shape is the registry's
    # grammar VERBATIM and the constant that names it is
    # `ru_pii_v6.LEGAL_GRAMMAR_UNASSERTED`.
    #
    # COURT_CASE_UID: the Инструкция СД № 36 form, 22 characters. The two letters
    # are `[A-Z]` in the registry's grammar, but the record's `form_features` name
    # `script` and the frozen FORM fixture pairs «77ОС0000-…» with «77OS0000-…»
    # as ONE document — so the Cyrillic twins are accepted and `legal_signature`
    # folds them (`value_notation: glyph_fold`). The dashes follow the record's
    # `separators` feature and may be absent.
    ("COURT_CASE_UID", r"\bуид\b|уникальн\w* идентификатор дела",
     r"\d{2}[A-ZА-ЯЁ]{2}\d{4}[ .\-]?\d{2}[ .\-]?\d{4}[ .\-]?\d{6}[ .\-]?\d{2}"),
    # ARBITRAZH_CASE_NO: five variants in the registry's own grammar — ordinary,
    # bankruptcy (a second numeric group), appeal (АП), cassation (Ф) and the
    # intellectual-rights court (С01). «А»/«Ф»/«С»/«АП» are the TYPE and are never
    # replaced by the mint; the Latin twins are admitted for the `script`/`glyph`
    # features, the same widening VIN already carries.
    ("ARBITRAZH_CASE_NO", r"дело №|по делу|арбитражн\w* дело|"
                          r"дело о банкротств\w*|обособленн\w* спор",
     r"(?:[АA]\d{2}-\d{1,7}-\d{1,5}/\d{4}"
     r"|[АA]\d{2}-\d{1,7}/\d{4}"
     r"|\d{2}[АA][ПP]-\d{1,7}/\d{4}"
     r"|[ФF]\d{2}-\d{1,7}/\d{4}"
     r"|[СC]01-\d{1,7}/\d{4}"
     # THE SQUEEZED SPELLING (G7 follow-up, 02.10.2026 — NOT one of the brief's
     # six). «А11-14094/2024» reaches the corpus message as «A11140942024» and
     # the dashed grammar read NONE of the 34 gold spans: 0% recall, 0% coverage.
     # The squeeze drops the TYPE letter nowhere and the digits are the record's
     # own groups (2 + 1..7 + 4), so the separator-free form is `[АA]` and 7–13
     # digits, token-bounded. `[АA]` accepts the Latin twin the glyph fold
     # produces, exactly as the dashed alternatives above already do.
     r"|(?<![0-9A-Za-zА-Яа-яЁё])[АA]\d{7,13}(?![0-9A-Za-zА-Яа-яЁё]))"),
    # COURT_CASE_NO_SOU: the general-jurisdiction case number, Инструкция СД № 36
    # п. 3.14. The leading group is one or two digits with an optional INDEX
    # LETTER («2а-456/2026») or «М» for a materials proceeding; the letter is
    # grammar, not content. «дело №» and «по делу» are shared with ARBITRAZH and
    # the SHAPE is what tells the two apart — the registry's own cards overlap
    # here, and both readings are offered rather than one being guessed.
    ("COURT_CASE_NO_SOU", r"дело №|гражданск\w* дело|по делу|"
                          r"судебн\w* приказ\s*№?|производство №",
     r"(?:\d{1,2}[а-я]?|[МM])-\d{1,6}/\d{4}"
     # THE SQUEEZED SPELLING (G7 follow-up). «2-13/2015» reaches the corpus as
     # «2132015» and the dashed shape read 1 of 35: 0% recall, 2.9% coverage.
     # The record's own groups are 1–2 + 1–6 + 4 digits, so the separator-free
     # form is a bare 6–12-digit run — cue-gated on «дело №»/«по делу», which is
     # the strongest evidence in this family, and token-bounded on both sides.
     # THE FAMILY'S PRIORITY IS RAISED WITH IT (see PRIORITY): an eleven-digit
     # case number beginning with 7 is what libphonenumber reads as a PHONE, and
     # at the default rank of 1 the bare shape lost the span to it (the sweep's
     # label-desync list names exactly that, `COURT_CASE_NO_SOU -> PHONE`).
     r"|(?<!\d)\d{6,12}(?!\d)"),
    # FSSP_IP_NO: two shapes, and the CUES ARE SPLIT BETWEEN THEM ON PURPOSE.
    # Alternative 1 carries the «-ИП»/«-СД» suffix, which is an anchor of its own;
    # alternative 2 (`12345/24/77001/12`) is four bare groups and would be a
    # fraction under a generic cue, so «ИП»/«пристав» reach alternative 1 only and
    # alternative 2 needs the words that cannot mean anything else.
    ("FSSP_IP_NO", r"исполнительн\w* производств\w*|номер ИП|ИП №|"
                   r"сводн\w* производств\w*|\bФССП\b|пристав",
     r"\d{1,7}/\d{2}/\d{5}-(?:[ИI][ПP]|[СC][ДD])"
     # THE SQUEEZED SPELLING, WHICH IS THE ONE THE CORPUS WRITES. The separators
     # graded «842899/97/31188-ИП» into «8428999731188ИП» (G7 §2: gold with
     # separators, message without), and the dashed alternative above cannot read
     # it. The `-ИП`/`-СД` suffix survives the squeeze and IS the anchor: the
     # groups are 1–7 + 2 + 5 digits glued, so the shape is 8–14 digits then the
     # suffix — narrower than any bare digit run, and cue-gated on top.
     #
     # THE SUFFIX ACCEPTS THE GLYPH TWINS. `squeeze`+`glyph_fold` is what the
     # corpus applies, so «СД» arrives as «CД» — Latin C, Cyrillic Д, the exact
     # pair `VIN_ALPHABET`-style folding produces — and 18 of 35 spans were missed
     # while the shape demanded Cyrillic only.
     r"|\d{8,14}(?:[ИI][ПP]|[СC][ДD])"),
    ("FSSP_IP_NO", r"исполнительн\w* производств\w*|сводн\w* производств\w*|"
                   r"\bФССП\b|судебн\w* пристав",
     r"\d{1,7}/\d{2}/\d{2}/\d{2}"),
    # EXEC_DOC_NO: two capitals and nine digits. The registry's cue list names
    # «серия ФС» — a cue that ENDS with the grammar's own two letters, so a
    # pattern demanding the shape immediately after it can never fire on
    # «серия ФС 012345678». The cue is therefore «серия», and the SHAPE is what
    # carries «ФС». «ИЛ» is anchored on word boundaries: it is a real word in no
    # other reading here, but a two-letter stem inside a longer word is not it.
    ("EXEC_DOC_NO", r"исполнительн\w* лист|исполнительн\w* документ|"
                    r"исп\. лист|серия|(?<!\w)ИЛ(?!\w)",
     r"[А-ЯЁA-Z]{2}\s?№?\s?\d{9}"),
    # CADASTRAL_NUMBER: Приказ П/0183 п. 3. The three separators are MANDATORY —
    # the registry's grammar writes colons and the record is `bare_typed=False`,
    # so a separator-free spelling (an unanchored digit run) is NOT claimed here.
    # The record's own `separators` feature names the closed list, and the shape
    # takes it; `case_class`/`script` have `abstain` for «none», so there are no
    # letters to widen.
    #
    # G7 FOLLOW-UP (02.10.2026), AND THIS ONE WAS NOT IN THE BRIEF'S SIX. The
    # corpus's squeeze removes the colons, so «43:72:743493:8225» reaches the
    # message as «43727434938225» and the mandatory-separator shape read NONE of
    # the 35 gold spans: 0% recall, 0% coverage — the single largest remaining
    # leak after the six (35 of the 284 message-level misses). The separator-free
    # spelling IS this record's own digit run (2+2+6..7+1..5 = 11–16 digits), and
    # it is claimed behind the SAME cues and with `(?<!\d)`/`(?!\d)` on both
    # sides, so an unanchored run is still not a cadastral number.
    ("CADASTRAL_NUMBER", r"кадастр\w*|кад\.?\s*номер|\bКН\b",
     r"\d{2}[ .\-/:]\d{2}[ .\-/:]\d{6,7}[ .\-/:]\d{1,10}"
     r"|(?<!\d)\d{11,16}(?!\d)"),
    # --- the v6 finance/insurance/medical family: cue -> shape ----------------
    #
    # ALL TEN ARE `bare_typed=False` AND NONE CARRIES A CHECKSUM (the registry
    # gives every one `generated_checksum == ""`), so the cue or the field key is
    # the WHOLE evidence and NOT ONE bare anchor is added here. Eight of the ten
    # are FREE-FORM («национальной НЕТ») — the registry's grammar names the forms
    # its authors saw, not a standard — so the shape below is the conservative
    # shape rule `pseudex/ru_pii_v6.py §finance` states, and the two constants that
    # name its limits are `ru_pii_v6.FINANCE_GRAMMAR_UNASSERTED` (OSAGO_POLICY —
    # the РСА/НСИС primary source was not obtained; REFERRAL_NUMBER — national
    # grammar not established) and the shape's own two guards:
    #
    #   * A DATE IS NOT CLAIMED. A typed span CONTAINS the DATE span the v5
    #     recognizer already found and therefore REPLACES it, so «история болезни
    #     12.03.2020» would hand the model a fake medcard number where the
    #     customer's date stood and the agent's date field would get a number. The
    #     lookahead `(?!\d{1,2}[.]\d{1,2}[.]\d{2,4})` / `(?!(?:19|20)\d{2}-\d{2}-
    #     \d{2})` is the one place that can refuse it.
    #   * A SPACE JOINS EXACTLY TWO GROUPS. The registry's own spaced sample is
    #     «45 0012345678» (PRESCRIPTION_NUMBER) and the printed forms allow a
    #     letter prefix joined by `.-/` («001SB12345678», «12-345678/2025»,
    #     «МФО-2025-0012345»). A repeating space gap would let the date of the
    #     NEXT word be swallowed into the value, so the space alternative is
    #     written out separately and bounded.
    #
    # THE CUES ARE THE REGISTRY'S OWN, WITH FOUR DELIBERATE OMISSIONS, each named
    # because each was a measured over-mask risk and not a convenience:
    #
    #   * DMS_POLICY drops «страховка» and «номер полиса»: «полис» is ALREADY the
    #     ОМС cue above (`omspolicy`, and the ОМС shape is exact-16 digits), and
    #     «страховка» alone introduces a phone number at least as often as a
    #     policy. «ДМС», «карта ДМС» and «добровольное медицинское» carry the type.
    #   * INSURANCE_CLAIM_NUMBER drops the bare «номер дела»: the legal family's
    #     ARBITRAZH/СОУ cues are «дело №»/«по делу» and a claim is «страховое
    #     дело»/«номер выплатного дела» — a bare «номер дела» would type a court
    #     case number as an insurance claim.
    #   * REFERRAL_NUMBER drops the bare «направление»: the registry itself says
    #     the word means a DIRECTION or a DEPARTMENT far more often, so the cue
    #     demands the document reading — «номер направления», «электронное
    #     направление», or «направление на <диагностику>».
    #   * LOAN_CONTRACT_NUMBER keeps the registry's «договор №» even though it also
    #     introduces B2B supply contracts: that is the registry's own cue, the
    #     owner's `CONTRACT_NUMBER_B2B` question is still open (OD-28), and
    #     dropping it would send a consumer loan contract to the model in the clear.
    ("LOAN_CONTRACT_NUMBER",
     r"кредитн\w* договор\w*|договор\w* займ\w*|договор\w*\s*№|"
     r"договор\w* потребительск\w*|номер договора|займ\w*\s*№|\bКД\s*№",
     r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
     r"(?:(?<!\+)(?:[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)?"
     r"\d(?:(?:[.\-/]{0,2}|[.\-/]?[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)\d){7,19}"
     r"|\d{2,8} \d{2,12})"),
    # CREDIT_SUBJECT_CODE is the one record with a REAL grammar (Указание ЦБ
    # 6474-У п. 1.3): 4–15 characters, digits plus letters of ONE alphabet, case
    # insensitive. All three facts are in the shape, and the single-alphabet clause
    # is enforced rather than assumed — folding two alphabets into one key would
    # merge two different subjects' codes.
    ("CREDIT_SUBJECT_CODE",
     r"код субъекта кредитной истории|код субъекта|\bкод КИ\b|"
     r"дополнительн\w* код|код для ЦККИ",
     r"(?:(?=[A-Za-z0-9]{4,15}(?![A-Za-z0-9]))(?=[A-Za-z]*\d)(?=\d*[A-Za-z])"
     r"[A-Za-z0-9]{4,15}"
     r"|(?=[А-Яа-яЁё0-9]{4,15}(?![А-Яа-яЁё0-9]))(?=[А-Яа-яЁё]*\d)"
     r"(?=\d*[А-Яа-яЁё])[А-Яа-яЁё0-9]{4,15})"),
    ("DMS_POLICY",
     r"\bДМС\b|карт\w* ДМС|добровольн\w* медицинск\w*",
     r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
     r"(?:(?<!\+)(?:[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)?"
     r"\d(?:(?:[.\-/]{0,2}|[.\-/]?[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)\d){5,19}"
     r"|\d{2,8} \d{2,12})"),
    # OSAGO_POLICY is `ГРАММАТИКА?`: the primary source was not obtained and the
    # «12 letters a series may use» restriction is explicitly unverified, so the
    # series class takes ANY three capitals — Cyrillic («ХХХ», «ТТТ», «ААН») or the
    # Latin «XXX» a form prints — and the shape asserts only the composition the
    # registry states. The optional «№»/«номер» covers the printed order «серия ТТТ
    # номер 7012345678».
    ("OSAGO_POLICY", r"ОСАГО|автогражд\w*|"
                     r"страховк\w* на машин\w*",
     r"(?:[А-ЯЁ]{3}|[A-Z]{3})[ .\-]?(?:№|N|номер)?[ .\-]?\d{10}(?!\d)"),
    ("KASKO_POLICY", r"КАСКО|добровольн\w* автострахован\w*",
     r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
     r"(?:(?<!\+)(?:[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)?"
     r"\d(?:(?:[.\-/]{0,2}|[.\-/]?[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)\d){5,19}"
     r"|\d{2,8} \d{2,12})"),
    # INSURANCE_CLAIM_NUMBER: «У-671-475136/25», «0012345678-001»,
    # «ОСАГО-25-123456». The cue list keeps the registry's «номер убытка»,
    # «убыток №», «страховое дело», «номер выплатного дела» and drops the bare
    # «номер дела» — see the omission note above.
    ("INSURANCE_CLAIM_NUMBER",
     r"номер убытка|убыт\w*\s*№|страхов\w* дело|выплатн\w* дело|"
     r"номер страхового дела|номер выплатного дела",
     r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
     r"(?:(?<!\+)(?:[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)?"
     r"\d(?:(?:[.\-/]{0,2}|[.\-/]?[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)\d){4,19}"
     r"|\d{2,8} \d{2,12})"),
    # MEDCARD_NUMBER: «12345/2024» and a department prefix. The registry's
    # `digits` needle names «если ≥4», which is the bound here.
    ("MEDCARD_NUMBER",
     r"медкарт\w*|медицинск\w* карт\w*|амбулаторн\w* карт\w*|"
     r"истори\w* болезн\w*|\bЭМК\b|номер карты пациента",
     r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
     r"(?:(?<!\+)(?:[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)?"
     r"\d(?:(?:[.\-/]{0,2}|[.\-/]?[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)\d){3,19}"
     r"|\d{2,8} \d{2,12})"),
    # ELN_NUMBER: the СФР specification says «xs:string, Макс.длинна: 12» and every
    # example the emitter prints is twelve digits on «9000…», so the shape claims
    # the digit form and nothing shorter or longer. A 12-digit ИНН is a DIFFERENT
    # personal identifier and not a negative — the cue is what separates them, and
    # the typed span beats the bare ИНН span on the same characters.
    ("ELN_NUMBER",
     r"\bЭЛН\b|больничн\w*|листок нетрудоспособности|"
     r"лист\w* нетрудоспособности|номер больничного|"
     r"электронн\w* больничн\w*",
     r"(?<!\d)\d{12}(?!\d)"),
    # PRESCRIPTION_NUMBER: бумажный бланк 148-1/у-04(л) — серия с кодом субъекта
    # (две первые цифры ОКАТО) + номер; the electronic one is a regional ГИС
    # number, which is why the shape is the free-form one and the cue is the
    # evidence. The registry's own sample is the spaced form.
    ("PRESCRIPTION_NUMBER", r"рецепт\w*",
     r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
     r"(?:(?<!\+)(?:[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)?"
     r"\d(?:(?:[.\-/]{0,2}|[.\-/]?[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)\d){3,19}"
     r"|\d{2,8} \d{2,12})"),
    # REFERRAL_NUMBER is `ГРАММАТИКА?` — 057/у-04 and the МИС/РЕГИЗ electronic
    # referrals, national grammar NOT established. Its cue is the narrowest in the
    # family because «направление» alone means a direction or a department far more
    # often (see the omission note above).
    #
    # G7 (02.10.2026): THE OMISSION OF THE BARE «направление» WAS THE WHOLE GAP —
    # 34/34 gold spans were missed with 0% coverage, and the corpus cue is exactly
    # «направление <13 digits>». The registry's own `cues` field names it
    # («направление»), so it is admitted here. The over-mask risk the old note
    # feared is real and is bounded by the SHAPE, not by the cue list: the shape
    # requires at least five digits in groups, so «направление деятельности» and
    # «направление в отдел» stay open, and `test_v6_gaps` pins both.
    ("REFERRAL_NUMBER",
     r"направлени\w*",
     r"(?!\d{1,2}[.]\d{1,2}[.]\d{2,4}(?!\d))(?!(?:19|20)\d{2}-\d{2}-\d{2}(?!\d))"
     r"(?:(?<!\+)(?:[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)?"
     r"\d(?:(?:[.\-/]{0,2}|[.\-/]?[A-Za-zА-Яа-яЁё]{1,5}[.\-/]?)\d){4,19}"
     r"|\d{2,8} \d{2,12})"),
    # --- the v6 telecom/device family: cue -> shape ---------------------------
    #
    # ALL EIGHT ARE `bare_typed=False` AND NONE CARRIES A CHECKSUM (the registry
    # gives every one `generated_checksum == ""`), so the cue or the field key is
    # the WHOLE evidence for the six that have no v5 recognizer. MAC and
    # IP_ADDRESS are the exception, and it is named here rather than smoothed
    # over: `detect_vehicle_ids` already reads `\b(?:[0-9A-Fa-f]{2}[:-]){5}
    # [0-9A-Fa-f]{2}\b` with no cue at all, and the v5 IPv4 regex already reads a
    # bare dotted quad. Those bare anchors STAY (`COV-INTEGRATION-KEEP-V5`); what
    # these entries add is what v5 cannot see — the Cisco `001A.2B3C.4D5E`
    # grouping, IPv6, the Cyrillic hex twins, and the field keys that name the
    # value in a JSON payload.
    #
    # THE SHAPES ARE THE SHAPES `pseudex/ru_pii_v6.py §telecom` COMPILES, and
    # `test_pii_v6` measures that the two readings of a value cannot drift. Every
    # digit-only shape carries `(?<!\d)`/`(?!\d)` and NO DOT OR COLON separator:
    # an IPv4 address must not also be an operator account, which is exactly what
    # happened when the separator class was shared.
    #
    # THE CUES ARE THE REGISTRY'S OWN, WITH FOUR DELIBERATE OMISSIONS, each a
    # measured over-mask risk rather than a convenience:
    #
    #   * IP_ADDRESS drops «с адреса». It introduces a POSTAL address far more
    #     often than an IP in Russian business writing («с адреса клиента: Москва,
    #     Ленина 14»), and the shape would then have to choose between the two.
    #   * SUBSCRIBER_ACCOUNT drops the English «account id» — «account» is ALREADY
    #     the bank-account cue above, whose shape is twenty digits, and a key or a
    #     cue types with no shape check. «лицевой счёт»/«л/с» carry the telecom
    #     reading, and their 8–12 digits can never meet the bank account's twenty.
    #   * METRICA_CLIENT_ID drops the bare «идентификатор посетителя»: a visitor
    #     is a counter, not a person, and the phrase introduces a session id at
    #     least as often as a Метрика ClientID. «ClientID», «client id» and
    #     «_ym_uid» are the evidence.
    #   * APP_DEVICE_ID drops the bare English «device id»: in a support chat that
    #     is a printer, a router or a handset model far more often than a person's
    #     identifier, and neither shape narrows it.
    ("IMSI", r"\bIMSI\b|международн\w* идентификатор абонент\w*",
     r"(?<!\d)250[ \t\-/:№]{0,2}\d{2,3}[ \t\-/:№]{0,2}\d{8,10}(?!\d)"),
    # MAC: the 2-2-2-2-2-2 forms the v5 recognizer already reads, the Cisco
    # 4-4-4 grouping it does not, AND the SOLID 12-hex spelling the corpus
    # actually writes. The letters are HEX, and the Cyrillic twins are admitted
    # because a hex field has no other reading (see `ru_pii_v6`).
    #
    # G7 (02.10.2026): the solid form was deliberately absent as «a prefix of the
    # 32-hex UUID», and that reasoning cost 35/35 spans — the corpus writes
    # «mac FCF3C2CFA5AC» and 0% was detected. It is admitted here BEHIND THE CUE
    # and with `(?<![0-9A-Fa-f...])`/`(?![0-9A-Fa-f...])` on both sides, so a
    # 12-hex run INSIDE a 32-hex UUID cannot match (the lookbehind/lookahead see
    # a hex neighbour), and no cue-less 12-hex run is claimed at all.
    ("MAC", r"\bMAC\b|мак[-\s]?адрес|физическ\w* адрес",
     r"(?<![0-9A-Fa-fАВЕСКМНОРТУХ])"
     r"(?:[0-9A-Fa-fАВЕСКМНОРТУХ]{2}(?:[:\-][0-9A-Fa-fАВЕСКМНОРТУХ]{2}){5}"
     r"|[0-9A-Fa-fАВЕСКМНОРТУХ]{4}\.[0-9A-Fa-fАВЕСКМНОРТУХ]{4}"
     r"\.[0-9A-Fa-fАВЕСКМНОРТУХ]{4}"
     r"|[0-9A-Fa-fАВЕСКМНОРТУХ]{12})"
     r"(?![0-9A-Fa-fАВЕСКМНОРТУХ])"),
    # IP_ADDRESS: the octet-bounded IPv4 quad (the v5 class itself, so the two
    # readings of an address cannot disagree), the SQUEEZED quad the corpus
    # writes, and the RFC 5952 IPv6 notation whose IPv4-mapped tail is read as
    # four OCTETS. The builder's `\D{0,20}` gap is bounded, so a cue at the head
    # of a line cannot reach a number further down it.
    #
    # THE LABEL IS THE REGISTRY ID. `engine_labels` records the v5-internal «IP»;
    # G7 measured 0/35 recall for a value that was masked (the span carried «IP»)
    # AND 0/35 coverage for the squeezed spelling, so both halves are fixed: the
    # id here, the squeezed quad below. The v5 bare recognizer
    # (`ru_pii._IPV4_RE`) still emits «IP» for a dotted quad with no cue — an
    # alias the vault answers for through `ru_pii_v6.engine_label`, and
    # `TELECOM_LABELS` carries both spellings so the notation path is the same.
    ("IP_ADDRESS", r"\bIP\b|айпи|ip[-\s]?адрес",
     r"(?:(?<![\d.])(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
     r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?![\d.])"
     # THE SQUEEZED QUAD: four octets with their dots removed, so «201.73.0.173»
     # reaches the message as «201730173». The four octets are read off the digit
     # run by the SAME class as the dotted form (`25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d`)
     # and the run is token-bounded on both sides, so the reading is "these digits
     # ARE four octets" and not "some digits are near four octets". 4–12 digits;
     # «ip 999999999» is refused because no 4-way split of nine nines is ≤255.
     #
     # THE BOUNDARY EXCLUDES `:` AND `.` AND HEX, and that is load-bearing rather
     # than tidy: `2001` is itself four valid octets (2|0|0|1), so a plain
     # `(?<!\d)…(?!\d)` here swallowed the first group of «ip-адрес 2001:db8::1»
     # and handed the model a four-character span where an IPv6 address stood —
     # found by `test_pii_v6`, not by the corpus, which carries no IPv6.
     r"|(?<![0-9A-Za-zА-Яа-яЁё])(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d){4}"
     r"(?![0-9A-Za-zА-Яа-яЁё:.])"
     # the IPv4-mapped / IPv4-embedded IPv6 families: a hex prefix, then a
     # DOTTED QUAD of real octets — which is why «::ffff:999.1.1.1» is refused.
     r"|(?<![0-9A-Fa-f:.])(?:(?:[0-9A-Fa-f]{1,4}:){1,6}"
     r"|::(?:[0-9A-Fa-f]{1,4}:){0,5}"
     r"|(?:[0-9A-Fa-f]{1,4}:){6})"
     r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
     r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?![0-9A-Fa-f:.])"
     # the pure IPv6 notations, IPv4-mapped tail included
     r"|(?<![0-9A-Fa-f:.])"
     r"(?:(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
     r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}"
     r"|(?:[0-9A-Fa-f]{1,4}:){6}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
     r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}"
     r"|::(?:[0-9A-Fa-f]{1,4}:){0,5}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
     r"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}"
     r"|[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){7}"
     r"|(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,6})?"
     r"::(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,6})?"
     r"|(?:[0-9A-Fa-f]{1,4}:){1,7}:)(?![0-9A-Fa-f:.]))"),
    # ESIA_OID: «\d+; длина не установлена». `\d+` is every digit run in the
    # message, so the shape takes the sample's floor (ten digits) and the fifteen
    # a digit run may reach. «СНИЛС» is deliberately NOT a cue here: the registry
    # names it, but СНИЛС is a checksum-gated type of its own and typing a
    # correctly-found СНИЛС as an ЕСИА identifier would trade a hard identifier
    # for a soft label.
    ("ESIA_OID", r"\boid\b|ЕСИА|идентификатор ЕСИА|Госуслуги ID",
     r"(?<!\d)\d{1,5}(?:[ \t\-/:№]{0,2}\d{1,5}){1,4}(?!\d)"),
    # MOBILE_AD_ID: GAID (lower case) and IDFA (upper case) differ only in case,
    # and the shape is ONE UUID either way — the case belongs to the writer, not
    # to the identity.
    ("MOBILE_AD_ID", r"\bGAID\b|\bIDFA\b|рекламн\w* идентификатор|advertising id",
     r"(?<![0-9A-Fa-fАВЕСКМНОРТУХ])"
     r"(?:[0-9A-Fa-f]{8}(?:[ \t.\-/:№]{0,2}[0-9A-Fa-f]{4}){3}"
     r"[ \t.\-/:№]{0,2}[0-9A-Fa-f]{12}"
     r"|[0-9A-Fa-f]{32})(?![0-9A-Fa-fАВЕСКМНОРТУХ])"),
    # APP_DEVICE_ID: a UUID (IFV) or the numeric appmetrica form. The bare
    # «device id» is deliberately not a cue — see the omission note above.
    ("APP_DEVICE_ID", r"appmetrica[_-]?device[_-]?id|идентификатор устройства",
     r"(?:(?<![0-9A-Fa-fАВЕСКМНОРТУХ])"
     r"(?:[0-9A-Fa-f]{8}(?:[ \t.\-/:№]{0,2}[0-9A-Fa-f]{4}){3}"
     r"[ \t.\-/:№]{0,2}[0-9A-Fa-f]{12}|[0-9A-Fa-f]{32})"
     r"(?![0-9A-Fa-fАВЕСКМНОРТУХ])"
     r"|(?<!\d)\d{1,6}(?:[ \t\-/:№]{0,2}\d{1,6}){0,5}(?!\d))"),
    # APP_DEVICE_ID, THE BARE ENGLISH CUE (G7 follow-up, 02.10.2026 — NOT one of
    # the brief's six). The omission above is recorded as a measured over-mask
    # risk: «device id» in a support chat names a printer or a handset at least
    # as often as a person. That reasoning stands for the ENTRY ABOVE, whose
    # digit alternative is a run of 1–36 digits and would type a model number;
    # it does NOT stand for the record, which the corpus writes 34 times behind
    # exactly this cue and which scored 0% coverage. So the cue is admitted with
    # the record's OWN two forms and nothing wider: the numeric bound is
    # `_TELECOM_DIGIT_COUNTS["APP_DEVICE_ID"]` (15–18 digits, the registry's own
    # «пример — 18 цифр»), and the UUID form is the record's other half — the
    # corpus writes that one too (`device id E944AD90…`). A 32-hex run is ALSO
    # MOBILE_AD_ID's form, and the family resolves that by asking the vault for
    # every reading the spelling permits, never by guessing here.
    ("APP_DEVICE_ID", r"\bdevice id\b|\bdevice[_-]?id\b",
     r"(?:(?<![0-9A-Fa-fАВЕСКМНОРТУХ])"
     r"[0-9A-Fa-f]{8}(?:[ \t.\-/:№]{0,2}[0-9A-Fa-f]{4}){3}"
     r"[ \t.\-/:№]{0,2}[0-9A-Fa-f]{12}(?![0-9A-Fa-fАВЕСКМНОРТУХ])"
     r"|(?<!\d)\d{15,18}(?!\d))"),
    # METRICA_CLIENT_ID: the issuer's 18-digit sample. The `_ym_uid` cookie NAME
    # is a cue of its own — it appears in a payload as a key and the value beside
    # it is the ClientID.
    ("METRICA_CLIENT_ID", r"ClientID|client id|_ym_uid|ym[_-]?client[_-]?id",
     r"(?<!\d)\d{1,6}(?:[ \t\-/:№]{0,2}\d{1,6}){0,5}(?!\d)"),
    # SUBSCRIBER_ACCOUNT: «операторский цифровой прогон, типично 8–12 цифр (НЕ из
    # первоисточника)». The bound IS that observation, so the shape claims 8–12
    # digits and no dot or colon — an address is not an account.
    ("SUBSCRIBER_ACCOUNT", r"лицев\w* счёт|л/с|номер договора абонента",
     r"(?<!\d)\d{1,6}(?:[ \t\-/:№]{0,2}\d{1,6}){0,5}(?!\d)"),
    # --- the v6 utility/account/education/travel family: cue -> shape ---------
    #
    # THE SHAPES ARE THE SHAPES `pseudex/ru_pii_v6.py §utility` COMPILES, and
    # `test_pii_v6` measures that the two readings of a value cannot drift (the
    # same pin the telecom family put on its own pair). None of the twelve records
    # carries a checksum and `bare_typed=False` on every one, so the CUE OR THE
    # FIELD KEY IS THE WHOLE EVIDENCE — which is also why the shapes carry their
    # own `(?<!…)`/`(?!…)` boundaries: the builder's `\D{0,20}?` gap may sit
    # anywhere, and a shape without a left boundary would read the tail of a
    # longer number.
    #
    # ONE COLLISION IS RECORDED RATHER THAN WON: the registry gives BOTH
    # `SUBSCRIBER_ACCOUNT` (telecom, above) and `UTILITY_ACCOUNT` (below) the cues
    # «лицевой счёт», «л/с», «ЛС» and the same 6–12 digit space. The entries below
    # stand AFTER the telecom one, and `_resolve` breaks an exact tie by the order
    # the spans were appended — so the shared cues answer `SUBSCRIBER_ACCOUNT` and
    # this family answers for the letter-bearing form the telecom shape cannot
    # read. `test_utility_shared_cue_arbitration_is_recorded` pins that decision;
    # changing it is a PRIORITY question for the Lead's table, not an edit here.
    #
    # GIS_ZHKH_ELS: the registry's grammar VERBATIM — 2 + 2 letters + 6, then
    # optional «-2» and «-4» groups. The letter slots REQUIRE LETTERS on purpose:
    # `normalize()` folds a Cyrillic look-alike series («60ВВ…» → «6088…») and the
    # shape must not read that folded value, because the customer's own series is
    # what has to come back. The family's raw-text path is the reading of it.
    ("GIS_ZHKH_ELS",
     r"\bЕЛС\b|единый лицевой счёт|идентификатор ЖКУ|ИЖКУ|"
     r"идентификатор платёжного документа|\bИПД\b",
     r"(?<!\d)\d{2}(?:[А-ЯЁа-яё]{2}|[A-Za-z]{2})\d{6}"
     r"(?:-\d{2}(?:-\d{4})?)?(?!\d)"),
    # UTILITY_ACCOUNT: «обычно 6–12 цифр, иногда буквы/дефисы». TWO ENTRIES, and
    # the split is the arbitration with the telecom family made concrete rather
    # than argued:
    #
    #   * «ЖКХ» IS THIS FAMILY'S OWN CUE, so the full shape (digits AND the
    #     letter-bearing form) stands behind it — the telecom family does not hold
    #     this word, and «ЖКХ 1234567890» is a ЖКХ personal account, not an
    #     operator's.
    #   * THE SHARED CUES («лицевой счёт», «л/с», «ЛС», «номер лицевого счёта»)
    #     KEEP ONLY THE LETTER-BEARING READING. A registry gives BOTH
    #     `SUBSCRIBER_ACCOUNT` and `UTILITY_ACCOUNT` these words and the same 6–12
    #     digit space, and the telecom entry stands earlier — so a plain digit run
    #     under a shared cue stays `SUBSCRIBER_ACCOUNT` (its own test pins that)
    #     while the form the telecom shape cannot read, «л/с 12-34АБ», is this
    #     family's. Making this family win the digit run too is a PRIORITY
    #     decision for the Lead's table, not an edit here.
    #
    # No dot and no colon anywhere: a dot is a date and a colon is a cadastral
    # number, and both are already owned. THE MIXED READING ALLOWS NO SPACE AT
    # ALL: with one allowed it matched «договор 875» — a word and a number —
    # behind any of these cues.
    ("UTILITY_ACCOUNT", r"\bЖКХ\b",
     r"(?:(?<!\d)\d(?:[ \t\-/]?\d){5,11}(?!\d)"
     r"|(?<![0-9A-Za-zА-Яа-яЁё\-/])"
     r"(?=[0-9А-ЯЁа-яёA-Za-z\-/]*\d)"
     r"(?=[\-/0-9]*[А-ЯЁA-Zа-яё])"
     r"[0-9А-ЯЁа-яёA-Za-z](?:[-/]?[0-9А-ЯЁа-яёA-Za-z]){4,11}"
     r"(?![0-9A-Za-zА-Яа-яЁё\-/]))"),
    ("UTILITY_ACCOUNT", r"лицев\w* счёт|л/с|\bЛС\b|номер лицевого счёта",
     r"(?<![0-9A-Za-zА-Яа-яЁё\-/])"
     r"(?=[0-9А-ЯЁа-яёA-Za-z\-/]*\d)"
     r"(?=[\-/0-9]*[А-ЯЁA-Zа-яё])"
     r"[0-9А-ЯЁа-яёA-Za-z](?:[-/]?[0-9А-ЯЁа-яёA-Za-z]){4,11}"
     r"(?![0-9A-Za-zА-Яа-яЁё\-/])"),
    # …AND THE ONE CUE THAT IS THIS FAMILY'S ALONE. The registry's own
    # «абонентский номер (ЖКХ)» is kept, but the shape is the LETTER-BEARING
    # reading only — the annotation in the registry is the industry, and a phone
    # stands after this phrase far more often than a personal account.
    ("UTILITY_ACCOUNT",
     r"абонентск\w* номер",
     r"(?<![0-9A-Za-zА-Яа-яЁё\-/])"
     r"(?=[0-9А-ЯЁа-яёA-Za-z\-/]*\d)"
     r"(?=[\-/0-9]*[А-ЯЁA-Zа-яё])"
     r"[0-9А-ЯЁа-яёA-Za-z](?:[-/]?[0-9А-ЯЁа-яёA-Za-z]){4,11}"
     r"(?![0-9A-Za-zА-Яа-яЁё\-/])"),
    # CDP_CUSTOMER_ID: three readings — a code («c-000184523»), a UUID (the
    # telecom family's own two shapes with their Cyrillic hex twins, so one
    # device-id reading cannot drift), and a digit run whose floor is the
    # registry's SAMPLE (nine digits; a shorter CDP id is reached by the field
    # key, see TYPES.md). THE TEXT IS `ru_pii_v6._UT_CDP` VERBATIM — the same
    # string the module compiles — so the lease and the mint cannot disagree.
    ("CDP_CUSTOMER_ID",
     r"\bID клиента\b|клиентский ID|\bcustomer id\b|\buser id\b|"
     r"идентификатор клиента|идентификатор пользователя",
     r"(?:(?:(?<![0-9A-Fa-fАВЕСКМНОРТУХ])[0-9A-Fa-fАВЕСКМНОРТУХавескмнортух]{8}[ \t.\-/:№]{0,2}[0-9A-Fa-fАВЕСКМНОРТУХавескмнортух]{4}[ \t.\-/:№]{0,2}[0-9A-Fa-fАВЕСКМНОРТУХавескмнортух]{4}[ \t.\-/:№]{0,2}[0-9A-Fa-fАВЕСКМНОРТУХавескмнортух]{4}[ \t.\-/:№]{0,2}[0-9A-Fa-fАВЕСКМНОРТУХавескмнортух]{12}(?![0-9A-Fa-fАВЕСКМНОРТУХ])|(?<![0-9A-Fa-fАВЕСКМНОРТУХ])[0-9A-Fa-fАВЕСКМНОРТУХавескмнортух]{32}(?![0-9A-Fa-fАВЕСКМНОРТУХ]))|(?<![0-9A-Za-zА-Яа-яЁё])[A-Za-zА-Яа-яЁё]{1,3}[-/]?\d{3,20}(?![0-9A-Za-zА-Яа-яЁё])|(?<!\d)\d{9,20}(?!\d))"),
    # LOGIN: `[A-Za-z0-9._-]{3,}`, bounded to a handle's length and requiring ONE
    # LETTER — the over-mask guard («логин 2024» is a year, and no sample in the
    # registry's industries is an all-digit handle).
    ("LOGIN", r"логин|имя пользователя|\busername\b|учётная запись|учетная запись",
     r"(?<![0-9A-Za-z._\-])(?=[0-9._\-]*[A-Za-z])"
     r"[A-Za-z0-9][A-Za-z0-9._\-]{2,31}(?![0-9A-Za-z._\-])"),
    # DIPLOMA_NUMBER: 6 series characters on 1[0-4] + 7 number digits, one
    # optional space. The registry's `grammar` VERBATIM.
    ("DIPLOMA_NUMBER", r"диплом|серия и номер диплома|бланк диплома|"
                       r"документ об образовании",
     r"(?<!\d)1[0-4]\d{4}[ \t]?\d{7}(?!\d)"),
    # SCHOOL_CERT_NUMBER: `\b\d{14}\b`, the registry's own grammar.
    ("SCHOOL_CERT_NUMBER", r"аттестат|номер аттестата|"
                           r"аттестат о среднем общем образовании",
     r"(?<!\d)\d{14}(?!\d)"),
    # STUDENT_ID_NUMBER — `ГРАММАТИКА?`. The registry's sample family «NN-NNNN»
    # plus the «или цифры» the card names; the digit-only reading starts at five
    # so a four-digit year after «студенческий билет» stays a year.
    ("STUDENT_ID_NUMBER", r"студенческий билет|студбилет|номер студенческого",
     r"(?<!\d)(?:\d{2}[ \t\-/]?\d{4}|\d{5,10})(?!\d)"),
    # ACCESS_PASS_NUMBER: the printed pass's digits (6–12; the reference sample is
    # «0034561») and the RFID UID in hex (8 or 14, the registry's own note).
    ("ACCESS_PASS_NUMBER", r"пропуск|номер пропуска|карта доступа|бейдж",
     r"(?:\d{6,12}|(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{14}|[0-9A-Fa-f]{8})"
     r"(?![0-9A-Fa-f]))"),
    # EMPLOYEE_TAB_NUMBER: the employer's digit run (6–10, leading zeros are the
    # norm) plus the 1С ЗУП grouping «0000-00412». The grouped form needs five
    # digits after the separator so «2024-2025» — a date range in prose — is not a
    # tab number.
    ("EMPLOYEE_TAB_NUMBER", r"табельный номер|таб\.? ?№|табельный|таб номер",
     r"(?<!\d)(?:\d{4}[ \t\-/]\d{5,6}|\d{6,10})(?!\d)"),
    # EMPLOYMENT_CONTRACT_NUMBER: the registry's two samples («145-ТД»,
    # «ТД-2024/017») read as letters and digits held together by `-` or `/`.
    #
    # G7 (02.10.2026): the GLUED «ТД2024» was «deliberately not claimed (no
    # registry sample is glued)» — and the corpus writes exactly that, after its
    # separator squeeze and glyph fold turn «ТД-2025/69917» into «TД202569917»
    # (0/35, 0% coverage). The glued alternative is ADMITTED and bounded: 1–3
    # letters, then 4–12 digits, both ends `[0-9A-Za-zА-Яа-яЁё]`-guarded, so a
    # word followed by a year («договор 2025») still needs the separator form to
    # be read as a contract number. The Cyrillic/Latin twins of the letters are
    # already inside the class — the fold is what the corpus writes.
    ("EMPLOYMENT_CONTRACT_NUMBER", r"трудовой договор|ТД №|номер трудового договора",
     r"(?<![0-9A-Za-zА-Яа-яЁё])"
     r"(?:\d{1,6}[-/][А-ЯЁA-Zа-яё]{1,3}(?:[-/]\d{1,6})*"
     r"|[А-ЯЁA-Zа-яё]{1,3}[-/]\d{1,6}(?:[-/]\d{1,6})*"
     r"|[А-ЯЁA-Zа-яё]{1,3}\d{4,12})"
     r"(?![0-9A-Za-zА-Яа-яЁё])"),
    # PNR — `ГРАММАТИКА?`: five or six alphanumerics per GDS, and the registry
    # notes «Сирена» locators may be Cyrillic. BOTH a letter and a digit are
    # required: «бронь отеля» is five Cyrillic letters and must not become a
    # booking locator. An all-letter or all-digit locator is reached by the field
    # key, not by the cue (TYPES.md).
    ("PNR", r"\bPNR\b|номер брони|код бронирования|номер бронирования|бронь",
     r"(?<![0-9A-Za-zА-Яа-яЁё])"
     r"(?=[0-9А-ЯЁа-яёA-Za-z]{0,5}[А-ЯЁа-яёA-Za-z])"
     r"(?=[А-ЯЁа-яёA-Za-z]*\d)"
     r"[0-9А-ЯЁа-яёA-Za-z]{5,6}(?![0-9A-Za-zА-Яа-яЁё])"),
    # E_TICKET_NUMBER — `ГРАММАТИКА?`: the AIR form only («3 + 10» digits). The
    # rail numbering is «не установлена», so nothing is claimed for it.
    ("E_TICKET_NUMBER", r"электронный билет|номер билета|e-ticket|"
                        r"маршрутная квитанция",
     r"(?<!\d)\d{13}(?!\d)"),
    # --- the temporary-secret family: cue -> shape ---------------------------
    #
    # C1 (O-SECRET). THE SECONDARY DISCRIMINATOR, and the window is the engine's
    # existing one (`pseudex/assets.py:432`: cue, at most 20 non-digit characters,
    # value). The field keys are above in `KEY_TYPE`; these entries are what
    # reaches the same classes in PROSE, where there is no schema.
    #
    # THE CARD VERIFICATION CODE IS THREE OR FOUR DIGITS BY ALIAS, and it is
    # written as TWO entries rather than one `\d{3,4}` on purpose: a single
    # bounded set per alias is what the contract requires, an unbounded `{3,4}`
    # widens the three-digit false-positive surface, and a fixed `\d{3}` silently
    # loses the Amex CID variant. The lookarounds `(?<!\d)`/`(?!\d)` are the
    # difference between «the value is three digits» and «the value STARTS with
    # three digits»: without them «cvv 0420» would match its own first three
    # digits — a wrong value masked, the fourth digit left in the clear.
    ("CARD_VERIFICATION_CODE",
     r"\bcvv2?\b|\bcvc2?\b|\bcsc\b|\bcav2\b|\bcv2\b|\bcvv-?код\b|"
     r"\bкод\s*cvv\b|\bкод\s*cvc\b|\bцвс\b|\bцсв\b|"
     r"защитн\w*\s+код(?:\s+карты)?|"
     r"код\s+безопасности\s+карты|код\s+проверки\s+карты|"
     r"security\s+code|card\s+security\s+code",
     r"(?<!\d)\d{3}(?!\d)"),
    # CID / 4DBC (American Express) — FOUR digits, the other half of the declared
    # set. «cid» is a whole word here and nowhere a head: a stem would claim
    # «cidnumber» in prose, where `_key_type` already answers for the key.
    ("CARD_VERIFICATION_CODE",
     r"\bcid\b|\b4dbc\b|\bcid-?код\b|\bкод\s*cid\b|amex\s+cid",
     r"(?<!\d)\d{4}(?!\d)"),
    # ISSUER_OTP — THE LENGTH IS UNASSERTED, so the shape claims the RUN, not a
    # width: the cue is the whole evidence and the value is taken as it is
    # written. Declaring 4, 6 or «4..8» here would invent exactly the answer the
    # owner recorded as RESEARCH_GAP (CONTEXT-MATRIX `known_coverage_gaps`;
    # EX-O-SECRET-1). NEG-OTP-1/2 (`номер заказа 991991`, `артикул 042042`) carry
    # the same glyphs and no cue of this class; NEG-PROSE-3 (`код 314`) shows why
    # bare «код» is absent from the list below — it names an order at least as
    # often as a secret, and P05 forbids buying recall that way.
    #
    # BARE «КОД ПОДТВЕРЖДЕНИЯ» IS DELIBERATELY NOT A CUE, and this is a MEASURED
    # boundary rather than a preference. Two independent suites already pin the
    # same sentence as a business code and not a secret — `test_hard_cases`
    # («код подтверждения 112233», MUST_NOT_DETECT) and `test_pii_v6`
    # (FINANCE_NEGATIVES, «код подтверждения 4521») — and the C0 contract itself
    # leaves this fork OWNER_PENDING (O-SECRET-2: is the accepted recall boundary
    # the field only, or the field OR a bounded cue?). Until the owner rules, the
    # engine keeps the boundary those cases fixed: the ONE-TIME or CHANNEL
    # qualifier is required («из смс», «одноразовый», «операции», «3-D Secure»).
    # Recorded in TYPES.md §boundary and in DELTA.json.
    ("ISSUER_OTP",
     r"\botp\b|\botp-?код\b|\bкод\s*otp\b|одноразов\w*\s+код|"
     r"код\s+подтверждения\s+(?:из\s+)?(?:смс|sms|почт\w*|email|пуш\w*|push)|"
     r"код\s+подтверждения\s+операции|"
     r"sms-?код|смс-?код|код\s+(?:смс|sms)|"
     r"3-?d\s?secure|\b3ds\b|\b3ds-?код\b|код\s*3ds\b|"
     r"\bverification\s+code\b|one[-\s]?time\s+(?:code|password)",
     r"(?<!\d)\d+(?!\d)"),
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
    # DOB ВЫШЕ DATE, потому что это та же дата с ДОБАВЛЕННЫМ свидетельством.
    # Слой quasi типизирует числовую дату в родильном контексте как DOB, но
    # DATE стоял старше, съедал спан целиком, и бенчмарк честно считал это
    # промахом: пересечение чужого типа — не полнота, а дата рождения,
    # замаскированная как «дата», теряет то единственное, что делает её
    # персональными данными.
    "NAME": 3, "DOB": 3, "DATE": 2, "PASSPORT": 2, "LOC": 2,
    # --- the v6 labels: the composition the N1 families handed to this table ---
    #
    # THE v5 CORE ABOVE IS NOT RENUMBERED. SNILS/INN/CARD keep 6, PHONE/EMAIL/
    # IP/PLATE keep 5, PASSPORT keeps 2 — every entry below is an ADDITION, and
    # a v6 label that already carried a v5 rank (ACCOUNT/OMS/OGRN/VIN/
    # DRIVER_LICENSE/VEHICLE_DOC/INTL_PASSPORT/BIRTH_CERT/MAC/IP) is left where
    # it was. A v6 label with no entry defaults to 1, which is BELOW every bare
    # v5 shape; each entry here exists because a handoff measured a concrete
    # case where that default lost the arbitration.
    #
    # DMS_POLICY 8 — ABOVE OMS (7). «полис» is the v5 ОМС cue and «ДМС» is this
    # record's own; both fire on «полис ДМС <16 digits>», the two spans share
    # their boundaries, and at equal priority `_resolve` keeps the one appended
    # first (the ОМС entry). At 7 — a tie — the label stayed ОМС; the value was
    # masked either way, the LABEL and the minted form were a medical policy's.
    # 8 is above the checksum tier on purpose: the cue says ОМС is not what this
    # is, and the alternative is a fake ОМС ENP in the customer's ДМС field.
    "DMS_POLICY": 8,
    # THE G7 LABEL ALIGNMENT (02.10.2026): the eight ids a span now carries where
    # it used to carry a v5-internal label. Each one REPLACES a rank that was
    # already taken by the old spelling — `VEHICLE_DOC`/`OGRN`/`OMS`/`ACCOUNT`
    # were 7, `IP` was 5 — so this is the same arbitration with the name the
    # benchmark reads, and NOT a renumbering: at the old rank the span would lose
    # its overlap to a bare v5 shape the moment the label changed (`STS_NUMBER`
    # is a ten-digit 2-2-6 run, i.e. exactly what libphonenumber reads as a
    # PHONE, so a default of 1 would have traded a label fix for a label
    # regression). `EPTS_NUMBER` and `LOYALTY_CARD_NUMBER` join the document tier
    # their old labels never had — they defaulted to 1 and covered 97% only
    # because nothing overlapped them.
    "BANK_ACCOUNT": 7, "OGRNIP": 7, "OMS_ENP": 7, "EPTS_NUMBER": 7,
    "LOYALTY_CARD_NUMBER": 7, "PTS_NUMBER": 7, "STS_NUMBER": 7,
    # THE LEGAL FAMILY'S SQUEEZED SHAPES AND THE DEVICE ID (G7 follow-up,
    # 02.10.2026). Three of them are cue-typed DIGIT RUNS, and the default rank of
    # 1 hands a run to any bare v5 shape that also matches — a nine-to-twelve-digit
    # case number beginning with 7 IS libphonenumber's phone, which is exactly how
    # «дело № 77298282030» was lost (`COURT_CASE_NO_SOU -> PHONE` in the sweep's
    # desync list). The three take the document tier (7) their sibling legal
    # records earn by being cue-typed; the device id takes 6 for the same reason.
    "ARBITRAZH_CASE_NO": 7, "COURT_CASE_NO_SOU": 7, "CADASTRAL_NUMBER": 7,
    "APP_DEVICE_ID": 6,
    # IP_ADDRESS 6, ONE ABOVE PHONE. The v5 `IP` sat at 5, a tie with PHONE, and
    # that was harmless while the only v5 reading was a DOTTED quad — libphonenumber
    # never calls `95.165.12.34` a number. The squeezed v6 reading is a bare digit
    # run (`159131204150`), and at a TIE `_resolve` keeps the span appended first,
    # which is `detect_pii`'s PHONE: 3 of 35 addresses went to the model as phone
    # numbers. The CUE is the evidence here («ip» names the type), so it outranks
    # a shape that only recognises a digit run.
    "IP_ADDRESS": 6,
    # MILITARY_ID 7 — the `№` form was already typed; the SEPARATOR-FREE
    # variants («военник АК1234567», «АК 1234567») are ALSO a v5 plate shape
    # (type 1А trailers, PLATE=5), so at the default 1 the whole value was
    # labelled and minted as a plate. 7 is the document-ID tier this family's
    # neighbours already sit in (INTL_PASSPORT, DRIVER_LICENSE, BIRTH_CERT).
    "MILITARY_ID": 7,
    # CIVIL_ACT_CERT 7 — ITS OWN LINE, AND TODAY IT IS DEFENSIVE. The record
    # shares the engine label BIRTH_CERT («грамматика: как BIRTH_CERT»), so the
    # shape is typed at BIRTH_CERT's rank 7 and nothing loses. The entry exists
    # because the moment the label is split the new label must not default to 1
    # and lose to `ru_pii._BIRTH_CERT_RE` — the v5 bare recognizer that holds 7.
    # The split itself is NOT made here: it needs the identity mint dispatch
    # (vault.py) and the identity signature reading (redact.py), which are family
    # bodies this integration is forbidden to touch; DELTA.json records it.
    "CIVIL_ACT_CERT": 7,
    # THE TWELVE UTILITY LABELS, 6 — the document-ID tier, below the checksum
    # IDs (SNILS/INN/CARD/VIN, 6) only in the sense that they share it. They are
    # cue- or key-typed and carry no checksum, so a bare v5 shape must not take
    # the span from them: «логин ivan.petrov» was read as NAME «ivan» (3) and
    # left «.petrov» to the model, and every digit run of 6–12 behind its own cue
    # («табельный номер …», «пропуск …», «ЖКХ …») could be re-read as a PHONE
    # (5). 6 keeps them below the v5 documents (7) they never overlap and above
    # every bare shape they do.
    "GIS_ZHKH_ELS": 6, "UTILITY_ACCOUNT": 6, "CDP_CUSTOMER_ID": 6,
    "LOGIN": 6, "DIPLOMA_NUMBER": 6, "SCHOOL_CERT_NUMBER": 6,
    "STUDENT_ID_NUMBER": 6, "ACCESS_PASS_NUMBER": 6,
    "EMPLOYEE_TAB_NUMBER": 6, "EMPLOYMENT_CONTRACT_NUMBER": 6,
    "PNR": 6, "E_TICKET_NUMBER": 6,
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
