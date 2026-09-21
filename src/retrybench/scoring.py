"""Exact-state scoring over the full side-effect identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List

from .model import EffectRecord, TaskSpec


@dataclass(frozen=True)
class ExactStateScore:
    exact_state_success: bool
    duplicate_effect: bool
    omission: bool
    unresolved: bool
    wrong_operation_identity: bool
    wrong_task: bool
    wrong_tool: bool
    wrong_target: bool
    wrong_payload: bool

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)


def score_exact_state(
    task: TaskSpec,
    expected_operation_id: str,
    effects: Iterable[EffectRecord],
    unresolved: bool,
) -> ExactStateScore:
    """Require exactly one effect whose complete identity matches the intent."""
    records: List[EffectRecord] = list(effects)
    wrong_operation_identity = any(
        record.operation_id != expected_operation_id for record in records
    )
    wrong_task = any(record.task_id != task.task_id for record in records)
    wrong_tool = any(record.tool != task.tool for record in records)
    wrong_target = any(record.target != task.target for record in records)
    wrong_payload = any(record.payload != task.payload for record in records)
    omission = not records
    duplicate_effect = len(records) > 1
    exact_identity = not any(
        (
            wrong_operation_identity,
            wrong_task,
            wrong_tool,
            wrong_target,
            wrong_payload,
        )
    )
    return ExactStateScore(
        exact_state_success=(
            len(records) == 1 and exact_identity and not unresolved
        ),
        duplicate_effect=duplicate_effect,
        omission=omission,
        unresolved=unresolved,
        wrong_operation_identity=wrong_operation_identity,
        wrong_task=wrong_task,
        wrong_tool=wrong_tool,
        wrong_target=wrong_target,
        wrong_payload=wrong_payload,
    )
