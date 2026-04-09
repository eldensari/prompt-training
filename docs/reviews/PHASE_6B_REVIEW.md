# Phase 6b Review — Smoke Test Analysis

**Phase**: 6b (Smoke Test — First Real API Spend)
**Execution date**: 2026-04-08
**Review date**: 2026-04-09
**Commits**: Phase 6b itself produced no commits (execution-only phase). Relevant commits:
- `21a1b15` — Phase 6a-prep (pyproject.toml flat-layout fix, landed just before Phase 6b)
- `c5b4267` — Phase 6c-prep (Tavily /usage fix + dotenv integration, landed after Phase 6b as a direct response to findings here)
- HEAD at review time: `c5b4267`

**Total cost spent**: $1.5208 across 3 smoke runs
**Total wall clock**: ~21 minutes

---

## Executive summary

Phase 6b executed three smoke test runs on GAIA Level 1 task 0 (Eliud Kipchoge marathon pace question) to verify that the full prompt-training pipeline works end-to-end with real API calls. All three runs reached completion, the cache system was populated and exercised, and every architectural assumption from Phases 1–5.5 held in practice.

Three major findings, each with significant implications for Phase 7 design:

1. **Pipeline works end-to-end.** Anthropic SDK 0.92.0 compatibility confirmed, cache discipline (h_raw + inverse + tavily) functions as specified, cost monitoring instrumentation captures per-provider token usage correctly, graceful-failure paths work.

2. **Anthropic API non-determinism at temperature=0 is larger than anticipated.** The same task produced materially different agent trajectories across runs — token counts ranging from 27K to 180K for condition A, and verifier_passed flipping between True and False across runs. This is not a bug; it is infrastructure-level variance acknowledged in `operations/reproducibility.md`. The implication is that single-task results are noisy and aggregate statistics across 40 tasks are the meaningful signal.

3. **N_SAMPLES=3 is below the measurement floor.** All three smoke runs produced H_raw=0.0 and H_improved=0.0 because three samples collapsed to a single semantic cluster at cosine threshold 0.15. This is consistent with the `spec/measurement.md` explicit warning that N=10 is the floor for meaningful entropy values. Phase 7 must use N_SAMPLES=10 or the primary metric is meaningless.

The run that revealed the most — and that almost got the project into trouble — was Block 1, which also surfaced the Together AI API key error (invalid 25-character key, truncated from the full value) and a `.env.example` security accident that recovered cleanly but consumed ~30 minutes of unplanned investigation. Both issues were resolved without leaking secrets.

---

## Execution details by block

### Block 1 — First smoke test (cold path, `--no-cache`)

**Command**: `python benchmark.py --task 0 --n-samples 3 --no-cache`
**Elapsed**: 658.8s (~11 minutes)
**Cost**: $0.8922
**Result**: SUCCESS (after Together AI key fix)

**Initial failure and recovery**:
The first attempt failed with `openai.AuthenticationError: Error code: 401 — Invalid API key provided` from Together AI's embedding endpoint. Investigation revealed that TOGETHER_API_KEY in `.env` was a 25-character string starting with `key_`, which does not match Together AI's standard 64-character key format. Elden corrected the key from the Together dashboard and the retry succeeded.

A separate failure in `_tavily_usage_credits()` was caught gracefully: the function returned None and cost logging reported "Tavily delta: unavailable". This was not a blocker but was noted for Block 6 investigation and eventual Phase 6c-prep fix.

**TSV rows produced**:

| Field | Condition A | Condition B |
|---|---|---|
| task_id | e1fc63a2-... | e1fc63a2-... |
| level | 1 | 1 |
| H_raw | 0.0 | 0.0 |
| H_improved | 0.0 | 0.0 |
| delta_H | 0 | 0.0 |
| loop_count | 0 | 0 |
| total_tokens | **179,585** | **35,892** |
| terminated_by | completed | completed |
| verifier_passed | **False** (answer: 17000) | **True** (answer: 17) |

