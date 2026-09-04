"""The awkward, the rare and the deliberately hostile.

The other suites prove the product works. This one tries to make it fail, on the
inputs a real Russian business actually produces: a name that is also a common
noun, a plate typed without switching keyboard layout, an address with a корпус
and a литера, a phone written six ways, and a message with ten entities at once.

TWO PROPERTIES, and a case can fail either way:

  ROUND TRIP — the real value comes back. A miss here means the customer's tool
  executes on a fake, which is the failure the product exists to prevent.

  NO OVER-MASKING — an order number, an article code or a tracking number is not
  personal data. Masking it makes the model useless for the job it was given,
  and the customer notices immediately.

Cases are grouped from ordinary to hostile, and each group states why it is
hard, so a future failure is diagnosable rather than just red.

    python3 test_hard_cases.py
"""

import os
import sys
import tempfile

import testkit
from pseudex import morph_places
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, unmask_text
from pseudex.vault import Vault

_FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"  {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(label)


# --------------------------------------------------------- must be detected

# (text, the entity types that MUST be found, why it is hard)
MUST_DETECT: list[tuple[str, set[str], str]] = [
    # --- ordinary, the baseline ---
    ("Иванов Пётр Сергеевич, +7 916 214-88-03", {"NAME", "PHONE"}, "обычное ФИО и телефон"),
    ("Позвоните Марии по номеру 89162148803", {"NAME", "PHONE"}, "имя без фамилии, телефон с 8"),

    # --- phones in the shapes people actually type ---
    ("тел. +7(916)214-88-03", {"PHONE"}, "скобки без пробелов"),
    ("телефон 8 916 214 88 03", {"PHONE"}, "восьмёрка и пробелы"),
    ("моб: +79162148803, доб. 214", {"PHONE"}, "слитно, рядом добавочный"),

    # --- the 46 values the live v4 re-run leaked to the model (03.09.2026) ---
    ("курьера на вишёнвая 28 это в крсанодар на имя марину телефон +79601068867", {"LOC", "NAME", "PHONE"},
     "улица с опечаткой, без слова-типа, за словом намерения — 15 из 46 утечек"),
    ("курьера на нидняя 59 это в соравала на имя кирилла", {"LOC", "NAME"}, "опечатка в голой улице"),
    ("курьера на пушкна шестьдесят пять корпус один это в самара", {"LOC"}, "опечатка в голой улице, дом словами"),
    ("теперь базисная 152кв7", {"LOC"}, "квартира приклеена к дому после голой улицы"),
    ("правильно химзаводская 3кв170 это в колпино", {"LOC"}, "однозначный дом и приклеенная квартира"),
    ("запишите миллера валерия леонидовича родился двадцать первое сентября восьмидесятого года", {"NAME", "DOB"},
     "дата рождения словами: порядковое число, месяц, год без века"),
    ("запишите миллера валерия леонидовича родилсяя двадцать первое сентября", {"NAME", "DOB"},
     "опечатка в «родился» — не четвёртое слово имени и не публичная фигура"),
    ("г Самара, ул Пушкина, д 65 к 1", {"LOC"}, "запись справочника с корпусом через пробел"),
    ("ул. Кирова 12 к 3 кв 300", {"LOC"}, "корпус через «к» с пробелом перед квартирой"),
    ("сверьте мои данные силс 20304105882 паспорт 1812759266", {"SNILS", "PASSPORT"},
     "СНИЛС с подсказкой и битой контрольной суммой — опечатка клиента, а не чужое число"),
    ("снилс 655-971-771 57 паспорт 9414 887065", {"SNILS", "PASSPORT"}, "то же, с разделителями"),
    ("телефон восемь девятьсот пятьдесят два двести шеесят пейсят два семьдесят", {"PHONE"},
     "сокращённые -десят в продиктованном номере"),
    ("сверьте паспрот 0312943300 выдан гу мвд", {"PASSPORT"}, "подсказка с опечаткой перед паспортом"),
    ("сннилс 40621994460 паспоот 4119424336", {"SNILS", "PASSPORT"}, "две подсказки с повреждением"),
    ("паспоорт сорок пять ноль восемь девяносто четыре десять шестьдесят восемь сергеев кирилл", {"PASSPORT", "NAME"},
     "устный паспорт за растянутой подсказкой"),
    ("паспорт ноль три четырнадцать пятьдесят восемь семьдесят пять восемьдесят громова марина борисовна", {"PASSPORT", "NAME"},
     "устный паспорт, случайно проходящий веса ИНН — подсказка главнее суммы"),
    ("дата рожжения 28.04.1975 телефон", {"DOB"}, "подсказка рождения с опечаткой"),
    ("дата рождения второго 05 06 1988", {"DOB"}, "дата через пробелы в родильном контексте"),
    ("адрес глазов проспект маяковского 163 кв 180", {"LOC"}, "строчный город перед словом-типом — не человек"),
    ("курьера на Ижевск, Маяковского, 141 подъезд 5 кв. 175", {"LOC"}, "письменная форма «Город, Улица, дом» с запятыми"),
    ("Москва, Ленина, 14", {"LOC"}, "самая частая письменная форма адреса"),
    ("курьераа на коммунаров дом сто девяносто шесть", {"LOC"}, "родительный множественного с маркером «дом»"),
    ("я в ижевск переулок коммнаров дом сто восемьдесят семь б телефон", {"LOC"}, "опечатка улицы за словом-типом, дом словами"),
    ("привет курьеа на мончегорсуая 195 корпус 1", {"LOC"}, "опечатка и в слове намерения, и в улице"),
    ("восемьдесят семь сорок восемсь кукушкин валерий михайлович", {"NAME"}, "числительное не приклеивается к имени"),

    # --- what the live v4 pilot and its hard negatives taught (02.09.2026) ---
    ("Адрес офиса для встречи — Розы Люксембург бульвар, дом 200.", {"LOC"},
     "двухсловное название улицы ПЕРЕД словом-типом: «Розы» не человек"),
    ("Вызовите сантехника на Кирова пр., дом 235.", {"LOC"},
     "сокращение типа после названия: «пр.» перед запятой"),
    ("Запишите адрес клиента: д. Петрово, набережная Космонавтов, д. 3", {"LOC"},
     "«д.» — деревня, когда за ним слово с заглавной"),
    ("Иван Петров улица Ленина 5", {"NAME", "LOC"},
     "человек из двух слов перед адресом остаётся человеком"),
    ("заведитее карточкуу букин сергей иванович телефон 8 916 402 11 87", {"NAME", "PHONE"},
     "опечатка в глаголе не съедается спаном имени"),
    ("добрыый деень курьера наа калашникова девять этоо в краснодаар", {"LOC"},
     "улица в форме фамилии перед числительным словами — адрес, не человек"),
    ("адресто можга проезд пушкина восемьдесят девять квартира шестьдесят семь", {"LOC"},
     "строчный город перед улицей входит в адрес, cue-слово с частицей снимается"),

    # --- documents ---
    ("СНИЛС 112-233-445 95", {"SNILS"}, "СНИЛС с контрольной суммой"),
    ("ИНН 770512345650", {"INN"}, "ИНН физлица, 12 знаков, валидный"),
    ("ИНН 7705123452 юрлица", {"INN"}, "ИНН юрлица, 10 знаков"),
    ("паспорт 4517 812345", {"PASSPORT"}, "серия и номер без знака №"),
    ("Карта 4276 1600 1234 5675", {"CARD"}, "карта, валидная по Луну"),

    # --- plates: every ГОСТ type, both layouts ---
    ("Машина А123ВС777", {"PLATE"}, "легковой, кириллица"),
    ("Машина E777KX102", {"PLATE"}, "ЛАТИНСКАЯ раскладка — те же 12 букв"),
    ("Машина е777кх102", {"PLATE"}, "латиница строчными"),
    ("Номер В 456 УО 45", {"PLATE"}, "с пробелами, двузначный регион"),
    ("Такси АА123 77", {"PLATE"}, "тип 1Б"),
    ("Прицеп АВ1234 77", {"PLATE"}, "тип 1А"),
    ("Мотоцикл 1234 АВ 77", {"PLATE"}, "тип 2"),

    # --- names that are also ordinary words ---
    ("Клиент Мороз Елена Ивановна", {"NAME"}, "фамилия = нарицательное"),
    ("Записать Веру Кисель", {"NAME"}, "имя и фамилия оба нарицательные"),
    ("Договор с Любовью Соколовой", {"NAME"}, "Любовь склоняется не как чувство"),

    # --- names that resist morphology ---
    ("Курьер к Анне Черных", {"NAME"}, "несклоняемая фамилия на -ых"),
    ("Счёт Шевченко Тарасу Григорьевичу", {"NAME"}, "несклоняемая на -ко + отчество"),
    ("Заявка от Салтыкова-Щедрина Михаила", {"NAME"}, "двойная фамилия"),
    ("Клиент Алиев Рустам Ахмед оглы", {"NAME"}, "тюркское отчество"),

    # --- addresses in the forms delivery actually sees ---
    ("Адрес: Москва, Ленинский проспект 42, кв. 118", {"LOC"}, "город, проспект, квартира"),
    ("ул. Тверская, д. 7, корп. 2, стр. 1", {"LOC"}, "корпус и строение"),
    ("г. Казань, ул. Профсоюзная, д. 17, под. 3", {"LOC"}, "подъезд"),

    # --- email ---
    ("Чек на m.ivanova@acme.ru", {"EMAIL"}, "обычная почта"),
    ("почта i.petrov+заказ@example.co.uk", {"EMAIL"}, "плюс-адресация, кириллица, двойной домен"),
    ("пишите на иван.петров@почта.рф", {"EMAIL"}, "полностью кириллический адрес"),

    # --- everything at once, which is what a real message looks like ---
    ("Здравствуйте! Иванов Пётр Сергеевич, +7 916 214-88-03, "
     "m.ivanov@acme.ru, СНИЛС 112-233-445 95, ИНН 770512345650, "
     "машина А123ВС777, адрес Москва, Ленинский проспект 42",
     {"NAME", "PHONE", "EMAIL", "SNILS", "INN", "PLATE", "LOC"},
     "семь типов в одном сообщении"),
]


