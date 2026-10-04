# Финальные gate-контракты после ответов владельца (round 2–3)

Этот документ связывает ответы владельца с исправленными proposal и фиксирует их как binding-контракты для соответствующих задач. Сами ответы дословно — [OWNER-DECISIONS-EXECUTION](<research/quality-sprint-2026-09-30/work/OWNER-DECISIONS-EXECUTION.md>).

## O-DATA (блокирует D1-N/A/I, Q1, RG)

Binding = [O-DATA-PROPOSAL](<research/quality-sprint-2026-09-30/work/contracts-revision-2/O-DATA-PROPOSAL.md>) + [SLICES](<research/quality-sprint-2026-09-30/work/contracts-revision-2/SLICES.json>) + [BUDGET](<research/quality-sprint-2026-09-30/work/contracts-revision-2/BUDGET.json>) + три ответа:

1. **EX-O-DATA-1 (смешанный план).** Приоритетные срезы NAME/LOC/PHONE/EMAIL доводятся до ≥300 независимых позитивов; редкие типы (PASSPORT/CARD/SNILS/INN/PLATE и новые v6) печатаются отдельной строкой с явным N, источником и статусом support (`DESCRIPTIVE_INSUFFICIENT_SUPPORT`), пока идёт расширение.
2. **EX-O-DATA-2 (обе границы).** `UNRESOLVED` — отдельный N; рядом строгая нижняя граница (неразрешённые = промах) и условная (исключены). Тихая фильтрация после предсказаний запрещена.
3. **EX-O-DATA-3 (labels у владельца).** Свежий blind split: текст порождает агент, labels хранит человек-владелец; процедура доступа проверяемая. Исторический 359-ID — диагностический, не «слепой».

Зафиксированный `O-DATA` checkpoint: `OWNER_ANSWERED`. Актуальный runtime split создаётся только в момент freeze.

## O-SECRET (блокирует C1)

Binding = [TYPE-CONTRACTS](<research/quality-sprint-2026-09-30/work/C0/TYPE-CONTRACTS.json>) + [OWNER-QUESTIONS O-SECRET](<research/quality-sprint-2026-09-30/work/C0/OWNER-QUESTIONS.md>) + **EX-O-SECRET-1**: всё семейство временных секретов видимо в матрице; CVC + ISSUER_OTP (карт-/issuer-аутентификация) измеряются, TOTP/2FA/recovery/коды-авторизации/PIN остаются видимым пробелом (`NOT_MEASURED`) до своего support. OTP/3DS длина — `RESEARCH_GAP`/`UNASSERTED`, не выдумывается. Lifecycle/admin/API/HITL — следующий спринт. Реальные платёжные секреты в тестах не используются; синтетический isolated path.

## O-SEMANTIC (disposition S2)

Binding = [GAP-MATRIX](<research/quality-sprint-2026-09-30/work/S2/GAP-MATRIX.json>) + **EX-O-SEMANTIC-1**: research-only карта пробелов + disposition. Смысловые ПД (здоровье/доход/долг/судимость) — отдельный следующий спринт, НЕ фокус текущего; текущий спринт закрывает все отрасли и все остальные ПД. Никаких изменений MEDICAL/DATE сейчас; DATE-policy на MEDICAL не переносится. Реализация — только после отдельного GO.

## Остальные checkpoint

- O-DETECT — OWNER_PENDING: нужны реальные measured latency/RSS из изолированного D0 эксперимента (не contended timings из первого прогона), затем вопрос владельцу.
- O-CORE/O-V6 — NOT_RUN: evidence собран; решения покрыты существующими decisionID либо технические, не новые owner forks; фиксируются через независимый review при K1/V1.
- O-LIVE/O-RELEASE — OWNER_PENDING: отдельный GO для paid run и релиза.

## Статус

Три checkpoint (O-DATA/O-SECRET/O-SEMANTIC) закрыты на уровне design-решений. Их runtime-артефакты (замороженный split, type registry, финальный gap disposition) создаются на соответствующих этапах DAG (freeze→Q1, C1, S2→Q1). Это НЕ отменяет: G2 (M1a) всё ещё FAIL, G3 (M1b/S1) не принят, K1/V1/D1/N1/C1/Q1/L1/Z1 впереди.
