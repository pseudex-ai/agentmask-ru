"""Synthetic end-to-end signup -> invoice payment -> attribution -> revoke.

Real Django views, CSRF, account/subscription/invoice and permission/ledger DB.
Payment, licensing and Metrika boundaries are simulated; no real charge,
production account, external conversion, network or live-paid proof.
"""
import io
import os
from pathlib import Path
import re
import tempfile
from unittest.mock import patch


def main():
    keep = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    os.environ.clear(); os.environ.update(keep)
    with tempfile.TemporaryDirectory(prefix="psx-acq-payment-path-") as directory:
        os.environ.update(DJANGO_SETTINGS_MODULE="pseudex_site.settings", PSEUDEX_DEBUG="1",
            PSEUDEX_SECRET_KEY="synthetic-payment-path-only", PSEUDEX_ALLOWED_HOSTS="testserver",
            PSEUDEX_DB_PATH=str(Path(directory)/"db.sqlite3"),
            PSEUDEX_ANALYTICS_SALT_FILE=str(Path(directory)/"salt"),
            PSEUDEX_YOOKASSA_SHOP_ID="synthetic-shop", PSEUDEX_YOOKASSA_SECRET_KEY="synthetic-secret",
            PSEUDEX_ACQUIRING_ENABLED="1")
        import django
        django.setup()
        from django.core import mail
        from django.core.cache import cache
        from django.core.management import call_command
        from django.test import Client, override_settings
        from django.urls import reverse
        from django.utils import timezone
        from accounts.models import Organization
        from billing import payments, licensing
        from billing.models import Invoice, Subscription
        from ops.acquisition_consent import AnalyticsGrant, PURPOSE_REVISION
        from ops.acquisition_delivery import AcquisitionDelivery, deliver
        from ops.acquisition_facts import current_facts
        from ops import yandex_api
        from test_payment_return import Provider
        provider = Provider()
        sent = []
        def deny(*args, **kwargs):
            raise AssertionError("No network in synthetic payment path")
        class Acknowledgement:
            status_code = 200
            def json(self):
                return {"uploading": {"id": 501, "status": "UPLOADED", "source_quantity": 1, "line_quantity": 1}}
        def upload(method, url, **kwargs):
            assert method == "POST" and url.endswith("/counter/123/offline_conversions/upload")
            sent.append(kwargs["files"]["file"][1])
            return Acknowledgement()
        with patch("socket.socket.connect", deny), patch("socket.getaddrinfo", deny), \
                patch.object(payments, "_client", return_value=provider), \
                patch.object(licensing, "set_status", return_value=1), \
                patch.object(licensing, "set_org_plan", return_value=1), \
                patch.object(licensing, "set_ceiling", return_value=None), \
                patch.object(licensing, "usage", return_value={"usage": {}}), \
                patch.object(licensing, "fleet", return_value={}), \
                patch.object(yandex_api, "access_token", return_value="synthetic-token"), \
                patch.object(yandex_api, "_request", side_effect=upload), \
                override_settings(ACQUISITION_LINK_ENABLED=True, ACQUISITION_EXPORT_ENABLED=True,
                    YANDEX_CONVERSIONS=False, METRIKA_ID="123",
                    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            call_command("migrate", verbosity=0, interactive=False)
            call_command("seed_plans", "--no-licensing", verbosity=0, stdout=io.StringIO())
            def flow(email, analytics):
                cache.clear()
                client = Client(enforce_csrf_checks=True)
                page = client.get("/analytics/preferences", secure=True)
                assert page.status_code == 200
                def post(path, data):
                    return client.post(path, data, secure=True, HTTP_ORIGIN="https://testserver",
                                       HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
                if analytics:
                    client.cookies["_ym_uid"] = "90071992547409930000"
                    permission = {"purpose_revision": PURPOSE_REVISION, "affirmative": "1",
                                  "browser_consent": "yes", "client_id": "90071992547409930000"}
                    assert post("/analytics/prepare", permission).status_code == 200
                    assert post("/analytics/grant", permission).status_code == 200
                signup = post(reverse("signup"), {"email": email, "company": "Synthetic only",
                    "plan": "start", "consent": "1", "terms": "1"})
                assert signup.status_code == 200
                org = Organization.objects.get(memberships__user__email=email)
                assert org.subscription.state == Subscription.PENDING
                link = re.search(r"https://testserver/activate\?t=([^\s]+)", mail.outbox[-1].body)[1]
                page = client.get("/activate", {"t": link}, secure=True)
                assert page.status_code == 200 and "analytics.js" not in page.content.decode()
                data = {"t": link}
                if analytics:
                    assert 'name="acquisition_confirmation"' in page.content.decode()
                    data["acquisition_confirmation"] = PURPOSE_REVISION
                assert post("/activate", data).status_code == 302
                assert not org.keys.exists()
                # Real subscribe view creates an invoice and requests a simulated
                # provider payment; no force_login and no direct mark_paid here.
                response = post(reverse("subscribe"), {"plan": "start"})
                assert response.status_code == 302 and response["Location"].startswith("https://pay.test/")
                invoice = org.invoices.get()
                assert invoice.state != Invoice.PAID and invoice.paid_at is None
                payment = provider.by_id[invoice.payment_ref]
                assert payment.status == "pending"
                payment.status = "succeeded"  # Simulated provider, not a real payment.
                response = client.get(reverse("invoice_detail", args=[invoice.number]), secure=True)
                assert response.status_code == 302
                invoice.refresh_from_db(); org.subscription.refresh_from_db()
                assert invoice.state == Invoice.PAID and invoice.paid_at
                assert org.subscription.state == Subscription.ACTIVE and not org.keys.exists()
                facts, issues = current_facts(organization_ids=[org.pk], now=timezone.now())
                paid = [f for f in facts if f.target == "paid"]
                assert len(paid) == 1 and paid[0].price == invoice.total
                return client, post, org, invoice, paid[0]
            client, post, org, invoice, fact = flow("with-permission@example.invalid", True)
            assert AnalyticsGrant.objects.get(organization=org).verified_at
            assert deliver(fact)["state"] == "accepted"
            assert len(sent) == 1 and "90071992547409930000" in sent[0]
            assert f",{invoice.total:.2f},RUB" in sent[0]
            assert not any(secret in sent[0] for secret in ("example.invalid", invoice.number, org.pk, "Synthetic"))
            original_at = invoice.paid_at
            client.get(reverse("invoice_detail", args=[invoice.number]), secure=True)
            invoice.refresh_from_db()
            assert invoice.paid_at == original_at and deliver(fact)["state"] == "already_reserved"
            assert post("/analytics/revoke", {}).status_code == 200
            assert deliver(fact)["state"] == "ineligible" and len(sent) == 1
            _, _, other, other_invoice, other_fact = flow("without-permission@example.invalid", False)
            assert other_invoice.state == Invoice.PAID  # Refusal does not stop the purchase.
            assert not AnalyticsGrant.objects.filter(organization=other).exists()
            assert deliver(other_fact)["state"] == "ineligible" and len(sent) == 1
            assert AcquisitionDelivery.objects.count() == 1
            print("PASS SYNTHETIC payment path: signup/CSRF/mailproof -> simulated provider -> real invoice settlement -> consent-bound CSV once -> revoke; refusal still pays without export")
            print("NOT LIVE: no real charge, no production data, no external goal delivered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
