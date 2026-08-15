"""The operator's local interface: a separate ASGI app, on its own port.

WHY A SEPARATE PROCESS AND PORT, not another router on :8000.

  * :8000 is the hot path the customer's gateway calls on every request. The UI
    must not be able to make it slower, and a page bug must not be able to take
    it down.
  * The interface has to survive the engine. "Сайдкар не отвечает" is a state the
    operator needs rendered — during a worker restart, or while the licence is
    being re-acquired — and a UI living inside the thing that is down cannot
    report that.
  * Exposure is different. A customer publishes :8000 to their own gateway;
    :8081 is for a human and should be reachable from far fewer places. Separate
    ports let them say so in one firewall rule.

AUTH: a startup token, printed with a sign-in URL, exactly like Jupyter. The
customer already has the container's log — that is the possession proof, and it
requires no account system for a product whose whole premise is that we hold
nothing about them. `VEILGATE_UI_PASSWORD` exists for a team that shares the
container and does not want to pass a log line around.

The session token is carried in the AUTHORIZATION HEADER, never a cookie. That
is not a preference: a cookie would make every state-changing call (/reveal
above all) reachable by cross-site request forgery, and defending that would
mean adding a CSRF token to protect a session mechanism chosen for convenience.
A header cannot be set by a cross-origin form at all, so the class of bug does
not exist here.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

# This process configures its OWN logging, and must: it deliberately does not
# import `veilgate.service`, which is where the sidecar's `basicConfig` lives.
# Without this line the root logger stays at WARNING with no handler, and the
# one line that matters most — the sign-in URL the customer is told to read out
# of `docker logs` — is discarded. The interface then works and is unreachable,
# which is the worst of the available failures.
logging.basicConfig(level=os.environ.get("VEILGATE_LOG_LEVEL", "INFO").upper())
_log = logging.getLogger("veilgate.localui")

# Where the page's files live. Two legitimate layouts, named explicitly rather
# than probed: next to this module in a source checkout, and at a separate path
# in the release image, where gate P1 requires that no directory called
# `veilgate` exist at all (a Nuitka build has no package tree, and P1 asserts
# that as evidence the source did not ship). The Dockerfile sets the variable;
# nothing guesses.
_STATIC = os.environ.get("VEILGATE_UI_STATIC", "") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static"
)

ENGINE_URL = os.environ.get("VEILGATE_ENGINE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.environ.get("VEILGATE_ADMIN_TOKEN", "")
# The sandbox screen calls /mask and /spans, which live on the GATEWAY surface
# and carry their own credential. The interface holds both because it is the one
# caller that legitimately spans them; the browser holds neither.
GATEWAY_TOKEN = os.environ.get("VEILGATE_GATEWAY_TOKEN", "")
UI_PASSWORD = os.environ.get("VEILGATE_UI_PASSWORD", "")
UI_ORG = os.environ.get("VEILGATE_UI_ORG", "") or os.environ.get("VEILGATE_ORG_ID", "default")

# Reusable for the life of the process, like Jupyter's. A genuinely single-use
# token would lock the operator out of their own container the moment they closed
# the tab, and the possession proof — reading this container's log — is unchanged
# by using it twice.
SIGNIN_TOKEN = os.environ.get("VEILGATE_UI_TOKEN", "") or secrets.token_urlsafe(32)

# Sessions live in memory. A restart invalidates them, which is correct: the
# process that vouched for the session is gone, and there is nothing here worth
# persisting a credential to disk for.
@dataclass(frozen=True)
class _Session:
    expires: float
    who: str


_SESSIONS: dict[str, _Session] = {}
_SESSION_TTL_SECONDS = 12 * 3600

# FAILED sign-ins, per source address. Both halves matter and both were wrong:
# one global counter meant an attacker at 0.17 req/s locked the operator out
# permanently, and counting successes meant a busy operator locked themselves
# out. The moment it bites is the worst one — licence expired, masking stopped,
# and the screen that explains why is unreachable.
_FAILURES: dict[str, list[float]] = {}
_MAX_FAILURES_PER_MINUTE = 10

# Exactly what the page may ask the engine for. An allowlist, not a prefix match:
# a proxy that forwards whatever path it is handed is an open relay into the
# container's own network, and this one holds a credential the caller does not.
_GET_ALLOWED = frozenset({
    "/status", "/events", "/stats", "/stats.csv", "/reveals",
    "/subscription", "/diagnostics", "/license", "/health", "/orgs",
})
_POST_ALLOWED = frozenset({"/reveal", "/selfcheck", "/spans", "/mask"})

_INLINE_SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)


def _inline_script_hashes() -> list[str]:
    """CSP hashes for the page's own inline scripts, computed FROM THE PAGE.

    The page carries one inline script: an import map, which resolves the bare
    specifiers `preact` and `htm` so the vendored files can stay byte-identical
    to what upstream published. An import map is an inline script as far as CSP
    is concerned, and `script-src 'self'` blocks it in every browser — the
    module graph then fails to resolve and the page renders EMPTY.

    That shipped. The test asserted the CSP header string and gate L16 asserted
    HTTP 200 on the page and its assets; neither can see that nothing executed.
    A header is not evidence that a page works.

    The hash is derived here rather than pasted in, so it cannot go stale: edit
    index.html and the policy follows. A hardcoded hash would be one edit away
    from a blank screen again, and the failure is silent.
    """
    try:
        with open(os.path.join(_STATIC, "index.html"), "r", encoding="utf-8") as handle:
            page = handle.read()
    except OSError:
        return []
    return [
        "'sha256-" + base64.b64encode(
            hashlib.sha256(body.encode("utf-8")).digest()
        ).decode() + "'"
        for body in _INLINE_SCRIPT.findall(page) if body.strip()
    ]


def signin_url(port: str) -> str:
    return f"http://localhost:{port}/?token={SIGNIN_TOKEN}"


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Print how to get in.

    A lifespan rather than the deprecated `@app.on_event("startup")`, matching
    the two other apps in this repo. The URL is the ONLY way in, so it is
    printed unconditionally and on its own lines: the customer is told to run
    `docker logs veilgate` and read it, and a line buried in a request log is
    not readable that way.
    """
    # The HTTP client is created HERE, not at module scope, so its lifetime is
    # the APPLICATION's. A module-level client closed on shutdown made the app
    # single-use: start it a second time in the same process and every proxied
    # call fails with "client has been closed". One long-lived pool per running
    # app is also what keeps connections to the engine warm.
    _app.state.client = httpx.AsyncClient(timeout=30.0)
    port = os.environ.get("VEILGATE_UI_PORT", "8081")
    if not ADMIN_TOKEN:
        _log.error("VEILGATE_ADMIN_TOKEN is not set — the interface cannot talk to "
                   "the engine. entrypoint.sh sets it for the whole container.")
    _log.info("")
    _log.info("    veilgate — локальный интерфейс")
    _log.info("    %s", signin_url(port))
    if UI_PASSWORD:
        _log.info("    (или пароль из VEILGATE_UI_PASSWORD)")
    _log.info("")
    yield
    await _app.state.client.aclose()


