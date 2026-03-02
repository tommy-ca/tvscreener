---
status: ready
priority: p2
issue_id: "144"
tags: [architecture, iceberg, backtesting]
dependencies: ["142"]
---

# Implement Iceberg Snapshot (Time-Travel) Queries

## Problem Statement
Users need to query historical states of the Gold signals table to audit signal drift or perform backtests.

## Findings
- Iceberg natively supports snapshots with a unique `snapshot_id`.
- DuckDB's `iceberg_scan` can take a `snapshot_id` parameter.

## Proposed Solutions
1. **Metadata Discovery**: Add a tool to list available Iceberg snapshots for a table.
2. **CLI Parameter**: Add `--snapshot` or `--timestamp` to `tvscreener-scan query`.

## Recommended Action
Expose Iceberg snapshot queries through the `EdgeQueryClient` and CLI.

## Acceptance Criteria
- [ ] Users can run `tvscreener-scan query --table gold_signals --snapshot 123456789`.
- [ ] `EdgeQueryClient` correctly passes the snapshot requirement to DuckDB.

## Work Log
### 2026-03-02 - Task Created
- Transitioning to Iceberg Medallion Pipeline.
