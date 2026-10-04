"""Coverage checklist for the personal-data types 152-ФЗ actually cares about.

Recall on our own generated datasets does not answer "do you cover everything?" —
those datasets only contain what we thought to generate. This file is the
explicit inventory instead: one line per document type, asserted in both
directions.

BOTH DIRECTIONS MATTER, AND FOR DIFFERENT REASONS:
  caught      a missed type is a leak, and a silent one
  typed right a type is not cosmetic. The token is rendered per type, so a
              driver's licence detected as PHONE is replaced with a fake phone
              number — the model then reads a phone where a document belongs and
              the customer's own validator rejects it. This is how the
              `cardholder_name` -> CARD defect surfaced in production data.
  not over-masked
              a version string, an order number or a tracking code must survive
              untouched, or we break the tool call we exist to protect.

The digit shapes of a driver's licence, a vehicle registration and a passport are
IDENTICAL (`NN NN NNNNNN`), so those types are separated by their cue word, not
by their shape. That is why each case here carries realistic surrounding text
rather than a bare number.

Run: python3 test_coverage_152fz.py
"""

from pseudex.detect_all import Detector
from testkit import load_dev_bundle

# (text as a user would actually write it, expected entity type)
_MUST_CATCH: tuple[tuple[str, str], ...] = (
    ("мой телефон +7 999 123-45-67", "PHONE"),
    ("почта ivan@mail.ru", "EMAIL"),
    ("меня зовут Иван Петров", "NAME"),
    ("доставьте на улицу Ленина 5, кв 12", "LOC"),
    ("СНИЛС 112-233-445 95", "SNILS"),
    ("ИНН 500100732259", "INN"),
    ("карта 4111 1111 1111 1111", "CARD"),
    ("паспорт 45 09 123456", "PASSPORT"),
    # ДАТА В КОНТЕКСТЕ РОЖДЕНИЯ — ЭТО DOB, А НЕ DATE, с 31.08: тип, у которого
    # отняли «рождение», потерял ровно то, что делает его персональным, и
    # маскировался тогда один только год. Метка здесь осталась от времени, когда
    # типа DOB не было, — тот же недосмотр, что был исправлен в генераторах
    # golden и dirty и не доехал до этого файла.
    ("дата рождения 12.03.1985", "DOB"),
    ("родился 7 июля 1988", "DOB"),
    ("клиенту 95 лет", "AGE"),
    ("диагноз сахарный диабет", "MEDICAL"),
    # THE EXPECTED STRINGS ARE THE v6 REGISTRY IDS (G7, 02.10.2026). The five
    # rows below used to name the v5-internal labels the engine emitted; the span
    # now carries the id the registry and the benchmark name, and
    # `ru_pii_v6.engine_label` hands the old spelling back to the vault. The
    # VALUES are unchanged and every one is still masked whole — the assertion's
    # logic is untouched, only the label it compares against.
    ("полис ОМС 7712345678901234", "OMS_ENP"),
    ("водительское удостоверение 99 12 345678", "DRIVER_LICENSE"),
    ("СТС 99 12 345678", "STS_NUMBER"),
    ("гос номер А123ВЕ777", "PLATE"),
    ("машина х456ор69", "PLATE"),
    ("счёт 40817810099910004312", "BANK_ACCOUNT"),
    # ОГРНИП only. The thirteen-digit ОГРН is on the other list — see there.
    ("ОГРНИП 304500116000157", "OGRNIP"),
    ("загранпаспорт 750123456", "INTL_PASSPORT"),
    ("подключался с IP 192.168.14.203", "IP_ADDRESS"),
    ("свидетельство о рождении II-МЮ №123456", "BIRTH_CERT"),
)

# Non-personal data that shares a shape with something above.
_MUST_NOT_MASK: tuple[str, ...] = (
    # A LEGAL PERSON HAS NO DATA SUBJECT. This test used to demand the opposite,
    # and the demand was wrong rather than merely outdated: 152-ФЗ ст. 3 п. 1
    # defines personal data through a физическое лицо, and GDPR Recital 14
    # excludes data of legal persons in as many words. Masking a company's
    # registration number broke the customer's own document flow — an agent
    # looking a counterparty up by ОГРН got a FAKE one and found nothing — to
    # protect something the law does not protect.
    #
    # The valid checksum is what makes this a real assertion: a shape test would
    # pass on any thirteen digits, while this is a number the recognizer would
    # have accepted before. ОГРНИП above stays, because an individual
    # entrepreneur IS a natural person.
    "ОГРН 1027700132195",
    "заказ 1234567890123",
    "трек 40817810099910004399123",
    "версия 1.2.3.4 сборки",
    "артикул 7712345678901299",
    "сумма 4276380012345678 копеек не бывает",
    "доставьте 15 марта",
    "встреча 20 июня в 14:00",
)


def main() -> None:
    load_dev_bundle()
    detector = Detector()
    missed: list[str] = []
    for text, expected in _MUST_CATCH:
        found = [span.entity_type for span in detector.detect(text)]
        if expected not in found:
            missed.append(f"{expected}: {text!r} -> {found}")

    over: list[str] = []
    for text in _MUST_NOT_MASK:
        found = [(span.entity_type, span.value) for span in detector.detect(text)]
        if found:
            over.append(f"{text!r} -> {found}")

    for line in missed:
        print(f"MISSED    {line}")
    for line in over:
        print(f"OVER-MASK {line}")
    assert not missed, f"{len(missed)} personal-data types not caught or mistyped"
    assert not over, f"{len(over)} non-personal values were masked"
    print(f"152-ФЗ coverage OK — {len(_MUST_CATCH)} types caught and typed correctly, "
          f"{len(_MUST_NOT_MASK)} look-alikes left untouched")


if __name__ == "__main__":
    main()
