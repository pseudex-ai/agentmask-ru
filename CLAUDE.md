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
| Conversation scope | derived from the transcript | `conversation_id` in the body, else derived |
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
`PSEUDEX_ADMIN_TOKEN`, `PSEUDEX_GATEWAY_TOKEN`, `PSEUDEX_UI_PORT`, `PSEUDEX_UI_TOKEN`, `PSEUDEX_UI_PASSWORD`, `PSEUDEX_UI`,
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
python3 bench/eval_piibench.py                                     # чужой русский корпус ПД в чатовом регистре
python3 bench/eval_noise_ladder.py --dataset dataset.json          # ГДЕ ломается детекция на живом чате
```

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
  Index by first-three AND last-three letters: an edit at position p is caught by the first key when
  p ≥ 3 and by the last when p < len − 3, so any single edit in a six-letter word lands in one.
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

## Conventions

- Comments are in English; product docs (`docs/`) are in Russian. Both are unusually dense —
  a comment explains *why the alternative was rejected*, not what the line does. Match that.
- Functional by default; classes only for connectors to external state (`Vault`, `AuditLog`,
  `Tenants`, `MaskCache`, `Detector` — the last one holds the Natasha model).
- `names.py` ships a compact seed name list; production swaps in the full 32k-name dictionaries
  behind the same API.
- `prototype/README.md` status checkboxes are stale (streaming and RU NER are done). Trust the
  code and `docs/how-it-works.md` over it.
