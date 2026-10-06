"""Вход сотрудников в админку и /ops/ через Authelia (OpenID Connect).

ЗАЧЕМ ЭТО ВООБЩЕ. До сих пор внутренние точки закрыты паролем Django и TOTP
(`django_otp`, `OTPAdminSite`). Это работает и остаётся, но у команды теперь
есть один портал идентичности на все инструменты, и вторая учётка только ради
админки — лишняя дверь, которую надо помнить и ротировать отдельно.

ЧЕГО ЗДЕСЬ СОЗНАТЕЛЬНО НЕТ: доверия заголовку прокси. Вариант «Caddy ставит
`X-Remote-User`, Django верит» выглядит проще всего и является дырой: любой,
кто дотянется до витрины мимо Caddy, войдёт как staff. Никаких доверенных
заголовков — только подписанный токен провайдера.

ВТОРОЙ ФАКТОР НЕ ОТМЕНЯЕТСЯ, А ПЕРЕЕЗЖАЕТ. Пропустить django-otp можно ТОЛЬКО
когда провайдер сам подтвердил второй фактор — то есть в токене есть claim
`amr` (RFC8176) со значением второго фактора. Нет claim — нет пропуска, и
человек вводит код из приложения, как раньше. Это «fail closed»: недоказанное
MFA считается отсутствующим.
"""
import logging

from django.contrib.auth import get_user_model
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

logger = logging.getLogger("pseudex.oidc")

# Ключ сессии: «этот вход прошёл второй фактор у провайдера».
SSO_MFA_SESSION_KEY = "pseudex_sso_mfa"

# RFC8176 Authentication Method Reference, и список ВЗЯТ ИЗ ДОКУМЕНТАЦИИ AUTHELIA,
# а не из общих соображений: https://www.authelia.com/reference/guides/authentication-method-references/
# Первый фактор — `pwd`; всё перечисленное ниже означает, что провайдер спросил
# что-то ЕЩЁ. Значения, которых Authelia не эмитит (`webauthn`, `totp`, `tel`),
# здесь не нужны: список, выглядящий шире реальности, прячет, что он на самом
# деле не сработал.
MFA_AMR = frozenset({
    "mfa",   # пользователь вошёл более чем одним фактором
    "mca",   # более чем одним каналом
    "otp",   # TOTP
    "pop",   # ключ владения, программный или аппаратный
    "hwk",   # аппаратный ключ
    "swk",   # программный ключ
    "sms",   # Duo
})


class PseudexOIDCBackend(OIDCAuthenticationBackend):
    """Пускать только существующих сотрудников; второй фактор — из токена."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._claims = {}

    def get_userinfo(self, access_token=None, id_token=None, payload=None, **kwargs):
        """Профиль — из двух источников, и у каждого своя роль.

        `amr` (подтверждён ли второй фактор) и `sub` приходят ТОЛЬКО в
        подписанном ID-токене, который библиотека уже проверила вместе с nonce.
        Адрес почты Authelia отдаёт в ответе userinfo — без него пользователь не
        находится вовсе: проверено на живом входе, `amr` приходил, а `email` нет,
        и вход молча никого не находил.

        ПОДПИСАННОЕ НЕ ПЕРЕТИРАЕТСЯ: чужой ответ дописывается только туда, где
        пусто. Поэтому второй фактор по-прежнему берётся из проверенного
        источника, а не из неподписанного JSON.
        """
        claims = dict(payload or {})
        if not claims.get("email"):
            try:
                extra = super().get_userinfo(access_token, id_token, payload)
                for key, value in (extra or {}).items():
                    claims.setdefault(key, value)
            except Exception:  # noqa: BLE001 — вход не должен падать из-за профиля
                logger.warning("userinfo недоступен, полагаемся на ID-токен")
        # Кладём рядом: authenticate() смотрит сюда после super(), потому что сам
        # метод возвращает только пользователя.
        self._claims = claims
        return claims

    def filter_users_by_claims(self, claims):
        """Сопоставление ТОЛЬКО по email, и только среди действующих staff.

        `OIDC_CREATE_USER = False` (settings): неизвестный адрес не заводит
        аккаунт. Сотрудник появляется в витрине раньше, чем в Authelia, и это
        осознанный порядок — SSO не должен уметь создавать доступ к ПД.
        """
        email = (claims.get("email") or "").strip()
        if not email:
            return get_user_model().objects.none()
        return get_user_model().objects.filter(
            email__iexact=email, is_staff=True, is_active=True,
        )

    def authenticate(self, request, **kwargs):
        user = super().authenticate(request, **kwargs)
        # Диагностика: видно, что именно провайдер положил в токен. Без этого
        # «SSO пустил, но админка спрашивает код» неотличимо от «amr не пришёл».
        logger.info("oidc amr=%s mfa=%s user=%s", self._claims.get("amr"),
                    self._mfa_confirmed(), bool(user))
        if user is not None and request is not None and self._mfa_confirmed():
            request.session[SSO_MFA_SESSION_KEY] = True
        return user

    def _mfa_confirmed(self) -> bool:
        amr = self._claims.get("amr") or []
        if isinstance(amr, str):
            amr = [amr]
        return bool(MFA_AMR.intersection(str(a).lower() for a in amr))
