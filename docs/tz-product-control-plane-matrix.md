# Матрица отбора: требования корпоративного AI-шлюза + пользовательская админка

**Статус: proposal для продуктового спринта.** В исходной матрице 60 групп требований, сопоставленных с 22 архитектурными паспортами. По отдельному запросу владельца добавлены R61–R66 для AI-разработки (F23/T12), всего 66 групп. HITL R28 и документы R22 после решений владельца получили отдельные паспорта F24/F25, итого 25, без добавления выдуманных новых требований. Выбранный объём, архитектура и критерии — в [основной спецификации](<docs/tz-product-control-plane-sprint.md>); порядок исполнения — в [плане](<docs/plan-product-control-plane-sprint.md>).

## 1. Источники, обозначения и правило отбора

- **S1:** [ТЗ корпоративного AI-шлюза](</Users/igor/.dsh/attachments/v1/files/ed/ed5f70976fbb2c8e23b35f6cfb2ced759b907ba2c5e48dae67c3d587eb4589cd/AI шлюз_ТЗ.docx>). Ссылки на разделы по оглавлению и точным заголовкам: экстракция не сохраняет внутреннюю автоматическую нумерацию Word, поэтому номера вида «7.8.3» не выдумываются. Весь основной текст, приложения и три схемы прочитаны.
- **S2:** [UI-концепт локального интерфейса](</Users/igor/.dsh/attachments/v1/files/4c/4c38a9c14ed8baf49c283dcb10bda5d97200980d60335156bac847ea9d99932f/Оптимизация_UI_движка_Docker_контейнера.zip>). Прочитан весь HTML, включая описания, данные, модали и handlers. JavaScript не запускался. Названия экранов — source labels, не готовые backend capabilities.
- **M:** экспертно широко переиспользуемая потребность интеграторов/разработчиков/техлидов. **E:** общекорпоративная потребность, не вкусовщина. **S:** отраслевой/поставщико-/организационно-специфический вариант. M/E/S — не измеренная частота спроса.
- **P0/P1:** предлагается делать в этом продуктовом объёме; P0 фундамент, P1 законченные возможности после него. **P2:** отдельно после спринта. **X:** указанную форму не делать, с безопасной заменой.
- Если capability выбрана узко, строка явно оставляет расширенный остаток. `REST adapter` не означает поддержку любого DLP; `rule` не semantic classifier; `model constraint` не firewall клиента.
- Основная ставка на «90+%»: максимальная повторная применимость механизмов конфигурации, не перенос каждой корпоративной системы внутрь Pseudex. Процент нельзя утверждать из этой матрицы; отдельно нужны спрос и независимая проверка сценариев.

## 2. Полная матрица решений

### A. Подключение, identity и управление

| ID | Возможность / применимость | Откуда | Выбор и архитектурные паспорта | Граница, остаток и причина |
|---|---|---|---|---|
| R01 | Две формы API, совместимость text/JSON/tools и SDK — M | S1 §5 «Основные задачи», §7 «Подготовка и нормализация»; S2 «Интеграция», onboarding | **P0** общий envelope, **P1** thin SDK/adapters; F03/F18/F21 | Сохраняем proxy/sidecar. gRPC, отдельные SDK всех языков и IDE plugins — P2. Не обещать endpoint по красивому mock snippet |
| R02 | Подтверждённая identity сервиса/пользователя — M/E | S1 §7 «Идентификация пользователя и источника», §9 «Идентификация приложений»; S2 «Агенты и org» | **P0** credential-bound project/app и разрешённые host assertions; F01/F02 | Agent labels для аналитики, не полномочия. Подразделение из body не trusted attribute |
| R03 | Агенты и сервисы, profile assignments и изоляция — M | S1 §5/§9; S2 «Агенты и org»; принято UX-consumer-name | **P0** плоский список карточек и effective policies; F01/F03/F08 | Internal project/namespace/environment не обязательная UI-иерархия; одна карточка может представлять всю внешнюю AI-платформу. Broad ABAC/device/risk — P2 |
| R04 | Две роли и выдаваемые разрешения — M/E | S1 §9; S2 equal access; принято AR09/HITL05/HITL06 | **P0** admin/user + explicit feature/HITL/sensitive grants; F02/F09/F20/F24 | Backend gates до mutating UI, originals отдельно. Это не полное обязательное IT/IB/auditor разделение S1 и не all-users-full-access demo |
| R05 | Корпоративный SSO и MFA — E | S1 §9 «Корпоративная аутентификация», «AD/LDAP/IdM, OAuth/OIDC/JWT»; S2 формы SSO нет | **P1** OIDC code flow + local session; F02 | OIDC generic. MFA у IdP; native MFA/SAML/LDAP/SCIM/IdM sync и прямые AD adapters — P2. Не импортировать storefront SSO в контейнер как доказательство |
| R06 | Действия allow/mask/pseudonymize/delete/block/local-only — M | S1 §7 «Решения по результатам проверки», приложение 2; S2 действия своих правил | **P0** общий decision algebra и transforms; F03/F07/F11 | Route constraint отдельно transform; deny dominates. Partial mask — explicit ограниченное раскрытие, не эквивалент полной псевдонимизации |
| R07 | Черновик, history, selected apply, no-restart и rollback — M | S1 §6/§7; S2 «Политика»; POLICY-batch-apply | **P0** snapshot/CAS/worker ACKs + consumer-target validation; F04 | Unselected сохраняют revision/overrides. Preflight failures: показать/deep-link, явно eligible subset либо никому; silent partial update запрещён. Fleet — P2 |
| R08 | Import/export/CLI/GitOps и diff — M | S1 §6 управление, §11 обновления; S2 «Политика», команды export | **P0** versioned references, **P1** CLI/API/import/export; F04/F18 | Import только draft, никаких creds/roles в portable policy. Полноценный GitOps server и multi-stage releases — P2 |

