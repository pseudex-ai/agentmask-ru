# Покрытие агентных сценариев с ПД: что меряет v4, чего не меряет, и как выводить недостающее

Дата: 2026-09-05. Вопрос владельца: «мы собирали кейсы через призму того, что должен решать наш проект, и каждый раз находили новое; надо детально исследовать покрытие агентных сценариев в реальных бизнес-задачах — CRM, аналитика, саппорт, продажи, колл-центры, — и понять, как такие кейсы ВЫВОДИТЬ, а не находить по озарению. Прав я или нет?»

## 0. Ответ

**Прав в диагнозе, не совсем прав в адресе.** Корпус v4 строился по одной оси — *что агент делает со ЗНАЧЕНИЕМ* (derive, decompose, compare, chain, correction, validate, container, result_feed, summary). Эта ось теперь покрыта хорошо и почти исчерпана (свежие seed-ы 6060/5150/8080 находят по 0–1 утечке). Но реальный агент CRM/саппорта/колл-центра ломается ещё по трём осям, которые корпус не моделирует:

1. **Ось потока** — *откуда ПД приходит и куда уходит* (память между сессиями, handoff другому агенту, результат поиска на десять записей, батч/экспорт, шаблон рассылки, эскалация человеку с саммари, фоновые задачи без беседы).
2. **Ось поверхности инструмента** — *роль поля*: ключ поиска (`?query=`, `findbycomm`), свободный текст (`note.text`, `message`), плейсхолдер шаблона (`{{name}}`), батч (`importContacts`, CSV), обязательные ПД в чеке (54-ФЗ), реквизиты с паспортом (`RQ_IDENT_DOC_*`).
3. **Ось «где ещё ходят ПД»** — вне аргументов инструмента: память (LangGraph Store, Mem0, ADK, memory tool), fork/subagent memory, переписанный RAG-запрос, трассы наблюдаемости (Langfuse пишет всё по умолчанию), webhooks/background без живой беседы.

«Обычные кейсы CRM/саппорта/продаж» — это не про домены (домены у нас те же самые: amoCRM, ЮKassa, СДЭК, ЕМИАС), а про **потоки внутри домена**. Самое важное, чего ты не сказал: часть этих потоков ломает не детекцию и не восстановление, а **саму модель области беседы**, на которой стоит волт (`minted_in`). Это решение продукта, а не баг — и его надо принять осознанно (§4).

## 1. Что покрыто сейчас (инвентарь v4, 360 случаев)

| ось | покрыто | замечание |
|---|---|---|
| преобразование значения | 9 семейств: derive 54, chain 48, compare 42, decompose 42, result_feed 36, correction 36, validate 36, summary 36, container 30 | ось построена и измерена; остаток на свежих seed-ах ≈ 0–1 утечка/1020 |
| инструменты | 11: courier_book 92, crm_find_contact 84, notify_sms 63, crm_upsert_contact 62, clinic_book 50, passport_verify 50, delivery_create_order 49, address_suggest 42, crm_import_csv 15, payment_create 14, callback_schedule 13 | все — «одна запись на вызов»; нет поиска, возвращающего список; нет заметки/тикета со свободным текстом; нет шаблона с плейсхолдерами; нет экспорта |
| регистры | voice_raw 118, chat 107, voice_itn 78, sloppy 51, clean 6 | достаточно |
| длина беседы | 1 реплика 198, 2 — 114, 3 — 48 | нет бесед длиннее трёх реплик, нет второй сессии |
| типы ПД | NAME 563, LOC 448, PHONE 407, DOB 113, EMAIL 91, SNILS 50, PASSPORT 50, CARD 14 | нет ИНН физлица в реквизитах, нет email как ключа поиска, нет номера заказа рядом с ПД (то, что НЕ надо маскировать) |
| где ПД | сообщение 1022, seed (карточка мока) 714 | результат инструмента — только «своя» запись; нет чужих записей в результате (соседи по поиску) |

## 2. Что нашли пробы за $0 (движок на 36aada2)

