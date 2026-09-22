"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, Type, TypeVar

from .benchmark import run_matrix
from .metrics import summarize
from .model import EvidenceContract, PolicyName, Schedule, TASKS

EnumT = TypeVar("EnumT")


def _values(enum_type: Type[EnumT], selected: Iterable[str]):
    values = list(selected)
    return [enum_type(value) for value in values] if values else list(enum_type)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="retrybench")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run the deterministic benchmark matrix")
    run.add_argument("--output", default="results/episodes.jsonl")
    run.add_argument("--summary", default="results/summary.json")
    run.add_argument("--policies", nargs="*", choices=[item.value for item in PolicyName])
    run.add_argument("--evidence", nargs="*", choices=[item.value for item in EvidenceContract])
    run.add_argument("--schedules", nargs="*", choices=[item.value for item in Schedule])
    smoke = subparsers.add_parser("openai-smoke", help="run a cost-bounded live-model smoke test")
    smoke.add_argument("--output", default="results/openai-smoke.jsonl")
    smoke.add_argument("--model", default="gpt-5.4-mini-2026-03-17")
    smoke.add_argument("--max-episodes", type=int, default=10)
    smoke.add_argument("--max-cost-usd", type=float, default=0.25)
    smoke.add_argument("--max-output-tokens", type=int, default=256)
    serve = subparsers.add_parser(
        "serve", help="run the persistent local fault-injection service"
    )
    serve.add_argument("--database", default="results/retrybench.sqlite3")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--late-commit-delay", type=float, default=1.0)
    preflight = subparsers.add_parser(
        "preflight", help="run the zero-cost pilot readiness gates"
    )
    preflight.add_argument(
        "--manifest", default="protocol/pilot-manifest-v1.jsonl"
    )
    preflight.add_argument(
        "--report", default="protocol/preflight-report-v1.json"
    )
    pilot = subparsers.add_parser(
        "pilot", help="execute the frozen paid pilot after an explicit spend decision"
    )
    pilot.add_argument("--manifest", default="protocol/pilot-manifest-v1.jsonl")
    pilot.add_argument("--output", default="results/live-pilot.jsonl")
    pilot.add_argument("--summary", default="results/live-pilot-summary.json")
    pilot.add_argument("--database", default="results/live-pilot.sqlite3")
    pilot.add_argument("--max-cost-usd", type=float, default=2.0)
    pilot.add_argument("--execute-paid-pilot", action="store_true")
    analyze = subparsers.add_parser(
        "analyze-pilot", help="sanitize and aggregate the completed frozen pilot"
    )
    analyze.add_argument("--input", default="results/live-pilot.jsonl")
    analyze.add_argument(
        "--preflight", default="protocol/preflight-report-v1.json"
    )
    analyze.add_argument(
        "--outcomes", default="runs/pilot-v1/sanitized-outcomes.jsonl"
    )
    analyze.add_argument("--report", default="runs/pilot-v1/analysis.json")
    confirmation_preflight = subparsers.add_parser(
        "confirmation-preflight", help="freeze and audit confirmation-v2 without API calls"
    )
    confirmation_preflight.add_argument(
        "--manifest", default="protocol/confirmation-v2-manifest.jsonl"
    )
    confirmation_preflight.add_argument(
        "--report", default="protocol/confirmation-v2-preflight.json"
    )
    confirmation = subparsers.add_parser(
        "confirmation", help="execute frozen confirmation-v2 after explicit approval"
    )
    confirmation.add_argument(
        "--manifest", default="protocol/confirmation-v2-manifest.jsonl"
    )
    confirmation.add_argument("--output", default="results/live-confirmation-v2.jsonl")
    confirmation.add_argument("--database", default="results/live-confirmation-v2.sqlite3")
    confirmation.add_argument("--max-cost-usd", type=float, default=1.0)
    confirmation.add_argument("--execute-paid-confirmation", action="store_true")
    replication_preflight = subparsers.add_parser(
        "replication-preflight", help="freeze and audit the GPT-5.4 replication without API calls"
    )
    replication_preflight.add_argument(
        "--manifest", default="protocol/gpt54-replication-manifest-v1.jsonl"
    )
    replication_preflight.add_argument(
        "--report", default="protocol/gpt54-replication-preflight-v1.json"
    )
    replication = subparsers.add_parser(
        "replication", help="execute the frozen GPT-5.4 replication"
    )
    replication.add_argument(
        "--manifest", default="protocol/gpt54-replication-manifest-v1.jsonl"
    )
    replication.add_argument("--output", default="results/live-gpt54-replication-v1.jsonl")
    replication.add_argument("--database", default="results/live-gpt54-replication-v1.sqlite3")
    replication.add_argument("--max-cost-usd", type=float, default=0.85)
    replication.add_argument("--execute-paid-replication", action="store_true")
    replication.add_argument("--resume", action="store_true")
    export_cases = subparsers.add_parser(
        "export-cases", help="export model-facing confirmation cases without hidden schedules"
    )
    export_cases.add_argument(
        "--manifest", default="protocol/confirmation-v2-manifest.jsonl"
    )
    export_cases.add_argument("--output", default="results/public-cases-v1.jsonl")
    score_decisions = subparsers.add_parser(
        "score-decisions", help="score external actions against frozen hidden schedules"
    )
    score_decisions.add_argument(
        "--manifest", default="protocol/confirmation-v2-manifest.jsonl"
    )
    score_decisions.add_argument("--decisions", required=True)
    score_decisions.add_argument("--output", default="results/external-scores-v1.jsonl")
    score_decisions.add_argument("--summary", default="results/external-summary-v1.json")
    analyze_confirmation = subparsers.add_parser(
        "analyze-confirmation", help="sanitize and analyze the completed confirmation-v2 block"
    )
    analyze_confirmation.add_argument(
        "--input", default="results/live-confirmation-v2.jsonl"
    )
    analyze_confirmation.add_argument(
        "--preflight", default="protocol/confirmation-v2-preflight.json"
    )
    analyze_confirmation.add_argument(
        "--outcomes", default="runs/confirmation-v2/sanitized-outcomes.jsonl"
    )
    analyze_confirmation.add_argument(
        "--report", default="runs/confirmation-v2/analysis.json"
    )
    analyze_replication = subparsers.add_parser(
        "analyze-replication", help="sanitize and analyze the GPT-5.4 replication"
    )
    analyze_replication.add_argument(
        "--input", default="results/live-gpt54-replication-v1.jsonl"
    )
    analyze_replication.add_argument(
        "--preflight", default="protocol/gpt54-replication-preflight-v1.json"
    )
    analyze_replication.add_argument(
        "--outcomes", default="runs/gpt54-replication-v1/sanitized-outcomes.jsonl"
    )
    analyze_replication.add_argument(
        "--report", default="runs/gpt54-replication-v1/analysis.json"
    )
    langgraph_audit = subparsers.add_parser(
        "langgraph-audit", help="run the offline LangGraph retry-contract audit"
    )
    langgraph_audit.add_argument(
        "--outcomes", default="runs/langgraph-v1/outcomes.jsonl"
    )
    langgraph_audit.add_argument(
        "--report", default="runs/langgraph-v1/summary.json"
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "langgraph-audit":
        from .external import write_jsonl
        from .langgraph_adapter import run_langgraph_audit, summarize_langgraph_audit

        rows = run_langgraph_audit()
        report = summarize_langgraph_audit(rows)
        write_jsonl(Path(args.outcomes), (row.to_dict() for row in rows))
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.command in {"analyze-confirmation", "analyze-replication"}:
        from .confirmation_analysis import (
            analyze_confirmation,
            load_jsonl,
            write_analysis,
            write_sanitized,
        )

        rows = load_jsonl(Path(args.input))
        preflight = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
        report = analyze_confirmation(
            rows,
            preflight,
            analysis_context=(
                "replication" if args.command == "analyze-replication" else "confirmation"
            ),
        )
        outcomes_hash = write_sanitized(Path(args.outcomes), rows)
        write_analysis(Path(args.report), report, outcomes_hash)
        print(json.dumps({
            "scored_outcomes": report["scored_outcomes"],
            "fresh_model_calls": report["fresh_model_calls"],
            "actual_cost_usd": report["actual_cost_usd"],
            "integrity": report["integrity"],
            "outcomes": args.outcomes,
            "report": args.report,
        }, indent=2, sort_keys=True))
        return 0 if all(report["integrity"].values()) else 1

    if args.command == "replication-preflight":
        from .confirmation import write_confirmation_manifest
        from .replication import build_replication_manifest, run_replication_preflight

        rows = build_replication_manifest()
        report = run_replication_preflight(rows)
        write_confirmation_manifest(Path(args.manifest), rows)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["all_zero_cost_gates_passed"] else 1

    if args.command == "replication":
        from .confirmation import load_confirmation_manifest
        from .openai_adapter import CostBudget, OpenAIResponsesPolicy
        from .replication import (
            REPLICATION_MAX_COST_USD,
            REPLICATION_MODEL,
            run_live_replication,
        )

        if not args.execute_paid_replication:
            raise SystemExit("paid replication requires --execute-paid-replication")
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is not set")
        if args.max_cost_usd <= 0 or args.max_cost_usd > REPLICATION_MAX_COST_USD:
            raise SystemExit(
                "--max-cost-usd must be greater than 0 and no more than %.2f"
                % REPLICATION_MAX_COST_USD
            )
        rows = load_confirmation_manifest(Path(args.manifest))
        policy = OpenAIResponsesPolicy(model=REPLICATION_MODEL)
        budget = CostBudget(args.max_cost_usd)
        results = run_live_replication(
            rows,
            policy,
            budget,
            Path(args.database),
            Path(args.output),
            resume=args.resume,
        )
        print(json.dumps({
            "scored_outcomes": len(results),
            "api_requests": budget.requests,
            "actual_cost_usd": budget.spent_usd,
            "output": args.output,
        }, indent=2, sort_keys=True))
        return 0

    if args.command == "export-cases":
        from .confirmation import load_confirmation_manifest
        from .external import export_public_cases, write_jsonl

        cases = export_public_cases(load_confirmation_manifest(Path(args.manifest)))
        write_jsonl(Path(args.output), cases)
        print(json.dumps({"cases": len(cases), "output": args.output}, indent=2))
        return 0

    if args.command == "score-decisions":
        from .confirmation import load_confirmation_manifest
        from .external import (
            load_external_decisions,
            score_external_decisions,
            summarize_external,
            write_jsonl,
        )

        rows = load_confirmation_manifest(Path(args.manifest))
        decisions = load_external_decisions(Path(args.decisions))
        results = score_external_decisions(rows, decisions)
        summary = summarize_external(results)
        write_jsonl(Path(args.output), results)
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "confirmation-preflight":
        from .confirmation import (
            build_confirmation_manifest,
            run_confirmation_preflight,
            write_confirmation_manifest,
        )

        rows = build_confirmation_manifest()
        report = run_confirmation_preflight(rows)
        write_confirmation_manifest(Path(args.manifest), rows)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["all_zero_cost_gates_passed"] else 1

    if args.command == "confirmation":
        from .confirmation import (
            CONFIRMATION_MAX_COST_USD,
            load_confirmation_manifest,
            run_live_confirmation,
        )
        from .openai_adapter import CostBudget, OpenAIResponsesPolicy

        if not args.execute_paid_confirmation:
            raise SystemExit("paid confirmation requires --execute-paid-confirmation")
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is not set")
        if args.max_cost_usd <= 0 or args.max_cost_usd > CONFIRMATION_MAX_COST_USD:
            raise SystemExit(
                "--max-cost-usd must be greater than 0 and no more than %.2f"
                % CONFIRMATION_MAX_COST_USD
            )
        rows = load_confirmation_manifest(Path(args.manifest))
        policy = OpenAIResponsesPolicy()
        budget = CostBudget(args.max_cost_usd)
        results = run_live_confirmation(
            rows, policy, budget, Path(args.database), Path(args.output)
        )
        print(json.dumps({
            "scored_outcomes": len(results),
            "api_requests": budget.requests,
            "actual_cost_usd": budget.spent_usd,
            "output": args.output,
        }, indent=2, sort_keys=True))
        return 0

    if args.command == "analyze-pilot":
        from .analysis import (
            analyze_pilot,
            load_jsonl,
            write_analysis,
            write_sanitized,
        )

        rows = load_jsonl(Path(args.input))
        preflight = json.loads(Path(args.preflight).read_text(encoding="utf-8"))
        report = analyze_pilot(rows, preflight)
        outcomes_hash = write_sanitized(Path(args.outcomes), rows)
        write_analysis(Path(args.report), report, outcomes_hash)
        print(
            json.dumps(
                {
                    "decision": report["decision"],
                    "pilot_cells": report["pilot_cells"],
                    "actual_cost_usd": report["actual_cost_usd"],
                    "all_empirical_novelty_gates_passed": report[
                        "all_empirical_novelty_gates_passed"
                    ],
                    "outcomes": args.outcomes,
                    "report": args.report,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if report["all_empirical_novelty_gates_passed"] else 1

    if args.command == "preflight":
        from .experiment import (
            build_pilot_manifest,
            run_zero_cost_preflight,
            write_manifest,
            write_report,
        )

        rows = build_pilot_manifest()
        report = run_zero_cost_preflight(rows)
        write_manifest(Path(args.manifest), rows)
        write_report(Path(args.report), report)
        print(
            json.dumps(
                {
                    "api_requests_made": report["api_requests_made"],
                    "pilot_cells": report["pilot_cells"],
                    "maximum_reserved_cost_usd": report[
                        "maximum_reserved_cost_usd"
                    ],
                    "spend_decision": report["spend_decision"],
                    "manifest": args.manifest,
                    "report": args.report,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if report["all_zero_cost_gates_passed"] else 1

    if args.command == "pilot":
        from .experiment import (
            PILOT_MAX_COST_USD,
            load_manifest,
            run_live_pilot,
            summarize_live_pilot,
        )
        from .openai_adapter import CostBudget, OpenAIResponsesPolicy

        if not args.execute_paid_pilot:
            raise SystemExit("paid pilot requires --execute-paid-pilot")
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is not set")
        if args.max_cost_usd <= 0 or args.max_cost_usd > PILOT_MAX_COST_USD:
            raise SystemExit(
                "--max-cost-usd must be greater than 0 and no more than %.2f"
                % PILOT_MAX_COST_USD
            )
        summary_path = Path(args.summary)
        if summary_path.exists():
            raise SystemExit("pilot summary already exists: %s" % summary_path)
        rows = load_manifest(Path(args.manifest))
        budget = CostBudget(args.max_cost_usd)
        policy = OpenAIResponsesPolicy()
        results = run_live_pilot(
            rows,
            policy,
            budget,
            Path(args.database),
            Path(args.output),
        )
        summary = summarize_live_pilot(results, budget)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "serve":
        from .http_service import RetryBenchHTTPService

        service = RetryBenchHTTPService(
            database_path=Path(args.database),
            host=args.host,
            port=args.port,
            late_commit_delay=args.late_commit_delay,
        )
        print(
            json.dumps(
                {
                    "base_url": service.base_url,
                    "database": str(Path(args.database)),
                    "late_commit_delay": args.late_commit_delay,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        try:
            service.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0

    if args.command == "openai-smoke":
        from .live import run_live_smoke, smoke_cases
        from .openai_adapter import CostBudget, OpenAIResponsesPolicy

        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("OPENAI_API_KEY is not set")
        if args.max_episodes < 1 or args.max_episodes > 10:
            raise SystemExit("--max-episodes must be between 1 and 10 for the smoke command")
        budget = CostBudget(args.max_cost_usd)
        policy = OpenAIResponsesPolicy(
            model=args.model,
            max_output_tokens=args.max_output_tokens,
        )
        rows = run_live_smoke(policy, budget, smoke_cases()[: args.max_episodes])
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "smoke_only": True,
                    "episodes": len(rows),
                    "model": args.model,
                    "actual_cost_usd": budget.spent_usd,
                    "output": str(output),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command != "run":  # pragma: no cover
        raise AssertionError("unreachable")

    rows = list(
        run_matrix(
            tasks=TASKS,
            schedules=_values(Schedule, args.schedules or []),
            evidence_contracts=_values(EvidenceContract, args.evidence or []),
            policies=_values(PolicyName, args.policies or []),
        )
    )
    output = Path(args.output)
    summary_path = Path(args.summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
    summary = summarize(rows)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
