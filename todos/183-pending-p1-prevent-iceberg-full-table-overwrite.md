---
status: completed
priority: p1
issue_id: "183"
tags: [data-integrity, iceberg, pipeline]
dependencies: []
---

# Prevent Iceberg Full Table Overwrite

## Problem Statement

Data Integrity risk: `table.overwrite()` in `LakehouseManager` without an `overwrite_filter` drops the entire historical table during Silver/Gold stages.

## Findings

- `LakehouseManager` currently invokes `table.overwrite()` without partition filters.
- This causes the entire history of the Iceberg table to be dropped and replaced only with the current batch's data.

## Proposed Solutions

### Option 1: Apply Dynamic Partition Filters

**Approach:** Calculate and apply dynamic partition filters (e.g., `Equal("signal_date", current_date)`) when overwriting to ensure only the latest batch is replaced.

**Pros:**
- Safely overwrites only the specific partition being processed.
- Maintains historical data.

**Cons:**
- Requires identifying the correct partition column dynamically.

**Effort:** 2 hours

**Risk:** Low

## Recommended Action

Implement dynamic partition filtering in `LakehouseManager`'s overwrite method to ensure data integrity during Silver/Gold stage processing.

## Technical Details

**Affected components:**
- `LakehouseManager` (`table.overwrite()`)
- Silver/Gold pipeline stages

## Acceptance Criteria

- [x] `LakehouseManager` is updated to accept and apply an `overwrite_filter`.
- [x] Silver/Gold stage processing logic passes the correct partition filter (e.g., `signal_date`).
- [x] Tests verify that historical data is preserved during an overwrite operation.
- [x] Run `uv run pytest` to confirm no regressions and that the new tests pass.

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Opencode

**Actions:**
- Created P1 todo based on code findings regarding Iceberg overwrite behavior.
- Documented the need for dynamic partition filters.

### 2026-03-03 - Implementation

**By:** Opencode (PR Comment Resolver Agent)

**Actions:**
- Updated `LakehouseManager.write_table` to accept `overwrite_filter` and calculate it automatically from `partition_by`.
- Updated `tvscreener/lib/screeners/pipeline.py` to use multi-column partitioning (`asset_type` + date) for Silver/Gold stages.
- Added unit tests for multi-column partition filters and explicit overwrite filters.
- Verified with `pytest`.

## Notes

- Critical path issue as it leads to historical data loss during data pipeline stages.
