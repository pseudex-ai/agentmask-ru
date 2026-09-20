# AgentMask-RU

**Does a PII-masking gateway break an LLM agent that calls tools?**

A benchmark and a harness for ANY masker. Russian language, 272 cases, 680 personal
values, 624 negatives. Code Apache-2.0, corpus CC BY 4.0.

*(Русская версия — [README.md](README.md). She is the authoritative one: the corpus
is Russian and so is the discussion of it.)*

## Disclosure: this benchmark is written by a vendor

AgentMask-RU is designed and maintained by the team behind **Pseudex**, a gateway this
benchmark measures. Therefore:

- The rule that admits a case is computable WITHOUT any masker and was fixed before
  any system was run. Value pools are disjoint from our production dictionaries by
  construction (`pools/build_pools.py`), and our own run's manifest prints how many
  of the corpus's names our gazetteer holds anyway.
- Our run is marked `vendor-submitted` and carries full per-item observations: anyone
  can recompute our lines with their own arithmetic.
- No run of ours is ever withdrawn. The worst numbers stay in the history.
- Our engine cannot be reproduced from this repository — it is licensed and detects
  nothing without a lease. Until a trial key is public, our row reads as a vendor
  claim, not an independent measurement, and we sign it that way.

## Why

Masking text is the easy half. An agent CALLS TOOLS, and a tool needs the real value:
`create_order(phone="+7 907 …")` finds no order under a substitute. So a gateway must
put the real value back into the argument — and break nothing else on the way. No
existing benchmark measures that: NER corpora have no tools, PII-masking corpora have
no tool calls, and tool-calling benchmarks (BFCL, τ-bench) have no personal data.

## Eight lines that never add up

`leak` (value altered before the model saw it) · `coverage` (no PIECE of it survived) ·
`typed` (type named correctly, where the masker exposes types) · `round_trip` (the tool
got the real value, over the values that WERE masked) · `end_to_end` (the same over all
values — "the agent still works") · `overmask` (order numbers, amounts, dates and bare
cities left alone) · `consistency` (the second mention of a person got the first one's
substitute) · `stability` (the substitute did not move between requests).

**There is no total score, and that is a decision.** A gateway that masks everything wins
the first line and loses the last two. Every rate carries an exact Clopper–Pearson
interval; a flawless line prints what it CERTIFIES, never "100%".

## Quick start

```sh
pip install -e .
agentmask run --adapter placeholder_regex
agentmask run --adapter openai_proxy --name my-gateway \
    --base-url http://localhost:8080/v1 --upstream-bind 0.0.0.0:8099
```

A proxy is measured WITHOUT a model: the harness starts a fake provider, the proxy
sends it the masked messages — exactly what the model would have seen — a scripted
"model" copies what it sees into a tool call, the proxy restores the arguments, and the
harness reads what the tool would have received.

## Results

See [leaderboard.md](leaderboard.md). Seven systems on one corpus, including
Cloud.ru's `guardrails-llm-filter`, LiteLLM's Presidio guardrail, Microsoft Presidio and
LLM Guard.

## Contributing

The unit of contribution is ONE case file. See [CONTRIBUTING.md](CONTRIBUTING.md).
