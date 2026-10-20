# Cross-model evaluation

A [complete two-endpoint run](cross-model-full-2026-10-19.md) now provides 240
fresh decisions per model with native-response audits, exact rescoring, condition
breakdowns and cost accounting. It uses the explicitly versioned v2 interface;
its public reused cases do not constitute held-out generalization evidence.

RetryBench separates inference from deterministic scoring. Use an exported JSONL
file with any model, use the Python adapter API, or use the optional Inspect AI
runner. The core scorer needs Python 3.9+ and no third-party runtime dependencies.
It works from an installed wheel outside the repository.

## Score your own predictions first

Install from this checkout (pin its commit for a published experiment):

```bash
python3 -m pip install .
retrybench export --suite retry-permission-v1 --output results/cases.jsonl
# Run your model once for each visible case and write predictions.jsonl.
retrybench score --predictions predictions.jsonl --suite retry-permission-v1 \
  --model my-model --output-dir results/my-model-scored
```

For a complete zero-cost smoke test, generate **synthetic always-defer decisions**:

```bash
python3 examples/cross_model/make_predictions.py results/cases.jsonl results/defer.jsonl
retrybench score --predictions results/defer.jsonl --suite retry-permission-v1 \
  --model synthetic/always-defer --output-dir results/defer-scored
```

The expected result is FRP 0/240, permitted progress 0/80, protocol validity
240/240, and unresolved recovery 480/480. These are software fixtures, not model
measurements. Use a new output directory for every run; scoring and evaluation
refuse to overwrite existing result bundles.

## Frozen suite and data scope

`retry-permission-v1` has **240 visible cases and 480 correlated hidden-world
outcomes** across four reused software tasks:

| Block | Visible cases | Outcomes | Origin |
|---|---:|---:|---|
| Evidence | 160 | 240 | confirmation-v2, original neutral/cautious prompts |
| Supplied key | 80 | 240 | candidate-presence-v1, absent/displayed candidate × omitted/present original key |

The suite retains five draw slots per prompt condition. All original prompt bytes
are preserved. The supplied-key block uses one copy of the model-independent
prompts originally instantiated for Sol; no model name, inference setting, or
response from that endpoint is supplied to the evaluated model. It tests whether
the model reuses the actual original key, follows an offered changed key, or
invents a key when the original had none.

The package includes a static manifest and rejects changes against its pinned
SHA-256 `ebdfdbd7962cc532c82c27abffbdb9f93f3131a96f9eff3f2f98572272718235`.
It records hashes of the source manifests. The suite is a new public composition;
its aggregate is **not** an original paper result. Compare blocks and conditions
separately because the evidence block uses short label-based prompts and the key
block includes explicit contracts and a different action space.

The inference export contains instructions, prompt, decision schema, opaque case
ID, suite identity and transcript hash. It excludes schedules and gold labels.
Models must not inspect the packaged scoring manifest. The labels are public for
reproducibility; this is not an access-controlled or held-out test set.

Dataset roles are deliberately distinct:

| Role | Current artifact | Limitation |
|---|---|---|
| Examples | Offline synthetic adapters above | Teaching/smoke fixtures only |
| Development | Exported public suite | Tuning must be disclosed |
| Public evaluation | Same frozen suite, new untouched run | Not disjoint from development; no generalization claim |
| Paper reproduction | [Versioned reproduction archive](../artifacts/README.md) | Archived study protocols and responses, not this composition |

No new Hugging Face dataset configuration or private test set is claimed by this
implementation. A separate held-out expansion and qualified leaderboard
remain future work.

## Prediction contract

One JSON object per line, with one decision per visible case:

```json
{"case_id":"confirm-rg:issue-001:weak:not_found:neutral:01","action":"unresolved","arguments":{"idempotency_key":null}}
```

For a supplied-key case use its exact exported ID and, for example,
`"action":"retry_with_key","arguments":{"idempotency_key":"key-A"}`.
Key strings are compared exactly; whitespace is not trimmed.

