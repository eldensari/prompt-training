# Deferred to v1 or later

> Sourced from: v2.7.9 §Deferred to v1 or later
> Related: [v0-v1-plan.md](./v0-v1-plan.md), [related-work.md](./related-work.md)

---

## What this file is about

A list of things that were *considered* for v0 and explicitly held out, with the reason for each. Holding things out is part of the v0 design — the experiment exists to test one hypothesis with one variable, and every additional axis would either confound the result or multiply the cost beyond the rerun budget.

This is not a wishlist. It is a deliberately curated list of "we know about this, we understand why it would matter, and we're not doing it now."

---

## The list

| Item | Reason for deferral |
|---|---|
| **Asymmetric model ablation** (inverse vs agent on different models) | v0 variable minimization. The single-model policy ([../implementation/agent-tools.md §LLM model](../implementation/agent-tools.md#llm-model-single-model-policy)) is what makes the A/B comparison about the inverse model rather than about which LLM is doing what. v1 may explore configurations where, for example, a stronger model runs `inverse()` while a cheaper one runs the agent — but only after v0 establishes that the inverse model has any effect at all. |
| **Multimodal GAIA tasks** (Levels 2/3 with file attachments) | v0 is text-only. Multimodal processing is a separate axis of capability that would confound the loop-rate measurement: a Level 2 task that loops because the agent can't process an image is not testing the same thing as a Level 1 task that loops because the prompt is ambiguous. The two-stage filter in [../implementation/gaia-integration.md §Loader](../implementation/gaia-integration.md#loader-two-stage-filter) explicitly excludes both file-attached tasks and text-only tasks that reference video/audio URLs. |
| **Self-authored ambiguous task set with LLM-judge verifier** | v0 maintains a single scoring pipeline (GAIA's quasi-exact-match scorer, vendored bit-exact). Introducing an LLM-judge would add a new noise source that would have to be calibrated against human judgment before its results could be combined with the GAIA-scored results. This becomes relevant in [v0-v1-plan.md](./v0-v1-plan.md) Case 4 — *"GAIA H_raw distribution is too low"* — where an ambiguation step would be the v1 fix. |
| **Forward model activation** (Predict-Compare cycle from Wolpert-Kawato) | The 80/70/150 token budget reserves space for it, but v0 does not exercise it. The decision to activate the forward model is conditioned on a positive v0 result — see [v0-v1-plan.md §Case 1](./v0-v1-plan.md#case-1-it-works) and [../spec/hypothesis.md §How the full Wolpert-Kawato architecture extends this](../spec/hypothesis.md#how-the-full-wolpert-kawato-architecture-extends-this). |
| **Per-task-category inverse system prompt specialization** | Requires v0 result analysis. There is no point in specializing prompts by task category before establishing that the inverse model has any baseline effect at all, and there is no point in deciding *which* categories matter before seeing where v0's effect is concentrated. This becomes the natural v1 step in [v0-v1-plan.md §Case 3](./v0-v1-plan.md#case-3-partial-effect). |
| **Korean-language task robustness sub-result** | Single English scoring pipeline decision. GAIA's verifier is English-only; supporting Korean would require either a separate scoring pipeline (rejected — see [../implementation/gaia-integration.md §Why no self-authored tasks](../implementation/gaia-integration.md#why-no-self-authored-tasks)) or an LLM-judge (deferred — see the row above). The prior draft (v2.7.8 t-track) included Korean tasks; v2.7.9 dropped them and v2.8.0 maintains the drop. This is intentional and is not to be reversed even if asked. |
| **Level-stratified analysis** | v0 uses Level 1 only. Level-stratified analysis is meaningful once Level 2 is added in v1 (after multimodal handling is in place), and it's the natural framing for [v0-v1-plan.md §Case 3](./v0-v1-plan.md#case-3-partial-effect). |

---

## What's not on this list

Things that were considered and rejected outright (not deferred) are not here. The clearest examples:

- **Mid-experiment hyperparameter tuning** is not deferred — it is forbidden by the rerun budget rule in [../operations/rerun-budget.md](../operations/rerun-budget.md). "Reconsideration means returning to the spec."
- **Removing the single-model policy in v0** is not deferred — it is what v0 is *for*. v1 may relax it; v0 is about the simplest meaningful test.
- **Adding more agent tools** is not deferred to a specific version — it is held out indefinitely as an experimental-variable concern. New tools would be added only if a specific v1 hypothesis required them.

The distinction matters because "deferred" means "we plan to come back to this" while "rejected" means "doing this would defeat the purpose of the experiment." A reader looking at this list should understand that the seven items above are *valid future work*, not abandoned ideas.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The list of seven deferred items | Editable | A v1 planning artifact. New items can be added; existing items can be promoted to the v1 plan once their preconditions are met. |
| The "reason for deferral" justifications | Editable | These should track the spec — if the spec changes, a deferral reason may change too. |
| The "what's not on this list" section | Editable | A clarification, not a rule. |
| Per-paragraph wording | Editable | Explanation. |

This file is **roadmap material** and contains no load-bearing methodology. Every row is editable. Updates are expected as v0 finishes and v1 takes shape.