* **Память между сессиями (главное).** Подмена «Ершов Константин Юрьевич», выданная в беседе A, «вспомнена» агентом в беседе B как текст памяти в промпте:
  — новая `conversation_id` → перечеканка, инструмент получает **фейк из A** как настоящее значение, 200 OK, `residual` пуст;
  — без `conversation_id`, или тот же id (память ключуется по клиенту) → верно;
  — токен из A прямо в аргументе инструмента в B (memory tool → arg) → верно (точный поиск токена по клиенту).
  Причина — область беседы у `is_minted_token` (защита от прямой коллизии, CLAUDE.md). Ветка C подтверждает, что это не экзотика: LangGraph Store, Mem0, Google ADK, memory tool Anthropic ключуют память по `user_id`, а не по беседе; `fork` в Agent SDK дублирует транскрипт под новым id; Microsoft Agent Framework при handoff держит отдельную сессию на каждого агента.
* **Несколько людей в одной фразе + ключ.** «клиенты: сидоров иван из самары и петрова анна из казани» — слой ключ→значение типизировал весь абзац как ОДНО имя (девять слов), города исчезли из вида модели, считать «по городу» стало нечего. Починено (36aada2): значение под ключом имени должно иметь форму имени. Это ровно «аналитический» регистр.
* **Результат поиска на 12 однофамильцев** («Смирнова Ольга» × 12 с разными телефонами) — одна подмена имени на всех (по построению: одно значение — одна подмена), телефоны разные; агент выбирает по телефону верно. Не дефект, но модель видит двенадцать одинаковых имён — как и в контроле.
* **Шаблон с плейсхолдерами** `{name}` — плейсхолдер не трогается, подставленное значение восстанавливается. Не проверено на живой модели.

## 3. Карта: домен × поток × где стоит ПД (ветка A, первоисточники)

Потоки, описанные в документации вендоров (оценки: A — прочитано в API-справочнике, B — официальная страница/справка, C — сторонний клиент, D — не найдено):

| поток | инструменты (реальные) | роль поля с ПД | покрыт в v4? | оценка |
|---|---|---|---|---|
| Идентификация звонящего по номеру до ответа | телефония (caller-ID) → `crm.contact.list`/`?query=`/`findbycomm` | ключ поиска | частично (`crm_find_contact` по телефону) | B |
| Поиск дублей и слияние перед записью | `crm.duplicate.findbycomm` (только phone/email) → `crm.entity.mergeBatch` | ключ поиска, результат — список чужих записей | **нет** | B |
| Карточка/сделка из звонка: регистрация → запись → транскрипт → заметка | `telephony.externalcall.*`, `attachTranscription`, `notes` (`params.text`, `params.phone`) | свободный текст с ПД внутри | **нет** (нет инструмента «заметка») | B |
| Эскалация человеку с саммари | Yandex AI Speech, МТС Exolve: «саммари в CRM», «сотрудник получает причину и историю» | свободный текст, модель ПИШЕТ саммари | частично (summary без инструмента) | B |
| Предсказание темы по истории транзакций | Sber: 45% тем угадываются до речи | результат инструмента с чужими данными | **нет** | B |
| Верификация по ДР/цифрам паспорта | нигде не задокументировано как API-поток | — | есть (validate/decompose), но источник — наше предположение | D |
| Шаблонная рассылка с подстановкой | Exolve `SendSMS`, Unisender, SMS Aero — именованные переменные в теле | плейсхолдер + свободный текст | **нет** (notify_sms без шаблона) | A/B |
| Оплата и чек 54-ФЗ | ЮKassa `customer.{full_name,email,phone,inn}`, T-Bank `Receipt.{Email,Phone}` — ровно одно обязательно | структурное поле, ОБЯЗАТЕЛЬНОЕ ПД | частично (payment_create без чека) | A |
| Реквизиты с паспортом/ИНН | Bitrix24 `crm.requisite` `RQ_IDENT_DOC_SER/NUM`, `RQ_INN` | структурное поле | **нет** | B |
| Нормализация перед записью | DaData `clean/phone` (страна/город/провайдер/часовой пояс), `clean/address` | инструмент-препроцессор, возвращает ПД в другой форме | частично (address_suggest) | B |
| Импорт/экспорт списков | Unisender `importContacts` (≤500 за вызов), CSV | батч | частично (crm_import_csv на 2 строки) | A/B |

Не найдено ни одного первоисточника, где бот колл-центра спрашивает ДР или цифры паспорта для верификации — наша семья `validate` стоит на предположении, а не на документе. Это стоит записать честно, а не считать доказанным.

## 4. Где ещё ходят ПД, кроме аргументов инструмента (ветка C, первоисточники)

