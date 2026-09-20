# FLOWS — how data moves

The MAP says where a thing is; this file says what happens to a request, a
lease, a store and a build, in order, with the function that does each step.
Read the flow before touching any step of it: most rules in INVARIANTS.md are
about the ORDER here, not about a line of code. Paths are relative to
`prototype/` unless prefixed.

---

## 1. One message through detection

`Detector.detect(text)` in `pseudex/detect_all.py` — the ONLY composition point.

```
text
 │
 ├─ 0  normalize.normalize(text)                       1:1 fold; offsets index the ORIGINAL
 │
 ├─ 1  recognizers, run on the normalized text, results UNIONED
 │      detect.detect_pii             libphonenumber ∪ regex phone/email
 │      ru_pii.detect_structured      СНИЛС / ИНН / card / passport / ОГРН — checksum-gated
 │      ru_pii.detect_vehicle_ids     VIN, plates
 │      credentials.detect_credentials  published prefixes only
 │      _ner_spans (Natasha PER/LOC)  gated by names.keep_person / names.keep_location
 │      address.detect_address        AddrExtractor ∪ anchors ∪ marker-less ∪ bare ∪ spoken tails → maximal spans
 │      names.gazetteer_names         what NER misses: lowercase, Latin, initials, typos (fuzzy), split surnames
 │      structured.detect_structured_kv   KEY types the VALUE (skips suppress)
 │      spoken.detect_spoken_ids      numeral runs → digits → the SAME validators
 │      quasi.detect_quasi            DOB in birth context, age ≥ 90, medical
 │
 ├─ 2  context.suppress(spans, text)                  deny-context: document words, cue distance,
 │                                                     place-reference vs address. BEFORE resolution.
 │
 └─ 3  _resolve(spans)                                _PRIORITY: IDs 6 > phone/email 5 > ADDR 4 > NAME 3 > DATE/PASSPORT/LOC 2
                                                       longest-first, non-overlapping; ADDR → LOC afterwards
 → list[Span]  (type, start, end, value — offsets into the ORIGINAL text)
```

Why the order matters: suppression that runs AFTER resolution cannot rescue a
NAME swallowed by a false LOC; a KV span that goes THROUGH suppress loses
`{"passport": …}`; a cue-word window that ignores sentence ends licenses a whole
system prompt. Each of those was a measured regression, see INVARIANTS.md#pipeline.

---

## 2. `/mask` on the sidecar (`pseudex/service.py`)

```
POST /mask  {org_id, agent_id?, conversation_id?, skip_system?, pseudonym_scope?, messages, tools?}
 │  Authorization: Bearer $PSEUDEX_GATEWAY_TOKEN
 │
 ├─ license state?          EXPIRED → 503 (assets are UNLOADED, there is nothing to detect with)
 ├─ _check_org               a bound container (PSEUDEX_ORG) refuses any other org
 ├─ conversation_id          given, else envelope.conversation_key(messages) — first two messages
 ├─ pseudonym_scope          `conversation` (default) | `customer`; else PSEUDEX_PSEUDONYM_SCOPE
 │
 ├─ anyio.to_thread.run_sync(_mask_request, …)  under _MASK_LIMITER (CapacityLimiter)
 │    context = MaskContext(detector, vault.for_conversation(conversation_id)
 │                                       .with_pseudonym_scope(scope).with_own_values(…),
 │                          audit, cache, org_id, agent_id, conversation_id)
 │    envelope.mask_messages(messages, context, skip_template)
 │      for each message / each content part / each tool_call argument:
 │        envelope.mask_one(text, context)
 │          key = maskcache.content_key(org_id, conversation_id, RAW text)
 │          cache.get_or_compute(key, _compute):
 │            spans  = detector.detect(text)                         (§1)
 │            events = audit.record_many(org_id, agent_id, …)         type + token + masked preview — on MISS only
 │            return redact.mask_text(text, vault, spans)
 │                     └─ per span: redact.tokenize_span → Vault.tokenize / tokenize_person → _tokenize
 │                        mint or reuse; _token_for_text inflects the substitute to the original's case
 │    envelope.mask_tools(tools, context)                            schemas: descriptions, enums, defaults
 │
 ├─ metering.bill(audit, license_client, org_id, agent_id)           AFTER success, never before:
 │     audit.record_request + license_client.consume                 a request is ONE billing unit
 │
 └─ 200 {messages, tools}      any exception → 5xx. NEVER pass-through.
```

