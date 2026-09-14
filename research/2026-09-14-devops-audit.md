# Deep Dive — DevOps/CI-CD Pseudex против первоисточников

> Дата: 2026-09-14 · Режим: breadth fan-out, 6 веток, синтез и критика — ведущим · Ведущий вопрос ниже.

## 1. Вопрос и рамки

- **Настоящий вопрос:** что в нашем конвейере (GitHub Actions → Yandex CR → pull-агент на VPS → docker compose) сделано **неправильно с точки зрения первоисточников**, что оставить, и в каком порядке чинить.
- **Полный ответ обязан установить:** для каждого узла — что он *на самом деле* проверяет/защищает (по коду, не по замыслу); где модель угроз, заявленная в комментариях, расходится с механизмом; какие дефекты ловятся статически; цена каждой правки.
- **Подвопросы:** (1) pull-агент и cosign keyless; (2) секреты; (3) Dockerfile/сборка; (4) compose в проде; (5) GitHub Actions; (6) бэкапы.
- **Гипотезы до исследования:** архитектура pull-агента верна; keyless-подпись защищает от подмены образа; init-sed для конфигов — костыль, у compose есть штатное; restic deny-delete — достаточно; семь дефектов за сутки — нормальная цена «CI видно только запуском». **Три из пяти оказались неверны** (см. §5).

## 2. Ответ (BLUF)

**Архитектура правильная, а политика в трёх местах пустая.** Pull-агент без входящего SSH, проверка подписи до остановки, keyless через OIDC, подпись дайджеста после гейтов, append-only бэкап с prune из другой зоны доверия — всё это совпадает с OWASP CICD, OpenGitOps, Google BSRS, SLSA и design doc restic `[B]`. Но: (а) `cosign verify` с `identity=.*` по коду cosign отключает единственную проверку, ради которой keyless существует, — публичный Fulcio выдаёт сертификат любому workflow любого репозитория, и наш агент доверяет реестру ровно так, как заявляет, что не доверяет `[A]`; (б) откат в агенте срабатывает только на отказ в первые ~2 с — `healthy()` проходит, пока сервисы ещё `starting` `[A]`; (в) `forget` без `--keep-within` — документированная в design doc restic атака, при которой взломанный хост заставляет **наш же CI** удалить настоящие снапшоты `[A]`. Семь дефектов за сутки — не цена, а симптом: три ловятся линтерами, которых нет, два — тестами на вынесенных из YAML скриптах. Ниже — 23 правки в порядке ценности; первые шесть закрываются за один рабочий день.

## 3. Инсайты (проход 0.01%)

