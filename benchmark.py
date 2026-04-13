"""
prompt-training/benchmark.py

A/B experiment runner for the inverse-model hypothesis.
  - Condition A: raw prompt -> ReAct agent (baseline)
  - Condition B: raw prompt -> inverse() -> improved prompt -> ReAct agent

Usage:
  python benchmark.py                    # run the full task set
  python benchmark.py --task 0           # run only one task (filtered-list index)
  python benchmark.py --task-id abc123   # run one task by GAIA task_id
  python benchmark.py --level 2          # use Level 2 tasks
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
import datetime
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from inverse import (
    MINIMAL_INSTRUCTION,
    _cache_hit_counters,
    _get_anthropic_client,
    _llm_token_accumulator,
    _record_llm_tokens,
    _run_state,
    detect_loop,
    inverse,
    measure_semantic_entropy,
)
from agent_tools import (
    TOOL_SCHEMA,
    tavily_extract,
    tavily_search,
)


# ---------------------------------------------------------------------------
# Top-level constants
# ---------------------------------------------------------------------------

#: Single LLM model used for ALL generation roles in v0:
#: inverse(), measure_semantic_entropy() sampling, and the ReAct agent.
#: Single-model policy -- see implementation/agent-tools.md.
MODEL: str = "claude-sonnet-4-6"

#: Entropy-measurement sample count. Floor for the noise-cancellation
#: argument. Smoke tests may override via --n-samples; result-producing
#: runs MUST use 10. See spec/measurement.md.
N_SAMPLES: int = 10

#: Cache version. Bump on any change to model, N_SAMPLES, clustering
#: threshold, or any prompt template that affects a cached value.
#: See implementation/caching.md.
CACHE_VERSION: str = "v2.9.0-001"

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
#: Adding output-only columns (e.g. trace_path) does not affect cache
#: geometry and does not require a CACHE_VERSION bump.
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
    "trace_path",
]

#: Whether caching is enabled. Set by CLI; mutated by --no-cache.
_caching_enabled: bool = True


# ---------------------------------------------------------------------------
# Cost monitoring constants (Phase 5)
# ---------------------------------------------------------------------------

#: LLM pricing as of 2026-04-08, looked up from official sources at
#: implementation time (NOT from training data). Keys are model
#: identifiers; values are (input_price_per_million, output_price_per_million)
#: in USD.
#:
#: Anthropic prices verified at:
#:   https://platform.claude.com/docs/en/about-claude/pricing
#: Together AI prices verified at:
#:   https://docs.together.ai/docs/serverless-models
#:
#: Pricing changes frequently. Re-verify before any result-producing
#: run. The lookup date is recorded in PRICING_LOOKUP_DATE so a stale
#: entry is at least visible.
LLM_PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.00, 15.00),
}

#: Together AI embedding pricing -- single rate, not split into input
#: and output. Embeddings have no "output tokens" in the LLM sense:
#: the output is the vector, which is not billed by token.
TOGETHER_EMBEDDING_PRICING_USD_PER_MTOK: float = 0.02

#: Date the above prices were last verified against official pricing
#: pages. Update whenever the constants are re-confirmed. log_cost_start
#: prints this so the operator can see how stale the pricing is.
PRICING_LOOKUP_DATE: str = "2026-04-08"


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
    """Cheap existence check (no JSON decode).

    Increments the per-subdir hit/miss counter for the cost-monitoring
    layer. Per operations/cost-monitoring.md, only ``cache_hit`` updates
    counters -- ``cache_get`` does NOT, because cache_get exceptions
    could mask misses as errors. Callers that want their lookups to
    appear in the hit-rate report should call cache_hit FIRST and only
    call cache_get on a hit.
    """
    if not _caching_enabled:
        return False
    if subdir not in _cache_hit_counters:
        _cache_hit_counters[subdir] = {"hits": 0, "misses": 0}
    exists = (CACHE_ROOT / subdir / f"{key}.json").exists()
    if exists:
        _cache_hit_counters[subdir]["hits"] += 1
    else:
        _cache_hit_counters[subdir]["misses"] += 1
    return exists


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


def load_gaia_tasks(level: int = 1) -> list[dict]:
    """Load GAIA validation set, truly text-only tasks for *level*.

    Column schema (confirmed):
        task_id, Question, Level, Final answer, file_name, file_path,
        Annotator Metadata

    Each returned dict is the GAIA row plus a derived ``max_steps`` key.
    Per-stage counts are logged to stdout for filter transparency.
    """
    if level not in (1, 2, 3):
        raise ValueError(
            f"level must be 1, 2, or 3 (got {level!r})"
        )

    from datasets import load_dataset  # type: ignore

    config = f"2023_level{level}"
    gaia = load_dataset("gaia-benchmark/GAIA", config, split="validation")

    # Stage 1: empty file_name
    no_file = [t for t in gaia if not t.get("file_name")]

    # Stage 2: no multimodal URLs in Question
    text_only = [t for t in no_file if is_truly_text_only(t)]

    total = len(gaia)
    excluded_by_url = len(no_file) - len(text_only)
    print(f"[load_gaia_tasks] Level {level} total: {total}")
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
        row["max_steps"] = _max_steps_for_level(int(row.get("Level", level)))
        enriched.append(row)

    # Assert task_id uniqueness — protects cache key integrity.
    seen_ids: set[str] = set()
    for row in enriched:
        tid = row["task_id"]
        if tid in seen_ids:
            raise RuntimeError(
                f"Duplicate task_id {tid!r} in level {level} — "
                "cache key integrity compromised"
            )
        seen_ids.add(tid)

    print(f"[load_gaia_tasks] level={level} filtered_count={len(enriched)}")
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


def run_task_both_conditions(task: dict, *, executor_model: str | None = None) -> list[dict]:
    """Run one task under both A and B. Returns a list of two rows."""
    task_key = _cache_key(task["task_id"], MODEL, N_SAMPLES)

    # Step 1: H_raw (shared between A and B). Use cache_hit() first
    # so the hit/miss counter increments for the cost-monitoring
    # layer; only call cache_get on a confirmed hit.
    if cache_hit("h_raw", task_key):
        cached = cache_get("h_raw", task_key)
        H_raw = cached["H_raw"]
        raw_prompt = cached["raw_prompt"]
    else:
        raw_prompt = task["Question"]
        # Token counts from this call are intentionally discarded at
        # the row level: row total_tokens accounts only for tokens
        # from inside run_react_loop. Pre/post-loop tokens are billed
        # by Phase 5's cost monitoring layer instead.
        H_raw, _ = measure_semantic_entropy(
            f"{MINIMAL_INSTRUCTION}\n\n{raw_prompt}",
            model=MODEL,
            n_samples=N_SAMPLES,
        )
        cache_set(
            "h_raw",
            task_key,
            {"H_raw": H_raw, "raw_prompt": raw_prompt},
        )

    # Step 2: Condition A
    row_A = run_single_task(
        task,
        condition="A",
        H_raw=H_raw,
        H_improved=H_raw,
        task_prompt=task["Question"],
        model=MODEL,
        executor_model=executor_model,
    )

    # Step 3: Condition B -- inverse() with its own cache. Same
    # cache_hit -> cache_get pattern as the H_raw lookup above so the
    # inverse cache hit rate is captured.
    if cache_hit("inverse", task_key):
        cached_inv = cache_get("inverse", task_key)
        improved_prompt = cached_inv["improved_prompt"]
    else:
        inverse_result = inverse(task["Question"], MODEL, N_SAMPLES)
        cache_set("inverse", task_key, inverse_result)
        improved_prompt = inverse_result["improved_prompt"]

    # H_improved: deliberately NOT cached -- inverse cache corruption
    # surfaces here. See implementation/caching.md. Token counts from
    # this call are intentionally discarded at the row level (see the
    # equivalent block above for H_raw).
    H_improved, _ = measure_semantic_entropy(
        f"{MINIMAL_INSTRUCTION}\n\n{improved_prompt}",
        model=MODEL,
        n_samples=N_SAMPLES,
    )

    row_B = run_single_task(
        task,
        condition="B",
        H_raw=H_raw,
        H_improved=H_improved,
        task_prompt=improved_prompt,
        model=MODEL,
        executor_model=executor_model,
    )

    return [row_A, row_B]


def run_single_task(
    task: dict,
    condition: str,
    H_raw: float,
    H_improved: float,
    task_prompt: str,
    model: str,
    *,
    executor_model: str | None = None,
) -> dict:
    """Run one task under one condition. Returns one TSV row."""
    result = run_react_loop(
        task_prompt=task_prompt,
        model=model,
        max_steps=task["max_steps"],
        H_raw=H_raw,
        task_id=task["task_id"],
        condition=condition,
        level=task["Level"],
        executor_model=executor_model,
    )

    # Phase 8.0: log per-step entropy curve to results/entropy_steps.tsv.
    # One row per step. Append mode; header written only if the file is new.
    _append_entropy_steps(
        task_id=task["task_id"],
        condition=condition,
        level=task["Level"],
        entropy_curve=result["entropy_curve"],
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
        "trace_path": (RESULTS_DIR / f"trace_{task['task_id']}_{condition}.jsonl").as_posix(),
    }


#: Phase 8.0: per-step entropy curve log. One row per entropy measurement.
ENTROPY_STEPS_PATH: Path = RESULTS_DIR / "entropy_steps.tsv"
_ENTROPY_STEPS_COLUMNS: list[str] = ["task_id", "condition", "level", "step", "H_n"]


def _append_entropy_steps(
    task_id: str,
    condition: str,
    level: object,
    entropy_curve: list[float],
) -> None:
    """Append per-step entropy rows to results/entropy_steps.tsv.

    Writes the header only if the file does not yet exist. One row per
    element in ``entropy_curve`` (step index is 1-based).
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not ENTROPY_STEPS_PATH.exists()
    with ENTROPY_STEPS_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=_ENTROPY_STEPS_COLUMNS, delimiter="\t"
        )
        if write_header:
            writer.writeheader()
        for step_index, H_n in enumerate(entropy_curve, start=1):
            writer.writerow(
                {
                    "task_id": task_id,
                    "condition": condition,
                    "level": level,
                    "step": step_index,
                    "H_n": H_n,
                }
            )


