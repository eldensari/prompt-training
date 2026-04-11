# CHECKPOINT_04 — Phase 8.0 pipeline restructure complete

**Project**: prompt-training
**Repository**: https://github.com/eldensari/prompt-training
**Local**: C:/Users/433/Documents/prompt-training
**Checkpoint date**: 2026-04-10 (Session 4 close)
**Preceding checkpoint**: `docs/checkpoints/CHECKPOINT_03_pilot_complete_with_bottleneck_finding.md`
**HEAD at checkpoint**: `b8daf4d` (Phase 8.0: remove summarize/trim bottleneck, full-prompt Head, relocate entropy measurement)

---

## 1. Framing

This was an **execution session**, not a diagnostic one. CHECKPOINT_03 ended with Finding 2 (the 80-token re-compression bottleneck) as a hypothesis to confirm. Phase 7.5.A confirmed it visually with a $0 cache read. The bulk of this session was the restructuring of the pipeline to remove the bottleneck — Phase 8.0.

The session also re-examined the Body/Tail 3-slot context structure that lived alongside the bottleneck and decided to remove it entirely. The justification chain: entropy was demoted to a trend-reading tool in CHECKPOINT_03, the trend-reading frame does not require y-axis consistency, the y-axis requirement was the only load-bearing reason for the 3-slot structure, therefore the 3-slot structure has no remaining justification.

Single most important sentence:

> **The pipeline has been restructured: agent now sees full prompt as Head, full step history accumulates with no compression, entropy is measured after each completed step. Phase 7.5.B and Phase 7.5.C from CHECKPOINT_03 §8 are superseded by Phase 8.0 — they were too small a fix.**

---

## 2. Git state

- HEAD: `b8daf4d` — Phase 8.0: remove summarize/trim bottleneck, full-prompt Head, relocate entropy measurement
- Branch: main
- Working tree: clean
- 5 commits ahead of origin (unpushed; push is optional)
- All Phase 7 artifacts in `results/pilot_*.tsv` and `results/pilot_*.log` remain untouched (gitignored). They are no longer reproducible since CACHE_VERSION moved past them.

Recent commits:
```
b8daf4d Phase 8.0: remove summarize/trim bottleneck, full-prompt Head, relocate entropy measurement
348b2e7 docs: add §3.5 decisive moments and §13 template to CHECKPOINT_03
8745575 docs: add CHECKPOINT_03 (pilot complete, bottleneck finding)
536445d Phase 7 pilot: lower clustering threshold 0.15 → 0.08
2e04d34 docs: add CHECKPOINT_02 (pilot preparation complete)
```

---

## 3. Findings from this session

### Finding 3 — Phase 7.5.A confirmed Finding 2 visually

A $0 visual diagnostic read the cached `inverse()` output for Tasks 2 (dc28cf18), 4 (3627a8be), and 6 (e961a717). For each task, the four nested fields `target`, `inversion`, `improved_prompt`, `improved_summary` were dumped and read manually. Result:

- `target` and `inversion` looked sensible across all three tasks. The Wolpert-Kawato structure was working at the conceptual level.
- `improved_prompt` was rich and structured (Task 2: 350+ words listing every family member, the consumption rates, the rounding rule). Critical constraints were present in this stage.
- `improved_summary` (the one-sentence re-compression) collapsed back to abstractions. Task 2's `improved_summary` re-introduced "counting attendees" as an abstract noun, dropping the explicit family enumeration that `improved_prompt` had built.

Conclusion: the inverse model's structure is real, but it is silently destroyed by `summarize_to_head` in the Compose-to-summary step. CHECKPOINT_03 Finding 2 confirmed.

### Finding 4 — The Body/Tail 3-slot structure exists only because of the entropy y-axis requirement

A line-by-line read of `spec/token-budget.md` showed that every load-bearing justification of the 80-token Head, the 70-token Body, the 150-token Tail, and the 300-token total chained back to a single root: the entropy y-axis must stay consistent so that `H_n` is comparable to `H_raw` and `H_improved` for the loop-detection threshold. CHECKPOINT_03 §6 demoted entropy to a trend-reading observation tool. The trend-reading frame does not require y-axis consistency. Therefore the 3-slot structure has no remaining load-bearing justification.

