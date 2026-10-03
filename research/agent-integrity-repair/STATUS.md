# Agent-hop integrity repair — status

Branch `fix/agent-hop-integrity`, worktree `/Users/igor/Projects/Obscura-agent-integrity`, base a810bf85fbb7f6fe5e12c73323ff42a0d8cc38bf. Prod and `main` untouched. Original stopped run untouched (hashes verified).

## Completed and pinned

| Class | Fix | Proof |
|---|---|---|
| House/flat digits rewritten into IDs, counts, list indices, phone prefix | numeric LOC literals restored only under role evidence; resolved-whole-token protection for cued numbers | test_hop_integrity numeric + phone + abbreviations |
| Full address collapsed to its city | exact generic-type-slot family lookup instead of arbitrary prefix range | test_hop_integrity city_family |
| W8 compositional missing-city projection minted a new core | conversation-scoped core owner reuse with full-head part namespace | test_hop_integrity projection + scope + ambiguity |
| Operational date next to a person typed DOB | JSON string-value/path evidence isolation; birth-key arrays and in-leaf birth cues preserved | test_hop_integrity dates + json offsets |
| Markdown field label captured into NAME | delimiter belongs to key; shared label grammar; next-label boundary | test_hop_integrity markdown + adjacent |
| Box weight swallowed into address | full spoken weight units in leased measure_after | test_hop_integrity quantity |
| NAME fragment consumed a trailing clock | place-only candidate cannot resolve as NAME; type provenance carried | test_hop_integrity name/time; deterministic seed2 |
| Complete Latin name lost to a colliding single token (ERSHOV ISO) | bound-identity whole-name precedence over contained token | test_hop_integrity coherent latin |
| Three-part Latin name restored mixed-script | Latin candidate windows 1–4 words | test_hop_integrity full translit |
| Ordinary word «по» restored to a whole person via initials index | NAME fragment requires all source words to align to fake parts | test_hop_integrity initials |
| Masked card `HEAD **** TAIL` left fake head | card mask resolves head (start) and tail (end) with unique-owner guard | test_hop_integrity card head/tail |
| Harness erased partial operations on error (calls=[]) | `_partial_run_v5` preserves calls/state/results/mentions/chronology | test_harness_stream partial_history |

## Measured, no regression

- 17-suite legacy battery: 0 failures (baseline and every after-* run).
- 21 cross-hop integrity checks: green.
- eval_dirty: 150/150 correct, 0/12 hard-negative false masks, 0/150 true leaks.
- eval_detect golden: unchanged vs baseline (DATE 12 labels typed DOB — a pre-existing golden/type-taxonomy mismatch present identically in a810bf8; not a privacy leak, not yet re-labelled).
- PII-Bench: ADDRESS 95.5%, NAME 99.1%, PASSPORT 90.0%, total «по закону» 89.1%.
- NEREL PERSON Cyrillic 93.4%.

## Reading coverage

All 419 recorded triples have BOTH primary packets and canary supplements read to EOF; zero gaps, zero parse errors. Lead reconciliation of conflicting reviewer verdicts is not yet final; reading completeness is.

## Open, with honest classification

1. **Streaming vs whole-text restoration** — real, customer-visible; the benchmark already counts it (`stream_mismatch`). A correct fix makes chunked restoration not depend on text after the emit window. Deep change; NOT yet implemented (no risky half-fix). Reproduction available: a chunked reply can leave a fake flat standing while the whole reply resolves it.
2. **Mint-side cross-script collision prevention** — restoration side is fixed (wrong values no longer reach the tool); preventing the mint from producing cross-script subword collisions requires constraining a finite name pool further and risks pool-exhaustion 5xx. Documented, not yet changed.
3. **Computation on fictitious data (age from DOB, decisions on impossible card prefixes)** — cannot be solved by string restoration. Needs an owner decision on the semantic contract: which derived/branch-relevant facts the gateway must supply in trustworthy form, versus which the model may not compute on fakes. [ROOT-CAUSE-008]; no code change until decided.
4. **Spoken card Luhn-invalid in the run** — NOT an engine mint defect: the minted fake is Luhn-valid (verified: 0886 5667 4349 9062 -> True). The invalid `0099…` was the model mis-transcribing the dictated fake; reversing digit substitution would violate the no-fuzzy-numerals invariant. Fail-closed and residual reporting already apply.
5. **Pre-existing benchmark failures unrelated to this scope** — `test_harness.only_harness_imports_pseudex` (detect_sweep imports the engine) and `test_connectors` (3 errors: ConnectorError re-raised as transient) fail identically on a810bf8. Not introduced here; noted.

## Final validation — BLOCKED on credential

Owner requires a new LIVE deepseek-flash C/C′/I run on the same recorded cases with before/after business comparison. The harness and corpus are verified runnable in this worktree (`build --check` passes, digest reproducible, dry-run path works). **`DEEPSEEK_API_KEY` is absent in the environment**, so the paid run cannot start. No new key is committed or logged; the owner must provide it through the normal secret path. Until then the live before/after cannot be produced and scope is not declared closed.

## Not claimed

- No «production-ready», no «all future bugs impossible».
- Streaming, mint-pool and semantic contract remain explicitly open.
- Offline tests are preconditions, not the owner-required live acceptance.
