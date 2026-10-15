"""Real beta form requests against migrated, isolated temporary SQLite.

Run with the storefront venv: python test_product_pages.py. No licensing server,
mail provider, payment service, or external analytics is needed or allowed.
"""

import logging
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch


def main():
    with tempfile.TemporaryDirectory(prefix="pseudex-product-pages-") as directory:
        keep = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
        os.environ.clear()
        os.environ.update(keep)
        os.environ.update({
            "DJANGO_SETTINGS_MODULE": "pseudex_site.settings",
            "PSEUDEX_SECRET_KEY": "product-pages-test-only",
            "PSEUDEX_DEBUG": "1",
            "PSEUDEX_DB_HOST": "",
            "PSEUDEX_DB_PATH": str(Path(directory) / "products.sqlite3"),
            "PSEUDEX_ANALYTICS_SALT_FILE": str(Path(directory) / "analytics-salt"),
            "PSEUDEX_ALLOWED_HOSTS": "testserver,localhost",
            "SITE_URL": "http://testserver",
        })
        import django
        django.setup()
        from django.conf import settings
        from django.contrib import admin
        from django.contrib.auth.models import Permission
        from django.core import mail
        from django.core.cache import cache
        from django.core.management import call_command
        from django.db import connection
        from django.test import Client, override_settings
        from django.test.utils import setup_test_environment, teardown_test_environment
        from django.urls import reverse
        from django_otp import DEVICE_ID_SESSION_KEY
        from django_otp.plugins.otp_totp.models import TOTPDevice
        from accounts.models import Membership, Organization, User
        from billing.models import Invoice, LicenseKey, Subscription
        from ops.models import DemandDay, ProductInterest
        from ops.analytics_models import Funnel
        from ops.acquisition_consent import AnalyticsGrant
        from ops.acquisition_delivery import AcquisitionDelivery
        from ops.acquisition_lifecycle import AcquisitionOutcome
        from storefront_web import products

        assert connection.vendor == "sqlite"
        assert Path(connection.settings_dict["NAME"]).parent == Path(directory)
        call_command("migrate", verbosity=0)
        setup_test_environment()
        previous_logging = logging.root.manager.disable
        logging.disable(logging.CRITICAL)  # Expected 400/403/429/500 cases are asserted below.

        class ProductPagesTests(unittest.TestCase):
            def setUp(self):
                cache.clear()
                self.client = Client(enforce_csrf_checks=True)
                self.network = [
                    patch.object(target, name, side_effect=AssertionError("external network forbidden")).start()
                    for target, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "getaddrinfo"))
                ]
                self.addCleanup(patch.stopall)
                self.before = ProductInterest.objects.count()

            def tearDown(self):
                self.assertEqual(sum(mock.call_count for mock in self.network), 0, "request attempted external I/O")

            def payload(self, product="enterprise", **changes):
                data = {"product": product, "email": "person@example.com", "role": "security",
                        "harness": "claude_code", "use_case": "data_protection",
                        "consent": "1", "website": ""}
                data.update(changes)
                return data

            def post(self, data=None, *, client=None, csrf=True):
                client = client or self.client
                if csrf:
                    if "csrftoken" not in client.cookies:
                        self.assertEqual(client.get("/ai-security").status_code, 200)
                    headers = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
                else:
                    headers = {}
                return client.post(reverse("product_interest"), data or self.payload(), **headers)

            def business_counts(self):
                return {model.__name__: model.objects.count() for model in (
                    User, Organization, Membership, Subscription, Invoice, LicenseKey,
                    Funnel, DemandDay, AnalyticsGrant, AcquisitionDelivery, AcquisitionOutcome)}

            def test_gets_render_real_templates_and_contract(self):
                for product, path, template in (
                    ("enterprise", "/ai-security", "products/enterprise.html"),
                    ("coding", "/ai-coding", "products/coding.html"),
                ):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(template, [t.name for t in response.templates])
                    self.assertEqual(response.context["product"], product)
                    self.assertEqual(response.context["canonical_path"], path)
                    self.assertFalse(response.context["interest_received"])
                    self.assertFalse(response.context["form"].is_bound)
                    body = response.content.decode()
                    for field in ("product", "email", "role", "harness", "use_case", "consent", "website", "csrfmiddlewaretoken"):
                        self.assertIn(f'name="{field}"', body)
                    self.assertIn('action="/products/interest"', body)
                    self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_success_both_products_is_durable_and_not_signup(self):
                before_business = self.business_counts()
                for product, path in (("enterprise", "/ai-security"), ("coding", "/ai-coding")):
                    response = self.post(self.payload(product, email=f"{product}@example.com"))
                    self.assertEqual(response.status_code, 303)
                    self.assertEqual(response["Location"], path + "?interest=received#early-access")
                    row = ProductInterest.objects.latest("pk")
                    self.assertEqual(row.product, product)
                    self.assertEqual(row.email, f"{product}@example.com")
                    self.assertEqual((row.role, row.harness, row.use_case), ("security", "claude_code", "data_protection"))
                    self.assertEqual(row.consent_revision, products.CONSENT_REVISION)
                    self.assertIsNotNone(row.consent_at)
                    self.assertIsNotNone(row.created_at)
                    connection.close()
                    self.assertTrue(ProductInterest.objects.filter(pk=row.pk, email=row.email).exists())
                    confirmation = self.client.get(response["Location"])
                    self.assertEqual(confirmation.status_code, 200)
                    self.assertTrue(confirmation.context["interest_received"])
                    self.assertNotIn(row.email, confirmation.content.decode())
                    self.assertFalse(self.client.get(response["Location"]).context["interest_received"])
                    self.assertTrue(response.cookies[products.RECEIPT_COOKIE]["httponly"])
                    self.assertEqual(response.cookies[products.RECEIPT_COOKIE]["samesite"], "Lax")
                self.assertEqual(ProductInterest.objects.count(), self.before + 2)
                self.assertEqual(self.business_counts(), before_business)
                self.assertNotIn("sessionid", self.client.cookies)
                self.assertEqual(len(getattr(mail, "outbox", [])), 0)

            def test_all_enums_reject_arbitrary_or_missing_values(self):
                for field in ("role", "harness", "use_case"):
                    for value in ("", "unknown", "<script>alert(1)</script>", "x" * 1000):
                        with self.subTest(field=field, value=value[:20]):
                            cache.clear()
                            response = self.post(self.payload(**{field: value}))
                            self.assertEqual(response.status_code, 400)
                            self.assertIn(field, response.context["form"].errors)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_product_cannot_select_template_or_redirect(self):
                for product in ("", "../enterprise", "other", "https://evil.invalid", "ENTERPRISE"):
                    cache.clear()
                    response = self.post(self.payload(product))
                    self.assertEqual(response.status_code, 400)
                    self.assertNotIn("Location", response)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_email_validation_and_length(self):
                for email in ("", "not-email", "a\nBcc:x@example.com", "a" * 250 + "@example.com"):
                    cache.clear()
                    response = self.post(self.payload(email=email))
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("email", response.context["form"].errors)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_explicit_consent_is_separate_and_exact(self):
                for value in (None, "", "0", "false", "true", "on", "yes"):
                    cache.clear()
                    payload = self.payload(consent=value)
                    if value is None:
                        del payload["consent"]
                    payload["analytics_consent"] = "1"
                    response = self.post(payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("consent", response.context["form"].errors)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_csrf_missing_invalid_and_cross_origin(self):
                response = self.post(csrf=False)
                self.assertEqual(response.status_code, 403)
                self.client.get("/ai-coding")
                response = self.client.post(reverse("product_interest"), self.payload(), HTTP_X_CSRFTOKEN="x" * 32)
                self.assertEqual(response.status_code, 403)
                response = self.client.post(reverse("product_interest"), self.payload(),
                                            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
                                            HTTP_ORIGIN="https://evil.invalid")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_honeypot_and_duplicate_fields_are_not_fake_success(self):
                for data in (self.payload(website="bot.invalid"), self.payload(website=" "),
                             self.payload(consent=["0", "1"]), self.payload(product=["enterprise", "coding"]),
                             self.payload(email=["first@example.com", "second@example.com"])):
                    cache.clear()
                    response = self.post(data)
                    self.assertEqual(response.status_code, 400)
                    self.assertNotIn("Location", response)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_files_and_json_are_not_a_second_ingestion_path(self):
                from django.core.files.uploadedfile import SimpleUploadedFile
                data = self.payload()
                data["attachment"] = SimpleUploadedFile("private.txt", b"never persist attachments")
                self.assertEqual(self.post(data).status_code, 400)
                response = self.client.post(reverse("product_interest"), '{"product":"enterprise"}',
                    content_type="application/json", HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_method_contract(self):
                for method in ("get", "head", "put", "delete"):
                    response = getattr(Client(), method)(reverse("product_interest"))
                    self.assertEqual(response.status_code, 405)
                for path in ("/ai-security", "/ai-coding"):
                    self.assertEqual(Client().post(path, self.payload()).status_code, 405)
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_actual_rate_limit_shared_by_products_counts_failures(self):
                for index in range(products.INTEREST_LIMIT):
                    response = self.post(self.payload("coding" if index % 2 else "enterprise", consent="0"))
                    self.assertEqual(response.status_code, 400)
                response = self.post(self.payload())
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response["Retry-After"], str(products.INTEREST_WINDOW))
                self.assertEqual(ProductInterest.objects.count(), self.before)
                # Caller-controlled forwarding does not buy another bucket.
                response = self.client.post(reverse("product_interest"), self.payload(),
                    HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
                    HTTP_X_FORWARDED_FOR="203.0.113.19")
                self.assertEqual(response.status_code, 429)
                other = Client(enforce_csrf_checks=True, REMOTE_ADDR="203.0.113.20")
                self.assertEqual(self.post(client=other).status_code, 303)

            def test_marker_is_closed_and_cannot_emit_pii_or_create_a_lead(self):
                for query, expected in (("?interest=received", False), ("?interest=1", False),
                                        ("?interest=received&interest=other", False),
                                        ("?interest=person@example.com", False), ("?success=1", False)):
                    response = self.client.get("/ai-coding" + query)
                    self.assertEqual(response.context["interest_received"], expected)
                    self.assertNotIn("person@example.com", response.content.decode())
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_receipt_is_product_scoped_signed_and_expires(self):
                import time
                self.post(self.payload("enterprise"))
                cookie = self.client.cookies[products.RECEIPT_COOKIE].value
                self.assertFalse(self.client.get("/ai-coding?interest=received").context["interest_received"])
                self.client.cookies[products.RECEIPT_COOKIE] = cookie + "tampered"
                self.assertFalse(self.client.get("/ai-security?interest=received").context["interest_received"])
                self.client.cookies[products.RECEIPT_COOKIE] = cookie
                with patch("django.core.signing.time.time", return_value=time.time() + products.RECEIPT_MAX_AGE + 2):
                    self.assertFalse(self.client.get("/ai-security?interest=received").context["interest_received"])

            def test_no_external_analytics_loader_even_when_configured(self):
                with override_settings(METRIKA_ID="123456", ACQUISITION_LINK_ENABLED=True,
                    ANALYTICS={"mode": "full", "host": "https://stats.invalid", "key": "test"}):
                    for response in (self.client.get("/ai-security"), self.client.get("/ai-coding"),
                                     self.post(self.payload(email="bound@example.com", consent="0"))):
                        self.assertFalse(response.context["analytics_here"])
                        self.assertEqual(response.context["metrika_id"], "")
                        body = response.content.decode()
                        self.assertNotIn('src="/static/analytics.js', body)
                        self.assertNotIn('src="/static/acquisition-actions.js', body)
                        self.assertNotIn("mc.yandex", response["Content-Security-Policy"])
                        self.assertNotIn("stats.invalid", response["Content-Security-Policy"])
                        self.assertEqual(response["Referrer-Policy"], "same-origin")
                        self.assertEqual(response["X-Frame-Options"], "DENY")
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_extra_text_is_not_stored_or_redirected(self):
                response = self.post(self.payload(message="DO NOT STORE THIS", next="https://evil.invalid",
                                                  consent_revision="fake", organization="fake"))
                self.assertEqual(response.status_code, 303)
                self.assertNotIn("evil", response["Location"])
                row = ProductInterest.objects.latest("pk")
                self.assertNotIn("DO NOT STORE THIS", str(row.__dict__))
                self.assertEqual(row.consent_revision, products.CONSENT_REVISION)

            def test_closed_enums_are_enforced_by_migrated_database(self):
                from django.db import IntegrityError
                self.post()
                row = ProductInterest.objects.latest("pk")
                for field in ("product", "role", "harness", "use_case"):
                    with self.assertRaises(IntegrityError):
                        ProductInterest.objects.filter(pk=row.pk).update(**{field: "arbitrary"})
                row.refresh_from_db()
                self.assertEqual(row.product, "enterprise")

            def test_db_failure_never_confirms_success(self):
                from django.db import DatabaseError
                with patch.object(ProductInterest.objects, "create", side_effect=DatabaseError("test failure")):
                    with self.assertRaises(DatabaseError):
                        self.post()
                self.assertEqual(ProductInterest.objects.count(), self.before)

            def test_staff_admin_preserves_mfa_and_model_permission(self):
                self.post(self.payload(email="lead-only@example.com"))
                url = reverse("admin:ops_productinterest_changelist")
                self.assertTrue(url.startswith(f"/{settings.ADMIN_PATH}/"))
                self.assertEqual(Client().get(url).status_code, 302)
                user = User.objects.create_user(email="lead-operator@example.com", is_staff=True)
                operator = Client()
                operator.force_login(user)
                self.assertEqual(operator.get(url).status_code, 302)
                device = TOTPDevice.objects.create(user=user, name="test", confirmed=True)
                session = operator.session
                session[DEVICE_ID_SESSION_KEY] = device.persistent_id
                session.save()
                denied = operator.get(url)
                self.assertEqual(denied.status_code, 403, (dict(denied.headers), dict(operator.session), str(denied.wsgi_request.user)))
                user.user_permissions.add(Permission.objects.get(content_type__app_label="ops", codename="view_productinterest"))
                response = operator.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn("lead-only@example.com", response.content.decode())
                self.assertIn("no-store", response["Cache-Control"])
                model_admin = admin.site._registry[ProductInterest]
                self.assertFalse(model_admin.has_add_permission(response.wsgi_request))
                self.assertFalse(model_admin.has_change_permission(response.wsgi_request))
                user.is_staff = False
                user.save(update_fields=["is_staff"])
                self.assertEqual(operator.get(url).status_code, 302)

        try:
            with override_settings(
                STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                          "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
                EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "product-page-tests"}},
                SECURE_SSL_REDIRECT=False,
            ):
                result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProductPagesTests))
            return 0 if result.wasSuccessful() else 1
        finally:
            logging.disable(previous_logging)
            teardown_test_environment()
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
