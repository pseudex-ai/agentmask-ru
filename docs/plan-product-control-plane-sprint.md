# План реализации спринта: управляемая защита Pseudex

**Статус: план-предложение, код не реализуется этим документом.** Основа — [спецификация 22 возможностей](<docs/tz-product-control-plane-sprint.md>) и [матрица 60 требований](<docs/tz-product-control-plane-matrix.md>). План не зависит от переговоров/КП и не обещает календарную длительность без команды и spikes.

**Расширение по запросу владельца:** в тот же спринт добавлен завершающий **T12 «AI-разработка»** — K10, F23, W28–W35 и AC01–AC12. Базовые 27 пакетов и 47 CP-гейтов сохранены; итог расширенного спринта — **C5**, а C4 теперь приёмка базовой платформы. Подробный контракт и пакеты: [AI coding track](<docs/tz-ai-coding-track.md>). Новая методологическая проработка пока не начинается.

**Текущий этап — методологическое согласование:** ключевые архитектурные и пользовательские развилки проходят владельца в [реестре решений](<docs/decisions-product-control-plane.md>). Порядок K/T/W и технические defaults ниже остаются проектными там, где ещё нет явного ответа. Jev исключён; реализация этим обсуждением не запускается.

**Действующее уточнение AR01/AR04:** один инстанс = одна локальная консоль, прежний быстрый запуск, готовая UI+API. Несколько приложений и upstream-направлений внутри одного инстанса — настраиваемость, не распределённая topology. Centers/nodes/fleet/Kubernetes/HA исключены из текущего sprint; ранее внесённая multi-node трактовка отменена. W02/W04/W12 снова standalone-план; отдельные внутренние storage/process decisions остаются proposed.

**Принято AR10/AR11/AR20:** base policy + application profiles с видимыми адресными overrides; ослабление требует предупреждения и audit author/reason. Обычный путь draft→automatic validation/контрольные примеры→explicit apply; default four-eyes нет. W05/W07/W11–W13/W19/W26 должны реализовать именно этот UX/authority contract, а не один global toggle или отдельную независимую policy каждого приложения.

**Scope update — HITL:** runtime approval входит в sprint, отдельно от four-eyes policy publication. Приняты очередь в нашей UI+API, сохранение pending operation и продолжение exact approved operation, safe defaults. По отдельно включённой настройке доступно разовое осознанное raw-key разрешение модели; requested credential substitution для tool получает отдельный scoped contract. Принято HITL04: временный encrypted pending payload хранит Pseudex, с очисткой/отдельными правами и без содержимого в logs/долговременных backups; точные TTL/reviewer grants ещё уточняются. Detailed work/gates добавляются после ответов. Прежние P2 и blanket raw-secret запреты не отменяют explicit HITL исключение, но technical-check failures не превращаются в allow. Unresolved семантику не реализовывать.

**Принято AR09/HITL05:** две базовые роли admin/user, администратор выдаёт дополнительные разрешения на настройки/HITL; originals — отдельное право. Прежний обязательный каталог пяти ролей отменён. **HITL ожидание:** default карточка не исчезает/не удаляется по таймеру; auto-expiry опционален. Не путать retention/SLA с живым tool/hook timeout; SP07 должен доказать pause/resume либо явный fail-closed handoff/retry, а не ждать в hook до таймаута. Поздний approve/caller gone/no background side effect — обязательные будущие gates; подробный UX ещё согласуется.

**Последнее scope-решение:** владелец вернул coding/harness integration в план как самый поздний T12; промежуточная отмена коннекторов superseded. T12/W28–W35/C5 снова планируются, но HITL08 имеет статус `research_required`: сначала официальные/source lifecycle факты Claude Code/Codex/DSH, затем выбор pause/resume/retry. Не выдаём прошлые гипотезы за принятое поведение. Реализация остаётся после базы; никаких hooks/моделей этой проектной работой не запускаем.

**HITL08 evidence ready:** [исследование harness lifecycle](<research/harness-hitl-lifecycle.md>) выполнено по official docs/pinned Codex source/installed DSH source. Оно не утверждает выбранный adapter и не заменяет SP07. W28 должен отдельно проверить live wait, viewer disconnect, cancel, process restart/defer, same-ID replay, input/output transform и fail-open hook failure. Документированные механизмы разных harness не унифицировать предположением об одном timeout.

**Принятые приоритеты PRIORITY01/02:** первый законченный сценарий — самостоятельная настройка защиты (profiles/rules/exceptions/real sandbox/tests/apply/rollback), после необходимых ядер и гейтов. SSO/DLP/SIEM реализуются после рабочего ядра и основных сценариев; их contracts можно подготовить заранее. Локальные users/rights/internal audit не откладываются, basic HITL не зависит от корпоративных adapters. Coding T12 остаётся последним. Это приоритет готовности и распределения усилий, а не отмена dependency graph или решение выпускать неполный продукт.

**Новый scope:** document protection — основной sprint; принято DOC01: native защищённый PDF/DOCX с сохранением структуры/оформления, не только extracted text. Принято DOC02/03: DOCX и текстовые PDF, OCR исключён; best-effort layout и видимые допустимые отличия, повреждение — отказ. Принято DOC04: непроверенные image/embedded parts по default блокируют выдачу fully protected файла; removal/partial processing только явно, coverage честен. Нужны отдельные parser/rewrite/protocol/storage/artifact no-leak gates и work packages. **SEM01:** ранее предложенный parallel semantic classifier R&D отменён владельцем, сейчас не реализуем и не исследуем. Coding сохраняет последнее место среди production треков.

**Принято PRIORITY-documents-hitl/CODING-first-harness:** после законченного self-service сценария документы и HITL — равноприоритетные параллельные треки с общими prerequisites, не sequential gates друг для друга. Coding остаётся последним: первый supported harness Claude Code, затем Codex; DSH не добавлен в обязательную поставку только фактом исследования. Конкретные adapter modes/версии проходят SP07; при консолидации нужен явный Codex follow-on work/gate этап, а не implicit simultaneous promise.

**Принято ENTERPRISE01/OFFLINE01:** enterprise scope = проверенные стандартные OIDC/event export/REST DLP interfaces без обещания всех вендоров; их реализация после основных сценариев. Full offline licensing/air-gap в этом спринте не реализуется; отдельный прежний design и коммерческие условия не меняются. Local UI/no-CDN не означает offline engine. Утверждённая цепочка приоритетов: self-service core → документы/HITL параллельно → enterprise → coding Claude Code затем Codex, с сохранением technical prerequisites.

**Принято CODING01-platforms:** завершающий coding-трек целится в Linux/macOS и Windows через WSL; native PowerShell/Windows executor не добавляем. Прежние Linux-only предложения superseded. SP07/AC должны отдельно подтвердить OS/filesystem/network/process behavior; Linux container GREEN не переносится автоматически на macOS/WSL. Порядок Claude Code→Codex сохранён.

## 1. Definition of Ready и порядок работы

Перед реализацией owner утверждает D1–D10 основной спецификации. Остальные начальные действия технические, не повторное обсуждение позиционирования:

1. Снять baseline кода/версии/dirty changes, existing HTTP contract, quality/perf и compiled gates на разрешённом стенде. Не stash/reset чужое дерево.
2. Разделить документацию действующего продукта и proposed scope. Не менять marketing claims до подтверждённой поставки.
3. Зафиксировать schema/DTO/API contracts, границы compatibility и приёмочные gate IDs.
4. Роли, privacy, fail-closed и backend semantics идут до изменяющей UI.
5. Каждая задача меняет tests/docs/wiki вместе с code. На существующий green baseline затем накладываются new can-fail tests.

**Размеры:** S локальное расширение; M несколько модулей с HTTP tests; L отдельный контракт и storage/transport; XL несколько связанных contracts и real-container gates. Это относительная сложность, не дни и не бюджет. Календарная ёмкость проекта определяется измерением и составом команды.

## 2. Нулевые технические spikes (до выбора библиотек/точных лимитов)

| Spike | Предмет проверки | Exit criterion | Если не проходит |
|---|---|---|---|
| SP01 | google-re2 в source/compiled Linux, Unicode offsets, max_mem/program size, memory LRU, ARM/x86 release targets | Подтверждены упаковка и bounded matching; adversarial corpus не hang, Unicode spans корректны | Не fallback Python re. Advanced regex переносится P2 явным решением; structural/exact matcher остаётся |
| SP02 | request-level ASSETS pinning через ContextVar/anyio и downstream cached assets | Concurrent renewal в середине прохода не смешивает версии; revoke не выпускает pinned output | Явная передача snapshot по необходимым function signatures; безопасность не откладывается |
| SP03 | N-worker prepare/ACK/active epoch reads + SQLCipher writer contention | Запрос после cutover new-or-503, overhead/RAM измерены, no event loop stall | Пересмотр short-tx/cache структуры, не молчаливый stale TTL; возможно отдельный control reader abstraction |
| SP04 | Нормативный vault transaction UnitOfWork и custom namespace PK | Mint+refs+pending receipt rollback не оставляет deliverable partial state; builtin restore не меняется | Выделить новый transactional writer, существующий API через adapter; не fake outer BEGIN |
| SP05 | OIDC auth library в compiled image + header-only session handoff | Code/PKCE/state/nonce/logout/CSRF tests, no arbitrary discovery, no API token URL/log | OIDC P2 only explicit scope cut; named local RBAC остаётся обязательным |
| SP06 | isolated test runtime/jobs memory+disk/stream parser | No production mutation, no plaintext spool, max row memory, cancel/restart predictable | Снижать подтверждённые limits/выделить resource role; не повторять 200MiB mock promise |

Spikes выполняются в отдельных controlled tests и не становятся вечными experimental paths production. Обновление scope после spike записывается в оба документа до продолжения implementation.

## 3. Последовательный dependency graph