| путь | что несёт ПД | ключ | через сессии | текст модели или дословный | следствие для подмены, ограниченной беседой |
|---|---|---|---|---|---|
| LangGraph `Store` | JSON-факты, записанные кодом/инструментом | `user_id` | да | обычно модели | записано в A, читается в B → перечеканка → фейк в инструмент |
| Mem0 | LLM-извлечённые «факты» | `user_id` | да | парафраз модели | то же; идентификаторы обычно сохраняются в подстроках, но не гарантированно |
| Anthropic memory tool | файлы `/memories`, пишет Claude | без области на уровне протокола | да, явно | дословный | границы нет вовсе; Anthropic сама пишет, что чистить ПД должен интегратор |
| Agent SDK `fork`, subagent `memory: user/project` | полный транскрипт / каталог памяти | новый `session_id` | да | дословный | транскрипт с токенами под новым id |
| Google ADK Memory | транскрипт или консолидированные факты | `app_name`+`user_id` | да | зависит от бэкенда | как Store/Mem0 |
| Microsoft Agent Framework handoff | broadcast сообщений между ОТДЕЛЬНЫМИ `AgentSession` | по агенту | да, структурно | дословный | N идентичностей сессии на одну беседу; аргументы вызовов не транслируются |
| OpenAI Agents SDK handoffs, LangGraph subgraphs | история в том же run/thread | тот же | нет по умолчанию | дословный | безопасно, риск только opt-in (`input_filter`, приватная история) |
| RAG: переписанный запрос | «standalone question», сгенерированный моделью | — | — | модели | в ретривер/лог уходит подмена или настоящее — шлюз, маскирующий только реплику, этого не видит |
| RAG: подмешанные документы | записи клиентов в промпте | — | — | дословно источник | если подмешаны ПОСЛЕ маскирования — настоящие ПД у модели |
| Langfuse / OTel GenAI | промпты, ответы, аргументы — по умолчанию целиком | trace id | отдельное хранилище | дословный | вторая, дольше живущая копия ПД; нужен явный `mask` |
| OpenAI webhooks / background | только id в payload; контент забирается отдельно | `response.id` | да | дословный | нет точки, где маскировать/восстанавливать |
| Intercom Fin handoff человеку | один объект транскрипта | conversation id | нет внутри платформы | дословный | человек видит ПОДМЕНЫ, если путь передачи не восстанавливает |

## 5. Как выводить сценарии системно (метод вместо озарения)

1. **Из схем инструментов.** Для каждого реального API (§3) перечислить поля с ПД и их РОЛЬ: ключ поиска / свободный текст / плейсхолдер / батч / экспорт / обязательное поле чека / реквизит. Каждая роль — отдельный класс поведения шлюза: ключ поиска требует канон, свободный текст — восстановление в прозе, плейсхолдер — нетронутый шаблон, батч — N людей в одном значении, экспорт — ПД к модели не идёт вовсе.
2. **Из операций над человеком.** Матрица «что делает оператор» × «где стоит ПД»: найти / проверить / обновить / слить / уведомить / эскалировать / записать заметку / отчитаться. Каждая клетка — сценарий; пустые клетки корпуса — §6.
3. **Из архитектуры.** Пути ПД вне аргументов (§4): память, handoff, RAG, трассы, фон. Для каждого — ответ на вопрос «что видит модель и что получает инструмент, если подмена ограничена беседой».
4. **Из чужих данных, не из наших генераторов.** Регистры и формулировки брать из корпусов, которых мы не писали (MASSIVE, RuDevices, PII-Bench уже так используются); для потоков — из таксономий чужих агентных бенчмарков (§7).
5. **Критерий включения.** Сценарий добавляется в корпус, если он меняет ПОВЕДЕНИЕ агента (переспрос, пропущенный вызов, другая идентичность, чужие данные в инструменте), а не только форму значения. Проверка: сначала скриптовым агентом за $0 на свежем seed, потом живой small по семейству.

## 6. Приоритизированный список непокрытого