### B. Настраиваемая защита данных

| ID | Возможность / применимость | Откуда | Выбор и паспорта | Граница, остаток и причина |
|---|---|---|---|---|
| R09 | Custom type по маске/примерам/regex/checksum — M | S1 §7 «Многоуровневое выявление», пользовательские шаблоны; S2 «Свои правила» | **P0** restricted builder + RE2 + safe custom token family; F05 | Только bounded declarative pattern/готовые validators; inferred pattern требуется проверить. Python callbacks/backtracking fallback — X |
| R10 | Customer dictionaries и списки — M | S1 §7 словари; S2 exact values/hint words | **P0** отдельные versioned dictionaries; F05 | Не редактировать leased ФИО/ГАР. Большие enterprise data fingerprint indexes/fuzzy customer gazetteers — P2 |
| R11 | Scoped exact exceptions, свои контакты/артикулы — M | S1 §7 исключения; S2 allow-list из quality/trace | **P0** reason/expiry/category/scope и impact tests; F06 | Глобальное «never mask» regex и исключения, снимающие SECRET/КТ obligations, — X. Approval weakening отдельно |
| R12 | Каталог типов, пресеты и subscription entitlement — M/S | S1 §7 категории, приложение 3; S2 «Типы данных», «Профили» | **P1** truthful runtime registry и versioned presets; F19 | Реально implemented, entitled, configured, active, mandatory — отдельные состояния. Новая тарифная модель не часть спринта |
| R13 | Confidence thresholds и toggles mechanisms — M/E | S1 §7 пороги, §10 confidence; S2 slider± и secret subgroup disable | **P1** evidence и только поддержанные controls; **X** universal numeric slider; F03/F19 | Calibrated ML thresholds — P2. «Кандидат найден, но не masked» считается изменением защиты и явно проверяется |
| R14 | Каталог native типов и недостающие customer formats — M/S | S1 приложение 3; S2 профили; current-main baseline | **P1** expose/profile/test существующих IMEI/IBAN/MAC и native v6 families, custom extensions только для реальных gaps; F19 | Не реализовывать native detector повторно. Registry→engine labels и validity inheritance сохраняются; качество требует negative/holdout/round-trip. Наличие нескольких форм не означает все банковские/телеком/юридические форматы |
| R15 | Credentials: detect/block/redact/reference/approved exception — M | S1 §7/§12; S2 demo secret reveal; принято AR13/CRED/HITL | **P0** default block/scoped redact, **P1** service-purpose refs и HITL; F07/F24 | Нет обычного reversible SECRET PII mapping. Разрешены approved encrypted credential/pending stores; raw model egress только opt-in once-only exact approval. Logs/plaintext backups запрещены; scoped deviation от строгого S1 явно указан |
| R16 | КТ/НМД/договор/код как trusted classification и patterns — E/S | S1 §7 категории, приложение 2; S2 «Свои правила» | **P1** trusted labels+customer dictionary→policy; F03/F05/F11/F22 | Не весь код автоматически секрет, не любой договор автоматически КТ. Provenance должна быть verified |
| R17 | Семантические категории, fingerprints и ML classifiers — E/S | S1 §5 много методов, §7 semantic detection, приложение 3 | **P2** отдельные локальные classifier/fingerprint modules | В этом спринте generic typed REST connector как расширение F17, но он не shipped detector. Нужны собственные корпуса/лицензии/latency/ресурсы |
| R18 | Проверять весь поддержанный контекст — M | S1 §5 assets, §7 полный контекст; S2 text/JSON и integration | **P0** единый envelope, system/history/tools/results, offsets/provenance; F03/F05/F22 | skip_system из request не authority в managed. Не все форматы OpenAI/Anthropic автоматически поддержаны: explicit supported schema |
| R19 | Output checks и разрешённый detok — M | S1 §7 «Проверка ответа», «Восстановление»; S2 restored panel/quality | **P1** новые secret/PII/custom findings, destination/field restrictions; F08/F10 | Detok ≠ output DLP. Нулевой residual ≠ правильный человек. Full semantic output moderation — P2 |
| R20 | Streaming safety, choice/tool fields — M | S1 §11 streaming, приложение 5; S2 «Проверка шлюза» | **P0** field/choice contract, **P1** full safe buffer; F10/F18 | Сначала checks, затем release. Low-latency semantic prefix scanning — P2. Stop-after-leak не исправление утечки |
| R21 | Явный отказ неподдержанных files/image/audio — M | S1 §5/§7 полный контекст, §12 bypass; S2 batch | **P0** capability manifest+415 в protected managed path; F03/F20 | Text из approved parser поддержан с provenance; нельзя молча pass-through и писать checked |
| R22 | Документы на границе контекста модели — M/E | S1 §5/§7/§12 + DOC-ARCH | **P1 основной sprint**, F25/K12/T14/W40–W44, DOCG01–DOCG10 | Текст/структура из tool_result (read_doc и т.п.) маскируются как прочий контекст; сырой файл модели не нужен. file-attachment к провайдеру → block/extract/route, raw не пропускать. Без OCR и без native-перезаписи файла. Документный бенчмарк обязателен |

