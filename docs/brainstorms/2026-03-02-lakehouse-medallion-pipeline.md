# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
date: 2026-03-02
topic: lakehouse-medallion-pipeline
---

# Lakehouse Medallion Pipeline: Narwhals Compute & Apache Iceberg Storage

## What We're Building
A high-performance, backend-agnostic quantitative data pipeline for `tvscreener`. This architecture migrates the current monolithic script into a structured **Lakehouse Medallion Pipeline** (Bronze -> Silver -> Gold) powered by **Apache Iceberg**.

### Core Components:
1.  **Storage Layer (Apache Iceberg)**: Using `pyiceberg` for transactional, spec-compliant table management. We will use a local **SqliteCatalog** (`~/.tvscreener/iceberg.db`) to manage table metadata and schemas without an external server.
2.  **Compute Layer (Narwhals)**: All ingestion, transformation, and scoring logic is written once using **Narwhals expressions**. This allows the pipeline to execute natively on either **Pandas** or **Polars**.
3.  **Edge Analytics (DuckDB)**: DuckDB is the high-performance serving layer. It connects to the same Iceberg catalog to perform SQL queries over the finalized Gold tables.

---

## The Medallion Flow

### 1. Bronze (Raw Ingestion)
*   **Action**: Fetch chunked JSON from TradingView.
*   **Storage**: Iceberg Table `tvscreener.bronze_raw`.
*   **Schema**: Loose/Open schema to capture raw API state.

### 2. Silver (Standardization)
*   **Action**: Read Bronze via Narwhals.
*   **Transformation**: Deduplicate, normalize column names, handle nulls.
*   **Validation**: Enforce Iceberg schema contracts.
*   **Storage**: Iceberg Table `tvscreener.silver_standardized`.

### 3. Gold (Feature Engineering & Scoring)
*   **Action**: Read Silver.
*   **Transformation**: Compute indicators and final signals using Narwhals.
*   **Storage**: Iceberg Table `tvscreener.gold_signals`. This is the source of truth.

---

## Why Apache Iceberg?
1.  **Schema Evolution**: Iceberg supports full schema evolution (add/drop/rename columns) without rewriting the entire data lake. This is critical as TradingView API fields change.
2.  **Partition Spec Evolution**: We can change how we partition data (e.g., from `pair` to `timestamp`) on the fly.
3.  **Hidden Partitioning**: Iceberg handles the complex folder logic for us; the CLI just queries the table name.
4.  **Zero-Copy Analytics**: DuckDB's `iceberg` extension reads Iceberg manifest files directly, ensuring it always sees the latest atomic snapshot.
5.  **Snapshots/Rollbacks**: Users can query historical snapshots to audit how signals changed over time.

---

## Key Decisions
- **Catalog Strategy**: Use `SqliteCatalog` for local transactional safety.
- **Unified Interface**: Use `pyiceberg` to write and DuckDB to read.
- **Edge-Only DuckDB**: DuckDB is strictly for analytics; `pyiceberg` + `narwhals` handles the pipeline math.

---

## Next Steps
→ `/workflows:plan` for implementation tasks in `todos/`.
