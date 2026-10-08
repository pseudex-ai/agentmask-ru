# HITL в реальных harness: Claude Code, Codex и DSH

**Назначение:** фактическая база для открытого решения HITL08. Владелец попросил изучить существующие механизмы, прежде чем выбирать pause/resume/retry. Это исследование документации и исходников, **не результат запущенных интеграционных тестов**. Coding остаётся завершающим T12; никакого решения о едином fallback за владельца не принято.

Связь: [реестр решений](<docs/decisions-product-control-plane.md>), [coding-трек/SP07](<docs/tz-ai-coding-track.md>), [общий план](<docs/plan-product-control-plane-sprint.md>).

## 1. Главное исправление исходной постановки

**Человек может отвечать долго без истечения таймаута исполняемой команды, если команда ещё не была запущена, а harness действительно ждёт permission.** Но ожидание permission, выполнение hook, работа subprocess и сохранение сессии — разные механизмы.

Ранее предложенные универсальные варианты «любой timeout уничтожает старое ожидание» или «любой сохранённый запрос можно продолжить после рестарта» неверны. В inspected Codex server обычный approval переживает отключение WebSocket-клиента в том же процессе. В Claude SDK permission callback может ждать неопределённо, а `defer` отдельно предназначен для сохранения отложенного вызова. В DSH закрытие страницы не равно остановке host.

Нужно различать:

| Событие | Что выясняем, а не предполагаем |
|---|---|
| Пользователь долго не отвечает | Есть ли deadline именно permission callback? |
| Истёк hook timeout | Fail-closed, no-decision или normal permission fallback? |
| Истёк timeout Bash | Была ли уже запущена команда; завершена/отменена/переведена в background? |
| Закрылась вкладка | Жив ли backend и его pending callback? |
| Переподключился transport | Есть ли replay pending requests и сохраняются ли IDs? |
| Пользователь нажал Stop | Как отменяются именно pending permissions и side effects? |
| Процесс умер | Что durable: transcript, deferred call, approval callback или только история? |
| Открыли сохранённую сессию | Это продолжение разговора или восстановление того же tool invocation? |

Карточка Pseudex хранится по выбранной пользователем политике; она сама не определяет жизнеспособность upstream waiter. Нельзя приравнять «approved в нашей БД» к «tool выполнен».

## 2. Достоверность и версии

- **DOC:** прямое описание official API. Проверяет объявленный контракт, не поведение установленного бинарника.
- **SRC:** чтение реализации конкретной версии/commit. Это не универсальная гарантия любых releases.
- **ISSUE:** сторонний воспроизводимый report в официальном репозитории, не подтверждённый нами баг текущей версии.
- **TEST:** в этой работе **не выполнялись** модельные, paid или реальные tool lifecycle прогоны. Любой обещанный production behavior требует SP07.

Claude: текущие official Code/Agent SDK docs; прочитанный официальный [changelog](https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md) начинается с 2.1.294. Это не установленная у пользователя версия. Min-version для каждого поля и platform/CLI-vs-SDK комбинации должен фиксироваться при spike.

