# prompt-training

> If an AI is going to do research well, it must first refine the problem.

**Version**: v2.7.9 · **Status**: v0 spec frozen, implementation pending · [CHANGELOG](./CHANGELOG.md)

---

## The one-line hypothesis

When you give a vague prompt directly to an agent, it falls into infinite loops. If you first run the prompt through an **inverse model** to lower its semantic entropy, loops drop sharply.

We test this with an A/B experiment on GAIA Level 1 and measure the effect as **ΔH** (entropy drop) correlated with loop rate and correctness.

---

## How the experiment is shaped

```
                      ┌─────────────────────────────┐
     raw GAIA task ──▶│     condition A (baseline)  │──▶ ReAct agent ──▶ verifier
                      └─────────────────────────────┘
                                    │
                                    │ vs
                                    ▼
                      ┌─────────────────────────────┐
     raw GAIA task ──▶│  condition B (inverse pre)  │──▶ ReAct agent ──▶ verifier
                      │   Target → Invert → Output  │
                      └─────────────────────────────┘

     measure H_raw ─────────────────┐
                                    ├──▶ ΔH = H_raw − H_improved
     measure H_improved ────────────┘
```

Both conditions run the same ReAct loop, the same tool set, the same verifier. The only difference is whether the prompt passes through `inverse()` first.

→ [implementation/benchmark.md](./implementation/benchmark.md) for the full A/B pseudocode.

---

## Where to go from here

The spec is split into five concerns. Start with whichever matches what you need.

### 1. Why this should work — [spec/](./spec/)

The theory and the measurement claim. Read these first if you want to understand what the experiment is actually testing.

- [hypothesis.md](./spec/hypothesis.md) — core hypothesis, Wolpert & Kawato (1998), why loops drop in B
- [measurement.md](./spec/measurement.md) — H_raw vs H_improved, 2-point measurement, Llama-3 clustering, the tape-measure noise-cancellation argument
- [loop-detection.md](./spec/loop-detection.md) — d²H/dt² ≈ 0 AND H > α·H_raw, why α·H_raw is the shared reference
- [token-budget.md](./spec/token-budget.md) — 80/70/150 split, Head summarization vs Tail trimming philosophy
- [termination-taxonomy.md](./spec/termination-taxonomy.md) — the four `terminated_by` values, the orthogonal `verifier_passed` column, False Positive and False Negative controls

### 2. How it runs — [implementation/](./implementation/)

The actual code structure. Read these when you're building or debugging.

- [inverse.md](./implementation/inverse.md) — `inverse.py`: 3-step prompt chaining, `measure_semantic_entropy()`, `detect_loop()`
- [react-loop.md](./implementation/react-loop.md) — `run_react_loop`, the [a]–[h] per-step flow, where entropy gets measured
- [benchmark.md](./implementation/benchmark.md) — `run_experiment` → `run_task_both_conditions` → `run_single_task` hierarchy, TSV schema
- [agent-tools.md](./implementation/agent-tools.md) — the three tools (`tavily_search`, `tavily_extract`, `final_answer`), final-answer format rules
- [gaia-integration.md](./implementation/gaia-integration.md) — two-stage text-only filter, `gaia_scorer.py` vendoring, schema mapping
- [caching.md](./implementation/caching.md) — 3 caches, why H_improved is deliberately NOT cached
- [file-layout.md](./implementation/file-layout.md) — directory structure, `pyproject.toml`, `.env.example`

### 3. How it's operated — [operations/](./operations/)

Rules for running the thing without fooling yourself.

- [reproducibility.md](./operations/reproducibility.md) — task order, per-role temperatures, seed, what's deterministic
- [rerun-budget.md](./operations/rerun-budget.md) — the 3-run v0 budget, why "reconsideration" means returning to spec
- [cost-monitoring.md](./operations/cost-monitoring.md) — Tavily `/usage`, per-provider LLM accumulation, cache hit rate
- [failure-modes.md](./operations/failure-modes.md) — the 5 failure scenarios and how each is handled
- [experiment-rules.md](./operations/experiment-rules.md) — what's editable vs what needs a version bump

### 4. How results are read — [analysis/](./analysis/)

What to count, what to ignore, where the known traps are.

- [metrics.md](./analysis/metrics.md) — the 3 result metrics + 3 process metrics, derived-metric rules (one column, one source)
- [temporal-drift.md](./analysis/temporal-drift.md) — GAIA's 2023 ground truth vs 2026 Tavily results, post-run manual review rule

### 5. What happens after v0 — [roadmap/](./roadmap/)

- [v0-v1-plan.md](./roadmap/v0-v1-plan.md) — branching plan based on v0 outcome (works / doesn't / partial)
- [deferred.md](./roadmap/deferred.md) — things explicitly held out of v0 and why
- [related-work.md](./roadmap/related-work.md) — how this differs from Entropy-Guided Loop, ProRefine, EPO, Semantic Uncertainty

---

## Quick facts

| | |
|---|---|
| **Task set** | GAIA validation Level 1, text-only (two-stage filter, ~30+ tasks after filtering) |
| **Agent** | ReAct with 3 tools: `tavily_search`, `tavily_extract`, `final_answer` |
| **Verifier** | GAIA's official quasi-exact-match scorer, vendored bit-exact |
| **Model policy** | Single model for all LLM roles (inverse, summarize, agent, entropy sampling) |
| **Embedding** | Together AI Llama-3 (separate from generation model) |
| **Measurement points** | 2 per task: H_raw, H_improved |
| **Budget** | ~$150 LLM + Tavily free tier, max 3 full runs |
| **Dependencies** | [pyproject.toml](./implementation/file-layout.md#pyprojecttoml) |

---

## For Claude Code: where to start implementing

See [implementation/checklist.md](./implementation/checklist.md) for the 7-phase build order. The short version:

1. Vendor `gaia_scorer.py` first (Phase 1)
2. Build `inverse.py` standalone and sanity-test it (Phase 2)
3. `benchmark.py` skeleton with `run_react_loop` stubbed (Phase 3)
4. Fill in the agent and the ReAct loop (Phase 4)
5. Cost monitoring and reproducibility plumbing (Phase 5)
6. Smoke test one task with `--n-samples 3 --no-cache` (Phase 6)
7. First full run at `--n-samples 10` (Phase 7)

---

## License

MIT. See [LICENSE](./LICENSE).