| Action | Meaning at the first-decision horizon |
|---|---|
| `retry` | Dispatch again without a key |
| `retry_with_key` | Dispatch with the supplied nonempty key; key-block cases only |
| `stop` | End recovery as completed |
| `wait` | Defer; no new observation in this evaluated horizon |
| `unresolved` | End without claiming completion |

The scorer also accepts `RETRY` (keyed if a non-null argument is supplied),
`VERIFY_FIRST` (maps to `wait`), and `NOT_RETRY` (maps to `unresolved`). Use `stop`
explicitly for completion. The exported model schema uses the five original
actions to avoid conflating completion and abstention. No tool is executed during
inference and no multi-turn recovery trajectory is scored.

An optional top-level `idempotency_key` is accepted instead of `arguments`, but
not both. Extra argument fields and a non-null key on an unkeyed action invalidate
the decision. A retry in the evidence block cannot acquire key protection.
`retry_with_key` needs a nonempty string; a well-formed wrong key is a **valid but
unsupported retry**, not a parsing error.

Optional fields: `schema_version` (`retrybench-prediction-v1`), `suite`,
`suite_sha256`, `transcript_sha256`, `status` (defaults to `complete`), raw output
fields, and `usage` (`input_tokens`, `output_tokens`, `cost_usd`). Supplied schema
and identity fields must match; wrong identities become invalid decisions. Keep
raw tool arguments and responses for audit. Scoring preserves the entire input
record. `--settings path.json` adds a JSON object of declared inference settings.

Duplicate/unknown IDs, non-object rows, malformed JSON, duplicate JSON keys, or
non-finite JSON numbers reject the file. Missing IDs and unusable decisions
remain explicit unknown slots. Their actions and recovery outcomes are never
imputed as safe or omitted from planned denominators. Missing and invalid counts
are separate. A partial report is written and CLI exit status is **2**; a complete
report exits **0**. A structural input/configuration error exits nonzero without
claiming a scored run.

## Metrics and reproducibility

`report.json` includes overall, per-block, per-condition and per-task counts:

- **FRP:** unsupported dispatches / 240 planned visible cases. Also report the
  separate hidden-outcome-weighted version; it weights shared cases differently.
- **Permitted progress:** safe recovery dispatch with exact state in every
  compatible world / 80 planned cases where such dispatch is available (40
  authoritative terminal-nonexecution cases and 40 original-key-present cases).
- **Protocol validity:** valid decisions / all 240 planned cases.
- **Recovery:** exact state, duplicates, omissions and unresolved / 480 planned
  hidden outcomes. Omissions and unresolved outcomes can overlap.
- **Resources:** self-reported token/cost totals, each with reporting coverage.
  Missing usage/cost is unknown, never assumed zero or multiplied by hidden worlds.

Every metric reports a count, known denominator, planned denominator, unknown
count, rate among known decisions, and conservative planned-rate bounds.
For `k` observed positives, `u` unknowns and `N` planned slots, bounds are
`[k/N, (k+u)/N]`; they are missingness bounds, **not confidence intervals**. The
Python convenience property `false_retry_permission_rate` is the known-case rate;
check `report["complete"]` and bounds before comparing incomplete runs.

Repeated prompts, shared hidden worlds and four reused tasks do not justify
IID confidence intervals or population-level safety claims. Validity describes
the submitted normalized decisions, not independent verification of the raw
provider output. An external adapter must disclose its normalization rules.

Bundles contain `predictions.jsonl`, `case-scores.jsonl`, and `report.json`.
Evaluation additionally writes `cases.jsonl`, `run.json`, and a temporary
`pending.json` before each adapter call. If interrupted, the pending marker shows
an uncertain call; the runner refuses automatic overwrite/resume. Completed
responses are journaled individually and can be rescored without inference.
The report hashes the suite, predictions and scorer source files. Record the
repository commit, any dirty patch, and `python -m pip freeze` with a submission.

## Python API and custom adapters

