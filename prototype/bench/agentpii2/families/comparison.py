"""The `compare` family — two mentions of one protected value, and a question
that can only be answered if the gateway made them ONE substitute.

THE CASE THE OWNER ASKS ABOUT. The customer says «г. Москва, улица Ленина, д. 14,
кв. 7» in the first turn and «доставка по адресу ленина 14 — это тот же адрес?»
in the last. Two vault keys, two fake addresses, and the model — seeing «Пушкина 18» and
«Садовая 3» — compares them honestly and answers «нет». Nothing in the pipeline
threw an error, nothing leaked, no token failed to resolve: the round trip is
clean and the answer is confidently wrong. Every other axis this benchmark has
scores that dialogue as a pass.

WHY THIS IS A FAMILY AND NOT A SCENARIO. `_linked_place` and `_linked_token` are
an existing mechanism with a single-candidate rule, and until now only unit tests
touched them. They are also the mechanism whose SAFETY is the conversation scope:
at tenant scale «Ленина 14» has a dozen owners and the rule refuses every time, so
the same change that makes linking mean something is the change that makes it
safe. A number for it has to come from somewhere that is not our own unit test.

FOUR VEHICLES, NOT THE DOC'S TWO. `docs/tz-agentpii2.md` §3.3 splits this family
into «то же место» and «тот же человек». The place half is kept whole (50 cases);
the person half is split three ways, because the three carry a person's identity
through three DIFFERENT mechanisms and they fail apart:

  * `name`   morphology. «Заберёт Игорь» against «Соколов Игорь Валентинович» —
             a partial that is one token of a three-token mention.
  * `phone`  the vault's own canonicalisation: «+7 916…» and «8 916…» collapse to
             one key by documented design, so a broken link here is a broken
             canonicaliser and not a broken scope.
  * `order`  the anchor is a NON-personal number that must survive in the clear
             in both turns, while the person beside it is written in the
             accusative once and the nominative once.

Averaging those three into «тот же человек» is the mistake `bench/voice` already
paid for once, when 71% turned out to be 94% on one legal class and 47% on the
other. The doc's 50/50 split between place and person is preserved exactly, so
its arithmetic still reads: 5 registers x (10 place + 4 name + 3 phone + 3 order).

THREE ARMS, AND THE THIRD ONE IS THE HONEST NEGATIVE.

  same        the partial MUST reach the model as the earlier value's substitute.
              `expected_answer = "да"`.
  different   two values of one type in one conversation MUST NOT merge, and the
              last turn tells the agent to act on one of them by name. A merge
              here is `other_person`: the tool executes, returns 200, and the
              courier goes to somebody else's flat. `expected_answer = "нет"`.
  ambiguous   two addresses on the SAME street (home and delivery) plus a
              street-only mention. The single-candidate rule refuses, correctly,
              and so the street-only mention's link is `unjudged` — a written
              requirement, not a gap. The question is asked about the two FULL
              addresses, which are both stated in the clear, so a gateway that
              refuses to link is not punished for being right.

SCORED TWICE, AND STRICT IS THE HEADLINE. `classify_answer` below is part of the
contract for the same reason `same_value` is in the schema: a scorer that invents
its own parser invents its own number.

  STRICT   the parsed answer equals `expected_answer`. Nothing else passes.
  LENIENT  a refusal («не могу подтвердить», «уточните») also passes.

Both are printed. The lenient one is not a softer strict: a gateway that breaks
linking so badly that the model stops answering is meaningfully better than one
that makes it answer wrongly, and only the gap between the two numbers says which
failure the product has. What never passes either is a confident wrong answer,
which is the whole point.

WHAT THIS FAMILY DELIBERATELY DOES NOT MINT. No СНИЛС, ИНН or card. They carry
their own checksums, and a value held by a checksum measures the checksum rather
than the link — `detect_structured` finds it whatever the register does to the
surrounding prose. The numeric vehicle here is the phone, generated on real
Russian mobile prefixes so libphonenumber accepts it as dialable.

REGISTER LIVES IN THE TEMPLATE AND IN THE SLOT VALUES, never in a pass over the
finished string. An earlier corpus stripped punctuation after assembly, which
changes length and silently moves every span computed before it; the ground truth
then points a few characters to the left and the benchmark keeps printing numbers.
Offsets here are counted by `_assemble` as the message is built.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii2.schema import (  # noqa: E402
    REGISTERS, Case, ExpectedCall, LinkExpectation, Negative, PiiItem,
    message_text,
)

# --- the shop's own prompt, one string for every case ----------------------
#
# Identical everywhere ON PURPOSE. Half the cases carry no `conversation_id`, so
# the engine derives one from the first TWO messages — and the first of those two
# is this prompt, shared by every dialogue an agent has. If the second message
# were not distinctive the derived key would collide and one customer's address
# would resolve inside another's conversation. `build` asserts that it is.
_SYSTEM = "Оператор поддержки магазина. Отвечай кратко и вызывай инструменты."


# --- people ---------------------------------------------------------------
#
# Accusative is written out, never derived. Russian surnames and given names have
# irregulars and indeclinables in the same pool («Нгуен Ань» declines in neither
# half, «Ким» declines only for a man), and a rule that gets one wrong puts a form
# nobody writes into the GROUND TRUTH, where it is scored as if it were real
# Russian. A table is checkable by a native speaker in ten seconds.
#
# FOREIGN NAMES ARE NOT AN ADVERSARIAL GARNISH. Measured on NEREL, nearly every
# name our detector misses is foreign, and a Russian shop with foreign customers
# is Tuesday. Six of the fifteen entries below carry no -ов/-ев/-ин suffix, and
# they are drawn from the same pool as everyone else in every arm and register.
_PEOPLE: tuple[tuple[str, str, str, str], ...] = (
    # (surname, given, patronymic, accusative of «Фамилия Имя»)
    ("Соколов", "Игорь", "Валентинович", "Соколова Игоря"),
    ("Кузнецов", "Дмитрий", "Андреевич", "Кузнецова Дмитрия"),
    ("Морозов", "Алексей", "Николаевич", "Морозова Алексея"),
    ("Фёдоров", "Кирилл", "Романович", "Фёдорова Кирилла"),
    ("Иванов", "Пётр", "Сергеевич", "Иванова Петра"),
    ("Соколова", "Ирина", "Петровна", "Соколову Ирину"),
    ("Лебедева", "Ольга", "Дмитриевна", "Лебедеву Ольгу"),
    ("Новикова", "Светлана", "Юрьевна", "Новикову Светлану"),
    ("Морозова", "Екатерина", "Сергеевна", "Морозову Екатерину"),
    ("Ким", "Виктор", "", "Кима Виктора"),
    ("Мкртчян", "Ашот", "", "Мкртчяна Ашота"),
    ("Нгуен", "Ань", "", "Нгуен Ань"),
    ("Мамедова", "Лейла", "", "Мамедову Лейлу"),
    ("Джонсон", "Майкл", "", "Джонсона Майкла"),
    ("Валиахметов", "Ильдар", "", "Валиахметова Ильдара"),
)

# (full form as a document writes it, the bare name a chat writes without a
# marker, the form that follows «на»). The bare form is what the partial mention
# is built from, and it is the form a marker-less street pattern has to survive.
#
# THE THIRD FIELD IS WRITTEN OUT, NOT DERIVED, for the same reason the accusative
# of a name is. Half these names are genitives that do not move («на Ленина», «на
# Чехова») and half are adjectives that do («на Садовой», «на Ленинском»); a rule
# that flattens the difference puts «на Садовая» into the corpus, and a benchmark
# written in Russian nobody writes measures the model's tolerance for it.
_STREETS: tuple[tuple[str, str, str], ...] = (
    ("улица Ленина", "Ленина", "Ленина"),
    ("улица Пушкина", "Пушкина", "Пушкина"),
    ("проспект Мира", "Мира", "Мира"),
    ("улица Гагарина", "Гагарина", "Гагарина"),
    ("Ленинский проспект", "Ленинский", "Ленинском"),
    ("улица Строителей", "Строителей", "Строителей"),
    ("Садовая улица", "Садовая", "Садовой"),
    ("улица Чехова", "Чехова", "Чехова"),
    ("улица Кирова", "Кирова", "Кирова"),
    ("Молодёжная улица", "Молодёжная", "Молодёжной"),
    ("улица Лермонтова", "Лермонтова", "Лермонтова"),
    ("Центральная улица", "Центральная", "Центральной"),
)

_CITIES: tuple[str, ...] = (
    "Москва", "Казань", "Екатеринбург", "Новосибирск", "Краснодар", "Самара",
    "Пермь", "Воронеж",
)

# Real Russian mobile prefixes. A phone that libphonenumber rejects would be
# caught by the regex arm alone, which is a different recognizer with different
# behaviour, and the corpus would be measuring the fallback.
_MOBILE_PREFIXES: tuple[str, ...] = (
    "903", "905", "906", "909", "910", "916", "917", "919", "925", "926",
    "927", "929", "999",
)

_ORDER_PREFIXES: tuple[str, ...] = ("", "A-", "№", "ORD-")


# --- numbers in words -----------------------------------------------------
#
# `voice_raw` is verbatim ASR and it carries NO digits: measured on OpenSTT
# `asr_calls_2_val`, 12 950 human transcripts of real Russian phone calls, zero
# contain one. So every number in that register — house, flat, phone, order —
# is spelled, and the schema's register gate refuses the case otherwise.

_ONES = ("ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь",
         "восемь", "девять")
_TEENS = ("десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
          "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать",
          "девятнадцать")
_TENS = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
         "семьдесят", "восемьдесят", "девяносто")
_HUNDREDS = ("", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
             "семьсот", "восемьсот", "девятьсот")


def _words(number: int) -> str:
    """0-999 in the citation (masculine nominative) form.

    Masculine throughout because that is what the numbers here agree with in
    speech — «дом четырнадцать», «квартира семь» are read as bare numerals, not
    declined to the noun.
    """
    if not 0 <= number <= 999:
        raise ValueError(f"{number} is outside the 0-999 this speller covers")
    parts: list[str] = []
    hundreds, rest = divmod(number, 100)
    if hundreds:
        parts.append(_HUNDREDS[hundreds])
    if 10 <= rest <= 19:
        parts.append(_TEENS[rest - 10])
    else:
        tens, ones = divmod(rest, 10)
        if tens:
            parts.append(_TENS[tens])
        if ones or not parts:
            parts.append(_ONES[ones])
    return " ".join(parts)


def _group_words(group: str) -> str:
    """One spoken group of a phone number, leading zeros read as «ноль».

    «03» is «ноль три» — the doc's own example — and «014» is «ноль
    четырнадцать». Reading the whole group as an integer would drop the zero and
    produce a number the speaker did not say.
    """
    zeros = len(group) - len(group.lstrip("0"))
    if zeros == len(group):
        return " ".join(_ONES[0] for _ in group)
    return " ".join(["ноль"] * zeros + [_words(int(group[zeros:]))])


def _digits_words(digits: str) -> str:
    """Digit by digit — how a person re-reads a number they already gave once."""
    return " ".join(_ONES[int(digit)] for digit in digits)


# --- the sloppy register --------------------------------------------------
#
# Drawn from RuSpellGold (RussianNLP, Apache 2.0, 1711 human-corrected pairs)
# rather than invented. Over 2112 real corrections: 950 single-letter
# substitutions (499 of them ё->е), 626 dropped letters, 463 stray characters.
# The commonest error is not a typo at all — «ё» written as «е» is ordinary
# Russian practice and it lands directly on Фёдоров, Пётр, Молодёжная.
#
# A keyboard-layout slip (a Latin twin inside a Cyrillic word) is kept because it
# defeats a Cyrillic-only matcher, but as the minority it is: RuSpellGold is
# edited text, where a layout slip is corrected before publication.
_PHONETIC: tuple[tuple[str, str], ...] = (
    ("ё", "е"), ("ё", "е"), ("ё", "е"),
    ("а", "о"), ("и", "е"), ("о", "а"), ("е", "и"),
    ("о", "у"), ("и", "ы"), ("я", "и"), ("т", "д"), ("з", "с"),
)
_LATIN_TWINS: dict[str, str] = {
    "о": "o", "а": "a", "е": "e", "с": "c", "р": "p", "у": "y", "х": "x",
    "О": "O", "А": "A", "Е": "E", "С": "C", "Р": "P",
}


def _typo(text: str, rng: random.Random) -> str:
    """One realistic writing error, applied to a VALUE before assembly.

    Never to the finished message: a message-level pass changes the string after
    its spans were counted. Never to a digit either — the sloppy phone gets its
    own slip, and a dropped digit would make the ground truth claim a number the
    customer does not have.
    """
    roll = rng.random()
    if roll < 0.45:
        for source, target in rng.sample(_PHONETIC, len(_PHONETIC)):
            positions = [i for i, ch in enumerate(text) if ch.lower() == source]
            if not positions:
                continue
            index = rng.choice(positions)
            replacement = target.upper() if text[index].isupper() else target
            return text[:index] + replacement + text[index + 1:]
        return text
    if roll < 0.75:
        # Never the first character: a dropped initial stops being a typo and
        # becomes a different word, which is a different measurement.
        positions = [i for i, ch in enumerate(text) if ch.isalpha() and i > 0]
        if not positions:
            return text
        index = rng.choice(positions)
        return text[:index] + text[index + 1:]
    if roll < 0.90:
        positions = [i for i, ch in enumerate(text) if ch == " "]
        if positions:
            index = rng.choice(positions)
            return text[:index] + text[index + 1:]
        return text
    positions = [i for i, ch in enumerate(text) if ch in _LATIN_TWINS]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + _LATIN_TWINS[text[index]] + text[index + 1:]


# --- rendering one datum in one register ----------------------------------
#
# THE CANONICAL IS THE FORM THE VAULT WOULD RETURN FOR WHAT WAS WRITTEN, and the
# two halves of that sentence pull in opposite directions on purpose:
#
#   * a NAME is canonicalised to the nominative, because the product claims to do
#     that and a declined name written into a customer's CRM is the defect the
#     claim exists to prevent. The typo is NOT repaired — demanding a spell-check
#     would score the gateway on something it must never do.
#   * a PHONE written in digits becomes «+7…», because canonicalisation across
#     «8…»/«+7…» is documented behaviour and `same_value` compares by digits
#     anyway. A phone spelled in WORDS has no canonicalisation, so it comes back
#     as the words: a gateway that masks and restores it faithfully must pass.
#   * an ADDRESS is returned as written. The city is present in exactly the
#     registers that wrote it, and never demanded from the three that drop it —
#     that bug cost v1 162 of 183 sloppy failures.


def _person_full(person: tuple[str, str, str, str], register: str,
                 rng: random.Random) -> tuple[str, str]:
    """The full mention. Returns (surface, canonical)."""
    surname, given, patronymic, _ = person
    if register == "clean":
        written = " ".join(part for part in (surname, given, patronymic) if part)
        return written, written
    canonical = f"{surname} {given}"
    if register == "sloppy":
        # THE TYPO IS NOT REPAIRED. The vault stores what was detected and hands
        # it back; demanding «Лебедева Ольга» from a turn that wrote
        # «ЛебедеваОльга» would score the gateway on a spell-check it must never
        # perform, and a correct round trip would then count as a break.
        written = _typo(canonical, rng)
        return written, written
    return canonical.lower(), canonical


def _person_accusative(person: tuple[str, str, str, str], register: str,
                       rng: random.Random) -> tuple[str, str]:
    """«оформлен на Соколову Ирину» — the case the round trip has to undo."""
    surname, given, _, accusative = person
    canonical = f"{surname} {given}"
    if register in ("clean", "sloppy"):
        # The sloppy register's error budget lands on the CUE WORDS here
        # («офрмлен», «получтель»), never on the name. The nominative of a typo'd
        # accusative is not derivable from a table, and deriving it by rule would
        # put a form nobody writes into the ground truth — where it is scored as
        # if it were real Russian. A clean accusative still measures the one
        # thing this vehicle exists for, which is the declension.
        return accusative, canonical
    return accusative.lower(), canonical


def _person_given(person: tuple[str, str, str, str], register: str,
                  rng: random.Random) -> tuple[str, str]:
    """A bare given name — «Заберёт Игорь». One token of a three-token identity."""
    given = person[1]
    if register == "clean":
        return given, given
    if register == "sloppy":
        written = _typo(given, rng)
        return written, written
    return given.lower(), given


def _address_full(city: str, street: tuple[str, str, str], house: int, flat: int,
                  register: str, rng: random.Random) -> str:
    full = street[0]
    if register == "clean":
        return f"г. {city}, {full}, д. {house}, кв. {flat}"
    if register == "chat":
        # The city is DROPPED, and only `clean` keeps it: in a shop's own chat
        # everybody knows which city, so ground truth that demands it back scores
        # the gateway on a word the message never carried.
        return f"{full.lower()} {house} кв {flat}"
    if register == "sloppy":
        return _typo(f"{full} {house}кв{flat}", rng)
    if register == "voice_itn":
        return f"{full.lower()} дом {house} квартира {flat}"
    return f"{full.lower()} дом {_words(house)} квартира {_words(flat)}"


def _address_partial(street: tuple[str, str, str], house: int, register: str,
                     rng: random.Random) -> str:
    """Street and house, no city and no flat — the mention that has to link."""
    bare = street[1]
    if register == "clean":
        return f"{bare}, {house}"
    if register == "chat":
        return f"{bare.lower()} {house}"
    if register == "sloppy":
        return _typo(f"{bare.lower()} {house}", rng)
    if register == "voice_itn":
        return f"{bare.lower()} {house}"
    return f"{bare.lower()} {_words(house)}"


def _street_only(street: tuple[str, str, str], register: str) -> tuple[str, str]:
    """A street with no house number. Identifies nobody — `duty = optional`.

    152-ФЗ ст. 3 п. 1 speaks of a determined or determinable person, and hundreds
    of buildings stand on улица Пушкина. Scored in the same column as an address
    with a house number, those two averaged 71% while the real figures were 94%
    and 47%.
    """
    _, bare, locative = street
    # The SURFACE is inflected and the canonical is not: «на Садовой» is what a
    # person says and «Садовая» is what a CRM would hold. The item is optional
    # and consumed by no tool, so nothing round-trips it — but a corpus that
    # wrote the citation form after a preposition would be teaching a register
    # that does not exist.
    if register == "clean":
        return locative, bare
    return locative.lower(), bare


def _phone_digits(rng: random.Random) -> str:
    return rng.choice(_MOBILE_PREFIXES) + "".join(
        str(rng.randrange(10)) for _ in range(7))


def _phone_first(digits: str, register: str) -> tuple[str, str]:
    head, mid, third, tail = digits[:3], digits[3:6], digits[6:8], digits[8:]
    if register == "clean":
        return f"+7 {head} {mid}-{third}-{tail}", f"+7{digits}"
    if register == "chat":
        return f"8{digits}", f"+7{digits}"
    if register == "sloppy":
        # A Cyrillic letter typed where a digit belongs is the commonest
        # obfuscation that is not an obfuscation — it is a keyboard slip, and
        # `normalize` folds it back inside a digit-dense run, so the number stays
        # dialable. Three digits have a Cyrillic twin and the first one PRESENT is
        # used: keying only on «0» left every number without a zero rendered
        # exactly as `clean` renders it, which deleted the register from a third
        # of the phone cases without deleting the cases.
        written = f"8-{head}-{mid}-{third}-{tail}"
        for digit, twin in (("0", "О"), ("3", "З"), ("4", "ч")):
            if digit in written:
                return written.replace(digit, twin, 1), f"+7{digits}"
        return written, f"+7{digits}"
    if register == "voice_itn":
        return f"8 {head} {mid} {third} {tail}", f"+7{digits}"
    spoken = " ".join(("восемь", _group_words(head), _group_words(mid),
                       _group_words(third), _group_words(tail)))
    return spoken, spoken


def _phone_second(digits: str, register: str) -> tuple[str, str]:
    """The SAME subscriber written the way the second turn writes them.

    A different grouping every time, because that is the claim under test: the
    vault collapses «+7 999…», «8 999…» and «89991234567» to one key, so one
    subscriber gets one substitute and the model can answer «да».
    """
    head, mid, third, tail = digits[:3], digits[3:6], digits[6:8], digits[8:]
    if register == "clean":
        return f"8 ({head}) {mid}-{third}-{tail}", f"+7{digits}"
    if register == "chat":
        return f"+7{digits}", f"+7{digits}"
    if register == "sloppy":
        return f"8 {head} {mid}{third}{tail}", f"+7{digits}"
    if register == "voice_itn":
        return f"8{head} {mid} {third}{tail}", f"+7{digits}"
    spoken = " ".join(("восемь", _digits_words(digits)))
    return spoken, spoken


def _order_id(rng: random.Random, register: str) -> str:
    digits = "".join(str(rng.randrange(10)) for _ in range(4))
    if register == "voice_raw":
        return _digits_words(digits)
    return rng.choice(_ORDER_PREFIXES) + digits


# --- register frames ------------------------------------------------------
#
# The prose around the values, per channel. `sloppy` carries its misspellings
# HERE rather than getting them from a pass over the finished string, and they
# land on cue words on purpose: «пасспорт» and «догвор» once disabled the guards
# those words provide, so a corpus that only ever spells its cues correctly
# cannot see that class of failure at all.
_FRAME: dict[str, dict[str, str]] = {
    "clean": {
        "open": "Здравствуйте! Заказ ",
        "slot": ", {label}: ",
        "slot2": ", {label}: ",
        "end": ".",
        "ack": "Принял, проверяю по заказу.",
        "ref": "Уточните: ",
        "q": " — это тот же {noun}?",
        "q2": " — это один и тот же {noun}?",
        "on": " оформлен на ",
        "on2": ", а заказ ",
        "on3": " на ",
    },
    "chat": {
        "open": "здравствуйте заказ ",
        "slot": " {label} ",
        "slot2": " и {label} ",
        "end": "",
        "ack": "секунду смотрю",
        "ref": "",
        "q": " это тот же {noun}?",
        "q2": " это один и тот же {noun}?",
        "on": " оформлен на ",
        "on2": " а заказ ",
        "on3": " на ",
    },
    "sloppy": {
        "open": "Здраствуйте, заказ ",
        "slot": ", {label}: ",
        "slot2": ", {label}: ",
        "end": "",
        "ack": "Принял, смотрю.",
        "ref": "",
        "q": " - это тот же {noun}?",
        "q2": " - это один и тот же {noun}?",
        "on": " офрмлен на ",
        "on2": ", а закз ",
        "on3": " на ",
    },
    "voice_itn": {
        "open": "алло у меня заказ ",
        "slot": " {label} ",
        "slot2": " и {label} ",
        "end": "",
        "ack": "да секунду смотрю",
        "ref": "",
        "q": " это тот же {noun}",
        "q2": " это один и тот же {noun}",
        "on": " оформлен на ",
        "on2": " а заказ ",
        "on3": " на ",
    },
    "voice_raw": {
        "open": "алло у меня заказ ",
        "slot": " {label} ",
        "slot2": " и {label} ",
        "end": "",
        "ack": "да секунду смотрю",
        "ref": "",
        "q": " это тот же {noun}",
        "q2": " это один и тот же {noun}",
        "on": " оформлен на ",
        "on2": " а заказ ",
        "on3": " на ",
    },
}

# The noun the question asks about. One word, so the question shape is identical
# across vehicles and a per-register phrasing table stays small enough to read.
_NOUN: dict[str, str] = {
    "place": "адрес", "name": "человек", "phone": "номер", "order": "человек",
}

# (label for the first value, label for the second). The place pair is «домашний
# адрес» / «адрес доставки» because that is the real dialogue: the customer gives
# where they live and then asks whether the courier is going there.
_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "clean": {
        "place": ("домашний адрес", "адрес доставки"),
        "name": ("плательщик", "получатель"),
        "phone": ("телефон", "второй телефон"),
        "order": ("получатель", "получатель"),
    },
    "chat": {
        "place": ("домашний адрес", "адрес доставки"),
        "name": ("плательщик", "получатель"),
        "phone": ("тел", "второй тел"),
        "order": ("получатель", "получатель"),
    },
    "sloppy": {
        "place": ("домашний адресс", "адресс доставки"),
        "name": ("плателщик", "полчатель"),
        "phone": ("тлф", "второй тлф"),
        "order": ("получтель", "получтель"),
    },
    "voice_itn": {
        "place": ("домашний адрес", "адрес доставки"),
        "name": ("плательщик", "получатель"),
        "phone": ("телефон", "второй телефон"),
        "order": ("получатель", "получатель"),
    },
    "voice_raw": {
        "place": ("домашний адрес", "адрес доставки"),
        "name": ("плательщик", "получатель"),
        "phone": ("телефон", "второй телефон"),
        "order": ("получатель", "получатель"),
    },
}

# What introduces the SECOND mention in the closing turn.
_REF: dict[str, dict[str, str]] = {
    "clean": {"place": "доставка по адресу ", "name": "заберёт ",
              "phone": "в заказе записан ", "order": "по заказу "},
    "chat": {"place": "доставка по адресу ", "name": "заберёт ",
             "phone": "в заказе записан ", "order": "по заказу "},
    "sloppy": {"place": "доствка по адрессу ", "name": "заберёт ",
               "phone": "в заказе записан ", "order": "по заказу "},
    "voice_itn": {"place": "а доставка по адресу ", "name": "а заберёт ",
                  "phone": "а в заказе записан ", "order": "а по заказу "},
    "voice_raw": {"place": "а доставка по адресу ", "name": "а заберёт ",
                  "phone": "а в заказе записан ", "order": "а по заказу "},
}

# The instruction that makes the agent CALL something. Without it a correct model
# answers the question and stops, and the round-trip axis has nothing to score —
# which would leave the family measuring the answer alone.
_DO: dict[str, dict[str, str]] = {
    "clean": {
        "place": " Подтвердите адрес в заказе.",
        "name": " Найдите заказ по получателю.",
        "phone": " Проверьте по нему статус заказа.",
        "order": " Найдите заказ по получателю.",
    },
    "chat": {
        "place": " подтвердите адрес в заказе",
        "name": " найдите заказ по получателю",
        "phone": " проверьте статус по нему",
        "order": " найдите заказ по получателю",
    },
    "sloppy": {
        "place": " Потвердите адрес в заказе.",
        "name": " Найдите закз по получателю.",
        "phone": " Проверте статус по нему.",
        "order": " Найдите заказ по получтелю.",
    },
    "voice_itn": {
        "place": " подтвердите адрес в заказе",
        "name": " найдите заказ по получателю",
        "phone": " проверьте статус по нему",
        "order": " найдите заказ по получателю",
    },
    "voice_raw": {
        "place": " подтвердите адрес в заказе",
        "name": " найдите заказ по получателю",
        "phone": " проверьте статус по нему",
        "order": " найдите заказ по получателю",
    },
}

# How the closing turn names WHICH of the two values to act on, in the
# `different` arm. For place and phone it is a position («второй»), which is not
# a mention; for a person it is the name again, which is a third mention of the
# same identity and therefore a second chance for the gateway to merge them.
# «Найдите заказ на » takes the accusative, which is why the third mention is
# rendered by `_person_accusative` and not by `_person_full`: «найдите заказ на
# Соколов Игорь» is not Russian, and a corpus that writes prose no Russian writes
# measures the model's tolerance for it rather than the gateway.
_PICK: dict[str, dict[str, str]] = {
    "clean": {"place": " Везите на второй.", "phone": " Звоните на второй.",
              "name": " Найдите заказ на ", "order": " Найдите заказ на "},
    "chat": {"place": " везите на второй", "phone": " звоните на второй",
             "name": " найдите заказ на ", "order": " найдите заказ на "},
    "sloppy": {"place": " Везите на второй.", "phone": " Звоните на второй.",
               "name": " Найдите закз на ", "order": " Найдите закз на "},
    "voice_itn": {"place": " везите на второй", "phone": " звоните на второй",
                  "name": " найдите заказ на ", "order": " найдите заказ на "},
    "voice_raw": {"place": " везите на второй", "phone": " звоните на второй",
                  "name": " найдите заказ на ", "order": " найдите заказ на "},
}

# The closing question of the `ambiguous` arm, and it is spelled out per register
# rather than reusing `q2`. The arm carries THREE address mentions and the
# question is about two of them; «курьер поедет на Гагарина — это один и тот же
# адрес?» reads as a question about the bare street, which is exactly the mention
# the arm declares unjudged.
# The separator is part of these strings rather than reused from the frame: a
# channel that ends a sentence with nothing runs the bare street straight into
# the question, and «на садовой домашний и адрес доставки» is a different
# sentence from the one this arm means to ask.
_AMBIG_Q: dict[str, str] = {
    "clean": ". Домашний адрес и адрес доставки — это один и тот же адрес?",
    "chat": ", домашний и адрес доставки это один и тот же адрес?",
    "sloppy": ". Домашний и адресс доставки - это один и тот же адрес?",
    "voice_itn": " домашний и адрес доставки это один и тот же адрес",
    "voice_raw": " домашний и адрес доставки это один и тот же адрес",
}

# One identity per side, per vehicle. Two mentions sharing an identity must reach
# the model as ONE substitute and two identities must never collide; the strings
# are case-local, so the pair below is the whole vocabulary a case needs.
_IDENTITY: dict[str, tuple[str, str]] = {
    "place": ("place_a", "place_b"),
    "phone": ("phone_a", "phone_b"),
    "name": ("person_a", "person_b"),
    "order": ("person_a", "person_b"),
}


# --- tools ----------------------------------------------------------------
#
# Plain OpenAI function-calling JSON so the corpus replays against any provider
# with no translation layer, and a competing gateway can be scored on it without
# adopting anything of ours. All four are offered in every case: a single-tool
# prompt lets a model succeed by having nowhere else to go, which hides whether
# an implausible substitute changed which tool it CHOSE.


def _tool(name: str, description: str,
          params: dict[str, tuple[str, str]],
          required: list[str]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    key: {"type": kind, "description": text}
                    for key, (kind, text) in params.items()
                },
                "required": required,
            },
        },
    }


_TOOLS: list[dict[str, object]] = [
    _tool("update_delivery_address",
          "Изменить адрес доставки у существующего заказа.",
          {"order_id": ("string", "Номер заказа"),
           "address": ("string", "Адрес доставки с домом и квартирой")},
          ["order_id", "address"]),
    _tool("lookup_order",
          "Найти заказ по его номеру и ФИО получателя.",
          {"order_id": ("string", "Номер заказа"),
           "customer_name": ("string", "ФИО получателя")},
          ["order_id", "customer_name"]),
    _tool("check_order_status",
          "Узнать статус заказа по номеру телефона покупателя.",
          {"order_id": ("string", "Номер заказа"),
           "phone": ("string", "Телефон, указанный при оформлении")},
          ["order_id", "phone"]),
    _tool("add_contact",
          "Добавить контакт клиента в CRM.",
          {"name": ("string", "ФИО контакта"),
           "phone": ("string", "Телефон"),
           "email": ("string", "Электронная почта")},
          ["name", "phone"]),
]


# --- assembly -------------------------------------------------------------

def _assemble(parts: list[object]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Build a message and the offsets of its tracked slots in ONE pass.

    A plain `str` is literal text; a `(name, value)` tuple is a slot whose span is
    recorded. Searching the finished string instead would find the FIRST
    occurrence, and a turn that names the same street twice would then carry a
    span pointing at the wrong one — silently, and it would still score.
    """
    out: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for part in parts:
        if isinstance(part, tuple):
            name, value = part
            if name in spans:
                raise ValueError(f"slot {name!r} assembled twice; one slot is "
                                 f"one span and the second would be lost")
            spans[name] = (cursor, cursor + len(value))
            out.append(value)
            cursor += len(value)
        else:
            text = str(part)
            out.append(text)
            cursor += len(text)
    return "".join(out), spans


