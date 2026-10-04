# S0 — error echo: root cause and red regression

## Current integration finding — 2026-09-27

The owner approved automatic linkage using the existing OpenAI transcript,
not a new mandatory customer parameter. Inspection found that the historical
benchmark does not retain that wire linkage: `RealGateway.note_tool_call` in
`prototype/bench/agentpii4/gateway.py` writes a function call without `id`, and
`push_tool` writes a result without `tool_call_id`. `GatewayV5` inherits those
methods. The archived call has written/restored arguments and `seq`; its tool
result has sequence/ordinal metadata, not a recoverable provider call ID.

Consequently a new literal fixture may reconstruct a protocol-faithful call
and result with **explicitly synthetic IDs**, but must not label those IDs as
archived evidence. v4 remains read-only. The v5 adapter must expose the same
call/result relation as the production envelope and preserve parallel/repeated
calls; positional or tool-name matching alone is not sufficient. The inherited
`_push` also compares production masking to a context-free `score._mask_message`
pass. That observer must be addressed explicitly: accepting a context-sensitive
engine output by dropping the double-pass guard would weaken the instrument.

The current local privacy test still has its single headline RED (**14/15**).
The headline now supplies the literal archived restored argument and error in
a standard transcript with explicitly synthetic matching IDs. Two added
controls pin non-mutation and ID preservation. Fixture setup also accepts a
dictated substitute rather than insisting on digit-only masking; the canary
and privacy assertion are unchanged. No contextual echo protection has been
implemented or certified yet.

The rest of this document records the original reproduction below.

Date: 2026-09-27. Case: `long_support-013` (source A, repeat 0). Read-only:
no engine change, no live model, no network. The regression test is
[`prototype/test_error_echo_privacy.py`](../../prototype/test_error_echo_privacy.py);
this file is the evidence behind it. Adjudication context: [README](README.md)
§4 (the leak "survives" re-verification), [chains.md](chains.md) §2.

**Engine state.** The S0 masking path is the committed engine and is untouched
here: `pseudex/detect_all.py` (SHA256 `45b6ed77…`), `pseudex/envelope.py`
(`ac3d7e0b…`), `pseudex/spoken.py` — all clean against `git HEAD`
(`9c5acbb13e02ae3b230a31411bef2877ecc23ef3`). `redact.py` and `vault.py` in the
worktree carry the separately checkpointed PHONE-OUT form work and are cited
only where their state changes the observed chain; the S0 gate below does not
depend on them.

## 1. What the literal record says

The first user turn carries the dictated phone:

```
добрый день не пришёл заказ это битюков олег телефон восемь девятьсот двадцать
шесть пятьдесят четыыре семьдесят восемь двадцать три восемсь кстати заа проезд
наличнымии
```

Real canonical: `+79265478238` (cluster `PHONE:9265478238`). The mock refuses
the call (`phone_not_e164`) and `Refusal.as_error`
(`bench/agentpii4/tools.py`) echoes the offending value **truncated to 80
characters**: `f"поле {path}: {rule}: {raw[:80]}"`. The dictated run is 87
characters, so the echo is the real value minus its final word `восемсь`. In
the dossier the two literal fields are byte-equal:

```
"text_real":   "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три \"\n  }\n}"
"text_masked": "{\n  \"error\": {\n    \"code\": \"phone_not_e164\",\n    \"field\": \"phone\",\n    \"message\": \"поле phone: phone_not_e164: восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три \"\n  }\n}"
```

The refused call is `ticket_find` seq 1 (`call_ordinal 0`, `turn 1`) and the
same pair repeats for `crm_find_contact seq 1` and both turn-1 retries.

## 2. Production-core probes (dev bundle, ephemeral vault)

`testkit.load_dev_bundle()` + `Detector()` + `Vault(":memory:")`, no model.
Verbatim output of the probe used for this section:

```
[d1] detect(full dictated run): [('PHONE', 'восемь девятьсот двадцать шесть пятьдесят четыыре семьдесят восемь двадцать три восемсь')]
[d2] detect(echo = full[:80]): []
[d3] detect(exact error body) : []
[d5] numeral words full: ['восемь','девятьсот','двадцать','шесть','пятьдесят','четыре','семьдесят','восемь','двадцать','три','восемь']  (11)
[d6] numeral words echo: ['восемь','девятьсот','двадцать','шесть','пятьдесят','четыре','семьдесят','восемь','двадцать','три']          (10)
```

- The **full** 87-character dictated run is detected as `PHONE` (it concatenates
  to the valid 11-digit national number `89265478238`).
- The **80-character echo** is not detected at all — not as a standalone run,
  not inside the exact error body. Its 10 numeral words yield a 10-digit run,
  which is not a valid Russian number.

Chain, through the production masking path (`envelope.mask_messages`, called by
the sidecar/proxy and by the benchmark's `RealGateway.push_tool`,
`bench/agentpii4/gateway.py:173`):

```
[m1] masked user: ... телефон +79251553030 ...
[m2] shown_forms: [('+79251553030', 'восемь ... двадцать три восемсь', 'PHONE'), ...]
[m3] fake written by agent: +79251553030
[m4] tool received (unmask_arguments): '+79265478238'          # current worktree: digits
[m5] dossier text_real == text_masked: True                    # <-- the leak
[m6] dossier payload out of mask_messages == input bytes, unchanged
[m7] live echo masked (digits form): ... phone_not_e164: +79251553030
[m8] untruncated echo masked:        ... phone_not_e164: +79251553030
```