# ---------------------------------------------------------------------------
# Per-step trace sidecar (Phase 8.1.A)
# ---------------------------------------------------------------------------

#: Maximum character length for the observation field in a trace row.
#: Observations longer than this are truncated; observation_truncated
#: is set to True and observation_full_len records the original length.
_TRACE_OBS_CHAR_LIMIT: int = 8_000


def _write_trace_sidecar_meta(
    task_id: str,
    condition: str,
    level: object,
    head: str,
) -> Path:
    """Create a fresh trace sidecar and write the meta header line.

    Returns the ``Path`` so callers can pass it to ``_append_trace_step``.
    Raises on file errors — if the file cannot be created, the run should
    fail loudly.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    trace_path = RESULTS_DIR / f"trace_{task_id}_{condition}.jsonl"
    meta = {
        "_meta": True,
        "task_id": task_id,
        "condition": condition,
        "level": str(level),
        "head": head,
        "schema_version": 1,
    }
    with trace_path.open("w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
    return trace_path


def _append_trace_step(
    trace_path: Path,
    step: int,
    thought: str,
    action_name: str,
    action_input: dict,
    observation: object | None,
    entropy: float,
) -> None:
    """Append one step row to the trace sidecar JSONL file.

    Truncates *observation* to ``_TRACE_OBS_CHAR_LIMIT`` characters.
    For ``final_answer`` steps *observation* is ``None`` — stored as
    ``null`` with ``observation_truncated: false, observation_full_len: 0``.

    File errors are caught and logged to stderr so that trace failures
    never break the benchmark run.
    """
    if observation is None:
        obs_text: str | None = None
        obs_truncated = False
        obs_full_len = 0
    else:
        try:
            obs_text = json.dumps(observation, ensure_ascii=False, indent=2)
        except Exception:
            obs_text = repr(observation)
        obs_full_len = len(obs_text)
        if obs_full_len > _TRACE_OBS_CHAR_LIMIT:
            obs_text = obs_text[:_TRACE_OBS_CHAR_LIMIT]
            obs_truncated = True
        else:
            obs_truncated = False

    row = {
        "step": step,
        "thought": thought,
        "action_name": action_name,
        "action_args": action_input,
        "observation": obs_text,
        "observation_truncated": obs_truncated,
        "observation_full_len": obs_full_len,
        "entropy": entropy,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        with trace_path.open("a", encoding="utf-8", newline="") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[trace] WARNING: could not write step {step} to {trace_path}: {exc}",
              file=sys.stderr)


#: Per-call max_tokens for the agent's Thought + Action generation.
#: Big enough to fit a substantive Thought plus a tool_use block;
#: small enough that runaway responses are bounded.
_AGENT_RESPONSE_MAX_TOKENS: int = 2048

#: Forced-fallback instruction appended to the user message after the
#: no-tool-call retry has also failed. NOT contamination of the system
#: prompt -- MINIMAL_INSTRUCTION is untouched. This appears only in
#: the user message of one specific retry call inside one specific
#: error path.
_FORCED_FINAL_ANSWER_SUFFIX: str = (
    "\n\n[SYSTEM INSTRUCTION] You did not call any tool in your previous "
    "response. You MUST call the final_answer tool right now with your "
    "best-effort answer to the task above. Do not respond with text "
    "alone -- emit a tool_use block for final_answer immediately."
)


def _format_step_raw(
    thought: str,
    action_name: str,
    action_input: dict,
    observation: object | None,
) -> str:
    """Build the raw text record of one ReAct step.

    Appended to ``step_history`` so the next step's context is
    head + all previous steps.

    Format:
        Thought: <text>
        Action: <tool_name>(<json input>)
        Observation: <pretty json>     # omitted on the final_answer step

    All three parts are optional. An empty step (no thought, no action,
    no observation) returns the empty string -- this should not happen
    in practice but is handled defensively.
    """
    parts: list[str] = []
    if thought:
        parts.append(f"Thought: {thought}")
    if action_name:
        try:
            input_repr = json.dumps(action_input, ensure_ascii=False)
        except Exception:
            input_repr = repr(action_input)
        parts.append(f"Action: {action_name}({input_repr})")
    if observation is not None:
        try:
            obs_repr = json.dumps(observation, ensure_ascii=False, indent=2)
        except Exception:
            obs_repr = repr(observation)
        parts.append(f"Observation: {obs_repr}")
    return "\n".join(parts)


def _cached_tavily_search(query: str) -> object:
    """Cache-aware wrapper around agent_tools.tavily_search.

    Consults cache/tavily/ before making a network call. The Tavily
    response (raw dict) is the cached value, keyed on tool_name +
    query + CACHE_VERSION per implementation/caching.md.

    The wrapper exists in benchmark.py rather than agent_tools.py so
    that agent_tools.py stays standalone (no benchmark.py imports).
    Phase 4a defined agent_tools.py as a leaf module; Phase 5.5 keeps
    that constraint.

    Exceptions from tavily_search propagate as-is. Per
    operations/failure-modes.md, run_react_loop catches them and
    terminates the loop with terminated_by="error". cache_set is
    only reached AFTER tavily_search returns successfully, so a
    failed call never poisons the cache -- the next run with the
    same query will be a cache miss again and will retry.
    """
    key = _cache_key("tavily_search", query)
    if cache_hit("tavily", key):
        return cache_get("tavily", key)
    result = tavily_search(query)
    cache_set("tavily", key, result)
    return result


def _cached_tavily_extract(url: str) -> object:
    """Cache-aware wrapper around agent_tools.tavily_extract.

    Same caching pattern as _cached_tavily_search. See that
    function's docstring for the rationale on living in benchmark.py
    rather than agent_tools.py and for the failure semantics.
    """
    key = _cache_key("tavily_extract", url)
    if cache_hit("tavily", key):
        return cache_get("tavily", key)
    result = tavily_extract(url)
    cache_set("tavily", key, result)
    return result


def _call_agent_with_retries(
    client,
    model: str,
    context: str,
) -> tuple[str, object | None, int, str]:
    """Make one ReAct step's Thought + Action call to the Anthropic API.

    Implements the failure handling from operations/failure-modes.md:

    - **LLM empty response**: retry once. If still empty -> ``status="error"``.
    - **No tool call**: if the agent emits text without any tool_use
      block, retry once. If the retry also has no tool_use, send a
      forced final_answer fallback (one extra call with an explicit
      instruction in the user message). If the forced fallback also
      produces no tool_use, ``status="error"``.

    The system prompt is always ``MINIMAL_INSTRUCTION`` -- never
    modified, never contaminated with format guidance. The forced
    fallback's extra instruction lives in the USER message of one
    specific retry call.

    Returns ``(thought_text, tool_use_block, total_tokens, status)``
    where ``status`` is ``"ok"`` or ``"error"``. On error, the caller
    must terminate the loop with ``terminated_by="error"``.
    """
    total_tokens = 0
    base_messages = [{"role": "user", "content": context}]

    def _one_call(messages):
        nonlocal total_tokens
        response = client.messages.create(
            model=model,
            max_tokens=_AGENT_RESPONSE_MAX_TOKENS,
            temperature=0.0,
            system=MINIMAL_INSTRUCTION,
            tools=TOOL_SCHEMA,
            messages=messages,
        )
        in_tok = int(response.usage.input_tokens)
        out_tok = int(response.usage.output_tokens)
        total_tokens += in_tok + out_tok
        # Cost monitoring (Phase 5): record into the shared accumulator.
        # The agent's Thought/Action calls happen here in benchmark.py
        # rather than via inverse._llm_call, so this is a separate
        # recording site.
        _record_llm_tokens("anthropic", in_tok, out_tok)
        return response

    def _extract(response):
        """Pull text and tool_use blocks out of an Anthropic response."""
        if not response.content:
            return "", None
        text_blocks = [
            b.text
            for b in response.content
            if getattr(b, "type", None) == "text"
        ]
        tool_use_blocks = [
            b for b in response.content if getattr(b, "type", None) == "tool_use"
        ]
        text = "".join(text_blocks)
        tool_use = tool_use_blocks[0] if tool_use_blocks else None
        return text, tool_use

    # First attempt.
    response = _one_call(base_messages)

    # Empty-response retry path.
    if not response.content:
        response = _one_call(base_messages)
        if not response.content:
            return "", None, total_tokens, "error"

    text, tool_use = _extract(response)
    if tool_use is not None:
        return text, tool_use, total_tokens, "ok"

    # No-tool-call retry: agent emitted text but no tool_use block.
    response = _one_call(base_messages)
    text, tool_use = _extract(response)
    if tool_use is not None:
        return text, tool_use, total_tokens, "ok"

    # Forced final_answer fallback: one extra call with explicit
    # instruction in the user message.
    forced_messages = [
        {"role": "user", "content": context + _FORCED_FINAL_ANSWER_SUFFIX}
    ]
    response = _one_call(forced_messages)
    text, tool_use = _extract(response)
    if tool_use is not None:
        return text, tool_use, total_tokens, "ok"

    # Forced fallback also failed.
    return text, None, total_tokens, "error"


def run_react_loop(
    task_prompt: str,
    model: str,
    max_steps: int,
    H_raw: float,
    *,
    task_id: str,
    condition: str,
    level: object,
    executor_model: str | None = None,
) -> dict:
    """The ReAct loop.

    Phase 8.0: the context is Head + full step history (no Body
    summarisation, no Tail trimming). Entropy is measured AFTER the
    just-completed step has been appended to step_history, so H_n
    reflects the agent's state including that step.

    Parameters
    ----------
    task_prompt : str
        The full task prompt (raw question in Condition A, improved
        prompt in Condition B). Locked at the start of execution and
        reused verbatim as the agent's goal anchor.
    model : str
        The single LLM model used for the Thought/Action calls AND for
        measure_semantic_entropy inside the loop. Single-model policy
        per implementation/agent-tools.md.
    max_steps : int
        Per-task step budget. Derived from GAIA Level (15 for Level 1).
        See implementation/gaia-integration.md.
    H_raw : float
        The per-task baseline used by detect_loop. The SAME H_raw is
        passed in for both conditions A and B -- never H_improved in B,
        per spec/loop-detection.md (c).
    task_id : str
        GAIA task identifier. Used for trace sidecar file naming.
    condition : str
        "A" or "B". Used for trace sidecar file naming.
    level : object
        GAIA level (e.g. 1, 2, 3). Recorded in trace meta header.

    Returns
    -------
    dict with keys:
        - terminated_by  : "completed" | "loop_detected" | "max_steps_reached" | "error"
        - final_answer   : str | None  (populated iff terminated_by == "completed")
        - entropy_curve  : list[float]  (H_n at every step, in order)
        - total_tokens   : int  (sum across every LLM call inside this loop)
    """
    # The Head is constructed ONCE here and reused for every step's
    # context build. MINIMAL_INSTRUCTION is prepended so the agent's
    # user message and the entropy measurement input share the same
    # shape.
    head: str = f"{MINIMAL_INSTRUCTION}\n\n{task_prompt}"

    # Phase 8.1.A: write the trace sidecar meta header. This CAN raise
    # — if the file cannot be created, fail loudly.
    trace_path: Path = _write_trace_sidecar_meta(task_id, condition, level, head)

    entropy_curve: list[float] = []
    total_tokens: int = 0

    # Full history of formatted step records (Thought/Action/Observation
    # blocks, in order). Grows by one entry per completed step.
    step_history: list[str] = []

    client = _get_anthropic_client()

    for step_num in range(1, max_steps + 1):
        # Build the agent's context: Head + everything we have done so far.
        if step_history:
            context = head + "\n\n" + "\n\n".join(step_history)
        else:
            context = head

        # Thought + Action via the Anthropic Messages API.
        thought_text, tool_use, call_tokens, status = (
            _call_agent_with_retries(client, executor_model or model, context)
        )
        total_tokens += call_tokens

        if status == "error":
            return {
                "terminated_by": "error",
                "final_answer": None,
                "entropy_curve": entropy_curve,
                "total_tokens": total_tokens,
            }

        # tool_use is guaranteed non-None here when status == "ok".
        action_name: str = tool_use.name
        action_input: dict = dict(tool_use.input or {})

        # Tool dispatch with final_answer interception.
        observation: object | None = None
        pending_completion: bool = False
        captured_answer: str | None = None

        if action_name == "final_answer":
            # INTERCEPT — do NOT dispatch the Python passthrough.
            pending_completion = True
            captured_answer = action_input.get("answer", "")
        elif action_name == "tavily_search":
            try:
                observation = _cached_tavily_search(
                    action_input.get("query", "")
                )
            except Exception:
                return {
                    "terminated_by": "error",
                    "final_answer": None,
                    "entropy_curve": entropy_curve,
                    "total_tokens": total_tokens,
                }
        elif action_name == "tavily_extract":
            try:
                observation = _cached_tavily_extract(
                    action_input.get("url", "")
                )
            except Exception:
                return {
                    "terminated_by": "error",
                    "final_answer": None,
                    "entropy_curve": entropy_curve,
                    "total_tokens": total_tokens,
                }
        else:
            # Unknown tool name. Defensive: TOOL_SCHEMA only exposes
            # three tools, so this should be unreachable.
            return {
                "terminated_by": "error",
                "final_answer": None,
                "entropy_curve": entropy_curve,
                "total_tokens": total_tokens,
            }

        # Build the raw text record for THIS step and append it to
        # step_history BEFORE the entropy measurement, so H_n reflects
        # the agent's state including the just-completed step.
        current_step_raw = _format_step_raw(
            thought=thought_text,
            action_name=action_name,
            action_input=action_input,
            observation=observation,
        )
        step_history.append(current_step_raw)

        updated_context = head + "\n\n" + "\n\n".join(step_history)

        H_n, h_n_tokens = measure_semantic_entropy(
            updated_context,
            model=model,
            n_samples=N_SAMPLES,
        )
        entropy_curve.append(H_n)
        total_tokens += h_n_tokens

        # Phase 8.1.A: append per-step trace row. Wrapped in try/except
        # so trace failures never break the benchmark run.
        try:
            _append_trace_step(
                trace_path,
                step=step_num,
                thought=thought_text,
                action_name=action_name,
                action_input=action_input,
                observation=observation,
                entropy=H_n,
            )
        except Exception as exc:
            print(f"[trace] WARNING: _append_trace_step failed at step {step_num}: {exc}",
                  file=sys.stderr)

        # Loop detection. Runs even on a final_answer step; the loop
        # detector wins over a simultaneous final_answer, per
        # spec/loop-detection.md and react-loop.md §[g].
        loop_result = detect_loop(
            entropy_curve, H_raw, alpha=0.3, window=3
        )
        if loop_result["is_loop"]:
            return {
                "terminated_by": "loop_detected",
                "final_answer": None,
                "entropy_curve": entropy_curve,
                "total_tokens": total_tokens,
            }

        # Completion check.
        if pending_completion:
            return {
                "terminated_by": "completed",
                "final_answer": captured_answer,
                "entropy_curve": entropy_curve,
                "total_tokens": total_tokens,
            }

        # max_steps check.
        if step_num >= max_steps:
            return {
                "terminated_by": "max_steps_reached",
                "final_answer": None,
                "entropy_curve": entropy_curve,
                "total_tokens": total_tokens,
            }

    # Defensive: the max_steps check inside the loop should always
    # exit before falling out of the for-loop.
    return {
        "terminated_by": "max_steps_reached",
        "final_answer": None,
        "entropy_curve": entropy_curve,
        "total_tokens": total_tokens,
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


def _tavily_usage_credits() -> int | None:
    """Fetch the current Tavily credit balance via the /usage endpoint.

    Returns the integer credit count, or ``None`` if the call fails
    for any reason (key missing, network error, unexpected response
    shape). Failure is non-fatal -- the run continues, but the cost
    log records "Tavily delta unavailable" so the operator knows
    something went wrong without crashing the run.

    Uses ``urllib.request`` from stdlib (no new dependency on
    tavily-python). The endpoint is GET https://api.tavily.com/usage
    with ``Authorization: Bearer $TAVILY_API_KEY``.

    Note: the /usage response shape was locked down at Phase 6b Block 6.
    The account-level counter lives at ``data["account"]["plan_usage"]``
    (current) and ``data["account"]["plan_limit"]`` (quota). We read
    plan_usage primarily; key.usage is a secondary fallback for
    per-key metering. Both can lag real-time usage by several seconds
    (eventual consistency observed during Phase 6b).
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None

    try:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            "https://api.tavily.com/usage",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            # Primary: account.plan_usage (verified via Phase 6b Block 6).
            account = data.get("account")
            if isinstance(account, dict) and "plan_usage" in account:
                return int(account["plan_usage"])
            # Secondary fallback: key.usage (per-key counter, may be eventual).
            key_info = data.get("key")
            if isinstance(key_info, dict) and "usage" in key_info:
                return int(key_info["usage"])
            # Unknown shape -- prefer None over a guess.
            return None
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        ValueError,
        KeyError,
        TimeoutError,
        OSError,
    ):
        return None


