"""Frozen new-task and lexical-counterbalancing robustness protocol."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from .confirmation import load_resume_state
from .experiment import HTTPExperimentClient, expected_observed_state
from .http_service import RetryBenchHTTPService
from .model import Action, EvidenceContract, ObservedState, Schedule, TASKS, TaskSpec
from .openai_adapter import (
    CostBudget,
    OpenAIResponsesPolicy,
    build_decision_input,
    maximum_decision_cost,
)
from .scoring import retry_is_permitted, score_exact_state


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


def run_live_task_robustness(
    rows: List[RobustnessCell],
    policy: OpenAIResponsesPolicy,
    budget: CostBudget,
    database_path: Path,
    output_path: Path,
    late_commit_delay: float = 0.1,
    resume: bool = False,
) -> List[Dict[str, object]]:
    """Execute one response per frozen group and replay weak actions by schedule."""
    run_robustness_preflight(rows)
    if policy.model != ROBUSTNESS_MODEL:
        raise ValueError("task-robustness model must be %s" % ROBUSTNESS_MODEL)
    if policy.max_output_tokens != ROBUSTNESS_MAX_OUTPUT_TOKENS:
        raise ValueError(
            "task-robustness max output tokens must be %d"
            % ROBUSTNESS_MAX_OUTPUT_TOKENS
        )
    if budget.max_cost_usd > ROBUSTNESS_MAX_COST_USD:
        raise ValueError(
            "task-robustness budget may not exceed $%.2f"
            % ROBUSTNESS_MAX_COST_USD
        )
    if database_path.exists():
        raise FileExistsError("task-robustness database must not already exist")

    schema_version = "retrybench-live-task-robustness-v1"
    if resume:
        if not output_path.exists():
            raise FileNotFoundError("resume output does not exist")
        results, completed_groups, recovered_spend, recovered_requests = load_resume_state(
            output_path, rows, ROBUSTNESS_MODEL, schema_version
        )
        budget.spent_usd = recovered_spend
        budget.requests = recovered_requests
        if budget.spent_usd > budget.max_cost_usd:
            raise ValueError("resume output already exceeds the configured budget")
        output_mode = "a"
    else:
        if output_path.exists():
            raise FileExistsError("task-robustness output must not already exist")
        results = []
        completed_groups = set()
        output_mode = "x"

    task_by_id = {task.task.task_id: task for task in ROBUSTNESS_TASKS}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open(output_mode, encoding="utf-8") as output:
        with RetryBenchHTTPService(
            database_path,
            late_commit_delay=late_commit_delay,
            manual_settlement=True,
        ) as service:
            client = HTTPExperimentClient(service.base_url)
            for group in _group_rows(rows).values():
                if group[0].response_group_id in completed_groups:
                    continue
                prepared = []
                for row in group:
                    robustness_task = task_by_id[row.task_id]
                    task = robustness_task.task
                    schedule = Schedule(row.schedule)
                    evidence = EvidenceContract(row.evidence)
                    operation_id = "task-robustness:%s" % row.cell_id
                    status, timeout_body = client.start(operation_id, task, schedule)
                    observed = client.status(operation_id, evidence)
                    instructions, prompt = build_decision_input(
                        task, evidence, observed, cautious_prompt=False
                    )
                    actual_hash = _canonical_hash(
                        {"instructions": instructions, "prompt": prompt}
                    )
                    if not (
                        status == 504
                        and timeout_body == {"error": "tool call timed out"}
                        and observed.value == row.expected_observed_state
                        and actual_hash == row.transcript_sha256
                    ):
                        raise RuntimeError("observation diverged before %s" % row.cell_id)
                    prepared.append((row, task, schedule, evidence, observed, operation_id))

                first = prepared[0]
                decision = policy.decide(
                    first[1], first[3], first[4], False, budget
                )
                for row, task, schedule, evidence, observed, operation_id in prepared:
                    if decision.action == Action.RETRY:
                        client.retry(operation_id, stable_idempotency=False)
                    if schedule == Schedule.IN_FLIGHT_LATE_COMMIT:
                        client.advance(operation_id)
                    unresolved = decision.action in {Action.WAIT, Action.UNRESOLVED}
                    effects = client.effects(operation_id)
                    score = score_exact_state(task, operation_id, effects, unresolved)
                    retry_permitted = retry_is_permitted(
                        schedule, evidence, observed
                    )
                    result = {
                        "schema_version": schema_version,
                        "cell_id": row.cell_id,
                        "response_group_id": row.response_group_id,
                        "shared_group_size": len(group),
                        "family_id": row.family_id,
                        "lexical_frame": row.lexical_frame,
                        "task_id": row.task_id,
                        "schedule": row.schedule,
                        "evidence": row.evidence,
                        "repetition": row.repetition,
                        "model": decision.model,
                        "operation_id": operation_id,
                        "observed_state": observed.value,
                        "transcript_sha256": row.transcript_sha256,
                        "decision": decision.to_dict(),
                        "retry_permitted": retry_permitted,
                        "false_retry_permission": (
                            decision.action == Action.RETRY and not retry_permitted
                        ),
                        "effect_count": len(effects),
                        **score.to_dict(),
                        "cumulative_cost_usd": budget.spent_usd,
                    }
                    output.write(json.dumps(result, sort_keys=True) + "\n")
                    output.flush()
                    results.append(result)
    return results


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
    frame_evidence_effects = {"create": [], "noncreate": []}
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
        for frame in ("create", "noncreate"):
            weak_frame = [row for row in weak if row["lexical_frame"] == frame]
            authoritative_frame = [
                row
                for row in authoritative
                if row["lexical_frame"] == frame
            ]
            weak_frame_rate = sum(
                bool(row["false_retry_permission"]) for row in weak_frame
            ) / len(weak_frame)
            authoritative_frame_rate = sum(
                bool(row["false_retry_permission"])
                for row in authoritative_frame
            ) / len(authoritative_frame)
            frame_evidence_effects[frame].append(
                {
                    "family_id": family_id,
                    "weak_rate": weak_frame_rate,
                    "authoritative_rate": authoritative_frame_rate,
                    "rate_difference": weak_frame_rate - authoritative_frame_rate,
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
    within_frame = {}
    for frame, frame_effects in frame_evidence_effects.items():
        frame_differences = [
            float(item["rate_difference"]) for item in frame_effects
        ]
        frame_mean = sum(frame_differences) / len(frame_differences)
        frame_variance = sum(
            (value - frame_mean) ** 2 for value in frame_differences
        ) / (len(frame_differences) - 1)
        frame_standard_error = math.sqrt(frame_variance / len(frame_differences))
        within_frame[frame] = {
            "family_effects": frame_effects,
            "weak_higher_families": sum(value > 0 for value in frame_differences),
            "equal_family_mean_rate_difference": frame_mean,
            "task_cluster_standard_error": frame_standard_error,
            "task_cluster_t_95_interval_bounded": [
                max(-1.0, frame_mean - critical * frame_standard_error),
                min(1.0, frame_mean + critical * frame_standard_error),
            ],
        }
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
        "post_hoc_within_frame_evidence_contrasts": {
            "status": "post_hoc_construct_validity_check",
            "frames": within_frame,
        },
        "predeclared_decision_rule": {
            "stronger_empirical_paper_path": "at least 6/8 weak-higher families and task-cluster interval lower bound above zero",
            "directional_artifact_first_path": "at least 5/8 weak-higher families and positive mean, but strong criterion not met",
            "no_task_generality_support": "all other outcomes",
        },
        "interpretation": "Task family is the top-level analysis unit; the eight hand-designed families are not a probability sample, and schedule outcomes and lexical variants are not independent task samples.",
    }