`[m6]` is the defect reproduced: the gateway minted the value, knows it in
`shown_forms`, and still hands the model the real dictated fragment. `[m7]`/`[m8]`
show that the rescan itself works — it masks the untruncated run and any
recognizable form. The failure is specifically that the mask leg only trusts
detection and never consults the values it itself injected.

## 3. Competing hypotheses and verdicts

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | **Detector spoken parse** fails on the echoed run | **Proximate mechanism — confirmed, not the fix target** | `[d1]` vs `[d2]`/`[d3]`: 11 numeral words → PHONE; 10 words → nothing. The validity gate (11-digit RU number) is the same gate that keeps ordinary numbers unmasked; teaching the detector to accept a 10-digit invalid run is broad generic fragment masking. |
| H2 | **Gateway does not rescan / lacks context** | **Half-true: rescan present, context absent** | `RealGateway.push_tool` → `_push` → `mask_messages` runs detection on the tool result; `[m7]`/`[m8]` prove masking fires on recognizable forms. What is absent is the *known-value* context: the restored arguments are never offered to the tool-result mask. |
| H3 | **Restoring an invalid agent value into the tool, then echoing it** | **True as the ORIGIN of the dossier event; not the masking failure** | In the audited checkout the arguments leg returned the customer's dictated words for a digits-form argument (`chains.md` §2). In the current worktree the separately checkpointed PHONE-OUT rendering returns digits (`[m4]`), so this origin no longer fires — yet `[m6]` still leaks, because a tool may echo what it received in any form. |

The defect is therefore **H2 in its "context" sense, triggered by H1's
validity gate**. H3 explains how the sensitive text entered the tool result; it
is neither necessary (the dossier payload leaks regardless of form) nor
sufficient (a correctly-formed argument can still be echoed back truncated).

## 4. Honest scope: a fragment, not the whole number

`README.md` explicitly refuses "the whole phone leaked". The production core
agrees:

- The echo is a **strict prefix** of the dictated value (80 of 87 characters);
  its digit signature `8926547823` is a **strict prefix** of the real
  `89265478238` — the trailing `8` (`восемсь`) is absent.
- The digit-form `+79265478238` never appears in the error payload.

The test pins this so no later summary grows into "the phone leaked". The claim
supported here is: **ten of eleven digits of the real number, in spoken form,
reach the model.**

## 5. The regression test

`prototype/test_error_echo_privacy.py` (script with `main()`, no pytest).

- **Gates on the exact archived literal payload**, independent of regenerating
  the erroneous OUT: the dossier string is a constant, fed to
  `envelope.mask_messages` with a vault that has actually minted the value.
- **RED today:** `12/13` checks pass; the single failure is
  `HEADLINE: the dossier's literal error echo loses the real fragment`.
- **Green controls that must stay green:**
  - `an untruncated dictated echo is masked` — the rescan is present (H2/H1 pin).
  - `an ordinary order number and quantity stay unmasked` — the negative; a fix
    must not mask non-personal numbers.
  - `conversation B does not attribute the fragment to A's person` (and not to
    B's) — the false-attribution / cross-conversation control; a fix must not
    pool value memory across conversations or persons.
  - the fragment-vs-whole-number honesty pins.

```
$ cd prototype && PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_error_echo_privacy.py
...
12/13 passed
error echo privacy NOT in place:
  - HEADLINE: the dossier's literal error echo loses the real fragment
```

Three consecutive runs give the same single RED; no gate depends on the random
mint.

## 6. Remedy: narrow, and what needs an owner decision

The evidence points at one narrow direction and rules out two broad ones.

**Do not** (a) relax the detector to call an invalid 10-digit run a phone, and
(b) mask arbitrary numeric prose — either turns the ordinary-number negative red
and is exactly the over-masking the audit forbids.

**Narrow direction:** give the tool-result masking leg the *known-value* evidence
it already holds — the real strings the gateway itself wrote into that tool
call — and protect those in the result. Concretely: after
`unmask_arguments`/`restore_arguments` for a call, remember the `(real string →
substitute)` pairs written into that call in this conversation; when masking the
result, mask occurrences of those real strings. The truncation case then needs a
bounded rule for a **prefix of a just-injected value** (the tool echoed
`raw[:80]`), never a free-floating fragment.

**Owner decision required before implementation.** The scope is a product
contract, not a code detail: which values are "known" (this call's restored
arguments only, or every value minted in the conversation?), how short a prefix
may still be protected without over-masking, and what happens across
conversations. This file recommends the tightest scope — *per conversation, per
call, values actually restored into a tool call, with a minimum-length prefix
rule* — but does not choose it silently. No engine change is made here.

## 7. Reproduce

```
cd prototype
python3 test_error_echo_privacy.py            # 12/13, RED on the headline
```

The literal payload this test gates on is the verbatim `text_real`/`text_masked`
pair quoted in §1, copied from
`research/hop-format-audit/evidence/cases/long_support-013.md`.

## 8. Not claimed / limits

- Only `long_support-013` was read in full here; instrument-level claims about
  prevalence stay with the audit's 450-case scope.
- H3 is reported from the audited checkout's records and from the current
  worktree probe; the exact seam (`_restore_verbatim_spans` vs
  `_restore_tokens_spans`) is not re-derived here.
- The `raw[:80]` truncation is a property of the mock
  (`Refusal.as_error`); a real upstream may truncate differently. The defect —
  masking that trusts detection over known values — is independent of the
  truncation length.
- No whole-number disclosure is claimed; see §4.