### C. LLM, RAG и инструменты

| ID | Возможность / применимость | Откуда | Выбор и паспорта | Граница, остаток и причина |
|---|---|---|---|---|
| R23 | Prompt injection/jailbreak detection — M/E | S1 §8 «Безопасность LLM», §12 injection tests; S2 отдельного classifier screen нет | **P1** bounded RU/EN signatures, evidence, monitor/block calibration; F22 | Семантический local detector, устойчивость multi-turn/multilingual/encoding — P2. Signatures не полная защита; `all OWASP neutralized` — X |
| R24 | Защита RAG fragments и происхождение — M/E | S1 §8 «Защита RAG», §10 provenance | **P1** fragment/source/classification/assertion metadata и общие checks; F22 | ACL утверждения host проверяются. Gateway не изобретает права источника. Ingestion poisoning/anomaly vector store/knowledge graph ACL — P2 |
| R25 | Approved tool registry, description/schema integrity, actions — M/E | S1 §8 «Безопасность агентов», «MCP/A2A»; S2 agents/integration | **P1** tool IDs/digests/ops/schema/restore permissions + execution wrapper; F08/F18/F22 | Полный MCP protocol proxy, динамический skill supply chain и semantic tool poisoning — P2. Tool name allowlist не sandbox |
| R26 | A2A, delegated rights, план/цель/память агента — E/S | S1 §8 агентная/межагентная защита | **P2** отдельные protocols/capabilities/agent runtime integrations | Глубина/count/deadline для интегрированного tool loop входят F22. Automatic intent/goal deviation classifier, memory poisoning полнота — не обещаем |
| R27 | SSRF и запрет неконтролируемого egress — M/E | S1 §8 SSRF, §9 network segmentation | **P1** наших proxy/DLP/SIEM/OIDC endpoints и registered tool destination; F11/F17/F22 | Remote tool должен иметь собственный egress enforcement/sandbox; это P2 adapter/infrastructure. Список имени tool не закрывает произвольный HTTP |
| R28 | Runtime HITL queue/UI/API — E/M | S1 §7 + HITL01–08 owner decisions | **P1 основной sprint**, F24/K11/T13/W36–W39, H01–H10 | Encrypted pending payload, no auto-expiry card default, separate reveal grant; exact once-only decision/attempt/live checks. Raw-key exception opt-in принят, technical bypass нет. Native resume OPEN-H01; four-eyes publish не требуется |
| R29 | Toxicity, языки, темы, phishing/reputation — E/S | S1 §7 output, §8 LLM, приложение 3 | **P2** локальные detector packs/репутационный connector | Exact запрещённые terms/category dictionaries возможны F05/F10, но не называются semantic moderation. Разрешённый язык не надёжный security boundary |
| R30 | Релевантность, factuality, bias и качество ответа — E/S | S1 §7 optional relevance, приложение 3 | **P2** scenario-specific evaluation, **X** universal truth guarantee | Не отправлять raw к внешнему judge автоматически. Product regression нашего transform отдельно F14; оценка содержания требует источников истины |

