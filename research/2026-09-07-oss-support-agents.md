# Открытые агенты поддержки: похож ли AgentPII-RU v4 на то, что эти агенты реально делают

Дата: 2026-09-07. Вопрос: «изучи, как устроены НАСТОЯЩИЕ открытые агенты поддержки и сервиса, и ответь — похожи ли наши сценарии на то, что они делают, и чего у нас нет». Смотреть КОД и КОНФИГИ, не маркетинг; терминальная ссылка — на файл с определениями инструментов или на официальную схему.

Разобрано ~40 репозиториев и 10 официальных API-схем. Всё ниже — из кода и вендорской документации; там, где подтвердить нечем, стоит «не подтверждено».

## 0. Ответ

**Ось «что агент делает со ЗНАЧЕНИЕМ» мы покрыли лучше, чем кто-либо в открытом доступе. Ось «откуда значение вообще берётся» покрыта наполовину — и половина, которой нет, в реальных агентах доминирует.**

Три вещи, которых у нас нет и которые встречаются чаще всего:

1. **ПД в системном промпте** — 14 из ~40 проектов, и это рекомендованный вендорами паттерн (Chatwoot `contact.liquid`, Google ADK `GLOBAL_INSTRUCTION`, официальная дока OpenAI Agents SDK, Swarm `context_variables`). У нас во всех 834 системных промптах ПД нет по построению, а флаг `skip_system` построен на допущении, что их там и не бывает.
2. **Значение под безымянным ключом** — `custom_fields_values[{field_id: int, values: [{value}]}]` в amoCRM, `fields: object` без properties в Битрикс24, `z.record(string,string)` в HubSpot. Измерено: под ключом `value` не находятся ПАСПОРТ, ИНН и голая дата рождения.
3. **Эхо-подтверждение по буквам и цифрам** — три независимых проекта требуют этого дословно. Измерено: подмена, произнесённая по буквам, не восстанавливается для имени и почты.

Сверка реальных форм данных с движком дала **восемь воспроизводимых дефектов** (§6). Два из них — прямые утечки на самой частой в отрасли форме идентификации клиента («Фамилия Имя ДД.ММ.ГГГГ»).

Наша главная структурная ставка — что ПД приходит репликами клиента — **верна для голосовых агентов** (LiveKit, pipecat, τ-bench airline) и **является меньшинством для текстовых help desk**, где контакт уже известен, а ПД приходит из промпта и из результата инструмента. Это не ошибка: голосовой РФ-рынок наш основной. Но одну ось мы измеряем плотнее другой.

---

## 1. Разобранные проекты

### 1.1. Open-source help desk

| Проект | Инструментов | Форма схем | Ходов | Файл с определениями |
|---|---|---|---|---|
| **Chatwoot Captain** | 7 клиентских + 7 Copilot + ≤15 HTTP на аккаунт | плоская, по одному строковому параметру | `max_turns: 10` (`enterprise/app/services/captain/assistant/agent_runner_service.rb:28`) | `config/agents/tools.yml`, `enterprise/lib/captain/tools/*.rb`, `enterprise/app/services/captain/tools/copilot/*.rb` |
| **Zammad** | 0 — tool calling нет | плоский хеш, отрендеренный `JSON.pretty_generate` в ТЕКСТ системного промпта | 1 | `lib/ai/provider.rb:255` — `chat(prompt_system:, prompt_user:, prompt_image:)`, параметра `tools` нет ни в одной из 7 реализаций |
| **Erxes** | 1 (`search_knowledge`) + генератор канваса (≤20) | плоскость зашита в TypeScript-тип | `MAX_AI_TOOL_ITERATIONS = 5` (`aiAction/tools.ts:19`) | `backend/services/automations/src/ai/bridge/types.ts:9-17`, `ai/aiAction/knowledgeTool.ts:62-78`, `executions/actions/aiAgentTools.ts:36-79` |
| **FreeScout** ядро и офиц. модуль `AiIntegration` v1.0.3 | 0 | — | 1 | tool calling отсутствует; grep по ядру на `openai\|chatgpt\|anthropic\|function_call\|tool_calls` вне `vendor/` → 0 |
| **FreeScout AiChatPanel** (сторонний, v1.3.4, AGPL) | 9 | плоская, есть `enum`/`minimum`/`maximum`/`minLength`/`maxLength`, ни одного `format` | `max_tool_iterations` default 4, потолок 10 | `lieblinger/freescout-AiChatPanel`, `Services/Tools/Builtin/*.php` |
| **Botpress llmz** | 0 встроенных + 3 выхода + 9 UI-компонентов | **вложенная (Zod)** — единственная из девяти | `this.loop = props.loop ?? 3` | `packages/llmz/src/context.ts:1052`; интеграции — `integrations/zendesk/src/definitions/actions.ts` |
| **Typebot** | 0 | плоская, **ровно 4 скалярных типа** (string/number/boolean/enum) | `maxSteps = 6` | `packages/ai/src/schemas.ts`, `packages/ai/src/constants.ts` |
| **Tiledesk** chatbot / llm | 0 / 4 (конвертация файлов) | плоская Pydantic | — | `tiledeskChatbotPlugs/DirAssistant.js` — единственное вхождение `"tools"` закомментировано |
| **Papercups** | — | AI нет | — | последний коммит `6a6f5adc`, 2022-05-10 |

Chatwoot, все 7 клиентских инструментов дословно — **по одной строке каждый, и ни один не принимает ПД**:

```
faq_lookup                 param :query, type: 'string'
handoff                    string :reason (optional), string :reason_category (enum из 5)
resolve_conversation       param :reason, type: 'string', required: true
update_priority            param :priority, type: 'string'   # enum НЕ в схеме, только в desc
add_private_note           param :note, type: 'string'
add_contact_note           param :note, type: 'string'
add_label_to_conversation  param :label_name, type: 'string'
```

`conversation_id` и `contact_id` берутся из `tool_context.state` (`enterprise/lib/captain/tools/base_public_tool.rb::find_conversation` → `state&.dig(:conversation, :id)`), а не из аргументов модели. Единственный настоящий enum во всём наборе — `REASON_CATEGORIES = %w[customer_request missing_knowledge unsupported_request policy_restriction tool_failure]`; у `update_priority` и `search_articles` допустимые значения перечислены **прозой в `desc`**, валидация в рантайме, и модель узнаёт список только из текста ошибки.

Copilot — 7 инструментов, и **`search_contacts` единственное место во всём Chatwoot, где модель пишет ПД в аргументы**: `param :email`, `:phone_number`, `:name`; форматов нет, сравнение точное (`where(phone_number: phone_number)`). Возвращает `contact_llm_formatter.rb`: Contact ID / Name / Email / Phone / Location / Country Code / все `custom_attribute_definitions` / текст каждой заметки. `search_conversation` зовёт `to_llm_text(include_contact_details: true, include_private_messages: true)` — до 100 разговоров за вызов.

Пользовательские HTTP-инструменты (`enterprise/app/models/captain/custom_tool.rb`, `MAX_PER_ACCOUNT = 15`) описываются не JSON Schema, а плоским массивом `{name, type, description, required}` с `additionalProperties: false`; UI (`ParamRow.vue:33-42`) даёт 5 типов, но у `array` нет `items`, у `object` нет `properties` — вложенность невозможна. Ответ ограничен `MAX_RESPONSE_SIZE = 1.megabyte`.

### 1.2. Примеры вендоров и фреймворков

