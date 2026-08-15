"""Prove the persistent canonical vault: (1) the same number in different
formats maps to ONE token; (2) the mapping survives a restart.
This is the fix for the cross-session "order not found / wrong number" failure.
"""

import pathlib

from pseudex.vault import Vault

DB = "vault_test.db"


def main() -> None:
    pathlib.Path(DB).unlink(missing_ok=True)

    vault = Vault(DB, "demo")
    token_a = vault.tokenize("+7 999 111 22 33", "PHONE")
    token_b = vault.tokenize("89991112233", "PHONE")  # same number, other format
    print("same number / different format -> one token:", token_a == token_b, "|", token_a)
    # Canonicalization is the DEDUP KEY (both spellings share one token), but what
    # the tool receives is the surface form the user actually typed.
    print("tool would receive (as user typed):", vault.detokenize(token_a))

    del vault
    reopened = Vault(DB, "demo")  # simulate restart / second instance
    print("survives restart (detok still works):", reopened.detokenize(token_a))

    pathlib.Path(DB).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
