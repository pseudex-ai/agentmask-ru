"""D-081 — ОДНА СУЩНОСТЬ = ОДНА ПОДМЕНА, ПОВЕРХ СМЕНЫ ФОРМЫ.

Пин к бесплатной метрике `bench/identity_invariant.py`: те же восемь групп
записаны ЗДЕСЬ как утверждения, поэтому регрессия краснеет детерминированно и
без чтения чужого вывода. Метрика считает — этот файл требует.

ЧТО ИМЕННО ПИНИТСЯ, ПО ТИПАМ (структура подмены, D-081):

  * LOC — тождество есть УЛИЦА + ДОМ. Квартира, подъезд, этаж и корпус/строение
    это ИЗМЕНЯЕМЫЕ ЧАСТИ: их ЗНАЧЕНИЕ ключ не двигает, а их РОЛЬ в ключе
    остаётся, иначе короткое упоминание получило бы часть, которой не называло
    (`test_product`: «brief carries a flat the mention never named»), а связывание
    короткого и полного написания потеряло бы различие владельцев. Диктовка
    («дом тридцать восемь») сворачивается в цифры, поэтому встречается с «дом 38».
    ЧАСТИ ПРИ ЭТОМ НЕ ВЫБРАСЫВАЮТСЯ (W8, кластер A решения владельца): ядро
    (улица+дом) чеканится ОДИН раз, а каждая часть растёт на нём своей подменой,
    поэтому «квартира 7» и «квартира 42» — один дом и две РАЗНЫЕ квартиры, а
    `detokenize` возвращает инструменту РОВНО написанное клиентом.
  * NAME — тождество есть ФАМИЛИЯ + ИМЯ. Отчество и инициалы это изменяемые
    части: «Иванов Пётр» и «Иванов Пётр Сергеевич» — один человек и одна подмена,
    а «Иванов Пётр» и «Иванов Николай» — два: имя В тождестве, отчество нет.
    Форма при этом сохраняется: имя, названное тремя частями, получает трёхчастную
    подмену (отчество ОТРИСОВАНО, не выброшено), названное двумя — двухчастную.
  * PHONE — тождество есть 10–11 цифр, нотация изменяема (`+7`/`8`/разделители).

НЕГАТИВНЫЕ КОНТРОЛИ — здесь же, потому что правило, проверенное только на том,
что находиться ДОЛЖНО, это правило, про которое неизвестно, что ещё оно находит:
разные люди, разные дома, разные улицы, разный род одинокой фамилии.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_identity_invariant.py
"""

import sys

import testkit

testkit.load_dev_bundle()

from pseudex import morph_places                                  # noqa: E402
from pseudex.morph_places import address_key                      # noqa: E402
from pseudex.vault import Vault, canonicalize, _PLACE_PART_TTL    # noqa: E402
from pseudex import morph_names                                   # noqa: E402
from pseudex.redact import unmask_text                            # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def place_core(token: str) -> str:
    """ЯДРО подмены адреса — улица, дом и настоящий город, без изменяемых частей."""
    core = morph_places.core_phrase(token)
    return core.casefold().replace("ё", "е") or token.casefold()


def place_parts(token: str) -> tuple[tuple[str, str], ...]:
    """Изменяемые части подмены, роль -> значение ЦИФРАМИ, в русском порядке."""
    roles = morph_places.split_roles(token)
    return tuple(
        (role, morph_places.house_digits((roles.get(role) or "").strip()))
        for role in morph_places.MUTABLE_PLACE_ROLES if roles.get(role))


def token_of(forms: list[str], entity_type: str) -> dict[str, list[str]]:
    """Формы → подмены, собранные в группы «одно тождество = сколько форм».

    ДЛЯ LOC ТОЖДЕСТВО — ЯДРО (D-081/W8): «квартира 7» и «квартира 42» это ОДИН
    адрес, и группа считается по `core_phrase`, а не по целой строке. Вторая
    половина решения — части обязаны остаться РАЗЛИЧИМЫМИ — проверяется там же,
    где группа (`test_metric_groups`).
    """
    vault = Vault(":memory:", "identity-pin")
    out: dict[str, list[str]] = {}
    for form in forms:
        token = vault.tokenize(form, entity_type)
        key = place_core(token) if entity_type == "LOC" else token
        out.setdefault(key, []).append(token)
    return out


