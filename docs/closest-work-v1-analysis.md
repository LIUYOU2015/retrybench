# Closest-work reproduction and extension result

The zero-cost closest-work gate passed on the six tasks preselected by the
authors of *Did It Happen?*. RetryBench validated upstream commit
`4b626e7cde61ec9275a30e23982d146ee6f4e65d`, all frozen input hashes, and the
exact `replication_subset_ids` before executing the upstream artifact's own
simulator.

## Source-faithful result

Across 48 deterministic source episodes, authoritative status reconciliation
and stable-idempotency replay each reached exact state in 12/12 episodes. In
every structural family, the better fixed prompt-only action reached 50%,
matching the upstream artifact's control gate.

The first RetryBench protocol draft incorrectly expected aggregate
prompt-only stop to reach 50%. The actual result was 4/12 (33.3%) because the
upstream `reserve_then_link` family requires a downstream link: stopping after
a response-lost reservation leaves the task incomplete. This was a
deterministic source-control transcription error. The correction, original
expectation, and observed result are retained in the protocol and analysis; no
task, extension schedule, policy, estimand, or outcome was changed.

## RetryBench extension result

The four-world extension contains 72 deterministic episodes: the same six
task/interface definitions crossed with the source worlds plus in-flight late
commit and stale-negative-after-commit, under three recovery contracts.

| Recovery contract | Exact state | Rate |
| --- | ---: | ---: |
| Negative status as retry permission | 12/24 | 50% |
| Terminal-aware status reconciliation | 24/24 | 100% |
| Stable-idempotency replay | 24/24 | 100% |

All 12 failures under negative-status retry occurred in the added worlds: six
in-flight late commits and six stale negative reads. None occurred in the
source's not-executed or executed-response-lost worlds. Each failure created
two effects, with the family-specific violation preserved: duplicate entity,
target overshoot, or overconsumption/orphan.

## Claim boundary

The closest work's status result reproduces inside its declared two-world,
authoritative-status scope. The conclusion that changes is not “status does
not help.” It is: **a status observation helps only to the extent that its
contract proves terminal non-execution or committed execution; a weak negative
lookup is not itself permission to retry.** Stable idempotency remains safe in
all tested worlds.

This is a deterministic construct-validity slice. It does not reproduce the
upstream paper's model-dependent aggregate rates and is not evidence about the
prevalence of stale or in-flight states in production.

Source: <https://github.com/shushuyang231/ambiguous-tool-outcomes-benchmark>;
archived release: <https://doi.org/10.5281/zenodo.21888869>. Task data and
documentation are attributed to Shengyao Sun under CC BY 4.0; upstream
software is MIT-licensed.
