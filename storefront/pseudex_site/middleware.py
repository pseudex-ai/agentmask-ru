"""Подтверждение второго фактора, полученное от провайдера идентичности.

ЗАЧЕМ ОТДЕЛЬНЫМ СЛОЕМ, А НЕ ПРОВЕРКОЙ В КАЖДОМ МЕСТЕ. Второй фактор спрашивают
две независимые вещи: `OTPAdminSite` (админка) и `otp_required` (операторская
консоль `/ops/`). Если бы «SSO тоже считается» жило в каждой из них, две копии
одного правила разошлись бы молча — ровно так, как это уже случалось с CSP и
счётчиками (`pseudex_site/context.py`). Здесь правило одно: подтверждённый вход
превращается в `request.user.otp_device`, а его читают оба.

ПОЧЕМУ ЭТО НЕ ОСЛАБЛЕНИЕ. Флаг в сессии ставит ТОЛЬКО `PseudexOIDCBackend`, и
только когда в токене есть claim `amr` со вторым фактором. Нет claim — флага
нет, и человек вводит код из приложения. То есть обход TOTP возможен ровно
тогда, когда провайдер уже спросил второй фактор сам.

ЧЕГО ЗДЕСЬ НЕТ: доверия заголовку прокси. Заголовок подставляет любой, кто
дотянулся до витрины мимо Caddy; подписанный токен — нет.
"""
from django.conf import settings

from pseudex_site.oidc import SSO_MFA_SESSION_KEY


class _SSODevice:
    """Подтверждение от провайдера в форме, которую понимает django-otp.

    `is_verified()` в django-otp — это `otp_device is not None`, и больше
    ничего: класс нужен, чтобы объект вёл себя как устройство там, где его
    показывают (имя в интерфейсе), и не притворялся TOTP-устройством в базе.
    """

    persistent_id = "sso"
    name = "Authelia (SSO)"
    confirmed = True

    def __str__(self) -> str:
        return self.name


class SSOMfaMiddleware:
    """Проставляет подтверждённый второй фактор из SSO-сессии.

    СТОИТ СРАЗУ ПОСЛЕ `django_otp.middleware.OTPMiddleware` и обязан там
    остаться: тот читает устройство из сессии и ПЕРВЫМ выставляет
    `otp_device`, а этот лишь дополняет его, когда устройства нет.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            getattr(settings, "OIDC_ENABLED", False)
            and user is not None
            and user.is_authenticated
            and user.is_staff
            and request.session.get(SSO_MFA_SESSION_KEY)
            and getattr(user, "otp_device", None) is None
        ):
            user.otp_device = _SSODevice()
        return self.get_response(request)
