import importlib.util
import unittest

from retrybench.langchain_adapter import (
    run_langchain_audit,
    summarize_langchain_audit,
)


@unittest.skipUnless(
    importlib.util.find_spec("langchain_core"), "langchain extra not installed"
)
class LangChainAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = summarize_langchain_audit(run_langchain_audit())

    def test_actual_framework_version_and_complete_matrix(self):
        self.assertEqual(self.report["framework"], "langchain-core")
        self.assertEqual(self.report["framework_version"], "0.3.86")
        self.assertEqual(self.report["episodes"], 48)

    def test_exception_retry_can_report_success_after_duplicate_effect(self):
        row = self.report["by_policy"]["langchain_exception_retry"]
        self.assertEqual(row["episodes"], 16)
        self.assertEqual(row["runnable_completed"], 16)
        self.assertEqual(row["retries"], 16)
        self.assertEqual(row["false_retry_permissions"], 16)
        self.assertEqual(row["duplicates"], 12)
        self.assertEqual(row["exact_state_success"], 4)

    def test_stable_replay_closes_the_gap(self):
        row = self.report["by_policy"]["stable_idempotency_retry"]
        self.assertEqual(row["episodes"], 16)
        self.assertEqual(row["runnable_completed"], 16)
        self.assertEqual(row["duplicates"], 0)
        self.assertEqual(row["exact_state_success"], 16)


if __name__ == "__main__":
    unittest.main()
