"""Independently replay a completed compatibility pilot without inference."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from retrybench.evaluation import load_predictions, public_cases, score_predictions
from retrybench.cross_model_pilot import reserve, MAX_OUTPUT
from retrybench.serialization import canonical_json_sha256, write_json


def resolve_attachments(value, attachments, seen=frozenset()):
    """Expand Inspect's lossless references without modifying saved records."""
    if isinstance(value, str) and value.startswith("attachment://"):
        key = value[len("attachment://"):]
        if key not in attachments or key in seen:
            raise ValueError("missing or cyclic transcript attachment: " + key)
        return resolve_attachments(attachments[key], attachments, seen | {key})
    if isinstance(value, dict):
        return {k: resolve_attachments(v, attachments, seen) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_attachments(v, attachments, seen) for v in value]
    return value


def verify(directory, output_path=None):
    directory = Path(directory)
    plan = json.loads((directory / "plan.json").read_text())
    summary = json.loads((directory / "run/summary.json").read_text())
    full = plan["schema_version"] == "retrybench-cross-model-full-v1"
    if summary["status"] != ("collected" if full else "passed"):
        raise ValueError("collection is incomplete; preserve its stop report")
    if summary["plan_sha256"] != canonical_json_sha256(plan):
        raise ValueError("plan hash mismatch")
    for name, digest in plan["source_sha256"].items():
        if hashlib.sha256((directory / "source/retrybench" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("snapshot changed: " + name)
    providers = {}
    visible = {c["case_id"]: c for c in public_cases()}
    for provider, config in plan["models"].items():
        dest = directory / "run" / provider
        rows = load_predictions(dest / "predictions.jsonl")
        if [r["case_id"] for r in rows] != plan["case_ids"]:
            raise ValueError("case selection/order mismatch")
        charged = Decimal(plan["prior_retained_reservations_usd"][provider]) if full else Decimal(0)
        fresh_cost = Decimal(0)
        for r in rows:
            if len(r["raw_calls"]) != 1:
                raise ValueError("unexpected raw call count")
            response = resolve_attachments(r["raw_calls"][0]["response"], r.get("transcript_attachments", {}))
            if provider == "openai":
                calls = [x for x in response["output"] if x.get("type") == "function_call"]
                try:
                    args = json.loads(calls[0]["arguments"]) if len(calls) == 1 else None
                except (ValueError, TypeError):
                    args = None
                completed = response["status"] == "completed"
                input_tokens, output_tokens = response["usage"]["input_tokens"], response["usage"]["output_tokens"]
            elif provider == "anthropic":
                calls = [x for x in response["content"] if x.get("type") == "tool_use"]
                args = calls[0]["input"] if len(calls) == 1 else None
                completed = response["stop_reason"] in ("tool_use", "end_turn")
                usage = response["usage"]
                input_tokens = usage["input_tokens"] + (usage.get("cache_creation_input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
                output_tokens = usage["output_tokens"]
            else:
                raise ValueError("unsupported provider audit")
            decodable = (completed and len(calls) == 1 and calls[0]["name"] == "decision"
                         and isinstance(args, dict) and set(args) == {"action", "idempotency_key"})
            if decodable:
                if r.get("status") != "complete" or args != {"action": r.get("action"), "idempotency_key": r.get("arguments", {}).get("idempotency_key")}:
                    raise ValueError("normalized decision differs from raw tool arguments")
            elif r.get("status") != "invalid_output":
                raise ValueError("unusable native output was not recorded as invalid")
            if response["model"] != r["returned_model"] or r["returned_model"] != config["returned_model"]:
                raise ValueError("raw model identity mismatch")
            if (input_tokens, output_tokens) != (r["usage"]["input_tokens"], r["usage"]["output_tokens"]):
                raise ValueError("raw usage differs from normalized usage")
            bound, amount = reserve(visible[r["case_id"]], config)
            actual = (Decimal(input_tokens) * Decimal(config["input_per_million"])
                      + Decimal(output_tokens) * Decimal(config["output_per_million"])) / Decimal(1000000)
            if input_tokens > bound or output_tokens > MAX_OUTPUT or actual > amount:
                raise ValueError("cost/token envelope mismatch")
            if full and charged + amount > Decimal(plan["total_authorized_caps_usd"][provider]):
                raise ValueError("call exceeded admission budget")
            charged += actual
            fresh_cost += actual
        if full:
            if str(fresh_cost) != summary["providers"][provider]["cost_upper_estimate_usd"]:
                raise ValueError("usage cost summary mismatch")
            if charged != Decimal(summary["budget"]["charged_or_reserved_usd"][provider]):
                raise ValueError("cumulative budget reconciliation mismatch")
        saved = json.loads((dest / "report.json").read_text())
        rescored = score_predictions(rows, model=config["model"], settings=saved["settings"])
        for field in ("suite_sha256", "prediction_sha256", "metrics", "per_block", "per_condition", "per_task", "raw_capture", "usage"):
            if rescored.report[field] != saved[field]:
                raise ValueError("rescore mismatch: " + field)
        if rescored.cases != load_predictions(dest / "case-scores.jsonl"):
            raise ValueError("case-score replay mismatch")
        selected = [r for r in rescored.cases if r["case_id"] in plan["case_ids"]]
        providers[provider] = {
            "raw_decisions_and_usage_verified": len(rows), "offline_rescore_identical": True,
            "diagnostic_only": not full, "valid_decisions": sum(c["status"] == "valid" for c in selected),
            "selected_cases": len(selected),
            "selected_frp_count": sum(c["false_retry_permission"] is True for c in selected),
            "selected_progress_count": sum(c["permitted_progress"] is True for c in selected if c["progress_opportunity"]),
            "selected_progress_denominator": sum(c["progress_opportunity"] for c in selected),
            "usage_cost_upper_estimate_usd": str(fresh_cost),
        }
    result = {"verified": True, "plan_sha256": canonical_json_sha256(plan),
              "decision_interface": plan["decision_interface"], "providers": providers,
              "interpretation": ("Full public suite; four reused tasks and selected endpoints, not held-out or population-level evidence."
                                 if full else "Infrastructure diagnostic; selected cases cannot establish full-suite model performance.")}
    write_json(Path(output_path) if output_path else directory / "verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, args.output), indent=2))
