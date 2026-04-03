# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
date: 2026-03-02
topic: duckdb-edge-architecture
---

# DuckDB Edge Architecture & Narwhals Medallion Pipeline

## What We're Building
A modernization of the `tvscreener` data pipeline. The current pipeline tightly couples data fetching, pandas transformation, DuckDB SQL execution (`DuckDBFilter`), and rendering into a single synchronous flow. 

We are shifting to a **Medallion Architecture (Bronze/Silver/Gold)** persisted to an **Iceberg lakehouse** and repositioning **DuckDB** exclusively at the edge as an OLAP client (`EdgeQueryClient`) to query Iceberg identifiers (materialized to Arrow for query execution, with extensions disabled by hardening).

## Why This Approach
1. **Performance & Ecosystem via Narwhals:** The compute pipeline will be completely refactored to use Narwhals. This allows us to write the scoring/filtering logic using Polars-style expressions but execute it natively and losslessly on *either* Polars (for GPU acceleration / multithreading) or PyArrow-backed Pandas (for compatibility with existing TA libraries). 
2. **Rejecting Ibis:** We are explicitly rejecting Ibis because it is a heavy query compiler meant for external databases. Narwhals, on the other hand, is a zero-dependency local dataframe abstraction layer that perfectly fits our need for a lightweight, flexible compute engine.
3. **Resilience & Idempotency:** DuckDB errors should not prevent producing canonical medallion outputs. By keeping DuckDB at the edge, the pipeline computes and persists Bronze/Silver/Gold to Iceberg, and the user's SQL only affects *post-run* analysis/printing.
4. **Agentic Workflows:** Agents should be able to query historical runs without re-fetching TradingView. Iceberg tables + `EdgeQueryClient` enable fast SQL and Narwhals transforms over persisted snapshots.

## Key Decisions
- **Adopt Narwhals for Compute:** Rewrite all intermediate pipeline logic (scoring/filtering) using Narwhals' Polars-style expressions to support both Polars and PyArrow-backed Pandas.
- **Reject Ibis:** Avoid Ibis in favor of Narwhals to maintain a lightweight, zero-dependency local dataframe abstraction.
- **Remove `DuckDBFilter` from Pipeline:** The `post_filters` pipeline step will no longer execute user SQL during the scan. 
- **Enforce Iceberg Checkpoints:** The pipeline persists Bronze/Silver/Gold to Iceberg as the canonical store (lakehouse-first).
- **Data Validation:** We will enforce strict dtypes at the Silver layer boundary to prevent silent downstream scoring failures (avoiding heavy external dependencies like `pandera`).
- **Keep DuckDB at the Edge (`EdgeQueryClient`):** DuckDB runs against Iceberg identifiers by scanning Iceberg to Arrow and registering relations/views for SQL execution (with external access disabled).
- **Universal Output Stage (Feature Parity):** Restore specialized Matrix/Detailed views for SQL results by refactoring the renderer to accept external data and using Narwhals to re-standardize schemas across backends.

## Multi-timeframe focus

Multi-timeframe is a first-class requirement:

- **Short-term (wide)**: timeframe-as-columns is acceptable for matrix UX, but must be keyed by `timeframe_set_id`.
- **Long-term (long)**: introduce long-form feature tables with a `timeframe` column and materialize matrix-ready products from them.

## Separation of concerns: data vs analytics pipelines

- **Data pipelines**: produce canonical Iceberg tables (Bronze/Silver/Gold) and MUST NOT depend on a specific query engine.
- **Analytics pipelines**: consume Iceberg tables and can use different query backends (DuckDB today; others later) to produce:
  - `signals_latest`
  - future `signals_batch` and other strategy/ranking outputs

## Open Questions
- Should the `EdgeQueryClient` replace the native Rich console rendering entirely, or just act as a pre-filter before handing the DataFrame back to the Rich renderer?
- Do we need to migrate the existing `tvscreener-scan` CLI into two separate subcommands (`run` vs `query`), or keep the current UX where passing `--sql` means "run/persist the pipeline to Iceberg, and then query Iceberg before printing"?

## Next Steps
Create actionable implementation tasks in the `todos/` directory using the `file-todos` skill.
