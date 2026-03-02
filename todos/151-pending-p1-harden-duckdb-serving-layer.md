---
status: pending
priority: p1
issue_id: "151"
tags: [security, duckdb, python]
dependencies: []
---

# Harden DuckDB Serving Layer

Ensure DuckDB connections are read-only and configurations are locked to prevent unauthorized file writes or configuration changes.

## Problem Statement

DuckDB connections are currently read-write by default. This allows users with query access to potentially write arbitrary files to the local filesystem or change critical database configurations (like loading unauthorized extensions).

## Findings

- DuckDB connections are not explicitly initialized in read-only mode for user-facing queries.
- Extension loading and configuration changes are not restricted during user query execution.

## Proposed Solutions

### Option 1: Read-Only Mode and Configuration Locking

**Approach:** 
1. Initialize the DuckDB connection with `read_only=True`.
2. Immediately execute `SET lock_configuration=true;` on the connection to prevent any further changes to the database configuration or extension loading.

**Pros:**
- Significantly reduces the attack surface.
- Prevents arbitrary file writes (e.g., via `COPY ... TO ...`).
- Blocks loading of potentially malicious extensions.

**Cons:**
- Prevents legitimate write operations if they were intended (though for serving/querying, read-only is usually preferred).

**Effort:** 1 hour

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `query.py` or wherever the DuckDB connection is initialized for edge queries.

## Acceptance Criteria

- [ ] DuckDB connections used for edge queries are initialized with `read_only=True`.
- [ ] `SET lock_configuration=true;` is executed before any user query runs.
- [ ] Attempting to write a file via SQL results in an error.
- [ ] Attempting to load an extension via SQL results in an error.

## Work Log

### 2026-03-02 - Initial Entry

**By:** Antigravity

**Actions:**
- Created todo from security findings.
- Identified need for read-only mode and configuration locking.

**Learnings:**
- DuckDB's default behavior is permissive; hardening is essential for serving layers.
