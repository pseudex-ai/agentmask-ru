# Группа 5: parallel + result_feed + send_template

Кейсов: 55. Семейства: parallel, result_feed, send_template.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - parallel-012 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - parallel-016 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - parallel-020 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - parallel-024 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - parallel-048 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - parallel-004 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - parallel-040 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - parallel-000 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)

**Все case_id группы:**
parallel-000, parallel-001, parallel-003, parallel-004, parallel-005, parallel-006, parallel-007, parallel-008, parallel-009, parallel-010, parallel-011, parallel-012, parallel-013, parallel-014, parallel-015, parallel-016, parallel-017, parallel-019, parallel-020, parallel-021, parallel-022, parallel-024, parallel-025, parallel-026, parallel-027, parallel-029, parallel-030, parallel-033, parallel-037, parallel-038, parallel-039, parallel-040, parallel-041, parallel-042, parallel-043, parallel-045, parallel-046, parallel-047, parallel-048, parallel-049, parallel-050, parallel-051, result_feed-000, result_feed-001, result_feed-002, result_feed-003, result_feed-004, result_feed-005, result_feed-006, result_feed-007, send_template-000, send_template-001, send_template-002, send_template-003, send_template-005

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
