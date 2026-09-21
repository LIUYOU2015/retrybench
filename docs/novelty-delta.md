# RetryBench novelty delta and go/no-go gate

Status: **conditional GO for a 96-episode pilot**

Frozen: 2026-09-20

Target framing: empirical construct-validity audit for agent retry evaluation

## Decision

RetryBench should not claim that ambiguous tool outcomes, verification before
retry, idempotency keys, delayed visibility, or provider reconciliation are new.
All are directly represented in adjacent work. The defensible contribution is
narrower:

> Measure whether an agent evaluation changes its retry-safety conclusion when
> evidence-contract strength and original-attempt terminality are varied while
> the visible decision transcript, task intent, and decision budget are held
> fixed.

The benchmark is therefore an audit of **retry permission**. Its primary failure
is a false permission to retry: a policy retries even though the available
negative evidence does not prove that the original attempt is terminal and
effect-free. It is not a new recovery algorithm.

## Claim-by-claim delta

| Candidate claim | Closest existing coverage | RetryBench delta | Disposition |
|---|---|---|---|
| The same timeout can hide execution or non-execution. | *Ambiguous side-effect outcomes in tool-using LLM agents* uses matched two-world pairs and establishes the prompt-only identification problem. | Add no novelty; reproduce as a control. | **Do not claim.** |
| Exact final state is a better outcome than self-reported success. | The same study scores final-state recovery; IdempotencyBench scores semantic duplicates. | Use exact-state safety as a required metric, not a contribution. | **Do not claim.** |
| Status reconciliation and stable-key idempotency improve recovery. | The ambiguous-outcomes study compares prompt, status, and idempotency conditions. Verified Tool Calls and OpenOnce operationalize verification/reconciliation. | Include positive controls to detect an invalid harness. | **Do not claim.** |
| Verification should distinguish true, false, and unknown and wait before retrying. | Verified Tool Calls specifies verify-before-retry with tri-state verification and backoff, including delayed visibility. | Reproduce the behavior as a deterministic runtime control. | **Do not claim.** |
| A negative read may be stale or non-authoritative. | Verified Tool Calls discusses false negatives under eventual consistency. OpenOnce distinguishes young/non-authoritative misses from mature/authoritative misses. | Factor evidence authority independently from the observed token `NOT_FOUND`. | **Incremental experimental factor only.** |
| The first request may still be in flight and commit after a negative read. | Verified Tool Calls includes non-atomic failures and polling; OpenOnce parks ambiguous effects as `UNKNOWN`. | Cross attempt terminality with evidence authority under a matched visible transcript. | **Candidate construct-validity contribution.** |
| Provider adapters need conformance tests for miss semantics. | OpenOnce already defines capability contracts and young-miss/mature-miss conformance scenarios. | Use those semantics to build an evaluation audit, not a new conformance concept. | **Do not claim mechanism novelty.** |
| Retry modes and runtime receipts affect duplicate side effects. | IdempotencyBench covers five retry modes, semantic duplication, keys, and runtime receipts. | Hold the retry substrate fixed in the pilot; do not introduce a new taxonomy. | **Do not claim.** |
| LLM advice and runtime enforcement behave differently under identical evidence. | Adjacent work compares prompt advice with mechanisms, but not under this exact terminality-by-evidence matched audit. | Compare the LLM decision with a deterministic permission rule using identical declared evidence and budgets. | **Secondary candidate contribution.** |

## What would make this publishable

The 96-episode pilot must establish all of the following before expansion:

1. **Matched observation:** paired schedules expose byte-equivalent decision
   transcripts until the declared evidence probe.
2. **Factor validity:** changing evidence authority or terminality changes the
   safety interpretation without changing task intent.
3. **Conclusion sensitivity:** at least one evaluated LLM condition is judged
   materially safer under an oracle/terminality assumption than under a weak,
   realistic contract.
4. **Control validity:** authoritative `NOT_EXECUTED` and stable-key controls
   recover safely; the harness detects injected duplicate and omission faults.
5. **Scoring validity:** exact state includes operation identity, target, and
   payload—not merely a count of effects.

If gates 1, 2, 4, or 5 fail, the benchmark is invalid. If gate 3 fails, the
paper has no demonstrated empirical delta and should not expand to a costly
confirmatory run. It can instead become a tool-demo artifact or a replication.

## Frozen pilot question

**RQ1.** How often does an LLM grant retry permission when the visible negative
evidence is insufficient to prove that the original attempt is terminal and
effect-free?

**RQ2.** How much does that rate change across no-status, weak-status, and
authoritative-status contracts when schedules and visible prompts are matched?

**RQ3.** Under the same evidence and decision budget, how does LLM judgment
compare with deterministic runtime enforcement?

The primary endpoint is the false-retry-permission rate. Duplicate effects,
omissions, unresolved outcomes, probes, and recovery steps are secondary and
must be reported separately rather than collapsed into one success score.

## Sources and boundaries

- [Ambiguous side-effect outcomes in tool-using LLM agents](https://github.com/shushuyang231/ambiguous-tool-outcomes-benchmark): paired hidden worlds, prompt/status/idempotency conditions, exact-final-state recovery, and software-engineering task contexts.
- [Verified Tool Calls](https://arxiv.org/html/2608.02645v1): non-atomic failures, postcondition verification, tri-state results, backoff, stable keys, and delayed visibility.
- [OpenOnce](https://github.com/memovai/openonce): durable receipts, `UNKNOWN` reconciliation, fail-closed re-arming, provider capability contracts, and authoritative versus non-authoritative misses.
- [IdempotencyBench](https://github.com/gssanjana4/idempotencybench): retry-mode matrix, semantic duplicate scoring, idempotency keys, and runtime receipts.
- [Amazon EC2 eventual consistency](https://docs.aws.amazon.com/ec2/latest/devguide/eventual-consistency.html): production grounding for stale reads and recommended exponential backoff.
- [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests): production grounding for stable request keys and replayed results.

The pilot does not estimate production incident prevalence, claim that its four
schedules are exhaustive, or claim that a simulator reproduces provider timing.
Those questions require separate observational or live-system evidence.
