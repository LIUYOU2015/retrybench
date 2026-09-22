import json
import tempfile
import unittest
from pathlib import Path

from retrybench.openai_adapter import CostBudget, OpenAIResponsesPolicy
from retrybench.confirmation import load_resume_state
from retrybench.replication import (
    REPLICATION_MAX_COST_USD,
    REPLICATION_MODEL,
    build_replication_manifest,
    run_live_replication,
    run_replication_preflight,
)


def fake_unresolved_response(api_key, payload):
    return {
        "id": "fake-gpt54-response",
        "model": REPLICATION_MODEL,
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


class ReplicationTests(unittest.TestCase):
    def test_zero_cost_frozen_manifest(self):
        rows = build_replication_manifest()
        report = run_replication_preflight(rows)
        self.assertEqual(len(rows), 240)
        self.assertEqual(len({row.response_group_id for row in rows}), 160)
        self.assertEqual({row.model for row in rows}, {REPLICATION_MODEL})
        self.assertTrue(report["all_zero_cost_gates_passed"])
        self.assertLessEqual(
            report["maximum_reserved_cost_usd"], REPLICATION_MAX_COST_USD
        )

    def test_fake_transport_makes_160_calls_for_240_outcomes(self):
        budget = CostBudget(REPLICATION_MAX_COST_USD)
        policy = OpenAIResponsesPolicy(
            model=REPLICATION_MODEL,
            api_key="fake",
            transport=fake_unresolved_response,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = run_live_replication(
                build_replication_manifest(),
                policy,
                budget,
                root / "replication.sqlite3",
                root / "outcomes.jsonl",
            )
        self.assertEqual(len(results), 240)
        self.assertEqual(budget.requests, 160)
        with tempfile.TemporaryDirectory() as directory:
            partial = Path(directory) / "partial.jsonl"
            first_group = results[:3]
            partial.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in first_group),
                encoding="utf-8",
            )
            recovered, groups, spent, requests = load_resume_state(
                partial,
                build_replication_manifest(),
                REPLICATION_MODEL,
                "retrybench-live-gpt54-replication-v1",
            )
        self.assertEqual(len(recovered), 3)
        self.assertEqual(len(groups), 1)
        self.assertEqual(requests, 1)
        self.assertAlmostEqual(spent, first_group[0]["decision"]["cost_usd"])


if __name__ == "__main__":
    unittest.main()
