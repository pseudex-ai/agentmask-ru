"""Synthetic contract for alphanumeric candidates misread as NAME initials.

Default is a CAN-FAIL contract: the unfixed engine fails the UUID negative.
--baseline isolates committed HEAD Vault and redact despite dirty source changes.
--characterize proves the pre-existing bug, without treating it as a success.
--trial-fix applies ONLY a process-local candidate-grammar hypothesis; no source
files change. No provider, socket, actual evidence, or persistent vault is used.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
from unittest.mock import patch

from testkit import load_dev_bundle
load_dev_bundle()

from pseudex import redact, vault as vault_module
from pseudex.detect_all import Detector
from pseudex.vault import Vault

SYNTHETIC_UUID = "abcdefab-12a3-4def-abcd-abcdefabcdef"
SYNTHETIC_FRAGMENT = "12a3"


def seeded_vault():
    vault = Vault(":memory:", "synthetic-residual-regression").for_conversation("synthetic-thread")
    source = "Зорин В. Г."
    # Only the random draw is fixed; actual detection, mask, indexing, scope,
    # unmask and residual reporting all remain production code.
    spans = Detector().detect(source)
    assert len(spans) == 1 and spans[0].entity_type == "NAME"
    with patch.object(vault_module, "_render_token", return_value="Тестов А. Б."):
        shown = redact.mask_text(source, vault, spans)
    assert shown == "Тестов А. Б."
    assert vault.shown_forms()
    return vault


def trial_name_grammar(original):
    def proposed(self, candidate):
        # Diagnosis only: a digit-bearing ASCII word is not a transliteration of
        # a NAME initial. Do NOT alter translit.fold globally or any exact-token,
        # typed-secret, numeric-fragment, conflict, or refused-sign guard.
        if any(word.isascii() and any(c.isdigit() for c in word)
               for word in candidate.split() if len(word) > 2):
            return None
        return original(self, candidate)
    return proposed


def check_negatives(vault, expect_defect):
    cases = {
        "uuid": {"thread_id": SYNTHETIC_UUID},
        "label": {"label": SYNTHETIC_FRAGMENT},
        "path": {"path": "/synthetic/12a3/report.csv"},
        "code": {"code": 'value = "12a3"'},
        "nested": {"items": [{"thread_id": SYNTHETIC_UUID}]},
        "separate_words": {"label": "12a3 abcd"},
    }
    counts = {}
    for name, arguments in cases.items():
        raw = json.dumps(arguments, ensure_ascii=False)
        out = redact.unmask_arguments(raw, vault)
        assert json.loads(out) == arguments, name + ": own argument was rewritten"
        residual = redact.surviving_substitutes(raw, out, vault, True)
        counts[name] = len(residual)
        if expect_defect:
            assert SYNTHETIC_FRAGMENT in residual, name + ": characterization no longer reproduces"
        else:
            assert not residual, name + ": false-positive NAME residual on an opaque value"
    return counts


def check_positive_guards(vault):
    raw = json.dumps({"name": "Тестов А. Б."}, ensure_ascii=False)
    out = redact.unmask_arguments(raw, vault)
    assert json.loads(out)["name"] == "Зорин В. Г."
    assert not redact.surviving_substitutes(raw, out, vault, True)
    # If a real minted NAME ever remains standing, its guard MUST still fire.
    assert redact.surviving_substitutes(raw, raw, vault, True)
    assert vault.residual_of("Testov") == "Тестов А. Б."

    # An actual ambiguous shown NAME is refused by core, not merely by a test
    # stub. The conflict must remain visible after the candidate-grammar change.
    vault.remember_shown("Антон", "Виктор", "NAME")
    vault.remember_shown("Антон", "Павел", "NAME")
    raw = json.dumps({"name": "Антон"}, ensure_ascii=False)
    out = redact.unmask_arguments(raw, vault)
    assert json.loads(out)["name"] == "Антон"
    assert "Антон" in redact.surviving_substitutes(raw, out, vault, True)

    # A numeric identity with an invented country sign remains refused. This
    # exercises an independent real unresolved-token path, not an exact mock.
    with patch.object(vault_module, "_render_token", return_value="+7 939 222-76-19"):
        token = vault.tokenize("+7 916 555-01-23", "PHONE")
    raw = json.dumps({"phone": token.replace("+7", "+3", 1)})
    out = redact.unmask_arguments(raw, vault)
    assert json.loads(out) == json.loads(raw)
    assert redact.surviving_substitutes(raw, out, vault, True)

    # A genuinely typed alphanumeric token is NOT waived merely because the
    # NAME lookup now rejects it. Exact typed ownership must still alarm if left.
    with patch.object(vault_module, "_render_token", return_value="12a3"):
        typed = vault.tokenize("98z7", "CREDIT_SUBJECT_CODE")
    raw = json.dumps({"credit_subject_code": typed})
    assert typed in redact.surviving_substitutes(raw, raw, vault, True)
    out = redact.unmask_arguments(raw, vault)
    assert json.loads(out)["credit_subject_code"] == "98z7"
    assert not redact.surviving_substitutes(raw, out, vault, True)
    return 6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--characterize", action="store_true")
    group.add_argument("--trial-fix", action="store_true")
    parser.add_argument("--baseline", action="store_true", help="execute committed HEAD Vault and redact in isolated RAM modules")
    args = parser.parse_args()
    if args.baseline:
        from bench.doubleup.restore_failure_analysis import baseline_module
        global redact, vault_module, Vault
        redact = baseline_module()
        vault_module = redact._baseline_vault
        Vault = vault_module.Vault
    context = (patch.object(Vault, "residual_of", trial_name_grammar(Vault.residual_of))
               if args.trial_fix else nullcontext())
    with context:
        vault = seeded_vault()
        positives = check_positive_guards(vault)
        # Use a fresh fixture so the positive typed token does not contaminate
        # the opaque negative with actual ownership of exactly the same string.
        counts = check_negatives(seeded_vault(), args.characterize)
    print(json.dumps({"mode": "characterize" if args.characterize else "trial-fix" if args.trial_fix else "contract",
                      "baseline": args.baseline,
                      "negative_residual_counts": counts, "positive_guard_groups": positives,
                      "provider_calls": 0, "network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
