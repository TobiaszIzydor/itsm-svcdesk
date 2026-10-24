<!-- ai-generated: 70% - Claude Code drafted the comparison from both transcripts and ledgers; the verdicts and the reading are mine -->
# Two investigators on the same incident

Both ran the course's agent loop (`agent.py`, MCP server `prom_mcp.py`, mcp 2.2.0) against the same recording,
lab4-rec-3, with nearly the same question ("Checkout errors paged at 07:09:19Z ... What is the cause?"). The first is
the recorded investigator, `qwen3:4b-instruct` on a local Ollama (`ai-rca/transcript.md`, ledger `ai-rca-eval.json`);
the second is `gemini-flash-latest` through Google AI Studio's OpenAI-compatible endpoint
(`ai-rca/second/transcript.md`, ledger `ai-rca-eval-2.json`). Every hypothesis of both was scored with the same
rules: a PromQL prediction evaluated at 07:11:30Z and 5 minutes before the onset (07:00:45Z).

| | qwen3:4b-instruct | gemini-flash-latest |
|---|---|---|
| tool calls before answering | 4 (list_metrics, two label_values, one query_range) | 7 (two alerts_at, three query, list_metrics, query_range), plus a forced final step |
| hypotheses | 4 | 3 |
| correct / hallucinated | 2 / 2 | 3 / 0 |
| beyond the alert | 1 of 4 (H2, the catalog) | all 3 (the catalog first, then its cascade) |

**How they worked.** qwen3 asked for raw counters of checkout's errors only, and read them wrongly: a cumulative
counter that stayed at 2 became "a consistent count of 2 erroneous calls" (H1) and "error counts growing steadily"
(H4, which then turned into an invented load spike). It also proposed a payment failure from general knowledge,
without running its own query (H3): payment had 0.11 calls per second and no errors. Its one useful lead, H2, came
from the label of a failed client span it happened to see. Gemini started from the alerts at the detection instant,
then asked for the error rate of **every** service with `rate()` and `sum by`, found product-catalog's GetProduct
failing, and used `ALERTS_FOR_STATE` to order the alerts in time, which put product-catalog (07:07:39Z) before
checkout. Its three hypotheses are one causal chain, catalog to frontend to checkout, and the data confirms each link.

**What neither found.** Both looked only at errors, because the question said "checkout errors": neither queried a
latency histogram or memory, so neither saw the ad service's garbage collection (p50 2 ms to 600 ms) or the
recommendation memory growth, two of the three faults. The better model was more systematic, not more curious: it
answered the question it was asked. An AI investigator inherits the framing of its prompt, so the on-call's
question should name the symptom and ask for every signal of the window, not only the one that paged.
