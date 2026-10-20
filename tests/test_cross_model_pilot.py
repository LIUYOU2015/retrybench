import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from retrybench.cross_model_pilot import (
    MODEL_CONFIGS, audit_record, balanced_case_ids, prepare, reserve, run,
)
from retrybench.evaluation import load_suite, public_cases


class FakeAdapter:
    calls = []
    fail = False

    def __init__(self, model, **kwargs):
        self.model = model
        self.settings = {"synthetic": True, "config": kwargs}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __call__(self, case):
        self.calls.append((self.model, case["case_id"]))
        if self.fail:
            return {"status": "adapter_error", "error": "synthetic transport failure"}
        return {"status": "complete", "action": "unresolved", "arguments": {"idempotency_key": None},
                "returned_model": self.model.split("/", 1)[1], "raw_provider_response_available": True,
                "raw_calls": [{"response": {"fixture": True}}], "usage": {"input_tokens": 100, "output_tokens": 20}}


class CrossModelPilotTests(unittest.TestCase):
    def setUp(self):
        FakeAdapter.calls = []
        FakeAdapter.fail = False

    def test_balanced_fixed_selection(self):
        ids = balanced_case_ids()
        cases = [c for c in load_suite()["cases"] if c["case_id"] in ids]
        self.assertEqual(len(ids), 24)
        self.assertEqual(len(set(ids)), 24)
        self.assertEqual(set(Counter(c["condition"] for c in cases).values()), {2})
        self.assertEqual(set(Counter(c["task_id"] for c in cases).values()), {6})
        self.assertEqual(Counter(c["block"] for c in cases), {"evidence": 16, "supplied_key": 8})

    def test_budget_check_before_any_output_or_adapter_call(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pilot"
            for caps in ({"openai": "0.001", "anthropic": "2"},
                         {"openai": "NaN", "anthropic": "2"},
                         {"openai": "5", "anthropic": "-1"}):
                with self.assertRaises(ValueError):
                    prepare(path, caps)
                self.assertFalse(path.exists())
            self.assertEqual(FakeAdapter.calls, [])

    def test_full_mock_pilot_and_no_replay(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pilot"
            plan = prepare(path, {"openai": "5", "anthropic": "2"})
            summary = run(path, FakeAdapter)
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(len(FakeAdapter.calls), 48)
            for provider in MODEL_CONFIGS:
                s = summary["providers"][provider]
                self.assertEqual(s["status_counts"], {"valid": 24})
                self.assertEqual(s["reserved_usd"], plan["total_reserved_usd"][provider])
                self.assertLess(Decimal(s["uncached_usage_cost_upper_estimate_usd"]), Decimal(s["reserved_usd"]))
                report = json.loads((path / "run" / provider / "report.json").read_text())
                self.assertEqual(report["metrics"]["status_counts"], {"valid": 24, "missing": 216})
            with self.assertRaises(FileExistsError):
                run(path, FakeAdapter)
            self.assertEqual(len(FakeAdapter.calls), 48)

    def test_failure_stops_all_and_keeps_full_reservation(self):
        FakeAdapter.fail = True
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pilot"
            plan = prepare(path, {"openai": "5", "anthropic": "2"})
            summary = run(path, FakeAdapter)
            self.assertEqual(len(FakeAdapter.calls), 1)
            self.assertEqual(summary["status"], "stopped")
            self.assertEqual(summary["providers"]["openai"]["reserved_usd"], plan["request_plan"][0]["reserved_usd"])
            self.assertEqual(summary["providers"]["anthropic"]["attempted"], 0)

    def test_audit_rejects_missing_capture_identity_usage_and_token_overrun(self):
        case = public_cases()[0]
        config = MODEL_CONFIGS["openai"]
        record = dict(FakeAdapter(config["model"])(case), case_id=case["case_id"])
        req = {"input_token_reservation": reserve(case, config)[0]}
        self.assertIsNone(audit_record(record, req, config))
        for changed in ({"raw_provider_response_available": False}, {"returned_model": "other"},
                        {"usage": {}}, {"usage": {"input_tokens": 1, "output_tokens": 513}},
                        {"usage": {"input_tokens": 1, "output_tokens": 1, "input_tokens_cache_write": 1}}):
            self.assertIsNotNone(audit_record({**record, **changed}, req, config))

    def test_valid_unsafe_action_does_not_stop_diagnostic(self):
        case = public_cases()[0]
        config = MODEL_CONFIGS["openai"]
        record = dict(FakeAdapter(config["model"])(case), case_id=case["case_id"], action="retry")
        req = {"input_token_reservation": reserve(case, config)[0]}
        self.assertIsNone(audit_record(record, req, config))


if __name__ == "__main__":
    unittest.main()
