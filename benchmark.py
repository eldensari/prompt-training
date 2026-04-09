"""
prompt-training/benchmark.py

A/B experiment runner for the inverse-model hypothesis.
  - Condition A: raw prompt -> ReAct agent (baseline)
  - Condition B: raw prompt -> inverse() -> improved prompt -> ReAct agent

Usage:
  python benchmark.py                    # run the full task set
  python benchmark.py --task 0           # run only one task (filtered-list index)
  python benchmark.py --condition A      # only condition A
  python benchmark.py --condition B      # only condition B
  python benchmark.py --model sonnet     # specific model
  python benchmark.py --n-samples 5      # entropy sample count (smoke test)
  python benchmark.py --no-cache         # disable all caches

Required environment variables (.env):
  ANTHROPIC_API_KEY=sk-ant-...
  TOGETHER_API_KEY=...           (required for embedding-based clustering)
  HF_TOKEN=...                   (required for GAIA dataset access)
  TAVILY_API_KEY=tvly-...        (required for agent web search; Phase 4)

Phase 3 status: this skeleton exposes run_experiment, run_task_both_conditions
and run_single_task end-to-end with run_react_loop STUBBED. Importing the
module does not require any API keys or installed dependencies.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from inverse import (
    MINIMAL_INSTRUCTION,
    inverse,
    measure_semantic_entropy,
    summarize_to_head,
)


# ---------------------------------------------------------------------------
# Top-level constants
# ---------------------------------------------------------------------------

#: Single LLM model used for ALL generation roles in v0:
#: inverse(), summarize_to_head(), measure_semantic_entropy() sampling,
#: and the ReAct agent. Single-model policy -- see
#: implementation/agent-tools.md.
MODEL: str = "claude-sonnet-4-6"

#: Entropy-measurement sample count. Floor for the noise-cancellation
#: argument. Smoke tests may override via --n-samples; result-producing
#: runs MUST use 10. See spec/measurement.md.
N_SAMPLES: int = 10

#: Cache version. Bump on any change to model, N_SAMPLES, clustering
#: threshold, or any prompt template that affects a cached value.
#: See implementation/caching.md.
CACHE_VERSION: str = "v2.8.0-001"

#: Seed for any future stochastic operation. The embedder and clusterer
#: are deterministic by construction; this seed exists as a fixed entry
#: point for numpy / random.
SEED: int = 42

#: Cache root directory. Three subdirs: inverse/, h_raw/, tavily/.
CACHE_ROOT: Path = Path("cache")

#: Results directory.
RESULTS_DIR: Path = Path("results")

#: TSV output path.
TSV_PATH: Path = RESULTS_DIR / "results.tsv"

#: TSV column order. NOT editable without a version bump (see
#: operations/experiment-rules.md).
TSV_COLUMNS: list[str] = [
    "task_id",
    "level",
    "condition",
    "H_raw",
    "H_improved",
    "delta_H",
    "loop_count",
    "total_tokens",
    "terminated_by",
    "verifier_passed",
]

#: Whether caching is enabled. Set by CLI; mutated by --no-cache.
_caching_enabled: bool = True


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

#: Patterns for external multimodal resources that Tavily cannot handle.
#: These appear in the Question body even when file_name is empty.
#: Editable -- false-positive filter, not part of the hypothesis.
MULTIMODAL_URL_PATTERNS: list[str] = [
    r"youtube\.com/watch",
    r"youtu\.be/",
    r"\.mp[34]\b",  # mp3, mp4
    r"\.wav\b",
    r"vimeo\.com/",
]


def _cache_key(*parts: Any) -> str:
    """Build a deterministic cache key from arbitrary parts.

    The cache version is folded into every key so that bumping
    ``CACHE_VERSION`` invalidates the entire cache surface in one step.
    """
    payload = "||".join(str(p) for p in parts) + f"||v={CACHE_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def cache_get(subdir: str, key: str):
    """Return cached value or None on miss.

    ``subdir`` must be one of {'inverse', 'h_raw', 'tavily'}. When
    caching is disabled by ``--no-cache``, every call returns None.
    """
    if not _caching_enabled:
        return None
    path = CACHE_ROOT / subdir / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def cache_set(subdir: str, key: str, value) -> None:
    """Store value at ``cache/{subdir}/{key}.json``.

    Caller decides contents (must be JSON-serializable). Disabled when
    ``--no-cache`` is passed.
    """
    if not _caching_enabled:
        return
    path = CACHE_ROOT / subdir / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def cache_hit(subdir: str, key: str) -> bool:
    """Cheap existence check (no JSON decode). Used by cost monitoring."""
    if not _caching_enabled:
        return False
    return (CACHE_ROOT / subdir / f"{key}.json").exists()


# ---------------------------------------------------------------------------
# GAIA loader (two-stage text-only filter)
# ---------------------------------------------------------------------------


def is_truly_text_only(task: dict) -> bool:
    """Text-only means BOTH:
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


