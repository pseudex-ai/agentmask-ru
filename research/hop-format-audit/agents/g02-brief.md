# Группа 2: memory_anaphora #2

Кейсов: 56. Семейства: memory_anaphora.

**Мастер-таблица метрик:** `00-case-metrics.json` (ищи свой case_id; ключи: 13 метрик + `form` по 4 хопам). Общий `metrics`-список — в том же файле.

**Худшие кейсы группы (по problem-score, от худшего):**
  - memory_anaphora-095 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.0)
  - memory_anaphora-058 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-118 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)
  - memory_anaphora-085 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-074 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-098 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-104 (end_to_end=0.25, chain_value=—, multi_all_out=0.0, tool_arg_form=1.0)
  - memory_anaphora-106 (end_to_end=0.0, chain_value=—, multi_all_out=0.0, tool_arg_form=0.5)

**Все case_id группы:**
memory_anaphora-051, memory_anaphora-052, memory_anaphora-053, memory_anaphora-054, memory_anaphora-055, memory_anaphora-057, memory_anaphora-058, memory_anaphora-061, memory_anaphora-064, memory_anaphora-065, memory_anaphora-066, memory_anaphora-068, memory_anaphora-070, memory_anaphora-072, memory_anaphora-073, memory_anaphora-074, memory_anaphora-075, memory_anaphora-076, memory_anaphora-077, memory_anaphora-078, memory_anaphora-079, memory_anaphora-080, memory_anaphora-081, memory_anaphora-082, memory_anaphora-083, memory_anaphora-085, memory_anaphora-086, memory_anaphora-087, memory_anaphora-088, memory_anaphora-090, memory_anaphora-091, memory_anaphora-092, memory_anaphora-094, memory_anaphora-095, memory_anaphora-096, memory_anaphora-098, memory_anaphora-099, memory_anaphora-101, memory_anaphora-104, memory_anaphora-105, memory_anaphora-106, memory_anaphora-107, memory_anaphora-108, memory_anaphora-109, memory_anaphora-110, memory_anaphora-112, memory_anaphora-113, memory_anaphora-114, memory_anaphora-115, memory_anaphora-117, memory_anaphora-118, memory_anaphora-119, memory_anaphora-120, memory_anaphora-121, memory_anaphora-124, memory_anaphora-125

**Где смотреть данные (глазами):** определения — `prototype/bench/runs/2026-09-28/*/corpus.v5.json` и `…/2026-09-29/*/corpus.v5.json`; поток шлюза — `*.arms.v5.jsonl`; точные байты маски/реального — `*.canary.jsonl`; вердикты по хопам — `*.hops.jsonl`. Находи строки по своему case_id.
