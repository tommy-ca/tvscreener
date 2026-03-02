---
status: complete
priority: p1
issue_id: "132"
tags: [architecture, duckdb, performance, medallion]
dependencies: []
---

# Remove DuckDBFilter from Intermediate Pipeline

## Problem Statement
The current pipeline evaluates user-defined SQL queries (`--sql`) during the `post_filters` execution phase using `DuckDBFilter`. This breaks idempotency, couples the data compute layer to DuckDB, and forces expensive serialization between Pandas and DuckDB mid-stream. In our new Narwhals-driven Medallion architecture, intermediate compute must remain pure and dataframe-agnostic.

## Findings
- `DuckDBFilter` creates an in-memory database and registers the dataframe for every execution.
- If a user passes invalid SQL, the entire pipeline fails, meaning the TradingView API fetch must be repeated.
- The pipeline architecture should be purely Python/Narwhals to ensure determinism.

## Proposed Solutions
1. **Remove `DuckDBFilter` completely**: Delete the class from `filters.py`.
2. **Remove `--sql` from pipeline**: Remove logic in `orchestrator.py` that appends `DuckDBFilter` to the `post_filters` list.
3. **Keep `MTFExpressionParser` natively**: The `--filter` argument translates into native Pandas/Narwhals evaluation. Disable the DuckDB pass-through.

## Recommended Action
Implement solution 1 & 2. Delete `DuckDBFilter` from `filters.py` and rip out the `request.sql` appending logic from `orchestrator.py`.

## Acceptance Criteria
- [ ] `DuckDBFilter` class deleted from `tvscreener/lib/screeners/filters.py`
- [ ] `orchestrator.py` no longer checks `request.sql` or appends to `post_filters` during scan execution
- [ ] Pipeline runs end-to-end natively without any DuckDB instantiation mid-stream

## Work Log
### 2026-03-02 - Task Created
- Created as part of the Medallion Architecture modernization plan.
