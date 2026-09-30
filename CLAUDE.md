# CLAUDE.md

This file guides Claude Code in this repository. **The agent wiki is the source
of truth for how the code is laid out and why; this file carries the commands,
the architecture prose, and the few load-bearing invariants, and embeds the map.**

## The agent wiki (`wiki/`) — read this before working

| file | what it gives you |
|---|---|
| [`wiki/MAP.md`](wiki/MAP.md) | where every module, test, benchmark, doc and deploy file lives, who calls it, which test pins it. Embedded below under **Repository map**. |
| [`wiki/FLOWS.md`](wiki/FLOWS.md) | how a request, a lease, a store and a build move through the code, step by step, with the real function names. |
| [`wiki/INVARIANTS.md`](wiki/INVARIANTS.md) | the 192 rules a change must not break, grouped by module, each with the test that holds it. The six "Rules that changes must not break" sections that used to live in this file are there now. |
| [`wiki/STATE.md`](wiki/STATE.md) | every decision, the alternative rejected and the price — the `D-NNN` log. Supersedes `docs/decisions.md`. |
| [`wiki/INDEX.md`](wiki/INDEX.md) | what each file in `docs/` and `research/` answers, and its status. |

**Keeping the wiki honest.** Do not edit the **Repository map** block below by
hand — edit `wiki/MAP.md` and run `python3 wiki/check.py --sync`. `wiki/check.py`
verifies that every path the wiki names exists, that the map matches the real
import graph, that every FLOWS symbol is real, that every invariant names a test
that exists, and that this file's embedded copy equals `wiki/MAP.md`; it runs in
CI (`.github/workflows/checks.yml`). After changing `check.py` itself, run
`python3 wiki/check.py --selftest` (it breaks the wiki in known ways and demands
a red for each). When you add a module, a test, a benchmark, a doc, a deploy
file, a rule or a decision, add its row to the wiki in the same change.

## What this is

Pseudex is a **reversible PII-tokenization gateway for LLM agents** on the RU market (152-ФЗ).
Real personal data is replaced with format-preserving fake tokens before the model sees it, and
detokenized server-side so the agent's **tool calls still execute on real values**. The tool-call
loop is the product — plain text masking is table stakes.

Everything shippable lives in `prototype/`. `docs/` is the product spec (RU), `research/` is the
evidence archive behind every design decision (why a layer exists, what SOTA does).

**The engine ships EMPTY.** `prototype/pseudex/` contains the rules; the tuned data those rules
consume (gazetteers, street vocabulary, cue words, priority table) lives in `prototype/licensing/`,
never ships, and is leased to the running container as an encrypted bundle that exists only in
memory. `docs/tz-license-packaging.md` is the spec for that; `docs/spec.md` §2 is the product
decision behind it.


## Commands

All commands run from `prototype/` with the venv active. Deps are **not** stdlib-only (even
`test_loop.py` needs `phonenumbers`):

```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

There is **no pytest and no test runner** — each test/eval is a script with a `main()`.

**Every script that detects anything must load a bundle first.** `testkit.load_dev_bundle()` builds
one from `licensing/pack.py` and loads it in-process; without it the detector raises
`BundleNotLeased` by design. That helper is a development path only and has no equivalent in the
shipped image.

```bash
python3 test_loop.py           # core proof: no PII to model + tool-call round-trip (no LLM, no network)
python3 test_product.py        # tenancy, audit, streaming detok
python3 vault_test.py          # canonicalization + persistence across restart
python3 test_perf_masking.py   # cache/audit-dedup/leak-regression/loop-responsiveness vs the real FastAPI app
python3 test_localui.py        # operator surface is closed, reveals audited, requests billed apart from entities
python3 test_persona_defects.py  # the five defects a persona run found and no corpus of ours did
python3 test_preflight.py      # how many workers fit, and what happens when they do not
python3 test_pseudexctl.py     # the ops CLI: command shapes, doctor verdicts, the rekey proof, upgrade
python3 test_schema.py         # the volume's schema contract: numbered, snapshotted, refused from the future
python3 test_localui_renders.py  # the interface in a REAL browser (needs playwright + chromium):
                                 # a 200 and a matching CSP header are not evidence it executed
python3 test_collisions.py     # подмена, совпавшая с настоящим значением: обе половины
python3 test_derived_forms.py  # транслит и инициалы в аргументе: в конвенции модели, разговор решает
```

Detection quality (needs generated datasets — all gitignored, regenerate before use):

```bash
python3 make_dataset.py && python3 eval_detect.py      # golden set: per-type recall/precision
python3 make_dirty.py   && python3 eval_dirty.py       # dirty set: + F2, FP/FN dump, hard-negative false-mask rate
python3 make_stress.py                                 # adversarial set (built to break the detector)
python3 make_holdout.py                                # hold-out benchmark
python3 make_addr_real.py addr_s11.json 11             # address benchmark on a FRESH seed
```

Performance:

```bash
python3 bench_masking.py       # O(n^2) growing-transcript cost, cache on vs off
python3 profile_latency.py     # part1 offline per-message cost; part2 real A/B (needs PSEUDEX_UPSTREAM_KEY)
```

Licensing and packaging (`docs/tz-license-packaging.md`). The gates are the definition of done —
they run against real containers, never against mocks:

```bash
python3 -m licensing.pack --out /tmp/bundle.bin   # build the detection bundle
python3 -m licensing.devserver                    # the real licensing server, :8443 + admin :9443

python3 e2e/gates.py                              # L1-L22 (+L2b), licensing, vault, preflight, ~15 min
python3 e2e/gates.py --only L4,L5                 # a subset while iterating
python3 make_dirty.py                             # P3 compares the two images on it; without
                                                  # it pack_gates refuses BEFORE the Nuitka build
python3 e2e/pack_gates.py                         # P1-P10, packaging (builds both images)

# ONE key is compiled into the release binary: the Ed25519 verification key. A
# fresh one forces a full Nuitka rebuild. The tuning is NOT compiled in — it
# travels in the lease (docs/tz-tuning-in-lease.md), so there is no tuning key to
# match. Pass the signing value an image was built with to reuse it with --skip-build:
PSEUDEX_SIGNING_KEY=<base64> python3 e2e/gates.py --image pseudex:compiled --skip-build
PSEUDEX_SIGNING_KEY=<base64> python3 e2e/pack_gates.py --skip-build
```

Two images, and the difference is only HOW the engine is built — `Dockerfile`
runs it from `.py`, `Dockerfile.nuitka` compiles it to a native binary. Both are
pinned to the same Debian release: a Nuitka binary links against the build
stage's glibc, so a runtime on an older one will not start.

**The threat model is narrower than it looks** (`docs/tz-license-packaging.md`
§3.4): the customer MAY see the leased bundle — that is accepted — and MUST NOT
see the source. So confidential computing is out (it protects the wrong thing and
needs hardware the market does not have), and the bar is commercial desktop
software: native code, no `uncompyle6`-shaped one-command path back.

Docstrings are stripped BEFORE Nuitka by `build_strip_docstrings.py`.
`--python-flag=no_docstrings` is not enough on its own — it stops `__doc__` being
set but leaves the literals in the constants blob, where `grep -a` finds them.
In this repo the docstrings are the design record, so they are the part most
worth withholding.

Run the two deployment shapes:

```bash
# A) OpenAI-compatible reverse proxy (we call the provider)
export PSEUDEX_UPSTREAM_BASE_URL=https://openrouter.ai/api/v1 PSEUDEX_UPSTREAM_KEY=sk-...
uvicorn pseudex.proxy:app --port 4000
python3 issue_key.py acme https://openrouter.ai/api/v1 sk-...   # mint a real tenant key

