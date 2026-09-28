# E03 NAME subject/object — independent read-only adversarial review (2026-09-28)

Row **E03** of the 19-row hop-format sprint: the **NAME** identity must keep its OWNER and its PARTS
across gender, case, reorder and a partial mention. Candidate is already in the tree:
`prototype/pseudex/morph_names.py` (a new `governing_cases` branch for third-person finite verbs),
`prototype/test_names_morphology.py` (gender-aware `detect_case` in the observer), plus the new
`prototype/test_name_case_regression.py` and `prototype/test_name_subject_form.py`. Pinned defect:
`громова марина` → `Громов Марин` (memory_anaphora-045).

**ACCEPTANCE CLAUSE for E03:** the identity and the parts survive gender, case, order and a partial
mention; working FEMALE names and the original `memory_anaphora-045` case stay as controls.

## Verdict: **REJECT**

The pinned subject case (`посылку примет громова марина`) is fixed, and every accepted suite passes.
But the fix is too blunt: it adds `nomn` to the governed cases of **every** third-person finite verb
without checking whether the subject slot is already occupied, so a MASCULINE name in the accusative
object position after such a verb — `система найдёт иванова петра` (the man *Иванов Пётр*) — is now
canonicalised as a WOMAN (*Иванова Петра*) and minted a FEMININE fake. Smallest counterexample below.

## 1. Recomputations of the accepted suites

Run from `prototype/` with `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python` (Python 3.12.12).

| command | result | exit |
|---|---|---|
| `.venv/bin/python test_names_morphology.py` | 16 PASS — gender/case/inflection/feminine/round-trip/well-formed/rewrite/one-row/Б21 | **0** |
| `.venv/bin/python test_name_subject_form.py` | 18/18 checks passed | **0** |
| `.venv/bin/python test_name_case_regression.py` | all PASS (observer + product path + mintable) | **0** |

All three suites pass. None of them covers a MASCULINE accusative after a third-person finite verb, so
the regression below is invisible to the whole accepted set.

`git rev-parse HEAD` = `9c5acbb13e02ae3b230a31411bef2877ecc23ef3`. Candidate hashes (recomputed):
`morph_names.py` `e173eae4…`, `test_names_morphology.py` `59b42e7c…`,
`test_name_case_regression.py` `523cf24b…`, `test_name_subject_form.py` `c0a7762f…`. The three test
files are untracked (new); `morph_names.py` is modified (+10/-0).

## 2. Independent probe

Probes in `/tmp/probe_e03.py`, `/tmp/probe_regress.py`, `/tmp/probe_final.py`, `/tmp/probe_ab.py`,
`/tmp/probe_ab2.py` — mirroring the tests' own helpers (`testkit.load_dev_bundle()`, `Detector`,
`Vault(...).for_conversation(...)`, `mask_text` / `unmask_text` / `unmask_arguments`,
`patch("pseudex.vault._fake_name", …)`). Everything runs through the real `Vault` + `mask_text` /
`unmask_arguments` path, never a re-import of a suite's constants.

**Pinned case (clean, no forcing):**

```
mask('посылку примет громова марина')          -> 'посылку примет фомина альбина'
stored canonical / token                        -> ('громова марина', 'Фомина Альбина')
unmask_arguments('{"name": "Фомина Альбина"}')  -> 'Громова Марина'
control mask('посылку примет иванова марина')   -> 'посылку примет котова анастасия'
```

The canonical is now the feminine nominative `громова марина` (was `громов марин`), the fake is
feminine, and the restore returns `Громова Марина` even when the model writes the fake back in an
oblique case (`Мухину Степану` → `Громову Марину`; `Мухин Степан` → `Громова Марина`). The real
person's gender drives the restoration, not the fake's — the pinned class is fixed.

**Controls (all pass):**

- FEMALE surname + given name whose gender disagrees with the surname's masculine-genitive prior:
  `detect_gender('иванова марина') == 'femn'`, `detect_gender('громова марина') == 'femn'` — not
  flipped masculine.
- Oblique full name restores the nominative owner + parts:
  `to_nominative('Иванову Петру Сергеевичу') == 'Иванов Пётр Сергеевич'`,
  `to_nominative('Ивановой Марии Петровне') == 'Иванова Мария Петровна'`. The governed accusative
  object stays feminine: `to_nominative_governed('громову марину', ('nomn','accs')) == 'громова марина'`.
