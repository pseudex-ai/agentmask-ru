"""The licensing server — the only Pseudex component that runs on our hardware.

It answers exactly one question for a running sidecar: "may this process have a
detection bundle, and here it is, sealed to that process". No personal data ever
reaches it; the traffic is a key, a public key, and aggregate counters.

TWO APPS, TWO PORTS, ON PURPOSE:
  * the public app (`app`) serves customers and exposes only /v1/lease + /v1/usage
  * the admin app (`admin_app`) issues and revokes keys and is never published

Splitting them at the ASGI level rather than by a path prefix means a
misconfigured reverse proxy cannot accidentally expose key issuance: the admin
routes are not mounted in the public app at all.
"""

import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from licensing.keys import encode_public, load_signing_key
from licensing.pack import build_plaintext
from licensing.store import (
    STATUS_ACTIVE,
    STATUS_REVOKED,
    STATUS_SUSPENDED,
    STATUS_UNPAID,
    LicenseStore,
)
from pseudex.bundle import plaintext_hash, seal, sign_lease

_log = logging.getLogger("licensing.server")

_DB = os.environ.get("PSEUDEX_LICENSE_DB", "license.db")
_TTL_SECONDS = int(os.environ.get("PSEUDEX_LEASE_TTL_SECONDS", "86400"))
_GRACE_SECONDS = int(os.environ.get("PSEUDEX_GRACE_SECONDS", "172800"))
_MIN_ENGINE = os.environ.get("PSEUDEX_MIN_ENGINE_VERSION", "")

# Fault injection for the e2e stand (gate L13). It exists in the REAL server,
# not in a test double, because the gates forbid a separate server
# implementation — a stand that runs different code proves nothing about the code
# that ships. Off unless explicitly set, and it announces itself at startup so an
# instance can never be in this mode unnoticed.
_FAULT = os.environ.get("PSEUDEX_FAULT_INJECT", "")

# Gate L12 has to check the ACTUAL WIRE, not our intentions: it greps what the
# sidecar really sent for every value of the test payload. That needs the raw
# body in the log. Off by default and announced at startup — a production
# instance logging customer request bodies would be its own problem, even though
# these bodies are only counters.
_LOG_RAW_BODY = os.environ.get("PSEUDEX_LOG_RAW_BODY", "") == "1"

STORE = LicenseStore(_DB)
SIGNING_KEY = load_signing_key()
PUBLIC_KEY = encode_public(SIGNING_KEY.public_key())

