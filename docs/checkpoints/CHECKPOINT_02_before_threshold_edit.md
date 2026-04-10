# CHECKPOINT_02 — Pilot preparation complete, before threshold edit

**Project**: prompt-training
**Repository**: https://github.com/eldensari/prompt-training
**Local**: C:/Users/433/Documents/prompt-training
**Checkpoint date**: 2026-04-09
**Preceding checkpoint**: `docs/checkpoints/CHECKPOINT_01.md` (Session 1 close)
**HEAD at checkpoint**: `0bd139b` (Phase 6c2-prep: add multi-level GAIA support)

---

## 1. What this checkpoint covers

Session 2 Session A made three verified state transitions since CHECKPOINT_01:

1. **Phase 6c2-prep** — multi-level GAIA support in `benchmark.py` (committed)
2. **Pilot candidate pool enumeration** — read-only, no file changes
3. **A/B condition definition clarification** — read-only, no file changes

Together these constitute "pilot preparation complete." Next state transition = threshold edit + pilot execution.

Per CHECKPOINT_01 §1, framing remains: **exploration, not publishable testing.**

---

## 2. Git state

- HEAD: `0bd139b` — Phase 6c2-prep: add multi-level GAIA support
- Branch: main
- Working tree: clean (prior to this checkpoint file commit)
- 20 commits total

Recent commits:
```
0bd139b Phase 6c2-prep: add multi-level GAIA support
bd01cb8 docs: update CHECKPOINT_01 with Phase 7 exploration plan
3ec0738 docs: add Phase 6b review and session 1 checkpoint
```

---

## 3. Phase 6c2-prep — completed and verified

### Changes (commit 0bd139b)
- `benchmark.py`: +66 / -11 lines
- `load_gaia_tasks(level: int = 1)` — parameterized, dynamic HF config `2023_level{N}`, ValueError on bad level, task_id uniqueness assert, log line `[load_gaia_tasks] level=N filtered_count=N`
- CLI: `--level {1,2,3}` (default 1), `--task-id STR`, mutual exclusion with `--task INT`
- Default behavior (no `--level`) preserved — existing L1 callers unaffected

### Verification (all PASS, zero API spend)
- V1 `--help` shows new flags
- V2 L1 regression: 40 tasks
- V3 L2=66, L3=19
- V4 task_id uniqueness across all 3 levels
- V5 CLI mutual exclusion errors before any API call

### Known non-issues
- HF token warning on bare `from benchmark import ...` (dotenv only loads in `main()`) — harmless, CLI path unaffected
- `run_experiment()` at line 352 still calls `load_gaia_tasks()` without level — intentional, preserves full-run default

---

## 4. GAIA dataset landscape (from Session B + candidate enumeration)

### Text-only counts after filter
| Level | Total | Text-only | Pilot-eligible (numeric or short string, no comma-list) |
|---|---|---|---|
| 1 | 53 | 40 | 33 |
| 2 | 86 | 66 | 61 |
| 3 | 26 | 19 | 15 |

### Answer format (Session B)
- L2: 53% numbers, 39% short strings, 8% comma-lists
- L3: 47% numbers, 32% short strings, 21% comma-lists
- Verifier built for L1 generalizes; L3 comma-list rate (21%) is a watch item for main exploration, avoided in pilot

### Multimodal URL filter
Near no-op (−2 on L1, 0 on L2/L3). `file_name` filter does nearly all the work.

---

## 5. A/B condition definition (verified from benchmark.py)

### Selection mechanism
- **Single invocation runs both A and B** via `run_task_both_conditions()` at `benchmark.py:381`
- Returns `[row_A, row_B]` → 2 rows per task in `results.tsv`
- `--condition` CLI flag is a post-filter only, not a selector

### Actual difference (benchmark.py:411–453)
Only the `summarized_query` fed to `run_react_loop` differs:
- **Condition A**: `raw_summary` = `summarize_to_head(original_question)`
- **Condition B**: `improved_summary` = `summarize_to_head(inverse(question))`

