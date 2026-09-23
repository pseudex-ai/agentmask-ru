"""Коллизии подмен: попытки СЛОМАТЬ защиту, а не подтвердить её.

ЧТО ЗДЕСЬ ЗА КЛАСС ОТКАЗА. Подмена берётся из того же пространства строк, что и
настоящие значения: фейковое имя — это по построению правильное русское имя,
фейковый адрес — правильный адрес, фейковая дата — настоящая дата. Значит рано
или поздно подмена одного человека совпадает с настоящим значением другого, и
дальше одна строка означает двух людей сразу:

  * НАЗАД — модель пишет подмену, детокенизация находит строку в столбце
    `token` и отдаёт инструменту ЧУЖИЕ данные (иногда химеру: «Кирилл Бородин»
    вернулся как «Ян Бородин», потому что каждое слово разрешилось по своей
    строке);
  * ВПЕРЁД — настоящий человек с таким именем приходит в трафике, сторож эха
    видит «это наша подмена» и пропускает его к модели ОТКРЫТЫМ ТЕКСТОМ.

Обе половины молчаливые и обе отвечают 200. Измерено на 2979 настоящих людях из
NEREL — чужая разметка, не наша: 3-7 обратных и 2-3 прямых на прогон.

ПОЧЕМУ ТЕСТ ЖИВЁТ В РЕПОЗИТОРИИ, А НЕ В ЧЕРНОВИКЕ. Ни один наш корпус этого не
видел: golden и dirty порождают по одному человеку на текст, `test_overmasking`
меряет чистую речь, NEREL меряет детекцию. Класс становится виден только когда
ОДИН клиент проходит через шлюз тысячами значений подряд — а это ровно та форма,
в которой продукт и работает.
"""
import json
import random
import sys

import testkit
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, mask_one
from pseudex.maskcache import MaskCache
from pseudex.redact import (mask_text, residual_tokens, surviving_substitutes,
                            unmask_arguments, unmask_text)
from pseudex.vault import Vault

_ORG = "collide"


def _context(detector: Detector, vault: Vault, conversation: str,
             scope: str = "conversation") -> MaskContext:
    return MaskContext(detector=detector,
                       vault=vault.for_conversation(conversation).with_pseudonym_scope(scope),
                       audit=AuditLog(":memory:"), cache=MaskCache(4096),
                       org_id=_ORG, agent_id="a", conversation_id=conversation)


def _people(count: int) -> list[str]:
    """Разные люди, чьи имена НЕ взяты из нашего же пула подмен."""
    first = ["Ринат", "Тамерлан", "Ислам", "Аслан", "Марат", "Ильдар", "Ленар",
             "Рустем", "Айрат", "Наиль", "Фанис", "Забир"]
    last = ["Гизатуллин", "Сафиуллин", "Хайруллин", "Валиахметов", "Мифтахов",
            "Ситдиков", "Нуриев", "Ахметзянов", "Шайхутдинов", "Гарипов"]
    rng = random.Random(20260901)
    out, seen = [], set()
    while len(out) < count:
        name = f"{rng.choice(first)} {rng.choice(last)}{rng.randrange(100)}"
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def test_substitute_is_never_a_real_value() -> None:
    """НАЗАД: ни одна подмена не равна настоящему значению того же клиента.

    Это половина, которую можно проверить в момент чеканки: настоящее значение
    уже лежит в волте, и запрос по первичному ключу стоит одну точку.
    """
    vault = Vault(":memory:", _ORG)
    for person in _people(1500):
        vault.tokenize(person, "NAME")
    rng = random.Random(7)
    for _ in range(1500):
        vault.tokenize(f"{rng.randrange(1, 29):02d}.{rng.randrange(1, 13):02d}."
                       f"{rng.randrange(1950, 2006)}", "DOB")
    rows = vault._conn.execute(
        "SELECT canonical, token, original, first_seen FROM tokens WHERE customer=?",
        (_ORG,)).fetchall()
    # ПО ВРЕМЕНИ, а не по множеству. Проверить в момент чеканки можно только
    # то, что уже лежит в волте; значение, пришедшее ПОЗЖЕ, этой проверке не
    # доступно вовсе — им занимается сторож эха, и у него свой тест ниже.
    born = {}
    for canonical, _token, original, first_seen in rows:
        for key in (canonical, original):
            if key:
                born[key] = min(born.get(key, first_seen), first_seen)
    clash = [row for row in rows
             if row[1] in born and born[row[1]] < row[3]]
    assert not clash, f"подмена равна СТАРШЕМУ настоящему значению: {clash[:5]}"
    print(f"назад OK — {len(rows)} подмен, ни одна не совпала со значением, "
          f"которое волт уже знал")


def test_substitute_is_never_the_value_it_replaces() -> None:
    """Строки, ради которой чеканят, в таблице ещё НЕТ — и подмена свободно
    выходила равной ей самой. Измерено: «15.06.1963» замаскировано в
    «15.06.1963», то есть не замаскировано вовсе, и с этого момента сторож эха
    пропускал эту дату у всех остальных."""
    vault = Vault(":memory:", _ORG)
    same = []
    rng = random.Random(11)
    for _ in range(4000):
        value = (f"{rng.randrange(1, 29):02d}.{rng.randrange(1, 13):02d}."
                 f"{rng.randrange(1950, 2006)}")
        if vault.tokenize(value, "DOB") == value:
            same.append(value)
    assert not same, f"подмена совпала с исходным значением: {same[:5]}"
    print(f"сама себе подмена OK — 4000 дат, ни одна не заменена на себя")


