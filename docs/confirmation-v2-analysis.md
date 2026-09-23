# RetryBench confirmation-v2 analysis

Run date: 2026-09-21

Model: `gpt-5.4-mini-2026-03-17`

Design: 4 tasks × 3 schedules × 2 evidence contracts × 2 prompts × 5 fresh draws

Completed: 160/160 fresh model calls; 240/240 scored outcomes

API cost: $0.063987

## Integrity

All frozen integrity checks passed: 240 unique outcomes, exactly 160 response groups, valid zero-cost preflight, and identical response ID/action/transcript within every shared-response group. Each weak `NOT_FOUND` response was replayed across fail-before-execution, in-flight late commit, and stale-negative-after-commit schedules. Pilot outcomes were excluded.

## Primary result

Under neutral prompting, weak evidence produced 51/60 false retry permissions (85%) versus 3/60 (5%) under authoritative evidence:

- absolute difference: **+80 percentage points**;
- risk ratio: **17.0**;
- raw paired discordance: 48 weak-only, 0 authoritative-only, 3 both, 9 neither;
- outcome-level exact McNemar diagnostic = `7.1054e-15` (**descriptive only; not valid headline inference**).

The outcome-level McNemar value is not inferential evidence because the same weak response is reused across three schedules. Collapsing each task × fresh-draw block to whether any schedule has a false retry permission gives 17/20 weak blocks and 3/20 authoritative blocks: 14 weak-only, 0 authoritative-only, 3 both, and 3 neither. The block-level exact diagnostic is `0.000122`, but the 20 blocks remain nested in only four task families.

With task family as the top-level sampling unit, the equal-task rate difference is +0.80, the task-cluster standard error is `0.1414`, and the four-cluster t interval is approximately `[+0.35, +1.00]` after bounding to the rate-difference scale. With only four clusters this interval is unstable; the task-specific effects and raw block discordance are primary, and no task-population p-value is claimed.

All four task templates have higher neutral false-retry counts under weak evidence. Differences are +12 for CI, +15 for issue creation, +15 for release creation, and +6 for review comments.

## Safety/liveness boundary

| Evidence | Prompt | Outcomes | False retry | Duplicates | Omissions | Unresolved | Exact state |
|---|---|---:|---:|---:|---:|---:|---:|
| Weak | Neutral | 60 | 51 | 34 | 3 | 9 | 17 |
| Weak | Cautious | 60 | 0 | 0 | 20 | 60 | 0 |
| Authoritative | Neutral | 60 | 3 | 3 | 0 | 21 | 36 |
| Authoritative | Cautious | 60 | 4 | 4 | 0 | 21 | 35 |

Neutral weak decisions retried in 17/20 fresh response groups. Those same decisions recover the 17 fail-before-execution outcomes but create 17 duplicates in the in-flight schedule and 17 in the stale-visibility schedule. Cautious guidance eliminates weak-evidence retries, but every weak outcome remains unresolved and all 20 fail-before-execution outcomes become omissions.

Authoritative state substantially improves the frontier but does not guarantee model compliance. The model waits in all 40 authoritative in-flight outcomes and retries all 40 authoritative non-execution outcomes across prompts, yet it incorrectly retries 7/40 committed outcomes. Cautious guidance does not reduce these authoritative committed-state violations.

## Full-paper decision

**Historical decision: GO to the next full-paper gate.** Confirmation-v2 turns the pilot observation into a repeated, shared-response result with a large effect, consistent direction across four task templates, and an explicit safety/liveness boundary. It supports the claim that evidence semantics determine retry admissibility and that prompt advice alone does not implement a safe recovery policy. After the second-model block, the current overall decision is a conditional full-paper gate pending independent task robustness.

It does not yet complete a full research paper. The next required evidence is:

1. one mainstream framework or SDK adapter showing that RetryBench exposes an actual recovery-contract failure or ranking change;
2. a contract-enforcing runtime baseline under the same visible evidence and budget;
3. one independently frozen second-model block;
4. a direct comparison/reproduction slice showing what in-flight and stale-visibility schedules change relative to the closest paired-world benchmark.

If the framework integration reveals no real contract problem, reposition the work as a strong tool/evaluation paper rather than claiming broad practical prevalence.

## Reproducibility

- Sanitized outcomes SHA-256: `4383572b216d9f94065ab364b8c46c2734bc15f70f868cdf88cff5be6cf87127`
- Raw JSONL SHA-256 (kept local): `0ddd655fbcb2f20b6115372413ef04de697b8ed02ab38ad250bcea5cec684735`
- Raw SQLite SHA-256 (kept local): `faa5abbf14adeb583553be4afd85f025cd67c5deef4d5f34ad3471a8661cbded`
- Analyzer was frozen in commit `a33186a` before the first paid request.

## Limitations

- One fixed model snapshot and four task templates.
- Five serving draws are not five independent tasks.
- Shared responses induce within-block dependence by design.
- Controlled schedules do not estimate production frequency or name a provider with weak semantics.
- At this confirmation-only stage, framework behavior and cross-model replication were untested; both were added later, while independent task robustness remains open.
