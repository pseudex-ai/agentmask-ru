# Интеграция Veilgate (drop-in)

**Принцип:** Veilgate — OpenAI-совместимый прокси. В коде клиента меняется ТОЛЬКО
`base_url` и ключ (наш, `sk-vg-…`). Инструменты/промпты/логика агента — не трогаются.

**Один раз (настройка):** клиент отдаёт свой провайдерский ключ — мы выдаём ему ключ Veilgate:
```bash
python issue_key.py acme https://openrouter.ai/api/v1 sk-or-<их_ключ>
# -> Veilgate API key (give to customer): sk-vg-eZwQ...
```
Теперь его агент ходит через нас; реальные ПД не доходят до модели, инструменты получают настоящие значения.

---

## OpenAI SDK (Python)
```python
from openai import OpenAI
# было:  client = OpenAI(api_key="sk-or-...")                      # прямо к провайдеру
client = OpenAI(base_url="https://veilgate.company.ru/v1",
                api_key="sk-vg-eZwQ...")                          # ← через Veilgate
# дальше всё как обычно — tools, messages без изменений
```

## LangChain / LangGraph
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    model="openai/gpt-4.1-mini",
    base_url="https://veilgate.company.ru/v1",   # ← единственное изменение
    api_key="sk-vg-eZwQ...",
)
# граф, узлы, tool-node — без изменений
```

## LlamaIndex
```python
from llama_index.llms.openai import OpenAI
llm = OpenAI(api_base="https://veilgate.company.ru/v1", api_key="sk-vg-eZwQ...")
```

## Vercel AI SDK / любой JS
```js
import { createOpenAI } from "@ai-sdk/openai";
const openai = createOpenAI({
  baseURL: "https://veilgate.company.ru/v1",
  apiKey: "sk-vg-eZwQ...",
});
```

## n8n (no-code)
В credential «OpenAI» (или «OpenAI Chat Model»):
- **Base URL** → `https://veilgate.company.ru/v1`
- **API Key** → `sk-vg-eZwQ...`

Всё. Никакого кода — два поля в настройках узла.

## Любой другой инструмент (universal fallback)
Многие читают переменные окружения:
```bash
export OPENAI_BASE_URL="https://veilgate.company.ru/v1"
export OPENAI_API_KEY="sk-vg-eZwQ..."
```
Совсем «закрытый» инструмент без настройки base_url → системный forward-proxy (на будущее).

## Голый HTTP (контракт)
```bash
curl https://veilgate.company.ru/v1/chat/completions \
  -H "Authorization: Bearer sk-vg-eZwQ..." \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4.1-mini",
       "messages":[{"role":"user","content":"Найди заказ по телефону +7 999 123-45-67"}],
       "tools":[{"type":"function","function":{"name":"find_order",
                 "parameters":{"type":"object","properties":{"phone":{"type":"string"}}}}}]}'
```

---

## Что происходит внутри (клиент этого не видит)
```
агент → (реальные ПД) → Veilgate: маскирует → (токены) → модель
модель → (токены в tool_call) → Veilgate: детокенизирует аргументы → агент выполняет тул на РЕАЛЬНЫХ данных
финальный ответ модели (токены) → Veilgate: детокенизирует → юзер видит реальное
```
Параллельно `GET /usage` отдаёт, что мы поймали и на что заменили (для UI «за что платишь»).
```bash
curl https://veilgate.company.ru/usage -H "Authorization: Bearer sk-vg-eZwQ..."
# {"protected_counts":{"PHONE":12,"NAME":5,"CARD":2}, "recent":[{"type":"PHONE","preview":"+7••••••••67",...}]}
```
