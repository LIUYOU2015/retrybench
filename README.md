# RetryBench

**A conformance benchmark for safe recovery from ambiguous tool outcomes in LLM agents.**

An agent calls a side-effecting tool, observes a timeout, and must decide whether
to retry. The same timeout can mean that the operation never ran, committed but
lost its response, or is still in flight. RetryBench evaluates recovery policies
against the hidden execution state instead of trusting the agent's completion
claim.

This repository is an executable research preview. It does not estimate
production failure prevalence or rank general model capability.

## Run RetryBench

```bash
python -m pip install .
retrybench run
```

To evaluate a method implemented in any language or framework, export the 160
public cases and score its actions against 240 hidden outcomes:

```bash
retrybench export-cases --output public-cases-v1.jsonl
retrybench score-decisions --decisions my-decisions.jsonl
```

See [Evaluate your method](docs/evaluate-your-method.md) for the two-field JSONL
interface and reporting checklist. Evaluated methods never receive hidden
schedule labels.

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

## Deterministic reference baselines

These 48-outcome-per-policy controls validate benchmark behavior; they are not
model leaderboard results.

| Policy | Exact state | Duplicates | Omissions | Unresolved |
|---|---:|---:|---:|---:|
| Always retry | 12/48 | 36 | 0 | 0 |
| Always stop | 36/48 | 0 | 12 | 0 |
| Single status | 24/48 | 24 | 0 | 0 |
| Tri-state backoff | 28/48 | 0 | 8 | 20 |
| Stable idempotency | 48/48 | 0 | 0 | 0 |

The [benchmark card](BENCHMARK_CARD.md) defines intended use, leakage controls,
metrics, and limitations. Frozen manifests follow the [versioning policy](VERSIONING.md).

## Research roadmap

1. Reproduce the controls from the closest ambiguous-outcome work.
2. Validate the in-flight and stale-negative schedules against an HTTP service.
3. Add one agent framework adapter while holding observations and budgets fixed.
4. Freeze RetryBench-v1 tasks, schedules, metrics, and container image.
5. Report safety, liveness, latency, probe cost, and unresolved outcomes without
   collapsing them into one success number.

## Frozen targeted confirmation

The exploratory pilot motivated a smaller confirmation rather than the original
4,800-outcome expansion. Freeze and audit it without API spend:

```bash
retrybench confirmation-preflight
```

The resulting protocol has 240 scored outcomes per model but only 160 fresh
model calls. For weak `NOT_FOUND`, one response is replayed across three hidden
schedules with byte-identical visible transcripts. Paid execution is separately
guarded by an explicit flag and a one-dollar maximum cap; pilot outcomes are not
included in the confirmatory analysis.

Confirmation-v2 completed 160 fresh calls and 240 scored outcomes for $0.063987.
Under neutral prompting, false retry permission was 51/60 with weak evidence and
3/60 with authoritative evidence; weak prompting produced 34 duplicates, while
cautious weak prompting produced zero duplicates but left all 60 outcomes
unresolved. See the [confirmation-v2 analysis](docs/confirmation-v2-analysis.md).

## Framework audit

The optional LangGraph adapter tests an actual graph-node retry boundary without
model calls:

```bash
python -m pip install -e '.[langgraph]'
retrybench langgraph-audit
```

With `langgraph==0.6.11`, an opt-in `RetryPolicy` using the framework's default
exception predicate retried ambiguous `ConnectionError` outcomes and produced
duplicates in 12/16 side-effecting episodes. No-retry produced zero duplicates
but left 16/16 unresolved; stable-idempotency replay reached exact state in
16/16. This is a configured contract boundary, not a framework-defect claim.
See the [LangGraph audit](docs/langgraph-v1-audit.md).

## License and citation

RetryBench is available under the PolyForm Noncommercial License 1.0.0.
Commercial use is not permitted. Citation metadata is in `CITATION.cff`.
The first archival release will add a DOI and preferred paper citation. Until
then, cite the exact Git commit used. Contributions are described in
[CONTRIBUTING.md](CONTRIBUTING.md).
