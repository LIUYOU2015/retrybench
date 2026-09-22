import importlib.util
import unittest

from retrybench.langgraph_adapter import (
    run_langgraph_audit,
    summarize_langgraph_audit,
)


@unittest.skipUnless(importlib.util.find_spec("langgraph"), "langgraph extra not installed")
class LangGraphAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = summarize_langgraph_audit(run_langgraph_audit())

    def test_actual_framework_version_and_complete_matrix(self):
        self.assertEqual(self.report["framework"], "langgraph")
        self.assertEqual(self.report["framework_version"], "0.6.11")
        self.assertEqual(self.report["episodes"], 48)

    def test_exception_retry_duplicates_ambiguous_side_effects(self):
        row = self.report["by_policy"]["langgraph_default_retry_policy"]
        self.assertEqual(row["episodes"], 16)
        self.assertEqual(row["retries"], 16)
        self.assertEqual(row["false_retry_permissions"], 16)
        self.assertEqual(row["duplicates"], 12)
        self.assertEqual(row["exact_state_success"], 0)

    def test_stable_replay_closes_the_gap(self):
        row = self.report["by_policy"]["stable_idempotency_retry"]
        self.assertEqual(row["episodes"], 16)
        self.assertEqual(row["graph_completed"], 16)
        self.assertEqual(row["duplicates"], 0)
        self.assertEqual(row["exact_state_success"], 16)


if __name__ == "__main__":
    unittest.main()
