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

import json
import os
import sys
import tempfile

import testkit
from pseudex import morph_places
from pseudex.detect_all import Detector
from pseudex.redact import mask_text, residual_tokens, unmask_arguments, unmask_text
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
    ('{"RQ_IDENT_DOC_SER": "4509", "RQ_IDENT_DOC_NUM": "123456", "RQ_INN": "500100732259"}',
     {"PASSPORT", "INN"}, "реквизиты Bitrix24: паспорт двумя полями, ИНН физлица"),
    # --- the five leaks a corpus on a FRESH seed found on 04.09 (none of ours had seen them) ---
    ("новый адрес челюскинцев 159 квартира 183", {"LOC"}, "родительный множественного за цифрой, с дверью после номера"),
    ("курьера на ленна дом сорок три а это в воткинск", {"LOC"}, "опечатка улицы перед «дом», слово известно словарю как краткое прилагательное"),
    ("курьера на воткинск проезд лермонтого дом двадцать пяять четвёртый подъезд квартира сто тридцать семь", {"LOC"},
     "опечатка в окончании улицы (две правки) и удвоенная буква в числительном"),
    ("курьера на сортавала добролюбого четырнадцать третий подъезд квартира двадцать один", {"LOC"},
     "город, опечатка в окончании голой улицы, дом словами, дверь"),
    ("запишите букина сергея ивановича он 19 12 1992 телефон 8-951-103-04-38", {"NAME", "DOB", "PHONE"}, "дата сразу после местоимения — дата рождения"),
    ("курьера на чапаева 17 на имя ирину телефн 89505973171", {"LOC", "NAME", "PHONE"}, "повреждённое слово-подсказка не приклеивается к имени"),
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
    ('{"RQ_KPP": "773601001", "RQ_OGRN": "1027700132195"}',
     "КПП и ОГРН определяют ЮРЛИЦО — 152-ФЗ их не покрывает, маскировать нельзя"),
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


def test_the_mirror_shows_nothing_real(detector: Detector) -> None:
    """The substitute is laid into the customer's own presentation, and the
    fail-safe that guards it asks about WORDS, not about a key.

    BOTH HALVES, because a proxy lies in both directions. The accept half:
    «г. Ачинск, б-р Озёрный, д. 78, кв. 105» has a flawless mirror — every word
    in it is the fake's or a marker — and `place_key` refused it anyway, since
    the vault's noise list carries «д» and «кв» but not «г», so the two strings
    differed by one stem. The model was shown a tidied canon, a rewriting agent
    had nothing to normalise, and the customer's own raw string came back where
    the agent's form was owed. The refuse half: a numbered or two-word street
    mis-aligns inside `in_form_of` and leaves the REAL name and the REAL house
    standing — «г. Киров, липоваяд 8-й Вешняковский, д. 38» — and that must
    still fall back to the canonical fake. Several draws because the fake is
    drawn at random and only the structure is ours to assert."""
    # A REAL STREET NAME THE POOL CANNOT DRAW, so «it came back» never means
    # «it was drawn»; the house and flat numbers ARE drawn from the real ones'
    # magnitude, so no assertion here may rest on a digit literal.
    tidy = "Доставка на г. Ачинск, б-р Комсомольский, д. 78, кв. 105"
    mirrored = []
    for attempt in range(5):
        talk = Vault(":memory:", "acme").for_conversation(f"mirror-{attempt}")
        mirrored.append(mask_text(tidy, talk, detector.detect(tidy)))
    check("the customer's own presentation is mirrored when nothing real survives",
          all(m.startswith("Доставка на г. Ачинск, б-р ") and ", д. " in m and ", кв. " in m
              for m in mirrored), f"{mirrored}")
    check("and the mirror shows no real word of the address",
          all("Комсомольск" not in m for m in mirrored), f"{mirrored}")

    # The refuse half: `in_form_of` mis-aligns on a NUMBERED street and leaves
    # the customer's own name and his ordinal standing inside the fake
    # («г. Киров, липоваяд 8-й Вешняковский, д. 38»). Neither the name nor the
    # ordinal can be minted, so both are evidence and neither is a lottery.
    for surface, real_words in (
        ("Доставка на г. Киров, пр-д 4-й Вешняковский, д. 38, кв. 77",
         ("Вешняковск", "4-й", "-й ")),
        ("Доставка на г. Балашов, ул. 3-я Победиловская, д. 77, кв. 113",
         ("Победиловск", "3-я", "-я ")),
    ):
        leaked = []
        for attempt in range(5):
            talk = Vault(":memory:", "acme").for_conversation(f"mis-{attempt}")
            masked = mask_text(surface, talk, detector.detect(surface))
            if any(word in masked for word in real_words):
                leaked.append(masked)
        check(f"a mis-aligned mirror is refused: {surface[12:40]}…", not leaked, f"{leaked}")


