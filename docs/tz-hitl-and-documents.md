# HITL и документы: согласованный объём и проект исполнения

**Статус:** объём и пользовательские принципы приняты владельцем; схемы/API/библиотеки ниже — проект для реализации после контрактных проверок. Это не уже работающие функции. Основа — [реестр решений](<docs/decisions-product-control-plane.md>), [общая спецификация](<docs/tz-product-control-plane-sprint.md>), [план](<docs/plan-product-control-plane-sprint.md>).

Сверка выполнена с `origin/main` **633fb4816a6cfae07287e5cc493174fbfe2ee958**, engine version file 0.3.21, исходными DOCX и UI-демо. Текущий runtime этих функций не содержит. UI-демо показывает batch CSV/JSONL, а не защиту PDF/DOCX; исходное ТЗ требует «приостановить до согласования», но не задаёт ни часовой expiry, ни универсальный resume чужого harness.

**Идентификаторы:** F24/K11/T13/W36–W39/H01–H10 — HITL; F25/K12/T14/W40–W44/DOCG01–DOCG10 — документы. Добавлены без перенумерации существующих F01–F23/W01–W35/CP01–CP47/AC01–AC12. T13 и T14 идут **параллельно после self-service core**, не после coding только из-за большего номера. W45 — последующий Codex adapter после принятого Claude slice, AC13 его отдельная приёмка.

## 1. Неизменяемые принятые условия

- Один локальный инстанс, одна консоль, готовый UI + API, плоские «Агенты и сервисы». Нет fleet/Kubernetes/центра управления узлами.
- Две роли admin/user; дополнительные права на настройки/HITL выдаёт admin. Original reveal — отдельное право, безопасное превью default. Mandatory second-person approval не выбран.
- SECRET default блокирует конкретный model request; redact можно настроить адресно. Credential reference передаёт настоящий ключ только approved сервису/purpose через поддержанный adapter. Ручной список всех tools пользователю не нужен; автоматической доверенности по префиксу ключа тоже нет.
- Отдельная настройка может открыть уполномоченному reviewer **разовую передачу исходного ключа модели**. Это осознанное исключение из защиты, не псевдонимизация и не технический fail-open.
- Pending HITL payload хранится encrypted внутри Pseudex. Pending карточка по default не исчезает по времени; auto-expiry opt-in. Reminder/SLA не удаляет карточку. Tool/HTTP/hook timeout и срок approval — отдельные события.
- **Документы (DOC-ARCH):** документ — источник контента на границе контекста модели. Защищаем текст/структуру, попадающие в контекст через tool_result (read_doc и т.п.); сырой файл модели не нужен. Единственная особая точка — file-attachment к провайдеру: default block/извлечение текста/локальный маршрут, raw не пропускать молча. Native-перезапись файла не делается. **OCR исключён.** Обязателен документный бенчмарк (таблицы, судебные практики, отрасли, заявления).
- Ни model routing, ни provider fallback. «Только локальное назначение» — ограничение, которое должен соблюсти caller, а не автоматическая смена модели.

## 2. F24 / K11 — очередь согласований

### 2.1 К чему применяется

HITL создаётся для **reviewable policy decision** до внешней передачи или side effect. Ошибка mandatory detector, revoked licence, невозможность открыть vault, unsafe JSON, unknown executable grammar либо сломанный parser не становятся разрешимыми кнопкой «всё равно выполнить». Политика определяет, какие business/security причины допускают review и какие действия доступны.

Четыре возможных решения по секрету:

1. отклонить;
2. удалить секрет/выбрать другую разрешённую безопасную обработку;
3. передать credential разрешённому сервису через scoped reference, не модели;
4. raw-secret egress exception, **только** если заранее включён для данной области и у reviewer есть отдельное право.

Вариант другого назначения не означает наш reroute: caller явно подтверждает новое разрешённое binding, новое содержимое/назначение заново проверяются. Одобрение исходного запроса не переносится на произвольный новый endpoint.

### 2.2 Раздельные состояния

```text
Approval: awaiting_decision → approved | rejected | cancelled | expired(opt-in)
Execution: not_started | waiting_native | caller_detached | ready | running
           → completed | failed | outcome_unknown
```

