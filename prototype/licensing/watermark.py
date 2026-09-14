"""Per-customer watermark for the leased bundle.

A leaked tuning copy — lifted from one customer's RAM while it ran (a residual we
cannot close against root, see docs/tz-tuning-in-lease.md) — carries a mark that
names WHOSE lease delivered it. It does not PREVENT the leak; it makes an
un-scrubbed one attributable, turning "someone leaked it" into "this org did".

The mark is `HMAC-SHA256(secret, org_id)`, truncated to 16 hex chars:
  * per-org and DETERMINISTIC, so a dump maps to exactly one org and renewals do
    not churn it;
  * not reversible without the secret, and the secret lives only on the licensing
    server (`PSEUDEX_WATERMARK_SECRET`), never in the customer's image;
  * `identify()` maps a found mark back to an org by re-deriving it for each known
    org — the server has the org list, the attacker does not have the secret.

Honest limit: a sophisticated leaker with root can see the `_wm` field and strip
it before redistributing. This is deterrence and attribution for the common case,
not a cryptographic binding. A subtler, harder-to-scrub watermark (perturbing
benign tuning data per org) is a possible future step.
"""
import hashlib
import hmac
import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _secret() -> bytes:
    """The server-side watermark secret. Empty when unset — watermarking is then
    OFF (the server still leases, just without attribution), never a crash."""
    return os.environ.get("PSEUDEX_WATERMARK_SECRET", "").encode("utf-8")


def watermark_for(org_id: str) -> str:
    """The 16-hex watermark for one org, or "" when no secret is configured."""
    secret = _secret()
    if not secret:
        return ""
    return hmac.new(secret, org_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def identify(mark: str, orgs: "list[str] | tuple[str, ...]") -> "str | None":
    """Which of `orgs` a found watermark belongs to, or None. The server holds the
    org list; re-deriving the mark for each is how a dump is attributed."""
    if not mark or not _secret():
        return None
    for org in orgs:
        if hmac.compare_digest(watermark_for(org), mark):
            return org
    return None