def test_real_person_named_like_a_substitute_is_masked(detector: Detector) -> None:
    """ВПЕРЁД: клиент, которого зовут как чью-то подмену, всё равно маскируется.

    Разговор — вот что различает два чтения одной строки. Своя подмена
    возвращается к нам в том же диалоге, куда мы её отдали; тёзка подмены
    приходит из другого.
    """
    vault = Vault(":memory:", _ORG)
    first = _context(detector, vault, "conv-1")
    mask_one("Клиент Иван Петров просит перезвонить", first)
    token = vault._conn.execute(
        "SELECT token FROM tokens WHERE customer=? AND entity_type='NAME'",
        (_ORG,)).fetchone()[0]

    other = _context(detector, vault, "conv-2")
    out = mask_one(f"Клиент {token} просит перезвонить", other)
    assert token not in out, f"тёзка подмены ушёл к модели открытым: {out!r}"
    print(f"вперёд OK — {token!r} в чужом разговоре замаскирован: {out!r}")


def test_memory_recall_across_conversations(detector: Detector) -> None:
    """ПАМЯТЬ АГЕНТА — ЭТО ЭХО ИЗ ДРУГОГО ДИАЛОГА, и область подмены решает,
    чем оно окажется.

    Агент с долговременной памятью вспоминает факт из прошлой беседы, и текст,
    который хост подмешивает в промпт, несёт ПОДМЕНУ, показанную тогда. Все
    известные хранилища памяти ключуются по ПОЛЬЗОВАТЕЛЮ, а не по беседе
    (LangGraph Store, Mem0, Google ADK, memory tool Anthropic; fork сессии и
    handoff с отдельной сессией дают то же самое другим способом).

    ОБЕ ПОЛОВИНЫ РАЗМЕНА ПРОВЕРЯЮТСЯ ЗДЕСЬ, и вторая — не меньше первой:

      * при `conversation` подмена из прошлой беседы читается как чужая строка,
        маскируется ВТОРОЙ раз, и инструмент получает ФЕЙК первой беседы с
        кодом 200 и пустым списком остатков;
      * при `customer` она узнаётся, и инструмент получает настоящее значение;
      * ценой этого узнавания идёт настоящий человек-тёзка чужой подмены: при
        `customer` он уходит к модели ОТКРЫТЫМ ТЕКСТОМ, при `conversation` —
        маскируется. Поэтому умолчание не двигается, а хост объявляет память
        сам (`pseudonym_scope`, `PSEUDEX_PSEUDONYM_SCOPE`).
    """
    said = "это иванов пётр сергеевич, телефон 89162148803"
    for scope, recalled_is_ours in (("conversation", False), ("customer", True)):
        vault = Vault(":memory:", _ORG)
        first = _context(detector, vault, "conv-A", scope)
        shown = mask_one(said, first)
        token = vault._conn.execute(  # noqa: SLF001 - the test reads the store directly
            "SELECT token FROM tokens WHERE customer=? AND entity_type='NAME'", (_ORG,)).fetchone()[0]
        assert token.casefold() in shown.casefold(), (scope, shown)   # shown in the customer's lower case

        later = _context(detector, vault, "conv-B", scope)
        memory = f"из памяти: клиент {token} звонил на прошлой неделе"
        seen = mask_one(memory, later)
        assert (token.casefold() in seen.casefold()) is recalled_is_ours, (scope, seen)
        back = unmask_arguments(json.dumps({"name": token}, ensure_ascii=False),
                                vault.for_conversation("conv-B").with_pseudonym_scope(scope))
        # The token itself always resolves — the vault's own lookup is
        # customer-wide. What the scope decides is whether the model was shown
        # that string or a SECOND substitute standing for it.
        assert json.loads(back)["name"].lower().startswith("иванов"), (scope, back)

        # THE PRICE, measured in the same test rather than promised in a comment.
        namesake = _context(detector, vault, "conv-C", scope)
        out = mask_one(f"Клиент {token} просит перезвонить", namesake)
        leaked = token.casefold() in out.casefold()
        assert leaked is recalled_is_ours, (scope, out)
    print("память OK — при `customer` подмена из прошлой беседы узнаётся, "
          "при `conversation` перечеканивается; тёзка подмены — цена расширения")


def test_echo_in_its_own_conversation_is_left_alone(detector: Detector) -> None:
    """И ровно то, ради чего сторож существует, должно уцелеть: подмена,
    вернувшаяся в СВОЁМ разговоре, не маскируется второй раз. Иначе она получает
    подмену подмены, детокенизация возвращает инструменту фейк, и личность
    человека меняется каждый ход."""
    vault = Vault(":memory:", _ORG)
    conv = _context(detector, vault, "conv-echo")
    real = ("Клиент Иван Петров просит перезвонить, телефон +7 999 123-45-67, "
            "адрес улица Ленина 5, кв 12")
    first = mask_one(real, conv)
    second = mask_one(f"Повтор: {first}", conv)
    assert first in second, f"эхо переписано в своём же разговоре: {second!r}"
    restored = unmask_text(second, vault)
    assert "Иван Петров" in restored and "+7 999 123-45-67" in restored, restored
    print(f"эхо OK — подмена устойчива в своём разговоре и разворачивается обратно")


def test_migrated_vault_keeps_the_old_behaviour(detector: Detector) -> None:
    """Строка, отчеканенная до появления столбца, не знает своего разговора —
    и должна вести себя как раньше, а не считаться чужой. Иначе обновление
    версии переписало бы каждую подмену в каждом живом диалоге сразу."""
    vault = Vault(":memory:", _ORG)
    conv = _context(detector, vault, "conv-old")
    mask_one("Клиент Иван Петров просит перезвонить", conv)
    vault._conn.execute("UPDATE tokens SET minted_in=NULL")
    vault._conn.commit()
    token = vault._conn.execute(
        "SELECT token FROM tokens WHERE customer=? AND entity_type='NAME'",
        (_ORG,)).fetchone()[0]
    elsewhere = vault.for_conversation("conv-new")
    assert elsewhere.is_minted_token(token), "старая строка объявлена чужой"
    print("миграция OK — строка без разговора ведёт себя как до изменения")


