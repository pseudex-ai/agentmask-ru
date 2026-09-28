# S01 unbound / E01 current-request-form — independent adversarial recheck (2026-09-28)

Task: `hop-s01-unbound-privacy-review-20260928` · workspace `/Users/igor/Projects/Obscura-hop-audit`
(`pwd` verified = that root). Second independent recheck after
`research/hop-format-audit/evidence/reviews/s01-mixed-recheck-20260927.md` (REJECT).

**Verdict, stated separately:**

* **S01 privacy: PASS** — the refused-association leak that the previous review rejected is closed on
  all seven shapes. A tool result bound to no usable call is now **neutrally redacted**
  (`REDACTED…`), the 80-character dictated fragment is absent, and no real person's substitute is
  guessed. One honest limit remains and is stated in §5.
* **E01 current-request form: PASS with residual** — on the matched association the result now carries
  the rendering the current request minted (the model-visible leaf), not the previous turn's string.
  One residual P2 case-retyped rendering mismatch was observed (no leak); the literal
  `long_order-058` PHONE-notation shape was **not** re-run inside this budget and is listed as not
  measurable.

No code, test, wiki, corpus or saved transcript was modified. The only file written is this report.

---

## 1. Scope, discipline, hashes

* Read-only. Probes live in `/tmp/hop-s01-recheck2/` and import the engine; they do not modify it.
* No child sessions or subagents. No network, no provider, no paid 450, no live benchmark.
* Frozen candidate reviewed: `prototype/pseudex/envelope.py` sha256
  `2ee78458856717a6f86fb4735384db6a6cf4119efd7c34ada7a040e3a0cb5c6b` and
  `prototype/test_error_echo_privacy.py` sha256
  `1eb33e65c37b4e4c496facaaad8101ca5fabebf8a4151f8df8a5474c09ef204b`. Both match the task's
  hashes. `git rev-parse --short HEAD` = `9c5acbb`.
* `prototype/bench/agentpii5/actual_hops.py` / `test_actual_hops.py` were not opened, run, edited or
  attributed; the concurrent writer owns them.
* Binding context read: `wiki/MAP.md`, `wiki/INVARIANTS.md`, `wiki/AGENTMASK.md`,
  `docs/plan-hop-form-before-450.md` (rows S01 line 44, E01 line 51, and the §4 responsibility table),
  the prior REJECT report, and the frozen candidate.
* Runtime: `.venv/bin/python` 3.12.12, commands from `prototype/`.

## 2. What was recomputed independently

| command | result |
|---|---|
| `.venv/bin/python test_error_echo_privacy.py` | **284/284 passed**, exit 0 |
| `python3 wiki/check.py` (repo root) | **0 finding(s)** (map, flows, claude, index, state, invariants) |
| `.venv/bin/python /tmp/hop-s01-recheck2/probeR2.py` | own fixtures, §3/§4 |
| `.venv/bin/python /tmp/hop-s01-recheck2/probeR4.py` | cache discriminator |
| `.venv/bin/python /tmp/hop-s01-recheck2/probeR5.py` | own-substitute replay / Finding 2 |

The 284/284 is author-adjacent; it is reported as a recomputation, not as proof. The proof is the
fresh fixtures below, built here from my own dictated number (`+7 915 265-47-88` spelled out,
85 characters, one typo in a group) and my own names, never copied from the suite's constants.

Fixture precondition, printed by the probe (`probeR2.py` §A):

```
REAL len=85
full detected=True   cut80 detected=False
```

That is the S01 mechanism: the full dictation is recognised and mints a substitute; the tool's
80-character cut (`real[:80]`, the echo `Refusal.as_error` writes) is **declined by the detector by
design**, so call provenance is the only layer that can protect it.

## 3. S01 — the seven refused association shapes (prior Finding 1)

Same transcript, same store, same bytes in `arguments`; the only variable is the binding. Result body
is the 80-character cut of the recorded dictation. `probeR2.py` §B:

| shape | `tool_result_contexts` status | cut in model body | substitute/real present | neutral redaction |
|---|---|---|---|---|
| wrong id | `missing` | **no** | no | `REDACTEDd4954b` |
| id key absent | `missing` | **no** | no | `REDACTEDd4954b` |
| duplicate id | `ambiguous` | **no** | no | `REDACTEDd4954b` |
| future declaration | `missing` | **no** | no | `REDACTEDd4954b` |
| mismatched tool name | `invalid` | **no** | no | `REDACTEDd4954b` |
| invalid JSON arguments | `invalid` | **no** | no | `REDACTEDd4954b` |
| no declaration at all | `missing` | **no** | no | `REDACTEDd4954b` |

`TALLY_B {'leak': 0, 'sub': 0, 'neutral': 7, 'n': 7}`. This is the exact property the previous
review found false. The mechanism in the candidate is the **second, weaker leg**
`_Provenance.recorded_values()` → `_echo_targets(...)` → `_replace_echoes(..., recorded, ...)`, which
answers an echo of a value *this conversation recorded* with `_neutral_redaction` and never with a
substitute. It is fed to every `role == "tool"` message (`envelope.py:1242-1243`, `:1272-1275`), which
is why a refused binding no longer removes protection. The suite now asserts the *absence* of the
fragment for these shapes (`test_error_echo_privacy.py:1436-1480`), not its presence as the old suite
did.

**Matched mixed raw-real PHONE + shown NAME** (`probeR2.py` §C), both JSON orders: cut leak `False`,
real-name leak `False`, shown-name in body `False`, shown-phone in body `False`. The model-visible
call leaf and the result agree:

```
model_args={"client": "Осипов Виктор", "phone": "REDACTED157e45"}
body_tail='   "message": "поле phone: phone_not_e164: REDACTED157e45"\n  }\n}'
```

Note the real-leaf side is answered with a **neutral redaction**, not a substitute — consistent with
the policy that attribution stays call-scoped while privacy is conversation-scoped.

## 4. E01 — current-request form (prior Finding 3) and Finding 2

**Matched own substitute replay** (`probeR2.py` §D). Full mention and 8-character cut, model-visible
leaf vs result rendering:

| model retype | model reads in the call | real value in result | result rendering (cut) |
|---|---|---|---|
| as-is | `Беляев Николай` | absent | `Беляев ` |
| casefold | `беляев николай` | absent | `Беляев ` |
| upper | `БЕЛЯЕВ НИКОЛАЙ` | absent | `Беляев ` |
| title | `Беляев Николай` | absent | `Беляев ` |

