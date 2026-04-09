# File layout

> Sourced from: v2.7.9 §File layout, §Environment, §pyproject.toml
> Related: [benchmark.md](./benchmark.md), [inverse.md](./inverse.md), [gaia-integration.md](./gaia-integration.md)

---

## Directory structure

```
prompt-training/
├── README.md             ← project overview (multi-file shell)
├── inverse.py            ← inverse model engine + entropy measurement
├── benchmark.py          ← GAIA loader, A/B runner, verifier, caching, cost monitoring
├── gaia_scorer.py        ← vendored GAIA official scorer (bit-exact)
├── cache/                ← gitignored
│   ├── inverse/
│   ├── h_raw/
│   └── tavily/
├── results/
│   ├── results.tsv
│   ├── entropy_curves/
│   └── run_<timestamp>.log
├── pyproject.toml
└── .env.example
```

The three Python files are described in [inverse.md](./inverse.md), [benchmark.md](./benchmark.md), and [gaia-integration.md §Verifier](./gaia-integration.md#verifier). The three cache subdirectories correspond to the three caches in [caching.md](./caching.md).

`results/entropy_curves/` holds per-task entropy traces — one file per `(task_id, condition)` pair, useful for plotting and for the temporal-drift review described in [../analysis/temporal-drift.md](../analysis/temporal-drift.md). The exact file format is left to the implementation; the only constraint is that the curves are reproducible from the cache + TSV combination.

`results/run_<timestamp>.log` is the cost-monitoring log — see [../operations/cost-monitoring.md](../operations/cost-monitoring.md). One file per run.

---

## `.env.example`

```
# LLM API key (Anthropic only — v0 single-model policy)
ANTHROPIC_API_KEY=

# Embedding model (required for semantic clustering)
TOGETHER_API_KEY=

# GAIA dataset access (HuggingFace gated — requires form submission and approval)
HF_TOKEN=

# Web search for ReAct agent
TAVILY_API_KEY=
```

`HF_TOKEN` requires GAIA's HuggingFace gated-dataset form submission and approval. This is a one-time per-developer step and must be done before the first run. See the implementation checklist in [checklist.md](./checklist.md).

`TOGETHER_API_KEY` is required for the embedding-based clustering — see [../spec/measurement.md §Clustering](../spec/measurement.md#clustering-what-we-ask-of-it). It is independent of which generation provider is used.

Only `ANTHROPIC_API_KEY` is required for generation. The single-model policy ([agent-tools.md §LLM model](./agent-tools.md#llm-model-single-model-policy)) fixes `MODEL` to a Claude variant in v0; other generation providers are intentionally not configured.

---

## `pyproject.toml`

```toml
[project]
name = "prompt-training"
version = "2.8.1"
description = "Inverse model pre-processing reduces agent loops: a semantic entropy measurement framework on GAIA"
requires-python = ">=3.10"
dependencies = [
    "anthropic>=0.40.0",
    "openai>=1.50.0",  # client lib for Together AI's OpenAI-compatible embeddings endpoint
    "numpy>=1.24.0",
    "matplotlib>=3.7.0",
    "python-dotenv>=1.0.0",
    "scikit-learn>=1.3.0",
    "datasets>=2.14.0",
    "tavily-python>=0.3.0",
    "huggingface_hub>=0.20.0",
]

[project.scripts]
prompt-training = "benchmark:main"
```

The `version` field tracks the spec version and should be bumped together with `CHANGELOG.md` whenever a load-bearing element changes — see [../operations/experiment-rules.md](../operations/experiment-rules.md).
