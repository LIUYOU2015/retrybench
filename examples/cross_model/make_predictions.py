"""Create a complete synthetic JSONL fixture from exported visible cases."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("cases", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
rows = [json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open("x", encoding="utf-8") as output:
    for case in rows:
        output.write(json.dumps({
            "schema_version": "retrybench-prediction-v1",
            **{k: case[k] for k in ("case_id", "suite", "suite_sha256", "transcript_sha256")},
            "action": "unresolved", "arguments": {"idempotency_key": None},
            "raw_response": {"fixture": "always-defer; synthetic"},
        }, sort_keys=True) + "\n")
