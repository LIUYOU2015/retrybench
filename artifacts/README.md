# RetryBench research reproduction

Download [reproduction-v1.zip](reproduction-v1.zip), supporting the October 16,
2026 author revision, **RetryBench: Retry Decisions and Protected Recovery
Across GPT Interfaces**. It includes frozen model responses, missing-case
records, protocols, collection-time source snapshots, tests, and analyses.

Verify the download against [SHA256SUMS](SHA256SUMS), then extract it:

```sh
shasum -a 256 -c SHA256SUMS
unzip reproduction-v1.zip -d reproduction-v1
cd reproduction-v1
python3 -m venv .venv
.venv/bin/python -m pip install '.[langgraph,langchain,figures]'
.venv/bin/python verify.py
```

Python 3.9 is the validated environment. Dependency installation uses the
network; the verification commands require no API key or paid inference.
The [validated dependency versions](reproduction-v1-dependencies.txt) record
the full environment; use this file as pip's `-c` constraints file if dependency
resolution changes in the future.
The verifier checks file integrity, runs scientific tests and 27 analysis
commands, then compares 49 regenerated outputs byte for byte with the frozen
results. See [release verification](reproduction-v1-verification.json).

The archive's README maps result families to their data directories.
`ANALYSIS-COMMANDS.json` lists exact commands and source paths;
`EXPECTED-OUTPUTS.json` identifies the 49 outputs;
`FILE-HASHES.json` covers every distributed file except itself.

Use a fresh extraction for each integrity check. This release supports offline
scientific reproduction, not paper PDF compilation or a new live collection.
Presentation and documentation-navigation tests are outside its scope.
The existing PolyForm Noncommercial 1.0.0 license applies; attribution and
citation metadata are included in the archive.
