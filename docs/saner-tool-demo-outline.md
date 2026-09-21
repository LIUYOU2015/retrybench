# SANER 2027 Tool Demo outline (five pages including references)

Working title: **RetryBench: Conformance Testing for Ambiguous LLM-Agent Tool Outcomes**

## Page budget

1. **Problem and artifact claim (0.75 page).** A timeout after a side-effecting tool call does not reveal whether the attempt failed, committed, or remains in flight. State the narrow contribution: an executable conformance tool for testing retry decisions against hidden execution state and declared Retry Admissibility Contracts (RACs). Explicitly separate this from prior ambiguous-outcome benchmarks and established retry/idempotency practice.
2. **Architecture and RAC model (1.0 page).** Diagram the local fault-injection service, model/framework adapter, shared visible transcript, hidden schedules, ledger, and exact-state scorer. Include the compact RAC taxonomy.
3. **Demonstration scenarios (1.0 page).** Show one weak `NOT_FOUND` model response replayed against fail-before-execution, in-flight late commit, and stale-after-commit schedules. Then switch to authoritative states and show why correct actions diverge. End with an injected wrong-target or duplicate fault caught by the scorer.
4. **Evaluation and evidence (1.0 page).** Report the completed 96-call pilot as motivation, clearly labeled exploratory. Report confirmation-v2 separately: 240 scored outcomes from 160 fresh responses/model, five draws, frozen snapshot, two prompts, raw paired discordance and safety/liveness metrics. Do not merge pilot and confirmation.
5. **Use, limitations, availability, and references (1.25 pages).** Describe CLI/HTTP integration and one mainstream framework adapter. Limit claims to controlled conformance behavior; discuss synthetic tasks, four operations, model/version dependence, and absence of prevalence estimates. Give public repository, archival release/DOI, reproducibility commands, license, and references.

## Claimed contributions

- A runnable fault-injection and exact-state oracle for ambiguous side-effecting calls.
- A provisional RAC schema that makes the preconditions for safe retry machine-testable.
- Shared-response counterfactual replay: an identical model decision is evaluated under hidden schedules with different ground truth.
- A framework adapter and reproducible demo workflow intended for adoption, teaching, and regression testing.

## Evidence discipline

- Closest-work reproduction results, if included, are labeled reproduction rather than novelty.
- The pilot is exploratory and excluded from confirmation statistics.
- Model block 2 and the framework study are separate replications, not pooled after looking at block 1.
- No claim that RetryBench measures incident frequency or all real provider semantics.