Any error in masking propagates to a 5xx — the caller treats an error as a
block, and that is the whole safety story. The proxy shape (`pseudex/proxy.py`,
`POST /v1/chat/completions`) runs the same `mask_messages` / `mask_tools`, then
forwards upstream itself, then runs §3 on the answer before returning it.

---

## 3. The way back: `/unmask`, `/unmask_chunk`, `/unmask_arguments`

```
POST /unmask  {org_id, response}                          a whole chat completion
 ├─ _detok_rate_ok(org_id)  → 429                         per-org rate limit (pentest B1)
 ├─ envelope.unmask_response(response, vault)
 │    message.content            → redact.unmask_text(text, vault)
 │                                  exact tokens → vault; digit-signature reindex for reformatted numbers;
 │                                  translit.fold index for Latin renderings; PROSE restored in AGREEMENT
 │    tool_calls[].arguments     → redact.unmask_arguments(json_text, vault)
 │                                  JSON-aware; value restored VERBATIM in the AGENT's form
 │                                  (agent_form.cased_like, morph_places.in_form_of); initials joined
 │                                  positionally (_join_initials); residual_of ties by minted_in
 ├─ residual = redact.residual_tokens(result)              substitutes that did NOT resolve → still fakes
 ├─ _audit_detok(org_id, actor, …)                         COUNTS only (resolved + misses), never values
 └─ 200 {response, residual_tokens?}  + header X-Pseudex-Residual: N

POST /unmask_chunk       {org_id, choice_index, delta.content}        per streamed content delta
 └─ redact.StreamDetokenizer — ONE carry per choice.index; flat text substitution

POST /unmask_arguments   {org_id, arguments}                          accumulated tool-call arguments, ONCE
 └─ redact.unmask_arguments — never route arguments through /unmask_chunk:
    «ООО "Заря"» by plain replacement injects two bare quotes and the JSON stops parsing
```

`/unmask*` stays reachable on an EXPIRED lease by design (the customer's own
vault; `/mask` being down already stops the agent).

---

## 4. Vault: from a detected value to a substitute and back

```
mint (redact.mask_text → redact.tokenize_span → Vault.tokenize / tokenize_person → Vault._tokenize)
  value ─ canonicalize (vault.canonicalize / canonicalize_person / place_key)
            phones: +7 / 8 / bare → one key            names: nominative WITH evidence of an oblique case,
            IDs: digits (never empty — spoken → digits)   gender from lone_nominative_gender
            addresses: morph_places.split_roles → street_house_key (city kept)
        ─ scope: Vault.for_conversation(id) is a shallow VIEW; place_parts / LINKED rows live under a
            conversation-scoped canonical, full addresses under the plain key
        ─ lookup (customer, canonical) → existing token, else
        ─ _unique_token: draw from the fake pool, format-preserving, checksum-INVALID;
            refuse a candidate equal to any canonical / canonical_fold / the value being minted
            (UNION ALL, one index per branch); _same_street_in_conversation keeps ONE fake street per real street
        ─ store (customer, canonical, token, minted_in = conversation_id, type)

restore (redact.unmask_text / redact.unmask_arguments → Vault lookups)
  token ─ exact:            tokens table
        ─ inflected name:   name_key(fake) → nominative index
        ─ reformatted number: digit-signature reindex
        ─ Latin rendering:  translit.fold → fold_key index
        ─ piece / initials: residual_of(piece) → owner by minted_in; a lone initial resolves only by its OBJECT
        ─ ISO date the agent wrote: date_owner (canonical-date index)
  is_minted_token(value, conversation) — our substitute coming back INSIDE its own conversation is not
  re-masked; the same string from another conversation is a stranger (unless pseudonym_scope = customer)
```