1. **Keyless-подпись с `.*` эквивалентна Watchtower.** Оба доверяют тому, что лежит в реестре; разница только в замысле. Fulcio принимает `token.actions.githubusercontent.com` без ограничения по репозиторию (`fulcio/config/identity/config.yaml:114-120`), SAN = `job_workflow_ref` атакующего, а `CheckCertificatePolicy` при `.*` — тавтология (`cosign/pkg/cosign/verify.go:306-360`). Второе следствие: `publish` можно запустить `gh workflow run release.yml --ref main -f publish=true` любым write-аккаунтом, и образ подпишется identity `…@refs/heads/main` — только regexp с `@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+$` отсекает это на хосте. `[A]` cosign v2.4.1, fulcio v1.8.8.
2. **Verify по тегу и pull по тегу — два разных резолва.** Подпись стоит над дайджестом, в payload нет версии; `VerifyImageSignatures` резолвит `name:VERSION` сам (`verify.go:504`), `docker compose pull` — второй раз. Скомпрометированный реестр отдаёт под тегом `1.0.5` **другой наш же подписанный** образ (старый, уязвимый) — verify зелёный. Cosign 2.0 сам называет теги «insecure since tags are mutable». Лечится дайджестом из `cosign verify -o json` в compose (`image@sha256:`). `[A]`
3. **`healthy()` агента — проверка, которая не может покраснеть после второй секунды.** `awk '$2=="unhealthy"…'` возвращает успех на первом чистом тике, а `starting` чистым и считается; moby: первая проба внутри `start_period` через 5 с (`health.go:37`). `docker compose up --wait` (`start.go:76-98`) ждёт `healthy` и падает на `unhealthy`/`exited` — это не замена цикла, а его починка. `[A]` docker/compose v5.5.1.
4. **Append-only restic — правильная форма и незакрытая дыра одновременно.** Наша политика байт-в-байт `rest-server --append-only` (`repo.go`: DELETE запрещён везде кроме `locks`) `[A]`. Но design doc, Threat Model: атакующий «may manipulate the use of the `forget` command into deleting all legitimate snapshots» — подложными снапшотами с `--time` в каждое окно `--keep-daily`; docs: «TL;DR: With append-only repositories, you should specifically use the `--keep-within` option». У нас его нет. `[A]`
5. **`configs: content:` в compose — «hack» по словам сопровождающего, наш init-sed — рекомендованная форма.** ndeloof, docker/compose#11900: «configs is actually implemented as a hack … better use an explicit bind mount». Содержимое копируется в контейнер при старте и не входит в config-hash: смена `.env` не доезжает до работающего контейнера. Наш приём делает то, что советует автор, плюс валидацию. Одна правка нужна: `restart: true` на ребре `depends_on`, иначе рендер обновился, а Alertmanager держит старый в памяти (`reconcile.go:970-993`). `[A]`
6. **Переносимый трюк — «отрицательный атом требует положительного над тем же источником» применим к DevOps так же, как к гейтам.** P6 подписывает ключом с `--tlog-upload=false` и проверяет с `--insecure-ignore-tlog` — ни Fulcio, ни SCT, ни identity там не участвуют, и дефект №1 P6 не увидит никогда. Гейт, который проверяет production-путь: verify с боевым regexp проходит, с `@refs/heads/main` и с чужим репо — падает. `[A]`
7. **Секрет через `--build-arg` не течёт в опубликованный образ — но только потому, что Dockerfile двухстадийный.** Эксперимент: `docker history/inspect/save` финала — 0 совпадений; `pseudex:source` (одна стадия) несёт ключ в history и собирается на каждом ноутбуке с боевым `PSEUDEX_TUNING_KEY`. `RUN --mount=type=secret` закрывает и это, и `ps` на раннере, и любой экспорт кеша `mode=max` — и **заодно чинит слой-кеш**, который сейчас инвалидируется каждым прогоном из-за `os.urandom` в `ARG`. `[A]`

## 4. Механизм и находки

### 4.1 Pull-агент и cosign keyless
- **Как работает на самом деле:** `cosign verify` keyless проверяет цепочку до корня Fulcio, SCT, подпись над payload, дайджест в payload, SET Rekor (offline — обещание, не inclusion proof: `verify.go:1055-1110`), срок сертификата против IntegratedTime — и identity/issuer по regexp. При `.*` последнее — `return nil`. Fulcio: SAN = `https://github.com/{job_workflow_ref}`; при `workflow_dispatch --ref v1.2.3` ref = тег → identity `…/release.yml@refs/tags/v1.2.3`. `[A]`
- **Rekor** в модели «наш аккаунт украден» даёт обнаружение, «relies on monitoring» (Sigstore threat-model.md:20) — мониторинга нет; в модели «реестр скомпрометирован» не даёт ничего сверх подписи (статья §6.3). Даёт доверенное время: без tlog keyless-подпись v2.4.1 не проверяется через 10 минут. `[A/B]`
- **SOTA для compose:** эталонной реализации «pull + cosign-политика» нет; Portainer/Komodo тянут git без подписей, Kamal — push по SSH под root, Watchtower архивирован 17.12.2025 с «не для прода». Эталоны политики — Flux `matchOIDCIdentity` (issuer+subject обязательны), `containers-policy.json` (точное совпадение, regexp нет), nerdctl `pull --verify=cosign`. `[B]`
- **Ещё:** якорь доверия — «самый свежий тег в origin» без ruleset; откат `git tag -f` не работает (`WANT == HAVE → exit 0`); версии cosign не закреплены с двух сторон (cosign-installer@v3 плавающий; v3 меняет bundle-формат); агент 50 минут после тега шлёт `crit` «подпись не сошлась», потому что образа ещё нет `[A]`.

