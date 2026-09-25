# Citation and claim audit for the complete Markdown manuscript

Date: 2026-09-25

Manuscript: [`paper.md`](paper.md)

## Audit result

**Pass for a venue-neutral research draft.** Every empirical number in the main
argument is attached to M1–M3 or R1–R11, whose JSON Pointers are regression
tested against committed artifacts. Every external related-work statement uses
a primary paper, author artifact, provider document, or framework reference.
The manuscript contains no placeholder citations and no dependency on a newly
written LaTeX manuscript.

The scientific claim ceiling remains:

> Weak negative evidence increased false retry permission in two fixed model
> snapshots and persisted across eight new, disjoint GPT-5.4 task families; the
> magnitude depended on task and was sensitive to lexical framing.
> Deterministic reproduction and framework runtime audits identify the tested
> contract boundary: evidence must establish terminal non-execution, or a valid
> stable-idempotency guarantee must make replay safe.

Every qualifier is load-bearing. The manuscript does not convert this into a
model-general, task-population, provider-prevalence, exactly-once, or framework
defect claim.

## Primary-source audit

| Source | Primary material checked | Manuscript use | Explicit non-use |
|---|---|---|---|
| Sun, *Did It Happen?* | Author repository, `CITATION.cff`, release DOI, frozen artifact description | Paired executed/not-executed worlds; exact-state recovery; status and stable-idempotency controls; provenance for the six-template slice | No claim that RetryBench reproduces its live-model aggregate rates or refutes its scoped result |
| Mansoor, Phadke, and Rana, *Verified Tool Calls* | arXiv:2608.02645 | Postcondition verification, verify-before-retry, idempotency, non-atomic failures, delayed visibility | No claim that tri-state verification, backoff, or idempotency is RetryBench novelty |
| OpenOnce | Author repository and provider-capability documentation | Durable receipts, `UNKNOWN` reconciliation, authoritative/non-authoritative miss semantics, fail-closed re-arming | No mechanism-novelty claim and no empirical comparison presented as model evidence |
| IdempotencyBench | Author repository and included manuscript metadata | Retry-mode matrix, hidden effect ledger, semantic duplicate scoring, idempotency keys, runtime receipts | No claim that duplicate scoring or retry-substrate analysis is new |
| AWS EC2 | Official provider documentation | Concrete production example of eventual-consistency `NotFound` and backoff guidance | No estimate of how often RetryBench schedules occur in AWS |
| Stripe | Official provider documentation | Concrete provider-enforced idempotency semantics, key retention, and parameter binding | No claim that RetryBench validates Stripe or that every provider matches Stripe |
| LangGraph | Official API reference | Existence and role of opt-in `RetryPolicy` | No claim about unconfigured/default application behavior across versions |
| LangChain Core | Official API reference | `Runnable.with_retry` and exception-eligibility semantics | No claim about every LangChain configuration or a framework defect |

All sources were rechecked on 2026-09-25. The comparison table uses “not
reported” where a cited artifact does not state a factor, rather than inferring
that the capability is impossible or absent from all versions.

## Evidence-ID audit

| IDs | Manuscript role | Audit disposition |
|---|---|---|
| M1 | Exploratory pilot factorial design | Design only; pilot excluded from confirmatory denominators |
| M2 | Per-model confirmation/replication design and response sharing | Correctly distinguishes 160 model calls from 240 correlated outcomes |
| M3 | New, disjoint held-out task-block design | Does not use the retired “independent-task” wording |
| R1 | Exploratory pilot totals and cost | Labeled exploratory and not pooled |
| R2–R3 | Two fixed-snapshot neutral evidence contrasts | Raw rates, block discordance, task means, and coarse four-family intervals all reported |
| R4–R5 | Cautious-prompt safety/liveness boundary | Zero false permission is paired with 60/60 unresolved and 20 omissions |
| R6 | Eight-family result, lexical pairs, and post-hoc within-frame decomposition | Main criterion remains predeclared; within-frame analysis is visibly labeled post-hoc |
| R7 | Closest-work source controls and extension | Explicitly deterministic policy/conformance evidence with no fresh model calls |
| R8–R9 | LangGraph and LangChain audits | Exact versions/configurations and stable-idempotency assumption are bounded |
| R10 | Historical live-archive audit | Zero contradiction claim is limited to state-sensitive rows; eight no-evidence rows and unrecoverable timing margin remain disclosed |
| R11 | Deterministic policy frontier | Counts are presented as conformance controls, not sampled uncertainty |

## Table and figure audit

- **Table 1** is a source-scoped comparison; “not reported” is defined before
  the table.
- **Table 2** distinguishes outcome rates, response-block discordance, and
  task-family intervals.
- **Figure 3** (the checked-in SVG) shows all eight family effects and lexical
  pairs rather than only an aggregate.
- **Table 3** separates source-faithful and extended deterministic controls and
  states that no model was called.
- **Table 4** reports completion, retry, duplicate, unresolved, and exact-state
  outcomes for exact framework configurations.

The Markdown manuscript embeds the result tables directly. Existing generated
LaTeX tables remain historical build artifacts, but the current writing task
does not create or require LaTeX.

## Residual submission work, not scientific blockers

- Select a venue and apply its Markdown-to-submission formatting process.
- Add author names, affiliations, acknowledgments, funding, and conflict
  statements when supplied by the owner.
- Decide the anonymity-compatible public-release trigger; repository visibility
  remains private.
- Create an archival DOI and update `CITATION.cff` only when release is
  authorized.
- Revisit the noncommercial license deliberately if citation/adoption strategy
  favors broader reuse; do not change it implicitly.

No additional paid model run is justified by the present manuscript audit.
