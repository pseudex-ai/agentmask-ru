# DoubleUp × Pseudex: локальный пилот и inspection API

Статус: **ongoing / in progress**, локальная реализация; не релиз и не готовность
к dev/prod. Срез: 24.10.2026. Текущие evidence и ограничения — в
[отчёте четырёх переходов/полных диалогов](<../research/2026-10-24-doubleup-four-hops-and-dialogues.md>).
[23 октября](<../research/2026-10-23-doubleup-local-pilot.md>) — предыдущий checkpoint,
не текущая full-suite/full-dialogue приёмка.

## Текущий срез: три трека владельца

- UI исправлен DeepSeek Flash и проверен Lead: email link labels, стабильные метки/
  отдельный60s private payload, человеческие номера запросов и collapsed IDs;
  **140 Node tests, tsc/lint exit0**, реальный synthetic browser27 checks и обновлённый
  four-hop gate. Полный backend после source-view guard: **6 224 passed /36 existing
  environment skips,243.04s** (без сети, новых skip не добавлено). Auth/thread смена закрывает старую scope до passive cleanup.
- UUID: [причина и независимое воспроизведение](<../research/2026-10-24-uuid-residual-research.md>).
  Это исследование, не принятый фикс и не основание обходить residual/fail-closed.
- [Реальная подборка](<../research/2026-10-24-real-sensitive-dialogues.md>): **21 полный
  исходный диалог /183 пользовательских хода**, 15 с контактами в исторических тулах,
  12 с повторением пользовательских контактов в аргументах/результатах. Это не новый
  прогон. Локальные исходники read-only: попытка POST /query даёт409 до модели.
- Live ранее: none8/8, builtin8/8 (один owner-approved retry при сохранённом unknown
  reserve), Pseudex остановлен внутри первого хода после8 tool steps. `0/8 completed`
  не означает8 провалов: остальные7 не запускались. Его не выдаём за успешный.
- Сейчас gateway **fixture / paid disabled**. Учтено с резервами **$2.7971142**, остаток
  **$7.2028858**. Новых платных прогонов по трём текущим трекам нет. Подробные старые
  блоки ниже описывают этапы подготовки; это верхнее резюме задаёт текущий статус.

## Что подключено

```text
DoubleUp (none | builtin | pseudex)
   → общий HTTP transport перед LiteLLM
       ↔ Pseudex sidecar /mask + /unmask
   → локальный model connector
       fixture: детерминированный копировщик, без внешних вызовов
       live: только разрешённый DeepSeek endpoint через LiteLLM, ledger ≤ $10
```

Провайдера вызывает DoubleUp через существующий transport. Сайдкар не заменяет
LiteLLM и не получает его ключ. Billing metadata сохраняется; в тестах используются
локальные surrogate tenant/thread, не клиентские кошельки. Новые органы данных
из исходных трейсов не выводятся догадками.

`PSEUDEX_PILOT=1` включает локальный путь. `PII_BACKEND` — `none`, `builtin`,
`pseudex`; по умолчанию `builtin`. Без флага nonbuiltin запрещён. Изменение
маскирования не выключает отдельную проверку блокирующей политики.

- `none`: без маскирования и обратной подстановки.
- `builtin`: существующие DoubleUp masker, policy resolver, Redis-vault и fail-open.
- `pseudex`: встроенный masker/restore обходятся, работает сайдкар. Ошибка защиты,
  malformed JSON и residual substitutes не превращаются в raw pass-through.

В pilot поддержаны nonstream OpenAI chat completions с текстом и native tool calls.
**Provider streaming**, Anthropic-native, некоторые SDK и нетекстовые запросы в
защищённом режиме явно блокируются. SSE самого чата (start/events/end и stable
message IDs) работает; это другая граница, не provider stream и не streaming
receipts. Движковые streaming endpoints сами по себе не интегрируют эту границу.
31/74-user source chats с image_url нельзя превратить в поддержанные, удалив
изображения или сократив историю.

## Совместимое расширение контейнерного API

### `POST /mask`

Шлюзовая авторизация: `Authorization: Bearer $PSEUDEX_GATEWAY_TOKEN`.
Старый запрос без `inspection` по-прежнему получает только `messages` и `tools?`.
Новый optional opt-in:

