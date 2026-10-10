"""Bounded consent-aware export and status reconciliation; no ad mutations."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ops import yandex_api
from ops.acquisition_consent import AnalyticsGrant, purge_expired, eligible_grant
from ops.acquisition_delivery import AcquisitionDelivery, TARGETS, deliver, export_enabled, refresh_delivery, reconcile_unknown
from ops.acquisition_facts import current_facts


class Command(BaseCommand):
    help = "Проверить и отправить разрешённые consent-bound конверсии, без повторов неопределённых загрузок"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("limit должен быть от 1 до 100")
        dry = options["dry_run"]
        now = timezone.now()
        # Retention is independent of dispatch: turning export OFF must not
        # retain raw attribution identifiers past their promised lifetime.
        if not dry:
            purge_expired(now=now)
        if getattr(settings, "YANDEX_CONVERSIONS", False):
            raise CommandError("Отключите старый PSEUDEX_YANDEX_CONVERSIONS: два экспортёра недопустимы")
        if not export_enabled():
            self.stdout.write("disabled: новая передача конверсий не включена")
            return
        if not dry:
            uncertain = AcquisitionDelivery.objects.filter(state="unknown").order_by("created_at").first()
            if uncertain is not None:
                reconcile_unknown(uncertain)
                if AcquisitionDelivery.objects.filter(state="unknown").exists():
                    raise CommandError("Неопределённая загрузка: сверка не завершена; новые отправки приостановлены")
        orgs = list(AnalyticsGrant.objects.filter(
            revoked_at__isnull=True, verified_at__isnull=False,
            expires_at__gt=now, organization__isnull=False)
            .order_by("organization_id").values_list("organization_id", flat=True).distinct())
        facts, issues = current_facts(organization_ids=orgs, now=now)
        reserved = set(AcquisitionDelivery.objects.filter(counter_id=str(settings.METRIKA_ID))
                       .values_list("organization_id", "target"))
        # Apply the network budget AFTER excluding prior deliveries: otherwise
        # the same earliest paid account starves all later acquisitions forever.
        from ops.analytics_models import ConversionSent
        reserved.update(ConversionSent.objects.values_list("organization_id", "target"))
        facts = [fact for fact in facts if fact.target in TARGETS
                 and (fact.organization_id, fact.target) not in reserved
                 and eligible_grant(fact.organization_id, fact.at, now=now) is not None]
        # Goals are never created by this worker. A disabled/missing goal is a
        # delivery readiness failure, not a reason to invent identifiers.
        if not dry:
            try:
                reply = yandex_api.metrika_get(f"/management/v1/counter/{settings.METRIKA_ID}/goals")
                active = {condition.get("url") for goal in reply.get("goals", [])
                          if goal.get("type") == "action" and goal.get("status", "Active") == "Active"
                          for condition in goal.get("conditions", []) if condition.get("type") == "exact"}
            except Exception:
                raise CommandError("Не удалось проверить определения целей; отправка не начата") from None
            if not TARGETS <= active:
                raise CommandError("Не хватает активных точных серверных целей; отправка не начата")
        outcomes = {}
        for fact in facts[:limit]:
            result = deliver(fact, dry_run=dry)
            state = result["state"]
            outcomes[state] = outcomes.get(state, 0) + 1
            if state in {"unknown", "auth_unavailable"}:
                break
        if not dry:
            pending = AcquisitionDelivery.objects.filter(state="accepted", uploading_id__isnull=False).order_by("checked_at")[:limit]
            for item in pending:
                result = refresh_delivery(item)
                state = "poll_" + result["state"]
                outcomes[state] = outcomes.get(state, 0) + 1
        # No user/org IDs, contact values, ClientIDs, invoice numbers or raw API
        # errors in the console (including cron logs). Unknown is operationally
        # visible and must never be converted to zero successful matches.
        self.stdout.write(json.dumps({"dry_run": dry, "organisations_considered": len(orgs),
                                     "facts_considered": min(limit, len(facts)),
                                     "evidence_issues": len(issues), "outcomes": outcomes,
                                     "unknown_uploads": AcquisitionDelivery.objects.filter(state="unknown").count(),
                                     "matched_rows": None}, ensure_ascii=False))
        if not dry and (AcquisitionDelivery.objects.filter(state="unknown").exists()
                        or outcomes.get("poll_status_unavailable") or outcomes.get("auth_unavailable")):
            raise CommandError("Передача требует проверки: неопределённая загрузка или недоступен API; повторы POST запрещены")
