# Engineering audit response — September 23, 2026

This note records the disposition of seven findings from an independent source
review. Correctness and paid-run safety fixes were implemented before drafting
the manuscript. No OpenAI API calls were made.

## Fixed now

1. **Frozen output-token guard.** Pilot, confirmation, replication, and task
   robustness runners now reject a policy whose `max_output_tokens` differs
   from the value used to construct the frozen cost manifest. The guard runs
   before API spending, database creation, or output creation. Confirmation's
   shared runner accepts the expected token limit explicitly so a future
   replication cannot silently inherit a changed confirmation constant.
2. **Single retry-permission predicate.** All live runners and the external
   scorer call `retry_is_permitted(schedule, evidence, observed)`. An exhaustive
   enum-cross-product test verifies that permission is true only for
   authoritative `NOT_EXECUTED` evidence under `FAIL_BEFORE_EXECUTION`.
3. **Closest-work evidence label.** The weak-evidence policy now records
   `WEAK_NOT_FOUND`, rather than `TERMINAL_NOT_EXECUTED`, in the not-executed
   extension world. The policy takes the same retry action, so every aggregate
   rate and conclusion is unchanged. The regenerated outcome hash is
   `307b01fbd3b4bc88b134bc937e0ffe0e0cfbf2dd6b99217ccf16c8ff4c464905`.
4. **Deterministic settlement for experiments.** Paid and preflight runners no
   longer use wall-clock sleep to settle an in-flight original operation. The
   local service exposes an explicit logical advance used only by deterministic
   experiments. The standalone HTTP service retains wall-clock settlement for
   interactive demonstrations. This prevents machine load from allowing a
   nominal late commit to occur before the frozen first observation.

## Deferred, bounded debt

5. **Upstream import cache.** `closest_work.py` fails loudly if a second source
   checkout is loaded in the same Python process. The supported CLI invokes one
   checkout per fresh process, so there is no silent corruption. An isolated
   subprocess importer is a future ergonomics improvement.
6. **Analysis-module duplication.** The pilot and confirmation analysis modules
   contain similar loaders and summaries. They currently have independent
   frozen tests and checked-in outputs. Refactoring them while manuscript
   numbers are being stabilized has more regression risk than benefit; move
   common pure functions only after adding golden-output tests.
7. **Conservative token reservation.** Byte-count token estimation remains
   intentionally pessimistic. It can stop a run early but cannot overspend the
   declared cap. Actual usage and cost are recovered exactly on resume. Replace
   it only with a version-pinned tokenizer if premature reservation becomes an
   observed problem.

## Verification

- Full source suite: 65/65 tests pass.
- Live-run fake transports preserve the frozen call/outcome denominators.
- Logical-clock and wall-clock HTTP modes each have direct integration tests.
- Closest-work aggregate rates, paper tables, and figure values are unchanged.
- Repository visibility was not modified.

### Retrospective verification of pre-fix paid runs

The already-collected pilot, confirmation-v2, GPT-5.4 replication, and
task-robustness runs were produced with wall-clock settlement. They were not
rerun. A read-only audit now cross-checks every archived JSONL row against its
durable SQLite operation/effect ledger:

- 768/768 output rows have a matching operation, schedule, and effect count;
- all 248 in-flight operations eventually reached `committed` with a recorded
  effect timestamp;
- all 240 weak/authoritative in-flight rows retained the frozen first
  observation (`NOT_FOUND` or `IN_FLIGHT`), with zero early-settlement
  contradictions;
- the remaining eight in-flight rows are pilot `none`-evidence cells. Their
  first observation is always `UNKNOWN`, so exact decision-time ordering is
  not retrospectively observable, but each final effect count matches the
  ordering-invariant expectation: one original effect plus one additional
  effect exactly when the model chose retry;
- the interrupted GPT-5.4 run is reconciled across both SQLite ledgers. Their
  240-operation union matches all output rows; the one overlapping operation
  has identical schedule, terminal state, and effect count.

The requested numeric start-to-effect-read margin cannot be reconstructed:
the historical schema did not persist operation start time and cleared
`due_at` on settlement. The audit therefore makes the narrower evidence-backed
claim above rather than inventing a timing margin. For the confirmation,
replication, and robustness headline conditions, the state-sensitive frozen
observations directly rule out settlement before the first probe. The
machine-readable report is `runs/archive-integrity-v1/analysis.json`; regenerate
it locally with `retrybench audit-live-archives` while the ignored raw archives
are present.
