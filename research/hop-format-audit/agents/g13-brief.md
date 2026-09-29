# Группа 13: long_support + user_in_loop + sequential_chain:assistant

Кейсов: 55. Семейства: long_support, user_in_loop, sequential_chain:assistant.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - long_support-027 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.875)
  - long_support-004 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.8462)
  - user_in_loop-019 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.5)
  - long_support-038 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.8889)
  - long_support-024 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.8333)
  - long_support-003 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.931)
  - long_support-009 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.8)
  - long_support-015 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.9474)

**Все case_id группы:**
long_support-000, long_support-001, long_support-002, long_support-003, long_support-004, long_support-005, long_support-008, long_support-009, long_support-010, long_support-011, long_support-014, long_support-015, long_support-017, long_support-018, long_support-019, long_support-020, long_support-021, long_support-022, long_support-023, long_support-024, long_support-025, long_support-027, long_support-029, long_support-030, long_support-031, long_support-032, long_support-034, long_support-035, long_support-036, long_support-037, long_support-038, long_support-039, long_support-040, long_support-041, long_support-042, sequential_chain:assistant-001, sequential_chain:assistant-002, sequential_chain:assistant-003, user_in_loop-002, user_in_loop-003, user_in_loop-004, user_in_loop-005, user_in_loop-006, user_in_loop-007, user_in_loop-008, user_in_loop-009, user_in_loop-010, user_in_loop-011, user_in_loop-012, user_in_loop-013, user_in_loop-014, user_in_loop-016, user_in_loop-017, user_in_loop-018, user_in_loop-019

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
