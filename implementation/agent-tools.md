# Agent and tool set

> Sourced from: v2.7.9 §Agent (Tool set, Final answer format, LLM model policy)
> Related: [react-loop.md](./react-loop.md), [../spec/measurement.md](../spec/measurement.md), [../spec/hypothesis.md](../spec/hypothesis.md)

---

## The three tools

The ReAct agent has exactly **three tools**. Not two, not four. The number is fixed for v0.

| Tool | Purpose | Backend | Tavily credit |
|---|---|---|---|
| `tavily_search(query: str)` | Web search | Tavily basic mode (`max_results=5`) | 1 |
| `tavily_extract(url: str)` | Fetch and extract page text | Tavily | 1 |
| `final_answer(answer: str)` | Terminate the ReAct loop | Internal | 0 |

### Why these three and only these three

Adding more tools introduces "which tool to use" as a new variable. The hypothesis under test is that pre-processing with the inverse model lowers semantic entropy and thereby reduces loops; if we also vary the tool set, we cannot tell whether a difference in loop rate came from the inverse model or from the agent having more or fewer options to choose between. Tool set is held fixed in v0 and any expansion is a v1 concern.

### Why basic mode and `max_results=5` are fixed

Tavily has a basic mode (1 credit per call) and an advanced mode (2 credits per call). v0 uses basic only, for two reasons: cost predictability, and uniform search quality across conditions A and B. If basic and advanced were mixed, the search-quality variance would add noise to the loop rate.

`max_results=5` is the Tavily default. Raising it would make each search return more content, which increases the burden on the Tail-trimming pipeline (see [../spec/token-budget.md](../spec/token-budget.md)) and might push truly relevant content past the 150-token Tail boundary. Lowering it would degrade search quality. Five is fixed to remove it as an experimental variable.

### Why `final_answer` is a tool, not a special string

Terminating the loop by tool call (rather than by parsing the agent's text for a magic phrase) makes the exit condition unambiguous. `run_react_loop` watches for a tool_use block whose name is `final_answer`; when one appears, the loop exits with `terminated_by = "completed"` and the answer string is captured for the verifier. There is no parsing ambiguity.

If the agent produces text without any tool call, the step is retried once. On second failure, the loop forces a `final_answer` call with the agent's best-effort answer. See [../operations/failure-modes.md](../operations/failure-modes.md).

---

## Final answer format

GAIA's scorer expects answers in a specific normalized form. Where the format instruction lives is **load-bearing**: it goes in the `final_answer` **tool description**, *not* in the minimal instruction. This preserves the apples-to-apples control variable from [../spec/measurement.md](../spec/measurement.md): the entropy measurement input is `[minimal instruction] + [80-token summary]`, identical for A and B, and the format rules never enter the measurement pipeline.

```
Tool: final_answer
Description: Call this tool when you are ready to give the final answer to the user's question.

Your answer should be:
- A number, OR
- As few words as possible, OR
- A comma-separated list of numbers and/or strings.

Formatting rules:
- If you are asked for a number, do not use commas or units (such as $ or %) unless explicitly requested.
- If you are asked for a string, do not use articles or abbreviations, and write digits in plain text unless explicitly requested.
- If you are asked for a comma-separated list, apply the above rules to each element in the list.

Parameter:
    answer (str): the final answer, formatted according to the rules above.
```

The format instruction exists only in the agent's tool schema. It is not passed to the entropy measurement pipeline. If a future change moved this string into the system prompt, it would silently lower H by adding constraints that the measurement is supposed to be measuring around — which would invalidate every prior `H_raw` and `H_improved`.

---

## LLM model (single-model policy)

**All LLM calls in v0 use the same model**, defined as `MODEL` at the top of `benchmark.py` and overridable via CLI `--model`.

This applies to:

- `inverse()` internal calls (Target / Invert / Compose)
- `summarize_to_head()`
- ReAct agent (Thought + Action generation)
- `measure_semantic_entropy()` sampling calls

**Exception**: the embedding model used for semantic clustering is Together AI's Llama-3, which is a separate component from the generation model. The embedder is intentionally a different model — see [../spec/measurement.md §Clustering: what we ask of it](../spec/measurement.md#clustering-what-we-ask-of-it) for the reason (a separate, neutral embedder gives a more honest measure of semantic spread).

### Why a single model for all generation roles

v0 minimizes experimental variables. The hypothesis under test is "does inverse pre-processing reduce loops?" Introducing model asymmetry — for example, agent on Sonnet, inverse on Opus, summarizer on Haiku — would require an exponential ablation to interpret the results, because any improvement in B could then be attributed to "the inverse model used a stronger LLM" rather than to "the inverse model removed entropy from the prompt." Asymmetric configurations are deferred to v1. See [../roadmap/deferred.md](../roadmap/deferred.md).

---

## Cross-references

- [react-loop.md](./react-loop.md) — where the agent's tool calls are dispatched
- [../spec/measurement.md](../spec/measurement.md) — why the format string lives in the tool description, not the minimal instruction
- [../operations/failure-modes.md](../operations/failure-modes.md) — what happens when the agent emits no tool call
- [caching.md](./caching.md) — Tavily responses are cached at the tool level
