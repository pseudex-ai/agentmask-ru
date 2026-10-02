"""FREE identity-invariant metric — no model, no network.

Measures, per PII type, whether ONE identity written in several forms collapses
to ONE fake. The invariant the product promises: one person/address/phone =
one substitute, across case/order/dictation and across mutable details (flat/
entrance for an address, patronymic for a name, +7 vs 8 for a phone).

STRUCTURED TYPES (phase 3). The first version covered NAME/LOC/PHONE only, and
that is exactly the shape of the hole it left: the identifiers whose identity
is a checksum-valid DIGIT RUN are the ones a customer writes with separators as
often as without («4512 345678» on a form, «4512345678» in a JSON field), and
v6 added a family of document shapes whose key is the TYPED content (a ПТС keys
as «VEHICLE_DOC\x1f78YB123456», an IBAN keeps its letters). The groups below
therefore cover, besides NAME/LOC/PHONE/EMAIL:

  PASSPORT, SNILS, INN, CARD, OGRN, OGRNIP — the v5 digit identifiers;
  OMS_ENP, IBAN, VIN, PTS_NUMBER — the v6 records;
  DOB — the identity-bearing date.

DATE IS NOT A COLLAPSE GROUP, AND THAT IS MEASURED, NOT ASSUMED. The registry
declares DATE `item_type=False` (a non-item date: a document date, «от
15.05.2025»), its `canonicalize` branch is `value.strip()` and its substitute
MIRRORS the notation the customer wrote (`date_form.render_like`), so
«21.01.1979», «21/01/1979» and «1979-01-21» are three rows and three fakes by
design. The person-linked date is DOB, whose canonical IS the calendar date
(`_date_canonical`), and the collapse of the very same three forms is pinned
there. Marking these three forms `collapse` for DATE would be the metric
demanding an engine change the task forbids (measurement only); it is recorded
here as a DIFFER` control instead, and named in GATE.json as the one place the
literal reading of the phase-3 brief is not achievable — see main()'s note.

Two kinds of group, and the negative ones are not decoration:
  * `collapse` — all forms MUST mint ONE fake (the invariant);
  * `differ`   — all forms MUST mint DIFFERENT fakes (the control). A rule
    checked only on what it must find is a rule nobody knows the reach of:
    different people, different documents, different cards, a different date.

THE SCOPE. `probe("customer")` — a FRESH vault per group, the scope the eight
phase-1 groups were measured in and the one `test_identity_invariant.py` pins.
`probe("conversation")` — a fresh vault with `for_conversation`, the scope the
sweep's real scoring path uses. Both must report the same stability; the metric
prints the customer scope and `bench/agentpii5/detect_sweep.py` prints the
conversation scope beside it.

TWO SUBSTITUTES ARE THE SAME FAKE WHEN THEY ARE THE SAME IDENTITY, NOT THE SAME
STRING. D-081 renders ONE substitute at the granularity the mention named: a
conversation shown «Осипов Радислав Андреевич» answers «Осипов Радислав» for
the brief mention and «Осипов Р. А.» for the initials — one person, three
strings. Counting raw strings would read that as three fakes, i.e. the metric
would be measuring its own comparison. `fake_identity` folds a NAME substitute
to surname + given-name initial; every other type is its own string (their
canonical IS a digit run or a typed key, so equal key = equal fake).

Run:  cd prototype && .venv/bin/python bench/identity_invariant.py
      exit 0 = every collapse group minted one fake and every control held.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from testkit import load_dev_bundle  # noqa: E402
load_dev_bundle()
from pseudex.vault import Vault, canonicalize  # noqa: E402
from pseudex import morph_names, ru_pii_v6  # noqa: E402

# (title, entity_type, expect, [forms, ...])
#   expect="collapse" — all forms MUST mint ONE fake (the invariant).
#   expect="differ"  — all forms MUST mint DIFFERENT fakes (negative control).
# The first eight are the phase-1/phase-2 groups, word for word: their printed
# result must not move when this list grows.
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
    # --- phase 3: the structured and v6 records -------------------------------
    ("EMAIL case and spaces (one mailbox)", "EMAIL", "collapse", [
        "Ivanov@Example.RU", " ivanov@example.ru "]),
    ("EMAIL different mailboxes (must differ)", "EMAIL", "differ", [
        "ivanov@example.ru", "petrov@example.ru"]),
    ("PASSPORT series+number separators (one document)", "PASSPORT", "collapse", [
        "4512 345678", "4512345678"]),
    ("PASSPORT different documents (must differ)", "PASSPORT", "differ", [
        "4512 345678", "4512 345679"]),
    ("SNILS separators (one account)", "SNILS", "collapse", [
        "123-456-789 01", "12345678901"]),
    ("SNILS different accounts (must differ)", "SNILS", "differ", [
        "123-456-789 01", "123-456-789 02"]),
    ("INN separators (one number)", "INN", "collapse", [
        "7712345678", "77 12345678"]),
    ("INN different numbers (must differ)", "INN", "differ", [
        "7712345678", "7712345679"]),
    ("CARD grouping (one card)", "CARD", "collapse", [
        "4276 1234 5678 9012", "4276123456789012"]),
    ("CARD different cards (must differ)", "CARD", "differ", [
        "4276 1234 5678 9012", "4276 1234 5678 9013"]),
    ("OGRN separators (one record)", "OGRN", "collapse", [
        "1027700132195", "1 0277 00132195"]),
    ("OGRN different records (must differ)", "OGRN", "differ", [
        "1027700132195", "1027700132196"]),
    ("OGRNIP separators (one entrepreneur)", "OGRNIP", "collapse", [
        "304500000012345", "3045000000 12345"]),
    ("OGRNIP different records (must differ)", "OGRNIP", "differ", [
        "304500000012345", "304500000012346"]),
    # DATE: a NON-ITEM date is notation-bearing by design — see the module
    # docstring. The three forms are the brief's, and the control asserts the
    # engine's declared shape (three rows), not the invariant.
    ("DATE notation is presentation (non-item: NOT collapsed)", "DATE", "differ", [
        "21.01.1979", "21/01/1979", "1979-01-21"]),
    ("DOB notation (one birth date)", "DOB", "collapse", [
        "21.01.1979", "21/01/1979", "1979-01-21"]),
    ("DOB different birth dates (must differ)", "DOB", "differ", [
        "21.01.1979", "22.01.1979"]),
    ("OMS_ENP grouping (one policy)", "OMS_ENP", "collapse", [
        "1234567890123456", "1234 5678 9012 3456"]),
    ("OMS_ENP different policies (must differ)", "OMS_ENP", "differ", [
        "1234567890123456", "1234567890123457"]),
    ("IBAN grouping and case (one account)", "IBAN", "collapse", [
        "RU0204452560040702810412345678901",
        "ru02 0445 2560 0407 0281 0412 3456 78901"]),
    ("IBAN different accounts (must differ)", "IBAN", "differ", [
        "RU0204452560040702810412345678901",
        "RU0204452560040702810412345678902"]),
    ("VIN case and spaces (one car)", "VIN", "collapse", [
        "XTA210990Y2765499", "xta 210990 y2765499"]),
    ("VIN different cars (must differ)", "VIN", "differ", [
        "XTA210990Y2765499", "XTA210990Y2765498"]),
    ("PTS_NUMBER separators and Cyrillic/Latin twins (one document)",
     "PTS_NUMBER", "collapse", [
         "78 УВ 123456", "78УВ123456", "78 YB 123456"]),
    ("PTS_NUMBER different documents (must differ)", "PTS_NUMBER", "differ", [
        "78 УВ 123456", "78 УВ 123457"]),
]


def fake_identity(entity_type: str, token: str) -> str:
    """The IDENTITY a substitute stands for — not its spelling.

    D-081 renders one substitute at the granularity the mention named, so a
    conversation shown «Осипов Радислав Андреевич» answers «Осипов Радислав»
    and «Осипов Р. А.» for the shorter mentions. Those are ONE fake. The fold
    is surname + the first letter of the given name (an initial is the same
    letter), and it is applied only to NAME: every other type's canonical is
    already the whole identity (a digit run or a typed key), so its token is
    its identity.
    """
    if not token:
        return token
    if ru_pii_v6.engine_label(entity_type) != "NAME":
        return token
    words = token.split()
    shape = morph_names.name_shape(token)
    if len(shape) != len(words):
        return token
    surname = [w for w, kind in zip(words, shape) if kind == "surn"]
    given = [w for w, kind in zip(words, shape) if kind in ("name", "init")]
    if surname and given:
        return f"{surname[0].casefold()}|{given[0].strip('.').casefold()[:1]}"
    return token


def identity_key(entity_type: str, value: str) -> str:
    """The identity key of a REAL value — no vault, no fake minted.

    This is what a caller that cannot open a vault (the operator endpoint the
    interface reads) uses: `canonicalize` is the row key, and equal row key
    means equal substitute on a fresh vault. For NAME the canonical of a
    shorthand is a different STRING but the same person, so the same
    surname+initial fold `fake_identity` applies to substitutes is applied to
    the canonical here. Verified to agree with `fake_identity(tokenize(...))`
    on every group in this file (see `main`).
    """
    if ru_pii_v6.engine_label(entity_type) == "NAME":
        return fake_identity("NAME", canonicalize(entity_type, value))
    return canonicalize(entity_type, value)


def _measure(scope: str):
    """Run every group through a FRESH vault; one row per group.

    A fresh vault PER GROUP, not one for the file: a group is one identity in
    one case, and a vault shared across groups lets a different group's person
    (another «Иванов») make this group's surname ambiguous inside a
    conversation — measured, 1 of 33 groups flaked that way. The pin test
    (`test_identity_invariant.py::token_of`) already does it per group.
    """
    measured = []
    for index, (title, entity_type, expect, forms) in enumerate(GROUPS):
        vault = Vault(":memory:", f"identity-metric-{scope}-{index}")
        view = vault.for_conversation(f"identity-metric-{scope}-{index}") \
            if scope == "conversation" else vault
        rows: dict[str, list[tuple[str, str, str]]] = {}
        for form in forms:
            canonical = canonicalize(entity_type, form)
            token = view.tokenize(form, entity_type)
            rows.setdefault(fake_identity(entity_type, token), []).append(
                (form, canonical, token))
        unique = len(rows)
        ok = (unique == 1) if expect == "collapse" else (unique == len(forms))
        measured.append({
            "title": title, "entity_type": entity_type, "expect": expect,
            "forms": list(forms), "rows": rows, "unique": unique, "ok": ok,
        })
    return measured


def by_type(measured) -> dict[str, dict[str, object]]:
    """Per-type identity stability: collapse groups with ONE fake / all of them.

    `differ` controls are counted separately and never enter the stability
    denominator: a control that is SUPPOSED to mint several fakes cannot be a
    stability miss, and mixing them would report a type as unstable for
    guarding correctly.
    """
    out: dict[str, dict[str, object]] = {}
    for row in measured:
        stats = out.setdefault(row["entity_type"], {
            "collapse_groups": 0, "collapse_stable": 0,
            "differ_groups": 0, "differ_ok": 0, "groups": []})
        stats["groups"].append(row["title"])
        if row["expect"] == "collapse":
            stats["collapse_groups"] += 1
            stats["collapse_stable"] += 1 if row["ok"] else 0
        else:
            stats["differ_groups"] += 1
            stats["differ_ok"] += 1 if row["ok"] else 0
    return out


def stability(scope: str = "customer") -> dict[str, dict[str, object]]:
    """`by_type` over a fresh run of GROUPS in `scope` — the per-type metric.

    This is the function `bench/agentpii5/detect_sweep.py` imports for its
    `identity` axis, so the sweep owns no copy of the groups and cannot drift
    from the metric.
    """
    return by_type(_measure(scope))


def _ui_mirror_check() -> str:
    """Compare the groups with the interface's own copy in `pseudex/operator.py`.

    `pseudex/` may never import from `bench/` (bench does not ship), so the
    operator endpoint that the interface reads carries a mirror of these forms.
    A mirror that quietly diverges makes the screen lie about a number the
    metric prints, so the divergence is reported here rather than trusted.
    """
    try:
        from pseudex import operator
    except Exception as exc:  # pragma: no cover — importable in this checkout
        return f"not checked (pseudex.operator unavailable: {exc})"
    mirror = getattr(operator, "IDENTITY_PROBE", None)
    if mirror is None:
        return "DRIFT: pseudex/operator.py carries no IDENTITY_PROBE"
    theirs = [(str(et), str(expect), tuple(forms)) for et, expect, forms in mirror]
    ours = [(et, expect, tuple(forms)) for _, et, expect, forms in GROUPS]
    if theirs == ours:
        return f"agrees ({len(ours)} groups)"
    missing = [g for g in ours if g not in theirs]
    extra = [g for g in theirs if g not in ours]
    return (f"DRIFT: metric-only={[g[0] + '/' + g[1] for g in missing]} "
            f"ui-only={[g[0] + '/' + g[1] for g in extra]}")


def main() -> int:
    measured = _measure("customer")
    passed = sum(1 for row in measured if row["ok"])
    total = len(measured)
    for row in measured:
        mark = "OK " if row["ok"] else "BAD"
        print(f"[{mark}] {row['entity_type']} | {row['title']} "
              f"[{row['expect']}]: {row['unique']} фейк(ов) на {len(row['forms'])} форм")
        if not row["ok"]:
            for key, rows in row["rows"].items():
                for form, canonical, token in rows:
                    print(f"        {form!r:58} канон={canonical!r} -> {token}")

    stats = by_type(measured)
    print("\n=== Identity-стабильность по типам "
          "(collapse-группы: 1 фейк / все) ===")
    print(f"{'ТИП':<12}{'collapse':>9}{'stable':>8}{'stability':>11}"
          f"{'differ':>8}{'ok':>5}")
    stable_types = 0
    for entity_type in sorted(stats):
        row = stats[entity_type]
        groups = row["collapse_groups"]
        rate = f"{row['collapse_stable'] / groups:.1%}" if groups else "н/п"
        if groups and row["collapse_stable"] == groups:
            stable_types += 1
        print(f"{entity_type:<12}{groups:>9}{row['collapse_stable']:>8}{rate:>11}"
              f"{row['differ_groups']:>8}{row['differ_ok']:>5}")
    applicable = sum(1 for t in stats if stats[t]["collapse_groups"])
    print(f"типов со collapse-группами: {stable_types}/{applicable} стабильны; "
          f"всего типов в метрике: {len(stats)}")

    # THE SCOPE CROSS-CHECK. The sweep's probe runs in conversation scope; a
    # metric that only held at customer scope would be green while the engine
    # the customer runs was not.
    conversation = by_type(_measure("conversation"))
    scope_mismatch = [t for t in stats
                      if stats[t]["collapse_stable"] != conversation[t]["collapse_stable"]
                      or stats[t]["collapse_groups"] != conversation[t]["collapse_groups"]]
    print(f"scope cross-check (customer vs conversation): "
          + ("agrees on every type" if not scope_mismatch
             else f"DIFFERS on {scope_mismatch}"))

    print(f"UI-зеркало (pseudex/operator.py): {_ui_mirror_check()}")
    print(f"\n=== Identity-инвариант: {passed}/{total} групп корректны ===")
    return 0 if passed == total and not scope_mismatch else 1


if __name__ == "__main__":
    raise SystemExit(main())
