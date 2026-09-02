"""`result` — personal data arriving FROM the customer's own system.

THE THIRD LEG OF THE CONTRACT, and v1 had none of it. Every other family asks
what happens to data the customer SAYS. Here the CRM answers a lookup and the
answer is full of real people: the gateway has to mask it on the way IN to the
model, and hand the real values back when the model puts them into the next tool
call. A gateway can pass every `transfer` case and leak here, because inbound
masking runs over machine text with a different shape — JSON, Latin keys, a list
of strangers, and a free-text field where an operator typed prose.

SIX SUB-SHAPES, one per defect class, and each is a claim about where a gateway
breaks that the others cannot make:

  flat        one record, flat JSON. The base line the rest is measured against.
  list        several records at once. The model acts on ONE of them and the
              other people in the list are strangers whose values may not reach
              the customer — `FinalAnswer.must_not_contain` is the only place in
              this corpus where a REAL value is forbidden from an answer, and
              over WebArena's 812 official cases that assertion appears zero
              times.
  latin_kv    `{"passport": "4509123456"}`. The KEY types the value, and the
              engine's own history says this is a separate class: re-gating a
              KV-typed span through the Russian cue list lost the Latin
              `passport` entirely while the same number after «паспорт» was
              masked.
  iso_date    `{"birth_date": "1963-01-26"}` beside `created_at`. A bare date is
              not personal data; this one is, because the key says so, and the
              document date in the same object must survive untouched.
  comment     the datum lies in PROSE inside a JSON string, in an oblique case,
              with no key typing it and no schema around it.
  spoken      the row was typed BY EAR — «школьная пятьдесят девять а первый
              подъезд», «восемь девятьсот двенадцать сорок один ноль девять».
              Both known engine defects live here and neither is reachable from
              written text, where a digit is a digit.

WHAT THIS FAMILY REFUSES TO DO:

  * It never runs the detector to decide what to label. Ground truth is what the
    generator PLACED: `_emit` reports the offset of every value as it writes the
    character, so no span is ever recovered afterwards with `str.find`. v2's
    predecessor matched clean parts against the finished surface by substring and
    every part a register had TOUCHED vanished from the labels — 162 of 183
    sloppy failures were that one bug, twice.
  * It never lets the literary register in through the back. The register gate
    reads user messages only, on purpose (a CRM answers in digits whatever the
    caller's voice did), so `clean` here means the CUSTOMER wrote like a
    document: 10 cases of 250, kept to prove we did not break on it.
  * It never asserts a link the conversation does not settle. «Иванов Пётр» in
    the customer's turn beside «Иванов Пётр Сергеевич» in the CRM row is
    `unjudged` — two customers can share a surname and a given name, and a corpus
    demanding the merge would score a gateway on a guess.
  * `verbatim` describes the CUSTOMER'S turns, all of which are unaltered
    RuDevices utterances carried by value with their digest. The tool result
    beside them is authored by construction: no corpus of speech contains a CRM
    response, and pretending one did would be the only dishonest way to reach a
    higher verbatim share.

NEGATIVES ARE HALF OF WHAT IS MEASURED HERE. An order number, a track code, an
article, a sum and a delivery window ride in the same JSON as the personal data,
and the model has to see every one of them in the clear or the call it makes next
is wrong. The dictated order number — four to eight numeral words with no digit
anywhere — is the shape that once got masked in production and that no
digit-shaped pattern can ever see; it is a declared negative in every voice-
register turn this module composes.

The other half of the precision measurement is `optional`, and it is NOT the same
thing. A negative may not be masked at all; an `optional` value may be masked
without penalty and missed without a leak. The bare street in `pickup_point`
carries that column: hundreds of buildings stand on «улица Советская», which is
one step more specific than the city that already identifies nobody under 152-ФЗ
ст. 3 п. 1. Folded into recall with the full address, the two averaged 71% while
the real figures were 94% and 47%.

ONE MEASUREMENT THIS FAMILY CANNOT MAKE, named rather than faked: the document
date (`created_at`) sitting beside a birth date is a real over-masking risk and
`schema.NEGATIVE_FAMILIES` has no member for it. Filing it under `order_number`
would corrupt the per-family precision breakdown, so it rides in the payload
unclaimed — neither credited nor penalised — until the schema grows a family for
it.

CONTRACT WITH THE BUILDER: `build(seed)` returns validated cases in a stable
order for one integer seed. It raises rather than return a case `schema.validate`
rejects; a corpus that ships an unscoreable case goes on printing numbers, and
the numbers go on looking like numbers.
"""

import hashlib
import json
import random
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    # `families/` is a namespace package under `agentpii3/`. A build script run
    # from `agentpii3/` already has the parent on the path; a direct
    # `python3 families/toolresult.py` does not. One line here beats a second
    # copy of the schema-import rule in every family module.
    sys.path.insert(0, str(_HERE.parent))

import schema  # noqa: E402


FAMILY: str = "result"
TARGET: int = 250
SUBSHAPES: tuple[str, ...] = (
    "flat", "list", "latin_kv", "iso_date", "comment", "spoken",
)

_CACHE = Path.home() / ".cache" / "pseudex-bench"
_RUDEVICES = _CACHE / "speech_rudevices.jsonl"
_RUDEVICES_LABELS = _CACHE / "rudevices_addresses.json"
_MINED = _HERE.parent / "mined"

# SOVA RuDevices is CC BY 4.0, so its text ships inside the corpus file. OpenSTT
# `asr_calls_2_val` is CC BY-NC 4.0 and not one line of it is read here: this
# family borrows FORMS from the call grammar — a pattern and a frequency already
# published in `mined/calls_grammar.json` — and never a sentence.
_LICENCE_RU = "CC BY 4.0"
_LICENCE_CALLS = "CC BY-NC 4.0"

# 250 of 4805 replies were read in the RuDevices number layer. A share over that
# stratum that forgets the factor is wrong by nineteen, and wrong in our favour.
_RANDOM_WEIGHT = 19.22


class BuildError(RuntimeError):
    """The generator could not honour a claim it was about to write down."""


# --- value pools -----------------------------------------------------------
#
# Authored and deliberately ordinary. A pool of unusual names measures a
# gazetteer's tail rather than the register; a pool of one name measures nothing.
# Surnames come in (masculine, feminine) pairs because a record whose name and
# gender disagree is a defect manufactured inside the corpus, and the
# gender-invariant tail is here because the substitute pool for those ran out at
# six in production — the seventh woman named by surname alone was a 5xx.

_SURNAMES: tuple[tuple[str, str], ...] = (
    ("Иванов", "Иванова"), ("Кузнецов", "Кузнецова"), ("Соколов", "Соколова"),
    ("Попов", "Попова"), ("Лебедев", "Лебедева"), ("Новиков", "Новикова"),
    ("Морозов", "Морозова"), ("Волков", "Волкова"), ("Зайцев", "Зайцева"),
    ("Павлов", "Павлова"), ("Семёнов", "Семёнова"), ("Голубев", "Голубева"),
    ("Виноградов", "Виноградова"), ("Богданов", "Богданова"),
    ("Воробьёв", "Воробьёва"), ("Фёдоров", "Фёдорова"),
    ("Михайлов", "Михайлова"), ("Беляев", "Беляева"), ("Тарасов", "Тарасова"),
    ("Белов", "Белова"), ("Комаров", "Комарова"), ("Орлов", "Орлова"),
    ("Киселёв", "Киселёва"), ("Макаров", "Макарова"), ("Андреев", "Андреева"),
    ("Ковалёв", "Ковалёва"), ("Ильин", "Ильина"), ("Гусев", "Гусева"),
    ("Титов", "Титова"), ("Кудрявцев", "Кудрявцева"),
)
_SURNAMES_INVARIANT: tuple[str, ...] = (
    "Ким", "Цой", "Бондаренко", "Шевченко", "Ткаченко", "Коваль", "Приходько",
)
_GIVEN_M: tuple[tuple[str, str], ...] = (
    ("Александр", "Александрович"), ("Дмитрий", "Дмитриевич"),
    ("Сергей", "Сергеевич"), ("Андрей", "Андреевич"), ("Алексей", "Алексеевич"),
    ("Максим", "Максимович"), ("Иван", "Иванович"), ("Артём", "Артёмович"),
    ("Никита", "Никитич"), ("Михаил", "Михайлович"), ("Роман", "Романович"),
    ("Кирилл", "Кириллович"), ("Егор", "Егорович"), ("Пётр", "Петрович"),
    ("Владимир", "Владимирович"), ("Николай", "Николаевич"),
    ("Игорь", "Игоревич"), ("Олег", "Олегович"), ("Павел", "Павлович"),
    ("Денис", "Денисович"),
)
_GIVEN_F: tuple[tuple[str, str], ...] = (
    ("Анастасия", "Александровна"), ("Мария", "Дмитриевна"),
    ("Анна", "Сергеевна"), ("Елена", "Андреевна"), ("Ольга", "Алексеевна"),
    ("Татьяна", "Максимовна"), ("Наталья", "Ивановна"), ("Ирина", "Артёмовна"),
    ("Екатерина", "Никитична"), ("Юлия", "Михайловна"),
    ("Светлана", "Романовна"), ("Марина", "Кирилловна"),
    ("Валентина", "Егоровна"), ("Людмила", "Петровна"),
    ("Галина", "Владимировна"), ("Ксения", "Николаевна"),
    ("Дарья", "Игоревна"), ("Полина", "Олеговна"), ("Вера", "Павловна"),
    ("Нина", "Денисовна"),
)

# The oblique case is 15% of every name mention in the mined grammar (124 of
# 815), and it is where the round trip breaks in a way detection cannot see:
# «позвоните Игорю» coming back as «Игорю» is a declined name written into a
# customer's CRM. The forms are hand-written pairs rather than produced by
# morphology, because a generator that guesses a declension puts its own guess in
# the ground truth and then scores the gateway against it.
_OBLIQUE_PEOPLE: tuple[tuple[str, str, str, str], ...] = (
    ("Марина", "марине", "Петрова", "петровой"),
    ("Игорь", "игорю", "Иванов", "иванову"),
    ("Ольга", "ольге", "Кузнецова", "кузнецовой"),
    ("Сергей", "сергею", "Волков", "волкову"),
    ("Анна", "анне", "Соколова", "соколовой"),
    ("Дмитрий", "дмитрию", "Морозов", "морозову"),
    ("Елена", "елене", "Новикова", "новиковой"),
    ("Пётр", "петру", "Лебедев", "лебедеву"),
    ("Наталья", "наталье", "Зайцева", "зайцевой"),
    ("Алексей", "алексею", "Павлов", "павлову"),
    ("Татьяна", "татьяне", "Белова", "беловой"),
    ("Роман", "роману", "Гусев", "гусеву"),
)

# The contracted patronymic is the register, not a curiosity: fifteen distinct
# contracted forms in the mined call grammar, and a row typed by ear carries one
# wherever the caller said one.
_PATRONYMIC_SHORT: dict[str, str] = {
    "Павлович": "палыч", "Михайлович": "михалыч", "Иванович": "иваныч",
    "Николаевич": "николаич", "Александрович": "саныч",
    "Сергеевич": "сергеич", "Дмитриевич": "димыч", "Алексеевич": "алексеич",
}

# Diminutives go in by hand. Neither a name dictionary nor pymorphy3 calls
# «ирочка» or «витёк» a name, so a whole way of naming a person never reaches a
# benchmark that draws only from a gazetteer.
_DIMINUTIVES: tuple[str, ...] = (
    "ирочка", "витёк", "серёжа", "женя", "петя", "наташа", "танюша", "юля",
    "саша", "вова", "лёша", "коля", "оля", "маша", "света",
)

# Street names are public toponyms, and both morphological kinds the mined
# grammar found are represented: adjectival (14 of 44) and surname-genitive (28
# of 44). A generator that writes only one measures half the language.
# Adjectival street names agree in gender with the type word they hang on, and
# the marker-free form elides «улица», so it is feminine. «переулок парковая» and
# «пер. Новая» are not Russian, and a corpus that produced them would be
# measuring the detector on strings the language does not contain.
_STREETS_ADJ_F: tuple[str, ...] = (
    "школьная", "вольная", "кирочная", "мончегорская", "клубная", "нижняя",
    "базисная", "зеленоградская", "вишнёвая", "буммашевская", "химзаводская",
    "подлесная", "наличная", "союзная", "советская", "центральная", "лесная",
    "садовая", "новая", "полевая", "заречная", "северная", "южная",
    "молодёжная", "солнечная", "октябрьская", "первомайская", "парковая",
)
_STREETS_ADJ_M: tuple[str, ...] = (
    "ленинский", "советский", "северный", "южный", "загородный", "смольный",
    "восточный", "западный", "первомайский", "октябрьский", "цветочный",
    "тихий", "берёзовый", "сосновый",
)
_STREETS_ADJ_N: tuple[str, ...] = (
    "воткинское", "заречное", "южное", "северное", "новое", "старое",
    "объездное",
)
_STREETS_GEN: tuple[str, ...] = (
    "ленина", "лермонтова", "комиссарова", "энгельса", "калашникова",
    "грибоедова", "чайковского", "гагарина", "кирова", "маяковского",
    "тимирязева", "пушкина", "гусева", "баранова", "шумайлова", "миронова",
    "коммунаров", "орджоникидзе", "дзержинского", "добролюбова", "чапаева",
    "некрасова", "толстого", "горького", "фрунзе", "челюскинцев",
)
_CITIES: tuple[str, ...] = (
    "Ижевск", "Казань", "Пермь", "Уфа", "Самара", "Тюмень", "Воронеж",
    "Краснодар", "Новосибирск", "Екатеринбург", "Ярославль", "Саратов",
    "Челябинск", "Омск", "Сортавала", "Тула", "Рязань", "Киров", "Пенза",
)
_EMAIL_DOMAINS: tuple[str, ...] = (
    "mail.ru", "yandex.ru", "gmail.com", "bk.ru", "list.ru", "inbox.ru",
    "rambler.ru",
)

# The mined openers. «<без вступления>» is the majority — 101 of 169 gold address
# replies open with the value itself — and it is the empty string here.
_OPENERS_VOICE: tuple[str, ...] = (
    "", "", "", "", "", "здравствуйте", "алло", "алло здравствуйте",
    "доброе утро", "а", "аа", "эээ", "нуу", "девушка", "слушайте", "значит",
)
_OPENERS_CHAT: tuple[str, ...] = (
    "", "", "", "здравствуйте", "добрый день", "привет", "подскажите",
)
_OPENERS_CLEAN: tuple[str, ...] = (
    "Добрый день,", "Здравствуйте,", "Доброе утро,",
)

