"""Language-agnostic export and scoring for external recovery methods."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

from .confirmation import ConfirmationCell, validate_confirmation_manifest
from .model import Action, EvidenceContract, Schedule, TASKS
from .scoring import score_exact_state
from .service import AmbiguousTimeout, DeterministicService


def export_public_cases(rows: List[ConfirmationCell]) -> List[Dict[str, object]]:
    """Export one model-facing case per response group, omitting hidden schedules."""
    validate_confirmation_manifest(rows)
    cases = []
    seen = set()
    for row in rows:
        if row.response_group_id in seen:
            continue
        seen.add(row.response_group_id)
        cases.append(
            {
                "schema_version": "retrybench-public-case-v1",
                "case_id": row.response_group_id,
                "task_id": row.task_id,
                "evidence": row.evidence,
                "prompt_condition": row.prompt_condition,
                "repetition": row.repetition,
                "instructions": row.instructions,
                "prompt": row.prompt,
                "transcript_sha256": row.transcript_sha256,
            }
        )
    return cases


def load_external_decisions(path: Path) -> Dict[str, Action]:
    decisions: Dict[str, Action] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = str(row["case_id"])
            if case_id in decisions:
                raise ValueError("duplicate case_id on line %d: %s" % (line_number, case_id))
            decisions[case_id] = Action(str(row["action"]))
    return decisions


def score_external_decisions(
    rows: List[ConfirmationCell], decisions: Dict[str, Action]
) -> List[Dict[str, object]]:
    """Replay external actions over every preregistered hidden schedule."""
    validate_confirmation_manifest(rows)
    expected = {row.response_group_id for row in rows}
    missing = sorted(expected - set(decisions))
    extra = sorted(set(decisions) - expected)
    if missing or extra:
        raise ValueError(
            "decision IDs do not match frozen cases: missing=%d extra=%d"
            % (len(missing), len(extra))
        )

    tasks = {task.task_id: task for task in TASKS}
    results = []
    for row in rows:
        task = tasks[row.task_id]
        schedule = Schedule(row.schedule)
        evidence = EvidenceContract(row.evidence)
        action = decisions[row.response_group_id]
        operation_id = "external:%s" % row.cell_id
        service = DeterministicService(task, schedule, evidence)
        try:
            service.start(operation_id)
        except AmbiguousTimeout:
            pass
        observed = service.status()
        if observed.value != row.expected_observed_state:
            raise RuntimeError("observation diverged for %s" % row.cell_id)
        if action == Action.RETRY:
            service.retry(operation_id, stable_idempotency=False)
        service.settle()
        unresolved = action in {Action.WAIT, Action.UNRESOLVED}
        score = score_exact_state(task, operation_id, service.effects, unresolved)
        retry_permitted = (
            schedule == Schedule.FAIL_BEFORE_EXECUTION
            and evidence == EvidenceContract.AUTHORITATIVE
        )
        results.append(
            {
                "schema_version": "retrybench-external-score-v1",
                "cell_id": row.cell_id,
                "case_id": row.response_group_id,
                "task_id": row.task_id,
                "schedule": row.schedule,
                "evidence": row.evidence,
                "prompt_condition": row.prompt_condition,
                "repetition": row.repetition,
                "observed_state": observed.value,
                "action": action.value,
                "retry_permitted": retry_permitted,
                "false_retry_permission": action == Action.RETRY and not retry_permitted,
                "effect_count": len(service.effects),
                **score.to_dict(),
            }
        )
    return results


def summarize_external(results: Iterable[Dict[str, object]]) -> Dict[str, object]:
    rows = list(results)
    actions = Counter(str(row["action"]) for row in rows)
    metrics = (
        "false_retry_permission",
        "duplicate_effect",
        "omission",
        "unresolved",
        "exact_state_success",
    )
    return {
        "schema_version": "retrybench-external-summary-v1",
        "scored_outcomes": len(rows),
        "actions": dict(sorted(actions.items())),
        **{metric: sum(bool(row[metric]) for row in rows) for metric in metrics},
    }


def write_jsonl(path: Path, rows: Iterable[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
