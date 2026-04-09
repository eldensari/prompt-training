# `run_react_loop`: the per-step flow

> Sourced from: v2.7.9 §benchmark.py (Per-step flow inside run_react_loop)
> Related: [inverse.md](./inverse.md), [agent-tools.md](./agent-tools.md), [../spec/token-budget.md](../spec/token-budget.md), [../spec/loop-detection.md](../spec/loop-detection.md), [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md)

---

## Role

`run_react_loop` is the function that actually drives the agent. It is called once per `(task, condition)` pair from `run_single_task` (see [benchmark.md](./benchmark.md)) and returns:

```
{terminated_by, final_answer, entropy_curve, total_tokens}
```

The function name is **`run_react_loop`**, not `run_agent`. The rename happened in v2.7.9 to make explicit that the loop is a ReAct (Thought → Action → Observation) loop and to distinguish it from the t2.5 codebase's terminology.

`run_react_loop` is the only place in the codebase that owns the `terminated_by` value. Every exit path is handled here, and exactly one of the four taxonomy values from [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md) is assigned before returning.

---

## Parameters

```python
def run_react_loop(summarized_query, model, max_steps, H_raw):
    ...
```

- `summarized_query`: the 80-token Head string (the same string for the whole run; locked at the start). For condition A this is the summary of the raw query; for condition B it is the summary of the inverse-model's refined query.
- `model`: the single LLM model used for everything (single-model policy — see [../spec/hypothesis.md](../spec/hypothesis.md#what-this-is-not)).
- `max_steps`: the per-task step budget. Derived from GAIA Level — 15 for Level 1. See [gaia-integration.md](./gaia-integration.md#max_steps-by-level).
- `H_raw`: the per-task baseline used by the loop detector. The same number is passed in whether the call is for condition A or condition B — see [../spec/loop-detection.md §(c)](../spec/loop-detection.md#c-why-h_raw-is-the-reference-in-both-a-and-b-not-h_improved-in-b).

---

## The per-step flow ([a]–[h])

Each step of the loop executes the same eight-stage flow. The letters are referenced from elsewhere in the spec (and from the implementation checklist) — keep them stable.

### [a] Build context (300 tokens)

Construct the input the agent will reason over at this step:

- **Head (80 tokens)**: `[minimal instruction] + [summarized_query]`. Fixed for all steps. Never recomputed.
- **Body (70 tokens)**: a recursive summary of execution history before step n−2. At each step, this is re-summarized from (the previous Body) + (whatever just slid out of the Tail).
- **Tail (150 tokens)**: the Thought and Observation from step n−1, passed through `trim_to_tail()`. Short inputs are preserved; long inputs are meaning-preservingly trimmed (whitespace and filler removal only — never rewriting).

The total is 300 tokens. The split and the per-slot compression policies are load-bearing — see [../spec/token-budget.md](../spec/token-budget.md).

### [b] Measure semantic entropy (just before Thought)

Call `measure_semantic_entropy([minimal instruction] + [300-token context], model, n_samples)`. Append the resulting `H_n` to `entropy_curve`.

This must happen *before* the Thought, not after. The H value records the agent's situation as it enters this step, not as it leaves it. The loop detector in [f] then has the freshest possible reading of "where the agent is right now."

### [c] Thought

The agent reads the 300-token context and produces a natural-language reasoning trace about what to do next.

### [d] Action

The agent emits a tool call. There are exactly three tools — `tavily_search`, `tavily_extract`, `final_answer`. See [agent-tools.md](./agent-tools.md). One of them is called.

### [e] Observation

The tool's return value becomes the raw Observation. **The full, untruncated Observation is what step n's Thought sees** if step n needs to reference it (e.g., for tools that return long bodies). The Observation only enters the Tail trimming pipeline when step n+1's context is being built — not before. See [../spec/token-budget.md §Why the Tail can see Tavily responses much larger than 150 tokens](../spec/token-budget.md#why-the-tail-can-see-tavily-responses-much-larger-than-150-tokens).

### [f] Loop detection

Call `detect_loop(entropy_curve, H_raw, alpha=0.3, window=3)`. If `is_loop` is true, set `terminated_by = "loop_detected"` and exit. The verifier is not called for this exit path — `verifier_passed = "N/A"`.

### [g] Completion check

If the Action in [d] was `final_answer(...)`, set `terminated_by = "completed"`, capture the answer string, and exit. The completion check happens *after* loop detection in the same step: this means a step where the agent both fired the loop detector and called `final_answer` is recorded as a loop. The order matches the priorities of the experiment — `loop_detected` is the dependent variable.

### [h] max_steps check

If the step counter has reached `max_steps`, set `terminated_by = "max_steps_reached"` and exit. Otherwise, increment the step counter and proceed to step n+1.

---

## Failure paths into `terminated_by = "error"`

The four exit paths above ([f] loop, [g] completion, [h] budget) are the *normal* terminations. There is also a fourth value, `error`, assigned by `run_react_loop` when something in the infrastructure breaks in a way the agent cannot recover from:

- LLM returned an empty response twice in a row (one retry, then error).
- A tool call raised an exception that was not a normal Tavily error response.
- Agent generated text but no parseable tool call across two retries, *and* the forced `final_answer` fallback also failed.

Note: `inverse()` failure is *not* an exit path of `run_react_loop` itself — `inverse()` runs in `run_task_both_conditions` *before* `run_react_loop` is called for condition B. If `inverse()` fails, the row gets `terminated_by = "error"` without `run_react_loop` being entered at all. See [benchmark.md](./benchmark.md) and [../operations/failure-modes.md](../operations/failure-modes.md).

The full error-handling table is in [../operations/failure-modes.md](../operations/failure-modes.md).

---

## What `run_react_loop` returns

```python
{
    "terminated_by": str,        # one of "completed", "loop_detected", "max_steps_reached", "error"
    "final_answer": str | None,  # populated only when terminated_by == "completed"
    "entropy_curve": list[float],# H_n at every step, in order
    "total_tokens": int,         # sum of input+output tokens for every LLM call inside this loop
}
```

`run_single_task` consumes this dict, calls the verifier when appropriate, and writes the TSV row. See [benchmark.md](./benchmark.md).
