# RetryBench benchmark card

## Purpose

RetryBench tests whether recovery systems make safe retry decisions after ambiguous side-effecting tool outcomes. It is a conformance benchmark, not an estimate of real-world incident prevalence or a general agent leaderboard.

## Versioned evaluation unit

The public `retry-permission-v1` suite composes 160 evidence cases from
confirmation-v2 and 80 model-independent supplied-key cases from
candidate-presence-v1: 240 visible decisions and 480 correlated outcomes.
It is a public labeled evaluation set, not a held-out expansion or a pooled paper
estimate. The [cross-model contract](docs/cross-model-evaluation.md) defines
hashes, exact key matching, protocol validity, missingness bounds, and an
80-case permitted-progress denominator. Report its blocks separately.


Confirmation-v2 contains four software-engineering task templates, three decisive hidden schedules, two evidence contracts, two prompt conditions, and five fresh draws. It yields 160 public decision cases and 240 hidden-state outcomes per evaluated method/model.

## Primary construct

The primary construct is retry admissibility: a non-idempotent retry is permitted only when authoritative evidence establishes terminal non-execution, or when a separately declared replay-protection guarantee makes repetition safe. Weak `NOT_FOUND` does not establish this condition.

## Metrics

- False retry permission
- Duplicate effect
- Omission
- Unresolved outcome
- Exact-state success, including operation identity, task, tool, target, payload, multiplicity, and resolved status

Safety and liveness metrics must remain separate. Aggregate exact-state success can conceal whether a method achieves safety by leaving work unresolved or achieves liveness by risking duplicates.

## Intended uses

- Regression testing recovery policies and agent runtimes
- Comparing model interpretation with deterministic enforcement
- Auditing provider/tool evidence semantics
- Teaching ambiguous-outcome and idempotency failure modes

## Out-of-scope uses

- Estimating provider failure rates or production prevalence
- Claiming exactly-once execution for arbitrary external APIs
- Ranking general model intelligence
- Treating a synthetic schedule as evidence that a named provider has that behavior

## Leakage controls

Public cases exclude hidden schedule labels. Weak-evidence actions are reused across matched hidden schedules. The scorer alone reads ground truth. Evaluators should publish their decision JSONL and disclose any additional evidence or prompt changes.

## Known limitations

The current suite has four task templates, controlled local schedules, and no measured production timing distribution. Results can depend on model snapshots, prompts, framework defaults, and provider semantics. The exploratory pilot is not part of confirmation-v2 evidence.

## License and citation

The current repository license is PolyForm Noncommercial 1.0.0. This may restrict commercial adoption. Citation metadata is provided in `CITATION.cff`; a DOI and preferred paper citation will be added at the first archived release.
