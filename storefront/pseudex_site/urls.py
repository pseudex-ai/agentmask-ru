"""URL map.

`/admin/` is OUR back office and is the operational lever that keeps support
manual work near zero — issue a key, mark an invoice paid, resume a customer.
Its path is configurable because a fixed `/admin/` is the first thing every
scanner tries, and moving it costs nothing.
"""

from django.conf import settings
from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path, re_path

from django_otp.admin import OTPAdminSite

from storefront_web import views
from ops import acquisition_views

# Второй фактор на входе в админку. Меняем КЛАСС уже собранного admin.site, а не
# заводим новый сайт: все модели зарегистрированы на дефолтном сайте, и новый
# отдал бы пустую админку. has_permission требует подтверждённый второй фактор, и
# способов его предъявить два: код из приложения (django-otp) или подтверждение
# от Authelia в токене. Второй способ превращается в первый ОДНИМ механизмом —
# `pseudex_site.middleware.SSOMfaMiddleware`, — поэтому админка и /ops/ не могут
# разойтись в том, что считать подтверждением. Staff без ни того, ни другого
# видит форму входа, а не данные клиентов.
admin.site.__class__ = OTPAdminSite
admin.site.site_header = "pseudex"
admin.site.site_title = "pseudex"
admin.site.index_title = "Операции"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup", views.signup, name="signup"),
    path("analytics/prepare", acquisition_views.prepare, name="analytics_prepare"),
    path("analytics/grant", acquisition_views.grant, name="analytics_grant"),
    path("analytics/revoke", acquisition_views.revoke, name="analytics_revoke"),
    path("analytics/preferences", acquisition_views.preferences, name="analytics_preferences"),
    path("activate", views.activate, name="activate"),
    path("welcome", views.welcome, name="welcome"),
    path("healthz", views.healthz, name="healthz"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),

    # БРАУЗЕР И РОБОТ ПРОСЯТ ЭТОТ АДРЕС САМИ, БЕЗ ССЫЛКИ НА НЕГО, и получают
    # ФАЙЛ, А НЕ РЕДИРЕКТ. Здесь стоял 301 на `/static/favicon.svg`, и Вебмастер
    # назвал это ошибкой отдельной строкой своей таблицы — «файл перенаправляет
    # на другой адрес»; проверка 17.09.2026 так и написала: «Добавьте файл
    # favicon в формате SVG или размером 120 × 120 пикселей». 404 этот адрес
    # отдавать не должен (он кормит счётчик fail2ban), но 301 — не выход: робот
    # считает его ошибкой и иконку не берёт. Подробности — в `views.favicon`.
    path("favicon.ico", views.favicon),
    path("favicon.svg", views.favicon_svg),

    # Отметки конфигуратора. Вторая (и последняя) анонимная запись на сайте —
    # см. докстринг `views.demand`: ни текста, ни почты, счётчик на сутки.
    path("demand", views.demand, name="demand"),

    # The three documents the footer has always linked to. They pointed at an
    # anchor on the landing page, so a customer who came for a document to
    # forward to their own client's security officer found a section of a
    # marketing page and nothing to attach to an email.
    path("offer", views.offer, name="offer"),
    path("policy", views.policy, name="policy"),
    path("consent", views.consent, name="consent"),
    path("requisites", views.requisites, name="requisites"),
    path("architecture", views.architecture, name="architecture"),
    path("detection", views.detection, name="detection"),
    path("types", views.types, name="types"),
    path("litellm", views.litellm_integration, name="litellm"),
    path("how", views.how, name="how"),
    path("faq", views.faq, name="faq"),
    # Раздел «База знаний»: страницы под поисковые запросы, а не под продукт.
    path("baza-znaniy", views.kb, name="kb"),
    path("baza-znaniy/<slug:slug>", views.kb_article, name="kb_article"),
    path("resend", views.resend_activation, name="resend"),

    # КОМАНДА. АДРЕСА УЖЕ НАПЕЧАТАНЫ В QR НА ВИЗИТКАХ — смена маршрута это
    # перепечатка тиража, а не правка кода. Поэтому здесь литерал `/i/`, а не
    # настройка: путь, который нельзя менять, не должен выглядеть настраиваемым.
    #
    # `.vcf` стоит ПЕРЕД `<slug>` нарочно. Слаг точек не содержит, так что
    # `/i/igor.vcf` в него и не попал бы, — но полагаться на это значит поставить
    # порядок строк в зависимость от внутренностей конвертера Django.
    path("i/<slug:slug>.vcf", views.team_vcard, name="team-vcard"),
    # СЛЭШ НА КОНЦЕ — НЕ ТУПИК. Канонический адрес без слэша (он в QR), но
    # адрес, скопированный из письма или из мессенджера, приезжает со слэшем, и
    # `test_seo` требует, чтобы такой адрес уводил на канонический постоянным
    # редиректом, а не в 404. Постоянным (301): визитка напечатана, и «временный»
    # редирект означал бы, что поисковик будет спрашивать снова и снова.
    path("i/<slug:slug>/",
         RedirectView.as_view(pattern_name="team-person", permanent=True)),
    path("i/<slug:slug>", views.team_person, name="team-person"),
    path("i/", views.team, name="team"),

    path("app/", views.cabinet, name="cabinet"),
    path("app/keys/new", views.new_key, name="new_key"),
    path("app/keys/<int:key_id>/revoke", views.revoke_key, name="revoke_key"),
    path("app/overage", views.toggle_overage, name="toggle_overage"),
    path("app/payer", views.update_payer, name="update_payer"),
    path("app/subscribe", views.subscribe, name="subscribe"),
    path("app/pay-annual", views.pay_annual, name="pay_annual"),
    path("app/invoices/<str:number>", views.invoice_detail, name="invoice_detail"),
    path("app/invoices/<str:number>/print", views.invoice_print, name="invoice_print"),
    path("app/invoices/<str:number>/pay", views.pay_invoice, name="pay_invoice"),

    # Machine endpoint, outside /app/: no session, no CSRF, and deliberately not
    # under a path that login_required covers.
    path("hooks/yookassa", views.yookassa_webhook, name="yookassa_webhook"),

    # allauth's own sign-up form is REMOVED, not hidden. It creates a user with
    # no organisation and no key — a second, broken registration path sitting
    # behind the most prominent button on the site. Sign-up happens in one place,
    # the form on the landing, which issues the key.
    path("accounts/signup/", RedirectView.as_view(url="/#start", permanent=False)),

    # ВХОД БЕЗ ПАРОЛЯ. Регистрация («Быстрый старт») пароль не задаёт НИКОГДА,
    # поэтому парольная форма allauth предлагала клиенту заполнить то, чего у
    # него нет. Вход теперь ровно тот же акт, что и заведение аккаунта:
    # доказательство владения почтой — код в письме.
    #
    # УВОДИМ URL, А НЕ ПРЯЧЕМ ПОЛЕ. Спрятанное поле остаётся рабочей ручкой для
    # того, кто знает адрес: POST с паролем на `/accounts/login/` логинил бы
    # по-прежнему. `query_string=True` — иначе теряется `?next=`, и клиент,
    # пришедший по ссылке на счёт, после входа попадает на главную.
    #
    # Официального выключателя пароля у allauth 65.3.1 НЕТ (дока прямо говорит,
    # что code-only UI делается своими переопределениями), поэтому идём через
    # его же штатные вьюхи login-by-code, а не ломаем форму входа.
    path("accounts/login/", RedirectView.as_view(
        url="/accounts/login/code/", permanent=False, query_string=True)),
    # И ЗАВЕСТИ пароль тоже нельзя, иначе passwordless держался бы на том, что
    # клиент не найдёт ссылку сброса. Один префикс вместо шести маршрутов
    # (password/change, /set, /reset, /reset/done, /reset/key/…, /key/done).
    re_path(r"^accounts/password/", RedirectView.as_view(
        url="/accounts/login/code/", permanent=False)),

    path("accounts/", include("allauth.urls")),
    # ОПЕРАТОРСКАЯ КОНСОЛЬ — СОСЕД АДМИНКИ, а не отдельный угадываемый путь.
    # Она показывает всех клиентов разом, поэтому обязана наследовать то же
    # свойство: путь настраивается, и на угадывании его не найти.
    path(f"{settings.ADMIN_PATH}/ops/", include("ops.urls")),
    path(f"{settings.ADMIN_PATH}/", admin.site.urls),
]

if settings.OIDC_ENABLED:
    # OIDC ЖИВЁТ ПОД ТЕМ ЖЕ СКРЫТЫМ ПРЕФИКСОМ, ЧТО АДМИНКА. Отдельный
    # публичный `/oidc/` был бы вторым угадываемым путём к тому же входу, и
    # скрывать один, оставив второй, — это не скрывать.
    #
    # Вставляем ПЕРЕД `admin.site.urls`, иначе админка перехватила бы путь
    # своим catch-all, и callback отвечал бы её страницей «не найдено».
    urlpatterns.insert(
        len(urlpatterns) - 1,
        path(f"{settings.ADMIN_PATH}/oidc/", include("mozilla_django_oidc.urls")),
    )
