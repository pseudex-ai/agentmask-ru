"""Form-only probes over dictated Russian speech.

The engine must never be consulted here. A corpus profiled with the detector can
only report what the detector already knows -- the same defect that made the
first voice set report 100% where the truth was 38.6%. Everything below is a
surface-form rule written from the register, not from `pseudex/`.

Two properties of the register drive every rule:
  * there are no digits at all -- a number is a RUN OF NUMERAL WORDS;
  * there is no punctuation, no capital, no Latin -- so casing, sentence ends
    and `@` are unavailable as signals and cannot be leaned on.
"""

import re

# --- numerals ---------------------------------------------------------------
# Written text spells a number with digits, so a literary corpus carries no
# numeral run at all and a whole defect class is structurally invisible in it.

_CARD = (
    r"нол[ья]|ноль|нуль|нул[яё]"
    r"|один|одна|одно|одну|одного|одному|одним|одном"
    r"|дв[ае]|двух|двум|двумя|двое|двоих"
    r"|три|тр[её]х|тр[её]м|тремя|трое|троих"
    r"|четыре|четыр[её]х|четыр[её]м|четырьмя|четверо"
    r"|пят[ьи]|пятью|пятеро"
    r"|шест[ьи]|шестью|шестеро"
    r"|сем[ьи]|семью|семеро"
    r"|восем[ьи]|восьм[иью]|восемью|восьмью"
    r"|девят[ьи]|девятью"
    r"|десят[ьи]|десятью"
    r"|[а-яё]*надцат[ьию]"
    r"|двадцат[ьи]|тридцат[ьи]"
    r"|сорок|сорока"
    r"|пятьдесят|пятидесяти|шестьдесят|шестидесяти"
    r"|семьдесят|семидесяти|восемьдесят|восьмидесяти"
    r"|девяност[оа]"
    r"|ст[оа]|сотн[яиюе]|сотен"
    r"|двести|двухсот|двумстам|двумястами"
    r"|триста|тр[её]хсот|четыреста|четыр[её]хсот"
    r"|пятьсот|пятисот|шестьсот|шестисот|семьсот|семисот"
    r"|восемьсот|восьмисот|девятьсот|девятисот"
    r"|тысяч[аиуей]?|тыщ[аиуей]?|миллион[а-яё]*|миллиард[а-яё]*"
)
_ORD_STEM = (
    r"перв|втор|трет|четв[её]рт|пят|шест|седьм|восьм|девят|десят"
    r"|[а-яё]*надцат|двадцат|тридцат|сороков|пятидесят|шестидесят"
    r"|семидесят|восьмидесят|девяност|сот|двухсот|тр[её]хсот|тысячн"
)
_ORD_END = r"ый|ой|ий|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ья|ье|ьего|ьей|ьи"

CARDINAL = re.compile(r"^(?:%s)$" % _CARD)
ORDINAL = re.compile(r"^(?:%s)(?:%s)$" % (_ORD_STEM, _ORD_END))
# "пол" / "полтора" ride along with a number but are not one on their own.
NUMERAL_GLUE = frozenset(("полтора", "полторы", "пол", "дробь", "с", "и"))


def is_numeral(token):
    return bool(CARDINAL.match(token) or ORDINAL.match(token))


def numeral_runs(tokens):
    """Maximal runs of adjacent numeral words. Glue words never open a run."""
    runs, start = [], None
    for i, tok in enumerate(tokens):
        if is_numeral(tok):
            if start is None:
                start = i
        elif start is not None and tok in NUMERAL_GLUE and i + 1 < len(tokens) and is_numeral(tokens[i + 1]):
            continue  # "сто и двадцать" stays one dictated number
        else:
            if start is not None:
                runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(tokens)))
    return runs


def longest_run(tokens):
    runs = numeral_runs(tokens)
    return max((b - a for a, b in runs), default=0)


# --- names ------------------------------------------------------------------
# The gazetteer below is written here, by hand, for this measurement. It is NOT
# `licensing/`'s 197k list: reusing the leased dictionary would make the count
# a measure of the dictionary rather than of the corpus.

