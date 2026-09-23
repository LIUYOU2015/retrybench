# Cross-model decision: conditional full-paper gate

The second fixed snapshot replicated the primary direction within the four
studied task families. This supports continuing toward a full research paper,
but the evidence package is not complete and does not establish a
task-population, task-invariant, or model-invariant claim.

| Fixed snapshot | Weak neutral false permission | Authoritative neutral false permission | Difference | Weak neutral duplicates | Task directions |
|---|---:|---:|---:|---:|---|
| GPT-5.4 Mini (`gpt-5.4-mini-2026-03-17`) | 51/60 (85%) | 3/60 (5%) | +80 points | 34/60 | 4 weak-higher |
| GPT-5.4 (`gpt-5.4-2026-03-05`) | 30/60 (50%) | 0/60 (0%) | +50 points | 20/60 | 2 weak-higher, 2 ties |

The 60 outcome pairs per condition are not independent: the primary neutral
weak condition contains 20 model responses, each replayed across three hidden
schedules. Outcome-level McNemar values are therefore retained only as
descriptive diagnostics and must not be used as headline inference.

At the task×repetition response-block level, GPT-5.4 Mini has 17/20 weak blocks
with any false retry versus 3/20 authoritative blocks: 14 weak-only, zero
authoritative-only, three both, and three neither. GPT-5.4 has 10/20 versus
0/20: 10 weak-only, zero authoritative-only, and 10 neither. The corresponding
exact values (`0.000122` and `0.001953`) are still descriptive because the 20
blocks are nested within four task families.

Using task family as the top-level sampling unit, Mini's equal-task rate
difference is +0.80 with a four-cluster t interval bounded to approximately
`[+0.35, +1.00]`. GPT-5.4's difference is +0.50 with an interval of
approximately `[-0.42, +1.00]`. The latter includes zero. Four clusters yield
unstable, low-powered intervals, so the paper must show task-specific effects
and obtain independent task-template evidence before generalizing.

The result supports this bounded statement: across two fixed model snapshots,
weak negative evidence increased unsafe retry permission relative to
authoritative evidence under matched prompts and schedules. It does not show
that every task wording triggers the effect. GPT-5.4 retried weak evidence for
the issue and release tasks but not the CI and review tasks, whereas GPT-5.4
Mini showed the weak-higher direction for all four.

The cautious prompt is a safety-only baseline, not a complete solution. For
both snapshots it eliminated weak-evidence retries, but all 60 weak outcomes
remained unresolved and 20/60 became omissions. The useful contribution is
therefore the retry-admissibility boundary and executable conformance suite,
not the advice to always avoid retrying.

The full-paper decision is **conditionally passed, pending task robustness**.
The combined evidence is 320 fresh model calls and 480 scored outcomes, plus
the actual LangGraph contract audit. The next robustness block must use frozen
independent task templates and wording counterbalancing. Another model
leaderboard cell is lower priority until that task sensitivity is explained.

GPT-5.4 replication cost was $0.222605. Confirmation plus replication cost
$0.286592; total tracked project API spend is $0.33131525. Raw provider records
remain ignored locally. The checked-in replication outcomes are sanitized and
their SHA-256 is
`c2c40fe5a061638ab915ec3cf75c90039976cc44ee43d5b6d0c835105f6aec52`.
