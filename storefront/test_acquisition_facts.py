"""Standalone pure evidence tests; no DB, network, licensing or money writes."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from ops.acquisition_catalog import EVENTS, BY_ID
from ops.acquisition_facts import invoice_facts, observed_facts


def main():
    now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    def invoice(pk, org="a", **overrides):
        return dict({"id": pk, "organization_id": org, "state": "paid",
                     "paid_at": now - timedelta(hours=4-pk), "total": "3900.00",
                     "service_resumed_at": now-timedelta(minutes=1)}, **overrides)
    first, second = invoice(1), invoice(2)
    facts, issues = invoice_facts([second, first, first], now=now)
    assert [(f.target, f.key) for f in facts] == [("paid", "invoice:1:paid"), ("repeat_payment", "invoice:2:repeat_payment")]
    assert not issues and facts[0].price == Decimal("3900.00")
    assert facts[0].currency == "RUB"
    assert not any(f.target == "renewal_paid" for f in facts)
    for zero in [invoice(0, total="0.00"), invoice(3, total="0.00"), invoice(4, total="0.00", paid_at=None)]:
        with_zero, problems = invoice_facts([zero, second, first], now=now)
        assert with_zero == facts and not problems
    assert invoice_facts([invoice(1, total="0.00")], now=now) == ([], [])
    facts, issues = invoice_facts([first, invoice(2, paid_at=None)], now=now)
    assert not facts and issues[0]["reason"] == "paid_timestamp_missing"
    for amount in ["NaN", "Infinity", "-1", "1.001", "1e9000", "email@example.invalid", None]:
        facts, issues = invoice_facts([invoice(1, total=amount)], now=now)
        assert not facts and issues[0]["reason"] == "payment_amount_invalid", amount
    for at in [now, now+timedelta(hours=1), now.replace(tzinfo=None)]:
        facts, issues = invoice_facts([invoice(1, paid_at=at)], now=now)
        assert not facts and issues[0]["reason"] == "payment_time_invalid"
    facts, issues = invoice_facts([invoice(1, service_resumed_at=None)], now=now)
    assert len(facts) == 1 and issues[0]["reason"] == "paid_service_pending"
    assert not invoice_facts([invoice(1, state="issued")], now=now)[0]
    paid, _ = invoice_facts([first], now=now)
    observed = observed_facts([
        {"id": 11, "organization_id": "a", "step": "key_issued", "at": now-timedelta(hours=1)},
        {"id": 12, "organization_id": "a", "step": "key_issued", "at": now-timedelta(minutes=1)},
        {"id": 13, "organization_id": "a", "step": "first_mask", "at": now-timedelta(minutes=1)},
        {"id": 14, "organization_id": "a", "step": "paid", "at": now-timedelta(hours=6)},
    ], now=now)
    assert len(observed) == 2 and observed[0].key == "funnel:11:key_issued"
    assert paid[0].at < observed[0].at  # Paid-first doesn't require masking.
    assert observed[1].source == "hourly_observation"
    assert not any(f.target == "successful_agent_loop" for f in observed)
    assert len(BY_ID) == len(EVENTS)
    assert all(e.source == "public_browser" for e in EVENTS if e.external_default)
    assert BY_ID["paid"].repetition == "organisation"
    assert BY_ID["repeat_payment"].repetition == "invoice"
    assert set(asdict(paid[0])) == {"key", "organization_id", "target", "at", "source", "price", "currency"}
    print("PASS acquisition facts: real invoice money/time, paid-first, dedup, unknown evidence, observed != successful loop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
