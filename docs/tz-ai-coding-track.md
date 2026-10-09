# AI-разработка: завершающий трек единого спринта Pseudex

**Статус:** включение направления в текущий спринт запрошено владельцем; конкретная архитектура ниже — проект для последующей методологической проработки. Код, команды, paid evals и релизы сейчас не запускаются.

Связь: [общая спецификация](<docs/tz-product-control-plane-sprint.md>), [основной план](<docs/plan-product-control-plane-sprint.md>), [матрица возможностей](<docs/tz-product-control-plane-matrix.md>). Новый паспорт **F23**, новый завершающий трек **T12**, специализированное ядро **K10**, пакеты **W28–W35** (Claude slice), затем **W45** (Codex), проверки **AC01–AC13**. Runtime HITL/credentials используют общий F24, документы — F25, см. [контракт](<docs/tz-hitl-and-documents.md>). Старые W/CP не перенумеровываются. Jev отменён владельцем для текущего спринта; [проверка пригодности](<research/jev-typesafe-product-fit.md>) остаётся архивом. Высокоуровневые coding defaults проходят [методологическое согласование](<docs/decisions-product-control-plane.md>), а не считаются утверждёнными автоматически.

**Последнее решение владельца:** coding/harness integration снова планируем полностью в завершающем T12, реализуем после более приоритетной базы. Промежуточная отмена коннекторов superseded (§4duodecies [реестра](<docs/decisions-product-control-plane.md>)). HITL08 имеет docs/source evidence, но actual resume mode остаётся открытым до pinned runtime SP07 и выбора применимого контракта. SP07/W31/C5 возвращены в план, но не считаются реализованными/проверенными.

**Принято CODING01-platforms:** целевые execution environments — Linux и macOS; Windows через отдельно проверенный WSL. Нативный PowerShell/Windows executor не входит. Прежние Linux-only defaults ниже superseded как единственная целевая среда; Linux containers не доказательство macOS/WSL compatibility. Поставка самого Pseudex остаётся компактной.

**Принято CODING-first-harness:** первым доводим Claude Code, затем Codex. Не требуем одновременной реализации двух adapter до первого рабочего coding-сценария; и не считаем Codex уже выполненным общей поддержкой model API. DSH — источник исследования, не выбранный обязательный третий connector. Реализационный mode и версии обоих ещё проверяются SP07; последовательность должна попасть в итоговое work/gate разбиение.

## 1. Продуктовый результат и границы

**Обещание первой версии:** поддержанный AI-кодер читает локальный текст, ищет реальные значения и изменяет разрешённые текстовые файлы; модель видит защищённое представление, а локальные инструменты получают точные данные только для разрешённых операций. Не строим собственную IDE, модель-кодер или универсальный shell-антивирус.

Пользователь получает в той же админке профиль «AI-разработка», подключение coding harness, корни workspace, разрешённые операции, ограничения на данные/egress, историю решений и проверку интеграции. Используем общие identities, policies, receipts, audit, retention и capabilities. Подключение desktop executor не означает передачу ему общего ADMIN_TOKEN.

**Один контур — логически единый, не обязательно один процесс/сетевой порт.** Model boundary защищает контекст; локальный execution boundary защищает реальные действия. Proxy без контроля executor не доказывает безопасность Bash, файлов и прямых сетевых запросов клиента.

### 1.1 Пример ценности

```text
Локальный лог: ошибка для anna@company.example
Модель видит: ошибка для user-17@example.invalid
Модель просит: grep -F -- 'user-17@example.invalid' app.log

Обычный фильтр: в настоящем файле подстановки нет → поиск не находит запись.
Pseudex Coding: разрешённый аргумент восстанавливается для локального поиска;
результат снова защищается перед передачей модели.
```

**Эффект:** модель оперирует стабильными ссылками на чувствительные значения, но инструмент работает с настоящим окружением. Сначала проверяем этот детерминированный сценарий, затем более сложные изменения файлов.

