"""Transparent aggregation without hiding denominators."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from .benchmark import EpisodeResult


def summarize(results: Iterable[EpisodeResult]) -> Dict[str, object]:
    rows = list(results)
    by_policy = defaultdict(list)  # type: Dict[str, List[EpisodeResult]]
    for row in rows:
        by_policy[row.policy].append(row)

    def stats(group: List[EpisodeResult]) -> Dict[str, object]:
        n = len(group)
        return {
            "episodes": n,
            "exact_state_success": sum(row.exact_state_success for row in group),
            "duplicates": sum(row.duplicate_effect for row in group),
            "omissions": sum(row.omission for row in group),
            "unresolved": sum(row.unresolved for row in group),
            "wrong_operation_identity": sum(
                row.wrong_operation_identity for row in group
            ),
            "wrong_task": sum(row.wrong_task for row in group),
            "wrong_tool": sum(row.wrong_tool for row in group),
            "wrong_target": sum(row.wrong_target for row in group),
            "wrong_payload": sum(row.wrong_payload for row in group),
            "retries": sum(row.retries for row in group),
            "probes": sum(row.probes for row in group),
            "exact_state_success_rate": (sum(row.exact_state_success for row in group) / n) if n else None,
        }

    return {
        "schema_version": "retrybench-summary-v1",
        "overall": stats(rows),
        "by_policy": {name: stats(group) for name, group in sorted(by_policy.items())},
    }
