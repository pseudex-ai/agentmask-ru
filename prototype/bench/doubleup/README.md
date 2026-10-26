# Doubleup local forensic corpus intake

This package is a **local-only, read-only Langfuse intake**, not an agent harness.
It makes no provider calls, generates no responses, runs no detector, and mutates
no remote environment. `/recorded` validates stored evidence and emits counts;
it makes **no causal claim about what an agent would have done behind Pseudex**.
Paid model smoke and all production/dev changes are outside this package.

## Commands

From this worktree's `prototype/` directory, with Python and `cryptography`:

```sh
python3 -m unittest bench.doubleup.test_intake -v
python3 -m bench.doubleup probe
python3 -m bench.doubleup inventory --run-id inventory-example
python3 -m bench.doubleup export --inventory inventory-example --limit 200 --run-id export-example
python3 -m bench.doubleup /recorded --source export-example --run-id recorded-example
python3 -m bench.doubleup verify --source export-example
```

Run IDs are exclusive: retries use a NEW ID; never overwrite a partial/finished
run. A failed run without an authenticated manifest is **incomplete**, not usable.
`--end` can pin the inventory endpoint within the last day. The start is exactly
30 days before it; both API timestamp boundaries are inclusive. No fixed tenant,
project ID or historical date is embedded in code. Export refuses stale inventory.
`--max-pages` defaults to 5,000 and reaching it is an error, never success.

## Private storage boundary

All artifact writes are confined to `bench/doubleup/.pilot-state/`, including
when the caller supplies a run ID. There is deliberately no arbitrary `--out`.
Symlink paths, non-private directories, non-owner files and hardlinked evidence
are refused. Directories are 0700; the persistent AES-256-GCM key is 0600;
completed artifacts/manifests are 0400 and exclusively created with fsync.
The key is `.pilot-state/corpus.key`, **outside the run directories**. Preserve
it privately: losing it loses access. Never print it or pass it in argv.

**Archive only `.pilot-state/runs/<run-id>/`, never `.pilot-state/` or the key.**
The entire state directory is gitignored. Source-only archives must exclude all
ignored pilot state (including test scratch directories). This is an owner-only
local pilot, not KMS/HSM, cryptographic deletion, or WORM against root/the owner.
The key authenticates a second encrypted manifest; SHA256 checks alone would not
protect against an attacker replacing a manifest and all of its hashes.

Encrypted source and corpus payloads contain **original, un-anonymized content**,
including original tool args/results/schemas and any embedded secrets already in
traces. No scrubber, masking, redaction or substitute is applied. Parsed JSON is
serialized canonically; string content/types are unchanged. HTTP response byte
hash receipts and parsed-source hashes record both wire and object provenance.
No plaintext originals are written, printed, or included in source tests/docs.
Manifests and CLI output contain counts, safe status labels and hashes only;
source identifiers and JSON-pointer provenance are encrypted. Do not paste a
ciphertext's decrypted content into a handoff.

Credentials are read privately from `~/.config/2up/langfuse.env` (0600, owner-only).
The dotenv parser supports named Langfuse keys and `pk`/`sk` variants, without
shell sourcing. It refuses conflicting aliases. Keys never enter artifacts/logs.
Only `https://langfuse.inf.2up.dev` is allowed, with verified TLS; redirects and
environment proxy forwarding are disabled. Every request is a GET to an exact
public inventory endpoint. HTTP retries are bounded (4 attempts, 45s timeout,
capped backoff); bodies and raw exception text are never logged.

## What completeness means

* Inventory exhausts paginated trace metadata in the fixed last-30-day window.
  It checks timestamps, unique IDs, stable server totals and exact row counts.
  Cursor variants are also supported. Missing totals on a legacy page API,
  total drift, duplicates, ignored filters and page caps fail closed.
* Sampling covers up to 200 **whole session groups**, balancing available tenant,
  agent and explicit tool-metadata strata, rare strata first, deterministic ties.
  Unknown tool metadata remains its own stratum. A trace name is only a labeled
  agent proxy, not a confirmed assistant ID. Missing fields are not fabricated.
* Selected `sessionId`s are re-enumerated **without time limits** so earlier/later
  traces of each visible dialog are not silently dropped at the window edge.
  Every trace detail is fetched and observations are independently paginated;
  both embedded V2 observations and typed V3 variants remain in source evidence.
* Missing session IDs use explicit metadata dialog IDs (tenant-scoped) when
  present; otherwise they are unscoped traces. Their manifest completeness is
  **false / window-only**, not a claim of a whole historical session.
* API visibility is not all-time retention: deleted/inaccessible traces cannot
  be proven, and live reads are **not a transactional point-in-time snapshot**.
  These limitations are explicit in every export manifest.

Tenant attribution uses actual `org_id` / `billing_tenant_id` and explicit
organization metadata, including nested JSON-string LiteLLM metadata. **`userId`
is never automatically a tenant**: backend uses a user, gateway can use a tenant.
Conflicting tenant evidence is ambiguous; absence is unknown. Neither is guessed.

## Normalization and validation

Raw sources are never deduplicated away. Derived message arrays collapse exact
repeated snapshots and prefix-only growth, with every source pointer retained.
Branches stay separate; identical text at two dialog positions remains two
occurrences. No agent response is invented to join inputs and outputs.

Exact declared OpenAI/Anthropic/MCP-style tool schemas are preserved when present;
no schema is inferred from arguments. Args and results link only by actual call
ID **within a dialog**. Conflicting calls/results sharing an ID are ambiguous.
Typed tool spans with no call ID, missing results, absent schemas and orphan
results are counted explicitly. Provenance includes trace/observation source
JSON pointers and hashes. The raw encrypted source is authoritative for any
unrecognized serialization variant; normalized coverage is not invented.

The split assigns whole dialog groups deterministically to floor(80%)/remaining
20%; no trace/dialog is shared across train and holdout. This is an intentionally
stratified **pilot**, not an unbiased estimate of production prevalence. `/recorded`
checks authenticated files, normalized hashes, split isolation, duplicate trace
IDs and recomputed counts. It does not label PII ground truth, score detection,
execute tools, or measure causal quality.

Tests use stdlib `unittest`/`mock` and invented in-memory fixtures only. They
exercise the actual CLI path with mocked HTTP, pagination/refusal cases, nested
attribution, source preservation, tool-link ambiguity, growing snapshots,
private write bounds, persistent keys, GCM authentication and tamper detection.

Only code in this package changes. The engine, deployment, root instructions,
wiki and external repositories are deliberately untouched under this task's
explicit scope exception to the general wiki-update convention.
