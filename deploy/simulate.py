"""Drive the local stack as several customers would, so billing can be watched
end to end without waiting for real traffic.

WHAT THIS DOES NOT DO: it does not write counters anywhere. There is no test
hook in the product and this script does not add one — it registers through the
real sign-up form, runs real /mask calls against a real container, and then
waits for the engine to report its own counters on its next lease renewal. The
numbers that end up on an invoice got there the same way a customer's would.

That is also why it is slow in one place: the local stack leases for 5 minutes,
so counters reach the licensing server within 5 minutes of the traffic, not
instantly. `--wait` blocks until they do.

    python3 deploy/simulate.py --customers 3 --requests 40
    python3 deploy/simulate.py --customers 1 --requests 2000 --wait --invoice

Prerequisites: deploy/local.sh is up, and a veilgate container is running on
:8000 pointed at the local licensing server.
"""

import argparse
import random
import re
import sys
import time

import httpx

SITE = "http://localhost:8080"
ENGINE = "http://localhost:8000"
LICENSE_ADMIN = "http://localhost:9443"

# Synthetic people. Obviously fake, and deliberately varied in shape so the
# detector does real work: different name orders, phone formats, address forms
# and document types. Reusing one message would exercise the mask cache instead
# of the detector and produce a flattering, meaningless number.
FIRST = ["Иван", "Мария", "Пётр", "Ольга", "Сергей", "Анна", "Дмитрий", "Елена"]
LAST = ["Иванов", "Соколова", "Кузнецов", "Петрова", "Морозов", "Волкова"]
MIDDLE = ["Сергеевич", "Львовна", "Петрович", "Игоревна", "Валентинович"]
CITIES = ["Москва", "Казань", "Новосибирск", "Екатеринбург", "Самара"]
STREETS = ["Ленинский пр-т", "ул. Профсоюзная", "ул. Гагарина", "ул. Мира"]
AGENTS = ["support-bot", "order-agent", "kb-assistant", "batch-recheck"]


def message(rng: random.Random) -> str:
    name = f"{rng.choice(LAST)} {rng.choice(FIRST)} {rng.choice(MIDDLE)}"
    phone = rng.choice([
        f"+7 9{rng.randint(10, 99)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
        f"8{rng.randint(9000000000, 9999999999)}",
    ])
    address = (f"{rng.choice(CITIES)}, {rng.choice(STREETS)} {rng.randint(1, 99)}, "
               f"кв. {rng.randint(1, 300)}")
    shapes = [
        f"Здравствуйте! Меня зовут {name}, заказ №A-{rng.randint(1000, 9999)}. "
        f"Перезвоните на {phone}, доставку жду по адресу {address}.",
        f'{{"order": "A-{rng.randint(1000, 9999)}", "customer": "{name}", '
        f'"phone": "{phone}", "total": {rng.randint(1000, 90000)}}}',
        f"Курьер не нашёл вход. Адрес: {address}. Получатель {name}, телефон {phone}.",
        f"Для оформления: паспорт {rng.randint(1000, 9999)} № {rng.randint(100000, 999999)}, "
        f"ИНН {rng.randint(100000000000, 999999999999)}. Клиент {name}.",
        # No personal data at all. A request that finds nothing is still a
        # billable request, and if the counter ever stops agreeing with that,
        # this is the message that shows it.
        f"Какой статус у заказа A-{rng.randint(1000, 9999)}?",
    ]
    return rng.choice(shapes)


def register(client: httpx.Client, index: int) -> tuple[str, str]:
    """Sign up through the REAL form and read the key off the page it returns."""
    email = f"sim{index}-{int(time.time())}@example.com"
    page = client.get(SITE + "/")
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.text)
    if token is None:
        raise SystemExit("no CSRF token on the landing — is the storefront up?")
    response = client.post(
        SITE + "/signup",
        data={"csrfmiddlewaretoken": token.group(1), "email": email,
              "company": f"ООО Тест {index}", "plan": "start"},
        headers={"Referer": SITE + "/"},
        follow_redirects=True,
    )
    key = re.search(r"(vg_live_[A-Za-z0-9_\-]+)", response.text)
    if key is None:
        raise SystemExit(
            f"sign-up did not return a key for {email}. The storefront throttles "
            f"sign-ups per address; wait ten minutes or restart the stack."
        )
    org = re.search(r"(org_[0-9a-f]+)", response.text)
    return key.group(1), (org.group(1) if org else "")


def send(org: str, count: int, rng: random.Random) -> tuple[int, int]:
    ok = failed = 0
    with httpx.Client(timeout=60.0) as client:
        for index in range(count):
            body = {
                "org_id": org,
                "agent_id": rng.choice(AGENTS),
                "messages": [{"role": "user", "content": message(rng)}],
            }
            try:
                response = client.post(ENGINE + "/mask", json=body)
                ok += response.status_code == 200
                failed += response.status_code != 200
            except httpx.HTTPError:
                failed += 1
            if index and index % 50 == 0:
                print(f"    {index}/{count}…", flush=True)
    return ok, failed


def reported(org: str) -> int:
    try:
        body = httpx.get(f"{LICENSE_ADMIN}/admin/usage", params={"org_id": org},
                         timeout=10).json()
    except httpx.HTTPError:
        return -1
    usage = body.get("usage", {})
    return int(usage.get("requests", 0)) if isinstance(usage, dict) else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--customers", type=int, default=2)
    parser.add_argument("--requests", type=int, default=25)
    parser.add_argument("--wait", action="store_true",
                        help="block until the engine reports the counters upstream")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    try:
        httpx.get(ENGINE + "/health", timeout=5)
    except httpx.HTTPError:
        print("the engine is not answering on :8000 — start the container first "
              "(deploy/local.sh prints the command)")
        return 1

    accounts: list[tuple[str, str]] = []
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for index in range(args.customers):
            key, org = register(client, index)
            accounts.append((key, org))
            print(f"  customer {index + 1}: {org}  key {key[:16]}…")

    for key, org in accounts:
        print(f"  sending {args.requests} requests as {org}")
        ok, failed = send(org, args.requests, rng)
        print(f"    masked ok={ok} failed={failed}")

    if not args.wait:
        print("\ncounters reach the licensing server on the next lease renewal "
              "(5 min in the local stack). Re-run with --wait to block for it.")
        return 0

    print("\nwaiting for the engine to report its counters upstream…")
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        totals = {org: reported(org) for _key, org in accounts}
        if all(count > 0 for count in totals.values()):
            for org, count in totals.items():
                print(f"  {org}: licensing server has {count} requests")
            print("\nBilling can now be exercised: open the cabinet, or draft an "
                  "invoice from the Django shell with billing.services.build_invoice.")
            return 0
        time.sleep(15)
    print("counters never arrived. Check `docker logs veilgate` for lease renewals.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
