# CHECKPOINT_01 — Session 1 Close (v2, exploration framing)

**Project**: prompt-training
**Repository**: https://github.com/eldensari/prompt-training
**Local**: C:/Users/433/Documents/prompt-training
**Session 1 close date**: 2026-04-09
**HEAD at close**: `3ec0738` (docs commit) → will become new hash after this update commit

---

## 1. Critical reframing (read this first)

**The original Phase 7 plan was: 3 runs × 40 tasks × N=10, treated as "publishable result".**

**Session 1 ended this framing.** The new framing is:

> **Phase 7 is exploration, not publishable testing.** The goal is to understand whether the inverse model works as hypothesized, and what patterns emerge across difficulty levels. **Publishable results come later, after the forward model is added.** Right now we want to see what's actually happening, not prove anything statistically.

This reframing changes everything that follows.

---

## 2. Git state at Session 1 close

- HEAD: `3ec0738` — docs: add Phase 6b review and session 1 checkpoint (will update with this v2)
- Branch: main, synced with origin/main
- 19 commits total
- Working tree clean

Recent commits:
```
3ec0738 docs: add Phase 6b review and session 1 checkpoint
c5b4267 Phase 6c-prep: Tavily /usage shape fix + dotenv auto-loading
21a1b15 Phase 6a-prep: pyproject.toml py-modules — fix flat-layout discovery
```

---

## 3. Repo state

Standard structure plus:
- `docs/checkpoints/CHECKPOINT_01.md` (this file)
- `docs/reviews/PHASE_6B_REVIEW.md` (Phase 6b detailed review)

**Python env**: Python 3.13.12, anthropic 0.92.0, openai 2.31.0, datasets 4.8.4, numpy 2.4.4, sklearn 1.8.0, python-dotenv 1.2.2.

**API keys** in `.env` (gitignored): ANTHROPIC, TOGETHER, HF, TAVILY all valid.

---

## 4. Completed work in Session 1

### 4.1 Phase 6a — environment validation (passed, 9/9 checks)

GAIA Level 1 loads 53 → 42 → **40 text-only tasks**. All 4 API keys valid. All 27 imports resolve. Pricing fresh. Recovery from `.env.example` accident clean.

### 4.2 Phase 6b — smoke test (3 runs, $1.52 spent)

Three runs on task 0 (Kipchoge marathon pace) at N_SAMPLES=3. All completed. Anthropic SDK 0.92.0 confirmed compatible. Cache discipline works as specified. Anthropic API non-determinism observed (same task, different trajectories). N=3 caused entropy collapse (all H=0).

Full details: `docs/reviews/PHASE_6B_REVIEW.md`

### 4.3 Phase 6c-prep — Tavily /usage fix + dotenv (commit c5b4267)

Two mechanical fixes in benchmark.py: nested key lookup for Tavily /usage, and `load_dotenv()` in `main()` for direct invocation. All 4 verification tests passed.

### 4.4 Phase 7 validation — partial (3 of 6 tasks, $5.04 spent)

Ran task 0 twice (accidental duplicate), task 1, task 2 at N_SAMPLES=10.

**Task 2 surviving TSV** (the only per-condition data captured before overwrite):
- Condition A: 29,846 tokens, verifier_passed=False, terminated=completed
- Condition B: **7,769 tokens**, verifier_passed=False, terminated=completed
- **A/B token ratio: 3.84x**
- H_raw = 0.0 for both (collapse at N=10 — concerning)

**Critical findings**:
1. **Token efficiency signal across 4 paired observations** (Phase 6b Block 1/3/4 + validation task 2): ratios 5.0x, 1.2x, 2.4x, 3.8x. **All 4 show B < A.** Mean 3.1x. p=0.0625 binomial.
2. **N=10 entropy collapse** observed on task 2. Spec assumed N=10 was the floor. It may not be. Possible causes: clustering threshold too loose (0.15), task genuinely unambiguous, sampling temperature too low. Unknown from n=1.
3. **Per-task cost variance**: 4.8x spread ($0.42 to $2.00). Original Phase 7 cost estimates were too optimistic.

### 4.5 Spending

| Item | Cost |
|---|---|
| Phase 6b smoke | $1.52 |
| Phase 7 validation | $5.04 |
| **Session 1 total** | **$6.57** |

Anthropic charged: **$152** ($77 initial + $75 additional). Remaining: **~$145**.

---

## 5. Phase 7 NEW PLAN (replaces all prior 8 redesign options)

### 5.1 Decision rationale

The original spec (3×40×N=10) was framed as a publishable test. After validation revealed N=10 collapse risk, agent non-determinism larger than expected, and per-task cost variance of 4.8x, **the goal was reframed**:

- **Session 1 (closed)**: Pipeline works, hypothesis-relevant signal exists (4/4 token efficiency favors B), N=10 may be insufficient.
- **Session 2 (next)**: Small exploration to see what patterns emerge across difficulty levels, with reduced parameters for fast iteration.
- **Session 3+**: Forward model addition. *That* is when publishable testing happens.

