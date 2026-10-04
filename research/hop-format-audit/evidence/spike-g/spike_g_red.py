"""SPIKE-Г RED-тест: пять векторов утечки класса Г.

Self-contained, без LLM и без сети: грузит bundle прямо из исходников
(`testkit.load_dev_bundle()`) и гоняет НАСТОЯЩИЙ детектор/маскировщик/волт.
Ничего не «доказывает» — показывает дефект. Exit 1, если хоть один вектор
воспроизвёлся, то есть пока дефект есть — тест КРАСНЫЙ.

Запуск:
    cd /Users/igor/Projects/Obscura-hop-audit/prototype
    PYTHONPATH=$PWD .venv/bin/python /tmp/spike_g_red.py

Вектор 4 зовёт внутренний `Vault._is_free_token` намеренно: это ЕДИНСТВЕННЫЙ
сторож чеканки, и вопрос теста ровно к нему — не «успел ли случайный жребий», а
«пропускает ли сторож подмену, несущую настоящую фамилию живого клиента».
"""

import random
import sys
import tempfile

from testkit import load_dev_bundle

load_dev_bundle()

from pseudex.assets import ASSETS                                # noqa: E402
from pseudex.detect_all import Detector                          # noqa: E402
from pseudex.ru_pii import validate_snils                        # noqa: E402
from pseudex.structured import detect_structured_kv              # noqa: E402
from pseudex.vault import Vault                                  # noqa: E402

DET = Detector()
FAILS = []


def show(title, ok, detail):
    print(f"[{'RED ' if not ok else 'green'}] {title}")
    for line in detail.splitlines():
        print("        " + line)
    print()
    if not ok:
        FAILS.append(title)


def spans(text):
    return [(s.start, s.end, s.entity_type, s.value) for s in DET.detect(text)]


# ---------------------------------------------------------------------------
# ВЕКТОР 1. Полулатница: латинская фамилия детектится позиционно.
# Свидетели: g06 tracker-004 («Kukushkin Valeriy» → «Kukushkin Родион»,
#            5 из 8 IN/tool-хопов leaked), g15 document:office-001/003
#            («Evgeniy Volnov»), g12 P9 (202 script-расхождения).
# Корень: `names.gazetteer_names` берёт латиницу только из `_LATIN_PAIR_RE`
# (линия 1648) и принимает прогон лишь если ПЕРВОЕ слово — известное имя
# (1664-1670), а `names.name_set` (assets.py:269-271) транслитерирует ТОЛЬКО
# семенной список (641 запись), не `dict_surnames` (196 800).
# ---------------------------------------------------------------------------
print("=" * 78)
print("ВЕКТОР 1. Полулатница (латинская фамилия уходит модели в открытую)")
print("=" * 78)
v1_bad = []
for text in ('"displayName": "Kukushkin Valeriy"', "Kukushkin Valeriy",
             "Fomin Vyacheslav", "Kukushkin", "Kukushkin Valeriy Ivanovich"):
    found = spans(text)
    covered = [text[s:e] for s, e, _, _ in found]
    first = text.strip('"').strip().split()[0]
    if not any(first in c for c in covered):
        v1_bad.append((text, found))
show("1a. латинский прогон закрыт ЦЕЛИКОМ (позиция не важна)", not v1_bad,
     "\n".join(f"{t!r} -> {f}" for t, f in v1_bad) or "все закрыты")

# Зеркалирование скрипта на МИНТЕ: латинскому настоящему — латинская подмена.
bad_script = []
with tempfile.TemporaryDirectory() as td:
    v = Vault(td + "/v.db", "spike-g1").for_conversation("k")
    for real in ("Evgeniy Volnov", "Kukushkin Valeriy"):
        fake = v.tokenize(real, "NAME")
        if any("а" <= ch.lower() <= "я" for ch in fake):
            bad_script.append((real, fake))
show("1b. подмена наследует СКРИПТ источника (латиница → латиница)", not bad_script,
     "\n".join(f"{r!r} -> {f!r}" for r, f in bad_script) or "скрипт зеркален")


