# Reproducibility

> Sourced from: v2.7.9 §Reproducibility
> Related: [../spec/measurement.md](../spec/measurement.md), [../implementation/benchmark.md](../implementation/benchmark.md), [../implementation/gaia-integration.md](../implementation/gaia-integration.md)

---

## What "reproducible" means here

Two runs of the same task set, with the same code, the same model, the same `N_SAMPLES`, the same `CACHE_VERSION`, and a cleared cache, should produce *the same TSV up to entropy-sampling noise that already cancels in ΔH*. The noise-cancellation argument from [../spec/measurement.md §The cancellation argument](../spec/measurement.md#the-cancellation-argument) is the load-bearing reason this is achievable: every per-task pair `(H_raw, H_improved)` carries the same systematic noise on both sides, so the difference is stable even when individual H values are not.

That is what every rule below is in service of. Each rule pins down one source of variance.

## Task order

GAIA index ascending. `shuffle=False`. Always.

This is not a stylistic preference. The sample composition is locked at first load (see [../implementation/gaia-integration.md §Sample size contingency](../implementation/gaia-integration.md#sample-size-contingency)) and the order in which tasks are run is part of that lock. Two reasons:

1. **Cache key stability across reruns.** The `_cache_key` for a task does not depend on the order tasks are run in, but the *cost monitoring delta* and the per-task token accumulations recorded in `run_<timestamp>.log` do — they are reported in execution order. Comparing two runs is much easier when the rows line up.
2. **Failure forensics.** When a run fails partway through, the recovery rule is "drop the cache for the failed task and rerun from the same index." That rule only works if the task index is stable.

## Per-role temperatures

Different LLM roles use different temperatures, and the assignment is fixed:

| Role | Temperature | Why |
|---|---|---|
| Entropy sampling (`measure_semantic_entropy`) | **0.7** | Intentional variance — we are measuring response spread, so the sampler must produce a distribution. |
| `inverse()` internal calls (Target / Invert / Compose) | **0** | Deterministic refinement. Any randomness here would inject untracked variance into `improved_prompt`, which would propagate into `H_improved`. |
| ReAct agent calls (Thought + Action) | **0** | Deterministic action selection. The agent should be a function of its context, not a function of its sampling. |
| `summarize_to_head` calls | **0** | Deterministic compression. Summarization variance is already absorbed into the H measurement (see [../spec/measurement.md §Why we don't try to remove the noise](../spec/measurement.md#why-we-dont-try-to-remove-the-noise)) — making the summarizer itself stochastic would add a second, uncontrolled source of variance on top of that. |

The fact that 0.7 appears in exactly one place is the entire stochastic surface of the experiment. Everything else is deterministic by construction.

## Embeddings and clustering

- **Embeddings**: Llama-3 via Together AI. Deterministic at the API level — no seeding required. The embedder is intentionally a different model from the generation model; see [../spec/measurement.md §Clustering](../spec/measurement.md#clustering-what-we-ask-of-it).
- **Clustering**: scikit-learn `AgglomerativeClustering(metric="cosine", linkage="average", distance_threshold=0.15)`. Deterministic — no random state, no seeding required.

The combination means: given a fixed set of N=10 sampled responses, the cluster assignment is identical on every machine. The only stochasticity is upstream, in the temperature-0.7 sampling step.

## Other randomness

`SEED = 42` at the top of `benchmark.py`. This covers any code path that uses NumPy or Python's `random` module — currently a small surface, but the seed exists so that any future stochastic operation has a fixed entry point.

## What `--n-samples` overrides do and don't break

The CLI flag `--n-samples` lets a smoke test run with a smaller sample size (typically 3) to verify the pipeline cold without paying the full N=10 cost. Smoke-test outputs:

- **Are valid for**: pipeline correctness checks, cache cold-path verification, cost-monitoring sanity checks.
- **Are not valid for**: the result table. The noise-cancellation argument from [../spec/measurement.md §Sample size: N = 10](../spec/measurement.md#sample-size-n--10) explicitly depends on `N=10`. Smoke-test rows must not be merged into a result-producing TSV.

The implementation should make this hard to do accidentally — for example, by writing smoke-test rows to a separate filename or by tagging them in the TSV. The exact mechanism is left to the implementation; the rule is that result-producing TSV rows are always at `N_SAMPLES = 10`.

## Cache version as a reproducibility lever

Every cache key includes `CACHE_VERSION`. Bumping it invalidates everything. The rule for when to bump (any change to model, `N_SAMPLES`, clustering threshold, or the prompt templates that affect a cached value) is in [../implementation/caching.md §Cache invalidation](../implementation/caching.md#cache-invalidation).

The reproducibility consequence: two runs with different `CACHE_VERSION` strings are *not* expected to be reproducible. They are, by intent, different experiments. The version string is the audit trail.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| Task order = GAIA index ascending, `shuffle=False` | **No, version bump required** | Sample composition is locked; ordering is part of the lock. |
| Per-role temperatures (0.7 for sampling, 0 elsewhere) | **No, version bump required** | The assignment is the entire stochastic surface of the experiment. Changing any value changes what every H means. |
| `N_SAMPLES = 10` for result-producing runs | **No, version bump required** | The noise-cancellation argument depends on it. Smoke-test overrides are allowed but produce non-result data. |
| Embedding model identity (Together AI Llama-3) | **No, version bump required** | A different embedder produces different cluster geometry. |
| `SEED = 42` value | Editable | The value is arbitrary; what matters is that *some* fixed seed is set. |
| The `--n-samples` smoke-test convention (and its non-result status) | Editable | A workflow rule. The structural rule (smoke-test data is not result data) is what is non-editable; the exact filename or tag scheme is implementation-tunable. |
| Per-paragraph wording, the explanation of why each rule exists | Editable | Explanation, not methodology. |

The first four rows are load-bearing — they pin down the variance sources the experiment depends on. The rest is implementation tuning.
