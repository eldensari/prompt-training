# CHECKPOINT_03 — Pilot complete, with bottleneck finding

**Project**: prompt-training
**Repository**: https://github.com/eldensari/prompt-training
**Local**: C:/Users/433/Documents/prompt-training
**Checkpoint date**: 2026-04-10 (Session 2 close)
**Preceding checkpoint**: `docs/checkpoints/CHECKPOINT_02_before_threshold_edit.md`
**HEAD at checkpoint**: `536445d` (Phase 7 pilot: lower clustering threshold 0.15 → 0.08)

---

## 1. Reframing: this was a diagnostic session, not an evaluation

CHECKPOINT_01 §1 framed Phase 7 as "exploration, not publishable testing." CHECKPOINT_03 adds a second layer: **this session turned out to be a pipeline diagnostic, not a pilot evaluation.** The 6-task pilot ran to completion, but the interpretable output is not "does inverse work on GAIA?" — it is "where in the pipeline does inverse get silently damaged?"

The single most important sentence in this checkpoint:

> **The inverse() implementation matches the Wolpert-Kawato specification, but its output is re-compressed by summarize_to_head(max_tokens=80) before reaching the agent, and this second compression step is very likely destroying most of the inverse model's work.**

Everything else in this checkpoint supports, qualifies, or operationalizes that sentence.

---

## 2. Git state

- HEAD: `536445d` — Phase 7 pilot: lower clustering threshold 0.15 → 0.08
- Branch: main
- Working tree: clean
- Pilot results captured in `results/pilot_*.tsv` and `results/pilot_*.log` (gitignored)
- `results/pilot_batch_summary.txt` exists, gitignored
- No source code changes this session beyond the single threshold+cache-version commit (536445d)

---

## 3. The two root findings, in order of discovery

### Finding 1 — inverse() is implemented per spec

`inverse.py` §6 (function `inverse()`) calls three templates — `prompt_target`, `prompt_invert`, `prompt_compose` — in sequence, with independent LLM calls, temperature=0, no shared conversation history. These map 1:1 to `spec/prompt-training-forward-inverse_model.md` §Inverse Model steps 1-4 (Target → Invert → Compose). The "k=4 backward chaining" and "independent prompt chaining via explicit injection" structural commitments are present in code.

**Implication**: the pilot's negative results cannot be interpreted as "inverse doesn't work." The correct interpretation is "inverse's output was tested under a pipeline that may be erasing most of its effect."

### Finding 2 — the 80-token second-compression bottleneck

The `inverse()` function (inverse.py §6) ends with a call that takes `improved_prompt` (up to 1024 tokens, containing the done-state, the backward chain, and a self-contained instruction) and passes it to `summarize_to_head(..., max_tokens=80)`, producing `improved_summary`. `_SUMMARIZE_TEMPLATE` (inverse.py §2) instructs the LLM to compress the input into **a single English sentence** of at most 80 tokens that preserves "the goal and the concrete deliverable."

`benchmark.py` §411-453 confirms that Condition B's `summarized_query` is precisely this `improved_summary` — the re-compressed one-sentence form — not the richer `improved_prompt`.

**Consequence**: the structure that Target/Invert/Compose carefully build is reduced to "goal + deliverable in one sentence" before the agent ever sees it. In most cases, Condition A's one-sentence summary and Condition B's one-sentence summary will look remarkably similar, because both are outputs of the same `_SUMMARIZE_TEMPLATE` applied under "one sentence, goal + deliverable" instructions.

This is the single-best explanation that is consistent with all 6 pilot tasks (see §4).

---

## 3.5. Decisive moments in this session

Three turns initiated by Elden altered the session's trajectory. Each was a frame change, not a data point.

1. **Entropy demoted to secondary tool** (after Task 3)
   Elden observed that entropy was originally designed as an auxiliary observation tool, not as a primary success metric. Reframing: primary = correctness / termination mode / token cost; secondary = H_raw and H_improved. Every subsequent interpretation in this session operated under this frame. Without this reframe, Task 3's H_raw=0 alongside a correct answer would have been read as a failure of the threshold intervention rather than as confirmation that H_raw ≠ correctness.

