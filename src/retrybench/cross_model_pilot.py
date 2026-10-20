"""Bounded live compatibility diagnostic, separate from full-suite estimates."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .evaluation import SUITE, SUITE_SHA256, load_suite, public_cases, score_predictions
from .serialization import canonical_json_sha256, read_json_object, write_json, write_jsonl

MODEL_CONFIGS = {
    "openai": {
        "model": "openai/gpt-5.4-mini-2026-03-17", "returned_model": "gpt-5.4-mini-2026-03-17",
        "input_per_million": "0.75", "output_per_million": "4.50",
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-5.4-mini",
        "model_args": {"max_retries": 0, "responses_api": True, "responses_store": False,
                       "service_tier": "default", "base_url": "https://api.openai.com/v1"},
    },
    "anthropic": {
        "model": "anthropic/claude-sonnet-4-6", "returned_model": "claude-sonnet-4-6",
        "input_per_million": "3", "output_per_million": "15",
        "pricing_source": "https://platform.claude.com/docs/en/about-claude/pricing",
        "model_args": {"max_retries": 0, "streaming": False, "base_url": "https://api.anthropic.com"},
    },
}
MAX_OUTPUT = 512


def now():
    return datetime.now(timezone.utc).isoformat()


def balanced_case_ids():
    """Two distinct tasks in each condition, six cases per task, no outcomes."""
    cases = load_suite()["cases"]
    tasks = sorted({c["task_id"] for c in cases})
    selected = []
    for i, condition in enumerate(sorted({c["condition"] for c in cases})):
        for j in (0, 2):
            selected.append(next(c["case_id"] for c in cases if c["condition"] == condition
                                 and c["task_id"] == tasks[(i + j) % len(tasks)] and c["repetition"] == 1))
    # First calls cover both an evidence and a key interface; each provider sees
    # the same fixed order, interleaved at collection time.
    return [selected[0], selected[-1]] + selected[1:-1]


def reserve(case, config):
    """Conservative text-only reservation, never released for later requests.

    Twice the UTF-8 serialized public input bytes plus 8192 framing tokens, plus
    the entire output cap, all at uncached standard prices. No billed tools,
    explicit prompt-cache writes, retries, images, or priority tier are enabled.
    This is a declared token envelope, not control of a provider's billing system.
    """
    input_bound = 2 * (len(json.dumps(case, ensure_ascii=False).encode("utf-8")) + 4096)
    amount = (Decimal(input_bound) * Decimal(config["input_per_million"])
              + Decimal(MAX_OUTPUT) * Decimal(config["output_per_million"])) / Decimal(1000000)
    return input_bound, amount


def prepare(directory, caps):
    directory = Path(directory)
    if directory.exists():
        raise ValueError("refusing to replace a frozen pilot directory")
    if set(caps) != set(MODEL_CONFIGS):
        raise ValueError("provide separate OpenAI and Anthropic caps")
    for cap in caps.values():
        if not Decimal(str(cap)).is_finite() or Decimal(str(cap)) <= 0:
            raise ValueError("caps must be finite and positive")
    ids = balanced_case_ids()
    visible = {c["case_id"]: c for c in public_cases()}
    records = [{"provider": p, "case_id": cid,
                "input_token_reservation": reserve(visible[cid], config)[0],
                "reserved_usd": str(reserve(visible[cid], config)[1])}
               for cid in ids for p, config in MODEL_CONFIGS.items()]
    totals = {p: sum((Decimal(r["reserved_usd"]) for r in records if r["provider"] == p), Decimal(0)) for p in caps}
    if any(totals[p] > Decimal(str(caps[p])) for p in caps):
        raise ValueError("full pilot reservation exceeds a provider cap: %s" % totals)
    directory.mkdir(parents=True)
    source = Path(__file__).resolve().parent
    shutil.copytree(source, directory / "source/retrybench", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    snapshot = directory / "source/retrybench"
    source_hashes = {str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(snapshot.rglob("*")) if p.is_file()}
    plan = {
        "schema_version": "retrybench-cross-model-pilot-v2", "suite": SUITE,
        "decision_interface": "inspect-null-only-unkeyed-v2",
        "suite_sha256": SUITE_SHA256, "created_at_utc": now(),
        "purpose": "Compatibility diagnostic only; not a complete benchmark or ranking",
        "case_ids": ids, "models": MODEL_CONFIGS,
        "generation": {"max_output_tokens": MAX_OUTPUT, "reasoning_effort": "none",
                       "temperature": None, "cache_prompt": False, "timeout_seconds": 45},
        "authorized_caps_usd": {p: str(caps[p]) for p in caps},
        "total_reserved_usd": {p: str(totals[p]) for p in caps},
        "request_plan": records, "source_sha256": source_hashes,
        "reservation_policy": "2 * (public case JSON UTF8 bytes + 4096) input tokens + full output cap at uncached standard rates; reservations never released; stop on overrun, unknown usage or audit failure",
        "price_check_date": "2026-10-19",
        "stop_policy": "One attempt per case/provider. Halt all remaining calls on any infrastructure, output-schema, raw-capture, model-identity, token-envelope or usage audit failure. No replacements or automatic resume.",
    }
    write_json(directory / "plan.json", plan)
    write_jsonl(directory / "cases.jsonl", [visible[cid] for cid in ids])
    return plan


def audit_record(record, request, config):
    if record.get("status") != "complete":
        return "provider or output failure"
    if record.get("returned_model") != config["returned_model"]:
        return "returned model mismatch"
    if not record.get("raw_provider_response_available") or len(record.get("raw_calls", [])) != 1:
        return "raw call capture missing or unexpected call count"
    usage = record.get("usage", {})
    for key in ("input_tokens", "output_tokens"):
        if type(usage.get(key)) is not int or usage[key] < 0:
            return "usage unknown or invalid"
    if usage["input_tokens"] > request["input_token_reservation"] or usage["output_tokens"] > MAX_OUTPUT:
        return "token reservation exceeded"
    if usage.get("input_tokens_cache_write", 0):
        return "unexpected billed cache write"
    # The scorer checks normalized action/key validity without inspecting outcome
    # quality. A well-formed unsafe decision must not trigger selection/stopping.
    scores = score_predictions([record]).cases
    if next(c for c in scores if c["case_id"] == record["case_id"])["status"] != "valid":
        return "invalid normalized decision"
    return None


def run(directory, adapter_factory=None):
    directory = Path(directory).resolve()
    plan = read_json_object(directory / "plan.json")
    package = Path(__file__).resolve().parent
    for name, digest in plan["source_sha256"].items():
        if hashlib.sha256((package / name).read_bytes()).hexdigest() != digest:
            raise ValueError("run from the frozen source snapshot; code hash differs: %s" % name)
    if plan["models"] != MODEL_CONFIGS or plan["suite_sha256"] != SUITE_SHA256 or plan["case_ids"] != balanced_case_ids():
        raise ValueError("pilot plan differs from frozen protocol")
    if plan["decision_interface"] != "inspect-null-only-unkeyed-v2":
        raise ValueError("pilot interface mismatch")
    # Atomically claim a single run. Interrupted or failed attempts are not replayed.
    run_dir = directory / "run"
    run_dir.mkdir()
    if adapter_factory is None:
        from .inspect_adapter import InspectAdapter
        adapter_factory = InspectAdapter
    visible = {c["case_id"]: c for c in public_cases()}
    ledger = {p: Decimal(0) for p in MODEL_CONFIGS}
    predictions = {p: [] for p in MODEL_CONFIGS}
    stop = None
    write_json(run_dir / "authorization.json", {"caps_usd": plan["authorized_caps_usd"],
               "plan_sha256": canonical_json_sha256(plan), "started_at_utc": now()})
    with ExitStack() as stack:
        adapters = {p: stack.enter_context(adapter_factory(c["model"], max_output_tokens=MAX_OUTPUT,
                    reasoning_effort="none", timeout=45, model_args=c["model_args"], cache_prompt=False,
                    null_only_unkeyed=True))
                    for p, c in MODEL_CONFIGS.items()}
        write_json(run_dir / "adapter-settings.json", {p: a.settings for p, a in adapters.items()})
        for request in plan["request_plan"]:
            p, cid = request["provider"], request["case_id"]
            case, config = visible[cid], MODEL_CONFIGS[p]
            bound, amount = reserve(case, config)
            if request["input_token_reservation"] != bound or Decimal(request["reserved_usd"]) != amount:
                raise ValueError("reservation tampered")
            if ledger[p] + amount > Decimal(plan["authorized_caps_usd"][p]):
                stop = "provider budget exhausted: " + p
                break
            ledger[p] += amount
            write_json(run_dir / "pending.json", {**request, "started_at_utc": now()})
            write_json(run_dir / "ledger.json", {"reserved_usd": {k: str(v) for k, v in ledger.items()}})
            raw = adapters[p](case)
            record = {**raw, "case_id": cid, "suite": SUITE, "suite_sha256": SUITE_SHA256,
                      "transcript_sha256": case["transcript_sha256"], "collected_at_utc": now(),
                      "budget_reservation_usd": str(amount)}
            # Persist original provider output before any audit or normalization.
            dest = run_dir / p
            dest.mkdir(exist_ok=True)
            with (dest / "predictions.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                handle.flush()
            predictions[p].append(record)
            (run_dir / "pending.json").unlink()
            stop = audit_record(record, request, config)
            print(json.dumps({"provider": p, "attempted": len(predictions[p]),
                              "status": record.get("status"), "audit": stop or "passed"}), flush=True)
            if stop:
                break
    summaries = {}
    for p, records in predictions.items():
        result = score_predictions(records, model=MODEL_CONFIGS[p]["model"], settings=adapters[p].settings)
        dest = run_dir / p
        dest.mkdir(exist_ok=True)
        write_json(dest / "report.json", result.report)
        write_jsonl(dest / "case-scores.jsonl", result.cases)
        selected = [c for c in result.cases if c["case_id"] in plan["case_ids"]]
        usage_cost = sum((Decimal(r["usage"]["input_tokens"]) * Decimal(MODEL_CONFIGS[p]["input_per_million"])
                          + Decimal(r["usage"]["output_tokens"]) * Decimal(MODEL_CONFIGS[p]["output_per_million"])) / Decimal(1000000)
                         for r in records if isinstance(r.get("usage", {}).get("input_tokens"), int)
                         and isinstance(r.get("usage", {}).get("output_tokens"), int))
        summaries[p] = {"attempted": len(records), "planned_diagnostic_cases": len(plan["case_ids"]),
                        "status_counts": dict(Counter(c["status"] for c in selected)),
                        "raw_calls_retained": sum(bool(r.get("raw_provider_response_available")) for r in records),
                        "reserved_usd": str(ledger[p]), "uncached_usage_cost_upper_estimate_usd": str(usage_cost),
                        "note": "This selected diagnostic is not a full-suite score; full report retains all 240 planned slots."}
    summary = {"status": "passed" if stop is None and all(len(r) == 24 for r in predictions.values()) else "stopped",
               "stop_reason": stop, "finished_at_utc": now(), "providers": summaries,
               "plan_sha256": canonical_json_sha256(plan)}
    write_json(run_dir / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--openai-cap", type=Decimal)
    parser.add_argument("--anthropic-cap", type=Decimal)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.openai_cap is None or args.anthropic_cap is None:
            parser.error("prepare requires separate authorized provider caps")
        result = prepare(args.directory, {"openai": args.openai_cap, "anthropic": args.anthropic_cap})
        print(json.dumps({"directory": str(args.directory), "reservations": result["total_reserved_usd"]}))
    else:
        result = run(args.directory)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "passed" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
