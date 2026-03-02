---
status: ready
priority: p1
issue_id: "142"
tags: [architecture, iceberg, storage]
dependencies: ["134"]
---

# Implement Apache Iceberg Storage Layer

## Problem Statement
The current pipeline uses loose Parquet files. We need a formal Lakehouse format to support schema evolution, atomic commits, and snapshot management.

## Findings
- `pyiceberg` supports a local `SqliteCatalog` which is perfect for a CLI.
- DuckDB has an `iceberg` extension for native table scanning.

## Proposed Solutions
1. **PyIceberg Integration**: Add `pyiceberg[sqlalchemy,pyarrow]` to dependencies.
2. **Catalog Initialization**: Setup a local SQLite catalog at `~/.tvscreener/catalog.db`.
3. **Table Lifecycle**: Implement `IcebergScreenerStorage` to handle creating and appending to `bronze_raw`, `silver_standardized`, and `gold_signals` tables.

## Recommended Action
Implement the Iceberg storage layer using `pyiceberg`. Update `ExportMixin` to support `format="iceberg"`.

## Acceptance Criteria
- [ ] `pyiceberg` added to `pyproject.toml`.
- [ ] Local SQLite catalog initializes automatically.
- [ ] `Gold` data is appended to an Iceberg table.
- [ ] DuckDB `query_sql` works against `iceberg_scan('tvscreener.gold_signals')`.

## Work Log
### 2026-03-02 - Task Created
- Transitioning to Iceberg Medallion Pipeline.
