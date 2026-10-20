# Cross-model evidence v1

Download [cross-model-v1.zip](cross-model-v1.zip) and check
[cross-model-v1-SHA256SUMS](cross-model-v1-SHA256SUMS). This archive supports the
[October 19 full comparison](../docs/cross-model-full-2026-10-19.md), separately
from the paper's historical [reproduction archive](README.md).

```bash
shasum -a 256 -c cross-model-v1-SHA256SUMS
unzip cross-model-v1.zip -d cross-model-v1
python3 cross-model-v1/verify.py
```

Python 3.9+ and its standard library suffice. Verification needs no API key,
provider SDK, network, or paid inference. Use a fresh extraction. It checks every
distributed file against a hash manifest, audits native provider tool arguments,
usage, model identity and budget accounting, and exactly reproduces the full
and pilot scores from their frozen collection-time source.

The full collection has 240 fresh responses per model and 480 replayed outcomes
per model. GPT-5.4 mini had 61/240 unsupported retries and 60/80 permitted-progress
successes; Claude Sonnet 4.6 had 12/240 and 80/80. Both returned 240/240 valid
decisions. These descriptive results concern this public reused suite and the
explicit v2 interface, not general model superiority or held-out performance.

The archive also retains the 48-call successful diagnostic and the initial
one-call failed attempt. It does not silently replace the failed observation.
Original plans, source snapshots, raw responses, normalized predictions,
dependency records, scores and cost summaries are included. Recorded local paths
are preserved for provenance; portable verification uses bundled copies.

See [release validation](cross-model-v1-verification.json) for checks on the
distributed artifact. The existing PolyForm Noncommercial license applies.