### D. Инструменты разработчика и контроля качества

| ID | Возможность / применимость | Откуда | Выбор и паспорта | Граница, остаток и причина |
|---|---|---|---|---|
| R31 | Настоящая text/JSON песочница и selfcheck — M | S1 §12 reproducible tests; S2 «Песочница», «Проверить сейчас» | **P1** explain vs real mask→restore, isolated namespace; F13 | Provider по default не зовём. Статическое повторение input в restored panel — X |
| R32 | Batch CSV/JSONL — M | S2 «Песочница/Пакет»; S1 §12 testsets | **P1** bounded streaming parse, progress/cancel/errors/privacy-safe export; F13/F21 | 20MiB/100k rows proposal до benchmark. 200MiB mock/huge jobs arbitrary formats — P2. Sensitive input opt-in, no plaintext spool |
| R33 | Explain/trace candidates/context/checksum/overlap — M | S1 §10 объяснение rule/mechanism; S2 «Почему так?» | **P1** реальная instrumentation всех gates; F03/F13 | Raw trace с permission, no production mint. ML explanation и отсутствие candidate как «не ПД» — P2/X соответственно |
| R34 | Клиентский корпус, negatives и regression перед publish — M | S1 §11/§12 regression; S2 «Регрессия», rule test panel | **P0** минимальный stamp/critical cases, **P1** полноценный UI run/compare; F04/F14 | Stamp engine/bundle/policy/suite/dictionary. Critical test failure не обходить обычной кнопкой publish |
| R35 | Testset retention/ACL/version/provenance — M | S2 save example/history; S1 §10 allowed content | **P1** отдельный encrypted jobs store, expiry, explicit save/export/delete; F14/F15 | Real cases отдельная sensitive surface. SECRET samples synthetic recipe; no automatic retention source text |
| R36 | Preview изменений и historical replay — M/E | S2 policy diff/dry-run14d; S1 §6 monitor/§10 provenance | **P1** comparison saved suites/batch и explicit bounded opt-in sample; F14 | Existing masked preview не raw archive. Replay14d по всем сообщениям без capture — X. Huge replay scheduler — P2 |
| R37 | Shadow новой policy/rule — M | S1 §6 «Параллельный мониторинг»; S2 watch/live | **P1** parallel draft analysis с budget, active enforcement сохраняется; F14 | Timeout→not_evaluated. Mirror произвольного трафика вне нашего protocol — P2. Monitor не protected |
| R38 | FP/FN/round-trip quality и feedback — M | S1 §7 ≤5%, §12 Precision/Recall/F1; S2 «Качество детекции» | **P1** labeled basis/denominator/provenance/confirmed wrong-value; F14/F16 | Автоматический recall всей production без labels, 100% по 200/residual0 — X. Representative annotation queues — P2 |

### E. Данные, наблюдаемость и эксплуатация

