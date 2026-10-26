"""Synthetic-only proofs of flat pricing, metadata privacy and additive holds."""

from concurrent.futures import ThreadPoolExecutor
import copy
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from budget import (BudgetRefused, DIALOGUE_MODEL, Ledger, LIMIT_NANO, OFFICIAL_POLICY,
                    PRICING_SOURCE, canonical_hash, dialogue_rates, load_pricing, nanos, quote)
import refresh_dialogue_pricing as refresh
from test_budget import BODY, PRICES


def response_fixture(**overrides):
    info = {"litellm_provider": "deepseek", "mode": "chat", "max_input_tokens": 1000000,
            "max_output_tokens": 393216, "max_tokens": 393216,
            "input_cost_per_token": 1.4e-7, "output_cost_per_token": 2.8e-7,
            **{f"{side}_cost_per_token_above_{tier}k": None
               for side in ("input", "output") for tier in (128, 200, 272, 512)}, **overrides}
    return {"data": [{"model_name": DIALOGUE_MODEL, "model_info": info,
                      "litellm_params": {"api_key": "SYNTHETIC-DO-NOT-ARCHIVE"}},
                     {"model_name": "other", "litellm_params": {"api_key": "OTHER-SYNTHETIC-SECRET"}}]}


def snapshot_fixture(**overrides):
    response = response_fixture(**overrides)
    return refresh.build_snapshot({"source": PRICING_SOURCE, **copy.deepcopy(PRICES)},
                                  response, canonical_hash(response), time.time())


def long_body(length=130000):
    return {**BODY, "model": DIALOGUE_MODEL,
            "messages": [{"role": "system", "content": "x" * length}]}


def old_estimate():
    return {**quote(BODY, PRICES), "model": DIALOGUE_MODEL}