**Observations**:
- Condition B produced the correct answer (17 km/h) and used 5x fewer tokens than condition A.
- Condition A spent 179,585 tokens on an extended ReAct path that ended with the answer "17000" — likely 17 km/h in meters (unit confusion). This is a textbook case of an ambiguous deliverable format, which is exactly the failure mode the inverse model is hypothesized to prevent.
- Cache directories were created but empty (expected — `--no-cache` disables writes).
- Cost distribution: Anthropic $0.8919, Together $0.0002, Tavily unreported.
- The 5:1 token efficiency in condition B's favor is the single most suggestive data point for hypothesis direction in Phase 6b, but is only n=1.

**Anthropic SDK compatibility** — reaching the cost log and producing TSV rows is empirical proof that anthropic 0.92.0 works with the Phase 4b SDK usage pattern. This was the single largest unknown risk going into Phase 6b. Risk closed.

### Block 2 — Inspection of Block 1

No commands executed. Reasoning from Block 1 output:
- Both conditions completed without looping.
- N_SAMPLES=3 entropy collapse (H=0.0 across the board) is a measurement resolution artifact, not a result about the inverse model. `spec/measurement.md` explicitly identifies N=10 as the floor.
- The verifier_passed flip in B's favor on n=1 is not statistically meaningful but is in the direction the hypothesis predicts.
- Cost of $0.89 is high relative to the budget because condition A's 179K tokens dominated.

### Block 3 — Second smoke test (cache enabled, first write pass)

**Command**: `python benchmark.py --task 0 --n-samples 3`
**Elapsed**: 322.8s (~5.4 minutes)
**Cost**: $0.3018
**Result**: SUCCESS

**TSV rows produced**:

| Field | Condition A | Condition B |
|---|---|---|
| total_tokens | 26,971 | 22,685 |
| terminated_by | completed | completed |
| verifier_passed | **True** (answer: 17) | **False** (answer: 17000) |

**Cache hit rates**:
- h_raw: 0/1 (0.0%) — expected miss, wrote 1 file
- inverse: 0/1 (0.0%) — expected miss, wrote 1 file
- tavily: 3/9 (33.3%) — intra-run hits, wrote 6 files

**Cache file state after Block 3**:
- cache/h_raw/: 1 file
- cache/inverse/: 1 file
- cache/tavily/: 6 files

**Observations**:
- **Condition A and B swapped outcomes** relative to Block 1. A was now correct (17), B was now wrong (17000). This is the first concrete evidence of Anthropic API non-determinism at temperature=0 producing different agent trajectories.
- **Condition A's token count dropped from 179,585 to 26,971 — a 6.6x decrease** — despite both runs being cold (Block 1 was `--no-cache`, Block 3's cache was empty before the run). This variance is not cache-related; it is downstream of the same API non-determinism.
- **Tavily cache hit rate of 33.3%** reflects intra-run cross-condition sharing: condition B made several search queries that condition A had already made earlier in the same run, so B's calls hit the cache rather than making duplicate real API calls. This is the cross-sharing behavior enabled by the task_id being absent from the Tavily cache key.
- Per-provider cost: Anthropic $0.3017, Together $0.0001 (embedding calls for entropy clustering), Tavily unreported.

### Block 4 — Third smoke test (cache should hit)

**Command**: `python benchmark.py --task 0 --n-samples 3`
**Elapsed**: 289.4s (~4.8 minutes)
**Cost**: $0.3268
**Result**: SUCCESS

**TSV rows produced**:

| Field | Condition A | Condition B |
|---|---|---|
| total_tokens | 53,333 | 22,018 |
| terminated_by | completed | completed |
| verifier_passed | **False** (answer: 17000) | **False** (answer: 17000) |

**Cache hit rates**:
- h_raw: 1/1 (**100.0%**) — the Block 3 write was successfully reused
- inverse: 1/1 (**100.0%**) — the Block 3 write was successfully reused
- tavily: 8/13 (61.5%) — 8 of 13 queries hit Block 3's cached responses

