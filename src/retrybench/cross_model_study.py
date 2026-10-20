"""Frozen full-suite collection with rolling, fail-closed budget admission."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import shutil

from .cross_model_pilot import MODEL_CONFIGS, MAX_OUTPUT, now, reserve
from .evaluation import SUITE, SUITE_SHA256, public_cases, score_predictions
from .serialization import canonical_json_sha256, read_json_object, write_json, write_jsonl

SEED = 2026101901
TOTAL_CAPS = {"openai": "5", "anthropic": "2"}


def request_order():
    ids = [c["case_id"] for c in public_cases()]
    random.Random(SEED).shuffle(ids)
    return ids


def usage_cost(record, config):
    usage = record.get("usage") or {}
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
        return None
    return (Decimal(usage["input_tokens"]) * Decimal(config["input_per_million"])
            + Decimal(usage["output_tokens"]) * Decimal(config["output_per_million"])) / Decimal(1000000)


class Budget:
    """One serial pending request; unknown usage never releases its reserve."""
    def __init__(self, caps, prior):
        self.caps = {p: Decimal(str(v)) for p, v in caps.items()}
        self.charged = {p: Decimal(str(v)) for p, v in prior.items()}
        self.pending = None
        for p in self.caps:
            if not self.caps[p].is_finite() or not self.charged[p].is_finite() or not 0 <= self.charged[p] < self.caps[p]:
                raise ValueError("invalid budget")

    def admit(self, provider, amount):
        if self.pending is not None or not amount.is_finite() or amount <= 0:
            raise ValueError("invalid/pending reservation")
        if self.charged[provider] + amount > self.caps[provider]:
            return False
        self.charged[provider] += amount
        self.pending = (provider, amount)
        return True

    def settle(self, actual=None):
        provider, amount = self.pending
        if actual is not None:
            if not actual.is_finite() or actual < 0:
                raise ValueError("invalid actual cost")
            if actual > amount:
                self.charged[provider] += actual - amount
                self.pending = None
                raise ValueError("usage exceeds reserved cost; stop immediately")
            self.charged[provider] += actual - amount
        self.pending = None

    def to_dict(self):
        return {"caps_usd": {p: str(v) for p, v in self.caps.items()},
                "charged_or_reserved_usd": {p: str(v) for p, v in self.charged.items()},
                "pending": [self.pending[0], str(self.pending[1])] if self.pending else None}


def prepare(directory, prior_runs):
    directory = Path(directory)
    if directory.exists():
        raise ValueError("refusing to replace frozen study")
    prior = {p: Decimal(0) for p in MODEL_CONFIGS}
    evidence = []
    for old in prior_runs:
        path = Path(old) / "run/summary.json"
        data = read_json_object(path)
        for p in prior:
            prior[p] += Decimal(data["providers"][p]["reserved_usd"])
        evidence.append({"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    Budget(TOTAL_CAPS, prior)
    directory.mkdir(parents=True)
    package = Path(__file__).resolve().parent
    shutil.copytree(package, directory / "source/retrybench", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    snapshot = directory / "source/retrybench"
    ids = request_order()
    plan = {
        "schema_version": "retrybench-cross-model-full-v1", "suite": SUITE,
        "suite_sha256": SUITE_SHA256, "decision_interface": "inspect-null-only-unkeyed-v2",
        "created_at_utc": now(), "models": MODEL_CONFIGS, "case_ids": ids, "order_seed": SEED,
        "planned_requests": 480, "fresh_responses_per_model": 240, "outcomes_per_model": 480,
        "total_authorized_caps_usd": TOTAL_CAPS,
        "prior_retained_reservations_usd": {p: str(v) for p, v in prior.items()},
        "prior_run_evidence": evidence,
        "generation": {"max_output_tokens": MAX_OUTPUT, "reasoning_effort": "none", "temperature": None,
                       "cache_prompt": False, "timeout_seconds": 45},
        "source_sha256": {str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(snapshot.rglob("*")) if p.is_file()},
        "budget_policy": "Before every serial call reserve 2*(public input JSON bytes+4096) input tokens plus 512 output tokens. Reconcile new completed calls to uncached usage-price upper estimates. Unknown charges retain full reservations. Prior pilot reservations remain charged. Stop before exceeding either cumulative cap; completion is not guaranteed.",
        "stopping": "No retries or replacements. Stop all calls on transport/auth, missing raw response, unexpected model, unknown usage, cache-write, or token/cost envelope failure. Retain malformed/truncated model decisions as invalid and continue; do not stop based on safety/performance outcomes.",
        "scope": "Fresh full public-suite evaluation after diagnostic schema selection. Reused public prompts; no held-out/general-model claim; no pooling with pilot or paper studies.",
        "analysis": "Exact case-level FRP, permitted progress, validity, missingness bounds, and hidden-world recovery metrics. Report each block/condition/task separately. Shared worlds and repeated prompts are not independent task-population observations. No post-hoc leaderboard or performance-based filtering.",
        "pricing_checked": "2026-10-19",
    }
    write_json(directory / "plan.json", plan)
    write_jsonl(directory / "cases.jsonl", public_cases())
    return plan


def infrastructure_error(record, input_bound, config):
    if record.get("status") == "adapter_error":
        return "provider/transport error"
    if record.get("returned_model") != config["returned_model"]:
        return "returned model mismatch"
    if not record.get("raw_provider_response_available") or len(record.get("raw_calls", [])) != 1:
        return "raw response missing or multiple calls"
    if usage_cost(record, config) is None:
        return "usage unknown"
    usage = record["usage"]
    if usage["input_tokens"] > input_bound or usage["output_tokens"] > MAX_OUTPUT:
        return "token envelope exceeded"
    if usage.get("input_tokens_cache_write", 0):
        return "unexpected cache-write charge"
    return None


def run(directory, adapter_factory=None):
    directory = Path(directory).resolve()
    plan = read_json_object(directory / "plan.json")
    package = Path(__file__).resolve().parent
    if (plan["case_ids"] != request_order() or plan["models"] != MODEL_CONFIGS
            or plan["total_authorized_caps_usd"] != TOTAL_CAPS or plan["suite_sha256"] != SUITE_SHA256
            or plan["decision_interface"] != "inspect-null-only-unkeyed-v2"):
        raise ValueError("frozen plan mismatch")
    for name, h in plan["source_sha256"].items():
        if hashlib.sha256((package / name).read_bytes()).hexdigest() != h:
            raise ValueError("use frozen source snapshot: " + name)
    prior = {p: Decimal(0) for p in MODEL_CONFIGS}
    for item in plan["prior_run_evidence"]:
        if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("prior accounting changed")
        previous = read_json_object(Path(item["path"]))
        for p in prior:
            prior[p] += Decimal(previous["providers"][p]["reserved_usd"])
    if prior != {p: Decimal(v) for p, v in plan["prior_retained_reservations_usd"].items()}:
        raise ValueError("prior reservations mismatch")
    run_dir = directory / "run"
    run_dir.mkdir()  # no automatic resume, overwrite, or uncertain replay
    budget = Budget(plan["total_authorized_caps_usd"], plan["prior_retained_reservations_usd"])
    visible = {c["case_id"]: c for c in public_cases()}
    records = {p: [] for p in MODEL_CONFIGS}
    costs = {p: Decimal(0) for p in MODEL_CONFIGS}
    unknown = {p: Decimal(0) for p in MODEL_CONFIGS}
    stop = None
    if adapter_factory is None:
        from .inspect_adapter import InspectAdapter
        adapter_factory = InspectAdapter
    with ExitStack() as stack:
        adapters = {p: stack.enter_context(adapter_factory(c["model"], max_output_tokens=MAX_OUTPUT,
                    reasoning_effort="none", timeout=45, model_args=c["model_args"], cache_prompt=False,
                    null_only_unkeyed=True)) for p, c in MODEL_CONFIGS.items()}
        write_json(run_dir / "adapter-settings.json", {p: a.settings for p, a in adapters.items()})
        for cid in plan["case_ids"]:
            for provider, config in MODEL_CONFIGS.items():
                case = visible[cid]
                bound, amount = reserve(case, config)
                if not budget.admit(provider, amount):
                    stop = "budget limit: " + provider
                    break
                write_json(run_dir / "ledger.json", budget.to_dict())
                write_json(run_dir / "pending.json", {"provider": provider, "case_id": cid,
                           "reserved_usd": str(amount), "started_at_utc": now()})
                try:
                    raw = adapters[provider](case)
                except Exception as exc:
                    raw = {"status": "adapter_error", "error_type": type(exc).__name__}
                row = {**raw, "case_id": cid, "suite": SUITE, "suite_sha256": SUITE_SHA256,
                       "transcript_sha256": case["transcript_sha256"], "collected_at_utc": now(),
                       "input_token_reservation": bound, "budget_reservation_usd": str(amount)}
                dest = run_dir / provider
                dest.mkdir(exist_ok=True)
                with (dest / "predictions.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                    handle.flush()
                records[provider].append(row)
                stop = infrastructure_error(row, bound, config)
                actual = usage_cost(row, config) if stop is None else None
                if actual is None:
                    unknown[provider] += amount
                else:
                    costs[provider] += actual
                try:
                    budget.settle(actual)
                except ValueError as exc:
                    stop = str(exc)
                write_json(run_dir / "ledger.json", budget.to_dict())
                (run_dir / "pending.json").unlink()
                print(json.dumps({"provider": provider, "attempted": len(records[provider]),
                                  "status": row.get("status"), "cost_upper_usd": str(costs[provider]),
                                  "audit": stop or "passed"}), flush=True)
                if stop:
                    break
            if stop:
                break
    providers = {}
    for p, rows in records.items():
        result = score_predictions(rows, model=MODEL_CONFIGS[p]["model"], settings=adapters[p].settings)
        dest = run_dir / p
        dest.mkdir(exist_ok=True)
        write_json(dest / "report.json", result.report)
        write_jsonl(dest / "case-scores.jsonl", result.cases)
        providers[p] = {"attempted": len(rows), "planned": 240,
                        "status_counts": result.report["metrics"]["status_counts"],
                        "cost_upper_estimate_usd": str(costs[p]), "unknown_cost_reserved_usd": str(unknown[p]),
                        "raw_calls_retained": result.report["raw_capture"]["provider_response_available"]}
    summary = {"status": "collected" if stop is None and all(len(r) == 240 for r in records.values()) else "stopped",
               "stop_reason": stop, "plan_sha256": canonical_json_sha256(plan), "providers": providers,
               "finished_at_utc": now(), "budget": budget.to_dict()}
    write_json(run_dir / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--prior-run", type=Path, action="append", default=[])
    args = parser.parse_args()
    result = prepare(args.directory, args.prior_run) if args.command == "prepare" else run(args.directory)
    print(json.dumps(result, indent=2))
    if args.command == "run" and result["status"] != "collected":
        raise SystemExit(2)
