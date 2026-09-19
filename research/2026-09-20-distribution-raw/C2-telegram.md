# C2 — Русскоязычный Telegram как слой усиления для серии лонгридов Habr + открытого бенчмарка (pseudex)

Дата раскопок: 2026-09-20. Бюджет: ~40 fetch (исчерпан). Числа сняты с t.me/s/<handle> (превью канала), tgstat.ru (через extract) и telega.in (карточки). Всё, что не удалось снять — помечено [D] и явно названо.

Градации доказательности:
- **[A]** — число с собственной страницы канала (t.me/s/) или tgstat.ru, снято сегодня
- **[B]** — карточка telega.in (цена, ERR, число выполненных заказов)
- **[C]** — вторичный источник (блог eLama, vc.ru, GitHub-список)
- **[D]** — вывод/память, не проверено в этом прогоне

Важная оговорка по «ER»: t.me/s/ показывает просмотры поста, не ER. Я считаю **охват/подписчики** по последним 5–6 постам — это грубая оценка ERR (reach rate), а не engagement rate telega.in (у них ER = реакции/подписчики). Обе цифры приведены там, где есть.

---

## 1. Каналы (broadcast)

### 1.1 Ядро: LLM-инженеры и продакты в РФ-бизнесе

| Канал | Handle | Подписчики | Ср. просмотры / ERR | Тема | Админ (публично) | Гостевые / репосты / реклама | Цена | Доказательство | Грейд |
|---|---|---|---|---|---|---|---|---|---|
| **LLM под капотом** | @llm_under_hood | **29.2K** (tgstat: 29 181) | 8.8K / 6.5K / 8.0K / 9.6K / 13.5K → **~9.3K, ERR ≈ 32%** | разработка продуктов на LLM, кейсы внедрения в бизнес, SGR, Enterprise RAG Challenge | Ринат Абдуллин (abdullin.com; контакт только через бота @llm_under_hood_bot) | Bio: **«Рекламы в канале - нет. За комменты от ботов баним вместе с хозяином.»** Репост чужого возможен только если автор сам сочтёт кейс интересным — канал регулярно разбирает чужие кейсы и success stories по SGR | нет | https://t.me/s/llm_under_hood ; https://tgstat.ru/channel/@llm_under_hood | A |
| **Сиолошная** | @seeallochnaya | **79.6K** | 88.7K / 28.5K / 39.5K / 32.1K / 38.5K / 34.5K → **~44K, ERR ≈ 55%** (аномально высокий — часть просмотров из репостов) | новости NLP/LLM с разбором, OpenAI-центричный | Игорь Котенков [D: @stalkermustang] | Bio без упоминания рекламы; telega.in — 404 (не в каталоге) | не продаётся | https://t.me/s/seeallochnaya | A |
| **эйай ньюз** | @ai_newz | **96.9K** | 31K / 32.3K / 27.8K / 22.3K / 23.2K / 41.6K → **~30K, ERR ≈ 31%** | новости AI, культурно-авторский | Артём Санакоев (@asanakoy), ex-Meta GenAI; **PR: @ssnowysnow** | Есть PR-контакт в bio → реклама принимается | telega.in: «от 23 076.90 ₽» (подозрительно низко для 97K, возможно старый прайс — проверить у @ssnowysnow) | https://t.me/s/ai_newz ; https://telega.in/channels/ai_newz/card | A / B |
| **Data Secrets** | @data_secrets | **93.8K** | 19.6K / 18.1K / 17.7K / 19.8K / 20.8K / 19K → **~19.2K, ERR ≈ 20%** (telega.in ERR 18.8%, ER 2.23%) | новости ML, «главный по машинному обучению», редакционный | команда, анонимно; **Сотрудничество: @veron_28**; РКН-регистрация есть | Принимает рекламу активно: **172 выполненных заказа на telega.in, 98 повторных** | **97 902 ₽ (1/24), 100 699 ₽ (2/48), 107 692 ₽ нативный, 97 902 ₽ репост** | https://telega.in/channels/data_secrets/card | A / B |
| **gonzo-обзоры ML статей** | @gonzo_ML | **24.3K** | 2.08K / 1.84K / 2.41K / 2.45K / 1.96K / 1.87K → **~2.1K, ERR ≈ 9%** (!! низкий) | разборы статей, глубокий research | Григорий Сапунов (CTO Intento) + Алексей Тихонов | Рекламы нет в bio; telega.in — 404 | нет | https://t.me/s/gonzo_ML | A |
| **Борис опять** | @boris_again | **17.6K** | 14.3K / 6.1K / 4.8K / 5.0K / 2.9K / 2.0K → **~5.8K, ERR ≈ 33%** | ML-инженерия, дайджесты, Perseus, харнессы; личный | Борис Цейтлин, **лс @btseytlin**; whois: t.me/boris_again/3400 | Есть на telega.in, но цена **139 860 ₽** при 17.6K = заградительная («не пишите мне») | 139 860 ₽ | https://t.me/s/boris_again ; https://telega.in/channels/boris_again/card | A / B |
| **Kali Novskaya** | @rybolos_channel | **19K** | 23.1K / 7.8K / 8.0K / 10.3K / 12.6K / 8.4K → **~10K, ERR ≈ 53%** | русские LLM (Muse Glimmer), open-source, командные релизы | Татьяна Шаврина [D] | Рекламы нет в bio | нет | https://t.me/s/rybolos_channel | A |
| **Мишин Лернинг** | @mishin_learning | **7.46K** | 4.1K / 2.8K / 2.7K / 3.2K / 3.0K / 4.7K → **~3.4K, ERR ≈ 46%** | новости моделей, личный | Владимир Мишин [D] | не указано | — | https://t.me/s/mishin_learning | A |
| **Техножрица** | @tech_priestess | [D: ~10K] | 3.6K / 4K на посты (tgstat) | математика, DL, NLP, research, личный | Лаида Кушнарева [D] | не указано; ведёт ПК Practical ML Conf | — | https://tgstat.ru/channel/@tech_priestess | A (просмотры) |
| **DL in NLP** | @dlinnlp | **11.6K** | ~15K на старых постах | NLP research | Владислав Лялин (@dropout05), **«(рекламы нет)»** | **Канал спит с ~окт 2024** — не тратить время | — | https://t.me/s/dlinnlp | A |
| **NLP Core Team** | @nlpcoreteam | **3.58K** | ~1.8K | команда SberDevices (ruGPT, FRED-T5), сейчас продвигает Koda | корпоративная | корпоративный, рекламу не берёт | — | https://t.me/s/nlpcoreteam | A |
| **Data Science by ODS.ai** | @opendatascience | **38 690** | 1.1K–2.6K на постах (низко) | англоязычный агрегатор ODS | **редакторы: @malev** | контакт есть, не рекламный | — | https://tgstat.ru/channel/@opendatascience | A |
| **Машинное обучение RU** | @machinelearning_ru | **18 196** | ~1.6K | сеть агрегаторов (@ai_machinelearning_big_data, @pythonl и др.), **рекламный** | **админ @workakkk** | Продаёт рекламу открыто (в ленте курсы Stepik со скидками) | [D: через @workakkk, ориентир 5–15K ₽] | https://tgstat.ru/channel/@machinelearning_ru | A |
| **Машинное обучение: подготовка к собеседованию** | @machinelearning_interview | **30.3K** | telega.in ERR 7.6%, ER 2.03% | ML-интервью, агрегатор | — | **163 заказа, 124 повторных**, 90% мужчины | **25 174.80 ₽ (1/24), 26 573 ₽ (2/48), 40 559 ₽ (3/72), 48 951 ₽ 30 дней, 41 958 ₽ нативный** | https://telega.in/channels/machinelearning_interview/card | B |
| **Denis Sexy IT** | @denissexy | **137K** | 19K / 39.7K / 42.1K / 35.2K / 44.8K / 67.9K → **~41.5K, ERR ≈ 30%** | технологии, широкая | Денис Ширяев | Bio: **«Реклама в канале возможна для юрлиц и физ-лиц у которых работает SWIFT оплата в Нидерланды»** — для РФ-юрлица практически закрыто | [D] | https://t.me/s/denissexy | A |
| **AI Happens** | @aihappens | [D] | ~7K на постах (tgstat) | AI + продукт, личный, много мата | [D] | не указано | — | https://tgstat.ru/channel/@aihappens | A (просмотры) |
| **Just AI** | @just_ai_official | **1 987** | ~720 на Habr-репостах | корпоративный канал вендора | Just AI | публикуют свои же Habr-статьи; исторически писали ровно про наш кейс: **«компании разработали специальные скрипты для анонимизации данных перед отправкой в облако 🤨 Хотя качество маскирования данных с помощью таких скриптов вызывает вопросы... есть и те, кто не может себе позволить облачные LLM из-за федерального закона о персональных данных»** | — | https://t.me/s/just_ai_official?after=291 | A |

