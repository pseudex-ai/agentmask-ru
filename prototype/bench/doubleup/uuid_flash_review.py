"""Independent synthetic review of the UUID-fragment -> NAME-initial residual.

THE CLAIM UNDER REVIEW. A tool argument that is an opaque identifier — a
`thread_id` UUID, an order code, a path segment — is written by the model
unchanged, because it is not personal data and no recognizer masks it. On the
reporting leg the engine proposes fragments of it as candidates and asks the
vault whether they are pieces of a substitute it minted. On committed HEAD one
fragment answers YES: the CREDIT_SUBJECT_CODE shape in `ru_pii_v6` offers the
hyphen-delimited UUID segment `12a3` (4-15 alphanumerics with a digit AND a
letter), and `Vault.residual_of` looks a Latin word up FOLDED —
`translit.fold` drops every non-letter — so `12a3` folds to `a`, which is the
indexed key of a minted NAME's initial `А.`. The engine then answers 200 with
`residual_tokens: ["12a3"]`; the pilot adapter turns that into a refusal.

WHAT THIS SCRIPT PROVES, and what it deliberately does NOT do.

  * It reproduces the defect from source on ANY tree it is pointed at, in a
    child-clean process, with synthetic values only: `--engine <prototype dir>`.
    Two runs in two processes are how HEAD and the working tree are compared —
    never two module copies inside one process, which is how a shared
    `sys.modules` turns a core change into a false baseline.
  * `--characterize` inverts the verdict: it PASSES when the defect reproduces
    and FAILS when it does not, so a fixed engine cannot be scored green by a
    stale "it is broken" belief.
  * The positive groups are asserted in BOTH modes. A candidate-grammar change
    that silences an opaque identifier by also silencing a genuine leftover
    substitute would be worse than the defect, so the guards that must keep
    firing are pinned here: a rebuilt NAME that no longer resolves, a standing
    substitute, an ambiguous shown surface, a refused country sign, and an
    exactly typed alphanumeric record.

NO REAL DATA, NO SOCKETS, NO MODEL CALLS. The vault is `:memory:`; the only
"mint" that is not production code is the RANDOM DRAW of the fake (`_render_token`
is patched to a fixed synthetic name so the run is reproducible). Detection,
masking, indexing, conversation scope, argument restoration and residual
reporting are the engine's own.

    python3 bench/doubleup/uuid_flash_review.py --engine ../..        # contract
    python3 bench/doubleup/uuid_flash_review.py --engine <head tree> --characterize
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

# A bench run must not leave .pyc files in the tree it is inspecting.
sys.dont_write_bytecode = True

SYNTHETIC_UUID = "abcdefab-12a3-4def-abcd-abcdefabcdef"
SYNTHETIC_FRAGMENT = "12a3"
# Synthetic persons: one real, one fake. Neither is derived from any corpus.
SYNTHETIC_REAL = "Зорин В. Г."
SYNTHETIC_FAKE = "Тестов А. Б."
# The typed alphanumeric record and its own fake, for the exact-token guard.
SYNTHETIC_CODE_REAL = "98z7"
SYNTHETIC_CODE_FAKE = "12a3"
SYNTHETIC_PHONE_REAL = "+7 916 555-01-23"
SYNTHETIC_PHONE_FAKE = "+7 939 222-76-19"


def _engine(prototype_dir: Path):
    """Import the engine from `prototype_dir`, which must come first on the path."""
    sys.path.insert(0, str(prototype_dir))
    from testkit import load_dev_bundle  # noqa: PLC0415 — after the path is set
    load_dev_bundle()
    from pseudex import redact, ru_pii_v6, translit, vault as vault_module
    from pseudex.detect_all import Detector
    from pseudex.vault import Vault, token_re
    return {
        "redact": redact, "ru_pii_v6": ru_pii_v6, "translit": translit,
        "vault_module": vault_module, "Detector": Detector, "Vault": Vault,
        "token_re": token_re,
    }


def _seeded_vault(engine) -> object:
    """One conversation holding ONE minted name, drawn from a fixed fake."""
    vault = engine["Vault"](":memory:", "synthetic-uuid-flash-review")
    vault = vault.for_conversation("synthetic-thread")
    spans = engine["Detector"]().detect(SYNTHETIC_REAL)
    assert len(spans) == 1 and spans[0].entity_type == "NAME", (
        "fixture broken: the synthetic person is no longer one NAME span")
    with patch.object(engine["vault_module"], "_render_token",
                      return_value=SYNTHETIC_FAKE):
        shown = engine["redact"].mask_text(SYNTHETIC_REAL, vault, spans)
    assert shown == SYNTHETIC_FAKE, "fixture broken: the fake was not minted"
    return vault


def _parts(vault) -> list[tuple[str, str]]:
    return [tuple(row) for row in vault._conn.execute(
        "SELECT part, token FROM token_parts ORDER BY part")]


def _residual(engine, vault, arguments: dict, *, restored: bool = True) -> list[str]:
    """The reporting leg exactly as `/unmask_arguments` calls it."""
    raw = json.dumps(arguments, ensure_ascii=False)
    out = engine["redact"].unmask_arguments(raw, vault) if restored else raw
    return engine["redact"].surviving_substitutes(raw, out, vault, True)


def _fragment_candidates(engine, text: str) -> tuple[list[str], list[str], list[str]]:
    """Which scanner OFFERS the fragment: the token scan, or the finance family.

    `_written_candidates` unions both, and the distinction is the diagnosis: the
    vault's own token shape does not claim a UUID segment, so the candidate that
    answers YES is born in `ru_pii_v6.FINANCE_TOKEN_RE`.
    """
    tokens = [m.group() for m in engine["token_re"]().finditer(text)]
    finance = [m.group() for m in engine["ru_pii_v6"].FINANCE_TOKEN_RE.finditer(text)]
    named = sorted(engine["redact"]._written_candidates(text, True).named)
    return tokens, finance, named


def _negatives(engine, vault) -> dict[str, list[str]]:
    """Opaque values that MUST report no residual. Each is a different grammar."""
    return {
        "uuid": _residual(engine, vault, {"thread_id": SYNTHETIC_UUID}),
        "fragment": _residual(engine, vault, {"label": SYNTHETIC_FRAGMENT}),
        "path": _residual(engine, vault, {"path": "/synthetic/12a3/report.csv"}),
        "code_literal": _residual(engine, vault, {"code": 'value = "12a3"'}),
        "nested": _residual(engine, vault, {"items": [{"thread_id": SYNTHETIC_UUID}]}),
        "two_words": _residual(engine, vault, {"label": "12a3 abcd"}),
    }


def _positives(engine, vault) -> dict[str, bool]:
    """The guards that must keep firing. A false-positive fix may not buy silence."""
    redact = engine["redact"]
    checks: dict[str, bool] = {}

    # 1. A rebuilt NAME still restores to the real person, and reports nothing.
    raw = json.dumps({"name": SYNTHETIC_FAKE}, ensure_ascii=False)
    out = redact.unmask_arguments(raw, vault)
    checks["genuine NAME restores"] = (
        json.loads(out)["name"] == SYNTHETIC_REAL
        and not redact.surviving_substitutes(raw, out, vault, True))

    # 2. The same substitute LEFT STANDING is still reported.
    checks["standing NAME still alarms"] = bool(
        redact.surviving_substitutes(raw, raw, vault, True))

    # 3. An ambiguous shown surface is refused and stays visible. Two owners for
    #    one surface is the engine's own refusal, not a test stub.
    vault.remember_shown("Антон", "Виктор", "NAME")
    vault.remember_shown("Антон", "Павел", "NAME")
    raw = json.dumps({"name": "Антон"}, ensure_ascii=False)
    out = redact.unmask_arguments(raw, vault)
    checks["ambiguous surface refused"] = (
        json.loads(out)["name"] == "Антон"
        and "Антон" in redact.surviving_substitutes(raw, out, vault, True))

    # 4. A substitute under an invented country sign is still refused.
    with patch.object(engine["vault_module"], "_render_token",
                      return_value=SYNTHETIC_PHONE_FAKE):
        phone = vault.tokenize(SYNTHETIC_PHONE_REAL, "PHONE")
    raw = json.dumps({"phone": phone.replace("+7", "+3", 1)})
    out = redact.unmask_arguments(raw, vault)
    checks["refused country sign alarms"] = bool(
        redact.surviving_substitutes(raw, out, vault, True))

    # 5. An EXACTLY TYPED alphanumeric record keeps its owner, and its leftover is
    #    reported by ownership — not by the fragment grammar this review touches.
    vault2 = engine["Vault"](":memory:", "synthetic-uuid-flash-review-typed")
    with patch.object(engine["vault_module"], "_render_token",
                      return_value=SYNTHETIC_CODE_FAKE):
        typed = vault2.tokenize(SYNTHETIC_CODE_REAL, "CREDIT_SUBJECT_CODE")
    raw = json.dumps({"subject_code": typed}, ensure_ascii=False)
    out = redact.unmask_arguments(raw, vault2)
    checks["exact typed record owned"] = (
        typed in redact.surviving_substitutes(raw, raw, vault2, True)
        and json.loads(out)["subject_code"] == SYNTHETIC_CODE_REAL
        and not redact.surviving_substitutes(raw, out, vault2, True))

    # 6. The ordinary path: a transcript with no substitute in it stays silent.
    raw = json.dumps({"query": "покажи отчёт за март"}, ensure_ascii=False)
    checks["clean argument silent"] = not redact.surviving_substitutes(
        raw, redact.unmask_arguments(raw, vault), vault, True)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="the prototype/ directory of the tree to inspect")
    parser.add_argument("--characterize", action="store_true",
                        help="PASS when the defect reproduces, FAIL when it does not")
    args = parser.parse_args()

    proto = args.engine.resolve()
    if not (proto / "pseudex" / "vault.py").is_file():
        print(f"no engine at {proto}")
        return 2
    engine = _engine(proto)
    vault = _seeded_vault(engine)

    parts = _parts(vault)
    folded = engine["translit"].fold(SYNTHETIC_FRAGMENT)
    tokens, finance, named = _fragment_candidates(
        engine, json.dumps({"thread_id": SYNTHETIC_UUID}))
    owner = vault.residual_of(SYNTHETIC_FRAGMENT)

    print(f"engine: {proto}")
    print(f"fold({SYNTHETIC_FRAGMENT!r}) = {folded!r}")
    print(f"token_parts single-letter keys = "
          f"{sorted(p for p, _t in parts if len(p) == 1)}")
    print(f"candidate scanners: token_re={tokens}")
    print(f"                    FINANCE={finance}")
    print(f"                    named={named}")
    print(f"residual_of({SYNTHETIC_FRAGMENT!r}) = {owner!r}")
    bad = _negatives(engine, vault)
    for name, residual in bad.items():
        print(f"  negative {name:<12} residual={residual}")
    good = _positives(engine, vault)
    for name, ok in good.items():
        print(f"  positive {name:<26} {ok}")

    residual_found = any(bad.values())
    all_positive = all(good.values())
    collapsed = owner is not None

    if args.characterize:
        # A characterization that cannot fail certifies nothing.
        reproduced = residual_found and collapsed and SYNTHETIC_FRAGMENT in bad["uuid"]
        print(f"\ncharacterize: reproduced={reproduced} "
              f"(partial: residual={residual_found} collapse={collapsed})")
        return 0 if reproduced else 1
    print(f"\ncontract: false_residual={residual_found} all_positive={all_positive}")
    return 0 if (not residual_found and all_positive) else 1


if __name__ == "__main__":
    raise SystemExit(main())
