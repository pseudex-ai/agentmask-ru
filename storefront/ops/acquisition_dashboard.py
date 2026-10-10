"""Operator-only measurement readiness and goal reports, not a bidding console."""
from datetime import timedelta
from decimal import Decimal
import json
import time

from django.conf import settings
from django.db.models import Count, Sum
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils.dateparse import parse_datetime
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ops.views import _ops_gate
from ops.acquisition_catalog import EVENTS, BY_ID
from ops.acquisition_consent import AnalyticsGrant
from ops.acquisition_delivery import AcquisitionDelivery, TARGETS
from ops.analytics_models import Funnel
from ops.acquisition_reports import build_report_plan, collect_reports
from ops import collect, yandex_api
from ops.acquisition_lifecycle import AcquisitionOutcome, KINDS, record_outcome, cohort_retention
from accounts.models import Organization
from billing.models import Invoice


def _dump(value):
    def encode(obj):
        if isinstance(obj, Decimal) and obj.is_finite():
            return {"decimal": str(obj)}
        raise TypeError("Unsupported report state value")
    return json.dumps(value, default=encode)


def _load(value):
    return json.loads(value, object_hook=lambda obj: Decimal(obj["decimal"])
                      if set(obj) == {"decimal"} and isinstance(obj["decimal"], str) else obj)


def _goal_catalog():
    result = []
    for goal in yandex_api.goals():
        if goal.get("type") != "action" or goal.get("status", "Active") != "Active":
            continue
        conditions = goal.get("conditions") or []
        if len(conditions) != 1 or conditions[0].get("type") != "exact":
            continue
        name = conditions[0].get("url")
        if name in BY_ID:
            result.append({"id": str(goal["id"]), "name": name,
                           "title": BY_ID[name].title, "kind": BY_ID[name].kind})
    if not result:
        raise ValueError("No active known goals")
    return result