def test_pool_is_not_narrowed_by_the_extra_rejections() -> None:
    """Каждая новая проверка отвергает кандидатов, а исчерпанный пул — это
    постоянный 5xx для клиента, а не худшая подмена. Меряется потолок, а не
    факт «хватило»: пул с запасом в одну строку проходит любую проверку на
    «хватило» и падает у клиента.

    ПОТОЛОК ЗДЕСЬ СВОЙ И ОН НЕ ОТ ЭТИХ ПРАВОК. Одна женская фамилия без имени
    берётся из выведенного подпула инвариантных фамилий — тех, чья женская форма
    разрешается во всех падежах, — и их 33. Столько же было и до правок; проверка
    на совпадение с настоящим значением этот потолок не сдвинула. Это тот самый
    класс, который файл `vault.py` чинил уже дважды (на 6 и на 33), и он всё ещё
    достижим.
    """
    vault = Vault(":memory:", _ORG)
    minted, reached = set(), 0
    try:
        for index in range(400):
            minted.add(vault.tokenize(f"Гизатуллина{index}", "NAME"))
            reached = index + 1
    except RuntimeError:
        pass
    assert reached >= 100, (
        f"пул одиночных женских фамилий сузился до {reached} — правки сделали "
        f"постоянный 5xx ближе, чем он был")
    print(f"пул — потолок {reached} одиночных женских фамилий на клиента "
          f"(до правок столько же); дальше клиент получает 5xx навсегда")


def test_two_people_in_one_dialogue_never_share_a_fake_surname(detector: Detector) -> None:
    """Два человека в одной беседе не получают одну фамилию подмены.

    С пулом в 28 фамилий сообщение с двумя людьми вытягивало одну и ту же
    примерно раз в 28 — «Шилов Семён» и «Шилова Иванна». Агент строит из них
    CSV, а «Шилова» — это и её именительный, и его родительный: два владельца,
    отказ, и подмена уходит в CRM клиента (container-009/015/027 в скриптовом
    прогоне 04.09). Проверяется по 300 чеканкам: ни одной пары с общей основой
    в одной беседе — и что чужая беседа по-прежнему свободна брать ту же.
    """
    text = "занесите двоих в базу васильев иван телефон 8 977 388 78 79 и мамедова лейла телефон +79602859294"
    spans = detector.detect(text)
    shared = 0
    for _ in range(300):
        vault = Vault(":memory:", _ORG).for_conversation("one")
        mask_text(text, vault, spans)
        tokens = [row[0] for row in vault._conn.execute(  # noqa: SLF001 - the test reads the store directly
            "SELECT token FROM tokens WHERE entity_type='NAME'").fetchall()]
        stems = {token.split()[0].casefold().rstrip("а") for token in tokens}
        shared += 1 if len(tokens) == 2 and len(stems) < 2 else 0
    assert shared == 0, f"{shared} из 300 чеканок дали двум людям одну фамилию в одной беседе"
    print("основа фамилии OK — два человека в одной беседе не делят подмену; 300 чеканок")


def test_b23_customer_word_equal_to_another_dialogue_substitute(detector: Detector) -> None:
    """Б23: НАСТОЯЩЕЕ СЛОВО КЛИЕНТА, РАВНОЕ ЧУЖОЙ ПОДМЕНЕ, НЕ СТАНОВИТСЯ ЧУЖИМ
    ЧЕЛОВЕКОМ на обратном пути.

    Публичный бенчмарк на выпущенном 0.3.16: диалог 021 вытянул для «ахат
    дормедонтов» подмену «Николай Крылов»; в диалоге 024 клиент написал
    «адрес николая заболоцкого 81 кв 51», детектор взял «заболоцкого 81 кв
    51», слово «николая» ушло к модели открытым, а из аргумента инструмента
    вернулось «ахат улицы Заболоцкого…» — единственный владелец куска
    «Николая» во ВСЁМ томе заказчика побеждал сразу. Кусок подмены может
    прийти только из диалога, которому показали целое: `token_uses` это
    помнит, и в чужом диалоге слово остаётся словом клиента.

    Обе половины: (1) в диалоге 024 «николая» не трогается; (2) в диалоге
    021 — и в любом позднем диалоге, где та же подмена показана снова, —
    кусок «Николая» по-прежнему разрешается в Ахата.
    """
    import secrets  # noqa: PLC0415

    real_choice = secrets.choice

    def forcing(*sticky: str):
        def choice(seq):
            seq = list(seq)
            for want in sticky:
                if want in seq:
                    return want
            return real_choice(seq)
        return choice

    vault = Vault(":memory:", _ORG)
    try:
        secrets.choice = forcing("Николай", "Крылов")
        first = _context(detector, vault, "conv-021")
        shown = mask_one("заказ на ахат дормедонтов, тел 89162148803", first)
    finally:
        secrets.choice = real_choice
    assert "николай крылов" in shown, shown          # in the customer's lower case, as the source

    other = _context(detector, vault, "conv-024")
    said = "адрес николая заболоцкого 81 кв 51"
    masked = mask_one(said, other)
    assert "николая" in masked, masked            # the first word of the street stays in the clear (open issue)
    argument = json.dumps({"address": masked.replace("адрес ", "")}, ensure_ascii=False)
    back = json.loads(unmask_arguments(argument, vault.for_conversation("conv-024")))["address"]
    assert back.startswith("николая"), back
    assert "ахат" not in back.lower(), back

    # The positive half: the dialogue that WAS shown the substitute resolves its piece.
    piece = json.dumps({"name": "Николая"}, ensure_ascii=False)
    assert json.loads(unmask_arguments(piece, vault.for_conversation("conv-021")))["name"].lower().startswith("ахат")
    # ...and so does a later dialogue where the same person is masked again (token reused).
    later = _context(detector, vault, "conv-031")
    again = mask_one("заказ на ахат дормедонтов, тел 89162148803", later)
    assert "николай крылов" in again, again
    assert json.loads(unmask_arguments(piece, vault.for_conversation("conv-031")))["name"].lower().startswith("ахат")
    print("Б23 OK — кусок подмены разрешается только в диалоге, которому её показали; чужое слово остаётся словом клиента")


