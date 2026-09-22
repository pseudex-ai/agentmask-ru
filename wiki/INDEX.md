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
| `docs/articles/2026-09-habr-01-agentmask-ru.md` | article #1 for Habr: the public benchmark and seven systems — a DRAFT the owner rewrites in his own prose (Habr bans AI-written text); Pseudex numbers marked ⚠ must be re-measured after the release that carries Б19 | design (draft, not published) |
| `docs/tz-release-and-versions.md` | the release and version lifecycle: two streams (engine `vX.Y.Z` / platform «platform/vX.Y.Z») via release-please, «version.txt», the registry «deploy/releases.json», the version verdict in the lease, `user_version` + refuse-from-the-future + snapshot, `pseudexctl upgrade`, «release/X.Y» security backports; four worked scenarios | ТЗ-partial (stages 1–7 in progress) |
| `docs/idea.md` | the product concept: what Pseudex is, who it is for, the 152-ФЗ framing | spec (note: `docs/idea.md:69` cites ст. 13.1 wrongly — it is about upload to a Mincifry GIS; see STATE D-018) |
| `docs/spec.md` | the master ТЗ: delivery, protection, performance, the benchmark — the current accepted state, not a changelog | ТЗ |
| `docs/how-it-works.md` | the mechanics with worked examples: what happens to data, why the model sees nothing real, how the tool call still executes | spec |
| `docs/integration.md` | drop-in integration: change ONE env var, the OpenAI-compatible proxy | spec |
| `docs/integration-diva-litellm.md` | integration with Diva-Soft-Back via a LiteLLM callback (the sidecar shape) | design (nothing in Diva modified yet) |
| `docs/integration-diva-backend-api.md` | Diva backend API: per-agent toggle + stats | design |
| `docs/known-issues.md` | the substitution-quality defects, live: §0–§3 and the owner's backlog Б1–Б23 (Б20 dead containers hold a trial slot; Б21 and Б22 found by a red tag and fixed in 0.3.16; Б23 the customer's own word resolved to another dialogue's person, Б24 the form belonged to us and not to the agent — both found by the public benchmark on 0.3.16, fixed in 0.3.17), each with what it costs and when to fix | spec (the defect register — read before touching redact/vault/address) |
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

### Market, pricing, distribution

| file | answers | STATE |
|---|---|---|
| `research/2026-08-15-ru-market-billing.md` | who else solves this in Russia, and the tier-ladder arithmetic bug | D-030 |
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
| `research/2026-09-22-instance-liveness-and-slots.md` | Б26 to the line: why a dead container holds its plan slot 16–24 h and why the 300 s release cooldown is tied to nothing — both are proxies for ONE unnamed quantity, «how long a lease keeps working after we stop hearing from it» (`ttl+grace` = 72 h). Ten measured reproductions against a local devserver (the cooldown never binds: 12/h against the 3/h release budget; an idle instance DOES heartbeat every 120 s; 32 containers fit under one `instance_id`; a 16-worker start plan is refused on its THIRD restart in a day). Three clocks named and numbered (T_alive 600 s, T_turnover 3/h, T_offline 72 h), the threat table trick-by-trick, an eight-step plan marked server-only / engine-needed, and the four refusal texts | — |

### DevOps and legal launch

| file | answers | STATE |
|---|---|---|
| `research/2026-09-14-devops-audit.md` | the CI/CD pipeline against first sources: three empty policies | D-043 |
| `research/2026-09-14-legal-launch-audit.md` | legal audit of the storefront before sales: two code defects | D-044 |
| `research/2026-09-17-yandex-offline-conversions.md` | Metrika conversions from the server, not the page; the consent question | D-047 |
| `research/2026-09-20-release-and-version-lifecycle.md` | release + versions research behind D-051…D-064 | D-051 |
| `research/2026-09-22-toolresult-derisk.md` | де-риск направления v5: плечо tool_result — где форма-сохраняющий уникально нужен (noop течёт, placeholder непрозрачен, мы отдаём пригодное + форму) | — |
