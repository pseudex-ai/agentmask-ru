"""Fetch the open name/street/city pools this benchmark is generated from.

WHY THE POOLS ARE SNAPSHOTS AND NOT LIVE QUERIES. `build.py --seed N` must
regenerate the corpus byte for byte (gate G9), and a live SPARQL endpoint
changes daily. The snapshot files under `pools/` are committed together with
the query that produced them and the date it ran, so anyone can re-run this
script, diff the result against the snapshot, and see exactly what moved.

WHY THESE SOURCES AND NOT OTHERS. The benchmark's author also sells a masker
whose gazetteers come from the `russiannames` package and the ГАР street
register. A corpus drawn from the same lists could not fail against that
masker — every value would be in its dictionary by construction. Wikidata
(CC0), NEN (CC BY 4.0), mimesis and Faker (MIT, used at build time) are
independent of both, and the corpus additionally records for every name which
TIER it came from (common / tail / diminutive / foreign) so a reader can see
the score on names a big gazetteer is unlikely to hold.

    python3 pools/build_pools.py --out pools/

Network access: Wikidata Query Service and huggingface.co only.
"""

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "agentmask-ru-build/0.1 (benchmark pools; github.com/pseudex/agentmask-ru)"
WIKIDATA = "https://query.wikidata.org/sparql"
NEN_JSON = "https://huggingface.co/datasets/MentalTech/russian-given-names-nen/resolve/main/data/names.json"

# One capitalised Cyrillic word, optionally hyphenated. Labels that carry
# Latin letters, digits or spaces are transcription artefacts or multi-word
# entries and are dropped rather than repaired — a repaired label is a value
# nobody wrote.
_CLEAN = re.compile(r"^[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?$")

QUERIES: dict[str, str] = {
    "given_names": """
SELECT DISTINCT ?item ?label ?gender WHERE {
  VALUES (?cls ?gender) { (wd:Q12308941 "m") (wd:Q11879590 "f") (wd:Q202444 "u") }
  ?item wdt:P31 ?cls ; wdt:P282 wd:Q8209 ; rdfs:label ?label .
  FILTER(LANG(?label) = "ru")
}""",
    "family_names": """
SELECT DISTINCT ?item ?label WHERE {
  ?item wdt:P31 wd:Q101352 ; wdt:P282 wd:Q8209 ; rdfs:label ?label .
  FILTER(LANG(?label) = "ru")
}""",
    "streets": """
SELECT DISTINCT ?item ?label ?cityLabel WHERE {
  ?item wdt:P31 wd:Q79007 ; wdt:P17 wd:Q159 ; rdfs:label ?label .
  OPTIONAL { ?item wdt:P131 ?city . ?city rdfs:label ?cityLabel . FILTER(LANG(?cityLabel) = "ru") }
  FILTER(LANG(?label) = "ru")
}""",
    "cities": """
SELECT DISTINCT ?item ?label ?pop WHERE {
  ?item wdt:P31 wd:Q7930989 ; wdt:P17 wd:Q159 ; rdfs:label ?label .
  OPTIONAL { ?item wdt:P1082 ?pop }
  FILTER(LANG(?label) = "ru")
}""",
}

# Street labels on Wikidata carry the generic word inside the label
# («Большая Садовая улица»). The corpus needs the name and the type apart, so
# a register can write «ул. Большая Садовая» or «большая садовая». Anything
# whose type is not in this list is dropped, not guessed.
_STREET_TYPES: tuple[str, ...] = (
    "улица", "переулок", "проспект", "шоссе", "бульвар", "набережная",
    "площадь", "проезд", "аллея", "тупик",
)


def sparql_csv(query: str) -> list[dict[str, str]]:
    url = WIKIDATA + "?" + urllib.parse.urlencode({"query": query})
    request = urllib.request.Request(url, headers={"Accept": "text/csv", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        body = response.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(body)))


def surname_gender(name: str) -> str:
    """Gender by the Russian surname suffix; «u» when the suffix says nothing
    (Билык, Богдан), in which case the surname is used unchanged for either."""
    if name.endswith(("ова", "ева", "ёва", "ина", "ына", "ская", "цкая", "ая")):
        return "f"
    if name.endswith(("ов", "ев", "ёв", "ин", "ын", "ский", "цкий", "ой", "ый", "ий")):
        return "m"
    return "u"


def split_street(label: str) -> tuple[str, str] | None:
    words = label.split()
    for i, word in enumerate(words):
        if word.lower() in _STREET_TYPES:
            name = " ".join(words[:i] + words[i + 1:])
            # «1-й проезд» and «1 Мая» are real streets, but a name with no
            # letter at all is a bare number next to a type word, and that is
            # the shape the benchmark's NEGATIVES take («заказ 1»).
            if name and all(re.match(r"^[А-ЯЁа-яё0-9-]+$", w) for w in name.split()) and re.search(r"[А-ЯЁа-яё]", name):
                return name, word.lower()
    return None