```json
{
  "org_id": "tenant-17",
  "agent_id": "agent-3",
  "conversation_id": "chat-8",
  "pseudonym_scope": "conversation",
  "request_id": "run-9/step-2/attempt-1",
  "inspection": true,
  "messages": [{"role": "user", "content": "…"}],
  "tools": []
}
```

Response сохраняет фактические `messages`/`tools` и добавляет:

```json
{
  "inspection": {
    "version": 1,
    "request_id": "run-9/step-2/attempt-1",
    "receipt_id": "opaque-receipt-id",
    "conversation_id": "chat-8",
    "pseudonym_scope": "conversation",
    "offset_unit": "unicode_codepoint",
    "complete": true,
    "limitations": [],
    "replacements": [
      {
        "occurrence_id": "opaque-occurrence-id",
        "path": "/messages/0/content",
        "source_start": 0,
        "source_end": 1,
        "output_start": 0,
        "output_end": 1,
        "type": "NAME",
        "shown": "…",
        "base_token": "…",
        "kind": "pseudonym"
      }
    ]
  }
}
```

Числа в примере схематические: реальные диапазоны рассчитывает движок.

- Диапазоны half-open, в Unicode code points; в JS после emoji нельзя использовать
  индексы UTF-16 без преобразования. `path` — JSON Pointer поля исходного/выходного
  конверта. Для `function.arguments` offsets относятся к JSON-строке аргументов,
  а не к отдельно декодированному leaf.
- `shown` — точная вставленная форма. `base_token` — ключ vault для раскрытия,
  может отличаться от склонённой/переформатированной формы; может быть `null`.
- `kind=redaction` не обещает обратимость. Нельзя придумывать token для раскрытия.
- `complete=false` и `limitations` означают, что не для всех преобразований можно
  доказать исходные координаты. Выходной payload точен, но receipt неполон.
- Capture происходит при реальных splice/echo операциях, не повторной детекцией.
  Cache хранит immutable masked text и локальные координаты вместе. Raw literals,
  request IDs и пути полей в cache не добавляются; чтение receipt не mint-ит
  новые токены и не пишет повторный entity audit. Каждый успешный `/mask` остаётся
  одним запросом биллинга, с флагом и без него.
- `request_id` — корреляция попытки, не idempotency key. Без него при opt-in
  создаётся ID. `receipt_id`/`occurrence_id` не являются URL постоянной истории.
- У proxy sandbox `/mask` receipt показывает его фактическую derived conversation
  и environmental scope. Sidecar-only body options там не начинают действовать
  автоматически. OpenAI `/v1/chat/completions` не получает новых JSON-полей.

Опции неправильного типа — 400; неверный surface token — 401. Обычные auth,
lease, org binding и fail-closed ошибки сохраняются.

### `POST /unmask`, `POST /unmask_arguments`: OUT receipt v2

Обе manual поверхности — sidecar и proxy — требуют **gateway token**. При
`inspection: true` добавляется отдельный OUT v2; без opt-in прежний JSON shape
сохраняется. Proxy OpenAI `/v1/chat/completions` не получает дополнительных полей.
Mask receipt v1 выше **не изменён**.

```json
{
  "inspection": {
    "version": 2,
    "operation": "restore",
    "request_id": "run-9/step-2/attempt-1",
    "receipt_id": "opaque-receipt-id",
    "conversation_id": "chat-8",
    "pseudonym_scope": "conversation",
    "offset_unit": "unicode_codepoint",
    "coverage": "semantic_transformations",
    "semantic_complete": true,
    "lexical_complete": false,
    "limitations": [{"path": "/arguments/0", "reason": "json_serialization_normalized"}],
    "replacements": [{
      "occurrence_id": "opaque-occurrence-id",
      "path": "/arguments/0",
      "source_start": 1, "source_end": 2,
      "output_start": 1, "output_end": 2,
      "type": "RESTORATION", "kind": "restoration",
      "granularity": "json_leaf", "leaf_path": "/field"
    }]
  }
}
```

Диапазоны в примере схематические, не исполнимое evidence. `span` означает
accepted changed prose splice; `json_leaf` — actual changed-leaf write и **целый
лексический scalar, включая кавычки строк**, не decoded substring. `leaf_path`
optional. Metadata не содержит raw/restored literals, `shown` или `base_token`;
они не добавляются в cache/audit. Читаемая пара берётся из точных host snapshots.

Whitespace/escape normalization не semantic restoration. Поэтому semantic/lexical
completeness разделены; duplicate keys и untracked changed leaves явно incomplete.
Нельзя восстановить receipt постфактум по diff/поиску значения. Actual `/unmask`
paths: `/response/choices/{ARRAY POSITION}/message/…`, **не choice.index**;
standalone `/unmask_arguments`: `/arguments/{i}`. Host при чтении provider snapshots
снимает только известный `/response` prefix; исходный engine receipt сохраняется.
Provider-streaming receipts unsupported.

### Точная история принадлежит host backend

Контейнер не заводит новую БД истории. DoubleUp сохраняет отдельно:

1. вход HTTP-границы (`source_request`);
2. фактически отправленный body (`model_request`);
3. сырой ответ (`model_response`);
4. ответ, возвращённый агенту (`restored_response`);
5. actual tool-dispatch records, когда исполнитель действительно вызывается.

В `builtin` первый snapshot мог уже пройти встроенный masker раньше. Это не
обещание дословного исходника пользовательского сообщения. Подготовленный payload
не доказывает доставку модели; `delivery_unknown` остаётся неизвестностью.

Message provenance — server-owned ID + exact whole text/hash/role, не совпадение
слов. Оба converters используют несериализуемые _WireMessage attributes: модель
не получает служебных JSON keys, posted JSON не подделывает Python capability.
Root request ID отделён от actual attempt ID. SSE start передаёт
pseudex_input_messages [{input_index,message_id}], final answer — existing actual
AIMessage ID. Все actual attempts сохраняются; old data не backfill-ятся по text/time.
Raw tool result хранится отдельно от trimmed forwarded content. Dispatch/call/
execution IDs привязывают реальный эффект; prepared result не считается forwarded
до следующего actual ModelRequest с точными ID/text/hash.

Снимки шифруются AES-GCM в отдельной локальной Mongo collection. Metadata включает
tenant/thread/owner/agent/attempt, version и expiration; AAD связывает ciphertext с
идентичностью. TTL по умолчанию 7 дней, чтение проверяет expiration независимо от
задержки TTL sweeper. Ключ — отдельный внешний regular file 0600; symlink,
relative path, source-tree location и неправильный владелец отклоняются.
Pseudex SQLCipher schema и schema lock не меняются.

## API backend для чата

Все ручки дополнительно требуют реального JWT DoubleUp, org membership и права на
диалог. В pilot — владелец private thread либо superadmin; shared-project access
не расширяется автоматически. Организация, actor, token и URL не принимаются от
браузера как полномочия.

```http
GET /api/v1/pseudex/inspections?thread_id=<id>
GET /api/v1/pseudex/inspections/highlights?thread_id=<id>
GET /api/v1/pseudex/inspections/<attempt_id>
POST /api/v1/pseudex/inspections/<attempt_id>/occurrences/<occurrence_id>/reveal
```

Список: `{items:[{attempt_id,thread_id,mode,status,created_at}]}`. Detail содержит
перечисленные snapshots, inline `inspection`, `inspection_availability` и
`tool_dispatches`. Unknown/foreign object — 404; нет дополнительного права
раскрытия — 403; не записан/необратим occurrence — 409. Responses, включая ошибки,
имеют `Cache-Control: no-store`. Validation ошибки не отражают исходные значения.

Highlights BFF авторизует owner/superadmin и metadata каждого attempt **до decrypt**.
Ответ — bounded projection: до 100 attempts, 400 messages, 400 tools, 128 KiB/entry,
512 KiB общего entry budget. Oversize entries **omit, не truncate**: иначе offsets/
hashes перестали бы обозначать exact snapshot. Evidence status verified/no_op/
incomplete/not_recorded не смешивается с delivery status и tool execution outcome.
Отсутствие привязки не означает «0 ПД». Fixed root-prefix mapping делается только
на чтении, original engine receipt path сохраняется.

