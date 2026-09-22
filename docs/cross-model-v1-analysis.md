# Cross-model decision: pursue the full paper, with heterogeneity explicit

The second fixed snapshot replicated the primary direction. This clears the
project's breadth gate for continuing toward a full research paper, but it does
not support a task-invariant or model-invariant claim.

| Fixed snapshot | Weak neutral false permission | Authoritative neutral false permission | Difference | Weak neutral duplicates | Task directions |
|---|---:|---:|---:|---:|---|
| GPT-5.4 Mini (`gpt-5.4-mini-2026-03-17`) | 51/60 (85%) | 3/60 (5%) | +80 points | 34/60 | 4 weak-higher |
| GPT-5.4 (`gpt-5.4-2026-03-05`) | 30/60 (50%) | 0/60 (0%) | +50 points | 20/60 | 2 weak-higher, 2 ties |

For GPT-5.4, all 30 discordant pairs favored weak evidence and none favored
authoritative evidence. The descriptive paired exact McNemar value is
`1.86e-9`; it is not an independent-sample significance claim because one weak
response is shared across three hidden schedules. All integrity gates passed.

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

The full-paper decision is **GO, with heterogeneity**. The combined evidence is
now 320 fresh model calls and 480 scored outcomes, plus the actual LangGraph
contract audit. The next robustness block should be frozen independent task
templates and wording counterbalancing. Another model leaderboard cell or a
second framework adapter is lower priority until that task sensitivity is
explained.

GPT-5.4 replication cost was $0.222605. Confirmation plus replication cost
$0.286592; total tracked project API spend is $0.33131525. Raw provider records
remain ignored locally. The checked-in replication outcomes are sanitized and
their SHA-256 is
`c2c40fe5a061638ab915ec3cf75c90039976cc44ee43d5b6d0c835105f6aec52`.
