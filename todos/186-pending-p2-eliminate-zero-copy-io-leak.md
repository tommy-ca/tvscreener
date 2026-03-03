---
status: completed
priority: p2
issue_id: "186"
tags: [performance, duckdb, zero-copy, orchestrator]
dependencies: []
---

# Eliminate Zero-Copy I/O Leak in Orchestrator

## Problem Statement

The `orchestrator.py` module writes DataFrames to `tvscreener_edge_cache.parquet` on disk solely to run DuckDB SQL queries against them. This introduces unnecessary disk I/O, which defeats the purpose of DuckDB's high-performance in-memory zero-copy capabilities when working with PyArrow or Pandas DataFrames.

## Findings

- `orchestrator.py` writes a temporary cache file (`tvscreener_edge_cache.parquet`) when it already holds the DataFrame in memory.
- DuckDB natively supports querying Pandas and PyArrow DataFrames directly without persisting to disk.
- This redundant disk write degrades query performance, especially for larger datasets.

## Proposed Solutions

### Option 1: Pass DataFrame directly to DuckDB

**Approach:** Pass the DataFrame directly into `EdgeQueryClient.query_sql()` and leverage DuckDB's native zero-copy Arrow/Pandas ingestion. Remove all logic related to writing and cleaning up the `tvscreener_edge_cache.parquet` file.

**Pros:**
- Eliminates unnecessary disk I/O.
- Substantially improves query performance.
- Simplifies the `orchestrator.py` logic.

**Cons:**
- Minimal, primarily requires ensuring `EdgeQueryClient` handles DataFrame objects seamlessly.

**Effort:** 1-2 hours
**Risk:** Low

## Recommended Action

Implement Option 1. Modify `orchestrator.py` to skip the parquet file write and directly pass the DataFrame into `EdgeQueryClient.query_sql()`. Ensure any cache file cleanup logic is removed.

## Technical Details

**Affected files:**
- `tvscreener/lib/orchestrator.py`
- `tvscreener/lib/query.py`

**Related components:**
- DuckDB edge querying logic

## Resources

- DuckDB Python API documentation on DataFrame querying

## Acceptance Criteria

- [x] `orchestrator.py` no longer writes `tvscreener_edge_cache.parquet` to disk.
- [x] DataFrames are passed directly into DuckDB SQL queries via `EdgeQueryClient`.
- [x] Tests pass when executing `uv run pytest`.
- [x] Overall execution time for queries handled by `orchestrator.py` is demonstrably reduced or I/O load is minimized.

## Work Log

### 2026-03-03 - Initial Creation

**By:** Claude Code

**Actions:**
- Created todo from issue findings.

### 2026-03-03 - Implementation

**By:** Claude Code

**Actions:**
- Modified `tvscreener/lib/orchestrator.py` to pass DataFrames directly to `query_sql`.
- Removed cache file logic from `orchestrator.py`.
- Updated `tvscreener/lib/query.py` to support DataFrames, Narwhals frames, and Arrow objects in `get_relation`.
- Fixed broken Narwhals chains in `score.py` and `forex_strategy.py` to restore test passing state.
- Verified with `uv run pytest`.
