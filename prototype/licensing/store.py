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
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path, LICENSING_STORE)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS keys ("
            "key_hash TEXT PRIMARY KEY, org_id TEXT, plan TEXT, status TEXT, created_at REAL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS process_reports ("
            "org_id TEXT, pubkey TEXT, secret TEXT DEFAULT '', "
            "seq INTEGER DEFAULT 0, prev TEXT DEFAULT '', signature TEXT DEFAULT '', "
            "chain_breaks INTEGER DEFAULT 0, updated_at REAL, "
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
            # Доказательная часть: последний номер в цепи, хеш предыдущей
            # подписи, сама подпись и вердикт о ней. `chain_breaks` считает
            # разрывы — пропуск, перестановку или подмену старым отчётом.
            "seq INTEGER DEFAULT 0, prev TEXT DEFAULT '', signature TEXT DEFAULT '', "
            "trust TEXT DEFAULT 'unsigned', chain_breaks INTEGER DEFAULT 0, "
            "unverified_reports INTEGER DEFAULT 0, "
            "unverified_requests INTEGER DEFAULT 0, "
            "PRIMARY KEY (org_id, instance_id))"
        )
        # Существующие тома пережили релизы без этой колонки.
        columns = {row[1] for row in
                   self._conn.execute("PRAGMA table_info(leases)")}
        if "pubkey" not in columns:
            self._conn.execute("ALTER TABLE leases ADD COLUMN pubkey TEXT")
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
                             "unverified_requests INTEGER DEFAULT 0")):
            if column not in usage_columns:
                self._conn.execute(f"ALTER TABLE usage ADD COLUMN {ddl}")
        self._conn.commit()

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
        row = self._conn.execute(
            "SELECT org_id, status, plan FROM keys WHERE key_hash=?", (hash_key(key),)
        ).fetchone()
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
        row = self._conn.execute(
            "SELECT values_reported, values_total, resets FROM usage "
            "WHERE org_id=? AND instance_id=?", (org_id, instance_id),
        ).fetchone()
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
        row = self._conn.execute(
            "SELECT secret FROM process_reports WHERE org_id=? AND pubkey=?",
            (org_id, pubkey)).fetchone()
        return (row[0] or "") if row else ""

    def record_usage(self, org_id: str, instance_id: str, requests: int,
                     entities: dict[str, int], values: int, seq: int = 0,
                     prev: str = "", signature: str = "",
                     trust: str = "unsigned", report_pubkey: str = "") -> None:
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
        with self._lock:
            accumulated = self._accumulate_values(org_id, instance_id, values)
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
        row = self._conn.execute(
            "SELECT seq, signature, chain_breaks FROM process_reports "
            "WHERE org_id=? AND pubkey=?", (org_id, report_pubkey),
        ).fetchone()
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
            return breaks
        if last_seq == 0:
            return breaks
        expected_prev = hashlib.sha256(last_signature.encode("ascii")).hexdigest()
        if seq == last_seq + 1 and (not prev or prev == expected_prev):
            return breaks
        _log.warning("usage chain break for org=%s instance=%s: seq %d -> %d, "
                     "prev %s (trust=%s)", org_id, instance_id, last_seq, seq,
                     "ok" if prev == expected_prev else "mismatch", trust)
        return breaks + 1

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
    # Mirrors billing/management/commands/seed_plans.py. Two places, because
    # the licensing server must not depend on the storefront — but they are
    # checked against each other by test_storefront.py.

    def instances_allowed(self, plan: str) -> int:
        return self.PLAN_INSTANCES.get(plan, 1)

    def release_instance(self, org_id: str, instance_id: str) -> None:
        """Free a slot the moment a container shuts down cleanly.

        Without this the slot lingers for the whole window, and a customer who
        redeploys onto a fresh volume is locked out of their own product with a
        message that blames them and suggests paying more. A persona client
        called that disqualifying for production, and they were right: a release
        happens on every `docker stop`, which is every deploy.

        Best effort by construction — a container that is killed cannot tell us
        anything, which is exactly what the time-based expiry below is for.
        """
        with self._lock:
            self._conn.execute(
                "DELETE FROM leases WHERE org_id=? AND instance_id=?",
                (org_id, instance_id),
            )
            self._conn.commit()

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
        cutoff = time.time() - window_seconds
        rows = self._conn.execute(
            "SELECT instance_id, MAX(issued_at) FROM leases "
            "WHERE org_id=? AND issued_at>=? GROUP BY instance_id "
            "ORDER BY MAX(issued_at) DESC",
            (org_id, cutoff),
        ).fetchall()
        return [{"instance_id": row[0], "last_lease": float(row[1])} for row in rows]

    def release_instance(self, org_id: str, instance_id: str) -> bool:
        """Give a slot back before its window expires.

        A customer who recreated a volume is a NEW instance by construction, and
        in production the window is a day — so without this they wait a day to
        run the product they are paying for. Deleting the leases is safe: the
        engine is fail-closed and a container without a live lease is not
        serving, so a slot released by mistake costs one renewal round trip.
        """
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM leases WHERE org_id=? AND instance_id=?",
                (org_id, instance_id))
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
        cutoff = time.time() - window_seconds
        rows = self._conn.execute(
            "SELECT DISTINCT instance_id, pubkey FROM leases "
            "WHERE org_id=? AND issued_at>=?", (org_id, cutoff),
        ).fetchall()
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
        ceiling = allowed * self.PROCESSES_PER_INSTANCE
        # СТАРАЯ ГРАНИЦА ОСТАЁТСЯ ВЕРХНЕЙ. Клиент, который честно называет свои
        # контейнеры, упирается в неё раньше и видит понятное сообщение про
        # контейнеры, а не про процессы.
        if instance_id not in instances and len(instances) >= allowed:
            return False, (
                f"тариф допускает {allowed} инстанс(ов), сейчас активно "
                f"{len(instances)}. Остановите лишний контейнер или перейдите "
                f"на больший тариф."
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

    def usage_totals(self, org_id: str) -> dict[str, object]:
        """Billing view: the org's consumption, summed across its INSTANCES.

        Summing instances is right (two containers are two deployments doing real
        work); summing reports would not be, because each report restates the same
        cumulative total."""
        rows = self._conn.execute(
            "SELECT instance_id, reports, requests, entities, values_total, resets, "
            # СЧЁТ ОБЯЗАН ВИДЕТЬ, ЧТО ЕМУ НЕ ПОКАЗАЛИ. Без этих двух колонок
            # инвойс не мог отличить «расхода не было» от «расход был, но его
            # никто не подтвердил».
            "unverified_reports, unverified_requests, chain_breaks "
            "FROM usage WHERE org_id=?",
            (org_id,),
        ).fetchall()
        entities: dict[str, int] = {}
        requests = reports = values = resets = 0
        unverified_reports = unverified_requests = breaks = 0
        for row in rows:
            (_instance, row_reports, row_requests, row_entities, row_values,
             row_resets, row_unver, row_unver_req, row_breaks) = row
            requests += int(row_requests or 0)
            reports += int(row_reports or 0)
            values += int(row_values or 0)
            resets += int(row_resets or 0)
            unverified_reports += int(row_unver or 0)
            unverified_requests += int(row_unver_req or 0)
            breaks += int(row_breaks or 0)
            for entity_type, count in json.loads(row_entities or "{}").items():
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
                "chain_breaks": breaks}

    def release_process(self, org_id: str, pubkey: str) -> None:
        """Освободить слот ОДНОГО процесса, названного его собственным ключом."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM leases WHERE org_id=? AND pubkey=?", (org_id, pubkey))
            self._conn.commit()

    def instances(self, org_id: str) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT instance_id, process_id, issued_at FROM leases WHERE org_id=? "
            "ORDER BY issued_at DESC LIMIT 100", (org_id,)
        ).fetchall()
        return [{"instance_id": r[0], "process_id": r[1], "issued_at": r[2]} for r in rows]

    def list_orgs(self) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT org_id, plan, status, created_at FROM keys ORDER BY created_at"
        ).fetchall()
        return [{"org_id": r[0], "plan": r[1], "status": r[2], "created_at": r[3]}
                for r in rows]
