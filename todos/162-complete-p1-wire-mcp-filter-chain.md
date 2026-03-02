---
status: complete
priority: p1
issue_id: "162"
tags: [correctness, mcp, filtering]
dependencies: []
---

# Fix Broken MCP Filter Chain

## Problem Statement

The MCP server's `scanner_opportunities` tool accepts `sql` and `filters` parameters, but these are currently ignored and not passed to the underlying execution logic in `scan_opportunities`. This prevents users from applying custom filters or SQL overrides through the MCP interface.

## Findings

- `mcp/server.py`: `scanner_opportunities` function receives parameters but doesn't forward them.
- `scan_opportunities`: The core execution logic likely supports these parameters but they aren't reaching it.

## Proposed Solutions

### Option 1: Wire Parameters Directly

**Approach:** Update the `scanner_opportunities` wrapper in `mcp/server.py` to pass the `sql` and `filters` arguments to the `scan_opportunities` call.

**Pros:**
- Direct and simple fix.

**Cons:**
- None.

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `mcp/server.py` - `scanner_opportunities` tool implementation.

## Acceptance Criteria

- [x] `sql` parameter passed from MCP tool is used in the scan.
- [x] `filters` parameter passed from MCP tool is applied to the scan.
- [x] Integration test verifies that filters actually restrict results via `uv run tvscreener-mcp`.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo based on finding in MCP server implementation.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Updated `mcp/server.py` to forward `sql` and `filters`.
- Fixed `mcp/tools.py` to use nested `ScanRequest` structure.
- Fixed `orchestrator.py` to actually apply `sql` and `filters` in `get_*_results`.
- Updated `query.py` to support DataFrames in `query_sql`.
- Verified with unit and integration tests.
