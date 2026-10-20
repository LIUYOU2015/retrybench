## Model result submission

- Model/provider and immutable snapshot, or disclose a mutable alias:
- Suite version/hash and code commit (plus dirty patch if applicable):
- Collection dates, adapter version, dependency lock, exact inference settings:
- Prompt/schema changes and additional tools, memory, or evidence:
- Training/tuning or previous exposure to RetryBench:
- Prediction, report, case-score, and raw provider-response artifact paths:
- Input/output tokens and cost, with reporting coverage and pricing basis:

## Required evidence

- [ ] Filled `examples/cross_model/submission.json`; status remains unverified.
- [ ] Raw predictions rescore with `retrybench score` without inference.
- [ ] All 240 planned cases and 480 outcomes accounted for; invalid/missing retained.
- [ ] FRP, permitted progress, protocol validity, and recovery metrics reported separately.
- [ ] Per-block and per-condition results included; no pooled paper-result claim.
- [ ] Exact arguments/raw responses preserved, or missing capture disclosed.
- [ ] First decision only; no hidden-world labels passed to inference.
- [ ] Any subset, retries, exclusions, prompt tuning or format repair disclosed.
- [ ] No credentials in artifacts; RetryBench citation included.

## Verification

Maintainer rescoring result and artifact hashes:

Independent inference reproduction (if any):

Limitations and missing data:

Do not label a result reproduced solely because its submitted decisions rescore.
