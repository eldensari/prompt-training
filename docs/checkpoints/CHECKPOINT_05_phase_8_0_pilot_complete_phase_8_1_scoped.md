# CHECKPOINT_05 — Phase 8.0 pilot complete, Phase 8.1 scoped (§1–§5)
Project: prompt-training
Repository: https://github.com/eldensari/prompt-training
Local: C:/Users/433/Documents/prompt-training
Checkpoint date: 2026-04-11 (Session 5 close)
Preceding checkpoint: docs/checkpoints/CHECKPOINT_04_phase_8_0_pipeline_restructure.md
HEAD at checkpoint: cc6a573 (spec: rewrite token-budget.md for Phase 8.0) — code unchanged this session, only data and diagnostics produced

## 1. Framing
This was a execution + diagnostic + scoping session. Three phases, in order:

Phase 8.0 pilot re-execution (5 of 6 tasks). The same pilot tasks from CHECKPOINT_03 were re-run under the new full-prompt-Head pipeline. Two recoveries (Tasks 2, 4), two no-changes (Tasks 1, 3), one new failure mode (Task 5). The §7 Step 8.0.C decision gate's first-row condition ("B-new improves on 2+ tasks") was met.
Task 5 trajectory diagnostic. A $21 single-task spike triggered the per-task hard-abort and stopped the batch before Task 6. Rather than running Task 6 next (option A) or stopping cold (option B), Elden chose option C: read Task 5's trajectory before deciding. The diagnostic surfaced three structural problems in Phase 8.0's auxiliary infrastructure that the pilot's correctness-only view had hidden.
Phase 8.1 scoping. The three problems plus a fourth (cost model) form a 4-step roadmap. Elden surfaced the dependency question, which revealed that Phase 8.1 Step 3 (entropy measurement layer) is the hub — Steps 1 and 4 depend on it. Option A ordering was chosen: 2 → 3 → 1 → 4. The dependency itself made it necessary to design a CHECKPOINT mechanism that survives multi-step roadmaps without losing dependency information between sessions.

The session did not write any code. CACHE_VERSION is unchanged. The HEAD sha (cc6a573) is the same as the start-of-session HEAD because all of this session's outputs were data files (results/pilot_8_0_.tsv, results/pilot_8_0_.log, results/entropy_steps.tsv) and a checkpoint document.
Single most important sentence:

Phase 8.0 confirmed its core hypothesis (bottleneck removal → recovery on tasks where inverse-model output was rich), but did so while quietly breaking three pieces of auxiliary infrastructure: detect_loop, per-step trace observability, and the cost model's step-count assumption. Phase 8.1 is a 4-step multi-session roadmap to fix these without re-introducing the bottleneck. Step 2 (trace persistence) is the first action; Step 3 (entropy measurement layer) is the dependency hub.


## 2. Git state

HEAD: cc6a573 — spec: rewrite token-budget.md for Phase 8.0 (unchanged from session start)
Branch: main
Working tree: clean except for results/ artifacts (gitignored) and this checkpoint
Code files (inverse.py, benchmark.py): byte-identical to b8daf4d. No code changes this session. Verified via git diff b8daf4d HEAD -- inverse.py benchmark.py (empty) at the start of every Claude Code task in this session.

Recent commits (unchanged from CHECKPOINT_04 §2):
cc6a573 spec: rewrite token-budget.md for Phase 8.0
ac9260d docs: add CHECKPOINT_04
b8daf4d Phase 8.0: remove summarize/trim bottleneck
348b2e7 docs: add §3.5 decisive moments and §13 template to CHECKPOINT_03
8745575 docs: add CHECKPOINT_03
Files produced this session (all gitignored):
results/pilot_8_0_8e867cd7.tsv + .log   (Task 1, Mercedes Sosa, L1)
results/pilot_8_0_dc28cf18.tsv + .log   (Task 2, mashed potatoes, L1)
results/pilot_8_0_17b5a6a3.tsv + .log   (Task 3, invasive species, L2)
results/pilot_8_0_3627a8be.tsv + .log   (Task 4, mollusk shell, L2)
results/pilot_8_0_676e5e31.tsv + .log   (Task 5, 1959 standards, L3)
results/entropy_steps.tsv                (60 rows: 1 header + 59 per-step measurements across 5 tasks)
Task 6 (e961a717, Asian monarchies, L3) was NOT run. Per-task hard abort fired on Task 5.