# Built once: the bundle is the same for every customer, and the per-process part
# is the sealing, not the contents.
_PLAINTEXT = build_plaintext()
_PLAINTEXT_HASH = plaintext_hash(_PLAINTEXT)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Announce what this instance is. A lifespan rather than the deprecated
    `@app.on_event("startup")` — the same replacement this change already made in
    `pseudex/proxy.py`, and the modes announced below are exactly the ones nobody
    should ever discover by surprise."""
    _log.info("licensing server up: bundle=%s ttl=%ss grace=%ss pubkey=%s",
              _PLAINTEXT_HASH[:12], _TTL_SECONDS, _GRACE_SECONDS, PUBLIC_KEY)
    if _FAULT:
        _log.warning("FAULT INJECTION ACTIVE (%s) — this server is deliberately "
                     "returning broken leases. Never run this in production.", _FAULT)
    if _LOG_RAW_BODY:
        _log.warning("RAW BODY LOGGING ACTIVE — lease request bodies go to the log.")
    yield


_STATUS_RESPONSE = {
    STATUS_UNPAID: (402, "license_unpaid", "subscription is not paid"),
    STATUS_REVOKED: (403, "license_revoked", "key has been revoked"),
    STATUS_SUSPENDED: (403, "license_revoked", "key is suspended"),
}


app = FastAPI(title="Pseudex licensing", lifespan=_lifespan)
admin_app = FastAPI(title="Pseudex licensing admin")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "bundle": _PLAINTEXT_HASH[:12]}


@app.get("/v1/pubkey")
async def pubkey() -> dict[str, str]:
    """The verification key, so a customer can pin what their binary already has
    compiled in. Public by design — it verifies, it does not sign."""
    return {"public_key": PUBLIC_KEY}


def _version_tuple(version: str) -> tuple[int, ...]:
    """Compare versions numerically, not as strings.

    String order gets this backwards exactly where it matters: "1.10.0" sorts
    BELOW "1.9.0", so the first double-digit minor release would be told it is
    too old and every customer running it would be pushed into grace."""
    parts = []
    for chunk in version.split("."):
        digits = "".join(character for character in chunk if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _store_usage(instance_id: str, org_id: str, usage: object) -> None:
    """Record the instance's cumulative counters. No-op on the first lease of a
    process, which has nothing to report yet."""
    if not isinstance(usage, dict) or not instance_id:
        return
    entities = usage.get("entities")
    STORE.record_usage(
        org_id, instance_id, int(usage.get("requests", 0)),
        entities if isinstance(entities, dict) else {},
    )


@app.post("/v1/lease")
async def lease(request: Request) -> JSONResponse:
    raw = await request.body()
    if _LOG_RAW_BODY:
        _log.info("RAW_LEASE_BODY %s", raw.decode("utf-8", "replace"))
    body = json.loads(raw)
    key = body.get("key")
    if not isinstance(key, str) or not key:
        return JSONResponse({"error": "license_missing", "detail": "no key presented"},
                            status_code=401)
    record = STORE.lookup(key)
    if record is None:
        return JSONResponse({"error": "license_invalid", "detail": "unknown key"},
                            status_code=403)
    if record.status != STATUS_ACTIVE:
        # `.get` with a REFUSING default, not `[...]`. A status outside the three
        # known values — a stray space, a hand-repaired row, a value added later —
        # raised KeyError, which FastAPI turns into a 500. The client counts 500
        # as OUR outage and grants the full 48 h grace, so a key in a broken state
        # kept working for two days: the kill switch failing OPEN, which is the
        # one direction it must never fail.
        status_code, error, detail = _STATUS_RESPONSE.get(
            record.status,
            (403, "license_invalid", f"key is in an unusable state ({record.status!r})"),
        )
        return JSONResponse({"error": error, "detail": detail}, status_code=status_code)

    engine_version = str(body.get("engine_version", ""))
    if _MIN_ENGINE and _version_tuple(engine_version) < _version_tuple(_MIN_ENGINE):
        return JSONResponse(
            {"error": "engine_incompatible",
             "detail": f"engine {engine_version} is below the required {_MIN_ENGINE}"},
            status_code=409,
        )

    recipient = body.get("pubkey")
    if not isinstance(recipient, str) or not recipient:
        return JSONResponse({"error": "license_invalid", "detail": "no process public key"},
                            status_code=400)

    instance_id = str(body.get("instance_id", ""))
    process_id = str(body.get("process_id", ""))
    # Counters ride in on the renewal request. Recorded BEFORE the new lease is
    # minted so a client that dies mid-renewal has still been accounted for.
    _store_usage(instance_id, record.org_id, body.get("usage"))

    lease_id = "ls_" + secrets.token_urlsafe(16)
    STORE.record_lease(lease_id, record.org_id, instance_id, process_id, _TTL_SECONDS)

    payload: dict[str, object] = {
        "lease_id": lease_id,
        "org_id": record.org_id,
        "plan": record.plan,
        "issued_at": int(time.time()),
        "ttl_seconds": _TTL_SECONDS,
        "grace_seconds": _GRACE_SECONDS,
        # A third of the TTL: two consecutive renewals may fail before the lease
        # is even stale, so a brief outage on our side is invisible to the client.
        "renew_after_seconds": max(1, _TTL_SECONDS // 3),
        "bundle_version": _PLAINTEXT_HASH[:16],
        "bundle_sha256": _PLAINTEXT_HASH,
    }
    payload["signature"] = sign_lease(payload, SIGNING_KEY)

    sealed = seal(_PLAINTEXT, recipient)
    if _FAULT == "corrupt_bundle":
        # Flip one byte in the middle of the ciphertext. age is authenticated, so
        # this must surface as a decryption failure, not as garbled assets.
        middle = len(sealed) // 2
        sealed = sealed[:middle] + ("A" if sealed[middle] != "A" else "B") + sealed[middle + 1:]
    payload["bundle"] = sealed
    return JSONResponse(payload)


@app.post("/v1/usage")
async def usage(request: Request) -> JSONResponse:
    """Out-of-band counter delivery. Normally counters ride on /v1/lease; this
    exists for a client that wants to report before its renewal is due."""
    body = await request.json()
    key = body.get("key")
    if not isinstance(key, str):
        return JSONResponse({"error": "license_missing"}, status_code=401)
    record = STORE.lookup(key)
    if record is None or record.status != STATUS_ACTIVE:
        return JSONResponse({"error": "license_invalid"}, status_code=403)
    _store_usage(str(body.get("instance_id", "")), record.org_id, body.get("usage"))
    return JSONResponse({"status": "recorded"})


@admin_app.post("/admin/issue")
async def admin_issue(request: Request) -> JSONResponse:
    body = await request.json()
    org_id = str(body.get("org_id", ""))
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)
    key = STORE.issue_key(org_id, str(body.get("plan", "standard")))
    return JSONResponse({"org_id": org_id, "key": key})


async def _set_status(request: Request, status: str) -> JSONResponse:
    body = await request.json()
    org_id = str(body.get("org_id", ""))
    changed = STORE.set_status(org_id, status)
    if changed == 0:
        return JSONResponse({"error": "unknown org_id", "org_id": org_id}, status_code=404)
    return JSONResponse({"org_id": org_id, "status": status, "keys_changed": changed})


@admin_app.post("/admin/revoke")
async def admin_revoke(request: Request) -> JSONResponse:
    return await _set_status(request, STATUS_REVOKED)


@admin_app.post("/admin/revoke_key")
async def admin_revoke_key(request: Request) -> JSONResponse:
    """Revoke a single key by its hash, without touching the organisation.

    The organisation-wide levers stop everything the customer runs; this one
    exists so "this key leaked" is not the same action as "stop this customer".
    """
    body = await request.json()
    key_hash = str(body.get("key_hash", ""))
    if not key_hash:
        return JSONResponse({"error": "key_hash required"}, status_code=400)
    changed = STORE.revoke_key_hash(key_hash)
    if changed == 0:
        return JSONResponse({"error": "unknown or already revoked key"},
                            status_code=404)
    return JSONResponse({"revoked": changed})


@admin_app.post("/admin/suspend")
async def admin_suspend(request: Request) -> JSONResponse:
    return await _set_status(request, STATUS_SUSPENDED)


@admin_app.post("/admin/unpaid")
async def admin_unpaid(request: Request) -> JSONResponse:
    return await _set_status(request, STATUS_UNPAID)


@admin_app.post("/admin/resume")
async def admin_resume(request: Request) -> JSONResponse:
    return await _set_status(request, STATUS_ACTIVE)


@admin_app.get("/admin/list")
async def admin_list() -> JSONResponse:
    return JSONResponse({"orgs": STORE.list_orgs()})


@admin_app.get("/admin/usage")
async def admin_usage(request: Request) -> JSONResponse:
    org_id = request.query_params.get("org_id", "")
    return JSONResponse({
        "usage": STORE.usage_totals(org_id),
        "instances": STORE.instances(org_id),
    })
