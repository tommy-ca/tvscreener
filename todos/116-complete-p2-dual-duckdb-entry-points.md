---
status: complete
priority: p2
issue_id: "116"
tags: [architecture, dead-code, duckdb, code-review]
dependencies: ["105"]
---

# Dual DuckDB Entry Points — DuckDBEngine is Dead Code

## Problem Statement

Two completely independent DuckDB abstractions exist: `DuckDBFilter` (global connection, used everywhere) and `DuckDBEngine` (instance connection, used nowhere in production). `DuckDBEngine` is 42 lines of dead code that creates proper isolated connections but was never wired into the filter pipeline.

## Findings

- `tvscreener/lib/screeners/duckdb_engine.py` — 42 lines, only imported by test
- `tvscreener/lib/screeners/filters.py:36-66` — DuckDBFilter uses global connection
- When issue 105 is resolved (sandboxing DuckDBFilter), DuckDBEngine becomes redundant

## Proposed Solutions

### Option 1: Delete DuckDBEngine After Fixing DuckDBFilter

**Approach:** After issue 105 sandboxes DuckDBFilter, delete `duckdb_engine.py` and its test.

**Effort:** 5 minutes
**Risk:** None

## Recommended Action

**Delete DuckDBEngine after #105 is resolved.** Once DuckDBFilter uses sandboxed connections, `duckdb_engine.py` is fully redundant. Remove it and its test.

## Acceptance Criteria

- [ ] Single canonical DuckDB entry point exists
- [ ] Dead code removed
- [ ] No test regressions

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (architecture-strategist, code-simplicity-reviewer)
