# Методологический разбор спринта: решения владельца

**Статус:** активное обсуждение, не разрешение на реализацию. Записываем высокоуровневые решения последовательно вместе с владельцем. Общая положительная оценка плана не считается автоматическим утверждением всех предложенных defaults.

Связанные документы: [спецификация](<docs/tz-product-control-plane-sprint.md>), [план](<docs/plan-product-control-plane-sprint.md>), [матрица](<docs/tz-product-control-plane-matrix.md>), [AI-разработка](<docs/tz-ai-coding-track.md>).

## 1. Порядок согласования

1. Перед вопросом объяснить пользовательский результат, варианты и цену каждого. Рекомендация архитектора — отдельная метка, не ответ за владельца.
2. Обсуждать небольшими блоками, начиная с решений, от которых зависит больше остальных. Не задавать сразу десятки взаимозависимых вопросов.
3. Статусы: `open`, `proposed`, `accepted`, `deferred`, `rejected`, `superseded`. Условное «да, если…» фиксируется вместе с условием; двусмысленный ответ уточняется, не достраивается.
4. Для каждого принятого решения: выбор, исходная формулировка/смысл ответа, причина, альтернативы, компромисс, затронутые F/K/T/W/CP/AC, изменения документов и тестов. Причину, которую владелец не назвал, помечать как инженерное следствие, не приписывать владельцу.
5. Обновлять affected spec/plan/matrix после ответа. Не удалять старое решение: при пересмотре указывать, какое новое обстоятельство его заменило.
6. Отдельно различать продуктовый выбор и техническую проверку реализуемости: решение использовать harness не доказывает наличие нужного hook; spike остаётся обязательным.
7. Низкоуровневую механику выводить из утверждённых принципов. Если остаётся выбор с последствиями для приватности, UX, стоимости, качества или доступности — тоже вынести владельцу.
8. Существующие safety invariants не ослабляются молча. Несовместимый с ними новый выбор требует отдельного явно обсуждённого изменения модели угроз/обещаний.
9. Не реализовывать код, не запускать paid eval и не публиковать релизы в ходе обсуждения. Реестр фиксирует методологию продукта; он не заменяет runtime acceptance.

## 2. Уже явно выраженные решения

### OWN-01 — модульная платформа безопасности ИИ

**Статус:** accepted (направление продукта).
**Основание:** владелец выбрал «Модульная платформа безопасности ИИ» вместо обязательной замены всего AI gateway.
**Выбор:** единые политики/защита/интеграции; допускаются собственный proxy и встраивание в existing gateway.
**Не означает:** утверждение всех компонентов, протоколов и всех P1 позиций текущей спецификации. Детали обсуждаются ниже.

### OWN-02 — аудитория

**Статус:** accepted.
**Основание:** интеграторы/владельцы B2B AI-платформ; дополнительно разработчики и техлиды, затем coding-agent сценарии.
**Выбор:** конфигурируемый переиспользуемый продукт, не кастомная реализация одному заказчику. Сделка/пилот не управляют этой дискуссией.

### OWN-03 — ядра, параллельные feature-треки, тесты до реализации

**Статус:** accepted (организация разработки).
**Основание:** прямой запрос на максимальный фокус на ядрах, параллельность между треками, последовательность внутри трека, предварительные tests/gates.
**Выбор:** contract/test-first, scoped delegation, independent acceptance и real integration.
**Не означает:** техническое одобрение каждого K-модуля и каждой предложенной библиотеки.

### OWN-04 — AI-разработка в том же спринте

**Статус:** accepted (включение направления).
**Основание:** «впиши … как отдельный трек … может после всех остальных … выпускать целостную систему».
**Выбор:** T12 включён в общий план; завершающее положение — текущая согласованная рабочая последовательность, конкретные границы coding v1 обсуждаем отдельно.
**Не означает:** подтверждённую совместимость Claude Code/Linux/любого Bash; эти defaults пока proposed и зависят от ответов и SP07.

### OWN-05 — Jev отменён

**Статус:** rejected для интеграции в текущем спринте.
**Основание:** прямое «тогда отмена по jev».
**Выбор:** нет Jev adapter/eval/procurement или dependency в объёме этого спринта. [Исследование](<research/jev-typesafe-product-fit.md>) сохраняется как архив, его прежняя рекомендация optional evaluation больше не действующий план работ.
**Не означает:** автоматический запрет всех будущих локальных classifiers или уже обоснованных DLP-интеграций. Это отдельные архитектурные вопросы.

### OWN-06 — ключевые решения проходят владельца

**Статус:** accepted (процесс согласования).
**Основание:** владелец попросил разобрать все неоднозначные архитектурные, UX, логические и компонентные решения и фиксировать его выбор.
**Выбор:** исходная спека — набор гипотез; решения не считаются утверждёнными по молчанию. Дискуссия идёт от границ/топологии к зависимым механизмам, с явными альтернативами и последствиями.

## 3. Карта развилок: ничего из open не утверждено

Это начальный реестр областей, не обещание, что обнаружатся ровно 30 решений. При чтении зависимых контрактов добавляются дочерние вопросы. Низкоуровневые проблемы не маскируются под выбор продукта, но и продуктовые компромиссы не называются «единственно правильной реализацией».

