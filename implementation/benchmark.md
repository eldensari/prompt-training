# `benchmark.py`

> Sourced from: v2.7.9 §benchmark.py — A/B experiment + automatic measurement
> Related: [inverse.md](./inverse.md), [react-loop.md](./react-loop.md), [agent-tools.md](./agent-tools.md), [gaia-integration.md](./gaia-integration.md), [caching.md](./caching.md), [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md)

---

## Role

`benchmark.py` is the experiment runner. It loads the GAIA task set, runs each task under both conditions, calls the verifier, writes the result table, and logs cost. Everything that touches a task at the experiment level lives here.

The function call graph is three layers deep:

```
run_experiment()
  └─ load_gaia_tasks()                              → see gaia-integration.md
  └─ for each task:
       run_task_both_conditions(task)
         ├─ measure / cache H_raw (shared A/B)
         ├─ run_single_task(task, condition="A", ...)
         │    └─ run_react_loop(...)                → see react-loop.md
         │    └─ if completed: question_scorer(...) → see gaia-integration.md
         ├─ inverse(task["Question"])               → see inverse.md
         ├─ measure H_improved (deliberately not cached, see caching.md)
         └─ run_single_task(task, condition="B", ...)
  └─ write_tsv(rows)
  └─ log cost summary
```

---

## File header

```python
"""
prompt-training/benchmark.py

A/B experiment runner for the inverse-model hypothesis.
  - Condition A: raw prompt → ReAct agent (baseline)
  - Condition B: raw prompt → inverse() → improved prompt → ReAct agent

Usage:
  python benchmark.py                    # run the full task set (3 full runs max)
  python benchmark.py --task 0           # run only one task (filtered-list index)
  python benchmark.py --condition A      # only condition A
  python benchmark.py --condition B      # only condition B
  python benchmark.py --model sonnet     # specific model
  python benchmark.py --n-samples 5      # entropy sample count (quick test)
  python benchmark.py --no-cache         # disable all caches

Required environment variables (.env):
  ANTHROPIC_API_KEY=sk-ant-...
  OPENAI_API_KEY=sk-...          (optional, if using OpenAI)
  GOOGLE_API_KEY=...             (optional, if using Gemini)
  TOGETHER_API_KEY=...           (required for embedding-based clustering)
  HF_TOKEN=...                   (required for GAIA dataset access)
  TAVILY_API_KEY=tvly-...        (required for agent web search)
"""
```

The `--no-cache` flag and the per-flag CLI semantics are part of the operational contract — see [../operations/reproducibility.md](../operations/reproducibility.md) for which combinations are valid for result-producing runs vs smoke tests.

---

## Top-level constants

```python
MODEL = "claude-sonnet-4-6"   # example; set at implementation time
N_SAMPLES = 10
CACHE_VERSION = "v2.7.9-001"
SEED = 42
```

`MODEL` and `N_SAMPLES` are CLI-overridable. `CACHE_VERSION` is the cache invalidation knob — see [caching.md](./caching.md). `SEED` covers any randomness in the implementation that is not already deterministic by construction (the embedding model and clustering library are deterministic; this seed exists for `numpy` and any future stochastic operations).

---

## `run_experiment()`

Top-level: iterate over all tasks, run both conditions, write the TSV.

```python
def run_experiment():
    tasks = load_gaia_tasks()
    apply_sample_size_contingency(tasks)   # see gaia-integration.md

    rows = []
    log_cost_start()
    for task in tasks:
        rows.extend(run_task_both_conditions(task))
    write_tsv(rows)
    log_cost_end()
```

