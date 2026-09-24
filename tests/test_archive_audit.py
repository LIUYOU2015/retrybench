import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from retrybench.archive_audit import audit_archive_dataset


def make_archive(root: Path, observed: str = "not_found", effect_count: int = 2):
    database = root / "archive.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE operations (
                operation_id TEXT PRIMARY KEY, schedule TEXT, state TEXT, due_at REAL
            );
            CREATE TABLE effects (
                effect_id INTEGER PRIMARY KEY, operation_id TEXT, committed_at REAL
            );
            """
        )
        connection.execute(
            "INSERT INTO operations VALUES (?, ?, ?, ?)",
            ("op-1", "in_flight_late_commit", "committed", None),
        )
        for index in range(effect_count):
            connection.execute(
                "INSERT INTO effects VALUES (?, ?, ?)",
                (index + 1, "op-1", 100.0 + index),
            )
    output = root / "archive.jsonl"
    output.write_text(
        json.dumps(
            {
                "operation_id": "op-1",
                "schedule": "in_flight_late_commit",
                "evidence": "weak",
                "observed_state": observed,
                "decision": {"action": "retry"},
                "effect_count": effect_count,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return output, database


class ArchiveAuditTests(unittest.TestCase):
    def test_valid_archive_passes_without_claiming_timestamp_margin(self):
        with tempfile.TemporaryDirectory() as directory:
            output, database = make_archive(Path(directory))
            report = audit_archive_dataset("fixture", output, [database])
        self.assertTrue(report["archive_integrity_passed"])
        self.assertFalse(report["timestamp_margin_recoverable"])
        self.assertEqual(report["sensitive_early_settlement_contradictions"], 0)

    def test_committed_weak_observation_exposes_race_contradiction(self):
        with tempfile.TemporaryDirectory() as directory:
            output, database = make_archive(Path(directory), observed="committed")
            report = audit_archive_dataset("fixture", output, [database])
        self.assertFalse(report["archive_integrity_passed"])
        self.assertEqual(report["sensitive_early_settlement_contradictions"], 1)

    def test_ledger_effect_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output, database = make_archive(Path(directory), effect_count=1)
            row = json.loads(output.read_text())
            row["effect_count"] = 2
            output.write_text(json.dumps(row) + "\n", encoding="utf-8")
            report = audit_archive_dataset("fixture", output, [database])
        self.assertFalse(report["archive_integrity_passed"])
        self.assertEqual(report["effect_count_mismatches"], 1)


if __name__ == "__main__":
    unittest.main()
