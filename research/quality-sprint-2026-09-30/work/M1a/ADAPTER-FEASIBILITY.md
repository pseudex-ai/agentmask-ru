# Legacy capture adapter — feasibility finding (round 6)

Вывод по структуре сохранённых capture (`payload_canaries.CapturedPayload` / `RunCapture`): провайдер-линк для message-раскрытий **не восстанавливается** из существующих captures, tool_result-раскрытия — частично.

## Что есть в captures

`RunCapture.delivered` — кортеж `CapturedPayload(name, text, real_text)` по границам `model_input/tool_args/tool_result/tool_error/final_answer/model_request`. Для каждого payload сохранены `text` (masked/доставленное) и `real_text` (pre-mask источник). `final_answer` = raw_reply (model bytes) + restored (customer bytes) — OUT-нога.

## Что восстанавливается

- **tool_result disclosure:** `run.tool_results` (ToolResultRecord с `text_real`/`text_masked`/`spans_real`/`pieces`) + `run.model_trace.call_requests[i]` (provider request на call) + `available_results` дают провайдер-линк. `validate_evidence` уже принимает такой proof. Adapter может построить DisclosureProof для tool_result: `request` = минимальный provider request, где результат стал available.
- **message disclosure:** `model_request` capture — push-снапшот masked/real транскрипта, но без provider ordinal. `MentionRecord.request_index` (gateway pushes) и `ModelResponse.request` (provider responses) — разные счётчики, прямое сопоставление запрещено. Message-раскрытия остаются **UNKNOWN** (не fabricated).

## Следствие

- Adapter НЕ должен изобретать zip(push snapshots, provider responses) или last-response fallback.
- Реальный измеримый охват на legacy прогонах = tool_result-раскрытия + те message-раскрытия, для которых провайдер-линк появится при M1c (harness extension). До этого message-путь честно UNKNOWN.
- Это НЕ блокирует G2 (метрика корректно выдаёт UNKNOWN без доказательства); это вопрос M1c wiring: либо расширить harness capture провайдер-линком, либо принять tool_result-only + UNKNOWN message coverage с явной публикацией.

Никаких изменений engine/scorer/raw. Правка кода не выполнялась — только анализ структуры.