### 1.2 AI-безопасность (самая точная аудитория для guardrails/PII — но маленькая)

Источник списка — GitHub `ivolake/awesome-ai-security-tg` [C], числа — tgstat/t.me [A]. Вся ниша 2–7K на канал; авторы **дружат и кросс-промоутят через общую папку** («Папка с каналами по безопасности ИИ» в bio у PWN AI и Борис_ь с ml) и **в начале 2026 собирались вместе подводить итоги года** (пост в @borismlsec: «мы (авторы телеграм-каналов по безопасности ИИ) собрались, чтобы подвести итоги прошедшего года»). Это значит: попасть в одну — попасть в папку.

| Канал | Handle | Подписчики | Просмотры | Тема | Админ | Политика | Грейд |
|---|---|---|---|---|---|---|---|
| **PWN AI** | @pwnai | **7.31K** | 0.9K–2.4K → ~1.7K | практический AI security / MLSecOps, guardrails, GuardRate leaderboard | Артём Семёнов [D] | Bio: **«Нет рекламе. Мой личный канал.»** Только органический репост | A |
| **Евгений Кокуйкин — Raft** | @kokuykin | **2.14K** | ~580 | Raft AI, HiveTrace Guardrails / DataClean, OWASP Agentic Top 10, GraySwan | Евгений Кокуйкин, **контакт @artmaro** | корпоративно-личный; **прямой конкурент по DataClean** — репост маловероятен, но бенчмарк может обсудить | A |
| **AI Security Lab** (Raft × ИТМО) | @aisecuritylab | **2 212** | ~1.1K | гард-модели, каскады, вебинары | лид лабы Сабрина Садиех (@jdata_blog) | лаборатория; публикуют разборы гардов — наш бенчмарк по PII им по теме | A |
| **LLM Security** («llm security и каланы») | @llmsecurity | **2 024** | 0.66K–0.88K | jailbreaks, prompt injection, обзоры статей | [D] | не указано | A |
| **Борис_ь с ml** | @borismlsec | **2 388** | 1.0K–1.4K | ML + ИБ, методология, разборы конференций | Борис Захир [D] | **«На некоммерческой основе»** + @mlsecfeed | A |
| ML&Sec Feed / AISec x_feed / AI SecOps / OK ML / Poxek AI / AISecurilka / paranoAISecure | @mlsecfeed @aisecnews @aisecops @okmlai @poxek_ai @aisecurilka @paranoAISecure | [D] | — | tier 2 из списка | — | — | C |
| Чаты: **Безопасность ИИ и ML** @secaiml; **LLAMATOR** @llamator | — | [D; tgstat не знает @secaiml] | — | открытые чаты по AI security | — | — | C |

