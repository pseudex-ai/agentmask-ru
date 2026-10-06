# Бот поддержки — bostrot/telegram-support-bot, собранный ИЗ ЗАКРЕПЛЁННОГО КОММИТА.
#
# ГОТОВОГО ОБРАЗА У АПСТРИМА НЕТ: их compose делает `build: .`. А у нас образы
# собираются в CI и подписываются, потому что деплой-агент ПРОВЕРЯЕТ ПОДПИСЬ до
# того, как что-либо остановит, — и «собрать на хосте» означало бы одну неподписанную
# вещь в стеке, который весь стоит на подписи.
#
# КОММИТ, А НЕ ТЕГ. Тег переставляем, и `v5.0.0` завтра может указывать на
# другие байты; SHA — нет. Обновление версии — это осознанная правка этой
# строки, а не то, что случается само.
#
# Стадии сборки повторяют Dockerfile апстрима v5.0.0 дословно (node:22-alpine,
# npm ci, npm run build, production-стадия с --only=production), чтобы образ,
# который мы подписываем, был тем же, что апстрим считает своим.
#
# Лицензия апстрима GPL-3.0. Нам не мешает: бот запускается отдельным
# сервисом и ни во что из нашего не линкуется.

FROM alpine/git:2.47.2 AS source
ARG UPSTREAM_REPO=https://github.com/bostrot/telegram-support-bot.git
ARG UPSTREAM_COMMIT=0e4838e7c8f7dcef7f09f9e2ea28f6f9b2e31c70
WORKDIR /src
RUN git init -q . \
 && git remote add origin "${UPSTREAM_REPO}" \
 && git fetch -q --depth 1 origin "${UPSTREAM_COMMIT}" \
 && git checkout -q FETCH_HEAD \
 && test "$(git rev-parse HEAD)" = "${UPSTREAM_COMMIT}"

# НАШИ ИСПРАВЛЕНИЯ — ОДНИМ ФАЙЛОМ ПАТЧА, А НЕ ЦЕПОЧКОЙ `sed`.
#
# Первым здесь стоял один `sed` по `staff.ts`: ответ оператора искался только по
# `external_reply.message_id` (форум-темы), а для обычного «Ответить» падал в
# ветку с фильтром по категории, которой у оператора не бывает. Найдено первым
# же ответом на первый же тикет, и лечилось одной строкой.
#
# Вторым — и это уже не одна строка — оказалось то же самое место: фильтр по
# пустой категории (`{ category: null }`) означал «тикет БЕЗ категории», а не
# «категория неизвестна», поэтому ЛЮБОЙ ответ, кроме ответа на первую карточку,
# отбивался текстом «Этот тикет закрыт» — при открытом тикете. Цепочка `sed`
# растёт вместе с числом таких находок и молчит, когда строка изменилась.
#
# `git apply` НЕ МОЛЧИТ: он либо кладёт всё, либо падает и роняет сборку. Это
# ровно то поведение, которое нужно при обновлении апстрима — изменившуюся
# строку видно на сборке, а не в проде.
#
# ТРЕТЬИМ — LOCKFILE, И ЭТО ТОЖЕ ПРАВКА БЕЗОПАСНОСТИ, А НЕ КОД. Публикацию
# остановил гейт сканера: в образе нашли исправимые CRITICAL `proxy-addr` 2.0.7
# (CVE-2026-90711) и `tar` 7.4.3 (CVE-2026-59873) — транзитивные зависимости
# бота, которые подтягивает апстрим (`express` просит `proxy-addr@^2.0.7`,
# `cacache` и `node-gyp` — `tar@^7.4.3`). Патч поднимает их до 2.0.8 и 7.5.19
# прямо в `package-lock.json`, вместе с `resolved` и `integrity`: диапазоны
# апстрима новые версии и так разрешают, поэтому `npm ci` остаётся честным — он
# ставит ровно то, что в замке, и не ходит в реестр за свежими версиями.
#
# Через `overrides` в `package.json` это сделать нельзя: `npm ci` отказывается
# работать, когда package.json разошёлся с замком, — а правка замка патчем
# заодно видна в ревью и ломает сборку, если апстрим поднимет пакет сам.
COPY patches/ /patches/
RUN git apply --verbose /patches/pseudex.patch

# КОНФИГ СВЕРЯЕТСЯ ЗДЕСЬ, ГДЕ АПСТРИМ ЛЕЖИТ РЯДОМ. Семь ключей нашей первой
# версии (`allow_user_close`, `ticket_per_message`, `allow_broadcast`,
# `forward_edited_messages`, `forward_stickers`, `show_replied_mark`,
# `user_commands`) в v5.0.0 не существуют: они молча ничего не делали, а
# комментарии рядом описывали поведение, которого нет. `user_commands` стоил
# дороже всех — он объявлял `/docs` и `/cabinet`, которых бот не знает, а
# неизвестный текст у клиента становится тикетом.
#
# Ключ, которого нет в исходниках, — это опечатка, которую нельзя поймать
# глазами: список ключей меняется от версии к версии, а `config-sample.yaml`
# документирует не всё, что читает код. Проверка стоит секунду и падает один
# раз — на сборке.
COPY config.yaml /check/config.yaml
RUN set -eu; \
    for k in $(grep -E '^[a-z_]+:' /check/config.yaml | cut -d: -f1); do \
      grep -rq "$k" src/ || { \
        echo "deploy/supportbot/config.yaml: ключ ${k} отсутствует в апстриме ${UPSTREAM_COMMIT}."; \
        echo "Такой ключ молча ничего не делает: уберите его или почините имя."; \
        exit 1; }; \
    done; \
    echo "все ключи config.yaml существуют в исходниках апстрима"

FROM node:22-alpine AS builder
WORKDIR /bot
COPY --from=source /src/package.json /src/package-lock.json /bot/
RUN apk add --no-cache python3 build-base
RUN npm ci
COPY --from=source /src/src /bot/src
COPY --from=source /src/tsconfig.json /bot/tsconfig.json
COPY --from=source /src/jest.config.js /bot/jest.config.js
COPY --from=source /src/jest.setup.js /bot/jest.setup.js
COPY --from=source /src/test /bot/test
RUN npm run build
# ТЕСТЫ АПСТРИМА И НАШИ РЕГРЕССИИ — ЧАСТЬ СБОРКИ, А НЕ ПОЖЕЛАНИЕ.
#
# Патч может отвалиться не только целиком (`git apply` такое ловит), но и
# частично: строка изменилась так, что патч лёг, а поведение не то. Тесты
# `pseudex-regressions.test.ts` падают именно на непатченном апстриме — это
# проверено снятием патча, — поэтому здесь ловится и такой случай.
#
# ВАЖНО ПРО `test/mocks.ts`: он подключён через `setupFiles` и подменяет
# `../src/db` частичной заглушкой, из-за чего тесты самого апстрима в
# `db.test.ts` уходят в ветку `else { expect(true).toBe(true) }` — проходят, не
# проверив ничего. Наши тесты вызывают `jest.unmock('../src/db')` и работают с
# настоящим модулем.
RUN npm test

FROM node:22-alpine AS production
WORKDIR /bot
COPY --from=source /src/package.json /src/package-lock.json /bot/
RUN apk add --no-cache python3 build-base
RUN npm ci --only=production && npm cache clean --force
COPY --from=builder /bot/build /bot/build
ENV NODE_ENV=production
CMD ["node", "./build/index.js"]
