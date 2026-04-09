# Metrics

> Sourced from: v2.7.9 §Metrics (3 result + 3 process metrics)
> Related: [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md), [../spec/loop-detection.md](../spec/loop-detection.md), [temporal-drift.md](./temporal-drift.md)

---

## What this file is about

The result table has six metrics: three about *what happened* (result metrics, computed after the run) and three about *how H moved* (process metrics, recorded during the run). Every metric reads from exactly one column of the TSV ([../implementation/benchmark.md §TSV output schema](../implementation/benchmark.md#tsv-output-schema)) and is derived under the strict orthogonality rules of [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md).

This file defines the six metrics and the rules for deriving them. The loop *detection* formula itself — `d²H/dt² ≈ 0 AND H > α × H_raw` — lives in [../spec/loop-detection.md](../spec/loop-detection.md) and is not restated here. The two files answer different questions about the same source section: loop-detection.md defines *when* `terminated_by = "loop_detected"` is assigned to a row; this file defines *what gets reported about* the rows that ended up with that value.

---

## The three result metrics

These are computed after the run from the TSV. They are the headline numbers.

| # | Metric | Definition | Why |
|---|--------|-----------|-----|
| 1 | **Loop count** | `count(terminated_by == "loop_detected")` | Direct dependent variable of the hypothesis. |
| 2 | **Token usage** | `sum(input + output tokens)` across all LLM calls | Cost effect of the inverse model, per condition. |
| 3 | **Task correctness rate** | `count(terminated_by == "completed" AND verifier_passed == True) / total_tasks` | Whether the agent actually produced correct answers. |

### Derivation rules

Each metric reads from exactly one column at a time. **Never collapse `terminated_by` and `verifier_passed`** — that re-introduces the False Negative bug from [../spec/termination-taxonomy.md §False Negative control](../spec/termination-taxonomy.md#false-negative-control-completion-vs-correctness). The correctness rate filters first by `terminated_by`, then checks `verifier_passed`. Strict order, never the reverse, never a fused boolean.

The loop count reads only from `terminated_by`. It does not look at `verifier_passed` at all — by definition, a row with `terminated_by = "loop_detected"` has `verifier_passed = "N/A"`, so there is nothing to look at.

Token usage reads only from the `total_tokens` column. The single number per row aggregates everything (entropy sampling, agent reasoning, tool dispatch). Per-condition totals are what feed the cost-effect comparison.

### Why these three and not more

These are the v0 minimal set. The reason there are only three:

- **Loop count** is the dependent variable — the experiment exists to measure this.
- **Token usage** is the cost variable — it's the price tag on the loop reduction (if any).
- **Correctness rate** is the safety variable — it's how we detect "B reduces loops by producing confidently wrong answers," which would be a pyrrhic win.

Adding a fourth result metric would either duplicate one of these or introduce a new dependent variable that the experiment was not designed to test. v1 candidates (completion time, TTFMA, pivot count, spec match, error recovery rate, number of human interventions) are listed at the end of this file but are not part of v0.

---

## The three process metrics

These are recorded during the run, one value per step per task per condition. They are stored in `results/entropy_curves/` and feed loop detection.

| # | Metric | What it measures |
|---|--------|------------------|
| 4 | **H (entropy)** | Uncertainty level at each step. |
| 5 | **dH/dt (velocity)** | Rate of entropy decrease between consecutive steps. |
| 6 | **d²H/dt² (acceleration)** | Acceleration / deceleration of the decrease — the signature the loop detector watches for. |

The first two are observable on the entropy curve directly. The third is what the loop detector consumes — see [../spec/loop-detection.md §(a)](../spec/loop-detection.md#a-why-the-second-derivative-and-not-the-first) for why the second derivative (rather than the first) is the load-bearing test.

These are *measurements*, not *targets*. Nothing in the experiment is optimized to push H or its derivatives in any particular direction. The agent runs against the same context budget regardless of how H is moving; the only operational consequence of these process metrics is that `detect_loop` reads the latest few values to decide whether to terminate.

### How the process metrics map to the result metrics

| Process metric | Used by |
|---|---|
| H, dH/dt | Recorded for analysis. Plottable per task. Not directly consumed by any termination rule. |
| d²H/dt² | Consumed by `detect_loop` together with H. The result is the assignment of `terminated_by = "loop_detected"`, which then feeds result metric #1. |

So the process-metric-to-result-metric chain is: `(H, d²H/dt²)` → `detect_loop` → `terminated_by` → `loop_count`. The process metrics are not metrics of the *experiment's outcome*; they are instrumentation that the dependent variable is built on top of.

---

## How the termination taxonomy maps to the metrics

Every TSV row lands in exactly one cell of the 4×3 grid in [../spec/termination-taxonomy.md §Two orthogonal columns](../spec/termination-taxonomy.md#two-orthogonal-columns). Each metric counts a specific subset of cells:

```
loop_count       ← rows where terminated_by == "loop_detected"
correct_count    ← rows where terminated_by == "completed" AND verifier_passed == True
error_count      ← rows where terminated_by == "error"          (reported, not in headline 3)
budget_count     ← rows where terminated_by == "max_steps_reached" (reported, not in headline 3)
```

The four counts sum to the total task count (with `correct_count` plus the wrong-answer count making up the `completed` total). No row is counted twice; no row escapes counting.

`error_count` and `budget_count` are not part of the three headline metrics, but they are reported in the run summary. If `error_count / total > 10%` the run is excluded from analysis ([../operations/failure-modes.md](../operations/failure-modes.md)). If `budget_count / total > 20%` the contingency in [../implementation/gaia-integration.md §Contingency rule](../implementation/gaia-integration.md#contingency-rule-max_steps-upward-adjustment) raises `max_steps`.

---

## Reading correctness with temporal drift in mind

The correctness rate (#3) is not the final word. GAIA's 2023 ground truth can disagree with 2026 reality on "current state" questions, and the verifier will mark a present-day-correct answer as wrong. The handling rule (manual post-run review, separate temporal-mismatch category) is in [temporal-drift.md](./temporal-drift.md). The primary correctness rate excludes temporal-mismatch tasks; the unadjusted number is reported alongside as a sanity check.

This adjustment is a *post-run* analysis step, not an automated one. The TSV row stores `verifier_passed` as it came from the scorer; the temporal-mismatch flag is an additional column or annotation produced by the manual review pass.

---

## v1 candidate metrics

Listed for the record. None are computed in v0:

- **Completion time** — wall clock per task per condition.
- **TTFMA** (time to first meaningful action) — how many steps until the agent does something other than re-read the prompt.
- **Pivot count** — how many times the agent changes search strategy mid-task.
- **Spec match** — for self-authored tasks with structured expected outputs (deferred to v1; v0 uses GAIA's quasi-exact-match scorer instead).
- **Error recovery rate** — for runs where transient infrastructure errors happen, how often the agent successfully continues.
- **Number of human interventions** — only meaningful in a human-in-the-loop context, not v0.

These are listed in [../roadmap/v0-v1-plan.md](../roadmap/v0-v1-plan.md).

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The three result metrics (loop count, token usage, correctness rate) | **No, version bump required** | They are the dependent variables of the hypothesis. Changing or removing one redefines the experiment. |
| The three process metrics (H, dH/dt, d²H/dt²) | **No, version bump required** | The loop detector depends on them in the form defined here. |
| Strict-order derivation (filter by `terminated_by` first, check `verifier_passed` second) | **No, version bump required** | Reversing the order or fusing the columns re-introduces the False Negative bug. |
| The "one column, one source" rule for derived metrics | **No, version bump required** | This is what keeps the False Positive and False Negative controls effective. |
| The list of v1 candidate metrics | Editable | A roadmap, not methodology. New candidates can be added; existing ones can be removed if a v1 design moves in a different direction. |
| Per-paragraph wording, the chain-diagram, the v1 list | Editable | Explanation. |

The first four rows are load-bearing — they are the result-table contract. The rest is exposition and forward-looking material.