### 1.3 ИБ и 152-ФЗ (CTO, CISO, DPO)

| Канал | Handle | Подписчики | Просмотры / ERR | Тема | Админ | Политика | Цена | Доказательство | Грейд |
|---|---|---|---|---|---|---|---|---|---|
| **Пост Лукацкого** | @alukatsky | **37.9K** | 5.5K / 4.6K / 4.0K / 4.2K / 3.9K / 2.9K → **~4.2K, ERR ≈ 11%** | кибербез, CISO-повестка; сейчас много про ИИ-агентов в ИБ («не так важна модель... сколько харнесс вокруг нее») | Алексей Лукацкий, **@alukatsk** | Bio: **«Рекламу не размещаю!!!»**, «Канал личный - мой работодатель никак не влияет» | нет | https://t.me/s/alukatsky | A |
| **SecAtor** | @true_secator | **41.7K** | 5.5K / 4.8K / 4.9K / 5.4K / 5.8K → **~5.3K, ERR ≈ 13%** | threat intel, утечки, уязвимости | аноним, mschniperson@mailfence.com | не продаётся (telega.in 404); новостной — возьмут, если есть повод | нет | https://t.me/s/true_secator | A |
| **Информация опасносте** | @alexmakus | **18.8K** | 5.3K / 11K / 12.3K / 9.8K / 9.1K → **~9.5K, ERR ≈ 50%** | cybersec-новости, ироничный | @alexmaknet | Bio: **«Размещение рекламы остановлено в связи с войной России против Украины»** | нет | https://t.me/s/alexmakus | A |
| **Codeby** | @codeby_sec | **37K** | 2.8K / 2.5K / 2.4K / 2.3K / 2.4K → **~2.5K, ERR ≈ 7%** (telega.in ERR 5.0%) | пентест, обучение, CTF | сообщество; **Сотрудничество @KinWiz, Реклама @Savchenkova_Valentina** | принимает: 24 заказа на telega.in | **20 979 ₽ (1/24), 25 175 ₽ (2/48), 32 168 ₽ (3/72), 41 958 ₽ 30 дней/нативный** | https://telega.in/channels/codeby_sec/card | A / B |
| **Б-152: защита персональных данных** | @b152privacy | **8 797** | ~1.1K на постах | 152-ФЗ практика, курсы DPO, аутсорс ответственного за ПДн | компания Б-152 (b-152.ru) | вендор; продают курс DPO; репост чужого — только если полезно их аудитории DPO | — | https://tgstat.ru/channel/@b152privacy | A |
| **152DOC** | @persdan_152doc | **11** (мёртв) | — | — | — | пропустить | — | tgstat | A |
| **Privacy Advocates / RPPA / «Комплаенс по ПДн» / Кибердед** | — | **не найдены** под предполагаемыми handle (tgstat 404 на @privacyadvocates) | — | — | — | нужен ручной поиск в самом Telegram | — | — | D |

