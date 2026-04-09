# `inverse.py`

> Sourced from: v2.7.9 §inverse.py — Inverse Model engine + entropy measurement
> Related: [../spec/measurement.md](../spec/measurement.md), [../spec/loop-detection.md](../spec/loop-detection.md), [../spec/token-budget.md](../spec/token-budget.md), [../spec/hypothesis.md](../spec/hypothesis.md)

---

## Role

`inverse.py` is the entropy-and-refinement engine. It takes a vague prompt and returns an improved prompt, and along the way it produces the two entropy measurements (`H_raw` and `H_improved`) that are the experimental signal. Everything else in the codebase reads its outputs.

There are six exported functions. They live in one file because they share the same dependencies (the LLM client, the embedding client, the clustering library) and because keeping them together makes the inverse model's pipeline auditable in a single place.

---

## File header

```python
"""
prompt-training/inverse.py

Vague prompt → improved prompt converter (inverse model).
Entropy is measured only at the raw prompt and the improved prompt.

Usage:
  from inverse import inverse, measure_semantic_entropy

  result = inverse("I want to cut waste. I have 3 cards.", model=MODEL)
  print(result["improved_prompt"])
  print(result["H_raw"])          # e.g. 2.32
  print(result["H_improved"])     # e.g. 0.15
  print(result["delta_H"])        # e.g. 2.17
"""

MINIMAL_INSTRUCTION = "You are an AI agent that solves problems using tools."
```