def test_a_bare_street_answers_only_in_its_own_dialogue(detector: Detector) -> None:
    """ВЫРОЖДЕННЫЙ КЛЮЧ УЛИЦЫ НЕ ОТДАЁТ УЛИЦУ ЧУЖОГО ДИАЛОГА.

    Улица без номера — «наб. Ольгина», каким его берёт детектор из «наб.
    Ольгина пруда, 119» (Б16), — чеканится ключом «ольгин|»: ни одной цифры,
    то есть ни одного признака, который отличал бы ОДИН адрес от всех
    остальных с тем же названием. Второму диалогу того же заказчика выпадает
    фейковая улица с тем же названием, агент кладёт её в поле `street`, и
    `_lookup_typed` по `name_key` отдавал настоящую улицу ПЕРВОГО диалога —
    раскрытие данных одного разговора в инструменте другого, тот же класс,
    который Б23 закрыл для куска имени.

    Обе половины: чужой диалог получает СВОЮ улицу, свой — по-прежнему первую.
    Подмена тянется случайно, поэтому название фейка здесь закреплено, а не
    разыграно: иначе проверка ловила бы дефект раз в сорок прогонов.
    """
    import secrets  # noqa: PLC0415

    real_choice = secrets.choice

    def forcing(*sticky: str):
        def choice(seq):
            seq = list(seq)
            for want in sticky:
                if want in seq:
                    return want
            return real_choice(seq)
        return choice

    vault = Vault(":memory:", _ORG)
    first_said = "доставка по адресу наб. Ольгина пруда, 119, кв. 234"
    second_said = "адрес изобильная 60 кв 186"
    try:
        secrets.choice = forcing("Каштановой")
        first = _context(detector, vault, "conv-bare-A")
        first_masked = mask_one(first_said, first)
        second = _context(detector, vault, "conv-bare-B")
        second_masked = mask_one(second_said, second)
    finally:
        secrets.choice = real_choice
    assert "Каштановая" in first_masked, first_masked
    assert "каштановая" in second_masked.lower(), second_masked

    field = json.dumps({"street": "Каштановая"}, ensure_ascii=False)
    theirs = json.loads(unmask_arguments(field, vault.for_conversation("conv-bare-B")))["street"]
    assert "Ольгина" not in theirs, theirs
    assert theirs.lower().startswith("изобильн"), theirs

    ours = json.loads(unmask_arguments(field, vault.for_conversation("conv-bare-A")))["street"]
    assert ours == "Ольгина", ours

    # A FULL ADDRESS KEEPS THE CUSTOMER-WIDE ANSWER: its key carries the house
    # and the flat, so it names ONE address and «одна подмена, навсегда» holds.
    whole = second_masked.split("адрес ", 1)[1].strip()
    everywhere = json.loads(unmask_arguments(
        json.dumps({"address": whole}, ensure_ascii=False),
        vault.for_conversation("conv-bare-C")))["address"]
    assert "изобильн" in everywhere.lower(), everywhere

    # …И ХОЗЯИН, ОБЪЯВИВШИЙ ПАМЯТЬ АГЕНТА, ПО-ПРЕЖНЕМУ ПОЛУЧАЕТ ШИРОКИЙ ОТВЕТ.
    # Сужение — это УМОЛЧАНИЕ, а не запрет: `with_pseudonym_scope("customer")`
    # объявляет, что диалоги одного заказчика — один субъект, и тогда улица без
    # номера разрешается за пределами своего разговора ровно так же, как это уже
    # делает `is_minted_token`. Без этой половины правило читалось бы как
    # «вырожденный ключ не разрешается никогда», и объявление ничего не значило бы.
    declared = json.loads(unmask_arguments(
        field, vault.for_conversation("conv-bare-B").with_pseudonym_scope("customer")))["street"]
    assert declared == "Ольгина", declared

    # ПЛЕЧО, КОТОРОЕ НЕ НАЗВАЛО РАЗГОВОРА, СТОИТ НЕ ВО ВСЕХ, А НИ В ОДНОМ.
    # `/mask` выводит разговор из самой переписки, когда хост его не назвал;
    # у `/unmask` переписки нет, и правило, написанное как «пустая область —
    # значит сравнивать не с чем», выключало сужение ровно там, где значение
    # ОТДАЮТ. Половина пути была закрыта.
    nameless = json.loads(unmask_arguments(field, vault))["street"]
    assert "Ольгина" not in nameless, nameless
    assert nameless == "Каштановая", nameless

    # И ОТКАЗ ВИДЕН. Цена сужения, записанная в D-067, — «улица возвращается
    # ВИДИМЫМ остатком вместо тихой чужой улицы»; пока `surviving_substitutes` не
    # знал об отказе, в инструмент уходил фейк при 200 и пустом списке, то есть
    # ровно та тишина, ради которой список и заведён.
    written = json.loads(field)["street"]
    for asked in (vault, vault.for_conversation("conv-bare-Z")):
        left = surviving_substitutes(
            written, json.loads(unmask_arguments(field, asked))["street"], asked, True)
        assert left == ["Каштановая"], left
    # …и своему диалогу отвечать есть чем, поэтому остатка там нет.
    home = vault.for_conversation("conv-bare-A")
    assert surviving_substitutes(
        written, json.loads(unmask_arguments(field, home))["street"], home, True) == []

    # СТРОЧНАЯ УЛИЦА, СТОЯЩАЯ ОДНА, — ЭТО НИЖНЯЯ ПОЛОВИНА СИГНАЛА, И ЕЁ НИКТО
    # НЕ ПРОВЕРЯЛ. Заглавную «Каштановую» предлагает `_name_windows`, поэтому
    # проверки выше держались бы и с вырезанной строчной половиной; а в поле
    # схемы подмена стоит ровно строчной — карточка CRM хранит «солнечная», и
    # подмена согласуется с полем. Восстановление предлагает такое окно только
    # на плече АРГУМЕНТА (`_tool_windows`), и сигнал обязан спрашивать ровно то
    # же: остаток, которого он не предложил, — это фейк в инструменте при 200 и
    # пустом списке.
    lower = json.dumps({"street": "каштановая"}, ensure_ascii=False)
    for asked in (vault, vault.for_conversation("conv-bare-Z")):
        stood = json.loads(unmask_arguments(lower, asked))["street"]
        assert stood == "каштановая", stood
        assert surviving_substitutes("каштановая", stood, asked, True) == ["каштановая"], \
            surviving_substitutes("каштановая", stood, asked, True)
        # …И ГРАНИЦА ТОЖЕ ЗАКРЕПЛЕНА: в ПРОЗЕ это окно не предлагается ни
        # восстановлением, ни сигналом — иначе перед волтом встал бы абзац слов.
        assert surviving_substitutes("каштановая", stood, asked, False) == [], \
            surviving_substitutes("каштановая", stood, asked, False)
    # И ВТОРАЯ ПОЛОВИНА ПРАВИЛА: ЕДИНСТВЕННЫЙ КАНДИДАТ ОТВЕЧАЕТ. Отказ всему,
    # что не назвало разговора, молча ломает документированного клиента
    # сайдкара (`docs/integration-diva-backend-api.md`), который
    # `conversation_id` не шлёт вовсе. У заказчика, где про эту улицу говорил
    # ОДИН диалог, кандидат один — и тогда ответ безопасен ровно по той же
    # причине, по которой область разговора вообще работает.
    only = Vault(":memory:", _ORG)
    try:
        secrets.choice = forcing("Каштановой")
        alone_masked = mask_one(first_said, _context(detector, only, "conv-only-A"))
    finally:
        secrets.choice = real_choice
    assert "Каштановая" in alone_masked, alone_masked
    answered = json.loads(unmask_arguments(field, only))["street"]
    assert answered == "Ольгина", answered
    assert surviving_substitutes("Каштановая", answered, only, True) == [], \
        surviving_substitutes("Каштановая", answered, only, True)

    print("вырожденный ключ улицы OK — чужой диалог получает свою улицу, свой — первую; "
          "плечо без разговора — единственный кандидат, двусмысленность — видимый остаток "
          "(и строчная улица в аргументе тоже); "
          "полный адрес остаётся общим, объявленная память агента — тоже")