### 1.4 Широкие IT-медиа (охват, не точность)

| Канал | Handle | Подписчики | Политика | Доказательство | Грейд |
|---|---|---|---|---|---|
| **Хабр** | @habr_com | **132 495** | Реклама → **adv@habr.team**. Канал **сам репостит статьи Хабра** — в «популярном» tgstat: «Три месяца с Claude: хороший ассистент, плохой программист», «Хайп вокруг ИИ: реальное состояние дел» — т.е. хорошая статья Хабра получает канал автоматически, без договорённостей | https://tgstat.ru/channel/@habr_com | A |
| **Типичный программист** | @tproger | [D: ~100K+] | **Реклама: @tproger_sales_bot**; «Другие каналы: @tproger_channels» | https://tgstat.ru/channel/@tproger | A |
| Backend Community, DevOps Deflope, Highload++ | — | tgstat 404 / fetch failed | не проверены | — | D |

---

## 2. Чаты (discussion)

| Чат | Handle | Участники | Админы | Правила самопиара (дословно где есть) | Грейд |
|---|---|---|---|---|---|
| **Natural Language Processing** | @natural_language_processing | [D: порядка 10K, tgstat /stat требует логин] | **@dveselov, @alexkuk** (Александр Кукушкин — автор Natasha, на которой стоит наш NER) | «Русскоязычный чат про NLP: QA, новости, мероприятия, вакансии. Описание — t.me/natural_language_processing/55810». Спутники: **@NLP_eng** (англ.), **@NLP_jobs**. Пост с правилами (55810) не вытянулся — прочитать руками до постинга | A (админы) / D (размер) |
| **ПДн 152-ФЗ** | @PDn152FZ | [D] | @zlonov | Правила (telegra.ph, 18.09.2025) — **разрешено: «Размещения полезных материалов, ссылок на публикации по заявленной тематике чата»**; **запрещено: «Реклама (любая) без согласования с администраторами и не от их имени»**, «Публикация ссылок на иные каналы и чаты Telegram... без согласования», «Размещение платного контента», анонсы мероприятий только через админов. Стиль: «Спорьте с фактами... ссылками на нормативные правовые акты», «деловой стиль». Дружественные: @ruCyberSecurity, @vseFZ, @KII187FZ, @EP63FZ, @KT98FZ | A |
| **ruCyberSecurity** | @ruCyberSecurity | [D] | — | «Три правила чата: взаимное уважение, соблюдение тематики (кибербезопасность) и ненарушение законодательства» | A |
| **Python** | @ru_python | [D: крупный] | — | «Уютный чат для профессионалов... Как не получить бан: t.me/ru_python/2755095» — прочитать перед постом | A |
| **Безопасность ИИ и ML** | @secaiml | [D] | — | «Open chat dedicated to security of AI and ML» (из awesome-списка) | C |
| **LLAMATOR — AI Red Team Community** | @llamator | [D] | Raft/ИТМО | red-team фреймворк; бенчмарк по PII туда ложится | C |
| Vikhr / Saiga / LLM Arena / LangChain RU / n8n RU / AI Agents RU / Claude Code RU / ODS-чаты | — | **не верифицированы** (поиск не дал handle) | — | ODS живёт в Slack/Matrix + канал @opendatascience; остальные искать руками в Telegram | D |

**Вывод по чатам:** единственный чат с явно написанной политикой — @PDn152FZ, и она допускает ссылку на публикацию по теме (бенчмарк = «полезный материал»), но запрещает любую рекламу и ссылки на каналы. Формулировка поста должна быть «вот измерение, вот методика, вот код», без упоминания продукта и без ссылки на свой канал.

---

## 3. Механика

