---
status: complete
priority: p1
issue_id: "152"
tags: [bug, mcp, python]
dependencies: []
---

# Fix Broken MCP Filter Chain

Wire `sql` and `filters` parameters from `scanner_opportunities` to the underlying execution logic.

## Problem Statement

The MCP tool `scanner_opportunities` in `mcp/server.py` defines `sql` and `filters` parameters, but these are currently ignored and not passed to the `scan_opportunities` function (or equivalent execution logic). This prevents users from applying custom SQL or filters when using the MCP tool.

## Findings

- `mcp/server.py`: `scanner_opportunities` signature includes `sql` and `filters`.
- Implementation: These parameters are not used in the function body when calling the scanning logic.

## Proposed Solutions

### Option 1: Wire Parameters Directly

**Approach:** Pass the `sql` and `filters` arguments from `scanner_opportunities` to the internal scanning function.

**Pros:**
- Simple and direct fix.
- Restores intended functionality.

**Cons:**
- None.

**Effort:** 0.5 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/mcp/server.py` - `scanner_opportunities` function.

## Acceptance Criteria

- [ ] `sql` parameter in `scanner_opportunities` is passed to the scanning logic.
- [ ] `filters` parameter in `scanner_opportunities` is passed to the scanning logic.
- [ ] Manual test verifies that providing a `filters` argument via MCP correctly filters the results.
- [ ] Manual test verifies that providing a `sql` argument via MCP correctly executes the custom SQL.

## Work Log

### 2026-03-02 - Initial Entry

**By:** Antigravity

**Actions:**
- Created todo from correctness findings.
- Identified `mcp/server.py` as the target file.

**Learnings:**
- Parameters were defined but not implemented in the tool handler.