## 3. Findings from this session
Finding 5 — Phase 8.0 core hypothesis confirmed (correctness)
5-task correctness matrix:
TaskLevelPhase 8.0 APhase 8.0 BSession 2 ASession 2 BPattern1 Mercedes SosaL1✓✓✓✓no change2 mashed potatoesL1✓✓FF⭐ both recovered3 invasive speciesL2✓✓✓✓no change4 mollusk shellL2✓✓✓F (max_steps)⭐ B recovered5 1959 standardsL3FFF (max_steps)F (error)failure mode shift6 Asian monarchiesL3————NOT RUN
§7 Step 8.0.C decision gate row 1 ("B-new improves on 2+ tasks") met (Tasks 2 and 4). Phase 8.0's bottleneck-removal hypothesis is confirmed by this data.
A subtlety surfaced in Task 2: A also recovered, not just B. CHECKPOINT_03 Finding 2 attributed the failure to summarize_to_head destroying improved_prompt structure, which predicts only B-side recovery. Task 2's A-side recovery means full-prompt Head helped both conditions, possibly because the old 80-token Head was also damaging raw prompts. Task 4 has the cleanest inverse-model causal pattern (B recovery without A change), so the original Finding 2 holds for at least one task. Task 2's A recovery is a secondary finding worth holding.
Finding 6 — Phase 8.0 broke detect_loop structurally
Re-read of detect_loop in inverse.py:563–601:
pythonthreshold = alpha * H_raw                  # alpha=0.3
...
tol = 0.05 * max(H_raw, 1e-9)
flattened = all(abs(d2) <= tol for d2 in second_diffs)
H_now = recent[-1]
high = H_now > threshold                   # strict >
if flattened and high:
    return {"is_loop": True, ...}
When H_raw = 0:

threshold = 0
tol = 5e-11 (the max(H_raw, 1e-9) floor protects against /0 but doesn't restore usable tolerance)
H_now > threshold becomes 0 > 0 = False (strict >)
The function structurally cannot return is_loop=True

CHECKPOINT_04 §5 promised that detect_loop's "ratios and derivatives" structure was compatible with the trend-reading frame. That promise silently assumed H_raw > 0. After Phase 8.0, H_raw = 0 is the common case — confirmed by 4 of 5 pilot tasks producing H_raw = 0 in both conditions. detect_loop is dead on most tasks now.
This is a real bug, not a design choice. It's Phase 8.1 Step 1 work.
Finding 7 — Entropy measurement resolution is N_SAMPLES-bound
69 entropy measurements across 5 tasks. 2 non-zero. Both equal to exactly 0.7219280948873623 — the Shannon entropy of a 4-1 split among 5 samples. With N_SAMPLES=5, the discrete entropy values possible are {0, 0.72, 0.97, 1.37, 1.92, 2.32}, and only the first two were observed.
This is not a bug in semantic_cluster. It is the resolution limit of N=5 sampling. For GAIA L1/L2 questions where the agent's "what action will I take next?" response is high-confidence, 5 samples almost always cluster into 1 group. The clusterer is doing what it's supposed to do; the question is whether N=5 is the right input for the trend-reading frame, or whether the measurement layer needs to be redesigned (different N, different metric, different question prompt).
The non-zero values landed in interesting positions: Task 3 A's pre-final-answer step (4-1 split when the agent had to decide whether to commit or keep searching), and Task 4 B's H_improved entrance (the inverse-model widened the next-action distribution exactly where it was supposed to). When the resolution permits a measurement at all, the measurement is meaningful. The problem is that the resolution rarely permits one.
This is Phase 8.1 Step 3 work and is the dependency hub of Phase 8.1.
Finding 8 — Per-step traces are not persisted; observability dead-end
Task 5's diagnostic was forced to reconstruct the trajectory from the Tavily cache (which stores query strings but no condition labels). The 28 cached Tavily calls were chronologically ordered but the A/B split point had to be inferred from a 3:45 timing gap. 4 cache-hit calls were invisible (hits don't write new files). The Thought texts were never recoverable.
results/results.tsv has 10 columns, none of them per-step. step_history is a Python list inside run_react_loop and is discarded when the function returns. The detailed log file is cost-summary only.
For tasks where the entropy curve is flat-zero (most tasks, per Finding 7), the entropy log carries no information. Without traces in the TSV, the diagnostic surface disappears entirely. The trend-reading frame cannot function as a diagnostic tool without traces. This is Phase 8.1 Step 2 work and the next session's first action.
Finding 9 — Cost is quadratic in step count, not linear
Per-task costs:

Task 1 (3 steps each): $3.69
Task 2 (1 step each): $0.18
Task 3 (3+4 steps): $0.62
Task 4 (4+6 steps): $0.85
Task 5 (15+19 steps): $21.47

Task 5 alone is 80% of batch cost. The driver is structural: step_history accumulates without compression, and entropy is measured at every step on head + step_history. Step n's measurement input contains step_history of length n-1. The total measurement cost across N steps scales as O(N²) per condition because every step pays the cumulative-history input cost.
CHECKPOINT_04 §6 estimated $10–20 for the 6-task pilot using a per-task average. The actual 5-task cost was $26.81 because the average hides the quadratic tail. Hard tasks (15+ steps) explode.
This is Phase 8.1 Step 4 work — a planning/budget framework update, not a code change.

## 3.5. Decisive moments in this session
Eight turns initiated by Elden altered the trajectory.

Acceptance of HEAD = cc6a573 instead of literal b8daf4d. Claude Code's strict HEAD verification correctly caught a SHA mismatch. Elden re-framed the verification from "is HEAD this SHA" to "is the Phase 8.0 code in place" and approved a verification-by-invariants check (CACHE_VERSION + grep for deleted symbols + git diff to b8daf4d). Without this, the entire pilot would have stalled at task 1 verification.
Token direction correction in Task 2 analysis. Claude misread Task 2's token numbers (claimed B used fewer tokens than A; actually B used more) and built a wrong narrative on top of the misread. Elden caught the direction error directly. Correction surfaced a deeper finding: Task 2's A also recovered, not just B, which complicates the original CHECKPOINT_03 Finding 2 attribution to summary destruction alone.
Token comparison item (j) added inline starting at Task 3. Elden chose to embed Session 2 vs Phase 8.0 token comparison in every per-task report rather than collecting it at batch end. This made the cost-tradeoff pattern visible by Task 3 instead of Task 6 and was what surfaced Finding 9 mid-batch.
Budget ceiling raised $25 → $100 before tasks 4-5-6 batch. Elden lifted the cumulative cap based on confidence in the per-task hard-abort. This allowed the batch to be authorized with safety margin without artificial pressure to short-circuit.
Per-task $10 hard abort fired on Task 5 ($21). The Claude Code instance stopped the batch after Task 5 per protocol, instead of continuing to Task 6. This was the right operational call and prevented a second cost spike. The hard-abort at $10/task is now established as the right granularity for this kind of pilot.
Choice of option C over options A and B at Task 5 boundary. When the batch halted, Elden chose to read Task 5's trajectory diagnostic before deciding whether to run Task 6 ($0 read-only). This was an explicit "observation before design" choice and surfaced Findings 6, 7, 8 — three structural problems that the pilot's correctness-only view had hidden. Without this turn, Phase 8.1 would have been scoped much more narrowly.
Dependency question that revealed Step 3 as hub. Elden asked which of the 4 Phase 8.1 tasks affects the others. Claude's first-pass ordering (4 → 1 → 2 → 3) ignored that detect_loop's threshold formula depends on the entropy distribution shape, which depends on the measurement layer. The dependency matrix exercise produced Option A (2 → 3 → 1 → 4) and the recognition that Step 3 is the hub. Without this question the next session would have begun Step 1 first and re-done it after Step 3.
Decision to encode Phase 8.1 as a 4-step tracker in §7B with mandatory cross-session updating. Elden surfaced the meta-question: "how do I make sure the next session does Step 1 first AND doesn't forget Steps 2-4?" This led to the §7A/§7B split, the table-as-memory mechanism, and the mandatory state-update obligation in §10. This is a new pattern in the CHECKPOINT system that did not exist in CHECKPOINT_03 or 04.

Hypothesis amplitude during the session
Five reframings:

Initial: "Run all 6 pilot tasks, evaluate Phase 8.0 by correctness."
After Task 2: "B's improvement is faster (token-cheaper)" — this was wrong (token direction misread).
After Task 2 correction: "Both A and B recovered. Phase 8.0 helped both conditions, not just B. The CHECKPOINT_03 Finding 2 'summary destroyed structure' attribution is partial."
After Task 5 abort: "Phase 8.0 has a quadratic-cost failure mode on hard tasks. Failure shape changed from timeout to confident-wrong-answer."
After Task 5 diagnostic: "Phase 8.0 broke three things: detect_loop, observability, cost model. These three plus the entropy resolution problem form Phase 8.1. Step 3 (entropy) is the dependency hub. Step 2 (trace) is the first action."

Reframing 5 is what §7 of this checkpoint encodes.

## 4. What changed this session
No code changes. No commits to inverse.py or benchmark.py. CACHE_VERSION is still v2.9.0-001. All Phase 8.0 invariants from CHECKPOINT_04 §4 remain intact.
Data produced: 5 pilot task TSV snapshots, 5 log files, 1 entropy_steps.tsv with 59 per-step measurements, 1 inverse cache entry for Task 5 (used in trajectory reconstruction). All gitignored.
Documents produced: This checkpoint (CHECKPOINT_05).
One thing was diagnosed but not changed: detect_loop's H_raw=0 dead state was confirmed in Finding 6, but the code is unchanged. The fix is Phase 8.1 Step 1 work, deferred until Step 3 settles the entropy distribution shape that the new threshold rule will need to be calibrated against.

## 5. spec/token-budget.md status
This is now consistent with code. CHECKPOINT_04 §5 obligation was discharged in commit cc6a573 between sessions. The spec and the b8daf4d code are aligned.
CHECKPOINT_05 introduces no new spec/code inconsistency. Phase 8.1 will introduce changes that will need spec updates as they land — those updates should accompany each Phase 8.1 step's code commit, not lag behind.

CHECKPOINT_05 — §6–§11

## 6. Budget state

Through CHECKPOINT_03: $15.47
Session 4 (CHECKPOINT_04): $0
Session 5 (this session): $26.81

Task 1: $3.69 / Task 2: $0.18 / Task 3: $0.62 / Task 4: $0.85 / Task 5: $21.47
Task 5 alone = 80% of session cost (quadratic step-cost tail)


Cumulative project total: $42.28
Phase 8.1 Step 2 (trace persistence) estimate: ~$1–3 (1 task validation re-run on a small task)
Phase 8.1 Step 3 (entropy mini-experiment) estimate: ~$5–15 (depends on N_SAMPLES sweep design)
Main 18 estimate: deferred until Phase 8.1 Step 4 (cost model rebuild) lands


## 7. Next state transition
### §7A — Immediate next session work (single step)
The next session executes Phase 8.1 Step A only. Do not attempt other steps. When 8.1.A is complete, write CHECKPOINT_06 and stop.
Phase 8.1 Step A — Per-step trace persistence
Goal: every benchmark.py run records the per-step Thought / Action / Observation sequence to disk in a form that survives function return.
Completion criteria:

Trace data is written somewhere readable after the run (TSV column or sidecar JSON file — design choice deferred to next session).
Trace contains, per step: step number, thought text, action name + args, observation text, the entropy value at that step.
One validation re-run on a cheap task (Task 2 dc28cf18 — was $0.18, 1 step each condition) confirms trace is written and readable.
spec/ updated to document the trace persistence layer.
Code commit + checkpoint update.

What is not in scope for 8.1.A:

detect_loop fix (that's 8.1.C, depends on 8.1.B)
entropy measurement changes (that's 8.1.B)
cost model rewrite (that's 8.1.D)

Design questions deferred to next session:

TSV column (step_history_json) vs sidecar file (results/trace_<task_id>_<condition>.json)?
JSON vs JSONL vs flat TSV inside the trace?
Truncation policy for very long observation texts?

These are intentionally not specified here. The next session's first turn should make these calls and record the rationale in CHECKPOINT_06 §3.5.
### §7B — Phase 8.1 roadmap tracker (multi-session)
This table is the single source of truth for Phase 8.1 progress. Every session that touches Phase 8.1 must update this table when closing the session and copy it forward to the next checkpoint. Do not delete rows. Do not rewrite columns. Status transitions only: TODO → ACTIVE → DONE (with commit SHA).
Step작업의존성상태완료 조건결과/SHA8.1.APer-step trace persistencenoneACTIVE (next session)Trace written + readable + 1 task validation + spec update—8.1.BEntropy measurement layer redesign (mini-experiment: N_SAMPLES sweep, optionally MEASUREMENT_QUESTION variants)8.1.A complete (need traces to read mini-experiment results)TODODecision on N_SAMPLES + question prompt + (optional) metric change, documented with experimental data—8.1.Cdetect_loop H_raw=0 fallback8.1.B complete (new entropy distribution shape determines threshold rule)TODOFallback rule implemented, retroactive validation against Task 5 trace, spec update—8.1.DCost model rebuild8.1.C complete (cost depends on final measurement layer + loop detector)TODOO(N²) cost formula documented, main-18 budget cap and per-task abort thresholds set—
Rationale for the order (do not re-order without documenting in §1 of a future checkpoint): Step 3 (8.1.B, entropy) is the dependency hub — its output shape determines the threshold formula in 8.1.C and the per-step measurement cost in 8.1.D. Step 2 (8.1.A, trace) is the only fully independent step and is required for 8.1.B's mini-experiment to be readable. Therefore the dependency-respecting order is 8.1.A → 8.1.B → 8.1.C → 8.1.D, which corresponds to "Option A" in this session's discussion.
Mandatory session-close obligation: Whichever session completes a step must (a) flip its status to DONE with the commit SHA, (b) flip the next step's status to ACTIVE, and (c) copy the entire table forward to the next checkpoint without removing rows or columns. Failing to update this table is a framing violation — it deletes the cross-session memory of which steps remain.
Re-scoping is allowed but must be documented. If a future session discovers that a step needs to be split, removed, or reordered, the checkpoint that does so must explain why in its §1 framing. The table is a living document, not a fixed contract.
### §7C — Decision deferred to after Phase 8.1
§7 Step 8.0.C decision gate from CHECKPOINT_04 was partially evaluated in Findings 5–9 but the final main-18 / no-main-18 decision is deferred until Phase 8.1 lands. The current state is "Phase 8.0 core hypothesis confirmed, but auxiliary infrastructure must be repaired before scaling to 18 tasks." Task 6 (e961a717) is also deferred — it will naturally re-run as part of main 18 once Phase 8.1 closes.

## 8. Operational lessons from Session 5 (carry forward)
Inherited from CHECKPOINT_04 §8. Additions from this session:

HEAD verification should reference invariants, not SHAs. Checkpoint bootstrap blocks that pin a SHA will break when legitimate non-code commits land between checkpoint write and checkpoint load. Use grep for deleted symbols, CACHE_VERSION reads, and git diff <code-baseline-sha> HEAD -- <code-files> (must be empty) instead. SHA pinning is fine as a signal of intent but should never be the gate.
Per-task hard-abort thresholds are operationally correct, not over-cautious. The $10/task limit fired exactly once and prevented a $21 single-task spike from cascading. A $50 batch limit alone would not have caught it because cumulative was still under $30 when Task 5 finished. Per-task limits catch tail events; cumulative limits catch creep. Keep both.
Token-direction errors compound. A single misread of "A used X tokens, B used Y tokens" propagated into a wrong narrative ("B improved by being more efficient") that lasted across two turns until Elden caught it. Numerical claims about A vs B should be double-checked against the source row before being woven into a hypothesis. When in doubt, paste the raw row.
"Observation before design" applies recursively. It already meant "observe what the system does before designing changes." This session added: "observe the trajectory of a failed task before deciding whether to run more failed tasks." Task 5's diagnostic (option C) was free and surfaced 3 structural findings; running Task 6 would have cost $20+ and yielded one more datapoint of the same kind. Reading-before-running is a default mode, not just a pre-design step.
Multi-step roadmaps need a tracker, not a sequence. When the work after a checkpoint is more than one step and the steps have dependencies, listing them as "next steps" in a §7 paragraph guarantees that downstream steps get forgotten. The §7B table pattern in this checkpoint is the response. Future multi-step phases should use the same pattern.
The dependency hub matters more than the visible bug. This session's first instinct was to fix detect_loop first (the most clearly broken thing). Elden's dependency question revealed that detect_loop's fix needs the entropy layer's new distribution shape. Fixing the visible bug first would have meant fixing it twice. When ordering work, find the hub before starting at the leaf.


## 9. Safety notes
Inherited from CHECKPOINT_04 §9. Unchanged unless noted.
NEVER: touch .env.example; echo .env contents; re-invoke a running benchmark.py process; commit results/ or cache/; treat 1 datapoint as pattern evidence; accept bash_tool background detach for benchmark runs without explicit wrapper.
ALWAYS: read the current checkpoint fully before acting; use explicit timeout 1800 shell wrapper for any long-running command; capture stdout + copy results.tsv between tasks; preserve data from self-terminating tasks even if they exceed wall-clock limits; be honest about what is observed vs hypothesised.
Inherited from Session 4:

Before designing any pipeline change, observe what the current pipeline actually produces.
entropy is a primary observation tool, not optional infrastructure. Do not propose removing measurement to save cost.

New in Session 5:

detect_loop is structurally dead when H_raw = 0. CHECKPOINT_04 §5 promised that detect_loop's ratio-and-derivative shape was compatible with the trend-reading frame. That promise silently assumed H_raw > 0. After Phase 8.0, H_raw = 0 is the common case (4 of 5 pilot tasks). detect_loop has not fired on any task this session and structurally cannot fire on H_raw=0 tasks. Until Phase 8.1.C lands, do not rely on detect_loop output for any decision. Treat its is_loop=False as unknown, not as not a loop.
Per-step traces are not persisted in the current pipeline. When entropy curves are flat-zero (the common case post-Phase-8.0), trace data is the only diagnostic surface, and it does not exist. Until Phase 8.1.A lands, task failures cannot be properly diagnosed, only inferred from cache artifacts. Do not promise diagnostic depth that the pipeline does not currently support.
Cost is quadratic in step count. Per-task budget estimates based on average cost will fail on hard tasks. When estimating any batch that includes L3 tasks, use a per-task hard abort ($10 worked this session) and assume cost variance is high. Until Phase 8.1.D lands, all main-18 budget estimates should be treated as unreliable.
The Phase 8.1 §7B table is mandatory cross-session memory. A session that does Phase 8.1 work without updating §7B has left the next session blind to which steps remain. This is a framing violation, not a minor oversight.
HEAD verification by SHA is brittle. Use invariants (file diffs against a known code baseline, CACHE_VERSION, deleted-symbol grep) instead. SHA pinning is a hint, not a gate.


## 10. New session bootstrap block
To continue work, open a new Claude conversation and paste the following prompt followed by the full contents of this file:
This is a continuation of the prompt-training project. Load the checkpoint below in full before acting. Pay special attention to §1 (framing — Phase 8.1 is a 4-step multi-session roadmap, not a single next step), §3 (Findings 5–9), §3.5 (decisive moments — especially the dependency-hub recognition), §7A (your single immediate task), §7B (the Phase 8.1 4-step tracker — this table is mandatory cross-session memory), §8 (operational lessons), and §9 (safety notes — three new ones from Session 5).

Your job: execute §7A — Phase 8.1 Step A (per-step trace persistence). This is the first of 4 steps in Phase 8.1. Do not attempt Steps B, C, or D in this session. They depend on Step A's output and on each other.

Before executing: 
1. Acknowledge the checkpoint. 
2. Read §7B and confirm you understand that it is the cross-session memory tracker for Phase 8.1, that you must update it at session close, and that you must copy it forward to CHECKPOINT_06 without removing any rows.
3. Make and document the design choices for Step A that §7A intentionally deferred: TSV column vs sidecar file, JSON format choice, truncation policy. Record your rationale — these go into CHECKPOINT_06 §3.5.
4. Verify code state by invariants (not SHA): grep for absence of summarize_to_head/summarize_to_body/trim_to_tail in inverse.py and benchmark.py, confirm CACHE_VERSION reads v2.9.0-001, run `git diff b8daf4d HEAD -- inverse.py benchmark.py` (must be empty). Do NOT pin to a literal HEAD SHA.
5. Propose the Claude Code prompt for the first sub-task of Step A (likely: read benchmark.py's run_react_loop to understand current step_history handling, then propose the schema). Wait for my OK.

Working method: I (Elden) do not let you write code directly. You produce Claude Code prompts that I paste into a separate Claude Code session. I relay outputs back to you. You review, decide, and produce the next prompt.

When producing CHECKPOINT_06 at the close of this session:
- Follow the template inherited from CHECKPOINT_03 §13.
- Inherit §9 Safety notes with any additions.
- Update §7B: flip 8.1.A from ACTIVE to DONE with the commit SHA, flip 8.1.B to ACTIVE.
- Do NOT remove or shorten the §7B table. Copy all rows forward.
- If you found a reason to re-order or re-scope Phase 8.1 steps, explain the reason in §1 framing of CHECKPOINT_06.

---

[PASTE FULL CONTENTS OF CHECKPOINT_05_phase_8_0_pilot_complete_phase_8_1_scoped.md HERE]

## 11. End of CHECKPOINT_05
Session 5 closes after this file is committed. No code changes this session. Phase 8.0 pilot is complete on 5 of 6 tasks; Task 6 deferred to main 18 re-run. Phase 8.1 is a 4-step multi-session roadmap tracked in §7B with mandatory cross-session updating. The next session begins with Phase 8.1 Step A (trace persistence) per the bootstrap block above.