Reveal дополнительно требует org owner/admin или superadmin. Backend выбирает
`base_token` из проверенной записи, вызывает существующий `/reveal` под admin
credential и выводит actor из JWT. Сначала успешный engine audit, затем host audit
identity/attempt, только после этого plaintext. В audit нет раскрытого значения.
Vault value — каноническое значение, не обязательно literal исходной фразы.

**Ни gateway, ни admin token не принадлежат браузеру.** Gateway token способен
получать plaintext через execution `/unmask*`; разделение токенов не отменяет
этой способности. В UI нет произвольного proxy или `/unmask` как human reveal.

Actual MessageBubbleV2/page и existing tool menu теперь используют inline
highlighter: жёлтый mask, teal restore, actual peer form по hover/focus/tap.
Codepoint→UTF-16 перевод точный. WeakMap capability на HAST node и factory последним
rehype plugin не позволяют HTML string/forged attribute открыть peer value.
Точные link labels, включая GFM email, теперь помечаются неинтерактивным mark внутри
исходной ссылки; hover/focus принадлежит anchor без второго tab stop и без изменения href.
Code/math/link destinations, cross-node и transformed text — explicit plain fallback, не догадка. positions сохраняет exact soft-line offsets до remarkBreaks
и явно порождённый `br` newline перед rehypeRaw; multiline regression после
bold/emoji/autolink проходит, без восстановления позиций поиском значения.

Пара строится только по JSON Pointer/offsets и обоим exact snapshots, не через
canonical vault lookup. Отдельный canonical reveal остаётся явным/audited. Session
provider no-store/auth/context org+user+path+token-epoch scoped. **Метки и детали имеют
разный lifetime:** координаты/occurrence без counterpart остаются в открытом разрешённом
чате; private peer/tool snapshots очищаются через абсолютные60s и при hide. Явный
hover/focus/tap подгружает свежую запись, только exact-key join, без фонового polling.
Thread/org/user/token/logout/pagehide, отказ авторизации и toggle-off удаляют всё;
render-time identity guard не публикует предыдущую scope до passive cleanup.
PII/counters/details не сохраняются в localStorage/analytics; dev raw chat logs отключены
**только pilot**, Sentry выключен. Реальный browser gate проверяет send/hover/focus/tool
marks/toggle, mobile taps и сохранение marks послеTTL без старого private peer. Форма входа до hydration не
отправляет пароль GET-запросом: method POST и disabled submit.

## Локальный запуск

Нужны sibling worktree `doubleup-pilot`, `doubleup-backend-pilot`,
`doubleup-frontend-pilot`, Docker/Compose и Python с зависимостями prototype.
Команды ниже — из корня Pseudex pilot worktree. Состояние намеренно не стирается:
повторный `prepare` отказывается перегенерировать ключи существующего vault.

```bash
python deploy/doubleup-pilot/stand.py prepare
python deploy/doubleup-pilot/stand.py snapshot-engine
python deploy/doubleup-pilot/stand.py build
python deploy/doubleup-pilot/stand.py base
python deploy/doubleup-pilot/stand.py apps
python deploy/doubleup-pilot/stand.py seed
python deploy/doubleup-pilot/stand.py roundtrip
python deploy/doubleup-pilot/stand.py fixture
python deploy/doubleup-pilot/http_inspection_gate.py
python deploy/doubleup-pilot/seed_four_hop.py
python deploy/doubleup-pilot/four_hop_web_gate.py
python deploy/doubleup-pilot/browser_four_hop_gate.py
```

Адреса: frontend `127.0.0.1:18880`, user API `:18860`, graph `:18861`,
source engine `:18862`, compiled gate `:18863`, fixture connector `:18850`.
Admin licensing `:18943` доступен только loopback. Приложения/БД/инструменты
на internal network; fixed-upstream frontdoor публикует порты без общего relay.
Живой egress временно получает только ограниченный model connector.

Frontend запускается отдельно из его worktree с environment:

```bash
NEXT_PUBLIC_PSEUDEX_PILOT=1 \
NEXT_PUBLIC_API_BASE=http://127.0.0.1:18860 \
NEXT_PUBLIC_GRAPH_API=http://127.0.0.1:18861 \
NEXT_PUBLIC_KEYCLOAK_ENABLED=false \
NEXT_PUBLIC_KEYCLOAK_URL=http://127.0.0.1:18860/disabled-keycloak \
NEXT_PUBLIC_SENTRY_DSN= NEXT_PUBLIC_GLITCHTIP_ENABLED=false \
NEXT_TELEMETRY_DISABLED=1 \
node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 18880
```

Использовать project Node, совместимый с native Next/CSS modules. В этой среде
это `/opt/homebrew/bin/node`; подписанный bundled Node не загрузил native modules.
Dependencies установлены отдельно по committed lockfile, не в чужой рабочей копии.
`NEXT_PUBLIC_*` фиксируются при запуске dev/build. Учётные данные создаются только локально в закрытом
[generated browser config](../deploy/doubleup-pilot/.state/runtime/browser.json);
в командную строку или отчёт их не копировать. После входа открыть
[synthetic four-hop demo chat](<http://127.0.0.1:18880/doubleup-pilot/assistantnew/1f55257d-83f5-51a9-88e1-e0eb11442855?thread=41269e0d-008d-521e-ab54-b8de46e5820a>)
и «Проверка границы данных». Для внешней демонстрации выбирать synthetic org
`doubleup-pilot`, не организации с оригинальными клиентскими случаями.

Дополнительные реальные артефактные проверки:

```bash
python deploy/doubleup-pilot/stand.py build-compiled
python deploy/doubleup-pilot/stand.py compiled-gate
python deploy/doubleup-pilot/backend_image.py
python deploy/doubleup-pilot/baked_gate.py
python deploy/doubleup-pilot/browser_gate.py
python deploy/doubleup-pilot/web_query_gate.py
```

Baked backend использует существующую dependency image и собственный source
snapshot. Это не полный rebuild requirements и не публикация образа. У него нет
bind mount приложения; дополнительные loopback gate ports — 18864/18865.

## Полные исходные диалоги — текущий корпус

[Read-only intake](<../prototype/bench/doubleup/>) теперь опирается на Mongo
**authoritative ROOT** и **application Langfuse**, не на прежние 200 gateway trace
fragments. Исторические 76 групп/60–16 split/113 unscoped не являются текущей
full-chat выборкой или доказательством независимости.

Mongo read-only был отдельно разрешён владельцем. [Mongo intake](<../prototype/bench/doubleup/mongo_intake.py>)
использует find/aggregate, не MongoSaver: его constructor создаёт indexes.
[ROOT normalizer](<../prototype/bench/doubleup/mongo_dialogues.py>) декодирует
msgpack/JSON через static safe message allowlist, без arbitrary imports/pickle;
установленный serde не поддерживал allowed_objects вопреки warning. Raw canonical
EJSON и обе source projections сохранены encrypted. Credentials только RAM/stdin,
source-resource container без логов/DDL; stdout только counts/hashes/codes.

Локальный Langfuse profile — gateway project. Backend GitOps LANGFUSE keys —
**другой application project**, 8 637 видимых traces, session IDs actual thread
UUID. Ни person names, ни secret values/host URI не копируются. Ранее source
credentials случайно напечатали и раскрыли владельцу; значения не повторять,
production rotation этой работой не выполнялась.

Source inventory: 2 231 threads /53 734 message documents /28 478 graph states /
19 compactions. Шесть encrypted raw exports — immutable RunStore
mongo-full-chats-local-pilot-v2. ROOT user counts **6/31/74/8/11/8**, assistant
**14/33/74/24/33/19**. Ordered stable IDs, earliest empty ROOT/no parent и selected
compactions=0 подтверждают всю retained visible ROOT history, **не** never-deleted-
ever или transactional snapshot. 31/74-user projections различаются, включая
image/text additions; original обе sequences сохранены, это не доказательство
truncation/deletion. Четыре exact cross-source text checks совпали, два unresolved.
Нулевые ROOT tools не означают no tools: internal multi-agent activity видна в LF.

Первый application-normalized RunStore содержал 3 complete joins: 47 traces /
914 observations /316 ID-linked calls/results. [Extension](<../prototype/bench/doubleup/extend_dialogues.py>)
завершил все шесть через 469 дополнительных GET (227 trace-detail +227 observation
+15 pagination), reuse ready joins, zero mutations/provider calls/cost.
[Public manifest](<../prototype/bench/doubleup/.pilot-state/runs/mongo-dialogues-all-six-application-join-v1/manifest.json>)
даёт **274 traces /3 201 observations /512 ID-linked source calls/result variants**.
Это не шесть независимых statistical cases и не complete production environment.
Manual PII labels не делаются: живое сравнение остаётся качественным visual review,
без precision/recall/equivalence/task-quality superiority metrics.

Immutable run IDs нельзя overwrite. Архивировать только run directory, **не state
с ключами**; ciphertext/originals не входят в source archives/screenshots/docs.
Legacy package README/CLI описывает первый gateway intake; текущая интерпретация
full chats — этот раздел и [новый отчёт](<../research/2026-10-24-doubleup-four-hops-and-dialogues.md>).

## Причинный replay: подготовка есть, финального результата пока нет

[Source resources](<../prototype/bench/doubleup/source_resources.py>) заморожены
в safe-local-replay-plan-v4 для **трёх ready cases**, не для всех шести: десять
source contracts (7 Mongo registry +3 actual code), 36 tool tests passed.
[ReplayTools](<../prototype/bench/doubleup/replay_tools.py>) query-dependent для
web/read/memory/project: NEW arguments и per-arm own state, не constant source
answers. Missing/partial resources явно unsupported. Historical assistant/generated
outputs и source-generated files не seed-ятся, а могут появиться только причинно.

[Replay executor](<../prototype/bench/doubleup/replay_executor.py>) + dedicated
[Dockerfile](<../deploy/doubleup-pilot/Dockerfile.replay-executor>) — настоящий
Python Docker, network none, no host mounts/socket/secret env, RO root uid1000,
capdropALL/no-new-privs/pids64/512MiB/CPU1/tmpfs, stdout/stderr <1MiB each,
files <1MiB each/8MiB total/128, timeout1–60s и verified own kill. 19 genuine Docker
checks passed. Image `9b8c1a7d74e2504a8b7e2254f64b58fccbcb332d8bb57c0b4c280b8a900bc2c4`.
Stdlib+numpy/pandas/openpyxl/matplotlib; это **не production hostile-code sandbox**.

[prepare_dialogue_replay](<../deploy/doubleup-pilot/prepare_dialogue_replay.py>)
запечатал 3 text-only user sequences **6/8/8** с original multi-text blocks и exact
executor system prompt из earliest native-tool-output generation. **Explicit
adaptation:** actual DoubleUp ExecutionStage tool loop +frozen source executor
prompt; historical multi-agent orchestrator **не воспроизведён**.
[dialogue_bridge](<../deploy/doubleup-pilot/dialogue_bridge.py>)/
[dialogue_runner](<../deploy/doubleup-pilot/dialogue_runner.py>) прошёл весь dry
protocol восьмиходового случая в трёх режимах: 48 scripted model steps /24 genuine
Python calls. Начат paid replay этого случая; трёхсторонний результат пока не
готов. В дальнейшие steps идут NEW model/tool returns, fixed original user sequence
и independent workspace каждого arm. Start marker/unknown/stopped arm не auto-repaid.
[Live wrapper](<../deploy/doubleup-pilot/run_dialogue_live.py>) закрывает paid egress
в `finally`. Нельзя silently strip images/shorten source history ради supported path.

## Persistent budget и условия будущего paid go

Точный approved model ID **deepseek-v4-flash не меняется**. По
[официальному pricing](<https://api-docs.deepseek.com/quick_start/pricing/>) (fetched
24 октября) legacy ID обслуживается V4.1 Flash 1017 alias, 1M context, peak cache-MISS
input **$0.30/M**, output **$1.20/M**. Gateway metadata base 1.4e-7/2.8e-7 per token
ниже peak; полагаться только на него нельзя.

[Budget](<../deploy/doubleup-pilot/budget.py>) использует max(gateway positive
base/all tiers, official peak), затем **×2 safety**. Только verified flat 1M proof
разрешает long input, input+output≤1M. Другие unpriced >120k модели отказывают,
не получают нулевую цену или обрезанную history. [Pricing refresh](<../deploy/doubleup-pilot/refresh_dialogue_pricing.py>)
делает только authenticated read-only GET с numeric whitelist/privacy cache,
fresh≤24h; без model call. Новые 31 budget checks green.

Persistent cap **$10** сохранён. До нового paid run: original 13 calls, 12 settled
+1 **usage_unknown** (не delivery_unknown), прежние **$0.0473207** неизменны.
Additive immutable idempotent pricing reserve **$0.0877183** дал исходный accounted
**$0.135039**, remaining **$9.864961**. Коррекция не invoice и не новый вызов;
**это не текущий остаток уже работающего live replay** — он читается из ledger.

Gateway был перезапущен с новым Ledger для одобренного paid run; теперь он снова
fixture/paid disabled. Текущий accounted/reserved **$2.7971142**, remaining **$7.2028858**;
начальные цифры выше не текущий остаток. [Wrapper](<../deploy/doubleup-pilot/run_dialogue_live.py>) делает finally-disable;
этот runbook не команда автоматического запуска. Не удалять ledger/keys ради повтора, не auto-repay partial
arms. Полный causal run quote заранее неизвестен: каждый actual request резервируется
до отправки и неопределённая стоимость удерживается.

Per-request no-log запрошен по [LiteLLM contract](<https://docs.litellm.ai/docs/proxy/logging>),
глобальное разрешение на общем gateway не доказано. Локальный SDK Langfuse выключен.
Thinking одинаково disabled согласно [DeepSeek API](<https://api-docs.deepseek.com/guides/thinking_mode/>).
[Старые prepare_live/live_runner](<../deploy/doubleup-pilot/live_runner.py>) —
предыдущий single-generation smoke, не full dialogue replay.

## Карта клиентских исходников (read-only aliases)

Это source links в sibling client worktrees; они **не** engine import edges и
не новые AI notes в клиентских репозиториях. Foreign PLATFORM_OVERVIEW/SUMMARY и
исходные dirty docs не изменяются этим runbook.

| Read-only source alias | Фактическая роль |
|---|---|
| [backend links](<../../doubleup-backend-pilot/services/pseudex_pilot_links.py>) | server IDs/exact whole text/hash, nonserialized _WireMessage capability, IN/OUT root mapping и bounded highlight projection |
| [backend pilot service](<../../doubleup-backend-pilot/services/pseudex_pilot.py>), [encrypted repository](<../../doubleup-backend-pilot/repository/pseudex_pilot_inspections.py>), [routes](<../../doubleup-backend-pilot/routes/pseudex_pilot.py>) | actual per-attempt snapshots/restoration/dispatch/results; root correlation отдельно; owner/superadmin-before-decrypt, no-store highlights/reveal |
| [shared converter](<../../doubleup-backend-pilot/chat_graph/llm_utils.py>), [ExecutionStage](<../../doubleup-backend-pilot/chat_graph/stages/execution_stage.py>) | оба converters, actual output IDs, raw/trimmed tool snapshots и следующий ModelRequest |
| [pilot tools](<../../doubleup-backend-pilot/tools/pseudex_pilot_tools.py>) | только flag+DB doubleup_pilot+org doubleup-pilot; synthetic no effects; existing registry/map gated |
| [link tests](<../../doubleup-backend-pilot/tests/test_pseudex_pilot_links.py>), [four-hop tests](<../../doubleup-backend-pilot/tests/test_pseudex_pilot_four_hops.py>), [transport tests](<../../doubleup-backend-pilot/tests/test_pseudex_pilot_transport.py>), [inspection tests](<../../doubleup-backend-pilot/tests/test_pseudex_pilot_inspections.py>) | bounded provenance/ACL/default-mode/API regressions; focused результаты не полный backend run |
| [highlight types](<../../doubleup-frontend-pilot/src/components/pseudex-highlights/types.ts>), [ranges](<../../doubleup-frontend-pilot/src/components/pseudex-highlights/ranges.ts>), [highlight component](<../../doubleup-frontend-pilot/src/components/pseudex-highlights/PseudexHighlightedText.tsx>) | точные Unicode codepoint→UTF-16 диапазоны, actual peer text, yellow/teal hover/focus/tap |
| [Markdown capability](<../../doubleup-frontend-pilot/src/components/pseudex-highlights/markdown.tsx>), [positions](<../../doubleup-frontend-pilot/src/components/pseudex-highlights/positions.ts>), [exports](<../../doubleup-frontend-pilot/src/components/pseudex-highlights/index.ts>) | WeakMap/HAST capability, factory last rehype, conservative fallback, soft-line positions before remarkBreaks |
| [session provider](<../../doubleup-frontend-pilot/src/components/PseudexHighlightSession.tsx>), [tool hop views](<../../doubleup-frontend-pilot/src/components/PseudexToolHopViews.tsx>) | auth/context identity, absolute60s clear/abort и actual existing tool menu |
| [MessageBubbleV2](<../../doubleup-frontend-pilot/src/app/(dashboard)/assistantnew/[id]/components/MessageBubbleV2.tsx>), [page](<../../doubleup-frontend-pilot/src/app/(dashboard)/assistantnew/[id]/page.tsx>) | подключён настоящий чат, не отдельный mock |
| [API](<../../doubleup-frontend-pilot/src/app/api/pseudex.ts>), [SSE](<../../doubleup-frontend-pilot/src/app/api/chat.ts>), [message types](<../../doubleup-frontend-pilot/src/types/common.ts>) | no-store/highlight types, start pseudex_input_messages и final existing IDs |
| [highlight tests](<../../doubleup-frontend-pilot/tests/pseudex-highlights.test.mjs>), [prior panel tests](<../../doubleup-frontend-pilot/tests/pseudex-pilot.test.mjs>) | prior33 passed; новый multiline test ещё исправляется, не green evidence |

## Текущие gates и открытая граница

[HTTP source report](<../deploy/doubleup-pilot/.state/http-inspection-gate.json>) и
[compiled report](<../deploy/doubleup-pilot/.state/http-inspection-gate-compiled.json>)
прошли all-four-hops/v2/default shapes/auth на actual :18862/:18863. Engine snapshot
`1265a266c328f6b1e05f9cc1577550878cfc3e33738f03ee3c06274715642ba1`, source image
`45dc6170bf493ef5bf3a9eb78a2213bb69aad26460554ce6a41514fbd60c5c98`.
[Web report](<../deploy/doubleup-pilot/.state/four-hop-web-gate.json>) подтверждает
authenticated User API/query +actual ToolExecutor +SSE IDs +все четыре marks;
[browser report](<../deploy/doubleup-pilot/.state/browser-four-hop-gate.json>) —
actual send/user hover/assistant focus/both tool marks/toggle erase. Всё synthetic,
fixture, **$0**. [User](<../deploy/doubleup-pilot/.state/browser/inline-user-highlight.png>),
[assistant](<../deploy/doubleup-pilot/.state/browser/inline-assistant-highlight.png>),
[tools](<../deploy/doubleup-pilot/.state/browser/four-hop-tool-panel.png>) screenshots
сняты mid CSS transition и требуют refresh; это не source client data.

Source focused 6 restoration/7 mask/33 address — pass; backend worker192 и parent107
passed +1 **existing** skip; Mongo28+65=93. **6 194 baseline/110 old tests — previous,
не current.** Новый full backend/frontend/build/baked gate не выполнен; новый
multiline/mobile/TTL E2E не закрыт. Нельзя объявлять goal complete, production
acceptance или качество агентов на основании этих contained mechanism checks.

Перед dev отдельно нужны unsupported image/provider-stream/native SDK adapters,
shared-thread полномочия, нагрузочные/regression/release gates и согласованный
canary/rollback. Full causal scenarios ещё dry-testing, сравнение qualitative без
manual PII labels. Офлайн-лицензия — отдельный релизный блок по
[принятому контракту](<tz-offline-license.md>); реализации в этом pilot нет.
