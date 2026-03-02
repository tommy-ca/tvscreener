---
status: completed
priority: p1
issue_id: "095"
tags: [architecture, new-feature, mtf, duckdb]
dependencies: ["094"]
---

# Implement DuckDBEngine utility for zero-copy DataFrame querying

## Problem Statement

To power the `MTFScanner` and `SQLScanner`, we need a robust interface between our internal Pandas DataFrames and DuckDB's execution engine. This engine needs to handle view registration, error management, and seamless Pandas conversion.

## Findings

- DuckDB supports querying Pandas DataFrames directly if they are stored in local variables (via replacement scans).
- However, for an encapsulated library, explicitly registering DataFrames as virtual tables (views) using `duckdb.register("view_name", df)` is safer and prevents scope resolution issues.

## Proposed Solutions

### Option 1: Create `tvscreener/lib/screeners/duckdb_engine.py`

**Approach:** 
Create a class `DuckDBEngine` that:
1. Initializes an in-memory database (`duckdb.connect()`).
2. Provides a `register_df(name, df)` method.
3. Provides a `query(sql) -> pd.DataFrame` method.

**Pros:**
- Encapsulates DuckDB specific API away from the core screener logic.
- Makes testing easier by allowing mock connections.

**Effort:** 1-2 hours
**Risk:** Low

## Acceptance Criteria

- [x] `DuckDBEngine` class implemented in `tvscreener/lib/screeners/duckdb_engine.py`.
- [x] Supports registering DataFrames.
- [x] Supports executing SQL strings and returning DataFrames.
- [x] Unit tests added.
