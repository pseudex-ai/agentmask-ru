# A1 — RU/CIS commercial products: is any PII-masking gateway TRANSPARENT to an LLM agent? (re-verification, 2026-09-20)

Scope: RU/CIS commercial products only, transparency-to-the-agent axis + deployment. Not detection quality, not Western, not OSS-Western, not academic. Baseline = `research/cis-pii-llm-middleware.md` (June 2026) and `research/2026-09-08-rynok-i-cena.md`.

Fetch log (primary sources read this session): Cloud.ru `guardrails-llm-filter` repo cloned and read (README, CHANGELOG, docs/architecture, docs/storage, rule catalog, `pkg/llmutils/*`, `internal/usecases/guardrails/mask/*`, `internal/guardrails/demask/*`, `internal/sseproc/*`, `tests/e2e/README.md`, `tests/e2e/tool_test.py`); cloud.ru docs (release notes, concepts__guardrails); provod.ai docs (data-protection, 152-fz) + vc.ru article; Habr: Orion soft/StarGuard AI (22.07.2026), AGIMA (11.09.2026), Just AI (1045967), Just AI (946392, baseline); jaycopilot.com/help/jayguard (manual-masking, proxy-requests, overview); kodikrouter.ru/docs; hivetrace.ru + /news/release-4.2; gptunnel.ru/ru/b2b/obfuscator; red_mad_robot video description (YouTube/Instagram, 12–17.08.2026); Yandex Cloud AI Studio agents docs; Sber developers portal (GigaChat API). ~24 fetch-equivalents.

---

## 0. Executive verdict (short)

**Something DID change over the summer.** On **2026-07-06 Cloud.ru open-sourced `guardrails-llm-filter`** (Apache-2.0, single Go binary, on-prem) — a drop-in reverse proxy that masks with `<TYPE_N>` placeholders AND **restores originals inside tool-call `function.arguments`** in the response, **JSON-escaped, in SSE too**, and that **scans `tool` role messages (tool results) on the way in** (extractor is role-agnostic). That is checklist items **2 and 3 (mask half) = YES** for one RU product, proven in code and in its e2e suite. In June no RU product documented this.

**What did NOT change:** nobody on the RU market does format-preserving substitutes, nobody restores a substitute the model REWROTE (declined / transliterated / initials / digits reformatted — item 7), nobody has a persistent conversation-scoped vault with canonicalisation (item 5), nobody handles agent memory echoes (8), partial mentions/corrections (9), collisions (11), and nobody publishes a measurement of "agent unaffected" on the tool-call axis (13). Every RU product uses opaque typed placeholders (`<FIO_1>`, `<jg:person_1>`, `PERSON_1`, `<PLACEHOLDER_N>`), which makes item 2 cheap (string replace + JSON escape) and item 7 structurally impossible/irrelevant (the model cannot inflect `<FIO_1>`; if it glues a suffix, restore yields a corrupted form).

Second new player: **provod.ai** ("российский OpenRouter", docs updated 17.08.2026) documents masking of "аргументы вызовов инструментов и текстовые результаты инструментов", per-request pseudonyms, fail-closed 503, restore "перед ответом клиенту" — restore INSIDE tool_calls not explicitly documented. Cloud SaaS only.

Confidence on "does ANY RU product cover items 2, 3, 7?": **item 2 — YES (Cloud.ru OSS, [A]); item 3 — PARTIAL YES (Cloud.ru: re-masked, same placeholder by exact-match within the request; provod.ai [C]); item 7 — NO (high confidence, structural).**

---

## 1. Cloud.ru — `guardrails-llm-filter` (OSS) + Foundation Models "Правила защиты" (SaaS)