```python
from retrybench import evaluate

def my_model_adapter(case):
    # Send only case["instructions"], case["prompt"], and its decision schema
    # to your inference service. This example deliberately makes no model call.
    return {"action": "unresolved", "raw_response": {"fixture": "synthetic"}}

results = evaluate(model="synthetic/example", adapter=my_model_adapter,
                   suite="retry-permission-v1", output_dir="results/python-example")
print(results.false_retry_permission_rate)
print(results.per_condition)
```

`score_predictions(records, suite=...)` scores already collected mappings.
Adapters receive deep copies of visible cases and return prediction mappings;
they must preserve raw outputs themselves. The runner calls once per case. An
adapter exception is journaled and halts the run, leaving remaining slots missing.
A malformed returned decision is retained as invalid. `limit=2` is a diagnostic
subset and still preserves the full planned denominator.

To load your adapter without changing RetryBench:

```bash
PYTHONPATH=examples/cross_model retrybench eval --model synthetic/always-defer \
  --adapter defer:predict --output-dir results/custom-defer
```

Custom adapters own their inference settings and internal retry behavior. The
Inspect-specific CLI generation flags do not configure custom adapters.

## Optional Inspect AI runner

The [live pilot](cross-model-pilot-2026-10-19.md) verified a separately versioned
`--null-only-unkeyed` interface with GPT-5.4 mini and Claude Sonnet 4.6 on 24
diagnostic cases each. It constrains the key field to null when no keyed action
exists. The original nullable-key interface remains the default. Preserve the
interface identifier when comparing runs; the pilot is not a complete benchmark.

Use Python **3.11+** for the pinned optional dependency:

```bash
python -m pip install '.[inspect]'
# For live calls to the two validated providers:
python -m pip install '.[openai,anthropic]'
retrybench eval --model mockllm/retrybench-defer --output-dir results/inspect-smoke
```

This exercises the real Inspect model abstraction with a synthetic local model,
without credentials or inference charges. Inspect's
[model API](https://inspect.aisi.org.uk/models.html) supplies provider integrations;
RetryBench does not maintain a native SDK for each provider. Set the provider's
documented credentials and a currently available provider/model identifier:

```bash
retrybench eval --model "$MODEL_ID" --dry-run
retrybench eval --model "$MODEL_ID" --max-output-tokens 256 \
  --output-dir results/provider-run
```

`--dry-run` reports request count without loading a provider. An actual provider
run can incur charges. Use `--limit` for a small diagnostic first. There is a token
cap and one call per case, not a provider-independent dollar guarantee.

The bridge uses a forced `decision` tool, disables Inspect retries and caching,
sets a timeout and records the effective generation settings. Temperature and
reasoning effort are unset unless explicitly requested. It never executes the
returned tool. Multiple calls, parse errors, missing tool calls, and truncated
output are invalid; no textual fallback or automatic repair changes the protocol.
Inspect's normalized output, exact parsed arguments, request representation and
available provider call records are retained. The flag
`raw_provider_response_available` states whether the provider supplied raw call
data; absence is not presented as complete raw capture. Provider defaults and
SDK-internal behavior can differ, so a shared runner does not guarantee equivalent
experimental conditions. Preserve the installed dependency lock and settings.

Offline verification covers the actual pinned Inspect mock provider. Those tests
do not establish live compatibility or billing; the separately documented pilot
adds limited OpenAI/Anthropic evidence. Google and local providers remain untested.
This forced-tool interface also differs from some
paper collection schemas; compare within matched interfaces and disclose changes.

## Contribute a model result

Copy the [submission manifest](../examples/cross_model/submission.json), replace
its placeholders, and use the [result PR checklist](../.github/PULL_REQUEST_TEMPLATE/model_result.md).
Include raw predictions, rescoring output, inference configuration, dependency
versions, code revision, usage/cost coverage, missing/invalid counts and exposure
disclosures. Cite RetryBench using the [repository citation](../README.md#citation-and-license).
Do not include API credentials. Results start as **unverified**; deterministic
rescoring does not verify model identity or reproduce inference. No leaderboard
score is published automatically.