### 3.1 Как Habr-статьи расходятся по Telegram (что подтверждается)
- **Официальный @habr_com (132K) репостит статьи сам** — сильные материалы попадают туда без переговоров [A, tgstat popular].
- Вендоры репостят свои Habr-статьи в свои каналы: Just AI → 721 просмотр на репосте статьи «Окно в LLM: как компании из России найти безопасную альтернативу ChatGPT» [A]. То есть корпоративный репост даёт сотни просмотров, не тысячи.
- Авторские каналы (Data Secrets, Борис опять, LLM под капотом) берут Habr-материал как **повод**, не как ссылку: «Вышел подробный туториал по Perseus» (@boris_again, 5.0K просмотров) — репост туториала другой команды [A].
- vc.ru (2026, [C]): «находите топ-10 каналов в смежных нишах, которые регулярно делают подборки, и предлагаете себя... В 2026 году отношения между авторами ценятся больше, чем когда-либо»; «Посевы в тематических чатах... вступаете в 20–30 тематических чатов... Периодически, когда это уместно, упоминаете свой канал. Это медленно».
- Habr (18.02.2026, [C]): «дублируйте контент на несколько площадок. Например, технические статьи зайдут не только на Хабре, но и на дтф».

### 3.2 Время постинга [C — нет tgstat-исследования 2026 в открытом доступе]
- Autogram (2026): «Публичные исследования сходятся на двух окнах для Telegram-каналов — приблизительно **13:00-16:00 и 18:00-22:00** по местному времени подписчика, **со вторника по пятницу**»; «Лонгриду нужен не "слот пика просмотров", а "слот пика внимания", который часто сдвинут на более поздний вечер».
- Rambler&Co (янв–июн 2025, ppc.world): вдумчивое чтение **5–8 утра со смартфона, 9–10 с десктопа**; «самое непопулярное время... **с 10:00 до 12:00 и с 13:00 до 17:00**»; «самый популярный день недели... **среда**».
- PublishIQ (2026): «Для B2B (бизнес) — 10:00-12:00», «Среда, четверг — самая высокая активность», «Понедельник утром — худший охват недели».
- Источники расходятся по дневному окну (10–12 «мёртвое» у Rambler vs «B2B-пик» у PublishIQ) — тестировать на своём канале двухнедельными блоками, как советует Autogram.

### 3.3 Прайс-лист посевов (telega.in, формат 1/24, ₽, комиссия 15% уже внутри)
| Канал | Подписчики | ERR | 1/24 | Нативный | ₽ за 1000 подписчиков | ₽ за 1 просмотр (оценка = цена / (подп × ERR)) | URL |
|---|---|---|---|---|---|---|---|
| Data Secrets | 93.8K | 18.8% | **97 902** | 107 692 | 1 044 | **5.6 ₽** | https://telega.in/channels/data_secrets/card |
| ML: подготовка к собеседованию | 30.3K | 7.6% | **25 175** | 41 958 | 831 | **10.9 ₽** | https://telega.in/channels/machinelearning_interview/card |
| Codeby | 37.0K | 5.0% | **20 979** | 41 958 | 567 | **11.3 ₽** | https://telega.in/channels/codeby_sec/card |
| эйай ньюз | 96.9K | ~31% (по t.me) | **от 23 077** | — | 238 | ~0.8 ₽ (нереалистично — уточнять у @ssnowysnow) | https://telega.in/channels/ai_newz/card |
| Борис опять | 17.6K | ~33% | **139 860** | — | 7 947 | 24 ₽ (заградительная) | https://telega.in/channels/boris_again/card |
| Сиолошная, gonzo_ML, SecAtor | — | — | **404 — не продаются через биржу** | — | — | — | telega.in |

Рыночные ориентиры: Telega.in (свой канал): «Средняя стоимость размещения в тематических каналах составляет 5-10 тысяч рублей. В среднем на платформе один рекламодатель инвестирует около 200 тысяч» [B]. eLama (сентябрь 2026): посты через Telega.in «От 70 до 2,34 млн руб.» [C]. Telega.in берёт каналы от **2000 подписчиков и 3 месяцев** [C, unisender]. Likeni (07.05.2026): «В апреле реклама в Telegram подешевела почти на 16% после падения охватов» [C].

### 3.4 Telegram Ads, РФ, 2026 [C — три источника, расходятся в деталях]
- **Минимальный бюджет:** eLama — «250 € + 20% комиссия реселлера + 22% НДС. Итого — 366 €»; «У большинства реселлеров... минимальный бюджет составляет 500 €»; «через Маркетолог Pro от МТС Ads стартовый бюджет ниже — 250 €, через кабинет от «МегаФона» — 100 €». Пример полной стоимости: «при рекламном бюджете €1000 комиссия 20% составит €200, а НДС — €264. Таким образом, на запуск потребуется €1464».
- **Минимальная ставка CPM:** eLama — «С февраля 2026 года минимальная ставка в Telegram Ads составляет 0,7 € во всех тематиках, кроме «Политики и происшествия» (0,35 €)»; aksanov/vc.ru называют 1 € для таргета по каналам. Наценки за оформление (aksanov): «логотип канала: +30%... картинка-баннер: +50%... видео: от +70%». vc.ru: «на практике старт часто получается около 2 евро».
- **Реальный CPM:** eLama — «от 0,5 до 5 € в зависимости от конкуренции и тематики. В конкурентных нишах (инвестиции, недвижимость, маркетинг) реальные ставки могут достигать 5–15 €».
- **Дешёвый вход:** Stars-кабинет «~1000 Stars ≈ 1200 ₽» (aksanov) / «~2 500 ₽» (fedotovseo), но «ожидание 21 день после пополнения перед запуском» и нет маркировки по 38-ФЗ.
- **Регуляторика:** eLama — «до конца 2026 года ФАС не штрафует за рекламу в Telegram».
- Стоимость подписчика через Ads (fedotovseo): «0.3-1.2 EUR» vs посевы «4-10 EUR»; moscow.mba: в B2B «от 80–120 рублей... до нескольких сотен».