### 4.2 Секреты
- `environment:` виден в `docker inspect`, `docker exec env`, `/proc/<pid>/environ`, `compose config`, наследуется потомками — эксперимент `[A]`. Compose `secrets: file:` = тот же bind `:ro` (`create.go:1250-1296`), но отсутствующий файл — ошибка, а не молча созданный каталог `[A]`.
- Против root на хосте не даёт ничего ни одна мера; даёт — отсутствие материала на хосте. Реестр без ключа: только Yandex Compute + СА ВМ + `docker-credential-yc` (токен из метаданных, на диске ничего) + запрет 169.254.169.254 из контейнеров `[B]`. На чужом VPS Lockbox требует авторизованный ключ на диске — бессмысленно `[B]`.
- **WLIF:** Yandex официально поддерживает GitHub OIDC (`tutorials/security/wlif-github-integration`), CR принимает IAM-токен в `docker login`, `yc-actions/yc-cr-login` с `yc-sa-id` — JSON-ключ реестра в секретах не нужен `[B]`. Субъект — точная строка; для тегов, меняющихся каждый релиз, привязывать через `environment: release` (`sub = repo:…:environment:release`) `[B/C]`.
- Ротация ключа подписи: `license.py:208-221` уже принимает список ключей; `pack_gates.py:76-80` собирает с одним. TUF даёт форму: офлайн-корень в бинарнике, онлайн-ключ лиз с сертификатом от корня, `not_after` против freeze — это последний перевыпуск флота, делать пока флот мал `[B]`.
- GitHub secrets: «do not use a blob of JSON… significantly reduces the probability the secrets will be properly redacted» — наш `REGISTRY_PASSWORD` ровно такой `[B]`.

### 4.3 Dockerfile и сборка
- **33 минуты:** ccache стоит в build-стадии (`Dockerfile.nuitka:31`), но холодный каждый прогон; `NUITKA_JOBS=6` на приватном репо = `ubuntu-latest` 2 vCPU. Слой-кеш для компиляции бесполезен по построению (`COPY` выше `RUN nuitka`; `ARG` с `os.urandom` инвалидирует всё ниже). Правильно: `RUN --mount=type=cache` + `actions/cache` + `buildkit-cache-dance`; Nuitka кеширует объектники gcc, не Python-фазу. Ожидание 33 → 10–14 мин `[C]`. Локально те же 1040 файлов — 290 с `[A]`.
- **`USER`:** CIS 4.1 *Automated* — WARN при `Config.User` пустом; безопасник клиента увидит первым делом. SO_REUSEPORT требует одинакового effective UID — N воркеров под одним `USER` это выполняют. Цена — bind-mount `/data` от хоста `[A]`.
- **`HEALTHCHECK`:** CIS 4.6; для клиента с голым `docker run` инструкция в Dockerfile — единственная. `/health` без токена уже есть; в trixie-slim нет curl, есть bash `/dev/tcp` — работает, проверено `[A]`.
- **Digest vs tag:** защищает воспроизводимость и supply-chain, замораживает патчи → пин индекс-дайджестом + Renovate; инцидент с glibc уже был `[A]`.
- **SBOM/provenance:** L2 через `attest-build-provenance`; для приватного репо — Sigstore GitHub без публичного лога, клиент к нему не достанет; `docker save/load` теряет buildx-аттестации по построению; syft по Nuitka-образу видит только Debian-пакеты. Не сейчас `[B]`.