def log_cost_start() -> None:
    """Initialize cost monitoring at the start of a benchmark run.

    Resets the per-provider token accumulator, the cache hit
    counters, and the per-run scratchpad. Captures the starting
    Tavily credit balance into ``_run_state``.

    Per operations/cost-monitoring.md, this runs ONCE per benchmark
    invocation, not per task.

    IMPORTANT: uses ``.clear()`` rather than reassignment so the
    shared-state references in inverse.py and benchmark.py stay in
    sync. See inverse.py "Cost monitoring shared state" for the
    rationale.
    """
    _llm_token_accumulator.clear()
    _cache_hit_counters.clear()
    _run_state.clear()

    tavily_start = _tavily_usage_credits()
    _run_state["tavily_credits_at_start"] = tavily_start
    _run_state["started_at"] = time.time()

    print("[cost] run start")
    if tavily_start is not None:
        print(f"[cost]   Tavily credits at start: {tavily_start}")
    else:
        print(
            "[cost]   Tavily /usage unavailable "
            "(key missing or endpoint failed)"
        )
    print(f"[cost]   model: {MODEL}")
    print(f"[cost]   N_SAMPLES: {N_SAMPLES}")
    print(f"[cost]   CACHE_VERSION: {CACHE_VERSION}")
    print(f"[cost]   pricing lookup date: {PRICING_LOOKUP_DATE}")


