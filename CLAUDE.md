# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
python3 test_collisions.py     # подмена, совпавшая с настоящим значением: обе половины
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

python3 e2e/gates.py                              # L1-L21 (+L2b), licensing + vault, ~15 min
python3 e2e/gates.py --only L4,L5                 # a subset while iterating
python3 e2e/pack_gates.py                         # P1-P9, packaging (builds both images)

# TWO keys are COMPILED INTO the release binary, so a fresh either forces a full
# Nuitka rebuild: the Ed25519 verification key AND PSEUDEX_TUNING_KEY (which seals
# the tuning blob and must match the server, which delivers it in the lease). Pass
# BOTH values an image was built with to reuse it with --skip-build:
PSEUDEX_SIGNING_KEY=<base64> PSEUDEX_TUNING_KEY=<base64> python3 e2e/gates.py --image pseudex:compiled --skip-build
PSEUDEX_SIGNING_KEY=<base64> PSEUDEX_TUNING_KEY=<base64> python3 e2e/pack_gates.py --skip-build
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
| Paths | `/mask`, `/unmask`, `/unmask_chunk`, `/spans`, `/health` | `/status`, `/events`, `/stats`, `/stats.csv`, `/reveals`, `/subscription`, `/diagnostics`, `/selfcheck`, `/reveal` |
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
- Split rule for what is an asset: **in the LEASED bundle, only the semi-public BULK that rotates
  (name lists, ГАР streets — open data); in the BINARY, every algorithm AND all the authored TUNING**
  (cue words, address regex, priority table, look-alike folds, key→type map). СНИЛС checksums stay
  in the engine; 28k names lease. The tuning USED to lease and was inverted: a client with root
  decrypts their own bundle in one step, so leased tuning was readable — it now rides compiled into
  the engine as an opaque `zlib+hex` blob (`licensing/pack.py::emit_tuning_module` →
  `pseudex/_tuning_blob.py`, merged at load by `assets.py`), so reconstructing it needs REVERSING the
  binary, not a bundle dump. Matching protection to change-rate: bulk drifts (lease + rotation), tuning
  is stable (static barrier). The lease still gates detection — no bulk, no names/streets, no output.

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
  the model sees a stable identity across turns. Detokenization returns the *canonical* form.
- **Format-preserving, checksum-INVALID tokens**: a fake СНИЛС/ИНН/card is deliberately generated
  to fail its own checksum, so a token can never collide with a real person's ID.
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

## Rules that changes must not break

- **Fail-closed.** Any error in masking must propagate to a 5xx. Never fall back to passing text
  through unmasked — the caller treats an error as a block, and that is the whole safety story.
- **No PII pre-filter, ever.** A `maybe_contains_pii` gate existed and was removed: it silently
  stopped being a superset of the recognizers (Latin names, `{"name":"john"}`) and leaked raw PII.
  A pre-filter would have to stay a perfect permanent superset of every recognizer's triggers.
  The content cache already removes the repeated-work cost; detection always runs.
- **Never re-feed masked output into detection.** `mask(mask(x)) != mask(x)` — a fake phone is a
  valid phone shape. The cache keys on RAW content for exactly this reason; "skip already-masked
  messages" is a wrong optimization.
- **Keep normalization 1:1.** Any substitution that changes length breaks every span offset
  downstream, including `/spans` (which the UI uses to highlight the *original* text).
- **`_morph_compat` must be imported before any `from natasha import …`** — it aliases
  pymorphy2→pymorphy3 at module-load time, and natasha binds the name eagerly.
- **`/spans` and `peek_token` are read-only** — rendering a dialog must never mint tokens or
  write audit.
- Audit stores type + token + a masked preview only. It is not a second PII surface; the full
  value lives only in the vault (and `/reveal`, on explicit request).
- **Every `/reveal` is recorded, and `actor` is required.** The record holds who / which token /
  when — never the value, or the access log becomes the second copy of the data the vault exists
  to contain. Misses are recorded too: a sweep of guessed tokens leaves no other trace. The ENGINE
  writes it, not the UI — a log written by the caller about itself is not a log, and `curl` against
  the sidecar is a supported shape.
- **`requests` is a request counter, not `sum(entities)`.** It was the latter, so a plan sold as
  "100 000 запросов" was consumed once per detected VALUE — several times faster than quoted and
  impossible to reconcile against the customer's own gateway log. A request that finds no PII is
  still billable, so it cannot be derived from the events table.
- The self-check runs the REAL `/mask` + `/unmask` under `SELFCHECK_ORG`, which `billing_totals`
  excludes: a customer proving our product works must not pay for it.
- **No bundle means no detection, not less detection.** `names.py` used to treat an empty
  dictionary as a supported state; that is inverted now. A gateway detecting with half its
  gazetteer leaks silently, which is worse than a stopped service.
- **A leased regex carries its own case flag** (`(?i)` inside the pattern source). Applying
  `re.IGNORECASE` uniformly at compile time turned the marker-less address pattern's
  `[А-ЯЁ][а-яё]+` from "a Capitalised word" into "any word" — "течение 12" became an address, and
  those inflated LOC spans outranked NAME and swallowed real people (-12 PERSON on NEREL).
- **`pseudex/` must never import from `licensing/`.** The licensing package holds the assets; an
  import would drag them into the image and defeat the lease. Shared code goes the other way
  (`pseudex/bundle.py` is imported BY the server).
- The engine writes nothing to its own filesystem (`PYTHONDONTWRITEBYTECODE=1`), so "did the
  container write a file" has a clean answer — gate L5 depends on it.
- **`pseudex/` must never `import sqlite3`.** Stdlib sqlite3 accepts `PRAGMA key` WITHOUT raising
  and writes plain text, so `except ImportError: import sqlite3` is a product that claims
  encryption and silently has none. One driver (`sqlcipher3`), no branch; both Dockerfiles fail
  the build on such an import, and P9 proves it from outside by opening the release image's own
  volume with stdlib SQLite. The driver's exception classes are NOT subclasses of the stdlib
  ones — not `IntegrityError`, not `OperationalError` — so handlers name the ones exported from
  `sqlite_setup`.
