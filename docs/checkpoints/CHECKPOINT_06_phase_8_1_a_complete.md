# CHECKPOINT_06 — Phase 8.1.A complete, Phase 8.1.A.Plus scoped (Session 6 post-close extension)
Project: prompt-training
Repository: https://github.com/eldensari/prompt-training
Local: C:/Users/433/Documents/prompt-training
Checkpoint date: 2026-04-12 (Session 6 close)
Preceding checkpoint: docs/checkpoints/CHECKPOINT_05_phase_8_0_pilot_complete_phase_8_1_scoped.md
HEAD at checkpoint: 27480c0 (spec: add trace.md documenting the Phase 8.1.A trace sidecar layer)

## 1. Framing
Session 6 was an execution session for Phase 8.1 Step A — per-step trace persistence — and a workflow-evolution session that changed how Elden and Claude collaborate. Both threads ran in parallel and both closed at session end.

The execution thread followed §7B's mandated single-step rule. Phase 8.1.A was decomposed into 4 sub-tasks: (1) read current `run_react_loop` and `step_history` shape without modifying anything (deferred design choices were locked at this point — sidecar JSONL over TSV column, JSONL with meta header, observation 8000-char cap, head in meta header only, asymmetric failure mode), (2) implement the trace sidecar writer in `benchmark.py`, (3) add the `trace_path` column to `results.tsv`, (4) document the entire layer in `spec/trace.md`. Each sub-task produced exactly one commit with explicit invariant verification before and after. Cumulative cost: $0.50 for one validation run on Task 2 (mashed potatoes, dc28cf18). All four sub-tasks landed without scope crawl. The §7 Step 8.0.C decision gate from CHECKPOINT_05 remains deferred until Phase 8.1 lands.

The workflow thread was triggered mid-session by Elden's observation that Claude was passing technical jargon back to him for decisions that should have been compressed first. Three workflow rules were established and applied immediately: (a) Elden reads Claude's metaphor-language summary and decides; Claude holds all technical detail in its own head, (b) raw data is exposed only at "decision branches that are expensive to undo" — Claude judges which decisions qualify, (c) the running-river principle applied to the collaboration itself: Elden should not become the bottleneck of his own workflow. The trigger for this evolution was CHECKPOINT_05 §3.5 decisive moment 2 (the token-direction misread), which had cost two turns of wrong narrative before Elden caught it. Session 6 made that lesson explicit and operational.

The session also surfaced two findings about `inverse()` itself that did not exist in any prior checkpoint. First, Elden's anchor "5단계 → 3단계 was intentional" was verified against `inverse.py` directly: the function calls 3 LLM steps (Target / Invert / Compose), not 5. Second, Elden caught Claude in a self-contradiction when Claude claimed "inverse() does not use the LLM's prior knowledge." The Invert step in particular has no guard against prior-knowledge use, and the mashed potato Condition B head (which Elden had read directly two turns earlier) demonstrated arithmetic procedural knowledge being injected by the inverse model. Interpretation A was adopted: inverse() is intended to mobilize the LLM's prior knowledge to restructure vague prompts into procedural instructions, consistent with the Wolpert & Kawato (1998) inverse-model framework where the inverse model operates on top of a learned forward model. This is not a code change but a clarification of what the experiment is actually testing. It also opens a future hypothesis: Task 5's confident-wrong-answer failure mode may be caused by inverse() mobilizing incorrect prior knowledge during backward chaining — testable by reading the Task 5 inverse cache entry post-8.1.B at zero LLM cost.

Single most important sentence:

Phase 8.1.A is complete and committed across three commits (0556d8f trace writer, f5e624b trace_path column, 27480c0 spec/trace.md), the diagnostic-surface gap from CHECKPOINT_05 Finding 8 is closed, and Phase 8.1.A.Plus (cost-frontier validation: planner=sonnet / executor=haiku, inserted Session 6 post-close) becomes the next session's single immediate task. The workflow itself evolved during this session — Elden now decides from metaphor-language summaries with raw exposure only at decision branches — and that evolution is encoded in §9 safety notes as a load-bearing operational rule.

---

## 2. Git state

HEAD: 27480c0 — spec: add trace.md documenting the Phase 8.1.A trace sidecar layer
Branch: main (3 commits ahead of origin)
Working tree: clean except for results/ artifacts (gitignored)
inverse.py: byte-identical to b8daf4d. Verified via `git diff b8daf4d HEAD -- inverse.py` (empty) at multiple points in this session.
benchmark.py: changed by 8.1.A across 3 commits, +128 lines total.

