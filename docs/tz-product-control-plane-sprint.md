# Pseudex: спринт управляемой защиты ИИ — проектная спецификация

**Статус: proposal / методологическое согласование с владельцем. Не описание поставленных функций и не разрешение начать реализацию.**

Архитектурные defaults и UX-варианты этого документа проходят отдельное согласование в [реестре решений владельца](<docs/decisions-product-control-plane.md>). Положительная оценка общего плана не означает принятия всех частных решений. Явные новые решения фиксируются в реестре и затем синхронизируются с affected sections.

**Целевая аудитория:** интеграторы, разработчики AI-приложений, владельцы B2B AI-платформ и технические лиды. **Цель:** превратить существующее ядро защиты в настраиваемый продукт с едиными политиками, API управления и локальной админкой. Сделка, КП и персональная реализация заказчику не являются предметом этого документа.

Связанные документы: [матрица отбора возможностей](<docs/tz-product-control-plane-matrix.md>), [план реализации и приёмки](<docs/plan-product-control-plane-sprint.md>), [AI-разработка — завершающий трек](<docs/tz-ai-coding-track.md>).

**Дополнение владельца:** AI-разработка включена в тот же спринт как F23/T12 после базовых F01–F22. Единство означает общие policy/identity/audit и поддержанные integration boundaries, а не обещание защиты любого сетевого трафика или произвольной shell-программы. Финальная приёмка расширенного объёма — C5; конкретные coding contracts остаются проектными до проверок. Jev отменён владельцем для этого спринта; [исследование](<research/jev-typesafe-product-fit.md>) сохранено как архив, не integration backlog.

**Принято владельцем — HITL:** ручное подтверждение policy-остановленных операций входит в sprint (прежнее P2 отменено). Default SECRET = block; irreversible redact адресно настраивается. Очередь в нашей UI + единый API; pending operation сохраняется и продолжается по точному согласованному содержимому, не долгим HTTP. Принято HITL04: pending payload кратковременно хранится зашифрованным внутри Pseudex с отдельными правами/очисткой и без raw content в audit/долговременных backups; точный TTL ещё уточняется. Это разрешённая transient sensitive copy, а не обычный reversible SECRET mapping. Default разрешения — безопасное преобразование; отдельная настройка может открыть уполномоченному reviewer **разовую отправку исходного ключа модели** с предупреждением/основанием/audit без raw key. Это явное исключение из защиты, не raw fail-open и не technical-check bypass. Пользователь также запросил credential substitution «модель видит подстановку, инструмент получает ключ»; proposed реализация — отдельная scoped credential reference, не обычный PII vault/unmask arbitrary Bash. Прежние абсолютные запреты raw-secret передачи ниже читаются как default; полный exception/credential contract разрабатывается по [реестру решений](<docs/decisions-product-control-plane.md>).

**HITL lifecycle уточняется:** владелец выбрал сохранять карточку ожидания без автоматического исчезновения по умолчанию; auto-expiry настраиваемая опция, 1h/24h не утверждены. Review SLA/reminder, retention и таймаут активного HTTP/tool вызова разделены. Возможность продолжить exact operation после approvals зависит от реальной pause/resume интеграции caller; не обещаем воскресить timed-out tool call или скрытно исполнить его после закрытия harness. Предлагаемый fallback explicit reattach/retry с live recheck сейчас на согласовании. Нельзя использовать timeout command/http hook Claude Code как fail-closed gate; это отдельный обязательный negative acceptance case SP07/AC.

**Принято SCOPE-files/DOC01:** document protection входит в основной sprint, результат — native защищённый PDF/DOCX с сохранением структуры/оформления, не extraction-only text. Принято DOC02/03: только DOCX/PDF с text layer, без OCR; best-effort сохранение структуры/оформления с явным показом допустимых изменений, существенное повреждение — failure. Принято DOC04: при непроверенных изображениях/embedded parts по default не выдавать файл как защищённый; показать причину, разрешить убрать части либо отдельно явно согласовать partial processing с честным coverage. Partial download не означает разрешение автоматического external egress. Нельзя считать весь mixed document защищённым автоматически. Нужны форматные rewrite/rebuild, удаление hidden originals/metadata и независимый artifact no-leak gate; визуальная плашка сама по себе не защита. **SEM01 отменяет semantic R&D:** отдельный поиск/дообучение малого смыслового classifier убраны из текущего спринта, остаются возможным будущим backlog; текущие NER/rules/DLP contracts этим не отменены. Новые document work/gates добавляются при консолидации до реализации, CSV/JSONL eval не их замена.

## 0. Как читать и что считается решением

- `P0` — несущий фундамент и безопасность. Делается первым; зависимые возможности без него не выпускаются.
- `P1` — выбранный функциональный объём этого продуктового спринта после P0. Это не «когда-нибудь» и не необязательные декоративные экраны.
- `P2` — следующий самостоятельный объём; в этом спринте только явно названные точки расширения, без заявления о готовности.
- `X` — не делаем в указанной форме: противоречит продукту, не даёт проверяемой гарантии либо является чужой задачей.
- «Делаем» ниже означает **предложенный выбор для согласования**, не уже утверждённый ADR. Новые модули, таблицы, ручки, лимиты и тесты — проектируемые.
- Спринт здесь — один согласованный продуктовый объём, разбитый на последовательные инкременты. Это **не обещание уложить весь объём в две недели**. Численность команды и календарная ёмкость неизвестны; оценка длительности выполняется после технических spikes. При сокращении сначала исключается целая P1-возможность с обновлением матрицы, а не её безопасность.
- «90+% потребностей рынка» — целевая гипотеза, не измеренный результат. Мы выбираем переиспользуемые возможности и явно показываем остаток. Количество строк этого ТЗ не является долей рынка или качеством обнаружения.
- Пути в ссылках на репозиторий отсчитываются от рабочего корня. В блоках `proposed` названы ещё не существующие файлы.

### 0.1 Исходные материалы

1. [ТЗ корпоративного AI-шлюза](</Users/igor/.dsh/attachments/v1/files/ed/ed5f70976fbb2c8e23b35f6cfb2ced759b907ba2c5e48dae67c3d587eb4589cd/AI шлюз_ТЗ.docx>): функциональные разделы 5–11 и приложения 2–6. Используем требования как данные, не копируем клиентские схемы и текст целиком в продуктовую документацию.
2. [UI-концепт](</Users/igor/.dsh/attachments/v1/files/4c/4c38a9c14ed8baf49c283dcb10bda5d97200980d60335156bac847ea9d99932f/Оптимизация_UI_движка_Docker_контейнера.zip>): 19 пунктов навигации; интерактивный прототип, не backend и не доказательство качества. Встроенные демонстрационные regex, значения, таймеры и CDN-runtime не переносятся в production.
3. Код текущей рабочей копии: версия [0.3.19](<prototype/version.txt>), схема [0.3](<prototype/schema_lock.json>). Исходники проверены чтением, не повторным прогоном продуктовых тестов. Dirty-изменения пользователя не сбрасываются.
4. Принятые ограничения: [инварианты](<wiki/INVARIANTS.md>), [потоки](<wiki/FLOWS.md>), [дисциплина изменения API](<docs/integration-shared-gateway.md>), [локальная UI v1](<docs/tz-local-ui.md>), [пользовательские правила/SDK](<docs/tz-roadmap-from-oss.md>), [вертикали](<docs/tz-verticals-and-configurator.md>), [версии и миграции](<docs/tz-release-and-versions.md>).

### 0.2 Предлагаемый результат спринта

Интегратор регистрирует приложение, назначает политику, добавляет свои идентификаторы и исключения, проверяет изменения на примерах, публикует их без перезапуска движка, получает объяснимые решения, настраивает срок хранения и экспорт событий. Те же возможности доступны через management API, CLI и локальную админку. На входе и выходе работают конкретные поддерживаемые проверки; восстановление разрешено только внутри установленных границ.

```text
BEFORE: свой формат → тикет нам → изменение движка → новая поставка.
AFTER: свой формат → правило → негативы и round-trip → версия политики → публикация.
Effect: поддерживаемая конфигурацией адаптация не требует новой сборки движка.
```

## 1. Реальная точка старта

