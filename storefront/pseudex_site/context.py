"""Настройки, которые шаблон обязан видеть, чтобы текст не разошёлся с кодом."""

from django.conf import settings


def analytics(request) -> dict[str, object]:
    """Режим аналитики — в каждый шаблон.

    ТЕКСТ НА ЛЕНДИНГЕ ГЕНЕРИРУЕТСЯ ИЗ НЕГО, а не пишется рядом. На странице
    стоит сильное обещание про отсутствие счётчиков и баннера; включить счётчик
    и оставить фразу значило бы опубликовать утверждение, не совпадающее с
    кодом. Тест, сравнивающий две копии, ловит расхождение; одна копия,
    выведенная из другой, не может разойтись вовсе.

    СКРИПТ НЕ ОТДАЁТСЯ НА ЗАКРЫТЫХ СТРАНИЦАХ. На экране кабинета префиксы
    ключей и суммы счетов; запись сессии сделала бы их копию, которую никто не
    заказывал. Решение продублировано в CSP (`middleware._policy_for`) — здесь
    шаблон, там заголовок, и одно без другого неполно.
    """
    private = (request.path.startswith("/app/")
               or request.path.startswith(f"/{settings.ADMIN_PATH}")
               or request.path.startswith("/accounts/"))
    return {"analytics": settings.ANALYTICS,
            "analytics_here": settings.ANALYTICS["mode"] != "off" and not private,
            "support_bot": settings.SUPPORT_BOT}
