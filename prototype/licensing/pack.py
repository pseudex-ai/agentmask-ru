"""Build the detection bundle from the authored assets.

One source of truth: the values live in `assets_source.py` and the dictionaries
in `licensing/data/`, and this module is the only thing that turns them into the
wire format the engine consumes. The engine can therefore never drift from the
bundle — it has no copy to drift from.

Format: zlib(JSON). Not msgpack — JSON is stdlib, and the cost that matters is
paid once per lease, not per request (measured: ~0.4 s to parse and compile the
whole 225k-entry payload, against a 24 h lease).

The version is the content hash. A bundle rebuilt from unchanged sources gets the
same version, which is what makes gate L6 meaningful: the token for a given input
may only change if the ASSETS changed, so a version that moves across a renewal
is a real signal, not build noise.

usage: python3 -m licensing.pack [--out bundle.bin]
"""

import argparse
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path

from licensing import assets_source
from licensing import canary
from licensing import fingerprint
# Allowed direction: shared crypto lives in pseudex.bundle and is imported BY the
# licensing side, never the other way (CLAUDE.md). The server already imports it.
from pseudex.bundle import merge_payload, frame_payload

_DATA = Path(__file__).resolve().parent / "data"


def _load_dictionary(filename: str) -> list[str]:
    path = _DATA / filename
    if not path.exists():
        raise FileNotFoundError(
            f"name dictionary missing: {path}. Regenerate with "
            f"bench/build_name_dicts.py — the bundle cannot be built without it."
        )
    return sorted(set(path.read_text(encoding="utf-8").split()))


def street_attribution() -> str:
    """The source line ФНС's open licence obliges us to carry.

    «указывать ссылку на источник открытых данных» is the one condition the
    ОТКРЫТАЯ ЛИЦЕНЗИЯ attaches to extraction and commercial reuse, and it is
    cheap to satisfy and expensive to forget. It rides IN THE BUNDLE rather than
    only in `docs/`: the bundle is what a customer's process actually loads, and
    an attribution that lives only in a repository the customer never sees is
    not an attribution.

    The DATE is part of it — «не искажать… время последнего обновления» — and it
    is read from the file the fetcher wrote rather than restated here, so a
    stale bundle cannot claim a fresh dump."""
    path = _DATA / "gar_streets.tsv"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# Государственный адресный реестр"):
            return line.lstrip("# ").strip()
    raise ValueError(f"{path} has no attribution header — it was not written by "
                     f"licensing/fetch_gar.py, and its provenance is unknown")


def load_street_vocabulary() -> list[str]:
    """The ГАР street names that earn their place in the bundle.

    A FREQUENCY CUT, NOT THE WHOLE REGISTER, and the reason is precision rather
    than size — all 165 600 names gzip to well under a megabyte, so size was
    never the constraint. The constraint is that this vocabulary is a GATE: an
    entry says "a word spelled like this can name a street", and the tail of the
    register is full of names that are ordinary Russian words naming one street
    each in one village. `assets_source.STREET_MIN_OBJECTS` records what the
    measured trade was.

    Names of one WORD only. A multi-word ГАР name («Карла Маркса», «8 Марта»)
    is looked up here token by token, so storing the phrase would never match
    and storing its parts would put «карла» and «маркса» in as separate claims.
    The multi-word case belongs to the patterns, which can see the whole phrase.
    """
    path = _DATA / "gar_streets.tsv"
    if not path.exists():
        raise FileNotFoundError(
            f"street vocabulary missing: {path}. Regenerate with "
            f"`python3 -m licensing.fetch_gar` — the bundle cannot be built "
            f"without it, and a bundle built from a stale copy would mask "
            f"streets that no longer exist while missing the ones that do."
        )
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        count, _, name = line.partition("\t")
        if int(count) < assets_source.STREET_MIN_OBJECTS:
            continue
        name = name.strip().lower()
        # Digits and abbreviations belong to `numbered_st` and to the type
        # markers; a bare «1-я» or «б-р» in this set would claim any token that
        # looked like one.
        if len(name) < 4 or " " in name or "-" in name or any(c.isdigit() for c in name):
            continue
        names.add(name)
    if len(names) < 1000:
        raise ValueError(
            f"street vocabulary has only {len(names)} usable entries — the "
            f"file is truncated or the cut is set impossibly high"
        )
    return sorted(names)


