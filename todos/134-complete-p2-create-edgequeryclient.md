---
status: complete
priority: p2
issue_id: "134"
tags: [architecture, duckdb, serving, medallion]
dependencies: ["132"]
---

# Create DuckDB EdgeQueryClient

## Problem Statement
With DuckDB removed from the intermediate pipeline (Task 132), we need a mechanism for users and MCP agents to query the finalized Gold Parquet datasets using SQL. DuckDB belongs exclusively at the edge.

## Findings
- The pipeline currently writes final exported Parquet files via `ExportMixin`.
- Users still need the ability to run `--sql "SELECT * FROM df WHERE TREND > 0"`.

## Proposed Solutions
1. **Edge Client**: Create a new class `EdgeQueryClient` in `tvscreener/lib/query.py` that mounts an in-memory DuckDB connection.
2. **Execution Context**: When `request.sql` is provided, wait until the pipeline finishes exporting the `output` Parquet file. Then, use `EdgeQueryClient` to execute the user's SQL query against `read_parquet('exports/gold/...')` and return a DataFrame.
3. **Console Routing**: Pass the resulting dataframe to the Rich console rendering functions instead of the raw pipeline output.

## Recommended Action
Implement `EdgeQueryClient` as the sole SQL interface for `tvscreener`.

## Acceptance Criteria
- [ ] New `EdgeQueryClient` class created.
- [ ] `ScreenerController` intercepts `--sql` queries and routes them to the `EdgeQueryClient` *after* pipeline execution.
- [ ] CLI rendering respects the filtered DuckDB dataframe output.

## Work Log
### 2026-03-02 - Task Created
- Created as part of the Medallion Architecture modernization plan.