| # | сценарий | ожидаемый класс дефекта | как проверить | цена |
|---|---|---|---|---|
| 1 | Память между сессиями: факт из беседы A в промпте беседы B | фейк из A в инструменте (доказано пробой) | решение по области подмены (§8), затем семья `memory` в v4 | $0 + живой |
| 2 | Поиск, возвращающий СПИСОК чужих записей (дубли, однофамильцы, соседи) | одна подмена на однофамильцев; связь «нужная запись ↔ подмена»; Б8 на соседях | семья `lookup_list` | $0 |
| 3 | Заметка/тикет со свободным текстом, куда модель ПИШЕТ саммари с ПД | восстановление прозы внутри аргумента (Б11 на плече инструмента) | инструмент `crm_note`/`ticket_create` | $0 |
| 4 | Шаблон рассылки с плейсхолдерами + подстановка | плейсхолдер повреждён или подстановка в неверной форме | инструмент `send_template` | $0 |
| 5 | Чек 54-ФЗ: одно из email/phone обязательно | фейк email в чеке → фискальный отказ | `payment_create` с `receipt.customer` | $0 |
| 6 | Реквизиты: паспорт/ИНН в структурном объекте (`RQ_IDENT_DOC_*`) | ключ типизирует, серия/номер отдельно (уже есть кусок) | семья `requisites` | $0 |
| 7 | Handoff другому агенту с отдельной сессией | как №1 | архитектурное решение | — |
| 8 | Эскалация человеку: саммари для оператора | человек видит подмены | путь восстановления на выходе к человеку (есть `/unmask`), сценарий в корпусе | $0 |
| 9 | Аналитика: N людей в одной фразе, агрегат по городу/дате | слияние людей (починено 36aada2), город в подмене (настоящий — верно) | семья `analytics` | $0 |
| 10 | Нормализация DaData `clean/phone` как инструмент-препроцессор | результат в другой форме → вторая подмена (Б8) | `result_feed` с `clean/phone` | $0 |
| 11 | Долгие беседы (5–10 реплик) с возвратом к человеку через несколько ходов | идентичность через реплики, `place_parts` за сутки | удлинить генератор | $0 |
| 12 | Трассы наблюдаемости и фоновые задачи | ПД мимо шлюза | документация/интеграция, не корпус | — |

## 7. Паттерны чужих агентных бенчмарков (ветка B, первоисточники: статьи и репозитории)

Что перечисляют 15 публичных бенчмарков агентов с инструментами (● есть, ◐ частично, ○ нет, пусто — не применимо):

| Pattern | τ-bench | τ²-bench | CRMArena | CRMArena-Pro | AppWorld | ToolSandbox | AgentDojo | BFCL v3 | BFCL v4 | WorkArena(++) | WorkBench | LoCoMo | LongMemEval | MemBench | BEAM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Lookup by identifier | ● | ● | ● | ● | ◐ | ● | ◐ | ● | ◐ | ● | ● | | | | |
| Identity verification challenge | ● | ● | ○ | ○ | ○ | ○ | ○ | ● | ◐ | ○ | ○ | | | | |
| Multi-entity comparison | ○ | ○ | ● | ● | ○ | ○ | ○ | ○ | ○ | ● | ○ | | | ○ | |
| Batch operation | ◐ | ◐ | ○ | ○ | ● | ○ | ◐ | ● | ● | ● | ○ | | | | |
| Cross-session memory recall | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ● | ◐ | ○ | ● | ● | ● | ● |
| Handoff/escalation with summary | ◐ | ◐ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | | | | |
| Policy-gated refusal | ● | ● | ○ | ● | ○ | ○ | ○ | ◐ | ◐ | ● | ○ | | | | |
| Templated outbound message | ○ | ○ | ○ | ○ | ● | ● | ● | ● | ● | ◐ | ● | | | | |
| Aggregation/report over many records | ○ | ○ | ● | ● | ◐ | ○ | ○ | ○ | ○ | ● | ○ | ○ | ◐ | ● | ○ |
| Correction of an earlier value | ● | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ● | ● | ● |
| Tool result fed into next tool | ● | ● | ● | ● | ● | ● | ◐ | ● | ● | ● | ● | ○ | ○ | ○ | ○ |
| Missing-parameter clarification | ◐ | ◐ | ○ | ○ | ○ (forbidden) | ● | ○ | ● | ● | ○ | ○ | | | | |
| Prompt-injection via tool result | ○ | ○ | ○ | ○ | ○ | ○ | ● | ○ | ○ | ○ | ○ | | | | |

Что это значит для нас:

* **«Результат инструмента → следующий инструмент»** и **«поиск по идентификатору»** — почти универсальны, и почти всегда ключ поиска — это ПД (имя, email, телефон, имя+индекс/ДР). У нас — `result_feed`, `chain`, `crm_find_contact` по телефону: покрыто, но только с ОДНОЙ записью в ответе.
* **Верификация личности** как реальный шлюз — только τ-bench/τ²-bench (email или имя+индекс/ДР) и BFCL v3. Наш `validate` (контрольная сумма) — другая вещь; «спроси ДР и сверь с карточкой» у нас нет, а это единственная документированная форма верификации.
* **Память между сессиями** — только бенчмарки памяти (LoCoMo, LongMemEval, MemBench, BEAM) и новая категория BFCL v4; ни один CRM/retail/travel-бенчмарк её не проверяет. Это подтверждает §2: класс существует и никем в нашей нише не измерен.
* **Исправление ранее названного значения** — τ-bench проверяет на самом ключе поиска (клиент сам поправляет индекс), бенчмарки памяти — как «обновление знания». У нас `correction` есть, но только внутри одной реплики/беседы; исправления через сессию нет.
* **Конфиденциальность между клиентами** проверяет один CRMArena-Pro, и судит по ЯЗЫКУ отказа, а не по факту утечки строки — слабее нашего типоориентированного счётчика утечек. **Целевая инъекция через результат инструмента** (вытащить ПД одного человека) — ни у кого; AgentDojo — только массовая.
* **Агрегат по многим записям** — CRMArena/-Pro, WorkArena, MemBench («сколько людей живёт в X»). У нас нет ни одного случая.
* **Уточнение недостающего параметра** — BFCL/ToolSandbox формализуют как категорию; AppWorld ЗАПРЕЩАЕТ агенту спрашивать. Наш главный класс расхождений на живой модели («переспросил вместо вызова») — как раз то, что чужие бенчмарки считают либо нормой, либо запретом; наша метрика L3 наказывает за это агента, а не шлюз, если C тоже спросил — C′≈C пол это и ловит.

## 8. Решение, которое надо принять (не техническое)

Область подмены сейчас — беседа: это то, что делает связь коротких упоминаний осмысленной и защищает от «настоящий носитель подмены пришёл из другой беседы». Память агента, fork и handoff-по-сессиям все ключуются по КЛИЕНТУ. Варианты:

* **A. Хост даёт стабильный id уровня клиента**, когда включена память (id пользователя = `conversation_id`). Ноль изменений в движке; связь коротких упоминаний остаётся внутри id; цена — правило единственного кандидата работает на весь трафик клиента этого пользователя (для одного человека это по-прежнему мало).
* **B. Режим `scope=customer` для `is_minted_token`** (подмена, выданная этому заказчику где угодно, считается нашей), связь адресов остаётся по беседе. Возвращает прямую коллизию, измеренную на NEREL как 2–3 на 2979 человек.
* **C. Помечать блоки памяти** (хост говорит «это память») — сложнее для интегратора, зато точно.

Рекомендация: A по умолчанию с документированным требованием к хосту, B как явный флаг. Проверить на v4 семьёй `memory` в обеих конфигурациях.

## 9. Чего не делать

* Не расширять `validate`: верификация по ДР/паспорту не найдена ни в одном первоисточнике (§3, D).
* Не добавлять домены ради доменов (банк, страхование, HR): поверхности инструментов те же — ключ/текст/шаблон/батч/чек; новые **потоки** важнее новых **вывесок**.
* Не чинить «12 однофамильцев с одной подменой» — это модель реальности, контроль видит то же.

## 10. Источники

Полные таблицы с URL первоисточников — ниже (перенесены из отчётов веток дословно).