| ID | Возможность / применимость | Откуда | Выбор и паспорта | Граница, остаток и причина |
|---|---|---|---|---|
| R39 | Request decision journal, entity events, admin history — M | S1 §7/§10/app4; S2 «Журнал», «История» | **P0** per-request safe ledger, actor/version/action/counts; F09 | Entity dedup отдельно, cache hits не пропуски в decision journal. Full content storage не default |
| R40 | Reveal, access audit, value search — M/E | S1 §9/§10; S2 «Раскрытия»/«Волт»; HITL06 | **P0** separate permission+audit-before-value, **P1** safe UX; F02/F08/F09/F15/F24 | Не generic SECRET reveal из PII vault. Sensitive pending access допускается только своим явным grant; ordinary reviewer не получает originals автоматически. Misses/direct API тоже audit |
| R41 | Vault TTL, session isolation и deletion — M/E | S1 §7 временные соответствия; S2 «Волт/90д» | **P1** separate lifetime domains/live refs/deletion epochs; F08/F15 | Idle TTL не absolute, cleanup links не deletes originals. Legacy permanent mapping сохраняется до explicit migration |
| R42 | Audit/admin/reveal/analytics retention — M/E | S1 §10 logs и §11 backups; S2 period filters | **P1** separate deadlines/quotas/privacy/aggregate retention; F09/F15 | Billing cumulative counters не очистить. WORM/legal holds и root-proof immutable audit — P2 |
| R43 | Diagnostic capture и data minimization — M/E | S1 §10 allowed content; S2 dry-run/history/support | **P1** capture off, explicit scope/purpose/permission, encrypted TTL; F14/F15 | Не требуется для defaults/graphs; неизвестные secrets не гарантированно исключены. Поддержка без автоотправки. Universal full traffic recording — X |
| R44 | Drift/аномалии/уведомления — M | S1 §10 recurring violations/anomalies; S2 «Дрейф»/channels | **P1** deterministic series+shape candidates+review, webhook/SMTP; F16/F17 | New shape ≠ утечка. ML mining/seasonality/automatic rule fix — P2/X |
| R45 | Лёгкий incident lifecycle — M | S1 §10 расследование; S2 «Инциденты» | **P1** evidence→draft fix→run→verified close/reopen; F09/F16/F20 | Без SOC case management/собственного task tracker/SLA orchestration: P2 |
| R46 | Агрегированные отчёты и выгрузка — M | S1 §10 reporting; S2 «Отчёты» | **P1** local print/CSV/JSON, единый DTO, gaps/versions; F09/F16 | Доказательство «мы предпринимали меры», не автоматический legal compliance certificate. Scheduled reports — P2 |
| R47 | Latency/stages/SLO/error budget/readiness — M | S1 §11 perf/monitoring, app6; S2 «Трафик и SLO», дежурный | **P1** shared real histograms, known denominator, health/readiness/coverage отдельно; F16/F21 | Demo values не baseline. Error-budget auto governance/fleet observability — P2 |
| R48 | Size/rate/queue/concurrency/time/steps — M | S1 §5/§8 resources; S2 traffic/system | **P0** limits до expensive checks, **P1** shared per-app admission; F12/F22 | N workers не N×allowance. Resource limiter не лимит лицензии; advanced global multi-node counters — P2 |
| R49 | LLM tokens/стоимость/Pseudex billing — M/E | S1 §10 usage/cost; S2 tokens/subscription | **P1** actual/estimated/unknown accounting, preserve billing; F12/F16 | Universal token reservation/reconciliation/price routing — P2; no usage ≠ 0. Core commercial terms не менять |
| R50 | Jobs, диагностика, support bundle, onboarding/docs/search — M | S1 §11 ops; S2 «Система», docs, CmdK, onboarding | **P0** safe jobs role, **P1** truthful scoped UI/doctor/support composition; F13/F20/F21 | UI не shell/Docker controller. Support без raw data/keys и автоотправки; статусы errors реальные |

### F. Интеграции, маршруты и промышленная поставка

