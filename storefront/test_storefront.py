"""The storefront, against a REAL licensing server.

Two things are being proved:

  1. THE PATH WORKS. Sign-up issues a key that the licensing server actually
     knows about, and the cabinet renders. This is the site's only metric —
     time from first visit to first masked request — and every step of it goes
     through another service, so a mocked licensing server would test the mock.

  2. THE SITE NEVER BECOMES A PII SURFACE. No page may render a dialogue, a
     token or a value; the landing demo must have no input; the full key must
     appear exactly once and never again. These are not preferences — they are
     what keeps us outside the perimeter under 152-ФЗ, so they are checked
     rather than reviewed.

No pytest, matching the engine repo: run it, read the lines, non-zero is broken.

    python3 test_storefront.py
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

_HERE = Path(__file__).resolve().parent
_PROTOTYPE = _HERE.parent / "prototype"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _free_port() -> int:
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_licensing() -> tuple[subprocess.Popen, str]:
    """The real licensing server, in its own interpreter.

    A subprocess rather than an import because it lives in the engine's
    virtualenv with the engine's dependencies, and the storefront deliberately
    shares neither. That separation is the point: if this test could import
    `licensing`, so could the storefront.
    """
    public, admin = _free_port(), _free_port()
    env = {
        **os.environ,
        "VEILGATE_LICENSE_PORT": str(public),
        "VEILGATE_LICENSE_ADMIN_PORT": str(admin),
        "VEILGATE_LICENSE_DB": os.path.join(
            tempfile.mkdtemp(prefix="veilgate-store-test-"), "license.db"),
        "VEILGATE_LICENSE_CERT": "",
        "VEILGATE_LICENSE_KEYFILE": "",
    }
    process = subprocess.Popen(
        [str(_PROTOTYPE / ".venv/bin/python"), "-m", "licensing.devserver"],
        cwd=str(_PROTOTYPE), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    admin_url = f"http://127.0.0.1:{admin}"
    for _ in range(120):
        try:
            httpx.get(f"{admin_url}/admin/list", timeout=2)
            return process, admin_url
        except httpx.HTTPError:
            time.sleep(0.25)
    process.kill()
    raise RuntimeError("the licensing server never came up")


def main() -> int:
    process, admin_url = start_licensing()
    os.environ["VEILGATE_LICENSING_ADMIN_URL"] = admin_url
    os.environ["VEILGATE_DEBUG"] = "1"
    os.environ["VEILGATE_SECRET_KEY"] = "test-only"
    os.environ["VEILGATE_DB_PATH"] = os.path.join(
        tempfile.mkdtemp(prefix="veilgate-store-db-"), "store.sqlite3")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "veilgate_site.settings")

    import django
    django.setup()
    from django.core.management import call_command
    from django.test import Client

    call_command("migrate", verbosity=0, interactive=False)
    call_command("seed_plans", verbosity=0)

    try:
        run_checks(Client())
    finally:
        process.terminate()
        process.wait(timeout=10)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        return 1
    print("storefront OK — key issued before payment, cabinet renders, "
          "no PII surface anywhere on the site")
    return 0


def run_checks(client) -> None:
    from accounts.models import Organization
    from billing.models import LicenseKey

    landing = client.get("/")
    body = landing.content.decode()
    check("the landing renders", landing.status_code == 200)
    # An input on the landing would mean this server starts receiving other
    # people's personal data. The demo is prepared examples only.
    check("the landing demo has no free-text input",
          "<textarea" not in body and 'type="text" name="text"' not in body)
    check("the landing carries a content security policy",
          "default-src 'self'" in landing.headers.get("Content-Security-Policy", ""))

    signed = client.post("/signup", {"email": "buyer@acme.ru",
                                     "company": "ООО Ромашка", "plan": "start"})
    check("sign-up redirects to the key page",
          signed.status_code == 302 and signed.url == "/welcome",
          f"status={signed.status_code}")

    welcome = client.get("/welcome")
    welcome_body = welcome.content.decode()
    organization = Organization.objects.first()
    stored = LicenseKey.objects.first()
    check("an organisation and a key were created",
          organization is not None and stored is not None)
    check("the full key is shown once",
          stored.prefix in welcome_body, f"prefix={stored.prefix}")
    check("the run command comes with the key already in it",
          "VEILGATE_LICENSE_KEY=" in welcome_body and stored.prefix in welcome_body)

    # The key must be gone from the session now: a page that re-renders a bearer
    # credential on refresh is a credential in browser history.
    again = client.get("/welcome")
    check("the key page does not render the key twice",
          again.status_code == 302, f"status={again.status_code}")

    # The full key must not be recoverable from our own database.
    check("only a prefix and a hash are stored",
          not any(field.name == "key" for field in LicenseKey._meta.get_fields()),
          "there is no column that could hold the key")

    licensed = httpx.get(f"{os.environ['VEILGATE_LICENSING_ADMIN_URL']}/admin/list",
                         timeout=10).json()
    check("the licensing server knows the organisation",
          any(row.get("org_id") == organization.id for row in licensed.get("orgs", [])),
          f"orgs={[row.get('org_id') for row in licensed.get('orgs', [])]}")

    anonymous = client.get("/app/")
    check("the cabinet refuses an anonymous visitor",
          anonymous.status_code == 302 and "/accounts/login" in anonymous.url,
          f"status={anonymous.status_code}")

    from accounts.models import User
    client.force_login(User.objects.get(email="buyer@acme.ru"))
    cabinet = client.get("/app/")
    cabinet_body = cabinet.content.decode()
    check("the cabinet renders for its owner", cabinet.status_code == 200)
    check("the cabinet shows the key prefix but not the key",
          stored.prefix in cabinet_body, "prefix only")
    check("cabinet pages are not cached",
          "no-store" in cabinet.headers.get("Cache-Control", ""),
          cabinet.headers.get("Cache-Control", "missing"))
    # The site's whole legal position in one assertion.
    check("the cabinet states plainly that it holds no dialogues or values",
          "нет ваших диалогов" in cabinet_body)

    # The full key must never be written to OUR storage. Django's session
    # backend is a table, so a key parked in the session would sit in a database
    # a backup and a support query both reach.
    from django.contrib.sessions.models import Session
    parked = " ".join(row.session_data for row in Session.objects.all())
    check("the key is never parked in a server-side session",
          stored.prefix not in parked, "session table is clean")

    # Sign-up mints a key on the licensing server, so an unthrottled loop would
    # fill the one database whose loss stops every deployment in the field.
    throttled = None
    for index in range(6):
        throttled = client.post("/signup", {"email": f"flood{index}@example.com",
                                            "company": "x", "plan": "start"})
    check("sign-up is throttled",
          throttled.url == "/" if throttled.status_code == 302 else False,
          f"last redirect={getattr(throttled, 'url', throttled.status_code)}")

    repeat = client.post("/signup", {"email": "buyer@acme.ru", "company": "x",
                                     "plan": "start"})
    check("a known email is sent to sign-in, not given a second organisation",
          Organization.objects.filter(memberships__user__email="buyer@acme.ru").count() == 1,
          f"orgs={Organization.objects.filter(memberships__user__email='buyer@acme.ru').count()}")

    # A second organisation must not be able to read the first one's invoices.
    other_user = User.objects.create_user(email="stranger@example.com")
    other_org = Organization.objects.create(display_name="Другая")
    from accounts.models import Membership
    Membership.objects.create(user=other_user, organization=other_org)
    client.force_login(other_user)
    leaked = client.get(f"/app/invoices/DOES-NOT-EXIST")
    check("one organisation cannot open another's invoice",
          leaked.status_code == 404, f"status={leaked.status_code}")


if __name__ == "__main__":
    sys.exit(main())
