"""
prompt-training/inverse.py

Vague prompt -> improved prompt converter (inverse model).
Entropy is measured only at the raw prompt and the improved prompt.

Public interface (call signatures match implementation/inverse.md):
    MINIMAL_INSTRUCTION : str
    summarize_to_head(text, max_tokens=80, *, model)            -> tuple[str, int]
    summarize_to_body(prev, displaced, *, model, max_tokens=70) -> tuple[str, int]
    trim_to_tail(text, max_tokens=150)                          -> str
    semantic_cluster(responses)                                 -> list[int]
    measure_semantic_entropy(input_context, model, n_samples=10)-> tuple[float, int]
    inverse(raw_prompt, model, n_samples=10)                    -> dict
    detect_loop(entropy_history, H_raw, alpha=0.3, window=3)    -> dict

Token-counting note: as of Phase 4b, summarize_to_head, summarize_to_body,
and measure_semantic_entropy all return ``(value, total_tokens)`` tuples.
The second element is the sum of input + output tokens from every LLM
call inside the function. inverse()'s ``total_tokens_used`` field now
correctly accounts for ALL of: the 2 summarize_to_head calls, the 2
measure_semantic_entropy calls, and the 3 Target/Invert/Compose calls.
(Pre-4b, only the 3 generation calls were counted, undercounting B's
true token cost.)

Design notes:
  * No conversation history is shared between the three inverse-model
    steps. The previous step's output is explicitly injected as text
    into the next step's prompt template (Prompt Chaining via Explicit
    Injection -- see spec/hypothesis.md).
  * All LLM calls inside inverse() use temperature=0. Entropy-sampling
    calls use temperature=0.7.
  * The summarizer is at temperature=0; its variance is intentionally
    absorbed into H, where it cancels in delta_H -- see
    spec/measurement.md.
  * H_raw uses H_raw as the loop-detection reference in BOTH conditions
    A and B -- see spec/loop-detection.md and detect_loop() below.
  * Heavy dependencies (anthropic, openai, sklearn, numpy) are
    lazy-imported inside the functions that need them, so importing
    this module never requires API keys or installed packages.
    Note: `openai` is the client library used to call the Together AI
    embeddings endpoint, which is OpenAI-compatible. v0 does not call
    OpenAI's own models — see spec/measurement.md "Implementation note"
    in the Clustering section.

Usage example (after .env is populated):

    from inverse import inverse
    result = inverse("I want to cut waste. I have 3 cards.",
                     model="claude-sonnet-4-6")
    print(result["improved_prompt"])
    print(result["H_raw"], result["H_improved"], result["delta_H"])
"""

from __future__ import annotations

import math
import os
import re
import time
from collections import Counter
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: System prompt for every entropy measurement and for the agent itself.
#: This is a control variable. Do NOT modify, do NOT append to it, do NOT
#: use it for format guidance. Format instructions live in the
#: ``final_answer`` tool description (see implementation/agent-tools.md).
MINIMAL_INSTRUCTION: str = (
    "You are an AI agent that solves problems using tools."
)

#: The fixed measurement question. Asked at every entropy measurement
#: point (H_raw, H_improved, and H_n during execution). Defines the
#: dimension along which entropy is measured.
MEASUREMENT_QUESTION: str = (
    "What concrete action will the agent take next?"
)

#: Together AI embedding model used by ``semantic_cluster``. The clustering
#: geometry depends on this -- changing it requires a CACHE_VERSION bump.
#: As of v2.8.1 (April 2026) Together AI's serverless catalog has
#: consolidated to a single embedding model: intfloat/multilingual-e5-large-
#: instruct (1024-dim, 514-token context). The "neutral and external"
#: constraint from spec/measurement.md is satisfied -- the embedder is
#: separate from the generation model.
EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large-instruct"

#: Together AI OpenAI-compatible base URL.
TOGETHER_BASE_URL: str = "https://api.together.xyz/v1"

#: Sampling temperature for the entropy-measurement calls. The ONLY
#: stochastic surface of the experiment.
ENTROPY_SAMPLING_TEMPERATURE: float = 0.7

