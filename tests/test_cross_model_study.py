from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from retrybench.cross_model_study import Budget, infrastructure_error, prepare, request_order, run, usage_cost
from retrybench.cross_model_pilot import MODEL_CONFIGS
from test_cross_model_pilot import FakeAdapter


class StudyTests(unittest.TestCase):
    def setUp(self):
        FakeAdapter.calls = []
        FakeAdapter.fail = False

    def test_rolling_reservations_reconcile_and_stop_before_cap(self):
        b = Budget({"a": "1"}, {"a": "0.2"})
        self.assertTrue(b.admit("a", Decimal("0.5")))
        self.assertEqual(b.charged["a"], Decimal("0.7"))
        b.settle(Decimal("0.1"))
        self.assertEqual(b.charged["a"], Decimal("0.3"))
        self.assertFalse(b.admit("a", Decimal("0.8")))
        self.assertTrue(b.admit("a", Decimal("0.7")))
        b.settle(None)
        self.assertEqual(b.charged["a"], Decimal("1"))
        self.assertFalse(b.admit("a", Decimal("0.001")))

    def test_unknown_usage_overrun_and_double_admission(self):
        b = Budget({"a": "1"}, {"a": "0"})
        b.admit("a", Decimal("0.3"))
        with self.assertRaises(ValueError):
            b.admit("a", Decimal("0.3"))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            b.settle(Decimal("0.4"))
        self.assertEqual(b.charged["a"], Decimal("0.4"))

    def test_invalid_model_decision_does_not_stop_collection(self):
        class Invalid(FakeAdapter):
            def __call__(self, case):
                r = super().__call__(case)
                r["action"] = "not-a-valid-action"
                return r
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "study"
            prepare(path, [])
            result = run(path, Invalid)
            self.assertEqual(result["status"], "collected")
            self.assertEqual(len(FakeAdapter.calls), 480)
            for p in MODEL_CONFIGS:
                self.assertEqual(result["providers"][p]["status_counts"], {"invalid": 240})
                report = json.loads((path / "run" / p / "report.json").read_text())
                self.assertEqual(report["metrics"]["false_retry_permission"]["unknown"], 240)
            with self.assertRaises(FileExistsError):
                run(path, Invalid)

    def test_transport_failure_retains_reserve_and_stops_all(self):
        FakeAdapter.fail = True
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "study"
            prepare(path, [])
            result = run(path, FakeAdapter)
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(len(FakeAdapter.calls), 1)
            self.assertGreater(Decimal(result["providers"]["openai"]["unknown_cost_reserved_usd"]), 0)
            self.assertEqual(result["providers"]["anthropic"]["attempted"], 0)

    def test_all_cases_fresh_order_and_prior_tampering_rejected(self):
        self.assertEqual(len(set(request_order())), 240)
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "prior/run"
            old.mkdir(parents=True)
            summary = {"providers": {p: {"reserved_usd": "0.5"} for p in MODEL_CONFIGS}}
            (old / "summary.json").write_text(json.dumps(summary))
            path = Path(d) / "study"
            plan = prepare(path, [old.parent])
            self.assertEqual(plan["prior_retained_reservations_usd"], {p: "0.5" for p in MODEL_CONFIGS})
            plan["prior_retained_reservations_usd"]["anthropic"] = "0"
            (path / "plan.json").write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "reservations mismatch"):
                run(path, FakeAdapter)
            self.assertEqual(FakeAdapter.calls, [])

    def test_no_usage_is_not_free_and_truncated_output_can_be_recorded(self):
        cfg = MODEL_CONFIGS["openai"]
        self.assertIsNone(usage_cost({}, cfg))
        r = {"status": "invalid_output", "returned_model": cfg["returned_model"],
             "raw_provider_response_available": True, "raw_calls": [{}],
             "usage": {"input_tokens": 100, "output_tokens": 512}}
        self.assertIsNone(infrastructure_error(r, 1000, cfg))
        r["usage"]["output_tokens"] = 513
        self.assertEqual(infrastructure_error(r, 1000, cfg), "token envelope exceeded")


if __name__ == "__main__":
    unittest.main()