def log_cost_end() -> None:
    """Compute and print the four cost categories at run end.

    Reads from ``_llm_token_accumulator``, ``_cache_hit_counters``,
    and ``_run_state``. Writes a single human-readable summary to
    stdout and a detailed log file to ``results/run_<timestamp>.log``
    via ``_write_run_log``. Cost data is NOT written to the TSV
    (the TSV is per-task-per-condition; cost is per-run).
    """
    elapsed = time.time() - _run_state.get("started_at", time.time())

    # --- 1. Tavily delta ---
    tavily_end = _tavily_usage_credits()
    tavily_start = _run_state.get("tavily_credits_at_start")
    if tavily_start is not None and tavily_end is not None:
        tavily_delta: int | None = tavily_end - tavily_start
        tavily_str = f"{tavily_delta} credits"
    else:
        tavily_delta = None
        tavily_str = "unavailable"

    # --- 2. LLM token totals (across all providers) ---
    total_input = sum(
        p["input_tokens"] for p in _llm_token_accumulator.values()
    )
    total_output = sum(
        p["output_tokens"] for p in _llm_token_accumulator.values()
    )

    # --- 3. USD estimate, per provider ---
    total_usd = 0.0
    per_provider_usd: dict[str, float] = {}
    for provider, counts in _llm_token_accumulator.items():
        if provider == "anthropic":
            pricing = LLM_PRICING_USD_PER_MTOK.get(MODEL)
            if pricing is None:
                print(
                    f"[cost]   WARNING: no pricing entry for "
                    f"MODEL={MODEL!r}. USD estimate for anthropic "
                    "will be 0."
                )
                per_provider_usd[provider] = 0.0
                continue
            input_price, output_price = pricing
            usd = (
                counts["input_tokens"] / 1_000_000 * input_price
                + counts["output_tokens"] / 1_000_000 * output_price
            )
        elif provider == "together":
            # Together embeddings: single rate, no input/output split.
            # semantic_cluster records embedding tokens under
            # input_tokens with output_tokens=0; sum both for safety
            # in case a future call site puts tokens on the other side.
            total_embedding_tokens = (
                counts["input_tokens"] + counts["output_tokens"]
            )
            usd = (
                total_embedding_tokens
                / 1_000_000
                * TOGETHER_EMBEDDING_PRICING_USD_PER_MTOK
            )
        else:
            print(
                f"[cost]   WARNING: no pricing for provider "
                f"{provider!r}. USD estimate for this provider will "
                "be 0."
            )
            usd = 0.0
        per_provider_usd[provider] = usd
        total_usd += usd

    # --- 4. Cache hit rates ---
    cache_summary: dict[str, str] = {}
    for subdir, counts in _cache_hit_counters.items():
        total = counts["hits"] + counts["misses"]
        if total > 0:
            rate = counts["hits"] / total
            cache_summary[subdir] = (
                f"{counts['hits']}/{total} ({rate:.1%})"
            )
        else:
            cache_summary[subdir] = "0/0 (n/a)"

    # --- Stdout summary lines (the four headline numbers) ---
    print()
    print("[cost] run end")
    print(f"[cost]   elapsed: {elapsed:.1f}s")
    print(f"[cost]   Tavily delta: {tavily_str}")
    print(f"[cost]   LLM input tokens:  {total_input:,}")
    print(f"[cost]   LLM output tokens: {total_output:,}")
    for provider, usd in per_provider_usd.items():
        counts = _llm_token_accumulator[provider]
        print(
            f"[cost]   {provider}: "
            f"in={counts['input_tokens']:,} "
            f"out={counts['output_tokens']:,} "
            f"= ${usd:.4f}"
        )
    print(f"[cost]   estimated total USD: ${total_usd:.4f}")
    print("[cost]   cache hit rates:")
    for subdir, summary in cache_summary.items():
        print(f"[cost]     {subdir}: {summary}")
    print()

    # --- Detailed log file (one per run) ---
    _write_run_log(
        tavily_delta=tavily_delta,
        total_input=total_input,
        total_output=total_output,
        per_provider_usd=per_provider_usd,
        total_usd=total_usd,
        cache_summary=cache_summary,
        elapsed=elapsed,
    )


