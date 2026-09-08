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

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Annotated
from dataclasses import dataclass

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from licensing.keys import encode_public, load_signing_key
from licensing.pack import build_plaintext
from licensing.store import (
    STATUS_ACTIVE,
    STATUS_REVOKED,
    STATUS_SUSPENDED,
    STATUS_UNPAID,
    LicenseStore,
)
from pseudex import metrics as metrics_format
from pseudex.bundle import (BundleError, is_recipient, nonce_wrap,
                            plaintext_hash, seal, sign_lease, verify_report)

_log = logging.getLogger("licensing.server")

_DB = os.environ.get("PSEUDEX_LICENSE_DB", "license.db")
_TTL_SECONDS = int(os.environ.get("PSEUDEX_LEASE_TTL_SECONDS", "86400"))
_GRACE_SECONDS = int(os.environ.get("PSEUDEX_GRACE_SECONDS", "172800"))
_MIN_ENGINE = os.environ.get("PSEUDEX_MIN_ENGINE_VERSION", "")

# ДРЕЙФ БАНДЛА — ГЛАВНЫЙ ДОЛГОВЕЧНЫЙ РЫЧАГ ПРОТИВ ПИРАТСТВА, и он держится на
# одном неравенстве: захваченный plaintext-бандл обслуживает не дольше TTL+grace,
# а содержимое бандла ротируется на каденции ГАР (дважды в неделю, ≤3.5 суток).
# Пока TTL меньше окна ротации, украденная копия ПРОТУХАЕТ внутри своего же срока
# годности — детектор на ней начинает течь, и пиратство превращается в гонку, а
# не в разовую кражу (тот же принцип, что ре-версии Denuvo; research
# 2026-09-01-antitamper-nuitka §7 ход №4). Рычаг бесплатный и уже работает — его
# единственный враг за пять лет сопровождения это тихое «давайте TTL на месяц,
# чтобы реже дёргать сервер»: это НЕ операционная настройка, это снятие защиты.
# Поэтому потолок объявляется громко на старте, а не живёт устным знанием.
_DRIFT_TTL_CEILING_SECONDS = 7 * 86400

# How often to drop leases too old to count in any window. `leases` gains ~3 rows
# per worker per day (lease_id is fresh on every renewal, so INSERT replaces
# nothing); `may_lease` already ignores the old ones, this only reclaims disk.
_PRUNE_INTERVAL_SECONDS = int(os.environ.get("PSEUDEX_PRUNE_INTERVAL_SECONDS", "3600"))


async def _prune_loop() -> None:
    """Periodically prune expired lease rows so the table does not grow forever.

    The method existed but nothing called it in production — only a test — so the
    table grew unbounded on the very machine we run on. Offloaded to a thread
    because `prune_leases` takes the store lock; a bare except keeps a maintenance
    task from ever killing the loop."""
    while True:
        await asyncio.sleep(_PRUNE_INTERVAL_SECONDS)
        try:
            removed = await asyncio.to_thread(STORE.prune_leases, _TTL_SECONDS)
            if removed:
                _log.info("pruned %d lease rows too old to count", removed)
        except Exception:  # noqa: BLE001 — maintenance must not die
            _log.exception("lease prune failed; will retry next interval")

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
    if _TTL_SECONDS + _GRACE_SECONDS > _DRIFT_TTL_CEILING_SECONDS:
        _log.warning(
            "LEASE WINDOW %ss (ttl+grace) EXCEEDS THE BUNDLE-DRIFT CEILING %ss. A "
            "captured bundle now outlives the ГАР rotation window, so the anti-"
            "piracy drift lever is materially weakened — a stolen copy no longer "
            "rots within its own validity. This is a security posture change, not "
            "an ops convenience; shorten PSEUDEX_LEASE_TTL_SECONDS / "
            "PSEUDEX_GRACE_SECONDS unless this is deliberate.",
            _TTL_SECONDS + _GRACE_SECONDS, _DRIFT_TTL_CEILING_SECONDS)
    if _FAULT:
        _log.warning("FAULT INJECTION ACTIVE (%s) — this server is deliberately "
                     "returning broken leases. Never run this in production.", _FAULT)
    if _LOG_RAW_BODY:
        _log.warning("RAW BODY LOGGING ACTIVE — lease request bodies go to the log.")
    prune_task = asyncio.create_task(_prune_loop())
    try:
        yield
    finally:
        prune_task.cancel()


_STATUS_RESPONSE = {
    STATUS_UNPAID: (402, "license_unpaid", "subscription is not paid"),
    STATUS_REVOKED: (403, "license_revoked", "key has been revoked"),
    STATUS_SUSPENDED: (403, "license_revoked", "key is suspended"),
}


app = FastAPI(title="Pseudex licensing", lifespan=_lifespan)

# ИСХОДЫ СЧИТАЮТСЯ В ОДНОМ МЕСТЕ, А НЕ В ВЕТКАХ. `/v1/lease` возвращает из
# двенадцати мест, и счётчик на каждом возврате — это счётчик, который однажды
# забудут в тринадцатом; middleware видит ещё и 500, которых в тексте
# обработчика вообще нет. Именно доля 402/403 названа в `docs/operations.md` §5
# метрикой, которая отличает волну неоплат от НАШЕЙ ошибки в статусах, — и была
# там же честно помечена как нереализованная.
#
# Мощность меток ограничена ТАБЛИЦЕЙ МАРШРУТОВ, а не тем, что прислали: см.
# `_route_label`. Ни org_id, ни ключ в метку не попадают, и это не
# забывчивость — метка со значением из клиентской базы даёт Prometheus по
# временному ряду на клиента навсегда.
_OUTCOMES = metrics_format.Counter()


@app.middleware("http")
async def _count_outcomes(request: Request, call_next):
    # ПЯТИСОТКА НЕ ПРИХОДИТ СЮДА ОТВЕТОМ — ОНА ПРИХОДИТ ИСКЛЮЧЕНИЕМ. В тексте
    # обработчиков нет ни одного явного 5xx: их делает `ServerErrorMiddleware`,
    # который стоит ВЫШЕ пользовательских, поэтому `await call_next(...)` не
    # возвращается, а бросает. Первая версия просто считала возвращённый ответ —
    # то есть счётчик 5xx был бы вечным нулём, а тревога `PseudexLeaseServerErrors`
    # никогда бы не сработала. И это худший из нулей: клиент трактует 5xx как НАШ
    # сбой и берёт полные сорок восемь часов работы в долг, так что пятисотки на
    # аренде — это молчаливая раздача grace.
    try:
        response = await call_next(request)
    except Exception:
        _OUTCOMES.add((_route_label(request), "500"))
        raise
    _OUTCOMES.add((_route_label(request), str(response.status_code)))
    return response