def test_two_addresses_on_one_fake_street(detector: Detector) -> None:
    """ДВЕ ПОДМЕНЫ НА ОДНОЙ ФЕЙКОВОЙ УЛИЦЕ — ЭТО ДВА КАНДИДАТА, А НЕ «ПОЗДНИЙ».

    Внутри ОДНОГО разговора две строки на одной улице — это исправленный дом, и
    поздняя из них та, на которой заказчик остановился: `place_owner_by_street`
    отдаёт её намеренно. Между РАЗНЫМИ диалогами «позже» не значит ничего, кроме
    «кто-то другой говорил последним», и плечо, разговора не назвавшее, получило
    бы вместе с улицей ЧУЖОЙ НОМЕР ДОМА — та же выдача, что Б28, только другой
    дорогой.

    И отказ должен быть СЛЫШЕН. Отказ здесь — не по чужому диалогу, а по
    двусмысленности: улицу носят две наши подмены сразу, и ни одна из них не
    единственная. Называет его `place_fragment_is_ours`, спрошенный о том, что
    написал агент; без него в инструмент уходил фейк при 200 и пустом списке.

    Подмена тянется случайно, поэтому улица здесь закреплена, а не разыграна.
    """
    import secrets  # noqa: PLC0415

    real_choice = secrets.choice

    def forcing(want: str):
        def choice(seq):
            seq = list(seq)
            return want if want in seq else real_choice(seq)
        return choice

    vault = Vault(":memory:", _ORG)
    try:
        secrets.choice = forcing("Каштановой")
        first = mask_one("доставка на улицу Ольгина 5 кв 1", _context(detector, vault, "conv-two-A"))
        second = mask_one("доставка на улицу Ольгина 91 кв 62", _context(detector, vault, "conv-two-B"))
    finally:
        secrets.choice = real_choice
    assert "Каштанов" in first and "Каштанов" in second, (first, second)

    # Дом агент пишет СВОЙ — такой, какого нет ни в одной подмене: иначе
    # владельца назвал бы он (`place_owner` по числу), и проверялась бы не та
    # дорога. Номера в подменах разыгрываются, поэтому он ищется, а не берётся.
    minted = [row[0] for row in vault._conn.execute(
        "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC'", (_ORG,)).fetchall()]
    house = next(str(number) for number in range(300, 400)
                 if all(str(number) not in token for token in minted))
    field = json.dumps({"street": "Каштановая", "house": house}, ensure_ascii=False)
    for tag, asked in (("без разговора", vault), ("чужой диалог", vault.for_conversation("conv-two-Z"))):
        out = json.loads(unmask_arguments(field, asked))
        assert out["street"] == "Каштановая", (tag, out)
        assert out["house"] == house, (tag, out)
        assert "Ольгина" not in json.dumps(out, ensure_ascii=False), (tag, out)
        left = surviving_substitutes("Каштановая", out["street"], asked, True)
        assert left == ["Каштановая"], (tag, left)

    # …и каждому своему диалогу волт по-прежнему отвечает СВОИМ адресом — с его
    # собственным домом, а не с домом соседнего разговора.
    for conversation, real_house in (("conv-two-A", "5"), ("conv-two-B", "91")):
        mine = vault.for_conversation(conversation)
        out = json.loads(unmask_arguments(field, mine))
        assert out["street"] == "Ольгина", (conversation, out)
        assert out["house"] == real_house, (conversation, out)
        assert surviving_substitutes("Каштановая", out["street"], mine, True) == []
    print("две подмены на одной улице OK — «поздняя побеждает» осталось правилом одного "
          "разговора; чужому и безымянному плечу — отказ с видимым остатком")