`approved` не означает `executed`. UI показывает обе оси. Callback/native defer/resume выбирается по **проверенному** integration capability; прочитанные [harness lifecycle docs/source](<research/harness-hitl-lifecycle.md>) не равны эксперименту SP07. Неподтверждённый способ cold resume остаётся открытым решением HITL08; никаких незаметных retry/background side effects при утрате waiter.

Закрытие браузера не равно отмене operation. Stop/cancel/backend restart обрабатываются по actual protocol и отображаются. Если нет актуального способа продолжить, карточка остаётся с `caller_detached`/`resume_unavailable`; API не имитирует успешное выполнение. Конкретный fallback после такого состояния требует владельца/проверенного adapter, это не принятая универсальная политика повторов.

### 2.3 Данные и транзакции (proposed)

- `control.db`: `approval_requests` — safe metadata, subject/service, reason IDs, allowed action kinds, policy/binding revisions, state/revision, operation identity, payload reference; `approval_decisions`, `approval_permits` и audit/outbox.
- `jobs.db`: encrypted `approval_payloads`, отдельный retention class; не обычный test/batch result с default TTL 24h. В payload допустим исходный секрет **по явно принятому HITL storage contract**, но не в event preview/log/URL/notification. Содержимое default отсутствует в обычных configuration/export/долгих backup.
- Original provider key transport binding и credential broker — отдельные authorised secret refs; нельзя использовать approval payload как searchable общий secret vault.
- Raw payload сначала durable encrypted; затем metadata row+audit одной control transaction. При crash между stores — orphan без actionable approval, удаляемый восстановлением; нет обещания общего ACID между WAL-файлами.
- `request_id`/approval ID не bearer secret. Любое read/decision/consume требует verified subject/grants/service ownership. Хеш содержимого — keyed digest, чтобы low-entropy чувствительные поля не угадывались из публичного hash.
- `approve` проверяет актуальную запись/CAS, права reviewer и enabled raw-exception setting. Менять permanent policy из approve нельзя; «запомнить правило» создаёт draft и проходит обычный validation/apply.
- `consume` повторно проверяет live grants/revisions/destination/exact payload/required checks и однократно допускает **попытку** исполнения. Повтор response/два reviewer не создают второй side effect. Внешний service call не становится exactly-once транзакцией с нашей БД; uncertain outcome фиксируется, не повторяется автоматически.

### 2.4 Сроки и ёмкость

Pending не автоистекает по default. Администратор может включить expiry на policy/service; это отличается от срока уже выданного execution permit и от normal vault TTL. Reminder/escalation status без удаления payload допустимы. При завершении/отмене/настроенном expiry sensitive payload очищается согласно явному контракту, safe audit остаётся. Долгое ожидание должно быть видно как sensitive storage age, а не скрытая бесконечная копия.

Размер/count/disk quotas обязательны, но точные значения остаются configuration proposal до измерения. При заполнении очередь отказывает **новым** ожиданиям с ясной ошибкой; не молча удаляет pending. Восстановление из backup не должно оживлять истёкшие/отозванные permits. Memory plaintext lifetime, snapshots, WAL, temporary files и source-client logs учитываются в threat model; «root никогда не прочтёт RAM» не обещается.

### 2.5 UI/API

Очередь: агент/сервис, операция, причина, получатель, возраст, reviewer status, connection/caller status, safe preview, доступные действия. `reveal` отдельная кнопка/право с audit-before-value. Key отправки модели скрыт от обычного reviewer; raw exception скрыт/disabled при выключенной policy, а не «позволяет всё».

Proposed management endpoints: list/read/decide/cancel/reveal pending request; proposed data endpoints create pending/status/consume permission. Конкретные URL фиксируются в W36 contract, не публикуются как existing API. SDK умеет вернуть typed `approval_required` и correlated ID; compatible host реализует wait/poll/events/native pause. OpenAI/Anthropic клиент **не обязан понимать наш новый JSON статус без adapter**: baseline mode показывает limitation и безопасно отказывает, не молча ломает схему стандартного ответа.

Нажатие approve не создаёт дополнительного billable masking автоматически. Повтор HTTP decision idempotent; существующие successful-mask billing semantics сохраняются. Новая оплата ожидания/операции/страницы — не утверждена. До production нужен документированный metering mapping для двух стадий protect/resume и тест отсутствия двойного списания за повторное delivery одного решения.