### 4.4 Compose
- Init с `restart: "no"` перезапускается на каждом `up -d` (exited не считается выполненным — `service_containers.go:596`); при смене `.env` пересоздаётся (env в config-hash); потребитель — нет, пока не `restart: true` `[A]`.
- `${VAR:?}` под profiles ломает `up -d` — по коду compose-go (`loader.go:489`) и словам ndeloof #11977 «not planned» `[A]`. Наш `:-` + валидация в контейнере + awk в CI — единственный корректный паттерн `[A]`.
- `unless-stopped` + `live-restore` — правильный выбор; docker-ce не обновляется unattended-upgrades (`Origin: Docker` вне `Allowed-Origins`) `[A]`.
- `up -d` без `--profile` не обновляет профильные сервисы и не удаляет их как orphans (`isOrphaned` учитывает `DisabledServiceNames`) — агент никогда не выкатит новый Prometheus, пока `COMPOSE_PROFILES` не в `.env` `[A]`.
- Сторож с `docker.sock` = root на хосте (OWASP Rule #1; `:ro` «не решение»); нужен один `GET /containers/json` → systemd-таймер на хосте `[A]`.

### 4.5 GitHub Actions
- actionlint (прогнан на версиях из git до починок): дубль `permissions` — `[syntax-check]`, heredoc — SC1039/SC1119. zizmor pedantic — секрет в `run:`. `${{ secrets }}` не считается untrusted ни одним из них в default — правило «ноль `${{ }}` внутри `run:`» enforce-ится только pedantic `[A]`.
- Шесть `${{ secrets.* }}` внутри `run:` всё ещё живут (`ship.yml:154-157`, `backup-audit.yml:183-192`) — класс не закрыт `[A]`.
- `concurrency` нет у ship/release/checks/gates: два ship → два тега → агент упирается в старший красный, младший зелёный не выкатится `[A]`.
- Артефакт 136 МБ × 7 дней на приватном репо → квота 500 МБ, четвёртый релиз за неделю упадёт `[A]`. `docker save/load` — 32 с из 50 мин, не проблема производительности.
- `permissions` не объявлены в 5 из 6 файлов; безопасность держится на настройке репо вне git `[A]`.
- act не воспроизводит ни один дефект, который не ловят линтеры (permissions, concurrency, OIDC игнорируются) `[B]`.

### 4.6 Бэкапы
- Политика = `rest-server --append-only` по коду; раздела «минимальные права S3» в docs restic **нет** — форма стоит на форуме мейнтейнера (#6858, пост 4) `[A]`.
- Версионирование защищает от **перезаписи хостом** (`PutObject` поверх существующего — S3-политика не выражает), не от второго ключа: `storage.editor` умеет `DeleteObjectVersion` и правит lifecycle `[A]`. Object Lock compliance на Yandex работает с restic без правок (Content-MD5 шлёт, удаляет без VersionId) — единственное, что защищает и от второго ключа, и от владельца `[B]`.
- `--read-data-subset=5%` — случайно, новый сид каждый раз, при <40 pack = один pack в день; 30 дней = 78%, не «всё» `[A]`.
- Второй пароль restic ничего не покупает: все key-файлы открывают один мастер-ключ, отзыв без перешифровки невозможен (design doc) `[A]`.
- RPO 24 ч; ключи восстановимы из витрины (тот же `sha256(key)` в обеих базах), кванты и `report_secret` — нет. Litestream: WAL включён, шифрование выключено, `retention.enabled: false` под нашу deny-delete `[B]`.
- `check`/`prune` упадут в 06:20, если хост пишет — `--retry-lock 15m` `[A]`.

## 5. Критический анализ

- **Стилмен консенсуса:** «pull-агент + keyless + append-only — это и есть SOTA для одного хоста». Верно: первоисточники (OWASP CICD-SEC-6, OpenGitOps §3–4, BSRS «verify artifacts, not people», SLSA threat G/H, restic design doc) поддерживают каждую из этих форм.
- **Сильнейший контрдовод:** формы без политики — пустые. Три центральные защиты (identity, health-wait, keep-within) выглядят настроенными и не работают — и **ни один гейт этого не показывает**, потому что P6 проверяет не production-путь, а `healthy()` не может покраснеть после второй секунды. Это тот же класс, что `audit_gates.py` ловит у L-гейтов.
- **Единственное несущее допущение:** «реестру мы не доверяем». Оно верно ТОЛЬКО при точной identity + дайджесте в compose + ruleset на теги. Сейчас реестр Яндекса — единственная граница, а комментарий агента утверждает обратное.
- **Где источники расходятся и почему:** Docker docs говорят «build-arg персистирует в финальном образе» — для single-stage; наш эксперимент показывает 0 в multi-stage. Оба правы, режим разный; наш `prototype/Dockerfile` — single-stage. Restic docs молчат про минимальные права S3, форум даёт форму — это не противоречие, а незакрытая документация.
- **Стимулы:** Watchtower архивирован самими авторами; Portainer/Komodo — продукты, подписи им не нужны для продаж; GitHub рекомендует `environment:` для OIDC-субъекта, что попутно продаёт environments. Ни один из них не даёт довода против нашей формы.
- **Заработанный консенсус vs повторяемое:** 41 утверждение [A] (код/эксперимент), 19 [B], 5 [C], 1 [D]. Топик **закрыт первоисточниками**; единственная фольклорная посылка — «restic docs описывают минимальные права S3» — оказалась ложной и заменена ссылкой на мейнтейнера.

## 6. План правок — в порядке ценности

✅ — сделано и проверено запуском (коммиты 72f5af4…cc6a825 и далее); линтеры
стоят в `checks.yml` (джоба `workflows`) и красят PR сами.

| # | правка | почему | усилие |
|---|---|---|---|
| 1 ✅ | **identity/issuer точные, агент отказывает без них** | `.*` = Watchtower `[A]` | 30 мин |
| 2 ✅ | **`up -d --wait --wait-timeout 120`** вместо `healthy()` | откат работает только 2 с `[A]` | 30 мин |
| 3 ✅ | **`--keep-within 30d`** в `forget` | атака из design doc `[A]` | 5 мин |
| 4 ✅ | **`--read-data` целиком**, комментарий исправить | 5% = один pack `[A]` | 15 мин |
| 5 ✅ | **actionlint + zizmor pedantic** в checks.yml; `${{ }}` из `run:` — все 16 | 3/7 дефектов статически `[A]` | 1 ч |
| 6 ✅ | **`concurrency`** на ship/release/checks/gates; агенту — ветка «образа ещё нет» | гонка тегов, 50 мин crit `[A]` | 1 ч |
| 7 ✅ | `restart: true` на `depends_on` init-сервисов; `COMPOSE_PROFILES` в `.env`; `PSEUDEX_CONF_REV` (дерево `deploy/` тега) в environment всех сервисов с bind-mount конфигов — содержимое файла не входит в хеш сервиса (`hash.go`) | рендер без потребителя; профили не обновляются; конфиг-only тег не применяется `[A]` | 20 мин |
| 8 | `--mount=type=secret` для tuning key; гейт P11 с положительным контролем | `pseudex:source` + `ps` + кеш `[A]` | 2,5 ч |
| 9 | Nuitka ccache: cache-mount + actions/cache + cache-dance; `NUITKA_JOBS=nproc` | 33 → 10–14 мин `[C]` | 1 день |
| 10 | Deny `DeleteObjectVersion`+`PutLifecycleConfiguration` аудиту; версии 30 дн; `--retry-lock 15m` | второй ключ стирает навсегда `[A]` | 45 мин |
| 11 | Дайджест из `cosign verify -o json` в compose (`image@sha256:`) | двойной резолв тега `[A]` | 1 ч |
| 12 | `USER 10001` + `HEALTHCHECK` (bash `/dev/tcp`) в клиентском образе; P8 проверяет | CIS 4.1/4.6 `[A]` | полдня + L19–L22 |
| 13 ✅ | `permissions` во всех 6 файлах; `persist-credentials: false`; `retention-days: 1` | квота, least-privilege `[A]` | 30 мин |
| 14 | Сторож → systemd-таймер; promtail через socket-proxy | root на хосте `[A]` | 2 ч |
| 15 | WLIF вместо JSON-ключа реестра; `environment: release` с reviewer | статический ключ не нужен `[B]` | 2 ч |
| 16 | Ruleset на `v*`: кто может создавать теги | якорь доверия `[A]` | 15 мин |
| 17 | Гейт P6b: verify production-regexp проходит, `@refs/heads/main` и чужой repo падают | P6 не проверяет прод-путь `[A]` | 1 ч |
| 18 | Пин cosign с двух сторон (`cosign-release:` = версия в bootstrap) | v3 меняет bundle `[B]` | 10 мин |
| 19 | `pg_restore` вывезенного дампа в аудите (services: postgres) | никогда не разворачивался `[B]` | 1,5 ч |
| 20 | Секреты файлами (`_FILE`) через compose `secrets:` | inspect/exec/наследование `[A]` | 5 ч |
| 21 | Ротация ключа подписи: конвейер с двумя ключами | движок готов, конвейер нет `[B]` | 3 ч |
| 22 | Litestream для лицензионной SQLite | RPO 24 ч → секунды `[B]` | 1 день |
| 23 | Пин `FROM` дайджестами + Renovate (действия GHA уже по SHA + Dependabot, мажоры руками — ✅); `next-version`/`checks-green`/compose-проверки → `ci/*.sh` + bats | glibc-инцидент; дефекты №3–4 фикстурами `[A]` | полдня |

Первые шесть — один рабочий день, и они закрывают все три «пустые политики».

## 7. Что оставить как есть (с обоснованием)

- **Pull-агент без SSH и без креденшала прода в GitHub** — OWASP CICD-SEC-6, OpenGitOps §3–4; push по SSH (Kamal) хуже по обоим.
- **Проверка подписи до остановки, fail-closed, откат, flock** — SLSA G/H, Humble «smoke test your deployments»; чинить политику, не место.
- **Keyless + Rekor вместо долгоживущего ключа** — статья §6.5: компрометация ограничена одним прогоном.
- **Подпись дайджеста после гейтов, `docker save/load` как транспорт** — «only build packages once»; Docker docs рекомендуют ровно это для single-platform.
- **Init-sed + `restart: "no"` + `service_completed_successfully`** — форма, которую сопровождающий compose сам рекомендует; `configs: content:` — hack без обновления.
- **`${VAR:-}` + отказ в контейнере + awk в CI** — единственный корректный паттерн для profiled.
- **Deny-delete с исключением `locks/`, prune из CI другим ключом** — «separate and well-secured client» из docs restic; не сужать до `uploader`.
- **Один пароль restic** — второй не покупает отзыва (design doc); усилия — в ротацию S3-ключа.
- **Незашифрованные локальные копии, `sqlite3 .backup`, restore-drill с непустыми таблицами**.
- **Bind `:ro` файлом** — тот же код, что compose `secrets:`; менять только ради отказа на отсутствующем файле.
- **Ключ проверки вкомпилирован, env игнорируется (L2b)** — верно; список ключей в `_public_key_materials` — верно, доделать конвейер.
- **act не заводить** — не воспроизводит ничего, что не ловят линтеры.

## 8. Открытые вопросы

- **Нерешено:** точный формат субъекта WLIF Яндекса для тегов (документация показывает только точную строку; `environment:` — обход, не подтверждённый для тегов) `[C]`. Поддержка OCI referrers в cr.yandex для `push-to-registry` аттестаций `[D]`.
- **Что перевернёт вывод:** если cosign-installer на CI уже ставит 3.x с новым bundle-форматом — тогда хост с 2.4.1 не проверит ни одной подписи, и первый же настоящий деплой упадёт fail-closed с диагнозом «подпись не сошлась». Проверить `cosign version` в логе последнего release.
- **Что измерить дальше:** hit-rate ccache после п.9 (`ccache -s` в конце RUN); реальный `--wait-timeout` на стенде; `job_workflow_ref` в сертификате опубликованного образа — `cosign verify -o json | jq '.[].optional'`.

## 9. Источники (первичные, прочитаны)

**Sigstore.** [cosign v2.4.1 `pkg/cosign/verify.go`, `cmd/cosign/cli/options/certificate.go`](https://github.com/sigstore/cosign/tree/v2.4.1) · [fulcio v1.8.8 `config/identity/config.yaml`](https://github.com/sigstore/fulcio/tree/v1.8.8) · [Sigstore threat model](https://docs.sigstore.dev/about/threat-model/) · [Newman, Meyers, Torres-Arias — Sigstore: Software Signing for Everybody, CCS '22](https://dl.acm.org/doi/10.1145/3548606.3560596) · [Cosign 2.0 released](https://blog.sigstore.dev/cosign-2-0-released/) · [OIDC in Fulcio](https://docs.sigstore.dev/certificate_authority/oidc-in-fulcio/)
**Деплой.** [OpenGitOps v1](https://opengitops.dev/) · [OWASP Top 10 CI/CD](https://owasp.org/www-project-top-10-ci-cd-security-risks/) · [Google BSRS ch. 14](https://google.github.io/building-secure-and-reliable-systems/raw/ch14.html) · [SLSA v1.0 Verifying artifacts](https://slsa.dev/spec/v1.0/verifying-artifacts) · [SLSA v1.0 levels](https://slsa.dev/spec/v1.0/levels) · [Flux OCIRepository spec](https://fluxcd.io/flux/components/source/ocirepositories/) · [containers-policy.json(5)](https://github.com/containers/image/blob/main/docs/containers-policy.json.5.md) · [Watchtower README / discussion #2135](https://github.com/containrrr/watchtower)
**Секреты.** [Docker: build secrets](https://docs.docker.com/build/building/secrets/) · [Dockerfile reference ARG / RUN --mount](https://docs.docker.com/reference/dockerfile/) · [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/) · [docker/compose `pkg/compose/create.go`, `secrets.go`](https://github.com/docker/compose) · [Yandex WLIF + GitHub](https://yandex.cloud/ru/docs/tutorials/security/wlif-github-integration) · [Yandex CR auth](https://yandex.cloud/ru/docs/container-registry/operations/authentication) · [Yandex Lockbox](https://yandex.cloud/ru/docs/lockbox/) · [TUF spec](https://theupdateframework.github.io/specification/latest/) · [SOPS README](https://github.com/getsops/sops) · [GitHub: Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use) · [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
**Сборка.** [Docker cache invalidation](https://docs.docker.com/build/cache/invalidation/) · [Cache mounts in GHA](https://docs.docker.com/build/ci/github-actions/cache/) · [Nuitka: caching](https://nuitka.net/user-documentation/tips.html) · [Nuitka-Action](https://github.com/Nuitka/Nuitka-Action) · [Docker best practices: USER, pin](https://docs.docker.com/build/building/best-practices/) · [Docker engine security](https://docs.docker.com/engine/security/) · [OWASP Docker Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html) · [docker-bench-security 4.x](https://github.com/docker/docker-bench-security) · [Scorecard Pinned-Dependencies](https://github.com/ossf/scorecard/blob/main/docs/checks.md) · [Renovate docker](https://docs.renovatebot.com/docker/) · [Docker attestations](https://docs.docker.com/build/metadata/attestations/) · [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
**Compose.** [Compose spec: services, configs, interpolation](https://github.com/compose-spec/compose-spec) · [compose-go `loader/loader.go`](https://github.com/compose-spec/compose-go) · [docker/compose `reconcile.go`, `start.go`, `service_containers.go`, `hash.go`](https://github.com/docker/compose) · [docker/compose #11900, #11977](https://github.com/docker/compose/issues/11900) · [moby `restartmanager.go`, `daemon.go`](https://github.com/moby/moby) · [Docker: restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/) · [Docker: live-restore](https://docs.docker.com/engine/daemon/live-restore/) · [docker-socket-proxy](https://github.com/Tecnativa/docker-socket-proxy) · [docker-rollout](https://github.com/wowu/docker-rollout)
**GHA.** [actionlint checks](https://github.com/rhysd/actionlint/blob/main/docs/checks.md) · [zizmor audits](https://docs.zizmor.sh/audits/) · [GitHub: script injections](https://docs.github.com/en/actions/reference/security/secure-use#understanding-the-risk-of-script-injections) · [GitHub: triggering a workflow from a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow) · [GitHub: concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) · [GitHub: OIDC reference](https://docs.github.com/en/actions/reference/security/oidc) · [GitHub: artifact storage billing](https://docs.github.com/en/billing/managing-billing-for-your-products/about-billing-for-github-actions) · [upload-artifact README](https://github.com/actions/upload-artifact) · [act: unsupported functionality](https://nektosact.com/not_supported.html)
**Бэкапы.** [restic: forget, security in append-only](https://restic.readthedocs.io/en/stable/060_forget.html#security-considerations-in-append-only-mode) · [restic: check](https://restic.readthedocs.io/en/stable/045_working_with_repos.html#checking-integrity-and-consistency) · [restic design doc, threat model](https://restic.readthedocs.io/en/stable/100_references.html#threat-model) · [restic `cmd_check.go`, `lock.go`, `s3.go`](https://github.com/restic/restic) · [rest-server `repo/repo.go`](https://github.com/restic/rest-server) · [restic forum #6858](https://forum.restic.net/t/any-way-to-get-restic-to-work-with-s3-object-locking-or-a-read-only-key/6858) · [restic #5204, #4992](https://github.com/restic/restic/issues/5204) · [Yandex: policy actions, roles, object lock](https://yandex.cloud/en/docs/storage/concepts/object-lock) · [Litestream: how it works, config](https://litestream.io/how-it-works/) · [PostgreSQL: pg_restore, continuous archiving](https://www.postgresql.org/docs/current/continuous-archiving.html)
