# Build brief — must-have ядро настраиваемости (+ полный UX/UI)

**Статус:** binding-контракт исполнения для ядра настраиваемости. Это не перепланирование: он сворачивает уже принятые решения из авторитетных документов в один исполнительный контракт. Любое расхождение с авторитетным документом решается в пользу авторитетного документа.

## 0. Авторитетные источники (обязательны, не перевыводить)

Абсолютные пути (репозиторий `/Users/igor/Projects/Obscura`; при работе в worktree пути относительно его корня):

- `docs/tz-product-control-plane-sprint.md` — спецификация F01–F25, D1–D10, API/storage/security.
- `docs/plan-product-control-plane-sprint.md` — план: W-пакеты, CP01–CP47, K01–K12, T01–T14, test-first цикл, worktree/merge-контракты.
- `docs/tz-product-control-plane-matrix.md` — R01–R66, границы P0/P1/P2/X, 10 осознанных отклонений от ТЗ.
- `docs/decisions-product-control-plane.md` — хронология решений владельца (роли, политика, секреты, документы, coding).
- `docs/tz-hitl-and-documents.md` — F24/F25 (не в этом объёме, но C4 требует их потом; здесь не реализовывать).
- `research/security-platform-current-main-baseline.md` — что уже есть в current main (не реализовывать повторно).
- `research/security-platform-reconciliation.md` — закрытые OPEN-решения и осознанные отклонения.
- `prototype/CLAUDE.md` + `wiki/INVARIANTS.md` (192 правила), `wiki/MAP.md`, `wiki/FLOWS.md`, `wiki/STATE.md` — код/инварианты/порядок.
- `brand/admin-control-plane/` — UI-концепт владельца (binding UI-источник).

Запрещено: пере-исследовать рынок, пере-утверждать scope, добавлять фичи из P1/P2, откатывать принятые решения (две роли, без model-router, reveal-off по default, live-only HITL).

## 1. Объём (только must-have A)

Реализовать ядро настраиваемости и полный UX/UI поверх него:

| Возможность | F | W | Gates |
|---|---|---|---|
| Store registry/миграции (control/jobs) | F21 | W02 | CP01–CP03 |
| Две роли + выдаваемые права, named identity | F01/F02 | W03 | CP04–CP06 |
| Snapshot запроса + cache invalidation | F03 | W04 | CP07–CP09 |
| Декларативный policy engine + профили | F03 | W05 | CP10 |
| Evidence/trace инструментация | F05 | W06 | CP11 |
| Свои правила/словари/исключения (любые паттерны, не только заведённые ПД) | F05/F06 | W07 | CP12–CP13 |
| Actions/секреты (block/redact по умолчанию) | F07 | W08 | CP14–CP15 |
| Receipts и авторизованный restore по project/app | F08 | W09 | CP16–CP17 |
| Журнал каждого решения + admin audit | F09 | W10 | CP18–CP19 |
| Безопасная песочница проверки правил | F12 | W11 | CP20 |
| Prepare/activate/rollback (selected/all) | F04 | W12 | CP21–CP23 |
| CLI/import-export управления | F21 | W13 | CP38 |
| Admission/лимиты (минимально) | F10 | W14 | CP24 |
| Onboarding на несколько fixed upstream (без model-router) | F20 | W15 | CP25–CP26 |
| Каталог native-типов + профили (минимальный) | F19 | W23 | CP38/CP46 |
| Полный UX/UI по концепту владельца | F21 | W26 | CP42–CP43 |

**Вне объёма (не делать сейчас):** HITL (F24/W36–W39), документы (F25/W40–W44), coding (F23/W28–W35/W45), OIDC/DLP/SIEM (W21/W22 production), полный analytics/SDK/batch/retention. Их contracts можно готовить заранее, но не выдавать за готовое.

## 2. Роли исполнения (честность через разделение)

- **Lead реализует лично.** Никаких соавторов-агентов по коду.
- **Flash-агенты только ревью и тесты:** пишут adversarial/edge-case тесты и независимое e2e-ревью. Их вывод — доказательство, не подгонка.
- Acceptance-ораклы фиксируются ДО реализации (test-first); reviewer не видит реализацию заранее.

## 3. Последовательный spine и выходные gates

Порядок строгий; не входить в следующий шаг, пока gate предыдущего не зелёный.

