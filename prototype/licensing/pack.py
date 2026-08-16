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

_DATA = Path(__file__).resolve().parent / "data"


def _load_dictionary(filename: str) -> list[str]:
    path = _DATA / filename
    if not path.exists():
        raise FileNotFoundError(
            f"name dictionary missing: {path}. Regenerate with "
            f"bench/build_name_dicts.py — the bundle cannot be built without it."
        )
    return sorted(set(path.read_text(encoding="utf-8").split()))


def build_payload() -> dict[str, object]:
    """The bundle contents, before compression. Deterministic: same sources in,
    byte-identical payload out (every collection is sorted or explicitly
    ordered), so the content hash is a stable identity."""
    payload: dict[str, object] = {
        "names": {
            "dict_first": _load_dictionary("first_names.txt"),
            "dict_surnames": _load_dictionary("surnames.txt"),
            "seed_first_names": list(assets_source.SEED_FIRST_NAMES),
            "diminutives": list(assets_source.DIMINUTIVES),
            "surname_suffixes": list(assets_source.SURNAME_SUFFIXES),
            "patronymic_suffixes": list(assets_source.PATRONYMIC_SUFFIXES),
            "translit": assets_source.TRANSLIT,
            "cues": list(assets_source.NAME_CUES),
            "stopwords": list(assets_source.STOPWORDS),
        },
        "address": {
            "street_gaz": list(assets_source.STREET_GAZ),
            "core_part": list(assets_source.CORE_PART),
            "patterns": assets_source.ADDRESS_PATTERNS,
        },
        "quasi": {
            "birth_ctx": list(assets_source.BIRTH_CTX),
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
        },
        # A LIST of pairs, not a dict. `_key_type` falls back to matching the
        # normalized key against each stem in turn, so the ORDER decides which
        # type wins when several stems are prefixes of the same key. Shipping a
        # dict would hand that order to `json.dumps(sort_keys=True)`, i.e. to the
        # alphabet — a silent semantic change with no test that would notice.
        # JSON arrays preserve order; sort_keys does not touch their contents.
        "structured": {"key_type": [[key, value] for key, value in assets_source.KEY_TYPE.items()]},
        "ru_pii": {
            "ctx_types": [list(entry) for entry in assets_source.CTX_TYPES],
            "inn_context": list(assets_source.INN_CONTEXT),
        },
        "priority": assets_source.PRIORITY,
        "lookalike": assets_source.LOOKALIKE,
    }
    _check_lookalike_table()
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    payload["version"] = hashlib.sha256(canonical).hexdigest()[:16]
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


def build_plaintext() -> bytes:
    """The decrypted bundle exactly as the engine's `Assets.load` expects it."""
    payload = build_payload()
    return zlib.compress(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"), 6
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plaintext = build_plaintext()
    version = build_payload()["version"]
    if args.out is None:
        sys.stdout.buffer.write(plaintext)
    else:
        args.out.write_bytes(plaintext)
    print(f"bundle {version}  {len(plaintext) / 1024:.0f} KB compressed", file=sys.stderr)


if __name__ == "__main__":
    main()
