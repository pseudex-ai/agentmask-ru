# E03 NAME subject/object — third-repair re-check (2026-09-28)

Independent read-only re-check of the THIRD repair to E03. Prior verdicts: REJECT #1
(`система найдёт иванова петра` read the man as a woman), REJECT #2 (`оператор пригласит
иванова петра` — pymorphy's inanimate homograph), REJECT #3-of-repair-2 (inanimate-syncretic
subjects `сервис`/`приложение`/`скрипт`/`фильтр`/`алгоритм` could not be recognised as subjects).
This third repair abandons the pre-verbal subject detection entirely: `governing_cases(text, start,
surface)` now takes the NAME surface and, for a 3rd-person finite verb, decides object-vs-subject from
the NAME's own gender via `_oblique_object_case(surface, governed) = detect_gender(surface) != "femn"`.

## Verdict: **ACCEPTED_FIX**

Every required reproduction holds, the two rejections that killed repairs #1/#2 are fixed, the
previously-untested inanimate-syncretic-subject direction (`сервис найдёт иванова петра` etc.) now
canonicalises correctly, and adversarial probing in BOTH directions (masculine objects, feminine
subjects, feminine declined objects, and masculine nominative subjects in OVS word order) found no
grammatical in-domain sentence that still mis-canonicalises. The one non-result is a lone-surname
detection gap, not a canonicalisation defect, and is outside E03's scope.

## 1. What was reviewed

- `prototype/pseudex/morph_names.py` — `governing_cases` (line 616, now takes `surface: str = ""`),
  the new `_oblique_object_case` (line 665), `detect_gender` (line 336), `read_person` (line 696).
- `prototype/pseudex/detect_all.py:277` — the caller now passes `morph_names.governing_cases(text,
  s.start, s.value)`.
- `prototype/test_name_subject_form.py` — expanded from 25 to 28 checks: the inanimate-syncretic
  subjects `сервис найдёт иванова петра` and `приложение найдёт иванова петра` are now pinned as
  masculine-accusative rows (lines 39-40, 67-68), closing the blind spot recheck2 named.

The diff against HEAD (`git rev-parse HEAD` = `9c5acbb13e02ae3b230a31411bef2877ecc23ef3`) removes the
`_nominative_subject_before` heuristic of repairs #1/#2 entirely (confirmed absent by grep) and inserts,
after the `_GOVERNOR_CASES` lookup:

```python
if word.startswith(_ACCUSATIVE_VERBS + _DATIVE_VERBS) and any(
    parse.is_known and parse.tag.POS == "VERB" and parse.tag.person == "3per"
    for parse in _MORPH.parse(word)
):
    governed = "accs" if word.startswith(_ACCUSATIVE_VERBS) else "datv"
    if surface and _oblique_object_case(surface, governed):
        return (governed,)
    return ("nomn", governed)
