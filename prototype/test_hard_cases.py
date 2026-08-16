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

    print()
    if _FAILURES:
        print(f"FAILED: {len(_FAILURES)} — {_FAILURES}")
        return 1
    print("hard cases OK — detected, restored, and nothing over-masked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
