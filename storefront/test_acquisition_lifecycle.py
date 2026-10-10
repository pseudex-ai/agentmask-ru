"""Standalone lifecycle regression: temporary SQLite, sockets forbidden, no money APIs."""
import os
from pathlib import Path
import tempfile
from unittest.mock import patch


def main():
    keep = {k: os.environ[k] for k in ("PATH", "HOME", "SYSTEMROOT") if k in os.environ}
    os.environ.clear()
    os.environ.update(keep)
    with tempfile.TemporaryDirectory(prefix="psx-lifecycle-") as directory:
        os.environ.update(DJANGO_SETTINGS_MODULE="pseudex_site.settings", PSEUDEX_DEBUG="1",
            PSEUDEX_SECRET_KEY="synthetic-lifecycle-only", PSEUDEX_DB_PATH=str(Path(directory)/"db.sqlite3"))
        def forbidden(*args, **kwargs):
            raise AssertionError("Unexpected network")
        with patch("socket.socket.connect", forbidden), patch("socket.getaddrinfo", forbidden):
            import django
            django.setup()
            from datetime import timedelta
            from decimal import Decimal
            from django.contrib.auth import get_user_model
            from django.core.exceptions import PermissionDenied, ValidationError
            from django.core.management import call_command
            from django.db.models.deletion import ProtectedError
            from django.utils import timezone
            from accounts.models import Organization
            from billing.models import Invoice, Subscription, Plan
            from ops.analytics_models import Funnel, UsageDay
            from ops.acquisition_lifecycle import (
                AcquisitionOutcome, record_outcome, cohort_retention, STAFF_ATTESTED,
                EXTERNAL_EXPORT_DEFAULT, KINDS,
            )
            from ops.acquisition_delivery import TARGETS
            assert not set(KINDS) & TARGETS
            # Explicit import above also registers the model before lead adds
            # ops.models import; schema comes from the real numbered migration.
            call_command("migrate", verbosity=0, interactive=False)
            call_command("makemigrations", "ops", dry_run=True, check=True, verbosity=0)
            now = timezone.now()
            at = now - timedelta(days=1)
            org = Organization.objects.create(display_name="Synthetic", created_at=now-timedelta(days=50))
            other = Organization.objects.create(display_name="Other", created_at=org.created_at)
            staff = get_user_model().objects.create_user(email="staff@example.invalid", is_staff=True)
            staff.is_verified = lambda: True
            user = get_user_model().objects.create_user(email="user@example.invalid")
            user.is_verified = lambda: True
            inactive = get_user_model().objects.create_user(email="inactive@example.invalid",
                                                           is_staff=True, is_active=False)
            inactive.is_verified = lambda: True
            denied_count = 0
            def denies(fn, error=ValidationError):
                nonlocal denied_count
                count = AcquisitionOutcome.objects.count()
                try:
                    fn()
                except error:
                    denied_count += 1
                else:
                    raise AssertionError("Expected rejection")
                assert AcquisitionOutcome.objects.count() == count
            def attest(**kw):
                return record_outcome(**dict(dict(actor=staff, organization=org,
                    kind="qualified_lead", event_at=at), **kw))
            for actor in (None, user, inactive):
                denies(lambda actor=actor: attest(actor=actor), PermissionDenied)
            staff.is_verified = lambda: False
            denies(lambda: attest(), PermissionDenied)
            del staff.is_verified
            denies(lambda: attest(), PermissionDenied)
            staff.is_verified = lambda: True
            # Stale in-memory privilege doesn't override current database state.
            get_user_model().objects.filter(pk=staff.pk).update(is_staff=False)
            denies(lambda: attest(), PermissionDenied)
            get_user_model().objects.filter(pk=staff.pk).update(is_staff=True)
            lead = attest(reference="doc:qualification-001")
            assert lead.source == STAFF_ATTESTED and lead.actor_id == staff.pk
            assert lead.currency == "" and lead.amount is None and not EXTERNAL_EXPORT_DEFAULT
            assert attest(reference="doc:qualification-001").pk == lead.pk
            assert "qualification" not in lead.reference_digest and len(lead.reference_digest) == 64
            loop = attest(kind="successful_agent_loop", reference="doc:acceptance-001")
            assert loop.invoice_id is None
            implicit = attest(event_at=at-timedelta(minutes=1))
            assert attest(event_at=implicit.event_at).pk == implicit.pk
            for kw in [dict(kind="paid"), dict(event_at=now+timedelta(seconds=1)),
                       dict(event_at=at.replace(tzinfo=None)), dict(event_at=org.created_at-timedelta(days=1)),
                       dict(amount="1"), dict(reference="email@example.invalid"),
                       dict(reference="doc:"+"x"*113), dict(reference="doc:+79991234567"),
                       dict(reference="https://example.invalid"),
                       dict(reference="doc:qualification-001", kind="successful_agent_loop"),
                       dict(reference="doc:qualification-001", organization=other)]:
                denies(lambda kw=kw: attest(**kw))
            def invoice(number, **kw):
                return Invoice.objects.create(**dict(dict(organization=org, number=number,
                    state=Invoice.PAID, paid_at=now-timedelta(days=3), total=Decimal("100.00"),
                    period_start=(now-timedelta(days=30)).date(), period_end=now.date()), **kw))
            first = invoice("test-first")
            second = invoice("test-second", paid_at=now-timedelta(days=2))
            wrong = invoice("test-other", organization=other)
            unpaid = invoice("test-unpaid", state=Invoice.ISSUED)
            missing = invoice("test-missing", organization=other, paid_at=None)
            future = invoice("test-future", paid_at=now+timedelta(days=1))
            zero = invoice("test-zero", total=Decimal("0"))
            invoices_before = list(Invoice.objects.values())
            subscriptions_before = list(Subscription.objects.values())
            def financial(**kw):
                return attest(**dict(dict(kind="refund_confirmed", invoice=first,
                                           amount="30.00", reference="provider:refund-001"), **kw))
            for kw in [dict(invoice=wrong), dict(invoice=unpaid), dict(invoice=missing, organization=other),
                       dict(invoice=future), dict(invoice=zero),
                       dict(invoice=None), dict(reference=None), dict(amount=None),
                       dict(event_at=first.paid_at-timedelta(seconds=1))]:
                denies(lambda kw=kw: financial(**kw))
            for amount in ("-1", "0", "NaN", "Infinity", "-Infinity", "1.001", "1e9000", "101"):
                denies(lambda amount=amount: financial(amount=amount))
            denies(lambda: financial(kind="renewal_paid", amount="100"))
            denies(lambda: financial(kind="renewal_paid", invoice=second, amount="30"))
            denies(lambda: financial(kind="renewal_paid", invoice=wrong, organization=other, amount="100"))
            renewal = financial(kind="renewal_paid", invoice=second, amount="100",
                                reference="doc:renewal-001")
            assert renewal.currency == "RUB" and renewal.source == STAFF_ATTESTED
            denies(lambda: financial(kind="renewal_paid", invoice=second, amount="100",
                                     reference="doc:renewal-other"))
            refund = financial()
            assert financial().pk == refund.pk
            denies(lambda: financial(amount="31"))
            denies(lambda: financial(invoice=second))
            financial(amount="70", reference="provider:refund-002")
            denies(lambda: financial(amount="0.01", reference="provider:refund-003"))
            assert AcquisitionOutcome.objects.filter(kind="refund_confirmed").count() == 2
            assert list(Invoice.objects.values()) == invoices_before
            assert list(Subscription.objects.values()) == subscriptions_before
            denies(lambda: lead.save())
            denies(lambda: lead.delete())
            denies(lambda: AcquisitionOutcome.objects.filter(pk=lead.pk).update(amount=1))
            denies(lambda: AcquisitionOutcome.objects.all().delete())
            denies(lambda: AcquisitionOutcome.objects.create(organization=org, kind="qualified_lead", event_at=at))
            denies(lambda: AcquisitionOutcome.objects.bulk_create([AcquisitionOutcome()]))
            denies(lambda: staff.delete(), ProtectedError)
            denies(lambda: attest(kind="subscription_cancelled"))
            plan = Plan.objects.create(code="synthetic", title="Synthetic", monthly_price="100")
            sub = Subscription.objects.create(organization=org, plan=plan, state=Subscription.CANCELLED,
                                              trial_ends_at=at, current_period_end=at)
            before_cancel = list(Subscription.objects.values())
            cancellation = attest(kind="subscription_cancelled", reference="doc:cancellation-001")
            assert cancellation.source == STAFF_ATTESTED
            assert list(Subscription.objects.values()) == before_cancel

            # Retention: old orgs/new signups, first-not-latest entry, age maturity,
            # lifetime totals, sparse zeros, resets and QA are all separate cases.
            def cohort(name, age=40, qa=False, samples=()):
                entered = now-timedelta(days=age)
                entity = Organization.objects.create(display_name=name,
                    created_at=now-timedelta(days=100), source_utm_source="qa_r01" if qa else "")
                Funnel.objects.create(organization_id=entity.pk, step=Funnel.SIGNUP_SUBMITTED, at=entered)
                for day, count in samples:
                    UsageDay.objects.create(organization_id=entity.pk,
                        day=entered.date()+timedelta(days=day), requests=count)
                return entity
            cohort("active", samples=((7, 100), (14, 110)))
            cohort("flat-covered", samples=tuple((d, 100) for d in range(7, 15)))
            cohort("lifetime-only", samples=((7, 100),))
            cohort("sparse-flat", samples=((7, 100), (14, 100)))
            cohort("reset", samples=((7, 100), (9, 0), (14, 120)))
            cohort("negative", samples=((7, -1), (14, 1)))
            cohort("absent")
            cohort("young", age=3)
            cohort("QA", qa=True, samples=((7, 0), (14, 1)))
            old = cohort("old", age=80)
            Funnel.objects.create(organization_id=old.pk, step=Funnel.SIGNUP_SUBMITTED,
                                  at=now-timedelta(days=20))
            result = cohort_retention(now-timedelta(days=60), now=now, windows=(7, 14, 30))
            assert result["eligible"] == 8 and result["cohort"] == "first_signup_submitted"
            row = result["windows"][1]
            assert row == dict(age_days=14, eligible=8, mature=7, immature=1, evaluable=2,
                              active=1, inactive=1, unknown=5, rate=0.5, coverage=2/7), row
            assert result["windows"][2]["rate"] is None
            assert result["windows"][2]["unknown"] == 7
            cohort("mutable-today", age=14, samples=((7, 0), (14, 100)))
            current = cohort_retention(now-timedelta(days=60), now=now, windows=(14,))["windows"][0]
            assert current["unknown"] == 6 and current["mature"] == 8 and current["active"] == 1
            assert "Synthetic" not in str(result) and "example.invalid" not in str(result)
            empty = cohort_retention(now-timedelta(days=1), now=now)
            assert empty["eligible"] == 0
            assert all(r["coverage"] is None and r["rate"] is None for r in empty["windows"])
            for args in [dict(windows=(True,)), dict(windows=(0,)), dict(windows=()),
                         dict(now=now.replace(tzinfo=None))]:
                denies(lambda args=args: cohort_retention(now-timedelta(days=60), **args))
            print(f"PASS lifecycle: {denied_count} rejection checks; immutable staff/OTP evidence, "
                  "exact replay, refund cap, renewal classification, unchanged billing, mature retention/coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
