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
import random
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path

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

def _engine_version() -> str:
    """The version this build IS, from one source (D-053).

    A released image carries it in the generated `pseudex/_release.py` next to
    the verification key; a dev checkout reads `prototype/version.txt`. It used
    to be a constant here that said "1.0.0" to the licence server and the
    operator for every image ever shipped — so the server compared its minimum
    against a number nobody had set, and the fleet histogram was one bar.
    """
    try:
        from pseudex import _release  # noqa: PLC0415  (optional, generated at build)
        version = str(getattr(_release, "ENGINE_VERSION", "")).strip()
        if version:
            return version
    except ImportError:
        pass
    version_file = Path(__file__).resolve().parent.parent / "version.txt"
    if version_file.exists():
        version = version_file.read_text(encoding="utf-8").strip()
        if version:
            return version
    return "0.0.0-dev"


ENGINE_VERSION = _engine_version()

# ЧТО ЭТОТ ДВИЖОК УМЕЕТ, НАЗВАНО ЯВНО (D-063, D-064). `lease_contract` едет в
# запросе, чтобы сервер знал, какой формы ответ этот клиент прочтёт: сегодня 3
# (эхо нонса, ёмкость на /v1/meter); несовместимое изменение станет 4, и
# старым клиентам сервер продолжит отдавать 3, пока тот поддерживается.
# `bundle_format` — формат содержимого бандла (2 = секционный фрейм); ответ с
# большим числом отвергается как «обновите движок», а не как «бандл повреждён»
# — это разные диагнозы с разными действиями.
LEASE_CONTRACT = 3
SUPPORTED_BUNDLE_FORMAT = 2

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

# ФЕНСИНГ: МЕСТО ЭТОГО ЗАПУСКА ЗАНЯЛ БОЛЕЕ НОВЫЙ ЗАПУСК ТОГО ЖЕ ТАРИФА.
#
# Приходит с `/v1/meter` как 409 с этим кодом, и намеренно НЕ добавлен в
# `_ANSWER_CODES`: весь выпущенный флот читает 409 вне этого множества как наш
# временный сбой и доцеживает купленную полосу. Новый движок обязан вести себя
# не хуже — отказ в НОВОЙ ёмкости не гасит процесс, гасит его обычная
# `has_capacity()`.
FENCED = "fenced"

# ОТКАЗ В ЁМКОСТИ ПО ПОТОЛКУ — НЕ ОТВЕТ О ПОДПИСКЕ, И ЭТО РАЗНЫЕ ДЕЙСТВИЯ (Б30).
#
# Сервер обещал в комментарии, что упёршийся в потолок процесс доживает на уже
# купленном кванте, а клиент на том же ответе звал `_expire()`: бандл
# выгружался, `/mask` отдавал 503 в ту же секунду, и оплаченный остаток сгорал.
# Обещание и поведение разошлись ровно потому, что обе причины отказа —
# «мест больше нет» и «не оплачено» — приземлялись в одну ветку.
#
# Здесь они разведены по СМЫСЛУ, а не по коду ответа: потолок означает «больше
# не покупаю», неоплата означает «больше не обслуживаю». `instance_limit`
# остаётся в списке ради СТАРОГО сервера — новый его на ёмкости не выдаёт.
_CEILING_CODES = frozenset({FENCED, "instance_limit"})

# ПЕРЕЗАЯВКА ОТФЕНСЕННОГО ПОКОЛЕНИЯ. Джиттер — чтобы N воркеров одного старта
# не пришли за арендой в одну миллисекунду; час — пол, ниже которого два живых
# контейнера на одном слоте перезаявляли бы друг друга вечно (шторм аренд по
# два мегабайта). Час — ВЫБОР ТЗ, не замер.
_RECLAIM_JITTER_SECONDS = 10.0
_RECLAIM_MIN_INTERVAL_SECONDS = 3600.0
# ПОЛ ДЛЯ ТЁМНОГО ПРОЦЕССА — ДРУГОЙ, И РАЗНИЦА НЕ КОСМЕТИЧЕСКАЯ. Часовой пол
# заведён против ДВУХ ОБСЛУЖИВАЮЩИХ контейнеров, перезаявляющих друг друга;
# процесс, у которого полоса кончилась, не обслуживает вовсе — он уже отдаёт
# 503, и час такой темноты и есть та самая «остановка второго контейнера»,
# которую вариант А §6.1 обещает не делать («перезаявляет СРАЗУ при исчерпании
# полосы»). Минута — выбор, не замер: она ограничивает шторм двумя арендами в
# минуту на тёмный контейнер и держит темноту в пределах минуты.
_RECLAIM_DARK_SECONDS = 60.0
# Попытка, не дошедшая до сервера, перезаявку НЕ тратит (иначе секунда без сети
# в момент перезаявки стоит часа темноты), но и повторять её каждый тик нельзя.
_RECLAIM_RETRY_SECONDS = 60.0

_STARTUP_ATTEMPTS = 3
_STARTUP_BACKOFF_SECONDS = 2.0

# How often a REVOKED or UNPAID licence re-asks. Slower than a normal renewal —
# the answer is unlikely to change minute to minute — but never never: a customer
# who pays their invoice must come back without restarting every container.
_TERMINAL_RETRY_SECONDS = 60.0
# Каждый процесс продлевается на 80–100% интервала — свой случайный сдвиг
# рассыпает синхронный флот по окну (см. _loop).
_RENEW_JITTER = 0.2


def _roll_renew_jitter() -> float:
    """Множитель порога продления в [1 - _RENEW_JITTER, 1.0). Только ВНИЗ —
    продлеваем не ПОЗЖЕ намеченного, никогда не рискуя уехать в STALE."""
    return 1.0 - random.random() * _RENEW_JITTER

# ОТЧЁТ О РАСХОДЕ — СВОИМ ТАЙМЕРОМ, А НЕ НА ПРОДЛЕНИИ АРЕНДЫ.
#
# Продление считается от TTL (`renew_after_seconds = TTL // 3`, то есть раз в
# восемь часов при суточной аренде) и отвечает на вопрос «жива ли лицензия».
# Расход к этому вопросу отношения не имеет, а был к нему привязан: счётчики
# уезжали вместе с продлением. Следствия измеримы и оба плохие — кабинет
# отставал на восемь часов, а контейнер, проживший меньше восьми, не
# отчитывался ВООБЩЕ, и клиент платил по ВЫДАННОЙ ёмкости (200 запросов), а не
# по фактическому расходу (семь).
#
# Эндпоинт `/v1/usage` существует ровно для этого, и в его же докстринге
# написано: «Normally counters ride on /v1/lease; this exists for a client that
# wants to report before its renewal is due». Не хватало только вызова.
#
# Две минуты — потому что отчёт КУМУЛЯТИВНЫЙ: потерянный исправляется
# следующим, значит частые отправки дёшевы и безопасны, а редкие стоят клиенту
# неверной цифры в кабинете. Стоимость — один лёгкий POST на контейнер.
_USAGE_REPORT_SECONDS = float(os.environ.get("PSEUDEX_USAGE_REPORT_SECONDS", "120"))