---

## 4. Own-channel playbook (факты, не советы)

**LLM под капотом (Ринат Абдуллин)** — единственный в списке, чью траекторию удалось снять по постам:
- Старт: середина 2023 («Этот канал начинался три года назад с разбора кейсов внедрения LLM в бизнес продукты в компаниях» — пост 2026, tgstat popular). Первые посты (#39–59) — **разборы кейсов и бенчмарки моделей**, без новостей.
- Январь 2024 (пост ~#264): **«С прошлого поста, где я рассказывал о себе, прошло больше полугода, а канал вырос в 10 раз: со 170 до почти 1700 подписчиков»**. В тот момент новостной пост собирал 3.66K просмотров при 1.7K подписчиков — т.е. ERR > 200% за счёт пересылок.
- Сентябрь 2026: **29.2K**, ~9K просмотров на пост, **«Рекламы в канале - нет»**, контакт только через бота.
- Что работало (по контенту): (1) **собственный открытый бенчмарк** — LLM Product Benchmarks и Enterprise RAG Challenge (упоминается в abdullin.com/about и в чужих отзывах: «thanks Rinat Abdullin for the Enterprise RAG Challenge too»); (2) методология с именем — **Schema-Guided Reasoning**, которую читатели пересказывают как success story и которую он репостит («Keep sharing your successful use-cases!»); (3) курс и вебинары («пяти потокам слушателей»); (4) оффлайн-встречи сообщества (Нови-Сад, 2026); (5) устойчивая подпись «Ваш, @llm_under_hood 🤗» и «Пар выпустил))» — личный голос. **Прямая аналогия с нашим кейсом: открытый бенчмарк + названный метод = именно то, что вырастило этот канал.**

**Борис опять** — 17.6K, личный, whois-пост закреплён (t.me/boris_again/3400), лс в bio, цена на бирже заградительная — модель «я не продаюсь, но пиши».

**Ниша AI-security** — авторы каналов по 2–7K (PWN AI 7.3K, Борис_ь 2.4K, AI Security Lab 2.2K, Raft 2.1K, LLM Security 2.0K) растут **папкой** (общая папка каналов в bio) и совместными итогами года. Для нового канала в этой нише вход — попросить включить в папку.

**Корпоративные каналы не растут:** Just AI — 1 987 подписчиков и ~720 просмотров после нескольких лет; NLP Core Team — 3.58K. Личный канал Кокуйкина (2.1K) сопоставим с корпоративным Just AI. Вывод из данных: у личных каналов ERR 30–50%, у корпоративных — сотни просмотров.

**Ориентиры по механике (vc.ru, 2026 [C]):** «регулярность публикаций (не менее 4–5 постов в неделю), высокая скорость получения реакций в первые 30 минут после публикации, наличие сохранений и пересылок»; «Первый месяц — создайте контентную базу. Минимум 20 качественных постов»; «стабильный рост 1–3% в неделю на старте — хороший знак» (moscow.mba). Нормальный ER (реакции/подписчики) «от 3% до 6%» (moscow.mba) — у Data Secrets на telega.in 2.23%.

---

## 5. Ранжированный список outreach (бесплатное — первым)

