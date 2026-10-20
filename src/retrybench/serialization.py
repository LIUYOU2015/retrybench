"""Deterministic JSON readers, writers, and hashes used across RetryBench."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


def canonical_json_sha256(value: object) -> str:
    """Hash a value using RetryBench's canonical JSON representation."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    """Read one JSON object and reject non-object top-level values."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: %s" % path)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read non-empty JSONL lines as objects, preserving file order."""
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    "expected JSON object on line %d: %s" % (line_number, path)
                )
            rows.append(value)
    return rows


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    """Write stable, human-readable JSON with one trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    """Write stable JSONL, creating parent directories when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