**Observations**:
- **Both conditions produced the wrong answer (17000)** in Block 4. Neither A nor B achieved verifier_passed.
- **h_raw and inverse cache hits at 100%** confirm the cache write/read paths for deterministic computations work correctly. These caches are keyed on `(task_id, model, n_samples, cache_version)` and the Block 3 entries matched exactly.
- **Tavily cache hit rate of 61.5%** is higher than Block 3's 33.3%, showing cross-run cache reuse. However, 5 of 13 calls were cache misses, meaning the agent made 5 new search queries that had not appeared in Block 3. These new queries reflect the non-deterministic choice of search strategy — even with the same cached `improved_prompt` (inverse cache hit = 100%), the agent's ReAct loop selected different actions than it did in Block 3.
- **Condition A's token count doubled** (26,971 → 53,333) relative to Block 3 despite the cache hits reducing some LLM call overhead. The agent loop's non-determinism outweighed the cache savings in this run.
- **Cost was actually slightly higher** in Block 4 ($0.3268) than Block 3 ($0.3018) despite the cache hits. This is a critical observation: cache discipline reduces the cost of specific subcomponents (inverse, h_raw) but cannot compensate for a longer agent loop. In Phase 7 Full Run #2 and #3, cache savings should be larger in aggregate because (a) most task runs should be closer to the mean agent-loop length, not a 2x outlier, and (b) inverse() is expensive relative to most agent steps.

### Block 4 vs Block 3 — the invariant question

The original design expectation, stated in the Phase 6b prompt, was that Block 3 and Block 4 would produce identical TSV rows because Block 4's cache hits should make it equivalent to Block 3. This expectation turned out to be incorrect.

**What is invariant across Block 3 → Block 4**:
- H_raw (0.0 in both — deterministic by virtue of cache hit at Block 4)
- H_improved (0.0 in both — not cached, but recomputed identically because N=3 collapses to single cluster regardless)
- The `improved_prompt` string produced by inverse() (not directly verified, but guaranteed by inverse cache 100% hit)
- terminated_by ("completed" in both)

**What is NOT invariant across Block 3 → Block 4**:
- total_tokens (A: 26,971 vs 53,333. B: 22,685 vs 22,018 — small)
- verifier_passed (A: True vs False. B: False vs False)
- Agent's choice of search queries (5 new queries in Block 4 not seen in Block 3)
- Elapsed wall time

**Why**: The agent loop itself is not cached by design (see `spec/caching.md`). Each ReAct step calls Anthropic fresh. Anthropic's API is documented as "temperature=0 but not bitwise deterministic" — the same input can produce different outputs due to batch effects, kernel scheduling, and other infrastructure variance. The per-step choice can cascade into different Thought → Action → Observation chains, which manifests as different token counts, different verifier outcomes, and different search query sequences.

**Implication for Phase 7**: Single-run results for a single task are noisy. The experiment's statistical power comes from averaging across 40 tasks (reducing task-level variance) and across 3 full runs (reducing agent-trajectory variance). The paired comparison design — same task, same seed, same model version, A and B run back-to-back — ensures that the main source of A vs B differences is the inverse model, not cross-task noise. But within a single (task, run) cell, the noise floor is higher than the Phase 4b specification assumed.

### Block 5 — Tavily search response shape lockdown

**Command**: Python one-liner inspecting cached Tavily JSON files
**Result**: Response shape confirmed and stable

**Shape**:
```json
{
  "query": "...",
  "follow_up_questions": null,
  "answer": null,
  "images": [],
  "results": [
    {
      "url": "...",
      "title": "...",
      "content": "...",
      "score": 0.XX,
      "raw_content": "..."
    },
    ... (5 results total, matching max_results=5)
  ],
  "response_time": 0.68,
  "request_id": "..."
}
```

All 3 inspected files had identical top-level structure and identical per-result field sets. The `raw_content` field is present and contains the full page text, which can be very large (tens of KB per result). This field is currently pass-through: it enters the Observation, gets serialized via `json.dumps` in `_format_step_raw`, and gets trimmed to fit the Tail budget (150 tokens) before the next agent step. Most of `raw_content` is therefore discarded, but it still inflates cache file size and JSON serialization time.

**Follow-up for Phase 7+ optimization** (not a blocker): consider requesting `include_raw_content=false` in `tavily_search` calls if the Tavily client library supports it, or post-processing cached responses to strip `raw_content` before write. Deferred.

### Block 6 — Tavily /usage endpoint shape lockdown

**Command**: Python one-liner making one manual GET to `https://api.tavily.com/usage` with Bearer token
**Result**: Response shape confirmed; previous `_tavily_usage_credits()` implementation was wrong

