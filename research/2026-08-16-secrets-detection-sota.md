# Детекция секретов (API-ключи, токены, пароли, приватные ключи): что реально используют в проде

**Дата:** 2026-08-16 · **Повод:** для маскирующего гейта Pseudex нужна доказательная база
по детекции СЕКРЕТОВ (не PII) — если решим добавить такой слой, ложное срабатывание
там ломает tool-call так же, как и на PII, поэтому вопрос тот же: что даёт минимум
ложных срабатываний при приемлемой полноте. Этот файл — сырая доказательная база,
не архитектурное решение.

**Проверено:** прямым чтением исходников, а не по памяти или пересказу —
`config/gitleaks.toml` скачан и разобран `grep`'ом построчно (222 правила, точный
подсчёт `grep -c '^\[\[rules\]\]'`); `detect_secrets/plugins/keyword.py` скачан и
прочитан целиком (весь DENYLIST процитирован дословно); исходники детекторов
trufflehog (`anthropic.go`, `openrouter.go`, `deepseek.go`, `googlegemini.go`,
`yandex.go`) получены напрямую; список директорий `pkg/detectors` — через GitHub
API (901 запись); issue-треды всех трёх репозиториев — через `gh search issues` /
`gh issue view`; научные статьи — через `export.arxiv.org/api/query` (реальный
arXiv ID у каждой); HuggingFace — через прямой поиск по `huggingface.co/models`;
официальная документация вендоров — прямым фетчем (Anthropic/platform.claude.com,
AWS IAM docs, GitHub docs, Slack docs.slack.dev, Stripe docs.stripe.com, Google
Cloud docs, Yandex Cloud docs, Sber GigaChat docs, T-Bank developer docs); RFC 7468
— напрямую с rfc-editor.org. Веб-поиск (WebSearch) в этой сессии был исчерпан
(бюджет 200/200), поэтому весь ресёрч сделан через прямой fetch известных URL и
`gh`/GitHub API — это ЖЁСТЧЕ по покрытию, чем поиск, но зато каждая ссылка ниже —
это то, что реально было открыто, а не то, что нашёл поисковик.

---

## Ответ

- **Для precision-first задачи якорь по префиксу — доминирующий продакшен-подход.**
  Из 222 правил `gitleaks.toml` подавляющее большинство — это литеральный
  префикс/формат (`sk-ant-`, `ghp_`, `AKIA`, `xoxb-`...), энтропия там, где
  используется, — ДОПОЛНИТЕЛЬНЫЙ фильтр поверх префикса, а не замена ему.
- **trufflehog добавляет третий, самый сильный механизм — живую верификацию.**
  Сетевой вызов к API провайдера (`GetCallerIdentity`, `/v1/models`, `/v1/key`...)
  даёt бинарный ответ valid/invalid — это единственный из трёх механизмов, который
  устраняет ложные срабатывания полностью, а не статистически.
- **Чистая энтропия Шеннона (`detect-secrets` `Base64HighEntropyString` /
  `HexHighEntropyString`) — источник ложных срабатываний №1** по собственному
  issue-трекеру инструмента: UUID, git SHA, base64-блобы, короткие имена
  переменных — все пересекают дефолтные пороги (base64=4.5, hex=3.0) в реальных
  репортах (ссылки в разделе 2).
- **Строгого опубликованного бенчмарка "энтропия vs префикс" не существует** — ни
  в одном из трёх репозиториев, ни в документации, ни в 4 найденных статьях.
  Это прямо помечено [D], а не выдумано.
- **Каталог префиксов** уверенно закрывает ~20 международных сервисов
  (по большей части [A] — код скан-инструмента + документация вендора совпадают).
  Слабое место — Mistral/Cohere/OpenRouter не имеют жёсткого литерального
  префикса у всех вендоров одинаково, а **RU-сервисы, кроме Yandex Cloud, вообще
  не имеют публично задокументированного формата** — это честный отрицательный
  результат, не пробел в ресёрче.