Recent commits:
27480c0 spec: add trace.md documenting the Phase 8.1.A trace sidecar layer
f5e624b Phase 8.1.A: add trace_path column to results.tsv (Option B)
0556d8f Phase 8.1.A: add per-step trace sidecar writer (no schema change to results.tsv)
c33aa6d docs: add CHECKPOINT_05 (Phase 8.0 pilot complete, Phase 8.1 scoped as 4-step roadmap)
cc6a573 spec: rewrite token-budget.md for Phase 8.0 (full-prompt Head, no compression, trend-reading frame)

Files produced this session (gitignored except for committed code/spec):
results/trace_dc28cf18-6431-458b-83ef-64b3ce566c10_A.jsonl  (1 step row, validation run)
results/trace_dc28cf18-6431-458b-83ef-64b3ce566c10_B.jsonl  (1 step row, validation run)
results/validation_8_1_a_A.log
results/validation_8_1_a_B.log

CACHE_VERSION unchanged: v2.9.0-001. Phase 8.1.A is purely an output-only diagnostic layer addition; cache geometry is untouched.

---

## 3. Findings from this session

### Finding 10 — Task 2 is a ceiling task; Phase 8.1.B's mini-experiment must use floor tasks

The validation run for Phase 8.1.A used Task 2 (dc28cf18, mashed potatoes, GAIA Level 1) on both conditions A and B. Both runs produced the correct answer ("2") in exactly one ReAct step, with `entropy = 0.0` for the single step row in both conditions. Elden read the resulting trace sidecar files directly and observed that:

1. Condition A's head was the GAIA original prompt (informal, family-narrative style). The agent solved it in one step by enumerating attendees, classifying them, applying the consumption rates, and computing the answer — all before calling `final_answer`.
2. Condition B's head was the inverse model's improved prompt: a procedural specification that explicitly instructed enumeration → classification → rate application → arithmetic conversion → ceiling-rounding. The agent followed the procedure and produced the same answer in one step.

Both arrived at "2." This task is too easy: the agent does not need the inverse model's procedural restructuring to solve it, and the entropy measurement layer cannot distinguish between the two conditions because both terminate in 1 step at `H_n = 0`. Task 2 is a "ceiling task" — both conditions hit the maximum possible quality, and the experimental signal collapses to zero.

This explains the puzzle in CHECKPOINT_05 Finding 5: Task 2 recovered under both Phase 8.0 condition A and condition B, even though the original Finding 2 attribution to summarize_to_head destruction predicted only B-side recovery. The actual cause is simpler — Task 2 is solvable from the raw prompt under any reasonable prompt-structure regime, so any pipeline change that does not actively damage prompt quality will produce A-side recovery.

The implication for Phase 8.1.B (entropy measurement layer redesign) is direct: the mini-experiment must not use ceiling tasks for the measurement-resolution sweep. The whole point of the sweep is to find an N_SAMPLES setting (or a different metric, or a different MEASUREMENT_QUESTION) under which the entropy curve can distinguish meaningful trajectories from each other. A ceiling task always produces `H_n = 0` regardless of measurement layer, so it provides no signal about the layer's resolution. The mini-experiment must use floor tasks — tasks where the entropy curve has a chance to be non-zero because the agent's next-action distribution is genuinely uncertain. Task 5 (1959 standards, L3, 19 steps in CHECKPOINT_05) is the canonical floor task in the existing pilot set. Tasks 3 and 4 (L2, 3-6 steps) are intermediate. Task 2 is provably ceiling. Task 1 needs re-checking (it was 3 steps in Session 5 but the difficulty profile is unclear).

Phase 8.1.B should run the N_SAMPLES sweep on a small set of {Task 5} ∪ {one of Task 3/4} as the measurement target, with Task 2 reserved for cheap regression validation (not measurement signal). This is a planning constraint, not a finding about the trace layer itself.

### Finding 11 — Cost-frontier hypothesis: planner sonnet / executor haiku (Session 6 post-close addition)

After Session 6 closed, Elden proposed a complementary hypothesis: the inverse model's primary value may not be higher correctness, but equal correctness at lower cost. Specifically — if `inverse()` (run on a strong model, sonnet) produces a procedural prompt self-contained enough that a weaker executor (haiku) can follow it to the same answer a sonnet executor would reach, then the meaningful comparison is not A (raw + sonnet) vs B (inverse + sonnet) but A (raw + sonnet) vs B' (inverse[sonnet] + haiku). B' is on a cheaper cost-quality frontier. This reframes `inverse()` from a "make the agent smarter" tool into a "get the same answer more cheaply" tool.

