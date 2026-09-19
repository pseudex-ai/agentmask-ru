# B2 — Как запускались, управлялись и росли РУССКОЯЗЫЧНЫЕ бенчмарки и датасеты

Дата: 2026-09-20. Оценки: **[A]** первичный документ прочитан · **[B]** утверждается в статье/карточке · **[C]** утверждение без проверки первички · **[D]** мой вывод.
Цифры GitHub/HF сняты через API 2026-09-20 (stars, downloads = за последние 30 дней у HF).

---

## 0. Главные находки в одну страницу

1. **MERA — единственный русский бенчмарк, у которого механизм внешнего вклада РЕАЛЬНО СРАБОТАЛ, и он сработал только после формального «call for datasets».** PR #13 «call for new tests» (2025-08-25) → за февраль–август 2026 задачи прислали ≥10 разных GitHub-аккаунтов (Alex-ast7 ×7, Fr0do, 077136, antoshkaxxr, danil31219as, king-menin2, marybal7, Alikata, mathamateur, tippered1-debug) → «MERA Text 2.0» 01.09.2026 с 12 новыми приватными тестами. [A] Ключ — не «open issues», а **письменные критерии приёма** (`docs/dataset_review.md`: ≥300 вопросов, baseline ≤ 0.8, источник синтетики обязателен, лицензия в метаданных, human baseline с overlap 5) и **пара README RU+EN**.
2. **В MERA Text 2.0 уже есть русский tool-calling тест — GorillaHard** (1169 вопросов, 14–22 инструмента в каталоге, «инструменты не исполняются — измеряется само решение»). Он приватный, без исполнения и без измерения ПД. [A] Это ближайший прецедент и одновременно свидетельство, что ниша «ПД × реальные вызовы инструментов» не занята.
3. **Русских бенчмарков ПД, кроме `hivetrace/pii-bench`, нет; агентных бенчмарков с ПД нет вообще.** Поиск по HF API («russian tool calling», «russian function calling», «russian agent benchmark», «ru agentic») даёт 0; русский запрос про «бенчмарк LLM-агентов … вызов инструментов» возвращает только BFCL/τ-bench. Единственная русская работа на стыке — Habr-статья Raft/HiveTrace (102 синтетических запроса, судья-модель), **без кода и без датасета**, с прямой оговоркой: «Персональные данные не используются приложением для дальнейшего реального решения задачи пользователя». [A]
4. **`pii-bench` — витрина того, как НЕ растёт датасет без сообщества:** 45 коммитов, все от двух авторов; 1 обсуждение (бот parquet); 0 внешних PR; 10 лайков; 385 скачиваний/мес. Дефект чек-сумм (88 из 92 карт не проходили Луна — наше измерение) авторы починили сами коммитом «resolve checksums» **2026-08-25, через 7 месяцев после релиза**. [A]
5. **Что убило Russian SuperGLUE — не конкурент, а смена парадигмы**, названная авторами прямо: «надобность в бенчмарках типа Russian SuperGLUE, которые предоставляли тренировочные сеты для файнтюнов моделей, медленно изживает себя». Сайт не закрыт, лидерборд (44 сабмита) просто остановился; GitHub без пушей с 06.2023. [A]
6. **Юридически синтетика вне 152-ФЗ по определению** (ст. 3: ПДн — информация о «прямо или косвенно определённом или определяемом физическом лице»), и русские публикаторы ограничиваются дисклеймером «полностью синтетические, совпадения случайны». Позиции РКН по синтетике **не найдено** (отсутствие — результат). Реальный риск не в законе, а в **коллизиях**: в РФ нет резервного «вымышленного» диапазона номеров вроде американского 555, и `+79261234567` из pii-bench — живой номер МТС-диапазона. [D]

---

## 1. По бенчмаркам — таблица (Q1)

