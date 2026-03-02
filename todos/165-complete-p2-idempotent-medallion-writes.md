---
status: complete
priority: p2
issue_id: "165"
tags: [architecture, iceberg, medallion, storage]
dependencies: []
---

# Implement Idempotent Medallion Writes

Enable idempotent writes in `IcebergStorage` to prevent duplicates on retry.

## Problem Statement

The current implementation of `IcebergStorage.write` uses blind appends. If a write operation is retried due to a transient failure or timeout, it can result in duplicate data being written to the Iceberg table. To support a robust Medallion architecture, writes must be idempotent.

## Findings

- `IcebergStorage.write` lacks support for different write modes.
- No mechanism currently exists for overwrite-by-partition, which is essential for re-processing data.

## Proposed Solutions

### Option 1: Basic Write Modes

**Approach:** Add a `mode` parameter to `IcebergStorage.write` with support for `"append"` (default) and `"overwrite"`.

**Pros:**
- Simple to implement.
- Prevents full table duplicates if `overwrite` is used.

**Cons:**
- Full table overwrite is inefficient for large datasets.

**Effort:** 2-3 hours

**Risk:** Low

---

### Option 2: Overwrite-by-Partition

**Approach:** Implement `overwrite` with partition-level granularity. This allows replacing only the data in specific partitions (e.g., a specific date or asset class) without affecting the rest of the table.

**Pros:**
- Highly efficient for Medallion architecture re-processing.
- Industry-standard approach for idempotent ETL.

**Cons:**
- Requires reliable partition detection from the incoming DataFrame.
- More complex PyIceberg implementation.

**Effort:** 5-8 hours

**Risk:** Medium

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lib/storage/iceberg.py` (assuming path based on context)

**Related components:**
- Data ingestion pipeline
- Medallion layer (Bronze/Silver/Gold)

**Database changes (if any):**
- No (Iceberg table metadata updates only)

## Resources

- [PyIceberg Write API](https://pyiceberg.apache.org/api/#writing-data)
- [Iceberg Partitioning Docs](https://iceberg.apache.org/spec/#partitioning)

## Acceptance Criteria

- [x] `IcebergStorage.write` accepts `mode="append"|"overwrite"`.
- [x] `mode="overwrite"` correctly replaces data based on table partitioning (dynamic partition overwrite).
- [x] Tests verify that retrying an `overwrite` write does not result in duplicates.
- [x] Integration test with a partitioned table confirms only affected partitions are modified.

## Work Log

### 2026-03-02 - Implementation Completed

**By:** Antigravity

**Actions:**
- Updated `IcebergStorage.write` to support `mode` and `partition_by`.
- Implemented dynamic partition overwrite using PyIceberg's `table.overwrite()`.
- Updated Medallion layer to use `overwrite` for Silver/Gold and added automatic partitioning columns.
- Added comprehensive unit tests in `tests/unit/test_iceberg_storage.py`.

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo for idempotent medallion writes.
- Defined requirements for partition-level overwrites.

**Learnings:**
- Blind appends are a significant risk in distributed data systems.

## Notes

- Ensure `overwrite` mode is the default for "Gold" layer tables to maintain data integrity.
