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

# ПУТИ ЛЕЖАТ ТАБЛИЦЕЙ, А НЕ СОБИРАЮТСЯ ИЗ ЗНАЧЕНИЯ СТАТУСА.
#
# `f"/admin/{ {'active': 'resume'}.get(status, status) }"` выглядело как
# сокращение и было арифметикой по строке: `unpaid` совпадал с именем ручки
# случайно, а `revoked` и `suspended` попадали в `/admin/revoked` и
# `/admin/suspended`, которых не существует. Проверено — 404 даже под полным
# админ-токеном, то есть отзыв и приостановка из витрины не работали ни для
# кого. Валидатор строкой ниже эти два значения при этом разрешал.
#
# Таблица делает неверный путь НЕПРЕДСТАВИМЫМ, а не «проверяемым». Дублирование
# с `licensing/server.py::ADMIN_ACTIONS` сознательное и по той же причине, что у
# `PLAN_INSTANCES`: лицензионный сервер не должен зависеть от витрины. Сверяет
# их `test_storefront.py`.
ISSUE = "/admin/issue"
REVOKE_KEY = "/admin/revoke_key"
RELEASE = "/admin/release"
INSTANCES = "/admin/instances"
USAGE = "/admin/usage"
# Операторская консоль. Те же правила: путь литералом, аудитория решена на той
# стороне в `ADMIN_ACTIONS`, и разъезд роняет старт лицензионного сервера.
PLANS = "/admin/plans"
FLEET = "/admin/fleet"
CHAINS = "/admin/chains"

_STATUS_ACTION = {
    "active": "/admin/resume",
    "unpaid": "/admin/unpaid",
    "revoked": "/admin/revoke",
    "suspended": "/admin/suspend",
}


class LicensingError(RuntimeError):
    """The licensing server refused or could not be reached.

    Raised, never swallowed: every caller of this module is doing something the
    customer is watching — issuing their key, resuming their service after
    payment — and a silent failure there is a support ticket that starts with
    "I paid and nothing happened".
    """


def _auth() -> dict[str, str]:
    """Учётные данные админки. Пусто — заголовка нет, и сервер ответит 401:
    молча ходить без токена хуже, чем громко не дойти."""
    token = getattr(settings, "LICENSING_ADMIN_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _post(path: str, payload: dict[str, object]) -> dict[str, object]:
    url = f"{settings.LICENSING_ADMIN_URL.rstrip('/')}{path}"
    try:
        response = httpx.post(url, json=payload, timeout=15.0,
                              headers=_auth(),
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
                             headers=_auth(), verify=settings.LICENSING_CA or True)
    except httpx.HTTPError as error:
        raise LicensingError(f"{url} unreachable: {error}") from error
    if response.status_code != 200:
        raise LicensingError(
            f"{url} returned {response.status_code}: {response.text[:300]}"
        )
    return response.json()


def issue_key(org_id: str, plan: str) -> str:
    """Mint a key. Returned ONCE, in full — see `billing.models.LicenseKey`."""
    body = _post(ISSUE, {"org_id": org_id, "plan": plan})
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
    path = _STATUS_ACTION.get(status)
    if path is None:
        raise LicensingError(
            f"unknown status {status!r}, expected one of {sorted(_STATUS_ACTION)}")
    body = _post(path, {"org_id": org_id})
    return int(body.get("keys_changed", 0))


def revoke_key(key_hash: str) -> None:
    """Revoke ONE key on the licensing server.

    Without this the cabinet's revoke button was a local flag and a success
    message: the key kept leasing, so an engineer who left with a copy kept a
    working credential for the customer's whole gateway.
    """
    _post(REVOKE_KEY, {"key_hash": key_hash})


def usage(org_id: str) -> dict[str, object]:
    """Counters as the licensing server has them.

    These are what the customer's own containers reported, so they are the
    number an invoice may be based on. The storefront never counts anything
    itself — it has no way to and must not acquire one.
    """
    return _get(USAGE, {"org_id": org_id})


def instances(org_id: str) -> dict[str, object]:
    """Which containers hold a slot right now, and since when.

    The plan is sold in containers and the limit is enforced on them, but the
    cabinet had nowhere to show them: a persona whose only slot was held by a
    container they had already deleted read «остановите лишний контейнер или
    перейдите на больший тариф» — asked to stop something that did not exist,
    and offered a bigger plan as the remedy.
    """
    return _get(INSTANCES, {"org_id": org_id})


def release_instance(org_id: str, instance_id: str) -> bool:
    """Give a slot back before its window expires.

    A customer who recreated a volume is a NEW instance by construction, and in
    production the window is a day — so without this they wait a day to run the
    product they pay for.
    """
    result = _post(RELEASE, {"org_id": org_id, "instance_id": instance_id})
    return bool(result.get("released"))


def plans() -> list[dict[str, object]]:
    """Тарифы, как их видит ЛИЦЕНЗИОННЫЙ СЕРВЕР, — строки, а не наш `Plan`.

    Два источника обязаны сходиться, и консоль — единственное место, где
    расхождение видно глазом, а не только красным тестом. Поэтому здесь читается
    именно та сторона, по которой сервер принимает решения: наши строки лежат в
    базе рядом и берутся из ORM.
    """
    body = _get(PLANS, {})
    rows = body.get("plans", [])
    return rows if isinstance(rows, list) else []


def set_plan(code: str, values: dict[str, object], actor: str) -> dict[str, object]:
    """Поправить тариф на лицензионном сервере.

    `actor` обязателен и уезжает в `updated_by`: только он отличает правленную
    строку от посеянной, поэтому запись без него сделала бы `source` выдумкой.
    Передаётся почта вошедшего сотрудника — та же дисциплина, что у `actor` в
    журнале раскрытий.
    """
    body = _post(PLANS, {"code": code, "actor": actor, **values})
    plan = body.get("plan", {})
    return plan if isinstance(plan, dict) else {}


def fleet(org_ids: list[str]) -> dict[str, dict[str, object]]:
    """Счётчики и инстансы СРАЗУ по нескольким организациям, по `org_id`.

    ПАКЕТ ПО НАЗВАННЫМ, А НЕ ПЕРЕЧИСЛЕНИЕ. Витрина держит меньший токен, и
    каталог всех абонентов (`/admin/list`) ей не положен — это единственное, что
    разделение токенов защищает. Здесь она и не перечисляет: список организаций у
    неё свой, она их сама создала, и ручка отвечает ровно про названных.

    Пустой список — ни одного обращения: страница без клиентов не должна ходить
    по сети, чтобы узнать это.
    """
    if not org_ids:
        return {}
    body = _get(FLEET, {"org_ids": ",".join(org_ids)})
    rows = body.get("orgs", [])
    return {str(row.get("org_id", "")): row for row in rows if isinstance(row, dict)}


def chains(org_id: str) -> dict[str, object]:
    """Цепь отчётов по процессам одной организации плюс её история по суткам.

    `usage_totals` отдаёт разрывы СУММОЙ — по ней видно, что что-то не так, и
    нечего делать дальше. Здесь видно, какой процесс и на каком месте цепи.
    """
    return _get(CHAINS, {"org_id": org_id})