| ID | Что предстоит выбрать | Почему влияет на результат | Затронутые области | Статус |
|---|---|---|---|---|
| AR01 | Единица управления: отдельная установка или несколько узлов под общей консолью | Независимые продукты/контуры versus единый distributed control plane | F01/F04/F20/F21; K01/K04 | accepted revised: один инстанс = одна консоль; multi-node superseded |
| AR02 | Размещение конечных клиентов: отдельные экземпляры или общая multi-tenant установка | Isolation, keys, noisy neighbour, blast radius, стоимость внедрения | F01/F02/F08/F15; K01/K02/K06 | accepted: независимый контур/консоль каждого клиента |
| AR03 | Продуктовая поверхность интегратора: наша консоль/API или встроенное управление/white-label | Объём API/UX, кому адресована админка, границы поддержки | F02/F18/F20; T01/T03/T10 | accepted: готовая консоль + полный API |
| AR04 | Топология процессов и state: один контейнер/compose/раздельные компоненты | Простота запуска, независимое обновление, минимальные ресурсы | F21; W02; K01 | accepted: быстрый standalone запуск, без control center/Kubernetes |
| AR05 | Хранилища и HA уже в спринте или отдельный промышленный режим | SQLite/new backend, отказоустойчивость, цена поддержки | F15/F21; R58; K01/K06 | deferred: multi-node/HA вне текущего спринта |
| AR06 | Что делаем сами на пути модели, что обязан делать host | End-to-end authority, routing, bypass, требования к интеграции | F10/F11/F18/F22; K09 | open |
| AR07 | Лицензирование/offline и доступ к восстановлению после остановки | Доступность клиента, защита IP, права на собственные данные | F08/F21; R59 | open |
| AR08 | Identity пользователей/приложений/агентов и доверие host assertions | Кому разрешено устанавливать policy-relevant attributes | F01/F02/F22; K02 | open |
| AR09 | Роли, право раскрытия, владелец установки, recovery access | Простота настройки versus separation of duties | F02/F09/F15; K02/K06 | open |
| AR10 | Policy inheritance, defaults, приоритеты и исключения | Возможность случайного ослабления/предсказуемость effective policy | F03/F06; K04/K05 | accepted: общая политика + профили с явными overrides; детали propagation open |
| AR11 | Кто может ослаблять защиту и нужно ли two-person approval | UX публикации и модель ответственности | F02/F04/F06; T01/T03 | accepted: адресное ослабление, предупреждение, автор/основание/audit |
| AR12 | Возможности правил: маски/regex/словари/пороги/свои validators | Self-service сила, безопасность, качество и support burden | F05/F06/F19; K05 | open |
| AR13 | ПДн/секреты/КТ: действия и границы автоматической классификации | Reversibility, utility, false positives, пределы обещаний | F03/F07/F19/F22 | open |
| AR14 | Область стабильности подстановок и память агента | Изоляция session versus долговременная полезность | F08/F15/F23; K06 | accepted: conversation default, long-term opt-in |
| AR15 | Право восстановления и его привязка к получателю/операции | Интеграционная сложность и защита disclosure | F08/F10/F22; K06/K09 | open |
| AR16 | Output protection, buffering и streaming UX | Задержка/плавность versus контекст обязательной проверки | F10/F18; K09 | open |
| AR17 | Политики отказов, local fallback, audit/DLP availability | Fail-closed границы, остановка приложений, варианты degraded режима | F03/F11/F17/F21 | open |
| AR18 | TTL mappings, deletion, backup и long-lived tokens | Минимизация данных versus восстановление старых процессов | F08/F15; K06 | accepted: active refs + recovery-period autocleanup; durations open |
| AR19 | Что сохраняем для diagnostics/testsets/replay | Privacy footprint и полезность расследования | F09/F13/F14/F15 | open |
| AR20 | Песочница, обязательность регрессии, сравнение и shadow | Самостоятельность пользователя и условия безопасной публикации | F04/F13/F14; K08 | accepted: draft→automatic checks→explicit apply; suite детали open |
| AR21 | Аналитика качества, drift, incidents и отчёты | Что продукт действительно доказывает и насколько сложна админка | F09/F16/F20 | open |
| AR22 | DLP/SIEM/OIDC/adapters: глубина первой поставки | Ширина функциональности versus стоимость поддерживаемых integrations | F02/F17/F18 | open |
| AR23 | SDK/API compatibility и migration legacy consumers | Простота подключения versus trusted managed authority | F01/F08/F18/F21 | open |
| AR24 | Безопасность инструментов/RAG: где проверяем фактическое действие | Видимость предложенной команды versus execution enforcement | F22/F23; K09/K10 | open |
| AR25 | Coding v1: harness, OS, local/remote execution, способы подключения | Реальная аудитория первого выпуска и техническая реализуемость | F23; SP07; T12 | open |
| AR26 | Coding v1: Bash subset, arbitrary commands, файлы и patch | Полезность разработчику versus безопасные границы подстановки | F23; K10; AC01–AC09 | open |
| AR27 | Coding credentials/egress/подтверждения опасных действий | Секреты и право agent-generated программы воздействовать на окружение | F07/F22/F23; AC06/AC10 | open |
| AR28 | UI navigation, progressive disclosure, profiles и capability states | Понятность для разработчика и корпоративного оператора | F19/F20/F23; T10 | open |
| AR29 | Release slices, сокращение scope и критерий целостного выпуска | Что обязано быть готово вместе; что явно переносится | C0–C5; W27/W35 | open |
| AR30 | Performance budgets, dependency choices и режим фоновых jobs | Цена установки, latency, вычислительные ресурсы и скорость работ | F12/F13/F16/F21; SP01–SP06 | open |

| AR31 | Где обрабатываем original data и храним mapping: возле узла или общий сервис клиента | Data locality, межузловое восстановление, зависимость от связи | F08/F15/F21/F23; K01/K06/K10 | not applicable: отдельные processing nodes не выбраны |
| AR32 | Поведение узла при потере связи с клиентским управлением | Доступность versus скорость применения отзыва/новой политики | F04/F08/F21; K02/K03/K04 | not applicable: удалённый клиентский центр исключён |

## 4. Первый блок: AR01–AR03 — ответы получены

**Формат дальнейшего обсуждения:** по прямому требованию владельца варианты задаются через `ask_user_question`, а не длинным перечнем вопросов в финальном сообщении.

**AR01 — accepted:** владелец выбрал «Одна клиентская консоль для нескольких узлов». Центр управления локальный, внутри одного клиентского контура. Прежняя исходная рекомендация standalone ниже сохранена для истории; в форме вопроса рекомендован и выбран multi-node control.

**AR02 — accepted, в границе сказанного:** дословно: «Вообще консоль находится локально в контуре клиента, у каждого своя ни с кем не связанная». Каждый клиент имеет независимую консоль/контур, общую межклиентскую консоль и SaaS multi-tenant control plane не включаем. Это не означает автоматически air-gap, прекращение существующего licensing transport или запрет DLP/SIEM/разрешённых внешних моделей; эти вопросы отдельные. Physical topology stores/keys/nodes внутри клиента пока open.

**AR03 — accepted:** владелец выбрал «Готовая консоль Pseudex и полноценный API». Не делаем white-label или headless-first обязательным результатом спринта; UI-only возможности не допускаются.

**Причина выбора:** дополнительных мотивов владелец не сформулировал. **Инженерное следствие:** общий policy/node management уже часть текущего scope; старый single-host-only blueprint недостаточен. Multi-node management не равно HA-кластеру или распределённому общему vault.

**Affected:** F01/F02/F04/F08/F15/F20/F21/F23; K01/K02/K03/K04/K06/K09/K10; W02/W03/W04/W09/W12/W20/W21/W26/W27/W28–W35; CP04/CP07–CP09/CP21–CP22/CP31–CP33/CP44 и AC09/AC11.

**Синхронизация:** accepted topology constraints добавлены в основную spec/plan; R58 разделён на in-scope node management и пока не утверждённый HA. Детальный replacement state/rollout/backend design **pending AR04/AR05/AR31/AR32**, прежние single-host sections нельзя исполнять как окончательный multi-node контракт.

### История рассмотренных вариантов

### AR01 — что означает «единая точка» для первой поставки

**Вопрос:** каждой установкой управляют отдельно или уже в этом спринте требуется одна консоль, управляющая несколькими установками?

- **A. Самостоятельная установка:** внутри неё несколько apps/agents и одна UI; другая установка имеет другую UI. Экспорт policy облегчает перенос, но не называется central management. Близко к текущей поставке, меньше распределённой сложности.
- **B. Клиентский центр управления + несколько execution nodes:** общий policy rollout, identities, inventory и status; узлы располагаются около сервисов/рабочих мест. Требует distribution/trust/availability/version compatibility. Raw data не должны автоматически ехать в центр.
- **C. Два готовых режима:** standalone для малого клиента и distributed для платформы. Шире охват, но две топологии и их тестовые матрицы должны реально работать.

**Рекомендация для текущего объёма:** A с явными границами расширения; если без одной консоли на разные узлы продукт не отвечает ожиданиям владельца — B, с пересмотром single-node assumptions, а не декоративной кнопкой «узлы». **Статус:** superseded recommendation; выбор владельца AR01 — B, см. начало §4.

### AR02 — конечные клиенты интегратора

- **A. По отдельной установке на клиента:** процессы/stores/keys изолированы по deployment. Apps внутри клиента разделяются логически. Выше infra cost, проще доказать tenant boundary.
- **B. Общая multi-tenant установка:** процессы и инфраструктура общие, доступ/namespace/quotas логически раздельные. Экономнее для SaaS-интегратора, но требуется самостоятельная cross-tenant/noisy-neighbour/security приёмка.
- **C. Оба режима поставки:** feature contract поддерживает оба, каждый с явным topology manifest и tests. Не называть shared keys физической изоляцией.

**Прежняя рекомендация:** обсуждать вместе с AR01; универсального победителя нет. **Статус:** уточнено и принято свободным ответом AR02: каждый клиент со своей независимой локальной консолью; никакого выбора shared multi-tenant по умолчанию. Внутриклиентские project isolation/storage details остаются отдельными вопросами.

### AR03 — кто пользуется нашим управлением

- **A. Наша консоль для интегратора/техлида + полноценный API:** законченный самостоятельный интерфейс и automation; интегратор может позже построить свою оболочку.
- **B. Embedded/headless-first:** все customer journeys доступны через API для собственной админки интегратора; наша UI в основном диагностическая. Нужно явно определить делегирование customer-admin прав и поддержку встроенного UX.
- **C. Готовая white-label консоль для конечных клиентов плюс operator консоль интегратора:** branded embedding и role-aware tenant UX входят в первый scope, стоимость frontend/auth/support заметно выше.

