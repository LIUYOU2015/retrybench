"""Deterministic side-effect service with hidden execution schedules."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import List, Optional, Set

from .model import EffectRecord, EvidenceContract, ObservedState, Schedule, TaskSpec


class AmbiguousTimeout(TimeoutError):
    """The only initial failure visible to a recovery policy."""


@dataclass
class DeterministicService:
    task: TaskSpec
    schedule: Schedule
    evidence: EvidenceContract
    effects: List[EffectRecord] = field(default_factory=list)
    dedupe_records: Set[str] = field(default_factory=set)
    pending_original: bool = False
    original_operation_id: Optional[str] = None
    dedupe_enabled: bool = False
    steps: int = 0
    probes: int = 0

    def start(self, operation_id: str) -> None:
        """Dispatch the original call and always expose the same timeout."""
        self.original_operation_id = operation_id
        if self.schedule == Schedule.FAIL_BEFORE_EXECUTION:
            pass
        elif self.schedule == Schedule.COMMIT_THEN_DROP_RESPONSE:
            self._commit(operation_id, deduplicate=False)
        elif self.schedule == Schedule.IN_FLIGHT_LATE_COMMIT:
            self.pending_original = True
        elif self.schedule == Schedule.STALE_NEGATIVE_AFTER_COMMIT:
            self._commit(operation_id, deduplicate=False)
        raise AmbiguousTimeout("tool call timed out")

    def status(self) -> ObservedState:
        self.probes += 1
        if self.evidence == EvidenceContract.NONE:
            return ObservedState.UNKNOWN

        if self.evidence == EvidenceContract.WEAK:
            if self.steps == 0 and self.schedule in {
                Schedule.FAIL_BEFORE_EXECUTION,
                Schedule.IN_FLIGHT_LATE_COMMIT,
                Schedule.STALE_NEGATIVE_AFTER_COMMIT,
            }:
                return ObservedState.NOT_FOUND
            return ObservedState.COMMITTED if self.effects else ObservedState.NOT_FOUND

        if self.schedule == Schedule.FAIL_BEFORE_EXECUTION:
            return ObservedState.NOT_EXECUTED
        if self.pending_original:
            return ObservedState.IN_FLIGHT
        return ObservedState.COMMITTED if self.effects else ObservedState.NOT_EXECUTED

    def advance(self) -> None:
        """Advance logical time and allow an in-flight original call to commit."""
        self.steps += 1
        if self.pending_original:
            self.pending_original = False
            self._commit(self.original_operation_id or "original", deduplicate=self.dedupe_enabled)

    def retry(self, operation_id: str, stable_idempotency: bool) -> None:
        self.dedupe_enabled = stable_idempotency
        self._commit(operation_id, deduplicate=stable_idempotency)

    def settle(self) -> None:
        """Finish outstanding work before ground-truth scoring."""
        self.advance()

    def _commit(self, operation_id: str, deduplicate: bool) -> None:
        if deduplicate and operation_id in self.dedupe_records:
            return
        self.effects.append(
            EffectRecord(
                operation_id=operation_id,
                task_id=self.task.task_id,
                tool=self.task.tool,
                target=self.task.target,
                payload=deepcopy(self.task.payload),
            )
        )
        if deduplicate:
            self.dedupe_records.add(operation_id)


def seed_original_idempotency_record(service: DeterministicService, operation_id: str) -> None:
    """Record a committed original call in the provider's dedupe store."""
    if service.effects:
        service.dedupe_records.add(operation_id)