#: AgglomerativeClustering distance threshold (cosine). Determines what
#: counts as "the same meaning." NOT editable without a version bump.
CLUSTERING_DISTANCE_THRESHOLD: float = 0.08

#: Approximate chars-per-token used by the local trim/summarize length
#: estimates. Anthropic's tokenizer would be more accurate but would
#: require an API call; this constant lets the trim and summarize layers
#: enforce a budget without billing the user. ~4 chars/token is the
#: widely cited rough estimate for English.
_CHARS_PER_TOKEN: int = 4


# ---------------------------------------------------------------------------
# Cost monitoring shared state (Phase 5)
# ---------------------------------------------------------------------------
#
# These mutable module-level objects are SHARED with benchmark.py via
# ``from inverse import _llm_token_accumulator, ...``. Importing a name
# binds the local name in the importer to the SAME object; mutations
# from either file affect the same dict.
#
# IMPORTANT: never REBIND these names (e.g. ``_llm_token_accumulator =
# {}``). Doing so creates a new object that benchmark.py's existing
# reference cannot see, breaking cost monitoring silently. To reset,
# ALWAYS use ``.clear()``. log_cost_start in benchmark.py relies on
# this.
#
# Phase 5 wires these as follows:
#   * inverse.py's _llm_call records every Anthropic generation call
#     via _record_llm_tokens("anthropic", in_tok, out_tok).
#   * inverse.py's semantic_cluster records every Together AI
#     embedding call via _record_llm_tokens("together", emb_tokens, 0).
#   * benchmark.py's _call_agent_with_retries._one_call records every
#     agent Thought/Action call via _record_llm_tokens("anthropic", ...).
#   * benchmark.py's cache_hit() increments _cache_hit_counters.
#   * benchmark.py's log_cost_start() / log_cost_end() consume these.

#: Per-provider LLM token accumulator. Reset at log_cost_start; read
#: at log_cost_end. Keys are provider identifiers
#: ({"anthropic", "together"} in v0). Values are dicts with
#: ``input_tokens`` and ``output_tokens`` integers.
_llm_token_accumulator: dict[str, dict[str, int]] = {}

#: Per-cache-subdir hit/miss counters. Reset at log_cost_start; read
#: at log_cost_end. Only cache_hit() in benchmark.py increments these
#: -- cache_get() does NOT (per operations/cost-monitoring.md, "the
#: latter could mask misses as errors").
_cache_hit_counters: dict[str, dict[str, int]] = {}

#: Per-run scratchpad: starting Tavily credits, started_at timestamp,
#: any other run-level state log_cost_start needs to remember for
#: log_cost_end. Reset (.clear()) at log_cost_start.
_run_state: dict = {}


def _record_llm_tokens(
    provider: str, input_tokens: int, output_tokens: int
) -> None:
    """Add tokens to the per-provider accumulator.

    Called from every LLM-touching code path:
      * Generation (Anthropic Messages API): "anthropic"
      * Embedding (Together AI OpenAI-compat API): "together"
    Unknown provider names are accepted (recorded under their name)
    but will produce a warning at log_cost_end if no pricing entry
    exists.
    """
    if provider not in _llm_token_accumulator:
        _llm_token_accumulator[provider] = {
            "input_tokens": 0,
            "output_tokens": 0,
        }
    _llm_token_accumulator[provider]["input_tokens"] += int(input_tokens)
    _llm_token_accumulator[provider]["output_tokens"] += int(output_tokens)


# ---------------------------------------------------------------------------
# Lazy clients
# ---------------------------------------------------------------------------

_anthropic_client = None
_together_client = None


def _get_anthropic_client():
    """Lazily construct the Anthropic client.

    The import is deferred so that ``import inverse`` works without
    ``anthropic`` installed. Reads ``ANTHROPIC_API_KEY`` from the
    environment.
    """
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic  # type: ignore

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Populate .env (see "
                ".env.example) before running anything that calls the LLM."
            )
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