def test_preposition_is_not_a_litera(vault: Vault, detector: Detector) -> None:
    """«двадцать семь в третий подъезд» is house 27 IN the third entrance, not
    house 27в. The letter is a preposition when what follows is what a
    preposition governs — an ordinal, a marker in an oblique case — and a
    litera when a nominative marker follows («семнадцать в квартира двести
    двадцать девять» is a real call). The building went to the courier as
    «27в» on the 05.09 medium run (decompose-001, voice register)."""
    import json
    from pseudex.redact import unmask_arguments
    for said, house in (
        ("здравствуйте курьера на воткинск бульвар комиссарого двадцать семь в третий подъезд квартира сто шестьдесят два", "двадцать семь"),
        ("адрес улица ленина двадцать семь в квартиру пять", "двадцать семь"),
        ("адрес улица ленина двадцать семь к пятому подъезду", "двадцать семь"),
        ("бибиревская дом семнадцать в квартира двести двадцать девять", "семнадцать в"),
        ("так двадцать пять а корпус два квартира двадцать семь", "двадцать пять а"),
    ):
        spans = [s for s in detector.detect(said) if s.entity_type == "LOC"]
        check(f"one address span: {said[:40]}…", len(spans) == 1, f"{[s.value for s in spans]}")
        if len(spans) != 1:
            continue
        roles = morph_places.split_roles(spans[0].value)
        check(f"house role is «{house}»", roles.get("house") == house, f"roles={roles}")
    said = "здравствуйте курьера на воткинск бульвар комиссарого двадцать семь в третий подъезд квартира сто шестьдесят два"
    talk = Vault(":memory:", "acme").for_conversation("litera")
    masked = mask_text(said, talk, detector.detect(said))
    token = talk._conn.execute("SELECT token FROM tokens WHERE entity_type='LOC'").fetchone()[0]  # noqa: SLF001
    fake = morph_places.split_roles(token)
    back = json.loads(unmask_arguments(json.dumps({"address": {"building": fake["house"], "porch": fake["entrance"], "sflat": fake["flat"]}}), talk))
    check("building 27, porch 3, flat 162 reach the courier", back == {"address": {"building": "27", "porch": "3", "sflat": "162"}},
          f"token={token!r} back={back}")


def test_a_numbered_street_is_not_a_house(detector: Detector) -> None:
    """«ул. 3-я Победиловская, д. 77» — дом 77, а улица называется «3-я
    Победиловская».

    Дом берётся как ПЕРВОЕ число, которое не забрал ни один маркер, и
    порядковый префикс названия — такое же число: роли выходили
    `street='ул'`, `house='3'`. Отсюда две поломки от одной причины. Схема,
    просящая поля по отдельности, получала в CRM «ул. Ул» и дом «3» — это
    мусор, а не иная форма. А `in_form_of` резал строку клиента по этим же
    ролям и вставлял части фейка ВНУТРЬ настоящего названия
    («родниковаяд 8-й Вешняковский, д. 38»), после чего предохранитель по
    словам правильно отбивал зеркало и показывал канон — то есть цена
    неверного разбора платилась и формой тоже.

    «дом 5-й корпус 2» проверяется здесь же: порядковое окончание за маркером
    дома — это дом, а не улица, иначе правка забрала бы номер дома."""
    for phrase, street, house in (
        ("г. Балашов, ул. 3-я Победиловская, д. 77, кв. 113", "ул. 3-я Победиловская", "77"),
        ("г. Киров, пр-д 4-й Вешняковский, д. 38, кв. 77", "пр-д 4-й Вешняковский", "38"),
        ("Москва, 2-я Тверская-Ямская 10, кв. 4", "2-я Тверская-Ямская", "10"),
        ("улица 5-й армии д62 кв149", "улица 5-й армии", "62"),
        ("3-я линия 5", "3-я линия", "5"),
        ("дом 5-й корпус 2", "", "5"),
        ("ул. Ленина, д. 14, кв. 3", "ул. Ленина", "14"),
    ):
        roles = morph_places.split_roles(phrase)
        check(f"роли: {phrase[:38]}…",
              roles.get("street", "") == street and roles.get("house") == house,
              f"{roles}")

    # …И ПОЛЕ `street` СХЕМЫ ПОЛУЧАЕТ НАЗВАНИЕ, А НЕ ОСТАТОК МАРКЕРА.
    said = "адрес г. Балашов, ул. 3-я Победиловская, д. 77, кв. 113"
    wrong = []
    for attempt in range(4):
        talk = Vault(":memory:", "acme").for_conversation(f"numbered-{attempt}")
        masked = mask_text(said, talk, detector.detect(said))
        fields = morph_places.split_roles(masked.split("адрес ", 1)[1])
        argument = json.dumps({"street": fields.get("street", ""),
                               "house": fields.get("house", ""),
                               "flat": fields.get("flat", "")}, ensure_ascii=False)
        restored = unmask_arguments(argument, talk)
        back = json.loads(restored)
        if (back["house"] != "77" or back["flat"] != "113"
                or "победиловск" not in back["street"].lower()
                or residual_tokens(restored, talk)):
            wrong.append((argument, restored, residual_tokens(restored, talk)))
    check("поля street/house/flat возвращают настоящий адрес без остатка", not wrong, f"{wrong}")


def test_a_frozen_genitive_street_is_not_an_oblique_case(detector: Detector) -> None:
    """«заболоцкого 81 кв 51» — ЭТО НАЗВАНИЕ УЛИЦЫ, А НЕ ПАДЕЖ ПРЕДЛОЖЕНИЯ.

    Без родового слова и без сокращённого маркера `detect_case` голосует по
    словам, а улица, названная по человеку, голосует за родительный или
    винительный — потому что так она и пишется в именительном. Прочитанная как
    косвенная, подмена склонялась и показывалась причёсанным каноном («улицы
    Вязовой 59, кв. 127»); переписывающему агенту нечего было нормализовать, он
    копировал, и наружу уходила сырая строка клиента там, где была должна форма
    агента. Чатовый регистр — основной трафик — именно такой формы.

    ВТОРАЯ ПОЛОВИНА ОБЯЗАТЕЛЬНА: прилагательное женского рода согласуется с
    опущенной «улицей» («на Тверской 7»), и там косвенное чтение остаётся —
    иначе модель читает ломаный русский и переписывает токен.
    """
    for said in ("курьера на заболоцкого 81 кв 51", "адрес чернышевского 29 кв 52"):
        shown = []
        for attempt in range(4):
            talk = Vault(":memory:", "acme").for_conversation(f"frozen-{attempt}")
            masked = mask_text(said, talk, detector.detect(said))
            shown.append(masked.split()[-4:])
        flat = [" ".join(words) for words in shown]
        check(f"замороженный родительный зеркалится, а не склоняется: {said[:28]}…",
              all("улиц" not in form and form == form.lower() for form in flat), f"{flat}")

    oblique = "Встретимся на Тверской 7"
    still_inflected = []
    for attempt in range(4):
        talk = Vault(":memory:", "acme").for_conversation(f"oblique-{attempt}")
        masked = mask_text(oblique, talk, detector.detect(oblique))
        for span in detector.detect(masked):
            if span.entity_type == "LOC" and morph_places.detect_case(span.value) == "nomn":
                still_inflected.append(masked)
    check("а согласующееся прилагательное по-прежнему склоняется",
          not still_inflected, f"{still_inflected}")


