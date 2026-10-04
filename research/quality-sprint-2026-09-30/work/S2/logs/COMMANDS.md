# S2 — exact commands, exits, environment

Все команды выполнены 2026-10-01 из `/Users/igor/Projects/Obscura-hop-audit`, интерпретатор
`prototype/.venv/bin/python`, `PYTHONDONTWRITEBYTECODE=1`. Ни одной записи вне `work/S2/`;
`git status` не изменился, новых `__pycache__` под `prototype/` нет.

| # | команда | cwd | exit | лог |
|---|---|---|---:|:--|
| 1 | `PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python ../research/quality-sprint-2026-09-30/work/S2/probes/semantic_probe.py` | `prototype` | 0 | [semantic_probe.log](semantic_probe.log) |
| 2 | `PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/S2/probes/build_inputs.py` | root | 0 | [build_inputs.log](build_inputs.log) |
| 3 | `PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/S2/probes/build_matrix.py` | root | 0 | [build_matrix.log](build_matrix.log) |
| 4 | `PYTHONDONTWRITEBYTECODE=1 prototype/.venv/bin/python research/quality-sprint-2026-09-30/work/S2/probes/verify_outputs.py` | root | 0 | [verify_outputs.log](verify_outputs.log) |

Проверки чтения и закрепления (без записи):

- `git rev-parse HEAD` → `890c50849a326f882eac336ba4e38c91171de473` (evidence).
- `git diff --stat 0bfda236..HEAD -- prototype/pseudex prototype/licensing prototype/testkit.py prototype/test_coverage_152fz.py` → пусто, exit0: продукт не сдвинулся.
- `build_inputs.py` → `pinned_sources=7 mismatches=[]`.
- `verify_outputs.py` → `CHECKS 19 FAILURES 0`.

Окружение probe: `load_dev_bundle()` (in-process, из `licensing/pack.py`), `Vault(":memory:", ...)`
на каждый эпизод, никакой сети, провайдера, установок и загрузок моделей. Внешние обращения —
только два `web_fetch` официального текста 152-ФЗ (ссылки в `INPUTS.json` → `legal_sources_fetched`).

Запрошенная маршрутизация этой задачи — `deepseek-official`/`deepseek-flash` (задана родителем);
технического доказательства собственной идентичности модели не приводится и не заявляется.
