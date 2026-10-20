# RetryBench

**Evaluate retry permission and recovery outcomes across models.**

When a tool call times out, it may have failed, completed without returning a
reply, or still be running. RetryBench asks two separate questions: did the
visible contract justify retrying, and did the resulting state match the intended
operation? A successful outcome alone does not establish that a retry was justified.

[**Read the paper**](https://arxiv.org/abs/2610.15884v1) ·
[**Hugging Face demo**](https://huggingface.co/spaces/uuhugg/retrybench-demo) ·
[**Blog walkthrough**](https://huggingface.co/blog/uuhugg/retrybench-retry-permission) ·
[**GitHub Pages mirror**](https://liuyou2015.github.io/retrybench/)

The demo offers a plain-language payment example and a research view in English
and Chinese. It uses synthetic examples and runs entirely in your browser.

## Evaluate your model

Bring predictions from any provider, local model, or inference framework. Install
with `python3 -m pip install .` from this checkout, export the visible cases, and
score your model's first decisions without an API dependency:

```bash
retrybench export --suite retry-permission-v1 --output results/cases.jsonl
retrybench score --predictions my_predictions.jsonl --suite retry-permission-v1 \
  --model my-model --output-dir results/my-model
```

The frozen suite contains **240 visible cases / 480 replayed outcomes**, including
evidence ambiguity and supplied-key cases. Reports separate false retry
permission, permitted progress, protocol validity, and recovery outcomes, with
condition breakdowns, exact denominators, and missing/invalid accounting.

Use `from retrybench import evaluate` with your own Python adapter, or install
`.[inspect]` on Python 3.11+ for an optional provider-independent runner. This
one-command example uses a synthetic local model and costs nothing:

```bash
retrybench eval --model mockllm/retrybench-defer --output-dir results/inspect-smoke
```

Download the [raw-response evidence archive](artifacts/cross-model-v1.md) to reproduce
the comparison without API calls.

See the [cross-model guide](docs/cross-model-evaluation.md) for prediction formats,
an offline end-to-end example, provider settings, and result contributions.

## Project status

The public cross-model suite is a versioned composition of existing prompts,
separate from the paper's study-specific results below. It is publicly labeled,
not a held-out test. The runner is verified with offline fixtures and Inspect's
mock provider. A [live compatibility pilot](docs/cross-model-pilot-2026-10-19.md)
also passed on 24 cases each for GPT-5.4 mini and Claude Sonnet 4.6 using the
explicit v2 tool interface. A subsequent [full public-suite comparison](docs/cross-model-full-2026-10-19.md)
collected 240 fresh responses per model: observed unsupported retries were 61/240
for GPT-5.4 mini and 12/240 for Claude Sonnet 4.6, with permitted progress of 60/80
and 80/80 respectively. These descriptive results use four reused tasks and the
v2 interface; they are separate from the paper studies below. A leaderboard is deferred until independently
reproducible submissions exist. Browse the [documentation map](docs/README.md)
for research protocols and reproduction records.

## Findings

The [paper](https://arxiv.org/abs/2610.15884v1) reports:

- **Protected recovery and rejection of unsupported retries are different abilities.**
  In a 720-response key control, offered changed keys elicited unsupported retries
  in Sol (1/80), Terra (55/80), and Luna (60/80), despite generally successful
  recovery with valid keys.
- **Errors can persist without a displayed candidate key.** In a separate
  240-response supplied-key control, unsupported dispatches were 0/80 for Sol,
  0/80 for Terra, and 8/80 for Luna. Output requirements and conditions also
  changed, so this is not an isolated test of candidate display.
- **Deferral avoids dispatch but does not establish recovery.** An explicit-contract
  cue control elicited deferral in all 762 returned responses, leaving recovery
  unresolved.

These results concern four selected software tasks, fixed GPT endpoints, and
one recovery decision. They do not establish production failure rates, internal
model mechanisms, or episode-level safety. Report retry permission and realized
recovery together, including duplicates, omissions, and unresolved outcomes.

## Reproduce the deterministic benchmark

Requires Python 3.9 or later. The core benchmark has no third-party runtime
dependencies and makes no model calls.

```bash
git clone https://github.com/LIUYOU2015/retrybench.git
cd retrybench
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
retrybench run --output results/episodes.jsonl --summary results/summary.json
```

On Windows, activate the environment with `.venv\Scripts\activate`.
Record `git rev-parse HEAD` with your results to identify the exact code version.

The command evaluates five policies across four tasks, four execution schedules,
and three evidence contracts: 240 deterministic outcomes, 48 per policy.

| Policy | Exact state | Duplicates | Omissions | Unresolved |
|---|---:|---:|---:|---:|
| Always retry | 12/48 | 36 | 0 | 0 |
| Always stop | 36/48 | 0 | 12 | 0 |
| Single status | 24/48 | 24 | 0 | 0 |
| Tri-state backoff | 28/48 | 0 | 8 | 20 |
| Stable idempotency | 48/48 | 0 | 0 | 0 |

These are simulator reference results, not model scores. Omissions and unresolved
outcomes can overlap. The [reference summary](runs/deterministic-baselines-v1/summary.json)
contains the archived counts; current output also includes operation-identity
error fields. Same-key retry assumes a valid provider deduplication guarantee,
unchanged payload, and use of that key on the original call.

Run the core benchmark checks with:

```bash
python -m unittest discover -s tests -p test_benchmark.py -v
```

## Legacy confirmation-only evaluation

Export the visible cases, generate one action per case, then score those actions:

```bash
retrybench export-cases --output results/public-cases-v1.jsonl
retrybench score-decisions --decisions my-decisions.jsonl \
  --output results/my-scores.jsonl --summary results/my-summary.json
```

`my-decisions.jsonl` must contain one JSON object per line with `case_id` and
`action`. Valid actions are `retry`, `stop`, `wait`, and `unresolved`.
The export has 160 visible cases; scoring replays decisions across compatible
hidden schedules to produce 240 outcomes. Methods must not inspect hidden
schedules when choosing actions.

See [Evaluate your method](docs/evaluate-your-method.md) for this legacy format.
New cross-model runs should use the versioned `export` / `score` workflow above.

## Research data and reproduction scope

The public repository includes the deterministic benchmark, external-decision
scorer, and archived results for the
[confirmation study](runs/confirmation-v2/analysis.json),
[replication study](runs/gpt54-replication-v1/analysis.json), and
[task-robustness study](runs/task-robustness-v1/analysis.json).
Their sanitized outcome files are stored alongside the reports.

The [versioned reproduction archive](artifacts/reproduction-v1.zip) includes the
frozen data, protocols, collection-time source, and offline analyses for the
revised paper's key and interface controls. See the
[reproduction instructions](artifacts/README.md) for installation, checksums,
and verification of 49 regenerated scientific outputs. This self-contained
snapshot is separate from the lightweight benchmark installation above.

Reproduction reanalyzes archived model responses; it does not obtain new model
responses or incur inference charges. The demo's 81 synthetic teaching rows
are separate from the research observations.

The [benchmark card](BENCHMARK_CARD.md) describes metrics and intended use.
Optional framework checks are documented for
[LangGraph](docs/langgraph-v1-audit.md) and
[LangChain Core](docs/langchain-v1-audit.md).

## Run the demo locally

```bash
python3 -m http.server 7860 --bind 127.0.0.1 --directory demo
```

Open <http://localhost:7860>. See the [demo guide](demo/README.md) for the
interactive walkthrough and interpretation of its outcomes.

## Citation and license

```bibtex
@misc{liu2026retrybench,
  title = {RetryBench: Separating Retry Permission from Recovery Outcomes in GPT Tool Use},
  author = {You Liu and Yue Liu and Quanchao Lu},
  year = {2026},
  eprint = {2610.15884},
  archivePrefix = {arXiv},
  primaryClass = {cs.AI},
  url = {https://arxiv.org/abs/2610.15884v1}
}
```

Code is available under the [PolyForm Noncommercial License 1.0.0](LICENSE).
See the license for permitted uses and conditions. For software results, also
report the Git commit used.
