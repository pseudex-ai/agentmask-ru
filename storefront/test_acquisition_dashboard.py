"""Staff/OTP/CSRF operator report integration; no external API or money writes."""
import os
from pathlib import Path
import tempfile
from unittest.mock import patch


def main():
    keep = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
    os.environ.clear(); os.environ.update(keep)
    with tempfile.TemporaryDirectory(prefix="psx-acq-dashboard-") as directory:
        os.environ.update(DJANGO_SETTINGS_MODULE="pseudex_site.settings", PSEUDEX_DEBUG="1",
            PSEUDEX_SECRET_KEY="offline-dashboard-only", PSEUDEX_ALLOWED_HOSTS="testserver",
            PSEUDEX_DB_PATH=str(Path(directory)/"db.sqlite3"),
            PSEUDEX_ANALYTICS_SALT_FILE=str(Path(directory)/"salt"))
        import django
        django.setup()
        from decimal import Decimal
        from django.conf import settings
        from django.core.management import call_command
        from django.test import Client, override_settings
        from accounts.models import User
        from testkit_otp import login_staff
        from ops import acquisition_dashboard as dashboard
        from ops.acquisition_lifecycle import AcquisitionOutcome
        from billing.models import Invoice
        def deny(*args, **kwargs):
            raise AssertionError("Unexpected network")
        with patch("socket.socket.connect", deny), patch("socket.getaddrinfo", deny), \
                override_settings(METRIKA_ID="123", ACQUISITION_EXPORT_ENABLED=False,
                    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            call_command("migrate", verbosity=0, interactive=False)
            path = f"/{settings.ADMIN_PATH}/ops/acquisition/"
            client = Client()
            assert client.get(path, secure=True).status_code == 302
            user = User.objects.create_user(email="staff@example.invalid", is_staff=True)
            client.force_login(user)
            assert client.get(path, secure=True).status_code == 302
            login_staff(client, user)
            response = client.get(path, secure=True)
            assert response.status_code == 200
            html = response.content.decode()
            assert "От рекламы до результата" in html and "не измерен" in html
            assert "analytics.js" not in html and "acquisition-actions.js" not in html
            assert response["X-Frame-Options"] == "DENY"
            assert "frame-ancestors 'none'" in response["Content-Security-Policy"]
            assert client.get(path+"?days=not-a-number", secure=True).status_code == 200
            csrf_client = Client(enforce_csrf_checks=True)
            login_staff(csrf_client, user)
            assert csrf_client.post(path, {"action": "attest_outcome"}, secure=True).status_code == 403
            assert not AcquisitionOutcome.objects.exists() and not Invoice.objects.exists()
            before = Invoice.objects.count()
            campaigns = {"result": {"Campaigns": [{"Id": 715028805, "UnifiedCampaign": {"CounterIds": {"Items": [123]}}}]}}
            goals = [{"id": 91, "type": "action", "status": "Active", "conditions": [{"type": "exact", "url": "paid"}]}]
            result = {"status": "complete", "state": None, "reason": None,
                "rows": [{"Date": "2026-10-10", "CampaignId": "715028805", "AdGroupId": "123456789",
                          "AdId": "1923093719428180734", "Cost": Decimal("120.34"), "Clicks": Decimal("7"),
                          "Conversions_91_LC": None}],
                "goals": [{"id": "91", "name": "paid", "title": "Первая оплата"}],
                "fullness": {"batches_complete": 1, "batches_total": 1}}
            with patch.object(dashboard.yandex_api, "direct", return_value=campaigns) as direct, \
                    patch.object(dashboard.yandex_api, "goals", return_value=goals), \
                    patch.object(dashboard, "collect_reports", return_value=result) as reports:
                response = client.post(path, {"action": "report_start", "campaign": "715028805", "level": "ad"}, secure=True)
                assert response.status_code == 302
                assert direct.call_args.args[:2] == ("campaigns", "get")
                assert reports.call_args.kwargs["max_requests"] == 2
                response = client.get(path, secure=True)
                html = response.content.decode()
                assert "1923093719428180734" in html and "120,34" in html and "неизвестно" in html
                saved = dashboard._load(client.session["acquisition_report"])
                assert saved["result"]["rows"][0]["Cost"] == Decimal("120.34")
                assert saved["result"]["rows"][0]["Conversions_91_LC"] is None
            assert Invoice.objects.count() == before and not AcquisitionOutcome.objects.exists()
            assert dashboard._load(dashboard._dump({"value": Decimal("0.00"), "unknown": None})) == {"value": Decimal("0.00"), "unknown": None}
            print("PASS acquisition dashboard: staff+OTP+CSRF, no private SDK, linked-counter reports, exact IDs/Decimal/unknown, no financial mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
