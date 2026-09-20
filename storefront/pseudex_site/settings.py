"""Storefront settings.

READ THIS BEFORE ADDING A FIELD, A LOG LINE OR AN INTEGRATION.

This service must never receive personal data belonging to a customer's
customers. Not in a form, not in a support attachment, not in an error report.
That is not a privacy preference — it is what keeps us outside the perimeter
under 152-ФЗ, and it is the thing the product sells. Every setting below that
looks unusually strict is strict for that reason:

  * no third-party error reporter that would ship request bodies off-box;
  * no analytics that would beacon from a page a logged-in customer is on;
  * `DEBUG` cannot be enabled by accident in production, because a Django error
    page prints the whole request.

Anything a customer might paste that could contain personal data belongs in
their own local interface, on port 8081, inside their contour.
"""

import os

from django.core.exceptions import ImproperlyConfigured
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


# --- core ----------------------------------------------------------------

# No default in production. A framework that ships a working secret key is a
# framework where someone forgets to set one, and session forgery follows.
SECRET_KEY = _env("PSEUDEX_SECRET_KEY")
DEBUG = _flag("PSEUDEX_DEBUG", False)
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("PSEUDEX_SECRET_KEY must be set when DEBUG is off")
    SECRET_KEY = "dev-only-not-a-secret"

ALLOWED_HOSTS = [host for host in _env("PSEUDEX_ALLOWED_HOSTS", "").split(",") if host]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Django needs the scheme here, and a bare hostname silently fails CSRF on POST.
CSRF_TRUSTED_ORIGINS = [
    origin for origin in _env("PSEUDEX_CSRF_ORIGINS", "").split(",") if origin
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    # Второй фактор для внутренних админ-точек (админка + /ops/): один пароль
    # больше не открывает доступ к ПД клиентов. Только TOTP-плагин — статические
    # коды и прочие устройства не заводим, чтобы поверхность была минимальной.
    "django_otp",
    "django_otp.plugins.otp_totp",
    "accounts",
    "billing",
    "storefront_web",
    "ops",
]

MIDDLEWARE = [
    # ПЕРВЫМ В СПИСКЕ, И ЭТО СУЩЕСТВЕННО. Всё, что логируется в middleware
    # выше по списку, идентификатора запроса уже не получит — а именно там
    # живут отказы безопасности, которые интереснее всего связать с запросом.
    "pseudex_site.logfmt.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # СРАЗУ ПОСЛЕ AuthenticationMiddleware: читает из сессии подтверждённое
    # OTP-устройство и выставляет request.user.is_verified(). Без него ни
    # OTPAdminSite, ни otp_required на /ops/ не увидят второй фактор.
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "storefront_web.middleware.SecurityHeadersMiddleware",
    # СРАЗУ ЗА ЗАГОЛОВКАМИ, ПЕРЕД АНАЛИТИКОЙ. Соседство здесь ничего не решает:
    # `AnalyticsMiddleware` записывает только `200`, поэтому ни 404, который сюда
    # приходит, ни 301, который отсюда уходит, визитом не станут. А сама она
    # остаётся последней, как и было задумано, — «считает только то, что
    # действительно отдано».
    "storefront_web.middleware.TrailingSlashRedirectMiddleware",
    "storefront_web.middleware.AnalyticsMiddleware",
]

ROOT_URLCONF = "pseudex_site.urls"
WSGI_APPLICATION = "pseudex_site.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "pseudex_site.context.analytics",
    ]},
}]

# SQLite by default so a developer (and the smoke test) needs no database
# server; Postgres in production via the URL.
if _env("PSEUDEX_DB_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _env("PSEUDEX_DB_NAME", "pseudex"),
        "USER": _env("PSEUDEX_DB_USER", "pseudex"),
        "PASSWORD": _env("PSEUDEX_DB_PASSWORD"),
        "HOST": _env("PSEUDEX_DB_HOST"),
        "PORT": _env("PSEUDEX_DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _env("PSEUDEX_DB_PATH", str(BASE_DIR / "storefront.sqlite3")),
    }}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True
# "11900 ₽" on a price card and on a счёт reads as a typo. With ru-ru this
# groups by a non-breaking space and keeps the decimal comma, which is the
# form an accountant reconciles against a bank statement.
USE_THOUSAND_SEPARATOR = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- auth ----------------------------------------------------------------

SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Email only, and a link rather than a password. The sign-up form asks for one
# thing because every additional field is a place to lose someone on the way to
# the single metric this site is measured by — fifteen minutes to the first
# masked request. A password would also be a credential we then have to hold.
# ИМЕНА НАСТРОЕК ЗДЕСЬ — ДЕЙСТВУЮЩИЕ ДЛЯ УСТАНОВЛЕННОЙ ВЕРСИИ, И ЭТО ПРОВЕРЯЕТСЯ,
# А НЕ ПОМНИТСЯ. На 65.3.1 тут стояли `ACCOUNT_LOGIN_METHODS`/`SIGNUP_FIELDS` —
# API БОЛЕЕ ПОЗДНЕЙ версии: та версия таких имён не знала, конфигурация была
# молча инертна, allauth работал на умолчаниях (вход по username) против модели,
# где `username` нет, и страница входа отдавала 500 — единственный путь клиента
# обратно в кабинет. Набор это пережил, потому что все тесты входят через
# `force_login()` и ту страницу не рисуют.
#
# Теперь мы на 65.19.3, и имена вернулись к новым — но уже ПОСЛЕ проверки:
# `manage.py check` на старых ругался «deprecated», а тесты подтвердили, что
# новые действуют. При следующем апгрейде — так же: сверить по `check` и по
# `app_settings.py`, а не по памяти.
ACCOUNT_LOGIN_METHODS = {"email"}
# БЕЗ ПОЛЕЙ ПАРОЛЯ, И ЭТО НЕ КОСМЕТИКА. Вход у клиента — код из письма, пароля
# нет вовсе; устаревшая пара ACCOUNT_EMAIL_REQUIRED/USERNAME_REQUIRED выводила
# отсюда `['email*','password1*','password2*']`, то есть описывала продукт,
# которого нет.
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
# ЕДИНСТВЕННЫЙ способ входа клиента, поэтому окно жизни кода — по реальной
# доставке письма, а не по умолчанию в три минуты: письмо, пришедшее на четвёртой
# (серый список у принимающей стороны — обычное дело), оставляло бы клиента за
# дверью с валидным кодом в руках. Десять минут. Имя настройки сверено с
# `allauth/account/app_settings.py` (LOGIN_BY_CODE_TIMEOUT), а не по памяти;
# `LOGIN_BY_CODE_SUPPORTS_RESEND` в 65.3.1 НЕ существует — задавать нельзя,
# молча не сработает.
ACCOUNT_LOGIN_BY_CODE_TIMEOUT = 600
# ПОВТОРНАЯ ОТПРАВКА КОДА — НАТИВНАЯ, А НЕ САМОДЕЛЬНАЯ. До 65.15 её в allauth не
# было вовсе, и «письмо не пришло» приходилось лечить сбросом входа; теперь это
# штатный переход, а счётчик держит сервер. Число — это МАКСИМУМ повторов на
# один вход (`True` означало бы 2); поверх него продолжает работать временной
# лимит ACCOUNT_RATE_LIMITS['request_login_code'].
ACCOUNT_LOGIN_BY_CODE_SUPPORTS_RESEND = 3
# ПУСТОЙ ПРЕФИКС ТЕМЫ, А НЕ УМОЛЧАНИЕ. При `None` allauth подставляет в тему имя
# объекта Site, а он в базе стоит дефолтный django — клиент получал бы письмо
# «[example.com] Код для входа». Тему и текст письма пишем сами
# (`templates/account/email/login_code_*`), не наследуясь от обёртки allauth,
# которая тоже тянет site_name. Имя настройки сверено с app_settings.py:206.
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_RATE_LIMITS = {
    # The sign-in form is the one unauthenticated write on the site.
    "login_failed": "5/5m",
    # ИМЯ КЛЮЧА ПРОВЕРЕНО ПО ИСХОДНИКАМ УСТАНОВЛЕННОГО allauth, а не по памяти:
    # `app_settings.py:196` называет его `request_login_code`. Прежнее
    # `login_by_code_request` не существует, а RATE_LIMITS сливается поверх
    # умолчаний — то есть настройка молча не действовала, и работал дефолт
    # 20/m/ip,3/m/key. Ровно тот же промах, что уже описан выше в этом файле
    # про ACCOUNT_LOGIN_METHODS.
    "request_login_code": "3/5m",
}
LOGIN_REDIRECT_URL = "/app/"
LOGOUT_REDIRECT_URL = "/"

EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if _env("PSEUDEX_SMTP_HOST")
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = _env("PSEUDEX_SMTP_HOST")
EMAIL_PORT = int(_env("PSEUDEX_SMTP_PORT", "587"))
EMAIL_HOST_USER = _env("PSEUDEX_SMTP_USER")
EMAIL_HOST_PASSWORD = _env("PSEUDEX_SMTP_PASSWORD")
EMAIL_USE_TLS = _flag("PSEUDEX_SMTP_TLS", True)
DEFAULT_FROM_EMAIL = _env("PSEUDEX_FROM_EMAIL", "pseudex <noreply@pseudex.ru>")

# --- transport security --------------------------------------------------

# Behind a TLS-terminating proxy, so Django learns the real scheme from the
# header the proxy sets. Without it `request.is_secure()` is False, the secure
# cookie flags below never apply, and a session cookie goes out in the clear.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
# Sessions are short: this account can stop a production gateway.
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# --- pseudex ------------------------------------------------------------

# The licensing server's ADMIN app, which is never published. This is the only
# outbound call the storefront makes, and it carries an org id and a status —
# never anything about a customer's traffic.
LICENSING_ADMIN_URL = _env("PSEUDEX_LICENSING_ADMIN_URL", "http://127.0.0.1:9443")

# АБСОЛЮТНЫЙ АДРЕС ВИТРИНЫ ДЛЯ ПИСЕМ, ОТПРАВЛЕННЫХ НЕ ИЗ ЗАПРОСА. Всё, что шлёт
# почту из вьюхи, строит ссылку через `request.build_absolute_uri`; у
# планировщика запроса нет, а ссылка в счёте обязана быть кликабельной.
SITE_URL = _env("PSEUDEX_SITE_URL", "http://127.0.0.1:8000").rstrip("/")
# Общий секрет с админкой лицензионного сервера. Сетевая изоляция 9443 — первый
# замок, этот второй: витрина смотрит в интернет, и её компрометация не должна
# сразу означать выпуск ключей.
# Витрина ходит МЕНЬШИМ токеном: ей нужны пять ручек из одиннадцати, и ни одна
# из них не массовая. Полный токен здесь не должен лежать вовсе — витрина
# единственная смотрит в интернет.
LICENSING_ADMIN_TOKEN = _env("PSEUDEX_LICENSE_STOREFRONT_TOKEN", "")
LICENSING_CA = _env("PSEUDEX_LICENSING_CA", "")

