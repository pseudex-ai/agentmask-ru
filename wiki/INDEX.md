# INDEX — the documents

`docs/` is the product specification and the ТЗ, written in Russian for humans;
`research/` is the evidence archive — deep dives, audits, pentests — behind the
design decisions. Neither is loaded into an agent's context by default. This
index answers, for each file, **what question it answers** and **its status**, so
an agent reads the one document it needs and knows whether it still holds.

The decision each research doc reached is lifted into [STATE.md](STATE.md) (the
`D-NNN` id is given here); the argument stays in the doc. Where a document is
superseded or has open items, the row says so. `wiki/check.py` verifies that
every file in `docs/` and `research/` has a row and that every path named here
exists.

Status: `spec` (describes shipped behaviour) · `ТЗ` (a specification;
`ТЗ-done` / `ТЗ-design` / `ТЗ-partial` says how much is built) · `design`
(a proposal, not built) · `evidence` (a read-only research archive) ·
`superseded` · `has-open-items`.

---

## docs/ — product specification (RU)

| file | answers | status |
|---|---|---|
| `docs/decisions-product-control-plane.md` | owner-led methodological decision log: accepted topology/roles/policy/HITL/documents/secrets/coding choices, chronological supersedes (incl. Jev and semantic R&D cancelled), plus a consolidated scope summary and open owner questions | design (decision log; scope proposed, not implemented) |
| `docs/tz-ai-coding-track.md` | owner-requested final T12 of the same sprint: F23/K10, W28–W35 (Claude slice) then W45 (Codex), AC01–AC13; exact-byte coding mappings, controlled Bash subset/read-search/literal patch, local executor, scoped credential operations, SP07 harness compatibility, Linux/macOS/WSL; release boundary C5 = OPEN-C01 | design (coding scope requested; architecture proposed, not implemented) |
| `docs/tz-hitl-and-documents.md` | accepted F24 HITL (queue/UI/API, encrypted pending, no-auto-expiry card, live-only first release, reveal off by default, H01–H10, W36–W39) and F25 documents-on-context-boundary (tool_result masking, file-attachment block/extract/route, no OCR/native rewrite, document benchmark, DOCG01–DOCG10, W40–W44); closed owner decisions OPEN-C/H/DOC-ARCH | design (scope accepted; protocol/benchmark details still SP08) |
| `docs/tz-product-control-plane-sprint.md` | consolidated product sprint for integrators/developers: F01–F25 over the current engine, two roles + grants, fixed upstream security forwarding (no model routing), custom rules, receipts/output, retention, documents/HITL, integrations, local UI, API/storage/security and acceptance boundaries | design (proposal; not approved implementation) |
| `docs/tz-product-control-plane-matrix.md` | 66 requirement groups: 60 from the corporate AI-gateway specification/local UI concept plus 6 owner-requested coding requirements; P0/P1/P2/X selection, mainstream versus enterprise/specific needs, narrowed scope, and the 10 explicit deviations from full customer spec | design (proposal, not market-share evidence) |
| `docs/plan-product-control-plane-sprint.md` | consolidated execution plan: test-first kernels K01–K12, tracks T01–T14, W01–W45, gates CP01–CP47 + H01–H10 + DOCG01–DOCG10 + AC01–AC13, delivery checkpoints C0–C5 (C4 requires HITL/documents, C5 = OPEN-C01), worktree/main discipline and delegation/evidence/merge contracts | design (proposal, no implementation performed) |
| `docs/tz-v5-model-connectors.md` | interchangeable v5 agent/judge connectors, preserved Claude path, direct DeepSeek agent, Agents SDK + subscription-Codex judge, clean-envelope and quota limits, remaining calibration/resume boundaries (D-069) | ТЗ-partial |
| `docs/articles/2026-09-habr-01-agentmask-ru.md` | article #1 for Habr, first of a series: the public benchmark (six gateways plus the empty `noop` baseline) against a live tool-calling agent. Prose rewritten for human register (no long dashes, no draft scaffolding, no self-critique section). Pseudex numbers measured on the SHIPPED image `pseudex:0.3.21` (digest `sha256:162ca2598b03…`, reader path, full corpus, `copier`): leak 94.7 · coverage 86.2 · round_trip 96.9 · end_to_end 97.0 · overmask 98.4; raw run in `research/agentmask/2026-10-05-pseudex-0.3.21-copier.json` | ready to publish; hand-over folder with numbered images: `docs/articles/publish-habr-01/` |
| `docs/articles/2026-10-habr-02-chuzhie-benchmarki.md` | article #2 for Habr, the series' foreign-benchmarks piece: what NER / PII-masking / tool-calling corpora (global and Russian) actually annotate, our recorded runs on them (NEREL 93.4% Cyrillic PERSON, MASSIVE NAME 68.0%, PII-Bench 89.1% «по закону», noise ladder 100/94.0/94.0/89.9/83.9, `bench/gate` 78.0%/21.3%), where the labels lie (checksum-invalid cards, КПП/ОГРН counted as «ПД», pools inside the leased dictionaries), and the honest gap: no competitor runs on foreign corpora. Every number carries its file; 5 image placeholders | ready to publish; hand-over copy: `docs/articles/publish-habr-02/habr-READY.md` |
| `docs/tz-release-and-versions.md` | the release and version lifecycle: two streams (engine `vX.Y.Z` / platform «platform/vX.Y.Z») via release-please, «version.txt», the registry «deploy/releases.json», the version verdict in the lease, `user_version` + refuse-from-the-future + snapshot, `pseudexctl upgrade`, «release/X.Y» security backports; four worked scenarios | ТЗ-partial (stages 1–7 in progress) |
| `docs/idea.md` | the product concept: what Pseudex is, who it is for, the 152-ФЗ framing | spec (note: `docs/idea.md:69` cites ст. 13.1 wrongly — it is about upload to a Mincifry GIS; see STATE D-018) |
| `docs/spec.md` | the master ТЗ: delivery, protection, performance, the benchmark — the current accepted state, not a changelog | ТЗ |
| `docs/how-it-works.md` | the mechanics with worked examples: what happens to data, why the model sees nothing real, how the tool call still executes | spec |
| `docs/integration.md` | drop-in integration: change ONE env var, the OpenAI-compatible proxy | spec |
| `docs/integration-diva-litellm.md` | integration with Diva-Soft-Back via a LiteLLM callback (the sidecar shape) | design (nothing in Diva modified yet) |
| `docs/integration-diva-backend-api.md` | Diva backend API: per-agent toggle + stats | design |
| `docs/known-issues.md` | the substitution-quality defects, live: §0–§3 and the owner's backlog Б1–Б23 (Б20 dead containers hold a trial slot; Б21 and Б22 found by a red tag and fixed in 0.3.16; Б23 the customer's own word resolved to another dialogue's person, Б24 the form belonged to us and not to the agent — both found by the public benchmark on 0.3.16, fixed in 0.3.17; Б31 the name outside the dictionary — 88% of everything that reaches the model, with the sources to close it and the pools that must NOT be used), each with what it costs and when to fix | spec (the defect register — read before touching redact/vault/address) |
| [`docs/kp-first-enterprise.md`](../docs/kp-first-enterprise.md) | `draft` | коммерческое предложение первому корпоративному клиенту: три пакета (внутреннее использование · право поставки конечным клиентам · совместное развитие), цена, сошедшаяся из двух независимых якорей — четыре года нашей подписки и 60–80 дней собственной разработки, — и раздел «что НЕ входит», где названы и типы, которых мы не находим, и остаток на плече обратного прокси |
| [`docs/integration-shared-gateway.md`](../docs/integration-shared-gateway.md) | `design` | как встать в ОБЩИЙ шлюз клиента, через который ходят все его продукты: включение по ключу, а не глобально (наш простой иначе останавливает чужие продукты); безопасный порядок перехода, когда у хоста УЖЕ есть своё маскирование; пропуск локальных моделей; обязательность conversation_id на всех четырёх ручках и что ломается без него; развёртывание, два токена, ключ тома; что меняется на стороне хоста и чем откатывается |
| [`docs/tz-license-volume-quota.md`](../docs/tz-license-volume-quota.md) | `live` | ЗАМЕНА СЛОТОВ: лимит по объёму (запросы), включённая квота предоплатой + PAYG-овередж по цене тарифа (счёт постфактум) + потолок + переключатель овереджа (дефолт выкл). Модель уже в биллинге витрины; на лиц-сервере — быстрый стоп через `/admin/ceiling` + рекенси-подсчёт (живой=granted, мёртвый=billable). Инстансы — только показ |
| [`docs/tz-license-slots-and-epochs.md`](../docs/tz-license-slots-and-epochs.md) | `superseded by tz-license-volume-quota.md` | прежний заход: слоты/поколения/эпохи/фенсинг вместо счёта живых процессов. Удалён из кода 24.09.2026 — инстанс-счёт не мерит продаваемое (весь трафик через один прокси) и FLP-невозможен; лимит перенесён на объём. Хранится для истории |
| `docs/tz-license-packaging.md` | the licensing layer and packaging: the threat model §3.4, the two images, gates L1–L22 / P1–P11 — the definition of done | ТЗ-done · STATE D-001 |
| `docs/tz-tuning-in-lease.md` | why the tuning rides in the lease, not a compiled blob — closing A2 (extract-once-run-forever) | ТЗ-done · STATE D-039, D-045 |
| `docs/tz-offline-license.md` | the term-licence SKU that works with no call home; the O1–O15 gates | ТЗ-design (O1–O15 not built) · STATE D-004 |
| `docs/tz-vault-encryption.md` | vault encryption at rest: SQLCipher, the key resolver, migration | ТЗ-done (29.08.2026) · STATE D-012–D-017 |
| `docs/tz-name-gender-canonical.md` | the surname-gender-in-the-canonical-key problem and its fix | ТЗ-done (kept for the road to the solution) · STATE D-032 |
| `docs/tz-local-ui.md` | the operator's local web interface: auth, the engine-proxy allowlist, why a separate process | ТЗ-done |
| `docs/tz-agentpii2.md` | AgentPII-RU v2: case schema and family taxonomy | superseded by v4 (normative file was `bench/agentpii2/schema.py`) |
| `docs/tz-agentpii3.md` | AgentPII-RU v3: the ТЗ; normative file `bench/agentpii3/schema.py` | superseded by v4 (the 69.6% NAME number is from here) |
| `docs/tz-agentpii4.md` | AgentPII-RU v4: the ТЗ; normative file `bench/agentpii4/schema.py` | ТЗ (the live benchmark) · STATE D-038, D-041 |
| `docs/tz-agentpii5.md` | AgentPII-RU v5: the next generation of v4 — a LIVE agent, the form of every PII type checked on every hop (user → tool arg → tool result → answer) inside the gateway arm, tool_result as the base, multi-call turns, memory, RAG, documents, tool diversity by vertical, a judge that sees the client's view; every metric with a can-fail test. Normative file `bench/agentpii5/contracts.py`, the item list `bench/agentpii5/CHECKLIST.md` | ТЗ approved 2026-09-22 (§8 included) · build in progress, run only on the owner's explicit GO |
| `docs/tz-agentpii6.md` | AgentPII-RU v6: +500 cases of industry-specific RU identifiers inside v5 — the TypeSpec registry, 15 industries and tool rules, provenance, pilot/full floors, form and value comparison, acceptance gates and mutants, unchanged v5 results, judge calibration, small Codex work packages and G1 decisions | ТЗ-design (edition 2, 2026-09-26) · pilot size and pilot-only implementation approved; other G1 decisions pending in §13 · D-077 · implementation awaits GO |
| `docs/tz-agentpii6-registry.md` | Appendix A to the v6 ТЗ: the 63 candidate cards (grammar with primary source, checksum with worked example and undetectable mutations, surfaces, cues and keys, look-alikes, needles, today's engine behaviour), negatives, collision clusters, the L7 status after the blind fact-check, the 45 proposed tools and their gaps, the live-register survey, and the full text of OD-01…OD-79 | reference data for `docs/tz-agentpii6.md` (2026-09-24) |
| `docs/tz-bench-harness.md` | the mature eval HARNESS for the private benchmark: run as an object (dry-run estimate, run registry, labels, transport resilience), any-run-vs-any-run comparison with a per-case diff and a microscope, cases as data, one provider layer, an HTTP gateway path for comparing image versions, machine-readable report and trend, the discipline rules (dirty tree, CI), and the three the owner added (cost-per-case brake, quarantine of unstable cases, one-command repro) | ТЗ approved 2026-09-23 (22 items) · STATE D-066 · roadmap `docs/tz-roadmap-from-oss.md` §4bis |
| `docs/tz-verticals-and-configurator.md` | detection profiles per vertical and the landing configurator | ТЗ-design (not started) · STATE D-034 |
| `docs/tz-vertical-coverage.md` | the strategy of covering the RU verticals (medicine, finance, insurance, legal, public sector, retail, …) and the roadmap of PII types that `docs/tz-verticals-and-configurator.md` §2 does not hold — a map of directions, not a sprint plan | roadmap-design (2026-09-21) · extends `docs/tz-verticals-and-configurator.md` §2 |
| `docs/tz-roadmap-from-oss.md` | what to take from the OSS competitor landscape, what to refuse and why — a map of directions after the first public-benchmark run, not a sprint plan | roadmap-design |
| `docs/gar-street-vocabulary.md` | why the ГАР street vocabulary exists, how it is fetched, how much is leased, the fuzzy-street curve | spec |
| `docs/billing-integrity.md` | what we bill, what backs it, what it does not close | spec · STATE D-030, D-036 |
| `docs/metering-integrity.md` | the metering design end to end: keys, statuses, the usage-report chain | spec · STATE D-036 |
| `docs/staleness-and-rotation.md` | staleness and N-version rotation (WS-6 / M3) — decay as a defense | spec · STATE D-045 |
| `docs/operations.md` | the operational spec: what runs without us, what needs a human | spec |
| `docs/rkn-notification.md` | the Roskomnadzor processing notification (ст. 22), drafted | design (not filed) · STATE D-044 |
| `docs/payment-provider-request.md` | one text to send ЮKassa and Т-Касса to compare their answers | spec · STATE D-031 |
| `docs/sprint-cabinet-and-pricing.md` | the cabinet + pricing + first-sale sprint | ТЗ |
| `docs/decisions.md` | the original decision log | superseded by wiki/STATE.md (kept; STATE lifts all 28 entries) |
| `docs/yandex-api/` | the Yandex ops-panel API spec (`docs/yandex-api/spec.html`, `docs/yandex-api/spec.pdf`, `docs/yandex-api/ops-panel.png`) | reference |

Not in root `docs/`: `storefront/docs/tz-site.md` and `storefront/docs/tz-site-stack.md`
— the storefront's own spec, moved there (its README links them relative to `storefront/`).

---

## research/ — the evidence archive (mixed RU/EN)

### Agent-hop integrity repair (in progress)

| file | answers | status |
|---|---|---|
| `research/agent-integrity-repair/SCOPE.md` | Complete repair scope, acceptance requirements, frozen source separation, baseline and pending semantic decisions | has-open-items |
| `research/agent-integrity-repair/run_battery.py` | Reproducible per-script before/after regression logs without paid model calls; generated results live beside the runner | evidence tooling |
| `research/agent-integrity-repair/REVIEW-AND-MEASUREMENT.md` | Independent-review corrections, preliminary paired measurements and honest outstanding test failures; not live acceptance | has-open-items |
| `research/agent-integrity-repair/compare_name_seeds.py` | Isolated paired seeded NAME-suite runs against baseline and repair to classify nondeterministic restoration faults | evidence tooling |
| `research/agent-integrity-repair/NAME-PROVENANCE.md` | Candidate-type and bound-identity restoration repairs, full Latin windows, initials-index collision guard; preliminary tests, open mint/morphology scope | has-open-items |

### Market, pricing, distribution

| file | answers | STATE |
|---|---|---|
| `research/2026-08-15-ru-market-billing.md` | who else solves this in Russia, and the tier-ladder arithmetic bug | D-030 |
| `research/2026-10-05-b21-roundtrip-residual.md` | Б21 не флейк: воспроизведённый дефект обратного пути (дательный падеж при подмене, собранной фамилией вперёд), причина в `name_shape`, правка и замеры; **починено в движке 0.3.21**; рядом два побочных наблюдения (мёртвый `test_argument_form`, редкий средовой красный в `test_detok_security`) | done · shipped v0.3.21 |
| `research/2026-10-05-litellm-masking-vs-pseudex.md` | real local run: what LiteLLM's Presidio masking does on Russian chat (false positive on the word «адрес», zero entities when configured for ru) versus Pseudex on the same message, including our own measured boundary | evidence for `/litellm` |
| `research/2026-09-08-rynok-i-cena.md` | who we are compared to; reversibility is not our novelty | D-042 |
| `research/2026-08-15-ru-payments.md` | taking money from RU legal entities: card vs invoice | D-031 |
| `research/2026-08-15-hosting-domain.md` | domain and hosting for launch | D-028 |
| `research/2026-09-20-market-transparency-axis.md` | the market-transparency positioning axis for the article series | D-049 |
| `research/2026-09-20-release-and-version-lifecycle.md` | how to version the customer engine apart from our platform out of one repo (release-please manifest mode, two streams), carry «newer / deprecated / EOL» in the lease response (Tailscale/Sentry shape, RFC 9745/8594), guard the volume with `user_version` + refuse-from-the-future + `VACUUM INTO` snapshot, and give the customer a native upgrade path; what to take ready-made and what to write; H3 (digest churn) refuted — `0.3.12` = `0.3.13` byte for byte | evidence (ТЗ pending) |
| `research/2026-09-20-open-benchmark-mechanics.md` | how to run a NEW public benchmark (review-as-contribution, MMTEB) | D-049 |
| `research/2026-09-21-public-row-0316.md` | our public-benchmark row on the RELEASED 0.3.16 vs 0.3.14: per-value diff (27 DOB leaks closed, 4 names), the corpus's blind spot to Б22 (no two-word patronymics), the chimera it found (Б23), what the judge could not read | Б22, Б23 |
| `research/2026-09-20-ru-distribution-channels.md` | RU distribution: Habr 2026 mechanics, hubs, channels | D-049 |

### Architecture, interception, monetisation

| file | answers | STATE |
|---|---|---|
| `research/security-platform-current-main-baseline.md` | corrects planning's stale 380e3e72/0.3.19 baseline against current main 4cc929bc/engine 0.3.21: native v6 types, checksums, CVC/OTP, JSON evidence, provenance/cache/notation/UI telemetry; preserves real control-plane gaps; canonical docs in main and fresh-base worktrees | evidence (read-only source comparison, no product tests) |
| `research/security-platform-reconciliation.md` | final cross-check of sprint docs against customer ТЗ, UI demo and current code: 11 corrected contradictions (two-role, no model routing, native docs, HITL bodies, secret storage exceptions, CONNECT03, RESTORE01, OS/harness closure, T13/T14 UI, OIDC ordering, S1 traceability) and 10 explicit deviations + 5 open owner questions | evidence (read-only, no runtime gates) |
| `research/harness-hitl-lifecycle.md` | actual HITL lifecycle evidence: Claude Code settings hooks versus SDK canUseTool/defer, Codex app-server warm replay versus cold resume at pinned commit, installed DSH pending/reconnect/restart/input-output seams; no live tests, HITL08 remains owner decision | evidence (read-only docs/source research) |
| `research/jev-typesafe-product-fit.md` | primary-source Jev review: hosted typed API, MIT SDK versus unconfirmed public weights/self-hosting, price/context/version, documented adversarial-state weaknesses and confidence semantics; optional evaluator was investigated, then cancelled by owner; never PII prefilter or Bash authorization; no API execution | evidence (archived candidate, owner cancelled integration) |
| `research/2026-08-15-llm-traffic-interception.md` | how to stand in the LLM traffic path; the three integration levels | D-029 |
| `research/2026-08-31-usage-billing-on-hostile-hardware.md` | metering when the counter runs on the adversary's hardware | D-036 |
| `research/dd5-deployment-architecture.md` | deployment & integration architecture for the gateway | D-048 |
| `research/dd5-monetization-selfhosted.md` | monetisation & metering for a self-hosted gateway; open-core rejected | D-048 |
| `research/deep-dive-toolcall-tokenization.md` | tool-call PII tokenisation: frontier practices, the build decisions | D-048 |
| `research/west-pii-toolcall-sota.md` | Western PII protection for LLM agents — tool-call / function-calling SOTA | D-048 |
| `research/dd-notes-1-skyflow.md` | Skyflow's PII protection across tool calls (decoded) | D-048 |
| `research/dd-notes-3-proxies-mcp.md` | PII de-identification proxies / gateways / MCP middleware in front of LLMs | D-048 |
| `research/cis-pii-llm-middleware.md` | CIS/Russian PII-protection middleware for LLM pipelines (152-ФЗ) | D-048 |
| `research/frontier-architecture.md` | the path to 99%+ on noisy RU PII — the build order | D-048 |

### Detection: names, addresses, IDs, quasi-identifiers

| file | answers | STATE |
|---|---|---|
| `research/2026-08-16-russian-name-morphology.md` | what to inflect ФИО with and where it breaks | D-032 |
| `research/2026-08-31-ml-gate-or-rules.md` | does 95% recall+precision need an ML model | D-035 |
| `research/2026-08-31-context-gate-over-pii-candidates.md` | a small context model as a GATE over PII candidates | D-035 |
| `research/2026-08-19-provenance-linking-noise.md` | what to mask, how to link, how to survive noisy input | D-005, D-007 |
| `research/2026-09-17-prose-case-homography.md` | prose case breaks on a gender-homographic substitute | D-046 |
| `research/2026-09-22-compound-street-address.md` | what the rewriter's remaining 29 % on ADDRESS is actually made of after `915a365`: six classes with counts (the named compound-street fallback is 3 of ~25 and only 1 of those is a false alarm; the «~13 addresses» are the COVERAGE cost of Б16), the mechanism of each to the line, a six-step plan measured by monkeypatch (71.1 % → 83.2 % without touching detection, copier 89.4 % → 92.9 %, whole battery green), the regression battery with today's baselines, and the honest ceiling (≈94 % and what no step closes) | — |
| `research/2026-08-16-secrets-detection-sota.md` | secret detection (keys, tokens, private keys): what production uses | D-033 |
| `research/2026-09-03-checksum-valid-substitutes.md` | checksum-valid substitutes from human-impossible ranges | D-039 |
| `research/dd2-notes-A-ru-ner.md` | local high-recall RU PERSON (ФИО) detection | D-048 |
| `research/dd2-notes-B-ru-address.md` | the best local approach to RU addresses, incl. marker-less | D-048 |
| `research/dd2-notes-C-disambiguation.md` | numeric-ID disambiguation & hard-negative FP suppression | D-048 |
| `research/dd2-notes-D-architecture-eval.md` | defense-in-depth detector architecture + eval methodology | D-048 |
| `research/dd3-location-pii.md` | distinguishing ADDRESS-as-PII from PLACE-as-reference | D-048 |
| `research/dd4-A-noise-phone.md` | noisy/obfuscated PHONE detection + Unicode normalisation | D-048 |
| `research/dd4-B-structured.md` | PII in semi-structured text (JSON / labelled forms / KV) | D-048 |
| `research/dd4-C-quasi-identifiers.md` | quasi-identifiers: what/how to detect | D-048 |
| `research/dd-notes-2-presidio.md` | Presidio's reversible de-identification (source-grounded) — no RU recognisers | D-048 |
| `research/dd-notes-4-fpe-ru-detection.md` | FPE tokenisation + RU PII detection + edge-case literature | D-048 |
| `research/deep-dive-detection-upgrade.md` | fixing Pseudex's RU PII detection (names, addresses, collisions, recall) | D-048 |
| `research/ru-pii-dataset-and-detectors.md` | RU PII datasets, detection methods, reusable components, checksums | D-048 |
| `research/realistic-ru-queries.md` | realistic RU user messages for the detection eval set | evidence |

### The benchmark (AgentPII-RU v4 and its critics)

| file | answers | STATE |
|---|---|---|
| `research/2026-09-02-agent-form-benchmark.md` | «the gateway does not break the agent»: the benchmark and the reverse-path architecture | D-038 |
| `research/2026-09-05-agent-scenario-coverage.md` | what v4 measures, what it misses, how to derive the missing scenarios; the memory-scope decision | D-040 |
| `research/2026-09-06-benchmark-tiers.md` | run tiers, retention, «repeats vs breadth»; DEFF/ICC and TOST | D-041 |
| `research/2026-09-07-benchmark-critics.md` | seven critics against v4; the four defects they found | D-041 |
| `research/2026-09-07-oss-support-agents.md` | do open support agents resemble what v4 models | evidence |

### Verticals and PII law

| file | answers | STATE |
|---|---|---|
| `research/2026-08-16-vertical-pii-registry.md` | the register of verticals and PII types: what to protect, what we lack | D-034 |
| `research/2026-08-16-industry-pii-hr-insurance-legal.md` | PII types protected by sector law in HR / insurance / legal | D-034 |
| `research/legal-152fz-developer-liability.md` | can a company recover a 152-ФЗ fine from the developer | evidence (RU law as of June 2026) |

### IP protection, hardening, security

| file | answers | STATE |
|---|---|---|
| `research/2026-09-01-antitamper-nuitka.md` | raising the cost of reversing / de-licensing the Nuitka binary | D-037 |
| `research/2026-09-15-ip-protection-map-and-sota.md` | the IP-protection map (the moat in four parts) and how to do it ideally | D-045 |
| `research/2026-09-15-ram-extraction-hardening.md` | raising the price of RAM extraction of the tuning for a customer-local root | D-045 |
| `research/2026-09-14-pentest-client-greybox.md` | full grey-box pentest, a client with root on their own hardware | D-045 |
| `research/2026-09-14-security-redteam.md` | the red team, live report (A1/A2/A3) | D-045 |
| `research/2026-09-23-instance-counting-sota.md` | Counting instances of a self-hosted product on hostile hardware: why it is not a hard problem but a FORBIDDEN one (FLP; Chandra-Toueg footnote 6 — even the weakest useful detector is unimplementable without a timing assumption), and what the field does instead — a monotonic epoch on the RIGHT TO ACT, checked by the resource (Chubby sequencer, Kleppmann fencing, Kafka KIP-98/345, van Renesse's «at most one round is operational»). Excavation of ~21 self-hosted products (only 6 technically enforce a count; NGINX Plus enforces the REPORT, not the count) and 11 floating-licence managers (nine document «the same machine retakes its own seat»; RLM `min_checkout` is minimum billed occupancy — prior art for the recommendation). Shows the owner's «restart must be free» is COMPELLED by platform defaults (a 1-replica k8s Deployment doubles on every rollout; an OOM kill is SIGKILL, so no design that needs a goodbye survives it), locates the leak in `RESERVE_SECONDS`/`billable` rather than in the instance count, and recommends ONE construction: server-minted slots, an epoch per container start fenced at `/v1/meter`, and a capacity ledger keyed by SLOT that a new generation INHERITS | — |
| `research/2026-09-22-instance-liveness-and-slots.md` | Б26 to the line: why a dead container holds its plan slot 16–24 h and why the 300 s release cooldown is tied to nothing — both are proxies for ONE unnamed quantity, «how long a lease keeps working after we stop hearing from it» (`ttl+grace` = 72 h). Ten measured reproductions against a local devserver (the cooldown never binds: 12/h against the 3/h release budget; an idle instance DOES heartbeat every 120 s; 32 containers fit under one `instance_id`; a 16-worker start plan is refused on its THIRD restart in a day). Three clocks named and numbered (T_alive 600 s, T_turnover 3/h, T_offline 72 h), the threat table trick-by-trick, an eight-step plan marked server-only / engine-needed, and the four refusal texts | — |

### Hop-format audit and proposed architecture

| file | answers | status |
|---|---|---|
| `docs/tz-hop-form-adaptation.md` | Per-hop form ownership, causal measurement, PHONE/NAME/LOC tracks and acceptance gates | M0 partial + F1 candidate in worktree; S0 open; D-070 |
| `docs/plan-hop-form-before-450.md` | Before implementing the next hop-form track: case-to-cause matrix, ten-type/full-loop scope, metric targets, owner decisions and pre-450 gates | plan for approval; no new build/live-run authorization; D-071 |
| `docs/plan-hop-form-execution.md` | Mandatory execution contract for the 19-item, five-stage sprint: DeepSeek authorship, timeboxes, anti-loop pauses, stage gates and budget | active sprint runbook; no live-run authorization |
| `research/hop-format-audit/README.md` | Verified 450-case cohort, metric caveats, adjudicated evidence and audit scope | evidence; primary audit conclusion |
| `research/hop-format-audit/names.md` | Six NAME/projection case investigations; reviewer caveats in the audit conclusion | investigator evidence, not all claims accepted |
| `research/hop-format-audit/numbers.md` | Six numeric-form investigations | investigator evidence |
| `research/hop-format-audit/chains.md` | Six chain/address/error investigations; reviewer caveats in the audit conclusion | investigator evidence, not all claims accepted |
| `research/hop-format-audit/skeptic.md` | Six metric/observer investigations; reviewer caveats in the audit conclusion | investigator evidence, not all claims accepted |
| `research/hop-format-audit/PROGRESS.md` | M0/S0/F1 targets versus measurements, remaining red tests and next gate | current acceptance status |
| `research/hop-format-audit/s0-reproduction.md` | Exact truncated error echo and scope-safe negative controls | confirmed open defect |
| `research/hop-format-audit/f1-review.md` | Independent PHONE review plus architect adjudication | scoped review; not production approval |
| `research/hop-format-audit/m03-provenance-review.md` | Response ordering versus tool execution and limitations of archived traces | investigator evidence; initial causal claim withdrawn |
| `research/hop-format-audit/c01-baseline.md` | Literal non-PHONE form fixtures and initial red outcomes | local evidence, not live benchmark gains |
| `research/hop-format-audit/name-subject-review.md` | Finite-verb subject fix and object regressions in its first version | first patch rejected; current state in PROGRESS |
| `research/hop-format-audit/atomic-form-review.md` | Independent form/glyph attacks | investigator evidence, requires architect adjudication |
| `research/hop-format-audit/location-hop-review.md` | Structured-address hybrid and prose/form divergence | reproduced defects; not blanket LOC acceptance |
| `research/hop-format-audit/response-trace-implementation.md` | ModelResponse/ModelTrace hooks, serialization and local verification | additive harness contract; no live generation |
| `research/hop-format-audit/name-case-regression-review.md` | NAME random-mint false red and separate gender-blind OUT failure | verified against pristine HEAD and literal controls |
| `research/hop-format-audit/location-form-adversarial.md` | Independent LOC negative controls, regressions and open semantic boundaries | red findings remain open until individually verified |
| `research/hop-format-audit/address-pattern-evidence.md` | Literal saved dialogue evidence for address projections, sender edits and generated inconsistency | investigation; not a new live run |
| `research/hop-format-audit/regression-checkpoint.md` | Quick regression commands, exit codes and engine hashes | intermediate snapshot; drifted runs are not acceptance |
| `research/hop-format-audit/evidence/m0/summary.md` | Completed-only old lines beside versioned actual OUT diagnostic; immutable saved generations | offline evidence, not new-engine gain |

### DevOps and legal launch

| file | answers | STATE |
|---|---|---|
| `research/2026-09-14-devops-audit.md` | the CI/CD pipeline against first sources: three empty policies | D-043 |
| `research/2026-09-14-legal-launch-audit.md` | legal audit of the storefront before sales: two code defects | D-044 |
| `research/2026-09-17-yandex-offline-conversions.md` | Metrika conversions from the server, not the page; the consent question | D-047 |
| `research/2026-09-20-release-and-version-lifecycle.md` | release + versions research behind D-051…D-064 | D-051 |
| `research/2026-09-22-toolresult-derisk.md` | де-риск направления v5: плечо tool_result — где форма-сохраняющий уникально нужен (noop течёт, placeholder непрозрачен, мы отдаём пригодное + форму) | — |