# The customer wants something DONE with what the CRM knows. Without an ask the
# case is an address recitation and belongs in `transfer`.
_ASKS_VOICE: tuple[str, ...] = (
    "посмотрите что там по моему заказу",
    "гляньте пожалуйста что у вас записано",
    "скажите куда его повезут",
    "проверьте пожалуйста мою заявку",
    "что там по доставке",
    "поднимите мою карточку",
    "уточните что у вас записано",
    "перезвоните мне как проверите",
)
_ASKS_CLEAN: tuple[str, ...] = (
    "— посмотрите, пожалуйста, что у вас записано",
    "— уточните, пожалуйста, адрес доставки",
    "— проверьте, пожалуйста, мою карточку в базе",
    "— подскажите, куда поедет курьер",
)
_ASKS_CHAT: tuple[str, ...] = (
    "посмотрите что записано по заказу",
    "проверьте пожалуйста мою заявку",
    "что там с доставкой",
    "поднимите мою карточку в базе",
    "скажите на какой адрес поедет курьер",
    "нужно подтвердить данные по заказу",
)
_ASSISTANT_VOICE: tuple[str, ...] = (
    "секунду смотрю", "да слушаю вас", "минуту поднимаю карточку",
    "хорошо записал", "сейчас гляну", "угу понял", "да да вижу",
)
_ASSISTANT_CHAT: tuple[str, ...] = (
    "секунду, смотрю", "да, вижу заявку", "минуту, поднимаю карточку",
    "хорошо, проверяю", "сейчас гляну", "принято",
)
# Authored chat filler, and long enough that a `deep` case in a written register
# can reach the character floor without two hundred one-word messages.
_CHAT_FILLER: tuple[str, ...] = (
    "ага понял а долго вообще ждать курьера или можно как-то ускорить если "
    "я доплачу за срочность",
    "ну ок тогда я жду но у меня в обед совещание и я не смогу подойти к "
    "двери поэтому лучше заранее",
    "спасибо что проверяете а то в прошлый раз мне звонили три раза и всё "
    "равно привезли не туда",
    "а если меня не будет дома можно оставить у консьержа он всегда на "
    "месте до восьми вечера",
    "хорошо давайте так только предупредите пожалуйста заранее чтобы я "
    "успел спуститься вниз",
    "понятно а по времени как это будет вообще сегодня или уже завтра "
    "потому что мне надо планировать день",
    "ладно жду тогда а курьер сам позвонит или мне надо будет как-то "
    "отслеживать где он едет",
    "угу а можно вообще поменять способ оплаты или уже поздно раз заказ "
    "собран и уехал со склада",
    "это срочно вообще у меня послезавтра поездка и без этого я никуда не "
    "поеду так что очень надо",
    "а можно побыстрее как-то потому что я третий день жду и никто ничего "
    "внятного не говорит",
    "в общем я не понимаю почему так долго обрабатывается обычный заказ "
    "который есть на складе",
    "хорошо тогда я жду звонка и надеюсь что в этот раз всё будет нормально "
    "без переносов",
    "а скидка на следующий заказ будет или это только в приложении можно "
    "получить я не разбирался",
    "слушайте а вы вообще работаете в выходные или только по будням до "
    "шести вечера как обычно",
    "ну хорошо давайте попробуем ещё раз только теперь я никуда не уйду и "
    "буду ждать весь день дома",
    "да я всё понимаю просто хочется уже наконец получить то за что я "
    "заплатил почти месяц назад",
    "а если вдруг что-то не подойдёт можно будет вернуть или обменять и "
    "сколько это займёт времени",
    "ок принято тогда до связи и спасибо что разобрались я правда очень "
    "надеюсь на вашу помощь",
)


# --- mined shapes this family instantiates ---------------------------------
#
# `Provenance.shape` names an entry in the mined grammars, and «the form came
# from real speech» is worth nothing if nobody can check it. Every pattern below
# is verified against `mined/*.json` at build time and the build RAISES on a
# miss: 1070 of v2's 1334 cases carried that claim with nothing behind it, and
# nothing noticed for a version.

_SHAPES_NAME: tuple[str, ...] = (
    "<фамилия>",
    "<имя>",
    "<имя> <отчество>",
    "<имя> <фамилия>",
    "<фамилия> <имя> <отчество>",
    "это <имя>",
    "меня зовут <имя>",
    "меня зовут <имя> <отчество>",
    "моя фамилия <фамилия>",
)
_SHAPES_ADDR: tuple[str, ...] = (
    "<улица> <число прописью>",
    "улица <улица> <число прописью>",
    "<улица> <число прописью> <порядковое> подъезд",
    "<улица> <число прописью> <литера>",
    "<улица> <число прописью> корпус <число прописью>",
    "улица <улица> дом <число прописью>",
    "проспект <улица> <число прописью>",
    "переулок <улица> <число прописью>",
    "<улица> шоссе <число прописью>",
)
_SHAPES_NUMBER: tuple[str, ...] = (
    "непрерывный пробег числительных длиной 4-8 слов, без единой цифры",
    "<число> <число> — самая частая длина пробега; дом, квартира, кабинет, дата",
)

# Where each pattern was mined, so `Provenance.corpus`, `.selection` and
# `.licence` are not guessed per case. The dispatch value shapes come from the
# 400-reply MARKER census — selected by the words the detector also reads, biased
# upward by construction, and declared as such rather than laundered. The call
# shapes were mined across all 12 950 replies, which is a census of that corpus.
_SHAPE_ORIGIN: dict[str, tuple[str, str, str]] = {}
for _pattern in _SHAPES_ADDR:
    _SHAPE_ORIGIN[_pattern] = ("speech_rudevices", "marker", _LICENCE_RU)
for _pattern in _SHAPES_NAME + _SHAPES_NUMBER:
    _SHAPE_ORIGIN[_pattern] = ("speech_calls", "census", _LICENCE_CALLS)


# --- numerals as words -----------------------------------------------------
#
# The register has no digits at all: 0 of 53 324 measured utterances carry one.
# A house number, a phone and an order number are all RUNS OF NUMERAL WORDS here,
# which is exactly why the two defects this benchmark exists for are invisible to
# every written corpus.

_ONES: tuple[str, ...] = (
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь",
    "девять",
)
_TEENS: tuple[str, ...] = (
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
    "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
)
_TENS: tuple[str, ...] = (
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто",
)
_HUNDREDS: tuple[str, ...] = (
    "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
    "семьсот", "восемьсот", "девятьсот",
)
_ORDINALS: tuple[str, ...] = (
    "", "первый", "второй", "третий", "четвёртый", "пятый", "шестой",
    "седьмой", "восьмой", "девятый",
)

# Measured on the call corpus: 22.9% of every «-десят» form arrives contracted.
# That is the norm of the register and the generator produces it at the measured
# rate, not at a rate that feels safe.
_CONTRACTIONS: dict[str, tuple[str, ...]] = {
    "пятьдесят": ("песят", "пеесят", "пейсят"),
    "шестьдесят": ("шеесят", "шейсят", "шесят"),
    "восемьдесят": ("восемесят",),
}
# A numeral cut off mid-word, and a letter lost. Both are in the mined near-miss
# table, and both land INSIDE a value: 9 of 44 call-corpus addresses carry a
# transcription error inside the address itself.
_TRUNCATIONS: dict[str, tuple[str, ...]] = {
    "тридцать": ("триц", "тридц", "трис"),
    "девяносто": ("девяно",),
    "триста": ("тристо", "трииста"),
    "восемь": ("восем", "восемсь"),
    "четыре": ("четыыре",),
}


def _spell_int(value: int) -> str:
    """0..999 as words. Masculine, which is what a house number takes."""
    if not 0 <= value <= 999:
        raise BuildError(f"no spelling for {value}; this register dictates "
                         f"nothing above a thousand as one run")
    if value < 10:
        return _ONES[value]
    if value < 20:
        return _TEENS[value - 10]
    if value < 100:
        tens, ones = divmod(value, 10)
        return _TENS[tens] if not ones else f"{_TENS[tens]} {_ONES[ones]}"
    hundreds, rest = divmod(value, 100)
    if not rest:
        return _HUNDREDS[hundreds]
    return f"{_HUNDREDS[hundreds]} {_spell_int(rest)}"


def _spell_pairs(digits: str) -> str:
    """A digit string read out in twos, the way a number is actually dictated.

    «сорок один ноль девять шестьдесят семь» is 41-09-67. A leading zero inside a
    pair is spoken as «ноль» and never swallowed — 95 replies in the call corpus
    have a zero inside a number as a word, often doubled.
    """
    words: list[str] = []
    for index in range(0, len(digits), 2):
        chunk = digits[index:index + 2]
        if len(chunk) == 1:
            words.append(_ONES[int(chunk)])
        elif chunk[0] == "0":
            words.append(f"{_ONES[0]} {_ONES[int(chunk[1])]}")
        else:
            words.append(_spell_int(int(chunk)))
    return " ".join(words)


def _asr_noise(text: str, rng: random.Random) -> str:
    """Phonetic wear at the measured rate. ASR errors, not typing ones.

    `sloppy` gets keyboard errors and `voice_raw` gets these, and they are kept
    apart because they break different things: «Кзнецов» is a neighbouring key,
    «песят» and «триц» are a microphone.
    """
    out: list[str] = []
    for word in text.split(" "):
        if word in _CONTRACTIONS and rng.random() < 0.229:
            out.append(rng.choice(_CONTRACTIONS[word]))
        elif word in _TRUNCATIONS and rng.random() < 0.12:
            out.append(rng.choice(_TRUNCATIONS[word]))
        else:
            out.append(word)
    return " ".join(out)


# --- keyboard wear, for `sloppy` -------------------------------------------

_LOOKALIKE_OUT: dict[str, str] = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
}
_NEIGHBOURS: dict[str, str] = {
    "о": "л", "л": "о", "и": "т", "т": "и", "н": "г", "г": "н", "е": "к",
    "к": "е", "а": "в", "в": "а", "р": "п", "п": "р", "с": "м", "м": "с",
}


def _keyboard_noise(text: str, rng: random.Random) -> str:
    """One writing error in one word of five letters or more. Bounded on purpose.

    Two errors in one short word stop being a typo and become a different word,
    and a corpus that cannot say which it meant cannot score anybody.
    """
    words = text.split(" ")
    candidates = [i for i, word in enumerate(words) if len(word) >= 5]
    if not candidates:
        return text
    index = rng.choice(candidates)
    word = words[index]
    position = rng.randrange(1, len(word) - 1)
    mode = rng.randrange(4)
    if mode == 0:
        word = word[:position] + word[position + 1:]
    elif mode == 1:
        word = (word[:position] + word[position + 1] + word[position]
                + word[position + 2:])
    elif mode == 2:
        letter = word[position]
        word = (word[:position] + _LOOKALIKE_OUT.get(letter, letter)
                + word[position + 1:])
    else:
        letter = word[position]
        word = (word[:position] + _NEIGHBOURS.get(letter, letter)
                + word[position + 1:])
    words[index] = word
    return " ".join(words)


# --- identifiers, with their real checksums --------------------------------
#
# CHECKSUM-VALID, and that is a measurement decision rather than a flourish. The
# engine gates СНИЛС, ИНН and card on their own arithmetic, so a corpus of
# invalid numbers would report a miss the gateway was right to make and the whole
# per-type column would be noise. The algorithms are published; they are
# reimplemented here because a benchmark that imports from `pseudex/` reports our
# opinion of ourselves.

def _snils(rng: random.Random) -> str:
    body = "".join(str(rng.randrange(10)) for _ in range(9))
    if body.startswith("00"):
        body = "1" + body[1:]
    total = sum(int(digit) * (9 - index) for index, digit in enumerate(body))
    if total < 100:
        check = total
    elif total in (100, 101):
        check = 0
    else:
        check = total % 101
        if check in (100, 101):
            check = 0
    return f"{body[0:3]}-{body[3:6]}-{body[6:9]} {check:02d}"


def _inn_person(rng: random.Random) -> str:
    body = [rng.randrange(10) for _ in range(10)]
    if body[0] == 0:
        body[0] = 7
    weights_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    weights_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    eleventh = sum(w * d for w, d in zip(weights_11, body)) % 11 % 10
    twelfth = sum(w * d for w, d in zip(weights_12, body + [eleventh])) % 11 % 10
    return "".join(str(digit) for digit in body + [eleventh, twelfth])


def _card(rng: random.Random) -> str:
    prefix = rng.choice(("2200", "2202", "2204", "4276", "5536", "5469"))
    body = prefix + "".join(str(rng.randrange(10)) for _ in range(11))
    total = 0
    for index, digit in enumerate(reversed(body)):
        value = int(digit)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    full = body + str((10 - total % 10) % 10)
    return " ".join(full[i:i + 4] for i in range(0, 16, 4))


def _passport(rng: random.Random) -> str:
    return (f"{rng.randrange(10, 100)}{rng.randrange(10, 100)} "
            f"{rng.randrange(100000, 1000000)}")


_PLATE_LETTERS = "АВЕКМНОРСТУХ"


def _plate(rng: random.Random) -> str:
    head = rng.choice(_PLATE_LETTERS)
    tail = rng.choice(_PLATE_LETTERS) + rng.choice(_PLATE_LETTERS)
    region = rng.choice(("18", "16", "59", "02", "63", "77", "78", "116"))
    return f"{head}{rng.randrange(100, 1000)}{tail}{region}"


def _phone_digits(rng: random.Random) -> str:
    return "9" + "".join(str(rng.randrange(10)) for _ in range(9))


def _phone_written(digits: str, rng: random.Random) -> str:
    style = rng.randrange(4)
    if style == 0:
        return f"+7 {digits[0:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
    if style == 1:
        return f"8{digits}"
    if style == 2:
        return f"+7{digits}"
    return f"8 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"


def _phone_spoken(digits: str, rng: random.Random) -> str:
    """«восемь девятьсот двенадцать сорок один ноль девять шестьдесят семь».

    «плюс семь» does not occur once in the call corpus; a number opens with
    «восемь». The operator code is one group, the rest is read in twos.
    """
    head = f"восемь {_spell_int(int(digits[0:3]))}"
    # 3-2-2 after the operator code. Flat pairs across all seven would regroup
    # the number («семьдесят шесть девяносто восемь…» is a different phone), and
    # a corpus that mis-groups its own value scores the gateway on the mistake.
    body = f"{_spell_int(int(digits[3:6]))} {_spell_pairs(digits[6:10])}"
    return _asr_noise(f"{head} {body}", rng)


_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _email(given: str, surname: str, rng: random.Random) -> str:
    left = "".join(_TRANSLIT.get(ch, ch) for ch in given.lower())
    right = "".join(_TRANSLIT.get(ch, ch) for ch in surname.lower())
    style = rng.randrange(3)
    if style == 0:
        local = f"{left[0]}.{right}"
    elif style == 1:
        local = f"{right}{rng.randrange(60, 100)}"
    else:
        local = f"{left}_{right}"
    return f"{local}@{rng.choice(_EMAIL_DOMAINS)}"


def _birth_iso(rng: random.Random) -> str:
    return (f"{rng.randrange(1948, 2006):04d}-{rng.randrange(1, 13):02d}"
            f"-{rng.randrange(1, 29):02d}")


# --- people and addresses as records ---------------------------------------

@dataclass(frozen=True)
class _Person:
    surname: str
    given: str
    patronymic: str
    female: bool
    phone_digits: str
    email: str
    birth: str


@dataclass(frozen=True)
class _Address:
    city: str
    street: str          # lower case, as spoken
    street_type: str     # "" when marker-free — the majority shape
    type_after: bool     # «воткинское шоссе» puts the type after the name
    house: int
    letter: str          # «сто тридцать восемь а»
    korpus: int
    flat: int
    entrance: int
    house_marker: bool   # «улица вишнёвая дом двенадцать» says the word «дом»


def _make_person(rng: random.Random) -> _Person:
    female = rng.random() < 0.55
    if rng.random() < 0.12:
        surname = rng.choice(_SURNAMES_INVARIANT)
    else:
        pair = rng.choice(_SURNAMES)
        surname = pair[1] if female else pair[0]
    given, patronymic = rng.choice(_GIVEN_F if female else _GIVEN_M)
    return _Person(surname=surname, given=given, patronymic=patronymic,
                   female=female, phone_digits=_phone_digits(rng),
                   email=_email(given, surname, rng), birth=_birth_iso(rng))


# A mined value shape, spelled out as the fields it constrains. The shape is
# picked FIRST and the address is built to satisfy it, never the other way round:
# generating freely and labelling afterwards is how a corpus comes to claim a
# form its own text does not have, and `Provenance.shape` would then be exactly
# the unverifiable assertion the schema wrote it down to prevent.
_ADDR_SHAPE_FIELDS: dict[str, dict[str, object]] = {
    "<улица> <число прописью>": {},
    "улица <улица> <число прописью>": {"street_type": "улица"},
    "проспект <улица> <число прописью>": {"street_type": "проспект"},
    "переулок <улица> <число прописью>": {"street_type": "переулок"},
    "<улица> шоссе <число прописью>": {"street_type": "шоссе",
                                       "type_after": True},
    "<улица> <число прописью> <литера>": {"letter": True},
    "<улица> <число прописью> корпус <число прописью>": {"korpus": True},
    "<улица> <число прописью> <порядковое> подъезд": {"entrance": True},
    "улица <улица> дом <число прописью>": {"street_type": "улица",
                                           "house_marker": True},
}