```

`_oblique_object_case` is `detect_gender(surface) != "femn"`.

`sha256` prefixes (working tree): `morph_names.py` `96abc06df5…`, `test_name_subject_form.py`
`b5481ecd1b…`, `test_name_case_regression.py` `523cf24b54…`, `test_names_morphology.py` `59b42e7c36…`,
`detect_all.py` `ddc2d29150…`.

## 2. Accepted suites (run from `prototype/`, `PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python`)

| command | result | exit |
|---|---|---|
| `python test_name_subject_form.py` | `name_subject_form: 28/28 checks passed` | **0** |
| `python test_name_case_regression.py` | all PASS, `name case regression OK — …` | **0** |
| `python test_names_morphology.py` | `names OK — gender and case agree, …` | **0** |
| `python test_product.py` | `… names OK — one reading of the phrase, the sentence breaks the tie … tool schemas OK` | **0** |

## 3. Reproduction through the real `Detector` + `Vault` + `mask_text`

Probe `/tmp/probe_e03_recheck3.py` mirrors the suites' helpers (`testkit.load_dev_bundle()`,
`Detector()`, `Vault(":memory:", …).for_conversation(...)`, `mask_text`, `patch("pseudex.vault._fake_name",
…)`). The stored NAME row is read from the vault `tokens` table (`canonical`, `token`, `original`);
`unmask_arguments` of the minted token gives the restored person. Canonical is stored lower-case; restore
round-trips to title case. `gov=` is the `NameSpan.cases` the detector handed the vault.

Required cases — **all correct**:

```
система найдёт иванова петра        gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
оператор найдёт иванова петра       gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
менеджер найдёт иванова петра       gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
сервис найдёт иванова петра         gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'   (was REJECT in recheck2)
приложение найдёт иванова петра     gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'   (was REJECT in recheck2)
скрипт найдёт иванова петра         gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
фильтр найдёт иванова петра         gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
алгоритм найдёт иванова петра       gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
он проверит иванова петра           gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
курьер примет иванова петра         gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
оператор пригласит иванова петра    gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
менеджер пригласит иванова петра    gov=('accs',)        canonical='иванов пётр'     restored='Иванов Пётр'
заказ проверит громова марина       gov=('nomn','accs')  canonical='громова марина'  restored='Громова Марина'
посылку примет громова марина       gov=('nomn','accs')  canonical='громова марина'  restored='Громова Марина'
оператор пригласит громову марину   gov=('accs',)        canonical='громова марина'  restored='Громова Марина'
система найдёт громову марину       gov=('accs',)        canonical='громова марина'  restored='Громова Марина'
менеджер позвонит громовой марине   gov=('nomn','datv')  canonical='громова марина'  restored='Громова Марина'
приедет иванов пётр                 gov=()               canonical='иванов пётр'     restored='Иванов Пётр'   (preserved)
```

Pinned `громова марина` subject class (all correct):

```
прими громову марину           -> 'Громова Марина' (femn)
примите громову марину         -> 'Громова Марина' (femn)
позвоните громовой марине      -> 'Громова Марина' (femn)
передайте марину посылку       -> 'Марин' (masc)   # the suite's own pinned expectation
```

`memory_anaphora-045` verbatim (the original defect):

```
посылку примет громова марина адрес казань улица нижняя 10 квартира 151
    -> span='громова марина'  canonical='громова марина'  restored='Громова Марина'  (femn)
```

## 4. Adversarial probing, both directions

47/47 end-to-end cases pass in `/tmp/probe_e03_recheck3.py`; a second probe
(`/tmp/probe_e03_fragility.py`) covers 18/18 full-name cases (varied surnames + given names +
patronymics + a-stem masculine names); the one non-result there is a lone-surname detection skip, not a
canonicalisation defect (see §5).

**Direction A — masculine object after more nouns** (the direction repairs #1/#2 got wrong):

```
врач найдёт иванова петра        -> 'иванов пётр' (masc)   OK
водитель пригласит иванова петра -> 'иванов пётр' (masc)   OK
секретарь проверит иванова петра -> 'иванов пётр' (masc)   OK
робот найдёт иванова петра       -> 'иванов пётр' (masc)   OK
сайт найдёт иванова петра        -> 'иванов пётр' (masc)   OK  (inanimate-syncretic, was REJECT)
код проверит иванова петра       -> 'иванов пётр' (masc)   OK  (inanimate-syncretic, was REJECT)
запрос найдёт иванова петра      -> 'иванов пётр' (masc)   OK  (inanimate-syncretic, was REJECT)
письмо проверит иванова петра    -> 'иванов пётр' (masc)   — sentence is grammatically impossible
                                                             (a letter cannot check a person); no
                                                             canonical is "correct", not a counterexample
