"""Read-only business evidence, never a new billing or licensing mutation.

An invoice is the source for payment time/amount. Legacy Funnel.detail is not
an authoritative financial ledger. Missing payment timestamps and refunds are
unknown, not zero. No event here claims a successful agent tool call.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class BusinessFact:
    key: str
    organization_id: str
    target: str
    at: datetime
    source: str
    price: Decimal | None = None
    currency: str | None = None


OBSERVED_TARGETS = frozenset({"activated", "key_issued", "first_lease", "first_mask"})


def invoice_facts(rows, *, now):
    """First paid invoice + independently recorded repeated payments.

    Rows may arrive in any order. A missing date on ANY paid invoice makes
    first-payment classification ambiguous for that organisation; do not pick
    a more recent invoice merely because its timestamp happens to exist.
    A zero total is not a money-received conversion.
    """
    organisations = {}
    issues = []
    unique = set()
    for row in rows:
        if row["state"] != "paid":
            continue
        identity = str(row["id"])
        if identity in unique:
            continue
        unique.add(identity)
        org = str(row["organization_id"])
        organisations.setdefault(org, []).append(row)
    facts = []
    for org, paid in organisations.items():
        # Billing legitimately settles zero invoices (free / annual-covered
        # periods). They are not money received and do not corrupt the order
        # of real payments, even if they precede the first positive invoice.
        monetary = []
        for row in paid:
            try:
                value = Decimal(str(row["total"]))
                known_zero = value.is_finite() and value == 0
            except (InvalidOperation, TypeError, ValueError):
                known_zero = False
            if not known_zero:
                monetary.append(row)
        paid = monetary
        if any(row.get("paid_at") is None for row in paid):
            issues.append({"organization_id": org, "reason": "paid_timestamp_missing"})
            continue
        accepted = []
        for row in paid:
            at = row["paid_at"]
            if at.tzinfo is None or at.utcoffset() is None or at >= now:
                issues.append({"organization_id": org, "reason": "payment_time_invalid"})
                continue
            try:
                amount = Decimal(str(row["total"]))
            except (InvalidOperation, TypeError, ValueError):
                amount = Decimal("NaN")
            if (not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99")
                    or amount != amount.quantize(Decimal("0.01"))):
                issues.append({"organization_id": org, "reason": "payment_amount_invalid"})
                continue
            accepted.append((row, amount))
        # If chronology contains malformed evidence, the first genuine paid
        # invoice is unknown; avoid labelling another one an acquisition win.
        if len(accepted) != len(paid):
            continue
        accepted.sort(key=lambda pair: (pair[0]["paid_at"], int(pair[0]["id"])))
        for index, (row, amount) in enumerate(accepted):
            target = "paid" if index == 0 else "repeat_payment"
            facts.append(BusinessFact(
                key=f"invoice:{row['id']}:{target}", organization_id=org,
                target=target, at=row["paid_at"], source="paid_invoice",
                price=amount, currency="RUB"))
            # A tariff switch, overage invoice and ordinary renewal are not
            # interchangeable. Further renewal classification requires its own
            # persisted cause, not a guess from every second payment.
            if row.get("service_resumed_at") is None:
                issues.append({"organization_id": org, "reason": "paid_service_pending"})
    return facts, issues


def observed_facts(rows, *, now):
    """First recorded occurrence per org/target; hourly facts stay observations."""
    first = {}
    for row in rows:
        target, org, at = row["step"], str(row["organization_id"]), row["at"]
        if not org or target not in OBSERVED_TARGETS:
            continue
        if at.tzinfo is None or at.utcoffset() is None or at >= now:
            continue
        key = (org, target)
        if key not in first or (at, row["id"]) < (first[key]["at"], first[key]["id"]):
            first[key] = row
    return [BusinessFact(key=f"funnel:{row['id']}:{target}",
                         organization_id=org, target=target, at=row["at"],
                         source="hourly_observation" if target.startswith("first_") else "server_event")
            for (org, target), row in first.items()]


def current_facts(*, organization_ids, now):
    """Bounded caller-selected cohort; never read customer content or keys."""
    from billing.models import Invoice
    from ops.analytics_models import Funnel
    ids = tuple(organization_ids)
    if not ids:
        return [], []
    invoices = Invoice.objects.filter(organization_id__in=ids, state=Invoice.PAID).values(
        "id", "organization_id", "state", "paid_at", "total", "service_resumed_at")
    paid, issues = invoice_facts(invoices, now=now)
    rows = Funnel.objects.filter(organization_id__in=ids, step__in=OBSERVED_TARGETS).values(
        "id", "organization_id", "step", "at")
    return sorted(paid + observed_facts(rows, now=now), key=lambda fact: (fact.at, fact.key)), issues