# What to DO about each terminal code. A persona following the documented
# `docker run` hit an unreachable licensing host and got a bare Python traceback
# — the gateway refused to serve, exactly as designed, and told them nothing
# about why or what to try. Fail-closed without a diagnosis reads as "broken",
# and the customer's next move is to close the tab rather than open the firewall.
# КУДА ИДТИ ЗА КЛЮЧОМ. Отдельной константой, потому что это единственный адрес,
# который человек видит, когда у него ещё НЕТ ни ключа, ни кабинета, ни нас в
# закладках: он запустил образ, прочитал имя продукта где-то и попробовал.
# Переопределяется на случай собственной инсталляции у крупного заказчика.
SITE_URL = os.environ.get("PSEUDEX_SITE_URL", "https://pseudex.ru").rstrip("/")

REMEDIES: dict[str, str] = {
    "license_missing":
        "Переменная PSEUDEX_LICENSE_KEY не задана.\n"
        f"    Ключ выпускается бесплатно, карта не нужна: {SITE_URL}\n"
        "    Если ключ уже был и потерялся — он показывается один раз, "
        f"выпустите новый в кабинете: {SITE_URL}/app/",
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
    "license_capped":
        "Достигнут глобальный потолок объёма запросов по тарифу — это не "
        "отзыв ключа. Обслуживание возобновится само в новом периоде; чтобы "
        "снять потолок раньше, перейдите на старший тариф в кабинете "
        f"({SITE_URL}/app/). Ключ перевыпускать НЕ нужно.",
    "bundle_corrupt":
        "Полученный пакет не прошёл проверку подписи. Это не чинится настройками "
        "— напишите нам, приложив вывод контейнера.",
    "capacity_exhausted":
        "Предоплаченная ёмкость израсходована, а лицензионный сервер сейчас "
        "недоступен, поэтому взять следующую невозможно. Проверьте исходящий "
        "доступ к нему по HTTPS — как только связь вернётся, обслуживание "
        "продолжится само, без перезапуска контейнера.",
    # ОСТАЁТСЯ РАДИ СТАРЫХ СЕРВЕРОВ, И БЕЗ СЛОВА «ЛИШНИЕ». Совет остановить
    # лишний контейнер стоил шести заходов подряд: сервер называл лишним тот,
    # чьё молчание он не сумел отличить от смерти, и оператор шёл останавливать
    # то, чего нет. Новый сервер этот код на ёмкости не выдаёт вовсе.
    "instance_limit":
        "Сервер лицензий считает, что по тарифу работает больше контейнеров, "
        "чем оплачено. Если это переразвёртывание — ничего делать не нужно, "
        f"оно доработает само. Иначе смените тариф: {SITE_URL}/app/",
    # ФЕНСИНГ. Текст без «поколения N с HH:MM» — их подставляет
    # `explain_fenced`, когда сервер их назвал; фраза, которой нет, лучше
    # фразы «поколение None».
    FENCED:
        "Место этого запуска занял более новый запуск того же тарифа. Этот "
        "контейнер доработает на уже купленной ёмкости и остановится сам. Если "
        "это переразвёртывание — ничего делать не нужно. Если контейнеров "
        "действительно больше, чем по тарифу, — остановите один или смените "
        f"тариф: {SITE_URL}/app/",
    # ВЕРДИКТ ПО ВЕРСИИ, НЕ СБОЙ (D-055, D-056). Сервер отвечает 426 только
    # циклу, закрытие которого объявлено за 90 дней; до этого он предупреждал
    # на каждом продлении. Grace здесь не применяется, как и к 402/403.
    "unsupported_client":
        "Эта версия движка больше не обслуживается — цикл закрыт по объявленному "
        "заранее сроку. Обновитесь до поддерживаемой:\n"
        "    pseudexctl upgrade\n"
        "Том с данными сохраняется; какая версия минимальная и какая новейшая — "
        "в тексте ответа выше.",
    "bundle_format_unsupported":
        "Сервер лицензий выдал бандл в формате новее, чем понимает этот движок. "
        "Это не порча и не подмена — нужен более новый образ:\n"
        "    pseudexctl upgrade",
}


def explain(code: str) -> str:
    """The operator-facing remedy for a terminal licence code."""
    return REMEDIES.get(code, "Напишите нам, приложив вывод контейнера.")


def explain_fenced(fenced: dict[str, object] | None) -> str:
    """Тот же текст, но с поколением и временем, когда сервер их назвал.

    ОДНА ФРАЗА, А НЕ ДВЕ. Соблазн — второй статический текст «без подробностей»;
    цена — два места, где одна и та же ситуация описана по-разному, и оператор,
    сверяющий экран с логом, читает их как две разные беды.
    """
    text = REMEDIES[FENCED]
    if not fenced:
        return text
    epoch = fenced.get("current_epoch")
    since = fenced.get("holder_since")
    if not isinstance(epoch, int):
        return text
    when = (f", с {time.strftime('%H:%M', time.localtime(since))}"
            if isinstance(since, (int, float)) and since else "")
    return text.replace("того же тарифа.",
                        f"того же тарифа (поколение {epoch}{when}).", 1)