def load_frequent_streets() -> list[str]:
    """The one-word ГАР names that occur in a HUNDRED or more places.

    COUNTS ARE SUMMED ACROSS CASE. The register is case-split — «Садовая» 17 324
    and «садовая» 1 are two lines — and `load_street_vocabulary` lower-cases
    only after the cut, which is harmless while the cut is 1 and would silently
    judge a name on the smaller half if it were ever raised. Here the sum is the
    number, because the question is how many places bear the name, not how the
    register capitalised it.

    Read by `address.register_spelling` and by nothing else; the reasoning and
    the measured margins are in `assets_source.STREET_FREQUENT_MIN`.
    """
    path = _DATA / "gar_streets.tsv"
    if not path.exists():
        raise FileNotFoundError(f"street vocabulary missing: {path}")
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        count, _, name = line.partition("\t")
        name = name.strip().lower()
        if len(name) < 4 or " " in name or "-" in name or any(ch.isdigit() for ch in name):
            continue
        counts[name] = counts.get(name, 0) + int(count)
    names = sorted(name for name, total in counts.items()
                   if total >= assets_source.STREET_FREQUENT_MIN)
    if len(names) < 200:
        raise ValueError(
            f"only {len(names)} streets reach {assets_source.STREET_FREQUENT_MIN} "
            f"objects — the file is truncated or the threshold is impossibly high"
        )
    return names


def load_street_phrases() -> list[str]:
    """The MULTI-WORD ГАР names, stored and matched as whole phrases.

    Fifty-five per cent of the register is multi-word — 90 706 of 165 672 — and
    that half is not the tail: «Карла Маркса» names 1 512 streets, «Степана
    Разина» 498, «Максима Горького» 465, «8 Марта» 1 953. They were absent
    entirely, so a customer on any of them was unprotected the moment the type
    word carried a typo, because the fuzzy-type path is the one that demands the
    vocabulary.

    A SEPARATE SET, not extra entries in `street_names`, and the distinction is
    the whole point. `load_street_vocabulary` deliberately keeps single words
    because its lookup is token by token: putting «карла» and «маркса» in there
    would let either word claim on its own to name a street, and «карла» does not.
    A phrase entry can only ever match the whole phrase, so it adds the name
    without adding the claim.

    Digits stay, unlike in the single-word set. «8 марта» and «1 мая» are among
    the commonest street names in the country, and as a PHRASE the digit is part
    of the name rather than a house number — which is exactly why the single-word
    set had to exclude the bare month.
    """
    path = _DATA / "gar_streets.tsv"
    if not path.exists():
        raise FileNotFoundError(
            f"street vocabulary missing: {path}. Regenerate with "
            f"`python3 -m licensing.fetch_gar`."
        )
    phrases: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        count, _, name = line.partition("\t")
        if int(count) < assets_source.STREET_MIN_OBJECTS:
            continue
        name = " ".join(name.strip().lower().split())
        if " " not in name or len(name) < 6:
            continue
        # Three words or more is almost always an administrative full form
        # («имени 40 лет октября»); the two-word case is what people write.
        if len(name.split()) > 3:
            continue
        phrases.add(name)
    if len(phrases) < 1000:
        raise ValueError(
            f"street phrase set has only {len(phrases)} entries — the file is "
            f"truncated or the cut is impossibly high"
        )
    return sorted(phrases)


def _bulk_payload() -> dict[str, object]:
    """The semi-public BULK — this half reads the big dictionaries from disk.

    Names and ГАР streets are open data; leasing them protects little, and they
    are what rotates on the ГАР cadence, which the drift lever needs. This is all
    that stays in the lease. `attribution` rides here because it is read from the
    same ГАР dump."""
    return {
        "names": {
            "dict_first": _load_dictionary("first_names.txt"),
            "dict_surnames": _load_dictionary("surnames.txt"),
        },
        "address": {
            "street_names": load_street_vocabulary(),
            "street_frequent": load_frequent_streets(),
            "street_phrases": load_street_phrases(),
        },
        "attribution": [street_attribution()],
    }


