import json
import tempfile
import unittest
from pathlib import Path

from retrybench.experiment import (
    PILOT_MAX_COST_USD,
    PILOT_MAX_OUTPUT_TOKENS,
    build_pilot_manifest,
    load_manifest,
    run_live_pilot,
    run_zero_cost_preflight,
    summarize_live_pilot,
)
from retrybench.model import EvidenceContract, Schedule, TASKS
from retrybench.openai_adapter import CostBudget, OpenAIResponsesPolicy


REPOSITORY_ROOT = Path(__file__).parents[1]


def fake_unresolved_response(api_key, payload):
    return {
        "id": "fake-%s" % payload["input"].splitlines()[0],
        "model": "gpt-5.4-mini-2026-03-17",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {"action": "unresolved", "rationale": "Fake test decision."}
                        ),
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


class PilotManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build_pilot_manifest()

    def test_manifest_is_exact_frozen_factorial(self):
        self.assertEqual(len(self.rows), 96)
        coordinates = {
            (
                row.task_id,
                row.schedule,
                row.evidence,
                row.prompt_condition,
                row.repetition,
            )
            for row in self.rows
        }
        self.assertEqual(len(coordinates), 96)
        self.assertEqual({row.task_id for row in self.rows}, {task.task_id for task in TASKS})
        self.assertEqual({row.schedule for row in self.rows}, {item.value for item in Schedule})
        self.assertEqual(
            {row.evidence for row in self.rows},
            {item.value for item in EvidenceContract},
        )
        self.assertEqual({row.prompt_condition for row in self.rows}, {"neutral", "cautious"})
        self.assertEqual({row.repetition for row in self.rows}, {1})

    def test_hidden_schedule_never_appears_in_model_input(self):
        for row in self.rows:
            with self.subTest(cell_id=row.cell_id):
                self.assertNotIn(row.schedule, row.instructions)
                self.assertNotIn(row.schedule, row.prompt)

    def test_conservative_reservation_is_within_cap(self):
        reserved = sum(row.maximum_reserved_cost_usd for row in self.rows)
        self.assertLessEqual(reserved, PILOT_MAX_COST_USD)

    def test_checked_in_manifest_matches_generator(self):
        checked_in = load_manifest(
            REPOSITORY_ROOT / "protocol" / "pilot-manifest-v1.jsonl"
        )
        self.assertEqual(checked_in, self.rows)


class ZeroCostPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_zero_cost_preflight(build_pilot_manifest())

    def test_all_preflight_gates_pass(self):
        self.assertTrue(self.report["all_zero_cost_gates_passed"])
        self.assertTrue(all(self.report["gates"].values()))

    def test_preflight_makes_no_api_requests_and_recommends_pilot(self):
        self.assertEqual(self.report["api_requests_made"], 0)
        self.assertEqual(self.report["spend_decision"], "GO")
        self.assertEqual(
            self.report["pilot_conclusion_sensitivity"], "pending_paid_pilot"
        )


class GuardedLivePilotTests(unittest.TestCase):
    def test_runner_rejects_output_token_mismatch_before_spending(self):
        policy = OpenAIResponsesPolicy(
            api_key="fake-key",
            max_output_tokens=PILOT_MAX_OUTPUT_TOKENS + 1,
            transport=fake_unresolved_response,
        )
        budget = CostBudget(PILOT_MAX_COST_USD)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "max output tokens"):
                run_live_pilot(
                    build_pilot_manifest(),
                    policy,
                    budget,
                    root / "pilot.sqlite3",
                    root / "pilot.jsonl",
                )
            self.assertEqual(budget.requests, 0)
            self.assertFalse((root / "pilot.sqlite3").exists())
            self.assertFalse((root / "pilot.jsonl").exists())

    def test_full_frozen_runner_with_fake_transport(self):
        policy = OpenAIResponsesPolicy(
            api_key="fake-key", transport=fake_unresolved_response
        )
        budget = CostBudget(PILOT_MAX_COST_USD)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = run_live_pilot(
                build_pilot_manifest(),
                policy,
                budget,
                root / "pilot.sqlite3",
                root / "pilot.jsonl",
                late_commit_delay=0.02,
            )
            summary = summarize_live_pilot(results, budget)
            self.assertEqual(len((root / "pilot.jsonl").read_text().splitlines()), 96)
        self.assertEqual(summary["episodes"], 96)
        self.assertEqual(summary["api_requests"], 96)
        self.assertEqual(summary["false_retry_permissions"], 0)
        self.assertLess(summary["actual_cost_usd"], PILOT_MAX_COST_USD)


if __name__ == "__main__":
    unittest.main()
