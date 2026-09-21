# LiteLLM + Presidio guardrail

Открытый LLM-шлюз (MIT, `github.com/BerriAI/litellm`) с guardrail `presidio`:
плейсхолдеры `<TYPE_N>` на входе, `output_parse_pii: true` обещает
восстановление на выходе.

Измеряется адаптером `openai_proxy`. Имя модели обязано совпадать с
`model_list` в `config.yaml` — здесь `fake`; несовпадение даёт 272 ошибки подряд.

```sh
docker compose up -d      # litellm + presidio-analyzer + presidio-anonymizer

agentmask run --adapter openai_proxy --name litellm --model fake \
    --base-url http://127.0.0.1:4000/v1 --api-key sk-agentmask \
    --upstream-bind 0.0.0.0:8099 --out results/

docker compose down
```

**Заявленные дефекты (20.09.2026, litellm 1.102.0 `main-stable`).** Оба
воспроизводятся одной английской фразой без модели — минимальный стенд в
issue.

- [BerriAI/litellm#42130](https://github.com/BerriAI/litellm/issues/42130) —
  пересекающиеся спаны анализатора (телефон + `UK_NHS`/`US_BANK_NUMBER`/…)
  режут уже вставленный плейсхолдер: модель видит `<US_BANK_NUMBER_7>LICENSE_7>`.
  В этом корпусе — 257 из 327 замаскированных значений.
- [BerriAI/litellm#31950](https://github.com/BerriAI/litellm/issues/31950)
  (открыт с июля, PR #32014 не влит) — `output_parse_pii` не восстанавливает
  `tool_calls[].function.arguments` на пути `UnifiedLLMGuardrails`: круг 0/327.
- [BerriAI/litellm#31959](https://github.com/BerriAI/litellm/issues/31959) —
  нумерация плейсхолдеров сбрасывается на каждом сообщении; в семье
  `second_mention` это даёт коллизии токенов между репликами.

Presidio по умолчанию — английские распознаватели; русские имена и адреса он
почти не видит (строка `leak` это показывает), и это не дефект LiteLLM.