def _forcing(*sticky: str):
    """Вернуть замену `secrets.choice`, которая тянет ИМЕННО эти слова.

    Подмена тянется случайно, а здесь важно, КАКОЕ название выпало двум
    разговорам: без закрепления дефект ловился бы раз в сорок прогонов.
    Вызывающий обязан вернуть настоящую функцию в `finally` — `secrets.choice`
    общий на процесс.
    """
    import secrets  # noqa: PLC0415

    real_choice = secrets.choice

    def choice(seq):
        seq = list(seq)
        for want in sticky:
            if want in seq:
                return want
        return real_choice(seq)

    return choice


def test_a_correct_restoration_raises_no_alarm(detector: Detector) -> None:
    """ДВУСМЫСЛЕННОСТЬ — ПРО ПОДМЕНУ, А НЕ ПРО ВОССТАНОВЛЕННОЕ ЗНАЧЕНИЕ.

    Сигнал остатка спрашивался по окнам УЖЕ ВОССТАНОВЛЕННОГО текста, а волт на
    вопрос «эту основу носят несколько моих подмен?» отвечает одинаково и про
    нашу подмену, и про НАСТОЯЩУЮ улицу заказчика, которой случайно досталось
    то же название. Получалось «не исполняй вызов» на ПРАВИЛЬНОМ восстановлении
    — 5 из 50 диалогов документированного клиента, — а сигнал, который кричит
    зря, хуже молчания: мы сами пишем в документации, что непустой
    `residual_tokens` есть основание отказаться от вызова инструмента.

    Здесь это собрано руками: двум разговорам выпадает фейковая «Кленовая», а
    третий говорит про НАСТОЯЩУЮ Кленовую. Его собственный адрес возвращается
    целиком и верно — и именно про него поднималась тревога.
    """
    import secrets  # noqa: PLC0415

    real_choice = secrets.choice
    vault = Vault(":memory:", _ORG)
    try:
        secrets.choice = _forcing("Кленовой", "Кленовая")
        mask_one("адрес ольгина 14", _context(detector, vault, "conv-alarm-A"))
        mask_one("адрес изобильная 60", _context(detector, vault, "conv-alarm-B"))
    finally:
        secrets.choice = real_choice
    owners = [row[0] for row in vault._conn.execute(
        "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC'", (_ORG,)).fetchall()]
    assert sum("леновая" in token.lower() for token in owners) >= 2, owners

    # А ТЕПЕРЬ НАСТОЯЩАЯ КЛЕНОВАЯ — улица заказчика, а не наша.
    real_talk = _context(detector, vault, "conv-alarm-real")
    masked = mask_one("адрес кленовая 77 кв 4", real_talk)
    fake = masked.split("адрес ", 1)[1].strip()
    assert "кленовая" not in fake.lower(), fake
    asked = vault.for_conversation("conv-alarm-real")
    written = json.dumps({"address": fake}, ensure_ascii=False)
    restored = unmask_arguments(written, asked)
    back = json.loads(restored)["address"]
    assert "кленовая" in back.lower() and "77" in back, back
    # Восстановление правильное — значит остатка нет. Вопрос задан о том, что
    # НАПИСАЛ АГЕНТ, и написанное разрешилось, поэтому спрашивать больше не о чем.
    assert surviving_substitutes(written, restored, asked, True) == [], \
        surviving_substitutes(written, restored, asked, True)
    print("ложная тревога OK — правильное восстановление не поднимает остаток, "
          "даже когда настоящая улица носит имя двух наших подмен")


def test_every_class_of_refused_fragment_is_visible(detector: Detector) -> None:
    """ФРАГМЕНТ, КОТОРЫЙ НЕ РАЗРЕШИЛСЯ, ОБЯЗАН БЫТЬ НАЗВАН — ЛЮБОГО ТИПА.

    Виден был только отказ по УЛИЦЕ. Номер дома и цифровой хвост отказывали
    молча — 22 и 6 из 50 у документированного клиента, — потому что вопрос о
    них не задавался вовсе: ключ с цифрами исключался как «отвечающий по всему
    заказчику», а это про ОБЛАСТЬ, а не про то, наша ли это строка. Дата —
    третий такой класс: агент переписывает её в свою нотацию, точная подмена
    больше не совпадает, и владельца ищет `date_owner`.

    Отказ здесь делает ЧУЖОЙ разговор: он детерминирован, в отличие от
    случайного совпадения двух подмен, и это ровно тот отказ, который клиент
    видит чаще всего.
    """
    vault = Vault(":memory:", _ORG)
    # ДАТА СКАЗАНА СЛОВАМИ НАМЕРЕННО. Подмена цифровой даты — это цифровая
    # дата, то есть ЦЕЛЫЙ токен, и она разрешается по всему заказчику по
    # праву: назвать её мог только тот, кому мы её отдали. Фрагментом дата
    # становится ровно тогда, когда агент переписывает СКАЗАННУЮ подмену
    # цифрами — тогда точного токена нет, и отвечает `date_owner` по
    # каноническому прочтению.
    said = ("клиент по адресу ольгина 14 кв 7, телефон +7 912 345-67-89, "
            "дата рождения четырнадцатого марта восемьдесят пятого года")
    masked = mask_one(said, _context(detector, vault, "conv-vis-A"))
    rows = {row[0]: row[1] for row in vault._conn.execute(
        "SELECT entity_type, token FROM tokens WHERE customer=? AND minted_in=?",
        (_ORG, "conv-vis-A")).fetchall()}
    assert {"LOC", "PHONE", "DOB"} <= set(rows), (rows, masked)
    house = next(word.strip(".,") for word in rows["LOC"].split()
                 if word.strip(".,").isdigit())
    tail = "".join(character for character in rows["PHONE"] if character.isdigit())[-4:]
    spoken = [row[0] for row in vault._conn.execute(
        "SELECT part FROM token_parts WHERE customer=? AND token=?",
        (_ORG, rows["DOB"])).fetchall()]
    day, month, year = next(part for part in spoken if part.count(".") == 2).split(".")
    stranger = vault.for_conversation("conv-vis-Z")

    cases = {
        # дом без улицы: `place_owner` внутри чужого разговора не находит строку
        "house": (house, "номер дома"),
        # цифровой хвост: `digit_fragment_owner` — то же самое для цифр
        "last_digits": (tail, "хвост телефона"),
        # дата в ДРУГОЙ нотации: точная подмена больше не совпадает, отвечает
        # `date_owner` по каноническому прочтению — и тоже отказывает
        "birth_date": (f"{year}-{month}-{day}", "дата в нотации агента"),
    }
    for key, (value, what) in cases.items():
        written = json.dumps({key: value}, ensure_ascii=False)
        restored = unmask_arguments(written, stranger)
        assert json.loads(restored)[key] == value, (what, restored)
        left = surviving_substitutes(written, restored, stranger, True)
        assert left == [value], (what, left)

    # …И СВОЕМУ РАЗГОВОРУ ВСЕ ТРИ ОТВЕЧАЮТ, поэтому остатка там нет: проверка,
    # которая не умеет молчать, ничего не измеряет.
    home = vault.for_conversation("conv-vis-A")
    for key, (value, what) in cases.items():
        written = json.dumps({key: value}, ensure_ascii=False)
        restored = unmask_arguments(written, home)
        assert json.loads(restored)[key] != value, (what, restored)
        assert surviving_substitutes(written, restored, home, True) == [], (what, restored)
    print("видимость OK — дом, цифровой хвост и дата в чужой нотации отказывают "
          "ВИДИМО, а своему разговору по-прежнему отвечают")


