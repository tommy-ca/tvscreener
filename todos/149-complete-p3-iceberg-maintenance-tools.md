---
status: complete
priority: p3
issue_id: "149"
tags: [infrastructure, iceberg, maintenance]
dependencies: ["145"]
---

# Implement Iceberg Lakehouse Maintenance Tools

## Problem Statement
A Lakehouse requires periodic maintenance to stay performant. We need tools to clean up old snapshots, expire data, and compact small files.

## Findings
- `pyiceberg` provides APIs for `expire_snapshots()`.
- Multiple scan runs create many small Parquet files, which can degrade DuckDB query performance over time.

## Proposed Solutions
1. **Maintenance Tool**: Add a `maintenance` command to the CLI.
2. **Snapshot Expiry**: Implement logic to keep only the last $N$ days of snapshots to save disk space.
3. **Compaction**: Implement a basic file compaction routine (reading and rewriting data into fewer, larger Parquet files).

## Recommended Action
Implement a basic snapshot expiry and metadata cleanup utility in the `IcebergCatalogManager`.

## Acceptance Criteria
- [ ] CLI command `tvscreener-scan maintenance --expire-snapshots` works.
- [ ] Successfully removes old metadata JSON files and unreferenced Parquet files.
- [ ] Disk usage is reduced after running maintenance.

## Work Log
### 2026-03-02 - Task Created
- Transitioning to Iceberg Lakehouse migration.
