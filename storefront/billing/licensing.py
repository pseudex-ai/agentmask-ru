"""Connector to the licensing server's admin API.

WHY OVER HTTP AND NOT BY IMPORTING `licensing/`.

The licensing server is a separate deployment with its own database, and it is
the SOURCE OF TRUTH for whether a key may lease. The storefront is the reason a
status changes — someone paid, or did not — but it is not a second place where
that status lives. Two stores for one kill switch drift, and the two ways they
drift are both bad: a paying customer stopped, or an unpaid one still running.

So this module states an intent ("suspend acme") and reads back the fact. It
never caches status as truth; `Subscription` keeps only what the shop needs to
render and to bill.

The admin port is never published. In production this call goes over the
internal network, which is why there is no signature scheme here — adding one
would be protecting a channel whose only other reachable endpoint is us.
"""

import httpx
from django.conf import settings


class LicensingError(RuntimeError):
    """The licensing server refused or could not be reached.

    Raised, never swallowed: every caller of this module is doing something the
    customer is watching — issuing their key, resuming their service after
    payment — and a silent failure there is a support ticket that starts with
    "I paid and nothing happened".
    """


def _post(path: str, payload: dict[str, object]) -> dict[str, object]:
    url = f"{settings.LICENSING_ADMIN_URL.rstrip('/')}{path}"
    try:
        response = httpx.post(url, json=payload, timeout=15.0,
                              verify=settings.LICENSING_CA or True)
    except httpx.HTTPError as error:
        raise LicensingError(f"{url} unreachable: {error}") from error
    if response.status_code != 200:
        raise LicensingError(
            f"{url} returned {response.status_code}: {response.text[:300]}"
        )
    return response.json()


def _get(path: str, params: dict[str, str]) -> dict[str, object]:
    url = f"{settings.LICENSING_ADMIN_URL.rstrip('/')}{path}"
    try:
        response = httpx.get(url, params=params, timeout=15.0,
                             verify=settings.LICENSING_CA or True)
    except httpx.HTTPError as error:
        raise LicensingError(f"{url} unreachable: {error}") from error
    if response.status_code != 200:
        raise LicensingError(
            f"{url} returned {response.status_code}: {response.text[:300]}"
        )
    return response.json()


def issue_key(org_id: str, plan: str) -> str:
    """Mint a key. Returned ONCE, in full — see `billing.models.LicenseKey`."""
    body = _post("/admin/issue", {"org_id": org_id, "plan": plan})
    key = str(body.get("key", ""))
    if not key:
        raise LicensingError(f"licensing server issued no key for {org_id}")
    return key


def set_status(org_id: str, status: str) -> int:
    """Move every key of an org to a status. Returns how many changed.

    `unpaid` and `revoked` are not the same lever and must not be used
    interchangeably: `unpaid` is what a missed invoice does and is reversible by
    paying, while `revoked` is for a key that should never work again. Both
    bypass grace on the client, so both stop the customer within a minute.
    """
    allowed = {"active", "unpaid", "revoked", "suspended"}
    if status not in allowed:
        raise LicensingError(f"unknown status {status!r}, expected one of {sorted(allowed)}")
    body = _post(f"/admin/{ {'active': 'resume'}.get(status, status) }",
                 {"org_id": org_id})
    return int(body.get("keys_changed", 0))


def usage(org_id: str) -> dict[str, object]:
    """Counters as the licensing server has them.

    These are what the customer's own containers reported, so they are the
    number an invoice may be based on. The storefront never counts anything
    itself — it has no way to and must not acquire one.
    """
    return _get("/admin/usage", {"org_id": org_id})
