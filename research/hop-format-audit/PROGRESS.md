# M0 → S0 → F1: expected results and measured changes

## Current checkpoint — 19/19 accepted; final integration regression GREEN

Formal acceptance: **19/19**. Final one-shot local regression (all from `prototype/`,
`PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python`; `PYTHONFAULTHANDLER=1` for perf):
`test_loop` PASS · `test_product` PASS · `test_overmasking` **99.5%** (HEAD parity) ·
`test_phone_hop_form` 16/16 · `test_other_hop_forms` **98/98** · `test_name_subject_form`
28/28 · `test_location_hop_form` 16/16 · `test_spoken_identifier_form` **124/124** ·
`test_derived_forms` PASS · `-m bench.agentpii5.test_payload_canaries` PASS ·
`test_argument_form` PASS · `test_perf_masking` **PASS** (exit 0, no 139) ·
`-m bench.agentpii5.test_harness_stream` PASS (E07 chain PASS) ·
`-m bench.agentpii5.test_harness` PASS. `wiki/check.py` **0 findings** ·
`git diff --check` clean · `ast.parse` clean on redact/morph_names/detect_all/translit/vault/morph_places.

`E07 = ACCEPTED_FIX`: a new in-process check
`test_chain_repeat_correction_memory_two_entities` in
`test_harness_stream.py` drives the REAL `GatewayV5` path (`GatewayHooks` +
`seed_backend_v5`, scripted agent, no LLM/network) and pins all five: (a) chain —
`source_hop==3` on the notify hop names the IN/tool `crm_find_contact.p1s` hop and
the first actual crossing restores `+79164021187` with value+form ok; (b) repeat —
6 calls → 6 `number` events with distinct `call_seq`, never merged; (c) correction —
right crossing later than wrong; (d) memory — turn-2 crossing restores the turn-1
value; (e) two entities — i1/i2 never swap and no fake reaches the tool. Assertions
read the RESTORED value (not the mint), so the agent's action choice is not
substituted for the gateway eval. Non-vacuity: flipping `source_hop` 3→6 → RED.
Only `test_harness_stream.py` touched (engine and `harness.py` untouched). Evidence:
`evidence/reviews/e07-chains-recheck-20260928.md` over
`evidence/reviews/e07-chains-implementation-20260928.md`.

Two NON-BLOCKING gaps recorded by the re-check: (A) the check omits its own
`load_dev_bundle()` — standalone it raises `BundleNotLeased`, passing only via
`main()` ordering; (B) the `correction` sub-check is a necessary condition, not a
unique pin (deleting only the correction block leaves the test green; same shape
for `repeat`). Both are recorded, not silently claimed fixed.

`C01 = ACCEPTED_FIX`: `test_other_hop_forms.py`
82/82 → 98/98 (+16 = 10 cross-type, 3 per-type negatives, 3 fake-checksum).
Cross-type examples are real (SNILS leading-8 signature resolves typed as SNILS,
not phone-spliced; INN-10-vs-PHONE; CARD-vs-INN; PASSPORT-vs-INN/PHONE;
PLATE-vs-prose «от»); per-type negatives stay unmasked through the real
`Detector`+`mask_text` and go masked when their gate is broken; the fake-checksum
assertion is `validate_*(fake) is True` — the engine mints checksum-VALID
substitutes from impossible ranges (ИНН region «00», card MII 0, СНИЛС never
≤ 001-001-998; `research/2026-09-03-checksum-valid-substitutes.md`). This
surfaced a stale doc line: CLAUDE.md + wiki/INVARIANTS.md claimed
"checksum-INVALID" and are now corrected to checksum-VALID-from-impossible-ranges.
Mutation test (in `/tmp`) flips one cross-type and one checksum expectation → RED.
Evidence: `evidence/reviews/c01-coverage-recheck-20260928.md` over
`evidence/reviews/c01-coverage-implementation-20260928.md` (impl) and
`evidence/reviews/c01-c02-coverage-20260928.md` (first reject).

`C02 = ACCEPTED_FIX` (G1+G4, G3 a documented
limit): the malformed `+8`/`++` PHONE hybrid is gone on all three restore passes
(`_malformed_phone_sign`), spoken EMAIL/PLATE reconstruction is pinned, and the
zero-width Unicode leak is recorded as a limit imposed by the 1:1 `#normalize`
invariant. Evidence: `evidence/reviews/c02-g1-g4-recheck-20260928.md` over
`evidence/reviews/c01-c02-coverage-20260928.md` (reject).

`E03 = ACCEPTED_FIX` after the third repair moved
off the pre-verbal noun onto the NAME's own gender: `governing_cases` takes the
name surface and `_oblique_object_case(surface) = (detect_gender(surface) !=
"femn")`, so a masculine/undetermined name after a 3rd-person finite verb is the
object and a feminine name the subject; the independent re-check reproduced
every subject class (система/оператор/менеджер/сервис/приложение/скрипт/… +
masculine object → `иванов пётр`; feminine subject → `громова марина`; declined
feminine object → `громова марина`; `приедет иванов пётр` preserved) with no
grammatical counterexample. Evidence:
`evidence/reviews/e03-subject-object-recheck3-20260928.md` over the three prior
rejects.

- `C03 = ACCEPTED_NO_CHANGE` — nested JSON (string/number/escaped-quote) restores
  with types intact, chunked == buffered, per-`choice.index` carry prevents
  splicing, a failing field stays a residual and never pulls a sibling's value.
  Evidence: `evidence/reviews/c03-c06-transport-20260928.md`.
- `C04 = ACCEPTED_NO_CHANGE` — no blanket quote-exemption exists; quoted PII is
  masked/restored exactly like unquoted (fail-closed); quoted markers and
  measurements stay untouched; the OD-2 boundary («д. 7») is the address
  marker+number anchor, not a quote rule. Evidence:
  `evidence/reviews/c04-quote-assessment-20260928.md`.
- `C06 = ACCEPTED_NO_CHANGE` (code surface) — vault persistence, tenant and
  conversation isolation, cache, and proxy↔sidecar masking parity hold (both
  entry points now share `envelope.mask_messages`; the CLAUDE.md "drifted
  `_mask_messages`" note is stale). The pre-agreed resource THRESHOLD is not
  recorded anywhere — reported as an owner decision for G4, not a code gap.
  Evidence: `evidence/reviews/c03-c06-transport-20260928.md`.

`E05 = ACCEPTED_FIX` — a non-dictionary adjectival street name now declines
with the agent's generic word («на улице Зацепской», not «…Зацепская»), while
frozen genitives (Ленина/Комиссарова/Победы) and unknown non-adjectives stay
unchanged. Evidence: `evidence/reviews/e05-declension-recheck-20260928.md`
over `evidence/reviews/e04-e06-loc-independent-20260928.md` (reject).
- `S02 = ACCEPTED_FIX` — the zero-capture archive now reports its denominator
  (`NOT_MEASURED`, `coverage_known=True`, `0/450`) instead of `0/0/0`.
  Evidence: `evidence/reviews/s02-denominator-recheck-20260928.md` over
  `evidence/reviews/s02-capture-independent-20260928.md` (reject).
- `E02 = ACCEPTED_FIX` — a phone the model extended by one digit, in ANY
  position (suffix/prefix/interior), is returned unchanged and flagged residual
  on both out paths, never a real/fake hybrid. The last-10 fallback now fires
  only for 10/11-digit runs. Evidence:
  `evidence/reviews/e02-prefix-insert-recheck-20260928.md` over
  `evidence/reviews/e02-phone-out-full-20260928.md` (reject).
- `E04 = ACCEPTED_FIX` and `E06 = ACCEPTED_NO_CHANGE` — composite LOC never
  becomes fake-street+real-house, same-street addresses keep their own houses,
  an omitted flat is not added back; projections are one object, a new value
  version does not rewrite the old, tenant/conversation are isolated. Evidence:
  `evidence/reviews/e04-e06-loc-independent-20260928.md`.

`M02 = ACCEPTED_FIX` (scorer) after an independent
adversarial review of estimator `m0-actual-out-v14`: a matching surname across
two people stays `ambiguous` (1a/1b), an old vs new value version of one field
stays `ambiguous` with both values visible (2), a 2–3 digit quantity never
attributes to a phone while the full fake in the wrong field is still `residual`
(3), the residual flag is byte-identical with an owner and with a forced
no-owner and is computed by the ownerless reader `_leaf_leak` (4), and a
city-only identity is refused as `unattributed` (5). The denominator is one
shared `candidates` set that includes `ambiguous`/`unattributed`/
`not_identifiable`/`mixed`, with `not_applicable` printed separately (6).
`test_actual_hops` 50/50 and `test_hop_report` PASS. Evidence:
`evidence/reviews/m02-v14-independent-20260928.md`.

`C05 = ACCEPTED_FIX` after an independent
read-only re-check of the index-closure repair: the pinned `Майя Устинова`
literal and the three sibling fixtures (Михаил Жуков / Фёдор Кузнецов / Надежда
Жукова) are 6/6 green, the `declared_keys` property self-test passes and can
fail (941 on the narrow index), cross-word key collisions are 0/309, and
`test_overmasking.py` holds 99.5 % — parity with HEAD, so the widened index did
not buy recall with over-masking. The class is closed over the renderings
`UNITS` declares, not one unit. Evidence:
`evidence/reviews/c05-index-closure-accept-20260928.md` (re-check) over
`evidence/reviews/c05-fold-closure-recheck-20260928.md` (reject + repair).

`E01 = ACCEPTED_FIX` after an independent
3/3 acceptance-clause pass on naturally minted warm two-request PHONE forms in
both directions, stable repeat/cache and marker collision. Codex reran 311/311
echo checks, 16/16 warm hops, tool context, argument form, loop, product, perf
masking and wiki-check. The malformed `+8`/`++` input retains an invalid prefix;
this is assigned to open C02 noise, not claimed as an E01 valid-form pass.
The derived-form flake is now a C05 candidate with a pinned fake, not an E01
regression. Evidence:
`evidence/reviews/e01-current-render-v2-recheck-20260928.md`.
`M04 = ACCEPTED_FIX` after the independent
same-ID corpus mutation and frozen-oracle recheck; `M01 = ACCEPTED_FIX` after
actual-event v7 was checked against the saved 450 events (450 complete triples,
6462 candidates, 3895 attributed, 1184 ambiguous, 712 unattributed, 668
`not_identifiable`). These are measurement repairs, not new engine wins or a
paid rerun. Evidence: `evidence/reviews/m04-digest-recheck-20260927.md` and
`evidence/reviews/m01-m03-actual-event-20260927.md`.

`M02 = ACCEPTED_FIX` (scorer) after an independent adversarial review of
estimator `m0-actual-out-v14`. Earlier independent reviews rejected v9/v10 for a
hidden residual and false generic-city residual. v14 keeps the residual flag
independent of owner choice (`_leaf_leak` is ownerless by signature) and refuses
a city-only identity; on the same 450 saved triples v14 moves two v13 `matched`
rows back to `value_wrong` (value 3668 → 3666 of 6462 candidates, joint
3326 → 3324, attribution 3895 and residual 639 unchanged). The reviewer's six
probe classes — same surname across two people, old vs new value version, short
unrelated number, residual under forced no-owner, city-only identity, and
denominator honesty — all hold; `test_actual_hops` 50/50 and `test_hop_report`
PASS. This is a scorer change, not an engine improvement and not a new
450 result. Evidence: `evidence/reviews/m02-v14-independent-20260928.md`;
earlier `evidence/reviews/m02-leak-side-v9-recheck-20260928.md` and
`evidence/reviews/m02-orthogonal-residual-recheck-20260928.md`.
`M03 = ACCEPTED_FIX` after
independent review of `m03-causal-hops-v2`: an unknown carrier now prevents
optimistic attribution. On the same saved 450, 208 old `attributed` and 98
`ambiguous` emissions move to `not_identifiable`. The old archive has 0/450
`model_trace`, so its answer-from-tool causality remains unmeasured. The local
real GatewayHooks/records forward path passes. Evidence:
`evidence/reviews/m03-unknown-carrier-recheck-20260928.md`. Author DSH spend is
at least $0.189356388 with incomplete accounting; reviewer spend $0.081881112
is complete.

`S01 = ACCEPTED_FIX` after a new conversation-scoped privacy leg protected
the archived dictated PHONE cut and seven independently reproduced refused
call/result bindings. It neutral-redacts without guessing a person's token;
ordinary numbers and a foreign conversation are unchanged. Codex reran
284/284 focused checks, `test_loop`, `test_product`, `test_perf_masking`, and
wiki-check. A bare result with no value previously recorded by the conversation
remains an explicit provenance limit. Evidence:
`evidence/reviews/s01-unbound-privacy-recheck-20260928.md`.

`E01` v1 was rejected for warm PHONE form and marker targeting, then repaired
and accepted as above. `S02 = ACCEPTED_FIX`: old 450 captures are 0/450 and stay
`NOT_MEASURED` — now WITH the denominator the triples journal derives. The
local runner constructs a manifest from case-declared literals, records exact
model-request bytes at delivery, persists capture rows, refuses duplicate and
missing I-arm rows, separates 4 MiB row from 256 MiB run limits, and its report
names measured capture/I/selected counts. The first review rejected the
zero-capture denominator (`0/0/0` instead of `0/450`); the repair folds
`_expected_capture_keys` into the no-capture `NOT_MEASURED` and the re-check
accepted it. Evidence: `evidence/reviews/s02-denominator-recheck-20260928.md`
over `evidence/reviews/s02-capture-independent-20260928.md` and
`evidence/reviews/s02-canary-inventory-20260928.md`.

`E02 = ACCEPTED_FIX`. A known `+7` fake with one agent-added digit — now in ANY
position (suffix, prefix, or interior insertion, and the `8`-prefixed domestic
form) — is returned UNCHANGED on both tool and answer OUT paths and flagged
through `residual_tokens`/`surviving_substitutes`; it never becomes a real/fake
hybrid. The phone last-10 fallback in `_restore_reformatted_spans` now fires
only for 10/11-digit runs (a phone is never 12 digits), and
`_extended_phone_runs` deletes each position of a 12-digit run and checks every
remainder (and its 10-digit tail) against the minted PHONE signatures. The
earlier `test_perf_masking.py` exit 139 after printing PASS did not repeat under
`PYTHONFAULTHANDLER=1`; recorded as a one-off process failure, not an accepted
product result. Evidence: `evidence/reviews/e02-prefix-insert-recheck-20260928.md`
over `evidence/reviews/e02-phone-out-full-20260928.md`.

`C05` has a fixed literal random-mint reproducer: fake `Майя Устинова`, written
as `USTINOVA MAIIA`, restored only the surname before the change. The leased
`йя` alignment/fold tables now recognise `iia`, `jya` and `yya`; all three
written forms restore `BITYUKOVA ZINAIDA`. A separate exhaustive property over
309 fake-pool words and four supported tables found 0 broken align/fold words
and 0 duplicate fold keys. `pseudex.translit`, `test_derived_forms`, the NAME
morphology/case/subject suites, argument form, product, lint and wiki pass.
This is a completed code candidate; see the re-check below for its acceptance.

**C05 independent recheck (2026-09-28): the pinned case is real, the fix was one
unit wide, and the repair is now index closure.** A separate-context reviewer,
read-only on the candidate as found, reproduced the pinned literal against a
clean `HEAD` checkout — the candidate's own test file on the unpatched tree is
**3/3 red**, on the candidate **3/3 green** — and independently reproduced the
claimed 0 colliding fold keys over 309 words, noting that
`pseudex.translit.main()` as committed checked only a word's key set against
itself and would have passed a collision between two different words.

The reviewer then **rejected the candidate as terminal acceptance**, because
`fold` is a substring replacement while `UNITS` declares several spellings per
unit and the two do not close: **142 (word, unit, option) triples** the engine's
own `align` accepts (142/142) that fold to a key nobody held — `е`→`je` (107
words), `х`→`h` (16), `ё`→`io` (8), `ж`→`j` (7), `е`→`ie`/`ye` (2), ICAO `ъ`
(1). Each was reproduced through the real `Vault` + `unmask_arguments` path with
a pinned fake, and in each the **fake given name or surname reached the
customer** beside the real one: `MIHAIL PETROV`, `FIODOR SOKOLOV`,
`NADEJDA EGOROV`, `IVAN PODIEIACHEV`. `residual_of('MIHAIL')` was `None` purely
because the index held `folded('Михаил') = mIXaIl` while `fold('MIHAIL') =
mIhaIl`. The `йя` entries fix one of those six; adding the rest to
`TRANSLIT_FOLD` is impossible, because a bare `j` is both ГОСТ's `й` and the
everyday `ж` and no entry order separates them.

Repair (this session, author = the reviewer, therefore *not* accepted by it):
`translit.declared_keys` returns every fold key the declared renderings produce,
the vault NAME mint indexes that set instead of the single default key, and
`translit.main()` pins the property **over the renderings themselves** — every
spelling `UNITS` allows must align back and be indexed, and no key may have two
owners. Measured cost over the pool: 536 keys against 309, **0 keys shared by
two different fake words**, widest word 256 spellings. The new property fails
with exactly `FAIL (941)` when `declared_keys` is monkeypatched back to the
narrow form, so the instrument can fail. Red→green: the three pinned `Майя`
literals and three new sibling fixtures are 6/6 red on `HEAD` and 6/6 green
after the repair; the ICAO `ъ` case moves `IVAN PODIEIACHEV` → `IVAN SOKOLOV`.
Nearest guards all EXIT 0: derived forms, NAME morphology, argument form,
collisions, loop, product, perf masking (with `PYTHONFAULTHANDLER=1`, no exit
139), and over-masking **99.5 % observed, identical to `HEAD`**.
Negative controls (`MIHAIL PETROV`, `MIHAILOV`, `JUKOVA`, `MIHAIL IVANOV`,
`SOKOLOV PETROV`) all return no owner. Evidence:
`evidence/reviews/c05-fold-closure-recheck-20260928.md`.

C05 is now **ACCEPTED_FIX** after the independent re-check described in
the checkpoint above; the class (derived-form index closure over the renderings
`UNITS` declares) is closed, not one unit. Evidence:
`evidence/reviews/c05-index-closure-accept-20260928.md`.

**Execution mode (owner directive, 2026-09-28):** `deepseek-first` is deprecated
and must not be used — no new DSH sessions, no paid ledger tasks, and the stale
`workflow-dsh-dispatcher-repair-20260928` reservation is left as-is rather than
touched through the deprecated plugin. The autonomous `workflow` tool is also
not used. Independent review and implementation are done with subagents
(separate contexts), the Lead integrating results and updating PROGRESS.

**E03 repair (this session, three attempts, re-check #3 in flight).** The
subject/object disambiguation after a 3rd-person finite verb was first tried on
the PRE-VERBAL noun and failed twice: the noun cannot tell subject from object
(«система»/«оператор»/«сервис» are subjects, «заказ»/«посылку» are objects, and
syncretic-accusative nouns are ambiguous). The third repair moved to the NAME's
own morphology: `governing_cases(text, start, surface)` takes the name span and
decides via `_oblique_object_case(surface) = (detect_gender(surface) != "femn")`
— a feminine name is the nominative subject, a masculine/undetermined name is
the object, and `read_person` still reads a declined feminine name («Громову
Марину») as accusative. `detect_all.py` passes `s.value`. Evidence (rejects):
`evidence/reviews/e03-name-subject-object-independent-20260928.md`,
`evidence/reviews/e03-subject-object-recheck-20260928.md`,
`evidence/reviews/e03-subject-object-recheck2-20260928.md`.

**C01 = REJECT (coverage) and C02 = REJECT (real defect), this session.**
Evidence: `evidence/reviews/c01-c02-coverage-20260928.md`.
- C01: `test_other_hop_forms.py` is green (82/82) but has ZERO cross-type
  examples, only generic negatives, and never asserts the fake's checksum (the
  pinned fakes are checksum-VALID). Engine behaviour behind the gaps is correct.
- C02: the malformed `+8`/`++` PHONE on the agent→tool restore leg produced a
  real/fake hybrid (`+89795553322 → +89162148803`, `++79795553322 →
  ++79162148803`). REPAIRED: `_malformed_phone_sign` now refuses to splice under
  a `+8` or `++` sign in all three restore passes (verbatim, token, reformatted);
  pinned in `test_spoken_identifier_form.py` (120/120). Spoken EMAIL/PLATE
  reconstruction is now pinned too (G4, 124/124). The zero-width Unicode leak
  (G3) is left as a DOCUMENTED LIMIT: `normalize` maps zero-width chars to a
  space to keep the 1:1 offset invariant, so a ZWSP inside a dictated numeral
  word («два\u200bдцать») splits it and the spoken phone is not detected; fixing
  it would break the load-bearing length-preservation invariant, so it is
  recorded rather than "fixed".

**E05 = ACCEPTED_FIX** — see the checkpoint above; the repair (guessed `ADJF`
declension + `_is_genitive` known-gate) passed its independent re-check.


The autonomous DSH workflow was stopped after its M02 gate repeated authors
without starting a reviewer. The owner then instructed Codex to author the
remaining code directly; the current execution contract reflects that change.
No new DSH task or paid 450 run has started. Main, merge and deploy remain
untouched.

## Earlier checkpoint — M04 accepted, S01 repair rejected by task ceiling

Formal acceptance: **1/19** (`M04 = ACCEPTED_FIX`). The independent M04 recheck
reproduced the original same-ID corpus mutation and verified that `m04-frozen-3`
changes the digest when scored corpus content changes. Saved-hop totals and
printed axes agree; the complete saved nano counts remain unchanged. The frozen
scorer caught eight deliberately wrong gateways, including passthrough, wrong
identity, residual, wrong form and an absent action. Codex reran the frozen,
report, gate and perfect suites. The old nano has 0/69 LOC repair witnesses and
is still labelled unmeasured; this is not a new 450 result. Evidence:
`evidence/reviews/m04-digest-recheck-20260927.md`.

`S01` remains **REJECTED / not accepted**. The first independent review proved a
mixed replayed call leaks a truncated real PHONE when another leaf resolves from
the raw call. The bounded repair leaves a candidate with `test_error_echo_privacy`
254/254, `test_tool_result_context` 13/13 and `test_loop` passing locally, but
the DSH task exceeded its $0.12 ceiling: observed cost is at least
$0.121926624 and `accountingComplete=false`. The execution contract treats the
package as rejected; no independent recheck has accepted this code. New paid DSH
work is paused pending the owner's decision on incomplete accounting. Main,
merge, deploy and the paid 450 remain untouched.

## Resume checkpoint — 2026-09-27, DeepSeek-first plugin

The owner explicitly resumed the 19-item sprint. The global plugin is enabled
and its seven hook trust records are present; hook execution in this already-open
chat was not independently observed. The worktree and original run artifacts
remain separate from main. No paid task, live benchmark, merge or deploy was
started at this checkpoint.

Fresh offline checks on the current candidate: `test_shown_form_ambiguity.py`
**39/39**, `test_error_echo_privacy.py` **238/238**,
`test_tool_result_context.py` **13/13**, `bench.agentpii5.test_harness_stream`
**PASS**, `bench.agentpii5.test_payload_canary_integration` **PASS**, and
`test_product.py` **PASS** from an isolated writable temporary cwd, and
`wiki/check.py` **0 findings**. The earlier S01 RED and harness-stream RED below
are historical observations, not the current local state. These checks do not
by themselves establish full S01 or 19/19 acceptance, nor a new live-450 gain.
The first `test_product.py` attempt could not open its relative test database
under this chat's read-only worktree permissions; the isolated rerun passed.

Both last DSH tasks are idle. `hop-sprint-conflict-implementation-20260927`
reports $0.131418912 with complete accounting. The separate
`hop-sprint-remaining-evidence-20260927` still reports a **lower bound** of
$0.251535048, `accountingComplete=false`, against its $0.25 task ceiling.
Therefore no new paid delegation until that uncertainty is resolved or the
owner explicitly accepts proceeding with it. The sprint budget has not been
silently reset. A compact mission graph is recorded in the global plugin state;
all 19 requirement IDs remain subject to the acceptance matrix.

Owner GO for the expanded [pre-450 plan](../../docs/plan-hop-form-before-450.md): 2026-09-27. Implementation has started in worktree `Obscura-hop-audit`; no merge, deployment or paid live benchmark authorized. New sprint DeepSeek budget: $10, at most two active agents, no children. The table below records the preceding M0/S0/F1 pass, not completion of this sprint.

| Stage | Target | Before | After | Interpretation |
|---|---|---|---|---|
| M0 cohort | Exactly 450 complete triples, no overlapping retries; preserve all spend | Old summary used 457 observations | 450 complete C/C2/I triples; A314+B9+C124+D3; 4 configuration groups; 15 tests PASS | Correct accounting, not engine improvement |
| M0 actual tool crossings | No scheduled-turn requirement; attribution before restoration; explicit ambiguous/unattributed denominators | Legacy declared OUT: 301/1736; 1348 absent | `m0-actual-out-v4`: 11565 leaves, 6462 candidates; 27 tests PASS | Additive diagnostic; M0 pipeline/paired/answer work is NOT complete |
| S0 error echo | Protect the known sensitive fragment in a real tool error without masking unrelated quantities | `long_support-013` error fragment remains clear | 12/13 checks PASS, archived truncated echo still RED | Protection not implemented; call-scoped provenance decision pending |
| F1 PHONE | Agent-selected digits/prefix/grouping on both tool and answer legs | 13/24 exact value+form; 3 ordinary-quantity controls pass | 24/24 plus 7/7 additional controls; quantity controls unchanged | Local deterministic regression set, not full v5 percentage |

The F1 initial command is `PYTHONDONTWRITEBYTECODE=1 /private/tmp/agentpii5-connectors-venv/bin/python test_phone_hop_form.py` from the worktree's prototype directory. It exits 1: six answer-form failures on written input, plus five failures on spoken input. The fake phone is pinned. These are three source forms × four agent forms × two consumers, not 24 independent statistical cases.

Engine acceptance keeps value, form and residual separate; joint success requires all three. Privacy coverage and wrong-identity/overmask regressions may not be traded for a larger form percentage. Old reports remain immutable. C₀↔C₁ versus I↔C₀ behavioural comparison remains separate from actual-hop mechanical scoring.

The expanded pre-450 plan includes NAME/LOC, the other v5 types and full-loop checks before rerunning the quarter; their implementation is not reported as done here. Live nano/quarter and production rollout remain separate GO boundaries. A published stage result must name the estimator version, population and exclusions so a measuring change cannot be sold as an engine improvement.

## Current checkpoint — independent acceptance of delegated conflict fix

The next offline check, `python -m bench.agentpii5.test_harness_stream`, exits
**1** on the current candidate. No provider was called: this module uses
scripted replies and simulated connection failures; its printed `$0.0030`
is fixture usage, not a new paid run. The conversation-view check masks 108
messages, demonstrates 83 losses through the unscoped negative and 18 tool
differences, but four copied messages return dictated PHONEs as digits
(`chain-003`, `chain-018`, `chain-030`, `chain-041`). Reading the assertion and
`spoken.digits_in_words_like` identifies the open IN rendering/round-trip
class, not evidence that `GatewayV5.vault` lost its conversation scope.
Unsupported numeral layouts still fall back to a numeric presentation.

The corpus streaming check reports **83/350** chunked/whole disagreements on
this random-mint run yet passes: it proves the harness scores what the client
read, not that the engine's two transports agree. That PASS must NOT close
C03's parity requirement. Preserve this distinction when constructing the
remaining renderer/streaming acceptance tests; no existing assertion was
weakened and no engine change was made on this probe alone.

Follow-up offline verification regenerated the gitignored synthetic sets and
ran `eval_detect.py` / `eval_dirty.py` with the pinned interpreter: **298/298**
and **150/150**, both recall and precision 100%, hard-negative false masks
**0/12**, exit 0. These internal corpora do not replace external precision or
the remaining full-loop acceptance. DSH status re-read confirms all six
sessions from the last two tasks idle; the inventory accounting is still
incomplete, so paid delegation remains paused.

Root triage of the already-paid inventory rejected its S02 allegation that
`ToolResultRecord.spans_real` comes from the detector. `GatewayV5.push_call`
in `prototype/bench/agentpii5/harness.py` builds those spans from
`CallLog.result_spans` (mock item tags), and stores detector-derived `pieces`
separately. Reading `_in_tool` alone had misidentified their provenance.
No observer rewrite or denominator change is justified by that allegation.
Independent payload canaries remain required; rejecting the allegation does
not close S02. M04's distinct lazy dependency is confirmed by source:
v4 taxonomy imports v3 `classify_break`, whose `_street_repaired` imports
`pseudex.address.register_spelling`. Isolating the v5 oracle is still open;
v3/v4 were not edited. The inventory is provisional, not accepted wholesale.

DeepSeek implemented the rewrite veto and added positive PHONE and NAME
controls. Root acceptance found two unacceptable choices: swallowing every
canonicalization exception, and exempting composite LOC from the conflict
veto to avoid a partial-restoration regression. Two literal whole-address
controls reproduced the latter: **35/37 RED**. Neither choice was accepted.

The common boundary now selects non-overlapping replacement ranges first,
then keeps a conflicting range unchanged instead of falling through to
smaller parts. Errors propagate explicitly. The same focused suite is
**37/37 GREEN**, and LOC remains **76/76 GREEN**. This is the narrow conflict
class only; arbitrary projections, inactive expiry and S01 remain open.
The first broad regression (`/private/tmp/hop-sprint-conflict-final-tests`)
was **18/19**, failing the existing same-address/two-spellings control.
The owner comparison now normalizes LOC as detection already does; a Latin
homoglyph retained for display is not another address identity. That test
then passed, and the conflicting-address controls stayed **37/37**. The final
frozen run (`/private/tmp/hop-sprint-conflict-accepted-tests/summary.json`)
is **19/19**, no timeout, zero watched-file drift. Test lint, wiki validation
and diff whitespace checks passed. No expectations or metric denominators
were relaxed to close the regression.

Delegation control incident: the read-only inventory task spawned four children
despite its explicit no-children instruction. Root interrupted all five sessions;
`list_dsh_agents` confirmed each idle. Its observed cost is **at least
$0.251535048**, accounting **incomplete**, above its $0.25 task ceiling. No
complete inventory report was accepted. The separate implementation was also
interrupted before further paid work; its terminal accounting is complete at
**$0.131418912**. All fifteen tasks therefore have an observed cumulative lower
bound of **$1.822634688**, NOT a fully reconciled total. No new paid assignments
until accounting is reconciled or the owner explicitly decides otherwise.
An attempted steer was denied by auto-review on that budget condition; it was
not bypassed. Local root acceptance and offline tests used no model API calls.

No live 450 rerun, main-tree write, merge, deployment or completion claim.

## Prior checkpoint — shown-owner conflicts, delegated implementation

The focused shown-form suite exposed last-writer ownership: **5/12 RED →
12/12 GREEN**, then 18 controls passed including two independent database
connections and reopening. The accompanying 19-script regression at
`/private/tmp/hop-sprint-shown-conflict-tests` passed **19/19**, zero watched-file
drift. This was before the subsequent counterexamples and is not final acceptance.

Root reproduced a false conflict between case/yo variants of the same NAME:
**19/20 RED → 20/20 GREEN** after reusing `fold_key` for the NAME identity
comparison. Independent review then found a real bypass: reformatting a
conflicting PHONE surface selects the minted token owner. Six new assertions
on the text, residual and tool legs leave the expanded suite **22/28 RED**.
That bypass is delegated for bounded implementation, not waived.

The review also identified active-replay expiry: an ignored insertion followed
by a sweep could remove the row before its owner lookup. An external-clock
test reproduced the RuntimeError; moving the sweep after the active row's
refresh passed that control in the 22/28 run. This does **not** change the
existing one-day retention policy or prove indefinite ambiguity persistence.
Expired, inactive evidence and its interaction with token ownership remain
an explicit acceptance question, not a lifetime guarantee.

Thirteen completed DeepSeek sessions reconcile to **$1.439680728**, accounting
complete. Two new sessions are running with a combined **$0.50 cap**: narrow
conflict implementation (owns redact/test only) and a read-only inventory of
all 19 acceptance clauses. Pending usage is not counted as zero. Root owns
architecture and independently checks their results; no additional parallel
agents, paid benchmark, main edit or rollout is authorized.

S01 still has **14/15 RED**: the context reader is not yet wired into masking.
This checkpoint closes neither S01 nor E06, and none of these local counts
is a measured improvement of the live 450.

## Prior checkpoint — spoken hesitations and call association (partial S01)

The independent code review is terminal and reconciled: **$0.124187556**,
accounting complete. Twelve idle sprint sessions total **$1.306017408** of
the $10 ceiling. No paid benchmark has been launched.

The review correctly identified that the SNILS exact-copy test did not prove
restoration of a rewritten spoken substitute. New public swap tests now cover
that path, real leading zeroes, a ten-digit national PHONE and an inter-group
hesitation. This expanded matrix was **42/44 RED** on the preceding candidate
(both hesitation OUT legs returned digits), then **44/44 GREEN**. The renderer
now carries existing filler words between numeral groups without changing
their position. Internal fillers inside a changed multi-word group still
return an unsupported layout; this limitation is not waived. The 19-script
regression at `/private/tmp/hop-sprint-spoken-fillers-tests` passed 19/19 with
zero watched-file drift, before the call-context reader was added.

S01 now has a pure shared-envelope association reader, `tool_result_contexts`,
with **12/12** protocol controls. It uses only a unique preceding assistant
call ID, distinguishes missing/ambiguous/invalid evidence, handles parallel
same-name calls and reversed result order, and never imports future or other
transcript evidence. Raw arguments remain raw; no lookup, restoration, global
state, cache or new required client field is introduced. This reader is NOT
yet consumed by `mask_messages`: typed echo projection and the v5 gateway/
observer integration still need implementation. The privacy reproducer is
therefore still **14/15 RED**, not a closed S01.
After adding the reader, `test_product.py` passed again, the privacy fixture
confirmed that same single red, test lint reported zero problems and the wiki
checker reported zero findings. The MAP copy was regenerated with `--sync`.

Other review findings are bounded: repeated assertions across different input
registrations are not independent statistical cases; the 36/36 headline was
always a fixture count. The private group speller's over-three-digit input is
unreachable through the current public grammar; no unrelated guard patch was
made. Performance, domestic-prefix remasking and full residual mutation
coverage remain hypotheses/acceptance work, not proven defects or passes.

Next: consume exact call evidence in typed echo protection and v5 observation;
close remaining speech layouts and M03/M04, then all full-loop gates. The
19-requirement completion criterion is unchanged.

## Prior checkpoint — spoken identifiers, not S01 acceptance

The same `test_spoken_identifier_form.py` runs **3/36 on the pristine pre-sprint
archive** and **36/36 on the current candidate**. This comparison is against
the sprint baseline, not just the preceding LOC checkpoint. It covers spoken
PHONE groups, individual digits, uppercase, both OUT consumers, repeat masking,
residual diagnostics and a fixed SNILS leading-zero copy. It does not cover
every numeric type or every speech layout.

The renderer uses the existing numeral grammar and indexed typed identities.
It rejects a proposed spelling whose readback changes the target digit string.
Exact copied spoken forms use the recorded original, because a zero-padded
substitute can split one original group into several spoken groups. This fixed
a real broad-suite regression; the expectation was not weakened. The fixture
setup in `test_phone_hop_form.py` and `test_error_echo_privacy.py` now reads
the substitute's identity rather than requiring its presentation to be digits.

The frozen local regression at `/private/tmp/hop-sprint-spoken-final-tests`
passes **19/19**, zero per-test hash drift. Focused test: **36/36**; LOC:
**76/76**; test lint and wiki: zero findings. Regenerated golden **298/298**,
dirty **150/150**, hard negatives **0/12** false masks. Full external
quality/performance acceptance remains pending.

**Still RED:** `test_error_echo_privacy.py` is now **14/15**, specifically the
archived truncated echo in a reconstructed standard call/result transcript.
The two additional controls pin input immutability and preservation of the
explicitly synthetic ID; the privacy canary is unchanged.
`bench.agentpii5.test_harness_stream` also remains red: the real
gateway scope test still finds a spoken source returned as digits. Its random
negative fixture initially failed to distinguish broken chunking; it now tests
both correct and carry-less readers on one-character chunks, so the negative
does not depend on where a random mint falls in a larger chunk. That focused
instrument check passes; it does not close the separate scope failure. Some minted
group combinations cannot be rendered with the current greedy grammar; fillers
and transfer of changed numeral typos are not closed. None of these is waived.

S01 investigation established an additional harness dependency: v4's inherited
`note_tool_call` omits `tool_calls[].id`, and `push_tool` omits `tool_call_id`;
v5 inherits both. The dossier has call `seq` and written/restored arguments,
not recovered provider IDs. The `_push` double-pass observer also has no
call context. Automatic production call/result protection therefore needs a
v5 adapter/observer integration check, not just an envelope patch. See the
current addendum in `s0-reproduction.md`. No call-context engine change yet.

A self-contained DeepSeek numeral review used no files/tools or archived
traces. Its zero-dropping and lowercase-only assumptions were checked against
the real parser and rejected: `сто ноль` reads `1000`, `сто ноль пять` reads
`10005`, `ШЕСТЬСОТ два` reads `602`. Boundary-merging concerns were confirmed;
the new renderer refuses the tested identity-changing layout. This is narrow
language review, not independent code acceptance. Cost **$0.022967352**;
eleven reconciled idle sessions total **$1.181829852**, accounting complete.
The earlier proposed archive investigation was blocked before starting and
was not sent. The separate code-only review of three approved engine/test files
has completed under task `hop-sprint-spoken-code-review-20260927`, cap $0.30;
its cost and verified follow-up are in the current checkpoint above. No paid benchmark, commit, push,
main edit or deployment.

Next: S01 protocol-faithful call/result evidence and masking, the remaining
spoken-layout cases, then M03/M04 and full-loop gates. All 19 requirements
remain binding; this checkpoint is not sprint completion.

## Prior checkpoint — LOC role projection and conflict control

This is local engine evidence, not a replay or a new live result on the 450.
The original benchmark artifacts remain untouched. All 19 sprint requirements
are still required; a green focused suite does not close a whole requirement.

- E04/E05: the original adversarial matrix moved from HEAD **44/64** to
  **63/64**. CAPS city parsing, streetless projection and role-cued numbers
  now work on both text and tool-string paths. The remaining assertion wrongly
  demanded zero residual for a mention combining two different addresses.
- That assertion was replaced with stronger, explicit ambiguity checks: the
  whole conflicting mention must remain unchanged on both legs, with residual
  diagnostics present. The revised suite passed **66/66**. It is not valid to
  subtract 44 from 66 as an improvement on an unchanged denominator.
- Independent review confirmed that adjudication and found two new defects:
  a category/initial `Д` interpreted as a house cue, and a house number used
  under a flat cue borrowing the real flat. Ten literal controls made the suite
  **69/76** before the fix and **76/76** afterwards. Numeric identity now needs
  the requested role; bare `д` needs a field/delimiter boundary or preposition.
  Evidence: `/private/tmp/hop-sprint-loc-role-red.log` and
  `/private/tmp/hop-sprint-loc-role-after.log`.
- E03/C05: NAME subject/object suite **18/18**, separate pinned case-observer
  checks **85** pass. One broad-suite complaint was an ambiguous, gender-blind
  observer; a separate real OUT genitive defect was fixed using the resolved
  real person's gender. These are different findings, not a relaxed engine
  expectation.
- C01: spoken DOB grammatical form **4/7 -> 7/7**; the existing product spoken
  birth-date check also passes. General arbitrary speech/noise remains open.
- M01/M03: explicit response/call chronology is serialized for future runs.
  Actual-OUT **v7** report at `/private/tmp/hop-sprint-m03-v7-20260927` has
  450 complete triples, 6462 candidate leaves, 3895 attributed, 1184 ambiguous,
  712 unattributed and **668 not_identifiable**. This is measurement uncertainty,
  not 668 newly discovered engine failures. Answer/chain acceptance remains open.
- Literal address evidence is in `address-pattern-evidence.md`. It distinguishes
  sender reformulation from generated-marker inconsistency; the four inspected
  cases do not establish a real user correction history merely because the
  agent wrote "corrected". No per-case street/name exceptions were added.
- S01 owner direction: derive call/result association automatically from existing
  transcript `tool_calls[].id` / `tool_call_id`, within conversation scope.
  No new required field or manual host integration. Implementation and privacy
  acceptance are still pending; no guessing when evidence is absent.

Regression evidence is revision-specific: the first independent 19-script run
straddled changes and is not acceptance. The next frozen run at
`/private/tmp/hop-sprint-loc-freeze-tests` passed 19/19 before the two new cue/role
fixes. The current rerun at `/private/tmp/hop-sprint-loc-role-freeze-tests`
also passes **19/19**, with **zero per-test hash drift**. The root agent checked
the child exit codes in `summary.json`; no engine edits occurred during this
run. Test lint and wiki checker both report zero findings after the fixes.
External full measurements and complete-loop gates remain pending.

Vault design research is retained in `wiki/STATE.md` D-072 as a hypothesis.
No storage engine replacement, migration, production deployment or paid
benchmark generation has been performed.

## Sprint implementation checkpoint — 2026-09-27 (not final acceptance)

### Acceptance ledger at the earlier checkpoint (before M04 acceptance)

At this earlier checkpoint no row had met the execution contract's terminal evidence standard;
**formal acceptance was 0/19**. The current count is in the latest checkpoint above. `candidate` means a local implementation or
fixture exists but the full row's negatives, production path and independent
review have not all been signed off. The exact requirements remain in
`docs/plan-hop-form-before-450.md`; this table records only the next missing
piece so an agent does not equate a passing script with closing a row.

| ID | State | Next evidence before acceptance |
|---|---|---|
| M01 | candidate | Actual-event attribution across moved/repeated calls; full-loop and no-future-data negative |
| M02 | candidate | Whole/part, same surname, value version and unrelated short-number controls on saved and new paths |
| M03 | candidate | Separate user/first-result/later-result causality, `not_identifiable`, and answer/chain aggregates |
| M04 | candidate | One scored saved-hop population, frozen oracle/axis agreement, can-fail mutants and independent review |
| S01 | RED | Replayed real tool-call arguments: three new assertions fail (243/246); model-visible call provenance, same-call positives and foreign-call negatives |
| S02 | open | Classify all saved privacy misses with independent payload canaries and unaffected neighbours |
| E01 | candidate | Current mention's form through both entry points, tool-result replay, cache/conversation controls |
| E02 | candidate | PHONE IN/OUT shared contract on tool and answer paths plus independent review |
| E03 | candidate | Fixed random mint/seed, gender/case/partial-name matrix and original control cases |
| E04 | candidate | Composite LOC without real/fake hybrid, two-address ambiguity and omitted-apartment negative |
| E05 | candidate | LOC prose/tool/summary/template use one projection and preserve case/order/selected parts |
| E06 | candidate | Same-object projections, changed value version, foreign tenant/conversation negatives |
| E07 | open | Real A→B tool edges, retries, corrections, memory, two entities and all four boundaries |
| C01 | candidate | All ten v5 types, cross-type negatives, checksum and real-value preservation |
| C02 | candidate | Supported spoken/noise/Unicode transformation registry and explicit unknowns |
| C03 | open | Nested JSON, string/number scalars, escaping, chunk/choice parity and partial failure |
| C04 | open | Literal quote/marker versus entity mention; summary/template and ambiguity policy |
| C05 | candidate | Reproducible mint/seed failure on base and candidate, not a lucky green rerun |
| C06 | open | Production endpoints, persistence, tenant scope, cache, isolation and measured resource threshold |

Two DeepSeek writers are now operating from the exact `Obscura-hop-audit`
root on disjoint files: `hop-replayed-call-impl-20260927` (S01/E01) and
`hop-report-population-impl-20260927` (M04). Their output is candidate only;
Codex and a different reviewer must inspect it before moving any row to
terminal acceptance. Neither is a new 450 run.

All edits remain in `Obscura-hop-audit`. No new benchmark generations, main writes,
deployment, commit or push. Original A/B/C/D artifacts are unchanged.

| Work item | Before → candidate | Evidence and remaining qualification |
|---|---|---|
| M02 whole/declared-part identity | 27 original tests + 3 new tests pass; diagnostic ambiguity 2162 → 1363 | `actual_hops` v5 only, same 450 saved outcomes, `/private/tmp/hop-sprint-m02-v5-20260927`; independent review found no wrong-identity credit. Not an engine improvement. Superseded for temporal attribution by v6 below. |
| M01 response timing | New same-turn parallel-call fixture RED → GREEN; 31 checks pass | v6 no longer assumes that sequential execution proves separate model responses. Missing timing is `not_identifiable`. Forward recording is in progress; no full pipeline certification. |
| E01 current IN form + C01 atomic types | 47/66 → 66/66 | Seven non-PHONE types, literal expectations, real vault; current mention's format is separate from stored identity. |
| E02 PHONE | 24/24 + 11/11 controls | Adds repeated-IN notation controls to prior OUT fix. |
| E03 NAME subject/object | Original six-example matrix 8/12 → 12/12; independent attack found three reproducible regressions in broader matrix; revised rule 16/16 | Finite verbs allow both subject and governed object readings. Initial blanket governor suppression was rejected. Further family coverage still open. |
| C02 numeric look-alikes | 16/20 → 20/20 adversarial checks | An O representing a known zero resolves; replacing a minted two with O is a changed number, not evidence of identity. Unknown full numbers stay unknown instead of becoming real/fake hybrids. |
| C01 date/email details | Extended adversarial suite 21/24 → 24/24 | Month case, second-IN zero padding, and independent email local/domain case. |

The first DeepSeek C01 test version was rejected because it encoded current bugs
as expected outputs. The NAME review's stub-asset conclusion was also rejected;
the real-bundle recheck reproduced the subject fix and exposed real object
regressions. In the atomic review, the hybrid-number finding was accepted, but
its proposed restoration of a changed numeric identity was rejected. Its PLATE
probe initially sent the restored real value instead of the fake; corrected
before acceptance. Agent assertions are evidence to verify, not acceptance.

Quick regressions passed after the shared renderer and NAME refinement:
PHONE, seven other types, atomic adversarial, argument forms, derived forms,
collisions, loop, product and names morphology. The later date/email refinements
still require the same broad recheck. Golden 298/298 and dirty 150/150 with 0/12
false masks matched HEAD before those refinements. NEREL before/first-candidate
PERSON 1764/1908 and Cyrillic 1713/1835 matched; final-candidate external battery
is pending. PII-Bench could not start in the connector venv (missing pyarrow);
this is NOT a passed quality gate.

M03 confirmed a second archive limitation: final `reply_raw` is the last nonempty
reply, not necessarily the last event. Neither result availability nor unique
disclosure proves why the model chose a value. Old chain/answer rates cannot be
relabeled as causal product performance. Explicit model-response recording is
being implemented and reviewed without changing historical metric formulas.

S01 remains RED pending the owner's call-scoped provenance decision. LOC,
whole-loop acceptance, full error-payload coverage, random-mint failures and
performance acceptance remain open; this checkpoint does not close the sprint.

### New sprint delegation accounting

| DeepSeek task | Cumulative estimate USD | Accounting |
|---|---:|---|
| `hop-sprint-m03-inspect-20260927` | 0.153352152 | complete |
| `hop-sprint-c01-fixtures-20260927` | 0.152155668 | complete |
| `hop-sprint-name-review-20260927` | 0.075492420 | complete at latest recorded snapshot |
| `hop-sprint-atomic-review-20260927` | 0.079406400 | complete |
| `hop-sprint-response-trace-20260927` | 0.156272496 | complete |
| `hop-sprint-loc-repro-20260927` | 0.089270892 | complete |
| `hop-sprint-name-random-20260927` | 0.092926032 | complete |
| `hop-sprint-loc-attack-20260927` | 0.217192428 | complete; latest cumulative continuation snapshot |
| `hop-sprint-loc-patterns-20260927` | 0.110602020 | complete |
| `hop-sprint-regression-snapshot-20260927` | 0.032191992 | complete |
| `hop-sprint-numeral-grammar-20260927` | 0.022967352 | complete; self-contained arithmetic, no tools |
| `hop-sprint-spoken-code-review-20260927` | 0.124187556 | complete; code-only read-only review |

Twelve reconciled sessions total **$1.306017408** (provider-token price estimate, not an
invoice); all are idle and all accounting snapshots are complete. Reservations
are ceilings, not spent money. Keep
the latest cumulative snapshot per session; never sum continuation snapshots.
Sprint ceiling remains $10 and at most two active agents. This accounting is
separate from the earlier research sessions below and any future live run.

## Saved-run targets before this sprint

The saved-run [M0 report](evidence/m0/summary.md) is the OLD engine under the new
estimator, not a replay through F1. Its PHONE slice has 1928 attributable leaves:
value 1916/1928 (99.38%), form 1570/1928 (81.43%), residual present 2/1928
(0.10%, lower is better), joint 1568/1928 (81.33%). Seven `unmasked_known`
events get no protected-value credit; standalone form is never joint success.
No after-F1 percentage on these 450 exists yet. Fresh dialogue behaviour must
be measured by a new C/C2/I run, not by relabelling these outcomes.

Before acceptance, direct reading exposed two bugs in the additive estimator:
short unrelated numbers were attributed to phones, and a dictated real phone
was called a wrong identity instead of the right identity in a wrong form.
Both have red-before/green-after fixtures. Versions v2/v3 are superseded by v4;
the interim 80.49% PHONE joint headline is withdrawn. Old `metrics.py` and
`observe.py` remain unchanged; their completed-only numbers remain reproducible.

For other types this is still a diagnostic, not a certified acceptance baseline:
2162 ambiguous and 712 unattributed events remain overall. Whole/part records
can describe one entity while carrying different canonical values; role-less
NAME/LOC matching still inherits the old needle layer. IN, answer, chain and
paired behavioural scoring are not repaired by the new OUT reader. Do not
interpret its all-types 43.05% joint lower bound as measured engine accuracy.

## Engine change and regressions

F1 keeps the existing renderer and indexed vault lookups. The lookup now retains
the entity type; PHONE canonicalization supplies the real digits, while the
current sender supplies notation on all three restoration paths (literal,
token and reformatted), both tool and answer. No schema, licensing or detector
change. Two historical PHONE assertions were intentionally updated: prose is
no longer forced back into the user's older `8 …` or `+7 …` layout.

- PASS: PHONE 24+7 controls, collisions, product/streaming, core loop; cohort,
  actual OUT, report CLI and existing report/observer/metrics tests; test lint.
- **Not a green full engine battery:** the first broad `test_argument_form`
  run had one NAME case failure; `test_derived_forms` had two transliteration
  failures. Fresh baseline runs passed. A fixed 12-seed, 36-outcome comparison
  of those paths was byte-identical before/after, all passed. This supports
  random-mint sensitivity, but does not reproduce or close the original failures.
  They are an explicit pre-merge verification item; no NAME expectations were
  relaxed to make F1 pass.
- **Known RED:** `test_error_echo_privacy.py`, 12/13. F1 avoids the observed
  wrong-form trigger but does not protect arbitrary truncated error echoes.

Local latency probe (1000 measured calls/leg after 200 warmups; one process per
snapshot, no concurrent load): tool p50/p95/p99 before 0.101/0.132/0.198 ms,
after 0.103/0.124/0.135 ms; answer before 0.066/0.075/0.080 ms, after
0.074/0.092/0.100 ms. This is a small diagnostic, **not** a production latency
gate or a statistically established speed improvement. No per-token full-vault
scan or extra database lookup was introduced.

## Next boundary and budget

The current order and completion gates are maintained in the
[pre-450 matrix](../../docs/plan-hop-form-before-450.md). It supersedes the
earlier PHONE-first stopping point; this file records measured results only.

Three bounded DeepSeek Flash sessions were used for implementation/review, no
nested agents. Recorded estimates for this stage: cohort $0.201343344, events
$0.336363216, S0 plus F1 review $0.205763412; sum approximately $0.74347.
Two sessions report incomplete accounting, so this is not an exact invoice or
a guaranteed total. Paid benchmark generation spend in this stage: **zero**.
No commit, push, merge or deployment was performed.
