"""Typed benchmark protocol shared by services, policies, and scorers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class Schedule(str, Enum):
    FAIL_BEFORE_EXECUTION = "fail_before_execution"
    COMMIT_THEN_DROP_RESPONSE = "commit_then_drop_response"
    IN_FLIGHT_LATE_COMMIT = "in_flight_late_commit"
    STALE_NEGATIVE_AFTER_COMMIT = "stale_negative_after_commit"


class EvidenceContract(str, Enum):
    NONE = "none"
    WEAK = "weak"
    AUTHORITATIVE = "authoritative"


class ObservedState(str, Enum):
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"
    NOT_EXECUTED = "not_executed"
    IN_FLIGHT = "in_flight"
    COMMITTED = "committed"


class Action(str, Enum):
    RETRY = "retry"
    STOP = "stop"
    WAIT = "wait"
    UNRESOLVED = "unresolved"


class PolicyName(str, Enum):
    ALWAYS_RETRY = "always_retry"
    ALWAYS_STOP = "always_stop"
    SINGLE_STATUS = "single_status"
    TRI_STATE_BACKOFF = "tri_state_backoff"
    STABLE_IDEMPOTENCY = "stable_idempotency"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    tool: str
    target: str
    payload: Dict[str, Any]


TASKS = (
    TaskSpec("issue-001", "create_issue", "repo/acme", {"title": "Fix race"}),
    TaskSpec("review-001", "post_review_comment", "repo/acme#17", {"body": "Please add a test."}),
    TaskSpec("ci-001", "trigger_ci", "repo/acme@main", {"workflow": "release"}),
    TaskSpec("release-001", "create_release", "repo/acme", {"tag": "v1.2.3"}),
)