The hypothesis aligns with the Wolpert & Kawato (1998) interpretation adopted in §9, which states that `inverse()` mobilizes the LLM's prior knowledge — that was Elden's Session 6 catch (decisive moment 2, via the mashed potato Invert example). **Session 6 post-close extension to that interpretation (Claude, not in §9):** the "prior knowledge" in §9 can be identified more precisely with the **forward model** in Wolpert & Kawato's framework — the learned mapping from action to predicted outcome. Under this reading, `inverse()` operates as an inverse model on top of the LLM's forward model. A strong planner supplies a strong forward model via its prior knowledge, and the procedural prompt it produces is effectively a precomputed motor command that a weaker executor can follow without needing its own strong forward model. This is the mechanistic basis of the cost-frontier hypothesis — but it is an unverified theoretical extension, not part of §9's established interpretation. The extension should be tested, not assumed, by Phase 8.1.A.Plus.

Claude Code diagnostic on the current codebase (Session 6 post-close) classified this change as **Bucket B (small change, < 15 lines)**: both `inverse()` and `run_react_loop()` already accept `model` as a parameter, and they currently receive the same module-level `MODEL` constant from a single CLI arg (`--model`). Splitting requires adding one CLI arg (`--executor-model`, defaulting to `--model` for backward compatibility) and passing it to `run_react_loop()` while `inverse()` keeps receiving `--model`. No schema changes required. `CACHE_VERSION` is unaffected — `model_for_execution` is outside the inverse cache key.

This finding motivates Phase 8.1.A.Plus — see §7B.

---

## 3.5. Decisive moments in this session

Seven turns initiated by Elden altered the trajectory.

1. **Anchor "5단계 → 3단계 was intentional."** When Claude proposed reading inverse.py to map "what inverse() actually does vs what was intended," Elden anchored the read by stating that the reduction from 5 steps to 3 was a deliberate design choice, not a regression. This eliminated an entire branch of misreading — without this anchor Claude would have spent turns puzzling over "where did the other 2 steps go?" The anchor was verified directly by the code (3 LLM calls in inverse(): Target / Invert / Compose), and Elden's framing was confirmed.

2. **Catching Claude's self-contradiction on inverse() prior knowledge.** Claude wrote that inverse() "does not use the LLM's prior knowledge — it only restructures input." Two paragraphs earlier in the same answer, Claude had walked through the mashed potato Invert example which mobilized arithmetic procedural knowledge ("정수가 있으려면 → 5로 나눈 올림값 → 0.5 곱해서 파운드..."). Elden caught the contradiction and pushed back with "이렇게 하는 것을 보면 LLM의 사전 지식을 쓰는 것 같은데?" Claude then re-read the prompt templates carefully and found that only `prompt_target` has the "do not add unimplied requirements" guard; `prompt_invert` and `prompt_compose` have no such guard. Interpretation A was adopted (inverse mobilizes prior knowledge intentionally, consistent with Wolpert & Kawato). This is the same class of error as Session 5's "token direction misread" — Claude built a narrative on top of a partial reading and Elden caught it from the example evidence. The lesson generalizes: Claude's high-level summaries about code behavior should be cross-checked against concrete worked examples before being trusted, especially when the summary contains absolute language ("does not", "never", "always").

3. **Workflow evolution: metaphor-language summaries with raw exposure only at decision branches.** Mid-session, Elden observed that Claude was passing technical jargon back to him for decisions. Elden requested that Claude hold all technical detail and present decisions in metaphor language so that Elden could decide without mentally translating. Claude offered two options: (a) full delegation, raw never exposed, (b) raw exposed only at decision branches expensive to undo. Elden chose (b). The choice was applied immediately and held for the rest of the session. This is the most significant procedural change since CHECKPOINT_03's "observation before design" lesson and is encoded in §9 as load-bearing.

4. **Elden requested to see the trace sidecar files directly after validation passed.** Even though all 6 validation checks had passed and Claude had recommended progressing to the next sub-task, Elden chose to read the actual JSONL files. This is exactly the rule that workflow rule 3 codifies — for a contract-establishing artifact (the first real trace sidecar files the system has ever produced), raw exposure was correct even though the formal validation had cleared. Reading the files directly produced the Task 2 ceiling task observation (Finding 10) which would have been missed under pure validation-pass-pass progression.

5. **Option B vs Option A on the trace_path column.** Sub-task 3 had two viable approaches: thread trace_path through `run_react_loop`'s return dict (Option A, 8 touch points), or reconstruct the deterministic path string in `run_single_task` directly (Option B, 2 touch points). Claude Code initially recommended A as "data flow explicit." Claude reviewed and switched to B based on Sandi Metz's "duplication is far cheaper than the wrong abstraction" — coupling cost was higher than the duplication cost for a one-line deterministic path string. Elden chose B. Touch points dropped from 8 to 2, the change committed clean in 4 lines.

