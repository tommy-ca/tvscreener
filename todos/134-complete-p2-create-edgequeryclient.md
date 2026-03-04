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
- The pipeline persists canonical outputs to Iceberg medallion tables (`tvscreener.*`).
- Users still need the ability to run `--sql "SELECT * FROM df WHERE TREND > 0"` against either:
  - an Iceberg table identifier (preferred), or
  - an explicitly provided snapshot file path (optional artifact).

## Proposed Solutions
1. **Edge Client**: Create a new class `EdgeQueryClient` in `tvscreener/lib/query.py` that mounts an in-memory DuckDB connection.
2. **Execution Context**: When `request.sql` is provided, route the SQL through `EdgeQueryClient` against the in-memory results dataframe or an Iceberg table identifier (preferred). Avoid hard dependencies on repository-local parquet paths.
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