def test_an_abbreviation_inside_a_word_opens_no_window(vault: Vault, detector: Detector) -> None:
    """«ул» ВНУТРИ «Барнаул» — не маркер улицы.

    Ветка сокращений у `LOC_TOKEN_PATTERN` не имела левой границы слова, и окно
    восстановления строилось со смещения 5 в «Барнаул Ивовая 55»: настоящая
    улица вставлялась В СЕРЕДИНУ названия города — «Барнаватаняна 50». Запятая
    после города прятала дефект, потому что подмена чеканилась с ней; клиент,
    написавший город без запятой, его вскрывает — а теперь подмена повторяет
    форму клиента, значит вскрывает всегда."""
    said = "адрес барнаул ватаняна 50 кв 86"
    chewed = []
    for attempt in range(4):
        talk = Vault(":memory:", "acme").for_conversation(f"barnaul-{attempt}")
        masked = mask_text(said, talk, detector.detect(said))
        field = masked.split("адрес ", 1)[1]
        agent = " ".join(word[:1].upper() + word[1:] if word[:1].isalpha() and word[0] not in "к"
                         else word for word in field.replace(" кв ", " кв. ").split())
        back = json.loads(unmask_arguments(
            json.dumps({"address": agent}, ensure_ascii=False), talk))["address"]
        if not back.lower().startswith("барнаул "):
            chewed.append((agent, back))
    check("настоящая улица не вставляется внутрь названия города", not chewed, f"{chewed}")


def test_a_hyphen_glued_substitute_is_two_words(vault: Vault, detector: Detector) -> None:
    """ДЕФИС СКЛЕИЛ ПОДМЕНУ С НАСТОЯЩИМ СЛОВОМ КЛИЕНТА, И ПОЛОВИНА — НАША.

    «литвина-седого 39 кв 62»: детектор берёт «седого 39 кв 62» (Б16), первое
    слово остаётся клиентским, и в показанной строке «литвина-осиновая 39 кв 62»
    наша половина приклеена дефисом. Ни `_LOWER_WORD`, ни `_LOWER_RUN` её не
    предлагают — дефис стоит в их классе исключения НАМЕРЕННО, иначе при
    маскировании разрывалась бы дефисная фамилия. Пока подмена показывалась
    каноном («улицы Осиновой»), окно находил заглавный проход; со строчным
    зеркалом окна не стало, и **фейковая улица с фейковым домом уходила в
    инструмент с ПУСТЫМ `residual_tokens`** — статус 200 и никакого признака.

    Копирующий агент этого не видит: буквальный срез ловит `shown_forms`.
    Ломается переписывающий, поэтому агент здесь дописывает точку и запятую."""
    said = "адрес литвина-седого 39 кв 62"
    leaked = []
    for attempt in range(4):
        talk = Vault(":memory:", "acme").for_conversation(f"hyphen-{attempt}")
        masked = mask_text(said, talk, detector.detect(said))
        field = masked.split("адрес ", 1)[1]
        rewritten = field.replace(" кв ", ", кв. ")
        agent = rewritten[:1].upper() + rewritten[1:]
        argument = json.dumps({"address": agent}, ensure_ascii=False)
        back = json.loads(unmask_arguments(argument, talk))["address"]
        if "седого" not in back.lower() or "39" not in back:
            leaked.append((agent, back, residual_tokens(argument, talk)))
    check("склеенная дефисом подмена разрешается, а не уезжает в инструмент",
          not leaked, f"{leaked}")


def test_corrected_address_shares_its_street(vault: Vault, detector: Detector) -> None:
    """A customer who corrects the HOUSE keeps the STREET, and so must the
    substitutes: «заречная пятьдесят семь … ой нет, правильно заречная двадцать
    девять» was «Черёмуховая 15 … Грушевая 107» — a correction between two
    unrelated places (32 of 36 two-address `correction` cases on the seed-6060
    run). One real street in a dialogue is one fake street; the numbers differ,
    the `street` field the agent fills from the fake resolves to the corrected
    real spelling, and the house to the corrected house."""
    import json
    from pseudex.redact import unmask_arguments
    # The agent fills the field from the CAPITALISED fake («Заречная», как его
    # чеканит генератор), so the real street returns in the agent's case —
    # «Заречная», not the dictated lower-case «заречная». Форма агента, включая
    # регистр: та же половина правила, что и в опечатке «Мончгорская» выше.
    for said, street, house in (
        ("курьера на адрес заречная пятьдесят семь квартира сто восемьдесят семь ой нет правильно заречная двадцать девять квартира сто восемьдесят семь это в воткинск", "Заречная", "29"),
        ("курьера на адрес калашнкова 61кв134 стоп правильно калашникова 33 квартира 134 это в абакан", "Калашникова", "33"),
        ("привет курьера на энгельса 134 кв 92 нет не так правильно энгельса 106 квартира 92 это в воткинск", "Энгельса", "106"),
    ):
        talk = Vault(":memory:", "acme").for_conversation("fix")
        masked = mask_text(said, talk, detector.detect(said))
        tokens = [row[0] for row in talk._conn.execute("SELECT token FROM tokens WHERE entity_type='LOC' ORDER BY rowid").fetchall()]  # noqa: SLF001
        heads = {morph_places.split_roles(token).get("street", "") for token in tokens}
        check(f"one fake street for one real street: {said[:30]}…", len(tokens) == 2 and len(heads) == 1,
              f"tokens={tokens}")
        houses = {morph_places.split_roles(token).get("house", "") for token in tokens}
        check("two different fake houses", len(houses) == 2, f"tokens={tokens}")
        last = morph_places.split_roles(tokens[-1])
        # the agent writes the street bare, as the live model does («Речная», not «улица Речная»)
        bare = last["street"].split()[-1]
        back = json.loads(unmask_arguments(json.dumps({"address": {"street": bare, "building": last["house"]}}, ensure_ascii=False), talk))
        check("street and house restore to the CORRECTED real address",
              back == {"address": {"street": street, "building": house}}, f"masked={masked!r} back={back}")
        # …and the street ALONE, with two owners on one street, still resolves
        back = json.loads(unmask_arguments(json.dumps({"address": {"street": bare}}, ensure_ascii=False), talk))
        check("the street alone resolves when every owner agrees on it",
              back == {"address": {"street": street}}, f"back={back}")
    # two DIFFERENT streets in one dialogue still get two different fake streets
    said = "курьера на заречная 57 квартира 187 а потом на энгельса 106 квартира 92 это в воткинск"
    talk = Vault(":memory:", "acme").for_conversation("two")
    mask_text(said, talk, detector.detect(said))
    tokens = [row[0] for row in talk._conn.execute("SELECT token FROM tokens WHERE entity_type='LOC' ORDER BY rowid").fetchall()]  # noqa: SLF001
    heads = {morph_places.split_roles(token).get("street", "") for token in tokens}
    check("two real streets keep two fake streets", len(tokens) == 2 and len(heads) == 2, f"tokens={tokens}")


