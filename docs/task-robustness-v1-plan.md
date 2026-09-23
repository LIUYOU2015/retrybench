# Frozen independent-task robustness block

This block is the decision experiment for the conditional full-paper gate. It
tests whether GPT-5.4's earlier issue/release effect versus CI/review ties
reflects task semantics, a `create` lexical cue, or unstable behavior across a
small number of hand-authored tasks.

Eight new software-engineering task families are disjoint from the original
four. Each has two semantically matched variants: a `create_*` tool name and a
non-create verb. Target and payload are byte-equivalent within each pair, so
the tool-name frame is the intended surface manipulation. The families cover
artifact publication, deployment requests, reviewer requests, security
findings, maintenance jobs, webhook events, package versions, and change
records.

Each frame receives two fresh neutral GPT-5.4 responses. Weak responses are
replayed across fail-before-execution, in-flight late commit, and stale-negative
after commit schedules. Authoritative responses are schedule-specific. This
produces 128 model calls and 192 scored outcomes.

Task family is the top-level generalization unit. The primary estimate is the
equal-family mean false-retry-permission difference between weak and
authoritative evidence. The lexical estimate is the paired create-minus-
noncreate difference under weak evidence. Schedule outcomes and lexical
variants are not counted as independent task samples.

The stronger empirical-paper path requires at least 6/8 weak-higher families
and a task-cluster 95% t interval whose lower bound is above zero. A positive
mean with at least 5/8 weak-higher families but failure of the interval
criterion selects the directional artifact-first path. All other outcomes fail
to support task generality.

The conservative reservation is $0.43164 under a $0.60 run cap. Added to the
tracked $0.33131525, the maximum cumulative amount is $0.93131525, below the
user's $1 check-in threshold. Expected cost from the previous GPT-5.4 run is
approximately $0.178084. No paid call is permitted until the manifest,
preflight, analysis implementation, tests, and this document are committed.

Repository visibility remains private.
