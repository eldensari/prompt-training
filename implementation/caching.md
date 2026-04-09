# Caching policy

> Sourced from: v2.7.9 §Caching policy
> Related: [benchmark.md](./benchmark.md), [inverse.md](./inverse.md), [../spec/measurement.md](../spec/measurement.md)

---

## Default

Caching is **default-on**. The `--no-cache` CLI flag disables it. Smoke tests typically run with `--no-cache` to make sure cold paths work; result-producing runs use the default-on behavior to keep cost manageable across reruns.

There are exactly **three** caches. Each one corresponds to a different kind of expensive computation, and each one has its own subdirectory.

| Cache | Key | Stored value | Reason |
|---|---|---|---|
| `cache/inverse/{key}.json` | `sha256(task_id + model + n_samples + cache_version)` | full `inverse()` return dict | `inverse()` is expensive (3 LLM calls + 2 entropy measurements); deterministic given the same task |
| `cache/h_raw/{key}.json` | `sha256(task_id + model + n_samples + cache_version)` | `{"H_raw": float, "raw_summary": str}` | Shared between conditions A and B; measured once per task |
| `cache/tavily/{key}.json` | `sha256(tool_name + query_or_url + cache_version)` | raw Tavily response JSON | Dominant cost saver across reruns |

---

## H_improved is deliberately NOT cached

This is the load-bearing oddity. Of the four expensive things in the pipeline — `inverse()`, `H_raw`, the agent's Tavily calls, and `H_improved` — three are cached and one is not. The exclusion is deliberate.

`H_improved` exists as a sanity check on the `inverse` cache. Here is the failure mode it is designed to catch:

Suppose the `inverse` cache for some task contains a stale or corrupted entry — maybe the cache key collided, maybe a half-written file was committed during a crash, maybe a model upgrade silently changed how the same prompt gets interpreted. The cached `inverse_result` returns a stale `improved_prompt`. If we *also* cached `H_improved`, that stale `improved_prompt` would have a stale `H_improved` next to it, and the row in the result table would look perfectly internally consistent. The corruption would be invisible.

By recomputing `H_improved` fresh on every run, we force a comparison: the `H_improved` written into the row was just measured, against the `improved_prompt` that the (possibly cached) `inverse_result` returned. If the cache is healthy, the freshly measured `H_improved` matches what `inverse_result["H_improved"]` would have been; if the cache is corrupted, the two numbers diverge and the disagreement is visible. The cost of an extra entropy measurement per task is the price of detecting cache corruption immediately rather than after a paper has been written.

The same principle is the reason the agent itself runs against a freshly-summarized 80-token Head rather than a cached one — see [../spec/measurement.md §Why we don't try to remove the noise](../spec/measurement.md#why-we-dont-try-to-remove-the-noise). Both choices serve the same goal: keep the production-time pipeline identical to the measurement-time pipeline, so any divergence surfaces immediately.

---

## Cache invalidation

Bump `CACHE_VERSION` (top of `benchmark.py`) to invalidate everything. Changing the model, `N_SAMPLES`, or the clustering distance threshold should also bump the version, because all three change what every cached value *means* — the same `task_id` under a different model or N produces a different distribution and therefore a different valid `H` value.

The `CACHE_VERSION` string is editable; the practice of bumping it on any of the above changes is not. See [../operations/experiment-rules.md](../operations/experiment-rules.md).

---

## Cache helper functions

```python
import hashlib, json
from pathlib import Path

CACHE_VERSION = "v2.7.9-001"
CACHE_ROOT = Path("cache")

def _cache_key(*parts) -> str:
    """Build a deterministic cache key from arbitrary parts."""
    payload = "||".join(str(p) for p in parts) + f"||v={CACHE_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]

def cache_get(subdir: str, key: str):
    """Return cached value or None if miss. subdir ∈ {'inverse', 'h_raw', 'tavily'}."""
    path = CACHE_ROOT / subdir / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())

def cache_set(subdir: str, key: str, value) -> None:
    """Store value. Caller decides contents (must be JSON-serializable)."""
    path = CACHE_ROOT / subdir / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))

def cache_hit(subdir: str, key: str) -> bool:
    return (CACHE_ROOT / subdir / f"{key}.json").exists()
```

The `cache_hit` function exists separately from `cache_get` so that cost monitoring (see [../operations/cost-monitoring.md](../operations/cost-monitoring.md)) can count hits and misses without paying the JSON-decode cost of a full read.

---

## Cross-references

- [benchmark.md](./benchmark.md#run_task_both_conditionstask) — where the three caches are consulted
- [../operations/cost-monitoring.md](../operations/cost-monitoring.md) — per-cache hit rate logging
- [../spec/measurement.md](../spec/measurement.md) — why H_improved being uncached is the same principle as the freshly-summarized Head
