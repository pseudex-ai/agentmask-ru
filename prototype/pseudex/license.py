"""Client side of the lease: get the detection assets, keep them, give them up.

The engine ships empty. Everything it needs to detect personal data arrives here,
sealed to a keypair this process generated in memory and never wrote down.

WHY THE DEGRADATION LADDER LOOKS LIKE THIS

    LEASED   lease is current                      serve
    STALE    renewal failing, inside grace         serve, warn
    EXPIRED  grace exhausted, or revoked           unload assets, refuse

Grace exists so OUR outage does not stop the customer's business on a Friday
night. It is therefore granted only for failures that are plausibly ours — a
timeout, a 5xx, DNS. A 402 or 403 is not an outage, it is an answer: the
subscription ended or the key was revoked. Stretching that over 48 hours would
hand a departing customer two more days of the product, so those go straight to
EXPIRED.

WHY THE GRACE CLOCK IS `time.monotonic()`

Not to be clever about clock tampering — to make it structurally irrelevant.
Monotonic time ignores the system clock, so winding the container back does
nothing; and the only other way to reset the countdown is to restart the process,
which discards the in-memory bundle and forces a fresh lease. There is no
persisted expiry for a customer to edit, because nothing is persisted at all.

COLD START HAS NO GRACE. A process that never leased has no assets to run on, so
"degrade" is not a thing it can do. It retries a few times for the ordinary case
of a container racing its own network, then exits non-zero.
"""

import logging
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pseudex.assets import ASSETS
from pseudex.bundle import (
    BundleError,
    ProcessKey,
    decode_public_key,
    generate_process_key,
    open_sealed,
    plaintext_hash,
    verify_lease,
)

_log = logging.getLogger("pseudex.license")

ENGINE_VERSION = "1.0.0"

STATE_BOOT = "boot"
STATE_LEASED = "active"
STATE_STALE = "stale"
STATE_EXPIRED = "expired"

# Failures that are ours to own -> grace applies. Everything else is an answer.
#
# 409 (engine too old for what the server will now issue) is in here on purpose:
# the customer did nothing wrong and is paying, so the failure is ours to fix by
# shipping them an upgrade. Stopping their agents within minutes over our own
# version policy would be using the kill switch for the wrong thing — they get
# the grace window and a warning naming the required version.
_GRACE_WORTHY_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

_STARTUP_ATTEMPTS = 3
_STARTUP_BACKOFF_SECONDS = 2.0

# How often a REVOKED or UNPAID licence re-asks. Slower than a normal renewal —
# the answer is unlikely to change minute to minute — but never never: a customer
# who pays their invoice must come back without restarting every container.
_TERMINAL_RETRY_SECONDS = 60.0