def _get_together_client():
    """Lazily construct the Together AI client (OpenAI-compatible).

    Reads ``TOGETHER_API_KEY`` from the environment.
    """
    global _together_client
    if _together_client is None:
        from openai import OpenAI  # type: ignore

        api_key = os.environ.get("TOGETHER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "TOGETHER_API_KEY is not set. Populate .env (see "
                ".env.example) before running anything that calls the "
                "embedding API."
            )
        _together_client = OpenAI(api_key=api_key, base_url=TOGETHER_BASE_URL)
    return _together_client


# ---------------------------------------------------------------------------
# 1. LLM call helper (single point of entry for generation)
# ---------------------------------------------------------------------------


def _llm_call(
    prompt: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int = 1024,
    system: str | None = None,
) -> tuple[str, int, int]:
    """Call the Anthropic Messages API once.

    Returns ``(text, input_tokens, output_tokens)``. The token counts come
    from the response's ``usage`` field; do not estimate locally.
    """
    client = _get_anthropic_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system is not None:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    # Anthropic returns a list of content blocks; the text blocks have .text
    text_parts = [
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ]
    text = "".join(text_parts)
    in_tok = int(getattr(response.usage, "input_tokens", 0))
    out_tok = int(getattr(response.usage, "output_tokens", 0))
    # Cost monitoring (Phase 5): record into the shared accumulator.
    _record_llm_tokens("anthropic", in_tok, out_tok)
    return text, in_tok, out_tok


# ---------------------------------------------------------------------------
# 2. summarize_to_head
# ---------------------------------------------------------------------------


_SUMMARIZE_TEMPLATE = """\
Compress the following text into a single English sentence of at most {max_tokens} tokens (~{max_chars} characters). Preserve the goal and the concrete deliverable -- what would exist when the task is finished. Drop greetings, hedging, and meta-commentary. Do not add information that is not in the source. Output the compressed sentence only, with no preamble.

Source:
{text}
"""


def summarize_to_head(
    text: str, max_tokens: int = 80, *, model: str
) -> tuple[str, int]:
    """Compress ``text`` to at most ``max_tokens`` tokens.

    Used to produce the 80-token Head for both H_raw and H_improved
    inputs, and (with the same 80-token cap) to produce the locked Head
    for the agent's execution context. The 80 used here is the SAME 80
    that the measurement pipeline uses; see spec/token-budget.md.

    * temperature = 0 (deterministic compression)
    * The summarizer's residual variance is intentional. It cancels in
      delta_H because both H_raw and H_improved share this pipeline.
      See spec/measurement.md "The cancellation argument".

    Returns ``(summary, tokens_used)`` where ``tokens_used`` is the
    sum of input + output tokens from the single LLM call.
    """
    prompt = _SUMMARIZE_TEMPLATE.format(
        max_tokens=max_tokens,
        max_chars=max_tokens * _CHARS_PER_TOKEN,
        text=text,
    )
    summary, in_tok, out_tok = _llm_call(
        prompt,
        model=model,
        temperature=0.0,
        max_tokens=max_tokens + 16,  # small headroom for the LLM's stop
    )
    summary = summary.strip()

    # Hard cap by character budget. Truncating from the end is the
    # right behaviour for a "compressed sentence" output -- if the LLM
    # overshoots, the leading tokens still carry the goal.
    char_budget = max_tokens * _CHARS_PER_TOKEN
    if len(summary) > char_budget:
        summary = summary[:char_budget].rstrip()
    return summary, in_tok + out_tok


# ---------------------------------------------------------------------------
# 2b. summarize_to_body
# ---------------------------------------------------------------------------


_BODY_SUMMARIZE_TEMPLATE = """\
You are maintaining a running 70-token summary of an AI agent's execution history. The agent works on a task by alternating Thought, Action (tool call), and Observation. As steps advance, older steps slide out of the recent-action window and must be folded into this running summary so the agent does not lose track of what has already been established.

You receive two inputs:

PRIOR SUMMARY (the running summary of everything BEFORE the displaced content; may be empty if this is the first time we are summarising):
\"\"\"
{previous_body}
\"\"\"

DISPLACED CONTENT (the chunk that just slid out of the recent-action window — must now be integrated into the running summary):
\"\"\"
{displaced_content}
\"\"\"

Update the running summary by integrating the displaced content into the prior summary. Output the new summary in at most {max_tokens} tokens (~{max_chars} characters).

What to PRESERVE:
- Facts the agent has confirmed (e.g. "established that X = ...", "ruled out Y").
- Open questions still unresolved.
- The agent's current line of inquiry — what it is currently trying to establish.

What to DROP:
- Greetings, hedging, meta-commentary about reasoning ("I should think about...", "Let me consider...").
- Step numbers, exact tool names, exact wording of search queries.
- Anything that does not advance the agent's understanding of the task.

Constraints:
- Output the new summary only. No preamble. No labels. No explanation.
- Older facts compress more aggressively than newer ones; the displaced content (which is the newest material to be summarised) gets relatively more space than older items already compressed in the prior summary.
- If the prior summary is empty or "(none yet)", produce a fresh summary of the displaced content alone.
- Write in the third person, in declarative present tense.
"""


def summarize_to_body(
    previous_body: str,
    displaced_content: str,
    *,
    model: str,
    max_tokens: int = 70,
) -> tuple[str, int]:
    """Recursively summarise the agent's execution history into the Body slot.

    Called by ``run_react_loop`` at each step from step 3 onward, when
    a previous step's content has slid past the n-2 boundary and must
    be integrated into the running 70-token Body summary.

    * ``previous_body``: the Body summary as of the previous step.
      Empty string for the first call (step 3, when nothing has been
      summarised yet).
    * ``displaced_content``: the raw thought+action+observation text
      from the step that just slid out of the recent-action window.
    * temperature = 0 (deterministic recursive compression).
    * 70-token cap is load-bearing per spec/token-budget.md.

    Returns ``(new_body, tokens_used)``.
    """
    prompt = _BODY_SUMMARIZE_TEMPLATE.format(
        max_tokens=max_tokens,
        max_chars=max_tokens * _CHARS_PER_TOKEN,
        previous_body=previous_body if previous_body else "(none yet)",
        displaced_content=displaced_content if displaced_content else "(none)",
    )
    summary, in_tok, out_tok = _llm_call(
        prompt,
        model=model,
        temperature=0.0,
        max_tokens=max_tokens + 16,
    )
    summary = summary.strip()

    # Hard cap by character budget (same safety net as summarize_to_head).
    char_budget = max_tokens * _CHARS_PER_TOKEN
    if len(summary) > char_budget:
        summary = summary[:char_budget].rstrip()
    return summary, in_tok + out_tok


# ---------------------------------------------------------------------------
# 3. trim_to_tail
# ---------------------------------------------------------------------------

# Filler patterns removed by trim_to_tail. These are *meaning-preserving*
# normalisations only -- they collapse whitespace and strip wrappers, they
# do NOT paraphrase. Adding a pattern that rewrites meaning would break
# the entropy resolution argument in spec/token-budget.md.
_FILLER_PATTERNS: list[tuple[str, str]] = [
    # Collapse runs of internal whitespace (but keep single newlines).
    (r"[ \t]+", " "),
    # Collapse 3+ blank lines into one blank line.
    (r"\n{3,}", "\n\n"),
    # Strip trailing whitespace per line.
    (r"[ \t]+\n", "\n"),
]


def trim_to_tail(text: str, max_tokens: int = 150) -> str:
    """Meaning-preserving trim. NEVER summarises or rewrites.

    Removes runs of whitespace and excessive blank lines. Key error
    logs and technical keywords are preserved verbatim. Short inputs
    pass through unchanged.

    If the result still exceeds ``max_tokens``, truncate from the END
    (not from the middle) and mark the truncation point. Truncating
    from the middle would lose the most recent state, which is what
    the Tail is for.
    """
    if not text:
        return ""

    out = text
    for pattern, replacement in _FILLER_PATTERNS:
        out = re.sub(pattern, replacement, out)
    out = out.strip()

    char_budget = max_tokens * _CHARS_PER_TOKEN
    if len(out) > char_budget:
        marker = " ...[trimmed]"
        out = out[: char_budget - len(marker)].rstrip() + marker
    return out


# ---------------------------------------------------------------------------
# 4. semantic_cluster
# ---------------------------------------------------------------------------


def semantic_cluster(responses: list[str]) -> list[int]:
    """Embed N responses and cluster on cosine similarity.

    Embeddings come from Together AI's serverless embedder via the
    OpenAI-compatible interface (currently intfloat/multilingual-e5-
    large-instruct -- see EMBEDDING_MODEL). Clustering uses scikit-
    learn's AgglomerativeClustering with average linkage and a fixed
    cosine distance threshold of 0.15. Both the embedder identity and
    the threshold are NOT editable without a version bump (see
    spec/measurement.md).

    Returns a list of cluster labels in the same order as ``responses``.
    Deterministic given fixed embeddings.
    """
    if not responses:
        return []
    if len(responses) == 1:
        return [0]

    client = _get_together_client()
    embed_response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=responses,
    )
    embeddings = [item.embedding for item in embed_response.data]

    # Cost monitoring (Phase 5): record Together AI embedding tokens
    # into the shared accumulator. Field name varies by SDK version,
    # so try total_tokens first, then prompt_tokens, then 0 if neither
    # is present. Output tokens are 0 for embeddings -- the output is
    # the vectors, which are not billed by token.
    embedding_tokens = 0
    if hasattr(embed_response, "usage") and embed_response.usage is not None:
        usage = embed_response.usage
        embedding_tokens = (
            getattr(usage, "total_tokens", None)
            or getattr(usage, "prompt_tokens", None)
            or 0
        )
    _record_llm_tokens("together", int(embedding_tokens), 0)

    import numpy as np  # type: ignore
    from sklearn.cluster import AgglomerativeClustering  # type: ignore

    matrix = np.asarray(embeddings, dtype=float)
    clusterer = AgglomerativeClustering(
        metric="cosine",
        linkage="average",
        distance_threshold=CLUSTERING_DISTANCE_THRESHOLD,
        n_clusters=None,
    )
    labels = clusterer.fit_predict(matrix)
    return [int(label) for label in labels]


