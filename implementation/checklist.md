# Implementation checklist (for Claude Code)

> Sourced from: v2.7.9 §Implementation checklist, §Implementation notes for Claude Code
> Related: [inverse.md](./inverse.md), [benchmark.md](./benchmark.md), [react-loop.md](./react-loop.md), [agent-tools.md](./agent-tools.md), [gaia-integration.md](./gaia-integration.md), [caching.md](./caching.md), [file-layout.md](./file-layout.md)

---

This is the suggested order for a from-scratch implementation. Phases 3 and 4 have a dependency: `run_single_task` (Phase 3) calls `run_react_loop` (Phase 4), so implement Phase 4 first, or stub `run_react_loop` in Phase 3 and fill it in during Phase 4.

---

## Phase 1 — Environment and vendoring

- [ ] Create the project directory structure shown in [file-layout.md](./file-layout.md).
- [ ] Write `pyproject.toml` with the dependencies listed in [file-layout.md §pyproject.toml](./file-layout.md#pyprojecttoml).
- [ ] Write `.env.example`. Ask the user to populate `.env` with actual keys.
- [ ] Download `gaia_scorer.py` from the GAIA source URL and place it at `prompt-training/gaia_scorer.py` with the header described in [gaia-integration.md §Vendoring procedure](./gaia-integration.md#vendoring-procedure). Do not modify the vendored code.
- [ ] Sanity check: `python -c "from gaia_scorer import question_scorer; print(question_scorer('42', '42'))"` → `True`
- [ ] Sanity check: `python -c "from gaia_scorer import question_scorer; print(question_scorer('forty-two', '42'))"` → `False`
- [ ] Add HuggingFace GAIA access instructions to `README.md` (form submission + token setup).

## Phase 2 — `inverse.py`

- [ ] Implement `MINIMAL_INSTRUCTION` constant.
- [ ] Implement `summarize_to_head(text, max_tokens, model)` — LLM call with `temperature=0`.
- [ ] Implement `trim_to_tail(text, max_tokens)` — meaning-preserving whitespace/filler removal.
- [ ] Implement `semantic_cluster(responses)` using Together AI embeddings + `AgglomerativeClustering`.
- [ ] Implement `measure_semantic_entropy(input_context, model, n_samples)`.
- [ ] Implement the 3 prompt templates: `prompt_target` (Target), `prompt_invert` (Invert with macro backward chaining, `k=4`), `prompt_compose` (Compose).
- [ ] Implement `inverse(raw_prompt, model, n_samples)` following the pseudo-code in [inverse.md](./inverse.md#inverseraw_prompt-model-n_samples10).
- [ ] Implement `detect_loop(entropy_history, H_raw, alpha=0.3, window=3)`.

> The third inverse-model step is named **Compose** (not "Output"). The function is `prompt_compose`. The original v2.7.9 used "Output" — see `CHANGELOG.md` v2.8.0 for the rename and the reason.

## Phase 3 — `benchmark.py` skeleton

- [ ] Define top-level constants (`MODEL`, `N_SAMPLES`, `CACHE_VERSION`, `SEED`).
- [ ] Implement cache helpers (`_cache_key`, `cache_get`, `cache_set`, `cache_hit`) — see [caching.md](./caching.md).
- [ ] Implement `load_gaia_tasks()` with the two-stage filter and per-stage logging — see [gaia-integration.md §Loader](./gaia-integration.md#loader-two-stage-filter).
- [ ] Implement `apply_sample_size_contingency()` per [gaia-integration.md §Sample size contingency](./gaia-integration.md#sample-size-contingency).
- [ ] Implement `run_experiment()`, `run_task_both_conditions()`, `run_single_task()` per the pseudo-code in [benchmark.md](./benchmark.md).
- [ ] Stub `run_react_loop()` (full implementation in Phase 4).
- [ ] Add `--task`, `--condition`, `--model`, `--n-samples`, `--no-cache` CLI flags via argparse.

## Phase 4 — Agent and tool set

- [ ] Implement `tavily_search(query)` using `tavily-python` with basic mode, `max_results=5`.
- [ ] Implement `tavily_extract(url)` using `tavily-python`.
- [ ] Implement `final_answer(answer)` as a tool that, when called by the agent, causes `run_react_loop` to exit with `terminated_by = "completed"`.
- [ ] Define the three-tool schema with the format instruction from [agent-tools.md §Final answer format](./agent-tools.md#final-answer-format) in the `final_answer` description.
- [ ] Implement `run_react_loop()` with the [a]–[h] per-step flow from [react-loop.md](./react-loop.md#the-per-step-flow-ah).
- [ ] Implement failure handling per [../operations/failure-modes.md](../operations/failure-modes.md).
- [ ] Wire `question_scorer` into `run_single_task` — called only when `terminated_by == "completed"`.

## Phase 5 — Cost monitoring and reproducibility

- [ ] Implement `log_cost_start()` and `log_cost_end()` per [../operations/cost-monitoring.md](../operations/cost-monitoring.md):
  - Call `GET https://api.tavily.com/usage` at both points.
  - Track per-provider LLM token accumulation from API response `usage` fields.
  - Look up current LLM pricing from official pages (do not hardcode from memory) and compute USD estimates.
  - Track cache hit rates.
- [ ] Ensure all LLM calls use the temperature values from [../operations/reproducibility.md](../operations/reproducibility.md).
- [ ] Set `numpy.random.seed(SEED)` and any other seeds at startup.
- [ ] Ensure task order is `shuffle=False`.

## Phase 6 — Smoke tests

- [ ] `python benchmark.py --task 0 --n-samples 3 --no-cache` — cold smoke test.
- [ ] Verify: GAIA dataset loads, first task runs both conditions end-to-end, TSV row is written.
- [ ] Verify: Tavily `/usage` delta shows non-zero credit consumption.
- [ ] Verify: `run_<timestamp>.log` contains all four cost categories.
- [ ] `python benchmark.py --task 0 --n-samples 3` — second run should hit caches, Tavily delta should be zero, LLM cost should drop significantly.

## Phase 7 — First full run

- [ ] `python benchmark.py --n-samples 10` — first full run.
- [ ] Review `results.tsv` and `run_<timestamp>.log`.
- [ ] Decide on Tavily plan upgrade based on actual credit usage.
- [ ] Decide whether to proceed to runs 2 and 3 based on LLM cost and initial signal — see [../operations/rerun-budget.md](../operations/rerun-budget.md).

---

## Implementation notes for Claude Code

1. **`"Final answer"` contains a space** — GAIA's original column name. Use `task["Final answer"]`, not `task["final_answer"]`. Same for `"Annotator Metadata"`.
2. **`MINIMAL_INSTRUCTION` is a control variable** — do not modify, do not append instructions to it, do not use it for format guidance. Format instructions live in the `final_answer` tool description only. See [agent-tools.md](./agent-tools.md#final-answer-format) and [../spec/measurement.md](../spec/measurement.md#the-minimal-instruction-system-prompt-as-control-variable).
3. **`H_improved` is intentionally not cached** — this is by design, not an oversight. It exists to surface inverse cache corruption. See [caching.md §H_improved is deliberately NOT cached](./caching.md#h_improved-is-deliberately-not-cached).
4. **`Annotator Metadata` and `file_path` fields are not used** — they leak ground-truth signal (metadata) or are irrelevant (file_path for filtered tasks). See [gaia-integration.md §Fields explicitly not used](./gaia-integration.md#fields-explicitly-not-used).
5. **Single model for all LLM roles** — do not split inverse / summarize / agent / entropy sampling across different models. v1 may explore asymmetric configurations; v0 does not.
6. **Korean-language tasks are not part of the task set** — do not add them back even if asked. The decision is documented in [gaia-integration.md §Why no self-authored tasks](./gaia-integration.md#why-no-self-authored-tasks).
7. **LLM pricing constants must be looked up at implementation time** — do not rely on training data for pricing. Check official pricing pages.
8. **The vendored scorer is bit-exact** — do not refactor, do not fix style issues, do not add type hints. Preserve it as-is for auditability.
9. **Use `Compose`, not `Output`, for the third inverse-model step** — this includes prose, function names (`prompt_compose`), and any tables that map LLM steps to Wolpert-Kawato concepts. The original v2.7.9 used "Output"; the rename is recorded in `CHANGELOG.md` v2.8.0.
