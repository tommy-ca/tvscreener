---
status: complete
priority: p1
issue_id: "146"
tags: [infrastructure, iceberg, storage]
dependencies: ["145"]
---

# Implement Iceberg Storage Backend for ExportMixin

## Problem Statement
We need to standardize how data is written to Iceberg tables across both the Opportunity and Strategy scanners.

## Findings
- All scanners use `ExportMixin`.
- Writing to Iceberg requires converting to Arrow first.

## Proposed Solutions
1. **Unified Storage Class**: Implement `IcebergStorage` to wrap `pyiceberg` table appends.
2. **Narwhals-to-Iceberg**: Use `nw.to_arrow()` as the bridge.
3. **Data Preparation**: Implement a `prepare_arrow()` helper to cast timestamps to microsecond (`us`) precision to meet Iceberg requirements.
4. **Schema Evolution**: Implement manual `union_by_name` logic before appends to support adding new technical indicators.

## Recommended Action
Add `write_iceberg` method to the pipeline utilities. Update `ExportMixin` to support an `iceberg` format. Handle timestamp precision and schema evolution explicitly.

## Acceptance Criteria
- [ ] `Gold` signals can be appended to an Iceberg table via the CLI.
- [ ] Polars `ns` timestamps are correctly cast to `us` before ingestion.
- [ ] New technical columns are automatically added to the table schema via `union_by_name`.
- [ ] Transactions are committed atomically; failed writes don't corrupt table state.

## Work Log
### 2026-03-02 - Task Created
- Part of Iceberg Lakehouse migration.