# ----------------------------------------------------- must NOT be detected

# Ground truth here is "no personal data at all". Over-masking these makes the
# model useless for the task: an agent that cannot see the order number cannot
# look up the order.
MUST_NOT_DETECT: list[tuple[str, str]] = [
    ("заказ на складе 5 готов", "известное слово с числом за словом намерения — не улица"),
    ("привезите на дачу 12 коробок", "число считает коробки"),
    ("курьера на завтра 10 утра", "время, не дом"),
    ("курьера на объект 7", "известное слово — не опечатка улицы"),
    ("договор 9455 480555 оплачен", "документ — не паспорт"),
    ("Тверь, Советская, 5 км от центра", "мера после числа"),
    ("заказ WA-4471 доставлен", "номер заказа"),
    ("артикул 7705123456 на складе", "артикул из цифр, длиной как ИНН"),
    ("трек-номер RB123456789CN", "почтовый трек"),
    ("счёт 2024/117 от 15 числа", "номер счёта"),
    ("версия 4517 812345 сборки", "цифры в форме паспорта, но это сборка"),
    ("сумма 4276 1600 рублей", "цифры в форме карты"),
    ("код подтверждения 112233", "одноразовый код"),
    ("рейс SU 1234 вылетает в 15:00", "номер рейса"),
    ("документ ГОСТ Р 50577-2018", "номер стандарта"),
    ("температура 36.6, давление 120/80", "медицинские числа без человека"),
    ("Встреча в переговорной 2 в 15:00.", "номер переговорной и время, а не дом и литера"),
    ("Площадь помещения 80 кв.м, какая цена?", "площадь как площадь, единица измерения после числа"),
]


