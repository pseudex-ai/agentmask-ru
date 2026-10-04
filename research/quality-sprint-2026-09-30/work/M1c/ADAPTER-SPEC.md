# M1c Фаза 2 — legacy capture adapter (SPEC для Flash-исполнителя)

Цель: построить `AnswerEvidence` (кортеж `DisclosureProof`) из сохранённого прогона, чтобы `answer_events(case, run, *, evidence)` измерил real run. **Без zip(push, provider) и last-response fallback.**

## API результата

Новый модуль `prototype/bench/agentpii5/legacy_adapter.py`:

```python
def build_evidence(case: CaseV5, run: ArmRunV5) -> AnswerEvidence | None
```

- Возвращает `AnswerEvidence((...))` с доказанными `DisclosureProof` или `None` (нет доказанных раскрытий).
- Импортирует `AnswerEvidence`, `DisclosureProof` из `bench.agentpii5.answer_restoration` (НЕ создаёт циклический импорт: answer_restoration не импортирует adapter).

## Что доказуемо (tool_result)

Из `run.tool_results` (ToolResultRecord: `seq`, `text_real`, `text_masked`, `spans_real`, `pieces`, `call_ordinal`) + `run.model_trace.call_requests` (provider request на call) + `run.model_trace.responses`.

Для каждого tool_result и каждого item_id в `spans_real`:
- `record_id = f"tool-{seq}-{item_id}"`.
- `request` = минимальный `response.request`, где результат был доступен модели: `call_requests[index] < response.request` и `index < response.available_results` (где `index` = позиция call с `seq == record.seq` в `run.base.calls`). Если такого response нет — доказательство пропустить (result никогда не был доступен последующему consumer).
- `source_kind='tool_result'`, `source_index=record.seq`.
- `source_text=record.text_real`, `masked_text=record.text_masked`.
- `source_start/source_end = record.spans_real[item_id]`.
- `masked_start/masked_end`: вычислить из `record.pieces` (drift: для куска `(start,end,substitute,engine_type)` с `(start,end)==spans_real[item_id]`, masked-смещение = start + накопленный drift; `engine_type` обязан совпадать с `item.type`).
- `source_sha256/masked_sha256` = SHA256 UTF-8.

Валидность проверяй вызовом `validate_evidence(case, run, evidence)` из answer_restoration (уже реализована); невалидный proof — пропустить с именем, не кидать.

## Что НЕ доказуемо (message)

`model_request` capture — push-снапшот без provider ordinal. Message-раскрытия НЕ строятся; остаются UNKNOWN (ответ консервативный). НЕ изобретать `zip(push snapshots, provider responses)`.

## Тест (RED→GREEN)

Новый `prototype/bench/agentpii5/test_legacy_adapter.py`:
1. Синтетический case+run с tool_result (text_real/text_masked/spans_real/pieces + call_requests) → `build_evidence` возвращает валидный proof, `validate_evidence` проходит, `answer_events(case, run, evidence=...)` даёт measurable (не UNKNOWN).
2. Message-only раскрытие (mentions без tool_result) → `build_evidence` возвращает None или только tool_result-подмножество; message остаётся UNKNOWN.
3. Невалидный tool_result (engine_type не совпадает, или результат не был доступен) → proof пропущен, не кидает.

## Scope

Пишет только `prototype/bench/agentpii5/legacy_adapter.py` + `prototype/bench/agentpii5/test_legacy_adapter.py` + `research/quality-sprint-2026-09-30/work/M1c/adapter/`. НЕ трогать `answer_restoration.py`, `payload_canaries.py`, engine, scorer, raw runs. Запуск: `PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python -m bench.agentpii5.test_legacy_adapter`.

## Результат

`INPUTS.json`, `SPEC.md` (свой), `RED.log`/`GREEN.log`, `DELTA.json`, `GATE.json` (PASS/FAIL честно), краткий отчёт. Explicit routing deepseek-flash.
