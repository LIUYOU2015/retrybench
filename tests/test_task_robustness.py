import json
import tempfile
import unittest
from pathlib import Path

from retrybench.openai_adapter import CostBudget, OpenAIResponsesPolicy
from retrybench.task_robustness import (
    ROBUSTNESS_MAX_COST_USD,
    ROBUSTNESS_MAX_OUTPUT_TOKENS,
    ROBUSTNESS_MODEL,
    analyze_task_robustness,
    build_robustness_manifest,
    run_live_task_robustness,
    run_robustness_preflight,
)


def fake_unresolved_response(api_key, payload):
    return {
        "id": "fake-robustness-response",
        "model": ROBUSTNESS_MODEL,
        "output": [{"type": "message", "content": [{
            "type": "output_text",
            "text": json.dumps({"action": "unresolved", "rationale": "test"}),
        }]}],
        "usage": {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


class TaskRobustnessTests(unittest.TestCase):
    def test_zero_cost_protocol_freeze(self):
        rows = build_robustness_manifest()
        report = run_robustness_preflight(rows)
        self.assertEqual(len(rows), 192)
        self.assertEqual(len({row.response_group_id for row in rows}), 128)
        self.assertTrue(report["all_zero_cost_gates_passed"])

    def test_predeclared_analysis_strong_fixture(self):
        rows = []
        for cell in build_robustness_manifest():
            false_retry = cell.evidence == "weak"
            rows.append({
                **cell.to_dict(),
                "false_retry_permission": false_retry,
            })
        report = analyze_task_robustness(rows)
        self.assertEqual(report["decision"], "STRONGER_EMPIRICAL_PAPER_PATH")
        self.assertEqual(report["weak_higher_families"], 8)
        self.assertEqual(report["equal_family_mean_rate_difference"], 1.0)
        self.assertEqual(report["task_cluster_t_95_interval_bounded"], [1.0, 1.0])
        self.assertEqual(
            report["lexical_counterbalance"][
                "equal_family_mean_create_minus_noncreate"
            ],
            0.0,
        )
        for frame in ("create", "noncreate"):
            contrast = report["post_hoc_within_frame_evidence_contrasts"][
                "frames"
            ][frame]
            self.assertEqual(contrast["weak_higher_families"], 8)
            self.assertEqual(contrast["equal_family_mean_rate_difference"], 1.0)
            self.assertEqual(
                contrast["task_cluster_t_95_interval_bounded"], [1.0, 1.0]
            )

    def test_checked_in_post_hoc_contrasts_recompute_from_sanitized_outcomes(self):
        root = Path(__file__).resolve().parents[1]
        outcome_path = root / "runs/task-robustness-v1/sanitized-outcomes.jsonl"
        rows = [
            json.loads(line)
            for line in outcome_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        recomputed = analyze_task_robustness(rows)
        checked_in = json.loads(
            (root / "runs/task-robustness-v1/analysis.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            recomputed["post_hoc_within_frame_evidence_contrasts"],
            checked_in["post_hoc_within_frame_evidence_contrasts"],
        )

    def test_guarded_runner_makes_128_calls_for_192_outcomes(self):
        policy = OpenAIResponsesPolicy(
            model=ROBUSTNESS_MODEL,
            max_output_tokens=ROBUSTNESS_MAX_OUTPUT_TOKENS,
            api_key="fake",
            transport=fake_unresolved_response,
        )
        budget = CostBudget(ROBUSTNESS_MAX_COST_USD)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = run_live_task_robustness(
                build_robustness_manifest(),
                policy,
                budget,
                root / "robustness.sqlite3",
                root / "outcomes.jsonl",
                late_commit_delay=0.01,
            )
        self.assertEqual(len(results), 192)
        self.assertEqual(budget.requests, 128)


if __name__ == "__main__":
    unittest.main()
