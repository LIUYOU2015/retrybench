"""Frozen pilot manifest and zero-cost HTTP preflight audit."""

from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import quote

from .http_service import RetryBenchHTTPService
from .model import (
    Action,
    EffectRecord,
    EvidenceContract,
    ObservedState,
    Schedule,
    TASKS,
    TaskSpec,
)
from .openai_adapter import (
    CostBudget,
    OpenAIResponsesPolicy,
    build_decision_input,
    maximum_decision_cost,
)
from .scoring import retry_is_permitted, score_exact_state


PILOT_MODEL = "gpt-5.4-mini-2026-03-17"
PILOT_MAX_OUTPUT_TOKENS = 256
PILOT_MAX_COST_USD = 2.0
PROMPT_CONDITIONS = ("neutral", "cautious")


@dataclass(frozen=True)
class PilotCell:
    cell_id: str
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


class HTTPExperimentClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(
        self, path: str, method: str = "GET", body: Dict[str, object] = None
    ) -> Tuple[int, Dict[str, object]]:
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        with response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def start(
        self, operation_id: str, task: TaskSpec, schedule: Schedule
    ) -> Tuple[int, Dict[str, object]]:
        return self._request(
            "/operations",
            "POST",
            {
                "operation_id": operation_id,
                "schedule": schedule.value,
                "task": {
                    "task_id": task.task_id,
                    "tool": task.tool,
                    "target": task.target,
                    "payload": task.payload,
                },
            },
        )

    def status(
        self, operation_id: str, evidence: EvidenceContract
    ) -> ObservedState:
        path = "/operations/%s/status?evidence=%s" % (
            quote(operation_id, safe=""),
            evidence.value,
        )
        status, body = self._request(path)
        if status != 200:
            raise RuntimeError("status probe failed: %s %s" % (status, body))
        return ObservedState(str(body["observed_state"]))

    def retry(self, operation_id: str, stable_idempotency: bool) -> bool:
        path = "/operations/%s/retry" % quote(operation_id, safe="")
        status, body = self._request(
            path, "POST", {"stable_idempotency": stable_idempotency}
        )
        if status not in {200, 201}:
            raise RuntimeError("retry failed: %s %s" % (status, body))
        return bool(body["effect_created"])

    def advance(self, operation_id: str) -> bool:
        path = "/operations/%s/advance" % quote(operation_id, safe="")
        status, body = self._request(path, "POST", {})
        if status != 200:
            raise RuntimeError("logical advance failed: %s %s" % (status, body))
        return bool(body["effect_created"])

    def effects(self, operation_id: str) -> List[EffectRecord]:
        status, body = self._request("/ledger")
        if status != 200:
            raise RuntimeError("ledger failed: %s %s" % (status, body))
        return [
            EffectRecord(
                operation_id=str(row["operation_id"]),
                task_id=str(row["task_id"]),
                tool=str(row["tool"]),
                target=str(row["target"]),
                payload=dict(row["payload"]),
            )
            for row in body["effects"]
            if row["operation_id"] == operation_id
        ]


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def expected_observed_state(
    schedule: Schedule, evidence: EvidenceContract
) -> ObservedState:
    if evidence == EvidenceContract.NONE:
        return ObservedState.UNKNOWN
    if evidence == EvidenceContract.WEAK:
        if schedule == Schedule.COMMIT_THEN_DROP_RESPONSE:
            return ObservedState.COMMITTED
        return ObservedState.NOT_FOUND
    if schedule == Schedule.FAIL_BEFORE_EXECUTION:
        return ObservedState.NOT_EXECUTED
    if schedule == Schedule.IN_FLIGHT_LATE_COMMIT:
        return ObservedState.IN_FLIGHT
    return ObservedState.COMMITTED


def build_pilot_manifest() -> List[PilotCell]:
    rows = []
    cell_number = 0
    for task in TASKS:
        for schedule in Schedule:
            for evidence in EvidenceContract:
                for prompt_condition in PROMPT_CONDITIONS:
                    cell_number += 1
                    observed = expected_observed_state(schedule, evidence)
                    instructions, prompt = build_decision_input(
                        task,
                        evidence,
                        observed,
                        prompt_condition == "cautious",
                    )
                    rows.append(
                        PilotCell(
                            cell_id="pilot-%03d" % cell_number,
                            task_id=task.task_id,
                            schedule=schedule.value,
                            evidence=evidence.value,
                            prompt_condition=prompt_condition,
                            repetition=1,
                            model=PILOT_MODEL,
                            expected_observed_state=observed.value,
                            instructions=instructions,
                            prompt=prompt,
                            transcript_sha256=_canonical_hash(
                                {"instructions": instructions, "prompt": prompt}
                            ),
                            maximum_reserved_cost_usd=maximum_decision_cost(
                                PILOT_MODEL,
                                instructions,
                                prompt,
                                PILOT_MAX_OUTPUT_TOKENS,
                            ),
                        )
                    )
    return rows


