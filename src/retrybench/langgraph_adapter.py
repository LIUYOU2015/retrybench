"""Offline audit of LangGraph node retries around ambiguous external effects."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import version
from typing import Dict, List, TypedDict

from .model import EvidenceContract, Schedule, TASKS, TaskSpec
from .scoring import score_exact_state
from .service import (
    AmbiguousTimeout,
    DeterministicService,
    seed_original_idempotency_record,
)


class GraphState(TypedDict, total=False):
    status: str


@dataclass(frozen=True)
class LangGraphAuditResult:
    task_id: str
    schedule: str
    policy: str
    framework: str
    framework_version: str
    graph_completed: bool
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


def _langgraph_components():
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import RetryPolicy
    except ImportError as exc:  # pragma: no cover - exercised without optional extra
        raise RuntimeError(
            "LangGraph audit requires: python -m pip install 'retrybench[langgraph]'"
        ) from exc
    return END, START, StateGraph, RetryPolicy


def run_langgraph_episode(
    task: TaskSpec, schedule: Schedule, policy: str
) -> LangGraphAuditResult:
    """Execute an actual LangGraph node with a two-attempt retry boundary."""
    if policy not in {
        "no_retry",
        "langgraph_default_retry_policy",
        "stable_idempotency_retry",
    }:
        raise ValueError("unknown LangGraph audit policy: %s" % policy)

    END, START, StateGraph, RetryPolicy = _langgraph_components()
    service = DeterministicService(task, schedule, EvidenceContract.NONE)
    operation_id = "langgraph:%s:%s:%s" % (task.task_id, schedule.value, policy)
    attempts = 0
    graph_completed = False

    def side_effect_node(state: GraphState) -> GraphState:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            try:
                service.start(operation_id)
            except AmbiguousTimeout as exc:
                if policy == "stable_idempotency_retry":
                    seed_original_idempotency_record(service, operation_id)
                # A response-lost connection error is in LangGraph 0.6.11's
                # default retry predicate even though execution state is unknown.
                raise ConnectionError("connection lost after dispatch") from exc
            raise AssertionError("RetryBench schedules always surface ambiguity")

        if policy == "stable_idempotency_retry":
            service.retry(operation_id, stable_idempotency=True)
            return {"status": "recovered_by_stable_replay"}

        service.retry(operation_id, stable_idempotency=False)
        raise ConnectionError("retry response also lost")

    builder = StateGraph(GraphState)
    if policy == "no_retry":
        builder.add_node("side_effect", side_effect_node)
    else:
        builder.add_node(
            "side_effect",
            side_effect_node,
            retry_policy=RetryPolicy(
                initial_interval=0.0,
                backoff_factor=1.0,
                max_interval=0.0,
                max_attempts=2,
                jitter=False,
            ),
        )
    builder.add_edge(START, "side_effect")
    builder.add_edge("side_effect", END)
    graph = builder.compile()
    try:
        graph.invoke({"status": "pending"})
        graph_completed = True
    except ConnectionError:
        graph_completed = False

    service.settle()
    stable = policy == "stable_idempotency_retry"
    retries = max(0, attempts - 1)
    score = score_exact_state(
        task, operation_id, service.effects, unresolved=not graph_completed
    )
    return LangGraphAuditResult(
        task_id=task.task_id,
        schedule=schedule.value,
        policy=policy,
        framework="langgraph",
        framework_version=version("langgraph"),
        graph_completed=graph_completed,
        attempts=attempts,
        retries=retries,
        stable_idempotency=stable,
        false_retry_permission=retries > 0 and not stable,
        effect_count=len(service.effects),
        **score.to_dict(),
    )


def run_langgraph_audit() -> List[LangGraphAuditResult]:
    return [
        run_langgraph_episode(task, schedule, policy)
        for task in TASKS
        for schedule in Schedule
        for policy in (
            "no_retry",
            "langgraph_default_retry_policy",
            "stable_idempotency_retry",
        )
    ]


def summarize_langgraph_audit(
    rows: List[LangGraphAuditResult],
) -> Dict[str, object]:
    by_policy = {}
    for policy in sorted({row.policy for row in rows}):
        selected = [row for row in rows if row.policy == policy]
        by_policy[policy] = {
            "episodes": len(selected),
            "graph_completed": sum(row.graph_completed for row in selected),
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
        "schema_version": "retrybench-langgraph-audit-v1",
        "framework": "langgraph",
        "framework_version": rows[0].framework_version if rows else None,
        "episodes": len(rows),
        "by_policy": by_policy,
        "interpretation": (
            "LangGraph's retry mechanism behaves as configured; the audit tests "
            "whether exception-based retry is admissible for an external side effect."
        ),
    }
