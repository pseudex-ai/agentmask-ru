"""No sockets/provider calls: reservation, refusal and concurrency proofs."""

from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import tempfile
import unittest

from budget import BudgetRefused, Ledger, LIMIT_NANO, quote


PRICES = {"models": [{"model_name": "test-model", "mode": "chat",
    "input_cost_per_token": 0.00000014, "output_cost_per_token": 0.00000028}]}
BODY = {"model": "test-model", "messages": [{"role": "user", "content": "Synthetic fixture"}], "max_tokens": 512}


class BudgetTests(unittest.TestCase):
    def test_positive_quote_and_explicit_bounds(self):
        result = quote(BODY, PRICES)
        self.assertGreater(result["reserved_nano"], 0)
        self.assertGreater(result["input_bound"], len(BODY["messages"][0]["content"]))
        self.assertEqual(result["output_bound"], 512)

    def test_unpriced_models_and_free_price_are_not_guessed(self):
        for prices in ({"models": []}, {"models": [{**PRICES["models"][0], "input_cost_per_token": None}]},
                       {"models": [{**PRICES["models"][0], "output_cost_per_token": 0}]}):
            with self.assertRaises(BudgetRefused):
                quote(BODY, prices)

    def test_missing_or_invalid_bound_is_refused(self):
        for value in (None, True, -1, 0, 32769, "512"):
            request = {**BODY, "max_tokens": value}
            with self.assertRaises(BudgetRefused):
                quote(request, PRICES)

    def test_multimodal_stream_route_override_refused(self):
        for delta in ({"stream": True}, {"api_base": "https://arbitrary.invalid"}, {"n": True},
                      {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]}):
            with self.assertRaises(BudgetRefused):
                quote({**BODY, **delta}, PRICES)

    def test_no_truncation_to_fit_large_context(self):
        request = copy.deepcopy(BODY)
        request["messages"][0]["content"] = "x" * 130000
        with self.assertRaises(BudgetRefused):
            quote(request, PRICES)
        self.assertEqual(len(request["messages"][0]["content"]), 130000)

    def test_duplicate_routes_use_highest_price(self):
        higher = {**PRICES["models"][0], "input_cost_per_token": 0.0001}
        result = quote(BODY, {"models": [PRICES["models"][0], higher]})
        self.assertEqual(result["input_price"], "0.0001")

    def test_timeout_never_refunds_unknown_request(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            estimate = {**quote(BODY, PRICES), "reserved_nano": LIMIT_NANO}
            identifier = ledger.reserve(estimate)
            ledger.unknown(identifier)
            self.assertEqual(ledger.summary()["remaining_usd"], "0")
            with self.assertRaises(BudgetRefused):
                ledger.reserve(quote(BODY, PRICES))

    def test_usage_settles_known_cost_and_rejects_duplicate_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            estimate = quote(BODY, PRICES)
            identifier = ledger.reserve(estimate)
            ledger.settle(identifier, {"usage": {"prompt_tokens": 10, "completion_tokens": 20}})
            self.assertEqual(ledger.summary()["states"], {"settled": 1})
            self.assertLess(float(ledger.summary()["spent_or_reserved_usd"]), estimate["reserved_nano"] / 1e9)
            with self.assertRaises(BudgetRefused):
                ledger.settle(identifier, {})

    def test_missing_usage_retains_full_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            identifier = ledger.reserve({**quote(BODY, PRICES), "reserved_nano": LIMIT_NANO})
            ledger.settle(identifier, {"error": "synthetic"})
            self.assertEqual(ledger.summary()["states"], {"usage_unknown": 1})
            self.assertEqual(ledger.summary()["remaining_usd"], "0")

    def test_bound_violation_quarantines_all_future_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            identifier = ledger.reserve(quote(BODY, PRICES))
            with self.assertRaises(BudgetRefused):
                ledger.settle(identifier, {"usage": {"prompt_tokens": 10, "completion_tokens": 513}})
            self.assertTrue(ledger.summary()["bound_violated"])
            with self.assertRaises(BudgetRefused):
                ledger.reserve(quote(BODY, PRICES))

    def test_concurrent_reservations_cannot_overbook(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "budget.db")
            estimate = {**quote(BODY, PRICES), "reserved_nano": LIMIT_NANO // 4}
            def reserve(_):
                try:
                    ledger.reserve(estimate)
                    return True
                except BudgetRefused:
                    return False
            with ThreadPoolExecutor(max_workers=12) as executor:
                results = list(executor.map(reserve, range(12)))
            self.assertEqual(sum(results), 4)
            self.assertEqual(ledger.summary()["remaining_usd"], "0")
            self.assertEqual(Ledger(Path(directory) / "budget.db").summary()["calls"], 4)


if __name__ == "__main__":
    unittest.main()
