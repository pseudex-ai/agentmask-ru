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
    for name, take, want in (
        ("серия паспорта", lambda m: " ".join(m.split()[1:3]), "45 09"),
        ("номер паспорта", lambda m: m.split()[3], "123456"),
        ("последние четыре цифры телефона", lambda m: m.split()[5][-4:], "4567"),
        ("первая группа СНИЛС", lambda m: m.split()[7].split("-")[0], "112"),
    ):
        _, _, restored = _round_trip(detector, source, take)
        failures += not _check(name, restored, want)

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