Codex: [upstream commit](https://api.github.com/repos/openai/codex/commits/8c818cbed4bc83d30f5d515674b809646fe2676d) `8c818cbed4bc83d30f5d515674b809646fe2676d` (2026-10-08) плюс release docs. Main source может опережать релиз; docs это прямо предупреждают.

DSH: установленный [package.json](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/package.json#L1-L4>), `0.1.7-rc.2`; source — shipped JS/d.ts в локальной установке, не заявление о текущем upstream main.

## 3. Claude Code: нельзя смешивать три поверхности

### 3.1 Обычные CLI/settings command/HTTP hooks

**DOC:** [hooks reference](https://code.claude.com/docs/en/hooks.md) описывает `PreToolUse` с allow/deny/ask/defer, `updatedInput`, `PermissionRequest`, а также подмену tool output через `PostToolUse`. Async hooks не служат synchronous decision gate.

Критически важен [раздел Timeouts](https://code.claude.com/docs/en/hooks#timeouts): timed-out **command/http/mcp_tool PreToolUse** не запрещает tool сам по себе; call продолжает обычный permission flow. Invalid/non-blocking hook failure также не равно deny. Следовательно «отправить approval request в Pseudex и бесконечно ждать в HTTP hook» — не доказанный fail-closed контракт.

`PermissionRequest` не тождественен PreToolUse: запускается на запросе разрешения, а не автоматически на любом вызове. Нельзя использовать обычный success/no-decision/timeout как implicit Pseudex approval. Должен быть explicit enforcement path с отдельно проверенным поведением при отсутствии ответа.

### 3.2 Agent SDK: живое ожидание человека

**DOC:** [Handle approvals and user input](https://code.claude.com/docs/en/agent-sdk/user-input.md) явно говорит: `canUseTool` callback может оставаться pending indefinitely; выполнение paused до его результата. Это **не** обычный короткий hook timeout.

Пока callback и процесс живы:

```text
Модель уже предложила tool call
→ canUseTool ожидает решения нашего приложения
→ человек отвечает в нашей UI
→ callback возвращает allow/deny, возможно updatedInput
→ разрешённый tool запускается
→ обычный agent loop получает результат
```

Чтобы лишь дождаться разрешения, модель не обязана повторно генерировать команду. Но после tool result дальнейший loop естественно может сделать новый LLM call — это обычное продолжение задачи, не повтор из-за approval.

**Ограничение coverage:** auto-approved tools могут вообще не попасть в canUseTool. [Permissions](https://code.claude.com/docs/en/agent-sdk/permissions.md) задаёт порядок hooks → deny → ask → mode → allow → callback. Чтобы обязательная проверка покрывала все нужные tool calls, недостаточно установить callback и разрешить tools другим способом.

### 3.3 SDK hook callback: другой timeout

**DOC:** [Agent SDK hooks](https://code.claude.com/docs/en/agent-sdk/hooks.md) описывает timeout у HookMatcher (для большинства events default 600s). Pending **PreToolUse SDK callback** по timeout не выполняет tool; модель получает error result, turn может продолжиться. В документированной новой версии interrupt pending callback также отменяет pending call; более старые версии отличались.

Для **PostToolUse** timeout текущая документация говорит о сохранении исходного tool result и продолжении. Значит, output masking hook, который просто упал/не ответил, не обеспечивает наше обещание «в модель не попал raw результат». Нужен proof именно before-model projection при всех failures.

### 3.4 `defer`: отдельный путь для долгой паузы и завершения процесса

**DOC:** [user-input](https://code.claude.com/docs/en/agent-sdk/user-input.md) прямо рекомендует PreToolUse `defer`, если человек может отвечать дольше допустимого lifetime процесса: процесс может закончиться и позже возобновиться из persisted session. [SDK hooks](https://code.claude.com/docs/en/agent-sdk/hooks.md) указывает `stop_reason: tool_deferred`; это не обычная отмена и не простое сохранение истории.

Особенно важно: с `permissionDecision: defer` поле `updatedInput` **игнорируется**. Нельзя одновременно записать восстановленный input через defer и считать его будущим execution payload. Сначала defer; на supported resume путь должен снова подтвердить актуальный input/permission, и это проверяется отдельным gate.

Подробные ограничения native CLI defer, batch/parallel tool calls и unattended resume не подтверждены выполненным тестом. Наличие этой возможности доказано official SDK docs, а универсальность для всех CLI режимов — нет.

**ISSUE, не наш замер:** [Python SDK #993](https://github.com/anthropics/claude-agent-sdk-python/issues/993) сообщает для SDK 0.2.87 / bundled CLI 2.1.150, что deferred resume мог выполнить call без повторного in-process PreToolUse callback; settings-based command hook в том же report работал иначе. Issue на момент чтения открыт, независимого подтверждения текущей версии нет. Это готовый **негативный тест-кандидат**, а не основание объявить все версии сломанными.

### 3.5 Обычный resume не равен deferred-call resume

**DOC:** [Sessions](https://code.claude.com/docs/en/agent-sdk/sessions.md): session сохраняет prompt/tool calls/results/conversation, не filesystem. `resume`/`continue` возвращают разговор после restart. Из этого не следует восстановление любого произвольного pending canUseTool callback. Durable deferred mechanism обсуждается отдельно выше.

**Практическая граница:** SDK — наш программный host с callback, а independently launched native CLI — другой способ интеграции. Поддержанный API callback не означает, что можно подключить его к любому уже запущенному CLI одной настройкой proxy URL.

## 4. Codex: approval server request, reconnect и cold restart

### 4.1 Документированный протокол

**DOC:** [App Server](https://learn.chatgpt.com/docs/app-server.md) — двунаправленный JSON-RPC, `initialize`/`initialized` на connection, thread/turn/item отдельны. Stdio JSONL — default; WebSocket transport в docs experimental/unsupported. Нельзя молча считать такой transport production SLA.

Обычный flow:

```text
item/started
→ item/commandExecution/requestApproval либо item/fileChange/requestApproval
→ client response с тем же RPC id и решением
→ serverRequest/resolved
→ item/completed с результатом операции
```

Решения accept/acceptForSession/decline/cancel и supported amendment variants зависят от availableDecisions. **Approval response не произвольный replacement args/patch DTO.** Proposed file preview может приходить на item, а не внутри approval message. Approval triggers зависят от policy; не каждый tool обязательно спрашивает.

### 4.2 Что реально сохраняет текущий server source

**SRC** pinned commit:

| Событие | Проверенная реализационная семантика |
|---|---|
| Потеря WebSocket-клиента | Обычные pending requests/callbacks остаются в памяти работающего app-server |
| Reconnect + initialize + warm thread/resume | Replay pending requests с исходными RPC IDs; одного открытия socket недостаточно для этого contract |
| Другой клиент ответил первым | Callback снимается; duplicate/unknown response не новое одобрение. Нельзя предполагать exclusive reviewer ownership |
| Turn lifecycle complete/abort/start cleanup | Pending requests соответствующего thread отменяются; resolved notification не означает successful execution |
| Last subscriber ушёл | Не обязательный immediate shutdown; unload зависит также от inactivity/grace. Живой pending approval — не то же, что завершённая неактивная session |
| Stdio closure | Single-client processor выходит и запускает shutdown; не аналог потери одного WS viewer |
| Process restart/cold thread resume | Memory callbacks и counter не восстанавливаются; сохранённый разговор не старый живой permission waiter |

Источники SRC: [outgoing_message](https://raw.githubusercontent.com/openai/codex/8c818cbed4bc83d30f5d515674b809646fe2676d/codex-rs/app-server/src/outgoing_message.rs), [thread lifecycle](https://raw.githubusercontent.com/openai/codex/8c818cbed4bc83d30f5d515674b809646fe2676d/codex-rs/app-server/src/request_processors/thread_lifecycle.rs), [approval/turn events](https://raw.githubusercontent.com/openai/codex/8c818cbed4bc83d30f5d515674b809646fe2676d/codex-rs/app-server/src/bespoke_event_handling.rs), [server transport/shutdown](https://raw.githubusercontent.com/openai/codex/8c818cbed4bc83d30f5d515674b809646fe2676d/codex-rs/app-server/src/lib.rs), [cold daemon recovery](https://raw.githubusercontent.com/openai/codex/8c818cbed4bc83d30f5d515674b809646fe2676d/codex-rs/app-server/src/daemon_thread_recovery.rs).

RPC IDs — increasing process-local integers; новый process может повторить старый ID. Correlation нужна как минимум по backend generation + thread + turn + item + RPC ID. No local timer в inspected ordinary approval waiter — **не SLA бесконечного ожидания**. Connection-owned native verification ceremonies — отдельная категория, не ordinary replayed tool approvals.

### 4.3 SDK и hooks — не одно и то же с app-server

**SRC:** [TypeScript SDK execution](https://raw.githubusercontent.com/openai/codex/8c818cbed4bc83d30f5d515674b809646fe2676d/sdk/typescript/src/exec.ts) запускает CLI exec, пишет prompt и закрывает stdin, читает output. Approval policy option не означает interactive callback channel; `resumeThread` — не восстановление server-request callback. [SDK README](https://raw.githubusercontent.com/openai/codex/8c818cbed4bc83d30f5d515674b809646fe2676d/sdk/typescript/README.md).

**DOC:** актуальные [Codex hooks](https://learn.chatgpt.com/docs/hooks.md) уже поддерживают PreToolUse `updatedInput` для ряда local tools. Поэтому утверждать «Codex вообще не умеет переписать tool args» неверно. Но **app-server approval response** сам по себе по-прежнему decision-only.

- PreToolUse может deny/rewrite supported local function calls; hosted tools исключены, specialized paths могут opt out, `write_stdin` не проходит новый PreToolUse.
- PermissionRequest — allow/deny либо normal prompt; не вызывается там, где approval не требуется. Его updatedInput не supported.
- PostToolUse может заменить model-facing результат blocking feedback; это не undo side effect и не универсальный typed sanitized-output replacement. `updatedMCPToolOutput` не supported в описанном контракте.
- Ошибки/timeout/часть malformed hook results могут продолжить исходную операцию. Async hooks не blocking boundary.

**Вывод:** hooks и approval notifications полезны, но полный Pseudex privacy loop не доказан самим фактом их наличия. Коммерческие/auth условия способа интеграции, указанные в App Server docs, также требуют отдельной проверки, не подразумеваются из открытого исходника.

## 5. DSH 0.1.7-rc.2: что видно в установленном коде

### 5.1 Живое ожидание переживает закрытие страницы

**SRC:** [gateway:801–824](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-api-gateway/lib/index.js#L801-L824>) при новом Remote event клиенте повторно отдаёт `pendingRemoteEvents`. [846–889](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-api-gateway/lib/index.js#L846-L889>) создаёт pending entry и при отсутствии подключённых клиентов; timer в этой ветке не найден. [914–918](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-api-gateway/lib/index.js#L914-L918>) при disconnect удаляет delivery/client, но не host pending map.

Значит, **закрытая вкладка и отсутствие зарегистрированного approval answerer — разные ситуации**. Зарегистрированный bridge без viewer может продолжать ожидать. Пока host context/operation signal живы, reconnect может получить тот же pending event. Нельзя обещать это после убийства backend только на основании GUI reconnect.

### 5.2 Approval и input/output transformation разделены

**SRC:** [PreToolDecision](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-tools/lib/types/index.d.ts#L436-L460>): allow/deny/cancel/ask; ask запускает tool только после allowed-once. **Input rewriting исключён контрактом**, потому что args уже logged/presented. Следовательно generic pre-execute permission hook нельзя считать готовым каналом detok real args.

**SRC:** [postExecute](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-tools/lib/index.js#L3503-L3531>) допускает замену одной projection (`content` либо typed `value`) или block. Возможность post replacement не исправляет side effects и не доказывает, что raw data не попали в другой trace/observer до этого шага.

### 5.3 Stop, restart, audit и таймауты

**SRC:** [реальная pre-dispatch цепочка](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-tools/lib/index.js#L3214-L3273>) идёт через pre-execute → approval → guards → cancellation recheck → dispatch. [Approval service](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-user-approval/lib/index.js#L128-L188>) разрешает только `allowed-once`; missing/throwing/invalid answerer — unavailable, abort — cancelled. В approval waiter не найден собственный deadline. Это свойство native approval, не любого стороннего hook.

**SRC:** [agent dispose](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js#L1662-L1687>) отменяет, ждёт idle, освобождает scope/persistence; [API stop](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-api-session-controller/lib/index.js#L990-L999>) вызывает cancel. Это не обычное закрытие браузерного соединения. Remote context release/signal abort снимает pending event.

**SRC:** [resume](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-agent-loop/lib/index.js#L1927-L1955>) читает persisted events и добавляет interruptedTurnClosers, а не оживляет старую Promise. [Recovery contract](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-session/lib/index.js#L725-L754>) различает `TOOL_OUTCOME_UNKNOWN` и `TOOL_NOT_STARTED`; retry — новый execution. Old outcome unknown запрещает слепое повторение side effects. [JSONL batching](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-session-persistence-jsonl/lib/index.js#L179-L218>) использует buffer/200ms timer с flush/drain; не гарантирует сохранение ещё не flushed events при crash. Durable audit не равно durable pending interaction.

**SRC:** [Bash execution timeout](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-tool-bash/lib/index.js#L421-L474>) может перевести уже начатый процесс в background job; preparation/cancellation отличаются. [Cooperative tool timeout](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-tool-call-timeout-policy/lib/index.js#L115-L139>) ставится после pre-execute/approval. Не переносить эти deadlines на время ответа человека.

### 5.4 Compatibility hook не равен native approval

**SRC:** [Claude hook bridge](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-hooks-claude-code/lib/index.js#L179-L190>) игнорирует `updatedInput`; native input contract выше остаётся неизменным. [Hook protocol runner](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-hook-protocol/lib/index.js#L169-L210>) задаёт default command timeout 600000ms и превращает infrastructure failures в neutral outcome. [Parsing](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-hook-protocol/lib/index.js#L102-L125>) принимает blocking exit2/valid structured decisions; [default merge](</opt/homebrew/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-hook-protocol/lib/index.js#L221-L245>) не превращает отсутствие решения в обязательный deny.

Следовательно command-hook timeout/runner error нельзя считать native fail-closed approval. Для Pseudex input detok потребуется поддержанная другая integration seam/explicit wrapper либо отдельно согласованное изменение harness; написать `updatedInput` в совместимый hook недостаточно.

**Не проверено:** какие optional plugins включены в текущем running DSH, сторонние answerer deadlines, UI draft persistence после full reload, runtime kill/reconnect и все пути записи raw data до post hook. Факты source не объявляются проведённым пентестом.

## 6. Что уже можно сопоставить

| Сценарий | Claude Agent SDK | Codex app-server | DSH local Web GUI |
|---|---|---|---|
| Долго ждать человека при живом backend | Explicit DOC indefinite canUseTool callback, если call действительно туда попал | SRC ordinary waiter без собственного timer; не universal lifetime guarantee | SRC pending Remote event без timer в inspected path |
| Вкладка/клиент отключился, backend жив | Зависит от host приложения; сам SDK не определяет browser disconnect | Warm reconnect/resume replay ordinary approvals в inspected source | Remote bridge повторно доставляет pending после reconnect |
| Tool/hook timeout | Callback approval и hook timeout различны; CLI hooks и SDK hooks различаются | Hook error/timeout не equivalent native approval deny | Bash execution timeout не permission timeout |
| Backend process restart | Есть documented deferred-call path; обычный conversation resume отдельно | Cold resume не возвращает old in-memory RPC callbacks | SRC resume закрывает interrupted calls; старый pending tool не возобновляется, повтор — новый execution |
| Подмена tool input | DOC updatedInput в supported hooks/callbacks; defer его игнорирует | DOC PreToolUse rewrite; app-server approval response не rewrite | Native PreToolDecision input rewrite запрещён |
| Проверка/подмена результата до модели | DOC updatedToolOutput, но PostToolUse timeout сохраняет original result | Blocking feedback projection, ограничения coverage; observer event не gate | Native post replacement content/value; порядок других observers нужно проверить |

**Важное следствие:** общий UI Pseudex и единая policy не требуют одинаковой внутренней механики всех connectors. Реальные adapters могут использовать разные native protocols. Но это ещё не согласованный выбор, какой adapter выпускается первым.

## 7. Проверки SP07, которые теперь следуют из фактов

Предлагаемые experiment cases, не выполненные тесты и не новая автоматически утверждённая функциональность:

1. **Живое ожидание:** one harmless tool call + approval через достаточно долгую паузу; marker создаётся ровно после allow, без повторной генерации исходного call. Отдельно измерить timeout permission/hook/executor.
2. **Отключение viewer:** закрыть UI transport, оставить backend, подключиться и восстановить тот же pending item; duplicate clicks не повторяют execution.
3. **Interrupt:** Stop во время approval; поздний ответ не вызывает side effect. Cancel не равен decline.
4. **Process restart:** уничтожить backend, затем проверить native recovery. Old IDs не отвечают новым requests. Claude defer отдельно от обычного callback, Codex warm отдельно cold.
5. **Recheck после defer:** deny/revoked policy при resume должен победить прежний pending call. Python SDK report #993 становится negative regression fixture для pinned version.
6. **Hook outage:** timeout/crash/malformed/absent hook. Проверить, что наша выбранная enforcement topology не пропускает call/result по default behavior harness.
7. **Coverage:** auto-approved/read-only tools, subagents, hosted tools, write_stdin, параллельные calls и unknown tool paths. Непроверенные paths marked unsupported, не green.
8. **Input transformation:** выполнить безопасный вызов с synthetic placeholder; actual argv получает expected exact value, а model state/transcript/logs не получают восстановленный оригинал. Сам `updatedInput` этого не доказывает.
9. **Output transformation failure:** raw canary в tool stdout, masker timeout → canary не должен попасть в model request/checkpoint через fail-open PostToolUse.
10. **Receipt/consent identity:** permit bound to current backend/session/call/input; если cwd/files/policy изменились, old approval не переносится незаметно.
11. **No unwanted background action:** approval после окончательной отмены/утраты waiter не выполняет новую команду само по себе; статус исполнения отдельно от статуса решения.
12. **Корректный terminal status:** request resolved, denied, cancelled, expired, disconnected, deferred, resumed и actual execution success наблюдаются раздельно; API не возвращает «сделано» от одного клика allow.

Все сначала на synthetic local fixture, exact version/transport/OS фиксируются. Никаких secrets/prod operations/paid model runs без отдельного GO. Source-reading этот этап не заменяет.

## 8. Что остаётся решением владельца после исследования

- Какой **конкретный integration mode** делаем первым: native CLI hooks/defer, controlled SDK host, app-server client либо явный registered tool adapter? Это не взаимозаменяемые обещания.
- Где обязателен durable same-call resume, а где достаточно live approval и понятного reconnect/explicit retry? Теперь варианты должны называться с конкретным harness/версией.
- Как показывать карточку, если Pseudex хранит approval, но upstream request больше не actionable? Не предлагать универсальный TTL как замену этого решения.
- Нужно ли поддерживать экспериментальный транспорт/API в первом release и кто отвечает за собственный runtime bridge?

**Не изменяем уже выбранное:** один инстанс/консоль, две роли с выдаваемыми правами, HITL queue не исчезает автоматически по умолчанию, safe preview, encrypted pending payload, coding в конце спринта, Jev отменён. Готовый connector/support claim появляется только после actual SP07 gates и отдельного выбора, а не после этой сравнительной таблицы.
