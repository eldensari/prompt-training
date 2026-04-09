"""
prompt-training/agent_tools.py

The three tools the ReAct agent has access to in v0:

    tavily_search(query)   -> dict   # Tavily basic mode, max_results=5
    tavily_extract(url)    -> dict   # Tavily extract on a single URL
    final_answer(answer)   -> dict   # passthrough; the run_react_loop
                                     # intercepts the agent's final_answer
                                     # tool call to terminate the loop.

Plus the Anthropic tool-use schema for those three tools:

    TOOL_SCHEMA : list[dict]

Design notes:
  * The Tavily client is lazy-imported and lazy-constructed inside
    ``_get_tavily_client``, so importing this module does NOT require
    ``tavily-python`` to be installed or ``TAVILY_API_KEY`` to be set.
    First call constructs the client.
  * ``tavily_search`` and ``tavily_extract`` return the RAW Tavily
    response dict. No post-processing here -- Phase 4b's ReAct loop
    formats the response into an Observation.
  * ``final_answer`` is the only tool whose Python implementation is
    a no-op-ish passthrough. The agent invokes ``final_answer`` by
    emitting a structured tool-use block; the ReAct loop intercepts
    that block (BEFORE the function would normally be dispatched) to
    set ``terminated_by = "completed"`` and capture the answer string.
    The Python function exists for symmetry and as a safety net if
    something ever calls it directly.
  * The GAIA answer-format guidance lives EXCLUSIVELY in the
    ``final_answer`` tool description below. It must NOT leak into
    the system prompt -- ``MINIMAL_INSTRUCTION`` in inverse.py is a
    control variable for the entropy measurement and adding format
    rules to it would change every H value. See
    implementation/agent-tools.md "Final answer format" for the
    rationale.

Phase 4a status: this file is standalone. benchmark.py does NOT
import from it yet -- that wiring belongs to Phase 4b together with
the real run_react_loop body.
"""

from __future__ import annotations

import json
import os
from typing import Any


# ---------------------------------------------------------------------------
# Lazy Tavily client
# ---------------------------------------------------------------------------

_tavily_client = None


def _get_tavily_client():
    """Lazily construct the Tavily client.

    The import is deferred so that ``import agent_tools`` works without
    ``tavily-python`` installed. Reads ``TAVILY_API_KEY`` from the
    environment.
    """
    global _tavily_client
    if _tavily_client is None:
        from tavily import TavilyClient  # type: ignore

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY is not set. Populate .env (see "
                ".env.example) before running anything that calls "
                "Tavily."
            )
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def tavily_search(query: str) -> dict:
    """Web search via Tavily basic mode, ``max_results=5``.

    The mode and max_results are FIXED for v0 -- see
    implementation/agent-tools.md. Basic mode is 1 credit per call;
    raising max_results would push relevant content past the 150-token
    Tail boundary in the next step's context construction.

    Returns the raw Tavily response dict (typically contains a
    ``results`` list with ``title``, ``url``, ``content``, ``score``
    per result, and possibly an ``answer`` summary). Phase 4b's
    ReAct loop is responsible for formatting it into an Observation.
    """
    client = _get_tavily_client()
    return client.search(
        query=query,
        search_depth="basic",
        max_results=5,
    )


def tavily_extract(url: str) -> dict:
    """Fetch and extract page text from a single ``url`` via Tavily.

    The Tavily SDK accepts a list of URLs; we wrap the single ``url``
    argument in a one-element list to match the agent's tool-call
    contract (``url: str``). The raw Tavily response dict is returned;
    Phase 4b's ReAct loop trims it for the Tail (see
    spec/token-budget.md "Why the Tail can see Tavily responses much
    larger than 150 tokens").
    """
    client = _get_tavily_client()
    return client.extract(urls=[url])


def final_answer(answer: str) -> dict:
    """Passthrough. See module docstring.

    The agent invokes this by emitting a tool-use block named
    ``final_answer``; the ReAct loop intercepts that block before it
    would be dispatched as a Python call, sets
    ``terminated_by = "completed"``, and captures the ``answer``
    string for the verifier. This Python function exists as a safety
    net and for symmetry with the other two tools -- if something
    ever does dispatch it, the return value is shaped like the other
    tool returns so the loop does not crash.
    """
    return {"final_answer": answer}