# (заголовок, тип, ожидание, формы) — ровно группы метрики, слово в слово.
GROUPS = [
    ("NAME падежи и порядок", "NAME", "collapse", [
        "Иванов Пётр", "Иванову Петру", "Иванова Петра", "Пётр Иванов"]),
    ("NAME разные люди", "NAME", "differ", [
        "Иванов Пётр", "Иванов Николай"]),
    ("NAME с отчеством и без", "NAME", "collapse", [
        "Иванов Пётр Сергеевич", "Иванов Пётр", "Иванов П. С."]),
    ("LOC форма: регистр и разделители", "LOC", "collapse", [
        "улица Лермонтова, дом 38, квартира 7",
        "ул. Лермонтова 38 кв 7",
        "улица лермонтова дом 38 квартира 7"]),
    ("LOC диктовка против цифр", "LOC", "collapse", [
        "улица лермонтова дом тридцать восемь квартира семь",
        "улица Лермонтова дом 38 квартира 7"]),
    ("LOC смена квартиры", "LOC", "collapse", [
        "улица Лермонтова дом 38 квартира 7",
        "улица Лермонтова дом 38 квартира 42"]),
    ("LOC смена подъезда", "LOC", "collapse", [
        "улица Лермонтова дом 38 подъезд 1 квартира 7",
        "улица Лермонтова дом 38 подъезд 3 квартира 7"]),
    ("PHONE +7/8/без разделителей", "PHONE", "collapse", [
        "+7 916 402-11-87", "8 916 402-11-87", "89164021187"]),
]


def test_metric_groups() -> None:
    """Восемь групп метрики как утверждения — и метрика, и этот файл красны
    на одном и том же."""
    for title, entity_type, expect, forms in GROUPS:
        tokens = token_of(forms, entity_type)
        if expect == "collapse":
            ok = len(tokens) == 1
            detail = f"{len(tokens)} тождеств(о) на {len(forms)} форм"
            if ok and entity_type == "LOC":
                # ВТОРАЯ ПОЛОВИНА РЕШЕНИЯ ВЛАДЕЛЬЦА. Свёртка к ядру одна
                # удовлетворила бы группу «смена квартиры» и на вырожденной
                # подмене без квартиры; части обязаны быть РАЗЛИЧИМЫМИ, иначе
                # два человека в одном доме становятся одним.
                by_parts: dict[tuple[tuple[str, str], ...], set[str]] = {}
                for group in tokens.values():
                    for token in group:
                        by_parts.setdefault(place_parts(token), set()).add(token)
                collisions = {parts: group for parts, group in by_parts.items()
                              if len(group) != 1}
                ok = not collisions
                detail += ("; части различимы" if ok
                           else f"; части не различились: {collisions}")
        else:
            ok = len(tokens) == len(forms)
            detail = f"{len(tokens)} фейк(ов) на {len(forms)} форм (нужно по одному)"
        check(ok, f"метрика: {title}", detail)


def test_address_identity() -> None:
    """Тождество адреса — улица и дом; мелкие части изменяемы, но их РОЛЬ в
    ключе остаётся, а диктовка сворачивается в цифры."""
    typed = address_key("улица Лермонтова дом 38 квартира 7")
    check(address_key("улица Лермонтова дом 38 квартира 42") == typed,
          "адрес: смена квартиры не двигает тождество",
          f"{typed!r}")
    check(address_key("улица Лермонтова дом 38 подъезд 3 квартира 7")
          == address_key("улица Лермонтова дом 38 подъезд 1 квартира 7"),
          "адрес: смена подъезда не двигает тождество",
          f"{address_key('улица Лермонтова дом 38 подъезд 3 квартира 7')!r}")
    check(address_key("улица лермонтова дом тридцать восемь квартира семь") == typed,
          "адрес: диктовка «тридцать восемь» встречается с «38»",
          f"{address_key('улица лермонтова дом тридцать восемь квартира семь')!r}")
    # …а это негативные контроли: то, что тождество ДВИГАТЬ обязано.
    check(address_key("улица Лермонтова дом 39 квартира 7") != typed,
          "адрес: другой дом — другое тождество",
          f"{address_key('улица Лермонтова дом 39 квартира 7')!r}")
    check(address_key("улица Пушкина дом 38 квартира 7") != typed,
          "адрес: другая улица — другое тождество")
    check(address_key("улица Лермонтова дом 38") != typed,
          "адрес: упоминание без квартиры — ДРУГОЕ тождество",
          "иначе короткое написание получило бы часть, которой не называло")
    check(address_key("переулок Пушкина 5") != address_key("улица Пушкина 5"),
          "адрес: родовое слово — часть тождества (решение владельца)")