# Which adjectival list each type word can take. «шоссе» is neuter and takes no
# genitive surname in this corpus: «энгельса шоссе» would need the other word
# order («шоссе Энтузиастов») and the mined shape puts the type last.
_TYPE_STREETS: dict[str, tuple[tuple[str, ...], ...]] = {
    "": (_STREETS_ADJ_F, _STREETS_GEN, _STREETS_GEN),
    "улица": (_STREETS_ADJ_F, _STREETS_GEN, _STREETS_GEN),
    "проспект": (_STREETS_ADJ_M, _STREETS_GEN, _STREETS_GEN),
    "переулок": (_STREETS_ADJ_M, _STREETS_GEN, _STREETS_GEN),
    "проезд": (_STREETS_ADJ_M, _STREETS_GEN, _STREETS_GEN),
    "шоссе": (_STREETS_ADJ_N,),
}


def _street_for_type(street_type: str, rng: random.Random) -> str:
    """A street name that agrees with its type word.

    Both morphological kinds the mined grammar found stay represented —
    adjectival 14 against surname-genitive 28 — and the two-to-one weighting in
    the table above is that measurement, not a preference.
    """
    if street_type not in _TYPE_STREETS:
        raise BuildError(f"no street list for type {street_type!r}")
    return rng.choice(rng.choice(_TYPE_STREETS[street_type]))


def _make_address(rng: random.Random, shape: str) -> _Address:
    """An address that instantiates ONE mined value shape and nothing else.

    63.9% of real address values carry no street-type word at all, and the shape
    table above keeps that: five of its nine entries are marker-free. A generator
    that writes «улица Ленина дом 50» every time measures the easy half of the
    language.
    """
    if shape not in _ADDR_SHAPE_FIELDS:
        raise BuildError(f"no address shape {shape!r}")
    fields = _ADDR_SHAPE_FIELDS[shape]
    street_type = str(fields.get("street_type", ""))
    return _Address(
        city=rng.choice(_CITIES),
        street=_street_for_type(street_type, rng),
        street_type=street_type,
        type_after=bool(fields.get("type_after", False)),
        house=rng.randrange(1, 190),
        letter=rng.choice(("а", "б", "в")) if fields.get("letter") else "",
        korpus=rng.randrange(1, 6) if fields.get("korpus") else 0,
        flat=0,
        entrance=rng.randrange(1, 9) if fields.get("entrance") else 0,
        house_marker=bool(fields.get("house_marker", False)))


def _make_crm_address(rng: random.Random) -> _Address:
    """An address the CRM stored. Not shape-constrained: nobody dictated it.

    The mined shapes describe how a person SAYS an address. A stored row is
    written by a form, so it carries the flat and the block a spoken value often
    leaves off, and claiming a speech shape over it would be a false provenance.
    """
    shape = rng.choice(tuple(_ADDR_SHAPE_FIELDS))
    address = _make_address(rng, shape)
    return _Address(
        city=address.city, street=address.street,
        street_type=address.street_type, type_after=address.type_after,
        house=address.house, letter=address.letter, korpus=address.korpus,
        flat=rng.randrange(1, 210) if rng.random() < 0.45 else 0,
        entrance=address.entrance, house_marker=False)


def _full_name(person: _Person) -> str:
    return f"{person.surname} {person.given} {person.patronymic}"


def _addr_crm(address: _Address) -> str:
    """What the customer's system stores. Machine text, always written out.

    The register gate reads user messages only, and this is why: a CRM answers in
    digits and commas whatever the caller's voice did, and judging a tool result
    by the speech gate would make the whole family unrepresentable.
    """
    parts = [f"г. {address.city}"]
    street = address.street.capitalize()
    if not address.street_type:
        parts.append(f"ул. {street}")
    elif address.type_after:
        parts.append(f"{street} {address.street_type}")
    else:
        short = {"улица": "ул.", "проспект": "пр-т", "переулок": "пер.",
                 "проезд": "проезд"}[address.street_type]
        parts.append(f"{short} {street}")
    house = f"д. {address.house}{address.letter}"
    if address.korpus:
        house += f" к. {address.korpus}"
    parts.append(house)
    if address.flat:
        parts.append(f"кв. {address.flat}")
    return ", ".join(parts)


def _addr_spoken(address: _Address, rng: random.Random) -> str:
    """The address as it is said: no digits, no commas, type word usually gone."""
    words: list[str] = []
    if address.street_type and not address.type_after:
        words.append(address.street_type)
    words.append(address.street)
    if address.street_type and address.type_after:
        words.append(address.street_type)
    if address.house_marker:
        words.append("дом")
    words.append(_spell_int(address.house))
    if address.letter:
        words.append(address.letter)
    if address.korpus:
        words.extend(("корпус", _spell_int(address.korpus)))
    if address.flat:
        words.extend(("квартира", _spell_int(address.flat)))
    if address.entrance:
        # The ordinal stands BEFORE the marker: 82 against 60 the other way.
        words.extend((_ORDINALS[address.entrance], "подъезд"))
    return _asr_noise(" ".join(words), rng)


def _addr_typed(address: _Address) -> str:
    """Lower case with digits — a messenger, or ASR with normalisation on."""
    words: list[str] = []
    if address.street_type and not address.type_after:
        words.append(address.street_type)
    words.append(address.street)
    if address.street_type and address.type_after:
        words.append(address.street_type)
    if address.house_marker:
        words.append("дом")
    words.append(f"{address.house}{address.letter}")
    if address.korpus:
        words.extend(("к", str(address.korpus)))
    if address.flat:
        words.extend(("кв", str(address.flat)))
    if address.entrance:
        words.extend((_ORDINALS[address.entrance], "подъезд"))
    return " ".join(words)


# --- text assembly, offsets recorded as characters are written -------------

@dataclass(frozen=True)
class _Slot:
    text: str
    tag: str