YOOKASSA_SHOP_ID = _env("PSEUDEX_YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = _env("PSEUDEX_YOOKASSA_SECRET_KEY")

# ЭКВАЙРИНГ (оплата картой) — ЯВНЫЙ РУБИЛЬНИК, ПО УМОЛЧАНИЮ ВЫКЛЮЧЕН.
#
# Пока эквайринг не одобрен провайдером, карту нельзя предлагать на проде, даже
# если ключи ЮKassa настроены. Флаг по умолчанию OFF — «предохранитель снят
# осознанно»: карта включается ТОЛЬКО когда `PSEUDEX_ACQUIRING_ENABLED=1` явно
# задан в окружении. Одобрят эквайринг — ставим 1, деплой её включает. Так
# прод не показывает карту без флага, а счёт по реквизитам работает всегда.
ACQUIRING_ENABLED = _env("PSEUDEX_ACQUIRING_ENABLED", "0") == "1"

# Our own details, printed on every счёт and акт. Configuration rather than a
# template literal: they change (a bank, an address, an ОГРН correction) and a
# change to a legal requisite must not require a deploy of the whole site.
SELLER = {
    # NO PLAUSIBLE DEFAULT. This used to fall back to "ООО «Вейлгейт»" — an
    # entity that does not exist, under a brand we no longer use, printed as the
    # ИСПОЛНИТЕЛЬ on a document that goes to a customer's accountant. A missing
    # requisite must look missing: the printable form says so in red and the
    # invoice cannot be presented for payment, which is the correct outcome
    # until the real ИП details are configured.
    # РЕДАКЦИЯ СОГЛАСИЯ. Меняется вместе с текстом на /consent и записывается в
    # каждую организацию: согласие даётся на конкретную редакцию, и без её
    # номера нельзя ответить, на что именно человек соглашался.
    "consent_revision": _env("PSEUDEX_CONSENT_REVISION", "2026-09-14"),
    "name": _env("PSEUDEX_SELLER_NAME", ""),
    "inn": _env("PSEUDEX_SELLER_INN", ""),
    "kpp": _env("PSEUDEX_SELLER_KPP", ""),
    "ogrn": _env("PSEUDEX_SELLER_OGRN", ""),
    "address": _env("PSEUDEX_SELLER_ADDRESS", ""),
    "bank": _env("PSEUDEX_SELLER_BANK", ""),
    "bik": _env("PSEUDEX_SELLER_BIK", ""),
    "account": _env("PSEUDEX_SELLER_ACCOUNT", ""),
    "corr_account": _env("PSEUDEX_SELLER_CORR_ACCOUNT", ""),
    # УСН by default: a company on the simplified system must NOT print a VAT
    # line, and printing "НДС не облагается" when it does not apply is just as
    # wrong. Stated explicitly so nobody guesses.
    "vat": _env("PSEUDEX_SELLER_VAT", "Без НДС (УСН)"),
    # Where a subject of personal data sends a request under 152-ФЗ.
    # The policy is not publishable without it.
    "email": _env("PSEUDEX_SELLER_EMAIL", ""),
    # Телефон печатается на странице реквизитов: ст. 26.1 ЗоЗПП требует, чтобы
    # покупатель видел, с кем имеет дело, ДО оплаты, а один email этого не даёт.
    "phone": _env("PSEUDEX_SELLER_PHONE", ""),
}

# ОБРАЗ, КОТОРЫЙ САЙТ СОВЕТУЕТ КЛИЕНТУ, — ИЗ РЕЕСТРА ВЕРСИЙ (D-061). Репозиторий
# образа — здесь; ТЕГ — плавающий минор новейшего цикла из deploy/releases.json,
# копию которого агент выкатки кладёт рядом (PSEUDEX_RELEASES_FILE). Клиент на
# `pseudex:0.3` получает патчи одним `docker pull`, а шаг на минор остаётся
# осознанным. Раньше тег стоял руками (`…:1.0.0`, которого в реестре не было),
# потом выводился из VERSION платформы — и оба раза врал. PSEUDEX_DOCKER_IMAGE
# остаётся только как ручной override: задан — показывается как есть.
DOCKER_IMAGE_REPO = _env("PSEUDEX_DOCKER_REPO", "cr.yandex/pseudex/pseudex")
RELEASES_FILE = _env("PSEUDEX_RELEASES_FILE", "")
DOCKER_IMAGE = _env("PSEUDEX_DOCKER_IMAGE", "")

# Адрес сервера лицензий, который витрина ПОКАЗЫВАЕТ в команде запуска. Пусто —
# значит образ возьмёт своё боевое умолчание и лишняя переменная в команде не
# нужна. Заполнено — команда получает `-e PSEUDEX_LICENSE_URL=…`.
#
# Появилось после прогона персон: локальный стенд раздавал БОЕВУЮ команду, образ
# честно шёл на license.pseudex.ru, домена ещё нет, и все трое упёрлись в стену,
# которой у настоящего клиента не будет. Витрина должна говорить то, что знает
# про себя, а не то, что верно где-то ещё.
LICENSE_URL = _env("PSEUDEX_LICENSE_URL", "")

# Our back office. Configurable because a fixed /admin/ is the first path every
# scanner tries; moving it is not security, but it removes the background noise
# that hides a real attempt in the logs.
ADMIN_PATH = _env("PSEUDEX_ADMIN_PATH", "admin").strip("/")

# Имя эмитента в приложении-аутентификаторе: строка «pseudex (email)» вместо
# голого email. Только визуал, на проверку кода не влияет.
OTP_TOTP_ISSUER = "pseudex"

# JSON В КОНТЕЙНЕРЕ, ЧИТАЕМЫЙ ТЕКСТ ЛОКАЛЬНО. Loki ищет по ПОЛЯМ; строка, из
# которой смысл надо выковыривать регуляркой, превращает его в grep с
# веб-интерфейсом. Но JSON в терминале при разработке мешает, и заставлять себя
# читать его — верный способ перестать читать логи вовсе.
_LOG_JSON = _env("PSEUDEX_LOG_JSON", "") == "1"

# ── ПРОДУКТОВАЯ АНАЛИТИКА (Rybbit) ──────────────────────────────────────────
#
# ДВА РЕЖИМА, И ВЫБОР МЕЖДУ НИМИ — ЭТО ВЫБОР ТЕКСТА НА ЛЕНДИНГЕ, а не только
# настройка. На странице стоит сильное обещание: «аналитики и счётчиков на
# сайте нет вообще… поэтому нет и баннера». Включить счётчик и оставить эту
# фразу значило бы опубликовать утверждение, не совпадающее с кодом, — ровно
# то, ради чего в этом репозитории живёт `test_published_claims`.
#
# ПОЭТОМУ ТЕКСТ ГЕНЕРИРУЕТСЯ ИЗ РЕЖИМА, А НЕ ПИШЕТСЯ РЯДОМ С НИМ. Тест,
# сравнивающий две копии, ловит расхождение; одна копия, выведенная из другой,
# не может разойтись вовсе.
#
#   off   ничего не грузится. Остаётся только серверный счёт визитов.
#   full  Rybbit (свой, на нашем хосте): записи сессий, клики, воронки между
#         визитами. Скрипт хранит идентификатор посетителя в браузере, и
#         это ТРЕБУЕТ баннера согласия — шаблон его показывает не по доброй
#         воле, а потому что режим его включает.
#
# РЕЖИМА «cookieless» БОЛЬШЕ НЕТ. Он существовал у PostHog (persistence:
# memory); у Rybbit идентификатор в localStorage не отключается, а обещать
# «ничего не храним в браузере» и хранить — это ровно та ложь, от которой
# этот блок защищает. Меньше режимов — меньше текста, который может соврать.
_ANALYTICS_MODE = _env("PSEUDEX_ANALYTICS_MODE", "off")
if _ANALYTICS_MODE not in ("off", "full"):
    raise ImproperlyConfigured(
        f"PSEUDEX_ANALYTICS_MODE={_ANALYTICS_MODE!r}: допустимы off и full. "
        "Неизвестное значение молча выключило бы аналитику, и обнаружилось бы "
        "это через месяц пустых графиков."
    )

_ANALYTICS_HOST = _env("PSEUDEX_ANALYTICS_HOST", "")
_ANALYTICS_KEY = _env("PSEUDEX_ANALYTICS_KEY", "")
if _ANALYTICS_MODE != "off" and not (_ANALYTICS_HOST and _ANALYTICS_KEY):
    raise ImproperlyConfigured(
        f"PSEUDEX_ANALYTICS_MODE={_ANALYTICS_MODE}, но нет "
        "PSEUDEX_ANALYTICS_HOST/PSEUDEX_ANALYTICS_KEY. Пустые значения дали бы "
        "страницу, которая ОБЕЩАЕТ аналитику в тексте и не грузит её."
    )

ANALYTICS = {
    "mode": _ANALYTICS_MODE,
    "host": _ANALYTICS_HOST,
    "key": _ANALYTICS_KEY,
    "stores_id": _ANALYTICS_MODE == "full",
    "records_sessions": _ANALYTICS_MODE == "full",
}

# ── ЯНДЕКС.МЕТРИКА ──────────────────────────────────────────────────────────
#
# ПУСТО ЗНАЧИТ «НЕ СТАВИТЬ СЧЁТЧИК», И ЭТО СОСТОЯНИЕ ПО УМОЛЧАНИЮ. На лендинге
# стоит обещание «чужих счётчиков нет — ни Метрики, ни Google Analytics», и
# текст FAQ ВЫВЕДЕН ИЗ ЭТОЙ ЖЕ НАСТРОЙКИ (`templates/landing.html`): пока
# счётчика нет, обещание — правда; когда он появится, текст сменится сам.
# Две копии одного решения разошлись бы; одна, выведенная из другой, — нет.
#
# ПОЧЕМУ ОТДЕЛЬНАЯ НАСТРОЙКА, А НЕ РЕЖИМ `ANALYTICS`. `ANALYTICS` — про наш
# Rybbit: либо он есть на публичных страницах, либо его нет вовсе. Метрика
# живёт по другим правилам: она третья сторона, её можно включить при
# выключенном Rybbit и наоборот. Смешать их в одном значении значило бы
# потерять ровно ту разницу, ради которой этот блок и написан.
#
# СЧЁТЧИК СТОИТ ТОЛЬКО НА ПУБЛИЧНЫХ СТРАНИЦАХ. Граница та же, что у нашей
# аналитики, и решают её те же два места: `pseudex_site/context.py` (шаблон) и
# `storefront_web/middleware._policy_for` (CSP). В кабинете на экране префиксы
# ключей и суммы счетов, и запись визита сделала бы их копию, которую никто не
# заказывал.
#
# МЕТРИКА — ТРЕТЬЯ СТОРОНА, И ЭТО НЕ ДЕТАЛЬ: данные посетителей уходят в
# Яндекс. Поэтому её включение требует упоминания в политике обработки
# (`/policy`), а не только строки в `.env`.
METRIKA_ID = _env("PSEUDEX_METRIKA_ID", "")
if METRIKA_ID and not METRIKA_ID.isdigit():
    raise ImproperlyConfigured(
        f"PSEUDEX_METRIKA_ID={METRIKA_ID!r}: номер счётчика — только цифры. "
        "Опечатка дала бы тег, который выглядит установленным и молча не "
        "считает ничего; заметили бы это по пустым графикам через месяц."
    )

# ── ЯНДЕКС: OAUTH ДЛЯ API ───────────────────────────────────────────────────
#
# ЭТО НЕ СЧЁТЧИК, А ДОСТУП К ДАННЫМ ОТ ИМЕНИ ВЛАДЕЛЬЦА. `PSEUDEX_METRIKA_ID`
# выше отвечает на вопрос «показывать ли счётчик посетителю»; эти три — на
# вопрос «имеем ли мы право читать статистику и управлять кампаниями». Счётчик
# может стоять без них, и они могут стоять без счётчика.
#
# ЧТО ЗДЕСЬ ЛЕЖИТ И ЧЕГО ЗДЕСЬ НЕТ. ClientID и Client secret — это ПРИЛОЖЕНИЕ,
# они не дают доступа ни к чему, пока владелец не выдал токен. Refresh-токен —
# это уже доступ: он обменивается на access-токен без участия человека и
# действует, пока владелец не отзовёт приложение. Поэтому его кладут в `.env`
# (как пароль), а access-токен НЕ кладут никуда: он получается из refresh при
# каждом холодном старте и живёт в памяти процесса. Секрет, который можно
# переполучить, не должен переживать процесс — иначе он переживёт и отзыв.
YANDEX_OAUTH_CLIENT_ID = _env("YANDEX_OAUTH_CLIENT_ID", "")
YANDEX_OAUTH_CLIENT_SECRET = _env("YANDEX_OAUTH_CLIENT_SECRET", "")
YANDEX_OAUTH_REFRESH_TOKEN = _env("YANDEX_OAUTH_REFRESH_TOKEN", "")

# ОТСУТСТВИЕ ТОКЕНА — ЭТО НЕ ОШИБКА ЗАПУСКА, А ВЫКЛЮЧЕННАЯ ИНТЕГРАЦИЯ. Витрина
# обязана подниматься на машине, где Яндекса нет вовсе (разработка, чужой
# стенд), и `docs/tz-site.md` запрещает делать чужой сервис условием своего
# старта. Ошибка здесь — только ПОЛОВИНА НАСТРОЙКИ: refresh без пары
# client_id/secret не обменивается ни на что и выглядит как рабочий до первого
# обращения, а это ровно тот молчаливый отказ, который ищут по логам день.
if YANDEX_OAUTH_REFRESH_TOKEN and not (
    YANDEX_OAUTH_CLIENT_ID and YANDEX_OAUTH_CLIENT_SECRET
):
    raise ImproperlyConfigured(
        "YANDEX_OAUTH_REFRESH_TOKEN задан, а YANDEX_OAUTH_CLIENT_ID/"
        "YANDEX_OAUTH_CLIENT_SECRET — нет. Refresh-токен без пары приложения "
        "не обменивается ни на что; интеграция выглядела бы включённой и "
        "молча не работала."
    )

# ОТПРАВКА КОНВЕРСИЙ — ОТДЕЛЬНОЕ РЕШЕНИЕ, А НЕ СЛЕДСТВИЕ НАЛИЧИЯ ТОКЕНА.
#
# ЧТО ЗДЕСЬ НЕ ТАК БЕЗ ЭТОГО ФЛАГА. Счётчик спрашивает согласие баннером, и
# раздел 9bis политики обещает: «без ответа не загружается ни один счётчик»,
# а раздел 6 — что сведения о посещении уходят в Метрику «с отдельным
# согласием». Офлайн-конверсия уходит С СЕРВЕРА и на выбор посетителя не
# смотрит вовсе: отказавшийся «Не считать» всё равно получил бы передачу
# факта своей регистрации в Яндекс, привязанную к клику по объявлению.
#
# То есть механизм, включённый одним лишь токеном, молча разошёлся бы с
# опубликованным документом — а политику читает служба безопасности клиента,
# и расхождение с ней дороже любой строки здесь.
#
# ПОЧЕМУ ФЛАГ, А НЕ ГЕЙТ ПО СОГЛАСИЮ. Выбор посетителя живёт в браузере
# (localStorage) и на сервер не приходит; чтобы его соблюсти, его надо
# провести через форму регистрации и хранить у организации — это отдельная
# работа и отдельное решение о правовом основании, которое принимает
# Оператор, а не код. Флаг делает передачу ЯВНОЙ: пока он не поднят, ничего
# не уходит, и «мы не знали» перестаёт быть возможным.
YANDEX_CONVERSIONS = _flag("PSEUDEX_YANDEX_CONVERSIONS", False)

# ТОКЕН МАШИННОГО ДОСТУПА К OPS-API. Страницы консоли закрыты сессией staff +
# TOTP — это правильно для человека и неприменимо к боту: у бота нет ни
# пароля, ни второго фактора, и заводить ему staff-аккаунт значило бы выдать
# ему весь биллинг ради одного отчёта. Отдельный токен даёт РОВНО те
# эндпоинты, что перечислены в `ops/urls.py` под `_ops_api_gate`, и ничего
# больше; пусто — машинного доступа нет.
OPS_API_TOKEN = _env("PSEUDEX_OPS_API_TOKEN", "")

# БОТ ПОДДЕРЖКИ НА ЛЕНДИНГЕ. Решение от 29.08.2026 (docs/decisions.md):
# поддержка в Telegram с первого дня, почта вторым каналом. До этого на странице
# стояло «чата поддержки нет намеренно» — фраза, снятая владельцем и оставшаяся
# в шаблоне. Ссылка и текст выводятся отсюда: пустое имя честно говорит «почта».
SUPPORT_BOT = _env("PSEUDEX_SUPPORT_BOT", "")

# ЯЩИК ДЛЯ ПИСЕМ, А НЕ `noreply`. `noreply@pseudex.ru` стоит в `FROM_EMAIL` и
# существует ровно для исходящих: ответ на него никто не читает, поэтому
# показывать его как «напишите нам» значит гарантированно не получить письма.
# Отдельная настройка, а не захардкоженный адрес в шаблоне, потому что ящик
# заводится на стороне почты и меняется без выкатки.
SUPPORT_EMAIL = _env("PSEUDEX_SUPPORT_EMAIL", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"rid": {"()": "pseudex_site.logfmt.RequestIdFilter"}},
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
        "json": {"()": "pseudex_site.logfmt.JsonFormatter"},
    },
    "handlers": {"console": {
        "class": "logging.StreamHandler",
        "formatter": "json" if _LOG_JSON else "plain",
        "filters": ["rid"],
    }},
    "root": {"handlers": ["console"], "level": _env("PSEUDEX_LOG_LEVEL", "INFO")},
}
