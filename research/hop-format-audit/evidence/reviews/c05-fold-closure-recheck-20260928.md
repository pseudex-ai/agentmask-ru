# C05 — independent read-only recheck: the pinned mint reproduces, but the fix was one unit wide

Verdict: **REJECT as terminal acceptance of the candidate as found; repair
implemented and locally verified; C05 stays a candidate until a review that did
not write the repair re-checks it.**

Reviewer: separate-context DSH agent (this session), read-only on the candidate
as found. The C05 code candidate and its `test_derived_forms.py` block were
authored by the previous Codex session; this reviewer is a different agent
lineage and wrote no part of that change. The repair *below* was written by this
agent afterwards, which is exactly why it cannot also accept it.

Date: 2026-09-28. Worktree `Obscura-hop-audit`, branch `research/hop-format-audit`.
Base for every "before" number: a clean `git archive HEAD prototype` checkout in
`/tmp/hop-c05-base`, run with the worktree venv. No file in the worktree was
reset, cleaned or committed.

## 1. The pinned reproducer is real — red on HEAD, green on the candidate

The candidate's own test file was copied onto the clean HEAD checkout, so the
only difference between the two runs is the engine.

```
cd /tmp/hop-c05-base/prototype && .venv/bin/python test_derived_forms.py
FAIL  зафиксированная Майя USTINOVA MAIIA …  получили 'BITYUKOVA MAIIA'
FAIL  зафиксированная Майя USTINOVA MAJYA …  получили 'BITYUKOVA MAJYA'
FAIL  зафиксированная Майя USTINOVA MAYYA …  получили 'BITYUKOVA MAYYA'
НЕ ПРОШЛО: 3

cd Obscura-hop-audit/prototype && .venv/bin/python test_derived_forms.py   -> EXIT 0
```

The failure mode is not cosmetic. `Vault.residual_of("MAIIA")` returned `None`
on HEAD — the model wrote a rendering of the substitute that the index did not
hold, so the restore leg dropped the given name and the **fake** went to the
customer's `name_latin` field beside the real surname. That is the
"Meshcheryakova Anna" class the module docstring exists to prevent.

## 2. The accompanying claim is true, and the shipped self-test does not check it

PROGRESS claimed *"ноль совпавших fold-ключей"* over the 309 leased fake-pool
words. Independently reproduced — but `pseudex.translit.main()` as committed
only checks that **one word's own** key sets coincide; a collision **between two
different words** would have passed it. Checked separately:

```
fake-pool words: 309        distinct fold keys: 309        colliding keys: 0
table-inconsistent words: 0
```

So the claim holds, and the instrument that was said to establish it did not.

## 3. The reason to reject: the same class is one unit away, and it is reachable

`fold` is a sequence of substring replacements; `UNITS` declares several
spellings per unit. For the 309 words these do not close over each other —
**142 (word, unit, option) triples** where the engine's own `align` accepts the
spelling (142/142) and `fold` does not unify it with the word's index key:

| unit | declared option | example fake word | spelling | breaks |
|---|---|---|---|---|
| `е` | `je` | Александр | aljeksandr | 107 words |
| `х` | `h` | Михаил | mihail | 16 words |
| `ё` | `io` | Пётр | piotr | 8 words |
| `ж` | `j` | Надежда | nadejda | 7 words |
| `е` | `ie` / `ye` | Дмитриевич | dmitriievich | 2 words |
| `ь`+ICAO `ъ` | `ie` | Подъячев | podieiachev | 1 word |

False-negative rate on the *declared* rendering set: 941 of the enumerated
spellings fold to a key nobody holds.

**This is not theory; all three were reproduced through the real
`Vault` + `unmask_arguments` path** (pinned fake via `pseudex.vault._fake_name`,
exactly as the accepted C05 fixture does):

```
fake «Михаил Жуков»  written «MIHAIL ZHUKOV»    HEAD: MIHAIL PETROV    (fake given name to CRM)
fake «Фёдор Кузнецов» written «FIODOR KUZNETSOV» HEAD: FIODOR SOKOLOV
fake «Надежда Жукова» written «NADEJDA ZHUKOVA»  HEAD: NADEJDA EGOROV
fake «Пётр Подъячев»  written «PETR PODIEIACHEV» HEAD: IVAN PODIEIACHEV
```