**Рекомендация:** A, но без UI-only возможностей. Полный management API не равен обещанию готового white-label продукта. **Статус:** accepted A, см. ответ AR03 выше.

## 4bis. Уточнение владельца: standalone вместо узлов — действующее решение

**Этот блок заменяет multi-node интерпретацию AR01 в §4.** Владелец уточнил: «один инстанс = одна консоль», «должна остаться та же максимально быстрая установка», «масштабирование это оверинженерия … хочется единый удобный инстанс». Причина названа владельцем: лишняя сложность и ненужная сейчас инфраструктура.

- **AR01 — accepted, revised:** один standalone инстанс и его собственная локальная консоль. Предыдущий выбор общей консоли нескольких узлов — **superseded этим уточнением**, не сосуществует с ним как второй режим.
- **AR02 — accepted, unchanged:** у каждого клиента независимый локальный контур/консоль; общего управления клиентами нет.
- **AR03 — accepted, unchanged:** готовая консоль Pseudex + полноценный API.
- **AR04 — accepted:** сохраняем существующий быстрый способ запуска единого инстанса; не требуем Kubernetes/отдельного control center/регистрации удалённых узлов. Несколько внутренних процессов текущего контейнера — реализационная деталь, а не новая topology для пользователя.
- **AR05 — deferred вне текущего scope:** multi-node scaling, HA и fleet management не делаем в этом спринте. Это не запрет ресурсоограничений и существующих N workers одного инстанса.
- **AR31/AR32 — not applicable для текущей topology:** удалённые processing nodes и потеря связи с клиентским центром отсутствуют. Ошибки локальных процессов/stores и связи с licensing/DLP/LLM рассматриваются в своих вопросах, не переносят сюда distributed control model.

**Продуктовый принцип:** максимум настраиваемых сценариев внутри одного удобного инстанса, минимум обязательной инфраструктуры. Один инстанс может обслуживать несколько приложений/агентов через общие возможности; точные scopes/UX политики обсуждаем отдельно. «Любой трафик» пока aspiration: supported protocols/formats обязательно перечисляются, неподдержанное не объявляется проверенным.

**Coding:** локальный tool-execution adapter может технически требоваться для реального Bash/file boundary, но не означает fleet/control-center продукт. Где исполнять его относительно единственного инстанса, уточняется в AR25; нельзя из AR01 молча вывести регистрацию множества узлов.

**Синхронизация:** основной spec §3.1, plan current constraints и matrix R58 возвращены к standalone. Detailed distribution rewrite отменён; существующая local SQLCipher/N-worker схема остаётся proposed baseline. Выбор конкретных store/process internals не утверждён этим ответом автоматически. Engineering consequence: не добавлять distributed rollout/cluster discovery/network control protocol только ради масштаба.

## 4ter. Политики и публикация — AR10/AR11/AR20 приняты

- **AR10 — accepted:** «Общая политика + профили приложений». После установки безопасная общая политика; приложение наследует настройки и может иметь явные переопределения. UI показывает effective policy и источник каждого поля. Изменение общей политики и поведение уже существующих overrides уточняются дочерним вопросом при проектировании lifecycle; не предполагаем незаметное массовое ослабление.
- **AR11 — accepted:** «Разрешать явно и адресно, с предупреждением и аудитом». Уполномоченный администратор может разрешить конкретной категории/application/destination иной режим; показываются последствия, автор и основание. Не выбирались ни полный запрет ослаблений, ни свободный глобальный off. Это не разрешение raw fail-open при технической ошибке обязательной проверки.
- **AR20 — accepted:** «Черновик → автоматическая проверка → применить». Проверяются schema/technical safety/conflicts/обязательные контрольные примеры, администратор подтверждает diff, rollback доступен. Обязательный второй человек не является обычным путём; не добавляем его как скрытый default. Условия опционального enterprise approval могут обсуждаться позже.

**Основание:** ответы владельца через ask_user_question; дополнительных мотивов не названо. **Инженерное следствие:** effective policy компилируется из base+explicit authorised overrides **до** evaluation; адресное ослабление — изменение утверждённой конфигурации, а не caller allow, отменяющий runtime deny. Конфликты mandatory obligations в уже собранной policy по-прежнему fail-closed. Override нельзя прятать в per-request field или global environment.

**Affected:** F02/F03/F04/F06/F13/F14/F19/F20, K02/K04/K05/K08, W05/W07/W11–W13/W19/W26, CP10/CP14/CP20–CP23/CP38/CP42. Spec principle и plan acceptance обновлены; конкретные override merge fields/ownership, propagation preview и обязательные suites ещё требуют дочерних решений/контрактов. Не считаем все численные TTL и лимиты утверждёнными.

## 4quater. Подстановки и хранение — AR14/AR18 приняты; секреты уточняются

- **AR14 — accepted:** «Внутри диалога; долговременный режим включается отдельно». Default scope — conversation; shared identity across sessions/apps не включается автоматически. Долговременная память требует отдельного explicit profile setting.
- **AR18 — accepted:** «Автоочистка с учётом активной работы и периода восстановления». Lifetime учитывает активные разрешённые операции/refs и настраиваемый период после неактивности; длительная память отдельный режим. Численные idle/absolute/recovery TTL этим ответом **не утверждены**. Журналы имеют отдельный retention contract.
- **AR13-secrets — clarification_pending:** владелец предварительно выбрал рекомендуемую блокировку, но спросил, означает ли она обратимую подмену либо плейсхолдер. До подтверждения после объяснения не считаем конкретную secret action принятой. Разъяснение: block не отправляет конкретный запрос модели; redact удаляет секрет/заменяет marker без mapping; pseudonymize создаёт reversible mapping. Credential injection для approved executor отдельный механизм, не secret unmask в arbitrary Bash.

**Основание:** ответы ask_user_question. **Affected:** F07/F08/F15/F23, K05/K06/K10, W08/W09/W20/W29/W33; CP15–CP17/CP31–CP33, AC09/AC10. Spec principles обновлены; точные durations/limits и semantics session close будут согласованы отдельно.

## 4quinquies. Secret default подтверждён; HITL включается в спринт

**AR13-secrets — accepted, clarification resolved:** владелец подтвердил рекомендуемый вариант после объяснения: настоящий SECRET блокирует конкретный model request; необратимое скрытие+продолжение разрешается адресной настройкой приложения. Block не означает псевдонимизацию или marker. Общий default ПДн — reversible protection в пределах принятой политики. Exact known placeholder не автоматически настоящий secret.

**AR28-HITL (уточняет область AR11/AR24 и матрицу R28) — accepted scope, semantics pending:** владелец добавил «hitl интерфейс для подтверждения заблокированных подобных операций … ручное разрешение». Human approval переносится из P2 в текущий sprint. Это runtime approval остановленной операции, не обязательный второй человек при обычной публикации policy.

**Пока НЕ выбрано:** можно ли одобрять отправку raw SECRET/PII или только безопасно преобразованную операцию; какие policy denies reviewable; где оператор подтверждает; как caller продолжает выполнение. Approval не делает parser/decode errors, отсутствие обязательного сканера или неисправность vault безопасными. Для такого обхода никаких автоматических решений не принимаем.

**Требуется после уточнения:** pending operation lifecycle, original/sanitized payload binding, reviewer identity и grants, expiry, compare current policy, one-use resume permit, отсутствие raw secrets в queue/audit, UI/API notifications, cancellation/restart и правильные billing semantics. Affected F02/F03/F07/F08/F09/F18/F20/F22/F23, K02/K04/K06/K07/K08/K09/K10, W09/W13/W16–W19/W21/W24/W26/W30/W33; новые acceptance atoms добавляются после выбора semantics. Прежние P2 annotations runtime approval в исходной spec подчинены этому scope change, не служат причиной пропустить HITL.

