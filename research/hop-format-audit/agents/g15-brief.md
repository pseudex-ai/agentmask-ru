# Группа 15: sequential_chain + same_tool_other_target + document:office

Кейсов: 54. Семейства: sequential_chain, same_tool_other_target, document:office.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - sequential_chain-026 (end_to_end=0.0, chain_value=0.0, multi_all_out=—, tool_arg_form=0.0)
  - sequential_chain-014 (end_to_end=0.0, chain_value=0.0, multi_all_out=—, tool_arg_form=0.0)
  - document:office-003 (end_to_end=0.1667, chain_value=—, multi_all_out=0.0, tool_arg_form=0.4)
  - sequential_chain-002 (end_to_end=0.0, chain_value=0.0, multi_all_out=—, tool_arg_form=0.0)
  - document:office-001 (end_to_end=0.1667, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)
  - same_tool_other_target-008 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - document:office-002 (end_to_end=0.3333, chain_value=—, multi_all_out=0.0, tool_arg_form=0.6923)
  - sequential_chain-003 (end_to_end=0.25, chain_value=0.0, multi_all_out=0.0, tool_arg_form=1.0)

**Все case_id группы:**
document:office-000, document:office-001, document:office-002, document:office-003, document:office-005, document:office-006, same_tool_other_target-000, same_tool_other_target-001, same_tool_other_target-002, same_tool_other_target-003, same_tool_other_target-006, same_tool_other_target-007, same_tool_other_target-008, same_tool_other_target-010, same_tool_other_target-011, same_tool_other_target-013, same_tool_other_target-014, same_tool_other_target-015, same_tool_other_target-016, same_tool_other_target-017, same_tool_other_target-018, same_tool_other_target-020, same_tool_other_target-021, same_tool_other_target-022, same_tool_other_target-023, sequential_chain-000, sequential_chain-001, sequential_chain-002, sequential_chain-003, sequential_chain-004, sequential_chain-005, sequential_chain-006, sequential_chain-007, sequential_chain-008, sequential_chain-009, sequential_chain-012, sequential_chain-013, sequential_chain-014, sequential_chain-015, sequential_chain-016, sequential_chain-018, sequential_chain-019, sequential_chain-021, sequential_chain-022, sequential_chain-025, sequential_chain-026, sequential_chain-027, sequential_chain-028, sequential_chain-029, sequential_chain-030, sequential_chain-031, sequential_chain-032, sequential_chain-033, sequential_chain-035

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
