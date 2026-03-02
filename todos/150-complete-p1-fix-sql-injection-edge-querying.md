---
status: complete
priority: p1
issue_id: "150"
tags: [security, duckdb, python]
dependencies: []
---

# Fix SQL Injection in Edge Querying

Use parameterized queries or DuckDB native methods to prevent SQL injection in edge querying logic.

## Problem Statement

The `query.py` module currently uses f-strings to construct SQL queries for `inspect --output` and S3 credential settings. This pattern is vulnerable to SQL injection if user-provided input is not properly sanitized or escaped.

## Findings

- `query.py`: f-strings are used to build SQL strings for output inspection and S3 configuration.
- Risk: Malicious input could escape the intended SQL structure and execute arbitrary commands or access unauthorized data within the DuckDB environment.

## Proposed Solutions

### Option 1: Parameterized Queries

**Approach:** Use DuckDB's parameterized query support (e.g., `execute("SELECT ... WHERE col = ?", (val,))`) for all dynamic SQL generation.

**Pros:**
- Industry standard for preventing SQL injection.
- Clean and readable code.

**Cons:**
- May require refactoring some complex query builders.

**Effort:** 1-2 hours

**Risk:** Low

---

### Option 2: DuckDB Native `.sql()` Method

**Approach:** Use DuckDB's native Python API methods like `.sql()` which handle some level of escaping or structural validation.

**Pros:**
- Leverages DuckDB-specific optimizations.

**Cons:**
- Less universal than standard parameterization.

**Effort:** 1-2 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `query.py` - Look for f-string SQL construction.

## Acceptance Criteria

- [ ] All f-string SQL construction in `query.py` is replaced with parameterized queries.
- [ ] S3 credential handling is secured against injection.
- [ ] `inspect --output` logic uses parameterized paths and options.
- [ ] Unit tests verify that malicious SQL input is correctly handled/escaped.

## Work Log

### 2026-03-02 - Initial Entry

**By:** Antigravity

**Actions:**
- Created todo from security findings.
- Identified `query.py` as the primary target.

**Learnings:**
- f-strings in SQL are a critical security risk.
