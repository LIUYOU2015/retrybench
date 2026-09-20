"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
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
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
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

