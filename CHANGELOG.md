# Changelog

| Version | Date | Changes |
|---------|------|---------|
| **v2.8.1** | **2026-04-08** | **Embedding model migration.** Together AI's serverless catalog as of April 2026 no longer offers a Llama-3-based embedding model. Switched to `intfloat/multilingual-e5-large-instruct` (the only serverless embedding option). spec/measurement.md updated to reflect that the load-bearing constraint is "neutral and external" rather than "must be Llama-3." No methodology change — the requirement that the embedder be separate from the generation model is preserved. |
| **v2.8.0** | **2026-04-08** | **Multi-file restructuring of v2.7.9.** Single 1132-line spec split into README.md (shell) plus 20 sub-files under spec/, implementation/, operations/, analysis/, roadmap/. Original preserved at archive/v2.7.9-monolith.md. Renamed inverse-model step "Output" → "Compose" to resolve the naming collision with the function's return value (also called the output). The rename is mechanical: prose, tables, pseudo-code, and the implementation checklist all use "Compose" everywhere. No content changes beyond what splitting/merging surfaced as new explicit justifications (notably the three justifications hidden in `spec/loop-detection.md` and the Head/Tail philosophical asymmetry argument in `spec/token-budget.md`). See `README.md` for the new structure. |
| v2.7.9 | 2026-04-08 | Consolidated t track back into main. GAIA validation Level 1 (text-only, two-stage filter) replaces self-authored tasks.json. All self-authored tasks dropped including Korean-language tasks (intentional, for single English scoring pipeline). GAIA official quasi-exact-match scorer vendored as gaia_scorer.py. False Negative control: verifier_passed column added, orthogonal to terminated_by. Metric #3 redefined from completion rate to correctness rate. Agent tool set made explicit: tavily_search / tavily_extract / final_answer. Caching (default-on, 3 caches, H_improved deliberately excluded). Cost monitoring via Tavily /usage + LLM usage accumulation. v0 rerun budget (3 runs). Reproducibility rules (task order, temperatures, seed). Failure handling for 5 scenarios. terminated_by extended to 4 values (completed / loop_detected / max_steps_reached / error). Single-model policy for all LLM roles. run_agent renamed to run_react_loop; run_single_task / run_task_both_conditions / run_experiment hierarchy introduced. |
| v2.7.8.t2.5 | 2026-04-07 | False Positive control: termination reasons separated into completed / loop_detected / max_steps_reached |
| v2.7.8.t2.4 | 2026-04-07 | Summarization noise absorbed into H measurement; cancels in ΔH because A/B share the same pipeline |
| v2.7.8.t2.3 | 2026-04-06 | run_agent made explicit as ReAct (Thought → Action → Observation); entropy measured before Thought at each step |
| v2.7.8.t2.2 | 2026-04-06 | Academic grounding: Kuhn 2023; removed vague Scientific Agent Framework; verified all citations |
| v2.7.8.t2.1 | 2026-04-06 | Methodological distinction between Head summarization (abstraction) and Tail trimming (resolution preservation) |
| v2.7.8.t2 | 2026-04-06 | Token strategy refinement: Head(Target) summarization + Tail(Action) trimming. Unified H_raw/H_improved input as 80-token summary (apples-to-apples) |
| v2.7.8.t1 | 2026-04-06 | [t1 track] Minimal instruction, 300-token dynamic budget (80/70/150), Forward-Model-compatible recursive summarization |
| v2.4.7 | 2026-04-06 | Spelled out condition-A recording logic in run_experiment flow |
| v2.4.6 | 2026-04-06 | TSV recording rules for condition A (H_improved = H_raw, delta_H = 0) |
| v2.4.5 | 2026-04-06 | Unified variable names: H₀ → H_raw, H_output → H_improved |
| v2.4.4 | 2026-04-06 | Added TOGETHER_API_KEY to benchmark.py environment variables |
| v2.4.3 | 2026-04-06 | Tidied inverse() pseudo-code; unified model/n_samples parameters |
| v2.4.2 | 2026-04-06 | Step 2 Macro-level Backward Chaining (N-k threshold); fixed missing entropy parameters |
| v2.4.1 | 2026-04-06 | Explicit independent prompt chaining in inverse.py |
| v2.4 | 2026-04-06 | Switched from NLI-based clustering to neutral embedding (Llama-3) + AgglomerativeClustering |
| v2.3 | 2026-04-05 | Removed program.md; Experiment Rules merged into README.md; file version control |
| v2.2 | 2026-04-05 | detect_loop threshold: 0.1 → alpha × H_raw (same reference for A and B) |
| v2.1 | 2026-04-05 | Result metrics 9 → 3; total metrics 12 → 6 |
| v2.0 | 2026-04-05 | Initial draft: inverse model 6 steps → 3 steps; H_raw/H_improved 2-point measurement |
