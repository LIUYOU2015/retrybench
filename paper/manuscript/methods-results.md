# Methods and Results Draft

Working title: **When Is a Retry Safe? Benchmarking Retry Admissibility Under
Ambiguous LLM Agent Tool Outcomes**

This draft intentionally begins with Methods and Results. The Introduction and
Abstract remain unwritten until the empirical narrative, claim boundary, and
limitations have stabilized. Bracketed evidence identifiers resolve to exact
files and JSON Pointers in [`evidence-ledger.json`](evidence-ledger.json); a
test fails if any recorded value diverges from the committed artifact.

## 3. Method

### 3.1 Research questions

We study four questions:

- **RQ1 — Evidence contract:** How does weak negative evidence, relative to
  authoritative state evidence, change an LLM agent's permission to retry and
  the resulting safety/liveness trade-off?
- **RQ2 — Generality and moderation:** Does the weak-evidence effect persist
  across fixed model snapshots and independently introduced task families, and
  how strongly is it moderated by tool-name framing?
- **RQ3 — Closest-work boundary:** Which conclusion from the closest public
  benchmark changes when nonterminal in-flight and stale-visibility schedules
  are added without selecting tasks from RetryBench results?
- **RQ4 — Runtime enforcement:** Do real framework retry boundaries enforce
  external-effect retry admissibility, and which additional contract closes
  any observed gap?

### 3.2 Retry admissibility

RetryBench treats retry as a permission question rather than merely an action
label. A non-idempotent retry is permitted only when evidence establishes that
the earlier attempt is both terminal and effect-free. In the implemented
contract this is the conjunction of the `FAIL_BEFORE_EXECUTION` schedule, an
authoritative evidence contract, and the observed state `NOT_EXECUTED`.
Alternatively, replay may be safe under a provider-enforced stable idempotency
guarantee. All other cases are forbidden or unresolved: a missing object under
a weak evidence contract does not prove that an earlier attempt cannot still
commit.

The primary metric, **false retry permission**, marks a decision that chooses
retry without either form of permission. We report it separately from exact
final-state success, duplicate effects, omissions, and unresolved outcomes.
This separation prevents an always-stop policy from appearing successful only
because it creates no duplicates, and prevents a successfully returned retry
wrapper from hiding an incorrect external state.

### 3.3 Hidden execution schedules and evidence contracts

The local service implements four hidden schedules. In
`FAIL_BEFORE_EXECUTION`, the original attempt is terminal and effect-free. In
`COMMIT_THEN_DROP_RESPONSE`, it commits before its response is lost. In
`IN_FLIGHT_LATE_COMMIT`, it remains nonterminal at the decision point and
commits after recovery begins. In `STALE_NEGATIVE_AFTER_COMMIT`, it has
committed but the first weak lookup remains negative. Every schedule initially
returns the same timeout.

Evidence has three declared contracts. `none` exposes no state evidence.
`weak` may return `NOT_FOUND`, but that value does not establish terminal
non-execution. `authoritative` distinguishes `NOT_EXECUTED`, `IN_FLIGHT`, and
`COMMITTED`. Schedule labels and ground truth never enter model input.

The original pilot crossed four software-engineering tasks, four schedules,
three evidence contracts, two prompt conditions, and one draw, for 96 model
episodes [M1]. The tasks create an issue, post a review comment, trigger CI,
and create a release. Exact-state scoring checks operation identity, task,
tool, target, payload, multiplicity, and unresolved status rather than only
counting whether some effect exists.

### 3.4 Counterfactual response replay

The confirmatory design isolates interpretation from hidden execution truth by
replaying one model response across schedules when its visible input is byte
identical. Within each task, prompt condition, and fresh draw, the weak
`NOT_FOUND` response is shared across `FAIL_BEFORE_EXECUTION`,
`IN_FLIGHT_LATE_COMMIT`, and `STALE_NEGATIVE_AFTER_COMMIT`. Authoritative
transcripts are not shared across those worlds because their observed states
differ.

For each model block, four tasks, three schedules, two evidence contracts, two
prompt conditions, and five fresh draws produce 240 scored outcomes from 160
fresh model calls [M2]. Forty weak responses generate 120 counterfactual
outcomes; 120 authoritative responses each generate one outcome. The 96 pilot
episodes are exploratory and excluded from confirmatory denominators.

### 3.5 Model conditions

The first frozen block uses `gpt-5.4-mini-2026-03-17`; the second is a separate
replication using `gpt-5.4-2026-03-05`. Both use structured decisions with the
actions retry, stop, wait, or unresolved and a maximum of 256 output tokens
[M2]. The neutral prompt supplies the task, timeout, evidence contract, and
observed state without caution-specific advice. The cautious prompt explicitly
requires evidence before replaying a side effect. We report snapshots rather
than product-family names to avoid implying stability across later releases.

### 3.6 Independent-task robustness and lexical counterbalance

