# DoubleUp × Obscura: результаты локального пилота

Срез: 23.10.2026. Внутренний отчёт без исходных клиентских значений и credentials.
**Вердикт: локальная интеграция доказана; сравнительное качество завершённых
агентных задач пока не доказано. Это не разрешение выкладки.**

## 1. Что найдено в ветках

- Исходная рабочая ветка Obscura отставала от локального `main` на 336 коммитов.
  Её многочисленные dirty changes не переключались, не очищались и не переносились.
- Закоммиченные V5/V6 уже входили в `main`; повторное объединение исторических
  веток не нужно. В `main` есть исправления dispatch V6 mock backend и live schemas,
  которых ещё нет на старом integration HEAD.
- В V5 есть 11 обобщённых клиентских схем и 64 synthetic сценария. Это не полный
  контракт реальных инструментов DoubleUp. У ветки 2UP единственный уникальный
  коммит — benchmark-adapter, не production connector. Его scripted-copy результаты
  нельзя выдавать за качество текущих живых агентов.
- Версия движка `0.3.21` и версии benchmark V5/V6 — разные оси.
- [Офлайн-контракт](../docs/tz-offline-license.md) принят, но реализации/гейтов
  O1–O19 нет. Локальный пилот использует настоящий online lease от локального
  licensing server, не «офлайн по grace».

Отдельные worktree, без merge/push/выкладки:

| Проект | Ветка пилота | Baseline SHA |
|---|---|---|
| Obscura | `feat/doubleup-local-pilot` | `a0c880a05aa5c8d2d183ba929809663b37d6fb6b` |
| DoubleUp backend | `feat/pseudex-local-pilot` | `16daf3cd296d6ef89145485de684c72659ca9fad` |
| DoubleUp frontend | `feat/pseudex-local-pilot` | `6318d33c6bf494f694835f484cb97868100d844d` |

Baseline dirty documentation в клиентских worktree сохранена отдельно от наших
Python/frontend изменений. Теги, release registry, dev/prod-конфигурация и
клиентские инструменты не менялись. Разрешённые модельные вызовы через общий
LiteLLM, разумеется, были; это не утверждение об отсутствии биллинговых событий.

## 2. Что реально работает

- Изолированные БД, Redis и тома; отдельный Compose project и loopback-порты.
  Старый «healthy» стенд проверял только TCP и конфликтовал с чужим приложением —
  он не был использован как доказательство готовности.
- Три режима на реальном DoubleUp HTTP boundary: `none`, существующий `builtin`,
  `pseudex`. Builtin сохраняет Redis/policy/fail-open, другие режимы не маскируются
  дважды. У защищённого пути нет raw fallback на ошибке.
- Source и **настоящий Nuitka compiled** контейнер прошли HTTP inspection gate:
  точные offsets, прежний response без opt-in, JSON round-trip, audited reveal,
  раздельные auth surfaces. В compiled image нет `/app/pseudex`.
- Собран отдельный backend verification image с кодом внутри, **без bind mount
  приложения**: health, настоящий вход, авторизация/no-store и трёхрежимный вызов
  инструмента прошли. Dependency image переиспользована; это не полный rebuild
  requirements и не release image публикация.
- Настоящий authenticated web path `User API → graph RPC → Pseudex → model fixture`
  прошёл: HTTP 200, start/events/end, ответ получен, создан новый protected attempt
  с тремя подменами. SSE веб-события работают; SSE **от провайдера модели** — другая
  граница, в этом connector пока не поддержана.
- В реальном desktop/mobile чате есть четыре представления границы. Браузер
  проверил реальные backend snapshots, точные пары «исходный фрагмент → форма модели»
  по записанным offsets, явное подтверждение реального reveal и удаление plaintext
  при закрытии. Credential браузера — только пользовательский
  JWT, не ключи контейнера.

Контракт и команды — в [runbook](../docs/integration-doubleup-local.md).

## 3. Проверка механизма поломки инструмента

В детерминированном сценарии provider fixture копирует увиденное значение в
аргумент; **реальный DoubleUp исполнитель** вызывает локальный безопасный tool.
Далее выполняется второй model hop. Source/compiled HTTP-путь проверен отдельно.

| Режим | Tool действительно вызван | Аргумент равен исходному | Второй hop |
|---|---:|---:|---:|
| Без защиты | да | да | да |
| Встроенная защита DoubleUp | да | **нет** | да |
| Pseudex | да | **да** | да |

У builtin дошёл плейсхолдер, не исходное значение. Это не обязательно исключение
или битый JSON: инструмент может успешно записать **не те данные**. Механизм
соответствует просмотренному коду: точный restore в финальном тексте, но не перед
исполнением аргументов. Конкретная CRM/почта клиента здесь не исполнялась.

Это сильное доказательство connector-дефекта **при активном маскировании**, но
не процент поломок живых агентов и не утверждение, что каждый исторический Qwen
запрос проходил этот режим. Встроенная политика пропускает локальные модели.

## 4. Реальные схемы инструментов

