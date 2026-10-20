# Changelog

## 0.2.0 — 2026-10-20

- Add the frozen cross-model suite, `export` / `score` / `eval`, Python adapter API, and optional Inspect integration.
- Preserve first-decision scope, exact key matching, missing/invalid denominators, raw responses and reproducibility hashes.
- Add the verified 240-case-per-model comparison and a self-contained offline evidence archive, including both pilots.
- Add provider extras, contribution templates and CI. Existing study IDs and historical artifacts remain unchanged.

All notable artifact changes are recorded here. Raw provider responses and
local SQLite ledgers remain excluded from version control.

## Unreleased — audit hardening (2026-09-23)

### Fixed

- Enforced frozen `max_output_tokens` before every paid runner can spend or
  create output.
- Replaced four retry-permission implementations with one exhaustively tested
  contract predicate.
- Corrected the closest-work weak/not-executed observation label without
  changing any aggregate outcome.
- Replaced wall-clock settlement in experiment runners with explicit logical
  advancement; retained wall-clock mode for interactive HTTP demonstrations.

### Verified

- Audited 768 archived paid-run rows against their SQLite ledgers, including
  248 in-flight rows and the interrupted/resumed GPT-5.4 replication.
- Found zero observation, schedule, effect-count, or settlement-order
  contradictions. Exact historical timing margin is unavailable by schema and
  is not claimed.
- Full source test suite passes.

See [the itemized engineering audit response](docs/engineering-audit-response.md)
and the machine-readable
[archive-integrity report](runs/archive-integrity-v1/analysis.json).

## 0.1.0 — initial research artifact

- Frozen pilot, confirmation, cross-model replication, independent-task
  robustness, closest-work extension, and LangGraph/LangChain audits.
- Added exact-state scoring, external evaluation interfaces, benchmark card,
  versioning policy, and reproducible paper assets.
