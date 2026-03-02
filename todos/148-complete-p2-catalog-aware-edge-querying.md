---
status: complete
priority: p2
issue_id: "148"
tags: [architecture, duckdb, catalog]
dependencies: ["145"]
---

# Implement Catalog-Aware Edge Querying in DuckDB

## Problem Statement
`EdgeQueryClient` currently only knows how to read raw Parquet files. It should be aware of the Iceberg catalog to allow querying by table name (e.g. `SELECT * FROM gold_signals`).

## Findings
- DuckDB can register PyArrow tables as virtual views.
- `pyiceberg` can load an Iceberg table into a PyArrow table.

## Proposed Solutions
1. **Table Resolver**: Update `EdgeQueryClient` to resolve logical table names using `IcebergCatalogManager`.
2. **Zero-Copy Bridge**: Extract `table.metadata_location` and pass it to DuckDB's native `iceberg_scan()` function for maximum performance.
3. **Fallback**: If `iceberg_scan` fails, fall back to registering the PyArrow table directly in DuckDB.

## Recommended Action
Update `EdgeQueryClient.query_sql` to handle table names by resolving them through the catalog.

## Acceptance Criteria
- [ ] `tvscreener-scan query --table gold` works without specifying a file path.
- [ ] DuckDB uses its C++ Iceberg engine to read manifest/metadata JSON files resolved from the SQLite catalog.
- [ ] Sub-second query latency on tables with multiple historical snapshots.

## Work Log
### 2026-03-02 - Task Created
- Part of Iceberg Lakehouse migration.