- Reorder → ONE owner: masking `Иванов Пётр Сергеевич` / `Пётр Иванов Сергеевич` /
  `Пётр Сергеевич Иванов` leaves a single `tokens` row (`('Иванов Пётр Сергеевич', 'Мухин Глеб
  Александрович')`) via `_same_person_reordered`; the surface mirrors the mention's own word order.
- Partial mention: surname-only `Иванов` → the stored person's surname part (`Панов` of `Панов Филипп
  Степанович`); given-only `Пётр` → its part; an ambiguous `Иванов`/`Пётр` with two owners on file stays
  unresolved (fresh row) as required.

**The regression (clean A/B, no forcing):**

```
sentence = 'система найдёт иванова петра'   (a man: Иванов Пётр, accusative object of a 3per verb)
OLD governing_cases -> ('accs',)       : mask -> 'система найдёт ершова алексея'   stored 'иванов пётр'   gender masc
NEW governing_cases -> ('nomn','accs') : mask -> 'система найдёт боброва злата'    stored 'иванова петра'  gender femn
```

`read_person('иванова петра', ('accs',))      == ('masc', 'accs')`   (pre-candidate)
`read_person('иванова петра', ('nomn','accs')) == ('femn', 'nomn')`  (candidate)

The man *Иванов Пётр* in the accusative is now stored under the feminine canonical `иванова петра`,
minted a feminine fake (`Боброва Злата`), and no longer collapses to the same row as the nominative
`Иванов Пётр` — one person becomes two, and a real man reaches the model as a woman.

## 3. Smallest reproducible counterexample

1. `Vault(":memory:", …).for_conversation(...)`, `Detector()`, `testkit.load_dev_bundle()`.
2. `mask_text('система найдёт иванова петра', vault, detector.detect(...))` → the masked sentence
   carries a **feminine** fake (e.g. `боброва злата`).
3. The stored NAME row is `canonical='иванова петра'` (a woman), not `'иванов пётр'` (the man).
4. `unmask_arguments` of that fake returns `Иванова Петра` — a different person/gender from the man
   who was written.

Pre-candidate the same sentence stored `'иванов пётр'` and minted a masculine fake
(`ершова алексея` = the accusative of a man's name). `Пётр` is among the most common Russian male
names, and `найдёт`/`проверит`/`пригласит`/`запишет` are ordinary verbs, so this is not a corner case.

## 4. Root cause (code location)

- `prototype/pseudex/morph_names.py:640-644` — the new branch returns `("nomn", "accs")` /
  `("nomn", "datv")` for **any** word whose known parses include a 3rd-person finite verb. It does not
  check whether an explicit subject already precedes the verb (`система найдёт …`), and it unconditionally
  admits the nominative, so a masculine accusative object is allowed to be re-read as a feminine
  nominative.
- `prototype/pseudex/morph_names.py:739-743` (`read_person` `best=`) — with both `(masc, accs)` and
  `(femn, nomn)` in the candidate set, the score sum wins first, and for a syncretic `-ова/-ина`
  surname + a given name that also exists as a feminine name (`петра`), the feminine-nominative sum
  (`0.222+0.048`) out-scores the masculine accusative (`0.074+0.095`). The oblique-preference tiebreak
  is only the *third* key, so it never runs.

The verb stem alone cannot license `nomn` once the subject slot is already filled; the fix needs to
restrict the `nomn` admission to subject position (no preceding subject noun, e.g. `посылку примет …`)
or to a spelling that genuinely cannot be an oblique object — otherwise the correct masculine-accusative
reading is silently flipped to feminine. **Not fixed here** (REJECT — read-only review).

## 5. Terminal verdict

**REJECT.** The pinned `громова марина` subject class is fixed and all controls (feminine gender,
oblique restore, reorder, partial mention) hold, but the change regresses a common MASCULINE accusative
after a third-person finite verb: `система найдёт иванова петра` now canonicalises the man *Иванов
Пётр* as the woman *Иванова Петра* and mints a feminine fake — the gender/case survival the clause
requires, broken for a name the code used to read correctly.

No source, test, wiki, corpus or saved run was modified; only this report was written. No network, no
provider, no child sessions.
