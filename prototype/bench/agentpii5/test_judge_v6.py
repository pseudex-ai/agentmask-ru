"""`judge.py` v6 pinned: the pre-gate hunts new types from the registry, and the
rubric/prompt stay byte-stable.

    cd prototype && source .venv/bin/activate
    && python3 -m bench.agentpii5.test_judge_v6

Offline: no model, no key, no money. Three claims, two from §9.2:
  * R6-15 — an ALPHANUMERIC substitute (a VIN) rewritten with homoglyphs in the
    restored answer is caught by the pre-gate, where F3 recorded «MISSED»;
  * R6-16 — the hunt on the OLD v5 surfaces is identical to today's: a NAME, a
    PHONE, a CARD, a PLATE are hunted under exactly the pre-v6 types;
  * the rubric and headings are byte-stable, so `prompt_sha256` did not move.
"""
import sys
from collections.abc import Callable

from bench.agentpii4.parts import parts_of
from bench.agentpii5 import contracts, judge

# The pre-v6 `hunted_types` — restated in the test as the R6-16 oracle, exactly
# as §9.2 describes today's hunt (NAME/LOC/EMAIL/PHONE/DOB always, PLATE by
# shape).
_OLD_NEEDLE_TYPES: tuple[str, ...] = ("NAME", "LOC", "EMAIL", "PHONE", "DOB")

# The VIN sample and its homoglyph rewrite: the first three Latin letters of the
# VIN alphabet are written as their Cyrillic twins, which is exactly the rewrite
# F3 recorded as a miss.
_VIN: str = "XTAGFK330LY123456"
_VIN_HOMOGLYPH: str = "ХТАGFK330LY123456"


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_pregate_catches_rewrites() -> list[str]:
    """R6-15. A VIN substitute left in the answer, written with homoglyphs, is a
    residual the pre-gate refuses — the P3 «MISSED» row becomes «обязан поймать»."""
    problems: list[str] = []
    if "VIN" not in judge.hunted_types(_VIN):
        problems.append("the VIN surface was not hunted under its own type")
    verdict = judge.residual_pregate_of(f"Проверил: {_VIN_HOMOGLYPH}.", (_VIN,), ())
    if verdict is None or verdict.judged_by != "residual_gate":
        problems.append(f"a homoglyph VIN rewrite passed the pre-gate: {verdict}")
    # The NEGATIVE: the same answer without the substitute is not refused, so the
    # row above fires on the REWRITE and not on a gate that refuses everything.
    if judge.residual_pregate_of("Проверил: всё в порядке.", (_VIN,), ()) is not None:
        problems.append("an answer with no substitute was refused")
    return problems


def test_old_hunt_identity() -> list[str]:
    """R6-16. The hunt on old surfaces is byte-identical to today's: no v6 type
    joins for a NAME, PHONE, CARD, SNILS, INN, PASSPORT, DOB or LOC surface, and
    a PLATE still adds exactly PLATE."""
    problems: list[str] = []
    surfaces = {
        "NAME": "Пахомова Ольга",
        "PHONE": "+7 943 239-11-74",
        "CARD": "4276 3800 1234 5678",
        "SNILS": "681-644-063 10",
        "INN": "7736050003",
        "PASSPORT": "4509 123456",
        "DOB": "14.03.1987",
        "LOC": "орёл проспект рябиновый 100 кв 102",
        "EMAIL": "olga.pahomova@mail.ru",
    }
    for label, surface in surfaces.items():
        got = judge.hunted_types(surface)
        want = (*_OLD_NEEDLE_TYPES, "PLATE") if parts_of("PLATE", surface) else _OLD_NEEDLE_TYPES
        if got != want:
            problems.append(f"{label}: hunted as {got}, the pre-v6 hunt is {want}")
    plate = judge.hunted_types("а123вс777")
    if plate != (*_OLD_NEEDLE_TYPES, "PLATE"):
        problems.append(f"a plate is hunted as {plate}, not the pre-v6 list + PLATE")
    return problems


def test_prompt_sha256_unchanged() -> list[str]:
    """The rubric and headings did not move, so the calibration hash that pins a
    judge to a prompt is byte-stable (§9.1, R6-16)."""
    problems: list[str] = []
    expected = "d39ef7aa94bd7544709d1ba44339f2d5310a95c7304e953cbe585d8761f4139a"
    if judge.prompt_sha256() != expected:
        problems.append(f"prompt_sha256 moved: {judge.prompt_sha256()}")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("pregate_catches_rewrites", test_pregate_catches_rewrites),
        ("old_hunt_identity", test_old_hunt_identity),
        ("prompt_sha256_unchanged", test_prompt_sha256_unchanged),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("judge_v6: PASS" if not failures else "judge_v6: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