В локальном runtime registry 106 записей. Исключены 54 скрытых benchmark/retired
записи. **52 платформенных инструмента** имеют реальные JSON-схемы.

Все 52 прошли `/mask` в лицензированном контейнере: имена функций и исполняемая
структура schemas не изменились. Description/title могли изменяться; записано
44 replacement occurrence. Comparator отдельно проверен на способность заметить
изменение argument с именем `title`, required, enum/default literal и function
name — он не стирает исполняемые данные под видом metadata.

**Граница:** это schema-contract coverage, не успешное исполнение 52 внешних
интеграций. Доступность credential-dependent инструментов также не измерялась.

## 5. Исходный Langfuse корпус

Видимый проект: один. За окно 30 дней инвентаризировано 25 902 trace; API pagination
и временные границы проверены. API ключи не печатались. Выгружены **200 оригинальных
трейсов**, без предварительного обезличивания, с encrypted originals и hash/AAD
provenance. Загруженное исходное содержимое не заменялось синтетикой.

Критическое ограничение: list metadata недостаточно для conversation identity.
Full detail дал 88 attributed traces, но не все с dialogue ID. Первоначальная
trace-level разбивка имела пять пересечений известного диалога между train и
holdout. Она **не используется** как доказательство независимости.

После отдельного `reconcile`, без изменения originals:

| Показатель | Значение |
|---|---:|
| Исходных traces | 200 |
| Консервативных наблюдаемых групп | 189 |
| Подтверждённых dialogue-identity групп | 76 |
| Train / holdout подтверждённых групп | 60 / 16 |
| Unscoped, исключены из сравнительных метрик | 113 |
| Известных пересечений между split | 0 |
| Полная история диалогов доказана | **нет** |

85 schema occurrences в корпусе — это **13 вариантов схем семи имён**, не 85
разных инструментов. Встречены `generate_image`, `internet_search`, `kb_open`,
`kb_search`, `read_webpage`, `save_to_memory`, `search_memory`; динамические
KB/memory tools и базовый runtime catalog — не один и тот же список.

Независимой разметки чувствительных spans пока нет. Содержимое «original trace»
означает как сохранено источником, не гарантию наличия pre-mask пользовательского
исходника. Unknown tenancy не восстанавливалась из `userId` догадками. Корпус —
forensic evidence, не выдуманное продолжение агента.

## 6. Живой smoke: фактические результаты

Выбраны три original inputs с реальными схемами и различными tool-set shapes.
Все tool-bearing traces этой первой выборки были на Qwen3.8, отсутствующей в
текущем каталоге. Владелец разрешил **DeepSeek-v4-flash во всех плечах**.

Параметры воспроизведения:
- original messages и tool schemas не изменены;
- модель заменена явно, transport buffered/nonstream;
- thinking выключен одинаково во всех плечах: нельзя дописать отсутствующую
  `reasoning_content` к Qwen history и назвать её исходной;
- C/C′ — два контроля, B — builtin HIGH/L3 preset на локальном org, P — Pseudex;
  оригинальные org overrides этой выборкой не установлены;
- это **одна генерация на плечо**, не полный причинный цикл исходной задачи;
- tool-bearing случаи оказались unscoped и используются только диагностически,
  не как независимый статистический holdout.

| Случай | Calls C / C′ / B / P | Schema validity вызовов | P replacement occurrences | Реальное исполнение |
|---|---|---|---:|---:|
| `3b9f8bd4ac4c` | 0 / 0 / 0 / 0 | не сравнимо | 9 | 0 |
| `dcc522ff8f50` | 0 / 0 / 0 / 0 | не сравнимо | 1 | 0 |
| `06c838e4da4a` | 2 / 2 / 2 / 2 | все 8 вызовов валидны | 1 | 0 |

**12/12 API responses ≠ 12 успешных задач.** В двух случаях модель не действовала
ни в одном плече. В третьем не возникло sensitive-argument restoration opportunity:
parsed arguments при unmask не изменились. В двух последних случаях единственная
P replacement относилась не к message payload, а к schema metadata. Разное число
подмен не является измерением recall/precision. Между C и C′ имена инструментов
совпали, точные аргументы — нет: собственный разброс модели уже наблюдается.

Отсюда нельзя вывести ни «Pseudex не влияет на задачи», ни «Pseudex лучше на X%».
TOST/CI на этом smoke не публикуются. Корректный вывод — внешний модельный путь,
получение и восстановление ответов/аргументов, хранение evidence работают; качество
реальных завершённых действий требует отдельного прибора и данных.

### Деньги и остановка

Лимит persistent ledger: $10. На момент сбора:
- 12 settled вызовов: **$0.0112175** — оценка по usage и базовым тарифам;
- первый отклонённый provider request без usage: **$0.0361032** консервативно
  удержано, не выдано за фактическую стоимость;
- всего потрачено/зарезервировано **$0.0473207**, осталось **$9.9526793**;
- граница reservation не нарушалась; live egress выключен, connector снова fixture.

