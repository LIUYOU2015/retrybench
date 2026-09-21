"""Small, gated live-model smoke test. Smoke results are not paper results."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .model import Action, EvidenceContract, ObservedState, Schedule, TASKS, TaskSpec
from .openai_adapter import CostBudget, OpenAIResponsesPolicy
from .service import AmbiguousTimeout, DeterministicService


SmokeCase = Tuple[TaskSpec, Schedule, EvidenceContract, bool]


def smoke_cases() -> List[SmokeCase]:
    return [
        (TASKS[0], Schedule.FAIL_BEFORE_EXECUTION, EvidenceContract.NONE, False),
        (TASKS[0], Schedule.COMMIT_THEN_DROP_RESPONSE, EvidenceContract.NONE, False),
        (TASKS[1], Schedule.IN_FLIGHT_LATE_COMMIT, EvidenceContract.WEAK, False),
        (TASKS[1], Schedule.STALE_NEGATIVE_AFTER_COMMIT, EvidenceContract.WEAK, False),
        (TASKS[2], Schedule.FAIL_BEFORE_EXECUTION, EvidenceContract.AUTHORITATIVE, False),
        (TASKS[2], Schedule.COMMIT_THEN_DROP_RESPONSE, EvidenceContract.AUTHORITATIVE, False),
        (TASKS[3], Schedule.IN_FLIGHT_LATE_COMMIT, EvidenceContract.AUTHORITATIVE, False),
        (TASKS[3], Schedule.STALE_NEGATIVE_AFTER_COMMIT, EvidenceContract.AUTHORITATIVE, False),
        (TASKS[0], Schedule.IN_FLIGHT_LATE_COMMIT, EvidenceContract.WEAK, True),
        (TASKS[0], Schedule.STALE_NEGATIVE_AFTER_COMMIT, EvidenceContract.WEAK, True),
    ]


def run_live_smoke(
    policy: OpenAIResponsesPolicy,
    budget: CostBudget,
    cases: Iterable[SmokeCase],
) -> List[Dict[str, object]]:
    rows = []
    for index, (task, schedule, evidence, cautious) in enumerate(cases):
        service = DeterministicService(task=task, schedule=schedule, evidence=evidence)
        operation_id = "live:%s:%d" % (task.task_id, index)
        try:
            service.start(operation_id)
        except AmbiguousTimeout:
            pass
        observed = ObservedState.UNKNOWN if evidence == EvidenceContract.NONE else service.status()
        decision = policy.decide(task, evidence, observed, cautious, budget)
        unresolved = decision.action in {Action.WAIT, Action.UNRESOLVED}
        if decision.action == Action.RETRY:
            service.retry(operation_id, stable_idempotency=False)
        elif decision.action == Action.WAIT:
            service.advance()
        service.settle()
        effect_count = len(service.effects)
        rows.append(
            {
                "schema_version": "retrybench-live-smoke-v1",
                "smoke_only": True,
                "case_index": index,
                "task_id": task.task_id,
                "tool": task.tool,
                "schedule": schedule.value,
                "evidence": evidence.value,
                "observed_state": observed.value,
                "prompt_condition": "cautious" if cautious else "neutral",
                "decision": decision.to_dict(),
                "effect_count": effect_count,
                "duplicate_effect": effect_count > 1,
                "omission": effect_count == 0,
                "unresolved": unresolved,
                "exact_state_success": effect_count == 1 and not unresolved,
                "cumulative_cost_usd": budget.spent_usd,
            }
        )
    return rows

