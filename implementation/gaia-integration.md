# GAIA integration

> Sourced from: v2.7.9 §Task set: GAIA Level 1 (text-only), §Verifier
> Related: [benchmark.md](./benchmark.md), [../spec/termination-taxonomy.md](../spec/termination-taxonomy.md), [../analysis/temporal-drift.md](../analysis/temporal-drift.md)

---

## Source

The v0 task set is **GAIA validation Level 1, text-only subset**. Self-authored tasks are not used.

### Why GAIA

- Questions are conceptually simple for humans but require multi-step reasoning, tool use, and information retrieval — precisely the setting where agent loops emerge.
- Ground truth answers are unambiguous and machine-verifiable, enabling automated scoring.
- Level 1 is the smallest, most manageable subset for v0 while still exercising the hypothesis.

### Why text-only

- v0 targets the inverse model's effect on agent loops. Multimodal processing (images, audio, PDFs) is a separate axis of capability that would confound the result.
- Multimodal is deferred to v1. See [../roadmap/deferred.md](../roadmap/deferred.md).

### Why no self-authored tasks

- GAIA provides a pre-existing, widely recognized benchmark with an official scorer. Self-authored tasks would require a separate (and weaker) verification path.
- Korean-language tasks are deliberately excluded. GAIA's scorer is English-only, and maintaining a single scoring pipeline is more valuable than language generalization in v0. Language generalization is a v1 concern or a separate paper.

---

## Loader (two-stage filter)

The loader applies a two-stage text-only filter. The first stage alone is insufficient because GAIA Level 1 contains tasks where `file_name` is empty but the Question body embeds a YouTube/video/audio URL — these are structurally unsolvable with Tavily and would inject systematic noise into condition A's loop rate.

```python
import re
from datasets import load_dataset

# Patterns for external multimodal resources that Tavily cannot handle.
# These appear in the Question body even when file_name is empty.
# Observed in GAIA Level 1: questions like "In the video https://youtube.com/watch..."
MULTIMODAL_URL_PATTERNS = [
    r"youtube\.com/watch",
    r"youtu\.be/",
    r"\.mp[34]\b",   # mp3, mp4
    r"\.wav\b",
    r"vimeo\.com/",
]

def is_truly_text_only(task) -> bool:
    """
    Text-only means BOTH:
    1. No file attachment (file_name is empty), AND
    2. Question body does not reference external multimodal resources
       that Tavily's search/extract cannot handle.
    """
    if task.get("file_name"):
        return False
    question = task.get("Question", "")
    for pattern in MULTIMODAL_URL_PATTERNS:
        if re.search(pattern, question, re.IGNORECASE):
            return False
    return True

def load_gaia_tasks():
    """
    Load GAIA validation set Level 1, truly text-only tasks.

    Column schema (confirmed):
        task_id, Question, Level, Final answer, file_name, file_path, Annotator Metadata
    Level 1 validation total: 53 tasks.
    """
    gaia = load_dataset("gaia-benchmark/GAIA", "2023_level1", split="validation")

    # Stage 1: empty file_name
    no_file = [t for t in gaia if not t.get("file_name")]

    # Stage 2: no multimodal URLs in Question
    text_only = [t for t in no_file if is_truly_text_only(t)]

    total = len(gaia)
    excluded_by_url = len(no_file) - len(text_only)
    print(f"[load_gaia_tasks] Level 1 total: {total}")
    print(f"[load_gaia_tasks] After file_name filter: {len(no_file)}")
    print(f"[load_gaia_tasks] After multimodal URL filter: {len(text_only)}")
    print(f"[load_gaia_tasks] Excluded due to multimodal URLs in question body: {excluded_by_url}")
    return text_only
```

Logging both stage counts separately makes the filter behavior transparent. If the URL filter excludes an unexpectedly large fraction, that itself is a signal worth investigating before the run.

The `MULTIMODAL_URL_PATTERNS` list is **editable** — see [../operations/experiment-rules.md](../operations/experiment-rules.md) — because it is a false-positive filter, not part of the experimental hypothesis.

---

## Schema mapping (GAIA field → internal task field)

| Internal field | GAIA field | Notes |
|---|---|---|
| `task_id` | `task_id` (GAIA UUID) | used as cache key and TSV row |
| `raw_prompt` | `Question` | passed to `inverse()` and to the agent |
| `ground_truth` | `Final answer` | passed to verifier only; never seen by agent |
| `level` | `Level` | always 1 in v0 |
| `max_steps` | derived from `Level` | see below |
| `timeout_seconds` | constant 300 | — |

### Fields explicitly not used

