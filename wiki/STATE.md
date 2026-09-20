# STATE — decisions, alternatives, prices

The log of forks: **what was chosen, what was rejected, and why** — so a question
is not reopened from scratch, and when it is reopened it is with a new fact, not
a new mood. What must not break is in [INVARIANTS.md](INVARIANTS.md); where the
code lives is in [MAP.md](MAP.md); what each source document answers is in
[INDEX.md](INDEX.md).

This file supersedes `docs/decisions.md` as the decision log. The Russian entries
below are the owner's own wording, kept verbatim — a translation would risk
shifting the meaning of a decision. New entries are in English (the wiki's
language). `wiki/check.py` verifies that every `Related:` path exists.

**ADR format.** Each entry: an id (`D-NNN`), a date, a one-line title, then
**Status** (active / open / superseded by X / narrowed by X), **Context** (the
problem and the facts that constrained it), **Options** (what was on the table),
**Decision** (what was chosen), **Price** (what it costs, when a cost was named),
**Related** (the invariant it holds up, the module that implements it, the source
document). A reversed decision is not deleted — its status points at the fact
that reversed it.

**Coverage.** Part 1 lifts the ~28 forks from `docs/decisions.md`. Part 2 lifts
the load-bearing decision from each `research/` deep dive — the archive itself
stays the full argument, indexed in INDEX.md; only the decision and its price are
here. The implicit «tried X, cost Y, removed it» lessons scattered through the
engine's history live in INVARIANTS.md (the rule) with the story here only where
a fork was actually chosen between named alternatives.

---

# Part 1 — from docs/decisions.md

## Code protection and licensing

### D-001 · 2026-08-20 · Nuitka, не PyArmor Pro
**Status:** active
**Context:** Нужна защита исходника от клиента с root на своём железе; модель угроз (`docs/tz-license-packaging.md` §3.4): заказчик **может** видеть арендованный бандл, но **не должен** видеть исходник.
**Options:** (a) PyArmor Pro ($89 разово) — срок как дата в бинарнике, привязка к MAC/диску, отзыв офлайновым `.rkey`, «Pro 9.x не работает в CI»; (b) Nuitka + серверная аренда.
**Decision:** Nuitka. **Каждая строка, где PyArmor выигрывает, у нас закрыта лицензионным сервером и закрыта сильнее**: живая аренда с TTL и лестницей `LEASED → STALE → EXPIRED` вместо вшитой даты; бандл запечатан на процессную пару X25519 в памяти вместо привязки к железу; отзыв минует grace и действует за секунды. Купив PyArmor, мы заменили бы серверную лицензию офлайновой — более слабой.
**Price:** Nuitka-сборка, Debian-пин, три build-шага; доказывается гейтами P1–P2 на настоящем образе.
**Related:** INVARIANTS.md#lease · `prototype/Dockerfile.nuitka` · `research/2026-09-01-antitamper-nuitka.md` · `docs/tz-license-packaging.md`

### D-002 · 2026-08-20 · Подписывается дайджест, а не тег; подпись — после гейтов
**Status:** active
**Context:** Релизный пайплайн должен доказывать, что клиент скачает именно проверенные байты.
**Options:** подпись тега (изменяем, ничего не говорит о байтах) · подпись дайджеста образа после гейтов.
**Decision:** Подписывается дайджест; порядок в `.github/workflows/release.yml` обратный обычному намеренно — «подписано» означает «доказано», а не «собралось».
**Price:** подпись только после ~15-минутной батареи гейтов.
**Related:** `.github/workflows/release.yml` · MAP.md §7.2

### D-003 · ~~2026-09-08 · Офлайн-лицензии НЕТ, и из юрпакета её надо убрать~~
**Status:** narrowed by D-004 (2026-09-18) — верна для своего объекта («вшитая дата в бинарнике»), не покрывает лицензию-аренду по файлу
**Context:** EULA, SLA и Order Form обещали офлайн-режим, которого в продукте не было: контейнеру нужен исходящий HTTPS, без связи он живёт на резерве (`RESERVE_MAX`), потом маскирование останавливается — и это покрывает НАШ простой, а не изолированный контур.
**Options:** (a) написать механизм к релизу — вшитая дата в бинарнике, ровно то, что отвергнуто в D-001; (b) вычеркнуть пункты из документов.
**Decision:** (b). Расхождение закрывается со стороны документов; клиенту с изолированным контуром — отдельные условия. 48-часовой льготный период при нашей недоступности остаётся в SLA как льгота при простое лицензиара, а не как офлайн-режим.
**Price:** сегмент с закрытым исходящим HTTPS не обслуживается.
**Related:** D-004 · INVARIANTS.md#lease · `docs/tz-license-packaging.md`

### D-004 · 2026-09-18 · Офлайн-лицензия НА СРОК — да; запись 08.09 сужена до своего объекта
**Status:** active (design; O1–O15 not built)
**Context:** После `docs/tz-tuning-in-lease.md` активов в бинаре нет вовсе: лицензия **и есть** payload, без неё детектировать нечем. Все три свойства, за которые 08.09 отвергла офлайн (булева проверка снимается NOP, активы в образе, продление выкаткой), **следуют из того, ГДЕ ЛЕЖАТ АКТИВЫ, а не из слова «офлайн»**. Офлайн стал свойством транспорта, а транспорт несущим не был никогда.
**Options:** локальная проверка как механизм (отвергнуто, D-003) · офлайн как транспорт того же арендуемого payload (принято).
**Decision:** Продавать предоплаченную лицензию на 6/12 месяцев, работающую без единого обращения к нам, как второй SKU рядом с арендой. Принято вслух: **отзыва нет** (рычаг — срок плюс необязательный `POST /v1/attest`); **часы клиента — его часы** (роллбэк внутри файла без TPM не закрывается; на продлении срок считает наша сторона `max(issued_now, previous_expires_at) + term`); **дрейф бандла заменён на атрибуцию** — canary, Tardos и `_wm` уже вшиваются `licensing/pack.py` в тот же payload.
**Price:** Коэффициент к аренде в цене тарифа, не оптимизируется. Правки EULA/SLA/лендинга — **после** зелёных гейтов O1–O15.
**Related:** D-003 · `docs/tz-offline-license.md` · INVARIANTS.md#lease · `prototype/licensing/pack.py`

## What counts as personal data

### D-005 · 2026-08-20 · Роль сообщения — неверное основание. Провенанс — свидетельство, не правило
**Status:** active
**Context:** Предложение «системный промпт не маскируем».
**Options:** маскировать по роли сообщения (отвергнуто) · провенанс как вес в `prototype/pseudex/context.py` (принято).
**Decision:** Роль ошибается в обе стороны, обе подтверждены первоисточниками: данные юрлица не ПД **даже в реплике клиента** (GDPR Recital 14, 152-ФЗ через определение субъекта как физлица); данные человека — ПД **даже в системном промпте** (WP29 Opinion 4/2007, тест «содержание / цель / результат» альтернативный). Происхождение значения даёт **вес** в пользу организации и складывается с сигналами `prototype/pseudex/context.py`; права не проверять оно не даёт. Ловушка: у ИП рабочий адрес часто и есть домашний.
**Price:** системный промпт детектируется каждый раз (кэш снимает стоимость повторов).
**Related:** INVARIANTS.md#collisions (роль не дискриминатор) · `research/2026-08-19-provenance-linking-noise.md` · `prototype/pseudex/context.py`

### D-006 · 2026-08-20 · ОГРН не маскируем, ОГРНИП маскируем
**Status:** active
**Context:** `validate_ogrn` знал обе длины всегда; ОГРН маскировался.
**Options:** маскировать оба · различать по длине.
**Decision:** 13 цифр — юрлицо, у него нет субъекта данных; 15 цифр — ИП, физлицо. Маскирование ОГРН было не осторожностью, а поломкой: агент, ищущий контрагента, получал фейковый номер и не находил ничего.
**Price:** ноль — колонка «ВСЕГО (по закону)» в `bench/eval_piibench.py` не сдвинулась: правовая позиция уже была в приборе.
**Related:** INVARIANTS.md#structured-ids · `prototype/pseudex/ru_pii.py` · `prototype/bench/eval_piibench.py`