After observing cross-model task heterogeneity, we froze a separate GPT-5.4
block before inference. It contains eight new semantic task families, each
implemented through two matched tool-name frames: one begins with `create_`
and one uses a non-create verb. Within a pair, target and payload are identical;
all task identifiers, tools, targets, and payloads are disjoint from the
original four tasks. Two draws per frame yield 128 fresh calls and 192 scored
outcomes under the same weak-response sharing rule [M3].

Task family is the top-level generalization unit. The preregistered stronger
empirical path requires at least six of eight families to have a positive
weak-minus-authoritative effect and the lower bound of the task-cluster 95%
t interval to exceed zero. The create-minus-non-create contrast is explanatory
and was not part of that venue decision threshold.

### 3.7 Closest-work reproduction and extension

We directly exercise the public artifact for *Did It Happen?* rather than
selecting examples from its paper. RetryBench verifies source commit
`4b626e7cde61ec9275a30e23982d146ee6f4e65d`, input hashes, and the six template
identifiers that the source authors placed in their own replication subset.
The slice covers create-once, ordered-transition, and reserve-then-link state
topologies, with two tasks per family.

The source-faithful block invokes the upstream simulator over its two original
hidden worlds and its prompt-only, authoritative-status, and stable-idempotency
controls. The extension preserves task text, logical references, and
family-specific exact-state semantics, then adds in-flight late commit and
stale negative visibility. Its three policies treat negative status as retry
permission, require terminal-aware status, or replay with stable idempotency.
This is a deterministic construct-validity test, not a rerun of the upstream
paper's model-dependent aggregate study.

### 3.8 Framework audits

We execute two real runtime boundaries. The LangGraph audit uses
`langgraph==0.6.11` and an opt-in node `RetryPolicy`; the LangChain audit uses
`langchain-core==0.3.86` and `RunnableLambda.with_retry`. Each crosses the four
base tasks with four schedules and three policies—no retry, bounded exception
retry, and the same retry boundary with stable idempotency—for 48 deterministic
episodes per framework. The audits test the boundary between exception
eligibility and external-effect replay permission; they are not defect claims
against either framework.

### 3.9 Analysis units and uncertainty

The model response is the independent sampling unit within a frozen visible
condition. The three outcomes produced by replaying one weak response are
correlated counterfactuals, not three independent model samples. We therefore
report outcome rates for operational interpretation, response-block
discordance after collapsing the three schedules, and task-specific effects.
For task-population generalization we use task family as the top-level unit and
a two-sided t interval over family effects.

Outcome-level exact McNemar values are retained only as descriptive diagnostics.
They are not headline inferential evidence because standard McNemar inference
would treat schedule-expanded pairs as independent. Deterministic closest-work
and framework episodes have no sampling uncertainty; we report exact counts
and scope boundaries rather than p-values.

### 3.10 Reproducibility and audit trail

Manifests were frozen before paid execution, runners refuse mismatched model or
output-token settings, completed response groups are resumable without
repeating calls, and sanitized evidence is hash-bound. Current experiment
runners use explicit logical advancement for the in-flight schedule so machine
load cannot settle an operation before the frozen first observation.

Paid data were collected before that logical-clock hardening. We therefore
performed a read-only retrospective audit of 768 output rows against the
preserved SQLite ledgers. It covers 248 in-flight rows, of which 240 have
state-sensitive weak or authoritative observations; all passed with zero
early-settlement contradictions. Eight pilot `none`-evidence rows cannot reveal
exact decision-time ordering because `UNKNOWN` is timing-insensitive, but their
final effect counts are invariant to settlement ordering and match the ledger
[R10]. The historical schema did not retain operation start time and cleared
`due_at` on settlement, so we do not claim a reconstructable numeric timing
margin.

Two noninferential corrections are preserved in the audit trail. First, the
closest-work weak/not-executed row now records `WEAK_NOT_FOUND` rather than a
terminal label; policy actions and aggregates are unchanged. Second, an initial
source-control expectation incorrectly assumed prompt-only stop would reach
50% across all topologies. The upstream reserve-then-link topology additionally
requires a downstream link, so the corrected check uses the upstream artifact's
pre-existing per-family best-of-stop/retry control. Neither correction changes
the selected tasks, primary estimand, extension schedules, or observed outcomes.

## 4. Results

### 4.1 RQ1: Weak negative evidence increased false retry permission

The exploratory pilot established conclusion sensitivity but is not pooled
with later blocks. Across its 96 episodes, it recorded 24 false retry
permissions, 18 duplicate effects, 10 omissions, and 48 unresolved outcomes at
an API cost of $0.0401565 [R1]. These results motivated the reduced frozen
confirmation design.

In GPT-5.4 Mini, the neutral weak condition produced 51 false retry permissions
in 60 outcomes (85%), compared with 3/60 (5%) under authoritative evidence, an
80 percentage-point difference. At the response-block level, 14 of 20 blocks
were weak-only discordances and none were authoritative-only. The equal-task
mean difference was 0.80; the four-task 95% t interval was [0.350, 1.000] [R2].

