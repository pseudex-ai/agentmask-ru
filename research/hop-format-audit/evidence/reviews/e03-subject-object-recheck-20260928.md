# E03 NAME subject/object — repair re-check (2026-09-28)

Independent read-only re-check of the REPAIR to E03 (prior verdict: REJECT). The repair added
`_nominative_subject_before` to `prototype/pseudex/morph_names.py` and extended
`prototype/test_name_subject_form.py`. The repair's claimed rule: a post-verbal name is admitted the
nominative only when NO UNAMBIGUOUS nominative noun/pronoun already fills the subject slot before the
verb, where "unambiguous" = the pre-verbal noun's nominative is not syncretic with its accusative.

## Verdict: **REJECT**

The original counterexample (`система найдёт иванова петра`) IS fixed, and the pinned
`громова марина` subject class holds. But the "unambiguous nominative" heuristic is still too blunt in
the OTHER direction: a noun that pymorphy3 also reads as an **inanimate** homograph (whose accusative
equals its nominative) is discarded as a subject even when its **animate** reading is what the sentence
uses. `оператор` and `менеджер` are such nouns, so a masculine accusative object after them is still
re-read as a feminine nominative — the exact E03 class the repair was meant to close.

## 1. Accepted suites (run from `prototype/`, `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python`)

| command | result | exit |
|---|---|---|
| `.venv/bin/python test_name_subject_form.py` | `name_subject_form: 21/21 checks passed` | **0** |
| `.venv/bin/python test_name_case_regression.py` | `name case regression OK — …` | **0** |
| `.venv/bin/python test_names_morphology.py` | `names OK — gender and case agree …` | **0** |

All three pass. `test_name_subject_form.py` covers the MASCULINE accusative only for the subject
`система` (line 30) and covers `оператор` only with a FEMININE name (`громову марину`, line 23); the
masculine + `оператор`/`менеджер` combination is untested, which is why the regression is invisible.

`git rev-parse HEAD` = `9c5acbb13e02ae3b230a31411bef2877ecc23ef3`.
`sha256` prefixes: `morph_names.py` `764640fa…`, `test_name_subject_form.py` `8bc6a07d…`,
`test_name_case_regression.py` `523cf24b…`, `test_names_morphology.py` `59b42e7c…`.

## 2. Reproduction through the real `Detector` + `Vault` + `mask_text`

Mirrors the suites' helpers exactly (`testkit.load_dev_bundle()`, `Detector()`,
`Vault(":memory:", …).for_conversation(...)`, `mask_text`, `patch("pseudex.vault._fake_name", …)`).
Stored rows read from the vault's `tokens` table (`canonical`, `token`, `original`), and the gender
handed to `_fake_name` recorded via a side-effect patch.

```
система найдёт иванова петра     spans cases=('accs',)  canonical='иванов пётр'    gender masc   (FIXED)
заказ проверит громова марина    spans cases=('nomn','accs') canonical='громова марина' gender femn  (OK)
посылку примет громова марина    spans cases=('nomn','accs') canonical='громова марина' gender femn  (OK)
он проверит иванова петра        spans cases=('accs',)  canonical='иванов пётр'    gender masc   (OK)
оператор пригласит иванова петра spans cases=('nomn','accs') canonical='иванова петра'  gender femn  (REGRESSION)
курьер примет иванова петра      spans cases=('accs',)  canonical='иванов пётр'    gender masc   (OK)
система найдёт громову марину    canonical='громова марина' gender femn  (OK)
оператор пригласит громову марину canonical='громова марина' gender femn  (OK)
курьер примет громову марину     canonical='громова марина' gender femn  (OK)
```

`governing_cases`:

```
'система найдёт '    -> ('accs',)
'заказ проверит '    -> ('nomn', 'accs')
'он проверит '       -> ('accs',)
'посылку примет '    -> ('nomn', 'accs')
'оператор пригласит ' -> ('nomn', 'accs')   # WRONG: should be ('accs',)
'курьер примет '     -> ('accs',)
```

Full round-trip (`mask_text` → `unmask_arguments('{"name": …}')`) for the counterexample:

```
оператор пригласит иванова петра -> restored 'Иванова Петра'   (WRONG: the man Иванов Пётр)
курьер примет иванова петра      -> restored 'Иванов Пётр'     (correct)
менеджер пригласит иванова петра -> canonical 'иванова петра'  (WRONG, same class)
диспетчер пригласит иванова петра -> canonical 'иванов пётр'   (correct)
администратор пригласит иванова петра -> canonical 'иванов пётр' (correct)
```

## 3. Smallest reproducible counterexample

1. `Vault(":memory:", …).for_conversation(...)`, `Detector()`, `testkit.load_dev_bundle()`.
2. `mask_text('оператор пригласит иванова петра', vault, detector.detect(...))`.
3. The stored NAME row is `canonical='иванова петра'` (a woman) and the fake minted is feminine —
   not `'иванов пётр'` (the man).
4. `unmask_arguments` of the fake returns `Иванова Петра`.

`оператор`/`менеджер` are ordinary dispatcher/CRM subjects (precisely the domain this module targets),
and `пригласит`/`примет` are in the module's own `_ACCUSATIVE_VERBS` list, so this is not a corner case.

## 4. Root cause (code location)

`prototype/pseudex/morph_names.py:626-632` (`_nominative_subject_before`) collects the CASE of every
known parse of a pre-verbal noun and requires `"nomn" in cases and "accs" not in cases`. pymorphy3
parses `оператор` and `менеджер` three ways: an ANIMATE nominative (the subject of «пригласит») plus
an INANIMATE homograph whose accusative equals its nominative, so `cases == {'nomn', 'accs'}` and the
function returns False. The inanimate reading (a mathematical/software "operator", a file "manager")
cannot be the subject of `пригласит`, but the heuristic does not distinguish lexeme/animacy — it sees
the syncretic accusative in ANY parse and discards a genuine animate subject. Consequently
`governing_cases('оператор пригласит ')` returns `('nomn','accs')` instead of `('accs',)`, and
`read_person('иванова петра', ('nomn','accs'))` falls on `('femn','nomn')`, corrupting the man into
the woman `иванова петра` (the very E03 failure, now for `оператор`/`менеджер` instead of `система`).

## 5. Terminal verdict

**REJECT.** The repair closes `система найдёт иванова петра` and keeps the `громова марина` subject
class fixed, but the "unambiguous nominative" test treats any noun with an inanimate homograph
(`оператор`, `менеджер`) as non-subject, so `оператор пригласит иванова петра` still canonicalises the
man *Иванов Пётр* as the woman *Иванова Петра* and mints a feminine fake — the gender/case survival the
clause requires, broken for a common masculine-accusative object.

No source, test, wiki, corpus or saved run was modified; only this report was written. No network, no
provider, no child sessions.
