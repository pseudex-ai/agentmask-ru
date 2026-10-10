"""Consent-bound offline conversions with an uncertainty-preserving ledger.

No blind POST retries. A durable UNKNOWN reservation precedes every network
side effect; a process death therefore cannot turn an ambiguous upload into a
fresh event next run. A valid upload ID means accepted, never proven row-level
attribution. ClientID is read only under the current grant lock, never copied
into this ledger or logs. Legacy yclid-only ConversionSent is not reused.
"""
import csv
import io
import re
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from ops import yandex_api

TARGETS = frozenset({"activated", "key_issued", "first_lease", "first_mask", "paid"})
REMOTE_STATUSES = frozenset({"PREPARED", "UPLOADED", "EXPORTED", "MATCHED", "PROCESSED", "LINKAGE_FAILURE"})


class AcquisitionDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    counter_id = models.CharField(max_length=32)
    organization_id = models.CharField(max_length=32, db_index=True)
    target = models.CharField(max_length=64)
    fact_key = models.CharField(max_length=100)
    event_at = models.DateTimeField()
    grant = models.ForeignKey("ops.AnalyticsGrant", null=True, on_delete=models.SET_NULL)
    state = models.CharField(max_length=24, default="unknown", db_index=True)
    uploading_id = models.BigIntegerField(null=True)
    remote_status = models.CharField(max_length=24, blank=True)
    source_quantity = models.PositiveIntegerField(null=True)
    line_quantity = models.PositiveIntegerField(null=True)
    error_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    checked_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "ops"
        constraints = [models.UniqueConstraint(
            fields=["counter_id", "organization_id", "target"],
            name="acq_first_outcome_once")]


def export_enabled():
    # Independent opt-ins: browser purpose availability must not itself export.
    return bool(getattr(settings, "ACQUISITION_EXPORT_ENABLED", False)
                and getattr(settings, "ACQUISITION_LINK_ENABLED", False)
                and not getattr(settings, "YANDEX_CONVERSIONS", False)
                and settings.METRIKA_ID)


def conversion_csv(fact, client_id, *, now):
    if fact.target not in TARGETS:
        raise ValueError("unsupported_target")
    if not isinstance(client_id, str) or not re.fullmatch(r"[0-9]{1,32}", client_id):
        raise ValueError("invalid_client_id")
    if fact.at.tzinfo is None or fact.at.utcoffset() is None or fact.at >= now:
        raise ValueError("invalid_event_time")
    headers = ["Target", "DateTime", "ClientId"]
    row = [fact.target, int(fact.at.timestamp()), client_id]
    if fact.target == "paid":
        try:
            price = Decimal(str(fact.price))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("invalid_payment_amount") from None
        if (fact.source != "paid_invoice" or fact.currency != "RUB"
                or not price.is_finite() or price <= 0 or price > Decimal("9999999999.99")
                or price != price.quantize(Decimal("0.01"))):
            raise ValueError("invalid_payment_amount")
        headers += ["Price", "Currency"]
        row += [f"{price:.2f}", "RUB"]
    elif fact.price is not None:
        raise ValueError("non_payment_value_forbidden")
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerow(row)
    return stream.getvalue()


def validate_upload(payload, *, expected_id=None):
    if not isinstance(payload, dict) or payload.get("errors") or payload.get("error"):
        raise ValueError("upload_error_payload")
    obj = payload.get("uploading")
    if not isinstance(obj, dict):
        raise ValueError("upload_missing")
    number = obj.get("id")
    # A JSON boolean is an int in Python; it is not an upload identifier.
    if (isinstance(number, bool) or not isinstance(number, (int, str))
            or not re.fullmatch(r"[0-9]{1,19}", str(number))
            or not 0 < int(number) < 2**63):
        raise ValueError("upload_id_invalid")
    if expected_id is not None and int(number) != expected_id:
        raise ValueError("upload_id_mismatch")
    if obj.get("status") not in REMOTE_STATUSES:
        raise ValueError("upload_status_unknown")
    for field in ("source_quantity", "line_quantity"):
        if obj.get(field) is not None and (type(obj[field]) is not int or obj[field] < 0):
            raise ValueError("upload_count_invalid")
    return {"uploading_id": int(number), "remote_status": obj["status"],
            "source_quantity": obj.get("source_quantity"),
            "line_quantity": obj.get("line_quantity")}


