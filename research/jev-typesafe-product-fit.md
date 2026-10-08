# Jev / TypeSafe AI: открытость, размещение и пригодность для Pseudex

**Статус:** desk research по первичным источникам в этой сессии; модель/API не запускались, платные запросы и клиентские данные не отправлялись. Цены/версии — снимок доступной документации, не наше SLA. Документ не меняет обязательный scope спринта.

**Решение владельца после исследования: Jev отменён для текущего спринта.** Материал ниже сохранён как evidence archive; предложения optional evaluation/integration больше не являются планом работ. Не разрабатывать adapter, не запускать eval/procurement без нового прямого решения. См. [OWN-05](<docs/decisions-product-control-plane.md>).

## 1. Краткий ответ

**Подключить Jev технически можно через hosted API. Использовать его как подтверждённую open-source/self-hosted модель сейчас оснований нет:** в проверенных официальных материалах найдены SDK и публичные examples/evals, но не опубликованные веса Jev, licence на их распространение и инструкция локального inference. Это результат поиска, не доказательство невозможности отдельной enterprise-поставки по договору.

Для Pseudex рекомендован **необязательный typed evaluator / риск-сигнал**, выключенный по умолчанию, с отдельным разрешением передачи данных и собственной калибровкой. Не заменяет PII pipeline, exact restore, policy engine, Bash parser, permissions или sandbox. [Официальная System One документация](https://docs.typesafe.ai/concepts/system-one.md) прямо отделяет calibration на группах прогнозов от гарантии правильности конкретного решения.

## 2. Что подтверждено

| Вопрос | Проверенный ответ | Основание / степень доказательства |
|---|---|---|
| Что за модель? | State + typed questions; Choice, Score, Noul; не генерация кода/прозы | [Introduction](https://docs.typesafe.ai/introduction), [System One](https://docs.typesafe.ai/concepts/system-one.md): документация разработчика |
| Обучение | Разработчик описывает RLCD — reinforcement learning for calibrated decisions | [AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer.md): описание производителя, не независимое воспроизведение обучения |
| Parallel questions | Независимые вопросы оцениваются против одного state; возможны разные primitive types в одном запросе | [Introduction](https://docs.typesafe.ai/introduction), [API](https://docs.typesafe.ai/api.md); точную внутреннюю архитектуру weights мы не проверяли |
| Актуальная именованная модель | В models указана `jev-1.13.0`; `jev-latest`/`jev-preview` на момент чтения указывают на неё | [Models](https://docs.typesafe.ai/models). Security evaluation должен pin version, не latest |
| Стоимость | $0.042 за миллион input tokens, output tokens бесплатно | [Models](https://docs.typesafe.ai/models). Полная стоимость = state+questions, retries, routing overhead; не «бесплатные дополнительные вызовы» |
| Контекст | 64k суммарно state+all questions, при этом state+самый длинный вопрос ≤32k | [Models](https://docs.typesafe.ai/models). Нельзя считать это 64k для одного raw state |
| Ввод | Text/JSON/arrays; не images/audio/video | [Models](https://docs.typesafe.ai/models) |
| Язык | English primary/best; другие языки требуют собственной проверки | [Models](https://docs.typesafe.ai/models); RU качество для наших задач не измерено |
| Rate limits | Документация указывает 100k tokens/s и 80 requests/s, но подчёркивает динамическое изменение | [Models](https://docs.typesafe.ai/models); не рассчитывать production capacity как гарантированную |
| SDK open source? | Python SDK опубликован под MIT; это HTTP client | [SDK README](https://raw.githubusercontent.com/typesafe-ai/typesafe-sdk-python/main/README.md), [LICENSE](https://raw.githubusercontent.com/typesafe-ai/typesafe-sdk-python/main/LICENSE) |
| Model weights open? | В проверенной официальной документации/публичном GitHub не найдены weights/model card с self-host instructions и licence на веса | [Docs index](https://docs.typesafe.ai/llms.txt), [public repos](https://api.github.com/orgs/typesafe-ai/repos?per_page=100). Не переносить MIT SDK на права модели |
| Self-host / air-gap? | Публичный подтверждённый deployment path — hosted API; локальный/offline path не установлен | [API](https://docs.typesafe.ai/api.md), [Models](https://docs.typesafe.ai/models). Enterprise on-prem надо отдельно запросить у TypeSafe |
| Data handling | Models page заявляет no training on customer requests/responses; ZDR предлагается enterprise customers | [Models](https://docs.typesafe.ai/models), [Legal](https://docs.typesafe.ai/legal.md). No training ≠ no retention; ZDR ≠ данные остаются локально |
| Latency 70–500ms? | В прочитанных текстовых официальных API/models docs точный диапазон не подтверждён как гарантированный SLA | [LangChain article](https://www.langchain.com/blog/building-a-harness-with-jev) цитирует vendor speedups, но это не измерение нашего p95/p99. Не принимать цифры user summary за benchmark |

Официальная документация сама ссылается на `github.com/typesafe-ai`; это использовано для определения first-party organization. Поисковая выдача содержала похожие домены с Jev/TypeSafe в названии: они не приняты за vendor evidence.

[Лендинг](https://typesafe.ai/), [launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [DPA](https://typesafe.ai/legal/data-processing) и [MCA](https://typesafe.ai/legal/mca) открылись, но инструмент извлёк лишь заголовки. Поэтому подробные договорные права, география processing, retention periods и on-prem conditions **не объявлены проверенными**. Нужен доступ к полному договорному тексту/ответ vendor, прежде чем делать privacy/SLA обещания.

## 3. Главные ограничения для security-продукта

### 3.1 Adversarial state может изменить решение

[Официальные ограничения Jev 1.13](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md), reviewed 2026-10-02, прямо говорят: state не рассматривается как hostile по умолчанию; injected instructions, misleading framing и текст, убеждающий модель в собственной классификации, могут изменить ответ.

Там же названы: literal reading, numeric/date/counting errors, multi-hop indirection, degradation от irrelevant large state, зависимость от порядка Choice options. Это особенно важно для Bash: оценка «безопасная команда» вероятностной моделью не доказательство эффекта программы.

При этом [guardrails cookbook](https://docs.typesafe.ai/cookbooks/llm_guardrails.md) демонстрирует удачную фильтрацию jailbreaks и эмоционально описывает устойчивость. Это 10 inputs + 5 outputs, результаты `jev-1.12` с cache, а не adversarial coverage guarantee. **Не разрешаем противоречие в пользу рекламного примера:** явно документированный failure mode новой версии и собственная проверка важнее удачного cookbook.

### 3.2 Confidence не равен вероятности безопасности

[Confidence docs](https://docs.typesafe.ai/confidence.md): Choice confidence вычисляется из распределения, для n вариантов `c=(p_max−1/n)/(1−1/n)`. Это не отдельный независимый сертификат правильности. Noul возвращает вероятность yes и не имеет отдельного confidence. Утверждение `safe=0.99` не означает, что leakage/unauthorized side-effect rate у нас ≤1%.

Нужны label corpus, class imbalance, selective error/reject rates, calibration curves/Brier/ECE, adversarial tests и confidence intervals на нашем домене. Порог из tutorial нельзя копировать как production authorization rule.

### 3.3 Внешний guard до локальной защиты уже получает данные

Опасная схема:

```text
raw prompt/код/секрет → Jev cloud → decide safe → наша защита
```

В ней передача произошла до решения. Поэтому Jev hosted не подходит обязательным preflight-классификатором сырых ПДн/кода/КТ в нашей local-first поставке. Он также не может служить `maybe_contains_pii` pre-filter: если модель ошиблась «нет ПДн», обязательный detector не должен быть пропущен.

Допустимая optional схема:

```text
локальные обязательные проверки + policy egress authorization
→ минимизированное, разрешённое к передаче state
→ optional Jev evaluation
→ typed result validation + domain calibration/uncertainty handling
→ локальная policy + permissions + exact plan validation
→ live consume → controlled executor
```

Замаскированный текст не автоматически безопасен для внешнего сервиса: могут остаться ПДн, КТ, архитектура кода и косвенные идентификаторы. Нужен отдельный разрешённый destination и data-purpose policy. State может быть синтетическим/публичным либо разрешённой структурированной сводкой (`operation_kind`, approved resource class, no credential/raw paths).

## 4. Где Jev может быть полезен

| Сценарий | Потенциал | Роль / ограничение |
|---|---|---|
| Triage событий и приоритет расследования | Хороший кандидат на тест | Optional asynchronous ranking безопасных events; не меняет права и mandatory enforcement |
| Классификация intent/risk в agent workflow | Возможен выигрыш против отдельного generative judge | Узкие вопросы, разрешённый state, monitor-first. Unknown/ошибка не allow |
| Routing между разрешёнными моделями | Кандидат внутри уже допустимого множества | Не может выбрать запрещённый external route или отменить local-only |
| RAG relevance / документная категория | Кандидат на разрешённых/public текстах | Не восстанавливает отсутствующие ACL; confidential content нельзя отправить для решения, можно ли его отправлять |
| Дополнительный риск-сигнал Bash/tool action | Экспериментальный | Может увеличить осторожность/deny; никогда не отменяет parser/permission/sandbox deny |
| Точная локализация всех PII spans | Не замена текущему ядру | Choice из заранее найденных candidates не находит кандидаты, которые не появились; offsets/bytes/round-trip — код |
| Custom type/threshold suggestion в UI | Поздний optional advisor | Только draft, no auto-activation, no raw training samples outside without approval |
| Основной privacy/security gate или standalone coding LLM | Не рекомендуем | Нет подтверждённого локального inference; documented adversarial weakness; не генерирует код |

[LangChain integration article](https://www.langchain.com/blog/building-a-harness-with-jev) подтверждает API-класс `TypeSafeClassifier` и примеры model-routing/tool-risk middleware. Это evidence применимости **интеграционного паттерна**, не доказательство безопасного выполнения shell.

## 5. Как подключать, если решим проверить

1. **Не делать Jev зависимостью F01–F23/T12.** Default engine и coding executor работают без TypeSafe API key, сети и этой модели.
2. Adapter через общий typed classifier interface F17/F22, fixed approved endpoint `https://api.typesafe.ai/v1/systemone`, не chat/completions. Client/keys только в контуре клиента, не в UI и не на нашей витрине.
3. Pin model `jev-1.13.0`, question/rubric/version и state-projection schema; логировать только safe IDs/results/timing/usage. Не использовать `jev-latest` для калиброванного production gate.
4. Schema-check result: ожидаемые question IDs/types/choices, finite probabilities в [0,1], compatible rubric; partial/malformed/429/529/timeout → `not_evaluated`/escalation according to policy, не implicit safe.
5. У SDK retries по умолчанию; задать общий deadline и retry budget нашего request, не ждать минуты при заявленной «быстрой» проверке. Async triage не в critical path.
6. Normalized command plan/execution permit остаются authoritative. Advisory не добавляет scopes, не разрешает unknown grammar, не хранит credentials и не отменяет mandatory check.
7. Начать с synthetic/public eval, RU+EN, shell false positives/false negatives, injected instructions, option permutation, state size, clean vs masked context. Отдельно замерять реальные p50/p95/p99, $/decision, timeouts/rate limits и полезность против rule-only baseline.
8. Только после результатов — opt-in customer integration с policy egress и согласованными data terms. Если появится vendor on-prem offer, проверить weights/runtime/container licence, hardware/latency, telemetry, offline keying/update и договорное право встраивания.

**Рекомендация:** оставить сменный интерфейс вероятностной оценки в архитектуре, а Jev оценивать как один backend, не как несущую технологию безопасности. Для local-only обязательных checks отдельно исследовать локальные модели с подтверждёнными весами/лицензиями; этот документ не утверждает наличие drop-in open-source аналога Jev.

## 6. OpenRouter и вопросы, оставшиеся открытыми

Поиск обнаружил [OpenRouter Jev 1.13](https://openrouter.ai/typesafe/jev-1.13/api), но текст страницы не раскрыл полноценный wire contract. Поэтому не делаем вывод, что достаточно заменить `model` в текущем OpenAI client и сохранить все typed semantics. Для исследования предпочтителен подтверждённый direct TypeSafe API. Router-посредник означает ещё одного участника обработки и отдельную privacy/destination policy.

Нужно отдельно подтвердить у TypeSafe: есть ли private/on-prem/VPC deployment, лицензия на встроенную поставку/перепродажу, data residency/retention/subprocessors, условия ZDR, pinned-version lifetime и SLA/rate stability, RU calibration и security evals. Публичного подтверждения этих коммерческих условий в прочитанном материале нет. Открытый SDK не отвечает на эти вопросы.

## 7. Итог решения для текущего планирования

- **AI-разработка добавляется в спринт независимо от Jev.**
- **Jev API технически пригоден для optional typed classification; его пригодность на наших данных ещё не измерена.**
- **Open-source Jev weights/self-host не подтверждены; подтверждён MIT Python SDK.**
- **Ни сырые чувствительные данные во внешний guard, ни разрешение Bash по одной вероятности не принимаются.**
- Исследование не создаёт paid API call, не устанавливает SDK, не изменяет конфигурацию production и не запускает методологический этап пользователя.
