import json
import tempfile
import unittest
from pathlib import Path

from retrybench.confirmation import build_confirmation_manifest
from retrybench.external import (
    export_public_cases,
    load_external_decisions,
    score_external_decisions,
    summarize_external,
)
from retrybench.model import Action


class ExternalEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.rows = build_confirmation_manifest()
        self.cases = export_public_cases(self.rows)

    def test_export_has_160_unique_cases_and_no_hidden_schedule(self):
        self.assertEqual(len(self.cases), 160)
        self.assertEqual(len({case["case_id"] for case in self.cases}), 160)
        self.assertTrue(all("schedule" not in case for case in self.cases))

    def test_shared_decisions_score_240_hidden_outcomes(self):
        decisions = {case["case_id"]: Action.UNRESOLVED for case in self.cases}
        results = score_external_decisions(self.rows, decisions)
        summary = summarize_external(results)
        self.assertEqual(len(results), 240)
        self.assertEqual(summary["scored_outcomes"], 240)
        self.assertEqual(summary["unresolved"], 240)
        self.assertEqual(summary["false_retry_permission"], 0)

    def test_loader_rejects_duplicate_case_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decisions.jsonl"
            row = {"case_id": self.cases[0]["case_id"], "action": "stop"}
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
            with self.assertRaisesRegex(ValueError, "duplicate case_id"):
                load_external_decisions(path)


if __name__ == "__main__":
    unittest.main()
