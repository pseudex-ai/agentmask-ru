# DoubleUp × Pseudex: четыре перехода и полные диалоги

Срез: **24.10.2026 · ongoing / in progress**. Локальная реализация, не релиз,
не завершённое сравнение агентов и не разрешение dev/prod-выкладки. Здесь нет
клиентского plaintext, source screenshots, имён людей, ключей или URI источника.
[Runbook](<../docs/integration-doubleup-local.md>) — текущий контракт;
[отчёт 23 октября](<2026-10-23-doubleup-local-pilot.md>) — предыдущий checkpoint,
не доказательство текущего полного прогона.

## Актуальный поздний срез: три трека

Ниже сохранён ход реализации; ранние «dry-testing/ещё исполняются» — исторические
этапы, не текущий статус. По последнему указанию владельца:

1. **UI исправлен:** link labels/email, persistent marks vs60s details, human attempt
   labels; DeepSeek Flash138 tests + Lead2 auth/render-transition regressions = **140/140**,
   tsc/lint exit0, реальный браузер27 checks и обновлённый four-hop gate. Сырые ID только
   в collapsed технических деталях; послеTTL hover делает только read-only GET.
2. **UUID только исследован:** [конкретная причина, HEAD repro и конфигурация](<2026-10-24-uuid-residual-research.md>).
   Это ложное NAME ownership после удаления цифр, не регрессия UI/OUT receipts.
3. **Выборка готова:** [21 полный исходный диалог /183 пользовательских хода](<2026-10-24-real-sensitive-dialogues.md>),
   15 с контактами в source tools,12 с совпадающими пользовательскими контактами
   в arguments/results. 2 кандидата исключены,7 недочитанных не объявлены полными.
   Это архив источника, не synthetic demo, не новый model replay и не gold labels.

Paid pilot ранее: none8/8, builtin8/8 (один явно разрешённый повтор послеunknown),
Pseudex остановился ВНУТРИ первого пользовательского хода после8 tool steps.
Это одна остановка, **не8 неудачных ответов**; остальные7 ходов P не запускались.
Учтено/зарезервировано **$2.7971142**, остаток **$7.2028858**; gateway сейчасfixture.
Ни текущая подборка, ни UI/UUID subagent-треки новых платных model calls не делают.
Исходный остановленный результат сохранён; никакой task-success/equivalence/«Pлучше»
оценки нет. Baked backend четырёх переходов ранее проверен поHTTP без source bind;
source-original read-only guard дополнительно проверен actualHTTP409 и3 tests.

## 1. Что уже подтверждено, а что ещё нет

| Утверждение | Основание | Граница |
|---|---|---|
| Четыре фактических перехода имеют receipts и привязки | actual source/compiled HTTP, authenticated web query, реальный ToolExecutor и браузер | synthetic fixture, $0, не качество модели |
| OUT показывает реальные операции восстановления | opt-in v2 на accepted splice/write hooks | не provider streaming и не произвольный lexical diff |
| В чате видны actual peer forms | ID + whole-text/hash, IN/OUT offsets, настоящий MessageBubbleV2/tool menu | не canonical vault lookup; unsupported Markdown остаётся plain |
| Есть шесть полных сохранённых ROOT-историй | source Mongo, ordered IDs, ранний пустой ROOT без parent, selected compactions=0 | не «никогда ничего не удалялось» и не transactional snapshot |
| Application Langfuse присоединён ко всем шести | public manifest: 274 traces /3 201 observations | не шесть независимых статистических случаев и не полная production-среда |
| Безопасные локальные ресурсы готовы | три ready text-only случая, десять source contracts, query-dependent mirrors и Docker executor | только эта замороженная среда, не внешние клиентские эффекты |
| Выполнен dry causal protocol | восемь исходных пользовательских ходов × три режима: 48 scripted model steps, 24 настоящих запуска Python | $0, не качество модели |
| Начат paid causal replay | первый восьмиходовый случай; плечо none прошло все 8 ходов, builtin/pseudex ещё исполняются | **полный трёхсторонний итог пока не доказан** |

Новый полный backend: **6 221 passed /36 skipped, 226.78 s**, без внешней сети;
frontend: **125/125 tests, tsc и lint exit 0** (lint сообщает предупреждения).
Multiline source positions и mobile tap/абсолютный TTL проверены. Новый backend
image собран; HTTP-проверка обновлённого baked image ещё предстоит. Нет manual
PII labels, precision/recall, equivalence, процента task success, «агент лучше» или
«цель завершена». `Complete` у replay означает обработанные пользовательские ходы,
а не успешность бизнес-задачи.