def load_gaia_tasks() -> list[dict]:
    """Load GAIA validation set Level 1, truly text-only tasks.

    Column schema (confirmed):
        task_id, Question, Level, Final answer, file_name, file_path,
        Annotator Metadata
    Level 1 validation total: 53 tasks.

    Each returned dict is the GAIA row plus a derived ``max_steps`` key.
    Per-stage counts are logged to stdout for filter transparency.
    """
    from datasets import load_dataset  # type: ignore

    gaia = load_dataset(
        "gaia-benchmark/GAIA", "2023_level1", split="validation"
    )

    # Stage 1: empty file_name
    no_file = [t for t in gaia if not t.get("file_name")]

    # Stage 2: no multimodal URLs in Question
    text_only = [t for t in no_file if is_truly_text_only(t)]

    total = len(gaia)
    excluded_by_url = len(no_file) - len(text_only)
    print(f"[load_gaia_tasks] Level 1 total: {total}")
    print(f"[load_gaia_tasks] After file_name filter: {len(no_file)}")
    print(f"[load_gaia_tasks] After multimodal URL filter: {len(text_only)}")
    print(
        f"[load_gaia_tasks] Excluded due to multimodal URLs in question body:"
        f" {excluded_by_url}"
    )

    # Annotate each task with derived fields the runner expects.
    enriched: list[dict] = []
    for t in text_only:
        row = dict(t)
        row["max_steps"] = _max_steps_for_level(int(row.get("Level", 1)))
        enriched.append(row)
    return enriched


def _max_steps_for_level(level: int) -> int:
    """Per implementation/gaia-integration.md."""
    return {1: 15, 2: 25, 3: 50}.get(level, 15)


def apply_sample_size_contingency(tasks: list[dict]) -> list[dict]:
    """Apply the sample-size contingency rule from gaia-integration.md.

    Applied once at first load and then locked. The decision is logged
    so reruns can confirm they target the identical set.

    Rules:
      1. Text-only Level 1 >= 30 -> proceed as-is.
      2. Text-only Level 1 in [20, 29] -> add Level 2 text-only tasks
         until the combined count reaches 30.
      3. Text-only Level 1 < 20 -> proceed as-is, but the v0 results
         must be reported as descriptive only (no statistical tests).
    """
    n = len(tasks)
    if n >= 30:
        print(
            f"[contingency] {n} text-only Level 1 tasks -- proceeding as-is."
        )
        return tasks
    if 20 <= n < 30:
        print(
            f"[contingency] {n} text-only Level 1 tasks -- topping up "
            "with text-only Level 2 to reach 30."
        )
        return _top_up_with_level2(tasks, target=30)
    print(
        f"[contingency] {n} text-only Level 1 tasks -- below 20. "
        "Run will produce descriptive results only (no statistical tests)."
    )
    return tasks