def write_manifest(path: Path, rows: Iterable[PilotCell]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")


def load_manifest(path: Path) -> List[PilotCell]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(PilotCell(**json.loads(line)))
    return rows


def validate_frozen_manifest(rows: List[PilotCell]) -> None:
    expected = [row.to_dict() for row in build_pilot_manifest()]
    actual = [row.to_dict() for row in rows]
    if actual != expected:
        raise ValueError("pilot manifest differs from frozen generated protocol")


def deterministic_recovery(
    client: HTTPExperimentClient,
    operation_id: str,
    evidence: EvidenceContract,
    first_observation: ObservedState,
) -> Tuple[Action, int, int]:
    """Fail closed; retry only on authoritative terminal non-execution."""
    probes = 1
    if first_observation == ObservedState.COMMITTED:
        return Action.STOP, probes, 0
    if (
        evidence == EvidenceContract.AUTHORITATIVE
        and first_observation == ObservedState.NOT_EXECUTED
    ):
        client.retry(operation_id, stable_idempotency=False)
        return Action.RETRY, probes, 1

    client.advance(operation_id)
    second = client.status(operation_id, evidence)
    probes += 1
    if second == ObservedState.COMMITTED:
        return Action.STOP, probes, 0
    if (
        evidence == EvidenceContract.AUTHORITATIVE
        and second == ObservedState.NOT_EXECUTED
    ):
        client.retry(operation_id, stable_idempotency=False)
        return Action.RETRY, probes, 1
    return Action.UNRESOLVED, probes, 0


def _manifest_factor_gate(rows: List[PilotCell]) -> bool:
    coordinates = {
        (row.task_id, row.schedule, row.evidence, row.prompt_condition, row.repetition)
        for row in rows
    }
    hidden_leak = any(row.schedule in row.instructions or row.schedule in row.prompt for row in rows)
    return len(rows) == 96 and len(coordinates) == 96 and not hidden_leak


def _matched_hash_gate(rows: List[PilotCell]) -> Tuple[bool, List[Dict[str, object]]]:
    expected_groups = (
        (EvidenceContract.NONE, tuple(Schedule)),
        (
            EvidenceContract.WEAK,
            (
                Schedule.FAIL_BEFORE_EXECUTION,
                Schedule.IN_FLIGHT_LATE_COMMIT,
                Schedule.STALE_NEGATIVE_AFTER_COMMIT,
            ),
        ),
        (
            EvidenceContract.AUTHORITATIVE,
            (
                Schedule.COMMIT_THEN_DROP_RESPONSE,
                Schedule.STALE_NEGATIVE_AFTER_COMMIT,
            ),
        ),
    )
    evidence_rows = []
    passed = True
    for task in TASKS:
        for prompt_condition in PROMPT_CONDITIONS:
            for evidence, schedules in expected_groups:
                selected = [
                    row
                    for row in rows
                    if row.task_id == task.task_id
                    and row.prompt_condition == prompt_condition
                    and row.evidence == evidence.value
                    and row.schedule in {item.value for item in schedules}
                ]
                hashes = sorted({row.transcript_sha256 for row in selected})
                group_passed = len(selected) == len(schedules) and len(hashes) == 1
                passed = passed and group_passed
                evidence_rows.append(
                    {
                        "task_id": task.task_id,
                        "prompt_condition": prompt_condition,
                        "evidence": evidence.value,
                        "schedules": [item.value for item in schedules],
                        "transcript_sha256": hashes,
                        "passed": group_passed,
                    }
                )
    return passed, evidence_rows


def _scorer_fault_gate() -> Dict[str, bool]:
    task = TASKS[0]
    operation_id = "scorer-control"
    intended = EffectRecord(
        operation_id, task.task_id, task.tool, task.target, dict(task.payload)
    )
    wrong_target = EffectRecord(
        operation_id, task.task_id, task.tool, "wrong/target", dict(task.payload)
    )
    wrong_payload = EffectRecord(
        operation_id, task.task_id, task.tool, task.target, {"wrong": True}
    )
    return {
        "wrong_target": score_exact_state(task, operation_id, [wrong_target], False).wrong_target,
        "wrong_payload": score_exact_state(task, operation_id, [wrong_payload], False).wrong_payload,
        "duplicate": score_exact_state(task, operation_id, [intended, intended], False).duplicate_effect,
        "omission": score_exact_state(task, operation_id, [], False).omission,
    }


def run_zero_cost_preflight(rows: List[PilotCell]) -> Dict[str, object]:
    matched_passed, matched_evidence = _matched_hash_gate(rows)
    actual_observations_match = True
    initial_timeout_responses = set()
    deterministic_rows = []
    stable_control_passed = True
    late_commit_delay = 0.02

    task_by_id = {task.task_id: task for task in TASKS}
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "preflight.sqlite3"
        with RetryBenchHTTPService(
            database,
            late_commit_delay=late_commit_delay,
            manual_settlement=True,
        ) as service:
            client = HTTPExperimentClient(service.base_url)
            for row in rows:
                task = task_by_id[row.task_id]
                schedule = Schedule(row.schedule)
                evidence = EvidenceContract(row.evidence)
                operation_id = "preflight:%s" % row.cell_id
                status, timeout_body = client.start(operation_id, task, schedule)
                initial_timeout_responses.add(
                    _canonical_hash({"status": status, "body": timeout_body})
                )
                observed = client.status(operation_id, evidence)
                instructions, prompt = build_decision_input(
                    task,
                    evidence,
                    observed,
                    row.prompt_condition == "cautious",
                )
                actual_hash = _canonical_hash(
                    {"instructions": instructions, "prompt": prompt}
                )
                actual_observations_match = actual_observations_match and (
                    status == 504
                    and timeout_body == {"error": "tool call timed out"}
                    and observed.value == row.expected_observed_state
                    and actual_hash == row.transcript_sha256
                )
                action, probes, retries = deterministic_recovery(
                    client,
                    operation_id,
                    evidence,
                    observed,
                )
                score = score_exact_state(
                    task,
                    operation_id,
                    client.effects(operation_id),
                    action == Action.UNRESOLVED,
                )
                unsafe_retry = retries > 0 and not (
                    schedule == Schedule.FAIL_BEFORE_EXECUTION
                    and evidence == EvidenceContract.AUTHORITATIVE
                    and observed == ObservedState.NOT_EXECUTED
                )
                deterministic_rows.append(
                    {
                        "cell_id": row.cell_id,
                        "action": action.value,
                        "probes": probes,
                        "retries": retries,
                        "unsafe_retry": unsafe_retry,
                        **score.to_dict(),
                    }
                )

            for task in TASKS:
                for schedule in Schedule:
                    operation_id = "stable:%s:%s" % (task.task_id, schedule.value)
                    client.start(operation_id, task, schedule)
                    client.retry(operation_id, stable_idempotency=True)
                    client.advance(operation_id)
                    score = score_exact_state(
                        task, operation_id, client.effects(operation_id), False
                    )
                    stable_control_passed = (
                        stable_control_passed and score.exact_state_success
                    )

    authoritative_rows = [
        result
        for result, cell in zip(deterministic_rows, rows)
        if cell.evidence == EvidenceContract.AUTHORITATIVE.value
    ]
    scorer_faults = _scorer_fault_gate()
    maximum_reserved_cost = round(
        sum(row.maximum_reserved_cost_usd for row in rows), 12
    )
    gates = {
        "frozen_denominator_and_no_hidden_leak": _manifest_factor_gate(rows),
        "matched_transcript_hashes": matched_passed,
        "actual_http_observations_match_manifest": actual_observations_match,
        "identical_initial_timeout_response": len(initial_timeout_responses) == 1,
        "deterministic_controller_has_zero_unsafe_retries": not any(
            row["unsafe_retry"] for row in deterministic_rows
        ),
        "authoritative_control_exact_state": bool(authoritative_rows)
        and all(row["exact_state_success"] for row in authoritative_rows),
        "stable_idempotency_control_exact_state": stable_control_passed,
        "scorer_injected_faults_detected": all(scorer_faults.values()),
        "maximum_reserved_cost_within_cap": maximum_reserved_cost
        <= PILOT_MAX_COST_USD,
    }
    passed = all(gates.values())
    return {
        "schema_version": "retrybench-preflight-v1",
        "api_requests_made": 0,
        "pilot_cells": len(rows),
        "model": PILOT_MODEL,
        "maximum_output_tokens": PILOT_MAX_OUTPUT_TOKENS,
        "maximum_reserved_cost_usd": maximum_reserved_cost,
        "pilot_cost_cap_usd": PILOT_MAX_COST_USD,
        "gates": gates,
        "all_zero_cost_gates_passed": passed,
        "pilot_conclusion_sensitivity": "pending_paid_pilot",
        "spend_decision": "GO" if passed else "NO_GO",
        "matched_hash_evidence": matched_evidence,
        "deterministic_control_summary": {
            "episodes": len(deterministic_rows),
            "exact_state_success": sum(
                row["exact_state_success"] for row in deterministic_rows
            ),
            "unresolved": sum(row["unresolved"] for row in deterministic_rows),
            "unsafe_retries": sum(row["unsafe_retry"] for row in deterministic_rows),
        },
        "scorer_fault_controls": scorer_faults,
    }


def run_live_pilot(
    rows: List[PilotCell],
    policy: OpenAIResponsesPolicy,
    budget: CostBudget,
    database_path: Path,
    output_path: Path,
    late_commit_delay: float = 0.02,
) -> List[Dict[str, object]]:
    """Execute frozen cells through HTTP, writing each paid result immediately."""
    validate_frozen_manifest(rows)
    if policy.model != PILOT_MODEL:
        raise ValueError("pilot model must be the frozen snapshot %s" % PILOT_MODEL)
    if policy.max_output_tokens != PILOT_MAX_OUTPUT_TOKENS:
        raise ValueError(
            "pilot max output tokens must be %d" % PILOT_MAX_OUTPUT_TOKENS
        )
    if budget.max_cost_usd > PILOT_MAX_COST_USD:
        raise ValueError("pilot budget may not exceed $%.2f" % PILOT_MAX_COST_USD)
    if database_path.exists():
        raise FileExistsError("pilot database already exists: %s" % database_path)
    if output_path.exists():
        raise FileExistsError("pilot output already exists: %s" % output_path)

    task_by_id = {task.task_id: task for task in TASKS}
    results = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        with RetryBenchHTTPService(
            database_path,
            late_commit_delay=late_commit_delay,
            manual_settlement=True,
        ) as service:
            client = HTTPExperimentClient(service.base_url)
            for row in rows:
                task = task_by_id[row.task_id]
                schedule = Schedule(row.schedule)
                evidence = EvidenceContract(row.evidence)
                operation_id = "pilot:%s" % row.cell_id
                status, timeout_body = client.start(operation_id, task, schedule)
                observed = client.status(operation_id, evidence)
                instructions, prompt = build_decision_input(
                    task,
                    evidence,
                    observed,
                    row.prompt_condition == "cautious",
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
                    raise RuntimeError(
                        "live observation diverged from manifest before %s" % row.cell_id
                    )

                decision = policy.decide(
                    task,
                    evidence,
                    observed,
                    row.prompt_condition == "cautious",
                    budget,
                )
                if decision.action == Action.RETRY:
                    client.retry(operation_id, stable_idempotency=False)
                if schedule == Schedule.IN_FLIGHT_LATE_COMMIT:
                    client.advance(operation_id)

                unresolved = decision.action in {Action.WAIT, Action.UNRESOLVED}
                effects = client.effects(operation_id)
                score = score_exact_state(
                    task,
                    operation_id,
                    effects,
                    unresolved,
                )
                retry_permitted = retry_is_permitted(schedule, evidence, observed)
                false_retry_permission = (
                    decision.action == Action.RETRY and not retry_permitted
                )
                result = {
                    "schema_version": "retrybench-live-pilot-v1",
                    "cell_id": row.cell_id,
                    "task_id": row.task_id,
                    "schedule": row.schedule,
                    "evidence": row.evidence,
                    "prompt_condition": row.prompt_condition,
                    "model": decision.model,
                    "operation_id": operation_id,
                    "initial_http_status": status,
                    "initial_http_body": timeout_body,
                    "observed_state": observed.value,
                    "transcript_sha256": actual_hash,
                    "decision": decision.to_dict(),
                    "retry_permitted": retry_permitted,
                    "false_retry_permission": false_retry_permission,
                    "effect_count": len(effects),
                    **score.to_dict(),
                    "cumulative_cost_usd": budget.spent_usd,
                }
                output.write(json.dumps(result, sort_keys=True) + "\n")
                output.flush()
                results.append(result)
    return results


def summarize_live_pilot(
    results: List[Dict[str, object]], budget: CostBudget
) -> Dict[str, object]:
    return {
        "schema_version": "retrybench-live-pilot-summary-v1",
        "episodes": len(results),
        "api_requests": budget.requests,
        "actual_cost_usd": budget.spent_usd,
        "false_retry_permissions": sum(
            bool(row["false_retry_permission"]) for row in results
        ),
        "exact_state_success": sum(bool(row["exact_state_success"]) for row in results),
        "duplicates": sum(bool(row["duplicate_effect"]) for row in results),
        "omissions": sum(bool(row["omission"]) for row in results),
        "unresolved": sum(bool(row["unresolved"]) for row in results),
    }


def write_report(path: Path, report: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
