"""Класс Г — утечки: пять векторов, пять массовых правил.

Свидетели: g06 `sequential_chain:tracker-004/005/006`, g08 `mailfind-000/003`,
g09 `document-027…-048` (24 утечки, форма PASSPORT 0/22), g04 `long_order-027`,
g12 `fanout_pick-020`, g15 `document:office-001/003`, g07 `rag-008`.
Разбор механизма — `research/hop-format-audit/SPIKE-Г.md`; решение владельца по
развилке — `DECISIONS-SPRINT.md` §Класс Г.

Self-contained: без LLM и без сети, грузит bundle из исходников и гоняет
НАСТОЯЩИЙ `Detector`/`Vault`/`redact`. Тест не привязан ни к одному кейсу:
вектор 1 требует ЛЮБОЙ порядок слов латинского имени, вектор 2 — замаскированное
слово (любым типом), вектор 3 — закрытые листья любого типизированного объекта,
вектор 4 — отказ сторожа чеканки на целом слове настоящего значения, вектор 5 —
телефон, победивший по ГРАНИЦЕ.

    python3 test_class_g_leaks.py
"""

import sys
import tempfile

import testkit

testkit.load_dev_bundle()

from pseudex import redact                                       # noqa: E402
from pseudex import names                                        # noqa: E402
from pseudex.assets import ASSETS                                # noqa: E402
from pseudex.detect_all import Detector                          # noqa: E402
from pseudex.ru_pii import validate_snils                        # noqa: E402
from pseudex.structured import detect_structured_kv              # noqa: E402
from pseudex.vault import Vault                                  # noqa: E402

DET = Detector()
RESULTS: list[tuple[bool, str, str]] = []
_CYRILLIC = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя")


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def spans(text: str) -> list[tuple[int, int, str, str]]:
    return [(s.start, s.end, s.entity_type, s.value) for s in DET.detect(text)]


def covered(text: str, needle: str, kind: str | None = None) -> list[tuple[int, int, str, str]]:
    low = needle.lower()
    return [s for s in spans(text)
            if low in text[s[0]:s[1]].lower() and (kind is None or s[2] == kind)]


def vault_in(td: str, customer: str, conversation: str = "class-g") -> Vault:
    return Vault(f"{td}/v.db", customer).for_conversation(conversation)


# ---------------------------------------------------------------------------
# ВЕКТОР 1. Полулатница: латинское имя судится СЛОВОМ, а не позицией в прогоне.
# Корень: `names.gazetteer_names` принимал латинский прогон лишь когда ПЕРВОЕ
# слово — известное имя, а `assets._build_names` транслитерировал только семя
# (641 запись), не `dict_surnames` (196 800). Движок знает «Кукушкин» и не
# узнаёт `Kukushkin` — свидетельство лежит не там, где его ищут.
# ---------------------------------------------------------------------------
def vector_1() -> None:
    print("\nВЕКТОР 1. Полулатница (позиция не важна, скрипт зеркалится)")
    # КАЖДОЕ латинское имя прогона обязано быть закрыто — в любом порядке.
    probes = (
        '"displayName": "Kukushkin Valeriy"',
        "Kukushkin Valeriy",
        "Valeriy Kukushkin",
        "Fomin Vyacheslav",
        "Kukushkin",
        "Evgeniy Volnov",
        "Kukushkin Valeriy Ivanovich",
    )
    for text in probes:
        found = spans(text)
        words = [w.strip('":,') for w in text.split()]
        leaked = [w for w in words
                  if len(w) > 3 and w[:1].isupper() and w.isascii() and w.isalpha()
                  and not covered(text, w, "NAME")]
        check(not leaked, f"1a латиница закрыта: {text!r}",
              f"не закрыты: {leaked}" + (f"; спаны={found}" if leaked else ""))

    # ЗЕРКАЛИРОВАНИЕ СКРИПТА И ОБРАТНЫЙ ПУТЬ: латинскому настоящему — латинская
    # подмена, и она же обязана разрешаться (иначе вылечим утечку — получим
    # утечку подмены: инструмент получит фейк).
    with tempfile.TemporaryDirectory() as td:
        vault = vault_in(td, "g1")
        for real in ("Evgeniy Volnov", "Kukushkin Valeriy"):
            fake = vault.tokenize(real, "NAME")
            mirrored = not (set(fake.lower()) & _CYRILLIC)
            check(mirrored, f"1b скрипт зеркален: {real!r}", f"подмена {fake!r}")
            check(vault.is_minted_token(fake),
                  f"1c подмена разрешается: {real!r} -> {fake!r}",
                  f"detokenize={vault.detokenize(fake)!r}")

    # ЯВНО, А НЕ ТОЛЬКО ЧЕРЕЗ ДЕТЕКТОР: движок ЗНАЕТ латинскую фамилию, то
    # есть свидетельство лежит в том же словаре, прочитанном тем же столом.
    check("Kukushkin" not in names.ASSETS.get().names.name_set
          and "kukushkin" in names.ASSETS.get().names.latin_surnames,
          "1e латинская фамилия есть в словаре, хотя её нет в семени",
          "dict_surnames \u2192 latin_surnames")
    check(names.is_surname_shaped("\u0430\u043b\u0435\u043d\u0447\u0438\u0435\u0432"),
          "1f форма фамилии читается без словаря", "\u0430\u043b\u0435\u043d\u0447\u0438\u0435\u0432")

    # ГЕЙТ ОТ ОВЕРМАСКИРОВАНИЯ: латинское слово внутри почты/URL/пути — не имя.
    for text, needle in (
            ("пишите на sokolov@example.com", "sokolov"),
            ("открой /tmp/kuznetsov/report.pdf", "kuznetsov"),
            ("зайди на https://sokolov.ru/catalog", "sokolov"),
    ):
        inside = [s for s in spans(text) if s[2] == "NAME"
                  and needle in text[s[0]:s[1]].lower()]
        check(not inside, f"1d латиница не имя в не-имени: {text!r}", str(spans(text)))