def test_detection(detector: Detector) -> None:
    missed = []
    for text, wanted, why in MUST_DETECT:
        found = {span.entity_type for span in detector.detect(text)}
        # ADDR is an internal type remapped to LOC; accept either.
        if "ADDR" in found:
            found.add("LOC")
        if not wanted <= found:
            missed.append((why, sorted(wanted - found), text[:48]))
    check("every hard case is detected", not missed,
          f"missed={missed}" if missed else f"{len(MUST_DETECT)} cases")


def test_no_over_masking(detector: Detector) -> None:
    over = []
    for text, why in MUST_NOT_DETECT:
        found = [(s.entity_type, s.value) for s in detector.detect(text)]
        if found:
            over.append((why, found))
    check("nothing that is not personal data is masked", not over,
          f"over-masked={over}" if over else f"{len(MUST_NOT_DETECT)} negatives")


def test_round_trip(vault: Vault, detector: Detector) -> None:
    """The value the tool receives must be the real one, for every case above."""
    broken = []
    for text, _, why in MUST_DETECT:
        masked = mask_text(text, vault, detector.detect(text))
        if masked == text:
            continue  # nothing detected; covered by the detection check
        restored = unmask_text(masked, vault)
        for span in detector.detect(text):
            # NAME comes back in the sentence's case and PHONE in its canonical
            # form (+7…) — both are deliberate, documented, and checked in their
            # own suites. Here the question is only whether the REAL value
            # returned at all, so compare on digits for phones.
            if span.entity_type == "NAME":
                continue
            if span.entity_type == "PHONE":
                digits = "".join(c for c in span.value if c.isdigit())[-10:]
                restored_digits = "".join(c for c in restored if c.isdigit())
                if digits not in restored_digits:
                    broken.append((why, "PHONE", span.value))
                continue
            if span.entity_type == "PLATE":
                # Case is not identity for a plate either, and for the same
                # reason the phone above compares on digits: «е777кх102» and
                # «Е777КХ102» are one car, so they now share one vault row and
                # the row returns whichever spelling was written FIRST.
                #
                # THIS ASSERTION WAS RELAXED, deliberately and after the fact —
                # the strict form was passing only because one car was being
                # kept as several. The ГОСТ alphabet was chosen so every letter
                # has a Latin twin, so the fold belongs here too.
                fold = str.maketrans("ABEKMHOPCTYXabekmhopctyx",
                                     "АВЕКМНОРСТУХавекмнорстух")
                wanted = span.value.translate(fold).upper()
                if wanted not in restored.translate(fold).upper():
                    broken.append((why, "PLATE", span.value))
                continue
            if span.value not in restored:
                broken.append((why, span.entity_type, span.value))
    check("every detected value round-trips back intact", not broken,
          f"broken={broken}" if broken else "")


