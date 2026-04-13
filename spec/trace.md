# Trace sidecar

> Sourced from: Phase 8.1.A (commits 0556d8f, f5e624b, 2026-04-12).
> Related: [measurement.md](./measurement.md), [token-budget.md](./token-budget.md), [loop-detection.md](./loop-detection.md)
> Checkpoint: [CHECKPOINT_05](../docs/checkpoints/CHECKPOINT_05_phase_8_0_pilot_complete_phase_8_1_scoped.md) §3 Finding 8 records the diagnostic gap that produced this layer.

> **Heads-up — measurement.md inconsistency**: the trace sidecar exists because the entropy measurement layer described in [measurement.md](./measurement.md) degenerates to flat-zero on most post-Phase-8.0 tasks (CHECKPOINT_05 Finding 7). Until Phase 8.1.B rewrites `measurement.md`, treat the trace sidecar — not the entropy curve — as the primary diagnostic surface for any task where `H_n` collapses to zero.

---

## What this file defines

The per-step trace sidecar: a JSONL file written alongside each benchmark run that records the full content of every ReAct step — Thought text, Action call, Observation payload, and measured entropy — in a structured, machine-readable format. The sidecar exists because Phase 8.0's removal of the 80-token Head compression (commit b8daf4d) had the unintended side-effect of collapsing the entropy curve to flat-zero on most tasks (CHECKPOINT_05 Finding 7), which left the experiment with no per-step diagnostic surface at all (Finding 8). The trace sidecar restores observability by recording the raw step data that `step_history` held in memory but discarded on function return. This file documents the sidecar's schema and the three design decisions that shaped it.

Per-task per-condition JSONL file at `results/trace_<task_id>_<condition>.jsonl`, referenced by `results.tsv` column `trace_path`.

---

## Why this file exists

CHECKPOINT_05 Finding 8 diagnosed a diagnostic dead-end. Task 5 ran 19 steps under condition A and failed, but post-hoc analysis was forced to reconstruct the trajectory from Tavily cache files — which store query strings but no condition labels, no Thought texts, and no step ordering. Four cache-hit calls were invisible entirely (hits do not write new files). The entropy log, which was supposed to be the primary diagnostic surface, carried no information because all 19 `H_n` values were zero (Finding 7: with `N_SAMPLES=5`, 5 samples almost always cluster into one group on GAIA L1/L2 questions, producing `H_n = 0.0`).