# ---------------------------------------------------------------------------
# 5. measure_semantic_entropy
# ---------------------------------------------------------------------------


def measure_semantic_entropy(
    input_context: str,
    model: str,
    n_samples: int = 10,
) -> tuple[float, int]:
    """Sample, cluster, and return Shannon entropy of the cluster distribution.

    * ``input_context`` is used as the system prompt -- typically
      ``f"{MINIMAL_INSTRUCTION}\\n\\n{summary}"`` for entrance
      measurements, or the full 300-token Head+Body+Tail for during-
      execution measurements.
    * The user message is always ``MEASUREMENT_QUESTION`` -- fixed,
      never edited (see spec/measurement.md).
    * Sampling temperature is fixed at 0.7. Anything else changes what
      H means.

    Returns ``(entropy, tokens_used)`` where ``tokens_used`` is the
    sum of input + output tokens across all ``n_samples`` LLM calls.
    """
    samples: list[str] = []
    total_tokens = 0
    for _ in range(n_samples):
        text, in_tok, out_tok = _llm_call(
            MEASUREMENT_QUESTION,
            model=model,
            temperature=ENTROPY_SAMPLING_TEMPERATURE,
            max_tokens=256,
            system=input_context,
        )
        total_tokens += in_tok + out_tok
        samples.append(text.strip())

    labels = semantic_cluster(samples)
    if not labels:
        return 0.0, total_tokens

    counts = Counter(labels)
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy, total_tokens


