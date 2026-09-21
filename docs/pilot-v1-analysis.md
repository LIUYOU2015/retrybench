# RetryBench pilot-v1 analysis

Run date: 2026-09-20

Model: `gpt-5.4-mini-2026-03-17`

Design: 4 tasks × 4 schedules × 3 evidence contracts × 2 prompts × 1 sample

Completed: 96/96 cells

API cost: $0.0401565

## Decision

**GO for the public artifact, a SANER Tool Demo-oriented paper, and a small
targeted confirmation. Do not launch the 4,800-episode confirmatory matrix.**

The pilot passes the empirical continuation gate: evidence strength changes the
safety conclusion, matched weak-negative transcripts expose duplicate effects in
different hidden worlds, cautious prompting reveals a safety/liveness tradeoff,
and deterministic authoritative/idempotent controls close the gap. This supports
a benchmark-validity and tool contribution. It does not yet support broad claims
about models, production prevalence, or a new recovery mechanism.

## Headline results

| Evidence | Prompt | n | False retry permission | Duplicates | Unresolved | Exact state |
|---|---:|---:|---:|---:|---:|---:|
| None | Neutral | 16 | 11 | 9 | 5 | 2 |
| None | Cautious | 16 | 0 | 0 | 16 | 0 |
| Weak | Neutral | 16 | 11 | 7 | 2 | 7 |
| Weak | Cautious | 16 | 0 | 0 | 15 | 1 |
| Authoritative | Neutral | 16 | 2 | 2 | 4 | 10 |
| Authoritative | Cautious | 16 | 0 | 0 | 6 | 10 |

Overall: 24 false retry permissions, 18 duplicate effects, 10 omissions, 48
unresolved outcomes, and 30 exact-state successes. These totals combine
deliberately different conditions and should not be read as a model leaderboard.

## Matched weak-negative result

The most diagnostic cells hold the model-facing transcript fixed at weak
`NOT_FOUND` while the hidden schedule is one of:

- definitively not executed;
- original request still in flight and later committing; or
- committed but temporarily invisible.

Under neutral instructions, the model retried in 10/12 such cells. All ten are
false permissions because weak `NOT_FOUND` does not establish terminal
non-execution. The retry happened to complete the four pre-execution-failure
cells, but caused six duplicates across the in-flight and stale-read worlds.

Under cautious instructions, the model made zero unsafe retries and zero
duplicates in the same 12 cells, but all 12 remained unresolved and the four
pre-execution-failure cells became omissions. Prompt advice therefore moved the
system from unsafe liveness to fail-closed safety; it did not solve recovery.

## Evidence-strength contrast

For the 16 paired neutral-prompt coordinates:

- weak evidence had 11 false retry permissions;
- authoritative evidence had 2;
- nine pairs failed only under weak evidence, two failed under both, and none
  failed only under authoritative evidence;
- the descriptive exact McNemar two-sided p-value is 0.00390625.

The two remaining authoritative failures are important: the model retried 2/8
authoritative `COMMITTED` cells, despite an observation that should terminate
recovery. Deterministic enforcement did not make these mistakes.

## Interface versus enforcement

The zero-cost deterministic controller made zero unsafe retries. Its
authoritative-status cells and all 16 stable-idempotency controls reached exact
state. The LLM exposed to authoritative evidence still produced two duplicates,
while cautious instructions avoided duplicates by leaving more tasks unresolved.

The defensible result is therefore not simply “more information helps.” It is:

> Evidence semantics determine whether retry is permitted, but exposing those
> semantics to a model is not equivalent to enforcing them in the runtime.
> Weak-negative interfaces can look live by spending safety; cautious prompting
> can look safe by spending liveness.

This statement is consistent with prior verification and durable-effect work.
RetryBench's incremental value is an executable construct-validity audit that
makes the hidden assumption and tradeoff measurable.

## Rationale diagnostics

Several neutral decisions invented guarantees absent from the interface—for
example, describing issue creation or release creation as “idempotent-looking,”
or retrying authoritative `COMMITTED` work to obtain confirmation. These are
qualitative failure examples, not a separately powered outcome.

## Validity boundary

- One fixed model snapshot.
- Four task templates and one sample per cell.
- No estimate of production incident frequency.
- No randomized repeated sampling; descriptive p-values do not replace
  task-level replication.
- The service schedules are controlled constructs, not measurements of provider
  timing distributions.
- The continuation threshold operationalizes the predeclared word “material”
  after protocol freeze; it is a pilot heuristic, not a preregistered hypothesis
  test.

## Publication recommendation

The fastest defensible route is now **SANER 2027 Tool Demo**, centered on the
runner, manifest, exact-state scorer, transcript audit, persistent fault service,
and reproducible safety/liveness report. The empirical result motivates the tool
but should remain explicitly labeled a pilot.

Keep **SANER 2027 RENE** as a secondary route only after adding a faithful
reproduction slice of the closest work and repeated samples for the decisive
weak-negative contrasts. A full 4,800-episode matrix is not justified yet.

## Next gate

Before further paid expansion:

1. Freeze a targeted confirmation protocol around weak `NOT_FOUND`,
   authoritative controls, and runtime enforcement.
2. Add repeated samples and at least one second model only to those decisive
   cells.
3. Predeclare the statistical estimand and stopping rule.
4. Draft the Tool Demo paper and demo workflow in parallel; the artifact already
   has enough behavior to demonstrate without waiting for a leaderboard.
