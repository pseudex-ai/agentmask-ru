# Execution subagent usage — текущий quality sprint

Lead: session target gpt-6-astra. Первый исполняемый goal: goal-970b5fca-5fca-4434-88c3-20175b17679e. Это новый журнал выполнения, не повторные исследования planning waves.

| Task | Invocation | Requested routing | Inputs/scope | Output/gate |
|---|---|---|---|---|
| B0 independent review | subagent_fork d9aedfb0-84b7-4e11-a273-8288245b2005 | fork текущей Lead-сессии gpt-6-astra; explicit model override этим tool не предоставляется | только чтение B0 SPEC/checkpoint/log/INPUTS/RUNTIME/WIP-MANIFEST + archive; запись только work/B0/REVIEW.md | PASS local/design G1; durable work/B0/REVIEW.md прочитан, evidence commit890c508, production digest отдельно до RG |

## Исполняемая волна после B0

Workflow `quality-sprint-design-red-1`, job `workflow-3`, старт после G1 PASS и локального evidence commit890c508. Семь agent вызовов с **явными** overrides `provider=deepseek-official`, `model=deepseek-flash`: M1b/A1/S1/D0/V0/C0/S2. Точные задачи и индивидуальные scopes закреплены в [FIRST-WAVE-TASKS](<research/quality-sprint-2026-09-30/work/FIRST-WAVE-TASKS.json>) и [FIRST-WAVE-SCOPES](<research/quality-sprint-2026-09-30/work/FIRST-WAVE-SCOPES.md>). Завершено7/7; job_output collected. Результаты и хеши перечислены в [WAVE-1-RECEIPT](<research/quality-sprint-2026-09-30/work/WAVE-1-RECEIPT.json>), замечанияLead в [WAVE-1-INTAKE](<research/quality-sprint-2026-09-30/work/WAVE-1-INTAKE.md>). Полныеgates ещё не приняты; independentreview/ownerdecisiondedupe впереди. Каждый пишет только work/<свой ID>/; общие product/scorer файлы readonly. Lead независимо выполняет M1a.

Запрос исполнения передан каждому self-contained с GATE/REVIEW B0, bindingрешениями, exacttaskselection, запрещённымиоперациями и обязательнымиOUTPUTS. Новых benchmark/provider/prod calls эта волна не разрешает.

## M1a independent design review

Invocation `subagent_fork:7ac9e839-fe35-4124-9b90-33d9eea930d7`, inherited Lead target gpt-6-astra, отдельный reviewer не автор. Входы: work/M1a/SPEC, RED script/log/results и preserved M04prototype, ownerpolicies. Единственная запись reviewer: work/M1a/DESIGN-REVIEW.md. РезультатREVISE получен; проверены5targetproperties, требуетсяисправитьevidencefixtureизоляцию. Lead записал revision race/поправкуpushcountв work/M1a/REVIEW-RESPONSE.md, исходныйREDsourceвосстановленbyteexactпопрежнемуhash. Evidencecommit8a808ca; G2FAIL не повышается.

## Round 2 independent reviews

- `subagent_fork:362d7372-b395-4044-9164-5cdba7cb0353` — inherited gpt-6-astra, critical M1b/S1; writes only work/review-critical/. Result REVISE collected; accepted bounded REDs, rejected claims about complete vault state and missing raw/SSE.223 hashes during probes; at final221 unchanged+2 declared Lead M1a edits outside critical scope.
- `subagent_fork:5bc0b8a7-2bfa-44cc-a3f0-50a42d8a85bf` — inherited gpt-6-astra, A1/D0/V0/C0/S2; writes only work/review-contracts/. Result REVISE collected; no child fullgate promotion.30 input hashes unchanged and49citations checked. Repeated ownerquestions filtered; PPV/corpusversion/registrycounts corrected.
- `subagent_fork:19b630b1-c158-4cff-9bce-50aab90fe950` — inherited gpt-6-astra, M1a v2-dev foundation47controls; writes only work/M1a/foundation-review/. FAILED before final verdict but returned four confirmed defects (alias exact-copy bypass, non-integer chronology, unknown piece type, future-proof erasing unknown competitor). Lead fixed all four; suite now55controls.
- `subagent_fork:2f5d5333-2b4d-4757-b175-bbef132ee563` — inherited gpt-6-astra, M1a v2-dev foundation RE-review после четырёх исправлений; writes only work/M1a/foundation-review-2/. RUNNING. Two M1a source/test files FROZEN; G2remainsFAIL (adapter/derivedroles/uniquealignment unfinished).

## Bounded first-wave correction

`quality-sprint-design-revision-2`, job `workflow-4`, explicit `deepseek-official/deepseek-flash` на2agentвызова. `critical-revision` пишеттолько work/M1b/revision-2/ иwork/S1/revision-2/; `contracts-revision` —только work/contracts-revision-2/. Входы—independentreviews, originalfrozenchildoutputs, latestownerdecisions. Задача—исправитьevidence/протоколы/повторныевопросы,неproductpatch. Завершено2/2, job_output collected; оба результата REVISE в собственных scope, noG3promotion. ОбеM1a sourceправкиLeadобъявленыкакразрешённые,неатрибутируютсядругимагентам.

