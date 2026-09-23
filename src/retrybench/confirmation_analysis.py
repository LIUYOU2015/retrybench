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
        "outcome_level_exact_mcnemar_two_sided_p_descriptive_only": exact_mcnemar_p(
            left_only, right_only
        ),
        "dependence_note": (
            "Do not use the outcome-level exact McNemar value as inferential evidence: "
            "weak actions are shared across three schedules within task/prompt/repetition "
            "blocks, so the 60 outcome pairs are not independent."
        ),
    }


def _clustered_primary_analysis(rows: List[Dict[str, object]]) -> Dict[str, object]:
    """Analyze the primary contrast at response-block and task-family levels."""
    selected = [row for row in rows if row["prompt_condition"] == "neutral"]
    blocks = defaultdict(list)
    for row in selected:
        blocks[(str(row["task_id"]), int(row["repetition"]))].append(row)
    if len(blocks) != 20 or any(len(block) != 6 for block in blocks.values()):
        raise ValueError("primary clustered analysis requires 20 complete six-outcome blocks")

    block_pairs = []
    block_differences = []
    for block in blocks.values():
        weak = [row for row in block if row["evidence"] == "weak"]
        authoritative = [row for row in block if row["evidence"] == "authoritative"]
        if len(weak) != 3 or len(authoritative) != 3:
            raise ValueError("each primary block requires three outcomes per evidence contract")
        weak_count = sum(bool(row["false_retry_permission"]) for row in weak)
        authoritative_count = sum(
            bool(row["false_retry_permission"]) for row in authoritative
        )
        block_pairs.append((weak_count > 0, authoritative_count > 0))
        block_differences.append((weak_count - authoritative_count) / 3.0)

    block_counts = Counter(block_pairs)
    weak_only = block_counts[(True, False)]
    authoritative_only = block_counts[(False, True)]

    task_effects = []
    for task_id in sorted({str(row["task_id"]) for row in selected}):
        task_rows = [row for row in selected if row["task_id"] == task_id]
        weak_rows = [row for row in task_rows if row["evidence"] == "weak"]
        authoritative_rows = [
            row for row in task_rows if row["evidence"] == "authoritative"
        ]
        weak_rate = sum(bool(row["false_retry_permission"]) for row in weak_rows) / len(
            weak_rows
        )
        authoritative_rate = sum(
            bool(row["false_retry_permission"]) for row in authoritative_rows
        ) / len(authoritative_rows)
        task_effects.append(
            {
                "task_id": task_id,
                "weak_outcomes": len(weak_rows),
                "authoritative_outcomes": len(authoritative_rows),
                "weak_rate": weak_rate,
                "authoritative_rate": authoritative_rate,
                "rate_difference": weak_rate - authoritative_rate,
            }
        )

    differences = [float(item["rate_difference"]) for item in task_effects]
    task_count = len(differences)
    mean_difference = sum(differences) / task_count
    sample_variance = (
        sum((value - mean_difference) ** 2 for value in differences)
        / (task_count - 1)
        if task_count > 1
        else 0.0
    )
    standard_error = (sample_variance / task_count) ** 0.5
    # Four preregistered task families imply df=3 for this task-clustered interval.
    t_critical_95_df3 = 3.182446305
    lower = mean_difference - t_critical_95_df3 * standard_error
    upper = mean_difference + t_critical_95_df3 * standard_error

    return {
        "estimand": "neutral weak minus neutral authoritative false-retry-permission rate",
        "response_block_level": {
            "blocks": len(blocks),
            "block_definition": "task_id x repetition; each block contains three schedules per evidence contract",
            "weak_any_false_retry": sum(left for left, _ in block_pairs),
            "authoritative_any_false_retry": sum(right for _, right in block_pairs),
            "weak_only": weak_only,
            "authoritative_only": authoritative_only,
            "both": block_counts[(True, True)],
            "neither": block_counts[(False, False)],
            "mean_within_block_schedule_rate_difference": sum(block_differences)
            / len(block_differences),
            "exact_mcnemar_two_sided_p_descriptive_only": exact_mcnemar_p(
                weak_only, authoritative_only
            ),
            "inference_note": (
                "This removes three-schedule pseudoreplication, but the 20 blocks remain "
                "nested within only four task families; do not use this p-value for "
                "task-population generalization."
            ),
        },
        "task_family_level": {
            "task_families": task_count,
            "effects": task_effects,
            "equal_task_weight_mean_rate_difference": mean_difference,
            "task_cluster_standard_error": standard_error,
            "task_cluster_t_95_interval_unbounded": [lower, upper],
            "task_cluster_t_95_interval_bounded_to_rate_difference": [
                max(-1.0, lower),
                min(1.0, upper),
            ],
            "degrees_of_freedom": task_count - 1,
            "inference_note": (
                "The t interval treats the four task families as the top-level sampling "
                "units. With only four clusters it is unstable and low-powered; report "
                "the task-specific effects and interval, not a task-general p-value."
            ),
        },
        "headline_rule": (
            "Lead with effect sizes, raw block discordance, task-specific effects, and "
            "the task-clustered interval. Outcome-level McNemar values are descriptive only."
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
        "schema_version": "retrybench-confirmation-analysis-v3",
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
        "clustered_primary_false_retry_analysis": _clustered_primary_analysis(rows),
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
