# S01/E01 independent adversarial review — replayed call vs result echo

Task: `hop-replayed-call-review-20260927` · workspace `/Users/igor/Projects/Obscura-hop-audit`
(verified: `pwd` = that exact root; `git rev-parse --short HEAD` = `9c5acbb`).
Scope: candidate change in `prototype/pseudex/envelope.py` (working-tree modification, 762 insertions)
plus its new test `prototype/test_error_echo_privacy.py` (untracked). Source and tests read-only; no
engine/test edit was made. No children, no live/paid eval. Runtime: `.venv/bin/python` 3.12.12.

## Verdict: REJECT (the all-or-nothing provenance gate at `envelope.py:929`)

One concrete, reproduced counterexample leaks the exact value S01 exists to protect, silently
(no error, no 5xx, no residual: the fail-closed invariant is satisfied only on paper here).

## What was verified as sound

* `cd prototype && .venv/bin/python test_error_echo_privacy.py` → **246/246 passed**. The
  single-leaf replay case (`test_a_restored_real_leaf_grants_provenance`, `test_error_echo_privacy.py:591`)
  does behave as documented: the raw replayed real leaf is masked in the call and the echo answers with
  the string the model reads in *that* request.
* Snapshot semantics (`envelope.py:509-520`, call site `:904-905`) are correct: `_literals`/`_identities`
  are frozen before the loop, and rows minted during the pass (observed: one new `shown_forms` row in the
  restored-real pass) are excluded, so the pass cannot read its own writing back.
* Conversation scoping holds: `Vault.shown_forms` filters `WHERE customer=? AND conversation=?`, and the
  cross-conversation suite (incl. `test_only_this_dialogue_s_own_record_grants_provenance`) is green.
* `_model_visible_call`'s cache/audit claim (`envelope.py:846-851`) holds **for the single-leaf path**:
  a restored-real pass produced 3 detector calls (user turn, assistant args, result body) and audit
  `{'NAME':1,'OPAQUE':1,'PHONE':1}`; a fourth detection or a second audit event for the same call would
  have shown up. The `mask_one` inside `_model_visible_call` is the earlier `_mask_tool_calls` cache hit.

## Failing counterexample (P0 — real PII reaches the model)

