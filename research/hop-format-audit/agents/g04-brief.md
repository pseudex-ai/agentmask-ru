# Группа 4: long_order + correction

Кейсов: 56. Семейства: long_order, correction.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - correction-005 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=None)
  - correction-006 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=None)
  - long_order-005 (end_to_end=0.0909, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.4444)
  - long_order-020 (end_to_end=0.0833, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.6429)
  - long_order-029 (end_to_end=0.1667, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.5625)
  - long_order-035 (end_to_end=0.0909, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.7143)
  - long_order-022 (end_to_end=0.2, chain_value=—, multi_all_out=0.0, tool_arg_form=0.7)
  - long_order-009 (end_to_end=0.2, chain_value=—, multi_all_out=0.0, tool_arg_form=0.7143)

**Все case_id группы:**
correction-000, correction-001, correction-005, correction-006, correction-007, correction-008, correction-009, correction-010, long_order-001, long_order-002, long_order-003, long_order-005, long_order-006, long_order-007, long_order-008, long_order-009, long_order-010, long_order-012, long_order-013, long_order-015, long_order-016, long_order-017, long_order-018, long_order-019, long_order-020, long_order-021, long_order-022, long_order-024, long_order-025, long_order-026, long_order-027, long_order-028, long_order-029, long_order-031, long_order-032, long_order-033, long_order-034, long_order-035, long_order-037, long_order-039, long_order-040, long_order-041, long_order-042, long_order-043, long_order-045, long_order-046, long_order-048, long_order-049, long_order-050, long_order-051, long_order-052, long_order-053, long_order-055, long_order-057, long_order-058, long_order-059

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
