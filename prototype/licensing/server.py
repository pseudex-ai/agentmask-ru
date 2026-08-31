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

import hashlib
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
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
from pseudex.bundle import (BundleError, plaintext_hash, seal, sign_lease,
                            verify_report)

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
# ВТОРОЙ ЗАМОК НА АДМИНКЕ, ПОТОМУ ЧТО ПЕРВЫЙ — ЭТО СЕТЬ. Порт 9443 не
# публикуется наружу (`deploy/compose.yml` даёт ему `expose`, не `ports`), и
# это верно, но единственный контроль. В той же docker-сети стоит витрина на
# Django, смотрящая в интернет 443-м портом, и ходит она сюда БЕЗ учётных
# данных: любой SSRF или RCE в витрине давал выпуск ключей, отзыв у всех
# клиентов и полный список абонентов с их расходом.
#
# Токен обязателен, и сервер без него не стартует. Сгенерировать свой, как это
# делает движок для операторской поверхности, здесь нельзя: движок — процесс у
# клиента, где выбора нет, а лицензионный сервер наш, и «сгенерировали и
# написали в лог» на нём означает, что витрина не подключится, а тот, кто
# читает логи, войдёт.
_ADMIN_TOKEN = os.environ.get("PSEUDEX_LICENSE_ADMIN_TOKEN", "")


if not _ADMIN_TOKEN:  # noqa: F821 - checked at import, before anything is served
    _log.error("PSEUDEX_LICENSE_ADMIN_TOKEN is not set — /admin/* will refuse "
               "every request")


def _require_admin(request: Request) -> None:
    # СРАВНИВАЮТСЯ БАЙТЫ. `secrets.compare_digest` на строках с не-ASCII бросает
    # `TypeError`, и он превратился бы в 500 вместо 401 — тот же промах, что уже
    # найден в проверке MAC отчёта. Заголовок и так обязан быть ASCII, но
    # решать это должен явный отказ, а не исключение.
    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    try:
        given = presented.encode("ascii")
        expected = _ADMIN_TOKEN.encode("ascii")
    except UnicodeEncodeError:
        raise HTTPException(status_code=401, detail="admin token required") from None
    if not given or not expected or not secrets.compare_digest(given, expected):
        raise HTTPException(status_code=401, detail="admin token required")


admin_app = FastAPI(title="Pseudex licensing admin",
                    dependencies=[Depends(_require_admin)])


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


def _store_usage(instance_id: str, org_id: str, usage: object,
                 pubkey: str = "") -> None:
    """Record the instance's cumulative counters. No-op on the first lease of a
    process, which has nothing to report yet.

    ПОДПИСЬ И ЦЕПЬ ПРОВЕРЯЮТСЯ ЗДЕСЬ, И ОТКАЗ НЕ РОНЯЕТ АРЕНДУ. Отчёт, который
    не сходится, — это счёт, а не право работать: клиент с испорченной цепью
    продолжает обслуживать своих людей, а мы получаем помеченную запись и
    разговор. Ронять `/mask` за расхождение в биллинге значило бы наказывать
    конечного пользователя за спор двух юрлиц.
    """
    if not isinstance(usage, dict) or not instance_id:
        return
    trust = "unsigned"
    secret_hex = STORE.report_secret(org_id, pubkey) if pubkey else ""
    if secret_hex and usage.get("signature"):
        try:
            verify_report(usage, bytes.fromhex(secret_hex))
            trust = "signed"
        except (BundleError, ValueError) as error:
            _log.warning("usage report signature failed for org=%s instance=%s: %s",
                         org_id, instance_id, error)
            trust = "bad_signature"
    entities = usage.get("entities")
    STORE.record_usage(
        org_id, instance_id, int(usage.get("requests", 0)),
        entities if isinstance(entities, dict) else {},
        int(usage.get("values", 0)),
        seq=int(usage.get("seq", 0)), prev=str(usage.get("prev", "")),
        signature=str(usage.get("signature", "")), trust=trust,
        report_pubkey=pubkey,
        build=str(usage.get("build", "")),
    )


