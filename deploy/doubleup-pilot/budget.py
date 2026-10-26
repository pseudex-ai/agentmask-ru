"""Reserve the full priced upper bound before any paid pilot request is sent.

A lost response consumes its entire reservation permanently. This is deliberately
conservative: releasing a timeout's money could buy the same unknown request a
second time. The approved dialogue model uses the maximum of fresh authenticated
metadata and pinned official peak prices. Missing proof/bounds fail closed; an
accounting correction is an additive reserve, never a fabricated new paid call.
"""

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import secrets
import re
import sqlite3
import time

NANO = Decimal(1_000_000_000)
LIMIT_NANO = 20_000_000_000  # owner raised the aggregate cap from 10 to 20 on 2026-10-24
PRICING_SOURCE = "https://litellm.inf.2up.dev/model/info"
DIALOGUE_MODEL = "deepseek-v4-flash"
# Hand-asserted from the official table fetched by the operator, not scraped or
# inferred from NULL tier fields. A new publication needs a reviewed code change.
OFFICIAL_POLICY = {
    "version": "deepseek-peak-cache-miss-flat-1m-2026-10-24-v1",
    "published_table_date": "2026-10-24",
    "official_url": "https://api-docs.deepseek.com/quick_start/pricing/",
    "selected_model": DIALOGUE_MODEL,
    "published_serving_alias": "DeepSeek-V4.1-Flash-1017",
    "context_policy": "explicit_flat_peak_cache_miss_no_context_tiers",
    "max_context_tokens": 1_000_000,
    "max_output_tokens": 393216,
    "input_cost_per_token": "0.00000030",
    "output_cost_per_token": "0.00000120",
    "safety_factor": 2,
}
METADATA_FIELDS = {"model_name", "provider", "mode", "max_input_tokens", "max_output_tokens", "max_tokens"}
RATE_KEY = re.compile(r"(?:input|output)_cost_per_token(?:_above_[1-9][0-9]*k)?\Z")


def canonical_hash(value) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError):
        raise BudgetRefused("invalid_pricing_evidence") from None
    return hashlib.sha256(encoded).hexdigest()


class BudgetRefused(RuntimeError):
    pass


def _decimal(value, *, positive=False) -> Decimal:
    try:
        if isinstance(value, bool):
            raise ValueError
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or (positive and amount == 0):
            raise ValueError
        return amount
    except (InvalidOperation, ValueError, TypeError):
        raise BudgetRefused("invalid_price") from None


def nanos(value: str | int | float | Decimal) -> int:
    return int((_decimal(value) * NANO).to_integral_value(rounding=ROUND_CEILING))


def _fresh(timestamp) -> None:
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise BudgetRefused("pricing_snapshot_stale")
    age = _decimal(time.time()) - _decimal(timestamp)
    if age < -300 or age > 86400:
        raise BudgetRefused("pricing_snapshot_stale")


