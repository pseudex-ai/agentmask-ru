"""Measurement semantics: actions are not business outcomes.

The catalog is deliberately independent of tracking SDKs. Declaring an event
never makes it delivered. Consumers must report emitter, consent, attribution
and delivery readiness separately. Private-page facts come from the server;
no browser replay or arbitrary DOM/text payload is permitted there.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EventDefinition:
    identifier: str
    title: str
    kind: str
    source: str
    repetition: str
    interpretation: str
    external_default: bool = False


EVENTS = (
    EventDefinition("start_cta_click", "Нажатие Начать", "diagnostic", "public_browser", "action", "Намерение, не регистрация", True),
    EventDefinition("pricing_view", "Просмотр тарифов", "diagnostic", "public_browser", "document", "Фактическая видимость блока, не загрузка HTML", True),
    EventDefinition("plan_selected", "Выбран тариф", "diagnostic", "public_browser", "action", "Выбор, не покупка", True),
    EventDefinition("signup_attempt", "Попытка регистрации", "diagnostic", "public_browser", "action", "Валидная отправка формы, не созданный аккаунт", True),
    EventDefinition("signup", "Аккаунт создан", "acquisition", "public_browser", "document", "Серверный успешный ответ; повторная отправка письма исключена", True),
    EventDefinition("signup_rejected", "Регистрация отклонена", "friction", "server", "attempt", "Только закрытый код причины, без введённых данных"),
    EventDefinition("activation_email_resent", "Повторно запрошено письмо", "friction", "server", "attempt", "Не подтверждает доставку или прочтение письма"),
    EventDefinition("activated", "Подтверждена почта", "acquisition", "server", "organisation", "Не выдача ключа и не запуск продукта"),
    EventDefinition("key_issued", "Выдан ключ", "activation", "server", "organisation", "Только факт, ни ключа, ни его префикса в аналитике"),
    EventDefinition("first_lease", "Замечено подключение контейнера", "activation", "server", "organisation", "Почасовое наблюдение; не точное время первого запуска"),
    EventDefinition("first_mask", "Замечен первый маскированный запрос", "activation", "server", "organisation", "Не доказательство правильного действия инструмента"),
    EventDefinition("qualified_lead", "Подтверждён подходящий проект", "business", "first_party_review", "opportunity", "Ручная квалификация по проверяемым критериям, не клик контакта"),
    EventDefinition("successful_agent_loop", "Принят рабочий агентный сценарий", "business", "first_party_review", "acceptance", "Приёмка результата инструмента; без диалогов и значений клиента"),
    EventDefinition("integration_copy", "Скопирована инструкция", "diagnostic", "public_browser", "action", "Clipboard успешно завершён, не внедрение", True),
    EventDefinition("docs_open", "Переход к документации", "diagnostic", "public_browser", "action", "Фиксированный раздел, не произвольный URL", True),
    EventDefinition("content_engaged", "Содержательное чтение раздела", "diagnostic", "public_browser", "document_section", "Заголовок увиден и 20 секунд в активной вкладке; не доказательство понимания", True),
    EventDefinition("faq_open", "Открыт ответ FAQ", "diagnostic", "public_browser", "document_question", "Явное раскрытие посетителем; без текста вопроса", True),
    EventDefinition("setup_video_started", "Начат просмотр настройки", "diagnostic", "public_browser", "document", "Явное воспроизведение, не автозагрузка видео", True),
    EventDefinition("setup_video_completed", "Досмотрена инструкция", "diagnostic", "public_browser", "document", "Реально проиграно не менее 80% и достигнут конец; не выполненная настройка", True),
    EventDefinition("configurator_used", "Выбраны требования к данным", "diagnostic", "public_browser", "action", "Факт выбора, без категорий, значений и текста клиента", True),
    EventDefinition("coverage_gap_submitted", "Отправлен запрос недостающего типа", "diagnostic", "server", "accepted_request", "Успех сервера, не нажатие кнопки; не квалифицированная заявка"),
    EventDefinition("enterprise_contact_click", "Клик контакта Enterprise", "diagnostic", "public_browser", "action", "Не полученное письмо или лид", True),
    EventDefinition("support_contact_click", "Клик поддержки", "diagnostic", "public_browser", "action", "Причину обращения не выводить из одного клика", True),
    EventDefinition("checkout_started", "Получена ссылка оплаты", "commerce", "server", "request", "Успешный запрос ссылки; повтор не обязательно новая попытка или списание"),
    EventDefinition("checkout_unavailable", "Не удалось начать оплату", "friction", "server", "request", "Ошибка подготовки оплаты, не отказ банка и не потерянный клиент"),
    EventDefinition("payment_failed", "Замечен отказ оплаты", "friction", "server", "observation", "Проверенный статус при возврате; повторные наблюдения не уникальные платежи"),
    EventDefinition("paid", "Первая подтверждённая оплата", "business", "server", "organisation", "Реальная конечная сумма первого оплаченного счёта; не повторный вебхук"),
    EventDefinition("repeat_payment", "Повторная подтверждённая оплата", "commerce", "server", "invoice", "Не каждая повторная оплата является продлением"),
    EventDefinition("renewal_paid", "Оплачено продление", "retention", "server", "invoice", "Только подтверждённый новый период; не смена тарифа или перерасход"),
    EventDefinition("refund_confirmed", "Подтверждён возврат", "commerce", "server", "refund", "Отдельный денежный факт; не отрицательная фиктивная paid-конверсия"),
    EventDefinition("paid_service_pending", "Оплачено, доступ ещё не восстановлен", "operations", "server", "incident", "Состояние биллинга, не провал платежа"),
    EventDefinition("usage_retained", "Подтверждено продолжение использования", "retention", "server", "cohort_window", "По положительному изменению счётчиков, неизвестное окно не ноль"),
    EventDefinition("usage_stalled", "Использование перестало расти", "retention", "server", "observation_window", "Диагностический сигнал, не доказанный отток"),
    EventDefinition("subscription_cancelled", "Отменено продление", "retention", "server", "transition", "Не равнозначно немедленному прекращению оплаченного доступа"),
)
BY_ID = {event.identifier: event for event in EVENTS}
if len(BY_ID) != len(EVENTS):
    raise ValueError("Duplicate acquisition event identifier")

# These are boundaries of interpretation, not permission to collect or export.
PUBLIC_SECTIONS = frozenset({
    "home", "pricing", "how", "architecture", "detection", "types",
    "litellm", "knowledge_base", "knowledge_article", "faq", "team",
    "offer", "privacy", "requisites", "setup",
})
FRICTION_REASONS = frozenset({
    "validation", "rate_limited", "account_exists", "disposable_email",
    "terms_missing", "consent_missing", "plan_unavailable", "expired_link",
    "provider_declined", "provider_unavailable", "service_pending", "unknown",
})
