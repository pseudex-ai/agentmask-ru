"""Offline delivery tests: real temporary SQLite ledger, synthetic API only."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch


def main():
    keep = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT") if key in os.environ}
    os.environ.clear()
    os.environ.update(keep)
    with tempfile.TemporaryDirectory(prefix="psx-acquisition-delivery-") as directory:
        os.environ.update({"DJANGO_SETTINGS_MODULE": "pseudex_site.settings",
                           "PSEUDEX_SECRET_KEY": "synthetic-delivery-not-production",
                           "PSEUDEX_DEBUG": "1", "PSEUDEX_DB_PATH": str(Path(directory)/"db.sqlite3")})
        import django
        django.setup()
        from datetime import timedelta
        from decimal import Decimal
        from django.core.management import call_command
        from django.contrib.auth import get_user_model
        from django.test import override_settings
        from django.utils import timezone
        from accounts.models import Organization
        from ops.acquisition_consent import AnalyticsGrant, PURPOSE_REVISION, revoke_grants
        from ops.acquisition_facts import BusinessFact
        from ops.acquisition_delivery import AcquisitionDelivery, deliver, refresh_delivery, validate_upload
        from ops import yandex_api
        now = timezone.now()
        requests = []
        reply = {"uploading": {"id": 301, "status": "UPLOADED", "source_quantity": 1, "line_quantity": 1}}
        def forbidden(*args, **kwargs):
            raise AssertionError("Unexpected network connection")
        class Response:
            status_code = 200
            def json(self):
                return reply
        def transport(method, url, **kwargs):
            requests.append((method, url, kwargs))
            assert url.startswith("https://api-metrika.yandex.net/management/v1/counter/123/")
            if method == "POST":
                text = kwargs["files"]["file"][1]
                assert text == "Target,DateTime,ClientId,Price,Currency\npaid," + str(int(fact.at.timestamp())) + ",90071992547409931234,3900.00,RUB\n"
                assert "psxacq" in kwargs["params"]["comment"]
                assert not any(value in text for value in ("example.invalid", "company", "ps_live_", "invoice:"))
            return Response()
        with patch("socket.socket.connect", forbidden), patch("socket.getaddrinfo", forbidden), \
                patch.object(yandex_api, "_request", side_effect=transport), \
                patch.object(yandex_api, "access_token", return_value="synthetic-token") as token, \
                override_settings(ACQUISITION_LINK_ENABLED=True, ACQUISITION_EXPORT_ENABLED=True,
                                  YANDEX_CONVERSIONS=False, METRIKA_ID="123"):
            call_command("migrate", verbosity=0, interactive=False)
            user = get_user_model().objects.create_user(email="person@example.invalid")
            org = Organization.objects.create(display_name="Synthetic company")
            grant = AnalyticsGrant.objects.create(user=user, organization=org,
                purpose_revision=PURPOSE_REVISION, granted_at=now-timedelta(hours=2),
                reference_at=now-timedelta(hours=2), verified_at=now-timedelta(minutes=90),
                expires_at=now+timedelta(days=20), client_id="90071992547409931234")
            fact = BusinessFact("invoice:1:paid", org.pk, "paid", now-timedelta(hours=1),
                                "paid_invoice", Decimal("3900.00"), "RUB")
            assert deliver(fact, dry_run=True)["state"] == "eligible"
            assert not requests and not AcquisitionDelivery.objects.exists() and not token.called
            with override_settings(ACQUISITION_EXPORT_ENABLED=False):
                assert deliver(fact)["state"] == "disabled"
            result = deliver(fact)
            assert result["state"] == "accepted" and result["uploading_id"] == 301
            assert len(requests) == 1
            assert deliver(fact)["state"] == "already_reserved" and len(requests) == 1
            row = AcquisitionDelivery.objects.get()
            reply = {"uploading": {"id": 301, "status": "PROCESSED", "line_quantity": 1, "source_quantity": 1}}
            result = refresh_delivery(row)
            assert result["state"] == "processed" and result["matched_rows"] is None
            assert result["validated_rows"] == 1
            # Malformed positive responses must never become successful uploads.
            for bad in [{}, {"uploading": {}}, {"uploading": {"id": 0, "status": "UPLOADED"}},
                        {"uploading": {"id": True, "status": "UPLOADED"}},
                        {"uploading": {"id": 2, "status": "fictional"}},
                        {"error": "bad", "uploading": {"id": 2, "status": "UPLOADED"}}]:
                try:
                    validate_upload(bad)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Malformed API acknowledgement accepted")
            row.delete()
            reply = {"uploading": {"status": "UPLOADED"}}
            assert deliver(fact)["state"] == "unknown"
            count = len(requests)
            assert deliver(fact)["state"] == "already_reserved" and len(requests) == count
            AcquisitionDelivery.objects.all().delete()
            with patch.object(yandex_api, "_request", side_effect=TimeoutError("do not log identifiers")):
                assert deliver(fact)["state"] == "unknown"
            assert AcquisitionDelivery.objects.get().uploading_id is None
            AcquisitionDelivery.objects.all().delete()
            revoke_grants(AnalyticsGrant.objects.filter(pk=grant.pk))
            assert deliver(fact)["state"] == "ineligible" and len(requests) == count
            grant.refresh_from_db()
            assert grant.client_id == "" and grant.revoked_at
            # A historical yclid is not permission or identity for this worker.
            org.source_yclid = "123456"
            org.save(update_fields=["source_yclid"])
            assert deliver(fact)["state"] == "ineligible"
            assert not AcquisitionDelivery.objects.exists()
        print("PASS acquisition delivery: consent, exact ClientID/money, no dry-run writes/network, durable unknown, no replay, accepted != matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