def _item(item_id: str, kind: str, text: str, span: tuple[int, int],
          canonical: str, msg: int, identity: str, duty: str,
          tool_param: str | None) -> PiiItem:
    """One ground-truth item, its value SLICED from the assembled text.

    Never retyped: a value written out a second time is a second string that has
    to stay equal to the first, and the register transforms are exactly the place
    where it stops being.
    """
    start, end = span
    return PiiItem(id=item_id, type=kind, value=text[start:end], start=start,
                   end=end, canonical=canonical, msg=msg, identity=identity,
                   duty=duty, tool_param=tool_param)


def _messages(first: str, ack: str, last: str) -> list[dict[str, object]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": first},
        {"role": "assistant", "content": ack},
        {"role": "user", "content": last},
    ]


# --- the three arms -------------------------------------------------------
#
# Every case is four messages: the shop's prompt, the turn that states the value,
# one acknowledgement, and the turn that names it again and asks. The
# acknowledgement is not filler — without a turn between them the two mentions
# sit in one message and the conversation scope is never asked to hold anything.


def _build_same(rng: random.Random, register: str, subject: str,
                index: int) -> Case:
    """The headline: a partial mention that MUST resolve against a fuller one."""
    frame = _FRAME[register]
    order = _order_id(rng, register)
    label_a = _LABELS[register][subject][0]
    identity = _IDENTITY[subject][0]

    if subject == "place":
        city = rng.choice(_CITIES)
        street = rng.choice(_STREETS)
        house, flat = rng.randrange(1, 90), rng.randrange(1, 200)
        first_value = _address_full(city, street, house, flat, register, rng)
        second_value = _address_partial(street, house, register, rng)
        kind, param = "LOC", "address"
        # The address canonical is the surface, exactly. The city lives only in
        # the register that wrote it, and the flat only where the register kept
        # it; demanding either back from a turn that dropped it scores the
        # gateway on information the message never carried.
        first_canonical, second_canonical = first_value, second_value
        tool_name = "update_delivery_address"
    elif subject == "phone":
        digits = _phone_digits(rng)
        first_value, first_canonical = _phone_first(digits, register)
        second_value, second_canonical = _phone_second(digits, register)
        kind, param = "PHONE", "phone"
        tool_name = "check_order_status"
    elif subject == "name":
        person = rng.choice(_PEOPLE)
        first_value, first_canonical = _person_full(person, register, rng)
        second_value, second_canonical = _person_given(person, register, rng)
        kind, param = "NAME", "customer_name"
        tool_name = "lookup_order"
    else:
        person = rng.choice(_PEOPLE)
        first_value, first_canonical = _person_accusative(person, register, rng)
        second_value, second_canonical = _person_full(person, register, rng)
        kind, param = "NAME", "customer_name"
        tool_name = "lookup_order"

    if subject == "order":
        # The anchor is the ORDER NUMBER and it must survive in the clear in both
        # turns. A gateway that masks it has broken the only handle the customer
        # has on their own order, which is as bad as leaking one.
        first, spans_first = _assemble(
            [frame["open"], order, frame["on"], ("value", first_value),
             frame["end"]])
        last, spans_last = _assemble(
            [frame["ref"], _REF[register][subject], order, " ",
             ("value", second_value), frame["q"].format(noun=_NOUN[subject]),
             _DO[register][subject]])
        negatives = [Negative(order, "номер заказа", 1),
                     Negative(order, "номер заказа", 3)]
    else:
        first, spans_first = _assemble(
            [frame["open"], order, frame["slot"].format(label=label_a),
             ("value", first_value), frame["end"]])
        last, spans_last = _assemble(
            [frame["ref"], _REF[register][subject], ("value", second_value),
             frame["q"].format(noun=_NOUN[subject]), _DO[register][subject]])
        negatives = [Negative(order, "номер заказа", 1)]

    messages = _messages(first, frame["ack"], last)
    items = [
        _item("first", kind, first, spans_first["value"], first_canonical,
              1, identity, "required", param),
        # ONLY the fuller mention claims the tool parameter. Two items claiming
        # one argument would state two demands on one value, and the scorer
        # cannot resolve which of them the tool was supposed to receive.
        _item("second", kind, last, spans_last["value"], second_canonical,
              3, identity, "required", None),
    ]
    arguments: dict[str, str | int | float] = {"order_id": order,
                                               param: first_canonical}
    return Case(
        id=f"cmp{index:04d}-same-{subject}-{register}",
        family="compare",
        scenario=f"same_{subject}",
        register=register,
        difficulty="hard",
        length_rung="short",
        conversation_id=_conversation_id(index),
        relation="equality",
        messages=messages,
        tools=_TOOLS,
        pii=items,
        preceded_by="",
        annotators=0,
        adjudicated=False,
        negatives=negatives,
        links=[LinkExpectation(
            left="first", right="second", kind="same", case="",
            why=("одно значение, названное дважды в одном разговоре: без общей "
                 "подмены модель сравнивает два разных фальшивых значения и "
                 "уверенно отвечает не то"))],
        calls=[ExpectedCall(name=tool_name, after_msg=3, arguments=arguments,
                            pii_items=["first"])],
        expected_answer="да",
    )