def build_given(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for row in rows:
        label = row["label"]
        if not _CLEAN.match(label):
            continue
        # A name listed under both a gendered class and the generic class keeps
        # the gendered reading; two gendered readings keep the first seen.
        if label not in seen or seen[label] == "u":
            seen[label] = row["gender"]
    return [{"name": n, "gender": g} for n, g in sorted(seen.items())]


def build_family(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    names = sorted({row["label"] for row in rows if _CLEAN.match(row["label"])})
    return [{"name": n, "gender": surname_gender(n)} for n in names]


def build_streets(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: dict[tuple[str, str], str] = {}
    for row in rows:
        parts = split_street(row["label"])
        if parts is None:
            continue
        out.setdefault(parts, row.get("cityLabel", "") or "")
    return [{"name": n, "type": t, "city": c} for (n, t), c in sorted(out.items())]


def build_cities(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    out: dict[str, int] = {}
    for row in rows:
        label = row["label"]
        if not all(re.match(r"^[А-ЯЁ][а-яё-]+$", w) for w in label.split()):
            continue
        pop = row.get("pop", "")
        population = int(float(pop)) if pop else 0
        out[label] = max(out.get(label, 0), population)
    return [{"name": n, "population": p} for n, p in sorted(out.items())]


def fetch_nen() -> list[dict[str, object]]:
    request = urllib.request.Request(NEN_JSON, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        rows = json.loads(response.read().decode("utf-8"))
    return [
        {
            "name": r["name"],
            "gender": r["gender"],
            "bucket": r["popularity_bucket"],
            "short_forms": [s for s in r.get("short_forms", []) if _CLEAN.match(s)],
        }
        for r in rows
        if _CLEAN.match(r["name"])
    ]


def snapshot_libraries() -> tuple[dict[str, object], dict[str, object]]:
    """The mimesis and Faker Russian lists, copied out of the installed
    packages so the corpus does not move when a library release edits a
    list. Both are MIT; the versions are recorded in the snapshot."""
    import importlib.resources as resources

    import faker
    import mimesis
    from faker.providers.person.ru_RU import Provider as FakerPerson

    person = json.loads((resources.files("mimesis") / "datasets" / "ru" / "person.json").read_text(encoding="utf-8"))
    address = json.loads((resources.files("mimesis") / "datasets" / "ru" / "address.json").read_text(encoding="utf-8"))
    meta = {
        "source": "mimesis (datasets/ru/person.json, address.json) and Faker (providers/person/ru_RU)",
        "license": "MIT",
        "mimesis_version": mimesis.__version__,
        "faker_version": faker.VERSION,
        "fetched": dt.date.today().isoformat(),
    }
    items = {
        "mimesis": {
            "given_male": person["names"]["male"],
            "given_female": person["names"]["female"],
            "surname_male": person["surnames"]["male"],
            "surname_female": person["surnames"]["female"],
            "patronymic_male": person["patronymic"]["male"],
            "patronymic_female": person["patronymic"]["female"],
            "streets": address["street"]["name"],
            "cities": address["city"],
        },
        "faker": {
            "given_male": list(FakerPerson.first_names_male),
            "given_female": list(FakerPerson.first_names_female),
            "surname_male": list(FakerPerson.last_names_male),
            "surname_female": list(FakerPerson.last_names_female),
            "patronymic_male": list(FakerPerson.middle_names_male),
            "patronymic_female": list(FakerPerson.middle_names_female),
        },
    }
    return meta, items


def write(path: Path, meta: dict[str, object], items: list[dict[str, object]]) -> None:
    payload = {"meta": meta, "count": len(items), "items": items}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, help="directory for the snapshot files")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    wikidata_meta = {
        "source": "Wikidata Query Service",
        "license": "CC0-1.0",
        "license_url": "https://www.wikidata.org/wiki/Wikidata:Licensing",
        "fetched": today,
    }
    builders = {
        "given_names": build_given,
        "family_names": build_family,
        "streets": build_streets,
        "cities": build_cities,
    }
    for key, builder in builders.items():
        rows = sparql_csv(QUERIES[key])
        items = builder(rows)
        meta = dict(wikidata_meta)
        meta["query"] = QUERIES[key].strip()
        meta["rows_fetched"] = len(rows)
        write(out / f"wikidata_{key}.json", meta, items)
        print(f"wikidata_{key}: {len(rows)} rows -> {len(items)} items", file=sys.stderr)
    nen = fetch_nen()
    write(
        out / "nen_given_names.json",
        {
            "source": "MentalTech/russian-given-names-nen (Hugging Face)",
            "source_url": "https://huggingface.co/datasets/MentalTech/russian-given-names-nen",
            "author": "NEN («Нет, это нормально»), n-e-n.ru",
            "license": "CC-BY-4.0",
            "fetched": today,
        },
        nen,
    )
    print(f"nen_given_names: {len(nen)} items", file=sys.stderr)
    lib_meta, lib_items = snapshot_libraries()
    (out / "mimesis_faker.json").write_text(
        json.dumps({"meta": lib_meta, "items": lib_items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("mimesis_faker: snapshot written", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
