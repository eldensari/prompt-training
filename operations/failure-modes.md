# Failure modes

> Sourced from: v2.7.9 §Failure handling
> Related: [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md), [../implementation/react-loop.md](../implementation/react-loop.md), [../implementation/benchmark.md](../implementation/benchmark.md)

---

## The five scenarios

Five things can go wrong during a run that aren't a normal `completed` / `loop_detected` / `max_steps_reached` outcome. Each has a specific handling rule. None of them is allowed to silently turn into a loop or a completion.

| Failure | Handling |
|---|---|
| **Tavily timeout/error** | Place the error message as the Observation; let the agent decide (retry or switch tools). No new termination category. |
| **LLM rate limit** | Exponential backoff at the API call layer. Does not affect `terminated_by`. |
| **LLM empty response (rare)** | Retry once with the same prompt. If still empty, `terminated_by = "error"`. |
| **`inverse()` internal failure** | Retry once. If still failing, `terminated_by = "error"` and `verifier_passed = "N/A"`. (This happens before `run_react_loop` is entered for condition B — see [../implementation/benchmark.md](../implementation/benchmark.md).) |
| **Agent returns text without any tool call** | Retry the same step once. If still no tool call, force a `final_answer` call with the agent's best-effort answer. |

The first two never produce an `error` row. They are normal infrastructure noise that the rest of the pipeline absorbs:

- **Tavily errors** become Observations. The agent reads the error string in its next Thought and decides what to do — retry, switch tools, give up. This is intentional: a transient timeout looks the same as any other tool failure, and the agent handling it is a normal part of execution. If we instead bumped the row to `error` on every Tavily blip, the `error` rate would track Tavily uptime rather than infrastructure correctness.
- **LLM rate limits** are handled at the API call layer with exponential backoff. They never reach the loop logic. From `run_react_loop`'s point of view, a rate-limited call is just a slightly slower successful call.

The last three can produce an `error` row, and each has a one-retry budget before doing so. The retry budget exists because most transient failures resolve on a single retry; the cap at one retry exists because retry storms in `terminated_by = "error"` country would otherwise cost real money without doing useful work.

## Why `error` is its own taxonomy value

The reason `error` exists as a separate value (rather than being silently retried until success, or rolled into `loop_detected` or `max_steps_reached`) is the same reason the False Positive control exists in [../spec/termination-taxonomy.md §False Positive control](../spec/termination-taxonomy.md#false-positive-control-loop-count-vs-budget-exhaustion): we never want infrastructure noise to be misclassified as something else.

An LLM rate-limit retry storm should not look like a loop in the result table. A two-retry empty-response failure should not look like a `max_steps_reached`. A failed `inverse()` call in condition B should not look like the agent giving up. Each of these is a different *kind* of thing, and the result table needs to distinguish them so that an unusually high rate of any one of them surfaces as its own anomaly rather than poisoning a metric the experiment cares about.

The orthogonality with `verifier_passed` falls out automatically: an `error` row by definition has no final answer, so `verifier_passed = "N/A"`. The verifier is never called on an `error` row. See [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md).

## The 10% error-rate gate

If the rate of `terminated_by = "error"` exceeds **10%** in a run, that run is **excluded from analysis** and the cause is investigated before any further runs.

The threshold is a quality gate, not a structural element. The reason 10% (rather than 5% or 20%) is the right cutoff: it's high enough that ordinary infrastructure noise — one unlucky rate-limit storm, one Tavily outage during a 40-task run — doesn't trip it, but low enough that systematic problems (a corrupted cache, a misconfigured API key, a model provider returning gibberish) do.

A run that trips the 10% gate is excluded from the rerun budget in [rerun-budget.md](./rerun-budget.md). It does not count toward the 3-run cap, because by definition it produced no usable result.

## Where each handling rule is implemented

| Failure | Implemented in |
|---|---|
| Tavily timeout/error | The `tavily_search` / `tavily_extract` wrappers — see [../implementation/agent-tools.md](../implementation/agent-tools.md) |
| LLM rate limit | The LLM client wrapper layer — generic, not loop-specific |
| LLM empty response | `run_react_loop` — see [../implementation/react-loop.md](../implementation/react-loop.md) |
| `inverse()` internal failure | `run_task_both_conditions` — see [../implementation/benchmark.md](../implementation/benchmark.md) |
| Agent returns no tool call | `run_react_loop` — see [../implementation/react-loop.md](../implementation/react-loop.md) |

The split between `run_react_loop` and `run_task_both_conditions` is the reason `inverse()` failures don't go through the agent loop at all — `inverse()` runs *before* the agent is invoked in condition B, so a failure at that stage has its own handling path.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The five-scenario taxonomy of failures | **No, version bump required** | Removing or merging a row would re-introduce the misclassification problem `error` exists to prevent. |
| The principle that infrastructure noise (Tavily, rate limits) does not produce `error` rows | **No, version bump required** | If it did, `error` rate would track provider uptime rather than experimental infrastructure correctness. |
| The retry-once-then-error policy for the three error-producing scenarios | **No, version bump required** | One retry catches transient failures; more would mask real problems and cost real money. |
| The 10% error-rate gate (run excluded from analysis) | Editable | A quality threshold, not a structural rule. The principle "exclude pathological runs" is non-editable; the exact percentage is editable based on first-run experience. |
| The 10% threshold's role in the rerun budget (failed runs don't count) | Editable | An operational rule, not a methodology rule. |
| Per-failure error message wording | Editable | Implementation detail. |
| Per-paragraph wording | Editable | Explanation. |

The first three rows are load-bearing — they are the protection against silent misclassification. The rest is operational tuning.
