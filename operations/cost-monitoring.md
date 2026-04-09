# Cost monitoring

> Sourced from: v2.7.9 §Cost monitoring
> Related: [rerun-budget.md](./rerun-budget.md), [../implementation/benchmark.md](../implementation/benchmark.md), [../implementation/caching.md](../implementation/caching.md)

---

## What gets logged

`benchmark.py` logs cost at run start and run end via `log_cost_start()` and `log_cost_end()`. There are four categories.

### Tavily credits

- **At run start**: call `GET https://api.tavily.com/usage` with `Authorization: Bearer $TAVILY_API_KEY` and log the current credit balance.
- **At run end**: call the endpoint again and log the delta.
- When the Tavily cache hits, no API call is made, so the delta reflects only **actual billable usage** — not retries, not cache hits, not anything that didn't cost credits.

The delta is the authoritative number for "how much of the Tavily quota did this run consume." Comparing it against the local count of `tavily_search` and `tavily_extract` invocations is also a useful sanity check: a large discrepancy means the cache is misbehaving.

### LLM usage

- Accumulate `input_tokens` and `output_tokens` from each LLM response's `usage` field. Every provider's SDK exposes this on the response object.
- Aggregate per provider (Anthropic / OpenAI / Google / Together).
- Compute USD estimates using provider pricing constants defined at the top of `benchmark.py`. **These constants must be looked up at implementation time from official pricing pages — do not hardcode from memory.** Pricing changes frequently and stale numbers in the spec would be misleading.

The single-model policy ([../implementation/agent-tools.md §LLM model](../implementation/agent-tools.md#llm-model-single-model-policy)) means in practice only one provider is exercised per run, but the per-provider aggregation is in place so that v1 asymmetric configurations work without code changes to the cost monitor.

The Together AI bill is a separate row because the embedder runs there regardless of which generation provider is used.

### Cache hit rate

Per cache subdir (`inverse`, `h_raw`, `tavily`):

```
hit_rate = hit_count / (hit_count + miss_count)
```

The `cache_hit()` helper exists separately from `cache_get()` so that the counters can be incremented without paying the JSON-decode cost — see [../implementation/caching.md §Cache helper functions](../implementation/caching.md#cache-helper-functions).

A high `tavily` hit rate on the second run is the key sign that the cache is working; the first run necessarily has a 0% hit rate everywhere, which is itself a useful baseline.

### Run summary

A single line is written to stdout at run end with the four headline numbers:

- Tavily credits used (delta from `/usage`).
- Total LLM input tokens.
- Total LLM output tokens.
- Estimated USD cost.

The detailed log goes to `results/run_<timestamp>.log`. Cost data is **not** written to the TSV — the TSV is per-task-per-condition and cost is per-run.

---

## How this feeds the 3-run budget

The 3-run rerun budget in [rerun-budget.md](./rerun-budget.md) depends on the cost log being honest. The decision rule "execute the first full run, review the cost log, then decide" only works if the cost log accurately reflects what was billed. This is why:

- The Tavily delta comes from `/usage`, not from local counters — the local counter could be wrong (uncounted retry, double increment), but `/usage` is what the bill is based on.
- The LLM token counts come from each response's `usage` field, not from any local pre-call estimate — the model's own report is what providers bill on.
- The cache hit rate is computed from `cache_hit()`, not from `cache_get()` exceptions — the latter could mask misses as errors.

The cost log is the authoritative input to the "do we have budget for runs 2 and 3" decision. Treat it as such.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The four cost categories (Tavily delta / LLM tokens / cache hit rate / USD estimate) | **No, version bump required** | These are the inputs to the rerun-budget decision rule. Removing one would silently break that rule. |
| Tavily delta computed from `/usage`, not from local counters | **No, version bump required** | Local counters can drift; the API is authoritative. |
| LLM token counts taken from response `usage` fields | **No, version bump required** | Same reason — the provider's own report is what gets billed. |
| Cost monitoring logged once at run start and once at run end | **No, version bump required** | Per-task logging would multiply log volume without changing the decision rule. |
| Per-provider pricing constants | Editable | Pricing changes — must be looked up at implementation time, not from memory. |
| The exact format of the run-end summary line | Editable | A presentation choice. |
| Whether per-cache-subdir hit rates are reported separately or aggregated | Editable | A presentation choice. |
| Per-paragraph wording | Editable | Explanation. |

The first four rows are load-bearing — they are what the rerun-budget decision depends on. The rest is implementation tuning.