6. **The spec/trace.md commit-before-review ordering error and lesson.** Sub-task 4's prompt instructed Claude Code to commit `spec/trace.md` immediately after passing verification, without an intermediate "wait for Elden's raw review" step. The result was acceptable in this case (Elden read it post-commit and approved), but the ordering was wrong: spec documents are contracts, and contracts should be raw-reviewed before commit. This is the inverse of sub-task 2 (trace writer code) where Elden read the actual sidecar JSONL files after the run, which was correct because the files were the artifact being established. For sub-task 4 the artifact was the spec text itself, and Claude defaulted to "verify→commit" instead of "verify→pause→Elden raw review→commit." Future spec/document commits must include the pause step. This lesson is encoded in §9.

7. **The "Editable vs not editable" table that Claude Code added to spec/trace.md without being asked.** The prompt outline did not include this table. Claude Code observed it as a pattern in `loop-detection.md` and `token-budget.md` and applied it autonomously. Elden reviewed and accepted it. This is a good kind of autonomy — pattern-matching against existing project conventions to enrich a new file with the same conventions. It also demonstrates that Sub-task 4's prompt outline could have been looser: when Claude Code has access to high-quality reference files for tone, the structural skeleton can be terser. Future spec-writing prompts: shorter outline, more reference reading.

Hypothesis amplitude during the session:
Four reframings:
- Initial: "execute Phase 8.1.A as a single atomic step."
- Mid-session: "Phase 8.1.A is 4 sub-tasks with intermediate Elden checkpoints."
- After Elden's metaphor-language request: "the collaboration itself is a load-bearing layer — Claude's job is metaphor compression, Elden's job is direction at branch points."
- After the trace.md commit-before-review error: "spec/document commits need a different default than code commits — pause before commit is mandatory for contracts."

Reframing 4 is what §9's spec-commit safety note encodes.

---

## 4. What changed this session

Three commits, all in main, in dependency order:

- **0556d8f** — `Phase 8.1.A: add per-step trace sidecar writer (no schema change to results.tsv)`. Added `_write_trace_sidecar_meta` and `_append_trace_step` helpers in benchmark.py. Added `task_id`, `condition`, `level` as keyword-only parameters to `run_react_loop` (the only signature change to a public function this session). Wired meta header write at function start (fail-loud) and step row append after entropy measurement (fail-soft via try/except). +124 lines.
- **f5e624b** — `Phase 8.1.A: add trace_path column to results.tsv (Option B)`. Added `"trace_path"` to `TSV_COLUMNS` (now 11 columns). Added one row dict line in `run_single_task` reconstructing the path deterministically via `(RESULTS_DIR / f"trace_{task['task_id']}_{condition}.jsonl").as_posix()`. Added a clarifying comment that output-only column additions do not require CACHE_VERSION bumps. +4 lines.
- **27480c0** — `spec: add trace.md documenting the Phase 8.1.A trace sidecar layer`. Created `spec/trace.md`, 135 lines. Schema (meta header + step row, 6 + 9 fields), three load-bearing decisions (sidecar JSONL not TSV / head in meta only / asymmetric failure mode), "What is NOT in this file" cross-references to measurement.md (8.1.B), loop-detection.md (8.1.C), token-budget.md (cache invariants), and an "Editable vs not editable" table. Cross-links anchor-resolved against `spec/token-budget.md` headers (`#trend-reading-frame-for-entropy`, `#head-the-full-task-prompt-locked`).

One thing diagnosed but not changed: detect_loop's H_raw=0 dead state (CHECKPOINT_05 Finding 6) is still unfixed. It is Phase 8.1.C work, deferred until 8.1.B's measurement layer redesign settles the entropy distribution shape that the new threshold rule will calibrate against.

inverse.py untouched. CACHE_VERSION untouched. The Phase 8.0 invariants from CHECKPOINT_04 §4 remain intact.

---

## 5. spec/ status

spec/trace.md added in commit 27480c0. Cross-references to measurement.md, token-budget.md, and loop-detection.md are anchor-resolved and link to extant headers. The "Heads-up — measurement.md inconsistency" note in trace.md flags that measurement.md still describes the pre-8.1.B measurement layer, and instructs readers to treat the trace sidecar (not the entropy curve) as the primary diagnostic surface for any task where H_n collapses to zero.