| ID | Возможность / применимость | Откуда | Выбор и паспорта | Граница, остаток и причина |
|---|---|---|---|---|
| R51 | Защищённые OpenAI/Anthropic API endpoints и destination constraints — M/E | S1 §6; уточнение владельца ROUTE01/02 | **P1** fixed upstream bindings/UI onboarding/protocol-aware security forwarding; F11 | Не model catalogue/selection: model выбирает клиент, proxy сохраняет её, sidecar не вызывает provider. Trust class задаёт администратор, не caller |
| R52 | Provider fallback/load balancing/model routing | S1 §5/§11; явное отклонение владельца ROUTE02 | **X для нашей роли:** не берём обязанности LiteLLM | Ошибку upstream возвращаем caller; другой provider выбирает host. Security restrictions не обходятся, подключение к существующему LiteLLM как одному upstream допустимо |
| R53 | SIEM delivery, CEF/syslog/JSON/REST — E/M | S1 §10 SIEM + app4; S2 notifications, отдельного SIEM screen нет | **P1** durable sanitized bounded outbox, HTTPS/JSON+CEF/syslogTLS; F09/F17 | At-least-once/event_id dedup. Queue mode required vs best-effort. Vendor correlation/WORM anchors — P2 |
| R54 | DLP sync/async/check failure — E/S | S1 §6/§10 DLP; S2 интеграции без DLP UI | **P1** fixed REST adapter actual verdict/enforcement, timeouts; F17 | Generic REST test fixture и реальный connector contract, не «все DLP». ICAP/собственные DLP detectors/vendor-specific templates — P2 |
| R55 | KMS/keys/rotation/TLS/mTLS — M/E | S1 §9 crypto/secrets, §11 ops; S2 «Волт/ключ» | **P1** existing customer key resolver, all-store rekey plans, TLS adapters; F02/F11/F15/F21 | No UI-editable KEY_CMD, keys never shown. mTLS на наших fixed outbound adapters допустима configure refs; собственный CA/HSM/TPM service и сертификация — P2 |
| R56 | Backup/restore без revival deleted data — M/E | S1 §11 backups/RTO/RPO; S2 vault ops | **P1** config/audit разделение, legacy inventory, tombstone-aware restore; F15/F21 | Данные вне контроля клиента нельзя erase promise. Cross-node DR/SLA и scheduled orchestration — P2; offline compaction honest |
| R57 | Engine/policy/bundle/schema versions, release и SBOM — M/E | S1 §11 update/supply chain; S2 policy versions/system | **P1** отдельные versions, store migration+old-probe fence, SBOM/licenses; F04/F19/F21 | Policy rollback ≠ image rollback. Не добавляем migrations под locked minor; docs не подтверждают shipped gate |
| R58 | HA, горизонтальный multi-node cluster и fleet management — E | S1 §6/§11; уточнение владельца AR01/AR04 | **P2 вне текущего scope:** выбран один инстанс = одна локальная консоль и максимально быстрый запуск | Multi-node/control center/Kubernetes сейчас отвергнуты как лишняя сложность. Несколько upstream URL/apps в одном инстансе входят F11, это не cluster. Shared SQLite/NFS и N workers как HA — X |
| R59 | Air-gap/perpetual offline licensing и обновления — E/S | S1 §11 isolated contour; S2 local UI offline claim | **P2**, отдельный уже описанный delivery contract | UI без CDN делаем F20. Это не offline engine. Сохраняется принятый бессрочный design в [offline spec](<docs/tz-offline-license.md>), не переоткрываем условия и не обещаем реализацию в текущем sprint |
| R60 | Web Chat персональных аккаунтов, full corporate interception и закупочные условия — S | S1 §3/§6 web accounts, §13 исполнители | **X** как core sprint feature; adapters/procedure отдельно | Не строим браузерный credential relay, собственные DLP/SIEM/IAM/inference/agent platform; лицензия/опыт исполнителя не software checkbox. API-controlled channels развиваем R01 |

### G. AI-разработка — добавлена владельцем как последний трек текущего спринта

Источник R61–R66 — прямое расширение задачи владельцем, не приписываем эти детали исходному корпоративному ТЗ или mock UI. [Полный coding-контракт](<docs/tz-ai-coding-track.md>) и §7.10 общего плана задают F23/K10/T12, W28–W35 (Claude slice) + W45 (Codex), AC01–AC13.

| ID | Возможность / применимость | Выбор | Граница и причина |
|---|---|---|---|
| R61 | Coding harness и execution boundary — M | **P1 завершающий T12**, F23/W28–W35 + subsequent W45 | Claude Code первым, затем Codex (AC13), Linux/macOS/WSL независимо; native PowerShell и остальные IDE — вне scope. Exact C5 release boundary Codex OPEN-C01 |
| R62 | Exact mappings и provenance для paths/search/data literals — M | **P1**, F23/K10 | Не NAME morphology и не fuzzy restore; scope session/workspace, ambiguity deny |
| R63 | Bash subset с typed plan, literal argv, live consume и sandbox — M/E | **P1**, F23/K10 | Arbitrary shell/eval/nested languages restoration — X для первой версии; parser не заменяет OS enforcement |
| R64 | Protected file read/search и snapshot-bound literal patch — M | **P1**, F23 | Source map/bytes/CAS, no stale/fuzzy patch, executable contexts только с supported adapter; language-wide AST rewriting P2 |
| R65 | Coding credentials без модели и обратимых secret mappings — M/E | **P1**, F23 + F07/F11/F22 | Narrow registered operation/approved destination; secret в arbitrary command/env процесса с неограниченными правами — X |
| R66 | Coding profile, trace/retention/coverage и доказанная целостная поставка — M | **P1**, F23/F20/F21 | AC gates + повторная CP-регрессия на новой сборке/C5; no claim «весь трафик» или «все AI-кодеры» |

