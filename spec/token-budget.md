# Token budget

> Sourced from: Phase 8.0 pipeline restructure (commit b8daf4d, 2026-04-10). Replaces the v2.7.9 §Token management strategy as the load-bearing description of how the agent's context is built.
> Related: [measurement.md](./measurement.md), [loop-detection.md](./loop-detection.md), [implementation/inverse.md](../implementation/inverse.md), [implementation/agent-tools.md](../implementation/agent-tools.md)
> Checkpoint: [CHECKPOINT_04](../docs/checkpoints/CHECKPOINT_04_phase_8_0_pipeline_restructure.md) §5 records the obligation that produced this rewrite.

> **Heads-up — cross-link inconsistency**: this file has been rewritten for Phase 8.0. Sister specs `measurement.md`, `loop-detection.md`, and `hypothesis.md` still describe the pre-Phase-8.0 80/70/150/300 structure as load-bearing in places, and they cross-link to this file as if it still endorsed that. Until those files are themselves rewritten, treat their references to "the 80-token Head" or "the 300-token total" as historical. The current source of truth for context structure is **this file** and the implementation in `benchmark.py run_react_loop` at HEAD ac9260d or later. CHECKPOINT_04 §5 records the wider rewrite obligation.

---

## Why this file was rewritten

The previous version of this file argued that the agent's context must be capped at exactly 300 tokens, partitioned into an 80-token Head, a 70-token Body, and a 150-token Tail, each with its own compression policy. The entire argument was load-bearing on a single root claim: that the entropy values measured during execution (`H_n` at each ReAct step) had to share a y-axis with `H_raw` and `H_improved`, because the loop-detection threshold `H > 0.3 × H_raw` compared them numerically.

CHECKPOINT_03 (commit 8745575) found that this 80-token Head was destroying the inverse model's output: `improved_prompt` was rich and structured, but `summarize_to_head` re-compressed it to a one-sentence abstraction before the agent ever saw it. CHECKPOINT_03 also reframed entropy from an absolute-value comparison metric to a trend-reading observation tool — within a single task, the trajectory of `H_n` is read for direction (sign of `delta_H`, shape of the curve, firing of `detect_loop`) rather than as numeric comparison across runs.

The trend-reading frame does not require cross-task y-axis consistency. The y-axis requirement was the only load-bearing reason for the 3-slot compression structure. Therefore the 3-slot structure has no remaining justification, and Phase 8.0 (commit b8daf4d) removed it entirely. This file documents the new structure.

---

## The structure

The context the agent runs against, and the context the entropy measurement is taken on, is built from **two parts**:

| Part | Content | Compression |
|---|---|---|
| **Head** | `[minimal instruction] + [full task prompt]` | None. Locked once at the start of execution. The full prompt is the raw question in Condition A and the full `improved_prompt` from `inverse()` in Condition B. |
| **step_history** | The ordered list of formatted records of every completed step (Thought + Action + Observation), as built by `_format_step_raw`. | None. Records are appended verbatim. |

There is no fixed total token budget. The context grows step by step as `step_history` accumulates. The agent's input at step n is `head + "\n\n" + "\n\n".join(step_history)` where `step_history` has length n−1 at the moment the agent is called and length n at the moment entropy is measured.

This is two parts, two jobs, no compression. The asymmetry the previous version of this file defended at length is gone — and the loss of asymmetry is the *point* of Phase 8.0, not an oversight.

---

## Head: the full task prompt, locked

The Head holds the goal in its **complete original form**, not as an abstraction of the goal. In Condition A, that means the full GAIA question text — every constraint, every named entity, every numeric value the user wrote. In Condition B, that means the full `improved_prompt` produced by `inverse()` — every rebuilt precondition, every concrete commitment that the inverse model surfaced through backward chaining.

The Head is **locked**: it is constructed once at the start of `run_react_loop` (`head = f"{MINIMAL_INSTRUCTION}\n\n{task_prompt}"`) and never modified. This is the only constancy that survived Phase 8.0 and the reason is the same as before: the goal does not change as execution proceeds, so the part of the context that represents the goal should not change either. If the Head were rebuilt at each step, two slightly different reconstructions would produce slightly different `H_n` values for reasons unrelated to the agent's progress, and the trajectory would carry phantom variance.

What is **gone** from the Head: the 80-token cap, the `summarize_to_head` rewriting layer, and the equality-with-measurement-pipeline argument. CHECKPOINT_03 Finding 2 showed that this layer was the bottleneck — `improved_prompt` carried real structure and the summary collapsed it back to abstraction. The fix is to delete the layer, not to tune it.

---

## step_history: full accumulation, no compression

`step_history` is a Python list of strings built by `_format_step_raw(thought, action_name, action_input, observation)`. Each entry is the literal Thought, the literal Action call, and the literal Observation from one completed step, in the order they happened. New entries are appended verbatim. Old entries are never compressed, never trimmed, never re-summarized, never dropped.

The previous version of this file devoted three sections to defending three separate compression policies — meaning-level summarization for Head, recursive meaning-level summarization for Body, whitespace-only trimming for Tail. Phase 8.0 removes all three by removing the slots they applied to. There is no Body to recursively summarize and no Tail to trim, so there is no compression policy to defend.

The previous Tail-trimming argument deserves a specific note because it was the most subtle of the three. The argument was: summarizing the Tail would systematically lower measured `H_n` without lowering the actual ambiguity of the agent's situation, because a summarizer would smooth a Tavily error response (specific host, specific timeout, specific error class) into a generic paraphrase, and the agent's response distribution to the smoothed input would be tighter than its distribution to the raw input. That argument is **still correct as a general observation about smoothing** — but it was an argument *against* compressing the most-recent slot, not an argument *for* having a most-recent slot in the first place. With `step_history` carrying every step verbatim, the most-recent step is preserved by definition; there is no need to designate a separate Tail slot to protect it.

The previous Body-summarization argument is the inverse case: the Body existed to compress older history *for token budget reasons*. With no token budget, no Body, no compression. The agent at step n sees every step from 1 through n−1 in full.

Two practical consequences:

1. **Measurement input grows with steps.** `measure_semantic_entropy` is called on `head + "\n\n" + "\n\n".join(step_history)`, which is larger at step n than at step n−1. The cost of one entropy measurement at step 15 is therefore larger than at step 1. The trend-reading frame absorbs this — within a single task the y-axis can shift step-to-step without breaking interpretation, as long as the operator reads direction (`delta_H` sign, slope, shape) rather than treating individual `H_n` numbers as cross-step comparable.

2. **Tavily responses are now visible to every subsequent step.** Under the previous design, a Tavily response was visible to its own step's Thought (in full) but only to the next step's context (trimmed to 150 tokens), and was destroyed entirely after that. Under Phase 8.0, the same response is visible to every later step in full. This changes the agent's reasoning surface significantly — it can re-reference earlier observations directly instead of relying on the Body's lossy summary of them. Whether this helps or hurts is the empirical question Phase 8.0 pilot re-execution is meant to answer.

---

## Trend-reading frame for entropy

The `H_raw`, `H_improved`, and per-step `H_n` values are still measured. They are still recorded in `results/results.tsv` (`H_raw`, `H_improved`, `delta_H`) and `results/entropy_steps.tsv` (per-step long-format). What has changed is **how they are read**.

The previous frame compared values across measurements by absolute number, on the assumption that they shared a y-axis. The new frame reads each task's entropy trajectory as an internal pattern:

- **delta_H sign**: `H_raw - H_improved` positive means the inverse model collapsed exploration space, negative means it widened, zero means no change. The magnitude is informative but not authoritative.
- **H_n shape**: convergent (decreasing toward zero), divergent (increasing), flat (stuck), oscillating (exploring). Read from the trajectory in `entropy_steps.tsv`, not from individual numbers.
- **detect_loop firing**: the loop detector still uses `H > 0.3 × H_raw AND d²H/dt² ≈ 0`. Both conditions are *ratios and derivatives*, not absolute values across runs, so the rule remains valid even though the y-axis is no longer constant. This is why `detect_loop` and the `loop_count` TSV column survived Phase 8.0 unchanged.

