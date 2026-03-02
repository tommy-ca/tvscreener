---
date: 2026-03-02
topic: duckdb-edge-architecture
---

# DuckDB Edge Architecture & Narwhals Medallion Pipeline

## What We're Building
A modernization of the `tvscreener` data pipeline. The current pipeline tightly couples data fetching, pandas transformation, DuckDB SQL execution (`DuckDBFilter`), and rendering into a single synchronous flow. 

We are shifting to a **Medallion Architecture (Bronze/Silver/Gold)** that relies entirely on **Narwhals** (`narwhals`) for all intermediate compute, filtering, and scoring. **DuckDB** will be completely removed from the intermediate pipeline and repositioned exclusively at the edge as an OLAP client (`EdgeQueryClient`) to query the final exported Parquet files.

## Why This Approach
1. **Performance & Ecosystem via Narwhals:** The compute pipeline will be completely refactored to use Narwhals. This allows us to write the scoring/filtering logic using Polars-style expressions but execute it natively and losslessly on *either* Polars (for GPU acceleration / multithreading) or PyArrow-backed Pandas (for compatibility with existing TA libraries). 
2. **Rejecting Ibis:** We are explicitly rejecting Ibis because it is a heavy query compiler meant for external databases. Narwhals, on the other hand, is a zero-dependency local dataframe abstraction layer that perfectly fits our need for a lightweight, flexible compute engine.
3. **Resilience & Idempotency:** The pipeline currently drops all state if a user's `--sql` query is malformed. By moving DuckDB exclusively to the Edge/Serving layer, the pipeline deterministically computes the Gold Parquet dataset 100% of the time. The user's SQL query only filters the *terminal output* of that finalized file.
4. **Agentic Workflows:** MCP Agents can currently only query data by triggering a full TradingView API fetch. By exporting Gold Parquet files and providing an `EdgeQueryClient`, agents and users can run dozens of `--sql` queries against historical scans instantly over the cached `.parquet` outputs.

## Key Decisions
- **Adopt Narwhals for Compute:** Rewrite all intermediate pipeline logic (scoring/filtering) using Narwhals' Polars-style expressions to support both Polars and PyArrow-backed Pandas.
- **Reject Ibis:** Avoid Ibis in favor of Narwhals to maintain a lightweight, zero-dependency local dataframe abstraction.
- **Remove `DuckDBFilter` from Pipeline:** The `post_filters` pipeline step will no longer execute user SQL during the scan. 
- **Enforce Parquet Checkpoints:** The pipeline will keep `bronze` and `silver` stages in-memory for performance, and only write the final `gold_scored.parquet` to disk.
- **Data Validation:** We will enforce strict dtypes at the Silver layer boundary to prevent silent downstream scoring failures (avoiding heavy external dependencies like `pandera`).
- **Keep DuckDB at the Edge (`EdgeQueryClient`):** A new module that spins up an in-memory DuckDB instance to allow users/MCP agents to run `--sql` queries strictly against the cached `gold_scored.parquet` outputs *after* the pipeline finishes.
- **Universal Output Stage (Feature Parity):** Restore specialized Matrix/Detailed views for SQL results by refactoring the renderer to accept external data and using Narwhals to re-standardize schemas across backends.

## Open Questions
- Should the `EdgeQueryClient` replace the native Rich console rendering entirely, or just act as a pre-filter before handing the DataFrame back to the Rich renderer?
- Do we need to migrate the existing `tvscreener-scan` CLI into two separate subcommands (`run` vs `query`), or keep the current UX where passing `--sql` just means "run the pipeline, save the parquet, and then query the parquet before printing"?

## Next Steps
Create actionable implementation tasks in the `todos/` directory using the `file-todos` skill.