- **A SUBSTITUTE IS DRAWN FROM THE SAME STRING SPACE AS REAL VALUES, so sooner
  or later it IS one.** A fake name is a well-formed name, a fake address a
  well-formed address, a fake date a real date — and then one string means two
  people at once. Backwards, the model writes the substitute and detokenization
  hands the tool the OTHER person's data, sometimes a chimera («Кирилл Бородин»
  restored as «Ян Бородин», each word resolved against a different row).
  Forwards, the real bearer arrives in the traffic, `is_minted_token` says «this
  is ours» and sends them to the model IN THE CLEAR, for ever. Measured on 2979
  real people from NEREL: 3-7 backwards and 2-3 forwards per run, plus 10 dates
  of birth per 800 once DOB started minting a date instead of `REDACTED…`. The
  two halves need different answers, and neither answers the other:
  * BACKWARDS is knowable at mint time — the real value is already in the vault
    — so `_unique_token` refuses a candidate equal to any `canonical`, any
    `canonical_fold`, or the value being minted for right now. That last one is
    not pedantry: the row does not exist yet, and «15.06.1963» was minted as
    «15.06.1963» — a date masked into itself and thereafter skipped for everyone
    who shares it. Written as one `OR` the check planned a scan of every row the
    customer has (1.27 ms at 20 000 rows, on a path that runs up to 200 times);
    `UNION ALL` gives each branch its own covering index and costs 2 µs.
  * FORWARDS is not knowable at mint time, and the discriminator is the
    CONVERSATION. Our own substitute comes back to us inside the dialogue it was
    handed to; a customer's contact who happens to bear that name walks in from
    another one. `tokens.minted_in` carries it and `is_minted_token` compares.
    A NULL (a row minted before the column) and an empty scope both behave as
    before — a caller that named no conversation has nothing to compare.
- **AGENT MEMORY IS AN ECHO FROM ANOTHER DIALOGUE, and the conversation scope
  reads it as a stranger.** Every long-term memory store in the field keys by
  USER, not by conversation (LangGraph Store, Mem0, Google ADK, Anthropic's
  memory tool; `fork` and a per-agent handoff session arrive at the same place
  by other means), so the text the host injects carries the substitute the model
  was shown in an earlier dialogue. Judged at conversation scope it is masked a
  SECOND time and the tool receives the FIRST dialogue's fake — 200 OK, empty
  residual list. Widening the question costs a real person: `is_minted_token`
  is also what stops us masking somebody who bears a name minted elsewhere, and
  at customer scope they reach the model in the clear (2-3 per run on 2979
  NEREL people). So the default does NOT move — 152-ФЗ counts the leak, not the
  broken tool call — and a host with memory declares it: `pseudonym_scope` on
  `/mask`, `PSEUDEX_PSEUDONYM_SCOPE` for the process. `Vault.with_pseudonym_scope`
  holds the argument; `test_collisions` pins BOTH halves of the trade, because a
  price stated only in a comment is a price nobody re-measures.
- **The role of the message is NOT that discriminator, and using it would leak
  everything.** The answer is detokenized before it is returned, so the assistant
  messages the customer re-sends carry REAL values, not tokens. «assistant means
  echo, do not mask» would hand the model every real value it ever mentioned, on
  every later turn. Demonstrated, not argued.
- **The conversation scope has a price and it is identity churn.** A derived
  `conversation_key` reads the first two messages, so a trimmed transcript is a
  new conversation and that dialogue's own substitutes are re-masked: the person
  gets a second pseudonym mid-conversation and the entity is billed again. The
  round trip still returns the real value (measured) — this costs coherence, not
  correctness — and it is one more reason a caller should pass an explicit
  `conversation_id` rather than let one be derived. A leak is worse than churn,
  which is the whole trade.
- **`bench_masking.py` and `profile_latency.py` cannot see the storage layer**: both use
  `Vault(":memory:")`, so an encryption change leaves their numbers identical by construction.
  "The bench did not move" is not evidence that a disk-layer change is free.

## Concurrency and perf model

pymorphy3 holds the GIL during morphology, so **real parallelism comes from processes, not
threads**. `entrypoint.sh` starts N uvicorn workers (default = CPU count, ~300 MB resident each
for the model stack). Inside a worker, `service.py` offloads detection via `anyio.to_thread` under
a `CapacityLimiter` so `/health` stays responsive and bursts queue instead of thrashing cores.

`MaskCache` is per-worker and holds only masked output; the SQLite vault + audit are shared, which
is what keeps tokens consistent across workers. Audit is recorded on the cache **miss** only — the
same value re-sent in a growing transcript is one protected value, not N.

Env knobs: `PSEUDEX_DB_DIR`, `PSEUDEX_WORKERS`, `PSEUDEX_MASK_CONCURRENCY`, `PSEUDEX_MASK_CACHE_SIZE`,
`PSEUDEX_PSEUDONYM_SCOPE` (`conversation` | `customer`; the sidecar also takes `pseudonym_scope` per request),
`PSEUDEX_ADMIN_TOKEN`, `PSEUDEX_GATEWAY_TOKEN`, `PSEUDEX_UI_PORT`, `PSEUDEX_UI_TOKEN`, `PSEUDEX_UI_PASSWORD`, `PSEUDEX_UI`,
`PSEUDEX_UI_ORG`, `PSEUDEX_UI_STATIC`, `PSEUDEX_ROLE` (`engine` | `proxy` | `ui` | `probe` | `rekey` | `decrypt`),
`PSEUDEX_VAULT_KEY`, `PSEUDEX_VAULT_KEY_FILE`, `PSEUDEX_VAULT_KEY_CMD`, `PSEUDEX_VAULT_KEY_NEW`,
`PSEUDEX_VAULT_ENCRYPTION` (`auto` | `required` | `off`; empty means `auto`),
`PSEUDEX_VAULT_MIGRATION_BACKUP`, `PSEUDEX_TUNING_KEY` (base64 of 32 bytes — seals the
compiled tuning blob at engine build AND is set on the LICENSING SERVER, which delivers it in
each lease so the engine can open its own tuning; the two must match, like the signing key).

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

