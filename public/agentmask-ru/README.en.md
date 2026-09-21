# AgentMask-RU

**Does a PII-masking gateway break an LLM agent that calls tools?**

[![gates](https://github.com/pseudex-ai/agentmask-ru/actions/workflows/ci.yml/badge.svg)](https://github.com/pseudex-ai/agentmask-ru/actions/workflows/ci.yml)
[![code](https://img.shields.io/badge/code-Apache--2.0-blue)](LICENSE)
[![data](https://img.shields.io/badge/data-CC%20BY%204.0-blue)](LICENSE-DATA)
[![python](https://img.shields.io/badge/python-3.12+-blue)](pyproject.toml)

[Contributing](CONTRIBUTING.md) · [Русский](README.md)

Masking text is half the job. An agent CALLS TOOLS, and a tool needs the real value:
`create_order(phone="+7 907 …")` finds no order under a substitute. A gateway must put
the real value back into the argument and break nothing else on the way. NER corpora,
PII-masking corpora and tool-calling benchmarks each measure something else.

## Overview

272 cases · 680 personal values · 624 negatives · Russian

| | |
|---|---|
| **Families** | `create_order` · `check_status` · `verify_identity` · `refund` · `send_sms` · `second_mention` |
| **Registers** | `clean` (as typed into a form) · `chat` (lower case, no separators) · `sloppy` (one slip) |
| **Types** | name · phone · address · date of birth · СНИЛС · ИНН · passport · card |
| **Name tiers** | `common` · `tail` · `diminutive` · `foreign` |
| **Adapters** | `noop` · `placeholder_regex` · `openai_proxy` · `presidio` · `llm_guard` · `pseudex_sidecar` |

Nine lines that **never add up to a single score**:

| line | meaning |
|---|---|
| `leak` | the value was altered before the model saw it |
| `coverage` | no PIECE of the real value survived into what the model saw |
| `typed` | the type was named correctly (where the masker exposes spans) |
| `round_trip` | the tool received the real value — over the values that WERE masked |
| `round_trip_repaired` | the same, also counting a value delivered in **canonical form** — `02.06.1975` for «2 июня 1975», the nominative of a name for its accusative. The gap to the line above is exactly the masker's normalisation, and nothing else |
| `end_to_end` | the same over all values: "the agent still works" |
| `overmask` | order numbers, tracking numbers, amounts, document dates and bare cities untouched |
| `consistency` | the second mention of a person got the first one's substitute — the same one **up to inflection**: «Харитон Рыбаков» and «Харитона Рыбакова» are one substitute |
| `stability` | the substitute did not change between requests |

A gateway that masks everything wins the first line and loses the last two. Every rate

**The judge reads Russian.** Names are compared by word lemmas (pymorphy3) in any
word order: «есина рушана» in the chat and «Рушан Есин» in the CRM are one person,
«Иван Петров» and «Пётр Иванов» are not (dictionary readings scored below 0.1 are
dropped). One rule for every system: a placeholder `<PERSON_1>` equals only itself,
as before. The table is re-derived from the recorded observations by the current
judge, so older runs are read with the same eyes as new ones.
carries an exact Clopper–Pearson interval; a flawless line prints what it **certifies**,
never "100%".

## Install

```sh
pip install -e .                 # core: standard library + jsonschema
pip install -e ".[presidio]"     # for the presidio adapter
pip install -e ".[llm_guard]"    # for the llm_guard adapter
```

## Run

```sh
# a library
agentmask run --adapter presidio

# any OpenAI-compatible masking proxy
agentmask run --adapter openai_proxy --name my-gateway \
    --base-url http://localhost:8080/v1 --upstream-bind 0.0.0.0:8099

# record a run and rebuild the table
agentmask run --adapter presidio --out results/
agentmask leaderboard
```

A proxy is measured **without a model**: the harness starts a fake provider, the proxy
sends it the masked messages — exactly what the model would have seen — a scripted
"model" copies what it sees into a tool call, the proxy restores the arguments, and the
harness reads what the tool would have received.

Recipes for third-party gateways are in [`baselines/`](baselines/).

## Results

This repo ships the HARNESS, not a table. Numbers — especially measurements of
OTHER products — are not published here: they belong in an article, where the
methodology is visible and it reads as the author's measurement, not an
«official ranking». Run your own:

```sh
agentmask run --adapter <your adapter> --out results/   # results/ is .gitignored
agentmask leaderboard                                    # table, locally
```

`results/` and `leaderboard.md` are deliberately `.gitignore`d. Every run carries
per-item observations, so any result is recomputable — but it is published by
whoever measured it.

## Corpus

Generated deterministically; `--check` proves the committed corpus is exactly what the
seed produces.

```sh
agentmask build --seed 20260920 --out cases/
agentmask build --seed 20260920 --out cases/ --check
```

Values come from Wikidata (CC0), NEN (CC BY 4.0), mimesis and Faker (MIT). Phone numbers
are drawn from **reserve DEF codes** of the Russian numbering plan (Приказ Минцифры № 75):
valid to libphonenumber, assigned to no subscriber. Ground truth is the canonical form
of **what was written**. Attributions in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Checks

```sh
agentmask gates          # seven gates
pytest -q                # 29 tests
```

The gates guard against a corpus that cannot fail: `G6` requires the passthrough to
carry every case, `G7` requires the naive regex to leave a mark wherever a case does not
state why it cannot, `G8` watches the strata. `tests/test_gates.py` breaks each property
on purpose and requires the gate to go red.

## Disclosure

This benchmark is written by the **Pseudex** team, whose gateway it also measures.

- The rule that admits a case is computable without any masker and was fixed before any
  system was run.
- Value pools are disjoint from Pseudex's production dictionaries by construction; our
  run's manifest prints how many of the corpus's names our gazetteer holds anyway.
- Our run is marked `vendor-submitted`, carries full observations, and is never withdrawn.
- Our row is reproducible **by the same path as everyone else's**: a trial key from
  [pseudex.ru](https://pseudex.ru) (14 days, no payment), the released image and the
  `openai_proxy` adapter — recipe in [`baselines/pseudex/`](baselines/pseudex/). The
  engine is licensed and its source is not here; the benchmark sees only what the
  endpoint answers.

## Not measured (v0.1)

Streaming · PII arriving back from a tool · agent memory across conversations ·
restoring a substitute the model inflected or transliterated · TOST equivalence.

## Citation

```bibtex
@misc{agentmaskru2026,
  title  = {AgentMask-RU: does a PII-masking gateway break a Russian-speaking LLM agent?},
  author = {{AgentMask-RU contributors}},
  year   = {2026},
  url    = {https://github.com/pseudex-ai/agentmask-ru}
}
```

Code Apache-2.0 · corpus CC BY 4.0 · results CC0 · contributions under [DCO](DCO).

Canary: `AGENTMASK-RU-CANARY-7c1e4b2a-6f3d-4a8e-9b1c-2d5e8f0a3b7c`

*Unrelated to `adithyan-ak/agentmask` and to the MASK Benchmark (CAIS).*