## 4sexies. HITL — ответы HITL01–HITL03 и новый credential-сценарий

- **HITL01 — accepted с дополнением:** default варианты безопасного преобразования. В настройках администратор может отдельно разрешить вариант «отправить оригинальный ключ модели», после чего он появляется у уполномоченного reviewer. Default off. Это осознанное исключение, не гарантия скрытия ключа; exact operation/destination binding, reason/explicit warning/audit без raw key обязательны. Точный scope настройки/права и storage ещё уточняются. Прежние blanket statements «raw SECRET никогда наружу» теперь относятся к default/обычной политике, а не отрицают explicitly enabled HITL exception.
- **HITL02 — accepted:** очередь в готовой консоли и единый decision API для интерфейса интегратора. Backend permissions одинаковы, UI не отдельный источник полномочий.
- **HITL03 — accepted:** сохранять pending state и продолжать именно эту операцию после подтверждения. HTTP не держится неопределённо; correlated pending ID и explicit expiry/cancel/resume. Способ хранения чувствительного payload пока не выбран; не объявляем raw persistence согласованной автоматически.
- **Credential substitution — owner_requested, semantics proposed:** владелец хочет режим, где модель видит псевдоним, а инструмент получает настоящий ключ. Рекомендация архитектора: отдельная scoped credential reference/substitute, restoration только approved tool/destination/field после live permission check. Не обычный PII mapping и не автоматический unmask arbitrary Bash. В UX один понятный вариант «скрыть от модели, передать инструменту». Конкретные ограничения и источники credentials — следующие вопросы.

**Affected:** F07/F08/F18/F20/F22/F23; K02/K04/K06/K08/K09/K10; W08/W09/W16–W19/W24/W26/W30/W33. Main spec/plan scope notes синхронизированы; полная HITL state machine/storage/task decomposition pending следующих решений. Backend implementation ещё не разрешена.

## 4septies. Pending storage принят; credential UX уточняется

**HITL04 — accepted:** кратковременно хранить ожидающий payload зашифрованным внутри Pseudex. Отдельные права, срок, очистка после завершения/истечения и исключение секретного payload из обычных logs/долговременных backups. Это **явно согласованное исключение** из прежнего запрета любой persistent SECRET copy: transient encrypted approval payload допустим, обычный reversible PII mapping для ключа не подразумевается. Конкретные сроки/что видит reviewer обсуждаются отдельно. Старые слова «секретов нет в queue» из первоначальных proposed constraints заменены этим решением.

**CRED01 — принцип поддержан, UX/контракт уточняется:** владелец за recommended protection, но не хочет вручную перечислять тулы и уточняет работу в Bash. Требование пользователя: дополнительные ограничения для credentials, не обязательный список инструментов/доменов для восстановления всех ПДн.

**Предложено, пока не принято отдельным ответом:** сервисное подключение/credential purpose вместо ручного tool inventory; поддержанные адаптеры автоматически используют registry scope. Пример: GitHub key для auth approved repo/operation, не для arbitrary destination или content публичного issue на том же host. Scope только домен недостаточен; credential prefix/LLM-derived destination не является доказательством доверия. Неизвестное использование вызывает HITL/deny, не automatic trust. Поддержанный Bash execution adapter — да, arbitrary scripts с blind restore — нет.

**Первичные основания, прочитанные в сессии:** [Anthropic sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing) описывает scoped proxy, прикрепляющий Git credential после проверки destination/branch; [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) — least privilege. Это обоснование ограничения доступа, не утверждение, что наш продукт должен копировать весь их runtime.

**Синхронизация:** main spec/plan HITL storage principle обновлён; детальная migration/storage schema и tests пока pending final approval contract. Exact secret lifecycle отдельный от PII mappings и audit.

## 4octies. Credential UX принят — CRED-UX01

**Статус: accepted.** Владелец выбрал «Да, подключение сервиса + HITL для нового использования».

**Контракт пользователя:** настраивается сервисное подключение и purpose credential, а не ручной список каждого tool. Поддержанные adapters, включая Bash, используют это подключение автоматически. Неизвестное использование требует понятного HITL; система может предложить правило, но не выдаёт доверие автоматически. Опция запомнить узкое разрешение требует права изменения policy и проходит принятый draft/check/apply, обычное разовое approval не создаёт permanent policy.

**Граница:** дополнительные credential-specific settings не применяются к обычной псевдонимизации NAME/PHONE и другим ПДн; общие app/recipient privacy policies остаются. Scope — purpose/recipient/operation/ресурс, не одно имя домена; approved host не разрешает публиковать ключ в body/content. Неподдержанный arbitrary shell context не становится безопасным от HITL: required parsing/execution protections остаются обязательными.

**Affected:** F07/F08/F11/F18/F20/F22/F23 и runtime HITL; K04/K06/K09/K10; W08/W09/W15–W19/W24/W26/W29–W34. Spec coding credential boundary и общий scope принцип обновляются без добавления отдельного distributed secret manager. Не выбраны ещё UI reviewer permissions, expiry/default wait time, полная scope policy grammar и gate-level decomposition HITL.

## 4nonies. Простота доступа и смысл HITL expiry — уточнение

**HITL06 — accepted:** безопасное превью pending request; оригиналы только по отдельному разрешению, просмотр журналируется. Право одобрить не равно автоматическому праву увидеть raw content.

**HITL05 — open:** владелец не утвердил подробные scoped roles/grants; просит не строить сложную авторизацию без запроса, рассматривает admin+users или equal access. Перечитан исходный S1 §9: IT admin без request content, security admin policy/content с audit, auditor read-only; critical changes не должны быть незаметно выполнены/скрыты IT admin. Рекомендация архитектора к обсуждению: 2 basic roles admin/user; admin runtime settings/publish/HITL, user safe logs/errors/stats/sandbox; raw reveal отдельное permission уже принято. Не выдавать это за полное соответствие разделению IT/IB/auditor. Прежняя 5-role/grant модель F02 remains proposed и не утверждена.

**HITL07 — clarification_pending:** срок ожидания не выбран. Объяснены фазы: до model dispatch ожидающий сохранённый request продолжает первый вызов; после model response сохранённый ответ может быть выдан без повторной генерации; перед tool action ждёт неисполненная операция. Expiry при выбранном delete contract отменяет ожидание, удаляет sensitive payload и оставляет safe terminal status; auto retry/auto approval не возникает. Для повторения нужен повторно предоставленный исходник и новое разрешение. UI/API должны показывать pending/expired/rejected/cancelled, но готовый frontend конечного приложения не появляется автоматически — SDK/host интеграция обязана отобразить статус.

**Пока нет решения:** конечный timeout versus ожидание до решения/отмены и default длительность. Не фиксируем 1h либо 24h от имени владельца. Retention mappings AR18 отдельно от approval payload.

## 4decies. Две роли с выдаваемыми правами; HITL не равен живому вызову

**AR09/HITL05 — accepted:** две базовые роли admin/user. Пользователь по default смотрит safe logs/errors/stats и работает в sandbox. Администратор может выдать пользователю права на любые необходимые настройки и на HITL через понятные разрешения; дополнительных обязательных именованных ролей/иерархии не создаём. Право раскрыть originals отдельно (HITL06); выдавать/отзывать полномочия может администратор, выданное обычное право не означает право повышать собственные полномочия. Пять ранее предложенных ролей F02 заменяются этой моделью; конкретная группировка checkbox прав ещё проектируется.

**HITL07 — accepted product direction, runtime semantics under clarification:** default карточка ожидает долго, не исчезает и не удаляется автоматически; автоистечение можно включить настройкой. Конкретные 1h/24h не приняты. Истечение технического HTTP/tool/hook timeout не удаляет HITL карточку и не является пользовательским rejection. SLA/review reminder, retention карточки, sensitive payload storage и execution timeout — разные параметры, не один TTL. Очередь ограничена ресурсами; переполнение явно отклоняет новые ожидания, не молча удаляет существующие.

