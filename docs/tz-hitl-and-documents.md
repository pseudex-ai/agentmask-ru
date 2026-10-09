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
- Документы: native защищённый **DOCX и PDF с текстовым слоем**, сохранение структуры/оформления максимально, локальные отличия видимы; повреждение не success. **OCR исключён.** Непроверенные images/embedded parts default блокируют выдачу fully protected файла; explicit removal/partial policy отдельны.
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

## 3. F25 / K12 — native document protection

### 3.1 Поток документа

```text
upload/ref с подтверждённым доступом
→ тип/размер/ресурсы/структурная валидность
→ inventory всех parts/channels + supported coverage
→ text extraction с точной связью с original runs/objects
→ тот же Detector + effective policy + data transformations
→ native DOCX/PDF rewrite/rebuild
→ independent artifact validation + no-original canaries
→ encrypted result + coverage/fidelity report
→ authorised download либо protected upstream-file binding
```

Результат — **файл**, не plain text вместо документа. Один document artifact привязан к input digest, service, policy revision, mapping refs и parser/writer versions; cached protected file с другим policy/scope не переиспользуется.

### 3.2 Безопасный разбор и пределы

- Format sniffing по содержимому, а не filename/MIME; bounded ZIP expansion, object count, recursion/pages/stream size, time/memory/temporary disk. Parser запускается с минимальными правами и без внешнего network fetch. Никаких макросов, внешних relations, автоматического открытия ссылок или embedded executables.
- DOCX: inventory document/header/footer/footnote/endnote/comment/revision/custom properties/hidden text и relationships. Нельзя заменить видимый run, оставив оригинал в tracked deletion, comment или metadata. Text fragments могут пересекать runs; mapping должен сохранять структуру.
- PDF: поддержанный text layer/encoding/glyph positions и object/content streams. Black rectangle или incremental append поверх старого текста не считается удалением. Result должен быть переписан так, чтобы supported original text не извлекался из старых объектов/revisions/search/copy/metadata.
- Images, scanned/mixed pages, unsupported embedded structures, encryption/signatures и неподдержанные encodings должны получить явный capability verdict. Signed/password-protected/нестандартный документ не считается автоматически поддержанным; список форматов/режимов будет результатом SP08. Это не скрытое разрешение убрать юридическую подпись либо открыть protected файл.
- **Без OCR.** Непроверенные части default дают `unsupported_content` и не выдаются как fully protected. User может запросить supported removal либо explicit partial mode, если это разрешено политикой. Partial artifact имеет неизменяемый coverage report; скачивание не даёт автоматически разрешение отправить его внешней модели. Unsafe parser failure не reviewable business denial.

### 3.3 Подстановка, восстановление и формат

Форматные readers/writers не копируют правила PII: они преобразуют supported text parts через общий K05/K06. Hidden metadata с невозможным safe rewrite означает refuse/explicit supported removal, не skip. Исходный sensitive payload не добавляется в ordinary logs/test results.

Best-effort layout сохраняет paragraphs/styles/tables/page intent; локальные отличия переносов показываются. Коррупция, потеря структуры или невозможность проверить removal — failure. Критерии fidelity и поддержанный набор embedded elements закрепляются на golden files, не рекламируются как pixel-perfect для любых документов.

Owner запросил protected file; **автоматическое обратное восстановление скачанного PDF/DOCX целиком не утверждено**. Text/tool detok и evidence refs используют общий установленный контракт. Whole-document detok, редактирование уже masked files и сохранение цифровых подписей не добавляются без отдельного решения.

### 3.4 Протоколы и хранение

- Manual UI и API используют одинаковый protected artifact contract. В UI обязательно original/protected preview только с разрешениями, found categories, unsupported parts, fidelity differences, policy version и job state.
- Provider file upload/input-file/content blocks — отдельные protocol adapters **на уровне формата**, не model routing. Связка caller source-file ref → approved protected artifact → upstream file ID обязана быть service-scoped. Нельзя случайно отправить original file ID вместо protected.
- Поддержку конкретных upload/download endpoints OpenAI/Anthropic доказывает SP08; schema compatibility и API rights нельзя угадывать. До подтверждения manual/local artifact может быть готов, а auto provider path остаётся unsupported, не completed whole F25.
- Fixed approved upstream only; никакого произвольного URL-fetch документа, SSRF redirects либо credentials в ссылке. Filename не filesystem path; temporary/parser paths контролирует backend.
- Input/results/source maps живут encrypted в jobs/storage domain с отдельными read/download grants, quotas и lifecycle. Export-safe audit только IDs/counts/coverage. Original input и protected output — разные sensitivity classes: masked документ может содержать иные конфиденциальные данные, не автоматически public.
- Конкретная artifact TTL и способ краткоживущего plaintext для parser, которому нужен file handle, должны быть заданы до реализации и включены в canary tests; они не равны default pending HITL lifetime. Перенос библиотек/native dependencies в Nuitka образ требует licence/SBOM/сборочного spike.

## 4. Треки, последовательность и blockers

