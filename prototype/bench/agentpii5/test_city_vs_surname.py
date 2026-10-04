"""C1 city-vs-surname — a surname-colliding settlement reads as ONE LOC, not NAME.

    cd prototype && source .venv/bin/activate && \
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_city_vs_surname

The long_order-* divergence. «Одоев» is a real settlement (Tula oblast) whose
name pymorphy3 reads ONLY as a surname (`Surn`, no `Geox`), so in an address the
leading settlement was minted as a PERSON while the street beside it was minted
as a LOC: the model re-cased the fake surname and production parted from the
scorer, which (correctly) treats «одоев улица солнечная 104» as one composite
LOC with the settlement kept real.

The fix keys the lowercase variant on a SETTLEMENT DICTIONARY, not morphology
(detect-change: a lowercase form needs a dictionary, and morphology here only
says "surname"). The settlement is kept real by `vault._settlement_of`; the
street, house and flat are faked. The surname reading survives: «фамилия одоев»
is a person, exactly as before.

No model, no network. Detection is checked directly, and the vault leg through
the production path `envelope.mask_messages`.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from testkit import load_dev_bundle  # noqa: E402
from pseudex import morph_places  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.envelope import MaskContext, mask_messages  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402

RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


ADDRESS: str = "везите на одоев улица солнечная 104"


def _detect(text: str) -> list[tuple[str, str]]:
    d = Detector()
    return [(s.entity_type, text[s.start:s.end]) for s in d.detect(text)]


def _check_detect_one_loc() -> None:
    """The settlement + street is ONE LOC span, never NAME + LOC."""
    spans = _detect(ADDRESS)
    locs = [value for kind, value in spans if kind == "LOC"]
    names = [value for kind, value in spans if kind == "NAME"]
    check(len(locs) == 1 and "одоев" in locs[0] and "улица солнечная 104" in locs[0],
          "the settlement + street detect as ONE LOC span",
          f"spans={spans!r}")
    check(not names,
          "the settlement is not minted as a NAME beside the LOC",
          f"spans={spans!r}")


def _check_surname_stays_name() -> None:
    """«фамилия одоев» remains a person; the dictionary does not leak into prose."""
    spans = _detect("фамилия одоев")
    names = [value for kind, value in spans if kind == "NAME"]
    check(names == ["одоев"],
          "the surname reading survives (фамилия одоев -> NAME)",
          f"spans={spans!r}")
    check(all(kind != "LOC" for kind, _ in spans),
          "the surname context is not re-read as an address",
          f"spans={spans!r}")


def _check_settlement_stays_real() -> None:
    """Through the vault: the settlement is real, the street+house are faked."""
    detector = Detector()
    view = Vault(":memory:", "city-surname").for_conversation("c1")
    context = MaskContext(
        detector=detector, vault=view, audit=AuditLog(":memory:"),
        cache=MaskCache(1024), org_id="city-surname", agent_id="bench",
        conversation_id="c1")
    masked = mask_messages([{"role": "user", "content": ADDRESS}], context, False)[0]["content"]
    assert isinstance(masked, str)
    # ONE composite LOC, not a town and a street minted separately (the split the
    # live run diverged on).
    forms = [(shown, original) for shown, original, kind in view.shown_forms()
             if kind == "LOC" and shown != original]
    check(len(forms) == 1, "the composite address minted exactly one LOC substitute",
          f"forms={forms!r}")
    if forms:
        shown, _ = forms[0]
        roles = morph_places.split_roles(shown)
        check(roles.get("city", "").casefold() == "одоев",
              "the settlement stays real inside the masked address",
              f"shown={shown!r} roles={roles!r}")
    check("солнечная" not in masked.casefold(),
          "the real street name never reaches the model",
          f"masked={masked!r}")


def main() -> int:
    load_dev_bundle()
    _check_detect_one_loc()
    _check_surname_stays_name()
    _check_settlement_stays_real()
    failures = [name for ok, name, _ in RESULTS if not ok]
    print()
    print("=" * 72)
    print(f"{len(RESULTS) - len(failures)}/{len(RESULTS)} passed")
    if failures:
        print("city-vs-surname NOT in place:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("city-vs-surname: settlement + street = one LOC, surname reading survives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
