---
status: complete
priority: p2
issue_id: "102"
tags: [performance, duckdb, pandas]
dependencies: []
---

# Optimize DuckDB Zero-Copy Integration

## Problem Statement
The proposed `DataFrameFilter` protocol evaluates to `pd.DataFrame` at every step. If multiple DuckDB filters are pipelined sequentially, this forces intermediate materializations (copying C++ columnar data back to Pandas NumPy arrays repeatedly), completely destroying the "zero-copy" benefits. Furthermore, Pandas object-strings force memory copies.

## Findings
- Performance Oracle highlighted the O(N) serialization cost of sequential Pandas materialization.
- Using the PyArrow dtype backend in Pandas ensures true zero-copy text transfers to DuckDB.

## Proposed Solutions

### Option 1: Lazy Evaluation and PyArrow Backend
**Approach:** 
1. Convert the DataFrame to PyArrow strings in `DataTransformer` (`df.convert_dtypes(dtype_backend='pyarrow')`).
2. Update the `DataFrameFilter` protocol to accept and return either a `pd.DataFrame` or a `duckdb.DuckDBPyRelation`, deferring the final `.df()` materialization until all filters are applied.

## Acceptance Criteria
- [x] Enriched DataFrame uses PyArrow dtypes for strings before hitting DuckDB.
- [x] Intermediate pipeline steps do not force `.df()` materialization.

## Work Log
### 2026-03-01 - Fix DuckDB Zero-Copy Integration

**Actions:**
- Edited `tvscreener/lib/screeners/base.py` to add `df = cast(pd.DataFrame, df.convert_dtypes(dtype_backend="pyarrow"))` inside `get_opportunities()`.
- Added support for lazy evaluation in `_prepare_enriched_data()` by converting relation to DataFrame at the end using `if not isinstance(df, pd.DataFrame): df = df.df()`.
- Updated `tvscreener/lib/screeners/filters.py` to accept and return `DuckDBPyRelation` in the `DataFrameFilter` protocol.
- Made `import duckdb` conditional in `filters.py` and handled execution to keep DuckDB queries lazy until explicitly materialized.