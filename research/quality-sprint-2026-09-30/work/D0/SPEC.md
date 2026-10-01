# D0 — comparable detector-mechanism experiment (design/RED wave 1)

Status: **executed, scoped PASS** for the local design/RED part of G3. This is
**not** an architecture decision, **not** an engine-quality verdict, and **not**
a production measurement. `O-DETECT` remains `OWNER_PENDING`.

## 1. Authorization and scope

| Source | What D0 is bound by |
|---|---|
| [FIRST-WAVE-TASKS D0](<../FIRST-WAVE-TASKS.json>) | "reproducible comparable detector mechanism experiment, not choose architecture"; read-only source/packages inventory; harness comparing full `Detector` vs bare Natasha on identical explicit gold; per-type overlap/whole/wrong-type/FP + source hashes; candidate/license/lease/resource matrix; precise steps for a later controlled p50/p95/RSS experiment; O-DETECT needs real cost and quality, not invented numbers; deliver INPUTS/SPEC/harness/smoke.log/OPTIONS/GATE (no full PASS) |
| [SPRINT-PLAN §6 D0](<../SPRINT-PLAN.md#L121>) | isolated research harness/outputs; shipped code unchanged; no PII to external inference |
| [SPRINT-PLAN §7 G3](<../SPRINT-PLAN.md#L147>) | RED reproducible on a pinned unchanged build; causal mechanism only where input/state was reproduced; a disputed choice is the owner's |
| [GOAL-BRIEF P15/P17](<../GOAL-BRIEF.md#L152-L166>) | engine ships empty; weights must satisfy shipping/lease/licence/resource rules; compare rules/local-NER/hybrid on identical gold with real CPU/RAM/latency, no pre-declared winner |
| [OWNER-DECISIONS Q4](<../OWNER-DECISIONS.md#L29-L31>) | comparing variants is allowed; choosing one is reserved to the owner |
| [REMAINING-DECISIONS block 4](<../REMAINING-DECISIONS.md#L29-L34>) | best proven quality under the principles; real resource cost shown and a material regression agreed **before** adoption; point estimate + CI, small slices are not full acceptance |
| [B0 GATE/REVIEW](<B0/GATE.json>) | G1 local/design PASS; production digest `NOT_VERIFIED`; product source pinned `0bfda236` |

Write scope honoured: everything D0 wrote is under
`research/quality-sprint-2026-09-30/work/D0/`. No file under `prototype/`,
`licensing/`, `wiki/`, `corpora`, run directories or git was modified
(`git status --porcelain` on those paths is empty; see §7).

## 2. What D0 is and is not

**Is:** a durable, re-runnable harness that puts several detection mechanisms on
the *same* explicit gold and reports a fixed outcome taxonomy, plus an inventory
of what local models/weights actually exist on this host and what shipping them
would cost.

**Is not:** a ranking, a recommendation, a product change, a claim that
`RAW_NER` replaces anything, or a causal attribution of a quality difference to
one component. An ablation shows a *difference on this gold*; it does not show
why, and it does not transfer to production traffic.

## 3. Exact requirement (falsifiable)

D0 is satisfied when all of the following hold, and they are recorded in
`GATE.json`:

1. A harness exists in this folder that can run ≥3 mechanisms (product rules+NER,
   rules-only, raw NER) over identical texts with explicit gold, is deterministic,
   and needs only `testkit.load_dev_bundle()` + the in-process models.
2. It reports per gold type: `exact`, `whole_same_type`, `partial_same_type`,
   `wrong_type` (and *which* type was used instead), `miss`, character coverage,
   and prediction-side FP split by what the prediction landed on
   (`declared` / `other` / `place` / `public` / nothing).
3. It records source hashes of every engine/licensing module it can influence,
   model-weight hashes, gold-file hashes, the bundle identity, and verifies the
   engine modules against B0's pins.
4. Instrument controls can fail: a positive control proves the harness sees the
   detector, a negative control proves empty input yields zero spans. Both pass.
5. A candidate matrix with availability, licence, lease/shipping feasibility and
   resource status exists, and every unmeasured cell says `NOT_MEASURED` instead
   of a number.
6. A runbook specifies the later controlled p50/p95/RSS experiment precisely
   enough to be executed and independently repeated.

## 4. Instrument design, and the two counting bugs found while building it

Gold is never re-labelled by the harness; it only reads existing known-diagnostic
sets:

| Slice | Source (sha256) | Units |
|---|---|---|
| `golden` | [dataset.json](</prototype/dataset.json>) `82901b0f…` (100 cases) | 298 unique (span,type) gold |
| `dirty` | [dirty.json](</prototype/dirty.json>) `970c4ab2…` (150 cases) | 134 unique gold + 6 declared hard negatives |
| `gatectx` | [gate_candidates.json](</Users/igor/.cache/pseudex-bench/gate_candidates.json>) `508bf6de…` × [labels.json](</prototype/bench/gate/labels.json>) `d2133f5d…` | 587 hand-labelled occurrences: 295 must-mask (person 271 + address 24), 292 must-not (other 209, place 26, public 57) |

Two defects were found *in the instrument itself* and fixed before any number
was kept (this is the "an instrument that cannot fail is not an instrument"
rule):

1. **Double-counted occurrence rows.** `labels.json` has 587 unique keys but the
   occurrence list contains 634 labelled rows (47 keys appear 2–3×). Counting
   rows inflated the denominator to 634/320. Fixed: dedupe by the instrument's
   own key ([sheet.py:101](</prototype/bench/gate/sheet.py#L101>)).
2. **A prediction counted once per sibling occurrence.** A text carries several
   labelled occurrences; a prediction that misses one occurrence's gold was
   re-counted as a fresh false positive for every sibling occurrence in the same
   utterance. Fixed: gold items are counted once per (span,type), predictions
   once per unique text.

Both bugs are recorded here because the first run's numbers (320 gate gold,
121 gate FP) are wrong and must not be quoted.

## 5. Executed result — bounded known-diagnostic slices only

Command (exit 0), full log in [smoke.log](smoke.log), raw data in
[out/arm-results.json](out/arm-results.json) and
[out/arm-summary.tsv](out/arm-summary.tsv):

```
cd prototype
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  ../research/quality-sprint-2026-09-30/work/D0/d0_arm_compare.py \
  --out ../research/quality-sprint-2026-09-30/work/D0/out
```

Slice `golden` (298 gold), whole-same-type / character coverage:

| arm | exact | whole | partial | wrong type | miss | char cov | pred |
|---|---:|---:|---:|---:|---:|---:|---:|
| `FULL` (product) | 266 | 20 | 0 | 12 | 0 | 0.9699 | 288 |
| `RULES_ONLY` (ablation) | 248 | 20 | 0 | 12 | 18 | 0.9174 | 270 |
| `HYBRID_UNION` (ablation) | 266 | 20 | 0 | 12 | 0 | 0.9699 | 288 |
| `RAW_NER` (ablation) | 85 | 0 | 13 | 0 | 200 | 0.2990 | 98 |
| `RAW_NER_REGEX` (ablation) | 167 | 0 | 13 | 25 | 93 | 0.5925 | 233 |

Slice `gatectx` (295 must-mask occurrences, lowercase real speech):

| arm | exact | whole | wrong type | miss | char cov | pred | typed TP | FP other/place/public | neg masked |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `FULL` | 145 | 93 | 3 | 54 | 0.8415 | 372 | 233 | 104 / 7 / 25 | 69/292 |
| `RULES_ONLY` | 145 | 93 | 3 | 54 | 0.8415 | 372 | 233 | 104 / 7 / 25 | 69/292 |
| `RAW_NER` | 0 | 0 | 0 | 295 | 0.0000 | 1 | 0 | 1 / 0 / 0 | 0/292 |
| `RAW_NER_REGEX` | 0 | 0 | 0 | 295 | 0.0000 | 1 | 0 | 1 / 0 / 0 | 0/292 |

Slice `dirty` (134 gold + 6 declared negatives): `FULL`/`RULES_ONLY` 134/134
whole, 0 FP, 0 negatives masked. `RAW_NER` 14/134 whole, 7 FP-other.
`RAW_NER_REGEX` 57/134 whole, 41 wrong-type (INN/SNILS/PHONE/CARD/PASSPORT →
`NUM`), 2 FP on declared negatives, 1 negative masked.

Wrong-type details: `FULL`, `RULES_ONLY` and `HYBRID_UNION` turn all 12 golden
`DATE` items into `DOB`; `FULL` turns 3 gate `LOC` occurrences into `NAME`;
`RAW_NER_REGEX` turns 25 golden `INN` into `NUM`.

Timings on this run are **exploratory only** (single run, host shared with other
sprint tasks, and a second run of the same harness gave `FULL` 7.58 ms/text
instead of 12.35): `FULL` 12.35, `RULES_ONLY` 5.25, `HYBRID_UNION` 6.70,
`RAW_NER` 0.89, `RAW_NER_REGEX` 0.73 ms/text over 791 unique texts. These are
**not** a p50/p95 and **not** an admission budget — see
[RUNBOOK-PERF.md](RUNBOOK-PERF.md).

### What these numbers do and do not say

- The news-NER layer's contribution is **register-dependent on this gold**: it
  is what finds 18 of 56 `LOC` in `golden` (rules-only misses them), but on the
  lowercase real-speech occurrence slice `FULL` and `RULES_ONLY` are *identical*
  (238/295 whole, 54 misses, same FPs) because bare news NER emits one span in
  the whole slice. That is a fact about this harness's inputs; it is not proof
  that NER is useless, and not proof that rules suffice.
- `HYBRID_UNION` being equal to `FULL` on `golden`/`gatectx` says only that raw
  NER adds no *new* covered gold there; it adds 7 over-masks on `dirty` (ORG
  spans). Union is not a mechanism and this is not a recommendation.
- The 104 `other` + 7 `place` + 25 `public` predictions on hand-labelled
  occurrences are consistent with the gate instrument's own ceiling
  ([bench/gate/README.md](</prototype/bench/gate/README.md#L26-L35>): 78.0% of
  masked occurrences must be masked, precision 84.8%), but D0 does **not** claim
  those as precision estimates: the slice here is the whole labelled set, not the
  instrument's two 300-occurrence strata, and no CI is computed.
- Known-diagnostic counts from the earlier read-only measurement
  ([conversation/summary.md](</research/hop-format-audit/detection-status-2026-09-30/conversation/summary.md>))
  are cited as context, not re-derived: AgentPII-RU 98.60%/97.88%, real OpenSTT
  addresses 90.91%/90.91%, MASSIVE person 85.35%/81.07%, typed span PPV 99.24%.

### Instrument controls (executed)

| Control | Requirement | Result |
|---|---|---|
| positive | `FULL` yields ≥2 spans on synthetic «Позвоните Иванову Ивану по телефону +79261234567» | PASS — `NAME` «Иванову Ивану», `PHONE` (36–48) |
| positive (golden) | `FULL` whole-recall on `golden` > 0 (can fail if the detector is not loaded) | 0.9597 |
| negative | empty string yields 0 spans from every arm | PASS |

## 6. Identity and non-drift evidence

- Bundle rebuilt in memory: version `2a07cebae2b050ec`, 1 524 582 bytes,
  sha256 `01c19f4689450b54694b7aaa4070cbaf695efc3e98f0b59471486392a0348206` —
  **identical to [B0 RUNTIME.json](<B0/RUNTIME.json>)**, nothing written to disk.
- 63/63 hashed `prototype/pseudex/*.py` + `prototype/licensing/*.py` modules match
  B0's pins (drift 0); the four leased dictionaries match B0's recorded hashes.
  HEAD is the evidence-only commit `890c5084…`; this is consistent with
  "product source remains pinned `0bfda2363ef1a1d552e2ac093129b1026a86ad68`".
- Model weights actually used: natasha news NER
  `slovnet_ner_news_v1.tar` 2 385 920 B `16c3343a…`, navec news embeddings
  `navec_news_v1_1B_250K_300d_100q.tar` 26 634 240 B `f0727083…` — vendored in
  `.venv`, no download, no network call.
- No holdout file exists in `prototype/` and none was read; the paid run
  directory was not opened.

## 7. Rejected alternatives (deliberate)

| Not done | Why |
|---|---|
| downloading/installing any new model or library | forbidden this wave; `slovnet` weights, spaCy, transformers/torch are simply absent offline |
| sending any text to a provider/external inference | P15, D0 brief |
| choosing or recommending an architecture | Q4: the comparison is allowed, the choice is the owner's |
| stashing/checking out to produce a "before" build | measure-skill's stale `git stash` recipe is not applicable; B0 archive + hashes are the baseline |
| running the holdout or the whole AgentPII/NEREL batteries | expensive, shared host, and not needed to prove the harness; would also mix a meter question into a mechanism question |
| patching the engine to expose arm switches | D0 changes no shipped file; `RULES_ONLY` is a documented subclass only and is labelled an ablation |

## 8. Open questions and unknowns

1. **`O-DETECT` (owner).** Which mechanism family is worth a full 99%-gate
   attempt, and what resource envelope is acceptable? D0 supplies the harness,
   the observable ablation differences and the candidate inventory; it supplies
   **no** p50/p95/RSS and **no** quality number that could rank families.
2. **Real cost is unmeasured.** Every candidate's latency/RSS/image-size cell in
   [OPTIONS.md](OPTIONS.md) is `NOT_MEASURED`. The protocol to fill them is
   [RUNBOOK-PERF.md](RUNBOOK-PERF.md).
3. **Russian-capable non-commercial vs commercial candidates.** The one local
   token-classification model with a PII label space is English + `cc-by-nc-4.0`
   (non-commercial) — unusable as a shipped mechanism, usable only as a research
   contrast. The only local Russian encoder is a pretrained MLM with no
   token-classification head, i.e. it would require fine-tuning (training data,
   labels, an owner decision) before any number exists.
4. **Lease/shipping path for any new weight set is unresolved.** Today the NER
   model rides inside the image through the `natasha` pip dependency; the lease
   carries 1.52 MB of tuning, and the image must stay <1.5 GB with <20 s cold
   start (P8). Whether a larger model may ship in the image, or must be leased,
   or must be built as a separate artifact, is an owner/packaging decision, not
   a D0 finding.
5. **The gate slice is not a quality gate.** It is a diagnostic occurrence
   instrument with our own labels; D0 uses it to separate context/boundary
   behaviour per arm, not to estimate product precision.

Evidence index: [out/source-hashes.json](out/source-hashes.json) (source, model,
dictionary, gold hashes and the B0 pin check), [out/arm-results.json](out/arm-results.json)
(machine-readable run), [out/arm-summary.tsv](out/arm-summary.tsv) (per-type
table), [smoke.log](smoke.log) (stdout, exit 0).