# ---------------------------------------------------------------------------
# 6. inverse() and the three prompt templates
# ---------------------------------------------------------------------------

# First-draft prompt templates for the three inverse-model steps. These
# are the *experimental subject* -- improvements are expected. The
# structural commitments (3 steps, no shared history, explicit injection,
# k=4 backward chaining) are load-bearing; the wording inside each
# template is editable.


def prompt_target(raw_prompt: str) -> str:
    """Step 1 (Target): define the done state. Maps to x*_{t+1}."""
    return f"""\
Your task is to define the SUCCESS CONDITION for the request below.

Request:
\"\"\"
{raw_prompt}
\"\"\"

When this task is finished and successful, what concrete artifact, state, or answer will exist?

Describe the "done" state precisely:
- What deliverable will the user have in hand?
- What properties must that deliverable satisfy?
- What would let any reviewer agree, on inspection, that the task is finished?

Constraints:
- Write the done state as a single short paragraph.
- Do NOT list steps. Do NOT describe how to get there.
- Do NOT add requirements that are not implied by the request.

Output the paragraph only, with no preamble or commentary."""


# k=4 enforcement is instruction-only in v0: the template tells the LLM
# "stop at 5 steps total" but inverse() does not parse the LLM's output
# to verify the chain length. A stricter parsing-based enforcement is a
# post-Phase-6 decision — adding it now would introduce a confounding
# variable (effect of inverse model vs effect of stricter enforcement).
def prompt_invert(target: str, raw_prompt: str) -> str:
    """Step 2 (Invert): macro-level backward chaining. The work of g."""
    return f"""\
Your task is to derive the work needed to reach a target state, working strictly BACKWARD.

Target state (the "done" state from the previous step):
\"\"\"
{target}
\"\"\"

Original request (for context only -- do not re-derive the target):
\"\"\"
{raw_prompt}
\"\"\"

Apply MACRO-LEVEL BACKWARD CHAINING. At each step, ask: "what must be true immediately before this state, for this state to be reachable?"

Rules:
- Ignore micro-steps. Record only DECISIVE LOGICAL JUMPS -- the few preconditions without which the next state cannot exist.
- Stop AS SOON AS either of the following is true:
    (a) the most recent precondition can be satisfied with information already present in the original request, OR
    (b) the chain has reached 5 steps total (k = 4).
- Whichever stop condition fires first wins. Do not extend the chain past either.

Output format:
- A numbered list, from the LATEST precondition (closest to the target) DOWN TO the earliest.
- Each item is one short sentence.
- No preamble, no explanation, no headings -- just the numbered list."""