# B) Sidecar behind a host gateway (the host calls the provider)
PSEUDEX_DB_DIR=/tmp/pseudex uvicorn pseudex.service:app --port 8000
docker build -t pseudex:latest . && docker run -p 8000:8000 -v pseudex-data:/data pseudex:latest
```

Scripts needing a live LLM (`agent_demo.py`, `response_test.py`, `live_eval.py`) expect the proxy
running on `localhost:4000` with a seeded `pseudex-dev` tenant.


## Release and versions

The full specification is `docs/tz-release-and-versions.md` (D-051…D-064 in
`wiki/STATE.md`); this section is what an agent must not get wrong. **The
number lies when the artifact did not change** — `0.3.12` and `0.3.13` were
one image under two tags — and everything below exists to make that impossible.

### Two streams from one repository (D-051)

| stream | paths | tag | artifacts | who consumes |
|---|---|---|---|---|
| **engine** | `prototype/` minus `licensing/`, `bench/`, `e2e/` — exactly the `COPY` lines of `prototype/Dockerfile.nuitka` (`deploy/shipped_paths.sh` derives the set) | `vX.Y.Z` | `pseudex` (source + compiled), aliases `X.Y.Z`, `X.Y`, `X`, `latest` | the customer, by `docker run` |
| **platform** | `prototype/licensing/`, `storefront/`, `deploy/` (linked versions, one tag) | `platform/vX.Y.Z` | `pseudex-licensing`, `-storefront`, `-backup`, `-supportbot` | our host, by `deploy/agent.sh` (follows `platform/v*` only) |

A commit is attributed to a stream by the FILES it touches; `release-please`
opens one Release PR per stream on `main`. **The engine is versioned only when
the engine changed**, held by three layers: release-please's `exclude-paths`,
`deploy/lint_engine_commits.sh` in `checks.yml` (a visible-type commit that
touches `prototype/` and nothing shipped is red), and the publish job in
`release.yml` (red when the shipped set is unchanged since the previous tag of
the same cycle). There is no root package `"."` in `release-please-config.json`
— it would receive every commit.

### Release = merge of the Release PR (D-052)

Nobody creates a tag by hand. `release-please.yml` opens/updates the Release
PR on every push (changelog, `version.txt`, manifest); **merging it is the
owner's «go»** — the `tag` job waits for green checks, creates the tag and
GitHub Release, and dispatches `release.yml` on the tag explicitly (a tag
pushed with `GITHUB_TOKEN` never triggers `tags:`). Manual fallback:
`docs/operations.md` §6.

Commit types decide the number (pre-1.0):

| type | effect | note |
|---|---|---|
| `feat`, `fix`, `security`, `perf`, `build`, `revert` | patch | visible in the changelog |
| `chore`, `ci`, `docs`, `refactor`, `test`, `research`, `bench` | nothing | hidden; `chore(registry)` is what the engine publish job commits |
| footer `Release-As: X.(Y+1).0` | **new minor = new support cycle** | a conscious act: adds a `schema_lock.json` line, opens `release/X.Y` |

### One version source (D-053)

`prototype/version.txt` — baked into `pseudex/_release.py` next to the
verification key, read by `pseudex/license.py`, sent in every lease, shown by
`/status`, the UI and `pseudexctl doctor`. Never a constant in code again.

### The versions registry (D-054, D-056, D-061)

`deploy/releases.json`, endoflife.date shape: `cycles[]` newest first with
`state` (`current` / `maintenance` / `eol`), `eoas`, `eol`, `eol_announced`,
`latest{version,date,digest}`, `aliases`; `notices[]`. Rules an agent must obey:

- **Written by the pipeline** (`python3 -m licensing.registry record` in the
  engine publish job → commit `chore(registry): pseudex X.Y.Z` in `main`).
  By hand only `eol`, `eol_announced`, `notices` — through a PR.
- **Additive, always**: a recorded version never changes digest, `latest` never
  walks back, a cycle is never removed (`checks.yml` validates against the
  previous file). `eol` needs `eol_announced ≤ today` and `eol ≥ announced +
  90 d`; the server refuses to ENFORCE a late `eol` (`registry.check` says
  «late», not 426).
- **The dates decide, the `state` label lags**: a `maintenance` cycle whose
  `eol` has passed is closed (`registry.effective_state`), the file stays
  valid, and the next `record` writes the label. A version the registry has
  not recorded yet (published minutes ago) is judged as the NEWEST cycle;
  `1.0.0` (every pre-D-053 image) as the oldest.
- The site advertises `pseudex:X.Y` of the newest cycle
  (`storefront_web/engine_release.py`), never a hand-set tag.
- It reaches the licensing server through the platform release: `deploy/agent.sh`
  syncs `origin/main:deploy/releases.json` every tick, accepted only after
  `cosign verify` of the newest digest, into `deploy/.registry/` (`docs/operations.md` §2bis).

### What the container learns, and when (D-055, D-056, D-063, D-064)

The lease response carries a signed `version` block (`running_latest`, `latest`,
`latest_in_cycle`, `min_supported`, `deprecated_at` as `@unix`, `sunset_at` as
HTTP-date, `notice`), `bundle_format`, `lease_contract`. The client ladder:
INFO «есть новее» once per version → WARN on every renewal after
`deprecated_at` + banner in the UI + `pseudexctl doctor` → **426
`unsupported_client` only past an `eol` announced ≥ 90 days ahead**, a verdict
outside grace like 402/403. Silence from the server is «неизвестно» on every
screen, never «новейшая». A `bundle_format` above `SUPPORTED_BUNDLE_FORMAT` is
`bundle_format_unsupported` («обновите движок»), not `bundle_corrupt`.

### The volume's schema (D-058, D-059, D-060)

Every store carries `application_id` and `user_version`; steps are numbered
in `vault.VAULT_MIGRATIONS`, `audit.AUDIT_MIGRATIONS`, `tenants.TENANTS_MIGRATIONS`
and run by `pseudex/schema.py::ensure`. `PSEUDEX_ROLE=migrate` runs once
before the fan-out (snapshot `<store>.pre-<from>-<to>.db` by `VACUUM INTO`
under the same key, then steps, then stamp); `probe` exits 2 on a volume a
newer image wrote → container exit 6, untouched; no room for the snapshot →
exit 5 before anything is touched. **The contract of the number:** a patch
keeps `user_version` (rollback within a minor is free); a minor may raise it,
one way. `prototype/schema_lock.json` pins the maximum per minor — **adding a
migration step under a pinned minor is red in `test_schema.py`; open a minor
(`Release-As`) and add its line.**

### Support window and `release/X.Y` (D-057)

A minor is `current` until the next minor ships, then `maintenance` for six
months (security only), then `eol` announced ≥ 90 days ahead (`registry.record`
sets these dates on the day the next minor is recorded). Branch `release/X.Y`
is created from the last tag of the cycle when the next minor opens. **Only
`security:` commits that touch the image go there**, by cherry-pick:
`.github/workflows/backport.yml` opens a backport PR into every live
`release/*` when a PR with such a commit merges into `main` — the WHOLE PR is
cherry-picked, so **a security fix of the engine is its own PR**, never mixed
with other work; a direct push needs `git switch release/X.Y && git
cherry-pick -x <sha> && git push`. release-please on the branch uses
`release-please-config.release.json` (the `prototype` package only — the
platform is released from `main` alone) and produces `X.Y.Z+1`; `release.yml`
reads aliases from `origin/main`'s registry and moves `X.Y` only — never
`latest`. Ordinary `fix:` commits are NOT backported.

### The customer's upgrade (D-062)

`pseudexctl upgrade [--to X.Y]`, shipped in both images at `/app/pseudexctl`:
pull → probe with the NEW image before anything stops → stop → archive →
rename → run with the same name/ports/mounts/env (`--env-file` 0600, secrets
never in argv) → `/health`; unhealthy → the old image's probe decides between
an automatic rollback and the printed `restore` command. Compose users:
`docker compose pull && up -d`.

### Commands

```bash
python3 test_schema.py                                  # the schema contract and the lock
python3 -m licensing.test_registry                      # the registry's promises
python3 -m licensing.registry validate [--previous OLD] ../deploy/releases.json   # from prototype/
python3 -m licensing.registry record --version X.Y.Z --digest sha256:… --date YYYY-MM-DD ../deploy/releases.json
sh deploy/test_agent.sh                                 # the deploy agent without docker
sh deploy/lint_engine_commits.sh main..HEAD             # engine commits typed honestly
pseudexctl --dry-run upgrade --to 0.4                   # the plan, nothing executed
npx release-please release-pr --dry-run --repo-url … --config-file release-please-config.json --manifest-file .release-please-manifest.json
```

**Exit codes of the container** (`entrypoint.sh`): 3 volume does not open with
the key · 4 preflight (memory) · 5 schema not brought forward (space) · 6
volume newer than the image, untouched · 1 licence.


## Architecture

### Two entry points, one core

`pseudex/proxy.py` and `pseudex/service.py` are **parallel deployment shapes**, not layers:

| | `proxy.py` | `service.py` (sidecar) |
|---|---|---|
| Who calls the provider | Pseudex | the host gateway (e.g. Diva's LiteLLM callback) |
| Auth / tenancy | `sk-ps-…` key → `Tenants` → upstream URL+key | `org_id` in the request body |
| Surface | `POST /v1/chat/completions`, `GET /usage` | `/mask`, `/unmask`, `/spans`, `/reveal`, `/usage` |
| Conversation scope | derived from the transcript | `conversation_id` in the body, else derived |
| Streaming | yes (`StreamDetokenizer`; tool-call requests buffered) | yes — `/unmask_chunk` for `delta.content`, `/unmask_arguments` for tool calls |

Both wrap the same core: `detect_all` → `vault` → `redact` → `audit`. Their `_mask_messages`
implementations are **duplicated on purpose but have drifted** — `service.py` handles multi-part
content blocks, `skip_system`, the mask cache, and the threadpool offload; `proxy.py` does not.
When you change masking semantics, decide explicitly whether both need it.

### Two surfaces on the sidecar, with different auth

`service.py` serves two audiences and they are gated differently on purpose:

| | gateway surface | operator surface (`pseudex/operator.py`) |
|---|---|---|
| Paths | `/mask`, `/unmask`, `/unmask_chunk`, `/spans`, `/health` | `/status`, `/events`, `/stats`, `/stats.csv`, `/reveals`, `/subscription`, `/diagnostics`, `/selfcheck`, `/reveal`, `/metrics` |
| Auth | `Authorization: Bearer $PSEUDEX_GATEWAY_TOKEN` | `Authorization: Bearer $PSEUDEX_ADMIN_TOKEN` |
| Why | a cheap credential the customer's gateway holds; it is NOT the admin one, so a compromised gateway config cannot reveal values | these disclose real values and the list of what exists to disclose |

Both tokens are **generated per process when the environment does not set them**, which is safe for a
single worker and wrong for N — see the `PSEUDEX_ADMIN_TOKEN` note below, which applies to both.
Test harnesses must read the token off `pseudex.service` rather than restating it: a copied constant
is a second value that has to stay equal to the first, and `test_perf_masking.py` failing with 401
is what that drift looks like from the outside.

`PSEUDEX_ADMIN_TOKEN` **must be set by `entrypoint.sh`, once, for all workers.** Each worker
generating its own would mean N valid tokens for one SO_REUSEPORT port, and the interface would
401 at random as the kernel moved it between workers.

### The local interface (`pseudex/localui/`)

A separate ASGI app on **:8081**, started by `entrypoint.sh` as the same binary under
`PSEUDEX_ROLE=ui`. It is a separate process so it can report "движок не отвечает" — a UI inside
the thing that is down cannot. It never imports `pseudex.service` and never leases.

- Sign-in: a startup token printed with a URL, Jupyter-style, reusable for the process lifetime.
  `PSEUDEX_UI_PASSWORD` for a shared team. Generated in `entrypoint.sh` so a UI restart does not
  invalidate the link the operator already followed.
- The session token rides in the **Authorization header, never a cookie** — a cookie would make
  `/reveal` reachable by CSRF, and then a CSRF token would be needed to defend a mechanism chosen
  for convenience.
- The engine proxy is an **allowlist of exact paths**, not a prefix match: it holds a credential
  the page does not, so a pass-through would be an open relay into the container's network.
- Page files ship at `/app/ui` in the release image, **never under a directory called `pseudex`** —
  gate P1 asserts `/app/pseudex` does not exist as evidence the Python package did not ship.
- Rendering uses vendored Preact+htm (no build step). Not a style preference: every screen renders
  values from the customer's own traffic, and string-concatenated `innerHTML` would execute markup
  arriving inside a name or a preview, in a page holding a session that can reveal personal data.

### The lease (`licensing/` → `pseudex/assets.py`)

```
licensing/assets_source.py   the authored data: gazetteers, street type stems, cue words,
                             priority table, key->type map, look-alike table. NEVER SHIPS.
licensing/data/              the bulk dictionaries: 197k names, 165k ГАР street names
licensing/fetch_gar.py       rebuilds the street vocabulary from ГАР (twice-weekly dump)
licensing/pack.py            builds it into zlib(JSON); version = content hash
licensing/server.py          POST /v1/lease -> seals the bundle to ONE process, signs it
pseudex/bundle.py            the wire format, shared by both sides
pseudex/license.py           process keypair, renewal loop, degradation ladder
pseudex/assets.py            in-memory registry; compiles every regex ONCE at load
```

- The worker generates an X25519 keypair **in memory** and the server seals the bundle to it. A
  captured lease is useless elsewhere, and there is no portable form of the bundle to copy off
  the machine. Restart → new keypair → new lease.
- **Encryption and signature answer different questions.** age says who may open it; Ed25519 says
  who made it (age x25519 does not authenticate the sender, and a swapped bundle is a silent leak).
- Ladder: `LEASED` → `STALE` (grace, warns) → `EXPIRED` (assets *unloaded*, `/mask` 503). Grace is
  counted with `time.monotonic()`, so winding the clock back does nothing, and a restart needs a
  fresh lease anyway — there is no persisted expiry to edit.
- **Grace covers OUR outage only.** 402/403 (unpaid, revoked) bypass it entirely.
- Split rule for what is an asset: **EVERYTHING authored travels in the LEASED bundle — the
  semi-public BULK (name lists, ГАР streets — open data) AND the authored TUNING** (cue words, address
  regex, priority table, look-alike folds, key→type map). The engine ships with NEITHER; СНИЛС
  checksums and the detection regexes stay in the binary as ordinary code, because those are the
  algorithm, not the tuned data. The tuning USED to be compiled into the binary as a static-key-sealed
  blob (`_tuning_blob`), and the key rode in every lease — which the red team showed was strictly worse
  (`docs/tz-tuning-in-lease.md`, A2): a memory dump recovered the static key in ~1 s and decrypted the
  blob OFFLINE, forever, past revocation, while a leaseholder read the tuning either way. It now rides
  whole in the lease (`licensing/pack.py::build_plaintext` → `assets.py::load`), inside the bundle the
  server age-seals to the ephemeral process key and nonce-wraps. **WHAT THIS BUYS, STATED HONESTLY:** a
  root leaseholder still sees their ACTIVE lease's tuning in RAM (a theorem — no software closes that on
  any hardware), but there is no compiled blob and no static key, so extraction is one lease window, not
  forever, and revocation works. The licence stays load-bearing and STRONGER: an engine that never
  leased has no tuning at all (nothing to decrypt), not a sealed blob it merely cannot open. Sharpening
  the window further (short TTL, per-customer watermark) is the next step, not this one.

### Detection pipeline (`detect_all.py` is the only place that composes it)

```
normalize()            Layer 0 — 1:1 length-preserving fold (homoglyphs→digits only inside
                       digit-dense runs, dashes/spaces/zero-width). INVARIANT: offsets from
                       the normalized text index straight back into the ORIGINAL text.
  ├ detect_pii         libphonenumber ∪ regex phone/email
  ├ detect_structured  СНИЛС/ИНН/карта/паспорт/дата — checksum-gated (mod 101, INN weights, Luhn)
  ├ _ner_spans         Natasha PER/LOC, gated by names.keep_person / keep_location + context
  ├ detect_address     union of Natasha AddrExtractor + regex anchors + morphology-gated
                       marker-less streets, merged into maximal spans, core-part required
  ├ gazetteer_names    what NER misses: lowercase diminutives, Latin names, initials
  ├ detect_structured_kv  Layer 1 — JSON/form KV where the KEY types the whole VALUE
  └ detect_quasi       DOB in birth context, age ≥ 90, medical terms
context.suppress()     runs BEFORE overlap resolution (order matters — see the comment)
_resolve()             priority-ordered, longest-first, non-overlapping
```

`_PRIORITY` in `detect_all.py` is the arbiter: checksum IDs (6) > phone/email (5) > ADDR (4) >
NAME (3) > DATE/PASSPORT/LOC (2). `ADDR` is an internal type that exists solely to outrank a NAME
sitting inside a street name; it is remapped back to `LOC` after resolution.



### Streaming on the sidecar

The sidecar does not hold the connection — the host gateway does — so streaming
here is a CONTRACT, not a pipe, and it is **per field, never per chunk**:

| field | endpoint | when |
|---|---|---|
| `delta.content` | `/unmask_chunk` | as it streams |
| `delta.tool_calls[].function.arguments` | `/unmask_arguments` | accumulate, then once |

- **Tool arguments may never go through `/unmask_chunk`.** It substitutes flat
  text and a real value is arbitrary text: «ООО "Заря"» put into a JSON string
  by plain replacement injects two bare quotes and the tool call stops parsing.
  On Russian business traffic that is the common case, not an edge one. Pinned
  from both sides in `test_perf_masking.py`, because the tempting simplification
  is to route everything through one endpoint.
- **The tool call is buffered, and that is the trade.** Nothing inside a JSON
  string can be emitted before the string closes — the escaping depends on the
  whole value and a sent prefix cannot be retracted. Correctness over
  smoothness, the same choice the proxy leg made in `_stream_as_single`; the two
  halves of the product disagreeing about it would be worse than either gain.
- **One carry per `choice.index`.** With `n > 1` the deltas interleave on one
  connection and a shared carry splices one answer's tail onto another's head.
- `/unmask_arguments` returns `residual_tokens` like `/unmask` does, and it
  matters more here: a substitute that fails to resolve inside a tool call is a
  fake reaching the tool, and the caller cannot see it any other way — the JSON
  is well-formed and the status is 200.

### The conversation scope (`Vault.for_conversation`, `envelope.conversation_key`)

A partial mention («Ленина 14») may resolve against a fuller one said earlier —
but only inside ONE conversation, and the reason is arithmetic rather than
caution. That street and house exist in every Russian city, so across a tenant's
whole traffic the single-candidate rule finds a dozen owners and refuses every
time: at tenant scope the rule is not careful, it is dead. **The scope is what
makes the rule mean anything and what makes it safe, and one change buys both.**

- `Vault.for_conversation()` hands out a shallow-copied VIEW, never a field on
  the shared object: the vault is built once per org and used from several
  threads, so writing the scope onto it would make one request's scope visible
  to another — the exact cross-conversation link the scope prevents.
- **`content_key` carries the conversation.** Without it the mask cache serves
  the first conversation's link to every later one, and the isolation above is
  decoration.
- `conversation_key(messages)` derives an identity from the first TWO messages
  when the caller names none — one is a system prompt shared by every dialogue
  an agent has. Weaker than a given id and knowingly so; the single-candidate
  rule is what keeps that safe.
- A LINKED row is stored under a conversation-scoped canonical. Written plainly
  it would leak the link past the scope on the very next request. Full addresses
  keep the plain key: one place, one substitute, for ever.
- `place_parts` expires after a day. It grows with CONVERSATIONS, and kept for
  ever it would turn a scope meant to bound a decision into a record of who
  talked when.

### Vault (`vault.py`)

- **Canonicalization**: `+7 999…` / `8 999…` / `89991234567` collapse to one key → one token, so
  the model sees a stable identity across turns. PHONE detokenization preserves that identity
  while rendering the real digits in the current sender's supported notation on both legs;
  see wiki/INVARIANTS.md#swap and D-070 in wiki/STATE.md.
- **Format-preserving, checksum-VALID tokens from impossible ranges**: a fake СНИЛС/ИНН/card is
  deliberately generated to PASS its own checksum (so a checksum-checking agent still calls the
  tool) but from ranges that cannot belong to a person (ИНН region «00», card MII 0, СНИЛС never
  ≤ 001-001-998), and `_unique_token` refuses a mint equal to a value the customer already holds.
  See `research/2026-09-03-checksum-valid-substitutes.md`.
- Persistent SQLite keyed by `(customer, canonical)` — survives restarts and is shared across
  uvicorn workers via the mounted `PSEUDEX_DB_DIR`.
- **Encrypted at rest (SQLCipher), and the driver has no fallback.** One key resolver
  (`vault_key.py`): `PSEUDEX_VAULT_KEY` → `_KEY_FILE` → `_KEY_CMD` (stdout of any command — a
  customer's KMS with no integration on our side) → generated beside the data and announced on
  every start. HKDF-SHA256 gives each store its own key. `PSEUDEX_VAULT_ENCRYPTION=required`
  refuses to start rather than generate one; `off` is plaintext and is what the LICENSING image
  sets, because encrypting it would break `deploy/backup.sh` and the weekly restore drill for
  zero personal data. A plaintext store found on disk is migrated in place by `vault_migrate.py`
  — under `flock`, idempotent by file header, `wal_checkpoint(TRUNCATE)` first because the real
  values live in the `-wal`. `PSEUDEX_ROLE=probe` says which file opens; `PSEUDEX_ROLE=decrypt`
  is the same export backwards; `PSEUDEX_ROLE=rekey` rotates to
  `PSEUDEX_VAULT_KEY_NEW` (a store is atomic, a VOLUME is not — the role names
  which files moved, so a half-rotated volume is legible rather than lost).
- `unmask_text` also does a **digit-signature reindex** so a numeric token the model *reformatted*
  (`+7…` → `8…`, separators stripped) still detokenizes.


## Concurrency and perf model

pymorphy3 holds the GIL during morphology, so **real parallelism comes from processes, not
threads**. `entrypoint.sh` starts N uvicorn workers (default = CPU count, ~350 MB resident each
for the model stack — `PSEUDEX_ROLE=preflight` does that arithmetic against the cgroup
limit BEFORE the fan-out and refuses or lowers N, rather than leaving it to the OOM
killer, whose verdict is status 137 and names neither memory nor us). Inside a worker, `service.py` offloads detection via `anyio.to_thread` under
a `CapacityLimiter` so `/health` stays responsive and bursts queue instead of thrashing cores.

`MaskCache` is per-worker and holds only masked output; the SQLite vault + audit are shared, which
is what keeps tokens consistent across workers. Audit is recorded on the cache **miss** only — the
same value re-sent in a growing transcript is one protected value, not N.

Env knobs: `PSEUDEX_DB_DIR`, `PSEUDEX_WORKERS`, `PSEUDEX_MASK_CONCURRENCY`, `PSEUDEX_MASK_CACHE_SIZE`,
`PSEUDEX_PSEUDONYM_SCOPE` (`conversation` | `customer`; the sidecar also takes `pseudonym_scope` per request),
`PSEUDEX_ADMIN_TOKEN`, `PSEUDEX_GATEWAY_TOKEN`,
`PSEUDEX_WORKER_MB`, `PSEUDEX_HEADROOM_MB`, `PSEUDEX_MEMORY_LIMIT_MB`, `PSEUDEX_UI_PORT`, `PSEUDEX_UI_TOKEN`, `PSEUDEX_UI_PASSWORD`, `PSEUDEX_UI`,
`PSEUDEX_UI_ORG`, `PSEUDEX_UI_STATIC`, `PSEUDEX_ROLE` (`engine` | `proxy` | `ui` | `preflight` | `probe` | `rekey` | `decrypt`),
`PSEUDEX_VAULT_KEY`, `PSEUDEX_VAULT_KEY_FILE`, `PSEUDEX_VAULT_KEY_CMD`, `PSEUDEX_VAULT_KEY_NEW`,
`PSEUDEX_VAULT_ENCRYPTION` (`auto` | `required` | `off`; empty means `auto`),
`PSEUDEX_VAULT_MIGRATION_BACKUP`. (There is no `PSEUDEX_TUNING_KEY` anymore — the
tuning travels in the lease, not a compiled blob; see docs/tz-tuning-in-lease.md.)


## Eval discipline

Datasets are generated, not committed (`*.json` from `make_*.py` are gitignored). Regenerate
before evaluating. `make_stress.py`, `make_holdout.py`, and `make_addr_real.py` were built
**independently of the detector and must not be tuned against** — `make_addr_real.py` takes the
seed as a CLI arg so you validate on fresh seeds. Ground truth labels only real personal data;
`negatives` (track/order/article numbers, a city used as a place reference) must stay unmasked, so
the evals measure over-masking as honestly as recall.

**Our own sets cannot tell you the truth about precision.** They reported 100% while «Счёт 1234 от
15.05.2025» — one of the commonest sentences in Russian business writing — was being masked. They
were not wrong; they contained no ordinary business text, so the failure was invisible to every
metric we had. Three external measurements exist for that reason and none replaces the others:

```bash
python3 test_overmasking.py                                    # clean business text, must be 100%
python3 bench/eval_external_ner.py <NEREL dir> --splits dev,test   # recall on a corpus we did not write
python3 bench/eval_external_precision.py <NEREL dir>               # what we mask that no annotator labelled
python3 bench/agentpii/build.py && python3 bench/agentpii/score.py bench/agentpii/corpus.json
python3 bench/eval_piibench.py                                     # чужой русский корпус ПД в чатовом регистре
python3 bench/eval_noise_ladder.py --dataset dataset.json          # ГДЕ ломается детекция на живом чате
python3 bench/eval_noise_by_type.py dataset.json                   # та же лестница ПО ТИПАМ — кто именно ломается
python3 bench/eval_gar_cut.py                                      # где резать словарь улиц ГАР и чем это платится
```

`bench/eval_noise_by_type.py` существует потому, что одно число на ступень —
среднее по девяти типам, и оно прячет виновника: телефон и СНИЛС держит
контрольная сумма, а LOC падал со 100% до 4% на одной опечатке, потому что улица
искалась точным вхождением. Голые города в нём исключены, как и во второй колонке
общей лестницы.

Корпуса живут в `~/.cache/pseudex-bench/` (не в репозитории и не в `/tmp`, который
чистится при перезагрузке — NEREL терялся так дважды):

```bash
git clone --depth 1 https://github.com/nerel-ds/NEREL.git ~/.cache/pseudex-bench/nerel
curl -L --create-dirs -o ~/.cache/pseudex-bench/pii-bench/data/domain-00000-of-00001.parquet \
  https://huggingface.co/datasets/hivetrace/pii-bench/resolve/main/data/domain-00000-of-00001.parquet
python3 bench/fetch_ru_prose.py --out ~/.cache/pseudex-bench/ru_prose.jsonl --count 220
```

`bench/eval_piibench.py` печатает ДВЕ итоговых строки, и это не уклонение: корпус
размечает КПП и ОГРН как персональные данные, а они идентифицируют ЮРЛИЦО —
Recital 14 выводит его из-под регламента, 152-ФЗ приходит туда же через
определение субъекта как физлица. ОГРНИП остаётся: ИП — физлицо. Три типа несут
`!` и строку с причиной, потому что сырое число послало бы читателя чинить
работающий код: **88 из 92 карт корпуса не проходят Луна** (мы находим ровно
четыре валидных), их `TOKEN` — любая энтропия против наших опубликованных
префиксов, а своего типа CVC у нас нет.

**AN INSTRUMENT THAT CANNOT FAIL IS NOT AN INSTRUMENT, AND v4 COULD NOT FAIL IN
FOUR PLACES AT ONCE.** All four were found by reading the code, not by a number
moving, and each one worked in the gateway's favour:

- **A triple with nothing to compare passed all five levels.** `values_ok` is
  `not any(...)` over an EMPTY list of fields, `level_state` compares zero records
  and says «equal», `level_keys` never enters its loop. `receipt` printed 18/18
  while 12 of those 18 triples made no accepted call at all. `LevelVerdict.comparable`
  names the levels a pair had anything to say about; the rest are `None`, and BOTH
  pairs must be comparable or the effect would move without any arm acting.
- **`FieldSpec.required` stood on 69 specifications and was read by no scorer**, so
  «the control filled the field the tool demands and the gateway arm did not» scored
  as agreement. `absent_required` is outside the whitelist; the optional half of the
  argument still holds.
- **There was no level for «did the arm act at all».** `state` compares the records
  that exist, and when the gateway arm wrote none it compares nothing. Exactly one
  arm was left out of a mutation the other two performed 78 times for I against 48
  for C and 41 for C′ — a floor of 44.5.
- **Over-masking was not measured by anything.** `Case.negatives` was declared, the
  API written, and no family ever called it. Recall without precision is bought by
  one line that masks everything.

**NEITHER McNEMAR NOR A CONFIDENCE INTERVAL CAN PROVE «NO EFFECT».** They answer a
question about a DIFFERENCE, and failing to find one is equally consistent with a
corpus too small to see it. The product's promise is the other claim, so the report
publishes a TOST verdict at δ=3pp — one margin for every level, so none can be
granted a looser promise by a decision made after the numbers were seen. The
interval form is exact rather than approximate and reuses the same cluster
bootstrap, so two lines of one report cannot disagree about the data. Plus a
resolution floor of 1/n: a percentile bootstrap over identical cases returns a
zero-width interval, and zero width certifies ANY margin.

**A CALL THE OTHER ARM NEVER MADE PRODUCES TEN FIELD VERDICTS, AND THE TAXONOMY
TABLE DROWNS IN THEM.** `extra +131` and `absent_required +55` read as «the gateway
writes 131 extra fields»; the truth was thirteen net extra CALLS, counted once per
field of each. Read the call level first, and the field level only for calls both
arms made.

**A BENCHMARK'S OWN CONVENTION IS A FOURTH CONVENTION.** The instrument accepted
three transliteration standards plus one «common» table and scored everything else
against the gateway — while the CONTROL arm wrote «Kuznetsov Dmitry» and «Kuznetsov
Dmitriy» in one run, «Yulia» and «Yuliya», «Maxim» and «Maksim». Widening the
accepted set by SYLLABLE (never by distance — another person's name still matches
nothing) took the value axis from −1.7pp to −0.3pp with McNemar (21,20), p=1.000.
The instrument's habit must be a MODEL's habit, and the same lesson is already
written into the engine's own `translit.align`.

`bench/gate/` is the ceiling of the dictionary gate, and it is the instrument that
found four of the defects above. 600 occurrences of real speech labelled BY HAND
in context, two strata that never add up: of what the gate masks 78.0% must be
masked, of what it rejects 21.3% must be. Three things about it are load-bearing:

- **A word without context cannot be labelled.** The first version was a frequency
  list — «ленина» 36, «капец» 60 — and answers nothing: «ленина» is a street in
  one utterance and a person in another. The gate decides an OCCURRENCE.
- **The sample is pinned to a snapshot, not to the live engine.** It was pinned to
  what the engine does now, so the first fix reshuffled it and 228 of 600 hand
  labels survived — the instrument fell apart from the very improvement it was
  built to measure. The live detector now re-runs on the pinned occurrences and
  the printed line is MOVEMENT.
- **A learned context gate reaches ~10% of the gap on third-party data.** Of 287
  MASSIVE person misses, 72.1% are words not in the dictionary at all — the
  candidate is never born — and 34.4% of the misses are public figures. Excluding
  those, recall is ≥86.2%. Full argument in
  `research/2026-08-31-ml-gate-or-rules.md`.

`bench/agentpii/` is **AgentPII-RU**, built here because the intersection it covers — Russian
conversational PII flowing through tool schemas that consume it — has no benchmark anywhere. Read
its README before changing it. Three things about it are load-bearing:

- **Registers are the point.** `clean` / `chat` / `sloppy` / `voice`. The first run scored 89% and
  every defect it found lived outside the clean register: lower-case addresses (36% recall), a Latin
  letter inside a Cyrillic word, a typo in the cue word, and canonicalisation corrupting surnames.
- **The round-trip axis finds what detection cannot.** «Иванова Мария Львовна» keyed as «Иванов
  Мария» while detection scored 100% on it. Never judge a masking change by recall alone.
- **Ground truth is the canonical form of WHAT WAS WRITTEN.** A chat message with no patronymic must
  not demand one back; that scores the gateway on information the message never carried. Derive it
  from what the generator BUILT, never by searching the finished string — `_canonical_name` matched
  clean parts against the surface by substring, so every part a register had TOUCHED vanished from
  the ground truth («Иванов Петр», е for ё, demanded «Иванов»). 162 of 183 sloppy failures. The same
  bug, twice: the address kept demanding the city three registers deliberately drop.
- **A scorer fallback hides the defect it forgives.** That one was invisible because the round trip
  also accepted "came back as written" — so fixing the ground truth moved nothing, and the leniency
  was ALSO passing «позвоните Игорю» → «Игорю», a declined name in the customer's CRM.
- **An eval must take the production path.** The round trip minted tokens straight from the raw
  corpus value, skipping normalization, and reported ~180 phone breaks that do not exist — through
  `mask_one` a Cyrillic О in a number is folded and the phone comes back dialable. Read the vault
  read-only for the token masking actually minted; do not mint a fresh one.
- **Overlap is not coverage, and the difference is a leak.** «Кзнецов Дмитрий» detected as «Дмитрий»
  scores as recall while the surname reaches the model in the clear. Both numbers are printed, never
  merged: 97.6% recall against 95.0% coverage is 69 partial leaks the single number hid.


## Conventions

- Comments are in English; product docs (`docs/`) are in Russian. Both are unusually dense —
  a comment explains *why the alternative was rejected*, not what the line does. Match that.
- Functional by default; classes only for connectors to external state (`Vault`, `AuditLog`,
  `Tenants`, `MaskCache`, `Detector` — the last one holds the Natasha model).
- `names.py` ships a compact seed name list; production swaps in the full 32k-name dictionaries
  behind the same API.
- `prototype/README.md` status checkboxes are stale (streaming and RU NER are done). Trust the
  code and `docs/how-it-works.md` over it.


## Invariants — the load-bearing few

The full set — 192 rules, each with the test that pins it — is
[`wiki/INVARIANTS.md`](wiki/INVARIANTS.md), grouped by module (detection →
`#names` `#address` `#spoken` `#context`, the swap and vault → `#swap` `#vault`
`#collisions` `#conversation-scope`, the lease → `#lease`, the instruments →
`#instruments`, the business → `#billing`, and the rest). The seven that decide
the most, so they are here too:

- **Fail closed.** Any error in masking propagates to a 5xx; never pass text
  through unmasked. The caller treats an error as a block — that is the whole
  safety story. (`#engine-wide`)
- **No PII pre-filter, ever.** A `maybe_contains_pii` gate silently stopped being
  a superset of the recognizers and leaked raw PII; the content cache removes the
  repeated-work cost, detection always runs. (`#engine-wide`)
- **Never re-feed masked output into detection.** `mask(mask(x)) != mask(x)` — a
  fake phone is a valid phone shape; the cache keys on RAW content. (`#engine-wide`)
- **Keep normalization 1:1.** Any length change breaks every span offset
  downstream, including `/spans`. (`#normalize`)
- **No bundle means no detection, not less.** An empty dictionary is not a
  supported state; `BundleNotLeased`, `/mask` 503. (`#engine-wide`)
- **`pseudex/` never imports from `licensing/`**, and never `import sqlite3` —
  both would defeat the product (leaked assets; silent plaintext). Both
  Dockerfiles fail the build on them. (`#engine-wide`)
- **Fail closed on the lease too:** `LEASED → STALE → EXPIRED`, grace on
  `time.monotonic()` with a wall-clock ceiling; 402/403 bypass grace. (`#lease`)

## Repository map

The map is maintained in `wiki/MAP.md` and copied here by
`python3 wiki/check.py --sync`. Do not edit between the markers by hand.

<!-- wiki:MAP:begin -->
# MAP — where everything lives

The map of the repository for an agent that has to act in it. It answers
**where** a thing is, **what** it is for, **who** calls it, **which test pins
it** and **which document explains it**. How data moves is in [FLOWS.md](FLOWS.md);
what must not be broken is in [INVARIANTS.md](INVARIANTS.md); why a choice was
made is in [STATE.md](STATE.md); what each document in `docs/` and `research/`
answers is in [INDEX.md](INDEX.md); how this wiki is kept current is in
[PROTOCOL.md](PROTOCOL.md).

Paths are relative to the repository root unless a section says otherwise.
`wiki/check.py` verifies that every path named here exists, that every `Uses`
line matches the real import graph, and that the copy embedded in `CLAUDE.md`
equals this file.

**Status vocabulary** (one per entry):

| status | meaning for an agent |
|---|---|
| `live` | current code; change it through the normal path |
| `frozen` | an instrument or reference that must NOT be tuned against the engine — read, run, never "fix" |
| `superseded by X` | kept for history and for numbers cited elsewhere; new work goes to X |
| `drifted` | known to lag behind its sibling; the lag is recorded where the entry says |
| `generated` | produced by a build or a script; never edit by hand |
| `design` | a specification with no implementation yet |

---

## 0. Top level

| path | what it is | ships to customer? | entry points | read first |
|---|---|---|---|---|
| `prototype/pseudex/` | the engine: detection → vault → swap → audit, two HTTP surfaces, lease client | **yes** — as `.py` in `pseudex:source`, as a Nuitka binary in `pseudex:compiled` | `prototype/serve_main.py` via `prototype/entrypoint.sh` | §1, FLOWS.md |
| `prototype/licensing/` | our side: the authored detection assets, the bundle packer, the licensing server and its store | **never** — an import of it from `pseudex/` is a build failure | `python3 -m licensing.devserver`, `python3 -m licensing.pack` | §2 |
| `prototype/*.py`, `prototype/pseudexctl` | entry points, build steps, tests, evals, dataset generators (all flat, no package) | tests/evals never; `pseudexctl` and `serve_main.py` yes | see §3 | §3 |
| `prototype/bench/` | measurement instruments: benchmarks we built, corpora we did not write, paired live runs | never | each script has a `main()` | §4 |
| `prototype/e2e/` | closing gates against REAL containers: licensing (L1–L25), packaging (P1–P11), plus the gate that audits the gates | never | `e2e/gates.py`, `e2e/pack_gates.py` | §5 |
| `prototype/Dockerfile`, `prototype/Dockerfile.nuitka` | the two images; same Debian release, different way of building the engine | — | `docker build` | §3.2 |
| `storefront/` | landing, signup, customer cabinet, operator console, billing, analytics — Django, on OUR hardware; shares no code with the engine | no (runs on our side) | `storefront/manage.py`, `storefront/run_all.py` | §6, `storefront/README.md` |
| `deploy/` | our production host: compose, Caddy, Prometheus/Loki/Grafana, backups, watchdog, systemd timers, support bot | no | `deploy/bootstrap.sh`, `deploy/agent.sh`, `deploy/local.sh` | §7 |
| `.github/workflows/` | CI: checks on push, nightly gates, release on tag, ship, uptime, backup audit | — | — | §7.2 |
| `docs/` | product specification and ТЗ, in Russian, for humans | — | — | INDEX.md |
| `research/` | the evidence archive behind design decisions: deep dives, audits, pentests | — | — | INDEX.md |
| `brand/` | logo, ad images, landing/UI mock-ups (`brand/*.dc.html`), bot avatar | — | `brand/README.md` | §8 |
| `e2e-personas/` | persona runs against a LIVE model (OpenRouter), the harness and their findings | never | `e2e-personas/harness.py` | §8 |
| `wiki/` | this wiki | never | `wiki/check.py` | PROTOCOL.md |
| `.claude/` | Claude Code settings, skills, agent worktrees (worktrees hold STALE copies of `CLAUDE.md` — never read those) | — | — | — |

Generated, ignored, never committed: `prototype/*.json` datasets (`make_*.py`),
`prototype/*.db*`, `prototype/pseudex-vault.key`, `prototype/pseudex/_release.py`
(the compiled-in verification key, written by both Dockerfiles), `deploy/secrets/`, «deploy/.registry/» (the agent's cosign-verified copy of `deploy/releases.json`),
`storefront/.venv`, `storefront/storefront.sqlite3`, `~/.cache/pseudex-bench/`
(external corpora — NEREL, PII-Bench, RuDevices, MASSIVE, ru_prose).

---

## 1. `prototype/pseudex/` — the engine

46 modules, ~22 500 lines. Paths in this section are relative to `prototype/`.
`Uses` / `Used by` are the real import edges inside the package (lazy imports
included). `Tests` lists scripts that import the module directly, then `via` —
the modules through which the rest of the suite reaches it. Every test script
is described in §3.3.

### 1.1 Detection pipeline

Composed in ONE place, `pseudex/detect_all.py`. Order: `normalize` → recognizers (union)
→ `context.suppress` → `_resolve` (priority, longest-first, non-overlapping).
See FLOWS.md §1.

#### `pseudex/normalize.py` — 139 lines · `live`
Layer 0: a 1:1 length-preserving fold of the text before detection — homoglyphs
→ digits only inside digit-dense runs, dashes/spaces/zero-width. Offsets from the
normalized text index straight back into the original.
- **API:** `normalize`
- **Uses:** assets · **Used by:** detect_all, redact, vault
- **Tests:** test_persona_defects, test_product · via detect_all → everything in §3.3
- **Docs:** `research/dd4-A-noise-phone.md` · rules: INVARIANTS.md#normalize

#### `pseudex/detect.py` — 97 lines · `live`
The span types every recognizer emits (`Span`, `NameSpan`, `PartSpan`) and the
first recognizer: libphonenumber ∪ regex phone/email.
- **API:** `Span`, `NameSpan`, `PartSpan`, `detect_pii`
- **Uses:** — · **Used by:** address, context, credentials, detect_all, envelope, names, quasi, redact, ru_pii, spoken, structured
- **Tests:** test_loop · via detect_all
- **Docs:** `docs/how-it-works.md`

#### `pseudex/ru_pii.py` — 380 lines · `live`
Russian structured identifiers, checksum-gated: СНИЛС (mod 101), ИНН (weight
vectors), card (Luhn), ОГРН/ОГРНИП, passport (cue-gated), VIN, licence plates.
The validators are the algorithm and stay in the binary; the cue words are leased.
- **API:** `validate_snils`, `validate_inn`, `validate_luhn`, `validate_ogrn`, `vin_check_digit_valid`, `detect_vehicle_ids`, `detect_structured`, `detect_plates`
- **Uses:** assets, detect, fuzzy · **Used by:** detect_all, spoken, vault
- **Tests:** test_class_g_leaks, test_product, make_dataset · via detect_all → test_coverage_152fz, test_hard_cases, test_overmasking
- **Docs:** `research/dd2-notes-C-disambiguation.md`, `research/ru-pii-dataset-and-detectors.md` · rules: INVARIANTS.md#structured-ids

#### `pseudex/structured.py` — 219 lines · `live`
Layer 1: JSON / form key-value, where the KEY types the WHOLE value with no shape
check (`KEY_TYPE`), or only licenses a shape (`CTX_TYPES`). A KV-typed span skips
`suppress`.
- **API:** `detect_structured_kv`, `key_edge`
- **Uses:** assets, detect, morph_places · **Used by:** detect_all, redact
- **Tests:** none direct · via detect_all → test_hard_cases, test_persona_defects, test_product
- **Docs:** `research/dd4-B-structured.md` · rules: INVARIANTS.md#structured-kv

#### `pseudex/credentials.py` — 123 lines · `live`
API keys, tokens, private keys — anchored to PUBLISHED prefixes, never to entropy.
- **API:** `detect_credentials`, `secret_prefix`
- **Uses:** detect · **Used by:** detect_all, vault
- **Tests:** none direct · via detect_all, vault → test_credentials
- **Docs:** `research/2026-08-16-secrets-detection-sota.md` · rules: INVARIANTS.md#credentials

#### `pseudex/quasi.py` — 131 lines · `live`
Quasi-identifiers: date of birth in birth context, age ≥ 90, medical terms.
- **API:** `sentence_window`, `detect_quasi`
- **Uses:** assets, detect, fuzzy · **Used by:** context, detect_all
- **Tests:** none direct · via detect_all → test_hard_cases, test_coverage_152fz, test_overmasking
- **Docs:** `research/dd4-C-quasi-identifiers.md` · rules: INVARIANTS.md#dates

#### `pseudex/spoken.py` — 674 lines · `live`
Identifiers DICTATED ALOUD: numeral runs → digit strings, then the SAME
validators as the digit path (Luhn, mod 101, ИНН, libphonenumber). Spoken dates,
e-mails, plates. The typo table is MINED from real transcripts; fuzzy matching on
numerals is forbidden.
- **API:** `is_numeral_word`, `numeral_alternation`, `canonical_numeral`, `date_from_words`, `date_to_words`, `run_to_digits`, `digits_in_words_like`, `numeral_runs`, `detect_spoken_ids`, `email_from_words`, `detect_spoken_email`, `plate_from_words`, `plate_in_words_like`, `detect_spoken_plate`, `main`
- **Uses:** agent_form, assets, detect, fuzzy, ru_pii · **Used by:** address, date_form, detect_all, morph_places, names, notation, redact, vault
- **Tests:** test_product · via detect_all → test_overmasking (dictated order numbers), test_hard_cases; `bench/voice/`
- **Docs:** `bench/voice/README.md`, `docs/known-issues.md` (Б1, Б6) · rules: INVARIANTS.md#spoken

#### `pseudex/names.py` — 1 692 lines · `live`
What NER misses and what it over-tags: the gazetteer (leased), lowercase
diminutives, Latin names, initials, the cue-word gate, the deletion-neighbourhood
typo index, the four-signal split-surname join. Also the gate that KEEPS or DROPS
a Natasha PER/LOC.
- **API:** `is_known_name`, `is_surname_shaped`, `keep_location`, `trim_person_span`, `keep_person`, `gazetteer_names`, `trim_document_words`, `recover_damaged_name`
- **Uses:** assets, detect, fuzzy, morph, spoken · **Used by:** address, assets, detect_all, vault
- **Tests:** test_class_g_leaks, test_product, test_unload_scrub, profile_deep · via detect_all → test_names_morphology, test_hard_cases, test_persona_defects, test_overmasking; `bench/gate/`, `bench/eval_massive_ru.py`, `bench/eval_external_ner.py`
- **Docs:** `research/dd2-notes-A-ru-ner.md`, `research/2026-08-31-ml-gate-or-rules.md`, `bench/gate/README.md` · rules: INVARIANTS.md#names

#### `pseudex/morph_names.py` — 988 lines · `live`
Russian personal-name morphology: gender, case, nominative, inflection, the
round-trip guard. `to_nominative` is called from two sides (real value in
`canonicalize`, fake value in `name_key`) and only one may carry a guard.
- **API:** `name_shape`, `has_given_name`, `detect_gender`, `detect_case`, `full_patronymic`, `governing_cases`, `read_person`, `to_nominative_governed`, `to_nominative`, `lone_nominative_gender`, `inflect_person`, `cases_spelled_as`, `looks_like_person`, `given_name_gender`, `feminine_surname`, `survives_round_trip`
- **Uses:** assets, fuzzy, morph · **Used by:** detect_all, redact, vault
- **Tests:** test_derived_forms, test_names_morphology, test_product
- **Docs:** `research/2026-08-16-russian-name-morphology.md`, `docs/tz-name-gender-canonical.md`, `research/2026-09-17-prose-case-homography.md` · rules: INVARIANTS.md#name-morphology

#### `pseudex/address.py` — 1 927 lines · `live`
High-recall Russian address detection: Natasha AddrExtractor ∪ regex anchors ∪
marker-less streets (ГАР-vocabulary-gated) ∪ bare lower-case streets (four gates)
∪ spoken tails, merged into maximal spans with a core part required. Also the
register-spelling repair of a mistyped street for the TOOL leg.
- **API:** `register_spelling`, `repair_street`, `detect_address`
- **Uses:** _morph_compat, assets, detect, fuzzy, morph, morph_places, names, spoken · **Used by:** assets, detect_all, redact
- **Tests:** test_hard_cases, test_unload_scrub, profile_deep · test_class_g_leaks via detect_all → test_overmasking, test_persona_defects, test_product; `bench/voice/`, `bench/eval_gar_cut.py`, `make_addr_real.py`
- **Docs:** `docs/gar-street-vocabulary.md`, `research/dd2-notes-B-ru-address.md`, `research/dd3-location-pii.md` · rules: INVARIANTS.md#address

#### `pseudex/morph_places.py` — 1 937 lines · `live`
Place morphology and the address READER: street vs city, nominative, agreement
with the generic word, `split_roles` (city / street / street_type / street_name /
house / flat / entrance — the one parser every consumer must reuse), keys for the
vault (`address_key` is the IDENTITY and `street_house_key` is the LINKING key;
`key_type` reads the type slot of the identity), `in_form_of` for restoring a
tool argument in the agent's own form, and `field_role` / `field_tokens` /
`field_prefix` for reading a schema's field names (`street_type`, `streetType`,
`address.street`).
- **API:** `looks_like_street`, `to_nominative`, `phrase_to_nominative`, `inflect_place`, `detect_case`, `place_gender`, `generic_forms`, `region_prefix_end`, `address_key`, `key_type`, `generic_full`, `street_house_key`, `strip_flat`, `strip_leading_city`, `place_shape`, `agree_with_generic`, `match_signature`, `signature_parts`, `is_generic_word`, `street_case`, `split_roles`, `role_spans`, `field_role`, `field_tokens`, `field_prefix`, `role_of_field`, `city_case`, `address_from_fields`, `part_in_form_of`, `house_digits`, `in_form_of`, `reduce_address`
- **Uses:** agent_form, assets, morph, spoken · **Used by:** address, assets, envelope, notation, redact, structured, vault
- **Tests:** test_address_composition, test_hard_cases, test_product, test_unload_scrub; `bench/agentpii4/harness.py`, `bench/agentpii4/microscope.py`
- **Docs:** `docs/known-issues.md` (§2, Б2, Б10), `research/2026-09-02-agent-form-benchmark.md` · rules: INVARIANTS.md#address, INVARIANTS.md#agent-form

#### `pseudex/context.py` — 386 lines · `live`
Context-aware false-positive suppression (the deny-context layer): document
words before a date, cue words within 60 characters and never across a sentence
end, place-reference vs address. Runs BEFORE overlap resolution.
- **API:** `location_is_pii`, `suppress`
- **Uses:** assets, detect, fuzzy, quasi · **Used by:** detect_all
- **Tests:** none direct · via detect_all → test_overmasking, test_hard_cases, test_coverage_152fz
- **Docs:** `research/dd2-notes-C-disambiguation.md`, `research/dd3-location-pii.md` · rules: INVARIANTS.md#context

#### `pseudex/fuzzy.py` — 213 lines · `live`
One-edit matching shared by names and addresses: Damerau distance and the
deletion-neighbourhood index (Mor-Fraenkel / SymSpell), complete by construction.
- **API:** `within_one_edit`, `within_one_typo`, `deletion_keys`, `DeletionIndex`, `build_index`, `lookup`, `recover_one_edit`, `Edit`, `edit_from`, `apply_edit`
- **Uses:** — · **Used by:** address, context, morph_names, names, quasi, ru_pii, spoken, vault
- **Tests:** `bench/blocking_recall.py` · via names/address → test_hard_cases, test_persona_defects
- **Docs:** `docs/gar-street-vocabulary.md` (the fuzzy-street curve) · rules: INVARIANTS.md#names, INVARIANTS.md#spoken

#### `pseudex/morph.py` — 38 lines · `live`
The single pymorphy3 analyzer shared by every module that needs morphology.
- **API:** `is_stretched_filler` (+ the module-level analyzer)
- **Uses:** — · **Used by:** address, assets, morph_names, morph_places, names; `bench/eval_gar_cut.py`
- **Tests:** none direct · via every morphology test
- **Docs:** —

#### `pseudex/_morph_compat.py` — 19 lines · `live`
Aliases pymorphy2 → pymorphy3 at import time. MUST be imported before any
`from natasha import …` — natasha binds the name eagerly.
- **Uses:** — · **Used by:** address, detect_all; `bench/_baseline_independent.py`, `bench/eval_vault_precision.py`
- **Tests:** none direct · via detect_all (an import-order regression shows as an ImportError at startup)
- rules: INVARIANTS.md#morph-compat

#### `pseudex/detect_all.py` — 279 lines · `live`
The ONLY composition point. `Detector` holds the Natasha model and runs the
pipeline above; `_PRIORITY` is the arbiter (checksum IDs 6 > phone/email 5 >
ADDR 4 > NAME 3 > DATE/PASSPORT/LOC 2); `ADDR` exists only to outrank a NAME
inside a street name and is remapped to `LOC` after resolution.
- **API:** `Detector`
- **Uses:** _morph_compat, address, assets, context, credentials, detect, morph_names, names, normalize, profiling, quasi, ru_pii, spoken, structured · **Used by:** envelope, proxy, service
- **Tests:** test_class_g_leaks, test_argument_form, test_collisions, test_coverage_152fz, test_credentials, test_hard_cases, test_names_morphology, test_overmasking, test_perf_masking, test_persona_defects, test_product, test_prose_fragments; every `eval_*.py`; every `bench/`
- **Docs:** `docs/how-it-works.md`, `docs/spec.md`, `research/dd2-notes-D-architecture-eval.md` · rules: INVARIANTS.md#pipeline

#### `pseudex/translit.py` — 350 lines · `live`
Transliteration and initials — the DERIVED forms a model writes. `align` learns
the model's per-unit choice from the substitute, `render` applies it to the real
name, `fold` is the vault index key of one rendering, and `declared_keys` is the
set of keys the mint indexes so that no rendering `UNITS` declares can miss it.
- **API:** `apply`, `is_cyrillic_word`, `units_of`, `align`, `render`, `variants`, `table_for`, `fold`, `folded`, `declared_keys`, `match_case`, `squeezed_initials`, `main`
- **Uses:** assets · **Used by:** notation, redact, vault
- **Tests:** test_derived_forms, test_prose_fragments
- **Docs:** `research/2026-09-02-agent-form-benchmark.md` · rules: INVARIANTS.md#derived-forms

#### `pseudex/date_form.py` — 108 lines · `live`
A date written the way ANOTHER date is written: `render_like` puts the
canonical «dd.mm.yyyy» into the notation of a sample (separator, padding,
two-digit year, ISO, month in words with or without the year, spoken),
`same_notation` says when the customer's own words must stay. The substitute
mirrors the customer's notation at the mint, the restorer renders the real
date in the agent's.
- **API:** `notation_of`, `same_notation`, `render_like`, `main`
- **Uses:** spoken · **Used by:** notation, vault
- **Tests:** `python3 -m pseudex.date_form` (self-test) · via redact → test_argument_form (`_forms_follow`), test_product, test_hard_cases; test_notation_symmetry
- **Docs:** `docs/known-issues.md` (Б24) · rules: INVARIANTS.md#swap

#### `pseudex/agent_form.py` — 135 lines · `live`
The FORM the agent wrote a substitute in (case, word by word, positional), laid
over the real value on the way back to the tool. Symmetric: lower case in, lower
case out. A NAME is cased as a whole class (`lower`/`upper`/`title`), never
word by word — mirroring a lower-case particle onto the fake's patronymic
produced a run the windows could not read back (Б24).
- **API:** `cased_like`, `case_class`, `name_cased_like`, `main`
- **Uses:** — · **Used by:** morph_places, notation, redact, spoken
- **Tests:** none direct · via redact → test_argument_form
- **Docs:** `research/2026-09-02-agent-form-benchmark.md` · rules: INVARIANTS.md#agent-form

#### `pseudex/notation.py` — 434 lines · `live`
ONE interface for notation: «the value in the notation of whoever wrote it».
`render_like(value, surface, kind, target=None, for_tool=False)` is the single
decision point every restore seam and every mint must use — `surface` is the
notation SAMPLE, `value` is the content from the vault, `target` is the leaf's
notation (class Ж `FieldSpec`), and `for_tool` says which leg the mention is on
(the tool cannot execute a dictated phrase, so there the leaf's/register's
written form wins). `notation_of(surface, kind)` names the notation CLASS. The
per-type renderers stay where they belong (PHONE/SNILS/card/date/email in
`redact`/`date_form`, the address in `morph_places.in_form_of`, the plate here);
they are reached ONLY through this interface, because seven separate decisions
was exactly the class А defect. `plate_signature` is the content signature a
plate resolves by (letters + digits, both Latin readings folded). `redact`,
`translit` and `vault` are reached by LAZY imports inside the type-specific
renderers — `redact` imports this module, and `vault`/`translit` would make the
ring.
- **API:** `script_of`, `case_of`, `looks_dictated`, `notation_of`, `render_like`, `plate_content`, `plate_signature`, `plate_notation_of`, `plate_in_form_of`, `plate_laid_like`, `written_place`, `place_in_form_of`, `name_in_form_of`, `name_in_script`
- **Uses:** agent_form, date_form, morph_places, redact (lazy), spoken, translit (lazy), vault (lazy) · **Used by:** redact, vault
- **Tests:** test_notation_symmetry; via redact/vault → the hop-form suites
- **Docs:** `research/hop-format-audit/SPIKE-А.md`, `research/hop-format-audit/DECISIONS-SPRINT.md` · rules: INVARIANTS.md#notation

### 1.2 Swap and vault

#### `pseudex/redact.py` — 1 666 lines · `live`
The swap layer: tokenize spans on the way to the model (substitute inflected to
the original's case), detokenize on the way back — prose in agreement, tool
arguments verbatim in the agent's form; PHONE notation follows the current
sender on both legs. Streaming detokenizer with one carry per
`choice.index`; `unmask_arguments` for buffered tool calls; `residual_tokens`
(two arguments, the shape the benchmark's own gateway calls) and the leg-aware
`surviving_substitutes` for substitutes that failed to resolve.
- **API:** `mask_text`, `is_own_substitute`, `vault_value`, `tokenize_span`, `unmask_text`, `unmask_stream_chunk`, `unmask_arguments`, `residual_tokens`, `surviving_substitutes`, `StreamDetokenizer`
- **Uses:** address, agent_form, assets, detect, morph_names, morph_places, normalize, notation, profiling, spoken, structured, translit, vault · **Used by:** envelope, notation, proxy, service
- **Tests:** test_class_g_leaks, test_argument_form, test_collisions, test_derived_forms, test_digit_truncation, test_hard_cases, test_loop, test_names_morphology, test_notation_symmetry, test_phone_hop_form, test_error_echo_privacy, test_product, test_prose_fragments, bench_masking, profile_latency; `bench/agentpii{2,3,4}`, `bench/agentrun/roundtrip.py`
- **Docs:** `docs/how-it-works.md`, `docs/known-issues.md` (§0, §1, Б8, Б11, Б12) · rules: INVARIANTS.md#swap, INVARIANTS.md#streaming

#### `pseudex/vault.py` — 3 397 lines · `live`
Token vault: persistent SQLCipher store keyed by `(customer, canonical)`;
canonicalization (phones, names in the nominative with gender evidence,
addresses via `split_roles`); format-preserving, checksum-VALID substitutes from
impossible ranges; the conversation scope (`for_conversation`, `with_pseudonym_scope`, `minted_in`);
the digit-signature and translit reindexes; the collision guards at mint time.
`Vault.resolve_digit_signatures_typed` preserves type and exact-over-tail
precedence for PHONE rendering without a new schema or database query.
`Vault.digit_fragment_owner` answers a run that is a substitute's digits as a
NUMBER spelled without their leading zeros with the real value WHOLE (class Д,
never `canon[2:12]`), refuses two owners of one number, and
`digit_fragment_is_ours` names a substitute one digit from what the agent wrote
without ever resolving it.
- **API:** `count_values_since`, `canonicalize_person`, `canonicalize`, `name_key`, `fold_key`, `place_key`, `token_re`, `create_tables`, `create_indexes`, `Vault` (+ `VAULT_MIGRATIONS`)
- **Uses:** assets, credentials, date_form, fuzzy, morph_names, morph_places, names, normalize, notation, profiling, ru_pii, schema, spoken, sqlite_setup, translit · **Used by:** assets, envelope, notation, proxy, redact, service, schema (lazy)
- **Tests:** test_class_g_leaks, vault_test, test_argument_form, test_collisions, test_credentials, test_derived_forms, test_digit_truncation, test_hard_cases, test_loop, test_names_morphology, test_notation_symmetry, test_persona_defects, test_product, test_prose_fragments, test_unload_scrub; `bench/eval_vault_precision.py`, `bench/fuzz_registers.py`
- **Docs:** `docs/tz-vault-encryption.md`, `docs/tz-name-gender-canonical.md`, `docs/how-it-works.md`, `research/2026-09-03-checksum-valid-substitutes.md` · rules: INVARIANTS.md#vault, INVARIANTS.md#collisions, INVARIANTS.md#conversation-scope

#### `pseudex/envelope.py` — 326 lines · `live`
Transformations over the OpenAI chat wire envelope, shared by BOTH surfaces:
`mask_messages` (multi-part content, `skip_system`, the mask cache),
`mask_tools`, `unmask_response`, `conversation_key` (derived from the first two
messages when the caller names none).
- `tool_result_contexts` binds exact preceding IDs for contextual echo protection;
  an unbound result can neutral-redact a typed echo recorded in this conversation.
- **API:** `MaskContext`, `ToolCallContext`, `ToolResultContext`, `tool_result_contexts`, `conversation_key`, `mask_one`, `mask_messages`, `mask_tools`, `unmask_response`
- **Uses:** audit, detect, detect_all, maskcache, morph_places, profiling, redact, vault · **Used by:** proxy, service
- **Tests:** test_collisions, test_persona_defects, test_product, test_tool_result_context, profile_deep; `bench/agentpii*/`
- **Docs:** `docs/how-it-works.md` · rules: INVARIANTS.md#conversation-scope, INVARIANTS.md#cache

#### `pseudex/maskcache.py` — 109 lines · `live`
Content-keyed cache of MASKED output, per worker — the O(n²) killer on a growing
transcript. Keys on RAW content (masked output is never re-fed); the key carries
the conversation.
- **API:** `content_key`, `MaskCache`
- **Uses:** — · **Used by:** envelope, proxy, service
- **Tests:** test_perf_masking, test_collisions, test_persona_defects, test_product, bench_masking
- **Docs:** — · rules: INVARIANTS.md#cache

#### `pseudex/audit.py` — 549 lines · `live`
What was caught and what replaced it: type + token + masked preview only, never
the value. Recorded on cache MISS only. Also the request counter (`requests` is
a REQUEST counter, not `sum(entities)`), reveal records, billing totals
(excluding `SELFCHECK_ORG`).
- **API:** `create_tables`, `AuditLog` (+ `AUDIT_MIGRATIONS`)
- **Uses:** profiling, schema, sqlite_setup · **Used by:** envelope, metering, operator, proxy, service, schema (lazy)
- **Tests:** test_collisions, test_detok_security, test_localui, test_persona_defects, test_product; `bench/agentpii*/`
- **Docs:** `docs/tz-local-ui.md`, `docs/metering-integrity.md` · rules: INVARIANTS.md#audit

### 1.3 Lease and assets

#### `pseudex/assets.py` — 540 lines · `live`
In-memory registry of the LEASED detection assets — gazetteers, street
vocabulary, cue words, priority table, look-alike folds, key→type map, fake
pools. Compiles every regex ONCE at load; raises `BundleNotLeased` when nothing
is loaded — no bundle means NO detection, not less.
- **API:** `BundleNotLeased`, `NameAssets`, `AddressAssets`, `SpokenAssets`, `QuasiAssets`, `ContextAssets`, `StructuredAssets`, `RuPiiAssets`, `TranslitAssets`, `FakeAssets`, `CompositeType, DetectionAssets`, `Assets`
- **Uses:** address, bundle, morph, morph_places, names, vault (lazy) · **Used by:** address, context, detect_all, license, morph_names, morph_places, names, normalize, proxy, quasi, redact, ru_pii, service, spoken, structured, translit, vault
- **Tests:** test_canary, test_derived_forms, test_fingerprint, test_hard_cases, test_product, test_prose_fragments, test_tuning_lease_security, test_unload_scrub, test_watermark, testkit
- **Docs:** `docs/tz-license-packaging.md`, `docs/tz-tuning-in-lease.md` · rules: INVARIANTS.md#lease

#### `pseudex/bundle.py` — 413 lines · `live`
The wire format shared by both sides: age-seal to ONE process key, Ed25519
signature (who made it — encryption alone does not authenticate the sender),
nonce wrap, framing, the usage-report MAC. Imported BY the licensing server —
the one direction that is allowed.
- **API:** `BundleError`, `ProcessKey`, `generate_process_key`, `is_recipient`, `seal`, `open_sealed`, `nonce_wrap`, `nonce_unwrap`, `merge_payload`, `is_framed`, `frame_payload`, `unframe_payload`, `plaintext_hash`, `signing_payload`, `report_payload`, `sign_lease`, `mac_report`, `verify_report`, `decode_public_key`, `verify_lease`
- **Uses:** — · **Used by:** assets, license; `licensing/keys.py`, `licensing/pack.py`, `licensing/server.py`
- **Tests:** test_canary, test_fingerprint, test_tuning_lease_security, test_watermark, `licensing/test_admin_api.py`, `licensing/test_metering_attacks.py`
- **Docs:** `docs/tz-license-packaging.md` §3 · rules: INVARIANTS.md#lease

#### `pseudex/license.py` — 977 lines · `live`
Client side of the lease: X25519 process keypair in memory, `POST /v1/lease`,
renewal loop, the degradation ladder `LEASED → STALE → EXPIRED` (grace on
`time.monotonic()`, 402/403 and 426 bypass it), unload + scrub, usage reports, the
compiled-in verification key from `pseudex/_release.py`. Also the version
ladder (D-055): the signed `version` block of each lease is parsed once into
`LicenseStatus` (INFO «есть новее» once per version, WARN on every renewal
after `deprecated_at`, a notice once per id), `lease_contract` is declared in
the request (D-063), and a `bundle_format` above `SUPPORTED_BUNDLE_FORMAT` is
`BundleFormatError` — «обновите движок», grace on renewal, its own code at start (D-064).
- **API:** `explain`, `BundleFormatError`, `LicenseError`, `LicenseStatus`, `LicenseClient`
- **Uses:** _release (generated), assets, bundle, measure · **Used by:** metering, proxy, service
- **Tests:** test_clock_freeze, test_localui, test_persona_defects, `licensing/test_admin_api.py`, `licensing/test_metering_attacks.py`; `e2e/gates.py` L1–L22
- **Docs:** `docs/tz-license-packaging.md`, `docs/tz-tuning-in-lease.md`, `docs/staleness-and-rotation.md`, `docs/tz-offline-license.md` (design) · rules: INVARIANTS.md#lease

#### `pseudex/measure.py` — 77 lines · `live`
A measurement of the running build (which binary, which hash) — goes into the
lease request and the usage report so the server can tell builds apart.
- **API:** `build_measurement`
- **Uses:** — · **Used by:** license, serve_main
- **Tests:** `licensing/test_metering_attacks.py`
- **Docs:** `docs/metering-integrity.md`

#### `pseudex/metering.py` — 34 lines · `live`
ONE point where a request is counted and capacity is charged for it.
- **API:** `bill`
- **Uses:** audit, license · **Used by:** proxy, service
- **Tests:** none direct · via service → test_perf_masking, test_localui; `e2e/gates.py` L12; `licensing/test_metering_attacks.py`
- **Docs:** `docs/metering-integrity.md`, `docs/billing-integrity.md` · rules: INVARIANTS.md#billing

### 1.4 Surfaces

#### `pseudex/service.py` — 1 015 lines · `live`
The sidecar behind a host gateway: `/mask`, `/unmask`, `/unmask_chunk`,
`/unmask_arguments`, `/spans`, `/health` (gateway token) + the operator router
(admin token). `org_id` and `conversation_id` in the body; detection offloaded
via `anyio.to_thread` under a `CapacityLimiter`.
- **API:** `profile`, `health`, `license_status`, `mask`, `unmask`, `unmask_arguments_endpoint`, `unmask_chunk`, `spans`, `usage`, `reveal`
- **Uses:** assets, audit, detect_all, envelope, license, maskcache, metering, operator, profiling, redact, sqlite_setup, vault · **Used by:** serve_main
- **Tests:** test_detok_security, test_localui, test_perf_masking, test_persona_defects; `e2e/gates.py`
- **Docs:** `docs/integration.md`, `docs/integration-diva-litellm.md`, `docs/integration-diva-backend-api.md`, `docs/how-it-works.md` · rules: INVARIANTS.md#surfaces, INVARIANTS.md#streaming

#### `pseudex/proxy.py` — 911 lines · `live` (formerly `drifted`)
The OpenAI-compatible reverse proxy: `sk-ps-…` key → `Tenants` → upstream URL +
key; `POST /v1/chat/completions` with streaming (`StreamDetokenizer`; tool-call
requests buffered), `GET /usage`. Shares `envelope.mask_messages`, `MaskCache`,
the thread offload and the limiter with the sidecar. The one remaining
difference: no `skip_system` (the proxy always masks the system prompt).
`CLAUDE.md`'s "duplicated on purpose but have drifted" paragraph predates the
shared envelope. `docs/known-issues.md` §3 lists what else lagged and what is closed.
- **API:** `health`, `license_status`, `profile`, `usage`, `chat_completions`, `spans`, `mask`, `reveal`
- **Uses:** assets, audit, detect_all, envelope, license, maskcache, metering, operator, profiling, redact, sqlite_setup, tenants, vault · **Used by:** serve_main
- **Tests:** test_persona_defects · via redact → test_product (streaming detok); live: `agent_demo.py`, `response_test.py`, `live_eval.py` (live)
- **Docs:** `docs/integration.md`, `docs/known-issues.md` §3 · rules: INVARIANTS.md#surfaces

#### `pseudex/operator.py` — 532 lines · `live`
Read-mostly endpoints for the operator's local interface, mounted on both
surfaces under the ADMIN token: `/status`, `/events`, `/stats`, `/stats.csv`,
`/reveals`, `/subscription`, `/diagnostics`, `/selfcheck`, `/reveal`, `/metrics`.
`release_verdict` is the `engine.release` block of `/status` and `/subscription`:
the server's verdict on this version (D-055) with unix dates and the one
upgrade command, `None` fields when the server said nothing.
- **API:** `processes`, `memory`, `release_verdict`, `build_router`
- **Uses:** audit, metrics, preflight, profiling, schema, sqlite_setup · **Used by:** proxy, service
- **Tests:** none direct · via service → test_localui, test_perf_masking (401 on token drift), test_detok_security
- **Docs:** `docs/tz-local-ui.md` · rules: INVARIANTS.md#surfaces, INVARIANTS.md#audit

#### `pseudex/localui/server.py` — 428 lines · `live`
The operator's local interface: a SEPARATE ASGI app on :8081 (`PSEUDEX_ROLE=ui`)
so it can say "движок не отвечает". Startup token / `PSEUDEX_UI_PASSWORD`
sign-in, token in the Authorization header (never a cookie), engine proxy as an
ALLOWLIST of exact paths. Pages are vendored Preact+htm under `pseudex/localui/`
and ship at `/app/ui`. Never imports `pseudex.service`, never leases.
- **API:** `signin_url`, `signin`, `signout`, `whoami`, `engine_get`, `engine_post`, `healthz`, `index`, `static_file`
- **Uses:** — · **Used by:** serve_main
- **Tests:** test_localui · via a running UI process → test_localui_renders (real browser)
- **Docs:** `docs/tz-local-ui.md` · rules: INVARIANTS.md#local-ui

#### `pseudex/tenants.py` — 87 lines · `live`
Multi-tenant API keys for the proxy shape: key → upstream URL + key.
- **API:** `create_tables`, `Tenant`, `Tenants` (+ `TENANTS_MIGRATIONS`)
- **Uses:** schema, sqlite_setup · **Used by:** proxy, schema (lazy); `issue_key.py`
- **Tests:** test_product
- **Docs:** `docs/integration.md`

#### `pseudex/metrics.py` — 113 lines · `live`
Prometheus text format written by hand — no client library in the image.
- **API:** `escape`, `render`, `series`, `Counter`
- **Uses:** — · **Used by:** operator; `licensing/server.py`
- **Tests:** none direct · via operator → test_localui
- **Docs:** `docs/operations.md`

### 1.5 Storage, process, ops

#### `pseudex/sqlite_setup.py` — 392 lines · `live`
The ONE SQLite driver setup for the four stores (vault, audit, tenants,
licensing): `sqlcipher3` only, no `import sqlite3` anywhere in `pseudex/` (both
Dockerfiles fail the build on it). HKDF per-store keys, read-only opens, volume
state, preflight of the mounted volume.
- **API:** `VaultLocked`, `store_key`, `connect`, `connect_readonly`, `volume_state`, `preflight`, `describe`
- **Uses:** vault_key, vault_migrate · **Used by:** audit, operator, proxy, schema, service, tenants, vault; `licensing/store.py`, `licensing/verify.py`, serve_main
- **Tests:** `licensing/test_store_upgrade.py` · via vault → vault_test, test_pseudexctl; `e2e/pack_gates.py` P9
- **Docs:** `docs/tz-vault-encryption.md` · rules: INVARIANTS.md#storage

#### `pseudex/vault_key.py` — 507 lines · `live`
Where the store key comes from, and never from us: `PSEUDEX_VAULT_KEY` →
`_KEY_FILE` → `_KEY_CMD` → generated beside the data. `required` refuses to
generate; `off` is plaintext (the licensing image only).
- **API:** `VaultKeyError`, `VaultSecret`, `resolve`, `existing`, `replacement`, `key_literal`, `key_state`, `reset_cache`
- **Uses:** — · **Used by:** sqlite_setup, vault_migrate, serve_main
- **Tests:** none direct · via serve_main roles → test_pseudexctl (rekey proof, doctor); `e2e/gates.py` vault gates
- **Docs:** `docs/tz-vault-encryption.md`, `docs/operations.md` · rules: INVARIANTS.md#storage

#### `pseudex/vault_migrate.py` — 358 lines · `live`
Plaintext store → encrypted, in place, under `flock`, idempotent by file header,
`wal_checkpoint(TRUNCATE)` first. Rekey and decrypt are the same move in other
directions (`PSEUDEX_ROLE=rekey|decrypt`).
- **API:** `VaultMigrationError`, `file_state`, `ensure_encrypted`, `rekey_store`, `decrypt_store`
- **Uses:** vault_key · **Used by:** schema, sqlite_setup, serve_main
- **Tests:** none direct · via serve_main roles → test_pseudexctl; `e2e/gates.py` (migration gates)
- **Docs:** `docs/tz-vault-encryption.md` · rules: INVARIANTS.md#storage

#### `pseudex/schema.py` — 330 lines · `live`
The schema of a volume, numbered (D-058…D-060): `application_id` per store,
`user_version` moved only by numbered idempotent steps (`vault.VAULT_MIGRATIONS`,
`audit.AUDIT_MIGRATIONS`, `tenants.TENANTS_MIGRATIONS`), `ensure` — refuse a
volume from the future (`SchemaTooNew`) or another store's file
(`SchemaMismatch`) BEFORE touching it, `VACUUM INTO` snapshot under the same
key before the first step (`SchemaNoSpace` when < 2× free), fast path when the
volume is current. `PSEUDEX_ROLE=migrate` runs it once before the fan-out;
`probe` exits 2 on a future volume (entrypoint 6). `schema_lock.json` pins the
maximum per minor.
- **API:** `SchemaError`, `SchemaTooNew`, `SchemaTooOld`, `SchemaMismatch`, `SchemaNoSpace`, `Step`, `StoreSchema`, `registry`, `short_name`, `max_version`, `versions`, `running`, `read_lock`, `on_disk`, `explain_too_new`, `snapshots`, `ensure`, `snapshot` (+ constants `APPLICATION_IDS`, `MIN_VERSION`, `RUNNING`)
- **Uses:** sqlite_setup, vault_migrate, audit (lazy), tenants (lazy), vault (lazy) · **Used by:** audit, operator, tenants, vault, serve_main
- **Tests:** test_schema · via entrypoint.sh → test_preflight (exit codes 5/6); `e2e/gates.py` L24–L25
- **Docs:** `docs/tz-release-and-versions.md` §7 · rules: INVARIANTS.md#storage

#### `pseudex/hardening.py` — 114 lines · `live`
Process-level hardening against reading the worker's memory off disk: no core
dumps, no ptrace attach, applied BEFORE any role touches the tuning or the vault.
- **API:** `get_dumpable`, `tracer_pid`, `harden_process`
- **Uses:** — · **Used by:** serve_main
- **Tests:** test_memory_hardening; `e2e/gates.py` L14 (memscan)
- **Docs:** `research/2026-09-15-ram-extraction-hardening.md`, `research/2026-09-14-pentest-client-greybox.md` · rules: INVARIANTS.md#hardening

#### `pseudex/tripwire.py` — 240 lines · `live`
Memory-read tripwire: detects and attributes attempts to read the engine's RAM,
reports them to the licensing server (`/v1/tripwire`). Runs as
`PSEUDEX_ROLE=tripwire`.
- **API:** `engine_workers`, `ReadEvent`, `scan`, `watch`, `main`
- **Uses:** — · **Used by:** serve_main
- **Tests:** test_tripwire
- **Docs:** `docs/staleness-and-rotation.md`, `research/2026-09-15-ip-protection-map-and-sota.md` · rules: INVARIANTS.md#hardening

#### `pseudex/preflight.py` — 222 lines · `live`
How many workers fit in the cgroup memory limit — computed BEFORE the fan-out
(`PSEUDEX_ROLE=preflight`), refusing or lowering N instead of leaving it to the
OOM killer.
- **API:** `memory_limit_mb`, `plan`, `cpus_available`
- **Uses:** — · **Used by:** operator, serve_main
- **Tests:** test_preflight
- **Docs:** `docs/operations.md` · rules: INVARIANTS.md#process

#### `pseudex/profiling.py` — 126 lines · `live`
Stage-level profiler for the masking hot path; exposed at `/profile`.
- **API:** `StageStats`, `stage`, `snapshot`
- **Uses:** — · **Used by:** audit, detect_all, envelope, operator, proxy, redact, service, vault; `profile_deep.py`
- **Tests:** none dedicated (read by `profile_deep.py`, `profile_latency.py`)
- **Docs:** —

#### `pseudex/_release.py` — `generated`
`LICENSE_PUBKEY = "…"`, written by both Dockerfiles from `PSEUDEX_LICENSE_PUBKEY`.
Absent in a source checkout; `pseudex/license.py` explains the failure when it is missing.

---

## 2. `prototype/licensing/` — our side, never ships

Paths relative to `prototype/`. `pseudex/` must never import from here; this
package imports `pseudex.bundle`, `pseudex.sqlite_setup`, `pseudex.metrics`.

| file | lines | status | what |
|---|---|---|---|
| `licensing/assets_source.py` | 1 422 | `live` | THE authored detection assets: cue words, address regexes, priority table, look-alike folds, key→type map, fake pools. The tuning. |
| `licensing/data/first_names.txt`, `licensing/data/surnames.txt` | 28k / 197k entries | `live` | the bulk name dictionaries (`bench/build_name_dicts.py` rebuilt them once) |
| `licensing/data/gar_streets.tsv`, `licensing/data/gar_types.json` | 165k streets / 42 types | `generated` by `licensing/fetch_gar.py` | the ГАР street vocabulary with its attribution line and dump date |
| `licensing/fetch_gar.py` | 437 | `live` | rebuilds the street vocabulary from the ФНС ГАР dump without downloading 53 GiB (central-directory range reads) |
| `licensing/pack.py` | 423 | `live` | builds the bundle: `build_plaintext` → zlib(JSON), version = content hash; weaves canary, fingerprint and watermark; reads the ГАР attribution back rather than restating it |
| `licensing/canary.py` | 165 | `live` | per-customer canary surnames/streets in the leased gazetteers, for attribution of a leaked bundle |
| `licensing/fingerprint.py` | 137 | `live` | Tardos collusion-resistant fingerprint; `accuse` survives a coalition |
| `licensing/watermark.py` | 50 | `live` | per-customer watermark (`_wm`) in the payload |
| `licensing/keys.py` | 69 | `live` | the Ed25519 signing key (private on the server, public compiled into the release binary by `deploy/make-release-keys.sh`) |
| `licensing/server.py` | 1 317 | `live` | the licensing server — the only component on our hardware: `POST /v1/lease` (seal to the process key, sign), `/v1/release`, `/v1/tripwire`, `/v1/meter`, `/v1/usage`; admin API on :9443 (instances, anomalies, issue/revoke/suspend/resume/replan/plans, fleet) |
| `licensing/store.py` | 1 675 | `live` | licensing state: keys, leases, usage chains, anomalies. Schema MIGRATES before any index is built. |
| `licensing/devserver.py` | 68 | `live` | runs the server locally exactly as in production (`basicConfig` for the root logger lives here — uvicorn does not configure it) |
| `licensing/registry.py` | 470 | `live` | the versions registry as code (stdlib only): `validate` (schema, order, aliases, the 90-day rule, additive against the previous file), `record` (patch moves `latest`; a new minor opens a cycle and closes the previous one), `aliases_for`, `verdict` (the lease `version` block), `check` (the 426, never for a late `eol`), `Watch` (the server's mtime-reloaded view). CLI `python3 -m licensing.registry validate|record|aliases|verdict` |
| `licensing/test_registry.py` | 170 | `live` | every promise of `docs/tz-release-and-versions.md` §5–6 as a check |
| `licensing/verify.py` | 77 | `live` | is this copy of the licensing DB a WORKING database and how full is it (the restore drill asks this) |
| `licensing/repair_usage.py` | 77 | `live` | one-off repair of `usage` rows written before input validation existed |
| `licensing/test_admin_api.py` | 855 | `live` | attacks THROUGH HTTP, not around it: every admin action, auth, replay |
| `licensing/test_metering_attacks.py` | 360 | `live` | attacks on instance counting and on the chain of usage reports (race, replay, forged MAC, frozen clock) |
| `licensing/test_store_upgrade.py` | 116 | `live` | upgrade on EXISTING data: a verbatim snapshot of the old schema, never "current minus a column" |
| `licensing/test_ceiling.py` | `live` | объёмный потолок периода (`docs/tz-license-volume-quota.md` §C): `/admin/ceiling` хранит абсолютное число, `/v1/meter` отказывает сверх него ЛЮБОМУ процессу (анти-Б35) кодом `ceiling_reached` (мягкий, вне `_ANSWER_CODES`), рекенси-подсчёт (живой=granted, мёртвый=billable — нет дрейфа и нет переслужа), подъём потолка снимает отказ |

Docs: `docs/tz-license-packaging.md` (the spec), `docs/tz-tuning-in-lease.md`,
`docs/metering-integrity.md`, `docs/staleness-and-rotation.md`,
`docs/gar-street-vocabulary.md`, `docs/tz-offline-license.md` (design, O1–O15 not built).

---

## 3. `prototype/` root — entry points, build, tests, evals

Paths relative to `prototype/`. Everything runs from `prototype/` with the venv
active. There is NO pytest; each script has a `main()`.

### 3.1 Entry points and the roles

| file | status | what |
|---|---|---|
| `version.txt` | `live` | the ONE source of the engine version (D-053): both Dockerfiles bake it into `pseudex/_release.py` as `ENGINE_VERSION`, `pseudex/license.py` reads it (dev checkout: the file), the lease, `/status`, the UI and `pseudexctl doctor` show it; `.github/workflows/release.yml` is red when it differs from the tag |
| `entrypoint.sh` | `live` | the container's PID 1: generates the two tokens ONCE for all workers, runs `PSEUDEX_ROLE=preflight` to size N, `PSEUDEX_ROLE=probe` to check the volume, then fans out N uvicorn workers (`engine`, or `proxy`) and starts the UI process (`PSEUDEX_ROLE=ui`) |
| `serve_main.py` | `live` | entry point of ONE worker; dispatches on `PSEUDEX_ROLE`: `engine` (default) · `proxy` · `ui` · `preflight` · `probe` · `rekey` · `decrypt` · `measure` · `tripwire`. Hardens the process before any role runs. |
| `pseudexctl` | `live` | the ops CLI, one entry instead of six `docker run -e PSEUDEX_ROLE=…`: `doctor`, `probe`, `preflight`, `decrypt`, `diag`, `metrics`, `rekey`, `backup`, `restore`, `upgrade` (D-062: new image, same volume, rollback by itself or by snapshot). Ships in both images at `/app/pseudexctl`. Pinned by `test_pseudexctl.py`. |
| `issue_key.py` | `live` | mint a proxy tenant key (`sk-ps-…`) into `tenants.db` |
| `testkit.py` | `live` (dev only) | `load_dev_bundle()` — builds a bundle from `licensing/pack.py` and loads it in-process; every test/eval that detects calls it first. NO equivalent in the shipped image. |
| `requirements.txt` | `live` | not stdlib-only: `fastapi`, `uvicorn`, `httpx`, `phonenumbers`, `pymorphy3` + `pymorphy3-dicts-ru`, `natasha`, `pyrage` (age), `cryptography`, `sqlcipher3` |

### 3.2 Build

| file | status | what |
|---|---|---|
| `Dockerfile` | `live` | `pseudex:source` — the engine from `.py`; writes `pseudex/_release.py`; fails on `import sqlite3` in `pseudex/` |
| `Dockerfile.nuitka` | `live` | `pseudex:compiled` — same Debian release, engine compiled to a native binary; the three `build_*.py` steps (§3.2) run first |
| `build_strip_docstrings.py` | `live` | removes docstrings BEFORE Nuitka (`--python-flag=no_docstrings` leaves the literals in the constants blob) |
| `build_mangle_names.py` | `live` | renames PRIVATE crown symbols to opaque names before compilation (WS-1); `_release` is on its keep-list |
| `build_harden_strings.py` | `live` | hides the beacon strings of the licensing path from the compiled image |
| `deploy/tripwire/` | `live` | the tripwire's own container files |
| `THIRD-PARTY-NOTICES.md` | `live` | licences of what ships |

### 3.3 Tests — what each one pins

Run from `prototype/`; each loads the dev bundle itself.

| script | pins |
|---|---|
| `test_loop.py` | the core proof: no PII reaches the model, tool-call round trip restores real values (no LLM, no network) |
| `test_product.py` | tenancy, audit, streaming detok, the product layer offline |
| `vault_test.py` | canonicalization (`+7`/`8`/bare → one token) and persistence across restart |
| `test_perf_masking.py` | mask cache, audit dedup on cache miss, leak regression, loop responsiveness under load, the `/unmask_chunk` vs `/unmask_arguments` contract from both sides, the `requests` counter — against the real FastAPI app |
| `test_localui.py` | the operator surface: closed by default, reveals audited with `actor`, requests billed apart from entities, self-check excluded from billing |
| `test_localui_renders.py` | the interface in a REAL browser (playwright + chromium): a 200 and a CSP header are not evidence it executed |
| `test_persona_defects.py` | the five defects the 18.08.2026 persona run found and no corpus of ours did |
| `test_preflight.py` | worker arithmetic against the cgroup limit; what happens when N does not fit; the contract with `entrypoint.sh` (including probe 2 → 6 and migrate 5) |
| `test_schema.py` | the schema contract of a volume (D-058…D-060): fresh store stamped, legacy volume snapshotted and brought forward (snapshot opens with the same key), future volume refused untouched, no space refused before touching, the maxima equal `schema_lock.json` for the minor in `version.txt`, `probe` exits 2 and `migrate` brings a volume forward |
| `test_pseudexctl.py` | the ops CLI: command shapes, doctor verdicts (incl. the version ladder), the rekey proof, `upgrade` (order, secrets never in argv, both rollback branches, dry-run leaves nothing) |
| `test_collisions.py` | a substitute equal to a real value — both halves (backwards at mint, forwards via `minted_in`), and BOTH sides of the `pseudonym_scope` trade |
| `test_derived_forms.py` | transliteration and initials in a tool argument — in the model's own convention, resolved by the conversation |
| `test_notation_symmetry.py` | class А: the substitute inherits the SOURCE's notation (dictation, case, separators and region position, script) and the argument is rendered in the AGENT's, or the leaf's when the tool cannot execute a phrase; one interface (`notation.render_like`) for every seam, with the PHONE/СНИЛС/DOB controls that already worked |
| `test_argument_form.py` | a tool argument is restored VERBATIM in the agent's form (case, generic words); prose in agreement |
| `test_own_substitute_fixed_point.py` | class В: a part, a lone surname, initials, an oblique case, another script and a re-typing field key of the dialogue's OWN substitute are a fixed point of the mask (prose and JSON leaf), the engine's `REDACTED…` marker is a fixed point, and the boundary holds — a stranger reusing our surname, a bare given name, a Latin stranger, an address and another conversation all stay masked |
| `test_phone_hop_form.py` | fixed PHONE mint: three input forms × four numeric agent forms × both output legs; copied typo, separate identities, tenant and typed-numeric controls |
| `test_other_hop_forms.py` | current-hop form for SNILS, INN, CARD, PASSPORT, DOB, EMAIL and PLATE; fixed mints and literal expected values |
| `test_atomic_form_adversarial.py` | independent numeric/glyph, date and email-form attacks; unknown changed digits must not restore a known prefix |
| `test_spoken_date_form.py` | spoken day case at IN and both OUT legs; copied words, changed case and ISO share one identity |
| `test_spoken_identifier_form.py` | spoken PHONE grouping/case/hesitations, national notation, both OUT legs, no second mint, residual visibility, copied and rewritten SNILS with leading zeroes; not full arbitrary-speech acceptance |
| `test_tool_result_context.py` | standard call/result association: parallel same-name calls, reverse order, duplicate and missing IDs, invalid arguments, no future/cross-transcript evidence; not echo masking acceptance |
| `test_shown_form_ambiguity.py` | conflicting shown owners, replay/reopen and independent-connection safety; equivalent spelling and expiry controls; rewritten-conflict acceptance tracked in the sprint report |
| `test_name_subject_form.py` | finite verb subjects versus objects and known-gender NAME rewrites through the real detector and vault |
| `test_name_case_regression.py` | pinned random-name false alarm: literal accusative outputs and gender-aware morphology controls |
| `test_location_hop_form.py` | structured address leaves recomposed into one mention, prose/tool form parity and independent owners |
| `test_location_form_adversarial.py` | independent LOC attacks, including unresolved fragments and CAPS; a red suite is not an accepted fix |
| `test_address_composition.py` | class Б: the street TYPE survives on both legs and in a schema field (incl. a dotted path), `street`/`street_type` are two leaves of ONE street, one real street is one fake street whatever the house and the litera keeps two houses apart, and a fragment of a substitute resolves WHOLE or is named in `residual_tokens` |
| `test_digit_truncation.py` | class Д: a substitute's NUMBER survives its spelling — a run equal to the substitute's digits as a number (leading zeros dropped) resolves to the real value WHOLE and never to a positional slice of the canon, two owners of one number are a NAMED refusal, a named place (passport series/number, last four digits) still slices, and a run one digit from a substitute is reported in the residual without ever being resolved |
| `test_positional_slice_guard.py` | class Д (REVIEW-SPRINT.md point 4): the positional slice of the canon is licensed ONLY by a NAMED edge — `{"inn":"0084999497"}` no longer hands the tool 10 of 12 real digits and is NAMED, `{"x":"6984"}` does not slice like `{"last4":"6984"}`, while `last4` and the passport series/number still slice and a number written without its zeros restores WHOLE |
| `test_typo_inheritance.py` | class А (REVIEW-SPRINT.md point 1): a single damaged name after a naming cue is a NAME, the mint applies the SAME edit to the drawn fake (the damaged slot stays damaged, the clean slot clean), and the same damaged word in an address is not a person |
| `test_type_identity_linking.py` | class Б (REVIEW-SPRINT.md point 2): the street TYPE is identity in the old tolerant paths too — «переулок Пушкина 5» and «улица Пушкина 5» are two substitutes in both directions, while a writing with no type still links to the typed one |
| `test_one_person_one_mint.py` | class В (REVIEW-SPRINT.md point 3): a CRM card of three name fields and the same person as a whole string mint ONE substitute set whatever the order, and the tool gets the real parts back |
| `test_class_g_leaks.py` | class Г (five vectors): a Latin name is judged WORD BY WORD whatever its position (`Kukushkin Valeriy`, `Fomin Vyacheslav`, a lone `Kukushkin`) and the substitute mirrors the source script and resolves back; a bare lowercase word is granted a span by its anchor (`адрес репина` → LOC, `от аленчиев`/`к аленчиеву` → NAME, `на бибиревская` → LOC) while the measured negatives stay untouched; a typed PARENT key closes its children (`passport.series`/`.number` masked as 4/6-digit parts of ONE document, `address` still whole, and the parts rejoin on the tool leg); a substitute may not carry a whole word that is another person's real value in the conversation, and pool exhaustion fails CLOSED; and a phone that passes the СНИЛС checksum wins by BOUNDARY (the «+» included) while an equal-boundary or dashed СНИЛС does not move |
| `test_g3_passport_fail_closed.py` | class Г (REVIEW-SPRINT.md point 6): a typed passport parent closes its children FAIL-CLOSED — a lone `series`/`number`, a misspelled role (`seria`/`nomer`) and a non-digit part are each masked as a WHOLE passport substitute, never left open; the complete passport still mints two parts of ONE document and the `address` in the same payload stays closed |
| `test_g4_reverse_order.py` | class Г (REVIEW-SPRINT.md point 7): a substitute minted EARLIER is recognised by PART (a lone surname, surname+given) so it is not re-minted into a second person, while the FULL real name of a person appearing LATER whose surname equals the substitute's is masked, never passed as «ours», and that later person's substitute never carries the surname |
| `test_b_litera_composition.py` | class Б (REVIEW-SPRINT.md point 10): a house litera written as a separate word before a marker («34 в кв 9») is glued to the number BEFORE prepositions are dropped, so «34 в кв 9» ≠ «34 кв 9» while «34в» == «34 в», the dot after the marker does not matter, and «с» between two numbers stays «строение», not a litera |
| `test_v_redacted_deterministic.py` | class В (REVIEW-SPRINT.md point 13): a type with no renderer mints a DETERMINISTIC `REDACTED<6hex>` (digest of the value), not a random one — the same value is idempotent, and `cardholder` under a re-typing key stays a fixed point instead of becoming a fake card |
| `test_g_spent_words_crossworker.py` | class Г (REVIEW-SPRINT.md point 14): two `Vault` instances on ONE DB share the spent-word index — the second worker's snapshot is invalidated by the first worker's NAME insert (a `MAX(rowid)` point query, like `_shares_a_stem_in_conversation`) and refuses a substitute carrying the other's real word |
| `test_zh2_schema_notation.py` | class Ж (REVIEW-SPRINT.md point 5): the tool schema's declared leaf notation reaches the OUT leg — `unmask_arguments(leaf_notation={"snils":"snils"})` renders the real СНИЛС as `XXX-XXX-XXX YY`, an undeclared leaf keeps the agent's own form (never guessed), and the notation applies per leaf, not to the whole call |
| `test_error_echo_privacy.py` | S01 privacy gate: archived truncated spoken-phone echo, seven unbound-result shapes, ordinary-number and cross-conversation controls; E01 case-retyped cut form remains open |
| `test_date_association_dob.py` | a date personal ONLY by association (next to a СНИЛС/card/passport, no «рождения») is typed DOB, not DATE, so the vault mints a DOB fake and an unbound tool result echoing it is redacted instead of leaking; meeting and document dates stay real |
| `test_prose_fragments.py` | a piece or a derivative of a substitute in the ANSWER to the customer |
| `test_names_morphology.py` | gender, case and self-agreement of names; the round-trip guard |
| `test_hard_cases.py` | 967 lines of the awkward, the rare and the deliberately hostile — addresses, names, dates, KV |
| `test_overmasking.py` | 538 phrases of ordinary business/technical Russian with NO personal data (496 from MASSIVE's annotation): must stay unmasked; prints the Clopper-Pearson precision floor, not just the observed rate |
| `test_coverage_152fz.py` | a checklist of the personal-data types 152-ФЗ cares about — each one detected |
| `test_credentials.py` | credentials found when stamped by a vendor prefix, untouched when merely random (SHA, UUID, `pk_live_`, placeholders) |
| `test_detok_security.py` | detok surface hardening (pentest B1/B2/B4): every `/unmask*` writes a counts-only audit row and is rate-limited per org; a bound container (`PSEUDEX_ORG`) refuses other orgs; the preview shows ≤1 char at each end. B3 (`/unmask` reachable on an expired lease) is BY DESIGN |
| `test_memory_hardening.py` | the worker is non-dumpable and non-traceable |
| `test_tripwire.py` | a memory read is detected and attributed (WS-7) |
| `test_clock_freeze.py` | a frozen clock (LD_PRELOAD) does not extend a lease (pentest W2) |
| `test_tuning_lease_security.py` | A2 is closed: the tuning rides in the lease, there is no compiled blob and no static key |
| `test_unload_scrub.py` | leased-data caches are scrubbed on unload (H3) |
| `test_canary.py` | per-customer canaries survive into the leased gazetteers and identify a leaked bundle |
| `test_fingerprint.py` | the Tardos fingerprint survives a coalition |
| `test_watermark.py` | every leased bundle carries the customer's watermark |
| `test_metering_anomaly.py` | the fleet-wide anomaly report surfaces a silently root-patched counter (WS-6/M2) |
| `test_published_claims.py` | numbers PRINTED to the customer (landing, EULA) equal the numbers the code works by — and the replaced literals are ABSENT |

Not in `prototype/`: `licensing/test_*.py` (§2), `storefront/test_*.py` (§6),
`e2e/` gates (§5).

### 3.4 Evals and dataset generators (own corpora)

| script | status | what |
|---|---|---|
| `make_dataset.py` → `eval_detect.py` | `live` | golden set: 100 synthetic RU cases with checksum-valid PII; per-type recall/precision |
| `make_dirty.py` → `eval_dirty.py` | `live` | dirty set from the researched noise patterns: F2, FP/FN dump, hard-negative false-mask rate, type-aware miss and type-blind TRUE-LEAK printed apart. `pack_gates` P3 needs `dirty.json` and refuses BEFORE the Nuitka build without it |
| `make_stress.py` → `eval_stress.py` | `frozen` | adversarial set built to break the detector — built independently, never tuned against |
| `make_holdout.py` | `frozen` | large diverse hold-out; independent of the detector |
| `make_addr_real.py <out> <seed>` | `frozen` | address benchmark on a FRESH seed each time |
| `bench_masking.py` | `live` | O(n²) growing-transcript cost, cache on vs off. Uses `Vault(":memory:")` — cannot see the storage layer |
| `profile_latency.py` | `live` | part 1 offline per-message cost; part 2 real A/B (needs `PSEUDEX_UPSTREAM_KEY`). Same blind spot |
| `profile_deep.py` | `live` | three zoom levels on the masking bottleneck |
| `agent_demo.py`, `response_test.py`, `live_eval.py` | `live` (needs proxy on :4000 + `pseudex-dev` tenant) | a real tool-using agent through the proxy; the response leg shows the REAL phone; end-to-end with tool calls that USE personal data as logic |

---

## 4. `prototype/bench/` — instruments

Paths relative to `prototype/`. Every instrument here was built so that the
engine could FAIL on it; read `CLAUDE.md` § "Eval discipline" before changing
any of them. External corpora live in `~/.cache/pseudex-bench/`.

### 4.1 Benchmarks we built

The additive v5 hop audit uses `bench/agentpii5/cohort.py` (complete-only C/C2/I
composition with input hashes and excluded spend), `bench/agentpii5/actual_hops.py`
(versioned actual OUT diagnostic, no scheduled-turn requirement), and
`bench/agentpii5/hop_report.py` (offline manifest, old lines, actual events and
limits), and `bench/agentpii5/live.py` (real-time watch face of a RUNNING run:
recomputes the same metrics on the partial files — no provider, engine or
judge; the four hop-owner transitions and every rarer bucket are printed
beside the 13 sprint metrics). Pins: `bench/agentpii5/test_cohort.py`,
`bench/agentpii5/test_actual_hops.py`, `bench/agentpii5/test_hop_report.py`,
`bench/agentpii5/test_live.py`,
`bench/agentpii5/test_response_trace.py` (additive model-response chronology,
same-response tool batches, legacy absence and strict record validation).
It does not replace the historical observer or certify all NAME/LOC, IN,
answer, chain and paired metrics. Status and acceptance:
`docs/tz-hop-form-adaptation.md`, `research/hop-format-audit/PROGRESS.md`.
Before the next hop-form implementation or a proposed 450 rerun, consult
`docs/plan-hop-form-before-450.md`: evidence matrix, all current v5 types,
full-loop acceptance, open owner decisions and budget boundaries.

Owner's decision 2026-09-20: of the four AgentPII generations only **v4 is
live**; v1–v3 stay for the numbers cited from them and are not developed.

| package | status | what it measures | normative file | doc |
|---|---|---|---|---|
| `bench/agentpii/` | `superseded by agentpii4` | AgentPII-RU v1: Russian conversational PII through tool schemas, four registers (clean/chat/sloppy/voice), recall vs COVERAGE printed apart, round-trip axis | `bench/agentpii/schema.py` | `bench/agentpii/README.md` |
| `bench/agentpii2/` | `superseded by agentpii4` | v2: case schema and family taxonomy (families/, live/) | `bench/agentpii2/schema.py` | `docs/tz-agentpii2.md`, `bench/agentpii2/README.md` |
| `bench/agentpii3/` | `superseded by agentpii4` | v3: полнота on speech-like agent traffic; mined dispatch calls and reference forms (`bench/agentpii3/mine_*.py`, `bench/agentpii3/mined/`); audit + crosscheck. **The 69.6% NAME полнота number cited in CLAUDE.md is from here** — kept for that number, not for new work | `bench/agentpii3/schema.py` | `docs/tz-agentpii3.md` |
| `bench/agentpii4/` | `live` | v4 «шлюз не ломает агента»: three arms (control, control′, gateway) over a mock CRM; levels calls/fields/state; TOST at δ=3pp with cluster bootstrap; `autopsy`, `microscope`, `compare_runs`; fresh-seed corpora `bench/agentpii4/fresh5150/` … `bench/agentpii4/fresh8080/` | `bench/agentpii4/schema.py` | `docs/tz-agentpii4.md`, `bench/agentpii4/README.md`, `research/2026-09-05-agent-scenario-coverage.md`, `research/2026-09-06-benchmark-tiers.md`, `research/2026-09-07-benchmark-critics.md` |
| `bench/agentpii5/` | `live` | v5 «tool-result-first, форма на каждом хопе, живой агент»: a value's FORM is compared at every hop it crosses (`Hop`, `HopObservation`), not once at the tool. Contracts and rules: `bench/agentpii5/contracts.py` (hops, `CaseV5`, `ToolSpecV5`, form features, metric `Line`s + the refuse-to-report gate, judge I/O, the v4-vs-v5 side-by-side), `bench/agentpii5/schema.py` (R01–R23 per case, K01–K15 per corpus, the corpus snapshot), `bench/agentpii5/RULINGS.md` (the architect's decisions the builders were held to), `bench/agentpii5/CHECKLIST.md` (191 conformance items), `bench/agentpii5/briefs/` (one brief per component). Tools and backend: `bench/agentpii5/tools.py` (43 tools over 11 verticals, 8 return forms), `bench/agentpii5/mock.py` (the seeded CRM the three arms share). Form: `bench/agentpii5/form.py` + `bench/agentpii5/form_tables.py` (`form_match` per type and feature, with the ABSTAIN rule). Corpus: `bench/agentpii5/scenarios5/` (`bench/agentpii5/scenarios5/common.py` the builder, `bench/agentpii5/scenarios5/plan_a.py` / `bench/agentpii5/scenarios5/plan_b.py` the two halves, one module per behaviour — `retry_same_tool`, `same_tool_other_target`, `sequential_chain`, `parallel`, `fanout_pick`, `branching`, `user_in_loop`, `memory_anaphora`, `rag`, `document`), `bench/agentpii5/revise.py` (v4's 834 cases given a behaviour and hops, bytes untouched), `bench/agentpii5/build.py` (assemble, check, freeze the ladder). Run: `bench/agentpii5/harness.py` (the ONLY module here that imports `pseudex` — the gateway arm is the production path), `bench/agentpii5/records.py` (every run file, both ways), `bench/agentpii5/judge.py` + `bench/agentpii5/calibration.py` (the blind judge and its κ stamp). Read-back: `bench/agentpii5/observe.py`, `bench/agentpii5/metrics.py`, `bench/agentpii5/fixtures.py` (three fixtures per metric, one adversarial), `bench/agentpii5/report.py` (the side-by-side, refused metrics named), `bench/agentpii5/reportjson.py` (the same report as one versioned machine schema), `bench/agentpii5/live.py` (real-time watch face, engine-free; `--latest`/`--once`/`--web` — terminal or an HTTP page at `http://host:port/`). Acceptance: `bench/agentpii5/perfect.py` + `bench/agentpii5/test_perfect.py` — a PERFECT gateway must clear every bounded line and four WRONG ones must fail them, on the whole corpus; an instrument that cannot fail is not an instrument. The harness as a tool (`docs/tz-bench-harness.md`, D-066): `bench/agentpii5/runinfo.py` (the estimate before a dollar, the run registry the runs write themselves, and the refusal that keeps a key or a corpus value out of it), `bench/agentpii5/provider.py` (what answered and what masked, with prices and key NAMES), `bench/agentpii5/compare.py` (any run against any other, case by case, with the cluster bootstrap), `bench/agentpii5/microscope.py` (one case whole, no model and no spend), `bench/agentpii5/trend.py` (the runs by date), `bench/agentpii5/repro.py` (the one command that repeats a run), `bench/agentpii5/quarantine.py` (cases unstable at ALL arms — a defect of the CASE; it prints and never marks). One `test_*.py` per module, each a script with `main()`; imports `bench/agentpii4/`; the base gateway exposes one no-op request-capture hook so v5 records the exact existing mask result without another mask pass | `bench/agentpii5/contracts.py` | `docs/tz-agentpii5.md`, `wiki/BENCHMARK.md`, `research/2026-09-22-toolresult-derisk.md` |
| `bench/agentpii5/payload_canaries.py` | `live` | Case-declared S02 canary manifest with raw-payload placement, exact model-request snapshots and boundary scan; missing, duplicate and oversized captures or missing I-arm rows are `NOT_MEASURED`, never a clean result. `bench/agentpii5/test_payload_canaries.py` pins the scanner and `bench/agentpii5/test_payload_canary_integration.py` pins the gateway capture seam. Saved 450 runs have no manifest and remain unmeasured. | `bench/agentpii5/payload_canaries.py` | `docs/plan-hop-form-before-450.md`, `research/hop-format-audit/PROGRESS.md` |
| `bench/agentpii5/test_spike_e.py` | `live` | Класс Е of the hop-format sprint: the OUT leaf funnel answers ONE fact per status (`observed` / `residual` / `engine_kept` / `not_masked` / `leaf_foreign` / `absent` — `unmasked` used to be three of them at once), the strict headline denominators stay the corpus's and the engine's honest share is published BESIDE them (`end_to_end_written` + the `out_*` counts), `optional` is read off the LEAF and off the generic role (`GENERIC_PIECE_ROLES`), and a declared hop is satisfied by the semantically equal leaf the run really wrote (`contracts.LEAF_EQUIVALENCE`, an AUTHORED table, never a guess off a tool name). Runs the real observer and the real metric functions on hand-built records, no model and no network. | `bench/agentpii5/test_spike_e.py` | `research/hop-format-audit/SPIKE-Е.md`, `research/hop-format-audit/DECISIONS-SPRINT.md` |
| `bench/agentpii5/test_spike_zh.py` | `live` | Класс Ж of the hop-format sprint: the VALUE question («did this leaf receive THAT value») is answered by ONE table (`contracts.VALUE_NORMALISERS`) through ONE predicate (`observe.values_equal`) with three thin callers (`metrics.value_matches`, `observe.part_matches`, `revise._same_value` — a third copy that had already drifted); NAME compares as a multiset of parts, LOC by the roles street/house/flat, PLATE squeezed, the digital documents by digits, a date by ISO, and PHONE by the last ten digits **plus the prefix class** (the one place the value line deliberately does not reduce to the needle layer: `+1…` ≠ `+7…`); `script` is the ALPHABET and `translit` the ROMANIZATION SYSTEM, abstaining on `latin:unknown`; and the tool schema is the authoritative notation marker (`tools.LEAF_NOTATION`, proved against each leaf's own parser by rule V08) while the value line stays notation-blind. Runs the real comparator on hand-built pairs — no model, no network, no engine. | `bench/agentpii5/test_spike_zh.py` | `research/hop-format-audit/SPIKE-Ж.md`, `research/hop-format-audit/DECISIONS-SPRINT.md` |
| `bench/agentrun/` | `live` | paired runs on BFCL tasks with injected Russian PII (`bench/inject_ru_pii.py`): did putting Pseudex in the path cost anything; `bench/agentrun/gpu/` + `bench/agentrun/GPU.md` for a local model | — | `bench/agentrun/GPU.md` |
| `bench/fragments/` | `live` | **Б29: переписывает ли возврат числа, которых шлюз не подменял, и возвращает ли он те, что подменял.** Прибор меряет ОБЕ стороны и ни одна не главнее: «наше не вернулось» (делится на видимое и ТИХОЕ) против «чужое переписано» (молчит всегда). Режет по поверхности (аргумент · проза · поток · обратный прокси), по области (разговор назван · не назван · `pseudonym_scope=customer`) и по НАПОЛНЕННОСТИ хранилища — дефект арифметический, и на пустом волте его не видно. Чужие числа строятся так, чтобы столкновение с цифрами выданных подмен было неизбежным, а не случайным. Предшественники (инструменты ложных тревог пятого захода по адресам) слали подмену дословно и поля порознь, поэтому показывали ноль там, где было 12 из 12 молчащих потерь. Модели не зовёт, денег не тратит: агента имитирует скрипт, движок настоящий, путь продуктовый | — | `docs/known-issues.md` (Б29) |
| `bench/gate/` | `frozen` | the ceiling of the dictionary gate: 600 hand-labelled OCCURRENCES pinned to a snapshot; the live detector re-runs and prints MOVEMENT | `bench/gate/labels.json` | `bench/gate/README.md` |
| `bench/voice/` | `frozen` | real taxi-dispatch transcripts (RuDevices), addresses hand-labelled in two strata (400 marker-carrying + 250 of 4 805 number-only; weight the second 250/4805); `bench/voice/score.py` filters to LOC | `~/.cache/pseudex-bench/rudevices_addresses.json` | `bench/voice/README.md` |
| `bench/runs/` | `frozen` | measurement outputs by date (2026-09-01 … ); `README.md` says what each run answered. Never edit. | — | `bench/runs/README.md` |

### 4.2 Evals on corpora we did not write

| script | corpus | question |
|---|---|---|
| `bench/eval_external_ner.py <NEREL> --splits dev,test` | NEREL | recall on a corpus we did not write (PERSON 91.5%, Cyrillic 92.3%) |
| `bench/eval_external_precision.py <NEREL>` | NEREL | what we mask that no annotator labelled; 1 922 spans → the error budget at 99.4% is 12 spans |
| `bench/eval_massive_ru.py` | MASSIVE ru-RU (16 521 utterances, CC BY 4.0) | полнота on third-party speech: NAME 68.0%, `place_name` 0.1% is CORRECT (bare cities are refused by law) |
| `bench/eval_piibench.py` | hivetrace PII-Bench | Russian chat-register PII; prints TWO totals (КПП/ОГРН identify a legal entity) |
| `bench/eval_noise_ladder.py --dataset dataset.json` | own | where detection breaks on live chat, rung by rung |
| `bench/eval_noise_by_type.py dataset.json` | own | the same ladder BY TYPE — who exactly breaks |
| `bench/eval_gar_cut.py` | ГАР | where to cut the street vocabulary and what each cut costs (`STREET_MIN_OBJECTS = 1`) |
| `bench/eval_overmasking_volume.py` | `~/.cache/pseudex-bench/ru_prose.jsonl` (Wikipedia, `bench/fetch_ru_prose.py`) | over-masking on VOLUME of ordinary prose |
| `bench/eval_vault_precision.py` | real speech | how many PROTECTED values are not personal data |
| `bench/eval_canaries.py` | real messages + known PII | known PII planted into REAL messages |
| `bench/eval_disagreement.py` | real traffic | what the INDEPENDENT baseline (`bench/_baseline_independent.py`: bare Natasha + naive regex, none of our dictionaries) finds and we do not |
| `bench/eval_metamorphic.py` | own | metamorphic relations on addresses and names — an invariant, not a labelling |
| `bench/blocking_recall.py` | — | recall of the deletion-neighbourhood index |
| `bench/fuzz_registers.py` | — | every way one value can be written, mechanically |
| `bench/leak_check.py` | a run's log | did any REAL personal data reach the model |
| `bench/compare_arms.py` | paired run | what putting Pseudex in the path cost |
| `bench/fetch_ru_prose.py`, `bench/fetch_ru_speech.py` | — | corpus fetchers (Wikipedia prose; real call transcripts) |
| `bench/build_name_dicts.py` | — | extracted the name dictionaries into `licensing/data/` (one-off) |
| `bench/run_all.py`, `bench/summarize_run.py` | — | the whole battery in one run; headline numbers of one run into one document |
| `bench/public_row.py` | — | produces OUR own row in the public benchmark the way anybody else's is made: starts a real sidecar and runs the PUBLIC harness against it over HTTP, so nothing of the engine reaches the benchmark but its endpoint answers. Also prints the corpus-name overlap our leased gazetteers already hold, which the benchmark itself cannot see |

---

### Optional v5 model connectors

`prototype/bench/agentpii5/connectors.py` defines agent/judge I/O contracts;
`prototype/bench/agentpii5/deepseek_connector.py` implements the direct stateless
Responses API loop for DeepSeek Flash; `prototype/bench/agentpii5/codex_connector.py`
implements an OpenAI Agents SDK `Model` backed by the pinned Codex SDK and a clean,
dedicated ChatGPT-subscription home for the judge.
`prototype/bench/agentpii5/requirements-codex.txt` is optional, benchmark-only.
`prototype/bench/agentpii5/test_connectors.py` checks gateway hooks, JSON boundaries,
usage accounting and the existing judge quote gate without a model.
The existing Claude path remains the default; the same harness, corpus and
observer serve both paths. Spec and point-test limits:
`docs/tz-v5-model-connectors.md`. New-connector resume/calibration are not yet supported;
nano requires owner GO.

## 5. `prototype/e2e/` — the gates

Definition of done for the licensing layer and packaging. They run against REAL
containers, never mocks, and are themselves audited.

| file | what |
|---|---|
| `e2e/gates.py` | L1–L25 (+L2b): lease, renewal, grace, revocation, vault encryption/migration/rekey, preflight, memory scan, tokens, billing counter (L12), the schema of the volume (L25 pre-versioned volume snapshotted and brought forward, L24 a future volume refused untouched with exit 6), against a local stand (`deploy/compose.local.yml`). `--only L4,L5` for a subset; `--image pseudex:compiled --skip-build` with `PSEUDEX_SIGNING_KEY` to reuse a build. ~15 min |
| `e2e/pack_gates.py` | P1–P11 on the compiled image: no `/app/pseudex`, no docstrings (`grep -a`), parity with the source tree (P3 via `e2e/parity.py` on `dirty.json`), latency, stdlib-SQLite cannot open the volume (P9), no `sqlite3` import… Builds BOTH images unless `--skip-build` |
| `e2e/parity.py` | P3: the compiled image detects EXACTLY what the source tree detects |
| `e2e/audit_gates.py` | the gate over the gates: every NEGATIVE atom needs a POSITIVE atom over the same source; `--selftest` on 13 fixtures REFUSES to report unless it separates them. Runs in the battery as `62-gate-audit` |
| `e2e/lint_tests.py` | mechanical gates against checks that cannot fail: swallowed failures, unreachable and duplicate checks |
| `e2e/memscan.py` | search a running process's memory for a string (L14) |
| `e2e/fixtures.py` | the personal data the gates push through a real instance; `leak_values` for the memory scan |
| `e2e/certs.py` | self-signed CA + server cert for the stand |
| `e2e/load_licensing.py` | load test of the licensing server (`docs/tz-license-packaging.md` §2.6.4): boots the REAL server in-process, drives N processes (default 10 000) across enterprise-cap keys, measures `/v1/lease` `/v1/meter` `/v1/usage` p50/p99 + RPS + error rate + DB growth, PASS/FAIL against thresholds named in the file. Container-side (RSS, vault/audit.db) is a separate soak, its bars in `CONTAINER_THRESHOLDS` |

The stand builds `pseudex:local`; the gates build `pseudex:source` — DIFFERENT
verification keys, never share the tag.

---

## 6. `storefront/` — landing, signup, cabinet, console, billing

Django on our infrastructure. Shares no code with the engine and MUST NOT: the
storefront never sees personal data, the engine never depends on the shop. Talks
to the licensing server through ONE connector (`storefront/billing/licensing.py`) with
`PSEUDEX_LICENSE_STOREFRONT_TOKEN`. Run and test commands: `storefront/README.md`.

| app / file | what |
|---|---|
| `storefront/pseudex_site/` | settings (no `PSEUDEX_SECRET_KEY` → refuses to start unless `PSEUDEX_DEBUG`), URL map, `storefront/pseudex_site/context.py` (numbers the templates must see so text never diverges from code), `storefront/pseudex_site/logfmt.py` (JSON logs) |
| `storefront/storefront_web/` | the pages; `storefront/storefront_web/detection_types.py` (what the engine finds and does not — the configurator's data); `storefront/storefront_web/middleware.py` (security headers); `storefront/storefront_web/engine_release.py` (the image the site advertises — the floating minor of the newest cycle from the synced registry, `latest` without a file, `PSEUDEX_DOCKER_IMAGE` as the only override; D-061) |
| `storefront/accounts/` | users, organisations, `storefront/accounts/payer.py` (who the customer is, as THEY state it) |
| `storefront/billing/` | `storefront/billing/models.py` (Plan, Subscription, Key, Invoice, Offer), `storefront/billing/services.py` (ALL state changes in one place), `storefront/billing/payments.py` (ЮKassa: cards, СБП, invoice link), `storefront/billing/licensing.py` (connector to the licensing admin API), `storefront/billing/slots.py` (the one reading of `/admin/instances` both screens draw: occupancy is the server's number, never the length of the list, and its silence is «неизвестно», never zero), `storefront/billing/reconcile.py` (our invoice vs the customer's own gateway log), `storefront/billing/onboarding.py` (the coding-agent onboarding prompt); commands `run_billing_cycle` (the ONLY caller of the billing primitives, hourly as its own compose service, idempotent by a DB row) and `seed_plans` |
| `storefront/ops/` | operator console (all customers, one customer, report chains, plans), first-party analytics (`storefront/ops/analytics_models.py`, `storefront/ops/collect.py` — daily salt, bot filter), demand for detection types we lack (`storefront/ops/models.py`), Yandex Metrika/Direct API + server-side conversions (`storefront/ops/yandex_api.py`, `storefront/ops/yandex_views.py`); commands `daily_digest`, `enroll_totp`, `rollup_analytics`, `yandex_auth`, `yandex_conversions` |
| `storefront/templates/`, `storefront/static/` | pages, the configurator JS, generated images (`storefront/make_favicons.py`, `storefront/make_og_cover.py`, `storefront/make_ad_images.py` — from the SVG, never hand-drawn) |
| `storefront/docs/` | the storefront's own specification, moved here from the root `docs/`: `storefront/docs/tz-site.md` (what the site must do), `storefront/docs/tz-site-stack.md` (stack choice and what was rejected). Its README links them as docs/tz-site.md relative to storefront/ |
| `storefront/run_all.py` | the whole storefront in one command, «прошло» and «не гонялось» separated |
| `storefront/testkit_otp.py` | sign in to the console FROM A TEST, with the second factor |

Tests (`storefront/test_*.py`): `test_storefront` (against a REAL licensing
server) · `test_billing_lifecycle` (landing → container on a mock provider;
asks the server for `window_seconds`; POSTs `/mask` into a live container after
every state transition; the container-stopping check goes LAST) ·
`test_billing_e2e` (the REAL ЮKassa test shop) · `test_annual` · `test_hardcap`
· `test_offers` · `test_paywall` · `test_passwordless` · `test_admin_2fa` ·
`test_auth_style` · `test_signup_forms` · `test_configurator_renders` and
`test_ops_renders` (real browser) · `test_engine_release` (the advertised image comes from the registry: override → file → `latest`, reload on replace, the landing shows the same tag) · `test_seo` · `test_crawler_allowlist`
(fail2ban allowlist) · `test_deploy_references` (SQL names in deploy scripts vs
real tables) · `test_analytics` · `test_yandex_api` · `test_overage_toggle` (переключатель овереджа: ВЫКЛ → стоп на включённом без начисления, ВКЛ → служит и копит по ставке; переключение меняет зону; уже начисленный период не пересчитывается) · `test_slots` (real browser: показ по объёму/инстансам после удаления слотов; молчание сервера — «неизвестно», а не ноль) · `test_slots_stand` (STAND: runs the real `licensing.devserver` under the engine's interpreter and captures the `/admin/instances` bodies the screens render, so no screen check rides on a hand-written response).

Docs: `docs/sprint-cabinet-and-pricing.md`, `docs/billing-integrity.md`,
`docs/metering-integrity.md`, `docs/tz-verticals-and-configurator.md` (design),
`docs/payment-provider-request.md`, `docs/rkn-notification.md`,
`research/2026-08-15-ru-payments.md`, `research/2026-09-17-yandex-offline-conversions.md`,
`research/2026-09-14-legal-launch-audit.md`.

---

## 7. `deploy/` and CI

### 7.1 `deploy/` — our production host

| file | what |
|---|---|
| `deploy/compose.yml` | OUR side: licensing server, storefront, their database, the billing-cycle service, observability. `$VAR` in `command:` is interpolated by compose — escape as `$$VAR` |
| `deploy/compose.local.yml` | the whole product on one machine (the stand the gates and `deploy/local.sh` use); builds `pseudex:local` |
| `deploy/local.sh` | brings the stand up and PROVES it is up (a 401 from the admin port is proof of life) before printing the walkthrough |
| `deploy/bootstrap.sh` | clean Ubuntu 24.04 → production host, one idempotent command |
| `deploy/agent.sh` + `deploy/systemd/pseudex-agent.service`, `.timer` | the deploy the host performs ITSELF on a timer |
| `deploy/releases.json` | the versions registry (D-054): `cycles[]` newest→oldest with `state`, `eoas`, `eol`, `eol_announced`, `latest{version,date,digest}`, `aliases`; `notices[]`. Written by `.github/workflows/release.yml` (`record`), edited by hand only for `eol`/`eol_announced`/`notices` through a PR; validated by `.github/workflows/checks.yml`; read by the licence server and the storefront through the copy the agent syncs (stage 3) |
| `deploy/shipped_paths.sh` | the files that make up the customer image, derived from the `COPY` lines of `prototype/Dockerfile.nuitka` — the one definition both the commit lint and the «empty engine release» refusal read |
| `deploy/lint_engine_commits.sh` | refuses a visible-type commit («feat/fix/security/perf/build/revert») that touches `prototype/` and nothing shipped: it would mint an engine version for an unchanged image. Runs in `.github/workflows/checks.yml` |
| `deploy/version.txt`, `storefront/version.txt`, `prototype/licensing/version.txt` | the platform stream's version files (release-please `simple` strategy, linked as one component) — bumped by the Release PR, never by hand |
| `deploy/CHANGELOG.md`, `storefront/CHANGELOG.md`, `prototype/licensing/CHANGELOG.md`, `prototype/CHANGELOG.md` | `generated` — the changelogs release-please writes in each Release PR from the visible commit types (D-052); never edited by hand, the engine's one ships nowhere |
| `deploy/test_agent.sh` | the agent's DECISIONS without docker: follows «platform/v*» only, compares «platform/v0.3.16» with `v0.3.15` by number (raw `sort -V` puts `p` before `v` and would refuse every release as a downgrade), refuses a real downgrade, refuses an identity that cannot match platform tags, waits when no platform tag exists. Runs in `.github/workflows/checks.yml` |
| `deploy/watch.sh` | the watchdog: `docs/operations.md` §5 turned into a mechanism; also warns when a cycle's `eol` is ≤ 30 days away and containers still run on it (`/admin/versions`, D-056) |
| `deploy/backup.sh`, `deploy/restore-drill.sh` + `deploy/systemd/pseudex-restore-drill.service`, `.timer` | nightly backups of both databases; the weekly drill restores yesterday's and asks `licensing/verify.py` whether it is alive |
| `deploy/housekeeping.sh` + `deploy/systemd/pseudex-housekeeping.service`, `.timer` | weekly disk cleanup, on its own timer |
| `deploy/notify.sh` | one alert channel (Telegram) for deploys, the watchdog and backups |
| `deploy/Caddyfile` | TLS, HSTS, security headers |
| `deploy/prometheus.yml`, `deploy/alerts.yml`, `deploy/alertmanager.yml` | scrape targets with token; few alerts ON PURPOSE |
| `deploy/loki.yml`, `deploy/promtail.yml`, `deploy/grafana-dashboard.json`, `deploy/grafana-provisioning/` | logs by LABEL (content not indexed); the one dashboard |
| `deploy/fail2ban/` | jails + the crawler allowlist (`storefront/test_crawler_allowlist.py`) |
| `deploy/supportbot/` | the Telegram support bot container |
| `deploy/make-release-keys.sh` | the Ed25519 pair: public half compiled into the release binary, private on the server. A fresh one forces a full Nuitka rebuild |
| `deploy/build-arkari-clang.sh` | the obfuscating clang for the Nuitka build — one time, pinned |
| `deploy/check-dns.sh` | what the OUTSIDE world thinks of the domain |
| `deploy/simulate.py` | synthetic, obviously fake people for demos |
| `deploy/secrets/` | gitignored: `license-admin-token`, `tg-bot-token` |
| `deploy/Dockerfile.backup` | the backup container |

Docs: `docs/operations.md` (the operational spec), `research/2026-09-14-devops-audit.md`,
`research/2026-08-15-hosting-domain.md`.

### 7.2 `.github/workflows/`

| workflow | trigger | what |
|---|---|---|
| `.github/workflows/checks.yml` | every push, every PR | the engine suite without containers: `test_loop`, `test_tuning_lease_security`, `test_watermark`, `test_canary`, `test_clock_freeze`, `test_detok_security`, `test_tripwire`, `test_memory_hardening`, `vault_test`, `test_coverage_152fz`, `test_product`, `test_localui`, `test_hard_cases` (+ storefront jobs) |
| `.github/workflows/gates.yml` | nightly 01:00 UTC + dispatch; the vault slice on push to the paths it guards | `make_dirty` → `pack_gates` (both images) → `gates.py --image pseudex:compiled --skip-build`; on dispatch a subset via `ONLY`. The nightly full run goes only when the shipped set, `e2e/` or `licensing/` changed since the last GREEN nightly (job `nightly-needed`, diff against its `headSha`), and every Monday regardless — ~50 runner-minutes a night otherwise proved that yesterday's image is still yesterday's |
| `.github/workflows/release.yml` | tags `v[0-9]*` and «platform/v[0-9]*» | one file, two streams (the cosign identity the host trusts is this file's name): engine — tag equals `prototype/version.txt`, the shipped set (`deploy/shipped_paths.sh`) changed since the previous engine tag or red, aliases from the registry, anonymous pull of every ref, digest signed, `chore(registry): pseudex X.Y.Z` committed to `main`; platform — four images, closed to anonymous, signed |
| `.github/workflows/backport.yml` | a PR merged into `main` | when the PR carries a `security:` commit that touches the image (`deploy/shipped_paths.sh`), opens a cherry-pick PR of the WHOLE PR into every live «release/*» branch (korthout/backport-action, pinned) — so an engine security fix is its own PR; the only way commits reach a support branch (D-057). A direct push needs a manual `git cherry-pick -x` |
| `.github/workflows/release-please.yml` | every push to `main` or a «release/**» branch; dispatch from `.github/workflows/release.yml` | keeps one Release PR per stream (engine `vX.Y.Z`, platform «platform/vX.Y.Z») on the branch the push came to (`target-branch`); on merge waits for green checks, creates the tag and GitHub Release, dispatches `.github/workflows/release.yml` explicitly (a GITHUB_TOKEN tag push fires no `tags:` trigger). Replaced the former «ship.yml» (D-052) |
| `.github/workflows/uptime.yml` | every 10 min | is production answering |
| `.github/workflows/backup-audit.yml` | daily 06:20 UTC | did last night's backup happen and is it readable |
| `.github/zizmor.yml`, `.github/dependabot.yml` | — | workflow linting; dependency updates |

---

## 8. Everything else

| path | what |
|---|---|
| `docs/` | 27 documents — see INDEX.md for what each answers and which are superseded |
| `research/` | 50 documents — see INDEX.md |
| `brand/` | `brand/README.md`, logo/landing/UI mock-ups as `brand/*.dc.html`, `brand/ad-images/`, `brand/uploads/`, `brand/support.js`, bot avatar |
| `e2e-personas/` | `e2e-personas/REAL-LLM.md` (why personas call a live model; the key lives in `prototype/.env.local`), `e2e-personas/harness.py`, five personas (`e2e-personas/personas/`), findings by date (`e2e-personas/findings/`) — the 18.08.2026 run is what `test_persona_defects.py` pins |
| `release-please-config.json`, `release-please-config.release.json`, `.release-please-manifest.json` | the two release streams (D-052): packages `prototype` (engine, `exclude-paths` licensing/bench/e2e) and `prototype/licensing` + `storefront` + `deploy` (platform, linked); NO root package; per-package `version.txt`. The `.release.json` variant holds the `prototype` package only and is what `.github/workflows/release-please.yml` uses on «release/**» branches — the platform is never released from a support branch; `.github/workflows/checks.yml` pins the two configs equal on that package |
| `.trivyignore` | accepted CVE findings for the images |
| `.claude/skills/`, `.claude/worktrees/` | project skills; agent worktrees hold STALE copies of `CLAUDE.md` |
<!-- wiki:MAP:end -->
