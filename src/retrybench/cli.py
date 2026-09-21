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
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
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