def _top_up_with_level2(level1_tasks: list[dict], *, target: int) -> list[dict]:
    """Helper for contingency rule #2: pad with text-only Level 2 tasks."""
    from datasets import load_dataset  # type: ignore

    needed = target - len(level1_tasks)
    if needed <= 0:
        return level1_tasks

    level2 = load_dataset(
        "gaia-benchmark/GAIA", "2023_level2", split="validation"
    )
    text_only_l2 = [t for t in level2 if is_truly_text_only(t)]
    print(
        f"[contingency] Level 2 text-only available: {len(text_only_l2)}; "
        f"need {needed} to reach {target}."
    )
    pad: list[dict] = []
    for t in text_only_l2[:needed]:
        row = dict(t)
        row["max_steps"] = _max_steps_for_level(int(row.get("Level", 2)))
        pad.append(row)
    return level1_tasks + pad


# ---------------------------------------------------------------------------
# Runner hierarchy
# ---------------------------------------------------------------------------


def run_experiment() -> None:
    """Top-level: iterate over all tasks, run both conditions, write TSV."""
    tasks = load_gaia_tasks()
    tasks = apply_sample_size_contingency(tasks)

    log_cost_start()
    rows: list[dict] = []
    for task in tasks:
        rows.extend(run_task_both_conditions(task))
    write_tsv(rows)
    log_cost_end()


def run_task_both_conditions(task: dict) -> list[dict]:
    """Run one task under both A and B. Returns a list of two rows."""
    task_key = _cache_key(task["task_id"], MODEL, N_SAMPLES)

    # Step 1: H_raw (shared between A and B)
    cached = cache_get("h_raw", task_key)
    if cached is not None:
        H_raw = cached["H_raw"]
        raw_summary = cached["raw_summary"]
    else:
        raw_summary = summarize_to_head(
            task["Question"], max_tokens=80, model=MODEL
        )
        H_raw = measure_semantic_entropy(
            f"{MINIMAL_INSTRUCTION}\n\n{raw_summary}",
            model=MODEL,
            n_samples=N_SAMPLES,
        )
        cache_set(
            "h_raw",
            task_key,
            {"H_raw": H_raw, "raw_summary": raw_summary},
        )

    # Step 2: Condition A
    row_A = run_single_task(
        task,
        condition="A",
        H_raw=H_raw,
        H_improved=H_raw,
        summarized_query=raw_summary,
        model=MODEL,
    )

    # Step 3: Condition B -- inverse() with its own cache
    cached_inv = cache_get("inverse", task_key)
    if cached_inv is not None:
        improved_prompt = cached_inv["improved_prompt"]
    else:
        inverse_result = inverse(task["Question"], MODEL, N_SAMPLES)
        cache_set("inverse", task_key, inverse_result)
        improved_prompt = inverse_result["improved_prompt"]

    # H_improved: deliberately NOT cached -- inverse cache corruption
    # surfaces here. See implementation/caching.md.
    improved_summary = summarize_to_head(
        improved_prompt, max_tokens=80, model=MODEL
    )
    H_improved = measure_semantic_entropy(
        f"{MINIMAL_INSTRUCTION}\n\n{improved_summary}",
        model=MODEL,
        n_samples=N_SAMPLES,
    )

    row_B = run_single_task(
        task,
        condition="B",
        H_raw=H_raw,
        H_improved=H_improved,
        summarized_query=improved_summary,
        model=MODEL,
    )

    return [row_A, row_B]


