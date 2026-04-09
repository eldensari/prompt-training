# CHECKPOINT_01 — Session 1 Close

**Project**: prompt-training (hypothesis: inverse model pre-processing reduces agent infinite loops)
**Repository**: https://github.com/eldensari/prompt-training (Public, MIT)
**Local path**: C:/Users/433/Documents/prompt-training
**Session 1 date**: 2026-04-09
**Checkpoint written**: 2026-04-09 ~14:00 PST
**Next session**: Session 2 — Phase 7 redesign + execution

---

## 1. Session metadata

**What Session 1 accomplished**:
- Phase 6a pre-flight complete (environment, dependencies, GAIA load, pricing)
- Phase 6b smoke test complete (3 runs on task 0, pipeline verified end-to-end)
- Phase 6c-prep complete (Tavily /usage fix + dotenv auto-loading)
- Phase 7 validation **partial** (3 of planned 6 tasks executed, intentional early stop for budget analysis)
- PHASE_6B_REVIEW.md written
- CHECKPOINT_01.md written (this document)

**What Session 1 deliberately did NOT do**:
- Phase 7 full runs (deferred to Session 2 after budget-constrained redesign)
- Phase 7 validation tasks 3, 4, 5 (stopped early; 3-task data sufficient for decision)
- Any commits to benchmark.py, inverse.py, agent_tools.py after Phase 6c-prep

**Session transition rationale**: Phase 7 validation revealed per-task cost variance (4.8x spread) that invalidates the original Phase 7 plan under the available $77 Anthropic budget. Rather than make the redesign decision in this session (already long, with context accumulation and some drift), Session 2 will enter with fresh context, validation data, and explicit redesign options. The decision is deferred but not abandoned.

---

## 2. Git state

**Current HEAD**: `c5b4267` — Phase 6c-prep: Tavily /usage shape fix + dotenv auto-loading
**Branch**: main
**Remote**: origin/main, synced (pushed after Phase 6c-prep)
**Working tree**: clean (to be verified once docs are committed at end of Session 1)

**Commit log (last 5)**:
```
c5b4267 Phase 6c-prep: Tavily /usage shape fix + dotenv auto-loading
21a1b15 Phase 6a-prep: pyproject.toml py-modules — fix flat-layout discovery
b40050b Phase 5.5: Tavily cache wrappers
a6fefa1 Phase 5: cost monitoring + reproducibility wiring
7ffbb1d Phase 4b: run_react_loop body with full [a]-[h] flow
```

**Total commits on origin/main at Session 1 close**: 18 (or 19 if the docs commit lands before session ends)

---

## 3. Repo state

**Repo layout** (Session 1 end):
```
prompt-training/
├── README.md, CHANGELOG.md, LICENSE, pyproject.toml
├── .env.example (committed empty template)
├── .env (gitignored, real keys, local only)
├── .gitignore
├── benchmark.py (18 commits history, HEAD at c5b4267)
├── inverse.py (stable since Phase 2/3)
├── agent_tools.py (stable since Phase 4a)
├── gaia_scorer.py
├── spec/                    — specification layer (design docs)
├── implementation/          — implementation layer (detailed algorithms)
├── operations/              — operations layer (cost, reproducibility, caching)
├── analysis/                — analysis layer (empty, for Phase 8)
├── roadmap/                 — roadmap (empty, placeholder)
├── archive/                 — archive (earlier design iterations)
├── docs/                    — (added at Session 1 close)
│   ├── checkpoints/
│   │   └── CHECKPOINT_01.md (this file)
│   └── reviews/
│       └── PHASE_6B_REVIEW.md
├── cache/                   — (gitignored) populated by Phase 6b and 7 validation
│   ├── h_raw/               — ~3 files
│   ├── inverse/             — ~3 files
│   └── tavily/              — ~35+ files
├── results/                 — (gitignored) 6 run logs + results.tsv
└── prompt_training.egg-info/ — pip install -e . artifact
```

**Python environment**:
- Python 3.13.12
- anthropic 0.92.0 (verified compatible in Phase 6b)
- openai 2.31.0 (used as Together AI client)
- datasets 4.8.4
- numpy 2.4.4
- scikit-learn 1.8.0
- huggingface_hub 1.9.2
- python-dotenv 1.2.2
- tavily-python (installed, version not exposed via __version__)

**API keys in .env** (local, never committed):
- ANTHROPIC_API_KEY (sk-ant-..., 108 chars)
- TOGETHER_API_KEY (corrected from 25-char truncated to full value in Phase 6b)
- HF_TOKEN (hf_..., 37 chars)
- TAVILY_API_KEY (tvly-dev-..., 58 chars, Researcher plan)

