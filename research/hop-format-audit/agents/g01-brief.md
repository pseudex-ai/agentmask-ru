# Группа 1: memory_anaphora #1

Кейсов: 46. Семейства: memory_anaphora.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - memory_anaphora-005 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - memory_anaphora-016 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-017 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-047 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=0.6667)
  - memory_anaphora-002 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-033 (end_to_end=0.25, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.6471)
  - memory_anaphora-009 (end_to_end=0.25, chain_value=0.0, multi_all_out=0.0, tool_arg_form=0.75)
  - memory_anaphora-004 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)

**Все case_id группы:**
memory_anaphora-000, memory_anaphora-001, memory_anaphora-002, memory_anaphora-003, memory_anaphora-004, memory_anaphora-005, memory_anaphora-006, memory_anaphora-007, memory_anaphora-008, memory_anaphora-009, memory_anaphora-010, memory_anaphora-011, memory_anaphora-013, memory_anaphora-014, memory_anaphora-016, memory_anaphora-017, memory_anaphora-018, memory_anaphora-019, memory_anaphora-020, memory_anaphora-021, memory_anaphora-022, memory_anaphora-023, memory_anaphora-024, memory_anaphora-025, memory_anaphora-026, memory_anaphora-027, memory_anaphora-028, memory_anaphora-029, memory_anaphora-030, memory_anaphora-031, memory_anaphora-032, memory_anaphora-033, memory_anaphora-034, memory_anaphora-035, memory_anaphora-036, memory_anaphora-037, memory_anaphora-038, memory_anaphora-039, memory_anaphora-040, memory_anaphora-043, memory_anaphora-044, memory_anaphora-045, memory_anaphora-046, memory_anaphora-047, memory_anaphora-049, memory_anaphora-050

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
