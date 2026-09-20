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

45 modules, ~22 400 lines. Paths in this section are relative to `prototype/`.
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
- **Uses:** assets · **Used by:** detect_all, vault
- **Tests:** test_persona_defects, test_product · via detect_all → everything in §3.3
- **Docs:** `research/dd4-A-noise-phone.md` · rules: INVARIANTS.md#normalize

#### `pseudex/detect.py` — 97 lines · `live`
The span types every recognizer emits (`Span`, `NameSpan`, `PartSpan`) and the
first recognizer: libphonenumber ∪ regex phone/email.
- **API:** `Span`, `NameSpan`, `PartSpan`, `detect_pii`
- **Uses:** — · **Used by:** address, context, credentials, detect_all, names, quasi, redact, ru_pii, spoken, structured
- **Tests:** test_loop · via detect_all
- **Docs:** `docs/how-it-works.md`

#### `pseudex/ru_pii.py` — 380 lines · `live`
Russian structured identifiers, checksum-gated: СНИЛС (mod 101), ИНН (weight
vectors), card (Luhn), ОГРН/ОГРНИП, passport (cue-gated), VIN, licence plates.
The validators are the algorithm and stay in the binary; the cue words are leased.
- **API:** `validate_snils`, `validate_inn`, `validate_luhn`, `validate_ogrn`, `vin_check_digit_valid`, `detect_vehicle_ids`, `detect_structured`, `detect_plates`
- **Uses:** assets, detect, fuzzy · **Used by:** detect_all, spoken, vault
- **Tests:** test_product, make_dataset · via detect_all → test_coverage_152fz, test_hard_cases, test_overmasking
- **Docs:** `research/dd2-notes-C-disambiguation.md`, `research/ru-pii-dataset-and-detectors.md` · rules: INVARIANTS.md#structured-ids

#### `pseudex/structured.py` — 219 lines · `live`
Layer 1: JSON / form key-value, where the KEY types the WHOLE value with no shape
check (`KEY_TYPE`), or only licenses a shape (`CTX_TYPES`). A KV-typed span skips
`suppress`.
- **API:** `detect_structured_kv`
- **Uses:** assets, detect, morph_places · **Used by:** detect_all
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
- **API:** `is_numeral_word`, `numeral_alternation`, `canonical_numeral`, `date_from_words`, `date_to_words`, `run_to_digits`, `numeral_runs`, `detect_spoken_ids`, `email_from_words`, `detect_spoken_email`, `plate_from_words`, `detect_spoken_plate`, `main`
- **Uses:** assets, detect, fuzzy, ru_pii · **Used by:** address, detect_all, morph_places, names, vault
- **Tests:** test_product · via detect_all → test_overmasking (dictated order numbers), test_hard_cases; `bench/voice/`
- **Docs:** `bench/voice/README.md`, `docs/known-issues.md` (Б1, Б6) · rules: INVARIANTS.md#spoken

#### `pseudex/names.py` — 1 692 lines · `live`
What NER misses and what it over-tags: the gazetteer (leased), lowercase
diminutives, Latin names, initials, the cue-word gate, the deletion-neighbourhood
typo index, the four-signal split-surname join. Also the gate that KEEPS or DROPS
a Natasha PER/LOC.
- **API:** `is_known_name`, `is_surname_shaped`, `keep_location`, `trim_person_span`, `keep_person`, `gazetteer_names`, `trim_document_words`
- **Uses:** assets, detect, fuzzy, morph, spoken · **Used by:** address, assets, detect_all
- **Tests:** test_product, test_unload_scrub, profile_deep · via detect_all → test_names_morphology, test_hard_cases, test_persona_defects, test_overmasking; `bench/gate/`, `bench/eval_massive_ru.py`, `bench/eval_external_ner.py`
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
- **Uses:** _morph_compat, assets, detect, fuzzy, morph, morph_places, names, spoken · **Used by:** assets, detect_all, redact, vault
- **Tests:** test_hard_cases, test_unload_scrub, profile_deep · via detect_all → test_overmasking, test_persona_defects, test_product; `bench/voice/`, `bench/eval_gar_cut.py`, `make_addr_real.py`
- **Docs:** `docs/gar-street-vocabulary.md`, `research/dd2-notes-B-ru-address.md`, `research/dd3-location-pii.md` · rules: INVARIANTS.md#address