| Бенчмарк / датасет | Кто управляет | Хостинг | Лицензия | Лидерборд / приватный тест | Путь вклада | Рост (даты, числа) | Что остановило / состояние | Оц. |
|---|---|---|---|---|---|---|---|---|
| **MERA** (Text/Industrial/Code/Multi/Reason, SWE-MERA) | Альянс в сфере ИИ (a-ai.ru); экспертный совет: «НИУ ВШЭ, РАН, Сколтех и наши партнеры из индустрии»; core — команда AGI NLP SberDevices | mera.a-ai.ru (свой сайт: личный кабинет, сабмит ZIP, автоскоринг) + GitHub `MERA-Evaluation/MERA` (52★, 10 forks, 7 контрибьюторов, ~39 PR, MIT) + HF org `MERA-evaluation` (54 датасета; `MERA` 3160 dl/мес, 11 лайков) | датасеты MIT; Multi: «tasks can only be used for testing models, not for training» | Ответы тестов только у организаторов; сабмит → скор в кабинете приватно → галочка «Publish» → модерация экспертами с проверкой логов воспроизводимости → публикация; анонимный сабмит допускается; на лидерборд — только полный набор задач + описание модели | «CALL FOR NEW DATASETS»: 4 шага (критерии → формат + загрузка на HF → интеграция в lm-eval-fork + прогон baseline → PR); вопросы — Issue, Telegram-форум t.me/+XkBIbHFg8s5iNGIy, mera@a-ai.ru | v1.0 11.2023 (21 задача) → v1.2.0 09.2024 → Industrial 06.2025, Code 07.2025, SWE-MERA 09.2025 (MWS AI+Sber+ITMO), Reason 07.2026, **Text 2.0 01.09.2026: 12 новых приватных тестов** (Human-Centric, Culture-Specific, Agentic, Reasoning) | Живой; активные пуши 2026-09-14 | [A] |
| **Russian SuperGLUE** (2020) | AGI NLP SberDevices + Noah's Ark Huawei + ФКН ВШЭ | russiansuperglue.com (свой сайт, сабмит через логин) + GitHub `RussianNLP/RussianSuperGLUE` (113★, MIT, последний push 2023-06-12) + HF `RussianNLP/russian_super_glue` (757 dl/мес) | MIT (код); данные на сайте | Приватные тестовые ответы, 9 задач, human baseline 0.811; 44 записи; внешние сабмиттеры: Saiga team, RCC MSU, «Avengers Ensemble», Yandex | Не формализован; задачи делала команда | EMNLP 2020; RSG 1.1 (2022) | Устарел: «предыдущие стандарты … медленно, но верно устаревают»; уведомления о закрытии на сайте нет — просто замер | [A] |
| **TAPE** (few-shot, 2022) | RussianNLP (ВШЭ/Sber) | GitHub `RussianNLP/TAPE` 8★, 0 forks, push 2023-03 | Apache-2.0 | сайт tape-benchmark | — | — | Мёртв через год; поглощён MERA | [A-stat] |
| **RuCoLA** (2022) | RussianNLP (ВШЭ, Sber, Toloka) | rucola-benchmark.com + GitHub 50★ + HF `RussianNLP/rucola` | Apache-2.0 | публичный лидерборд | — | ACL 2022 | Push 2024-10; поддерживается вяло | [A-stat] |
| **RuBLiMP** (2024) | RussianNLP | GitHub 20★ (push 2026-02) + HF `RussianNLP/rublimp` 673 dl/мес, 4 лайка | Apache-2.0 | без лидерборда (minimal pairs) | — | EMNLP 2024 | Академический артефакт | [A-stat] |
| **LIBRA** (long context ru, 2024) | ai-forever (SberDevices) | GitHub `ai-forever/LIBRA` 22★ + HF `ai-forever/LIBRA` 712 dl/мес | MIT | — | — | push 2026-06 | Живой, но нишевый | [A-stat] |
| **ruMTEB** (2024) | AGI NLP SberDevices (М. Тихонова, А. Феногенова, А. Снегирёв) | **едет на международной инфраструктуре MTEB**: PR в `embeddings-benchmark/mteb` («Update ruMTEB tasks list» 2024-08-15, «ruMTEB v1.1» 2025-11-27), лидерборд — HF Space MTEB, форк `ai-forever/mteb-leaderboard` | как MTEB (Apache-2.0) | публичный | PR в mteb | NAACL 2025; 23 задачи, 17 новых | Живой; поглотил `encodechka` (avidale): «рекомендуется использовать ruMTEB вместо Encodechka» | [A/B] |
| **NEREL / NEREL-BIO** (2021/2023) | МГУ (Н. Лукашевич) + Sber AI Lab / Казань (Е. Тутубалина) | GitHub `nerel-ds/NEREL` 38★, 4 forks, 23 коммита, последний 2023-11; HF-зеркало третьей стороны `iluvvatar/NEREL` (131 dl/мес, 9 лайков) | **лицензии нет ни в репо, ни в HF-карточке** (`license: None`) | нет; baselines в README | 1 внешний PR смержен (#1 `1ytic/fix-labels`, 02.2023) — единственный | RANLP 2021: 56K сущностей, 39K отношений; NEREL-BIO → shared task **BioNNE @ CLEF 2024 (BioASQ)** | Данные рабочие, репо замер; рост шёл через shared tasks (RuNNE-2022 на Dialogue, BioNNE-2024), не через PR | [A] |
| **hivetrace/pii-bench** (01.2026) | HiveTraceLab (ITMO AI Security Lab / Raft): Б. Минко, С. Садиех, Е. Кокуйкин | HF only (`hivetrace/pii-bench`); статья arXiv 2605.05277 (GLiNER Guard) | **Apache-2.0** | нет лидерборда; «PII-Bench is only informative as a held-out benchmark … This is a request, not a license restriction» | никакого (нет CONTRIBUTING; 1 обсуждение = бот) | 1810 примеров, 13 типов × 70, 9 доменов × 100; IAA 0.87; 385 dl/мес; 10 лайков; 45 коммитов двух авторов; **2026-08-25 «resolve checksums»** | Живой, но закрытый контур авторов | [A] |
| Прочие RU-PII на HF | `alrosait/pii-synthetic-ru` (06.2026, MIT, 76 dl), `wolframko/russian-pii-66k` (02.2026, без лицензии, схема ai4privacy), `alexen2/pii-ner-ru-benchmark` (04.2026, без лицензии, 62 dl) | HF | смешанно | нет | нет | — | Одиночные загрузки, без карточек | [A-stat] |
| **Golos** (Sber, 2021) / **open_stt** (snakers4) / **RuDevices** | SberDevices / А. Вейсов | GitHub `salute-developers/golos` 146★ (+ зеркало `sberdevices/golos` 220★), OpenSLR 114; open_stt 824★ архив 2022 | Golos — своя «public license with attribution and conditions reserved»; open_stt — NOASSERTION (cc-by-nc + коммерческая) | нет | нет | Interspeech 2021, 1240 ч | Одноразовые релизы корпораций | [A/B] |
| **natasha / corus / nerus** (А. Кукушкин) | один мейнтейнер + лаборатория | GitHub `natasha/corus` 315★, 22 forks, **4 контрибьютора, 9 PR, 69 открытых issue**, push 2026-04; `natasha/natasha` 1349★, 17 контрибьюторов; чат TG «Natural Language Processing» 6 667 участников (админы @dveselov, @alexkuk) | MIT | нет | «add source»: `corus/sources/<source>.py` + `meta.py` + `docs.ipynb` + тесты | 20+ датасетов, 350 ГБ+ (README); Habr 516098: +53, 198 закладок | Жив 7 лет как **реестр ссылок и загрузчиков**, а не хостинг данных — обслуживает собственный стек (naeval) | [A] |
| **IlyaGusev: rulm / Saiga / PingPong** | один человек | GitHub `rulm` 466★ (архив 08.2024), `ping_pong_bench` 122★ Apache-2.0 («Any contributions are welcomed!»); HF 27 датасетов (`gazeta` 2500 dl); TG «Старший Авгур» 8 145 подписчиков | Apache-2.0 | PingPong: LLM-судья + эмулятор пользователя, 40+ моделей RU/EN | PR | «Saiga ❤️ 500+ · ⬇️ 2M» | rulm заархивирован — автор перешёл на агентные проекты | [A] |
| **Vikhrmodels** (сообщество) | HF-org, 23 участника | HF Spaces: «Russian LLM Leaderboard — Submit your LLM», arena-hard ru, Small Shlepa, DOoM, Russian ASR Leaderboard; **датасеты `requests` (3267 dl) / `results` (1463 dl)** = шаблон Open-LLM-Leaderboard | — | публичные | сабмит через HF Space | 108 датасетов | Живой; **это и есть «HF Spaces путь» в РФ** | [A] |
| **LLM Arena (llmarena.ru)** | Роман Куцев (основатель) | свой сайт + HF org `LLMArena` (`ruarena-user-preference-7k`, `crowd-preference-4k`); GitHub 1★ | — | Elo/Bradley-Terry по голосам + оффлайн Arena Hard 500 промптов | добавление модели по договорённости | «каждый день сотни людей общаются с моделями» (Habr 920150) | Живой | [A/C] |
| **Dialogue Evaluation** (shared tasks конференции «Диалог») | оргкомитет; координатор devaluation@dialogue-conf.org | по задачам (GitHub/Codalab) | по задачам | публичные лидерборды соревнований | письмо координатору с предложением shared task | 2023: RuCoCo, RuSentNE, SEMarkup, RECEIPT-AVQA; 2025: CoBaLD, RuOpinionNE, RuTermEval; ранее RuNNE (NEREL) | Живой; академический рецензируемый трек (Scopus) | [A] |
| **ODS.ai** соревнования | сообщество, А. Натёкин | платформа ods.ai (хабы, треки) | — | — | «Соревнование соревнований — от сообщества для сообщества!» (2021–22): номинации Deploy/Educational/Insight, призовой фонд, голосование на ODS Awards | ODS: 50 000 участников (2020); Data Fest 2019: 6 000+; хабы 2026: NLP 842, ML & Security 52, Reliable ML 10 105 | Живой; Data Fest 2026 (AvitoTech, 30.05) | [A/B] |

---

## 2. Цитаты (verbatim) с источниками

### MERA — правила приёма задач (`docs/dataset_review.md`) [A]
> «Задачи в MERA делятся на приватные и публичные. … в приоритете закрытые тесты.»
> «На предлагаемой задаче должны быть проведены замеры нескольких baseline-моделей …; минимальная оценка среди них должна не превышать 0.8.»
> «Если для создания датасета использованы синтетические данные, обязательно должен быть указан их источник (в том числе генеративные модели).»
> «Минимальный объем датасета — 300 вопросов. … на каждую такую категорию нужно от 100 до 1000 вопросов.»
> «Все тестирования human baseline (HB) нужно делать с перекрытием (overlap) разметчиков = 5, на средне-статистических людях … краудсорс … (например, в Толоке, Яндекс.Заданиях, ABC Elementary или TagME).»
> «Задачу не должна решаться простым бейзлайном (в т.ч. обычной текстовой LLM / агентом / быстро вопроизводимым скриптом).»
— https://github.com/MERA-Evaluation/MERA/blob/main/docs/dataset_review.md

### MERA — README, call for datasets [A]
> «The tests needs to be HARD for the latest models! MERA TEXT targets primarily the Russian language tests.»
> «3. Submit a **Pull Request** with your dataset to this repository. We will review your submission and, upon approval, add it to New MERA TEXT.»
— https://github.com/MERA-Evaluation/MERA

### MERA — сайт «How MERA works» [A]
> «An uploaded model submission does not automatically become public. To request publication on the leaderboard, tick the “Publish” box. Then, MERA administrators (and part-time experts who are members of the benchmark expert council) will receive a notification to check the submission.»
> «Systems should not use unlabeled test data from MERA tasks to train models … **It's not good to learn from test data!**»
> «All MERA tasks are based on open resources. All datasets are published under the MIT license.»
— https://mera.a-ai.ru/en/multi/about

### MERA — статья ACL 2024 [B]
> «The evaluation result is then displayed in the user’s account and kept private unless they use the “Publish” function and request publication. In this case, it undergoes an expert verification of its reproducibility, which includes checking log files automatically formed by the evaluation script.»
— https://aclanthology.org/2024.acl-long.534.pdf

### MERA — Habr-анонс (alenusch, 22.11.2023, 10K просмотров, 9 комментариев) [A]
> «В состав экспертного совета бенчмарка входят представители академической сферы (НИУ ВШЭ, РАН, Сколтех, и тд.) и наши партнеры из индустрии»
> «надобность в бенчмарках типа Russian SuperGLUE, которые предоставляли тренировочные сеты для файнтюнов моделей, медленно изживает себя. Бенчмарки вслед за моделями требуют новых форматов.»
> «Ранее мы писали про коллаборативный проект Russian SuperGLUE нашей команды AGI NLP SberDevices, лаборатории Noah’s Ark Huawei и факультета компьютерных наук ВШЭ.»
> «Присоединяйтесь и вы к нам <3»
— https://habr.com/ru/companies/sberdevices/articles/775336

### GorillaHard — PR #46 в MERA (artemorloff, смержен 2026-08-11) [A]
> «Модель получает запрос, каталог из 14–22 инструментов и ноль-два приложенных файла, а вернуть должна одно решение в виде JSON-объекта: вызов инструмента, план из зависимых шагов, набор независимых вызовов, уточняющий вопрос или отказ. **Инструменты не исполняются — измеряется само решение**»
> «Сложность: 1169 вопросов, четыре тира — T1_medium 16, T2_hard 56, T3_expert 329, T4_wild 768. Сильнейшая из проверенных моделей (gpt-5.6-terra) берёт 0.466 по строкам»
— https://github.com/MERA-Evaluation/MERA/pull/46

### hivetrace/pii-bench — карточка [A]
> «Examples were generated with **Claude Sonnet 4.5** (Anthropic) using domain-specific seed prompts … Two native Russian-speaking annotators then independently annotated every example … Inter-annotator agreement is 0.87»
> «Eleven of the thirteen types are regex-resolvable. … Only `NAME` and `ADDRESS` genuinely require learned extraction.»
> «The license permits any use, but PII-Bench is only informative as a **held-out** benchmark. Please do not train or fine-tune on it … This is a request, not a license restriction.»
> «All examples are **fully synthetic**. No real user data was used. … Any resemblance to real people, companies, addresses, or phone numbers is coincidental.»
> «Every `INN`, `SNILS`, `OGRN`, `OGRNIP` and `BANK_CARD_NUMBER` in the benchmark satisfies its own check-digit algorithm» (текст появился после коммита `9b2c076 resolve checksums`, 2026-08-25)
> «A valid checksum does not by itself make a number synthetic: `INN` and `OGRN` are public ЕГРЮЛ data, so a memorised real registration number satisfies every arithmetic rule.»
— https://huggingface.co/datasets/hivetrace/pii-bench ; история: https://huggingface.co/datasets/hivetrace/pii-bench/commits/main

### Raft/HiveTrace — «Влияние очистки от ПД на работу LLM-агентов» (Habr, Evgenii_A, 23 марта; судья gpt-5.2 ⇒ 2026; 7.2K просмотров, 1 комментарий, +9) [A]
> «Отправили в него по 102 синтетических запроса в трёх вариациях входных данных (чистые, маска, псевдонимы)»
> «псевдонимизация не имеет значительного влияния на работу конечного агента. В то время как маскировка вызывает более заметную просадку.»
> «Персональные данные не используются приложением для дальнейшего реального решения задачи пользователя»
— https://habr.com/ru/companies/raft/articles/1013906/ (кода и датасета в статье нет)

### ODS — «Соревнование соревнований» [A]
> «ML соревнования — это отличный формат для того, чтобы делом продвигать Data Science и Machine Learning: … А ещё, в некоторых случаях соревнования являются опорными бенчмарками для крупных подобластей в ML.»
> «Следуя нотации MICCAI, мы будем награждать соревнования от сообщества в 3 номинациях: Deploy challenges … Educational challenges … [Insight]»
> «До 21 мая 2022 мы рассматриваем заявки. В течение 2022: мы запускаем соревнования, встраиваем их в курсы ODS, а участники пытаются решить ваши задачи! Декабрь 2022: идут голосования за лучшие соревнования в рамках ODS Awards»
— https://ods.ai/tasks/ods-competitions-2021

### Dialogue Evaluation [A]
> «Dialogue Evaluation is a special «Dialogue» section that combines shared tasks for various practical and research NLP problems for the Russian language.»
> цель — «develop uniform principles of 'evaluation' in order to objectively assess text analysis systems for different tasks and set technical benchmarks (SOTA-solutions)»
— https://dialogue-conf.org/evaluation/

### natasha / corus [A]
> «Links to publicly available Russian corpora + code for loading and parsing. 20+ datasets, 350Gb+ of text.» — https://github.com/natasha/corus
> «natural_language_processing — чат пользователей, разработчиков проекта.» — https://natasha.github.io
> «Русскоязычный чат про NLP: QA, новости, мероприятия, вакансии. … Админы @dveselov, @alexkuk.» (6 667 участников) — https://t.me/natural_language_processing

### encodechka → ruMTEB [A]
> «ruMTEB … русскоязычная часть MTEB. С недавнего времени там есть 23 разнообразных задачи … рекомендуется использовать ruMTEB вместо Encodechka.» — https://github.com/avidale/encodechka

### ruMTEB — Habr SberDevices [A]
> «Такой большой проект как новый бенчмарк ruMTEB — это всегда результат совместной работы большого количества людей и команд. … спасибо своему Тимлиду команды AGI NLP SberDevices @alenusch и коллегам … @Andriljo, @anpalmak, @artemsnegirev» — https://habr.com/ru/companies/sberdevices/articles/831150

---

## 3. Q2 — Куда русские практики РЕАЛЬНО сабмитят системы

| Канал | Кто и как | Оц. |
|---|---|---|
| **mera.a-ai.ru** — свой сайт с личным кабинетом | ZIP из форка lm-eval-harness → автоскоринг → «Publish» → модерация экспертов. Единственная площадка, где **все** русские модельные команды (Sber, Yandex, MTS, T-Bank и т.д.) обязаны появиться. | [A] |
| **HF Spaces (шаблон requests/results)** | Vikhrmodels «Russian LLM Leaderboard — Submit your LLM», arena-hard ru, Russian ASR Leaderboard; `Vikhrmodels/requests` 3267 dl/мес. Низовой канал, без модерации. | [A] |
| **HF MTEB leaderboard** | ruMTEB как таб MTEB; сабмит = PR результатов в `embeddings-benchmark/results`. | [A/B] |
| **russiansuperglue.com** | сабмит через логин; сейчас практически не пополняется (последние — Saiga/Qwen-адаптации). | [A] |
| **llmarena.ru** | арена по голосам; модели добавляют организаторы. | [A/C] |
| **Codalab / GitHub соревнования Dialogue Evaluation** | академические shared tasks (RuNNE-2022 на NEREL, RuSentNE-2023 и т.д.). | [C] |
| **ods.ai** | соревнования с призовым фондом; популяризация ниш («опорные бенчмарки для подобластей»). Kaggle для RU-задач больше не используется как основной. | [A/D] |

**Вывод [D]:** для «оценки шлюза» (не модели) ни одна площадка не подходит напрямую — MERA оценивает модель, HF-лидерборды тоже. Единственные прецеденты «оценка системы, а не модели» в РФ — shared tasks Dialogue и ODS-соревнования (участник сдаёт предсказания/сабмит). Значит, для харнесса «любой маскер» нужен свой GitHub-раннер + опубликованные результаты в HF-датасете `results` (шаблон Vikhr) — а задача-подмножество (без исполнения инструментов) может быть отдана в MERA как приватный тест.

---

## 4. Q3 — Есть ли русский бенчмарк ПД / агентов кроме pii-bench

**ПД-детекция:** единственный оформленный — `hivetrace/pii-bench`. Ещё три загрузки без карточек/лицензий (`alrosait/pii-synthetic-ru` MIT, `wolframko/russian-pii-66k` — схема ai4privacy дословно, `alexen2/pii-ner-ru-benchmark`). Модель `bbeglerov/opf-russian-pii-66k` (OpenAI Privacy Filter, дообученная) — не бенчмарк. Русские корпуса ПД с **настоящими** данными отсутствуют (см. также research/2026-08-31). [A]

**Агенты / tool-calling на русском:**
- **GorillaHard** внутри MERA Text 2.0 (09.2026) — приватный, «инструменты не исполняются», без ПД. [A]
- **SWE-MERA** (09.2025) — код, не tool-calling. [A]
- **PingPong** (IlyaGusev) — ролевая игра RU/EN, LLM-судья, не инструменты. [A]
- «BFCL-ru», «ru-tau-bench», «ruAgentBench» — **не найдены**.

**Проведённые поиски (для фиксации отсутствия):**
- HF API `datasets?search=`: «russian tool calling», «russian function calling», «russian agent benchmark», «ru agentic», «персональные данные», «anonymization russian» → 0 результатов; «pii ru» → 3 (выше).
- Tavily RU: «бенчмарк LLM-агентов русский язык вызов инструментов function calling открытый датасет 2026» → только BFCL/τ-bench/LangChain.
- Tavily EN: «Russian tool calling benchmark LLM agents … Russian language agentic 2025 2026» → только западные.
- Tavily RU: «бенчмарк обезличивание персональных данных русский язык датасет ПДн детекция открытый» → только юридические статьи об обезличивании (233-ФЗ, 01.09.2025).
- Tavily: «"MERA Text 2.0" agentic GorillaHard …» → только новости MERA; состав «Agentic»-категории на сайте не отрендерился (SPA), взят из PR.

**Итог [A/D]:** бенчмарка «шлюз ПД × агент × реальные вызовы инструментов × русский» не существует; ближайшие соседи — GorillaHard (инструменты без исполнения и без ПД) и статья Raft (ПД без инструментов, без кода).

---

## 5. Q4 — 152-ФЗ и синтетические ПД

- **Определение** (ст. 3 п. 1 152-ФЗ): «любая информация, относящаяся к прямо или косвенно определенному или определяемому физическому лицу». Вымышленные ФИО/телефоны/адреса, не относящиеся ни к какому лицу, под определение не подпадают **по построению**. [D, на основе текста закона]
- **Что заявляют публикаторы:**
  - pii-bench: «All examples are fully synthetic. No real user data was used. … do not correspond to real individuals or organizations. Any resemblance … is coincidental.» + предупреждение, что ИНН/ОГРН юрлиц — публичные данные ЕГРЮЛ и «memorised real registration number satisfies every arithmetic rule». [A]
  - MERA (требование к любому датасету): «Если для создания датасета использованы синтетические данные, обязательно должен быть указан их источник (в том числе генеративные модели).» [A]
  - NEREL: реальные тексты Wikinews о публичных лицах; заявления о ПД **нет**, лицензии **нет**. [A]
  - Golos (речь): собственная публичная лицензия; речь размечалась на краудсорсе — про согласие дикторов в README не сказано. [B]
- **Позиция регулятора по синтетике — не найдена** (два поиска: «синтетические персональные данные 152-ФЗ …», «"вымышленные" OR "тестовые" персональные данные …»). Найденное касается обезличивания (233-ФЗ с 01.09.2025, ГИС обезличенных данных) и обучения на реальных данных («Если в обучающем датасете присутствуют данные, по которым можно прямо или косвенно определить человека — это обработка персональных данных», vc.ru). [A/C]
- **Практические риски [D]:**
  1. **Телефоны**: в российской нумерации нет резервного вымышленного диапазона (аналог US 555). Сгенерированный `+7926…` принадлежит реальному абоненту. pii-bench это игнорирует (дисклеймер). Варианты: явно невалидные формы, диапазон, который заведомо не выдан, либо декларация «номера сгенерированы, совпадения случайны» + запрет на дозвон в README.
  2. **Валидные чек-суммы**: наш же принцип «подмена фальшивая по чек-сумме» защищает от коллизии с реальным человеком; pii-bench после 08.2025 пошёл в обратную сторону (все чек-суммы валидны) и честно назвал цену.
  3. **Имена публичных лиц**: генератор-LLM может выдать реальных людей (в MASSIVE — Ирина Аллегрова и т.п.); фильтр по спискам публичных персон — норма, которую стоит записать в карточку.
  4. **Юридически безопасная формула для карточки** (собрано из pii-bench + MERA): источник синтетики (модель + затравки), «не относятся ни к одному определяемому лицу», перечень типов идентификаторов с указанием, валидны ли чек-суммы и почему, запрет использования для обучения как **просьба**, а не условие лицензии.

---

## 6. Q5 — Что сообщество вознаграждает

| Формат | Свидетельство | Оц. |
|---|---|---|
| **Habr-статья от команды + GitHub/HF** | MERA: 10K просмотров, 9 комментариев; ruMTEB и RSG — тоже Habr SberDevices; natasha (Habr 516098): +53, 198 закладок. Raft-исследование БЕЗ кода: 7.2K, 1 комментарий — отклика нет. | [A] |
| **Статья на ACL/EMNLP/NAACL + Dialogue** | RSG — EMNLP 2020; MERA — ACL 2024; ruMTEB — NAACL 2025; RuBLiMP — EMNLP 2024; NEREL — RANLP; Dialogue — Scopus-труды. Академическая легитимность = обязательна для цитирования и для включения в MERA. | [A] |
| **Включение в MERA как задача** | 15+ задач от внешних аккаунтов за год после call; авторы задач попадают в национальный бенчмарк, который прогоняют все модельные команды. Требует README RU+EN («Align the dataset README pairs», PR #48). | [A] |
| **Shared task на Dialogue / CLEF** | NEREL → RuNNE-2022, NEREL-BIO → BioNNE-2024: рост цитирований и пользователей без единого PR в репо. | [A/C] |
| **ODS-доклад / соревнование с призом** | Data Fest секции, ODS Awards, хабы (NLP 842). Аудитория практиков, не академиков. | [A] |
| **Telegram** | NLP-чат 6 667 (Кукушкин/Веселов), «Старший Авгур» 8 145 (Гусев), форум MERA. Быстрый отклик, но не «награда». | [A] |
| **HF-карточка на русском** | Норма НЕ сложилась: pii-bench — карточка только EN; MERA — пары RU+EN обязательны; Vikhr — RU. Рекомендация: две карточки. | [A/D] |

---

## 7. (i) Механики, которые сработали именно в России

1. **Формальный «call for datasets» с письменными критериями и PR-шаблоном** (MERA). До 08.2025 в репо было ~6 PR за год, все от команды; после — 25+ PR, ≥10 внешних аккаунтов, и 12 новых приватных тестов ушли в релиз. Критерии (≥300, baseline ≤0.8, синтетика с источником, RU+EN README, лицензия в meta) — это одновременно фильтр качества и инструкция.
2. **Приватный тест + автоскоринг + модерация публикации** (RSG → MERA). Приватность ответов удержала доверие; модерация с логами воспроизводимости — защита от «ручных» сабмитов.
3. **Ехать на международной инфраструктуре** (ruMTEB на MTEB, MERA на lm-eval-harness, GorillaHard на идее BFCL). Снижает порог участия: команды уже умеют запускать harness.
4. **Shared task как двигатель роста датасета** (NEREL → RuNNE/BioNNE; Dialogue Evaluation). Академики приходят за публикацией, а не за звёздами.
5. **Зонтичный бренд «национального бенчмарка»** (Альянс в сфере ИИ + экспертный совет из ВШЭ/РАН/Сколтеха + индустрия). Бенчмарк одной компании (TAPE, encodechka) либо умирает, либо поглощается зонтиком.
6. **Реестр вместо хостинга** (corus): одна функция-загрузчик на корпус, MIT, минимум обязательств — живёт 7 лет на одном мейнтейнере.
7. **Публичная починка дефекта** (pii-bench «resolve checksums» + переписанный раздел карточки) — единственный вид «роста», который датасет получил без сообщества; ни один внешний баг-репорт в HF не оставлен — значит, каналом были не issues, а личный контакт/статья.

Что **не** работает: одиночная Habr-статья без кода (Raft), репо без лицензии (NEREL — 4 форка за 5 лет), «Any contributions are welcomed!» без критериев (PingPong — 0 внешних задач), корпоративный датасет под кастомной лицензией (Golos — 8 открытых issue без ответа).

## 7. (ii) Рецепт запуска, каждый шаг — с прецедентом

| Шаг | Решение | Прецедент |
|---|---|---|
| **Имя** | `AgentPII-RU` (уже используется в репо) с задачей-подмножеством в стиле MERA `ru<Name>` (напр. `ruAgentPII`). Схема «ru»+Имя/«-RU» — норма: ruMTEB, RuCoLA, RuBLiMP, ruHumanEval, PII-Bench (ru). | MERA task naming; pii-bench |
| **Хостинг** | GitHub (харнесс, раннер «любой маскер», CI) + HF-датасет с **двумя карточками RU/EN** + HF-датасет `results` (шаблон Vikhr `requests/results`) вместо своего лидерборда. | MERA docs/dataset_hf.md; Vikhrmodels |
| **Лицензия** | Apache-2.0 на данные и код (pii-bench, RuCoLA, RuBLiMP, rulm) — совместимо с MERA (MIT) и MTEB. Не повторять NEREL (без лицензии) и Golos (кастомная). | pii-bench; MERA FAQ |
| **Структура данных** | Спаны с символьными офсетами + `negatives` + регистр (clean/chat/sloppy/voice) + для агентной части: каталог инструментов, ожидаемые аргументы, «arm» (control/gateway). Явный `held-out`-раздел как **просьба**, не условие. | pii-bench («agnostic to tokenization», «This is a request») |
| **Синтетика** | В карточке: генератор и затравки; фильтр публичных лиц; правило для телефонов/чек-сумм; «не относятся ни к одному определяемому лицу». | MERA dataset_review; pii-bench |
| **Приватная половина** | Отдать в MERA приватный тест «PII-in-tool-calls» (≥300 вопросов, baseline ≤0.8, human baseline overlap 5) через PR по их 4 шагам — так задачу прогонят все модельные команды РФ. Публичную половину держать у себя для оценки шлюзов. | MERA call for datasets; GorillaHard PR #46 как образец описания (3 раздела: суть, навыки, пример) |
| **Первый анонс** | 1) TG-чат «Natural Language Processing» (6 667; админ Кукушкин) и форум MERA; 2) Habr-статья с **историями дефектов и числами** (стиль MERA/natasha), под блогом компании; 3) секция NLP/ML & Security на Data Fest (май–июнь) и ODS-хабы; 4) письмо devaluation@dialogue-conf.org с предложением shared task на «Диалог» (июнь). | Habr 775336 (10K); NEREL→RuNNE; ODS Awards |
| **Академическая ножка** | Статья на Dialogue (RU-рецензирование) + arXiv; затем ACL/EMNLP workshop. | RSG/MERA/ruMTEB |
| **Поддержание** | CONTRIBUTING с критериями приёма кейса (как MERA), issue-шаблон «[Dataset proposal]», публичный changelog в карточке при каждой починке. | MERA issue #42 «[Dataset proposal] RuDocGround-CF»; pii-bench commit log |
| **Чего избегать** | Свой сайт-лидерборд (RSG — замер без уведомления), «contributions welcomed» без критериев (PingPong), одна статья без кода (Raft). | см. §7(i) |

