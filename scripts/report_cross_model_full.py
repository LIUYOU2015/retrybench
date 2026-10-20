"""Generate a descriptive full-suite comparison from audited local artifacts."""

import argparse
from decimal import Decimal
import json
from pathlib import Path


def ratio(metric):
    text = "%d/%d" % (metric["count"], metric["planned_denominator"])
    if metric["unknown"]:
        text += " (%d unknown)" % metric["unknown"]
    return text


def report(directory, output):
    directory = Path(directory)
    plan = json.loads((directory / "plan.json").read_text())
    summary = json.loads((directory / "run/summary.json").read_text())
    verified = json.loads((directory / "verification.json").read_text())
    if not verified["verified"] or summary["status"] != "collected":
        raise ValueError("requires an audited completed collection")
    reports = {p: json.loads((directory / "run" / p / "report.json").read_text()) for p in plan["models"]}
    names = {"openai": "GPT-5.4 mini (2026-03-17)", "anthropic": "Claude Sonnet 4.6"}
    lines = ["# Full public-suite cross-model comparison — 2026-10-19", "",
             "This collection obtained 240 fresh responses per endpoint, replayed over 480 compatible hidden-world outcomes per endpoint. It uses the public `retry-permission-v1` suite and the explicitly versioned `inspect-null-only-unkeyed-v2` tool interface. Pilot responses are not pooled into these results.", "",
             "## First-decision results", "",
             "Counts below use planned denominators. Unknowns are retained, not counted as safe. Permitted progress has 80 opportunities per model.", "",
             "| Endpoint | Valid decisions | Observed unsupported retries (FRP) | Permitted progress |",
             "|---|---:|---:|---:|"]
    for p, r in reports.items():
        m = r["metrics"]
        lines.append("| %s | %s | %s | %s |" % (names[p], ratio(m["protocol_validity"]), ratio(m["false_retry_permission"]), ratio(m["permitted_progress"])))
    lines += ["", "| Endpoint | FRP among known decisions | Conservative planned FRP bounds |", "|---|---:|---:|"]
    for p, r in reports.items():
        m = r["metrics"]["false_retry_permission"]
        rate = "unknown" if m["rate_among_known"] is None else "%.2f%%" % (100 * m["rate_among_known"])
        bounds = "%.2f%%–%.2f%%" % tuple(100 * x for x in m["planned_rate_bounds"])
        lines.append("| %s | %s | %s |" % (names[p], rate, bounds))
    lines += ["", "## Blocks and conditions", "",
              "The evidence block uses short neutral/cautious label prompts. The supplied-key block includes explicit contracts. Their aggregates measure different interfaces and should be interpreted separately.", "",
              "| Block | GPT FRP | Claude FRP | GPT progress | Claude progress |", "|---|---:|---:|---:|---:|"]
    for block in reports["openai"]["per_block"]:
        a, b = reports["openai"]["per_block"][block], reports["anthropic"]["per_block"][block]
        lines.append("| %s | %s | %s | %s | %s |" % (block, ratio(a["false_retry_permission"]), ratio(b["false_retry_permission"]), ratio(a["permitted_progress"]), ratio(b["permitted_progress"])))
    lines += ["", "| Condition | GPT FRP | Claude FRP | GPT valid | Claude valid |", "|---|---:|---:|---:|---:|"]
    for condition in reports["openai"]["per_condition"]:
        a, b = reports["openai"]["per_condition"][condition], reports["anthropic"]["per_condition"][condition]
        lines.append("| %s | %s | %s | %s | %s |" % (condition, ratio(a["false_retry_permission"]), ratio(b["false_retry_permission"]), ratio(a["protocol_validity"]), ratio(b["protocol_validity"])))
    lines += ["", "## Recovery outcomes", "",
              "These denominators are hidden-world outcomes, not independent model responses. Omissions and unresolved outcomes can overlap.", "",
              "| Endpoint | Exact state | Duplicates | Omissions | Unresolved |", "|---|---:|---:|---:|---:|"]
    for p, r in reports.items():
        m = r["metrics"]["outcomes"]
        lines.append("| %s | %s | %s | %s | %s |" % (names[p], *(ratio(m[k]) for k in ("exact_state_success", "duplicate_effect", "omission", "unresolved"))))
    lines += ["", "## Cost and collection settings", "",
              "| Provider | This run: usage-based upper estimate | Including both pilots | Authorized cap |", "|---|---:|---:|---:|"]
    for p in reports:
        fresh = Decimal(summary["providers"][p]["cost_upper_estimate_usd"])
        previous = sum((Decimal(json.loads(Path(e["path"]).read_text())["providers"][p]["uncached_usage_cost_upper_estimate_usd"]) for e in plan["prior_run_evidence"]), Decimal(0))
        lines.append("| %s | $%s | $%s | $%s |" % (p, fresh, fresh + previous, plan["total_authorized_caps_usd"][p]))
    lines += ["", "Estimates use returned token usage at uncached standard rates; they are not invoice or account-balance verification. Sources: [OpenAI pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini) and [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), checked on the collection date.", "",
              "Generation: 512 output-token cap, reasoning effort `none`, temperature unset, prompt-cache writes disabled, forced single decision tool, no tool execution. OpenAI uses Responses with `store=false` and default service tier. Both SDK and Inspect retries are disabled. A fixed seeded shuffle orders cases; providers are interleaved serially. Provider defaults may still differ.", "",
              "New calls reserve conservative text input/output envelopes before dispatch, then reconcile known usage. Unknown charges retain their reserves; the earlier pilot reserves remain charged in the admission ledger. Infrastructure failures stop collection; model validity or safety outcomes do not trigger retries, repairs, or early stopping.", "",
              "## Interpretation and scope", "",
              "These are descriptive results for two selected endpoints, four reused software tasks, public prompts, and one recovery decision. They are not estimates of production failure rates, general model superiority, or held-out generalization. Repeated prompt draws and shared execution worlds are not independent task-population samples. Missingness bounds are not confidence intervals. No pooled paper estimate, significance claim, or leaderboard rank is produced.", "",
              "The v2 output schema was selected after a pilot exposed an invalid non-null key on an evidence-only case. That original failed attempt and the subsequent diagnostic remain separate. Each of the 240 cases was freshly queried for this full collection, including cases previously seen in the pilot; this is not an unseen-prompt evaluation.", "",
              "## Reproducibility", "",
              "Plan SHA-256: `%s`." % summary["plan_sha256"], "",
              "Suite SHA-256: `%s`." % plan["suite_sha256"], "",
              "Local artifacts: `%s/` contains the plan, case export, frozen source, dependency lock, execution log, per-provider raw predictions and scores, budget ledger, and independent `verification.json`." % directory, "",
              "The offline verifier checked native tool arguments, raw token usage, returned model identity, budget admission/reconciliation, and exact reproduction of all case scores and report metrics. No inference is used for rescoring.", "",
              "```bash", "PYTHONPATH=src python3 scripts/verify_cross_model_pilot.py %s" % directory, "```", "",
              "This report and artifacts are local. No public release, manuscript change, or leaderboard publication is implied.", ""]
    Path(output).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report(args.directory, args.output)