Same model, same max_steps, same tool set, same agent loop. Clean comparison.

### N_SAMPLES and threshold
- `N_SAMPLES` — `benchmark.py:77`, default 10, CLI-overridable via `--n-samples`
- Clustering threshold — `inverse.py:102` constant `CLUSTERING_DISTANCE_THRESHOLD: float = 0.15`, **not CLI-overridable**, requires source edit + cache version bump per `inverse.py:460-461`

### results.tsv
- Path: `results/results.tsv`
- Mode `"w"` — **overwrites every invocation** (CHECKPOINT_01 §8 warning confirmed)
- Per-task stdout + manual file copy required between task runs

---

## 6. Selected pilot tasks (6 task_ids, 2 per level, all numeric answers)

All selected to minimize verifier noise: pure numeric answers, no comma-lists, avoided reversed-text / logic-symbol / special-char cases.

### Level 1
| task_id | answer | Question (short) |
|---|---|---|
| `8e867cd7-cff9-4e6c-867a-ff5ddc2550be` | 3 | Mercedes Sosa studio albums 2000–2009 |
| `dc28cf18-6431-458b-83ef-64b3ce566c10` | 2 | Family reunion mashed potatoes quantity |

### Level 2
| task_id | answer | Question (short) |
|---|---|---|
| `17b5a6a3-bc87-42e8-b0fb-6ab0781ef2cc` | 34689 | Invasive species popularized as movie main character |
| `3627a8be-a77f-41bb-b807-7e1bd4c0ebdf` | 142 | British Museum mollusk shell 2012,5015.17 |

### Level 3
| task_id | answer | Question (short) |
|---|---|---|
| `676e5e31-a554-4acc-9286-b60d90a92d26` | 86 | July 1959 US processed fruit/vegetable standards |
| `e961a717-6b25-4175-8a68-874d28190ee4` | 12 | Asian monarchies with sea access (Wikipedia, 2021) |

### Selection rationale
- All numeric → cleanest verifier signal for exploration
- L1 tasks provide Session 1 comparability (similar difficulty profile to prior validation runs)
- L2 tasks are multi-hop lookups in external/domain sources
- L3 tasks chosen on the simpler end of L3 to raise max_steps=50 completion probability; `e961a717` in particular is a single Wikipedia query
- **Not guaranteed** that Session 1's task index 2 (the 3.84x ratio anchor) is among these — task_id was not recorded in Session 1's surviving TSV. Anchor continuity is approximate, not exact.

---

## 7. Phase 7 pilot parameters (unchanged from CHECKPOINT_01 §5)

- **N_SAMPLES = 5** (via `--n-samples 5`)
- **Clustering threshold = 0.08** (requires `inverse.py` edit, not yet done)
- **1 run only**
- **30-minute hard limit per task**
- **Sequential execution** (not batch) — enables H_raw monitoring and early abort
- Expected cost: $10–15
- Expected time: 2–3 hours

---

## 8. Next state transition (for the session that loads this checkpoint)

**Goal**: Edit clustering threshold + execute pilot + capture results.

### Step B.75 — threshold edit (first, small, committable in isolation)
1. Edit `inverse.py:102` — `CLUSTERING_DISTANCE_THRESHOLD: float = 0.15` → `0.08`
2. Bump cache version per the comment at `inverse.py:460-461` (exact mechanism to be read at implementation time)
3. Verify: no syntax errors, the constant reads 0.08, cache version incremented
4. Commit with message referencing the N=10 collapse observation from Phase 7 validation
5. Zero API spend

### Step C — pilot execution (sequential, 6 tasks)
For each of the 6 task_ids in §6:
1. `python benchmark.py --level N --task-id <id> --n-samples 5`
2. Capture full stdout immediately to `results/pilot_<task_id>.log`
3. Copy `results/results.tsv` to `results/pilot_<task_id>.tsv` **before** next task
4. Check H_raw distribution in the row
5. **Abort rule**: if first 2–3 tasks all show H_raw=0 for both conditions, STOP and escalate (threshold=0.05 or temperature bump)
6. 30-minute hard limit per task — kill and record if exceeded