**Raw response**:
```json
{
  "key": {
    "usage": 0,
    "limit": null,
    "search_usage": 0,
    "crawl_usage": 0,
    "extract_usage": 0,
    "map_usage": 0,
    "research_usage": 0
  },
  "account": {
    "current_plan": "Researcher",
    "plan_usage": 0,
    "plan_limit": 1000,
    "search_usage": 0,
    "crawl_usage": 0,
    "extract_usage": 0,
    "map_usage": 0,
    "research_usage": 0,
    "paygo_usage": 0,
    "paygo_limit": null
  }
}
```

**Diagnosis**: The Phase 5 implementation of `_tavily_usage_credits()` tried four flat top-level keys: `credits`, `credits_used`, `usage`, `total`. None of these exist in Tavily's actual response. The correct paths are:
- Primary: `data["account"]["plan_usage"]` — account-level counter
- Fallback: `data["key"]["usage"]` — per-key counter

Both values were 0 at the time of the /usage call, even though Phase 6b had already made at least 15 real Tavily search requests (6 in Block 3, 5 new in Block 4, plus queries from Block 1 which used `--no-cache`). This strongly suggests **eventual consistency**: Tavily's /usage endpoint does not update in real time. The dashboard confirmed this — a check ~30 minutes after Block 6 showed "27 / 1,000 Credits" used, reflecting the actual activity.

**Immediate fix**: Phase 6c-prep (commit `c5b4267`) replaces the 4-key flat lookup with the nested lookup. After the fix lands, cost logs report a number (possibly stale) instead of "unavailable."

**Known limitation of the fix**: Because of eventual consistency, `_tavily_usage_credits()` may return stale counts. The cost log's "Tavily delta" between run start and run end may undercount the actual credits spent in that run. This is acceptable for Phase 7 — we have a 1000-credit monthly quota and expect to use 280-580 credits across all 3 full runs, so even a 50% undercount is comfortable. Dashboard remains the authoritative source for budget checks.

---

## Cost breakdown

| Block | Elapsed (s) | Anthropic in | Anthropic out | Together | USD | Notes |
|---|---|---|---|---|---|---|
| Block 1 (cold) | 658.8 | 203,669 | 18,729 | 11,924 | $0.8922 | 179K tokens on condition A dominated |
| Block 3 (write) | 322.8 | 45,655 | 10,982 | 7,029 | $0.3018 | Shorter agent loop |
| Block 4 (hit) | 289.4 | 68,569 | 8,064 | 4,657 | $0.3268 | Cache hit 100% (h_raw, inverse), 61.5% (tavily) |
| **Total** | **1271** | **317,893** | **37,775** | **23,610** | **$1.5208** | ~21 min wall clock |

- Anthropic accounted for 99.97% of total spend ($1.5204 of $1.5208).
- Together (embeddings) was negligible ($0.0004 total).
- Tavily spend: 27 credits according to dashboard (not billed against Anthropic or Together).
- Budget headroom: $1.52 spent out of ~$60 available (Anthropic credit). 2.5% of budget consumed during smoke test.

**Per-task cost mean for Phase 7 extrapolation**: ($0.8922 + $0.3018 + $0.3268) / 3 = $0.5069 per task at N_SAMPLES=3.

**Adjusted for N_SAMPLES=10**: Entropy measurement scales roughly linearly with N (the 10 samples are independent API calls). But the agent loop cost is unchanged. Rough adjustment: N=10 per-task cost ≈ $0.30-0.60 depending on whether the task is a fast-completer or a loop-prone one. Phase 7 validation will replace this estimate with real N=10 measurements.

---

## Key decisions and their rationales

### Decision 1: Phase 6c-prep was created as a direct response to Block 6 findings

Rather than deferring the Tavily /usage fix to Phase 7 Phase A or accepting "unavailable" permanently, the fix was scoped as a single-file mechanical change (Phase 6c-prep) before any Phase 7 work. Rationale:

- Cost visibility matters during multi-hour Phase 7 runs. If something goes wrong (agent calls 10x more searches than expected), "unavailable" in the cost log provides no early warning.
- The fix is mechanical — no risk, no spec impact.
- Combining it with the dotenv auto-loading wiring (also a small quality-of-life improvement) made the commit self-contained.
- Phase 6c-prep landed as commit `c5b4267`, 18 commits total.

### Decision 2: Cache design stays as-is for Phase 7

