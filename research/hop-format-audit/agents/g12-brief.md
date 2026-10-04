# Группа 12: long_clinic + fanout_pick + analytics

Кейсов: 55. Семейства: long_clinic, fanout_pick, analytics.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - long_clinic-007 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - long_clinic-005 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.7143)
  - analytics-002 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.6667)
  - long_clinic-008 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - analytics-003 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.6667)
  - analytics-000 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.8)
  - long_clinic-043 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.875)
  - long_clinic-000 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)

**Все case_id группы:**
analytics-000, analytics-002, analytics-003, fanout_pick-000, fanout_pick-001, fanout_pick-002, fanout_pick-004, fanout_pick-005, fanout_pick-007, fanout_pick-008, fanout_pick-009, fanout_pick-010, fanout_pick-011, fanout_pick-012, fanout_pick-013, fanout_pick-016, fanout_pick-017, fanout_pick-019, fanout_pick-020, fanout_pick-022, long_clinic-000, long_clinic-001, long_clinic-002, long_clinic-003, long_clinic-004, long_clinic-005, long_clinic-006, long_clinic-007, long_clinic-008, long_clinic-010, long_clinic-011, long_clinic-012, long_clinic-013, long_clinic-014, long_clinic-015, long_clinic-017, long_clinic-020, long_clinic-022, long_clinic-024, long_clinic-027, long_clinic-028, long_clinic-029, long_clinic-030, long_clinic-031, long_clinic-032, long_clinic-033, long_clinic-034, long_clinic-035, long_clinic-036, long_clinic-038, long_clinic-039, long_clinic-041, long_clinic-042, long_clinic-043, long_clinic-044

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
