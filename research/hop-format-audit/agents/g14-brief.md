# Группа 14: prompt_rule + branching + lookup_list

Кейсов: 55. Семейства: prompt_rule, branching, lookup_list.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - prompt_rule-013 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=None)
  - prompt_rule-016 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=None)
  - prompt_rule-022 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=None)
  - prompt_rule-028 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - prompt_rule-003 (end_to_end=0.2, chain_value=—, multi_all_out=0.0, tool_arg_form=0.7917)
  - prompt_rule-001 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - prompt_rule-004 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=None)
  - prompt_rule-010 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)

**Все case_id группы:**
branching-000, branching-001, branching-003, branching-004, branching-005, branching-006, branching-007, branching-008, branching-010, branching-011, branching-012, branching-013, branching-014, branching-015, branching-017, branching-019, branching-020, branching-022, branching-023, lookup_list-001, lookup_list-002, lookup_list-003, lookup_list-004, lookup_list-005, lookup_list-007, prompt_rule-000, prompt_rule-001, prompt_rule-002, prompt_rule-003, prompt_rule-004, prompt_rule-005, prompt_rule-006, prompt_rule-009, prompt_rule-010, prompt_rule-011, prompt_rule-012, prompt_rule-013, prompt_rule-014, prompt_rule-015, prompt_rule-016, prompt_rule-017, prompt_rule-018, prompt_rule-021, prompt_rule-022, prompt_rule-023, prompt_rule-024, prompt_rule-025, prompt_rule-026, prompt_rule-027, prompt_rule-028, prompt_rule-029, prompt_rule-030, prompt_rule-032, prompt_rule-033, prompt_rule-034

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