def _build_different(rng: random.Random, register: str, subject: str,
                     index: int) -> Case:
    """Two values of one type in one conversation that MUST NOT merge.

    The closing turn names one of them for the tool, so a wrong merge is not an
    opinion the model expressed — it is the courier at the wrong door, or the
    call placed to somebody else. That is `other_person`, the worst outcome the
    product has, and v1 had no name for it.
    """
    frame = _FRAME[register]
    order = _order_id(rng, register)
    label_a, label_b = _LABELS[register][subject]
    negatives = [Negative(order, "номер заказа", 1)]
    pick_third: str | None = None
    pick_canonical = ""

    if subject == "place":
        city = rng.choice(_CITIES)
        street_a, street_b = rng.sample(_STREETS, 2)
        house_a, house_b = rng.randrange(1, 90), rng.randrange(1, 90)
        flat_a, flat_b = rng.randrange(1, 200), rng.randrange(1, 200)
        value_a = _address_full(city, street_a, house_a, flat_a, register, rng)
        value_b = _address_full(city, street_b, house_b, flat_b, register, rng)
        canonical_a, canonical_b = value_a, value_b
        kind, param = "LOC", "address"
        tool_name = "update_delivery_address"
    elif subject == "phone":
        digits_a, digits_b = _phone_digits(rng), _phone_digits(rng)
        value_a, canonical_a = _phone_first(digits_a, register)
        value_b, canonical_b = _phone_first(digits_b, register)
        kind, param = "PHONE", "phone"
        tool_name = "check_order_status"
    elif subject == "name":
        person_a, person_b = rng.sample(_PEOPLE, 2)
        value_a, canonical_a = _person_full(person_a, register, rng)
        value_b, canonical_b = _person_full(person_b, register, rng)
        pick_third, pick_canonical = _person_accusative(person_b, register, rng)
        kind, param = "NAME", "customer_name"
        tool_name = "lookup_order"
    else:
        person_a, person_b = rng.sample(_PEOPLE, 2)
        value_a, canonical_a = _person_accusative(person_a, register, rng)
        value_b, canonical_b = _person_accusative(person_b, register, rng)
        pick_third, pick_canonical = _person_accusative(person_b, register, rng)
        kind, param = "NAME", "customer_name"
        tool_name = "lookup_order"

    if subject == "order":
        # Two orders, two people, one surname family away from each other. The
        # order numbers are the anchors and both must stay in the clear.
        order_b = _order_id(rng, register)
        first, spans_first = _assemble(
            [frame["open"], order, frame["on"], ("a", value_a), frame["on2"],
             order_b, frame["on3"], ("b", value_b), frame["end"]])
        negatives = [Negative(order, "номер заказа", 1),
                     Negative(order_b, "номер второго заказа", 1)]
        call_order = order_b
    else:
        first, spans_first = _assemble(
            [frame["open"], order, frame["slot"].format(label=label_a),
             ("a", value_a), frame["slot2"].format(label=label_b),
             ("b", value_b), frame["end"]])
        call_order = order

    identity_a, identity_b = _IDENTITY[subject]
    parts_last: list[object] = [
        frame["ref"], frame["q2"].format(noun=_NOUN[subject]).lstrip(" —-"),
        _PICK[register][subject]]
    if pick_third is not None:
        parts_last.append(("c", pick_third))
    last, spans_last = _assemble(parts_last)

    items = [
        _item("first", kind, first, spans_first["a"], canonical_a, 1,
              identity_a, "required", None),
        # Only the value the closing turn PICKS claims the tool parameter. The
        # other one is present, detected and never consumed, which is what makes
        # a merge visible: the tool then receives a real value belonging to the
        # person the conversation was not about.
        _item("second", kind, first, spans_first["b"], canonical_b, 1,
              identity_b, "required", param),
    ]
    if pick_third is not None:
        # A THIRD mention of the same person, in the turn that names whom to act
        # on. Same identity as `second`, so it is a second chance to merge the
        # two people — and this time the merge reaches the tool.
        items.append(_item("third", kind, last, spans_last["c"], pick_canonical,
                           3, identity_b, "required", None))

    return Case(
        id=f"cmp{index:04d}-different-{subject}-{register}",
        family="compare",
        scenario=f"different_{subject}",
        register=register,
        difficulty="hard",
        length_rung="short",
        conversation_id=_conversation_id(index),
        relation="equality",
        messages=_messages(first, frame["ack"], last),
        tools=_TOOLS,
        pii=items,
        preceded_by="",
        annotators=0,
        adjudicated=False,
        negatives=negatives,
        links=[LinkExpectation(
            left="first", right="second", kind="different", case="",
            why=("два разных значения в одном разговоре: слияние отправит "
                 "инструмент на настоящее значение постороннего человека, и "
                 "вызов вернёт 200"))],
        calls=[ExpectedCall(name=tool_name, after_msg=3,
                            arguments={"order_id": call_order,
                                       param: canonical_b},
                            pii_items=["second"])],
        expected_answer="нет",
    )


