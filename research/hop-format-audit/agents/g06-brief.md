# Группа 6: chain + search_rank + sequential_chain:tracker

Кейсов: 54. Семейства: chain, search_rank, sequential_chain:tracker.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - sequential_chain:tracker-002 (end_to_end=0.0, chain_value=0.0, multi_all_out=0.0, tool_arg_form=None)
  - search_rank-008 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - search_rank-011 (end_to_end=0.1667, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - search_rank-009 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - search_rank-004 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)
  - search_rank-010 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)
  - search_rank-007 (end_to_end=0.1667, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - search_rank-002 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)

**Все case_id группы:**
chain-000, chain-001, chain-003, chain-004, chain-005, chain-007, chain-008, chain-010, chain-011, chain-012, chain-013, chain-014, chain-015, chain-016, chain-017, chain-019, chain-020, chain-021, chain-022, chain-023, chain-024, chain-025, chain-026, chain-027, chain-028, chain-029, chain-030, chain-031, chain-032, chain-034, chain-035, chain-036, chain-037, chain-038, chain-039, chain-040, chain-041, chain-042, chain-043, chain-044, chain-046, search_rank-002, search_rank-004, search_rank-005, search_rank-006, search_rank-007, search_rank-008, search_rank-009, search_rank-010, search_rank-011, sequential_chain:tracker-002, sequential_chain:tracker-004, sequential_chain:tracker-005, sequential_chain:tracker-006

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
