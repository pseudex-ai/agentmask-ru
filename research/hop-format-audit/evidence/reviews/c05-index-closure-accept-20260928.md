# C05 index-closure repair — independent re-check

Date: 2026-09-28. Reviewer: independent (read-only on code).
Scope: the `declared_keys` repair in `translit.py` + `vault.py` NAME `fake_parts`
branch + `test_derived_forms.py` fixtures. Verdict: **ACCEPTED_FIX**.

## Files verified (actual working-tree content, not narration)

- `prototype/pseudex/translit.py` — `declared_keys(word)` (lines 188–222): enumerates
  the fold of every rendering the word's declared units produce (cartesian product,
  `_MAX_DECLARED_SPELLINGS = 100_000` cap, empty-key guard). `main()` (lines 290–310)
  asserts, over the 309-word fake pool: every declared spelling aligns back AND its
  fold is in the word's `declared_keys`, and no declared key has two owners.
- `prototype/pseudex/vault.py` — NAME `fake_parts` branch (lines 2867–2899) indexes
  `translit.declared_keys(word)` per Cyrillic word instead of only `translit.folded(word)`.
  `residual_of` (lines 3640–3746) folds Latin candidates before lookup.
- `prototype/test_derived_forms.py` — pinned `Майя Устинова` block (104–110) plus three
  sibling fixtures (120–130): Михаил Жуков→MIHAIL ZHUKOV→ALEKSANDR PETROV, Фёдор
  Кузнецов→FIODOR KUZNETSOV→PIOTR SOKOLOV, Надежда Жукова→NADEJDA ZHUKOVA→NIKOLAY EGOROV.

Note: `vault.py` also carries unrelated in-flight sprint changes (spoken ИНН/карта,
`shown_forms`, digit-signature typed lookup). Those are outside this row's scope; the
C05 repair is the NAME-branch index closure only.

## Commands and exit codes

All run from `prototype/` with `PYTHONDONTWRITEBYTECODE=1` and `.venv/bin/python`.

| # | command | exit |
|---|---|---|
| 1 | `python -m pseudex.translit` | 0 |
| 2 | `python test_derived_forms.py` | 0 |
| 3 | adversarial probes + negative controls (stdin script below) | 0 |
| 4 | `python test_overmasking.py` | 0 |
| 5 | cross-word `declared_keys` collision check (stdin script below) | 0 |

## Observed outputs

### 1. translit self-test
```
translit: PASS
```
Includes the fold invariant over standards + fake pool, the declared-closure property,
the one-owner-per-declared-key property, and the align/refuse cases — all pass.

### 2. test_derived_forms.py
All 17 checks PASS, including the three pinned class-closure fixtures:
```
PASS  зафиксированная Михаил Жуков как MIHAIL ZHUKOV не оставляет fake-имя
PASS  зафиксированная Фёдор Кузнецов как FIODOR KUZNETSOV не оставляет fake-имя
PASS  зафиксированная Надежда Жукова как NADEJDA ZHUKOVA не оставляет fake-имя
производные подмены возвращаются производными настоящего значения в конвенции модели
```

### 3. Independent adversarial probes (REAL Vault + unmask_arguments)
```python
from unittest.mock import patch
patch("pseudex.vault._fake_name", return_value=FAKE)
v = Vault(":memory:","x").for_conversation("one"); v.tokenize(REAL,"NAME")
json.loads(unmask_arguments(json.dumps({"c":{"n":WRITTEN}}), v))["c"]["n"]
```
| probe | REAL | FAKE | WRITTEN | restored | expected | verdict |
|---|---|---|---|---|---|---|
| х→h | александр петров | Михаил Жуков | MIHAIL ZHUKOV | ALEKSANDR PETROV | ALEKSANDR PETROV | PASS |
| ё→io | пётр соколов | Фёдор Кузнецов | FIODOR KUZNETSOV | PIOTR SOKOLOV | PIOTR SOKOLOV | PASS |

Both restore the REAL name; the fake given name is not left beside the real surname.

### Negative controls (with «Михаил Жуков» minted, `v.residual_of(s)`)
| s | result | expected | verdict |
|---|---|---|---|
| MIHAIL PETROV | None | None | PASS |
| MIHAILOV | None | None | PASS |
| JUKOVA | None | None | PASS |
| MIHAIL IVANOV | None | None | PASS |
| MIHAIL | «Михаил Жуков» | non-None | PASS |
| JUKOV | «Михаил Жуков» | non-None | PASS |
| MIHAIL ZHUKOV | «Михаил Жуков» | non-None | PASS |

Every-word-must-match-and-agree holds: partial Latin never resolves, whole/subset
forms do.

### 4. Over-masking precision parity
```
наблюдаемая точность: 99.5%   (было 69.2% до правок 16.08)
```
Unchanged from the 99.5% reported on HEAD → no over-masking regression from the
widened index.

### 5. Cross-word key collisions
Over `ASSETS.get().fakes.first + last + last_invariant + names.patronymics_masc +
names.patronymics_femn`, deduplicated:
```
total distinct words: 309
colliding keys: 0
max keys per word: 8 (Лебедев)
```
309 words, 0 shared fold keys — no two different fake words ever produce the same
`declared_keys` entry.

## Verdict

**ACCEPTED_FIX.** Every probe, every negative control, the precision parity (99.5%),
and the zero-collision property hold. The index is closed over the renderings
`UNITS` declares (verified by the property self-test and the 0-collision run), and
`align` — not `fold` — still decides which fake word a rendering came from.