The direction replicated in GPT-5.4, although at a smaller and more
task-dependent magnitude. Neutral weak evidence produced 30/60 false retry
permissions (50%), while authoritative evidence produced 0/60. Ten of 20
response blocks were weak-only and none were authoritative-only. The equal-task
mean was 0.50, but the four-task interval was [-0.419, 1.000], reflecting two
positive task effects and two ties rather than contradictory directions [R3].
Table `table-model-results.tex` reports these contrasts with the correct
analysis units.

Safety did not imply task completion. Under cautious weak evidence, both model
blocks made zero false retry permissions, but all 60 outcomes were unresolved
and the 20 terminal pre-execution failures became omissions [R4][R5]. Thus a
fail-closed prompt removed unsafe replay at the cost of complete liveness loss
in this condition. The result supports separate safety and liveness reporting,
not a claim that caution alone solves recovery.

**Answer to RQ1.** In both fixed snapshots, replacing authoritative state
evidence with a weak negative observation materially increased false retry
permission under neutral prompting. Cautious prompting avoided unsafe retries
but did so by refusing to resolve every weak-evidence outcome.

### 4.2 RQ2: The effect generalized across new families, with lexical moderation

The preregistered robustness block met the stronger empirical criterion. All
eight independent task families had a positive weak-minus-authoritative
effect. The equal-family mean difference was 0.625, with an eight-family 95%
t interval of [0.402, 0.848] [R6]. This closes the specific uncertainty left by
the four-task GPT-5.4 replication: the effect was not confined to the two
original create-oriented tasks.

Magnitude nevertheless remained heterogeneous. In the matched lexical
contrast, create-prefixed tools exceeded non-create frames by 0.50 on average
[R6]. Family-level weak-minus-authoritative effects ranged from 0.25 to 1.00,
and create-minus-non-create contrasts ranged from 0 to 1.00. Figure
`figure-task-robustness.svg` shows every family and matched lexical pair rather
than only the aggregate.

**Answer to RQ2.** The weak-negative effect generalized in direction across all
eight new GPT-5.4 task families under the frozen design, while tool-name
framing materially moderated its magnitude. We therefore claim task-family
generality for the tested block, not task-invariant behavior or a complete
causal account of the lexical effect.

### 4.3 RQ3: The closest-work status conclusion became conditional

The source-faithful controls reproduced on the author-selected slice. Across 48
upstream-simulator episodes, authoritative status reconciliation and stable
idempotency each reached exact state in 12/12 episodes. The upstream
no-affordance best action remained 50% within every structural family [R7].

Adding in-flight and stale-negative worlds changed only the weak-status
interpretation. Treating negative status as retry permission reached exact
state in 12/24 extension episodes (50%). Its 12 failures occurred exclusively
in the added worlds: six in-flight late commits and six stale negative reads.
Terminal-aware status and stable-idempotency replay each reached 24/24 exact
state [R7]. Table `table-closest-work.tex` reports the source and extension
controls side by side.

**Answer to RQ3.** The closest work's status benefit remains valid inside its
authoritative two-world contract. What changes is the generalization: a
negative lookup improves recovery only when its semantics establish terminal
non-execution, or when replay is independently protected. The extension is a
scope qualification, not a refutation of the upstream result.

### 4.4 RQ4: Framework completion did not guarantee correct external state

The LangGraph exception-retry configuration retried all 16 ambiguous
side-effect episodes, produced duplicate effects in 12, and completed in exact
state in 0/16 because the graph exhausted its attempts unresolved. Stable
idempotency produced no duplicates and reached exact state in 16/16 [R8].

LangChain exposed a different manifestation of the same contract boundary.
Its exception-retry runnable reported completion in 16/16 episodes, yet 12 had
duplicate external effects and only 4/16 reached exact state. Stable
idempotency again reached exact state in 16/16 without duplicates [R9]. Table
`table-framework-audits.tex` reports both runtimes and their no-retry controls.

**Answer to RQ4.** In two tested framework/version configurations, exception
eligibility was insufficient to authorize external-effect replay. LangChain
additionally demonstrates that a successful framework return can coexist with
an incorrect external state. Stable provider-enforced operation identity closed
the tested gap in both runtimes.

### 4.5 Result boundary

Together, the results support a bounded empirical claim: weak negative evidence
increased false retry permission in two fixed model snapshots and across eight
independently introduced GPT-5.4 task families; the magnitude depended on task
and lexical framing. Deterministic reproduction and two runtime audits identify
the contract boundary: evidence must establish terminal non-execution, or a
valid stable-idempotency guarantee must make replay safe.

The study does not estimate the prevalence of delayed or stale states in
production, prove exactly-once execution for arbitrary providers, establish a
new general impossibility theorem, or show that the tested frameworks are
defective. Those claims exceed both the design and the evidence.

## Artifact references used in this draft

- Model table: [`../generated/table-model-results.tex`](../generated/table-model-results.tex)
- Robustness figure: [`../generated/figure-task-robustness.svg`](../generated/figure-task-robustness.svg)
- Closest-work table: [`../generated/table-closest-work.tex`](../generated/table-closest-work.tex)
- Framework table: [`../generated/table-framework-audits.tex`](../generated/table-framework-audits.tex)
- Claim ledger: [`evidence-ledger.json`](evidence-ledger.json)