## Rules that changes must not break, part two — detection precision

These were all learned by measuring, and each one cost recall or precision in the opposite
direction when done the obvious way:

- **A bare date is not personal data.** It becomes personal by ASSOCIATION — next to a personal
  identifier, or next to a birth cue — and a document word directly before it («наряд от», «счёт
  от») wins over a person elsewhere in the sentence. A deny-list of document words was the
  alternative and fails open; this fails closed.
- **Canonicalisation needs EVIDENCE of an oblique case.** pymorphy3 reaches the nominative through
  the lemma, which is masculine for surnames and invented for unknown ones. No conversion without
  evidence, and no conversion of a part already nominative. A gender target and a stem guard were
  both tried and removed — they broke «Руслану» and «Петру».
- **Credentials are anchored to published prefixes, never to entropy.** A git SHA, a UUID, a content
  hash and a base64 image are all high-entropy and none is a secret. `pk_live_` is publishable by
  Stripe's own design and must not be masked; placeholders (`${VAR}`, `xxxx`, AWS's own EXAMPLE key)
  must not either.
- **A cue word may be misspelt.** «пасспорт» and «догвор» disabled the guards that word provides.
  Deny matching tolerates one edit, bounded at one and at a two-letter prefix.
- **Extending a name to its neighbour needs two signals**, not one: morphology must say the
  neighbour can name a person AND its best reading must not be a function word. Any-parse alone ate
  «В», «из» and «по» in news prose.
- **`to_nominative` is called from two sides and only one may be changed.** `canonicalize` calls it
  on the REAL value (the key for "have we met this person"); `name_key` calls it on the FAKE one
  (the index that resolves a token the model inflected). A guard placed inside `to_nominative`
  stopped «Иванова» collapsing to «Иванов» AND stopped «Тарасова» finding «Тарасов» — the fake
  reaching the tool. Measured: `survives_round_trip` then rejected all 28 pool surnames and every
  one-word substitute silently became two. The same guard in `canonicalize` alone is correct
  (`morph_names.lone_nominative_gender`), and `detect_gender` must use it too — a key that says
  woman with a substitute minted for a man is the disagreement, manufactured internally.
- **A KV-typed span carries its own evidence and must skip `suppress`.** The KEY typed the value,
  which is stronger than any word standing near it. Re-gating it lost `{"passport": "4509123456"}`
  entirely — the cue list holds «паспорт» and not the Latin «passport» — while the same number after
  the Russian word was masked. Extending the cue list fixes one key and leaves the next to be found
  the same way.
- **A `KEY_TYPE` entry types the WHOLE value with no shape check**, so an ambiguous Russian business
  word may never be one. «счёт» is an invoice more often than a bank account, and «Реквизиты:»
  introduces a LIST — adding them cost 12 of 298 on the golden set at once, because «Реквизиты:
  СНИЛС 647-436-713 22, карта …» became one account number that swallowed the СНИЛС. Those words
  belong in `CTX_TYPES`, where the 20-digit shape keeps an invoice number out.
- **`normalize` folds a look-alike only when it is not glued to a letter.** «ч» is a look-alike for
  4, and at a word edge its only neighbours inside the run were a space and the phone that followed:
  «Валентинович» became «Валентинови4», the name span ended a character early, and the orphaned «ч»
  glued itself to the substitute — a string in no vault, so `/unmask` and `/reveal` both returned
  nothing and a person who does not exist was written into the customer's system. "Real letters
  break the run" only ever held for letters INSIDE it.
- **Never take `parse(word)[0]` for a gazetteer lookup.** «марину» has «марин» (a man) and «марина»
  (a woman) at the SAME score of 0.500 and the winner is arbitrary; it picked the man, the gazetteer
  had no such entry, and «запишите марину петрову» went to the model with both words in the clear.
  Consider every name-tagged reading TIED FOR FIRST — unbounded costs 0.7pp of NEREL precision by
  admitting «жене»→«Женя», «юре»→«Юра», «розами»→«Роза».
- **A single-token NER person is kept unless the dictionary claims the word.** The gate used to
  demand a known name or a Russian surname suffix, so it threw away every foreign name Natasha had
  already found — Обама, Месси, Бейонсе, Акихито. NEREL PERSON recall 80.6% → 91.5% (Cyrillic 81.1%
  → 92.3%) at **no** precision cost. The `is_known` half is what makes it free: dropping it admits
  the capitalised nouns Natasha over-tags at a caption boundary («Цветы», «Девочки», «Дезинфектор» —
  72 on NEREL) and costs 0.3pp. «Обама» survives the narrow rule because it carries a `Surn` reading
  even though the dictionary knows the word.
- **A mistyped name is reachable, but only with THREE signals.** Adjacent to a detected name, within
  one edit of the gazetteer, AND unknown to morphology. The third is not optional: in a 197k-name
  dictionary the distance-1 neighbourhood is dense enough that ordinary words land in it —
  «заказ»→«Закар», «адрес»→«Адрей», «клиент»→«Клинт», «спасибо»→«Спасибов» are all real rare
  surnames. Without it `test_product` returned «Яков Роман Карпов Василий перезвонить» to a tool.
  Index by the DELETION NEIGHBOURHOOD (Mor-Fraenkel 1982, the construction SymSpell popularised):
  two strings are within one edit — transposition included — exactly when their deletion sets
  intersect, so the lookup is complete by construction. The first-three/last-three scheme that
  stood here was a broken pigeonhole filter: the argument needs a gap between the two windows and
  they have one only at length seven, so it reached 77.9% at length five and 95.1% at six.
