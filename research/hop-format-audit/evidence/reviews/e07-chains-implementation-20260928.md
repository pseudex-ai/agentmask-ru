# E07 CHAINS — implementation note (2026-09-28)

Row **E07** of the 19-row hop-format sprint: «verify real A→B tool chains, repeats,
corrections, memory, and several entities WITHOUT substituting the agent's action choice for the
gateway evaluation». The harness already carried `source_hop` on declared hops and
`run_triple_v5` / `actual_events`, but no test pinned chain / repeat / correction / memory /
multi-entity behaviour. This note records the test that closes the row.

Pinned file: `prototype/bench/agentpii5/test_harness_stream.py` — new check
`test_chain_repeat_correction_memory_two_entities`, registered in `main()`. Only that test file
was touched; the engine (`prototype/pseudex/*`) and `harness.py` were NOT modified.

## The five properties, and the one small case that pins them

The case is built by hand (`_chain_case`): a system prompt, two user turns, two `contacts` seed
records, two PHONE entities of one type. Real values `+79164021187` (identity **i1**) and
`+79261234567` (identity **i2**) — the first in a message, both in a seed record
(`p1s`/`p2s`), with the same two values in the message (`p_msg1`/`p_msg2`).

Declared hops (turn 1) carry the chain link — the OUT/tool_arg `notify_sms.number` hop has
`source_hop == 3`, the `hop_index` of the IN/tool `crm_find_contact` `contacts[].phone` hop:

| # | kind | owner | item | tool | path | source_hop |
|---|---|---|---|---|---|---|
| 0/1 | IN | user | p_msg1 / p_msg2 | — | — | −1 |
| 2 | OUT | tool_arg | p_msg1 | crm_find_contact | query.phone | 0 |
| 3 | IN | tool | **p1s** | crm_find_contact | contacts[].phone | −1 |
| 4 | OUT | tool_arg | **p1s** | notify_sms | number | **3** (the chain) |
| 5 | OUT | tool_arg | p_msg2 | crm_find_contact | query.phone | 1 |
| 6 | IN | tool | p2s | crm_find_contact | contacts[].phone | −1 |
| 7 | OUT | tool_arg | p2s | notify_sms | number | 6 |

The agent is **scripted, no LLM, no network** through the REAL `GatewayV5` path
(`GatewayHooks`, the same seam `ConnectedArms._run` drives, over
`seed_backend_v5` + an in-memory `Vault` + `load_dev_bundle()`). The script echoes the
substitutes the gateway just minted, so the RESTORED value is the assertion and the mint itself
is not. It makes, in order: find→SMS (a: chain), find→SMS (e: second entity), SMS again
(b: repeat), wrong-SMS then right-SMS (c: correction), and a turn-2 SMS (d: memory). The
restored `ArmRunV5` is then read by `actual_hops.actual_events`.

| property | what the assertion pins |
|---|---|
| (a) chain | `source_hop` on the notify hop names the IN/tool `crm_find_contact.p1s` hop; and the FIRST actual `notify_sms.number` crossing is attributed to `p1s` and restores to `+79164021187` with `value_ok` and `form_ok`. |
| (b) repeat | every actual `notify_sms` call is exactly ONE `number` event — `len(events) == len(calls)`, with distinct `call_seq`; a merge would drop the count. |
| (c) correction | the wrong number (p2s) is a crossing, and the re-issued right one (p1s) is a LATER crossing — `max(right) > max(wrong)`. |
| (d) memory | the turn-2 `notify_sms.number` crossing is attributed to `p1s` and restores `+79164021187`, i.e. the turn-1 value persists. |
| (e) two entities | identity `i1` restores only `+79164021187`, `i2` only `+79261234567`; both crossed at least once; no substitute reaches the tool (`residual` empty). |

The measurement follows the ACTUAL events: the turn-2 memory crossing is measured even though
the declared hops are all at turn 1, and no turn number is asserted equal to the declaration.

## Command and exit code

```
cd prototype
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m bench.agentpii5.test_harness_stream
```

Result: `harness_stream: PASS` — exit code **0**.

## The instrument can fail (RED checks, each reverted after)

| broken property | mutation | result |
|---|---|---|
| (a) chain (declared) | flip `source_hop` 3→6 on the notify hop | FAIL: «source_hop 6 ведёт не на IN/tool crm_find_contact.p1s» — exit 1 |
| (a)/(e) point B at the wrong entity | chain SMS writes `sub_two` instead of `stored_one` | FAIL: «первый notify_sms.number ушёл не на сущность цепи (p1s), а на p_msg2» — exit 1 |
| (c) correction | re-issue the wrong number again | FAIL: «исправленный номер не стал ПОЗЖЕ неверного — правка не измерена» — exit 1 |
| (d) memory | turn-2 SMS writes the other entity | FAIL: «значение с хода 1 не дошло до хода 2 — память не измерена» — exit 1 |

(b) is structural (`events == calls`); a dedupe in `actual_events` drops the count and fails the
same line. The `test_harness.test_only_harness_imports_pseudex` guard still passes (no new test
file, no new `pseudex` importer).