def _route_label(request: Request) -> str:
    """МАРШРУТ, А НЕ ПУТЬ ИЗ ЗАПРОСА, и разница здесь безгранична.

    Публичное приложение смотрит в интернет (`ports: 443:8443`), а
    `request.url.path` — это то, что прислал вызывающий: один сканер за ночь
    заводит десятки тысяч НАВСЕГДА живущих временных рядов в Prometheus и
    столько же ключей в этом словаре. «Путей четыре» верно для маршрутов и
    неверно для того, что приходит.

    Всё, что не попало ни в один маршрут, сливается в одну метку: сам факт
    сканирования видеть полезно, перечислять его выдумки — нет.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", "") if route is not None else ""
    return path or "<no route>"
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


# ВТОРОЙ ТОКЕН, С МЕНЬШИМИ ПРАВАМИ, ДЛЯ ВИТРИНЫ. Один общий секрет означал, что
# компрометация витрины — а она единственная смотрит в интернет — отдаёт СПИСОК
# ВСЕХ АБОНЕНТОВ с их расходом.
#
# Это НЕ делает витрину безопасной: токен лежит у неё в окружении, и тот, кто
# исполнил там код, его прочитает. Это ограничивает РАДИУС.
_STOREFRONT_TOKEN = os.environ.get("PSEUDEX_LICENSE_STOREFRONT_TOKEN", "")


@dataclass(frozen=True)
class AdminAction:
    """Одна ручка админки: путь, метод и аудитория.

    ОДНА ТАБЛИЦА ВМЕСТО ДВУХ РАЗЪЕХАВШИХСЯ СПИСКОВ. Белый список путей был
    отдельным литералом, а витрина строила свои пути в другом репозитории и в
    другом venv — сверять их было нечем. Разъезд стоил денег дважды и обоими
    способами сразу:

      * `/admin/resume` в списке НЕ БЫЛО, поэтому клиент платил, вебхук звал
        `mark_paid`, тот получал 403 внутри `transaction.atomic()`, и счёт
        оставался `draft` с непродлённой подпиской. Деньги списаны, шлюз стоит,
        ЮKassa ретраит вечно с тем же результатом;
      * витрина строила путь АРИФМЕТИКОЙ ПО СТРОКЕ статуса и для `revoked` и
        `suspended` попадала в `/admin/revoked` и `/admin/suspended`, которых
        не существует, — 404 даже под полным токеном.

    ПОЧЕМУ `revoke` И `suspend` ВИТРИНЕ ТЕПЕРЬ МОЖНО. Прежнее обоснование —
    «ни одна из них не массовая» — верно и для них: они бьют по одной
    организации. А держатель витринного токена и так может остановить любого
    клиента через `unpaid`, который в списке был и минует grace ровно так же.
    Запрет не покупал ничего и создавал ровно тот класс расхождения, который
    стоил денег. Настоящая ценность белого списка одна: `/admin/list` —
    единственная ручка, отдающая КАТАЛОГ ВСЕХ АБОНЕНТОВ. Она и остаётся
    операторской.

    Правило по умолчанию не изменилось: новая ручка не получает витринных прав,
    пока автор не решит её аудиторию, — только теперь нерешённая аудитория
    роняет старт, а не тихо разъезжается.
    """

    path: str
    method: str
    storefront: bool


ADMIN_ACTIONS: tuple[AdminAction, ...] = (
    AdminAction("/admin/issue", "POST", True),
    AdminAction("/admin/revoke_key", "POST", True),
    AdminAction("/admin/revoke", "POST", True),
    AdminAction("/admin/suspend", "POST", True),
    AdminAction("/admin/unpaid", "POST", True),
    AdminAction("/admin/resume", "POST", True),
    AdminAction("/admin/release", "POST", True),
    AdminAction("/admin/instances", "GET", True),
    AdminAction("/admin/usage", "GET", True),
    # ЧТЕНИЕ И ПРАВКА ПРАЙС-ЛИСТА — ВИТРИНЕ, и решение стоит записать, раз
    # аудитория обязана быть решена. Белый список защищает КАТАЛОГ АБОНЕНТОВ, а
    # не цены: держатель витринного токена уже умеет выпускать, отзывать,
    # приостанавливать и возобновлять ключи ЛЮБОЙ организации, и строка прайса
    # слабее любого из этих рычагов. Запрет не купил бы ничего и создал бы ровно
    # тот класс расхождения, которым этот файл уже дважды заплатил.
    AdminAction("/admin/plans", "GET", True),
    AdminAction("/admin/plans", "POST", True),
    # ПАКЕТ ПО НАЗВАННЫМ ИДЕНТИФИКАТОРАМ — НЕ ПЕРЕЧИСЛЕНИЕ. Витрина сама создала
    # все организации и знает их список; перечислять ей незачем, ей нужно быстро
    # спросить про тех, кого она уже назвала. Поэтому ручка не отдаёт ничего, что
    # вызывающий не мог бы получить, позвав `/admin/usage` по одному, — она лишь
    # схлопывает N обращений в одно, и свойство «ни одна не массовая» цело.
    AdminAction("/admin/fleet", "GET", True),
    # Детализация за суммой `chain_breaks`, по ОДНОЙ организации.
    AdminAction("/admin/chains", "GET", True),
    # Каталог абонентов. Единственная ручка, которой у витрины быть не должно.
    AdminAction("/admin/list", "GET", False),
    # СКРЕЙП — ОПЕРАТОРУ, и по той же причине, по которой каталог не витрине:
    # это сводка по ВСЕМУ флоту в одной строке, и организации с порванной цепью
    # названы в ней поимённо. Витрине она не нужна — её консоль спрашивает про
    # тех, кого назвала сама, — а Prometheus и так наш.
    AdminAction("/admin/metrics", "GET", False),
)

_STOREFRONT_PATHS = frozenset(a.path for a in ADMIN_ACTIONS if a.storefront)


def _matches(presented: str, secret: str) -> bool:
    """Сравнение по БАЙТАМ: `compare_digest` на не-ASCII строке бросает
    TypeError, и это был бы 500 вместо 401."""
    if not presented or not secret:
        return False
    try:
        return secrets.compare_digest(presented.encode("ascii"),
                                      secret.encode("ascii"))
    except UnicodeEncodeError:
        return False


def _require_admin(request: Request) -> None:
    # СРАВНИВАЮТСЯ БАЙТЫ. `secrets.compare_digest` на строках с не-ASCII бросает
    # `TypeError`, и он превратился бы в 500 вместо 401 — тот же промах, что уже
    # найден в проверке MAC отчёта. Заголовок и так обязан быть ASCII, но
    # решать это должен явный отказ, а не исключение.
    header = request.headers.get("authorization", "")
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    if _matches(presented, _ADMIN_TOKEN):
        return
    if _matches(presented, _STOREFRONT_TOKEN):
        if request.url.path in _STOREFRONT_PATHS:
            return
        _log.warning("storefront token used on %s — refused", request.url.path)
        raise HTTPException(status_code=403,
                            detail="this token may not use that endpoint")
    raise HTTPException(status_code=401, detail="admin token required")


admin_app = FastAPI(title="Pseudex licensing admin",
                    dependencies=[Depends(_require_admin)],
                    # Автодокументация перечисляет все рычаги, а это
                    # машинный API: читать её приходит только тот, кто
                    # ищет, что тут можно нажать.
                    docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "bundle": _PLAINTEXT_HASH[:12]}


# ВЕРСИЯ КОНТРАКТА АРЕНДЫ. Движок версии 2 требовал `recipient`,
# `report_secret` и `issued_at`; версия 3 добавляет ЭХО НОНСА и блок `capacity`
# с адресом ручки ёмкости. Отсутствие обязательного поля движок трактует как
# «сервер старше меня или это повтор» и не стартует — верно по существу и
# похоже на наш сбой, если выкатить образы в неверном порядке. Марка публичная
# и без токена, чтобы выкатчик мог спросить сервер ДО раскатки движка.
#
# Сервер держит ОБЕ схемы и различает их по наличию `nonce` в теле аренды:
# движок 2 против сервера 3 работает без изменений (подпись покрывает весь
# словарь, лишние поля он не читает), движок 3 против сервера 2 отказывается
# стартовать и называет причину.
LEASE_CONTRACT = 3


@app.get("/v1/pubkey")
async def pubkey() -> dict[str, str]:
    """The verification key, so a customer can pin what their binary already has
    compiled in. Public by design — it verifies, it does not sign."""
    return {"public_key": PUBLIC_KEY, "lease_contract": str(LEASE_CONTRACT)}


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


# ПРЕДЕЛ НА ТЕЛО И ОДНА ДВЕРЬ ДЛЯ ЕГО РАЗБОРА.
#
# 64 KiB с запасом покрывают лизу и отчёт: самое большое, что клиент присылает,
# — это счётчики по типам сущностей, их девятнадцать.
_MAX_BODY_BYTES = 64 * 1024


async def json_object(request: Request) -> dict[str, object]:
    """Тело запроса как объект — или 400, и НИКОГДА 500.

    Пятисотка — это наше обещание «сломались мы», и клиент его исполняет:
    `500 ∈ _GRACE_WORTHY_STATUS` в `pseudex/license.py`, то есть уезжает в
    grace на сорок восемь часов. Значит любой вход, роняющий нас в 500, — это
    примитив «вызвать чужой отказ», доступный из тела запроса. Проверено: до
    этой правки `{"usage": {"requests": "abc"}}` и просто битый JSON давали
    ровно 500, и клиенту достаточно было отравить СВОЙ ЖЕ отчёт, чтобы ехать
    на grace, не трогая сеть.

    Зависимость, а не `try` в каждой ручке: их было семь, и в шести из них
    защиты не было вовсе. Ручка, написанная завтра без этой зависимости,
    заметна на ревью — пропущенный `try` не заметен.
    """
    raw = await request.body()
    if len(raw) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="body too large")
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="body is not JSON")
    if not isinstance(body, dict):
        # Валидный JSON, но не объект: `[]`, `5`, `"x"`. Дальше по коду везде
        # `body.get(...)`, то есть AttributeError и та же пятисотка.
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    return body


class ReportRejected(ValueError):
    """Отчёт не разобран. Несёт причину, потому что она едет клиенту."""


# Потолки. Не «на всякий случай»: `prev`, `signature` и `build` уходят в
# `process_reports` как есть, а `entities` — в JSON внутри строки `usage`.
# Потолок на пакетный запрос флота. Каждый идентификатор — два прохода по
# счётчикам, а строка запроса приходит снаружи: без границы один URL превращается
# в сколь угодно долгую работу под локом store, то есть в остановку выдачи аренд
# всем остальным. Двести покрывает экран любого разумного размера с запасом, а
# витрина всё равно листает свой собственный список.
_MAX_FLEET_ORGS = 200
_MAX_COUNTER = 2 ** 53
_MAX_ENTITY_TYPES = 200
_MAX_ENTITY_KEY = 64
_MAX_OPAQUE = 256


def _counter(report: dict[str, object], field: str) -> int:
    value = report.get(field, 0)
    # `bool` — подкласс `int`, и `True` прошёл бы как единица. Строку "5" тоже
    # не принимаем: честный клиент шлёт `int` всегда (`audit.billing_totals`),
    # а мягкая коррекция — это отчёт, о котором никто не узнал.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReportRejected(f"{field} must be an integer")
    if not 0 <= value <= _MAX_COUNTER:
        raise ReportRejected(f"{field} out of range")
    return value


def _opaque(report: dict[str, object], field: str) -> str:
    value = report.get(field, "")
    if not isinstance(value, str):
        raise ReportRejected(f"{field} must be a string")
    if len(value) > _MAX_OPAQUE:
        raise ReportRejected(f"{field} too long")
    return value


def parse_usage_report(usage: object) -> dict[str, object] | None:
    """Разобрать отчёт о расходе или отказать с причиной.

    `None` — законное «отчёта нет»: первая аренда процесса отчитываться нечем.

    ОТРИЦАТЕЛЬНОЕ НЕ ПРИНИМАЕТСЯ, И ЭТО НЕ ПЕДАНТИЗМ. Подписанный отчёт с
    `requests = -10**9` под свежим `instance_id` уводил итоги организации в
    минус: защита от отката ключуется на `(org_id, instance_id)`, а его
    выбирает клиент, и `usage_totals` строки суммирует. Дальше `build_invoice`
    записывал отрицательное значение как ПОСТОЯННУЮ ватермарку, и все
    следующие периоды давали ноль.

    `entities` проверяется ПО ЗНАЧЕНИЯМ, а не только как dict. Нечисловое
    значение переживало запись и роняло `/admin/usage` в 500 НАВСЕГДА —
    строка перечитывается на каждом вызове, — а вместе с ним кабинет и
    выставление счёта этому клиенту.
    """
    if usage is None:
        return None
    if not isinstance(usage, dict):
        raise ReportRejected("usage must be an object")
    entities = usage.get("entities", {})
    if not isinstance(entities, dict):
        raise ReportRejected("entities must be an object")
    if len(entities) > _MAX_ENTITY_TYPES:
        raise ReportRejected("too many entity types")
    clean_entities: dict[str, int] = {}
    for entity_type, count in entities.items():
        if not isinstance(entity_type, str) or len(entity_type) > _MAX_ENTITY_KEY:
            raise ReportRejected("entity type must be a short string")
        if isinstance(count, bool) or not isinstance(count, int):
            raise ReportRejected(f"count for {entity_type!r} must be an integer")
        if not 0 <= count <= _MAX_COUNTER:
            raise ReportRejected(f"count for {entity_type!r} out of range")
        clean_entities[entity_type] = count
    return {
        "requests": _counter(usage, "requests"),
        "values": _counter(usage, "values"),
        "seq": _counter(usage, "seq"),
        "entities": clean_entities,
        "prev": _opaque(usage, "prev"),
        "signature": _opaque(usage, "signature"),
        "build": _opaque(usage, "build"),
    }


def _store_usage(instance_id: str, org_id: str, usage: object,
                 pubkey: str) -> None:
    """Record the instance's cumulative counters. No-op on the first lease of a
    process, which has nothing to report yet.

    ПОДПИСЬ И ЦЕПЬ ПРОВЕРЯЮТСЯ ЗДЕСЬ, И ОТКАЗ НЕ РОНЯЕТ АРЕНДУ. «Сходится»
    здесь значит «не переписан В КАНАЛЕ» и ничего не говорит о правдивости
    чисел — полностью это разобрано в `pseudex/bundle.py::mac_report`. Отчёт,
    который не сходится, — это счёт, а не право работать: клиент с испорченной цепью
    продолжает обслуживать своих людей, а мы получаем помеченную запись и
    разговор. Ронять `/mask` за расхождение в биллинге значило бы наказывать
    конечного пользователя за спор двух юрлиц.

    Разбор — `parse_usage_report`, и он бросает `ReportRejected`. Что с этим
    делать, решает ВЫЗЫВАЮЩИЙ, потому что решение разное: на `/v1/lease` отчёт
    отбрасывается и аренда выдаётся (та же политика, что для плохой подписи), а
    на `/v1/usage`, где отчёт и есть весь смысл запроса, это 400 с причиной.
    """
    if not instance_id:
        return
    report = parse_usage_report(usage)
    if report is None:
        return
    trust = "unsigned"
    secret_hex = STORE.report_secret(org_id, pubkey) if pubkey else ""
    if secret_hex and report["signature"]:
        try:
            verify_report(usage, bytes.fromhex(secret_hex))
            trust = "signed"
        except (BundleError, ValueError) as error:
            _log.warning("usage report signature failed for org=%s instance=%s: %s",
                         org_id, instance_id, error)
            trust = "bad_signature"
    STORE.record_usage(
        org_id, instance_id, report["requests"], report["entities"],
        report["values"], seq=report["seq"], prev=report["prev"],
        signature=report["signature"], trust=trust, report_pubkey=pubkey,
        build=report["build"],
    )


@app.post("/v1/release")
async def release(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
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
    record = STORE.lookup(str(body.get("key", "")))
    if record is None:
        return JSONResponse({"error": "unknown key"}, status_code=403)
    pubkey = str(body.get("pubkey", ""))
    if not pubkey:
        return JSONResponse({"error": "no process public key"}, status_code=400)
    # БЮДЖЕТ ОСВОБОЖДЕНИЙ. Остывание ограничивает темп, но не количество:
    # контейнер, отдавший слот, продолжает обслуживать до конца TTL, и это не
    # чинится в софте, работающем в чужом периметре. Сверх бюджета ручка не
    # делает ничего, и слот истекает по TTL — как до её появления.
    budget = STORE.release_budget(record.plan)
    if STORE.releases_last_hour(record.org_id) >= budget:
        _log.warning("release budget exhausted for org=%s: %d in the last hour",
                     record.org_id, budget)
        return JSONResponse({"error": "release_budget",
                             "detail": f"не более {budget} освобождений в час"},
                            status_code=429)
    return JSONResponse({"released": STORE.release_process(record.org_id, pubkey)})


@app.post("/v1/lease")
async def lease(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    if _LOG_RAW_BODY:
        _log.info("RAW_LEASE_BODY %s",
                  json.dumps(body, ensure_ascii=False, sort_keys=True))
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
    # ФОРМА ПРОВЕРЯЕТСЯ ДО ЛЮБОЙ РАБОТЫ. Битый ключ разваливался внутри
    # `seal()` в 500, а 500 у клиента grace-worthy: строки `age1x` в теле
    # хватало, чтобы получить сорок восемь часов работы в долг.
    if not is_recipient(recipient):
        return JSONResponse({"error": "license_invalid",
                             "detail": "process public key is not an age recipient"},
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
    # ПРОВЕРКА И ЗАПИСЬ — ОДНА КРИТИЧЕСКАЯ СЕКЦИЯ. Раньше это были два вызова
    # с отпущенным между ними локом, и N одновременных аренд все видели место
    # свободным. Идентификатор аренды готовится заранее, потому что решение и
    # запись теперь неразделимы.
    lease_id = "ls_" + secrets.token_urlsafe(16)
    allowed, why_not = STORE.lease_if_allowed(
        lease_id, record.org_id, record.plan, instance_id, process_id,
        _TTL_SECONDS, pubkey=recipient)
    if not allowed:
        _log.warning("lease refused for org=%s instance=%s: %s",
                     record.org_id, instance_id, why_not)
        return JSONResponse({"error": "instance_limit", "detail": why_not},
                            status_code=409)
    # Counters are recorded AFTER the instance is admitted, not before. An
    # over-limit renewal is refused above (409) and must leave NO usage row: a
    # single valid key sending a fresh client-chosen instance_id each time would
    # otherwise INSERT an unbounded number of usage rows and inflate the
    # instance/missing counters, all past a cap that only bounds the `leases`
    # table. An admitted instance loses nothing — `lease_if_allowed` persisted
    # its slot in the same critical section, so the "died mid-renewal is still
    # accounted for" intent holds for every instance that is actually serving.
    #
    # ИСПОРЧЕННЫЙ ОТЧЁТ ОТБРАСЫВАЕТСЯ, А АРЕНДА ВЫДАЁТСЯ. Ровно та политика,
    # которую докстринг `_store_usage` уже объявляет для плохой подписи: спор о
    # биллинге не имеет права останавливать конечного пользователя. Но и тишиной
    # это быть не должно — считается отдельно от «расхода не было».
    # ПРОДЛЕНИЕ БЕЗ ОТЧЁТА — ЭТО ЗАПИСЬ, А НЕ ТИШИНА. `lease_id` клиент шлёт с
    # самого начала, и до этой правки сервер его не читал вовсе, поэтому
    # перехватчик, выбрасывающий поле `usage`, не двигал НИ ОДНОГО счётчика:
    # подделать отчёт было видно, повторить видно, снять целиком — нет.
    if body.get("lease_id") and body.get("usage") is None:
        _log.warning("renewal without a usage report for org=%s instance=%s",
                     record.org_id, instance_id)
        STORE.record_missing_report(record.org_id, instance_id)
    try:
        _store_usage(instance_id, record.org_id, body.get("usage"), recipient)
    except ReportRejected as error:
        _log.warning("malformed usage report from org=%s instance=%s: %s",
                     record.org_id, instance_id, error)
        STORE.record_malformed(record.org_id, instance_id)
    # СЕКРЕТ ОТЧЁТОВ, ЗАПЕЧАТАННЫЙ ПОЛУЧАТЕЛЮ. Это закрывает ПЕРЕХВАТЧИКА:
    # `recipient` под подписью, поэтому подменить его на свой он не может —
    # контейнер сверит с собственным ключом и откажется стартовать. Про самого
    # клиента отсюда не следует ничего: получателя называет он сам, и владелец
    # ключа подписывает что угодно (`pseudex/bundle.py::mac_report`). Поэтому
    # счёт строится на выданной ёмкости, а не на отчёте.
    report_secret = secrets.token_bytes(32)
    STORE.record_report_secret(record.org_id, recipient, report_secret.hex())

    # ЭХО НОНСА — ЕДИНСТВЕННОЕ, ЧТО УБИВАЕТ ПОВТОР. Свежесть по часам не
    # годится: часы в контейнере чужие, а окно `ttl + skew` на проде это
    # двадцать пять часов, в течение которых захваченная лиза принималась как
    # своя — проверено, `granted` при этом замирал навсегда, а движок показывал
    # `state=active` и ноль ошибок.
    nonce = str(body.get("nonce", ""))
    contract_3 = bool(nonce)
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
        # ПОЛЕ КОНТРАКТА 2, ОСТАЁТСЯ ПОКА В ПАРКЕ ЕСТЬ СТАРЫЕ ДВИЖКИ. Для
        # контракта 3 ёмкость покупается на `/v1/meter`, и здесь не чеканится
        # ничего.
        "requests_granted": STORE.grant_size(record.plan),
    }
    if contract_3:
        payload["nonce"] = nonce
        payload["capacity"] = {"endpoint": "/v1/meter",
                               "target_seconds": STORE.METER_TARGET_SECONDS}
        payload["lease_contract"] = LEASE_CONTRACT
    else:
        # Мост: движок контракта 2 по-прежнему получает грант по времени и
        # считается по старой, завышающей схеме. Никого не бьёт, пока тариф
        # фиксированный, и исчезает вместе с последним старым образом.
        STORE.record_grant(record.org_id, recipient, STORE.grant_size(record.plan))
    payload["report_secret_sha256"] = hashlib.sha256(report_secret).hexdigest()
    payload["signature"] = sign_lease(payload, SIGNING_KEY)

    # КОНТРАКТ 3: внутренний слой, чей ключ выведен из СВЕЖЕГО нонса клиента.
    # Повтор старой аренды у пропатченного клиента даёт нерасшифровываемый
    # бандл (`pseudex/bundle.py::nonce_wrap`). Контракт 2 получает голый бандл.
    inner = nonce_wrap(_PLAINTEXT, nonce) if contract_3 else _PLAINTEXT
    sealed = seal(inner, recipient)
    if _FAULT == "corrupt_bundle":
        # Flip one byte in the middle of the ciphertext. age is authenticated, so
        # this must surface as a decryption failure, not as garbled assets.
        middle = len(sealed) // 2
        sealed = sealed[:middle] + ("A" if sealed[middle] != "A" else "B") + sealed[middle + 1:]
    payload["bundle"] = sealed
    return JSONResponse(payload)


@app.post("/v1/meter")
async def meter(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    """Купить следующий квант ёмкости, назвав свой расход.

    ЛЁГКАЯ РУЧКА, И ЭТО АРИФМЕТИКА, А НЕ ЭСТЕТИКА. Аренда пересобирает и
    заново шифрует весь бандл — 1481 КБ после zlib, около двух мегабайт
    age+base64 на КАЖДОЕ обращение, синхронно на цикле однопроцессного
    uvicorn. Покупать этим ценой квант в несколько сотен запросов нельзя.
    Здесь около килобайта: один HMAC, одна подпись, одна запись.

    Частота обращений — `1 / (0.75 · τ_Q)`, то есть одно в четыре минуты на
    процесс НЕЗАВИСИМО ОТ ТРАФИКА: квант растёт вместе с расходом. Клиент под
    нагрузкой не создаёт нагрузки нам.
    """
    key = body.get("key")
    if not isinstance(key, str) or not key:
        return JSONResponse({"error": "license_missing", "detail": "no key presented"},
                            status_code=401)
    record = STORE.lookup(key)
    if record is None:
        return JSONResponse({"error": "license_invalid", "detail": "unknown key"},
                            status_code=403)
    if record.status != STATUS_ACTIVE:
        status_code, error, detail = _STATUS_RESPONSE.get(
            record.status,
            (403, "license_invalid", f"key is in an unusable state ({record.status!r})"))
        return JSONResponse({"error": error, "detail": detail}, status_code=status_code)

    pubkey = str(body.get("pubkey", ""))
    nonce = str(body.get("nonce", ""))
    if not pubkey or not nonce:
        return JSONResponse({"error": "license_invalid",
                             "detail": "pubkey and nonce are required"},
                            status_code=400)

    # ОТЧЁТ О РАСХОДЕ ЕДЕТ ТЕМ ЖЕ MAC, ЧТО И ВСЕГДА. Новых секретов нет:
    # `report_secret` уже запечатан на этот ключ процесса.
    acked: int | None = None
    trust = "none"
    ack = body.get("ack")
    if isinstance(ack, dict):
        try:
            consumed = _counter(ack, "consumed")
        except ReportRejected as error:
            return JSONResponse({"error": "report_rejected", "detail": str(error)},
                                status_code=400)
        secret_hex = STORE.report_secret(record.org_id, pubkey)
        if secret_hex and ack.get("signature"):
            try:
                verify_report(ack, bytes.fromhex(secret_hex))
                acked, trust = consumed, "signed"
            except (BundleError, ValueError) as error:
                _log.warning("capacity ack failed for org=%s pubkey=%s: %s",
                             record.org_id, pubkey[:12], error)
                trust = "bad_signature"
        else:
            trust = "unsigned"

    # ДЕШЁВЫЙ ПОТОЛОК ЧАСТОТЫ. Инфляция ёмкости атакующему бесполезна — она
    # только поднимает его же счёт, — но ручка публичная, а сервер
    # однопроцессный, и долбёжка по ней это уже наша проблема, а не его.
    # 429 у клиента grace-worthy, поэтому честного это ничем не задевает: он
    # приходит раз в четыре минуты на процесс.
    if STORE.metered_too_recently(record.org_id, pubkey, time.time()):
        return JSONResponse({"error": "too_fast", "detail": "one grant per second"},
                            status_code=429)
    quantum = STORE.issue_quantum(record.org_id, pubkey, record.plan, acked,
                                  time.time())
    payload: dict[str, object] = {
        "kind": "capacity",
        # Квант не может быть прочитан как лиза, а лиза как квант: тип внутри
        # подписи, и клиент его сверяет.
        "recipient": pubkey,
        "nonce": nonce,
        "org_id": record.org_id,
        "plan": record.plan,
        "issued_at": int(time.time()),
        "ack_trust": trust,
        "lease_contract": LEASE_CONTRACT,
        **quantum,
    }
    payload["signature"] = sign_lease(payload, SIGNING_KEY)
    return JSONResponse(payload)


@app.post("/v1/usage")
async def usage(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    """Out-of-band counter delivery. Normally counters ride on /v1/lease; this
    exists for a client that wants to report before its renewal is due."""
    key = body.get("key")
    if not isinstance(key, str):
        return JSONResponse({"error": "license_missing"}, status_code=401)
    record = STORE.lookup(key)
    if record is None or record.status != STATUS_ACTIVE:
        return JSONResponse({"error": "license_invalid"}, status_code=403)
    # ЗДЕСЬ ОТЧЁТ И ЕСТЬ ВЕСЬ СМЫСЛ ЗАПРОСА, поэтому неразобранный — это 400 с
    # причиной, а не молчаливый пропуск.
    try:
        _store_usage(str(body.get("instance_id", "")), record.org_id,
                     body.get("usage"), str(body.get("pubkey", "")))
    except ReportRejected as error:
        return JSONResponse({"error": "report_rejected", "detail": str(error)},
                            status_code=400)
    return JSONResponse({"status": "recorded"})


@admin_app.get("/admin/instances")
async def admin_instances(request: Request) -> JSONResponse:
    """Which containers hold a slot for this org, and since when."""
    org_id = request.query_params.get("org_id", "")
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)
    return JSONResponse({"org_id": org_id,
                         "window_seconds": _TTL_SECONDS,
                         "cooldown_seconds": STORE.RELEASE_COOLDOWN_SECONDS,
                         "releases_last_hour": STORE.releases_last_hour(org_id),
                         "instances": STORE.active_instances(org_id, _TTL_SECONDS)})


@admin_app.post("/admin/release")
async def admin_release(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    """Free a slot held by a container that is no longer running."""
    org_id = str(body.get("org_id", ""))
    instance_id = str(body.get("instance_id", ""))
    if not org_id or not instance_id:
        return JSONResponse({"error": "org_id and instance_id required"},
                            status_code=400)
    released = STORE.release_instance(org_id, instance_id)
    return JSONResponse({"released": released})


@admin_app.post("/admin/issue")
async def admin_issue(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    """Mint a key. The full key is returned ONCE and never stored in the clear.

    THE PLAN IS VALIDATED HERE, and the default is a plan that exists. It was
    `"standard"` — a string present in none of `PLAN_INSTANCES`, `PLAN_GRANT`,
    `QUANTUM_BOUNDS` or `RESERVE_MAX` — so every key issued without an explicit
    plan silently got the smallest tariff's limits: one container, 5 000-request
    grants, the "start" quantum bounds. Nothing failed and nothing logged; the
    customer simply hit an instance ceiling belonging to a tariff they had not
    bought, and the refusal named a limit no screen could explain.

    Refusing an unknown plan rather than defaulting is the point: a typo in the
    storefront's plan code, or a plan added to the shop and not to the licensing
    server, must be a 400 somebody reads — not a downgrade nobody sees.
    """
    org_id = str(body.get("org_id", ""))
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)
    plan = str(body.get("plan", "start"))
    if not STORE.known_plan(plan):
        return JSONResponse(
            {"error": "unknown plan", "plan": plan, "known": STORE.known_plans()},
            status_code=400)
    key = STORE.issue_key(org_id, plan)
    return JSONResponse({"org_id": org_id, "key": key})


async def _set_status(body: dict, status: str) -> JSONResponse:
    org_id = str(body.get("org_id", ""))
    changed = STORE.set_status(org_id, status)
    if changed == 0:
        return JSONResponse({"error": "unknown org_id", "org_id": org_id}, status_code=404)
    return JSONResponse({"org_id": org_id, "status": status, "keys_changed": changed})


@admin_app.post("/admin/revoke")
async def admin_revoke(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    return await _set_status(body, STATUS_REVOKED)


@admin_app.post("/admin/revoke_key")
async def admin_revoke_key(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    """Revoke a single key by its hash, without touching the organisation.

    The organisation-wide levers stop everything the customer runs; this one
    exists so "this key leaked" is not the same action as "stop this customer".
    """
    key_hash = str(body.get("key_hash", ""))
    if not key_hash:
        return JSONResponse({"error": "key_hash required"}, status_code=400)
    changed = STORE.revoke_key_hash(key_hash)
    if changed == 0:
        return JSONResponse({"error": "unknown or already revoked key"},
                            status_code=404)
    return JSONResponse({"revoked": changed})


@admin_app.post("/admin/suspend")
async def admin_suspend(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    return await _set_status(body, STATUS_SUSPENDED)


@admin_app.post("/admin/unpaid")
async def admin_unpaid(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    return await _set_status(body, STATUS_UNPAID)


@admin_app.post("/admin/resume")
async def admin_resume(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    return await _set_status(body, STATUS_ACTIVE)


@admin_app.get("/admin/plans")
async def admin_plans() -> JSONResponse:
    """Тарифы как они есть НА САМОМ ДЕЛЕ — строки, не константы в коде.

    `source` отличает посеянное от правленного руками, и это не украшение: сид
    идёт `INSERT OR IGNORE`, поэтому поправить константу и выкатить релиз больше
    НЕ меняет работающий тариф. Единственный способ увидеть это снаружи — вот
    это поле.
    """
    return JSONResponse({"plans": STORE.plans()})


@admin_app.post("/admin/plans")
async def admin_set_plan(body: Annotated[dict, Depends(json_object)]) -> JSONResponse:
    """Создать или поправить тариф.

    `actor` обязателен по той же причине, по которой он обязателен у `/reveal`:
    запись без того, кто её сделал, — не запись. Она и отличает `edited` от
    `seed`, так что пустой `actor` сделал бы правку неотличимой от посева.

    Числа проверяются на неотрицательность и на потолок, потому что тело сюда
    приходит из интерфейса: `max_instances` со знаком минус превратил бы
    `instances_allowed` в отказ всем контейнерам организации, а нулевой
    `quantum_max` — в процесс, которому никогда не выдадут ёмкость.
    """
    code = str(body.get("code", "")).strip()
    if not code:
        return JSONResponse({"error": "code required"}, status_code=400)
    actor = str(body.get("actor", "")).strip()
    if not actor:
        return JSONResponse({"error": "actor required"}, status_code=400)

    values: dict[str, object] = {}
    for field in STORE._PLAN_FIELDS:
        if field not in body:
            continue
        try:
            number = int(body[field])
        except (TypeError, ValueError):
            return JSONResponse({"error": f"{field} must be a whole number"},
                                status_code=400)
        # Верхняя граница есть у каждого поля по одной причине: число из тела
        # уезжает в арифметику ёмкости, а `int` в Python не переполняется — он
        # просто становится очень большим, и `granted` вместе с ним.
        if number < 1 or number > 10_000_000:
            return JSONResponse(
                {"error": f"{field} must be between 1 and 10000000", "got": number},
                status_code=400)
        values[field] = number
    if not values:
        return JSONResponse({"error": "nothing to change",
                             "fields": list(STORE._PLAN_FIELDS)}, status_code=400)
    try:
        # Согласованность строки — забота store, а не этой ручки: тариф правит и
        # интерфейс, и однажды CLI, и запись, оставляющая пол выше потолка, не
        # должна зависеть от того, кто её позвал.
        row = STORE.set_plan(code, values, actor)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    _log.info("plan %s changed by %s: %s", code, actor, values)
    return JSONResponse({"plan": row})


@admin_app.get("/admin/fleet")
async def admin_fleet(request: Request) -> JSONResponse:
    """Счётчики и инстансы СРАЗУ ПО НЕСКОЛЬКИМ названным организациям.

    Ровно то же, что `/admin/usage` отдаёт по одной, — и намеренно ничего сверх.
    Вызывающий обязан назвать идентификаторы, поэтому ручка не перечисляет
    абонентов и не становится вторым `/admin/list`: она экономит round-trip, а не
    расширяет права.

    Экран «все клиенты» строится из СВОЕГО списка организаций (витрина их и
    создала) плюс один такой запрос, а не из каталога лицензионного сервера.

    ИНСТАНСЫ ЗДЕСЬ — ДЕРЖАЩИЕ СЛОТ, а не строки аренд, и это НЕ то же самое, что
    отдаёт `/admin/usage`. Там `STORE.instances` — сырые строки таблицы аренд,
    по строке на КАЖДУЮ выдачу, вместе с освобождёнными и с `LIMIT 100`: их
    количество не считает контейнеры, оно упирается в сотню за сутки работы. На
    экране флота колонка называется «занято по тарифу», поэтому здесь берётся
    ровно то, чем этот потолок и принуждается, — `active_instances`, как в
    `/admin/instances`.
    """
    raw = request.query_params.get("org_ids", "")
    org_ids = [part.strip() for part in raw.split(",") if part.strip()]
    if not org_ids:
        return JSONResponse({"error": "org_ids required"}, status_code=400)
    if len(org_ids) > _MAX_FLEET_ORGS:
        return JSONResponse(
            {"error": "too many org_ids", "limit": _MAX_FLEET_ORGS,
             "got": len(org_ids)}, status_code=400)
    # Порядок и дубликаты — вызывающего: повтор идентификатора не должен стоить
    # двух проходов по счётчикам.
    seen: dict[str, dict[str, object]] = {}
    for org_id in org_ids:
        if org_id in seen:
            continue
        seen[org_id] = {"org_id": org_id,
                        "usage": STORE.usage_totals(org_id),
                        "instances": STORE.active_instances(org_id, _TTL_SECONDS)}
    return JSONResponse({"orgs": list(seen.values()),
                         "window_seconds": _TTL_SECONDS})


@admin_app.get("/admin/chains")
async def admin_chains(request: Request) -> JSONResponse:
    """Цепь отчётов по каждому процессу ОДНОЙ организации.

    `/admin/usage` отдаёт `chain_breaks` суммой по организации — по ней видно,
    что что-то не так, и совершенно нечего делать дальше. Здесь видно, КАКОЙ
    процесс, на каком месте цепи и когда его слышали в последний раз.
    """
    org_id = request.query_params.get("org_id", "")
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)
    detail = STORE.chain_detail(org_id)
    return JSONResponse({"org_id": org_id, "history": STORE.usage_history(org_id),
                         **detail})


@admin_app.get("/admin/list")
async def admin_list() -> JSONResponse:
    return JSONResponse({"orgs": STORE.list_orgs()})


@admin_app.get("/admin/metrics")
async def admin_metrics() -> PlainTextResponse:
    """The fleet in one scrape: lease outcomes, capacity, and broken chains.

    ЭТО ВТОРАЯ ПОЛОВИНА НАБЛЮДАЕМОСТИ, И ОНА НЕ ЗАМЕНЯЕТ ПЕРВУЮ. Движок отдаёт
    своё собственное состояние клиенту, который его держит; здесь — то, что
    видно только у нас: сколько аренд отказано и с каким кодом, сколько
    контейнеров обслуживает прямо сейчас, и у кого порвана цепь отчётов.

    `chain_breaks` уже писался в базу и уже был виден в консоли — но КОНСОЛЬ
    НАДО ОТКРЫТЬ, а тревога должна прийти сама. Ровно этой разницы стоила
    метрика 402/403: она описана в `docs/operations.md` §5 и была помечена там
    «не реализовано», потому что честнее, чем оставлять описание метрики,
    которой нет.
    """
    fleet = STORE.fleet_totals(_TTL_SECONDS)
    out = [
        metrics_format.series(
            "pseudex_license_responses_total", _OUTCOMES.snapshot(),
            "Responses on /v1/*, by path and status code. The 402/403 share "
            "separates a wave of non-payment from our own error in statuses",
            ("path", "code"), "counter"),
        metrics_format.series(
            "pseudex_keys", fleet["keys_by_status"],
            "Issued keys by status", "status"),
        metrics_format.render("pseudex_orgs_serving", fleet["orgs_serving"],
                              "Organisations holding a live lease"),
        metrics_format.render("pseudex_instances_serving", fleet["instances_serving"],
                              "Containers holding a live lease"),
        metrics_format.render("pseudex_processes_serving", fleet["processes_serving"],
                              "Worker processes holding a live lease"),
        metrics_format.render("pseudex_fleet_requests_total", fleet["requests"],
                              "Requests reported by the whole fleet", "counter"),
        metrics_format.render("pseudex_fleet_values_total", fleet["values"],
                              "Personal values reported by the whole fleet", "counter"),
        metrics_format.render("pseudex_chain_breaks_total", fleet["chain_breaks"],
                              "Report-chain breaks across the fleet: a gap, a "
                              "reorder, or an old report replayed", "counter"),
        # ПОИМЁННО — ТОЛЬКО ПОРВАННЫЕ. Метка по организации обычно означает ряд
        # на клиента навсегда; здесь множество ограничено бедой, а не продажами,
        # и схлопывается обратно, когда беда починена.
        metrics_format.series("pseudex_chain_breaks_by_org", fleet["breaks_by_org"],
                              "Chain breaks, named — only organisations that have any",
                              "org", "counter"),
        metrics_format.render("pseudex_unverified_reports_total",
                              fleet["unverified_reports"],
                              "Reports accepted with a bad or missing signature", "counter"),
        metrics_format.render("pseudex_malformed_reports_total",
                              fleet["malformed_reports"],
                              "Reports we could not parse — NOT the same as no usage",
                              "counter"),
        metrics_format.render("pseudex_reports_missing_total", fleet["reports_missing"],
                              "Renewals that carried no usage report at all", "counter"),
        metrics_format.render("pseudex_counter_resets_total", fleet["resets"],
                              "Times a cumulative counter went backwards", "counter"),
    ]
    return PlainTextResponse("".join(out),
                             media_type="text/plain; version=0.0.4; charset=utf-8")


@admin_app.get("/admin/usage")
async def admin_usage(request: Request) -> JSONResponse:
    """Counters for ONE org, and the org must be named.

    `org_id` used to be optional here while `/admin/instances` next door required
    it. An omitted parameter therefore queried the literal empty string and
    returned a fully-formed, all-zero structure — indistinguishable from a real
    customer who has not started yet. The caller that drops the parameter (a
    console with a typo in a query string, a script whose variable is unset) gets
    a plausible answer rather than an error, and "this customer used nothing" is
    exactly the wrong thing to be confidently wrong about on a billing screen.
    """
    org_id = request.query_params.get("org_id", "")
    if not org_id:
        return JSONResponse({"error": "org_id required"}, status_code=400)
    return JSONResponse({
        "usage": STORE.usage_totals(org_id),
        "instances": STORE.instances(org_id),
    })


def _check_admin_surface() -> None:
    """Смонтированное обязано совпасть с объявленным — иначе процесс не встаёт.

    КОД ПРОТИВ КОДА, А НЕ КОД ПРОТИВ ПАМЯТИ. Ручка, добавленная без строки в
    `ADMIN_ACTIONS`, и строка без ручки — одинаково валят старт. Инвариант
    детерминированный, поэтому в проде он упасть не может, не упав раньше в CI;
    а разъезд, который стоил нам оплаченного и невозобновлённого обслуживания,
    перестаёт быть тем, что замечают по жалобе клиента.
    """
    mounted = {(route.path, method)
               for route in admin_app.routes
               for method in (getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}
               if getattr(route, "path", "").startswith("/admin")}
    declared = {(action.path, action.method) for action in ADMIN_ACTIONS}
    if mounted != declared:
        raise RuntimeError(
            "admin surface drift: смонтировано без объявления "
            f"{sorted(mounted - declared)}, объявлено без ручки "
            f"{sorted(declared - mounted)}")


_check_admin_surface()