def test_model_never_sees_the_original(vault: Vault, detector: Detector) -> None:
    """The point of the product: no detected value survives into the masked text."""
    leaks = []
    for text, _, why in MUST_DETECT:
        spans = detector.detect(text)
        masked = mask_text(text, vault, spans)
        for span in spans:
            if span.value in masked:
                leaks.append((why, span.entity_type, span.value))
    check("no detected value reaches the model", not leaks,
          f"leaks={leaks}" if leaks else f"{len(MUST_DETECT)} messages")


def test_same_value_same_token(vault: Vault, detector: Detector) -> None:
    """One person is one identity, however the message is phrased.

    Checked on a phone, where canonicalisation has always worked, and on a name,
    where it was added — a customer writing the same person two ways must not
    become two people in the agent's memory.
    """
    phone_forms = ["+7 916 214-88-03", "8 916 214 88 03", "89162148803", "+79162148803"]
    tokens = set()
    for form in phone_forms:
        text = f"Телефон {form}"
        tokens.add(mask_text(text, vault, detector.detect(text)).replace("Телефон ", ""))
    check("one phone written four ways is ONE token", len(tokens) == 1,
          f"tokens={tokens}")


def test_json_payload(vault: Vault, detector: Detector) -> None:
    """PII inside a JSON body, which is how a tool call actually carries it.

    Quotes and braces around a value must not stop detection, and the restored
    text must still parse as JSON — a substitution that changes the number of
    quotes breaks the caller's parser rather than their privacy.
    """
    import json
    payload = json.dumps({
        "name": "Иванов Пётр Сергеевич",
        "phone": "+7 916 214-88-03",
        "address": "Москва, Ленинский проспект 42",
        "order": "WA-4471",
    }, ensure_ascii=False)
    masked = mask_text(payload, vault, detector.detect(payload))
    restored = unmask_text(masked, vault)
    ok_json = True
    try:
        parsed = json.loads(restored)
    except json.JSONDecodeError:
        ok_json, parsed = False, {}
    check("a JSON tool payload survives masking and still parses", ok_json,
          "" if ok_json else f"restored={restored[:120]}")
    check("the order number is untouched inside JSON",
          parsed.get("order") == "WA-4471", f"order={parsed.get('order')}")
    check("the phone comes back exactly",
          parsed.get("phone") == "+7 916 214-88-03", f"phone={parsed.get('phone')}")


