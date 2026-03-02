---
status: complete
priority: p2
issue_id: "136"
tags: [mcp, agents, duckdb]
dependencies: ["134"]
---

# Update MCP Server Tools for Edge Querying

## Problem Statement
MCP Agents currently trigger a full TradingView API ingestion sequence every time they want to query data. With DuckDB shifted to the edge and the final datasets cached as Parquet files, agents should be able to query historical datasets directly without invoking the upstream API.

## Findings
- `mcp/server.py` and `mcp/tools.py` bind directly to the `ScreenerController` run logic.
- We need to expose the newly created `EdgeQueryClient` directly to agents.

## Proposed Solutions
1. **Separate Scan and Query Tools**: 
   - Keep `scanner_opportunities` and `scanner_strategies` for running fresh data ingestion.
   - Create a new tool `query_historical_scan(sql: str, file_path: str)` that uses `EdgeQueryClient` to execute SQL over a previously generated Parquet file.

## Recommended Action
Add the `query_historical_scan` tool to the FastMCP server.

## Acceptance Criteria
- [ ] `query_historical_scan` tool implemented and exposed via MCP.
- [ ] Tool docstring explicitly explains that agents should use this to query data they already exported instead of running fresh scans.

## Work Log
### 2026-03-02 - Task Created
- Created as part of the Medallion Architecture modernization plan.