# ---------------------------------------------------------------------------
# Anthropic tool-use schema
# ---------------------------------------------------------------------------

#: Anthropic Messages API tool definitions for the three v0 tools.
#:
#: Format reference:
#:   https://docs.claude.com/en/docs/build-with-claude/tool-use
#:
#: Each tool has ``name``, ``description``, and ``input_schema`` (a
#: JSON Schema fragment with ``type: "object"``).
#:
#: NOTE: the GAIA answer-format guidance below appears in the
#: ``final_answer`` tool DESCRIPTION ONLY. It must not be moved to the
#: system prompt -- ``MINIMAL_INSTRUCTION`` is a control variable for
#: the entropy measurement (see spec/measurement.md). The tool
#: description is the only legitimate location for format rules.
TOOL_SCHEMA: list[dict] = [
    {
        "name": "tavily_search",
        "description": (
            "Search the web for information relevant to the user's "
            "task. Returns the top 5 results in Tavily basic mode "
            "(title, URL, snippet, relevance score per result, and "
            "sometimes a brief synthesised answer). Use this when you "
            "need to find facts, sources, or starting points; the "
            "results will become the Observation for your next "
            "reasoning step."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The search query. Phrase it as you would a "
                        "web search -- short, specific, and including "
                        "the most distinctive keywords from the task."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "tavily_extract",
        "description": (
            "Fetch and extract the readable text content of a single "
            "web page by URL. Use this when a search result looks "
            "promising and you need the full page body rather than "
            "just the snippet. The extracted text will become the "
            "Observation for your next reasoning step."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "The exact URL to fetch. Must be a single "
                        "fully-qualified URL, typically copied from a "
                        "previous tavily_search result."
                    ),
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "final_answer",
        "description": (
            "Call this tool when you are ready to give the final "
            "answer to the user's question. Calling this tool ENDS "
            "the task -- you will not get another reasoning step. "
            "Be sure your answer is correct and complete before "
            "calling.\n"
            "\n"
            "Your answer must be one of:\n"
            "  - A NUMBER, OR\n"
            "  - A STRING containing as few words as possible, OR\n"
            "  - A COMMA-SEPARATED LIST of numbers and/or strings.\n"
            "\n"
            "Formatting rules:\n"
            "  - If the answer is a number, do NOT use commas (write "
            "1000, not 1,000) and do NOT include units such as $, %, "
            "kg, etc. unless the question explicitly asks for them. "
            "Write the digits, not the word (write '5', not 'five').\n"
            "  - If the answer is a string, do NOT use articles "
            "('a', 'an', 'the') and do NOT use abbreviations. Write "
            "digits in plain text using digit characters unless the "
            "question explicitly asks for spelled-out numbers.\n"
            "  - If the answer is a comma-separated list, apply the "
            "rules above to EACH element of the list independently. "
            "Separate elements with a single comma followed by a "
            "space."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": (
                        "The final answer, formatted exactly per the "
                        "rules in this tool's description."
                    ),
                },
            },
            "required": ["answer"],
        },
    },
]


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _self_test() -> None:
    """Inspect TOOL_SCHEMA without calling any live API.

    Prints the schema as formatted JSON for eyeball review, then
    asserts that the three expected tools are present by name and
    that each has an object-typed input_schema.
    """
    print("--- TOOL_SCHEMA ---")
    print(json.dumps(TOOL_SCHEMA, indent=2))
    print()

    expected_names = {"tavily_search", "tavily_extract", "final_answer"}
    actual_names = {tool["name"] for tool in TOOL_SCHEMA}
    assert actual_names == expected_names, (
        f"Expected tools {expected_names}, got {actual_names}"
    )
    print(f"[ok] All three tools present: {sorted(actual_names)}")

    for tool in TOOL_SCHEMA:
        schema_type = tool["input_schema"]["type"]
        assert schema_type == "object", (
            f"Tool {tool['name']!r} has input_schema.type = "
            f"{schema_type!r}, expected 'object'"
        )
    print("[ok] All three input_schema.type == 'object'")

    print()
    print("agent_tools self-test passed.")


if __name__ == "__main__":
    _self_test()