def should_reclaim(scheduled_at: float | None, last_reclaim_at: float | None,
                   last_attempt_at: float | None, band_left: int,
                   now: float) -> bool:
    """ПРАВИЛО ДОПУСКА ПЕРЕЗАЯВКИ — ОДНА ФУНКЦИЯ, ПОТОМУ ЧТО ЭТО РАЗВИЛКА.

    Развилка §6.1 ТЗ решается владельцем, и её цена уже посчитана; код обязан
    дать сменить ответ заменой ОДНОЙ функции, а не правкой петли.

      * ВАРИАНТ А (здесь, по умолчанию): «N это упаковка, параллелизм
        бесплатен, объём оплачен». Отфенсенное поколение перезаявляет слот
        по расписанию (одна немедленная попытка с джиттером) И при исчерпании
        купленной полосы — второе условие и есть режим «по исчерпанию»;
      * ВАРИАНТ Б: то же, но без второго условия — тогда отфенсенный после
        исчерпания темнеет до обычного продления (до восьми часов). Включается
        удалением `band_left <= 0` и больше ничем;
      * ВАРИАНТ В (порог против ЧУЖОЙ установки) — решение СЕРВЕРА, здесь его
        нет по построению: клиент не знает, чья установка держит слот.

    ПОЛ ЗАВИСИТ ОТ ТОГО, ОБСЛУЖИВАЕТ ЛИ ПРОЦЕСС. Час заведён против двух
    ЖИВЫХ контейнеров, перезаявляющих друг друга непрерывно, — это шторм аренд
    по два мегабайта. Процесс с исчерпанной полосой не обслуживает ничего: он
    уже отдаёт 503, и держать его в темноте час — это поведение варианта Б,
    выданное за вариант А. Поэтому тёмный ждёт минуту, а не час. Сервер ни того
    ни другого не принуждает — он СЧИТАЕТ возвраты (аномалия на поколении,
    вернувшемся дважды), и в этом вся разница между наблюдением и таймером.

    ПОПЫТКА, НЕ ДОШЕДШАЯ ДО СЕРВЕРА, ПЕРЕЗАЯВКУ НЕ ТРАТИТ. `_reclaim_step`
    ставил отметку ДО запроса, а `_renew` глотает сетевой сбой как временный:
    секунда без связи ровно в момент перезаявки стоила часа темноты — в том
    числе живому соседу, ошибочно вытесненному ранжированием, ради которого
    перезаявка и заведена. Поэтому отметок две: попытка и удавшийся возврат.
    """
    due = (scheduled_at is not None and now >= scheduled_at) or band_left <= 0
    if not due:
        return False
    if (last_attempt_at is not None
            and now - last_attempt_at < _RECLAIM_RETRY_SECONDS):
        return False
    if last_reclaim_at is None:
        return True
    floor = (_RECLAIM_DARK_SECONDS if band_left <= 0
             else _RECLAIM_MIN_INTERVAL_SECONDS)
    return now - last_reclaim_at >= floor


def _process_start_ticks(pid: int) -> str:
    """Момент старта процесса в тиках (поле 22 `/proc/<pid>/stat`).

    Нужен, потому что PID переиспользуются: без него два разных запуска, которым
    ядро выдало один номер, дали бы один `start_id` — то есть одно поколение на
    два контейнера. Поля считаются ПОСЛЕ последней закрывающей скобки: `comm`
    лежит в скобках и может содержать и пробелы, и сами скобки, поэтому
    `split()[21]` промахивается на любом процессе с нестандартным именем.
    """
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    return stat[stat.rindex(")") + 2:].split()[19]


def start_id(instance_id: str) -> str:
    """КАКОЙ СТАРТ КОНТЕЙНЕРА ЭТО. Один старт — одно поколение — один эпох.

    `entrypoint.sh` чеканит `PSEUDEX_START_ID` ОДИН РАЗ до фан-аута, ровно там
    же и по той же причине, что `PSEUDEX_ADMIN_TOKEN` и `PSEUDEX_GATEWAY_TOKEN`:
    N воркеров с N значениями на один порт — это N истин.

    СЛУЧАЙНОЕ ЗНАЧЕНИЕ НА ПРОЦЕСС ЗДЕСЬ ЗАПРЕЩЕНО, и это не стилистика. На
    тарифе в один слот N воркеров стали бы N поколениями на этом слоте и
    отфенсили бы друг друга на покупке ёмкости: контейнер сломан по построению,
    причём тем сильнее, чем больше воркеров у клиента. Поэтому форма поставки Б
    (`uvicorn pseudex.service:app` без entrypoint, она через скрипт не проходит)
    выводит значение ДЕТЕРМИНИРОВАННО для всех воркеров одного запуска:
    установка плюс загрузка ядра плюс родитель плюс момент его старта — у
    `uvicorn --workers N` родитель один.

    На macOS `/proc` нет, поэтому там значение случайное и с предупреждением:
    это машина разработчика, а в образе всегда Linux.
    """
    declared = os.environ.get("PSEUDEX_START_ID", "").strip()
    if declared:
        return declared[:128]
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="utf-8").strip()
        parent = os.getppid()
        material = f"{instance_id}\x1f{boot_id}\x1f{parent}\x1f" \
                   f"{_process_start_ticks(parent)}"
    except OSError:
        _log.warning(
            "PSEUDEX_START_ID is unset and this is not Linux: falling back to a "
            "random per-process value. In a container entrypoint.sh mints one "
            "for every worker; here each worker is its own generation")
        return "dev:" + secrets.token_hex(8)
    return "derived:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


class BundleFormatError(BundleError):
    """The lease is genuine and ours, and its bundle is in a format this build
    cannot read. A `BundleError` for the renewal loop — the leased assets stay
    loaded and grace applies, because the mismatch is OUR deployment order,
    not the customer's fault — and a distinct code at startup, where there is
    nothing to fall back on and the remedy is an upgrade, not a support ticket."""