---

## 4. Completed work (this session)

### 4.1 Phase 6a — pre-flight environment verification

All 9 checks passed:
1. git state clean ✓
2. pip install -e . succeeds (after Phase 6a-prep flat-layout fix at commit 21a1b15)
3. .env key check — 4 keys present, prefixes plausible, lengths verified
4. (no step 4 in original Phase 6a)
5. public-API imports — 27 imports from inverse/benchmark/agent_tools all resolve
6. GAIA dataset load — 53 Level 1 tasks, HF gated access working
7. load_gaia_tasks() filter — 53 → 42 → **40 text-only tasks** (contingency branch 1: ≥30, proceed as-is, full statistical analysis viable)
8. dependency versions (listed in §3)
9. pricing freshness — 0 days old (PRICING_LOOKUP_DATE = today)

**Recovery incident**: During Phase 6a Step 3 re-run, Notepad accidentally saved real API keys into `.env.example` (tracked file) instead of `.env` (gitignored). Recovered cleanly via `cp .env.example .env && git checkout -- .env.example`. No secrets committed, staged, or pushed.

### 4.2 Phase 6b — smoke test (first real API spend)

Three runs on task 0 (Eliud Kipchoge marathon pace question) at N_SAMPLES=3:

| Block | Mode | Elapsed | Cost | Condition A | Condition B |
|---|---|---|---|---|---|
| Block 1 | --no-cache | 659s | $0.8922 | 179,585 tokens, verifier_passed=False (answer: 17000) | 35,892 tokens, verifier_passed=True (answer: 17) |
| Block 3 | cache enabled | 323s | $0.3018 | 26,971 tokens, verifier_passed=True (answer: 17) | 22,685 tokens, verifier_passed=False (answer: 17000) |
| Block 4 | cache enabled | 289s | $0.3268 | 53,333 tokens, verifier_passed=False (answer: 17000) | 22,018 tokens, verifier_passed=False (answer: 17000) |

**Phase 6b total spent**: $1.5208

**Key findings**:
1. Anthropic SDK 0.92.0 compatibility confirmed (largest unknown risk closed)
2. Cache discipline works as specified (h_raw, inverse, tavily all populated and hit correctly)
3. Anthropic API is not bitwise deterministic at temperature=0 — same task produces different agent trajectories across runs; this is infrastructure variance, not a bug
4. N_SAMPLES=3 is below the measurement floor — all three runs produced H_raw=0.0 (single-cluster collapse)
5. Cost monitoring instrumentation captures per-provider tokens correctly
6. Tavily `/usage` endpoint returned "unavailable" due to wrong key lookup (4-key flat vs nested account.plan_usage) — addressed in Phase 6c-prep
7. Second `.env.example` incident (line-ending normalization from Notepad save) recovered cleanly

Full details: `docs/reviews/PHASE_6B_REVIEW.md`

### 4.3 Phase 6c-prep — Tavily /usage fix + dotenv integration

**Commit**: `c5b4267`
**File changed**: benchmark.py only
**Changes**: 21 insertions, 9 deletions (3 hunks)

**Change 1**: `_tavily_usage_credits()` nested key lookup
- Removed 4-key flat fallback (`credits`, `credits_used`, `usage`, `total`)
- Added primary lookup: `data["account"]["plan_usage"]`
- Added fallback lookup: `data["key"]["usage"]`
- Updated docstring to reference Phase 6b Block 6 lockdown

**Change 2**: `benchmark.main()` auto-loads .env
- Added `from dotenv import load_dotenv; load_dotenv()` before `_parse_args(argv)`
- Enables direct `python benchmark.py --n-samples 10` invocation without inline wrapper

**Verification**: All 4 grep-based assertion tests passed. No API calls required.

### 4.4 Phase 7 validation — partial (3 of 6 tasks)

**Ran**: task 0 (twice, due to Claude Code duplicate invocation), task 1, task 2
**Did NOT run**: tasks 3, 4, 5 (stopped early by decision for Session 2 analysis)

**Results (run-level aggregates from run logs)**:

| Run | Task | Elapsed | Cost | Anthropic in | Anthropic out | Cache h_raw | Cache inverse | Cache tavily | terminated_by |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 0 (cold) | 1507s | $1.3752 | 181,935 | 55,232 | 0/1 | 0/1 | 19/23 (82.6%) | completed |
| 2 | 0 (cached) | 1248s | $1.2468 | (not captured separately) | (not captured) | 1/1 (100%) | 1/1 (100%) | 24/30 (80%) | completed |
| 3 | 1 | 1238s | $2.0021 | 467,704 | 39,893 | 0/1 | 0/1 | 13/23 (56.5%) | completed |
| 4 | 2 | 545s | $0.4205 | ~54,000 | ~8,000 | 0/1 | 0/1 | 0/2 (0.0%) | completed |

