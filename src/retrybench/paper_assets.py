"""Generate paper tables and figures from checked-in machine-readable evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.sax.saxutils import escape


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: %s" % path)
    return value


def _percent(value: float) -> str:
    return "%.1f\\%%" % (100.0 * value)


def _ratio(row: Mapping[str, Any], field: str) -> str:
    return "%d/%d" % (int(row[field]), int(row["episodes"]))


def _neutral_row(analysis: Mapping[str, Any], evidence: str) -> Mapping[str, Any]:
    return next(
        row
        for row in analysis["by_evidence_and_prompt"]
        if row["evidence"] == evidence and row["prompt_condition"] == "neutral"
    )


def model_results_table(mini: Mapping[str, Any], full: Mapping[str, Any]) -> str:
    lines = [
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        r"Model & Weak FRP & Auth. FRP & $\Delta$ & Weak-only blocks & Task mean $\Delta$ & Task 95\% CI \\",
        r"\midrule",
    ]
    for label, analysis in (("GPT-5.4 Mini", mini), ("GPT-5.4", full)):
        weak = _neutral_row(analysis, "weak")
        auth = _neutral_row(analysis, "authoritative")
        clustered = analysis["clustered_primary_false_retry_analysis"]
        block = clustered["response_block_level"]
        task = clustered["task_family_level"]
        interval = task["task_cluster_t_95_interval_bounded_to_rate_difference"]
        lines.append(
            "%s & %d/%d & %d/%d & %s & %d/%d & %s & [%s, %s] \\\\"
            % (
                label,
                weak["false_retry_permission"],
                weak["outcomes"],
                auth["false_retry_permission"],
                auth["outcomes"],
                _percent(
                    weak["false_retry_permission_rate"]
                    - auth["false_retry_permission_rate"]
                ),
                block["weak_only"],
                block["blocks"],
                _percent(task["equal_task_weight_mean_rate_difference"]),
                _percent(interval[0]),
                _percent(interval[1]),
            )
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            "% FRP = false retry permission. Hidden-schedule outcomes sharing one response are not independent samples.",
        ]
    )
    return "\n".join(lines) + "\n"


def closest_work_table(analysis: Mapping[str, Any]) -> str:
    source = analysis["source_faithful"]["by_control"]
    extension = analysis["retrybench_extension"]["by_policy"]
    rows = (
        ("Source", "Prompt-only stop", source["prompt_only_stop"]),
        ("Source", "Prompt-only retry", source["prompt_only_retry"]),
        ("Source", "Authoritative status", source["authoritative_status_reconcile"]),
        ("Source", "Stable idempotency", source["stable_idempotency_retry"]),
        ("Extended", "Negative status as permission", extension["negative_status_as_retry_permission"]),
        ("Extended", "Terminal-aware status", extension["terminal_aware_status_reconcile"]),
        ("Extended", "Stable idempotency", extension["stable_idempotency_retry"]),
    )
    lines = [
        r"\begin{tabular}{llrr}",
        r"\toprule",
        r"World set & Recovery contract & Exact state & Rate \\",
        r"\midrule",
    ]
    for world, contract, row in rows:
        lines.append(
            "%s & %s & %d/%d & %s \\\\"
            % (
                world,
                contract,
                row["exact_state_successes"],
                row["episodes"],
                _percent(row["exact_state_rate"]),
            )
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines) + "\n"


def framework_table(
    langgraph: Mapping[str, Any], langchain: Mapping[str, Any]
) -> str:
    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"\toprule",
        r"Framework & Policy & Completed & Retries & Duplicates & Unresolved & Exact state \\",
        r"\midrule",
    ]
    specs = (
        (langgraph, "LangGraph", "graph_completed"),
        (langchain, "LangChain Core", "runnable_completed"),
    )
    policy_labels = {
        "no_retry": "No retry",
        "langgraph_default_retry_policy": "Exception retry",
        "langchain_exception_retry": "Exception retry",
        "stable_idempotency_retry": "Stable idempotency",
    }
    for report, framework, completed_field in specs:
        for policy, row in report["by_policy"].items():
            lines.append(
                "%s & %s & %s & %d & %d & %d & %d/%d \\\\"
                % (
                    framework,
                    policy_labels[policy],
                    _ratio(row, completed_field),
                    row["retries"],
                    row["duplicates"],
                    row["unresolved"],
                    row["exact_state_success"],
                    row["episodes"],
                )
            )
        lines.append(r"\addlinespace")
    lines[-1] = r"\bottomrule"
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


def _x(value: float, left: float, width: float) -> float:
    return left + value * width


def robustness_svg(analysis: Mapping[str, Any]) -> str:
    effects = list(analysis["task_family_effects"])
    lexical = {
        row["family_id"]: row
        for row in analysis["lexical_counterbalance"]["family_effects"]
    }
    width, height = 1120, 650
    left_a, plot_width = 180.0, 340.0
    left_b = 730.0
    top, gap = 120.0, 52.0
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
        % (width, height, width, height),
        '<rect x="0" y="0" width="1120" height="650" fill="white"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#17212b}.title{font-size:22px;font-weight:700}.panel{font-size:17px;font-weight:700}.label{font-size:14px}.tick{font-size:12px;fill:#4b5563}.axis{stroke:#9ca3af;stroke-width:1}.grid{stroke:#e5e7eb;stroke-width:1}.effect{fill:#2563eb}.mean{fill:#dc2626}.create{fill:#7c3aed}.noncreate{fill:#059669}.pair{stroke:#94a3b8;stroke-width:2}</style>',
        '<text x="40" y="38" class="title">Task-family robustness and lexical moderation</text>',
        '<text x="40" y="72" class="panel">A  Weak − authoritative false-retry-permission rate</text>',
        '<text x="590" y="72" class="panel">B  Matched weak-evidence rates by tool-name frame</text>',
    ]
    for left in (left_a, left_b):
        for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
            xpos = _x(tick, left, plot_width)
            parts.append(
                '<line x1="%.1f" y1="92" x2="%.1f" y2="555" class="grid"/>'
                % (xpos, xpos)
            )
            parts.append(
                '<text x="%.1f" y="580" text-anchor="middle" class="tick">%.2g</text>'
                % (xpos, tick)
            )
        parts.append(
            '<line x1="%.1f" y1="555" x2="%.1f" y2="555" class="axis"/>'
            % (left, left + plot_width)
        )
    for index, row in enumerate(effects):
        y = top + index * gap
        family = escape(str(row["family_id"]))
        parts.append(
            '<text x="168" y="%.1f" text-anchor="end" class="label">%s</text>'
            % (y + 5, family)
        )
        parts.append(
            '<circle cx="%.1f" cy="%.1f" r="6" class="effect"/>'
            % (_x(float(row["rate_difference"]), left_a, plot_width), y)
        )
        pair = lexical[str(row["family_id"])]
        x_non = _x(float(pair["noncreate_rate"]), left_b, plot_width)
        x_create = _x(float(pair["create_rate"]), left_b, plot_width)
        parts.append(
            '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" class="pair"/>'
            % (x_non, y, x_create, y)
        )
        parts.append('<circle cx="%.1f" cy="%.1f" r="6" class="noncreate"/>' % (x_non, y))
        parts.append('<circle cx="%.1f" cy="%.1f" r="6" class="create"/>' % (x_create, y))

    mean = float(analysis["equal_family_mean_rate_difference"])
    low, high = analysis["task_cluster_t_95_interval_bounded"]
    y_mean = 532.0
    parts.append(
        '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#dc2626" stroke-width="4"/>'
        % (_x(low, left_a, plot_width), y_mean, _x(high, left_a, plot_width), y_mean)
    )
    mx = _x(mean, left_a, plot_width)
    parts.append(
        '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" class="mean"/>'
        % (mx, y_mean - 9, mx + 9, y_mean, mx, y_mean + 9, mx - 9, y_mean)
    )
    parts.append('<text x="168" y="537" text-anchor="end" class="label">Mean (95% t CI)</text>')
    parts.append('<circle cx="735" cy="615" r="6" class="noncreate"/><text x="748" y="620" class="label">non-create frame</text>')
    parts.append('<circle cx="900" cy="615" r="6" class="create"/><text x="913" y="620" class="label">create frame</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def generate_paper_assets(repo_root: Path, output_dir: Path) -> list[Path]:
    mini = _load(repo_root / "runs/confirmation-v2/analysis.json")
    full = _load(repo_root / "runs/gpt54-replication-v1/analysis.json")
    robustness = _load(repo_root / "runs/task-robustness-v1/analysis.json")
    closest = _load(repo_root / "runs/closest-work-v1/analysis.json")
    langgraph = _load(repo_root / "runs/langgraph-v1/summary.json")
    langchain = _load(repo_root / "runs/langchain-v1/summary.json")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "table-model-results.tex": model_results_table(mini, full),
        "table-closest-work.tex": closest_work_table(closest),
        "table-framework-audits.tex": framework_table(langgraph, langchain),
        "figure-task-robustness.svg": robustness_svg(robustness),
    }
    paths = []
    for name, content in outputs.items():
        path = output_dir / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths
