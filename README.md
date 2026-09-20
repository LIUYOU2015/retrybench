# RetryBench

**A conformance benchmark for safe recovery from ambiguous tool outcomes in LLM agents.**

An agent calls a side-effecting tool, observes a timeout, and must decide whether
to retry. The same timeout can mean that the operation never ran, committed but
lost its response, or is still in flight. RetryBench evaluates recovery policies
against the hidden execution state instead of trusting the agent's completion
claim.

This repository is an early, executable research scaffold. It does not yet make
empirical claims about production systems or language models.

## What is included

- Four deterministic schedules: pre-execution failure, commit then response
  loss, in-flight late commit, and stale negative observation after commit.
- Three evidence contracts: no status, weak/eventually consistent status, and
  authoritative status.
- Five baselines: always retry, always stop, single status check, tri-state
  verification with backoff, and stable-key idempotent retry.
- Four software-engineering-flavored side effects.
- Exact-state scoring for duplicates, omissions, unresolved outcomes, probes,
  retries, and recovery steps.
- Reproducible JSONL episode logs and aggregate JSON summaries.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
retrybench run --output results/episodes.jsonl --summary results/summary.json
python -m unittest discover -s tests -v
```

The benchmark is deterministic. Re-running the same command produces the same
episode records apart from output-file ordering only if caller options change.

## Example

```bash
retrybench run \
  --policies always_retry tri_state_backoff stable_idempotency \
  --evidence weak authoritative \
  --schedules fail_before_execution in_flight_late_commit
```

Each JSONL row records the public observation, hidden schedule, policy decision,
ground-truth effect count, and exact-state verdict. Hidden fields are supplied to
the scorer only; policies receive only the declared evidence.

## Interpretation

`NOT_FOUND` under a weak status contract is not proof that an earlier attempt
cannot still commit. Only `NOT_EXECUTED`, supplied by an authoritative contract,
permits a non-idempotent retry. A stable idempotency key can permit retry under
ambiguity, but only while the provider's deduplication guarantee is valid.

## Research roadmap

1. Reproduce the controls from the closest ambiguous-outcome work.
2. Validate the in-flight and stale-negative schedules against an HTTP service.
3. Add one agent framework adapter while holding observations and budgets fixed.
4. Freeze RetryBench-v1 tasks, schedules, metrics, and container image.
5. Report safety, liveness, latency, probe cost, and unresolved outcomes without
   collapsing them into one success number.

## License and citation

RetryBench is MIT licensed. Citation metadata is in `CITATION.cff`.