### 1.2 Что включено и что нет

| В текущем треке | За пределами первой поддержанной версии |
|---|---|
| Claude Code первым, затем Codex отдельным adapter этапом; Linux/macOS/WSL отдельно проверяются | Поддержка всех IDE и native Windows/PowerShell; утверждение Codex-ready по одному Claude run |
| Поддержанные Anthropic message/tool envelopes и точный capability manifest | Все private APIs, произвольные multimodal/reasoning-блоки и автоматический replay непрозрачных подписанных блоков |
| Текстовые read/search, поддержанный subset Bash-вызовов, контролируемый literal patch | Произвольная программа shell/Python/JS/SQL с восстановлением токенов внутри неё |
| Exact byte-preserving mappings для approved data slots | Морфологическая канонизация пути/исходника, fuzzy correction команд или имён файлов |
| Workspace confinement, process/resource limits, no network default | Контроль всего хоста/root, обход прав доступа IDE, невозможность утечки через произвольный unmediated процесс |
| Secret injection в заранее зарегистрированную узкую операцию | Восстановление API-ключа в текст произвольного bash -c, общего prompt или файла репозитория |
| Общие policy/audit/retention и coding regression fixtures | Второй независимый policy engine или отдельный неуправляемый vault для IDE |

Неизвестная операция возвращает `unsupported_execution_context`/deny, а не выполняется «потому что модель уверена». Пользовательское подтверждение само по себе не делает неподдержанный синтаксис безопасным для восстановления. Допустим переход на явно разрешённую локальную модель/ручное исполнение, но это отдельный маршрут и не помечается как наш защищённый round-trip.

## 2. Что уже найдено в репозитории

Worktree `Obscura-vibecode`, branch `spike/anthropic-shim`, экспериментальный [anthropic_shim.py](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py>) на момент осмотра был untracked. Не переносить worktree целиком поверх main и не считать общий diff ветки coding-реализацией.

