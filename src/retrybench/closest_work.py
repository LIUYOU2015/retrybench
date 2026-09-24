"""Source-validated reproduction and extension of the closest public artifact."""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


class ClosestWorkError(RuntimeError):
    """Raised when the frozen source or reproduction contract is violated."""


@dataclass(frozen=True)
class ExtensionOutcome:
    template_id: str
    family: str
    schedule: str
    policy: str
    status_observation: str
    action_calls: int
    effect_count: int
    deduplicated_calls: int
    waited_for_terminal_state: bool
    exactly_once_success: bool
    state_outcome: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ClosestWorkError("expected a JSON object: %s" % path)
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_source_checkout(source_root: Path, protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Verify exact source revision, licensed inputs, and author-selected ids."""
    source = protocol["source"]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ClosestWorkError("cannot resolve source checkout revision") from exc
    if commit != source["commit"]:
        raise ClosestWorkError(
            "source commit mismatch: expected %s, got %s" % (source["commit"], commit)
        )

    observed_hashes: dict[str, str] = {}
    for relative, expected in source["frozen_file_sha256"].items():
        path = source_root / relative
        if not path.is_file():
            raise ClosestWorkError("missing frozen source file: %s" % relative)
        observed = _sha256(path)
        if observed != expected:
            raise ClosestWorkError("source hash mismatch: %s" % relative)
        observed_hashes[relative] = observed

    upstream_manifest = _load_json(
        source_root / "protocol/frozen_manifest_sqj_v1_4.json"
    )
    selected = list(protocol["slice_selection"]["ids"])
    if upstream_manifest.get("replication_subset_ids") != selected:
        raise ClosestWorkError("frozen ids differ from upstream replication_subset_ids")
    if upstream_manifest.get("protocol_id") != source["protocol_id"]:
        raise ClosestWorkError("upstream protocol id mismatch")
    return {"commit": commit, "file_sha256": observed_hashes}


def _import_upstream(source_root: Path):
    source_paths = (str(source_root), str(source_root / "src"))
    for value in reversed(source_paths):
        if value not in sys.path:
            sys.path.insert(0, value)
    try:
        confirmatory = importlib.import_module("tools.confirmatory_suite_probe")
        family = importlib.import_module("tools.ambiguous_task_family_probe")
        core = importlib.import_module("tools.ambiguous_outcome_probe")
    except ImportError as exc:
        raise ClosestWorkError("cannot import the validated upstream artifact") from exc
    module_file = Path(confirmatory.__file__).resolve()
    if source_root.resolve() not in module_file.parents:
        raise ClosestWorkError("loaded confirmatory module outside validated checkout")
    return confirmatory, family, core


def load_validated_slice(
    source_root: Path,
    slice_path: Path,
    protocol: Mapping[str, Any],
) -> tuple[list[Any], dict[str, Any]]:
    provenance = validate_source_checkout(source_root, protocol)
    confirmatory, _, _ = _import_upstream(source_root)
    catalog_path = (
        source_root / "data/public/ambiguous_outcomes_se_v1_4/catalog.jsonl"
    )
    expanded = confirmatory.expand_catalog(confirmatory.load_catalog(catalog_path))
    by_id = {item.template_id: item for item in expanded}
    ids = list(protocol["slice_selection"]["ids"])
    try:
        templates = [by_id[item_id] for item_id in ids]
    except KeyError as exc:
        raise ClosestWorkError("upstream selected template is absent") from exc
    extracted = [asdict(item) for item in templates]
    frozen = _load_jsonl(slice_path)
    if extracted != frozen:
        raise ClosestWorkError("vendored slice differs from upstream expansion")
    provenance["slice_sha256"] = _sha256(slice_path)
    return templates, provenance


def run_source_faithful_block(
    templates: Sequence[Any], source_root: Path
) -> list[dict[str, Any]]:
    """Use the source artifact's own simulator and episode function."""
    _, family, core = _import_upstream(source_root)
    controls = (
        ("prompt_only_stop", core.Affordance.NONE, core.RecoveryPolicy.STOP),
        ("prompt_only_retry", core.Affordance.NONE, core.RecoveryPolicy.RETRY),
        (
            "authoritative_status_reconcile",
            core.Affordance.STATUS,
            core.RecoveryPolicy.RECONCILE,
        ),
        (
            "stable_idempotency_retry",
            core.Affordance.IDEMPOTENCY,
            core.RecoveryPolicy.IDEMPOTENT_RETRY,
        ),
    )
    rows: list[dict[str, Any]] = []
    for template in templates:
        for hidden in family.HiddenWorld:
            for control, affordance, policy in controls:
                result = family.run_family_episode(
                    template, hidden, affordance, policy
                )
                row = asdict(result)
                row["control"] = control
                rows.append(row)
    return rows


def _state_outcome(family: str, effect_count: int) -> str:
    if effect_count == 0:
        return "omission"
    if effect_count == 1:
        return "exactly_once"
    return {
        "create_once": "duplicate_entity",
        "ordered_transition": "target_overshoot",
        "reserve_then_link": "overconsumption_and_orphan",
    }[family]


def run_extension_episode(template: Any, schedule: str, policy: str) -> ExtensionOutcome:
    schedules = {
        "not_executed",
        "executed_response_lost",
        "in_flight_late_commit",
        "stale_negative_after_commit",
    }
    policies = {
        "negative_status_as_retry_permission",
        "terminal_aware_status_reconcile",
        "stable_idempotency_retry",
    }
    if schedule not in schedules:
        raise ValueError("unknown extension schedule: %s" % schedule)
    if policy not in policies:
        raise ValueError("unknown extension policy: %s" % policy)

    initial_effect = schedule in {
        "executed_response_lost",
        "stale_negative_after_commit",
    }
    original_pending = schedule == "in_flight_late_commit"
    effect_count = int(initial_effect)
    action_calls = 1
    deduplicated = 0
    waited = False

    if schedule == "not_executed":
        status = (
            "WEAK_NOT_FOUND"
            if policy == "negative_status_as_retry_permission"
            else "TERMINAL_NOT_EXECUTED"
        )
    elif schedule == "executed_response_lost":
        status = "COMMITTED"
    elif schedule == "in_flight_late_commit":
        status = "WEAK_NOT_FOUND" if policy == "negative_status_as_retry_permission" else "IN_FLIGHT"
    else:
        status = "WEAK_NOT_FOUND" if policy == "negative_status_as_retry_permission" else "COMMITTED"

    if policy == "negative_status_as_retry_permission":
        if status in {"TERMINAL_NOT_EXECUTED", "WEAK_NOT_FOUND"}:
            action_calls += 1
            effect_count += 1
    elif policy == "terminal_aware_status_reconcile":
        if status == "TERMINAL_NOT_EXECUTED":
            action_calls += 1
            effect_count += 1
        elif status == "IN_FLIGHT":
            waited = True
    else:
        action_calls += 1
        if initial_effect or original_pending:
            deduplicated += 1
        else:
            effect_count += 1

    if original_pending:
        effect_count += 1

    outcome = _state_outcome(template.family, effect_count)
    return ExtensionOutcome(
        template_id=template.template_id,
        family=template.family,
        schedule=schedule,
        policy=policy,
        status_observation=status,
        action_calls=action_calls,
        effect_count=effect_count,
        deduplicated_calls=deduplicated,
        waited_for_terminal_state=waited,
        exactly_once_success=outcome == "exactly_once",
        state_outcome=outcome,
    )


def run_extension_block(templates: Sequence[Any]) -> list[ExtensionOutcome]:
    return [
        run_extension_episode(template, schedule, policy)
        for template in templates
        for schedule in (
            "not_executed",
            "executed_response_lost",
            "in_flight_late_commit",
            "stale_negative_after_commit",
        )
        for policy in (
            "negative_status_as_retry_permission",
            "terminal_aware_status_reconcile",
            "stable_idempotency_retry",
        )
    ]


def _summarize(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return {
        name: {
            "episodes": len(values),
            "exact_state_successes": sum(
                bool(item["exactly_once_success"]) for item in values
            ),
            "exact_state_rate": sum(
                bool(item["exactly_once_success"]) for item in values
            ) / len(values),
        }
        for name, values in grouped.items()
    }


def _source_family_rates(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for family in sorted({str(row["family"]) for row in rows}):
        selected = [row for row in rows if row["family"] == family]
        by_control = _summarize(selected, "control")
        result[family] = {
            "by_control": by_control,
            "no_affordance_best_exact_state_rate": max(
                by_control["prompt_only_stop"]["exact_state_rate"],
                by_control["prompt_only_retry"]["exact_state_rate"],
            ),
        }
    return result


def run_closest_work(
    source_root: Path,
    protocol_path: Path,
    slice_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    protocol = _load_json(protocol_path)
    templates, provenance = load_validated_slice(
        source_root, slice_path, protocol
    )
    source_rows = run_source_faithful_block(templates, source_root)
    extension_results = run_extension_block(templates)
    extension_rows = [item.to_dict() for item in extension_results]
    source_summary = _summarize(source_rows, "control")
    source_by_family = _source_family_rates(source_rows)
    extension_summary = _summarize(extension_rows, "policy")

    expected_source = protocol["source_faithful_block"][
        "primary_reproduction_checks"
    ]
    source_checks = {
        "no_affordance_best_is_half_in_every_family": all(
            value["no_affordance_best_exact_state_rate"]
            == expected_source[
                "no_affordance_best_exact_state_rate_in_every_family"
            ]
            for value in source_by_family.values()
        ),
        "authoritative_status_is_one_in_every_family": all(
            value["by_control"]["authoritative_status_reconcile"][
                "exact_state_rate"
            ]
            == expected_source[
                "authoritative_status_reconcile_exact_state_rate_in_every_family"
            ]
            for value in source_by_family.values()
        ),
        "stable_idempotency_is_one_in_every_family": all(
            value["by_control"]["stable_idempotency_retry"][
                "exact_state_rate"
            ]
            == expected_source[
                "stable_idempotency_retry_exact_state_rate_in_every_family"
            ]
            for value in source_by_family.values()
        ),
    }
    weak_failures = [
        row
        for row in extension_rows
        if row["policy"] == "negative_status_as_retry_permission"
        and not row["exactly_once_success"]
    ]
    extension_checks = {
        "weak_negative_failures_only_in_added_schedules": bool(weak_failures)
        and all(
            row["schedule"]
            in {"in_flight_late_commit", "stale_negative_after_commit"}
            for row in weak_failures
        ),
        "terminal_aware_status_safe_everywhere": extension_summary[
            "terminal_aware_status_reconcile"
        ]["exact_state_rate"]
        == 1.0,
        "stable_idempotency_safe_everywhere": extension_summary[
            "stable_idempotency_retry"
        ]["exact_state_rate"]
        == 1.0,
    }
    all_checks = {**source_checks, **extension_checks}
    report = {
        "schema_version": "retrybench-closest-work-analysis-v1",
        "api_calls": 0,
        "api_cost_usd": 0.0,
        "source_provenance": provenance,
        "slice": {
            "templates": len(templates),
            "families": sorted({item.family for item in templates}),
            "ids": [item.template_id for item in templates],
        },
        "source_faithful": {
            "episodes": len(source_rows),
            "by_control": source_summary,
            "by_family": source_by_family,
            "post_freeze_correction": protocol["source_faithful_block"][
                "post_freeze_correction"
            ],
        },
        "retrybench_extension": {
            "episodes": len(extension_rows),
            "by_policy": extension_summary,
            "weak_negative_failures_by_schedule": {
                schedule: sum(row["schedule"] == schedule for row in weak_failures)
                for schedule in sorted({row["schedule"] for row in extension_rows})
            },
        },
        "checks": all_checks,
        "all_frozen_checks_passed": all(all_checks.values()),
        "conclusion": (
            "The source artifact's structural status and idempotency controls "
            "reproduce on its author-selected slice. After adding in-flight and "
            "stale-negative worlds, a negative lookup is not sufficient retry "
            "permission; the status benefit is conditional on authoritative, "
            "terminal-aware evidence. Stable idempotency remains safe."
        ),
        "scope": (
            "This deterministic slice validates a construct boundary and does not "
            "reproduce the upstream paper's model-dependent aggregate rates."
        ),
    }
    return report, source_rows + extension_rows


def write_closest_work_outputs(
    report: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes = output_dir / "outcomes.jsonl"
    outcomes.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    final_report = dict(report)
    final_report["outcomes_sha256"] = _sha256(outcomes)
    (output_dir / "analysis.json").write_text(
        json.dumps(final_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