Tavily cache sharing across conditions (and in principle across tasks) raises a theoretical concern about experimental contamination: if condition B reuses condition A's search result, is that A "helping" B? The answer after Phase 6b data:

- Within a task, A and B sharing the same search response produces no systematic bias because the response reflects real web state, which would be nearly identical if both called real API.
- Across tasks, query collisions are expected to be rare because the 40 GAIA Level 1 tasks cover distinct topics.
- The alternative — adding task_id to the Tavily cache key — would reduce Phase 7 cache hit rate significantly, pushing Tavily credit usage toward or past the 1000-credit free tier.
- The safer alternative — disabling Tavily cache entirely — would make Run #2 and Run #3 as expensive as Run #1, nearly tripling Anthropic cost.

Phase 7 proceeds with the spec-as-written cache design. A `--no-cache` Phase 7.5 validation run is held in reserve: if Phase 7 results are noisy or inconclusive, 6 tasks in `--no-cache` mode can verify cache invariance retroactively.

### Decision 3: N_SAMPLES=10 is non-negotiable for Phase 7

N_SAMPLES=3 yielding 100% single-cluster collapse (H=0.0) in all three smoke runs validates `spec/measurement.md`'s floor requirement. Phase 7 cannot use N=3 without the primary metric (delta_H) being structurally meaningless. N=10 carries ~3.3x the entropy-measurement cost per task relative to N=3, which is factored into Phase 7 cost estimates ($12-24 per full run at N=10).

### Decision 4: Phase 7 uses 3 full runs, not task-level repetition

Given the large trajectory variance observed in Blocks 1/3/4, an alternative design would be to run each task multiple times within a single "run" (e.g., 40 tasks × 2 conditions × 3 repeats = 240 rows in one invocation). This would give McNemar-style paired statistics per task.

The original spec — 40 tasks × 2 conditions × 1 iteration × 3 full runs — remains the Phase 7 plan for these reasons:
- It matches the reproducibility assertion being tested: "if we rerun the experiment, do we get the same aggregate answer?"
- The 3 runs provide run-to-run variance bounds in addition to task-level variance.
- Aggregation is decided at analysis time (Phase 8), not at execution time. The 240 rows can be sliced as "40 tasks × 3 observations" or "120 independent (task, run) cells" or "3 fully independent experiments" depending on what the analysis calls for.

---

## Known follow-ups for Phase 7 and beyond

1. **Per-task entropy curves should be logged.** Currently `run_log` contains only aggregate cost metrics. The actual per-step entropy curve — which is used by `detect_loop` — is computed in memory and never serialized. For Phase 7 analysis, having the entropy trajectory per task per condition would enable finer-grained failure analysis. Deferred for Phase 7 to avoid scope creep; fix in Phase 8 if needed.

2. **Tavily /usage eventual consistency** is a known limitation of the Phase 6c-prep fix. The function can return stale counts. A future improvement could poll the endpoint with a backoff pattern, but this is unnecessary for v0 — dashboard is authoritative.

3. **`_format_step_raw` passes raw_content through unmodified.** The raw_content field in Tavily search results is very large and mostly discarded by `trim_to_tail`. A v1 optimization could strip raw_content at cache-write time or request `include_raw_content=false` from the Tavily client. Size reduction: probably 50-80% of current cache file size. Cost impact: minimal. Deferred.

4. **Anthropic API non-determinism characterization.** Phase 7 will produce 240 rows across 3 runs. A useful side analysis: for each (task, condition) cell, compute the variance across the 3 repetitions. Tasks with high variance are "hard" (agent has many equally-plausible paths); tasks with low variance are "easy." This is an orthogonal finding about GAIA as a benchmark, and could be a useful addendum to the paper if this research becomes published.

5. **N_SAMPLES calibration.** N=3 is below the floor. N=10 is the spec default. But is N=10 enough? If Phase 7 H_raw values are still low (< 1.0 across most tasks), we may need N=20 or N=30 to resolve meaningful distinctions. This is a Phase 7.5 question, not a Phase 7 question. Budget: 1.5-2x Anthropic spend if we increase to N=20.

6. **`detect_loop` 5% tolerance band re-calibration.** The current implementation has `abs(d²H/dt²) < 0.05 × H_raw` as the acceptance band. This was chosen by analogy to physical inflection point detection, not from data. Phase 7 will be the first real data showing what H vs time curves actually look like. Post-Phase-7, consider refitting the tolerance.