def test_address_render_and_restore() -> None:
    """Части не выброшены: подмена их ОТРИСОВЫВАЕТ, а `detokenize` собирает
    настоящее написание обратно. Два человека в одном доме остаются различимы
    своими частями, а не тем, что один из них потерял квартиру."""
    vault = Vault(":memory:", "identity-pin-loc")
    first = vault.tokenize("улица Лермонтова дом 38 квартира 7", "LOC")
    second = vault.tokenize("улица Лермонтова дом 38 квартира 42", "LOC")
    check("кв" in first, "адрес: подмена несёт квартиру, а не выбрасывает её", f"{first!r}")
    # ЯДРО ОДНО (улица+дом), А КВАРТИРА — СВОЯ. Здесь стоял пин полного
    # равенства строк: он и был исходным дефектом — вторая квартира получала
    # чужую подмену, а инструмент — чужой настоящий адрес (W8).
    check(place_core(first) == place_core(second),
          "адрес: смена квартиры — ТО ЖЕ ядро улица+дом",
          f"{place_core(first)!r} / {place_core(second)!r}")
    check(place_parts(first) != place_parts(second)
          and dict(place_parts(first)).get("flat") != dict(place_parts(second)).get("flat"),
          "адрес: два человека в одном доме различимы квартирой",
          f"{first!r} / {second!r}")
    # ПОПРАВКА «ОЙ НЕ ТА КВАРТИРА» НЕ ЧЕКАНИТ НОВЫЙ ДОМ. Соседний номер
    # квартиры приходит к тому же ядру — это и есть принцип владельца из D-081.
    third = vault.tokenize("улица Лермонтова дом 38 квартира 13", "LOC")
    check(place_core(third) == place_core(first),
          "адрес: поправка квартиры сохраняет улицу и дом", f"{third!r}")
    check(len({dict(place_parts(t)).get("flat")
               for t in (first, second, third)}) == 3,
          "адрес: три квартиры одного дома — три разные подмены")
    check(unmask_text(first, vault) == "улица Лермонтова дом 38 квартира 7",
          "адрес: инструмент получает ровно то, что написал клиент",
          f"{unmask_text(first, vault)!r}")
    check(unmask_text(second, vault) == "улица Лермонтова дом 38 квартира 42",
          "адрес: вторая квартира возвращается ЕЁ настоящей, а не первой",
          f"{unmask_text(second, vault)!r}")
    check(unmask_text(third, vault) == "улица Лермонтова дом 38 квартира 13",
          "адрес: поправка возвращается дословно",
          f"{unmask_text(third, vault)!r}")
    # КОРПУС — ТАКАЯ ЖЕ ЧАСТЬ НА ТОМ ЖЕ ЯДРЕ, и он тоже различим.
    corpus_vault = Vault(":memory:", "identity-pin-corpus")
    one = corpus_vault.tokenize("улица Лермонтова дом 38 корпус 1", "LOC")
    two = corpus_vault.tokenize("улица Лермонтова дом 38 корпус 2", "LOC")
    shared = Vault(":memory:", "identity-pin-corpus-2")
    flat = shared.tokenize("улица Лермонтова дом 38 квартира 7", "LOC")
    corpus = shared.tokenize("улица Лермонтова дом 38 корпус 1", "LOC")
    check(place_core(one) == place_core(two),
          "адрес: корпус 1 и корпус 2 — то же ядро", f"{one!r} / {two!r}")
    check(dict(place_parts(one)).get("building") != dict(place_parts(two)).get("building"),
          "адрес: разные корпуса различимы", f"{one!r} / {two!r}")
    check(place_core(flat) == place_core(corpus),
          "адрес: квартира и корпус растут на ОДНОМ ядре", f"{flat!r} / {corpus!r}")
    # КОРОТКОЕ УПОМИНАНИЕ НЕ ПОЛУЧАЕТ ЧУЖОЙ КВАРТИРЫ. Полная запись с городом
    # связывается с короткой отдельным правилом (`_linked_place`), и проекция
    # снимает часть, которой короткая не называла.
    brief_vault = Vault(":memory:", "identity-pin-brief").for_conversation("d-1")
    brief_vault.tokenize("г. Казань, ул. Садовая, д. 3, кв. 12", "LOC")
    brief = brief_vault.tokenize("садовая 3", "LOC")
    check(brief and "кв" not in brief,
          "адрес: короткое упоминание не показывает квартиру", f"{brief!r}")