# ---------------------------------------------------------------------------
# ВЕКТОР 2. Голое слово в нижнем регистре: роль решает ЯКОРЬ, а не только
# заглавная. Свидетели: «адрес репина» (LOC), «от аленчиев» (NAME),
# «на бибиревская» (LOC). Якорь в коде уже есть — он умел только ЗАПРЕЩАТЬ.
# ---------------------------------------------------------------------------
def vector_2() -> None:
    print("\nВЕКТОР 2. Голое слово после адресного/персонального якоря")
    witnesses = (
        ("Мой телефон +79164021187, адрес репина, дата рождения 1987-03-14", "репина", "LOC"),
        ("поищите в почте письмо от аленчиев", "аленчиев", "NAME"),
        ("доставка была на бибиревская", "бибиревская", "LOC"),
        ("перезвоните к аленчиеву сегодня", "аленчиеву", "NAME"),
    )
    for text, needle, kind in witnesses:
        hits = covered(text, needle)
        right = [h for h in hits if h[2] == kind]
        check(bool(hits) and bool(right), f"2a {needle!r} -> {kind}",
              f"спаны={spans(text)}")

    check(names.ASSETS.get().names.anchor_re.search("\u043f\u0438\u0441\u044c\u043c\u043e \u043e\u0442 ") is not None,
          "2c \u043f\u0440\u0435\u0434\u043b\u043e\u0433-\u044f\u043a\u043e\u0440\u044c \u0430\u0440\u0435\u043d\u0434\u043e\u0432\u0430\u043d \u0438 \u0441\u043a\u043e\u043c\u043f\u0438\u043b\u0438\u0440\u043e\u0432\u0430\u043d",
          str(names.ASSETS.get().names.anchor_preps))

    # НЕГАТИВЫ ИЗМЕРЕНЫ, А НЕ ВЫДУМАНЫ: они уже стоят в корпусах как ложные
    # срабатывания строчных адресных веток, и ни один не имеет ни адресного
    # якоря, ни предлога ВПЛОТНУЮ.
    negatives = (
        "14 марта ему исполнилось 60",
        "в конце марта 55",
        "в виде лишения свободы 2",
        "на 8 марта 5 подарков",
        "счёт 1234 от 15.05.2025 оплачен",
    )
    for text in negatives:
        check(not spans(text), f"2b негатив не тронут: {text!r}", str(spans(text)))


# ---------------------------------------------------------------------------
# ВЕКТОР 3. Вложенный объект: РОДИТЕЛЬСКИЙ ключ типизирует детей — правило уже
# работает для `address` и жёстко привязано к LOC. `{"passport": {"series",
# "number"}}` не типизируется вовсе: 4 и 6 цифр без контрольной суммы.
# ---------------------------------------------------------------------------
V3_PAYLOAD = ('{"last_name": "громова", "first_name": "ольга", '
              '"passport": {"series": "4608", "number": "246256"}, '
              '"snils": "760-451-105 71", '
              '"address": {"city": "уфа", "street": "сиреневая", "house": "72", "flat": "33"}}')