Первый отклонённый вызов — несовместимость thinking history после замены модели,
не ошибка Pseudex. V1 и V2 сохраняются раздельно, история не «чинится» задним числом,
неопределённая сумма не возвращается для повторной оплаты того же unknown request.
Это не подтверждённый счёт провайдера. Per-request `no-log` был запрошен; его
централизованное разрешение на общем шлюзе не доказано. Локальный Langfuse SDK off.

## 7. Найденные и исправленные дефекты

1. **Compiled-only ошибка preprocessing.** Функция `replacement` в другом модуле
   сделала одноимённое поле dataclass кандидатом на rename. Source и ASGI тесты
   проходили; реальный compiled `/mask` падал. Введён запрет такого rename,
   can-fail регрессия сначала воспроизвела проблему, новый binary gate прошёл.
2. **Пароль в URL до hydration формы входа.** Native form fallback использовал GET.
   Исправлены method POST и disabled submit до hydration, тестовый пароль сразу
   заменён. Реальный браузер проверил SSR без JS и успешный обычный вход без password
   в URL. Это исправление находится только в локальной ветке.
3. **False independence intake.** Full-detail dialogue identity теперь reconciled;
   unscoped помещён в карантин, crossing split и дубли диалога отклоняются.
4. **Comparator мог игнорировать property `title`.** Исполняемые имена и literal
   enum/default отделены от metadata title/description; специальные негативные
   тесты действительно могут уронить gate.
5. Accessibility name inspector conflicted с default hidden title общего Sheet.
   У панели установлен явный name; после исправления реальный browser gate прошёл.

## 8. Проверки и evidence

| Проверка | Результат и граница |
|---|---|
| Новый inspection core/HTTP | 7 suites, source apps, без внешней сети |
| Runtime-field preprocessing regression | PASS; сначала воспроизводила compiled дефект |
| Existing HTTP/perf, error echoes, detok security | PASS; echo controls 313/313 |
| Intake/reconcile | 38 synthetic tests; encrypted original manifests проверены |
| Budget / catalog comparator | 11 / 5 tests, без model calls |
| Backend focused final | 50 passed, внешняя сеть запрещена |
| Backend предыдущий полный | 6190 passed / 30 skipped; существующий tokenizer cache |
| Backend финальный полный | **6194 passed / 30 skipped / 34 warnings**, 274.75 s, внешняя сеть запрещена |
| Frontend | **110/110**, typecheck и lint проходят; legacy warnings сохранены |
| Real browser | четыре границы, реальный reveal, очистка plaintext, SSR login guard |
| Real web RPC | authenticated `/query` → graph → protected fixture, PASS |
| Source/compiled engine HTTP | оба PASS, реальное лицензирование |
| Baked backend | real login/API/трёхрежимный tool fixture, без source bind mount, PASS |
| Full release/security/load suite | **не выполнялась как релизная приёмка** |

Локальные generated evidence (не публиковать весь state, там ключи):
[HTTP source](../deploy/doubleup-pilot/.state/http-inspection-gate.json),
[HTTP compiled](../deploy/doubleup-pilot/.state/http-inspection-gate-compiled.json),
[baked backend](../deploy/doubleup-pilot/.state/baked-backend-gate.json),
[browser](../deploy/doubleup-pilot/.state/browser-gate.json),
[web query](../deploy/doubleup-pilot/.state/web-query-gate.json),
[catalog](../deploy/doubleup-pilot/.state/catalog-gate.json),
[fixture](../deploy/doubleup-pilot/.state/fixture-gate.json),
[live counts](../deploy/doubleup-pilot/.state/live-summary.json).

Скриншоты содержат только synthetic демонстрацию:
[исходное → форма модели](../deploy/doubleup-pilot/.state/browser/replacement-pairs.png),
[граница модели](../deploy/doubleup-pilot/.state/browser/model-boundary.png),
[передача инструменту](../deploy/doubleup-pilot/.state/browser/tool-boundary.png).

## 9. Решение о следующем этапе

**Можно:** открыть локальное демо, обсуждать контракт интеграции, показать
механизм плейсхолдера в инструменте и надёжное inspection evidence. Все source
изменения остаются в отдельных worktree, `main` не обновлялся, PR/release не созданы.

**Нельзя пока:** продавать числа качества или обещать отсутствие влияния на
агентов, поддержку всех 52 действий, SSE/native SDK или offline delivery.

До dev нужны: контекстная PII ground truth; релевантная source выборка с достоверной
conversation/tenant attribution; полный causal loop с безопасными исполнителями и
oracle итогового состояния; provider SSE и SDK adapters; нагрузка/конкурентность,
shared-thread authorization и release gates; затем отдельно согласованный canary.
Офлайн-лицензия — отдельный принятый контракт и релизный блок, не добавление флага.

Быстрый путь OpenAI nonstream уже реализован локально. Срок полного dev-внедрения
по этому smoke не измерен; выдавать его за «заменить base_url и готово» нельзя.
