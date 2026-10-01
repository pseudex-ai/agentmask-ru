# D0 — mechanism options, licence/lease/resource feasibility

This document is an **inventory and a cost sheet**, not a ranking. Under
[OWNER-DECISIONS Q4](<../OWNER-DECISIONS.md#L29-L31>) and
[REMAINING-DECISIONS block 4](<../REMAINING-DECISIONS.md#L29-L34>) the mechanism
family is chosen by the owner after evidence; D0 supplies the evidence that can
be obtained without installing, downloading or calling anything.

**Everything in the "resource" column is `NOT_MEASURED`.** The only timings D0
produced are exploratory single-run numbers on a host shared with other sprint
tasks (see [SPEC.md](SPEC.md#L112-L121)); they are not a p50/p95, not an
admission budget, and not comparable across candidates. The protocol that would
make them comparable is [RUNBOOK-PERF.md](RUNBOOK-PERF.md).

## 1. What already exists on this host (verified, read-only)

| Item | Version | Licence (primary) | Where the weights are | Present offline? |
|---|---|---|---|---|
| `natasha` + `navec` + `slovnet` + `razdel` + `yargy` | 1.6.0 / 0.10.0 / 0.6.0 / 0.5.0 / 0.16.0 | MIT — installed metadata + [THIRD-PARTY-NOTICES.md:82](</prototype/THIRD-PARTY-NOTICES.md#L82>) | vendored in `.venv/lib/python3.12/site-packages/natasha/data/` | **yes** |
| news NER weights actually used | `slovnet_ner_news_v1.tar` 2 385 920 B `16c3343a…` | ships inside the MIT wheel; upstream *weight* licence statement `NOT_VERIFIED` | `natasha/data/model/` | yes |
| news embeddings used | `navec_news_v1_1B_250K_300d_100q.tar` 26 634 240 B `f0727083…` | same | `natasha/data/emb/` | yes |
| other `slovnet` model tars (e.g. wiki-domain) | — | MIT (library) | not downloaded | **no** |
| spaCy / DeepPavlov / stanza / flair | — | — | — | **no** (not installed) |
| `transformers`, `torch` | — | — | — | **no** (not installed) |
| `cointegrated/rubert-tiny2` | HF cache 115 MB, ref `e8ed3b0c…` | **MIT** — [model card](https://huggingface.co/cointegrated/rubert-tiny2) | `~/.cache/huggingface/hub/` | weights yes, **runtime no** |
| `Isotonic/deberta-v3-base_finetuned_ai4privacy_v2` | HF cache 712 MB | **cc-by-nc-4.0 (non-commercial)** — [model card](https://huggingface.co/Isotonic/deberta-v3-base_finetuned_ai4privacy_v2) | `~/.cache/huggingface/hub/` | weights yes, **runtime no** |

Machine-readable form with hashes and the exact labels/config read from the local
cache: [MODEL-INVENTORY.json](MODEL-INVENTORY.json).

## 2. Candidate matrix

`Avail` = could be run today with what is installed; `Ship` = can these weights
legally and practically reach a customer image/lease.

| # | Candidate mechanism | Avail | Licence | Russian ability | Ship / lease path | Resource status | What it would cost to know |
|---|---|---|---|---|---|---|---|
| 1 | **Current product**: rules + gates + Natasha news NER (+ Natasha address) | yes | MIT deps | in production; register-dependent (see SPEC §5) | already shipped via pip dependency; `natasha/data` rides in the image | ~350 MB resident/worker is the project's measured per-worker figure ([preflight.py:19,33](</prototype/pseudex/preflight.py#L19>)); not re-measured by D0 | nothing new; it is the baseline arm |
| 2 | **Rules-only** (no ML NER; address layer still needs natasha's `AddrExtractor`, [address.py:84](</prototype/pseudex/address.py#L84>)) | yes (D0 `RULES_ONLY` arm) | MIT | loses 18/56 `LOC` on `golden`; identical to full on the lowercase speech slice in D0 | does **not** remove the natasha dependency, so it saves no shipping weight | exploratory 5.25 ms/text vs 12.35 for full (same run, not comparable) | controlled p50/p95/RSS per RUNBOOK |
| 3 | **Bare news NER** | yes (D0 `RAW_NER` arm) | MIT | not viable alone: 0/295 on lowercase speech, 28.5% whole on golden | — | — | **not a candidate** — ablation only (D0 brief) |
| 4 | **Union rules ∪ NER** | yes (D0 `HYBRID_UNION` arm) | MIT | equal to full on golden/gatectx; +7 over-masks on `dirty` | — | — | **not a mechanism** — ablation ceiling only |
| 5 | **Additional `slovnet` models** (different domain/config) | **no** (weights absent) | MIT library | unknown | would ship in the image like natasha's; needs size/cold-start review | `NOT_MEASURED` | download + install are **out of scope this wave**; needs an owner-approved acquisition step |
| 6 | **Fine-tuned Russian encoder** (`rubert-tiny2`, MIT, 3 layers/312 hidden, MLM head only) | **no** (torch/transformers absent) | MIT (weights) | pretrained Russian encoder; **no** token-classification head → needs fine-tuning | small enough for an image in principle (115 MB cache); but training data/labels are A1/O-DATA territory and the output weights need a licence+ship review | `NOT_MEASURED` (RSS/latency of a 3-layer BERT on CPU vs the current model stack unknown) | install + build a training pipeline on approved gold + controlled perf; **new owner decision** |
| 7 | **ai4privacy DeBERTa** (111 labels incl. `CREDITCARDCVV`) | **no** (torch/transformers absent) | **cc-by-nc-4.0 — non-commercial** | English corpus; Russian efficacy `NOT_VERIFIED` | **cannot ship** in a commercial product as-is | `NOT_MEASURED` | useful only as an offline research contrast; any use needs legal review first |
| 8 | **Local LLM as detector** (several GGUF/MLX models are cached on the host) | partially (host runtimes, not this venv) | varies | unknown/unevaluated for token-level PII | large weights, large RSS, per-call latency; conflicts with the current per-worker memory budget | `NOT_MEASURED` | not justified by D0 evidence; only if the owner wants an LLM-family comparison |
| 9 | **External inference API** | — | — | — | — | — | **forbidden**: P15, D0 brief (no PII to external inference) |

## 3. Shipping and leasing constraints any new mechanism must satisfy

These are the constraints the matrix above is filtered through; they are product
rules, not D0 opinions:

- **Engine ships empty of authored tuning**; the tuned data travels in the leased
  bundle (`CLAUDE.md`, [docs/tz-tuning-in-lease.md](</docs/tz-tuning-in-lease.md>),
  GOAL-BRIEF P15). The lease payload today is 1 524 582 bytes in memory
  (`2a07cebae2b050ec`, `01c19f46…`); putting hundreds of MB of weights into the
  lease would be paid on **every** renewal and would sit in every worker's RAM.
- **`pseudex/data` must not ship** and `pseudex/` must not import `licensing/` or
  `sqlite3` — both are build-time failures ([Dockerfile:82–87](</prototype/Dockerfile#L82-L87>)).
- **Image budget and cold start are gated**: image < 1.5 GB, cold start to first
  successful `/mask` < 20 s (P8, [docs/tz-license-packaging.md:931](</docs/tz-license-packaging.md#L931>)).
- **Per-worker memory is arithmetically enforced** by `PSEUDEX_ROLE=preflight`
  against the cgroup limit with a default 350 MB/worker + 128 MB headroom
  ([preflight.py:33–39](</prototype/pseudex/preflight.py#L33-L39>)). A heavier
  model raises N×RSS and therefore lowers worker count or raises the container
  limit — a material cost that must be shown to the owner **before** adoption
  (REMAINING-DECISIONS block 4).
- **Third-party notices are maintained** in
  [THIRD-PARTY-NOTICES.md](</prototype/THIRD-PARTY-NOTICES.md>); any new weight
  set needs a row there with a primary licence source.

## 4. What D0's ablation does and does not license

Observed (bounded known-diagnostic slices, [SPEC §5](SPEC.md#L74-L121)):

- the news-NER layer is what finds 18 of 56 `golden` `LOC` values that the rules
  layer misses, but it emits **one** span across the whole lowercase-speech
  occurrence slice, where `FULL` and `RULES_ONLY` are then numerically identical;
- raw NER adds over-masking on `dirty` (ORG spans) when unioned;
- all 12 golden `DATE` items are emitted as `DOB` by every product-path arm.

Not licensed by that:

- that rules "suffice" — the speech slice is 587 hand-labelled occurrences of
  dictionary-shaped words, not a PII distribution;
- that NER "does not help" — the register in which it contributes here is
  capitalized news-like text, and the gold sets are ours;
- any causal statement about why a component failed, or any transfer of these
  differences to production traffic;
- any ranking between candidates 1, 5 and 6, which is exactly the decision
  `O-DETECT` reserves.

## 5. The question the owner has to answer (`O-DETECT`)

Per [SPRINT-PLAN §7](<../SPRINT-PLAN.md#L174>) and
[GOAL-BRIEF §9](<../GOAL-BRIEF.md#L318>), `O-DETECT` is
"actual architecture choice and material CPU/RAM/latency cost after D0" — not a
permission to compare. To be answerable it needs, at minimum:

1. **Identical quality** of every candidate on the *same* approved gold
   (rules-only, current hybrid, and any new NER family), per type/register, with
   `x/n` and CI, plus the true-negative side — via the harness in this folder
   extended with the new arm, run on data approved through `O-DATA`.
2. **Measured cost**: cold start, p50/p95/p99 detect latency, RSS per worker,
   throughput, model bytes on disk, image-size delta — produced by
   [RUNBOOK-PERF.md](RUNBOOK-PERF.md) in an isolated phase, never on a host
   shared with other measurement work.
3. **Feasibility**: licence of the weights (not just the library), the lease/image
   path they would use, and the effect on the 350 MB/worker and 1.5 GB image
   budgets.
4. **A candidate acquisition plan** if a new family is chosen: what is
   downloaded, from where, under what licence, and who approves it — because
   this wave is forbidden from downloading.

Until then: no candidate is adopted, and `RAW_NER` in particular is **not** a
proposed production replacement.