_SCRIPT_HASHES = _inline_script_hashes()

app = FastAPI(
    title="Veilgate local UI",
    lifespan=_lifespan,
    # No interactive API docs. They publish the operator surface to anyone
    # who can reach the port, and this app is a fixed page plus a fixed
    # proxy — there is no third party writing against it.
    docs_url=None, redoc_url=None, openapi_url=None,
)


def _sweep_sessions(now: float) -> None:
    for token, session in list(_SESSIONS.items()):
        if session.expires <= now:
            del _SESSIONS[token]


def _require_session(request: Request) -> str:
    """Validate the session and return the id that identifies it in the audit.

    Returns the id rather than just passing/failing because the reveal path must
    label the access record with something the caller cannot choose.
    """
    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    now = time.time()
    _sweep_sessions(now)
    session = _SESSIONS.get(presented) if presented else None
    if session is None:
        raise HTTPException(status_code=401, detail="not signed in")
    # Name plus a session fingerprint. Not the token itself: the access log is
    # readable in the interface, and printing a live credential into a screen
    # people paste into support tickets would be its own incident.
    short = hashlib.sha256(presented.encode()).hexdigest()[:8]
    return f"ui:{session.who}:{short}" if session.who else f"ui:{short}"


@app.post("/api/signin")
async def signin(request: Request) -> JSONResponse:
    """Exchange the startup token (or the shared password) for a session."""
    now = time.time()
    # Direct peer address: this port is meant to be reached over loopback or a
    # short hop, and trusting a forwarded header would let a caller choose their
    # own bucket.
    source = request.client.host if request.client else "unknown"
    recent = [when for when in _FAILURES.get(source, []) if now - when < 60]
    _FAILURES[source] = recent
    if len(recent) >= _MAX_FAILURES_PER_MINUTE:
        return JSONResponse({"error": "too many attempts, wait a minute"},
                            status_code=429)
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"error": "expected an object"}, status_code=400)
    presented = str(body.get("secret", ""))
    # compare_digest against BOTH, and without short-circuiting between them:
    # `a or b` would leak which of the two matched through timing.
    matches_token = hmac.compare_digest(presented, SIGNIN_TOKEN)
    matches_password = bool(UI_PASSWORD) and hmac.compare_digest(presented, UI_PASSWORD)
    if not (matches_token or matches_password):
        recent.append(now)
        return JSONResponse({"error": "wrong token"}, status_code=401)
    _FAILURES.pop(source, None)
    session = secrets.token_urlsafe(32)
    # An optional name, kept in memory only, never stored and never sent
    # anywhere. It exists so the reveal log answers the question it was built
    # for: "кто обращался к персональным данным". Without it the record reads
    # `ui:a1b2c3d4e5f6`, which nothing on earth resolves to a person — the
    # session dies with the process and one token or one shared password serves
    # a whole team.
    who = str(body.get("who", "")).strip()[:40]
    _SESSIONS[session] = _Session(expires=now + _SESSION_TTL_SECONDS, who=who)
    return JSONResponse({"session": session, "org_id": UI_ORG,
                         "expires_in": _SESSION_TTL_SECONDS})