def test_repeated_masking_is_stable(vault: Vault, detector: Detector) -> None:
    """A growing transcript re-sends the same text; the token must not drift.

    If it did, the person's identity would change every turn and the provider's
    prefix cache would miss on every request.
    """
    text = "Клиент Иванов Пётр Сергеевич, +7 916 214-88-03"
    first = mask_text(text, vault, detector.detect(text))
    second = mask_text(text, vault, detector.detect(text))
    check("masking the same text twice gives the same tokens", first == second,
          f"first={first[:60]} second={second[:60]}")


def test_masked_output_is_not_remasked(vault: Vault, detector: Detector) -> None:
    """`mask(mask(x))` must equal `mask(x)`.

    A fake phone is a valid phone shape, so detection finds it again. Minting a
    second token would make detokenization return the intermediate token — the
    tool would execute on a plausible but WRONG person.
    """
    text = "Клиент Иванов Пётр Сергеевич, +7 916 214-88-03"
    once = mask_text(text, vault, detector.detect(text))
    twice = mask_text(once, vault, detector.detect(once))
    check("a masked message is not masked a second time", once == twice,
          f"once={once[:60]} twice={twice[:60]}")


ADDRESS_ROUND_TRIP = [
    "Адрес: Москва, Ленинский проспект 42, кв. 118",
    "Доставка на ул. Тверская, д. 7, корп. 2",
    "г. Казань, ул. Профсоюзная, д. 17",
    "Курьер приехал на улицу Арбат",
    "Живёт в Санкт-Петербурге на Невском проспекте 100",
    "Встретимся на Тверской 7",
    "переезд с улицы Ленина на улицу Победы",
    "Клиент Иванов Пётр, Москва, ул. Тверская 7",
    "Доставка в Казань, ул. Баумана 5, кв. 3",
    "Офис на Ленинском проспекте, дом 10, корпус 3",
    "Заберите с Профсоюзной 12 и отвезите на Тверскую 7",
    "Живу на Валдае, улица Мира 4",
]


def test_addresses(vault: Vault, detector: Detector) -> None:
    """Addresses agree with their sentence AND come back intact.

    Both halves are needed and neither implies the other. A substitute that
    reads `улице Тополиной, 21` in a nominative slot invites the model to fix
    it; a fix it cannot be matched back from delivers a fake address to a
    courier. The suffix-stripping key that was tried first passed the first half
    and failed the second — `Валдай` and `Валдае` reduced to different stems —
    so the signature is built from lemmas now.
    """
    broken, nominative_in_oblique = [], []
    for original in ADDRESS_ROUND_TRIP:
        spans = [s for s in detector.detect(original) if s.entity_type == "LOC"]
        masked = mask_text(original, vault, detector.detect(original))
        if unmask_text(masked, vault) != original:
            broken.append((original, masked, unmask_text(masked, vault)))
        for span in spans:
            want = morph_places.detect_case(span.value)
            if want in (None, "nomn"):
                continue
            for masked_span in detector.detect(masked):
                if masked_span.entity_type != "LOC":
                    continue
                if morph_places.detect_case(masked_span.value) == "nomn":
                    nominative_in_oblique.append((original, masked))
                break
    check("every address round-trips back intact", not broken,
          f"broken={broken}" if broken else f"{len(ADDRESS_ROUND_TRIP)} addresses")
    check("no address substitute sits in the nominative inside an oblique slot",
          not nominative_in_oblique, f"{nominative_in_oblique}")


def test_address_signature_is_inflection_proof() -> None:
    """Every pool entry must key the same in every case, or restoration misses.

    Checked over the whole leased pool rather than a sample: this is the
    property the round trip rests on, and a single entry that fails it is one
    address type that silently delivers a fake.
    """
    from pseudex.vault import _FAKE_CITIES, _FAKE_STREETS
    drift = []
    for city in _FAKE_CITIES:
        nominative = morph_places.to_nominative(city)
        for case in ("gent", "datv", "loct", "ablt", "accs"):
            inflected = morph_places.inflect_place(nominative, case)
            if morph_places.match_signature(nominative) != morph_places.match_signature(inflected):
                drift.append((nominative, case, inflected))
    for street in _FAKE_STREETS:
        phrase = f"улица {morph_places.to_nominative(street)}, 42"
        for case in ("gent", "datv", "loct", "ablt", "accs"):
            inflected = morph_places.inflect_place(phrase, case)
            if morph_places.match_signature(phrase) != morph_places.match_signature(inflected):
                drift.append((phrase, case, inflected))
    check("the address signature survives every case of every pool entry",
          not drift, f"drift={drift[:5]}" if drift else
          f"{(len(_FAKE_CITIES) + len(_FAKE_STREETS)) * 5} combinations")