class DialoguePricingTests(unittest.TestCase):
    def test_official_peak_dominates_low_metadata_before_2x(self):
        result = quote(long_body(), snapshot_fixture())
        self.assertEqual(Decimal(result["input_price"]), Decimal("3e-7"))
        self.assertEqual(Decimal(result["output_price"]), Decimal("1.2e-6"))
        self.assertEqual(result["reserved_nano"], nanos(2 * (Decimal("3e-7") * result["input_bound"]
                                                           + Decimal("1.2e-6") * result["output_bound"])))
        self.assertEqual(result["model"], DIALOGUE_MODEL)
        self.assertEqual(result["published_serving_alias"], "DeepSeek-V4.1-Flash-1017")
        self.assertGreater(result["input_bound"], 120000)

    def test_flat_policy_allows_exact_1m_including_output_without_mutation(self):
        body = long_body(900000)
        result = quote(body, snapshot_fixture())
        padding = 1000000 - result["input_bound"] - result["output_bound"]
        body["messages"][0]["content"] += "x" * padding
        original = copy.deepcopy(body)
        result = quote(body, snapshot_fixture())
        self.assertEqual(result["input_bound"] + result["output_bound"], 1000000)
        self.assertEqual(body, original)
        body["messages"][0]["content"] += "x"
        with self.assertRaisesRegex(BudgetRefused, "model_context_or_output_bound_exceeded"):
            quote(body, snapshot_fixture())

    def test_unknown_and_related_models_still_refuse_long_context(self):
        prices = snapshot_fixture()
        for model in ("test-model", "deepseek-v4-pro", "deepseek-v4-flash-vision-exp", "DeepSeek-V4.1-Flash-1017"):
            with self.subTest(model=model):
                prices["models"].append({**PRICES["models"][0], "model_name": model})
                with self.assertRaisesRegex(BudgetRefused, "large_context_tier_not_priced"):
                    quote({**long_body(), "model": model}, prices)

    def test_no_proof_is_not_a_short_or_long_target_fallback(self):
        prices = {"source": PRICING_SOURCE, "models": [{**PRICES["models"][0], "model_name": DIALOGUE_MODEL}]}
        for body in (long_body(), {**BODY, "model": DIALOGUE_MODEL}):
            with self.assertRaisesRegex(BudgetRefused, "dialogue_price_evidence_required"):
                quote(body, prices)

    def test_invalid_policy_or_authenticated_proof_fails_closed(self):
        mutations = [lambda p: p.pop("dialogue_pricing"),
                     lambda p: p["dialogue_pricing"].update(policy={}),
                     lambda p: p["dialogue_pricing"].update(policy_sha256="0" * 64),
                     lambda p: p["dialogue_pricing"]["policy"].update(official_url="https://api-docs.deepseek.com/quick_start/pricing"),
                     lambda p: p["dialogue_pricing"]["policy"].update(context_policy="assume_null_is_free"),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(authenticated=False),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(method="POST"),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(source="https://arbitrary.invalid"),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(response_sha256=None),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(rows_sha256="0" * 64),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(rows=[]),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(fetched_at=time.time() - 86401),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(fetched_at=time.time() + 301),
                     lambda p: p["dialogue_pricing"]["authenticated_metadata"].update(fetched_at=float("nan"))]
        for mutate in mutations:
            prices = snapshot_fixture()
            mutate(prices)
            with self.subTest(mutate=mutate), self.assertRaises(BudgetRefused):
                quote(long_body(), prices)

    def test_unpriced_invalid_nan_or_negative_base_and_tiers_are_refused(self):
        for field in ("input_cost_per_token", "output_cost_per_token", "input_cost_per_token_above_128k"):
            for value in (0, -1, "NaN", "-Infinity", "not-a-price", True, float("nan")):
                with self.subTest(field=field, value=value), self.assertRaises(BudgetRefused):
                    snapshot_fixture(**{field: value})
        for field in ("input_cost_per_token", "output_cost_per_token"):
            with self.subTest(field=field), self.assertRaises(BudgetRefused):
                snapshot_fixture(**{field: None})
        with self.assertRaises(BudgetRefused):
            snapshot_fixture(input_cost_per_token_future_conflicting=0.001)

    def test_missing_cache_prices_never_reduce_peak_reserve(self):
        first = quote(long_body(), snapshot_fixture())
        second = quote(long_body(), snapshot_fixture(cache_read_input_token_cost=0, cache_creation_input_token_cost=None))
        self.assertEqual(first["reserved_nano"], second["reserved_nano"])

    def test_positive_tiers_and_duplicate_routes_choose_max_rates_min_bounds(self):
        response = response_fixture(input_cost_per_token_above_128k=0.000002,
                                    output_cost_per_token_above_512k=0.000003)
        second = copy.deepcopy(response["data"][0])
        second["model_info"].update(max_input_tokens=800000, output_cost_per_token=0.000004)
        response["data"].append(second)
        prices = refresh.build_snapshot({"source": PRICING_SOURCE, "models": []}, response, canonical_hash(response), time.time())
        result = quote(long_body(), prices)
        self.assertEqual(Decimal(result["input_price"]), Decimal("2e-6"))
        self.assertEqual(Decimal(result["output_price"]), Decimal("4e-6"))
        with self.assertRaises(BudgetRefused):
            quote(long_body(800000), prices)

    def test_route_conflicts_missing_or_lower_model_bounds_refuse(self):
        for overrides in ({"litellm_provider": "other"}, {"mode": "embedding"}, {"max_input_tokens": None},
                          {"max_input_tokens": -1}, {"max_output_tokens": "393216"}, {"max_tokens": True}):
            with self.subTest(overrides=overrides), self.assertRaises(BudgetRefused):
                snapshot_fixture(**overrides)
        with self.assertRaises(BudgetRefused):
            quote(long_body(), snapshot_fixture(max_input_tokens=120000))
        with self.assertRaises(BudgetRefused):
            quote(long_body(), snapshot_fixture(max_output_tokens=511))
        with self.assertRaises(BudgetRefused):
            quote({**long_body(), "n": 4, "max_tokens": 32768}, snapshot_fixture(max_tokens=100000))

    def test_output_choice_text_and_route_safeguards_survive_proof(self):
        for change in ({"n": 5}, {"n": True}, {"max_tokens": 32769}, {"stream": True},
                       {"api_key": "synthetic"}, {"messages": [{"content": [{"type": "image_url"}]}]}):
            with self.subTest(change=change), self.assertRaises(BudgetRefused):
                quote({**long_body(), **change}, snapshot_fixture())

    def test_file_and_authenticated_timestamp_both_have_24h_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pricing.json"
            prices = snapshot_fixture()
            path.write_text(json.dumps(prices))
            self.assertEqual(load_pricing(path)["source"], PRICING_SOURCE)
            old = time.time() - 86401
            os.utime(path, (old, old))
            with self.assertRaises(BudgetRefused):
                load_pricing(path)
            path.write_text(json.dumps(prices))
            prices["dialogue_pricing"]["authenticated_metadata"]["fetched_at"] = old
            path.write_text(json.dumps(prices))
            with self.assertRaises(BudgetRefused):
                load_pricing(path)

    def test_refresh_preserves_non_target_rows_source_and_original_age(self):
        previous = {"source": PRICING_SOURCE, "models": copy.deepcopy(PRICES["models"]),
                    "source_note": "synthetic", "non_target_snapshot_mtime": time.time() - 86401}
        response = response_fixture()
        prices = refresh.build_snapshot(previous, response, canonical_hash(response), time.time())
        self.assertEqual(prices["models"][:-1], previous["models"])
        self.assertEqual(prices["source_note"], previous["source_note"])
        self.assertNotIn("SYNTHETIC-DO-NOT-ARCHIVE", json.dumps(prices))
        self.assertNotIn("litellm_params", json.dumps(prices))
        with self.assertRaises(BudgetRefused):
            quote(BODY, prices)
        quote(long_body(), prices)

    def test_fetch_only_fixed_authenticated_get_no_models_no_redirect(self):
        raw = json.dumps(response_fixture()).encode()
        class Reply:
            status, url = 200, PRICING_SOURCE
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, count): return raw
        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                return Reply()
        opener = Opener()
        with patch.object(refresh, "read_private", return_value="LITELLM_TOKEN=synthetic-token\n"), \
             patch.object(refresh.urllib.request, "build_opener", return_value=opener):
            response, digest, timestamp = refresh.fetch_authenticated_metadata()
        self.assertEqual(opener.request.full_url, PRICING_SOURCE)
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertIsNone(opener.request.data)
        self.assertEqual(opener.request.get_header("X-litellm-api-key"), "synthetic-token")
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
        self.assertGreater(timestamp, 0)
        self.assertEqual(response, json.loads(raw))
        with self.assertRaises(BudgetRefused):
            refresh.NoRedirect().redirect_request(None, None, 302, "", {}, "https://arbitrary.invalid")

    def test_private_profile_parser_and_safe_network_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.env"
            path.write_text("export LITELLM_TOKEN='synthetic'\n")
            path.chmod(0o600)
            self.assertEqual(refresh.dotenv(refresh.read_private(path))["LITELLM_TOKEN"], "synthetic")
            path.chmod(0o644)
            with self.assertRaises(BudgetRefused):
                refresh.read_private(path)
        with patch.object(refresh, "read_private", return_value="LITELLM_TOKEN=synthetic\n"), \
             patch.object(refresh.urllib.request, "build_opener", side_effect=RuntimeError("SECRET")):
            with self.assertRaisesRegex(BudgetRefused, "^authenticated_metadata_fetch_failed$"):
                refresh.fetch_authenticated_metadata()


