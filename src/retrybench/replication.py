"""Frozen GPT-5.4 replication of the confirmation-v2 design."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .confirmation import (
    ConfirmationCell,
    build_confirmation_manifest,
    run_confirmation_preflight,
    run_live_confirmation,
)
from .openai_adapter import CostBudget, OpenAIResponsesPolicy


REPLICATION_MODEL = "gpt-5.4-2026-03-05"
REPLICATION_MAX_OUTPUT_TOKENS = 256
# Existing tracked project spend is $0.10871025. This cap keeps the cumulative
# autonomous-spend ceiling below the user's $1 check-in threshold.
REPLICATION_MAX_COST_USD = 0.85
REPLICATION_CELL_PREFIX = "gpt54-repl"
REPLICATION_GROUP_PREFIX = "gpt54-rg"


def build_replication_manifest() -> List[ConfirmationCell]:
    """Change only the fixed model snapshot and coordinate prefixes."""
    return build_confirmation_manifest(
        model=REPLICATION_MODEL,
        cell_prefix=REPLICATION_CELL_PREFIX,
        response_group_prefix=REPLICATION_GROUP_PREFIX,
        max_output_tokens=REPLICATION_MAX_OUTPUT_TOKENS,
    )


def run_replication_preflight(rows: List[ConfirmationCell]) -> Dict[str, object]:
    return run_confirmation_preflight(
        rows,
        model=REPLICATION_MODEL,
        maximum_cost_usd=REPLICATION_MAX_COST_USD,
        cell_prefix=REPLICATION_CELL_PREFIX,
        response_group_prefix=REPLICATION_GROUP_PREFIX,
        schema_version="retrybench-gpt54-replication-preflight-v1",
        max_output_tokens=REPLICATION_MAX_OUTPUT_TOKENS,
    )


def run_live_replication(
    rows: List[ConfirmationCell],
    policy: OpenAIResponsesPolicy,
    budget: CostBudget,
    database_path: Path,
    output_path: Path,
    late_commit_delay: float = 0.1,
    resume: bool = False,
) -> List[Dict[str, object]]:
    return run_live_confirmation(
        rows,
        policy,
        budget,
        database_path,
        output_path,
        late_commit_delay=late_commit_delay,
        expected_model=REPLICATION_MODEL,
        maximum_cost_usd=REPLICATION_MAX_COST_USD,
        cell_prefix=REPLICATION_CELL_PREFIX,
        response_group_prefix=REPLICATION_GROUP_PREFIX,
        operation_prefix="gpt54-replication",
        schema_version="retrybench-live-gpt54-replication-v1",
        resume=resume,
        expected_max_output_tokens=REPLICATION_MAX_OUTPUT_TOKENS,
    )
