"""КУСОК ПОДМЕНЫ И ЕЁ ПРОИЗВОДНАЯ В ОТВЕТЕ КЛИЕНТУ.

Живой замер v4 (355 троек): в 59 ответах клиент читал кусок нашей подмены
или её производную как своё — «Верен ли номер дома 74?», хвост карты и
транслит держателя, СНИЛС по цифрам с контрольным числом, «| Латиница |
Tsvetkov Vsevolod |», «инициалы Ж.М.». На пути аргумента всё это
восстанавливалось; в прозе — намеренно нет, потому что «число в прозе —
количество». Здесь закреплено, что ПОДСКАЗКА рядом с числом снимает этот
запрет, что латиница и инициалы восстанавливаются ТОЙ ЖЕ производной
настоящего значения, и что количество остаётся количеством.

    python3 test_prose_fragments.py
"""
import re

import testkit

testkit.load_dev_bundle()

from pseudex import translit  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import mask_text, unmask_text  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

SOURCE = ("клиент Цветков Всеволод Владимирович, адрес Москва, ул. Ленина 14, кв. 5, "
          "карта 4276 1600 1234 5675, снилс 112-233-445 95, паспорт 4509 123456, телефон 8 916 402 11 87")


def _check(label: str, got: str, want: str) -> bool:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        print(f"      получили {got!r}\n      ждали    {want!r}")
    return ok


def main() -> int:
    detector = Detector()
    failures = 0
    vault = Vault(":memory:", "acme").for_conversation("c1")
    masked = mask_text(SOURCE, vault, detector.detect(SOURCE))
    name = re.search(r"клиент (\S+ \S+ \S+),", masked).group(1)  # type: ignore[union-attr]
    house = re.search(r"ул\. \S+ (\d+)", masked).group(1)  # type: ignore[union-attr]
    flat = re.search(r"кв\. (\d+)", masked).group(1)  # type: ignore[union-attr]
    card = re.search(r"карта (\d{4} \d{4} \d{4} \d{4})", masked).group(1)  # type: ignore[union-attr]
    snils = re.search(r"снилс (\d{3}-\d{3}-\d{3} \d\d)", masked).group(1)  # type: ignore[union-attr]
    passport = re.search(r"паспорт (\d{2} ?\d{2} \d{6})", masked).group(1)  # type: ignore[union-attr]
    phone = re.search(r"\+7\d{10}", masked).group()  # type: ignore[union-attr]
    surname, given, patronymic = name.split()
    latin = " ".join(translit.apply(translit.ICAO, w).capitalize() for w in (surname, given))
    snils_digits = re.sub(r"\D", "", snils)

    for label, text, want in (
        ("номер дома с подсказкой", f"Верен ли номер дома {house}?", "Верен ли номер дома 14?"),
        ("квартира с подсказкой", f"квартира {flat}, подтверждаете?", "квартира 5, подтверждаете?"),
        ("хвост карты и транслит держателя", f"**** **** **** {card[-4:]} ({latin.upper()}), 07/2030",
         "**** **** **** 5675 (TSVETKOV VSEVOLOD), 07/2030"),
        ("СНИЛС по цифрам и контрольное число",
         f"Цифры: {' '.join(snils_digits[:9])}, контрольное число: {snils[-2:]}",
         "Цифры: 1 1 2 2 3 3 4 4 5, контрольное число: 95"),
        ("латиница в сводке", f"| Латиница | {latin} |", "| Латиница | Tsvetkov Vsevolod |"),
        ("инициалы", f"инициалы {given[0]}.{patronymic[0]}.", "инициалы В.В."),
        ("серия паспорта", f"серия {passport.replace(' ', '')[:4]}", "серия 4509"),
        ("последние цифры телефона", f"последние четыре цифры телефона {phone[-4:]}",
         "последние четыре цифры телефона 1187"),
        # --- а количество остаётся количеством ---
        ("количество коробок", "доставим 12 коробок", "доставим 12 коробок"),
        ("время и слово «дом» без числа", "встреча в 15:00, дом сдан", "встреча в 15:00, дом сдан"),
        ("числа в прозе", "осталось 90 штук и ещё 71", "осталось 90 штук и ещё 71"),
        ("чужое латинское слово", "заказ через Ozon доставлен", "заказ через Ozon доставлен"),
    ):
        failures += not _check(label, unmask_text(text, vault), want)
    print()
    if failures:
        print(f"НЕ ПРОШЛО: {failures}")
        return 1
    print("кусок и производная подмены в прозе возвращаются настоящим значением")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
