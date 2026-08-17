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

python3 e2e/gates.py                              # L1-L15 (+L2b), licensing, ~14 min
python3 e2e/gates.py --only L4,L5                 # a subset while iterating
python3 e2e/pack_gates.py                         # P1-P8, packaging (builds both images)

# The verification key is COMPILED INTO the release binary, so a fresh key forces
# a full Nuitka rebuild. Pass the key an image was built with to reuse it:
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

## Architecture

### Two entry points, one core

`pseudex/proxy.py` and `pseudex/service.py` are **parallel deployment shapes**, not layers:

| | `proxy.py` | `service.py` (sidecar) |
|---|---|---|
| Who calls the provider | Pseudex | the host gateway (e.g. Diva's LiteLLM callback) |
| Auth / tenancy | `sk-ps-…` key → `Tenants` → upstream URL+key | `org_id` in the request body |
| Surface | `POST /v1/chat/completions`, `GET /usage` | `/mask`, `/unmask`, `/spans`, `/reveal`, `/usage` |
| Streaming | yes (`StreamDetokenizer`; tool-call requests buffered) | not yet (phase 2) |

Both wrap the same core: `detect_all` → `vault` → `redact` → `audit`. Their `_mask_messages`
implementations are **duplicated on purpose but have drifted** — `service.py` handles multi-part
content blocks, `skip_system`, the mask cache, and the threadpool offload; `proxy.py` does not.
When you change masking semantics, decide explicitly whether both need it.

### Two surfaces on the sidecar, with different auth

`service.py` serves two audiences and they are gated differently on purpose:

| | gateway surface | operator surface (`pseudex/operator.py`) |
|---|---|---|
| Paths | `/mask`, `/unmask`, `/unmask_chunk`, `/spans`, `/health` | `/status`, `/events`, `/stats`, `/stats.csv`, `/reveals`, `/subscription`, `/diagnostics`, `/selfcheck`, `/reveal` |
| Auth | none — the customer's own gateway calls it every request | `Authorization: Bearer $PSEUDEX_ADMIN_TOKEN` |
| Why | a credential there buys nothing against someone already on the contour network | these disclose real values and the list of what exists to disclose |

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
licensing/assets_source.py   the authored data: gazetteers, street vocabulary, cue words,
                             priority table, key->type map, look-alike table. NEVER SHIPS.
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
- Split rule for what is an asset: **in the bundle, everything we tuned; in the binary, everything
  published and every algorithm.** СНИЛС checksums stay in the engine; 28k names do not.

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

### Vault (`vault.py`)

- **Canonicalization**: `+7 999…` / `8 999…` / `89991234567` collapse to one key → one token, so
  the model sees a stable identity across turns. Detokenization returns the *canonical* form.
- **Format-preserving, checksum-INVALID tokens**: a fake СНИЛС/ИНН/card is deliberately generated
  to fail its own checksum, so a token can never collide with a real person's ID.
- Persistent SQLite keyed by `(customer, canonical)` — survives restarts and is shared across
  uvicorn workers via the mounted `PSEUDEX_DB_DIR`.
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

## Concurrency and perf model

pymorphy3 holds the GIL during morphology, so **real parallelism comes from processes, not
threads**. `entrypoint.sh` starts N uvicorn workers (default = CPU count, ~300 MB resident each
for the model stack). Inside a worker, `service.py` offloads detection via `anyio.to_thread` under
a `CapacityLimiter` so `/health` stays responsive and bursts queue instead of thrashing cores.

`MaskCache` is per-worker and holds only masked output; the SQLite vault + audit are shared, which
is what keeps tokens consistent across workers. Audit is recorded on the cache **miss** only — the
same value re-sent in a growing transcript is one protected value, not N.

Env knobs: `PSEUDEX_DB_DIR`, `PSEUDEX_WORKERS`, `PSEUDEX_MASK_CONCURRENCY`, `PSEUDEX_MASK_CACHE_SIZE`,
`PSEUDEX_ADMIN_TOKEN`, `PSEUDEX_UI_PORT`, `PSEUDEX_UI_TOKEN`, `PSEUDEX_UI_PASSWORD`, `PSEUDEX_UI`,
`PSEUDEX_UI_ORG`, `PSEUDEX_UI_STATIC`, `PSEUDEX_ROLE`.

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
```

`bench/agentpii/` is **AgentPII-RU**, built here because the intersection it covers — Russian
conversational PII flowing through tool schemas that consume it — has no benchmark anywhere. Read
its README before changing it. Three things about it are load-bearing:

- **Registers are the point.** `clean` / `chat` / `sloppy` / `voice`. The first run scored 89% and
  every defect it found lived outside the clean register: lower-case addresses (36% recall), a Latin
  letter inside a Cyrillic word, a typo in the cue word, and canonicalisation corrupting surnames.
- **The round-trip axis finds what detection cannot.** «Иванова Мария Львовна» keyed as «Иванов
  Мария» while detection scored 100% on it. Never judge a masking change by recall alone.
- **Ground truth is the canonical form of WHAT WAS WRITTEN.** A chat message with no patronymic must
  not demand one back; that scores the gateway on information the message never carried.

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

## Conventions

- Comments are in English; product docs (`docs/`) are in Russian. Both are unusually dense —
  a comment explains *why the alternative was rejected*, not what the line does. Match that.
- Functional by default; classes only for connectors to external state (`Vault`, `AuditLog`,
  `Tenants`, `MaskCache`, `Detector` — the last one holds the Natasha model).
- `names.py` ships a compact seed name list; production swaps in the full 32k-name dictionaries
  behind the same API.
- `prototype/README.md` status checkboxes are stale (streaming and RU NER are done). Trust the
  code and `docs/how-it-works.md` over it.