This finding is what made Phase 8.0 expand beyond just removing summarize_to_head. The whole compression layer fell with the same argument.

---

## 3.5. Decisive moments in this session

Seven turns initiated by Elden altered the trajectory of this session. They are listed in the order they happened.

1. **Acknowledgement that the bottleneck finding in CHECKPOINT_03 needed visual confirmation, not direct intervention.** Without this, Phase 7.5.B (compose template tweak + re-run) might have been executed first, masking the deeper structural issue.

2. **Refusal to accept "demote entropy by removing measurement".** When Claude proposed removing `measure_semantic_entropy` calls because the new full-prompt Head would make them expensive, Elden corrected: entropy is the primary observation tool of this project; measurement infrastructure is non-negotiable; only the measurement input may change.

3. **Re-framing entropy interpretation from absolute-value comparison to trend reading.** Elden made the point explicitly: it is not H_raw vs H_improved as numbers that matter, it is delta_H sign and H_n trajectory shape. This unlocked Phase 8.0 because it freed the pipeline from y-axis consistency.

4. **Insistence on observation-before-design.** When Claude attempted to design Phase 8.0 directly, Elden redirected: "first see what an agent step actually looks like, then judge whether 3-slot is necessary, only then design." Claude jumped to design twice and was corrected twice.

5. **Decision that Body/Tail must be re-examined as a unit, not preserved by default.** This question opened the door to removing the entire compression layer, not just `summarize_to_head`.

6. **Decision that the entropy measurement should occur after the action and observation, not before the Thought.** This collapsed the "step 1 empty-state baseline" and aligned every measurement with "post-action state". The H_improved → H_n=1 → H_n=2 sequence is now a continuous trajectory of post-action snapshots.

7. **Decision to keep `summarize_to_head` / `summarize_to_body` / `trim_to_tail` as fully deleted, not as dead code.** Claude proposed leaving them as dead code "in case future phases need them"; Elden ruled delete entirely. This kept the diff clean and forced the design commitment.

### Hypothesis amplitude during the session

The interpretation of how the pipeline should be restructured shifted four times:

1. Initial: "Add a fix to prompt_compose so critical constraints come first in its output, hoping they survive summarize_to_head's one-sentence compression." (Phase 7.5.B in CHECKPOINT_03 §8)
2. After entropy framing correction: "Remove summarize_to_head entirely, agent sees full prompt as Head; keep Body/Tail to manage execution history."
3. After Body/Tail re-examination: "Remove Body/Tail too; use simple step_history accumulation; entropy measurement input grows with steps but that's fine because trend reading does not require constant y-axis."
4. After observation that step 1's pre-Thought entropy measurement was tautological: "Move entropy measurement to after action+observation; step 1's measurement is now meaningful as 'state after first action', not 'state of empty context'."

Interpretation 4 is what the b8daf4d commit implements.

---

## 4. What changed in code (Phase 8.0 commit b8daf4d)

Diff stat: 2 files changed, 139 insertions(+), 388 deletions(-).

### inverse.py

- DELETED functions: `summarize_to_head`, `summarize_to_body`, `trim_to_tail`. Their templates and the `_CHARS_PER_TOKEN`, `_FILLER_PATTERNS` constants. The `import re` that only `trim_to_tail` used.
- MODIFIED `inverse()`:
  - H_raw measurement now reads `f"{MINIMAL_INSTRUCTION}\n\n{raw_prompt}"` (full prompt, no summary).
  - H_improved measurement now reads `f"{MINIMAL_INSTRUCTION}\n\n{improved_prompt}"` (full prompt, no summary).
  - All three `_llm_call` invocations (target/invert/compose) raised from `max_tokens=512` (or 1024) to `max_tokens=8192`.
  - Return dict: removed `raw_summary` and `improved_summary` keys. Added `target_tokens`, `invert_tokens`, `compose_tokens` keys (per-stage token totals).
- MODIFIED `prompt_invert` template: removed the "stop at 5 steps total (k=4)" stopping rule. The macro-level backward chaining instruction itself remains; the LLM now chooses chain depth naturally.
- LEFT UNTOUCHED: `detect_loop`, `measure_semantic_entropy`, `semantic_cluster`, `_llm_call`, all shared state, all constants except those listed above.

### benchmark.py