### 5.2 New Phase 7 structure

**Two-stage exploration with multi-level scope**:

**Stage 1 — Pilot (6 tasks)**:
- 2 tasks each from Level 1, Level 2, Level 3
- N_SAMPLES = **5** (down from 10)
- Clustering threshold = **0.08** (down from 0.15)
- 1 run only
- Text-only tasks (current filter unchanged)
- Estimated cost: ~$10-15
- Estimated time: ~2-3 hours
- **Purpose**: Technical validation (multi-level pipeline works) + minimal pattern hint (2 datapoints per level shows direction)

**Stage 2 — Main exploration (18 tasks)**:
- 6 tasks each from Level 1, Level 2, Level 3
- Same N=5, threshold=0.08
- 1 run only
- **Purpose**: Pattern observation across difficulty levels — does inverse effect scale with task complexity as Wolpert-Kawato theory predicts?
- Estimated cost: ~$30-50
- Estimated time: ~6-10 hours

**Stage 3 (later, possibly Session 3+)**:
- Forward model added
- *Then* publishable-quality experiment
- Out of scope for Session 2

### 5.3 Why these specific numbers

- **N=5**: Reduced from 10 because exploration cares about *direction*, not precise entropy values. Combined with tighter threshold to compensate.
- **threshold=0.08**: Direct response to N=10 collapse on task 2. Tighter clustering should resolve more clusters from the same samples. **Not validated** — pilot will test this.
- **6/18 split**: Pilot 6 = 2 per level (minimum to see within-level variance). Main 18 = 6 per level (enough for level-comparison pattern, not statistical proof).
- **Multi-level**: Original spec was Level 1 only. Hypothesis is about generalization — testing one difficulty hides whether the effect scales. Wolpert-Kawato theory predicts inverse model value should *increase* with task complexity.
- **1 run only**: Reproducibility measurement is largely defeated by cache architecture (cached components are deterministic by design). Multiple runs only measure agent ReAct loop noise. Save for forward-model phase.

### 5.4 Required code changes (Phase 6c2-prep)

Currently `load_gaia_tasks()` only loads Level 1. Multi-level support needed:
- Add `level` parameter to `load_gaia_tasks()` accepting 1, 2, or 3
- Or add `--level` CLI argument to benchmark.py
- Also: add `--task-id` CLI alternative to `--task` (index) for explicit task selection across levels
- Cost: $0
- Time: 30-60 min for code + verification

This is **Session 2's first technical action** (in Session A).

---

## 6. Two parallel sessions for Session 2

### 6.1 Why parallel

Session 1 demonstrated context inflation problems. Sequential work in one long session causes drift. Solution: split Session 2 into two parallel Claude conversations with different scopes.

**Session A — Phase 7 setup and execution** (long, complex)
**Session B — GAIA dataset exploration** (short, focused)

Coordination is done by **the user**, not by the Claudes. Session B writes a small .md report, user verifies it, user pastes it into Session A.

### 6.2 Why this works

- Each session has clean, focused context
- Session A and Session B can run **truly in parallel** — Session A starts setup work that doesn't depend on GAIA exploration results (code changes, prompt drafting), Session B does exploration in background
- User integrates results when both ready
- Github holds final products, user's external coordination tool (separate project) holds the thinking trail

### 6.3 Open questions Session B must answer

1. GAIA validation split: Level 1, 2, 3 total task counts
2. After `file_name` filter: counts per level
3. After multimodal URL filter: counts per level
4. Sample question text from 3 Level 2 and 3 Level 3 tasks (short)
5. Expected_answer format for Level 2 and 3 (number? string? list?)

These determine Phase 7 feasibility. If Level 3 has fewer than 6 text-only tasks after filter, the 6/18 split per-level needs adjustment.

---

## 7. Open questions (for Session 2)

1. **Does threshold=0.08 fix the H_raw collapse?** Pilot will test. If pilot still shows widespread H=0, escalate to threshold=0.05 or temperature increase.

2. **L2 and L3 task counts after filter?** Session B answers.

3. **Will L2 and L3 tasks complete within max_steps?** L1 max_steps=15, L2=25, L3=50. Validation showed L1 tasks can run 9-25 min. L2/L3 may be much longer.

4. **Cost per L2/L3 task?** Unknown until pilot. Could be 2-5x L1 cost.

5. **Pattern direction**: Does the A/B token ratio increase with difficulty (theory predicts yes), stay constant, or decrease?

---

## 8. Safety notes for Session 2