| Трек | Ядро и реализационный порядок | Входные зависимости | Готовность |
|---|---|---|---|
| T13 — HITL | K11: W36 contract/tests → W37 encrypted queue/decision → W38 exact consume/SDK/UI → W39 integration/retention gates | W02/W03/W05/W09/W10/W11/W12/W13/W14/W18; consume связывается с готовыми protect/output surfaces | H01–H10 + relevant CP; native harness часть проходит SP07/AC отдельно |
| T14 — Документы | K12: W40 SP08/format fixtures → W41 safe inventory/parser → W42 native rewrite/artifact checks → W43 UI/API/provider bindings → W44 full document acceptance | W02/W03/W05–W11/W13/W14/W15/W18; writer использует K05/K06 | DOCG01–DOCG10 + relevant CP; no OCR и truthful partial coverage |

T13 не зависит от готового T14 и наоборот. Если document verdict требует HITL, composition test включается **после обеих готовых interfaces**, а не образует cycle в фундаменте. Доставка внешних уведомлений через T07 optional extension; минимальная queue/UI/poll API не ждёт SMTP/SIEM. Enterprise интеграции идут после основных сценариев по приоритету владельца; их contract preparation может идти заранее.

W27/C4 базовой платформы теперь требует W39/W44 вместе с original W01–W26. T12 production начинается после C4. W35 принимает первый Claude coding slice как техническую контрольную точку; **W45** реализует/проверяет последующий Codex adapter на том же ядре. Привязка Codex к первому публичному coding-выпуску/C5 остаётся **OPEN-C01**: владелец выбрал порядок Claude→Codex, но не утвердил одновременную выпускную обязательность. Нельзя ни объявить Codex готовым после W35, ни задерживать выпуск новым условием без этого решения. Номер W36 больше W27, но зависимость определяется DAG, не числом; никаких циклов с W26 UI: shared shell/API-client готов раньше, полная UI-приёмка собирает готовые feature modules в W27.

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
| DOCG01 | MIME/extension mismatch, ZIP bomb, oversized PDF object graph, malformed package — bounded reject без parser network/host side effects |
| DOCG02 | Original canary в DOCX runs/headers/footnotes/comments/revisions/metadata — после supported rewrite не остаётся в распакованном artifact или в скрытых channels |
| DOCG03 | PDF visible/invisible text, old incremental revision/object/metadata canary — независимое извлечение не находит original; нарисованная плашка над исходником делает тест RED |
| DOCG04 | Image/scan/embedded unsupported part — default refusal; allowed removal/partial показывает exact coverage, partial download не authorizes provider send |
| DOCG05 | Golden structures/tables/styles/Unicode/длинные substitutes — формат открывается независимым reader, существенная corruption fail, допустимые differences задокументированы |
| DOCG06 | Cross-service artifact ID/cache policy change/revoked key — чужой download/forward запрещён, namespace/receipt refs проверяются |
| DOCG07 | Upload/cancel/parser crash/restart/cleanup — нет plaintext persist в непредусмотренных temp/log/WAL/export, resource budget bounded, stale claimant не публикует artifact |
| DOCG08 | Input file ref и provider file ID подменены/перепутаны — original никогда не forwards вместо approved protected artifact; неизвестный transport сообщает unsupported |
| DOCG09 | SECRET in document: default block/redact without regular reversible mapping; explicit HITL path соответствует H02/H08, не обход checks; synthetic negatives не ломаются |
| DOCG10 | Встроенный библиотечный writer «успешен», но artifact ещё содержит canary/сломаны структуры — independent oracle красный; source/compiled/native dependency licences и execution parity проверены |

Гейты — definition и planned fixtures, **не уже пройденные тесты**. Оракул удаления seeded originals/структуры независим от writer и не требует объявлять detector omniscient. Качество распознавания отдельно от надёжности удаления уже найденного значения. Whole-market90% из pass этого корпуса не следует.

## 6. Что остаётся открытым, а не решено молча

| ID | Вопрос | Где блокирует |
|---|---|---|
| OPEN-C01 | Обязан ли Codex быть готов к первому публичному coding-выпуску/C5 либо следует отдельным выпуском после Claude; порядок работ уже принят | Release criterion C5, не contract design W45 |
| OPEN-H01 | Конкретный native/live/deferred resume mode для Claude/Codex после lifecycle research, recovery после process restart | SP07/W28/W31/W45; basic queue/API не ждут универсального ответа для всех harness |
| OPEN-H02 | Полный набор permission checkbox/default admin reveal, короткий срок execution permit и exact payload policy для long pending | W36 contract; scope two roles/grants и no-auto-expiry pending уже приняты |
| OPEN-D01 | Проверенные writer/parser libs и лицензии, exact supported DOCX/PDF parts/signatures/fonts, resource limits | SP08/W40; не выбираем случайную библиотеку без evidence |
| OPEN-D02 | Provider file endpoints/auth/schema и billing новой document operation, artifact retention defaults | W40/W43; нельзя обещать native API compatibility/цену без проверки |

Это ограниченные решения/проверки, а не возврат отменённых model routing, OCR, semantic R&D или cluster scope. Источник truth — утверждённые owner principles; implementation detail ниже них не может тайно расширить полномочия или выпускные обещания.