- REMOVED imports of `summarize_to_head`, `summarize_to_body`, `trim_to_tail` from inverse.
- BUMPED `CACHE_VERSION` from `v2.8.1-002` to `v2.9.0-001`. All prior cache entries are now invisible (cache key includes CACHE_VERSION).
- MODIFIED `run_task_both_conditions`:
  - Removed both `summarize_to_head` calls (raw_summary, improved_summary).
  - H_raw measurement input is now `task["Question"]` itself.
  - H_improved measurement input is now `improved_prompt` itself.
  - h_raw cache value stores `{"H_raw": H_raw, "raw_prompt": raw_prompt}` instead of `{..., "raw_summary": ...}`.
  - Condition A and Condition B both pass full prompt to `run_single_task` via the renamed parameter `task_prompt`.
- RENAMED `summarized_query` parameter to `task_prompt` in `run_single_task` and `run_react_loop`.
- REWROTE `run_react_loop` per-step state management:
  - `head` is built once: `f"{MINIMAL_INSTRUCTION}\n\n{task_prompt}"`. No summarization.
  - Removed `previous_body`, `step_n_minus_1_raw`, `step_n_minus_2_raw`, `new_body`, `new_tail`.
  - Removed `summarize_to_body` and `trim_to_tail` calls.
  - Removed end-of-step bookkeeping shift.
  - Added `step_history: list[str] = []`.
  - Context assembly: `head + "\n\n" + "\n\n".join(step_history)` (or just `head` when step_history is empty).
- MOVED entropy measurement position:
  - Previous: top of for-loop body, BEFORE `_call_agent_with_retries`. Step 1 measured an empty post-Head state.
  - Current: AFTER the action and observation are appended to `step_history`. Step 1 measures post-first-action state. Per-step flow is now: build context → agent thought+action → tool dispatch → format current_step_raw → append to step_history → measure entropy on updated context → detect_loop → completion check → max_steps check.
- ADDED `results/entropy_steps.tsv` per-step long-format logging:
  - New module-level constants `ENTROPY_STEPS_PATH` and `_ENTROPY_STEPS_COLUMNS`.
  - New helper `_append_entropy_steps(task_id, condition, level, entropy_curve)` that appends one row per step. Header written only on first call (file does not yet exist).
  - Called from `run_single_task` after `run_react_loop` returns, before the verifier call.
- LEFT UNTOUCHED: `detect_loop` import and call, `loop_count` TSV column, `TSV_COLUMNS` schema in general, `gaia_scorer` integration, all CLI arguments, all cache helpers, all cost monitoring, the agent retry logic (`_call_agent_with_retries`).

### Verification before commit (all 7 passed)

1. `python -m py_compile inverse.py benchmark.py` → ok
2. `python -c "import inverse; import benchmark; print('imports ok')"` → ok
3. `grep -c "summarize_to_head\|summarize_to_body\|trim_to_tail"` in both files → 0
4. `CACHE_VERSION == 'v2.9.0-001'` → ok
5. Inside `run_react_loop`: `_call_agent_with_retries` at line 791, `measure_semantic_entropy` at line 863. Entropy is measured AFTER the agent call.
6. `python benchmark.py --help` → CLI shows `--task-id`, `--level`, `--condition`
7. `from inverse import detect_loop; detect_loop([0.5, 0.5, 0.5], 1.0)` → returns `{'is_loop': True, 'loop_start_step': 0}`

---

## 5. spec/token-budget.md status

Not yet rewritten. The spec still describes the 80/70/150/300 structure as load-bearing. This is **inconsistent with the b8daf4d commit** and must be addressed. Elden has stated they will draft the rewrite themselves; this checkpoint records the obligation.

The rewrite must:
- Replace "80-token Head locked at start" with "Full task prompt (raw or improved) used as Head, locked at start".
- Remove the Body and Tail sections entirely. Replace with "step_history: full accumulation of formatted step records; no compression".
- Replace "300-token total" with no fixed total.
- Replace the load-bearing argument about y-axis consistency with: "Entropy is now a trend-reading observation tool. Absolute-value comparability across tasks is not required. Within a single task, the entropy trajectory is read for direction (delta_H sign, H_n shape, detect_loop firing) rather than as numeric comparison to a threshold."
- Keep the section explaining `detect_loop`'s `H > 0.3 * H_raw AND d²H/dt² ≈ 0` rule. This rule is compatible with the trend frame because it uses ratios and derivatives, not absolute values across runs.

