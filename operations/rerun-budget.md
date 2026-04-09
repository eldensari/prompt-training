# v0 rerun budget

> Sourced from: v2.7.9 §v0 budget and rerun discipline
> Related: [cost-monitoring.md](./cost-monitoring.md), [experiment-rules.md](./experiment-rules.md), [../roadmap/v0-v1-plan.md](../roadmap/v0-v1-plan.md)

---

## The rule

> **v0 rerun budget: at most 3 full runs of the GAIA Level 1 text-only set.** If 3 runs do not produce a clear result (a statistically significant ΔH effect on loop rate, OR a clear null result), the design is reconsidered before a 4th run. "Reconsideration" means returning to the spec, not adjusting hyperparameters in place.

This rule lives in `README.md` as a project rule. It is not enforced in code; it is enforced by discipline. The codebase will happily run a fourth or fifth time.

## Why "reconsideration" means returning to the spec

The failure mode this rule is designed to prevent is **unbounded hyperparameter tuning** — the loop where each run produces an inconclusive result, the experimenter tweaks one threshold or one prompt template "just to see what happens," runs again, sees a different inconclusive result, and tweaks again. After enough iterations the experiment has been redefined into something the original spec no longer describes, and any "positive result" is overfit to the tweaks.

The discipline is: if 3 runs cannot produce a clear answer, the answer is not "tune harder." The answer is one of:

- The hypothesis is wrong, and we record a null result.
- The measurement apparatus is measuring the wrong thing, in which case the spec needs to change *deliberately* — see [../roadmap/v0-v1-plan.md](../roadmap/v0-v1-plan.md) for the branching rules.
- The task set is wrong (e.g., GAIA Level 1 is uniformly low-entropy and doesn't exercise the inverse model), in which case a different task set is a v1 question.

In all three cases the next step is a spec edit, not a parameter twiddle. The version bump rule from [experiment-rules.md](./experiment-rules.md) is the gate.

## Estimated v0 budget (3 runs total, with caching enabled)

These are estimates from the original v2.7.9 spec. Actual numbers come from the cost-monitoring log on the first run — see [cost-monitoring.md](./cost-monitoring.md). Do not commit to 3 runs upfront. **Execute the first full run, review the cost log, then decide.**

- **Tavily**: approximately 600–1,200 calls total. Free tier (1,000/month) is borderline. First run will reveal the actual figure. If exceeded, upgrade to Project plan (~$30/month, 4,000 credits).

- **LLM** (Sonnet baseline, with caching):
  - Entropy measurement sampling: ~$25/run × 3 ≈ $75
  - ReAct agent calls: ~$15/run × 3 ≈ $45
  - `inverse()` + summarization (cache-hit heavy): ~$5/run × 3 ≈ $15
  - **Total: ~$135**

- **Recommended budget allocation**: $150 for LLM, free tier for Tavily initially.

The single largest variance in the LLM estimate is the agent's per-task step count. A run where many tasks hit `max_steps_reached` will consume more than the estimate. The contingency for that case (raise `max_steps` to 20) is in [../implementation/gaia-integration.md §Contingency rule](../implementation/gaia-integration.md#contingency-rule-max_steps-upward-adjustment) and would shift the LLM estimate upward by roughly 30%.

## What "a clear result" means

The rerun budget exists to bound iteration toward clarity. "Clear" is intentionally not a fixed p-value:

- **Clear positive**: across runs, condition B has a meaningfully lower `loop_count` than condition A, and the effect correlates with per-task ΔH (higher ΔH → bigger B advantage). The size of the effect should be visible by inspection of the result table, not only by statistical test.
- **Clear null**: across runs, condition B's `loop_count` is indistinguishable from A's, *and* ΔH is meaningfully nonzero on a substantial fraction of tasks. (If ΔH is itself near zero everywhere, that is a "task set is wrong" outcome, not a null result for the hypothesis.)
- **Inconclusive**: anything else — high variance between runs, ambiguous correlation, suspicious cluster of `error` rows, or a `max_steps_reached` rate that drives the headline numbers.

The first two end the v0 phase. The third is what the 3-run budget is meant to bound: at most three swings before the spec is reopened.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The 3-run rerun budget | **No, version bump required** | It is the discipline gate. Raising it without a spec edit defeats the rule. |
| The "reconsideration means returning to the spec" interpretation | **No, version bump required** | The rule has no force if "reconsideration" is allowed to mean "tweak a hyperparameter." |
| The cost estimates ($75 / $45 / $15 / ~$135) | Editable | These are projections from the original spec. Real numbers come from the first run's cost log. |
| The Tavily upgrade trigger (free tier vs Project plan) | Editable | Operational, not structural. |
| The "clear positive / clear null / inconclusive" definitions | Editable | These are interpretation guides. Sharpening them based on first-run evidence is allowed and should be recorded in the changelog. |
| Per-paragraph wording | Editable | Explanation. |

The first two rows are load-bearing — they are the rule. The rest is supporting estimate and exposition.
