# Live cross-provider compatibility pilot — 2026-10-19

Follow-up: the [full public-suite comparison](cross-model-full-2026-10-19.md)
collected fresh responses separately. The pilot observations below remain unchanged.

**The revised interface passed the live compatibility gate.** The diagnostic used
24 fixed cases per provider: two per each of 12 conditions, six per each of four
tasks. It contains 16 evidence cases and eight supplied-key cases. Selection used
case metadata before inference, with identical IDs and order across providers.
This is a small diagnostic, not the complete benchmark or a model ranking.

## Authorization and credentials

The user authorized at most $5 on OpenAI and $2 on Anthropic. Existing macOS
Keychain entries passed read-only model-access checks. Credentials were injected
into the collection process environment; no new credentials were needed or
written to artifacts. No account balance or final invoice was inferred.

Models: `openai/gpt-5.4-mini-2026-03-17` and `anthropic/claude-sonnet-4-6`.
The first is a dated snapshot; the second is the available provider identifier,
not an independently established immutable weights snapshot. Each response's
returned model matched the requested identifier.

## First attempt and explicit interface revision

Pilot v1 stopped after one OpenAI call, as specified by its audit rule. The model
returned `unresolved` with a non-null idempotency key in an evidence-only case.
The frozen scorer correctly marked that invalid. The tool schema had allowed
a nullable string even when no keyed action existed. No Anthropic call occurred
in v1. The raw response and invalid decision remain in the original run.

The follow-up uses the explicitly versioned `inspect-null-only-unkeyed-v2`
interface. It restricts the key field to JSON null in evidence-only cases; the
supplied-key cases keep their nullable string field. Case prompts, scenarios,
scorer, and case selection were unchanged. V2 is a new diagnostic collection,
not a replacement presented as if v1 had succeeded. The first case was asked
again under the changed interface. Total live calls: **49**, including v1.

The original interface remains available. To opt into the tested v2 tool schema,
use `retrybench eval --null-only-unkeyed` or
`InspectAdapter(..., null_only_unkeyed=True)`. Provider settings still matter;
the pilot froze them separately rather than relying on CLI defaults.

## V2 diagnostic observations

| Endpoint | Valid decisions | Unsupported dispatches (FRP) | Permitted progress |
|---|---:|---:|---:|
| GPT-5.4 mini snapshot | 24/24 | 5/24 | 6/8 opportunities |
| Claude Sonnet 4.6 | 24/24 | 0/24 | 8/8 opportunities |

These counts describe only the selected cases and revised interface. They do not
establish full-suite rates, superiority, or population generalization. The full
scorer reports retain 216 unattempted cases per provider as missing and mark the
240-case benchmark incomplete. The initial invalid response is reported
separately rather than excluded from the collection history.

All **48/48 v2 raw responses** and exact tool arguments were retained. Independent
verification recovered decisions and token counts from the native provider
responses, checked returned model identity, and reproduced all case scores and
report metrics without additional model calls.

## Spending and safeguards

| Provider | User cap | Total retained reservation, both runs | Usage-based uncached cost upper estimate |
|---|---:|---:|---:|
| OpenAI | $5.00 | $0.2677965 | $0.00944025 |
| Anthropic | $2.00 | $0.993672 | $0.08340000 |
| Combined | $7.00 | $1.2614685 | $0.09284025 |

Cost estimates use reported input/output usage at published uncached standard
rates: OpenAI $0.75/$4.50 and Anthropic $3/$15 per million tokens. Sources checked
on the collection date: [OpenAI model pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
and [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).
These are usage-based estimates, not invoice verification. The OpenAI estimate
includes the first invalid response's 251 input and 40 output tokens.

The runner checks conservative reservations before dispatch and never recycles
unused reservations into extra calls. The OpenAI v2 cap was reduced by v1's full
reservation. Input reservation is twice serialized visible-case UTF-8 bytes plus
8192 framing tokens; output reservation is the full 512-token cap. Actual usage
stayed inside every envelope. This controls request admission under the declared
pricing/token assumptions, not the provider's billing system.

Requests were serial, interleaved by provider, with retries disabled in both
Inspect and the provider SDKs. Reasoning effort was `none`; temperature was left
unset; explicit prompt-cache writes were disabled. OpenAI used Responses,
`store=false`, and standard service tier. Each call requested one decision tool;
no tool was executed. Any infrastructure, validity, capture, identity, or usage
audit failure stops the diagnostic without automatic replay. A well-formed
unsupported retry is a measured decision error and does not stop collection.

## Reproducibility and verification

Local artifacts (gitignored):

- `results/cross-model-pilot-v1-2026-10-19/`: stopped original attempt.
- `results/cross-model-pilot-v2-2026-10-19/`: plan, visible cases, frozen source,
  dependency lock, execution log, per-provider predictions/reports, and verification.
- V2 plan hash: `e567171739033230b0f7c779bdc879f9627a64b2eba61f2e2c4d4bdd85fbf1ca`.

The collector ran from its hashed source snapshot. Dependency versions include
Inspect AI 0.3.281, OpenAI SDK 3.35.1, and Anthropic SDK 1.15.0 on Python 3.12.
The SDK constructors were checked offline with retry count zero before inference.
Six pilot tests cover balance, budgets, retained failed-call reservations,
non-replay, audit failures and acceptance of valid unsafe decisions; all pass.
Four optional Inspect tests pass, including the versioned schema change and
capture beyond Inspect's default five-call raw logging limit.

Reproduce the independent audit without credentials or inference:

```bash
PYTHONPATH=src python3 scripts/verify_cross_model_pilot.py \
  results/cross-model-pilot-v2-2026-10-19
```

The next experimental step is a separately frozen complete 240-case run per
model, under matched recorded interfaces and an explicit budget. No full run,
leaderboard, public dataset update, or publication was performed by this pilot.