система найдёт петрова николая   -> 'петров николай' (masc) OK
система найдёт кузнецова илью    -> 'кузнецов илья' (masc)  OK
система найдёт сидорова кузьму   -> 'сидоров кузьма' (masc) OK
система найдёт иванова никиту    -> 'иванов никита' (masc)  OK
```

**Direction B — feminine nominative subject after more nouns:**

```
сайт проверит громова марина     -> 'громова марина' (femn) OK
код проверит громова марина      -> 'громова марина' (femn) OK
запрос найдёт громова марина     -> 'громова марина' (femn) OK
врач проверит громова марина     -> 'громова марина' (femn) OK
робот найдёт громова марина      -> 'громова марина' (femn) OK
заказ проверит громова           -> 'громова' (femn)        OK (lone surname subject)
заказ проверит смирнова          -> 'смирнова' (femn)       OK (lone surname subject)
```

**Direction C — masculine NOMINATIVE subject after a transitive verb (OVS / VS order), the direction
repair #3's asymmetry risks:**

```
заказ проверит иванов пётр        -> 'иванов пётр'   (masc, nomn) OK — preserved, not forced into accs
систему найдёт иванов пётр        -> 'иванов пётр'   (masc, nomn) OK
посылку примет иванов пётр        -> 'иванов пётр'   (masc, nomn) OK
заказ проверит иванов николай     -> 'иванов николай' (masc)      OK
заказ проверит иванов никита      -> 'иванов никита'  (masc, a-stem) OK
посылку примет иванов илья        -> 'иванов илья'    (masc, a-stem) OK
заказ проверит петров никита      -> 'петров никита'  (masc)      OK
заказ проверит кузнецов кузьма    -> 'кузнецов кузьма' (masc)     OK
```

Why direction C survives: a masculine nominative surface has no masculine accusative reading (the
accusative differs — `иванов пётр` → `иванова петра`), so `read_person(surface, ('accs',))` finds no
accusative candidate, leaves `(masc, nomn)` standing, and `to_nominative_governed` returns the surface
unchanged. `_oblique_object_case` forcing `(governed,)` is therefore harmless for nominative subjects.

**Direction D — feminine declined objects, varied surnames (surname-accusative is syncretic with the
masculine dative, the hardest feminine reading):**

```
система найдёт смирнову анну      -> 'смирнова анна' (femn, accs) OK
система найдёт иванову ольгу      -> 'иванова ольга' (femn, accs) OK
система найдёт кузнецову веру     -> 'кузнецова вера' (femn, accs) OK
оператор пригласит петрову марию  -> 'петрова мария' (femn, accs) OK
курьер примет сидорову елену      -> 'сидорова елена' (femn, accs) OK
врач примет громову марину        -> 'громова марина' (femn)      OK
секретарь пригласит громову марину-> 'громова марина' (femn)      OK
сайт найдёт громову марину        -> 'громова марина' (femn)      OK
код проверит громову марину       -> 'громова марина' (femn)      OK
менеджер позвонит смирновой анне  -> 'смирнова анна' (femn, datv) OK
менеджер позвонит кузнецовой вере -> 'кузнецова вера' (femn, datv) OK
система найдёт громову марину борисовну -> 'громова марина борисовна' (femn) OK (patronymic)
менеджер позвонит громовой марине борисовне -> 'громова марина борисовна' (femn) OK (patronymic)
```

Mechanism note (verified, not conjectured): for a declined feminine name such as `громову марину`,
`detect_gender` returns **None** (the `-у` ending defeats both the 1.5× vote margin and the `-а/-я`
last-resort heuristic), so `_oblique_object_case` returns True and `governing_cases` emits the bare
`('accs',)`. That is exactly right: the bare accusative governor excludes the spurious
masculine-dative reading of `громову марину` (dative of `Громов Марин`), and `read_person` then reads
the only accusative candidate `(femn, accs)`. The docstring's claim — "when it is declined, `read_person`
reads the oblique case out of it whether or not the nominative is also admitted" — holds, through the
`None` path rather than the `femn` path.

## 5. The one non-result (out of scope, not a counterexample)

`посылку примет иванова` (a lone surname) returns **0 NAME spans** — the detector does not flag the bare
`иванова` at all, so there is nothing for the vault to canonicalise. This is a detection-coverage matter
(the lone `-ова` surname is structurally ambiguous: feminine nominative vs masculine genitive), not a
canonicalisation matter, and it is unchanged by this repair, which only alters how a DETECTED name's
cases are computed. The comparable lone-subject cases `заказ проверит громова` / `… смирнова` are
detected and canonicalise correctly. E03 is about full-name subject/object, so this is outside the fix's
contract.

## 6. Why the third repair succeeds where #1/#2 failed

Repairs #1/#2 asked "is the pre-verbal noun a subject?" and had to enumerate subject-noun classes —
animate-homograph (`оператор`), then inanimate-syncretic (`сервис`) — and each enumeration was provably
incomplete. The third repair never asks that question. It uses only the NAME's own gender (`detect_gender`
— the same given-name-outvotes-surname weighting `read_person` already lives by, so the two cannot
disagree): a name whose gender reads masculine/undetermined after a transitive 3rd-person verb is the
object and is read in the governed case; a feminine name is read in whatever case its surface actually
carries (`nomn`, `accs`, `datv`), because the feminine nominative (`громова марина`) and the declined
forms (`громову марину`, `громовой марине`) are all unambiguous once the governor is not allowed to
admit the spurious masculine reading. The masculine-nominative-subject direction stays safe because a
nominative masculine name has no accusative reading to be forced into.

No source, test, wiki, corpus or saved run was modified; only this report was written. Probes live under
`/tmp` (outside the repo). No network, no provider, no child sessions.
