# CHECKPOINT_07 — Phase 8.1.A.Plus.1 complete, Phase 8.1.A.Plus.2 scoped
Project: prompt-training
Repository: https://github.com/eldensari/prompt-training
Local: C:/Users/433/Documents/prompt-training
Checkpoint date: 2026-04-13 (Session 7 close)
Preceding checkpoint: docs/checkpoints/CHECKPOINT_06_phase_8_1_a_complete.md
HEAD at checkpoint: 8fdbf50 (Phase 8.1.A.Plus.1: add --executor-model CLI arg (Option C: fail-loud single-task, legacy-preserving batch))

---

## 1. Framing

Session 7 was an infra-validation session for Phase 8.1.A.Plus.1 (cost-frontier hypothesis, planner=sonnet / executor=haiku) and simultaneously a discipline session where the Session 6 workflow rules (metaphor-language summaries with raw exposure at decision branches) were tested under pressure and held in most cases but failed in one specific failure mode that is now encoded in §9 as a new safety note.

The session followed the CHECKPOINT_06 bootstrap instructions but deviated from them at the first decision point. CHECKPOINT_06 §7A had instructed the next session to treat A.Plus as a single Q2 (hypothesis validation) session starting with task selection. Within the first few turns of Session 7, Elden rejected this framing and re-split A.Plus into two sequential sub-phases: A.Plus.1 (Q1: infra validation — "does planner/executor separation technically work?") and A.Plus.2 (Q2: hypothesis test — "is cost-frontier meaningful on floor tasks?"). The re-split was correct — Session 6's Bucket B diagnostic had estimated the infra change at < 15 lines but had never actually executed the code, and conflating Q1/Q2 would have wasted task-selection design effort on an unverified infrastructure. This re-split is the single most consequential framing decision of Session 7 and is the direct source of Finding 14 (Bucket diagnostic ≠ execution validation).

The execution thread followed the A.Plus.1 scope. Round 1 added --executor-model CLI arg to benchmark.py as a fail-loud Option C design (explicit parameter threading on the single-task path, silent fallback on the legacy batch path), committed as 8fdbf50. Round 2a backed up Session 6 trace files to prevent data loss from overwrite. Round 2b ran the actual benchmark on dc28cf18 under inverse=sonnet + executor=haiku, produced a B' trace sidecar, and manually renamed the output to _Bp.jsonl to preserve Session 6 B as baseline. Total Session 7 cost: $0.1424 on the single validation run (benchmark.py estimator, not verified against Anthropic billing), zero on Round 1. Infra Q1 passes — all five validation criteria met.

The Q2 signal was more ambiguous than expected. Round 2b's raw data showed B' total cost ($0.14) below Session 6's total cost ($0.50), which looks like a positive first datapoint for the cost-frontier hypothesis. However, Claude's initial narrative misframed this twice in one session: first by fabricating a Session 6 B single-condition cost of ~$0.03 (never actually recorded anywhere) and reporting "B' is more expensive than B" — the opposite of the truth — and second, after Elden caught the first error, by constructing a "71% lower cost" framing that divided two estimates to produce false precision. Elden caught both errors in real-time. The correction reframes Finding 12: Round 2b is consistent with the cost-frontier hypothesis but cannot support quantitative attribution, because the current trace schema and cost logging cannot decompose where the savings come from (executor vs measurement vs inverse), and the benchmark.py cost estimator itself has not been verified against Anthropic billing. Phase 8.1.A.Plus.2's first design decision must be trace schema expansion for per-stage token attribution, not task selection.

The workflow thread tested the Session 6 rules (metaphor summaries + raw exposure at branches) throughout the execution. They held in most cases — Elden made five substantive catches of Claude errors mid-session, all of which would have progressed into committed artifacts if Session 6's rules had not been in force. But the rules failed in one specific mode that repeated within the same session: Claude fabricated numbers for quantities it did not actually know (the Session 6 B solo cost, and then again the 71% percentage), rather than leaving the cell blank or marked "unknown". This failure mode is distinct from prior failure modes (narrative contradiction, scope creep, technical jargon bleed) and is encoded in §9 as a new load-bearing rule: precision preservation — no output should have more numerical precision than its least-precise input.

Single most important sentence:

Phase 8.1.A.Plus.1 is complete and committed as 8fdbf50; the infra question (Q1) passes with all five criteria met; the cost-frontier hypothesis (Q2) has a first datapoint consistent with the hypothesis direction but cannot be attributed to executor savings specifically due to measurement tool limitations and estimator precision limitations, which makes trace schema expansion (per-stage token attribution: executor / measurement / inverse) the A.Plus.2 prerequisite before floor task selection. Session 7 also tested the Session 6 workflow rules in execution and found them generally load-bearing but exposed one new failure mode (fabrication of unknown quantities under formatting pressure, repeated twice in one session), now encoded in §9 as the precision preservation rule.

---

## 2. Git state

HEAD: 8fdbf50 — Phase 8.1.A.Plus.1: add --executor-model CLI arg (Option C: fail-loud single-task, legacy-preserving batch)
Branch: main (4 commits ahead of origin)
Working tree: clean except for results/ artifacts (gitignored)
inverse.py: byte-identical to b8daf4d. Verified via `git diff b8daf4d HEAD -- inverse.py` (empty) at Round 1 verification step.
benchmark.py: +17 lines / -3 lines from CHECKPOINT_06 baseline (27480c0 → 8fdbf50), all in one commit.

Recent commits:
```
8fdbf50 Phase 8.1.A.Plus.1: add --executor-model CLI arg (Option C: fail-loud single-task, legacy-preserving batch)
2b7fb46 docs: extend CHECKPOINT_06 with Phase 8.1.A.Plus (cost-frontier hypothesis with Wolpert-Kawato credit attribution)
7fbe147 docs: add CHECKPOINT_06 (Phase 8.1.A complete, Phase 8.1.B scoped)
27480c0 spec: add trace.md documenting the Phase 8.1.A trace sidecar layer
```

Note: commits 7fbe147 and 2b7fb46 were made between CHECKPOINT_06 close (27480c0) and Session 7 start. They are docs-only (CHECKPOINT_06 itself and its Session 6 post-close extension). No code changes. Session 7's only code commit is 8fdbf50.

Files produced this session (gitignored, results/ artifacts):
```
results/trace_dc28cf18-6431-458b-83ef-64b3ce566c10_Bp.jsonl       (Round 2b B': haiku executor, 3636 bytes, meta + 1 step)
results/results.8_1_a_plus_1_Bp.tsv                               (Round 2b B' row only, 251 bytes)
results/trace_dc28cf18-6431-458b-83ef-64b3ce566c10_A.session6.jsonl.bak   (Session 6 A baseline backup, 3044 bytes)
results/trace_dc28cf18-6431-458b-83ef-64b3ce566c10_B.session6.jsonl.bak   (Session 6 B baseline backup, 3997 bytes)
results/results.session6.tsv.bak                                  (Session 6 results.tsv backup, 181 bytes)
```

Session 6 trace files (_A.jsonl, _B.jsonl) were restored from .bak copies after Round 2b completed. Round 2b overwrote them during execution (A was re-run because --condition B filters results but still executes both conditions; B was overwritten by the haiku executor run). Restoration verified by diff against backups (all empty).

CACHE_VERSION unchanged: v2.9.0-001. Phase 8.1.A.Plus.1 is CLI arg plumbing only; cache geometry is untouched. model_for_execution is outside the inverse cache key, as confirmed by Round 2b's inverse: 1/1 (100.0%) cache hit on the Session 5 entry despite executor model change.

---

## 3. Findings from this session