def test_name_identity() -> None:
    """Тождество имени — фамилия и имя. Отчество ОТРИСОВАНО, инициалы
    сокращаются до той же подмены, разные имена не сливаются."""
    # ОТЧЕСТВО НАЗВАНО ПЕРВЫМ: подмена трёхчастная, и обе более короткие формы
    # приходят к ней же.
    long_first = Vault(":memory:", "identity-pin-name-1")
    three = long_first.tokenize("Иванов Пётр Сергеевич", "NAME")
    check(len(three.split()) == 3, "имя: три части — трёхчастная подмена", f"{three!r}")
    check(long_first.tokenize("Иванов Пётр", "NAME") == three,
          "имя: написанное без отчества приходит к той же подмене")
    check(long_first.tokenize("Иванов П. С.", "NAME") == three,
          "имя: инициалы — та же подмена")
    check(long_first.detokenize(three) == "Иванов Пётр Сергеевич",
          "имя: инструмент получает настоящее написание целиком",
          f"{long_first.detokenize(three)!r}")
    # НАЗВАНО КОРОТКО ПЕРВЫМ: двухчастная подмена, и полное имя ВЫРАЩИВАЕТ её,
    # а не чеканит второго человека.
    short_first = Vault(":memory:", "identity-pin-name-2")
    two = short_first.tokenize("Иванов Пётр", "NAME")
    check(len(two.split()) == 2, "имя: две части — двухчастная подмена", f"{two!r}")
    grown = short_first.tokenize("Иванов Пётр Сергеевич", "NAME")
    check(grown != two and len(grown.split()) == 3,
          "имя: полное имя выращивает подмену с отчеством", f"{two!r} -> {grown!r}")
    check(grown.split()[:2] == two.split(),
          "имя: выросшая подмена несёт те же фамилию и имя", f"{grown!r}")
    check(short_first.detokenize(grown) == "Иванов Пётр Сергеевич",
          "имя: отчество возвращается инструменту", f"{short_first.detokenize(grown)!r}")
    # НЕГАТИВНЫЕ КОНТРОЛИ.
    check(token_of(["Иванов Пётр", "Иванов Николай"], "NAME").__len__() == 2,
          "имя: другое имя — другая подмена (ИМЯ в тождестве)")
    lone = Vault(":memory:", "identity-pin-name-3")
    check(lone.tokenize("Иванова", "NAME") != lone.tokenize("Иванов", "NAME"),
          "имя: одинокая фамилия не схлопывается по родам",
          "«Иванова» — женский именительный, не мужской родительный")


def test_traps() -> None:
    """Ловушки detect-change, каждая — потому что её уже проходили."""
    # `to_nominative` зовут с двух сторон, и страж стоит на стороне НАСТОЯЩЕГО
    # значения: сама функция обязана остаться безоружной, иначе круг развалится
    # у всех подмен сразу.
    check(morph_names.to_nominative("Иванова") == "Иванов"
          and morph_names.lone_nominative_gender("Иванова") is not None,
          "ловушка: страж одинокой фамилии живёт в canonicalize, не в to_nominative")
    check(canonicalize("NAME", "Тагиев") == "Тагиев",
          "ловушка: канонизация требует ДОКАЗАТЕЛЬСТВА падежа, а не похожести")
    # `place_parts` — таблица СВЯЗЫВАНИЯ, и она обязана истекать: иначе область
    # разговора превращается в вечный список, кто с кем говорил.
    check(0 < _PLACE_PART_TTL <= 24 * 60 * 60,
          "ловушка: place_parts истекает (это связывание, а не тождество)",
          f"{_PLACE_PART_TTL}s")
    # Подмена стабильна: одно значение дважды — одна строка, а не два фейка.
    stable = Vault(":memory:", "identity-pin-stable")
    check(stable.tokenize("Иванов Пётр", "NAME") == stable.tokenize("Иванов Пётр", "NAME"),
          "ловушка: повторное значение не чеканит второй подмены")


def main() -> int:
    test_metric_groups()
    test_address_identity()
    test_address_render_and_restore()
    test_name_identity()
    test_traps()
    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} проверок зелёные")
    for name in failed:
        print(f"  RED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