#### `pseudex/morph_places.py` — 1 607 lines · `live`
Place morphology and the address READER: street vs city, nominative, agreement
with the generic word, `split_roles` (city / street / house / flat / entrance —
the one parser every consumer must reuse), keys for the vault, `in_form_of` for
restoring a tool argument in the agent's own form.
- **API:** `looks_like_street`, `to_nominative`, `phrase_to_nominative`, `inflect_place`, `detect_case`, `place_gender`, `generic_forms`, `region_prefix_end`, `address_key`, `generic_full`, `street_house_key`, `strip_flat`, `strip_leading_city`, `place_shape`, `agree_with_generic`, `match_signature`, `signature_parts`, `is_generic_word`, `split_roles`, `role_spans`, `field_role`, `role_of_field`, `city_case`, `address_from_fields`, `part_in_form_of`, `house_digits`, `in_form_of`, `reduce_address`
- **Uses:** agent_form, assets, morph, spoken · **Used by:** address, assets, redact, structured, vault
- **Tests:** test_hard_cases, test_product, test_unload_scrub; `bench/agentpii4/harness.py`, `bench/agentpii4/microscope.py`
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
- **API:** `within_one_edit`, `within_one_typo`, `deletion_keys`, `DeletionIndex`, `build_index`, `lookup`
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
- **Tests:** test_argument_form, test_collisions, test_coverage_152fz, test_credentials, test_hard_cases, test_names_morphology, test_overmasking, test_perf_masking, test_persona_defects, test_product, test_prose_fragments; every `eval_*.py`; every `bench/`
- **Docs:** `docs/how-it-works.md`, `docs/spec.md`, `research/dd2-notes-D-architecture-eval.md` · rules: INVARIANTS.md#pipeline

#### `pseudex/translit.py` — 264 lines · `live`
Transliteration and initials — the DERIVED forms a model writes. `align` learns
the model's per-unit choice from the substitute, `render` applies it to the real
name, `fold` is the vault index under which every rendering collides.
- **API:** `apply`, `is_cyrillic_word`, `units_of`, `align`, `render`, `variants`, `table_for`, `fold`, `folded`, `match_case`, `squeezed_initials`, `main`
- **Uses:** assets · **Used by:** redact, vault
- **Tests:** test_derived_forms, test_prose_fragments
- **Docs:** `research/2026-09-02-agent-form-benchmark.md` · rules: INVARIANTS.md#derived-forms

#### `pseudex/agent_form.py` — 86 lines · `live`
The FORM the agent wrote a substitute in (case, word by word, positional), laid
over the real value on the way back to the tool. Symmetric: lower case in, lower
case out.
- **API:** `cased_like`, `main`
- **Uses:** — · **Used by:** morph_places, redact
- **Tests:** none direct · via redact → test_argument_form
- **Docs:** `research/2026-09-02-agent-form-benchmark.md` · rules: INVARIANTS.md#agent-form

### 1.2 Swap and vault

