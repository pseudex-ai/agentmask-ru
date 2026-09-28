# Adversarial review: subject-vs-object guard in `morph_names.governing_cases`

Scope: working-tree change to `prototype/pseudex/morph_names.py` (new guard, current
lines 635–644), `prototype/test_name_subject_form.py`, and
`research/hop-format-audit/evidence/cases/memory_anaphora-045.md`. Verdict: **the fix is
real and reproduces the case-045 defect; it also introduces four end-to-end regressions
on 3rd-person transitive objects.** All numbers below come from the real dev bundle, the
real `Detector`, `mask_text`/`unmask_arguments`, run with
`/private/tmp/agentpii5-connectors-venv/bin/python`, `PYTHONDONTWRITEBYTECODE=1`, cwd
`prototype/`; baseline = `/private/tmp/hop-sprint-baseline.86Dxvl/prototype`, separate
process, same Python, bundle and inputs. An earlier stub-asset run of this review was
invalid and its conclusions are withdrawn.

## What the change does

Before the existing stem checks it returns `()` (no case evidence) whenever the word in
front of the name starts with any `_ACCUSATIVE_VERBS + _DATIVE_VERBS` stem **and** any
known parse is `POS=VERB, person=3per`:
```python
if word.startswith(_ACCUSATIVE_VERBS + _DATIVE_VERBS) and any(
    parse.is_known and parse.tag.POS == "VERB" and parse.tag.person == "3per"
    for parse in _MORPH.parse(word)
):
    return ()
```

## Confirmed — the fix works, and case 045 is a real reproducer

`read_person` with the real bundle, before and after (identical in both variants — the
morphology is not what changed; the **governor** is):
`('громова марина', ('accs',)) -> ('masc','accs') canonical 'громов марин'`;
`('громова марина', ()) -> ('femn','nomn') 'громова марина'`.
Baseline end-to-end for `"посылку примет громова марина"`: detector span `('громова
марина', ('accs',))`, `read_person = ('masc','accs')`, `unmask_arguments` restored
`'Громов Марин'` — exactly the wrong canonical recorded in case 045. Current: span
`(..., ())`, `('femn','nomn')`, restored `'Громова Марина'` (the golden). The defect is
confirmed, not a conjecture; the guard is what fixes it.

## Confirmed regression — four 3rd-person transitive objects break end-to-end

| input | baseline gov / read / restored | current gov / read / restored |
|---|---|---|
| `курьер передаст громову марину` | `('datv')` / `('femn','datv')` / **`Громова Марина`** | `()` / `('masc','datv')` / **`Громов Марин`** |
| `оператор пригласит громову марину` | `('accs')` / `('femn','accs')` / **`Громова Марина`** | `()` / `('masc','datv')` / **`Громов Марин`** |
| `система найдёт громову марину` | `('accs')` / `('femn','accs')` / **`Громова Марина`** | `()` / `('masc','datv')` / **`Громов Марин`** |
| `курьер примет громову марину` | `('accs')` / `('femn','accs')` / **`Громова Марина`** | `()` / `('masc','datv')` / **`Громов Марин`** |

Independent expectation: in all four the name is the direct/indirect object (a woman,
`Громова Марина`); baseline is right and current is wrong. The trigger is *the object
surface itself*: `'громову марину'` with `()` reads `('masc','datv')`, and the guard now
produces `()` for every 3rd-person finite form. Intra-paradigm inconsistency in the same
variant: `оператор пригласит` (accs→`()`), but `примите`/`пригласите` (imperative,
`('accs')`) stay `('femn','accs')`, and `менеджер позвонит громовой марине` still
restores correctly only because its object surface is unambiguous (`('femn','datv')` even
with `()`). Male/female axis: the current variant converts a woman into a man in these
four; no case where it converts a man into a woman was found. `передайте марину посылку`
is wrong in **both** variants (`('masc','datv')`, restored `'Марин'`) — pre-existing, not
caused by this diff, but worth an acceptance case.

## Test blind spot

`test_name_subject_form.py` exercises female subjects already in the nominative
(`громова марина`) and imperatives (`прими/примите/позвоните`); it contains no 3rd-person
verb followed by an accusative/dative **object**, so none of the four regressions above
can fail it. Its `()` assertions for `примет`/`проверит` are assertions about the
intended suppression, and the suppression is correct only where the name is a subject.

## Tests

- Real-bundle morphology probe (`read_person`/`to_nominative_governed` on `громова
  марина`, `громову марину`, `громовой марине` with and without governor) and a
  nine-sentence end-to-end probe (detector spans → `mask_text` → `unmask_arguments`,
  `_fake_name` patched to the test's fakes) were run on **both** the baseline archive and
  the current worktree in separate processes; the tables above are their output.
- `test_name_subject_form.py` itself was not executed; with the connector venv that would
  be `PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python
  test_name_subject_form.py` from `prototype/`. The probes replicate its detector +
  mask/unmask path on the same fakes.

## Limits

- Probes covered nine sentences and three surfaces; no corpus sweep, so the regression
  rate is unknown — the four are existence proofs, not a frequency estimate.
- Only `_fake_name` was patched; vault, detector, bundle and pipeline are the real ones.
- `read_person` was probed directly as well as through the detector; no other caller
  (`redact.py:316`, `vault.py:2678`) was exercised separately.
- No claim that fixing the subject case *requires* the object regression — that is a
  property of this guard's shape (stem match + 3per), not of the goal.

## Suggested acceptance probes (for Codex)

1. `("курьер передаст громову марину"` → restored `Громова Марина`) — baseline
   passes, current fails.
2. `("оператор пригласит громову марину", ...)` and `("система найдёт громову марину",
   ...)` — same.
3. Keep case 045 `("посылку примет громова марина" → `Громова Марина`)` as the
   must-not-regress subject case a replacement rule has to preserve.
