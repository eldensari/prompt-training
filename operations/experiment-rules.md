# Experiment rules

> Sourced from: v2.7.9 §Experiment Rules
> Related: every other file in this repo — this is the master editability table

---

## Purpose

This file is the master list of what can be changed without a version bump and what cannot. Every other file in `spec/`, `operations/`, and `analysis/` carries its own local "What is and is not editable" table at the bottom; this file collects the *project-level* version of the same rules.

The rule of thumb: if a change would produce a TSV row that means something different from what it claimed to mean in a prior run, the change requires a version bump. If a change improves explanation, prompt template wording, or operational ergonomics without changing the meaning of the result table, no version bump is needed.

---

## Editable

These can change without a version bump. Improvements are expected.

- The Target / Invert / Compose system prompts in `inverse.py`. The wording of the inverse model's three prompts is **the experimental subject** — improving them is the whole point of the project. See [../spec/hypothesis.md](../spec/hypothesis.md) for the structural constraints (3 steps, names, no shared history).
- The agent execution logic and per-step flow details in `benchmark.py` / `inverse.py`, *as long as the per-step flow [a]–[h] in [../implementation/react-loop.md](../implementation/react-loop.md) is preserved*.
- The `MODEL` and `N_SAMPLES` constants — but bumping `CACHE_VERSION` together is required when either changes.
- The cache version string itself.
- The Tavily multimodal URL pattern list in `load_gaia_tasks` (for false-positive filtering).
- The `summarize_to_head` prompt template wording, as long as it stays at temperature 0 and respects the 80-token cap.
- The `trim_to_tail` whitespace/filler rules, as long as they remain meaning-preserving.
- Per-paragraph wording, examples, analogies, tables that exist for explanation rather than for methodology.
- Per-cache-subdir presentation choices in cost monitoring.
- The exact filename / tag scheme that distinguishes smoke-test rows from result rows.

## NOT editable without a version bump

These are the load-bearing elements. Changing any of them changes what every prior result row means, and a version bump is required so that future readers can correctly interpret which run produced which numbers.

- `measure_semantic_entropy()` function signature and semantics.
- The measurement question text (`"What concrete action will the agent take next?"`).
- The minimal instruction string (`"You are an AI agent that solves problems using tools."`).
- The 6 metric definitions in [../analysis/metrics.md](../analysis/metrics.md).
- The A/B experiment structure (single inverse-model variable, paired comparison).
- The loop detection formula (`d²H/dt² ≈ 0 AND H > α × H_raw`, with `α = 0.3`, `H_raw` as the reference in both A and B).
- The verifier source — must remain bit-exact vendored from GAIA's official scorer.
- The TSV schema — `task_id`, `level`, `condition`, `H_raw`, `H_improved`, `delta_H`, `loop_count`, `total_tokens`, `terminated_by`, `verifier_passed`.
- The 80-token Head budget, the 70-token Body budget, the 150-token Tail budget, and the 300-token total.
- The Head-summarize / Tail-trim asymmetry (and the reason — see [../spec/token-budget.md](../spec/token-budget.md)).
- The clustering distance threshold (0.15), embedding model identity (Together AI Llama-3), Shannon entropy formula.
- Sampling temperature (0.7) for entropy measurement; temperature 0 elsewhere.
- The four `terminated_by` values and their definitions.
- The orthogonality of `terminated_by` and `verifier_passed`.
- The single-model policy (one model for all generation roles in v0).
- The fixed three-tool agent set (`tavily_search`, `tavily_extract`, `final_answer`).
- The two-stage GAIA text-only filter and the schema mapping that excludes `Annotator Metadata` and `file_path`.
- Task order = GAIA index ascending, `shuffle=False`.
- The deliberate non-caching of `H_improved`.

---

## How a version bump works

1. Make the change in the relevant file under `spec/`, `implementation/`, `operations/`, `analysis/`, or `roadmap/`.
2. Add a new row to `CHANGELOG.md` describing the change in the same voice as existing rows.
3. Bump the version in `pyproject.toml` and (if relevant) `CACHE_VERSION` in `benchmark.py`.
4. The next run is recorded under the new version. Mixed-version analysis is not supported — runs across version bumps are not directly comparable.

The version bump is the audit trail. If two runs disagree and one of them happened across a version bump, the changelog should explain why they disagree.

---

## Why this file exists separately

Each individual file under `spec/`, `operations/`, and `analysis/` carries its own local editability table at the bottom (see e.g. [../spec/measurement.md §What is and is not editable](../spec/measurement.md#what-is-and-is-not-editable)). Those tables are scoped to one file's content. This file is the project-level rollup, useful for two cases:

- A reviewer who wants the one-page answer to "what can change without a version bump."
- An implementer who is about to edit something and wants to check whether their change requires the bump-and-changelog ritual before committing.

Local tables are the source of truth for *how* a particular element is load-bearing (the "Why" column). This file is the source of truth for the *what* — the catalog.

---

## What is and is not editable

| Element | Editable? | Why |
|---|---|---|
| The catalog itself (the two lists above) | **No, version bump required** | This file is the master list. Adding or removing an element from the load-bearing list is itself a load-bearing change. |
| The "how a version bump works" procedure | **No, version bump required** | The procedure is the audit trail. Changing it would break audit continuity. |
| The local-table-vs-master-list division of labor | Editable | An organizational choice. If the local tables and master list ever drift apart, the master list (this file) wins. |
| Per-paragraph wording, the rule-of-thumb explanation | Editable | Explanation. |

The first two rows are load-bearing — they are the editability discipline itself. The rest is exposition.