**NEVER**:
- Touch `.env.example` (tracked file, two recovery incidents already)
- Echo `.env` contents to chat or terminal
- Re-invoke a running benchmark.py process (Python stdout buffering is normal)
- Skip the 30-minute hard limit per task
- Commit `results/` or `cache/` (gitignored)
- Misinterpret `loop_count=0` as a bug (it's the hypothesis-favorable outcome)
- Treat 1 datapoint as evidence of a pattern
- Confuse pilot (6 tasks, technical validation + minimal hint) with main exploration (18 tasks, pattern observation)

**ALWAYS**:
- Read CHECKPOINT_01.md fully before acting
- Capture each task's stdout immediately (results.tsv overwrites)
- Monitor H_raw distribution on first 2-3 pilot tasks — if all collapse to 0, STOP and escalate
- Trust that Phase 6c-prep dotenv fix works (no inline wrappers)
- Apply 30-minute hard limit per task
- Be honest about what data shows vs. what we want it to show

---

## 9. Budget state

- Anthropic charged: $152 ($77 + $75)
- Spent in Session 1: $6.57
- **Remaining**: ~$145
- Session 2 estimated cost: $40-65 (pilot $10-15 + main $30-50)
- **Plenty of headroom** — budget is no longer a constraint

Tavily: ~50 of 1000 credits used. ~950 remaining. No concern.

---

## 10. Session 2 prompts

### 10.1 Session B prompt (start first, runs in parallel with Session A)

This is a SHORT session for one focused task. Open a new Claude conversation and paste:

```
This is a focused exploration task. I need information about the GAIA benchmark dataset before deciding on a multi-level experiment design. You have access to Claude Code which can run Python and access HuggingFace datasets.

Goal: Produce a short markdown report with the following information:

1. GAIA validation split — total task count for Level 1, Level 2, Level 3
2. After filtering tasks where `file_name` is non-empty (file attachments) — counts per level
3. After filtering tasks where the question body contains image/video/audio URLs — counts per level
4. From Level 2 text-only tasks: 3 sample questions (just the question text, kept short)
5. From Level 3 text-only tasks: 3 sample questions (just the question text, kept short)
6. Expected_answer format observed in Level 2 and Level 3 — are answers numbers, strings, lists, structured?

The dataset is at huggingface.co/datasets/gaia-benchmark/GAIA. HF authentication is needed (already configured in .env at C:/Users/433/Documents/prompt-training/.env).

You can either:
- Use the existing project at C:/Users/433/Documents/prompt-training (it has a load_gaia_tasks function in benchmark.py that handles Level 1; you'll need to adapt for L2 and L3)
- Or write a fresh small Python script that loads each level separately

Either way, do not modify benchmark.py. This is read-only exploration.

Output format: a single markdown report with the 6 answers above. Keep it concise — bullet points and numbers, not prose.

Do not commit anything. Do not run any benchmark or experiment. This is purely dataset inspection.

When done, paste the markdown report so I can verify it and forward to my main session.
```

Expected time: 10-15 minutes.

### 10.2 Session A prompt (start nearly simultaneously, long-running)

This is the main Session 2 work. Open another new Claude conversation and paste this prompt followed by the full CHECKPOINT_01.md content:

```
This is Session 2 of the prompt-training project, continuing from Session 1's CHECKPOINT_01.md.

Session 2 has two parallel components:
- Session A (this one) — Phase 7 setup, code changes, pilot execution
- Session B (separate Claude conversation, started in parallel) — GAIA dataset exploration

I will provide Session B's results when they arrive (10-15 min). Until then, you can proceed with work that does not depend on GAIA exploration results.

Please read the CHECKPOINT_01.md content below in full before acting. Pay special attention to:
- §1 (Critical reframing — exploration not publishable)
- §5 (New Phase 7 plan — 6/18 split, N=5, threshold=0.08, multi-level)
- §6 (Two parallel sessions design)
- §7 (Open questions)

Session 2 (Session A) goals in order:
1. Read and acknowledge CHECKPOINT_01.md
2. Phase 6c2-prep: Add multi-level support to load_gaia_tasks() (no GAIA exploration needed for this — code change only)
3. Wait for Session B results (I will paste them)
4. Use Session B results to select 6 specific tasks for the pilot (2 per level)
5. Write Phase 7 pilot prompt for Claude Code
6. Execute pilot via Claude Code
7. Review pilot results
8. Decide whether to proceed to 18-task main exploration

Constraints:
- Budget: ~$145 Anthropic remaining, plenty of headroom
- Pilot expected cost: $10-15
- Main expected cost: $30-50
- 30-minute hard limit per task
- Never re-invoke a running benchmark process
- Capture each task's stdout immediately (results.tsv overwrites)
- Be honest about exploration findings — this is not testing, it's understanding

The CHECKPOINT_01.md content follows. After reading it, acknowledge and start with step 2 (Phase 6c2-prep planning) while we wait for Session B.

---

[PASTE FULL CONTENTS OF CHECKPOINT_01.md HERE]
```

---

## 11. End of CHECKPOINT_01 v2

Session 1 closes here. Session 2 begins with two parallel Claude conversations as described in §10. The user (Elden) coordinates between them by hand, with verification.

The experiment is real, the framing is honest, and the budget is sufficient. Good luck, Session 2.