class SupplementalHoldTests(unittest.TestCase):
    def rows(self, ledger):
        with ledger._connect() as connection:
            return connection.execute("SELECT * FROM calls ORDER BY id").fetchall()

    def test_prior_settled_unknown_exact_rows_preserved_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            estimate = old_estimate()
            settled = ledger.reserve(estimate)
            ledger.settle(settled, {"usage": {"prompt_tokens": 100, "completion_tokens": 200}})
            unknown = ledger.reserve(estimate)
            ledger.unknown(unknown)
            original = self.rows(ledger)
            before = ledger.summary()
            backup = ledger.backup()
            result = ledger.supplement_dialogue_pricing(snapshot_fixture(), backup)
            self.assertEqual(self.rows(ledger), original)
            self.assertEqual(result["new_paid_calls"], 0)
            self.assertEqual(result["adjusted_calls"], 2)
            charged = next(row[5] for row in original if row[0] == settled)
            scaled = charged * Fraction(30, 7)
            expected_settled = (scaled.numerator + scaled.denominator - 1) // scaled.denominator
            expected_unknown = nanos(2 * (Decimal("3e-7") * estimate["input_bound"]
                                           + Decimal("1.2e-6") * estimate["output_bound"]))
            self.assertEqual(result["new_total_nano"], expected_settled + expected_unknown)
            self.assertEqual(ledger.summary()["calls"], 2)
            self.assertEqual(ledger.summary()["states"], before["states"])
            self.assertEqual(ledger.summary()["original_call_accounting_usd"], before["original_call_accounting_usd"])
            second = ledger.supplement_dialogue_pricing(snapshot_fixture(), backup)
            self.assertEqual(second["added_hold_nano"], 0)
            self.assertEqual(second["new_total_nano"], result["new_total_nano"])
            self.assertEqual(ledger.summary()["supplemental_adjustments"], 2)
            with self.assertRaises(BudgetRefused):
                ledger.settle(unknown, {"usage": {"prompt_tokens": 0, "completion_tokens": 0}})

    def test_higher_policy_adds_only_delta_and_lower_never_refunds(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            ledger.unknown(ledger.reserve(old_estimate()))
            backup = ledger.backup()
            first = ledger.supplement_dialogue_pricing(snapshot_fixture(), backup)
            higher = snapshot_fixture(output_cost_per_token_above_128k=0.000004)
            second = ledger.supplement_dialogue_pricing(higher, backup)
            self.assertGreater(second["new_total_nano"], first["new_total_nano"])
            again = ledger.supplement_dialogue_pricing(higher, backup)
            self.assertEqual(again["added_hold_nano"], 0)
            lower = ledger.supplement_dialogue_pricing(snapshot_fixture(), backup)
            self.assertEqual(lower["new_total_nano"], second["new_total_nano"])

    def test_holds_count_toward_fixed_cap_under_concurrent_migration_and_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "budget.db"
            ledger = Ledger(path)
            estimate = {**old_estimate(), "reserved_nano": LIMIT_NANO // 8,
                        "input_price": "0.00000015", "output_price": "0.00000060"}
            identifier = ledger.reserve(estimate)
            # A privacy-safe historical settled fixture worth $1.25 at old rates.
            with ledger._connect() as connection:
                connection.execute("UPDATE calls SET charged_nano=?,status='settled' WHERE id=?", (LIMIT_NANO // 8, identifier))
            ledger.supplement_dialogue_pricing(snapshot_fixture(), ledger.backup())
            self.assertEqual(ledger.summary()["spent_or_reserved_usd"], "2.5")
            estimate = {**quote(BODY, PRICES), "reserved_nano": LIMIT_NANO // 4}
            def reserve(_):
                try:
                    Ledger(path).reserve(estimate)
                    return True
                except BudgetRefused:
                    return False
            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(reserve, range(12)))
            self.assertEqual(sum(results), 3)
            self.assertEqual(ledger.summary()["remaining_usd"], "0")
            self.assertEqual(ledger.summary()["calls"], 4)

    def test_negative_holds_immutable_audit_and_reservation_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            ledger.unknown(ledger.reserve(old_estimate()))
            ledger.supplement_dialogue_pricing(snapshot_fixture(), ledger.backup())
            for table in ("adjustments", "adjustment_audit"):
                with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError), ledger._connect() as connection:
                    connection.execute(f"UPDATE {table} SET created=0")
                with self.subTest(table=table), self.assertRaises(sqlite3.IntegrityError), ledger._connect() as connection:
                    connection.execute(f"DELETE FROM {table}")
            with self.assertRaises(sqlite3.IntegrityError), ledger._connect() as connection:
                row = connection.execute("SELECT * FROM adjustments").fetchone()
                connection.execute("INSERT INTO adjustments VALUES(?,?,?,?,?,?,?,?)", (row[0], "new", -1, *row[3:]))
            for value in (-1, 0, True, "1", float("nan")):
                with self.subTest(value=value), self.assertRaises(BudgetRefused):
                    ledger.reserve({**old_estimate(), "reserved_nano": value})

    def test_backup_is_unique_private_readonly_and_required(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            ledger.unknown(ledger.reserve(old_estimate()))
            first, second = ledger.backup(), ledger.backup()
            self.assertNotEqual(first["file"], second["file"])
            path = ledger.path.with_name(first["file"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o400)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), first["sha256"])
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0], 1)
            for bad in ({}, {**first, "sha256": "0" * 64}, {**first, "file": "../outside"}):
                with self.assertRaises(BudgetRefused):
                    ledger.supplement_dialogue_pricing(snapshot_fixture(), bad)

    def test_old_schema_migration_preserves_original_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            with sqlite3.connect(path) as connection:
                connection.executescript("""CREATE TABLE config(id INTEGER PRIMARY KEY,limit_nano INTEGER,violated INTEGER);
                    CREATE TABLE calls(id TEXT PRIMARY KEY,request_sha256 TEXT,model TEXT,quote TEXT,
                    reserved_nano INTEGER,charged_nano INTEGER,status TEXT,created REAL);""")
                connection.execute("INSERT INTO config VALUES(1,?,0)", (LIMIT_NANO,))
                estimate = old_estimate()
                connection.execute("INSERT INTO calls VALUES(?,?,?,?,?,NULL,'delivery_unknown',?)",
                                   ("old", estimate["request_sha256"], DIALOGUE_MODEL, json.dumps(estimate), estimate["reserved_nano"], 1.0))
                old = connection.execute("SELECT * FROM calls").fetchall()
            ledger = Ledger(path)
            self.assertEqual(self.rows(ledger), old)
            ledger.supplement_dialogue_pricing(snapshot_fixture(), ledger.backup())
            self.assertEqual(self.rows(ledger), old)
            self.assertEqual(ledger.summary()["limit_usd"], "10")


if __name__ == "__main__":
    unittest.main()