@app.post("/api/signout")
async def signout(request: Request) -> JSONResponse:
    """Drop this session. Without it a 12-hour session could not be revoked
    short of restarting the interface."""
    header = request.headers.get("authorization", "")
    _SESSIONS.pop(header[7:] if header.lower().startswith("bearer ") else "", None)
    return JSONResponse({"status": "signed out"})


@app.get("/api/whoami")
async def whoami(request: Request) -> JSONResponse:
    _require_session(request)
    return JSONResponse({
        "org_id": UI_ORG,
        "engine": ENGINE_URL,
        # Named honestly. UI_ORG is the org this interface OPENS ON, not a
        # boundary: there is one credential per container and the switcher
        # reaches every org the container has served. Returning it as though it
        # were a scope invited exactly the wrong deployment — handing one
        # tenant's admin a container that also masks for another tenant.
        "scope": "container",
    })


async def _forward(method: str, path: str, request: Request) -> Response:
    """Proxy one allowlisted call to the engine, adding the operator token.

    Engine unreachable becomes 503 with a machine-readable code rather than a
    stack trace: this is the state the status screen renders as "сайдкар не
    отвечает", so it has to be a normal answer, not an exception.
    """
    actor = _require_session(request)
    gateway = path in ("/mask", "/spans")
    headers = {"Authorization": f"Bearer {GATEWAY_TOKEN if gateway else ADMIN_TOKEN}"}
    client: httpx.AsyncClient = request.app.state.client
    try:
        if method == "GET":
            upstream = await client.get(
                f"{ENGINE_URL}{path}", params=dict(request.query_params), headers=headers
            )
        else:
            payload = await request.body()
            if path == "/reveal":
                # The actor is STAMPED HERE, replacing whatever the page sent.
                # It was passed through, which made the whole access log
                # worthless: the one field that says who disclosed a personal
                # value was chosen by the client, so an operator could write
                # someone else's name into their colleague's disclosure. The
                # only party that knows which session this is, is this process.
                try:
                    body = json.loads(payload or b"{}")
                except ValueError:
                    return JSONResponse({"error": "invalid json"}, status_code=400)
                # A list, a string or a number parses fine and then fails on
                # item assignment — a 500 with a stack trace in the log for a
                # body anyone signed in can send.
                if not isinstance(body, dict):
                    return JSONResponse({"error": "expected an object"}, status_code=400)
                body["actor"] = actor
                payload = json.dumps(body).encode()
            upstream = await client.post(
                f"{ENGINE_URL}{path}", content=payload,
                headers={**headers, "Content-Type": "application/json"},
            )
    except httpx.HTTPError as error:
        return JSONResponse(
            {"error": "engine_unreachable", "detail": str(error)}, status_code=503
        )
    media = upstream.headers.get("content-type", "application/json")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=media,
        # Carried through so "выгрузить CSV" downloads a file instead of
        # rendering the report as text in the tab.
        headers=({"Content-Disposition": upstream.headers["content-disposition"]}
                 if "content-disposition" in upstream.headers else None),
    )


