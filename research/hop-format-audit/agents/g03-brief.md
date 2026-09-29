# Группа 3: retry_same_tool + crm_note

Кейсов: 55. Семейства: retry_same_tool, crm_note.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - retry_same_tool-053 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - crm_note-000 (end_to_end=—, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - crm_note-002 (end_to_end=—, chain_value=—, multi_all_out=—, tool_arg_form=0.8)
  - crm_note-004 (end_to_end=—, chain_value=—, multi_all_out=—, tool_arg_form=1.0)
  - retry_same_tool-025 (end_to_end=0.5, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)
  - retry_same_tool-048 (end_to_end=0.5, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - retry_same_tool-009 (end_to_end=0.5, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)
  - retry_same_tool-021 (end_to_end=0.5, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)

**Все case_id группы:**
crm_note-000, crm_note-001, crm_note-002, crm_note-003, crm_note-004, retry_same_tool-000, retry_same_tool-003, retry_same_tool-004, retry_same_tool-006, retry_same_tool-007, retry_same_tool-008, retry_same_tool-009, retry_same_tool-010, retry_same_tool-011, retry_same_tool-012, retry_same_tool-013, retry_same_tool-014, retry_same_tool-015, retry_same_tool-016, retry_same_tool-019, retry_same_tool-020, retry_same_tool-021, retry_same_tool-022, retry_same_tool-023, retry_same_tool-025, retry_same_tool-026, retry_same_tool-027, retry_same_tool-028, retry_same_tool-030, retry_same_tool-032, retry_same_tool-033, retry_same_tool-034, retry_same_tool-035, retry_same_tool-036, retry_same_tool-037, retry_same_tool-038, retry_same_tool-039, retry_same_tool-040, retry_same_tool-043, retry_same_tool-045, retry_same_tool-046, retry_same_tool-047, retry_same_tool-048, retry_same_tool-049, retry_same_tool-050, retry_same_tool-051, retry_same_tool-052, retry_same_tool-053, retry_same_tool-054, retry_same_tool-055, retry_same_tool-056, retry_same_tool-060, retry_same_tool-061, retry_same_tool-062, retry_same_tool-063

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
