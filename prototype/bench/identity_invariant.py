"""FREE identity-invariant metric — no model, no network.

Measures, per PII type, whether ONE identity written in several forms collapses
to ONE fake. The invariant the product promises: one person/address/phone = one
substitute, across case/order/dictation and across mutable details (flat/entrance
for an address, patronymic for a name, +7 vs 8 for a phone).

Run:  cd prototype && .venv/bin/python bench/identity_invariant.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from testkit import load_dev_bundle  # noqa: E402
load_dev_bundle()
from pseudex.vault import Vault, canonicalize  # noqa: E402

# (title, entity_type, expect, [forms, ...])
#   expect="collapse" — all forms MUST mint ONE fake (the invariant).
#   expect="differ"  — all forms MUST mint DIFFERENT fakes (negative control).
GROUPS = [
    ("NAME case/order (one person)", "NAME", "collapse", [
        "Иванов Пётр", "Иванову Петру", "Иванова Петра", "Пётр Иванов"]),
    ("NAME different people (must differ)", "NAME", "differ", [
        "Иванов Пётр", "Иванов Николай"]),
    ("NAME with/without patronymic (one person)", "NAME", "collapse", [
        "Иванов Пётр Сергеевич", "Иванов Пётр", "Иванов П. С."]),
    ("LOC form: case/separators (one address)", "LOC", "collapse", [
        "улица Лермонтова, дом 38, квартира 7",
        "ул. Лермонтова 38 кв 7",
        "улица лермонтова дом 38 квартира 7"]),
    ("LOC dictation vs digits (one address)", "LOC", "collapse", [
        "улица лермонтова дом тридцать восемь квартира семь",
        "улица Лермонтова дом 38 квартира 7"]),
    ("LOC flat change (same street+house)", "LOC", "collapse", [
        "улица Лермонтова дом 38 квартира 7",
        "улица Лермонтова дом 38 квартира 42"]),
    ("LOC entrance change (same street+house)", "LOC", "collapse", [
        "улица Лермонтова дом 38 подъезд 1 квартира 7",
        "улица Лермонтова дом 38 подъезд 3 квартира 7"]),
    ("PHONE +7/8/no-separators (one number)", "PHONE", "collapse", [
        "+7 916 402-11-87", "8 916 402-11-87", "89164021187"]),
]


def main() -> int:
    v = Vault(":memory:", "identity-metric")
    passed = 0
    total = 0
    for title, et, expect, forms in GROUPS:
        tokens = {}
        for f in forms:
            c = canonicalize(et, f)
            t = v.tokenize(f, et)
            tokens.setdefault(t, []).append((f, c))
        uniq = len(tokens)
        ok = (uniq == 1) if expect == "collapse" else (uniq == len(forms))
        passed += 1 if ok else 0
        total += 1
        mark = "OK " if ok else ("BAD" if expect == "collapse" else "BAD")
        print(f"[{mark}] {title} [{expect}]: {uniq} фейк(ов) на {len(forms)} форм")
        if not ok:
            for t, rows in tokens.items():
                for f, c in rows:
                    print(f"        {f!r:56} -> {t}")
    print(f"\n=== Identity-инвариант: {passed}/{total} групп корректны ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