```text
W01 baseline → W02 stores / transaction skeleton / roles
W01 + W02 → W04 runtime snapshot / asset pin / cache
W04 → W06 detector evidence
W02 → W03 identities/RBAC
W03 + W04 → W05 policy schema / immutable model
W05 + W06 → W07 custom rules/dictionaries
W05 + W06 + W07 → W08 actions/secrets
W02 + W03 + W04 + W08 → W09 scopes/receipts/restore
W02 + W03 + W05 + W09 → W10 decision/admin ledger
W06 + W07 + W08 + W09 + W10 → W11 isolated test core
W05 + W07 + W10 + W11 → W12 prepare/activate/rollback
W03 + W05 + W12 → W13 management/CLI/import-export
W03 + W10 → W14 shared admission/limits
W05 + W10 + W12 + W14 → W15 routes/trust
W08 + W09 + W10 + W14 + W15 → W16 output/stream
W09 + W15 + W16 → W17 SDK/adapters
W02 + W11 + W14 → W18 jobs/batch
W11 + W12 + W18 → W19 regression/compare/shadow
W09 + W10 + W12 + W18 + W19 → W20 retention/deletion/restore
W03 + W10 + W14 + W15 + W18 → W21 DLP/SIEM/notifications
W03 + W10 → W22 named access/OIDC
W07 + W08 + W11 + W19 → W23 catalog/profiles/types
W05 + W09 + W15 + W16 + W17 → W24 agent/RAG/tool basics
W10 + W14 + W18 + W19 + W21 → W25 analytics/reports/incidents
backend contracts + grants → W26 integrated UI
базовые capabilities W01–W26 → W27 packaging/regression/platform evidence → C4
C4 → W28 → W29 → W30 → W31 → W32 → W33 → W34 → W35 → C5
W28–W35: завершающий T12 AI-разработка; W35 повторяет платформенную приёмку
```

Нет циклической зависимости «публикация ждёт полной UI-регрессии, UI-регрессия ждёт публикации»: W11 сначала создаёт minimal test core/stamp для W12, W19 добавляет полный клиентский corpus/run UX. W02 содержит минимальный supervised housekeeping/coordinator skeleton; deployment orchestration реализуется W12, bulk jobs — W18. UI можно проектировать и читать раньше, но кнопка mutation включается лишь после готового permission-gated backend.

## 4. Work packages

### W01. Baseline и contract inventory — P0 / M

**Выход:** воспроизводимые fixtures по обеим legs; реестр actual surface/types/error/stream semantics; снимки baseline quality/perf и store schema.

**Работа:** проверить различия docs/code, зафиксировать representative clean/chat/sloppy/JSON/tool-system cases, wire spy и tool-store oracle. Тесты не обучать на holdout. Пометить existing defects отдельно от regression. Preflight stats всех roles. Зависимости: нет.

**Приёмка:** каждый будущий gate имеет источник истины и отрицательный вариант; baseline артефакт содержит commit/dirty diff/engine/bundle/host/dataset hash. Paid/live LLM benchmark только отдельный owner GO.

### W02. Store registry, migrations и transaction skeleton — P0 / XL

**Выход:** control.db/jobs.db под клиентским шифрованием, migration/probe/rekey/restore coverage и skeleton lifecycle новых process roles.

**Работа:** расширить [ключи stores](<prototype/pseudex/vault_key.py>), [STORES](<prototype/pseudex/sqlite_setup.py>), [schema registry](<prototype/pseudex/schema.py>), [entrypoint](<prototype/entrypoint.sh>), [roles](<prototype/serve_main.py>), ops CLI/Dockerfiles. Зарегистрировать control/jobs APPLICATION_ID и HKDF info, увеличить known audit/vault schema в новом minor; snapshots и disk-space checks. Создать transaction-aware writer interface для mapping/refs/receipt без nested commits. Housekeeping separation critical/noncritical processes.

**Зависимость:** W01. **Приёмка:** CP01/CP02/CP03. Старый probe реально refuses new volume, а не игнорирует unknown store. Миграция не открывает roles вне allowed host configuration.

### W03. Principals, projects, apps, local RBAC — P0 / L

**Выход:** server-derived AuthContext, named admin sessions, issue/revoke/rotate app credentials, scoped grants.

**Работа:** new identity/control connectors, compatibility adapters к [tenants](<prototype/pseudex/tenants.py>) и обеим HTTP surfaces. Bootstrap owner, sensitive grants separate, no self-declared role/actor/org. Session revoke security epoch. Raw provider pass-through остаётся explicit legacy, не route в managed project.

**Зависимость:** W02. **Приёмка:** CP04/CP05/CP06; direct API tests и negative namespace searches; secrets one-time display no logs. New mutating backend не запускается с одной shared authority.

### W04. RuntimeContext, ASSETS snapshot и cache invalidation — P0 / XL

**Выход:** один фактический detection/config snapshot на обработку и namespace-aware cached transformations.

**Работа:** изменить [envelope context](<prototype/pseudex/envelope.py>), [cache key](<prototype/pseudex/maskcache.py>), [Assets facade](<prototype/pseudex/assets.py>) и downstream reads. Разделить cached transform и always-evaluated authorization/decision/DLP. Preserve raw-only key; exclude raw-allow cache. Revocation fence/expiry clears.

**Зависимость:** W01/W02. **Приёмка:** CP07/CP08/CP09. Тест принудительного renewal в середине detector/token generator, control change on same RAW content, expired/deleted mapping cache lookup.

### W05. Policy schema/compiler/evaluation — P0 / L

**Выход:** закрытая schema и deterministic Decision со span/source/destination/required check/action restrictions.

**Работа:** proposed policy module; immutable DTO; registry supported matchers/actions; category obligation раньше overlap removal; inheritance ограничений без last-rule wins. Unknown knobs reject; no per-call caller policy. Minimal static validation/stamp interface для W11.

**Зависимость:** W03/W04. **Приёмка:** CP10. SECRET deny нельзя снять allow, empty route intersection deny, arbitrary attributes untrusted.

### W06. Evidence и trace instrumentation built-in pipeline — P0 / L

**Выход:** реальные reasons/candidate/gate/conflict provenance без смены поведения baseline.

**Работа:** instrumentation [detect_all](<prototype/pseudex/detect_all.py>) и существующих gate paths; optional observer/no trace cost default; offsets RAW. Kept/dropped/merged кандидаты, checksum validation, source field context; no pretend confidence. Not found ≠ classified nonPII.

**Зависимость:** W04. **Приёмка:** CP11 и parity battery: без policy/custom additions output baseline unchanged, trace read-only и не содержит persistable originals в audit.

### W07. Custom recognizers, dictionaries, exceptions и tokens — P0 / XL

**Выход:** bounded exact/mask/field/RE2 rules, dictionary revisions, scoped exact exemptions, safe generator.

**Работа:** custom compile/run, mask inference candidate, checksum selector finite enum, versioned templates, independent custom token table/namespace. Exception mechanism не глобальное suppress; lexical Unicode rules/readable display. RE2 quota/cache release/budget. Built-in and custom collisions проверяются вместе, no fallback unsupported generator.

**Зависимость:** W05/W06/SP01/SP04. **Приёмка:** CP12/CP13/CP14. Custom own account positive+negative+roundtrip, malicious regex/exhausted pool, same text across versions/projects.

### W08. Irreversible actions и secret catalog — P0 / L

**Выход:** block/redact/partial/pseudonymize план до mint, curated секреты.

**Работа:** shared envelope/typed JSON traversal делает strict parse и проверки decoded leaves/keys до transformations, escaped tool args не отдельный непрозрачный text path (CP46). [redact](<prototype/pseudex/redact.py>) получает action plan; [credentials](<prototype/pseudex/credentials.py>) known format catalogue, source notices/leases там где authored tuning. Remove structured field only schema-safe; required args→deny. Legacy SECRET inventory no silent purge.

**Зависимость:** W05/W06/W07. **Приёмка:** CP15; cleartext canary scan DB/WAL/snapshots/log/result, public keys/hashes negative corpus. No SECRET reversible mapping даже когда overlapped custom span.

### W09. Managed sessions, receipts, restoration permits — P0 / XL

**Выход:** per-project/app/session namespace и receipt-restricted restore по approved recipient/field/operation.

**Работа:** [vault](<prototype/pseudex/vault.py>) UnitOfWork, reference tracking/custom restore metadata, receipt pending→deliverable, v2 endpoints, derived aliases among authorized mapping IDs only. Existing token render/canonicalization неизменны в legacy. Concurrent restore/live revoke/delivery audit checks.

**Зависимость:** W02/W03/W04/W08. **Приёмка:** CP16/CP17. Foreign receipt/project/conversation denied, current hard revoke overrides pin, old custom revision compatible restore or explicit resolver error, no fake200.

### W10. Decision/admin ledger и safety choreography — P0 / L

**Выход:** request_decisions и outbox atomic within own store, admin mutation+event atomic, no raw content logs.

**Работа:** расширить [audit](<prototype/pseudex/audit.py>), operator endpoints и обработчики; убрать INFO protected transcript logging из [proxy](<prototype/pseudex/proxy.py>) — masked text может содержать detector misses. Every request decision включая cache/noPII/block/error. Accounting выделить и сохранить [metering](<prototype/pseudex/metering.py>) successful-request semantics; no exactly-once generation claim.

**Зависимость:** W02/W03/W05/W09. **Приёмка:** CP18/CP19. Audit failure before receipt/delivery blocks output; actor spoof не попадает в event; raw/support/SIEM projections sanitized.

### W11. Minimal isolated test/explain runtime — P0 supporting / M

**Выход:** реальный dry test kernel для валидации политики, без provider и production writes.

**Работа:** same envelope/detector/transform/restore в test namespace, separate cache/audit/no-meter context, hard admission budget. Test mode выбирается privileged endpoint, не произвольным body org magic. Positive/negative/action/roundtrip outcomes comparable; suite stamp current hashes.

**Зависимость:** W06/W07/W08/W09/W10. **Приёмка:** CP20. Mutating broken restorer должен сделать test red; explain абсолютно read-only; no bill production counters.

### W12. N-worker prepare/ACK/activation/rollback — P0 / XL

**Выход:** no-restart customer policy lifecycle с truthful status.

