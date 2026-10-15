# Три продукта Pseudex: страницы проверки спроса

## Что сделано

- Главная сохраняет существующую воронку клиентского сервиса. Крупный блок «Сила ИИ. Контроль остаётся у вас» ведёт в три направления.
- `/ai-security`: корпоративная платформа AI-безопасности, демонстрация политик/доступа/журнала, заявка на beta-пилот.
- `/ai-coding`: защищённый AI-кодинг, четыре границы, сравнение mask-only / round-trip, явный отказ для неизвестной подстановки, коннекторы и ранний доступ.
- Названия карточек называют продукт. Слоганы и конкретная польза идут ниже; краткое описание каждого направления — в серверном HTML главной, не скрыто за JS.
- Отдельные title/description/canonical и записи sitemap. Нет придуманных метрик, отзывов, клиентов или гарантий совместимости.

## Источники и границы обещаний

Изучены текущий публичный https://pseudex.ru и исходники опубликованной базы `platform/v0.3.38` (`2cddd2c9`). Реализация изолирована в `feat/product-beta-pages`.

Корпоративный продукт: ветка `feat/must-core`, build brief, полный sprint/matrix/decisions/plan и все 18 контрактов `docs/must-core/`, сверены с runtime. Показаны существующие в ветке policy/access/catalog/applications/journal, но не объявлены готовыми rollout/rollback, SSO, DLP/SIEM, HITL или конструктор regex. Журнал в демо — пример безопасного журнала, не обещание отсутствия любого content logging во всех transport paths.

Coding: ветка `feat/coding-codex`, `docs/tz-ai-coding-track.md`, локальный execution note и SP07/wire/live evidence; Anthropic shim из `spike/anthropic-shim` — эксперимент, не security acceptance. DSH-диалог найден: «Таааак смотри Наша за (1)», `session-2ec1a145-845f-4944-8840-53509ccdf557`. Codex subscription transport подтверждён локально, но это не полная приёмка four-hop coding. Claude Code — в разработке; другие CLI — индивидуальная проверка; ChatGPT/Claude desktop — планы без обещанной даты.

Все интерактивы — синтетические, полностью локальные симуляции. Никаких uploads, доступа к файлам пользователя, вызовов модели или исполнения команд. Код доступен модели в разрешённом объёме: не обещаем скрыть бизнес-логику и одновременно анализировать её. Model proxy не заменяет sandbox/OS-политику.

## Проверка спроса, а не выдуманная конверсия

Форма создаёт отдельный `ops.ProductInterest`: product, role, harness, use_case — закрытые enum; email; consent_at/revision; created_at. Нет аккаунта, лицензии, счёта, оплаты или автоматического qualified_lead. Подтверждение только после DB INSERT и с короткоживущей подписанной product-only cookie. GET-параметр сам по себе не подтверждает заявку. CSRF, honeypot, лимит попыток, DB CHECK enum.

Просмотры двух URL остаются в существующей first-party таблице Visit. Это просмотры/суточные отпечатки, не недельные уникальные люди и не доказанная когортная конверсия. Заявки считаются отдельно по продукту; качество лидов требует разговора. Внешние counters/replay на страницах формы выключены, даже если раньше принято согласие: email не должен попасть в запись сессии. Метрика goals этим изменением не создаются и не отправляются.

Оператор видит заявки в штатной Django admin: `/<PSEUDEX_ADMIN_PATH>/ops/productinterest/`, с MFA и правом просмотра модели. Поля read-only; удаление по отдельному праву. Контакты не экспортируются провайдерам аналитики.

## Локальный просмотр

Из `storefront/`, с установленными зависимостями storefront:

```bash
export PSEUDEX_DEBUG=1
export PSEUDEX_SECRET_KEY=local-preview-only
export PSEUDEX_DB_PATH="$PWD/product-preview.sqlite3"
export PSEUDEX_ANALYTICS_MODE=off
export PSEUDEX_METRIKA_ID=''
export PSEUDEX_SITE_URL=http://127.0.0.1:18765
python manage.py migrate --noinput
python manage.py seed_plans
python manage.py runserver 127.0.0.1:18765
```

Не использовать production БД/ключи. Preview ничего не отправляет клиентам; тестовые заявки записываются только в локальную SQLite. Публикация и production migration — отдельное действие владельца.

Проверки:

```bash
python test_product_pages.py
python test_product_pages_browser.py --base-url http://127.0.0.1:18765
python test_acquisition_consent.py
python test_seo.py
```

Browser test разрешает только loopback HTTP и блокирует стороннюю сеть; проверяет responsive layout 320/390/768/1440, две темы, интерактивы, формы, confirmation, JS/CSP errors. Создаёт только синтетические контакты example.test. Изображения проверки в `.preview/` gitignored.

Официальные марки и их источники — `storefront/static/brands/README.md`. Серые логотипы показывают названия интеграций, не партнёрство и не пройденную приёмку.
