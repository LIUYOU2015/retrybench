import json
import unittest

from retrybench.confirmation import build_confirmation_manifest
from retrybench.confirmation_analysis import analyze_confirmation
from retrybench.external import score_external_decisions
from retrybench.model import Action


class ConfirmationAnalysisTests(unittest.TestCase):
    def test_complete_shared_response_analysis(self):
        manifest = build_confirmation_manifest()
        cases = {row.response_group_id for row in manifest}
        decisions = {
            case_id: (Action.RETRY if ":weak:" in case_id else Action.STOP)
            for case_id in cases
        }
        scored = score_external_decisions(manifest, decisions)
        response_number = {case_id: number for number, case_id in enumerate(sorted(cases))}
        rows = []
        for row in scored:
            case_id = str(row["case_id"])
            action = decisions[row["case_id"]]
            rows.append({
                **row,
                "response_group_id": case_id,
                "transcript_sha256": next(
                    cell.transcript_sha256
                    for cell in manifest
                    if cell.cell_id == row["cell_id"]
                ),
                "model": "gpt-5.4-mini-2026-03-17",
                "decision": {
                    "action": action.value,
                    "rationale": "fixture",
                    "response_id": "fake-%03d" % response_number[case_id],
                    "model": "gpt-5.4-mini-2026-03-17",
                    "cost_usd": 0.001,
                    "usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 0,
                        "output_tokens": 5,
                        "reasoning_tokens": 0,
                    },
                },
            })
        report = analyze_confirmation(
            rows, {"all_zero_cost_gates_passed": True}
        )
        self.assertEqual(report["scored_outcomes"], 240)
        self.assertEqual(report["fresh_model_calls"], 160)
        self.assertAlmostEqual(report["actual_cost_usd"], 0.16)
        primary = next(
            item
            for item in report["paired_neutral_weak_vs_authoritative"]
            if item["metric"] == "false_retry_permission"
        )
        self.assertEqual(primary["pairs"], 60)
        self.assertEqual(primary["left_only"], 60)
        self.assertEqual(primary["right_only"], 0)
        self.assertTrue(all(report["integrity"].values()))


if __name__ == "__main__":
    unittest.main()
