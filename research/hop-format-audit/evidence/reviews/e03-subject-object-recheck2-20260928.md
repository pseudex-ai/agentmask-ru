# E03 NAME subject/object — second-repair re-check (2026-09-28)

Independent read-only re-check of the SECOND repair to E03. Prior verdicts: REJECT (reject #1:
`система найдёт иванова петра` read the man as a woman), REJECT (reject #2: `оператор пригласит
иванова петра` — pymorphy gives `оператор`/`менеджер` an inanimate homograph whose accusative equals
the nominative, so the previous "unambiguous nominative" heuristic discarded them as subjects). This
repair replaces that heuristic with a per-parse rule in `_nominative_subject_before`: a pre-verbal
noun/pronoun fills the subject slot iff it has a KNOWN NOMINATIVE parse whose accusative inflection
DIFFERS from the nominative surface.

## Verdict: **REJECT**

The reject-#2 counterexample (`оператор пригласит иванова петра`) and `менеджер` are both fixed, and
all nine required reproductions hold. But the per-parse "accusative-differs" rule is still too blunt in
the OTHER direction: an **inanimate** noun whose accusative is syncretic with its nominative (neuter
`приложение`, masculine `сервис`/`скрипт`/`фильтр`/`алгоритм`) is discarded as a subject even when the
sentence genuinely uses it as one. `приложение найдёт иванова петра` ("the application finds Ivanov
Petr") and `сервис найдёт иванова петра` ("the service finds Ivanov Petr") are grammatical, reachable
sentences — in the product's own domain the *service* is exactly what finds/masks a person — and both
still canonicalise the man *Иванов Пётр* as the woman *Иванова Петра*. This is the same E03 class, now
for a different subject noun class (inanimate-syncretic instead of animate-homograph).

## 1. Accepted suites (run from `prototype/`, `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python`)

| command | result | exit |
|---|---|---|
| `.venv/bin/python test_name_subject_form.py` | `name_subject_form: 25/25 checks passed` | **0** |
| `.venv/bin/python test_name_case_regression.py` | `… name case regression OK — the substitute is written in the sentence's case …` (all PASS) | **0** |
| `.venv/bin/python test_names_morphology.py` | `names OK — gender and case agree, and a re-inflected token still resolves to the real person` | **0** |

All three pass. `test_name_subject_form.py` pins the masculine accusative only for the subjects
`система`, `оператор`, `менеджер` (lines 30-35) and pins the feminine subject class for `заказ` /
`посылку` / `прими` etc.; an inanimate-syncretic subject with a MASCULINE object is untested, which is
why the regression below is invisible to the whole accepted set.

`git rev-parse HEAD` = `9c5acbb13e02ae3b230a31411bef2877ecc23ef3`.
`sha256` prefixes: `morph_names.py` `d83f557f…`, `test_name_subject_form.py` `bc0e4129…`,
`test_name_case_regression.py` `523cf24b…`, `test_names_morphology.py` `59b42e7c…`.

## 2. Reproduction through the real `Detector` + `Vault` + `mask_text`

Probe in `/tmp/probe_e03_recheck2.py` / `/tmp/probe_e03_final.py`, mirroring the suites' helpers
(`testkit.load_dev_bundle()`, `Detector()`, `Vault(":memory:", …).for_conversation(...)`, `mask_text`,
`patch("pseudex.vault._fake_name", …)`). The stored NAME row is read from the vault `tokens` table
(`canonical`, `token`, `original`); the gender handed to `_fake_name` is recorded via a side-effect
patch; `unmask_arguments` of the minted token gives the restored person. Canonical is stored lower-case;
the restore round-trips to title case.

Required cases — **all correct**:

```
система найдёт иванова петра        cases=('accs',)       canonical='иванов пётр'     gender=masc  restored='Иванов Пётр'   (FIXED)
оператор пригласит иванова петра    cases=('accs',)       canonical='иванов пётр'     gender=masc  restored='Иванов Пётр'   (FIXED — reject #2)
менеджер пригласит иванова петра    cases=('accs',)       canonical='иванов пётр'     gender=masc  restored='Иванов Пётр'   (FIXED — reject #2)
курьер примет иванова петра         cases=('accs',)       canonical='иванов пётр'     gender=masc  restored='Иванов Пётр'
диспетчер пригласит иванова петра   cases=('accs',)       canonical='иванов пётр'     gender=masc  restored='Иванов Пётр'
администратор пригласит иванова петра cases=('accs',)     canonical='иванов пётр'     gender=masc  restored='Иванов Пётр'
он проверит иванова петра           cases=('accs',)       canonical='иванов пётр'     gender=masc  restored='Иванов Пётр'
заказ проверит громова марина       cases=('nomn','accs') canonical='громова марина'  gender=femn  restored='Громова Марина'
посылку примет громова марина       cases=('nomn','accs') canonical='громова марина'  gender=femn  restored='Громова Марина'
```

Pinned `громова марина` subject class and controls (all correct, restore round-trips to the feminine
nominative owner):

```
прими громову марину            -> 'Громова Марина' (femn)
примите громову марину          -> 'Громова Марина' (femn)
позвоните громовой марине       -> 'Громова Марина' (femn)
менеджер позвонит громовой марине -> 'Громова Марина' (femn)
оператор пригласит громову марину -> 'Громова Марина' (femn)
система найдёт громову марину   -> 'Громова Марина' (femn)
курьер примет громову марину    -> 'Громова Марина' (femn)
передайте марину посылку        -> 'Марин' (masc)   # the suite's own pinned expectation
```

`governing_cases` (the reject-#2 rows are now correct):

```
'система найдёт '          -> ('accs',)
'оператор пригласит '      -> ('accs',)   # was ('nomn','accs') under repair #1
'менеджер пригласит '      -> ('accs',)   # was ('nomn','accs') under repair #1
'курьер примет '           -> ('accs',)
'диспетчер пригласит '     -> ('accs',)
'администратор пригласит ' -> ('accs',)
'он проверит '             -> ('accs',)
'заказ проверит '          -> ('nomn','accs')
'посылку примет '          -> ('nomn','accs')
```

## 3. Adversarial probing of the OTHER direction

Morphology (all nominative parses and their accusative inflection) is the load-bearing fact:

```
система   inan  acc='систему'      DIFFERS   -> subject   (correct)
оператор  anim  acc='оператора'    DIFFERS   -> subject   (correct, reject #2 fixed)
          inan  acc='оператор'     syncretic
менеджер  anim  acc='менеджера'    DIFFERS   -> subject   (correct)
          inan  acc='менеджер'     syncretic
врач/водитель/секретарь/робот/бот  anim  acc differs      -> subject  (correct)
письмо    inan  acc='письмо'       syncretic -> NOT subject
приложение inan  acc='приложение'  syncretic -> NOT subject
заказ     inan  acc='заказ'        syncretic -> NOT subject
сервис    inan  acc='сервис'       syncretic -> NOT subject
скрипт    inan  acc='скрипт'       syncretic -> NOT subject
фильтр    inan  acc='фильтр'       syncretic -> NOT subject
алгоритм  inan  acc='алгоритм'     syncretic -> NOT subject
```

End-to-end (`mask_text` → `unmask_arguments`), masculine accusative object in every row:

```
врач найдёт иванова петра        -> 'иванов пётр'  masc  (OK)
водитель пригласит иванова петра -> 'иванов пётр'  masc  (OK)
секретарь проверит иванова петра -> 'иванов пётр'  masc  (OK)
робот найдёт иванова петра       -> 'иванов пётр'  masc  (OK — pymorphy reads робот as animate)

письмо проверит иванова петра      -> 'иванова петра' femn  (grammatically impossible: a letter
                                                             cannot check a person — NOT a counterexample)
приложение найдёт иванова петра    -> 'иванова петра' femn  (GENUINE — the app finds the man)
сервис найдёт иванова петра        -> 'иванова петра' femn  (GENUINE — the service finds the man)
скрипт проверит иванова петра      -> 'иванова петра' femn  (GENUINE — the script checks the man)
фильтр найдёт иванова петра        -> 'иванова петра' femn  (GENUINE — the filter finds the man)
алгоритм найдёт иванова петра      -> 'иванова петра' femn  (GENUINE — the algorithm finds the man)
```

`read_person` is what makes the wrong call once the subject is not recognised:

```
read_person('иванова петра', ('accs',))       == ('masc', 'accs')   (man, correct)
read_person('иванова петра', ('nomn','accs')) == ('femn', 'nomn')   (woman, wrong when the man is the object)
```

## 4. Smallest reproducible counterexample

1. `Vault(":memory:", …).for_conversation(...)`, `Detector()`, `testkit.load_dev_bundle()`.
2. `mask_text('сервис найдёт иванова петра', vault, detector.detect(...))` (equivalently
   `приложение найдёт иванова петра`).
3. The stored NAME row is `canonical='иванова петра'` (a woman), gender handed to `_fake_name` is
   `femn`, and `unmask_arguments` of the minted token returns `Иванова Петра` — not `иванов пётр`
   / `Иванов Пётр` (the man).

`сервис`/`приложение` are inanimate nouns whose accusative equals their nominative, so the new rule's
`accusative.word.lower() != parse.word.lower()` is never true for them and `_nominative_subject_before`
returns False; `governing_cases` then admits `('nomn','accs')` and `read_person`'s score sum picks the
feminine-nominative reading. "The service/app finds Ivanov Petr" is ordinary SaaS/CRM speech — the
product itself is "the service finds and masks a person" — so this is not a corner case. `письмо
проверит …` is excluded: a letter cannot check a person, so its feminine-nominative reading is the only
grammatical one and is not a counterexample.

## 5. Root cause (code location)

- `prototype/pseudex/morph_names.py:631-638` (`_nominative_subject_before`) requires the subject's
  accusative to DIFFER from the nominative surface. Inanimate masculine/neuter nouns (`приложение`,
  `сервис`, `скрипт`, `фильтр`, `алгоритм`, `заказ`, `письмо`, …) have a syncretic accusative, so the
  rule can never recognise them as subjects and `governing_cases` (line 675-677) falls through to
  `('nomn','accs')`.
- `prototype/pseudex/morph_names.py:771-777` (`read_person` `best=`) then picks `('femn','nomn')` for
  `иванова петра` because the feminine-nominative score sum out-ranks the masculine-accusative sum, and
  the oblique-preference tie-break is only the third sort key — it never runs.

The docstring at lines 622-623 acknowledges the gap ("«заказ» … proves nothing and the post-verbal name
may still be the subject") but treats it as benign; it is not benign when the inanimate noun is a
genuine transitive subject ("the service finds the man"). The rule conflates two different facts:
*animacy/syncretism* (does the accusative differ) and *subjecthood* (does a noun actually fill the slot).
For inanimate subjects those facts diverge.

## 6. Terminal verdict

**REJECT.** The second repair closes reject #2 (`оператор`/`менеджер`) and keeps every required
reproduction and the pinned `громова марина` subject class correct. But the per-parse "accusative
differs" test cannot recognise inanimate-syncretic subjects, so `сервис найдёт иванова петра` /
`приложение найдёт иванова петра` still canonicalise the man *Иванов Пётр* as the woman *Иванова
Петра* and mint a feminine fake — the gender/case survival the clause requires, broken for a common
masculine-accusative object after an inanimate software subject.

No source, test, wiki, corpus or saved run was modified; only this report was written. No network, no
provider, no child sessions. Probes were written under `/tmp` (outside the repo).
