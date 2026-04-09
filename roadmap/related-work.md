# How this differs from prior work

> Sourced from: v2.7.9 §How this differs from prior work, §References
> Related: [../spec/hypothesis.md](../spec/hypothesis.md), [../spec/measurement.md](../spec/measurement.md), [v0-v1-plan.md](./v0-v1-plan.md)

---

## The comparison table

There is existing work on every individual piece of this project — inverse models in motor neuroscience, entropy-based loop detection, prompt refinement at inference time, semantic uncertainty as a metric, training-time entropy regularization. None of them combine the three things this project combines.

| Prior work | What this project adds |
|---|---|
| **Wolpert & Kawato (1998)** — forward / inverse model theory for motor control | Applies the cognitive control model to **prompt refinement for LLM agents**. The mapping from `motor command` to `refined prompt` is metaphorical — see [../spec/hypothesis.md §What this is not](../spec/hypothesis.md#what-this-is-not) — but the functional structure (work backward from a desired outcome to the required inputs) is preserved. |
| **Correa & de Matos (2025)** — *Entropy-Guided Loop*: an inference-time refinement loop triggered by token-level uncertainty | Removes entropy **before execution (pre-processing)**, not during execution. This project's question is whether the loop pathology can be avoided in advance, not whether it can be exited once entered. |
| **Pandita et al. (2025)** — *ProRefine* (NeurIPS): an agentic loop that refines prompts at inference time using textual feedback | Quantifies the effect with **the entrance/exit entropy difference (ΔH)**. ProRefine refines based on feedback signals; this project refines once, up front, and measures the effect with a numeric metric that does not depend on a feedback loop. |
| **Xu et al. (2025)** — *EPO*: entropy control during multi-turn LLM agent RL training | Measures **ΔH at inference time**, not during training. EPO is a training-time intervention; this project changes nothing about how the agent is trained and only modifies what it sees at inference. |
| **Kuhn et al. (2023)** — *Semantic Uncertainty* (ICLR Spotlight): entropy measurement based on semantic equivalence | Re-purposes Semantic Entropy as **a metric for the effect of pre-processing (ΔH)**, rather than as a metric of QA uncertainty per se. The clustering and Shannon-entropy formula come directly from Kuhn et al.; the application is novel. |

## What nobody has put together

The contribution of this project is the *combination*:

1. **Apply the inverse model from motor neuroscience to prompt refinement** — borrowing the functional structure (`g(x*_{t+1}, x_t) → u_t`) from Wolpert & Kawato (1998) and instantiating it as a 3-step prompt chain. See [../spec/hypothesis.md](../spec/hypothesis.md).

2. **Measure the semantic entropy of the raw and improved prompts using the same question** — re-purposing Kuhn et al.'s metric and holding the measurement question, system prompt, and summarization pipeline identical on both sides so that the difference is interpretable. See [../spec/measurement.md](../spec/measurement.md).

3. **Test, A/B, whether pre-processing reduces the agent loop rate on a standardized benchmark (GAIA)** — using GAIA's official scorer, the False Positive and False Negative controls, and the loop detector based on `d²H/dt²`. See [../spec/loop-detection.md](../spec/loop-detection.md), [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md), and [../implementation/gaia-integration.md](../implementation/gaia-integration.md).

Each piece individually exists. The combination — applying the cognitive-control inverse model as a pre-processing step, measuring its effect with semantic entropy, and validating against a standardized benchmark with a quasi-exact-match scorer — is what this project tests.

## A note on what is *not* claimed

Re-stating from [../spec/hypothesis.md §What this is not](../spec/hypothesis.md#what-this-is-not), so a prior-work reviewer doesn't have to chase a link:

- This is **not a faithful biological model** of motor control. The Wolpert-Kawato architecture is borrowed for its functional structure, not as a neuroscience claim. A better-grounded biological framing is in Cooper (2010), but the present project does not depend on it.
- This is **not a prompt optimization study**. The Target / Invert / Compose templates are not tuned per task. They are fixed pre-processing.
- This is **not a model comparison**. All LLM roles run the same model in v0.
- This is **not a loop-avoidance trick for production**. Whether anyone would actually want this in front of a production agent depends on the cost vs. benefit numbers from [../analysis/metrics.md](../analysis/metrics.md), which the experiment measures but does not optimize.

These caveats matter for the lit review because they clarify the *scope* of the contribution: a reader who reads the title as "an inverse-model-based prompt optimizer" will be disappointed; a reader who reads it as "a controlled measurement of whether one specific kind of pre-processing reduces one specific kind of failure" will not.

---

## References

- **Wolpert, D.M. & Kawato, M.** (1998). *Multiple paired forward and inverse models for motor control.* Neural Networks, 11(7-8), 1317-1329.
- **Kuhn, L., Gal, Y., & Farquhar, S.** (2023). *Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation in Natural Language Generation.* ICLR 2023 (Spotlight). arXiv:2302.09664.
- **Cooper, R. P.** (2010). *Forward and Inverse Models in Motor Control and Cognitive Control.* Proceedings of the International Symposium on AI-Inspired Biology, AISB 2010 Convention, 108-110.
- **Ren, A. Z., Ichter, B., & Majumdar, A.** (2024). *Thinking Forward and Backward: Effective Backward Planning with Large Language Models.* arXiv:2411.01790.
- **Correa, A. G. A. & de Matos, A. C. H.** (2025). *Entropy-Guided Loop: Achieving Reasoning through Uncertainty-Aware Generation.* arXiv:2509.00079.
- **Pandita, D., Weerasooriya, T. C., Shah, A., Homan, C. M., & Wei, W.** (2025). *ProRefine: Inference-time Prompt Refinement with Textual Feedback.* NeurIPS 2025. arXiv:2506.05305.
- **Xu, W., Zhao, W., Wang, Z., Li, Y.-J., Jin, C., Jin, M., Mei, K., Wan, K., & Metaxas, D. N.** (2025). *EPO: Entropy-regularized Policy Optimization for LLM Agents Reinforcement Learning.* arXiv:2509.22576.
- **Mialon, G. et al.** (2023). *GAIA: A Benchmark for General AI Assistants.* arXiv:2311.12983.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The five-row prior-work comparison | Editable | A literature review. New related work appears regularly and the table should be updated as it does. |
| The three-point "what nobody has put together" framing | Editable | This is the contribution claim. It may be sharpened based on first-run results or based on a reviewer's framing. |
| The "what is *not* claimed" section | Editable | Caveats. They should track [../spec/hypothesis.md](../spec/hypothesis.md); if the hypothesis file's "What this is not" section changes, this list should follow. |
| The reference list | Editable | Citations are added as the literature evolves. |

This is **roadmap material** — every row is editable. The methodological commitments referenced from this file (the hypothesis, the measurement design, the loop detector) are load-bearing; the prior-work framing of those commitments is not.