## Comparison and linking

### D-007 · 2026-08-20 · Область связывания — разговор, и это предпосылка, а не предосторожность
**Status:** active
**Context:** Короткое упоминание («Ленина 14») должно связываться с полным адресом. Эта улица и дом есть в каждом русском городе.
**Options:** (a) покомпонентная подмена город→фейк, улица→фейк, дом→фейк — prefix-preserving; Xu et al. (ICNP 2002): раскрывает общий префикс при компрометации одного элемента и **по построению** склеит «Ленина 14» в Москве и в Казани; (b) область арендатора — правило единственного кандидата находит десяток владельцев и отказывает **всегда**, оно там не осторожно, оно мертво; (c) нечёткое сопоставление на прямом пути — Eder et al.: «Lena» и «Lina» различаются одной буквой; (d) область разговора.
**Decision:** (d). Одно изменение даёт и смысл, и безопасность. Средний исход Фэллеги–Сантера («возможная связь, передать человеку») схлопнут в отказ — человека у шлюза нет.
**Price:** identity churn при обрезке транскрипта без явного `conversation_id`; память агента — эхо из другого диалога (INVARIANTS.md#conversation-scope).
**Related:** INVARIANTS.md#conversation-scope · `prototype/pseudex/vault.py` (`for_conversation`) · `research/2026-08-19-provenance-linking-noise.md`

### D-008 · 2026-08-20 · Вызовы инструментов в потоке буферизуются
**Status:** active
**Context:** Внутри JSON-строки нельзя отдать ничего до её закрытия: экранирование зависит от значения целиком, а отданный префикс не вернёшь. Замерено: через `/unmask_chunk` — `{"company":"ООО "Заря""}` JSON сломан; через `/unmask_arguments` — ок.
**Options:** отдавать до последнего **закрытого** листа (аргументы короткие, выигрыш крошечный, сложность настоящая) · буферизовать целиком.
**Decision:** Буферизовать. Прокси-лег сделал тот же выбор (`_stream_as_single`); расхождение двух половин продукта было бы хуже любого выигрыша.
**Price:** плавность стрима на tool call.
**Related:** INVARIANTS.md#streaming · FLOWS.md §3 · `prototype/test_perf_masking.py`

## Operations

### D-009 · 2026-08-20 · Живость и тревога разделены по кодам ответа
**Status:** active
**Options:** «пусть `/health` падает при деградации» (отвергнуто) · `/health` 200 пока обслуживает, `/license` 503 пока не `leased`.
**Decision:** Разделить. Падающий healthcheck — активный вред: grace существует, чтобы работающий шлюз пережил **наш** сбой, а оркестратор перезапустит контейнер, которому понадобится свежий лиз — тот самый, которого нет. Переживаемый сбой превратился бы в невосстановимый.
**Related:** INVARIANTS.md#lease · `prototype/pseudex/service.py`

### D-010 · 2026-08-20 · Том клиента не бэкапим мы — но говорим об этом в онбординге
**Status:** active
**Context:** `pseudex-data` — единственный носитель соответствия между подменами в CRM клиента и настоящими значениями. Потеря = строки без обратного пути, и мы их не восстановим.
**Decision:** Мы туда не ходим: его контур, его данные, односторонняя связь делает нас необработчиком. Инструкция — в шаге 7 онбординга, единственном документе, который клиент читает.
**Related:** D-014 · `storefront/billing/onboarding.py`

### D-011 · 2026-08-20 · Ошибка провайдера — 502 с именем хоста
**Status:** active
**Context:** Самая дорогая находка прогона персон на стороне лицензии.
**Decision:** Не 500: запрос в порядке и мы в порядке, не в порядке апстрим. Хост **называется** — «не удалось связаться» без имени не кладётся ни в правило файрвола, ни в поисковую строку. В потоке код менять поздно, ошибка приходит SSE-событием — иначе клиент получает обрезанный поток за уже отданным 200.
**Related:** `prototype/pseudex/proxy.py` · `e2e-personas/findings/`

## Vault encryption

### D-012 · 2026-08-20 · SQLCipher. Решение «отложено» от 16.08 отменено — оно стояло на ошибке
**Status:** active (supersedes the 2026-08-16 deferral)
**Context:** `docs/tz-vault-encryption.md` §3 отверг SQLCipher как «не собранный под нашу платформу» — проверялся пакет `sqlcipher3-binary` (7 колёс), а вывод сделан про `sqlcipher3` (77 колёс, включая наши, опубликованные 07.01.2026). Проверено скачиванием.
**Options:** схема §4 (AES-GCM + HMAC по колонкам) — **несовместима с нашим `PRIMARY KEY (customer, canonical)`** (усечённый blind index намеренно даёт коллизии, уникальность их запрещает), дороже в 3–4 раза (~30 стейтментов, 3 PK, 3 JOIN, 6 миграций, где ошибка — тихая подстановка не того человека) · SQLCipher.
**Decision:** SQLCipher. Попутно: `digits10` и `name_key` — сигнатуры **фейка**, не ПД; настоящие ПД в `name_parts`, `place_parts`, `canonical_fold`. `PRAGMA key` нельзя передать параметром — ключ валидируется как ровно 64 hex до подстановки; `sqlcipher3.IntegrityError` не подкласс stdlib — затронуты пять обработчиков.
**Price:** 2 дня минимум, 4–5 «под МФО». Дверь не односторонняя — роль `decrypt` те же ~20 строк.
**Related:** INVARIANTS.md#storage · `docs/tz-vault-encryption.md` · `prototype/pseudex/sqlite_setup.py`

### D-013 · 2026-08-20 · Ключ шифрования — у клиента, никогда у нас
**Status:** active
**Options:** выдача ключа нашим сервером лицензий (механизм есть, соблазн понятен) · `PSEUDEX_VAULT_KEY` → `_KEY_FILE` → `_KEY_CMD`.
**Decision:** У клиента. `_KEY_CMD` (stdout любой команды, ~15 строк) закрывает Yandex KMS, HashiCorp Vault и любой секрет-менеджер без единой интеграции с нашей стороны. Выдача нами **меняет нашу роль**: мы становимся стороной, способной расшифровать ПД граждан РФ, наш простой — их неработающим волтом, юридически это обработка по поручению.
**Related:** INVARIANTS.md#storage · `prototype/pseudex/vault_key.py`

### D-014 · 2026-08-20 · Гейт обязан грепать ВЕСЬ том, а не файл базы
**Status:** active
**Context:** Настоящие ПД лежат не в `vault.db`, а в `vault.db-wal` до контрольной точки — проверено на живом волте: в `vault.db` совпадений ноль, в `-wal` есть и телефон, и имя.
**Decision:** Гейт, смотрящий на один файл, прошёл бы на незашифрованном волте. Отсюда обязательный `PRAGMA wal_checkpoint(TRUNCATE)` первым шагом миграции.
**Related:** INVARIANTS.md#storage · INVARIANTS.md#instruments · `prototype/e2e/gates.py`

### D-015 · 2026-08-20 · Фолбэка на stdlib `sqlite3` не будет
**Status:** active
**Decision:** `sqlite3` на `PRAGMA key` не поднимает ошибку и пишет открытый текст. `try: import sqlcipher3 / except ImportError: import sqlite3` — продукт, который заявляет шифрование и молча его не делает. Доказать отсутствие фолбэка может только гейт.
**Related:** INVARIANTS.md#engine-wide · `prototype/e2e/pack_gates.py` (P9)

### D-016 · 2026-08-29 · Реализовано: три решения, которых в плане не было
**Status:** active
**Decision (1):** `PSEUDEX_VAULT_ENCRYPTION` — три режима, пустая строка = `auto`: `${VAR:-}` в compose и env без значения в k8s приходят пустой строкой, трактовка её как ошибки не подняла стенд вовсе. `required` НЕ удовлетворяется сгенерированным ключом — иначе потерянный `_KEY_CMD` тихо деградирует в ключ внутри защищаемого тома.
**Decision (2):** Волт открывается ПЕРВЫМ, до остальных хранилищ: неверный ключ давал контейнер, который стартовал, отвечал «здоров» и падал 500 на первом настоящем сообщении. `entrypoint.sh` гоняет `PSEUDEX_ROLE=probe` до воркеров — один неверный ключ даёт одно сообщение, а не N.
**Decision (3):** Своя база лицензий НЕ шифруется: ПД в ней нет, а шифрование сломало бы `deploy/backup.sh` и еженедельные учения. Записано в `licensing/Dockerfile` рядом с `off`.
**Related:** INVARIANTS.md#storage · FLOWS.md §6 · `prototype/entrypoint.sh`

### D-017 · 2026-08-29 · Учения открывают копию тем же кодом, что и продукт
**Status:** active
**Context:** Хостовый `sqlite3` не умеет SQLCipher; при его отсутствии учения деградировали до проверки ЗАГОЛОВКА; второе место, знающее как открыть хранилище — второе место, которое надо держать равным первому. Попутно: `deploy/backup.sh` работал в `postgres:17-alpine`, где `sqlite3` нет — ветка `.backup` не выполнялась НИ РАЗУ, каждая ночная копия базы лицензий была `cp` живой WAL-базы, сторож смотрел только на возраст файла.
**Decision:** Проверка строк переехала в `licensing/verify.py` через `pseudex.sqlite_setup.connect_readonly`; бэкап получил свой образ (`deploy/Dockerfile.backup`) с инструментами внутри.
**Related:** `prototype/licensing/verify.py` · `deploy/restore-drill.sh` · `deploy/Dockerfile.backup`

### D-018 · 2026-08-20 · ГОСТ — ВОПРОС ОТКРЫТ, решением не является
**Status:** open (to a lawyer)
**Context:** Здесь была запись «ГОСТ не требуется» с цепочкой цитат — снята: исследователь правовой раздел по первоисточникам не проверял. Ни ФЗ-152 ст. 19, ни ПП-1119, ни приказы ФСТЭК №21 / ФСБ №378 / РКН №140 никем из нас не прочитаны.
**Decision (what we may say):** «AES-256, ключ у вас, мы его не видим». **Нельзя** до юриста: «соответствует требованиям», «сертифицировано», «закрывает 152-ФЗ». **Не делать в любом случае:** называть наш AES «СКЗИ» и мерой по ст. 19 — добровольный вход в режим приказа №378 и ПКЗ-2005.
**Open:** ПП РФ №313 лицензирует разработку и распространение шифровальных средств; образ везёт `pyrage` (X25519 + ChaCha20-Poly1305) и `cryptography`. **Урок методики:** отчёт агента с пометкой [A] — не доказательство; различать по тому, ЧТО именно было запущено.
**Related:** `research/2026-09-14-legal-launch-audit.md` · `docs/rkn-notification.md`

## Infrastructure and DevOps

### D-019 · 2026-08-20 · Домен регистрируется на владельца лично и НЕ у того, у кого VPS
**Status:** active (domain done — see memory `launch-state-2026-09`)
**Decision:** С 1 сентября 2026 для `.ru/.рф/.su` обязательна идентификация через ЕСИА. Регистратор отдельно от хостера: спор с одной конторой не должен отнимать и машину, и домен. Один домен закрывает и витрину, и `license.`. **Имя выбирается один раз** — адрес сервера лицензий вшивается в образ и попадает в белые списки клиентов.
**Related:** `research/2026-08-15-hosting-domain.md` · `deploy/check-dns.sh`

### D-020 · 2026-08-20 · Корпуса живут в `~/.cache/pseudex-bench`, не в `/tmp`
**Status:** active
**Decision:** `/tmp` чистится при перезагрузке и дважды унёс NEREL.
**Related:** MAP.md §4

### D-021 · 2026-08-20 · Хост забирает выкатку сам, CI внутрь не заходит
**Status:** active
**Options:** GitHub Actions заходит по SSH (долгоживущий ключ в GitHub с root на боевой машине + открытый входящий SSH) · pull-модель.
**Decision:** Pull. Источник правды — тег в git, из него же берётся compose-файл. Откат — `PSEUDEX_PIN` в `.env`, он же выключает автовыкатку. Агент **проверяет подпись до того, как что-либо остановить**, и **откатывается сам** — разница между «автономно» и «автоматически».
**Related:** `deploy/agent.sh` · `deploy/systemd/pseudex-agent.timer` · `research/2026-09-14-devops-audit.md`

### D-022 · 2026-08-20 · Наши образы собираются в CI, а не на хосте
**Status:** active
**Context:** Были `build:` в compose — `docker compose build` на боевой машине, и ничто не доказывает, что крутится то, что прошло гейты.
**Decision:** Сборка и подпись в CI; агент проверяет подпись, значит компрометация реестра не становится компрометацией продакшена.
**Related:** D-002 · `.github/workflows/release.yml` · `deploy/compose.yml`

### D-023 · 2026-08-20 · Тревоги в Telegram, на смену состояния
**Status:** active
**Decision:** Канал один на всё (выкатка, сторож, учения, внешняя проверка) — два канала это два места, куда забудут посмотреть. **Тревога на переход, а не на каждый обход**; отбой шлётся тоже. В тревогу не попадают логи и тела ответов — там ПД клиентов.
**Related:** `deploy/notify.sh` · `deploy/watch.sh` · `deploy/alerts.yml`

### D-024 · 2026-08-29 · Поддержка в Telegram с первого дня, и это ОТДЕЛЬНЫЙ бот от ops
**Status:** active (reverses «почта единственным каналом»)
**Context:** Снято владельцем как решение без учёта рынка: в СНГ B2B-поддержка живёт в Telegram.
**Decision:** Support-бот отдельно от ops-бота — требования к видимости противоположны и область компрометации разная (один токен на оба означает, что разговорная поверхность отдаёт канал тревог). Через поддержку клиент неизбежно пришлёт настоящие ПД, поэтому бот первым сообщением просит **токен и время, а не значение** — по ним операторский интерфейс находит событие, значение клиент смотрит у себя через `/reveal`.
**Related:** `deploy/supportbot/` · INVARIANTS.md#audit

### D-025 · 2026-08-20 · Внешняя проверка живёт в GitHub Actions
**Status:** active
**Decision:** Сторож на хосте не видит собственной смерти; платный мониторинг отвергнут — GitHub уже есть, живёт не у нас, стоит ноль. Внутренняя проверка видит «процесс жив», внешняя — «машина жива».
**Related:** `.github/workflows/uptime.yml` · `deploy/watch.sh`

### D-026 · 2026-08-20 · Учения по восстановлению идут сами, раз в неделю
**Status:** active
**Decision:** Свежесть и восстановимость — разные утверждения, разница обнаруживается ровно один раз. Проверяется «таблицы непустые», а не «файл читается»: оборванный дамп читается прекрасно.
**Related:** D-017 · `deploy/restore-drill.sh` · `.github/workflows/backup-audit.yml`

## Detection quality

### D-027 · 2026-08-29 · Планка качества детекции для релиза, и почему она в покрытии
**Status:** active (gate for release)
**Context:** Владелец: «нам нельзя релизиться с текущим качеством». Голосовой канал был нулём: семь расшифровок звонков — ноль спанов.
**Options:** мерить полнотой (отвергнуто — «Кзнецов Дмитрий», найденное как «Дмитрий», засчитывается в полноту, пока фамилия уходит открытой) · покрытием на метаморфных отношениях.
**Decision:** **95% покрытия на каждом метаморфном отношении, для LOC и NAME**, плюс два условия: `test_overmasking.py` 100%, точность на NEREL не ниже 99%. На 29.08: маркер сокращённый 99%, «№» 100%, прописью 69%, строчные 86/79%, одна опечатка 70/76% — четыре клетки ниже порога. Порядок: адреса, потом имена.
**Price:** релиз ждёт четыре клетки.
**Related:** `prototype/bench/eval_metamorphic.py` · INVARIANTS.md#instruments · `prototype/test_overmasking.py`

## Open questions (from decisions.md)
- Провайдер VPS — выбирает владелец; стенд провайдер-агностичен.
- ПП РФ №313 — к юристу (D-018).
- `docs/idea.md:69` ссылается на ст. 13.1 неверно: она про выгрузку в ГИС Минцифры.

## Research 2026-08-15

### D-028 · 2026-08-15 · Domain and hosting for launch
**Status:** active (domain/hosting done in Sept 2026)
**Context:** Launch needs a domain and one Moscow box for the licensing server + storefront; the RKN hosting-provider registry could not be checked (403/404).
**Options:** Timeweb MSK 50 (972 ₽/mo yearly, 50 GB, backups paid) vs Beget 2/4/40 (1 004 ₽/mo, 40 GB, backups «every few days», FSTEC attestation); managed Postgres vs compose on the box; HA for licensing.
**Decision:** Timeweb MSK 50 — the 10 GB of disk decide it (the box is also the build machine; a full disk stops the licensing server, the one failure that stops every customer). Postgres stays in compose; no HA at start. `pseudex.ru` was found taken (reg.ru, private person — likely the owner's); fallback `pdgate.ru`. Registrar = Timeweb. The licensing DNS record must NOT be proxied through Cloudflare.
**Price:** ≈1 100–1 300 ₽/mo at start, ≈2 100–2 400 at ~20 customers.
**Related:** D-019 · `research/2026-08-15-hosting-domain.md` · `deploy/bootstrap.sh`

### D-029 · 2026-08-15 · Three integration levels, and we do NOT write a normalisation layer
**Status:** active
**Context:** How to intercept all outgoing LLM traffic with minimum customer effort; is «zero configuration» possible. Nine products (LiteLLM, Portkey, Helicone, Cloudflare AI GW, Kong, Envoy, Arch, Langfuse, OpenRouter) all require changing the base URL; none documents `HTTPS_PROXY` or CA install. Transparent interception was built and driven with a real streaming tool call — it works, at the price of a CA in every runtime's trust store.
**Options:** adapters for six providers (rejected: LiteLLM under MIT already covers 137; our value is masking, not routing) · three levels ordered by customer cost.
**Decision:** Level 1 — the customer already has a gateway: our sidecar `/mask` + `/unmask` in one callback (the most mature code). Level 2 — no gateway: OpenAI-compatible endpoint, one env var (`pseudex/proxy.py`, tool calls buffered by design). Level 3 — config cannot be changed: `HTTPS_PROXY` + our CA, sold as «mode for closed systems», never as the main path; intercept ONLY the LLM host list, never globally (breaks pip/npm); never touch ГОСТ-TLS (the device becomes an СКЗИ). No Anthropic/Gemini adapters; the one exception is YandexGPT (not in LiteLLM, RU-relevant).
**Price:** three proxy-mode defects found and fixed (relative `tenants.db` path etc. — `docs/known-issues.md` §3).
**Related:** MAP.md §1.4 · `docs/integration.md` · `docs/integration-diva-litellm.md` · `research/2026-08-15-llm-traffic-interception.md`

### D-030 · 2026-08-15 · The market claim is false as stated and true narrowly; the tier ladder was inoperative
**Status:** active (pricing reworked → INVARIANTS.md#billing)
**Context:** Reversible masking in front of an LLM is a commodity in Russia (≥6 reachable products, one free — LiteLLM + Presidio, one bundled — KodikRouter +10%; an anti-malware.ru review of 29.07.2026 names eleven vendors, zero public prices). Nobody documents substituting the REAL value back into a tool-call argument — that is the differentiator, and AppSec.AIGate has tool-call inspection on its roadmap for Q3–Q4 2026.
**Options:** meter by requests vs protected values; flat fee + declining unit price; publish prices vs not.
**Decision:** Position on tool-call substitution (a write operation in the execution path), publish prices, fix the ladder: the overage rate 0.40 ₽/1000 was 50–242× cheaper than the in-tier price, so nobody would ever upgrade. The metering unit later became the REQUEST (see INVARIANTS.md#audit, INVARIANTS.md#billing), not protected values as this report suggested.
**Price:** the window is two to four quarters and it is a distribution race, not an engineering one.
**Related:** `research/2026-08-15-ru-market-billing.md` · `research/2026-09-08-rynok-i-cena.md` · `docs/billing-integrity.md` · INVARIANTS.md#billing

---

# Part 2 — from research/

Each deep dive in `research/` ends in a recommendation; this lifts the one that
became a decision. The number grade the researchers used ([A] read in a primary
source, [B] single unverified source, [C] asserted, [D] folklore) is not repeated
here — read the source document (INDEX.md points to it) for the evidence behind
any claim.

### D-031 · 2026-08-16 · ЮKassa stays; the payment instrument for a legal entity is the invoice, not the card
**Status:** active
**Context:** Cheque of 19–49k ₽ to a legal entity. Open web search was down; forum sentiment (vc.ru, banki.ru) was NOT collected — the recommendation rests on vendor behaviour, not opinions.
**Options:** switch provider (no evidence to) · keep ЮKassa, add invoice-by-transfer.
**Decision:** Do not change provider — no verified evidence any alternative is better, and the one hard criticism of a competitor (Tinkoff) was three years stale. Change the INSTRUMENT: the main path for a legal entity is a bank-transfer invoice (confirmed by Yandex Cloud and amoCRM behaviour), saving the ~3.8% acquiring fee and the fiscal loop; ЮKassa stays for ИП, micro-teams, trials, overage. Т-Касса only if we open a Т-Бизнес account anyway.
**Price:** fix the webhook race (`select_for_update` / unique index on `Invoice.payment_ref`); add an «invoice issued, awaiting payment order» state with manual reconciliation.
**Related:** `research/2026-08-15-ru-payments.md` · `storefront/billing/payments.py` · `storefront/billing/reconcile.py` · `docs/payment-provider-request.md`

### D-032 · 2026-08-16 · pymorphy3 is the only morphology core, and never `parse(w)[0]`
**Status:** active
**Context:** Grammatically disagreeing fake ФИО were «fixed» by the model, and the fixed token stopped resolving in the vault — a non-existent person reached the tool. Three persona-customers hit it independently.
**Options:** petrovich (two port bugs, PyPI data stale, last release 2020, does NOT detect gender — `gender=None` means «don't filter rules», not «detect») · natasha (cannot inflect at all; `normalize()` is lemmatisation, no inverse) · pymorphy2 (does not run on 3.12) · pymorphy3.
**Decision:** pymorphy3 only. The first parse of a name is regularly the wrong part of speech — never take `parse(w)[0]`.
**Related:** INVARIANTS.md#names · INVARIANTS.md#name-morphology · `prototype/pseudex/morph.py` · `research/2026-08-16-russian-name-morphology.md` · `docs/tz-name-gender-canonical.md`

### D-033 · 2026-08-16 · Credentials, if ever added, anchor on the prefix; entropy is only a secondary filter
**Status:** active (implemented in `prototype/pseudex/credentials.py`)
**Context:** Evidence base for SECRET detection (not PII); a false positive there breaks a tool call as badly as on PII.
**Options:** Shannon entropy (detect-secrets `*HighEntropyString`) — the #1 false-positive source by its own issue tracker (UUID, git SHA, base64) · prefix anchor (gitleaks: most of 222 rules are literal `sk-ant-`, `ghp_`, `AKIA`) · live verification (trufflehog network call — the only mechanism that removes false positives entirely, not statistically).
**Decision:** Prefix anchor is the dominant production approach; entropy only as an added filter over a prefix. Live verification is the strongest but out of scope for an in-perimeter gateway.
**Related:** INVARIANTS.md#credentials · `prototype/pseudex/credentials.py` · `research/2026-08-16-secrets-detection-sota.md`

### D-034 · 2026-08-16 · The detection-type surface and the landing claims are corrected to what the engine proves
**Status:** active
**Context:** 18 types verified by probing the engine (one probe per type so a higher-priority neighbour does not swallow it). Two of six research branches (medicine, RU market size) did not return and are deliberately absent.
**Decision:** Landing: «23 types» → 18 with the list published; replace «libraries tuned for English» with the checkable claim that none of nine world solutions validate ИНН/СНИЛС by checksum and Google DLP has one Russia type; do NOT claim «we alone understand Russian» (two of nine do). Industry law (ТК гл. 14, страховая/банковская/образовательная тайна) names PII types beyond ФИО/phone/address — a vertical backlog, not a launch blocker.
**Related:** `research/2026-08-16-vertical-pii-registry.md` · `research/2026-08-16-industry-pii-hr-insurance-legal.md` · `storefront/storefront_web/detection_types.py` · `docs/tz-verticals-and-configurator.md`

### D-035 · 2026-08-31 · No ML model for detection; rules + one product decision close the gap
**Status:** active
**Context:** Owner: is an ML model needed for 95% recall+precision on third-party data. Precision is already >95% everywhere; the binding constraint is RECALL, worst 78.4% (later 68.0%) on MASSIVE.
**Options:** (a) a learned context GATE over dictionary candidates (the previous research's proposal) — reaches at most 10% of the shortfall on third-party data; the other 90% is structurally out of reach because the candidate is never born; (b) rules + a public-figures decision.
**Decision:** No model. Rules in one day gave +10.9pp LOC coverage and +2.0pp name recall on a third-party corpus and closed a defect class no instrument saw. Order: (1) decide public figures — zero code, moves recall 78.4% → ≥86.2%, needs a lawyer not an engineer; (2) close the remaining coverage misses; (3) a leased ambiguous-word list; (4) only THEN a learned gate, knowing it buys a tenth of the shortfall and risks precision that has no headroom. Two method bans: don't compare before/after with two independent NEREL precision estimates (measures noise at 0.73pp CI width — use paired McNemar); don't report «100% on clean prose» as proof of the 99.4% budget.
**Related:** INVARIANTS.md#names · INVARIANTS.md#instruments · `research/2026-08-31-ml-gate-or-rules.md` · `research/2026-08-31-context-gate-over-pii-candidates.md` · `prototype/bench/gate/`

### D-036 · 2026-08-31 · Billing meter is signed prepaid capacity granted by the server, not client self-report
**Status:** active
**Context:** The counter runs on hardware a hostile client owns; can under-reporting be made structurally impossible.
**Options:** trust client self-report (defeatable) · signed prepaid quanta + short lease TTL.
**Decision:** The right inversion is not «client reports» → «client asks» but «client cannot continue without asking» — the number of grants issued is OUR record, unfalsifiable; the client can only fail to spend what was granted. Bill on `capacity_billable` derived by the server from granted capacity, clamped `[granted − quantum − reserve, granted]`; self-report is reconciliation only. Double-spend is accounting, not crypto (RFC 9578 does not cover it). Value only appears together with a short lease TTL — a grant with no forced return is just a number in memory.
**Price:** under-reporting bounded to a ~0.84% reconciliation band; a root binary patch of the meter is binary-integrity, not billing-math, bounded to one TTL window.
**Related:** INVARIANTS.md#billing · `research/2026-08-31-usage-billing-on-hostile-hardware.md` · `research/2026-09-14-pentest-client-greybox.md` · `docs/metering-integrity.md`

### D-037 · 2026-09-01 · The IP leak is the constants blob, closed by a source transform, not by heavy obfuscation
**Status:** active (superseded on the tuning by D-039)
**Context:** What a reverser actually recovers from the Nuitka binary.
**Options:** heavy obfuscation (Nuitka Commercial data-hiding, o-LLVM, VMProtect/Themida) · a pre-compile source transform.
**Decision:** The real leak is symbol names and beacon strings in the constants blob (data, not the ELF symbol table, so `strip` misses them). Extend `build_strip_docstrings.py` into a source transform that removes/moves beacon strings and neutralises qualnames BEFORE Nuitka — same pattern as docstring stripping, does not raise entropy (no EDR trigger), keeps line numbers for our support tracebacks. Heavy obfuscation does not pay: it targets the wrong leak, a public `nuitka-static-unpacker` removes Commercial constant encryption in ms, and packers are exactly what malware authors use and what the customer's EDR flags. Make the check load-bearing (no boolean branch to NOP), but its ceiling is known: a secret present in RAM of a legitimate process on the attacker's machine is extractable (white-box crypto theorem).
**Related:** INVARIANTS.md#hardening · `research/2026-09-01-antitamper-nuitka.md` · `prototype/build_harden_strings.py` · `prototype/build_mangle_names.py`

### D-038 · 2026-09-02 · The reverse path in tool calls is a benchmark and an architecture, not a hope
**Status:** active (built as AgentPII-RU v4 and the redact/agent_form/translit paths)
**Context:** Property-preserving pseudonymisation costs bits; the model writes derived forms (age, initials, transliteration, E.164) the restorer must handle.
**Decision:** Benchmark: three arms (Control, Intervention, Control′) over ONE typed mock backend, gateway effect = agreement(I,C) − agreement(C,C′), paired, cluster bootstrap, Clopper-Pearson floor printed; INV relation at three levels separately (tool-name sequence / argument-key set / typed mock state); a per-field divergence taxonomy the instrument must SHOW because the engine does not fix those classes (`derived`, `validated_refused`, `residual`). Architecture for the unrecoverable classes: coherent substitutes with a declared bit budget (region/gender/decade ≈10 bits, less than a name's format already gives); a library of derivations computed from the REAL value on our side; an opt-in agent instruction «values are opaque, copy verbatim»; a `residual`/`refused` signal outward.
**Related:** INVARIANTS.md#swap · INVARIANTS.md#derived-forms · `research/2026-09-02-agent-form-benchmark.md` · `prototype/bench/agentpii4/` · `docs/tz-agentpii4.md`

### D-039 · 2026-09-03 · Substitute checksums stay INVALID; СНИЛС has no safe valid range, and the conversation scope makes that acceptable
**Status:** active (revised 2026-09-04)
**Context:** A model told to validate checksums refuses a fake with an invalid sum and does not call the tool (v4 small: 16 of 36 `validate` triples). Substitutes are minted checksum-invalid on purpose so a fake can never be a real person's ID. For ИНН/passport/card a valid-but-impossible range exists by number structure; for СНИЛС it does NOT (≈10⁹ valid space, ~1.5·10⁸ issued → a random valid fake is someone's real number ~1 in 7; no reserved structural field).
**Decision (03.09):** СНИЛС stays checksum-invalid; the price (an agent that validates СНИЛС refuses the tool call) is measured and accepted. **Revision (04.09):** the price was the whole rest of the `validate` family, and the «1 in 7» argument holds for the WHOLE country but a substitute lives in ONE conversation — the real bearer entering ANOTHER conversation is not mistaken for our fake (`tokens.minted_in`), and does not enter the same one with a probability that does not exist. Same argument that fake names and fake streets already stand on. Backwards collisions (a fake equal to a value the customer already has) are refused at mint.
**Related:** INVARIANTS.md#collisions · INVARIANTS.md#conversation-scope · `research/2026-09-03-checksum-valid-substitutes.md` · `prototype/pseudex/vault.py`

### D-040 · 2026-09-05 · Substitute scope stays the conversation; a host with memory declares a customer-level id
**Status:** decided (A default + B flag) — see memory `agent-scenario-coverage`
**Context:** Agent memory, `fork` and per-session handoff all key by CUSTOMER, so injected text carries a substitute from an earlier dialogue; judged at conversation scope it is masked a second time and the tool gets the first dialogue's fake.
**Options:** (A) host gives a stable customer-level id when memory is on (user id = `conversation_id`) — zero engine change, single-candidate rule then runs over that user's whole traffic (still small for one person); (B) `scope=customer` for `is_minted_token` — reintroduces the direct collision measured at 2–3 per 2979 on NEREL; (C) host tags memory blocks (precise, hardest for the integrator).
**Decision:** A by default with a documented host requirement, B as an explicit flag (`pseudonym_scope` / `PSEUDEX_PSEUDONYM_SCOPE`), verified by the v4 `memory` family in both configurations. Do NOT extend `validate` (no primary source verifies by DOB/passport). Do NOT add domains for their own sake — new FLOWS matter more than new signboards; the tool surfaces are the same five (key/text/template/batch/receipt).
**Related:** INVARIANTS.md#conversation-scope · `research/2026-09-05-agent-scenario-coverage.md` · `prototype/test_collisions.py`

### D-041 · 2026-09-06/07 · The equivalence claim needs TOST, and the benchmark is stress-tested by seven critics
**Status:** active
**Context:** The product's promise is that the gateway does NOT change the agent's behaviour — an equivalence claim; a non-significant McNemar does not show it. Seven critic lenses ran against v4; 5 of 35 findings survived adversarial refutation.
**Decision:** Publish a TOST verdict at a pre-declared margin (δ=3pp), one margin per level, from a cluster bootstrap (DEFF≈2.1 → error inflation √2.1≈1.45×); the interval form is exact and reuses the same bootstrap; resolution floor 1/n. Fix the four defects the critics found: the vacuous-triple pass (`not any([])`), the dead `FieldSpec.required`, no «did the arm act» level, over-masking measured by nothing. Read the CALL level before the field level. Don't build a synthetic «null agent» harness (a `calls=()` arm already fails four of five levels).
**Related:** INVARIANTS.md#instruments · `research/2026-09-06-benchmark-tiers.md` · `research/2026-09-07-benchmark-critics.md` · `prototype/bench/agentpii4/stats.py`

### D-042 · 2026-09-08 · Reversibility is NOT our novelty; tool-call value substitution is, and the window is a distribution race
**Status:** active
**Context:** Owner: «from the market, not from memory». The first framing («we do the reverse leg, which nobody does») was taken from a competitor's own comparison page and is wrong — reversibility is offered by Grepture, GPTunneL, KodikRouter, Presidio, Skyflow, Protecto.
**Decision:** Do not sell reversibility as new. The differentiator is restoring the REAL value into a tool-call ARGUMENT so the tool executes on real data — and the strongest evidence is a competitor's own paper: HiveTrace measured that pseudonymisation does not significantly hurt the agent, and stated its study «does not cover data restoration or transfer to external tools». The nearest RU competitor reached our topic, measured half, and named the other half out of scope. The window is two to four quarters and it is a distribution race.
**Related:** `research/2026-09-08-rynok-i-cena.md` · `research/2026-08-15-ru-market-billing.md` · `docs/billing-integrity.md` · MAP.md §6

### D-043 · 2026-09-14 · DevOps: architecture is right, policy is empty in three places
**Status:** active (fixes tracked in `research/2026-09-14-devops-audit.md`)
**Context:** GitHub Actions → Yandex CR → pull-agent → docker compose, audited against first sources.
**Decision:** Three empty policies to fix: (a) `cosign verify` with `identity=.*` disables the one check keyless exists for — Fulcio signs any workflow of any repo; pin the identity regex to `@refs/tags/v[0-9]+…` and verify by DIGEST not tag (a compromised registry serves another of our own signed images under the same tag); (b) the agent's rollback only fires in the first ~2s — `healthy()` passes while services are still `starting`; use `docker compose up --wait`; (c) restic `forget` without `--keep-within` is the documented attack where a compromised host makes our own CI delete real snapshots. The «negative atom needs a positive over the same source» rule (from the gate audit) carries to DevOps: P6 signs and verifies bypassing Fulcio/SCT/identity and cannot see defect (a).
**Related:** INVARIANTS.md#instruments · INVARIANTS.md#operations · `research/2026-09-14-devops-audit.md` · `deploy/agent.sh` · `.github/workflows/release.yml`

### D-044 · 2026-09-14 · Legal launch audit: two code defects block the storefront
**Status:** action items (D1, D2 fix; RKN notification pending — memory `launch-state-2026-09`)
**Context:** `storefront/` legal templates and payment code against the laws in force.
**Decision:** Two defects where the site text promises what the code does not: (D1) one checkbox for consent + policy + offer, illegal since 01.09.2025 (consent must be «separate from other documents») — split into two required checkboxes; (D2) the fiscal cheque never fires — `needs_receipt` is true only for a physical person and `kind` is never set from the UI, so every org is `company` and no cheque is sent, while ЮKassa requires a receipt in every payment. RKN notification (ст. 22) is a drafted doc, not filed — file before processing begins.
**Related:** `research/2026-09-14-legal-launch-audit.md` · `docs/rkn-notification.md` · `storefront/accounts/models.py` · `storefront/billing/payments.py`

### D-045 · 2026-09-14/15 · The binary against a root customer: money holds, the product does not, and the answer is deterrence + decay
**Status:** active (hardening implemented; the residual is an accepted boundary)
**Context:** Two pentests. Money is robust (billed on server-granted capacity, fail-closed, under-reporting bounded ~0.84%). The product is not: a root customer dumped the full tuning from RAM in ~1 second and ran a standalone detector free forever, because the tuning key was static and shared across a build's leases (A2).
**Options:** hardware TEE (excluded by «any hardware» — SGX removed from 11th-gen Core, ÆPIC/SGAxe on older, CVM puts guest-root inside the TCB; all give zero against a customer on their own machine) · software deterrence + decay.
**Decision:** You cannot make extraction IMPOSSIBLE for a root customer on their own machine (a theorem TEE does not lift here) but you can make it NON-TRIVIAL, free, in software. Implemented: tuning in the lease with an empty binary (D-039/A2 close), section-framed lease (kills the monolithic 8.8MB carve → ~13 frames ≤44KB), `mlockall` + `PR_SET_DUMPABLE=0` + core off (swap leak closed), per-customer Tardos watermark + canaries ON by default (a leak names the org), short TTL (24h, 7d ceiling) to make a captured snapshot stale. The residual (a professional instrumenting the load path and reading live RAM) is an accepted boundary that leaves an attribution trace.
**Related:** INVARIANTS.md#hardening · INVARIANTS.md#lease · `research/2026-09-14-pentest-client-greybox.md` · `research/2026-09-14-security-redteam.md` · `research/2026-09-15-ip-protection-map-and-sota.md` · `research/2026-09-15-ram-extraction-hardening.md` · `docs/tz-tuning-in-lease.md` · `docs/staleness-and-rotation.md`

### D-046 · 2026-09-17 · Prose case breaks on a gender-homographic substitute — known, unfixed, cheap
**Status:** open (known defect, NOT fixed; a same-day fix made it worse and was reverted)
**Context:** «Записать Никиту Гущина» (accusative) → substitute «Гордея Жукова»; a man's `-я/-ова` in the accusative is written exactly like a woman's name in the NOMINATIVE, and `detect_case` without a hint picks the feminine reading, so `_restore_inflected` returns the real name unchanged: «Записать Никита Гущин».
**Decision:** Left unfixed because it is cheap: the person comes back CORRECT (not a leak, not identity swap); tool-call arguments are untouched (restored verbatim via `agent_form.cased_like`); only PROSE agreement suffers. Frequency ~4% (1 in 27 local runs). Passing gender into `detect_case` was tried and made it worse — reverted.
**Related:** INVARIANTS.md#name-morphology · `research/2026-09-17-prose-case-homography.md` · `prototype/pseudex/morph_names.py` · `prototype/pseudex/redact.py`

### D-047 · 2026-09-17 · Yandex conversions go server-side, and consent is an open question that currently sends nothing
**Status:** open (neither path chosen; default sends nothing)
**Context:** Metrika/Direct need signup+activation goals. `reachGoal` is impossible: `/activate?t=…` carries a signed token and `/welcome` carries the license key in the markup, and the counter sends `location.href` — the token/key would reach Yandex even with Webvisor off.
**Decision:** Conversions go from the SERVER (`PSEUDEX_YANDEX_CONVERSIONS`, default empty; `--dry-run` works without the flag). Open: the server-side conversion ignores the visitor's consent choice (it lives in `localStorage`, never reaches the server), which contradicts the published policy §6/§9bis. Two incompatible paths — (1) carry the banner choice into the signup form and send only the consenting, or (2) rewrite the policy to name this transfer honestly — and until one is chosen, nothing is sent, which is the safe default.
**Related:** `research/2026-09-17-yandex-offline-conversions.md` · `storefront/ops/yandex_api.py` · `storefront/ops/management/commands/yandex_conversions.py`

### D-048 · foundational · Deep-dive research base (dd-notes, dd2–dd5): the recurring conclusions the engine is built on
**Status:** active (background; each dd-note is indexed in INDEX.md)
**Context:** A dozen source-grounded deep dives read before the engine's shape was fixed. They are evidence, not decisions, but the same conclusions recur and the code follows them.
**Decisions they support:** Presidio ships NO Russian recognisers and stops at text (dd-notes-2); Skyflow/proxies/MCP middleware do not put the value back in a tool call (dd-notes-1, dd-notes-3, west-pii-toolcall-sota); the detector is defense-in-depth with a precision-first disambiguation ladder, checksum-gated IDs, and Natasha + a gazetteer for RU NER (dd2-A/C/D, ru-pii-dataset-and-detectors); address is AddrExtractor ∪ regex anchors ∪ marker-less streets, and ADDRESS-as-PII is separated from PLACE-as-reference (dd2-B, dd3); quasi-identifiers are masked, not generalised, for a single real-time message (dd4-C); semi-structured KV is detected by the key typing the value (dd4-B); phone noise is defeated by offset-safe normalisation (dd4-A); FPE tokenisation + RU detection are the buildable primitives (dd-notes-4, deep-dive-detection-upgrade, deep-dive-toolcall-tokenization, frontier-architecture); monetisation is a self-hosted meter, open-core is rejected (dd5-monetization); deployment keeps data in the perimeter with minimal, language-agnostic integration (dd5-deployment).
**Related:** INVARIANTS.md#pipeline · MAP.md §1.1 · INDEX.md (research §Deep dives) · `research/dd*.md`

### D-049 · 2026-09-20 · Distribution phase: article series + a NEW public benchmark, never the private one
**Status:** active (in progress — see memory `distribution-phase-2026-09`)
**Context:** The differentiator is a feature gap with a published closing date and no distribution to convert it (D-042); the launch needs reach.
**Decision:** An article series plus a NEW public benchmark built for publication — never the private AgentPII-RU (its backup is in `~/Backups`). Owner framing rules apply. Three research docs support it: market-transparency axis, open-benchmark mechanics, RU distribution channels.
**Related:** `research/2026-09-20-market-transparency-axis.md` · `research/2026-09-20-open-benchmark-mechanics.md` · `research/2026-09-20-ru-distribution-channels.md` · memory `distribution-phase-2026-09`

### D-050 · 2026-09-20 · The customer image is publicly pullable; the four server images are not
**Status:** active
**Context:** The public benchmark tried to reproduce our row the way a reader would — released image, trial key — and the registry answered `unauthorized`. The site's `docker run` has no login step, so no customer could have started the container; nothing had ever pulled the image as a customer. The site also advertised `pseudex:1.0.0`, a tag the registry does not hold: `CUSTOMER_IMAGE` was set once by hand while the deploy agent bumped `VERSION` per release.
**Decision:** `allUsers` gets `container-registry.images.puller` on the ONE repository `pseudex` (a repository-level binding in the Yandex console, never the registry-level one — that would open `pseudex-licensing`, which carries the leased dictionaries and the tuning). The advertised image is derived from `REGISTRY`/`VERSION` in `deploy/compose.yml`; `CUSTOMER_IMAGE` remains only as a manual override. The release pipeline gates both directions with an anonymous `DOCKER_CONFIG` before signing.
**Alternative rejected:** a separate public registry for the customer image — a second registry to keep in step with the release pipeline, for no gain over a repository-level binding. Handing customers a pull token — a second secret in onboarding, and the image is designed to be in every customer's hands anyway (compiled, no source, no dictionaries; gates P1–P11).
**Price:** the compiled image is now downloadable by anyone, which changes nothing the threat model did not already accept (`docs/tz-license-packaging.md` §3.4). The prod host's `.env` still carries the stale `CUSTOMER_IMAGE` line until the owner removes it.
**Related:** INVARIANTS.md#process · `.github/workflows/release.yml` · `deploy/compose.yml` · wiki/AGENTMASK.md

### D-051 · 2026-09-20 · Two release streams from one repository: engine (`vX.Y.Z`) and platform («platform/vX.Y.Z»)
**Status:** active (ТЗ `docs/tz-release-and-versions.md`, stages 1–7)
**Context:** One tag built five images; in 12 tags the engine changed in two; `0.3.12` and `0.3.13` are one image under two numbers. The customer image and our four services have different receivers, ladders and cadence.
**Decision:** `engine` = `prototype/` minus `prototype/licensing/` → `vX.Y.Z` → image `pseudex`; `platform` = `prototype/licensing/` + `storefront/` + `deploy/` → «platform/vX.Y.Z» → the four internal images, deployed together by one agent with one `compose up`. The engine publish job is red on an empty diff of its paths.
**Alternative rejected:** five streams (the agent would reconcile four tags for nothing); one stream (status quo).
**Price:** two changelogs; a bridge release under the old scheme so the running agent learns «platform/v*».
**Related:** `research/2026-09-20-release-and-version-lifecycle.md` · D-052 · D-053

### D-052 · 2026-09-20 · release-please manifest mode, no root package, `security`/`perf`/`build` visible, `feat` → patch while 0.x
**Status:** active
**Context:** semantic-release keeps one tag stream by construction («get-tags.js», `git log` without pathspec); changesets needs «package.json» per component. release-please attributes a commit to a component by file path (`commit-split.ts`) and skips hidden types.
**Decision:** manifest mode with packages `prototype` (component `engine`, tag `vX.Y.Z`, `exclude-paths: [prototype/licensing]`) and `prototype/licensing` + `storefront` + `deploy` (component `platform`, `tag-separator: "/"`, linked). No `"."` package — it receives every commit. `security`, `perf`, `build` visible (patch); «chore/ci/docs/refactor/test/research/bench» do not bump. While `0.x`, `feat` → patch; a new minor is opened only by `Release-As: 0.Y.0` (a minor is a support cycle and a branch). A release is the merge of a Release PR; the tag is created by CI and never by hand.
**Alternative rejected:** hand-picked bump in the former «ship.yml» (the number depended on memory of the schema); semantic-release; changesets.
**Price:** a GitHub Action dependency — the CONVENTION (types, path attribution, «version.txt», tags) is tool-independent and reproducible by a 100-line script; shared files outside every path belong to nobody by design (`deploy/` is platform; `.github/` bumps nothing).
**Related:** D-051 · D-060

### D-053 · 2026-09-20 · «prototype/version.txt» is the single source of the engine version
**Status:** active
**Context:** `ENGINE_VERSION = "1.0.0"` in `prototype/pseudex/license.py` reached the licence server and the operator UI for every image ever shipped.
**Decision:** «version.txt», written into `pseudex/_release.py` by both Dockerfiles, read by `prototype/pseudex/license.py` (dev checkout: the file), reported in the lease, `/status`, the UI and `pseudexctl doctor`. Publish is red when it differs from the tag.
**Related:** D-051

### D-054 · 2026-09-20 · Versions registry «deploy/releases.json», endoflife.date-shaped, written by the engine pipeline, delivered through a platform release
**Status:** active
**Context:** endoflife.date is a static Jekyll site whose API is generated at build; hosting it for one product is Ruby for a 40-line JSON. The floor of the minimum supported version is security-relevant and must pass review.
**Decision:** `cycles[]{cycle, state, release_date, eoas, eol, eol_announced, latest{version,date,digest}, aliases}` + `notices[]`. The engine publish job runs `licensing.registry record` and commits `chore(registry): pseudex X.Y.Z` to `main` — a hidden type, so no platform Release PR opens for data (a four-image release for a JSON change would be an empty release on our side). The server and the storefront read the copy the agent syncs every minute («git show origin/main:deploy/releases.json» + `cosign verify` of the newest digest with the image identity; a file that does not parse or whose digest is unsigned never replaces the last good copy). By hand only `eol`, `eol_announced`, `notices`, via PR — the floor still never moves without review.
**Alternative rejected:** the pipeline POSTing to an admin endpoint (the floor moves without review; two sources of truth); self-hosting endoflife.date.
**Price:** the host trusts «origin/main» for DATA — bounded by the cosign check of the digest it names and by CI's validation of every change to the file.
**Related:** D-056 · D-061

### D-055 · 2026-09-20 · The version verdict rides in the lease response, signed, with a three-rung client ladder
**Status:** active
**Context:** Every container renews its lease daily over an authenticated channel and already sends `engine_version`. Grafana/Nextcloud/Sentry add a separate phone-home and argue about opt-out; here the information flows server → client and the outbound stream does not grow. `sign_lease` covers every top-level key except `bundle`/`signature`, and 0.3.14 clients verify over what they received — new fields are signature-compatible.
**Decision:** `version{running_latest, latest, latest_in_cycle, min_supported, deprecated_at (@unix, RFC 9745), sunset_at (HTTP-date, RFC 8594), notice{id, severity, text, url}}` added before signing. Client: `running_latest=false` → INFO once per version + `/status`/UI; `deprecated_at` passed → WARN every renewal + UI banner + doctor, fully functional; `sunset_at` passed → server 426 `unsupported_client` naming `min_supported` and the upgrade command, a verdict outside grace like 402/403. A notice is retracted by absence (Sentry beacon).
**Alternative rejected:** a separate update-check endpoint.
**Related:** D-056 · D-063 · D-064

### D-056 · 2026-09-20 · The floor moves only through the registry, with ≥90 days of notice, and the server refuses to enforce a floor announced late
**Status:** active
**Context:** Docker 29.0 raised the minimum API from 1.24 to 1.44, broke Traefik and GitLab Runner, and reverted to 1.40 in 29.3.
**Decision:** `min_supported` = `latest` of the oldest cycle whose `eol` has not passed. 426 only when `eol ≤ now` AND `eol − eol_announced ≥ 90 d` AND `now − eol_announced ≥ 90 d`; otherwise log and serve. CI rejects a registry diff that sets or advances `eol` without `eol_announced ≤ today` and `eol ≥ eol_announced + 90 d`. `PSEUDEX_MIN_ENGINE_VERSION` is retired. The fleet histogram (`/admin/versions`, from `engine_version` recorded per lease) is the precondition for moving the floor — and it is empty of truth until the first real version ships (every container says `1.0.0` today).
**Related:** D-054 · D-055

### D-057 · 2026-09-20 · Support window: current → maintenance (security only, 6 months, from «release/X.Y») → eol
**Status:** active
**Context:** The owner chose the promise a B2B customer expects: a security fix without a forced schema migration.
**Decision:** A minor is `current` until the next minor ships; then `maintenance` for six months (`eoas` = next minor's date, `eol` = +6 months, `eol_announced` = that day); then `eol`. Only `security:` commits (and `fix:` by the owner's call) are backported by cherry-pick into «release/X.Y»; a GitHub Action opens the backport PR on merge to `main`; release-please on the branch cuts `X.Y.Z+1`, which moves only the `X.Y` alias. The numbers live in `support{}` of the registry and change as data.
**Alternative rejected:** fixes only in the current minor with 90 days to move (Immich-style) — simpler, riskier for the customer.
**Price:** one branch per minor in the window; the owner merges backport PRs.
**Related:** D-054 · D-061

### D-058 · 2026-09-20 · `PRAGMA application_id` + monotonic `PRAGMA user_version` per store; an older image refuses a volume from the future
**Status:** active
**Context:** Migrations ran inside every worker's `Vault.__init__` with no schema number; an older image opened a newer volume silently. SQLite reserves both header integers for the application; SQLCipher encrypts the header, so they are readable only after `PRAGMA key`.
**Decision:** numbered steps beside each store (`VAULT_MIGRATIONS` …), run once by «pseudex/schema.py::ensure» in the new one-shot role `migrate` between `probe` and the worker fan-out; `probe` reads both numbers after key resolution and exits 2 (entrypoint 6) on `user_version > max` with a message naming both numbers, the minimum image and the snapshot path; `< min` → «upgrade to image Y first». `user_version 0` = pre-versioned: all idempotent steps, then stamp. Same guard in Gitea, Signal Desktop (SQLCipher), Home Assistant.
**Alternative rejected:** `schema_version` (SQLite's own cookie, moves on VACUUM); a migrations table without the header (unreadable before trusting any table).
**Related:** D-059 · D-060

### D-059 · 2026-09-20 · A `VACUUM INTO` snapshot before any step that raises `user_version`
**Status:** active
**Decision:** free space ≥ 2 × (store + `-wal`) or refuse before touching anything; `PRAGMA wal_checkpoint(TRUNCATE)`; `VACUUM INTO '<store>.pre-<from>-<to>.db'` on the same keyed connection (SQLCipher keeps the key — `sqlcipher-compatibility.test`); fsync file and directory; once, under `vault_migrate._Lock`. The documented rollback is «stop, replace the store with the `.pre-*` snapshot, delete `-wal`/`-shm`, start the older image».
**Alternative rejected:** copying the file (unsafe with WAL, «howtocorrupt.html»); no snapshot.
**Price:** 2× disk during migration.
**Related:** D-058

### D-060 · 2026-09-20 · Semver is a schema contract, pinned by «schema_lock.json»
**Status:** active
**Decision:** patch → `user_version` unchanged, downgrade free; minor → may raise, one way; major → may require an operator role named in the release notes. `prototype/schema_lock.json` maps each minor to the max step per store; «test_schema.py» is red when `max_version(store)` differs from the row of the minor in «version.txt». Gitea/PostgreSQL/Grafana state the same contract in words; here it is a test.
**Related:** D-052 · D-058

### D-061 · 2026-09-20 · The site advertises the floating minor `pseudex:X.Y`; the registry moves the aliases; signatures stay on the digest
**Status:** active
**Context:** Docker Official Images require `1.2.3 → 1.2 → 1 → latest` aliases; under D-060 a patch never moves the schema, so a floating minor is safe in both directions.
**Decision:** publish `X.Y.Z`, `X.Y`, `X`, `latest`; `X` and `latest` only on the newest cycle; a maintenance patch moves only `X.Y`. The storefront reads the newest cycle from the synced registry (`engine_release.current_image()`), never from a hand-set env var — the 20.09.2026 `1.0.0` defect. cosign signs the digest; the registry publishes it.
**Alternative rejected:** the exact tag (no patches without a visit to the site); `latest` (a minor without consent).
**Related:** D-054 · D-060

### D-062 · 2026-09-20 · `pseudexctl upgrade` is the native update for `docker run` customers; Watchtower is not recommended
**Status:** active
**Decision:** pull → stop → snapshot (tar) → `probe` with the old image → rename → run with the same volume/ports/env (names only; values in the child environment) → health; unhealthy with an unmoved schema → back to the old image; moved → print `pseudexctl restore …` and touch nothing. Compose customers: `docker compose pull && up -d` (volumes survive everything but `down -v`).
**Alternative rejected:** Watchtower (archived December 2025, «not for production» in its own README, leaves no container on failure).
**Related:** D-058 · D-059

### D-063 · 2026-09-20 · No new protocol field: the client sends the existing `lease_contract`; incompatible changes are contract 4
**Status:** active
**Context:** `lease_contract = 3` already exists server-side (`/v1/pubkey`, response) and is inferred today from the presence of `nonce`. A new `lease_protocol` would duplicate it.
**Decision:** the client sends `lease_contract: 3` explicitly; the server records it; additive fields never bump it; a change an old client could misparse is contract 4, and contract-3 clients keep getting the contract-3 shape while it is served. Unversioned = oldest supported (PostgreSQL libpq, GitHub REST).
**Related:** D-055

### D-064 · 2026-09-20 · `bundle_format` integer in the signed lease; a too-old engine gets «upgrade», not «corrupt»
**Status:** active
**Context:** The bundle has an implicit format discriminator (`is_framed`) but no number; an old engine given a newer format would fail as `bundle_corrupt`.
**Decision:** `bundle_format: 2` (sectioned frame) in the signed payload; the client compares with its maximum and reports `bundle_format_unsupported` naming the engine version that reads it. Raising it raises `min_supported` and is done only together (restic repository version).
**Related:** D-055 · D-056