def test_declared_memory_reaches_the_fragment_lookups(detector: Detector) -> None:
    """ОБЪЯВЛЕННАЯ ПАМЯТЬ АГЕНТА — СНАЧАЛА СВОЙ РАЗГОВОР, ПОТОМ ВЕСЬ ЗАКАЗЧИК.

    `with_pseudonym_scope("customer")` до фрагментных поисков не доходил вовсе:
    целая подмена узнавалась по всему заказчику, а её ЧАСТЬ по-прежнему искалась
    только в своём разговоре. Хост с памятью получал половину настройки.

    Наивное расширение ломает того же хоста иначе, и это вторая половина
    проверки: у двух разговоров одна фейковая улица, и «спрашиваем сразу весь
    волт» дало бы двух кандидатов — СОБСТВЕННЫЙ адрес перестал бы разрешаться,
    как только другой диалог упомянул ту же улицу. Поэтому шага два.
    """
    import secrets  # noqa: PLC0415

    real_choice = secrets.choice
    vault = Vault(":memory:", _ORG)
    try:
        secrets.choice = _forcing("Кедровой", "Кедровая")
        # ПОЛНЫЕ АДРЕСА, А НЕ ГОЛАЯ УЛИЦА, И ЭТО УСЛОВИЕ ПРОВЕРКИ. Голая улица
        # — это ЦЕЛЫЙ токен, а целую подмену объявленная память узнаёт и без
        # фрагментных поисков (`_answers_another_dialogue`); спрашивать надо о
        # том, что целым токеном не является.
        mask_one("адрес ольгина 14 кв 7",
                 _context(detector, vault, "conv-mem-A", "customer"))
        mask_one("адрес изобильная 60 кв 186",
                 _context(detector, vault, "conv-mem-C", "customer"))
    finally:
        secrets.choice = real_choice
    field = json.dumps({"street": "Кедровая"}, ensure_ascii=False)

    # ШАГ ПЕРВЫЙ. Свой разговор отвечает СВОИМ адресом и ни с кем не
    # соревнуется — хотя ту же фейковую улицу носит и второй разговор.
    for conversation, want in (("conv-mem-A", "ольгин"), ("conv-mem-C", "изобильн")):
        mine = vault.for_conversation(conversation).with_pseudonym_scope("customer")
        got = json.loads(unmask_arguments(field, mine))["street"]
        assert want in got.lower(), (conversation, got)
        assert surviving_substitutes("Кедровая", got, mine, True) == [], (conversation, got)

    # ШАГ ВТОРОЙ. У диалога, который эту улицу не видел, дома ответа нет — и
    # тогда спрашивается весь заказчик. Кандидатов двое, значит отказ, и он
    # ВИДЕН: расширение не делает правило слабее, оно делает его вторым шагом.
    stranger = vault.for_conversation("conv-mem-Z").with_pseudonym_scope("customer")
    stood = json.loads(unmask_arguments(field, stranger))["street"]
    assert stood == "Кедровая", stood
    assert surviving_substitutes("Кедровая", stood, stranger, True) == ["Кедровая"], stood

    # …А ТАМ, ГДЕ КАНДИДАТ ОДИН, второй шаг отвечает — ради этого он и заведён.
    alone = Vault(":memory:", _ORG)
    try:
        secrets.choice = _forcing("Кедровой", "Кедровая")
        mask_one("адрес ольгина 14 кв 7",
                 _context(detector, alone, "conv-solo-A", "customer"))
    finally:
        secrets.choice = real_choice
    elsewhere = alone.for_conversation("conv-solo-B").with_pseudonym_scope("customer")
    answered = json.loads(unmask_arguments(field, elsewhere))["street"]
    assert "ольгин" in answered.lower(), answered
    # …и БЕЗ объявления памяти тот же вопрос из чужого разговора отказывает.
    plain = alone.for_conversation("conv-solo-B")
    assert json.loads(unmask_arguments(field, plain))["street"] == "Кедровая"
    print("объявленная память OK — фрагмент отвечает сначала в своём разговоре, "
          "потом единственным кандидатом по заказчику; двусмысленность видна")


