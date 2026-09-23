# Full-paper outline

## Working title

**When Is a Retry Safe? Benchmarking Retry Admissibility Under Ambiguous LLM
Agent Tool Outcomes**

Short artifact name: **RetryBench**

## Abstract skeleton

**Problem.** LLM agents frequently recover from timed-out tool calls by
querying state or retrying, but a negative observation may be stale or may
describe an operation that is still in flight.

**Gap.** Existing evaluations often score recovery under executed versus
not-executed worlds and assume status evidence is authoritative. This does not
test whether an observation actually permits re-execution.

**Method.** RetryBench freezes task intent and the model-visible transcript,
replays one recovery decision across hidden execution schedules, and scores
false retry permission, exact final state, unresolved work, omissions, probes,
and latency separately. It varies attempt terminality, evidence contracts, and
stable idempotency.

**Results.** Weak negative evidence increased false retry permission in two
fixed model snapshots. A predeclared eight-family GPT-5.4 block found a +0.625
equal-family difference with all eight families in the same direction, while
matched lexical framing strongly moderated magnitude. On an author-selected
slice of the closest artifact, authoritative status and stable idempotency
reproduced perfectly, but weak-negative retry fell to 50% exact state after
in-flight and stale worlds were added. Actual LangGraph and LangChain Core
retry boundaries each produced duplicates in 12/16 exception-retry episodes;
stable-idempotency replay was exact in 16/16.

**Conclusion.** A status label or retryable exception is not a retry
authorization. Agent evaluations and runtimes should expose and test evidence
authority, original-attempt terminality, and replay protection.

## 1. Introduction

- Motivate with the “timeout after dispatch” decision, without implying that
  all timeouts share one cause.
- Show the three relevant realities after the same apparent failure:
  definitively not executed, still in flight, or committed but not visible.
- State the core distinction: observation versus permission to re-execute.
- Summarize the empirical finding and the safety/liveness trade-off.
- List the five contributions from the evidence map.
- End with the bounded claim: tested tasks, snapshots, and framework versions.

## 2. Background and closest work

### 2.1 Ambiguous tool outcomes

- Response loss, delayed execution, stale visibility, and duplicate effects.
- Logical operation identity versus transport attempt identity.

### 2.2 Recovery mechanisms

- Status reconciliation, terminality, backoff, stable idempotency, receipts.
- Why each is a contract rather than a keyword or UI label.

### 2.3 Closest empirical benchmark

- Credit *Did It Happen?* for paired hidden worlds, task families, status, and
  idempotency conditions.
- State its relevant exclusion/assumption boundary neutrally.
- Preview the direct author-selected reproduction slice.

### 2.4 Other systems and benchmark work

- Position Verified Tool Calls, OpenOnce, and IdempotencyBench as mechanisms or
  adjacent evaluations, not novelty to reclaim.

## 3. Retry admissibility model

### 3.1 State and evidence

- External truth: terminal not-executed, in-flight, committed.
- Evidence: source, freshness, authority, and identifier binding.

### 3.2 Retry Admissibility Contract (RAC)

- Inputs: logical operation, prior attempt status, evidence contract,
  idempotency guarantee.
- Outputs: retry permitted, retry forbidden, or unresolved/wait.
- Explicitly avoid an arbitrary-provider exactly-once theorem.

### 3.3 Metrics

- False retry permission as primary safety construct.
- Exact-state success, duplicate, omission, unresolved, wrong identity/target/
  payload, probes, recovery steps, latency.
- Safety and liveness remain separate.

## 4. RetryBench design

### 4.1 Counterfactual response replay

- Freeze one visible response and replay it over hidden schedules.
- Explain why schedule outcomes are correlated and not independent samples.

### 4.2 Schedules and evidence contracts

- Four schedules and three evidence strengths.
- Byte-equivalence and leakage guards.

### 4.3 Tasks and exact-state scorer

- Original four tasks and independent eight-family robustness tasks.
- Matched create/non-create lexical frames.
- Family-specific exact-state violations.

### 4.4 Guarded execution and reproducibility

- Frozen manifests, snapshot models, cost caps, resumable storage, sanitization,
  hashes, and external evaluation interface.

## 5. Research questions

- **RQ1:** How does evidence-contract strength affect false retry permission and
  the safety/liveness trade-off?