---

## 6. Budget state

- Spent through CHECKPOINT_03: $15.47 ($6.57 Session 1 + $8.90 Session 2 pilot)
- Spent in Session 4 (this session): $0 (Phase 7.5.A was a $0 cache read; Phase 8.0 was code-only; CHECKPOINT_04 is text-only)
- Phase 8.0 pilot re-execution estimate: ~$10-20 (uncertain — full-prompt Head increases per-step measurement cost; trade-off with no Body summarization cost)
- Main 18 estimate (deferred): unknown until Phase 8.0 pilot is complete

---

## 7. Next state transition — Phase 8.0 pilot re-execution

The next session loading this checkpoint should execute the same 6 pilot tasks under the new pipeline.

### Step 8.0.A — Pilot re-execution (the same 6 tasks)

For each of the six pilot task_ids:
- L1: 8e867cd7-cff9-4e6c-867a-ff5ddc2550be (Mercedes Sosa)
- L1: dc28cf18-6431-458b-83ef-64b3ce566c10 (mashed potatoes)
- L2: 17b5a6a3-bc87-42e8-b0fb-6ab0781ef2cc (invasive species)
- L2: 3627a8be-a77f-41bb-b807-7e1bd4c0ebdf (mollusk shell)
- L3: 676e5e31-a554-4acc-9286-b60d90a92d26 (1959 fruit/vegetable standards)
- L3: e961a717-6b25-4175-8a68-874d28190ee4 (Asian monarchies)

Run sequentially with `timeout 1800 python benchmark.py --level <N> --task-id <id> --n-samples 5`. Cache is invalidated by CACHE_VERSION bump, so every task is a cold run. Foreground only — explicit `timeout 1800` shell wrapper to avoid the bash_tool background-detach hard-limit bypass observed in Session 2.

Cost expectation: each task may cost more than the Session 2 equivalent because the full prompt is now passed to entropy measurement N_SAMPLES=5 times per step. Watch the per-task cost. Abort the batch if any single task exceeds $5 or cumulative exceeds $20 — these limits are higher than CHECKPOINT_02's $5/$15 because we expect higher per-step measurement cost from larger inputs.