| Проект | Инструментов | Файл | Ключевое |
|---|---|---|---|
| **openai/openai-cs-agents-demo** | 11 `@function_tool`, 6 агентов | `python-backend/airline/tools.py` (353 стр.) | все схемы плоские, ни одного enum, **все возвращают прозу** (`-> str`); 2 input-guardrail на каждом агенте; README-транскрипты 3-4 хода |
| **openai/swarm** airline | 7 — **все без параметров** | `examples/airline/configs/tools.py` | ПД целиком в `context_variables` промпта; политики — нумерованные шаг-машины прозой; evals: 1 ход на кейс, `n = 5` прогонов |
| **openai/openai-agents-python** | 2 | `examples/customer_service/main.py` (189 стр.) | handoff без payload по умолчанию (`input_json_schema` пустой, `src/agents/handoffs/__init__.py:307`); отказ — `assert`, не сообщение модели |
| **anthropic-cookbook** | 3 | `tool_use/customer_service_agent.ipynb` | плоские, ни одного enum, ни одного формата; телефон `123-456-7890`; три независимых однооборотных сценария |
| **anthropic-quickstarts** `customer-support-agent` | **0** | `app/api/chat/route.ts:23-45` | инструментов нет вовсе — RAG со structured output; эскалация = поле `redirect_to_agent.reason` |
| **openai-cookbook** | 2 / 3 агента | `Using_tool_required_for_customer_service.ipynb`, `Orchestrating_agents.ipynb` | единственный настоящий JSON-Schema `enum` во всём вендорском корпусе: `problem: ["fraud","refund","information"]`; `escalate_to_human(summary)`; `execute_order` с `input("Confirm order? y/n: ")` |
| **google/adk-samples** customer-service | 12 | `python/agents/customer-service/customer_service/tools/tools.py` (407 стр.) | `GLOBAL_INSTRUCTION` с полным JSON клиента; eval `full_conversation.test.json`: **10 ходов / 6 вызовов, максимум 1 вызов за ход**; пороги `tool_trajectory_avg_score: 0.2` |
| **LangGraph** Swiss Airlines | 18 + 5 handoff-классов | `docs/docs/tutorials/customer-support/customer-support.ipynb` @ пин `23961cff` | `passenger_id` из `config`, не из аргументов (3 инструмента из 18); 11 sensitive за `interrupt_before`, 7 safe; Part 1: Human=14 / Ai=39 / Tool=25 |
| **Rasa** (4 демо-репозитория) | формы и слоты | `financial-demo/domain.yml`, `actions/custom_forms_config.yml`, `rasa-calm-demo/data/flows/patterns.yml` | телефона нет **нигде**; единственная regex во всём наборе — `.+@.+\..+` из mailchimp3; `max_validation_failures: 2`; `pattern_correction` + 12 e2e-тестов коррекции |
| **LlamaIndex** | `handoff(to_agent, reason)` | `llama-index-core/llama_index/core/agent/workflow/multi_agent_workflow.py:73-92`, `prompts.py` | `update_booking(user_id, property, value)` — **имя поля приезжает значением аргумента**; `user_state` в системный промпт каждого агента (`multi-agent-concierge/workflow.py`) |
| **CrewAI** | `DelegateWorkTool` / `AskQuestionTool` | `lib/crewai/src/crewai/tools/agent_tools/*.py`, `translations/en.json` | описание требует «share absolutely everything you know» в свободный `context: str`; `customer_support/` в crewAI-examples **не существует** |
| **Langroid** | `LeaseMessage` | `examples/docqa/chat_multi_extract.py` | 3 уровня вложенности, адрес одной строкой, все листья `str`; `phones: Dict[str, int]` в тестах — телефон целым числом |
| **τ-bench** (sierra-research) | 16 + 14 | `tau_bench/envs/retail/tools/`, `envs/airline/tools/`, политики в `wiki.md` | адрес — **6 плоских полей, все required**, `address2` может быть `''`; `passengers[{first_name,last_name,dob}]` до 5; `max_num_steps=30`, один вызов за шаг принудительно |
| **openai-realtime-agents** | 9 | `src/app/agentConfigs/customerServiceRetail/authentication.ts` | единственный проект с **`pattern` в JSON Schema**; адрес — вложенный объект; `execute()` сам ходит в LLM с транскриптом мимо шлюза |
| **LiveKit agents** hotel / healthcare / frontdesk / drive_thru | 54 / 13 / 3 / 5 | `examples/hotel_receptionist/tools_*.py`, `examples/healthcare/agent.py`, `livekit-agents/livekit/agents/beta/workflows/` | `beta.workflows` — шипающиеся примитивы сбора ПД; отель: 57 сценариев, типичный 5-8 ходов клиента и 6-12 вызовов; `max_tool_steps` default 3 |
| **pipecat** phonellm / patient_intake / restaurant | 4 / 8 / 3 | `pipecat-examples/phonellm/server/tools.py`, `pipecat-flows/examples/patient_intake.py` | «Never read a YYYY-MM-DD date aloud — that format is for tool arguments only»; поиск точным равенством после `.lower()`; 4-5 реплик, 2-3 вызова |
| **vocode-core** | `record_email` и др. | `vocode/streaming/action/record_email.py`, `base_action.py` | держит **обе формы** значения: `raw_value` + `formatted_value`; автоматически дописывает `user_message` в каждый вызов |
| **libredesk** (2884★) | 4 + 6 | `internal/aiagent/tools.go` | OTP-верификация; ПД в блоке `<<customer_context>>`; `neutralizeMarkers` заменяет `<<`/`>>` — исказит токен с этими символами |
| **chattermate** | 6 + 3 | `backend/app/tools/shopify_toolkit.py` | разбитый адрес `{address1,address2,city,provinceCode,zip,country}` и он же вторым разом склеенной строкой; `search_orders(limit=10)` → до 10 чужих заказов |
| **microsoft/autogen** | 3 + 3 | `python/samples/core_streaming_handoffs_fastapi/tools.py` | единственный support-сэмпл в репозитории; ПД нет; handoff несёт `List[LLMMessage]` целиком и пишет на диск |
| **Flowise** | 13 marketplace | `packages/components/src/utils.ts:869` (`convertSchemaToZod`) | **4 типа**: string/number/boolean/date; ни `.email()`, ни `.regex()`, ни min/max; вложенность физически невозможна |
| **Dify** | HubSpot-плагин | `langgenius/dify-official-plugins/tools/hubspot/tools/create_contact.yaml` | параметр-люк `properties: string` с произвольным JSON внутри; **все 6 параметров `required: false`**; `api/core/tools/provider/builtin/*` в актуальном Dify не существует |

τ-bench, адрес дословно — эталон разложения:

```python
"properties": {
    "user_id":  {"type": "string", "description": "The user id, such as 'sara_doe_496'."},
    "address1": {"type": "string", "description": "The first line of the address, such as '123 Main St'."},
    "address2": {"type": "string", "description": "The second line of the address, such as 'Apt 1' or ''."},
    "city": {...}, "state": {...}, "country": {...}, "zip": {...},
},
"required": ["user_id", "address1", "address2", "city", "state", "country", "zip"],
```

LiveKit `beta.workflows` — канонические примитивы сбора ПД, которые примеры и вызывают:

| | Форма | Файл |
|---|---|---|
| Телефон | ОДНА строка, `PHONE_REGEX = r"^\+?[1-9]\d{6,14}$"`, «digits only with optional leading +» | `beta/workflows/phone_number.py:14` |
| Адрес | **4 поля на вход → ОДНА строка на выход** (`" ".join([street_address, unit_number, locality, country])`) | `beta/workflows/address.py` |
| Дата рождения | **три `int`** (`year, month, day`), не строка | `beta/workflows/dob.py` |
| Имя | **три поля** `first_name / middle_name / last_name`, все `\| None` | `beta/workflows/name.py` |
| Карта | номер строкой без разделителей; наружу только `[-4:]`; подтверждение ПОВТОРОМ клиента, не зачитыванием | `beta/workflows/credit_card.py` |
| Дата в отеле | типизированный `datetime.date`, в docstring «ISO YYYY-MM-DD format» | `examples/hotel_receptionist/tools_*.py` |