def deliver(fact, *, dry_run=False):
    """One first milestone per organisation/counter, with no implicit retries.

    Serialising revocation and dispatch on the same grant means an acknowledged
    revoke prevents subsequent dispatches. Network calls can hold this lock for
    the bounded transport timeout. Already in-flight data cannot be recalled.
    """
    from ops.acquisition_consent import AnalyticsGrant, eligible_grant, grant_eligible

    if not export_enabled():
        return {"state": "disabled"}
    if fact.target not in TARGETS:
        return {"state": "unsupported_target"}
    now = timezone.now()
    grant = eligible_grant(fact.organization_id, fact.at, now=now)
    if grant is None:
        return {"state": "ineligible"}
    # Existing legacy uploads suppress duplicates even if their old bookkeeping
    # was weak. Do not silently backfill or try to repair them by another POST.
    from ops.analytics_models import ConversionSent
    if ConversionSent.objects.filter(organization_id=fact.organization_id, target=fact.target).exists():
        return {"state": "legacy_delivery_exists"}
    counter = str(settings.METRIKA_ID)
    if not re.fullmatch(r"[0-9]{1,19}", counter):
        return {"state": "invalid_counter"}
    if AcquisitionDelivery.objects.filter(counter_id=counter, organization_id=fact.organization_id,
                                          target=fact.target).exists():
        return {"state": "already_reserved"}
    try:
        conversion_csv(fact, grant.client_id, now=now)
    except ValueError as error:
        return {"state": "invalid_fact", "reason": str(error)}
    if dry_run:
        return {"state": "eligible", "target": fact.target}  # No token refresh or writes.
    # Refresh before reservation: a failure here cannot have uploaded anything.
    try:
        token = yandex_api.access_token()
    except Exception:
        return {"state": "auth_unavailable"}
    delivery, created = AcquisitionDelivery.objects.get_or_create(
        counter_id=counter, organization_id=fact.organization_id, target=fact.target,
        defaults={"grant": grant, "event_at": fact.at, "fact_key": fact.key,
                  "state": "unknown", "error_code": "dispatch_unconfirmed"})
    if not created:
        return {"state": "already_reserved"}
    with transaction.atomic():
        current = AnalyticsGrant.objects.select_for_update().get(pk=grant.pk)
        ledger = AcquisitionDelivery.objects.select_for_update().get(pk=delivery.pk)
        if not export_enabled() or not grant_eligible(current, fact.at, now=timezone.now()):
            ledger.state, ledger.error_code = "cancelled", "consent_no_longer_valid"
            ledger.checked_at = timezone.now()
            ledger.save(update_fields=["state", "error_code", "checked_at"])
            return {"state": "cancelled"}
        body = conversion_csv(fact, current.client_id, now=timezone.now())
        # The nonce contains no visitor, invoice or account identifier. It is a
        # reconciliation handle, NOT a provider-supported idempotency key.
        comment = "psxacq" + delivery.id.hex
        try:
            response = yandex_api._request(
                "POST", f"{yandex_api.METRIKA_API}/management/v1/counter/{counter}/offline_conversions/upload",
                params={"comment": comment},
                headers={"Authorization": f"OAuth {token}"},
                files={"file": ("conversions.csv", body, "text/csv")})
            if response.status_code != 200:
                raise ValueError("upload_http_error")
            result = validate_upload(response.json())
            for key, value in result.items():
                setattr(ledger, key, value)
            ledger.state = "linkage_failure" if result["remote_status"] == "LINKAGE_FAILURE" else "accepted"
            ledger.error_code = ""
        except Exception:
            # Don't print exception text: external errors can echo identifiers.
            # Preserve the durable uncertainty; automatic POST replay is unsafe.
            ledger.state, ledger.error_code = "unknown", "upload_unconfirmed"
        ledger.checked_at = timezone.now()
        ledger.save()
        return {"state": ledger.state, "delivery_id": str(ledger.id),
                "uploading_id": ledger.uploading_id, "remote_status": ledger.remote_status}


def reconcile_unknown(delivery, *, page_limit=100, max_pages=5):
    """Find a possibly accepted POST by its nonce, never replay the POST.

    Only a complete bounded list with exactly one match establishes its upload
    identifier. No match, truncated history or duplicate nonce stays UNKNOWN.
    No raw CSV or visitor records are downloaded for reconciliation.
    """
    if not export_enabled() or delivery.state != "unknown":
        return {"state": "not_reconciled"}
    if not 1 <= page_limit <= 1000 or not 1 <= max_pages <= 5:
        raise ValueError("invalid_reconciliation_budget")
    matches = []
    complete = False
    try:
        for page in range(max_pages):
            response = yandex_api.metrika_get(
                f"/management/v1/counter/{delivery.counter_id}/offline_conversions/uploadings",
                {"type": "BASIC", "limit": page_limit, "offset": page * page_limit})
            items = response.get("uploadings")
            if not isinstance(items, list):
                raise ValueError("invalid_upload_list")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("invalid_upload_item")
                if item.get("comment") == "psxacq" + delivery.id.hex:
                    matches.append(validate_upload({"uploading": item}))
            if len(items) < page_limit:
                complete = True
                break
    except Exception:
        return {"state": "unknown", "reason": "reconciliation_unavailable"}
    if not complete or len(matches) != 1:
        return {"state": "unknown", "reason": "nonce_not_unique_or_history_incomplete"}
    values = matches[0]
    with transaction.atomic():
        row = AcquisitionDelivery.objects.select_for_update().get(pk=delivery.pk)
        if row.state != "unknown":
            return {"state": row.state}
        for field, value in values.items():
            setattr(row, field, value)
        row.state = ("linkage_failure" if row.remote_status == "LINKAGE_FAILURE"
                     else "processed" if row.remote_status == "PROCESSED" else "accepted")
        row.error_code, row.checked_at = "", timezone.now()
        row.save()
    return {"state": row.state, "uploading_id": row.uploading_id, "matched_rows": None}


def refresh_delivery(delivery):
    """Read remote batch status; never claim validated rows are matched rows."""
    if not export_enabled() or not delivery.uploading_id:
        return {"state": "not_polled"}
    try:
        payload = yandex_api.metrika_get(
            f"/management/v1/counter/{delivery.counter_id}/offline_conversions/uploading/{delivery.uploading_id}")
        values = validate_upload(payload, expected_id=delivery.uploading_id)
    except Exception:
        delivery.error_code = "status_unavailable"
        delivery.checked_at = timezone.now()
        delivery.save(update_fields=["error_code", "checked_at"])
        return {"state": "status_unavailable"}
    for key, value in values.items():
        setattr(delivery, key, value)
    delivery.state = ("linkage_failure" if delivery.remote_status == "LINKAGE_FAILURE"
                      else "processed" if delivery.remote_status == "PROCESSED" else "accepted")
    delivery.checked_at, delivery.error_code = timezone.now(), ""
    delivery.save()
    return {"state": delivery.state, "remote_status": delivery.remote_status,
            "validated_rows": delivery.line_quantity, "matched_rows": None}