## 7. (iii) Чьё внимание важно (публичные фигуры/организации)

1. **Алёна Феногенова** — @alenusch (Habr), тимлид AGI NLP SberDevices; лид RSG → MERA → ruMTEB. Ключ к MERA.
2. **Мария Тихонова** — GitHub `MariyaTikhonova`, MERA/ruMTEB core (59 коммитов в MERA).
3. **Артём Орлов** — GitHub `artemorloff`, MERA core (60 коммитов), автор GorillaHard/IFHardBench/SOB-Hard — прямой прецедент tool-calling теста.
4. **Альянс в сфере ИИ** — mera@a-ai.ru, форум t.me/+XkBIbHFg8s5iNGIy; экспертный совет (ВШЭ, РАН, Сколтех).
5. **Александр Кукушкин** — @alexkuk (TG), @alexanderkuk (Habr); natasha/corus; админ чата «Natural Language Processing» (6 667).
6. **Дмитрий Веселов** — @dveselov, второй админ того же чата.
7. **Илья Гусев** — @YallenGusev (TG «Старший Авгур» 8 145), GitHub `IlyaGusev`; Saiga, PingPong; сейчас агентные фреймворки (codearkt, academia_mcp).
8. **Алексей Натёкин** — основатель ODS.ai / Data Fest; хабы NLP и ML & Security.
9. **Богдан Минко / Евгений Кокуйкин** — HF `bogdanminko`, HiveTraceLab (ITMO AI Security Lab / Raft); авторы pii-bench и GLiNER Guard; Raft-исследование о ПД и агентах. Конкуренты, но единственные, кто уже мерил соседнюю задачу — их отзыв легитимизирует.
10. **Наталья Лукашевич** (МГУ) — NEREL; и координатор Dialogue Evaluation (devaluation@dialogue-conf.org) — путь в shared task.
11. **Роман Куцев** — LLM Arena (llmarena.ru), краудсорс-оценка; **Vikhrmodels** (HF org, 23 участника) — низовые лидерборды; **Давид Дале** (@avidale) — encodechka, авторитет по «маленьким честным бенчмаркам».

---

## 8. Ограничения этого отчёта
- Страницы mera.a-ai.ru — SPA: список задач Text 2.0 не отрендерился, состав «Agentic» взят из смерженных PR (GorillaHard — единственный явно tool-calling).
- Год статьи Raft восстановлен по судье gpt-5.2 (⇒ 2026); в HTML год не выводится.
- Число контрибьюторов MERA (7) — это авторы коммитов в main; авторы задач через PR (≥10 аккаунтов) в этот счётчик не входят, потому что PR мержились squash'ем командой.
- Не проверялись: Toloka datasets, Yandex Cup, AIJ Contest (вне 35 фетчей; их механика — корпоративные соревнования с призами, для бенчмарка шлюза не прецедент).