_GIVEN = """
александр алексей анатолий андрей антон аркадий арсений артем артём артур борис
вадим валентин валерий василий виктор виталий владимир владислав вячеслав
геннадий георгий глеб григорий даниил данила денис дмитрий евгений егор иван
игорь илья кирилл константин леонид максим марк матвей михаил никита николай
олег павел петр пётр роман руслан семен семён сергей станислав степан тимофей
тимур федор фёдор эдуард юрий ярослав вова саша дима леша лёша женя коля миша
серега серёга толя витя гриша паша ваня костя слава юра стас макс сеня
александра алена алёна алина алла анастасия ангелина анжела анна антонина
валентина валерия вероника виктория галина дарья диана дина екатерина елена
елизавета жанна зинаида зоя инна ирина карина кристина ксения лариса лидия
людмила маргарита марина мария наталья наталия нина оксана ольга полина раиса
регина светлана софия софья тамара татьяна ульяна юлия яна настя катя лена таня
оля маша даша ира надя люда галя вика ксюша аня юля зина нюра
""".split()

# Homonyms with ordinary Russian words. Kept out on purpose -- counting "вера",
# "надежда", "слава", "света" as people would inflate the name share with prose.
# "женя" is here for the same reason it is called out in CLAUDE.md: its stem
# swallows «жена», «жену», «женой» -- three of the commonest words in the corpus.
_GIVEN_HOMONYM = frozenset(
    "вера надежда любовь света слава роза лев майя рома дина воля люда женя".split()
)
GIVEN = frozenset(n for n in _GIVEN if n not in _GIVEN_HOMONYM)
GIVEN_STEMS = frozenset(n[:-1] if n[-1] in "аяьйе" else n for n in GIVEN)

_NAME_ENDINGS = ("", "а", "я", "у", "ю", "ы", "и", "е", "ой", "ей", "ом", "ем", "ём", "ку", "ке", "ки")


def is_given_name(token):
    if token in CORPUS_COMMON:
        return False
    if token in GIVEN:
        return True
    if len(token) < 4:
        return False
    for end in _NAME_ENDINGS:
        if end and token.endswith(end) and token[: -len(end)] in GIVEN_STEMS:
            return True
    return False


# "-евне"/"-овне" is the dative of a patronymic AND the tail of "деревне".
# Length is what separates them: a real one is at least eight letters.
PATRONYMIC = re.compile(r"^[а-яё]{4,}(ович|овича|овичу|овичем|евич|евича|евичу|евичем"
                        r"|ьевич|ьевича|овна|овну|овны|евна|евну|евны"
                        r"|инична|иничны|иничну|итична)$"
                        r"|^[а-яё]{5,}(овне|евне)$")
# Bare "ко"/"ук"/"юк" were here and had to go: they turn "только", "сколько",
# "лук" and "звук" into surnames, and this shape is only ever a supporting
# signal -- one that fires on function words supports everything.
SURNAME_SHAPE = re.compile(r"^[а-яё]{4,}(ов|ев|[её]в|ин|ын|ова|ева|[её]ва|ина|ына"
                           r"|ову|еву|ину|овы|евы|ский|ская|цкий|цкая|ских|ского|ской"
                           r"|енко|енка|швили|дзе)$")
# Ordinary words that fall into SURNAME_SHAPE. Only ever used to reject.
# The bulk of the rejection is done by CORPUS_COMMON (see set_common): the 400
# commonest tokens of a 417k-token corpus are function words by construction,
# and no surname reaches that rank.
_SURNAME_STOP = frozenset("""
один одна одни магазин машин машина мужчин женщин причин бензин район
сын сынок карантин балкон вагон телефон камин пингвин апельсин витамин
картина корзина витрина скотин животин долин глубин величин
""".split())

CORPUS_COMMON = frozenset()


def set_common(tokens):
    """Disqualify the corpus's own commonest words from every name shape."""
    global CORPUS_COMMON
    CORPUS_COMMON = frozenset(tokens)

NAME_CUE = re.compile(r"\b(меня зовут|как вас зовут|вас зовут|его зовут|е[её] зовут"
                      r"|моя фамилия|фамилия имя|имя отчество|по фамилии|на имя"
                      r"|фамилию|отчество|представьтесь)\b")