def _build_ambiguous(rng: random.Random, register: str, subject: str,
                     index: int) -> Case:
    """Two addresses on ONE street, plus a street-only mention.

    The single-candidate rule refuses to link the bare street, and it is RIGHT to
    refuse — «Ленина» names both of them. So that mention's link is `unjudged`,
    which is a written requirement and not a gap: v1 could express «these are one
    person» and could not express «we are not judging this», so a real merge could
    hide in the same silence as a deliberate abstention.

    The question is asked about the two FULL addresses, both stated in the clear
    in the same turn. A gateway that refuses to link the bare street must not be
    punished for being right, and it is only not punished if the answer does not
    depend on the refusal.
    """
    del subject  # place only: the bare-street mention has no analogue elsewhere
    frame = _FRAME[register]
    order = _order_id(rng, register)
    city = rng.choice(_CITIES)
    street = rng.choice(_STREETS)
    house_a, house_b = rng.sample(range(1, 90), 2)
    flat_a, flat_b = rng.randrange(1, 200), rng.randrange(1, 200)
    label_a, label_b = _LABELS[register]["place"]

    value_a = _address_full(city, street, house_a, flat_a, register, rng)
    value_b = _address_full(city, street, house_b, flat_b, register, rng)
    bare, bare_canonical = _street_only(street, register)

    first, spans_first = _assemble(
        [frame["open"], order, frame["slot"].format(label=label_a),
         ("a", value_a), frame["slot2"].format(label=label_b), ("b", value_b),
         frame["end"]])
    last, spans_last = _assemble(
        [frame["ref"], "курьер поедет на ", ("c", bare), _AMBIG_Q[register]])

    # NEITHER full address claims a tool parameter, and the arm expects no call.
    # A tool argument would have to name one of the two, which is a question this
    # arm deliberately does not ask: what it measures is whether the two stay
    # apart and whether the bare street is left alone, not what gets executed.
    items = [
        _item("first", "LOC", first, spans_first["a"], value_a, 1,
              "place_a", "required", None),
        _item("second", "LOC", first, spans_first["b"], value_b, 1,
              "place_b", "required", None),
        # `duty = optional`: a street with no house number identifies nobody, so
        # masking it is not an error and missing it is not a leak. `identity` is
        # empty for the same reason the link is unjudged — claiming an identity
        # would state, through the back door, which of the two it belongs to.
        _item("third", "LOC", last, spans_last["c"], bare_canonical, 3,
              "", "optional", None),
    ]
    return Case(
        id=f"cmp{index:04d}-ambiguous-place-{register}",
        family="compare",
        scenario="ambiguous_place",
        register=register,
        difficulty="hard",
        length_rung="short",
        conversation_id=_conversation_id(index),
        relation="equality",
        messages=_messages(first, frame["ack"], last),
        tools=_TOOLS,
        pii=items,
        preceded_by="",
        annotators=0,
        adjudicated=False,
        negatives=[Negative(order, "номер заказа", 1)],
        links=[
            LinkExpectation(
                left="first", right="second", kind="different", case="",
                why=("два дома на одной улице — разные здания; слияние отправит "
                     "курьера к соседу")),
            LinkExpectation(
                left="third", right="first", kind="unjudged", case="",
                why=("голая улица подходит обоим адресам, правило "
                     "единственного кандидата обязано отказать, и требовать "
                     "связывания значило бы наказывать шлюз за правоту")),
        ],
        calls=[],
        expected_answer="нет",
    )