1. **W01/W02** — baseline fixtures по обеим legs + store registry/миграции. Gate: CP01–CP03 (шифрование, refuse-from-future, crash-safe). Плюс существующие suites зелёные (не регрессия).
2. **W03** — identity: admin/user + grants, named sessions. Gate CP04–CP06.
3. **W04** — snapshot/cache. Gate CP07–CP09.
4. **W05** — policy schema/model (immutable revisions). Gate CP10.
5. **W06/W07/W08** — evidence → правила/словари/исключения → секреты. Gate CP11–CP15. Правила обязаны покрывать произвольные customer-паттерны (структурные, KV, regex/RE2, словари), а не только заведённые ПД.
6. **W09** — receipts/restore. Gate CP16–CP17 (RESTORE01: любой unresolved tool call не исполняется).
7. **W10** — журнал решений. Gate CP18–CP19.
8. **W11** — песочница. Gate CP20 (пустой suite ≠ pass; wrong-person мутация = fail).
9. **W12** — prepare/activate/rollback. Gate CP21–CP23 (eligible-subset-or-none, target revalidation).
10. **W13/W14/W15** — CLI/импорт → admission → fixed upstream onboarding. Gate CP24–CP26/CP38. Без model-router/fallback.
11. **W23-min** — каталог native-типов/профили. Gate CP38/CP46.
12. **W26** — полный UI по `brand/admin-control-plane/`. Gate CP42–CP43 (truthful states, unsupported = not_available, нет fake success).

DAG-зависимости из plan §3 сохраняются; шаги 5–8 могут готовить tests параллельно, но merge только по порядку.

## 4. Test-first дисциплина (обязательна)

- Сначала RED-тест на целевую логику, потом реализация; ImportError не считается осмысленным RED.
- **Запрещён happy-path-confirmation:** тесты пишутся как edge cases против логики (XSS/Unicode, ReDoS, pool exhaustion, revoke-race, foreign receipt, concurrent publish, cache-hit-noPII, empty suite, malformed JSON, wrong-person mutation). Каждый gate имеет негативный сценарий из plan §5.
- **e2e на реальном локальном инстансе:** оба legs (proxy + sidecar), N workers, реальный SQLCipher том, реальный browser (`test_localui_renders.py`, playwright). Не моки и не демо-regex.
- Приёмка только после: (a) unit/edge тесты зелёные, (b) e2e зелёное, (c) flash-reviewer подтвердил честность (не подгонку), (d) существующие батареи без регрессий, (e) source/compiled parity.
- Paid/live LLM не нужен для этого объёма.

## 5. Hard-инварианты + HALT

- Семь инвариантов из CLAUDE.md: fail-closed, no PII pre-filter, никогда не маскировать повторно (`mask(mask(x)) != mask(x)`), normalization 1:1, no bundle = 503, `pseudex/` не импортирует `licensing/` и не `import sqlite3`.
- RESTORE01: любой affected unresolved tool call не исполняется. Секреты default block/redact без reversible PII-mapping.
- Две роли только; reveal off по default; без model-router/fallback.
- **HALT и доложить, не фабриковать:** при любом красном gate, невозможности e2e, расхождении с авторитетным документом, невоспроизводимости — остановиться и зафиксировать, НЕ помечать зелёным, не придумывать результат, не выдавать unverified за trustworthy.

## 6. DO / DO NOT

- DO: атомарный commit на шаг; менять tests/docs/wiki вместе с code; фиксировать base SHA и contract revision.
- DO NOT: тянуть вперёд P1/P2, пропускать gate, пере-планировать, откатывать решения владельца, скрывать красный тест, выдавать mock-UI за production.

## 7. UI (на основе оптимизации владельца)

- Источник — `brand/admin-control-plane/interface.dc.html` (экраны: Агенты и инструменты, Волт, Журнал, Интеграция, Политика, Качество детекции, Регрессии, Библиотека шаблонов, Лицензия, Настройки контейнера).
- Дизайн-система Nocturne (тёмная, Inter, blurple #9184d9, 8px, outline-кнопки, Phosphor) из `brand/admin-control-plane/nocturne-design-system.md`.
- Экран без backend-контракта — `unsupported/not_available` с причиной, никогда не toast успеха. Двух ролей/grants достаточно; нет role-конструктора.

## 8. Языковая граница (D-090)

- UI-строки — через string table; policy/rule/decision-схемы без языко-специфичных полей.
- Языко-зависимые примитивы (детекторы/морфология/словари/spoken/даты) — сменяемый слой с объявленной границей. Новый язык сейчас НЕ реализовывать, только не зашивать русский в новые control-plane логики.

## 9. Worktree и merge

- `git fetch origin` → зафиксировать `origin/main` SHA → `git worktree add -b feat/must-core <path> origin/main`.
- Не работать от старой dirty-копии `/Users/igor/Projects/Obscura` (она на другой ветке). Документы/решения меняются в main отдельными doc-коммитами; код этого трека не трогает общий контракт без интегратора.
