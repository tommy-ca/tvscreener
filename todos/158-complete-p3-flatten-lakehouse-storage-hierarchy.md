---
status: complete
priority: p3
issue_id: "158"
tags: [architecture, storage, iceberg]
dependencies: []
---

# Flatten Lakehouse Storage Hierarchy

Merge storage functions into `catalog.py` or standalone utilities to remove the state-less indirection caused by `IcebergStorage`.

## Problem Statement

The current storage hierarchy is unnecessarily deep: `IcebergCatalogManager` -> `IcebergStorage` -> `write_iceberg`. The `IcebergStorage` class is a state-less indirection that doesn't provide significant value, adding complexity to the call stack and making the codebase harder to navigate.

## Findings

- `IcebergStorage` acts as a middleman between the catalog manager and the actual writing functions.
- The class does not maintain any instance state that justifies its existence.
- This pattern of "indirection for the sake of indirection" complicates the architecture without providing clear benefits like abstraction or decoupled testing.

## Proposed Solutions

### Option 1: Merge into Catalog Manager

**Approach:** Move the logic from `IcebergStorage` directly into `IcebergCatalogManager`.

**Pros:**
- Flattens the hierarchy.
- Reduces the number of files/classes to manage.

**Cons:**
- Might make `IcebergCatalogManager` too large if not careful.

**Effort:** 2-3 hours

---

### Option 2: Standalone Utilities

**Approach:** Convert `IcebergStorage` methods into standalone utility functions in a `storage_utils.py` or similar, or merge into `catalog.py` as top-level functions.

**Pros:**
- Keeps the catalog manager focused on catalog operations.
- Functional approach is often cleaner for state-less logic.

**Cons:**
- Still requires importing from another location, but removes the class indirection.

**Effort:** 2-3 hours

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lakehouse/catalog.py` (potential target for merged logic)
- `tvscreener/lakehouse/storage.py` (contains `IcebergStorage`)
- `tvscreener/lakehouse/write.py` (contains `write_iceberg`)

## Acceptance Criteria

- [ ] `IcebergStorage` class is removed.
- [ ] Logic for writing/managing iceberg storage is relocated to `catalog.py` or a simplified utility module.
- [ ] All calls to storage functions are updated throughout the codebase.
- [ ] Code remains functionally identical, but with a shallower call stack.

## Work Log

### 2026-03-02 - Task Creation

**By:** Antigravity

**Actions:**
- Identified deep indirection in lakehouse storage hierarchy.
- Proposed flattening by merging/removing `IcebergStorage`.
- Created P3 todo.

## Notes

- Nice-to-have architectural cleanup.