Capture for each task:
- `results/pilot_8_0_<short_id>.tsv` (copy of results.tsv before next run overwrites)
- `results/pilot_8_0_<short_id>.log` (tee from stdout)
- `results/entropy_steps.tsv` will accumulate across all six runs (do NOT delete between runs — it is the trend dashboard's raw input)

### Step 8.0.B — Trend dashboard first version

After all six tasks complete, build a first trend dashboard from `results/entropy_steps.tsv`. The dashboard does not need to be sophisticated — for the first iteration, plot per-task H_n trajectories for both A and B side by side. Read for: delta_H sign (H_improved vs H_raw, then trajectory direction), H_n shape (convergent/divergent/flat/oscillating), detect_loop firing.

The dashboard design itself is intentionally deferred — Elden chose to design it after seeing the actual trajectory shapes, not before.

### Step 8.0.C — Decision gate

After 8.0.A and 8.0.B, compare the new B condition results to the Session 2 pilot results:

| Outcome | Decision |
|---|---|
| B-new shows correctness improvement on 2 or more of the 6 tasks compared to B-old | Strong signal. Proceed to main 18 with this pipeline. |
| B-new correctness equals B-old but shows clearer trajectory shapes (convergence visible) | Pipeline is healthier even if outcome unchanged. Re-evaluate whether 6 tasks are enough or main 18 is needed. |
| B-new performs worse than B-old on correctness | Phase 8.0 introduced regression. Inspect entropy_steps.tsv to identify failure mode. Do NOT rollback automatically — analysis first. |
| Tasks crash or behave erratically | spec/token-budget.md inconsistency may be causing structural issues. Inspect run_react_loop output and CACHE_VERSION freshness. |

The Phase 8.0 pilot result interpretation must use the trend-reading frame, not absolute-value comparison. Per-task trajectory shape is the primary metric; correctness is a secondary check.

---

## 8. Operational lessons from Session 4 (carry forward)

1. **Observation must precede design.** Twice in this session, Claude attempted to design pipeline changes before observing what an agent step actually looks like. Both times Elden corrected. The corrected order is: observe → judge → design. Future sessions should treat any "design first" impulse as a flag to step back and verify what is actually happening in the system being designed against.

2. **Self-correction within a long session is sustainable when the operator names the framing error explicitly.** Several times in Session 4, Claude drifted toward "remove the entropy measurement to save cost" or "make the change minimal". Each time, naming the framing error directly ("entropy is the observation tool, not optional infrastructure") allowed the correction to stick rather than re-emerging in the next turn.

3. **Spec/code inconsistency is a real risk after structural changes.** spec/token-budget.md remains in its pre-Phase-8.0 form in the main branch. This is intentional (Elden will rewrite it) but it must not be forgotten — if a future session reads token-budget.md and treats it as ground truth, the entire 3-slot framing returns. The §5 section above records this obligation.

4. **The relay working method scales to large changes.** Two source files modified, 388 deletions, 139 insertions, all in one commit, all done through prompt-relay between Claude (this conversation) and Claude Code (separate session). The session's coordination overhead was non-trivial but manageable. The discipline holds.

---

## 9. Safety notes

Inherited from CHECKPOINT_03 §10. Unchanged unless noted.

**NEVER**: touch `.env.example`; echo `.env` contents; re-invoke a running benchmark.py process; commit `results/` or `cache/`; treat 1 datapoint as pattern evidence; accept bash_tool background detach for benchmark runs without explicit wrapper.

**ALWAYS**: read the current checkpoint fully before acting; use explicit `timeout 1800` shell wrapper for any long-running command; capture stdout + copy results.tsv between tasks; preserve data from self-terminating tasks even if they exceed wall-clock limits; be honest about what is observed vs hypothesised.

**NEW in Session 4**:
- Before designing any pipeline change, observe what the current pipeline actually produces. Do not skip this step under time pressure.
- spec/token-budget.md is currently inconsistent with code (Phase 8.0 pre-rewrite state). Do not use it as ground truth until Elden's rewrite lands.
- entropy is a primary observation tool, not optional infrastructure. Do not propose removing measurement to save cost.

---

## 10. New session bootstrap block

To continue work, open a new Claude conversation and paste the following prompt followed by the full contents of this file:

```
This is a continuation of the prompt-training project. Load the checkpoint below in full before acting. Pay special attention to §1 (framing), §3 (Findings 3 and 4), §3.5 (decisive moments — observe before design), §4 (what changed in code), §5 (spec/token-budget.md is inconsistent with code, do not treat as ground truth), §7 (next state transition — Phase 8.0 pilot re-execution), §8 (operational lessons), and §9 (safety notes).

Your job: execute §7 Step 8.0.A — re-run the same 6 pilot tasks under the new Phase 8.0 pipeline. Cache is invalidated by CACHE_VERSION bump v2.9.0-001, so every task is a cold run. Use sequential foreground execution with explicit `timeout 1800` wrapper. Watch for higher per-step measurement cost.

Working method: I (Elden) do not let you write code directly. You produce Claude Code prompts that I paste into a separate Claude Code session. I relay outputs back to you. You review, decide, and produce the next prompt.

Before executing: acknowledge the checkpoint, identify anything ambiguous in §7 Step 8.0.A, and propose the Claude Code prompt for the first task (Mercedes Sosa, L1, 8e867cd7). Wait for my OK before I paste it to Claude Code. Use the trend-reading frame for all entropy interpretation.

When producing the next checkpoint at the close of this session, follow the template in §13 of CHECKPOINT_03 (inherited here). Inherit §9 Safety notes with any additions from this session's Operational lessons, and do not rewrite the template itself unless you have a structural reason documented in that checkpoint's §1 framing.

---

[PASTE FULL CONTENTS OF CHECKPOINT_04_phase_8_0_pipeline_restructure.md HERE]
```

---

## 11. End of CHECKPOINT_04

Session 4 closes after this file is committed. Phase 8.0 code is in HEAD `b8daf4d`. The pipeline now matches the trend-reading entropy frame and removes the 80-token bottleneck. The next session begins with Phase 8.0 pilot re-execution from the bootstrap block above.
