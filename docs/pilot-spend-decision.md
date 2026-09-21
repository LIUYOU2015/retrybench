# Pilot API-spend decision

Decision date: 2026-09-20

> Historical decision record. The pilot has since completed; its analysis is in
> `docs/pilot-v1-analysis.md`. The superseding targeted design is frozen in
> `protocol/confirmation-v2.json` and does not authorize paid execution.

## Decision: GO

Authorize the frozen 96-episode GPT-5.4 Mini pilot with a hard API ceiling of
**$2.00**. This authorizes the pilot only. It does not authorize the 4,800-episode
confirmatory run and does not establish the paper's empirical claim.

The zero-cost preflight made no OpenAI API requests. Its conservative reservation
for all 96 calls is **$0.142854**, calculated with each UTF-8 input byte treated as
an input token and every response using the full 256-output-token allowance. The
runtime budget still remains $2.00 to tolerate accounting differences without
allowing an uncontrolled run.

## Gate evidence

| Gate | Result |
|---|---|
| Frozen denominator | PASS — 96 unique cells |
| Hidden-state leakage | PASS — schedule labels absent from model input |
| Matched decision transcripts | PASS — expected schedule groups share SHA-256 hashes |
| HTTP implementation fidelity | PASS — all actual observations match the manifest |
| Initial ambiguity | PASS — one identical 504 status/body fingerprint across schedules |
| Deterministic retry safety | PASS — zero unsafe retries in 96 control episodes |
| Authoritative-status control | PASS — exact state in every authoritative cell |
| Stable-idempotency control | PASS — exact state across every task and schedule |
| Scorer fault injection | PASS — wrong target, wrong payload, duplicate, and omission detected |
| Cost reservation | PASS — $0.142854 ≤ $2.00 |
| Credential readiness | PASS locally — the configured Keychain item exists; no value was printed or stored |

The deterministic controller completed 56 of 96 cells in exact state, left 40
unresolved, and made zero unsafe retries. This is the expected safety/liveness
tradeoff: without sufficient evidence it fails closed rather than inventing
permission to retry.

## Paid-path safeguards

The `retrybench pilot` command:

- requires the explicit `--execute-paid-pilot` flag;
- requires `OPENAI_API_KEY` in the process environment;
- refuses a budget above $2.00;
- requires the exact checked-in 96-cell manifest and fixed model snapshot;
- validates the observed HTTP status, body, evidence, and transcript hash before
  each model request;
- writes each result immediately to JSONL;
- refuses to overwrite an existing database, output, or summary; and
- records token usage, actual cost, exact-state failures, and false retry
  permissions.

The full paid path was executed with a fake transport for all 96 cells. This
validated request count, per-cell persistence, result serialization, and budget
accounting without contacting OpenAI.

## What the pilot decides

The pilot tests the remaining empirical gate: whether retry-safety conclusions
change materially between weak realistic evidence and oracle-like authoritative
evidence, and whether cautious instructions reduce false retry permission.

After the pilot:

- **Continue toward a paper** only if there is a clearly auditable conclusion
  sensitivity or informative safety/liveness boundary beyond the controls.
- **Stop the confirmatory spend** if the result is fully explained by existing
  baselines, if matched cells show no meaningful contrast, or if protocol
  deviations undermine the comparison.

This authorization was consumed by the completed pilot. It does not authorize
the separately guarded confirmation-v2 command.