`residual_of('MIHAIL')` was `None` on HEAD purely because
`fold('MIHAIL') = 'mIhaIl'` while the index held `folded('Михаил') = 'mIXaIl'`.

The candidate's `йя` table entries fix exactly one of these. Accepting it would
be closing C05 with one particular form, which the execution contract §9
forbids.

## 4. Why the fix cannot stay in the fold table

The obvious repair — add every declared option to `TRANSLIT_FOLD` — is not
available. `j` is both ГОСТ 7.79-B's `й` and the everyday `ж`; a bare `j` must
fold to the `й` marker for «Юрий»→«jurij», so it cannot simultaneously fold to
the `ж` marker for «Жуков»→«jukov». No entry order separates them, because
`fold` is string-level while the ambiguity is unit-level. This is a limit of the
mechanism, not of the table.

## 5. Repair: make the index closed over the declared renderings

Files: `prototype/pseudex/translit.py`, `prototype/pseudex/vault.py`,
`prototype/test_derived_forms.py`. No leased-data change; `fold` itself is
unchanged and its behaviour is byte-identical.

- `translit.declared_keys(word)` — every fold key the word's **declared**
  renderings produce (Cartesian product over the unit options, deduped,
  hard cap 100 000 spellings, empty key discarded). Measured cost over the
  whole pool: 536 distinct keys against 309 today, **0 keys shared between two
  different fake words**, widest single word 256 spellings / 8 keys.
- `vault.py` NAME mint branch indexes `declared_keys(word)` instead of the one
  default key. The lookup is untouched: it still folds what the model wrote, and
  one of the indexed keys is now its key. `align` — not `fold` — still decides
  which fake word it was.
- `translit.main()` gains the property **stated over the renderings, not over
  `declared_keys`**: every spelling `UNITS` allows must `align` back and its
  fold must be in the word's index, and no key may have two owners. That clause
  cannot be passed by an implementation agreeing with itself.

**The new instrument can fail.** With `declared_keys` monkeypatched to the
pre-repair narrow form, `translit.main()` reports exactly `FAIL (941)` — the
same 941 the independent probe counted.

## 6. Red → green, and the controls

| run | HEAD | candidate | repaired |
|---|---|---|---|
| pinned `Майя` 3 spellings | 3/3 red | 3/3 green | 3/3 green |
| sibling fixtures added here | 3/3 red | 3/3 red | 3/3 green |
| ICAO `PETR PODIEIACHEV` | `IVAN PODIEIACHEV` | — | `IVAN SOKOLOV` |
| `translit.main()` property | — | narrow: 941 FAIL | PASS |

Nearest precision guards, repaired tree (all EXIT 0):
`test_derived_forms.py`, `test_names_morphology.py`, `test_argument_form.py`,
`test_collisions.py`, `test_loop.py`, `test_product.py`,
`test_perf_masking.py` (with `PYTHONFAULTHANDLER=1`; no exit 139 this run),
`test_overmasking.py` **99.5 % observed, identical to HEAD** — the widened index
did not buy recall with over-masking.

Negative controls through the real vault with a `Михаил Жуков` substitute
minted: `residual_of` returns `None` for `MIHAIL PETROV`, `MIHAILOV`,
`JUKOVA`, `MIHAIL IVANOV`, `SOKOLOV PETROV`; it returns the owner for
`MIHAIL`, `JUKOV`, `MIHAIL ZHUKOV`, `MIHAIL JUKOV`.

## 7. What is still open

- C05 is **not** accepted. The repair was written by this reviewer; a review
  that did not write it must re-run the six fixtures and the property.
- The 941-spelling closure hole is closed at the *index*; `fold` remains
  non-closed by construction. Any future consumer that folds a Latin word
  without going through the vault index inherits the old behaviour.
- The widened index is wider than HEAD's: +227 key rows across the whole pool
  (~+1 row per NAME token). `test_perf_masking.py` did not reproduce the
  `database is locked` contention the mint comment warns about, but that test
  is not a burst gate at 4 workers; the stage-boundary regression should keep it
  in view.
