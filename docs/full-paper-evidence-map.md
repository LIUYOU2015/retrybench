# Full-paper claim and evidence map

Working title: **When Is a Retry Safe? Benchmarking Retry Admissibility Under
Ambiguous LLM Agent Tool Outcomes**

## Central claim

After a tool call returns an ambiguous failure, an observation such as
`NOT_FOUND` is not by itself permission to execute the operation again. Safe
retry depends on a contract: whether the original attempt is terminal, whether
the evidence is authoritative and fresh, and whether replay is protected by a
valid idempotency guarantee. RetryBench makes that distinction executable and
measures both unsafe retry permission and the safety/liveness trade-off.

## Claim-to-evidence matrix

| ID | Bounded claim | Evidence | Unit / size | Status | Do not claim |
| --- | --- | --- | --- | --- | --- |
| C1 | Identical visible recovery evidence can require different safe actions because original execution may still be pending or temporarily invisible. | Deterministic paired schedules and exact-state scorer. | 4 schedules × 4 base tasks; byte-identical pre-probe transcripts. | Supported. | A new general impossibility theorem. |
| C2 | Treating weak negative evidence as retry permission creates duplicate effects in nonterminal and stale worlds; authoritative terminal evidence or stable idempotency prevents those failures in the tested design. | RetryBench deterministic controls and closest-work extension. | Closest-work extension: 6 upstream-selected tasks × 4 worlds × 3 contracts = 72 episodes. Weak-negative exact state 12/24; terminal-aware and stable-idempotency 24/24 each. | Supported across three upstream state topologies. | Exactly-once guarantees for arbitrary providers. |
| C3 | The closest work's status benefit is conditional on the authority and terminality assumed by its status interface. | Direct source-validated reproduction at upstream commit `4b626e7c…`, followed by the frozen extension. | 48 upstream-simulator episodes plus 72 extension episodes; author-selected six-task replication subset. | Supported as a construct-validity delta. | That the upstream result is false, or that its model-dependent rates were reproduced. |
| C4 | Weak negative evidence increases LLM false retry permission relative to authoritative evidence in two fixed model snapshots. | Frozen confirmation and cross-model replication. | 320 independent model responses / 480 scored outcomes. Mini neutral: 51/60 vs 3/60; GPT-5.4 neutral: 30/60 vs 0/60. | Supported for the tested snapshots, prompts, and tasks. | Universal model behavior or independence of schedule-expanded outcomes. |
| C5 | The GPT-5.4 effect persists across a new disjoint task block, but magnitude is sensitive to lexical framing. | Predeclared, commit-frozen held-out validation block. | 8 hand-designed semantic families × 2 matched frames; 128 responses / 192 outcomes. | Supported in the tested block: 8/8 weak-higher; equal-family difference +0.625; 95% family t interval [+0.402,+0.848]. Create-minus-noncreate difference +0.50. A labeled post-hoc check remains positive within create (+0.875; 8/8) and non-create (+0.375; 4/8 plus four ties) frames. | Task-population inference, task-invariant effect size, or a confirmatory causal interaction. |
| C6 | Real framework retry boundaries can correctly implement exception retry while violating external-effect retry admissibility. | Actual LangGraph and LangChain Core integrations. | 48 episodes per framework; 96 total. Both exception-retry conditions produce 12 duplicates/16. Stable idempotency reaches 16/16 exact state in each. | Supported for two exact framework versions/configurations. | A framework defect, all framework versions, or all retry middleware. |
| C7 | Safety and liveness must be reported separately: failing closed prevents duplicates but can leave tasks unresolved or omitted. | Pilot, deterministic controls, and both framework audits. | Pilot cautious weak condition: 0 unsafe retries but 60/60 unresolved and 20 omissions in confirmation; framework no-retry: 0 duplicates but 16/16 unresolved per framework. | Supported. | That cautious/no-retry behavior is globally optimal. |

## Statistical hierarchy

The paper must keep four units distinct:

1. **Model response:** the independent sampling unit within a frozen prompt and
   task coordinate.
2. **Hidden-schedule replay:** correlated outcomes derived from one response;
   useful for counterfactual scoring, not independent samples.
3. **Task family:** the top-level unit for task-generality inference in the
   eight-family robustness block.
4. **Deterministic episode:** a conformance check with no sampling uncertainty;
   report counts and scope rather than p-values.

Outcome-level McNemar values from shared-response schedules are descriptive
only. Headline uncertainty should use response blocks and, for generalization,
task-family effects. The four-family cross-model intervals are explicitly
coarse; the eight-family predeclared block is the main task-generality result.

## Contribution statement

1. **Retry admissibility as an evaluation construct.** RetryBench distinguishes
   an observed status label from contractual permission to re-execute by
   representing attempt terminality, evidence authority/freshness, and replay
   protection.
2. **Counterfactual response replay.** One byte-identical model decision is
   evaluated under multiple hidden execution schedules, separating agent
   interpretation from future external truth without paying for or sampling a
   new response per world.
3. **Evidence about model behavior and heterogeneity.** Two fixed model
   snapshots show the same directional weak-evidence effect; a predeclared
   eight-family block supports task generality while identifying lexical
   framing as an important moderator.
4. **Executable systems evidence.** A direct closest-work extension and two
   actual framework integrations show where status and exception-retry
   conclusions depend on the external-effect contract, while stable
   idempotency acts as a positive control.
5. **Reusable artifact.** The repository includes frozen protocols, guarded
   runners, an exact-state scorer, external case export/scoring, HTTP
   fault-injection service, framework adapters, sanitized evidence, and
   machine-readable analyses.

## Remaining threats and required wording

- Tasks and side effects are synthetic; the paper evaluates recovery contracts
  and decisions, not production incident prevalence.
- Model evidence covers two OpenAI snapshots, with the eight-family robustness
  block run only on GPT-5.4. Say “replicated directionally across two tested
  snapshots,” not “model-general.”
- The closest-work gate is a deterministic source-level reproduction slice,
  not a full rerun of its 756 model-task study.
- Framework audits use a controlled side-effect service. They validate the
  retry boundary, not every integration layer, persistence mode, or provider.
- Stable idempotency is safe only when key scope, retention, payload binding,
  and provider enforcement actually satisfy the declared contract.
- The task-cluster interval uses eight families and a t approximation; report
  all family effects and avoid asymptotic precision language.
- Lexical framing is a matched manipulation that explains observed variation;
  it does not establish the complete cognitive cause of retry behavior.
- Repository privacy is an owner constraint during development. The camera-ready
  plan must include a policy-compliant public release trigger and archival DOI
  to realize citation potential.

## Readiness decision

The evidence now supports a full empirical/software-engineering paper rather
than only a tool demo. All previously identified evidence gates are closed:

- new disjoint task-block robustness: passed;
- clustered/statistical repair: completed;
- closest-work direct slice and exact delta: completed;
- second framework/configuration: completed.

The remaining work is manuscript construction, figure/table generation,
artifact packaging, and venue-specific formatting—not another broad paid model
matrix. Additional API spending should require a specific reviewer-facing
hypothesis that the existing evidence cannot answer.
