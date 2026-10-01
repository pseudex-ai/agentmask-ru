# test_gen_v6.py — pins the generator home of the v6 checksum arithmetic (L2)
# and the scrub-gate denylist (R6-26/R6-27, TZ §3.3).
#
#     cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_gen_v6
#
# No pytest, as everywhere in `prototype/`: `main()` prints PASS/FAIL and
# returns the exit code. This test MAY import `checksum_v6` (R6-10) — the two
# homes agreeing on the corpus is the proof they did not share one bug — but the
# generator itself may not (R6-07, pinned in `test_two_homes_by_design` in a
# fresh process).

from __future__ import annotations

import json
import pathlib
import string
import subprocess
import sys

import bench.agentpii5.checksum_v6 as checksum_v6
import bench.agentpii5.gen_v6 as gen_v6
import bench.agentpii5.pii_types as pii_types

_PROTOTYPE = str(pathlib.Path(__file__).resolve().parent.parent.parent)
_DENYLIST = pathlib.Path(__file__).resolve().parent / "v6" / "denylist.json"


def _v6_types() -> tuple[pii_types.TypeSpec, ...]:
    return tuple(t for t in pii_types.TYPE_REGISTRY if t.origin == pii_types.ORIGIN_V6)


# --- R6-10: every checksum-carrying v6 type mints a value the validator accepts
# Except the VIN Russian-WMI half (OD-62, position 9 «as manufacturer», wrong by
# construction) and the 20-digit ICCID (which the generator never mints — C-02,
# OD-16). BANK_ACCOUNT is a (account, BIK) pair check, so it goes through
# `validate_account(value, gen_v6.BANK_ACCOUNT_BIK)`, never through `validate`.

def test_values_validate() -> list[str]:
    problems: list[str] = []
    for t in _v6_types():
        if not t.generated_checksum:
            continue
        value, _canonical = gen_v6.generate(t.id, 0)
        if t.id == "VIN":
            # OD-62: the Russian-WMI half deliberately does NOT carry an ISO 3779
            # check at position 9 — it is the one documented exception.
            if gen_v6.vin_is_russian_wmi(value):
                continue
            if not checksum_v6.validate("VIN", value):
                problems.append(f"VIN {value!r} not ISO-3779 valid")
        elif t.id == "BANK_ACCOUNT":
            if not checksum_v6.validate_account(value, gen_v6.BANK_ACCOUNT_BIK):
                problems.append(f"BANK_ACCOUNT {value!r} not ЦБ-515 valid for {gen_v6.BANK_ACCOUNT_BIK}")
        else:
            # ICCID is always 19 digits here; the 20-digit legacy form is never
            # generated (its Luhn claim is unconfirmed), so no special case.
            if not checksum_v6.validate(t.id, value):
                problems.append(f"{t.id} {value!r} not {t.generated_checksum} valid")
    return problems


# --- R6-07: importing the generator home loads neither the validator home nor
# pseudex / licensing. Checked in a FRESH process so an import left behind by
# this runner cannot both load the module and pass the check (the same trick as
# `test_checksum_v6.test_two_homes_by_design`, mirrored here for the other home).

def test_two_homes_by_design() -> list[str]:
    code = (
        "import sys; import bench.agentpii5.gen_v6; "
        "bad = sorted({m for m in sys.modules "
        "if m.split('.')[0] in ('pseudex', 'checksum_v6', 'licensing') "
        "or m == 'bench.agentpii5.checksum_v6'}); "
        "print(','.join(bad))"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=_PROTOTYPE)
    if proc.returncode != 0:
        return [f"fresh process failed: {proc.stderr.strip()}"]
    leaked = proc.stdout.strip()
    if leaked:
        return [f"gen_v6 loads a forbidden module: {leaked}"]
    return []


# --- determinism: the same (type_id, seed) yields the same (value, canonical)
# across calls (a LOCAL Random(seed) is constructed on every call — no state).

def test_deterministic() -> list[str]:
    problems: list[str] = []
    for t in _v6_types():
        for seed in (0, 1, 12345):
            a = gen_v6.generate(t.id, seed)
            b = gen_v6.generate(t.id, seed)
            if a != b:
                problems.append(f"{t.id} seed {seed} not deterministic: {a!r} vs {b!r}")
    return problems


# --- R6-35: the generated value's span is the identifier chars + internal
# separators, and the grammar never emits a cue word or an «от <дата>» tail.

_SPAN_CHARS = set(
    string.ascii_letters + string.digits
    + "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдежзийклмнопрстуфхцчшщъыьэюя"
    + " -/:№._"
)


def test_span_rule() -> list[str]:
    problems: list[str] = []
    for t in _v6_types():
        value, _canonical = gen_v6.generate(t.id, 0)
        low = value.lower()
        # 1. the value never carries a cue word of its own type.
        for cue in t.cues:
            if cue.lower() in low:
                problems.append(f"{t.id} value emits cue word {cue!r}: {value!r}")
        # 2. the value never carries the «от <дата>» tail: no standalone «от».
        if " от " in f" {low} ":
            problems.append(f"{t.id} value emits an «от» tail: {value!r}")
        # 3. the span is identifier chars + internal separators only — no leading
        #    cue text, no trailing prose, no out-of-span character.
        for ch in value:
            if ch not in _SPAN_CHARS:
                problems.append(f"{t.id} value has out-of-span char {ch!r}: {value!r}")
    return problems


# --- R6-26: the denylist is non-empty and carries the required literal examples
# (IMEI / GS1 / IBAN / the three ЦБ 515 accounts / the two ICAO MRZ bodies).

def test_denylist() -> list[str]:
    problems: list[str] = []
    if not _DENYLIST.exists():
        return [f"denylist missing: {_DENYLIST}"]
    try:
        data = json.loads(_DENYLIST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"denylist unreadable: {exc}"]
    values = data.get("values")
    if not isinstance(values, list) or not values:
        return ["denylist 'values' is empty or not a list"]
    present = set(values)
    required = (
        "260531793113837",                # IMEI (registry C-01:933)
        "37610425002123456",              # GS1 body (registry C-22:1319)
        "RU0304452522540817810538091310419",  # IBAN (registry A-08:214)
        "40602810700000000025",           # ЦБ 515 (registry A-07:162)
        "40102810100000010001",           # ЦБ 515 РКЦ (registry §1.8:1603)
        "30101810800000000746",           # ЦБ 515 corr (registry A-07:163)
        "520727",                         # ICAO MRZ body (registry A-01:37)
        "AB2134<<<",                      # ICAO MRZ body (registry A-01:37)
    )
    for value in required:
        if value not in present:
            problems.append(f"denylist missing required literal example {value!r}")
    return problems


CHECKS = (test_values_validate, test_two_homes_by_design, test_deterministic,
          test_span_rule, test_denylist)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_gen_v6: PASS" if not failures else f"test_gen_v6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
