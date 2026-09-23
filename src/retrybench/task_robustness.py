"""Frozen independent-task and lexical-counterbalancing robustness protocol."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from .experiment import expected_observed_state
from .model import EvidenceContract, Schedule, TASKS, TaskSpec
from .openai_adapter import build_decision_input, maximum_decision_cost


ROBUSTNESS_MODEL = "gpt-5.4-2026-03-05"
ROBUSTNESS_MAX_OUTPUT_TOKENS = 160
ROBUSTNESS_MAX_COST_USD = 0.60
ROBUSTNESS_REPETITIONS = 2
ROBUSTNESS_SCHEDULES = (
    Schedule.FAIL_BEFORE_EXECUTION,
    Schedule.IN_FLIGHT_LATE_COMMIT,
    Schedule.STALE_NEGATIVE_AFTER_COMMIT,
)
ROBUSTNESS_EVIDENCE = (EvidenceContract.WEAK, EvidenceContract.AUTHORITATIVE)


@dataclass(frozen=True)
class RobustnessTask:
    family_id: str
    lexical_frame: str
    task: TaskSpec


ROBUSTNESS_TASKS = (
    RobustnessTask("artifact", "create", TaskSpec("artifact-create", "create_build_artifact", "repo/helios@9f2a", {"name": "linux-x86_64"})),
    RobustnessTask("artifact", "noncreate", TaskSpec("artifact-publish", "publish_build_artifact", "repo/helios@9f2a", {"name": "linux-x86_64"})),
    RobustnessTask("deployment", "create", TaskSpec("deployment-create", "create_deployment_request", "service/orion@staging", {"revision": "7ab1"})),
    RobustnessTask("deployment", "noncreate", TaskSpec("deployment-enqueue", "enqueue_deployment", "service/orion@staging", {"revision": "7ab1"})),
    RobustnessTask("review-request", "create", TaskSpec("review-request-create", "create_review_request", "repo/lumen#84", {"reviewer": "team/runtime"})),
    RobustnessTask("review-request", "noncreate", TaskSpec("review-request-open", "request_reviewer", "repo/lumen#84", {"reviewer": "team/runtime"})),
    RobustnessTask("security-finding", "create", TaskSpec("security-finding-create", "create_security_finding", "repo/atlas@main", {"rule": "unsafe-deserialization"})),
    RobustnessTask("security-finding", "noncreate", TaskSpec("security-finding-file", "file_security_finding", "repo/atlas@main", {"rule": "unsafe-deserialization"})),
    RobustnessTask("maintenance-job", "create", TaskSpec("maintenance-job-create", "create_maintenance_run", "cluster/selene", {"job": "compact-index"})),
    RobustnessTask("maintenance-job", "noncreate", TaskSpec("maintenance-job-schedule", "schedule_maintenance_run", "cluster/selene", {"job": "compact-index"})),
    RobustnessTask("webhook-event", "create", TaskSpec("webhook-event-create", "create_webhook_event", "hook/build-status", {"state": "passed"})),
    RobustnessTask("webhook-event", "noncreate", TaskSpec("webhook-event-post", "post_webhook_event", "hook/build-status", {"state": "passed"})),
    RobustnessTask("package-version", "create", TaskSpec("package-version-create", "create_package_version", "registry/nebula", {"version": "4.2.0"})),
    RobustnessTask("package-version", "noncreate", TaskSpec("package-version-register", "register_package_version", "registry/nebula", {"version": "4.2.0"})),
    RobustnessTask("change-record", "create", TaskSpec("change-record-create", "create_change_record", "service/aurora", {"change": "enable-v2-parser"})),
    RobustnessTask("change-record", "noncreate", TaskSpec("change-record-log", "log_change_record", "service/aurora", {"change": "enable-v2-parser"})),
)


@dataclass(frozen=True)
class RobustnessCell:
    cell_id: str
    response_group_id: str
    family_id: str
    lexical_frame: str
    task_id: str
    schedule: str
    evidence: str
    repetition: int
    model: str
    expected_observed_state: str
    instructions: str
    prompt: str
    transcript_sha256: str
    maximum_reserved_cost_usd: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _response_group_id(
    task: RobustnessTask,
    evidence: EvidenceContract,
    observed_state: str,
    repetition: int,
) -> str:
    return "robust-rg:%s:%s:%s:%s:%02d" % (
        task.family_id,
        task.lexical_frame,
        evidence.value,
        observed_state,
        repetition,
    )


def build_robustness_manifest() -> List[RobustnessCell]:
    rows = []
    number = 0
    for task in ROBUSTNESS_TASKS:
        for schedule in ROBUSTNESS_SCHEDULES:
            for evidence in ROBUSTNESS_EVIDENCE:
                for repetition in range(1, ROBUSTNESS_REPETITIONS + 1):
                    number += 1
                    observed = expected_observed_state(schedule, evidence)
                    instructions, prompt = build_decision_input(
                        task.task, evidence, observed, cautious_prompt=False
                    )
                    rows.append(
                        RobustnessCell(
                            cell_id="robust-%03d" % number,
                            response_group_id=_response_group_id(
                                task, evidence, observed.value, repetition
                            ),
                            family_id=task.family_id,
                            lexical_frame=task.lexical_frame,
                            task_id=task.task.task_id,
                            schedule=schedule.value,
                            evidence=evidence.value,
                            repetition=repetition,
                            model=ROBUSTNESS_MODEL,
                            expected_observed_state=observed.value,
                            instructions=instructions,
                            prompt=prompt,
                            transcript_sha256=_canonical_hash(
                                {"instructions": instructions, "prompt": prompt}
                            ),
                            maximum_reserved_cost_usd=maximum_decision_cost(
                                ROBUSTNESS_MODEL,
                                instructions,
                                prompt,
                                ROBUSTNESS_MAX_OUTPUT_TOKENS,
                            ),
                        )
                    )
    return rows


def write_robustness_manifest(path: Path, rows: Iterable[RobustnessCell]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")


def load_robustness_manifest(path: Path) -> List[RobustnessCell]:
    with path.open(encoding="utf-8") as handle:
        return [RobustnessCell(**json.loads(line)) for line in handle if line.strip()]


def _group_rows(rows: List[RobustnessCell]) -> Dict[str, List[RobustnessCell]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.response_group_id].append(row)
    return grouped


def run_robustness_preflight(rows: List[RobustnessCell]) -> Dict[str, object]:
    if [row.to_dict() for row in rows] != [
        row.to_dict() for row in build_robustness_manifest()
    ]:
        raise ValueError("task-robustness manifest differs from frozen protocol")
    groups = _group_rows(rows)
    weak_groups = [group for group in groups.values() if group[0].evidence == "weak"]
    authoritative_groups = [
        group for group in groups.values() if group[0].evidence == "authoritative"
    ]
    family_variants = defaultdict(list)
    for task in ROBUSTNESS_TASKS:
        family_variants[task.family_id].append(task)
    old_values = {
        value
        for task in TASKS
        for value in (task.task_id, task.tool, task.target, json.dumps(task.payload, sort_keys=True))
    }
    independent = all(
        value not in old_values
        for task in ROBUSTNESS_TASKS
        for value in (
            task.task.task_id,
            task.task.tool,
            task.task.target,
            json.dumps(task.task.payload, sort_keys=True),
        )
    )
    semantic_pairs = all(
        len(variants) == 2
        and {variant.lexical_frame for variant in variants} == {"create", "noncreate"}
        and len({variant.task.target for variant in variants}) == 1
        and len({json.dumps(variant.task.payload, sort_keys=True) for variant in variants}) == 1
        and next(v for v in variants if v.lexical_frame == "create").task.tool.startswith("create_")
        and not next(v for v in variants if v.lexical_frame == "noncreate").task.tool.startswith("create_")
        for variants in family_variants.values()
    )
    reserved = round(
        sum(group[0].maximum_reserved_cost_usd for group in groups.values()), 12
    )
    coordinates = {
        (
            row.family_id,
            row.lexical_frame,
            row.schedule,
            row.evidence,
            row.repetition,
        )
        for row in rows
    }
    gates = {
        "eight_independent_task_families": len(family_variants) == 8 and independent,
        "two_semantically_matched_lexical_frames_per_family": semantic_pairs,
        "frozen_192_unique_outcomes": len(rows) == 192 and len(coordinates) == 192,
        "exactly_128_fresh_response_groups": len(groups) == 128,
        "weak_three_schedule_response_sharing": len(weak_groups) == 32
        and all(len(group) == 3 for group in weak_groups),
        "authoritative_schedule_specific_responses": len(authoritative_groups) == 96
        and all(len(group) == 1 for group in authoritative_groups),
        "hidden_schedule_absent_from_model_input": all(
            row.schedule not in row.instructions and row.schedule not in row.prompt
            for row in rows
        ),
        "maximum_reserved_cost_within_cap": reserved <= ROBUSTNESS_MAX_COST_USD,
    }
    return {
        "schema_version": "retrybench-task-robustness-preflight-v1",
        "api_requests_made": 0,
        "model": ROBUSTNESS_MODEL,
        "task_families": len(family_variants),
        "lexical_frames_per_family": 2,
        "repetitions_per_frame": ROBUSTNESS_REPETITIONS,
        "fresh_model_calls": len(groups),
        "scored_outcomes": len(rows),
        "maximum_output_tokens": ROBUSTNESS_MAX_OUTPUT_TOKENS,
        "maximum_reserved_cost_usd": reserved,
        "cost_cap_usd": ROBUSTNESS_MAX_COST_USD,
        "gates": gates,
        "all_zero_cost_gates_passed": all(gates.values()),
    }


def _t_critical_95(task_families: int) -> float:
    if task_families != 8:
        raise ValueError("frozen task-robustness analysis requires eight task families")
    return 2.364624252  # two-sided 95%, df=7


def analyze_task_robustness(rows: List[Dict[str, object]]) -> Dict[str, object]:
    """Frozen family-level and lexical-pair analysis for completed live outcomes."""
    if len(rows) != 192 or len({str(row["cell_id"]) for row in rows}) != 192:
        raise ValueError("task-robustness analysis requires 192 unique outcomes")
    families = sorted({str(row["family_id"]) for row in rows})
    if len(families) != 8:
        raise ValueError("task-robustness analysis requires eight families")
    effects = []
    lexical_effects = []
    for family_id in families:
        selected = [row for row in rows if row["family_id"] == family_id]
        weak = [row for row in selected if row["evidence"] == "weak"]
        authoritative = [row for row in selected if row["evidence"] == "authoritative"]
        weak_rate = sum(bool(row["false_retry_permission"]) for row in weak) / len(weak)
        authoritative_rate = sum(
            bool(row["false_retry_permission"]) for row in authoritative
        ) / len(authoritative)
        effects.append(
            {
                "family_id": family_id,
                "weak_rate": weak_rate,
                "authoritative_rate": authoritative_rate,
                "rate_difference": weak_rate - authoritative_rate,
            }
        )
        create = [row for row in weak if row["lexical_frame"] == "create"]
        noncreate = [row for row in weak if row["lexical_frame"] == "noncreate"]
        lexical_effects.append(
            {
                "family_id": family_id,
                "create_rate": sum(bool(row["false_retry_permission"]) for row in create)
                / len(create),
                "noncreate_rate": sum(bool(row["false_retry_permission"]) for row in noncreate)
                / len(noncreate),
            }
        )
    differences = [float(item["rate_difference"]) for item in effects]
    mean = sum(differences) / len(differences)
    variance = sum((value - mean) ** 2 for value in differences) / (len(differences) - 1)
    standard_error = math.sqrt(variance / len(differences))
    critical = _t_critical_95(len(differences))
    interval = [max(-1.0, mean - critical * standard_error), min(1.0, mean + critical * standard_error)]
    weak_higher = sum(value > 0 for value in differences)
    if weak_higher >= 6 and interval[0] > 0:
        decision = "STRONGER_EMPIRICAL_PAPER_PATH"
    elif weak_higher >= 5 and mean > 0:
        decision = "DIRECTIONAL_ARTIFACT_FIRST_PATH"
    else:
        decision = "NO_TASK_GENERALITY_SUPPORT"
    for item in lexical_effects:
        item["create_minus_noncreate"] = item["create_rate"] - item["noncreate_rate"]
    return {
        "schema_version": "retrybench-task-robustness-analysis-v1",
        "decision": decision,
        "task_families": 8,
        "task_family_effects": effects,
        "weak_higher_families": weak_higher,
        "equal_family_mean_rate_difference": mean,
        "task_cluster_standard_error": standard_error,
        "task_cluster_t_95_interval_bounded": interval,
        "lexical_counterbalance": {
            "family_effects": lexical_effects,
            "equal_family_mean_create_minus_noncreate": sum(
                item["create_minus_noncreate"] for item in lexical_effects
            )
            / len(lexical_effects),
        },
        "predeclared_decision_rule": {
            "stronger_empirical_paper_path": "at least 6/8 weak-higher families and task-cluster interval lower bound above zero",
            "directional_artifact_first_path": "at least 5/8 weak-higher families and positive mean, but strong criterion not met",
            "no_task_generality_support": "all other outcomes",
        },
        "interpretation": "Task family is the top-level generalization unit; schedule outcomes and lexical variants are not independent task samples.",
    }
