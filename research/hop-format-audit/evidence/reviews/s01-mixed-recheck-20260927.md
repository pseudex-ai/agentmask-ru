# S01/E01 independent recheck — repaired candidate (unioned call evidence)

Task: `hop-s01-independent-recheck-20260927` · workspace `/Users/igor/Projects/Obscura-hop-audit`
(verified: `pwd` = that exact root). Requested by the S01/E01 owner as a second, independent,
adversarial review of the **repaired** candidate after
`research/hop-format-audit/evidence/reviews/s01-replayed-call-20260927.md` (REJECT).

Scope and discipline actually observed:

* Read-only. No source or test file was edited, in this repo or any other. Every probe lives in
  `/tmp/hop-s01-recheck/` and imports the engine, it does not modify it.
* No children, no subagents. No network, no live/paid benchmark, no provider call.
* Reviewed artefacts: `prototype/pseudex/envelope.py` (working-tree modification; `git diff`
  = 793 insertions / 8 deletions, 1111 lines total) and `prototype/test_error_echo_privacy.py`
  (untracked, 1591 lines). `git rev-parse --short HEAD` = `9c5acbb`.
* Runtime: `.venv/bin/python` 3.12.12, all commands from `prototype/`.
* **USD ceilings: none were applied.** The owner removed them for the remaining sprint, so this
  report carries **actual measured counts** (detector calls, audit events, vault rows, per-run
  wall clock) rather than a budgeted stop. No probe was cut short for cost.

---

## Verdict

**PASS on the rejected counterexample — REJECT as a complete fix.**

Two separate statements, deliberately not merged:

1. **The exact counterexample the first review rejected is CLOSED.** The per-call all-or-nothing
   provenance gate is gone; `_Provenance.values_for_replayed` reads both forms and unions them, and
   the original mixed `restored-real PHONE + shown NAME` leak no longer reproduces through the
   public `mask_messages` path (`probe1.py`: control `False`, mixed `False`, mixed-reversed-order
   `False`; today's run).
2. **The candidate is REJECTED as submitted, because the same real fragment still reaches the
   provider through the same public path whenever the association reader refuses the result's
   binding** (wrong id, missing id, duplicate id, future declaration, mismatched tool name,
   unparseable arguments, or no declaration at all). The clean result is not a consequence of the
   refusal — it is that *no echo layer runs at all*, and detection alone declines the 80-character
   dictated cut. The new suite **pins this as intended behaviour** at
   `test_error_echo_privacy.py:682-684` and `:1465-1466`, so the suite is green and the property is
   false at the same time. Reproduced below on the dossier's own bytes.

There is **no PII leak** on the matched-association path. I looked for one specifically and did not
find it: every matched shape I built keeps the real value out of the provider body. The Finding 1
defect is not a flaw in the union; it is the union's *reach*. Two smaller matched-path defects do
exist and are reported below as Finding 2, the Codex follow-up and **Finding 3**: the result echo
writes a rendering the model does not read (and, when the replaced span is a prefix cut, leaves a
doubled fragment), and a case-retyped own substitute is re-minted. Neither exposes a real value, and
neither changes the verdict — Finding 3 is confirmed on 12 of 12 fresh fixtures.

---

## Metrics (actual, no ceiling)

| command | result |
|---|---|
| `.venv/bin/python test_error_echo_privacy.py` | **254/254 passed**, exit 0 (matches the candidate's claim) |
| `.venv/bin/python test_loop.py` | exit 0 — model saw only tokens; tool received real values |
| `.venv/bin/python test_product.py` | exit 0 |
| `.venv/bin/python test_argument_form.py` | exit 0 |
| `.venv/bin/python test_prose_fragments.py` | exit 0 |
| `.venv/bin/python test_collisions.py` | exit 0 |
| `.venv/bin/python test_derived_forms.py` | exit 0 |

Per-pass cost, matched association, one store, one context reused (probe J, J1/J2):

* 2 `Detector.detect` calls in the first pass (one for the replayed `arguments` string, one for the
  result body) and **0 on the second, byte-identical pass** — the union's second read is a genuine
  cache hit.
* 1 audit group of 1 event in the first pass, 0 in the second; rows 2 → 3 then 3 → 3.
* The union read itself adds **no** detection, **no** audit event and **no** vault row beyond the
  pass's own call masking. The "no extra audit/vault row" requirement **holds on the matched path**,
  and is **not** met for a case-retyped own substitute (Finding 2 / follow-up (c): the audit event
  and the row are minted by `_mask_tool_calls`, in the same pass, and the union then consumes them).

---

## What was attacked, and what held

Every row is through the public `mask_messages` path with a fresh context per pass unless stated.

| attack | result |
|---|---|
| fresh first request, no prior turn in the transcript | **held** — echo = `REDACTED…`, canary absent (`probeA.py` §1) |
| mixed restored-real leaf + shown leaf, both JSON orders | **held** (`probe1.py`, `probeC.py` C2/C3) |
| two real leaves + two shown leaves in one call | **held** — both real values absent (`probeA.py` §3) |
| two identities with a shared surname fragment (`Битюков Олег` / `Битюков Петр`) | **held** — neither substitute leaks into the other's slot; the bare shared fragment masks to one substitute and no real value appears (`probeA.py` §4) |
| foreign conversation's rendering beside this dialogue's real leaf | **held** — B's value not attributed; A's own leaf still protected (`probeF.py` F4) |
| wrong / missing / duplicate / future call id | **echo layer does not run** → see Finding 1 |
| unparseable / non-object `arguments` | **echo layer does not run** → see Finding 1 |
| tool-result `name` omitted or `null` (the wire spells absence) | **held** — `matched`; `name` that disagrees → see Finding 1 |
| ordinary numbers in an armed result | **held** — byte-for-byte identical (`probeF.py` F7, `probeJ.py`) |
| multiple result content blocks (3, one echoing the cut) | **held** (`probeF.py` F5) |
| two result messages for one call id | **held** (`probeF.py` F6) |
| proxy leg (model's own substitute in `arguments`) | **held** (`probeF.py` F9) |
| sidecar leg (`/unmask_arguments` residual, restored real in `arguments`) | **held**; the residual string is fully restored, no fake leaf survived in this fixture (`probeF.py` F8) |
| echo form vs the rendering the model reads, nested `query.phone` shape | **held** for the matched case — echo = the model-visible token, not the raw replayed string (`probeD.py`, `probeJ.py` J5) |
| own substitute retyped with different case | **not held** — see Finding 2 |

---

## Finding 1 — REJECT: the echo layer's protection is void wherever the reader refuses the binding (P1, real PII reaches the model)

### Exact commands

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python /tmp/hop-s01-recheck/probeJ.py     # minimal counterexample, printed
.venv/bin/python /tmp/hop-s01-recheck/probeH.py     # all seven refusal modes at once
.venv/bin/python /tmp/hop-s01-recheck/probeF.py     # F1/F2/F3 inside the surface battery
```

### Minimal counterexample (probe J, verbatim output)

```
real_phone: 'восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три восемсь'

  matched   status=matched   cut in model-bound body: False
             body tail: '...phone_not_e164: REDACTED8c1b4c"\n  }\n}'
  wrong id  status=missing   cut in model-bound body: True
             body tail: '...phone_not_e164: восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три "\n  }\n}'
```

Same transcript, same store, same bytes in `arguments`; the **only** difference is
`tool_call_id` (`"A"` vs `"B"`). With `"A"` the model reads a token; with `"B"` the model reads the
customer's dictated phone prefix.

### Every refusal mode leaks the identical fragment (probe H)

`cut survived = True` in all of these, each time with the full 80-character dictated fragment in the
tool message the provider receives:

| shape | `tool_result_contexts` status |
|---|---|
| result `name` is any value other than the declaration's name | `invalid` |
| `tool_call_id` not declared | `missing` |
| `tool_call_id` key absent | `missing` |
| same id declared twice | `ambiguous` |
| result appears before its declaration (sliding-window transcript) | `missing` |
| `arguments` is malformed JSON / a JSON array / a JSON string | `invalid` |
| no declaration in the transcript at all | `missing` |

By contrast, the NAME family in the same position does **not** leak (`probeH.py` H5: `битюков оле`
→ the substitute, under both matched and wrong id), because the detector recognises the name cut.
The phone cut is the one that needs the echo layer, and the echo layer is exactly what a refusal
removes.

### Why this is not a false alarm about "generic fragment masking"

The value is not generic: it is `REAL_DICTATED[:80]` — the very canary the suite defines as
`CANARY_FRAGMENT` and asserts absent at `:593-597`, `:661-663`, `:796-798`. The detector declines it
by design (the candidate's own comment at `envelope.py:146-151` says teaching it to accept ten
dictated digits would be the forbidden generic rule). So the **only** mechanism that can protect it
is call provenance, and a refused association removes that mechanism.

### Why it is reachable in production

The dossier's own gateway arm holds exactly the prerequisite. From
`research/hop-format-audit/evidence/cases/long_support-013.md:1461+`, call `seq: 1`:

```json
"written":  {"phone": "+79042711995"},
"restored": {"phone": "восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три восемсь"},
"refusal_path": "phone", "refusal_rule": "phone_not_e164"
```

The replayed `arguments` carry the **restored real dictation** (the app composed them from its own
state — the shape `_model_visible_call`'s own docstring describes), and the tool's refusal body
echoes its 80-character prefix. The candidate's headline test
(`test_a_restored_real_leaf_grants_provenance`) builds precisely this transcript and passes — but
only under a binding the reader accepts. The harness that produced the dossier (`bench/agentpii5/`)
does not itself construct `tool_call_id` bindings; the binding comes from the app/gateway, and the
reader refuses it on any of the seven shapes above. A sliding-window transcript, a retried call, an
id re-serialised by an adapter, or a tool-result `name` that is a display name rather than the
function name all land in the leak column.

Honest counterweight, stated so the severity is not inflated: the standard OpenAI-style flow echoes
`tool_call_id` verbatim and usually repeats the function `name`, so the *common* case matches. I
could not measure the production frequency of the refused shapes inside this budget. What is proved
is the mechanism, not the rate — the same posture the first review took.

### Why the suite is green anyway

The suite asserts the refusal deliberately:

* `test_error_echo_privacy.py:682-684` — `check(stripped == DOSSIER_ERROR_REAL, "without the
  association the same body is untouched (the binding is load-bearing)")`.
* `test_error_echo_privacy.py:1465-1466` — every refusal row, including `"unmatched id"`,
  `"future declaration"`, `"duplicate id"`, `"mismatched tool name"`, `"unparseable arguments"` and
  `"a bare result with no call at all"`, asserts
  `check(masked == DOSSIER_ERROR_REAL and CANARY_FRAGMENT in masked, …)`.

So the candidate does not merely miss this path; it **pins the leak as the expected result**. The
refusal is the right decision for *attribution* — answering with the wrong person's substitute is
worse — but the privacy consequence ("the real fragment stays in the prompt") was accepted
implicitly rather than decided, and it is the defect S01 exists to remove.

### Severity

**P1** by the product's own bar: real personal data reaches the model, silently, with no error, no
5xx and no residual. The fail-closed invariant is satisfied only in the sense that nothing was
passed through unmasked by accident; the intended protection simply did not run.

### Minimal fix direction (not applied — read-only review)

Do not widen the association to guess. Instead make the echo layer independent of the *name* check
and of the refusal status:

* The echo pass needs the call's `arguments`, not the call's name. A unique preceding declaration
  with a matching id whose **name disagrees** should still supply provenance (the name check exists
  to stop a foreign result being attributed; a name disagreement is evidence about the tool, not
  about whether these bytes are this conversation's own writing). That alone converts `invalid` into
  a protected result for the `ticket_find` vs display-name route.
* For `missing`/`ambiguous`/future ids, refuse *attribution to a person* as today, but still run the
  echo pass over the union of the values of **every** preceding declaration in the same conversation
  — the substitute and the real rendering are both this dialogue's own writing, so an unresolved
  fragment is still recognisable as ours. If that is judged too broad, the honest alternative is to
  accept the leak explicitly in `docs/known-issues.md` and in the case manifest, and to keep a
  canary asserting it — not to leave the suite asserting the fragment survives without a name.
* Either way, add a test in the same change that asserts the **absence** of the fragment for the
  refused shapes; the current tests assert its presence.

---

## Finding 2 — RESIDUAL (P2): an own substitute retyped with different case is re-minted, and the candidate now consumes that row as evidence

### Exact command

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python /tmp/hop-s01-recheck/probeB.py     # B1/B3
```

Measured (`probeB.py` B3), on the bare leaf:

```
shown verbatim     'восемь девятьсот тридцать один нол' -> unchanged   rows 3->3 audit=[()]
shown upper        'ВОСЕМЬ ДЕВЯТЬСОТ ТРИДЦАТЬ ОДИН НОЛ' -> unchanged   rows 3->3 audit=[()]
shown title        'Восемь Девятьсот Тридцать Один Нол' -> unchanged   rows 3->3 audit=[()]
shown name upper   'ФОМИН ФЁДОР' -> 'ФРОЛОВ ЯКОВ'                      rows 3->4 audit=[('NAME','Фролов Яков','ФОМИН ФЁДОР')]
```

and the resulting vault row (measured directly):

```
new shown_forms row: ('ШИЛОВ ФИЛИПП', 'ПАНОВ ИГНАТ', 'NAME')
```

`original` is itself a substitute. Three consequences, all confirmed:

1. A **billed audit event** and a **new vault row whose `original` is a fake** — a fake-of-a-fake
   chain (`is_own_substitute` is exact-case, `mask_one`'s `_compute` therefore mints).
2. The same person acquires **two different substitutes in one transcript** (`панов игнат` in the
   earlier turn, `шилов филипп` in the replayed call).
3. The candidate's union then **admits that row as evidence**: `_index` keys `шилов филипп` to
   `real = панов игнат`, and `values_for_replayed` returns
   `(NAME, real='гущин демьян', substitute='цветков ярослав')`-shaped chains in the mixed fixture —
   a substitute whose `real` is another substitute. The 254/254 suite does not cover it:
   `test_protecting_an_echo_mints_no_new_substitute` (`:1471-1488`) measures only the PHONE
   substitute across two passes with the same context.

The first review reported this as a pre-existing P2 (`_mask_tool_calls` is unchanged by the diff).
That is still true, and it is not a privacy leak: the real value does not appear. It is a product
correctness and billing-hygiene defect that the repaired candidate now **depends on** for its
"case-changed leaf" evidence, so it should be decided explicitly rather than inherited.

Minimal fix direction: make `is_own_substitute` case-insensitive for NAME (fold as
`_identity_key`/`fold_key` already do, or reuse `_index`), and delete the fake-of-a-fake row.

---

## Follow-up (Codex lead): does the echo of that same value use the rendering the model reads?

Codex observed that `probe4.py` only measures the audit, and asked for the two strings that
actually matter. Tested. **Answer: no leak, but yes — a genuine function mismatch on the
PHONE-substitute branch, and the partial-prefix match leaves a visibly doubled fragment.**

### Commands

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python /tmp/hop-s01-recheck/probeK2.py     # echo pass instrumented
.venv/bin/python /tmp/hop-s01-recheck/probeK4.py     # corrected per-branch matrix
.venv/bin/python /tmp/hop-s01-recheck/probeK5.py     # exact strings, union + spans
.venv/bin/python /tmp/hop-s01-recheck/probeL.py      # span geometry per shape
```

### Measured, on the production path

Call = one field carrying only the dialogue's own substitute; result = the tool echoing that
substitute. `_replace_echoes` instrumented, so these are the spans and substitutes that really fired:

| shape | model reads | echo writes | real value in body | verdict |
|---|---|---|---|---|
| PHONE own substitute | `REDACTED…` (14 chars) | the **dictated-words rendering** (74–76 chars) | **absent** (full, 80-char cut, last word) | no leak; **wrong form** |
| NAME own substitute | the re-minted substitute | the same re-minted substitute | **absent** | consistent |
| NAME own substitute, retyped title-case | `«Цветков Ярослав»` | `«Цветков Ярослав»` | **absent** | consistent |
| NAME own substitute, retyped UPPER | `«УСТИНОВ ПЛАТОН»` | `«УСТИНОВ ПЛАТОН»` | **absent** | consistent |

So the lead does **not** produce a PII leak: every shape keeps the real value out of the provider
body. What it does produce is:

**(a) The echo form is not the string the model reads, on the substitute-replay branch.** Measured
target from the instrumented pass:

```
target type=PHONE len(real)=87 len(sub)=74 self=False spans=[(89, 106, 17)]
model reads: {'phone': 'REDACTED5dbe87'}
```

The `substitute` in the union entry is the *raw replayed leaf* (the dialogue's dictated rendering),
while the model reads the OPAQUE token this pass minted for that same field. This is the opposite of
the acceptance line "each message/field reflects its own form". The first review predicted this
branch (`s01-replayed-call-20260927.md:100-104`). **Finding 3 below pins the cause** — it is not the
union's ordering, as this paragraph first claimed, but the snapshot freeze plus the rendering this
pass minted; the same defect reproduces on the NAME branch in 12/12 fixtures.

**(b) The span geometry is a prefix cut, so the inserted rendering is longer than the text it
replaces.** The literal echo finds the longest common prefix of the two dictated renderings (26
characters, `«восемь девятьсот »`), bounded by `_prefix_is_a_cut` (`envelope.py:622-644`), and
`_replace_echoes` then writes the whole 74–76-character rendering into that 26-character span. The
body therefore grows (measured 170 → 227, 162 → 211) and carries a doubled fragment. Same in the
**pre-fix** branch (measured identical, `probeL`/inline pre-fix comparison) — so this is a
pre-existing defect of the echo machinery, not something the union introduced, and not something the
union fixes.

**(c) The case-change re-mint is mostly invisible from outside.** The echo and the model-visible
field agree in all NAME variants (`N2`, `L2`, `L3`), because the re-minted substitute is exactly what
the masking produced. The consequences stay the ones already reported in Finding 2 — a billed audit
event, a fake-of-a-fake `shown_forms` row, and two substitutes for one person across turns — not a
third-party-visible mismatch.

Severity of the follow-up: **P2**, product correctness, no PII exposure. It matters because the
request explicitly asked for the echo's form to equal the phone rendering the model reads in the
current request, and on this branch it does not.

Minimal fix direction (superseded in part by Finding 3, which shows the cause is the frozen
rendering index rather than the dedup order): prefer the model-visible leg's `substitute` when both
legs resolve one identity, and make `_replace_echoes` refuse a span whose replacement is longer than
the span — a rendering longer than the matched prefix is not an echo of it.

---

## Finding 3 (Codex lead, independently reproduced) — the matched path writes a rendering the model does not read

Codex reported a current-request form mismatch on the NAME branch. **Reproduced deterministically on
12 of 12 fresh fixtures**, and the mechanism is now pinned. It is real, it is on the *matched*
association path, and it does **not** leak the real value.

### Commands (fresh fixture every time, no sample string trusted)

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python /tmp/hop-s01-recheck/probeO.py   # 12 fresh fixtures, public path
.venv/bin/python /tmp/hop-s01-recheck/probeP.py   # production vs isolation, one process
.venv/bin/python /tmp/hop-s01-recheck/probeQ.py   # the production pass instrumented
```

### Measurement (probe O, 12 fresh fixtures, `_session` + `_mint_phone` + a user turn)

Replay `{"client": <shown NAME>}`, tool result = the FULL real name:

```
TALLY: {'full_form_MISMATCH': 12, 'full_noleak': 12, 'cut_form_MISMATCH': 9,
        'cut_removed': 12, 'cut_form_ok': 3}
MISMATCHES: 21
  full: shown='жуков михаил'  real='битюков олег' model_reads='гущин олег'        body='жуков михаил'
  full: shown='шилов радислав' real='битюков олег' model_reads='мещеряков аркадий' body='шилов радислав'
  cut : shown='мухин кузьма'   real='битюков олег' model_reads='наумов назар'     body='мухин '
  cut : shown='рыбаков леонид' real='битюков олег' model_reads='беляев евгений'   body='беляев евгений'
```

* **Full mention: 12/12 mismatch.** The model reads the substitute this request minted
  (`гущин олег`), the result carries the substitute the *previous turn* showed (`жуков михаил`).
* **8-character cut: 9/12 mismatch.** The cut is removed from the body in 12/12 (no leak); in 3 cases
  the re-minted rendering happens to match, in 9 it does not.
* **Real value: absent in 12/12** (full, cut and last word). So this is a form/identity defect, not a
  disclosure.

### Mechanism (probe Q, the production pass instrumented)

```
mask_one key=47481 changed=True   in : '{"client": "лебедев владислав"}'
                                 out: '{"client": "сазонов виктор"}'
values_for            arg='{"client": "лебедев владислав"}'
    ('NAME', 'битюков олег', 'лебедев владислав')
mask_one key=47481 changed=True   in : '{"client": "лебедев владислав"}'
                                 out: '{"client": "сазонов виктор"}'      <-- cache hit
values_for            arg='{"client": "сазонов виктор"}'  -> []           <-- resolves NOTHING
values_for_replayed   arg='{"client": "лебедев владислав"}'
    ('NAME', 'битюков олег', 'лебедев владислав')

model reads = 'сазонов виктор'   result field = 'лебедев владислав'   same = False
```

Three facts in one trace:

1. `_mask_tool_calls` masks the replayed arguments and, because `is_own_substitute` is exact-case
   (Finding 2), **mints a second substitute** for the same person: `лебедев владислав` →
   `сазонов виктор`.
2. `_model_visible_call` re-masks the same bytes, so it is the **cache hit** and returns exactly the
   rendering the model reads (`сазонов виктор`) — the mechanism is not at fault.
3. That fresh rendering **resolves to nothing**, because `provenance.snapshot()` froze the rendering
   index *before* the loop (`envelope.py:937-938`) and the row `сазонов виктор` was minted inside the
   pass. The union therefore keeps only the raw leg, whose `substitute` is the *previous* rendering.
   `_echo_targets` writes that older string into the result.

So the defect is **the snapshot freeze plus the fresh rendering**, not the union's ordering as I
first wrote in the follow-up above: the echo cannot see the substitute the model is reading in the
very request that minted it. A cross-check in isolation shows the opposite result, which is why this
took a second harness to pin: with the snapshot taken *after* masking (not production), the union
does contain `('NAME', 'юдин мирослав', 'сазонов герман')` and the echo agrees with the model
(`probeP.py`). The freeze is the difference.

### Is it a regression introduced by this candidate?

No. In the pre-fix `_mask_content` there was **no echo pass at all** (the diff's `-` side is
`masked_block["text"] = mask_one(...)`, no `_replace_echoes`), so this shape's real name reached the
provider raw. The candidate improves it to a substitute-versus-substitute mismatch. The correct
comparison is therefore *pre-fix leak → post-fix form mismatch*, not *correct → broken*.

### Severity and whether it blocks S01/E01

* **Severity P2** — product correctness / identity consistency, **not** a privacy defect. The
  acceptance line "each message/field reflects its own form" is not met on this branch; E01's
  security purpose (stop the real value reaching the model) *is* met on the matched path.
* **It does not block S01/E01, and it does not change the verdict of this review.** The blocker
  remains Finding 1, which is a real PII leak through the refused-association path.
* What it does do is remove the "residual, arguably cosmetic" reading of the first review's secondary
  finding: a model can now be shown one rendering of a person in the tool call and handed a different
  rendering of the same person in the tool result, in the same request, on the ordinary matched path.

Minimal fix direction: make the result leg prefer the **substitute the current request minted** —
either pass the model-visible arguments from `_mask_tool_calls` (already computed, same cache entry)
into `_mask_content` instead of re-deriving them, or resolve the token/rendering this pass minted
without admitting the row as *identity* evidence. Add a test asserting
`model_reads == result_field` for a replayed own substitute, full mention and 8-character cut.

---

## On the first review's requested fix

The implemented fix follows the first review's recommendation literally — union `values_for(raw)`
with `values_for(_model_visible_call(raw))` before `_echo_targets` — and it works:

* the union is per **leaf-in-both-forms**, not per call, so the mixed call no longer adopts one form
  for the whole call (`envelope.py:559-589`, call site `:846`, `:952-964`);
* the short-circuit when `visible_call.arguments == call.arguments` is sound: an identical masked
  form carries no value the raw read did not (`:581-587`);
* the second read is a cache hit (measured: 0 extra detection, 0 extra audit, 0 extra rows);
* snapshot semantics are preserved (`snapshot()` before the loop, `:937-938`);
* the refusal controls the first review checked remain green.

The gap is scope, not mechanics: the fix protects **within** a matched association, and the
association reader is the gate that decides whether the fix is reached at all. That gate is new in
this same diff and is strict enough to be the dominant residual risk.

---

## Residual limits, stated honestly

1. **Frequency is not measured.** The mechanism of Finding 1 is proved on seven shapes; how often a
   real app/gateway produces them is not measured here, and no live/paid run was made. The
   `ticket_find`-vs-display-name and sliding-window routes are the plausible ones.
2. **The refusal shapes I could not reach.** I did not construct a matched association that leaks —
   I tried and failed, which is evidence *for* the union. The leak needs the binding to be refused.
3. **Provider variety is untested.** Anthropic-style `tool_use`/`tool_result` blocks and
   LiteLLM-normalised transcripts were not run end to end; only the OpenAI-shaped messages the suite
   builds.
4. **`/unmask_arguments` residual route (the first review's route 2)** reproduced no resolvable fake
   leaf in this fixture (`probeF.py` F8 printed a fully restored string). It remains unproven rather
   than disproven.
5. **One probe step failed on a probe-side API mismatch**, not on the engine: `probe2.py` line 47
   calls `AuditLog.recent()` without its required `limit`; the three rows it printed before the
   traceback are valid and showed no leak.
6. **The union's substitute-form ordering — cause corrected in Finding 3.** My first pass could not
   turn the raw-first `substitute` into a wrong-form echo: with a restored REAL leaf, the raw leg's
   rendering is the customer's own writing and the model reads a token, which is exactly what
   `probeD.py` D3, `probeE.py` and `probeJ.py` J5 measured as *correct*. The Codex lead showed the
   branch where it goes wrong (a call whose own leaf **is** the dialogue's substitute), and
   `probeQ.py` then showed the cause is not the ordering but the snapshot freeze: the rendering this
   pass minted is the cache-hit model-visible form, yet it resolves to nothing because the index was
   frozen before the loop. Earlier revisions of this report attributed it to the dedup order; this
   entry supersedes that.

---

## Artefacts (all read-only, all in `/tmp`, outside the repo)

```
/tmp/hop-s01-probe/probe1.py … probe4.py      # the first review's probes, re-run unchanged
/tmp/hop-s01-recheck/probeA.py                # fresh request, two identities, shared fragments, case changes
/tmp/hop-s01-recheck/probeB.py                # union internals for case-changed own substitutes
/tmp/hop-s01-recheck/probeC.py                # per-leg instrumentation, detector/audit/row counts
/tmp/hop-s01-recheck/probeD.py                # which substitute form the echo inserts
/tmp/hop-s01-recheck/probeE.py                # pre-fix branch vs union branch, cold vs warm
/tmp/hop-s01-recheck/probeF.py                # remaining surface battery with invariant checks
/tmp/hop-s01-recheck/probeG.py                # matched bare-real leaf, branch comparison
/tmp/hop-s01-recheck/probeH.py                # the seven refusal modes
/tmp/hop-s01-recheck/probeI.py                # cost accounting + optional `name`
/tmp/hop-s01-recheck/probeJ.py                # minimal counterexample + warm-cache cost
/tmp/hop-s01-recheck/probeK.py                # own-substitute echo form (first cut)
/tmp/hop-s01-recheck/probeK2.py               # echo pass instrumented
/tmp/hop-s01-recheck/probeK3.py               # union content per shape
/tmp/hop-s01-recheck/probeK4.py               # corrected per-branch matrix
/tmp/hop-s01-recheck/probeK5.py               # exact strings: union, spans, before/after
/tmp/hop-s01-recheck/probeK6.py               # production path, model reads vs body
/tmp/hop-s01-recheck/probeL.py                # span geometry per shape
/tmp/hop-s01-recheck/probeM.py                # Codex's shape, instrumented first cut
/tmp/hop-s01-recheck/probeN.py                # substituted-NAME chain, per-step vault accounting
/tmp/hop-s01-recheck/probeO.py                # 12 fresh fixtures, public path (Finding 3 tally)
/tmp/hop-s01-recheck/probeP.py                # production vs isolation conflict, one process
/tmp/hop-s01-recheck/probeQ.py                # the production pass instrumented (Finding 3 cause)
/tmp/hop-s01-recheck/focused-254.log          # 254/254
```

No file under `research/`, `prototype/` or anywhere else in the repository was modified by this
review; this report is the only file written. Codex owns acceptance.