## 3. F25 / K12 — документы на границе контекста модели

**Принято DOC-ARCH (владелец):** «мы платформа безопасности для AI трафика, не для нахождения ПД в документах… моделька видит только то, что попадает ей в контекст». Документ — источник контента, а не отдельный форматный пайплайн перезаписи файлов.

### 3.1 Ядро: защита контента в контексте

Любой текст/структура, попадающие в контекст через `tool_result` (read_doc, поиск по документам, табличные выгрузки и т.п.), проходят тот же Detector + effective policy + transformations, что и прочий контекст. Сырой файл модели не отправляется. Переиспользуется существующий envelope/tool_result masking; документ не заводит параллельный слабый correlator.

Закрываемые пробелы контекстного пути: очень длинные документы и чанки/токен-бюджет; таблицы и структурированный текст с сохранением связей; смешанные/нетекстовые блоки; границы чанков, не рвущие span одного значения; nested content blocks.

### 3.2 Единственная особая точка: file-attachment к провайдеру

Есть путь, где байты уходят провайдеру в обход text-конвера — OpenAI file input / Anthropic document content block (source document). Там провайдер получает файл напрямую, и tool_result masking не применяется.

Default: **block** либо извлечь текст в контекст (если поддержан протокол и текст можно замаскировать) либо разрешённый локальный маршрут. **Никогда не пропускать raw молча.** Native-перезапись файла не нужна и не делается. Поддержку конкретных file-endpoints/протоколов доказывает SP08; до подтверждения такие блоки = unsupported/blocked, не «completed F25».

### 3.3 Не делаем

Native-перезапись DOCX/PDF/XLSX, выдача redacted файла для скачивания, OCR/сканы. Форматная «поддержка» нужна лишь настолько, насколько надо извлечь текст в контекст либо решить block/route — не как «произвести защищённый файл».

### 3.4 Документный бенчмарк (новый, обязательный)

Новый корпус документ-производных текстов в агентных сценариях: таблицы, судебные практики, отраслевые документы, заявления/обращения, смешанные структуры. Метрики по тому, что модель реально видит в контексте: recall/coverage/round-trip/over-mask; независимая разметка; can-fail прибор (инструмент, способный провалиться). Измеряем качество маскирования текста, попавшего в контекст, а не «прочитали файл».

## 4. Треки, последовательность и blockers

| Трек | Ядро и реализационный порядок | Входные зависимости | Готовность |
|---|---|---|---|
| T13 — HITL | K11: W36 contract/tests → W37 encrypted queue/decision → W38 exact consume/SDK/UI → W39 integration/retention gates | W02/W03/W05/W09/W10/W11/W12/W13/W14/W18; consume связывается с готовыми protect/output surfaces | H01–H10 + relevant CP; native harness часть проходит SP07/AC отдельно |
| T14 — Документы (context) | K12: W40 doc benchmark/fixtures → W41 контекстный охват (длинные доки/таблицы/блоки) → W42 file-attachment block/extract/route → W43 UI/API coverage + benchmark integration → W44 doc acceptance | W02/W03/W05–W11/W13/W14/W15/W18; переиспользует K05/K06 | DOCG01–DOCG10 + relevant CP; context-boundary, no native rewrite, no OCR |

T13 не зависит от готового T14 и наоборот. Если document verdict требует HITL, composition test включается **после обеих готовых interfaces**, а не образует cycle в фундаменте. Доставка внешних уведомлений через T07 optional extension; минимальная queue/UI/poll API не ждёт SMTP/SIEM. Enterprise интеграции идут после основных сценариев по приоритету владельца; их contract preparation может идти заранее.

W27/C4 базовой платформы теперь требует W39/W44 вместе с original W01–W26. T12 production начинается после C4. W35 принимает первый Claude coding slice как техническую контрольную точку; **W45** реализует/проверяет последующий Codex adapter на том же ядре. **OPEN-C01 решён:** Codex обязателен в первом публичном C5 — оба adapter проходят свои AC-гейты на declared OS до первого публичного coding-выпуска. Номер W36 больше W27, но зависимость определяется DAG, не числом; никаких циклов с W26 UI: shared shell/API-client готов раньше, полная UI-приёмка собирает готовые feature modules в W27.

