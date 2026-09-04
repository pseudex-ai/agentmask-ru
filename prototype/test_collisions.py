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
import random
import sys

import testkit
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, mask_one
from pseudex.maskcache import MaskCache
from pseudex.redact import mask_text, unmask_text
from pseudex.vault import Vault

_ORG = "collide"


def _context(detector: Detector, vault: Vault, conversation: str) -> MaskContext:
    return MaskContext(detector=detector, vault=vault.for_conversation(conversation),
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


def main() -> int:
    testkit.load_dev_bundle()
    detector = Detector()
    detector.detect("прогрев")
    test_substitute_is_never_a_real_value()
    test_substitute_is_never_the_value_it_replaces()
    test_real_person_named_like_a_substitute_is_masked(detector)
    test_echo_in_its_own_conversation_is_left_alone(detector)
    test_migrated_vault_keeps_the_old_behaviour(detector)
    test_pool_is_not_narrowed_by_the_extra_rejections()
    test_two_people_in_one_dialogue_never_share_a_fake_surname(detector)
    print("\nвсе проверки коллизий пройдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