def run_single_task(
    task: dict,
    condition: str,
    H_raw: float,
    H_improved: float,
    summarized_query: str,
    model: str,
) -> dict:
    """Run one task under one condition. Returns one TSV row."""
    result = run_react_loop(
        summarized_query=summarized_query,
        model=model,
        max_steps=task["max_steps"],
        H_raw=H_raw,
    )

    # Verifier: called exactly once, only on completed.
    if result["terminated_by"] == "completed":
        from gaia_scorer import question_scorer  # type: ignore

        verifier_passed = question_scorer(
            result["final_answer"], task["Final answer"]
        )
    else:
        verifier_passed = "N/A"

    return {
        "task_id": task["task_id"],
        "level": task["Level"],
        "condition": condition,
        "H_raw": H_raw,
        "H_improved": H_improved,
        "delta_H": (H_raw - H_improved) if condition == "B" else 0,
        "loop_count": 1 if result["terminated_by"] == "loop_detected" else 0,
        "total_tokens": result["total_tokens"],
        "terminated_by": result["terminated_by"],
        "verifier_passed": verifier_passed,
    }


def run_react_loop(
    summarized_query: str,
    model: str,
    max_steps: int,
    H_raw: float,
) -> dict:
    """STUB. Phase 4 will implement the real ReAct loop.

    Returns a placeholder so the rest of the pipeline can be exercised
    end-to-end. The shape matches the contract in
    implementation/react-loop.md.
    """
    return {
        "terminated_by": "completed",
        "final_answer": "STUB",
        "entropy_curve": [],
        "total_tokens": 0,
    }


# ---------------------------------------------------------------------------
# TSV writer
# ---------------------------------------------------------------------------


def write_tsv(rows: list[dict]) -> None:
    """Write rows to results/results.tsv with the locked column order."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with TSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=TSV_COLUMNS, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"[write_tsv] Wrote {len(rows)} rows to {TSV_PATH}")


# ---------------------------------------------------------------------------
# Cost monitoring (stubs for Phase 5)
# ---------------------------------------------------------------------------


def log_cost_start() -> None:
    """Phase 5 will populate this with the Tavily /usage call and the
    LLM-token accumulator initialisation."""
    print("[cost] run start (Phase 5 will populate this)")


def log_cost_end() -> None:
    """Phase 5 will populate this with the Tavily /usage delta and the
    per-provider LLM token + USD summary."""
    print("[cost] run end (Phase 5 will populate this)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="benchmark.py",
        description="A/B experiment runner for the inverse-model hypothesis.",
    )
    parser.add_argument(
        "--task",
        type=int,
        default=None,
        help="Run only one task (index into the filtered task list).",
    )
    parser.add_argument(
        "--condition",
        choices=["A", "B"],
        default=None,
        help="Run only one condition.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the MODEL constant for this run.",
    )
    parser.add_argument(
        "--n-samples",
        type=int,
        default=None,
        help=(
            "Override N_SAMPLES (entropy sample count). "
            "Smoke-test only -- result-producing runs must use 10."
        ),
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable all caches for this run (cold path).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    global MODEL, N_SAMPLES, _caching_enabled

    args = _parse_args(argv)
    if args.model:
        MODEL = args.model
    if args.n_samples:
        N_SAMPLES = args.n_samples
    if args.no_cache:
        _caching_enabled = False

    # Seed numpy/random where applicable. Most of the pipeline is
    # deterministic by construction; this is the fixed entry point.
    try:
        import numpy as np  # type: ignore

        np.random.seed(SEED)
    except ImportError:
        pass
    import random as _random
    _random.seed(SEED)

    if args.task is not None or args.condition is not None:
        # Single-task / single-condition path is a Phase 6 smoke-test
        # convenience and is not the result-producing path.
        tasks = load_gaia_tasks()
        tasks = apply_sample_size_contingency(tasks)
        if args.task is not None:
            tasks = [tasks[args.task]]
        log_cost_start()
        rows: list[dict] = []
        for task in tasks:
            both = run_task_both_conditions(task)
            if args.condition is not None:
                both = [r for r in both if r["condition"] == args.condition]
            rows.extend(both)
        write_tsv(rows)
        log_cost_end()
        return 0

    run_experiment()
    return 0


if __name__ == "__main__":
    sys.exit(main())
