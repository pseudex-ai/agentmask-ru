# Группа 10: tool_chain + derive + validate

Кейсов: 55. Семейства: tool_chain, derive, validate.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - tool_chain-023 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.3333)
  - tool_chain-007 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.375)
  - tool_chain-027 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.4545)
  - tool_chain-036 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.4545)
  - tool_chain-020 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.4286)
  - tool_chain-040 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.5455)
  - tool_chain-042 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.4545)
  - tool_chain-035 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.5556)

**Все case_id группы:**
derive-000, derive-001, derive-003, derive-004, derive-005, derive-007, derive-008, derive-009, derive-010, derive-012, derive-013, tool_chain-000, tool_chain-001, tool_chain-002, tool_chain-003, tool_chain-004, tool_chain-005, tool_chain-007, tool_chain-009, tool_chain-010, tool_chain-011, tool_chain-012, tool_chain-013, tool_chain-014, tool_chain-015, tool_chain-016, tool_chain-017, tool_chain-018, tool_chain-019, tool_chain-020, tool_chain-021, tool_chain-023, tool_chain-025, tool_chain-027, tool_chain-029, tool_chain-030, tool_chain-031, tool_chain-033, tool_chain-035, tool_chain-036, tool_chain-037, tool_chain-038, tool_chain-040, tool_chain-041, tool_chain-042, tool_chain-043, tool_chain-044, validate-000, validate-002, validate-005, validate-006, validate-007, validate-008, validate-009, validate-010

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