def test_spoken_birth_date_keeps_its_register(vault: Vault, detector: Detector) -> None:
    """A date of birth SAID is replaced by a date SAID: «родился одиннадцатого
    сентября пятьдесят пятого» was masked as «родился 28.03.1972 пятьдесят
    пятого» (9 of 9 spoken dates on the seed-6060 run) — digits in a spoken
    sentence and the real year left standing outside the span. Now the span
    reaches the year with or without «года», the substitute is in words, in
    the customer's own century style, keeps the year and the side of today
    (so the age the agent derives agrees), the ISO the agent writes resolves,
    and the prose paraphrase comes back as the real date."""
    import json
    import time
    from pseudex.redact import unmask_arguments
    from pseudex.vault import _date_canonical
    today = (time.localtime().tm_mon, time.localtime().tm_mday)
    for said, real_iso, year_words in (
        ("запишите кузнецова дмитрия андреевича родился одиннадцатого сентября пятьдесят пятого", "1955-09-11", "пятьдесят"),
        ("пациент родилась двадцать третьего марта тысяча девятьсот восемьдесят второго", "1982-03-23", "тысяча девятьсот"),
        ("дата рождения двадцать первого сентября восьмидесятого года", "1980-09-21", "года"),
    ):
        talk = Vault(":memory:", "acme").for_conversation("dob")
        spans = [s for s in detector.detect(said) if s.entity_type == "DOB"]
        check(f"the spoken year is inside the DOB span: {said[-40:]}", len(spans) == 1 and said.endswith(spans[0].value.rstrip()),
              f"spans={[s.value for s in spans]}")
        masked = mask_text(said, talk, detector.detect(said))
        check("no digit in the substitute of a spoken date", not any(ch.isdigit() for ch in masked), masked)
        token = talk._conn.execute("SELECT token FROM tokens WHERE entity_type='DOB'").fetchone()[0]  # noqa: SLF001
        fake = _date_canonical(token)
        real_d, real_m, real_y = int(real_iso[8:]), int(real_iso[5:7]), int(real_iso[:4])
        check("the year is kept", fake.endswith(str(real_y)), f"token={token!r}")
        check("the century style of the customer is mirrored", year_words in token, f"token={token!r}")
        fake_md = (int(fake[3:5]), int(fake[:2]))
        check("the same side of today, so the derived age agrees",
              (fake_md < today) == ((real_m, real_d) < today) and fake_md != (real_m, real_d), f"fake={fake} real={real_iso}")
        iso = f"{fake[6:]}-{fake[3:5]}-{fake[:2]}"
        back = json.loads(unmask_arguments(json.dumps({"patient": {"birth_date": iso}}), talk))
        check("the ISO the agent writes resolves to the real ISO", back == {"patient": {"birth_date": real_iso}}, f"{iso} -> {back}")
        check("the prose paraphrase comes back as the real date",
              unmask_text(f"Пациент родился {token}, записал.", talk) == f"Пациент родился {said.split('родил', 1)[-1].split(' ', 1)[-1] if 'родил' in said else said.split('рождения ', 1)[-1]}, записал.",
              unmask_text(f"Пациент родился {token}, записал.", talk))
        check("the spoken substitute is recognised as ours when echoed", talk.is_minted_token(token), token)


