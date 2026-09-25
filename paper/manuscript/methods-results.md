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
  across fixed model snapshots and a new, disjoint set of task families, and
  how sensitive is its magnitude to tool-name framing?
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
guarantee. Otherwise a non-idempotent retry is not permitted: a policy can stop
when commitment is established, but must wait, reconcile, or escalate when the
attempt remains nonterminal or unknown. A missing object under a weak evidence
contract does not prove that an earlier attempt cannot still commit.

The primary metric, **false retry permission**, marks a decision that chooses
retry without either form of permission. This is a contract-violation metric,
not a count of realized harm: a retry can restore the intended state in the
particular fail-before-execution world while still being unsupported by the
evidence available to the caller. We therefore report it separately from exact
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

### 3.6 New-task robustness and lexical counterbalance

After observing cross-model task heterogeneity, we designed and commit-froze a
separate GPT-5.4 block before executing it. It contains eight new semantic task
families, each
implemented through two matched tool-name frames: one begins with `create_`
and one uses a non-create verb. Within a pair, target and payload are identical;
all task identifiers, tools, targets, and payloads are disjoint from the
original four tasks. The families are hand-designed validation cases rather
than a random sample from a defined task population. Two draws per frame yield
128 fresh calls and 192 scored outcomes under the same weak-response sharing
rule; this block uses reasoning effort `none` and a 160-token output limit [M3].

Task family is the top-level analysis unit. The predeclared, commit-frozen
stronger-paper rule requires at least six of eight families to have a positive
weak-minus-authoritative effect and the lower bound of the task-cluster 95%
t interval to exceed zero. The create-minus-non-create contrast is explanatory
and was not part of that venue decision threshold. After the primary analysis,
we added a labeled post-hoc construct-validity check that recomputes the
weak-minus-authoritative contrast separately within each lexical frame.

### 3.7 Deterministic reference policies

Five zero-cost policies establish that the schedules and scorer expose the
expected safety/liveness frontier: always retry, always stop, a single weak
status check, tri-state verification with backoff, and stable-idempotency
replay. Each policy runs over four tasks, four schedules, and three evidence
contracts, for 48 episodes. These are conformance controls rather than sampled
empirical observations; probe and retry counts measure logical benchmark steps,
not wall-clock or production latency.

### 3.8 Closest-work reproduction and extension

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
This is a deterministic policy/conformance construct-validity test. It samples
no fresh live-model decisions and is not a rerun of the upstream paper's
model-dependent aggregate study.

### 3.9 Framework audits

We execute two real runtime boundaries. The LangGraph audit uses
`langgraph==0.6.11` and an opt-in node `RetryPolicy` with its default exception
predicate and two total attempts; the LangChain audit uses
`langchain-core==0.3.86` and `RunnableLambda.with_retry`, retaining its broad
`Exception` predicate while setting two total attempts and disabling jitter.
Each crosses the four
base tasks with four schedules and three policies—no retry, bounded exception
retry, and the same retry boundary with stable idempotency—for 48 deterministic
episodes per framework. The audits test the boundary between exception
eligibility and external-effect replay permission; they are not defect claims
against either framework.

### 3.10 Analysis units and uncertainty

The model response is the independent sampling unit within a frozen visible
condition. The three outcomes produced by replaying one weak response are
correlated counterfactuals, not three independent model samples. We therefore
report outcome rates for operational interpretation, response-block
discordance after collapsing the three schedules, and task-specific effects.
For variation across tested task families we use task family as the top-level
unit and a two-sided t interval over family effects. Because the families are
hand-designed rather than probability-sampled, this interval summarizes
between-family variation in the tested block; it is not a population-sampling
guarantee for arbitrary software-engineering tools.

Outcome-level exact McNemar values are retained only as descriptive diagnostics.
They are not headline inferential evidence because standard McNemar inference
would treat schedule-expanded pairs as independent. Deterministic closest-work
and framework episodes have no sampling uncertainty; we report exact counts
and scope boundaries rather than p-values.

### 3.11 Reproducibility and audit trail

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

### 4.1 Deterministic controls expose the expected frontier

Always retry reached exact state in 12/48 episodes and produced 36 duplicates;
always stop reached 36/48 but omitted all 12 pre-execution failures. A single
status check reached 24/48 and produced 24 duplicates. Tri-state verification
with backoff produced no duplicates, but reached 28/48 exact states, made 80
probes, omitted eight tasks, and left 20 unresolved. Under the benchmark's
declared stable-deduplication assumption, idempotent replay reached 48/48 exact
states with no duplicates or omissions [R11]. These deterministic controls
show why duplicate avoidance alone is not a complete recovery metric and why
the stable-idempotency result is conditional on its provider contract.

### 4.2 RQ1: Weak negative evidence increased false retry permission

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

### 4.3 RQ2: The effect persisted across the new task block, with lexical sensitivity