### A: tool surfaces (primary URLs)
| Domain | Product | Endpoint / tool | PII fields (exact names, format) | Field role | Primary URL | Grade |
|---|---|---|---|---|---|---|
| CRM | amoCRM v4 | `POST/PATCH /api/v4/contacts` | `name`, `first_name`, `last_name`; `custom_fields_values[].field_code = "PHONE"/"EMAIL"` with `values[].value` + `values[].enum_code` (`WORK`/`MOBILE`/`WORKDIRECT`/`HOME`) | search key (`?query=`) + free-form custom field | https://www.amocrm.ru/developers/content/crm_platform/contacts-api | B |
| CRM | amoCRM v4 | `GET /api/v4/contacts?query=` | any populated field (phone/email/name) — "поиск по заполненным полям сущности" | search key | same as above | B |
| CRM | amoCRM v4 | `POST/PATCH /api/v4/leads`, `POST /api/v4/leads/complex` | `custom_fields_values[].field_id/values[].value`; `_embedded.contacts[].id/is_main` (links a lead to the PII-bearing contact) | free text (custom field) + linkage | https://www.amocrm.ru/developers/content/crm_platform/leads-api | B |
| CRM | amoCRM v4 | `POST/PATCH /api/v4/{entity_type}/notes` | `note_type`: `common`, `call_in`, `call_out`, `sms_in`, `sms_out`, `geolocation`, `attachment`, `service_message`; `params.text` (free text); call params: `params.phone`, `params.duration`, `params.uniq`, `params.link`, `params.source` | free text / call metadata (phone) | https://www.amocrm.ru/developers/content/crm_platform/events-and-notes | B |
| CRM | amoCRM v4 | `POST/PATCH /api/v4/tasks` | `text` (free text, mandatory), `task_type_id`, `complete_till`, `entity_type`, `entity_id`, `result.text` | free text | https://www.amocrm.ru/developers/content/crm_platform/tasks-api | B |
| CRM | Bitrix24 REST | `crm.contact.add/update/get/list` | `NAME`, `LAST_NAME`, `SECOND_NAME`; `PHONE`/`EMAIL` = arrays of `{VALUE, VALUE_TYPE}` | search key (exact match only on PHONE/EMAIL/WEB/IM/LINK; `%`/`=%` LIKE works on NAME/LAST_NAME) | https://apidocs.bitrix24.ru/api-reference/crm/contacts/index.html , https://apidocs.bitrix24.ru/api-reference/crm/contacts/crm-contact-list.html | A |
| CRM | Bitrix24 REST | `crm.duplicate.findbycomm` | `type` = `PHONE`/`EMAIL`, `values[]` (array of numbers/addresses), optional `entity_type` = `LEAD`/`CONTACT`/`COMPANY` | search key (duplicate/merge lookup) | https://apidocs.bitrix24.ru/api-reference/crm/duplicates/crm-duplicate-find-by-comm.html | B (page opened via search-snippet extraction, not raw fetch) |
| CRM | Bitrix24 REST | `crm.requisite.add/update/get/fields` (company & person legal/identity requisites) | `RQ_INN`, `RQ_KPP`, `RQ_OGRN`, `RQ_OGRNIP`, `RQ_NAME`, `RQ_FIRST_NAME`, `RQ_LAST_NAME`, `RQ_SECOND_NAME`, `RQ_EMAIL`, `RQ_PHONE`, `RQ_FAX`; identity-document sub-fields `RQ_IDENT_DOC` (тип), `RQ_IDENT_DOC_SER`, `RQ_IDENT_DOC_NUM`, `RQ_IDENT_DOC_DATE`, `RQ_IDENT_DOC_ISSUED_BY`, `RQ_IDENT_DOC_DEP_CODE`; address is a separate `RQ_ADDR` requisite-address field (sub-fields `ADDRESS_1`, `ADDRESS_2`, `CITY`, `REGION`, `PROVINCE`, `POSTAL_CODE`, `COUNTRY` per a third-party integration guide) | structured KV (passport series/number, INN, address) — the single richest native PII surface found in either CRM's docs | https://apidocs.bitrix24.ru/api-reference/crm/requisites/universal/crm-requisite-fields.html | A (field list) / C (address sub-fields, from a third-party guide, not the primary page) |
| CRM | Bitrix24 REST | `telephony.externalcall.register/show/hide/finish`, `telephony.externalcall.attachRecord`, `telephony.call.attachTranscription`, `telephony.externalcall.searchCrmEntities` | call identifiers `CALL_ID`, `EXTERNAL_CALL_ID`, `USER_ID`; phone number passed to `searchCrmEntities` to resolve a CRM entity; recording attached via `attachRecord`; transcript text via `attachTranscription` | search key (phone→CRM entity) + free text (transcript) | https://apidocs.bitrix24.ru/api-reference/telephony/index.html | B |
| CRM | RetailCRM v5 | `customers/create`, `customers/{id}/edit` | `firstName`, `lastName`, `phones` (array), `email`, `birthday`; nested `address` object: `index`, `countryIso`, `region`, `regionId`, `city`, `cityId`, `street`, `streetId`, `building`, `flat`, `floor`, `house`, `metro`, `notes`, `text` | structured KV + free text (`address.text`, `address.notes`) | https://docs.retailcrm.ru/Developers/API (index only opened directly; `Address` struct confirmed via official Go SDK) | C (struct read from `github.com/retailcrm/api-client-go`, not the HTML doc page itself, which 404'd on direct fetch) |
| CRM/booking | YClients | `GET clients/{company_id}` (list/search), `POST clients/{company_id}` (add), `PUT/DELETE client` | `phone`, `fullname`/`name`, `email`, `comment`, `code` (search fields include `phone`, `name`) | search key (phone/name/email filter) + free text (`comment`) | https://developers.yclients.com/ru/ (index page only; content behind interactive console, not fetchable) — confirmed via official-style third-party PHP client | C |
| Booking | YClients | `book_record` (create appointment) | client sub-object: `phone`, `fullname`, `email`, `comment`; `code` (SMS confirmation code, via `book_code`) | free text (`comment`) + template placeholder target (confirmation SMS) | same as above | C |
| Support ticketing | Usedesk | `POST https://secure.usedesk.com/uapi/create/ticket` | `client_name`, `client_email`, `client_phone`, `subject`, `message` (free text), custom fields via `field_id`/`field_value` | free text (`message`) + search/identify key (`client_email`/`client_phone` used to match/create a client record) | https://api.usedocs.com/article/51378 | B |
| Support ticketing | Zendesk (reference "Zendesk-like") | Tickets API / Ticket Requests API | requester email/name inside `ticket.requester`, ticket `comment.body` (free text) | free text + identity key | https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/ (indexed via search only, not opened directly this pass) | D |
| Telephony/callback | Mango Office VPBX | REST callback events; outbound-call trigger API | `from_number`/`to_number`, `from_extension`/`to_extension`, `command_id` (call id), `recording_id`; webhook payload documented only in the vendor PDF (`MangoOffice_VPBX_API.pdf`), not opened this pass | search key (phone) + call metadata + recording link | https://www.mango-office.ru/support/integratsiya-api/restapivatshelp/obshchie_voprosy_po_api_vats_mango_office/ | C (field names taken from third-party PHP client code samples referenced on the vendor help page; the authoritative PDF was not opened) |
| Telephony/callback | Zadarma API | Webhook events `notify_start`, `notify_internal`, `notify_answer`, `notify_end`, `notify_out_start`, `notify_out_end`, `notify_record`, `notify_ivr`; `GET /v1/pbx/internal/<PBXSIP>/info/` | `call_id`, `pbx_call_id`, `clid` (caller id), `sip`, `callstart`, `disposition`, `seconds`, `is_recorded`, `caller_id`, `record_email` | call metadata / search key (`clid`) | https://zadarma.com/en/support/api/ | B |
| SMS | МТС Exolve | `POST https://api.exolve.ru/messaging/v1/SendSMS` | `number` (sender), `destination` (recipient phone), `text` (free text, supports named variables for templated/transactional SMS) | template placeholder + free text | https://docs.exolve.ru/docs/ru/api-reference/sms-api/ | A |
| SMS | SMS Aero | `GET https://gate.smsaero.ru/v2/sms/send?number=&text=&sign=` | `number` (recipient phone), `text` (free text/template), `sign` (sender name) | template placeholder + free text | https://smsaero.ru/integration/ | B |
| Email/SMS marketing | Unisender | `sendSms` (SMS API), `importContacts`/`createList` (Contacts API) | `phone`, `sender`, `text` for SMS; `importContacts.fields`/`data` map arbitrary customer fields (name/phone/email) into Unisender fields, ≤500 contacts/call; message bodies support `{{...}}`-style substitution tags ("подстановки") for personalization | batch import (≤500/call) + template placeholder | https://www.unisender.com/ru/support/api/common/sms-rassylka/ , https://www.unisender.com/ru/support/api/contacts/createlist/ | B |
| Data enrichment/cleansing | DaData | `POST https://cleaner.dadata.ru/api/v1/clean/phone` | request: `source` (raw phone string); response: `phone`, `country_code`, `city_code`, `number`, `extension`, `provider`, `country`, `region`, `city`, `type`, `timezone`, `qc`, `qc_conflict` | normalization/enrichment of a search key | https://dadata.ru/api/clean/phone/ | A |
| Data enrichment/cleansing | DaData | `POST /api/v1/clean/address` (not opened directly this pass; existence + field categories confirmed via search of dadata.ru/api pages) | breaks a free-text address into region/city/street/house/flat + KLADR/FIAS(GAR)/OKATO/OKTMO/postal index | normalization of free text into structured PII | https://dadata.ru/api/clean/address/ | C |
| Payments | ЮKassa (YooMoney) | `POST https://api.yookassa.ru/v3/receipts` | `customer.full_name`, `customer.email`, `customer.phone` (numeric, e.g. `79000000000`), `customer.inn` | structured KV, required for 54-ФЗ fiscal receipt | https://yookassa.ru/developers/payment-acceptance/receipts/54fz/other-services/payments | A |
| Payments | T-Bank (Tinkoff) Kassa / eACQ | `Init`/`Confirm` — `Receipt.Email` (≤64 chars), `Receipt.Phone` (format `+{digits}`, ≤64 chars) — exactly one of the two is required; `Receipt.Taxation`, `Receipt.Items[]` (`Name`,`Price`,`Quantity`,`Amount`,`Tax`); top-level `DATA` (free-form key/value, ≤20 pairs, key ≤20 / value ≤100 chars) | structured KV (fiscal receipt) + free-form KV bag (`DATA`) | https://developer.tbank.ru/eacq/api/init | A |
| Contact-centre AI | Yandex AI Studio — AI Speech | Realtime API for voice agents | no field-level API schema surfaced on the product page; described capability: agent gives the operator prompts mid-call and "автоматически формирует саммари с сохранением результатов в CRM и аналитических системах" (auto-generates a summary and saves it to CRM) | free text (summary) written back into CRM | https://aistudio.yandex.ru/ru/ai-speech | B |
| Contact-centre AI | Sber SaluteSpeech (case study, Sberbank contact centre) | n/a (case study, not an API page) | no fields; flow only: virtual assistant "Афина" resolves 68% of calls fully, predicts call topic for 45% of calls from transaction data before the customer speaks, routes complex requests to a human operator | n/a — process description only | https://developers.sber.ru/portal/cases/sberbank-call-center | B (case study explicitly does **not** describe identity verification, transcript, or handoff-summary fields — noted as absent, not assumed) |
| Contact-centre AI | МТС Exolve — "Робот-оператор" | product page (no public field-level API schema) | described flow only: "Робот определяет абонента по данным из CRM и начинает диалог без ожидания на линии" (identifies caller from CRM data); "Сотрудник получает звонок вместе с причиной обращения и историей диалога с роботом" (operator receives call + reason + dialogue history); "После разговора система сохраняет запись разговора и статус обращения в карточке клиента в CRM" (saves recording + status to the CRM card) | identify-by-phone/CRM-lookup + handoff-with-context + write-back to CRM card | https://exolve.ru/products/robots/robot-operator/ | B |