**Повторная проверка S1:** §7 «Требуется согласование» = приостановить выполнение до решения уполномоченного работника/системы; конкретных 1h/24h, HTTP semantics и Claude Code resume протокола нет. §12 требует воспроизводимые сценарии и safe отказ mandatory check. Следовательно native harness mechanics нужно проверить, а не навязывать продукту распределённую workflow-платформу.

**Первичный технический источник:** [Claude Code hooks](https://code.claude.com/docs/en/hooks.md), раздел Timeouts: timed-out command/http/mcp_tool PreToolUse hook не блокирует вызов сам по себе, действие продолжает обычный permission flow; Agent SDK callback timeout, напротив, блокирует tool call. В актуальной таблице есть также permissionDecision defer, но его exact supported version/resume lifecycle ещё должен пройти SP07. Нельзя считать ожидание в HTTP hook fail-closed boundary. Прямое извлечение полного markdown альтернативным HTTP client получило server403; извлечённые web_fetch официальные timeout поля достаточны для указанного вывода, но не доказательство работающего adapter.

**Предложение архитектора, требует подтверждения UX:** пока caller имеет поддержанную настоящую pause/resume связь, approval продолжает согласованную операцию; если caller timed out/cancelled/closed, HITL карточка остаётся и показывает «исходный вызов больше не ожидает». Поздний approve **не исполняет tool в фоне**. Требуется explicit reattach/retry от клиента и новая проверка exact args/file snapshot/live permissions; changed context — новое согласование. Неизвестный результат side effect не retry автоматически. Это сужает прежнее безусловное обещание «всегда продолжим тот же запрос» до реально поддержанного integration contract.

**Affected:** F02/F03/F08/F14/F18/F20/F22/F23; K02/K06/K08/K09/K10; W09/W13/W16–W19/W24/W26/W28/W30/W31; новые HITL tests timeout-before-approval/late approval/caller gone/same-vs-changed retry/no background side effect/queue saturation. Raw payload по-прежнему encrypted и не входит в audit/long-term backups; operational capacity и deletion options будут явно заданы без тайного default часа.

## 4undecies. Ограничение scope: harness-specific connectors отложены

**HITL08 — исходные варианты не приняты. Новое прямое решение владельца:** «это перебор … ещё и коннекторы с конкретными харнесами я пока делать не готов … тонна … более приоритетного».

**Accepted:** не включать в текущую реализацию коннекторы к конкретным coding harness и их native pause/resume/timeout orchestration. Не продолжать исследование/проектирование Claude Code hooks ради текущего HITL без нового запроса. Это уменьшение scope, не требование обойти checks или выполнять timed-out команды.

**HITL остаётся ранее запрошенной возможностью:** наша очередь и generic approval API. Возможность конкретного caller продолжить операцию — его интеграционный контракт; не строим автоматически клиента для всех harness и не обещаем transparent resume. Последние proposed HITL08 схемы не считаются утверждёнными.

**Открытый вопрос:** отложить весь специализированный coding T12 или только его harness-specific часть, сохранив узкий generic execution API. Не считать прежнюю обязательную C5 coding приёмку по умолчанию действующей при deferred зависимости. F23/T12/W28–W35/AC/C5 отмечаются scope_under_revision до ответа владельца. Базовые F01–F22/T01–T11 не расширять из-за этого частного сценария.

## 4duodecies. Coding снова планируется; HITL08 требует первичных фактов

**SCOPE-coding-now — принято новое уточнение владельца:** «давай планировать сразу, делать потом по приоритету … это самое последнее будет». Отмена harness-specific coding scope из §4undecies **superseded**. Восстанавливаем планирование полного завершающего T12/SP07/W28–W35/C5; реализовывать сейчас не требуется.

**HITL08 — research_required, варианта владелец не выбрал:** «нам надо изучить как это работает в харнесах и исходя из функционала уже принимать решения а не гадать». Не считать предложенный fallback retry или resume-only утверждённым. Проводится отдельное исследование официальных Claude Code/Agent SDK и Codex interfaces и локального DSH; выводы docs/source отдельно от экспериментально проверенных свойств.

**Что сохраняется:** один инстанс/одна консоль; две роли + выдаваемые права; safe previews; очередь по default не исчезает автоматически; временный payload encrypted внутри Pseudex; raw-key exception opt-in; сервисные credential scopes, не ручной список tools. Новые сроки ожидания/разрешений и native resume mechanics не назначаются до доказательств и ответа владельца.

## 4terdecies. HITL08: исследование завершено, выбор ещё не сделан

Подготовлено [primary-source исследование Claude Code/Codex/DSH](<research/harness-hitl-lifecycle.md>). Результат — documentary/source evidence, не runtime acceptance. Coding T12 восстановлен последним, Jev по-прежнему отменён.

**Факты для последующего решения:** Claude Agent SDK `canUseTool` может ждать indefinitely в живом процессе; отдельно существует documented defer/persisted resume. Native CLI hooks и SDK hooks имеют разные timeout semantics; не все tool calls идут в approval callback. Codex app-server pinned source сохраняет ordinary pending callback при disconnect и replay на warm resume, но не после process restart; approval reply и argument rewrite разные interfaces. DSH installed source сохраняет pending при browser reconnect, но resume после restart закрывает interrupted tool calls; native pre-gate input rewrite отсутствует. Поэтому прежняя постановка «таймаут любой системы требует нового запроса» слишком общая, а «бесконечно держим HTTP» не универсальный механизм.

**Не выбираем за владельца:** первый harness/mode, требование cold restart same-call resume, fallback при утрате waiter, native frontend ownership и exact operation content lifecycle. Эти вопросы теперь задаются через ask_user_question с конкретной подтверждённой integration surface, а не через общий абстрактный TTL. После выбора W28/SP07 доказывает поведение на actual pinned release.

## 4quaterdecies. Приоритеты — PRIORITY01/PRIORITY02 приняты

**PRIORITY01 — accepted:** первая полностью работающая пользовательская контрольная точка — «Настроить защиту самостоятельно»: профили приложений, собственные правила/исключения, реальная песочница, автоматическая проверка изменений, применение и rollback. Несущие safety ядра, identity/audit/cache/transaction contracts и их tests предшествуют зависимым кнопкам. Это приоритет разработки, не одобрение публичного выпуска неполного продукта.

**PRIORITY02 — accepted:** SSO/DLP/SIEM после рабочего ядра и основных пользовательских сценариев. Extension contracts закладываются заранее, но реализация корпоративных adapters не задерживает policies/rules/sandbox/basic HITL. Local named users/rights/internal audit нужны до mutating UI, их не откладываем вместе с enterprise integrations.

**Сохраняется:** coding/harness T12 последним; core test-first и независимые tracks могут работать параллельно по prerequisites. Не приписывать этому ответу утверждение точной очередности всех остальных F/W либо сроков/ресурсов команды.

**Affected:** приоритет внутренних milestones W01–W13 + соответствующая UI W26 выше complete W21/W22; W17 generic integration и basic HITL требуют отдельной scope/contract синхронизации. Общий dependency graph технических prerequisites сохраняется. Implementation order будет очищен от прежних proposal противоречий после завершения методологического согласования.

**Следующие решения:** AR12 authoring custom rules; AR10.1 propagation общей policy; затем supported routes/protocol/output и retention. Полное исследование hooks не означает автоматическое принятие конкретной coding integration.

## 4quindecies. Создание правил и выбор адресатов публикации

**AR12 — accepted:** «Понятный конструктор + расширенный режим». Основной UX: шаблоны, примеры/негативы, exact lists/context cues и тестирование; advanced безопасные ограниченные regex для технического пользователя. Произвольный исполняемый код не включён. Предложенный RE2/native package остаётся инженерным кандидатом до spike, не выбором владельца конкретной библиотеки.

**AR10-propagation — accepted intent:** владелец предложил применение новой политики к конкретным приложениям либо всем через явную кнопку «применить во всех». Не выбираем автоматическое каскадное обновление всех consumers от редактирования base. Сохранение draft/revision отдельно от activation; оператор выбирает target set и подтверждает impact. Не выбранные consumers сохраняют прежнюю assigned revision. Индивидуальные overrides сохраняются и видны в effective-policy diff. Atomicity batch activation/partial failure требует отдельного технического контракта; не выводим из кнопки гарантию всех процессов без отказов.

**AR03/AR10 UX clarification_pending:** термин «приложение» непонятен владельцу, он понимает разделение по агентам. Объяснение: плоская именованная logical integration/consumer одного инстанса, а не отдельный deployed app/node. Examples: support agent, document agent, internal AI chat, coding harness. Model/provider URL = destination, не эта consumer identity. Предлагаемый label «Агенты и сервисы» или «Подключения» выбирается далее. Не утверждены дополнительные обязательные уровни project/environment/group.

**Affected:** F01/F03/F04/F05/F06/F19/F20; K02/K04/K05; W03/W05/W07/W12/W13/W23/W26; CP04/CP07/CP10/CP21–CP23/CP38. Spec activation принцип и constructor status обновлены; raw caller agent label всё ещё не auth authority.

## 4sedecies. UX: «Агенты и сервисы» принято

**UX-consumer-name — accepted:** владелец выбрал название «Агенты и сервисы» и подтвердил, что целую корпоративную AI-платформу можно подключить как отдельный сервис с политикой.

**Действующая модель:** один инстанс, плоский список именованных consumers. Карточка может представлять одного агента, обработчик, внутренний чат, coding harness или всю внешнюю AI-платформу. У карточки assignment политики, настройки/идентификация, статистика и события. Не требовать UI-иерархию org→project→app→agent. Внутренние namespace/project IDs могут остаться инженерным механизмом изоляции, но не обязательным onboarding шагом.

**Граница:** Pseudex не узнаёт автоматически внутреннюю структуру чужой платформы. Если нужно выделять её агентов, trusted integration должна передать проверяемую identity/метку в рамках service permissions; это optional extension, не условие подключения. Адрес/модель получателя отдельны от карточки вызывающего сервиса. Service-level state не означает отдельный контейнер.

**Affected:** F01/F03/F04/F09/F16/F18/F20/F23; W03/W05/W13/W17/W25/W26/W34. В UI labels используем «Агенты и сервисы», API может сохранять technical application_id без пользовательской путаницы. Основная политика назначается единице настройки, в том числе всей корпоративной платформе.

## 4septendecies. Pseudex не LiteLLM — ROUTE01/02 уточнение принято

**Ответ владельца:** security proxy/sidecar, model routing не наша роль; защищаем OpenAI/Anthropic API traffic к указанному URL. Хотим простой native onboarding вместо путающей ручной env/base_url схемы. Не выбирать модель, не строить fallback/load balancing/cost router. Прежний recommended model registry+fallback не принят и отменён как core feature.

**Accepted:** сохраняем обе формы security интеграции: model-protocol reverse proxy с фиксированным upstream binding и sidecar callback где upstream вызывает host. Один инстанс может иметь несколько configured API bindings. Forward к этому upstream не равно выбору модели; model field/правила provider сохраняются в рамках поддержанного протокола. Security destination constraints остаются защитой, не автоматическим перенаправлением.

**UX proposal, pending:** добавить через админку/API исходный API base URL, protocol и policy, получить готовый защищённый base URL/snippet; не требовать изменения startup env на каждый новый connection. Как привязать downstream identity и upstream credential, ещё обсуждается. Не обещать «только заменил URL» и trusted user identity без дополнительного основания аутентификации.

**Что проверено в текущем коде:** tenants поддерживает несколько credential→upstream records; простой PSEUDEX_UPSTREAM passthrough имеет один env URL, dev seeding использует другой env pair. Существующая managed integration меняет base_url и api_key на Pseudex key. Поэтому multiple providers принципиально уже представлены, а unified удобный UI/onboarding — новая задача, не изобретение routing engine.

**Affected:** F11 и ссылки F03/F10/F12/F17/F18/F22/F23; W15 и route-related tests CP25/CP36; R51/R52. F11 переписан под fixed API binding. При консолидации удалить старые fallback clauses/readiness/catalog модели, сохраняя credential egress и no-bypass gates. Automated retries модельного запроса/side effects — ответственность caller, не наша собственная orchestration.

## 4duodevicies. Подключение API — CONNECT01/CONNECT02 приняты

**CONNECT01 — accepted:** мастер в локальной админке и эквивалентный management API. Агент/сервис получает fixed upstream binding (исходный URL, поддержанный protocol, policy) и готовые client parameters/snippet. Никакой правки startup env на каждый connection. Pseudex не выбирает/балансирует модели и не делает provider fallback.

**CONNECT02 — accepted:** исходный provider/API credential хранится в Pseudex внутри контура клиента (encrypted store/approved secret reference). Приложение получает отдельный Pseudex key и меняет base_url + api_key. Key binding разрешает caller service и его approved upstream; revoke ключа Pseudex не требует provider key rotation. Provider credential только transport auth исходного API, не LLM prompt. Display одноразовый/secret-safe, никаких keys в logs/export/snippets после выдачи.

**Следствие для UX:** protected base URL не обязан быть отдельным path на каждый service — технически binding может выбираться Pseudex credential, как у existing managed proxy. Конкретный URL shape/Anthropic header adaptation — инженерный contract, не добавление model routing. Один caller может иметь несколько явно созданных connections; ключ не даёт право передать произвольный URL в теле.

**Affected:** F01/F02/F11/F18/F20; W03/W13/W15/W17/W26; CP04/CP06/CP25/CP36/CP42. F11 onboarding и credential mode теперь approved. Прозрачный provider-key passthrough не выбран новым default и не расширяется как второй новый режим; legacy compatibility рассматривается отдельно без обхода managed auth.

## 4undevicies. Диагностическое хранение принято; streaming уточняется

**AR19 — accepted:** «Нет; безопасный журнал, исходники — отдельный режим диагностики». Обычный трафик не архивируем целиком по default; сохраняем safe decision metadata/categories/versions/metrics. Sensitive diagnostic capture только explicit для выбранного агента/сервиса, encrypted, scoped access, configured retention. Это отдельно от vault mappings и ранее согласованной HITL pending queue. Не обещать replay всей прошлой истории без сохранённых исходников.

**AR16 — clarification_pending:** владелец не понял формулировку и попросил кратко объяснить и повторить вопрос через tool. Вариант streaming/buffering ещё не выбран.

**Affected:** F09/F13/F14/F15/F16/F20, W10/W18–W20/W25/W26, CP18–CP20/CP30–CP33/CP41. Principle aligns с исходным proposed default capture off; срок и конкретный состав diagnostics пока отдельные engineering/owner решения.

## 4vicies. Streaming — AR16 принято после уточнения

**AR16 — accepted:** «Ждём полный ответ, проверяем, затем показываем». Это действует, когда хотя бы одна включённая обязательная проверка требует полного ответа. В остальных supported случаях streaming сохраняется. UI заранее показывает влияние на потоковую выдачу; не отключаем выбранную проверку молча ради streaming. Universal always-buffer не выбран.

**Engineering consequences:** capability negotiation по фактическим checks, buffered limits/timeouts/errors, no unchecked prefix/tail, structured tool arguments contract. Конкретные guards, которые доказанно могут incremental execution, определяются testing, не пользовательским желанием «сделать быстрее». Это утверждение UX policy, не свидетельство готовой проверки.

**Affected:** F10/F18/F20, K09, W16/W17/W26, CP26/CP27/CP47. Main spec mode wording синхронизирован. AR19 safe journal/capture opt-in также отмечен как accepted default.

## 4unvicies. Массовое применение и наблюдение — приняты

**POLICY-batch-apply — accepted custom:** предварительная проверка показывает список incompatible/failed agents/services и причины, с быстрым deep-link в trace/tests/effective-policy разбор. Затем оператор выбирает: (1) явно применить ко всем остальным прошедшим проверку либо (2) не применять никому. Автоматического partial success без выбора нет; silent rollback чужих successful изменений не подразумевается. Selected eligible subset фиксируется в confirmation/digest; перед actual commit повторно проверить неизменность revisions/permissions, иначе свежий preview. Техническое поведение при worker/store failure после подтверждения определяется existing activation contract и отдельными gates, не обещанием UI.

**RULE-observe-mode — accepted:** optional наблюдение нового правила на живом трафике до enforcement. Active policy продолжает защищать; shadow не меняет output и production mapping, полный исходник не сохраняется по default. Оператор отдельно активирует после проверки результатов. Shadow timeout/неполный sample показывается как not_evaluated/недостаточно данных, не отсутствие срабатываний. Обязательный период наблюдения для каждого правила не выбран.

**Affected:** F04/F05/F13/F14/F20, K04/K05/K08, W11–W13/W19/W26; CP20–CP23/CP30/CP42. В UI обязательно различать preflight failed/eligible/selected и applied/runtime failed. Spec принципы обновлены; применение к исключённым consumers не допускается.

## 4duovicies. Документы в основном спринте, semantic R&D параллельно

**SCOPE-files — accepted direction:** владелец: «давай добавим документы в спринт, это супер востребованно». Защита документов переносится из P2 в основной scope. В предложенном первом объёме речь о DOCX и PDF с text layer; exact formats, mixed scanned pages/OCR и сохранение layout не считаются автоматически утверждёнными словом «документы». Следующий вопрос — результат для модели/скачивания, затем protocol compatibility research и safe parser plan.

**SCOPE-semantic — accepted conditional research:** владелец выбрал параллельный неосновной исследовательский трек. Сначала готовый малый classifier, допустимо оценить дообучение; если внедрение оказывается чрезмерно сложным либо качество/ресурсы неудовлетворительны — переносим. Это не обязательная shipped semantic capability и не блокер основного sprint. Dataset/training privacy/licence/runtime sizing/метрики и условие принятия исследуются отдельно; разрешение планировать fine-tuning не разрешает paid compute/API или внешнюю выгрузку данных автоматически. Jev по-прежнему исключён.

**Scope change:** R22 document parsing больше не полностью P2; R17/R23 собственные classifiers имеют in-sprint research milestone, production acceptance условно после отдельного evidence/owner review. Не отмечать research interface как готовую detection feature. Current F/W/CP/AC baseline сохранён; новый document work/gate decomposition надо добавить после UX/format contracts и до запуска реализации. Coding остаётся самым поздним production треком, semantic R&D не входит в его критический путь.

**Affected:** F03/F05/F07/F10/F13/F17/F20/F22/F23; envelope supported types, parser sandbox, file metadata/source maps, provider file APIs, upload/storage/retention, actual wire no-leak gates. Наличие CSV/JSONL batch sandbox не выполнение защиты DOCX/PDF.

## 4tervicies. Документный результат и отмена semantic R&D

**DOC01-output — accepted:** владелец выбрал «Именно файл с сохранением структуры и оформления». Требуем native защищённый PDF/DOCX, а не только extracted text. Extraction-only первая поставка не удовлетворяет выбору. Архитектура требует format-aware rewrite/rebuild, mapping/provenance и независимой проверки итогового файла на сохраняющиеся originals; визуальная чёрная плашка не удаление underlying text/image/metadata. Exact допустимая fidelity и OCR scope уточняются отдельно, не обещать байт-идентичную layout при любых заменах.

**SEM01-first-target — rejected current research:** владелец: «передумал … уберём пока что». Полностью снимаем выбранный в §4duovicies parallel semantic-small-classifier R&D с текущего спринта. Не проводить selection/fine-tuning/benchmark этого трека без нового запроса. Будущие semantic classifiers могут остаться P2/backlog; это не отмена встроенной NER/существующих детекторов, пользовательских правил или уже согласованных external DLP interfaces. Jev остаётся отменённым.

**Affected:** R17/R23 возвращаются к прежнему production-limited scope/P2 без in-sprint research. R22 и document workstream расширены owner output contract: native protected file. Следующие вопросы DOC02 форматы/сканы, DOC03 preservation fallback. Любые схемы передачи файла provider API должны проходить source-backed compatibility research, не предполагаются по аналогии с text messages.

## 4quatervicies. Документы без OCR и best-effort layout — принято

**DOC02-formats — accepted:** DOCX и PDF с доступным текстовым содержимым; OCR не делаем в этом спринте. Владелец явно исключил OCR из-за сложности и уже большого объёма. Не включать распознавание сканов/изображений как скрытую зависимость document protection. Raw PDF/DOCX parser и native protected-file output остаются обязательными, это не CSV/JSONL/text extraction-only.

**DOC03-layout — accepted:** сохраняем структуру/стили/таблицы и оформление максимально; допустимы локальные изменения переносов/размеров из-за подстановки, их показываем. Существенное повреждение output — ошибка, оригиналы не оставляются ради fidelity. Pixel-perfect для произвольного файла не обещаем.

**Открытая граница DOC04:** поведение, если supported document содержит raster image, scan либо embedded объект, который не анализируется text-only pipeline. Нельзя автоматически считать его безопасным; выбор между strict отказом выдачи всего файла и явным text-only coverage с сохранением непроверенных частей требует владельца. Обычное наличие картинки не означает, что OCR тайно входит в scope.

**Affected:** R22, document workstream, parser supported inventory/format rewrite/offset provenance/hidden text and metadata verification, UI coverage/fidelity report, artifact security gates. Main scope/defaults отмечены, финальный полный document implementation plan pending DOC04/protocol research.

## 4quinvicies. Непроверенные части документа — DOC04 принято

**DOC04-uninspected-parts — accepted:** по умолчанию не выдавать mixed документ как защищённый, если изображения/embedded objects не проверяются text-only pipeline. Объяснить непроверенные части; пользователь может удалить их либо отдельно разрешить частичную обработку по applicable policy. Silent preserve-and-green не разрешён. Если partial output явно разрешён, coverage ограничение сохраняется в UI/API/export receipt и такой файл не называется fully protected.

**Связь с DOC02/03:** OCR не добавляется; logo/scan нельзя автоматически различить как safe без оснований. Полностью поддержанный text document идёт автоматически; unsupported content выводит понятный failure/review, а не декоративное предупреждение после external egress. Автоматическая отправка partial document модели не следует из разрешения скачать его локально: destination policy всё ещё действует.

**Affected:** R21/R22, новый document workstream, protocol part inventory/hidden metadata/images/embedded objects gates, UI coverage, F03/F07/F10/F13/F20. После UX решений ещё нужны source-backed parser/library/provider-file compatibility проверки, бюджет размеров и новое work/gate разбиение при консолидации.

## 4sexvicies. Приоритет документов/HITL и первый coding harness

**PRIORITY-documents-hitl — accepted:** после первой законченной self-service защиты документы и HITL имеют равный приоритет и развиваются параллельными треками по готовности общих prerequisites. Не делать искусственную зависимость «HITL после документов» или наоборот. Их shared auth/policy/vault/jobs/audit изменения интегрируются владельцами соответствующих K, а formatter/parser и approval UI/runtime — disjoint scopes. Coding по-прежнему последний.

**CODING-first-harness — accepted:** Claude Code первым, Codex после законченного первого supported coding scenario. Это приоритет интеграций, не предположение, что native hooks или SDK автоматически дают нужную безопасность. Конкретный mode/версии/transport/resume определяются research + SP07 + последующим review. DSH изучен как источник фактов, но не выбран как третий обязательный production adapter.

**Affected:** новый document workstream и runtime HITL workstream в одном post-core readiness front; W28–W35/T12 primary Claude, дальнейший Codex adapter sequencing должен быть явно отражён при консолидации. Вопрос включения окончательной Codex parity в C5 следует разрешать по исходному agreed scope/дальнейшему milestone decision, не подменять «затем» словом «никогда».

## 4septvicies. Enterprise depth и offline приоритет — приняты

**ENTERPRISE01-depth — accepted:** стандартные проверенные интерфейсы, без заявления поддержки всех вендоров: OIDC, выбранные стандартные event transports/formats, документированный REST DLP contract; settings/test connection в UI. Несовместимые vendor-specific системы требуют отдельного adapter. Connector protocol tests не дают право назвать любой DLP/IdP автоматически совместимым.

**OFFLINE01-scope — accepted:** полноценная offline/air-gap поставка остаётся отдельным следующим объёмом. Текущий sprint не меняет механизм лицензирования ради offline, ограничения сети/lease честно показываются. Уже принятые коммерческие условия отдельного бессрочного design не пересматриваются. UI local/no-CDN и on-prem processing не выдаются за offline engine.

**Порядок:** core/test-first + self-service configuration first; documents/HITL равноприоритетно параллельно по prerequisites; enterprise integrations после основных сценариев; coding последним, Claude Code→Codex. Semantic R&D, Jev, HA/fleet/Kubernetes и full offline excluded/deferred согласно отдельным решениям. Точная очередь прочих независимых work packages выводится из dependency graph, не превращает эти приоритеты в глобальные барьеры.

**Affected:** F02/F17/F18/F21; W21/W22/W27; R53/R54/R59; CP34–CP37/CP44–CP45. Scope/task IDs документов/HITL и последующего Codex adapter требуют финальной консолидации после завершения обсуждения, а не молчаливого полного утверждения старого графа.

## 4duodetricies. Невосстановленные подстановки — RESTORE01 принято

**RESTORE01-unresolved — accepted:** если нельзя однозначно восстановить исходное значение, проблемный tool call не выполняется. Для обычного текста допустима явная нераскрытая подстановка + machine-readable incomplete restoration status и понятная UI/SDK диагностика. Не угадываем оригинал, не заменяем на похожое чужое значение, не выдаём residual-free за полную корректность. Останавливается проблемная операция, а не весь инстанс; решение судьбы других независимых calls требует safe envelope contract, не автоматической retry оркестрации.

**Affected:** F08/F10/F18/F20/F22/F23; K06/K09/K10, W09/W16/W17/W24/W26/W31; CP16/CP17/CP27/CP28/CP47, AC02/AC09.

**Новый открытый интеграционный вопрос CONNECT03:** простое base_url+api_key подключение против обязательной explicit conversation identity/receipt contract. Нельзя одновременно обещать zero-code drop-in для любого клиента и строгую cross-conversation isolation без identity. Обычный OpenAI envelope не всегда несёт conversation_id, existing derive-first-messages heuristic слабее trusted ID. Advanced capabilities должны показываться отдельно от baseline, не добавляться скрытой mandatory SDK зависимостью после выбора мастера.

## 4undetricies. Глубина интеграции — CONNECT03 принято

**CONNECT03-integration-depth — accepted:** простой запуск через base_url/Pseudex key + расширенная интеграция по необходимости. Baseline protection работает без mandatory SDK adaptation там, где поддержанный API это позволяет. Strict conversation binding, durable memory/continuation и HITL capabilities требуют explicit verified conversation identity/adapter, если native protocol не даёт её сам.

**Граница:** не обещать строгую cross-conversation isolation по эвристике первых сообщений; capability registry/UI показывает реально доступные гарантии для данного connection mode. Advanced policy, которой требуется отсутствующая identity/receipt/resume capability, должна отказать validation/processing с понятной причиной, а не silent downgrade. Baseline не означает raw fail-open и не разрешает shared legacy admin key читать managed данные. Это совместимо с AR14 default conversation intent: когда identity отсутствует, weaker basis явно видна, а строгий режим не имитируется.

**Affected:** F01/F03/F08/F11/F18/F20/F23, v2 versus compatibility adapters, W03/W05/W09/W13/W15/W17/W26/W31; CP04/CP07/CP16/CP23/CP28/CP42/CP47. Не превращать весь продукт в обязательную миграцию на новый agent SDK; native execution privacy отдельно проверяется SP07.

## 4tricies. Coding platforms — CODING01 принято

**CODING01-platforms — accepted:** Linux и macOS; Windows через отдельно проверенный WSL, без нативного PowerShell/Windows executor в текущем спринте. Это целевые execution environments для coding, не требование заменить компактный Docker инстанс Pseudex отдельной распределённой системой.

**Ограничение:** WSL не автоматически equivalent Linux для Windows-mounted files, paths и network; нужны отдельные fixtures/negative gates. Linux container tests не доказывают macOS host isolation. Выбранный результат включает независимую проверку этих environments на actual harness versions. Native Windows/PowerShell остаётся P2, не hidden scope.

**Приоритет сохраняется:** coding последний; Claude Code первым, Codex затем. SP07/W28 и AC01–AC12 расширяются на declared OS matrix; конкретные sandbox/process integration implementations выбираются по official/source facts и spike, не угадываются. Runtime tests ещё не запускались.

**Affected:** F23/K10/T12, W28–W35, SP07, AC01–AC12; main coding doc/plan scope обновлены. Первоначальная Linux-only baseline как единственный целевой substrate superseded.

## 4tricies-unum. Документы в main, треки от свежего main — принято

**WORKTREE01 — accepted:** владелец: «документы должны быть в main и от него будут идти worktree с параллельными треками». Для каждого implementation track свой worktree/ветка от fetched актуального `origin/main`; не от старой локальной ветки, резервной docs-ветки или незавершённой ветки соседа. Base SHA/contract revision фиксируются в задаче; prerequisites потребляются после merge либо как явно обозначенные test fixtures, не как скрытая смена основы.

**Исправление ошибки подготовки:** первоначальная техническая сверка документов была на старой рабочей копии `380e3e72` (engine version file 0.3.19), не на текущем remote main. Product choices владельца от этого не отменяются. Подготовительный worktree создан от `4cc929bcc09e4a27eb5226771060c74643c46f43`; docs commit `84f9ef32` перенесён cherry-pick без посторонних dirty changes. Актуальная [сверка baseline](<research/security-platform-current-main-baseline.md>) исправляет конкретные code claims; оставшиеся proposal sections не превращаются в approved implementation от одного переноса.

**Рабочий порядок:** документы публикуются в main документными коммитами; каждый трек читает ту же main revision и не заводит альтернативный canonical plan. Исходная dirty копия остаётся нетронутой. Временная ветка переноса не замена main. Перед фактическим implementation требуется консолидация pending document/HITL/work-package детализации и current-code baseline tests, а не применение старых строк плана наугад.

## 5. Шаблон записи после ответа

```text
Decision: ARxx
Status: accepted / deferred / rejected
Выбор владельца:
Основание ответа / условия:
Зачем выбран (высказанное владельцем):
Инженерные последствия (вывод архитектора):
Отвергнутые альтернативы и цена выбора:
Зависимые вопросы:
Affected F/K/T/W/CP/AC:
Синхронизация spec/plan/matrix: pending / done + sections
Verification spike: required / not required; что не доказано
Supersedes: ...
```

Действующий выбор topology — уточнение §4bis (один инстанс/одна консоль), не первоначальная multi-node запись. Последующие ответы записываются хронологически выше; последние явные уточнения заменяют ранние proposed/defaults. Текущий открытый вопрос: HITL pause/resume относительно timeout/закрытия вызывающего harness. Новые вопросы — только через ask_user_question, с самостоятельным объяснением.
