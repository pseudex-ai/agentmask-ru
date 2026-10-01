# M1c — benchmark writer (приёмка reader-контракта + legacy adapter + wiring)

Статус: M1a G2 MET (PASS_G2_READY). M1b design/RED PASS_CORRECTIONS, engine reader остаётся на 4 MiB (NOT_MEASURED). M1c — единственный benchmark writer (Lead): принимает reader-контракт из [M1b revision-2](<research/quality-sprint-2026-09-30/work/M1b/revision-2/SPEC.md#L71-L106>), реализует его в engine, строит legacy adapter, подключает M04 `answer_events` и canary reader в report. **Никакой опубликованный score до готовности legacy adapter.**

## Фаза 1 — reader-контракт (payload_canaries.py)

Принять design D1 из revision-2:
1. Row ceiling 8 MiB (derived), payload bound 1 MiB + count 4096 (load-bearing).
2. **Skip, never abort:** строка за жёсткой границей пропускается с именем/счётом, остальные строки читаются.
3. **Denominator survives** на каждом пути (triples journal, `_expected_capture_keys`).
4. **No status softening:** если есть пропуски — глобальный вердикт NOT_MEASURED (частичное чтение ≠ полное покрытие); parity hard fail остаётся fail-closed.

API: `read_captures` возвращает прочитанные строки И запись о пропущенных (named/counted); `check_run` читает denominator ДО/ПОСЛЕ и при пропусках отдаёт NOT_MEASURED с coverage.

## Фаза 2 — legacy capture adapter (новый модуль)

Строит `DisclosureProof`/`AnswerEvidence` из сохранённых данных:
- **tool_result:** доказуемо (ToolResultRecord `text_real`/`text_masked`/`spans_real`/`pieces` + `call_requests[i]` + `available_results`). Adapter строит proof с провайдер-линком.
- **message:** НЕ доказуемо (`model_request` — push-снапшот без provider ordinal). Остаётся UNKNOWN.
- Без `zip(push snapshots, provider responses)` и last-response fallback.

## Фаза 3 — wiring (report/live, без score)

- Подключить `answer_events(case, run, *, evidence)` к benchmark report как отдельный additive блок.
- Пока legacy adapter не готов — real run отдаёт all-UNKNOWN + `unsupported_spellings`/status breakdown явно; НЕ публиковать числовой answer-restoration rate.
- Frozen counters (старые 38 metrics) не двигаются; meter gain ≠ engine gain.

## Ограничения

- Correction meter (M04) и improvement engine (K1) — разные changesets, не смешивать.
- Old raw outputs не менять; новые output-пути/версии.
- Никаких engine/scorer/raw/paid изменений; `answer_real`/`observe`/`contracts` неизменны.

## Приёмка

Независимый review Фазы 1 (reader) отдельно, затем Фазы 2–3 (adapter+wiring). G2 для reader: saved run 810/810 читается, hostile строка пропускается с именем/счётом, denominator выживает, частичное ≠ полное.