- **RQ2:** Does the weak-negative effect replicate across model snapshots and
  independent task families, and how much does lexical framing moderate it?
- **RQ3:** Which conclusion from the closest benchmark changes when in-flight
  and stale-visibility worlds are added without changing task semantics?
- **RQ4:** Do actual framework retry boundaries enforce external-effect retry
  admissibility, and which contract closes the gap?

## 6. Experimental protocol

### 6.1 Model blocks

- Confirmation-v2 and fixed GPT-5.4 replication.
- Prompts, response sharing, repetitions, and fixed snapshots.

### 6.2 Independent-task robustness

- Predeclared 8 × 2 matched design and decision criterion.
- Task family as the top-level generalization unit.

### 6.3 Closest-work reproduction

- Exact commit/hash validation, licenses, author-selected six-template subset,
  source simulator, and four-world extension.
- Transparently disclose the noninferential prompt-stop protocol correction.

### 6.4 Framework audits

- LangGraph 0.6.11 and LangChain Core 0.3.86 actual runtimes.
- No retry, exception retry, stable-idempotency replay.

### 6.5 Analysis

- Raw rates and discordance.
- Response-block summaries and task-family t interval.
- Outcome-level McNemar only as descriptive diagnostic.
- Deterministic controls use exact counts, not sampling p-values.

## 7. Results

### 7.1 Evidence strength changes retry permission

- Table: Mini and GPT-5.4 neutral weak versus authoritative.
- Figure: safety versus unresolved/omission trade-off by prompt condition.

### 7.2 Generalization is positive but heterogeneous

- Forest plot: eight family effects and equal-family mean/interval.
- Paired plot: create versus non-create frame within each family.

### 7.3 Closest-work conclusion becomes conditional

- Table: source controls versus four-world extension.
- State the changed conclusion precisely; do not frame as refutation.

### 7.4 Framework completion is not external-state correctness

- Side-by-side LangGraph/LangChain table.
- Highlight LangChain's 16/16 runnable completion alongside 12 duplicates.
- Stable idempotency positive control.

## 8. Discussion

### 8.1 Implications for agent evaluation

- Benchmarks should vary terminality and evidence semantics, not only labels.
- Shared-response replay improves causal isolation but changes inference units.

### 8.2 Implications for framework and tool designers

- Separate exception retryability from effect replay admissibility.
- Surface operation identity, terminal state, evidence freshness, and dedupe
  scope at the boundary.

### 8.3 Safety/liveness policy choices

- Fail-closed, wait/reconcile, and stable replay occupy different trade-offs.

### 8.4 What the lexical effect means

- Tool naming can change apparent risk tolerance even under matched semantics.
- Treat as a measurable interface factor, not a complete mechanistic account.

## 9. Threats to validity

- Construct, internal, statistical-conclusion, external, and reproducibility
  threats from the evidence map.
- Include the closest-work protocol correction as an auditability strength and
  a planning-error limitation.

## 10. Artifact and adoption

- One-command deterministic benchmark and framework audits.
- Export/score interface for other agents and models.
- Benchmark card, versioning, citation file, package plan, archival DOI.
- Public-release trigger consistent with venue anonymity and owner approval.

## 11. Conclusion

- Restate the contract-level result, empirical scope, and actionable design
  principle in three short paragraphs.

## Planned headline figures and tables

1. **Figure 1:** same timeout/negative observation branching into terminal
   non-execution, in-flight late commit, and stale committed state.
2. **Figure 2:** RetryBench counterfactual response-replay pipeline.
3. **Figure 3:** eight-family effect forest plot plus lexical pairs.
4. **Table 1:** comparison with closest and adjacent work by schedules,
   evidence contract, replay design, exact-state scoring, and framework audit.
5. **Table 2:** two-model safety/liveness results with correct analysis units.
6. **Table 3:** closest-work reproduction and extension.
7. **Table 4:** LangGraph and LangChain audit outcomes.

## Writing order

1. Lock RQs, contribution wording, and Table 1 scope comparison.
2. Generate Tables 2–4 directly from checked-in JSON.
3. Generate the eight-family figure from the frozen robustness analysis.
4. Draft Methods and Results before Introduction and Abstract.
5. Run a claim audit: every number maps to an artifact; every generalization
   has an explicit unit and limitation.
