# Cross-model implementation validation — 2026-10-19

This records the initial offline validation. The subsequent
[live compatibility pilot](cross-model-pilot-2026-10-19.md) records real calls,
an explicit interface revision, costs and diagnostic-only observations.

The first four adoption deliverables are implemented and verified locally:
frozen scoring contract, score-only CLI, Python/Inspect runner, and contribution
templates. The leaderboard remains deferred. See the
[usage and scoring contract](cross-model-evaluation.md).

## Executed checks

| Check | Result |
|---|---|
| Core Python 3.9 test discovery | 166 tests run, 11 optional-dependency skips, no failures |
| New scorer/API tests | 19 passed, including every evidence-action replay versus the legacy scorer |
| Optional Inspect AI 0.3.281 tests on Python 3.12 | 3 passed, including raw capture past the default logging limit and no retry after an adapter exception |
| Wheel install on fresh Python 3.9, no runtime dependencies | Export and score passed outside the repository |
| Wheel install with Inspect on Python 3.12 | Full 240-case mock evaluation passed outside the repository |
| Raw provider-call capture in full mock run | 240/240 retained, with original parsed tool arguments |
| Compile and whitespace checks | Passed |

All smoke predictions are synthetic always-defer fixtures. Both the score-only
and Inspect workflows report FRP **0/240**, permitted progress **0/80**, valid
decisions **240/240**, and unresolved outcomes **480/480**. These values establish
pipeline behavior, not language-model performance. No paid model inference ran.

## Issues found and resolved

The pre-change suite had one README navigation failure. The new project-status
section restores the documentation-map link while making the cross-model workflow
prominent.

Three historical analysis tests required the byte-identical collection-time
package. They now run in separate interpreters that preload the real archived
source. No protocol hash, historical source, or scientific output was changed,
and their original integrity checks still execute.

Inspect's standalone transcript defaults to retaining raw call data for only five
calls per model. The adapter now explicitly enables full raw logging in a fresh
transcript per decision and retains transcript attachments. This uses an internal
initialization hook in the pinned Inspect version; upgrading the dependency must
rerun the extended capture test and full smoke check.

## Local evidence and remaining validation

Local bundles and logs are in `results/cross-model-verification/` (gitignored):
`verification.json`, `core-tests.log`, `inspect-tests.log`, dependency locks,
the built wheel, `wheel-score/`, and `wheel-inspect/`. Each report records the
suite, prediction, and scorer source hashes. Inspect additionally records the
adapter source hash and library version.

At the end of this offline validation, the implementation had not been published
and real provider access, schema compatibility, model identity and billing were
unverified. The later pilot supplies limited evidence for two endpoints.
No Hugging Face dataset configuration, private test set, leaderboard or new
cross-model empirical claim was published. External result submissions must
include the disclosures and artifacts in the contribution template.
