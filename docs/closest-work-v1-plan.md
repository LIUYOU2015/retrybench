# Closest-work reproduction and extension (frozen)

This gate uses the six-task replication subset selected by the authors of
*Did It Happen? Benchmarking LLM Agents on Ambiguous Tool Outcomes in Software
Engineering*. It does not select tasks based on RetryBench outcomes.

The source-faithful block runs the upstream artifact's own simulator and
episode function at commit `4b626e7cde61ec9275a30e23982d146ee6f4e65d`.
It checks the structural controls over the source design's two hidden worlds.
The source artifact's own gate is that the better of prompt-only stop and retry
reaches 50% separately in every family, while authoritative status
reconciliation and stable idempotency reach 100% in every family. These checks
are deterministic controls, not a reproduction of the upstream paper's
model-dependent aggregate rates.

Post-freeze correction: the first protocol draft incorrectly required an
aggregate 50% rate for prompt-only stop. Source execution exposed that
`reserve_then_link` also requires a downstream link, so stop is unsuccessful
even when the reservation happened but its response was lost. The observed
aggregate stop rate is therefore 4/12 (33.3%). The corrected check is the
upstream artifact's pre-existing family-level `max(stop, retry) == 0.5` gate.
This correction changes no selected task, extension schedule, outcome,
estimand, or interpretation rule; the original mistake and result remain
recorded here and in the machine-readable protocol.

The RetryBench extension preserves the same six instructions, logical
references, family-specific state topologies, and exact-state outcomes. It adds
two worlds excluded by the closest artifact: an original operation that is
still in flight when status is queried, and a committed operation hidden by a
stale negative read. The comparison separates three contracts:

1. treating a negative lookup as permission to retry;
2. terminal-aware status reconciliation that can distinguish and wait for
   in-flight work; and
3. stable idempotency-key replay.

The intended conclusion is deliberately conditional. If weak-negative retry
fails only in the added worlds while authoritative status and idempotency stay
safe, RetryBench shows that the closest work's status benefit depends on the
authority and terminality of status evidence. It does not contradict the
published result inside its stated scope.

Source attribution: task data and documentation were created by Shengyao Sun
and are reused with changes indicated under CC BY 4.0. Upstream software is
MIT-licensed. Source repository:
<https://github.com/shushuyang231/ambiguous-tool-outcomes-benchmark>;
archived release: <https://doi.org/10.5281/zenodo.21888869>.