### Tier 0 — где репост стоит ноль и попадает точно в ЦА
1. **@alexkuk (Александр Кукушкин)** и **@dveselov** — админы NLP-чата, Кукушкин автор Natasha, на которой стоит наш детектор. Бенчмарк русского PII-NER — это буквально его тема. Постить в @natural_language_processing после прочтения 55810.
2. **@pwnai** (7.3K, «нет рекламе», guardrails/GuardRate) — прислать бенчмарк как материал, не как продукт. Попасть → попасть в общую AISec-папку.
3. **@aisecuritylab** (2.2K) и **@llamator** — публикуют разборы гард-моделей; PII-бенчмарк в чатовом регистре им в масть.
4. **@PDn152FZ** — единственный чат с правилами, разрешающими «ссылки на публикации по тематике». Пост про бенчмарк маскирования как измерение для 152-ФЗ, без продукта.
5. **@llm_under_hood** — рекламы нет, но Абдуллин сам живёт бенчмарками (ERC). Прислать через @llm_under_hood_bot результаты, а не пресс-релиз.
6. **@habr_com** — автоматически: сильная статья репостится сама (132K).
7. **@boris_again** — лс @btseytlin; репостит чужие туториалы (Perseus, 5K просмотров).
8. **@alukatsky** — «Рекламу не размещаю!!!», но пишет про ИИ-агентов в ИБ; 152-ФЗ + агенты — его повестка; @alukatsk.
9. **@borismlsec** — «на некоммерческой основе», ML+ИБ методология.
10. **@rybolos_channel** (Шаврина) — русские LLM и open-source; бенчмарк на русском корпусе — её область.
11. **@b152privacy** (8.8K DPO) — вендор, но аудитория DPO; предложить материал «как маскировать ПДн перед LLM» как гостевой.

### Tier 1 — платно, если понадобится (CPV-оценка)
| Канал | Цена 1/24 | ₽/просмотр | Кому |
|---|---|---|---|
| Data Secrets | 97 902 ₽ | ~5.6 | широкий ML, 172 заказа — отлаженный процесс |
| Codeby | 20 979 ₽ | ~11 | ИБ-практики |
| ML: подготовка к собеседованию | 25 175 ₽ | ~11 | ML-инженеры junior/middle |
| эйай ньюз | «от 23 077 ₽» | уточнить у @ssnowysnow | широкий AI |
| Машинное обучение RU / сеть @workakkk | [D] | — | агрегаторы, дешёвый охват |
| Tproger | @tproger_sales_bot | [D] | широкий IT |
| Хабр | adv@habr.team | [D] | широкий IT |

### Закрыто для рекламы (не тратить время на «купить»): Сиолошная, gonzo_ML, SecAtor, Пост Лукацкого, Информация опасносте, LLM под капотом, DL in NLP, PWN AI, Борис_ь с ml; Denis Sexy IT — только SWIFT в Нидерланды.

---

## 6. Топ-персоны (публичные handle)

| # | Кто | Handle | Почему важен для нас |
|---|---|---|---|
| 1 | Александр Кукушкин | @alexkuk | автор Natasha, админ NLP-чата — наш детектор стоит на его библиотеке |
| 2 | Ринат Абдуллин | @llm_under_hood_bot / abdullin.com | 29K, enterprise-LLM в РФ/ЕС, живёт бенчмарками |
| 3 | Артём Санакоев | @asanakoy (PR @ssnowysnow) | 97K, широкий AI |
| 4 | Борис Цейтлин | @btseytlin | 17.6K, ML-инженерия, репостит чужие туториалы |
| 5 | Алексей Лукацкий | @alukatsk | 38K CISO-аудитория, 152-ФЗ + ИИ-агенты |
| 6 | Евгений Кокуйкин | @artmaro | Raft/HiveTrace — конкурент по DataClean, но узел AI-security сообщества и OWASP |
| 7 | Артём Семёнов [D] | @pwnai | 7.3K, guardrails, держатель AISec-папки |
| 8 | Сабрина Садиех | @jdata_blog | лид AI Security Lab (Raft × ИТМО) |
| 9 | Татьяна Шаврина [D] | @rybolos_channel | 19K, русские LLM |
| 10 | Игорь Котенков [D] | @seeallochnaya | 80K, но не продаётся и не про enterprise — только если бенчмарк станет новостью |
| 11 | Григорий Сапунов | @gonzo_ML | 24K research-аудитория, низкий ERR (~9%) |
| 12 | Дмитрий Веселов | @dveselov | второй админ NLP-чата |
| 13 | Data Secrets (редакция) | @veron_28 | 94K, платно, отлажено |
| 14 | Борис Захир [D] | @borismlsec | ML+ИБ методология |
| 15 | @zlonov | @zlonov | админ чата ПДн 152-ФЗ и автор его правил |

---