Command (probe reused the test file's own fixtures, in-memory only):

```
cd /Users/igor/Projects/Obscura-hop-audit/prototype
.venv/bin/python /tmp/hop-s01-probe/probe1.py
```

Fixture: one conversation, `USER_MESSAGE` mints the dictated PHONE substitute and a NAME substitute.
Call arguments = the RESTORED REAL dictated phone **plus one leaf this dialogue already showed**; result =
`DOSSIER_ERROR_REAL` (the 80-char cut of the real dictated words). A/B only in the extra leaf:

```
--- CONTROL single restored REAL leaf ---
  args on the wire (raw) : {"phone": "восемь девятьсот двадцать шесть … двадцать три восемсь"}
  args model reads       : {"phone": "REDACTEDf816e7"}
  echo fragment leaked   : False
--- MIXED restored REAL leaf + already-shown NAME rendering ---
  args on the wire (raw) : {"phone": "восемь девятьсот двадцать шесть … восемсь", "client": "карпов макар"}
  args model reads       : {"phone": "REDACTEDf816e7", "client": "юдин богдан"}
  echo fragment leaked   : True
```

Isolation (`probe2.py`, same fixture, third leaf varied):

```
(a) no extra field                             leaked=False
(a) extra field, does NOT resolve  ("1428570") leaked=False
(a) extra field, DOES resolve (shown NAME)     leaked=True
```

Cause, `prototype/pseudex/envelope.py:929-930`:

```python
if result_call is not None and not provenance.values_for(result_call):
    result_call = _model_visible_call(result_call, context)
```

`values_for(raw)` is all-or-nothing **per call**. As soon as ONE leaf of the replayed arguments resolves
as a rendering/token this dialogue showed, the raw form is adopted for the whole call and
`_model_visible_call` is skipped, so every OTHER leaf that only the model-visible masking would have
converted (the restored REAL leaf) contributes no provenance. The comment at `:919-928` ("Both forms are
this call's own arguments, so neither is inferred") is true per leaf and false per call: the two forms are
never merged. The model therefore reads a masked phone in the call while the same call's result echoes the
raw dictated fragment — a direct contradiction of the property the new test asserts at
`test_error_echo_privacy.py:661`.

Trigger conditions (honest statement): the call must carry at least one restored-real leaf *and* at least
one leaf that resolves through `shown_forms`/token/digit columns. Two production routes: an app that
composes `arguments` from its own state (real from the CRM for one field, the substitute for another), or
`unmask_arguments` residuals (a field that failed to restore stays a fake while the rest become real) if
that residual is resolvable. Route 1 is reproduced above; route 2 was not reproduced inside the budget.

## Secondary finding (P2, pre-existing but newly load-bearing)

Re-masking an **own** substitute inside a replayed call is not recognised as our own when its rendered case
differs from the minted token:

```
probe3.py
(c) shown NAME: беляев артур | real: битюков олег | peek_token: Беляев Артур
(c) mask_one(shown NAME) -> {"client": "карпов тарас"}
(c) new rows: {('карпов тарас', 'беляев артур')}
probe4.py
own-NAME-replay  mask_one: audit {} -> {'NAME': 1}
own-PHONE-replay mask_one: audit {} -> {'OPAQUE': 1}, shown_forms rows +1
```

Two consequences: a billed audit event and a new vault row whose `original` is itself a fake (a
fake-of-a-fake), and in the raw-first branch the echo is answered with `беляев артур` while the model reads
`карпов тарас` in the same request — the E01 acceptance line "each message/field reflects its own form; the
cache does not return another mention's form" is not met on this branch. `_mask_tool_calls` is unchanged by
this diff, so this is not introduced here; but the candidate now *consumes* the replayed arguments as
evidence, and `test_protecting_an_echo_mints_no_new_substitute` (`:1328`) measures only the PHONE substitute
between two passes, so it does not cover it.

## Other questions asked, answered from the code

* *Raw-first stale evidence*: `_Provenance` is per pass and `_calls` is memoised per `(call_id, arguments)`,
  so no cross-request staleness was found; the defect above is the per-call gate, not staleness.
* *Wrong call/conversation/value*: `_recorded_here` (`envelope.py:457-466`) gates the customer-wide
  token/digit columns to the dialogue's frozen literals/identities; the suite's negative controls
  (unmatched/future/duplicate/mismatched id, unparseable args, foreign conversation) are green. Note the
  literal branch is type-agnostic (`real in self._literals`), which is intentional but widens provenance to
  any type that wrote the same literal; no failing repro was found for it.
* *Cache/audit*: no extra detector work or audit event from `_model_visible_call` itself (measured above).
  The audit inflation observed is on `_mask_tool_calls`, described in the secondary finding.

## Recommendation

REJECT as submitted. Minimal fix direction: keep the raw-first read, but resolve per leaf —
`resolved = values_for(raw)`, and when any leaf is still unresolved, also read the model-visible form
(`values_for(_model_visible_call(raw))`, which is a cache hit and costs no detection or audit, verified
above) and UNION the two value sets before `_echo_targets`. That preserves every refusal control
(a never-carried leaf still resolves to nothing in both forms) and closes the mixed-call leak. A test with
the two-leaf call from `probe1.py` belongs in the same change.

Remaining uncertainty: (1) the production frequency of mixed restored/residual call arguments is not
measured here — the mechanism, not the rate, is proven; (2) whether the sidecar's `/unmask_arguments`
residual path can itself produce a resolvable fake leaf (route 2) is unverified; (3) the secondary
own-substitute re-mint may be intended behaviour of `is_own_substitute` for derived forms — it should be
decided explicitly, not left as a side effect of this change.
