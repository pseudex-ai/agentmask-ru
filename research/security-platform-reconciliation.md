# Повторная сверка спринта: ТЗ, UI-демо и актуальный код

**Статус:** read-only сверка документов после консолидации решений владельца. Не runtime-гейт и не новое изменение scope. База: `origin/main` 633fb4816a6cfae07287e5cc493174fbfe2ee958, engine version file 0.3.21, schema lock 0.3: vault9/audit1/tenants1. Прочитаны 608 текстовых строк извлечённого ТЗ, 2677 строк UI-демо (JS не запускался), три PNG-схемы и актуальные исходники. Существующие `research/security-platform-current-main-baseline.md` исправляют прежнюю ошибку выбора старой базы 380e3e72/0.3.19; этот отчёт закрывает оставшиеся внутренние противоречия документов.

## 1. Что исправлено в этой итерации

| Несогласованность | Исправление |
|---|---|
| HITL и документы были «приняты», но без F/W/gate/API/store тел | Новые F24/F25, K11/K12, T13/T14, W36–W44, H01–H10, DOCG01–DOCG10 в [контракте](<docs/tz-hitl-and-documents.md>); C4 теперь требует W39/W44 |
| Пять ролей оставались нормативом внутри F02/API/плана | admin/user + явные feature-grants; прежние роли-метки — только наименования разрешений, не role designer |
| Blanket «никакого persisted secret» противоречил encrypted HITL payload | Default block/redact без PII-mapping; явно разрешены scoped credential refs и transient encrypted approval payload; raw model egress только opt-in once-only |
| Отменённый model routing/fallback оставался задачей | T05/W15/C2/CP25 переписаны на fixed binding + preserve caller model; outage не меняет URL/model |
| Документы всё ещё были P2/«форматы не решены» | Документы на границе контекста: tool_result маскируется, file-attachment block/extract/route; без OCR и native-перезаписи файла |
| HITL всё ещё был P2/request approval | F24 очередь+API, encrypted payload, no-auto-expiry card, separate reveal grant; live-only первый релиз, cold resume позже |
| CONNECT03 «ещё обсуждается» | baseline base_url+key без mandatory SDK; strict conversation/receipt только с verified capability |
| RESTORE01 сужался до high-risk tools | любой affected unresolved tool call не исполняется; prose допускает explicit incomplete status |
| Выбранные Linux/macOS/WSL и Claude→Codex не закрывались задачами | W45/AC13 для Codex, независимые OS gates; Codex обязателен в первом C5 |
| T10/T11 не включали T13/T14 | shell ранний vs полная W26 приёмка; W27 ждёт W39/W44 |
| OIDC стартовал раньше основных сценариев | ранний contract/SP05/fixtures; production после HITL/documents |
| Отсутствовали трассировки S1: время/lineage, целостность, standalone restore | Добавлены в F09/F16/F20/F21 с явными границами (не NTP-сервис, не root-proof WORM, не HA) |

## 2. Осознанные отличия от полного S1 (НЕ «покрыто на 100%»)

1. **Standalone, не HA/cluster.** Один инстанс/одна консоль; «несколько экземпляров за балансировщиком» не реализуются в этом спринте.
2. **Не model routing/fallback.** Security proxy к заданному API; выбор провайдера/модели остаётся у caller/host.
3. **Нет универсальной semantic/all-OWASP защиты.** Jev и собственный semantic R&D отменены; NER/rules/DLP-contracts сохраняются.
4. **Без OCR/image/audio.** Документ = контент в контексте модели; native-перезапись файла и redacted-скачивание не делаются.
5. **Две роли, не полное IT/ИБ/аудитор разделение.** admin/user + grants; original reveal отдельно.
6. **Ограниченное отклонение по секретам.** approved credential refs/encrypted pending/opt-in one-use original, при default block/redact.
7. **Capture off по умолчанию.** Безопасный журнал решений, не полный архив содержимого для ИБ.
8. **Offline/air-gap engine отложен**; локальная UI/no-CDN не означает работу без лицензионного сервера.
9. **Стандартные OIDC/REST DLP/event interfaces**, не все LDAP/SCIM/ICAP/vendor/HSM.
10. **Не WebChat-перехват личных аккаунтов/полный MCP/A2A.**

Эти отклонения названы явно, а не замаскированы «есть REST adapter».

## 3. Закрытые вопросы (ответы владельца)

| ID | Решение |
|---|---|
| OPEN-C01 | Codex обязателен в первом публичном C5 (оба adapter до первого coding-выпуска) |
| OPEN-H01 | Первый релиз — только live-ожидание; cold restart/resume не обещаем; defer/resume — следующий этап |
| OPEN-H02 | Reveal выключен по default, админ включает себе отдельной операцией с аудитом |
| DOC-ARCH | Документы только на границе контекста; native-перезапись файла/redacted-скачивание исключены; file-attachment → block/extract/route; добавлен документный бенчмарк (таблицы, судебные практики, отрасли, заявления) |

Протокольные детали file-endpoints и параметры бенчмарка доказывает SP08; они не расширяют отменённые направления (fleet/OCR/offline/semantic/Jev).

## 4. Предел проверки

Сверка — документальная и статическая. Не запускались detector datasets, контейнерные гейты, models/paid API и не устанавливались сторонние библиотеки. Наличие кода в main не доказывает его наличие в ранее опубликованном image. Канонические документы живут в main; feature-worktrees создаются от fetched origin/main с зафиксированным SHA.