def prompt_compose(raw_prompt: str, target: str, inversion: str) -> str:
    """Step 3 (Compose): combine into one self-contained instruction. Maps to u_t."""
    return f"""\
Your task is to compose a SINGLE, CLEAR INSTRUCTION that an AI agent can follow.

You have three inputs:

Original request:
\"\"\"
{raw_prompt}
\"\"\"

Done state (Target, from Step 1):
\"\"\"
{target}
\"\"\"

Backward chain of preconditions (Invert, from Step 2):
\"\"\"
{inversion}
\"\"\"

Combine the above into ONE instruction for the agent. The instruction must:
- State the goal in concrete terms drawn from the done state.
- List the required information and actions in FORWARD order (i.e. the reverse of the backward chain from Step 2).
- Be SELF-CONTAINED: an agent reading only this instruction, without ever seeing the original request, must understand exactly what to do and what success looks like.

Constraints:
- Write the instruction as a single block of text.
- No headings. No numbered lists unless the list is part of the instruction itself.
- No commentary about the process. No "Here is the instruction:" preamble.
- Do not invent constraints that are not implied by the inputs above."""


def inverse(
    raw_prompt: str,
    model: str,
    n_samples: int = 10,
) -> dict:
    """Run the 3-step inverse model and return everything measured along the way.

    Three independent LLM calls (no shared conversation history). Each
    step's output is explicitly injected into the next step's prompt
    template. ``temperature = 0`` for all three. Entropy is measured
    only at the entrance (raw_prompt) and the exit (improved_prompt).
    """
    started_at = time.monotonic()
    total_tokens = 0

    # 1. Original query -> 80-token summary -> measure H_raw
    raw_summary, raw_summary_tokens = summarize_to_head(
        raw_prompt, max_tokens=80, model=model
    )
    total_tokens += raw_summary_tokens
    H_raw, H_raw_tokens = measure_semantic_entropy(
        f"{MINIMAL_INSTRUCTION}\n\n{raw_summary}",
        model=model,
        n_samples=n_samples,
    )
    total_tokens += H_raw_tokens

    # 2. Run the 3 inverse-model steps (independent prompt chaining)
    target_text, in1, out1 = _llm_call(
        prompt_target(raw_prompt),
        model=model,
        temperature=0.0,
        max_tokens=512,
    )
    total_tokens += in1 + out1

    inversion_text, in2, out2 = _llm_call(
        prompt_invert(target_text.strip(), raw_prompt),
        model=model,
        temperature=0.0,
        max_tokens=512,
    )
    total_tokens += in2 + out2

    improved_prompt, in3, out3 = _llm_call(
        prompt_compose(raw_prompt, target_text.strip(), inversion_text.strip()),
        model=model,
        temperature=0.0,
        max_tokens=1024,
    )
    total_tokens += in3 + out3

    improved_prompt = improved_prompt.strip()

    # 3. Refined query -> 80-token summary -> measure H_improved
    improved_summary, improved_summary_tokens = summarize_to_head(
        improved_prompt, max_tokens=80, model=model
    )
    total_tokens += improved_summary_tokens
    H_improved, H_improved_tokens = measure_semantic_entropy(
        f"{MINIMAL_INSTRUCTION}\n\n{improved_summary}",
        model=model,
        n_samples=n_samples,
    )
    total_tokens += H_improved_tokens

    return {
        "raw_prompt": raw_prompt,
        "improved_prompt": improved_prompt,
        "raw_summary": raw_summary,
        "improved_summary": improved_summary,
        "target": target_text.strip(),
        "inversion": inversion_text.strip(),
        "H_raw": H_raw,
        "H_improved": H_improved,
        "delta_H": H_raw - H_improved,
        "total_tokens_used": total_tokens,
        "pre_processing_time": time.monotonic() - started_at,
    }