- **The apartment marker is usually glued to the house number.** «д.5кв12», «Строителей 53к193»,
  «Гагарина88кв152» — `_TOK` demanded whitespace before the marker, so the flat fell outside the
  span and went to the model inside an address whose street was already masked. A bare «к» is
  admitted only when glued to a digit («за 100к 5 штук» must not read as an apartment), and both
  branches stay SUPPORT so a stray match can never mask anything on its own.
- **A surname alone may not decide gender, and the case must then be read in that gender.** A typo
  in the given name («Кузнецова Ольго») leaves only the surname voting, and `-ова` scores higher as
  a man's genitive — so the span canonicalised to «Кузнецов Ольго» and the tool was called with a
  man. Both halves are gated on `has_given_name`: applying the case filter unconditionally cost -14
  round trips, because where the gender is itself a guess (foreign names) it left a tally with
  nothing sensible in it and «Ким Викдор» became «Ким Викдоры».
- **An address span drops its leading CUE words.** «адрес ленинский проспект 55» matched with
  «адрес» inside the street name and sent it to the tool as part of the address; «мой адрес …» sent
  two. Marker-less streets are «adjective + type», so the pattern cannot see where the name starts.
  Trimmed with signals that already exist — `addr_ctx` for the cue vocabulary, the `Apro` grammeme
  for «мой»/«наш» — because part of speech alone does not separate them from «Ленинский». A street
  TYPE word passes both tests, which is what keeps «улица Тверская» whole.
- **A pool that a customer can exhaust is a permanent 5xx for that customer.** It has happened
  twice: addresses at 33, and gender-invariant surnames at 6 (the seventh woman named by surname
  alone). Any generator drawing from a fixed list needs a floor check at the pool, not a stack
  trace in someone's traffic.
- **A cue word licenses its neighbour, it does not name it.** «фамилия волков» must mask «волков»
  (the bulk surname dictionary is capital-only, so lower case leaked), and «фамилия клиента не
  указана» must not. Same two-signal rule: the cue AND morphology saying the word can name a person.
- **NER spans get trimmed down to one token when the leading word is a verb.** The dictionary trim
  stops at two, presuming «Имя Фамилия»; that presumption made «Наберите Игорю» one name, deleted
  the sentence's verb, and gave the pair an identity unrelated to the person the same message had
  already named.

- **A settlement plus a number is not an address, and that is a VETO.** «погода в
  Сочи 25 градусов», «в Москве 12 филиалов» — a city takes no house number, so
  whatever the context says it is refused. `prep_before` counts as address
  context on its own, and «в», «на», «по» open an address exactly as they open
  everything else, so a vote would have lost. Street names that ARE toponyms
  carry a second reading («Тверская» ADJF, «Ленина» Surn) and are untouched —
  checked across EVERY parse, because «Тверская»'s Geox reading outranks its
  adjectival one and `parse[0]` threw away a real street.
- **A lower-case marker-less street is gated on the VOCABULARY, never on
  morphology.** The capital is one of two signals; with it gone, morphology is
  what admits «течение 12». A leased vocabulary cannot generalise to prose,
  which is the property needed. A month in that vocabulary («марта», for «8
  Марта») names a street only behind a number, so it is excluded there.
- **A marked street with no house number needs an INTENT word, not a
  preposition.** «на улицах Каира собрались десятки» opens with «на» too. Only
  somebody saying they live or receive things there separates an address from
  prose about streets — measured, `prep_before` alone cost 0.1pp of NEREL
  precision. `площад\w+` is excluded from that arm entirely: without a house
  number it matches «площадка», «площади», «площадью».
- **A cue word reaches 60 characters and never across a sentence end.** One
  «адрес» near the top of a system prompt licensed every capitalised-word-plus-
  number for the rest of it. The candidate's own first letter joins the tail
  before splitting, because a sentence end is a period FOLLOWED BY A CAPITAL and
  that capital is the span being judged.
- **An address span stops at a sentence boundary.** The gap vocabulary must hold
  the period because «ул.» and «д.» are built from it, so «Наш адрес: …, д. 14.
  Часы 9-21» masked as one address ending in «Часы 9».
- **The trailing house number joins BEFORE the second merge.** «ул. Гагарина, 45,
  кв. 12» lost its flat while «ул. Гагарина 45 кв 12» kept it — one comma made
  the flat too far away at merge time.
- **A plural reading, an unknown word and the VOCATIVE are not evidence of a
  case.** «Тагиев» is read as genitive plural of an invented «Тагии»; «Ань» has
  nothing left but a vocative and became «Аня». A person is never plural, and
  the vocative survives only as address («мам!») — never in a form or a CRM
  field. The guard lives in `detect_case`, which is safe there and only there:
  the substitute pool is known singular Russian names, so no fake's reading is
  plural or out-of-vocabulary.
- **A stray space inside a surname needs FOUR signals.** «Фёдо ров Кирилл» was
  detected as «Кирилл» and half the surname leaked. Joined must be a name or a
  surname shape; the pair must touch a detected name; the left fragment may not
  be a function word («на»+«Лебедева» → «наЛебедева» ends in «ева» and passes the
  shape test); and at least one fragment must not be a word AND the left one may
  not be a whole word of five letters or more (a typo makes «Влкова» unknown by
  itself, so «получатель Влкова» joined). «Вол ков» is deliberately NOT joined —
  both halves are ordinary words and nothing distinguishes the split.
- **A given name that is also a surname wins the tie.** `any(Surn)` is right for
  every real surname (they carry no `Name` reading) and wrong for «Регина», tied
  at 0.33 — the shape became (surn, surn, patr), both parts mapped to one slot of
  the substitute, and one person got two pseudonyms in one dialogue.
- **A passport needs a cue, and the window after it is sixteen characters.**
  «Паспортные данные: 4518123456» needed nine and the pattern allowed eight.
