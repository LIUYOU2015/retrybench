"""Offline audit of LangChain runnable retries around ambiguous side effects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import version
from typing import Dict, List

from .model import EvidenceContract, Schedule, TASKS, TaskSpec
from .scoring import score_exact_state
from .service import (
    AmbiguousTimeout,
    DeterministicService,
    seed_original_idempotency_record,
)


@dataclass(frozen=True)
class LangChainAuditResult:
    task_id: str
    schedule: str
    policy: str
    framework: str
    framework_version: str
    runnable_completed: bool
    attempts: int
    retries: int
    stable_idempotency: bool
    false_retry_permission: bool
    effect_count: int
    exact_state_success: bool
    duplicate_effect: bool
    omission: bool
    unresolved: bool
    wrong_operation_identity: bool
    wrong_task: bool
    wrong_tool: bool
    wrong_target: bool
    wrong_payload: bool

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _runnable_lambda():
    try:
        from langchain_core.runnables import RunnableLambda
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "LangChain audit requires: python -m pip install 'retrybench[langchain]'"
        ) from exc
    return RunnableLambda


def run_langchain_episode(
    task: TaskSpec, schedule: Schedule, policy: str
) -> LangChainAuditResult:
    """Execute an actual LangChain Runnable with a bounded retry wrapper."""
    if policy not in {
        "no_retry",
        "langchain_exception_retry",
        "stable_idempotency_retry",
    }:
        raise ValueError("unknown LangChain audit policy: %s" % policy)

    RunnableLambda = _runnable_lambda()
    service = DeterministicService(task, schedule, EvidenceContract.NONE)
    operation_id = "langchain:%s:%s:%s" % (task.task_id, schedule.value, policy)
    attempts = 0
    completed = False

    def side_effect_node(_: object) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            try:
                service.start(operation_id)
            except AmbiguousTimeout:
                if policy == "stable_idempotency_retry":
                    seed_original_idempotency_record(service, operation_id)
                raise
            raise AssertionError("RetryBench schedules always surface ambiguity")

        if policy == "stable_idempotency_retry":
            service.retry(operation_id, stable_idempotency=True)
            return "recovered_by_stable_replay"

        # The application preserves logical operation identity, but without a
        # provider deduplication guarantee that identity does not prevent a
        # second externally visible effect.
        service.retry(operation_id, stable_idempotency=False)
        return "recovered_by_exception_retry"

    runnable = RunnableLambda(side_effect_node)
    if policy != "no_retry":
        # Keep LangChain's default Exception predicate but cap at two attempts
        # and disable waiting so the audit remains deterministic and fast.
        runnable = runnable.with_retry(
            stop_after_attempt=2,
            wait_exponential_jitter=False,
        )
    try:
        runnable.invoke({"status": "pending"})
        completed = True
    except AmbiguousTimeout:
        completed = False

    service.settle()
    stable = policy == "stable_idempotency_retry"
    retries = max(0, attempts - 1)
    score = score_exact_state(
        task, operation_id, service.effects, unresolved=not completed
    )
    return LangChainAuditResult(
        task_id=task.task_id,
        schedule=schedule.value,
        policy=policy,
        framework="langchain-core",
        framework_version=version("langchain-core"),
        runnable_completed=completed,
        attempts=attempts,
        retries=retries,
        stable_idempotency=stable,
        false_retry_permission=retries > 0 and not stable,
        effect_count=len(service.effects),
        **score.to_dict(),
    )


def run_langchain_audit() -> List[LangChainAuditResult]:
    return [
        run_langchain_episode(task, schedule, policy)
        for task in TASKS
        for schedule in Schedule
        for policy in (
            "no_retry",
            "langchain_exception_retry",
            "stable_idempotency_retry",
        )
    ]


def summarize_langchain_audit(
    rows: List[LangChainAuditResult],
) -> Dict[str, object]:
    by_policy = {}
    for policy in sorted({row.policy for row in rows}):
        selected = [row for row in rows if row.policy == policy]
        by_policy[policy] = {
            "episodes": len(selected),
            "runnable_completed": sum(row.runnable_completed for row in selected),
            "retries": sum(row.retries for row in selected),
            "false_retry_permissions": sum(
                row.false_retry_permission for row in selected
            ),
            "duplicates": sum(row.duplicate_effect for row in selected),
            "omissions": sum(row.omission for row in selected),
            "unresolved": sum(row.unresolved for row in selected),
            "exact_state_success": sum(
                row.exact_state_success for row in selected
            ),
        }
    return {
        "schema_version": "retrybench-langchain-audit-v1",
        "framework": "langchain-core",
        "framework_version": rows[0].framework_version if rows else None,
        "episodes": len(rows),
        "api_calls": 0,
        "api_cost_usd": 0.0,
        "configuration": {
            "retry_exception_types": ["Exception"],
            "max_attempts": 2,
            "wait_exponential_jitter": False,
        },
        "by_policy": by_policy,
        "interpretation": (
            "LangChain's retry wrapper behaves as configured; the audit tests "
            "whether exception eligibility establishes that replaying an external "
            "side effect is admissible."
        ),
    }