## 5. Предварительные гейты — до business implementation

### H01–H10

| Gate | Негативный сценарий / наблюдение |
|---|---|
| H01 | Awaiting decision не выпускает upstream/tool; хранение pending encrypted. Без специальных permissions API/UI не читает чужую карточку/payload |
| H02 | Raw-secret exception off или нет special grant — действие недоступно и direct API deny; opt-in exact approval касается только выбранного payload/destination |
| H03 | Два reviewer/повтор decision/повтор consume — не два execution attempts; stale CAS не перетирает решение |
| H04 | Revoke/изменившийся payload/file snapshot/target после approval — recheck/refusal, не применение старого разрешения |
| H05 | Default pending переживает время/GUI disconnect без auto-expiry; opt-in expiry/cancel удаляет sensitive payload и оставляет safe terminal audit |
| H06 | Очередь заполнена, store упал, crash между encrypted payload и metadata — bounded refusal/orphan recovery, no raw fail-open и no silent purge существующих pending |
| H07 | Approve, disclosure и actual execution имеют разные состояния; unknown side-effect outcome не повторяется автоматически |
| H08 | Safe preview по default; raw reveal требует отдельного права и audit-before-value; keys не попадают в notifications/logs/backups/results |
| H09 | Caller/harness disconnected/stopped/restarted — поведение соответствует проверенному capability profile, old request ID не назначается новому вызову; неподдержанный resume явно unavailable |
| H10 | Путь protect→wait→approve→resume сохраняет billing contract и audit; повтор доставки approval не списывает как новая protection operation автоматически; operational errors не становятся reviewable allow |

### DOCG01–DOCG10

| Gate | Негативный сценарий / наблюдение |
|---|---|
| DOCG01 | Длинный документ/чанки: защита не пропадает на границе чанка, span одного значения не рвётся, bounded memory |
| DOCG02 | Таблицы/структурированный текст: связи колонок сохраняются, round-trip не портится |
| DOCG03 | Нетекстовый/смешанный блок в tool_result: text часть маскирована, неподдержанная часть явная, не тихий skip |
| DOCG04 | file-attachment к провайдеру: default block/extract/route, raw никогда не уходит молча |
| DOCG05 | Документный корпус (таблицы/суд/отрасли/заявления): recall/coverage/round-trip/over-mask измерены, negatives не перемаскированы |
| DOCG06 | Cross-service/namespace: чужой document tool_result/файл не читается и не пересылается |
| DOCG07 | Огромный документ/токен-бюджет: защита не снимается ради бюджета, частичный вывод явно incomplete |
| DOCG08 | SECRET в тексте документа: default block/redact, explicit HITL по H02/H08 |
| DOCG09 | Caller-provided file id/ref: подмена не отдаёт другой документ, unknown transport unsupported |
| DOCG10 | Бенчмарк-прибор can-fail: мутация (пропустить/перемаскировать/чужое значение) делает отчёт RED |

Гейты — definition и planned fixtures, не уже пройденные тесты. Оракул — независимая разметка документ-производного текста и can-fail прибор; он не требует объявлять detector omniscient. Качество распознавания отдельно от полноты контекстного охвата. Whole-market90% из pass корпуса не следует.

## 6. Статус открытых вопросов

| ID | Статус и решение |
|---|---|
| OPEN-C01 | **Решено:** Codex обязателен в первом публичном C5 (оба adapter до первого coding-выпуска). Последовательность разработки Claude→Codex не меняется |
| OPEN-H01 | **Решено:** первый релиз — только live-ожидание; cold restart/resume не обещаем, неподдержанное явно `caller_detached`/`resume_unavailable`. Defer/persisted resume — следующий этап |
| OPEN-H02 | **Решено:** reveal выключен по default, админ включает себе отдельной операцией (и выдаёт другим адресно), с аудитом |
| DOC-ARCH | **Решено:** документы только на границе контекста; native-перезапись файла и redacted-скачивание исключены; file-attachment → block/extract/route; добавлен документный бенчмарк. Точный протокол file-endpoints доказывает SP08 |

Это ограниченные решения/проверки, а не возврат отменённых model routing, OCR, semantic R&D или cluster scope. Источник truth — утверждённые owner principles; implementation detail ниже них не может тайно расширить полномочия или выпускные обещания.