- **A fuzzy street match needs THREE signals and a fourth condition** — the same
  discipline a mistyped name needs, for a worse version of the same reason: 165 672
  ГАР names, and about half of them a single ordinary-looking word. A street-type
  word adjacent (rejects every bare word-plus-number in prose), the other word in
  the leased ГАР vocabulary as written / as its normal form / as its nominative
  (rejects «улица была пустой» and «на улицах Каира» — morphology admits all three
  and is deliberately not consulted), and address intent. The fourth: a fuzzy hit
  is accepted only for a word pymorphy3 does NOT know, and never for both words at
  once — «линии», «территории», «съезда» and «алло» are known, so they match only
  exactly. Full curve and counter-examples in `docs/gar-street-vocabulary.md`.
- **Cutting the street vocabulary by frequency concentrates the risk, it does not
  reduce it.** The intuition (a smaller gate lets less of the language through) is
  backwards here: the share of entries pymorphy3 calls an ordinary word RISES from
  22.9% at no cut to 65.1% at twelve, because the commonest Russian street names
  ARE ordinary words — центральная, лесная, новая, садовая, школьная. Measured, the
  whole tail costs nothing on NEREL, `test_overmasking` or news prose, and buys 0%
  → 90% on tail streets in the typo register. `STREET_MIN_OBJECTS = 1`.
- **Regex alternation picks the earliest POSITION, not the preferred branch.**
  `street_lower_nohouse`'s marker-last branch matched «адрес москве проспекте»
  before the marker-first branch could reach «проспекте мира», swallowed the cue
  word (which the gate then could not see in front of the span) and made
  `finditer` resume past the street. Ten of fourteen street values at the
  no-punctuation rung. A lookahead leaves the marker unconsumed so both branches
  fire and merge.
- **A number with a unit of measure after it is not a house number.** «территория
  завода 5 гектаров» satisfied every address signal — type word, name in the
  vocabulary, a bare «5» — because nothing looked PAST the number; it only became
  reachable when ГАР taught the engine all 42 street types. Same class `neg`
  already guards with «кв.м», and ordinary consumer Russian is full of it. The
  veto is on the NUMBER, not the span, so the match falls back to needing an
  intent word and the two type tiers decide it themselves. «кв» is deliberately
  NOT in the unit list: after a house number it is КВАРТИРА far more often than
  квадратный метр, and «улица Ленина 14 кв 3» is the commonest address line in
  the language — only the glued «кв.м» / «кв м» form counts.
- **The ГАР attribution rides IN THE BUNDLE, not only in `docs/`.** ФНС's ОТКРЫТАЯ
  ЛИЦЕНЗИЯ grants extraction and commercial reuse on one condition — «указывать
  ссылку на источник открытых данных», with the dump date — and the customer loads
  a bundle, never the repository. `licensing/fetch_gar.py` writes the line,
  `pack.py` reads it back rather than restating it, so a stale bundle cannot claim
  a fresh dump.
- **A spoken numeral must match WHOLE, and the alternation order is what does it.**
  «два» is a prefix of «двести», «три» of «тридцать», «пять» of «пятьсот» — so
  «квартира двести двадцать девять» matched «две» and the span ended three words
  early, inside an address the polnota column was already counting as found. The
  numeral is built longest-class-first (hundreds → teens → tens → units) and
  closed with `\b`. The old ceiling of ninety-nine was argued as «numbers above
  that are vanishingly rare»: true of houses, false of flats — a tower block
  numbers its flats into the hundreds as a matter of course.
- **A spoken house letter is decided by what FOLLOWS it, never by which letter it
  is.** «двадцать пять А» and «дом семнадцать В» are both real literas from real
  calls, and «этаж четвёртый я у вас» is a pronoun the same one-letter rule ate. A
  litera ends the address or hands over to the next marker; a conjunction or a
  pronoun always drags a clause behind it. A list of admissible letters was the
  alternative and would have to be kept in step with ГАР.
- **The spoken address TAIL is SUPPORT, exactly like `apt`.** `apt` demands `\d+`,
  so «улица дербенёвская двадцать четыре строение пять» masked through «четыре»
  and the rest went to the model inside a found span — four of the six voice
  truncations. It cannot mask alone (one marker plus a number word is «программу
  дом два», a television show in our own negative set); merged with a core address
  it is safe. «дом» is deliberately not in it — the chain of two already takes it.
- **A bare street name in front of «дом N» is gated on the ГАР vocabulary AS
  WRITTEN.** «бибиревская дом семнадцать в квартира…» has no type word, no capital
  and no digit, so every arm that could find the street wanted something the
  utterance does not carry. Not morphology — in lower case «бибиревская»,
  «широкая» and «пустая» are one part of speech. Not the normal form or the
  nominative either: `_fuzzy_street_candidates` may afford those because it
  conjoins three signals, and here there are two. The second is the word ORDER —
  «дом культуры» and «дом отдыха» put the register word after the marker.

- **A BENCHMARK'S SELECTION FILTER CAN BE PART OF THE DETECTOR, and then the
  benchmark cannot fail.** `bench/voice` admitted an utterance only if it held a
  street-type word or a house marker — the same signals the engine leans on — so
  it could only ever show cases we already handle. It reported 100% coverage.
  Widened to a filter that provably cannot hide the class (an address with a house
  number contains a number, so: any numeral or digit), 122 candidates became 1373
  and the true number was 38.6%. Ask of any corpus not «where does it fail» but
  «what could never have entered it».
- **A street name with NO type word is the MAJORITY form of a spoken Russian
  address, not a tail.** 400 hand-labelled utterances of real taxi dispatch: 100
  of 156 address values carry no «улица», no «проспект», no capital and no digit
  — «барышникова шестьдесят три первый подъезд». The class scored zero because
  every arm needs one of those. `_bare_street_candidates` is the riskiest shape in
  the engine (a lower-case word plus a number) and is admitted only past four
  gates: the ГАР register in three forms; the shape of the name (a surname in any
  case, an adjective only nominative or licensed by a preposition, never plural,
  never pronominal, never a bare settlement); no age, measure or numeral
  agreement after the number; and a DIGIT must satisfy the shape test even when
  the register names the form as written. Zero false addresses on 2691 NEREL
  sentences.
