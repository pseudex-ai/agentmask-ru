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


def _substitute_of(masked: str, source: str, pattern: str) -> str:
    """The substitute standing where the customer's value stood."""
    match = re.search(pattern, masked)
    assert match is not None, (source, masked, pattern)
    return match.group()


def _forms_follow(detector) -> bool:
    """One case per type: the substitute is written like the customer wrote the
    value (form IN), and the tool receives the value written like the AGENT
    wrote the substitute (form OUT) — verbatim, re-cased, re-inflected,
    re-ordered, re-notated. Every «want» is what an agent WITHOUT the gateway
    would have passed, given the same rewriting habit."""
    ok = True
    # (source, regex for the substitute in the masked text, [(agent's rewrite of the substitute, expected at the tool)])
    cases = [
        # NAME — lower case in, lower case out; the agent's case and order
        ("заказ на игорь анфалов, тел 89162148803", r"(?<=заказ на )[а-яё]+ [а-яё]+",
         [(lambda t: t, "игорь анфалов"), (lambda t: t.upper(), "ИГОРЬ АНФАЛОВ"),
          (lambda t: " ".join(w.capitalize() for w in t.split()), "Игорь Анфалов")]),
        # NAME — the customer's oblique case and surname-first order, copied verbatim
        ("пиши на есина рушана номер +79720652255", r"(?<=пиши на )[а-яё]+ [а-яё]+",
         [(lambda t: t, "есина рушана")]),
        # NAME — Title case in, Title case out; the agent inflects → so does the real name
        ("Клиент Игорь Анфалов ждёт звонка", r"(?<=Клиент )[А-ЯЁ][а-яё]+ [А-ЯЁ][а-яё]+",
         [(lambda t: t, "Игорь Анфалов")]),
        # DOB — month in words in, month in words out; ISO from the agent → ISO
        ("др 2 июня 1975, клиент мая одинцова", r"\d{1,2} [а-яё]+ \d{4}",
         [(lambda t: t, "2 июня 1975"), (lambda t: _iso(t), "1975-06-02")]),
        # DOB — the customer's short notation, kept; the agent's dotted form → dotted
        ("дата рождения 10.4.82, зовут ольга", r"\d{1,2}\.\d{1,2}\.\d{2}",
         [(lambda t: t, "10.4.82")]),
        # PASSPORT — the customer's grouping, not the register's
        ("паспорт 4509 123456", r"\d{4} \d{6}",
         [(lambda t: t, "4509 123456"), (lambda t: t.replace(" ", ""), "4509123456")]),
        # SNILS — bare digits in, bare out; dashed from the agent → dashed
        ("снилс 11223344595", r"(?<=снилс )\d{11}",
         [(lambda t: t, "11223344595"), (lambda t: f"{t[:3]}-{t[3:6]}-{t[6:9]} {t[9:]}", "112-233-445 95")]),
        # CARD — spaced in, spaced out; dashes from the agent → dashes
        ("карта 4276 1600 1234 5675", r"\d{4} \d{4} \d{4} \d{4}",
         [(lambda t: t, "4276 1600 1234 5675"), (lambda t: t.replace(" ", "-"), "4276-1600-1234-5675")]),
        # PHONE — the customer's form in; the agent's rewrite out
        ("тел 8 (916) 214-88-03", r"8 \(\d{3}\) \d{3}-\d{2}-\d{2}",
         [(lambda t: t, "8 (916) 214-88-03"), (lambda t: "+7" + re.sub(r"\D", "", t)[1:], "+79162148803")]),
        # EMAIL — the agent's letter case
        ("почта ivan.petrov@mail.ru", r"[a-z]{8}@example\.ru",
         [(lambda t: t, "ivan.petrov@mail.ru"), (lambda t: t.upper(), "IVAN.PETROV@MAIL.RU")]),
        # PLATE — Latin look-alikes and lower case from the agent still resolve, in its case
        ("номер А123ВС77", r"[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}",
         [(lambda t: t, "А123ВС77"), (lambda t: t.lower(), "а123вс77")]),
    ]
    for source, pattern, rewrites in cases:
        vault = Vault(":memory:", "acme").for_conversation("c1")
        masked = mask_text(source, vault, detector.detect(source))
        token = _substitute_of(masked, source, pattern)
        for rewrite, want in rewrites:
            written = rewrite(token)
            got = json.loads(unmask_arguments(json.dumps({"field": written}, ensure_ascii=False), vault))["field"]
            ok &= _check(f"форма: {source[:32]} ← агент написал {written!r}", got, want)
    return ok


