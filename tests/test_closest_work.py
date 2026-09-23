import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from retrybench.closest_work import (
    run_extension_block,
    run_extension_episode,
    write_closest_work_outputs,
)


TEMPLATES = [
    SimpleNamespace(template_id="create", family="create_once"),
    SimpleNamespace(template_id="transition", family="ordered_transition"),
    SimpleNamespace(template_id="reserve", family="reserve_then_link"),
]


class ClosestWorkExtensionTests(unittest.TestCase):
    def test_weak_negative_fails_only_in_added_schedules(self):
        rows = run_extension_block(TEMPLATES)
        failures = [
            row
            for row in rows
            if row.policy == "negative_status_as_retry_permission"
            and not row.exactly_once_success
        ]
        self.assertEqual(len(failures), 6)
        self.assertEqual(
            {row.schedule for row in failures},
            {"in_flight_late_commit", "stale_negative_after_commit"},
        )
        self.assertTrue(all(row.effect_count == 2 for row in failures))

    def test_terminal_status_and_stable_idempotency_are_safe(self):
        rows = run_extension_block(TEMPLATES)
        safe = {
            "terminal_aware_status_reconcile",
            "stable_idempotency_retry",
        }
        selected = [row for row in rows if row.policy in safe]
        self.assertEqual(len(selected), 24)
        self.assertTrue(all(row.exactly_once_success for row in selected))

    def test_family_specific_duplicate_labels_are_preserved(self):
        expected = {
            "create_once": "duplicate_entity",
            "ordered_transition": "target_overshoot",
            "reserve_then_link": "overconsumption_and_orphan",
        }
        for template in TEMPLATES:
            row = run_extension_episode(
                template,
                "stale_negative_after_commit",
                "negative_status_as_retry_permission",
            )
            self.assertEqual(row.state_outcome, expected[template.family])

    def test_outputs_are_hash_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_closest_work_outputs(
                {"schema_version": "test"},
                [{"exactly_once_success": True}],
                output,
            )
            report = json.loads((output / "analysis.json").read_text())
            self.assertEqual(len(report["outcomes_sha256"]), 64)
            self.assertTrue((output / "outcomes.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