Cross-task absolute comparison of `H_n` numbers is **not done**. A single task's H_n at step 5 is not meant to be compared to a different task's H_n at step 5. Within one task, the trajectory's *shape and direction* are the unit of analysis.

---

## What this design does NOT defend

The previous version of this file ended with a long table of "load-bearing" elements — eight rows of design commitments that would require version bumps to change. Phase 8.0 invalidated most of those rows. This file does not reintroduce a similar table, because Phase 8.0 is itself an early-stage restructure and the operator may revise it again after the next pilot batch. Locking commitments prematurely was part of how the previous structure became inconsistent with its own justifications.

What this file *does* commit to:

- **The full task prompt is the Head.** No re-introduction of summarization without an explicit checkpoint that names what the new summarization layer is for.
- **`step_history` accumulates verbatim.** No re-introduction of Body, Tail, or any compression layer without an explicit checkpoint that documents the y-axis-or-other argument that justifies it.
- **Entropy is read as trajectory shape, not as cross-task numbers.** The loop-detection rule's use of ratios is what allows it to coexist with this frame.
- **`detect_loop`, `H_raw`, `H_improved`, `delta_H`, `loop_count`** are preserved as observation infrastructure and TSV columns.

What this file deliberately leaves **open** for the next pilot to decide:

- Whether N_SAMPLES should remain at 5 (pilot) or move back to 10 (full runs) after observing the cost impact of larger entropy measurement inputs.
- Whether `entropy_steps.tsv` should grow additional columns (e.g. measurement-input token count, agent-call token count) for finer-grained trend reading.
- Whether `prompt_invert`'s removed k=4 stopping rule should be reintroduced in some other form after observing how long the inverse chains run without it.

These are open because Phase 8.0 is the moment to *observe how the system behaves without these constraints*, not to immediately replace them with new constraints.

---

## Editable vs not editable

| Element | Editable? | Why |
|---|---|---|
| The Head is the full task prompt | **No, version bump required** | The 80-token bottleneck removal is the central change of Phase 8.0. Reintroducing any pre-Head compression layer requires a checkpoint argument. |
| `step_history` accumulates verbatim | **No, version bump required** | Same reason. Compression here would reintroduce the failure mode Phase 8.0 was built to remove. |
| `head` is locked at start of `run_react_loop` | **No, version bump required** | The goal does not change during execution; the part of the context representing the goal should not either. |
| Entropy measurement happens AFTER the action and observation are appended to `step_history` | **No, version bump required** | The pre-Phase-8.0 placement (before Thought) measured an empty-state baseline at step 1, which was tautological. The new placement makes every `H_n` a "post-action" snapshot. |
| `detect_loop` rule uses ratios and derivatives, not absolute values | **No, version bump required** | This is what makes the loop detector compatible with the trend-reading frame. Changing it to absolute thresholds would re-create the y-axis dependency Phase 8.0 removed. |
| The format of one `step_history` entry (`Thought: ... \n Action: ... \n Observation: ...`) | Editable | Implementation detail of `_format_step_raw`. Wording of the prefixes is editable; the three-part structure is convention not load-bearing. |
| Whether N_SAMPLES is 5 or 10 | Editable | Cost vs noise trade-off; the trend frame does not pin this. |
| `entropy_steps.tsv` columns beyond the current five (task_id, condition, level, step, H_n) | Editable | Additive columns are safe; renaming or removing existing columns is a breaking change. |
| Per-paragraph wording of this file | Editable | Explanations of the design, not the design itself. |

The five non-editable rows are the design. Everything else is implementation detail or open for the next iteration to decide.
