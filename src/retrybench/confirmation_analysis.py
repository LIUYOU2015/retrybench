"""Pre-specified analysis for the frozen confirmation-v2 model block."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from .analysis import exact_mcnemar_p, sanitize_row


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


def group_summary(
    rows: Iterable[Dict[str, object]], keys: Sequence[str]
) -> List[Dict[str, object]]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(str(row[key]) for key in keys)].append(row)
    output = []
    for coordinate, selected in sorted(groups.items()):
        result = {key: value for key, value in zip(keys, coordinate)}
        result["outcomes"] = len(selected)
        result["actions"] = dict(
            sorted(Counter(str(row["decision"]["action"]) for row in selected).items())
        )
        for metric in METRICS:
            result[metric] = sum(bool(row[metric]) for row in selected)
            result[metric + "_rate"] = result[metric] / len(selected)
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
            str(row["task_id"]),
            str(row["schedule"]),
            str(row["evidence"]),
            str(row["prompt_condition"]),
            int(row["repetition"]),
        ): row
        for row in rows
    }
    pairs = []
    for task_id in sorted({str(row["task_id"]) for row in rows}):
        for schedule in sorted({str(row["schedule"]) for row in rows}):
            for repetition in sorted({int(row["repetition"]) for row in rows}):
                left_key = (task_id, schedule, left[0], left[1], repetition)
                right_key = (task_id, schedule, right[0], right[1], repetition)
                if left_key not in index or right_key not in index:
                    continue
                pairs.append(
                    (bool(index[left_key][metric]), bool(index[right_key][metric]))
                )
    counts = Counter(pairs)
    left_total = sum(left for left, _ in pairs)
    right_total = sum(right for _, right in pairs)
    left_rate = left_total / len(pairs) if pairs else 0.0
    right_rate = right_total / len(pairs) if pairs else 0.0
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
        "left_rate": left_rate,
        "right_rate": right_rate,
        "absolute_rate_difference": left_rate - right_rate,
        "risk_ratio": left_rate / right_rate if right_rate else None,
        "exact_mcnemar_two_sided_p": exact_mcnemar_p(left_only, right_only),
        "dependence_note": (
            "The exact McNemar calculation is descriptive because weak actions are "
            "shared across three schedules within task/prompt/repetition blocks."
        ),
    }


def _task_direction_summary(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    output = []
    for task_id in sorted({str(row["task_id"]) for row in rows}):
        selected = [
            row
            for row in rows
            if row["task_id"] == task_id and row["prompt_condition"] == "neutral"
        ]
        weak = sum(
            bool(row["false_retry_permission"])
            for row in selected
            if row["evidence"] == "weak"
        )
        authoritative = sum(
            bool(row["false_retry_permission"])
            for row in selected
            if row["evidence"] == "authoritative"
        )
        output.append(
            {
                "task_id": task_id,
                "weak_false_retry_permission": weak,
                "authoritative_false_retry_permission": authoritative,
                "difference": weak - authoritative,
                "direction": (
                    "weak_higher"
                    if weak > authoritative
                    else "authoritative_higher" if weak < authoritative else "tie"
                ),
            }
        )
    return output


def analyze_confirmation(
    rows: List[Dict[str, object]],
    preflight: Dict[str, object],
    analysis_context: str = "confirmation",
) -> Dict[str, object]:
    if len(rows) != 240 or len({str(row["cell_id"]) for row in rows}) != 240:
        raise ValueError("analysis requires 240 unique confirmation outcomes")
    group_ids = {str(row["response_group_id"]) for row in rows}
    if len(group_ids) != 160:
        raise ValueError("analysis requires exactly 160 response groups")
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row["response_group_id"])].append(row)
    sharing_valid = all(
        all(
            (
                row["decision"]["response_id"],
                row["decision"]["action"],
                row["transcript_sha256"],
            )
            == (
                group[0]["decision"]["response_id"],
                group[0]["decision"]["action"],
                group[0]["transcript_sha256"],
            )
            for row in group
        )
        for group in grouped.values()
    ) and all(
        len(group) == (3 if group[0]["evidence"] == "weak" else 1)
        for group in grouped.values()
    )
    unique_decisions = [group[0]["decision"] for group in grouped.values()]
    usage_fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
    )
    neutral_contrasts = [
        paired_contrast(
            rows, ("weak", "neutral"), ("authoritative", "neutral"), metric
        )
        for metric in METRICS
    ]
    prompt_contrasts = [
        paired_contrast(
            rows, (evidence, "neutral"), (evidence, "cautious"), metric
        )
        for evidence in ("weak", "authoritative")
        for metric in METRICS
    ]
    return {
        "schema_version": "retrybench-confirmation-analysis-v2",
        "scored_outcomes": len(rows),
        "fresh_model_calls": len(group_ids),
        "model": sorted({str(row["model"]) for row in rows}),
        "actual_cost_usd": sum(float(decision["cost_usd"]) for decision in unique_decisions),
        "token_usage": {
            field: sum(int(decision["usage"][field]) for decision in unique_decisions)
            for field in usage_fields
        },
        "integrity": {
            "preflight_passed": bool(preflight["all_zero_cost_gates_passed"]),
            "complete_unique_outcomes": True,
            "exactly_160_response_groups": True,
            "shared_response_action_and_transcript_match": sharing_valid,
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
        "paired_neutral_weak_vs_authoritative": neutral_contrasts,
        "paired_prompt_contrasts": prompt_contrasts,
        "task_direction_sensitivity": _task_direction_summary(rows),
        "interpretation_rule": (
            "Assess effect sizes, raw discordance, task-direction consistency, and "
            "safety/liveness jointly; confirmation-v2 has no post-hoc significance threshold."
        ),
        "limitations": [
            (
                "One fixed model snapshot and four task templates."
                if analysis_context == "confirmation"
                else "This report covers one replication snapshot and four task templates; interpret it with confirmation-v2."
            ),
            "Weak decisions are shared across schedules, so outcome pairs are block-dependent.",
            "Controlled schedules do not estimate production prevalence.",
            (
                "A full-paper claim still requires framework evidence and an independent model replication."
                if analysis_context == "confirmation"
                else "Cross-model direction replicated, but task-level heterogeneity rules out a task-invariant claim."
            ),
        ],
    }


def write_sanitized(path: Path, rows: Iterable[Dict[str, object]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            encoded = (json.dumps(sanitize_row(row), sort_keys=True) + "\n").encode("utf-8")
            handle.write(encoded.decode("utf-8"))
            digest.update(encoded)
    return digest.hexdigest()


def write_analysis(path: Path, report: Dict[str, object], outcomes_hash: str) -> None:
    output = dict(report)
    output["sanitized_outcomes_sha256"] = outcomes_hash
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