### Step D — pilot review
After all 6 tasks (or early abort):
- A/B token ratio per task
- H_raw distribution — did 0.08 resolve the collapse?
- Per-level pattern hint (2 datapoints per level = direction only, not evidence)
- Decision: proceed to main 18-task exploration, adjust parameters, or stop

---

## 9. Open questions (carried from CHECKPOINT_01 §7)

1. **Does threshold=0.08 fix H_raw collapse?** — Step C tests
2. **L2 and L3 task completion rate within max_steps?** — unknown until pilot
3. **Per-task cost for L2/L3?** — unknown, could be 2–5x L1
4. **Pattern direction** (A/B token ratio scaling with difficulty) — minimal signal from 6 tasks, real signal requires main 18

---

## 10. Safety notes (carried from CHECKPOINT_01 §8, still active)

**NEVER**:
- Touch `.env.example`
- Echo `.env` contents
- Re-invoke a running benchmark.py process
- Skip 30-minute hard limit per task
- Commit `results/` or `cache/`
- Treat 1 datapoint as pattern evidence
- Confuse pilot (6, technical + hint) with main (18, pattern observation)

**ALWAYS**:
- Read this checkpoint fully before acting
- Capture stdout + copy results.tsv between tasks
- Monitor H_raw on first 2–3 pilot tasks — abort on full collapse
- Be honest: exploration, not testing

---

## 11. Budget state

- Anthropic charged: $152
- Spent through Session 1: $6.57
- Spent in Session 2 so far: $0 (code + read-only operations)
- **Remaining**: ~$145
- Step B.75: $0
- Step C pilot: $10–15 estimated
- Step D: $0 (review)
- Budget is not a constraint

---

## 12. Checkpointing protocol (new, effective CHECKPOINT_02)

Per Session 2 decision: **new checkpoint per verified state transition**, not per micro-step.

State transition = a committable, reviewable state change that would cleanly survive being handed to a fresh Claude session.

Each checkpoint file named: `CHECKPOINT_NN_<short_description>.md`

Expected pacing for remainder of Phase 7:
- CHECKPOINT_03 — after Step B.75 (threshold edit committed) + before pilot starts, OR after pilot completes if pilot runs in same session as threshold edit without issue
- CHECKPOINT_04 — after pilot review, before main 18 decision
- CHECKPOINT_05+ — as main exploration progresses

The session that loads this checkpoint should decide at its own close point whether it produced one state transition or two, and checkpoint accordingly.

---

## 13. New session bootstrap block

To continue work, open a new Claude conversation and paste the following prompt followed by the full contents of this file:

```
This is a continuation of the prompt-training project. Load the checkpoint below in full before acting. Pay special attention to §1 (framing), §5 (A/B definition), §6 (selected pilot tasks), §8 (next state transition), §10 (safety notes), and §12 (checkpointing protocol).

Your job: execute the "Next state transition" in §8 — starting with Step B.75 (threshold edit), then Step C (pilot execution), unless anomalies warrant stopping earlier.

Working method: I (Elden) do not let you write code directly. You produce Claude Code prompts that I paste into a separate Claude Code session. I relay outputs back to you. You review, decide, and produce the next prompt.

Before executing: acknowledge the checkpoint, identify anything ambiguous, and propose the Step B.75 Claude Code prompt. Wait for my OK before I paste it to Claude Code.

---

[PASTE FULL CONTENTS OF CHECKPOINT_02_before_threshold_edit.md HERE]
```

---

## 14. End of CHECKPOINT_02

This session's role ends after this file is committed. The next session begins cleanly from the bootstrap block in §13.

The experiment is real, the framing is honest, and the budget is sufficient. Good luck, Session 2 Step B.75+C.