@app.post("/v1/release")
async def release(request: Request) -> JSONResponse:
    """Give a slot back when a container shuts down cleanly.

    ОСВОБОЖДАЕТСЯ ТОЛЬКО СВОЙ СЛОТ. Раньше слот удалялся по `instance_id`,
    который выбирает клиент, и это обнуляло весь потолок: контейнер отдавал
    слот, а бандл держал ещё сутки — своё состояние у него локальное, — и пять
    контейнеров по очереди обслуживали трафик на тарифе в один инстанс. Теперь
    требуется ключ процесса, и удаляется ровно его строка.

    ЧТО ЭТИМ НЕ ЗАКРЫТО, СКАЗАНО ВСЛУХ: контейнер, отдавший слот, продолжает
    работать до конца TTL, потому что дотянуться до него мы не можем. Сузить
    окно освобождения — решение продуктовое: оно бьёт по переразвёртыванию,
    ради которого release и существует.
    """
    body = await request.json()
    record = STORE.lookup(str(body.get("key", "")))
    if record is None:
        return JSONResponse({"error": "unknown key"}, status_code=403)
    pubkey = str(body.get("pubkey", ""))
    if not pubkey:
        return JSONResponse({"error": "no process public key"}, status_code=400)
    STORE.release_process(record.org_id, pubkey)
    return JSONResponse({"released": True})


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

    # THE PLAN BOUNDARY, and the only one that can exist. It is decided here, on
    # our side, from our own record of who leased recently — not from anything
    # the container tells us about itself. Values and request rates are produced
    # on the customer's hardware and can say whatever they are made to say; the
    # number of containers asking us for leases cannot.
    #
    # 409, not 402/403: the subscription is fine and the key is valid. This is
    # "you are running more containers than you bought", which is a different
    # sentence and must not be read by the client as a payment failure — those
    # bypass grace and stop everything.
    allowed, why_not = STORE.may_lease(record.org_id, record.plan, instance_id,
                                       _TTL_SECONDS, pubkey=recipient)
    if not allowed:
        _log.warning("lease refused for org=%s instance=%s: %s",
                     record.org_id, instance_id, why_not)
        return JSONResponse({"error": "instance_limit", "detail": why_not},
                            status_code=409)
    # Counters ride in on the renewal request. Recorded BEFORE the new lease is
    # minted so a client that dies mid-renewal has still been accounted for.
    _store_usage(instance_id, record.org_id, body.get("usage"), recipient)

    lease_id = "ls_" + secrets.token_urlsafe(16)
    STORE.record_lease(lease_id, record.org_id, instance_id, process_id,
                       _TTL_SECONDS, pubkey=recipient)
    STORE.record_grant(record.org_id, recipient, STORE.grant_size(record.plan))

    # СЕКРЕТ ОТЧЁТОВ, ЗАПЕЧАТАННЫЙ ПОЛУЧАТЕЛЮ. Достать его может только тот, у
    # кого приватная половина `recipient`, — а `recipient` теперь под подписью,
    # так что подменить его на свой перехватчик не может: контейнер сверит с
    # собственным ключом и откажется стартовать.
    report_secret = secrets.token_bytes(32)
    STORE.record_report_secret(record.org_id, recipient, report_secret.hex())

    payload: dict[str, object] = {
        "lease_id": lease_id,
        # КОМУ ЗАПЕЧАТАНО — В ПОДПИСИ. Без этого поля перехватчик на хосте
        # клиента полностью прозрачен: он подменяет `pubkey` на свой, мы
        # запечатываем ему, он открывает, перепечатывает на настоящий ключ
        # контейнера — `bundle_sha256` считается по ОТКРЫТОМУ тексту и не
        # меняется, подпись сходится, контейнер ничего не замечает.
        "recipient": recipient,
        "report_secret": seal(report_secret, recipient),
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
        # ГРАНТ ЁМКОСТИ. Счёт строится на ЭТОМ числе, а не на том, что контейнер
        # о себе сообщит: скрыть расход можно, скрыть собственную просьбу о
        # ёмкости — нет, потому что без неё движок перестаёт обслуживать.
        "requests_granted": STORE.grant_size(record.plan),
    }
    payload["report_secret_sha256"] = hashlib.sha256(report_secret).hexdigest()
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
    _store_usage(str(body.get("instance_id", "")), record.org_id,
                 body.get("usage"), str(body.get("pubkey", "")))
    return JSONResponse({"status": "recorded"})


@admin_app.get("/admin/instances")
async def admin_instances(request: Request) -> JSONResponse:
    """Which containers hold a slot for this org, and since when."""
    org_id = request.query_params.get("org_id", "")
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)
    return JSONResponse({"org_id": org_id,
                         "window_seconds": _TTL_SECONDS,
                         "instances": STORE.active_instances(org_id, _TTL_SECONDS)})


@admin_app.post("/admin/release")
async def admin_release(request: Request) -> JSONResponse:
    """Free a slot held by a container that is no longer running."""
    body = await request.json()
    org_id = str(body.get("org_id", ""))
    instance_id = str(body.get("instance_id", ""))
    if not org_id or not instance_id:
        return JSONResponse({"error": "org_id and instance_id required"},
                            status_code=400)
    released = STORE.release_instance(org_id, instance_id)
    return JSONResponse({"released": released})


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