_BUILDERS = {
    "same": _build_same,
    "different": _build_different,
    "ambiguous": _build_ambiguous,
}

# The per-register cycle, interleaved so that ANY prefix of five cases covers one
# cell across all five registers and any prefix of twenty covers all four
# vehicles. A block-ordered cycle would make `build(rng, 20)` twenty address
# cases, and a development-sized draw would then decide nothing about names.
#
# Counts over the twenty: place 10 (5 same, 3 different, 2 ambiguous), name 4,
# phone 3, order 3 — the doc's 50/50 split between place and person, with the
# person half divided among the three mechanisms that carry an identity.
_CYCLE: tuple[tuple[str, str], ...] = (
    ("place", "same"), ("name", "same"), ("phone", "same"), ("order", "same"),
    ("place", "different"), ("name", "different"), ("place", "same"),
    ("order", "different"), ("place", "ambiguous"), ("phone", "different"),
    ("place", "same"), ("name", "same"), ("place", "different"),
    ("order", "same"), ("place", "same"), ("name", "different"),
    ("place", "ambiguous"), ("phone", "same"), ("place", "different"),
    ("place", "same"),
)


def _conversation_id(index: int) -> str:
    """Half the cases are handed an id, half must have one DERIVED.

    Being given a `conversation_id` and deriving one from the transcript are
    different code paths, and the derived one is what a customer gateway with no
    conversation field actually triggers. v1 exercised neither: it passed the
    empty string and had no linking case, so the empty string was an accident
    rather than a measurement.
    """
    return "" if index % 2 else f"cmp-conv-{index:04d}"