@_ops_gate
@require_http_methods(["GET", "POST"])
def dashboard(request):
    now = timezone.now()
    try:
        days = max(1, min(31, int(request.GET.get("days", "7"))))
    except (ValueError, TypeError):
        days = 7
    error = ""
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "attest_outcome":
                if request.POST.get("evidence_confirmed") != "1":
                    raise ValidationError("explicit_attestation_required")
                org = Organization.objects.get(pk=request.POST.get("organization", ""))
                invoice_id = request.POST.get("invoice", "")
                invoice = Invoice.objects.get(pk=int(invoice_id)) if invoice_id else None
                record_outcome(request.user, org, request.POST.get("kind"),
                    parse_datetime(request.POST.get("event_at", "")), invoice=invoice,
                    amount=request.POST.get("amount") or None,
                    reference=request.POST.get("reference") or None)
                return redirect(request.path + "?days=" + str(days))
            if action == "report_start":
                saved = request.session.get("acquisition_report")
                if saved and _load(saved).get("resume_at", 0) > time.time():
                    raise ValueError("Previous report cooldown")
                campaign = request.POST.get("campaign", "")
                if not campaign.isascii() or not campaign.isdigit() or int(campaign) <= 0:
                    raise ValueError("Invalid campaign")
                # Read-only API verifies the same counter belongs to this EPС.
                reply = yandex_api.direct("campaigns", "get", {
                    "SelectionCriteria": {"Ids": [int(campaign)]},
                    "FieldNames": ["Id", "Type"],
                    "UnifiedCampaignFieldNames": ["CounterIds"]})
                campaigns = (reply.get("result") or {}).get("Campaigns") or []
                if len(campaigns) != 1 or str(campaigns[0].get("Id")) != campaign:
                    raise ValueError("Campaign not found")
                counters = (campaigns[0].get("UnifiedCampaign") or {}).get("CounterIds") or {}
                if str(settings.METRIKA_ID) not in {str(x) for x in counters.get("Items", [])}:
                    raise ValueError("Counter is not linked")
                today = timezone.localdate()
                plan = build_report_plan((today-timedelta(days=days-1)).isoformat(), today.isoformat(),
                    goals=_goal_catalog(), campaign_ids=[campaign], counter_id=str(settings.METRIKA_ID),
                    level=request.POST.get("level", "ad"), attribution="LC", page_limit=500)
                bundle = {"plan": plan, "state": None}
            elif action == "report_continue":
                bundle = _load(request.session["acquisition_report"])
                if time.time() < bundle.get("resume_at", 0):
                    raise ValueError("Report is still processing")
            else:
                raise ValueError("Unknown action")
            result = collect_reports(bundle["plan"], state=bundle.get("state"), max_requests=2)
            bundle.update(state=result.get("state"), result=result,
                          resume_at=time.time()+max(10, result.get("retry_in") or 0))
            encoded = _dump(bundle)
            if len(encoded) > 2_000_000:
                raise ValueError("Report is too large for this view; narrow the window")
            request.session["acquisition_report"] = encoded
            return redirect(request.path + "?days=" + str(days))
        except (ValidationError, PermissionDenied, Organization.DoesNotExist, Invoice.DoesNotExist):
            error = "Подтверждение не записано: проверьте полномочия, источник, организацию, счёт, сумму и время с часовым поясом. Состояние платежей не изменялось."
        except Exception:
            # Provider messages may contain account details. Preserve API error
            # semantics in the report result, not raw exception text in HTML.
            error = "Отчёт не обновлён. Проверьте ID кампании, привязку счётчика и доступ; для ожидающего отчёта дождитесь разрешённого повтора."
    report = None
    try:
        saved = _load(request.session.get("acquisition_report", "null"))
        if saved:
            report = saved.get("result")
    except (ValueError, TypeError, KeyError):
        report = None
    rows = []
    if report and report.get("status") == "complete":
        for row in report.get("rows", []):
            rows.append({"date": row.get("Date"), "campaign": row.get("CampaignId"),
                         "group": row.get("AdGroupId"), "ad": row.get("AdId"),
                         "cost": row.get("Cost"), "clicks": row.get("Clicks"),
                         "goals": [{"name": goal.get("title", goal["name"]),
                                    "value": row.get(f"Conversions_{goal['id']}_LC")}
                                   for goal in report.get("goals", [])]})
    stats = list(AcquisitionDelivery.objects.values("state").annotate(n=Count("pk")).order_by("state"))
    grant_stats = {"provisional": AnalyticsGrant.objects.filter(revoked_at__isnull=True, verified_at__isnull=True, expires_at__gt=now).exclude(client_id="").count(),
                   "verified": AnalyticsGrant.objects.filter(revoked_at__isnull=True, verified_at__isnull=False, expires_at__gt=now).exclude(client_id="").count(),
                   "revoked": AnalyticsGrant.objects.filter(revoked_at__isnull=False).count()}
    retention = cohort_retention(now-timedelta(days=days), now=now)
    lifecycle = list(AcquisitionOutcome.objects.filter(event_at__gte=now-timedelta(days=days), event_at__lte=now)
                     .values("kind", "source").annotate(n=Count("pk"), amount=Sum("amount")))
    friction = list(Funnel.objects.filter(at__gte=now-timedelta(days=days), at__lte=now,
        step__in=["signup_refused", "activation_email_resent", "checkout_started", "checkout_unavailable", "payment_failed"])
        .values("step", "detail").annotate(observations=Count("pk")).order_by("step", "detail"))
    cash = Invoice.objects.filter(state=Invoice.PAID, paid_at__gte=now-timedelta(days=days),
        paid_at__lt=now, total__gt=0).exclude(organization__source_utm_source="qa_r01").aggregate(
            invoice_count=Count("pk"), organisations=Count("organization_id", distinct=True), received=Sum("total"))
    internal_events = {"signup_rejected", "activation_email_resent", "checkout_started", "checkout_unavailable", "payment_failed", "repeat_payment", "paid_service_pending", "usage_retained", "usage_stalled"}
    event_rows = [{"event": event,
                   "implementation": "браузерный обработчик" if event.external_default else
                   "серверный экспорт с отдельным согласием" if event.identifier in TARGETS else
                   "внутренний подтверждённый сотрудником факт" if event.identifier in KINDS else
                   "внутренняя диагностика / наблюдения" if event.identifier in internal_events else
                   "каталог / отдельная проверка источника"}
                  for event in EVENTS]
    return render(request, "ops/acquisition.html", {"days": days, "error": error,
        "cohort": collect.acquisition_cohort(now-timedelta(days=days), until=now),
        "grant_stats": grant_stats, "deliveries": stats, "events": event_rows,
        "retention": retention, "lifecycle": lifecycle, "friction": friction, "cash": cash,
        "outcome_kinds": [{"id": kind, "title": BY_ID[kind].title} for kind in KINDS],
        "link_enabled": getattr(settings, "ACQUISITION_LINK_ENABLED", False),
        "export_enabled": getattr(settings, "ACQUISITION_EXPORT_ENABLED", False),
        "report": report, "report_rows": rows,
        "report_resume": bool(report and report.get("state") is not None)})
