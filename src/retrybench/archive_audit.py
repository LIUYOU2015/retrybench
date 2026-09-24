"""Retrospective integrity audit for paid runs created with wall-clock settlement."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence


class ArchiveAuditError(RuntimeError):
    """Raised when archived live evidence is missing or internally inconsistent."""


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ArchiveAuditError("archived JSONL is empty: %s" % path)
    return rows


def _read_ledger(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise ArchiveAuditError("archived ledger is missing: %s" % path)
    uri = "file:%s?mode=ro" % path.resolve()
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(operations)")
        }
        required = {"operation_id", "schedule", "state", "due_at"}
        if not required.issubset(columns):
            raise ArchiveAuditError("ledger has an unexpected operations schema")
        rows = connection.execute(
            """
            SELECT o.operation_id, o.schedule, o.state, o.due_at,
                   COUNT(e.effect_id) AS effect_count,
                   MIN(e.committed_at) AS first_committed_at,
                   MAX(e.committed_at) AS last_committed_at
            FROM operations o
            LEFT JOIN effects e ON e.operation_id = o.operation_id
            GROUP BY o.operation_id, o.schedule, o.state, o.due_at
            """
        ).fetchall()
    return {str(row["operation_id"]): dict(row) for row in rows}


def _merge_ledgers(paths: Sequence[Path]) -> tuple[dict[str, dict[str, Any]], int]:
    merged: dict[str, dict[str, Any]] = {}
    duplicate_operations = 0
    for path in paths:
        for operation_id, row in _read_ledger(path).items():
            if operation_id in merged:
                duplicate_operations += 1
                comparable = ("schedule", "state", "due_at", "effect_count")
                if any(merged[operation_id][key] != row[key] for key in comparable):
                    raise ArchiveAuditError(
                        "duplicate operation differs across ledgers: %s" % operation_id
                    )
                continue
            merged[operation_id] = row
    return merged, duplicate_operations


def audit_archive_dataset(
    name: str,
    jsonl_path: Path,
    database_paths: Sequence[Path],
) -> dict[str, Any]:
    """Cross-check archived output rows against their durable operation ledgers."""
    rows = _load_jsonl(jsonl_path)
    ledgers, duplicate_operations = _merge_ledgers(database_paths)
    operation_ids = [str(row["operation_id"]) for row in rows]
    if len(operation_ids) != len(set(operation_ids)):
        raise ArchiveAuditError("archived JSONL contains duplicate operation ids")

    missing_ledger = sorted(set(operation_ids) - set(ledgers))
    extra_ledger = sorted(set(ledgers) - set(operation_ids))
    schedule_mismatches = 0
    effect_count_mismatches = 0
    inflight_rows = []
    for row in rows:
        ledger = ledgers.get(str(row["operation_id"]))
        if ledger is None:
            continue
        schedule_mismatches += ledger["schedule"] != row["schedule"]
        effect_count_mismatches += int(ledger["effect_count"]) != int(
            row["effect_count"]
        )
        if row["schedule"] == "in_flight_late_commit":
            inflight_rows.append((row, ledger))

    expected_observation = {
        "none": "unknown",
        "weak": "not_found",
        "authoritative": "in_flight",
    }
    sensitive = [
        (row, ledger)
        for row, ledger in inflight_rows
        if row["evidence"] in {"weak", "authoritative"}
    ]
    none_rows = [
        (row, ledger)
        for row, ledger in inflight_rows
        if row["evidence"] == "none"
    ]
    observation_mismatches = sum(
        row["observed_state"] != expected_observation[str(row["evidence"])]
        for row, _ in inflight_rows
    )
    sensitive_early_settlement_contradictions = sum(
        row["observed_state"] != expected_observation[str(row["evidence"])]
        for row, _ in sensitive
    )
    unsettled_ledgers = sum(
        ledger["state"] != "committed" or ledger["due_at"] is not None
        for _, ledger in inflight_rows
    )
    missing_commit_timestamps = sum(
        ledger["first_committed_at"] is None for _, ledger in inflight_rows
    )
    outcome_ordering_mismatches = 0
    for row, _ in inflight_rows:
        action = str(row["decision"]["action"])
        expected_effects = 2 if action == "retry" else 1
        outcome_ordering_mismatches += int(row["effect_count"]) != expected_effects

    checks = {
        "json_operations_have_ledger_rows": not missing_ledger,
        "ledger_has_no_unmatched_operations": not extra_ledger,
        "schedules_match_ledger": schedule_mismatches == 0,
        "effect_counts_match_ledger": effect_count_mismatches == 0,
        "all_inflight_operations_eventually_committed": unsettled_ledgers == 0,
        "all_inflight_effects_have_commit_timestamps": missing_commit_timestamps == 0,
        "frozen_inflight_observations_match": observation_mismatches == 0,
        "evidence_sensitive_rows_exclude_early_settlement": (
            bool(sensitive) and sensitive_early_settlement_contradictions == 0
        ),
        "final_outcomes_are_settlement_order_invariant": (
            outcome_ordering_mismatches == 0
        ),
    }
    return {
        "name": name,
        "jsonl": str(jsonl_path),
        "databases": [str(path) for path in database_paths],
        "rows": len(rows),
        "ledger_operations": len(ledgers),
        "duplicate_operations_across_resume_ledgers": duplicate_operations,
        "in_flight_rows": len(inflight_rows),
        "evidence_sensitive_in_flight_rows": len(sensitive),
        "none_evidence_in_flight_rows": len(none_rows),
        "sensitive_early_settlement_contradictions": (
            sensitive_early_settlement_contradictions
        ),
        "observation_mismatches": observation_mismatches,
        "effect_count_mismatches": effect_count_mismatches,
        "outcome_ordering_mismatches": outcome_ordering_mismatches,
        "missing_ledger_operations": len(missing_ledger),
        "extra_ledger_operations": len(extra_ledger),
        "checks": checks,
        "archive_integrity_passed": all(checks.values()),
        "timestamp_margin_recoverable": False,
        "timestamp_limitation": (
            "The historical schema did not persist operation start time and "
            "cleared due_at on settlement, so an exact start-to-read margin cannot "
            "be reconstructed. Weak/authoritative observations are state-sensitive "
            "and rule out pre-probe settlement; none evidence is timing-insensitive, "
            "but its final effect count is invariant to settlement ordering."
        ),
    }


def audit_default_archives(results_root: Path) -> dict[str, Any]:
    specs = (
        (
            "pilot-v1",
            results_root / "live-pilot.jsonl",
            [results_root / "live-pilot.sqlite3"],
        ),
        (
            "confirmation-v2",
            results_root / "live-confirmation-v2.jsonl",
            [results_root / "live-confirmation-v2.sqlite3"],
        ),
        (
            "gpt54-replication-v1",
            results_root / "live-gpt54-replication-v1.jsonl",
            [
                results_root / "live-gpt54-replication-v1.sqlite3",
                results_root / "live-gpt54-replication-resume-v1.sqlite3",
            ],
        ),
        (
            "task-robustness-v1",
            results_root / "live-task-robustness-v1.jsonl",
            [results_root / "live-task-robustness-v1.sqlite3"],
        ),
    )
    datasets = [audit_archive_dataset(*spec) for spec in specs]
    return {
        "schema_version": "retrybench-live-archive-integrity-v1",
        "audit_type": "read_only_posthoc_wall_clock_integrity",
        "api_calls": 0,
        "api_cost_usd": 0.0,
        "datasets": datasets,
        "total_rows": sum(item["rows"] for item in datasets),
        "total_in_flight_rows": sum(item["in_flight_rows"] for item in datasets),
        "total_evidence_sensitive_in_flight_rows": sum(
            item["evidence_sensitive_in_flight_rows"] for item in datasets
        ),
        "total_none_evidence_in_flight_rows": sum(
            item["none_evidence_in_flight_rows"] for item in datasets
        ),
        "all_archives_passed": all(
            item["archive_integrity_passed"] for item in datasets
        ),
        "claim_boundary": (
            "The audit verifies archived outcomes and rules out pre-probe "
            "settlement wherever the evidence contract makes settlement visible. "
            "It does not claim a recoverable numeric timing margin."
        ),
    }


def write_archive_audit(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