def _is_surname_shape(token):
    return bool(SURNAME_SHAPE.match(token)) and token not in _SURNAME_STOP \
        and token not in CORPUS_COMMON and not is_numeral(token)


def name_probe(text, tokens):
    """Returns (strong, loose, evidence). Strong = a shape only a person has."""
    ev = []
    patr = [t for t in tokens if PATRONYMIC.match(t)]
    given = [t for t in tokens if is_given_name(t)]
    surn = [t for t in tokens if _is_surname_shape(t)]
    cue = bool(NAME_CUE.search(text))
    if patr:
        ev.append("patronymic:" + patr[0])
    # a given name standing next to a surname-shaped word is a full name
    pair = False
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if (is_given_name(a) and (_is_surname_shape(b) or PATRONYMIC.match(b))) or \
           (is_given_name(b) and _is_surname_shape(a)):
            pair = True
            ev.append("pair:%s %s" % (a, b))
            break
    named_after_cue = False
    m = NAME_CUE.search(text)
    if m:
        tail = text[m.end():].split()[:3]
        if any(is_given_name(t) or _is_surname_shape(t) for t in tail):
            named_after_cue = True
            ev.append("cue:" + " ".join(tail))
    strong = bool(patr) or pair or named_after_cue
    loose = strong or bool(given)
    if given and not ev:
        ev.append("given:" + given[0])
    return strong, loose, cue, ev


# --- address ----------------------------------------------------------------

STREET_TYPE = re.compile(r"^(улиц[аыуе]|улица|проспект[а-яё]*|переул[а-яё]+|шоссе"
                         r"|бульвар[а-яё]*|набережн[а-яё]+|проезд[а-яё]*|тупик[а-яё]*"
                         r"|аллея|аллее|квартал[а-яё]*|микрорайон[а-яё]*|мкр|мкрн"
                         r"|площад[ьи]|переулок|линия|линии)$")
HOUSE_MARK = re.compile(r"^(дом|дома|доме|дому|домик|квартир[аыуе]|кв|подъезд[а-яё]*"
                        r"|эта[жк][а-яё]*|корпус[а-яё]*|строен[а-яё]+|литер|владени[ея])$")
ADDR_CUE = re.compile(r"\b(адрес|адресу|адреса|по адресу|куда подать|куда ехать"
                      r"|откуда забрать|подай(те)?|подъезжай(те)?)\b")


def address_probe(tokens, text):
    ev = []
    for i, tok in enumerate(tokens):
        if STREET_TYPE.match(tok):
            nxt = tokens[i + 1: i + 4]
            prv = tokens[max(0, i - 2): i]
            # a street type is only an address when something names or numbers it
            if any(is_numeral(t) for t in nxt) or any(is_numeral(t) for t in prv):
                ev.append("street+num:" + " ".join(tokens[max(0, i - 2): i + 4]))
                break
            if nxt and not is_numeral(nxt[0]) and len(nxt[0]) > 3:
                ev.append("street+name:" + " ".join(tokens[i: i + 3]))
                break
        if HOUSE_MARK.match(tok):
            nxt = tokens[i + 1: i + 3]
            prv = tokens[max(0, i - 2): i]
            if any(is_numeral(t) for t in nxt) or any(is_numeral(t) for t in prv):
                ev.append("house:" + " ".join(tokens[max(0, i - 2): i + 3]))
                break
    if not ev and ADDR_CUE.search(text) and any(is_numeral(t) for t in tokens):
        ev.append("cue+num")
    return bool(ev), ev


# --- phone ------------------------------------------------------------------

PHONE_CUE = re.compile(r"\b(телефон[а-яё]*|номер[а-яё]*|позвон[а-яё]+|перезвон[а-яё]+"
                       r"|набер[а-яё]+|звони[а-яё]*|трубк[а-яё]+|сотов[а-яё]+|мобильн[а-яё]+)\b")


_COUNTING = ("раз два три", "один два три", "два три четыре", "три четыре пять")


def _is_counting(text):
    """A recited 1-2-3 is the commonest long numeral run in speech and is not
    a number anyone dictated -- vetoed by shape, never by a cue word."""
    return any(seq in text for seq in _COUNTING)


