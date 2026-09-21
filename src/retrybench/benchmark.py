"""Episode execution, exact-state scoring, and matrix generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Iterator, List

from .model import EvidenceContract, PolicyName, Schedule, TASKS, TaskSpec
from .policies import apply_policy
from .scoring import score_exact_state
from .service import AmbiguousTimeout, DeterministicService, seed_original_idempotency_record


@dataclass(frozen=True)
class EpisodeResult:
    task_id: str
    tool: str
    schedule: str
    evidence: str
    policy: str
    initial_observation: str
    policy_observations: List[str]
    final_action: str
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
    retries: int
    probes: int
    recovery_steps: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def run_episode(
    task: TaskSpec,
    schedule: Schedule,
    evidence: EvidenceContract,
    policy: PolicyName,
) -> EpisodeResult:
    operation_id = "op:%s" % task.task_id
    service = DeterministicService(task=task, schedule=schedule, evidence=evidence)
    try:
        service.start(operation_id)
    except AmbiguousTimeout:
        initial_observation = "timeout"
    else:  # pragma: no cover - service contract always times out
        raise AssertionError("benchmark schedule did not produce timeout")

    if policy == PolicyName.STABLE_IDEMPOTENCY:
        seed_original_idempotency_record(service, operation_id)

    outcome = apply_policy(policy, service, operation_id)
    service.settle()
    unresolved = outcome.final_action.value == "unresolved"
    score = score_exact_state(task, operation_id, service.effects, unresolved)
    return EpisodeResult(
        task_id=task.task_id,
        tool=task.tool,
        schedule=schedule.value,
        evidence=evidence.value,
        policy=policy.value,
        initial_observation=initial_observation,
        policy_observations=[item.value for item in outcome.observations],
        final_action=outcome.final_action.value,
        effect_count=len(service.effects),
        **score.to_dict(),
        retries=outcome.retries,
        probes=service.probes,
        recovery_steps=service.steps,
    )


def run_matrix(
    tasks: Iterable[TaskSpec] = TASKS,
    schedules: Iterable[Schedule] = tuple(Schedule),
    evidence_contracts: Iterable[EvidenceContract] = tuple(EvidenceContract),
    policies: Iterable[PolicyName] = tuple(PolicyName),
) -> Iterator[EpisodeResult]:
    for task in tasks:
        for schedule in schedules:
            for evidence in evidence_contracts:
                for policy in policies:
                    yield run_episode(task, schedule, evidence, policy)
