# F1 review — PHONE current-hop form (skeptic, read-only)

Date: 2026-09-27 12:34 +05. Scope: the working-tree diff only —
`prototype/pseudex/redact.py`, `prototype/pseudex/vault.py`,
`prototype/test_phone_hop_form.py`. Read-only; no engine edit. Fingerprints at
review time: `redact.py` `ab08d37a…`, `vault.py` `048a4f1c…`,
`test_phone_hop_form.py` `c076b97b…`.

Method: read the full diff and the surrounding functions, ran the phone suite
and the collisions suite, and probed edge shapes/spoken originals in a
temporary directory. No secrets, env or config printed.

Suites observed here: `test_phone_hop_form.py` → 24/24 + 7/7 controls, exit 0;
`test_collisions.py` → all green, exit 0.

## Findings

### F-1 (low, bounded) — a 12-digit written run keeps the agent's bogus prefix

`_digits_in_form_of` splices as `written_digits[:-10] + real_digits[-10:]`. For a
12-digit written run the first two written digits survive as the country prefix,
so the tool can receive an unusable number.

Repro:

```python
_phone_in_form_of("791621488032", "+79162148803") == "799162148803"   # 12 digits, prefix 79
```

This is the pre-existing prefix rule, but before F1 PHONE tokens did not reach it
from `_restore_tokens_spans` (only dates/other numerics did); F1 makes it
reachable for PHONE on both legs. Content is still the right person's last ten
digits — no cross-person leak, only a malformed agent-authored shape. Unsupported
shapes that do not fullmatch `_NUMERIC_FORM` (`"9162148803 доб. 5"`, `"2148803"`,
`"phone"`, `""`) correctly fall back to canonical E.164, so the blast radius is
the 11–12-digit prefix path only.

### F-2 (informational, test only) — the homoglyph control depends on form mirroring

`regression_controls` patches `pseudex.vault._fake_phone` to `"+79795553322"`,
but the mint mirrors the customer's grouping, so `shown` is
`"8 979 555-33-22"`, not the flat patched string. The assertion
`tool_value(shown, vault) == literal` therefore passes through the
`normalize(real) == rendered` branch of `_phone_in_form_of`, not through a
flat-substitute path. Under a genuinely flat substitute the same input would
return canonical digits; that is still the owner contract (agent form), so the
assertion `== literal` is stronger than the contract. Test clarity, not an
engine defect.

## Question-by-question verdicts

### 1. Typed lookup tuple ordering / full-signature precedence — no finding

- `resolve_digit_signatures_typed` returns `{**tails, **exact}`; a `digits`
  exact row overwrites the `digits10` tail for the same queried signature —
  identical to the previous `resolved = _lookup("digits10"); resolved.update(
  _lookup("digits"))  # exact wins`.
- `_restore_reformatted_spans` still prefers the full signature:
  `hit = resolved.get(digits) or (resolved.get(digits[-10:]) if len>=10 else None)`.
- The untyped `resolve_digit_signatures` now unpacks `(kind, value)` and drops
  the kind; its output is the same `dict[str, str]` as before.
- `_digit_signatures` populates `digits10` only for PHONE and `digits` for every
  numeric type, so a tail-vs-exact collision is possible in principle; I could
  not construct one with natural mints, and the winner is unchanged by the diff.
  Reported as not-disproven, not as a defect.

### 2. Unsupported numeric shapes — see F-1; otherwise safe

Verified fallbacks above. `_phone_in_form_of` also returns canonical E.164 when
the written form does not parse, never a mix of two entities' digits.

### 3. Exact copied typo — works; no engine finding (see F-2)

Repro, real `"8 916 214-88-О3"` (Cyrillic `О`), substitute mirrors its grouping:

```python
normalize("8 916 214-88-О3") == "8 916 214-88-03"
_phone_in_form_of("8 979 555-33-22", "8 916 214-88-О3") == "8 916 214-88-О3"   # literal kept
```

The branch `return real if normalized == rendered else rendered` is what
preserves a copied spelling; a spoken original fails that equality and is
rendered to digits (verified: spoken real → `+79500640017` on both tool and
answer legs).

### 4. PHONE current agent form on tool + answer — no finding

- `_restore_tokens_spans` adds `elif kind == "PHONE": value =
  _phone_in_form_of(surface, value)` ahead of the `for_tool and kind == "NAME"`
  branch, so it applies on the answer leg (`for_tool=False`) as well as the tool
  leg. Kinds are mutually exclusive, so the ordering is safe.
- `_restore_verbatim_spans` and `_restore_reformatted_spans` also route PHONE
  through `_phone_in_form_of`.
- Verified on `+7…`, `8 (…)`, ten bare digits and `+7 grouped`, on both
  `unmask_arguments` and `unmask_text`; prose quantities and `заказ 42` are
  untouched; the typed lookup keeps `kind == "PHONE"` so a SNILS never takes the
  phone prefix rule.

### 5. Leased-asset dependency — no finding

`_phone_in_form_of` calls `normalize(real)`, which reads
`ASSETS.get().lookalike`, but the restore path already required the bundle
unconditionally: `_restore_tokens_spans` begins with `token_re()` →
`_token_re(ASSETS.version)`. Repro with `ASSETS.unload()`: PHONE restore raises
`BundleNotLeased`, and so does SNILS restore on the unchanged path — the phone
branch adds no new asset-gated path.

### 6. Schema / tenant isolation — no finding

- `_lookup_typed` keeps `WHERE customer=? AND {column} IN (…)` and the
  `_answers_another_dialogue` filter, exactly as `_lookup`.
- Cross-tenant control: a token minted under `two-phones` comes back unchanged
  from `other-tenant`.
- No new column or migration: `digits`/`digits10` already exist; the diff only
  reads them, and `resolve_digit_signatures_typed` issues the same two queries as
  `resolve_digit_signatures` (no new DB round trip per lookup).
- `test_collisions.py` green, including Б23/Б28 dialogue scope and the degenerate
  street key.

## Summary

No security or isolation regression found. One low-severity bounded shape issue
(F-1, 12-digit written prefix) and one test-clarity note (F-2). The typed-lookup
precedence is behaviorally identical to the committed code; the added
asset touch is inside a path that was already asset-gated.

## Architect adjudication

F-1 is **not accepted as a new F1 regression**. Before this patch, PHONE already
reached `_digits_in_form_of` on the `for_tool` branch of `_restore_tokens_spans`.
The helper-only probe does not prove that its invented 12-digit string resolves
through the real vault path. Preserving an agent-authored prefix is also the
current contract, not permission to normalize arbitrary tool arguments. An
unsupported-shape policy remains separate; this review does not certify those
fallbacks as universally safe. F-2 is informational: the copied-homoglyph
fixture deliberately pins a supported exact-copy case, not all typo transforms.

The accepted evidence is the independent 24+7 PHONE checks, collision checks,
typed-lookup precedence and tenant scoping review. Broad regression status and
remaining NAME test instability are recorded in [PROGRESS](PROGRESS.md).