# ---------------------------------------------------------------------------
# ВЕКТОР 2. Голое слово в нижнем регистре без номера дома и без родового слова.
# Свидетели: g08 mailfind-000 «адрес репина» (IN/tool leaked ×2),
#            mailfind-003 «от аленчиев» (IN/user leaked), «на бибиревская» (×2).
# ---------------------------------------------------------------------------
print("=" * 78)
print("ВЕКТОР 2. Голое слово после предлога/адресного якоря")
print("=" * 78)
v2_bad = []
for probe, needle, why in (
        ("Мой телефон +79164021187, адрес репина, дата рождения 1987-03-14", "репина",
         "в dict_surnames ЕСТЬ + в ГАР ЕСТЬ; гасит `_lowercase_dictionary_ok` "
         "(обычное чтение «репина», NOUN,inan)"),
        ("поищите в почте письмо от аленчиев", "аленчиев",
         "нет ни в одном словаре; `_is_surname_shaped`=True, но якоря «от» нет"),
        ("доставка была на бибиревская", "бибиревская",
         "в ГАР ЕСТЬ, но `_street_reference` отвергает (не Surn), а адресная ветка "
         "требует дом")):
    found = spans(probe)
    hit = any(needle in probe[s:e].lower() for s, e, _, _ in found)
    if not hit:
        v2_bad.append((probe, found, why))
show("2. слово замаскировано", not v2_bad,
     "\n\n".join(f"{p!r}\n  спаны={f}\n  почему: {w}" for p, f, w in v2_bad) or "всё закрыто")


# ---------------------------------------------------------------------------
# ВЕКТОР 3. Вложенный объект: родительский ключ не типизирует детей.
# Свидетель: g09 document-027…-048 — 12 кейсов, 24 утечки, форма PASSPORT 0/22.
# Корень: `structured._address_object_spans` — единственное место, где
# «родительский ключ типизирует детей», и оно жёстко привязано к LOC
# (роли city/street/house/flat + обязательные street и house). `_JSON_KV`
# (structured.py:56) матчит только СТРОКОВЫЕ значения, поэтому `"passport": {`
# не матчится вовсе, а `series`/`number` — 4 и 6 цифр без контрольной суммы.
# ---------------------------------------------------------------------------
print("=" * 78)
print("ВЕКТОР 3. Вложенный passport.{series,number}")
print("=" * 78)
V3 = ('{"last_name": "громова", "first_name": "ольга", '
      '"passport": {"series": "4608", "number": "246256"}, '
      '"snils": "760-451-105 71", '
      '"address": {"city": "уфа", "street": "сиреневая", "house": "72", "flat": "33"}}')
f3 = spans(V3)
leaks3 = [p for p in ("4608", "246256") if not any(V3[s:e] == p for s, e, _, _ in f3)]
show("3. листья вложенного объекта закрыты (контроль: address ЗАКРЫТ)", not leaks3,
     f"спаны={f3}\nНЕ закрыты: {leaks3}\n"
     f"kv-спаны={[(s.start, s.end, s.entity_type, s.value) for s in detect_structured_kv(V3)]}\n"
     f"в том же объекте address закрыт целиком — правило есть, но только для LOC")


