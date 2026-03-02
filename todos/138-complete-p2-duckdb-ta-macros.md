---
status: complete
priority: p2
issue_id: "138"
tags: [architecture, duckdb, quantitative]
dependencies: ["137"]
---

# Implement DuckDB TA Indicator Macros

## Problem Statement
Calculating Technical Analysis indicators (like SMA, RSI, ATR) currently requires loading data into Pandas/Narwhals memory. For large-scale edge analytics, it is more efficient to run these calculations directly in the DuckDB engine using window functions.

## Findings
- DuckDB supports SQL Macros and Window Functions (`AVG(...) OVER (...)`).
- Moving compute to the data (in-database) significantly improves performance for large Parquet files.

## Proposed Solutions
1. **Register Macros**: Create a `_setup_ta_macros()` method in `EdgeQueryClient`.
2. **Standard Indicators**: Implement SMA and Bollinger Bands macros as a start.
3. **Narwhals Bridge**: Ensure `query_expr` can leverage these in-database calculations.

## Recommended Action
Implement SQL macros for common indicators during `EdgeQueryClient` initialization.

## Acceptance Criteria
- [ ] `sma(col, period)` macro registered and working in `query_sql`.
- [ ] Bollinger Band macros (upper/lower) registered.
- [ ] Unit test verifies that DuckDB SMA matches Pandas/TA-Lib output within float precision.

## Work Log
### 2026-03-02 - Task Created
- Part of Phase 2 architecture modernization.
