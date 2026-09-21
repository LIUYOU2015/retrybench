# Retry Admissibility Contract (provisional)

RetryBench treats retry permission as an interface contract, not as a guess derived from a timeout string. This taxonomy is intentionally provisional: the paper evaluates it as an artifact abstraction and does not claim that retry contracts, status checks, or idempotency are new concepts.

| Contract class | What a negative observation guarantees | Non-idempotent retry | Required agent behavior |
|---|---|---:|---|
| Weak visibility | The operation is not visible in the queried view now; execution may be in flight or the view may be stale | Not admissible | Wait, reconcile through stronger evidence, or remain unresolved |
| Authoritative terminal non-execution | The named attempt is terminal and produced no effect | Admissible | Retry using the intended operation identity |
| Authoritative in-flight | The named attempt can still commit | Not admissible | Wait and re-probe; do not overlap attempts |
| Authoritative committed | The intended effect committed | Not admissible | Stop and return the committed result |
| Stable idempotency | Repetition with the same stable key cannot create a second intended effect within the declared scope/window | Admissible under that scope | Preserve the key and verify the provider guarantee |
| Unknown/no status | No execution-state guarantee is available | Not admissible | Fail closed or escalate as unresolved |

The contract has four fields suitable for adapters: operation identity, evidence authority, attempt terminality, and replay/deduplication guarantee. A provider response such as `NOT_FOUND` is insufficient by itself; its admissibility depends on the declared semantics of the queried view.

## Boundary of the contribution

RetryBench contributes executable conformance tests, shared-response counterfactual schedules, and exact-state scoring around these contracts. It does not estimate production prevalence and does not present the underlying distributed-systems failure modes as novel.
