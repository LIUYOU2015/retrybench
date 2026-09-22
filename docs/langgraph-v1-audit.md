# LangGraph retry-contract audit

Run date: 2026-09-22

Framework: `langgraph==0.6.11`

Design: 4 RetryBench tasks × 4 hidden schedules × 3 retry policies = 48 offline episodes

API cost: $0

## Question

Does an exception-based graph-node retry policy establish that replaying an external side effect is admissible? The audit uses the actual LangGraph runtime, not a reimplementation of its scheduler.

LangGraph's `RetryPolicy` is opt-in. In the tested release, its default exception predicate retries Python `ConnectionError`, among other transient classes. The RetryBench node models a connection loss after dispatch: the external effect may not have executed, may have committed before the response was lost, or may still be in flight. Graph-state rollback cannot undo an external effect.

## Result

| Policy | Episodes | Retries | False retry permission | Duplicates | Omissions | Unresolved | Exact state |
|---|---:|---:|---:|---:|---:|---:|---:|
| No retry policy | 16 | 0 | 0 | 0 | 4 | 16 | 0 |
| LangGraph `RetryPolicy` with default exception predicate | 16 | 16 | 16 | 12 | 0 | 16 | 0 |
| Same retry boundary with stable idempotency | 16 | 16 | 0 | 0 | 0 | 0 | 16 |

The exception-retry condition makes two attempts after the same ambiguous connection failure. It produces duplicate effects in the committed-response-lost, in-flight-late-commit, and stale-visibility schedules for every task. It happens to create one final effect in fail-before-execution, but the graph still exhausts its attempts without a confirmed result.

No retry fails closed: it creates no duplicates but leaves every graph unresolved and omits the four fail-before-execution outcomes. Stable replay uses the same operation identity and a valid deduplication guarantee; all 16 episodes complete in exact state.

## Interpretation

This is a contract-boundary result, not a claim that LangGraph is defective. LangGraph behaves as configured: its retry policy decides whether to rerun a failed node from exception class and attempt count. The application remains responsible for whether rerunning that node is safe. For side-effecting operations, a transient exception is not evidence that the earlier attempt is terminal and effect-free.

The result strengthens RetryBench's practical claim:

> A framework retry mechanism can correctly implement exception retry while still violating side-effect retry admissibility. External-effect identity, attempt terminality, evidence authority, and replay protection must be represented above or inside the retry boundary.

## Reproducibility

```bash
python -m pip install -e '.[langgraph]'
retrybench langgraph-audit
```

The optional dependency is pinned to `langgraph==0.6.11`. Outcomes and the aggregate report are checked into `runs/langgraph-v1/`. The test suite executes the real framework when the optional extra is installed and skips only these optional tests otherwise.

## Validity boundary

- The audit studies an explicitly configured `RetryPolicy`; LangGraph does not automatically attach it to every node.
- `ConnectionError` is a controlled response-loss surrogate, not a claim about every provider or transport.
- The four tasks share one side-effect abstraction.
- Stable idempotency is a positive control whose guarantee must be valid in the real provider.
- Framework versions may change their retry predicates or APIs; report the exact version.
