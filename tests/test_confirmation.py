import json
import tempfile
import unittest
from pathlib import Path

from retrybench.confirmation import (
    CONFIRMATION_MAX_COST_USD,
    CONFIRMATION_MAX_OUTPUT_TOKENS,
    build_confirmation_manifest,
    load_confirmation_manifest,
    run_confirmation_preflight,
    run_live_confirmation,
)
from retrybench.openai_adapter import CostBudget, OpenAIResponsesPolicy


ROOT = Path(__file__).parents[1]


def fake_unresolved_response(api_key, payload):
    return {
        "id": "fake-response",
        "model": "gpt-5.4-mini-2026-03-17",
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


class ConfirmationManifestTests(unittest.TestCase):
    def test_frozen_manifest_and_response_sharing(self):
        rows = build_confirmation_manifest()
        self.assertEqual(len(rows), 240)
        groups = {row.response_group_id for row in rows}
        self.assertEqual(len(groups), 160)
        weak = [row for row in rows if row.evidence == "weak"]
        counts = {group: sum(row.response_group_id == group for row in weak) for group in groups}
        self.assertEqual(sorted(value for value in counts.values() if value), [3] * 40)
        self.assertEqual(
            load_confirmation_manifest(ROOT / "protocol" / "confirmation-v2-manifest.jsonl"),
            rows,
        )

    def test_zero_cost_preflight(self):
        report = run_confirmation_preflight(build_confirmation_manifest())
        self.assertTrue(report["all_zero_cost_gates_passed"])
        self.assertEqual(report["api_requests_made"], 0)
        self.assertEqual(report["fresh_model_calls"], 160)


class ConfirmationRunnerTests(unittest.TestCase):
    def test_runner_rejects_output_token_mismatch_before_spending(self):
        budget = CostBudget(CONFIRMATION_MAX_COST_USD)
        policy = OpenAIResponsesPolicy(
            api_key="fake",
            max_output_tokens=CONFIRMATION_MAX_OUTPUT_TOKENS + 1,
            transport=fake_unresolved_response,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "confirmation.sqlite3"
            output = root / "outcomes.jsonl"
            with self.assertRaisesRegex(ValueError, "max output tokens"):
                run_live_confirmation(
                    build_confirmation_manifest(),
                    policy,
                    budget,
                    database,
                    output,
                )
            self.assertEqual(budget.requests, 0)
            self.assertFalse(database.exists())
            self.assertFalse(output.exists())

    def test_fake_transport_makes_160_calls_for_240_outcomes(self):
        budget = CostBudget(CONFIRMATION_MAX_COST_USD)
        policy = OpenAIResponsesPolicy(
            api_key="fake", transport=fake_unresolved_response
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = run_live_confirmation(
                build_confirmation_manifest(),
                policy,
                budget,
                root / "confirmation.sqlite3",
                root / "outcomes.jsonl",
                late_commit_delay=0.1,
            )
        self.assertEqual(len(results), 240)
        self.assertEqual(budget.requests, 160)
        weak_groups = {}
        for row in results:
            if row["evidence"] == "weak":
                weak_groups.setdefault(row["response_group_id"], []).append(row)
        self.assertTrue(all(len(group) == 3 for group in weak_groups.values()))
        self.assertTrue(all(
            len({item["decision"]["action"] for item in group}) == 1
            for group in weak_groups.values()
        ))


if __name__ == "__main__":
    unittest.main()