Это уточняет R01: Claude Code затем Codex входят в план последовательно; остальные IDE отдельно. R25/R26 full MCP/A2A не становятся выполненными от local executor. Jev и собственный semantic R&D отменены владельцем для текущего спринта; внешние DLP interfaces и существующая NER этим не отменены.

## 3. Остаток P2: что действительно НЕ закрываем этим спринтом

Эти возможности не называются готовыми и не прячутся в «есть API»:

| Остаток | Предлагаемая архитектура следующего объёма | Почему отделён / критерий входа |
|---|---|---|
| Семантическая КТ/НМД/клинические данные | local classifier service или pinned local model behind typed check adapter; корпуса, device/RAM/latency budget, model licence; документ-level verdict | Словарь не смысл. До measured corpus и лицензирования не обещать detector |
| Enterprise fingerprints | encrypted keyed exact-data index, normalized signatures, provenance+retention, bounded matching; raw reference data остаются у клиента | Hash сам по себе не распознаёт перефразирование/фрагмент. Нужен independent precision/coverage benchmark |
| Semantic prompt injection/jailbreak | отдельный локальный classifier pack, adversarial RU/EN corpus, monitor calibration, enforcement independent tool boundary | Сигнатуры F22 не покрывают adversarial generalization. Cannot promise «все» |
| Full moderation/reputation | typed local scanner APIs, categorical policy, reputation dataset freshness и approved egress | Нужны разные модели/источники; toxicity не эквивалент утечке |
| RAG ingestion/source ACL/poisoning | retrieval/ingestion adapters with verified source ACL and document versions; quarantine/index hooks | На LLM boundary есть только переданные fragments, не весь knowledge store |
| Полный MCP/A2A/skills | transport-aware proxy, server/tool stable identity+digest, delegated attenuated capabilities, per-operation executor; approved egress sandbox | Модельная schema не фактическое исполнение. A2A delegation самостоятельный protocol |
| OCR/images/audio/general multimodal | Отдельные parsers/OCR/models, resource and coverage evidence | Исключены сейчас. **Документы на границе контекста уже в F25**, не P2; file-attachment и unknown embedded content не пропускаются raw молча |
| HA/DR/fleet | Store interfaces для control/vault/audit/jobs, внешнее transactional encrypted-at-rest storage, domain uniqueness, leadership/fencing, restore/probe evidence | SQLite single-host не кластер. Redis кеш один не делает mapping durable или consistent |
| Offline engine | реализация текущего [бессрочного design contract](<docs/tz-offline-license.md>), activation payload/узловые ключи/O gates/offline updates | Не лечится grace/кешем lease и не делается отключением checks |
| KMS/HSM/native MFA/LDAP/SCIM | fixed provider adapters, least privilege, rotations/recovery, IdP lifecycle; algorithm/scope tests | Existing key resolver и generic OIDC дают общую интеграцию, не заменяют corporate IAM/HSM |
| Advanced token budgets/cost attribution | Verified usage, reservations/reconciliation, prices versioning | Не Pseudex billing. Model routing/provider fallback/balancing **отклонены как наша роль**, не обещанная будущая функция |
| Immutable external audit/legal holds | append-only external sink with signed checkpoint anchor, retention legal-hold workflow | Root клиента может изменять свои local stores; SQL append-only API не WORM |
| Полный SOC/case management | экспорт evidence/correlation в существующий SOC; extensible incident refs | F20 lightweight issues достаточно для tuning, не нужен второй SIEM |
| Дополнительные языки SDK/IDE/gRPC | wrappers generated from contract + protocol parity suites; no local recognizers | После доказанного Python/HTTP contract, не сначала пять непроверенных клиентов |

## 4. Разрешение противоречий источников