The predeclared, commit-frozen robustness block met its stronger-paper rule.
All eight new task families had a positive weak-minus-authoritative
effect. The equal-family mean difference was 0.625, with an eight-family 95%
t interval of [0.402, 0.848] [R6]. This addresses the specific within-study
uncertainty left by the four-task GPT-5.4 replication by broadening the observed
effect beyond the original cases. It does not resolve the heterogeneity: the
within-frame analysis below shows that lexical framing remains associated with
where the effect appears.

Magnitude nevertheless remained heterogeneous. In the matched lexical
contrast, create-prefixed tools exceeded non-create frames by 0.50 on average
[R6]. Family-level weak-minus-authoritative effects ranged from 0.25 to 1.00,
and create-minus-non-create contrasts ranged from 0 to 1.00. Figure
`figure-task-robustness.svg` shows every family and matched lexical pair rather
than only the aggregate.

The post-hoc within-frame check shows that wording does not fully explain away
the evidence contrast. Within create frames, the equal-family
weak-minus-authoritative difference was 0.875 and all 8/8 families were
positive, with a family t interval of [0.681, 1.000]. Within non-create frames,
the mean difference remained positive at 0.375, with an interval of
[0.004, 0.746], but only 4/8 families were positive and four tied [R6]. Thus
evidence authority remains associated with retry permission inside both frames
on average, while lexical framing strongly changes effect consistency and
magnitude. Because this decomposition was requested after the primary result,
we treat it as a construct check rather than confirmatory evidence.

**Answer to RQ2.** The weak-negative effect persisted in direction across all
eight new GPT-5.4 task families under the frozen design. The large matched
create/non-create difference shows lexical sensitivity in these hand-designed
pairs, but two draws per frame do not support a population effect or a complete
causal account. The within-frame check rejects the simplest explanation that
the aggregate evidence effect is solely a create-verb artifact, but it also
shows that the non-create effect is concentrated in half the families. We claim
robustness across the tested block, not task-invariant or population-general
behavior.

### 4.4 RQ3: The closest-work status conclusion became conditional

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
controls side by side. These are deterministic policy outcomes; no live model
was called on the six closest-work tasks.

**Answer to RQ3.** The closest work's status benefit remains valid inside its
authoritative two-world contract. What changes is the generalization: a
negative lookup improves recovery only when its semantics establish terminal
non-execution, or when replay is independently protected. The extension is a
scope qualification, not a refutation of the upstream result.

### 4.5 RQ4: Framework completion did not guarantee correct external state

The LangGraph exception-retry configuration retried all 16 ambiguous
side-effect episodes, produced duplicate effects in 12, and completed in exact
state in 0/16 because the graph exhausted its attempts unresolved. Stable
idempotency produced no duplicates and reached exact state in 16/16 [R8].

LangChain exposed a different manifestation of the same contract boundary.
Its exception-retry runnable reported completion in 16/16 episodes, yet 12 had
duplicate external effects and only 4/16 reached exact state. Stable
idempotency again reached exact state in 16/16 without duplicates [R9]. Table
`table-framework-audits.tex` reports both runtimes and their no-retry controls.

**Answer to RQ4.** In two tested, explicitly configured framework/version
boundaries, exception eligibility was insufficient to authorize external-effect
replay. LangChain
additionally demonstrates that a successful framework return can coexist with
an incorrect external state. The benchmark's simulated, provider-enforced
stable-idempotency contract closed the tested gap in both runtimes; this is a
positive control, not validation of any real provider's guarantee.

### 4.6 Result boundary

Together, the results support a bounded empirical claim: weak negative evidence
increased false retry permission in two fixed model snapshots and persisted
across eight new, disjoint GPT-5.4 task families; the magnitude depended on task
and was sensitive to lexical framing. Deterministic reproduction and two
runtime audits identify the contract boundary: evidence must establish terminal non-execution, or a
valid stable-idempotency guarantee must make replay safe.

The study does not estimate the prevalence of delayed or stale states in
production, prove exactly-once execution for arbitrary providers, establish a
new general impossibility theorem, or show that the tested frameworks are
defective. Those claims exceed both the design and the evidence.

## 5. Discussion

### 5.1 Evidence labels should not double as retry authorization

The central design implication is not that status checks are ineffective. It
is that their semantics must be explicit. `NOT_FOUND` can mean authoritative,
terminal non-execution, temporary invisibility after commitment, or simply that
the lookup surface cannot bind the queried identifier to the original attempt.
Evaluations that collapse those contracts into one status label risk rewarding
a retry that succeeds in one hidden world but duplicates an effect in another.

Counterfactual response replay makes this distinction measurable: one model
decision is held fixed while the future external state changes. The benefit is
causal isolation of the decision from serving variation. The cost is that the
schedule-expanded outcomes are correlated, which is why the response block and
task family—not the expanded row—anchor interpretation.

### 5.2 Retry middleware needs an external-effect boundary

The two framework audits do not imply faulty retry implementations. Both
runtimes execute the policies they were given. The mismatch arises because an
exception predicate answers whether code is eligible to run again, whereas
external-effect admissibility also depends on logical operation identity,
attempt terminality, evidence authority, and replay protection. A useful tool
boundary should therefore carry those fields or require the application to
resolve them before enabling retry.