def _words(parts: tuple[object, ...]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Space-join strings and tagged slots, reporting each slot's offsets.

    Empty strings are dropped so an absent opener leaves no double space — which
    matters, because the offsets are the ground truth and a stray space in the
    middle of a span is a corpus defect that reads as a gateway failure.
    """
    pieces: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    position = 0
    kept = [part for part in parts
            if not (isinstance(part, str) and not part)]
    for index, part in enumerate(kept):
        if index:
            pieces.append(" ")
            position += 1
        if isinstance(part, _Slot):
            if part.tag in spans:
                raise BuildError(f"tag {part.tag!r} written twice into one string")
            if not part.text:
                raise BuildError(f"tag {part.tag!r} carries an empty value")
            spans[part.tag] = (position, position + len(part.text))
            pieces.append(part.text)
            position += len(part.text)
        elif isinstance(part, str):
            pieces.append(part)
            position += len(part)
        else:
            raise BuildError(f"cannot place {part!r} into text")
    return "".join(pieces), spans


# --- JSON emitted with the offsets known -----------------------------------
#
# `content` is the SERIALISED string always, because that is exactly what the
# gateway masks. Storing an object and serialising at score time would let a
# scorer's separator choices move every offset in the family, so the serialiser
# lives here and reports where it put each value.

def _escape_free(text: str) -> str:
    for character in text:
        if character in '"\\' or unicodedata.category(character) == "Cc":
            raise BuildError(
                f"{text!r} needs JSON escaping, and an escaped value no longer "
                f"equals its ground-truth span; tool-result values stay free of "
                f"quotes, backslashes and control characters")
    return text


def _emit(node: object, indent: int, level: int
          ) -> tuple[str, dict[str, tuple[int, int]]]:
    if isinstance(node, _Slot):
        body = _escape_free(node.text)
        return f'"{body}"', {node.tag: (1, 1 + len(body))}
    if isinstance(node, str):
        return f'"{_escape_free(node)}"', {}
    if isinstance(node, int):
        return str(node), {}
    if not isinstance(node, tuple) or len(node) != 2:
        raise BuildError(f"cannot emit {node!r}")
    kind, children = node
    pad = ("\n" + " " * (indent * (level + 1))) if indent else ""
    close = ("\n" + " " * (indent * level)) if indent else ""
    separator = "," + (pad if indent else " ")
    spans: dict[str, tuple[int, int]] = {}
    pieces: list[str] = []
    position = 1 + len(pad)
    if kind == "obj":
        for index, (key, value) in enumerate(children):
            if index:
                pieces.append(separator)
                position += len(separator)
            head = f'"{_escape_free(key)}": '
            pieces.append(head)
            position += len(head)
            body, inner = _emit(value, indent, level + 1)
            for tag, (start, end) in inner.items():
                if tag in spans:
                    raise BuildError(f"tag {tag!r} written twice")
                spans[tag] = (position + start, position + end)
            pieces.append(body)
            position += len(body)
        return "{" + pad + "".join(pieces) + close + "}", spans
    if kind == "arr":
        for index, value in enumerate(children):
            if index:
                pieces.append(separator)
                position += len(separator)
            body, inner = _emit(value, indent, level + 1)
            for tag, (start, end) in inner.items():
                if tag in spans:
                    raise BuildError(f"tag {tag!r} written twice")
                spans[tag] = (position + start, position + end)
            pieces.append(body)
            position += len(body)
        return "[" + pad + "".join(pieces) + close + "]", spans
    raise BuildError(f"unknown node kind {kind!r}")


def _serialise(node: object, indent: int
               ) -> tuple[str, dict[str, tuple[int, int]]]:
    text, spans = _emit(node, indent, 0)
    # A tool result the harness cannot parse is not a tool result. Cheap here,
    # and it catches an emitter bug at build time instead of at score time.
    json.loads(text)
    return text, spans


# --- specifications a payload hands back -----------------------------------

@dataclass(frozen=True)
class _ItemSpec:
    id: str
    type: str
    value: str
    canonical: str
    span: tuple[int, int]
    identity: str
    duty: str
    value_source: str
    spoken: bool
    tool_param: str


@dataclass(frozen=True)
class _NegSpec:
    value: str
    span: tuple[int, int]
    family: str
    why: str


@dataclass(frozen=True)
class _CallSpec:
    name: str
    arguments: dict[str, str]
    judged_args: tuple[str, ...]
    pii_items: tuple[str, ...]


@dataclass(frozen=True)
class _Payload:
    text: str
    tool: str
    tools: tuple[dict[str, object], ...]
    items: tuple[_ItemSpec, ...]
    negatives: tuple[_NegSpec, ...]
    links: tuple[tuple[str, str, str, str], ...]
    calls: tuple[_CallSpec, ...]
    final: schema.FinalAnswer
    note: str


# --- tool schemas ----------------------------------------------------------
#
# The provider's contract, not ours. Only the arguments CARRYING personal data
# are judged: `limit`, a page size and an idempotency key are the model's
# business, and comparing them would fail a gateway for a model's choice.

# Чем клиент просит сделать то, чего ждёт эталон. По одной строке на
# инструмент, словами самого корпуса и БЕЗ ЗНАЧЕНИЙ: просьба ссылается на
# карточку, а не пересказывает её.
_ACTION_REQUEST: dict[str, str] = {
    "notify_operator": "передайте эти данные оператору пожалуйста",
    "create_delivery": "оформите доставку по этой карточке",
    "schedule_courier": "назначьте курьера по этой карточке",
    "send_sms": "отправьте клиенту смс по этой карточке",
    "verify_identity": "сверьте личность по этим данным",
    "update_fiscal": "обновите реквизиты по этой карточке",
    "create_order": "оформите заказ по этой карточке",
    "find_client": "найдите клиента по этим данным",
}


def _tool(name: str, description: str,
          properties: tuple[tuple[str, str], ...]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": "string", "description": text}
                               for key, text in properties},
                "required": [key for key, _ in properties],
            },
        },
    }


_TOOL_LOOKUP = _tool("crm_get_client", "Поднять карточку клиента по номеру заказа",
                     (("order_no", "номер заказа"),))
_TOOL_SEARCH = _tool("crm_search_clients", "Найти клиентов по адресу или фамилии",
                     (("query", "строка поиска"),))
_TOOL_SMS = _tool("send_sms", "Отправить SMS клиенту",
                  (("phone", "номер телефона"), ("text", "текст сообщения")))
_TOOL_DELIVERY = _tool("create_delivery", "Оформить доставку",
                       (("recipient", "получатель"), ("address", "адрес"),
                        ("phone", "телефон получателя")))
_TOOL_COURIER = _tool("schedule_courier", "Назначить курьера",
                      (("address", "адрес"), ("phone", "телефон"),
                       ("slot", "интервал")))
_TOOL_VERIFY = _tool("verify_identity", "Сверить личность клиента",
                     (("passport", "серия и номер паспорта"),
                      ("birth_date", "дата рождения"), ("full_name", "ФИО")))
_TOOL_FISCAL = _tool("update_fiscal", "Обновить платёжные реквизиты",
                     (("inn", "ИНН"), ("snils", "СНИЛС"),
                      ("card", "номер карты")))
_TOOL_NOTIFY = _tool("notify_operator", "Передать заявку оператору",
                     (("full_name", "ФИО"), ("phone", "телефон")))


# --- negative material -----------------------------------------------------

def _order_no(rng: random.Random) -> str:
    return f"ORD-{rng.randrange(10000, 100000)}"


def _track_no(rng: random.Random) -> str:
    return f"R{rng.choice('ABEF')}{rng.randrange(100000000, 1000000000)}RU"


def _article(rng: random.Random) -> str:
    return f"АРТ-{rng.randrange(10, 100)}-{rng.randrange(1000, 10000)}"


def _slot_text(rng: random.Random) -> str:
    start = rng.randrange(8, 17)
    return f"с {start}:00 до {start + 3}:00"


def _spoken_order(rng: random.Random, shape: str) -> tuple[str, str]:
    """A dictated order number: three or four numeral words, not one digit.

    This is the shape that once got masked in production, and no digit-shaped
    pattern will ever see it. It is a negative in every voice case here.

    Both surfaces come back because inverse text normalisation produces the DIGIT
    string from the same utterance — a `voice_itn` case whose order number wears
    an `ORD-` prefix is a written form the caller never said.
    """
    if shape == _SHAPES_NUMBER[0]:
        length = 8      # four pairs: between four and eight numeral words
    elif shape == _SHAPES_NUMBER[1]:
        length = 4      # «<число> <число>», the commonest run in the corpus
    else:
        length = rng.choice((4, 6))
    digits = "".join(str(rng.randrange(10)) for _ in range(length))
    return _spell_pairs(digits), digits


_WHY_ORDER = ("номер заказа: не персональные данные, и без него следующий вызов "
              "промахивается мимо записи")
_WHY_TRACK = ("трек-номер отправления: девять цифр подряд, форма, на которую "
              "срабатывает любой числовой распознаватель")
_WHY_ARTICLE = "артикул товара: принадлежит товару, а не человеку"
_WHY_TOTAL = "сумма заказа: количество рублей, а не идентификатор"
_WHY_SLOT = "интервал доставки: время суток, а не дата рождения"
_WHY_CITY = "город как место склада: сам по себе никого не определяет"
# A key types the whole value, so the SPELLING of the key is a defect class in
# its own right: a gateway whose typing rests on one integration's field names
# leaks on the next customer's. Every alternative below is an ordinary name in a
# Russian delivery CRM.
_KEY_NAME: tuple[str, ...] = ("full_name", "fio", "client", "name",
                              "recipient_name")
_KEY_PHONE: tuple[str, ...] = ("phone", "tel", "contact_phone", "mobile")
_KEY_ADDRESS: tuple[str, ...] = ("address", "addr", "delivery_address",
                                 "ship_to")

_WHY_ROOM = "номер кабинета: число рядом с местом, которое адресом не является"

# Seven ways an operator writes the same note, and they differ in word order,
# vocabulary and in WHICH values appear — not in a counter. «улица Чехова, дом
# 29» and «улица Чехова, дом 43» differ by an increment, and a corpus of those
# measures one form many times and calls the result coverage.
_COMMENT_FRAMES: tuple[tuple[str, ...], ...] = (
    ("клиент просил перезвонить", "@name", "на", "@phone", "адрес доставки",
     "@addr", "домофон не работает встречает", "@dim", "у нас", "@room"),
    ("@name", "телефон", "@phone", "везти на", "@addr",
     "если не открывают звонить", "@dim"),
    ("перенесли на завтра получатель", "@name", "@addr", "контакт", "@phone",
     "@room", "не работает лифт"),
    ("звонила", "@dim", "сказала что заберёт сама адрес прежний", "@addr",
     "получатель", "@name", "телефон", "@phone"),
    ("оставить у соседей", "@addr", "созвон", "@phone", "получатель", "@name"),
    ("@addr", "подъезд со двора получатель", "@name", "@phone",
     "на месте будет", "@dim", "после обеда", "@room", "закрыт"),
    ("просили не звонить в дверь а набрать", "@phone", "получатель", "@name",
     "живёт", "@addr"),
)


def _history_rows(rng: random.Random, count: int
                  ) -> tuple[tuple[object, ...], tuple[tuple[str, str, str], ...]]:
    """Past orders. Bulk for a `deep` case, and every row is a negative.

    A page of order history is the honest way to make a tool result long: it adds
    characters without adding people, and it puts a dozen number-shaped strings in
    front of the gateway that it must leave alone.
    """
    rows: list[object] = []
    claims: list[tuple[str, str, str]] = []
    for index in range(count):
        order = _order_no(rng)
        track = _track_no(rng)
        rows.append(("obj", (
            ("order_no", _Slot(order, f"h{index}_order")),
            ("track", _Slot(track, f"h{index}_track")),
            ("date", f"2026-{rng.randrange(1, 9):02d}-{rng.randrange(1, 28):02d}"),
            ("total", f"{rng.randrange(400, 12000)} руб"),
            ("status", rng.choice(("доставлен", "отменён", "возврат"))),
        )))
        claims.append((f"h{index}_order", order, "order_number"))
        claims.append((f"h{index}_track", track, "order_number"))
    return tuple(rows), tuple(claims)


def _bulk_field(rng: random.Random, bulk: bool
                ) -> tuple[tuple[tuple[str, object], ...],
                           tuple[tuple[str, str, str], ...]]:
    if not bulk:
        return (), ()
    rows, claims = _history_rows(rng, rng.randrange(4, 8))
    return ((("history", ("arr", rows)),), claims)


def _claim_negatives(claims: tuple[tuple[str, str, str], ...],
                     spans: dict[str, tuple[int, int]]) -> tuple[_NegSpec, ...]:
    why = {"order_number": _WHY_ORDER, "quantity": _WHY_TOTAL}
    return tuple(_NegSpec(value=value, span=spans[tag], family=family,
                          why=why[family])
                 for tag, value, family in claims)


# --- payloads --------------------------------------------------------------

def _indent(rng: random.Random) -> int:
    """Compact, spaced or pretty. Real integrations ship all three."""
    return rng.choice((0, 0, 0, 2))


def _distinct_links(items: tuple[_ItemSpec, ...],
                    wanted: tuple[tuple[str, str, str], ...]
                    ) -> tuple[tuple[str, str, str, str], ...]:
    """Emit a `different` claim only where the two values really do differ.

    A pool draws collisions, and two items carrying the SAME string can only ever
    receive the same substitute — demanding two would fail every correct gateway
    on a defect of the corpus. Dropped rather than repaired, because a repaired
    pair is a different claim wearing the same id.
    """
    by_id = {item.id: item.value for item in items}
    return tuple((left, right, "different", why)
                 for left, right, why in wanted
                 if left in by_id and right in by_id
                 and by_id[left] != by_id[right])


def _flat_payload(case_id: str, rng: random.Random, order: str, track: str,
                  article: str, slot: str, bulk: bool,
                  caller: _Person | None) -> _Payload:
    """One flat CRM row. The base line the other five sub-shapes are read against.

    When the customer named themselves, the row the CRM returns is THEIRS — the
    only place in this family where one human is named twice across two messages,
    and where the gateway's linking decides whether the model sees one person or
    two.
    """
    person = caller if caller is not None else _make_person(rng)
    address = _make_crm_address(rng)
    phone = _phone_written(person.phone_digits, rng)
    total = f"{rng.randrange(500, 9000)} руб"
    city = rng.choice(_CITIES)
    # The same number twice, written two ways. One identity must reach the model
    # as ONE substitute or the model is looking at two customers.
    echo = f"8{person.phone_digits}" if phone.startswith("+7") else \
        f"+7 {person.phone_digits[0:3]} {person.phone_digits[3:6]}-" \
        f"{person.phone_digits[6:8]}-{person.phone_digits[8:10]}"
    # «улица Пушкина» is one step more specific than the city, and the city
    # identifies nobody under 152-ФЗ ст. 3 п. 1. Scored in the same column as the
    # full address those two averaged 71%, while the real figures were 94% and
    # 47% and the average described neither — so a bare street rides in every
    # flat row as the `optional` half of the duty split.
    pickup_street = _street_for_type("улица", rng)
    while pickup_street == address.street:
        # Not the customer's own street: the same name in two rows with opposite
        # duties would ask the gateway to treat one string two ways in one
        # message, which is a corpus defect wearing the shape of a finding.
        pickup_street = _street_for_type("улица", rng)
    pickup = f"ул. {pickup_street.capitalize()}"
    extra, bulk_claims = _bulk_field(rng, bulk)
    node = ("obj", (
        ("client_id", f"C-{rng.randrange(10000, 99999)}"),
        (rng.choice(_KEY_NAME), _Slot(_full_name(person), "t_name")),
        (rng.choice(_KEY_PHONE), _Slot(phone, "t_phone")),
        (rng.choice(_KEY_ADDRESS), _Slot(_addr_crm(address), "t_addr")),
        ("order_no", _Slot(order, "n_order")),
        ("track", _Slot(track, "n_track")),
        ("article", _Slot(article, "n_art")),
        ("status", rng.choice(("оплачен", "собран", "в пути", "ожидает"))),
        ("total", _Slot(total, "n_total")),
        ("delivery_slot", _Slot(slot, "n_slot")),
        ("warehouse", _Slot(city, "n_city")),
        ("pickup_point", _Slot(pickup, "t_pickup")),
        ("callback", _Slot(echo, "t_phone2")),
    ) + extra)
    text, spans = _serialise(node, _indent(rng))
    addr_value = _addr_crm(address)
    items = (
        _ItemSpec("t_name", "NAME", _full_name(person), _full_name(person),
                  spans["t_name"], f"{case_id}:client:NAME", "required", "pool",
                  False, ""),
        _ItemSpec("t_phone", "PHONE", phone, f"+7{person.phone_digits}",
                  spans["t_phone"], f"{case_id}:client:PHONE", "required",
                  "template", False, "phone"),
        _ItemSpec("t_addr", "LOC", addr_value, addr_value, spans["t_addr"],
                  f"{case_id}:client:LOC", "required", "pool", False, "address"),
        _ItemSpec("t_phone2", "PHONE", echo, f"+7{person.phone_digits}",
                  spans["t_phone2"], f"{case_id}:client:PHONE", "required",
                  "template", False, ""),
        _ItemSpec("t_pickup", "LOC", pickup, pickup, spans["t_pickup"],
                  f"{case_id}:pickup:LOC", "optional", "pool", False, ""),
    )
    negatives = (
        _NegSpec(order, spans["n_order"], "order_number", _WHY_ORDER),
        _NegSpec(track, spans["n_track"], "order_number", _WHY_TRACK),
        _NegSpec(article, spans["n_art"], "order_number", _WHY_ARTICLE),
        _NegSpec(total, spans["n_total"], "quantity", _WHY_TOTAL),
        _NegSpec(slot, spans["n_slot"], "time_of_day", _WHY_SLOT),
        _NegSpec(city, spans["n_city"], "city_reference", _WHY_CITY),
    ) + _claim_negatives(bulk_claims, spans)
    calls = (_CallSpec(
        name="schedule_courier",
        arguments={"address": addr_value, "phone": phone, "slot": slot},
        judged_args=("address", "phone"),
        pii_items=("t_addr", "t_phone")),)
    final = schema.FinalAnswer(must_contain=(), must_not_contain=(), answer="")
    return _Payload(
        text=text, tool="crm_get_client",
        tools=(_TOOL_LOOKUP, _TOOL_COURIER, _TOOL_SMS), items=items,
        negatives=negatives,
        links=(("t_phone", "t_phone2", "same",
                "один номер, записанный в двух формах: одна личность обязана "
                "получить одну подмену, иначе модель видит двух клиентов"),),
        calls=calls, final=final,
        note="плоская карточка CRM: ПД приходят ОТ системы клиента и обязаны "
             "быть замаскированы по дороге к модели, а номер заказа, трек и "
             "сумма — нет")


def _list_payload(case_id: str, rng: random.Random, order: str, track: str,
                  article: str, slot: str, bulk: bool) -> _Payload:
    count = rng.randrange(5, 8) if bulk else 3
    people = [_make_person(rng) for _ in range(count)]
    addresses = [_make_crm_address(rng) for _ in range(count)]
    # Two rows on ONE street whose house numbers are each other's digits
    # reversed. If a gateway's digit reindexing or partial resolution collapses
    # «Ленина 14» and «Ленина 41», two customers become one and the tool returns
    # 200 on the wrong human. The two values are checked to differ before the
    # `different` claim is written down: a link demanding two substitutes for one
    # identical string is a claim no correct gateway could satisfy.
    shared = addresses[0]
    flipped = int(str(shared.house)[::-1].lstrip("0") or "0")
    other_house = flipped if flipped and flipped != shared.house \
        else shared.house + 7
    addresses[1] = _Address(
        city=shared.city, street=shared.street, street_type=shared.street_type,
        type_after=shared.type_after, house=other_house, letter="", korpus=0,
        flat=shared.flat, entrance=0, house_marker=False)
    if _addr_crm(addresses[1]) == _addr_crm(shared):
        raise BuildError(f"{case_id}: the two neighbouring rows render to one "
                         f"address, so `different` would be unsatisfiable")
    target = rng.randrange(count)
    # One integration, one key spelling: the rows of a single response agree
    # with each other even when two customers' systems do not.
    name_key = rng.choice(_KEY_NAME)
    phone_key = rng.choice(_KEY_PHONE)
    address_key = rng.choice(_KEY_ADDRESS)
    rows: list[object] = []
    for index, (person, address) in enumerate(zip(people, addresses)):
        rows.append(("obj", (
            ("client_id", f"C-{rng.randrange(10000, 99999)}"),
            (name_key, _Slot(_full_name(person), f"p{index}_name")),
            (phone_key, _Slot(_phone_written(person.phone_digits, rng),
                              f"p{index}_phone")),
            (address_key, _Slot(_addr_crm(address), f"p{index}_addr")),
            ("order_no", _Slot(_order_no(rng), f"p{index}_order")),
        )))
    extra, bulk_claims = _bulk_field(rng, bulk)
    node = ("obj", (
        ("query", rng.choice(("поиск по клиенту", "поиск по заказу",
                              "совпадения в базе"))),
        ("found", count),
        ("clients", ("arr", tuple(rows))),
        ("track", _Slot(track, "n_track")),
        ("article", _Slot(article, "n_art")),
    ) + extra)
    text, spans = _serialise(node, _indent(rng))

    items: list[_ItemSpec] = []
    negatives: list[_NegSpec] = [
        _NegSpec(track, spans["n_track"], "order_number", _WHY_TRACK),
        _NegSpec(article, spans["n_art"], "order_number", _WHY_ARTICLE),
    ]
    for index, (person, address) in enumerate(zip(people, addresses)):
        name = _full_name(person)
        phone = text[spans[f"p{index}_phone"][0]:spans[f"p{index}_phone"][1]]
        addr = _addr_crm(address)
        who = "client" if index == target else f"other{index}"
        items.extend((
            _ItemSpec(f"p{index}_name", "NAME", name, name,
                      spans[f"p{index}_name"], f"{case_id}:{who}:NAME",
                      "required", "pool", False,
                      "full_name" if index == target else ""),
            _ItemSpec(f"p{index}_phone", "PHONE", phone,
                      f"+7{person.phone_digits}", spans[f"p{index}_phone"],
                      f"{case_id}:{who}:PHONE", "required", "template", False,
                      "phone" if index == target else ""),
            _ItemSpec(f"p{index}_addr", "LOC", addr, addr,
                      spans[f"p{index}_addr"], f"{case_id}:{who}:LOC",
                      "required", "pool", False, ""),
        ))
        row_order = text[spans[f"p{index}_order"][0]:spans[f"p{index}_order"][1]]
        negatives.append(_NegSpec(row_order, spans[f"p{index}_order"],
                                  "order_number", _WHY_ORDER))
    negatives.extend(_claim_negatives(bulk_claims, spans))

    # A stranger's value is forbidden from the reply — but only if it is not ALSO
    # the target's. Two rows in a CRM search really can carry the same name, and
    # forbidding the customer's own datum would fail a gateway for being right.
    mine = {item.value for item in items if item.id.startswith(f"p{target}_")}
    forbidden = tuple(sorted(
        {item.value for item in items
         if not item.id.startswith(f"p{target}_")
         and item.type in ("PHONE", "NAME") and item.value not in mine}))
    calls = (_CallSpec(
        name="notify_operator",
        arguments={
            "full_name": _full_name(people[target]),
            "phone": text[spans[f"p{target}_phone"][0]:
                          spans[f"p{target}_phone"][1]]},
        judged_args=("full_name", "phone"),
        pii_items=(f"p{target}_name", f"p{target}_phone")),)
    return _Payload(
        text=text, tool="crm_search_clients",
        tools=(_TOOL_SEARCH, _TOOL_NOTIFY, _TOOL_SMS), items=tuple(items),
        negatives=tuple(negatives),
        links=_distinct_links(items, (
            ("p0_addr", "p1_addr",
             "две записи на одной улице с разными номерами дома: слияние этих "
             "двух значений отдаёт инструменту чужого человека"),
            ("p0_phone", "p1_phone",
             "разные номера разных людей в одном ответе CRM"),
            (f"p{target}_name", f"p{(target + 1) % count}_name",
             "две карточки — два человека, две подмены"))),
        calls=calls,
        final=schema.FinalAnswer(
            must_contain=(), must_not_contain=forbidden, answer=""),
        note="ответ CRM списком: модель обязана действовать по ОДНОЙ записи, а "
             "данные остальных людей не имеют права попасть ни в вызов, ни в "
             "итоговый ответ")


def _latin_kv_payload(case_id: str, rng: random.Random, order: str, track: str,
                      slot: str, bulk: bool, anonymous: bool) -> _Payload:
    """Latin keys type the value. `anonymous` drops every NAME and LOC.

    A `template` case may carry only the types no speech corpus holds, and the
    schema refuses one carrying NAME or LOC. A verification endpoint that returns
    identifiers and a client id — and no name at all — is the shape that says so
    honestly, rather than a name quietly relabelled `optional`.
    """
    person = _make_person(rng)
    passport = _passport(rng)
    snils = _snils(rng)
    inn = _inn_person(rng)
    card = _card(rng)
    phone = _phone_written(person.phone_digits, rng)
    plate = _plate(rng)
    total = f"{rng.randrange(500, 9000)} руб"
    identity_fields: tuple[tuple[str, object], ...] = (
        ("passport", _Slot(passport, "t_passport")),
        ("snils", _Slot(snils, "t_snils")),
        ("inn", _Slot(inn, "t_inn")),
        ("birth_date", _Slot(person.birth, "t_dob")),
    )
    if not anonymous:
        identity_fields = (("full_name", _Slot(_full_name(person), "t_name")),
                           ) + identity_fields
    contact_fields: tuple[tuple[str, object], ...] = (
        ("phone", _Slot(phone, "t_phone")),
        ("email", _Slot(person.email, "t_email")),
    )
    if not anonymous:
        address = _make_crm_address(rng)
        contact_fields += (("address", _Slot(_addr_crm(address), "t_addr")),)
    extra, bulk_claims = _bulk_field(rng, bulk)
    node = ("obj", (
        ("client_id", f"C-{rng.randrange(10000, 99999)}"),
        ("identity", ("obj", identity_fields)),
        ("contacts", ("obj", contact_fields)),
        ("billing", ("obj", (("card", _Slot(card, "t_card")),
                             ("total", _Slot(total, "n_total"))))),
        ("vehicle", ("obj", (("plate", _Slot(plate, "t_plate")),))),
        ("order_no", _Slot(order, "n_order")),
        ("track", _Slot(track, "n_track")),
        ("delivery_slot", _Slot(slot, "n_slot")),
    ) + extra)
    text, spans = _serialise(node, _indent(rng))
    # `tool_param` is claimed only where THIS case's expected call consumes the
    # value. An item naming a parameter nothing calls reads as a round trip that
    # was checked and was not.
    items: list[_ItemSpec] = [
        _ItemSpec("t_passport", "PASSPORT", passport, passport.replace(" ", ""),
                  spans["t_passport"], f"{case_id}:client:PASSPORT", "required",
                  "template", False, "" if anonymous else "passport"),
        _ItemSpec("t_snils", "SNILS", snils, snils, spans["t_snils"],
                  f"{case_id}:client:SNILS", "required", "template", False,
                  "snils" if anonymous else ""),
        _ItemSpec("t_inn", "INN", inn, inn, spans["t_inn"],
                  f"{case_id}:client:INN", "required", "template", False,
                  "inn" if anonymous else ""),
        _ItemSpec("t_dob", "DOB", person.birth, person.birth, spans["t_dob"],
                  f"{case_id}:client:DOB", "required", "template", False,
                  "" if anonymous else "birth_date"),
        _ItemSpec("t_phone", "PHONE", phone, f"+7{person.phone_digits}",
                  spans["t_phone"], f"{case_id}:client:PHONE", "required",
                  "template", False, ""),
        _ItemSpec("t_email", "EMAIL", person.email, person.email,
                  spans["t_email"], f"{case_id}:client:EMAIL", "required",
                  "template", False, ""),
        _ItemSpec("t_card", "CARD", card, card.replace(" ", ""),
                  spans["t_card"], f"{case_id}:client:CARD", "required",
                  "template", False, "card" if anonymous else ""),
        _ItemSpec("t_plate", "PLATE", plate, plate, spans["t_plate"],
                  f"{case_id}:client:PLATE", "required", "template", False, ""),
    ]
    if not anonymous:
        name = _full_name(person)
        addr = text[spans["t_addr"][0]:spans["t_addr"][1]]
        items.extend((
            _ItemSpec("t_name", "NAME", name, name, spans["t_name"],
                      f"{case_id}:client:NAME", "required", "pool", False,
                      "full_name"),
            _ItemSpec("t_addr", "LOC", addr, addr, spans["t_addr"],
                      f"{case_id}:client:LOC", "required", "pool", False, ""),
        ))
    negatives = (
        _NegSpec(order, spans["n_order"], "order_number", _WHY_ORDER),
        _NegSpec(track, spans["n_track"], "order_number", _WHY_TRACK),
        _NegSpec(total, spans["n_total"], "quantity", _WHY_TOTAL),
        _NegSpec(slot, spans["n_slot"], "time_of_day", _WHY_SLOT),
    ) + _claim_negatives(bulk_claims, spans)
    if anonymous:
        calls = (_CallSpec(
            name="update_fiscal",
            arguments={"inn": inn, "snils": snils, "card": card},
            judged_args=("inn", "snils", "card"),
            pii_items=("t_inn", "t_snils", "t_card")),)
        tools = (_TOOL_LOOKUP, _TOOL_FISCAL)
    else:
        calls = (_CallSpec(
            name="verify_identity",
            arguments={"passport": passport, "birth_date": person.birth,
                       "full_name": _full_name(person)},
            judged_args=("passport", "birth_date", "full_name"),
            pii_items=("t_passport", "t_dob", "t_name")),)
        tools = (_TOOL_LOOKUP, _TOOL_VERIFY, _TOOL_FISCAL)
    # The one value in this corpus a reply is REQUIRED to carry, and an address
    # is deliberately not it: a model that writes «Ижевск, Ленина 56» instead of
    # «г. Ижевск, ул. Ленина, д. 56» has reformatted, not lost, and scoring that
    # as `value_missing` would charge the gateway for the model's prose. An
    # e-mail comes back character for character or it did not come back.
    readback = (person.email,) if rng.random() < 0.5 else ()
    return _Payload(
        text=text, tool="crm_get_client", tools=tools, items=tuple(items),
        negatives=negatives, links=(), calls=calls,
        final=schema.FinalAnswer(must_contain=readback, must_not_contain=(),
                                 answer=""),
        note="латинский ключ типизирует значение целиком: пере-гейтинг такого "
             "спана через русский список подсказок однажды потерял "
             "{\"passport\": ...} целиком, тогда как тот же номер после слова "
             "«паспорт» маскировался")


def _iso_date_payload(case_id: str, rng: random.Random, order: str, track: str,
                      slot: str, bulk: bool) -> _Payload:
    person = _make_person(rng)
    passport = _passport(rng)
    phone = _phone_written(person.phone_digits, rng)
    total = f"{rng.randrange(500, 9000)} руб"
    extra, bulk_claims = _bulk_field(rng, bulk)
    node = ("obj", (
        ("client_id", f"C-{rng.randrange(10000, 99999)}"),
        ("full_name", _Slot(_full_name(person), "t_name")),
        ("birth_date", _Slot(person.birth, "t_dob")),
        ("passport", _Slot(passport, "t_passport")),
        ("phone", _Slot(phone, "t_phone")),
        # A document date beside a birth date, and the pair is the whole point:
        # one is personal data because its key says so and the other is not
        # because its key says so. `created_at` rides unclaimed — see the module
        # docstring for why a misfiled negative family would be worse.
        ("created_at", f"2026-{rng.randrange(1, 9):02d}-"
                       f"{rng.randrange(1, 28):02d}"),
        ("order_no", _Slot(order, "n_order")),
        ("track", _Slot(track, "n_track")),
        ("total", _Slot(total, "n_total")),
        ("delivery_slot", _Slot(slot, "n_slot")),
    ) + extra)
    text, spans = _serialise(node, _indent(rng))
    items = (
        _ItemSpec("t_name", "NAME", _full_name(person), _full_name(person),
                  spans["t_name"], f"{case_id}:client:NAME", "required", "pool",
                  False, "full_name"),
        _ItemSpec("t_dob", "DOB", person.birth, person.birth, spans["t_dob"],
                  f"{case_id}:client:DOB", "required", "template", False,
                  "birth_date"),
        _ItemSpec("t_passport", "PASSPORT", passport, passport.replace(" ", ""),
                  spans["t_passport"], f"{case_id}:client:PASSPORT", "required",
                  "template", False, "passport"),
        _ItemSpec("t_phone", "PHONE", phone, f"+7{person.phone_digits}",
                  spans["t_phone"], f"{case_id}:client:PHONE", "required",
                  "template", False, ""),
    )
    negatives = (
        _NegSpec(order, spans["n_order"], "order_number", _WHY_ORDER),
        _NegSpec(track, spans["n_track"], "order_number", _WHY_TRACK),
        _NegSpec(total, spans["n_total"], "quantity", _WHY_TOTAL),
        _NegSpec(slot, spans["n_slot"], "time_of_day", _WHY_SLOT),
    ) + _claim_negatives(bulk_claims, spans)
    calls = (_CallSpec(
        name="verify_identity",
        arguments={"passport": passport, "birth_date": person.birth,
                   "full_name": _full_name(person)},
        judged_args=("passport", "birth_date", "full_name"),
        pii_items=("t_passport", "t_dob", "t_name")),)
    return _Payload(
        text=text, tool="crm_get_client",
        tools=(_TOOL_LOOKUP, _TOOL_VERIFY), items=items, negatives=negatives,
        links=(), calls=calls,
        final=schema.FinalAnswer(must_contain=(), must_not_contain=(),
                                 answer=""),
        note="дата рождения в ISO рядом с датой документа: одна персональные "
             "данные по ключу, вторая — нет, и обе выглядят одинаково")


def _comment_payload(case_id: str, rng: random.Random, order: str, track: str,
                     slot: str, bulk: bool) -> _Payload:
    """Personal data in PROSE inside a JSON string, in an oblique case.

    No key types it and no schema surrounds it. The name is declined, which is
    where the round trip breaks in a way detection cannot see: recovered as
    «Марине Петровой» it is a declined name written into the customer's CRM, and
    `classify_break` has a kind for exactly that.
    """
    given, given_obl, surname, surname_obl = rng.choice(_OBLIQUE_PEOPLE)
    digits = _phone_digits(rng)
    phone = _phone_written(digits, rng)
    address = _make_crm_address(rng)
    addr_typed = _addr_typed(address)
    room = f"кабинет {rng.randrange(101, 520)}"
    diminutive = rng.choice(_DIMINUTIVES)
    total = f"{rng.randrange(500, 9000)} руб"
    values = {"@name": (f"{given_obl} {surname_obl}", "t_name"),
              "@phone": (phone, "t_phone"), "@addr": (addr_typed, "t_addr"),
              "@dim": (diminutive, "t_dim"), "@room": (room, "n_room")}
    frame = rng.choice(_COMMENT_FRAMES)
    prose, prose_spans = _words(tuple(
        _Slot(*values[token]) if token in values else token
        for token in frame))
    extra, bulk_claims = _bulk_field(rng, bulk)
    node = ("obj", (
        ("order_no", _Slot(order, "n_order")),
        ("status", rng.choice(("собран", "в пути", "ожидает"))),
        ("total", _Slot(total, "n_total")),
        ("track", _Slot(track, "n_track")),
        ("delivery_slot", _Slot(slot, "n_slot")),
        (rng.choice(("comment", "note", "operator_note", "remark")),
         _Slot(prose, "comment")),
    ) + extra)
    text, spans = _serialise(node, _indent(rng))
    base = spans["comment"][0]
    inner = {tag: (base + start, base + end)
             for tag, (start, end) in prose_spans.items()}
    nominative = f"{given} {surname}"
    items = [
        _ItemSpec("t_name", "NAME", f"{given_obl} {surname_obl}", nominative,
                  inner["t_name"], f"{case_id}:client:NAME", "required", "pool",
                  False, "full_name"),
        _ItemSpec("t_phone", "PHONE", phone, f"+7{digits}", inner["t_phone"],
                  f"{case_id}:client:PHONE", "required", "template", False,
                  "phone"),
        _ItemSpec("t_addr", "LOC", addr_typed, addr_typed, inner["t_addr"],
                  f"{case_id}:client:LOC", "required", "pool", False, ""),
    ]
    negatives = [
        _NegSpec(order, spans["n_order"], "order_number", _WHY_ORDER),
        _NegSpec(track, spans["n_track"], "order_number", _WHY_TRACK),
        _NegSpec(total, spans["n_total"], "quantity", _WHY_TOTAL),
        _NegSpec(slot, spans["n_slot"], "time_of_day", _WHY_SLOT),
    ]
    links: tuple[tuple[str, str, str, str], ...] = ()
    if "t_dim" in inner:
        items.append(_ItemSpec(
            "t_dim", "NAME", diminutive, diminutive, inner["t_dim"],
            f"{case_id}:meeting:NAME", "required", "pool", False, ""))
        links = (("t_name", "t_dim", "unjudged",
                  "уменьшительное имя во второй половине комментария: диалог не "
                  "решает, тот же это человек или другой, и требовать "
                  "связывания значило бы судить шлюз по сведениям, которых в "
                  "тексте нет"),)
    if "n_room" in inner:
        negatives.append(_NegSpec(room, inner["n_room"], "room_number",
                                  _WHY_ROOM))
    negatives.extend(_claim_negatives(bulk_claims, spans))
    calls = (_CallSpec(
        name="notify_operator",
        arguments={"full_name": nominative, "phone": phone},
        judged_args=("full_name", "phone"),
        pii_items=("t_name", "t_phone")),)
    return _Payload(
        text=text, tool="crm_get_client",
        tools=(_TOOL_LOOKUP, _TOOL_NOTIFY, _TOOL_SMS), items=tuple(items),
        negatives=tuple(negatives), links=tuple(links), calls=calls,
        final=schema.FinalAnswer(must_contain=(), must_not_contain=(),
                                 answer=""),
        note="ПД прозой внутри поля comment: ключ ничего не типизирует, имя "
             "стоит в косвенном падеже, и вернуть его надо именительным")


def _spoken_payload(case_id: str, rng: random.Random, order: str, track: str,
                    slot: str, bulk: bool) -> _Payload:
    """The row was typed BY EAR. Not one digit in any personal value.

    Both known engine defects live here. The address has a WORD for a house
    number, so a substitute chosen by looking for `\\d` degrades to a bare
    settlement and the model is handed «Сортавала» — detection reports found, the
    round trip resolves, and only the SHAPE of the string says otherwise. The
    phone is a run of numeral words, and libphonenumber and every checksum wait
    for digits.
    """
    person = _make_person(rng)
    address = _make_crm_address(rng)
    addr_words = _addr_spoken(address, rng)
    phone_words = _phone_spoken(person.phone_digits, rng)
    patronymic = _PATRONYMIC_SHORT.get(person.patronymic, person.patronymic)
    name_words = f"{person.surname} {person.given} {patronymic}".lower()
    total = f"{rng.randrange(500, 9000)} руб"
    extra, bulk_claims = _bulk_field(rng, bulk)
    node = ("obj", (
        ("order_no", _Slot(order, "n_order")),
        ("source", "записано со слов клиента оператором"),
        ("client", _Slot(name_words, "t_name")),
        ("phone", _Slot(phone_words, "t_phone")),
        ("address", _Slot(addr_words, "t_addr")),
        ("track", _Slot(track, "n_track")),
        ("total", _Slot(total, "n_total")),
        ("delivery_slot", _Slot(slot, "n_slot")),
    ) + extra)
    text, spans = _serialise(node, _indent(rng))
    items = (
        _ItemSpec("t_name", "NAME", name_words, name_words, spans["t_name"],
                  f"{case_id}:client:NAME", "required", "pool", True,
                  "recipient"),
        _ItemSpec("t_phone", "PHONE", phone_words, f"+7{person.phone_digits}",
                  spans["t_phone"], f"{case_id}:client:PHONE", "required",
                  "template", True, "phone"),
        _ItemSpec("t_addr", "LOC", addr_words, addr_words, spans["t_addr"],
                  f"{case_id}:client:LOC", "required", "pool", True, "address"),
    )
    negatives = (
        _NegSpec(order, spans["n_order"], "order_number", _WHY_ORDER),
        _NegSpec(track, spans["n_track"], "order_number", _WHY_TRACK),
        _NegSpec(total, spans["n_total"], "quantity", _WHY_TOTAL),
        _NegSpec(slot, spans["n_slot"], "time_of_day", _WHY_SLOT),
    ) + _claim_negatives(bulk_claims, spans)
    # The expected argument is what was WRITTEN, never a digit form: demanding
    # digits back would score the model's arithmetic, and a digit form arriving
    # is `renumbered`, which is a break kind and not a pass.
    calls = (_CallSpec(
        name="create_delivery",
        arguments={"recipient": name_words, "address": addr_words,
                   "phone": phone_words},
        judged_args=("recipient", "address", "phone"),
        pii_items=("t_name", "t_addr", "t_phone")),)
    return _Payload(
        text=text, tool="crm_get_client",
        tools=(_TOOL_LOOKUP, _TOOL_DELIVERY), items=items, negatives=negatives,
        links=(), calls=calls,
        final=schema.FinalAnswer(must_contain=(), must_not_contain=(),
                                 answer=""),
        note="карточка, набранная со слуха: дом словом и телефон пробегом "
             "числительных — обе формы, в которых сегодняшние дефекты движка "
             "живут и которых письменный корпус не производит")


def _payload(subshape: str, case_id: str, rng: random.Random, bulk: bool,
             anonymous: bool, caller: _Person | None) -> _Payload:
    order = _order_no(rng)
    track = _track_no(rng)
    article = _article(rng)
    slot = _slot_text(rng)
    if subshape == "flat":
        return _flat_payload(case_id, rng, order, track, article, slot, bulk,
                             caller)
    if subshape == "list":
        return _list_payload(case_id, rng, order, track, article, slot, bulk)
    if subshape == "latin_kv":
        return _latin_kv_payload(case_id, rng, order, track, slot, bulk,
                                 anonymous)
    if subshape == "iso_date":
        return _iso_date_payload(case_id, rng, order, track, slot, bulk)
    if subshape == "comment":
        return _comment_payload(case_id, rng, order, track, slot, bulk)
    if subshape == "spoken":
        return _spoken_payload(case_id, rng, order, track, slot, bulk)
    raise BuildError(f"unknown sub-shape {subshape!r}")


# --- the customer's turn ---------------------------------------------------

# The slots each mined name shape fills, and the cue words standing in front of
# the value. The cue is NOT part of the span: «меня зовут» licenses the neighbour,
# it does not name it, and putting it inside the gold would make a gateway that
# masks correctly look like one that over-reaches.
_NAME_SHAPE_PARTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "<фамилия>": ("", ("surname",)),
    "<имя>": ("", ("given",)),
    "<имя> <отчество>": ("", ("given", "patronymic")),
    "<имя> <фамилия>": ("", ("given", "surname")),
    "<фамилия> <имя> <отчество>": ("", ("surname", "given", "patronymic")),
    "это <имя>": ("это", ("given",)),
    "меня зовут <имя>": ("меня зовут", ("given",)),
    "меня зовут <имя> <отчество>": ("меня зовут", ("given", "patronymic")),
    "моя фамилия <фамилия>": ("моя фамилия", ("surname",)),
}
# Measured on the call corpus: surname alone 350, given name alone 255, given
# plus patronymic 109, the full three 23, given plus surname 23. The weights
# below follow that, so the commonest way to name a person is also the commonest
# case — a generator that always writes ФИО tests one form out of nine.
_NAME_SHAPE_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("<фамилия>", 35), ("<имя>", 26), ("<имя> <отчество>", 11),
    ("<имя> <фамилия>", 4), ("<фамилия> <имя> <отчество>", 4),
    ("это <имя>", 6), ("меня зовут <имя>", 5),
    ("меня зовут <имя> <отчество>", 5), ("моя фамилия <фамилия>", 4),
)


def _pick_name_shape(rng: random.Random) -> str:
    total = sum(weight for _, weight in _NAME_SHAPE_WEIGHTS)
    draw = rng.randrange(total)
    for shape, weight in _NAME_SHAPE_WEIGHTS:
        draw -= weight
        if draw < 0:
            return shape
    raise BuildError("name shape weights do not sum")


def _name_for_shape(person: _Person, shape: str,
                    register: str) -> tuple[str, str]:
    """(cue words, the value) for one mined name shape.

    Written registers capitalise; the speech ones do not, and neither does a
    messenger. The lower-case surname is not a cosmetic detail — the bulk surname
    dictionary is capital-only, and «фамилия волков» in lower case is precisely
    where a gateway leaks.
    """
    if shape not in _NAME_SHAPE_PARTS:
        raise BuildError(f"no name shape {shape!r}")
    cue, slots = _NAME_SHAPE_PARTS[shape]
    value = " ".join({"surname": person.surname, "given": person.given,
                      "patronymic": person.patronymic}[slot] for slot in slots)
    return cue, value if register == "clean" else value.lower()


def _render_address(address: _Address, register: str,
                    rng: random.Random) -> str:
    """Words in `voice_raw`, digits everywhere else. ITN restores digits, not
    commas, so nothing here ever produces one."""
    return (_addr_spoken(address, rng) if register == "voice_raw"
            else _addr_typed(address))


def _compose_request(register: str, shape: str, person: _Person | None,
                     address: _Address | None, order: str,
                     spoken_order: tuple[str, str], rng: random.Random
                     ) -> tuple[str, dict[str, tuple[int, int]]]:
    """Build the customer's turn out of tagged pieces, in its register.

    The register wear is applied to the PIECES before they are placed, never to
    the finished string: a transform that runs afterwards moves every offset
    behind it, and the offsets are the ground truth.

    The mined shape decides which value the turn carries, so the text and the
    `Provenance.shape` beside it cannot come apart. Freely drawing a name and
    then labelling the case with whatever shape the sampler happened to pick is
    how «the form came from real speech» stops being checkable.
    """
    speech = register in schema.SPEECH_REGISTERS
    if register == "clean":
        opener: str = rng.choice(_OPENERS_CLEAN)
        ask = rng.choice(_ASKS_CLEAN)
    else:
        opener = rng.choice(_OPENERS_VOICE if speech else _OPENERS_CHAT)
        ask = rng.choice(_ASKS_VOICE if speech else _ASKS_CHAT)
    words, digits = spoken_order
    if register == "voice_raw":
        order_surface = words
    elif register == "voice_itn":
        # ITN turns the dictated run into digits and nothing else. The `ORD-`
        # prefix is a written form nobody says out loud.
        order_surface = digits
    else:
        order_surface = order
    cue, name_surface = ("", "")
    if person is not None:
        cue, name_surface = _name_for_shape(person, shape, register)
    address_surface = ("" if address is None
                       else _render_address(address, register, rng))
    if register == "sloppy":
        ask = _keyboard_noise(ask, rng)
        if name_surface and rng.random() < 0.5:
            name_surface = _keyboard_noise(name_surface, rng)
        elif address is not None and rng.random() < 0.5:
            # The typo lands on the STREET NAME, never on «улица» or «подъезд».
            # A misspelt structural word would make the case stop instantiating
            # the shape it declares, and a corpus whose text and provenance
            # disagree is the thing this generator exists to avoid. A misspelt
            # street name is also the interesting half: it is what a fuzzy street
            # match has to survive.
            address_surface = _render_address(
                _Address(**{**vars(address),
                            "street": _keyboard_noise(address.street, rng)}),
                register, rng)
    parts: list[object] = [opener, "заказ", _Slot(order_surface, "neg_order")]
    if name_surface:
        parts.extend((cue, _Slot(name_surface, "req_name")))
    if address_surface:
        parts.append(_Slot(address_surface, "req_addr"))
    parts.append(ask)
    text, spans = _words(tuple(parts))
    if register == "clean":
        # The opener already carries the capital and a comma; the full stop goes
        # on the end, behind every span, so nothing moves.
        text = text + "."
    return text, spans


# --- corpus on disk --------------------------------------------------------

_PROFANITY: frozenset[str] = frozenset(
    "блять бля блядь пиздец пизда ебать ебал ебло хуй хуя хуё нахуй сука "
    "ебан ёбан пидор мудак хуев хуёв ебать".split())


def _load_rudevices() -> tuple[dict[str, int], dict[str, str]]:
    """Text → first line, and text → the blake2b-6 key the annotation uses."""
    if not _RUDEVICES.exists():
        raise BuildError(
            f"{_RUDEVICES} is missing. This family carries real RuDevices "
            f"utterances by value (CC BY 4.0) and pins each one by sha256, so it "
            f"cannot be built without the corpus. Fetch it into {_CACHE} first.")
    lines: dict[str, int] = {}
    keys: dict[str, str] = {}
    with _RUDEVICES.open(encoding="utf-8") as handle:
        for number, raw in enumerate(handle, 1):
            text = json.loads(raw)["text"]
            if text in lines:
                continue
            lines[text] = number
            keys[text] = hashlib.blake2b(text.encode("utf-8"),
                                         digest_size=6).hexdigest()
    return lines, keys


def _load_labels() -> list[dict[str, object]]:
    if not _RUDEVICES_LABELS.exists():
        raise BuildError(
            f"{_RUDEVICES_LABELS} is missing. The verbatim cases take their "
            f"ground truth from that hand annotation and from nothing else.")
    return json.loads(_RUDEVICES_LABELS.read_text(encoding="utf-8"))


def _load_shape_vocabulary() -> frozenset[str]:
    """Every pattern the mined grammars actually contain."""
    known: set[str] = set()
    dispatch = json.loads((_MINED / "dispatch_grammar.json").read_text("utf-8"))
    for group in dispatch["value_shapes"].values():
        known.update(entry["pattern"] for entry in group)
    known.update(entry["pattern"] for entry in dispatch["reply_shapes"])
    known.update(entry["pattern"] for entry in dispatch["name_forms"]["shapes"])
    calls = json.loads((_MINED / "calls_grammar.json").read_text("utf-8"))
    known.update(entry["pattern"] for entry in calls["shapes"])
    return frozenset(known)


def _filler_usable(text: str) -> bool:
    """A shape screen and a length screen, sharing no signal with the detector.

    It asks whether the line carries a digit, an «@» or a run of numeral words —
    never whether the detector would fire on it. The first voice set admitted a
    reply only when «улица» or «дом» was in it, which is what the engine reads,
    and it reported 100% where the truth was 38.6%.

    THE TOLERANCE THIS USED TO LEAVE, and why it is closed now. This screen had
    no name check at all, and the argument for that was correct as far as it
    went: `false_masks` counts DECLARED negatives and recall counts DECLARED
    gold, so an unclaimed «александр» in filler moves no number. It was closed
    anyway, for the reason the argument does not cover — an unclaimed real
    address in the same conversation as a claimed one is a second candidate for
    the conversation-scoped partial-mention rule, which `scope` measures
    directly, and a benchmark whose own filler can steer the mechanism it
    measures has a leak whether or not today's scorer reads it.

    `schema.unsafe_filler` is NOT a recognizer — that is what makes closing it
    legal here. It screens with the labels WE wrote (the vocabulary is a
    snapshot of the corpus's own gold spans), never with the cues the detector
    reads, so it cannot flatter the thing under test.
    """
    if not 18 <= len(text) <= 320:
        return False
    if "@" in text:
        return False
    if text[:1].isupper():
        return False
    return not (schema.unsafe_filler(text)
                or set(text.lower().split()) & _PROFANITY)


def _filler_pool(lines: dict[str, int], keys: dict[str, str],
                 labels: list[dict[str, object]]
                 ) -> tuple[tuple[tuple[str, str, int], ...],
                            tuple[tuple[str, str, int], ...]]:
    """Real utterances that carry nothing, split short and long.

    Nine replies in ten carry no personal data at all — the measured floor is
    1.995% of call replies and 0.939% of dispatch replies. A long case whose
    every line holds a datum is not this register, and it inflates recall and
    precision at the same time.

    Replies a human read and labelled «не адрес» come first; the rest of the
    corpus fills in behind them, screened by shape alone.
    """
    read_and_clear = {str(row["text"]) for row in labels
                      if row["label"] == "не адрес"}
    ordered: list[str] = [text for text in sorted(read_and_clear)
                          if text in lines and _filler_usable(text)]
    for text in sorted(lines):
        if len(ordered) >= 3000:
            break
        if text not in read_and_clear and _filler_usable(text):
            ordered.append(text)
    short = tuple((text, keys[text], lines[text]) for text in ordered
                  if len(text) < 90)
    long = tuple((text, keys[text], lines[text]) for text in ordered
                 if len(text) >= 90)
    if len(short) < 200 or len(long) < 200:
        raise BuildError(f"filler pool too thin: {len(short)} short, "
                         f"{len(long)} long")
    return short, long


def _verbatim_rows(labels: list[dict[str, object]], lines: dict[str, int],
                   keys: dict[str, str]) -> tuple[dict[str, object], ...]:
    """Hand-labelled address utterances, ready to be carried by value.

    This is the one place a `find` is honest: the annotation names a substring of
    an UNMODIFIED utterance, not of a string a register transform produced. What
    it cannot name is refused rather than resolved — a value occurring twice in
    its own reply is dropped, because the annotation does not say which
    occurrence it meant, and a reply whose unclaimed remainder still holds a run
    of four numeral words is dropped too, because in this register that is the
    shape of a dictated identifier and the label does not claim it.
    """
    rows: list[dict[str, object]] = []
    for row in labels:
        if row["label"] not in ("адрес с номером", "улица без номера"):
            continue
        text = str(row["text"])
        values = [str(value) for value in row.get("spans", ())]
        if not values or text not in lines:
            continue
        if any(character.isdigit() for character in text) or text[:1].isupper():
            continue
        if any(text.count(value) != 1 for value in values):
            continue
        located = sorted(((value, text.index(value),
                           text.index(value) + len(value)) for value in values),
                         key=lambda entry: entry[1])
        if any(located[i][2] > located[i + 1][1]
               for i in range(len(located) - 1)):
            continue
        remainder = list(text)
        for _, start, end in located:
            for position in range(start, end):
                remainder[position] = " "
        if schema.numeral_run("".join(remainder)) >= 4:
            continue
        rows.append({
            "text": text, "key": keys[text], "line": lines[text],
            "spans": tuple(located),
            "required": row["label"] == "адрес с номером",
            "selection": "census" if row["filter"] == "marker" else "random",
            "weight": 1.0 if row["filter"] == "marker" else _RANDOM_WEIGHT,
        })
    if len(rows) < 30:
        raise BuildError(f"only {len(rows)} usable verbatim rows; the plan needs "
                         f"30 distinct ones")
    rows.sort(key=lambda entry: str(entry["key"]))
    # INTERLEAVED BY STRATUM, and this is the whole reason `selection` is a field.
    # The marker layer is selected by the very words the detector reads and is
    # biased upward by construction; the number layer is a fixed-seed random
    # sample and is the only unbiased view there is. Sorted by key alone, the
    # first thirty rows happened to hold three of the unbiased ones. Every row of
    # the small stratum is taken and `weight` (19.22) does the arithmetic —
    # over-sampling a stratum and weighting it correctly is what stratified
    # sampling IS, and the alternative measures the easy layer nineteen times
    # over.
    sampled = [row for row in rows if row["selection"] == "random"]
    census = [row for row in rows if row["selection"] != "random"]
    ordered: list[dict[str, object]] = []
    while sampled or census:
        if sampled:
            ordered.append(sampled.pop(0))
        if census:
            ordered.append(census.pop(0))
    return tuple(ordered)


# --- message layout --------------------------------------------------------

def _source_of(text: str, key: str, line: int) -> schema.Source:
    return schema.Source(
        corpus="speech_rudevices", key=key, line=line,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        licence=_LICENCE_RU)


def _filler_messages(register: str, minimum_messages: int, minimum_chars: int,
                     rng: random.Random,
                     short: tuple[tuple[str, str, int], ...],
                     long: tuple[tuple[str, str, int], ...]
                     ) -> list[schema.Message]:
    """Customer/operator small talk that carries nothing, in user/assistant pairs.

    Real utterances for the voice registers, each with a `Source` so the line can
    be found and its digest checked; authored lines for the written ones, because
    a dispatcher's home speech pasted into a messenger is not a chat message and
    labelling it one would make the register a lie.
    """
    messages: list[schema.Message] = []
    characters = 0
    pool = long if minimum_chars else short
    while len(messages) < minimum_messages or characters < minimum_chars:
        if len(messages) >= 180:
            raise BuildError("filler ran to 180 messages without reaching the "
                             "character floor")
        if register in schema.SPEECH_REGISTERS:
            text, key, line = pool[rng.randrange(len(pool))]
            messages.append(schema.Message(role="user", content=text,
                                           source=_source_of(text, key, line),
                                           name=""))
        else:
            messages.append(schema.Message(
                role="user", content=rng.choice(_CHAT_FILLER), source=None,
                name=""))
        characters += len(messages[-1].content)
        reply = rng.choice(_ASSISTANT_VOICE
                           if register in schema.SPEECH_REGISTERS
                           else _ASSISTANT_CHAT)
        messages.append(schema.Message(role="assistant", content=reply,
                                       source=None, name=""))
        characters += len(reply)
    return messages


def _system_message(rng: random.Random) -> schema.Message:
    return schema.Message(role="system", source=None, name="", content=rng.choice((
        "Ты оператор службы доставки. Отвечай коротко. Данные клиента бери "
        "только из инструментов.",
        "Ты ассистент диспетчерской. Перед вызовом инструмента сверь адрес и "
        "телефон с карточкой.",
        "Ты помощник контактного центра. Не выдумывай данные, которых нет в "
        "карточке клиента.",
    )))


# --- the plan --------------------------------------------------------------
#
# Explicit, because every share in it is checked by `validate_corpus`, and a
# generator that computes its own mix drifts from the one that was agreed — v2
# described a register mix in its design document and shipped the opposite. Read
# as (sub-shape, provenance, register, context rung, count).
#
#   speech (voice_raw + voice_itn)  146 / 250 = 58.4%   floor 50%
#   clean                            10 / 250 =  4.0%   cap    5%
#   verbatim + recombined           226 / 250 = 90.4%   floor 70%

_PLAN: tuple[tuple[str, str, str, str, int], ...] = (
    ("flat", "verbatim", "voice_raw", "solo", 8),
    ("flat", "verbatim", "voice_raw", "short", 6),
    ("flat", "verbatim", "voice_raw", "long", 3),
    ("flat", "verbatim", "voice_raw", "deep", 1),
    ("flat", "recombined", "voice_raw", "solo", 5),
    ("flat", "recombined", "voice_raw", "short", 3),
    ("flat", "recombined", "voice_raw", "long", 2),
    ("flat", "recombined", "voice_itn", "solo", 4),
    ("flat", "recombined", "voice_itn", "short", 3),
    ("flat", "recombined", "voice_itn", "long", 1),
    ("flat", "recombined", "chat", "solo", 7),
    ("flat", "recombined", "chat", "short", 5),
    ("flat", "recombined", "chat", "long", 3),
    ("flat", "recombined", "chat", "deep", 1),
    ("flat", "recombined", "sloppy", "solo", 4),
    ("flat", "recombined", "sloppy", "short", 3),
    ("flat", "recombined", "sloppy", "deep", 1),
    ("flat", "recombined", "clean", "solo", 1),
    ("flat", "recombined", "clean", "short", 1),

    ("list", "verbatim", "voice_raw", "solo", 5),
    ("list", "verbatim", "voice_raw", "short", 4),
    ("list", "verbatim", "voice_raw", "long", 2),
    ("list", "verbatim", "voice_raw", "deep", 1),
    ("list", "recombined", "voice_raw", "solo", 3),
    ("list", "recombined", "voice_raw", "short", 3),
    ("list", "recombined", "voice_raw", "long", 2),
    ("list", "recombined", "voice_itn", "solo", 3),
    ("list", "recombined", "voice_itn", "short", 2),
    ("list", "recombined", "voice_itn", "long", 1),
    ("list", "recombined", "chat", "solo", 6),
    ("list", "recombined", "chat", "short", 4),
    ("list", "recombined", "chat", "long", 3),
    ("list", "recombined", "chat", "deep", 1),
    ("list", "recombined", "sloppy", "solo", 3),
    ("list", "recombined", "sloppy", "short", 2),
    ("list", "recombined", "sloppy", "long", 1),
    ("list", "recombined", "clean", "solo", 1),
    ("list", "recombined", "clean", "short", 1),

    ("latin_kv", "template", "voice_raw", "solo", 4),
    ("latin_kv", "template", "voice_raw", "short", 2),
    ("latin_kv", "template", "voice_itn", "solo", 3),
    ("latin_kv", "template", "voice_itn", "short", 1),
    ("latin_kv", "template", "chat", "solo", 6),
    ("latin_kv", "template", "chat", "short", 3),
    ("latin_kv", "template", "chat", "long", 1),
    ("latin_kv", "template", "sloppy", "solo", 2),
    ("latin_kv", "template", "sloppy", "short", 1),
    ("latin_kv", "template", "clean", "solo", 1),
    ("latin_kv", "recombined", "voice_raw", "solo", 2),
    ("latin_kv", "recombined", "voice_raw", "short", 2),
    ("latin_kv", "recombined", "voice_raw", "long", 1),
    ("latin_kv", "recombined", "voice_itn", "solo", 2),
    ("latin_kv", "recombined", "voice_itn", "short", 1),
    ("latin_kv", "recombined", "chat", "solo", 2),
    ("latin_kv", "recombined", "chat", "short", 2),
    ("latin_kv", "recombined", "chat", "deep", 1),
    ("latin_kv", "recombined", "sloppy", "solo", 1),
    ("latin_kv", "recombined", "sloppy", "short", 1),
    ("latin_kv", "recombined", "clean", "short", 1),

    ("iso_date", "recombined", "voice_raw", "solo", 4),
    ("iso_date", "recombined", "voice_raw", "short", 3),
    ("iso_date", "recombined", "voice_raw", "long", 2),
    ("iso_date", "recombined", "voice_raw", "deep", 1),
    ("iso_date", "recombined", "voice_itn", "solo", 2),
    ("iso_date", "recombined", "voice_itn", "short", 2),
    ("iso_date", "recombined", "voice_itn", "long", 1),
    ("iso_date", "recombined", "chat", "solo", 3),
    ("iso_date", "recombined", "chat", "short", 3),
    ("iso_date", "recombined", "chat", "long", 2),
    ("iso_date", "recombined", "sloppy", "solo", 2),
    ("iso_date", "recombined", "sloppy", "short", 1),
    ("iso_date", "recombined", "sloppy", "long", 1),
    ("iso_date", "recombined", "clean", "short", 1),

    ("comment", "recombined", "voice_raw", "solo", 5),
    ("comment", "recombined", "voice_raw", "short", 4),
    ("comment", "recombined", "voice_raw", "long", 3),
    ("comment", "recombined", "voice_raw", "deep", 1),
    ("comment", "recombined", "voice_itn", "solo", 2),
    ("comment", "recombined", "voice_itn", "short", 2),
    ("comment", "recombined", "voice_itn", "long", 1),
    ("comment", "recombined", "voice_itn", "deep", 1),
    ("comment", "recombined", "chat", "solo", 5),
    ("comment", "recombined", "chat", "short", 4),
    ("comment", "recombined", "chat", "long", 2),
    ("comment", "recombined", "chat", "deep", 1),
    ("comment", "recombined", "sloppy", "solo", 3),
    ("comment", "recombined", "sloppy", "short", 2),
    ("comment", "recombined", "sloppy", "long", 1),
    ("comment", "recombined", "clean", "solo", 1),
    ("comment", "recombined", "clean", "short", 1),
    ("comment", "recombined", "clean", "long", 1),

    ("spoken", "recombined", "voice_raw", "solo", 10),
    ("spoken", "recombined", "voice_raw", "short", 8),
    ("spoken", "recombined", "voice_raw", "long", 4),
    ("spoken", "recombined", "voice_raw", "deep", 2),
    ("spoken", "recombined", "voice_itn", "solo", 4),
    ("spoken", "recombined", "voice_itn", "short", 2),
    ("spoken", "recombined", "voice_itn", "long", 1),
    ("spoken", "recombined", "voice_itn", "deep", 1),
)

# Filler pairs per rung. `deep` gets none here: its count comes from the
# character floor, because thirty two-word replies are not a long context and the
# schema says so with MIN_DEEP_CHARS.
_FILLER_PAIRS: dict[str, tuple[int, int]] = {
    "solo": (0, 0), "short": (1, 2), "long": (4, 8), "deep": (14, 14),
}


# --- assembly --------------------------------------------------------------

def _scaled_plan(count: int) -> tuple[tuple[str, str, str, str, int], ...]:
    """The plan resized to `count`, by largest remainder, shares intact.

    The plan is authored at `TARGET` and every share in it is a decision, so
    resizing may not be left to a sampler: largest-remainder allocation keeps each
    row's proportion and the caps that `validate_corpus` enforces. A size that
    cannot hold every register, rung, provenance and sub-shape is REFUSED rather
    than quietly delivered — a rung that silently drops `clean` or `verbatim` is
    exactly the v2 ladder, which closed its dimensions at one rung out of five.
    """
    if count == TARGET:
        return _PLAN
    total = sum(row[4] for row in _PLAN)
    exact = [row[4] * count / total for row in _PLAN]
    sized = [int(value) for value in exact]
    order = sorted(range(len(_PLAN)),
                   key=lambda i: (exact[i] - sized[i], exact[i]), reverse=True)
    for position in range(count - sum(sized)):
        sized[order[position % len(order)]] += 1
    plan = tuple((row[0], row[1], row[2], row[3], size)
                 for row, size in zip(_PLAN, sized) if size)
    if sum(row[4] for row in plan) != count:
        raise BuildError(f"largest-remainder allocation produced "
                         f"{sum(row[4] for row in plan)}, not {count}")
    for position, name in ((0, "sub-shape"), (1, "provenance"), (2, "register"),
                           (3, "context rung")):
        missing = ({row[position] for row in _PLAN}
                   - {row[position] for row in plan})
        if missing:
            raise BuildError(
                f"{count} cases cannot carry every {name}: {sorted(missing)} "
                f"would be dropped, and a set that closes no dimension answers a "
                f"different question under the same name")
    speech = sum(row[4] for row in plan
                 if row[2] in schema.SPEECH_REGISTERS) / count
    clean = sum(row[4] for row in plan if row[2] == "clean") / count
    real = sum(row[4] for row in plan
               if row[1] in ("verbatim", "recombined")) / count
    if (speech < schema.MIN_SPEECH_SHARE or clean > schema.MAX_CLEAN_SHARE
            or real < schema.MIN_REAL_FORM_SHARE):
        raise BuildError(
            f"resizing to {count} breaks the agreed mix: speech {speech:.1%}, "
            f"clean {clean:.1%}, real form {real:.1%}")
    return plan


def build(seed: int, count: int) -> list[schema.Case]:
    """Every `result` case, validated, in a stable order.

    One RNG for the whole family, consumed in plan order, so a case's values are
    a function of the seed and of its position and of nothing else.
    `require_valid` runs on every case before it is returned: a corpus that ships
    an unscoreable case keeps printing numbers, and the numbers keep looking like
    numbers.
    """
    rng = random.Random(f"v3:{FAMILY}:{seed}")
    lines, keys = _load_rudevices()
    labels = _load_labels()
    known_shapes = _load_shape_vocabulary()
    for pattern in _SHAPES_NAME + _SHAPES_ADDR + _SHAPES_NUMBER:
        if pattern not in known_shapes:
            raise BuildError(
                f"shape {pattern!r} is not in mined/*.json — «the form came from "
                f"real speech» would be an assertion nobody can check")
    # The fill tables are what the generator actually draws from, so a pattern
    # present in one and absent from the declared lists would slip past the
    # mined-vocabulary check above and reach a case unverified.
    drifted = ((set(_NAME_SHAPE_PARTS) | {name for name, _ in _NAME_SHAPE_WEIGHTS})
               - set(_SHAPES_NAME)) | (set(_ADDR_SHAPE_FIELDS) - set(_SHAPES_ADDR))
    if drifted:
        raise BuildError(f"fill tables name shapes the declared lists do not: "
                         f"{sorted(drifted)}")
    short_filler, long_filler = _filler_pool(lines, keys, labels)
    verbatim_rows = _verbatim_rows(labels, lines, keys)

    cases: list[schema.Case] = []
    verbatim_used = 0
    for subshape, kind, register, context, size in _scaled_plan(count):
        for _ in range(size):
            index = len(cases)
            row = None
            if kind == "verbatim":
                row = verbatim_rows[verbatim_used % len(verbatim_rows)]
                verbatim_used += 1
            case = schema.require_valid(_one_case(
                index, subshape, kind, register, context, rng, short_filler,
                long_filler, row))
            if not _shape_holds(case):
                raise BuildError(
                    f"{case.id} declares shape {case.provenance.shape!r} and its "
                    f"text does not instantiate it; «the form came from real "
                    f"speech» would be a claim nobody can check")
            cases.append(case)
    if len(cases) != count:
        raise BuildError(f"the plan produced {len(cases)} cases, not {count}")
    return cases


_STRUCTURAL_WORDS: frozenset[str] = frozenset(
    ("улица", "проспект", "переулок", "шоссе", "проезд"))


def _shape_holds(case: schema.Case) -> bool:
    """Does the case's text actually instantiate the shape it claims?

    THE CHECK THAT MAKES `Provenance.shape` WORTH ANYTHING. Verifying that a
    pattern EXISTS in the mined grammar is not the same as verifying that the
    case FOLLOWS it, and the difference is exactly the state 1070 of v2's cases
    were in — a claim of speech provenance over text nobody compared to a form.
    Run over every case in `main`, and a failure is a build failure.
    """
    shape = case.provenance.shape
    by_id = {item.id: item for item in case.pii}
    if not shape:
        return case.provenance.kind in ("template", "verbatim")
    if shape in _NAME_SHAPE_PARTS:
        item = by_id.get("u_name")
        if item is None:
            return False
        cue, slots = _NAME_SHAPE_PARTS[shape]
        if len(item.value.split()) != len(slots):
            return False
        if not cue:
            return True
        return schema.message_text(case, item.msg)[:item.start].rstrip(
            ).endswith(cue)
    if shape in _ADDR_SHAPE_FIELDS:
        item = by_id.get("u_addr")
        if item is None:
            return False
        fields = _ADDR_SHAPE_FIELDS[shape]
        words = item.value.split()
        wanted_type = str(fields.get("street_type", ""))
        if wanted_type and wanted_type not in words:
            return False
        if not wanted_type and (set(words) & _STRUCTURAL_WORDS):
            return False
        if bool(fields.get("house_marker")) != ("дом" in words):
            return False
        if bool(fields.get("korpus")) != bool({"корпус", "к"} & set(words)):
            return False
        return bool(fields.get("entrance")) == ("подъезд" in words)
    if shape in _SHAPES_NUMBER:
        # A numeral-run shape claims the reply's value IS the run, so the turn
        # may not also be carrying a name or an address the shape does not name.
        return "u_name" not in by_id and "u_addr" not in by_id
    return False


def _one_case(index: int, subshape: str, kind: str, register: str, context: str,
              rng: random.Random, short_filler: tuple[tuple[str, str, int], ...],
              long_filler: tuple[tuple[str, str, int], ...],
              verbatim: dict[str, object] | None) -> schema.Case:
    """Messages first, then every span against the indices those messages got."""
    case_id = f"{FAMILY}-{index:03d}"
    named_person: _Person | None = None
    named_address: _Address | None = None
    if verbatim is not None:
        request_text = str(verbatim["text"])
        request_spans: dict[str, tuple[int, int]] = {}
        request_source: schema.Source | None = _source_of(
            request_text, str(verbatim["key"]), int(verbatim["line"]))
        shape = ""
        prov_corpus = "speech_rudevices"
        prov_key = str(verbatim["key"])
        selection = str(verbatim["selection"])
        weight = float(verbatim["weight"])
        prov_licence = _LICENCE_RU
    else:
        request_source = None
        draw = rng.random()
        if kind == "template":
            # A `template` case may carry only the types no speech corpus holds,
            # so its customer turn names nobody and nowhere: the order number is
            # all it has, and the schema refuses the alternative rather than let
            # a NAME through the one provenance that cannot justify one. Its
            # `shape` is cleared below — a template claims no mined form.
            shape = _SHAPES_NUMBER[0]
        elif draw < 0.44:
            named_person = _make_person(rng)
            shape = _pick_name_shape(rng)
        elif draw < 0.72 or register not in schema.SPEECH_REGISTERS:
            # A numeral-run shape describes an utterance somebody DICTATED. In a
            # messenger nobody dictated anything, so a written register draws a
            # name or an address and never claims a run it does not have.
            shape = rng.choice(_SHAPES_ADDR)
            named_address = _make_address(rng, shape)
        else:
            shape = _SHAPES_NUMBER[0] if rng.random() < 0.5 \
                else _SHAPES_NUMBER[1]
        request_text, request_spans = _compose_request(
            register, shape, named_person, named_address, _order_no(rng),
            _spoken_order(rng, shape), rng)
        if kind == "template":
            shape, prov_corpus, prov_key = "", "authored", ""
            selection, prov_licence, weight = "authored", "authored", 1.0
        else:
            prov_corpus, selection, prov_licence = _SHAPE_ORIGIN[shape]
            prov_key, weight = "", 1.0

    payload = _payload(subshape, case_id, rng, context == "deep",
                       kind == "template", named_person)

    prefix: list[schema.Message] = []
    if context != "solo":
        prefix.append(_system_message(rng))
    pairs_low, pairs_high = _FILLER_PAIRS[context]
    minimum_chars = 0
    if context == "deep":
        minimum_chars = max(
            0, schema.MIN_DEEP_CHARS + 200 - len(payload.text)
            - len(request_text) - sum(len(m.content) for m in prefix))
    if pairs_high or minimum_chars:
        prefix.extend(_filler_messages(
            register, 2 * rng.randrange(pairs_low, pairs_high + 1),
            minimum_chars, rng, short_filler, long_filler))
    request_index = len(prefix)
    # ПРОСЬБА О ДЕЙСТВИИ ЕДЕТ В ПЕРВОЙ ЖЕ РЕПЛИКЕ, а не отдельной. Смысл семьи в
    # том, что персональные данные приходят из РЕЗУЛЬТАТА инструмента и уходят
    # обратно вторым вызовом. Второго вызова агент не делал: в живом прогоне на
    # 800 диалогов доля несделанных здесь была 100% (189 из 189), и чтение
    # показало, что он честно вызывает первый инструмент — читает карточку, — а
    # дальше его никто ни о чём не просит.
    #
    # Отдельной репликой это добавить нельзя: короткий случай держит полосу
    # длины в 1-2 сообщения, и лишнее ломает `require_valid`. Клиент просит обе
    # вещи сразу — так и говорят по телефону.
    #
    # ЗНАЧЕНИЙ В ПРОСЬБЕ НЕТ: она ссылается на карточку, а не пересказывает её.
    # Назвать имя или адрес значило бы вернуть данные в реплику пользователя и
    # измерить не ту ногу. Приписка идёт В КОНЕЦ, поэтому смещения спанов,
    # посчитанные по `request_text`, не сдвигаются.
    action = next((_ACTION_REQUEST[call.name] for call in payload.calls
                   if call.name in _ACTION_REQUEST), "")
    if action:
        request_text = f"{request_text} и {action}"
    tool_index = request_index + 1
    messages = list(prefix)
    messages.append(schema.Message(role="user", content=request_text,
                                   source=request_source, name=""))
    messages.append(schema.Message(role="tool", content=payload.text,
                                   source=None, name=payload.tool))
    if context in ("long", "deep") and rng.random() < 0.45:
        # The tool result is not always the last thing said. A gateway that only
        # ever masks the tail of a transcript passes a corpus where it is.
        tail_text, tail_key, tail_line = (
            long_filler[rng.randrange(len(long_filler))]
            if register in schema.SPEECH_REGISTERS
            else (rng.choice(_CHAT_FILLER), "", 0))
        messages.append(schema.Message(
            role="assistant", content=rng.choice(
                _ASSISTANT_VOICE if register in schema.SPEECH_REGISTERS
                else _ASSISTANT_CHAT), source=None, name=""))
        messages.append(schema.Message(
            role="user", content=tail_text,
            source=(_source_of(tail_text, tail_key, tail_line)
                    if tail_key else None), name=""))

    # ПРОСЬБА О ДЕЙСТВИИ, БЕЗ КОТОРОЙ ЭТАЛОН НЕ МОТИВИРОВАН. Смысл семьи в том,
    # что персональные данные приходят из РЕЗУЛЬТАТА инструмента и уходят
    # обратно вторым вызовом. Второго вызова агент не делал: в живом прогоне на
    # 800 диалогов доля несделанных здесь была 100% (189 из 189), и чтение
    # показало, что он честно вызывает первый инструмент — читает карточку, — а
    # никто в разговоре не просит его сделать что-то дальше.
    #
    # ЗНАЧЕНИЙ В ПРОСЬБЕ НЕТ. Она говорит «сделай это с тем, что вернула
    # карточка», и ни одного имени, адреса или телефона не называет: назвать их
    # значило бы вернуть данные в реплику пользователя и измерить не ту ногу.
    pii: list[schema.PiiItem] = []
    negatives: list[schema.Negative] = []
    for tag, span in sorted(request_spans.items()):
        surface = request_text[span[0]:span[1]]
        if tag == "neg_order":
            negatives.append(schema.Negative(
                value=surface, start=span[0], end=span[1], msg=request_index,
                family="order_number", why=_WHY_ORDER))
        elif tag == "req_name":
            pii.append(schema.PiiItem(
                id="u_name", type="NAME", value=surface, canonical=surface,
                start=span[0], end=span[1], msg=request_index,
                identity=f"{case_id}:caller:NAME", duty="required",
                value_source="pool", spoken=False, tool_param=""))
        elif tag == "req_addr":
            pii.append(schema.PiiItem(
                id="u_addr", type="LOC", value=surface, canonical=surface,
                start=span[0], end=span[1], msg=request_index,
                identity=f"{case_id}:caller:LOC", duty="required",
                value_source="pool", spoken=register == "voice_raw",
                tool_param=""))
    if verbatim is not None:
        required = bool(verbatim["required"])
        for position, entry in enumerate(verbatim["spans"]):
            value, start, end = entry
            pii.append(schema.PiiItem(
                id=f"u_addr{position}", type="LOC", value=value,
                canonical=value, start=start, end=end, msg=request_index,
                identity=f"{case_id}:caller{position}:LOC",
                duty="required" if required else "optional",
                value_source="corpus", spoken=True, tool_param=""))

    for item in payload.items:
        pii.append(schema.PiiItem(
            id=item.id, type=item.type, value=item.value,
            canonical=item.canonical, start=item.span[0], end=item.span[1],
            msg=tool_index, identity=item.identity, duty=item.duty,
            value_source=item.value_source, spoken=item.spoken,
            tool_param=item.tool_param))
    for negative in payload.negatives:
        negatives.append(schema.Negative(
            value=negative.value, start=negative.span[0], end=negative.span[1],
            msg=tool_index, family=negative.family, why=negative.why))

    links = [schema.LinkExpectation(left=left, right=right, kind=link_kind,
                                    case="", why=why)
             for left, right, link_kind, why in payload.links]
    # The same human named twice, once by themselves and once by the CRM. If the
    # caller said all three parts, the two mentions ARE one value and the claim
    # is `same`. If they said fewer, the corpus refuses to decide: «Иванов Пётр»
    # and «Иванов Пётр Сергеевич» can be two customers, and demanding the merge
    # would score the gateway on a guess the conversation never settled.
    if named_person is not None:
        said = next((item for item in pii if item.id == "u_name"), None)
        stored = next((item for item in pii
                       if item.id == "t_name" and item.type == "NAME"), None)
        if (said is not None and stored is not None
                and stored.value.casefold() == _full_name(named_person).casefold()):
            identical = said.value.casefold() == stored.value.casefold()
            links.append(schema.LinkExpectation(
                left=said.id, right=stored.id,
                kind="same" if identical else "unjudged", case="",
                why=("клиент назвал себя целиком и карточка вернула то же самое: "
                     "одна личность — одна подмена"
                     if identical else
                     "клиент назвал часть имени, карточка вернула полное: "
                     "диалог не решает, тот же это человек или однофамилец")))
    calls = tuple(schema.ExpectedCall(
        name=call.name, arguments=call.arguments, judged_args=call.judged_args,
        pii_items=call.pii_items, after_msg=tool_index)
        for call in payload.calls)

    return schema.Case(
        id=case_id, family=FAMILY, register=register, context=context,
        provenance=schema.Provenance(
            kind=kind, corpus=prov_corpus, key=prov_key, shape=shape,
            selection=selection, weight=weight, licence=prov_licence),
        cluster=(f"{FAMILY}:v:{verbatim['key']}" if verbatim is not None
                 else f"{FAMILY}:{subshape}:{index:03d}"),
        conversation_id=f"conv-{FAMILY}-{index:03d}" if index % 2 == 0 else "",
        messages=tuple(messages), tools=payload.tools, pii=tuple(pii),
        negatives=tuple(negatives), links=tuple(links), calls=calls,
        final=payload.final, preceded_by="",
        annotators=1 if verbatim is not None else 0, adjudicated=False,
        note=payload.note)


# --- standalone check ------------------------------------------------------

def _snils_valid(value: str) -> bool:
    """Independent verifier, written from the published rule, not from `_snils`.

    A generator checked against itself proves nothing. These three exist because
    the engine gates on the arithmetic: an invalid number would be a miss the
    gateway was RIGHT to make, and the per-type column would quietly become
    noise instead of a measurement.
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 11:
        return False
    total = sum(int(digit) * (9 - index)
                for index, digit in enumerate(digits[:9]))
    if total < 100:
        expected = total
    elif total in (100, 101):
        expected = 0
    else:
        expected = 0 if total % 101 in (100, 101) else total % 101
    return expected == int(digits[9:])


def _inn_valid(value: str) -> bool:
    if len(value) != 12 or not value.isdigit():
        return False
    digits = [int(character) for character in value]
    weights_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    weights_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    return (sum(w * d for w, d in zip(weights_11, digits[:10])) % 11 % 10
            == digits[10]
            and sum(w * d for w, d in zip(weights_12, digits[:11])) % 11 % 10
            == digits[11])


def _luhn_valid(value: str) -> bool:
    digits = [int(ch) for ch in value if ch.isdigit()]
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return len(digits) == 16 and total % 10 == 0


def _self_check(cases: list[schema.Case]) -> None:
    """The claims `schema.validate` does not make, checked here or nowhere.

    There is no test runner in this repository, so a family module carries its
    own. Each check below is a way this generator has been wrong or could be:
    a checksum that does not hold, a shape claimed over text that does not
    instantiate it, an expected argument no message could have produced, a
    licensed utterance shipped with a digest that no longer finds it.
    """
    checkers = {"SNILS": _snils_valid, "INN": _inn_valid, "CARD": _luhn_valid}
    for case in cases:
        for item in case.pii:
            check = checkers.get(item.type)
            if check is not None and not check(item.value):
                raise BuildError(
                    f"{case.id}: {item.type} {item.value!r} fails its own "
                    f"checksum — the gateway would be right to miss it and the "
                    f"whole {item.type} column would be noise")
        if not _shape_holds(case):
            raise BuildError(f"{case.id}: text does not instantiate "
                             f"{case.provenance.shape!r}")
        by_id = {item.id: item for item in case.pii}
        for call in case.calls:
            for item_id in call.pii_items:
                item = by_id[item_id]
                argument = call.arguments[item.tool_param]
                if schema.classify_break(item, argument, argument, ()) != "ok":
                    raise BuildError(
                        f"{case.id}: the expected argument for {item_id} does "
                        f"not compare equal to itself under the schema's own "
                        f"rule, so the round trip could never pass")
        for message in case.messages:
            if message.source is None:
                continue
            digest = hashlib.sha256(message.content.encode("utf-8")).hexdigest()
            if digest != message.source.sha256:
                raise BuildError(f"{case.id}: a carried utterance and its digest "
                                 f"disagree")
            if (message.source.licence not in schema.SHIPPABLE_LICENCES
                    and message.content):
                raise BuildError(f"{case.id}: text under {message.source.licence} "
                                 f"must not be carried by value")
    print(f"self-check: checksums, shapes, round-trip arguments and source "
          f"digests hold over {len(cases)} cases")


def main() -> None:
    """Build, validate, and print what the family actually contains.

    There is no test runner in this repository; a family module answers for
    itself. Everything printed here is a claim `validate_corpus` or the scorer
    will make later, printed now so a drift is caught by the person who caused
    it.
    """
    cases = build(20260830, TARGET)
    print(f"{FAMILY}: {len(cases)} cases\n")

    def tally(label: str, values: list[str]) -> None:
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        line = "  ".join(f"{name} {count}"
                         for name, count in sorted(counts.items()))
        print(f"{label:<12} {line}")

    tally("register", [case.register for case in cases])
    tally("context", [case.context for case in cases])
    tally("provenance", [case.provenance.kind for case in cases])
    tally("selection", [case.provenance.selection for case in cases])
    tally("cluster", [case.cluster.split(":")[1] for case in cases])
    tally("axis", [axis for case in cases for axis in schema.judged_axes(case)])
    tally("negative", [negative.family for case in cases
                       for negative in case.negatives])
    tally("link", [link.kind for case in cases for link in case.links])

    speech = sum(1 for case in cases
                 if case.register in schema.SPEECH_REGISTERS) / len(cases)
    clean = sum(1 for case in cases if case.register == "clean") / len(cases)
    real = sum(1 for case in cases
               if case.provenance.kind in ("verbatim", "recombined")) / len(cases)
    print(f"\nspeech {speech:.1%} (floor {schema.MIN_SPEECH_SHARE:.0%})  "
          f"clean {clean:.1%} (cap {schema.MAX_CLEAN_SHARE:.0%})  "
          f"real form {real:.1%} (floor {schema.MIN_REAL_FORM_SHARE:.0%})")

    denominators = schema.type_denominators(cases)
    distinct = schema.distinct_values(cases)
    print("\ntype        required  distinct   (a repeat is not an observation)")
    for kind in schema.TYPES:
        count = denominators.get(kind, 0)
        mark = "" if count >= schema.MIN_TYPE_DENOMINATOR else "  < 5, prints as a count"
        print(f"  {kind:<9} {count:>8}  {distinct.get(kind, 0):>8}{mark}")

    # `optional` never enters recall and is printed in its own column: masking a
    # bare street is not an error and missing it is not a leak.
    tally("duty", [item.duty for case in cases for item in case.pii])
    spoken = sum(1 for case in cases for item in case.pii if item.spoken)
    print(f"\nspoken items {spoken}   negatives "
          f"{sum(len(case.negatives) for case in cases)}   "
          f"expected calls {sum(len(case.calls) for case in cases)}")

    # The claim the whole file rests on: nothing was written that the schema
    # cannot read back. `case_from_json` is stricter than `validate` about types.
    for case in cases:
        rebuilt = schema.case_from_json(json.loads(json.dumps(case.to_json())))
        if schema.corpus_digest([rebuilt]) != schema.corpus_digest([case]):
            raise BuildError(f"{case.id} does not survive its own json round trip")
    print("json round trip: every case rebuilt to the same digest")
    _self_check(cases)

    example = next(case for case in cases if case.cluster.split(":")[1] == "spoken")
    print(f"\n--- {example.id} ({example.register}, {example.context}) ---")
    for position, message in enumerate(example.messages):
        print(f"[{position}] {message.role}: {message.content[:220]}")
    for item in example.pii:
        print(f"    {item.type:<8} {item.value!r} -> {item.canonical!r} "
              f"param={item.tool_param or '-'}")


if __name__ == "__main__":
    main()