| Конфликт | Нормативный выбор этого проекта |
|---|---|
| S1 изменение правил без restart, S2 restart+8с503 | Policy hot activation F04, infrastructure operations отдельный maintenance/CLI. Не promises «всегда 8с» |
| S1 strict secrets block/delete, S2 demo substitute+reveal | F07 default block/redact; owner разрешил service-purpose credential refs, encrypted pending F24 и explicit opt-in one-use original-to-model. Это сознательное ограниченное отклонение, не полный S1 compliance |
| S2 no weakened protection, sliders below-threshold no-mask | Evidence-based controls и explicit weakening review, no pretend safety through candidate counting |
| S2 exact allow wording против pattern allow | F06 exact scoped exceptions; patterns add protection, не global exemptions |
| S2 quality100%/FP/FN из counters | F16 labeled basis; technical metrics отдельно; no fake zeros или confidence |
| S2 historical14d replay против минимального entity log | F14 suites/batch/explicit capture; no fabricated raw reconstruction |
| S2 «26/18 типов» против перечисленных16 | F19 один authoritative registry и фактический count |
| S2 equal access против S1 IT/IB/auditor | Приняты admin/user с выдаваемыми правами, original reveal отдельно. Ни модель demo, ни всё S1 буквально не копируются |
| S2 idle90d против S1 temporary session и agent memory | F08/F15 lifetime domains, idle+absolute, explicit long-term, legacy protected |
| Offline UI claim против external demo runtime | F20 vendored runtime; engine air-gap R59 отдельно |
| Policy versions против current engine versions | F04 и F21 оба остаются; schema/bundle/revision различны |
| Fail-closed против monitor/availability | Required errors блокируют; optional/monitor not_evaluated не green. Provider outage не переключает URL/model автоматически |
| S1 полное покрытие угроз против наблюдения только LLM-boundary | F22 controls с named boundaries, P2 modules и coverage registry вместо absolute promises |

## 5. Покрытие функциональных экранов UI и явные отличия

Функциональные разделы прототипа сопоставлены с выбранной системой; это traceability, не доказательство реализации или согласия со всеми demo defaults:

- Обзор/selfcheck/дежурный → F13/F16/F20/F21.
- Журнал/раскрытия/история → F02/F08/F09/F15/F20.
- Песочница text/batch/trace → F03/F13/F21.
- Качество/трафик/SLO/дрейф → F14/F16/F17.
- Отчёты → F09/F16.
- Политика/версии/import-export/environments → F03/F04.
- Типы/secret subgroups/профили → F07/F19 с перечисленными correction.
- Свои правила/точные значения/подсказки/templates → F05/F06.
- Агенты/org/доступ → F01/F02/F03/F08: пользовательский раздел «Агенты и сервисы», без обязательной org/project иерархии.
- Регрессия → F14.
- Волт/search/delete/key/TTL → F08/F15/F21, UI не выполняет shell.
- Интеграция/snippets/probe/fail-closed → F11/F17/F18.
- Подписка/диагностика/support → F12/F20/F21, данные счётчиков не ошибка стоимости LLM.
- Инциденты → F09/F16/F20, evidence-backed close.
- Docs/search/shortcuts/onboarding → F20, generated registry+contracts.
- Дополнения владельца: runtime queue/HITL → F24; документы на границе контекста → F25; это не уже присутствующие mock screens.

Ничто из listed UI не считается уже реализованным на основании mock. Отложенная функция не получает активную кнопку с toast успеха; UI показывает `unsupported/not_available` и причину.

## 6. Приоритеты без смешения с календарём

1. **Сначала P0:** trust boundaries, snapshot/cache, schema/stores, ledger/secret safety, scoped rules/receipts и минимальные tests.
2. **Затем вертикальный цикл:** rule→trace→regression→publish→decision→rollback. Это первая пригодная к использованию контрольная точка.
3. **После core:** документы T14 и HITL T13 равноприоритетно параллельно, необходимые output/bindings/limits/SDK/lifecycle по dependencies.
4. **Затем enterprise:** стандартные OIDC/DLP/SIEM после основных сценариев; ранняя проработка контрактов разрешена.
5. **Coding последним:** Claude Code затем Codex, independent OS/harness gates.
6. **P2 отдельно:** semantic/industrial/прочие protocols; semantic R&D не выполняется в текущем sprint, Jev отменён. Provider routing не обещаем и в P2 как нашу роль.

Границы срезов не меняют выбранный конечный P0+P1 объём автоматически. При нехватке capacity owner явно переносит целое capability с изменением этой матрицы и основного документа. Безопасность нельзя оставить «на следующий спринт» для уже выпущенной изменяющей кнопки.