Storage: SQLCipher via `sqlite_setup.connect`, key from `vault_key.resolve`
(`PSEUDEX_VAULT_KEY` → `_KEY_FILE` → `_KEY_CMD` → generated), HKDF per store.
Shared by all workers through `PSEUDEX_DB_DIR`; `MaskCache` is per worker.
`place_parts` expires after a day.

---

## 5. The lease (`pseudex/license.py` ↔ `licensing/server.py`)

```
worker start (serve_main.py, role engine|proxy)
 ├─ hardening.harden_process()                  before ANY role touches tuning or vault
 ├─ LicenseClient(base_url, key, instance_id, ca_path, …)
 │    ProcessKey = bundle.generate_process_key()          X25519, IN MEMORY, per process
 │    POST /v1/lease {key, instance_id, pubkey, engine_version, lease_contract, measure.build_measurement(), usage counters}
 │      server: registry.check(engine_version) → 426 unsupported_client ONLY past an eol announced ≥ 90 d ahead
 │              store.lease_if_allowed + record_lease(engine_version, lease_contract) → pack.build_plaintext (bulk + TUNING + canary + fingerprint + watermark)
 │              → bundle.seal(to pubkey) → payload["bundle_format"], payload["version"] = registry.verdict(...) → bundle.sign_lease (Ed25519) → nonce_wrap
 │    client:   bundle.verify_lease(compiled-in LICENSE_PUBKEY from pseudex/_release.py)
 │              → bundle_format ≤ SUPPORTED_BUNDLE_FORMAT else BundleFormatError («обновите движок»)
 │              → bundle.open_sealed(process key) → assets.load(plaintext)   every regex compiled ONCE
 │              → _parse_verdict(lease["version"]) → LicenseStatus; _report_verdict(): INFO «есть новее» once per
 │                version, WARN every renewal after deprecated_at, notice once per id; absent block → verdict cleared
 │
 ├─ renewal loop every TTL // 3
 │    POST /v1/lease again (counters ride on it); /v1/usage between renewals when needed
 │    OK          → state LEASED (STATE_LEASED = "active"), _last_ok_monotonic stamped
 │    5xx/timeout/DNS (OUR outage) → grace: STALE (serve, warn) while monotonic elapsed ≤ TTL + grace
 │    402 / 403 (unpaid, revoked)  → NOT an outage: EXPIRED at once, slow re-ask
 │    426 (unsupported_client)     → the same: a VERDICT on the version, outside grace (D-056)
 │    wall-clock ceiling: if the wall says past TTL + grace + skew while monotonic looks fresh → EXPIRED
 │                        (a frozen clock fails CLOSED — pentest W2, test_clock_freeze)
 │
 ├─ EXPIRED → assets unloaded and caches SCRUBBED (test_unload_scrub); /mask 503; /unmask still answers
 ├─ tripwire (PSEUDEX_ROLE=tripwire) → POST /v1/tripwire when something reads the engine's RAM
 └─ shutdown → POST /v1/release
```

There is no persisted expiry to edit and no portable bundle to copy: a restart
is a new keypair and a new lease. The tuning exists ONLY inside a leased process.

---

## 6. Container start (`entrypoint.sh`)

```
PSEUDEX_ROLE=preflight|probe|rekey|decrypt|measure|tripwire  → run that role once, exit
otherwise:
 1. PSEUDEX_ADMIN_TOKEN, PSEUDEX_GATEWAY_TOKEN, PSEUDEX_UI_TOKEN  generated ONCE here if unset
    (N workers on one SO_REUSEPORT port must share one token, or the UI 401s at random)
 2. PSEUDEX_ROLE=preflight ./pseudex-serve   → N workers that fit the cgroup limit, or refuse (preflight.plan)
 3. PSEUDEX_ROLE=probe     ./pseudex-serve   → the volume opens with the key we have (sqlite_setup.preflight),
                                               plaintext store → vault_migrate.ensure_encrypted under flock
 4. N × uvicorn workers  (PSEUDEX_ROLE=engine → pseudex.service:app | proxy → pseudex.proxy:app)
 5. PSEUDEX_ROLE=ui ./pseudex-serve  → localui on :8081, separate process, never leases
```