def test_tool_result_with_a_future_date_masks(vault: Vault, detector: Detector) -> None:
    """A tool RESULT carries a booking in the future beside a date of birth —
    «slot: 2026-09-10T09:00» next to «birth_date: 1955-09-11» — and the result
    leg must mask it without a sound. `_fake_date` read a variable set only on
    the past-date branch, raised on the future one, the SDK turned the
    exception into a tool error the model read as «техническая ошибка», and
    304 gateway-arm replies on the r2 run of 06.09 said so while every record
    read `done`. The future date keeps its future, the birth date its year."""
    import datetime as _dt
    from pseudex.vault import _date_canonical

    def _as_date(canonical: str) -> _dt.date | None:
        """«dd.mm.yyyy» -> date, или None, если даты нет."""
        try:
            return _dt.datetime.strptime(canonical, "%d.%m.%Y").date()
        except ValueError:
            return None

    # СРАВНИВАЮТСЯ ДАТЫ, А НЕ ГОДЫ. Раньше здесь стояло `int(real[-4:]) >
    # year_now`, и доставка «30.09.2026», назначенная на десять дней вперёд,
    # считалась НЕ будущей только потому, что год совпадает с текущим — после
    # чего от подмены требовали сохранить год, а движок справедливо уводил её
    # в будущее. Граница года и граница «сегодня» — разные границы, и правило
    # продукта («будущая дата остаётся будущей») про вторую.
    today = _dt.date.today()
    for text in (
        '{"appointment_id": "apt-1", "slot": "2026-09-10T09:00:00+03:00", "status": "booked", "patient": {"birth_date": "1955-09-11"}}',
        '{"id": "clm-1", "interval": {"from": "2026-09-10T14:00:00+04:00", "to": "2026-09-10T18:00:00+04:00"}, "address": {"street": "Заречная", "building": "29"}}',
        "доставка 30.09.2026 получатель родился 11.09.1955",
    ):
        talk = Vault(":memory:", "acme").for_conversation("future")
        try:
            masked = mask_text(text, talk, detector.detect(text))
        except Exception as broken:  # noqa: BLE001 — the whole point of the test
            check(f"the result leg does not raise: {text[:40]}…", False, f"{type(broken).__name__}: {broken}")
            continue
        check(f"the result leg does not raise: {text[:40]}…", True)
        for token, original in talk._conn.execute("SELECT token, original FROM tokens WHERE entity_type IN ('DOB','DATE')").fetchall():  # noqa: SLF001
            fake_date, real_date = _as_date(_date_canonical(token)), _as_date(_date_canonical(original))
            if real_date is None or fake_date is None:
                continue
            if real_date > today:
                check(f"a future date stays in the future: {original} → {token}", fake_date > today, token)
            else:
                check(f"a birth date keeps its year: {original} → {token}",
                      fake_date.year == real_date.year, token)


def test_a_mistyped_street_reaches_the_tool_as_the_customer_wrote_it(
        vault: Vault, detector: Detector) -> None:
    """NO REPAIR: the customer's literal address reaches the tool, typo and all.

    «курьера на мончгорская 195» — the gateway used to «fix» the typo to the
    register spelling «Мончегорская» before handing it to the CRM. That was us
    CHANGING the parameter the agent passes, which the product promises never
    to do: correcting the customer's address is the AGENT's business, not the
    gateway's. If the agent wrote it correctly, we mirror that; if it copied
    the customer's typo, the tool gets the typo — the same string it would have
    got without us. `register_spelling` still exists (an opt-in host policy);
    it is no longer applied by default, and the round trip below pins that."""
    import json
    from pseudex.address import register_spelling
    from pseudex.redact import unmask_arguments

    # SEVERAL NEIGHBOURS, BROKEN BY THE REGISTER'S OWN COUNT. «садвая» reaches
    # садовая and садвал, «полвая» reaches полевая and полная: the rule refused
    # every such word and so fired on ONE mistyped street in six on the 06.09
    # live run. Only one candidate may be in the frequent set, and the margins
    # measured are 17 325 to 1, 12 087 to 1 and — at the narrowest — 1 565 to 24.
    for word, want in (("мончгорская", "мончегорская"), ("калашнкова", "калашникова"),
                       ("грибоеодва", "грибоедова"), ("пушшкина", "пушкина"),
                       ("садвая", "садовая"), ("полвая", "полевая"),
                       ("неркасова", "некрасова"), ("чапева", "чапаева"),
                       ("вишёнвая", "вишневая"),
                       # «вишневая» и «вишнёвая» — ОДНО имя в реестре, а не
                       # две возможности: сгруппированы по ё-фолду, иначе
                       # плоская опечатка отвергалась как неоднозначность.
                       ("вишнвая", "вишневая"), ("зелный", "зеленый")):
        check(f"опечатка чинится по реестру: {word}", register_spelling(word) == want,
              f"{word} -> {register_spelling(word)!r}")
    for word in ("мончегорская", "мончегорской", "вишнёвой", "садовой", "чапаевской",
                 "ленина", "улица", "проспект", "лениа", "ленна", "шумайова",
                 # …и те, где запас в реестре 3-10×, а не тысячи: «барышникова»
                 # 6 против «баранникова» 2. Отказ здесь — правильный ответ, а
                 # не предел: курьер, уехавший на Баранникова, хуже ненайденного
                 # адреса.
                 "смльный", "барашникова", "комиссарва",
                 # …and the two the frequency tie-break must NOT touch: a real
                 # rare street spelt correctly is in the register, so the first
                 # signal refuses it before the count is ever consulted.
                 "полная", "садвал"):
        # correct as written, correct but inflected, a type word, a numeral-ish
        # name, and the ambiguous ones — a word one edit from SEVERAL register
        # entries is Fellegi–Sunter's middle outcome and a gateway has no human
        # to refer it to, so it refuses.
        check(f"правильное или неоднозначное не трогается: {word}",
              register_spelling(word) == "", f"{word} -> {register_spelling(word)!r}")
    check("короткое слово не чинится", register_spelling("лена") == "")

    said = "курьера на мончгорская 195 квартира 12 это в мурманск"
    talk = Vault(":memory:", "acme").for_conversation("typo")
    mask_text(said, talk, detector.detect(said))
    token = talk._conn.execute("SELECT token FROM tokens WHERE entity_type='LOC'").fetchone()[0]  # noqa: SLF001
    fake = morph_places.split_roles(token)
    back = json.loads(unmask_arguments(json.dumps(
        {"address": {"street": fake["street"].split()[-1], "building": fake["house"],
                     "sflat": fake.get("flat", "")}}, ensure_ascii=False), talk))
    # ОПЕЧАТКА КЛИЕНТА ДОХОДИТ ДОСЛОВНО, в регистре агента (он написал подмену
    # с заглавной — значит и настоящее слово уходит с заглавной). Никакого
    # «Мончегорская»: содержимое клиента, форма агента, ни одного исправления.
    check("в инструмент уходит написание КЛИЕНТА (опечатка), дом и квартира — тоже",
          back["address"]["street"] == "Мончгорская" and back["address"]["building"] == "195"
          and back["address"]["sflat"] == "12", f"{back}")
    # …AND IN PROSE THE CUSTOMER KEEPS HIS OWN WORDS. Repeating his address
    # back corrected is a different act from filling a form with it.
    check("в прозе — слова клиента", unmask_text(f"Записал: {token}.", talk)
          == "Записал: мончгорская 195 квартира 12.",
          unmask_text(f"Записал: {token}.", talk))

    said = "курьера на мончегорской 195 квартира 12 это в мурманск"
    talk = Vault(":memory:", "acme").for_conversation("ok")
    mask_text(said, talk, detector.detect(said))
    token = talk._conn.execute("SELECT token FROM tokens WHERE entity_type='LOC'").fetchone()[0]  # noqa: SLF001
    fake = morph_places.split_roles(token)
    back = json.loads(unmask_arguments(json.dumps(
        {"address": {"street": fake["street"].split()[-1]}}, ensure_ascii=False), talk))
    check("склонённая правильная улица доходит как написана",
          back["address"]["street"] == "Мончегорской", f"{back}")