def _write_run_log(
    *,
    tavily_delta: int | None,
    total_input: int,
    total_output: int,
    per_provider_usd: dict[str, float],
    total_usd: float,
    cache_summary: dict[str, str],
    elapsed: float,
) -> None:
    """Write the detailed cost log to ``results/run_<timestamp>.log``.

    One file per benchmark invocation. Format is human-readable, not
    structured JSON -- this file is for the operator's eyes during
    review, not for downstream processing. (The TSV is the structured
    artifact.)
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = RESULTS_DIR / f"run_{timestamp}.log"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "prompt-training run log",
        f"  timestamp:        {timestamp}",
        f"  model:            {MODEL}",
        f"  N_SAMPLES:        {N_SAMPLES}",
        f"  CACHE_VERSION:    {CACHE_VERSION}",
        f"  SEED:             {SEED}",
        f"  pricing date:     {PRICING_LOOKUP_DATE}",
        f"  elapsed:          {elapsed:.1f}s",
        "",
        "Tavily delta:       "
        + (
            f"{tavily_delta} credits"
            if tavily_delta is not None
            else "unavailable"
        ),
        f"LLM input tokens:   {total_input:,}",
        f"LLM output tokens:  {total_output:,}",
        f"Total USD estimate: ${total_usd:.4f}",
        "",
        "Per-provider breakdown:",
    ]
    for provider, usd in per_provider_usd.items():
        counts = _llm_token_accumulator[provider]
        lines.append(
            f"  {provider}: in={counts['input_tokens']:,} "
            f"out={counts['output_tokens']:,} = ${usd:.4f}"
        )
    lines.append("")
    lines.append("Cache hit rates:")
    for subdir, summary in cache_summary.items():
        lines.append(f"  {subdir}: {summary}")
    lines.append("")

    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[cost]   detailed log: {log_path}")


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
        "--task-id",
        type=str,
        default=None,
        help=(
            "Run only one task by GAIA task_id. "
            "Mutually exclusive with --task."
        ),
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="GAIA difficulty level to load (default: 1).",
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
        "--executor-model",
        type=str,
        default=None,
        help="Override the executor model (default: same as --model).",
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

    # Load .env from the project root. python-dotenv is in pyproject.toml
    # dependencies, so it's guaranteed available after `pip install -e .`.
    # This makes `python benchmark.py ...` work directly without needing
    # an inline .env loader wrapper.
    from dotenv import load_dotenv
    load_dotenv()

    args = _parse_args(argv)
    if args.model:
        MODEL = args.model
    if args.executor_model is None:
        args.executor_model = MODEL
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

    # Mutual exclusion: --task (index) vs --task-id (string id)
    if args.task is not None and args.task_id is not None:
        print(
            "Error: --task and --task-id are mutually exclusive. "
            "Use one or the other.",
            file=sys.stderr,
        )
        return 1

    if args.task is not None or args.task_id is not None or args.condition is not None:
        # Single-task / single-condition path is a Phase 6 smoke-test
        # convenience and is not the result-producing path.
        tasks = load_gaia_tasks(level=args.level)
        tasks = apply_sample_size_contingency(tasks)
        if args.task_id is not None:
            matched = [t for t in tasks if t["task_id"] == args.task_id]
            if not matched:
                sample_ids = [t["task_id"] for t in tasks[:5]]
                print(
                    f"Error: task_id {args.task_id!r} not found in "
                    f"level {args.level} tasks. "
                    f"First 5 available: {sample_ids}",
                    file=sys.stderr,
                )
                return 1
            tasks = matched
        elif args.task is not None:
            tasks = [tasks[args.task]]
        log_cost_start()
        rows: list[dict] = []
        for task in tasks:
            both = run_task_both_conditions(task, executor_model=args.executor_model)
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