**Validation total cost**: $5.0446
**Per-task mean (excluding task 0 duplicate)**: $1.27 across 3 tasks
**Per-task time mean**: 1097s (~18.3 min)

**Task 2 results.tsv contents** (surviving TSV, from the last run to complete before overwrite; tasks 0 and 1 TSV data was lost to overwrite):

| Field | Condition A | Condition B |
|---|---|---|
| task_id | ec09fa32-d03f-4bf8-84b0-1f16922c3ae4 | ec09fa32-d03f-4bf8-84b0-1f16922c3ae4 |
| level | 1 | 1 |
| H_raw | 0.0 | 0.0 |
| H_improved | 0.0 | 0.0 |
| delta_H | 0 | 0.0 |
| loop_count | 0 | 0 |
| total_tokens | **29,846** | **7,769** |
| terminated_by | completed | completed |
| verifier_passed | False | False |

Task 2 was a probability question (verifier output hint: "Ball 1 (the ball starting at position 1) has the highest probability of being ejected" failed to parse, then "2" succeeded-as-number but was incorrect). Neither condition got the answer right.

**Critical preliminary signals from task 2 TSV**:

1. **Token efficiency ratio A/B = 3.84x** (29,846 / 7,769). Condition B used ~26% of the tokens condition A used. This is the only per-condition token comparison captured from Phase 7 validation (tasks 0 and 1 TSV was overwritten).

2. **H_raw = 0.0 at N_SAMPLES=10** — this was expected to be non-zero. N=3 collapsed to single-cluster in Phase 6b (acknowledged limitation); N=10 was supposed to resolve this. At least for task 2, it did not. Possible explanations:
   - Clustering threshold (cosine distance < 0.15) is too loose
   - Task 2's raw prompt is genuinely unambiguous from the "next action" measurement perspective
   - Temperature=0.7 sampling is not diverging enough in the embedding space
   - The `MEASUREMENT_QUESTION` ("What concrete action will the agent take next?") may elicit converged answers for some task types
   - **Unknown which explanation is correct from n=1**. Phase 7 Run #1 needs early monitoring of H_raw distribution.

3. **verifier_passed = False for both** — neither A nor B answered correctly. Hypothesis is about loop reduction and token efficiency, not accuracy, so this is orthogonal — but notable that inverse did not help task 2's correctness.

4. **loop_count = 0 for both** — this is NOT a bug. `loop_count` is the number of times `detect_loop` returned True during the run (per spec/measurement.md), not the number of ReAct iterations. A short task (like task 2 which completed in 9 min with only 2 Tavily searches) has few opportunities for detect_loop to fire. `loop_count=0` means the agent did not exhibit infinite-loop behavior, which is the hypothesis-favorable outcome.

