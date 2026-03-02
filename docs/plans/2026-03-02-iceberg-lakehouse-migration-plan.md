---
date: 2026-03-02
topic: iceberg-lakehouse-migration
---

# Iceberg Lakehouse Migration Plan

This plan outlines the systematic migration of the `tvscreener` pipeline into a structured **Apache Iceberg Lakehouse** with a **Medallion Architecture**.

## 1. Architectural Foundation
We will use `pyiceberg` to manage a local SQLite-backed catalog. Data processing will remain backend-agnostic via `narwhals`, with storage persisted in transactional Iceberg tables.

### 1.1 Medallion Layers
1.  **Bronze (`tvscreener.bronze`)**: Raw TradingView API response schema. Partitioned by `ingest_date` and `ingest_hour`. Used for idempotency and replaying scans.
2.  **Silver (`tvscreener.silver`)**: Normalized and cleaned data. Deduplicated by pair/broker using `EXCHANGE_PRIORITY`. Brittle raw columns (e.g. `Recommend.All|15`) are mapped to canonical technical names (`trend_15`). Null values are filled with neutral 0.0. Partitioned by `asset_type`. *Optional Z-Score volume outlier detection is available but disabled by default.*
3.  **Gold (`tvscreener.gold`)**: Scored signals and strategy features. Includes `ENSEMBLE_SCORE`, `CONFLUENCE_SCORE`, Grading, and Signal Detection results. Includes full Risk management outputs (SL/TP). Partitioned by `signal_date`. This is the source of truth for the UI and edge analytics.

## 2. Phase 1: Storage Layer & Catalog (Infrastructure)
*   **Action**: Integrate `pyiceberg` and setup the `SqliteCatalog`.
*   **Command**: `uv add "pyiceberg[sql-sqlite,pyarrow]"`
*   **Location**: `~/.tvscreener/lakehouse/` (Catalog DB + Warehouse directory).
*   **Key Interface**: `IcebergCatalogManager` class to encapsulate catalog loading and table creation.

## 4. Phase 3: Analytics Integration (Serving)
*   **Action**: Update `EdgeQueryClient` to resolve Iceberg table names using the catalog.
*   **DuckDB Bridge**: Use `table.to_arrow()` to register Iceberg snapshots as DuckDB virtual views for zero-copy querying.
*   **CLI UX**: Users query tables (`uv run tvscreener-scan query --table gold`) instead of raw files.

---
## Verification Strategy
- **Unit Tests**: Test `IcebergCatalogManager` table creation/deletion via `uv run pytest`.
- **Integration Tests**: Verify a full scan results in data being queryable in DuckDB via the Iceberg extension.
- **Parity Test**: Ensure `Gold` Iceberg data matches the previously exported Parquet files perfectly.