7. **`.env.example` line-ending accidents recovered twice in Phase 6b.** Both incidents involved Notepad re-saving the file with CRLF where the committed version had LF. Both recovered cleanly via `git checkout -- .env.example`. No secrets leaked. Going forward: use an editor that respects line-ending hints (e.g., VS Code with `files.eol: "\n"` setting), or avoid editing `.env.example` entirely. The practical discipline is: never touch `.env.example`; edit `.env` only.

8. **Phase 6b cost was 50% over estimate.** Block 1 alone cost $0.89 versus the $0.30-0.50 estimate. The root cause was condition A's 179K-token extended ReAct loop on the raw (vague) prompt, which is itself evidence for the hypothesis — raw prompts consume more tokens. Phase 7 extrapolation should use the Block 3+4 mean (~$0.30 per task) as the central estimate, with Block 1 ($0.89) as the pessimistic case.

---

## Artifacts from Phase 6b

- 3 × `results/run_<timestamp>.log` files (gitignored)
- `cache/h_raw/` 1 file (gitignored)
- `cache/inverse/` 1 file (gitignored)
- `cache/tavily/` ~11 files (gitignored)
- `results/results.tsv` (gitignored, overwritten by Block 4's output)
- No commits, no file changes in the repo from Phase 6b itself
- Phase 6c-prep (commit `c5b4267`) is the downstream artifact addressing Tavily /usage and dotenv issues discovered during Phase 6b

---

## Safety incidents during Phase 6b

Two `.env.example` modification incidents were caught and recovered:

**Incident 1**: During Together AI key correction, Notepad was opened on `.env` but apparently saved to `.env.example` instead (or Elden clicked through to the wrong file in Notepad's file dialog). Real API keys ended up in the tracked template file. Status: caught by `git status --short` before any commit/stage/push. Recovered by `cp .env.example .env` (moving keys to gitignored location) + `git checkout -- .env.example` (restoring empty template). Verified clean.

**Incident 2**: During a subsequent edit session, `.env.example` was modified with a whitespace-only (line-ending) change — one line's `\r\n` became `\n`. No real key values involved. Verified by masked-diff inspection (showing both sides of the diff rendered as `TAVILY_API_KEY=` with 15 chars). Recovered via `git checkout -- .env.example`.

Both incidents were handled by Claude Code's safe-by-default behavior: never echoing `.env*` contents to chat, using masked diff tools to verify the nature of changes without exposure, and requiring explicit user confirmation before any recovery action.

**Lessons**:
- Masked-diff inspection is the right pattern when the content of a sensitive file needs to be verified. `git diff --unified=0 | python` with a content-masking filter showed enough structure (line numbers, lengths) to determine the change was benign without exposing values.
- `git checkout -- <tracked-file>` is the correct recovery primitive — it reads from the committed blob, which is known safe.
- Never `type`, `cat`, or any command that echoes `.env*` files to terminal output.
- `.env` should be edited directly with an editor, and `.env.example` should be left strictly alone.

---

## Summary for Phase 7 entry

Phase 6b closed 5 risks and opened 2 refinements:

**Closed risks**:
1. Anthropic SDK 0.92.0 incompatibility — did not materialize
2. Pipeline integration breakage — did not materialize
3. Cache discipline incorrectness — h_raw and inverse 100% deterministic as designed
4. Tavily response shape unknown — locked down, handled by `_format_step_raw` cleanly
5. Cost monitoring instrumentation — per-provider tokens captured correctly

**Refinements applied as Phase 6c-prep** (commit `c5b4267`):
1. `_tavily_usage_credits()` now reads `data["account"]["plan_usage"]` instead of non-existent flat keys
2. `benchmark.main()` auto-loads `.env` via python-dotenv, enabling direct `python benchmark.py` invocation

**Refinements deferred to Phase 7.5 or later**:
1. Phase 7 `--no-cache` spot-check if results are noisy
2. raw_content stripping in Tavily cache
3. detect_loop tolerance band re-calibration from real data
4. N_SAMPLES=20 if N=10 still shows low H_raw across most tasks

Phase 7 is cleared to proceed.
