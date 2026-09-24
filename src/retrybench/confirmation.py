"""Frozen targeted confirmation with shared model responses across hidden schedules."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from .experiment import HTTPExperimentClient, expected_observed_state
from .http_service import RetryBenchHTTPService
from .model import Action, EvidenceContract, ObservedState, Schedule, TASKS
from .openai_adapter import (
    CostBudget,
    OpenAIResponsesPolicy,
    build_decision_input,
    maximum_decision_cost,
)
from .scoring import retry_is_permitted, score_exact_state


CONFIRMATION_MODEL = "gpt-5.4-mini-2026-03-17"
CONFIRMATION_MAX_OUTPUT_TOKENS = 256
CONFIRMATION_MAX_COST_USD = 1.0
CONFIRMATION_REPETITIONS = 5
CONFIRMATION_SCHEDULES = (
    Schedule.FAIL_BEFORE_EXECUTION,
    Schedule.IN_FLIGHT_LATE_COMMIT,
    Schedule.STALE_NEGATIVE_AFTER_COMMIT,
)
CONFIRMATION_EVIDENCE = (EvidenceContract.WEAK, EvidenceContract.AUTHORITATIVE)
PROMPT_CONDITIONS = ("neutral", "cautious")


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ConfirmationCell:
    cell_id: str
    response_group_id: str
    task_id: str
    schedule: str
    evidence: str
    prompt_condition: str
    repetition: int
    model: str
    expected_observed_state: str
    instructions: str
    prompt: str
    transcript_sha256: str
    maximum_reserved_cost_usd: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _response_group_id(
    task_id: str,
    evidence: EvidenceContract,
    observed: ObservedState,
    prompt_condition: str,
    repetition: int,
    prefix: str = "confirm-rg",
) -> str:
    return "%s:%s:%s:%s:%s:%02d" % (
        prefix,
        task_id,
        evidence.value,
        observed.value,
        prompt_condition,
        repetition,
    )


def build_confirmation_manifest(
    model: str = CONFIRMATION_MODEL,
    cell_prefix: str = "confirm",
    response_group_prefix: str = "confirm-rg",
    max_output_tokens: int = CONFIRMATION_MAX_OUTPUT_TOKENS,
) -> List[ConfirmationCell]:
    """Return the preregistered 240 outcomes and 160 response groups."""
    rows = []
    number = 0
    for task in TASKS:
        for schedule in CONFIRMATION_SCHEDULES:
            for evidence in CONFIRMATION_EVIDENCE:
                for prompt_condition in PROMPT_CONDITIONS:
                    for repetition in range(1, CONFIRMATION_REPETITIONS + 1):
                        number += 1
                        observed = expected_observed_state(schedule, evidence)
                        instructions, prompt = build_decision_input(
                            task,
                            evidence,
                            observed,
                            prompt_condition == "cautious",
                        )
                        rows.append(
                            ConfirmationCell(
                                cell_id="%s-%03d" % (cell_prefix, number),
                                response_group_id=_response_group_id(
                                    task.task_id,
                                    evidence,
                                    observed,
                                    prompt_condition,
                                    repetition,
                                    response_group_prefix,
                                ),
                                task_id=task.task_id,
                                schedule=schedule.value,
                                evidence=evidence.value,
                                prompt_condition=prompt_condition,
                                repetition=repetition,
                                model=model,
                                expected_observed_state=observed.value,
                                instructions=instructions,
                                prompt=prompt,
                                transcript_sha256=_canonical_hash(
                                    {"instructions": instructions, "prompt": prompt}
                                ),
                                maximum_reserved_cost_usd=maximum_decision_cost(
                                    model,
                                    instructions,
                                    prompt,
                                    max_output_tokens,
                                ),
                            )
                        )
    return rows


def write_confirmation_manifest(
    path: Path, rows: Iterable[ConfirmationCell]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")


def load_confirmation_manifest(path: Path) -> List[ConfirmationCell]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(ConfirmationCell(**json.loads(line)))
    return rows


def validate_confirmation_manifest(
    rows: List[ConfirmationCell],
    model: str = CONFIRMATION_MODEL,
    cell_prefix: str = "confirm",
    response_group_prefix: str = "confirm-rg",
    max_output_tokens: int = CONFIRMATION_MAX_OUTPUT_TOKENS,
) -> None:
    if [row.to_dict() for row in rows] != [
        row.to_dict()
        for row in build_confirmation_manifest(
            model, cell_prefix, response_group_prefix, max_output_tokens
        )
    ]:
        raise ValueError("confirmation manifest differs from frozen protocol")


def _group_rows(rows: List[ConfirmationCell]) -> List[List[ConfirmationCell]]:
    grouped: Dict[str, List[ConfirmationCell]] = {}
    order = []
    for row in rows:
        if row.response_group_id not in grouped:
            grouped[row.response_group_id] = []
            order.append(row.response_group_id)
        grouped[row.response_group_id].append(row)
    return [grouped[group_id] for group_id in order]


def load_resume_state(
    output_path: Path,
    rows: List[ConfirmationCell],
    expected_model: str,
    schema_version: str,
) -> tuple:
    """Validate completed groups and recover their calls and spend."""
    with output_path.open(encoding="utf-8") as handle:
        existing = [json.loads(line) for line in handle if line.strip()]
    expected_groups = {
        group[0].response_group_id: group for group in _group_rows(rows)
    }
    actual_groups: Dict[str, List[Dict[str, object]]] = {}
    seen_cells = set()
    for result in existing:
        group_id = str(result.get("response_group_id", ""))
        cell_id = str(result.get("cell_id", ""))
        if group_id not in expected_groups or cell_id in seen_cells:
            raise ValueError("resume output contains an unknown or duplicate coordinate")
        seen_cells.add(cell_id)
        actual_groups.setdefault(group_id, []).append(result)
    for group_id, completed in actual_groups.items():
        expected = expected_groups[group_id]
        if {str(item["cell_id"]) for item in completed} != {
            item.cell_id for item in expected
        }:
            raise ValueError("resume output contains an incomplete response group")
        if any(
            item.get("schema_version") != schema_version
            or item.get("model") != expected_model
            for item in completed
        ):
            raise ValueError("resume output does not match the frozen run")
        first = completed[0]
        if any(
            item["decision"]["response_id"] != first["decision"]["response_id"]
            or item["decision"]["action"] != first["decision"]["action"]
            or item["transcript_sha256"] != first["transcript_sha256"]
            for item in completed
        ):
            raise ValueError("resume output violates response sharing")
    spent = sum(
        float(group[0]["decision"]["cost_usd"])
        for group in actual_groups.values()
    )
    return existing, set(actual_groups), spent, len(actual_groups)


def run_confirmation_preflight(
    rows: List[ConfirmationCell],
    model: str = CONFIRMATION_MODEL,
    maximum_cost_usd: float = CONFIRMATION_MAX_COST_USD,
    cell_prefix: str = "confirm",
    response_group_prefix: str = "confirm-rg",
    schema_version: str = "retrybench-confirmation-preflight-v2",
    max_output_tokens: int = CONFIRMATION_MAX_OUTPUT_TOKENS,
) -> Dict[str, object]:
    """Validate the frozen denominator, response sharing, and cost without API calls."""
    validate_confirmation_manifest(
        rows, model, cell_prefix, response_group_prefix, max_output_tokens
    )
    groups = _group_rows(rows)
    group_integrity = all(
        len({(row.transcript_sha256, row.task_id, row.evidence,
                  row.prompt_condition, row.repetition) for row in group}) == 1
        for group in groups
    )
    weak_groups = [group for group in groups if group[0].evidence == "weak"]
    authoritative_groups = [
        group for group in groups if group[0].evidence == "authoritative"
    ]
    sharing_shape = (
        len(weak_groups) == 40
        and all(len(group) == 3 for group in weak_groups)
        and len(authoritative_groups) == 120
        and all(len(group) == 1 for group in authoritative_groups)
    )
    unique_reserved_cost = round(
        sum(group[0].maximum_reserved_cost_usd for group in groups), 12
    )
    coordinates = {
        (row.task_id, row.schedule, row.evidence, row.prompt_condition, row.repetition)
        for row in rows
    }
    no_hidden_leak = all(
        row.schedule not in row.instructions and row.schedule not in row.prompt
        for row in rows
    )
    gates = {
        "frozen_240_outcomes": len(rows) == 240 and len(coordinates) == 240,
        "exactly_160_fresh_response_groups": len(groups) == 160,
        "shared_response_group_integrity": group_integrity,
        "weak_three_way_sharing_and_authoritative_singletons": sharing_shape,
        "hidden_schedule_absent_from_model_input": no_hidden_leak,
        "pilot_outcomes_excluded": all(row.repetition in range(1, 6) for row in rows),
        "maximum_reserved_cost_within_cap": unique_reserved_cost
        <= maximum_cost_usd,
    }
    return {
        "schema_version": schema_version,
        "api_requests_made": 0,
        "scored_outcomes": len(rows),
        "fresh_model_calls": len(groups),
        "model": model,
        "maximum_output_tokens": max_output_tokens,
        "maximum_reserved_cost_usd": unique_reserved_cost,
        "cost_cap_usd": maximum_cost_usd,
        "gates": gates,
        "all_zero_cost_gates_passed": all(gates.values()),
        "spend_decision": "READY_FOR_SEPARATE_APPROVAL" if all(gates.values()) else "NO_GO",
    }


def run_live_confirmation(
    rows: List[ConfirmationCell],
    policy: OpenAIResponsesPolicy,
    budget: CostBudget,
    database_path: Path,
    output_path: Path,
    late_commit_delay: float = 0.1,
    expected_model: str = CONFIRMATION_MODEL,
    maximum_cost_usd: float = CONFIRMATION_MAX_COST_USD,
    cell_prefix: str = "confirm",
    response_group_prefix: str = "confirm-rg",
    operation_prefix: str = "confirmation",
    schema_version: str = "retrybench-live-confirmation-v2",
    resume: bool = False,
    expected_max_output_tokens: int = CONFIRMATION_MAX_OUTPUT_TOKENS,
) -> List[Dict[str, object]]:
    """Run once per response group, then replay that action on every hidden schedule."""
    validate_confirmation_manifest(
        rows,
        expected_model,
        cell_prefix,
        response_group_prefix,
        expected_max_output_tokens,
    )
    if policy.model != expected_model:
        raise ValueError("confirmation model must be %s" % expected_model)
    if policy.max_output_tokens != expected_max_output_tokens:
        raise ValueError(
            "confirmation max output tokens must be %d"
            % expected_max_output_tokens
        )
    if budget.max_cost_usd > maximum_cost_usd:
        raise ValueError("confirmation budget may not exceed $%.2f" % maximum_cost_usd)
    if database_path.exists():
        raise FileExistsError("confirmation database must not already exist")
    if resume:
        if not output_path.exists():
            raise FileNotFoundError("resume output does not exist")
        results, completed_groups, recovered_spend, recovered_requests = load_resume_state(
            output_path, rows, expected_model, schema_version
        )
        budget.spent_usd = recovered_spend
        budget.requests = recovered_requests
        if budget.spent_usd > budget.max_cost_usd:
            raise ValueError("resume output already exceeds the configured budget")
        output_mode = "a"
    else:
        if output_path.exists():
            raise FileExistsError("confirmation output must not already exist")
        results = []
        completed_groups = set()
        output_mode = "x"

    task_by_id = {task.task_id: task for task in TASKS}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open(output_mode, encoding="utf-8") as output:
        with RetryBenchHTTPService(
            database_path,
            late_commit_delay=late_commit_delay,
            manual_settlement=True,
        ) as service:
            client = HTTPExperimentClient(service.base_url)
            for group in _group_rows(rows):
                if group[0].response_group_id in completed_groups:
                    continue
                prepared = []
                for row in group:
                    task = task_by_id[row.task_id]
                    schedule = Schedule(row.schedule)
                    evidence = EvidenceContract(row.evidence)
                    operation_id = "%s:%s" % (operation_prefix, row.cell_id)
                    status, timeout_body = client.start(operation_id, task, schedule)
                    observed = client.status(operation_id, evidence)
                    instructions, prompt = build_decision_input(
                        task, evidence, observed, row.prompt_condition == "cautious"
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
                    first[1],
                    first[3],
                    first[4],
                    first[0].prompt_condition == "cautious",
                    budget,
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
                        "task_id": row.task_id,
                        "schedule": row.schedule,
                        "evidence": row.evidence,
                        "prompt_condition": row.prompt_condition,
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