2. **Suspicion of the summarization layer** (after Task 4)
   Elden asked whether `summarize_to_head` itself could be causing distortion. Until this point, Claude had been treating `inverse()` as a black box whose effects were observable only at the output. This question redirected the investigation toward pipeline internals. Without it, the session would likely have ended with a conclusion that inverse() does not improve GAIA performance — a false negative.

3. **Request to read inverse.py source** (after Task 5)
   Elden provided the `inverse.py` source and the two spec documents. Reading `inverse()` §6 directly revealed Finding 1 (spec-compliant implementation) and Finding 2 (80-token re-compression bottleneck). This was the single highest-signal action of the session in terms of explanatory power per minute invested.

### Hypothesis amplitude during the session

The working interpretation of pilot results shifted as data arrived:

1. After Task 1: "threshold=0.08 did not resolve H_raw collapse"
2. After Task 2: "B detects under-specification" (first appearance, from the refusal output)
3. After Task 3: "A ≈ B when both succeed; B only wins on failure"
4. After Task 4: "B is not reliably efficient; B/A token ratio varies with task structure, not with difficulty"
5. After reading inverse.py: "All of the above are symptoms of inverse model output being re-compressed to a single sentence before reaching the agent; the true variable is how much inverse-model structure survives compression for each task"

Interpretation 5 is the current Finding 2 hypothesis. It awaits confirmation in Phase 7.5.A. Interpretations 1-4 are now treated as artifacts of incomplete pipeline visibility.

### Operational anomaly: Task 5 background detach

Claude Code auto-detached `benchmark.py` to background during Task 5 execution. The `bash_tool`'s foreground "timeout 30m" did not apply to the detached process. While Claude (in this session) was drafting a kill prompt based on the assumption that the process was stuck, the process self-terminated with exit code 0 at 1984.5 seconds (33.1 minutes) and wrote valid TSV data.

Claude Code then labeled Task 5 as ABORTED because wall-clock exceeded the 30-minute hard limit, per a literal reading of the batch prompt's abort condition (c). Claude (in this session) recovered the data by instructing Claude Code to copy `results.tsv` to `pilot_676e5e31.tsv` before the next task could clobber it, and to rewrite the ABORTED line in `pilot_batch_summary.txt` as a normal summary line.

Lesson: abort conditions should be read by intent (prevent runaway cost) rather than by letter (kill anything over N minutes). A self-terminated overrun with valid output is not an abort case. This lesson is codified in §9 Operational lessons and in the safety notes of §10.

---

## 4. Pilot results — primary metric matrix

Entropy is set aside here (it is a secondary observation tool, per Session 2 reframing). Primary metrics: correctness, termination mode, token cost, B/A ratio.

| Task | Level | A answer | A token | A term | B answer | B token | B term | B/A tok | Category |
|---|---|---|---|---|---|---|---|---|---|
| 1 (8e867cd7) | L1 | none | 387,776 | max_steps | none | 176,465 | max_steps | 0.46 | both_none |
| 2 (dc28cf18) | L1 | "3" wrong, correct=2 | 6,065 | completed | refusal | 6,479 | completed | 1.07 | both_wrong_diff |
| 3 (17b5a6a3) | L2 | 12 correct | 29,871 | completed | 12 correct | 30,797 | completed | 1.03 | both_correct |
| 4 (3627a8be) | L2 | 142 correct | 109,914 | completed | none | 144,423 | max_steps | 1.31 | mixed (A win) |
| 5 (676e5e31) | L3 | none | 403,029 | max_steps | none | 5,153 | error | 0.013 | both_none (B crashed) |
| 6 (e961a717) | L3 | 12 correct | 664,047 | completed | "11" off-by-one | 154,905 | completed | 0.23 | mixed (A win, B 4x efficient) |

**Summary counts**:
- A correct: 3 (Tasks 3, 4, 6)
- B correct: 1 (Task 3)
- B "almost correct" (off-by-one, same shape): 1 (Task 6)
- B refusal citing under-specification: 1 (Task 2)
- B crashed / max_steps / failed: 3 (Tasks 1, 4, 5)