def test_address_signature_is_inflection_proof() -> None:
    """Every pool entry must key the same in every case, or restoration misses.

    Checked over the whole leased pool rather than a sample: this is the
    property the round trip rests on, and a single entry that fails it is one
    address type that silently delivers a fake.
    """
    from pseudex.assets import ASSETS
    fakes = ASSETS.get().fakes
    drift = []
    for city in fakes.cities:
        nominative = morph_places.to_nominative(city)
        for case in ("gent", "datv", "loct", "ablt", "accs"):
            inflected = morph_places.inflect_place(nominative, case)
            if morph_places.match_signature(nominative) != morph_places.match_signature(inflected):
                drift.append((nominative, case, inflected))
    for street in fakes.streets:
        phrase = f"улица {morph_places.to_nominative(street)}, 42"
        for case in ("gent", "datv", "loct", "ablt", "accs"):
            inflected = morph_places.inflect_place(phrase, case)
            if morph_places.match_signature(phrase) != morph_places.match_signature(inflected):
                drift.append((phrase, case, inflected))
    check("the address signature survives every case of every pool entry",
          not drift, f"drift={drift[:5]}" if drift else
          f"{(len(fakes.cities) + len(fakes.streets)) * 5} combinations")


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


def test_a_card_address_comes_back_from_free_text(vault: Vault, detector: Detector) -> None:
    """A CRM card stores its address LOWER CASE, and we hand the substitute back
    the same way — then could not read our own output.

    The card comes in as a tool result, so the fields are masked field by field
    and the model is shown «{"street": "ивовая", "house": "125"}». Written back
    into a field of the same name it resolves (`_join_address_fields`). Written
    into a FREE-TEXT address argument — «краснодар, улица ивовая 125, кв. 53»,
    exactly the string the model composes from what it read — it did not, and
    the customer's real address never reached the tool. Found by `long_order`
    on its first run: 18 of 60 cases, every one on `pickup_points_near`.

    THE KEY WAS NEVER THE PROBLEM. `place_key` casefolds, so «улица Ивовая 125»
    and «улица ивовая 125» produce the same key; the SCANNER that proposes the
    window demanded a capital, so for lower case no window was ever offered and
    the key was never asked. The capital is load-bearing in DETECTION, where the
    alternative is the whole language; in RESTORATION the candidate must equal
    one of our own minted tokens, so a window that is not ours costs one indexed
    query that returns nothing."""
    import json
    from pseudex.redact import unmask_arguments

    card = json.dumps({"contacts": [{"id": "c-1", "address": {
        "city": "омск", "street": "солнечная", "house": "104", "flat": "203"}}]}, ensure_ascii=False)
    scoped = vault.for_conversation("conv-card-address")
    spans = detector.detect(card)
    masked = mask_text(card, scoped, spans)
    address = json.loads(masked)["contacts"][0]["address"]
    check("подмена улицы в карточке — строчная, как поле",
          address["street"] == address["street"].lower(), address["street"])
    written = (f"{address['city']}, улица {address['street']} {address['house']}, "
               f"кв. {address['flat']}")
    restored = unmask_arguments(json.dumps({"address": written}, ensure_ascii=False), scoped)
    got = json.loads(restored)["address"]
    check("адрес из карточки, склеенный моделью в строку, восстановлен",
          "солнечная" in got and address["street"] not in got, got)
    # THE LIMIT, NAMED RATHER THAN TESTED. Lower case buys back every form that
    # carries a TYPE WORD, because that is what `LOC_TOKEN_PATTERN` keys on.
    # Without one — «каштановая 98», «омск, каштановая 98» — there is still no
    # window: those reach the vault through `_name_windows`, which proposes only
    # capitalised runs, and widening THAT to any word would offer every
    # one-to-three-word window of a long reply to the vault. It is also the one
    # form `residual_tokens` cannot warn about, for the same reason;
    # `bench/agentpii4/gateway.py::_pieces` carries the matching note. Written
    # down here so the next reader does not rediscover it from a customer.


