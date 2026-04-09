# v0 → v1 expansion plan

> Sourced from: v2.7.9 §v0 → v1 expansion plan, §Expected outcomes
> Related: [deferred.md](./deferred.md), [related-work.md](./related-work.md), [../operations/rerun-budget.md](../operations/rerun-budget.md), [../spec/hypothesis.md](../spec/hypothesis.md)

---

## Branching by v0 outcome

The v1 plan is conditional on what v0 produces. There are four cases, and each has its own next step. The 3-run rerun budget in [../operations/rerun-budget.md](../operations/rerun-budget.md) is the gate that decides which case we're in.

### Case 1: it works

> Condition B has meaningfully fewer loops than condition A; ΔH correlates with the per-task loop-rate difference; correctness rate in B is at least as high as in A.

**Next step**: add a forward model. Run a third condition C = inverse + forward. The forward model verifies during execution against the Target produced by the inverse model's first step — see [../spec/hypothesis.md §How the full Wolpert-Kawato architecture extends this](../spec/hypothesis.md#how-the-full-wolpert-kawato-architecture-extends-this). The 80/70/150 token budget already reserves space for the Predict-Compare cycle ([../spec/token-budget.md](../spec/token-budget.md)), so v1 can activate the forward model without changing the budget — which is the precondition for any v1 H values being comparable to v0 H values.

### Case 2: it doesn't work

> No significant loop-count difference between A and B, *and* ΔH is meaningfully nonzero on a substantial fraction of tasks.

**Next step**: add entropy measurement at the intermediate steps of `inverse()` (after Target, after Invert) to diagnose **where information is lost**. This requires a new methodology that makes intermediate measurements comparable — different question, different denominator, see [../spec/measurement.md §Why only two points](../spec/measurement.md#why-only-two-points) for why v0 deliberately did *not* take intermediate measurements. v1 would need its own argument for why the new measurements are valid.

If the diagnosis points to Target (the "what does done look like" step is producing vague targets), the next sub-step is sharpening the Target prompt. If it points to Invert (the backward chain is dropping information), the next sub-step is rethinking the macro-level backward chaining stop conditions. Either way, the diagnosis comes first.

### Case 3: partial effect

> Some tasks show a clear B advantage, others don't, and there's no obvious correlation with ΔH alone.

**Next step**: per-level analysis (Level 1 vs 2 vs 3, once Level 2 is added) and per-question-type analysis. The hypothesis here would be that the inverse model helps on some categories of task and not others, and the v1 work is to **specialize** the inverse-model system prompt by category.

This is also the case where the responsibility predictor from the full Wolpert-Kawato architecture starts to matter — the paper's RP is exactly a router that picks the right specialized inverse model based on task category. v0 doesn't justify investment in an RP yet; v1's per-category analysis is what would.

### Case 4: GAIA H_raw distribution is too low

> Across the task set, H_raw is uniformly small. The inverse model has nothing to remove because the queries are already clear enough.

**Next step**: introduce an **ambiguation** step in v1, with a self-authored ambiguous task set verified by an LLM-judge as a sub-result. This is the riskiest of the four branches because it involves leaving GAIA's bit-exact scorer behind, and the LLM-judge introduces a new noise source. The work would be: build the self-authored task set, validate it against a small held-out human-judged sample, then run A/B with the LLM-judge as the verifier and report the agreement rate with the human judgments alongside the headline numbers.

This case also implies that GAIA Level 1 was the wrong choice of benchmark for the hypothesis in question — not because GAIA is bad, but because its difficulty axis is "multi-step retrieval" rather than "ambiguity," and the hypothesis is about the latter. v1 would either move to a different existing benchmark or build one.

---

## Expected outcomes (if results are significant)

These are the artifacts the project would produce in the success case.

- **Paper**: *"Inverse Model Pre-processing Reduces Agent Failure: An Entropy-Based Analysis on GAIA"* — built on the condition A vs B comparison, with ΔH as the explanatory variable.
- **Open-source tool**: `pip install prompt-training` — a general pre-processor attachable in front of any agent. The interface is a single function that takes a raw prompt and returns an improved prompt; the entropy measurement is exposed but optional.
- **Contribution framework**: anyone can modify the Target / Invert / Compose prompts in `inverse.py` and re-run `benchmark.py` for comparison. The editability rules in [../operations/experiment-rules.md](../operations/experiment-rules.md) make clear what they can and can't change while still producing comparable results.

The paper, the package, and the contribution framework are all conditional on v0 producing a clear positive result (Case 1 above). A clear null result (Case 2) becomes a different paper with the same dataset and the same methodology — *"Pre-processing Does Not Reduce Agent Loops on GAIA Level 1: A Negative Result"* — which is also a useful contribution.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The four-case branching (works / doesn't / partial / H_raw too low) | Editable | This is a forward-looking plan, not a methodology rule. The first run's results may suggest a fifth case or merge two cases. |
| The "diagnose first, then decide" principle inside each case | Editable | Same reason — operational guidance for v1 planning. |
| The expected-outcomes list (paper, package, contribution framework) | Editable | Aspirational. |
| Per-paragraph wording, the descriptions of each case | Editable | Explanation. |

This file is **roadmap material**. It does not contain load-bearing methodology rules — those live in `spec/`. The editability table is included for consistency with the rest of the repo, but every row is editable and no row requires a version bump. Updates are expected as v0 evidence accumulates.
