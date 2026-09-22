# Citation and adoption plan

Objective: maximize legitimate external use and citation while preserving a defensible, reproducible claim.

## Principle

RetryBench earns citations when another paper can run a method against it, publish comparable outcomes, and cite one stable reference. Venue prestige matters less than low integration cost, discoverability, and continued maintenance.

## Priority 0 — unblock public reuse

1. Make the GitHub repository publicly readable before announcing or submitting the tool.
2. Decide whether to keep PolyForm Noncommercial or move to a permissive/dual license. The current license can deter commercial labs, framework maintainers, and organizations whose legal teams require OSI-approved terms.
3. Replace the placeholder `RetryBench contributors` citation author with the actual author list and ORCIDs.
4. Reserve the `retrybench` PyPI name and configure trusted publishing; do not publish an unstable interface as `1.0.0`.

These require owner decisions and are not changed automatically.

## Priority 1 — make comparison take minutes

- Maintain the language-agnostic 160-case JSONL export and 240-outcome scorer.
- Publish one copy-paste integration for a mainstream framework, then a second only if maintenance is affordable.
- Keep deterministic and model baselines in a visible README table with full denominators.
- Provide a machine-readable result bundle and require decision JSONL for leaderboard inclusion.
- Add CI that installs the built wheel, exports cases, scores a fixture, and verifies frozen hashes.

## Priority 2 — one citation funnel

- Use the first accepted archival RetryBench paper—currently targeted to SANER 2027 Tool Demo—as the preferred paper citation.
- Point `CITATION.cff`, PyPI metadata, the repository, benchmark card, Hugging Face card, and Zenodo record to that citation.
- Create a versioned Zenodo/GitHub release with a DOI. Cite the exact software release for empirical reuse and the paper for the benchmark contribution.
- Treat any future FORGE or journal work as a genuinely distinct study; do not split the same contribution across competing “canonical” papers.

## Priority 3 — discoverability

- Publish a Hugging Face dataset/benchmark card after the public release, with version, license, limitations, paper link, and machine-readable public cases.
- Add accurate GitHub topics, a concise description, and a social-preview image.
- Record a 3–5 minute demo and a 30-second minimal workflow clip.
- Announce only after anonymous users can reproduce the quick start.

## Priority 4 — maintain the citation window

- Support the latest release for at least two years after publication.
- Triage issues, label good-first adapters/tasks, and publish compatibility fixes without mutating frozen manifests.
- Issue new major versions for construct changes and maintain a results crosswalk rather than silently replacing scores.
- Track adoption evidence: unique external result bundles, framework adapters, forks/stars/downloads, and papers reporting RetryBench results. Do not optimize vanity metrics at the expense of reproducibility.

## Venue and preprint rule

Submit SANER Tool Demo first because it offers the fastest current archival path and explicitly values downloadable tools. Post a preprint only when the manuscript and artifact are frozen and the selected venue's anonymity rules permit it. Acceptance speed and public availability start the citation clock; premature publicity that violates venue policy does not help.

## Immediate sequence

1. Owner decisions: public visibility, license, real citation authors, and paid confirmation authorization.
2. Run confirmation block 1 only after explicit spend approval.
3. Add one mainstream framework adapter and wheel-install CI.
4. Freeze `v1.0.0`, archive it with a DOI, publish to PyPI and Hugging Face, and update the preferred citation.
5. Submit the five-page Tool Demo paper and release the demo video.
