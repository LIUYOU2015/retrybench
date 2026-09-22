# Contributing to RetryBench

Contributions that lower evaluation friction are especially welcome: framework adapters, provider-contract fixtures, independent task templates, reproducibility checks, documentation, and bug reports with minimal cases.

Before opening a pull request:

1. Preserve hidden-state isolation; evaluated methods must not receive schedule labels.
2. Do not modify frozen manifests in place.
3. Add tests for scorer, protocol, or adapter changes.
4. Run `python -m unittest discover -s tests -v`.
5. State whether the change affects benchmark comparability or only implementation.

New schedules or scoring semantics belong in a new versioned track. New model results should include decision JSONL, model snapshot, prompt/configuration, token usage, cost, and complete denominators.
