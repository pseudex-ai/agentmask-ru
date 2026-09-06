# Интеграция Pseudex (drop-in)

**Принцип:** Pseudex — OpenAI-совместимый прокси. В коде клиента меняется ТОЛЬКО
`base_url` и ключ (наш, `sk-ps-…`). Инструменты/промпты/логика агента — не трогаются.

**Один раз (настройка):** клиент отдаёт свой провайдерский ключ — мы выдаём ему ключ Pseudex:
```bash
python issue_key.py acme https://openrouter.ai/api/v1 sk-or-<их_ключ>
# -> Pseudex API key (give to customer): sk-ps-eZwQ...
```
Теперь его агент ходит через нас; реальные ПД не доходят до модели, инструменты получают настоящие значения.

---

## OpenAI SDK (Python)
```python
from openai import OpenAI
# было:  client = OpenAI(api_key="sk-or-...")                      # прямо к провайдеру
client = OpenAI(base_url="https://pseudex.company.ru/v1",
                api_key="sk-ps-eZwQ...")                          # ← через Pseudex
# дальше всё как обычно — tools, messages без изменений
```

## LangChain / LangGraph
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    model="openai/gpt-4.1-mini",
    base_url="https://pseudex.company.ru/v1",   # ← единственное изменение
    api_key="sk-ps-eZwQ...",
)
# граф, узлы, tool-node — без изменений
```

## LlamaIndex
```python
from llama_index.llms.openai import OpenAI
llm = OpenAI(api_base="https://pseudex.company.ru/v1", api_key="sk-ps-eZwQ...")
```

## Vercel AI SDK / любой JS
```js
import { createOpenAI } from "@ai-sdk/openai";
const openai = createOpenAI({
  baseURL: "https://pseudex.company.ru/v1",
  apiKey: "sk-ps-eZwQ...",
});
```

## n8n (no-code)
В credential «OpenAI» (или «OpenAI Chat Model»):
- **Base URL** → `https://pseudex.company.ru/v1`
- **API Key** → `sk-ps-eZwQ...`

Всё. Никакого кода — два поля в настройках узла.

## Любой другой инструмент (universal fallback)
Многие читают переменные окружения:
```bash
export OPENAI_BASE_URL="https://pseudex.company.ru/v1"
export OPENAI_API_KEY="sk-ps-eZwQ..."
```
Совсем «закрытый» инструмент без настройки base_url → системный forward-proxy (на будущее).

## Голый HTTP (контракт)
```bash
curl https://pseudex.company.ru/v1/chat/completions \
  -H "Authorization: Bearer sk-ps-eZwQ..." \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4.1-mini",
       "messages":[{"role":"user","content":"Найди заказ по телефону +7 999 123-45-67"}],
       "tools":[{"type":"function","function":{"name":"find_order",
                 "parameters":{"type":"object","properties":{"phone":{"type":"string"}}}}}]}'
```

---

## Инструкция агенту (одна фраза в системный промпт)

Дешёвая половина защиты от двух классов, которые обратным путём не чинятся —
проверено живым замером v4 (`docs/tz-agentpii4.md` §7): агент, который
ВЫВОДИТ поля из персональных данных (индекс из города, возраст из даты
рождения, инициалы и транслит из имени), выводит их из подмены, а агент,
который ПЕРЕСЧИТЫВАЕТ контрольные суммы, отвергает подмену и не вызывает
инструмент. Добавьте в системный промпт агента:

> Персональные данные клиента передавай в инструменты так, как они названы в
> разговоре или пришли из инструмента, не пересчитывая и не проверяя
> контрольные суммы. Поля, которых в разговоре не было (почтовый индекс,
> возраст, инициалы, написание латиницей), не выводи сам — спроси клиента или
> оставь пустыми, если схема это позволяет.

Шлюз при этом восстанавливает и производные формы (транслит, инициалы, кусок
номера), но только те, что он умеет вывести сам; фраза выше убирает остальное.

## Что происходит внутри (клиент этого не видит)
```
агент → (реальные ПД) → Pseudex: маскирует → (токены) → модель
модель → (токены в tool_call) → Pseudex: детокенизирует аргументы → агент выполняет тул на РЕАЛЬНЫХ данных
финальный ответ модели (токены) → Pseudex: детокенизирует → юзер видит реальное
```
Параллельно `GET /usage` отдаёт, что мы поймали и на что заменили (для UI «за что платишь»).
```bash
curl https://pseudex.company.ru/usage -H "Authorization: Bearer sk-ps-eZwQ..."
# {"protected_counts":{"PHONE":12,"NAME":5,"CARD":2}, "recent":[{"type":"PHONE","preview":"+7••••••••67",...}]}
```
