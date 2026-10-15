"""Beta interest is a local contact request, not signup or an analytics outcome.

DemandDay cannot hold this: it promises anonymous aggregate feature votes. A
ProductInterest holds an explicitly consented contact, with no customer account,
licence, payment, external delivery, or inferred qualification attached to it.
"""

from django import forms
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST, require_safe

from ops.models import ProductInterest
from storefront_web.views import _too_many

CONSENT_REVISION = "product-interest-v1"
CONSENT_TEXT = (
    "Согласен на обработку моего email и выбранных параметров заявки "
    "для связи со мной по поводу раннего доступа к выбранному продукту. "
    "Это не согласие на рекламную рассылку или аналитику."
)
INTEREST_LIMIT = 3
INTEREST_WINDOW = 600
RECEIPT_COOKIE = "product_interest_received"
RECEIPT_SALT = "product-interest-receipt-v1"
RECEIPT_MAX_AGE = 300
PRODUCTS = {
    "enterprise": {
        "url_name": "ai_security",
        "template": "products/enterprise.html",
        "title": "Корпоративная платформа AI-безопасности — Pseudex",
        "description": "Настраиваемая защита данных для корпоративных ИИ-систем: политики, права доступа и журнал решений в вашем контуре. Beta-пилоты Pseudex.",
    },
    "coding": {
        "url_name": "ai_coding",
        "template": "products/coding.html",
        "title": "Защищённый AI-кодинг: секреты проекта и данные — Pseudex",
        "description": "Защитный слой для AI-кодинга: чувствительные данные в файлах, логах и вызовах инструментов. Локальный прокси, коннекторы CLI и ранний доступ к бете Pseudex.",
    },
}

# Even a visitor who previously accepted analytics must not have the contact
# form replayed externally. This is local to these pages: the site's existing
# consent gate and analytics pipeline remain unchanged.
_PRODUCT_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "style-src-attr 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
    "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


def _private_response(response):
    response["Cache-Control"] = "no-store"
    # A same-origin POST must retain its Origin for Django CSRF validation.
    # no-referrer made Chromium send Origin: null and broke the real form,
    # despite synthetic Django Client tests passing. External referrers stay off.
    response["Referrer-Policy"] = "same-origin"
    response["Content-Security-Policy"] = _PRODUCT_CSP
    return response


def _choice(choices, label):
    return forms.ChoiceField(
        choices=[("", "Выберите вариант"), *choices], label=label,
        error_messages={"required": "Выберите вариант.", "invalid_choice": "Выберите вариант из списка."},
    )


class ProductInterestForm(forms.Form):
    product = forms.ChoiceField(choices=ProductInterest.Product.choices, widget=forms.HiddenInput)
    role = _choice(ProductInterest.Role.choices, "Ваша роль")
    harness = _choice(ProductInterest.Harness.choices, "Инструмент / harness")
    use_case = _choice(ProductInterest.UseCase.choices, "Основная задача")
    email = forms.EmailField(
        max_length=254, label="Email для связи",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "class": "ym-disable-keys"}),
        error_messages={"required": "Укажите email для связи.", "invalid": "Укажите корректный email."},
    )
    consent = forms.BooleanField(
        label=CONSENT_TEXT, required=True,
        widget=forms.CheckboxInput(attrs={"value": "1"}),
        error_messages={"required": "Для отправки заявки нужно отдельное согласие."},
    )
    website = forms.CharField(required=False, max_length=200, widget=forms.TextInput(
        attrs={"tabindex": "-1", "autocomplete": "off", "aria-hidden": "true"}))

    def clean_consent(self):
        # BooleanField accepts arbitrary nonempty strings; only the declared
        # checkbox value is affirmative consent in this form's protocol.
        if self.data.get("consent") != "1":
            raise forms.ValidationError("Для отправки заявки нужно отдельное согласие.")
        return True


def _page(request, product, *, form=None, status=200):
    spec = PRODUCTS[product]
    received = (
        request.method == "GET" and request.GET.getlist("interest") == ["received"]
        and request.get_signed_cookie(RECEIPT_COOKIE, default="", salt=RECEIPT_SALT,
                                      max_age=RECEIPT_MAX_AGE) == product
    )
    context = {
        "product": product,
        "form": form if form is not None else ProductInterestForm(initial={"product": product}),
        "interest_received": received,
        "canonical_path": reverse(spec["url_name"]),
        "interest_url": reverse("product_interest"),
        "consent_text": CONSENT_TEXT,
        "consent_revision": CONSENT_REVISION,
        "page_title": spec["title"],
        "page_description": spec["description"],
        "analytics_here": False,
        "metrika_id": "",
        "acquisition_link_enabled": False,
        "indexable": request.method == "GET",
    }
    response = render(request, spec["template"], context, status=status)
    if received:
        response.delete_cookie(RECEIPT_COOKIE, samesite="Lax")
    return _private_response(response)


@require_safe
@ensure_csrf_cookie
def enterprise(request):
    return _page(request, "enterprise")


@require_safe
@ensure_csrf_cookie
def coding(request):
    return _page(request, "coding")


@sensitive_post_parameters()
@require_POST
@csrf_protect
def interest(request):
    # Count failed attempts too; changing product must not buy another bucket.
    # _too_many uses the configured cache (per-process LocMem by default), not
    # a durable/global anti-abuse service. Do not claim stronger protection.
    if _too_many(request, "product-interest", INTEREST_LIMIT, INTEREST_WINDOW):
        response = _private_response(HttpResponse("Слишком много попыток. Попробуйте позже.", status=429))
        response["Retry-After"] = str(INTEREST_WINDOW)
        return response
    product = request.POST.get("product")
    if product not in PRODUCTS:
        return _private_response(HttpResponse("Неизвестный продукт.", status=400))
    # Ambiguous field values are not consent; files and honeypot content are
    # never retained, echoed back, or treated as a successful submission.
    if (request.FILES or request.POST.get("website", "")
            or any(len(request.POST.getlist(name)) > 1 for name in ProductInterestForm.base_fields)):
        return _private_response(HttpResponse("Не удалось отправить заявку. Проверьте форму.", status=400))
    form = ProductInterestForm(request.POST)
    if not form.is_valid():
        return _page(request, product, form=form, status=400)
    data = form.cleaned_data
    ProductInterest.objects.create(
        product=data["product"], role=data["role"], harness=data["harness"],
        use_case=data["use_case"], email=data["email"],
        consent_at=timezone.now(), consent_revision=CONSENT_REVISION,
    )
    # No email, row id, arbitrary next URL, or request query survives the PRG.
    # The closed marker is presentation only, never a conversion/analytics fact.
    response = HttpResponseRedirect(reverse(PRODUCTS[product]["url_name"]) + "?interest=received#early-access")
    response.status_code = 303
    # The URL alone is not a receipt. A short-lived signed product-only cookie
    # is set after the INSERT and consumed on display; no anonymous DB session
    # or contact is needed. Like any client receipt it is replayable, so never
    # use it as an analytics conversion or as authorization for another action.
    response.set_signed_cookie(
        RECEIPT_COOKIE, product, salt=RECEIPT_SALT, max_age=RECEIPT_MAX_AGE,
        secure=not settings.DEBUG, httponly=True, samesite="Lax",
    )
    return _private_response(response)