- **Prose writes house numbers as DIGITS, speech writes them as WORDS, and that
  separates the register from the language.** The ГАР register vouches for
  «Победы» and «Труда» — the genitive IS the street name — but those words also
  stand in the genitive in prose for the ordinary reason: «статьи 19 Федерации 2»,
  «порядка 71 сайта». Measured, letting the register alone decide cost 21 false
  addresses on news prose behind a digit and none behind a spelled number.
- **A numeral GOVERNS what it counts, and a house number governs nothing.**
  «один день» takes the nominative, «два дня» the genitive singular, «восемь
  обвиняемых» the genitive plural. Checking agreement — not a word list — is what
  separates «свободы один день» from «клубная восемьдесят пять». A genitive-only
  veto does not fire after «один», which is exactly how «ограничения свободы один
  день» became an address.
- **A CAPITALISED bare street costs six people on NEREL and is not worth it.**
  Allowing `[А-ЯЁ]` as the first letter of the bare-street arm took voice coverage
  79.5% → 84.1% and PERSON Cyrillic 93.4% → 93.1%: a LOC span outranks NAME
  (ADDR 4 > NAME 3) and swallows whoever is inside it. The arm stays lower-case,
  and «Лермонтова тридцать три» stays uncovered on purpose.
- **The entrance is named with an ORDINAL, and it stands BEFORE the marker.**
  «первый подъезд», «последний подъезд», «угловой подъезд» — every marker arm
  expected «подъезд первый». On the dispatch corpus that was 73 truncations out of
  156: the street and house were found and the entrance went to the model inside a
  span already reported as found.
- **The house litera forbids exactly one letter, «я», and no more.** A lookahead
  demanding the letter end the phrase or meet a marker was measured against real
  speech and cut the house number on every third address — «сто тридцать восемь а
  поедем на энгельса», «семьдесят два а магазин». The one measured harm was «этаж
  четвёртый я у вас», a pronoun read as a litera; ГАР numbers houses from «а» into
  the alphabet and «я» is a pronoun almost everywhere else. Forbid the letter that
  breaks, not the shape.

- **EIGHT OF THE TEN RUSSIAN DIGIT-WORDS ARE REAL ENTRIES IN THE ГАР REGISTER,
  and in speech every digit is a word.** «Семь Ветров», «Пятая Парковая»,
  «Первая» are genuine streets, so `один, четыре, пять, шесть, семь, восемь,
  девять, десять` and the ordinals all return true from a register lookup. A
  dictated order number therefore presents as exactly the shape the bare-street
  arm looks for: «номер заказа шесть семь восемь девять» became the street
  «шесть» at house «семь восемь», and «телефон восемь девять один шесть…» came
  back masked as an ADDRESS. Those values must reach the tool IN THE CLEAR — a
  track number, an invoice, a contract — so masking them does not leak, it makes
  the call fail. A numeral names a street only INSIDE a longer name, and every
  such name has a second word a one-word arm never sees; `NUMR` and `Anum` are
  the test. Same shape and same reason as the month exclusion above.
- **A NOUN NAMES A STREET IN THE GENITIVE, so a noun with no genitive form is a
  thing standing next to a number.** «школа двести десять» is a school, «вышка
  триста тридцать три» a call sign, «время двадцать двадцать один» a clock — all
  three are in the register as written, and the register is not wrong, they name
  streets somewhere. That is exactly why the register alone cannot decide it. An
  adjective is exempt (it agrees with «улица» and is nominative by construction),
  and so is a word a PREPOSITION put into an oblique case — «на литейном четыре»
  has no genitive of its own and «на» is the evidence.
- **EVERY WRITTEN CORPUS WE OWN IS STRUCTURALLY BLIND TO SPOKEN NUMBERS.** NEREL,
  the golden and dirty sets, `test_overmasking` and news prose all write digits
  as digits, so a run of spelled-out numbers cannot occur in any of them. All of
  them declared the bare-street change free; it was masking every dictated order
  number in the language. The class now lives in `test_overmasking.py`, which
  ships and needs no corpus — and it is held by TWO independent vetoes, so the
  test only fails when both are removed.
- **Cheap gates run before morphology.** The bare-street pattern fires on any word
  followed by a number — often, on ordinary text — and almost every hit is
  rejected by a set lookup or a regex. Ordering those first is worth about a third
  of the whole detection cost.

- **AN OVERLAP OF THE WRONG TYPE IS NOT RECALL.** «Overlap is not coverage» is the
  v1 lesson; this is one rung further out. A scorer that counts a gold item as
  found when ANY span touches it will score a СНИЛС masked as a STREET as СНИЛС
  recall — and a СНИЛС replaced by a fake street name is not a protected value,
  it is a broken tool call, and only part of the digits are covered anyway.
  Found when the digit-word defect above made a LOC fragment land inside a
  spelled-out card number and a neighbouring benchmark reported CARD/SNILS/
  PASSPORT going 18% → 100% as a WIN. Ours are clean and stay that way:
  `bench/agentpii/score.py` requires `span.entity_type == item["type"]`,
  `eval_dirty.py` prints the type-aware miss and the type-blind TRUE-LEAK as two
  separate lines, and `bench/voice/score.py` filters to LOC before comparing.
  Type-blind is defensible as a pure leak measure and must then be LABELLED as
  one, never merged with recall.
- **A CENSUS OF ONE STRATUM IS NOT A CENSUS OF THE CORPUS.** The RuDevices
  labelling covers all 400 marker-carrying utterances and a random 250 of the
  4805 that carry only a number. The second stratum holds ~250 address values
  against the first one's 156 — the complete half is the smaller half, and any
  rate over the sample must be weighted 250/4805. Kept in
  `~/.cache/pseudex-bench/rudevices_addresses.json` under a `filter` field so the
  two can never be added up by accident.