def test_a_dictated_phone_survives_a_deny_word(vault: Vault, detector: Detector) -> None:
    """«телефон для чека восемь девятьсот шестнадцать…» — a real leak, closed.

    The deny list holds «чек», so a number directly after it is a receipt
    number and not a phone; that rule is right and stays. The rescue beside it
    — a phone cue ANYWHERE in the sentence beats a denying word — was gated on
    the value LOOKING like a phone, and a phone said aloud has no digits to
    look like one. So the cue two words away could not save it and the number
    reached the model in the clear: 15 of 2444 values on `long_bank`'s first
    run, in the one place 54-ФЗ makes a phone mandatory.

    The gate is safe because the span is already typed: only the spoken
    detector produces a digit-free PHONE, and only after the words decode to
    eleven digits opening 7 or 8 followed by 9. Both directions are checked —
    a dictated number behind «чек», «трек» or «заказ» with no phone cue stays
    suppressed, which is what the deny list is for."""
    found = ("телефон для чека восемь девятьсот шестнадцать четыреста два "
             "одиннадцать восемьдесят семь",
             "телефон для связи восемь девятьсот шестнадцать четыреста два "
             "одиннадцать восемьдесят семь")
    for text in found:
        kinds = [span.entity_type for span in detector.detect(text)]
        check(f"продиктованный телефон найден: {text[:26]}…", "PHONE" in kinds, str(kinds))
    quiet = ("чек восемь девятьсот шестнадцать четыреста два одиннадцать восемьдесят семь",
             "трек восемь девятьсот шестнадцать четыреста два одиннадцать восемьдесят семь",
             "заказ восемь девятьсот шестнадцать четыреста два одиннадцать восемьдесят семь")
    for text in quiet:
        kinds = [span.entity_type for span in detector.detect(text)]
        check(f"без подсказки слово-отрицание держит: {text[:18]}…", not kinds, str(kinds))


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    # WITHIN A CONVERSATION, as every production path masks. The LOC substitute
    # is shown in the customer's own form now (lower case, glued markers, no
    # comma — `redact._token_for_text`), and an address the agent copies back
    # verbatim is recovered through the conversation's `shown_forms`; the pattern
    # handles the form a model rewrites it into. Outside a conversation a
    # lower-case copy has no form-independent index to recover it — the same
    # scoping `holds_minted_place`/`shown_forms` already carry.
    vault = Vault(os.path.join(tempfile.mkdtemp(), "hard.db"), "hard-cases").for_conversation("hard")

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
    test_preposition_is_not_a_litera(vault, detector)
    test_the_mirror_shows_nothing_real(detector)
    test_corrected_address_shares_its_street(vault, detector)
    test_a_numbered_street_is_not_a_house(detector)
    test_a_frozen_genitive_street_is_not_an_oblique_case(detector)
    test_an_abbreviation_inside_a_word_opens_no_window(vault, detector)
    test_a_hyphen_glued_substitute_is_two_words(vault, detector)
    test_a_mistyped_street_reaches_the_tool_as_the_customer_wrote_it(vault, detector)
    test_a_card_address_comes_back_from_free_text(vault, detector)
    test_a_dictated_phone_survives_a_deny_word(vault, detector)
    test_spoken_birth_date_keeps_its_register(vault, detector)
    test_tool_result_with_a_future_date_masks(vault, detector)
    test_chat_register(detector)
    test_the_form_belongs_to_the_agent(detector)
    test_the_substitute_keeps_the_house_magnitude(detector)
    test_the_host_may_declare_its_own_values(detector)

    print()
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} — {_FAILURES}")
        return 1
    print("hard cases OK — detected, restored, and nothing over-masked")
    return 0



def test_the_host_may_declare_its_own_values(detector: Detector) -> None:
    """Имя ассистента и адрес компании — не данные субъекта.

    ДВА СЛУЧАЯ, И ОБА ЛОМАЮТ РАЗГОВОР, А НЕ ВОССТАНОВЛЕНИЕ. «Я Татьяна,
    голосовой ассистент» стоит в системном промпте, клиент здоровается —
    «здравствуйте, Татьяна», — и обращение маскируется: модель читает
    приветствие постороннему. Промпт или справочник говорит «мы на Ленина 14»,
    клиент спрашивает «а вы на Ленина 14?» — агент видит «Пушкина 10» и
    отвечает «нет, мы на Ленина 14». Ни одна ось восстановления этого не видит:
    значение доехало бы верно, если бы до инструмента вообще дошло.

    ПУСТОЙ СПИСОК ПО УМОЛЧАНИЮ — вот почему регрессия здесь невозможна по
    построению: пока хост ничего не объявил, ни одна проверка не срабатывает.

    ЦЕНУ ПЛАТИТ ТОТ, КТО ОБЪЯВИЛ, И НЕ ЕГО КЛИЕНТЫ. Квартира, подъезд или
    корпус в упоминании дают другой ключ, поэтому жилец того же дома
    маскируется; ключ имени — именительный одного слова, поэтому «Татьяна
    Смирнова» это другой человек и он маскируется тоже.
    """
    own = ("Татьяна", "Ленина 14")
    keep = ("здравствуйте татьяна", "спасибо татьяне", "а вы на ленина 14?",
            "мы на ул. Ленина, д. 14", "вы находитесь на ленина 14")
    mask = ("запишите клиента петрова ольга телефон 89161234567",
            "клиент татьяна смирнова", "везите на ленина 14 квартира 7",
            "доставка ленина 14 подъезд 3", "курьера на ленина 14 корпус 2")
    for said in keep:
        vault = Vault(":memory:", "acme").for_conversation("own").with_own_values(own)
        got = mask_text(said, vault, detector.detect(said))
        check(f"объявлено хостом — не трогаем: {said[:34]}", got == said, got)
    for said in mask:
        vault = Vault(":memory:", "acme").for_conversation("own").with_own_values(own)
        got = mask_text(said, vault, detector.detect(said))
        check(f"чужое значение маскируется: {said[:34]}", got != said, got)
    # И БЕЗ ОБЪЯВЛЕНИЯ ВСЁ КАК БЫЛО.
    plain = Vault(":memory:", "acme").for_conversation("own")
    said = "здравствуйте татьяна"
    check("без объявления имя маскируется по-прежнему",
          mask_text(said, plain, detector.detect(said)) != said, said)
    print()