`pseudexctl` wraps steps 2–3 and the store roles for an operator:
`doctor · probe · preflight · decrypt · diag · metrics · rekey · backup · restore`.

---

## 7. Build and release

```
source tree ──► Dockerfile          → pseudex:source    (.py, writes pseudex/_release.py with LICENSE_PUBKEY)
            └─► Dockerfile.nuitka   → pseudex:compiled
                   build_strip_docstrings.py   docstrings out BEFORE Nuitka (the constants blob keeps literals)
                   build_mangle_names.py       private crown symbols → opaque names (keeps _release)
                   build_harden_strings.py     licensing-path beacons hidden
                   Nuitka (Arkari clang)       native binary; glibc of the build stage → same Debian release at runtime
                   localui pages → /app/ui     NEVER under a directory called pseudex (P1 asserts /app/pseudex is absent)

gates   e2e/gates.py L1–L22 (stand from deploy/compose.local.yml; builds pseudex:source)
        e2e/pack_gates.py P1–P11 (both images; P3 = e2e/parity.py on dirty.json — REFUSES before the build without it)
        e2e/audit_gates.py — the gate over the gates (negative atom ⇒ positive atom over the same source)
CI      .github/workflows/checks.yml on every push (incl. deploy/lint_engine_commits.sh, registry validate);
        gates.yml nightly; release-please.yml on push to main keeps one Release PR per stream and,
        on merge, tags + dispatches release.yml (tags v* = engine, platform/v* = platform)

Two streams (docs/tz-release-and-versions.md, D-051…D-054):
  commit touches prototype/pseudex/… ─► release-please: Release PR «engine X.Y.Z»
    merge ─► tag vX.Y.Z ─► release.yml: tests → gates → publish(engine):
      version.txt == tag · shipped set changed since previous v* (deploy/shipped_paths.sh)
      · pseudex:X.Y.Z + aliases (licensing.registry aliases) · anonymous pull · cosign digest
      · licensing.registry record → commit «chore(registry): pseudex X.Y.Z» on main
        ─► release-please: Release PR «platform …» ─► merge ─► platform/vX.Y.Z
  commit touches storefront/ | deploy/ | prototype/licensing/ ─► Release PR «platform X.Y.Z»
    merge ─► tag platform/vX.Y.Z ─► release.yml publish(platform): four images, closed to
    anonymous, signed ─► deploy/agent.sh (platform/v* only) verifies, pulls by digest, up -d
keys    deploy/make-release-keys.sh — public half compiled in, private on the server; a new pair = full rebuild
```

---

## 8. Money (`storefront/` ↔ `licensing/`)

```
landing → signup (email code, storefront/accounts) → cabinet → key
  storefront/billing/licensing.py  → licensing admin API (:9443, PSEUDEX_LICENSE_STOREFRONT_TOKEN)
       issue / revoke / suspend / resume / replan; fleet & anomalies for the console
  customer container leases with that key (§5); the server counts requests per lease (metering.bill)
  run_billing_cycle (hourly, own compose service, idempotent by a DB ROW):
       trial ended → invoice · period ended → invoice · past due → suspend (the CONTAINER stops masking)
       paid but not resumed → retry
  payments: storefront/billing/payments.py (ЮKassa: card, СБП, invoice link for a legal entity)
  reconcile: storefront/billing/reconcile.py — our count vs the customer's own gateway log
```

The rate ladder, the 300 000-request metering floor and every number printed
to the customer come from code (`storefront/pseudex_site/context.py`) and are
pinned by `storefront/test_billing_lifecycle.py` and `test_published_claims.py`.