### C: PII paths outside tool arguments (primary URLs)
[A]
[B] (Anthropic
[B] (help-center article, well-corroborated by search extraction; not independently re-verified by direct fetch of the full page)
https://adk.dev/sessions/memory/
https://code.claude.com/docs/en/agent-sdk/sessions
https://code.claude.com/docs/en/sub-agents
https://developers.openai.com/api/docs/guides/background
https://developers.openai.com/api/docs/guides/webhooks
https://docs.langchain.com/oss/python/langchain/long-term-memory
https://docs.langchain.com/oss/python/langgraph/use-subgraphs
https://docs.mem0.ai/platform/quickstart
https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md
https://google.github.io/adk-docs/sessions/memory/
https://langfuse.com/docs/observability/features/masking
https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff
https://openai.github.io/openai-agents-python/handoffs/
https://openai.github.io/openai-agents-python/sessions/
https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
https://reference.langchain.com/python/langchain-classic/chains/history_aware_retriever/create_history_aware_retriever
https://www.anthropic.com/engineering/contextual-retrieval
https://www.intercom.com/help/en/articles/7995955-hand-over-fin-ai-agent-conversations-to-another-support-tool

### B: benchmarks (primary URLs)
- https://ar5iv.labs.arxiv.org/html/2407.18901
- https://ar5iv.labs.arxiv.org/html/2408.04682
- https://arxiv.org/abs/2510.27246
- https://arxiv.org/html/2402.17753
- https://arxiv.org/html/2406.13352v3
- https://arxiv.org/html/2410.10813v1
- https://arxiv.org/html/2506.21605
- https://arxiv.org/pdf/2406.12045
- https://arxiv.org/pdf/2506.07982
- https://github.com/StonyBrookNLP/appworld
- https://github.com/apple/ToolSandbox
- https://github.com/import-myself/Membench.
- https://github.com/mohammadtavakoli78/BEAM
- https://github.com/sierra-research/tau-bench
- https://github.com/sierra-research/tau2-bench
- https://github.com/snap-research/locomo.
- https://github.com/xiaowu0162/LongMemEval.