Cost logging happens at run start and run end — see [../operations/cost-monitoring.md](../operations/cost-monitoring.md). The sample-size contingency is applied at first load and locked thereafter — see [gaia-integration.md §Sample size contingency](./gaia-integration.md#sample-size-contingency).

---

## `run_task_both_conditions(task)`

Run one task under both A and B. Returns a list of two rows.

```python
def run_task_both_conditions(task):
    task_key = _cache_key(task["task_id"], MODEL, N_SAMPLES)

    # Step 1: H_raw (shared between A and B)
    cached = cache_get("h_raw", task_key)
    if cached is not None:
        H_raw = cached["H_raw"]
        raw_summary = cached["raw_summary"]
    else:
        raw_summary = summarize_to_head(task["Question"], max_tokens=80, model=MODEL)
        H_raw = measure_semantic_entropy(
            f"{MINIMAL_INSTRUCTION}\n\n{raw_summary}", MODEL, N_SAMPLES
        )
        cache_set("h_raw", task_key, {"H_raw": H_raw, "raw_summary": raw_summary})

    # Step 2: Condition A
    row_A = run_single_task(
        task, condition="A", H_raw=H_raw, H_improved=H_raw,
        summarized_query=raw_summary, model=MODEL
    )

    # Step 3: Condition B — inverse() with its own cache
    cached_inv = cache_get("inverse", task_key)
    if cached_inv is not None:
        improved_prompt = cached_inv["improved_prompt"]
    else:
        inverse_result = inverse(task["Question"], MODEL, N_SAMPLES)
        cache_set("inverse", task_key, inverse_result)
        improved_prompt = inverse_result["improved_prompt"]

    # H_improved: deliberately NOT cached — inverse cache corruption surfaces here
    improved_summary = summarize_to_head(improved_prompt, max_tokens=80, model=MODEL)
    H_improved = measure_semantic_entropy(
        f"{MINIMAL_INSTRUCTION}\n\n{improved_summary}", MODEL, N_SAMPLES
    )

    row_B = run_single_task(
        task, condition="B", H_raw=H_raw, H_improved=H_improved,
        summarized_query=improved_summary, model=MODEL
    )

    return [row_A, row_B]
```

Three things to notice:

1. **`H_raw` is shared across A and B.** It is computed once (or fetched from cache once) and passed into both `run_single_task` calls. Condition A's row also records `H_improved = H_raw` and `delta_H = 0`.
2. **`inverse()` is cached, but the post-inverse `H_improved` measurement is not.** This is a deliberate sanity check on the `inverse` cache — if the cache is corrupted or stale, the freshly recomputed `H_improved` will disagree with `inverse_result["H_improved"]`, surfacing the problem immediately. The reasoning is in [caching.md](./caching.md).
3. **Both calls to `run_single_task` pass `H_raw=H_raw`** — never `H_improved` for condition B. This is the same `H_raw` for both. The loop detector inside `run_react_loop` uses this as the per-task threshold reference. See [../spec/loop-detection.md §(c)](../spec/loop-detection.md#c-why-h_raw-is-the-reference-in-both-a-and-b-not-h_improved-in-b).

---

## `run_single_task(task, condition, H_raw, H_improved, summarized_query, model)`

Run one task under one condition. Returns one TSV row.

```python
def run_single_task(task, condition, H_raw, H_improved, summarized_query, model):
    result = run_react_loop(
        summarized_query=summarized_query,
        model=model,
        max_steps=task["max_steps"],
        H_raw=H_raw,   # for loop detection reference
    )
    # result: {terminated_by, final_answer, entropy_curve, total_tokens}

    # Verifier: called exactly once, only when completed
    if result["terminated_by"] == "completed":
        verifier_passed = question_scorer(result["final_answer"], task["Final answer"])
    else:
        verifier_passed = "N/A"

    return {
        "task_id": task["task_id"],
        "level": task["Level"],
        "condition": condition,
        "H_raw": H_raw,
        "H_improved": H_improved,
        "delta_H": (H_raw - H_improved) if condition == "B" else 0,
        "loop_count": 1 if result["terminated_by"] == "loop_detected" else 0,
        "total_tokens": result["total_tokens"],
        "terminated_by": result["terminated_by"],
        "verifier_passed": verifier_passed,
    }
```

The verifier is called **exactly once per task per condition**, and only when `terminated_by == "completed"`. For the other three terminated_by values, `verifier_passed = "N/A"` — see [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md).

The `delta_H` field is only populated for condition B. Condition A always records `delta_H = 0` because `H_improved = H_raw` for that condition by definition.

---

## `run_react_loop`

Implemented in detail in [react-loop.md](./react-loop.md). The header is:

```python
def run_react_loop(summarized_query, model, max_steps, H_raw):
    """
    The ReAct loop itself. Implements steps [a]–[h] from the per-step flow.
    Named run_react_loop (not run_agent) to distinguish from t2.5 terminology.
    Returns: {terminated_by, final_answer, entropy_curve, total_tokens}
    """
    # ... see react-loop.md for the [a]–[h] flow ...
```

---

## TSV output schema

```
task_id  level  condition  H_raw  H_improved  delta_H  loop_count  total_tokens  terminated_by  verifier_passed
```

### Recording rules

- **Condition A**: write `H_improved = H_raw`, `delta_H = 0`. The `H_raw` value itself is recorded normally.
- **Condition B**: write the freshly measured `H_improved` and the computed `delta_H = H_raw − H_improved`.
- `loop_count = 1` iff `terminated_by == "loop_detected"`, else 0.
- `verifier_passed ∈ {"True", "False", "N/A"}`. It is `"N/A"` whenever `terminated_by != "completed"`.
- `level` is sourced from GAIA for each task (always 1 in v0).

The TSV is the canonical record. Every metric in [../analysis/metrics.md](../analysis/metrics.md) is derived from these columns. The schema is **not editable** without a version bump — see [../operations/experiment-rules.md](../operations/experiment-rules.md).

---

## Cross-references

- [react-loop.md](./react-loop.md) — the [a]–[h] per-step flow
- [inverse.md](./inverse.md) — `inverse()`, `summarize_to_head`, `measure_semantic_entropy`
- [agent-tools.md](./agent-tools.md) — the three tools the agent has access to
- [gaia-integration.md](./gaia-integration.md) — `load_gaia_tasks`, `apply_sample_size_contingency`, `question_scorer`, `max_steps`
- [caching.md](./caching.md) — `_cache_key`, `cache_get`, `cache_set`, why `H_improved` is not cached
- [../operations/cost-monitoring.md](../operations/cost-monitoring.md) — `log_cost_start`, `log_cost_end`
- [../operations/reproducibility.md](../operations/reproducibility.md) — temperatures, seed, task order