| Что есть в spike | Что требуется перед production |
|---|---|
| [Anthropic traversal](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py#L94-L126>) system/messages/tool_result/tool_use | Typed envelope validation, supported field manifest, no in-place mutation of shared model state |
| [JSON-safe tool restore](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py#L129-L146>) | JSON string command всё ещё программа; нужен execution-aware contract |
| [SSE input_json buffering](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py#L187-L260>) | Per-block IDs/sequence/cancel/limit/error tests, protocol fidelity; unknown blocks не pass-through автоматически |
| [Dev bundle, один org](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py#L31-L49>) | Общая production лицензия, verified identity/scope и shared core |
| [Fallback исходного input при ошибке](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py#L85-L91>) | Fail-closed, никаких raw returns при обязательном transform failure |
| [Debug log с восстановленным content](</Users/igor/Projects/Obscura-vibecode/prototype/anthropic_shim.py#L178-L180>) | Только privacy-safe projections; real args не сохранять в traces/support |

Spike — источник опыта для adapter, не основание заявлять пройденные security/compatibility gates. Не запускался этой проектной работой.

## 3. K10 — execution-aware подстановка: основной архитектурный фокус

K10 — adapter/kernel поверх K02/K03/K05/K06/K07/K09. Он не заменяет их policies, grants, transaction boundaries и лицензирование.

### 3.1 Два представления и точная provenance

- **Model view:** защищённые тексты, псевдонимизированные data literals/пути, стабильные session-scoped placeholders. Receipts/capabilities/секреты не передаются модели.
- **Execution view:** ephemeral восстановленные значения, проверенные executable/argv/cwd/file snapshot/operation. Только локальному approved executor, после live permission consume.
- **Coding mapping:** exact original bytes/encoding плюс source location/snapshot/type/allowed context. Для путей, search literals и patch preimage не использовать `NAME` nominative или общую нормализацию как значение восстановления. Domain `coding_exact` отделён от canonical PII; collision checks/scoped access используют общую инфраструктуру.
- **Обычная PII детекция остаётся:** она помогает найти чувствительное содержимое. Но вид подстановки и обратная форма задаются coding renderer. Semantic placeholders в конфиге не обязаны притворяться checksum-valid реальным credential.
- Один и тот же fake из другой session/project/workspace не считается ссылкой на текущее значение. Частичные, изменённые или неоднозначные placeholders не угадывать.

Детектор не гарантирует понимание произвольного исходного кода как секретной бизнес-логики. Если сам алгоритм нельзя выносить наружу, policy ограничивает передачу разрешённым локальным binding либо отказывает; модель выбирает caller, а не обещает сохранить смысл после полного сокрытия кода.

### 3.2 План исполнения, не строковый replace

Proposed DTO, не текущий API:

```text
CodingExecutionPlan {
  project, app, session, workspace_id,
  operation, executable_identity, argv_template, cwd_ref,
  typed_slots[{mapping_ref, position, context, expected_bytes_digest}],
  source_snapshot_refs, file_targets, policy_revision,
  limits, network_profile, optional_credential_ref,
  protected_plan_digest, resolved_plan_digest
}
```

1. Adapter разбирает поддержанный input локально. Semantic classifier/Jev не добавляются в этот sprint и не заменяют parser/authority; поведение определяется проверенным syntax/context contract.
2. Для Bash первой версии допускаются **простые команды из явного списка executable+option grammars**, с literal data slots. Не достаточно «разрешён grep»: проверяются флаги, operand positions, input files, subprocess/config side effects, encoding и resource caps. Стартовый кандидат: literal read/search (`grep -F`, `rg -F` в ограниченной конфигурации) и controlled file read, а не все флаги этих утилит.
3. Поддержанный Bash subset превращается в typed executable+argv и исполняется **без повторной интерпретации восстановленной строки shell**. Parser не вызывает expansions. `$()`, backticks, `eval`, `bash -c`, shell functions, pipelines, redirections, process substitution, heredoc, dynamic glob/variables и вложенные языки с token restoration — пока отказ. Это ограниченная совместимость, показываем её явно.
4. Кавычки в original value остаются данными argv, не новыми shell instructions. Дополнительно валидируется **смысл аргумента утилиты**: option injection/regex/path/URL не исправляются одним shell escaping.
5. Policy оценивает resolved target локально; log хранит safe IDs/digests, не real args. Permit связан с обеими формами плана, workspace/конкретной операцией/ресурсами/current epochs. Изменение плана после authorize требует нового allow.
6. Непосредственно перед side effect — общий online consume и recheck snapshot/path/permissions. Запрет шага означает, что executor не вызван. Already begun side effect не объявляется отменённым задним числом.
7. Stdout/stderr/exit metadata/file snippets проходят защиту **до попадания в model-facing history, telemetry и checkpoint**. Unsafe streaming prefix не выдаётся: bounded full buffer по default, превышение лимита → отмена/typed truncated error без raw tail.

**Bash parser не security sandbox.** Запуск ограничен workspace/process/network полномочиями реального executor; бинарник/окружение/конфигурация утилиты тоже часть execution identity. Нельзя разрешить одно имя программы, которую workspace подменил через PATH. Выбираются fixed executable paths, контролируемый env, отсутствие пользовательских startup hooks, process tree timeout/kill и закрытые лишние file descriptors.

### 3.3 Файлы, read/search и patch

- Workspace registry задаётся trusted local operator, не строкой пути от модели. Symlink/path traversal/rename races, выход из корня и hardlink aliases рассматриваются явно. Проверка пути и actual file operation должны использовать capability-safe directory handles/доказанную эквивалентную OS-схему; простое `realpath` перед поздним `open` недостаточно.
- Read/search фиксирует source file identity/version/digest и ограничивает binary/encoding/file size; immutable view содержит offset map между raw и protected text.
- Первая запись — narrow literal patch по protected preimage, а не general `sed`/Python/SQL. Model присылает patch для известного защищённого snapshot. Adapter сверяет preimage, переводит offsets через provenance, сохраняет exact unchanged originals и применяет only approved changes атомарно с compare-and-swap по actual file digest. Если original file изменился — `stale_file_snapshot`, не fuzzy apply.
- Token restoration допускается только в известном data context; token в identifier/operator/import/module path/исполняемой конструкции без поддержанного language-aware adapter → отказ. Произвольный код, похожий на текст, не получает разрешение на подстановку по умолчанию. First release поддерживает явно выбранные text/config literal operations; расширение языковых AST — следующий объём.
- Diff для пользователя локально может содержать реальные значения только с правом на просмотр. В model state/audit уходит protected diff. Raw original backups/temp patch files не создаются вне управляемого encrypted domain.
- Запуск тестов репозитория — исполнение кода, а не read-only диагностика. Только отдельный explicit workspace-sandbox profile, без production secrets/network по default; не автоматически разрешать `npm test`, `pytest` или package install по имени.

### 3.4 Секреты — отдельная операция, не обратимый текст

**Принято CRED-UX01:** пользователь настраивает сервисное подключение и назначение credential, не перечисляет каждый tool. Поддержанные adapters/Bash используют узкое разрешение автоматически; новое использование через HITL. Модель может видеть credential reference/substitute, а настоящий ключ получает approved исполнение/прокси; это не обычный PII mapping. Неизвестный host/purpose не становится доверенным по форме ключа. Постоянное правило из HITL создаётся только через полномочия policy editor и draft/check/apply. Требование не переносится как ручная настройка каждого телефона/имени.

**HITL дополнение:** default raw-key egress запрещён, но администратор может включить отдельный разовый вариант отправки оригинала модели для уполномоченного reviewer с exact binding/предупреждением/audit. Pending payload разрешено временно хранить encrypted внутри Pseudex, не в logs/долговременных backups. Это явные принятые исключения к прежним абсолютным default-формулировкам ниже; arbitrary shell substitution или неисправные mandatory checks ими не разрешаются.

Known SECRET по default блокируется/удаляется до model boundary. Исключение — принятое F24 opt-in exact one-use разрешение конкретному получателю; оно явно маркирует intentional disclosure, не privacy-safe substitution. Tool credentials не выдаются в command string или reversible mapping. Optional secret broker предоставляет secret **только заранее зарегистрированной узкой операции** (например, конкретный API-host/метод/credential purpose) через подходящий защищённый канал. Env injection сам по себе не защита: программа может прочитать env и отправить его наружу. Поэтому запрещены произвольные команды с credential, наследование всем детям и неограниченная сеть. Нет обещания безопасно дать production credential любой agent-generated программе.

Ref secret не является правом: live app/workspace/operation/destination grant, short lifetime, audited access, no raw logs. Для процесса, которому разрешён доступ к secret, локальные права/root и unmanaged traces остаются границей доверия. Output scanning не заменяет network sandbox.

### 3.5 Coding harness и точка исполнения

Первый кандидат — Claude Code, потому что существующий spike уже говорит на Anthropic protocol. Но номер версии/поддержанные hooks/proxy routes/API conditions фиксируются отдельным SP07 **до обещания совместимости**. Прямой вызов provider API и подписочные auth способы не смешиваются и не обходятся.

Обязательный способ интеграции должен одновременно:

1. перехватывать весь объявленный model-bound контекст, включая file reads/tool results/replayed args;
2. иметь enforcement до local tool execution с возможностью deny и typed replacement;
3. не сохранять real execution args в model history/remote traces;
4. обнаруживать неподдержанные tool paths и не давать обход через встроенный незавёрнутый Bash/Read/Edit;
5. сохранять требуемую protocol validity, включая opaque/signed blocks. Нельзя менять signed reasoning text и возвращать прежнюю signature. Если режим нельзя обработать с сохранением приватности и целостности, он disabled/unsupported; отсутствие видимого текста не доказательство отсутствия утечки.

Если конкретный harness не предоставляет этих границ, поддержка ограничивается integration mode с нашим registered executor/tools либо откладывается до адаптера; **нельзя выпускать transparent full protection, реализованную только сменой base_url**. Другие IDE/кодеры подключаются через тот же контракт, но каждый проходит свою compatibility suite.

## 4. Место в общем спринте и порядок реализации

**T12 идёт после базовых T01–T11 плюс T13 HITL/T14 документы и W27/C4.** C4 теперь означает «базовая платформа принята», а не финальную приёмку расширенного спринта. Claude integration и последующий Codex имеют отдельную приёмку; включение Codex в первый публичный **C5** остаётся OPEN-C01. Общая регрессия на новом артефакте обязательна после каждого принятого adapter. Исходные W27 gates не отменяются: W35 повторно проверяет платформу после добавления executor/adapters.

До C4 разрешены только contract/spike/test design coding-направления для раннего обнаружения критической несовместимости; реализацию production coding flow запускаем последней. Результат SP07 может потребовать версионированного изменения общего API: это согласуется с K-владельцем, не протаскивается через отдельный private API.

```text
T01–T11 + T13/T14 (W36–W44) → W27/C4 (базовая платформа)
  → T12.1/W28 → T12.2/W29 → T12.3/W30 → T12.4/W31
  → T12.5/W32 → T12.6/W33 → T12.7/W34 → T12.8/W35 (Claude accepted)
  → T12.9/W45 (Codex accepted); публичная граница C5 — OPEN-C01
```

### 4.1 SP07 — совместимость harness и executor substrate

**Первичная база подготовлена:** [сравнение HITL lifecycle](<research/harness-hitl-lifecycle.md>) отдельно описывает Claude CLI/settings hooks, Claude Agent SDK callback/defer, Codex app-server/hooks/SDK и установленный DSH. Это docs/source evidence, не выполненный SP07 и не обещание поддержать все три harness в первой версии. Выбор HITL08 пока открыт.

**Обязательные различия в spike:** долгий permission wait ≠ hook timeout ≠ command timeout; закрытие UI ≠ Stop ≠ process restart; обычный session resume ≠ durable deferred call. Claude callback может ждать indefinitely, а defer требует отдельного resume recheck; Codex warm reconnect replay не cold restart; DSH native pre-gate input rewriting запрещён. Hook failure/output-mask timeout не должны пропускать raw данные. Подробные experiment cases приведены в исследовании §7.

**Проверить:** current pinned Claude Code integration API, транспорт/auth constraints, pre-execution hook/registered tool replacement, state/checkpoint/tracing lifecycle, opaque signed blocks, process/file/network enforcement на выбранной OS. Целевые environments по CODING01 — Linux, macOS и Windows через WSL; каждый проверяется отдельно. Desktop macOS/WSL mounted Windows paths не считаются автоматически проверенными Linux container gate; native PowerShell исключён.

**Exit:** доказанные control points на synthetic local fixtures и зафиксированная матрица supported/unsupported. Ложный negative test (команда должна быть заблокирована, но выполнилась) делает spike RED. Если наблюдать execution boundary невозможно — выбранный режим не supported, меняем adapter topology, не ослабляем обещание.

### 4.2 Последовательные пакеты T12

| Шаг | Работа и выход | Depends on | Tests-first / гейты |
|---|---|---|---|
| T12.1 / W28 | Threat model, supported grammar/harness matrix, точные DTO/offset semantics, synthetic corpus и meaningful RED gates; закрыть SP07 | C4/W27 для production start; design до C4 допустим | AC01–AC12 определены, CP integration mapping; никакого ready только по docs |
| T12.2 / W29 | K10-A: exact coding mapping/provenance + execution plan validation + literal argv compilation, no shell reparse | W28, K03/K05/K06 | AC02/AC03/AC04; токены в синтаксисе/неизвестном контексте deny |
| T12.3 / W30 | K10-B: controlled local executor, workspace/file/process/network boundary, live consume, cleanup/cancel/output capture | W29, K02/K06/K09 | AC05/AC06/AC07; actual process side effects, race/revoke tests |
| T12.4 / W31 | Pinned Anthropic/coding-harness adapter, protected read/search, unsupported-tool refusal, two state views | W30, W17/W24 contracts | AC01/AC07/AC09, CP28/CP46/CP47 |
| T12.5 / W32 | Literal patch workflow со snapshot CAS/offset mapping, protected diff, explicit sandboxed test task profile | W31 | AC08; exact bytes/result tree oracle, stale preimage denial |
| T12.6 / W33 | Registered narrow secret-broker operation, approved network destination, transient credentials, no arbitrary Bash injection | W32, F07/F11/F22 | AC06/AC10; default no model/log/PII mapping, opt-in F24 по H02 отдельно; forbidden destination blocked |
| T12.7 / W34 | Единый UI профиль Coding: workspace/ops/capabilities, audit views, snippets/probe, limits/retention, no remote arbitrary shell UI | W33, F20 | AC11, CP04–CP06/CP42–CP43 |
| T12.8 / W35 | Claude coding acceptance, source/compiled/platform regressions, supported-host docs и packaging | W34 и все relevant core/H/DOCG | AC01–AC12 по Linux/macOS/WSL; не автоматическая приёмка Codex/C5 |
| T12.9 / W45 | Последующий Codex adapter, собственный capability profile и повторная общая регрессия | W35, Codex SP07 | AC13 + applicable AC01–AC12; release placement OPEN-C01 |

K10-A/B проектируются test-first до business implementation. Специализированная ownership не даёт права исправлять общий vault/envelope/authorization из coding-трека без владельца соответствующего K. Proposed write scopes: `prototype/pseudex/coding/`, отдельный thin harness adapter/executor distribution, coding fixtures/tests и UI feature module. Registry/Docker/entrypoint/schema changes интегрируются централизованно. Данные/лицензия ядра не копируются в SDK/executor; generic local executor не превращается в поставку proprietary recognizers.

## 5. AC01–AC13: обязательная самостоятельная приёмка

Все IDs — **новые proposed gates**, не уже запущенные тесты. Входы synthetic, без настоящих credentials/рабочих репозиториев. До implementation — fixtures, ожидаемый process/file outcome, controlled failure и RED. Реальный harness/OS/container gate нельзя заменить mock transport.

| Gate | Что ломаем/проверяем | Независимое доказательство |
|---|---|---|
| AC01 | Harness читает файл, вызывает tool, replay истории, protocol unknown/signed blocks | Wire spy + harness checkpoint/trace; unsupported block не проходит автоматически; transport integrity сохранена |
| AC02 | Exact path/search literal с Unicode/пробелами/разными регистрами/bytes | Значение у исполнителя совпадает байт-в-байт; неправильная канонизация/чужой mapping даёт RED |
| AC03 | Original содержит shell metacharacters; placeholder в command syntax | Фактический argv/side-effect oracle: значение только данные, никаких дополнительных операций; unsupported grammar denied |
| AC04 | Utility flag injection, variable/command substitution, nested language/eval, pipeline, binary replacement | Только разрешённая grammar/executable identity; добавление проверкой одной blacklist строки не проходит корпус |
| AC05 | Path traversal/symlink/hardlink/rename race/cwd switch | Доступ за workspace отсутствует у actual file operation, не только в log решения |
| AC06 | Permit replay/revoke/digest substitution, egress/destination mismatch | Handler не вызван; shared budget один consume; sandbox запрещает unmanaged выход |
| AC07 | Stdout/stderr split secret/PII, huge output, timeout и orphan child | Модель/trace не получают unchecked tail, process tree остановлено, buffer cap соблюдён |
| AC08 | Stale file preimage/offset drift/token в executable syntax/partial patch | Неверный snapshot не меняет файл; разрешённый literal patch даёт ожидаемое полное содержимое, originals вне edits сохранены |
| AC09 | Cross-project/session/workspace restored data и state pollution | Чужие mappings denied, checkpoint содержит только protected view, real execution copy не попадает в следующий model request |
| AC10 | Credential broker / default protection / explicit exception | Default no model/PII-map/log/result secret; intentional raw-key disclosure допускается только точным F24 opt-in (H02), replay/wrong destination не проходят; произвольный процесс credential не получает |
| AC11 | UI claim protection при absent executor/unsupported tool, смена policy/lease/expiry | Coverage честен; revoke/expiry fail-closed; snapshots/retention/privacy events совместимы с платформой |
| AC12 | Complete paired coding task + mutation + packaging | Успешный поиск/patch по одинаковому fixture с/без защиты, измеренная полезность/latency; injected wrong-value/leak/side-effect mutation делает отчёт RED |
| AC13 | Второй harness Codex, отдельно от Claude | Pinned actual mode/versions, approval/reconnect/cold restart/input-output/checkpoint tests на declared OS; невозможность input rewrite через approval reply не замалчивается. Общие safety/utility cases перепроверены |

Две независимые оси: **защита** (wire/trace/egress leaks и forbidden side effects) и **полезность** (найден правильный файл/строка, корректный patch, фактические test outcomes). Zero leakage через отказ всем задачам не полноценный успех. Корпус содержит безопасные команды, которые должны выполниться, и опасные/неподдержанные, которые должны быть отвергнуты.

Не обещать полную семантическую эквивалентность произвольной программы: supported subset фиксируется и расширяется только с новым corpus/gates. Automated fixtures обязательны; live coding-model paired runs требуют отдельного GO/бюджета и не нужны для написания предварительного test harness.

## 6. Интеграция в общее управление

- Один application типа `coding`, registered workspaces/executor identities и разрешённые профили; не новый независимый org/token root.
- Общая policy revision описывает data categories, exact transform mode, approved operations, allowed roots, network profile, limits, retention, required checks. Raw secret/cwd path claims из модели не authority.
- Граф UI показывает model ingress, file read, command execution, patch, tool results/checkpoints, сеть; каждый этап enforced/configured_unverified/unsupported. Наличие proxy не красит всю строку зелёным.
- Test corpus и exact originals используют общие sensitive storage/lifecycle contracts. Environment credentials/restore permits не входят в reports. Model token usage и billed protect не пересчитываются в число shell instructions.
- Совместимость coding с основной платформой F01–F22/F24/F25 проверяется заново. Нет обычных reversible SECRET PII mappings; scoped credential refs/authorised pending и opt-in one-use disclosure соответствуют F24, а не blanket no-storage assertion.

## 7. Открытые условия перед реализацией

Выбраны: coding последним, Claude→Codex, Linux/macOS/WSL, без native PowerShell; credentials через service/purpose и общий HITL, не ручной список всех tool names. Bash subset и exact file/context safety проектируются как K10 и проходят tests, а не объявляются свойствами одного proxy.

Не выбраны/не доказаны: exact native/SDK/hook mode каждого harness, cold resume contract после исследования, публикация Codex вместе с первым C5 или позже (OPEN-C01), low-level supported command grammar и resource budgets. Эти gaps перечислены в [общем контракте](<docs/tz-hitl-and-documents.md>), SP07 не заменён чтением документации.

Jev и самостоятельный semantic classifier R&D отменены. DSH изучен как пример lifecycle, но не добавлен обязательным третьим connector. В этой редакции не запускались code/model/paid integration tests.