def _tuning_payload() -> dict[str, object]:
    """The authored TUNING — NO file reads, so the engine build that compiles this
    into the binary needs only `assets_source`, never the bulk dictionaries.

    This is the product: the cue words «выстраданные на ложных срабатываниях», the
    address regex apparatus, the priority table, the look-alike folds, the
    key→type map. It TRAVELS IN THE LEASE (age-sealed to the process key,
    nonce-wrapped), never compiled into the binary — so a memory dump yields the
    current lease's tuning only, not a blob decryptable offline forever (A2,
    docs/tz-tuning-in-lease.md). Order and structure are exactly what `_build`
    expects for these keys."""
    _check_lookalike_table()
    return {
        "names": {
            "seed_first_names": list(assets_source.SEED_FIRST_NAMES),
            "diminutives": list(assets_source.DIMINUTIVES),
            "surname_suffixes": list(assets_source.SURNAME_SUFFIXES),
            "patronymic_suffixes": list(assets_source.PATRONYMIC_SUFFIXES),
            "patronymics_masc": list(assets_source.PATRONYMICS_MASC),
            "patronymics_femn": list(assets_source.PATRONYMICS_FEMN),
            "translit": assets_source.TRANSLIT,
            "cues": list(assets_source.NAME_CUES),
            "bio_cues": list(assets_source.BIO_CUES),
            "never_cues": list(assets_source.NAME_NEVER_CUES),
            "stopwords": list(assets_source.STOPWORDS),
            # ПРЕДЛОГИ-ЯКОРИ ЧЕЛОВЕКА. Настраиваемые, как всякий cue, и потому
            # едут в лизинг, а не в бинарник: «от аленчиев» — то же правило, что
            # «перезвоните морозову», и материал у него тот же.
            "anchor_preps": list(assets_source.NAME_ANCHOR_PREPS),
        },
        "address": {
            "street_gaz": list(assets_source.STREET_GAZ),
            "settlement_gaz": list(assets_source.SETTLEMENT_GAZ),
            "street_type_nohouse": list(assets_source.STREET_TYPE_NOHOUSE),
            "street_type_house": list(assets_source.STREET_TYPE_HOUSE),
            "core_part": list(assets_source.CORE_PART),
            "patterns": assets_source.ADDRESS_PATTERNS,
        },
        "spoken": {
            # Опечатки числительных, добытые из речевых корпусов. Данные, а не
            # алгоритм: разбор числительных опубликован и живёт в движке, а
            # то, КАК их коверкает расшифровщик, вынуто нами из чужих корпусов.
            "numeral_typos": assets_source.NUMERAL_TYPOS,
        },
        "quasi": {
            "birth_ctx": list(assets_source.BIRTH_CTX),
            "birth_ctx_words": list(assets_source.BIRTH_CTX_WORDS),
            "months": list(assets_source.MONTHS),
            "medical": assets_source.MEDICAL_PATTERN,
        },
        "context": {
            "deny": list(assets_source.DENY),
            "phone_trigger": list(assets_source.PHONE_TRIGGER),
            "passport_trigger": list(assets_source.PASSPORT_TRIGGER),
            "regions": list(assets_source.REGIONS),
            "addr_intent": list(assets_source.ADDR_INTENT),
            "place_ref": list(assets_source.PLACE_REF),
            "version_ctx": list(assets_source.VERSION_CTX),
            "org_cue": list(assets_source.ORG_CUE),
            "personnel_cue": list(assets_source.PERSONNEL_CUE),
        },
        # A LIST of pairs, not a dict. `_key_type` falls back to matching the
        # normalized key against each stem in turn, so the ORDER decides which
        # type wins when several stems are prefixes of the same key. Shipping a
        # dict would hand that order to `json.dumps(sort_keys=True)`, i.e. to the
        # alphabet — a silent semantic change with no test that would notice.
        # JSON arrays preserve order; sort_keys does not touch their contents.
        "structured": {"key_type": [[key, value] for key, value in assets_source.KEY_TYPE.items()],
                       # КАРТА «ТИП → РОЛИ» для композитных объектов. Арендуется
                       # целиком: это tuned-словарь частей документа (series /
                       # number / серия / номер), а не алгоритм, и в бинарник он
                       # не едет — ровно как `key_type`.
                       "composite_types": assets_source.COMPOSITE_TYPES},
        "ru_pii": {
            "ctx_types": [list(entry) for entry in assets_source.CTX_TYPES],
            "inn_context": list(assets_source.INN_CONTEXT),
        },
        # Transliteration machinery tables (align/render/fold). Value order inside
        # each UNITS entry, the ENDINGS order, the four-TABLES order and the FOLD
        # sequence are load-bearing — JSON arrays preserve them (sort_keys touches
        # only object KEYS, and no reader depends on UNITS/table key order).
        "translit_machine": {
            "units": {unit: list(opts) for unit, opts in assets_source.TRANSLIT_UNITS.items()},
            "endings": list(assets_source.TRANSLIT_ENDINGS),
            "tables": [assets_source.TRANSLIT_ICAO, assets_source.TRANSLIT_GOST_B,
                       assets_source.TRANSLIT_MVD_2010, assets_source.TRANSLIT_COMMON],
            "fold": [list(pair) for pair in assets_source.TRANSLIT_FOLD],
        },
        # Fake substitute pools (vault mint). Order is not load-bearing (drawn by
        # secrets.choice / filtered by round-trip), but the SETS are.
        "fakes": {
            "first": list(assets_source.FAKE_FIRST),
            "last": list(assets_source.FAKE_LAST),
            "last_invariant": list(assets_source.FAKE_LAST_INVARIANT),
            "cities": list(assets_source.FAKE_CITIES),
            "streets": list(assets_source.FAKE_STREETS),
            "house_max": assets_source.FAKE_HOUSE_MAX,
        },
        "priority": assets_source.PRIORITY,
        "lookalike": assets_source.LOOKALIKE,
    }


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")