### Finding 12 — Cost-frontier first datapoint is direction-consistent; magnitude cannot be quantified with current tools

**What is NOT known:** whether haiku executor produced cost savings relative to sonnet executor for dc28cf18, beyond what cache reuse alone would have produced, and by what margin. This is the central thing A.Plus.1 could not answer and is the reason A.Plus.2 must begin with trace schema expansion rather than floor task selection. Everything else in this finding is either directly observed, inferred from observed values, or estimator-reported. Readers encountering this finding in future sessions should start from this paragraph, not from the cost comparison below.

Round 2b ran inverse=sonnet + executor=haiku on dc28cf18 (mashed potatoes, GAIA Level 1, ceiling task per CHECKPOINT_06 Finding 10). The benchmark.py internal cost estimator reported `estimated total USD: $0.1424` for the Round 2b run. Session 6's comparable run (inverse=sonnet + executor=sonnet, same task, A+B conditions combined) estimated $0.50. Both figures come from the same estimator using benchmark.py's internal pricing table (pricing lookup date: 2026-04-08); the estimator's accuracy against actual Anthropic billing has not been verified in this project. Session 6 did not record a separate B-only cost; only the combined A+B run total was logged.

**What is directly observed** (from trace sidecars and TSV):

- Round 2b produced verifier_passed=True with final_answer=2 in exactly one ReAct step (_Bp.jsonl, 3636 bytes, meta + 1 step row).
- Round 2b B' total_tokens: 12,774 (from results.8_1_a_plus_1_Bp.tsv).
- Session 6 B total_tokens: 9,289 (from the restored Session 6 results.tsv).
- B' consumed 37% more total_tokens than Session 6 B for the same task with the same inverse procedural prompt (the inverse cache hit confirms identical head text).
- B' reasoning trace (raw-read by Elden) showed haiku enumerating each attendee individually with numeric indexing (1–17) and literal arithmetic, while Session 6 B's sonnet trace used markdown section headers (## Step 1 through ## Step 5) and a table. Both arrived at the same arithmetic (11 adults × 1.5, 3 children × 0.5, 3 second-cousins × 0) and the same answer. Reasoning style differed; reasoning content did not.

**What is inferred but not verified** (holds only under the assumption that the benchmark.py estimator is approximately correct, which is itself unverified):

- Haiku's published per-token price is lower than sonnet's (widely known, specific ratio not verified this session).
- The direction of the cost difference between B' and Session 6 B is plausibly favorable to haiku executor — B' uses more tokens but at a lower per-token rate, and the net effect under standard Anthropic pricing would be a lower B' cost. The magnitude of the reduction cannot be stated.
- The $0.50 → $0.14 estimator comparison is also contaminated by cache state asymmetry: Session 6 ran under inverse: 0/1 miss (fresh inverse() call on sonnet), while Round 2b ran under inverse: 1/1 hit (reused Session 6's cached inverse). Some portion of the estimator difference is cache reuse, not executor substitution.

**What remains blocked for A.Plus.2:**

- Separating haiku executor savings from cache reuse savings requires decomposed token attribution per stage (executor / measurement / inverse), which the current trace schema does not provide. TSV total_tokens is a single run-wide scalar.
- Per-step token counts for the executor call (_call_agent_with_retries) exist internally as the return value call_tokens but are not split into in/out and are not recorded in the trace sidecar step rows.
- Per-call token counts for measure_semantic_entropy (which continues to run on sonnet under policy α, regardless of executor model) are not surfaced at all — the function returns a scalar entropy value.
- Inverse() token counts (from its three internal LLM calls: Target / Invert / Compose) are not surfaced as a separable group.
- The benchmark.py estimator itself has not been verified against Anthropic billing. Even with decomposed token attribution, USD comparisons will remain approximate until the pricing table is cross-checked with current Anthropic rates.

**Ceiling task confound:** dc28cf18 is a CHECKPOINT_06 Finding 10 ceiling task. Both sonnet and haiku produced the answer in one step. The run does not test whether haiku can follow the inverse procedural prompt effectively under harder conditions — it tests whether haiku can produce `2` at all from this task, which is trivially true and would likely be true even without any inverse prompt. The cost-frontier hypothesis requires floor tasks (multi-step, where procedural scaffolding actually affects trajectory) to be tested meaningfully. Session 6 Finding 10 predicted this constraint; Session 7's raw B' trace confirmed it empirically — haiku's reasoning arrived at the same answer through the same arithmetic steps as sonnet, with only surface-level writing style differences, which is what a ceiling-task outcome looks like for both models.

**A.Plus.2 prerequisite (blocking):** Trace schema must be expanded before running the cost-frontier experiment on floor tasks. Required fields:

- Per step row: `executor_tokens_in`, `executor_tokens_out` (from _call_agent_with_retries return, split into input/output), `measurement_tokens_in`, `measurement_tokens_out` (from measure_semantic_entropy cost accounting — function must be extended to surface these).
- Per run meta header: `inverse_tokens_in`, `inverse_tokens_out` (from the inverse() call, zero if cache hit).
- USD conversion is NOT stored — raw token counts only, with prices applied at analysis time so the historical record survives pricing table updates.

Without this expansion, the A.Plus.2 floor task experiment would produce the same ambiguous result shape as Round 2b: "B' is cheaper but we can't tell why and can't tell by how much," which fails the stated success criterion of the cost-frontier validation.

### Finding 13 — Claude fabricated unknown quantities twice in one session under formatting pressure

**First instance:** After Round 2b completed, Claude produced a three-row comparison table labeling Session 6 A as "~$0.02", Session 6 B as "~$0.03", and Round 2b B' as "~$0.14", and concluded "B' is more expensive than B, contradicting cost-frontier predictions." The "~$0.03" number for Session 6 B was fabricated: it was not present in any CHECKPOINT_06 record, any Session 6 cost log, or any direct computation. Claude generated it by reverse-reasoning from total_tokens=9289 applied to an internally imagined sonnet price. The number appeared in the table with a tilde prefix, which made it look like an approximation of a real measurement rather than a fabrication.

Elden caught the error by noting that haiku's lower per-token price could mean B' has a lower total cost even with higher total_tokens, which directly contradicted the narrative Claude had built. Upon re-examination, Claude confirmed:

- The only costs actually recorded in CHECKPOINT_06 §6 are the full Session 6 run total ($0.50 for A+B combined) and Phase 8.0 cumulative ($42.28 through CHECKPOINT_05).
- Session 6 did not split A vs B cost at any point. The A-only and B-only columns in Claude's table were both estimates.
- Round 2b's $0.1424 is a confirmed single number from the benchmark log — but it is labeled `estimated total USD` and comes from benchmark.py's internal pricing table, not from verified Anthropic billing.

**Second instance, same session:** After retracting the fabricated $0.03, Claude rewrote Finding 12 with a "71% lower total run cost" framing that divided $0.14 (Round 2b estimated) by $0.50 (Session 6 estimated) to produce a specific percentage. Elden caught this too, pointing out that $0.14 itself is an internal estimator output with unverified accuracy, and that dividing one estimate by another to produce a precise-looking percentage is the same error class as fabricating a missing cell. Claude retracted the percentage and reframed Finding 12 around "what is NOT known / what is observed / what is inferred / what remains blocked" without numeric comparison.

**The two instances share a structural pattern:** a presentation format (comparison table in the first instance, statistical framing in the second) created an expectation of specific-number output, and Claude generated specific numbers to satisfy the expectation rather than leaving the gap or changing the format. This is not a factual error class that can be caught by checking sources — the inputs to both errors were real numbers that Claude knew were estimates. The error is in combining real-but-uncertain inputs to produce output that is presented as more certain than the inputs. The tilde prefix in the first instance was insufficient to mark the distinction — it rendered as "approximately" rather than "estimated by me just now". The decimal precision in the second instance was insufficient to mark the distinction — the "71%" looked like a calculated ratio rather than a ratio of estimates.

**The error class is distinct from prior Claude errors in this project:**

- Not a narrative contradiction (Session 6 decisive moment 2, inverse prior-knowledge): Claude is not contradicting a previous claim within the same message.
- Not a scope creep (Session 6 decisive moment 6, spec commit): Claude is not ignoring workflow rules about when to commit.
- Not a jargon bleed (Session 6 decisive moment 3, workflow evolution origin): Claude is presenting data clearly, not hiding it behind jargon.

This is a **data-fabrication-under-formatting-pressure** error: Claude was building a visual artifact (a comparison table, then a statistical framing) that required a specific number to complete the structure, did not have that number, and filled the gap with an estimate that then became indistinguishable from real data when the artifact was rendered. The root cause is tabular/statistical formatting acting as template completeness pressure: when a data structure has defined rows and columns or expects a headline statistic, there is an implicit expectation that every cell has a value and every framing has a magnitude, and Claude fills cells and magnitudes rather than violating the structure. This is a design-pattern-level failure mode, not a factual-error failure mode.

**How to recognize this in real-time** (Session 7 triggers — apply to future output production):

1. **The table/statistic trigger:** "I am about to produce a table or a statistical framing + one or more cells/numbers require values I do not directly have + I am about to pull the needed value from memory, or from adjacent data, or from a quick calculation on estimates." If all three conditions are present, STOP. Change the format: leave the cell blank, use prose instead of a table, describe direction without magnitude, or collapse the row with a footnote. Do not fill the gap.
2. **The ratio/percentage trigger:** "I am about to express a relationship between two numbers as a ratio, percentage, or multiplicative factor + at least one of the two numbers is an estimate, measurement, or memory recall rather than a directly known value." If both are present, STOP. The ratio of two estimates is an estimate with compounded uncertainty, and expressing it as a specific percentage creates false precision. Describe the relationship qualitatively instead ("lower", "substantially higher", "similar").
3. **The approximation-prefix trigger:** "I am about to prefix a number with '~', 'approximately', 'about', 'roughly' + the number itself originates from something I would not defend as a measurement under raw-reading scrutiny." If both are present, STOP. The approximation prefix is hiding, not marking, a fabrication. Remove the number and describe what is actually known.

All three triggers share a root test: could Claude defend the output number to Elden under raw-reading scrutiny without saying "well, that part was an approximation / recalled from memory / derived from an estimate"? If the answer is no, the output is false-precise and the format needs to change. This test should be applied before a finding, table, or comparison is written, not after Elden catches it.

**Corrective rule (now load-bearing, encoded in §9):** When a data gap meets a formatting pressure, prefer to change the format rather than fill the gap. Tables with blank cells are fine. Prose without percentages is fine. Findings that say "we don't know how much" are fine. The invariant to preserve is: **no output should have more numerical precision than its least-precise input.**

### Finding 14 — Bucket diagnostic is a scope estimate, not an execution validation

CHECKPOINT_06 Finding 11 classified the executor-model separation change as "Bucket B (small change, < 15 lines)" based on a Claude Code diagnostic that inspected benchmark.py's current signatures without actually running the change. The diagnostic's estimate was used by CHECKPOINT_06's bootstrap instructions to frame A.Plus as a single hypothesis-validation session — the implicit assumption being that the infra change was essentially confirmed by the diagnostic and the interesting work was downstream in task selection.

Session 7 directly contradicted this framing on the first decisive turn: Elden re-split A.Plus into A.Plus.1 (infra validation) and A.Plus.2 (hypothesis test), with A.Plus.1 as the prerequisite. The re-split was correct because the Bucket B estimate turned out to be close (actual diff: +17/−3, aligned with "< 15 lines" within rounding) but the execution of the change required multiple sub-decisions that the diagnostic had not surfaced:

1. The run_experiment vs single-task path asymmetry (main() has two call sites for run_task_both_conditions, with different arg access patterns), which required either a global variable (fail-silent) or explicit threading across a 5-function chain (fail-loud). The diagnostic had not flagged this asymmetry.
2. The measure_semantic_entropy policy α enforcement (3 call sites, all of which had to preserve `model` parameter while new `executor_model` flowed to a different call site). The diagnostic had not enumerated these call sites.
3. The threading depth that pushed the total line count from the estimated "< 15" to a measured 18 in the initial design, which triggered a "over budget" alert that was then resolved not by making the change smaller but by Elden/Claude recognizing the 15-line threshold itself was an artifact of the diagnostic's framing.

The lesson generalizes beyond this specific instance: a scope estimate produced by reading code is not the same as an execution validation produced by running the change. Bucket diagnostics can answer "how big is this change approximately" but cannot answer "does this change work when executed". Future sessions that receive a Bucket classification in a checkpoint should treat it as an input estimate, not a completed validation, and should schedule an explicit execution round before proceeding to downstream decisions that depend on the change working.

This finding is the structural justification for the A.Plus.1 / A.Plus.2 split and should be carried into how future phases are scoped in CHECKPOINT §7A sections — estimates and validations should be separated, and checkpoints should not conflate them.

### Finding 15 — Condition label is filesystem-hostile when it contains apostrophes; "B'" (in-memory) / "Bp" (filesystem) asymmetry works

Round 2b required a new condition label to distinguish the haiku executor run from Session 6's sonnet executor B run. Claude initially proposed "B'" (B-prime, indicating "a variant of B") and "Bp" (prime as "p") in parallel — in-memory representation B' for semantic clarity, filesystem representation Bp to avoid apostrophe escaping issues across shells (bash single-quote handling, PowerShell parsing, Windows cmd lexicon). During Round 2b execution, the filesystem form Bp was used in the renamed trace file (trace_dc28cf18-..._Bp.jsonl) and in the separated TSV (results.8_1_a_plus_1_Bp.tsv). No shell escaping problems were observed.

A secondary concern raised during design was that "Bp" appearing in the condition column of results.tsv could be parsed by downstream analysis scripts that expect only {A, B}. Session 7 mitigated this by rename-and-separate: the Round 2b results.tsv was moved to results.8_1_a_plus_1_Bp.tsv and the canonical results.tsv was restored from Session 6 backup. This preserves the {A, B} invariant in the canonical file and isolates the new condition to a dedicated file. The invariant and the new datafile coexist without conflict.

This is a minor finding but it establishes a precedent for Phase 8.1 condition naming: when introducing a new condition that diverges from an existing one, the filesystem form should avoid special characters (apostrophes, slashes, spaces), and when the new condition shares a task with existing conditions, the datafile should be separated rather than the condition column being extended. This precedent should be referenced in A.Plus.2 if multiple executor models are tested (e.g. Bp_haiku, Bp_opus, Bp_gpt5) — filesystem labels should be descriptive and shell-safe.

---

## 3.5. Decisive moments in this session

Five turns initiated by Elden altered the trajectory of this session. All five were catches of Claude framing or data errors that would have progressed into committed artifacts under Session 5's looser workflow but were intercepted by Session 6's "raw at decision branches" rule.

**1. Q1/Q2 split:** Elden refused the CHECKPOINT_06 bootstrap's framing and re-scoped A.Plus into two sequential phases. CHECKPOINT_06 §7A had instructed Session 7 to begin with task selection (a Q2-level decision). Elden's re-split put Q1 (infra validation) first, reading the Bucket B diagnostic as a scope estimate rather than an execution confirmation. This is Finding 14's origin and is the single most consequential framing decision of Session 7. Without this split, Session 7 would have spent design effort on task selection for an experiment that could not have run because the infra was untested. The re-split cost zero turns and saved approximately 5–10 turns of downstream design work.

**2. Fail-loud vs fail-silent on CLI threading:** Elden chose "방법 2" (explicit parameter threading) over "방법 1" (module-level global EXECUTOR_MODEL). Claude Code's initial design proposal used a module-level global variable, reasoning by symmetry with the existing MODEL constant. Claude reviewed this and pushed back with the Sandi Metz argument (duplication vs wrong abstraction) from Session 6 decisive moment 5, arguing that the global pattern creates fail-silent failure modes when run_single_task is called outside of main(). Elden chose the fail-loud pattern. This decision was then further refined into Option C (fail-loud on single-task path, legacy-preserving on batch path) when Claude realized the run_experiment path existed and had different semantic status. The fail-loud preference is the direct consequence of Session 5's confident-wrong-answer failures and Session 6's inverse() prior-knowledge self-contradiction — both cases where silent errors propagated into narratives and were only caught by Elden's raw reading.

**3. Round 2 decomposition into 2a / 2b / 2c:** Claude initially proposed Round 2 as a single Claude Code prompt mixing backup, execution, and rename into one procedure. Claude re-examined this after framing the prompt and noticed that the procedure contained an irreversible step (the benchmark run itself, which would overwrite Session 6 trace files before the backup step if Claude Code executed out of order). Claude split Round 2 into three micro-rounds with Elden checkpoints between each, and explicitly moved the raw-read step (Round 2c) out of Claude Code's scope and into Elden's direct terminal. The split was not requested by Elden — it was a Claude self-correction in response to the Session 6 rule about "raw exposure at decision branches expensive to undo". The decomposition is the first instance in this project of Claude applying Session 6's workflow rules to its own prompt design rather than to data presentation.

**4. Condition label design (B' vs Bp):** Claude raised the apostrophe-vs-filesystem asymmetry as raw information before making the decision. This is a small decisive moment but it matters because Claude explicitly surfaced the tradeoff ("in-memory apostrophe, filesystem Bp") as a design concern rather than picking one and hoping it would not cause problems. Elden accepted the asymmetry without further discussion. In Session 5 or earlier, Claude would likely have picked one label and proceeded; the raw surfacing here is Session 6's workflow rule applied to a minor but structurally important detail.

**5. Cost narrative correction (two-stage):** Elden caught Claude's numerical fabrication twice in sequence. First, Claude built a three-row comparison table with a fabricated Session 6 B solo cost ($0.03) and concluded "B' is more expensive than B, contradicting cost-frontier." Elden caught this with two sentences: "haiku executor에서 더 많은 token을 사용했더라도 가격이 sonnet executor보다 비용이 낮으니 총 비용은 더 낮을 수 있다." Claude retracted and reframed. Then, in the retraction, Claude constructed a "71% lower cost" framing by dividing $0.14 by $0.50. Elden caught this second error with a question: "$0.14도 정확한 계산인줄 모르지 않나?" — pointing out that $0.14 itself is an estimator output, not a verified billing number, and that dividing two estimates produces false precision. Claude retracted the percentage and reframed Finding 12 around "what is NOT known / what is observed / what is inferred / what remains blocked". Without either catch, CHECKPOINT_07 would have documented cost-frontier with a wrong conclusion first, then a false-precise conclusion second. Both catches were needed; one was not sufficient. This is the single most structurally important sequence of Session 7 because it produced the precision preservation rule (§9) and the Finding 13 failure mode documentation, and it prevented a wrong A.Plus.2 design direction from propagating forward.

**Hypothesis amplitude during the session:**

- **Initial** (from CHECKPOINT_06 bootstrap): "A.Plus is a hypothesis-validation session; begin with task selection."
- **After Elden's re-split** (decisive moment 1): "A.Plus.1 is an infra-validation session; task selection is deferred to A.Plus.2."
- **After Round 2b raw read** (before decisive moment 5 first catch): "A.Plus.1 completed with negative cost-frontier signal; A.Plus.2 needs to investigate haiku failure."
- **After decisive moment 5 first catch**: "A.Plus.1 completed with 71% positive cost-frontier signal; A.Plus.2 proceeds to floor task selection."
- **After decisive moment 5 second catch**: "A.Plus.1 completed with direction-consistent but quantitatively un-attributable first datapoint; A.Plus.2's first design decision is trace schema expansion for per-stage token decomposition, not task selection."

The final framing is the inverse of the third framing and a de-quantified version of the fourth framing. The second catch was necessary to prevent the fourth framing from becoming the CHECKPOINT_07 conclusion — which would have been a different error than the third framing but an error nonetheless.

---

## 4. What changed this session

One code commit, zero spec commits, zero inverse.py changes.

**8fdbf50** — Phase 8.1.A.Plus.1: add --executor-model CLI arg (Option C: fail-loud single-task, legacy-preserving batch). Added `--executor-model` argparse argument (default None) with help text documenting the Option C asymmetry. Added main() fallback logic (`if args.executor_model is None: args.executor_model = MODEL`) to make the default explicit after MODEL is settled. Added keyword-only `executor_model` parameter to three function signatures along the single-task call chain: `run_task_both_conditions`, `run_single_task`, `run_react_loop`. Threaded `executor_model` through each call site. In `run_react_loop`, used `executor_model or model` fallback at the `_call_agent_with_retries` call site (line 909). Preserved all three `measure_semantic_entropy` call sites (lines 400, 437, 983) with `model=MODEL` or `model=model` (policy α: measurement stays on inverse model regardless of executor model). Did not add a module-level `EXECUTOR_MODEL` constant — deliberate rejection of the global pattern in favor of explicit threading (fail-loud). Did not modify the `run_experiment` batch path — it continues to call `run_task_both_conditions(task)` without `executor_model` kwarg, which triggers None default and silent fallback to MODEL (legacy-preserving). +17 insertions / -3 deletions, benchmark.py only.

**One thing not changed:** inverse.py. Verified byte-identical to b8daf4d via `git diff b8daf4d HEAD -- inverse.py` (empty) at Round 1 verification. Inverse caching behavior unchanged, CACHE_VERSION unchanged. Phase 8.0 invariants from CHECKPOINT_04 §4 remain intact.

**One thing produced but not committed:** the B' (filesystem: Bp) trace sidecar from Round 2b and the separated results TSV. Both live in results/ which is gitignored. They are Session 7 experimental artifacts and are preserved on disk for future reference but are not part of the committed history.

---

## 5. spec/ status

No spec/ changes this session. Phase 8.1.A.Plus.1 is a CLI plumbing change that does not modify any contract surface, output schema, or cache invariant. spec/trace.md (added in CHECKPOINT_06 commit 27480c0) continues to describe the trace sidecar layer correctly — Round 2b's B' trace file conforms to the spec schema (meta header + step rows), and the condition label "B" in the meta header field is spec-compliant despite the filesystem rename to _Bp.jsonl (the rename is external to the file content, which still declares `condition: "B"`).

Phase 8.1.A.Plus.2 Stage 1 will require two spec changes, both deferred to that session:

1. **spec/trace.md extension:** add `executor_tokens_in`, `executor_tokens_out`, `measurement_tokens_in`, `measurement_tokens_out` to the step row schema, and add `inverse_tokens_in`, `inverse_tokens_out` to the meta header. Document that condition label remains "B" in meta even when filesystem name is _Bp.jsonl. Document that USD values are never stored (price applied at analysis time so historical records survive pricing table updates).
2. **spec/measurement.md** (if it exists and documents measurement policy): add an explicit statement of policy α (measure_semantic_entropy uses inverse model regardless of executor model) with the Session 7 rationale (measurement consistency as a controlled variable for cost-frontier comparison).

Neither spec change is part of A.Plus.1. Both are blocking prerequisites for A.Plus.2 Stage 2's first benchmark run. Both must follow Session 6 §9 rule 2 (pause-before-commit for spec/document commits).

---

## 6. Budget state

- Through CHECKPOINT_06: $42.78 (benchmark.py estimator, not verified against Anthropic billing)
- Session 7 Round 1 (CLI arg implementation): $0.00 (code change only, no LLM calls)
- Session 7 Round 2b (infra validation run): internal estimator reported $0.1424. This is the benchmark.py pricing-table estimate (pricing lookup date: 2026-04-08), not a verified Anthropic billing line item. Treat as approximate within an unknown margin.
- **Cumulative project total (approximate, as-reported-by-estimator): $42.92**

**Note on budget precision:** All cost figures in this project's history are benchmark.py internal estimates. Anthropic's actual billing was not cross-checked in this session and has not been cross-checked in any prior session. If precise budget tracking matters for future decisions (e.g., A.Plus.2 Stage 2 hard abort thresholds, main 18 budget caps), the pricing table should be verified against Anthropic's published rates at a chosen reference date. This is a deferred task; it does not block A.Plus.2 design but should be done before any budget-constrained experimental design that requires magnitude precision rather than direction.

Session 7's cost was well within the $10–15 estimate from CHECKPOINT_06 Finding 11 for the A.Plus Bucket B diagnostic (which covered the full A.Plus scope, not the A.Plus.1 subset). The remaining Bucket B budget (~$10–14 by the same estimate) is available for A.Plus.2 Stage 1 + Stage 2, though the split between stages depends on implementation complexity for the schema expansion.

Phase 8.1.A.Plus.2 will need its own budget estimate once the task set and design are settled. A per-task hard abort should be proposed as part of A.Plus.2 Stage 2's design session. The $1 hard abort used for A.Plus.1 was conservative and held — Round 2b came in at ~14% of that cap by the estimator.

Main 18 estimate: still deferred until Phase 8.1.D (cost model rebuild). Unchanged from CHECKPOINT_06 §6. Blocked on both the cost model and the pricing table verification.

---

## 7. Next state transition

### §7A — Immediate next session work (single step, two stages)

The next session executes Phase 8.1 Step A.Plus.2 only. Do not attempt Steps B, C, or D. A.Plus.2 is the cost-frontier hypothesis validation that A.Plus.1 could not complete due to measurement tool limitations (Finding 12).

A.Plus.2 is explicitly a two-stage step and the stages must execute in order:

**Stage 1 — Trace schema expansion** (prerequisite, code change + spec update). Before any floor task experiment can produce meaningful data, the trace sidecar schema must be extended to decompose token usage by stage (executor / measurement / inverse). This stage is blocking — Stage 2 cannot begin until Stage 1 commits are in main.

Required field additions:
- Step row: `executor_tokens_in`, `executor_tokens_out`, `measurement_tokens_in`, `measurement_tokens_out`
- Meta header: `inverse_tokens_in`, `inverse_tokens_out`

Implementation touches three function layers:
1. `_call_agent_with_retries` already returns a `call_tokens` value — verify it's split into in/out and is executor-only (not measurement-polluted), and wire it into the step row writer.
2. `measure_semantic_entropy` currently returns a scalar entropy value — extend its return interface (or add a companion accessor) to surface per-call token counts without breaking existing callers. Consider whether this requires a wrapper or a direct function signature change.
3. `inverse()` has three internal LLM calls (Target / Invert / Compose) — decide per-call recording vs aggregate recording in the spec design conversation. Provisional recommendation: aggregate (single pair `inverse_tokens_in`/`out` in meta header) to minimize schema churn, with per-call recording deferred to a future phase if needed.

spec/trace.md must be updated in the same phase with pause-before-commit (Session 6 §9 rule 2). CACHE_VERSION impact: schema additions to trace output should not affect cache keys, but verify during implementation by grep for cache key construction.

Expected scope: 20–40 lines across benchmark.py for token extraction and field wiring, plus spec/trace.md extension. Larger than A.Plus.1 because it touches three function layers and has spec implications. Treat as Bucket B upper bound or small Bucket C (apply Finding 14 — this is a scope estimate, not an execution validation).

**Stage 2 — Floor task selection + experiment run** (only after Stage 1 commits land). Once the trace schema supports decomposition, the cost-frontier experiment runs on a floor task set. Design questions for Stage 2 (do not resolve these in Stage 1 — they are Stage 2's design session items):

- **Floor task selection:** CHECKPOINT_06 Session 5 pilot data review in Session 7 found that Task 5 (676e5e31, L3) is the most canonical floor task but failed on both A and B conditions (verifier_passed=False both). Task 3 (3627a8be, L2) is the only task in the Session 5 pilot set that showed a genuine A/B signal difference. The task set proposal from Session 7's aborted Stage 2 design discussion was "Task 3 alone + Task 5 as qualitative diagnostic" — revisit this proposal in Stage 2 with the expanded trace schema in mind.
- **Measurement policy α confirmation or revisit:** Session 6 recommended policy α (measurement stays on inverse model). A.Plus.1's Round 2b ran under policy α without observable problems, but the entropy measurement layer remains broken (flat-zero per Finding 7), so policy α's actual effect is still theoretical. Stage 2 can either continue policy α or explicitly test policy β (measurement on executor model) on one task to observe the difference.
- **Success criterion:** With decomposed token attribution, the success criterion can be sharpened from "verifier_passed parity at lower total cost" to "executor-attributed cost reduction at verifier_passed parity on floor task." This is a stronger statement because it isolates the executor contribution from measurement and inverse confounds.
- **Budget:** Stage 2 estimate should be proposed after Stage 1 lands. With decomposed attribution, individual step costs become visible, which may enable tighter per-task hard aborts.
- **Pricing table verification:** Optional for Stage 2, but if the experiment results need to be framed in USD with any precision beyond direction-only, the pricing table should be cross-checked against Anthropic's published rates first.

**Critical constraint** (inherited from Session 7, non-negotiable): Do NOT begin A.Plus.2 with task selection or experiment design. Begin with Stage 1 trace schema expansion. Stage 2 design is contingent on measurement tools being ready. This constraint is the direct consequence of Finding 12 and the structural reason A.Plus.2 is split into two stages. A future Claude that reads §7A quickly and jumps to task selection will repeat the A.Plus.1 measurement ambiguity and lose the lesson Session 7 paid for.

### §7B — Phase 8.1 roadmap tracker (multi-session)

This table is the single source of truth for Phase 8.1 progress. Every session that touches Phase 8.1 must update this table when closing the session and copy it forward to the next checkpoint. Do not delete rows. Do not rewrite columns. Status transitions only: TODO → ACTIVE → DONE (with commit SHA).

| Step | 작업 | 의존성 | 상태 | 완료 조건 | 결과/SHA |
|------|------|--------|------|-----------|----------|
| 8.1.A | Per-step trace persistence | none | DONE | Trace written + readable + 1 task validation + spec update | 0556d8f → f5e624b → 27480c0 (trace writer → trace_path column → spec/trace.md). Validated on Task 2 (dc28cf18) in Session 6 at $0.50 cost. CHECKPOINT_06 §3 Finding 10 documents the validation result and its implications for 8.1.B target selection. |
| 8.1.A.Plus.1 | Infra validation: --executor-model CLI arg + single-task single-condition run under planner=sonnet/executor=haiku. Verify technical feasibility of executor separation. | 8.1.A complete | DONE | CLI arg implemented + run succeeds + trace sidecar valid + all 5 infra checklist items pass | 8fdbf50 (benchmark.py +17/-3, Option C: fail-loud single-task path, legacy-preserving batch path). Validation: Round 2b on dc28cf18, estimator-reported $0.14, verifier_passed=True, trace sidecar saved as _Bp.jsonl. All 5 Q1 checklist items passed. CHECKPOINT_07 §3 Finding 12 documents the cost-frontier first datapoint (direction-consistent but unattributable), Finding 13 documents Claude's fabrication errors (two instances, same session) and their correction, Finding 14 generalizes the Bucket-diagnostic-vs-execution lesson. |
| 8.1.A.Plus.2a | Trace schema expansion (Stage 1 of 2). Add per-stage token attribution: executor_tokens_in/out and measurement_tokens_in/out in step rows, inverse_tokens_in/out in meta header. Update spec/trace.md with pause-before-commit. | 8.1.A.Plus.1 complete | ACTIVE (next session, prerequisite for 8.1.A.Plus.2b) | Schema fields implemented in benchmark.py + trace sidecar produces the new fields on validation run + spec/trace.md updated and committed with pause + CACHE_VERSION impact verified (expected none) | — |
| 8.1.A.Plus.2b | Cost-frontier floor task experiment (Stage 2 of 2). Run floor task set under A (raw+sonnet) vs B' (inverse+haiku) with decomposed token attribution. Document cost decomposition with explicit attribution to executor savings vs cache reuse vs other factors. | 8.1.A.Plus.2a complete (schema expansion must be in main) | TODO (blocked on 2a) | Floor task set run, decomposed cost comparison documented, success criterion outcome (positive/partial/negative) stated regardless of direction. All claims subject to §9 precision preservation rule. | — |
| 8.1.B | Entropy measurement layer redesign (mini-experiment: N_SAMPLES sweep, optionally MEASUREMENT_QUESTION variants) | 8.1.A complete (need traces to read mini-experiment results) | TODO | Decision on N_SAMPLES + question prompt + (optional) metric change, documented with experimental data | — |
| 8.1.C | detect_loop H_raw=0 fallback | 8.1.B complete (new entropy distribution shape determines threshold rule) | TODO | Fallback rule implemented, retroactive validation against Task 5 trace, spec update | — |
| 8.1.D | Cost model rebuild | 8.1.C complete (cost depends on final measurement layer + loop detector) | TODO | O(N²) cost formula documented, main-18 budget cap and per-task abort thresholds set | — |

**Rationale for the order (updated Session 7):** 8.1.A.Plus was split into A.Plus.1 (infra, done Session 7) and A.Plus.2 (hypothesis, active). A.Plus.2 is further split into 2a (schema expansion) and 2b (floor task experiment) as separate rows in the roadmap because Session 6 taught that "one step" in §7B usually decomposes into multiple sub-tasks at execution time (Operational Lesson from CHECKPOINT_06 §8). Making the sub-stages visible as rows enforces the ordering: a session that reads this table will see that 2b is blocked on 2a and cannot skip to experiment design. A.Plus.2 remains a side-gate parallel to 8.1.B — it does not block 8.1.B/C/D, but is executed first because its results may inform 8.1.B's entropy work. 8.1.B remains the dependency hub for 8.1.C and 8.1.D. Dependency-respecting order: 8.1.A → 8.1.A.Plus.1 → 8.1.A.Plus.2a → 8.1.A.Plus.2b → 8.1.B → 8.1.C → 8.1.D.

**Mandatory session-close obligation:** Whichever session completes a step must (a) flip its status to DONE with the commit SHA, (b) flip the next step's status to ACTIVE, and (c) copy the entire table forward to the next checkpoint without removing rows or columns. Failing to update this table is a framing violation — it deletes the cross-session memory of which steps remain. The 2a/2b split is not a re-scoping in the sense that allows row removal; both rows must be carried forward until 2b lands.

---

## 8. Operational lessons from Session 7 (carry forward)

Inherited from CHECKPOINT_06 §8. Additions from this session:

1. **Bucket diagnostic is a scope estimate, not an execution validation** (Finding 14 generalized). When a prior checkpoint classifies a change as Bucket A/B/C with a line-count estimate, that classification answers "approximately how big" not "does it work". Sessions that receive a Bucket classification as input should schedule an explicit infra validation round before committing to downstream decisions that depend on the change working. The A.Plus.1 / A.Plus.2 split is the canonical example — Session 7 rejected CHECKPOINT_06's framing of A.Plus as a single hypothesis-validation session and inserted infra validation as a prerequisite, which was the single most consequential framing decision of the session. Future phases should apply this rule: estimate and validate are separate steps, and checkpoints should not conflate them.

2. **Numerical precision must not exceed input precision** (Finding 13 generalized). When producing cost comparisons, performance ratios, or any numerically-framed finding, the output precision must be bounded by the least-precise input. If any input is an estimate (e.g., benchmark.py's `estimated total USD`, memory-recalled values, counts inferred from adjacent data), the output must be framed as an estimate and specific percentages / ratios / multipliers must be avoided. The operational test is: can this output number be defended under raw-reading scrutiny without saying "well, that part was an approximation"? If not, the format is wrong and should be changed (prose instead of table, "unknown" cell instead of filled cell, "lower but magnitude unclear" instead of "X% lower"). This rule applies to both data presentation (tables, comparison rows) and analysis framing (findings, conclusions). The load-bearing statement of this rule lives in §9; the operational application lives here.

3. **Round decomposition: irreversible operations get their own round.** Session 7 Round 2 was initially framed as a single Claude Code prompt combining backup + execution + rename. Claude self-corrected and split it into 2a (backup) / 2b (execution + rename) / 2c (raw read by Elden). The rule: any procedure containing an irreversible step (file overwrite, file delete, commit, API cost) should be its own round, with an explicit checkpoint before and after. Mixing reversible and irreversible in one round creates recovery ambiguity — if the round fails mid-way, restoring state becomes guesswork. The cost of extra round-trips is paid in round count, not in recoverability, and recoverability is more valuable.

4. **Manual workarounds beat code changes for one-off experiments.** Session 7's condition label asymmetry (B' in-memory, Bp filesystem, and the results.tsv rename pattern) was handled with a manual procedure (backup → run → rename → restore) rather than extending benchmark.py to natively support the new condition. This was correct for a single infra validation — the cost of the manual procedure was a ~5-line bash sequence, and the cost of the code change would have been a new condition value in `run_task_both_conditions`, a new TSV column, possibly a new spec clause. The lesson: when an experiment is genuinely one-off, prefer manual file manipulation over code generalization. A.Plus.2 Stage 2 will likely require the code generalization (multiple runs, repeated condition labeling), and that's the right time to do it — not in A.Plus.1.

5. **Fail-loud asymmetry for two-path functions** (Finding 14 applied to design). When a function has two semantically distinct call sites — one representing active development/experiment and one representing legacy/backward-compat behavior — it is acceptable and sometimes correct to make one path fail-loud and the other path legacy-preserving. Option C in A.Plus.1 (single-task = fail-loud, batch = legacy) is the precedent. The rule is not "always fail-loud everywhere" — it is "fail-loud at the boundary where current decisions are being made, preserve behavior at the boundary where historical artifacts live". This is closer to the "decisions expensive to undo get raw exposure" rule from Session 6: active development paths demand explicit decisions; legacy paths demand non-disturbance.

6. **Pattern-learning lag: Claude learns specific instances faster than general rules, and must explicitly abstract rules after every catch.** Finding 13's structural observation: after Elden caught Claude's first numerical fabrication (Session 6 B solo cost), Claude learned "don't make up that specific number" rather than "don't fabricate numbers under formatting pressure", and repeated the same error class within the same session (the 71% percentage). This is a pattern-generalization failure, not a memory failure. The lesson: when Elden catches a specific instance of an error, Claude should explicitly attempt to state the rule in its most general form before moving on, and should check that general rule against the session's other outputs to see if the rule is already being violated elsewhere. If Claude cannot state the general rule confidently, the specific catch has not been fully absorbed and the same error class may recur later in the same session.

---

## 9. Safety notes

Inherited from CHECKPOINT_06 §9. Unchanged unless noted.

**NEVER:** touch .env.example; echo .env contents; re-invoke a running benchmark.py process; commit results/ or cache/; treat 1 datapoint as pattern evidence; accept bash_tool background detach for benchmark runs without explicit wrapper.

**ALWAYS:** read the current checkpoint fully before acting; use explicit timeout 1800 shell wrapper for any long-running command; capture stdout + copy results.tsv between tasks; preserve data from self-terminating tasks even if they exceed wall-clock limits; be honest about what is observed vs hypothesised.

**Inherited from Session 5:**

- Before designing any pipeline change, observe what the current pipeline actually produces.
- entropy is a primary observation tool, not optional infrastructure. Do not propose removing measurement to save cost.
- detect_loop is structurally dead when H_raw = 0 (CHECKPOINT_05 Finding 6). Do not rely on detect_loop output for any decision until 8.1.C lands.
- Per-step traces ARE persisted as of Phase 8.1.A (spec/trace.md). Trace sidecars at `results/trace_<task_id>_<condition>.jsonl` are the canonical per-step record.
- Cost is quadratic in step count. All main-18 budget estimates remain unreliable until Phase 8.1.D lands.
- The Phase 8.1 §7B table is mandatory cross-session memory. A session that does Phase 8.1 work without updating §7B has left the next session blind. The 2a/2b split rows added in Session 7 must be carried forward.
- HEAD verification by SHA is brittle. Use invariants (file diffs against a known code baseline, CACHE_VERSION, deleted-symbol grep) instead.

**Inherited from Session 6** (unchanged, see CHECKPOINT_06 §9 for full text):

- **Workflow rule (load-bearing):** Claude presents decisions in metaphor language; raw exposure happens only at decision branches expensive to undo. Session 7 tested this rule repeatedly across five decisive moments and found it load-bearing — raw exposure at branch decisions was what enabled Elden's catches (Q1/Q2 split, fail-loud choice, cost narrative correction first and second catches).
- **Spec/document commits require a pause-before-commit step.** Code commits do not. Session 7 had zero spec commits so the rule was not tested this session. A.Plus.2 Stage 1 will have a spec/trace.md extension commit and the rule will apply.
- **inverse() mobilizes the LLM's prior knowledge by design** (Interpretation A). Unchanged. Task 5 cache-read side-check still deferred.

**New in Session 7:**

- **Precision preservation rule (load-bearing, not optional):** No output should have more numerical precision than its least-precise input. Established mid-Session 7 by Elden's two consecutive catches (Finding 13 first and second instances — the fabricated Session 6 B solo cost, then the 71% percentage derived from two estimates). The rule has three applications:

  1. **Data presentation:** Tables with unknown cells must leave cells blank or marked "unknown", not estimate-and-tilde. Tilde-prefix is insufficient because it renders as "approximately known" rather than "made up by Claude just now".
  2. **Comparison framing:** Ratios, percentages, and multiplicative factors derived from two or more estimates must be presented as estimates of the ratio, not as precise ratios. If either input is uncertain by more than ~10%, avoid giving a specific percentage at all.
  3. **Finding narration:** A finding that concludes "X is lower by Y%" is stronger than "X is lower but magnitude unclear" only when Y is known to adequate precision. When it isn't, the weaker framing is the correct framing.

  **Real-time recognition (three triggers to watch for)** — these are the specific conditions Session 7 identified under which the rule tends to be violated. A future Claude reading this should mentally check each trigger before producing any numeric output:

  1. **Table/statistic trigger:** producing a table or statistical framing + one or more cells require values not directly known + the filling value will come from memory, adjacent data, or quick calculation on estimates. If all three: change the format (blank cell, prose, footnote) rather than fill the gap.
  2. **Ratio/percentage trigger:** expressing a relationship as ratio/percentage/multiplier + at least one of the two numbers is an estimate or memory recall. If both: describe qualitatively ("lower", "substantially higher"), not quantitatively.
  3. **Approximation-prefix trigger:** about to prefix a number with "~", "approximately", "about", "roughly" + the number is something that would not survive raw-reading scrutiny as a measurement. If both: the prefix is hiding a fabrication, not marking it — remove the number and describe what is actually known.

  **Root test** applicable to all three triggers: could Claude defend the output number to Elden under raw-reading scrutiny without saying "well, that part was an approximation / recalled from memory / derived from an estimate"? If no, the format is false-precise and must change.

  The rule is a response to Session 7's repeated failure mode where Claude filled numerical gaps to satisfy formatting expectations, producing narratives with false precision. Session 7's Finding 12 re-write (removing "71% lower" and replacing it with "what is NOT known / observed / inferred / blocked" structure) is the canonical example of applying the rule retroactively. Future sessions must apply it before a finding is written, not after Elden catches it. The "fabrication under formatting pressure" pattern from Finding 13 is a specific instance of this general rule — they are not two separate rules, they are one rule with its failure mode documented.

- **Bucket diagnostic is a scope estimate, not an execution validation** (see also §8 operational application). When a prior checkpoint's Finding or §7 framing contains a Bucket A/B/C classification with a line-count estimate, do not treat that classification as confirmation that the change works. Schedule an explicit infra validation round before committing to downstream decisions that depend on the change. Session 7's A.Plus.1 / A.Plus.2 split is the canonical application. This is listed here in §9 (not only in §8) because it is a standing constraint on how future sessions interpret checkpoint framing, not just a lesson about how to design individual sessions.

Manual workarounds for one-off experiments and round decomposition for irreversible operations are documented in §8 as operational lessons. They are deliberately not listed here in §9 as standing safety rules — they are best-practice patterns that Claude should apply with judgment per situation, whereas §9 items are constraints that apply regardless of situation.

---

## 10. New session bootstrap block

To continue work, open a new Claude conversation and paste the following prompt followed by the full contents of this file:

> This is a continuation of the prompt-training project. Load the checkpoint below in full before acting. Pay special attention to §1 (framing — Phase 8.1.A.Plus.1 is complete; Phase 8.1.A.Plus.2 begins as a two-stage step split into 2a/2b rows in §7B; the workflow rules from Session 6 held under pressure and a new load-bearing rule was added per §9), §3 (Findings 12–15, especially Finding 12 on cost-frontier first datapoint framed as "what is NOT known" first, Finding 13 on numerical fabrication with three real-time recognition triggers, Finding 14 on Bucket diagnostic vs execution validation), §3.5 (decisive moments — all five were Elden catches of Claude framing errors, with moment 5 being a two-stage sequence), §7A (your single immediate task — A.Plus.2 is two-stage: Stage 1 schema expansion blocks Stage 2 experiment), §7B (the Phase 8.1 tracker with A.Plus.2 split into 2a/2b rows — mandatory cross-session memory), §8 (operational lessons — six this session), §9 (safety notes — one new load-bearing rule: precision preservation, with three real-time recognition triggers).
>
> Your job: execute §7A — Phase 8.1 Step A.Plus.2 Stage 1 (trace schema expansion) first, Stage 2 (floor task experiment) only after Stage 1 commits. Do not attempt Steps B, C, or D in this session. Do not attempt Stage 2 until Stage 1 has landed and spec/trace.md has been updated with pause-before-commit per §9.
>
> **Important:** A.Plus.2 is a SCHEMA + SPEC session before it is an experiment session. Do not start by writing Claude Code prompts to select floor tasks. Start by walking through the schema expansion design with Elden:
>
> 1. **Which token counts to record, and at what layer?** Proposal (from CHECKPOINT_07 §5 and §7A): per-step row adds `executor_tokens_in`, `executor_tokens_out`, `measurement_tokens_in`, `measurement_tokens_out`; meta header adds `inverse_tokens_in`, `inverse_tokens_out`. Discuss whether this decomposition is sufficient or whether additional fields (e.g., per-retry tokens from `_call_agent_with_retries`) are needed.
> 2. **How to extract token counts from existing functions?** `_call_agent_with_retries` already returns a `call_tokens` value — verify it's split into in/out and is executor-only (not measurement-polluted). `measure_semantic_entropy` currently returns a scalar — needs extension to also return or log per-call token counts. `inverse()` has three internal LLM calls (Target / Invert / Compose) — aggregate or per-call recording? Provisional recommendation: aggregate, minimize schema churn.
> 3. **CACHE_VERSION impact:** schema additions to trace output should not affect cache keys, but verify by grep for cache key construction during Claude Code's diagnostic phase. If any cache entry format changes, CACHE_VERSION must bump.
> 4. **spec/trace.md update scope:** new fields documented, policy α statement added (measurement stays on inverse model), USD-not-stored principle documented. Pause-before-commit is mandatory per Session 6 §9 rule 2.
> 5. **Stage 2 design questions are explicitly deferred:** Floor task selection, success criterion, measurement policy confirmation or revisit, budget, and pricing table verification — these belong to Stage 2's design conversation, not Stage 1's schema work. Do not pre-empt them even if the conversation naturally drifts toward them. Stage 1's output must be a landed schema, not a planned experiment.
> 6. **Will measurement be done under entropy?** Same status as A.Plus.1 — entropy measurement layer remains broken (Finding 7 flat-zero). A.Plus.2's primary signals will be token attributions and verifier_passed. Entropy values will be recorded but may collapse to zero; treat as advisory.
>
> Only after Stage 1 schema design is settled with Elden should you begin proposing Claude Code prompts. The first code action will be the trace writer extension in benchmark.py (estimated 20–40 lines for token extraction + field wiring, larger than A.Plus.1 because it touches three function layers — apply Finding 14, this is a scope estimate, not a confirmation). Then spec/trace.md extension with pause-before-commit. Then invariant verification. Only after Stage 1 commits do you proceed to Stage 2 (floor task selection + experiment run), which will have its own design conversation at that point.
>
> **Before executing:**
>
> 1. Acknowledge the checkpoint.
> 2. Read §7B and confirm you understand that 8.1.A.Plus.1 is DONE (commit 8fdbf50), 8.1.A.Plus.2a is now ACTIVE, 8.1.A.Plus.2b is TODO blocked on 2a, and you must update the table at session close. The table is mandatory cross-session memory. Do NOT merge 2a and 2b back into one row even if it feels redundant — the split is structural and load-bearing.
> 3. Read §9 safety notes carefully — especially the new precision preservation rule from Session 7 with its three real-time recognition triggers. Apply the root test ("could I defend this number to Elden under raw-reading scrutiny?") before writing any numerically-framed content, not after Elden catches it.
> 4. Verify code state by invariants (not SHA): `grep -n 'summarize_to_head\|summarize_to_body\|trim_to_tail' inverse.py benchmark.py` (no matches), `grep -n 'CACHE_VERSION' benchmark.py` (v2.9.0-001), `git diff b8daf4d HEAD -- inverse.py` (empty), `grep -n 'executor_model\|executor-model' benchmark.py` (new arg and parameters present, 12+ matches expected), `grep -n 'EXECUTOR_MODEL' benchmark.py` (empty — no global), `grep -n '_write_trace_sidecar_meta\|_append_trace_step' benchmark.py` (both present).
> 5. Begin the schema design conversation with Elden. Do NOT propose code changes in your first turn. Ask the schema design questions above, in metaphor language, one branch at a time, with raw exposure only when a decision is expensive to undo (schema field additions are one such decision; CACHE_VERSION impact is another; measure_semantic_entropy return-interface change is another).
>
> **Working method:** I (Elden) do not let you write code directly. You produce Claude Code prompts that I paste into a separate Claude Code session. I relay outputs back to you. You review, decide, and produce the next prompt. Session 6 rule: you summarize technical decisions into metaphor language and present me with binary or trinary choices, not raw technical details. Raw exposure happens when a decision is expensive to undo. You judge which decisions qualify. Session 7 rule: no output may have more numerical precision than its least-precise input; when a data gap meets a formatting pressure, change the format rather than fill the gap.
>
> When producing CHECKPOINT_08 at the close of this session:
>
> - Follow the template inherited from CHECKPOINT_03 §13.
> - Inherit §9 Safety notes with any additions.
> - Update §7B: flip 8.1.A.Plus.2a from ACTIVE to DONE with commit SHA(s); if Stage 2 also completes, flip 8.1.A.Plus.2b from TODO to DONE. If only 2a completes in this session, leave 2b as ACTIVE (next session) and keep 8.1.B as TODO.
> - Do NOT remove or shorten the §7B table. Do NOT merge the 2a/2b split back into one row. Copy all rows forward.
> - If Stage 2's experiment results suggest re-ordering or re-scoping Phase 8.1 steps, explain the reason in §1 framing of CHECKPOINT_08.
>
> [PASTE FULL CONTENTS OF CHECKPOINT_07_phase_8_1_a_plus_1_complete.md HERE]

---

## 11. End of CHECKPOINT_07

Session 7 closes after this file is committed. One code commit landed in main this session (8fdbf50). Zero spec commits. Phase 8.1.A.Plus.1 is complete; the §7B table reflects this. Phase 8.1.A.Plus.2 is now split into two active rows — 2a (schema expansion, ACTIVE) and 2b (floor task experiment, TODO blocked on 2a) — and is the next session's single immediate task. The bootstrap block in §10 contains the prompt to load CHECKPOINT_07 in the next session.

Session 7's most important outcomes are not code changes. They are:

1. The Q1/Q2 split that rejected CHECKPOINT_06's framing (Finding 14, decisive moment 1)
2. The cost narrative correction in two stages that kept the cost-frontier hypothesis alive and prevented two different wrong conclusions from propagating (Finding 12, decisive moment 5)
3. The precision preservation rule that now constrains all future numerically-framed findings with three real-time recognition triggers (Finding 13, §9)
4. The §7B 2a/2b row split that enforces Stage 1 as a structural prerequisite visible in the roadmap table (§7B)
5. The confirmation that Session 6's workflow rules held under pressure across five decisive moments, including one two-stage sequence, with one new failure mode surfaced and now addressed

These are cross-session memory. They will shape how A.Plus.2 is designed and how future phases are scoped regardless of A.Plus.2's experimental result. A future session that reads this checkpoint and follows §7A and §9 will not repeat the A.Plus.1 measurement ambiguity, will not fill numerical gaps under formatting pressure, and will not jump to experiment design before schema is ready. A future session that skips §9 or merges the §7B 2a/2b rows may repeat one or more of these failure modes, and the next CHECKPOINT will have to re-learn them.