def vector_3() -> None:
    print("\nВЕКТОР 3. Вложенный passport.{series,number}")
    found = spans(V3_PAYLOAD)
    for leaf in ("4608", "246256"):
        hits = [s for s in found if V3_PAYLOAD[s[0]:s[1]] == leaf]
        check(bool(hits) and hits[0][2] == "PASSPORT",
              f"3a лист {leaf} закрыт как PASSPORT", f"спаны={found}")
    kv = [(s.start, s.end, s.entity_type, s.value, getattr(s, "whole", ""), getattr(s, "role", ""))
          for s in detect_structured_kv(V3_PAYLOAD)]
    passport = [k for k in kv if k[2] == "PASSPORT"]
    check(len(passport) == 2 and len({k[4] for k in passport}) == 1,
          "3b оба листа — части ОДНОГО документа", str(kv))
    # КОНТРОЛЬ: address в том же payload обязан остаться закрытым целиком.
    address_leaves = ("уфа", "сиреневая", "72", "33")
    open_address = [leaf for leaf in address_leaves
                    if not any(V3_PAYLOAD[s[0]:s[1]] == leaf for s in found)]
    check(not open_address, "3c контроль: address закрыт целиком", str(open_address))

    # ПОДМЕНА ЕДЕТ ФИНТИПОМ, А НЕ ЦЕЛЫМ: серия 4 цифры, номер 6 — и оба из ОДНОГО
    # документа, иначе инструмент получит серию одного человека и номер другого.
    with tempfile.TemporaryDirectory() as td:
        vault = vault_in(td, "g3")
        masked = redact.mask_text(V3_PAYLOAD, vault, DET.detect(V3_PAYLOAD))
        check("4608" not in masked and "246256" not in masked,
              "3d настоящее значение не ушло в подмену", masked)
        import json as _json
        doc = _json.loads(masked)
        series, number = doc["passport"]["series"], doc["passport"]["number"]
        check(series.isdigit() and len(series) == 4 and number.isdigit() and len(number) == 6,
              "3e финтип: серия 4 цифры, номер 6 цифр", f"{series!r} {number!r}")
        check(vault.is_minted_token(f"{series} {number}"),
              "3f серия+номер складываются в ОДИН документ", f"{series} {number}")
        check(vault.is_minted_token(f"{number} {series}") is False,
              "3g порядок частей — часть тождества", f"{number} {series}")


# ---------------------------------------------------------------------------
# ВЕКТОР 4. Коллизия подмены с настоящим значением НА УРОВНЕ ЧАСТИ.
# Решение владельца: подмена не имеет права нести целое слово = настоящее
# значение ДРУГОГО лица в том же разговоре; при исчерпании пула — fail-closed.
# Индекс свидетельства — НАСТОЯЩИЕ значения; две ПОДМЕНЫ, делящие слово, —
# это неразличимость личностей, и её держит `_shares_a_stem_in_conversation`
# (строго на первой половине попыток, мягко на второй), а не эта проверка.
# ---------------------------------------------------------------------------
def vector_4() -> None:
    print("\nВЕКТОР 4. Инъективность на словах внутри разговора")
    with tempfile.TemporaryDirectory() as td:
        vault = vault_in(td, "g4", "conv-1")
        real = "Лебедева Екатерина Петровна"
        fake = vault.tokenize(real, "NAME")
        print(f"        настоящий {real!r} -> подмена {fake!r}")
        witness = "Лебедева Ч. Д."          # доставленные байты long_order-027
        echo = "Котова Е. П."               # то, что заменяет кандидат — ФЕЙК
        check(vault._is_free_token(witness, "NAME", echo, "") is False,
              "4a сторож отвергает подмену с ЦЕЛЫМ словом настоящего",
              f"_is_free_token({witness!r}, original={echo!r})")

        # ИНЪЕКТИВНОСТЬ НА СЛОВАХ. Правило владельца: ПОДМЕНА не имеет права
        # нести целое слово, равное настоящему значению ДРУГОГО лица в том же
        # разговоре. Два НАСТОЯЩИХ человека могут делить имя («Валерий» дважды
        # в списке ниже) — это не дефект, дефект в ПОДМЕНЕ.
        #
        # ВОПРОС ЗАДАЁТСЯ НА МОМЕНТ ЧЕКАНИТЬ: свидетельство — то, что разговор
        # уже сказал. Человек, который ПОЯВИТСЯ позже, своё слово приносит с
        # собой, и ответ на это — не отказ в чеканке, а то, что `is_own_substitute`
        # не признаёт его нашей подменой (проверка 4e).
        people = ("Лебедева Екатерина Петровна", "Мещеряков Валерий Ярославович",
                  "Миллер Валерий Леонидович", "Громова Ольга Игоревна",
                  "Соловьёв Пётр Аркадьевич", "Кузнецова Дарья Львовна",
                  "Битюкова Зинаида Марковна", "Фомин Вячеслав Петрович")
        real_words: set[str] = set()
        clash: list[str] = []
        for person in people:
            token = vault.tokenize(person, "NAME")
            here = {w.casefold() for w in person.split() if len(w) > 1}
            mine = {w.casefold() for w in token.split() if len(w) > 1}
            clash += [f"подмена несёт чужое настоящее: {w} ({token})" for w in sorted(mine & real_words)]
            real_words |= here
        check(not clash, "4b подмена не несёт целого слова чужого НАСТОЯЩЕГО",
              str(clash))

        # FAIL-CLOSED, А НЕ ПРОБРОС: пул подмен конечен, и на исчерпании движок
        # обязан отказать (5xx у шлюза), а не выдать подмену с чужим словом.
        # ЗАДАЁТСЯ ИМЕННО ИСЧЕРПАНИЕ: настоящие фамилии берутся ИЗ ПУЛА ПОДМЕН,
        # потому что подмена не имеет права повторить НИ ОДНО настоящее слово
        # разговора. Когда весь пул израсходован как «настоящее», свободной
        # фамилии не остаётся — и движок обязан отказать, а не выдать подмену с
        # чужой фамилией.
        fakes = ASSETS.get().fakes
        names = list(fakes.last) + list(fakes.last_invariant)
        vault2 = vault_in(td, "g4b", "conv-2")
        issued: list[str] = []
        sources: list[str] = []
        failure: Exception | None = None
        try:
            for surname in names:
                sources.append(surname)
                issued.append(vault2.tokenize(f"{surname} Иван Петрович", "NAME"))
        except RuntimeError as exc:      # fail-closed — правильный ответ
            failure = exc
        carried = [f"{w} ({token})" for token, surname in zip(issued, sources)
                   for w in token.split() if w.casefold() == surname]
        check(failure is not None and not carried,
              "4c пул исчерпан — fail-closed, а не проброс",
              f"{len(issued)} подмен, исключение: {failure}; "
              f"подмена с настоящим словом: {carried[:3]}")

        # ОБРАТНОЕ НАПРАВЛЕНИЕ: настоящий человек с фамилией, равной слову
        # подмены, НЕ «наша» подмена — иначе он уходит к модели открытым.
        vault3 = vault_in(td, "g4c", "conv-3")
        theirs = vault3.tokenize("Мещеряков Валерий Ярославович", "NAME")
        carrier = next((w for w in theirs.split() if w.casefold() == "мещеряков"), None)
        check(carrier is None, "4d подмена не несёт настоящей фамилии", f"{theirs!r}")
        real_b = "Лебедев Иван Сергеевич"
        check(not redact.is_own_substitute(
            [s for s in DET.detect(real_b)][0], vault3),
            "4e настоящий человек с фамилией-словом подмены не пропускается",
            f"{real_b!r} при подмене {theirs!r}")