- **AN IDENTIFIER DICTATED ALOUD HAS NO DIGIT, AND EVERY RECOGNIZER WAITED FOR
  ONE.** Measured on a corpus built from real transcripts: 281 phones, cards,
  СНИЛС, ИНН and passports spoken as words, and the engine found none. `spoken.py`
  only turns words into a digit string; whether that string is an identifier is
  decided by the SAME validators the digit path uses — Luhn, mod 101, the ИНН
  weight vectors, libphonenumber. Nothing there is a new rule about what counts
  as personal data, and that is what makes a run of ordinary Russian words safe
  to claim. The run scanner alone fires once in 9300 utterances of real speech
  and never in 2691 sentences of prose.
- **FUZZY MATCHING IS FORBIDDEN ON NUMERALS, and it is not a close call.** Across
  58 983 distinct words, 99 ordinary ones sit within a single edit of a numeral —
  «есть» (1947 occurrences) beside «шесть», «опять» beside «пять», «ночь» beside
  «ноль». Distance-1 would not merely admit noise, it would CORRUPT the digits
  inside a real number, and a wrong digit string is worse than a missing one: it
  can pass a checksum and mask the wrong thing. The typo table is MINED instead —
  every form attested in a real corpus and occurring only inside a numeral run.
  Three forms our own benchmark generates («семесят», «четверьый», «подъкзд») are
  deliberately absent: chasing them would tune the engine to the instrument's
  imagination.
- **AN EMPTY CANONICAL IS A COLLISION GENERATOR.** `canonicalize` for СНИЛС/ИНН/
  карта was «strip everything that is not a digit», which returns the empty
  string for a value spoken aloud — so every spoken СНИЛС in the tenant collapsed
  onto ONE row and two different people shared one substitute. That is the single
  failure this product treats as unacceptable, it became reachable the moment the
  engine learned to hear, and it was caught by our own measurement rather than by
  a customer.
- **A TOOL ARGUMENT IS RESTORED VERBATIM; PROSE IS RESTORED IN AGREEMENT.** The
  old design assumed a model writes the nominative inside JSON, so one rule could
  serve both. It cannot: the substitute reaches the model ALREADY inflected —
  `_token_for_span` puts it into the original's case so the sentence stays
  grammatical — the model copies it as written, and the restorer then agreed the
  real value with it. «ленина пятьдесят» came back from the tool as «ленина
  пятидесяти», a house number in the genitive that no CRM will match. 506 of the
  diverged tool calls on the speech corpus were this; splitting the two paths
  took the tool-call axis from 72.1% to 77.8% and NAME arguments from 79% to 91%.
- **DETECTION WITHOUT A MATCHING SUBSTITUTE IS A NET LOSS ON THE TOOL AXIS.**
  Teaching the engine to hear spoken identifiers raised detection and LOWERED the
  tool-call axis by five points, because values that used to pass through
  untouched now went through a lossy restore. Any new recognizer must be measured
  on BOTH axes before it is called an improvement.
- **A SPOKEN HOUSE NUMBER IS STILL A HOUSE NUMBER, in three places that each
  decided it with `\d`.** `looks_like_street` chose between a street and a
  settlement, `place_shape` chose what the substitute is made of, and
  `inflect_place` decided what may not be declined. Fixing any one alone fixes
  nothing: the first minted «Сортавала» for «школьная пятьдесят девять», the
  second dropped the house from the substitute, the third declined «пятьдесят»
  into «пятидесяти».
- **«КВАРТИРА» IS NOT «КВАРТАЛ», and five letters cannot tell them apart.** The
  street-type scan matched a generic by its first five characters, so «кварт»
  made every flat marker into a street type and «химзаводская пять квартира
  пятнадцать» minted «квартира Сосновый 66» — a phrase that names nothing.
- **THE DICTIONARY IS NOT THE BOTTLENECK FOR NAMES, THE GATE IS.** Of 569 missed
  names on real speech, 474 (83%) are words already in the leased dictionary —
  28 413 given names and 196 800 surnames — refused because a lower-case surname
  needs a cue word AND morphology, and dispatch speech carries no cue: «морзов по
  улицам не пройти», «а захаров к 10 часам». Widening the dictionary is not
  available (a sixth of it is homonymous with ordinary words, which is why the
  gate exists). A perfect gate would take NAME polnota from 69.6% to 94.8%, and
  that decision is contextual — the one thing rules cannot make.

- **TWO INDEPENDENT CORPORA AGREE ON NAMES, AND THAT IS THE NUMBER TO DEFEND.**
  Полнота по именам: **69.6% on AgentPII-RU v3** (our generator, our labels) and
  **68.0% on MASSIVE ru-RU** (`bench/eval_massive_ru.py` — 16 521 utterances,
  slot-annotated by a third party, CC BY 4.0, zero capitals, 1.1% punctuation).
  Different data, different annotators, different years, one number. It therefore
  describes the ENGINE and not our generator, and any future improvement must
  move BOTH — a gain visible only on ours is a gain in our imagination. The same
  run reports EMAIL 75% and `place_name` **0.1%**, and that zero is CORRECT: the
  slot holds bare cities («в москве», «в пензе»), a city identifies nobody
  (152-ФЗ ст. 3 п. 1) and we refuse it deliberately. Reading it as a hole would
  send somebody to break a veto that stands on the law.
- **A CLEAN-TEXT SUITE MUST PRINT WHAT IT CERTIFIES, NOT WHAT IT OBSERVED.** Zero
  errors on 42 phrases certifies precision **≥93.1%**, not 100%; the product
  promises 99.4%, which needs 498 flawless phrases. `test_overmasking.py` now
  prints the exact one-sided Clopper-Pearson floor beside the observed rate, and
  says how many phrases the gap would cost. The same arithmetic applies to the
  headline NEREL number: 1 922 spans means the whole error budget at 99.4% is
  **12 spans** and the interval is [98.91, 99.64] — «precision did not move» is a
  statement that instrument cannot make.