# --- the answer axis ------------------------------------------------------
#
# Stated here for the same reason `same_value` is stated in the schema: a scorer
# that writes its own parser writes its own number. WebArena checks a reply with
# `must_include` — a substring — and ABC measured that leniency at 1.4-5.2%
# inflation, so a reply containing «нет» anywhere counted as «нет».

_REFUSALS: tuple[str, ...] = (
    "не могу", "не уверен", "не знаю", "уточните", "нужно уточнить",
    "не получается определить", "не могу подтвердить", "затрудняюсь",
)


def classify_answer(text: str | None) -> str:
    """One of «да», «нет», «refusal», «absent».

    Order matters and it is not arbitrary. A reply that OPENS with да/нет HAS
    answered, whatever it hedges afterwards: the customer reads the first word
    and acts on it, so «Нет, я не могу подтвердить» to a question whose answer is
    «да» is a wrong answer delivered and not an abstention — it earns no lenient
    credit. Only a reply that does not open with one is searched for a refusal
    marker.

    `absent` is the AgentBench move: a model that produced no parseable answer is
    a model failure and must never move the gateway's number in either direction.
    """
    if text is None:
        return "absent"
    stripped = text.strip().lower().lstrip("«\"'")
    if stripped.startswith("да"):
        return "да"
    if stripped.startswith("нет"):
        return "нет"
    if any(marker in stripped for marker in _REFUSALS):
        return "refusal"
    for word in ("нет", "да"):
        if f" {word} " in f" {stripped.replace(',', ' ').replace('.', ' ')} ":
            return word
    return "absent"