**Работа:** proposed rollout, worker registration boot+incarnation, immutable artifacts, preflight/test stamp, per-worker compile ACK. Durable assignment CAS, per-admission check, emergency revoke pre-egress. Coordinator recovery, membership churn, compatible rollback new epoch.

**Зависимость:** W05/W07/W10/W11/SP03. **Приёмка:** CP21/CP22. Persistent keepalive after activation new-or503, задержавшийся worker не обслуживает запросы молча по старой версии, crash midprepare keeps old active, conflicting publishers serialized.

### W13. Management API и CLI/Git-managed режим — P1 / L

**Выход:** одинаковое управление UI/CLI/integrator API, export/import draft без credentials.

**Работа:** typed management router, If-Match/428/412, grants и reason/approvers; schema docs/OpenAPI versions; [pseudexctl](<prototype/pseudexctl>) policy commands. Read-only/Git-managed optional mode: UI mutation запрещена, import через approved flow не обходит gate.

**Зависимость:** W03/W05/W12. **Приёмка:** CP23. Curl и UI не расходятся, stale editor не overwrite, import unknown versions fails closed, secret refs remain refs.

### W14. Shared admission, quotas и usage — P1 / M

**Выход:** per-app request/concurrency limits одинаковы на N processes; actual model usage nullable.

**Работа:** admission table short transactions/concurrency expiry, early size/depth bounds ASGI stream reading, queue/time budgets; billing counters не смешать с telemetry. Provider and host assertion counts provenance tagged. Tool budgets API staged for W24.

**Зависимость:** W03/W10. **Приёмка:** CP24. Invalid request not billed, N-worker burst does not multiply quota; worker killed releases slot; unknown token usage not0.

### W15. Защищённые API-подключения без model routing — P1 / L

**Выход:** несколько fixed upstream API bindings одного инстанса, понятное создание через UI/API и готовые клиентские параметры подключения; model selection/balancing/provider fallback не реализуем (принято ROUTE01/02).

**Работа:** protocol-aware forwarding OpenAI/Anthropic поддержанного envelope, preserve caller model, fixed upstream URL/trust class/credentials mode; no arbitrary URL relay, DNS/redirect/TLS checks. Sidecar выдаёт security verdict/constraints, host по-прежнему вызывает и выбирает provider. Secret/identity onboarding отдельно утверждается владельцем. Старые T05/K09 references на fallback не являются задачей текущего scope.

**Зависимость:** W05/W10/W12/W14. **Приёмка:** CP25. Два bindings forwards к своим endpoints; provider error не переключает модель/URL; unknown destination/metadata SSRF запрещены, disabled binding не используется.

### W16. Output/stream validation — P1 / XL

**Выход:** реальные output checks до issuance, authorized JSON restore, bounded full-context mode.

