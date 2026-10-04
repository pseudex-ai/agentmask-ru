# Группа 11: long_bank + sequential_chain:mail + summary

Кейсов: 54. Семейства: long_bank, sequential_chain:mail, summary.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - sequential_chain:mail-005 (end_to_end=—, chain_value=0.0, multi_all_out=—, tool_arg_form=None)
  - sequential_chain:mail-011 (end_to_end=—, chain_value=0.0, multi_all_out=—, tool_arg_form=None)
  - summary-003 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=0.2)
  - summary-007 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=0.4)
  - long_bank-025 (end_to_end=—, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - long_bank-028 (end_to_end=—, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - long_bank-031 (end_to_end=—, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - long_bank-023 (end_to_end=—, chain_value=—, multi_all_out=—, tool_arg_form=1.0)

**Все case_id группы:**
long_bank-000, long_bank-001, long_bank-002, long_bank-003, long_bank-004, long_bank-005, long_bank-006, long_bank-007, long_bank-008, long_bank-009, long_bank-011, long_bank-012, long_bank-014, long_bank-016, long_bank-018, long_bank-019, long_bank-020, long_bank-021, long_bank-022, long_bank-023, long_bank-024, long_bank-025, long_bank-026, long_bank-027, long_bank-028, long_bank-029, long_bank-030, long_bank-031, long_bank-033, long_bank-034, long_bank-035, long_bank-036, long_bank-038, long_bank-039, long_bank-041, long_bank-042, sequential_chain:mail-000, sequential_chain:mail-001, sequential_chain:mail-003, sequential_chain:mail-004, sequential_chain:mail-005, sequential_chain:mail-006, sequential_chain:mail-007, sequential_chain:mail-009, sequential_chain:mail-010, sequential_chain:mail-011, summary-000, summary-002, summary-003, summary-004, summary-005, summary-006, summary-007, summary-008

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
