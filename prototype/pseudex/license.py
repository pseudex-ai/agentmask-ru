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

import hashlib
import logging
import os
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pseudex.assets import ASSETS
from pseudex.measure import build_measurement
from pseudex.bundle import (
    BundleError,
    nonce_unwrap,
    mac_report,
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

# ...КРОМЕ ЭТИХ ОТВЕТОВ, ПРИШЕДШИХ С ТЕМ ЖЕ КОДОМ. 409 попал в список выше
# ради «движок слишком стар», и это верно. Но `may_lease` отказывает ТЕМ ЖЕ
# кодом — с обоснованием «подписка в порядке, ключ валиден, вы просто запустили
# больше контейнеров, чем купили», — и два независимо верных решения
# столкнулись: контейнер, которому отказали за превышение тарифа, уходил в
# STALE и обслуживал БЕЗЛИМИТНО семьдесят два часа. То есть превышение тарифа
# оплачивалось трёхсуточным подарком.
#
# Различается по полю `error` в теле, которое клиент и так разбирает, — код
# ответа менять не нужно, а значит и контракт не ломается.
_ANSWER_CODES = frozenset({"instance_limit", "release_budget"})

_STARTUP_ATTEMPTS = 3
_STARTUP_BACKOFF_SECONDS = 2.0

# How often a REVOKED or UNPAID licence re-asks. Slower than a normal renewal —
# the answer is unlikely to change minute to minute — but never never: a customer
# who pays their invoice must come back without restarting every container.
_TERMINAL_RETRY_SECONDS = 60.0


# What to DO about each terminal code. A persona following the documented
# `docker run` hit an unreachable licensing host and got a bare Python traceback
# — the gateway refused to serve, exactly as designed, and told them nothing
# about why or what to try. Fail-closed without a diagnosis reads as "broken",
# and the customer's next move is to close the tab rather than open the firewall.
REMEDIES: dict[str, str] = {
    "license_missing":
        "Переменная PSEUDEX_LICENSE_KEY не задана. Ключ показывается один раз "
        "при активации; если он потерян — выпустите новый в личном кабинете.",
    "bundle_unavailable":
        "Не удалось связаться с сервером лицензий. Проверьте, что из контейнера "
        "есть исходящий доступ к нему по HTTPS:\n"
        "    docker exec <контейнер> getent hosts <хост лицензий>\n"
        "Чаще всего мешает закрытый исходящий трафик или корпоративный прокси. "
        "Адрес сервера задаётся переменной PSEUDEX_LICENSE_URL.",
    "license_invalid":
        "Сервер лицензий не признал ключ. Проверьте, что скопирован он целиком "
        "и что не отозван в личном кабинете.",
    "license_expired":
        "Аренда истекла и льготный период закончился. Проверьте оплату — после "
        "неё обслуживание восстанавливается без перезапуска контейнера.",
    "license_revoked":
        "Ключ отозван в личном кабинете. Выпустите новый и перезапустите "
        "контейнер с ним.",
    "bundle_corrupt":
        "Полученный пакет не прошёл проверку подписи. Это не чинится настройками "
        "— напишите нам, приложив вывод контейнера.",
    "capacity_exhausted":
        "Предоплаченная ёмкость израсходована, а лицензионный сервер сейчас "
        "недоступен, поэтому взять следующую невозможно. Проверьте исходящий "
        "доступ к нему по HTTPS — как только связь вернётся, обслуживание "
        "продолжится само, без перезапуска контейнера.",
    "instance_limit":
        "Тариф не позволяет столько одновременно работающих контейнеров. "
        "Остановите лишние или смените тариф в личном кабинете.",
}


def explain(code: str) -> str:
    """The operator-facing remedy for a terminal licence code."""
    return REMEDIES.get(code, "Напишите нам, приложив вывод контейнера.")


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
    # The lease has always carried the plan and the timings; nothing passed them
    # on, so the subscription screen could only show lease mechanics — and
    # «остаток grace» while the licence is active is a number that frightens
    # without meaning anything. What the operator came to that screen for is
    # which plan is running and when it renews.
    plan: str | None
    # ЁМКОСТЬ — ТО, ЧЕГО ОПЕРАТОР НЕ ВИДЕЛ ВООБЩЕ. `capacity()` не вызывался
    # ниоткуда, а исчерпание выглядело на экране как `license_expired` — то
    # есть неверный диагноз и неверная подсказка.
    consumed: int
    granted: int
    capacity_left: int | None
    ttl_seconds: int
    renew_after_seconds: int
    next_renewal_in_seconds: float | None
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


def _public_key_materials() -> list[str]:
    """Ключи проверки, которые эта сборка принимает — СПИСОК, а не один.

    РОТАЦИЯ БЕЗ ОДНОВРЕМЕННОГО ВЫКЛЮЧЕНИЯ ВСЕГО. Ключ вкомпилирован в бинарник,
    поэтому замена одного значения означала: собрать образ с новым ключом,
    выкатить его КАЖДОМУ клиенту и только потом начать подписывать новым — а до
    этого момента старый ключ уже скомпрометирован и всё ещё единственный
    принимаемый. Список разрывает эту связку: новый образ принимает оба, мы
    переводим подпись на новый, старый выводится следующим релизом.

    Порядок значения не имеет — подпись либо сходится с одним из них, либо ни с
    одним. Разделитель запятая, пробелы отбрасываются.
    """
    return [item.strip() for item in _public_key_material().split(",")
            if item.strip()]


# Расхождение часов контейнера и нашего сервера, которое мы прощаем при
# проверке свежести лизы. Час — заведомо больше любого разумного дрейфа и
# заведомо меньше окна, в котором повтор что-то даёт.
_CLOCK_SKEW_SECONDS = 3600


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
        self._pending_nonce = ""
        # СЕКРЕТ ОТЧЁТА ПРИХОДИТ ЗАПЕЧАТАННЫМ НА ЭТОТ ЖЕ ПРОЦЕСС и никогда не
        # передаётся наружу. Открытый ключ подписи отправлять было нельзя:
        # перехватчик на хосте клиента (TLS проверяется по СИСТЕМНОМУ хранилищу
        # контейнера, см. `verify` ниже) подменял его на свой и подписывал
        # счета сам. Секрет подменить нечем — чтобы его прочитать, надо быть
        # получателем, а получатель теперь назван в ПОДПИСАННОЙ лизе.
        # ЁМКОСТЬ ТЕКУЩЕЙ АРЕНДЫ. Счётчик в ПАМЯТИ, и это не слабость: сбросить
        # его перезапуском можно, но перезапуск требует НОВОЙ аренды — ключ
        # процесса генерируется заново, — а новая аренда это новый грант, то
        # есть новая запись в нашем счёте. Обнулять счётчик рестартом означает
        # платить за рестарт.
        # ЁМКОСТЬ НАКАПЛИВАЕТСЯ, А НЕ ОБНОВЛЯЕТСЯ. `_consumed` монотонен за
        # жизнь процесса и НИКОГДА не обнуляется: раньше `_apply` сбрасывал его
        # на любой принятой лизе, поэтому повтор одной захваченной лизы
        # бесплатно пополнял ёмкость — проверено, `granted` у нас при этом
        # замирал навсегда, а движок показывал `state=active` и ноль ошибок.
        self._granted = 0
        self._consumed = 0
        self._quantum_seq = 0
        self._quantum_size = 0
        self._reserve = 0
        # Порог, на котором пора идти за следующим квантом. Лежит ВНУТРИ
        # резерва, поэтому к моменту исчерпания ёмкость уже пополнена и на пути
        # запроса не появляется ни одного сетевого раунд-трипа.
        self._prefetch_at = 0
        self._ack_trust = ""
        self._capacity_endpoint = ""
        self._report_secret: bytes | None = None
        self._report_seq = 0
        self._report_prev = ""
        # Resolved on first use, not here: `service.py` constructs this client at
        # import time, and a missing verification key must fail the STARTUP of a
        # process, not the IMPORT of the module — otherwise every test and tool
        # that merely imports the app dies with a licensing error.
        self._verify_keys: list[Ed25519PublicKey] | None = None

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
        self._plan: str | None = None
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
        # БУДИЛЬНИК ПЕТЛИ. Раньше исчерпание гранта ждало обычного пробуждения
        # («петля просыпается не реже чем раз в пять секунд»), то есть под
        # нагрузкой каждый квант стоил до пяти секунд простоя у клиента.
        self._wake = threading.Event()
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
        consumed, granted = self.capacity()
        return LicenseStatus(
            state=state,
            consumed=consumed,
            granted=granted,
            capacity_left=None if not granted else max(0, granted - consumed),
            code=self._terminal_code,
            lease_id=self._lease_id,
            bundle_version=self._bundle_version,
            seconds_since_lease=elapsed,
            grace_left_seconds=grace_left,
            last_error=self._last_error,
            plan=self._plan,
            ttl_seconds=self._ttl_seconds,
            renew_after_seconds=self._renew_after_seconds,
            next_renewal_in_seconds=(
                None if elapsed is None or not self._renew_after_seconds
                else max(0.0, self._renew_after_seconds - elapsed)),
        )

    def is_serving(self) -> bool:
        return self.state() in (STATE_LEASED, STATE_STALE) and self.has_capacity()

    def has_capacity(self) -> bool:
        """Осталась ли ёмкость. ОДНО УСЛОВИЕ, И БОЛЬШЕ НИКАКИХ.

        Убраны обе лазейки, и каждая была полным обходом учёта.

        `return self.state() == STATE_STALE` делало НАШ простой источником
        БЕЗЛИМИТНОЙ ёмкости: уронив связь с лицензионным сервером, клиент
        обслуживал сколько угодно весь TTL плюс grace — семьдесят два часа на
        проде, — и грантов за это не записывалось ни одного. Одна строка в
        фаерволе по крону превращала две трети месяца в бесплатный трафик.
        Теперь наш простой покрыт ПРЕДОПЛАЧЕННЫМ резервом, который лежит внутри
        `_granted`: grace сохраняет свой смысл — наш сбой не роняет чужой
        бизнес, — а блэкхол даёт ровно то, что уже оплачено.

        `if not self._granted: return True` делало безлимитом ОТСУТСТВУЮЩЕЕ
        поле, то есть любой сервер старше нас. Это ровно наоборот правилу
        «отсутствие поля — деградация», которое та же функция применяет к
        `recipient` и `report_secret`. Ноль остаётся безлимитом только до
        первого кванта и только для контракта 2.
        """
        with self._lock:
            if not self._granted:
                # НОЛЬ — БЕЗЛИМИТ ТОЛЬКО ДЛЯ СТАРОГО СЕРВЕРА. Иначе это была бы
                # та же лазейка, что убрана выше, через другую дверь: движок
                # взял аренду, наш сервер умер до первого кванта, `_granted`
                # остался нулём — и обслуживание снова стало безлимитным на весь
                # TTL плюс grace. Первый квант покупается в `acquire()`, поэтому
                # для контракта 3 ноль здесь означает «ёмкости ещё нет», а не
                # «ёмкость бесконечна».
                return not self._capacity_endpoint
            return self._consumed < self._granted

    def consume(self, units: int = 1) -> None:
        """Списать ёмкость. Зовётся с пути маскирования, по запросу."""
        with self._lock:
            self._consumed += units
            due = bool(self._prefetch_at) and self._consumed >= self._prefetch_at
        if due:
            self._wake.set()

    def capacity(self) -> tuple[int, int]:
        with self._lock:
            return self._consumed, self._granted

    def _sign_usage(self, usage: dict[str, object]) -> dict[str, object]:
        """Отчёт, СЦЕПЛЕННЫЙ с предыдущим и подписанный.

        `seq` растёт на единицу, `prev` — хеш подписи предыдущего отчёта.
        Выброшенный, переставленный или подменённый старым отчёт виден на нашей
        стороне как разрыв цепи; переписать содержимое в пути нельзя, не имея
        приватной половины, которая никогда не покидает память процесса.
        """
        if self._report_secret is None:
            return usage
        self._report_seq += 1
        signed = dict(usage)
        # МЕРА СБОРКИ ВНУТРИ ПОДПИСАННОГО ТЕЛА. Снаружи её переписал бы любой
        # перехватчик; внутри — только тот, кто уже держит секрет, то есть сам
        # процесс. Это не мешает пропатченному бинарнику соврать о себе, но
        # делает ложь датированной записью у нас.
        signed["build"] = build_measurement()
        signed["seq"] = self._report_seq
        signed["prev"] = self._report_prev
        signed["signature"] = mac_report(signed, self._report_secret)
        self._report_prev = hashlib.sha256(
            signed["signature"].encode("ascii")).hexdigest()
        return signed

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
            usage = self._sign_usage(usage)
            with self._lock:
                self._last_report = usage
                self._last_report_at = time.time()
        nonce = secrets.token_urlsafe(24)
        self._pending_nonce = nonce
        response = self._http.post(
            f"{self._base_url}/v1/lease",
            json={
                "key": self._key,
                "instance_id": self._instance_id,
                "process_id": self._process_id,
                "pubkey": self._process_key.public,
                "engine_version": ENGINE_VERSION,
                "lease_id": self._lease_id,
                "nonce": nonce,
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
        if response.status_code in _GRACE_WORTHY_STATUS and code not in _ANSWER_CODES:
            raise _TransientLeaseError(
                f"licensing server returned {response.status_code} "
                f"({code}: {detail}) for {self._base_url}"
            )
        raise LicenseError(code, f"{detail} (HTTP {response.status_code}, {self._base_url})")

    def _meter_once(self) -> None:
        """Купить следующий квант ёмкости, назвав свой расход.

        ОТЧЁТ ЗДЕСЬ — ЗАЩИТА КЛИЕНТА, А НЕ НАША. Счёт строится на выданном,
        зажатом снизу `granted - Q - R`: подтверждённый расход УМЕНЬШАЕТ его до
        фактического. Поэтому занизить отчёт невыгодно — потолок тут же
        опустится ниже собственного расхода, и движок перестанет обслуживать, —
        а снять его значит отказаться от скидки за неиспользованное.
        """
        with self._lock:
            consumed = self._consumed
        # БЕЗ СЕКРЕТА ЁМКОСТЬ ВСЁ РАВНО ПОКУПАЕТСЯ, ПРОСТО БЕЗ ОТЧЁТА. Ранний
        # выход означал бы, что процесс, потерявший секрет, перестаёт покупать
        # ёмкость и тихо умирает по её исчерпании. Шаг без отчёта СЛЕПОЙ: сервер
        # считает предыдущий квант выбранным целиком, то есть завышает — и это
        # ровно то, что делает молчание невыгодным без единого механизма
        # принуждения.
        ack: dict[str, object] | None = None
        if self._report_secret is not None:
            ack = {"consumed": consumed, "quantum_seq": self._quantum_seq}
            ack["signature"] = mac_report(ack, self._report_secret)
        nonce = secrets.token_urlsafe(24)
        endpoint = self._capacity_endpoint or "/v1/meter"
        response = self._http.post(
            f"{self._base_url}{endpoint}",
            json={"key": self._key, "instance_id": self._instance_id,
                  "pubkey": self._process_key.public, "nonce": nonce, "ack": ack})
        if response.status_code != 200:
            try:
                body = response.json()
                code = str(body.get("error", "license_invalid"))
                detail = str(body.get("detail", ""))
            except ValueError:
                code, detail = "license_invalid", response.text[:200]
            if (response.status_code in _GRACE_WORTHY_STATUS
                    and code not in _ANSWER_CODES):
                raise _TransientLeaseError(
                    f"capacity endpoint returned {response.status_code} "
                    f"({code}: {detail})")
            raise LicenseError(code, f"{detail} (HTTP {response.status_code})")
        self._apply_quantum(response.json(), nonce)

    def _apply_quantum(self, quantum: dict[str, object], nonce: str) -> None:
        if self._verify_keys is None:
            self._verify_keys = [decode_public_key(material)
                                 for material in _public_key_materials()]
        last: BundleError | None = None
        for key in self._verify_keys:
            try:
                verify_lease(quantum, key)
                break
            except BundleError as error:
                last = error
        else:
            raise last or BundleError("capacity grant carries no acceptable signature")
        # ТИП ВНУТРИ ПОДПИСИ. Иначе лизу можно предъявить как квант и наоборот:
        # оба подписаны одним ключом и оба несут `recipient` и `nonce`.
        if quantum.get("kind") != "capacity":
            raise BundleError("this is not a capacity grant")
        if str(quantum.get("recipient", "")) != self._process_key.public:
            raise BundleError(
                "capacity grant was issued to another recipient — someone is "
                "between this process and the licensing server")
        if str(quantum.get("nonce", "")) != nonce:
            raise BundleError("capacity grant answers a different request")
        seq = int(quantum.get("quantum_seq", 0) or 0)
        total = int(quantum.get("grant_total", 0) or 0)
        with self._lock:
            if seq <= self._quantum_seq:
                raise BundleError(
                    f"capacity grant {seq} is older than the accepted "
                    f"{self._quantum_seq} — refusing a replay")
            # ПОТОЛОК ТОЛЬКО РАСТЁТ, и приходит АБСОЛЮТНЫМ числом. Повтор несёт
            # меньшее значение и становится no-op сам по себе.
            self._granted = max(self._granted, total)
            self._quantum_seq = seq
            self._quantum_size = int(quantum.get("quantum_size", 0) or 0)
            self._reserve = int(quantum.get("reserve", 0) or 0)
            self._prefetch_at = int(quantum.get("prefetch_at", 0) or 0)
            self._ack_trust = str(quantum.get("ack_trust", ""))
        _log.info("capacity grant %d: +%d (reserve %d), ceiling %d, consumed %d",
                  seq, self._quantum_size, self._reserve, self._granted,
                  self._consumed)

    def _apply(self, lease: dict[str, object]) -> None:
        if self._verify_keys is None:
            self._verify_keys = [decode_public_key(material)
                                 for material in _public_key_materials()]
        last: BundleError | None = None
        for key in self._verify_keys:
            try:
                verify_lease(lease, key)
                break
            except BundleError as error:
                last = error
        else:
            raise last or BundleError("lease carries no acceptable signature")
        # ЛИЗА ВЫПИСАНА НЕ НАМ — ЗНАЧИТ В КАНАЛЕ КТО-ТО ЕСТЬ. `recipient` под
        # подписью, подделать нельзя; если он не наш, кто-то подменил наш
        # открытый ключ по дороге, чтобы прочитать бандл и наши отчёты.
        # ПОЛЕ ОБЯЗАТЕЛЬНО, А НЕ «ЕСЛИ ЕСТЬ». Мягкая проверка давала даунгрейд:
        # лиза, выписанная ДО этой правки, имеет валидную подпись и не имеет
        # `recipient`, поэтому её повтор отключал сверку целиком — и вместе с
        # ней MAC отчётов, потому что секрета в такой лизе тоже нет. Отсутствие
        # поля означает либо старый сервер, либо повтор; оба случая — отказ.
        # ЭХО НОНСА. Проверка свежести по `issued_at` осталась вторым рубежом,
        # но перестала быть единственным: часы контейнера чужие, а окно
        # `ttl + skew` на проде — двадцать пять часов, в которые захваченная
        # лиза принималась как своя.
        echoed = str(lease.get("nonce", ""))
        if not echoed:
            raise BundleError(
                "lease echoes no nonce: this engine needs lease contract 3 "
                "(GET /v1/pubkey reports the server's). Either the licensing "
                "server is older than this engine — deploy it FIRST — or an old "
                "lease is being replayed")
        if echoed != self._pending_nonce:
            raise BundleError(
                "lease answers a different request — it is a replay, or someone "
                "is between this process and the licensing server")
        recipient = str(lease.get("recipient", ""))
        if not recipient:
            raise BundleError(
                "lease names no recipient: this engine needs lease contract 2 "
                "(GET /v1/pubkey reports the server's). Either the licensing "
                "server is older than this engine — deploy it FIRST — or an old "
                "lease is being replayed"
            )
        if recipient != self._process_key.public:
            raise BundleError(
                "lease was issued to another recipient — someone is between this "
                "process and the licensing server"
            )
        # СВЕЖЕСТЬ. Повтор ЛЮБОЙ старой лизы — не только доправочной — иначе
        # остаётся способом вернуть отозванный бандл к жизни. Окно щедрое:
        # часы контейнера и наши могут разъехаться, а лиза и так живёт TTL.
        issued_at = lease.get("issued_at")
        ttl = int(lease.get("ttl_seconds", 0) or 0)
        if not isinstance(issued_at, (int, float)) or not ttl:
            raise BundleError("lease carries no issue time or lifetime")
        age = time.time() - float(issued_at)
        if age > ttl + _CLOCK_SKEW_SECONDS:
            raise BundleError(
                f"lease is {int(age)}s old, past its {ttl}s lifetime — refusing "
                f"a replayed lease")
        inner = open_sealed(str(lease["bundle"]), self._process_key)
        # КОНТРАКТ 3: снять внутренний слой ключом из НОНСА, который сгенерировал
        # ЭТОТ процесс для ЭТОГО запроса. Повтор старой/чужой аренды не
        # расшифруется — ветки, которую можно инвертировать, здесь нет: нонс это
        # ключ. `self._pending_nonce`, а не эхо из ответа: иначе патчер просто
        # скормил бы старый нонс из захваченной аренды.
        plaintext = (nonce_unwrap(inner, self._pending_nonce)
                     if lease.get("capacity") else inner)
        actual = plaintext_hash(plaintext)
        expected = str(lease["bundle_sha256"])
        if actual != expected:
            raise BundleError(
                f"bundle hash mismatch: signed {expected[:16]}, got {actual[:16]} — "
                f"the contents are not what was signed"
            )
        # ТОЖЕ ОБЯЗАТЕЛЬНО, И ХЕШ ТОЖЕ. Без секрета отчёты уходят без MAC, а
        # это ровно то состояние, ради выхода из которого он и заведён.
        sealed_secret = lease.get("report_secret")
        if not isinstance(sealed_secret, str) or not sealed_secret:
            raise BundleError("lease carries no report secret")
        secret = open_sealed(sealed_secret, self._process_key)
        expected = str(lease.get("report_secret_sha256", ""))
        if not expected or hashlib.sha256(secret).hexdigest() != expected:
            raise BundleError("report secret does not match its signed hash")
        self._report_secret = secret
        capacity = lease.get("capacity")
        if isinstance(capacity, dict):
            self._capacity_endpoint = str(capacity.get("endpoint", "/v1/meter"))
        ASSETS.load(plaintext)
        with self._lock:
            self._last_ok_monotonic = time.monotonic()
            self._ttl_seconds = int(lease["ttl_seconds"])
            self._grace_seconds = int(lease["grace_seconds"])
            self._renew_after_seconds = int(lease["renew_after_seconds"])
            self._lease_id = str(lease["lease_id"])
            self._bundle_version = str(lease["bundle_version"])
            self._plan = str(lease.get("plan") or "") or None
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
                # ПЕРВЫЙ КВАНТ ПОКУПАЕТСЯ НА СТАРТЕ, а не на первом тике петли.
                # Иначе между арендой и первым квантом остаётся окно, в котором
                # `_granted` равен нулю; а холодный старт и так не имеет grace —
                # процесс без ёмкости не может деградировать, ему нечем.
                if self._capacity_endpoint:
                    self._meter_once()
                _log.info("lease acquired: %s bundle=%s ttl=%ss grace=%ss "
                          "capacity=%d",
                          self._lease_id, self._bundle_version,
                          self._ttl_seconds, self._grace_seconds, self._granted)
                return
            except (_TransientLeaseError, httpx.HTTPError) as error:
                last_transient = error
                _log.warning("lease attempt %d/%d failed: %s",
                             attempt, _STARTUP_ATTEMPTS, error)
                if attempt < _STARTUP_ATTEMPTS:
                    time.sleep(_STARTUP_BACKOFF_SECONDS * attempt)
            except BundleError as error:
                raise LicenseError("bundle_corrupt", str(error)) from error
        # NAME THE HOST. «[Errno -2] Name or service not known» without it tells
        # the customer nothing: they cannot put it in a firewall rule, cannot
        # search for it, and cannot see that the container is dialling the
        # production address because this deployment never overrode it. Three
        # personas hit exactly that and all three ended up grepping inside the
        # image for the variable name.
        raise LicenseError(
            "bundle_unavailable",
            f"licensing server {self._base_url} unreachable after "
            f"{_STARTUP_ATTEMPTS} attempts: {last_transient}",
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

    def _quantum_due(self) -> bool:
        with self._lock:
            if not self._quantum_seq:
                return True
            return self._consumed >= self._prefetch_at

    def _meter_step(self) -> None:
        """Обёртка вокруг покупки кванта с той же классификацией отказов, что и
        у продления: ответ — терминальный, сбой — в долг из резерва."""
        try:
            self._meter_once()
            if self._terminal_code is not None:
                _log.info("capacity restored (was %s)", self._terminal_code)
                self._terminal_code = None
        except LicenseError as error:
            self._terminal_code = error.code
            self._record_error(error.detail)
            _log.error("capacity refused (%s): %s", error.code, error.detail)
            self._expire()
        except (_TransientLeaseError, httpx.HTTPError, BundleError) as error:
            self._record_error(str(error))
            _log.warning("capacity top-up failed, running on the reserve: %s", error)

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
                # ЁМКОСТЬ И АРЕНДА ПОКУПАЮТСЯ ОТДЕЛЬНО. Аренда тяжёлая (бандл
                # пересобирается и заново шифруется, около двух мегабайт) и
                # редкая; квант лёгкий и частый. Пересобирать бандл на каждый
                # квант нельзя — это была бы наша собственная DoS-атака.
                if self._capacity_endpoint and self._quantum_due():
                    self._meter_step()
                if last_attempt is None or (
                        time.monotonic() - last_attempt >= due):
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
            self._wake.wait(min(5.0, max(1.0, due / 4.0)))
            self._wake.clear()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="pseudex-license",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        # Иначе `join` ждёт полный таймаут вместо мгновенной остановки.
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._release()
        self._http.close()

    def _release(self) -> None:
        """Tell the server this instance is going away, so its slot frees now.

        Best effort, and short: a shutdown must not hang because our own server
        is slow, and the time-based expiry covers every case where this call
        does not arrive — a kill -9, a lost network, a crashed host. Without it
        the slot lingers for the whole lease TTL, and on a one-instance plan a
        redeploy means the customer cannot start their own container.
        """
        if not self._key or self._lease_id is None:
            return
        try:
            self._http.post(f"{self._base_url}/v1/release", timeout=3.0,
                            json={"key": self._key,
                                  "instance_id": self._instance_id,
                                  "pubkey": self._process_key.public})
        except Exception as error:  # noqa: BLE001 - shutdown must not raise
            _log.info("could not release the instance slot: %s", error)


class _TransientLeaseError(RuntimeError):
    """A failure plausibly on our side — grace applies."""