def phone_probe(tokens, text):
    run = longest_run(tokens)
    if _is_counting(text):
        return False, ""
    if run >= 7:
        return True, "run>=7:%d" % run
    if run >= 4 and PHONE_CUE.search(text):
        return True, "cue+run:%d" % run
    return False, ""


# --- email ------------------------------------------------------------------

EMAIL_SEP = re.compile(r"\bсобак[аиу]\b|\bэт\b|\bат\b")
EMAIL_DOMAIN = re.compile(r"\b(гмейл|джимейл|джимэйл|мейл|майл|м[еэ]йл ру|яндекс"
                          r"|рамблер|точка ру|точка ком|точка рф|дот ком)\b")
EMAIL_CUE = re.compile(r"\b(почт[аыуе]|электронн[а-яё]+ почт[а-яё]+|имейл|емейл|е-мейл|мыло)\b")


def email_probe(text):
    sep = bool(EMAIL_SEP.search(text))
    dom = bool(EMAIL_DOMAIN.search(text))
    cue = bool(EMAIL_CUE.search(text))
    if sep and (dom or cue):
        return True, "sep+domain"
    if dom and cue:
        return True, "domain+cue"
    return False, ""


# --- date of birth ----------------------------------------------------------

MONTH = re.compile(r"\b(январ[а-яё]*|феврал[а-яё]*|март[а-яё]*|апрел[а-яё]*|ма[йея]"
                   r"|июн[а-яё]*|июл[а-яё]*|август[а-яё]*|сентябр[а-яё]*|октябр[а-яё]*"
                   r"|ноябр[а-яё]*|декабр[а-яё]*)\b")
BIRTH_CUE = re.compile(r"\b(родил[а-яё]*|рождени[яе]|рождения|дата рождения|день рождения"
                       r"|года рождения|г р|в каком году роди[а-яё]*)\b")


def dob_probe(tokens, text):
    if not BIRTH_CUE.search(text):
        return False, ""
    if any(is_numeral(t) for t in tokens) or MONTH.search(text):
        return True, "birth_cue+num"
    return False, ""


# --- document / financial identifiers --------------------------------------

# "снилс" is a prefix of "снился" -- the lookahead is the whole difference
# between one mention of the document and every dream in the corpus.
SNILS_CUE = re.compile(r"\bснилс(?![яе])\w*|\bпенсионн[а-яё]+ (свидетельств|удостоверени)")
INN_CUE = re.compile(r"\bинн\b|\bи н н\b|\bидентификационн[а-яё]+ номер")
CARD_CUE = re.compile(r"\bкарт[аыуое][а-яё]*\b|\bкарточк[а-яё]+\b|\bвиз[аыу]\b"
                      r"|\bмастеркард\b|\bсбербанк[а-яё]*\b|\bсчет[а-яё]*\b|\bсч[её]т[а-яё]*\b")
CARD_STRICT = re.compile(r"\b(номер карт[а-яё]+|карт[аыу] сбербанк[а-яё]*|на карт[уые]"
                         r"|с карт[ыи]|карточк[а-яё]+ номер)\b")
PASSPORT_CUE = re.compile(r"\bпаспорт[а-яё]*\b|\bпасспорт[а-яё]*\b")
PLATE_CUE = re.compile(r"\bгосномер[а-яё]*\b|\bгос номер[а-яё]*\b|\bномер[а-яё]* машин[а-яё]+"
                       r"|\bномер[а-яё]* авто[а-яё]*|\bрегион[а-яё]*\b")
# a dictated plate spells its letters out one by one
# "а", "о", "у", "ка" and "ха" are ordinary words of the language before they
# are spelled plate letters; counting them made every "а ... а" a number plate.
PLATE_LETTER = frozenset("бэ вэ эм эн эр рэ эс тэ икс игрек".split())


def plate_probe(tokens, text):
    letters = sum(1 for t in tokens if t in PLATE_LETTER)
    if PLATE_CUE.search(text) and (letters >= 2 or longest_run(tokens) >= 3):
        return True, "cue+shape"
    if letters >= 3 and longest_run(tokens) >= 2:
        return True, "spelled_plate"
    return False, ""
