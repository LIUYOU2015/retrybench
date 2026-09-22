# Frozen GPT-5.4 replication plan

This block replicates confirmation-v2 with the fixed `gpt-5.4-2026-03-05`
snapshot. It changes the model only. The prompts, schedules, evidence contracts,
task templates, repetitions, response-sharing rule, scoring, and analysis remain
fixed.

The run contains 160 fresh API responses and 240 scored hidden-schedule
outcomes. Weak-evidence responses are replayed across the three matched hidden
schedules. Authoritative cases are singletons because their observed state can
differ by schedule.

The primary contrast is neutral weak versus neutral authoritative false-retry
permission. Interpretation also includes duplicate effects, omissions,
unresolved outcomes, exact-state success, raw discordance, task-direction
consistency, token usage, and cost. The analysis has no post-hoc significance
threshold.

The expected bill is about $0.21329 using confirmation-v2 token counts and the
official GPT-5.4 rates. The conservative byte-based reservation is $0.7956. The
run cap is $0.85; added to $0.10871025 already tracked, the maximum cumulative
amount remains $0.95871025, below the user's $1 check-in threshold.

Run `retrybench replication-preflight` before inference. A paid run requires
`--execute-paid-replication`; raw provider results remain ignored under
`results/`. Analyze with `retrybench analyze-replication` and publish only the
sanitized outcomes and aggregate report.

Pricing and snapshot support were verified against the official
[GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4) on
September 22, 2026.
