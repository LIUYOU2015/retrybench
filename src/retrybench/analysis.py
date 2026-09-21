"""Reproducible aggregation and sanitization for the frozen live pilot."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


METRICS = (
    "false_retry_permission",
    "duplicate_effect",
    "omission",
    "unresolved",
    "exact_state_success",
)


def load_jsonl(path: Path) -> List[Dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def exact_mcnemar_p(left_only: int, right_only: int) -> float:
    """Two-sided exact McNemar/binomial p-value for discordant pairs."""
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, value)
        for value in range(min(left_only, right_only) + 1)
    ) / (2**discordant)
    return min(1.0, 2 * tail)


def group_summary(
    rows: Iterable[Dict[str, object]], keys: Sequence[str]
) -> List[Dict[str, object]]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(str(row[key]) for key in keys)].append(row)
    output = []
    for coordinate, selected in sorted(groups.items()):
        result = {key: value for key, value in zip(keys, coordinate)}
        result["episodes"] = len(selected)
        result["actions"] = dict(
            sorted(Counter(str(row["decision"]["action"]) for row in selected).items())
        )
        for metric in METRICS:
            result[metric] = sum(bool(row[metric]) for row in selected)
        output.append(result)
    return output


def paired_contrast(
    rows: List[Dict[str, object]],
    left: Tuple[str, str],
    right: Tuple[str, str],
    metric: str,
) -> Dict[str, object]:
    index = {
        (
            row["task_id"],
            row["schedule"],
            row["evidence"],
            row["prompt_condition"],
        ): row
        for row in rows
    }
    pairs = []
    for task_id in sorted({str(row["task_id"]) for row in rows}):
        for schedule in sorted({str(row["schedule"]) for row in rows}):
            left_key = (task_id, schedule, left[0], left[1])
            right_key = (task_id, schedule, right[0], right[1])
            if left_key in index and right_key in index:
                pairs.append(
                    (bool(index[left_key][metric]), bool(index[right_key][metric]))
                )
    counts = Counter(pairs)
    left_only = counts[(True, False)]
    right_only = counts[(False, True)]
    return {
        "metric": metric,
        "left": {"evidence": left[0], "prompt_condition": left[1]},
        "right": {"evidence": right[0], "prompt_condition": right[1]},
        "pairs": len(pairs),
        "neither": counts[(False, False)],
        "right_only": right_only,
        "left_only": left_only,
        "both": counts[(True, True)],
        "exact_mcnemar_two_sided_p": exact_mcnemar_p(left_only, right_only),
    }


def sanitize_row(row: Dict[str, object]) -> Dict[str, object]:
    sanitized = dict(row)
    decision = dict(sanitized["decision"])
    decision.pop("response_id", None)
    sanitized["decision"] = decision
    return sanitized


def analyze_pilot(
    rows: List[Dict[str, object]], preflight: Dict[str, object]
) -> Dict[str, object]:
    if len(rows) != 96 or len({row["cell_id"] for row in rows}) != 96:
        raise ValueError("analysis requires the complete unique 96-cell pilot")
    weak_not_found = [
        row
        for row in rows
        if row["evidence"] == "weak" and row["observed_state"] == "not_found"
    ]
    committed = [row for row in rows if row["observed_state"] == "committed"]
    neutral_weak_vs_authoritative = [
        paired_contrast(
            rows,
            ("weak", "neutral"),
            ("authoritative", "neutral"),
            metric,
        )
        for metric in METRICS
    ]
    prompt_contrasts = [
        paired_contrast(rows, (evidence, "neutral"), (evidence, "cautious"), metric)
        for evidence in ("none", "weak", "authoritative")
        for metric in METRICS
    ]
    weak_false_retry = next(
        item
        for item in neutral_weak_vs_authoritative
        if item["metric"] == "false_retry_permission"
    )
    gates = {
        "complete_frozen_pilot": len(rows) == 96,
        "preflight_remained_valid": bool(preflight["all_zero_cost_gates_passed"]),
        "material_evidence_conclusion_sensitivity": (
            weak_false_retry["left_only"] >= 8
            and weak_false_retry["right_only"] == 0
        ),
        "matched_weak_negative_exposes_unsafe_outcomes": any(
            row["duplicate_effect"]
            and row["schedule"]
            in {"in_flight_late_commit", "stale_negative_after_commit"}
            for row in weak_not_found
        ),
        "cautious_prompt_exposes_safety_liveness_tradeoff": (
            sum(
                bool(row["false_retry_permission"])
                for row in rows
                if row["prompt_condition"] == "cautious"
            )
            == 0
            and sum(
                bool(row["unresolved"])
                for row in rows
                if row["prompt_condition"] == "cautious"
            )
            > 0
        ),
        "runtime_controls_close_the_gap": (
            preflight["gates"]["authoritative_control_exact_state"]
            and preflight["gates"]["stable_idempotency_control_exact_state"]
        ),
    }
    usage_fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
    )
    return {
        "schema_version": "retrybench-pilot-analysis-v1",
        "pilot_cells": len(rows),
        "model": sorted({str(row["model"]) for row in rows}),
        "actual_cost_usd": sum(float(row["decision"]["cost_usd"]) for row in rows),
        "token_usage": {
            field: sum(int(row["decision"]["usage"][field]) for row in rows)
            for field in usage_fields
        },
        "overall": {
            "actions": dict(
                sorted(Counter(str(row["decision"]["action"]) for row in rows).items())
            ),
            **{metric: sum(bool(row[metric]) for row in rows) for metric in METRICS},
        },
        "by_evidence_and_prompt": group_summary(
            rows, ("evidence", "prompt_condition")
        ),
        "by_schedule_evidence_and_prompt": group_summary(
            rows, ("schedule", "evidence", "prompt_condition")
        ),
        "weak_not_found_matched_cells": group_summary(
            weak_not_found, ("schedule", "prompt_condition")
        ),
        "committed_observation_cells": group_summary(
            committed, ("evidence", "prompt_condition")
        ),
        "paired_neutral_weak_vs_authoritative": neutral_weak_vs_authoritative,
        "paired_prompt_contrasts": prompt_contrasts,
        "empirical_novelty_gates": gates,
        "all_empirical_novelty_gates_passed": all(gates.values()),
        "decision": (
            "GO_ARTIFACT_AND_TARGETED_CONFIRMATION"
            if all(gates.values())
            else "NO_GO_REPOSITION_AS_REPLICATION"
        ),
        "limitations": [
            "One fixed model snapshot.",
            "One sample per cell and four task templates.",
            "No production prevalence claim.",
            "Pilot p-values are descriptive and do not replace task-level replication.",
            "Prompt and evidence effects may interact with unmeasured model stochasticity.",
        ],
    }


def write_sanitized(path: Path, rows: Iterable[Dict[str, object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_row(row), sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_analysis(path: Path, report: Dict[str, object], outcomes_sha256: str) -> None:
    value = dict(report)
    value["sanitized_outcomes_sha256"] = outcomes_sha256
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
