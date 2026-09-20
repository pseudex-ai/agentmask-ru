# AGENTMASK — как править публичный бенчмарк и не накосячить

AgentMask-RU живёт в ДВУХ местах одновременно:

| | где | что это |
|---|---|---|
| рабочая копия | `public/agentmask-ru/` в монорепозитории | здесь правим, здесь история проекта |
| публичный репозиторий | `github.com/pseudex-ai/agentmask-ru` (remote `agentmask`) | зеркало, которое видят чужие люди |

Правило одно: **правим только в монорепозитории, в публичный репозиторий
пушим выжимку.** Обратного направления нет — если кто-то пришлёт PR, его
содержимое переносится руками в `public/agentmask-ru/` и уезжает обратно тем
же путём, что и своё.

---

## Проверить, синхронизировано ли сейчас

```sh
cd /Users/igor/Projects/Obscura
git fetch -q agentmask
git diff --name-only HEAD:public/agentmask-ru agentmask/main
```

Пусто — совпадает. Любая строка — расхождение, и его надо разрешить ДО
следующей правки, иначе разойдутся дальше.

## Цикл правки

```sh
cd /Users/igor/Projects/Obscura/public/agentmask-ru
source .venv/bin/activate

#  …правим…

python -m pytest -q                                  # 29 тестов прибора
python -m agentmask_ru.gates --cases cases --root .  # семь гейтов
python -m agentmask_ru.build --seed 20260920 --out cases --check   # корпус тот же

cd /Users/igor/Projects/Obscura
git add -A public/agentmask-ru
git commit -F <файл-с-сообщением>          # кириллица в -m ломается на бэктиках
git push origin main

git subtree split --prefix=public/agentmask-ru -b agentmask-publish -q
git push agentmask agentmask-publish:main
git branch -D agentmask-publish            # ветка одноразовая, пересоздаётся
```

Три проверки перед коммитом — не формальность: гейты ловят дефекты КОРПУСА
(офсет уехал, негативов нет, случай стал неотличим от passthrough), а
`--check` ловит расхождение корпуса с его же зерном. Набор, который никто не
может пересобрать, никто не может и проверить.

## Чего делать нельзя

**`git subtree pull` не работает и не заработает.** `split` переписывает
коммиты: те же изменения получают другие хеши, общего предка git не находит и
отвечает «refusing to merge unrelated histories». `--squash` тоже не поможет —
он требует, чтобы префикс когда-то добавляли через `subtree add --squash`, а
его добавляли иначе. Тот же урок уже оплачен на storefront, см. коммит
`1ae1f47`.

**Не коммитить в публичный репозиторий напрямую.** Даже одну опечатку в
README: следующий `split` перезапишет её, правка потеряется молча.

**Не пушить `.venv`.** Она в `.gitignore` бенчмарка, но при `git add -A` из
корня монорепозитория легко утащить лишнее — проверяй `git status` перед
коммитом.

**Не переносить в публичный репозиторий ничего из `prototype/`.** Гейт G10
запрещает импорты `pseudex` и `licensing` в `src/`, но пулы значений и
словари он не проверяет: корпус обязан строиться из открытых источников
(`pools/build_pools.py`), а не из лизованных словарей движка, иначе бенчмарк
перестанет уметь нас проваливать.

## Наша строка в таблице

Прогон движка идёт ЧЕРЕЗ публичный харнесс по HTTP, а не изнутри:

```sh
cd /Users/igor/Projects/Obscura/prototype
source .venv/bin/activate
python3 bench/public_row.py --out ../public/agentmask-ru/results/
```

Скрипт поднимает сайдкар с dev-бандлом и зовёт публичный CLI с адаптером
`pseudex_sidecar`. Публичный пакет о движке не знает ничего, кроме ответов
трёх эндпоинтов — той же поверхности, что видят Cloud.ru и Presidio. Он же
печатает, сколько имён корпуса лежит в нашем газетире: это число уходит в
манифест прогона, потому что бенчмарк, написанный вендором, обязан сказать,
насколько корпус вообще способен его провалить.

## Прогон чужих систем

```sh
# Cloud.ru
cd public/agentmask-ru/baselines/cloudru && docker compose up -d
agentmask run --adapter openai_proxy --name cloudru \
    --base-url http://127.0.0.1:8080/v1 --upstream-bind 0.0.0.0:8099 --out results/

# LiteLLM + Presidio
cd public/agentmask-ru/baselines/litellm && docker compose up -d
agentmask run --adapter openai_proxy --name litellm --model fake \
    --base-url http://127.0.0.1:4000/v1 --api-key sk-agentmask \
    --upstream-bind 0.0.0.0:8099 --out results/
```

**Порт 8099 занимать нельзя.** Фальшивый провайдер слушает его на всех
интерфейсах, потому что контейнер ходит к нему через `host.docker.internal`.
Забытый процесс на этом порту стоил часа диагностики: прокси отвечал 501, и
это выглядело как дефект прокси. Проверка — `lsof -nP -iTCP:8099 -sTCP:LISTEN`.

**Имя модели должно совпадать с конфигом прокси.** У LiteLLM модель зовётся
`fake`, а адаптер по умолчанию шлёт `agentmask-fake`; несовпадение даёт 272
ошибки подряд, и такой прогон нельзя публиковать — он описывает нашу
конфигурацию, а не чужой продукт.

После прогонов:

```sh
agentmask leaderboard        # пересобрать leaderboard.md из results/
```

## Windows — не абстракция

Первый же прогон CI упал на Windows: консоль там отдаёт cp1251, и русская
строка в выводе роняет процесс с `UnicodeEncodeError`. Матрица `ubuntu` +
`windows` в CI стоит ровно ради этого — читатели статьи приходят и оттуда.
Точки входа зовут `_utf8_stdout()` первой строкой; любая новая точка входа с
русским выводом обязана делать то же.

## Где что лежит

| путь | что |
|---|---|
| `cases/<семья>/<id>.json` | корпус, 272 случая, по файлу на случай |
| `pools/` | снимки Wikidata, NEN, mimesis, Faker + скрипт пересборки |
| `src/agentmask_ru/` | схема, генератор, выравнивание, харнесс, скорер, гейты |
| `src/agentmask_ru/adapters/` | адаптеры измеряемых систем |
| `baselines/` | compose-рецепты чужих шлюзов |
| `results/<система>/<прогон>.json` | прогоны с пообъектными наблюдениями |
| `schema/` | JSON-схемы случая и результата, подключены к гейту G1 |
| `points/` | реестр очков контрибьюторов |

Связанное: `docs/tz-roadmap-from-oss.md` (что берём у конкурентов),
`docs/known-issues.md` Б16–Б19 (дефекты, которые нашёл бенчмарк),
`research/2026-09-20-open-benchmark-mechanics.md` (почему устроено именно так).