class LicenseError(RuntimeError):
    """The process may not run: no valid lease could be obtained at startup."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Fenced:
    """Кто занял место этого запуска — со слов сервера, дословно.

    Отдельной записью, а не тремя полями на клиенте: «отфенсен» — это ОДНО
    событие с одним временем, и половина его полей на экране без остальных
    означала бы, что оператор видит номер поколения, но не видит, чей он.
    """
    slot_no: int | None
    epoch: int | None
    current_epoch: int | None
    holder_start_id: str | None
    holder_since: float | None
    detail: str
    since: float

    def as_dict(self) -> dict[str, object]:
        return {"slot_no": self.slot_no, "epoch": self.epoch,
                "current_epoch": self.current_epoch,
                "holder_start_id": self.holder_start_id,
                "holder_since": self.holder_since,
                "detail": self.detail, "since": self.since}


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
    # ВЕРДИКТ ПО ВЕРСИИ ИЗ ПОСЛЕДНЕЙ АРЕНДЫ (D-055). Всё из подписанного блока
    # `version`; `None` — сервер его не прислал (нет реестра или сервер старше
    # этого движка), и тогда экран говорит «неизвестно», а не «новейшая».
    # Даты — unix-секунды: клиент разбирает `@unix` и HTTP-date один раз, и ни
    # интерфейс, ни CLI не парсят RFC-формы заново.
    engine_version: str
    running_latest: bool | None
    latest: str | None
    latest_in_cycle: str | None
    min_supported: str | None
    deprecated_at: float | None
    sunset_at: float | None
    notice: dict[str, str] | None
    # Every cycle the registry lists — cycle, state by the dates, latest,
    # release_date, eol — for the «Версии» screen. None when the server said nothing.
    cycles: list[dict[str, str | None]] | None
    # МЕСТО И ПОКОЛЕНИЕ ИЗ ПОСЛЕДНЕЙ АРЕНДЫ. `None` — сервер их не назвал
    # (старше этого движка), и экран обязан сказать «неизвестно», а не «слот 1»:
    # требовать поля значило бы вставать из-за порядка выкатки, а это ровно тот
    # дефект, который однажды уже стоил нам простоя (`recipient`).
    start_id: str
    slot_no: int | None
    epoch: int | None
    slot_count: int | None
    # Кто занял место — пока занял. `None` — не отфенсен.
    fenced: dict[str, object] | None


def block_code(status: LicenseStatus) -> str:
    """ЧТО ИМЕННО ОТВЕЧАЕТ 503 — ОДНО РЕШЕНИЕ НА ОБА ПЛЕЧА.

    Сайдкар и прокси печатают этот код и лечение по нему; две копии одного
    условия разъехались бы на первой же правке, и оператор получил бы два
    разных диагноза одной беды в зависимости от формы поставки.

    `fenced` — НЕ `capacity_exhausted`, хотя кончилось в обоих случаях одно и то
    же. Диагноз разный: во втором связи с нами нет и надо чинить сеть, в первом
    связь есть, и это переразвёртывание либо лишний контейнер. Значит и действие
    разное, а одинаковое слово отправило бы оператора чинить работающее.
    """
    if status.code is not None:
        return status.code
    # ПОРЯДОК — ЭТО И ЕСТЬ ДИАГНОЗ. Сюда попадают только те, кто НЕ обслуживает:
    # сначала мёртвая аренда (её чинит оплата или связь), потом кончившаяся
    # ёмкость, и лишь у неё бывает вкус «место занял более новый запуск».
    # `capacity_left` здесь не годится первым: у процесса, отфенсенного до
    # первой покупки, `granted` равен нулю, и он читался бы как «лицензия
    # истекла» — диагноз, к которому происходящее не имеет отношения.
    if status.state == STATE_EXPIRED:
        return "license_expired"
    if status.fenced is not None:
        return FENCED
    return "capacity_exhausted"


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


def _parse_verdict(block: object) -> dict[str, object] | None:
    """The signed `version` block → one dict with unix dates, or None when the
    server sent none. Wire forms are RFC 9745 `@unix` for `deprecated_at` and
    RFC 8594 HTTP-date for `sunset_at`; a form we cannot read is dropped, not
    guessed — a wrong date on the operator's screen is worse than no date."""
    if not isinstance(block, dict):
        return None
    parsed: dict[str, object] = {}
    for name in ("running_latest", "latest", "latest_in_cycle", "min_supported"):
        parsed[name] = block.get(name)
    parsed["deprecated_at"] = _unix_from_at(block.get("deprecated_at"))
    parsed["sunset_at"] = _unix_from_http_date(block.get("sunset_at"))
    notice = block.get("notice")
    parsed["notice"] = ({str(k): str(v) for k, v in notice.items()}
                        if isinstance(notice, dict) else None)
    cycles = block.get("cycles")
    parsed["cycles"] = ([{str(k): (None if v is None else str(v)) for k, v in c.items()}
                         for c in cycles if isinstance(c, dict)]
                        if isinstance(cycles, list) else None)
    return parsed


def _unix_from_at(value: object) -> float | None:
    if isinstance(value, str) and value.startswith("@"):
        try:
            return float(value[1:])
        except ValueError:
            return None
    return None