- **GROW A CLEAN SET BY SOMEBODY ELSE'S ANNOTATION, NEVER BY OUR OWN SILENCE.**
  The 496 phrases added to `test_overmasking.py` were selected because MASSIVE's
  annotators marked no PII-bearing slot in them, then read by hand and four
  dropped for naming a real person. Selecting phrases because our detector
  stayed quiet would build a suite that cannot fail — the exact forgery the voice
  benchmark already showed us once. Brands, media and museums stay IN: «окко»,
  «р б к», «третьяковская галерея» are not personal data and masking them is the
  defect the suite exists to catch.
- **A HYPHEN GLUES ONE TOKEN, AND HALF OF ONE IS NOT A NAME.** «Лос-Анджелесе»
  reached the model as «Любовь-Анджелесе», «Алма-Ате» as «Зоя-Демьяну», «де-юре»
  as «де-Ивану» — a city arriving as a mangled person, the substitute resolving
  back on the return leg and corrupting the place name in the tool call. 86 such
  spans on 933 NEREL documents, every one a fragment of a compound proper noun.
  NEITHER INSTRUMENT COULD SEE IT: NEREL precision credits a span overlapping ANY
  gold entity and «Лос» sits inside an annotated city, while the clean suite held
  no hyphenated toponym at all. The test is the one `_lowercase_dictionary_ok`
  already applies, asked of the WHOLE token — so «Жан-Клод» passes as a known
  name and «Петров-то» passes as an unknown surname with a particle, and the list
  of particles never has to be written down.
- **AN INVENTED LEMMA AGAINST 197k SURNAMES IS A LOTTERY THE DICTIONARY WINS.**
  pymorphy3 does not know «каоке», guesses the lemma «каока» by analogy, and that
  guess is a real dictionary entry. The lemma path must stay — it finds «джоли»,
  «липницкой», «зеленского», 365 hits across NEREL and both speech corpora — so
  the gate is morphology's own opinion of the unknown word: consult the lemma
  only when the word is known, or when some reading calls it a name.
- **A TOOL RESULT ARRIVES AS JSON, AND JSON PUTS A QUOTE WHERE PROSE PUTS A
  SPACE.** `_TOK` held whitespace, comma, semicolon, paren, № and #, so
  «"addr": "г. Пермь, ул. Добролюбова, д. 154б"» lost its «г. » and
  «{"a": "д. 12, кв. 5"}» was not found at all. That leg is where personal data
  arrives from the customer's OWN systems. 189 of 267 leaked LOC tails on
  AgentPII v3 were this one character; coverage 70.0% → 80.4% with recall
  unmoved, which is the whole reason polnota and coverage are never one number.
- **A STREET IN THE GENITIVE PLURAL IS ADMITTED ONLY WITH THE DOOR AFTER IT.**
  «улица Коммунаров», «Металлистов», «Строителей», «Космонавтов» is a large
  ordinary class and the plural veto threw all of it away. Lifting the veto is
  NOT available: a genitive plural before a number is the Russian
  approximate-quantity inversion — «строителей пять пришло на объект»,
  «шахтёров двести спасли» — and the ГАР register cannot separate them because
  the register is RIGHT, every one of those words names a street somewhere. Ten
  of twelve became false addresses. What separates them is what follows the
  number: a house takes an entrance or a flat, a quantity takes a verb. The
  continuation must begin IMMEDIATELY, or «строителей пять пришло на объект в
  доме два» talks its way into one.
- **A POSSESSIVE FROM A GIVEN NAME IS HOW RUSSIAN SAYS WHOSE**, and its span must
  carry the BASE NAME. «женин день рождения», «олино письмо», «машиного дня
  рождения» sit in no dictionary, carry no capital, and morphology calls them
  adjectives, so no arm saw them. Three gates: the `Poss` reading (the genitive
  plural of «машина» offers none, so «пять машин» never becomes a candidate), the
  base-name dictionary («мамин», «папин», «бабушкин», «дядин» all have `Poss` and
  no name behind them), and agreement with the following noun. `span.value` is
  BOTH the vault key and the source of gender, so with the written form «Женя»
  and «женин» became two rows — one person, two substitutes, the second one
  masculine. No corpus of ours can see that: none carries the possessive register
  except MASSIVE, and MASSIVE measures only recall.
- **`_LOWER_DICT_MIN = 5` IS MEASURED, NOT ASSERTED.** Lowering it to 4 finds nine
  names (азиз, алик, алсу, илик, ирка, лекс, лера, леся, шура) and masks thirty
  ordinary words — «вейп», «мега», «слыш», «джек», «лайт», «ляма», «раша»,
  «дите». Three false masks per person found. EVERY OTHER INSTRUMENT CALLED THE
  CHANGE FREE: NEREL +3 spans of 9720, the 538-phrase suite unmoved, MASSIVE
  person 76.4% → 77.1%. Two are written in capitals, the third measures only
  recall, and the harm lives in lower-case conversational speech.
- **A STREET TYPE IS NOT A STREET NAME, and the ГАР register does not separate
  them.** «улица», «проезд», «площадь», «шоссе», «дорога» all sit inside the NAME
  vocabulary — real streets carry those names — so the bare-street arm read «на
  дороге семьдесят» as the street «дороге» at house 70. The type stems are
  already leased for the arms that look for a type word; asking them here needs
  no second list. «дорог» was also simply MISSING from those stems, which is why
  the collision was reachable at all.

## Conventions

- Comments are in English; product docs (`docs/`) are in Russian. Both are unusually dense —
  a comment explains *why the alternative was rejected*, not what the line does. Match that.
- Functional by default; classes only for connectors to external state (`Vault`, `AuditLog`,
  `Tenants`, `MaskCache`, `Detector` — the last one holds the Natasha model).
- `names.py` ships a compact seed name list; production swaps in the full 32k-name dictionaries
  behind the same API.
- `prototype/README.md` status checkboxes are stale (streaming and RU NER are done). Trust the
  code and `docs/how-it-works.md` over it.