def build_payload() -> dict[str, object]:
    """The full payload (bulk + tuning), for tests and evals. Deterministic: same
    sources in, byte-identical out, so the content hash is a stable identity."""
    payload = merge_payload(_bulk_payload(), _tuning_payload())
    payload["version"] = hashlib.sha256(_canonical(payload)).hexdigest()[:16]
    return payload


def _check_lookalike_table() -> None:
    """Fail the build if a look-alike glyph was entered twice.

    A dict literal silently keeps the last value for a repeated key, so the
    duplicate is invisible in the built bundle — it only shows as a MISSING
    character, which is exactly how Greek small omicron went absent while
    Cyrillic 'о' appeared twice. Counting the source lines is the only place the
    two can still be told apart."""
    source = (Path(__file__).resolve().parent / "assets_source.py").read_text(encoding="utf-8")
    block = source.split("LOOKALIKE: dict[str, str] = {", 1)[1].split("}", 1)[0]
    declared = re.findall(r'^\s*"(.)"\s*:', block, re.MULTILINE)
    duplicates = {char for char in declared if declared.count(char) > 1}
    if duplicates:
        raise ValueError(
            "LOOKALIKE declares the same glyph twice: "
            + ", ".join(f"{char!r} (U+{ord(char):04X})" for char in sorted(duplicates))
        )
    if len(declared) != len(assets_source.LOOKALIKE):
        raise ValueError(
            f"LOOKALIKE has {len(declared)} declared entries but "
            f"{len(assets_source.LOOKALIKE)} survive in the dict"
        )


def _compress(payload: dict[str, object]) -> bytes:
    return zlib.compress(_canonical(payload), 6)


def build_plaintext(watermark: str = "", org_id: str = "") -> bytes:
    """The LEASED bundle: the FULL payload — bulk AND authored tuning.

    The tuning used to be compiled into the engine (a static-key-sealed blob) and
    only the key rode here; that gave extract-once-run-forever (A2). It now rides
    here whole, inside the bundle the server age-seals to the ephemeral process
    key and nonce-wraps — so it never touches disk, a captured lease is useless on
    another machine, and there is no compiled blob to decrypt offline. `version`
    is the payload's identity (audit, gate L6). See docs/tz-tuning-in-lease.md.

    `watermark` (per-org, from `licensing.watermark`) is stamped into the payload
    so a tuning dump names WHOSE lease carried it — inert for detection, carried
    into the engine's assets. Empty → no mark (watermarking off)."""
    payload = build_payload()
    if org_id:
        # Per-org canaries woven into the gazetteers (licensing.canary): a clone
        # built from a dump of THIS lease masks names/streets that exist in no real
        # dictionary and in no other org's bundle, so a leak is attributable. Novel
        # by construction; inert for real PII (test_canary.py).
        surnames = canary.canary_surnames(org_id)
        if surnames:
            names = payload["names"]
            names["dict_surnames"] = sorted(set(names["dict_surnames"]) | set(surnames))
        streets = canary.canary_streets(org_id)
        if streets:
            address = payload["address"]
            address["street_names"] = sorted(set(address["street_names"]) | set(streets))
        # PLUS the collusion-resistant fingerprint (licensing.fingerprint): a Tardos
        # codeword over a SHARED universe, so a bundle fused from several orgs (union
        # OR intersection) still traces to a contributor — the intersection attack
        # that strips per-org-unique canaries. Same secret, same novelty guarantee.
        fp_surnames = fingerprint.fingerprint_entries(org_id, "surname")
        if fp_surnames:
            payload["names"]["dict_surnames"] = sorted(
                set(payload["names"]["dict_surnames"]) | set(fp_surnames))
        fp_streets = fingerprint.fingerprint_entries(org_id, "street")
        if fp_streets:
            payload["address"]["street_names"] = sorted(
                set(payload["address"]["street_names"]) | set(fp_streets))
    if watermark:
        payload["_wm"] = watermark
    if watermark or org_id:
        # Re-hash: the mark and the canaries are part of what the signature will
        # cover, so two orgs' bundles differ and neither can be swapped for the
        # other without breaking the signature.
        payload["version"] = hashlib.sha256(_canonical(payload)).hexdigest()[:16]
    # Framed (sectioned) rather than one zlib(JSON) blob: the engine parses and
    # zeroes each section in turn, so a RAM carve no longer recovers the whole moat
    # in one `json.loads`, and the authored tuning is split off from the semi-public
    # bulk gazetteers (pseudex.bundle.frame_payload — RAM-carve hardening, WS-7).
    return frame_payload(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None,
                        help="write the leased bundle here")
    args = parser.parse_args()

    plaintext = build_plaintext()
    version = build_payload()["version"]
    if args.out is None:
        sys.stdout.buffer.write(plaintext)
    else:
        args.out.write_bytes(plaintext)
    print(f"bundle {version}  {len(plaintext) / 1024:.0f} KB compressed (bulk + tuning)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
