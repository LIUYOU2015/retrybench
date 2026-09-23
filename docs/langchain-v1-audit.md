# LangChain retry-contract audit

Run date: 2026-09-22

Framework: `langchain-core==0.3.86`

Design: 4 RetryBench tasks × 4 hidden schedules × 3 retry policies = 48
offline episodes

API cost: $0

## Question

Does an exception-eligible LangChain runnable retry establish that replaying an
external side effect is admissible? The audit executes the actual
`RunnableLambda.with_retry` wrapper. It retains the wrapper's default
`Exception` predicate, caps execution at two attempts, and disables jitter so
the audit is bounded and deterministic.

## Result

| Policy | Episodes | Runnable completed | Retries | False retry permission | Duplicates | Omissions | Unresolved | Exact state |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No retry | 16 | 0 | 0 | 0 | 0 | 4 | 16 | 0 |
| LangChain exception retry | 16 | 16 | 16 | 16 | 12 | 0 | 0 | 4 |
| Same boundary with stable idempotency | 16 | 16 | 16 | 0 | 0 | 0 | 0 | 16 |

The exception wrapper retries every ambiguous timeout. It succeeds safely only
when the first dispatch definitively did not execute. In the committed-response
lost, in-flight-late-commit, and stale-negative schedules, the runnable reports
successful completion even though final-state scoring finds two effects.

No retry avoids duplication but leaves all episodes unresolved and omits the
four fail-before-execution tasks. Stable replay retains one logical operation
identity and relies on a valid provider deduplication guarantee; all 16
episodes complete in exact state.

## Interpretation

This is a contract-boundary result, not a LangChain defect claim. The retry
wrapper correctly applies its configured exception predicate and attempt
limit. Exception eligibility answers whether code should run again; it does
not establish that an earlier external attempt is terminal and effect-free.

Together with the LangGraph audit, the result supports a class-level but still
bounded implementation claim: two real framework retry boundaries can behave
correctly according to framework semantics while violating external-effect
retry admissibility. A returned framework success is not sufficient evidence
of an exact final external state.

## Reproducibility

```bash
python -m pip install -e '.[langchain]'
retrybench langchain-audit
```

The optional dependency is pinned to `langchain-core==0.3.86`. Outcomes and
the aggregate report are checked into `runs/langchain-v1/`.

## Validity boundary

- The audit configures a two-attempt wrapper; LangChain's default maximum is
  three attempts. It preserves the default broad `Exception` eligibility.
- `AmbiguousTimeout` is a controlled response-loss surrogate, not a claim
  about every provider or exception.
- The four tasks share one side-effect abstraction.
- Stable idempotency is a positive control whose guarantee must hold in the
  actual provider.
- Framework versions may change behavior; the report records the exact
  version and configuration.
