"""Reference recovery policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .model import Action, ObservedState, PolicyName
from .service import DeterministicService


@dataclass
class PolicyOutcome:
    final_action: Action
    observations: List[ObservedState]
    retries: int


def apply_policy(name: PolicyName, service: DeterministicService, operation_id: str) -> PolicyOutcome:
    observations: List[ObservedState] = []

    if name == PolicyName.ALWAYS_RETRY:
        service.retry(operation_id, stable_idempotency=False)
        return PolicyOutcome(Action.RETRY, observations, 1)

    if name == PolicyName.ALWAYS_STOP:
        return PolicyOutcome(Action.STOP, observations, 0)

    if name == PolicyName.STABLE_IDEMPOTENCY:
        service.retry(operation_id, stable_idempotency=True)
        return PolicyOutcome(Action.RETRY, observations, 1)

    first = service.status()
    observations.append(first)

    if name == PolicyName.SINGLE_STATUS:
        if first == ObservedState.COMMITTED:
            return PolicyOutcome(Action.STOP, observations, 0)
        service.retry(operation_id, stable_idempotency=False)
        return PolicyOutcome(Action.RETRY, observations, 1)

    if name == PolicyName.TRI_STATE_BACKOFF:
        if first == ObservedState.COMMITTED:
            return PolicyOutcome(Action.STOP, observations, 0)
        if first == ObservedState.NOT_EXECUTED:
            service.retry(operation_id, stable_idempotency=False)
            return PolicyOutcome(Action.RETRY, observations, 1)

        service.advance()
        second = service.status()
        observations.append(second)
        if second == ObservedState.COMMITTED:
            return PolicyOutcome(Action.STOP, observations, 0)
        if second == ObservedState.NOT_EXECUTED:
            service.retry(operation_id, stable_idempotency=False)
            return PolicyOutcome(Action.RETRY, observations, 1)
        return PolicyOutcome(Action.UNRESOLVED, observations, 0)

    raise ValueError("unsupported policy: %s" % name)