Two things broke simultaneously. First, the entropy curve lost its resolution — a problem of the measurement layer's sample count and the discrete entropy formula's behaviour at low N, which is Phase 8.1.B work. Second, the per-step trace was never written to disk in the first place — `step_history` was a Python list inside `run_react_loop` and was discarded when the function returned. `results/results.tsv` had 10 columns, none of them per-step. The detailed log file was cost-summary only. These two facts combined meant that for any task where the entropy curve was flat-zero (most tasks), the diagnostic surface disappeared entirely. The trend-reading frame described in [token-budget.md](./token-budget.md#trend-reading-frame-for-entropy) cannot function as a diagnostic tool without traces.

The trace sidecar fixes the second problem. The first problem — entropy resolution — is a separate concern addressed by Phase 8.1.B.

---

## Schema

### Meta header (line 1)

```json
{
  "_meta": true,
  "task_id": "dc28cf18-6431-458b-83ef-64b3ce566c10",
  "condition": "A",
  "level": "1",
  "head": "You are an AI agent that solves problems using tools.\n\nMy family reunion is this week...",
  "schema_version": 1
}
```

| Field | Type | Description |
|---|---|---|
| `_meta` | `true` (literal) | Discriminator so consumers can skip this line when iterating step rows. |
| `task_id` | string | GAIA task identifier. Matches `results.tsv` column `task_id`. |
| `condition` | string | `"A"` or `"B"`. Matches `results.tsv` column `condition`. |
| `level` | string | GAIA level as string (`"1"`, `"2"`, `"3"`). |
| `head` | string | The full head text constructed at the top of `run_react_loop`: `MINIMAL_INSTRUCTION + "\n\n" + task_prompt`. Written verbatim, no truncation. This text is constant for the entire task execution — it is recorded once here, not repeated per step. |
| `schema_version` | integer | Currently `1`. Bumped when the set of fields or their semantics change. Independent of `CACHE_VERSION`. |

### Step rows (subsequent lines)

```json
{
  "step": 1,
  "thought": "I need to figure out the number of people attending...",
  "action_name": "final_answer",
  "action_args": {"answer": "2"},
  "observation": null,
  "observation_truncated": false,
  "observation_full_len": 0,
  "entropy": 0.0,
  "timestamp": "2026-04-13T00:01:26.771603+00:00"
}
```

| Field | Type | Description |
|---|---|---|
| `step` | integer | 1-indexed step number within this task execution. |
| `thought` | string | The agent's Thought text for this step, verbatim. Not truncated. |
| `action_name` | string | The tool the agent called: `"tavily_search"`, `"tavily_extract"`, or `"final_answer"`. |
| `action_args` | dict or string | The arguments the agent passed to the tool, as a JSON object. Not truncated. |
| `observation` | string or null | The tool's response, serialised as a JSON string via `json.dumps(observation, indent=2)`. Truncated to 8000 characters if longer; see `observation_truncated`. For `final_answer` steps, where no tool dispatch occurs, this is `null`. Consumers recovering the original dict should call `json.loads(row["observation"])` — the value is a JSON-encoded string, not a raw dict. |
| `observation_truncated` | boolean | `true` if the observation was longer than 8000 characters and was truncated. `false` otherwise, including for `final_answer` steps. |
| `observation_full_len` | integer | The original character length of the observation string before any truncation. Always present for consistency. For `final_answer` steps: `0`. |
| `entropy` | float | The `H_n` value measured on this step's post-action context (`head + step_history` including this step). The same value appended to `entropy_curve` and written to `entropy_steps.tsv`. |
| `timestamp` | string | ISO 8601 UTC timestamp at the moment the step row was written to disk. |

---

## Three load-bearing decisions

### 1. Sidecar JSONL file, not a TSV column

The per-step trace lives in a separate JSONL file at `results/trace_<task_id>_<condition>.jsonl`, not as additional columns in `results.tsv`.

The observation text from a single Tavily call can run to several kilobytes. Step counts are variable — one task may complete in 1 step, another may run to 19. The observation payload is a nested dict that must be serialised to a string for any flat format. Packing all of this into TSV columns would mean either (a) one row per step with the full observation JSON-escaped into a cell, destroying `results.tsv`'s readability in any spreadsheet, or (b) one row per task with a variable-length list of steps JSON-escaped into a single cell, which is worse.

The sidecar keeps `results.tsv` as a plain tabular summary — one row per task per condition, every column a scalar — and puts the per-step detail in a file whose format (one JSON object per line) matches the natural iteration unit of step-level analysis. The `trace_path` column in `results.tsv` is the link between the two: it names the sidecar file so that any consumer of the summary can locate the detail without path-guessing.

### 2. `head` text in the meta header only, not per step row

The agent's head text is recorded once in the meta header line, not duplicated into every step row.

The head is constructed once at the start of `run_react_loop` (`head = f"{MINIMAL_INSTRUCTION}\n\n{task_prompt}"`) and reused verbatim for every step's context build and every step's entropy measurement. It does not change during execution — this is an invariant documented in [token-budget.md](./token-budget.md#head-the-full-task-prompt-locked) and enforced by the code (the variable is assigned once, never reassigned). Duplicating a constant into every step row would waste disk proportionally to step count — for a 19-step task, 19 copies of a multi-paragraph prompt — without adding information. Consumers that need the head alongside a step row read it from the meta header.

If a future pipeline revision makes the head mutable per-step (e.g. a mid-execution re-prompting mechanism), the schema should add a `head_override` field to step rows that differ from the meta header's `head`, and bump `schema_version`. The current schema encodes the current invariant.

### 3. Asymmetric failure mode: meta fail-loud, step rows fail-soft

If the meta header cannot be written, the run fails loudly. If a step row cannot be written, the run logs a warning to stderr and continues.

The asymmetry is intentional and reflects different cost-of-failure calculations. A sidecar without a meta header has no `task_id`, no `condition`, and no `head` — it cannot be linked back to `results.tsv`, and step rows in it cannot be interpreted because the reader does not know what task or condition they belong to. Continuing to append step rows to an unidentifiable file produces data that is broken in a way that cannot be repaired after the fact. Failing loudly at meta-write time makes the problem visible immediately, before any LLM cost is incurred.

A missing step row is a different situation. The meta header is intact, the other step rows are intact, the `results.tsv` row is intact, and the benchmark run itself — the LLM calls, the entropy measurements, the verifier — is unaffected. Killing a 19-step Level 3 task because step 7's trace row hit a transient I/O error would discard all the LLM cost already spent on steps 1 through 6 and all the cost yet to be spent on steps 8 through 19. The trace is an observation layer, not a control layer; its failure should not propagate into the thing it observes.

The implementation reflects this split directly: `_write_trace_sidecar_meta` is called bare (exceptions propagate to `run_react_loop`'s caller), while `_append_trace_step` is wrapped in a `try/except` at the call site inside `run_react_loop` that prints a `[trace] WARNING` to stderr and continues.

---

## What is NOT in this file

- **`CACHE_VERSION`**: the trace sidecar is an output-only diagnostic layer. It does not affect `inverse.py`'s cache geometry, the entropy measurement pipeline, or the loop detection rule. Sidecar schema changes are tracked by the `schema_version` field in the meta header, not by `CACHE_VERSION`. Adding the `trace_path` column to `results.tsv` does not require a `CACHE_VERSION` bump. [token-budget.md](./token-budget.md)'s cache invariants are unaffected.

- **Entropy measurement layer redesign**: the sidecar records the `H_n` value produced by the existing measurement layer. It does not change how that value is computed. The flat-zero problem (CHECKPOINT_05 Finding 7) is a property of `N_SAMPLES=5` and the discrete entropy formula, not of the recording layer. Phase 8.1.B will address the measurement layer; the sidecar will record whatever values the new layer produces, without schema changes.

- **Loop detection threshold rewrite**: the `H_raw = 0` dead state (CHECKPOINT_05 Finding 6, [loop-detection.md](./loop-detection.md)) is Phase 8.1.C work. The sidecar is neither an input to nor an output of `detect_loop`. It records the entropy value that `detect_loop` consumes, but it does not participate in the detection decision.

---

## Editable vs not editable

| Element | Editable? | Why |
|---|---|---|
| Sidecar is a separate JSONL file, not TSV columns | **No, version bump required** | The separation is load-bearing for `results.tsv` readability and for the per-step iteration model. Merging traces back into the TSV would reproduce the problem the sidecar was designed to solve. |
| `head` is in the meta header only | **No, version bump required** | Depends on the head-is-locked invariant from [token-budget.md](./token-budget.md). If head becomes mutable per-step, the schema must change (add `head_override` to step rows, bump `schema_version`). |
| Meta write fails loud, step write fails soft | **No, version bump required** | The asymmetry is the core safety property of the trace layer. Reversing it (fail-soft on meta) would allow unidentifiable sidecar files; reversing the other direction (fail-loud on step) would let trace I/O errors kill benchmark runs. |
| `observation` truncation limit (8000 chars) | Editable | A space-vs-completeness trade-off. The limit can be raised or lowered without changing the schema, as long as `observation_truncated` and `observation_full_len` continue to be set correctly. |
| `schema_version` numbering | Editable | The number itself is a counter. What matters is that it is bumped on any change to the set of fields or their semantics. |
| `timestamp` precision and timezone | Editable | Currently ISO 8601 UTC via `datetime.now(timezone.utc).isoformat()`. The timezone convention is UTC; the sub-second precision is whatever Python provides. Neither is load-bearing. |
| Per-paragraph wording of this file | Editable | Explanations of the design, not the design itself. |

The first three rows are the design. Everything else is implementation detail or tuning.