**Пустышки, проверено:** `crewAIInc/crewAI-examples` — support-примера нет вовсе; `langgraph/examples/customer-support/` на `main` — две ячейки «This file has been moved»; `MODSetter/SurfSense` (16.1k★) — RAG для веб-ресёрча; `mem0ai/mem0` — в cookbook только `memory.add`; `n8n-io/n8n` — шаблоны на сайте, не в репозитории; `HubSpot/mcp-server` — официальный, но **пустой** (`size: 0`, `GET /commits` → 409, issue #1 «Missing source code» открыт с 2025-07-31); Zendesk официального MCP-сервера **не имеет** (перебраны все 888 репозиториев org, `search/code?q=org:zendesk "model context protocol"` → 0) — у него MCP есть только как у клиента.

Прикладных РУССКОЯЗЫЧНЫХ агентов поддержки с tool calling в открытом доступе практически нет: `ai-forever/gigachat` даёт только weather-пример, найденные amoCRM MCP-серверы (12 репозиториев, 0-10★) — обёртки над API без агентной логики. Наш корпус в этой части выведен из документации РФ-API, а не из наблюдаемого поведения агентов, и это его известное ограничение.

### 1.3. Официальные CRM-схемы: форма полей с ПД

| Вендор | ФИО | Адрес | Телефон | Даты |
|---|---|---|---|---|
| Zendesk | **1 поле** `name`, единственное обязательное | **поля нет** — свободный `details`, «such as an address» | «**should** comply with E.164» | ISO 8601 + Unix (`generated_timestamp`) в одном объекте |
| Intercom | **1 поле** `name` | нет; `location` — read-only `{type,country,region,city}` из IP | без `pattern`, без `format`, E.164 **не требуется** | **Unix в секундах**, при этом `format: date-time` на `type: integer` |
| Salesforce | **5 полей**, обязателен только `LastName` | разложен; compound `Address` **read-only**; `MailingStreet` — textarea 255 | **не валидирует, «can include alphabetic characters»** | ISO |
| HubSpot | 2 поля | **гибрид**: `address` строкой «including apartment or unit #» + `city/state/zip/country` отдельно | E.164 только при opt-in правиле; **поиск идёт БЕЗ кода страны** | Unix мс на приём, ISO на выдачу |
| amoCRM | 3 поля | `smart_address` через enum подполей (1-6) + плоский `streetaddress` | внутри `custom_fields_values` типа `multitext` | **Unix в секундах** |
| Битрикс24 | 3 поля (`NAME/SECOND_NAME/LAST_NAME`) | адрес контакта **устарел**, «используйте реквизиты» → `crm.address.*` | `crm_multifield[]` `{ID,TYPE_ID,VALUE,VALUE_TYPE}` | `YYYY-MM-DD`, `YYYY-MM-DDThh:mm:ss±hh:mm` |
| МойСклад | 3 поля | **две формы одновременно**; «При передаче обоих адресов строковый будет игнорирован» | — | `гггг-мм-дд чч-мм-сс` |
| RetailCRM | 3 поля | **22 поля**: `building`=дом, `house`=строение, `housing`=корпус, `block`=подъезд | массив `{number}` | `pattern: "Y-m-d H:i:s"`, `birthday: "Y-m-d"` |
| Twilio | — | — | **жёсткий E.164, отказ 21211** | — |
| SendGrid Marketing | `first_name`/`last_name` | **6 полей** с длинами (`address_line_1` ≤100 и т.д.) | — | — |

Официальные MCP-серверы: Intercom (14 инструментов, **только чтение контактов**, ни `create_contact`, ни `update_contact`, ни клиентского reply — единственная запись это внутренняя заметка), HubSpot (21 локальный / 25 hosted), Salesforce (~89 в 16 тулсетах, но в тулсете `data` — **ровно один**: произвольный SOQL с `JSON.stringify` всего ответа), Twilio и Битрикс24 (**отдают документацию, а не данные**: «Read-only… It does not execute API calls on your behalf»), Zendesk / amoCRM / RetailCRM / МойСклад — официальных нет.

**Ни один MCP-сервер в обзоре не маскирует ПД.** У HubSpot полный grep пакета на `pii|redact|mask|sanitiz|anonym|gdpr|sensitive` дал одно совпадение — в промпте, который даже не зарегистрирован (`promptsRegistry.js = export {};`). У hosted HubSpot защита есть, но узкая: закрывает Sensitive Data Properties (PHI), обычные `email`/`phone`/`address` под неё не подпадают.

Отдельно: **отрасль уже начала размечать ПД в схемах инструментов, двумя разными способами.** Salesforce Agentforce (`GenAiFunction`) кладёт в `schema.json` действия поле `"lightning:isPII": false` — «Indicates whether the property contains personally identifiable information». Twilio в OpenAPI ставит `x-twilio: {pii: {handling: standard, deleteSla: 30}}` на `body`, 120 на `from`/`to`. Обе разметки неполны (у Twilio `ContentVariables` её не имеет, хотя несёт те же ПД, что размеченный `Body`), но это готовые точки интеграции.

---

## 2. Что реальные агенты делают ↔ покрыто ли у нас

| Что делают в реальном коде | Где видно | Наша семья |
|---|---|---|
| Поиск по ПД → карточка → раскладка по полям | все CRM | `chain`, `decompose` |
| ПД из результата кормит следующий вызов | LangGraph, τ-bench, ADK | `result_feed`, `tool_chain`, `long_order` |
| Поиск возвращает чужие карточки | HubSpot `properties: item.properties` целиком, Intercom до 150, Chatwoot Copilot до 100 разговоров с приватными заметками | `lookup_list`, `search_rank`, `compare` |
| Модель пишет ПД прозой в заметку/тикет | Chatwoot `add_contact_note(note)`, ADK, LiveKit `take_guest_message` | `crm_note` |
| ПД в переменную шаблона | SendGrid `dynamic_template_data`, Twilio `ContentVariables` | `send_template` (частично, §3.6) |
| Свободный текст в CRM/тикет | Chatwoot, Botpress Zendesk | `crm_note`, `ticket_create` |
| Эскалация человеку прозой | Chatwoot, τ-bench `transfer_to_human_agents(summary)`, openai-cookbook, LiveKit | `long_support` |
| Склейка дублей | Bitrix24 `crm.duplicate.findbycomm`, дедупликация HubSpot по email | `crm_merge_contacts` |
| Клиент исправляет значение | Rasa `pattern_correction`, 12 e2e-тестов | `correction` |
| Внешний нормализатор переписывает значение | LiveKit `beta.workflows`, pipecat `normalize_date`, chattermate `_clean_email` | `normalize` |
| Бизнес-правило в промпте | τ-bench `wiki.md`, Swarm policies, ADK | `prompt_rule` |
| Несколько людей и агрегат | τ-bench `passengers[]`, SendGrid `personalizations` | `analytics` (частично, §3.5) |
| Производные значения (возраст, индекс) | CDEK индекс, ЕМИАС возраст | `derive` |
| Контакт как условие продажи | ЮKassa / T-Bank 54-ФЗ | `receipt` |
| Длинные диалоги 5-10 ходов | ADK eval 10, Chatwoot 10, LangGraph ~14 | `long_*` |
| **ПД в системном промпте** | **14 из ~40 проектов** | **НЕТ** |
| **Идентичность приходит вне модели (config / state / HTTP-заголовки)** | LangGraph, Chatwoot, Erxes, Botpress, libredesk | **НЕТ** |
| **Значение под безымянным ключом (`value`, `field_id`)** | amoCRM, Битрикс24, Zendesk, HubSpot, Dify, LlamaIndex | **НЕТ** |
| **Эхо-подтверждение по буквам / цифрам** | realtime-agents, LiveKit ×5 файлов | **НЕТ** |
| **Подтверждение перед мутацией (HITL)** | τ-bench, LangGraph `interrupt_before`, ADK, Swarm, LiveKit | **НЕТ** |
| **Массив коррелированных ПД одного человека** | τ-bench `passengers[]`, batch на 50, SendGrid до 1000 | **НЕТ** |
| **ПД внутри `enum` схемы инструмента** | LiveKit healthcare — enum из данных пациента | **НЕТ** |
| **Дата рождения тремя целыми числами** | LiveKit `beta/workflows/dob.py` | **НЕТ** |
| **FAQ / RAG / политика как инструмент** | почти каждый набор | **НЕТ** |
| **Тикет / handoff = весь транскрипт** | Botpress Zendesk, autogen, LiveKit warm-transfer | **НЕТ** |
| **Хост переписывает аргумент до исполнения** | ADK `lowercase_value(args)` | **НЕТ** |
| **Одно значение в двух формах в одном вызове** | vocode `raw_value`/`formatted_value`, LiveKit адрес | **НЕТ** |
| Аргументы утекают в текст ошибки / в SSE клиенту | Botpress, Flowise, LlamaIndex, LangGraph, Rasa | частично: мы маскируем результат-ошибку |

---

## 3. Чего у нас нет и почему это отдельная проверка

### 3.1. ПД в СИСТЕМНОМ ПРОМПТЕ — самый частый путь, у нас его нет ни в одном из 834 случаев

**Chatwoot**, `enterprise/lib/captain/prompts/snippets/contact.liquid` целиком:

```liquid
# Contact Information
- Contact ID: {{ contact.id }}
- Name: {{ contact.name || "Unknown" }}
- Email: {{ contact.email || "None" }}
- Phone: {{ contact.phone_number || "None" }}
- Identifier: {{ contact.identifier || "None" }}
- Type: {{ contact.contact_type || "visitor" }}
{% for attribute in contact.custom_attributes %}- {{ attribute[0] }}: {{ attribute[1] }}{% endfor %}
{% for attribute in contact.additional_attributes %}- {{ attribute[0] }}: {{ attribute[1] }}{% endfor %}
```

Рендерится из `assistant.liquid:28-29` и `scenario.liquid` при каждом наличии контакта, за флагом `config['feature_contact_attributes']` (`enterprise/app/models/concerns/agentable.rb`). Состав — `CONTACT_STATE_ATTRIBUTES = %i[id name email phone_number identifier contact_type custom_attributes additional_attributes]` (`runner_state_helper.rb`). Маскирования нет: grep по всему LLM-пути на `redact|anonymi[sz]|pii|scrub|mask_` → 0.

Остальные:

- **Google ADK**, `customer_service/prompts.py:19-21`: `GLOBAL_INSTRUCTION = f"""The profile of the current customer is: {Customer.get_customer("123").to_json()}"""` — `account_number`, ФИО, email, `phone_number="+1-702-555-1212"`, `billing_address{street,city,state,zip}`, `purchase_history`, на каждом ходе.
- **OpenAI Agents SDK**, официальная дока: пример dynamic instructions — `f"The user's name is {context.context.name}. Help them with their questions."` При этом дока `context/` говорит «The context object is **not** sent to the LLM» и «When an LLM is called, the **only** data it can see is from the conversation history» — то есть SDK предлагает ровно два способа показать модели профиль, и оба ведут в промпт или в аргумент.
- **Swarm**, `examples/airline/main.py:4-17`: `context_variables` с `NAME: John Doe`, `PHONE_NUMBER: (123) 456-7890`, `EMAIL`, `LOCATION: 1234 Main St, San Francisco, CA 94123, USA`, вклеиваются строкой в промпт триажа (`agents.py:40`).
- **Zammad**, `app/services/service/ai/feature/prompts/user/ai_agent.txt.erb`: ФИО автора, реальные `from`/`to`/`cc`, тема и **полный текст всех статей включая внутренние**; `articles: 'all'` по умолчанию (`agent/run/context/entity.rb`), лимита по числу и токенам нет; плюс OCR всех вложений.
- **LlamaIndex** `multi-agent-concierge/workflow.py`: `user_state` (`username`, `session_token`, `account_id`, `account_balance`) плоским текстом `"k: v"` в системный промпт **каждого** агента на **каждом** ходе.
- **LangGraph** Part 3/4: узел `fetch_user_info` выполняется первым и подставляет билеты как `<Flights>{user_info}</Flights>`.
- **libredesk**: блок `<<customer_context>>` с Name/Email/Phone/Country/External user ID и произвольными `CustomAttributes`.
- **Botpress**: значения объектов вклеиваются в промпт **как объявления кода** — `const name: Readonly<string> = 'John Smith'` (`objects.test.ts:70-88`, реальный inline-снапшот).
- **CrewAI**: интерполяция `{customer}`, `{person}`, `{inquiry}` в `Task.description`; в HubSpot-триггерах весь CRM-профиль физлица приходит одной JSON-строкой в `crewai_trigger_payload`, инструментов ноль.
- **FreeScout AiIntegration**: `"Customer name: ".$customer->getFullName()` + `json_encode($messages)` со всей перепиской (ограничение «последние 12 тредов» **закомментировано**).

**Почему это отдельная проверка.** `pseudex/envelope.py:161-166` документирует допущение дословно: «there the system prompt is the agent's own template, not user PII, and running NER over tens of KB on every call is the bulk of the cost and could corrupt instructions». Флаг `skip_system` (`pseudex/service.py:486`) на этом допущении и построен. Отрасль его массово нарушает. Наш корпус проверить не может: во всех 834 системных промптах ПД нет по построению, так что путь `skip_template=True` пуст и на плече I, и на плече C.

Дыра не в детекции: прогон шаблона Chatwoot через движок находит все семь значений (`NAME/EMAIL/PHONE/LOC/PASSPORT/INN/DOB`). Дыра в том, что **корпус не заставляет её сработать**, и в том, что интеграция может её выключить одним булевым полем.

**Поправка на наш рынок:** отель LiveKit ПД в системный промпт **не** вклеивает, потому что до верификации их не знает. Это паттерн текстовых help desk и агентов с уже известным клиентом, а не голосовых входящих звонков. Приоритет §3.1 ниже, чем §3.4 и §3.3.

### 3.2. Идентичность приходит МИМО модели, ПД появляется только на обратном плече

- **LangGraph**, дословно: «**The LLM never has to provide these explicitly**, they are provided for a given invocation of the graph so that each user cannot access other passengers' booking information». `passenger_id` из `config["configurable"]`, три инструмента из 18 (`fetch_user_flight_information`, `update_ticket_to_new_flight`, `cancel_ticket`), остальные 15 идентификатор клиента не принимают вообще.
- **Chatwoot**: `find_conversation(state)`; плюс `X-Chatwoot-Contact-Email`, `X-Chatwoot-Contact-Phone`, `X-Chatwoot-Contact-Id` уходят **HTTP-заголовками** (`enterprise/app/models/concerns/toolable.rb::add_contact_headers`) — мимо модели вообще.
- **Erxes**: входы, чей binding резолвится (`customerId`, `conversationId`), **скрыты из схемы** и подставляются сервером; `inputs: { ...args, ...resolvedBindings }`, binding'и выигрывают (`aiAgentTools.ts:147`).
- **Botpress**: `setStaticInputValues`.
- Контрпример: **τ-bench** требует аутентификацию через модель — «This has to be done even when the user already provides the user id», `find_user_id_by_email` либо `find_user_id_by_name_zip`.

У нас клиент всегда сам диктует свой ключ поиска. Нет ни одного случая, где ключ модель не видела вовсе, а ПД приходит только результатом — то есть где вся работа шлюза лежит на обратном плече и на свободном тексте.

### 3.3. Значение под БЕЗЫМЯННЫМ ключом — здесь прямая утечка

Доминирующая форма записи в CRM:

```json
"custom_fields_values": [{"field_id": 264785, "values": [{"value": "+79164021187", "enum_code": "WORK"}]}]
```

Подтверждено официальной докой amoCRM (телефон и email — не отдельные поля, а `multitext` внутри `custom_fields_values`; `enum_code` для PHONE: `WORK, WORKDD, MOB, FAX, HOME, OTHER`) и кодом коннекторов: `CustomFieldInput{field_id: int, values: list[dict[str, Any]]}` (`cAIborg-ai/amocrm-mcp`, `amocrm_mcp/models/schemas.py`). Битрикс24 MCP отдаёт `fields: {"type": "object"}` **без properties** и `filter: {"type": "object"}` тоже без (`Aiyo28/yzel`, `src/yzel/connectors/bitrix24/server.py`). HubSpot MCP — `const PropertiesSchema = z.record(z.string(), z.string())`. Zendesk — `custom_fields: [{id: 27642, value: "745"}]` у тикета и `{"membership_level": "silver"}` у юзера, **две разные конвенции в одном API**; `identities` кладут почту, телефон и хендл в одну строку `value`, тип несёт соседний ключ. Dify — `properties: string` с произвольным JSON внутри. LlamaIndex — `update_booking(user_id, property, value)`, где **тип ПД задаёт соседний аргумент**.

**Измерено на движке** (bundle загружен через `testkit.load_dev_bundle()`), форма `{"value": "..."}`:

| тип | найден |
|---|---|
| NAME, PHONE, EMAIL, LOC | да |
| СНИЛС (mod-101), карта (Luhn) | да |
| **ПАСПОРТ `4509 123456`** | **нет** |
| **ИНН `7707083893`** (валидный) | **нет** |
| **ДР `1987-03-14`** | **нет** |

На реалистичном payload записи контакта amoCRM (имя, фамилия, телефон, email, паспорт, ДР, ИНН в `custom_fields_values`) движок находит `NAME ×2, PHONE, EMAIL, DATE` — **паспорт и ИНН уходят к модели в открытом виде**. Причина не в детекции, а в архитектуре: эти типы опираются на КЛЮЧ, а у формы ключа нет. С русским ключом всё находится: `{"инн": …}` → INN, `{"паспорт": …}` → PASSPORT.

Дополнительно `morph_places.role_of_field('value')` возвращает пустую строку, то есть защита «голое число под адресным ключом» (`pseudex/redact.py:1219-1222`, добавлена после того, как «139» в `sflat` нашлось внутри цифр фейкового телефона) здесь выключена — ровно тот случай, ради которого её вводили.

Вторая половина: ключи в `custom_attributes` придумывает заказчик. Измерено: `passport_series` / `passport_number` и `tax_id` **не находятся**; `dob`, `birthday`, `snils`, `pension_number`, `phone_mobile`, `contact_phone`, `Мобильный`, `delivery_address`, `addr1` — находятся. Карта ключ→тип конечна, словарь имён полей у заказчиков — открытый.

Все 31 наш инструмент называют свои поля. Прибор эту ось увидеть не может по построению.

**Подкласс: значение без строки.** `beta/workflows/dob.py` — `update_dob(year: int, month: int, day: int)`. Ни один наш инструмент так не принимает — у нас везде ISO-строка. Три голых целых числа детекция не видит в принципе. Langroid добивает: `phones: Dict[str, int]` — телефон целым числом, ведущий `+7`/`8` теряется по типу. amoCRM и Intercom кладут даты Unix-секундами, HubSpot принимает Unix-миллисекунды.

### 3.4. Эхо-подтверждение по буквам и цифрам

Требуют дословно, в двух независимых проектах и пяти файлах:

- `openai-realtime-agents/customerServiceRetail/authentication.ts`: «Whenever the user provides a piece of information, **ALWAYS read it back to the user character-by-character** to confirm you heard it right before proceeding. If the user corrects you, ALWAYS read it back to the user AGAIN.» Примеры состояний: `"You said 0-2-1-5-5-5-1-2-3-4, correct?"`. Про имя отдельно: `"Do NOT verify or spell back the name; just accept it."`
- LiveKit `beta/workflows/address.py:202-205`: «**Confirm postal codes by reading them out digit-by-digit** as a sequence of single numbers. Do not read them as cardinal numbers. For example, read 90210 as 'nine zero two one zero.'»; `:205` «Spell out the address letter-by-letter when applicable, such as street names and provinces».
- `phone_number.py:27`: «Never repeat the phone number back to the user as a single block of digits. **Read it back in groups.**»; `:157` `"Read the number back to the user in groups.\n"`.
- `email_address.py:109,123`: `separated_email = " ".join(email)`, `f"Repeat the email character by character: {separated_email} if needed\n"`.
- `credit_card.py:29/50/71`: «Never repeat any sensitive information… back to the user»; `:254` `"Ask them to repeat the number, do not repeat the number back to them."` — карта подтверждается **повтором клиента**.
- `hotel_receptionist/verify_booking.py:16`: «**Read the code back letter by letter** to confirm before looking up the booking.»; `persona.py:38`: «When the caller spells something out — a name, an email, a code — **the letters ARE the value**… "Shane, S-H-A-Y-N-E" is Shayne… Record and read back the SPELLED form».

**Измерено:**

| форма | восстанавливается |
|---|---|
| телефон группами `+7 961 458 41 03` | да |
| телефон по цифрам `9 6 1 4 5 8 4 1 0 3` | да |
| **фамилия по буквам `К-У-Д-Р-Я-В-Ц-Е-В`** | **нет — клиенту диктуют ФЕЙК** |
| **фамилия через запятую `К, у, д, р, …`** | **нет** |
| **почта по буквам `m d p a h x p u собака example.ru`** | **нет** |

Наш корпус на 55% голосовой (`voice_raw` 33.1% + `voice_itn` 21.9%), но в нём **нет ни одной ассистентской реплики** (`roles: {system: 834, user: 2261}`), а семья `summary` судит только финальный ответ на вхождение целого значения. Класс «модель произносит подмену по буквам, клиент говорит „неверно“, цикл верификации не сходится никогда» невидим.

### 3.5. Массив коррелированных ПД одного человека

τ-bench `book_reservation`, до пяти пассажиров («Each reservation can have at most five passengers»):

```python
"passengers": {"type": "array", "items": {"type": "object",
  "properties": {"first_name": {...}, "last_name": {...},
                 "dob": {"description": "...in the format 'YYYY-MM-DD'"}},
  "required": ["first_name", "last_name", "dob"]}}
```

SendGrid — до 1000 `personalizations`, каждая со своим `to[{email, name}]`. HubSpot / amoCRM batch — до 50 объектов (`BatchCreateContactsInput.items: list[dict[str, Any]]`). LiveKit `take_guest_message(recipient, caller_name, caller_phone, message)` — **два разных человека в одном вызове**.

У нас `crm_import_csv` (CSV-строка с заголовком `last_name;first_name;phone;email;birth_date`) и `crm_segment_report.members[{name, bucket}]`. Нет формы «один человек разложен на три поля внутри элемента массива, связность обязана сохраниться **внутри элемента**» — а это ровно тот класс, где подмена склеивает химеру из ФИО одного и ДР другого.

### 3.6. Шаблоны: у нас ключи именованные, в реальности — либо любой глубины, либо бессмысленные

SendGrid `dynamic_template_data`, вся схема поля дословно и целиком:

```json
{"type": "object", "description": "A collection property names that will be substituted by their corresponding property values in the `subject`, `reply-to` and `content` portions of a SendGrid Dynamic Template..."}
```

Ни `properties`, ни `additionalProperties`, ни `maxProperties`, ни ограничения глубины — в отличие от соседнего `substitutions`, у которого стоит `"additionalProperties": {"type": "string"}`. Вложенность подтверждена докой Handlebars (`{{user.profile.firstName}}`). Официальный пример кладёт туда `name`, `address01`, `address02`, `city`, `state`, `zip` — **при полностью отсутствующем теле письма** (`content` нет, только `template_id`). Детектор, смотрящий на «текстовые поля сообщения», ПД там не увидит: их там нет. `{{{ }}}` отключает HTML-экранирование, в `href="{{url}}"` тоже.

Twilio наоборот: `ContentVariables` — `type: string`, внутри JSON-строка, значения строго `additionalProperties: {type: string}`, вложенности нет. Ключи `"1"`, `"2"`, ≤16 символов, семантики нет: что значит `{{1}}` — имя, адрес или номер заказа — известно только из тела шаблона на стороне Twilio под `ContentSid`. Тело запроса — `application/x-www-form-urlencoded`, JSON вложен в него строкой: **двойное кодирование**. Переменная подставляется не только в `body`, но и в `title`, `media[]` и `actions[].url`.

Наш `send_template.variables` — `{name, phone, when}`, один уровень, ключи говорящие. Ни один из двух реальных полюсов не воспроизведён.

### 3.7. Подтверждение перед мутацией

τ-bench `retail/wiki.md`: «Before taking consequential actions that update the database… you have to list the action detail and obtain **explicit user confirmation (yes)**» и «You should at most make **one tool call at a time**». LangGraph: `interrupt_before` на 11 sensitive-инструментах, отказ возвращается как `"API call denied by user. Reasoning: '{user_input}'. Continue assisting, accounting for the user's input."` ADK: «**Always confirm actions with the user before executing them**». LiveKit: `confirm_card_number` инжектируется **только после** `update_card_number` — «preventing the LLM from hallucinating a confirmation without user input»; машинная гарантия в `doheny-surf-desk/tasks/phone_task.py`: `if ctx.speech_handle == self._record_handle: raise ToolError("User must confirm explicitly")`. Swarm: `"human_input": true` **флагом в самой JSON-схеме**. openai-cookbook: `input("Confirm order? y/n: ")`, при отказе модель получает `"User cancelled order."` и перепланирует.

У нас ни одного случая, где агент обязан зачитать значение и получить «да». Связка с §3.4, и это самая частая структура диалога в τ-bench-подобных агентах.

Два противоположных лагеря, и они меняют объём ПД за запрос: «подтверди каждое, один вызов за раз» (τ-bench, Swarm, LiveKit hotel, ADK, LangGraph part 3) против «не спрашивай, цепочь» — `cs-agents-demo` дословно: «**perform multiple tool calls in a single turn without waiting for user replies**».

### 3.8. Одно значение в двух формах в одном вызове

vocode `record_email.py`:

```python
class RecordEmailParameters(BaseModel):
    raw_value: str = Field(..., description="The raw value parsed from the transcript.")
    formatted_value: str = Field(..., description="The estimated FORMATTED value of the email.")
```

`base_action.py` **автоматически дописывает в каждый вызов** `user_message` — произносимую реплику, где то же ПД повторено разговорно, затем `del params["user_message"]` перед исполнением; `models/actions.py` вписывает JSON аргументов строкой в транскрипт: `ACTION_STARTED_FORMAT_STRING = "!STARTING ACTION {action_name} WITH PARAMETERS {action_params}!"`.

LiveKit `address.py` принимает 4 поля и отдаёт `address: str = " ".join([...])`. chattermate отдаёт адрес структурой и вторым разом склеенной строкой. ADK возвращает `report` + `data`.

Наш `normalize` покрывает переписывание значения третьей стороной, но не «обе формы едут вместе и обязаны совпасть после восстановления».

### 3.9. FAQ / RAG / политика как инструмент

`faq_lookup` (Chatwoot), `faq_lookup_tool` (cs-demo, agents-python), `lookup_policy` (LangGraph), `query_docs` (Swarm support_bot), `search_knowledge` (Erxes), `search_articles`/`get_article` (Intercom, Chatwoot Copilot). Есть практически в каждом наборе; у нас ноль из 31.

Это не только «шаг без ПД» (эту роль играет `clinic_slots` в одной семье). RAG-результат может **сам** нести ПД: Zammad вклеивает OCR всех вложений тикета, Chatwoot `search_conversation` вызывается с `include_contact_details: true, include_private_messages: true`.

### 3.10. Ошибка, лог и HITL как канал

Botpress `tool.ts:757`: `` `Tool "${this.name}" failed after ${this.MAX_RETRIES} attempts. Last error: ${JSON.stringify(input)}` `` — **весь аргумент** в тексте ошибки. Flowise: `throw new ToolInputParsingException('Received tool input did not match expected schema', JSON.stringify(arg))`, и отдельно `Agent.ts:2337-2361` отправляет `usedTools` с `toolInput` **клиенту по SSE** — мимо шлюза вообще; `Agent.ts:2251-2255` стримит `toolCall` в чат markdown-блоком. LlamaIndex: `ToolOutput(content=str(e), raw_input=tool_input, is_error=True)`. LangGraph: `f"Error: {repr(error)}\n please fix your mistakes."` ADK возвращает настоящий id: `"You cannot use the tool with customer_id " + customer_id + ", only for " + c.customer_id + "."` Rasa helpdesk: `f"Could not retrieve caller id; {records} records found for email {email}"`, где `records` — **список JSON-записей пользователей ServiceNow целиком**. Erxes: `content = JSON.stringify({ error: error.message })` уходит модели как `role: 'tool'`.

Наш харнесс маскирует результат-ошибку тем же путём, что успех (`bench/agentpii4/harness.py:173` — `gateway.push_tool(tool_name, log.result_text)` вызывается до возврата с `is_error`), так что путь покрыт — но только если интеграция делает так же. Интеграция, маскирующая лишь успешные результаты, и канал Flowise «в чат клиенту напрямую» у нас нечем поймать.

### 3.11. Хост переписывает аргумент до исполнения

ADK `shared_libraries/callbacks.py`: `lowercase_value(args)` приводит **все строковые аргументы к нижнему регистру** перед вызовом. chattermate `_clean_email` лоуэркейсит. LiveKit нормализует телефон `123-555-0170` → `1235550170`. pipecat `normalize_date` при неудаче фоллбэчит на «склей все цифры» — чужой код с ровно нашей ошибкой «пустого каноникала». Rasa делает `.title()`. Поиск в pipecat — `reservation["name"].lower() == name.strip().lower()`: склонение или инициал = «не найдено» при 200 OK.

**Измерено:**

| форма подмены | восстановление |
|---|---|
| как написано | правильно |
| `.lower()` | правильно |
| **`.upper()` кириллица — ИМЯ** | **фейк «УСТИНОВ ИГНАТ» уходит в инструмент** |
| **`.upper()` кириллица — АДРЕС** | **химера «Барышникова ПЕРЕУЛОК 7»** |
| **`.upper()` — EMAIL** | **фейк уходит в инструмент** |
| `.upper()` латиница (`CHIZHOV MIROSLAV` → `BUKIN SERGEI`) | правильно |

Заглавная кириллица — не экзотика: банковский KYC, импорт в 1С, ФИО в госформах. Наш `payment_create` требует заглавные, но **латиницей**, поэтому эта дорожка проверена, а кириллическая — нет.

### 3.12. Handoff = весь транскрипт, а не сводка

Botpress Zendesk `_buildTicketBody` склеивает **весь диалог** в plain-text тело тикета через `DEFAULT_TRANSCRIPT_FORMATTER`; `startHitl.input.messageHistory` — `sdk.z.array(messageSchema)` **без `.max()`**. autogen передаёт `List[LLMMessage]` и пишет в `chat_history/` на диск. LiveKit `beta/workflows/warm_transfer.py` кладёт весь транскрипт в промпт брифинга; `healthcare/agent.py::transfer_to_human` вызывается **без аргументов** и передаёт `chat_ctx=context.session.history`. Chatwoot публикует `reason` приватной заметкой (`conversation.messages.create!(private: true, content: reason)`), `reason_category` уходит только в аналитику, структурированных полей оператору нет (`team_id`/`priority`/`escalation_level` — TODO прямо в файле). LiveKit `personal_shopper` копирует последние 6 сообщений + `"Customer: {first} {last} (ID: {id})"`.

Единственный структурированный handoff во всей выборке — LangGraph `To*Assistant` (`location`, `start_date`, `end_date`, `request`), и даты там всё равно `str`. Второй — LiveKit `record_followup(kind: FollowupKind, caller_name, caller_phone, summary)` с enum из 9 значений.

Наш `escalate_to_human(summary ≤1500, queue enum)` соответствует форме из openai-cookbook, но форма «уходит всё, дословно» — самая частая — не проверена.

### 3.13. Защита от устаревшего подтверждения

У всех примитивов LiveKit `confirm_*` держит замыкание на подтверждаемое значение:

```python
if address != self._current_address:
    return ("The address has changed since confirmation was requested, "
            "ask the user to confirm the updated address.")
```

Машинный аналог нашей семьи `correction`, и он показывает, чем коррекция кончается в реальном коде — не переспросом, а отказом подтвердить. Плюс примитивы читают историю: «If the user already stated one earlier in this conversation, record it with `update_phone_number` instead of asking again» — значение может прийти из реплики, сказанной десятью ходами раньше.

---

## 4. Где мы делаем НЕ ТАК

**4.1. `format` в схемах: у нас в 21 инструменте из 31, в отрасли почти нигде.** Ни одного `format` / `.email()` / E.164 / ISO 8601 во всех девяти help-desk-наборах. Ровно один проект из ~40 кладёт `pattern` в саму схему — `openai-realtime-agents`: `^\(\d{3}\) \d{3}-\d{4}$` и `^\d{4}-\d{2}-\d{2}$`. Это важно в обратную сторону: провайдер в strict-режиме проверяет их **до** исполнения, то есть форматосохраняющая подмена там — условие того, что вызов вообще состоится. Формат даты в Botpress задан текстом внутри `.describe('... in YYYY-MM-DD format')`. Из десяти CRM телефон валидирует **один** — Twilio (21211, «with no spaces, dashes, or parentheses»). Salesforce явно разрешает буквы, Zendesk пишет «should», Intercom не имеет ни `pattern`, ни `format`, HubSpot требует E.164 только при opt-in правиле. Телефон встретился в **пяти написаниях**: `(111) 222-3333`, `+12065550123`, `+1-702-555-1212`, `555-0122`, `1235550170`.

Строгость сокращается в парной разности, так что это калибровка, а не ошибка прибора: класс `validated_refused` у нас встречается заметно чаще, чем встретился бы в поле, и читать его долю как «столько сломается у заказчика» нельзя.

**4.2. Мы типизировали то, что в реальности свободная строка.** Наш `crm_find_contact.query{phone|email|last_name}` с правилом `exactly_one_key` ссылается на amoCRM `GET /api/v4/contacts?query=`, где на самом деле **одна свободная строка** — подтверждено кодом коннектора: `ContactsSearchInput.query: str = Field(description="Search query string")`. Chatwoot `findCustomer.query`: «partial or full value of any user property, **including name, email address, notes, or phone**», `z.string().min(2)`. Мы сделали задачу восстановления легче, чем она есть.

**4.3. Все 22 семьи смотрят на аргумент вызова или на финальный ответ.** Половина реальных путей ПД (§3.1, §3.2, §3.10) туда не попадает вовсе.

**4.4. В корпусе нет ассистентских ходов.** `roles: {system: 834, user: 2261}`. Значит невозможны эхо-подтверждение, память между сессиями внутри корпуса, инъекция истории хостом, handoff с транскриптом, «значение сказано десять ходов назад».

**4.5. Регистры.** У нас `voice_raw` 33.1%, `chat` 30.0%, `voice_itn` 21.9%, `sloppy` 14.3%, `clean` 0.7%. Восемь из девяти help-desk-продуктов — текстовые и почтовые каналы. Регистра «ветка письма» (подпись, цитата, `from`/`to`/`cc`) нет ни одного случая, а Zammad кладёт в промпт ровно это. Движок на нём работает (находит ФИО в подписи, три почты, оба телефона, адрес), но заодно маскирует `support@shop.ru` — корпоративный ящик самой поддержки.

**4.6. Ошибки.** У нас `{"error": {"code": rule, "field": path, "message": …}}`. В отрасли примерно половина — голая проза: `'Contact not found'`, `'Note content is required'`, `'Handoff skipped because a newer customer message arrived'` (Chatwoot), `"Error: order not found"`, `"Error: non-pending order cannot be cancelled"` (τ-bench), `f"Error: {repr(error)}"` (LangGraph), `"That slot was just taken. Try another time?"` (speechmatics — там домен и падение API вообще неразличимы, обе ветки под одним `except Exception`). Структурированно отвечают ADK (`{"status": "rejected", "message": "discount too large. Must be 10 or less."}` с комментарием «Send back a reason for the error so that the model can recover»), Intercom, HubSpot, amoCRM, МойСклад. Наш вариант правдоподобен, но смещён в сторону структурного.

**4.7. Длина диалога у нас в порядке**, вопреки ожиданию. Реальные лимиты: 1 (Zammad), 3 (Botpress `loop ?? 3`, LiveKit `max_tool_steps`), 4 (FreeScout AiChatPanel), 5 (Erxes), 6 (Typebot `maxSteps`), 10 (Chatwoot `max_turns`, ADK eval), 30 шагов (τ-bench), ~14 ходов (LangGraph). У нас 1-7 ходов пользователя, `long_order` — 7 ходов и 12 инструментов. Удлинять незачем.

---

## 5. Что у нас есть, а в реальных агентах не встречается

| Семья | Аналог в разобранном коде | Вердикт |
|---|---|---|
| `validate` — промпт требует посчитать контрольную сумму перед вызовом | **нет ни одного из ~40**. Ближайшее — τ-bench: «The API does not check these for the agent, so **the agent must make sure the rules apply before calling the API!**», но это проверка политики, не арифметики | Класс реален (движок минтит подмены, заведомо не проходящие контрольную сумму — наше решение, конфликт настоящий), но **сценарий выдуман**. Оставить, не расширять |
| `derive` — 54 случая, самая большая семья | индекс — да (CDEK требует); возраст/пол — форма ЕМИАС реальна, но **ни один открытый агент их не вычисляет** (ADK не вычисляет ничего, LangGraph тоже); **инициалы и транслит — аналогов нет нигде** | Обоснованно для РФ-форм, но подтверждено документацией API, а не поведением агентов. Самая большая семья держится на самой слабой внешней опоре |
| `passport_verify`, СНИЛС, ИНН, МФЦ | аналогов вне РФ нет | Оставить — рынок |
| `receipt` (54-ФЗ) | аналогов нет, опирается на ЮKassa и T-Bank дословно | Оставить |
| `crm_segment_report` | batch-инструменты есть (HubSpot, amoCRM `analytics_get_pipeline_analytics`, ≤50), но «сгруппируй по городам и дай сводку» встречается только в **агентских** Copilot-наборах, не в клиентских | Реален, но это Copilot-сценарий. Стоит пометить домен |
| `prompt_rule` — граница по номеру дома | правил в промптах масса (τ-bench `wiki.md`, Swarm `FLIGHT_CANCELLATION_POLICY`, ADK), конкретно «дом > 100» синтетика | Класс верный, форма условная — как и задумано в докстринге семьи |
| `crm_import_csv` — CSV-строка с фиксированным заголовком | batch есть, но как **массив нетипизированных объектов** (`items: list[dict[str, Any]]`, ≤50), не как CSV | Форма наша, класс реальный, см. §3.5 |

---

## 6. Восемь дефектов движка

Первые два — на форме, которой реальные агенты проверяют личность клиента: `get_patient_by_name_and_dob(name, dob)` в LiveKit healthcare (`fake_database.py`), `passengers[{first_name,last_name,dob}]` и `find_user_id_by_name_zip(first_name, last_name, zip)` в τ-bench, `birthday` в pipecat `patient_intake`.

| # | Симптом | Воспроизведение / место |
|---|---|---|
| **D1** | «Букин Сергей 14.03.1987» → **один LOC-спан «Букин Сергей 14»**. Имя маскируется как УЛИЦА, «.03.1987» уходит модели в открытом виде, инструмент получает «улица Кедровая 6.03.1987». Воспроизводится на любых именах: «Иванов Пётр 05.05.1990» → `LOC 'Иванов Пётр 05'`, «Соколова Анна 21.09.1980» → `LOC 'Соколова Анна 21'`. С запятой («Букин Сергей, 14.03.1987») правильно: `NAME` + `DATE` | `Detector().detect('Букин Сергей 14.03.1987')`; арм безмаркерного адреса в `detect_address` + `_PRIORITY` в `detect_all.py` (ADDR 4 > NAME 3) |
| **D2** | «Букин Сергей 1987-03-14» → **один NAME-спан, включающий дату**. Дата уничтожается подменой имени | тот же вызов с ISO-датой |
| **D3** | Подмена в ЗАГЛАВНОЙ кириллице не восстанавливается: имя и почта уходят фейком, адрес возвращается химерой «Барышникова ПЕРЕУЛОК 7». Латиница в порядке | `unmask_text(fake.upper(), vault, inflect=False, for_tool=True)`; путь `pseudex/redact.py::unmask_text` / `name_key` |
| **D4** | Подмена, произнесённая по буквам («К-У-Д-Р-Я-В-Ц-Е-В», «К, у, д, р, …»), не восстанавливается для имени и почты; телефон по цифрам и группами восстанавливается (цифровой реиндекс работает) | `unmask_text('Фамилия ' + '-'.join(fake.upper()), …)` |
| **D5** | Под безымянным ключом `{"value": …}` не находятся **ПАСПОРТ, ИНН и голая дата рождения**; `morph_places.role_of_field('value') == ''` выключает защиту «голое число под адресным ключом» | `pseudex/redact.py:1219-1222`; реалистичный payload `custom_fields_values` amoCRM: находятся `NAME ×2, PHONE, EMAIL, DATE`, паспорт и ИНН — нет |
| **D6** | Ключи вне арендованной карты ключ→тип: `passport_series` / `passport_number`, `tax_id` — не находятся (`dob`, `birthday`, `snils`, `pension_number`, `phone_mobile`, `contact_phone`, `Мобильный`, `delivery_address`, `addr1` — находятся). Ключи `custom_attributes` Chatwoot и `custom_fields` amoCRM придумывает заказчик | `Detector().detect('- passport_series: 4509\n- passport_number: 123456')` → `[]` |
| **D7** | `mask_tools` маскирует только `properties[*].description` **верхнего уровня**: наш собственный пример `+79161234567` внутри `recipient.phones[].number` (глубина 4) и `contact.phone` (глубина 2) уходит провайдеру сырым на каждом вызове. Форма MCP/Anthropic (`inputSchema` / `input_schema`) проходит **насквозь нетронутой** — обрабатывается только `tool["function"]` | `pseudex/envelope.py:206-232`; проверено: `mask_tools([DELIVERY.schema, COURIER.schema], ctx, False)` → `'+79161234567' in json.dumps(out) == True`. `pseudex/proxy.py:392` вызывает с `skip_template=False` всегда |
| **D8** | **ПД внутри `enum` уходит модели сырой — решение принято сознательно, на допущении, которое голосовые агенты нарушают.** `pseudex/envelope.py:200-202`: «Names, types and `enum` values are the tool CONTRACT: masking an enum would change the set of values the model is allowed to emit». Допущение — что enum это закрытый словарь. LiveKit healthcare (`examples/healthcare/agent.py`) строит enum **из данных самого пациента в рантайме**: `json_schema_extra={"enum": available_doctors}`, `{"enum": iso_times}` его слотов и `{"enum": appt_times}` **его собственных записей** — ПД оказывается в ОПРЕДЕЛЕНИИ функции | измерено: `mask_tools` пропускает enum с настоящим ФИО насквозь, описание верхнего уровня при этом маскируется корректно |

D7 и D8 разной природы. D7 — недоработка обхода схемы. D8 — верное решение под неверное допущение: чинить наивно нельзя, подмена в enum действительно меняет множество допустимых значений и сломает контракт; но класс существует, и надо решить, что мы про него говорим заказчику.

Плюс несоответствие допущения фактам: докстринг `pseudex/envelope.py:161-166` обосновывает `skip_template` тем, что системный промпт — шаблон агента без ПД. Chatwoot, ADK, Swarm, LangGraph, Zammad, libredesk, FreeScout, CrewAI и официальная дока OpenAI Agents SDK утверждают обратное.

---

## 7. Порядок работ

По убыванию отношения «частота в поле ÷ стоимость проверки», с поправкой на то, что основной рынок голосовой:

1. **Починить D1 и D2.** Не новая семья, а утечка на входной форме, которой каждый второй агент идентифицирует клиента. Проверяется одной строкой, стоит $0. Идти через `debug-leak` → `detect-change`: арм голого адреса тонкий и его уже дважды сужали.
2. **Семья `echo_spell`.** Агент обязан зачитать значение по буквам или цифрам и получить подтверждение. Закрывает D3 и D4; единственный класс, где без детокенизации исходящего текста ассистента диалог не сходится в принципе. Требует ассистентских ходов в корпусе — самая дорогая из четырёх и самая близкая к голосовому рынку.
3. **Семья `opaque_field`.** Запись в CRM через `custom_fields_values` с числовым `field_id` и ключом `value`, плюс `fields: object` Битрикс24 и `properties: string` Dify. Закрывает D5 и D6, инструмент добавляется без нового домена, $0 на построении. Сюда же подкласс «значение без строки»: ДР тремя `int`, телефон целым числом.
4. **Семья `profile_prompt`.** Карточка клиента в системном промпте, как у Chatwoot и ADK. Ассистентских ходов не требует; требует решения, что делать с `skip_system` — документировать риск или инвертировать умолчание.
5. `passengers[]` (связность внутри элемента массива) и `dynamic_template_data` (произвольная глубина, ключи вроде `address01`) — по одному инструменту каждая.
6. FAQ-инструмент в 2-3 семьи как шаг без ПД (сейчас эту роль играет только `clinic_slots` в одной семье), и вариант, где RAG-результат сам несёт ПД.
7. **D7 и D8 закрываются вне корпуса**: правка `mask_tools` (рекурсия по вложенным `properties`/`items`, поддержка формы `inputSchema`/`input_schema`) и продуктовое решение по enum.

**Не делать:** удлинять диалоги (реальный потолок 3-10 ходов, мы в нём); расширять `validate` (аналогов в поле нет ни одного); добавлять новые форматные строгости в мок (отрасль валидирует куда слабее нас — телефон проверяет ровно один вендор из десяти).

---

## 8. Источники

### Open-source help desk
- https://github.com/chatwoot/chatwoot/blob/develop/config/agents/tools.yml
- https://github.com/chatwoot/chatwoot/tree/develop/enterprise/lib/captain/tools
- https://github.com/chatwoot/chatwoot/blob/develop/enterprise/lib/captain/prompts/snippets/contact.liquid
- https://github.com/chatwoot/chatwoot/blob/develop/enterprise/app/models/captain/custom_tool.rb
- https://github.com/zammad/zammad/blob/develop/lib/ai/provider.rb
- https://github.com/erxes/erxes (`backend/services/automations/src/ai/`)
- https://github.com/lieblinger/freescout-AiChatPanel/blob/main/Services/Tools/Builtin/GetCustomerTool.php
- https://github.com/botpress/botpress (`packages/llmz/src/context.ts`, `integrations/zendesk/src/definitions/actions.ts`)
- https://github.com/baptisteArno/typebot.io/blob/main/packages/ai/src/schemas.ts
- https://github.com/Tiledesk/tiledesk-chatbot

### Примеры вендоров и фреймворков
- https://github.com/openai/openai-cs-agents-demo/blob/main/python-backend/airline/tools.py
- https://github.com/openai/swarm/blob/main/examples/airline/configs/tools.py
- https://github.com/openai/openai-agents-python/blob/main/examples/customer_service/main.py
- https://github.com/openai/openai-agents-python/blob/main/examples/sandbox/healthcare_support/tools.py
- https://openai.github.io/openai-agents-python/context/
- https://openai.github.io/openai-agents-python/agents/
- https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/customer_service_agent.ipynb
- https://github.com/anthropics/anthropic-quickstarts/tree/main/customer-support-agent
- https://github.com/openai/openai-cookbook (`Using_tool_required_for_customer_service.ipynb`, `Orchestrating_agents.ipynb`)
- https://github.com/google/adk-samples/blob/main/python/agents/customer-service/customer_service/tools/tools.py
- https://github.com/google/adk-samples/blob/main/python/agents/customer-service/customer_service/prompts.py
- https://github.com/langchain-ai/langgraph/blob/23961cff61a42b52525f3b20b4094d8d2fba1744/docs/docs/tutorials/customer-support/customer-support.ipynb
- https://github.com/RasaHQ/financial-demo (`domain.yml`, `actions/custom_forms_config.yml`)
- https://github.com/RasaHQ/rasa-calm-demo/blob/main/data/flows/patterns.yml
- https://github.com/RasaHQ/helpdesk-assistant
- https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/agent/workflow/multi_agent_workflow.py
- https://github.com/run-llama/multi-agent-concierge
- https://github.com/crewAIInc/crewAI/blob/main/lib/crewai/src/crewai/tools/agent_tools/delegate_work_tool.py
- https://github.com/langroid/langroid/blob/main/examples/docqa/chat_multi_extract.py
- https://github.com/sierra-research/tau-bench/tree/main/tau_bench/envs
- https://github.com/openai/openai-realtime-agents/blob/main/src/app/agentConfigs/customerServiceRetail/authentication.ts
- https://github.com/livekit/agents/tree/main/livekit-agents/livekit/agents/beta/workflows
- https://github.com/livekit/agents/tree/main/examples/hotel_receptionist
- https://github.com/livekit/agents/blob/main/examples/healthcare/agent.py
- https://github.com/pipecat-ai/pipecat-examples/blob/main/phonellm/server/tools.py
- https://github.com/pipecat-ai/pipecat-flows/blob/main/examples/patient_intake.py
- https://github.com/vocodedev/vocode-core/blob/main/vocode/streaming/action/record_email.py
- https://github.com/abhinavxd/libredesk/blob/main/internal/aiagent/tools.go
- https://github.com/chattermate/chattermate.chat/blob/main/backend/app/tools/shopify_toolkit.py
- https://github.com/microsoft/autogen/blob/main/python/samples/core_streaming_handoffs_fastapi/tools.py
- https://github.com/FlowiseAI/Flowise/blob/main/packages/components/src/utils.ts
- https://github.com/langgenius/dify-official-plugins/blob/main/tools/hubspot/tools/create_contact.yaml

### Официальные схемы CRM и рассылок
- https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
- https://developer.zendesk.com/api-reference/ticketing/users/users/
- https://developers.intercom.com/docs/guides/mcp
- https://developers.intercom.com/docs/references/rest-api/api.intercom.io/contacts/contact
- https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_contact.htm
- https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/compound_fields.htm
- https://github.com/salesforcecli/mcp
- https://developers.hubspot.com/docs/api-reference/latest/crm/objects/contacts/guide
- https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send
- https://www.twilio.com/docs/content/using-variables-with-content-api
- https://www.twilio.com/docs/api/errors/21211
- https://www.amocrm.ru/developers/content/crm_platform/contacts-api
- https://apidocs.bitrix24.ru/api-reference/crm/contacts/crm-contact-add.html
- https://github.com/moysklad/api-remap-1.2-doc/blob/master/md/dictionaries/_counterparty.md
- https://rest-api-docs.retailcrm.ru/v5/

### Коннекторы РФ-систем (не вендорские, но с реальными схемами)
- https://github.com/Aiyo28/yzel/blob/master/src/yzel/connectors/amocrm/server.py
- https://github.com/Aiyo28/yzel/blob/master/src/yzel/connectors/bitrix24/server.py
- https://github.com/cAIborg-ai/amocrm-mcp/blob/main/amocrm_mcp/models/schemas.py

### Наш код, на который ссылается отчёт
- `prototype/pseudex/envelope.py:161-166` (обоснование `skip_template`), `:188-232` (`mask_tools`), `:200-202` (enum как контракт)
- `prototype/pseudex/service.py:483-486` (`skip_system`)
- `prototype/pseudex/proxy.py:392` (`mask_tools(..., False)`)
- `prototype/pseudex/redact.py:1219-1222` (`_bare_address_leaf`), `:1225-1277` (`unmask_arguments`)
- `prototype/bench/agentpii4/tools.py` (31 инструмент), `scenarios/` (22 семьи), `harness.py:150-186` (плечо I и путь ошибки)
- `research/2026-09-05-agent-scenario-coverage.md` (предыдущая итерация той же работы)
