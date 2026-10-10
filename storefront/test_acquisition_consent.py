"""Offline SQLite acceptance tests; real Django CSRF/auth, synthetic mailbox only."""
import io
import os
from pathlib import Path
import re
import tempfile
from datetime import timedelta
from unittest.mock import patch


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        keep = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
        os.environ.clear()
        os.environ.update(keep)
        os.environ.update(DJANGO_SETTINGS_MODULE="pseudex_site.settings", PSEUDEX_DEBUG="1",
                          PSEUDEX_SECRET_KEY="offline-consent-fixture-only",
                          PSEUDEX_ALLOWED_HOSTS="testserver", PSEUDEX_DB_PATH=str(root / "db.sqlite3"),
                          PSEUDEX_ANALYTICS_SALT_FILE=str(root / "salt"))
        attempts = []

        def deny(*args, **kwargs):
            attempts.append(True)
            raise AssertionError("Network prohibited")

        with patch("socket.socket.connect", deny), patch("socket.socket.connect_ex", deny), \
                patch("socket.getaddrinfo", deny):
            import django
            django.setup()
            from django.core import mail
            from django.core.cache import cache
            from django.core.management import call_command
            from django.db import connections
            from django.test import Client, override_settings
            from django.utils import timezone
            from accounts.models import User, Organization, Membership
            from ops import acquisition_consent as c
            with override_settings(ACQUISITION_LINK_ENABLED=True,
                                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                                   STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
                call_command("migrate", verbosity=0, interactive=False)
                call_command("seed_plans", "--no-licensing", verbosity=0, stdout=io.StringIO())

                def browser():
                    client = Client(enforce_csrf_checks=True)
                    page = client.get("/analytics/preferences", secure=True)
                    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())[1]
                    client.cookies["_ym_uid"] = "999999999999999999999999"
                    return client, token

                def post(client, token, path, data=None, **kwargs):
                    return client.post(path, data or {}, secure=True, HTTP_X_CSRFTOKEN=token,
                                       HTTP_ORIGIN="https://testserver", **kwargs)

                payload = dict(purpose_revision=c.PURPOSE_REVISION, affirmative="1",
                               browser_consent="yes", client_id="999999999999999999999999")
                a, token = browser()
                assert a.post("/analytics/grant", payload, secure=True).status_code == 403
                assert a.post("/analytics/grant", payload, secure=True, HTTP_X_CSRFTOKEN=token,
                              HTTP_ORIGIN="https://evil.invalid").status_code == 403
                for change in ({"affirmative": "0"}, {"purpose_revision": "old"},
                               {"browser_consent": "no"}, {"client_id": "١٢٣"},
                               {"client_id": "1" * 33}, {"client_id": "123"}, {"client_id": 123}):
                    assert post(a, token, "/analytics/grant", {**payload, **change}).status_code == 400
                with override_settings(ACQUISITION_LINK_ENABLED=False):
                    assert post(a, token, "/analytics/grant", payload).status_code == 403
                assert not c.AnalyticsGrant.objects.exists()
                prepared = post(a, token, "/analytics/prepare", payload)
                assert prepared.status_code == 200
                cookie = prepared.cookies[c.MANAGEMENT_COOKIE]
                assert not c.AnalyticsGrant.objects.get().client_id
                response = post(a, token, "/analytics/grant", payload)
                assert response.status_code == 200
                assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "Lax"
                assert payload["client_id"] not in cookie.value and payload["client_id"] not in response.content.decode()
                row = c.AnalyticsGrant.objects.get()
                assert row.client_id == payload["client_id"] and not row.yclid
                expiry = row.expires_at
                post(a, token, "/analytics/grant", payload)
                row.refresh_from_db()
                assert c.AnalyticsGrant.objects.count() == 1 and row.expires_at == expiry
                assert not c.grant_eligible(row, timezone.now())

                def signup(client, csrf, email, **extra):
                    cache.clear()
                    return post(client, csrf, "/signup", {"email": email, "company": "Synthetic",
                        "plan": "start", "consent": "1", "terms": "1", **extra})

                assert signup(a, token, "one@example.invalid", consent="0").status_code == 302
                row.refresh_from_db()
                assert row.user_id is None
                assert signup(a, token, "one@example.invalid").status_code == 200
                row.refresh_from_db()
                assert row.user_id and row.organization_id and row.verified_at is None
                org, user = row.organization, row.user
                event_at = timezone.now()
                assert c.eligible_grant(org, event_at) is None
                activation = re.search(r"https://testserver/activate\?t=([^\s]+)", mail.outbox[-1].body)[1]
                page = a.get("/activate", {"t": activation}, secure=True)
                assert page.status_code == 200
                row.refresh_from_db()
                assert row.verified_at is None
                assert 'name="acquisition_confirmation"' in page.content.decode()
                assert c.confirm_grant(org, user) == 0  # Mailbox alone isn't purpose consent.
                assert post(a, token, "/activate", {"t": activation,
                    "acquisition_confirmation": c.PURPOSE_REVISION}).status_code == 302
                row.refresh_from_db()
                assert row.verified_at and c.eligible_grant(org, event_at).pk == row.pk
                assert not c.grant_eligible(row, row.granted_at - timedelta(seconds=1))
                assert not c.grant_eligible(row, timezone.now() + timedelta(days=1))
                assert not c.grant_eligible(row, event_at, row.reference_at + timedelta(days=20, seconds=1))
                assert not c.grant_eligible(row, event_at, row.expires_at)
                with override_settings(ACQUISITION_LINK_ENABLED=False):
                    assert c.eligible_grant(org, event_at) is None

                # Legacy yes / legal checkbox / missing or forged receipts do not grant.
                b, bt = browser()
                assert signup(b, bt, "two@example.invalid").status_code == 200
                assert c.AnalyticsGrant.objects.count() == 1
                b.cookies[c.MANAGEMENT_COOKIE] = "forged"
                assert post(b, bt, "/analytics/revoke").status_code == 400
                assert signup(b, bt, "three@example.invalid").status_code == 200
                assert c.AnalyticsGrant.objects.count() == 1
                # Victim/existing-email resubmission cannot move the attacker's grant.
                attacker, at = browser()
                assert post(attacker, at, "/analytics/prepare", payload).status_code == 200
                assert post(attacker, at, "/analytics/grant", payload).status_code == 200
                unbound = c.AnalyticsGrant.objects.exclude(pk=row.pk).get()
                assert signup(attacker, at, "one@example.invalid").status_code == 302
                unbound.refresh_from_db()
                assert not unbound.user_id
                # A fresh victim mailbox is not protected by the existing-user
                # guard. Victim activation in another browser must NOT endorse
                # the attacker's anonymous consent or ClientID.
                assert signup(attacker, at, "fresh-victim@example.invalid").status_code == 200
                victim_link = re.search(r"https://testserver/activate\?t=([^\s]+)", mail.outbox[-1].body)[1]
                victim, vt = browser()
                victim_page = victim.get("/activate", {"t": victim_link}, secure=True)
                assert 'name="acquisition_confirmation"' not in victim_page.content.decode()
                assert post(victim, vt, "/activate", {"t": victim_link,
                    "acquisition_confirmation": c.PURPOSE_REVISION}).status_code == 302
                unbound.refresh_from_db()
                assert unbound.verified_at is None
                assert c.eligible_grant(unbound.organization, timezone.now()) is None
                # Bound receipt cannot attach to another newly-created account.
                anon, ant = browser()
                anon.cookies[c.MANAGEMENT_COOKIE] = cookie.value
                assert signup(anon, ant, "four@example.invalid").status_code == 200
                row.refresh_from_db()
                assert row.user_id == user.pk
                # Logout-independent revocation clears identifiers before acknowledgment.
                assert post(anon, ant, "/analytics/revoke").status_code == 200
                row.refresh_from_db()
                assert row.revoked_at and not row.client_id and not row.yclid
                anon.cookies[c.MANAGEMENT_COOKIE] = cookie.value
                signup(anon, ant, "five@example.invalid")
                row.refresh_from_db()
                assert row.revoked_at and not row.client_id
                # Authenticated cross-device revocation is per-user, not per-org.
                second = User.objects.get(email="two@example.invalid")
                Membership.objects.create(user=second, organization=org)
                now = timezone.now()
                own = c.AnalyticsGrant.objects.create(user=user, organization=org, client_id="123")
                other = c.AnalyticsGrant.objects.create(user=second, organization=org, client_id="456")
                cross, ct = browser()
                cross.force_login(user)
                page = cross.get("/analytics/preferences", secure=True)
                ct = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())[1]
                assert "analytics.js" not in page.content.decode()
                assert post(cross, ct, "/analytics/preferences").status_code == 200
                own.refresh_from_db(); other.refresh_from_db()
                assert own.revoked_at and not own.client_id
                assert other.revoked_at is None and other.client_id == "456"
                c.AnalyticsGrant.objects.filter(pk=other.pk).update(expires_at=now - timedelta(seconds=1))
                c.purge_expired()
                other.refresh_from_db()
                assert other.revoked_at and not other.client_id
                org.source_yclid = "987654321"
                org.save(update_fields=["source_yclid"])
                assert c.eligible_grant(org, event_at) is None
                assert not attempts
                print("PASS consent: CSRF, IDs, provisional mailbox proof, no legacy authority, person scope, expiry, purge")
            connections.close_all()


if __name__ == "__main__":
    main()