**Работа:** output module/stream_sessions; integrate [proxy streaming](<prototype/pseudex/proxy.py#L488-L557>) и v2 sidecar finish. No unsafe tail flush error; per-choice/field/sequence; receipts and restored spans provenance. Finalize возвращает post-check protected_model_response отдельно от authorized delivery_response, включая новые output mappings/refs; schema-basis explicit (CP46/CP47). Legacy detok-only streaming limitation visible.

**Зависимость:** W08/W09/W10/W14/W15. **Приёмка:** CP26/CP27. Every split of seed secret, parallel choices/tool quotes, timeout/error/cancel no unchecked emission. Output allow policy doesn't exempt whole answer.

### W17. SDK и реальные integration adapters — P1 / L

**Выход:** Python sync/async client, raw HTTP/LiteLLM/LangChain/LangGraph examples, versioned probe runner.

**Работа:** thin client, typed errors, state immutability, tool execution ephemeral real args, protected results/checkpoints, host failure/destination gate. Pin framework versions, trace sanitization или tracing disabled; no naked original params into auto-traces.

**Зависимость:** W09/W15/W16. **Приёмка:** CP28/CP47. Real framework APIs, model wire/checkpoint/tool store oracle; injected 503 host does not call provider. Generic authorize guarded, unknown tools denied before W24 registry.

### W18. Durable jobs и bounded batch — P1 / L

**Выход:** job progress/cancel/resume для permitted encrypted retained material, CSV/JSONL evaluate/export.

**Работа:** jobs.db worker claim epoch, supervised optional role recovery, row/chunk limits, upload interrupted state, encryption/no plaintext spooling, one row audit+progress checkpoints. Partial retention consent explicit, SECRET rows ephemeral. Detection via dedicated budget/role, no multiprocessing spawn.

**Зависимость:** W02/W11/W14/SP06. **Приёмка:** CP29. Crash after chunk commit no duplicate artifacts, worker с устаревшим claim не может завершить job, cancel stops work, RAM bounded and primary latency budget.

### W19. Corpus/regression/compare/shadow — P1 / L

**Выход:** developer управляет размеченным suite, сравнивает actual draft и active, публикует только с valid stamp.

**Работа:** encrypted case CRUD/provenance/expiry labels, generate synthetic secret recipes, required negatives, diff action/spans/roundtrip; shadow bounded no production mint, timeout not_evaluated. Optional capture purpose/permission/TTL; historical preview not reconstruct original. Run manifests inspectable/export safe.

**Зависимость:** W11/W12/W18. **Приёмка:** CP20/CP23/CP30. Empty comparable corpus not100%; label mutation invalidates stamp; raw capture default off; shadow can't weaken primary.

### W20. Retention, delete plans, backup/restore — P1 / XL

**Выход:** четыре отдельные lifetime domains, reference-aware cleanup, logical deletion/reclaim/backup status.

**Работа:** refs/tombstones/namespace epoch, delete exact manifest CAS/live ref fences, job source/result/case TTL, decision/admin retention keeps billing totals. Maintenance plans integration с existing backup/rekey roles; restore replays deletion ledger before readiness. Physical maintenance supervised/drains, no UI shell.

**Зависимость:** W09/W10/W12/W18/W19. **Приёмка:** CP31/CP32/CP33. Concurrent delete/reveal/stream/cache cannot resurrect values; backups liability honest; known modern ledger unavailable →quarantine, no auto-ready.

### W21. DLP/SIEM/notifications — P1 / L

**Выход:** проверяемые generic interfaces и реальные deliveries, не только кнопки «интеграция».

**Работа:** JSON HTTPS/CEF+syslogTLS, per-store transactional sanitized outbox, bounded backoff/quarantine/cap; fixed REST DLP verdict plus optional local classifier connector. Deadline/schema/offset/destination auth handling; required check binding in policy. Alert webhook/SMTP secret refs+TLS.

**Зависимость:** W03/W10/W14/W15/W18. **Приёмка:** CP34/CP35/CP36. Sink down/up/retry/overflow; required DLP malformed/unavailable can't allow; optional reports unknown; no arbitrary remote fetch/SSRF.

### W22. OIDC и completed access UX — P1 / L

**Выход:** generic корпоративный login с verified group mapping, revoke and scoped roles.

**Работа:** local auth library/pin, strict JWT issuer/aud/alg/time, bounded JWKS cache; browser transaction binding no session token URL, IdP MFA claims policy. Поддерживать local audited recovery без постоянного untracked startup-token superadmin.

**Зависимость:** W03/W10/SP05. **Приёмка:** CP06/CP37. Login-CSRF/code replay/wrong key/kid-fetch storm/forged email/groups/revoke crossproject denied; no UI bearer cookies.

### W23. Каталог типов, профили и небольшой type expansion — P1 / L

**Выход:** один capability registry и реальные available presets; measured selected new identifiers.

**Работа:** register human/internal IDs/score/generator/reversibility/availability/entitlement; IMEI/IBAN/MAC + custom industry templates with grounded validators. No hardcoded26/18; preset compile validates capabilities and lease. Authoring assets через vendor lease, customer templates separately local.

**Зависимость:** W07/W08/W11/W19. **Приёмка:** CP38 и полный external/holdout/round-trip battery. Type count from registry, no broad digit matcher, no silent profile fallback.

### W24. Базовые agent/RAG/tool guards — P1 / L

**Выход:** source metadata проверяется, approved tool identities/digests/ops/limits enforce в SDK boundary; injection signatures with honest coverage.

**Работа:** agentguard registry/control, integrity change review, normalized args digest/field restore permit, execution wrapper consumes exact permission; RAG verified assertions and checks, known RU/EN signatures optional calibrated monitor/block. Static bindings no privilege escalation/delegation from tool descriptions. Перед каждым handler online /tools/consume с live grants/epochs и single-use permit/shared budget; queued revoked permit не становится ранее begun execution.

**Зависимость:** W05/W09/W15/W16/W17. **Приёмка:** CP39/CP40. Forbidden actual side effect absent, namesake server doesn't pass, changed schemas need review, RAG missing proof not model-bound. Benign prompt-injection tutorial not automatic block; semantic protection not claimed.

### W25. Analytics, reports, incidents, drift — P1 / L

**Выход:** реальные aggregate counters/histograms/labels/SLO and lightweight evidence-backed issue lifecycle.

**Работа:** bounded SQL aggregations, role/project query scoping, provider time separately gateway, quality from suite/feedback only, unknown/sample size/retention gaps. Drift shape counts no raw index; alerts/suppression, issue links+verified close. Print/CSV/JSON shared DTO and spreadsheet-safety.

**Зависимость:** W10/W14/W18/W19/W21. **Приёмка:** CP41. N workers aggregate exact, small sample insufficient_data, noPII/cache hits decisions count; no fake recall/wrong-value success rate; no PII labels.

### W26. Интегрированная локальная UI — P1 / XL

**Выход:** весь выбранный рабочий цикл плюс реестр coverage, navigation groups и preserved engine version screen.

**Работа:** migrate [frontend](<prototype/pseudex/localui/static/app.js>) на реальные scoped API DTO, разбить экраны; [server](<prototype/pseudex/localui/server.py>) typed method/path forwarding no wildcard relay. Background polling только active tab, no raw value persistence, backend failure real states, accessibility/keyboard, empty/new user scenario, snippets from registry. No mock CDN/runtime/code imports.

**Зависимость:** готовые backend contracts W03/W05/W10/W12 и затем соответствующие W13–W25. **Приёмка:** CP42/CP43. Real browser all roles/project states, XSS traffic/CSV/rules, reveal wipe, failed publication не success toast, no external UI network.

### W27. Packaging, final regressions и доказанная поставка — P1 / XL

**Выход:** два проверенных engine artifacts, операционная документация и полная feature acceptance report.

**Работа:** source/compiled parity/new surface gates, schema/rekey/restore/preflight/doctor, SDK package release separately versioned contract, SBOM licences/native deps, no customer data shipped. Existing engine/platform release streams. Обновить wiki после добавления real modules/tests/gates; старые документы only superseded sections, не fake claims.

**Зависимость:** все выбранные W01–W26. **Приёмка:** CP44/CP45 плюс действующие suite/gates. Каждому R01–R60 состояние implemented/verified/deferred/rejected, никакого «почти готово» вместо absent check.

## 5. Предлагаемые приёмочные gates (CP01–CP47)

Эти gate IDs **новые, пока не существуют**. Реализация может объединять scripts, но не исчезающие негативные атомы. Для gateway/ops gate нужен real compiled image, не ASGI mock как единственное доказательство.

| Gate | Контракт / отрицательный сценарий | Что независимо наблюдаем |
|---|---|---|
| CP01 | Новый store шифруется; key wrong/plain driver cannot open | File header+driver open+canary across file/WAL/snapshot |
| CP02 | Future schema/old image probe refuses untouched | Before/after digest всех stores, exit6 и no worker writes |
| CP03 | No-space/half-migrate/rekey interrupted | Idempotent per-store status, old/new key recovery, no false whole-volume success |
| CP04 | Key/project/app isolation включая searches/jobs/export | Foreign requests never read data or alter row counts |
| CP05 | Key revoked during queued/in-flight delivery | Новые disclosure/execution permits не допускаются; queued permit revoke отклоняет, begun external side effects нельзя выдать за отменённые |
| CP06 | Admin role/session assertions spoofed, logout между issuance и forwarding, method/query/body mismatch | Backend проверяет live named session и exact binding, replay/revoke дают отказ; bridge credential не самостоятельный admin |
| CP07 | Same RAW text with policy/custom/exception/scope change; непустой legacy env при empty managed policy | Current managed snapshot sole authority на обеих legs; ни stale cache, ни falsey env fallback не снимают защиту |
| CP08 | Assets renew midway through recognizer/generator pass | All evidence/renderers use one version; no mixed token |
| CP09 | Lease revoke while asset snapshot pinned | No egress/restore using revoked right; references/cache cleared |
| CP10 | Conflicting allow/SECRET/local-only/required DLP | Strong conjunction/deny, not last-rule-wins |
| CP11 | Explain/read-only trace on XSS/Unicode/overlap corpus | Real reasons and raw offsets; zero mapping/billing changes |
| CP12 | ReDoS/huge dictionary/Unicode/empty regex | Bounded rejection/work/memory, no Python-re fallback |
| CP13 | Custom fake collides with builtin/original/pool exhaustion | No wrong mapping or original fallback, typed failure |
| CP14 | Exception hides overlapped SECRET or broad pattern | SECRET still blocks; exact scope can't broaden |
| CP15 | Seed secret flows through all candidate stages | No mapping/value/preview/log/result/backups created for known secret |
| CP16 | Foreign/stolen/expired receipt, wrong recipient/field | Restore deny without disclosing token existence or value |
| CP17 | Policy/custom recipe removed, authorised old receipt | Correct compatible restore or explicit incompatibility, never fake200 |
| CP18 | Cache hit/noPII/deny/error request audit | Decision event each time; entity/billing counts remain distinct |
| CP19 | Audit unavailable after vault pending commit | No deliverable receipt/provider dispatch; orphan GC safe |
| CP20 | Empty suite/incorrect restorer/wrong-person mutation | Non-comparable not pass, oracle reports failure, production unchanged |
| CP21 | Missing worker ACK/conflicting publish/boot churn | Active pointer unchanged until ready; status shows failure |
| CP22 | Keepalive to old worker after activation commit | New revision or503; no old silent success |
| CP23 | Concurrent edit/import/weakening publish | CAS conflict/no secret import, changed draft invalidates stamp |
| CP24 | Burst N workers/oversized body/killed concurrency lease | Global allowance bound, no invalid request billed, health responsive |
| CP25 | Model alias/local claim/metadata redirect/fallback | Unapproved egress absent in wire spy, constraints respected |
| CP26 | SECRET split every offset in output/n>1 | No unchecked bytes emitted; choices independent |
| CP27 | Tool JSON quotes/cancel/error unsafe tail | Valid approved arguments only; no public tail flush on failure |
| CP28 | SDK host503+restore state mutation+framework trace | No provider call after failure; masked checkpoint/no trace original |
| CP29 | Batch kill/stale claimant/cancel/huge CSV line | Single committed output chunks, bounded memory/no plaintext spool |
| CP30 | Shadow timeout/sample capture/export | Active protection same, not_evaluated visible, capture off unless authorised |
| CP31 | Pause between epoch check/disclosure_begin, delete на другом worker; already-begun pending delivery | Новые permits после fence запрещены, completed только после cancel/drain ранее начатых; transport bytes не отзываются |
| CP32 | Active refs/session TTL absolute expiry | Live other refs preserved, expiry enforced even housekeeper down |
| CP33 | Restore old backup без ledger либо со stale-but-valid ledger | Нужен independently retained authoritative generation/digest и replay; непроверяемая freshness→quarantine, no deleted-data resurrection |
| CP34 | SIEM outage/retry/poison payload/queue cap | At-least-once event IDs, mandatory no loss beyond documented durable constraints, bounded backlog |
| CP35 | Required DLP timeout/malformed/offset mismatch | No upstream; optional check has not_evaluated not green |
| CP36 | Sink/JWKS/DLP DNS rebinding and redirects | Connection egress constrained, secrets absent in errors |
| CP37 | OIDC wrong iss/aud/alg/state/nonce/code replay | Auth fails; no shared admin identity or fetch URL from token |
| CP38 | Missing entitled type/wrong registry count/new type FP; renewal valid lease loses required mechanism | Compile/admission readiness refuses missing requirements, без subset fallback; independent negatives/holdout/compatible restore |
| CP39 | Changed tool digest/namesake server/forbidden operation; queued permit revoke/replay/concurrent exhausted steps | Online consume live recheck+single permit/shared-budget tx; denied attempt не вызывает handler, внешняя exactly-once не заявляется |
| CP40 | RAG source access assertion forged / signatures benign | Unauthorised fragment not model-bound, signature evidence limited/calibrated |
| CP41 | Histograms/quality/reports without labels/data | Correct aggregation and unknown/insufficient_data, no fake100% |
| CP42 | UI direct API bypass/XSS/URL search/CSV formulas | No script execution/privilege bypass, scopes consistent |
| CP43 | Engine down/stale lease/failed publish/logout/reveal | Truthful states; sensitive UI cleared; no CDN/provider UI calls |
| CP44 | source vs compiled endpoints/stores/jobs/restore parity | Same semantic decisions and failure atoms in both images |
| CP45 | Dirty release inputs/SBOM/licences/backup/doctor | Artifact built from recorded source, no attachments/customer material bundled |
| CP46 | Unicode/JSON escaped canary in history/tool args/output/schema enums | Decoded leaf checks эквивалентны plain form; malformed/duplicate keys deny; contract-bound sensitive values не silently skipped |
| CP47 | New PII/SECRET in assistant result, protected state versus restored delivery | Checkpoints/model/traces получают лишь post-check protected representation; authorized tool/user получает separate ephemeral delivery; forbidden recipient ничего не получает |

### 5.1 Proposed scripts и каталог тестов

Предлагаемые test script группы: `test_control_schema.py`, `test_managed_identity.py`, `test_policy_contract.py`, `test_policy_rollout.py`, `test_custom_rules.py`, `test_receipts.py`, `test_output_policy.py`, `test_test_surface.py`, `test_jobs.py`, `test_retention_policy.py`, `test_integrations_security.py`, `test_agentguard.py`, `test_control_ui_renders.py`. Они не существуют на момент составления. Gate orchestrator либо отдельный `e2e/control_gates.py`, либо явно выделенные CP cases в существующем runner, **не переопределять старые L/P IDs**.

Ни один gate не зелёный потому, что ничего не сравнивали/не было accepted call/пустые fields. Failed assertion/engine/network/no labels имеют раздельные outcomes. Suite mutation tests обязаны доказать, что отчёт может стать красным.

## 6. Контрольные точки поставки

| Checkpoint | Состав | Что пользователь действительно может сделать |
|---|---|---|
| C0 — безопасный фундамент | W01–W10 + baseline/spikes | Managed identity/policy primitives, no unsafe mutating UI; все trust/schema contracts проходят |
| C1 — первый полный цикл | W11–W13 + минимальная scoped UI | Создать custom rule, trace, проверить, опубликовать, увидеть decision, откатить |
| C2 — законченный ingress/egress integration | W14–W17 + W24 и соответствующая UI | Выбрать permitted model, проверить output, сохранить tool loop, проверить host fail-closed |
| C3 — самостоятельная эксплуатация | W18–W23/W25/W26 | Batch, regression, lifetime, SSO/DLP/SIEM, reports/SLO/issues без нашей ручной настройки |
| C4 — базовая платформа принята | W27 и CP01–CP47 | Базовые F01–F22 подтверждены, начинается production-реализация T12; это уже не финал расширенного спринта |
| C5 — целостная платформа с AI-разработкой | W28–W35, AC01–AC12 и повторная общая CP-регрессия | Поддержанный coding harness, read/search/Bash subset/literal patch/узкие credential operations работают под общей policy; unsupported capabilities видимы |

Это разрешённые промежуточные состояния разработки. Продавать весь sprint готовым по C1 нельзя. Выпуск промежуточного release требует отдельного decision и truthful capabilities.

## 7. AI-coding-first: ядра компонентов, параллельные треки и test-first исполнение

**Цель дополнения:** сосредоточить архитектурное внимание на несущей логике, а переиспользующие её фичи безопасно делегировать параллельно. Не увеличивать число одновременно пишущих агентов любой ценой, а сокращать критический путь и стоимость повторной интеграции.

K01–K09 и T01–T11 — декомпозиция исходного объёма, **не замена W01–W27 или CP01–CP47**. Позднее добавленное владельцем расширение K10/T12 описано отдельно в §7.10 и добавляет W28–W35/AC01–AC12. `K` — ядро компонента, `T` — трек расширений. Ядро не обязательно отдельный процесс, package или сервис: это единая ответственность, набор инвариантов и публичный контракт. Один W-пакет может включать ядро и расширения; его исходная приёмка остаётся обязательной целиком.

```text
BEFORE
Один большой пакет → реализация → тесты → обнаружение несовместимости потребителей.

AFTER
Контракт ядра → проверяемые гейты/красные тесты → минимальное рабочее ядро
                                                  ├─ трек A: A1 → A2 → A3
                                                  ├─ трек B: B1 → B2 → B3
                                                  └─ трек C: C1 → C2 → C3
                          каждый трек → реальная интеграция → общая приёмка

Effect: независимые расширения не ждут друг друга; границы безопасности и смысл
API остаются едиными. Ускорение ожидаемое, а не заранее измеренное в процентах.
```

### 7.1 Два разных разрешения: начать работу и считать её готовой

Для каждого ядра фиксируются четыре состояния:

| Состояние | Что существует | Что можно делегировать | Что ещё запрещено |
|---|---|---|---|
| `contract_ready` | Согласованные DTO/schema/errors, инварианты, ограничения, версия контракта; входы/ожидаемые выходы и тестовые адаптеры | Consumer tests, UI rendering, serialization, документацию, локальную логику адаптера на versioned fixtures | Называть stub production-ядром или feature готовой |
| `tests_ready` | Исполняемые проверки, осмысленный RED новой возможности, GREEN baseline, проверка чувствительности инструмента | Реализацию ядра и контрактно независимых потребителей | Ослаблять критерий ради удобства кода; считать ImportError доказательством RED |
| `kernel_ready` | Минимальное реальное ядро проходит заявленное подмножество CP, включая негативные сценарии и необходимую проверку на контейнере | Интеграцию потребителей, работающих по этому контракту | Автоматически считать пройденными CP других слоёв/полную W-приёмку |
| `integrated` | Реальное ядро и потребитель проверены вместе на зафиксированной сборке, без test doubles на проверяемой границе | Выпуск в рамках разрешённой контрольной точки | Выдавать локальный GREEN за готовность всего спринта |

**Межтрековые зависимости сохраняются.** Параллельность означает, что независимые задачи могут выполняться одновременно, а не что все треки стартуют без prerequisites. Внутри каждого трека задачи идут последовательно; внешняя зависимость блокирует только нужный шаг, а не всю программу.

Граф §3 задаёт порядок полной интеграционной готовности W-пакетов. Ранний старт по fixtures в этом разделе **не отменяет** этот граф. Например, UI редактора можно подготовить на `contract_ready` политики, но включить публикацию только после реальных identity, policy, audit и rollout gates.

### 7.2 Реестр ядер: где нужен максимальный архитектурный фокус

| Ядро | Единственная несущая ответственность | Исходные W / F | Публичный контракт, фиксируемый до реализации | Гейты ядра и сквозные проверки |
|---|---|---|---|---|
| K01 | Хранение, транзакции и процессный lifecycle | W02; F21 | Store registry, migration/probe/rekey, UnitOfWork boundaries, critical/optional process roles | CP01–CP03, CP44–CP45; crash/space/recovery fixtures |
| K02 | Доверенная identity и полномочия | W03; F01–F02 | AuthContext, named session, project/app bindings, live grants/epochs, bridge assertion | CP04–CP06; downstream revoke CP16/CP39 и OIDC CP37 |
| K03 | Snapshot запроса и кеш преобразований | W04; F03–F04 | RuntimeContext, pinned asset reference, cache basis, invalidation/revocation fence | CP07–CP09; coupling с CP22/CP32 |
| K04 | Policy decision и жизненный цикл конфигурации | W05/W12, контрактная часть W13; F03–F04 | Strict policy schema, Decision algebra, immutable refs, validation stamp, prepare/ACK/commit/rollback | CP10/CP21–CP23/CP38; no-restart и отказ при missing capability |
| K05 | Evidence, расширяемая детекция и действия | W06–W08, минимальный catalog W23; F05–F07/F19 | Finding/location basis, recognizer extension, safe custom recipe, action plan, decoded JSON contract | CP11–CP15/CP46, quality/parity corpus; no arbitrary code |
| K06 | Mapping, receipts и разрешённая выдача | W09, primitive части W20/W24; F08/F15/F22 | Namespace/ref lifecycle, pending/deliverable receipt, recipient+field capability, disclosure/execution fence | CP16–CP17/CP31–CP33/CP39; audit release coupling CP19 |
| K07 | Журнал решений и обязательные побочные записи | W10; F09/F12/F17 | Decision/admin event schema, atomic local outbox, release choreography, billing boundary | CP18–CP19; consumer delivery CP34 и accounting CP24 |
| K08 | Независимый test runtime и очередь работ | W11, ядро W18; F13–F14/F21 | Isolated test context, expected result schema, comparability, run stamp, job claim/cancel/checkpoint | CP20/CP29–CP30; isolation CP04, encryption CP01 |
| K09 | Граница передачи, лимиты и выходные проверки | W14–W16, security primitive W24; F10–F12/F22 | Admission, approved destination, buffered output, protected-state/delivery split, one-use execution attempt | CP24–CP27/CP36/CP39–CP40/CP46–CP47; SDK CP28 |

Колонка CP — **набор обязательств**, не разрешение отметить полный gate зелёным после unit-теста одного ядра. Гейт с несколькими участниками получает предварительные именованные assertions; весь CP зелёный только после сквозной проверки реальных участников. Минимальные role/capability/catalog/job interfaces появляются в ядрах, а их UI, пакеты и расширенные реализации — в треках.

#### K01. State kernel: до первой новой таблицы

- Сначала описать ownership каждой таблицы, ключи, ограничения уникальности, store encryption label, миграцию, схему downgrade refusal и допустимые crash states.
- До реализации создать тесты no-space/half-migration/future-schema и transaction rollback. Для UnitOfWork проверить, что вложенный helper не может самостоятельно commit незавершённый receipt.
- Минимальное ядро: реально открывающиеся encrypted stores, миграции и базовые transaction APIs, процессный supervisor с различием engine/job failure. Не «repository interface» без реального SQLCipher backend.
- **Не делегировать потребителям:** собственный SQL connection fallback, новый HKDF label, самостоятельные миграции по первому API вызову. Изменения общего schema registry интегрирует один ответственный.
- Feature-ответвления: эксплуатационные команды, job storage adapters, retention storage operations. Каждое использует один migration/transaction contract.

#### K02. Identity kernel: до новых management-кнопок

- Проработать subject/service/admin различия, project boundaries, live revoke, роли/grants, bootstrap и compatibility. Входные `org_id/actor/agent_id` не становятся authority.
- Test-first: таблица «субъект × операция × project × expected allow/deny», forged session/bridge assertions, logout между подписью и forward, legacy-token доступ к managed namespace.
- Минимальное ядро: одна реальная local named session и один app credential, проходящие оба HTTP legs с backend authorization. Shared secret UI не считается заменой.
- **Не делегировать:** новые правила выдачи прав, собственную проверку JWT в адаптере, расширение прав по удобному UI-флагу.
- Ответвления: OIDC, интерфейс access management, credential rotation UX, интеграционные snippets.

#### K03. Runtime kernel: до динамических правил

- Зафиксировать состав snapshot и transform-cache key, связь с asset lease, policy revision, namespace и deletion epochs. Shared cache result не является разрешением запросу.
- Test-first: управляемый scheduler/barrier ставит renewal, publish или revoke между двумя reads; результат нельзя получить случайным `sleep`. Один raw input с разными scope/exception revisions должен различаться.
- Минимальное ядро: реальный snapshot проходит полный recognizer→token generator pipeline; delayed worker и cache hit не обходят live permission checks.
- **Не делегировать:** локальные копии cache-key логики в SDK/UI/recognizer и бесконечное удержание revoked assets.
- Ответвления: custom rules, rollout, shadow evaluation, latency instrumentation; все используют один context contract.

#### K04. Policy kernel: два последовательных среза, не круговая зависимость

1. `K04-A`: schema, evaluator, immutable revision и минимальный capability registry на основе K02/K03. После него можно писать bounded rule consumers.
2. `K04-B`: validation stamp и prepare/ACK/commit/rollback после реальных K05/K06/K07 и минимального test runtime K08-A. Только этот срез разрешает production activation.

До A: truth tables для deny/route intersection/required checks, неизвестных полей, conflict resolution. До B: state-machine tests на отсутствующий ACK, смену worker incarnation, CAS конфликт и падение coordinator. Гейт использует N реальных процессов, а не N ответов случайного SO_REUSEPORT socket.

**Не делегировать:** собственную precedence исключений, отдельный policy enum в frontend, activation через сохранение mutable JSON. Ответвления: editor/import-export/CLI, templates/profiles, dev/prod comparison. Черновик и опубликованная revision различаются во всех API.

#### K05. Detection/action kernel: до каталога отраслевых фичей

- Сохранить существующие built-in semantics; развести «найдено», «подавлено контекстом», «проиграло overlap», «запрещено политикой» и «преобразовано».
- До реализации расширений определить extension interface и набор положительных/отрицательных/overlap/Unicode cases. Expected results размечаются независимо от функции, которую проверяем.
- Минимальное ядро: один custom structural type, один exact dictionary, одно scoped exception, SECRET block/redact и decoded JSON путь; настоящий round-trip и collision refusal.
- **Не делегировать:** mutation общего detector pipeline из каждого отраслевого pack, Python hooks, изменение canonicalization ради зелёного частного теста, использование подстроенного holdout.
- Ответвления: новые validated patterns/types, библиотека шаблонов, UI builder, trace rendering. Добавление данных каталога должно быть дешевле изменения несущей логики.

#### K06. Lifecycle kernel: до TTL, purge и инструментов

- Заранее описать namespace/lifetime domains, refs, совместимость старого decoder, pending/deliverable receipt и общую точку допуска disclosure/execution.
- До реализации написать модели переходов и crash/revoke/delete race tests: сначала фиксация fence, затем cancel/drain, затем completed. Нельзя проверять безопасность только отсутствием кнопки reveal.
- Минимальное ядро: настоящий authorised restore с ограничением mapping membership, deny чужой session/recipient, primitive expiry/delete fence. User-facing retention wizard и backup tooling могут прийти позже, **не сама граница запрета выдачи**.
- **Не делегировать:** самостоятельный token lookup мимо receipt, удаление строк без refs/tombstones, собственный execution permission bypass, обещание exactly-once внешнего side effect.
- Ответвления: session settings, value search/reveal UX, retention maintenance, agent tool wrappers. Tool consume допускается после связи с K09 и shared budget; наличие primitive interface не равно готовому MCP/A2A.

#### K07. Evidence kernel: до графиков и SIEM

- Зафиксировать allowlisted поля событий, actor authority, safe projections, counters, transaction boundaries и допустимые crash gaps между stores.
- Test-first: failed audit после pending receipt не допускает выдачу; cache/noPII/error также создают решения; секрет отсутствует в log/export; успешный protect и последующая ошибка provider не меняют денежный контракт.
- Минимальное ядро: запись реального decision/admin event и local outbox, consumer cursor и schema version. Внешний sink не нужен для проверки того, что данные не потерялись до очереди.
- **Не делегировать:** логирование «masked» полного текста как будто он безопасен, новые billing rules, вторую независимую схему counters для dashboard.
- Ответвления: SIEM/SMTP/webhook adapters, отчёты, аналитика, история и lightweight incidents.

#### K08. Verification/jobs kernel: инструмент тоже должен проходить проверку

1. `K08-A`: минимальный isolated test runner, oracle/comparability и stamp после K05/K06/K07. Он нужен K04-B и **не зависит от завершения полного batch/regression UI**.
2. `K08-B`: durable job claim/checkpoint/cancel, лимиты и storage после K01/K08-A/admission K09-A. Он нужен batch, delivery orchestration и full suite runs.

До runner пишутся проверки самой методики: неверное восстановление/чужой человек/пропуск SECRET обязаны стать RED, пустой corpus — `not_comparable`, недоступная среда — `blocked`, а не pass. До jobs — kill/restart/stale claimant/double finalize fixtures.

**Не делегировать:** новый «почти production» detector для песочницы, генерацию expected через тестируемую функцию, plaintext upload spool или test-free org из caller body. Ответвления: batch, suites, compare, shadow, per-case feedback. Общий test runner не должен проверять сам себя только своим же отчётом: внешний wire/store observer остаётся независимым.

#### K09. Delivery kernel: до провайдеров и agent middleware

1. `K09-A`: shared admission, fixed destination contract и egress validation. Использует K02/K04/K07, для complete route activation — K04-B; интерфейс лимитов доступен K08-B раньше полной выходной цепочки.
2. `K09-B`: output checks, safe buffer, protected-model/delivery split, one-use live tool consumption и фактическая integration boundary. Зависит от реальных K05/K06 и A; complete tool wrapper проверяется вместе с SDK.

До реализации: wire spy, provider/tool fixtures, escaped JSON и secret split на каждом offset, dangerous redirect, wrong recipient, permit replay и revoked queued permit. Минимальное ядро должно реально не вызвать downstream при deny, а не просто вернуть красивый `Decision`.

**Не делегировать:** перенос проверки после emission, произвольные URL routes, JSON строковую замену, auto-retry неизвестно выполненного tool action. Ответвления: SDK/framework adapters, registered provider routes, DLP connector, tool/source management UI.

### 7.3 Test-first цикл ядра и каждой фичи

Последовательность одинакова для K и T-задач:

```text
S0 контракт и область → S1 тест/гейт + доказанный RED
→ S2 минимальная реализация → S3 GREEN локальных проверок
→ S4 независимый review + mutation/fault проверка
→ S5 реальная интеграция + merge-candidate gates → принято
```

**S0 — контракт:** actor/scope, вход/выход/errors, state machine, ограничения, timeout/retry/expiry, storage/audit/billing, compatibility, зависимости и номер версии. Для security operation указать точку линеаризации и где располагается фактическое enforcement.

**S1 — тесты ДО business implementation:** сначала исполняемые unit/contract/HTTP acceptance tests с test harness, затем код функции. При отсутствии API допускается минимальный production skeleton, возвращающий typed `not_implemented`, и fixture adapter; он не реализует семантику и не выдаёт success. Записать baseline GREEN, новый RED с **ожидаемой причиной отсутствия поведения**, команды и версии. Ошибка импорта, пустой тест, падение сервера до нужной точки или `xfail` не доказывают чувствительность гейта.

**Сначала весь набор требований к гейтам, затем поочерёдно executable slices.** Нельзя достоверно прогнать готовый end-to-end rollout до появления реальных workers, но можно заранее написать runner, входы, oracle и fault controls. Такой гейт получает `defined/blocked_on_dependency`, не GREEN. После появления участника запускается без переписывания ожидаемого ответа под реализацию.

**S2–S3:** реализатор меняет production-код в выделенной области. Tests остаются независимым критерием; корректировка ошибочного теста допустима только с обоснованием требования и review, не «чтобы зелёнело». Сначала минимальное поведение, затем refactor с неизменными tests. Blanket mocks секретов/permission/scope на проверяемой границе запрещены.

**S4:** проверяющий не принимает «все тесты прошли» без manifests. Ввести контролируемый дефект в изолированную тестовую копию или fault seam: пропустить проверку прав, отдать старую policy, создать mapping SECRET, убрать audit, выпустить tail, повторно consume permit. Соответствующий gate обязан стать RED; затем fault убрать и подтвердить GREEN. Test-only fault mechanisms не доступны через production request/config и не попадают как обход в release.

**S5:** проверить реальную композицию: handler → auth → ядро → store → provider/tool observer. Для затронутой gateway/ops возможности запуск source/compiled gates требуется уже при её интеграции, не только в конце W27. Дорогая полная батарея остаётся на контрольных точках; минимальный affected gate subset обязателен на каждой такой поставке.

**Test ownership:** автор реализации может добавлять unit tests, но не единолично менять acceptance oracle. Ответственный за acceptance фиксирует ожидаемые результаты до implementation и проверяет итог. В небольшой команде это разные review-проходы, не обязательно разные люди; при AI-делегировании лучше отдельный контекст проверяющего. Тесты повышают уверенность, но не доказывают отсутствие неизвестных классов ошибок.

### 7.4 Параллельные feature-треки и последовательность внутри каждого

Обозначения: **старт** — минимум для разработки потребителя; **интеграция** — обязательные реальные зависимости. Во всех случаях шаги `Txx.1 → .2 → .3 → .4` выполняются последовательно и каждый проходит S0–S5. Шаг может завершиться контрактно на fixtures, но итог feature не `integrated`, пока не пройдены реальные зависимости соответствующего W.

| Трек | Ядра / старт | Последовательные задачи | Интеграция / доказательство |
|---|---|---|---|
| T01 — Политики и управление | K02/K04 `contract_ready` | T01.1 API schemas/client contract tests → T01.2 draft CRUD/CAS/diff/import/export → T01.3 publish/rollback/CLI/Git-managed adapter → T01.4 editor UI и реальный путь create→test→activate→rollback | K04-B/K07/K08-A готовы; W12/W13 и policy часть W26; CP21–CP23/CP42 |
| T02 — Правила, словари и профили | K04-A/K05 contracts | T02.1 matcher/template fixtures → T02.2 rule/dictionary/exception adapters и builder → T02.3 measured IMEI/IBAN/MAC/custom packs и profile catalog → T02.4 edit→trace→regress→publish с реальным ядром | K05/K08, затем W19 для complete W23; W07/W08/W23; CP12–CP15/CP38/CP46 |
| T03 — Доступ и SSO | K02/K07 contracts | T03.1 role/permission consumer matrix → T03.2 named-access/credentials UI → T03.3 OIDC adapter с SP05 → T03.4 session revoke/bridge/direct API/browser tests | K02/K07 и management contract; W22/access часть W26; CP04–CP06/CP37/CP42 |
| T04 — Песочница, batch и регрессия | K05/K08-A contracts | T04.1 explain/full-run UI и cases oracle → T04.2 CSV/JSONL parser/export + jobs progress → T04.3 suites/compare/shadow/capture permissions → T04.4 verified stamp перед production publish | K08-B/K04-B/K09-A; W11/W18/W19; CP20/CP29–CP30/CP46 |
| T05 — Маршруты и выходные проверки | K09 contracts | T05.1 route registry client/negative fixtures → T05.2 route/local-only/fallback adapters → T05.3 output/stream consumer и две проекции ответа → T05.4 wire-level deny/timeout/sequence/recipient проверка | Реальные K03/K05/K06/K07/K09; W14–W16; CP24–CP27/CP46–CP47 |
| T06 — SDK и agent/RAG adapters | K06/K09 versioned wire contracts | T06.1 Python sync/async client + contract tests → T06.2 LiteLLM/LangChain/LangGraph wrappers и probe → T06.3 registered tools/source metadata/signature packs + online consume wrapper → T06.4 checkpoint/trace/tool-side-effect verification | W17 после W09/W15/W16, complete W24 после W17; CP28/CP39–CP40/CP47 |
| T07 — DLP, SIEM и уведомления | K07/K09 contracts | T07.1 adapters/transport fixtures с faults → T07.2 JSON/CEF/syslogTLS outbox consumers → T07.3 DLP REST + webhook/SMTP и health UI → T07.4 outages/queue saturation/SSRF/required-check verification | K08-B jobs и реальные route/admission gates; W21; CP34–CP36 |
| T08 — Retention, vault и восстановление | K01/K06/K07 contracts | T08.1 delete-plan/ref/expiry model tests → T08.2 TTL/purge/maintenance adapters → T08.3 independently retained deletion-ledger/backup-restore tooling → T08.4 vault UI и race/restore verification | Primitive fences уже в K06; complete W20 ждёт W18/W19 sensitive stores; CP31–CP33/CP03 |
| T09 — Аналитика, отчёты и incidents | K07/K08 event/result contracts | T09.1 aggregate DTO + fixture oracle → T09.2 histograms/SLO/usage/quality/report readers → T09.3 drift/feedback/incident links и alert adapter → T09.4 сравнение всех UI/export цифр с реальными persisted events | Complete W25 ждёт W14/W18/W19/W21; CP18/CP24/CP41 |
| T10 — UI shell, документация и coverage | K02/management DTO contracts | T10.1 shell/navigation/error/accessibility fixtures → T10.2 общие auth-aware API client/forms/tables/guards → T10.3 подключение экранных модулей T01–T09 + onboarding/docs/coverage → T10.4 full browser run по ролям и failure states | W26 завершается на реальных API; CP42–CP43, no mock success/no CDN |
| T11 — Упаковка и эксплуатационная поставка | K01 contracts, W01 baseline | T11.1 source/compiled test runners/native-deps spikes → T11.2 incremental packaging/store/doctor adapters → T11.3 SBOM/compatibility/upgrade-restore procedures → T11.4 полный release-candidate gate run | Работа начинается рано; complete W27 ждёт W01–W26; CP01–CP03/CP44–CP45 |

**Здесь нет дублирования ownership:** в K реализуются invariant/state transition/permission/transaction semantics; в T — потребитель, UX, формат, каталог или adapter. Например, T08 не создаёт вторую deletion fence, T07 не создаёт второй outbox writer, T02 не переписывает policy precedence. При необходимости изменения ядра feature-трек подаёт change request владельцу K, а не правит его самостоятельно.

UI feature-экраны живут в треках соответствующих доменов; T10 владеет только shell, shared components, подключением и whole-app tests. Он не переписывает одновременно все экраны. Это позволяет собирать policy, access и analytics UI параллельно без трёх конфликтующих auth clients.

**Завершающий T12 «AI-разработка» не стартует параллельно production-реализации базовых треков:** после C4 он выполняется последовательно T12.1–T12.8. Contract/spike/test design допускается заранее. Его отдельная последовательность, K10 и release dependencies приведены в §7.10.

### 7.5 Как открывается параллельная работа

Не ждём «всё ядро целиком готово», но и не запускаем все бизнес-фичи на несуществующих контрактах. Следующая схема задаёт фронты готовности, а не общий барьер: отдельный consumer стартует сразу после своей зависимости.

1. **Фронт A — baseline и contracts.** W01; contract/test design K01–K09. SP01/SP02/SP05/SP06 можно исследовать независимо на контролируемых стендах. SP03/SP04 используют согласованные storage/context contracts. T11 готовит runners; T10 может готовить navigation/accessibility fixtures без объявления live API.
2. **Фронт B — state/trust/runtime.** Реальный K01; затем реализации K02 и K03 могут идти независимо при непересекающихся файлах. K07 event schema и acceptance tests готовятся заранее; его production release choreography завершится позже с K06.
3. **Фронт C — decision и transform.** На K02/K03 строим K04-A, на K03 — K05 evidence, затем custom/actions. По stable contracts начинают T01/T02/T03; T09 проектирует projections на event fixtures, не считает mock metrics настоящими.
4. **Фронт D — первый сквозной срез.** K06 → K07 production → K08-A → K04-B. Это основной критический путь C1. Одновременно K09-A admission после K07, T03 OIDC и T11 packaging; K08-B jobs после test runtime/admission. Feature consumers ранее готовы к интеграции, но не сокращают этот safety path.
5. **Фронт E — широкая реализация.** После нужных contracts/ядра T04 batch/regression, T05 output/routes, T07 external adapters, T08 lifecycle tooling, T09 analytics идут параллельно. T06 client/fixtures уже могут существовать; live SDK закрывается после output/receipt integration. T10 постепенно подключает принятые экраны, не ждёт общего финала для каждого.
6. **Фронт F — сборка продукта.** Новые kernels/consumers проверяются попарно и в общем вертикальном сценарии. T11 final release candidate после complete W27 dependencies. Закрываем все CP и оставшиеся cross-track failures, не только individual green reports.

**Полезная параллельность:** T03 OIDC не ждёт batch; T02 templates не ждёт SMTP; T09 report rendering не ждёт production delivery SIEM; T10 shell не ждёт готовности всех detectors. **Неполезная параллельность:** два агента одновременно меняют transaction semantics vault, общий envelope или authority policy, а затем «разберём конфликты».

Планировщик берёт ready задачи с наибольшим числом заблокированных потребителей. Ограничение WIP выбирается по CPU/RAM тестов, числу независимых write scopes и способности интегратора принимать результаты; запуск ещё одного агента на занятый shared file не считается ускорением. Дорогие compiled builds собираются централизованно на конкретной merge-candidate revision, чтобы не повторять одну сборку в каждом треке.

### 7.6 Владение кодом и границы делегирования

Это роли будущего исполнения, не автоматически созданная Agent Team. При использовании teammates требуется явное разрешение владельца; в этой работе изменяется только план.

| Ответственный | Владение | Обязательство |
|---|---|---|
| Архитектор/интегратор | cross-component contracts, semantic changes, общий composition root, migration registry, итоговая сборка | Не пишет каждую кнопку; принимает K и разрешает изменение контракта, держит критический путь |
| Владелец ядра K | несущая логика конкретного компонента, state machine и invariant tests | Один источник истины; не принимает private обходы от consumers |
| Исполнитель трека T | adapters/UI/catalog/read models в своём scope | Не расширяет authority или storage contract, сдаёт evidence manifest |
| Проверяющий acceptance | expected results, security negative cases, can-fail доказательства | Проверяет независимо от заявления реализатора, сохраняет holdout |
| Ответственный за сборку | source/compiled runners, merged artifact/test report | Проверяет общую revision, а не набор разных веток по отдельности |

**Shared hotspots:** [envelope](<prototype/pseudex/envelope.py>), [vault](<prototype/pseudex/vault.py>), [redact](<prototype/pseudex/redact.py>), [detect_all](<prototype/pseudex/detect_all.py>), [service](<prototype/pseudex/service.py>), [proxy](<prototype/pseudex/proxy.py>), [schema registry](<prototype/pseudex/schema.py>), [entrypoint](<prototype/entrypoint.sh>), [UI bridge](<prototype/pseudex/localui/server.py>), [CLI](<prototype/pseudexctl>) и wiki registration — один назначенный writer в конкретный момент. Для consumers интегратор сначала выделяет module seams; запрет одновременной записи не обходится запуском formatter/code generator другим агентом.

**Proposed disjoint scopes:** отдельные adapter-модули SDK, конкретный экран UI, конкретный integration formatter, schema-neutral report projection, template pack плюс его tests. Точные будущие пути назначаются задачей после декомпозиции модулей, не выводятся из названия роли. Каждый трек имеет список `allowed_write_paths` и `read_only_dependencies`; shared module edits оформляются отдельной зависимой задачей владельцу K.

**Schema ownership:** доменный трек может предложить migration, но не назначает номер сам. Интегратор резервирует номера один раз для нового minor и пересобирает registry/lock; несколько веток с одинаковой следующей migration number не принимаются. Никаких новых stores «для удобства фичи» без обновления всех operations.

### 7.7 Пакет задания для AI-исполнителя

Каждая делегация самодостаточна. Нельзя отправлять «сделай аналитический экран» без контракта и тестового оракула.

```yaml
task_id: T09.2
work_packages: [W25]
feature_ids: [F16]
objective: Реализовать агрегированные read models без изменения политики защиты
contract_revision: <зафиксированный hash/schema version>
requires:
  start: [K07.contract_ready, K08.contract_ready]
  integrate: [K07.kernel_ready, W14.integrated, W18.integrated, W19.integrated]
allowed_write_paths: [<точные projection-модули>, <их tests>]
read_only_dependencies: [<event schemas>, <auth API>, <store contracts>]
forbidden:
  - менять authority, policy semantics или billing
  - читать originals для построения графиков
  - считать неизвестное качество нулём или 100 процентами
acceptance: [CP41, <scoped query negative cases>]
test_first:
  - записать ожидаемые aggregates для фиксированных events независимо от реализации
  - показать RED неправильного знаменателя и cross-project query
handoff:
  - changed paths и contract revisions
  - RED/GREEN команды, exit codes и fixture hashes
  - проверенные и пока blocked integration cases
  - ограничения, новые dependencies, нужен ли owner K change
```

Это шаблон, **не объявление существующих задач или модулей**. В реальной карточке ссылки на spec/plan sections, полный список prerequisites и конкретные paths обязательны. Пример T09.2 допускает локальную read-model integration раньше законченного W25; финальный W25 дополнительно ждёт W21 и остальные его prerequisites.

Исполнитель не расширяет scope «заодно», не запускает платные модели без отдельного GO, не меняет frozen corpora, не ослабляет tests и не трогает чужие dirty changes. При contract conflict останавливает зависимую часть и передаёт точный failing example владельцу ядра; независимая работа в своём scope может продолжаться.

### 7.8 Evidence manifest и правила приёмки делегированного результата

Для каждой завершённой K/T-задачи сохраняются:

- baseline revision + patch/dirty scope, contract/schema version, изменённые paths;
- какие требования/F/W/CP покрыты и какая часть gate проверена локально;
- исходный meaningful RED, baseline GREEN, итоговый GREEN, точные команды/exit codes;
- dataset/fixture hashes, тип стенда, engine/bundle/role versions;
- mutation/fault case, который сделал gate красным, и повторный GREEN без дефекта;
- использованные doubles и перечень проверок на реальном ядре/HTTP/container/browser;
- необходимые migration/dependency/native-library изменения и resource measurements;
- известные ограничения и **blocked/not_run/not_comparable** отдельно от pass;
- следующий потребитель и нужна ли перегенерация API clients/tests.

`done` в сообщении агента не является evidence. Нет manifest или не доказан заявленный affected CP → задача возвращается на проверку. Report не содержит customer raw data, access tokens или leased tuning. Отчёты тестов сами проходят secret-safe projection.

**Merge queue:** интегратор берёт один готовый changeset, проверяет write scopes и diff, применяет к текущей интеграционной revision, запускает affected kernel+consumer tests и cross-boundary negatives, затем открывает следующую интеграцию. Независимые builds/tests можно исполнять параллельно; принятие несовместимых контрактных изменений не параллелится. GREEN до merge недостаточен: обязательный report после merge содержит новый revision/artifact digest.

**Contract change:** версия + причина + affected consumers + новые acceptance cases → review владельца K → обновление producer и всех consumers → invalidation старых test stamps → повторная интеграция. Не поддерживать две конкурирующие формы `Decision` или receipt из-за того, что два агента уже успели написать код.

### 7.9 Пример реального разветвления: собственное правило клиента

1. K04-A/K05 фиксируют schema custom type, exact exception, evidence и action plan. Acceptance author задаёт кейсы: настоящий номер, похожий артикул, overlap SECRET, escaped JSON и exhausted fake pool.
2. Появляются исполняемые RED tests и минимальное ядро. После его принятия открываются независимые consumers:
   - T02 делает template pack/builder;
   - T04 делает explain rendering и corpus import;
   - T01 делает draft diff/import/CLI;
   - T09 готовит usage-by-rule projection на безопасных events.
3. Ни один consumer не реализует собственный matcher и не активирует mutable draft. K06/K07/K08-A/K04-B закрывают restore/audit/test stamp/activation в основном фокусе.
4. Принимается один вертикальный сценарий: правило → dry-run → negative suite → publish → запрос через proxy и sidecar → audit → rollback → тот же запрос с ожидаемым изменением.
5. Затем отдельная mutation: оставить старый cache key после publish. CP07/CP22 обязаны упасть, хотя все формы UI продолжают корректно рендериться.

Так ядра получают максимальное внимание, а фичи действительно распараллеливаются. Уверенность создаёт **одинаковая проверяемая семантика на границах**, а не количество агентов и не число зелёных unit tests.

### 7.10 T12 — AI-разработка: последний трек того же спринта

**Выбор владельца:** выпускать целостную систему для интеграторов и AI-разработчиков, а не остановиться на поддержке/CRM. T12 переиспользует готовую платформу и расширяет её на coding tools; не создаёт вторую систему политик и аудита. Полный специализированный контракт — [F23/K10 и coding gates](<docs/tz-ai-coding-track.md>).

**K10, максимальный фокус:** exact original bytes вместо морфологического восстановления; provenance защищённого file view; typed execution plan; Bash subset→literal argv без повторной shell интерпретации; actual workspace/process/network boundary; точка live consume; проверка stdout/stderr до model checkpoint; snapshot-CAS patch. Общее ядро продолжает владеть identity, mappings, revoke, audit и billing. Probabilistic evaluator, включая Jev, не authority и не parser.

| Шаг / пакет | Последовательная задача | Что обязано быть доказано до следующего шага |
|---|---|---|
| T12.1 / W28 | Contract/threat model, SP07 harness/executor compatibility, corpus, test harness и meaningful RED | Поддержанная интеграция реально видит model и execution boundary; AC01–AC12 определены, scope отказов зафиксирован |
| T12.2 / W29 | K10-A exact mappings, protected source map, execution-plan compiler | Shell metacharacters остаются данными; неизвестный контекст/grammar deny; AC02–AC04 |
| T12.3 / W30 | K10-B controlled local executor, workspace/egress/process limits, live consume | Не только approved string, но фактическое исполнение ограничено; AC05–AC07 |
| T12.4 / W31 | Один pinned coding-harness/Anthropic adapter, file read/search и защищённый tool-result loop | Реальный запрос/история/checkpoint не содержат restored values; AC01/AC07/AC09 |
| T12.5 / W32 | Narrow literal patch по защищённому snapshot, safe local diff, sandboxed test profile | Correct bytes/offsets, stale preimage отказ, no fuzzy apply; AC08 |
| T12.6 / W33 | Credentials отдельной registered операции, а не unmask секретов в Bash | Scope/destination/child env ограничены, secret не попадает в LLM/log/vault; AC06/AC10 |
| T12.7 / W34 | Профиль Coding в общей UI/API, workspace/ops/coverage/trace/probe/retention | UI не remote shell, unsupported не enforced, RBAC действует; AC11 |
| T12.8 / W35 | Целостная paired coding приёмка, packaging и повторная платформенная регрессия | AC01–AC12, affected и обязательные общие CP, source/compiled parity; только затем C5 |

**Зависимости:** production start W28 после W27/C4; далее W28→W29→W30→W31→W32→W33→W34→W35. Общие контракты W09/W15–W17/W20/W24/W26 обязательны и уже входят в C4. SP07/contract tests можно подготовить до C4, чтобы ранняя несовместимость harness не обнаружилась только перед релизом. Это подготовка, не скрытый ранний rollout coding executor.

**SP07:** зафиксировать одну версию harness и одну проверенную OS/executor topology. Первый кандидат Claude Code из имеющегося spike; первый изолированный substrate — Linux. Подписочные/auth пути, pre-tool hooks, возможность блокировать незавёрнутые built-in tools, signed/opaque protocol blocks и checkpoint/traces должны быть проверены, а не предположены. Если transparent mode не позволяет enforcement, выбрать documented registered executor integration, не объявлять «смена base_url защищает всё».

**MVP границы:** supported text read/search и простые Bash-команды из validated executable/option grammar, exact data slots; narrow literal patch и отдельно registered credential operation. Arbitrary shell pipelines/expansions/eval, embedded Python/SQL, неизвестные scripts с восстановлением, все IDE и автономный контроль всей машины — не обещание первой версии. Repo tests являются выполнением кода и требуют sandbox profile. Секреты не превращаются обратно в обычный тип reversible PII.

**Общее владение:** T12 пишет coding adapter/fixtures/UI feature в выделенном scope; общие vault/envelope/roles/schema меняет владелец соответствующего K. Spike [anthropic_shim.py](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py>) — reference only: dev bundle, broad header forwarding, fail-open input fallback и logs restored values не переносятся в production.

**Release gate:** прежний T11/W27 проверяет базовую платформу; W35 повторяет packaging/регрессию на новой единой сборке после coding additions. C4 не завершает расширенный sprint. Изменение общего ядра в T12 инвалидирует affected acceptance evidence прошлых треков и требует повторной проверки. Методологические правила сверх уже принятого test-first цикла будут обсуждены следующим отдельным этапом, не придумываются здесь.

## 8. Definition of Done всего объёма

- [ ] Завершающий T12/W28–W35 принят на общем ядре: F23/K10 и AC01–AC12, supported harness/OS задокументированы; C5 подтверждён повторной платформенной регрессией.
- [ ] Arbitrary shell restoration и необёрнутый tool не выдаются за защищённую операцию; exact bytes/patch preimage/credential separation проверены.
- [ ] Для K01–K09 записаны контракты, инварианты и test-first evidence; состояние contract_ready не выдано за kernel_ready.
- [ ] Для T01–T11 соблюдены последовательные шаги и внешние prerequisites; fixtures не заменили real integration.
- [ ] Acceptance tests созданы до business implementation соответствующего среза; meaningful RED и can-fail mutation подтверждены.
- [ ] У каждой делегированной задачи есть write scope, contract revision и evidence manifest; shared hotspots имели одного writer.
- [ ] Все принятые изменения повторно проверены на общей merge-candidate revision; cross-track gates не заменены отчётами отдельных веток.
- [ ] Для каждого выбранного R требования есть F паспорт, work package и can-fail acceptance evidence.
- [ ] Все F01–F22 реально работают в заявленных narrow границах, нет mock successful actions.
- [ ] Обе формы API и соответствующие v2 contracts имеют одинаковую protection semantics.
- [ ] Customer mutations проходят verified permissions/audit/CAS; no UI-only policy semantics.
- [ ] No PII/secret pass-through on required failure; no unsafe output prefix.
- [ ] Unknown/monitor/unsupported/deferred явно показаны; не подменяют enforced.
- [ ] Existing quality/round-trip/collision/perf battery не ухудшена без явного scope-based решения и опубликованного ограничения.
- [ ] New type/custom rule negative+positive+roundtrip+holdout evidence frozen.
- [ ] source/compiled реальные gates; no arbitrary code/URL relay/Docker socket/external UI runtime.
- [ ] Все stores присутствуют в probe/migrate/rekey/decrypt/backup/restore/schema/preflight; old-image downgrade реально refused.
- [ ] Четыре retention класса независимы; tests/raw capture не бесконечные hidden copies; old backup deletion limits документированы.
- [ ] Денежная единица/Pseudex counters не изменились из-за количества findings/stages/testing.
- [ ] SDK real framework examples, preserved masked state, provider failures no silent bypass.
- [ ] Release streams, signed artifact pipeline, SBOM/licences, wiki map/docs актуальны.
- [ ] Market90% не объявлены измеренным результатом; acceptance report отдельно показывает capabilities, quality и unclosed P2.

## 9. Результат текущей проектной работы (не implementation)

Подготовлены три документа: specification, feature matrix и этот work plan. Прочитаны исходники и два внешних материала, проведена независимая проверка feature crosswalk и architecture constraints. Product code, runtime, настройки, тестовые datasets и релизы этой работой не менялись; paid модели/benchmark не запускались.

Проверка документации выполняется отдельно от product DoD: ссылки/IDs/dependencies/coverage, wiki baseline и diff. Существующие ошибки wiki отмечаются как pre-existing, не исправляются скрытой правкой unrelated research. После утверждения владелец может начать W01, но это не автономное разрешение на код/выкатку.