# ---------------------------------------------------------------------------
# 7. detect_loop
# ---------------------------------------------------------------------------


def detect_loop(
    entropy_history: list[float],
    H_raw: float,
    alpha: float = 0.3,
    window: int = 3,
) -> dict:
    """Detect a loop on the entropy curve.

    Condition: ``d^2H/dt^2 ~= 0`` (within ``window``) AND ``H > alpha * H_raw``.

    Both halves are required:
      * The second-derivative half distinguishes plateau from convergence.
        See spec/loop-detection.md (a) for why the SECOND derivative
        rather than the first.
      * The threshold half disambiguates "flattened high (loop)" from
        "flattened low (converged)". See spec/loop-detection.md (b).

    ``H_raw`` is the per-task baseline. **The same H_raw is used in both
    conditions A and B** -- never H_improved in B. See
    spec/loop-detection.md (c) for the reason: the loop threshold is part
    of the measurement apparatus, not part of the treatment, and it must
    not bend with what it is measuring.
    """
    n = len(entropy_history)
    threshold = alpha * H_raw

    # Need at least ``window`` points to estimate a second difference.
    if n < window:
        return {"is_loop": False, "loop_start_step": None}

    # Use the most recent ``window`` H values as the smoothing window.
    recent = entropy_history[-window:]

    # Estimate the second derivative as a discrete second difference of
    # the window. For window=3 this collapses to:
    #     d2 = H[n-1] - 2*H[n-2] + H[n-3]
    # For larger windows take the mean of overlapping second differences.
    second_diffs = []
    for i in range(len(recent) - 2):
        d2 = recent[i + 2] - 2 * recent[i + 1] + recent[i]
        second_diffs.append(d2)
    if not second_diffs:
        return {"is_loop": False, "loop_start_step": None}

    # "approximately zero" tolerance band: small fraction of H_raw.
    # Anything inside +/- TOL is treated as flat.
    # Tolerance band: 5% of H_raw. spec/loop-detection.md leaves "≈ 0" as an
    # implementation detail. This value is a tuning candidate — revisit after
    # Phase 6 smoke tests based on actual entropy curve shapes. Per the
    # spec's editability table, the exact tolerance is editable; only the
    # `d²H/dt² ≈ 0 AND H > α·H_raw` shape and `α = 0.3` are version-locked.
    tol = 0.05 * max(H_raw, 1e-9)
    flattened = all(abs(d2) <= tol for d2 in second_diffs)

    # H must currently be ABOVE the alpha*H_raw threshold for the loop
    # detector to fire. Otherwise we are in the convergence region.
    H_now = recent[-1]
    high = H_now > threshold

    if flattened and high:
        loop_start_step = n - window  # earliest index in the window
        return {"is_loop": True, "loop_start_step": loop_start_step}
    return {"is_loop": False, "loop_start_step": None}
