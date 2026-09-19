"""Value pools the generator draws from, with the TIER of every name.

Everything here comes from the snapshots under `pools/` (Wikidata CC0, NEN
CC BY 4.0, mimesis and Faker MIT) and from two short hand lists in this file.
Nothing comes from a masker's gazetteer — see `pools/build_pools.py` for why.

TIERS. A benchmark of names that every gazetteer holds cannot fail against
any gazetteer, so a name carries where it came from:

  common      NEN «top» and «popular» given names (ZAGS newborn statistics),
              Faker/mimesis surnames — the head of the distribution
  tail        NEN «rare» and Wikidata-only given names, Wikidata-only surnames
              (Курбан, Наиль, Биляна; Блювштейн, Билык) — real, uncommon
  diminutive  NEN short forms of common names (Саша, Таня, Лёва)
  foreign     transliterated foreign names, hand list below

The report prints each tier apart, and never averages them into one number.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path

POOLS_DIR = Path(__file__).resolve().parents[2] / "pools"

# Transliterated foreign names as a Russian support desk meets them. A hand
# list, not a gazetteer: the point is that they are NOT in any Russian
# surname dictionary and carry no Russian suffix to guess gender from.
FOREIGN_GIVEN: tuple[tuple[str, str], ...] = (
    ("Джон", "m"), ("Майкл", "m"), ("Ахмед", "m"), ("Ли", "m"), ("Хироси", "m"), ("Матеуш", "m"),
    ("Хавьер", "m"), ("Оливье", "m"), ("Нгуен", "m"), ("Раджеш", "m"), ("Юсуф", "m"), ("Эмре", "m"),
    ("Мария-Хосе", "f"), ("Айгуль", "f"), ("Фатима", "f"), ("Мэй", "f"), ("Ханна", "f"), ("Зейнеп", "f"),
    ("Приянка", "f"), ("Летиция", "f"), ("Сунь", "f"), ("Гюльнара", "f"), ("Ноа", "f"), ("Эмили", "f"),
)
FOREIGN_SURNAMES: tuple[str, ...] = (
    "Смит", "Мюллер", "Гарсия", "Ван", "Танака", "Ковальски", "Нгуен", "Патель", "Йылдыз", "Ахмади",
    "Оливейра", "Шмидт", "Ким", "Хассан", "Дюпон", "Россини", "Окафор", "Аль-Сайед", "Бергман", "Чжан",
)

# Which tier a NEN popularity bucket falls into. Short forms are taken only
# from the «top» bucket: the short forms NEN lists further down («Лорик»,
# «Заня», «Фек») are forms nobody at a support desk has met.
_NEN_TIER: dict[str, str] = {"top": "common", "popular": "common", "medium": "common", "rare": "tail"}
_DIMINUTIVE_BUCKETS: tuple[str, ...] = ("top",)

# Surnames of heads of state and other people a reader would recognise at
# once. A surname is not a person, but a synthetic customer called Путин is
# a distraction in a screenshot, so these never enter the pool.
_EXCLUDED_SURNAMES: frozenset[str] = frozenset({
    "Путин", "Путина", "Ельцин", "Ельцина", "Горбачёв", "Горбачёва", "Сталин", "Сталина", "Ленин", "Ленина",
    "Навальный", "Навальная", "Зеленский", "Зеленская", "Лукашенко", "Мишустин", "Мишустина", "Медведев", "Медведева",
})


@dataclass(frozen=True)
class Given:
    name: str
    gender: str          # "m" | "f"
    tier: str


@dataclass(frozen=True)
class Surname:
    name: str
    gender: str          # "m" | "f" | "u" (used unchanged for either)
    tier: str


@dataclass(frozen=True)
class Street:
    name: str
    type: str            # улица | переулок | ...


@dataclass(frozen=True)
class Pools:
    given: tuple[Given, ...]
    surnames: tuple[Surname, ...]
    patronymic_male: tuple[str, ...]
    patronymic_female: tuple[str, ...]
    streets: tuple[Street, ...]
    cities: tuple[str, ...]

    def given_by(self, gender: str, tier: str) -> tuple[Given, ...]:
        return tuple(g for g in self.given if g.gender == gender and g.tier == tier)

    def surnames_by(self, gender: str, tier: str) -> tuple[Surname, ...]:
        return tuple(s for s in self.surnames if s.tier == tier and s.gender in (gender, "u"))


def _read(name: str) -> dict[str, object]:
    return json.loads((POOLS_DIR / name).read_text(encoding="utf-8"))


def load_pools() -> Pools:
    nen = _read("nen_given_names.json")["items"]
    wd_given = _read("wikidata_given_names.json")["items"]
    wd_family = _read("wikidata_family_names.json")["items"]
    wd_streets = _read("wikidata_streets.json")["items"]
    wd_cities = _read("wikidata_cities.json")["items"]
    libs = _read("mimesis_faker.json")["items"]
    assert isinstance(nen, list) and isinstance(wd_given, list) and isinstance(wd_family, list)
    assert isinstance(wd_streets, list) and isinstance(wd_cities, list) and isinstance(libs, dict)

    given: dict[str, Given] = {}
    for row in nen:
        tier = _NEN_TIER[str(row["bucket"])]
        given[str(row["name"])] = Given(str(row["name"]), str(row["gender"]), tier)
        if str(row["bucket"]) in _DIMINUTIVE_BUCKETS:
            for short in row["short_forms"]:  # type: ignore[union-attr]
                # NEN lists affectionate forms too («Яшенька», «Раечуша»).
                # What a customer types into a chat is the short one — Саша,
                # Таня, Лёва — and five letters is where the two part.
                if 3 <= len(str(short)) <= 5:
                    given.setdefault(str(short), Given(str(short), str(row["gender"]), "diminutive"))
    for row in wd_given:
        name, gender = str(row["name"]), str(row["gender"])
        if name not in given and gender in ("m", "f"):
            given[name] = Given(name, gender, "tail")
    for name, gender in FOREIGN_GIVEN:
        given[name] = Given(name, gender, "foreign")

    surnames: dict[str, Surname] = {}
    faker = libs["faker"]
    mimesis = libs["mimesis"]
    assert isinstance(faker, dict) and isinstance(mimesis, dict)
    # Faker's Russian surnames are the frequency head (Смирнов, Иванов, …);
    # mimesis adds the next rank. Together they are what every gazetteer has.
    for gender, key in (("m", "surname_male"), ("f", "surname_female")):
        for name in list(faker[key]) + list(mimesis[key]):
            if str(name) not in _EXCLUDED_SURNAMES:
                surnames.setdefault(str(name), Surname(str(name), gender, "common"))
    for row in wd_family:
        name = str(row["name"])
        if name not in surnames and name not in _EXCLUDED_SURNAMES:
            surnames[name] = Surname(name, str(row["gender"]), "tail")
    for name in FOREIGN_SURNAMES:
        surnames[name] = Surname(name, "u", "foreign")

    streets = tuple(Street(str(r["name"]), str(r["type"])) for r in wd_streets)
    # Cities with a recorded population, largest first, so a draw prefers the
    # names a reader recognises; the long tail of small towns stays available.
    cities = tuple(str(r["name"]) for r in sorted(wd_cities, key=lambda r: -int(r["population"])) if int(r["population"]) > 0)  # type: ignore[call-overload]
    return Pools(
        given=tuple(given.values()),
        surnames=tuple(surnames.values()),
        patronymic_male=tuple(str(p) for p in mimesis["patronymic_male"]),
        patronymic_female=tuple(str(p) for p in mimesis["patronymic_female"]),
        streets=streets,
        cities=cities,
    )


@dataclass(frozen=True)
class Person:
    given: Given
    surname: Surname
    patronymic: str      # "" for a foreign person: no patronymic exists to write
    gender: str

    @property
    def tier(self) -> str:
        """The rarer of the two parts decides: a common given name with a
        Wikidata-only surname is a tail person for a gazetteer."""
        order = {"common": 0, "diminutive": 1, "tail": 2, "foreign": 3}
        return max((self.given.tier, self.surname.tier), key=lambda t: order[t])


def draw_person(pools: Pools, rng: random.Random, tier: str) -> Person:
    """A person whose NAME tier is `tier`. For «foreign» both parts are
    foreign; for «diminutive» the given name is a short form and the surname
    common; for «tail» at least one part is tail and the other common."""
    gender = rng.choice(("m", "f"))
    if tier == "foreign":
        given = rng.choice(pools.given_by(gender, "foreign"))
        surname = rng.choice(pools.surnames_by(gender, "foreign"))
    elif tier == "diminutive":
        given = rng.choice(pools.given_by(gender, "diminutive"))
        surname = rng.choice(pools.surnames_by(gender, "common"))
    elif tier == "tail":
        if rng.random() < 0.5:
            given = rng.choice(pools.given_by(gender, "tail"))
            surname = rng.choice(pools.surnames_by(gender, "common"))
        else:
            given = rng.choice(pools.given_by(gender, "common"))
            surname = rng.choice(pools.surnames_by(gender, "tail"))
    else:
        given = rng.choice(pools.given_by(gender, "common"))
        surname = rng.choice(pools.surnames_by(gender, "common"))
    if tier == "foreign":
        patronymic = ""
    else:
        patronymic = rng.choice(pools.patronymic_male if gender == "m" else pools.patronymic_female)
    return Person(given=given, surname=surname, patronymic=patronymic, gender=gender)
