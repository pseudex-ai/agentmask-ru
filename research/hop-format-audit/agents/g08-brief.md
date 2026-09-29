# Группа 8: single + normalize + sequential_chain:mailfind

Кейсов: 54. Семейства: single, normalize, sequential_chain:mailfind.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - single-039 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.0)
  - single-029 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - normalize-003 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.3636)
  - single-013 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.6667)
  - single-021 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - single-002 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.0)
  - single-050 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.0)
  - normalize-000 (end_to_end=0.2308, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)

**Все case_id группы:**
normalize-000, normalize-001, normalize-002, normalize-003, normalize-004, normalize-005, normalize-006, normalize-008, normalize-009, sequential_chain:mailfind-000, sequential_chain:mailfind-001, sequential_chain:mailfind-002, sequential_chain:mailfind-003, single-001, single-002, single-003, single-004, single-005, single-006, single-007, single-008, single-009, single-010, single-011, single-012, single-013, single-014, single-015, single-016, single-017, single-020, single-021, single-023, single-024, single-026, single-027, single-028, single-029, single-030, single-031, single-032, single-034, single-036, single-038, single-039, single-041, single-043, single-044, single-046, single-047, single-048, single-049, single-050, single-051

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