| Область | Что есть в коде | Разрыв для этого спринта |
|---|---|---|
| Две формы подключения | [service](<prototype/pseudex/service.py>), [proxy](<prototype/pseudex/proxy.py>) и общий [envelope](<prototype/pseudex/envelope.py#L1-L11>) | Новая семантика должна проходить через обе формы; не создавать третью копию обхода |
| Детекция | [Detector.detect](<prototype/pseudex/detect_all.py#L171-L279>): normalize → recognizers → suppress → resolve | Нет клиентского каталога правил и evidence/trace; общий [Span](<prototype/pseudex/detect.py#L13-L18>) не содержит confidence |
| Исключения | [own_values](<prototype/pseudex/service.py#L662-L666>) | Настройки запросом не равны управляемой, доверенной политике |
| Кеш | [org + conversation + raw text](<prototype/pseudex/maskcache.py#L42-L65>) | Нет policy/bundle/scope/exception epochs; ошибки invalidation нельзя скрыть UI |
| Assets | [атомарная замена pointer](<prototype/pseudex/assets.py#L439-L482>) | Не snapshot всего запроса; несколько функций читают глобальный ASSETS повторно |
| Vault | [SQLCipher и views](<prototype/pseudex/vault.py#L2169-L2201>) | Основные mapping постоянны; TTL только [вспомогательных данных](<prototype/pseudex/vault.py#L3735-L3747>); нет custom token family/receipt/политики удаления |
| Auth | общий gateway/admin bearer; [tenant key](<prototype/pseudex/tenants.py#L18-L34>) | org/agent labels не подтверждают пользователя; provider passthrough не identity |
| Админка | отдельный процесс, vendored Preact/htm, [точный allowlist](<prototype/pseudex/localui/server.py#L100-L107>) | Одна authority, [scope контейнера](<prototype/pseudex/localui/server.py#L279-L291>), имена со слов пользователя; нет CRUD политик/RBAC |
| Обратное плечо | [detok content/arguments](<prototype/pseudex/envelope.py#L287-L326>), streaming carry | Нет самостоятельной output DLP; residual не правильность restored value |
| Аудит | [events / requests / reveals / detoks](<prototype/pseudex/audit.py#L54-L109>) | events не журнал каждого решения; нет policy revision и доставки SIEM |
| Биллинг | [metering.bill](<prototype/pseudex/metering.py#L24-L34>): один успешный masking call | Не менять денежную единицу на число сущностей, стадий, тестов или output checks |
| Процессы | [N независимых процессов](<prototype/serve_main.py#L1-L23>), [entrypoint](<prototype/entrypoint.sh>) | Нет coordinator rollout и durable jobs; multiprocessing frozen image не подходит |
| Schema/операции | [3 stores](<prototype/pseudex/sqlite_setup.py#L65-L81>), [registry](<prototype/pseudex/schema.py#L144-L155>) | Новый store входит во ВСЕ операции; нужен новый minor, старый probe должен реально отказать |
| Offline/HA | Дизайн [offline](<docs/tz-offline-license.md#L1-L19>); local SQLite/WAL | Не поставлены; N workers не multi-node HA; в этом спринте не обещаем |

Устаревшие утверждения документации не являются контрактом реализации: обе поверхности уже используют общий envelope; после полной expiry [detok зависит от bundle](<prototype/pseudex/service.py#L685-L696>); новейший offline-дизайн бессрочный, а не на 6/12 месяцев.

## 2. Границы и неизменяемые свойства

### 2.1 Что сохраняем

1. RU detection, морфологию, форму подстановок, canonicalization, защиту коллизий и tool-call loop. Не переписываем движок на другом языке и не заменяем built-in типы универсальными placeholders.
2. Шифрование SQLCipher, ключи клиента, отсутствие импорта licensing из engine, данные вендора только в leased bundle.
3. Fail-closed: невозможность обязательной проверки означает отказ, не исходный трафик во внешнюю модель.
4. Нормализацию offset-safe 1:1. Дополнительные представления классификатора имеют явную карту offset, не подменяют общую normalize.
5. Нет PII pre-filter; нет re-detect masked transcript как будто он сырой.
6. JSON-aware восстановление аргументов; один carry на choice; tool arguments целиком; не выдаём их текстовым chunk-detok.
7. UI отдельно от engine и без внешних шрифтов, аналитики, CDN, error tracking. Наша платформа лицензий не получает клиентские правила, тесты, личности, тексты или события.
8. Зелёный health не доказательство безопасности всего приложения. Local deployment не означает air-gap и multi-worker не означает HA.

### 2.2 Чего спринт не обещает

Полного покрытия OWASP, семантического обнаружения любой КТ, OCR/аудио/изображений, достоверности любого ответа, полного SOC, собственного корпоративного IAM, HA-кластера, HSM-сертификации, офлайн-лицензирования либо контроля действий инструмента вне нашей точки исполнения. Эти вещи имеют явные P2/X решения в матрице; не называем все их «вкусовщиной».

### 2.3 Режимы совместимости

**Принято CONNECT03:** базовый защищённый proxy onboarding — base_url+Pseudex key, без обязательного SDK. Расширенные гарантии включаются при наличии нужной identity/receipt/integration capability. Если native API не передаёт trusted conversation_id, строгую изоляцию не имитируем эвристикой: UI обозначает weaker basis, требующая строгого scope policy не применяется silently. Advanced adapter — по необходимости, не условие любой базовой защиты. Ни один режим не raw fail-open.

- `legacy`: существующие API и credentials, прежний контракт и предупреждение об ограниченном trust. Не выдавать shared org label за multi-tenant RBAC. Никаких автоматических миграций raw provider keys в административные identities.
- `managed`: приложение с зарегистрированным service key, server-resolved project и assignment, явные conversation_id/destination; новый контракт v2 и receipts. Это режим выбранных возможностей.
- Проект в managed не обслуживается через legacy-ключ «в обход»: миграция включает установку запрета legacy для соответствующего проекта и проверку обеих legs. Это распространяется также на legacy `/unmask*`, `/reveal`, `/events`/экспорт и общий ADMIN_TOKEN: без named/scoped authority они не читают managed namespaces или receipts. Legacy org alias разрешается через bounded compatibility binding, не используется как произвольный внутренний namespace UUID.
- Защита обязательных данных не продаётся по цене количества включённых recognizers. Entitlement новых отраслевых типов отличается от режима действия политики. Ценообразование и право перепродажи этим документом не меняются.

## 3. Целевая архитектура поверх ядра

### 3.1 Компоненты и размещение

**Действующее уточнение владельца AR01/AR04:** один инстанс = одна локальная консоль, сохраняем максимально быстрый запуск. У каждого клиента независимый контур; наша готовая UI и полный API. Распределённый control center, управление удалёнными узлами, fleet/HA и Kubernetes не входят в текущий sprint. Прежняя multi-node интерпретация отменена (§4bis реестра).

**Область настраиваемости:** один инстанс обслуживает разные приложения/агентов и несколько настроенных направлений API. Несколько upstream URL не означают несколько инстансов. Схема ниже снова является standalone baseline; её конкретные storage/process детали ещё обсуждаются, а внутренние N workers не пользовательские узлы.

```text
локальная Preact UI / CLI / API клиента
          │ management credential, RBAC
          ▼
management router → ControlStore(control.db)
                    immutable policy revisions, principals, assignments, audit
          │ prepare / activate, persistent epochs
          ▼
N engine workers ← same shared local volume (один хост)
          │ AuthContext + request-start active revision
          ▼
envelope traversal → DetectionResult → policy decision → transformation
          │                                                 │
          │                         Vault + receipts (vault.db)
          ▼
proxy: разрешённый route → provider
sidecar: route constraint + protected envelope → host enforcement
          ▼
output validation → authorised detok → delivery decision
          ▼
DecisionLedger + outbox (audit.db) → housekeeping process → SIEM/webhooks

housekeeping process: jobs orchestration, bounded delivery, retention sweeps
UI остаётся отдельным процессом, не импортирует service и не leases
```

Это **модульный монолит с отдельными ролями процессов**, не микросервисная перестройка. В single-node форме нет Redis/Postgres/Kafka/OPA обязательным dependency. От OPA берём проверяемые patterns immutable revision / activation status / decision logs, не Rego runtime. Мультиузловая backend-замена — P2.

### 3.2 Предлагаемые точки расширения

Ниже `proposed`, не карта существующих файлов:

```text
prototype/pseudex/control.py           ControlStore, migrations, CAS revisions
prototype/pseudex/identity.py          auth context, keys, principals, RBAC
prototype/pseudex/policy.py            schemas, compile, effective policy, decision
prototype/pseudex/rollout.py           worker membership, prepare/ACK/activate
prototype/pseudex/custom.py            restricted recognizers, dictionaries, token recipes
prototype/pseudex/decision.py          per-request ledger + privacy-safe projection
prototype/pseudex/output.py            output checks, buffer, recipient-bound detok
prototype/pseudex/agentguard.py        source/tool identity, digests, signatures, operation limits
prototype/pseudex/routes.py            fixed destination registry + constrained proxy routing
prototype/pseudex/limits.py            per-app admission and shared counters
prototype/pseudex/jobs.py              durable bounded jobs + orchestration
prototype/pseudex/retention.py         reference-aware sweeps and purge plans
prototype/pseudex/integrations.py      explicit adapter registry / egress validation
prototype/pseudex/management.py        engine-owned management router and permission gates
prototype/pseudex/testsurface.py       isolated explain/run/compare/regression
prototype/pseudex/catalog.py           truthful detector/profile capability registry
prototype/sdk/                        тонкий HTTP client и integration adapters
prototype/pseudex/localui/static/      сохраняемый frontend, разбитый по экранам
```

Не создавать произвольную файловую proxy, plugin loader/import path из policy, shell hooks, docker.sock либо engine restart endpoint. Модули только connectors получают stateful classes; чистая evaluation функциональна. Backend домены не зависят от UI.

### 3.3 Модель идентичностей и областей

- `installation`: одна поставка, не юридический tenant.
- `project`: граница конечного клиента/системы с изолированными настройками и данными. Название/пользовательский org_id — alias, UUID назначает сервер.
- `application`: зарегистрированный вызывающий сервис внутри project. `agent_id` информационная метка либо зарегистрированный sub-scope, но не право доступа из самого текста.
- `environment`: dev/test/prod; назначения версии независимы. Production vault не используется для test.
- `principal`: admin либо service; роли и project bindings разрешаются сервером.
- `conversation`: явный ID внутри project/app; в managed не выводится по первым двум сообщениям.
- `namespace`: серверный UUID для vault_domain; strict session по умолчанию для новых managed projects, project scope — явный режим долговременной памяти. Legacy namespace не переименовывать автоматически.
- `destination`: заранее зарегистрированная модель/инструмент/получатель. `local=true` из body не делает endpoint доверенным.

Жёсткая граница project проверяется для запросов, поисков, jobs, export, trace, reveal, receipt и UI selection. UUID не служит credential. Список проектов определяется ролью, не `GET /orgs` всей установки.

### 3.4 Stores и таблицы

| Store | Предлагаемые таблицы | Принцип |
|---|---|---|
| control.db | projects, applications, principals, credentials, role_bindings, admin_sessions, policies, policy_revisions, custom_type_revisions, dictionary_revisions, exception_revisions, tool_revisions, tool_permits, run_budgets, source_bindings, profile_revisions, assignments, deployments, worker_acks, destinations, integrations, admin_events, admin_outbox, test_suite_refs, feedback, incidents, maintenance_plans | HKDF label `pseudex/store/v1/control`, SQLCipher. Policy revision immutable, draft editable CAS. Роли/сессии не UI-only |
| jobs.db | jobs, job_chunks, test_suites, test_cases, test_runs, run_results, diagnostic_samples | HKDF label `pseudex/store/v1/jobs`, SQLCipher. Bulk uploads/test material отдельно от коротких control admission tx; это не снимает общую дисковую конкуренцию |
| vault.db | существующие tokens и индексы; namespaces, sessions, mapping_refs, custom_tokens, receipts, receipt_tokens, restore_permits, stream_sessions, deletion_tombstones | Mapping refs и receipt фиксируются в одной транзакции. Никаких SECRET original mappings для новых managed requests |
| audit.db | существующие events/requests/meta; request_decisions, stage_metrics, delivery_events, decision_outbox, provider_usage, admission_counters | Решение и его SIEM outbox одной tx. Кумулятивный billing ledger переживает retention событий |
| tenants.db | существующие compatibility credentials | Не смешивать административную identity с tenant/upstream secret |

`policy_revisions(id,policy_id,revision,content_hash,schema_version,content,author,created,state)`; уникальны `(policy_id,revision)` и `content_hash` в контексте policy. Content хранит references на fixed revisions словарей/types/routes, не «текущий изменяемый словарь». Secrets — отдельные secret refs; экспорт политики не экспортирует passwords/keys.

`receipts(id,secret_digest,project,app,conversation,namespace,policy_revision,policy_hash,bundle_version,decoder_contract,auth_epoch,retention_epoch,destination,status,expires_at)` и `receipt_tokens(receipt_id,mapping_id,type)`; receipt в wire — случайный opaque 256-bit handle, в store только HMAC/digest. `receipt.id` в аудите не его секрет. Домен token/namespace не выбирается вызывающим из arbitrary строк.

`request_decisions(id,request_id,project,app,subject_ref,phase,destination,policy_revision,bundle_version,action,reason_codes,check_results,counts,cache_hit,status,timings,created)` без raw текстов, original values и restore handles.

Нет общей atomic transaction между разными WAL-файлами. Последовательность: permission/admission → begin local decision → compute → vault commit receipt со статусом pending → audit decision+outbox commit → success accounting → receipt deliverable → release response. Restore дополнительно требует durable audit completion: pending receipt не авторизует выдачу, даже если случайно получен handle. При отказе обязательного audit commit response/egress не выпускается; orphan mappings удаляются по refs/TTL. Для mint+receipt потребуется transaction-aware UnitOfWork в vault: нынешние helpers самостоятельно commit, внешний BEGIN без их переделки не атомарен. Admin mutation+admin_event+admin_outbox — одна tx control.db. Не обещать exactly-once генерацию модели или расход лицензии при любой аварии; сетевой retry — отдельный вызов согласно существующему billing contract. Review stamp связывается с immutable suite/run digest из jobs.db; удаление test material до publish проверяется отдельно и инвалидирует stamp.

### 3.5 Snapshot, кеш и многопроцессная активация

1. В каждой worker generation фиксируются immutable compiled customer policy и compatible custom rules. На request start читается durable active assignment в короткой transaction; DB недоступна в managed → 503, не молчаливый бесконечный stale cache.
2. `RuntimeContext`: verified identity, assignment epoch, policy revision/hash, asset bundle version, custom/type/dictionary versions, scope, namespace, exception digest, retention epoch, phase, destination class и auth epoch.
3. Cache key включает всё, что влияет на **преобразование**. Subject-bound решения, route permissions, DLP и audit не пропускаются по cache hit. Кеш текста нельзя использовать как кеш решения «разрешить запрос».
4. В cached result только protected output + safe finding descriptors/mapping IDs; не raw values. После TTL/deletion epoch проверяются references прежде чем выдать cache hit. Кеш с output `allow` может содержать raw permitted content: для такой политики raw-bearing результаты не кешировать данным MaskCache.
5. Customer rollout: `draft → validated → preparing → ready → active`, либо `failed`. CAS на expected active_revision. Housekeeping инициирует prepare; каждый живой worker компилирует, сохраняет ACK с digest и generation. Без ACK activation не называется успешной.
6. Commit active assignment атомарен в control.db. На следующем запросе worker обязан взять эту revision; нет compile → 503 `policy_not_ready`, а не старое решение. Worker, присоединившийся после prepare, не ready до загрузки active version. ACK membership не гарантия бессмертия процессов; UI показывает missing/unready.
7. Уже принятый запрос заканчивает на pinned policy revision. Emergency revoke application/destination/lease проверяется ещё раз непосредственно до внешней передачи/раскрытия; revoke сильнее обычного pinning. Старый receipt не может сохранять отозванное право.
8. `ASSETS` сейчас глобальный. До публикации P0 нужен request-level asset pinning: preferred ContextVar snapshot, доступ через Assets.get/version; synchronous pipeline/threads явно получают context. Тест доказывает, что каждое чтение в одном проходе видит одну revision. Lease revoke увеличивает epoch, блокирует egress и очищает caches; snapshot не даёт доработать в revoked state. Не сохранять vendor bundle на диск и не держать прошлые leases ради пользовательского rollback.
9. Rollback создаёт новый deployment epoch на проверенную старую customer revision с проверкой совместимости текущего engine/catalog. Не откатывает engine, vault, vendor bundle, identities или события.

### 3.6 Policy schema и семантика

**Принято AR10/AR11/AR20:** общая безопасная политика плюс профили приложений с явными адресными overrides. Effective policy и источник настройки видны пользователю. Уполномоченное ослабление допускается для заданного приложения/категории/направления с предупреждением, автором и основанием. Overrides компилируются при публикации, не являются runtime caller bypass; deny-dominates ниже относится к уже собранной effective policy. Обычная публикация: draft → обязательная автоматическая проверка schema/conflicts/контрольных примеров → показ diff → apply; второй человек не обязателен по умолчанию. Детали распространения base policy и состав контрольных suites ещё согласуются.

Декларативный schema_version=1, закрытые enum и unknown-field rejection. Пример, не текущий API:

```json
{
  "schema_version": 1,
  "name": "support-prod",
  "checks": {"builtin_pii": "required", "secrets": "required", "dlp": "disabled"},
  "default_action": "pseudonymize",
  "rules": [
    {"id": "secret-deny", "when": {"category": "SECRET"}, "action": "block"},
    {"id": "contract-local", "when": {"category": "CUSTOM:contract"}, "action": "route_constraint", "destinations": ["local-contracts"]}
  ],
  "output": {"checks": ["secrets", "custom_block_lists"], "stream_mode": "buffered"},
  "vault": {"scope": "conversation", "idle_ttl_seconds": 86400, "absolute_ttl_seconds": 604800},
  "audit": {"raw_capture": false, "decision_retention_days": 30},
  "exceptions_revision": "ex-4"
}
```

Разрешённые условия: project/environment/application bindings, registered agent, authenticated group refs, phase, category/custom_type, source class, destination ID/class, tool ID/operation. Group rules не применяются к caller labels без verified assertions. Время/устройство/произвольный риск-DSL — P2.

Решение состоит из `deny`, `transformations`, `allowed_destinations`, `required_checks`, `restore_constraints`, `limits`, `audit_requirements`; это не один scalar «allow/mask/local». Объединение ограничений: deny dominates; allowed_destinations пересекаются; required_checks объединяются; лимиты берут наиболее строгие. Empty intersection → deny. Не поддерживать «последнее правило всегда побеждает». Для пересекающихся замен компиляция выдаёт deterministic conflict, а не новую нестабильную маску.

Recognizer priority выбирает **границы сущности**, не отменяет security finding. SECRET, document classification и DLP deny оцениваются до отбрасывания overlapped spans. Exact exception действует на указанную built-in категорию/значение/source/app и не снимает иной SECRET/КТ finding. Базовый recognizer нельзя глобально отключить одним неясным checkbox; `allow` на конкретном доверенном направлении — явная, журналируемая политика, а не fail-open.

## 4. Паспорта выбранных возможностей

Каждый паспорт задаёт бизнес-результат, минимальный законченный объём, архитектуру, UI/API, ограничения и наблюдаемые критерии. Индивидуальная приёмка обязательна вместе с общей батареей.

### F01. Агенты и сервисы: карточки подключений и сервисные ключи — P0

**Принято UX-consumer-name:** пользователь видит плоский раздел «Агенты и сервисы» внутри одного инстанса. Карточка представляет как отдельного агента, так и целую корпоративную AI-платформу с одной политикой. Обязательной вложенности org/project/environment/app нет; внутренние scope IDs остаются технической деталью. Выделение внутренних агентов платформы optional и требует trusted integration, не автообнаружения authority по пользовательскому тексту.

**Результат:** свои настройки и отчёты для каждой интеграции, без доверия к произвольному org_id.

**Архитектура:** identity/control + adapter к существующему tenant flow. Непрозрачные ключи 256-bit с key_id; store хранит HMAC/digest, scopes, app binding, issued/revoked, expiry. Отдельные роли management и data-plane. Legacy key импортируется только явной операцией администратора с привязкой и проверкой; не меняет existing mapping namespace.

**Настройки/API/UI:** CRUD projects/applications, issue/revoke/rotate credentials, bindings на environment; экран «Приложения», creator получает secret один раз, UI никогда не показывает upstream secret. Active sessions отключаются security epoch. Caller subject assertion доступен только apps с отдельно выданным `assert_subject`; issuer/group mapping фиксирован, self-declared admin не принимается.

**Приёмка:** key проекта A не читает/не меняет/не раскрывает B; подмена body project и label agent не расширяет доступ; revoke действует на обоих legs и существующем restore handle; общий gateway token не admin key. Empty/foreign ID возвращает одинаковую privacy-safe ошибку.

### F02. Именные администраторы, RBAC и OIDC — P0 роли, P1 SSO

**Принято AR09/HITL05:** ровно две базовые роли admin/user. Admin управляет инстансом и может выдавать user дополнительные права на любые нужные настройки и HITL; user по default safe logs/errors/stats/sandbox. Просмотр originals отдельно, с аудитом (HITL06). Не вводим обязательный role constructor/иерархию/пять ролей; прежние списки owner/policy_editor/operator/auditor/developer ниже — superseded design и не implementation requirement. Fine-grained checks сохраняются на backend за простыми группами прав UI; управление чужими полномочиями — административная операция, не неявный эффект выданного feature grant. Полное S1 разделение IT/IB/auditor не заявляется автоматически.

**Результат:** разработчик тестирует, ИТ эксплуатирует, ИБ меняет политику, аудитор читает; раскрытие отдельное право.

**Архитектура:** backend permissions в management/data disclosure, не скрытые кнопки. Роли `owner`, `policy_editor`, `operator`, `auditor`, `developer`; `reveal` и `capture_read` отдельные grants по project. Owner не получает reveal автоматически. Startup token только bootstrap первого owner; production после bootstrap shared-password режим запрещён или явно legacy-only. Локальные именованные accounts: scrypt через существующую cryptography, random salt, rate limits, password change/revoke; encrypted admin_sessions, opaque bearer в Authorization. Токены не в URL/логах/localStorage.

**OIDC:** готовая поддерживаемая OIDC/JWT библиотека (Authlib + проверенный JOSE слой, pin/SBOM/gates), не самописный decoder. Authorization Code + PKCE S256, state/nonce, issuer/audience/alg allowlist/exp/nbf, fixed JWKS endpoints, exact redirects; no arbitrary jku/x5u. Browser login одноразовый handoff, привязанный к pre-login transaction, затем local header session; OIDC tokens не дают data-plane доступа сами по себе. MFA делегирована IdP; native MFA/SAML/LDAP sync — P2.

**UI/API:** «Доступ» показывает реальные principals, grants, sessions, отозвать; `whoami` effective project scope. State login/logout также в access audit. Поисковые endpoint требуют той же фильтрации.

**Приёмка:** policy_editor не раскрывает, operator не публикует; прямой curl соблюдает роли; revoked session/JWT wrong audience/forged groups/malicious issuer отклоняются. OIDC flow работает без cookies на mutating API; login-CSRF/replay тесты обязательны.

**Default роли → grants (проектируемый контракт):**

| Роль | Grants по назначенным project | Чего нет по default |
|---|---|---|
| owner | project/application/access administration, policy_edit/policy_publish, integration_admin, retention_admin, audit/analytics read | reveal, capture_read, value_search и sensitive-case/config export без отдельного grant |
| policy_editor | policy_edit, rule/dictionary draft management, test_execute, scoped audit/analytics read | policy_publish/approve, access administration, reveal/capture |
| operator | operational status/health/integration health, approved maintenance execution | policy edit/publish, raw content/reveal, выдача ролей |
| auditor | audit/analytics/history/config metadata read, safe aggregate export | mutation, raw content/reveal, secrets/config values |
| developer | test_execute, собственные case management, application integration docs/probes | prod policy publish, чужие raw test cases/capture/reveal |

`policy_approve`, `policy_publish`, `access_admin`, `integration_admin`, `retention_admin`, `analyst`, `reveal`, `capture_read`, `value_search`, `sensitive_config_read/export`, `real_case_read/export` — именованные scoped grants, а не новые неописанные роли. При four-eyes approver не author/initiator; publisher проверяет approval текущей revision. Owner может управлять grants только через журналируемую explicit операцию с установленными правилами согласования; bootstrap не даёт скрытого раскрытия. Редактору для чтения сохранённых PII exact lists нужна explicit sensitive_config grant, audit показывает change counts/digests без исходных значений.

### F03. Общий policy engine и объяснимое решение — P0

**Результат:** одна настраиваемая семантика для ingress/egress/RAG/tool context, не отдельные правила UI и SDK.

**Архитектура:** frozen DTO `Finding(category,path,start,end,mechanism,evidence,score?)`, `Decision`, `RuntimeContext`. Raw value временно внутри обработки и не сериализуется в ledger. Rule evaluation чистая функция. Built-in suppression и resolution сохраняются; trace instrumentation фиксирует candidates/dropped/conflict reasons до resolve. `score=null` для deterministic checks; не изобретать вероятности.

**API/UI:** explain возвращает policy rule IDs, action reasons, route constraints, required checks и применённые versions; policy editor выбирает короткие условия из registry. Тестирование выключения mandatory check требует explicit exception с основанием и не снимает fail-closed.

**Приёмка:** конфликт «SECRET block + app allow» блокирует; external local label не обходит ограничения; порядок policy rules не меняет result вне явно разрешённой precedence; cache hit выдаёт новый decision/audit и не пропускает DLP/auth.

### F04. Черновики, сравнение, активация, rollback, GitOps — P0

**Принято POLICY-batch-apply:** если preflight не проходит для части выбранных consumers, UI показывает причины/deep links и два действия: явно применить к остальным прошедшим либо не применять никому. Silent partial update запрещён. После выбора target subset/diff/revisions фиксируются; concurrent changes требуют повторного preview. Runtime failure после commit — отдельное truthful deployment state, не скрытый preflight success.

**Принято AR10-propagation:** новая revision применяется явно к выбранным consumers либо «ко всем» после impact preview/validation/подтверждения. Сохранить общую policy не означает автоматически обновить всех. Assignments не выбранных consumers остаются на старой revision; overrides видны в effective diff. Термин consumer/application — logical агент/сервис одного инстанса, не новый deployment; пользовательское название ещё выбирается.

**Результат:** смена защиты без рестарта и незаметного ослабления.

**Архитектура:** lifecycle §3.5, versioned references на types/dictionaries/exceptions/destinations. Edit CAS через If-Match; отсутствие precondition → 428, конфликт → 412. Draft не действует на production. Validation: schema/regex quotas/conflicts/safe generator/required test suite/current entitlements. Publish immutable hash, activation отдельная операция и deployment ID. Import не activates и не переносит credentials/principal grants.

**Availability gate:** минимальный runtime capability/entitlement registry входит уже в P0 F03/F04 и W05/W12; полный human catalog/profiles F19/W23 приходит позже. Если ещё действующая обновлённая lease перестала предоставлять обязательный mechanism/generator, affected managed assignment не ready и admission отказывает; нельзя молча исполнить policy на подмножестве recognizers. Старые receipts проверяют отдельно наличие нужного recorded decoder/output-check contract и live entitlement requirements; неизвестная совместимость означает typed refusal, не silent restore fallback.

**API/UI:** draft/edit/validate/diff/prepare/activate/rollback/status/export/import. Production weakening (exception, allowed destination, TTL увеличение, capture) требует reason + отдельного permission и второго подтверждения; при настройке four-eyes — другого principal, не второй клик того же. CLI export JSON, validate, import draft, publish; секреты только env-file/secret refs.

**Приёмка:** два редактора не теряют правки; invalid revision не меняет active; worker missing ACK не рисует applied; kill coordinator mid-prepare сохраняет старую active; запрос после commit не обслуживается старым rule; rollback не оживляет revoked key.

### F05. Собственные типы, безопасные regex и словари — P0

**Принято AR12:** понятный конструктор с примерами/шаблонами/списками/контекстом и расширенный безопасный regex режим для инженера. Выбор конкретной библиотеки и лимитов подтверждается spike; arbitrary executable hooks не входят.

**Результат:** лицевой счёт, внутренний ID, договор, артикул/полис клиента настраиваются без engine patch.

**Архитектура:** custom recognizers объединяются с candidate stream в detect_all до общего resolution; custom document findings живут вне span-priority и могут block/route whole envelope. Способы задания: exact dictionary, structural mask, named JSON/form fields + shape/context, advanced RE2 regex. По примерам строится только кандидат structural mask с показанными сегментами и негативами; без auto-activation и без внешнего LLM.

**RE2:** использовать официальный google-re2, pinned после packaging spike. Никакого fallback на Python re для клиентских expressions. Не поддерживаем backrefs/lookaround/произвольную рекурсию, code hooks и validators на Python. Seed quotas: 100 активных custom rules/project, 2 KiB expression, 16 MiB общий dictionary, 100k entries, max entry 256 chars; значения — предлагаемая безопасная конфигурация, performance gates могут только обоснованно изменить их. Regex compilation имеет memory budget, лимиты work растут с числом rules; линейность одной regex не отменяет общего лимита. Ограничить также общий compiled-policy/dictionary cache на worker, не только размер одной regex: начальный бюджет 64 MiB на customer compiled state, отдельно учитывать prepare peak двух snapshots в preflight. Известный LRU официального binding не оставлять без контроля (его default до 128×8MiB): ownership/cache очищаются при eviction/delete/revoke; превышение бюджета отклоняет prepare с понятной причиной, не вызывает OOM. Точный max_mem одного expression и memory budget фиксирует SP01, а не выбирает пользователь из UI.

**Token family:** UUID custom type сохраняется через rename. `custom_tokens` отдельно от built-in canonical PK, с namespace/type/value key и original form, уникальный fake в namespace с проверкой против всех built-in/custom tokens и real values. Формат-сохраняющая recipe для structural types; bounded mint, проверка checksum-INVALID при соответствующей recipe. Opaque marker разрешён только явным выбором с честной оговоркой; exact restore без fuzzy/morphological обещаний. Если recipe не может обеспечить безопасную подстановку — publish запрещает pseudonymize, предлагает block/delete.

**UI/API:** «Свои правила», builder, library версионированных шаблонов; dictionary import/diff/count с project grants. Пользователь не редактирует leased ФИО/ГАР vocabulary. Match scores только у реально реализованных mechanisms.

**Приёмка:** ReDoS corpus не зависает; загруженный словарь не выполняет JS/Python; rule A не действует в B; overlap с NAME не теряет хвост PII; два custom types одинаковой формы восстанавливаются верно; token pool exhaustion → refusal, не реальное значение.

### F06. Точечные исключения и политика собственных значений — P0

**Результат:** служебные контакты/название/конкретные ложные срабатывания перестают требовать ticket, без глобального обхода.

**Архитектура:** exact canonical match + category + app/source/destination scope + reason/author/expiry. Нет regex «никогда не маскировать всё похожее». Структурное исключение возможно только для trusted typed field и отдельной категории, когда validator подтверждает формат; оно не сильнее SECRET/document deny. Exceptions immutable revision в cache context. Raw own_values/skip_system/scope overrides v2 не принимаются как policy authority. Managed effective policy — единственный источник этих настроек: legacy env `PSEUDEX_OWN_VALUES`, `PSEUDEX_PSEUDONYM_SCOPE` и skip_template defaults не наследуются. Empty managed exception list — явное отсутствие исключений, а не falsey fallback к env; strict session scope не заменяется container-wide default.

**UI/API:** из trace «создать исключение» создаёт draft, показывает какой finding снят и какие остались, обязательные позитивный leak probe и негативы. Duplicate/expired/conflicting exceptions видны. «Все типы» не default.

**Приёмка:** совпавший allow pattern не снимает секрет; exception конкретного телефона не снимает чужой телефон; change при cache hit реально меняет output; exception expiry не зависит от открытия UI.

### F07. Действия над данными и расширение секретов — P0

**Принятые уточнения:** SECRET default блокирует конкретный model request, redact включается адресно. Режим «модель видит подстановку, инструмент получает credential» реализуется отдельным scoped credential reference: настраивается сервис/purpose, поддержанные adapters работают без перечисления всех tools; новое использование через HITL (CRED-UX01). Не применять credential-specific onboarding к обычной ПДн-псевдонимизации. Default запреты ниже допускают только явно включённое владельцем разовое HITL исключение raw-key egress и temporary encrypted approval payload, не общий fail-open или plaintext logs.

**Результат:** PII остаётся пригодной агенту; credentials не сохраняются для восстановления.

**Архитектура:** policy решение до mint. `pseudonymize` использует vault/redact; `redact` удаляет/ставит фиксированное безопасное обозначение; `partial_mask` только явная политика (показ остатка — раскрытие части данных, не обещание защиты идентичности); `block` не создаёт mapping. JSON изменения выполняются по parsed leaf/typed path, не строковой замене quotes. После удаления семантически обязательного tool field вызов запрещён, а не отправлен с invalid schema.

**SECRET:** расширить библиотеку опубликованных форматов — ключи LLM/Git/cloud/payment, PEM/OpenSSH private keys, credentials в connection strings, passwords в явном KV-контексте. Curated subset внешнего каталога с license notices и негативами; не импортировать entropy heuristics wholesale. Классифицировать password context, а не любую высокую энтропию; sample placeholders/public keys остаются отрицательными примерами. New managed secrets никогда не попадают в tokens/original preview/test-result persistence. Исторические legacy mappings не удаляются silently; migration report и отдельная purge operation.

**UI/API:** category→action, список поддержанных secret mechanisms, masked reason. Reveal для SECRET отсутствует в managed. API ошибки не цитируют секрет/вход.

**Приёмка:** seed секрет отсутствует в vault/audit/control/jobs/logs/exceptions/results/backups нового managed flow. При action=block вход с PII+SECRET блокируется до upstream. При явно разрешённом redact upstream получает только очищенный envelope, без исходного секрета и возможности его восстановить; required tool field нельзя удалить — тогда block. JSON валиден после redact; обычные commit hashes/UUID/public tokens не блокируются.

### F08. Сессии, receipts и разрешённое восстановление — P0

**Принято RESTORE01:** ambiguous/unresolved substitute не угадываем; проблемный tool call не выполняем. Обычный текст может быть выдан с явно нераскрытой подстановкой и machine-readable/UI признаком incomplete restoration. Это не успех exact round-trip; residual-free также не доказательство правильной личности. Zero-code proxy onboarding versus explicit conversation identity/receipt requirements — CONNECT03 ещё обсуждается, не обещать оба без основания.

**Принято AR14:** по умолчанию подстановки scoped внутри диалога; долговременная память включается отдельной настройкой, межприложенческая стабильность не подразумевается.

**Результат:** вернуть реальные данные правильному приложению и получателю, а не любому обладателю gateway token.

**Архитектура:** namespaces/refs/receipts в vault.db; handler проверяет app, project, conversation, live auth epoch, allowed destination и token membership. Strict restore не вводит видимость из одной session в другую. `receipt` связан с successful protect pass; subsequent tool-result protect добавляет разрешённые mapping refs текущей conversation через новый receipt, не переписывает immutable historical receipt. Restoration использует recorded decoder/generator metadata, current permission проверяется отдельно. Политика новых requests не уничтожает возможность корректно обработать outstanding разрешённый response.

**UI/API:** scope conversation/project, bounded receipt TTL, errors `receipt_expired`, `restore_forbidden`, `mapping_deleted`, `unresolved_token` без value. Высокорисковые tools с residuals не исполняются по default. Reveal — отдельный management grant/reason/audit, не использование restore endpoint для поиска vault.

**Приёмка:** stolen receipt без app credential бесполезен; чужая conversation/key/destination запрещена; смена обычной policy не портит approved response, revoke запрещает; deletion не выдаёт cache value; checksum/name/address/JSON round-trip регрессии сохраняются. Expired lease поведение не меняем этим sprint; bundle-free recovery P2.

### F09. Журнал каждого решения, административный аудит, история — P0

**Результат:** ответить «кто, по какой политике, что решил и что выполнил», в том числе при cache hit и запросе без PII.

**Архитектура:** новая request_decisions, а не переиспользование events как full request archive. Фазы ingress/output/tool имеют decision_id и общий request_id/root_request_id. Admin events внутри mutation tx, reveal record до раскрытия, actor из verified auth. Значения keys/content не входят в mutation diff: secret field → `changed=true`. Неуспешный вход, отказ, промах раскрытия, удаление, активация, экспорт и чтение диагностического содержимого также создают события.

**UI/API:** новый request journal + entity drilldown; filters по app/model/category/action/reason/policy; отдельный reveal log и unified admin history. Safe export JSONL/CSV, spreadsheet formula neutralization, bounded pagination/cursor. Данные по project permissions.

**Приёмка:** каждый обслуженный request имеет decision, cache hit не дырка; число protected entities не раздуто; forging actor не меняет журнал; audit disk full блокирует mutating/disclosure и managed egress где audit required. Local append-only API не называется WORM/root-proof; для защиты от root нужен внешний anchor/SIEM P2.

### F10. Выходные проверки и честный streaming — P1

**Принято AR16:** если включённой обязательной проверке нужен полный ответ, буферизуем, проверяем, затем выдаём; UI предупреждает о задержке/отключении streaming. Если все выбранные проверки доказанно поддерживают потоковый режим, сохраняем streaming. Не выключаем required check ради скорости и не выбираем universal always-buffer.

**Результат:** обнаружить новые секреты/custom forbidden data и нарушения формата в ответе, не замаскировать автоматически разрешённое восстановление.

**Архитектура:** output.py две стадии: raw provider response до detok (recognise known minted substitutes → provenance, не double-mask), затем restoration + recipient checks. Built-in newly generated PII action выбирается политикой; предполагаемые fake tokens модели не считаться автоматически нашими. Exact known tokens, typed spans, schema/tool rules — provenance-aware. Post-detok обязательные ограничения проверяют destination/type/operation, а не «любой телефон запрещён».

**Streaming:** когда требуется whole-context output check, default полный bounded buffer, checks и только затем выдача. Tool arguments всегда buffered JSON-aware. Fast streaming допускается только если все обязательные checks способны доказуемо проверять prefix с описанной границей; иначе validation отвергает конфигурацию. В первой поставке safe buffered mode — нормативный для output scanning, existing detok-only streaming остаётся отдельным явно limited mode. Размер/time превышен → отказ. Нельзя выпускать unsafe prefix, потом объявлять его заблокированным. Stream identity = receipt + stream_id + choice + field; sequence проверяется, chunks перепутанные/повторённые не конкатенируются. В failed stream tail не flush в public response автоматически.

**UI/API:** mode/latency warning, preflight capability matrix, distinct `stream_blocked`/`provider_failed` SSE outcomes. `finish_reason` и error event не имитируют успешный [DONE]. Sidecar v2 накопленные output/arguments через finish; SDK удерживает пока нет delivery allow. Общую токсичность/phishing reputation/general factuality P2.

**Приёмка:** секрет split на каждом offset не выходит в wire; n>1 не смешивается; midstream outage не выдаёт held unsafe tail; detok ФИО разрешённому CRM проходит, external HTTP recipient запрещён; новые ПДн не смешиваются с уже выданной подстановкой.

### F11. Подключение защищаемых API без маршрутизатора моделей — P1

**Принято ROUTE01/02 уточнением владельца:** Pseudex — security proxy/sidecar для OpenAI/Anthropic-compatible traffic, не LiteLLM. Выбор модели, cost routing, балансировка и provider fallback не входят в нашу ответственность. Модель и её параметры выбирает вызывающая система/существующий gateway; мы защищаем поддержанный protocol envelope.

**Результат:** несколько настроенных исходных API URL могут защищаться одним инстансом. Forward к заранее связанному upstream — transport forwarding, не автоматический model routing. Upstream может быть провайдером, локальным совместимым endpoint или существующим LiteLLM/корпоративным gateway.

**Принято CONNECT01/02:** мастер «Агент или сервис» → исходный base URL + поддержанный OpenAI/Anthropic protocol + policy + provider credential → готовые base_url/api_key Pseudex и snippet. Исходный API credential хранится локально encrypted/approved secret ref; клиент получает отдельный отзываемый Pseudex access key. Тот же workflow через management API. Endpoint shape может быть общим, binding определяется ключом; отдельный URL path на каждого service не обязателен. Настройки upstream из UI/API вместо env/restart на каждое подключение. Client один раз задаёт исходное назначение, не угадываем его из model name.

**Архитектура:** registered API binding id, owner/service, protocol/version capabilities, fixed upstream_base_url, trust class, credentials mode/reference, enabled. `model` в поддержанном envelope передаётся без выбора/замены с нашей стороны; обязательные category/destination security constraints могут запретить передачу. Unknown routes из caller URL/headers не превращают инстанс в open relay. Literal URL alias не является credential. Выбран Pseudex access key → service/binding; путь URL не authority. Provider credential не передаётся модели и не раскрывается клиенту через management read/export. Новый provider-key passthrough режим не выбран; legacy не должен обходить managed isolation.

**Sidecar:** host вызывает наш security API и сам владеет provider call/routing/retries. Выдаём protection verdict/constraints/receipt, не выбираем его provider. Фактическое соблюдение destination constraints — проверяемый интеграционный контракт host, не тайно построенный сетевой router.

**Egress:** TLS/CA validation, fixed approved endpoints, connection-time DNS/redirect rules, metadata/link-local запреты и explicit internal destinations. Existing upstream URL не даёт произвольный network access. Ни error защиты, ни provider failure не переключают модель; caller получает typed failure. Security решение «только локальное назначение» является ограничением/отказом текущему external request, не автоматическим reroute; выбор нового назначения делает host.

**Приёмка:** два API bindings одного инстанса правильно forwards исходную model identity и поддержанные параметры к своим endpoints; provider outage не вызывает другой URL/модель; alias/redirect не обходят policy; unsupported protocol fields явно обрабатываются по capability contract. Нет каталога доступных моделей, который клиент обязан постоянно синхронизировать ради обычного подключения.

### F12. Лимиты, admission и учёт использования — P1

**Результат:** ограничить ресурсные риски по приложению, не смешивая LLM usage с оплатой Pseudex.

**Архитектура:** size/type/depth/tool-schema limits до expensive detection; shared local admission counters в audit.db для project/app token bucket + concurrency leases с bounded expiry, короткие tx без удержания во время inference. Request/response timeout, max queued, streaming buffer и job budgets. Per-worker counters недостаточны при SO_REUSEPORT. Решение limits на demand проходит и при mask-cache hit.

**Предлагаемые defaults:** ingress 1 MiB, 256 messages, JSON nesting 32, output buffer 1 MiB, request processing 30 s без ожидания provider; provider timeout отдельно route-specific. Hard maximum/override валидируется ресурсами. Эти цифры не измеренные SLA. Provider input/output tokens nullable, reported от provider/host с provenance, estimated явно отдельно. Стоимость неизвестна без pricing metadata/version; никаких нулей вместо unavailable.

**Billing:** сохраняем existing successful masking call, не списываем отдельно output/trace/reveal/dry-run. Rejected/failed protect/masking не billed; отказ provider/output/finalize после уже успешного protect не отменяет его начисление. Proxy, как сейчас, считает запрос после успешного masking до upstream, поэтому provider failure не означает бесплатный masking. Статусы protection и downstream delivery в аналитике разделяются. Request attempts, processed, policy blocks, billable и protected values — разные counters. Не обещаем global token budget без usage от host/provider. Rate retry `Retry-After`, ограниченный timestamp skew.

**Приёмка:** burst на N workers не умножает разрешённый RPS на N; TTL lease после killed worker освобождает concurrency; invalid payload не bill; большой rejected body не удерживается целиком в RAM; provider usage missing показывается неизвестным.

### F13. Explain, настоящая песочница и batch CSV/JSONL — P1

**Результат:** понять причину и проверить реальный круг без загрязнения production.

**Архитектура:** testsurface использует тот же Detector/envelope/policy/redact под active leased assets, но отдельный namespace/database sandbox + изолированный cache и test audit. Explain read-only, никаких minted mappings/production audit/billing. Full test run делает mask→restore текста и JSON arguments; панель восстановленного значения — реальный результат, не копия ввода. Provider по default не зовётся. Synthetic tool transformations заданы явно; live-model test — отдельное opt-in с budget, не автоматическое действие этой спеки.

**Batch:** streaming parser не spools исходный файл на plaintext диск. Строка обрабатывается в bounded RAM, known SECRET не сохраняется; default retained results не содержат исходных строк. Для resumable input требуется explicit consent, отдельное право/TTL и encrypted row chunks в jobs.db после secret check; known-secret строки только ephemeral evaluation, без persistence исходника. Обнаружение не гарантирует отсутствие неизвестных секретов: consent предупреждает о новой sensitive surface. При прерванной upload без сохранённого input состояние interrupted, не фиктивное resume. Сначала CSV/JSONL UTF-8, text column и RFC-consistent CSV handling; no DOCX/PDF/OCR/ZIP extraction. Seed limits 20 MiB/file, 100k rows, 64 KiB/row, 1 active batch/project; original promise 200 MiB из mock отклонено до измерения. Job progress/cancel/restart/TTL, row errors, mode analyze versus full test; no one giant transaction/async background task tied to browser tab. Safe results export без исходного текста default.

**Trace:** candidates→gates→overlap→exceptions→action с rule IDs, offsets raw input и evidence. На свои raw тексты developer grant; reveal другой traffic требует отдельное право. Entire source текст не попадает в лог. CSV injection neutralization.

**Приёмка:** /explain не меняет vault/counters; full run можно обнаружить намеренно сломанным restorer; batch restart resume не смешивает namespaces, cancel перестаёт consuming worker time; crafted CSV/JSONL/huge line/file name не XSS/path traversal/plaintext leak. Пользователю явно видны input retention и limits.

### F14. Клиентская регрессия, сравнение и shadow — P1

**Принято AR19:** по умолчанию полные исходные запросы/ответы не хранятся. Safe journal отдельно; diagnostics capture — explicit режим по агенту/сервису с encryption/access/retention. Vault и pending HITL payload имеют собственные согласованные lifecycle. Historical replay без разрешённого retained input не обещать.

**Результат:** перед применением увидеть, что добавится/перестанет защищаться и не сломается ли восстановление.

**Архитектура:** encrypted versioned test_cases в jobs.db с expected spans/categories/action/round-trip и approved negatives, suite revisions. Synthetic secret tests хранят recipe/seed, а не действующий credential; пользовательский текст с известным настоящим секретом не сохраняется в suite. У тестового материала отдельный срок хранения/explicit expires_at: default real cases 30d, synthetic до удаления, разрешённое продление до 180d журналируется. Run manifest engine/bundle/policy/dictionary versions/input suite hash, comparable basis. Main snapshot и draft оцениваются отдельно на одном raw case, не mask(mask(x)), test namespaces разные. Findings/transform/mapping correctness сравниваются по каноническим ожиданиям, не случайным fake strings. Critical cases обязательны перед weakening activation, green test stamp инвалидируется изменением draft/catalog.

**Принято RULE-observe-mode:** наблюдение нового правила опционально, active защита не ослабляется; результат не включает автоматическое enforcement. Нет обязательного времени shadow для каждого нового rule.

**Shadow:** optional additional draft analysis на raw managed input до release; действующая active policy не ослабляется и новое правило не создаёт production mappings. Separate limiter/budget, timeouts recorded `not_evaluated`, не результат «новая policy пропустила». Никакого shadow-only вместо обещанной enforced защиты. Raw shadow content не сохраняется default.

**Historical replay:** только retained explicit test cases/opt-in diagnostic sample, не reconstruction оригинала из preview. Raw capture off default, encrypted, отдельный grant, purpose, TTL 24h/max 7d, не secrets — automatic secret field removal либо отказ capture. Невозможно гарантировать отсутствие всех undiscovered secrets; capture явно увеличивает доверенную поверхность, это не анонимные данные. Не включать его для реализации графика.

**Приёмка:** negative-only/no comparable round-trip не получает full pass; stamped suite нельзя использовать для другого draft; aborted comparison виден; shadow saturation не останавливает primary; нельзя replay erased data или выдумать FP/FN из счетчиков.

### F15. Retention, безопасное удаление и управление vault — P1

**Принято AR18:** default автоочистка с учётом активной разрешённой работы и настраиваемого периода восстановления после неактивности; long-term режим отдельно. Конкретные численные TTL ниже остаются предложениями до отдельного ответа, а audit retention не следует автоматически из срока mapping.

**Результат:** отдельные сроки для соответствий, событий, диагностического содержимого и тестов с понятными последствиями.

**Архитектура:** refs/sessions/receipts определяют lifetime mapping; session close и idle/absolute deadlines. Housekeeping удаляет только rows без живых required refs, блокирует новое использование истекшего namespace. Renewal не продлевает абсолютный срок; project-scope долговременной памяти explicit без TTL default при миграции legacy. CAS retention epoch fencing: перед раскрытием/cache release проверяется актуальный deletion epoch. В delete tx tombstone+refs+namespace epoch, после этого никакого восстановления; gc batches удаляют indices/original_form/custom aliases/carries и связанные cached outputs. Удаление last ref не удаляет mapping другого живого session.

**Настройки:** для новых managed session idle 24h, absolute 7d (proposal); decision events 30d; administrative/reveal audit 180d; jobs/results 24h; diagnostic capture off/24h; real test cases 30d/explicit expires_at, synthetic cases до явного удаления; оба с отдельным quota. Cumulative billing/install identity не очистить retention job. Admin/reveal retention нельзя снизить молча без reason/permission. Точная long-term legality/customer policy — вне нашего автоматического решения.

**Удаление:** preview plan показывает counts/live refs/affected apps/receipts, confirm другой nonce bound plan/version, execution progress, audit. Bulk purge queued requests cancels/fences; no browser raw SQL. Ротация/physical compaction через supervised maintenance plan + existing CLI/roles, не выдавать UI shell. Срок логического запрета и физического удаления отдельные статусы; SSD/RAM/backup secure erasure не обещается.

**Backups:** default configuration-only и audit snapshots отдельно; session mappings исключены из долговременного backup. Existing full-volume backups не становятся безопасными автоматически: показать inventory/procedure/legacy limitation. Deletion ledger проверяется при восстановлении и replay tombstones выполняется до readiness. **Источник актуальности должен сохраняться независимо от восстанавливаемого snapshot:** authoritative deletion generation/digest и полный журнал либо independently retained customer checkpoint/journal (отдельный approved mount, не та же архивная копия тома). Поддерживаемый ops adapter фиксирует новый checkpoint до статуса deletion completed; конфигурация места хранения только host/CLI, не arbitrary browser path/URL. Ledger внутри backup, даже корректный и подписанный, сам по себе не доказывает, что после backup не было новых удалений. Отсутствующая или непроверяемая freshness, в том числе stale-but-valid ledger, означает quarantined not-ready restore, не silent revival. Независимый journal тоже входит в key rotation/backup inventory/restore procedure; без такого источника не заявляем автоматический tombstone-safe restore. Не гарантировать удаление копий вне контроля клиента.

**Линеаризация выдачи/удаления:** право выдачи не реализуется схемой «прочитать epoch → позже вернуть bytes». `disclosure_begin` атомарно проверяет mapping/receipt/deletion epoch и регистрирует ограниченный delivery permit. Delete сначала фиксирует fence (новые permits запрещены), затем отменяет/дожидается ранее начатых незавершённых выдач; пока они не завершены, UI показывает `deleting/draining`, не completed. Completed означает, что ранее допущенные managed delivery operations закончены/отменены и новые запрещены. Уже переданные transport bytes не отзываются; граница disclosure — зарегистрированное начало, а не обещание мгновенно остановить произвольную клиентскую сеть. Release hooks/cache/stream/reveal обязаны использовать этот один lifecycle. Auth/destination revoke применяет аналогичный fence к новым permissions; операции, уже начавшие внешний side effect, нельзя объявлять автоматически отменёнными.

**Приёмка:** expired token не проходит cached restore; очистка не теряет live mapping; все aliases удалены. Тест останавливает worker между проверкой и началом выдачи, выполняет delete на другом worker и проверяет отказ нового permit; для уже начатой выдачи completed не появляется до cancel/drain. WAL/snapshots/results в проверке retention boundary; receipt status `deleted/expired`, не fake success. Поиск raw value только reveal-level privilege, запрос не логируется.

### F16. Аналитика качества, трафика, SLO и дрейфа — P1

**Результат:** технический лидер видит нагрузку, подтверждённые дефекты и изменения после policy update без выдуманных процентов.

**Архитектура:** shared stage_metrics/decisions/time buckets, bounded histograms и aggregate series; profiling current process нельзя назвать всем cluster. Dimensions только registered app/category/destination/env/revision; нет token/name/raw text labels Prometheus. FP/FN только annotated testset/sample/feedback, metrics имеют denominator, sample size, period и provenance. Production residual_count = технический сигнал, не exact restore success. Task success — парный agent benchmark, не счетчик green 200.

**Drift:** сравнивать category/action/miss/reveal distributions и known custom-shape unmatched counts; low sample → insufficient_data. Повторяющиеся candidate shapes с HMAC bucket и без raw значений; новый dictionary candidate только предложение. «Числовая строка не совпала» не значит PII miss. Настройка baseline window/min count/threshold и suppressed alerts versioned; ML auto-discovery/automatic repair — P2.

**UI/API:** p50/p95/p99, TTFT, added gateway latency отдельно provider time, per-stage cost, queue rejection/error budget; model usage actual/estimated/unavailable. Quality chart показывает «подтверждено на N примерах»; после policy update marker. Reports со scope, timeframe, versions, settings и limitations, локальные print/CSV/JSON; не сертификат соответствия закону.

**Приёмка:** fresh install не рисует 100%; histogram aggregate корректен на N workers; small sample не объявляет drift; FP label создаётся только annotation; matching CSV/print/UI цифры из одного DTO.

### F17. SIEM, DLP, уведомления и bounded интеграции — P1

**Принято ENTERPRISE01-depth:** проверенные стандартные interfaces, а не все vendor products. OIDC identity F02, standard event exports и документированный REST DLP contract с UI test connection; proprietary adapters отдельно. Приоритет после основных пользовательских сценариев. **OFFLINE01:** полноценный air-gap engine отдельным следующим объёмом, не скрытая часть этих connectors.

**Результат:** штатные универсальные интерфейсы вместо отдельных разработок для каждого заказчика.

**SIEM:** JSON HTTPS push как базовый sink, JSONL export и CEF/syslog-TLS formatter/transport. Outbox event payload already sanitized, tx с decision/admin mutation в его store. Housekeeping delivers at-least-once с event_id dedup, bounded retries/backoff, timeout, poison-event quarantine, queue byte/age caps. Best-effort overflow может drop только explicitly low severity с durable drop summary; mandatory reliable mode backpressure fail-closed, не бесконечный диск. Audit storage failure и sink outage — разные состояния.

**DLP:** fixed allowlisted REST adapter contract input document parts/context/request_id and output categories/action/spans/offset_basis. Response validates size, known decision/schema/signature/auth, no returned scripts/URLs. required timeout/unavailable/malformed/offset mismatch → deny; optional unknown→`not_evaluated`, baseline продолжает защищать. DLP может классифицировать whole document, не принуждать gateway искать fictitious spans. Защищаемый текст отправляется только явно разрешённому сервису в контуре клиента; provenance поля доступа verified. ICAP/vendor adapters P2.

**Notifications:** local/customer-approved webhook, SMTP STARTTLS/TLS с secret refs; same egress rules, initial sink delivery test без сырого текста; ack/suppression не изменение политики. Любая внешняя отправка требует явного выбора, не скрытый SaaS Slack default. Public cert CA verification, no auth token in logs.

**UI/API:** endpoint registration (role), required/optional, timeout/queue policy, test health, queue age/last successful delivery/errors/sanitized sample. No user-provided arbitrary URL in each request.

**Приёмка:** SIEM down затем up доставляет events с возможными duplicate IDs и без потерь mandatory; queue cap bounded; malformed DLP never allow; DNS rebinding/redirect/secret-in-URL не обходят network policy; sink query не экспортирует raw receipts/tokens/custom lists.

### F18. Python SDK, LiteLLM и агентные adapters — P1

**Результат:** разработчик подключает защиту правильно без написания собственного insecure round-trip.

**Архитектура:** thin HTTP client к v2, sync/async, structured errors, timeout, cancellation, receipt context, managed destination assertions. Нет local detector и leased assets в pip package. SDK копирует envelope/state, не вставляет real tool arguments в persistent masked agent state. Restored args только временная копия на execution boundary; tool result маскируется до следующего LLM/context/checkpoint. LangChain v1 `create_agent` middleware, direct LangGraph wrappers model/tool nodes — отдельные tested shapes; mock `builder.compile(middleware=...)` не выдавать за реальный API.

**Adapters:** OpenAI-compatible proxy guide, raw HTTP, LiteLLM callback ingress/egress with root correlation, explicit LangChain/LangGraph round-trip adapter и generic tool wrapper. `authorize_tool` минимально проверяет registered tool/destination/schema/receipt; arbitrary external tool execution не становится нашей responsibility. Depth/count/time budgets для интегрированного tool loop; полноценные MCP transport proxy/A2A delegated credentials P2.

**UI:** генератор snippets из capability registry + selected app/route/API contract, secrets placeholders, never print credentials из engine. «Проверка интеграции» требует portable fixture runner на стороне приложения; selfcheck только engine не доказывает host failure behavior. Probe result содержит integration version/timestamp/test IDs.

**Приёмка:** захваченный model request/checkpoint не содержит restored original после tool execution; host 503 → LLM не вызывается; n>1/chunk/tool buffers contract проверен; callback с repeated transcript не создает re-mask; versions пакетов pin, real library APIs в examples.

### F19. Профили, каталог типов и поддержанные отраслевые шаблоны — P1

**Результат:** видеть, что умеет установленный движок, выбирать осмысленный набор правил без фальшивого «26 типов».

**Архитектура:** runtime capability registry: builtin type IDs, mechanisms, available actions, reversibility, score semantics, tests/dataset coverage, bundle revision, entitlement availability. Count вычисляется из registry; mapped types NAME/LOC могут иметь human-facing PERSON/ADDRESS labels без двойного счёта. Profile = versioned policy/template набор поверх runtime capabilities; entitlement = доступность в lease/пакете, не разрешение конкретной передачи. Живой новый proprietary catalog включается только leased bundle, не встроенными customer assets.

**Scope:** общие presets «поддержка/ритейл», «документы», «разработка/секреты», шаблоны custom лицевой счёт/номер полиса/номер дела. Новые детерминированные IMEI/IBAN/MAC — добавлять как небольшой отдельно измеренный набор с checksums/context/FP negatives и round-trip. IMSI без контекста не 15-digit regex everywhere. БИК/SWIFT/организация не автоматически ПДн — category/confidentiality policy. Зарплата, долг, диагноз как смысл — локальный classifier P2; medicine отдельный профиль не обещаем.

**UI/API:** types inventory/availability/mandatory/score `not_applicable`; import template draft; missing entitlement не молчаливое отключение advertised защиты. При expiry действуют уже существующие правила lease refusal, не «профиль fallback пустой».

**Приёмка:** число типов равно каталогу; preset не включает отсутствующий detector; новые types проходят независимый holdout + overmask + production-path round-trip, fallback «mask any 15 digits» запрещён; переименование отображения не меняет stored token identity.

### F20. Обновлённая локальная админка и рабочие процессы — P1

**Результат:** функциональность двух источников согласована с одним backend, доступом и состояниями.

**Архитектура:** сохранить vendored Preact+htm/no-CDN; разделить монолит current app.js на экранные модули в shipped static. management API engine owns decisions/permissions; UI server forward только exact method+route schemas с typed path IDs, bounds и permission check, не wildcard relay. Browser не знает admin/gateway/upstream secret. Идентичность forward — краткоживущий internal assertion через local trust credential, проверенный management router, не actor из страницы. Нормативный payload: issuer/audience, principal_id, admin_session_id, auth_epoch, request_id/nonce, method, canonical route/query, project, body digest и expiry. Engine игнорирует asserted role labels, проверяет **live** session/grants/epoch в control.db и exact request binding, rejects replay/mismatch. Trust credential аутентифицирует UI bridge, но не даёт самостоятельной admin authority без named session. Logout/revoke между issuance и forwarding должен дать отказ, а не окно до assertion expiry. Прямой management API использует named principal credential и ту же live permission evaluation.

**Навигация:** «Обзор», «Защита» (policies/types/rules/dictionaries/profiles), «События» (requests/entities/reveals/history/incidents), «Проверка» (sandbox/batch/trace/suites/compare), «Агенты и сервисы» (плоские карточки callers, политики, направления и coverage; внутренние scope IDs не обязательная UI-иерархия), «Система» (access/integrations/vault/versions/licence/diagnostics). На малом install скрываем advanced UI capabilities, не удаляем их из API. Сохраняем отдельные engine versions и policy versions.

**UX:** empty/loading/error/degraded/stale/unknown/unsupported; keyboard focus и screen reader labels; density readable, не tiny mono для основного текста; confirmation destructive changes; reveal временно, no persistence/clipboard auto-copy, сброс на navigate/logout/expiry. Global search scope-aware, bounded, без raw value query по умолчанию. Incident lifecycle `open→triaged→draft_fix→verified→closed`, closing требует ссылки на evidence/run, без auto-policy change. Source annotations не автоматически verified incident.

**Приёмка:** все кнопки обращаются к реальным API или явно unavailable; никаких toast «успешно» до ответа. Real-browser tests включая XSS из traffic, CSP, two roles/project isolation, stale cache/activation/dead engine. Refresh/back восстановление безопасно, reveal не остаётся в history; no requests to CDN/vendor from UI.

### F21. Jobs, эксплуатация, промышленная упаковка и readiness — P0 jobs, P1 ops

**Результат:** UI и фоновые операции не ухудшают обслуживание; новые stores не выпадают из обновлений и восстановления.

**Jobs:** один supervised housekeeping role из существующего binary; state/material в jobs.db, bounded queue, job claim через CAS lease/epoch, resume checkpoints per batch, idempotent output fragments. Housekeeping crash переводит фоновые возможности в degraded, не немедленно убивает engine; entrypoint разделяет critical engine workers и restart-limited optional role, а shutdown останавливает обе группы. Heavy detection delegates в bounded engine test endpoints либо отдельный explicitly preflight-budgeted analysis worker role с собственным lease; не multiprocessing/fork frozen binary и не второй неожиданный Natasha model внутри UI. Analysis saturation не занимает весь primary limiter; resource cap и documented trade-off на одном core.

**Operations:** fixed maintenance plans вместо UI shell. Doctor/status включает per-store schema, key source, durable epochs, deployments, outbox/jobs age, raw capture state, vault refs/TTL, actual process readiness. `/health` liveness сохраняется; новый `/ready` проверяет active policy compile, license serving и stores. UI down не отключает active policy; housekeeping down прекращает jobs/delivery, primary отдельно оценивает mandatory outbox capacity и TTL на чтении (GC не граница безопасности).

**Packaging:** новые CONTROL_STORE и JOBS_STORE labels в vault_key/sqlite_setup/schema.registry; probe/migrate/rekey/decrypt/volume_state/backup/restore/doctor в обоих images. Повысить schema audit и vault под новым minor: старый probe иначе проигнорирует новый control.db и ошибочно разрешит downgrade. Не править lock 0.3 max9/1/1. Release-As выбирается owner по release contract; version source прежний. Source+compiled parity, RE2/OIDC зависимость и SBOM/licenses pinned; no customer docs/inputs in release image; capability surface gates on compiled image.

**Приёмка:** source/compiled rollout/jobs/reveal одинаковы; crash halfway rekey reports per store; no space migration ничего не изменяет; старый образ refuses untouched; restore quarantines stale tombstone snapshots; no root/docker socket/secret in argv; health stale lease не заставляет restart storm. UI не запускает docker upgrade/rekey сама.

### F22. Базовая безопасность LLM, RAG-контекста и инструментов — P1

**Результат:** ограничить конкретные угрозы, характерные для ИИ, не продавать набор regex как полную защиту от prompt injection.

**Архитектура:** proposed `prototype/pseudex/agentguard.py`, registry tools в control.db (`tool_id,server_id,version,schema_digest,description_digest,owner,trust,allowed_operations`). При изменении approved schema/description повторная регистрация; одинаковое human-readable имя разных servers не одна identity. `tool_id` и digest проверяются до LLM disclosure и на execution wrapper. No automatic trust from tool description. Input normal representation carries source type/document ref/chunk ref/classification/verified access assertion; RAG text и tool descriptions/results проходят тот же обязательный pipeline. Пользовательский source metadata без delegated grant — только label. Источник с required access proof без подтверждения исключается/блокируется до модели; gateway не читает ACL отсутствующей базы знаний сам.

**Injection signatures:** ограниченный versioned набор известных direct/indirect instruction override/exfiltration signatures RU/EN как механизм `injection_signature`, отдельно от PII. По default monitor на этапе калибровки, не отключающий PII/secret enforcement; explicit block допускается после согласованного positive/benign corpus. Evidence это совпавшая сигнатура, не вероятность злого умысла. Zero hits не означает безопасный prompt. Не добавлять instructions в customer system prompt автоматически и не менять нормализацию offsets. Local classifier REST connector может выдавать typed finding при явно настроенном сервисе и его test stamp; **наличие connector не считается shipped semantic detector**. Собственная semantic модель, multilingual jailbreak protection, intent/goal analyser — P2.

**Tool guard:** registered tool/destination/operation + schema and field allowlists + per-run steps/deadline. Proxy блокирует forbidden proposed call, SDK wrapper также проверяет непосредственно перед исполнением; restoration capabilities только на разрешённые paths, никогда credentials. Отсутствие wrapper = `execution_not_integrated` в coverage, не enforced. SSRF наших собственных integrations/proxy закрывает F11/F17; сетевые обращения произвольного remote tool требуют его собственный egress/sandbox, не решаются фильтром имени функции.

**UI/API:** «Инструменты и источники» как подраздел «Приложений», approved digests/изменения/полномочия/coverage, signature evidence/monitor/block, attach run limits. `/v2/tools/authorize` возвращает opaque pending permit bound to normalized args digest, receipt, operation, destination, tool registry generation, app/auth/deletion epochs и short deadline. Binding хранит отдельно digest protected arguments и digest **recipient-ready arguments после проверенного restore**; SDK не сравнивает fake JSON с real JSON как будто это один payload. Consume принимает exact argument payload/его проверяемую canonical representation, а не считает произвольный caller checksum доказательством; engine проверяет recipe/token membership/field constraints и ожидаемый recipient-ready digest без persistence исходных real args. Непосредственно перед execution wrapper обязан online вызвать `/v2/tools/consume`: engine повторно проверяет live app/tool/destination grants и receipt/mapping lifecycle; один control.db transaction переводит permit issued→consumed и списывает shared run step budget. Replay/expiry/revoke/digest mismatch/exhausted budget → отказ, handler не вызывается. `tool_permits` и `run_budgets` живут вместе в control.db; failure после consume может потратить step без side effect, это безопаснее повторного исполнения. Consume — нормативная точка допуска execution attempt, не distributed transaction с внешним инструментом; уже начатый внешний side effect нельзя отозвать и exactly-once не обещается. Wrapper не держит разрешение в очереди между consume и вызовом и использует bounded attempt deadline. Request approval workflow, MCP transport/A2A delegation — P2.

**Приёмка:** разрешённый tool ID с подменённой description/schema требует review; namesake server не shadow approved tool; malformed/forbidden args и превышение steps не исполняют side effect; RAG no access proof не reaches model; quotes о prompt injection в benign документации не получают безусловный block; deliberately bypassed signature обнаруживает limits/enforcement tests, а не зелёный «all attacks neutralized».

### F23. AI-разработка: exact data restoration на границе исполнения — P1, завершающий T12

**Результат:** AI-кодер работает с реальными workspace данными, пока модель получает protected view. Read/search, validated Bash subset, narrow literal patch и registered credential operations используют общее ядро. Рынок coding agents расширяет аудиторию, но его размер этим документом не измерен.

**Архитектура:** K10 execution-aware adapter, exact-byte mapping domain/provenance, structured execution plan, approved executable/argv grammar, workspace/process/network sandbox и live permission consume. Для coding literals/paths не применять canonical PII morphology. Известные credentials не возвращаются в LLM-generated script: доступ только narrowly registered операции через отдельный secret broker.

**Точка интеграции:** model boundary + local execution boundary. Первая кандидатная интеграция — pinned Claude Code/Anthropic protocol, проверяемая SP07; один HTTP shim не подтверждает контроль local Bash/Read/Edit/checkpoints. Другие harness/OS не считаются supported без своих gates. Неподдержанные signed/opaque content и shell contexts не преобразуются вслепую.

**UI/API:** приложение типа coding, approved workspaces/ops/egress/resource/retention settings, protected trace, integration probe и честная карта coverage в существующей админке. Не универсальная remote-shell кнопка в management API. Proposed coding DTO/adapter paths и полный lifecycle в [специализированной спецификации](<docs/tz-ai-coding-track.md>).

**Порядок/приёмка:** W28–W35 после W27/C4; AC01–AC12 проверяют exact argv/files, no secret/model leak, sandbox/races/permit replay, safe patch и полезность paired задачи. W35 повторяет общие CP на новой сборке; весь спринт заканчивается C5. Arbitrary shell/eval/embedded languages restoration, all IDE support и automatic semantics preservation не входят в узкую первую поставку.

## 5. API-контракт и интеграционные границы

### 5.1 Новый data-plane v2 (proposed)

| Метод/путь | Назначение | Credential/ограничение |
|---|---|---|
| POST /v2/protect | request envelope → decision + protected envelope + receipt | app key, project from auth, explicit conversation/destination |
| POST /v2/finalize | whole response → output checks + authorised restore + delivery | app key + receipt, actual destination verified against registered binding |
| POST /v2/finalize/arguments | accumulated JSON arguments → checked permitted args | registered tool/schema/destination + receipt |
| POST /v2/streams | allocate bounded stream context | receipt+app, choice/field mode, no arbitrary namespace |
| POST /v2/streams/{id}/chunks | bounded buffered append, explicit sequence | same app/session; no unsafe prefix response |
| POST /v2/streams/{id}/finish | run checks/restore/release or deny | complete schema/mode/choice validation |
| DELETE /v2/streams/{id} | abort and discard sensitive buffers | owner app; audit counts |
| POST /v2/tools/authorize | bounded schema/tool/destination/operation check, pending permit | app+receipt; does not itself execute tool |
| POST /v2/tools/consume | live recheck + one-use permit/run-budget consumption | app+permit+exact args digest; execution attempt разрешается только здесь |
| GET /ready | ready to serve declared managed contract | no content/credential disclosure |

Existing /mask,/unmask*,/spans и /v1/chat/completions остаются compatibility API. Managed OpenAI proxy uses same core, registers app/route headers (`X-Pseudex-Conversation`, registered route alias); служебные поля не уходят upstream. Не меняем тело стандартного OpenAI response произвольными полями; request/decision metadata в safe headers и ledger, error envelope document compatible.

`/protect` response example:

```json
{
  "request_id": "req_...",
  "decision_id": "dec_...",
  "action": "transform",
  "policy": {"revision": "pr_17", "hash": "sha256:..."},
  "checks": [{"id": "builtin_pii", "status": "completed"}, {"id": "secrets", "status": "completed"}],
  "allowed_destinations": ["external-approved"],
  "receipt": "opaque-secret-handle",
  "envelope": {"messages": [], "tools": []}
}
```

Denial не содержит исходный envelope и receipt. Status codes: 400 malformed, 401 invalid credential, 403 forbidden/policy_denied, 409 state/sequence/conflict, 410 expired/deleted receipt, 413 too large, 415 unsupported content, 422 invalid policy/schema/tool args, 429 admission, 502 provider failure, 503 required check/store/policy unavailable. Error: stable code/request_id/decision_id/reason IDs, никакого raw value. Не превратить engine bug в 403 business denial.

V2 не принимает caller-owned policy JSON/custom regex/own_values для каждого запроса: references только approved assignments. Subject claims отдельно verified auth, metadata labels не критерий trusted permissions. host `/finalize` подтверждает destination только как authenticated app assertion; сетевой маршрут host находится вне engine enforcement и должен быть проверен integration suite.

### 5.2 Декодирование JSON и две формы результата (нормативно)

**JSON нельзя проверять только как сериализованную строку.** На ingress replayed tool arguments, declared JSON tool results и на output `function.arguments`: bounded parse → decoded string leaves и data object keys → detect/custom/secret checks → typed transformation → JSON-safe serialize. Чувствительные значения в decoded keys также нельзя пропустить: для фиксированных property names/contract-bound keys required transform без безопасного поддержанного rewrite означает deny, не переименование поля, ломающее tool schema. Unicode/quote/backslash escapes не должны скрывать PII/SECRET от recognizer. Malformed JSON, duplicate keys, NaN/Infinity, invalid surrogates, exceeded depth и несоответствие registered tool schema в managed tool path означают отказ, не raw pass-through. Не пытаться JSON-parse любой prose по первой `{`: JSON форматы определяются поддержанным envelope/schema; general encoded prose/base64 de-obfuscation не заявляется полной защитой.

Finding location для JSON: `json_pointer` плюс start/end **в декодированном leaf**, а не ошибочные offsets во всей encoded wire строке. Если показываем исходное serialized представление, нужен явный decode source map; otherwise UI отображает decoded leaf и честно подписывает basis. `/spans` для plain text сохраняет raw 1:1 offsets. Валидация/детекция ключей и схем должна сохранять API semantics, нельзя изменить enum/property name ради generic redaction. Supported inventory: message text content/parts, replayed assistant tool_calls arguments, declared tool-result JSON/text, tool description и schema text annotations (`description/title/examples`) под известными branches. Schema contract values `enum/const/default` также **проверяются**, но не переписываются, когда это меняет tool contract: обязательная sensitive transform без implemented safe paired rewrite означает deny либо явно разрешённый доверенный route. Не оставлять эти значения silently exempt; новые provider extension fields получают declared support или unsupported outcome.

V2 finalize имеет **два разных результата**, не один восстановленный объект, который SDK случайно сохранит:

```json
{
  "request_id": "req_...",
  "decision_id": "dec_output_...",
  "protected_model_response": {"choices": []},
  "delivery_response": {"choices": []},
  "delivery": {"recipient": "crm-approved", "allowed": true},
  "next_receipt": "opaque-session-lineage-handle"
}
```

`protected_model_response` уже прошёл output проверки и необходимые data transforms; известные substitutes остаются substitutes, новые protected PII получают разрешённую подстановку, secrets удалены/заблокированы. Новые mapping refs фиксируются через transaction-aware output receipt; recognition/type/render basis и session lineage включают их. Именно этот результат допустим для agent model-state/checkpoint, не произвольный raw provider response. Следующее назначение модели всё равно проходит ingress policy заново.

`delivery_response` — отдельная ephemeral copy, с разрешённым восстановлением для конкретного recipient/field/operation. SDK никогда не добавляет её в model state, graph reducers или payload traces. При deny нет delivery_response и real values; возвращённое failure state не считается успешной delivery. Для tool arguments такой же split (`protected_arguments`, `delivery_arguments`), причём исполняется только разрешённая copy. Buffered streaming finish возвращает соответствующие две проекции, public OpenAI proxy отдаёт лишь recipient delivery в стандартном response shape. Legacy shape не меняется silently.

Framework tracing/checkpointing может записать raw input **до** наших middleware и restored execution args **внутри** traced handler. Поставленный adapter должен отключать либо доказанно sanitise такие callback/trace paths и документировать tested versions. Произвольная пользовательская instrumentation вне adapter — explicit boundary, не автоматическая гарантия SDK. CP28 и CP47 проверяют отдельно model wire, stored checkpoint, framework traces и final tool store.

### 5.3 Management API (proposed, prefix /management/v1)

| Семейство | Операции | Права |
|---|---|---|
| projects / applications / credentials | list/create/update/bind/revoke/rotate | scoped owner/admin, secret одноразово |
| principals / roles / sessions / oidc | list/invite/update/grant/revoke/auth/logout | explicit access_admin, grant subset boundaries |
| policies / revisions / deployments | draft/edit/validate/compare/export/import/prepare/activate/rollback/status | editor vs publisher, CAS/reason/four-eyes |
| custom-types / rules / dictionaries / exceptions | draft CRUD/import/validate/templates | editor scoped, edits feed policy revision |
| destinations / integrations | configure/test/disable/health | integration_admin, trusted egress refs |
| explain / sandbox-runs / suites / runs / batch-jobs | execute/read/cancel/download | developer, isolated test domain and quota |
| decisions / history / reveals / metrics / reports | read/filter/export | scoped reader, distinct content/reveal grants |
| retention / vault / maintenance-plans | estimate/create/confirm/status | retention_admin, reveal independent |
| feedback / incidents / alert-rules | annotate/triage/fix-link/verify/close | analyst/editor, no silent repair |
| capabilities / coverage / engine-versions / status | read actual installed state | scoped operational metadata |

Для variable route `{id}` разрешён только ожидаемый UUID/opaque ID, method-specific allowlist и backend authority; `path`/host/port/query-url клиент не задаёт. Просмотр статистики не наследует права на полный текст. Все write endpoints имеют explicit auth, concurrency token и audit; UI не обходной путь.

## 6. UI-контракт: из двух источников в одну систему

| Пользовательская задача | Backend и выбранная функция | Что обязательно видно |
|---|---|---|
| «Работает ли?» | F09/F16/F21 + real selfcheck | liveness / readiness / scope coverage / last probe отдельно |
| «Что защищаем?» | F03/F19/F20 | реальные types/mechanisms/actions/limitations, не выдуманный каталог |
| «Как настроить своё?» | F05/F06 | matcher/context/generator/scope/expiry/examples/negatives |
| «Что изменится?» | F04/F14 | revisions/basis/comparable results/new masks/new unprotected/errors |
| «Как применить?» | F04 | validated→preparing→ready→active/failed, live ACKs, reason/approver |
| «Почему отказ?» | F03/F09/F13 | безопасное explanation + reproducible authorised test case |
| «Что пропустили?» | F14/F16 | confirmed annotated misses; unlabelled signals отдельно |
| «Кто смотрел данные?» | F02/F09 | principal/project/permission/reason/time/result, not raw value |
| «Что хранится?» | F15 | четыре разные retention domains, live refs, backups limitation |
| «Что уходит в SIEM/DLP?» | F17 | реальная sanitized payload schema, exact approved destinations |
| «Как встроить?» | F18 | versioned working snippets + host-side probe, никаких real keys |
| «Как обновить?» | F21 | engine release/schema отдельно от policy rollback |

Не переносить UI прототипный `SECRET` reveal, ползунки probability без score, 200MiB upload promise, full access всем, historical replay без исходников, `8s restart`, динамический внешний runtime и автоматическое закрытие incident.

### 6.1 Реестр покрытых участков

У application отображается ingress text/tools/RAG text, output checks, actual tool execution enforcement, unsupported files, restored recipients, integration probe versions. Статусы: `enforced`, `configured_unverified`, `monitor_only`, `unsupported`, `not_integrated`, `failed`. Наличие flag не создаёт `enforced`: либо наш proxy реально владеет этапом, либо host integration имеет актуальный проверенный контракт. Proxy не может доказать отсутствие прямого внешнего канала в клиентской сети; сетевой enforcement маркируется external responsibility.

## 7. Фоновые операции, приватность и отказные решения

| Отказ/условие | Нормативное поведение |
|---|---|
| UI недоступна | active policy продолжает, management недоступно |
| control.db нельзя прочитать | managed request/restore permissions 503, не stale allow |
| active policy не compiled на worker | worker не ready, managed request 503 |
| publish failed | старая revision active; явный deployment failure |
| required DLP не отвечает | deny/503, не автоматический reroute; host может запросить отдельный допустимый сценарий, который заново проходит свои required checks |
| optional DLP down | baseline действует; status not_evaluated, не false completed |
| SIEM outage | bounded outbox; required cap → backpressure, optional documented drop summary |
| mandatory audit disk full | до egress/disclosure/write deny/503; диагностический health остаётся distinct |
| provider down | Ошибка upstream/502, без автоматической смены модели или URL; routing/retry решает caller |
| output violation/size overflow | held buffer discarded; no prefix release; explicit stream error |
| lease expired/revoked | сохраняем current engine stop semantics; не обходить лицензирование management testing |
| test/job role down | jobs queued/retry epoch; primary отдельно обслуживает active |
| namespace/token purged | cache/restore denied по deletion epoch; no resurrection |
| process dies после mint | orphan refs bounded GC; никакой успешной receipt без completed state |
| clock skew | bounded deadlines/monotonic runtime TTL where applicable; absolute stored cutoff проверяется с documented wall-clock assumptions |
| неподдержанный image/audio/file block | managed protected route 415, не unnoticed pass-through |

Raw vendor asset material не попадает в control revisions/exports/test manifests/support ZIP. Customer dictionary и test cases конфиденциальны независимо от формальной категории ПДн. Secrets полностью исключены из persistent result projections; raw capture отдельный opt-in risk, а не гарантия «ничего чувствительного».

## 8. Миграция, выпуск и тестирование

### 8.1 Schema и совместимость

- Новые stores/migrations требуют нового engine minor согласно действующему contract. Существующий minor [0.3 lock](<prototype/schema_lock.json>) не расширять задним числом.
- Migration create control.db/jobs.db + explicit known-store audit/vault version bumps. Старый probe должен выдать volume-too-new, untouched; new store alone не обеспечивает downgrade refusal.
- snapshot/space check/probe/migrate до worker fan-out. Repeated partial migration idempotent; no background implicit schema change при первом UI click.
- Mapping существующих namespaces и tenant keys сохраняются. На legacy key UI предупреждает про container-wide trust; переход managed — явный wizard с тестом и отключением legacy доступа.
- Новые секреты не reversible; старые SECRET mappings показываются migration inventory и удаляются только по отдельному confirmed плану.
- Новый static frontend vendored, static path release `/app/ui`, не `/app/pseudex`. UI не требует Node runtime у клиента.
- Smoke gates работают на source и compiled artifact; release numbers/publish согласно существующим двум streams. Изменения storefront/licensing для entitlement не маскируются engine release и не содержат client data.

### 8.2 Проверяемая готовность

Все F01–F23 из выбранного объёма требуют позитивного и отрицательного сценария на своей фактической границе (HTTP, coding harness или executor); изменяющие data plane — реального container gate. Для F23 дополнительно обязательны AC01–AC12 на проверенной OS/harness, не только HTTP mock. Proposed suite имена и dependency graph в [плане](<docs/plan-product-control-plane-sprint.md>). Existing detection/round-trip battery запускается на regenerated datasets; holdout нельзя подстраивать под новые recognizers. Новые client rules проходят mutation tests (искусственно пропустить/перемаскировать/вернуть чужое значение — отчёт обязан покраснеть).

Не объявлять «95%» на неизвестном корпусе. До реализации freeze clean baseline по типам/регистрам/направлениям; для нового типа ground truth и hard negatives. Quality регрессия отдельно от feature coverage. Нельзя принять собственный экран самопроверки как доказательство, что data действительно не ушли upstream: wire spy и конечный tool store проверяются независимо.

### 8.3 Предлагаемые performance budgets

Это **приёмочные бюджеты, не измеренные результаты**: на фиксированном CI/benchmark host и одном наборе bodies P0 control overhead без detection/network ≤10ms p95; with mandatory local defaults итоговая latency ≤baseline+15% либо явная техническая ревизия до release. Baseline определяется до code changes. Никакие remote DLP latency не прячем в «почти без накладных расходов»: timeout и separate p95 по стадиям.

Зафиксировать RAM/CPU per role, startup and double-snapshot peak, sync SQL writer contention, bounded queue/wal size. Long-running policy pin не держит DB read transaction и не мешает checkpoint. Batch нагрузка не должна увеличивать p95 primary более чем на согласованный бюджет (предложение +20% при выделенной analysis capacity); на 1core ограничение может требовать отключения batch при peak, а не ложной гарантии.

## 9. Способ выбора и проверки рыночного покрытия

Наша рабочая ставка: **единый policy/check/transform/integration механизм закрывает варианты клиентов дешевле, чем каталог bespoke функций**. Отраслевые идентификаторы становятся настройкой; corporate SSO/DLP/SIEM — стандартными интерфейсами; UI устраняет необходимость ручной поддержки.

Для заявления «90+%» нужна future demand matrix: scenario, segment, frequency/importance evidence, required capabilities, acceptance state, gap. Weighted coverage = sum(weight × independently verified covered)/sum(weight), при этом `partial` показывается отдельно и не округляется в `covered`. Это не recall detector и не процент строк customer TZ. До такой проверки документ говорит «широкое mainstream-покрытие», не «доказанные 90%».

Не заменять реальный продукт адаптером-интерфейсом: `classifier interface` не semantic detector, `authorize endpoint` не контролирует tool без wrapper, `route constraint` не firewall host, `backup UI` не проверенный restore, `offline design` не air-gap поставка.

## 10. Архитектурные основания и внешние первоисточники

Источники прочитаны в ходе проектирования. Это обоснование отдельных решений, не доказательство доли рынка и не предложение импортировать все перечисленные системы.

| Источник | Что применяем | Что не переносим |
|---|---|---|
| [OPA bundles](https://www.openpolicyagent.org/docs/management-bundles) | immutable revisions, validation-before-activation, status и no restart | eventual propagation не выдаём за синхронный multi-worker cutover; не persistence leased vendor assets |
| [OPA decision logs](https://www.openpolicyagent.org/docs/management-decision-logs) | decision_id, revision, privacy-safe event projections, bounded delivery | raw input logs/drop semantics по default не подходят нашим гарантиям |
| [OWASP Prompt Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | least privilege, tool boundary, testing indirect inputs, residual limits | keyword filter/system prompt не достаточная защита от всех атак |
| [SQLite WAL](https://www.sqlite.org/wal.html) | single-host WAL, one writer, bounded short transactions, per-store atomicity | NFS/shared network volume не HA, ATTACH не общая WAL-транзакция |
| [RE2 implementation](https://github.com/google/re2), [Python binding](https://github.com/google/re2/blob/main/python/re2.py) | bounded safe regex engine, unsupported syntax explicit | не Python backtracking fallback; linear regex не бесплатна при тысяче rules |
| [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html), [JWT BCP RFC8725](https://www.rfc-editor.org/rfc/rfc8725.html) | code flow, issuer/audience/algorithm/token-kind validation | ID token не universal service credential, arbitrary JWKS URL не доверенный endpoint |
| [LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom) | model/tool boundary adapters на поддержанных pinned APIs | UI mock builder.compile signature не публикуется без library test |

### 10.1 Предлагаемые решения, требующие утверждения владельцем

**D1:** базовый scope F01–F22 дополнен владельцем завершающим F23/T12 AI-разработки в том же sprint; narrow contracts обоих слоёв обязательны, итоговая приёмка C5. P2 не считается готовым интерфейсом.
**D2:** control plane local SQLCipher, single-node shipping first; cluster HA отдельный объём.
**D3:** managed API v2 + explicit compatibility migration; без silent trust upgrade legacy.
**D4:** policy hot activation и roles до mutating UI; restart для инфраструктуры только через ops.
**D5:** secrets block/redact, no reversible mapping; base tokenization сохраняется.
**D6:** default output scanning buffered, fast streaming только под фактические capabilities.
**D7:** exact scoped exceptions; arbitrary code hooks и глобальный allow regex запрещены.
**D8:** raw capture off; new session TTL явен; legacy permanent mapping не уничтожать по default.
**D9:** Python SDK+LiteLLM+LangChain/LangGraph thin adapters; собственный full AI router не создаём.
**D10:** market target не рекламообещание, календарь не выдумывается; запуск paid benchmarks/LLM требует отдельного GO.

Утверждение этого документа должно породить ADR в wiki и технические задачи. Пока выбранные здесь решения — согласованный между источниками **проект архитектуры для обсуждения**, а не изменение действующего нормативного состояния.