CHECKPOINT_06 introduces no other spec changes. Phase 8.1.B will require a measurement.md rewrite (parallel to token-budget.md's Phase 8.0 rewrite); that rewrite is the spec obligation produced by this checkpoint, to be discharged in the session that completes 8.1.B.

---

## 6. Budget state

- Through CHECKPOINT_05: $42.28
- Session 6 (this session): $0.50 (single validation run on Task 2 dc28cf18, A+B)
- Cumulative project total: $42.78
- Phase 8.1.B mini-experiment estimate: $5–15 (per CHECKPOINT_05 §6, deliberately not re-estimated until Phase 8.1.B's design conversation; the design session must propose a per-task hard abort before the experiment runs)
- Main 18 estimate: still deferred until Phase 8.1.D (cost model rebuild) lands

Session 6's cost was unusually low because all 4 sub-tasks except validation were code/spec changes with no LLM benchmark cost. The single validation run was on a 1-step task with cache hits, producing 0.5 USD across both conditions. This cost profile is not representative of 8.1.B which will run multiple tasks under multiple parameter settings.

---

## 7. Next state transition

### §7A — Immediate next session work (single step)

The next session executes Phase 8.1 Step A.Plus only. Do not attempt Steps B, C, or D. Step A.Plus is a newly inserted phase (see §3 Finding 11) that validates the cost-frontier hypothesis — whether inverse-generated procedural prompts let a weaker executor (haiku) match a stronger executor's (sonnet) correctness on floor tasks. It depends only on 8.1.A (the trace sidecar) and is on the critical path of neither 8.1.B nor the rest — it is a parallel side-gate, not a prerequisite for the remaining roadmap. The full bootstrap instructions for this step are in §10 below. The critical constraint: Step A.Plus is a DESIGN session before it is a code session, and the first turns should be design conversation with Elden (not Claude Code prompts).

### §7B — Phase 8.1 roadmap tracker (multi-session)

This table is the single source of truth for Phase 8.1 progress. Every session that touches Phase 8.1 must update this table when closing the session and copy it forward to the next checkpoint. Do not delete rows. Do not rewrite columns. Status transitions only: TODO → ACTIVE → DONE (with commit SHA).

| Step | 작업 | 의존성 | 상태 | 완료 조건 | 결과/SHA |
|------|------|--------|------|----------|---------|
| 8.1.A | Per-step trace persistence | none | **DONE** | Trace written + readable + 1 task validation + spec update | **0556d8f → f5e624b → 27480c0** (trace writer → trace_path column → spec/trace.md). Validated on Task 2 (dc28cf18) in Session 6 at $0.50 cost. CHECKPOINT_06 §3 Finding 10 documents the validation result and its implications for 8.1.B target selection. |
| **8.1.A.Plus** | **Cost-frontier validation: planner=sonnet / executor=haiku. Validate whether inverse-generated procedural prompts let a weaker executor reach the same correctness as a stronger one on floor tasks.** | **8.1.A complete (need traces to diagnose haiku failures)** | **ACTIVE (next session)** | **Floor task set (Task 5 + 1-2 others) run under (A=raw+sonnet, B'=inverse[sonnet]+haiku); verifier_passed parity OR clear cost-quality frontier point documented; trace sidecars read for any haiku failure** | **—** |
| 8.1.B | Entropy measurement layer redesign (mini-experiment: N_SAMPLES sweep, optionally MEASUREMENT_QUESTION variants) | 8.1.A complete (need traces to read mini-experiment results) | TODO | Decision on N_SAMPLES + question prompt + (optional) metric change, documented with experimental data | — |
| 8.1.C | detect_loop H_raw=0 fallback | 8.1.B complete (new entropy distribution shape determines threshold rule) | TODO | Fallback rule implemented, retroactive validation against Task 5 trace, spec update | — |
| 8.1.D | Cost model rebuild | 8.1.C complete (cost depends on final measurement layer + loop detector) | TODO | O(N²) cost formula documented, main-18 budget cap and per-task abort thresholds set | — |

Rationale for the order (updated Session 6 post-close): 8.1.A.Plus is inserted between 8.1.A and 8.1.B as a side-gate validating the cost-frontier hypothesis. 8.1.A.Plus depends only on 8.1.A and does not affect 8.1.B/C/D's dependency chain — its result (positive, negative, or partial) does not gate the remaining roadmap. 8.1.B (entropy) remains the dependency hub for 8.1.C and 8.1.D. The dependency-respecting order is now 8.1.A → {8.1.A.Plus, 8.1.B} → 8.1.C → 8.1.D, where the braces indicate that 8.1.A.Plus and 8.1.B are independent but sequentially executed (8.1.A.Plus first for the cheap hypothesis validation, 8.1.B second as the dependency hub). Session 6 confirmed the original 8.1.A → 8.1.B → 8.1.C → 8.1.D order; Session 6 post-close added 8.1.A.Plus as a non-blocking insertion.

Mandatory session-close obligation: Whichever session completes a step must (a) flip its status to DONE with the commit SHA, (b) flip the next step's status to ACTIVE, and (c) copy the entire table forward to the next checkpoint without removing rows or columns. Failing to update this table is a framing violation — it deletes the cross-session memory of which steps remain.

Re-scoping is allowed but must be documented. If a future session discovers that a step needs to be split, removed, or reordered, the checkpoint that does so must explain why in its §1 framing. The table is a living document, not a fixed contract.

---

## 8. Operational lessons from Session 6 (carry forward)

Inherited from CHECKPOINT_05 §8. Additions from this session:

- **Workflow rule: metaphor-language summaries with raw exposure only at decision branches.** Established mid-session 6 (decisive moment 3) and applied for the rest of the session. Claude holds technical detail; Elden decides from compressed metaphor summaries. Raw is exposed only when a decision is expensive to undo (cache invalidation, schema change, contract change, file format commit, anything that requires revert to fix). Claude judges which decisions qualify. The judgment failure mode is not "exposing too much raw" but "compressing a contract decision into metaphor and skipping Elden's check." Sub-task 4's commit-before-review error is an instance of this failure mode and is the test case future sessions should remember.

- **Spec/document commits need a pause-before-commit default.** Code commits with small clean diffs and passing verification can auto-commit safely. Spec/document commits cannot — the artifact IS the contract, and Elden must read the raw text before it lands in main. Future Claude Code prompts that touch spec/, docs/, README.md, or any other contract-establishing file must explicitly include "Stop after writing, wait for OK, then commit" as a mandatory step. This is asymmetric with code prompts where verification-pass-then-commit is fine.

- **Self-contradicting summaries are caught by concrete worked examples.** When Claude writes a high-level absolute claim about code behavior ("inverse does not use prior knowledge"), the fastest way to catch errors is to compare the claim against a worked example produced earlier in the same conversation. Elden caught Claude's prior-knowledge contradiction by comparing the absolute claim against the mashed potato Invert chain Claude itself had written two paragraphs earlier. Lesson for Claude: before committing to an absolute claim about code behavior, scan whether the same conversation contains a worked example that contradicts it. Lesson for Elden: when Claude writes absolutes, check the local examples; you have caught two of these in two sessions.

- **Pattern-matching against existing project files is the right kind of autonomy.** Sub-task 4's "Editable vs not editable" table was added by Claude Code without being asked, by reading `spec/loop-detection.md` and `spec/token-budget.md` for tone. Elden accepted it. This kind of autonomy — extending the new artifact with conventions from neighboring artifacts — is desirable and should be encouraged. Future spec-writing prompts can be shorter (looser outline, more reference files to read) on the assumption that Claude Code will pattern-match.

- **Sub-task decomposition with explicit Elden checkpoints scales better than monolithic steps.** Phase 8.1.A was scoped as a single step in CHECKPOINT_05 §7A. In execution it became 4 sub-tasks with Elden checkpoints between each. The decomposition was emergent — driven by the size of the work, not pre-planned. Future Phase 8.1.B/C/D estimates should assume similar decomposition: a "single step" in §7B usually means 3–5 sub-tasks at execution time.

- **Validation tasks and measurement tasks are different categories and must be chosen separately.** Task 2 (dc28cf18) was used for 8.1.A validation because it was cheap and quick (Finding 10's "ceiling task" status was unknown until validation). 8.1.B's mini-experiment cannot use the same task because ceiling tasks produce no measurement signal. Validation needs cheap, quick, deterministic tasks; measurement needs tasks where the metric being measured can actually vary. Conflating the two leads to running costly experiments on tasks that cannot answer the question.

---

## 9. Safety notes

Inherited from CHECKPOINT_05 §9. Unchanged unless noted.

NEVER: touch .env.example; echo .env contents; re-invoke a running benchmark.py process; commit results/ or cache/; treat 1 datapoint as pattern evidence; accept bash_tool background detach for benchmark runs without explicit wrapper.

ALWAYS: read the current checkpoint fully before acting; use explicit timeout 1800 shell wrapper for any long-running command; capture stdout + copy results.tsv between tasks; preserve data from self-terminating tasks even if they exceed wall-clock limits; be honest about what is observed vs hypothesised.

Inherited from Session 5:

- Before designing any pipeline change, observe what the current pipeline actually produces.
- entropy is a primary observation tool, not optional infrastructure. Do not propose removing measurement to save cost.
- detect_loop is structurally dead when H_raw = 0 (CHECKPOINT_05 Finding 6). Do not rely on detect_loop output for any decision until 8.1.C lands.
- Per-step traces are not persisted in the current pipeline. **(Updated by this session: per-step traces ARE now persisted as of commit 0556d8f. The constraint is lifted. Trace sidecars at `results/trace_<task_id>_<condition>.jsonl` are the canonical per-step record. See spec/trace.md.)**
- Cost is quadratic in step count. All main-18 budget estimates remain unreliable until Phase 8.1.D lands.
- The Phase 8.1 §7B table is mandatory cross-session memory. A session that does Phase 8.1 work without updating §7B has left the next session blind.
- HEAD verification by SHA is brittle. Use invariants (file diffs against a known code baseline, CACHE_VERSION, deleted-symbol grep) instead.

New in Session 6:

- **Workflow rule (load-bearing, not optional): Claude presents decisions in metaphor language; raw exposure happens only at decision branches expensive to undo.** Established mid-session 6 by Elden. The rule has two halves and both are required. Half one: Claude compresses technical detail into natural-language summaries before presenting choices, because Elden being forced to mentally translate jargon is the bottleneck the running-river philosophy explicitly forbids. Half two: Claude judges which decisions are expensive to undo (cache invalidation, schema change, file commit, contract establishment) and exposes raw at those moments, because pure metaphor delegation lets Claude's narrative errors slip past without Elden's detection — the failure mode is not "Elden saw too much raw" but "Elden trusted a metaphor about a contract." This rule is the response to two specific failure modes already observed: Session 5's token-direction misread (caught by raw token numbers, would have been missed under pure metaphor) and Session 6's inverse() prior-knowledge contradiction (caught by Elden noticing a concrete example contradicting an absolute claim, which only worked because the example had been kept in the conversation rather than compressed away).

- **Spec/document commits require a pause-before-commit step. Code commits do not.** Code commits with small diffs and passing verification can auto-commit. Spec, docs, README, checkpoint, or any other contract-establishing artifact MUST be raw-reviewed by Elden before commit. The asymmetry is intentional: code is verifiable by automated tests and can be reverted cheaply; contracts are verifiable only by reading the prose, and once a contract is in main other artifacts start cross-referencing it. This rule was learned from sub-task 4's commit-before-review ordering error (decisive moment 6). Future Claude Code prompts that touch spec/, docs/, README.md, or any contract file must explicitly include "Stop after writing, wait for OK, then commit" as a mandatory step. Commit auto-progression is reserved for code-only changes.

- **inverse() mobilizes the LLM's prior knowledge by design (Interpretation A, Session 6).** Only `prompt_target` has a "do not add requirements not implied by the request" guard. `prompt_invert` and `prompt_compose` have no such guard, and the mashed potato Condition B head demonstrates the inverse model injecting arithmetic procedural knowledge that was not in the raw prompt. This is consistent with the Wolpert & Kawato (1998) inverse-model framework where the inverse model operates on top of a learned forward model — the LLM's prior knowledge is the forward model. **Hypothesis (not yet verified):** Task 5's confident-wrong-answer failure mode may be caused by inverse() mobilizing incorrect prior knowledge during backward chaining. **Verification path:** read the Task 5 inverse cache entry from Session 5's pilot run (`cache/inverse/`), which contains the target / inversion / improved_prompt fields, at zero LLM cost. This verification can be done in any future session as a side-check; it does not depend on Phase 8.1.B/C/D landing.

---

## 10. New session bootstrap block

To continue work, open a new Claude conversation and paste the following prompt followed by the full contents of this file:

This is a continuation of the prompt-training project. Load the checkpoint below in full before acting. Pay special attention to §1 (framing — Phase 8.1.A is complete; Phase 8.1.A.Plus begins; the workflow itself evolved during Session 6 and is now load-bearing per §9), §3 (Findings 5–11, especially Finding 10 on ceiling vs floor tasks and Finding 11 on the cost-frontier hypothesis), §3.5 (decisive moments — especially the workflow evolution and the inverse() prior-knowledge clarification), §7A (your single immediate task), §7B (the Phase 8.1 5-step tracker — this table is mandatory cross-session memory), §8 (operational lessons), and §9 (safety notes — three new ones from Session 6 including the workflow rule).

Your job: execute §7A — Phase 8.1 Step A.Plus (cost-frontier validation: planner=sonnet / executor=haiku). This is a newly inserted side-gate phase (see §3 Finding 11) that validates whether inverse-generated procedural prompts let a weaker executor match a stronger one on floor tasks. Do not attempt Steps B, C, or D in this session.

Important: Step A.Plus is a DESIGN session before it is a code session. Do not start by writing Claude Code prompts to modify `benchmark.py`. Start by walking through the design decisions with Elden:
- Which floor tasks should the experiment measure? (Per §3 Finding 10: floor tasks like Task 5 are canonical. Avoid ceiling tasks like Task 2. Propose 2-3 task set including Task 5 and 1-2 intermediate tasks from L2.)
- Which models to compare? Baseline is A = raw + sonnet (Session 5 data can be reused from `results/pilot_8_0_*.tsv`). Target is B' = inverse[sonnet] + haiku. Inverse is cached (Session 5 cache), so inverse LLM calls should cost zero. Only executor calls are new.
- What is the success criterion? (e.g. "verifier_passed parity at X% cost reduction" — propose thresholds for positive / partial / negative outcomes. Partial is interesting too: "haiku matches sonnet on L1/L2, falls off on L3" would be a publishable finding.)
- What is the budget? Claude Code Bucket B diagnostic estimated $10-15 total. Propose a per-task hard abort ($5 recommended) before the experiment runs.
- Will measurement be done under entropy? The entropy measurement layer remains broken (Finding 7 flat-zero). 8.1.A.Plus's main signals are `verifier_passed` and `total_tokens` — both scalar columns in results.tsv, both unaffected by the entropy degradation. Entropy values will still be recorded but may collapse to zero; treat them as advisory, not decisive.
- Will the changes require a CACHE_VERSION bump? No — `model_for_execution` is outside the inverse cache key, per Claude Code diagnostic. Cache is fully reusable.
- Which `measure_semantic_entropy` policy? There is an open question (deferred from the diagnostic): when the executor model differs from the inverse model, which model should `measure_semantic_entropy` use for the per-step H_n measurements? Options: (α) always inverse model (sonnet) for measurement consistency; (β) always executor model (haiku) for realism; (γ) both (cross-product). Claude's provisional recommendation is (α) — measurement consistency is a controlled variable for cost-frontier comparison. Discuss with Elden.

Only after these design decisions are settled with Elden should you begin proposing Claude Code prompts. The first code action will be adding the `--executor-model` CLI arg and threading it to `run_react_loop()` (estimated < 15 lines per Bucket B diagnostic). Inverse stays on `--model`. Then run the mini-experiment with cache reuse to keep cost near the $10-15 estimate.

Before executing:
1. Acknowledge the checkpoint.
2. Read §7B and confirm you understand that 8.1.A is DONE (commits 0556d8f / f5e624b / 27480c0), 8.1.A.Plus is now ACTIVE, and that you must update the table at session close with whatever 8.1.A.Plus's outcome is. The table is mandatory cross-session memory.
3. Read §9 safety notes carefully — especially the three new ones from Session 6. The workflow rule (Elden decides from metaphor-language summaries; raw exposure only at decision branches) is now load-bearing. Apply it from your first turn, not just when you remember.
4. Verify code state by invariants (not SHA): grep for absence of `summarize_to_head`/`summarize_to_body`/`trim_to_tail` in `inverse.py` and `benchmark.py`, confirm `CACHE_VERSION` reads `v2.9.0-001` in benchmark.py, run `git diff b8daf4d HEAD -- inverse.py` (must be empty — `inverse.py` has not changed since Phase 8.0 landed). `benchmark.py` HAS changed (Phase 8.1.A added the trace sidecar layer); verify the trace functions exist with `grep -n '_write_trace_sidecar_meta\|_append_trace_step' benchmark.py`.
5. Begin the design conversation with Elden. Do NOT propose code changes in your first turn. Ask the design questions above, in metaphor language, one branch at a time, with raw exposure only when a decision is expensive to undo (executor model choice is one such decision; task selection is another).

Working method: I (Elden) do not let you write code directly. You produce Claude Code prompts that I paste into a separate Claude Code session. I relay outputs back to you. You review, decide, and produce the next prompt. As of Session 6, the rule is also: you summarize technical decisions into metaphor language and present me with binary or trinary choices, not raw technical details. Raw exposure happens when a decision is expensive to undo (cache invalidation, schema change, contract change). You judge which decisions qualify.

When producing CHECKPOINT_07 at the close of this session:
- Follow the template inherited from CHECKPOINT_03 §13.
- Inherit §9 Safety notes with any additions.
- Update §7B: flip 8.1.A.Plus from ACTIVE to DONE with the commit SHA(s), flip 8.1.B to ACTIVE.
- Do NOT remove or shorten the §7B table. Copy all rows forward.
- If you found a reason to re-order or re-scope Phase 8.1 steps (e.g. mini-experiment results suggest a different ordering), explain the reason in §1 framing of CHECKPOINT_07.

---

[PASTE FULL CONTENTS OF CHECKPOINT_06_phase_8_1_a_complete.md HERE]

---

## 11. End of CHECKPOINT_06

Session 6 closes after this file is committed. Three code/spec commits landed in main this session (0556d8f, f5e624b, 27480c0). Phase 8.1.A is complete; the §7B table reflects this. Phase 8.1.A.Plus is now ACTIVE and is the next session's single immediate task (cost-frontier validation inserted as Session 6 post-close addition; see §3 Finding 11). The bootstrap block in §10 contains the prompt to load CHECKPOINT_06 in the next session.

The workflow itself evolved during Session 6 and the evolution is encoded in §9 as load-bearing. Future sessions inherit the rule: Claude presents decisions in metaphor language with raw exposure only at decision branches expensive to undo, and spec/document commits require a pause-before-commit step. These are not optional.
