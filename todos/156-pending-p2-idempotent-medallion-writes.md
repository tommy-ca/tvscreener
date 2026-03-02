---
status: pending
priority: p2
issue_id: "156"
tags: [architecture, medallion, storage, iceberg]
dependencies: []
---

# Implement Idempotent Medallion Writes

`IcebergStorage.write` uses blind appends, creating duplicates on retry.

## Problem Statement

The current implementation of `IcebergStorage.write` performs blind appends to the Iceberg tables. If a write operation fails partially or is retried due to a transient error, it can result in duplicate data being written to the table. This compromises data integrity and complicates downstream processing.

## Findings

- `IcebergStorage.write` lack support for `mode="overwrite"`.
- It currently only supports blind appends.
- Retries lead to duplicates.

## Proposed Solutions

### Option 1: Implement `mode` parameter in `IcebergStorage.write`

**Approach:** Add a `mode` parameter to the `write` method, supporting `"append"` (current behavior) and `"overwrite"`.

**Pros:**
- Standardizes write operations.
- Provides a clear mechanism for idempotency.

**Cons:**
- Overwriting the entire table might be too heavy for large tables.

**Effort:** 1-2 hours

**Risk:** Low

---

### Option 2: Overwrite-by-partition

**Approach:** Implement a more granular overwrite mechanism that replaces only the relevant partitions (e.g., for a specific date or ticker) instead of the whole table.

**Pros:**
- More efficient than full table overwrites.
- Highly resilient to partial failures within a specific data batch.

**Cons:**
- More complex to implement correctly (requires identifying affected partitions).
- Depends on how tables are partitioned in Iceberg.

**Effort:** 3-5 hours

**Risk:** Medium

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lib/storage/iceberg.py` (Identify the `IcebergStorage` class and its `write` method)

## Acceptance Criteria

- [ ] `IcebergStorage.write` supports `mode="append"|"overwrite"`.
- [ ] `mode="overwrite"` correctly replaces existing data (either full table or by partition).
- [ ] Retrying a write operation with `mode="overwrite"` does not result in duplicate data.
- [ ] Tests verify idempotency for both append and overwrite modes.

## Work Log

### 2026-03-02 - Initial Entry

**By:** Antigravity

**Actions:**
- Created todo for implementing idempotent medallion writes.
- Identified blind appends as the cause of potential data duplication.
- Proposed `mode` support and overwrite-by-partition as solutions.

## Notes

- This is a fundamental architectural improvement for data reliability.
