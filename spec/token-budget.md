# Token budget

> Sourced from: v2.7.9 §Token management strategy (Lean & Forward Strategy), §Tavily responses and Tail trimming
> Related: [measurement.md](./measurement.md), [loop-detection.md](./loop-detection.md), [implementation/inverse.md](../implementation/inverse.md), [implementation/agent-tools.md](../implementation/agent-tools.md)

---

## The split

The context the agent runs against, and the context the entropy measurement is taken on, is capped at **300 tokens** total, partitioned as:

| Slot | Tokens | Content | Compression method |
|---|---|---|---|
| **Head** | 80 | `[minimal instruction] + [query summarized to ≤80 tokens]` | Summarized once, before execution. **Locked** for the rest of the run. |
| **Body** | 70 | Compressed summary of execution history before step n−2 | Re-summarized recursively at each step. |
| **Tail** | 150 | Thought + Observation from step n−1 | **Trimmed** (whitespace and filler removal only — no rewriting). |

Three slots, three different compression policies. The asymmetry is the whole point — every slot is doing a different job, and using the wrong compression for any of them would silently break the measurement. The bulk of this file is the *why* behind that asymmetry.

> **Forward Model note**: the Body slot exists to support a future "Predict-Compare" cycle from the full Wolpert-Kawato architecture (see [hypothesis.md](./hypothesis.md#how-the-full-wolpert-kawato-architecture-extends-this)). v0 carries the Body in the budget but does not exercise the Predict-Compare loop. The slot is reserved structurally so that v1 can activate the forward model without changing the token budget — which would invalidate every prior H value.

---

## The Head's 80 tokens is the same 80 as in measurement

The Head budget of 80 tokens is **the same 80** that the measurement pipeline in [measurement.md](./measurement.md#the-80-token-summarization-apples-to-apples) uses for `H_raw` and `H_improved`. They must be equal, and the equality is a design constraint, not a coincidence.

The reason: the entropy measured during execution (`H_n` at each ReAct step) needs to be comparable to `H_raw` and `H_improved`, and that comparability requires that all three measurements be taken on inputs of the same kind. The system prompt under which `H_raw` is sampled is `[minimal instruction] + [80-token summary of the raw query]`. The system prompt under which `H_improved` is sampled is `[minimal instruction] + [80-token summary of the refined query]`. The system prompt under which `H_n` is sampled at execution step n is `[minimal instruction] + [Head + Body + Tail]`, where the Head is *that same 80-token summary*, locked at the start of execution and never modified.

If the measurement pipeline summarized to 80 tokens but the agent executed against a different Head size — say, the agent ran against a 200-token Head because someone decided "more context is better" — then the entropy curve `H_n` would no longer share a y-axis with `H_raw` and `H_improved`. The y-axis would be a different thing on each side: H values measured on 80-token inputs versus H values measured on 200-token inputs are not on the same scale, because the response distribution at each is constrained by a different amount of input information. The loop detection condition `H > 0.3 × H_raw` (see [loop-detection.md](./loop-detection.md#c-why-h_raw-is-the-reference-in-both-a-and-b-not-h_improved-in-b)) would be comparing numbers from two different scales.

The threshold is the bridge: it uses `H_raw` as a per-task reference, and that reference can only mean what it claims to mean if the H values being compared against it were measured the same way. Equality of Head size is the load-bearing precondition. Cross-link: [measurement.md §Why 80 tokens specifically](./measurement.md#why-80-tokens-specifically).

The practical consequence: if you ever change 80 to some other number, you have to change it in *both* the measurement pipeline and the agent's Head construction at the same time, in a single coordinated edit, with a version bump. Half-changing it is the kind of bug that would silently invalidate every loop count in the result table without producing any error message.

---

## Head, Body, Tail — three jobs, three compressions

Each slot exists to preserve a different kind of information about the task, and each requires a different compression method to do its job without distorting the entropy measurement.

### Head (80 tokens, summarized) — the goal

The Head holds the goal — the Definition of Done that the agent must not lose track of. In the language of the Wolpert-Kawato model ([hypothesis.md](./hypothesis.md#where-the-inverse-model-comes-from)), the Head is the **Compare anchor**: when the forward model is eventually wired up in v1, the Head is what each predicted-vs-observed comparison happens against.

For this slot, **summarization** (meaning-level rewriting) is the right compression. We want the *essence* of the task — the final state the agent is trying to produce — not its literal wording. A long, wordy user query like *"Hi, I was wondering if you could help me figure out, you know, who currently holds the record for..."* contains exactly the same task as *"Find the current record holder for..."*, and the second version preserves everything that matters. Summarization throws away wording while preserving meaning, which is exactly the trade we want for the goal slot.

The Head is also the only slot that is **locked**: it is summarized once, at the start of execution, and never recomputed. The other slots change as execution proceeds; the goal does not. Locking the Head is what makes it a stable reference for the eventual Predict-Compare cycle and, more immediately, what makes the y-axis of the entropy curve constant across steps. If the Head were re-summarized at each step, two slightly different summaries of the same query would produce slightly different `H_n` values for reasons unrelated to the agent's progress, and the curve would be unreadable.

### Body (70 tokens, summarized) — the state

The Body holds a heavily compressed summary of execution history *before* the most recent step. Its job is to carry forward "facts confirmed so far" — what the agent has already established. In the eventual forward-model architecture, the Body is the **state value** that gets fed into Predict.

The Body is summarized for the same reason the Head is summarized: we care about meaning (which facts are now known) rather than exact wording. We do not need to preserve the literal text of every search result the agent has seen so far; we need to preserve "the agent has confirmed X, has ruled out Y, and has not yet checked Z." Summarization is appropriate here.

The Body is summarized **recursively**: at each step n, the Body slot becomes a summary of (the previous Body) + (whatever fell out of the Tail when the new step's data moved in). This is a sliding-window summarization, not an accumulating one — older information gets compressed more aggressively as it ages, which is the right shape for a fixed token budget.

### Tail (150 tokens, trimmed) — the most recent state

The Tail holds the Thought and Observation from the immediately preceding step. Its job is to carry forward the agent's most recent state with **full resolution** — including error logs, technical keywords, exact field names returned by tools, and any other content whose specific wording matters for the next step's decision.

This is the slot where the Head/Body compression strategy would actively *break* the experiment. If we summarized the Tail, we would be feeding the next step a smoothed version of the previous step's state. The next step's response distribution — and therefore its measured entropy — would be tighter than it should be, because some of the ambiguity of the agent's actual situation would have been quietly removed by the summarizer before the agent ever saw it.

Concretely: imagine the previous step's Observation was a Tavily error response containing the exact string `"timeout after 10s on host api.example.com"`. The agent's correct next action depends on whether the next step recognizes that as a transient infrastructure issue (retry), a permanent failure (fall back to a different search), or a sign that the URL is wrong (re-extract with a different query). A summarizer would compress that into something like *"the previous tool call failed with a timeout"* — a paraphrase that loses the exact host, the exact duration, and the exact error class, all of which the agent might have used. The agent's response distribution to the summarized Tail will be tighter (fewer plausible next moves to consider, because there is less to react to) than its distribution to the raw Tail. The measured `H_n` will be artificially low, and that low number will not reflect the agent's actual situation.

This is the same kind of failure mode as the H_raw-as-reference issue in [loop-detection.md §(c)](./loop-detection.md#c-why-h_raw-is-the-reference-in-both-a-and-b-not-h_improved-in-b): a measurement apparatus that quietly smooths its inputs reports a value that doesn't mean what it claims to mean. There the apparatus was the loop threshold; here the apparatus is the input to `measure_semantic_entropy` itself. The fix in both places is the same: hold the apparatus rigid even when an "improvement" looks tempting.

So the Tail uses **trimming**, not summarization. Trimming removes whitespace and filler — repeated newlines, boilerplate prefixes, the markup wrappers that some tool responses come with, the long disclaimers Tavily sometimes prepends. Trimming **never rewrites meaning**. Key error logs and technical keywords stay verbatim. If the trimmed text would still exceed 150 tokens after whitespace removal, the trim function truncates from the end, not from the middle, and the truncation point is recorded — but it does not paraphrase. Short inputs pass through unchanged.

The trim rule is applied **uniformly** across both conditions A and B and across every step. Uniformity is again about apparatus identity: if A's Tail were trimmed differently from B's, or if longer Observations were summarized while shorter ones were trimmed, the entropy values would no longer be comparable across runs.

### The asymmetry, summarized

| Slot | Compression | Why this compression |
|---|---|---|
| Head | Summarization | The goal is about meaning, not wording. Summarization throws away wording, preserves meaning. |
| Body | Summarization (recursive) | "Facts confirmed so far" is also a meaning-level abstraction; older facts compress more as they age. |
| Tail | Trimming only | The most recent state must keep its resolution. Summarizing it would systematically lower measured H without lowering actual ambiguity. |

Two slots get summarized, one slot gets trimmed. The asymmetry is not aesthetic — it is what keeps the entropy measurement honest.

---

## Why the Tail can see Tavily responses much larger than 150 tokens

Tavily's `tavily_search` returns approximately 5 results × ~200 characters per snippet, totalling roughly 1000 characters. `tavily_extract` can return much longer page bodies. Both routinely exceed the 150-token Tail budget. The handling is two-path, and both paths have to be implemented:

1. **In the current step's Thought phase**, the agent sees the **full, untruncated** Tavily response. No trimming yet. The agent's reasoning quality at this step must not be degraded by missing content; if a critical fact is in result #4, the agent has to be able to read it.

2. **In the next step's context construction only**, the raw Observation is passed through `trim_to_tail(obs, max_tokens=150)` *before* it becomes the Tail. This is where the 150-token cap actually applies.

`tavily_extract` is handled the same way: the raw page body is shown to the Thought once, then trimmed for subsequent steps.

The implementation must keep these two paths separate. The same Observation object exists in two states — full while the current step is reasoning over it, trimmed once it has slid into the Tail of the next step's context. Conflating them breaks either the agent's reasoning (if the trim happens too early) or the entropy measurement (if the trim never happens). See [implementation/react-loop.md](../implementation/react-loop.md) for where in the per-step flow this split happens.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The 80-token Head budget | **No, version bump required** | Equal to the measurement pipeline's 80. Half-changing it would invalidate every H value. |
| The 70-token Body budget | **No, version bump required** | Part of the 300-token total. Changing it changes the Body summarizer's compression ratio, which changes what H_n means. |
| The 150-token Tail budget | **No, version bump required** | Same reason as Head and Body — part of the H_n input. |
| The 300-token total | **No, version bump required** | The sum is the load-bearing constraint; the split into 80/70/150 is its decomposition. |
| Head is summarized (meaning-level) | **No, version bump required** | The locked goal anchor. Trimming would lose the abstraction that makes the goal stable. |
| Tail is trimmed (no meaning rewriting) | **No, version bump required** | Summarizing the Tail systematically lowers measured H without lowering actual ambiguity. This is the load-bearing asymmetry. |
| Body is recursively summarized | **No, version bump required** | The recursion shape is what gives the 70-token slot its compression-with-age behavior. |
| The two-path handling of large Tavily responses (full to Thought, trimmed to next Tail) | **No, version bump required** | Either path alone breaks something — agent reasoning or entropy measurement. |
| The exact `summarize_to_head` prompt template wording | Editable | Improvements expected; must respect 80-token cap and temperature-0. See [operations/experiment-rules.md](../operations/experiment-rules.md). |
| The exact `trim_to_tail` whitespace/filler rules | Editable | Implementation detail of "trim, don't rewrite." Must remain meaning-preserving. |
| Per-paragraph wording, the timeout-error example, the asymmetry table | Editable | Explanations of the design, not the design itself. |

The first eight rows are load-bearing — they are the design. The rest is implementation tuning and exposition.