# ---------------------------------------------------------------------------
# ВЕКТОР 5. Телефон, проходящий контрольную сумму СНИЛС: контрольная сумма,
# посчитанная на ПОДпрогоне, не решает протяжённость суперспана. Свидетель
# g07 rag-008: `+79628863588` -> SNILS (1,12), «+» остаётся литералом.
# ---------------------------------------------------------------------------
def vector_5() -> None:
    print("\nВЕКТОР 5. Граница телефона сильнее контрольной суммы подпрогона")
    text = "+79628863588"
    found = spans(text)
    check(found and found[0][2] == "PHONE" and found[0][0] == 0 and found[0][1] == 12,
          "5a +79628863588 -> PHONE (0,12)", str(found))
    # КОНТРОЛИ: при РАВНЫХ границах приоритет СНИЛС не двигается, а форма без
    # «+» телефоном не читается — это и есть граничное свидетельство.
    controls = (
        ("79628863588", "SNILS"),
        ("422-017-866 40", "SNILS"),
        ("112 233 445 95", "SNILS"),
    )
    for probe, kind in controls:
        hits = spans(probe)
        check(bool(hits) and hits[0][2] == kind, f"5b контроль {probe!r} -> {kind}", str(hits))

    with tempfile.TemporaryDirectory() as td:
        vault = vault_in(td, "g5")
        masked = redact.mask_text(text, vault, DET.detect(text))
        digits = "".join(ch for ch in masked if ch.isdigit())
        check(masked.startswith("+7") and len(digits) in (11,),
              "5c подмена едет в нотации телефона", f"{text!r} -> {masked!r}")
        check(masked != text and "79628863588" not in masked,
          "5d настоящее значение закрыто", masked)
    # ПОЧЕМУ ПРАВИЛО ВООБЩЕ НУЖНО: 11 цифр ПРОХОДЯТ контрольную сумму СНИЛС,
    # то есть тип решает ГРАНИЦА, а не контрольная сумма подпрогона.
    check(validate_snils("79628863588") is True,
          "5e контрольная сумма СНИЛС на этих цифрах проходит",
          "validate_snils('79628863588')")


def main() -> int:
    vector_1()
    vector_2()
    vector_3()
    vector_4()
    vector_5()
    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