def _bound(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BudgetRefused("model_bound_unavailable")
    return value


def metadata_rates(row: dict) -> tuple[Decimal, Decimal]:
    if not isinstance(row, dict) or set(row) - METADATA_FIELDS - {key for key in row if RATE_KEY.fullmatch(key)}:
        raise BudgetRefused("metadata_field_not_whitelisted")
    prices = []
    for side in ("input", "output"):
        base_key = f"{side}_cost_per_token"
        candidates = [_decimal(row.get(base_key), positive=True)]
        for key, value in row.items():
            if key.startswith(base_key + "_") and value is not None:
                candidates.append(_decimal(value, positive=True))
        # NULL means unadvertised, never free. Only the independently verified
        # official flat policy permits using the base across such absent tiers.
        prices.append(max(candidates))
    return tuple(prices)


def dialogue_rates(pricing: dict) -> tuple[Decimal, Decimal, int, int, str]:
    proof = pricing.get("dialogue_pricing")
    if not isinstance(proof, dict) or proof.get("policy") != OFFICIAL_POLICY:
        raise BudgetRefused("dialogue_price_evidence_required")
    policy_hash = canonical_hash(OFFICIAL_POLICY)
    if proof.get("policy_sha256") != policy_hash or pricing.get("source") != PRICING_SOURCE:
        raise BudgetRefused("dialogue_price_evidence_invalid")
    auth = proof.get("authenticated_metadata")
    if (not isinstance(auth, dict) or auth.get("source") != PRICING_SOURCE
            or auth.get("method") != "GET" or auth.get("authenticated") is not True
            or not isinstance(auth.get("response_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", auth["response_sha256"]) is None):
        raise BudgetRefused("authenticated_metadata_required")
    _fresh(auth.get("fetched_at"))
    rows = auth.get("rows")
    if not isinstance(rows, list) or not rows or auth.get("rows_sha256") != canonical_hash(rows):
        raise BudgetRefused("authenticated_metadata_hash_mismatch")
    input_prices = [_decimal(OFFICIAL_POLICY["input_cost_per_token"], positive=True)]
    output_prices = [_decimal(OFFICIAL_POLICY["output_cost_per_token"], positive=True)]
    contexts = [OFFICIAL_POLICY["max_context_tokens"]]
    outputs = [OFFICIAL_POLICY["max_output_tokens"]]
    for row in rows:
        if (not isinstance(row, dict) or row.get("model_name") != DIALOGUE_MODEL
                or row.get("provider") != "deepseek" or row.get("mode") != "chat"):
            raise BudgetRefused("dialogue_metadata_route_conflict")
        ip, op = metadata_rates(row)
        input_prices.append(ip)
        output_prices.append(op)
        contexts.append(_bound(row.get("max_input_tokens")))
        outputs.append(_bound(row.get("max_output_tokens")))
        outputs.append(_bound(row.get("max_tokens")))
    return max(input_prices), max(output_prices), min(contexts), min(outputs), policy_hash


def _text_request(body: dict) -> None:
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages or body.get("stream") not in (None, False):
        raise BudgetRefused("live_requires_nonstream_chat")
    if any(field in body for field in ("api_key", "api_base", "base_url", "input", "functions", "function_call")):
        raise BudgetRefused("live_route_override_refused")
    for message in messages:
        if not isinstance(message, dict):
            raise BudgetRefused("invalid_message")
        content = message.get("content")
        if content is None or isinstance(content, str):
            continue
        if not isinstance(content, list) or any(not isinstance(part, dict)
                or part.get("type") != "text" or not isinstance(part.get("text"), str) for part in content):
            raise BudgetRefused("live_multimodal_price_unbounded")


def quote(body: dict, pricing: dict) -> dict:
    _text_request(body)
    model = body.get("model")
    if not isinstance(model, str) or not model:
        raise BudgetRefused("model_required")
    if model != DIALOGUE_MODEL and "non_target_snapshot_mtime" in pricing:
        _fresh(pricing["non_target_snapshot_mtime"])
    matches = [row for row in pricing.get("models", []) if row.get("model_name") == model
               and row.get("mode") == "chat"]
    if not matches or any(row.get("input_cost_per_token") is None or row.get("output_cost_per_token") is None
                          for row in matches):
        raise BudgetRefused("model_price_unavailable")
    input_price = max(_decimal(row["input_cost_per_token"], positive=True) for row in matches)
    output_price = max(_decimal(row["output_cost_per_token"], positive=True) for row in matches)
    context_limit, output_limit, policy_hash = None, None, None
    if model == DIALOGUE_MODEL:
        ip, op, context_limit, output_limit, policy_hash = dialogue_rates(pricing)
        input_price, output_price = max(input_price, ip), max(output_price, op)
    count = body.get("n", 1)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 4:
        raise BudgetRefused("invalid_choice_count")
    bounds = [body[field] for field in ("max_completion_tokens", "max_tokens") if field in body]
    if not bounds or any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 32768 for value in bounds):
        raise BudgetRefused("explicit_output_bound_required")
    output_bound = max(bounds) * count
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    # Byte-fallback tokenizers cannot emit more source tokens than UTF-8 bytes.
    # Reserve substantial template/tool framing too, and stay below known tier
    # boundaries rather than guessing a higher-context price from a base quote.
    input_bound = len(encoded) + 32768 + 64 * len(body["messages"])
    if context_limit is not None:
        # Count all choices conservatively against context, not just one output.
        if output_bound > output_limit or input_bound + output_bound > context_limit:
            raise BudgetRefused("model_context_or_output_bound_exceeded")
    elif input_bound > 120000:
        raise BudgetRefused("large_context_tier_not_priced")
    # A twofold pricing safety factor covers gateway/provider quote drift. The
    # allowed batch is the very same payload across arms; no silent truncation.
    reserved = nanos((input_price * input_bound + output_price * output_bound) * 2)
    if reserved <= 0 or reserved > LIMIT_NANO:
        raise BudgetRefused("request_exceeds_pilot_budget")
    return {"model": model, "request_sha256": hashlib.sha256(encoded).hexdigest(),
            "input_bound": input_bound, "output_bound": output_bound,
            "input_price": str(input_price), "output_price": str(output_price),
            "reserved_nano": reserved,
            **({"pricing_policy_sha256": policy_hash,
                "published_serving_alias": OFFICIAL_POLICY["published_serving_alias"]} if policy_hash else {})}


def backup_ledger(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise BudgetRefused("ledger_not_private")
    destination = path.with_name(f"{path.name}.pre-pricing-{time.time_ns()}-{secrets.token_hex(8)}.bak")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    source = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.chmod(0o400)
    return {"file": destination.name, "sha256": digest}


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise BudgetRefused("ledger_symlink_refused")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(descriptor)
        if path.stat().st_mode & 0o077:
            raise BudgetRefused("ledger_not_private")
        with self._connect() as connection:
            connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1),
                    limit_nano INTEGER NOT NULL, violated INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, request_sha256 TEXT NOT NULL,
                    model TEXT NOT NULL, quote TEXT NOT NULL, reserved_nano INTEGER NOT NULL,
                    charged_nano INTEGER, status TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS adjustments (
                    call_id TEXT NOT NULL REFERENCES calls(id), policy_sha256 TEXT NOT NULL,
                    amount_nano INTEGER NOT NULL CHECK(typeof(amount_nano)='integer' AND amount_nano>0),
                    reason TEXT NOT NULL CHECK(reason='supplemental_accounting_reserve_not_new_spend'),
                    old_accounted_nano INTEGER NOT NULL CHECK(old_accounted_nano>=0),
                    conservative_upper_nano INTEGER NOT NULL CHECK(conservative_upper_nano>=old_accounted_nano),
                    rates_policy TEXT NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY(call_id,policy_sha256));
                CREATE TABLE IF NOT EXISTS adjustment_audit (
                    id TEXT PRIMARY KEY, policy_sha256 TEXT NOT NULL, details TEXT NOT NULL, created REAL NOT NULL);
                CREATE TRIGGER IF NOT EXISTS adjustments_no_update BEFORE UPDATE ON adjustments
                    BEGIN SELECT RAISE(ABORT,'immutable_adjustment'); END;
                CREATE TRIGGER IF NOT EXISTS adjustments_no_delete BEFORE DELETE ON adjustments
                    BEGIN SELECT RAISE(ABORT,'immutable_adjustment'); END;
                CREATE TRIGGER IF NOT EXISTS adjustment_audit_no_update BEFORE UPDATE ON adjustment_audit
                    BEGIN SELECT RAISE(ABORT,'immutable_adjustment_audit'); END;
                CREATE TRIGGER IF NOT EXISTS adjustment_audit_no_delete BEFORE DELETE ON adjustment_audit
                    BEGIN SELECT RAISE(ABORT,'immutable_adjustment_audit'); END;
            """)
            connection.execute("INSERT OR IGNORE INTO config(id,limit_nano) VALUES(1,?)", (LIMIT_NANO,))
            if connection.execute("SELECT limit_nano FROM config WHERE id=1").fetchone()[0] != LIMIT_NANO:
                raise BudgetRefused("ledger_limit_mismatch")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _accounted(connection) -> tuple[int, int]:
        calls = connection.execute("SELECT COALESCE(SUM(COALESCE(charged_nano,reserved_nano)),0) FROM calls").fetchone()[0]
        holds = connection.execute("SELECT COALESCE(SUM(amount_nano),0) FROM adjustments").fetchone()[0]
        return calls, holds

    def backup(self) -> dict:
        return backup_ledger(self.path)

    def supplement_dialogue_pricing(self, pricing: dict, backup: dict) -> dict:
        ip, op, _, _, official_hash = dialogue_rates(pricing)
        if (not isinstance(backup, dict) or not isinstance(backup.get("file"), str)
                or Path(backup["file"]).name != backup["file"]
                or re.fullmatch(r"[0-9a-f]{64}", str(backup.get("sha256"))) is None):
            raise BudgetRefused("private_backup_required")
        backup_path = self.path.with_name(backup["file"])
        if (backup_path.is_symlink() or not backup_path.is_file() or backup_path.stat().st_mode & 0o277
                or hashlib.sha256(backup_path.read_bytes()).hexdigest() != backup["sha256"]):
            raise BudgetRefused("private_backup_invalid")
        policy = {"official_policy_sha256": official_hash, "model": DIALOGUE_MODEL,
                  "input_price": str(ip), "output_price": str(op),
                  "settled_rule": "ceil_charged_times_max_new_old_ratio",
                  "unknown_rule": "max_existing_or_2x_new_rates_times_stored_bounds"}
        policy_hash = canonical_hash(policy)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT * FROM calls ORDER BY id").fetchall()
            before_calls_hash = canonical_hash(rows)
            before_base, before_holds = self._accounted(connection)
            added, adjusted = 0, 0
            for row in rows:
                identifier, _, model, raw_quote, reserved, charged, status, _ = row
                if model != DIALOGUE_MODEL:
                    continue
                if connection.execute("SELECT 1 FROM adjustments WHERE call_id=? AND policy_sha256=?",
                                      (identifier, policy_hash)).fetchone():
                    continue
                if (isinstance(reserved, bool) or not isinstance(reserved, int) or reserved <= 0
                        or charged is not None and (not isinstance(charged, int) or charged < 0)):
                    raise BudgetRefused("invalid_prior_accounting")
                estimate = json.loads(raw_quote)
                old_ip = _decimal(estimate.get("input_price"), positive=True)
                old_op = _decimal(estimate.get("output_price"), positive=True)
                accounted = reserved if charged is None else charged
                if charged is None:
                    if status not in ("reserved", "delivery_unknown", "usage_unknown"):
                        raise BudgetRefused("invalid_prior_accounting")
                    upper = nanos(2 * (max(ip, old_ip) * _bound(estimate.get("input_bound"))
                                       + max(op, old_op) * _bound(estimate.get("output_bound"))))
                else:
                    if status not in ("settled", "bound_violated"):
                        raise BudgetRefused("invalid_prior_accounting")
                    ratio = max(Fraction(1), Fraction(ip) / Fraction(old_ip), Fraction(op) / Fraction(old_op))
                    scaled = charged * ratio
                    upper = (scaled.numerator + scaled.denominator - 1) // scaled.denominator
                upper = max(accounted, upper)
                existing = connection.execute("SELECT COALESCE(SUM(amount_nano),0) FROM adjustments WHERE call_id=?",
                                              (identifier,)).fetchone()[0]
                amount = max(0, upper - accounted - existing)
                if amount:
                    if amount > 2**63 - 1:
                        raise BudgetRefused("invalid_supplemental_hold")
                    connection.execute("INSERT INTO adjustments VALUES(?,?,?,?,?,?,?,?)", (
                        identifier, policy_hash, amount, "supplemental_accounting_reserve_not_new_spend",
                        accounted, upper, json.dumps(policy, sort_keys=True), time.time()))
                    added += amount
                    adjusted += 1
            after_base, after_holds = self._accounted(connection)
            if canonical_hash(connection.execute("SELECT * FROM calls ORDER BY id").fetchall()) != before_calls_hash:
                raise BudgetRefused("prior_calls_changed")
            details = {"policy_sha256": policy_hash, "rates_policy": policy, "backup": backup,
                       "calls_sha256": before_calls_hash, "calls": len(rows),
                       "states": dict(connection.execute("SELECT status,COUNT(*) FROM calls GROUP BY status")),
                       "adjusted_calls": adjusted, "added_hold_nano": added,
                       "old_total_nano": before_base + before_holds, "new_total_nano": after_base + after_holds,
                       "supplemental_accounting_reserve_nano": after_holds, "new_paid_calls": 0}
            if added:
                connection.execute("INSERT INTO adjustment_audit VALUES(?,?,?,?)", (
                    secrets.token_hex(16), policy_hash, json.dumps(details, sort_keys=True), time.time()))
        return details

    def reserve(self, estimate: dict) -> str:
        amount = estimate.get("reserved_nano")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise BudgetRefused("invalid_reservation")
        identifier = secrets.token_hex(16)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            config = connection.execute("SELECT limit_nano,violated FROM config WHERE id=1").fetchone()
            base, holds = self._accounted(connection)
            if config[1] or base + holds + amount > config[0]:
                raise BudgetRefused("pilot_budget_exhausted")
            connection.execute("INSERT INTO calls VALUES(?,?,?,?,?,NULL,'reserved',?)", (
                identifier, estimate["request_sha256"], estimate["model"],
                json.dumps(estimate, sort_keys=True), estimate["reserved_nano"], time.time()))
        return identifier

    def unknown(self, identifier: str) -> None:
        with self._connect() as connection:
            result = connection.execute("UPDATE calls SET status='delivery_unknown' WHERE id=? AND status='reserved'", (identifier,))
            if result.rowcount != 1:
                raise BudgetRefused("ledger_transition_invalid")

    def settle(self, identifier: str, response: dict) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT quote,reserved_nano,status FROM calls WHERE id=?", (identifier,)).fetchone()
            if row is None or row[2] != "reserved":
                raise BudgetRefused("ledger_transition_invalid")
            estimate = json.loads(row[0])
            usage = response.get("usage")
            if not isinstance(usage, dict):
                connection.execute("UPDATE calls SET status='usage_unknown' WHERE id=?", (identifier,))
                return
            tokens = [usage.get("prompt_tokens"), usage.get("completion_tokens")]
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in tokens):
                connection.execute("UPDATE calls SET status='usage_unknown' WHERE id=?", (identifier,))
                return
            charged = nanos(Decimal(estimate["input_price"]) * tokens[0]
                            + Decimal(estimate["output_price"]) * tokens[1])
            violated = tokens[0] > estimate["input_bound"] or tokens[1] > estimate["output_bound"] or charged > row[1]
            if violated:
                connection.execute("UPDATE config SET violated=1 WHERE id=1")
            connection.execute("UPDATE calls SET charged_nano=?, status=? WHERE id=?", (
                max(charged, row[1]) if violated else charged,
                "bound_violated" if violated else "settled", identifier))
        if violated:
            raise BudgetRefused("provider_exceeded_reserved_bound")

    def summary(self) -> dict:
        with self._connect() as connection:
            config = connection.execute("SELECT limit_nano,violated FROM config WHERE id=1").fetchone()
            base, holds = self._accounted(connection)
            spent = base + holds
            calls = connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            states = dict(connection.execute("SELECT status,COUNT(*) FROM calls GROUP BY status").fetchall())
            adjustments = connection.execute("SELECT COUNT(*) FROM adjustments").fetchone()[0]
        return {"limit_usd": str(Decimal(config[0]) / NANO),
                "spent_or_reserved_usd": str(Decimal(spent) / NANO),
                "original_call_accounting_usd": str(Decimal(base) / NANO),
                "supplemental_accounting_reserve_usd": str(Decimal(holds) / NANO),
                "supplemental_adjustments": adjustments,
                "remaining_usd": str(max(Decimal(0), Decimal(config[0] - spent) / NANO)),
                "calls": calls, "states": states, "bound_violated": bool(config[1])}


def load_pricing(path: Path) -> dict:
    _fresh(path.stat().st_mtime)
    data = json.loads(path.read_text())
    if data.get("source") != PRICING_SOURCE:
        raise BudgetRefused("unexpected_pricing_source")
    if "dialogue_pricing" in data:
        dialogue_rates(data)
    return data
