"""ФОРМА АРГУМЕНТА ПРИНАДЛЕЖИТ АГЕНТУ, А СОДЕРЖИМОЕ — ВОЛТУ.

Схема инструмента вправе просить меньше, чем мы подменили: улицу и дом без
подъезда, серию паспорта без номера, последние четыре цифры телефона, одну
фамилию. Раньше на такой запрос шлюз отвечал тремя разными неправильными
способами — возвращал значение целиком, возвращал его В СВОЕЙ форме, или не
разрешал кусок вовсе и отдавал инструменту ПОДМЕНУ. Последнее — тихий отказ:
JSON корректен, код 200, список остатков пуст.

Здесь закреплены обе стороны правила: настоящее значение обязано дойти, и форма
агента обязана уцелеть. Обратное направление тоже: то, что полем схемы не
является — количество, число в прозе, — трогать нельзя.
"""
import json
import re

import testkit

testkit.load_dev_bundle()

from pseudex.detect_all import Detector          # noqa: E402
from pseudex.redact import mask_text, unmask_arguments, unmask_text  # noqa: E402
from pseudex.vault import Vault                  # noqa: E402


def _round_trip(detector, source, take):
    """Замаскировать, дать агенту взять КУСОК подмены, восстановить в аргументе."""
    vault = Vault(":memory:", "acme").for_conversation("c1")
    masked = mask_text(source, vault, detector.detect(source))
    written = take(masked)
    restored = json.loads(unmask_arguments(
        json.dumps({"field": written}, ensure_ascii=False), vault))["field"]
    return masked, written, restored


def _check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      получили {got!r}\n      ждали    {want!r}")
    return ok