def score_answer(case: Case, reply: str | None) -> tuple[bool, bool]:
    """(strict, lenient) for one case's final assistant text.

    STRICT is the headline: only the correct closed answer passes. LENIENT also
    accepts a refusal, and the two are printed side by side because the gap
    between them is the whole diagnosis — a gateway that breaks linking so badly
    the model stops answering is meaningfully better than one that makes it
    answer wrongly with confidence. A confident wrong answer passes neither.
    """
    answer = classify_answer(reply)
    strict = answer == case.expected_answer
    return strict, strict or answer == "refusal"


# --- entry point ----------------------------------------------------------

def build(rng: random.Random, count: int) -> list[Case]:
    """`count` cases of the `compare` family, deterministic from `rng`.

    Case `i` draws from `rng` in a fixed order and its cell is a pure function of
    `i`, so `build(rng, 20)` is the prefix of `build(rng, 100)`. That is what
    makes a small development draw comparable with the full family instead of
    being a different measurement under the same name.
    """
    if count < 0:
        raise ValueError(f"count {count} is negative")
    cases: list[Case] = []
    openings: dict[str, str] = {}
    for index in range(count):
        register = REGISTERS[index % len(REGISTERS)]
        subject, arm = _CYCLE[(index // len(REGISTERS)) % len(_CYCLE)]
        case = _BUILDERS[arm](rng, register, subject, index)
        # THE DERIVED-SCOPE COLLISION, checked rather than assumed. Half these
        # cases carry no conversation id, so the engine keys the conversation on
        # the first two messages — and message zero is the same prompt in every
        # case. Two cases with the same opening turn would then share one
        # conversation, and one customer's address would resolve inside another's
        # dialogue: a corpus bug that reports as a gateway leak.
        opening = message_text(case, 1)
        if opening in openings:
            raise ValueError(
                f"{case.id} opens identically to {openings[opening]}; with a "
                f"derived conversation id these two cases would share a scope")
        openings[opening] = case.id
        cases.append(case)
    return cases


def main() -> None:
    """Build the family and validate it. No corpus is written here — the corpus
    builder owns the file; this is the check that the generator's spans agree
    with its own text, which is the part that rots first."""
    from bench.agentpii2.schema import case_characters, validate

    cases = build(random.Random(20260830), 100)
    problems = [problem for case in cases for problem in validate(case)]
    sizes = [case_characters(case) for case in cases]
    print(f"cases      {len(cases)}")
    print(f"characters min {min(sizes)} max {max(sizes)} "
          f"(short band is 0-400)")
    print(f"problems   {len(problems)}")
    for problem in problems[:20]:
        print(f"  {problem}")


if __name__ == "__main__":
    main()