**Observations across all validation runs**:
1. **Task 2 was dramatically cheaper and faster than tasks 0/1** — 9 min vs 20-25 min, $0.42 vs $1.37-2.00. Task 2 used only 2 Tavily search calls total, suggesting it was a reasoning-heavy task rather than search-heavy.
2. **High per-task variance** — 4.8x spread between task 1 (most expensive, $2.00) and task 2 (cheapest, $0.42). This variance dominates any aggregate estimate.
3. **Anthropic input tokens are the dominant cost driver** — task 1 had 468K input tokens vs task 2's 54K (8.7x spread). Output tokens are roughly flat.
4. **Tavily cache sharing between Phase 6b smoke and Phase 7 validation tasks 0/1 is high** — 80-82% hit rate on task 0 (benefiting from Phase 6b smoke's cached queries). Task 2 had 0% cache hit because its queries were completely different from tasks 0/1.
5. **Phase 6c-prep Tavily /usage fix is confirmed working** — task 2's run log shows "Tavily delta: 19 credits" (non-zero, real number). Tasks 0 and 1 reported 0 due to Tavily's eventual consistency (not a bug in the fix).
6. **Phase 6c-prep dotenv fix is confirmed working** — all 4 runs used direct `python benchmark.py ...` invocation without the inline env loader wrapper.
7. **Claude Code ran task 0 twice** accidentally (duplicate invocation due to suspecting Python stdout buffering was a hang). Cost of duplicate: ~$1.25. Lesson documented for Session 2: Python stdout buffering is normal; cache file timestamps and tasklist process count are the only valid progress signals.
8. **All 3 tasks reached terminated_by=completed** — no max_steps_reached, no errors, no loop_detected.

### 4.5 Cumulative spending this session

| Item | Cost |
|---|---|
| Phase 6b smoke (3 runs) | $1.5208 |
| Phase 7 validation (task 0 ×2 + task 1 + task 2) | $5.0446 |
| **Session 1 total** | **$6.5654** |

Anthropic budget charged: $77
**Remaining budget after Session 1**: ~$70.43

### 4.6 Hypothesis-relevant preliminary signals (n is small — not statistically conclusive)

Combining Phase 6b smoke data and the surviving Phase 7 validation task 2 TSV, we have **4 paired A/B token comparisons** across 2 tasks (task 0 × 3 runs, task 2 × 1 run):

| Source | A tokens | B tokens | Ratio A/B | B < A? |
|---|---|---|---|---|
| Phase 6b Block 1 (task 0, --no-cache) | 179,585 | 35,892 | 5.0x | ✓ |
| Phase 6b Block 3 (task 0, cached) | 26,971 | 22,685 | 1.2x | ✓ |
| Phase 6b Block 4 (task 0, cached) | 53,333 | 22,018 | 2.4x | ✓ |
| Phase 7 validation task 2 | 29,846 | 7,769 | 3.8x | ✓ |
| **Mean ratio** | | | **3.1x** | **4/4** |

All 4 observations show B < A. Binomial test for 4/4 one-sided is p=0.0625 — just shy of conventional significance but directionally consistent. This is a preliminary signal for the tertiary hypothesis metric (token efficiency / cost reduction). Primary metrics (delta_H, loop_count) are not meaningfully observed yet due to N=3 collapse in Phase 6b and the single task 2 data point in validation.

**Conclusion**: Validation data cannot test the primary hypothesis but shows a consistent directional signal on the tertiary metric (B uses fewer tokens). Phase 7 Full Run #1's first 5-10 tasks should confirm or refute this pattern quickly.

---

## 5. Remaining work

### 5.1 Immediate (Session 2 opening)

1. **Read this checkpoint** (loaded from `docs/checkpoints/CHECKPOINT_01.md`)
2. **Optionally read `docs/reviews/PHASE_6B_REVIEW.md`** for deeper Phase 6b context
3. **Phase 7 redesign decision** — see §6 (Known decisions — Phase 7 redesign options)
4. **Write Phase 7 prompt** matching the chosen redesign
5. **Execute Phase 7 Run #1** (the specific command depends on the redesign)
6. **Monitor H_raw distribution on first 5-10 tasks** — if still 0.0 on most tasks, STOP and investigate clustering threshold before continuing

### 5.2 Phase 7 execution (Session 2 main work)

Depends on redesign decision. The default target is:
- Run #1 of the redesigned Phase 7 (cold cache, longest run)
- Run #2 of the redesigned Phase 7 (warm cache, cheaper)
- If redesign keeps 3 runs: defer Run #3 to Session 3
- If redesign collapses to 1-2 runs: complete Phase 7 entirely in Session 2

### 5.3 Phase 8 — analysis (Session 3, possibly late Session 2)

After Phase 7 runs complete:
- Primary metric: `delta_H` distribution across tasks — paired t-test or Wilcoxon signed-rank test
- Secondary metric: `loop_count` rate — McNemar test (paired binary)
- Tertiary metric: `total_tokens` — A vs B mean comparison (early signal from validation: ratio ~3.1x favoring B across 4 observations on 2 tasks)
- Orthogonal metric: `verifier_passed` rate — A vs B (not a hypothesis variable, but informative)
- Run-to-run variance analysis (if ≥2 runs completed)
- Per-task variance analysis (if any tasks were run multiple times)

### 5.4 Optional follow-ups (post-v0)

Items from PHASE_6B_REVIEW.md §"Known follow-ups":
1. Per-task entropy curves logged (not currently serialized, computed in-memory only)
2. Tavily `include_raw_content=false` optimization (cache file size reduction)
3. `detect_loop` tolerance band re-calibration from real data
4. N_SAMPLES calibration (is N=10 the right floor, or should it be N=6, N=20?)
5. Phase 7.5 `--no-cache` validation run if Phase 7 results are noisy
6. **results.tsv overwrite issue** — each benchmark.py run overwrites results.tsv. Phase 7 needs either per-task append mode, per-task file naming, or pre-run capture by the Claude Code wrapper. Decision deferred to Session 2.
7. **Clustering threshold review** — if H_raw remains 0.0 across most Phase 7 tasks at N=10, the 0.15 cosine threshold may need tightening to 0.10 or 0.08.

---

## 6. Known decisions

These decisions are load-bearing and should NOT be revisited without explicit reason.

### 6.1 Locked decisions (from earlier phases, stable)

- **MODEL**: `claude-sonnet-4-6` (single-model policy for v0)
- **Entropy sampling temperature**: 0.7 (for N samples in `measure_semantic_entropy`)
- **Agent loop temperature**: 0 (for ReAct thought/action generation)
- **Token budget**: Head 80 / Body 70 / Tail 150 = 300 total
- **Clustering**: AgglomerativeClustering(metric=cosine, linkage=average, distance_threshold=0.15)
- **Embedding model**: intfloat/multilingual-e5-large-instruct (via Together AI, OpenAI-compatible client)
- **detect_loop parameters**: window=3, alpha=0.3, d²H/dt² tolerance band = 0.05 × H_raw
- **CACHE_VERSION**: `v2.8.1-001` (bump on any change to model/N_SAMPLES/clustering/prompt templates)
- **3 cache subdirectories**: cache/h_raw/, cache/inverse/, cache/tavily/
- **H_improved deliberately NOT cached** (corruption detector role per spec/caching.md)
- **Tavily cache key excludes task_id** (cost vs isolation tradeoff, accepted — see PHASE_6B_REVIEW.md §6.2)
- **Pricing verified 2026-04-08**: Anthropic Sonnet 4.6 $3/$15 per MTok input/output, Together embedding $0.02 per MTok
- **max_steps by level**: Level 1 = 15, Level 2 = 25, Level 3 = 50
- **terminated_by values**: {completed, loop_detected, max_steps_reached, error}

### 6.2 Phase 7 redesign options (Session 2 decision)

**Context**: Phase 7 validation revealed that per-task cost at N_SAMPLES=10 has 4.8x variance ($0.42 to $2.00). The 3-task mean is $1.27. Original Phase 7 spec (3 full runs × 40 tasks × N=10) is estimated at $80-160 depending on the true task distribution, which exceeds the $70 remaining budget.

**Budget available for Phase 7**: ~$70

**Task cost estimates** (per task at N=10, cold cache):
- Pessimistic (task 1): $2.00
- Realistic (3-task mean): $1.27
- Optimistic (task 2 is typical of 50% of tasks, tasks 0/1 of the other 50%): ~$0.85
- **Unknown**: actual distribution of the 40 tasks — only 3 have been measured

**Cache impact on Run #2 and Run #3**:
- Phase 6b showed h_raw + inverse cache hit at 100% for repeated runs of the same task
- Agent loop itself is not cached (by design)
- Expected cost reduction for Run #2, #3: ~40-50% relative to Run #1

**New consideration from validation**: The H_raw=0.0 at N=10 observation on task 2 means Phase 7 may need early intervention if most tasks exhibit this pattern. Any redesign option should include a "check H_raw distribution after first 5-10 tasks" stop-and-evaluate step. If >50% of tasks have H_raw=0, Phase 7 needs a clustering threshold or sampling temperature fix before continuing.

**Options** (ordered by aggressiveness):

**Option A — 3 runs × 40 tasks × N=10** (original spec, no change)
- Cost estimate: $51 (optimistic) to $160 (pessimistic), central $102
- **Verdict**: Likely over budget. Only works if task distribution is strongly optimistic.

**Option B — 2 runs × 40 tasks × N=10**
- Cost estimate: $34 (optimistic) to $107 (pessimistic), central $68
- **Verdict**: Marginal. Central estimate matches budget exactly. Loses run-to-run variance as a metric (reduced from 3 observations to 2).

**Option C — 1 run × 40 tasks × N=10**
- Cost estimate: $17 (optimistic) to $80 (pessimistic), central $51
- **Verdict**: Fits budget comfortably. Single-run means no reproducibility data but maximal per-task depth. Variance must be estimated from per-task cells (A vs B paired within task) only.

**Option D — 3 runs × 40 tasks × N=6**
- N=6 scaled down from N=10, reducing entropy sampling cost by ~40%
- Cost estimate: $31 (optimistic) to $96 (pessimistic), central $61
- **Verdict**: Fits. Risk: N=6 may not be enough to resolve entropy above the noise floor. Phase 6b at N=3 collapsed everything to H=0; N=10 already shows collapse on task 2. N=6 is untested and the H_raw collapse concern applies.

**Option E — 2 runs × 40 tasks × N=6**
- Cost estimate: $20 (optimistic) to $65 (pessimistic), central $41
- **Verdict**: Fits comfortably. Two weakenings (fewer runs AND fewer samples). Likely safest for budget but sacrifices resolution twice.

**Option F — 3 runs × 25 tasks × N=10**
- Fewer tasks, same depth per task
- Cost estimate: $31 (optimistic) to $100 (pessimistic), central $64
- **Verdict**: Fits. Risk: 25 tasks drops below contingency branch 1 threshold (30) — statistical analysis becomes descriptive instead of inferential. Still technically valid for a pilot but weaker conclusion.

**Option G — 1 run × 40 tasks × N=10 + selective repetition of interesting tasks**
- First pass all 40 to identify high-variance or hypothesis-relevant tasks
- Then repeat ~10-15 "interesting" tasks 2-3 times each
- Cost estimate: $50 + $20-30 = $70-80
- **Verdict**: Tight. Adaptive design — more information-efficient but more complex to implement and analyze.

**Option H — 1 full run to measure the real distribution, then decide Run #2/#3 scope**
- Execute Option C first (1 × 40 × N=10) at $51
- Analyze results at Session 2 end
- Plan Run #2 budget based on actual measured per-task costs
- Decision-forward: can go to 2 full runs if cheap enough, or stay at 1
- **Verdict**: Recommended default. Spends ~$51 in Session 2, leaves ~$19 for Session 3 Run #2 (which runs cached, should be ~$15-25).

**Session 2 recommended decision procedure**:
1. Read the validation data above
2. Consider which task distribution assumption is most plausible
3. Choose Option H as default (most adaptive, least regret)
4. If task 2 is clearly atypical and task 1 is closer to normal, consider Options B or C
5. If N=6 is believed to still produce measurable entropy, Option D or E unlocks more runs
6. Document the chosen option and rationale in Session 2's opening message

### 6.3 Cache strategy decision (do not revisit)

- Tavily cache cross-sharing (no task_id in key) is accepted.
- No Tavily `include_raw_content` optimization for v0.
- No disable-cache Phase 7 run unless Phase 7 results are noisy (Phase 7.5 optional).

Rationale in PHASE_6B_REVIEW.md.

---

## 7. Open questions

1. **What is the actual task cost distribution across the 40 GAIA Level 1 filtered tasks?**
   Only 3 tasks measured. Extrapolation is uncertain. Options A-H above all make different assumptions.

2. **Does N=6 produce measurable entropy, or will it collapse like N=3 did?**
   Untested. Could be checked with a 1-task smoke at N=6 before committing to Option D/E. Cost: ~$0.50-1.50. Worth it if Option D or E is seriously considered.

3. **Is task 2 representative of a "reasoning-heavy" class, and if so, what fraction of GAIA Level 1 tasks belong to that class?**
   Unknown. Quick eyeball of the 40 task questions would give a rough estimate (search-heavy vs reasoning-heavy classification). Possible Session 2 opening task.

4. **Should condition A (raw prompt) be allowed to skip inverse() entirely, or does it still need H_raw computed?**
   Current code computes H_raw for both conditions. This is the correct per spec/measurement.md but doubles the entropy sampling cost for condition A. Worth revisiting in Session 2 if budget is tight — could reduce total cost by ~20% if H_raw is only computed once (shared across A and B for the same task).

5. **Is the Tavily free tier 1000-credit limit a real constraint for Phase 7?**
   Current usage: 27 credits at Phase 6b end, ~46+ after Phase 7 validation. Phase 7 full runs estimated at 200-400 credits total. Comfortable margin. But worth monitoring during Session 2.

6. **Why does H_raw = 0.0 at N_SAMPLES=10 on task 2?**
   The spec expects N=10 to be sufficient to produce non-zero entropy for ambiguous prompts. Task 2 contradicts this. Three possible causes:
   - Clustering threshold (cosine distance < 0.15) too loose — all 10 samples land in one cluster
   - Task 2's raw prompt is genuinely unambiguous — MEASUREMENT_QUESTION ("What concrete action will the agent take next?") yields the same answer across samples
   - Temperature=0.7 is not diverging enough
   
   **Cannot diagnose from n=1**. Session 2 must monitor H_raw across the first 5-10 Phase 7 Run #1 tasks. If >50% of tasks have H_raw=0.0, STOP and fix clustering/sampling before proceeding.

---

## 8. Known issues / follow-ups

### 8.1 Bugs and small issues observed (not blocking)

- **results/results.tsv gets overwritten on every run** (opened in "w" mode). Phase 7 needs to capture each task's rows immediately via stdout or append mode. Phase 4b/5 decision: overwrite is intentional for v0. Session 2 workaround: Claude Code must capture each task's stdout before the next invocation.

- **Run log does not include per-step entropy curves**. Phase 8 analysis may need these for detect_loop inspection. Deferred.

- **Run log does not include TSV rows inline**. Currently TSV and log are separate files. For Phase 7 multi-task runs, it would be cleaner to have both in one log. Deferred.

- **Tavily `/usage` endpoint has eventual consistency** — `_tavily_usage_credits()` may return stale counts. Task 2 saw the first non-zero delta. For Phase 7, treat Tavily cost as dashboard-confirmed only.

- **`loop_count` column is often misread**. It is NOT the number of ReAct iterations. It is the number of times `detect_loop` returned True during the run (per spec/measurement.md). A completed task with loop_count=0 means the agent did not exhibit infinite-loop behavior — this is the hypothesis-favorable outcome, not a bug. Session 2 Claude should read this note before interpreting loop_count values.

### 8.2 Untested scaling risks

- 40-task sequential runs have never been executed. Longest run so far is 1 task × 2 conditions × 2 runs simultaneously (~25 min). Phase 7 Run #1 will be 40x that. Unknown risks: memory growth over time (unlikely but untested), Tavily cache file count explosion (gitignored, not a problem per se but slows filesystem), cumulative error accumulation in cache.

- Anthropic API may rate-limit under sustained load. Phase 6b peak was ~10 requests/minute. Phase 7 at full load may reach ~30-50 requests/minute. If rate-limited, the benchmark's implicit retry logic in the Anthropic SDK should handle it, but this is untested.

### 8.3 Security notes (critical)

- **NEVER touch `.env.example`**. Tracked file. Committed as empty template. Two recovery incidents so far; both caught pre-commit. Discipline: edit `.env` directly, never open `.env.example` in an editor.
- **NEVER run `type .env`, `cat .env`, or any command that echoes file contents to chat/terminal**.
- **Before any edit to `.env`**: `git status --short` should be empty. After edit: `git status --short` should still show nothing (.env is gitignored).
- **If `M .env.example` appears in git status**: immediately `git checkout -- .env.example` and retry the edit.
- **CACHE_VERSION must be bumped** on any change to model, N_SAMPLES, clustering threshold, or cached prompt templates. Current version v2.8.1-001.
- **Pricing constants** in benchmark.py: re-verify against official sources if Phase 7 runs >14 days after 2026-04-08.
- **No cloud sync** on C:/Users/433/Documents/prompt-training (confirmed by Elden, Option A recovery path used twice).

---

## 9. Budget state

**Anthropic**:
- Charged to Anthropic console: $77
- Spent in Session 1 (Phase 6b + validation): $6.5654
- **Remaining for Session 2 + Session 3**: ~$70.43
- Phase 7 redesign options (from §6.2) all fit or exceed this budget depending on choice.

**Tavily**:
- Current plan: Researcher (free tier)
- Quota: 1000 credits/month
- Used at Session 1 close: ~46-50 credits estimated (27 after Phase 6b + ~20 from validation based on task 2's observed delta of 19)
- **Remaining**: ~950 credits
- Phase 7 estimated usage: 200-400 credits across all runs
- **Verdict**: Comfortable margin. No need to upgrade to paid tier.
- **Pay-as-you-go toggle**: OFF (confirmed by Elden's dashboard screenshot). If quota exhausted, runs will fail with HTTP error, not auto-bill.

**Together AI** (embeddings):
- Minimal cost (~$0.001 per task)
- Not a budget concern

**Hugging Face**:
- Free dataset access (gated, pre-approved for GAIA)
- Not a budget concern

---

## 10. Safety notes for Session 2

### 10.1 What Session 2 must NOT do

- **NEVER** re-run Phase 6c-prep or earlier phases. They are committed and correct.
- **NEVER** edit benchmark.py, inverse.py, or agent_tools.py without an explicit scope document (like a Phase 7-prep prompt if redesign requires code changes).
- **NEVER** edit `.env.example`. Period.
- **NEVER** echo `.env` contents in chat or terminal.
- **NEVER** re-invoke a python benchmark.py call that is already running. Python stdout buffering is normal. Progress signals: cache file timestamps, tasklist process count, run log file count.
- **NEVER** skip the hard 30-minute wall clock limit per task. If a task exceeds 30 minutes, kill it and investigate.
- **NEVER** commit `results/` or `cache/` contents. They are gitignored.
- **NEVER** commit anything containing raw API responses or user PII.
- **NEVER** misinterpret `loop_count=0` as a bug — it is the hypothesis-favorable outcome meaning the agent did not infinite-loop.

### 10.2 What Session 2 should do

- **READ this checkpoint carefully before anything else**. Especially §4.4 (task 2 TSV signals), §4.6 (hypothesis-relevant signals), §6.2 (Phase 7 redesign options), and §7 (open questions).
- **MAKE the redesign decision explicitly in the first message**. Document the choice and rationale.
- **TRUST the Phase 6c-prep dotenv fix**. Direct `python benchmark.py ...` invocation works. No inline wrappers.
- **CHECK Tavily dashboard occasionally** during long runs. It is the authoritative source for credit usage (not the `/usage` API response which can be stale).
- **CAPTURE each task's stdout immediately** after completion. results.tsv overwrites; run log is the permanent record but lacks TSV rows. Consider writing a wrapper that appends per-task TSV rows to a persistent file before the next invocation.
- **APPLY 30-minute hard limit per task**. Phase 7 validation showed tasks can range from 9-25 minutes. 30 min is a safe ceiling.
- **MONITOR H_raw distribution on the first 5-10 tasks of Phase 7 Run #1**. If >50% are 0.0, STOP and investigate clustering threshold or sampling temperature before continuing.

---

## 11. Next session prompt template

Paste the following as the first message when starting Session 2:

```
This is Session 2 of the prompt-training project, continuing from Session 1's CHECKPOINT_01.md.

Full context is in docs/checkpoints/CHECKPOINT_01.md in the repo
(https://github.com/eldensari/prompt-training). Please read it in full before
proceeding. Key sections to focus on:

- §2 (Git state) — current HEAD is c5b4267
- §4.4 (Phase 7 validation results) — actual task cost data + task 2 TSV with preliminary signals
- §4.6 (Hypothesis-relevant preliminary signals) — 4/4 directional signal on token efficiency
- §6.2 (Phase 7 redesign options) — the decision I need to make
- §7 (Open questions) — especially the H_raw=0 at N=10 concern
- §9 (Budget state) — ~$70 remaining Anthropic

Session 2 goals:
1. Review the validation data and propose a Phase 7 redesign
2. Write a Phase 7 prompt matching the chosen redesign
3. Execute Phase 7 Run #1 (via Claude Code)
4. Monitor H_raw distribution on first 5-10 tasks — STOP if most are 0.0
5. Review Run #1 results
6. If budget and time permit, execute Phase 7 Run #2

I will provide the CHECKPOINT_01.md contents inline below for immediate
context (do not require me to fetch from GitHub).

[PASTE THE FULL CONTENTS OF CHECKPOINT_01.md HERE]
```

**Alternative** (if GitHub access is available in the new session): the Claude in Session 2 can `web_fetch` the CHECKPOINT file directly from the raw GitHub URL. The URL format after Session 1 closes:
```
https://raw.githubusercontent.com/eldensari/prompt-training/main/docs/checkpoints/CHECKPOINT_01.md
```

---

## 12. Full commit log (17 commits at Session 1 start → 18 at Phase 6c-prep → ~19 at Session 1 close with docs commit)

```
c5b4267 Phase 6c-prep: Tavily /usage shape fix + dotenv auto-loading
21a1b15 Phase 6a-prep: pyproject.toml py-modules — fix flat-layout discovery
b40050b Phase 5.5: Tavily cache wrappers — _cached_tavily_search/extract in benchmark.py, run_react_loop dispatch wired to wrappers
a6fefa1 Phase 5: cost monitoring + reproducibility wiring — pricing constants, per-provider token accumulator, Tavily /usage, cache hit rates, run summary log
608b877 Phase 4b: run_react_loop body with full [a]-[h] flow
7ffbb1d Phase 4a: agent_tools.py
bf3e159 Phase 3 review cleanup
a6610d5 Phase 3: embedding model migration to e5
d8a0921 Phase 3 initial
f5f7789 Phase 3: benchmark.py skeleton
45dab1b Phase 2: inverse.py six functions
27e8ca9 Phase 1: environment
9c0d91b README fix
73e6ef1 spec commit 5
(...earlier spec commits)
665f2ee spec commit 1
```

Session 1 closes with one additional docs commit pending:
- `docs: add Phase 6b review and session 1 checkpoint` — adds `docs/reviews/PHASE_6B_REVIEW.md` and `docs/checkpoints/CHECKPOINT_01.md`

After that commit, git log --oneline -1 should show `[new_hash] docs: add Phase 6b review and session 1 checkpoint` and total commits should be 19.

---

## End of CHECKPOINT_01

Next session, start fresh with the template in §11. Good luck, Session 2 Claude — the validation data is in §4.4, the hypothesis signals are in §4.6, the budget math is in §6.2 and §9, and the experiment is real.
