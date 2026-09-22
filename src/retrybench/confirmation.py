"""Frozen targeted confirmation with shared model responses across hidden schedules."""

from __future__ import annotations

import hashlib
import json
import time
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
from .scoring import score_exact_state


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
) -> str:
    return "confirm-rg:%s:%s:%s:%s:%02d" % (
        task_id,
        evidence.value,
        observed.value,
        prompt_condition,
        repetition,
    )


def build_confirmation_manifest() -> List[ConfirmationCell]:
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
                                cell_id="confirm-%03d" % number,
                                response_group_id=_response_group_id(
                                    task.task_id,
                                    evidence,
                                    observed,
                                    prompt_condition,
                                    repetition,
                                ),
                                task_id=task.task_id,
                                schedule=schedule.value,
                                evidence=evidence.value,
                                prompt_condition=prompt_condition,
                                repetition=repetition,
                                model=CONFIRMATION_MODEL,
                                expected_observed_state=observed.value,
                                instructions=instructions,
                                prompt=prompt,
                                transcript_sha256=_canonical_hash(
                                    {"instructions": instructions, "prompt": prompt}
                                ),
                                maximum_reserved_cost_usd=maximum_decision_cost(
                                    CONFIRMATION_MODEL,
                                    instructions,
                                    prompt,
                                    CONFIRMATION_MAX_OUTPUT_TOKENS,
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


def validate_confirmation_manifest(rows: List[ConfirmationCell]) -> None:
    if [row.to_dict() for row in rows] != [
        row.to_dict() for row in build_confirmation_manifest()
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


def run_confirmation_preflight(rows: List[ConfirmationCell]) -> Dict[str, object]:
    """Validate the frozen denominator, response sharing, and cost without API calls."""
    validate_confirmation_manifest(rows)
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
        <= CONFIRMATION_MAX_COST_USD,
    }
    return {
        "schema_version": "retrybench-confirmation-preflight-v2",
        "api_requests_made": 0,
        "scored_outcomes": len(rows),
        "fresh_model_calls": len(groups),
        "model": CONFIRMATION_MODEL,
        "maximum_output_tokens": CONFIRMATION_MAX_OUTPUT_TOKENS,
        "maximum_reserved_cost_usd": unique_reserved_cost,
        "cost_cap_usd": CONFIRMATION_MAX_COST_USD,
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
) -> List[Dict[str, object]]:
    """Run once per response group, then replay that action on every hidden schedule."""
    validate_confirmation_manifest(rows)
    if policy.model != CONFIRMATION_MODEL:
        raise ValueError("confirmation model must be %s" % CONFIRMATION_MODEL)
    if budget.max_cost_usd > CONFIRMATION_MAX_COST_USD:
        raise ValueError("confirmation budget may not exceed $%.2f" % CONFIRMATION_MAX_COST_USD)
    if database_path.exists() or output_path.exists():
        raise FileExistsError("confirmation outputs must not already exist")

    task_by_id = {task.task_id: task for task in TASKS}
    results = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        with RetryBenchHTTPService(
            database_path, late_commit_delay=late_commit_delay
        ) as service:
            client = HTTPExperimentClient(service.base_url)
            for group in _group_rows(rows):
                prepared = []
                for row in group:
                    task = task_by_id[row.task_id]
                    schedule = Schedule(row.schedule)
                    evidence = EvidenceContract(row.evidence)
                    operation_id = "confirmation:%s" % row.cell_id
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
                        time.sleep(late_commit_delay + 0.01)
                    unresolved = decision.action in {Action.WAIT, Action.UNRESOLVED}
                    effects = client.effects(operation_id)
                    score = score_exact_state(task, operation_id, effects, unresolved)
                    retry_permitted = (
                        schedule == Schedule.FAIL_BEFORE_EXECUTION
                        and evidence == EvidenceContract.AUTHORITATIVE
                        and observed == ObservedState.NOT_EXECUTED
                    )
                    result = {
                        "schema_version": "retrybench-live-confirmation-v2",
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
