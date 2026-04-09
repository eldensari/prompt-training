# Measurement

> Sourced from: v2.7.9 §Measuring semantic entropy, §Handling measurement noise, §Tavily responses and Tail trimming (the entropy parts)

---

## What we are measuring, and why two points

We measure **semantic entropy** at exactly two moments in each task:

- **H_raw** — measured on the original query, before the inverse model touches it.
- **H_improved** — measured on the refined query that the inverse model produced.

The difference is the effect size of pre-processing:

```
ΔH = H_raw − H_improved
```

In condition A (baseline), there is no inverse model, so we record `H_improved = H_raw` and `ΔH = 0`. Condition A still measures H_raw — it's the same number we use as the loop-detection reference (see [loop-detection.md](./loop-detection.md)). In condition B (treatment), both points are measured and their difference is the experimental signal.

Two points, not three or more. The reason is below.

### Why only two points

It would be tempting to also measure entropy after the Target step and after the Invert step, to see "where the entropy actually drops." We deliberately do not.

Each step in the inverse model asks a *different question*. Target asks "what does done look like?" Invert asks "what's needed to get there?" Compose asks "how do I write this as one instruction?" If you measure entropy at each step, you are measuring the variance of answers to *different questions* and pretending they are points on the same curve. They are not. Different question → different response distribution → different denominator → not comparable.

H_raw and H_improved are comparable because they measure responses to the **same** question (see below) about the **same kind of input** (an 80-token summary of a query meant for the agent). Anything in between violates that constraint.

The v0 question is "does pre-processing reduce loops?" — not "where in the inverse chain does the entropy drop?" If v0 results are positive but we want to know *why*, we add intermediate measurements in v1 with a different methodology designed to make them comparable. See [roadmap/v0-v1-plan.md](../roadmap/v0-v1-plan.md).

---

## What "semantic entropy" means here

Semantic entropy is an information-theoretic measure of how *spread out* an LLM's responses to a fixed prompt are, when those responses are grouped by meaning rather than by surface form.

The intuition is "ask 10 people the same question and see how varied the answers are":

- If all 10 give essentially the same answer → entropy is near zero. The situation is clear; there's only one reasonable next step.
- If the 10 answers spread across many different ideas → entropy is high. The situation is ambiguous; many next steps are equally plausible.

In our case the 10 "people" are 10 sampled responses from the same LLM at temperature 0.7. We embed them, cluster them by semantic similarity, count how many fall into each cluster, and compute the Shannon entropy of that cluster distribution:

```
H = −Σ p(c) × log₂(p(c))
```

where `p(c)` is the fraction of samples that fell into cluster `c`. A single dominant cluster gives `H ≈ 0`. Many small clusters of equal size give `H = log₂(n_clusters)`.

This is a re-purposing of the **Semantic Uncertainty** metric from Kuhn et al. (2023, ICLR Spotlight), which originally measured uncertainty in question-answering. We use it as a metric for **the effect of pre-processing** rather than for QA uncertainty per se.

---

## The fixed measurement question

At every measurement point we ask the LLM the same question:

> **"What concrete action will the agent take next?"**

This question is fixed and never changes. It is asked once at the H_raw point (with the raw 80-token summary as the system prompt) and once at the H_improved point (with the refined 80-token summary as the system prompt). The 10 sampled answers are the inputs to clustering.

Why this question, and why fix it: the question determines what dimension we are measuring entropy *along*. "What's the goal?" would measure goal-clarity entropy. "What could go wrong?" would measure risk entropy. We chose "next action" because that is the operational variable we care about — agent loops happen when the agent cannot pick a next action with confidence.

If we let the question vary between A and B, or between H_raw and H_improved, we would be measuring *different things* and calling the difference ΔH. The fixed question is what makes ΔH a single number with a single interpretation.

---

## The minimal instruction (system prompt as control variable)

The two measurement points share an identical system prompt:

> **"You are an AI agent that solves problems using tools."**

That string. Nothing more. No format guidance, no role description, no examples, no chain-of-thought instructions. It is fixed by spec and is **not editable** without a version bump (see [operations/experiment-rules.md](../operations/experiment-rules.md)).

Why so minimal: the system prompt is one of the variables that can move H. A richer system prompt ("You are an expert researcher who carefully decomposes problems...") would lower H by itself, before the query even matters. We want the only thing that differs between H_raw and H_improved to be **the semantic clarity of the query**. So we hold the system prompt constant at the smallest meaningful value.