# ---------------------------------------------------------------------------
# ВЕКТОР 4. Коллизия подмены с настоящим значением НА УРОВНЕ ЧАСТИ.
# Свидетель: g04 long_order-027 — подмена перечеканилась в «Лебедева Ч. Д.»,
#            а настоящая фамилия клиента в том же разговоре — «лебедева»;
#            доставленные модели байты: `Отправитель — Лебедева Ч. Д.`
#            (настоящая фамилия провисела в контексте 8 запросов).
#            g12 fanout_pick-020 («мещеряков валерий ярославович» при настоящем
#            «миллер валерий леонидович»).
# Корень: `vault._is_free_token` (2396) сверяет ЦЕЛУЮ строку — три точечных
# запроса по token/canonical/canonical_fold (2448-2456); `_shares_a_word`
# (1509) сравнивает кандидата только с ТЕМ, ЧТО ОН ЗАМЕНЯЕТ; ни одна проверка
# не спрашивает про ЧАСТИ уже выданных настоящих значений разговора.
#
# Точная форма свидетеля: модель написала СВОЮ подмену с инициалами
# («Котова Е. П.»), транскрипт передетектировался, движок перечеканил фейк — и
# жребий вытянул фамилию, равную НАСТОЯЩЕЙ фамилии клиента из того же
# разговора. Поэтому `original` здесь — ФЕЙК, а не настоящее значение: именно
# так `_shares_a_word` и остаётся слепым.
# ---------------------------------------------------------------------------
print("=" * 78)
print("ВЕКТОР 4. Коллизия на уровне ЧАСТИ")
print("=" * 78)
letters = "абвгдежзиклмнопрстуфхцчшщэюя"
with tempfile.TemporaryDirectory() as td:
    vault = Vault(td + "/v.db", "spike-g4").for_conversation("conv-1")
    real_a = "Лебедева Екатерина Петровна"
    tok_a = vault.tokenize(real_a, "NAME")
    print(f"        настоящий клиент: {real_a!r} -> подмена {tok_a!r}")
    witness = "Лебедева Ч. Д."            # ровно доставленные байты long_order-027
    echo = "Котова Е. П."                 # то, что заменил этот кандидат — ФЕЙК
    free = vault._is_free_token(witness, "NAME", echo, "")
    print(f"        _is_free_token({witness!r}, original={echo!r}) -> {free} "
          f"(должно быть False: «Лебедева» — настоящее значение клиента)")
    # И это не теория: фамилия клиента лежит в ТОМ САМОМ пуле, из которого
    # `_fake_name` рисует фамилию для формы («Фамилия И. О.») — vault.py:1475.
    pool = ASSETS.get().fakes.last
    reachable = [s for s in pool if s.lower().startswith("лебедев")]
    print(f"        пул фамилий подмен ({len(pool)} шт.) содержит настоящую: {reachable}")
    # Собственный жребий движка её и выдаёт — наблюдено: «Лебедев Ц. З.».
    found = None
    tries = 0
    for a in letters:
        for b in letters:
            if tries >= 300:
                break
            tries += 1
            fake_b = vault.tokenize(f"Котов{a}{b} Е. П.", "NAME")
            if any(w.lower().startswith("лебедев") for w in fake_b.split()):
                found = fake_b
                break
        if found or tries >= 300:
            break
    print(f"        {tries} перечеканок эха в том же разговоре: "
          f"собственный жребий выдал {found!r}"
          + ("  ← настоящая фамилия «Лебедева» уехала модели" if found else
             "  (жребий за 300 проб не поймался — но сторож его пропустил бы: "
             "невоспроизводимость и есть цена класса)"))
    show("4. сторож чеканки отвергает подмену, несущую настоящую ЧАСТЬ другого лица",
         not free and not reachable,
         f"_is_free_token вернул {free}; настоящая фамилия в пуле подмен: {reachable}; "
         f"жребий выдал {found}")


# ---------------------------------------------------------------------------
# ВЕКТОР 5. Телефон, проходящий контрольную сумму СНИЛС.
# Свидетель: g07 rag-008: detect('+79628863588') -> [(1,12,'SNILS')], «+»
#            остаётся литералом, подмена уходит в нотации СНИЛС
#            (`+45985880975`), форма OUT/tool_arg 0/1.
# Корень: `_SNILS_NODASH_RE` (`\b\d{11}\b`, ru_pii.py:207) + PRIORITY
#         «SNILS: 6 > PHONE: 5» (licensing/assets_source.py:1421-1427):
#         контрольная сумма ПОДпрогона перебивает ФОРМУ более широкого спана.
# ---------------------------------------------------------------------------
print("=" * 78)
print("ВЕКТОР 5. 11-значный телефон проходит mod-101 СНИЛС и побеждает по приоритету")
print("=" * 78)
V5 = "+79628863588"
f5 = spans(V5)
snils = [s for s in f5 if s[2] == "SNILS"]
bad5 = bool(snils) and snils[0][0] > 0
show(f"5. {V5}", not bad5,
     f"спаны={f5}\nvalidate_snils('79628863588')={validate_snils('79628863588')}\n"
     f"победил тип {f5[0][2] if f5 else None}; «+» (индекс 0) в спане: "
     f"{'да' if not bad5 else 'НЕТ — остаётся литералом'}")

print("=" * 78)
print(f"ИТОГ: RED по {len(FAILS)} проверкам")
for f in FAILS:
    print(f"  RED: {f}")
print("=" * 78)
sys.exit(1 if FAILS else 0)
