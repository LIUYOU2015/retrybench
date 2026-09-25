# Hostile review of the Methods and Results draft

Date: 2026-09-24

Scope: construct validity, statistical language, baseline coverage, and claim
leakage. This review treats the checked-in JSON artifacts as fixed evidence and
asks what a skeptical software-engineering reviewer could reject in the paper's
wording or design interpretation.

## Findings and dispositions

| Severity | Finding | Disposition | Residual boundary |
| --- | --- | --- | --- |
| High | “Preregistered” implied a public or independent registration that did not occur. | Replaced with “predeclared, commit-frozen before execution.” | A commit freeze reduces analytic flexibility but is not a registry. |
| High | “Independent task families” could imply probability sampling or independent construction. The families were designed after heterogeneity was observed. | Recast as a new, disjoint, held-out validation block; state that tasks are hand-designed and not sampled from a defined population. | Generalization is across the tested block only. |
| High | False retry permission could be mistaken for realized harm, especially in the fail-before-execution world where retry restores the task. | Define it explicitly as a contract violation and report duplicates, omissions, unresolved work, and exact state separately. | The metric remains normative and depends on the declared contract. |
| High | The eight-family t interval could be read as a population confidence claim despite purposive task construction and eight clusters. | Describe it as a small-sample summary of between-family variation and show all family effects. | It does not provide probability-sample inference to arbitrary tasks. |
| High | Lexical framing could explain the aggregate evidence contrast rather than merely moderate it. | Added a labeled post-hoc within-frame decomposition. Create frames retain a +0.875 equal-family weak-minus-authoritative contrast with 8/8 positive; non-create frames retain +0.375 with 4/8 positive and four ties. Wording does not erase the average evidence contrast, but strongly changes its consistency and magnitude. | The decomposition is post-hoc, uses two draws per frame, and needs independent replication before supporting an interaction claim. |
| Medium | The draft omitted the benchmark's deterministic policy frontier even though those controls establish construct behavior. | Generated and checked in a fresh zero-cost 240-episode run; added always-retry, always-stop, single-status, tri-state/backoff, and stable-idempotency results. | These are deterministic conformance checks, not sampled empirical estimates. |
| Medium | Framework wording could be interpreted as auditing defaults or alleging defects. | Record exact opt-in/configured boundaries, attempt count, exception predicates, and disabled jitter; repeat that the frameworks behave as configured. | Only LangGraph 0.6.11 and LangChain Core 0.3.86 configurations are tested. |
| Medium | Stable-idempotency language risked implying real-provider validation. | Mark it as a simulated provider-enforced positive control and enumerate required scope, retention, payload binding, and enforcement assumptions. | No real provider guarantee is tested. |
| Medium | The closest-work result could be misread as a live-model replication on the six upstream tasks. | State in Method, Results, and Threats that it is a deterministic policy/conformance reproduction and extension with no fresh model calls. | It validates the construct boundary, not the upstream model-dependent aggregate rates. |
| Medium | Recovery-cost language could imply real latency measurement. | Report probes and logical steps, and explicitly state that logical-clock schedules do not estimate wall-clock or production latency. | Production latency and incident prevalence remain unmeasured. |
| Low | The post-freeze closest-work label and source-control corrections could look hidden or outcome-changing. | Retain both in the main audit-trail subsection and the internal-validity discussion. | The corrections reveal planning error but did not change selection, estimands, or aggregates. |
| Low | A private repository weakens present-day external reproducibility and citation adoption. | State the limitation without changing visibility; require a venue-compatible archival release after the anonymity decision. | External reproduction remains unavailable until the owner-triggered release. |

## Gate decision

The evidence still supports a full empirical/software-engineering paper, but
only under the narrower language now in the draft. The strongest defensible
claim is that weak negative evidence increased false retry permission in two
fixed snapshots and persisted across the eight tested held-out families, while
effect magnitude was task- and wording-sensitive. The deterministic and
framework results establish a retry-contract boundary under controlled
schedules; they do not establish production prevalence, provider correctness,
or framework defects.

No additional paid model experiment is justified by this review. The main
remaining manuscript dependency is a properly cited Background/Related Work
section and a venue-format integration pass.
