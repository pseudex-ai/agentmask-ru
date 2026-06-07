# Интеграция Obscura (drop-in)

**Принцип:** Obscura — OpenAI-совместимый прокси. В коде клиента меняется ТОЛЬКО
`base_url` и ключ (наш, `sk-obsc-…`). Инструменты/промпты/логика агента — не трогаются.

**Один раз (настройка):** клиент отдаёт свой провайдерский ключ — мы выдаём ему ключ Obscura:
```bash
python issue_key.py acme https://openrouter.ai/api/v1 sk-or-<их_ключ>
# -> Obscura API key (give to customer): sk-obsc-eZwQ...
```
Теперь его агент ходит через нас; реальные ПД не доходят до модели, инструменты получают настоящие значения.

---

## OpenAI SDK (Python)
```python
from openai import OpenAI
# было:  client = OpenAI(api_key="sk-or-...")                      # прямо к провайдеру
client = OpenAI(base_url="https://obscura.company.ru/v1",
                api_key="sk-obsc-eZwQ...")                          # ← через Obscura
# дальше всё как обычно — tools, messages без изменений
```

## LangChain / LangGraph
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    model="openai/gpt-4.1-mini",
    base_url="https://obscura.company.ru/v1",   # ← единственное изменение
    api_key="sk-obsc-eZwQ...",
)
# граф, узлы, tool-node — без изменений
```

## LlamaIndex
```python
from llama_index.llms.openai import OpenAI
llm = OpenAI(api_base="https://obscura.company.ru/v1", api_key="sk-obsc-eZwQ...")
```

## Vercel AI SDK / любой JS
```js
import { createOpenAI } from "@ai-sdk/openai";
const openai = createOpenAI({
  baseURL: "https://obscura.company.ru/v1",
  apiKey: "sk-obsc-eZwQ...",
});
```

## n8n (no-code)
В credential «OpenAI» (или «OpenAI Chat Model»):
- **Base URL** → `https://obscura.company.ru/v1`
- **API Key** → `sk-obsc-eZwQ...`

Всё. Никакого кода — два поля в настройках узла.

## Любой другой инструмент (universal fallback)
Многие читают переменные окружения:
```bash
export OPENAI_BASE_URL="https://obscura.company.ru/v1"
export OPENAI_API_KEY="sk-obsc-eZwQ..."
```
Совсем «закрытый» инструмент без настройки base_url → системный forward-proxy (на будущее).

## Голый HTTP (контракт)
```bash
curl https://obscura.company.ru/v1/chat/completions \
  -H "Authorization: Bearer sk-obsc-eZwQ..." \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4.1-mini",
       "messages":[{"role":"user","content":"Найди заказ по телефону +7 999 123-45-67"}],
       "tools":[{"type":"function","function":{"name":"find_order",
                 "parameters":{"type":"object","properties":{"phone":{"type":"string"}}}}}]}'
```

---

## Что происходит внутри (клиент этого не видит)
```
агент → (реальные ПД) → Obscura: маскирует → (токены) → модель
модель → (токены в tool_call) → Obscura: детокенизирует аргументы → агент выполняет тул на РЕАЛЬНЫХ данных
финальный ответ модели (токены) → Obscura: детокенизирует → юзер видит реальное
```
Параллельно `GET /usage` отдаёт, что мы поймали и на что заменили (для UI «за что платишь»).
```bash
curl https://obscura.company.ru/usage -H "Authorization: Bearer sk-obsc-eZwQ..."
# {"protected_counts":{"PHONE":12,"NAME":5,"CARD":2}, "recent":[{"type":"PHONE","preview":"+7••••••••67",...}]}
```
