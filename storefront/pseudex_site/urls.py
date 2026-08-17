"""URL map.

`/admin/` is OUR back office and is the operational lever that keeps support
manual work near zero — issue a key, mark an invoice paid, resume a customer.
Its path is configurable because a fixed `/admin/` is the first thing every
scanner tries, and moving it costs nothing.
"""

from django.conf import settings
from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path

from storefront_web import views

admin.site.site_header = "pseudex"
admin.site.site_title = "pseudex"
admin.site.index_title = "Операции"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("signup", views.signup, name="signup"),
    path("activate", views.activate, name="activate"),
    path("welcome", views.welcome, name="welcome"),
    path("healthz", views.healthz, name="healthz"),

    # The three documents the footer has always linked to. They pointed at an
    # anchor on the landing page, so a customer who came for a document to
    # forward to their own client's security officer found a section of a
    # marketing page and nothing to attach to an email.
    path("offer", views.offer, name="offer"),
    path("policy", views.policy, name="policy"),
    path("architecture", views.architecture, name="architecture"),
    path("detection", views.detection, name="detection"),
    path("resend", views.resend_activation, name="resend"),

    path("app/", views.cabinet, name="cabinet"),
    path("app/keys/new", views.new_key, name="new_key"),
    path("app/keys/<int:key_id>/revoke", views.revoke_key, name="revoke_key"),
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
    path("accounts/", include("allauth.urls")),
    path(f"{settings.ADMIN_PATH}/", admin.site.urls),
]
