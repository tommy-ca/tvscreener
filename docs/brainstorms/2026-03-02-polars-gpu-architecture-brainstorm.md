---
date: 2026-03-02
topic: polars-gpu-architecture
---

# Polars GPU Engine & Pandas Interop Architecture

## What We're Building
A modernized compute engine for the `tvscreener` pipeline that leverages **Polars (with its new GPU Engine support via NVIDIA RAPIDS)** for heavy vectorization, grouping, and filtering, while maintaining **Pandas (PyArrow backend)** compatibility for Technical Analysis (TA) libraries.

The tool must remain highly portable (a lightweight CLI), degrading gracefully to CPU-bound Polars if a GPU is unavailable, avoiding the massive deployment footprint of strict enterprise GPU frameworks.

## Why This Approach
1. **Portability (The Primary Constraint):** The user requires a `pip install`-able CLI tool. Polars is lightweight. Its new GPU engine allows opt-in GPU acceleration without forcing a 2GB dependency on every user.
2. **Zero-Copy Interop:** Both Pandas 2.0 (`dtype_backend="pyarrow"`) and Polars natively use the Apache Arrow memory format. We can transition between `pd.DataFrame` and `pl.DataFrame` instantly with zero memory serialization overhead.
3. **Best of Both Worlds:** We get the blazing fast, multi-threaded (and now GPU-accelerated) relational algebra of Polars for pipeline logic (filtering, sorting, aggregations), and the rich ecosystem of Pandas for specific TA indicators (`pandas-ta`).

## Key Decisions
- **Compute Engine:** Polars LazyFrames (`pl.LazyFrame`) will become the primary data structure for the core pipeline to optimize query plans before execution.
- **GPU Opt-In:** We will utilize the Polars GPU engine (`engine="gpu"`) when executing the lazy plan, falling back to CPU if no compatible hardware is detected.
- **Pandas/TA Boundary:** For TA indicators that Polars cannot natively compute, we will explicitly cast to Pandas (`df.to_pandas()`), run the indicator, and cast back (`pl.from_pandas(df)`). Because both are Arrow-backed, this is an $O(1)$ pointer swap.

## Open Questions
- **DuckDB Edge Client:** Does Polars entirely replace the need for the previously discussed DuckDB Edge Client, or do we still want DuckDB providing SQL semantics for the user at the edge?
- **Granularity of Interop:** Do we convert to Pandas once, run all TA, and convert back? Or do we bounce back and forth on a per-indicator basis?

## Next Steps
→ `/workflows:plan` for implementation details