def _unix_from_http_date(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return parsedate_to_datetime(value).timestamp()
    except (ValueError, TypeError):
        return None


def _int_field(value: object) -> int | None:
    """Целое с провода, или None. `bool` исключён явно: в Python он подкласс
    `int`, и `True` тихо прошёл бы как слот номер один."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _verdict_field(verdict: dict[str, object] | None, name: str, kind: type):
    if verdict is None:
        return None
    value = verdict.get(name)
    return value if isinstance(value, kind) else None


def _iso(stamp: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(stamp))


def _cycle_of(version: str) -> str:
    return ".".join(version.split(".")[:2])


class LicenseClient:
    """Connector to the licensing server (external state -> class)."""

    def __init__(self, base_url: str, key: str, instance_id: str, ca_path: str,
                 usage_provider: Callable[[], dict[str, object]]) -> None:
        self._base_url = base_url.rstrip("/")
        self._key = key
        self._instance_id = instance_id
        self._process_id = f"{instance_id}-{os.getpid()}"
        # СТАРТ КОНТЕЙНЕРА, ОДИН НА ВСЕХ ВОРКЕРОВ (см. `start_id`). Считается
        # один раз здесь, а не на каждой аренде: значение обязано быть
        # одинаковым у всех продлений этого процесса, иначе каждое продление
        # заводило бы новое поколение на слоте и фенсило само себя.
        self._start_id = start_id(instance_id)
        # СЛОТ И ПОКОЛЕНИЕ — ИЗ ПОСЛЕДНЕЙ УСПЕШНОЙ АРЕНДЫ, В ПАМЯТИ.
        #
        # Не на томе, и это не экономия. Эпох чеканит сервер и помнит durable
        # (иначе фенсинг небезопасен); у клиента это ТОКЕН, который он предъявляет
        # обратно. Сохранённый на томе, он пережил бы перезапуск и был бы предъявлен
        # ПОСЛЕ того, как новая аренда выдала следующий номер, — то есть контейнер
        # фенсил бы сам себя своим же прошлым запуском. Переживать перезапуск обязана
        # УСТАНОВКА (`installation_id` в томе), а не поколение.
        self._slot_no: int | None = None
        self._epoch: int | None = None
        self._slot_count: int | None = None
        # Состояние FENCED и его перезаявка (§3.6 ТЗ).
        self._fenced: Fenced | None = None
        self._reclaim_at: float | None = None
        self._last_reclaim_monotonic: float | None = None
        self._last_reclaim_attempt_monotonic: float | None = None
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
        # Wall time of the last good lease — an anti-freeze ceiling on the
        # monotonic timer below (see `state`). Monotonic stays primary; this is
        # only consulted to catch a frozen CLOCK_MONOTONIC.
        self._last_ok_wall: float | None = None
        # When we last TRIED, as opposed to when we last succeeded. Retry pacing
        # has to key off the attempt: pacing off the last success would retry on
        # every tick once a lease has gone stale.
        self._last_attempt_monotonic: float | None = None
        # Когда последний раз УЕХАЛ РАСХОД — отдельно от аренды.
        self._last_usage_monotonic: float | None = None
        self._ttl_seconds = 0
        self._grace_seconds = 0
        self._renew_after_seconds = 0
        self._renew_jitter = _roll_renew_jitter()
        self._lease_id: str | None = None
        self._bundle_version: str | None = None
        self._plan: str | None = None
        self._terminal_code: str | None = None
        self._last_error: str | None = None
        # Блок `version` последней аренды, уже разобранный (даты в unix).
        # Заменяется целиком на каждом продлении, поэтому уведомление,
        # исчезнувшее из ответа, исчезает и отсюда — отзыв отсутствием (D-055).
        self._verdict: dict[str, object] | None = None
        # Что уже сказано в лог: «есть новее X» — раз на X, уведомление — раз
        # на его id. Устаревание повторяется на каждом продлении намеренно.
        self._announced_latest: str | None = None
        self._announced_notices: set[str] = set()
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
        # ANTI-FREEZE. The wall clock is an upper-bound sanity check on the
        # monotonic timer. A root customer who LD_PRELOADs a frozen
        # CLOCK_MONOTONIC keeps `elapsed` pinned below the TTL and serves past
        # revocation (pentest W2-PATCH); but that attack leaves the wall clock
        # moving, so if the wall says this lease is already past ttl+grace while
        # monotonic pretends it is fresh, we trust the wall and fail closed.
        # Monotonic stays PRIMARY (it cannot be rolled back, which the wall can),
        # so the wall is only ever a ceiling: an NTP step is seconds and never
        # trips it, and a suspend longer than the whole grace window would have
        # expired the lease anyway. Freezing BOTH clocks consistently evades this
        # — a far higher bar than the one-line monotonic freeze it closes.
        # KNOWN EDGE (accepted): a container that booted with a wildly-past clock,
        # leased then, and got a LARGE forward NTP correction (> ttl+grace+skew ≈ 3
        # days) before its next renewal would false-EXPIRE here. Rare (needs a
        # multi-day boot-time jump inside one renewal window ≈ ttl/3), it fails
        # CLOSED not open, and it self-heals: the next renewal re-stamps
        # `_last_ok_wall` with the corrected clock, and a restart re-leases. Widening
        # the skew to cover it would weaken the freeze detection it exists for.
        if self._last_ok_wall is not None:
            wall_elapsed = time.time() - self._last_ok_wall
            if wall_elapsed > self._ttl_seconds + self._grace_seconds + _CLOCK_SKEW_SECONDS:
                return STATE_EXPIRED
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
            engine_version=ENGINE_VERSION,
            running_latest=_verdict_field(self._verdict, "running_latest", bool),
            latest=_verdict_field(self._verdict, "latest", str),
            latest_in_cycle=_verdict_field(self._verdict, "latest_in_cycle", str),
            min_supported=_verdict_field(self._verdict, "min_supported", str),
            deprecated_at=_verdict_field(self._verdict, "deprecated_at", float),
            sunset_at=_verdict_field(self._verdict, "sunset_at", float),
            notice=_verdict_field(self._verdict, "notice", dict),
            cycles=_verdict_field(self._verdict, "cycles", list),
            start_id=self._start_id,
            slot_no=self._slot_no,
            epoch=self._epoch,
            slot_count=self._slot_count,
            fenced=None if self._fenced is None else self._fenced.as_dict(),
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

    def _report_usage(self) -> None:
        """Отправить счётчики, НЕ ДОЖИДАЯСЬ продления аренды.

        Отчёт кумулятивный (см. `_usage_provider` и `_request_lease`): он
        называет ИТОГ, а не приращение, поэтому неудачная отправка ничего не
        теряет — следующий отчёт назовёт то же самое плюс новое. Именно поэтому
        частота здесь может быть минутной без риска задвоить начисление.

        Порядок важен: сначала ПОДПИСАТЬ и запомнить, потом отправить. Если
        отправка не пройдёт, `seq` уже израсходован, и следующий отчёт встанет
        в цепь ровно за тем, который до сервера не дошёл, — разрыв цепи на нашей
        стороне и есть признак потери, а не молчание.
        """
        if self._lease_id is None:
            # Без аренды отчитываться не о чем: процесс ещё не привязан к
            # организации, и сервер такой отчёт отклонит.
            return
        usage = self._sign_usage(self._usage_provider())
        with self._lock:
            self._last_report = usage
            self._last_report_at = time.time()
        self._last_usage_monotonic = time.monotonic()
        # СЛОТ И ЭПОХ ЗДЕСЬ ВЕРХНЕУРОВНЕВЫЕ, а не внутри `usage`: отчёт и так
        # подписан целиком, а `usage` — тело, чью форму сервер разбирает как
        # счётчики. Сервер принимает отчёт от ЛЮБОГО эпоха (это счёт), но метку
        # слота двигает только текущим.
        body: dict[str, object] = {
            "key": self._key,
            "instance_id": self._instance_id,
            "pubkey": self._process_key.public,
            "usage": usage,
        }
        if self._slot_no is not None and self._epoch is not None:
            body["slot_no"] = self._slot_no
            body["epoch"] = self._epoch
        self._http.post(f"{self._base_url}/v1/usage", json=body)

    def _usage_due(self) -> bool:
        last = self._last_usage_monotonic
        return last is None or (time.monotonic() - last) >= _USAGE_REPORT_SECONDS

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
                "lease_contract": LEASE_CONTRACT,
                "lease_id": self._lease_id,
                "nonce": nonce,
                # КАКОЙ ЭТО СТАРТ. Поле аддитивно: старый сервер его не читает,
                # новый без него ведёт контейнер под синтетическим поколением.
                # Поэтому `lease_contract` остаётся 3 — форма ответа не меняется.
                "start_id": self._start_id,
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
            # ФЕНСИНГ-ТОКЕН ВНУТРИ `ack`, ТО ЕСТЬ ПОД MAC ОТЧЁТА. Снаружи
            # аутентифицированной нагрузки он был бы украшением: перехватчик
            # переписал бы номер, не тронув подписи, и покупал бы ёмкость за
            # чужое поколение. `report_payload` сортирует ключи, поэтому
            # добавление полей MAC не ломает.
            if self._slot_no is not None and self._epoch is not None:
                ack["slot_no"] = self._slot_no
                ack["epoch"] = self._epoch
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
                body = {}
            # ФЕНСИНГ РАЗБИРАЕТСЯ ПО КОДУ, А НЕ ПО СТАТУСУ. Статус здесь 409 и
            # уже попадает в «временный сбой» — но тогда отказ стал бы неотличим
            # от таймаута, а это разные вещи на экране оператора и разные
            # действия: временный сбой проходит сам, вытеснение не проходит.
            if code == FENCED:
                raise _FencedError(Fenced(
                    slot_no=_int_field(body.get("slot_no")),
                    epoch=_int_field(body.get("epoch")),
                    current_epoch=_int_field(body.get("current_epoch")),
                    holder_start_id=(str(body["holder_start_id"])
                                     if body.get("holder_start_id") else None),
                    holder_since=(float(body["holder_since"])
                                  if isinstance(body.get("holder_since"), (int, float))
                                  else None),
                    detail=detail, since=time.time()))
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
        # ФОРМАТ БАНДЛА — ДО РАСПЕЧАТЫВАНИЯ (D-064). Поле под подписью, так что
        # число нельзя занизить по дороге. Отсутствие поля — сервер старше этого
        # движка, и тогда формат узнаётся по содержимому, как и раньше.
        declared = lease.get("bundle_format")
        if isinstance(declared, int) and declared > SUPPORTED_BUNDLE_FORMAT:
            raise BundleFormatError(
                f"lease carries bundle_format {declared}; this engine "
                f"({ENGINE_VERSION}) reads up to {SUPPORTED_BUNDLE_FORMAT} — "
                f"upgrade the engine: pseudexctl upgrade")
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
            self._last_ok_wall = time.time()
            self._ttl_seconds = int(lease["ttl_seconds"])
            self._grace_seconds = int(lease["grace_seconds"])
            self._renew_after_seconds = int(lease["renew_after_seconds"])
            self._lease_id = str(lease["lease_id"])
            self._bundle_version = str(lease["bundle_version"])
            self._plan = str(lease.get("plan") or "") or None
            self._last_error = None
            self._verdict = _parse_verdict(lease.get("version"))
            # МЕСТО И ПОКОЛЕНИЕ — ЕСЛИ СЕРВЕР ИХ НАЗВАЛ, И НИКОГДА ОБЯЗАТЕЛЬНО.
            # Требовать их значило бы завести второй `recipient`-дефект: движок,
            # вставший из-за порядка выкатки. Сервер старше этого движка их не
            # шлёт, и тогда экран говорит «неизвестно», а не «слот 1».
            slot_no = _int_field(lease.get("slot_no"))
            epoch = _int_field(lease.get("epoch"))
            if slot_no is not None and epoch is not None:
                self._slot_no, self._epoch = slot_no, epoch
            count = _int_field(lease.get("slot_count"))
            if count is not None:
                self._slot_count = count
        # УСПЕШНАЯ АРЕНДА — ЭТО И ЕСТЬ ОТВЕТ «СЛОТ ТВОЙ» (§3.2 ТЗ: «отказа в
        # п. 2 НЕТ, заявка всегда получает слот»). Отдельного признака здесь
        # быть не может: сервер отвечает на аренду либо слотом, либо ошибкой.
        self._clear_fencing("аренда")
        self._report_verdict()

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
                    # ОТКАЗ ПО ПОТОЛКУ НА ХОЛОДНОМ СТАРТЕ — НЕ ПРИЧИНА НЕ
                    # ПОДНЯТЬСЯ. Аренда уже получена, бандл загружен; отказали
                    # только в первом кванте, потому что между арендой и покупкой
                    # слот успел занять более новый запуск (или сервер ещё
                    # старый и принуждает места). Выйти здесь значило бы отдать
                    # оператору `bundle_unavailable` — диагноз, к которому
                    # происходящее не имеет отношения, — и погасить контейнер,
                    # который перезаявит слот сам через считаные секунды.
                    # Классификация — ТА ЖЕ, что в петле: см.
                    # `absorb_ceiling_refusal`, две копии уже разошлись однажды.
                    try:
                        self._meter_once()
                    except (_FencedError, LicenseError) as error:
                        if not self.absorb_ceiling_refusal(error):
                            raise
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
            except BundleFormatError as error:
                raise LicenseError("bundle_format_unsupported", str(error)) from error
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
        except BundleFormatError as error:
            # Наш порядок выкатки, не сбой клиента: бандл остаётся загруженным,
            # grace идёт, а в логе — действие, а не «повреждён».
            self._record_error(str(error))
            _log.error("lease renewal refused: %s. %s", error,
                       explain("bundle_format_unsupported"))
        except (_TransientLeaseError, httpx.HTTPError, BundleError) as error:
            self._record_error(str(error))
            _log.warning("lease renewal failed, running on the leased bundle: %s", error)

    def _report_verdict(self) -> None:
        """Лестница (D-055): INFO раз на «есть новее X», WARN на КАЖДОМ продлении
        после `deprecated_at` (RFC 9745: устаревание не меняет поведение, но и
        не даёт забыть), уведомление — раз на его id по своей серьёзности.
        426 сюда не доходит — он ответ, и его обрабатывает `_renew` как 402."""
        verdict = self._verdict
        if verdict is None:
            return
        latest = verdict.get("latest")
        if verdict.get("running_latest") is False and isinstance(latest, str) \
                and latest != self._announced_latest:
            self._announced_latest = latest
            _log.info("engine %s: newer version %s is available (newest in this "
                      "cycle: %s) — pseudexctl upgrade", ENGINE_VERSION, latest,
                      verdict.get("latest_in_cycle"))
        deprecated_at = verdict.get("deprecated_at")
        if isinstance(deprecated_at, float) and deprecated_at <= time.time():
            sunset_at = verdict.get("sunset_at")
            _log.warning("engine %s is DEPRECATED since %s; served until %s, then the "
                         "licensing server refuses it (426). Upgrade before then: "
                         "pseudexctl upgrade --to %s", ENGINE_VERSION,
                         _iso(deprecated_at),
                         _iso(sunset_at) if isinstance(sunset_at, float) else "(unset)",
                         _cycle_of(latest) if isinstance(latest, str) else "latest")
        notice = verdict.get("notice")
        if isinstance(notice, dict):
            notice_id = str(notice.get("id", ""))
            if notice_id and notice_id not in self._announced_notices:
                self._announced_notices.add(notice_id)
                # The registry's vocabulary (licensing/registry.py SEVERITIES): info, warning, danger.
                level = {"info": logging.INFO, "warning": logging.WARNING,
                         "danger": logging.ERROR}.get(str(notice.get("severity", "")),
                                                        logging.WARNING)
                _log.log(level, "notice %s for engine %s: %s %s", notice_id,
                         ENGINE_VERSION, notice.get("text", ""), notice.get("url", ""))

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
            # ОТФЕНСЕННЫЙ БОЛЬШЕ НЕ ПОКУПАЕТ. Это и есть «больше не покупаю» из
            # §3.6: место занято более новым запуском, следующая покупка
            # получила бы тот же отказ, а полосу, которая уже оплачена, процесс
            # доцеживает — её отзывать не за что.
            if self._fenced is not None:
                return False
            if not self._quantum_seq:
                return True
            return self._consumed >= self._prefetch_at

    def _enter_fenced(self, fenced: Fenced) -> None:
        """Перейти в «больше не покупаю» — и НЕ гасить процесс (Б30).

        Гасит его обычная `has_capacity()`, когда купленная полоса кончится.
        Именно этим отказ в НОВОЙ ёмкости отличается от ответа о подписке:
        отозвать уже выданное значило бы сжечь оплаченный клиентом остаток за
        то, что он переразвернул контейнер.
        """
        already = self._fenced is not None
        with self._lock:
            self._fenced = fenced
            if not already:
                # Одна немедленная перезаявка с джиттером. Повторный отказ
                # расписание НЕ переставляет — иначе «одна попытка» стала бы
                # одной попыткой на каждый отказ.
                self._reclaim_at = (time.monotonic()
                                    + random.random() * _RECLAIM_JITTER_SECONDS)
        self._record_error(fenced.detail)
        if not already:
            consumed, granted = self.capacity()
            _log.error(
                "FENCED: slot %s generation %s superseded by generation %s "
                "(start %s). Serving the %d requests already paid for, buying "
                "no more. %s",
                fenced.slot_no, fenced.epoch, fenced.current_epoch,
                fenced.holder_start_id or "?", max(0, granted - consumed),
                explain_fenced(fenced.as_dict()))

    def absorb_ceiling_refusal(self, error: Exception) -> bool:
        """ЭТО ОТКАЗ ПО ПОТОЛКУ? Тогда «больше не покупаю» — и процесс живёт.

        ОДНА ФУНКЦИЯ НА ОБА МЕСТА, И ЭТО ПОЧИНКА, А НЕ ПРИБОРКА. Классификация
        стояла в двух: `_meter_step` знала про оба кода потолка, а `acquire`
        ловила только `_FencedError`. Первый же квант, отказанный СТАРЫМ
        сервером (`instance_limit`, §7.2 — новый движок против ещё не
        обновлённого сервера), поднимался из `acquire` как терминальная ошибка
        лицензии, и контейнер не вставал вовсе: аренда взята, бандл загружен,
        а движок отказывается стартовать из-за отказа в ПЕРВОМ кванте, который
        он купил бы через десять секунд перезаявкой. Разойтись эти две ветки
        могли только потому, что их было две.

        Возвращает True, когда отказ поглощён; False — когда это ответ о
        подписке, и решать его обязан вызывающий (на старте — не подниматься,
        в петле — погасить).
        """
        if isinstance(error, _FencedError):
            self._enter_fenced(error.fenced)
            return True
        # СТАРЫЙ СЕРВЕР, `instance_limit`. Слота он не называет, поэтому
        # известен только текст — и это всё равно «больше не покупаю», а не
        # «умри»: причина отказа та же.
        if isinstance(error, LicenseError) and error.code in _CEILING_CODES:
            self._enter_fenced(Fenced(
                slot_no=self._slot_no, epoch=self._epoch, current_epoch=None,
                holder_start_id=None, holder_since=None,
                detail=error.detail, since=time.time()))
            return True
        return False

    def _clear_fencing(self, answered_by: str) -> None:
        """Снять FENCED, потому что СЕРВЕР ответил «да» — арендой или квантом.

        СРАВНЕНИЕ НОМЕРОВ ПОКОЛЕНИЙ ЗДЕСЬ СТОЯЛО И БЫЛО НЕВЕРНЫМ. Правило было
        «снимать только когда эпох СМЕНИЛСЯ», а его посылка — «аренда, вернувшая
        тот же эпох, значит слот всё ещё держит кто-то другой» — противоречит
        тому, как сервер решает: `lease_generation` возвращает ТОТ ЖЕ эпох
        ровно в одном случае — когда поколение этого старта УЖЕ держит свой слот
        на текущем эпохе (`fresh_claim = False`). То есть единственный ответ,
        который прежнее правило читало как «держит чужой», означает
        «держишь ты». Отфенсенный воркер, чей слот вернул брат по старту (или он
        сам), оставался в FENCED навсегда: `_quantum_due()` при `_fenced`
        возвращает False, покупок нет, полоса дотекает, и контейнер темнеет,
        держа слот.

        ВТОРАЯ ПОСЫЛКА ТОЖЕ УСТАРЕЛА. Она считала, что судьба воркера решается
        эпохом ЕГО СТРОКИ АРЕНДЫ; сервер теперь судит ПОКОЛЕНИЕ
        (`_generation_standing`), поэтому перезаявка ОДНОГО воркера снимает
        фенсинг со всех братьев — и узнают они об этом не по своему номеру, а по
        первому же «да» сервера. Ответ сервера и есть единственное свидетельство,
        которое здесь бывает; собственный номер — догадка о нём.

        Выданный квант — такое же «да»: сервер выдаёт его только поколению,
        которое держит слот (`meter_if_allowed`), и молча выдать квант мимо
        этого правила он не может.
        """
        if self._fenced is None:
            return
        with self._lock:
            self._fenced = None
            self._reclaim_at = None
        _log.info("fencing cleared by %s: this start holds slot %s at generation %s",
                  answered_by, self._slot_no, self._epoch)

    def _reclaim_step(self) -> None:
        """Перезаявить слот. Ровно одна попытка на фенсинг и не чаще раза в час.

        Зачем вообще: ранжирование слотов на сервере ошибается в окне разрешения
        отметок — контейнер, умерший тридцать секунд назад, «слышали позже», чем
        простаивающего живого соседа с отчётом стосекундной давности, и пришедшее
        в это окно поколение фенсит ЖИВОГО. Одна перезаявка ранжирует заново,
        когда мёртвый уже молчит дольше всех. Цена ошибки — одна аренда вместо
        простоя до восьми часов.
        """
        before = self._last_ok_monotonic
        self._last_reclaim_attempt_monotonic = time.monotonic()
        self._last_attempt_monotonic = time.monotonic()
        _log.info("fenced: one re-claim of the slot (generation %s held it)",
                  None if self._fenced is None else self._fenced.current_epoch)
        self._renew()
        # ПОТРАЧЕНА ТОЛЬКО ТА, КОТОРАЯ ДОШЛА. `_renew` глотает сетевой сбой как
        # временный и ничего об этом не возвращает, поэтому успех читается по
        # отметке последней удавшейся аренды — она двигается только в `_apply`.
        if self._last_ok_monotonic != before:
            self._last_reclaim_monotonic = time.monotonic()
            self._reclaim_at = None

    def _meter_step(self) -> None:
        """Обёртка вокруг покупки кванта с той же классификацией отказов, что и
        у продления: ответ — терминальный, сбой — в долг из резерва.

        ТРИ ИСХОДА, А НЕ ДВА (Б30). Отказ по ПОТОЛКУ («место занято», «мест по
        тарифу нет») раньше приземлялся в ту же ветку, что отказ по ПОДПИСКЕ, и
        звал `_expire()` — бандл выгружался, `/mask` отдавал 503 в ту же секунду,
        а оплаченный остаток сгорал. Сервер при этом в комментарии обещал
        обратное. Теперь потолок переводит процесс в «больше не покупаю», и
        гасит его обычная проверка ёмкости.
        """
        try:
            self._meter_once()
            # ВЫДАННЫЙ КВАНТ — ОТВЕТ СЕРВЕРА «ТЫ ДЕРЖИШЬ СЛОТ»: мимо текущего
            # эпоха он ёмкость не выдаёт. Значит своего номера поколения для
            # выхода из FENCED не нужно (см. `_clear_fencing`).
            self._clear_fencing("квант")
            if self._terminal_code is not None:
                _log.info("capacity restored (was %s)", self._terminal_code)
                self._terminal_code = None
        except _FencedError as error:
            # Поглощается всегда; разбор общий с `acquire`, чтобы ветка
            # классификации оставалась ОДНА — две уже разъехались однажды.
            self.absorb_ceiling_refusal(error)
        except LicenseError as error:
            if self.absorb_ceiling_refusal(error):
                return
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
            # Cleared BEFORE the work below, never after the wait. A consume()
            # that crosses prefetch_at and calls _wake.set() DURING the work would
            # be lost if we cleared once wait() had already returned; clearing
            # first means such a set() leaves the event set, so the wait() at the
            # bottom returns at once and the next pass meters promptly instead of
            # stalling up to ~5 s for the scheduled wake.
            self._wake.clear()
            due = self._renew_after_seconds
            # ДЖИТТЕР ПРОДЛЕНИЯ. 10k контейнеров, стартовавших вместе, иначе
            # приходят продлеваться в одну минуту, а сервер сериализует аренды
            # (seal ~1.5МБ держит GIL — нагрузочный тест §2.6.4). Свой множитель
            # у каждого процесса размазывает флот по окну; только ВНИЗ, поэтому
            # продление НЕ ПОЗЖЕ намеченного и STALE не грозит. Не трогает первый
            # (холодный) заход — тот с last_attempt=None срабатывает сразу.
            renew_threshold = self._renew_after_seconds * self._renew_jitter
            if self._terminal_code is not None:
                # A revoked or unpaid licence keeps asking, just slowly. Stopping
                # forever would mean a customer who pays their invoice has to
                # restart every container to come back — the kill switch is meant
                # to stop the service NOW, not to make recovery a support ticket.
                due = max(due, _TERMINAL_RETRY_SECONDS)
                # Терминальный бэкофф фиксирован, не джиттерится.
                renew_threshold = due
            last_attempt = self._last_attempt_monotonic
            try:
                # ПЕРЕЗАЯВКА ОТФЕНСЕННОГО — ПЕРЕД ПОКУПКОЙ, А НЕ ПОСЛЕ НЕЁ.
                # Правило допуска живёт в `should_reclaim` (развилка §6.1),
                # петля только исполняет его вердикт; но порядок внутри прохода
                # — цена ОДНОГО прохода для того, у кого полосы нет вовсе.
                # Покупка первой означала: перезаявка сняла фенсинг — и квант
                # покупается лишь на СЛЕДУЮЩЕМ проходе, до пяти секунд спустя
                # (`self._wake.wait`). Для холодного старта, отфенсенного на
                # первом кванте, эти пять секунд — весь его запас: `granted`
                # ноль, `/mask` отдаёт 503, доцеживать нечего. Обратный порядок
                # ничего не стоит: при `_fenced` покупка всё равно запрещена
                # (`_quantum_due`), так что на отфенсенном проходе она no-op.
                if self._fenced is not None:
                    consumed, granted = self.capacity()
                    if should_reclaim(self._reclaim_at,
                                      self._last_reclaim_monotonic,
                                      self._last_reclaim_attempt_monotonic,
                                      granted - consumed, time.monotonic()):
                        self._reclaim_step()
                # ЁМКОСТЬ И АРЕНДА ПОКУПАЮТСЯ ОТДЕЛЬНО. Аренда тяжёлая (бандл
                # пересобирается и заново шифруется, около двух мегабайт) и
                # редкая; квант лёгкий и частый. Пересобирать бандл на каждый
                # квант нельзя — это была бы наша собственная DoS-атака.
                if self._capacity_endpoint and self._quantum_due():
                    self._meter_step()
                # РАСХОД УХОДИТ САМ, НЕ ВМЕСТЕ С АРЕНДОЙ. Продление — раз в
                # `TTL / 3` (восемь часов при суточной аренде), и до этой
                # правки счётчики ждали его вместе с клиентом.
                if self._usage_due():
                    self._report_usage()
                if last_attempt is None or (
                        time.monotonic() - last_attempt >= renew_threshold):
                    self._last_attempt_monotonic = time.monotonic()
                    self._renew()
                    # Свежий сдвиг на следующий цикл — флот продолжает расходиться.
                    self._renew_jitter = _roll_renew_jitter()
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
            # No clear() here: it happens at the top of the next pass, so a set()
            # arriving now is not swallowed.
            self._wake.wait(min(5.0, max(1.0, due / 4.0)))

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


class _FencedError(_TransientLeaseError):
    """Место этого запуска занял более новый запуск — отказ в НОВОЙ ёмкости.

    ПОДКЛАСС ВРЕМЕННОГО СБОЯ НАМЕРЕННО. Любая ветка, которая про фенсинг не
    знает, обработает его как «доцеживай» — то есть промах в разборе ошибок
    стоит нам наблюдаемости и НИКОГДА не стоит клиенту оплаченного остатка.
    Обратный порядок наследования дал бы ровно Б30 при первой же забытой ветке.
    """

    def __init__(self, fenced: Fenced) -> None:
        super().__init__(f"{FENCED}: {fenced.detail}")
        self.fenced = fenced