def test_the_substitute_keeps_the_house_magnitude(detector: Detector) -> None:
    """Фальшивый дом стоит В ТОМ ЖЕ РАЗРЯДЕ, что настоящий.

    «В дома больше ста не возим» — обычное правило курьерской службы, оно
    живёт в системном промпте заказчика, и настоящий дом 33 под фальшивым 157
    его переворачивает: агент отказывается оформлять заказ, которого никто не
    отменял, и восстановленный ответ противоречит сам себе — «Дом 33 — номер
    больше 100». 12 троек семьи `prompt_rule` на живом прогоне 07.09, в каждой
    плечо шлюза не сделало НИ ОДНОГО вызова.

    ПОВТОРАМИ: номер тянется через `secrets`, и одна чеканка ничего не
    доказывает — разряд может совпасть случайно с вероятностью около трети.
    """
    def band(number: str) -> str:
        value = int(number)
        return "1-9" if value <= 9 else ("10-99" if value <= 99 else "100+")

    for said, want in (("улица мира 4", "1-9"), ("улица солнечная 33", "10-99"),
                       ("улица солнечная 157", "100+"),
                       ("школьная пятьдесят девять", "10-99")):
        bad = []
        for draw in range(30):
            vault = Vault(":memory:", "acme").for_conversation(f"band-{draw}")
            token = vault.tokenize(said, "LOC")
            house = morph_places.house_digits(morph_places.split_roles(token).get("house", ""))
            if not house or band(house) != want:
                bad.append(token)
        check(f"разряд дома сохранён: {said}", not bad, f"{len(bad)} из 30: {bad[:3]}")

    # НАСЕЛЁННЫЙ ПУНКТ ВНУТРИ АДРЕСА И ТАК НАСТОЯЩИЙ, и это уже правило движка
    # (`_settlement_of`), а не то, что надо чинить: почтовый индекс, который
    # агент выводит из города, поэтому совпадает у обоих плеч. Проверяется
    # здесь, чтобы правило нельзя было снять молча.
    vault = Vault(":memory:", "acme").for_conversation("city")
    token = vault.tokenize("Краснодар, улица солнечная 104", "LOC")
    check("город внутри адреса остаётся настоящим",
          token.lower().startswith("краснодар"), token)
    print()


def test_the_form_belongs_to_the_agent(detector: Detector) -> None:
    """Настоящее значение уходит в инструмент В ФОРМЕ, КОТОРОЙ ПОЛЬЗУЕТСЯ АГЕНТ.

    НИ ОДИН КОРПУС ЭТОГО НЕ ВИДИТ, И ЭТО НЕ ФИГУРА РЕЧИ. Скриптовый агент
    копирует подмену дословно, поэтому подмена и настоящее значение приходят в
    одном регистре и расхождения не возникает; а `taxonomy._typed_equal`
    сравнивает значения без учёта регистра, так что даже на живом прогоне ось
    ЗНАЧЕНИЙ этот класс прощает. Он виден только на оси ДОСЛОВНОСТИ и в поле
    заказчика: контроль пишет в CRM «Ким Виктор», плечо шлюза писало «ким
    виктор» — 262 расхождения на прогоне 07.09, задето 217 троек из 834.
    Поэтому правило закреплено ЗДЕСЬ, а не в бенчмарке.
    """
    import json
    from pseudex.redact import unmask_arguments

    said = "запишите ким виктор телефон 89601068867 на ул мичурина 14"

    # ПОВТОРАМИ, А НЕ ОДНОЙ ЧЕКАНКОЙ. Волт тянет подмену через `secrets`, и
    # дефект живёт в НЕКОТОРЫХ парах: строчное «осипов юрий» разваливалось на
    # «ким юрий» (фамилия настоящая, имя — подмена), а «беляев платон» на
    # «ким викторатон» — химера из двух людей. Один прогон это пропускает.
    seen: dict[str, list[str]] = {"title": [], "lower": [], "upper": [], "street": []}
    for draw in range(40):
        talk = Vault(":memory:", "acme").for_conversation(f"form-{draw}")
        mask_text(said, talk, detector.detect(said))
        rows = dict(talk._conn.execute(  # noqa: SLF001
            "SELECT entity_type, token FROM tokens WHERE entity_type IN ('NAME','LOC')").fetchall())
        name, place = rows.get("NAME", ""), rows.get("LOC", "")

        def through(value: str, vault: Vault = talk) -> str:
            return json.loads(unmask_arguments(json.dumps({"x": value}, ensure_ascii=False), vault))["x"]

        if name:
            seen["title"].append(through(name.title()))
            seen["lower"].append(through(name.lower()))
            seen["upper"].append(through(name.upper()))
        if place:
            street = morph_places.split_roles(place).get("street", "").split()[-1]
            seen["street"].append(through(f"ул. {street.title()}, 14"))

    def all_are(key: str, want: str) -> tuple[bool, str]:
        bad = [one for one in seen[key] if one != want]
        return (bool(seen[key]) and not bad), f"{len(bad)} из {len(seen[key])}: {bad[:3]}"

    check("имя с заглавной уходит с заглавной", *all_are("title", "Ким Виктор"))
    check("имя строчными уходит строчными и ЦЕЛИКОМ", *all_are("lower", "ким виктор"))
    # D3: заглавная кириллица не давала НИ ОДНОГО окна, и фамилия уезжала
    # подменой молча — `residual_tokens` строится на тех же окнах.
    check("имя КАПСОМ уходит КАПСОМ, а не подменой", *all_are("upper", "КИМ ВИКТОР"))
    check("родовое слово агента остаётся, название и регистр — тоже",
          *all_are("street", "ул. Мичурина, 14"))
    print()


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
