"""Licensing state: who has a key, what leases were issued, what was used.

Deliberately the same SQLite setup the sidecar uses (`pseudex/sqlite_setup.py`,
WAL + busy_timeout armed before journal_mode) — the licensing server is a small
service and a second storage stack would be a second thing to operate.

The key is stored HASHED. It is a bearer credential: anyone holding it can lease
the product, so a dump of this table must not be enough to serve customers. SHA-256
without a salt is correct here and a per-row salt would be worse — the key is 32
bytes of `secrets.token_urlsafe` entropy, so there is no dictionary to attack, and
an unsalted digest is what lets a lookup be a single indexed point query.
"""

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass

from pseudex.sqlite_setup import LICENSING_STORE, connect as sqlite_connect

KEY_PREFIX = "ps_live_"

_log = logging.getLogger("licensing.store")

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"
STATUS_SUSPENDED = "suspended"
STATUS_UNPAID = "unpaid"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KeyRecord:
    org_id: str
    status: str
    plan: str


class LicenseStore:
    """Connector to the licensing database (external state -> class)."""

    def __init__(self, db_path: str) -> None:
        # RLock, НЕ Lock, И ЭТО НЕ ВКУСОВЩИНА. `_accumulate_values` читает и
        # пишет, будучи вызванным ИЗ-ПОД уже взятого лока в `record_usage`;
        # обычный `Lock` встанет там намертво и остановит учёт целиком.
        self._lock = threading.RLock()
        self._conn = sqlite_connect(db_path, LICENSING_STORE)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS keys ("
            "key_hash TEXT PRIMARY KEY, org_id TEXT, plan TEXT, status TEXT, created_at REAL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS grants ("
            "org_id TEXT, pubkey TEXT, granted INTEGER DEFAULT 0, issued_at REAL, "
            "PRIMARY KEY (org_id, pubkey))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS process_reports ("
            "org_id TEXT, pubkey TEXT, secret TEXT DEFAULT '', "
            "seq INTEGER DEFAULT 0, prev TEXT DEFAULT '', signature TEXT DEFAULT '', "
            "chain_breaks INTEGER DEFAULT 0, updated_at REAL, "
            "build TEXT DEFAULT '', build_changes INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, pubkey))"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS leases ("
            "lease_id TEXT PRIMARY KEY, org_id TEXT, instance_id TEXT, process_id TEXT, "
            # КЛЮЧ ПРОЦЕССА — ЕДИНСТВЕННЫЙ ИДЕНТИФИКАТОР, КОТОРЫЙ КЛИЕНТ НЕ
            # ВЫБИРАЕТ. Он генерируется в памяти воркера, на него запечатывается
            # бандл, и два процесса не могут иметь один и тот же, не будучи
            # пропатченными. Всё остальное, чем контейнер представляется, —
            # переменные окружения.
            "pubkey TEXT, "
            # ОСВОБОЖДЁННЫЙ СЛОТ ОСТЫВАЕТ, А НЕ ИСЧЕЗАЕТ. Строка удалялась, и
            # это обнуляло единственную границу, которую мы принуждаем:
            # контейнер отдавал слот сам, поднимался следующий, и на тарифе в
            # один инстанс их поднималось пять подряд.
            "released_at REAL, released_by TEXT, "
            "issued_at REAL, ttl_seconds INTEGER)"
        )
        # Keyed by (org, instance) and holding the LATEST CUMULATIVE totals — not
        # one row per report.
        #
        # The client reports `audit.billing_totals()`, which is everything that
        # instance has ever protected, on every renewal. Summing those rows would
        # bill a customer once per renewal for the same traffic: at a 24 h lease
        # that is a month's usage counted thirty times over.
        #
        # Cumulative-and-overwrite also survives a lost report, which a delta
        # scheme does not: a delta that never arrives is gone, while a missed
        # cumulative report is corrected by the next one.
        #
        # Per INSTANCE, because every worker process of one container shares one
        # audit database and therefore reports the same instance-wide number —
        # summing workers would multiply the bill by the worker count.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS usage ("
            "org_id TEXT, instance_id TEXT, updated_at REAL, reports INTEGER, "
            "requests INTEGER, entities TEXT, "
            # The billed quantity, accumulated MONOTONICALLY on our side.
            # `values_reported` is the last number the installation sent;
            # `values_total` never decreases.
            "values_reported INTEGER DEFAULT 0, values_total INTEGER DEFAULT 0, "
            "resets INTEGER DEFAULT 0, "
            # Доказательная часть ПРОТИВ КАНАЛА: последний номер в цепи, хеш
            # предыдущей подписи, сама подпись и вердикт о ней. Против самого
            # клиента она ничего не доказывает — см. `bundle.py::mac_report`. `chain_breaks` считает
            # разрывы — пропуск, перестановку или подмену старым отчётом.
            "seq INTEGER DEFAULT 0, prev TEXT DEFAULT '', signature TEXT DEFAULT '', "
            "trust TEXT DEFAULT 'unsigned', chain_breaks INTEGER DEFAULT 0, "
            "unverified_reports INTEGER DEFAULT 0, "
            "unverified_requests INTEGER DEFAULT 0, "
            # «Не смогли разобрать» — это НЕ «расхода не было». Без отдельной
            # колонки испорченный отчёт был неотличим от молчания.
            "malformed_reports INTEGER DEFAULT 0, "
            # Продление ПРИШЛО, а отчёта в нём НЕ БЫЛО. Раньше это была полная
            # тишина: перехватчик, выбрасывающий поле `usage`, не двигал ни
            # одного счётчика — подделать отчёт было видно, повторить видно, а
            # снять целиком не видно ничем.
            "reports_missing INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, instance_id))"
        )
        # НИ ОДНОГО ИНДЕКСА ЗДЕСЬ НЕ БЫЛО. `leases` растёт примерно на три
        # строки в сутки на воркера и никогда не чистится (`lease_id` свежий на
        # каждое продление, поэтому `INSERT OR REPLACE` ничего не заменяет), а
        # `may_lease` сканирует её целиком на КАЖДОЙ аренде — то есть на
        # запросе, который решает, обслуживать ли клиента.
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS leases_org_issued "
            "ON leases(org_id, issued_at)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS leases_org_pubkey ON leases(org_id, pubkey)")
        # ЛЕДЖЕР ЁМКОСТИ. Ключ строки — ключ ПРОЦЕССА: единственный
        # идентификатор, который клиент не выбирает.
        #
        # `granted` — потолок, растёт только у нас и только вверх. `acked` —
        # высшее подтверждённое значение расхода, названное клиентом под MAC.
        # Счёт строится на `acked`, ЗАЖАТОМ между `granted - Q - R` и
        # `granted`: отчёт может двигать сумму только внутри полосы, которую
        # чеканим мы, поэтому занизить его выгодно ровно до нуля.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS meter ("
            "org_id TEXT, pubkey TEXT, first_seen REAL, updated_at REAL, "
            "quantum_seq INTEGER DEFAULT 0, quantum_size INTEGER DEFAULT 0, "
            "reserve INTEGER DEFAULT 0, granted INTEGER DEFAULT 0, "
            # Порог, на котором движок обязан прийти за следующим квантом. Сам
            # факт прихода — это и есть оценка расхода, когда отчёта нет.
            "prefetch_at INTEGER DEFAULT 0, "
            "acked INTEGER DEFAULT 0, acked_at REAL, "
            "ack_trust TEXT DEFAULT 'none', rate_per_second REAL DEFAULT 0, "
            # Кванты подряд без проверенного отчёта. Молчание перестаёт быть
            # тишиной: оно видно числом и стоит клиенту скидки.
            "unacked_quanta INTEGER DEFAULT 0, "
            # Расход поехал назад под одним ключом процесса. Процесс не может
            # обслужить меньше, чем уже обслужил, — значит либо два процесса на
            # одном ключе, либо повтор.
            "ack_regressions INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, pubkey))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS meter_org ON meter(org_id)")
        # ТАРИФ — СТРОКА, А НЕ КОНСТАНТА. Числа тарифа стояли классовыми
        # словарями, поэтому поправить потолок инстансов одному клиенту значило
        # выкатить релиз. Словари никуда не делись: они СИД для чистой базы и
        # последний рубеж, если строки нет, — а источником истины стала таблица.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS plans ("
            "code TEXT PRIMARY KEY, max_instances INTEGER, "
            "processes_per_instance INTEGER, grant_size INTEGER, "
            "quantum_min INTEGER, quantum_max INTEGER, reserve_max INTEGER, "
            # Пусто — значит строка как её посеяли; непусто — кто-то правил.
            # Дешевле и честнее, чем сравнивать шесть чисел с сидом.
            "updated_at REAL, updated_by TEXT DEFAULT '')"
        )
        # СУТОЧНЫЙ СРЕЗ ИСПОЛЬЗОВАНИЯ, и это требование записано до нас:
        # docs/tz-site.md §6 — «таблица `usage` хранит по одному снимку на
        # инстанс… для графика по времени нужны периодические срезы. Решить это
        # надо до того, как будет нарисован экран».
        #
        # СУТКИ, А НЕ ОТЧЁТ, и это арифметика. Отчёт едет на продлении, а
        # `renew_after = ttl // 3` — трижды в сутки на процесс; построчно это
        # порядка полусотни строк в сутки на клиента и десятки миллионов в год на
        # тысяче. Строка на инстанс в сутки даёт тысячи, а не миллионы.
        #
        # Хранится НАКОПИТЕЛЬНЫЙ снимок на конец суток, как и в `usage`, а не
        # прирост: график — разность соседних суток, ровно та же вычитаемая
        # ватермарка, которой уже считает `billing/services.py::build_invoice`.
        # Прирост пришлось бы вычислять на записи, а значит доверять тому, что
        # предыдущая запись случилась.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS usage_daily ("
            "org_id TEXT, instance_id TEXT, day TEXT, "
            "requests INTEGER DEFAULT 0, values_total INTEGER DEFAULT 0, "
            "reports INTEGER DEFAULT 0, updated_at REAL, "
            "PRIMARY KEY (org_id, instance_id, day))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS usage_daily_org ON usage_daily(org_id, day)")
        # Существующие тома пережили релизы без этой колонки.
        columns = {row[1] for row in
                   self._conn.execute("PRAGMA table_info(leases)")}
        if "pubkey" not in columns:
            self._conn.execute("ALTER TABLE leases ADD COLUMN pubkey TEXT")
        for column, ddl in (("released_at", "released_at REAL"),
                            ("released_by", "released_by TEXT")):
            if column not in columns:
                self._conn.execute(f"ALTER TABLE leases ADD COLUMN {ddl}")
        usage_columns = {row[1] for row in
                         self._conn.execute("PRAGMA table_info(usage)")}
        for column, ddl in (("seq", "seq INTEGER DEFAULT 0"),
                            ("prev", "prev TEXT DEFAULT ''"),
                            ("signature", "signature TEXT DEFAULT ''"),
                            ("trust", "trust TEXT DEFAULT 'unsigned'"),
                            ("chain_breaks", "chain_breaks INTEGER DEFAULT 0"),
                            ("unverified_reports",
                             "unverified_reports INTEGER DEFAULT 0"),
                            ("unverified_requests",
                             "unverified_requests INTEGER DEFAULT 0"),
                            ("malformed_reports",
                             "malformed_reports INTEGER DEFAULT 0"),
                            ("reports_missing",
                             "reports_missing INTEGER DEFAULT 0")):
            if column not in usage_columns:
                self._conn.execute(f"ALTER TABLE usage ADD COLUMN {ddl}")
        self._conn.commit()
        self._seed_plans()

    def _seed_plans(self) -> None:
        """Посеять тарифы из констант — `INSERT OR IGNORE`, НЕ `REPLACE`.

        СТРОКА ПОБЕЖДАЕТ КОНСТАНТУ, иначе таблица бессмысленна: правка тарифа
        обязана пережить рестарт, а `REPLACE` возвращал бы её к сиду на каждом
        подъёме процесса.

        Обратную сторону надо назвать вслух, потому что она неочевидна и укусит
        того, кто про неё не знает: **поправить константу и выкатить релиз больше
        НЕ меняет работающий тариф**. Поэтому расхождение видно снаружи —
        `plans()` отдаёт `source`, и `edited` означает, что здесь правили руками.

        Гонки нет: лицензионный сервер — один процесс (`devserver.py` поднимает
        два ASGI-приложения на одном `STORE` под `RLock`).
        """
        # НЕПОЛНЫЙ СИД — ОШИБКА В КОДЕ, И ОНА ПАДАЕТ ЗДЕСЬ, А НЕ У КЛИЕНТА.
        #
        # Раньше недостающие значения добирались через `.get(code, …)` с
        # умолчаниями «старта», и тариф, добавленный в `PLAN_INSTANCES` и
        # забытый в `PLAN_GRANT`, тихо оседал в таблице с грантом младшего
        # тарифа. Это ровно тот дефект, ради которого заводился `known_plan`, —
        # он просто переехал бы на одну таблицу дальше и стал невидим, потому
        # что строка-то теперь есть.
        incomplete = {
            code: [name for name, table in (("PLAN_GRANT", self.PLAN_GRANT),
                                            ("QUANTUM_BOUNDS", self.QUANTUM_BOUNDS),
                                            ("RESERVE_MAX", self.RESERVE_MAX))
                   if code not in table]
            for code in self.PLAN_INSTANCES
        }
        incomplete = {code: missing for code, missing in incomplete.items() if missing}
        if incomplete:
            raise ValueError(
                "неполный сид тарифов, тариф объявлен не во всех таблицах: "
                + "; ".join(f"{code} нет в {', '.join(tables)}"
                            for code, tables in sorted(incomplete.items())))
        with self._lock:
            for code, instances in self.PLAN_INSTANCES.items():
                low, high = self.QUANTUM_BOUNDS[code]
                self._conn.execute(
                    "INSERT OR IGNORE INTO plans (code, max_instances, "
                    "processes_per_instance, grant_size, quantum_min, quantum_max, "
                    "reserve_max, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?,'')",
                    (code, instances, self.PROCESSES_PER_INSTANCE,
                     self.PLAN_GRANT[code], low, high, self.RESERVE_MAX[code],
                     time.time()),
                )
            self._conn.commit()

    def _fetchall(self, sql: str, params: tuple) -> list[tuple]:
        """Every READ goes through here, under the same lock the writes take.

        The rule and the measurement behind it are `pseudex/audit.py::_fetchall`:
        `check_same_thread=False` lets threads share one connection, it does not
        make the connection concurrent, and a read interleaved with another
        thread's INSERT+commit returns a row with COLUMNS MISSING rather than an
        error anyone would recognise as a locking bug.

        Here it is worse than in the audit, because one of the readers is
        `may_lease` — the query that decides whether a customer may serve
        traffic at all — and `devserver.py` runs the admin app on a second
        thread against this same connection.
        """
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _fetchone(self, sql: str, params: tuple) -> tuple | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def issue_key(self, org_id: str, plan: str) -> str:
        key = KEY_PREFIX + secrets.token_urlsafe(32)
        with self._lock:
            self._conn.execute(
                "INSERT INTO keys (key_hash, org_id, plan, status, created_at) VALUES (?,?,?,?,?)",
                (hash_key(key), org_id, plan, STATUS_ACTIVE, time.time()),
            )
            self._conn.commit()
        return key

    def lookup(self, key: str) -> KeyRecord | None:
        row = self._fetchone(
            "SELECT org_id, status, plan FROM keys WHERE key_hash=?", (hash_key(key),)
        )
        return KeyRecord(row[0], row[1], row[2]) if row is not None else None

    def revoke_key_hash(self, key_hash: str) -> int:
        """Revoke ONE key. Statuses were per-organisation only, so the cabinet's
        "отозвать ключ" button set a local flag, reported success, and left the
        key leasing forever — the departing engineer's copy kept working.

        Matched on the hash because that is all the storefront holds: the key
        itself is shown once and never stored in readable form on either side.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET status=? WHERE key_hash=? AND status=?",
                (STATUS_REVOKED, key_hash, STATUS_ACTIVE),
            )
            self._conn.commit()
            return cursor.rowcount

    def set_status(self, org_id: str, status: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE keys SET status=? WHERE org_id=?", (status, org_id)
            )
            self._conn.commit()
        return cursor.rowcount

    def record_lease(self, lease_id: str, org_id: str, instance_id: str,
                     process_id: str, ttl_seconds: int, pubkey: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO leases "
                "(lease_id, org_id, instance_id, process_id, pubkey, issued_at, "
                "ttl_seconds) VALUES (?,?,?,?,?,?,?)",
                (lease_id, org_id, instance_id, process_id, pubkey, time.time(),
                 ttl_seconds),
            )
            self._conn.commit()

    def _accumulate_values(self, org_id: str, instance_id: str, reported: int) -> int:
        """Fold a new reading into a counter that never goes backwards.

        The vault lives on the customer's volume, so `docker volume rm` restarts
        `first_seen` and the reported count drops to zero. Billing the reported
        number directly would make deleting the vault a way not to pay.

        A drop is treated as a NEW INSTALLATION rather than as a correction: the
        growth since the reset is added on top of what was already accumulated.
        Re-protecting the same people after a reset therefore counts again,
        which is the honest reading — the engine did the work a second time.

        It is not evidence of anything. A vault can be lost honestly, in a
        migration or a disk failure. It is recorded as a `reset` so a pattern is
        visible, and a pattern is a conversation, not an accusation.
        """
        row = self._fetchone(
            "SELECT values_reported, values_total, resets FROM usage "
            "WHERE org_id=? AND instance_id=?", (org_id, instance_id),
        )
        if row is None:
            return reported
        previous, total, resets = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
        if reported >= previous:
            return total + (reported - previous)
        _log.warning("usage counter went backwards for org=%s instance=%s: "
                     "%d -> %d (vault reset or restore); accumulating on top",
                     org_id, instance_id, previous, reported)
        self._conn.execute(
            "UPDATE usage SET resets=? WHERE org_id=? AND instance_id=?",
            (resets + 1, org_id, instance_id),
        )
        return total + reported

    def record_report_secret(self, org_id: str, pubkey: str,
                             secret_hex: str) -> None:
        """КЛЮЧ — ОТКРЫТЫЙ КЛЮЧ ПРОЦЕССА, А НЕ `instance_id`.

        `instance_id` приходит из переменной окружения, которую ставит клиент —
        то самое, что мы убрали из подсчёта тарифа именно потому, что клиент его
        выбирает. Пока секрет лежал под ним, ломались ОБЕ стороны:

          * держатель ключа организации мог назваться чужим `instance_id`, и мы
            чеканили свежий секрет, запечатанный ЕГО ключу, поверх честного —
            после чего его отчёты проходили как `signed`, а настоящие падали в
            `bad_signature`;
          * и без всякой атаки: `entrypoint.sh` даёт всем воркерам ОДИН
            `instance_id`, у каждого свой ключ процесса и свой секрет, и все
            писали в одну строку — «подписанным» оставался только последний
            арендовавший, остальные навсегда `bad_signature`.

        Ключ процесса решает обе задачи разом: секрет, запечатанный ключу K,
        проверяется только против отчёта, назвавшего K, и у N воркеров N строк.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO process_reports (org_id, pubkey, secret, updated_at) "
                "VALUES (?,?,?,?) ON CONFLICT(org_id, pubkey) DO UPDATE SET "
                "secret=excluded.secret, updated_at=excluded.updated_at",
                (org_id, pubkey, secret_hex, time.time()),
            )
            self._conn.commit()

    def report_secret(self, org_id: str, pubkey: str) -> str:
        row = self._fetchone(
            "SELECT secret FROM process_reports WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        return (row[0] or "") if row else ""

    def record_usage(self, org_id: str, instance_id: str, requests: int,
                     entities: dict[str, int], values: int, seq: int = 0,
                     prev: str = "", signature: str = "",
                     trust: str = "unsigned", report_pubkey: str = "",
                     build: str = "") -> None:
        """Record the newest report.

        `requests` and `entities` are OVERWRITTEN — each report restates the
        instance's own cumulative totals, so the latest one is the truth.

        `values` is different, because it is what the invoice is computed from:
        it is folded into a counter that never decreases, so a customer who
        deletes their vault does not thereby delete what they owe. See
        docs/billing-integrity.md §2.1.
        """
        if not signature:
            trust = "unsigned"
        breaks = self._chain_breaks(org_id, instance_id, seq, prev, trust,
                                    report_pubkey)
        if report_pubkey:
            self._record_process_report(org_id, report_pubkey, seq, prev,
                                        signature, breaks)
            self._record_build(org_id, report_pubkey, build, trust)
        # НЕПРОВЕРЕННЫЙ ОТЧЁТ НЕ СТАНОВИТСЯ СЧЁТОМ. Раньше вердикт писался в
        # колонку и на этом всё: цифры принимались одинаково при `signed`,
        # `bad_signature` и `unsigned`, а `usage_totals` — то, из чего считается
        # инвойс — этих колонок не отдавал вовсе. Снять подпись было ТИШЕ, чем
        # подделать: без неё проверка даже не запускалась.
        #
        # Обслуживать продолжаем в любом случае — падать из-за спора о биллинге
        # значит наказывать конечного пользователя. Но в billable-счётчики
        # непроверенное не идёт: оно копится отдельно, чтобы разговор был
        # предметным, а не «поверьте нам».
        if trust != "signed":
            with self._lock:
                self._conn.execute(
                    "INSERT INTO usage (org_id, instance_id, updated_at, reports, "
                    "unverified_reports, unverified_requests, trust) "
                    "VALUES (?,?,?,0,1,?,?) "
                    "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                    "updated_at=excluded.updated_at, "
                    "unverified_reports=usage.unverified_reports+1, "
                    "unverified_requests=excluded.unverified_requests, "
                    "trust=excluded.trust",
                    (org_id, instance_id, time.time(), requests, trust),
                )
                self._conn.commit()
            _log.warning("usage report NOT billed for org=%s instance=%s: trust=%s",
                         org_id, instance_id, trust)
            return
        # ПОВТОР СТАРОГО ЧЕСТНОГО ОТЧЁТА НЕ ОПУСКАЕТ СЧЁТЧИК. У него настоящий
        # MAC — он и был настоящим, — поэтому проверка подписи его пропускает, а
        # `requests` перезаписывается последним пришедшим. Root на хосте ловит
        # вчерашний отчёт и шлёт его снова: 5000 -> 1000. `values` защищён
        # монотонным накоплением, `requests` не был.
        #
        # Разрыв цепи — это ровно тот случай, и при нём счётчики не двигаются
        # вниз: берём максимум. Честному клиенту это ничего не стоит, его
        # `requests` и так растёт.
        with self._lock:
            accumulated = self._accumulate_values(org_id, instance_id, values)
            previous = self._fetchone(
                "SELECT requests FROM usage WHERE org_id=? AND instance_id=?",
                (org_id, instance_id))
            if previous is not None:
                requests = max(requests, int(previous[0] or 0))
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, requests, "
                "entities, values_reported, values_total, seq, prev, signature, "
                "trust, chain_breaks) VALUES (?,?,?,1,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                "updated_at=excluded.updated_at, reports=usage.reports+1, "
                "requests=excluded.requests, entities=excluded.entities, "
                "values_reported=excluded.values_reported, "
                "values_total=excluded.values_total, seq=excluded.seq, "
                "prev=excluded.prev, signature=excluded.signature, "
                "trust=excluded.trust, chain_breaks=excluded.chain_breaks",
                (org_id, instance_id, time.time(), requests, json.dumps(entities),
                 values, accumulated, seq, prev, signature, trust, breaks),
            )
            # СУТОЧНЫЙ СРЕЗ ПИШЕТСЯ ТОЛЬКО ЗДЕСЬ — на подтверждённой ветке.
            # Неподтверждённое не входит в счёт, значит не должно входить и в
            # график счёта: иначе экран показывал бы объём, за который никто не
            # выставит, и расхождение с инвойсом пришлось бы объяснять словами.
            # Отдельно оно и так видно — `unverified_reports`/`unverified_requests`.
            self._record_daily(org_id, instance_id, requests, accumulated)
            self._conn.commit()

    def _record_daily(self, org_id: str, instance_id: str,
                      requests: int, values_total: int) -> None:
        """Снимок накопительных счётчиков на конец суток. Зовётся ИЗ-ПОД лока.

        Перезаписывает числа и увеличивает `reports`: за сутки отчётов несколько,
        и верен последний — ровно так же, как в `usage`. График рисуется
        разностью соседних суток, поэтому хранить надо накопительное, а не
        прирост: прирост требовал бы верить, что предыдущая запись случилась.
        """
        now = time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        self._conn.execute(
            "INSERT INTO usage_daily (org_id, instance_id, day, requests, "
            "values_total, reports, updated_at) VALUES (?,?,?,?,?,1,?) "
            "ON CONFLICT(org_id, instance_id, day) DO UPDATE SET "
            # МАКСИМУМ, А НЕ ПРИСВОЕНИЕ. Повтор старого честного отчёта имеет
            # настоящий MAC и проходит проверку подписи; `record_usage` уже
            # защищает от него `requests` максимумом, и срез обязан вести себя
            # так же, иначе график поедет вниз там, где счёт не поехал.
            "requests=MAX(usage_daily.requests, excluded.requests), "
            "values_total=MAX(usage_daily.values_total, excluded.values_total), "
            "reports=usage_daily.reports+1, updated_at=excluded.updated_at",
            (org_id, instance_id, day, requests, values_total, now),
        )

    def usage_history(self, org_id: str, days: int = 30) -> list[dict[str, object]]:
        """Накопительные счётчики организации по суткам, старые первыми.

        МОЛЧАВШИЙ ИНСТАНС ПЕРЕНОСИТСЯ ВПЕРЁД, А НЕ ИСЧЕЗАЕТ, и без этого ряд
        получался НЕ МОНОТОННЫМ. Считать `SUM(...) GROUP BY day` — значит взять
        сумму по тем инстансам, которые отчитались именно в эти сутки: два
        инстанса в понедельник и один во вторник дают падение, разность соседних
        суток становится отрицательной, и последняя точка расходится с
        `usage_totals`, который суммирует все инстансы, какие вообще видел.
        Инстанс молчит не когда обнулился, а когда его остановили или он не успел
        отчитаться в эти сутки; его накопительный итог никуда не делся.

        Перенос делается здесь, а не в SQL: оконная функция дала бы то же самое
        ценой зависимости от версии SQLite внутри SQLCipher, а строк тут — сутки
        на инстансы одной организации.
        """
        window = max(1, min(int(days), 365))
        rows = self._fetchall(
            "SELECT day, instance_id, requests, values_total, reports "
            "FROM usage_daily WHERE org_id=? ORDER BY day", (org_id,))
        latest: dict[str, tuple[int, int]] = {}
        by_day: dict[str, dict[str, object]] = {}
        for day, instance_id, requests, values_total, reports in rows:
            latest[instance_id] = (int(requests or 0), int(values_total or 0))
            bucket = by_day.setdefault(day, {"day": day, "reports": 0})
            bucket["reports"] = int(bucket["reports"]) + int(reports or 0)
            # Итог суток — состояние ВСЕХ известных инстансов на конец этих
            # суток, включая тех, кто сегодня промолчал.
            bucket["requests"] = sum(value[0] for value in latest.values())
            bucket["values"] = sum(value[1] for value in latest.values())
            bucket["instances"] = len(latest)
        return [by_day[day] for day in sorted(by_day)][-window:]

    def fleet_totals(self, window_seconds: int) -> dict[str, object]:
        """One row of numbers about the WHOLE fleet, for the scrape.

        AGGREGATED IN SQL AND NOT BY WALKING `list_orgs()`. The console reads
        per-organisation rows because a human is going to look at one of them;
        a scrape every fifteen seconds must not carry a cost that grows with the
        customer base, and `/admin/list` is the operator-only catalogue anyway.

        `breaks_by_org` is the ONE thing labelled by organisation, and only
        organisations that actually have a break appear in it. Prometheus keeps
        a series per label combination for ever, so labelling by customer
        normally means the series count grows with sales and never shrinks —
        here it grows with TROUBLE, which is bounded, drops back to nothing when
        the trouble is fixed, and is exactly the list somebody needs to be handed
        rather than to go looking for.
        """
        totals = self._fetchone(
            "SELECT COUNT(DISTINCT org_id), COALESCE(SUM(requests), 0), "
            "COALESCE(SUM(values_total), 0), 0, "
            "COALESCE(SUM(unverified_reports), 0), COALESCE(SUM(malformed_reports), 0), "
            "COALESCE(SUM(reports_missing), 0), COALESCE(SUM(resets), 0) FROM usage", ()
        ) or (0, 0, 0, 0, 0, 0, 0, 0)
        keys = self._fetchall("SELECT status, COUNT(*) FROM keys GROUP BY status", ())
        cutoff = time.time() - window_seconds
        # СЧИТАЮТСЯ ЛИЧНОСТИ, А НЕ СТРОКИ, и разница здесь кратная. `lease_id`
        # свежий на КАЖДОМ продлении, а `released_at` ставится только при явном
        # освобождении: при TTL 86400 и продлении через TTL//3 один живой воркер
        # оставляет в окне три-четыре строки, и `COUNT(*)` завысил бы флот
        # втрое. Считается `pubkey` — единственный идентификатор, который клиент
        # НЕ выбирает: он рождается в памяти воркера, на него запечатывается
        # бандл, и два процесса не могут иметь один и тот же, не будучи
        # пропатченными.
        #
        # Инстанс считается ПАРОЙ с организацией: `instance_id` приходит из
        # переменной окружения, то есть его выбирает клиент, и два разных
        # клиента, оставивших умолчание, слились бы в один. SQLite не умеет
        # `COUNT(DISTINCT a, b)`, отсюда подзапрос.
        live = "FROM leases WHERE issued_at >= ? AND released_at IS NULL"
        instances = self._fetchone(
            f"SELECT (SELECT COUNT(DISTINCT org_id) {live}), "
            f"(SELECT COUNT(*) FROM (SELECT DISTINCT org_id, instance_id {live})), "
            f"(SELECT COUNT(DISTINCT pubkey) {live})",
            (cutoff, cutoff, cutoff)) or (0, 0, 0)
        # ЦЕПЬ БЕРЁТСЯ ИЗ `process_reports`, А НЕ ИЗ `usage`, и это не выбор
        # источника, а исправление. `usage.chain_breaks` ПЕРЕЗАПИСЫВАЕТСЯ
        # накопительным счётчиком того процесса, чей отчёт пришёл последним, —
        # при нескольких воркерах на инстанс число скачет и может УМЕНЬШАТЬСЯ.
        # Экспортированное как `counter` и опрошенное через `increase()`, оно
        # рисовало бы призрачные сбросы и приросты. `process_reports` хранит
        # строку на (организация, процесс) и растёт только вверх — и это же то,
        # что суммирует `/admin/chains`, так что метрика и консоль больше не
        # спорят.
        broken = self._fetchall(
            "SELECT org_id, SUM(chain_breaks) FROM process_reports GROUP BY org_id "
            "HAVING SUM(chain_breaks) > 0", ())
        chain_total = self._fetchone(
            "SELECT COALESCE(SUM(chain_breaks), 0) FROM process_reports", ()) or (0,)
        return {
            "orgs_with_usage": int(totals[0] or 0),
            "requests": int(totals[1] or 0),
            "values": int(totals[2] or 0),
            "chain_breaks": int(chain_total[0] or 0),
            "unverified_reports": int(totals[4] or 0),
            "malformed_reports": int(totals[5] or 0),
            "reports_missing": int(totals[6] or 0),
            "resets": int(totals[7] or 0),
            "keys_by_status": {str(row[0] or "unknown"): int(row[1] or 0) for row in keys},
            "orgs_serving": int(instances[0] or 0),
            "instances_serving": int(instances[1] or 0),
            "processes_serving": int(instances[2] or 0),
            "breaks_by_org": {str(row[0]): int(row[1] or 0) for row in broken},
        }

    def chain_detail(self, org_id: str, limit: int = 200) -> dict[str, object]:
        """Строки цепи отчётов по каждому ПРОЦЕССУ организации.

        `usage_totals` отдаёт СУММУ разрывов по организации — число, по которому
        видно, что что-то не так, и совершенно нечего делать дальше. Это
        детализация за ним: какой процесс, на каком месте цепи, когда последний
        раз слышали. Ключ процесса режется до префикса — целиком он нужен только
        для сверки подписи, а на экране это шум, который вдобавок приглашает
        куда-нибудь его скопировать.

        ОГРАНИЧЕН, КАК И ВСЯКОЕ ДРУГОЕ ПЕРЕЧИСЛЕНИЕ ЗДЕСЬ. `process_reports`
        получает строку на КАЖДЫЙ воркер на КАЖДЫЙ перезапуск — ключ процесса
        живёт ровно столько, сколько процесс, — и не чистится ничем. У давнего
        клиента на старшем тарифе это десятки тысяч строк, и собирать их все
        значит держать лок store, который в этот момент нужен `may_lease`, чтобы
        выдавать аренды всем остальным.
        """
        window = max(1, min(int(limit), 1000))
        total = self._fetchone(
            "SELECT COUNT(*), COALESCE(SUM(chain_breaks), 0) "
            "FROM process_reports WHERE org_id=?", (org_id,))
        rows = self._fetchall(
            "SELECT pubkey, seq, prev, chain_breaks, build_changes, build, updated_at "
            "FROM process_reports WHERE org_id=? "
            # Порванные первыми: если строк больше, чем влезает, отрезать надо
            # тишину, а не сигнал.
            "ORDER BY chain_breaks DESC, updated_at DESC LIMIT ?",
            (org_id, window))
        return {
            "processes": [{"pubkey": (r[0] or "")[:16], "seq": int(r[1] or 0),
                           "prev": (r[2] or "")[:16], "chain_breaks": int(r[3] or 0),
                           "build_changes": int(r[4] or 0), "build": (r[5] or "")[:24],
                           "updated_at": r[6]}
                          for r in rows],
            # Сумма считается по ВСЕМ строкам, а не по показанным: иначе экран,
            # обрезанный лимитом, показывал бы разрывов меньше, чем их есть.
            "processes_total": int(total[0] or 0) if total else 0,
            "chain_breaks": int(total[1] or 0) if total else 0,
        }

    def record_missing_report(self, org_id: str, instance_id: str) -> None:
        """Продление без отчёта, хотя `lease_id` в теле есть.

        `lease_id` клиент шлёт с самого начала, и сервер его НЕ ЧИТАЛ вовсе —
        поэтому «это продление, отчёт обязан быть» установить было нечем.
        Теперь установить есть чем, и молчание стало записью.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, "
                "reports_missing) VALUES (?,?,?,0,1) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                "updated_at=excluded.updated_at, "
                "reports_missing=usage.reports_missing+1",
                (org_id, instance_id, time.time()))
            self._conn.commit()

    def record_malformed(self, org_id: str, instance_id: str) -> None:
        """Отчёт пришёл и не разобрался. Считается отдельно от всего.

        Раньше такой отчёт ронял сервер в 500, а 500 у клиента grace-worthy —
        то есть отравить собственный отчёт было способом уехать в grace, не
        трогая сеть. Теперь это запись, и она видна в итогах: инвойс не должен
        путать «расхода не было» с «расход был, но мы его не прочитали».
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage (org_id, instance_id, updated_at, reports, "
                "malformed_reports) VALUES (?,?,?,0,1) "
                "ON CONFLICT(org_id, instance_id) DO UPDATE SET "
                "updated_at=excluded.updated_at, "
                "malformed_reports=usage.malformed_reports+1",
                (org_id, instance_id, time.time()))
            self._conn.commit()

    def _chain_breaks(self, org_id: str, instance_id: str, seq: int, prev: str,
                      trust: str, report_pubkey: str = "") -> int:
        """Разрывы цепи отчётов ОДНОГО ПРОЦЕССА.

        Строка заведена под ключ процесса, поэтому перезапуск — это новая
        строка, а не особый случай: `seq` внутри одной строки обязан расти на
        единицу, `prev` — совпадать с хешем нашей записанной подписи. Повтор
        старого отчёта и вечная единица ловятся этим же условием, без отдельной
        эвристики про «мнимый перезапуск», которая была нужна, только пока
        строка делилась между воркерами.
        """
        if not report_pubkey:
            return 0
        row = self._fetchone(
            "SELECT seq, signature, chain_breaks FROM process_reports "
            "WHERE org_id=? AND pubkey=?", (org_id, report_pubkey),
        )
        if row is None:
            return 0
        last_seq, last_signature, breaks = (int(row[0] or 0), row[1] or "",
                                            int(row[2] or 0))
        if last_seq == 0:
            return breaks
        expected_prev = hashlib.sha256(last_signature.encode("ascii")).hexdigest()
        if seq == last_seq + 1 and (not prev or prev == expected_prev):
            return breaks
        _log.warning("usage chain break for org=%s pubkey=%s: seq %d -> %d, prev %s "
                     "(trust=%s)", org_id, report_pubkey[:12], last_seq, seq,
                     "ok" if prev == expected_prev else "mismatch", trust)
        return breaks + 1

    def _record_process_report(self, org_id: str, pubkey: str, seq: int,
                               prev: str, signature: str, breaks: int) -> None:
        # UPSERT, А НЕ UPDATE. Строка процесса создаётся при выдаче секрета, но
        # отчёт может прийти и для ключа, которому мы секрета не выдавали, — и
        # тогда `UPDATE` молча ничего не делал, `seq` навсегда оставался нулём,
        # а `_chain_breaks` возвращал ноль на любой последовательности. Вечная
        # единица проходила незамеченной.
        with self._lock:
            self._conn.execute(
                "INSERT INTO process_reports (org_id, pubkey, seq, prev, signature, "
                "chain_breaks, updated_at) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, pubkey) DO UPDATE SET seq=excluded.seq, "
                "prev=excluded.prev, signature=excluded.signature, "
                "chain_breaks=excluded.chain_breaks, updated_at=excluded.updated_at",
                (org_id, pubkey, seq, prev, signature, breaks, time.time()),
            )
            self._conn.commit()

    # How many containers each plan may run at once. THE ONE THING WE ENFORCE,
    # and the only thing that can be enforced: it is decided here, on our side,
    # when a lease is requested. Everything the container reports about itself —
    # values, requests, rate — is produced on the customer's hardware and can
    # say anything, so none of it can be a plan boundary.
    #
    # Instances are also the honest proxy for scale: one container handles a
    # given load, and more traffic needs more of them.
    PLAN_INSTANCES = {"start": 1, "work": 4, "industrial": 12, "enterprise": 100}
    # ПОТОЛОК ПРОЦЕССОВ НА КОНТЕЙНЕР. Тариф ПУБЛИКУЕТСЯ в контейнерах, а
    # ПРИНУЖДАЕТСЯ в процессах, потому что `instance_id` приходит из переменной
    # окружения (`service.py`), которую ставит клиент: пятьдесят контейнеров с
    # одним значением читались как один инстанс, и тариф обходился одной строкой
    # в compose-файле. Ключ процесса — единственное, что клиент не выбирает.
    #
    # Число щедрое намеренно. `entrypoint.sh` берёт воркеров по числу ядер, и
    # отказать честному клиенту на большой машине хуже, чем пропустить лишнее:
    # обход тарифа этим потолком становится дороже ровно настолько, насколько
    # клиенту придётся поднимать контейнеры с малым числом воркеров, то есть
    # тратить память впустую. 32 покрывает любой разумный узел.
    PROCESSES_PER_INSTANCE = 32
    # СКОЛЬКО СЛОТ ОСТЫВАЕТ ПОСЛЕ ОСВОБОЖДЕНИЯ.
    #
    # Выбрано НЕ по времени редеплоя, а по цене трюка, и вот почему редеплой
    # этим не задет вовсе: `instance_id` — это `AUDIT.installation_id()`, то
    # есть идентификатор ТОМА, а документированная команда запуска содержит
    # `-v pseudex-data:/data`. Значит `docker stop` -> `docker run` на том же
    # томе приходит с ТЕМ ЖЕ идентификатором и проходит по ветке «этот инстанс
    # уже держит слот». Платит только тот, у кого личность контейнера
    # действительно новая, — то есть ровно тот, кто крутит контейнеры по кругу.
    RELEASE_COOLDOWN_SECONDS = int(
        os.environ.get("PSEUDEX_RELEASE_COOLDOWN_SECONDS", "300"))
    # Остывание ограничивает ТЕМП, но не количество. Второй рычаг — бюджет:
    # сверх него `/v1/release` ничего не делает, и слот истекает по TTL, как до
    # появления ручки. Честному клиенту это ничего не стоит: `_release` на
    # выключении и так глотает любую ошибку.
    RELEASE_BUDGET_PER_HOUR = int(
        os.environ.get("PSEUDEX_RELEASE_BUDGET_PER_HOUR", "0")) or 0
    # Mirrors billing/management/commands/seed_plans.py. Two places, because
    # the licensing server must not depend on the storefront — but they are
    # checked against each other by test_storefront.py.

    # СКОЛЬКО ЗАПРОСОВ ДАЁТ ОДНА АРЕНДА. Гранулярность — компромисс: мелкий
    # грант точнее считает и чаще ходит к нам, крупный наоборот. Порядок «час
    # ожидаемого трафика» выбран так, чтобы клиент, остановившийся посреди
    # гранта, переплатил незначительно — гранты не возвращаются, и это цена
    # того, что число неподделываемо.
    # СКОЛЬКО СЕКУНД СОБСТВЕННОГО ТРАФИКА КЛИЕНТА СОСТАВЛЯЮТ КВАНТ И РЕЗЕРВ.
    #
    # Погрешность счёта при таком выборе равна `(τ_Q + τ_R) / период` и НЕ
    # зависит ни от объёма, ни от числа воркеров, ни от тарифа. При 300 с и 6 ч
    # это 0.84% в худшем случае — когда цепь отчётов порвана и счёт идёт по
    # потолку, — и РОВНО НОЛЬ, когда отчёты доходят.
    #
    # Квант вносит в эту цифру 23 миллионных, резерв — почти всё. Поэтому квант
    # выгодно делать КРУПНЫМ (в пять раз меньше обращений при той же точности),
    # а торговаться стоит за часы резерва: каждый час страховки от НАШЕГО
    # простоя стоит 0.14% худшей погрешности.
    METER_TARGET_SECONDS = int(os.environ.get("PSEUDEX_METER_TARGET_SECONDS", "300"))
    RESERVE_SECONDS = int(os.environ.get("PSEUDEX_RESERVE_SECONDS", str(6 * 3600)))
    # Порог предвыборки внутри РЕЗЕРВА: движок идёт за следующим квантом, пока
    # страховка ещё цела. Резерв — страховка, а не оборотный капитал.
    PREFETCH_FRACTION = 0.25

    # Нижние и верхние границы кванта и резерва по тарифам. Нижняя нужна, чтобы
    # почти простаивающий процесс не ходил к нам за единицами; верхняя — чтобы
    # всплеск не выдал вперёд месячный объём.
    QUANTUM_BOUNDS = {"start": (200, 2_000), "work": (200, 10_000),
                      "industrial": (500, 40_000), "enterprise": (500, 100_000)}
    RESERVE_MAX = {"start": 20_000, "work": 100_000,
                   "industrial": 400_000, "enterprise": 2_000_000}

    PLAN_GRANT = {"start": 5_000, "work": 25_000, "industrial": 100_000,
                  "enterprise": 500_000}

    _PLAN_FIELDS = ("max_instances", "processes_per_instance", "grant_size",
                    "quantum_min", "quantum_max", "reserve_max")

    def plan_row(self, plan: str) -> dict[str, object] | None:
        """Числа тарифа, или `None`, если такого тарифа нет.

        ЕДИНСТВЕННЫЙ ЧИТАТЕЛЬ ТАБЛИЦЫ, и все, кому нужен тариф, идут через него.
        Кеша здесь нет НАМЕРЕННО: кеш вернул бы ровно ту болезнь, ради которой
        таблица заводилась, — правка перестала бы действовать до перезапуска.
        Цена нулевая: чтение по первичному ключу, и зовут его на аренде и раз в
        225 секунд на процесс, а не на пути запроса.
        """
        row = self._fetchone(
            "SELECT code, max_instances, processes_per_instance, grant_size, "
            "quantum_min, quantum_max, reserve_max, updated_at, updated_by "
            "FROM plans WHERE code=?", (plan,))
        if row is None:
            return None
        return {"code": row[0], "max_instances": int(row[1] or 0),
                "processes_per_instance": int(row[2] or 0),
                "grant_size": int(row[3] or 0), "quantum_min": int(row[4] or 0),
                "quantum_max": int(row[5] or 0), "reserve_max": int(row[6] or 0),
                "updated_at": row[7],
                # Пустой `updated_by` — строка как её посеяли. Непустой — здесь
                # правили руками, и константа в коде больше не описывает
                # реальность. Это единственное, что отличает одно от другого
                # снаружи, поэтому оно и отдаётся.
                "source": "edited" if (row[8] or "") else "seed",
                "updated_by": row[8] or ""}

    def plans(self) -> list[dict[str, object]]:
        """Все тарифы, в порядке потолка инстансов — от младшего к старшему."""
        rows = self._fetchall("SELECT code FROM plans ORDER BY max_instances", ())
        return [row for row in (self.plan_row(r[0]) for r in rows) if row]

    def set_plan(self, code: str, values: dict[str, object], actor: str) -> dict:
        """Создать или поправить тариф. Возвращает строку, какой она стала.

        `actor` обязателен и пишется в `updated_by`: строка, которую правили,
        обязана отличаться от посеянной, иначе `source` — выдумка. Роль та же,
        что у `actor` в журнале раскрытий: запись о том, кто это сделал.
        """
        current = self.plan_row(code) or {field: 0 for field in self._PLAN_FIELDS}
        merged = {field: int(values.get(field, current.get(field, 0)) or 0)
                  for field in self._PLAN_FIELDS}
        # ПРОВЕРЯЕТСЯ ДО ЗАПИСИ И НА СЛИТОЙ СТРОКЕ, а не на теле запроса.
        #
        # До записи — потому что иначе несогласованная строка успевает лечь на
        # диск и остаётся там после отказа: вызывающий видит 400 и считает, что
        # ничего не произошло. На слитой — потому что править можно одно поле из
        # пары, и тогда противоречие рождается сложением нового значения с тем,
        # что уже лежало, а в теле запроса его не видно вовсе.
        #
        # `issue_quantum` зажимает квант между этими двумя, так что перевёрнутая
        # пара молча делает потолок ниже пола.
        # КАЖДОЕ ПОЛЕ ОБЯЗАНО БЫТЬ ПОЛОЖИТЕЛЬНЫМ, И ЭТО ПРО СОЗДАНИЕ НОВОГО
        # ТАРИФА, А НЕ ПРО ПРАВКУ СУЩЕСТВУЮЩЕГО.
        #
        # `current` для неизвестного кода — нули, поэтому запрос вида
        # `{"code": "gold", "max_instances": 4}` создавал строку, где всё
        # остальное ноль. Дальше `known_plan` такой тариф признаёт, а
        # `may_lease` считает `ceiling = allowed * 0 = 0` и отказывает клиенту в
        # ПЕРВОЙ ЖЕ аренде; нулевой `quantum_max` делает то же с ёмкостью.
        # Проверка на `quantum_min > quantum_max` на паре 0/0 не срабатывает, а
        # диапазонная проверка в ручке видит только присланные поля.
        zeroed = sorted(field for field in self._PLAN_FIELDS if merged[field] < 1)
        if zeroed:
            raise ValueError(
                f"plan {code} would have non-positive {', '.join(zeroed)}; "
                "a new plan must name every field")
        if merged["quantum_min"] > merged["quantum_max"]:
            raise ValueError(
                f"quantum_min {merged['quantum_min']} above quantum_max "
                f"{merged['quantum_max']} for plan {code}")
        with self._lock:
            self._conn.execute(
                "INSERT INTO plans (code, max_instances, processes_per_instance, "
                "grant_size, quantum_min, quantum_max, reserve_max, updated_at, "
                "updated_by) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(code) DO UPDATE SET "
                "max_instances=excluded.max_instances, "
                "processes_per_instance=excluded.processes_per_instance, "
                "grant_size=excluded.grant_size, quantum_min=excluded.quantum_min, "
                "quantum_max=excluded.quantum_max, reserve_max=excluded.reserve_max, "
                "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                (code, merged["max_instances"], merged["processes_per_instance"],
                 merged["grant_size"], merged["quantum_min"], merged["quantum_max"],
                 merged["reserve_max"], time.time(), actor),
            )
            self._conn.commit()
        return self.plan_row(code) or {}

    def known_plan(self, plan: str) -> bool:
        """Есть ли такой тариф вообще.

        СПРАШИВАЕТСЯ ПРИ ВЫПУСКЕ КЛЮЧА, ПОТОМУ ЧТО ДАЛЬШЕ КАЖДЫЙ LOOKUP МОЛЧА
        ПОДСТАВЛЯЕТ УМОЛЧАНИЕ. `instances_allowed` откатывался на 1, `grant_size`
        на 5 000, границы кванта и резерва — на значения «старта»: тариф, которого
        нет, не ломался, он тихо становился самым младшим. `/admin/issue`
        подставлял `"standard"`, которого нет нигде, поэтому ключ без явного
        тарифа был невидимым «стартом» независимо от того, что купили.
        """
        return self.plan_row(plan) is not None

    def known_plans(self) -> list[str]:
        """Тарифы, которые есть, — чтобы отказ называл допустимое, а не только
        недопустимое."""
        return sorted(row["code"] for row in self.plans())

    def grant_size(self, plan: str) -> int:
        row = self.plan_row(plan)
        return row["grant_size"] if row else 5_000

    def record_grant(self, org_id: str, pubkey: str, size: int) -> None:
        """ВЫДАННОЕ КОПИТСЯ У НАС И НЕ ЗАВИСИТ НИ ОТ ЧЕГО, ЧТО ПРИШЛО СНАРУЖИ.

        Это и есть счёт: клиент не может занизить число, которое мы записали
        сами, а перестать просить он может только перестав обслуживать.
        """
        with self._lock:
            self._conn.execute(
                "INSERT INTO grants (org_id, pubkey, granted, issued_at) "
                "VALUES (?,?,?,?) ON CONFLICT(org_id, pubkey) DO UPDATE SET "
                "granted=grants.granted+excluded.granted, issued_at=excluded.issued_at",
                (org_id, pubkey, size, time.time()),
            )
            self._conn.commit()

    def meter_row(self, org_id: str, pubkey: str) -> dict[str, object]:
        row = self._fetchone(
            "SELECT quantum_seq, quantum_size, reserve, granted, acked, acked_at, "
            "unacked_quanta, ack_regressions, prefetch_at "
            "FROM meter WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        if row is None:
            return {"quantum_seq": 0, "quantum_size": 0, "reserve": 0,
                    "granted": 0, "acked": 0, "acked_at": 0.0,
                    "unacked_quanta": 0, "ack_regressions": 0, "prefetch_at": 0}
        return {"quantum_seq": int(row[0] or 0), "quantum_size": int(row[1] or 0),
                "reserve": int(row[2] or 0), "granted": int(row[3] or 0),
                "acked": int(row[4] or 0), "acked_at": float(row[5] or 0.0),
                "unacked_quanta": int(row[6] or 0),
                "ack_regressions": int(row[7] or 0),
                "prefetch_at": int(row[8] or 0)}

    MIN_METER_INTERVAL_SECONDS = 1.0

    def metered_too_recently(self, org_id: str, pubkey: str, now: float) -> bool:
        """Просил ли этот процесс квант меньше секунды назад."""
        row = self._fetchone(
            "SELECT updated_at FROM meter WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        if row is None or row[0] is None:
            return False
        return now - float(row[0]) < self.MIN_METER_INTERVAL_SECONDS

    def issue_quantum(self, org_id: str, pubkey: str, plan: str,
                      acked: int | None, now: float) -> dict[str, int]:
        """Выдать следующий квант ёмкости. ОДНА транзакция, одна запись.

        `acked` — подтверждённый расход процесса, или `None`, если отчёта не
        было или он не сошёлся. Тогда шаг СЛЕПОЙ: считаем, что предыдущий квант
        выбран целиком. Слепой шаг не может быть выгоднее честного — он
        завышает, — и это то, что делает молчание невыгодным без единого
        механизма принуждения.

        ЦЕЛЬ, А НЕ ПРИБАВКА. `granted += Q` — это учёт по числу ОБРАЩЕНИЙ, то
        есть по времени: ровно тот дефект, из-за которого простаивающий воркер
        накапливал 45 000 выданных за полторы минуты и тринадцать запросов.
        `granted = max(granted, consumed + Q + R)` делает прирост равным
        расходу, а разрыв `granted - consumed` — КОНСТАНТОЙ на процесс.
        """
        with self._lock:
            row = self.meter_row(org_id, pubkey)
            regressed = acked is not None and acked < row["acked"]
            if acked is None or regressed:
                # СЛЕПАЯ ОЦЕНКА — ЭТО ПОРОГ ПРЕДВЫБОРКИ, А НЕ «ПОТОЛОК МИНУС
                # КВАНТ». Движок приходит за следующим квантом ТОЛЬКО перейдя
                # порог, поэтому сам факт прихода и есть измерение: он обслужил
                # не меньше, чем `prefetch_at`.
                #
                # Первая версия считала `granted - quantum_size`, и на первом же
                # слепом шаге это давало НОЛЬ (потолок 200 при кванте 200), то
                # есть занижала счёт ровно там, где снятие отчёта и должно было
                # стать невыгодным. Найдено прогоном: расход 150, к счёту 0.
                consumed = max(row["prefetch_at"], row["acked"])
                trust_step = "blind"
            else:
                consumed = acked
                trust_step = "acked"

            elapsed = now - row["acked_at"] if row["acked_at"] else 0.0
            gained = max(0, consumed - row["acked"])
            rate = gained / elapsed if elapsed > 1.0 else 0.0

            # Границы кванта и резерва читаются ИЗ СТРОКИ ТАРИФА. Фолбэк —
            # «старт», как и был: тариф здесь уже проверен при выпуске ключа,
            # так что путь фолбэка означает строку, удалённую под работающим
            # клиентом, и самый тесный тариф — правильный ответ на это.
            plan_row = self.plan_row(plan)
            low = plan_row["quantum_min"] if plan_row else self.QUANTUM_BOUNDS["start"][0]
            high = plan_row["quantum_max"] if plan_row else self.QUANTUM_BOUNDS["start"][1]
            quantum = min(max(int(rate * self.METER_TARGET_SECONDS), low), high)
            # РЕЗЕРВ ВЫДАЁТСЯ СО ВТОРОГО КВАНТА. Процессу, который ещё ничего не
            # обслужил, нечего страховать от нашего простоя, а выдавая резерв
            # сразу, мы заставили бы платить за него каждый воркер каждого
            # перезапуска — дефект «грант по времени» вернулся бы другой дверью.
            if row["quantum_seq"] == 0:
                reserve = 0
            else:
                reserve_max = (plan_row["reserve_max"] if plan_row
                               else self.RESERVE_MAX["start"])
                reserve = min(max(int(rate * self.RESERVE_SECONDS), quantum),
                              reserve_max)
            granted = max(row["granted"], consumed + quantum + reserve)
            prefetch_at = max(1, granted - reserve
                              - max(1, int(quantum * self.PREFETCH_FRACTION)))
            unacked = 0 if trust_step == "acked" else row["unacked_quanta"] + 1

            self._conn.execute(
                "INSERT INTO meter (org_id, pubkey, first_seen, updated_at, "
                "quantum_seq, quantum_size, reserve, granted, acked, acked_at, "
                "ack_trust, rate_per_second, unacked_quanta, ack_regressions, "
                "prefetch_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(org_id, pubkey) DO UPDATE SET updated_at=excluded.updated_at, "
                "quantum_seq=excluded.quantum_seq, quantum_size=excluded.quantum_size, "
                "reserve=excluded.reserve, granted=excluded.granted, "
                "acked=excluded.acked, acked_at=excluded.acked_at, "
                "ack_trust=excluded.ack_trust, rate_per_second=excluded.rate_per_second, "
                "unacked_quanta=excluded.unacked_quanta, "
                "ack_regressions=meter.ack_regressions+excluded.ack_regressions, "
                "prefetch_at=excluded.prefetch_at",
                (org_id, pubkey, now, now, row["quantum_seq"] + 1, quantum, reserve,
                 granted, max(consumed, row["acked"]), now, trust_step, rate,
                 unacked, 1 if regressed else 0, prefetch_at))
            self._conn.commit()
        if regressed:
            _log.warning("consumed went backwards under one process key for "
                         "org=%s pubkey=%s: %d -> %s", org_id, pubkey[:12],
                         row["acked"], acked)
        return {"quantum_seq": row["quantum_seq"] + 1, "quantum_size": quantum,
                "reserve": reserve, "grant_total": granted,
                "prefetch_at": prefetch_at}

    def billable(self, org_id: str) -> dict[str, int]:
        """Сколько выставить. ПОДТВЕРЖДЁННОЕ, ЗАЖАТОЕ ВЫДАННЫМ.

        `clamp(acked, granted - Q - R, granted)` на каждый процесс, и сумма.
        Верхнюю границу клиент не перепрыгнет — без гранта движок не
        обслуживает; нижнюю не продавит — она наша запись. Значит отчёт двигает
        счёт только ВНУТРИ полосы шириной `Q + R`, и снять его — значит
        отказаться от скидки за неиспользованное, а не спрятать расход.
        """
        rows = self._fetchall(
            "SELECT granted, acked, quantum_size, reserve, unacked_quanta "
            "FROM meter WHERE org_id=?", (org_id,))
        billable = ceiling = acknowledged = unacked = 0
        for granted, acked, quantum, reserve, row_unacked in rows:
            floor = max(0, int(granted or 0) - int(quantum or 0) - int(reserve or 0))
            billable += min(max(int(acked or 0), floor), int(granted or 0))
            ceiling += int(granted or 0)
            acknowledged += int(acked or 0)
            unacked += int(row_unacked or 0)
        return {"billable": billable, "granted": ceiling, "acked": acknowledged,
                "processes": len(rows), "unacked_quanta": unacked}

    def _record_build(self, org_id: str, pubkey: str, build: str,
                      trust: str) -> None:
        """Какая сборка отчиталась, и менялась ли она под одним ключом процесса.

        Ключ процесса живёт ровно столько же, сколько процесс, поэтому у ЧЕСТНОГО
        процесса мера под ним меняться не может: тот же процесс исполняет тот же
        файл. Смена — это либо подмена отчёта, либо сборка, которая врёт о себе;
        и то и другое стоит записать с датой, а не обсуждать по памяти. Это
        доказуемость, а не невозможность: пропатченный бинарник соврёт и о мере
        тоже.
        """
        if not build or trust != "signed":
            return
        row = self._fetchone(
            "SELECT build FROM process_reports WHERE org_id=? AND pubkey=?",
            (org_id, pubkey))
        previous = (row[0] or "") if row else ""
        with self._lock:
            if previous and previous != build:
                _log.warning("build measurement CHANGED under one process key for "
                             "org=%s pubkey=%s: %s -> %s", org_id, pubkey[:12],
                             previous[:20], build[:20])
                self._conn.execute(
                    "UPDATE process_reports SET build_changes=build_changes+1 "
                    "WHERE org_id=? AND pubkey=?", (org_id, pubkey))
            self._conn.execute(
                "UPDATE process_reports SET build=? WHERE org_id=? AND pubkey=?",
                (build, org_id, pubkey))
            self._conn.commit()

    def builds_seen(self, org_id: str) -> list[dict[str, object]]:
        rows = self._fetchall(
            "SELECT build, count(*), sum(build_changes) FROM process_reports "
            "WHERE org_id=? AND build!='' GROUP BY build", (org_id,))
        return [{"build": r[0], "processes": r[1], "changes": int(r[2] or 0)}
                for r in rows]

    def granted_total(self, org_id: str) -> int:
        row = self._fetchone(
            "SELECT COALESCE(SUM(granted), 0) FROM grants WHERE org_id=?",
            (org_id,))
        return int(row[0] or 0)

    def instances_allowed(self, plan: str) -> int:
        row = self.plan_row(plan)
        return row["max_instances"] if row else 1

    def processes_allowed(self, plan: str) -> int:
        """Потолок процессов на инстанс. Тоже из строки: тариф, которому нужно
        больше воркеров на узел, теперь настраивается, а не выкатывается."""
        row = self.plan_row(plan)
        return (row["processes_per_instance"] if row
                else self.PROCESSES_PER_INSTANCE)

    def active_instances(self, org_id: str, window_seconds: int) -> list[dict]:
        """The instances currently holding a slot, newest lease first.

        The plan is sold in containers and the limit is enforced on them, but
        there was nowhere to SEE them: a persona whose single slot was held by a
        container they had already deleted was told to «остановите лишний
        контейнер или перейдите на больший тариф» — asked to stop something that
        did not exist and offered a more expensive plan as the remedy.

        The same window `may_lease` counts with, so what the customer reads is
        exactly what the limit is applied to.
        """
        now = time.time()
        cutoff = now - window_seconds
        rows = self._fetchall(
            "SELECT instance_id, MAX(issued_at), MAX(COALESCE(released_at, 0)), "
            # Пока жив ХОТЯ БЫ ОДИН воркер (released_at IS NULL) — инстанс
            # активен. `MAX(released_at)` в одиночку показывал бы обслуживающий
            # инстанс «остывающим» в ту же секунду, как остановился любой из его
            # воркеров, — ровно то враньё оператору, которое эта функция чинит.
            "SUM(CASE WHEN released_at IS NULL THEN 1 ELSE 0 END) "
            "FROM leases WHERE org_id=? AND issued_at>=? GROUP BY instance_id "
            "ORDER BY MAX(issued_at) DESC",
            (org_id, cutoff),
        )
        listed = []
        for instance_id, last_lease, released_at, live_workers in rows:
            # ЧТО ВИДИТ ПОДДЕРЖКА, ТО И ПРИМЕНЯЕТСЯ. Слот, освобождённый и ещё
            # остывающий, — не «активный» и не «свободный»; без третьего
            # состояния разговор с клиентом снова становится про контейнер,
            # которого он не видит. Но «остывает» — только когда освобождены ВСЕ
            # воркеры инстанса: пока жив хоть один, слот занят и остывать не начал.
            fully_released = not live_workers
            free_at = (float(released_at) + self.RELEASE_COOLDOWN_SECONDS
                       if fully_released and released_at else 0.0)
            cooling = fully_released and bool(released_at) and free_at > now
            listed.append({"instance_id": instance_id,
                           "last_lease": float(last_lease),
                           "state": "cooling" if cooling else "active",
                           "free_at": free_at if cooling else None})
        return listed

    def release_instance(self, org_id: str, instance_id: str) -> bool:
        """Give a slot back before its window expires. Operator lever.

        A release happens on every `docker stop`, which is every deploy, and a
        customer who recreated a volume is a NEW instance by construction — so
        without this they wait out the whole window to run the product they are
        paying for. A persona client called that disqualifying for production
        and they were right.

        ONE DEFINITION, UNDER THE SAME LOCK AS EVERY OTHER WRITE. There were two
        of these, and the second silently replaced the first: same name, same
        class, different return type and different locking. The survivor was the
        one that wrote under `with self._conn` instead of `self._lock`, which
        made slot release the only unserialized writer on a connection opened
        `check_same_thread=False` — while `devserver.py` runs the admin app on a
        second thread.
        """
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM leases WHERE org_id=? AND instance_id=?",
                (org_id, instance_id))
            self._conn.commit()
        return cursor.rowcount > 0

    def may_lease(self, org_id: str, plan: str, instance_id: str,
                  window_seconds: int, pubkey: str = "") -> tuple[bool, str]:
        """Whether this instance may take a lease under the org's plan.

        Counts instances that leased RECENTLY, not ever. A container that was
        replaced — redeploy, node move, scale-down — would otherwise occupy a
        slot forever, and the customer would hit their limit without running
        anything extra. The window is longer than the 24 h lease so a slow
        renewal never looks like a new machine.

        The instance asking is always allowed if it already holds a slot, so a
        renewal can never be refused by this check — only a genuinely NEW
        container beyond the plan can.
        """
        # The window is the LEASE TTL, not a flat constant. A lease that has
        # expired cannot be serving traffic — the engine is fail-closed and
        # stops without one — so an instance past it is definitively not
        # running, and holding its slot punishes the customer for our
        # bookkeeping. The client renews at a third of the TTL, so a live
        # instance has three chances to be seen inside the window and a slow
        # renewal never reads as a new machine.
        #
        # It used to be a flat 36 hours, which meant one `docker rm` cost the
        # customer a day and a half on a single-instance plan.
        now = time.time()
        cutoff = now - window_seconds
        # ОСВОБОЖДЁННЫЙ СЛОТ СЧИТАЕТСЯ ЗАНЯТЫМ, ПОКА ОСТЫВАЕТ. Освобождение —
        # единственный рычаг, который есть у контейнера, и без остывания оно
        # обнуляло весь потолок: проверено, пять контейнеров на тарифе в один.
        rows = self._fetchall(
            "SELECT DISTINCT instance_id, pubkey FROM leases "
            "WHERE org_id=? AND issued_at>=? AND (released_at IS NULL OR released_at>=?)",
            (org_id, cutoff, now - self.RELEASE_COOLDOWN_SECONDS),
        )
        instances = {row[0] for row in rows}
        keys = {row[1] for row in rows if row[1]}
        # ПРОДЛЕНИЕ НЕ МОЖЕТ БЫТЬ ОТКАЗАНО. Ключ процесса создаётся один раз в
        # конструкторе клиента и живёт, пока живёт процесс, поэтому «этот ключ
        # уже держит слот» — точный признак продления, а не нового контейнера.
        if pubkey and pubkey in keys:
            # КЛЮЧ ПРИВЯЗАН К ПЕРВОМУ НАЗВАВШЕМУ ЕГО ИНСТАНСУ. Без этого быстрый
            # путь «этот ключ уже держит слот» пропускал пятьсот контейнеров,
            # предъявивших ОДИН ключ, — то есть правка оказывалась хуже дыры,
            # которую чинила. Повторное использование ключа само по себе
            # означает пропатченный бинарник (ключ генерируется в памяти), но
            # это не повод делать обход бесплатным.
            owners = {row[0] for row in rows if row[1] == pubkey}
            if owners and instance_id not in owners:
                _log.warning("process key reused across instance ids for org=%s: "
                             "%s now claimed by %r, first seen under %r",
                             org_id, pubkey[:12], instance_id, sorted(owners)[:3])
                return False, (
                    "этот рабочий процесс уже учтён под другим идентификатором "
                    "контейнера. Перезапустите контейнер."
                )
            return True, ""
        allowed = self.instances_allowed(plan)
        ceiling = allowed * self.processes_allowed(plan)
        # СТАРАЯ ГРАНИЦА ОСТАЁТСЯ ВЕРХНЕЙ. Клиент, который честно называет свои
        # контейнеры, упирается в неё раньше и видит понятное сообщение про
        # контейнеры, а не про процессы.
        if instance_id not in instances and len(instances) >= allowed:
            # ОТКАЗ ОБЯЗАН НАЗВАТЬ РАБОТАЮЩИЙ ПУТЬ, А НЕ ТОЛЬКО ЗАПРЕТ. Ровно
            # та болезнь, которую лечил `active_instances`: персоне сказали
            # «остановите лишний контейнер» про контейнер, которого не было.
            # Здесь то же самое было бы про остывающий слот.
            cooling = [row[0] for row in rows
                       if row[0] not in (instance_id,)
                       and self.slot_free_at(org_id, row[0]) > now]
            hint = (
                " Один из слотов освобождён и остывает —"
                f" освободится через {int((self.slot_free_at(org_id, cooling[0]) - now) / 60) + 1} мин."
                " Так мы не даём обойти тариф чередой контейнеров."
                " Если это переразвёртывание, поднимите контейнер НА ТОМ ЖЕ ТОМЕ"
                " (-v pseudex-data:/data): он сохранит свой идентификатор и"
                " займёт слот сразу." if cooling else
                " Остановите лишний контейнер или перейдите на больший тариф."
            )
            return False, (
                f"тариф допускает {allowed} инстанс(ов), сейчас активно "
                f"{len(instances)}.{hint}"
            )
        if len(keys) >= ceiling:
            # ОТНОШЕНИЕ КЛЮЧЕЙ К ИНСТАНСАМ — НАШЕ НАБЛЮДЕНИЕ, а не то, что
            # контейнер о себе сообщил. Значение много выше правдоподобного
            # числа воркеров означает, что несколько контейнеров называются
            # одним `instance_id`.
            _log.warning("process ceiling reached for org=%s: %d keys across %d "
                         "instance ids (ratio %.1f)", org_id, len(keys),
                         len(instances), len(keys) / max(len(instances), 1))
            return False, (
                f"тариф допускает {allowed} инстанс(ов) — это {ceiling} рабочих "
                f"процессов, сейчас активно {len(keys)}."
            )
        return True, ""

    def lease_if_allowed(self, lease_id: str, org_id: str, plan: str,
                         instance_id: str, process_id: str, window_seconds: int,
                         pubkey: str) -> tuple[bool, str]:
        """Проверить потолок и занять слот В ОДНОЙ критической секции.

        ПОТОЛОК ДЕРЖАЛСЯ НА ТОМ, ЧТО КЛИЕНТЫ СТУЧАТСЯ ПО ОЧЕРЕДИ. `may_lease` и
        `record_lease` — два отдельных публичных вызова, между которыми сервер
        отпускал лок: N одновременных запросов на аренду все видели
        `len(instances) < allowed` и все проходили. Это не гонка в драйвере, это
        дыра в единственной границе, которую мы вообще принуждаем.

        Лок реентрантный, поэтому оба вызова внутри берут его повторно и это
        по-прежнему одна секция.
        """
        with self._lock:
            allowed, why_not = self.may_lease(org_id, plan, instance_id,
                                              window_seconds, pubkey=pubkey)
            if not allowed:
                return False, why_not
            self.record_lease(lease_id, org_id, instance_id, process_id,
                              window_seconds, pubkey=pubkey)
            return True, ""

    def prune_leases(self, window_seconds: int) -> int:
        """Выбросить аренды, которые давно не считаются ни в одном окне.

        `may_lease` их и так не видит; смысл в том, чтобы таблица не росла
        вечно на машине, где мы сами и живём."""
        cutoff = time.time() - 2 * window_seconds
        with self._lock:
            cursor = self._conn.execute("DELETE FROM leases WHERE issued_at<?",
                                        (cutoff,))
            self._conn.commit()
        return cursor.rowcount

    def usage_totals(self, org_id: str) -> dict[str, object]:
        """Billing view: the org's consumption, summed across its INSTANCES.

        Summing instances is right (two containers are two deployments doing real
        work); summing reports would not be, because each report restates the same
        cumulative total."""
        rows = self._fetchall(
            "SELECT instance_id, reports, requests, entities, values_total, resets, "
            # СЧЁТ ОБЯЗАН ВИДЕТЬ, ЧТО ЕМУ НЕ ПОКАЗАЛИ. Без этих двух колонок
            # инвойс не мог отличить «расхода не было» от «расход был, но его
            # никто не подтвердил».
            "unverified_reports, unverified_requests, chain_breaks, "
            "malformed_reports, reports_missing FROM usage WHERE org_id=?",
            (org_id,),
        )
        entities: dict[str, int] = {}
        requests = reports = values = resets = 0
        unverified_reports = unverified_requests = breaks = malformed = 0
        missing = 0
        for row in rows:
            (_instance, row_reports, row_requests, row_entities, row_values,
             row_resets, row_unver, row_unver_req, row_breaks, row_malformed,
             row_missing) = row
            requests += int(row_requests or 0)
            reports += int(row_reports or 0)
            values += int(row_values or 0)
            resets += int(row_resets or 0)
            unverified_reports += int(row_unver or 0)
            unverified_requests += int(row_unver_req or 0)
            breaks += int(row_breaks or 0)
            malformed += int(row_malformed or 0)
            missing += int(row_missing or 0)
            # ТЕРПИМО К ТОМУ, ЧТО УЖЕ ЛЕЖИТ. Вход теперь проверяется, но в
            # проде могут лежать строки, записанные до этого: нечисловое
            # значение здесь давало TypeError, то есть `/admin/usage` отвечал
            # 500 НАВСЕГДА для этой организации — а вместе с ним падали кабинет
            # и выставление счёта. Первая же правка обязана поднять ручку, а не
            # ждать чистки (`licensing/repair_usage.py`).
            try:
                stored = json.loads(row_entities or "{}")
            except ValueError:
                _log.warning("unreadable entities for org=%s instance=%s", org_id, _instance)
                continue
            for entity_type, count in stored.items():
                if isinstance(count, bool) or not isinstance(count, int):
                    _log.warning("non-numeric count %r for %s in org=%s instance=%s",
                                 count, entity_type, org_id, _instance)
                    continue
                entities[entity_type] = entities.get(entity_type, 0) + count
        return {"org_id": org_id, "instances": len(rows), "reports": reports,
                "requests": requests, "entities": entities,
                # THE BILLED QUANTITY. Monotonic and summed across instances,
                # because two containers are two deployments doing real work.
                "values": values,
                # Times an instance's counter went backwards. Not evidence — a
                # vault can be lost honestly — but a pattern worth seeing.
                "resets": resets,
                # ЧТО НЕ ВОШЛО В СЧЁТ И ПОЧЕМУ. Отчёт без подтверждённого MAC
                # не попадает в `requests`/`values`; он копится здесь, чтобы
                # инвойс не путал «расхода не было» с «расход не подтверждён».
                "unverified_reports": unverified_reports,
                "unverified_requests": unverified_requests,
                "chain_breaks": breaks,
                # Отчёты, которые пришли и не разобрались.
                "malformed_reports": malformed,
                # Продления, в которых отчёта не было вовсе.
                "reports_missing": missing,
                # ЧИСЛО, НА КОТОРОМ СТРОИТСЯ СЧЁТ, И ВСЁ, ЧЕМ ОНО ЗАЖАТО.
                **{f"capacity_{name}": value
                   for name, value in self.billable(org_id).items()},
                # ЧИСЛО, НА КОТОРОМ СТРОИТСЯ СЧЁТ. Сумма выданной ёмкости —
                # целиком наша запись; `requests` рядом остаётся справочным.
                "granted": self.granted_total(org_id)}

    def release_process(self, org_id: str, pubkey: str) -> bool:
        """Пометить слот процесса освобождённым. Слот остывает, а не исчезает.

        Возвращает, освободилось ли что-нибудь: раньше ручка отвечала
        `{"released": true}` даже когда ни одна строка не совпала.
        """
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE leases SET released_at=?, released_by='process' "
                "WHERE org_id=? AND pubkey=? AND released_at IS NULL",
                (time.time(), org_id, pubkey))
            self._conn.commit()
        return cursor.rowcount > 0

    def releases_last_hour(self, org_id: str) -> int:
        """Сколько раз контейнеры этой организации освобождали слот за час."""
        row = self._fetchone(
            "SELECT COUNT(*) FROM leases WHERE org_id=? AND released_by='process' "
            "AND released_at>=?", (org_id, time.time() - 3600))
        return int(row[0] or 0)

    def release_budget(self, plan: str) -> int:
        """Потолок освобождений в час. По умолчанию выводится из тарифа:
        `max(3, инстансов)` — переразвёртывание одного контейнера укладывается,
        карусель нет."""
        return self.RELEASE_BUDGET_PER_HOUR or max(3, self.instances_allowed(plan))

    def slot_free_at(self, org_id: str, instance_id: str) -> float:
        """Когда освободится последний остывающий слот этого инстанса."""
        row = self._fetchone(
            "SELECT MAX(released_at) FROM leases WHERE org_id=? AND instance_id=? "
            "AND released_at IS NOT NULL", (org_id, instance_id))
        released = float(row[0] or 0.0) if row else 0.0
        return released + self.RELEASE_COOLDOWN_SECONDS if released else 0.0

    def instances(self, org_id: str) -> list[dict[str, object]]:
        rows = self._fetchall(
            "SELECT instance_id, process_id, issued_at FROM leases WHERE org_id=? "
            "ORDER BY issued_at DESC LIMIT 100", (org_id,)
        )
        return [{"instance_id": r[0], "process_id": r[1], "issued_at": r[2]} for r in rows]

    def list_orgs(self) -> list[dict[str, object]]:
        """Каталог абонентов — ОДНА СТРОКА НА ОРГАНИЗАЦИЮ.

        Была строка на КАЖДЫЙ КЛЮЧ (`FROM keys k`), поэтому организация с тремя
        ключами троилась. Для сторожа это не косметика: он печатает `late[:20]`,
        и один клиент с тремя ключами занимал в этом списке три места из
        двадцати — то есть список «кто вот-вот встанет» тем короче, чем больше у
        клиентов ключей.

        `last_lease` ОТДАЁТСЯ ЗДЕСЬ, И ЭТО НЕ УКРАШЕНИЕ. `deploy/watch.sh` читает
        это поле, чтобы поймать клиента, который вот-вот встанет; поля не было,
        поэтому проверка «не продлевают аренду больше суток» была ВСЕГДА ПУСТОЙ —
        а это ровно тот сигнал, который поймал бы и блэкхол, и повтор лизы: и то
        и другое выглядит как «клиент перестал продлеваться».

        `plan` берётся с ПОСЛЕДНЕГО выпущенного ключа: тарифы ключей одной
        организации расходятся только при смене тарифа, и тогда верен свежий.

        `status` ОРГАНИЗАЦИИ — ЭТО «ОБСЛУЖИВАЕТСЯ ЛИ ОНА», А НЕ СТАТУС КАКОГО-ТО
        ОДНОГО КЛЮЧА. `set_status` действительно двигает все ключи разом, но
        `revoke_key_hash` отзывает РОВНО ОДИН — им и отзывают утёкший ключ, не
        останавливая клиента. Взяв статус свежайшего, каталог показал бы
        организацию отозванной ровно потому, что у неё отозвали последний
        выпущенный ключ, — при живой работе на остальных. Поэтому: есть хоть один
        активный ключ — организация активна, а полная раскладка отдаётся рядом
        (`statuses`), чтобы «активна, но один ключ отозван» было видно, а не
        додумывалось.
        """
        rows = self._fetchall(
            "SELECT k.org_id, MIN(k.created_at), COUNT(*), "
            "(SELECT MAX(issued_at) FROM leases l WHERE l.org_id=k.org_id), "
            # Тариф свежайшего ключа: коррелированный подзапрос по `created_at`,
            # а не `MAX(k.plan)` — последнее вернуло бы лексикографический
            # максимум, то есть тариф наугад.
            "(SELECT plan FROM keys k2 WHERE k2.org_id=k.org_id "
            " ORDER BY k2.created_at DESC LIMIT 1), "
            "(SELECT status FROM keys k3 WHERE k3.org_id=k.org_id "
            " ORDER BY k3.created_at DESC LIMIT 1), "
            "SUM(CASE WHEN k.status='active' THEN 1 ELSE 0 END), "
            "GROUP_CONCAT(k.status) "
            "FROM keys k GROUP BY k.org_id ORDER BY MIN(k.created_at)", ())
        catalogue = []
        for row in rows:
            active = int(row[6] or 0)
            statuses: dict[str, int] = {}
            for status in (row[7] or "").split(","):
                if status:
                    statuses[status] = statuses.get(status, 0) + 1
            catalogue.append({
                "org_id": row[0], "created_at": row[1], "keys": int(row[2] or 0),
                "last_lease": row[3], "plan": row[4],
                "status": STATUS_ACTIVE if active else row[5],
                "active_keys": active, "statuses": statuses,
            })
        return catalogue
