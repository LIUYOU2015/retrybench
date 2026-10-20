"""Versioned, provider-independent first-decision evaluation.

Inference receives only public cases. Missing and invalid decisions are unknown,
never silently converted to a safe action or dropped from planned denominators.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

from .model import EvidenceContract, Schedule, TaskSpec
from .scoring import retry_is_permitted, score_exact_state
from .serialization import canonical_json_sha256, write_json, write_jsonl
from .service import AmbiguousTimeout, DeterministicService, seed_original_idempotency_record

SUITE = "retry-permission-v1"
SUITE_SHA256 = "ebdfdbd7962cc532c82c27abffbdb9f93f3131a96f9eff3f2f98572272718235"
SCORER_VERSION = "retrybench-score-v1"
PREDICTION_VERSION = "retrybench-prediction-v1"


def load_suite(suite: str = SUITE) -> dict:
    if suite != SUITE:
        raise ValueError("unknown suite: %s (available: %s)" % (suite, SUITE))
    data = json.loads(resources.files("retrybench").joinpath("data", suite + ".json").read_text())
    if canonical_json_sha256(data) != SUITE_SHA256:
        raise ValueError("packaged suite hash mismatch; protocol changes require a new version")
    return data


def decision_schema(actions: list) -> dict:
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": actions},
            "idempotency_key": {"type": ["string", "null"]},
        },
        "required": ["action", "idempotency_key"],
        "additionalProperties": False,
    }


def public_cases(suite: str = SUITE) -> list:
    """Export inference inputs only; no schedules or gold labels."""
    return [
        {
            "schema_version": "retrybench-case-v1", "suite": suite,
            "suite_sha256": SUITE_SHA256,
            **{k: c[k] for k in ("case_id", "instructions", "prompt", "transcript_sha256")},
            "decision_schema": decision_schema(c["allowed_actions"]),
        }
        for c in load_suite(suite)["cases"]
    ]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def load_predictions(path: Path) -> list:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, object_pairs_hook=_unique_object,
                             parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
        except ValueError as exc:
            raise ValueError("invalid JSON on line %d: %s" % (number, exc)) from exc
        if not isinstance(row, dict):
            raise ValueError("prediction on line %d must be an object" % number)
        records.append(row)
    return records


def _decision(row: Mapping, case: Mapping):
    """Return (action, key, error); never repair malformed model output."""
    if row.get("status", "complete") != "complete":
        return None, None, "prediction status: %s" % row.get("status")
    if row.get("schema_version", PREDICTION_VERSION) != PREDICTION_VERSION:
        return None, None, "unsupported prediction schema"
    for field, expected in (("suite", SUITE), ("suite_sha256", SUITE_SHA256),
                            ("transcript_sha256", case["transcript_sha256"])):
        if field in row and row[field] != expected:
            return None, None, "%s mismatch" % field
    action = row.get("action")
    args = row.get("arguments", {})
    if not isinstance(args, dict) or set(args) - {"idempotency_key"}:
        return None, None, "arguments must contain only idempotency_key"
    if "idempotency_key" in row and "idempotency_key" in args:
        return None, None, "idempotency_key supplied twice"
    key = args.get("idempotency_key", row.get("idempotency_key"))
    # Aliases preserve the original five-way action space. NOT_RETRY does not
    # claim completion; consumers that mean completion must explicitly use stop.
    if action == "RETRY":
        action = "retry_with_key" if key is not None else "retry"
    elif action == "VERIFY_FIRST":
        action = "wait"
    elif action == "NOT_RETRY":
        action = "unresolved"
    if not isinstance(action, str) or action not in case["allowed_actions"]:
        return None, None, "action is not permitted by the output schema"
    if action == "retry_with_key":
        if not isinstance(key, str) or not key:
            return None, None, "retry_with_key requires a nonempty string key"
    elif key is not None:
        return None, None, "non-keyed action must have a null or omitted key"
    return action, key, None


def _replay(case: Mapping, task: TaskSpec, action: str, key: Optional[str]) -> list:
    rows = []
    for name in case["schedules"]:
        schedule, evidence = Schedule(name), EvidenceContract(case["evidence"])
        service = DeterministicService(task, schedule, evidence)
        operation = "public:" + case["case_id"]
        try:
            service.start(operation)
        except AmbiguousTimeout:
            pass
        if case["original_key"] is not None:
            seed_original_idempotency_record(service, operation)
        observed = service.status()
        if observed.value != case["observed_state"]:
            raise RuntimeError("simulator observation differs from frozen case")
        protected = (action == "retry_with_key" and case["original_key"] is not None
                     and key == case["original_key"])
        permission = protected or retry_is_permitted(schedule, evidence, observed)
        dispatch = action in ("retry", "retry_with_key")
        if dispatch:
            service.retry(operation, stable_idempotency=protected)
        service.settle()
        score = score_exact_state(task, operation, service.effects, action in ("wait", "unresolved"))
        rows.append({
            "case_id": case["case_id"], "schedule": name,
            "action": action, "idempotency_key": key,
            "false_retry_permission": dispatch and not permission,
            "permitted_progress": dispatch and permission and score.exact_state_success,
            "effect_count": len(service.effects), **score.to_dict(),
        })
    return rows


def _metric(values: list) -> dict:
    known = [x for x in values if x is not None]
    count, planned, valid = sum(bool(x) for x in known), len(values), len(known)
    return {
        "count": count, "known_denominator": valid, "planned_denominator": planned,
        "unknown": planned - valid,
        "rate_among_known": count / valid if valid else None,
        "planned_rate_bounds": [count / planned, (count + planned - valid) / planned] if planned else None,
    }


def _summarize(rows: list) -> dict:
    outcomes = [world for row in rows for world in row["outcomes"]]
    return {
        "planned_cases": len(rows), "planned_outcomes": len(outcomes),
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "actions": dict(Counter(row["action"] for row in rows if row["action"] is not None)),
        "protocol_validity": _metric([row["status"] == "valid" for row in rows]),
        "false_retry_permission": _metric([row["false_retry_permission"] for row in rows]),
        "permitted_progress": _metric([row["permitted_progress"] for row in rows if row["progress_opportunity"]]),
        "outcomes": {name: _metric([world[name] for world in outcomes]) for name in (
            "false_retry_permission", "exact_state_success", "duplicate_effect", "omission", "unresolved")},
    }


def _usage(predictions: list) -> dict:
    fields = ("input_tokens", "output_tokens", "cost_usd")
    result = {}
    for field in fields:
        values = []
        for row in predictions:
            usage = row.get("usage")
            value = usage.get(field) if isinstance(usage, dict) else None
            if (isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and value >= 0):
                values.append(value)
        result[field] = {"reported_total": sum(values) if values else None,
                         "reported_records": len(values), "submitted_records": len(predictions)}
    return result


@dataclass
class EvaluationResult:
    report: dict
    cases: list
    predictions: list

    @property
    def false_retry_permission_rate(self):
        return self.report["metrics"]["false_retry_permission"]["rate_among_known"]

    @property
    def per_condition(self):
        return self.report["per_condition"]

    def save(self, directory: Path) -> None:
        """Write a new self-contained result bundle; never overwrite a run."""
        directory = Path(directory)
        if directory.exists() and any(directory.iterdir()):
            raise ValueError("output directory must be empty: %s" % directory)
        directory.mkdir(parents=True, exist_ok=True)
        write_jsonl(directory / "predictions.jsonl", self.predictions)
        write_jsonl(directory / "case-scores.jsonl", self.cases)
        write_json(directory / "report.json", self.report)


def score_predictions(predictions: Iterable[Mapping], suite: str = SUITE,
                      model: Optional[str] = None, settings: Optional[Mapping] = None) -> EvaluationResult:
    data = load_suite(suite)
    predictions = list(predictions)
    # The Python API must obey the same finite JSON contract as the JSONL CLI.
    json.dumps(predictions, allow_nan=False)
    expected = {c["case_id"] for c in data["cases"]}
    indexed = {}
    for row in predictions:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            raise ValueError("each prediction must have a string case_id")
        cid = row["case_id"]
        if cid not in expected:
            raise ValueError("unknown case_id: %s" % cid)
        if cid in indexed:
            raise ValueError("duplicate case_id: %s" % cid)
        indexed[cid] = row
    tasks = {t["task_id"]: TaskSpec(**t) for t in data["tasks"]}
    results = []
    for case in data["cases"]:
        prediction = indexed.get(case["case_id"])
        action, key, error = _decision(prediction, case) if prediction is not None else (None, None, "missing prediction")
        opportunity = (case["original_key"] is not None or
                       (case["evidence"] == "authoritative" and case["observed_state"] == "not_executed"))
        outcomes = _replay(case, tasks[case["task_id"]], action, key) if error is None else [
            {"case_id": case["case_id"], "schedule": s, **{k: None for k in (
                "false_retry_permission", "permitted_progress", "exact_state_success",
                "duplicate_effect", "omission", "unresolved", "effect_count")}}
            for s in case["schedules"]
        ]
        results.append({
            **{k: case[k] for k in ("case_id", "task_id", "block", "condition", "repetition")},
            "status": "missing" if prediction is None else ("invalid" if error else "valid"),
            "error": error, "action": action, "idempotency_key": key,
            "progress_opportunity": opportunity,
            "false_retry_permission": any(x["false_retry_permission"] for x in outcomes) if error is None else None,
            "permitted_progress": all(x["permitted_progress"] for x in outcomes) if error is None else None,
            "outcomes": outcomes,
        })
    source_files = ("evaluation.py", "model.py", "scoring.py", "service.py", "serialization.py")
    report = {
        "schema_version": SCORER_VERSION, "suite": suite, "suite_sha256": SUITE_SHA256,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": model, "settings": dict(settings or {}),
        "prediction_sha256": canonical_json_sha256(predictions),
        "scorer_source_sha256": {f: hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest() for f in source_files},
        "scope": data["scope"], "metrics": _summarize(results),
        "per_condition": {c: _summarize([r for r in results if r["condition"] == c]) for c in sorted({r["condition"] for r in results})},
        "per_task": {t: _summarize([r for r in results if r["task_id"] == t]) for t in sorted(tasks)},
        "per_block": {b: _summarize([r for r in results if r["block"] == b]) for b in sorted({r["block"] for r in results})},
        "usage": _usage(predictions),
        "raw_capture": {
            "submitted_records": len(predictions),
            "provider_response_available": sum(p.get("raw_provider_response_available") is True for p in predictions),
            "note": "Availability is adapter-reported; arbitrary imported predictions may use other raw-output fields.",
        },
        "complete": all(r["status"] == "valid" for r in results),
        "uncertainty": "Bounds reflect unknown decisions, not confidence intervals. Hidden worlds share decisions; repeated prompts and four reused tasks are not independent population samples.",
        "verification": "locally rescored; model identity and collection claims are self-reported",
    }
    return EvaluationResult(report, results, predictions)


def evaluate(model: str, adapter: Callable[[dict], Mapping], suite: str = SUITE,
             settings: Optional[Mapping] = None, limit: Optional[int] = None,
             output_dir: Optional[Path] = None) -> EvaluationResult:
    """Call an adapter once per visible case; preserve errors and planned slots.

    An adapter returns a prediction mapping (action, arguments, raw_response,
    usage, etc.). It must implement one decision, with no recovery-tool execution.
    With output_dir, journal each response immediately and refuse run overwrite.
    """
    cases = public_cases(suite)
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("limit must be a positive integer")
    directory = Path(output_dir) if output_dir is not None else None
    if directory is not None:
        if directory.exists() and any(directory.iterdir()):
            raise ValueError("output directory must be empty: %s" % directory)
        directory.mkdir(parents=True, exist_ok=True)
        write_jsonl(directory / "cases.jsonl", cases)
        write_json(directory / "run.json", {"model": model, "settings": dict(settings or {}),
                   "suite": suite, "suite_sha256": SUITE_SHA256, "limit": limit,
                   "started_at_utc": datetime.now(timezone.utc).isoformat()})
    predictions = []
    for case in cases[:limit]:
        if directory is not None:
            write_json(directory / "pending.json", {"case_id": case["case_id"]})
        try:
            output = adapter(copy.deepcopy(case))
            if not isinstance(output, Mapping):
                raise ValueError("adapter must return a prediction mapping")
            output = dict(output)
            # Validate serialization before journaling. Never silently discard raw data.
            json.dumps(output, allow_nan=False)
            if "case_id" in output and output["case_id"] != case["case_id"]:
                raise ValueError("adapter returned a different case_id")
        except Exception as exc:
            output = {"status": "adapter_error", "error": "%s: %s" % (type(exc).__name__, exc)}
        record = {**output, "case_id": case["case_id"], "suite": suite,
                  "suite_sha256": SUITE_SHA256, "transcript_sha256": case["transcript_sha256"],
                  "collected_at_utc": datetime.now(timezone.utc).isoformat()}
        predictions.append(record)
        if directory is not None:
            with (directory / "predictions.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
            (directory / "pending.json").unlink()
        if output.get("status") == "adapter_error":
            break  # do not repeat a broken/billable adapter across the remaining suite
    result = score_predictions(predictions, suite, model, settings)
    if directory is not None:
        write_jsonl(directory / "case-scores.jsonl", result.cases)
        write_json(directory / "report.json", result.report)
    return result
