import json
import unittest
from pathlib import Path

from retrybench.model import EvidenceContract, Schedule, TASKS


PROTOCOL_PATH = Path(__file__).parents[1] / "protocol" / "retrybench-v1.json"


class FrozenProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_protocol_matches_implemented_factors(self):
        self.assertEqual(
            self.protocol["task_ids"],
            [task.task_id for task in TASKS],
        )
        self.assertEqual(
            [item["id"] for item in self.protocol["hidden_schedules"]],
            [schedule.value for schedule in Schedule],
        )
        self.assertEqual(
            [item["id"] for item in self.protocol["evidence_contracts"]],
            [contract.value for contract in EvidenceContract],
        )

    def test_factor_ids_are_unique(self):
        for field in ("task_ids", "prompt_conditions", "controllers"):
            values = self.protocol[field]
            self.assertEqual(len(values), len(set(values)), field)
        for field in ("hidden_schedules", "evidence_contracts"):
            values = [item["id"] for item in self.protocol[field]]
            self.assertEqual(len(values), len(set(values)), field)

    def test_pilot_episode_count_is_frozen_product(self):
        pilot = self.protocol["pilot"]
        expected = (
            pilot["task_instances"]
            * pilot["schedule_count"]
            * pilot["evidence_contract_count"]
            * pilot["prompt_condition_count"]
            * pilot["repetitions"]
        )
        self.assertEqual(pilot["llm_episodes"], expected)
        self.assertEqual(expected, 96)

    def test_confirmatory_episode_count_is_frozen_product(self):
        run = self.protocol["confirmatory_run_if_all_gates_pass"]
        expected = (
            run["models"]
            * run["task_instances"]
            * run["schedule_count"]
            * run["evidence_contract_count"]
            * run["prompt_condition_count"]
            * run["repetitions"]
        )
        self.assertEqual(run["llm_episodes"], expected)
        self.assertEqual(expected, 4800)

    def test_protocol_preserves_claim_boundary(self):
        non_claims = " ".join(self.protocol["non_claims"]).lower()
        for prior_concept in (
            "ambiguous tool outcomes",
            "verification before retry",
            "tri-state reconciliation",
            "stable-key idempotency",
            "provider miss-semantics",
        ):
            self.assertIn(prior_concept, non_claims)


if __name__ == "__main__":
    unittest.main()