def main() -> int:
    detector = Detector()
    failures = 0

    # --- адрес: агент берёт меньше, чем мы подменили ------------------------
    source = "улица Ленина 14 кв 5"
    _, written, restored = _round_trip(
        detector, source, lambda m: m.split(",")[0])
    failures += not _check("улица и дом без квартиры", restored, "улица Ленина 14")

    _, written, restored = _round_trip(
        detector, source, lambda m: m.split()[1])
    failures += not _check("одно название улицы", restored, "Ленина")

    # Форма агента: сокращения и маркеры его, значения наши.
    vault = Vault(":memory:", "acme").for_conversation("c1")
    masked = mask_text(source, vault, detector.detect(source))
    street, house = masked.split()[1], masked.split()[2].rstrip(",")
    rewritten = f"ул. {street}, д. {house}, кв. {masked.split()[-1]}"
    restored = json.loads(unmask_arguments(
        json.dumps({"a": rewritten}, ensure_ascii=False), vault))["a"]
    failures += not _check("маркеры и сокращения агента", restored,
                           "ул. Ленина, д. 14, кв. 5")

    # --- числовые части -----------------------------------------------------
    source = "паспорт 4509 123456 телефон +79261234567 снилс 112-233-445 95"
    # Tokens are found by SHAPE, not by word index: the passport fake is minted
    # as «4509 123456» or «45 09 123456» at random, and an index into `split()`
    # made this check flaky.
    def passport(m: str) -> str:
        return re.search(r"\d{2} ?\d{2} \d{6}", m).group()  # type: ignore[union-attr]

    for name, take, want in (
        ("серия паспорта", lambda m: " ".join(passport(m).replace(" ", "")[i:i + 2] for i in (0, 2)), "45 09"),
        ("номер паспорта", lambda m: passport(m)[-6:], "123456"),
        ("последние четыре цифры телефона", lambda m: re.search(r"\+7\d{10}", m).group()[-4:], "4567"),  # type: ignore[union-attr]
        ("первая группа СНИЛС", lambda m: re.search(r"\d{3}-\d{3}-\d{3} \d{2}", m).group()[:3], "112"),  # type: ignore[union-attr]
    ):
        _, _, restored = _round_trip(detector, source, take)
        failures += not _check(name, restored, want)

    # --- адрес, разложенный по ВЛОЖЕННЫМ полям ------------------------------
    # Схема CRM просит `contact.address.street`, а не `street` на верхнем уровне.
    # Сборка адреса из кусков смотрела только на верхний уровень, и улица
    # уезжала в инструмент подменой — с кодом 200 и пустым списком остатков.
    source = "живу: Москва, ул. Ленина 14, кв. 5"
    vault = Vault(":memory:", "acme").for_conversation("c1")
    masked = mask_text(source, vault, detector.detect(source))
    fake = masked.split(": ", 1)[1]
    fake_street = fake.split(",")[1].split()[-2] if "ул." in fake else fake.split(",")[1].split()[-2]
    fake_house = fake.split(",")[1].split()[-1]
    nested = json.loads(unmask_arguments(json.dumps(
        {"contact": {"name": "x", "address": {"city": fake.split(",")[0], "street": fake_street,
                                               "house": fake_house}}}, ensure_ascii=False), vault))
    failures += not _check("улица во вложенном объекте", nested["contact"]["address"]["street"],
                           "Ленина")
    failures += not _check("дом во вложенном объекте", nested["contact"]["address"]["house"], "14")

    # --- число целиком, в форме агента --------------------------------------
    # Подмена телефона уходит к модели как «+7…»; модель пишет её дословно, как
    # «8 (…) …-..-..» или десятью голыми цифрами — потому что так просит её
    # схема. Обратно обязаны прийти НАСТОЯЩИЕ цифры в ЕЁ форме, а не в той, в
    # которой клиент когда-то написал номер.
    source = "телефон 8 916 402 11 87, паспорт 45 09 123456, родился 21.09.1955"
    vault = Vault(":memory:", "acme").for_conversation("c1")
    masked = mask_text(source, vault, detector.detect(source))
    fake_phone = re.search(r"\+7\d{10}", masked).group()  # type: ignore[union-attr]
    ten = fake_phone[2:]
    fake_date = re.search(r"\d{2}\.\d{2}\.\d{4}", masked).group()  # type: ignore[union-attr]
    for name, written, want in (
        ("телефон дословно, E.164", fake_phone, "+79164021187"),
        ("телефон через 8 со скобками", f"8 ({ten[:3]}) {ten[3:6]}-{ten[6:8]}-{ten[8:]}",
         "8 (916) 402-11-87"),
        ("телефон десятью цифрами", ten, "9164021187"),
        ("телефон +7 с пробелами", f"+7 {ten[:3]} {ten[3:6]} {ten[6:]}", "+7 916 402 1187"),
        ("дата в ISO", f"{fake_date[6:]}-{fake_date[3:5]}-{fake_date[:2]}", "1955-09-21"),
        ("дата дословно", fake_date, "21.09.1955"),
    ):
        restored = json.loads(unmask_arguments(
            json.dumps({"v": written}, ensure_ascii=False), vault))["v"]
        failures += not _check(name, restored, want)
    prose = unmask_text(f"перезвоним на {fake_phone}", vault)
    failures += not _check("в прозе — как написал клиент", prose,
                           "перезвоним на 8 916 402 11 87")

    # --- фамилия, которой морфология не знает, перед известным именем -------
    # «миллер валерий» читалось как (имя, фамилия): подмена чеканилась в том же
    # порядке, и `last_name` получал «валерий». Форма читается по документному
    # порядку, пара фейк↔настоящее позиционна по построению.
    for source, want_last, want_first in (("это миллер валерий, телефон 8 916 402 11 87", "миллер", "валерий"),
                                          ("это ерохин пётр николаевич", "ерохин", "пётр")):
        vault = Vault(":memory:", "acme").for_conversation("c1")
        masked = mask_text(source, vault, detector.detect(source))
        fake = re.search(r"это ([А-ЯЁ][а-яё]+) ([А-ЯЁ][а-яё]+)", masked)
        restored = json.loads(unmask_arguments(json.dumps(
            {"last_name": fake.group(1), "first_name": fake.group(2)}, ensure_ascii=False), vault))  # type: ignore[union-attr]
        failures += not _check(f"фамилия перед именем: {source.split()[1]}", restored,
                               {"last_name": want_last, "first_name": want_first})

    # --- имя: агент берёт одну часть ---------------------------------------
    source = "Иванов Пётр Сергеевич"
    for name, index, want in (("одна фамилия", 0, "Иванов"),
                              ("одно имя", 1, "Пётр")):
        _, _, restored = _round_trip(detector, source, lambda m, i=index: m.split()[i])
        failures += not _check(name, restored, want)

    # --- то, что полем схемы не является, трогать нельзя --------------------
    vault = Vault(":memory:", "acme").for_conversation("c1")
    source = "паспорт 4509 123456"
    mask_text(source, vault, detector.detect(source))
    quantities = json.loads(unmask_arguments(
        json.dumps({"count": "12", "qty": "5"}, ensure_ascii=False), vault))
    failures += not _check("количество остаётся количеством", quantities,
                           {"count": "12", "qty": "5"})
    prose = unmask_text("осталось 90 штук и ещё 71", vault)
    failures += not _check("число в прозе не подменяется", prose,
                           "осталось 90 штук и ещё 71")

    print()
    if failures:
        print(f"НЕ ПРОШЛО: {failures}")
        return 1
    print("форма аргумента принадлежит агенту, содержимое — волту")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