- **`Annotator Metadata`**: contains the annotator's step-by-step solution procedure. Using this would leak ground-truth signal to the agent.
- **`file_path`**: only relevant for tasks with attachments, which are excluded by the filter.
- **`expected_outputs`** (from t2.5): removed entirely; replaced by `ground_truth` + verifier.
- **`domain`** (from t2.5): removed; replaced by `level`.

### Important: column names contain spaces

GAIA's column names use spaces: `"Final answer"`, `"Annotator Metadata"`. Dictionary access must use the exact string with the space — `task["Final answer"]`, **not** `task["final_answer"]`. This is the most common bug entry point. See the implementation checklist in [checklist.md](./checklist.md).

---

## `max_steps` by Level

| Level | `max_steps` |
|---|---|
| 1 | 15 |
| 2 | 25 |
| 3 | 50 |

v0 uses Level 1 only, so effectively `max_steps = 15` for all tasks. Levels 2 and 3 are listed for v1 preparation.

### Contingency rule (max_steps upward adjustment)

If the first full run shows that **more than 20% of Level 1 tasks end with `terminated_by == "max_steps_reached"`**, raise `max_steps` to 20 and record the results separately. This is not a spec modification — it is a resource limit adjustment applied equally to both conditions A and B, so it is not an experimental variable.

The structural reason this is allowed (and the reason `max_steps_reached` is its own taxonomy value rather than getting folded into `loop_count`) is in [../spec/termination-taxonomy.md §False Positive control](../spec/termination-taxonomy.md#false-positive-control-loop-count-vs-budget-exhaustion).

---

## Sample size contingency

GAIA Level 1 validation has **53 tasks total**. After the two-stage text-only filter, the exact count must be logged at first load.

**Contingency rule (applied once at first load, then locked)**:

1. Text-only Level 1 ≥ 30 → proceed as-is.
2. Text-only Level 1 in [20, 29] → add Level 2 text-only tasks until the combined count reaches 30.
3. Text-only Level 1 < 20 → report v0 results as descriptive only (no statistical tests).

**Sample composition is fixed after the first load and does not change between runs.** Reruns always target the identical task set. This is a load-bearing reproducibility property — see [../operations/reproducibility.md](../operations/reproducibility.md).

---

## Verifier

### Source

The verifier is GAIA's **official quasi-exact-match scorer**, vendored bit-exact from the GAIA leaderboard repository.

**Source URL**: `https://huggingface.co/spaces/gaia-benchmark/leaderboard/blob/main/scorer.py`

### Vendoring procedure

1. Download `scorer.py` from the URL above.
2. Copy it to `prompt-training/gaia_scorer.py` without modification.
3. Add the following header to the file (prepend, do not modify existing code):

```python
"""
prompt-training/gaia_scorer.py

Vendored from: https://huggingface.co/spaces/gaia-benchmark/leaderboard/blob/main/scorer.py
Retrieved on: <YYYY-MM-DD>
Commit hash: <record the HF space commit SHA at retrieval time>

DO NOT MODIFY. This is a bit-exact copy of GAIA's official quasi-exact-match scorer.

Public interface used by benchmark.py:
    question_scorer(model_answer: str, ground_truth: str) -> bool

Scorer logic (for reference, not to reimplement):
    - If ground_truth is a float (numeric): normalize_number_str on model_answer,
      compare as float equality.
    - If ground_truth contains comma or semicolon: split both into lists,
      normalize each element by its type (numeric or string), compare element-wise.
    - Otherwise: normalize_str on both, compare as exact string equality.
"""
# --- Vendored code below this line ---
```

### Verification sanity checks (after vendoring)

```bash
python -c "from gaia_scorer import question_scorer; print(question_scorer('42', '42'))"
# Expected: True

python -c "from gaia_scorer import question_scorer; print(question_scorer('forty-two', '42'))"
# Expected: False (confirms number normalization is active)
```

### Integration

The verifier is called from `run_single_task` (see [benchmark.md](./benchmark.md#run_single_tasktask-condition-h_raw-h_improved-summarized_query-model)). It is called **exactly once per task per condition**, only when `terminated_by == "completed"`. For `loop_detected`, `max_steps_reached`, and `error`, the verifier is not called and `verifier_passed = "N/A"` is recorded.

The scorer is deterministic, so its output is not cached (re-invocation cost is negligible).

The bit-exact constraint is non-negotiable: do not refactor, do not fix style issues, do not add type hints. Preserve the file as-is for auditability. See the implementation checklist note in [checklist.md](./checklist.md).

---

## Known issue: temporal drift

GAIA was created in 2023. Some questions implicitly reference "the current moment" (e.g., "Who is the current CEO of X?"). Tavily will return 2026-era results; the ground truth in `Final answer` reflects 2023 facts. This is a known issue and is handled at the analysis layer, not in the loader. See [../analysis/temporal-drift.md](../analysis/temporal-drift.md).