The `MINIMAL_INSTRUCTION` constant is the system prompt for every entropy measurement and for the agent itself. It is a control variable — see [../spec/measurement.md §The minimal instruction](../spec/measurement.md#the-minimal-instruction-system-prompt-as-control-variable). Do not modify it. Do not append to it. Format guidance for the agent's final answer lives in the `final_answer` tool description, not here. See [agent-tools.md](./agent-tools.md).

---

## The six functions

### `summarize_to_head(text, max_tokens=80, model)`

Summarize an arbitrary-length text into at most `max_tokens` tokens. Used to produce the 80-token Head for both `H_raw` and `H_improved` inputs, and for every step of the agent's execution context (where the same Head is locked in once and reused).

- `temperature = 0` (deterministic compression).
- The 80-token cap is the same 80 used by the Head budget in [../spec/token-budget.md](../spec/token-budget.md). Equality is load-bearing.
- Returns: the summarized text as a string.

### `trim_to_tail(text, max_tokens=150)`

Meaning-preserving trim. Removes whitespace and filler only. Does **not** summarize or rewrite. Key error logs and technical keywords are preserved verbatim. Short inputs pass through unchanged.

The reason for the asymmetry between summarize-Head and trim-Tail is in [../spec/token-budget.md §Head, Body, Tail — three jobs, three compressions](../spec/token-budget.md#head-body-tail--three-jobs-three-compressions). It is load-bearing: summarizing the Tail would systematically lower measured entropy without lowering actual ambiguity.

### `measure_semantic_entropy(input_context, model, n_samples=10)`

The entropy measurement primitive. Used at three places:

1. On the 80-token raw summary, to produce `H_raw`.
2. On the 80-token improved summary, to produce `H_improved`.
3. On the 300-token Head+Body+Tail context, at every step of the agent's execution, to produce `H_n`.

Procedure:

- `input_context = [minimal instruction] + [query or 300-token state]`
- Fix `input_context` as the system prompt.
- Sample the user question — `"What concrete action will the agent take next?"` — `n_samples` times at temperature 0.7.
- Embed the responses with Together AI's Llama-3 embedding model.
- Cluster on cosine similarity (`AgglomerativeClustering`, average linkage, `distance_threshold=0.15`).
- Return the Shannon entropy of the resulting cluster distribution.

The fixed measurement question, the temperature, the sample size, the clustering threshold, and the embedding model identity are all load-bearing — see [../spec/measurement.md §What is and is not editable](../spec/measurement.md#what-is-and-is-not-editable).

### `semantic_cluster(responses)`

The clustering primitive. Embed `N` responses via Together AI (`base_url="https://api.together.xyz/v1"`, OpenAI-compatible interface) using the Llama-3 embedding model, then cluster:

```python
AgglomerativeClustering(
    metric="cosine",
    linkage="average",
    distance_threshold=0.15,
)
```

Returns the list of cluster labels. Deterministic given fixed embeddings.

### `inverse(raw_prompt, model, n_samples=10)`

The 3-step independent prompt chain. Each step runs as its own LLM call with no shared conversation history; the previous step's output is explicitly injected into the next step's prompt template. This is **Prompt Chaining via Explicit Injection** — see [../spec/hypothesis.md §Implementing the inverse model as an LLM prompt chain](../spec/hypothesis.md#implementing-the-inverse-model-as-an-llm-prompt-chain) for the rationale.

The three steps are **Target / Invert / Compose**. (The original v2.7.9 spec called the third step "Output" — we use "Compose" because "Output" collided with the function's return value, and the paper itself never names the step. See `CHANGELOG.md` v2.8.0.)

- **Target**: "When this task is finished, what exists?" → a definition of the done state.
- **Invert**: "To reach that, what must be done and what must be known?" → a backward chain. Performs **Macro-level Backward Chaining**: micro-steps are ignored; only decisive logical jumps are derived. Stopping conditions:
  - **Logical threshold**: the derived condition can start with information already in the initial request.
  - **Structural threshold**: the full backward chain is at most 5 steps (`k=4`).
- **Compose**: combine Target and Invert into a single, clear instruction → the refined prompt.

Entropy is measured only at the entrance (`raw_prompt`) and the exit (`improved_prompt`). Intermediate steps are not measured: each step asks a different question, the response distributions are on different curves, and they are not comparable. See [../spec/measurement.md §Why only two points](../spec/measurement.md#why-only-two-points).

`temperature = 0` for all LLM calls inside `inverse()` (deterministic refinement).

Pseudo-code:

```python
def inverse(raw_prompt, model, n_samples=10):
    # 1. Original query → 80-token summary → measure H_raw
    raw_summary = summarize_to_head(raw_prompt, max_tokens=80, model=model)
    H_raw = measure_semantic_entropy(
        f"{MINIMAL_INSTRUCTION}\n\n{raw_summary}", model, n_samples
    )

    # 2. Run the 3 inverse-model steps (independent prompt chaining)
    target = llm_call(prompt_target(raw_prompt), model, temperature=0)
    inversion = llm_call(prompt_invert(target, raw_prompt), model, temperature=0)
    improved_prompt = llm_call(
        prompt_compose(raw_prompt, target, inversion), model, temperature=0
    )

    # 3. Refined query → 80-token summary → measure H_improved
    improved_summary = summarize_to_head(improved_prompt, max_tokens=80, model=model)
    H_improved = measure_semantic_entropy(
        f"{MINIMAL_INSTRUCTION}\n\n{improved_summary}", model, n_samples
    )

    return {
        "raw_prompt": raw_prompt,
        "improved_prompt": improved_prompt,
        "raw_summary": raw_summary,
        "improved_summary": improved_summary,
        "target": target,
        "inversion": inversion,
        "H_raw": H_raw,
        "H_improved": H_improved,
        "delta_H": H_raw - H_improved,
        "total_tokens_used": total_tokens,
        "pre_processing_time": time_taken,
    }
```

The three prompt templates are named `prompt_target`, `prompt_invert`, `prompt_compose`. The original draft used `prompt_1` / `prompt_2` / `prompt_3` aliased to "Output"; the rename to `prompt_compose` makes the function name match the step name. The template *wording* is editable — it is the experimental subject — but the three-step structure and the names are not. See [../spec/hypothesis.md §What is and is not editable](../spec/hypothesis.md#what-is-and-is-not-editable).

### `detect_loop(entropy_history, H_raw, alpha=0.3, window=3)`

Detect loop regions in the entropy curve during agent execution.

- `threshold = alpha × H_raw` (based on the raw prompt's semantic entropy).
- **Both A and B use `H_raw` as the reference.** B does *not* use `H_improved`. The justification is in [../spec/loop-detection.md §(c)](../spec/loop-detection.md#c-why-h_raw-is-the-reference-in-both-a-and-b-not-h_improved-in-b).
- Condition: `d²H/dt² ≈ 0` (within `window`) AND `H > alpha × H_raw`. Both halves of the AND are required — see [../spec/loop-detection.md §(b)](../spec/loop-detection.md#b-why-both-conditions-are-needed-the-and-not-just-dhdt--0).
- The second derivative (rather than the first) is what distinguishes plateau from convergence — see [../spec/loop-detection.md §(a)](../spec/loop-detection.md#a-why-the-second-derivative-and-not-the-first).

Returns: `{"is_loop": bool, "loop_start_step": int or None}`.

Called by `run_react_loop` after each step's `H_n` is recorded. If `is_loop` is true, the loop terminates with `terminated_by = "loop_detected"`.

---

## Cross-references

- [../spec/measurement.md](../spec/measurement.md) — what every entropy value means
- [../spec/loop-detection.md](../spec/loop-detection.md) — what `detect_loop` is testing for
- [../spec/token-budget.md](../spec/token-budget.md) — why 80 / 70 / 150
- [react-loop.md](./react-loop.md) — where these functions are called from during execution
- [benchmark.md](./benchmark.md) — where `inverse()` is called from at the top level
- [caching.md](./caching.md) — what is cached and what deliberately is not