## 2. Движок: IN v1 сохранён, OUT v2 добавлен явно

Новый [restoration](<../prototype/pseudex/restoration.py>) подключён к
[redact](<../prototype/pseudex/redact.py>), [envelope](<../prototype/pseudex/envelope.py>),
[JSON boundaries](<../prototype/pseudex/json_fields.py>) и обеим поверхностям —
[sidecar](<../prototype/pseudex/service.py>)/[proxy](<../prototype/pseudex/proxy.py>).
Mask receipt v1 не менялся. OUT включается opt-in, default shapes прежние.

V2 несёт operation=restore, coverage=semantic_transformations, Unicode codepoint
offsets, semantic_complete, lexical_complete, limitations и replacements:
occurrence_id/path/source_start/end/output_start/end, type=RESTORATION,
kind=restoration, granularity=span|json_leaf, optional leaf_path. **В metadata нет
raw/restored literals, shown или base_token; они не добавляются в cache/audit.**
Пары для просмотра получаются из отдельных авторизованных точных snapshots.

Prose регистрируется только после принятой изменившей текст splice-операции;
JSON — на фактической записи изменившегося leaf. Scalar ranges лексические,
**включая кавычки строк**, а не приблизительные позиции decoded value.
Whitespace/escape normalization сама по себе не semantic restoration. Поэтому
semantic_complete может быть true при lexical_complete=false. Duplicate keys,
untracked changed leaves и недоказанная привязка не становятся «полной» квитанцией.

Actual `/unmask` paths начинаются `/response/choices/{ARRAY POSITION}/message/…`:
позиция массива, не значение choice.index. Standalone `/unmask_arguments` —
`/arguments/{i}`. Host snapshots укоренены в provider response: при чтении снимается
**только фиксированный** `/response` prefix; исходный engine path в сохранённом
receipt не переписывается. Новые manual proxy routes требуют gateway-auth;
OpenAI `/v1/chat/completions` JSON не изменён. Provider-streaming receipts unsupported.

## 3. Host provenance: операция, доставка и эффект — разные факты

Новая backend-связка server-owned IDs + exact whole text/hash передаётся через
несериализуемые атрибуты _WireMessage в **обоих** converters. Posted JSON не может
создать эти Python-атрибуты. Преобразованный/обрезанный текст без точной проекции
не получает привязку от похожей строки. Root request ID хранится отдельно от
attempt ID. SSE start передаёт pseudex_input_messages с input_index/message_id;
финальный ответ сохраняет actual message ID, а не случайно созданный browser ID.

Для tool call сохраняются call/dispatch/execution IDs. Raw tool result не равен
trimmed forwarded ToolMessage. Событие подготовки не доказывает forwarding:
только последующий actual ModelRequest с тем же ID/text/hash подтверждает, что
именно эта форма вошла в запрос. Все реальные attempts остаются доступны;
исторические записи не backfill-ятся по text/time.

Новый `GET /api/v1/pseudex/inspections/highlights?thread_id=…` проверяет текущего
owner/superadmin **до decrypt**, отвечает no-store, различает evidence statuses
verified/no_op/incomplete/not_recorded, delivery status и execution outcome.
Пределы: 100 attempts, 400 messages, 400 tools, 128 KiB/entry и 512 KiB общего
бюджета entries. Oversize entries **пропускаются**, не режутся с сохранением
ложных offsets/hash. Это bounded projection, не весь transcript и не PII recall.