def test_street_stays_a_street(vault: Vault, detector: Detector) -> None:
    """A street must not be substituted by a settlement, or the sentence changes
    meaning: «доставка на ул. Профсоюзная» coming back as «Кинешме» is a
    different delivery, and the model has no way to know."""
    wrong = []
    for original in ["Доставка на ул. Профсоюзная, д. 17",
                     "ул. Тверская, д. 7", "Ленинский проспект 42"]:
        masked = mask_text(original, vault, detector.detect(original))
        # Checked by KIND, not by the literal word. The substitute now mirrors
        # the original's generic — a проспект stays a проспект and «ул.» stays
        # «ул.» — so requiring the letters «улиц» tested the old behaviour of
        # turning every street into an улица, which was itself the defect.
        if not morph_places.looks_like_street(masked):
            wrong.append((original, masked))
    check("a street is replaced by a street, never by a town",
          not wrong, f"wrong={wrong}" if wrong else "")


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    vault = Vault(os.path.join(tempfile.mkdtemp(), "hard.db"), "hard-cases")

    test_detection(detector)
    test_no_over_masking(detector)
    test_round_trip(vault, detector)
    test_model_never_sees_the_original(vault, detector)
    test_same_value_same_token(vault, detector)
    test_json_payload(vault, detector)
    test_repeated_masking_is_stable(vault, detector)
    test_masked_output_is_not_remasked(vault, detector)
    test_addresses(vault, detector)
    test_address_signature_is_inflection_proof()
    test_street_stays_a_street(vault, detector)
    test_chat_register(detector)

    print()
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} — {_FAILURES}")
        return 1
    print("hard cases OK — detected, restored, and nothing over-masked")
    return 0



def test_chat_register(detector: Detector) -> None:
    """The two shapes a support chat produces that a written sentence never does.

    Both were measured by the noise ladder, and both cost more than typos do:
    lower case alone was −15.4 points of recall and dropping punctuation another
    −11.1, against −6.4 for a typo. Every value lost at the lower-case rung was
    an address; every value lost at the punctuation rung on top of it was a date.

    A MARKED STREET WITH NO HOUSE NUMBER, in lower case. «проживает на тверской
    улице» was invisible — the capitalised arm needs its capital, the lower-case
    arms need a house number. What replaces the house number as a guard is an
    address INTENT word, not a preposition: «на улицах города собрались десятки»
    opens with «на» too, and only somebody saying they live or receive things
    there separates an address from prose about streets. (The CAPITALISED arm is
    looser and always was — «улицах Каира» is masked on its own, which is a
    separate, older question about a marked street with no house number.)

    A DATE WITH ITS SEPARATORS GONE. «24121967» is eight digits and no shape,
    and it is judged by the SAME association rule as «24.12.1967» — personal
    beside an identifier or a birth cue, ordinary otherwise. That is why «заказ
    24121967 готов» stays untouched while «дата рождения 24121967» does not.
    """
    must_find = [
        ("николай зайцев проживает в екатеринбурге на тверской улице", "тверской улице"),
        ("адрес: москве, проспекте мира", "проспекте мира"),
        ("дата рождения 24121967", "24121967"),
        ("реквизиты снилс 647-436-713 22 карта 4090 9743 9533 9426 дата 21011979",
         "21011979"),
    ]
    for text, value in must_find:
        found = [text[span.start:span.end] for span in detector.detect(text)]
        assert any(value in one or one in value for one in found), \
            f"{value!r} not detected in {text!r} — found {found}"

    must_not = [
        "улица была пустой",
        "на главной улице города много людей",
        "на улицах города собрались десятки человек",
        "торговая площадка закрылась",
        "заказ 24121967 готов",
        "артикул 12345678 в наличии",
    ]
    for text in must_not:
        found = [text[span.start:span.end] for span in detector.detect(text)]
        assert not found, f"over-masked {text!r} -> {found}"
    print("chat register OK — lower-case streets and glued dates, without the prose")

if __name__ == "__main__":
    sys.exit(main())
