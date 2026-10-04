"""ПРОИЗВОДНАЯ ПОДМЕНЫ В АРГУМЕНТЕ ИНСТРУМЕНТА: транслит и инициалы.

Модель пишет `name_latin` и `cardholder` не по стандарту, а по буквам:
«Meshcheryakova» — щ по ICAO и я по бытовому написанию, «Dmitry» — окончание,
которого нет ни в одной таблице. Живой замер 05.09 (1053 тройки) показал два
следствия: подмена, проиндексированная четырьмя табличными написаниями, не
находилась по пятому и уходила в CRM полуживой («Meshcheryakova Anna»); а где
несколько таблиц объясняли слово модели одинаково, побеждала первая, и в
настоящее имя записывалось «iu» из ICAO против «yu», которое написал бы сам
агент — 38 троек, в 33 из них оба контроля сходились между собой.

Инициалы ломались иначе: ключ «то» из двух букв в общем на клиента хранилище
принадлежит многим подменам, «единственного владельца нет» — и подмена ушла
в инструмент. Разговор, в котором подмена выдана, и есть недостающий
дискриминатор.

Здесь закреплено: (1) имя возвращается В ТОЙ ЖЕ конвенции, какую модель
применила к подмене; (2) буква, которой в подмене не было, пишется так, как
контрольное плечо писало её чаще всего; (3) инициалы разрешаются внутри
разговора даже когда по всему клиенту они неоднозначны, и НЕ разрешаются,
когда неоднозначны внутри одного разговора; (4) чужое латинское слово не
трогается.

    python3 test_derived_forms.py
"""
import json
from unittest.mock import patch

import testkit

testkit.load_dev_bundle()

from pseudex import morph_names, translit  # noqa: E402
from pseudex.assets import ASSETS  # noqa: E402
from pseudex.redact import unmask_arguments  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

# THE MODEL'S OWN MIXED CONVENTION, as the control arm wrote it: щ→shch, я→ya,
# ю→yu, й→y, ё→e, soft sign dropped. Not one of the four standards.
MODEL_STYLE: dict[str, str] = {"щ": "shch", "я": "ya", "ю": "yu", "й": "y", "ё": "e",
                               "ь": "", "х": "kh", "ц": "ts", "ий": "iy", "ия": "iya"}
AMBIGUOUS = set("юяйёщхцъ") | {"ий", "ый", "ия", "кс", "йя"}


def _check(label: str, got: object, want: object) -> bool:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        print(f"      получили {got!r}\n      ждали    {want!r}")
    return ok


def _given_patronymic(name: str) -> tuple[str, str]:
    words, shape = name.split(), morph_names.name_shape(name)
    given = next(w for w, k in zip(words, shape) if k == "name")
    patronymic = next(w for w, k in zip(words, shape) if k == "patr")
    return given, patronymic


def _model_writes(fake: str, style: dict[str, str], caps: bool) -> str:
    out = " ".join(translit.render(w, style) for w in fake.split())
    return out.upper() if caps else " ".join(w.capitalize() for w in out.split())


def _restore(vault: Vault, args: dict) -> dict:
    return json.loads(unmask_arguments(json.dumps(args, ensure_ascii=False), vault))["contact"]