**Most important single observation**: Task 6 B used 23% of A's tokens, completed, and landed off-by-one on what appears to be a boundary interpretation rather than a random fabrication. This is the only datapoint in the pilot where B's token efficiency signal is clearly non-noise — and it happens on a task whose structure (single count + single condition) is the most likely to survive the 80-token bottleneck.

**Task 2 observation worth preserving**: B's refusal is the one case where B produced behavior that looks like detecting under-specification. Under §3 Finding 2's bottleneck hypothesis, this would be interpreted as "the Compose step's required-information slot happened to survive one-sentence compression for this particular task." Not confirmed, but worth testing in Phase 7.5.

---

## 5. The bottleneck hypothesis, stated precisely

**Hypothesis**: the gap between Condition A and Condition B performance is dominated by the information that is lost when `improved_prompt` is re-compressed via `summarize_to_head(..., max_tokens=80)` into `improved_summary`.

**What this hypothesis predicts** (and what Phase 7.5 will test):
1. Tasks where the required answer shape is simple will show B ≈ A or B > A, because a single sentence can carry the required structure. Consistent with Task 3 and Task 6.
2. Tasks where the required answer depends on constraints that do not fit in one sentence will show B < A. Consistent with Task 4.
3. Tasks with genuinely missing preconditions will show B diverging toward refusal only if the Compose step placed the required-information slot early enough to survive compression. Consistent with Task 2.
4. Phase 7.5 intervention: if `prompt_compose` is modified to place critical constraints in the first sentence of its output, B performance should improve on tasks 2, 4, and 6 specifically.

**What this hypothesis does NOT claim**: that inverse() is the right pipeline design for GAIA; that B will beat A in the main 18 even after the fix; that 80 tokens is inherently too small.

---

## 6. Entropy observations — for the record, not for decisions

H_raw was 0.0 in 4 of 6 tasks (1, 3, 4, 6). Only Task 2 (1.37) and Task 5 (0.72) showed non-zero H_raw. The threshold=0.08 change made at the start of this session did not resolve H_raw collapse. The collapse is dominated by `summarize_to_head`'s determinism — 5 samples at temperature=0 on the same input return near-identical text, which clusters to a single bucket.

**Entropy status for Phase 7.5 and beyond**: demoted to a secondary observation tool per the Session 2 reframing. Primary metrics drive decisions. Entropy curves may still be logged; they no longer gate decisions.

---

## 7. Budget state

- Spent through CHECKPOINT_01: $6.57
- Spent in Session 2: $8.90 (pilot) + $0 (threshold edit + diagnostic reading)
- Phase 7.5 estimate: ~$5 (diagnostic) + ~$8 (re-run of 6 pilot tasks with modified compose)
- Main 18 is still budgeted but deferred until Phase 7.5 completes

---

## 8. Next state transition — Phase 7.5 (diagnostic + targeted fix)

The session that loads this checkpoint should execute these steps in order. Do NOT jump to main 18.

### Step 7.5.A — $0 visual diagnostic (first, before any intervention)

Goal: confirm or falsify Finding 2 by reading actual pipeline outputs with human eyes, not by running more benchmarks.

For each of Tasks 2 (dc28cf18), 4 (3627a8be), and 6 (e961a717):
1. Write a small Python script that calls `inverse()` directly on the original GAIA question text. Cache should hit (v2.8.1-002), so cost should be near $0. If cache misses, cost is ~$0.10-0.30 per task.
2. Print all intermediate fields: `raw_prompt`, `raw_summary`, `target`, `inversion`, `improved_prompt`, `improved_summary`.
3. Read them manually and answer, in plain English:
   - (a) Does `target` capture a sensible done-state for this task?
   - (b) Does `inversion` list preconditions in a way that identifies the critical required inputs?
   - (c) Does `improved_prompt` put the critical inputs/constraints in its first sentence, or are they buried later?
   - (d) Does `improved_summary` preserve those critical inputs/constraints, or does it collapse to "goal + deliverable" and lose them?
