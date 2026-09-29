# Группа 7: rag + decompose + receipt

Кейсов: 54. Семейства: rag, decompose, receipt.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - decompose-002 (end_to_end=0.3333, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - decompose-007 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=None)
  - rag-046 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - decompose-008 (end_to_end=0.3333, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - rag-034 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.25)
  - rag-035 (end_to_end=0.0, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - decompose-005 (end_to_end=0.3333, chain_value=—, multi_all_out=—, tool_arg_form=0.3333)
  - receipt-000 (end_to_end=0.5, chain_value=—, multi_all_out=—, tool_arg_form=0.5)

**Все case_id группы:**
decompose-000, decompose-001, decompose-002, decompose-003, decompose-004, decompose-005, decompose-006, decompose-007, decompose-008, rag-000, rag-001, rag-002, rag-003, rag-004, rag-005, rag-006, rag-007, rag-008, rag-009, rag-011, rag-013, rag-014, rag-015, rag-016, rag-018, rag-019, rag-020, rag-021, rag-022, rag-024, rag-025, rag-026, rag-027, rag-029, rag-030, rag-031, rag-032, rag-033, rag-034, rag-035, rag-037, rag-038, rag-039, rag-040, rag-045, rag-046, rag-047, rag-048, rag-049, rag-050, receipt-000, receipt-002, receipt-003, receipt-005

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