Локальный synthetic helper доступен только при pilot flag + DB doubleup_pilot +
org doubleup-pilot. Реестр/карта gated; внешних эффектов у helper нет. Default
nonpilot поведение не изменено. Точные client source aliases — в
[runbook](<../docs/integration-doubleup-local.md#карта-клиентских-исходников-read-only-aliases>),
не в engine import graph wiki.

## 4. Реальный frontend, а не отдельный макет

В actual MessageBubbleV2 и странице подключены API/SSE/types, session provider,
tool-hop views и шесть файлов highlighter, включая positions. Маска жёлтая,
восстановление teal; actual peer snapshot открывается hover/focus/tap. Codepoint
координаты явно переводятся в UTF-16. Factory идёт последним rehype plugin;
полномочие на peer-value display — WeakMap identity HAST node, **не** HTML string
и не подделываемый data-attribute.

Code/math/link labels/destinations, cross-node ranges и transformed text не
объявляются поддержанными: plain fallback сообщает ограничение. Positions
сохраняет точные soft-line offsets до remarkBreaks и связывает только явно
порождённый после `br` newline с его исходным диапазоном перед rehypeRaw. Проверка
многострочного текста после bold/emoji/autolink проходит без угадывания по значениям.

Session scope включает auth/context org/user/path/token epoch, запросы no-store.
Абсолютный TTL 60 секунд, hide/pagehide/context clear и abort in-flight реализованы;
mobile first/second tap и удаление открытого tooltip/всех marks по TTL прошли
реальный браузерный gate с fast-forward clock. Canonical reveal остаётся отдельным явным
аудируемым действием, не hover. PII/counters/details не пишутся в localStorage;
dev raw chat logs выключены только в pilot, не глобально.

## 5. Проверенные артефакты и результаты

Engine snapshot: `1265a266c328f6b1e05f9cc1577550878cfc3e33738f03ee3c06274715642ba1`.
Source image: `45dc6170bf493ef5bf3a9eb78a2213bb69aad26460554ce6a41514fbd60c5c98`.
Это идентификаторы локальных артефактов, не release tags.

| Проверка | Actual result | Что не следует из зелёного |
|---|---|---|
| [HTTP gate](<../deploy/doubleup-pilot/http_inspection_gate.py>) | source :18862 и compiled :18863: all_four_hops, OUT v2, no literals, default shape/auth/reveal — pass | не обновлённый полный release gate |
| [Source report](<../deploy/doubleup-pilot/.state/http-inspection-gate.json>), [compiled report](<../deploy/doubleup-pilot/.state/http-inspection-gate-compiled.json>) | synthetic_only, provider_calls=0, paid_usd=0 | не live agent result |
| [Four-hop web gate](<../deploy/doubleup-pilot/four_hop_web_gate.py>) / [report](<../deploy/doubleup-pilot/.state/four-hop-web-gate.json>) | authenticated query 200; actual ToolExecutor; SSE input/final IDs; все четыре вида marks | scripted provider, не quality score |
| [Browser gate](<../deploy/doubleup-pilot/browser_four_hop_gate.py>) / [report](<../deploy/doubleup-pilot/.state/browser-four-hop-gate.json>) | actual input send, hover/focus, обе tool marks, toggle erase; mobile first/second tap; TTL удаляет открытый peer tooltip и marks | synthetic fixture, не PII recall |
| Source engine focused | 6 restoration /7 mask /33 address проверок — pass | не полный engine battery |
| Backend focused | worker 192 passed; parent four-hop + integration-map 107 passed, 1 **существующий** skip | не новый полный backend прогон; skip не добавлялся |
| Full backend | 6 221 passed /36 skipped /35 warnings, 226.78 s | skip-условия окружения не равны новому покрытию; бизнес-задачи не оценены |
| Frontend | 125/125 Node tests; tsc/lint exit 0; focused34/34 | production frontend build не заявлен; lint warnings остаются |
| Mongo normalization/intake | 28 +65 =93 passed | не manual PII labels |
| Replay tool mirrors | 36 passed | не все шесть production environments |
| Docker executor | 19 checks passed на genuine Docker | не production hostile-code certification |
| Новые budget checks | 31 passed | не новый spend и не запуск live |

Synthetic screenshots: [user highlight](<../deploy/doubleup-pilot/.state/browser/inline-user-highlight.png>),
[assistant highlight](<../deploy/doubleup-pilot/.state/browser/inline-assistant-highlight.png>),
[tool panel](<../deploy/doubleup-pilot/.state/browser/four-hop-tool-panel.png>).
Снимки обновлены с отключённой анимацией capture; [mobile](<../deploy/doubleup-pilot/.state/browser/inline-mobile-highlight.png>) также проверен. Это synthetic, не клиентские данные.

Демонстрация: [synthetic four-hop chat](<http://127.0.0.1:18880/doubleup-pilot/assistantnew/1f55257d-83f5-51a9-88e1-e0eb11442855?thread=41269e0d-008d-521e-ab54-b8de46e5820a>).
Credentials не публикуются; private browser config разрешено открывать только
владельцу по [path](<../deploy/doubleup-pilot/.state/runtime/browser.json>).

**6 194 baseline и старые 110 tests относятся к предыдущему checkpoint.** Текущий
full-suite результат приведён отдельно выше. Новый baked backend image:
`sha256:6a743f25831493671b2593c4b71491ee5e2cbc18b47a2716e2617a388001c891`,
source fingerprint `1c3f681cf6800077fe83949dfddf29250933b12555ccc6bcc6e80c25b20adf44`,
25 Python overlays, без runtime data/dirty docs и без push. HTTP gate этого image
пока не запускался: shared local model connector занят paid replay, и fixture
gate не должен нечаянно превращаться в платный вызов.

## 6. Исправленный корпус: полные CHATS, не 200 trace fragments

Mongo — authoritative ROOT, application Langfuse — внутренние model/tool hops.
Первоначальная группировка по gateway Langfuse была ошибочной для этой цели.
Локальный Langfuse profile относится к gateway project; backend GitOps LANGFUSE
keys указывают **другой application project**, где 8 637 видимых traces и session
IDs равны actual thread UUID. Values/host URI/имена в этот документ не переносятся.

Mongo read-only разрешён пользователем отдельно. Intake делает только find/aggregate;
**не MongoSaver**, чей constructor создаёт indexes. Credentials остаются в RAM,
stdin/log-driver-none на узком source-resource path, без DDL. Более ранняя случайная
печать source credentials была раскрыта владельцу; значения не повторяются,
production rotation не выполнялась. Это открытый operational факт, не заявление
«инцидента не было».

Inventory: 2 231 threads, 53 734 message documents, 28 478 graph states,
19 compactions. Выбраны шесть encrypted raw thread exports в immutable RunStore
mongo-full-chats-local-pilot-v2. Raw canonical EJSON сохраняется отдельно.
[ROOT normalizer](<../prototype/bench/doubleup/mongo_dialogues.py>) использует static
message allowlist msgpack/JSON revival, не arbitrary imports/pickle. Installed
serde, несмотря на warning, не поддерживал allowed_objects; безопасный explicit
reviver нужен именно поэтому.

| Selected ROOT (порядок manifest) | User | Assistant | Application traces | Observations |
|---|---:|---:|---:|---:|
| 1 | 6 | 14 | 13 | 301 |
| 2 | 31 | 33 | 55 | 703 |
| 3 | 74 | 74 | 149 | 1 338 |
| 4 | 8 | 24 | 17 | 311 |
| 5 | 11 | 33 | 23 | 246 |
| 6 | 8 | 19 | 17 | 302 |
| Всего | 138 | 197 | **274** | **3 201** |

Все шесть retained ROOT histories доступны полностью в проверенной экспортной
последовательности. Это опирается на ordered stable IDs, earliest empty ROOT с
no parent и selected compactions=0; не на отсутствие ошибок в UI projection.
В 31/74-user случаях user projections различаются, включая image/text additions;
обе исходные последовательности сохранены. Это **не evidence truncation/deletion**.
Четыре exact cross-source user-text checks прошли, два unresolved; legacy
mongo_visible_transcript_complete=false в этих двух manifest entries отражает
именно projection gap, а не потерянный authoritative ROOT export. ROOT tool=0
не означает «инструментов не было»: internal multi-agent tool activity видна в LF.

Первый application-normalized RunStore имел три complete joins: 47 traces,
914 observations, 316 ID-linked calls/results. Затем
[extend_dialogues](<../prototype/bench/doubleup/extend_dialogues.py>) завершил все
шесть: **469 дополнительных GET =227 trace-detail +227 observation +15 pagination**,
ранние ready joins переиспользованы. [Public manifest](<../prototype/bench/doubleup/.pilot-state/runs/mongo-dialogues-all-six-application-join-v1/manifest.json>)
даёт 274/3 201, **512 ID-linked source calls/result variants** и 511 tool execution
spans. Все шесть LF sessions complete; provider calls=0, remote mutations=0.
Это видимая retained-source полнота, не причинное воспроизведение production.

## 7. Локальные исполнители и явная адаптация replay

Immutable safe-local-replay-plan-v4 покрывает **только три ready случая**:
десять source contracts (семь Mongo registry +три actual code). Нет выдуманных
схем по аргументам. [ReplayTools](<../prototype/bench/doubleup/replay_tools.py>)
вычисляет web/read/memory/project ответы по NEW arguments и frozen resources,
не возвращает постоянный исторический answer. Missing/partial resources явно
unsupported. Original generated outputs не seed-ятся; per-arm state клонируется
независимо.

[Python executor](<../prototype/bench/doubleup/replay_executor.py>) + dedicated
[Dockerfile](<../deploy/doubleup-pilot/Dockerfile.replay-executor>) реально исполняет
Python в Docker: network none, без host mount/socket/secret env, read-only root,
uid1000, cap-drop ALL, no-new-privs, pids64, 512 MiB, CPU1, tmpfs, stdout/stderr
<1 MiB each, files <1 MiB each /8 MiB total /128, timeout1–60s. Own-container kill
проверяется по идентичности. Image:
`9b8c1a7d74e2504a8b7e2254f64b58fccbcb332d8bb57c0b4c280b8a900bc2c4`.
Доступны stdlib +numpy/pandas/openpyxl/matplotlib, не произвольные dependencies.
Docker sharing host kernel не позволяет назвать это production hostile-code sandbox.

[Bundle preparation](<../deploy/doubleup-pilot/prepare_dialogue_replay.py>) запечатал
три text-only sequences 6/8/8, сохранив original multi-text blocks. System prompt —
точный source executor prompt из earliest native-tool-output generation. **Это
explicit adaptation:** actual DoubleUp ExecutionStage tool loop +frozen executor
prompt; historical multi-agent orchestrator **не воспроизведён**.

[Bridge](<../deploy/doubleup-pilot/dialogue_bridge.py>) и
[runner](<../deploy/doubleup-pilot/dialogue_runner.py>) прошли dry protocol на всех
восьми ходах каждого из трёх плеч: 48 scripted model requests /24 genuine Python
calls. [Live wrapper](<../deploy/doubleup-pilot/run_dialogue_live.py>) начал первый
paid случай, закрывая платный egress в `finally`. Полный трёхсторонний paid результат
ещё не готов. Исполняется actual DoubleUp ExecutionStage, инструмент обращается
к host через приватный stdin/stdout RPC, не к source business systems. В дальнейший
контекст идут только NEW model/tool returns при fixed original user sequence и
собственном workspace каждого arm;
исторические assistant/generated answers не инжектируются. Source-generated files
могут появиться только если заново созданы причинно. Interrupted/unknown arm не
оплачивается автоматически повторно. 31/74-turn image_url chats нельзя silently
превратить в text-only, удалив картинки или сократив history.

## 8. Pricing и persistent $10: коррекция резерва, не расход

Authenticated metadata base 1.4e-7/2.8e-7 за token недооценивал текущий peak.
По [официальной странице pricing](<https://api-docs.deepseek.com/quick_start/pricing/>)
(получено родителем 24 октября), legacy deepseek-v4-flash теперь обслуживается
V4.1 Flash 1017 alias, 1M context, peak cache-MISS input **$0.30/M**, output
**$1.20/M**. Approved request model ID deepseek-v4-flash **не меняется**.

Политика [budget](<../deploy/doubleup-pilot/budget.py>): max(gateway base, все
положительные tiers, official peak), затем ×2 safety. Только verified flat 1M
proof разрешает long input при input+output≤1M; другие unpriced >120k модели
отказывают. [Refresh](<../deploy/doubleup-pilot/refresh_dialogue_pricing.py>) —
read-only authenticated GET, numeric whitelist, private sanitized cache fresh≤24h,
не модельный вызов и не разрешение live.

Снимок **до нового paid causal run** (не текущий остаток работающего прогона):

| Persistent accounting до нового live | USD |
|---|---:|
| Original 13 calls: 12 settled +1 **usage_unknown**, прежний учёт сохранён | 0.0473207 |
| Additive immutable idempotent pricing reserve | 0.0877183 |
| Total accounted | **0.135039** |
| Remaining из $10 | **9.864961** |

Дополнительный reserve — conservative correction, не новый spend и не invoice.
usage_unknown — не delivery_unknown. Gateway **перезапущен с новым Ledger**, что
проверено из контейнера, затем включён для явно одобренного владельцем live run.
Текущий расход/резерв читается из persistent ledger, а не из статической таблицы.
[Wrapper](<../deploy/doubleup-pilot/run_dialogue_live.py>) закрывает paid egress
в `finally`; отчёт не утверждает, что работающий run уже завершён.

Encrypted source/step archives и RAM-only sandbox не означают end-to-end encryption
всей платформы: replay chat history сохраняется в приватной локальной Mongo как
обычная история DoubleUp. Этот слой не выдаётся за SQLCipher vault.

## 9. Следующая граница доказательства

1. Дождаться итогов paid восьмиходового случая во всех трёх режимах, сохранить
   every attempted call/status и не подменять failed/limited outcome успешностью.
2. В fixture mode выполнить HTTP gate нового baked backend, затем проверить
   отображение actual replay histories/инструментальных записей без client screenshots.
3. Разобрать новые ответы и реальные локальные tool outcomes качественно; missing
   resources/dependencies и frozen-executor adaptation не приписывать Pseudex.
4. Решить объём дальнейших целых случаев по фактическому остатку persistent $10;
   не сокращать исходную историю и не повторно оплачивать неизвестные попытки.
5. Images, недостающие ресурсы, shared-thread ACL, provider streaming/SDK, нагрузка,
   release/canary/rollback и отдельный [offline contract](<../docs/tz-offline-license.md>)
   остаются отдельными открытыми границами, не побочным эффектом local green.
