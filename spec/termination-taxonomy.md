# Termination taxonomy

> Sourced from: v2.7.9 §False Positive control, §False Negative control
> Related: [loop-detection.md](./loop-detection.md), [analysis/metrics.md](../analysis/metrics.md)

---

## What this file is about

A single task can end in many ways, and a result table that collapses them into "did the agent finish or not" loses the information we actually care about. This file defines two orthogonal columns — `terminated_by` and `verifier_passed` — and the four termination values that go into the first one. Together they form a complete taxonomy: every task lands in exactly one cell of a 4×3 grid, and every metric the experiment reports is computed from exactly one column at a time.

The taxonomy exists to defend against two specific failure modes of result interpretation:

- **False Positive (loop counted that wasn't a loop)**: a task that ran out of step budget gets recorded as a loop, even though it was just a long task with too few steps.
- **False Negative (success counted that wasn't a success)**: a task whose agent confidently produced a wrong answer gets recorded as "completed," indistinguishable from a task that was actually solved correctly.

These two failures look unrelated at first — one is about *why the task ended*, the other is about *whether the answer was right*. But they have the same root cause: trying to compress two different kinds of information into one column. The fix is the same in both cases: split the column.

---

## Two orthogonal columns

Every row in `results.tsv` carries two columns that together describe how the task ended:

- **`terminated_by`** records *how the task stopped running*. It is one of four values (defined below). Every task has exactly one.
- **`verifier_passed`** records *whether the final answer was correct*. It is `True`, `False`, or `N/A`. It is `N/A` whenever `terminated_by != "completed"`, because there is no final answer to score.

These two columns are **orthogonal**. They must never be collapsed. Every derived metric reads from exactly one of them — never both, never a fused boolean. The complete derivation rules:

```
loop_count       ← count(terminated_by == "loop_detected")
correct_count    ← count(terminated_by == "completed" AND verifier_passed == True)
error_count      ← count(terminated_by == "error")
budget_count     ← count(terminated_by == "max_steps_reached")
```

`loop_count` reads only from `terminated_by`. `correct_count` reads from both, but in a strict order: first filter by termination, then check correctness. Never the reverse, never a single fused column.

The 4×3 grid this defines:

|  | `verifier_passed = True` | `verifier_passed = False` | `verifier_passed = N/A` |
|---|---|---|---|
| **`completed`** | task solved (correct answer) | task answered wrongly (False Negative would have been here) | — (impossible: completed always scores) |
| **`loop_detected`** | — | — | true loop, no answer to score |
| **`max_steps_reached`** | — | — | ran out of budget, no answer to score |
| **`error`** | — | — | infrastructure failure, no answer to score |

Five cells are populated. The two cells in the `completed` row are the entire correctness analysis. Everything else is `N/A` for `verifier_passed`.

---

## The four `terminated_by` values

Each task ends with exactly one of these values. The agent itself does not choose; the value is assigned by `run_react_loop` based on which exit condition fired first.

### `completed`

The agent called `final_answer(...)` and `run_react_loop` exited normally. A final answer string exists and is passed to the verifier.

This is the only termination value for which `verifier_passed` is meaningful. For the other three, there is nothing to score.

### `loop_detected`

The loop detector fired before the agent could call `final_answer`. The detector condition is `d²H/dt² ≈ 0 AND H > α × H_raw`, with α = 0.3 — see [loop-detection.md](./loop-detection.md) for the formula and the rationale.

This is **the dependent variable of the hypothesis**. The whole experiment exists to test whether condition B has fewer `loop_detected` rows than condition A. Every other termination value is something we measure to keep `loop_detected` clean.

### `max_steps_reached`

The agent hit the per-task step limit (`max_steps`, derived from the GAIA Level — 15 for Level 1) without calling `final_answer` and without triggering the loop detector. The task ran for the full budget and was forcibly stopped.

This is the False Positive control value. See the next section for why it exists as its own category.

### `error`

Something in the infrastructure failed in a way the agent couldn't recover from. Concrete cases:

- LLM returned an empty response twice in a row.
- `inverse()` failed twice in a row (only relevant in condition B).
- The agent generated text but no parseable tool call across two retries, and the forced `final_answer` fallback also failed.
- A tool call raised an exception that wasn't a normal Tavily error response.

`error` is **never** a real loop and **never** a completed task. It is its own category. If the rate of `error` exceeds 10% in a run, the run is excluded from analysis and the cause is investigated. See [operations/failure-modes.md](../operations/failure-modes.md) for the full handling rules.

The reason `error` is its own value (rather than being silently retried until success) is the same reason we have the False Positive control: we never want infrastructure noise to be misclassified as something else. An LLM rate-limit retry storm should not look like a loop in the result table.

---

## False Positive control (loop count vs budget exhaustion)

**The problem**: a complex task that legitimately needs more steps than its budget allows can produce an entropy curve whose last few points happen to satisfy `d²H/dt² ≈ 0 AND H > 0.3 × H_raw`. The agent was making real progress but ran out of budget mid-thought. If we record this as a loop, we are mixing two phenomena that have completely different causes.

**Why this matters for the experiment**: condition A's loop count is the headline number. If 40% of A's "loops" are actually budget exhaustions, then a positive result for B might just mean "B happens to finish faster, not that B avoids loops." We would learn nothing about whether the inverse model removes the actual loop pathology.

**The fix is structural, not parametric**. The naive response would be "raise `max_steps` until budget exhaustion stops happening." That doesn't work for two reasons:

1. It pushes cost up linearly while leaving the underlying ambiguity unresolved.
2. It makes the result depend on the choice of `max_steps`. If a reviewer asks "what would have happened with `max_steps = 30`?" we have no answer that doesn't require rerunning.

The structural fix is to **define `loop_detected` and `max_steps_reached` as two separate values from the start**. Now `max_steps` becomes a resource cap, not a variable that affects the experiment's interpretation. Whether `max_steps` is 15 or 30, `loop_count` only counts the rows where the loop detector actually fired before the budget ran out. Tasks that hit the budget show up in `budget_count`, not `loop_count`, no matter what.

This is why the False Positive control is **mandatory** in the sense that no tuning of `max_steps` can substitute for it. `max_steps` becomes a separate, second-order question — "did we give the experiment enough room to run?" — answered by looking at the `budget_count`. There's a contingency rule: if more than 20% of Level 1 tasks end in `max_steps_reached` on the first full run, raise `max_steps` to 20 and rerun. This is a resource adjustment applied equally to both conditions, so it is not an experimental variable. See [implementation/gaia-integration.md](../implementation/gaia-integration.md) for the rule.

**The result**: `loop_count` is now a clean measurement of the hypothesis variable. It does not float with `max_steps`. It does not silently absorb tasks that were just slow.

---

## False Negative control (completion vs correctness)

**The problem**: an earlier draft (v2.7.8.t2.5) treated a task as "completed" as long as the agent produced a final answer, regardless of whether that answer was right. The result was a "completion rate" metric that effectively measured "agent terminated normally" and said nothing about whether the experiment had succeeded.

This is the symmetric failure to the False Positive case. There, we were merging two reasons for failure (loop vs budget). Here, we were merging two outcomes of normal termination (correct vs wrong). In both cases the fix is the same: split the column.

**Why this matters for the experiment**: a run where every agent produced a confident wrong answer would, under the old metric, be indistinguishable from a run where every agent answered correctly. Both would show 100% "completion." The hypothesis is that pre-processing with the inverse model reduces *loops* — but if the price of reducing loops is producing more confident wrong answers, that is not a win, and we need to be able to see that in the result table.

There is also a sharper version of the worry. The inverse model might "succeed" by compressing the task into something the agent can answer without ambiguity, but in doing so might lose information the task actually required. The agent then produces a clean, fast, confident, *wrong* answer. Under the old metric this would look like a B-condition victory. Under the new taxonomy it shows up as `terminated_by = completed, verifier_passed = False`, and the correctness column tells the real story.

**The fix**: add `verifier_passed` as a separate column from `terminated_by`. They are read in strict order: termination first, then correctness. The verifier is GAIA's official quasi-exact-match scorer, vendored bit-exact (see [implementation/gaia-integration.md](../implementation/gaia-integration.md#verifier)). It is called exactly once per task, only when `terminated_by == "completed"`. For all other termination values, `verifier_passed` is `N/A` and is not derived from anything.

**The result**: the third headline metric of the experiment (correctness rate) is now meaningful. It is `count(terminated_by == "completed" AND verifier_passed == True) / total_tasks`, and a run cannot fake a high correctness rate by simply terminating a lot.

---

## Why both controls are the same idea

It is worth saying explicitly: False Positive and False Negative are two instances of one principle — **never compress two distinct kinds of information into one column**.

The False Positive control splits "task ended without an answer" into `loop_detected` vs `max_steps_reached` vs `error`. The False Negative control splits "task ended with an answer" into the cross-product of `completed` with `verifier_passed ∈ {True, False}`. Both controls preserve information that a single column would have erased.

Once you have both controls in place, the result table answers four independent questions instead of one:

1. How often did the agent loop? → `loop_count`
2. How often did the agent run out of budget? → `budget_count`
3. How often did the agent finish and answer correctly? → `correct_count`
4. How often did infrastructure fail? → `error_count`

These four numbers sum to `total_tasks` (with `correct_count` plus the wrong-answer count making up the `completed` total). No information is lost. No metric depends on a parameter choice (like `max_steps`) that should be a resource limit rather than a variable.

This is why the taxonomy belongs in the spec, not in the implementation. The number of values and their definitions cannot be changed without changing what every metric in [analysis/metrics.md](../analysis/metrics.md) means. The taxonomy is part of the experiment's contract with itself.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The set of `terminated_by` values | **No, version bump required** | Adding a fifth value would change the meaning of every existing metric. Removing one would silently re-bucket tasks. |
| The orthogonality of `terminated_by` and `verifier_passed` | **No, version bump required** | Collapsing them re-introduces the False Negative bug. |
| The derived metric formulas (loop_count, correct_count, etc.) | **No, version bump required** | They are the dependent variables of the hypothesis. |
| When the verifier is called (only on `completed`) | **No, version bump required** | Calling it on `loop_detected` or `error` would either crash or produce a meaningless score. |
| The `error` rate threshold (10%) for excluding a run | Editable | This is a quality gate, not a structural element. |
| The `max_steps_reached` contingency threshold (20%) | Editable | This is a resource-tuning rule, not a structural element. |

The first four rows are the load-bearing parts. The last two are heuristics on top.

---

## Cross-references

- [loop-detection.md](./loop-detection.md) — the formula for `terminated_by = "loop_detected"` (`d²H/dt² ≈ 0 AND H > α·H_raw`)
- [analysis/metrics.md](../analysis/metrics.md) — the 6-metric definitions, all of which read from this taxonomy
- [implementation/gaia-integration.md](../implementation/gaia-integration.md) — `max_steps` derivation, contingency rules, verifier vendoring
- [implementation/benchmark.md](../implementation/benchmark.md) — `run_single_task` is the function that assigns `terminated_by` and calls the verifier
- [operations/failure-modes.md](../operations/failure-modes.md) — the full table of error scenarios that map to `terminated_by = "error"`