@app.get("/api/engine/{path:path}")
async def engine_get(path: str, request: Request) -> Response:
    target = "/" + path
    if target not in _GET_ALLOWED:
        raise HTTPException(status_code=404, detail="not a proxied endpoint")
    return await _forward("GET", target, request)


@app.post("/api/engine/{path:path}")
async def engine_post(path: str, request: Request) -> Response:
    target = "/" + path
    if target not in _POST_ALLOWED:
        raise HTTPException(status_code=404, detail="not a proxied endpoint")
    return await _forward("POST", target, request)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    """The UI's OWN liveness, deliberately independent of the engine — this is
    what proves the "engine is down but the interface is up" state is real."""
    return JSONResponse({"status": "ok"})


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(_STATIC, "index.html"))


@app.get("/static/{path:path}")
async def static_file(path: str) -> Response:
    """Serve the bundled page. Resolved and then checked to be inside the static
    directory: `../` in a URL path is the oldest way to read a container's
    filesystem through a web server."""
    full = os.path.realpath(os.path.join(_STATIC, path))
    if not full.startswith(os.path.realpath(_STATIC) + os.sep) or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="not found")
    kind = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".woff2": "font/woff2",
        ".svg": "image/svg+xml",
    }.get(os.path.splitext(full)[1], "application/octet-stream")
    return FileResponse(full, media_type=kind)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    """A content-security policy that forbids everything the page does not do.

    `default-src 'self'` with no `unsafe-inline` is what makes the page's
    handling of customer PII safe by construction rather than by review: even if
    a preview string carrying markup reached the DOM, there is no origin from
    which a script could load and no inline script that could run.
    """
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; script-src 'self' {' '.join(_SCRIPT_HASHES)}; "
        "style-src 'self'; "
        # Style ATTRIBUTES are governed by style-src-attr, and fall back to
        # style-src when it is absent — so `style-src 'self'` alone silently
        # blocks every style="width:42%" the charts are drawn with. Allowed
        # explicitly and narrowly: attributes yes, injected <style> blocks no.
        # Nothing here builds a style string out of customer data; the only
        # dynamic parts are computed numbers.
        "style-src-attr 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "form-action 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    # The interface shows personal data. A shared proxy or the browser's back
    # button holding a rendered page of it is a copy nobody accounted for.
    response.headers["Cache-Control"] = "no-store"
    return response