def _verbatim_is_literal(detector) -> bool:
    """AN AGENT THAT COPIES GETS THE CUSTOMER'S STRING BACK, CHARACTER FOR
    CHARACTER — the Latin «a» inside «бaбичев», the Cyrillic «О» inside
    «682О 8116», the address with no street word. That is exactly what it
    would have passed without us. The vault remembers what this dialogue was
    shown (`shown_forms`); the verbatim pass puts the literal back before any
    form is rebuilt. 39 of the 56 «repaired» values on the public benchmark
    were look-alike letters we had folded; 12 were addresses we had dressed
    with «улицы»."""
    ok = True
    # An address counts only when the customer wrote the street word himself
    # («ул. Заболоцкого 81 кв 51»): for a bare «заболоцкого 81» the substitute
    # still adds «улица» on the way in — the open half of Б24 — and an agent
    # that copies it is copying a shape the customer did not write.
    for said in (
        "заказ на антон бaбичев, адрес ул. Заболоцкого 81 кв 51, карта 2200 6638 682О 8116",
        "снилс 618 318 3О1 82, паспорт 5021 675О54, тел 8 972 58О2333",
        "пиши на есина рушана номер +79720652255, др 2 июня 1975",
    ):
        vault = Vault(":memory:", "acme").for_conversation("c1")
        masked = mask_text(said, vault, detector.detect(said))
        assert masked != said, said
        back = json.loads(unmask_arguments(json.dumps({"field": masked}, ensure_ascii=False), vault))["field"]
        ok &= _check(f"дословно: {said[:40]}…", back, said)
        prose = unmask_text("Записал: " + masked, vault)
        ok &= _check(f"дословно в прозе: {said[:40]}…", prose, "Записал: " + said)
    return ok


def _iso(worded: str) -> str:
    """«19 июля 1975» → «1975-07-19», the way an agent rewrites a date for a `date` field."""
    from pseudex.vault import _date_canonical  # noqa: PLC0415
    day, month, year = _date_canonical(worded).split(".")
    return f"{year}-{month}-{day}"


def _check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      получили {got!r}\n      ждали    {want!r}")
    return ok


def main() -> int:
    detector = Detector()
    failures = 0

    # --- адрес: агент берёт меньше, чем мы подменили ------------------------
    source = "улица Ленина 14 кв 5"
    # Агент отбрасывает квартиру. Раньше это делалось через `split(",")[0]`, но
    # подмена теперь ЗЕРКАЛИТ форму клиента: он написал «кв 5» без запятой, и
    # запятой в подмене больше нет — поэтому квартира снимается по маркеру, не по
    # запятой (это и есть правильное поведение — форма клиента дословно).
    _, written, restored = _round_trip(
        detector, source, lambda m: re.sub(r"\s*,?\s*кв\.?\s*\d+.*$", "", m))
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
    # The substitute is written the customer's way (vault `_digits_in_customer_
    # form`); the agent's forms below are built from its digits.
    ten = re.sub(r"\D", "", re.search(r"\+?\d[\d\s()\-]{8,}\d", masked).group())[-10:]  # type: ignore[union-attr]
    fake_phone = "+7" + ten
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
    # РЕГИСТР ТЕПЕРЬ ТОЖЕ ЗЕРКАЛИТСЯ НА ВХОДЕ: клиент написал строчными, подмена
    # чеканится строчными, агент копирует её как есть, и настоящее имя уходит в
    # ЕГО регистре — то есть строчными. Раньше подмена шла с заглавной и этот
    # тест ждал «Миллер»: форму менял не агент, а мы, на плече маскирования.
    # Проверяется ПОРЯДОК частей — и регистр, потому что он теперь агентский.
    for source, want_last, want_first in (("это миллер валерий, телефон 8 916 402 11 87", "миллер", "валерий"),
                                          ("это ерохин пётр николаевич", "ерохин", "пётр")):
        vault = Vault(":memory:", "acme").for_conversation("c1")
        masked = mask_text(source, vault, detector.detect(source))
        fake = re.search(r"это ([а-яё]+) ([а-яё]+)", masked)
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

    # --- ФОРМА, ТИП ЗА ТИПОМ, В ОБЕ СТОРОНЫ ---------------------------------
    # На входе подмена зеркалит форму КЛИЕНТА (падеж, регистр, порядок,
    # нотация даты, группировка цифр), на выходе настоящее значение принимает
    # форму АГЕНТА. Каждая строка ниже — то, что публичный бенчмарк на 0.3.16
    # показал как «вернулось починенным» или как фейк в инструменте: 78 + 15
    # значений, форму которых на одном из плеч менял не агент, а мы.
    failures += not _forms_follow(detector)
    failures += not _verbatim_is_literal(detector)

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