#### `pseudex/redact.py` — 1 666 lines · `live`
The swap layer: tokenize spans on the way to the model (substitute inflected to
the original's case), detokenize on the way back — prose in agreement, tool
arguments verbatim in the agent's form. Streaming detokenizer with one carry per
`choice.index`; `unmask_arguments` for buffered tool calls; `residual_tokens`
for substitutes that failed to resolve.
- **API:** `mask_text`, `is_own_substitute`, `vault_value`, `tokenize_span`, `unmask_text`, `unmask_stream_chunk`, `unmask_arguments`, `residual_tokens`, `StreamDetokenizer`
- **Uses:** address, agent_form, assets, detect, morph_names, morph_places, profiling, translit, vault · **Used by:** envelope, proxy, service
- **Tests:** test_argument_form, test_collisions, test_derived_forms, test_hard_cases, test_loop, test_names_morphology, test_product, test_prose_fragments, bench_masking, profile_latency; `bench/agentpii{2,3,4}`, `bench/agentrun/roundtrip.py`
- **Docs:** `docs/how-it-works.md`, `docs/known-issues.md` (§0, §1, Б8, Б11, Б12) · rules: INVARIANTS.md#swap, INVARIANTS.md#streaming

#### `pseudex/vault.py` — 3 397 lines · `live`
Token vault: persistent SQLCipher store keyed by `(customer, canonical)`;
canonicalization (phones, names in the nominative with gender evidence,
addresses via `split_roles`); format-preserving, checksum-INVALID substitutes;
the conversation scope (`for_conversation`, `with_pseudonym_scope`, `minted_in`);
the digit-signature and translit reindexes; the collision guards at mint time.
- **API:** `count_values_since`, `canonicalize_person`, `canonicalize`, `looks_dictated`, `name_key`, `fold_key`, `place_key`, `token_re`, `create_tables`, `create_indexes`, `Vault` (+ `VAULT_MIGRATIONS`)
- **Uses:** address, assets, credentials, fuzzy, morph_names, morph_places, normalize, profiling, ru_pii, schema, spoken, sqlite_setup, translit · **Used by:** assets, envelope, proxy, redact, service, schema (lazy)
- **Tests:** vault_test, test_argument_form, test_collisions, test_credentials, test_derived_forms, test_hard_cases, test_loop, test_names_morphology, test_persona_defects, test_product, test_prose_fragments, test_unload_scrub; `bench/eval_vault_precision.py`, `bench/fuzz_registers.py`
- **Docs:** `docs/tz-vault-encryption.md`, `docs/tz-name-gender-canonical.md`, `docs/how-it-works.md`, `research/2026-09-03-checksum-valid-substitutes.md` · rules: INVARIANTS.md#vault, INVARIANTS.md#collisions, INVARIANTS.md#conversation-scope

#### `pseudex/envelope.py` — 326 lines · `live`
Transformations over the OpenAI chat wire envelope, shared by BOTH surfaces:
`mask_messages` (multi-part content, `skip_system`, the mask cache),
`mask_tools`, `unmask_response`, `conversation_key` (derived from the first two
messages when the caller names none).
- **API:** `MaskContext`, `conversation_key`, `mask_one`, `mask_messages`, `mask_tools`, `unmask_response`
- **Uses:** audit, detect_all, maskcache, profiling, redact, vault · **Used by:** proxy, service
- **Tests:** test_collisions, test_persona_defects, test_product, profile_deep; `bench/agentpii*/`
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
- **API:** `BundleNotLeased`, `NameAssets`, `AddressAssets`, `SpokenAssets`, `QuasiAssets`, `ContextAssets`, `StructuredAssets`, `RuPiiAssets`, `TranslitAssets`, `FakeAssets`, `DetectionAssets`, `Assets`
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
| `test_argument_form.py` | a tool argument is restored VERBATIM in the agent's form (case, generic words); prose in agreement |
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

Owner's decision 2026-09-20: of the four AgentPII generations only **v4 is
live**; v1–v3 stay for the numbers cited from them and are not developed.

| package | status | what it measures | normative file | doc |
|---|---|---|---|---|
| `bench/agentpii/` | `superseded by agentpii4` | AgentPII-RU v1: Russian conversational PII through tool schemas, four registers (clean/chat/sloppy/voice), recall vs COVERAGE printed apart, round-trip axis | `bench/agentpii/schema.py` | `bench/agentpii/README.md` |
| `bench/agentpii2/` | `superseded by agentpii4` | v2: case schema and family taxonomy (families/, live/) | `bench/agentpii2/schema.py` | `docs/tz-agentpii2.md`, `bench/agentpii2/README.md` |
| `bench/agentpii3/` | `superseded by agentpii4` | v3: полнота on speech-like agent traffic; mined dispatch calls and reference forms (`bench/agentpii3/mine_*.py`, `bench/agentpii3/mined/`); audit + crosscheck. **The 69.6% NAME полнота number cited in CLAUDE.md is from here** — kept for that number, not for new work | `bench/agentpii3/schema.py` | `docs/tz-agentpii3.md` |
| `bench/agentpii4/` | `live` | v4 «шлюз не ломает агента»: three arms (control, control′, gateway) over a mock CRM; levels calls/fields/state; TOST at δ=3pp with cluster bootstrap; `autopsy`, `microscope`, `compare_runs`; fresh-seed corpora `bench/agentpii4/fresh5150/` … `bench/agentpii4/fresh8080/` | `bench/agentpii4/schema.py` | `docs/tz-agentpii4.md`, `bench/agentpii4/README.md`, `research/2026-09-05-agent-scenario-coverage.md`, `research/2026-09-06-benchmark-tiers.md`, `research/2026-09-07-benchmark-critics.md` |
| `bench/agentrun/` | `live` | paired runs on BFCL tasks with injected Russian PII (`bench/inject_ru_pii.py`): did putting Pseudex in the path cost anything; `bench/agentrun/gpu/` + `bench/agentrun/GPU.md` for a local model | — | `bench/agentrun/GPU.md` |
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
| `storefront/billing/` | `storefront/billing/models.py` (Plan, Subscription, Key, Invoice, Offer), `storefront/billing/services.py` (ALL state changes in one place), `storefront/billing/payments.py` (ЮKassa: cards, СБП, invoice link), `storefront/billing/licensing.py` (connector to the licensing admin API), `storefront/billing/reconcile.py` (our invoice vs the customer's own gateway log), `storefront/billing/onboarding.py` (the coding-agent onboarding prompt); commands `run_billing_cycle` (the ONLY caller of the billing primitives, hourly as its own compose service, idempotent by a DB row) and `seed_plans` |
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
real tables) · `test_analytics` · `test_yandex_api`.

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
| `.github/workflows/gates.yml` | nightly 01:00 UTC + dispatch | `make_dirty` → `pack_gates` (both images) → `gates.py --image pseudex:compiled --skip-build`; on dispatch a subset via `ONLY` |
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