**URLs:** https://github.com/cloud-ru-tech/guardrails-llm-filter · https://cloud.ru/docs/foundation-models/ug/topics/concepts__guardrails · https://cloud.ru/docs/foundation-models/ug/topics/overview__release-notes
**Latest primary material:** repo HEAD `bbd6f27` 2026-07-26 (merge PR #21); CHANGELOG `[0.1.0] - 2026-07-06 Initial public release`; README badge `release-v0.1.2`; Cloud.ru release notes "Июль — Foundation Models Guardrails в открытом доступе".
**CHANGED since June:** yes — the closed-source Envoy ext_proc filter became an open-source standalone HTTP proxy with documented tool-call handling.

### Verbatim quotes

- README: «🔄 **Оригиналы возвращаются в ответ автоматически** — включая потоковые ответы и аргументы вызова инструментов (tool-call). Клиент видит настоящие данные, модель — только заглушки.» (README.md, "Возможности")
- README: «Запрос и ответ на него обрабатываются вместе, поэтому таблица «заглушка → оригинал» просто хранится в памяти процесса, пока идёт запрос. Отдельное хранилище для прохождения трафика не нужно.»
- README: «🟢 **Fail-open по замыслу**: любая внутренняя ошибка пропускает трафик, а не ломает его.» and «Если тело запроса не удаётся разобрать, он проходит без маскирования (безопасное поведение при сбое)»
- docs/architecture/README.md, «Инварианты (нарушать нельзя)»: «1. **Никогда не блокировать** … Вердикта «заблокировать» в пайплайне не существует. 2. **Fail-open на data-path** … Любая ошибка на data-path пропускает трафик, а не ломает его.»
- `pkg/llmutils/chatcompletions/extract.go`: «The extractor is role-agnostic for chat messages. If a payload field is sent to the model as text, it is considered scannable regardless of the message role.» Handles `messages[i].content`, `messages[i].content[j].text`, `messages[i].tool_calls[j].function.arguments`, `messages[i].function_call.arguments`.
- `internal/usecases/guardrails/mask/masker.go`: «masker encapsulates per-request masking state: dedup maps and placeholder counters. Created once per Handle() call, used across all texts» — dedup is `originalToPlaceholder map[string]string` (exact string match).
- `internal/guardrails/demask/factory.go`: `JSONDemasker()` — «is a JSON fragment (e.g. Anthropic input_json_delta.partial_json), where an original containing a quote or backslash would otherwise corrupt the JSON the client accumulates.» + `jsonEscapeString` «HTML escaping is disabled so restored originals survive byte-for-byte».
- `tests/e2e/README.md`: «| tool-call | `tool_test.py` | tool arguments demask to valid JSON incl. values with `"`/`\` (all 3 APIs, stream+non-stream) |» and «| structured | `struct_test.py` | multi-field masking: system, tool_use.input, tool_result, instructions, input items, function_call_output (string+array), chat multi/tool_calls |»
- cloud.ru concept doc: «При обработке запроса чувствительные данные заменяются на плейсхолдеры вида <PLACEHOLDER_N>, где: PLACEHOLDER — тип данных, указанный в правиле; N — порядковый номер замены в пределах текущего запроса.» … «Использование правил защиты рекомендуется при работе с внешними моделями.»
- CHANGELOG (Unreleased): «The closed-source origin rejected such requests with HTTP 400; the OSS verdict model (mask/pass — never block) forwards them instead»
- docs/storage/README.md: «TTL (`GUARDRAILS_STORE_MASKING_TTL`, по умолчанию 15m)» — masking state persisted only as cross-replica fallback during the request.
- Rule catalog `configs/guardrails_regex_rules.yaml`, group PERSONAL_DATA: `pii.fio-ru` (three-word FIO anchored on patronymic suffix, «Covered: declined forms»), `pii.fio-ru.initials`, `pii.fio-ru.short` (~120-name dictionary + surname suffix), `pii.phone-ru`, `pii.email`, `pii.docs.snils/passport/kpp/address/inn-person/inn-org/ogrn/ogrnip`, `pii.fin.*`. Address rule comment: «The street NAME must start capitalised: a lowercase relaxation was tried and rejected».

### Checklist

| # | Item | Verdict | Evidence / grade |
|---|---|---|---|
| 1 | Reversible | **yes** | README + demasker code; placeholders `<EMAIL_1>` restored in body and SSE. **[A]** |
| 2 | Tool-call args restored, JSON valid | **yes (proxy shape)** | `DemaskJSONArguments`/`JSONDemasker`, JSON-escaped originals, e2e `tool_test.py` with `"`/`\` values, streaming deltas via per-field demasker. Restore happens in the RESPONSE handed to the client, which executes the tool — the tool runs on real values. **[A]** (conditions: placeholder must survive byte-exact; mapping lives only for that request / 15 min store TTL) |
| 3 | Tool results re-masked, same substitute | **yes / partial** | Role-agnostic extractor masks `tool` messages before the model; `struct_test.py` covers `tool_result`/`function_call_output`. Same placeholder = exact-string dedup within ONE request; across turns numbering is deterministic by first appearance because the whole transcript is resent, but there is no vault and no canonicalisation (`+7…` vs `8…` → two placeholders). **[A] mask, [B] consistency** |
| 4 | Format-preserving substitutes | **no** | `<FIO_1>`, `<PHONE_1>` typed placeholders by design. **[A]** |
| 5 | Multi-turn consistency incl. canonicalisation | **no** | Per-request state («хранится в памяти процесса, пока идёт запрос»); exact-match dedup only. **[A]** |
| 6 | Streaming (content + tool-arg deltas) | **yes** | «Восстановление в SSE-стриме токен-за-токеном»; `sseproc` per-field demaskers buffer a suffix the length of the longest placeholder; tool-arg deltas go through `JSONDemasker`. **[A]** |
| 7 | Agent's own form (declined/translit/initials/digits) | **no** | Placeholders cannot be inflected; restore needs the literal `<TYPE_N>`. A glued suffix («<FIO_1>у») restores to `Иван Петров Сергеевичу`-style corruption. **[A] (structural)** |
| 8 | Memory / cross-conversation echo | **no** | No conversation concept at all. **[A]** |
| 9 | Partial mentions / corrections, one fake street | **no** | Not applicable to placeholders. **[A]** |
| 10 | Russian morphology / no type word / spoken numbers / lowercase | **partial** | Regex covers declined FIO triplets and ~120 given names; address requires capitalised street + marker/suffix; no lowercase, no spoken numerals, no Natasha/pymorphy. **[A]** |
| 11 | Collisions with real values | **n/a by construction** | Placeholders are outside the value space; `reservedPlaceholders` skips `<TYPE_N>` literals already in the text. **[A]** |
| 12 | Deployment / vault in RF / 152-ФЗ posture | **on-prem yes** | Apache-2.0, docker/k8s, in-process mapping; SaaS version inside Cloud.ru Foundation Models. Posture: «152-ФЗ» claimed in README; no обезличивание/псевдонимизация legal discussion. **Fail-OPEN by invariant** (opposite of Pseudex). **[A]** |
| 13 | Published "agent unaffected" measurement | **no** | Only detection F1 on hivetrace/pii-bench (93.1) etc.; nothing on tool-call fidelity. **[A]** |

---

## 2. provod.ai — "Маскирование чувствительных данных" (NEW player, not in the June sweep)

**URLs:** https://provod.ai/ru/docs/data-protection · https://provod.ai/ru/docs/152-fz · https://vc.ru/provod/3121596-proverka-personalnyh-dannyh-pered-zagruzkoj-v-neyroset
**Latest primary material:** docs page (no date shown); vc.ru article says «Живая продуктовая документация provod.ai, обновлённая 17 августа 2026 года» and «Актуальная редакция 152-ФЗ на дату статьи — 4 сентября 2026 года»; blog: «Верифицированные продуктовые факты provod.ai, owner-approved 15.07.2026».
**CHANGED since June:** new entrant (positioned as «российский OpenRouter»), first version of masking shipped mid-2026.

### Verbatim quotes

- «Когда оно включено, provod.ai проверяет поддерживаемые текстовые поля до отправки внешней модели, заменяет найденные значения типизированными псевдонимами и использует уже преобразованный запрос для всех попыток маршрутизации. Если модель вернула созданный для запроса псевдоним, API восстанавливает соответствующее исходное значение перед ответом клиенту.»
- «Первая версия обрабатывает текст сообщений и инструкций, текстовые части контента, аргументы вызовов инструментов и текстовые результаты инструментов. Поддерживаются категории людей, телефонов, email, адресов, паспортов, ИНН, СНИЛС, банковских счетов, банковских карт, IP-адресов и секретов похожего формата.»
- «Включённое маскирование работает по принципу fail-closed. Если детектор недоступен, превысил время ожидания, отклонил слишком большой текст или вернул некорректный результат, API отвечает `503` с кодом `guardrail_unavailable`. Исходный запрос в таком случае не отправляется внешнему провайдеру»
- «Журнал не хранит исходный или преобразованный текст, найденные значения, соседний контекст и таблицу восстановления псевдонимов.»
- 152-fz page: «Псевдонимизация не равна необратимому обезличиванию. Оцените возможность идентификации человека по оставшемуся контексту и дополнительной информации.» … «Она не является автоматическим подтверждением соответствия Федеральному закону № 152-ФЗ»
- vc.ru: «Успешный запрос с включённым маскированием оплачивается по цене выбранной модели с наценкой 5%.»

### Checklist

| # | Item | Verdict | Evidence / grade |
|---|---|---|---|
| 1 | Reversible | yes | «восстанавливает соответствующее исходное значение перед ответом клиенту» **[C]** |
| 2 | Tool-call args restored, JSON valid | **not documented** | Masks tool-call args on the way IN (request); restoration «перед ответом клиенту» does not say whether it applies inside `tool_calls[].function.arguments` or only `content`; JSON escaping not mentioned. **[C/—]** |
| 3 | Tool results re-masked, same substitute | partial | «текстовые результаты инструментов» are masked; pseudonym «созданный для запроса» → per-request scope, same person across turns not documented. **[C]** |
| 4 | Format-preserving | no | «типизированными псевдонимами» **[C]** |
| 5 | Multi-turn consistency / canonicalisation | not documented (per-request wording) | **[C]** |
| 6 | Streaming | not documented | — |
| 7 | Agent's own form | no | typed pseudonyms **[D]** |
| 8 | Memory / cross-conversation | no | — |
| 9 | Partial mentions | no | — |
| 10 | RU morphology | not documented | «Автоматическое распознавание вероятностное» |
| 11 | Collisions | n/a (placeholders) | — |
| 12 | Deployment | **cloud SaaS only**, «внутри российского контура»; fail-closed; honest 152-ФЗ posture (pseudonymisation ≠ обезличивание) **[C]** |
| 13 | Agent-unaffected measurement | no | — |

---

## 3. Orion soft — StarGuard AI (LLM firewall / gateway) — NEW since June

**URL:** https://habr.com/ru/companies/orion_soft/articles/1061756 (also securitymedia.org overview)
**Date:** 22.07.2026, author Никита Векессер (Orion soft).
**CHANGED since June:** new product announcement; tool-call control = action policies, not detokenisation.

### Verbatim quotes

- «В модель уходит уже другой текст: <PERSON_1>, <PASSPORT_1>, <ADDRESS_1>»
- «Если модель сохранила токены в ответе, StarGuard AI демаскирует их перед выдачей пользователю.»
- «Детектор использует несколько признаков: контекст слова, тип сущности, лемматизацию, метаинформацию и дополнительные проверки валидности.»
- Tool calls: «Он проверяет, какие действия LLM предлагает агенту выполнить, и применяет whitelist или blacklist.» … «Если модель пытается превратить это в вызов инструмента, StarGuard AI может заблокировать действие на уровне политики.»
- «StarGuard AI разворачивается в инфраструктуре заказчика на сервере, виртуальной машине, в Docker или Kubernetes.»
- «для агентских сценариев добавить контроль tool calls.» (policy per audience); «Сейчас StarGuard AI закрывает базовую архитектуру LLM-шлюза: проксирование запросов к моделям, детекторы, маскирование, политики, OIDC, пользователи и группы, учет токенов, журнал событий, обработку файлов и контроль tool calls.»

### Checklist
1 yes [C] · 2 **no/not documented** (tool calls are allow/deny-listed, arguments not detokenised) [B] · 3 not documented · 4 no (`<PERSON_1>`) [C] · 5 not documented · 6 not mentioned · 7 no · 8–9 no · 10 partial claim (lemmatisation) [C] · 11 n/a · 12 on-prem yes (Docker/K8s) [C] · 13 no.

---

## 4. Just AI — Jay Guard

**URLs:** https://jaycopilot.com/help/jayguard/ · https://jaycopilot.com/help/jayguard/api/manual-masking · https://jaycopilot.com/help/jayguard/api/proxy-requests · https://habr.com/ru/companies/just_ai/articles/1045967 (≈June 2026, id between 1035310/May and 1061756/22.07) · baseline https://habr.com/ru/companies/just_ai/articles/946392
**CHANGED since June:** no. Docs still describe text masking/unmasking by session id; a newer Habr piece names tool calling as a leak PATH but describes no mechanism.

### Verbatim quotes

- Manual masking: «Вы отправляете исходный запрос в Jay Guard для маскирования, затем передаете его в LLM, а ответ от модели — обратно в Jay Guard для демаскирования.» Placeholders in the example: `<jg:person_1>`, `<jg:phone_1>`; session header `X-DATA-GUARD-MASKING-ID`; unmask body «любой валидный JSON-объект c текстом, полученным от LLM».
- Streaming: WebSocket «/api/dataguard/public/user-masking/unmask/stream» — «Фрагменты ответа от LLM будут демаскированы в реальном времени».
- Proxy mode: «7. Если применялось маскирование (`redact`), восстанавливает исходные данные в ответе.»
- Habr 1045967: «Что-то осталось в файлах, что-то — в памяти и контексте, что-то — в логах, а часть данных уже ушла во внешние системы через tool calling. Все это нужно учитывать при проектировании» … «Только после успешного прохождения проверок ответ возвращается пользователю, а ранее замаскированные данные при необходимости восстанавливаются.» … «📌 Важно не путать маскирование с юридическим обезличиванием.»

### Checklist
1 yes [B, docs] · 2 **not documented** (no `tool_calls`/`arguments` anywhere in the API docs) · 3 not documented · 4 no (`<jg:person_1>`) [A, docs example] · 5 session-id based; TTL/reuse across turns not documented · 6 yes (WebSocket unmask stream) [B] · 7 no · 8–9 no · 10 ML NER (spaCy/flair per baseline) [C] · 11 n/a · 12 on-prem offered («поставку on-premise под ключ» per bm-it.ru summary) [C]; explicit «маскирование ≠ обезличивание» [B] · 13 no.

---

## 5. KodikRouter (Архитех ИИ)

**URLs:** https://kodikrouter.ru/docs · https://habr.com/ru/companies/kodik/news/1035310
**CHANGED since June:** no.
Quotes: «PII-маскирование — ФИО, телефоны, СНИЛС, адреса маскируются до отправки и восстанавливаются в ответе — 152-ФЗ из коробки.» · «Аудит и логи — Полный журнал запросов, масок, провайдеров и ошибок.» · Habr: «сервис может автоматически находить и маскировать персональные данные до отправки их в модель, а затем восстанавливать оригинальные значения в ответах.»
Checklist: 1 yes [C] · 2 not documented · 3 not documented · 4 not documented · 5 not documented · 6 not documented (SSE supported for tokens, demask unspecified) · 7–9 no · 10 NER module (TAdviser) [C] · 11 — · 12 cloud SaaS (+10% markup), vault residency not stated · 13 no.

---

## 6. GPTunneL — «Обфускатор персональных данных для LLM»

**URL:** https://www.gptunnel.ru/ru/b2b/obfuscator
**CHANGED since June:** product page now exists in a B2B form with on-prem Docker; not in the June sweep (was in the Sept-8 note as text-only restore).
Quotes: «Передавайте флаг «obfuscate: true» в POST /v1/chat/completions — данные автоматически маскируются до отправки в модель и восстанавливаются в ответе.» · «Буферизованный потоковый декодер для ответов в реальном времени — деобфусцирует чанки без задержек и разрыва плейсхолдеров.» · «Поставка в виде автономного Docker-образа для развертывания в локальной инфраструктуре или частном облаке организации.» · ticker: «детерминированные токены · … · Stateless-архитектура · On-Premises контур · Fail-Closed защита» · «0 байт сохраняемых данных (Stateless)» · FAQ: «Модель получает структурированные плейсхолдеры (например, <…> или <…>), которые однозначно определяют тип объекта и его роль в предложении.»
Checklist: 1 yes [C] · 2 **not documented** · 3 not documented · 4 no (placeholders) [C] · 5 «детерминированные токены» + stateless ⇒ same value → same token across turns by construction, canonicalisation not documented [C] · 6 yes (SSE) [C] · 7–9 no · 10 not documented · 11 n/a · 12 on-prem Docker; fail-closed claimed [C] · 13 «98,9% полнота детекции» (detection only) [C].

---

## 7. HiveTrace (AI Security Lab ИТМО / Raft) — DataClean + tool-call monitoring

**URLs:** https://hivetrace.ru · https://hivetrace.ru/news/release-4.2 · Cloud.ru deployment news 10.08.2026 (safe.cnews.ru, TAdviser)
**CHANGED since June:** 4.2 release — file scanning, tool-call monitoring/blocking, DataClean now covers the whole dialogue history.
Quotes: «DataClean проверяет всю историю диалога — Раньше DataClean на уровне шлюза обрабатывал только последнее сообщение пользователя. Теперь проверка и очистка чувствительных данных выполняются для всех сообщений, переданных в истории диалога.» · «Также мы добавили мониторинг вызовов инструментов AI-агентов» · title: «Релиз HiveTrace 4.2: от проверки файлов до блокировки tool calls» · session page tabs: «обзор, вызовы инструментов, файлы, очистка данных, цензоры и конфигурация валидации».
Checklist: 1 **not documented** (DataClean is described as очистка/monitoring; no restore mentioned anywhere) · 2 no (tool calls are monitored/blocked, not detokenised) [B] · 3 partial — history is cleaned, restoration absent · 4–9 no/— · 12 on-prem + Cloud.ru marketplace · 13 the Raft/HiveTrace study (baseline) remains the only RU measurement and explicitly excludes tool execution: «Исследование не охватывает восстановление данных или их передачу во внешние инструменты».
Note: the June 4.2 detail «до 4.2 обрабатывался только последний user message» is itself evidence of how immature the RU "guardrail" baseline was on multi-turn.

---

## 8. red_mad_robot — Guardrails / Daisy

**URLs:** YouTube «Как шифруют персональные данные при работе LLM?» (posted 2026-08-12, description) · Instagram reel 17.08.2026 · baseline redmadrobot.ru LLM-platform page
**CHANGED since June:** only marketing videos; no docs.
Quotes (video description / reel): «Перед отправкой запроса система находит персональные данные и заменяет их идентификаторами. Например, PERSON_1. Модель получает необходимый контекст, но не видит реальные данные пользователя. После генерации ответа система выполняет обратную замену.» · «Инструменты защиты данных используются и в Daisy gptdaisy.com — нашем сервисе для быстрого доступа к разным LLM.»
Checklist: 1 yes [C] · 2–3 not documented · 4 no (`PERSON_1`) [C] · 5–11 not documented/no · 12 not documented · 13 no.

---

## 9. AGIMA — internal LLM gateway (article, not a product)

**URL:** https://habr.com/ru/companies/agima/articles/1081356 — 11.09.2026, Андрей Непряхин (CTO AGIMA)
**Status:** «В AGIMA мы строим внутренний контур, через который сотрудники работают с LLM и агентами» — internal, no product name/URL. Useful as evidence of what a RU integrator considers the state of the art.
Quotes: «Модель может вернуть сущность в тексте, JSON, цитате, аргументах инструмента или потоковом ответе.» · «Для tool‑call — имя инструмента и аргументы до исполнения.» (checked, mechanism not described) · «регидрируются только токены, присутствующие в req_map текущего запроса» · «В проде session‑mapping живёт два часа, ограничен 500 токенами» · «Для streaming режим выбирается политикой: буфер … окно … или пропуск с пост‑сканом.» · «корректнее говорить «обратимая деперсонализация» или «псевдонимизация»».
Checklist: not a product; 2 mentioned as a check point only; 4 no (`NAME_1`); 5 session mapping 2h/500 tokens; 13 no.

---

## 10. Big platforms — Sber (GigaChat), Yandex (AI Studio), MTS (MWS AI Agents Platform / Cotype), VK Cloud, Selectel, T-Bank

Searched (Sep 2026, RU queries + domain-restricted to developers.sber.ru / yandex.cloud): **no PII-masking gateway product, no tool-call detokenisation, no guardrail of this class.** Yandex AI Studio agent docs describe Responses API, MCP Hub, tools, memory (30-day `response` objects) — nothing about masking; the platform sells «On-premises» and «Безопасность» as jurisdiction/locality. GigaChat API docs: functions, streaming, «все данные хранятся на серверах в РФ» — compliance by locality. MWS AI Agents Platform: on-prem platform + Cotype; the only Habr piece from MWS AI (AVI, external compliance filter, Habr 1056166) is a policy/compliance filter, not PII. Kaspersky / Positive Technologies / Solar / InfoWatch / Searchinform: searches returned market commentary only (Kaspersky blog 01.07.2026 on «серые» proxies; Solar webProxy «доступ к веб- и ИИ-ресурсам» = classic web DLP). Grade for "nothing exists": **[B]** (absence across vendor docs + trade press through Sep 2026).

## 11. SecureGPT (securegpt.ru)
«SecureGPT — корпоративная ИИ-платформа, развёрнутая на облачной инфраструктуре с аттестацией УЗ-1. Данные клиентов … не покидают защищённую инфраструктуру и не попадают к разработчикам ИИ-моделей.» — compliance by locality; no masking/restoration claims; not a gateway. Unchanged. [C]

## 12. Ideco / Brikko
No new primary material found after May 2026 (date-filtered searches empty). June verdicts stand: Ideco names tool-call control as the unsolved layer; Brikko: PII masking «в PRД расписан, в коде ещё не реализован», function calling «не реализовано». [D for "still unbuilt" — absence of evidence only]

---

## 13. Cross-product matrix (Sep 2026)

| Item | Cloud.ru OSS filter | provod.ai | StarGuard AI | Jay Guard | KodikRouter | GPTunneL Obf. | HiveTrace | red_mad_robot | Sber/Yandex/MTS/VK/Sel/T-Bank | Kaspersky/PT/Solar/DLP |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 Reversible | **yes [A]** | yes [C] | yes [C] | yes [B] | yes [C] | yes [C] | — | yes [C] | — | — |
| 2 Tool-args restored, JSON ok | **yes [A]** (proxy shape) | not doc. | no (policy only) | not doc. | not doc. | not doc. | no | not doc. | — | — |
| 3 Tool results re-masked | **yes [A]** / same-placeholder per request [B] | yes-masked [C] | not doc. | not doc. | not doc. | not doc. | history cleaned [C], no restore | not doc. | — | — |
| 4 Format-preserving | no | no | no | no | not doc. | no | — | no | — | — |
| 5 Multi-turn + canonicalisation | no (per request) | not doc. | not doc. | session id | not doc. | deterministic stateless [C] | — | not doc. | — | — |
| 6 Streaming (content + tool deltas) | **yes both [A]** | not doc. | not doc. | content (WS) [B] | not doc. | content [C] | — | — | — | — |
| 7 Agent's own form | no | no | no | no | no | no | no | no | — | — |
| 8 Memory echo | no | no | no | no | no | no | no | no | — | — |
| 9 Partial mentions / corrections | no | no | no | no | no | no | no | no | — | — |
| 10 RU morphology depth | regex+suffixes [A] | not doc. | lemmatisation [C] | ML NER [C] | NER [C] | not doc. | — | — | — | — |
| 11 Collisions | n/a (placeholders) | n/a | n/a | n/a | — | n/a | — | n/a | — | — |
| 12 On-prem / fail posture | on-prem, **fail-open** | SaaS, fail-closed | on-prem | on-prem opt. | SaaS | on-prem Docker, fail-closed | on-prem/Cloud.ru | — | locality | — |
| 13 Agent-unaffected measurement | no (detection F1 only) | no | no | no | no | no (98.9% detection) | Raft study excl. tools | no | — | — |

---

## 14. Verdict

**Q: Does ANY RU product cover items 2, 3, 7?**

- **Item 2 — YES, one product, since July 2026: Cloud.ru `guardrails-llm-filter`.** Restores placeholders inside `tool_calls[].function.arguments` (and Anthropic `tool_use.input`, Responses `function_call_arguments.delta`) with JSON escaping, non-stream and SSE, e2e-tested with quote/backslash values. In the reverse-proxy shape the client executes the tool, so the tool receives real values. Confidence **high [A]** — read in code, not in marketing. (provod.ai may also do it; its docs stop at «перед ответом клиенту» — **[C]/not documented**.)
- **Item 3 — PARTIAL YES (Cloud.ru; provod.ai on paper).** Tool results are scanned like any message before reaching the model. "Same substitute for the same person" holds only by exact-string dedup inside one request (and by resend order across turns); no canonicalisation, no vault, no conversation scope. HiveTrace 4.2 now cleans the whole history but documents no restore.
- **Item 7 — NO, nobody, high confidence.** Every RU product substitutes an opaque typed placeholder. That is precisely why item 2 is cheap for them and item 7 does not arise: a model cannot decline `<FIO_1>`; if it does glue a case ending or transliterate, restore fails or corrupts. No RU product restores a declined, transliterated, initialised, hyphen-joined or digit-reformatted substitute, because none mints substitutes that a model could plausibly rewrite.

**Owner's belief "nothing changed over the summer" — partly wrong.** The mechanism "restore inside tool-call JSON, keep JSON valid, stream it" is now on the RU market, free, Apache-2.0, on-prem, from a Sber-affiliated cloud, with a public comparison table against LiteLLM/Kong/Portkey/NeMo/LLM Guard/Presidio/Bedrock. Any pitch that says "мы единственные, кто восстанавливает подстановки в аргументах инструментов" is falsifiable as of 2026-07-06.

**What remains uncovered on the RU market (and is therefore the defensible claim):**
1. Format-preserving substitutes the model can reason and WRITE with (dialable fake phone, gendered fake name, checksum-invalid fake ID) — items 4, 11.
2. Restoration in the agent's own form — падеж, транслит, инициалы, дефис, переформатированные цифры — item 7.
3. A conversation-scoped persistent vault with canonicalisation (`+7`/`8`, declined forms), partial mentions, corrections, memory-echo policy — items 5, 8, 9.
4. Spoken/dictated numbers, lowercase chat register, addresses without a type word — item 10 beyond regex.
5. A published tool-call-fidelity measurement (three-arm, TOST) — item 13. The only RU measurement (Raft/HiveTrace, 102 requests) explicitly excludes restoration and tool execution.
6. Fail-closed posture: Cloud.ru's filter is fail-open BY INVARIANT («Вердикта «заблокировать» в пайплайне не существует»; unparsable body passes unmasked). provod.ai and GPTunneL claim fail-closed but are placeholder-based and (provod) cloud-only.

**Honest counter-point for the owner:** the Raft/HiveTrace study found `PERSON_1`-style pseudonymisation costs the agent ≈nothing on answer quality. So the placeholder camp's design is not naive — the argument for format-preserving substitutes must be made on the tool-call axis (agent writes the value into a CRM field, restores must be verbatim and morphologically right) and on multi-turn/memory coherence, which is exactly what no RU vendor measures.

---

## 15. Changes flagged since June 2026 (summary list)

| Date | Change | Source |
|---|---|---|
| 2026-07-06 | Cloud.ru open-sources `guardrails-llm-filter` v0.1.0 (Envoy ext_proc); later standalone HTTP proxy; tool-call args + SSE demask; tool results masked | GitHub CHANGELOG, README; cloud.ru release notes «Июль» |
| 2026-07-22 | Orion soft announces StarGuard AI (LLM firewall, `<PERSON_1>` masking, tool-call allow/deny policies, on-prem) | Habr 1061756 |
| Jul–Aug 2026 | provod.ai ships masking v1 covering tool-call args + tool results, fail-closed, per-request pseudonyms (docs updated 17.08.2026) | provod.ai/ru/docs/data-protection |
| 2026-08-10 | HiveTrace AI Firewall deployed in Cloud.ru; HiveTrace 4.2: DataClean over full dialogue history, tool-call monitoring/blocking | hivetrace.ru/news/release-4.2; safe.cnews.ru |
| 2026-08-12 | red_mad_robot publishes explainer video on `PERSON_1` pseudonymisation with reverse replacement (Daisy) | YouTube description |
| 2026-09-11 | AGIMA CTO describes internal gateway with request-scoped `NAME_n` mapping (2h/500 tokens); names tool-call args as a check point | Habr 1081356 |
| — | Jay Guard, KodikRouter, GPTunneL: no change in documented scope (text/response restore, streaming); no tool-call docs | vendor docs |
| — | Sber/Yandex/MTS/VK/Selectel/T-Bank/Kaspersky/PT/Solar/InfoWatch/Searchinform: nothing of this class found | searches Sep 2026 |