def test_the_public_signal_keeps_its_two_argument_shape(detector: Detector) -> None:
    """ПУБЛИЧНАЯ ФУНКЦИЯ С ВНЕШНИМ ВЫЗЫВАЮЩИМ ФОРМУ НЕ МЕНЯЕТ.

    `redact.residual_tokens` зовёт `bench/agentpii4/gateway.py` — плечо шлюза в
    базе сравнения, которую мы не правим. Расширенная проверка получила там
    четыре аргумента, и плечо падало `TypeError` на КАЖДОМ кейсе с вызовом
    инструмента: бенчмарк не показывал ухудшения, он просто не считался.

    Поэтому здесь закреплена ровно та форма, которой пользуется внешний
    вызывающий: один текст, один волт. Плечевая проверка живёт под своим
    именем (`surviving_substitutes`) и может меняться сколько угодно.
    """
    vault = Vault(":memory:", _ORG)
    masked = mask_one("клиент Ольга Ольгина, телефон +7 912 345-67-89",
                      _context(detector, vault, "conv-shape-A"))
    asked = vault.for_conversation("conv-shape-A")
    # Ровно как зовёт база сравнения: значение листа и волт, больше ничего.
    left = residual_tokens(masked, asked)
    assert left, (masked, left)
    # …а то, что разрешилось, остатком не называется.
    assert residual_tokens(unmask_text(masked, asked), asked) == []
    print("форма сигнала OK — публичная функция принимает два аргумента, "
          "как её зовёт база сравнения бенчмарка")


def test_a_number_under_a_role_no_substitute_wears_is_not_ours(detector: Detector) -> None:
    """ЧИСЛО, КОТОРОГО ШЛЮЗ НЕ ЧЕКАНИЛ, ОСТАТКОМ НЕ НАЗЫВАЕТСЯ (Б28ter).

    Вопрос задавался ПО ФОРМЕ: «носит ли такую цифру хоть какая-нибудь адресная
    подмена». Номер квартиры из СКЛАДСКОЙ карточки заказчика находил подмену, у
    которой это число — НОМЕР ДОМА, и правильный вызов получал «не исполняй».
    Восстановление такое поле даже не трогает — оно роль проверяет, — то есть
    докладывалось об отказе, которого не было: 10 из 21 ложной тревоги
    документированного клиента ровно этот класс.

    Роль — часть вопроса. Наши адресные подмены квартир не несут вовсе, значит
    ни одно число под ключом `flat` не наше.
    """
    vault = Vault(":memory:", _ORG)
    mask_one("адрес ольгина 14", _context(detector, vault, "conv-role-A"))
    token = vault._conn.execute(
        "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC'",
        (_ORG,)).fetchone()[0]
    house = next(word.strip(".,") for word in token.split() if word.strip(".,").isdigit())
    stranger = vault.for_conversation("conv-role-Z")

    # То же самое число под ключом `flat` — это квартира со склада заказчика.
    written = json.dumps({"flat": house}, ensure_ascii=False)
    restored = unmask_arguments(written, stranger)
    assert json.loads(restored)["flat"] == house, restored
    assert surviving_substitutes(written, restored, stranger, True) == [], \
        surviving_substitutes(written, restored, stranger, True)

    # …а под ключом `house` оно остаётся видимым: это ровно та подмена, которую
    # чужому разговору не разрешить, и молчать о ней нельзя.
    as_house = json.dumps({"house": house}, ensure_ascii=False)
    back = unmask_arguments(as_house, stranger)
    assert json.loads(back)["house"] == house, back
    assert surviving_substitutes(as_house, back, stranger, True) == [house]
    print("роль OK — число под ключом, которого ни одна подмена не носит в этой "
          "роли, тревоги не поднимает; под своим ключом — поднимает")


def test_a_refused_house_is_visible_in_prose_too(detector: Detector) -> None:
    """ОТКАЗ ВИДЕН НА ОБОИХ ПЛЕЧАХ, А НЕ ТОЛЬКО В АРГУМЕНТЕ.

    Номер дома в ПРОЗЕ — «Дом 47.» — уходил молча: подсказки «дом»/«кв.»
    выбрасывались из набора кандидатов сигнала целиком, хотя восстановление
    читает их и по ним же ищет владельца (`_restore_cued_numbers_spans`). 22 из
    50 домов документированного клиента терялись на прозаическом плече, пока
    тот же самый отказ в аргументе назывался вслух.
    """
    vault = Vault(":memory:", _ORG)
    mask_one("адрес ольгина 14", _context(detector, vault, "conv-prose-A"))
    token = vault._conn.execute(
        "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC'",
        (_ORG,)).fetchone()[0]
    house = next(word.strip(".,") for word in token.split() if word.strip(".,").isdigit())
    stranger = vault.for_conversation("conv-prose-Z")

    said = f"Дом {house}."
    restored = unmask_text(said, stranger)
    assert restored == said, restored
    assert surviving_substitutes(said, restored, stranger, False) == [house], \
        surviving_substitutes(said, restored, stranger, False)

    # …и своему разговору проза по-прежнему отвечает, поэтому остатка там нет.
    home = vault.for_conversation("conv-prose-A")
    answered = unmask_text(said, home)
    assert answered != said, answered
    assert surviving_substitutes(said, answered, home, False) == [], answered
    print("проза OK — отказ по дому назван и в прозе, а не только в аргументе")


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    detector.detect("прогрев")
    test_substitute_is_never_a_real_value()
    test_substitute_is_never_the_value_it_replaces()
    test_real_person_named_like_a_substitute_is_masked(detector)
    test_memory_recall_across_conversations(detector)
    test_echo_in_its_own_conversation_is_left_alone(detector)
    test_migrated_vault_keeps_the_old_behaviour(detector)
    test_pool_is_not_narrowed_by_the_extra_rejections()
    test_two_people_in_one_dialogue_never_share_a_fake_surname(detector)
    test_b23_customer_word_equal_to_another_dialogue_substitute(detector)
    test_a_bare_street_answers_only_in_its_own_dialogue(detector)
    test_two_addresses_on_one_fake_street(detector)
    test_a_correct_restoration_raises_no_alarm(detector)
    test_every_class_of_refused_fragment_is_visible(detector)
    test_declared_memory_reaches_the_fragment_lookups(detector)
    test_the_public_signal_keeps_its_two_argument_shape(detector)
    test_a_number_under_a_role_no_substitute_wears_is_not_ours(detector)
    test_a_refused_house_is_visible_in_prose_too(detector)
    print("\nвсе проверки коллизий пройдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
