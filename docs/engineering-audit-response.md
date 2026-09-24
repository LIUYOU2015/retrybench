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