## 7. Что НЕ удалось снять (честный список)
- Размер чата @natural_language_processing и его правила (пост 55810) — tgstat /stat за логином, t.me-пост не отдался.
- Handle и размеры чатов Vikhr / Saiga / LLM Arena / LangChain RU / n8n RU / Claude Code RU — поиск не нашёл; искать внутри Telegram.
- Privacy Advocates, RPPA, «Комплаенс по ПДн», Кибердед, «AI для всех», «Шорты ML», «Deep Dive AI», «Приключения ИИ в бизнесе», «Технологии, медиа и общество», Backend Community, DevOps Deflope, Highload++ — не проверены (бюджет fetch).
- Точные подписчики Техножрицы, AI Happens, Tproger, PWN-tier-2 каналов — tgstat отдал только просмотры.
- Исследование tgstat по времени постинга 2026 — в открытом доступе не найдено; приведены Rambler&Co 2025 и два блога.
- Примеры, где перечисленные каналы **уже** писали про PII-маскирование/guardrails: найдено только у Just AI (цитата выше) и косвенно у Raft/AI Security Lab (HiveTrace DataClean, гард-модели). Специального поста про PII-tokenization у авторских каналов не найдено — то есть тема свободна.

## Источники (все URL)
- https://t.me/s/llm_under_hood ; https://t.me/s/llm_under_hood?before=264 ; https://t.me/s/llm_under_hood?before=60 ; https://tgstat.ru/channel/@llm_under_hood
- https://t.me/s/seeallochnaya ; https://t.me/s/gonzo_ML ; https://t.me/s/data_secrets ; https://t.me/s/ai_newz ; https://t.me/s/denissexy ; https://t.me/s/boris_again ; https://t.me/s/mishin_learning ; https://t.me/s/rybolos_channel ; https://t.me/s/alukatsky ; https://t.me/s/true_secator ; https://t.me/s/alexmakus ; https://t.me/s/dlinnlp ; https://t.me/s/nlpcoreteam ; https://t.me/s/codeby_sec ; https://t.me/s/pwnai ; https://t.me/s/kokuykin ; https://t.me/s/just_ai_official?after=291
- https://tgstat.ru/channel/@habr_com ; https://tgstat.ru/channel/@tproger ; https://tgstat.ru/channel/@just_ai_official ; https://tgstat.ru/channel/@b152privacy ; https://tgstat.ru/channel/@persdan_152doc ; https://tgstat.ru/chat/@natural_language_processing ; https://tgstat.ru/chat/@pdn152fz ; https://tgstat.ru/chat/@ruCyberSecurity ; https://tgstat.ru/chat/@ru_python ; https://tgstat.ru/channel/@opendatascience ; https://tgstat.ru/channel/@machinelearning_ru ; https://tgstat.ru/channel/@tech_priestess ; https://tgstat.ru/channel/@aihappens ; https://tgstat.ru/channel/@pwnai ; https://tgstat.ru/channel/@kokuykin ; https://tgstat.ru/channel/@llmsecurity ; https://tgstat.ru/channel/@aisecuritylab ; https://tgstat.ru/channel/@borismlsec
- https://telega.in/channels/data_secrets/card ; https://telega.in/channels/ai_newz/card ; https://telega.in/channels/boris_again/card ; https://telega.in/channels/codeby_sec/card ; https://telega.in/channels/machinelearning_interview/card ; https://t.me/s/telegain?before=1027 ; https://telega.in/blog/kak-uznat-spravedlivuju-stoimost-reklamy-v-kanale ; https://www.unisender.com/ru/blog/gajd-po-telega-in
- https://elama.ru/blog/skolko-stoit-reklama-v-telegram ; https://elama.ru/blog/vse-chto-nuzhno-znat-o-cpm-v-telegram-ads ; https://aksanov.digital/blog/telegram-ads/minimalnyj-byudzhet ; https://fedotovseo.ru/blog/stoimost-reklamy-telegram-2026 ; https://vc.ru/marketing/2710435-reklama-v-telegram-ads-v-2026-zapusk-stoimost-i-osobennosti ; https://neurounit.ai/reklama-telegram/stoimost
- https://autogram.ninja/ru/blog/luchshee-vremya-publikatsii-telegram-kanal-nisha ; https://ppc.world/news/v-kakoe-vremya-luchshe-postit-v-telegram-i-drugih-socsetyah-analitiki-nazvali-tihie-chasy ; https://publishiq.ru/blog/luchshee-vremya-publikacii-socsetey ; https://likeni.ru/events/luchshee-vremya-dlya-postinga-vo-vkontakte
- https://github.com/ivolake/awesome-ai-security-tg ; https://telegra.ph/Pravila-chata-PDn-152-FZ-09-18 ; https://hivetrace.ru
- https://vc.ru/toptelegram/2994091-kak-prodvigat-kanaly-v-telegram ; https://habr.com/ru/articles/1001028 ; https://moscow.mba/journal/prodvizhenie-v-telegram-dlya-biznesa-kak-prevratit-kanal-v-istochnik-klientov ; https://trends.rbc.ru/trends/social/cmrm/68abfbba9a7947743b95f729 ; https://abdullin.com/about-me