def main() -> int:
    failures = 0

    # (1) the whole name comes back in the model's convention, whatever the fake
    real = "соколова анна игоревна"
    vault = Vault(":memory:", "acme").for_conversation("c1")
    fake = vault.tokenize(real, "NAME")
    for w in ("Соколова", "Анна", "Игоревна"):      # the CRM record, field by field
        vault.tokenize(w, "NAME")
    given, patronymic = _given_patronymic(fake)
    written = {"contact": {"name_latin": _model_writes(fake, MODEL_STYLE, caps=False),
                           "initials": f"{given[0]}.{patronymic[0]}."}}
    got = _restore(vault, written)
    failures += not _check("транслит целого имени в конвенции модели", got["name_latin"],
                           _model_writes(real, MODEL_STYLE, caps=False))
    failures += not _check("инициалы настоящего человека", got["initials"], "А.И.")

    # (2) a letter the fake never carried is written the way the control arm writes it
    real = "зинаида битюкова"
    for _attempt in range(40):
        vault = Vault(":memory:", "acme").for_conversation("c1")
        fake = vault.tokenize(real, "NAME")
        if not any(unit in AMBIGUOUS for w in fake.split() for unit in translit.units_of(w)):
            break
    else:
        raise RuntimeError("no fake without an ambiguous letter in 40 draws")
    _std = ASSETS.get().translit.tables  # leased now: (ICAO, GOST_B, MVD_2010, COMMON)
    for standard, label in ((_std[0], "модель писала по ICAO"), (_std[1], "модель писала по ГОСТ")):
        latin = " ".join(translit.apply(standard, w).upper() for w in reversed(fake.split()))
        got = _restore(vault, {"contact": {"name_latin": latin}})
        failures += not _check(f"ю, которого в подмене не было → «yu» ({label})",
                               got["name_latin"], "BITYUKOVA ZINAIDA")

    # C05: a saved random draw whose units passed the old filter but whose
    # Latin rendering resolved only the surname. The fake must not reach CRM.
    with patch("pseudex.vault._fake_name", return_value="Майя Устинова"):
        pinned = Vault(":memory:", "c05-mayya").for_conversation("one")
        assert pinned.tokenize(real, "NAME") == "Майя Устинова"
    for latin in ("USTINOVA MAIIA", "USTINOVA MAJYA", "USTINOVA MAYYA"):
        got = _restore(pinned, {"contact": {"name_latin": latin}})
        failures += not _check(f"зафиксированная Майя {latin} не оставляет fake-имя в CRM",
                               got["name_latin"], "BITYUKOVA ZINAIDA")

    # C05, THE SAME CLASS ONE UNIT OVER. «йя» was one hole in the derived-form
    # INDEX, and it was not the only one: the index held the fold of the
    # DEFAULT rendering only, while `UNITS` declares several spellings per unit
    # and a string-level fold cannot unify some of them («j» is both ГОСТ's «й»
    # and the everyday «ж»). Each of these came back as a FAKE given name
    # beside a real surname — «MIHAIL PETROV» for a person who does not exist.
    # Pinning only the «йя» literal would have left the class open, so the fix
    # is the index closure and these are its fixtures.
    for real_name, fake_name, latin_name, expected_name in (
        ("александр петров", "Михаил Жуков", "MIHAIL ZHUKOV", "ALEKSANDR PETROV"),
        ("пётр соколов", "Фёдор Кузнецов", "FIODOR KUZNETSOV", "PIOTR SOKOLOV"),
        ("николай егоров", "Надежда Жукова", "NADEJDA ZHUKOVA", "NIKOLAY EGOROV"),
    ):
        with patch("pseudex.vault._fake_name", return_value=fake_name):
            pinned = Vault(":memory:", f"c05-{latin_name}").for_conversation("one")
            assert pinned.tokenize(real_name, "NAME") == fake_name
        got = _restore(pinned, {"contact": {"name_latin": latin_name}})
        failures += not _check(f"зафиксированная {fake_name} как {latin_name} не оставляет fake-имя",
                               got["name_latin"], expected_name)

    # (2b) the ending the fake DID carry is carried over: Dmitry → Yury
    real = "юрий савельев"
    for _attempt in range(200):
        vault = Vault(":memory:", "acme").for_conversation("c1")
        fake = vault.tokenize(real, "NAME")
        if any("ий" in translit.units_of(w) for w in fake.split()):
            break
    else:
        raise RuntimeError("no fake ending in -ий in 200 draws")
    latin = " ".join(translit.render(w, {"ий": "y", "ё": "e"}).capitalize() for w in fake.split())
    got = _restore(vault, {"contact": {"name_latin": latin}})
    # ь is dropped (149:0 on the control arm), so «Савельев» is «Savelev»
    failures += not _check("окончание -ий→y, подсмотренное у подмены, переносится на Юрий",
                           got["name_latin"], "Yury Savelev")

    # (3) initials: ambiguous across the customer, decided by the conversation
    vault = Vault(":memory:", "acme")
    first = vault.for_conversation("c1").tokenize("соколова анна игоревна", "NAME")
    key = translit.squeezed_initials(_given_patronymic(first))
    others = ("новикова наталья петровна", "букин сергей иванович", "ерохина марина львовна",
              "битюков олег викторович", "заболотный руслан фёдорович", "воронина елена сергеевна")
    collided = None
    # A PROBABILISTIC SEARCH, AND THE BOUND WAS MEASURED WRONG. The comment
    # said 1500 draws find a collision «with near certainty»; measured over
    # five runs it missed one in five, and a gate that fails one run in five is
    # not a gate — it sends the next reader after a defect that is not there.
    # The pool of distinct initial pairs is bigger than the 600 assumed, so the
    # bound is raised until a miss is negligible; a miss still raises rather
    # than passing quietly, because the check below is what this half exists
    # for.
    for attempt in range(9000):
        other = others[attempt % len(others)]
        scope = vault.for_conversation(f"other-{attempt}")
        # a different person each time: the canonical carries the attempt so a
        # repeated real name is not one row reused
        token = scope.tokenize(f"{other.split()[0]}{attempt} {other.split()[1]} {other.split()[2]}", "NAME")
        if translit.squeezed_initials(_given_patronymic(token)) == key:
            collided = token
            break
    if collided is None:
        raise RuntimeError("no colliding initials in 9000 draws — the pool grew or "
                           "the minting changed; raise the bound deliberately")
    given, patronymic = _given_patronymic(first)
    got = _restore(vault.for_conversation("c1"), {"contact": {"initials": f"{given[0]}.{patronymic[0]}."}})
    failures += not _check("инициалы неоднозначны по клиенту — разговор решает", got["initials"], "А.И.")
    got = _restore(vault, {"contact": {"initials": f"{given[0]}.{patronymic[0]}."}})
    failures += not _check("без разговора неоднозначность остаётся неразрешённой",
                           got["initials"], f"{given[0]}.{patronymic[0]}.")
    # the same pair twice INSIDE one conversation: the dialogue cannot say who
    # Bounded low: every mint INSIDE one conversation refuses the stems already
    # used there, so the search slows as it goes; the check is conditional.
    scope = vault.for_conversation("c1")
    second = None
    for attempt in range(60):
        other = others[attempt % len(others)]
        token = scope.tokenize(f"{other.split()[0]}z{attempt} {other.split()[1]} {other.split()[2]}", "NAME")
        if translit.squeezed_initials(_given_patronymic(token)) == key:
            second = token
            break
    if second is not None:
        got = _restore(scope, {"contact": {"initials": f"{given[0]}.{patronymic[0]}."}})
        failures += not _check("две подмены одного разговора с одними инициалами — отказ, не догадка",
                               got["initials"], f"{given[0]}.{patronymic[0]}.")

    # (3b) a SINGLE initial is nobody's key; the name beside it in the same call is
    vault = Vault(":memory:", "acme").for_conversation("c1")
    fake = vault.tokenize("букин сергей", "NAME").split()
    got = _restore(vault, {"contact": {"last_name": fake[0], "first_name": fake[1], "initials": f"{fake[1][0]}."}})
    failures += not _check("одиночный инициал — от имени в том же вызове", got["initials"], "С.")
    foreign = "Ж." if fake[1][0] != "Ж" else "Щ."
    got = _restore(vault, {"contact": {"first_name": fake[1], "initials": foreign}})
    failures += not _check("инициал не подмены остаётся клиентским", got["initials"], foreign)
    fake = Vault(":memory:", "acme").for_conversation("c1")
    vault = fake
    words = vault.tokenize("соколова анна игоревна", "NAME").split()
    got = _restore(vault, {"contact": {"first_name": words[1], "middle_name": words[2],
                                       "initials": f"{words[1][0]}. {words[2][0]}."}})
    failures += not _check("пара инициалов с пробелом — пунктуация модели сохранена", got["initials"], "А. И.")

    # (4) a Latin name that is nobody's substitute stays as written
    vault = Vault(":memory:", "acme").for_conversation("c1")
    vault.tokenize("соколова анна игоревна", "NAME")
    got = _restore(vault, {"contact": {"name_latin": "Karenina Leo Tolstoevich"}})
    failures += not _check("чужая латиница не трогается", got["name_latin"], "Karenina Leo Tolstoevich")

    print()
    if failures:
        print(f"НЕ ПРОШЛО: {failures}")
        return 1
    print("производные подмены возвращаются производными настоящего значения в конвенции модели")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
