# Исправление baseline спринта: перенос документов на актуальный main

**Статус:** read-only сверка исходников, не новый product benchmark и не утверждение всей проектной спеки. Продуктовые решения владельца сохраняются. Документы должны находиться в main; все implementation worktrees создаются от актуального fetched origin/main.

## 1. Что произошло и какая база действительна

- Первоначальные документы создавались на старой локальной рабочей копии `380e3e72` с engine version file 0.3.19. Это была ошибка выбора технической базы; отставание обнаружилось только при первом push.
- Резервный docs commit `84f9ef32e14a4633f3d4fe9e82f1c92c619188a5` сохранён в отдельной ветке; это архив первоначального состояния обсуждения, **не основа разработки**.
- Подготовительный worktree создан от fetched `origin/main` **`4cc929bcc09e4a27eb5226771060c74643c46f43`**. Документы перенесены cherry-pick `ebdc38932f096d11deccd40c6054efe5450cd973`; никакие сторонние dirty code changes не перенесены.
- В этой базе [engine version](<prototype/version.txt>) = **0.3.21**, а `platform 0.3.36` в заголовке последнего commit относится к другому release stream. [Schema lock](<prototype/schema_lock.json>) всё ещё `0.3: vault9/audit1/tenants1`.
- Сверка проведена по actual code, current wiki и diff старой базы к новой. Ни модельные вызовы, ни detector datasets, ни контейнерные product gates этой работой не запускались. Наличие реализации в main не доказывает, что именно она присутствует в ранее опубликованном image.

## 2. Подтверждённые поправки к планированию

