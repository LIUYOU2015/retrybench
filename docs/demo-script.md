# RetryBench demo script (4 minutes)

## 0:00–0:35 — The ambiguous timeout

Start the local service and submit `create_release(repo/acme, v1.2.3)`. The HTTP response is the same 504 timeout in every schedule. Show that the ledger, not the timeout, is the ground-truth oracle.

## 0:35–1:35 — One response, three hidden realities

Select the weak evidence contract. The visible status is `NOT_FOUND`. Obtain one recovery decision and replay that exact response against:

1. failure before execution,
2. an original attempt still in flight, and
3. a committed effect hidden by a stale read.

If the response retries, show the safe recovery in case 1 and duplicate effects in cases 2–3. Emphasize that RetryBench did not resample the model between those hidden schedules.

## 1:35–2:25 — Change the contract, not the task

Switch to authoritative evidence. Display `NOT_EXECUTED`, `IN_FLIGHT`, and `COMMITTED` for the same task. The admissible actions are respectively retry, wait/reconcile, and stop. Show the RAC fields beside the transcript.

## 2:25–3:15 — Exact-state scoring

Open the effect ledger and scorer output. Demonstrate detection of duplicate, omission, wrong target, wrong payload, and unresolved outcomes. Explain why a natural-language success claim is not the oracle.

## 3:15–4:00 — Reproducibility and integration

Run `retrybench confirmation-preflight` and show: 240 frozen outcomes, 160 response groups, zero API calls, and the conservative cost cap. Finish with the framework adapter and the commands needed to reproduce the containerized demo.

## Presenter guardrails

- Do not call the paid confirmation command during a live demo.
- Do not describe ambiguous outcomes, reconciliation, or idempotency as novel.
- Label the 96-call result exploratory; confirmation-v2 is the preregistered evidence.
- If a result differs by model snapshot, present that as version dependence, not a failed demo.