Собственная фраза модели не является доказательством маршрутизации. Для Flash-волн нужен explicit workflow provider/model override; он фиксируется здесь вместе с job и результирующими артефактами. Никакие paid benchmark calls этим журналом не разрешаются.

## Round 3

- `subagent_fork:840196d9-9a08-4802-a6b5-22ea67844f55` — inherited gpt-6-astra, независимый re-review исправлений M1b/S1 revision-2; writes only work/review-critical-revision2/. RUNNING. Вход — findings work/review-critical/REVIEW.md против revision-2 пакетов. G3 не повышается без этого.

Собственная фраза модели не является доказательством маршрутизации.

## Round 4

- `subagent_fork:840196d9-9a08-4802-a6b5-22ea67844f55` — inherited gpt-6-astra, независимый re-review M1b/S1 revision-2; writes only work/review-critical-revision2/. Result **PASS_CORRECTIONS** (both). Каждый REVISE finding реально исправлен, не переименован. S1 raw перечитан из arms.v5.jsonl напрямую; probe перезапущен exit4 violated{A2,B,C,D1}; full G3 stays REVISED_NOT_PASS, M1b G2 stays NOT_MEASURED. Два неблокирующих замечания (index-notation ambiguous; long_clinic-006 field label).
- Lead M1a (round 4): доказуемые инициалы через whole-name disclosure, 58/58 controls, 6 legacy suites. Bare «ПО» намеренно не кандидат (P09).

Собственная фраза модели не является доказательством маршрутизации.

## Round 5

- `subagent_fork:76fef59f-83bc-430e-802b-dde035c7e75e` — inherited gpt-6-astra, независимый implementation review M1a v2-dev на G2-readiness; writes only work/M1a/g2-review/. RUNNING. Входы заморожены (2 M1a файла + docs). Задача — вердикт PASS_G2_READY/NOT_READY по 10 пунктам M04-READINESS + adversarial false-pass попытки.

Собственная фраза модели не является доказательством маршрутизации.

- `workflow-5` `d0-isolated-perf`, job `workflow-5`, explicit deepseek-official/deepseek-flash, 1 agent. Изолированный ресурсный замер FULL vs NER_ONLY (2 arm × 3 процесса, N≥1000) по RUNBOOK-PERF; writes only work/D0/perf-isolated/. RUNNING. Предварительный проход, не финальный O-DETECT бюджет. Не трогает holdout/paid run, не ставит модели.

## Round 7

- `subagent_fork:76fef59f` — G2-readiness review = NOT_READY (LOC false-negative hard blocker). Root cause: char-level SequenceMatcher truncated LOC «…дом 14» to «…дом 1».
- `workflow-5` `d0-isolated-perf` — completed; EXPLORATORY only (pre-existing bench.agentpii5.live holds a full core 100% CPU). FULL p50 4.77ms vs NER_ONLY 0.64ms; O-DETECT stays OWNER_PENDING.
- Lead M1a (round 7): fixed alignment (word-level + exact-copy narrowing), known-unknown surfacing, positive LOC control; 60/60 controls, 6 legacy suites. All 4 G2-required items closed.
- `subagent_fork:6034ec57-f80e-4d97-90b0-c11ac474e331` — G2 re-review на замороженных входах; writes only work/M1a/g2-review-2/. RUNNING.

Собственная фраза модели не является доказательством маршрутизации.

## Round 8

- `subagent_fork:6034ec57` — G2 re-review = NOT_READY: text_status used inclusive a<=x<=b so glued boundary insertion + duplicated real were reported clean (false PASS). Fixed by literal-gaps fidelity pass + swapped-person strong pin; 63/63 controls, reviewer probe_fixes 7/7 PASS.
- Lead live.py CPU fix (owner-requested): snapshot cache now mtime-keyed (was re-walking 802 triples every 2.5s, holding a full core). Live job restarted as bash-2160, now 0% CPU.
- D0 quality evidence answered: RAW_NER 100% clean NAME, ~69% LOC, 0% structured IDs and 0/295 on real speech (news-trained NER collapses); RULES_ONLY==FULL==HYBRID on gatectx (NER adds nothing over rules on real speech).

Собственная фраза модели не является доказательством маршрутизации.

## Round 9

- `subagent_fork:8e6a267f-2e0e-4f2d-a959-9dd032563b38` — FINAL G2 re-review (3-я) на замороженных входах 63 controls; writes only work/M1a/g2-review-3/. RUNNING.

Собственная фраза модели не является доказательством маршрутизации.

## Round 9

- `subagent_fork:8e6a267f` — G2 re-review #3 = **PASS_G2_READY** (M1a G2 MET). 63/63 controls, 6 legacy suites, reviewer probe 7/7, own adversarial hunt clean. Optional items deferrable to M1c.
- Lead M1b bounded canary reader implemented (payload_canaries.py): 8 MiB row ceiling + 1 MiB payload / 4096 count bounds; saved run 810/810 readable, hostile refused; integration test pins it.

Собственная фраза модели не является доказательством маршрутизации.

## Round 10

- Lead M1c Phase 1: reader contract implemented (payload_canaries.py skip-never-abort + denominator survival). Saved run 810/810 / 20201 payloads, 0 skips, check_run MEASURED. Integration test pins chatty-accept/hostile-skip-by-name/malformed-raise. M1c SPEC records 3-phase plan.

Собственная фраза модели не является доказательством маршрутизации.