4. Write a short note (3-5 bullets) per task into `docs/checkpoints/phase_7_5_A_notes.md`.

Step 7.5.A gate: if (c) shows Compose already puts critical constraints first AND (d) shows one-sentence compression preserves them, Finding 2 is weakened and 7.5.B may be unnecessary. More likely, (c) and (d) will confirm Finding 2.

### Step 7.5.B — Compose template modification

1. Edit `inverse.py prompt_compose()`: add an instruction to begin with the single most critical constraint or required input, stated explicitly in the first sentence.
2. Bump `benchmark.py CACHE_VERSION` from `v2.8.1-002` to `v2.8.1-003`. Single commit similar in shape to 536445d.
3. Verify the new constant is active.
4. Re-run the 6 pilot tasks sequentially, foreground, 30-min hard limit per task. Use explicit `timeout 1800` wrapper to avoid the background-detach hard-limit bypass that affected Task 5 this session.
5. Capture each result to `results/pilot_7_5_B_<task_id>.tsv` and `.log` to avoid clobbering Session 2's results.
6. Estimated cost: ~$8-12.

### Step 7.5.C — Phase 7.5 decision gate

After 7.5.B, compare per-task B-new vs B-old on primary metrics:

| Outcome | Decision |
|---|---|
| B-new correct on Task 2 OR 4 OR 6 where B-old was not | Proceed to main 18 with B-new |
| B-new higher token efficiency, same correctness | Proceed to main 18 with modest expectations |
| B-new unchanged from B-old | Finding 2 was wrong or incomplete. Do NOT proceed to main 18. Open new diagnostic |
| B-new worse than B-old | Revert the compose modification. Re-evaluate |

Decision recorded in CHECKPOINT_04 before any main-18 execution.

---

## 9. Operational lessons from Session 2 (carry forward to Phase 7.5)

1. **`bash_tool` background detach bypasses foreground timeout.** Task 5 auto-detached to background and the `timeout 30m` did not apply. It ran 33 minutes before self-completing. Mitigation: use `timeout 1800 python ...` as an explicit shell wrapper on every long-running command.

2. **The "hard limit" rule exists for runaway cost prevention, not for data exclusion.** Task 5 was initially marked ABORTED because it exceeded 30 minutes, but it self-completed with valid TSV data. The data was recovered. Rule: a task that self-terminates with exit code 0 and valid TSV output is NOT aborted — its data is preserved.

3. **A checkpoint's "verified" list should include component internals, not just call signatures.** CHECKPOINT_02 §5 verified that `run_task_both_conditions` calls `summarize_to_head(inverse(question))` for B but did not verify what `inverse()` actually does internally. Reading `inverse.py` earlier would have revealed Finding 2 before the pilot was run.

4. **Primary metric framing beats entropy framing when entropy is behaving badly.** Session 2's mid-session reframing (primary = correctness/termination/tokens, secondary = entropy) made the pilot results interpretable.

---

## 10. Safety notes

**NEVER**: touch `.env.example`; echo `.env` contents; re-invoke a running benchmark.py process; commit `results/` or `cache/`; treat 1 datapoint as pattern evidence; accept bash_tool's background detach for benchmark runs without explicit wrapper.

**ALWAYS**: read the current checkpoint fully before acting; use explicit `timeout 1800` shell wrapper for any long-running command; capture stdout + copy results.tsv between tasks; preserve data from self-terminating tasks even if they exceed wall-clock limits; be honest — diagnostic, not evaluation.

---

## 11. New session bootstrap block

To continue work, open a new Claude conversation and paste the following prompt followed by the full contents of this file:

```
This is a continuation of the prompt-training project. Load the checkpoint below in full before acting. Pay special attention to §1 (reframing), §3 (the two root findings, especially Finding 2), §5 (bottleneck hypothesis), §8 (next state transition — Phase 7.5.A first, then 7.5.B), §9 (operational lessons, especially the background-detach issue), and §10 (safety notes).

Your job: execute §8 Step 7.5.A FIRST — a $0 visual diagnostic, no benchmarking yet. Produce a Claude Code prompt that reads inverse() intermediate outputs for Tasks 2, 4, and 6 from cache, prints all intermediate fields, and helps me answer the four manual questions in §8 Step 7.5.A. Wait for my OK before I paste it to Claude Code.

Working method: I (Elden) do not let you write code directly. You produce Claude Code prompts that I paste into a separate Claude Code session. I relay outputs back to you. You review, decide, and produce the next prompt.

Before executing: acknowledge the checkpoint, identify anything ambiguous in §8 Step 7.5.A, and propose the Claude Code prompt. Entropy is a secondary tool now — do not get distracted by H_raw values.

When producing the next checkpoint at the close of this session, follow the template in §13 of the checkpoint loaded above. Inherit its structure, inherit §10 Safety notes with any additions from this session's Operational lessons, and do not rewrite the template itself unless you have a structural reason documented in that checkpoint's §1 framing.

---

[PASTE FULL CONTENTS OF CHECKPOINT_03_pilot_complete_with_bottleneck_finding.md HERE]
```

---

## 13. Template for future checkpoints

This section is inherited by every subsequent checkpoint. When producing a new checkpoint, copy this template structure forward and amend §10 Safety notes with any new operational lessons. Do not rewrite the template itself unless there is a structural reason to do so (and if you do, document the reason in that checkpoint's §1 framing).

### Structure

Every checkpoint has two kinds of sections.

**Technical sections** — for a future Claude session to resume from:
- Git state and HEAD hash
- Current pipeline configuration and any constants that changed this session
- Next state transition with concrete commands, abort conditions, and decision gates
- Budget state (spent this session, cumulative, estimated for next phase)
- Safety notes, inherited from the previous checkpoint and amended with new lessons
- Bootstrap block for the next session

**Narrative sections** — for a future Elden (or a future Claude reading as Elden's proxy) to understand how we got here:
- Framing — one sentence naming the kind of session this was (exploration / evaluation / diagnostic / refactor / recovery / other)
- Findings — numbered, in order of discovery, each stated as a claim that can be either confirmed or refuted later
- Decisive moments — turns where a hypothesis flipped, a frame was redefined, or an operator judgment call altered the trajectory. Attribute the initiator (Elden / Claude / Claude Code) for each
- Hypothesis amplitude — when a working hypothesis changed during the session, record the sequence of interpretations in order. This is what distinguishes a diagnostic session from a clean one
- Operational lessons — one-line takeaways that change how future sessions should be run. These become candidates for next checkpoint's safety notes

### Minimum checklist

Skip a row only with explicit justification in the checkpoint itself.

- [ ] Framing sentence in §1
- [ ] At least one Finding with clear claim / evidence / status
- [ ] Decisive moments section, even if only one bullet
- [ ] Next state transition with abort conditions
- [ ] Budget state
- [ ] Bootstrap block

### Rule of thumb: narrative vs technical

If the content would survive unchanged across sessions, it is technical. If the content only makes sense inside the story of this particular session, it is narrative.

Example: "CACHE_VERSION is v2.8.1-003" is technical. "We bumped CACHE_VERSION because Finding 2 required invalidating clusterings computed under the prior compose template" is narrative.

Both belong in the checkpoint. Keep them in separate sections so future readers can filter to the level they need.

### Inheritance rules

A new checkpoint **inherits**:
- Safety notes from the previous checkpoint, with new lessons appended
- This §13 template itself, copied forward

A new checkpoint **does NOT inherit**:
- Narrative sections (Findings, Decisive moments, Hypothesis amplitude) — those are specific to the session that produced them
- The previous checkpoint's Next state transition — the new one replaces it

To reconstruct the full project history, read checkpoints in order from CHECKPOINT_01 through the current one. No single checkpoint contains the whole story; the sequence does.

---

## 12. End of CHECKPOINT_03

This session's role ends after this file is committed. The next session begins cleanly from the bootstrap block in §11. The pilot is complete. The diagnostic finding is the real deliverable of Session 2.
