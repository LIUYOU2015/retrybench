# RetryBench: Was that retry allowed?

**A successful recovery does not necessarily mean the retry was justified.**

An agent sends a payment request and receives a timeout. The operation might never have run, already have committed, or still be in flight. Should the agent send it again?

This interactive demo lets you change the visible evidence, the idempotency-key condition, and the next action. It then shows whether retrying was permitted by the simulated contract and what happens in each compatible hidden execution state.

[Read the paper: RetryBench: Separating Retry Permission from Recovery Outcomes in GPT Tool Use](https://arxiv.org/abs/2610.15884v1) — You Liu, Yue Liu, and Quanchao Lu (2026).

## Language and reading mode

Use **中文 / English** at the top right. The full interface, explanations, choices, and generated results are bilingual. Switching languages preserves the selected scenario and visible results. The browser remembers your language preference when storage is available; the initial default is English. Raw example field names and the license remain in their original language.

A compact horizontal tab row switches between Overview / 通俗讲解 and Research & methods / 研究与方法. Bold text and an underline identify the active tab, directly above its content. Switching tabs preserves the page position. Arrow keys, Home, and End also switch the tabs.

The three story decisions use native radio buttons. One decision can be selected at a time; its radio dot and blue background remain visible while its result is shown. Changing language preserves the selection.

## Two reading paths

- **Overview / 通俗讲解:** a fictional order, three possible hidden situations, plain-language decisions, payment outcomes, and a short understanding check. No knowledge of API contracts or idempotency is assumed.
- **Research & methods / 研究与方法:** sourced arXiv v1 results with response denominators, method definitions, explicit assumptions, downloadable examples, and the full contract explorer.

The story and technical explorer use the same frozen simulator rows. The measured paper results are separately labeled and sourced; the simulator does not generate those empirical counts.

## Run locally

You need Python 3 and a modern web browser. No Python packages, model downloads, API keys, or paid inference are required.

Open a terminal in the folder containing `index.html` and `examples.json`, then run:

```bash
python3 -m http.server 7860 --bind 127.0.0.1
```

Open [http://localhost:7860](http://localhost:7860) in your browser. Press `Ctrl+C` in the terminal to stop the server.

You can also open `index.html` directly in a browser: the page embeds the same 81 rows, so the interaction needs no server or network. Keep the other files beside it for the download and documentation links.

## Technical explorer walkthrough

Select **Research & methods**, then scroll to **Make one recovery decision**. The default story path provides a separate plain-language walkthrough.

1. Select **Weak NOT_FOUND**, **Changed key**, and **RETRY**, then click **Reveal permission and outcomes**. The retry is unsupported: one world ends with exactly one effect, while the other compatible worlds produce duplicates.
2. Change the key condition to **Same original key (valid guarantee)** and reveal the results again. Reusing the valid original key protects the retry across these worlds.
3. Select **Authoritative NOT_EXECUTED** with **Changed key** and **RETRY**. The contract certifies terminal non-execution, so a retry can proceed without original-key protection.
4. Choose **WAIT / VERIFY**. No new call is dispatched, but recovery remains unresolved at the one-decision horizon.

You can also try **Timeout without status**, **Authoritative IN_FLIGHT**, **Original key absent**, and **STOP**.

## What the results mean

| Result | Interpretation |
| --- | --- |
| Retry permitted | The visible contract supports the retry: either terminal non-execution is certified or valid original-key protection applies. |
| False retry permission (FRP) | The selected action dispatches a retry without that support, even if a particular hidden world ends successfully. |
| Effects after settlement | The number of simulated effects after outstanding work finishes. Zero means omission; two means duplication. |
| Exact resolved state | Exactly one effect matches the intended operation, with recovery not marked unresolved. |
| Unresolved | The selected action defers recovery within the demo's one-decision horizon. |

**Weak NOT_FOUND is not proof of terminal non-execution.** In the simulator, it is compatible with failure before execution, an original request still in flight, or a stale negative observation after commitment.

Same-key protection assumes that the original request carried that key, the payload is unchanged, and the provider's deduplication guarantee remains valid. Changing the key—or introducing a key after an unkeyed original—does not protect against duplication of the original call.

**WAIT / VERIFY** represents deferral. The demo does not execute a later verification policy. **STOP** sends no retry and can leave the intended operation undone.

## Included examples

The demo contains four evidence cases, three key conditions, and three actions: **36 decision settings** in total. Replaying each setting across its compatible hidden worlds produces **81 outcome rows** in `examples.json`.

These rows were generated deterministically from the RetryBench simulator and scorer. They are synthetic teaching examples, not collected model responses or the full benchmark dataset. Hidden worlds are alternatives, not independent statistical observations or estimated probabilities; their row counts should not be interpreted as real-world failure rates.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Browser interface, styling, and interaction logic. |
| `examples.json` | Precomputed permission labels and simulated outcomes. |
| `README.md` | Setup instructions, walkthrough, and interpretation. |
| `LICENSE` | PolyForm Noncommercial License 1.0.0. |

The static interface displays precomputed outcomes. It does not call a model, connect to a payment service, or perform real side effects. Its external research link points to the paper.

## Scope

The payment scenario is fictional and serves as a teaching analogy. It is not an additional empirical task in the paper or a guarantee about any payment provider. The paper studies four selected software tasks, fixed GPT endpoints, and one recovery decision. Neither the demo nor those findings establish production error rates, general agent reliability, or episode-level safety.

Demo version: **teaching-demo-v4**. [Open the hosted demo](https://liuyou2015.github.io/retrybench/).

## Citation

If you discuss or use the research, cite the paper:

```bibtex
@misc{liu2026retrybench,
  title         = {RetryBench: Separating Retry Permission from Recovery Outcomes in GPT Tool Use},
  author        = {You Liu and Yue Liu and Quanchao Lu},
  year          = {2026},
  eprint        = {2610.15884},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AI},
  url           = {https://arxiv.org/abs/2610.15884v1}
}
```

## License

Code and generated teaching examples retain the **PolyForm Noncommercial License 1.0.0** in [LICENSE](LICENSE). No separate permissive data license is granted. See the license for permitted uses and conditions.
