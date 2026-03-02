---
status: complete
priority: p1
issue_id: "145"
tags: [infrastructure, iceberg, catalog]
dependencies: ["134"]
---

# Initialize Apache Iceberg Local Catalog

## Problem Statement
To transition to a Lakehouse architecture, we need a way to manage table metadata, schemas, and transactions. We need a lightweight, local, and transactional catalog for the CLI.

## Findings
- `pyiceberg` supports a `SqliteCatalog`.
- We can store the catalog database in `~/.tvscreener/lakehouse/catalog.db`.

## Proposed Solutions
1. **Catalog Manager**: Create `tvscreener/lib/lakehouse/catalog.py` containing `IcebergCatalogManager`.
2. **Auto-Initialization**: Ensure the catalog and warehouse directories are created automatically on first run.

## Recommended Action
Implement `IcebergCatalogManager` using `pyiceberg`. Ensure it resolves user home paths correctly.

## Acceptance Criteria
- [ ] `pyiceberg[sql-sqlite,pyarrow]` added to dependencies.
- [ ] `IcebergCatalogManager` implemented with support for absolute path SQLite URIs (e.g. `sqlite:////abs/path`).
- [ ] Catalog and warehouse directories automatically provisioned in `~/.tvscreener/lakehouse/`.
- [ ] `load_catalog()` successfully connects to the local SQLite DB.

## Work Log
### 2026-03-02 - Task Created
- Part of Iceberg Lakehouse migration.