| Область | Что есть в актуальном коде | Что делать в спринте, не дублируя реализованное |
|---|---|---|
| Native типы | [ru_pii_v6](<prototype/pseudex/ru_pii_v6.py#L1-L57>) и интеграция в [ru_pii](<prototype/pseudex/ru_pii.py>): IBAN, IMEI, MAC/IMSI/device, legal/finance/insurance/utility families | F19/W23 — inventory, exposure, profiles, permissions и regression; IMEI/IBAN/MAC не считать новыми detectors |
| Корпоративные номера | Поддержанные forms policy/contract/court/account IDs уже есть в [native families](<prototype/pseudex/ru_pii_v6.py>) | Customer-specific shapes и configurable rules — новый слой; built-in формы не реализовывать второй раз |
| Public type versus vault label | [registry-to-engine mapping](<prototype/pseudex/ru_pii_v6.py#L87-L125>) — BANK_ACCOUNT→ACCOUNT, OGRNIP→OGRN и другие | Capability UI не переименовывает persistent identifiers и не создаёт вторую противоречащую vocabulary |
| Checksums | [COV-CHECKSUM-INHERIT](<prototype/pseudex/ru_pii_v6.py#L35-L50>): valid source→valid fake, faulty→faulty; safe range отдельно для каждого типа | Не вводить blanket checksum-invalid рецепт. Existing structured-ID semantics сохраняются, custom recipe требует отдельного type-level safety/utility contract |
| CVC/OTP | [cvc](<prototype/pseudex/cvc.py>): field/cue evidence, context-scoped temporary-code restoration; [structured handling](<prototype/pseudex/structured.py>) и vault mint уже есть | Managed secret block/redact/credential/HITL — всё ещё новый policy layer; API-key SECRET, CVC и OTP не объединять молча в один тип |
| JSON structural evidence | [json_fields](<prototype/pseudex/json_fields.py#L1-L82>) определяет source-offset string leaves/ownership, исключает keys, invalid JSON→prose fallback | Это не полный strict decoded-leaf transform. Escaped arguments, object keys, duplicate keys/NaN/depth и managed reject semantics остаются work items |
| Schema traversal | [envelope schema traversal](<prototype/pseudex/envelope.py#L1815-L1910>) уже рекурсивно обрабатывает description/title в поддержанных branches/schema forms | examples ещё не обходятся; enum/const/default явно не изменяются. Strict sensitive-literal check/deny — новое; не переписывать готовый обход descriptions |
| Tool call/result association | [ToolCallContext/ToolResultContext](<prototype/pseudex/envelope.py#L49-L131>) и current-hop evidence связывают уникальный preceding tool call с result | Это transcript provenance, не authenticated tool identity/permissions. Новый guard переиспользует provenance, не создаёт параллельный слабый correlator |
| Нотация и обратная форма | [notation](<prototype/pseudex/notation.py>), [unmask_response](<prototype/pseudex/envelope.py#L1914-L1959>), [redact](<prototype/pseudex/redact.py>) и leaf_notation metadata уже развиты | Новые receipts и recipient permissions оборачивают существующее восстановление. Caller leaf_notation не trusted schema binding; malformed JSON legacy fallback не strict managed validation |
| Conversation scope | [Vault views/scope](<prototype/pseudex/vault.py#L3550-L3605>) уже есть; [derived conversation key](<prototype/pseudex/envelope.py#L1415-L1444>) остаётся эвристикой | Не добавлять scope flag с нуля. Strict namespace/receipt membership, separate app authority и retention — реальные gaps |
| Transform cache | [own-evidence discriminator](<prototype/pseudex/envelope.py#L1503-L1521>) добавляется к base key перед cache lookup | При введении policy/bundle/retention epochs сохранить этот discriminator. Формула «только org/conversation/raw» больше не описывает полный actual key |
| Assets | [build/load](<prototype/pseudex/assets.py#L462-L565>) поддерживает richer leased structured/composite data и atomic pointer publish | Request-wide snapshot/revoke fencing всё ещё не сделаны. Customer dictionary нельзя подменить копией vendor leased tuning на диск |
| Диагностика | Current detector/operator/UI получили suppression/identity/latency instrumentation; существующие diagnostic counters — не ноль | Использовать их как исходную операционную базу; не выдавать их за размеченные FP/FN или полноценный policy decision ledger |
| Stores/schema | Engine store registry остаётся vault/audit/tenants, lock не изменился | Новые control/jobs stores, scoped identity и migrations всё ещё proposed; новый minor/old-probe fence нужны по факту schema changes |

### 2.1 UI/API уточнения, которые также нельзя потерять

- [Operator /stats](<prototype/pseudex/operator.py#L591-L655>) добавляет `suppressed_by_type/total/since`; [Prometheus](<prototype/pseudex/operator.py#L782-L790>) публикует suppression totals. Это worker-local события детектора, не подсчёт истинных FP/FN и не scoped к окну выбранного org.
- [Identity probe](<prototype/pseudex/operator.py#L175-L224>) и [UI](<prototype/pseudex/localui/static/app.js#L1232-L1258>) показывают synthetic canonicalization stability. Это не production round-trip success rate.
- [Latency backend](<prototype/pseudex/operator.py#L294-L329>) и [UI](<prototype/pseudex/localui/static/app.js#L1030-L1145>) дают opt-in percentiles текущего worker; derived sum стадий не p95 целой операции. Missing/off/unmeasured не ноль.
- [UI routing](<prototype/pseudex/localui/static/app.js#L1991-L2001>) не содержит hop explorer. Наличие runtime hop integrity не означает такой экран.
- [leaf_notation sidecar](<prototype/pseudex/service.py#L765-L799>) и [proxy](<prototype/pseudex/proxy.py#L697-L705>) — реально принимаемая metadata, но не authenticated recipient permission.
- [Proxy billing](<prototype/pseudex/proxy.py#L732-L738>) после masking до provider сохраняется. Sidecar masking billed, а [proxy sandbox /mask](<prototype/pseudex/proxy.py#L928-L941>) отдельный unbilled путь. Future isolated tests нельзя рекламировать как одинаково уже бесплатные во всех текущих legs.
- [Health/license](<prototype/pseudex/service.py#L554-L624>) имеют разные serving/alarm критерии; `/health` не unconditional process liveness. [Status](<prototype/pseudex/operator.py#L519-L539>) уже содержит schema/process/memory, их надо расширять, не изобретать заново.
- [Local UI access](<prototype/pseudex/localui/server.py#L248-L291>) по-прежнему shared startup/password session/container scope; [bridge allowlist](<prototype/pseudex/localui/server.py#L103-L107>) не содержит policy CRUD. Новое SSO нашей storefront-платформы не доказывает именованную auth в локальной админке движка.

## 3. Какие проектные gaps не исчезли

Настраиваемый customer rule lifecycle, policy drafts/activation/rollback, строгая verified identity/RBAC по принятым двум ролям, отдельная authority restore receipts, managed secret actions, runtime HITL, document-file protection и coding executor не становятся реализованными от расширения detector. Аналогично новые detector families не равны UI constructor/profile entitlements.

Current UI telemetry не считается SIEM delivery или policy-aware SLO всей компании; existing exact allowlist и token auth не именованные права. Full output DLP и native PDF/DOCX rewrite не выводятся из новых JSON helpers. Полный feature audit/source QA перед каждым треком обязателен в W01.

## 4. Важные архитектурные зависимости текущего main

В [STATE](<wiki/STATE.md>) уже есть решения D-070/D-073 о current-hop notation, D-074 о роли адресных частей, D-076 о collision/evidence semantics, D-081 о stable core + mutable parts и D-082 о deferred per-agent/tree-like scope. Их **нельзя отменять как побочный эффект control-plane sprint**.

Принятый владельцем AR14 новый managed conversation default рассматривается как отдельный configurable deployment/policy режим. Он не автоматически меняет identity legacy vault и не чинит её проблемы простым сужением namespace. Перед W09/SP04 нужно сопоставить текущие identity/provenance rules и миграцию с новыми требованиями, отдельно показать trade-offs cross-agent stability. Не считать старые design-status строки wiki доказательством отсутствия фактически уже написанного кода.

Для custom types форма fake должна сохранять утверждённые type semantics. Blanket «проверка checksum-INVALID» удалена из новой specs: она конфликтовала с current validity inheritance. Для CVC/OTP требуется explicit migration/policy inventory, а не предположение, что единственный секрет — label SECRET.

## 5. Исправленные документы и предел проверки

- [Основная спецификация](<docs/tz-product-control-plane-sprint.md>): actual baseline/version, evidence locations, cache/provenance/notation/native type inventory и checksum contract.
- [План](<docs/plan-product-control-plane-sprint.md>): main/worktree discipline, W01 freshness gate, W23 reuse native capabilities вместо повторной реализации, existing tests как обязательный baseline.
- [Матрица](<docs/tz-product-control-plane-matrix.md>): native type row не считается новым detector scope.
- [Реестр решений](<docs/decisions-product-control-plane.md>): WORKTREE01 и честная запись первоначальной ошибки.

Не выполнялась полная консолидация всех исторических обсуждений/дочерних вопросов. Документы/HITL добавлены владельцем после исходного F/W разбиения и по-прежнему требуют явных complete work packages/gates. Отправка документов в main сохраняет решения, **но не является GO на реализацию неразрешённых контрактов**.

Старые line anchors в изменённых engine-файлах удаляются там, где они указывали уже на другой код; свежие конкретные evidence ranges приведены в этом отчёте. Исторические источники из других worktrees/attachments не импортируются в release и не становятся единственными данными для реализации.

## 6. Дисциплина дальнейшей работы

1. Документы и approved decisions — в main.
2. Перед новым worktree: fetch origin → записать origin/main SHA → создать уникальную branch/worktree именно от этого SHA.
3. Прочитать current wiki/source, сверить capability delta; затем test-first implementation в выделенном scope.
4. Изменение общего контракта проходит main/интегратора; соседние треки не создают расходящуюся policy/DTO копию.
5. Неисполненные prerequisites не скрывать стартом от ветки другого трека. Contract fixtures можно использовать только с явно marked readiness.
6. Перед merge повторить affected tests на общей candidate revision; before-merge green отдельного worktree недостаточно.
