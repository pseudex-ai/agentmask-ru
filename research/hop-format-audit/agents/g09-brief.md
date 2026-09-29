# Группа 9: document + compare + container

Кейсов: 55. Семейства: document, compare, container.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - compare-003 (end_to_end=0.3333, chain_value=—, multi_all_out=0.0, tool_arg_form=0.25)
  - document-023 (end_to_end=0.1667, chain_value=—, multi_all_out=—, tool_arg_form=0.5294)
  - document-041 (end_to_end=0.2, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - document-004 (end_to_end=0.1667, chain_value=—, multi_all_out=—, tool_arg_form=0.5882)
  - container-001 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - container-003 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - container-005 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - container-007 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=1.0)

**Все case_id группы:**
compare-000, compare-002, compare-003, compare-004, compare-005, compare-006, compare-007, compare-008, compare-009, container-000, container-001, container-002, container-003, container-005, container-007, document-000, document-001, document-002, document-003, document-004, document-007, document-008, document-009, document-010, document-011, document-012, document-013, document-015, document-017, document-018, document-019, document-020, document-022, document-023, document-024, document-025, document-026, document-027, document-028, document-029, document-031, document-033, document-034, document-036, document-037, document-038, document-040, document-041, document-042, document-043, document-044, document-045, document-046, document-047, document-048

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
