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

FROM node:22-alpine AS builder
WORKDIR /bot
COPY --from=source /src/package.json /src/package-lock.json /bot/
RUN apk add --no-cache python3 build-base
RUN npm ci
COPY --from=source /src/src /bot/src
COPY --from=source /src/tsconfig.json /bot/tsconfig.json
RUN npm run build

FROM node:22-alpine AS production
WORKDIR /bot
COPY --from=source /src/package.json /src/package-lock.json /bot/
RUN apk add --no-cache python3 build-base
RUN npm ci --only=production && npm cache clean --force
COPY --from=builder /bot/build /bot/build
ENV NODE_ENV=production
CMD ["node", "./build/index.js"]
