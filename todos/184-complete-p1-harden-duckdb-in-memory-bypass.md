---
status: completed
priority: p1
issue_id: "184"
tags: [security, duckdb]
dependencies: []
---

# Harden DuckDB In-Memory Bypass

## Problem Statement

Security risk: In `EdgeQueryClient`, if `db_path == ":memory:"`, DuckDB does not enforce `lock_configuration=True`. This allows arbitrary file reads (`read_csv`) or remote extension loading.

## Findings

- `EdgeQueryClient` conditionally applies security configurations.
- When `db_path == ":memory:"`, DuckDB is initialized without `lock_configuration=True` and `enable_external_access=False`.
- This bypass creates a vulnerability allowing unauthorized file reads and remote extension execution via memory instances.

## Proposed Solutions

### Option 1: Enforce Security Configurations Universally

**Approach:** Enforce `lock_configuration=True` and `enable_external_access=False` universally, regardless of the persistence mode (`:memory:` or otherwise).

**Pros:**
- Closes the security loophole completely.
- Simplifies configuration logic and prevents accidental bypasses.

**Cons:**
- Might require test modifications if any tests relied on external access during `:memory:` database testing.

**Effort:** 1 hour

**Risk:** Low

## Recommended Action

Update `EdgeQueryClient` DuckDB initialization to universally enforce security restrictions (`lock_configuration=True` and `enable_external_access=False`).

## Technical Details

**Affected files/components:**
- `EdgeQueryClient` initialization logic
- DuckDB connection parameters

## Acceptance Criteria

- [x] `EdgeQueryClient` enforces `lock_configuration=True` and `enable_external_access=False` for `:memory:` database paths.
- [x] Attempting to load remote extensions or read arbitrary files in an in-memory database fails with appropriate errors.
- [x] All existing functionality utilizing in-memory databases continues to work as expected without requiring external access.
- [x] Run `uv run pytest` to ensure all tests pass and security constraints are verified.

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Opencode

**Actions:**
- Created P1 todo based on DuckDB in-memory security bypass finding.
- Documented fix requirement for `lock_configuration` and `enable_external_access`.

### 2026-03-03 - Implementation and Verification

**By:** Opencode (Expert Code Review Resolution Specialist)

**Actions:**
- Hardened `EdgeQueryClient` by universally enforcing `lock_configuration=True` and `enable_external_access=False`.
- Updated `get_relation()` to use `pyarrow.parquet.read_table()` for local Parquet files, bypassing DuckDB's restricted file system access while maintaining security through `validate_path()`.
- Disabled remote extension loading by raising `RuntimeError` in `_setup_remote_access`.
- Verified fixes with `tests/security/test_sql_injection.py` and `tests/test_analytics_pipeline.py`.

## Notes

- This is a critical security vulnerability and should be prioritized immediately.
- The use of PyArrow for local file reading provides better control over file access and enables hardening of the DuckDB instance.