The minimal instruction is also the system prompt the agent itself runs under during execution. This is not a coincidence — if the measurement input differs from the agent's actual input, the comparison between H_n (entropy during execution) and H_raw/H_improved breaks. They have to be the same text, fed the same way.

> **Important**: format guidance (e.g., "answer as a number with no units") lives in the `final_answer` tool description, not in the minimal instruction. This keeps the entropy-measurement input identical for A and B, while still letting the agent know how to format its final answer. See [implementation/agent-tools.md](../implementation/agent-tools.md).

---

## The 80-token summarization (apples-to-apples)

Both H_raw and H_improved are measured on inputs that have been compressed to **at most 80 tokens** by an LLM-based summarizer. Specifically:

- **H_raw input**: `[minimal instruction] + [original query summarized to ≤80 tokens]`
- **H_improved input**: `[minimal instruction] + [refined query summarized to ≤80 tokens]`

The summarizer is the same LLM used for everything else (single-model policy — see [hypothesis.md](./hypothesis.md#what-this-is-not)), called at `temperature=0` for deterministic compression.

### Why summarize at all

The original query might be 30 tokens. The refined query — the output of Compose — is likely to be much longer, because it carries explicit Target definitions, backward-chained requirements, and preconditions. If we measure H_raw on a 30-token input and H_improved on a 400-token input, we are not measuring "the difference in clarity." We are measuring "the difference between a short input and a long input." Longer inputs reduce response variance for reasons that have nothing to do with semantic clarity (more constraints = fewer valid next moves).

Summarizing both sides to the same 80-token cap removes input length as a variable. Whatever ΔH we observe afterward is then attributable to how clearly the 80-token compression communicates the task, which is exactly the dimension we care about.

### Why 80 tokens specifically

80 is the **Head** budget in the 300-token total context (80 Head + 70 Body + 150 Tail). See [token-budget.md](./token-budget.md) for the full split. The reason measurement uses the same 80-token Head is the same reason the minimal instruction uses the same string the agent uses: **the measurement input must match the agent's actual input**, or H_raw/H_improved become uncomparable to H_n (the entropy during execution).

The 80-token cap is stable for v0 and may be re-tuned based on results.

### Apples-to-apples in one sentence

Both measurements pass through the same fixed system prompt, the same fixed measurement question, the same summarization pipeline at the same token budget — so the only thing that can produce a difference between H_raw and H_improved is **the semantic clarity of the query**. That is the entire experimental design in one sentence.

---

## Handling measurement noise: cancellation in ΔH

### The problem

Measure the same task twice and you'll get slightly different H values. Run it a third time and you'll get a third number close to the first two but not identical.

The reason is the summarization step. The LLM-based summarizer is at temperature 0 but is not perfectly deterministic across runs (model rounding, infrastructure variance), and even the *exact same* text summary can lead to different response distributions when sampled at temperature 0.7 in the entropy measurement step. So a two-source noise — summarization variance + sampling variance — is baked into every H measurement.

Concretely, if the original query is "I want to raise team productivity," two independent summarizations might produce:

- "Looking for ways to improve team productivity"
- "Searching for methods to improve team work efficiency"

To a human these are synonyms. But to the next LLM call, the version with "productivity" might bias responses toward tooling recommendations, while the version with "work efficiency" might bias them toward process analysis. Different bias → different cluster distribution → different H.

### Why we don't try to remove the noise

The naive fix would be: cache the summary, reuse it, eliminate summarization variance. We deliberately don't, for two reasons:

1. **The agent itself runs against a freshly-summarized 80-token Head.** If we remove summarization variance from the measurement but not from execution, the measured H no longer corresponds to the H the agent actually starts at. The control variable breaks.
2. **More importantly: the noise cancels in ΔH.** This is the key argument.

### The cancellation argument

We treat "summarize → measure" as a single block. The summarization variance is *part of* what H is measuring — not noise to be filtered, but a property of the measurement pipeline.

Now consider that the same pipeline measures both H_raw and H_improved:

- H_raw goes through `summarize_to_head() → measure_semantic_entropy()` once.
- H_improved goes through `summarize_to_head() → measure_semantic_entropy()` once.
- Both calls hit the same summarizer, the same temperature, the same embedding model, the same clustering algorithm.

The summarization variance is baked into both numbers in the same way. When we compute `ΔH = H_raw − H_improved`, the variance contribution to H_raw and the variance contribution to H_improved largely cancel — we're subtracting two noisy numbers that share their noise source.

> **Tape measure analogy**: imagine measuring two people's heights with the same tape measure. Even if the tape is off by 1 cm, the error is in *both* measurements equally, so it disappears in the difference. A − B still gives the correct height *difference* even though A and B individually have a 1 cm bias. Our summarization noise is the 1 cm bias, and ΔH is A − B.

This is why apples-to-apples (the previous section) is not just an aesthetic preference — it is what makes the noise cancellation valid. If A and B used different summarizers, or different system prompts, or different measurement questions, the noise sources would be different and would not cancel. The whole methodology rests on identity of pipeline.

### What this does and doesn't claim

What this **does** claim: the *systematic* noise from the summarization pipeline does not bias ΔH, because it appears identically on both sides of the subtraction.

What this **does not** claim: individual H_raw or H_improved values are precise. They are not — each one carries the full noise. Only the difference is reliable.

The practical consequence: do not interpret H_raw or H_improved in isolation. Always look at ΔH and the per-task pairing. A single H_raw of 2.3 means very little; a paired (H_raw=2.3, H_improved=0.4) means a lot.

---

## Clustering: what we ask of it

The clustering step groups the 10 sampled responses by meaning. Several design choices matter for the entropy result:

- **Embeddings come from a model that is *separate* from the generation model.** We use a neutral embedding model via Together AI — currently `intfloat/multilingual-e5-large-instruct`. The "neutral" constraint is what matters: the embedder must be separate from the generation model so that embeddings don't overfit to the generator's idiosyncrasies and underestimate semantic spread. The specific model identity is locked per spec version (changing it requires a version bump because cluster geometry depends on it), but the load-bearing constraint is "neutral and external," not "must be Llama-3." The original v2.7.9 named Llama-3 because it was the available choice at the time; the current Together AI serverless catalog has consolidated around E5.

  > **Implementation note:** the Together AI embeddings endpoint is OpenAI-compatible, so the client library used is `openai` (the Python package), pointed at `https://api.together.xyz/v1`. This is Together AI's standard usage pattern — there is no separate Together SDK. The presence of `openai` in `pyproject.toml` dependencies is for this purpose, not for calling OpenAI's own generation models (which v0 does not do).

- **Hierarchical clustering with a fixed cosine-distance threshold (0.15), not k-means.** k-means requires specifying the number of clusters in advance, but the whole point of measuring entropy is that we don't know how many distinct meanings there are. Threshold-based agglomerative clustering lets the number of clusters emerge from the data: similar responses merge until no two clusters are within 0.15 cosine distance.

- **Threshold = 0.15** is chosen to be tight enough that paraphrases of the same idea collapse to one cluster, but loose enough that genuinely different proposed actions stay in separate clusters. This threshold is **not editable without a version bump** — see [operations/experiment-rules.md](../operations/experiment-rules.md) — because changing it changes the meaning of every H value in the result table.

- **The clustering is deterministic given fixed embeddings.** scikit-learn's `AgglomerativeClustering` does not use any random state. Combined with deterministic embeddings, this means the only stochasticity in measurement comes from the temperature-0.7 sampling step, which is what we want.

Implementation details (library versions, exact API calls, base URLs) live in [implementation/inverse.md](../implementation/inverse.md). This file is about what we ask the clustering to *accomplish* and why, not how to call the API.

---

## Sample size: N = 10

Each H measurement samples the LLM **N = 10** times at temperature 0.7.

This is the smallest value where the cluster distribution is a meaningful estimate of the true response distribution. Smaller N makes the noise-cancellation argument above (which depends on noise being well-averaged across samples) start to break down. Larger N gives smoother H values but multiplies cost: each task in v0 has 2 measurement points × 2 conditions, so each task costs roughly 4N entropy-measurement calls before the agent even starts running. N=10 is the floor.

Operational rules for when N may differ from 10 (smoke tests, quick reruns) live in [operations/reproducibility.md](../operations/reproducibility.md).

---

## What the measurement does not see

Things that are *not* part of the entropy measurement, even though they happen in the same pipeline:

- **The agent's tool descriptions.** The agent has access to `tavily_search`, `tavily_extract`, and `final_answer` (see [implementation/agent-tools.md](../implementation/agent-tools.md)). These descriptions are passed to the agent during execution but **not** to the entropy measurement. The measurement input is strictly `[minimal instruction] + [80-token summary]` and nothing else. If we included tool descriptions in the measurement input, we would be measuring "uncertainty about which tool to call" rather than "uncertainty about what the task means."

- **The ground-truth answer.** Obviously. Never seen by the measurement, never seen by the agent.

- **GAIA's annotator metadata.** Each GAIA task comes with a step-by-step solution from the annotator. This is not used anywhere — not in measurement, not in execution. Including it would leak ground truth into the agent. See [implementation/gaia-integration.md](../implementation/gaia-integration.md).

- **Per-step state during execution.** H_raw and H_improved are the *entrance* measurements, taken before the agent runs. The entropy curve during execution (H_n at each step) is a separate measurement, governed by the same `measure_semantic_entropy()` function but with the 300-token Head+Body+Tail context as input instead of the 80-token Head alone. See [token-budget.md](./token-budget.md) and [loop-detection.md](./loop-detection.md).

---

## The complete measurement pipeline, in order

For a single H measurement (either H_raw or H_improved):

1. Take the query (raw or refined).
2. `summarize_to_head(query, max_tokens=80, temperature=0)` → an 80-token summary.
3. Construct the input: `[minimal instruction] + [summary]`. This is the system prompt.
4. With that system prompt fixed, ask the measurement question — "What concrete action will the agent take next?" — N=10 times at temperature 0.7. Collect 10 responses.
5. Embed the 10 responses with the Together AI Llama-3 embedder.
6. Cluster the embeddings with `AgglomerativeClustering(metric="cosine", linkage="average", distance_threshold=0.15)`.
7. Count the size of each cluster, normalize to a probability distribution, compute Shannon entropy.
8. Return that entropy value.

The pipeline runs twice per task in condition B (once for raw, once for improved), and once per task in condition A (raw only — H_improved is recorded as equal to H_raw and ΔH as 0).

H_raw is cached across conditions A and B (it's the same number for both). H_improved is **deliberately not cached**, as a sanity check on the inverse cache — see [implementation/caching.md](../implementation/caching.md) for the reasoning.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The minimal instruction string (`"You are an AI agent that solves problems using tools."`) | **No, version bump required** | It is the system prompt for every measurement and for the agent itself. Changing it changes what every H value means. |
| The measurement question (`"What concrete action will the agent take next?"`) | **No, version bump required** | The question defines what dimension entropy is measured along. Different question = different metric. |
| The 80-token Head budget | **No, version bump required** | Both H_raw and H_improved are measured on 80-token inputs. Changing the cap breaks comparability with all prior runs. |
| The clustering distance threshold (0.15) | **No, version bump required** | Determines what counts as "the same meaning." Changing it changes every H value and every ΔH. |
| `N_SAMPLES = 10` for result-producing runs | **No, version bump required** | Smaller N breaks the noise-cancellation argument. Smoke-test overrides via `--n-samples` are allowed but their output is not part of the result table — see [operations/reproducibility.md](../operations/reproducibility.md). |
| Sampling temperature (0.7) | **No, version bump required** | Determines the response distribution being clustered. Changing it changes the meaning of cluster spread. |
| Embedding model identity (currently `intfloat/multilingual-e5-large-instruct` via Together AI) | **No, version bump required** | A different embedder produces different cluster geometry, which changes every H value. The "neutral and external" constraint is the load-bearing part; the specific model id is the current implementation of that constraint and is still version-locked. |
| The Shannon entropy formula | **No, version bump required** | It is the metric. |
| The fact that H_raw and H_improved use the *same* pipeline | **No, version bump required** | The whole noise-cancellation argument depends on this identity. |
| The `summarize_to_head` prompt template wording | Editable | The summarizer is allowed to be improved over time, as long as it stays at temperature 0 and respects the 80-token cap. Improvements should be validated by checking that ΔH on a held-out task set does not change distribution. |
| Per-paragraph wording, the 10-people analogy, the tape-measure analogy, examples | Editable | These are explanations of the methodology, not the methodology itself. |

The first nine rows are load-bearing — they are the methodology. The last two are explanatory and improvable.