Stable idempotency is the cleanest tested positive control, but only under a
real guarantee that binds the same logical operation, parameters, retention
window, and deduplication scope. Reusing a key outside that scope, changing the
payload, or relying on client-side memory alone would not inherit the result.

### 5.3 Safe recovery is a frontier, not one score

Always retry restores pre-execution failures but duplicates committed work;
always stop avoids duplicates but omits work that never executed. Cautious
prompting similarly removed false retry permission under weak evidence while
leaving every such confirmatory outcome unresolved. Tri-state backoff occupied
another point on the frontier: no duplicates in the deterministic control, but
additional probes, omissions, and unresolved cases. Benchmarks should therefore
publish exact state, duplicate, omission, unresolved, and recovery-cost metrics
separately instead of hiding policy choices inside one success rate.

### 5.4 Lexical sensitivity is an interface warning, not an explanation

The matched create/non-create result suggests that API naming can change model
risk tolerance even when target and payload are fixed. It does not identify the
mechanism: the model may associate `create_*` with familiar idempotency advice,
respond to imperative morphology, or exploit other wording correlations in the
hand-designed pairs. The post-hoc within-frame check retains a positive average
evidence contrast in each frame, so wording alone does not explain the result;
however, the non-create contrast appears in only half the families. The
practical implication is narrower: benchmark authors should counterbalance
interface wording and show per-family results rather than treating one tool
name as semantically neutral.

### 5.5 Implications for benchmark use

RetryBench is best used as a conformance suite for proposed recovery methods,
not as a prevalence estimator or a leaderboard of general agent competence. A
new method should declare its evidence contract, operation-identity lifecycle,
deduplication assumptions, and unresolved policy; then run the same public
decision across hidden schedules and report the entire safety/liveness vector.

## 6. Threats to validity

### 6.1 Construct validity

False retry permission encodes a normative contract: retry requires evidence
of terminal non-execution or valid replay protection. It can therefore mark a
retry as unsupported even when that retry happens to restore the intended state
in a fail-before-execution world. We mitigate possible misinterpretation by
reporting realized duplicate, omission, unresolved, and exact-state outcomes
separately. The four schedules are controlled representatives, not an exhaustive
model of provider behavior, and the service uses logical time rather than
claiming realistic latency distributions.

### 6.2 Internal validity

The confirmatory blocks reuse model responses only where visible transcripts
are byte-identical; authoritative states receive separate calls. This isolates
hidden-state counterfactuals but cannot remove ordinary serving stochasticity.
The original pilot informed the reduced confirmation design, and the new task
families were designed after cross-model heterogeneity was observed. They were
commit-frozen before their own execution and are disjoint from the original
tasks, but they are a held-out validation block, not a preregistration or a
random sample. The closest-work label and source-control expectation were
corrected after freeze; both changes and their unchanged estimands/outcomes are
recorded in the audit trail.

### 6.3 Statistical-conclusion validity

Schedule-expanded rows are correlated because one weak-evidence response is
replayed three times. Outcome-level McNemar values are therefore descriptive
only. Four-task intervals are coarse, and the eight-family t interval rests on
only eight hand-designed clusters. All family effects and discordances are
shown so the conclusion does not depend on asymptotic precision or a single
p-value. Five response draws in the original-task blocks and two per lexical
frame measure serving variation within fixed cases; they are not additional
independent tasks. The within-frame evidence decomposition is explicitly
post-hoc and should be replicated before it is used as a confirmatory
interaction claim.

### 6.4 External validity

Model evidence covers two OpenAI snapshots; the eight-family validation uses
only GPT-5.4. Tasks are synthetic software-engineering side effects, and the
framework audits use one controlled external-effect abstraction under one
configuration of LangGraph 0.6.11 and LangChain Core 0.3.86. The study neither
estimates production failure frequency nor tests a real provider's timing,
status consistency, idempotency retention, or payload-binding behavior. The
closest-work experiment is an author-selected deterministic policy slice with
no fresh model decisions, not a rerun of its model-dependent aggregate study.

### 6.5 Reproducibility and artifact validity

Frozen manifests, exact snapshots, sanitized logs, hashes, guarded cost caps,
and machine-checked claim pointers reduce accidental drift. Historical paid
runs predate logical-clock settlement; the ledger audit found no contradiction
in every state-sensitive in-flight row, but eight no-evidence pilot rows cannot
reconstruct decision-time ordering and no numeric timing margin is recoverable.
Framework dependencies and model endpoints can change or disappear. Finally,
the development repository remains private at the owner's direction; external
reproduction and citation adoption require a venue-compatible public archival
release after the anonymity decision.

## Artifact references used in this draft

- Model table: [`../generated/table-model-results.tex`](../generated/table-model-results.tex)
- Robustness figure: [`../generated/figure-task-robustness.svg`](../generated/figure-task-robustness.svg)
- Closest-work table: [`../generated/table-closest-work.tex`](../generated/table-closest-work.tex)
- Framework table: [`../generated/table-framework-audits.tex`](../generated/table-framework-audits.tex)
- Claim ledger: [`evidence-ledger.json`](evidence-ledger.json)