- **ML-моделей специально под секреты в проде — по сути нет** как отдельного
  класса. Единственная найденная HF-модель — нишевый проект одного автора
  (72 загрузки/мес). Зато есть 3 релевантные научные работы 2024–2026 (F1
  92–98.5%) и один реальный продакшен-фиче — GitHub Advanced Security
  "AI-detected secrets" — но ВЕЗДЕ без исключения ML работает ВТОРЫМ этапом
  поверх regex-кандидатов, не вместо него.
- **Свободнотекстовый пароль без формата — нерешённая задача** у всех трёх
  open-source инструментов. `KeywordDetector` у `detect-secrets` — единственный
  такой механизм, и его словарь-депшлист буквально содержит только английские
  слова + испанское `contraseña`/`contrasena`. Кириллицы там нет. Формат «пароль
  от почты — qwerty123» этот механизм не поймает: ни ключевого слова, ни
  code-shaped синтаксиса присваивания.

---

## 1. Инструменты

| | detect-secrets (Yelp) | gitleaks | trufflehog |
|---|---|---|---|
| Архитектура | regex-плагины + 2 плагина на энтропии Шеннона + keyword-proximity | regex-first, энтропия — опциональный **per-rule** вторичный гейт | regex/prefix детекторы + **живая верификация** сетевым вызовом к API провайдера; энтропия — опциональный вторичный фильтр только для неверифицируемых совпадений |
| Кол-во детекторов | **~27 классов** в ~25 файлах `detect_secrets/plugins/` [A] | **222 правила**, посчитано напрямую (`grep -c '^\[\[rules\]\]' config/gitleaks.toml`) [A] | **901 директория** в `pkg/detectors` (посчитано через GitHub API) [A]; README сам заявляет «800+ типов секретов, 700+ с активной верификацией» [A читал напрямую] |
| Файл правил | [`detect_secrets/plugins/`](https://github.com/Yelp/detect-secrets/tree/master/detect_secrets/plugins) (каждый детектор — отдельный `.py`) | [`config/gitleaks.toml`](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml) | [`pkg/detectors/`](https://github.com/trufflesecurity/trufflehog/tree/main/pkg/detectors) (по директории на детектор) |
| Анти-FP | baseline-файл `.secrets.baseline` (новые находки диффятся против него); `detect-secrets audit` — ручная разметка; инлайн `# pragma: allowlist secret` / `# pragma: allowlist nextline secret`; флаги порога энтропии `--base64-limit` (**default 4.5**) / `--hex-limit` (**default 3.0**) [A README] | `keywords[]` — правило вообще не запускается, если в строке нет ни одного keyword (сильно режет и cost, и FP); **entropy — не глобальный, а per-rule** (у `generic-api-key` = 3.5, у `aws-access-token` = 3, у `jwt` = 3; многие уже‑якорённые по префиксу правила типа `github-pat`/`stripe`/`gitlab-*` тоже несут entropy как ДОПОЛНИТЕЛЬНЫЙ гейт сверху префикса, не вместо него); allowlists (regex/path/commit/stopwords); инлайн `gitleaks:allow` [A README + сам toml] | **живая верификация — главный механизм**: реальный HTTP-запрos к API провайдера (пример: AWS `GetCallerIdentity`), статус `verified` / `unverified` / `unknown`; `--filter-entropy` (рекомендованный старт 3.0) — вторичный фильтр только для непроверяемых совпадений [A README] |
| Лицензия | **Apache License 2.0** [A LICENSE-файл] | **MIT**, © Zachary Rice 2019 [A LICENSE-файл] | **AGPL-3.0** с версии v3.0 (раньше была другая) [A README, раздел License Change] |

Пример живой верификации, прочитанный напрямую в коде: `anthropic.go` различает
`sk-ant-admin01-` (проверяется GET `https://api.anthropic.com/v1/organizations/api_keys`)
и `sk-ant-api03-` (проверяется GET `https://api.anthropic.com/v1/models`), 200 = валиден,
401/404 = невалиден [A]
[github.com/trufflesecurity/trufflehog/.../anthropic/anthropic.go](https://github.com/trufflesecurity/trufflehog/blob/main/pkg/detectors/anthropic/anthropic.go).

---

## 2. Энтропия против префиксов

**Строгого количественного бенчмарка не найдено нигде** — ни в README всех трёх
инструментов, ни в их issue-трекерах, ни в официальной документации GitHub/GitLab/
Slack и т.д., ни в 4 найденных научных статьях (раздел 4). Это отмечается как **[D]**
прямо, вместо того чтобы выдумывать цифру.

Косвенное качественное подтверждение из независимого академического источника:
статья arXiv:2410.23657 формулирует прямо — *«Regex and entropy based approaches
achieve high recall but poor precision, while smaller models such as RoBERTa and
CodeBERT greatly improve performance (F1 = 92.70%)»* [A, прочитано в abstract] —
но точной изолированной цифры именно для энтропии там тоже нет.

Зато есть **реальные, подтверждённые ссылками репорты** о том, что именно ломает
энтропийный детектор:

| Issue | Что сломалось | Ссылка |
|---|---|---|
| gitleaks #1830 (open) | После апгрейда v8.20.1→v8.24.3 `generic-api-key` (entropy=3.5) начал массово матчить «all kinds of plaintext variable names and placeholders» — репортер прямо цитирует конфиг с `entropy = 3.5` | [A] [gitleaks/gitleaks#1830](https://github.com/gitleaks/gitleaks/issues/1830) |
| gitleaks #1775 | Yocto/BitBake: git-commit-SHA в `SRC_URI` рядом с BitBake-синтаксисом пересекает порог энтропии `generic-api-key` | [A] [gitleaks/gitleaks#1775](https://github.com/gitleaks/gitleaks/issues/1775) |
| gitleaks #2093 (open) | `square-access-token` (префикс `EAAA`) матчит внутри base64-encoded MIME/архивных payload'ов | [A] [gitleaks/gitleaks#2093](https://github.com/gitleaks/gitleaks/issues/2093) |
| gitleaks #1837 (open) | Минифицированный JS даёт ложные срабатывания (по заголовку issue; тело не читал подробно) | [B, по заголовку] [gitleaks/gitleaks#1837](https://github.com/gitleaks/gitleaks/issues/1837) |
| detect-secrets #266 | `Base64HighEntropyString` флагует короткие YAML env-var объявления (`MONGO_INITDB_ROOT_PASSWORD_FILE=...`) как высокоэнтропийные — математика энтропии на коротких строках нестабильна | [A] [Yelp/detect-secrets#266](https://github.com/Yelp/detect-secrets/issues/266) |
| detect-secrets #250 | «High Entropy string matchers have false positives on uuids» — прямое подтверждение | [A] [Yelp/detect-secrets#250](https://github.com/Yelp/detect-secrets/issues/250) |
| detect-secrets #285 (open) | Обратный баг: «a UUID isn't detected by the high entropy string detection» — тот же механизм на том же классе входа одновременно и пере-, и недо-срабатывает в разных репортах — само по себе свидетельство хрупкости порога | [A] [Yelp/detect-secrets#285](https://github.com/Yelp/detect-secrets/issues/285) |
| trufflehog #3266 (open) | SHA-пин GitHub Action (Cloudflare) флагуется как «unverified Cloudflare secret» | [A] [trufflesecurity/trufflehog#3266](https://github.com/trufflesecurity/trufflehog/issues/3266) |
| trufflehog #4631 (open) | `DatadogToken`-детектор ложно матчит «checksums, encrypted data, and service names» | [A] [trufflesecurity/trufflehog#4631](https://github.com/trufflesecurity/trufflehog/issues/4631) |

**Вывод по конкретным классам входа**, подтверждённым выше: UUID — да, ломает (в
обе стороны); git commit SHA — да, ломает; base64-блобы/MIME — да, ломает;
минифицированный JS — вероятно (заголовок issue, не проверено глубже); хеши/чексуммы
общего вида — да (trufflehog #4631).

---

## 3. Каталог префиксов

Confidence-тег в последней колонке. «Источник» — либо официальная документация
вендора, либо конкретный файл gitleaks/trufflehog (оба — легитимный [A]-источник:
это то, что реально матчится в проде тысячами инсталляций, просто не вендором
подтверждено).

### LLM / AI-провайдеры

| Сервис | Префикс / формат | Длина | Источник |
|---|---|---|---|
| **Anthropic** | `sk-ant-api03-` + 93 симв. + `AA` (админ-ключи: `sk-ant-admin01-`) | ~108 | [A] [gitleaks.toml:150-152](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L150-L153); подтверждено официально — пример в доке Anthropic: `"partial_key_hint": "sk-ant-api03-R2D...igAA"` [A] [platform.claude.com/docs/.../admin/api_keys/retrieve](https://platform.claude.com/docs/en/api/admin/api_keys/retrieve); то же в [trufflehog/anthropic.go](https://github.com/trufflesecurity/trufflehog/blob/main/pkg/detectors/anthropic/anthropic.go) |
| **OpenAI** | `sk-proj-`/`sk-svcacct-`/`sk-admin-` + маркер `T3BlbkFJ` в середине; легаси `sk-`+20+`T3BlbkFJ`+20 | 51–164 | [A] [gitleaks.toml:2704-2706](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L2704-L2706) |
| **Google / Gemini** | `AIzaSy` + 33 симв. (Gemini-специфичный) / generic GCP: `AIza` + 35 симв. | 39 | [A] [trufflehog/googlegemini.go](https://github.com/trufflesecurity/trufflehog/blob/main/pkg/detectors/googlegemini/googlegemini.go) (живая верификация против generativelanguage API) + [A] [gitleaks.toml:612-614](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L612-L614) (generic `gcp-api-key`) |
| **Mistral** | **не подтверждено** — нет правила в gitleaks.toml, нет детектора в trufflehog (проверено: 404 на `pkg/detectors/mistral/mistral.go`), формат не указан в docs.mistral.ai quickstart | — | [D] |
| **Cohere** | НЕ фиксированный префикс — keyword-proximity: `(cohere\|CO_API_KEY)` + 40 буквенно-цифровых | 40 (только значение) | [A] [gitleaks.toml:325-327](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L325-L327); в trufflehog детектора нет вовсе |
| **HuggingFace** | `hf_` + 34 строчных латинских (орг-токен: `api_org_` + 34) | 37 / 43 | [A] [gitleaks.toml:2364-2374](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L2364-L2374) |
| **OpenRouter** | `sk-or-v1-` + 64 hex | 73 | [A] [trufflehog/openrouter.go](https://github.com/trufflesecurity/trufflehog/blob/main/pkg/detectors/openrouter/openrouter.go), верифицируется против `openrouter.ai/api/v1/key`; в gitleaks.toml правила нет |
| **DeepSeek** | `sk-` + 32 строчных буквенно-цифровых, но детектор требует рядом keyword «deepseek» (сам по себе `sk-`+32 неотличим от других форматов) | 35 | [A] [trufflehog/deepseek.go](https://github.com/trufflesecurity/trufflehog/blob/main/pkg/detectors/deepseek/deepseek.go), верифицируется против `api.deepseek.com/user/balance`; в gitleaks.toml правила нет |

### Облака

| Сервис | Префикс / формат | Длина | Источник |
|---|---|---|---|
| **AWS Access Key ID** | `AKIA`\|`ASIA`\|`ABIA`\|`ACCA`\|`A3T` + 16 симв. `[A-Z2-7]` | 20 | [A] [gitleaks.toml:206-208](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L206-L209) + официально подтверждено AWS: AKIA=access key, ASIA=temp STS key, ABIA=STS bearer token, ACCA=context-specific credential [A] [docs.aws.amazon.com/IAM/.../reference_identifiers.html](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html) |
| **AWS Secret Access Key** | **префикса нет** — непрозрачная ~40-символьная base64-подобная строка | 40 | [A] отсутствие подтверждено и в gitleaks.toml (правила нет), и в самой доке AWS (в таблице префиксов такой строки нет) — хрестоматийный случай, когда anchor-детекция физически невозможна; работает только связка с соседним AKIA/ASIA либо keyword+энтропия |
| **AWS Bedrock API key** | долгоживущий: `ABSK` + 109–269 base64 симв.; короткоживущий: строка содержит литерал `bedrock-api-key-YmVkcm9jay5hbWF6b25hd3MuY29t` | вариативно | [A] [gitleaks.toml:223-233](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L223-L233) |
| **Google Cloud service account key** | не короткий токен — JSON-файл: `{"type":"service_account","private_key":"-----BEGIN PRIVATE KEY-----...","client_email":...}` | структурный | [A] [docs.cloud.google.com/iam/docs/keys-create-delete](https://docs.cloud.google.com/iam/docs/keys-create-delete) |
| **Google Cloud API key** | `AIza` + 35 симв. | 39 | [A] [gitleaks.toml:612-614](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L612-L614) |
| **Azure AD client secret** | `[3 симв.]Q~[31–34 симв.]` (литерал `Q~` — обязательная часть маркера) | 38–40 | [A] [gitleaks.toml:237-239](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L237-L239) |

### Dev / SaaS

| Сервис | Префикс / формат | Длина | Источник |
|---|---|---|---|
| **GitHub PAT (classic)** | `ghp_` + 36 | 40 | [A] gitleaks.toml + официально: docs.github.com таблица «GitHub's token formats» [A] [docs.github.com/.../about-authentication-to-github](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github) |
| **GitHub fine-grained PAT** | `github_pat_` + 82 | 93 | [A] то же |
| **GitHub OAuth token** | `gho_` + 36 | 40 | [A] то же |
| **GitHub App user/install token** | `ghu_` / `ghs_` + 36 | 40 | [A] то же |
| **GitHub App refresh token** | `ghr_` + 36 | 40 | [A] то же |
| **GitLab PAT** | `glpat-` + 20 (легаси) или routable `glpat-[27-300].[9 симв.]` | 26+ | [A] [gitleaks.toml:2225-2237](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L2225-L2237); GitLab также имеет `glcbt-`/`gldt-`/`glffct-`/`glft-`/`glimt-`/`glagent-`/`gloas-`/`glptt-`/`glrt-` под разные типы токенов и `GR1348941` под runner registration — все [A] тот же файл |
| **Slack bot token** | `xoxb-` + цифры-цифры-буквенно-цифровые | вариативно | [A] gitleaks.toml + официально docs.slack.dev подтверждает `xoxb-`, `xoxp-`, `xapp-` и НОВЫЙ `xwfp-` (workflow-токен, которого нет в gitleaks) [A] [docs.slack.dev/authentication/tokens](https://docs.slack.dev/authentication/tokens). Важный нюанс: gitleaks дополнительно покрывает ЛЕГАСИ/недокументированные `xoxa-`/`xoxr-`/`xoxe-`/`xoxo-`/`xoxs-`, которых уже нет в актуальной официальной доке Slack |
| **Stripe secret key** | `sk_(test\|live\|prod)_` + 10-99 | вариативно | [A] gitleaks.toml + официально docs.stripe.com/keys подтверждает `sk_live_`/`sk_test_`/`pk_live_`/`pk_test_`/`rk_live_`/`rk_test_`/`sk_org_` [A] [docs.stripe.com/keys](https://docs.stripe.com/keys). **Разрыв**: regex gitleaks покрывает только `sk_`/`rk_`, publishable `pk_`-семейство НЕ покрыто вовсе (хотя это и не секрет по дизайну Stripe) |
| **Twilio API key** | `SK` + 32 hex (это именно API-Key SID; Account SID — `AC...`, Auth Token — неотличимая от AWS secret key 32-hex строка без префикса) | 34 | [A] [gitleaks.toml:3117-3121](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L3117-L3121) |
| **SendGrid** | `SG.` + 66 | 69 | [A] [gitleaks.toml:2855-2858](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L2855-L2858) |

### Приватные ключи (PEM)

| Тип | Заголовок | Источник |
|---|---|---|
| PKCS#8, незашифрованный | `-----BEGIN PRIVATE KEY-----` | [A] RFC 7468, [rfc-editor.org/rfc/rfc7468](https://www.rfc-editor.org/rfc/rfc7468) |
| PKCS#8, зашифрованный | `-----BEGIN ENCRYPTED PRIVATE KEY-----` | [A] RFC 7468 |
| RSA (PKCS#1, легаси OpenSSL) | `-----BEGIN RSA PRIVATE KEY-----` | [B] — RFC 7468 явно НЕ определяет этот заголовок (проверено чтением RFC); это де-факто конвенция OpenSSL/PKCS#1, отдельного нормативного источника не фетчил |
| EC (SEC1, легаси OpenSSL) | `-----BEGIN EC PRIVATE KEY-----` | [B] тот же статус |
| DSA (легаси OpenSSL) | `-----BEGIN DSA PRIVATE KEY-----` | [B] тот же статус |
| OpenSSH (новый формат) | `-----BEGIN OPENSSH PRIVATE KEY-----` | [B] — фетч `openssh-portable/PROTOCOL.key` не дал текстовых BEGIN/END маркеров (файл описывает только бинарный payload), общеизвестный факт не переподтверждён напрямую в этой сессии |
| OpenPGP | `-----BEGIN PGP PRIVATE KEY BLOCK-----` | [B] — RFC 4880 §6.2 (ASCII Armor) не фетчил напрямую в этой сессии |
| **Практический вывод** | gitleaks не хардкодит каждый заголовок отдельно — ОДИН generic regex `(?i)-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----[\s\S-]{64,}?KEY(?: BLOCK)?-----` ловит все варианты сразу | [A] [gitleaks.toml:2787](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L2785-L2788) |

### JWT

| Структура | Формат | Источник |
|---|---|---|
| `header.payload.signature` | `ey` + 17+ base64url `.` `ey` + 17+ base64url `.` 10+ base64url (опц. `=`-паддинг); всегда начинается с `eyJ`, т.к. это base64url от `{"` | [A] regex — [gitleaks.toml:2424-2427](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L2424-L2427); общая структура специфицирована RFC 7519, но сам RFC в этой сессии не фетчился — [B] для нормативной части |

### Российские / СНГ

| Сервис | Статус | Источник |
|---|---|---|
| **Yandex Cloud API key** | community-формат `AQVN` + 35-38 симв., ВСЕГДА требует ключевое слово «yandex» рядом (не самостоятельный якорь) | [A] regex — [gitleaks.toml:3193-3196](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L3193-L3196). **Но** официальная дока Yandex Cloud этот префикс НЕ публикует — там сказано только «показываются последние шесть символов секретной части» [A] [yandex.cloud/en/docs/iam/concepts/authorization/api-key](https://yandex.cloud/en/docs/iam/concepts/authorization/api-key). Т.е. `AQVN` — это эмпирика community, не вендорское подтверждение |
| **Yandex Cloud IAM token** | `t1.` + сегменты base64url через точку (~86 симв. во 2-м сегменте) | [A] [gitleaks.toml:3187-3190](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L3187-L3190), та же оговорка про вендорское неподтверждение |
| **Yandex Cloud static access key (S3-совместимый)** | `YC` + 38 симв. | [A] [gitleaks.toml:3199-3202](https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml#L3199-L3202), та же оговорка |
| **Yandex (правило trufflehog)** | generic: keyword «yandex» + 83 буквенно-цифровых/точки, верифицируется против **dictionary.yandex.net** (legacy Yandex.Dictionary API) | [A] [trufflehog/yandex.go](https://github.com/trufflesecurity/trufflehog/blob/main/pkg/detectors/yandex/yandex.go). Важно: это ДРУГОЙ продукт Yandex, чем правила gitleaks (Cloud) — два инструмента детектируют не одно и то же под одним именем |
| **Sber GigaChat** | НЕ фиксированный формат — официальная дока прямо описывает: *«Авторизационный ключ — строка, полученная в результате кодирования в Base64 клиентского идентификатора (Client ID) и ключа (Client Secret)»*, т.е. структурно = HTTP Basic auth, без отличительного литерала | [A] явное вендорское подтверждение отсутствия формата — [developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-token](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-token) |
| **VK Cloud** | **не подтверждено** — домен `cloud.vk.com` недоступен для фетча в этой сессии (заблокирован/ошибка), правила нет ни в gitleaks, ни в trufflehog | [D] |
| **T-Bank (Tinkoff)** | **не подтверждено** — на стартовой странице `developer.tbank.ru/eacq/intro` формат ключа/TerminalKey не описан, правила нет ни в gitleaks, ни в trufflehog | [D] |

---

## 4. ML-модели

**Специализированного, реально используемого в проде ML-детектора секретов —
по сути нет как отдельного класса.** Это прямой, не смягчённый отрицательный
результат — вот на чём он основан:

**HuggingFace.** Три целевых поиска («secret detection», «api key detection»,
«credential detection») дали ровно **одну** релевантную модель:
[`fef2/ner_rus_bert-secret_detection`](https://huggingface.co/fef2/ner_rus_bert-secret_detection)
[A] — файнтюн `DeepPavlov/rubert-base-cased` на синтетических данных, для
русскоязычной NER-детекции credentials+PII. 72 загрузки в месяц, 1 лайк, автор —
физлицо, а не организация. Собственная модель-карточка честно оговаривает: цифра
recall 0.967 — это «union of NER + a deterministic regex layer, not the model
alone» [A] — т.е. даже автор этой единственной найденной модели не утверждает, что
чистый ML-слой сам по себе силён; это гибрид по собственному признанию. Свидетельств
стороннего продакшен-применения не найдено.

**Научная литература.** Через `export.arxiv.org/api/query` найдено 3 релевантные
статьи 2024–2026, и ВСЕ ТРИ — гибридные (regex вытаскивает кандидатов → ML/LLM
классифицирует настоящий секрет / не секрет), ни одна не предлагает чистый
end-to-end ML по сырому тексту:

| Статья | Метод | Результат | Источник |
|---|---|---|---|
| Rahman et al., *Secret Breach Detection in Source Code with Large Language Models* (апр. 2025) | regex-кандидаты + fine-tuned LLaMA-3.1-8B классификатор, 818 GitHub-репо | F1 = 0.9852 (бинарная классификация) | [A] [arXiv:2504.18784](https://arxiv.org/abs/2504.18784) |
| Ahmed et al., *Secret Leak Detection in Software Issue Reports using LLMs* (окт. 2024) | бенчмарк 54 148 инстансов из GitHub issues; RoBERTa/CodeBERT vs fine-tuned Qwen/LLaMA | RoBERTa F1=92.70%, лучшие LLM до F1=94.49% на бенчмарке, но только **81.6% F1 на реальной валидации** (разрыв generalization) | [A] [arXiv:2410.23657](https://arxiv.org/abs/2410.23657) |
| Baby et al., *Separating Secrets from Placeholders: Hybrid CNN-CodeBERT* (май 2026) | CodeBERT + character-level CNN, 3-классовая классификация (секрет/плейсхолдер/прочее), 9 426 сэмплов, 10 языков | MCC=0.86, macro-F1=0.90, 93% recall / 89% precision на классе «настоящий секрет», -33% high-severity алертов | [A] [arXiv:2605.31520](https://arxiv.org/abs/2605.31520) |

Статья Ahmed et al. прямо формулирует мотивацию: *«Regex and entropy based
approaches achieve high recall but poor precision»* [A, из abstract] — качественное
подтверждение тезиса раздела 2, но опять же без изолированной цифры для одной лишь
энтропии.

**Индустрия.** GitGuardian в *State of Secrets Sprawl 2025* называет отдельную
категорию детекторов «**Generic ML-certified**» наряду с rule-based/specific —
подтверждает, что ML реально работает у них в проде, но архитектура не раскрыта в
этом отчёте [B, язык маркетингового отчёта, не техническая методичка]
[gitguardian.com/state-of-secrets-sprawl-report-2025](https://www.gitguardian.com/state-of-secrets-sprawl-report-2025).

**Самое сильное подтверждение — GitHub Advanced Security.** Официальная
документация прямо, дословно: *«AI-detected secrets. Use AI to detect unstructured
secrets like passwords, or to generate regular expressions for custom patterns»*
[A] [docs.github.com/.../about-secret-scanning](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning).
Это реальная, именованная, отгруженная фича крупного вендора — но GitHub НЕ
публикует ни архитектуру, ни precision/recall, ни список поддерживаемых языков
для неё — [D] по любым конкретным цифрам качества этой конкретной фичи.

**Честный итог раздела 4:** ML-детекция секретов существует и растёт (GitHub
Advanced Security её отгружает, GitGuardian её продаёт, академические F1 высокие),
но **без единого найденного исключения** — это второй этап поверх
regex/keyword-извлечения кандидатов, никогда не замена ему. Свидетельств, что
чистый ML обгоняет якорь-по-префиксу + живую верификацию по precision для
известных провайдеров (там, где вендор даёт endpoint верификации — сетевой ответ
"да/нет" ML не переиграть), не найдено. Реальная точка приложения ML по этой
литературе — именно НЕСТРУКТУРИРОВАННЫЕ/generic секреты без фиксированного
префикса (пароли, «захардкоженный креды без формата»), то есть ровно задача
раздела 5, а не раздела 3.

---

## 5. Пароли в свободном тексте

**Механизм `detect-secrets` `KeywordDetector`** [A, файл прочитан целиком —
[detect_secrets/plugins/keyword.py](https://github.com/Yelp/detect-secrets/blob/master/detect_secrets/plugins/keyword.py)]:

DENYLIST — фиксированный кортеж из 18 записей, процитирован дословно из
исходника:

```
api_?key, auth_?key, service_?key, account_?key, db_?key, database_?key,
priv_?key, private_?key, client_?key, db_?pass, database_?pass, key_?pass,
password, passwd, pwd, secret, contraseña, contrasena
```

Единственные не-английские записи — испанское «contraseña»/«contrasena» (с
диакритикой и без). **Кириллицы в списке нет вообще** [A]. Механизм: из DENYLIST
собирается одна regex-алтернация, а дальше — семейство из ~10 «shape»-регексов
под то, как значение может идти ПОСЛЕ ключевого слова именно в СИНТАКСИСЕ КОДА:
`:=`, `:`, `=`/`==`, `.assign(...)`, стрелочные функции `=>`, обратные сравнения
(`"value" == password`). Всё это спроектировано вокруг синтаксиса присваивания в
языках программирования, а не вокруг структуры предложения естественного языка.

**Из этого прямо следует**: строка из брифа, «пароль от почты qwerty123», этим
механизмом поймана НЕ будет — ни разу: (1) «пароль» отсутствует в DENYLIST, (2)
даже гипотетический английский аналог без кавычек/`=`/`:` между словом и
значением не пройдёт ни один из shape-регексов, потому что это проза, а не код.
`detect-secrets` спроектирован как сканер секретов В ИСХОДНОМ КОДЕ; свободный
естественный текст — вне его области применения по дизайну, не по недосмотру.

**gitleaks / trufflehog — эквивалент.** Правило `generic-api-key` у gitleaks —
по сути тот же keyword-proximity механизм: ключевые слова
`access/auth/api/credential/key/password/secret/token` + регекс-коннектор в форме
оператора присваивания `(?:=|>|:{1,3}=|\|\||<=|=>|:|\?=)` + значение в
кавычках/без, entropy=3.5 как доп.гейт [A, тот же `gitleaks.toml`]. То же
допущение про синтаксис кода, та же причина не поймать свободную русскую прозу.
Отдельного «keyword-proximity в естественном языке» детектора не найдено ни у
одного из трёх инструментов.

**Единственная найденная продакшен-фича, целенаправленно бьющая именно в эту
задачу** — «unstructured secrets like passwords» — это GitHub «AI-detected
secrets» (раздел 4) [A, та же цитата из официальной доки]. Это явно ML/AI-подход,
а не regex-proximity эвристика, и, судя по формулировке доки, именно ПОТОМУ, что
regex-proximity подходы (см. выше про detect-secrets/gitleaks) не обобщаются за
пределы code-shaped синтаксиса присваивания. GitHub не публикует ни архитектуру,
ни обучающие данные, ни точность, ни список поддерживаемых языков/ключевых слов
для этой фичи — [D] по вопросу, работает ли она на русском.

**Честный итог раздела 5:** свободнотекстовая детекция пароля без формата — **не
решённая задача** ни в одном из трёх флагманских open-source инструментов.
Единственный существующий механизм (`KeywordDetector` у detect-secrets) — (а)
англо-испанский по словарю без каких-либо признаков расширяемости под другие
языки «из коробки», (б) спроектирован под синтаксис исходного кода, а не под
предложения естественного языка, и специально не поймает паттерн «пароль от X —
значение», взятый в брифе как пример. Это подтверждённый пробел, а не
осторожная формулировка.