class LicenseError(RuntimeError):
    """The process may not run: no valid lease could be obtained at startup."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LicenseStatus:
    state: str
    code: str | None
    lease_id: str | None
    bundle_version: str | None
    seconds_since_lease: float | None
    grace_left_seconds: float | None
    last_error: str | None


def _public_key_material() -> str:
    """Our verification key.

    A released build carries it in a generated `pseudex/_release.py`, written at
    image build time. The environment fallback exists only for an uncompiled
    development checkout, and it is deliberately NOT consulted when a release
    constant is present: if a customer could point the verification key at their
    own, they could sign their own bundles and the signature would mean nothing.
    """
    try:
        from pseudex import _release  # noqa: PLC0415  (optional, generated at build)
    except ImportError:
        material = os.environ.get("PSEUDEX_LICENSE_PUBKEY", "")
        if not material:
            raise LicenseError(
                "license_invalid",
                "no verification key: this build has no pseudex/_release.py and "
                "PSEUDEX_LICENSE_PUBKEY is unset",
            )
        _log.warning("using PSEUDEX_LICENSE_PUBKEY from the environment — "
                     "development build, not a release")
        return material
    return _release.LICENSE_PUBKEY


class LicenseClient:
    """Connector to the licensing server (external state -> class)."""

    def __init__(self, base_url: str, key: str, instance_id: str, ca_path: str,
                 usage_provider: Callable[[], dict[str, object]]) -> None:
        self._base_url = base_url.rstrip("/")
        self._key = key
        self._instance_id = instance_id
        self._process_id = f"{instance_id}-{os.getpid()}"
        self._usage_provider = usage_provider
        self._process_key: ProcessKey = generate_process_key()
        # Resolved on first use, not here: `service.py` constructs this client at
        # import time, and a missing verification key must fail the STARTUP of a
        # process, not the IMPORT of the module — otherwise every test and tool
        # that merely imports the app dies with a licensing error.
        self._verify_key: Ed25519PublicKey | None = None

        verify: object = ca_path if ca_path else True
        self._http = httpx.Client(verify=verify, timeout=15.0)

        self._lock = threading.Lock()
        self._last_ok_monotonic: float | None = None
        # When we last TRIED, as opposed to when we last succeeded. Retry pacing
        # has to key off the attempt: pacing off the last success would retry on
        # every tick once a lease has gone stale.
        self._last_attempt_monotonic: float | None = None
        self._ttl_seconds = 0
        self._grace_seconds = 0
        self._renew_after_seconds = 0
        self._lease_id: str | None = None
        self._bundle_version: str | None = None
        self._terminal_code: str | None = None
        self._last_error: str | None = None
        # A short history of renewal failures, not just the latest one. "Почему
        # встало" is rarely answered by the last error alone — a nightly connect
        # timeout that recovers on the third attempt looks identical to a hard
        # outage if you can only see one line. Bounded, so a container that has
        # been failing for a week does not accumulate a leak.
        self._errors: deque[tuple[float, str]] = deque(maxlen=20)
        # The last usage body actually PUT ON THE WIRE, so the operator's
        # subscription screen can show what left their contour verbatim instead
        # of an example from documentation. It is counters only by construction;
        # showing the real thing is what makes that checkable rather than
        # promised.
        self._last_report: dict[str, object] | None = None
        self._last_report_at: float | None = None
        self._last_warned_monotonic = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- state ---------------------------------------------------------

    def state(self) -> str:
        if self._terminal_code is not None:
            return STATE_EXPIRED
        last_ok = self._last_ok_monotonic
        if last_ok is None:
            return STATE_BOOT
        elapsed = time.monotonic() - last_ok
        if elapsed <= self._ttl_seconds:
            return STATE_LEASED
        if elapsed <= self._ttl_seconds + self._grace_seconds:
            return STATE_STALE
        return STATE_EXPIRED

    def status(self) -> LicenseStatus:
        state = self.state()
        last_ok = self._last_ok_monotonic
        elapsed = None if last_ok is None else time.monotonic() - last_ok
        grace_left = None
        if elapsed is not None and self._terminal_code is None:
            grace_left = max(0.0, self._ttl_seconds + self._grace_seconds - elapsed)
        return LicenseStatus(
            state=state,
            code=self._terminal_code,
            lease_id=self._lease_id,
            bundle_version=self._bundle_version,
            seconds_since_lease=elapsed,
            grace_left_seconds=grace_left,
            last_error=self._last_error,
        )

    def is_serving(self) -> bool:
        return self.state() in (STATE_LEASED, STATE_STALE)

    def _record_error(self, message: str) -> None:
        with self._lock:
            self._last_error = message
            self._errors.appendleft((time.time(), message))

    def recent_errors(self) -> list[dict[str, object]]:
        with self._lock:
            return [{"ts": when, "message": message} for when, message in self._errors]

    def last_report(self) -> dict[str, object]:
        """What we last sent about this instance, and when. `body` is None before
        the first renewal — the very first lease has nothing to report yet."""
        with self._lock:
            return {"body": self._last_report, "sent_at": self._last_report_at,
                    "url": f"{self._base_url}/v1/lease"}

    # --- lease ---------------------------------------------------------

    def _request_lease(self) -> dict[str, object]:
        # Cumulative instance-wide totals, restated on every renewal rather than
        # sent as deltas: a delta lost to a failed request is lost for good,
        # while a missed cumulative report is corrected by the next one.
        usage = self._usage_provider() if self._lease_id is not None else None
        if usage is not None:
            with self._lock:
                self._last_report = usage
                self._last_report_at = time.time()
        response = self._http.post(
            f"{self._base_url}/v1/lease",
            json={
                "key": self._key,
                "instance_id": self._instance_id,
                "process_id": self._process_id,
                "pubkey": self._process_key.public,
                "engine_version": ENGINE_VERSION,
                "lease_id": self._lease_id,
                "usage": usage,
            },
        )
        if response.status_code == 200:
            return response.json()
        # A body we cannot parse still has to produce a usable diagnosis, so the
        # status code and a truncated body go into the message either way.
        try:
            body = response.json()
            code = str(body.get("error", "license_invalid"))
            detail = str(body.get("detail", ""))
        except ValueError:
            code, detail = "license_invalid", response.text[:200]
        if response.status_code in _GRACE_WORTHY_STATUS:
            raise _TransientLeaseError(
                f"licensing server returned {response.status_code} "
                f"({code}: {detail}) for {self._base_url}"
            )
        raise LicenseError(code, f"{detail} (HTTP {response.status_code}, {self._base_url})")

    def _apply(self, lease: dict[str, object]) -> None:
        if self._verify_key is None:
            self._verify_key = decode_public_key(_public_key_material())
        verify_lease(lease, self._verify_key)
        plaintext = open_sealed(str(lease["bundle"]), self._process_key)
        actual = plaintext_hash(plaintext)
        expected = str(lease["bundle_sha256"])
        if actual != expected:
            raise BundleError(
                f"bundle hash mismatch: signed {expected[:16]}, got {actual[:16]} — "
                f"the contents are not what was signed"
            )
        ASSETS.load(plaintext)
        with self._lock:
            self._last_ok_monotonic = time.monotonic()
            self._ttl_seconds = int(lease["ttl_seconds"])
            self._grace_seconds = int(lease["grace_seconds"])
            self._renew_after_seconds = int(lease["renew_after_seconds"])
            self._lease_id = str(lease["lease_id"])
            self._bundle_version = str(lease["bundle_version"])
            self._last_error = None

    def acquire(self) -> None:
        """First lease. Raises `LicenseError` if the process may not run.

        The retries cover a container that starts before its network does; they
        are a bounded startup wait, not grace. An answer (402/403) is not
        retried — retrying a revocation would only delay the inevitable."""
        last_transient: Exception | None = None
        for attempt in range(1, _STARTUP_ATTEMPTS + 1):
            try:
                # Recorded even on the attempt that fails: the renewal loop paces
                # itself off the last ATTEMPT, and leaving it unset made the loop
                # fire a second, redundant lease the instant it started — one
                # extra full bundle sealed per worker on every container start.
                self._last_attempt_monotonic = time.monotonic()
                self._apply(self._request_lease())
                _log.info("lease acquired: %s bundle=%s ttl=%ss grace=%ss",
                          self._lease_id, self._bundle_version,
                          self._ttl_seconds, self._grace_seconds)
                return
            except (_TransientLeaseError, httpx.HTTPError) as error:
                last_transient = error
                _log.warning("lease attempt %d/%d failed: %s",
                             attempt, _STARTUP_ATTEMPTS, error)
                if attempt < _STARTUP_ATTEMPTS:
                    time.sleep(_STARTUP_BACKOFF_SECONDS * attempt)
            except BundleError as error:
                raise LicenseError("bundle_corrupt", str(error)) from error
        raise LicenseError(
            "bundle_unavailable",
            f"licensing server unreachable after {_STARTUP_ATTEMPTS} attempts: "
            f"{last_transient}",
        )

    def _renew(self) -> None:
        try:
            self._apply(self._request_lease())
            if self._terminal_code is not None:
                _log.info("licence restored (was %s) — resuming", self._terminal_code)
                self._terminal_code = None
            _log.info("lease renewed: %s bundle=%s", self._lease_id, self._bundle_version)
        except LicenseError as error:
            # An ANSWER, not an outage: grace does not apply.
            self._terminal_code = error.code
            self._record_error(error.detail)
            _log.error("lease terminated (%s): %s — refusing further requests",
                       error.code, error.detail)
            self._expire()
        except (_TransientLeaseError, httpx.HTTPError, BundleError) as error:
            self._record_error(str(error))
            _log.warning("lease renewal failed, running on the leased bundle: %s", error)

    def _expire(self) -> None:
        """Give up the assets. Not a flag — the data goes away."""
        if ASSETS.is_loaded:
            ASSETS.unload()
            _log.error("detection assets unloaded — /mask now returns 503")

    def _warn_interval(self) -> float:
        """Warn often enough to be visible within the grace window. 15 minutes at
        the production 48 h grace; proportionally sooner when grace is short, so a
        short-grace deployment is not silent until the moment it stops."""
        return min(900.0, max(5.0, self._grace_seconds / 8.0))

    def _tick(self) -> None:
        state = self.state()
        if state == STATE_EXPIRED:
            self._expire()
            now = time.monotonic()
            if now - self._last_warned_monotonic >= min(300.0, self._warn_interval()):
                self._last_warned_monotonic = now
                _log.error("license expired (%s): refusing to mask. last error: %s",
                           self._terminal_code or "grace exhausted", self._last_error)
            return
        if state == STATE_STALE:
            now = time.monotonic()
            if now - self._last_warned_monotonic >= self._warn_interval():
                self._last_warned_monotonic = now
                status = self.status()
                _log.warning(
                    "license STALE — renewal failing for %.0fs, %.0fs of grace left, "
                    "then masking stops. last error: %s",
                    status.seconds_since_lease or 0.0,
                    status.grace_left_seconds or 0.0, self._last_error,
                )

    def _loop(self) -> None:
        while not self._stop.is_set():
            due = self._renew_after_seconds
            if self._terminal_code is not None:
                # A revoked or unpaid licence keeps asking, just slowly. Stopping
                # forever would mean a customer who pays their invoice has to
                # restart every container to come back — the kill switch is meant
                # to stop the service NOW, not to make recovery a support ticket.
                due = max(due, _TERMINAL_RETRY_SECONDS)
            last_attempt = self._last_attempt_monotonic
            try:
                if last_attempt is None or time.monotonic() - last_attempt >= due:
                    self._last_attempt_monotonic = time.monotonic()
                    self._renew()
                self._tick()
            except Exception:  # noqa: BLE001 — see below
                # THIS THREAD MUST NOT DIE. It is the only thing that renews the
                # lease, enters STALE, and eventually unloads the assets; if it
                # stops, the worker serves on the last bundle until TTL+grace and
                # then 503s with no recorded reason — a healthy-looking process
                # that quietly stopped masking.
                #
                # A bare except is right here and nowhere else: `_renew` already
                # handles the failures it can name, so anything arriving here is
                # by definition one we did not anticipate (a truncated bundle
                # raising zlib.error, a malformed signature raising
                # binascii.Error, a store error from the usage provider). Losing
                # the loop over an unanticipated error is strictly worse than
                # logging it and trying again.
                self._record_error("unexpected error in the licence loop")
                _log.exception("unexpected error in the licence loop; continuing")
            # Wake often enough that EXPIRED is entered promptly even with no
            # traffic — the assets must go away on time, not on the next request.
            self._stop.wait(min(5.0, max(1.0, due / 4.0)))

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="pseudex-license",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._http.close()


class _TransientLeaseError(RuntimeError):
    """A failure plausibly on our side — grace applies."""
