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
    "accounts",
    "billing",
    "storefront_web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "storefront_web.middleware.SecurityHeadersMiddleware",
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
# These four are the settings django-allauth 65.3.1 ACTUALLY READS. The block
# here used to say `ACCOUNT_LOGIN_METHODS` / `ACCOUNT_SIGNUP_FIELDS`, which are
# a LATER version's API: 65.3.1 has no such names, so the whole configuration
# was silently inert and allauth ran on its defaults — authenticate by
# username, username required — against a User model whose `username` is None.
# The sign-in page therefore raised FieldDoesNotExist and returned 500, which
# is the only way back into the cabinet for every customer.
#
# It survived the suite because every test signs in with `force_login()` and
# never renders that page. If allauth is ever upgraded past 65.3, these become
# deprecated aliases and the new names take over — check both then.
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_LOGIN_BY_CODE_ENABLED = True
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
}

DOCKER_IMAGE = _env("PSEUDEX_DOCKER_IMAGE", "cr.yandex/pseudex/pseudex:1.0.0")

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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": _env("PSEUDEX_LOG_LEVEL", "INFO")},
}
