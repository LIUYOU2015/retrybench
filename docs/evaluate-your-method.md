# Evaluate your method on RetryBench

RetryBench accepts decisions from any model, agent framework, programming language, or runtime. Your method never receives hidden schedule labels.

## 1. Install and export public cases

Until the first PyPI release, install from a pinned Git revision:

```bash
python -m pip install "git+https://github.com/LIUYOU2015/retrybench.git@main"
git clone https://github.com/LIUYOU2015/retrybench.git
cd retrybench
retrybench export-cases --output public-cases-v1.jsonl
```

For a published result, replace `main` with an immutable release tag or commit.

The export contains 160 model-facing cases. Each row includes `case_id`, task, declared evidence, prompt condition, repetition, instructions, prompt, and transcript hash. It excludes the hidden execution schedule.

## 2. Produce one action per case

Run your system over each row and write JSONL:

```json
{"case_id":"confirm-rg:issue-001:weak:not_found:neutral:01","action":"unresolved"}
```

Valid actions are `retry`, `stop`, `wait`, and `unresolved`. Preserve `case_id` exactly. A complete submission has 160 unique rows.

## 3. Score against hidden schedules

```bash
retrybench score-decisions \
  --decisions my-decisions.jsonl \
  --output my-scores.jsonl \
  --summary my-summary.json
```

The scorer reuses each weak-evidence action across three matched hidden schedules, producing 240 outcomes. The summary reports false retry permission, duplicates, omissions, unresolved outcomes, and exact-state success. Keep these metrics separate; do not report exact-state success alone.

## 4. Report enough information to compare

Report the RetryBench version/commit, method and framework version, model snapshot, prompt modifications, response-sharing compliance, all five outcome counts, token/API cost, and any excluded or failed cases. Attach the 160-decision JSONL so others can reproduce scoring without rerunning your model.

## Integration rule

Adapters may transform the exported `instructions` and `prompt` into framework-native messages, but must not read `protocol/confirmation-v2-manifest.jsonl` or otherwise access hidden schedules while producing decisions. Any additional tool, memory, or evidence must be declared as a distinct condition.
