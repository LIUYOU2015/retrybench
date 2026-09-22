# Versioning policy

RetryBench versions the benchmark separately from incidental implementation changes.

- Patch releases fix runners, documentation, or packaging without changing public cases, hidden schedules, scoring semantics, or expected denominators.
- Minor releases may add optional adapters, reports, or clearly separated evaluation tracks. Existing track identifiers and scores remain reproducible.
- Major releases may change tasks, schedules, evidence contracts, prompts, scoring semantics, or denominators. Results from different major versions must not be pooled without an explicit mapping study.

Every paper or result should report the release tag and Git commit. Frozen manifests are immutable after release. Corrections produce a new version plus a machine-readable changelog; files are never silently replaced.

The first archival release will be `v1.0.0`. Until then, `0.x` releases are research previews and should be cited with their exact commit.
