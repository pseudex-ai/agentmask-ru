# NAME case regression: the written form is accusative; the observer is gender-blind

Scope: the single FAIL in
`/private/tmp/hop-sprint-current-test_names_morphology.py.log` (line 9),

    FAIL  a substitute never stands in the nominative inside an oblique slot
    disagreements=[('Записать Никиту Гущина на 15:00',
                    'Записать Гордея Жукова на 15:00', 'accs', 'nomn')]

Read-only diagnosis of the engine. No child agents, no external model calls, no
engine or existing-test edits. Every number below comes from the real dev bundle
(`testkit.load_dev_bundle()`, no stubs), the real `Detector`, the real
`Vault`, run with
`PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python`
from this worktree's `prototype/`; pristine HEAD is
`/private/tmp/hop-sprint-baseline.86Dxvl/prototype`, same interpreter, same
bundle, separate process.

## Verdict

**The written form is correct animate-accusative Russian. The morphology
observer the check uses is mistaken.**

`Записать Гордея Жукова на 15:00` is exactly what the engine's own inflector
produces for an accusative slot from the minted nominative substitute
`Гордей Жуков`:

    inflect_person("Гордей Жуков", "accs", "masc") == "Гордея Жукова"

The verdict `nomn` is produced one layer up, by the check's own observer:
`test_masked_text_is_well_formed` re-reads the masked span with the
**gender-blind** `morph_names.detect_case(value)`
(`test_names_morphology.py:237`), while the mask leg wrote that span through the
**gender-and-case-aware** `read_person(span.value, span.cases)`
(`pseudex/redact.py:316`). The two readers disagree, and the mask leg is right.

Not a regression: pristine HEAD emits byte-identical masked and restored
strings, and the same verdicts on every probe below. The working-tree hunks in
`morph_names.py` are in `governing_cases`, not in `detect_case` or
`read_person`; the reported behaviour is older than the sprint.

## Evidence

All literals asserted by `prototype/test_name_case_regression.py` (85 checks,
exit 0).

| observation | result |
|---|---|
| masked sentence | `Записать Гордея Жукова на 15:00` |
| restored sentence | `Записать Никиту Гущина на 15:00` (bit-exact) |
| masked NAME span | `('Гордея Жукова', ('accs',))` |
| `detect_case("Гордея Жукова")` — the check's observer | `nomn` |
| `detect_case("Гордея Жукова", "masc")` | `gent` |
| `read_person("Гордея Жукова", ("accs",))` — the mask leg's reader | `('masc', 'accs')` |
| `survives_round_trip("Гордей Жуков", "masc")` — the mint gate | `True` |
| same probes at pristine HEAD | identical |

## Exact cause

`detect_case` sums pymorphy3 scores over the parts with **no gender constraint**
(`morph_names.py:445`, tally at `:498`); `read_person` intersects the parts'
readings and honours the case the sentence governs (`morph_names.py:668`,
governed filter at `:706`). For this span the parses are:

| part | parse | score |
|---|---|---:|
| `Гордея` | `гордей` Name masc, gent | 0.25 |
| `Гордея` | `гордей` Name masc, accs | 0.25 |
| `Жукова` | `жуков` Surn **femn, nomn** | **0.70** |
| `Жукова` | `жуков` Surn masc, gent | 0.20 |
| `Жукова` | `жуков` Surn masc, accs | 0.10 |

The blind tally is `nomn 0.70` vs `gent 0.45` vs `accs 0.35` → `nomn`. The
masculine given name's accusative is syncretic with its own genitive and carries
no nominative reading, so nothing outvotes the surname's feminine nominative.
Adding the gender the engine already knows removes the feminine readings and the
same spelling reads `gent`.

This is the same homography the sibling file's own docstring names for
`-ой` forms, one paradigm over: `Жукова` is a woman's nominative and a man's
genitive/accusative at once. `Ивана Кузнецова` is read correctly blind only
because that given name's genitive score is high enough to win the sum — the
observer is not broken, it is answering a question the spelling does not answer
without gender.

### How often it fires (exact, not sampled)

Enumerating every masculine substitute that survives the engine's own
`survives_round_trip` gate and inflecting it into the reported accusative slot:
**29 of 2424 pairs (1.20%)** make the blind observer say `nomn`; the joint
reader says `accs` for all 2424. The misread class is a masculine animate
accusative whose given-name spelling is syncretic with the genitive and whose
surname ends in the `-ова` paradigm, e.g. `Вадима Жукова`, `Глеба Жукова`,
`Даниила Жукова`, `Евгения Тарасова`, `Артёма Жукова`, `Льва Наумова`,
`Вячеслава Жукова`, `Гордея Жукова`.

Feminine substitutes do not produce it: 2113 feminine fakes × 3 oblique cases
(6339 pairs) → 0 blind `nomn`. Direct sampling of the reported sentence in fresh
vaults flagged 5/300 and 2/300 draws in two runs (7/600 ≈ 1.2%), matching the
exact rate. Three immediate reruns of `test_names_morphology.py` passed.

So the sibling suite fails on the order of once in a hundred runs, and only ever
in this direction. That is what the log caught.

## Minimal recommendation

Test-side, one line, no engine change:

* In `test_masked_text_is_well_formed`, read the substitute with the same reader
  the mask leg used — `read_person(masked_span.value, masked_span.cases)` — and
  flag `nomn` only when that joint reading says `nomn`. Equivalently and more
  weakly, pass the gender the engine already has:
  `detect_case(masked_span.value, detect_gender(masked_span.value))`; that fixes
  all 29 misread pairs here with no `None` result.

The check stays non-vacuous: a genuine nominative placed in an accusative slot
is still caught (`read_person("Гордей Жуков", ("accs",)) == ("masc", "nomn")`),
which is the defect the suite exists for.

No product, engine, metric or policy change is recommended. The mask leg writes
the only form Russian offers for that person; the round trip is bit-exact; the
vault identity is stable.

## Secondary observation (policy-adjacent, not the reported failure)

The prose restore leg also reads the surface gender-blind
(`redact.py:2042`), guarded by `vault.as_minted` (`vault.py:4251`) and the
«customer's own case wins the tie» rule (`redact.py:2058`, Б21). In the narrow
window where the customer wrote the **nominative** and the agent rewrote the
fake into an oblique form the blind reader calls `nomn`:

    Клиент Никита Гущин          (customer, nominative)
    → Клиент Гордей Жуков        (masked)
    → Клиент Гордея Жукова       (agent, accusative)
    → Клиент Никита Гущин        (restored — nominative, not the agent's case)

Byte-identical at pristine HEAD. Since the surface `Гордея Жукова` is not
`as_minted`, the mirroring rule «the real name takes the case the agent wrote»
would put the accusative here; the blind `nomn` reading plus the written-form
tie-break (both nominative) land on the nominative instead. This is a
consequence of the same reader, in a window where the tie-break policy is what
decides, so it is recorded for the owner and **not** proposed for change in this
task. It does not affect the reported failure and it does not leak or swap a
person.

## Reproduce

```bash
cd prototype
PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python \
    test_name_case_regression.py                       # 85 checks, exit 0
PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python \
    test_names_morphology.py                           # passes; the FAIL is a ~1.2% draw
```

The regression file freezes randomness only where an exact output is asserted
(`patch("pseudex.vault._fake_name", ...)`, the pivot
`test_phone_hop_form.py` already uses) and asserts that every frozen substitute
is a real pool member that passes the engine's own inflection gate.

Artifacts: `prototype/test_name_case_regression.py`,
`research/hop-format-audit/name-case-regression-review.md`. Engine and existing
tests untouched.