No real fragment reaches the result in any variant, and the model's identity is unchanged (the guard
leaves the retyped own substitute alone rather than minting a second person). The residual: when the
model itself retypes the substitute in a non-canonical case, the **result's cut rendering is
canonical title-case** while the model leaf preserved the retyped case. That is a form deviation
(P2, E01's "each field reflects its own form"), not a disclosure. It is the opposite direction of the
old defect and is reported as open, not as a blocker.

**Finding 2 (case-retyped substitute re-minted) is closed** (`probeR5.py`, own substitute captured
from the same store, then replayed through `mask_messages`' tool-call leg):

```
as-is    own_shown='Жуков Александр' surface='Жуков Александр' rows 2->2 new=0 model_args={"client": "Жуков Александр"}
casefold own_shown='Беляев Прохор'   surface='беляев прохор'   rows 2->2 new=0 model_args={"client": "беляев прохор"}
upper    own_shown='Фомин Гордей'    surface='ФОМИН ГОРДЕЙ'    rows 2->2 new=0 model_args={"client": "ФОМИН ГОРДЕЙ"}
```

Zero new `shown_forms` rows, no fake-of-a-fake, no audit/slot inflation. `_own_renderings` is
case-folded (`envelope.py:472-478`) and `_is_own_rendering` reads both the exact and folded surface.

**Cache-key dependence** (`probeR4.py`, same context, same text, evidence vs no evidence):

```
casefold with_ev='{"client": "сорокин семён"}' (rows 2->2) | no_ev_same_ctx='{"client": "крылов николай"}' (rows 2->3) differ=True
upper    with_ev='{"client": "СОРОКИН СЕМЁН"}' (rows 3->3) | no_ev_same_ctx='{"client": "КРЫЛОВ НИКОЛАЙ"}' (rows 3->4) differ=True
as-is    with_ev='{"client": "Сорокин Семён"}' (rows 2->2) | no_ev_same_ctx='{"client": "Сорокин Семён"}' (rows 2->2) differ=False
```

The evidence-bearing and evidence-free readings are separate cache entries
(`_own_evidence_key`, `envelope.py:1013-1031`), and no cross-order collision was observed: the
evidence-free read can never serve the re-minted fake to the evidence-bearing caller. The `as-is`
row is covered by the older exact-case `is_own_substitute`, so a difference there is not required —
which is also why the ordinary prose/transcript path keeps its previous key and its dedup.

## 5. Controls, limits, and data not measurable

* **Ordinary quantities unchanged** (`probeR2.py` §E2): an armed matched result carrying
  `{"order": 12345, "date": "15.05.2025", "count": 8, "code": 7926547}` comes back **byte-identical**.
* **Foreign conversation unchanged** (`probeR2.py` §E3): conversation B, which never recorded A's
  value, leaves the fragment raw and attributes no substitute. This is the deliberate
  conversation-scope boundary, not a regression — B cannot protect a value it never handled.
* **EXACT LIMIT — a bare tool result with no preceding recorded value is not protected**
  (`probeR2.py` §E1): a transcript whose vault never restored the value
  (`[{"role":"tool","content": <80-char cut>}]`) passes the cut through raw. Public path, measured.
  There is no preceding value for provenance to key on, and the detector declines the truncated
  numeral run by design (teaching it to accept ten dictated digits is the forbidden generic rule).
  This is a real residual, stated rather than papered over; it is narrower than the rejected Finding 1
  (which leaked *even when the value was recorded and restored by this dialogue*).
* **Not measurable in this budget:** the production frequency of the refused association shapes; the
  Anthropic-style `tool_use`/`tool_result` transcript and LiteLLM-normalised messages; the live HTTP
  wrappers. `proxy.py:407` and `service.py:472` both call `envelope.mask_messages`, so the repaired
  leg is on both entry paths by construction, but no server was started. The literal
  `long_order-058` PHONE-notation shape (`+7…` result vs `8 …` user form) was not re-run.
* **Doc gate, not a security verdict — resolved doc-only:** the 2 expected import-map findings from
  `envelope -> detect` were cleared by syncing `wiki/MAP.md` and running `wiki/check.py --sync`;
  at recheck time (before and after the sync) the check reports **0 finding(s)** and the frozen
  candidate hashes are unchanged. This is a documentation gate and does not change the S01/E01
  behavior verdict.

## 6. Reproduction

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python test_error_echo_privacy.py              # 284/284, exit 0
.venv/bin/python /tmp/hop-s01-recheck2/probeR2.py        # 7 shapes + matched mixed + form + limits
.venv/bin/python /tmp/hop-s01-recheck2/probeR4.py        # cache discriminator
.venv/bin/python /tmp/hop-s01-recheck2/probeR5.py        # Finding 2 replay
cd .. && python3 wiki/check.py                           # 0 findings
```

Verdicts: **S01 privacy PASS** (refused-association leak closed; neutral redaction; no wrong-person
substitute; ordinary quantities and foreign conversations untouched) with the §5 bare-unrecorded
limit stated. **E01 current-request form PASS with one residual P2** case-retyped rendering mismatch.
This is an independent recheck, not a formal acceptance claim; Codex owns acceptance.
