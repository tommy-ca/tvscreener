---
status: complete
priority: p1
issue_id: "110"
tags: [security, mcp, code-review]
dependencies: []
---

# MCP Path Traversal on Parquet Inspect

## Problem Statement

The `inspect_file()` function in `mcp/tools.py` passes user-provided paths directly to `pd.read_parquet()` and `pq.read_metadata()` without calling `validate_path()`. A malicious MCP client could read any parquet file on the filesystem.

The CLI path (`orchestrator.py:run_inspect_parquet`) correctly validates paths.

## Findings

- `tvscreener/mcp/tools.py:570-584` — `inspect_file()` uses raw path without validation
- `tvscreener/lib/inspect_utils.py:32,56` — `pq.read_metadata(path)` and `pd.read_parquet(path)` with raw input
- `tvscreener/lib/orchestrator.py:398` — CLI correctly calls `self._validate_path(request.output)`

## Proposed Solutions

### Option 1: Add validate_path() to inspect_file()

**Approach:** Call `validate_path(path)` before passing to `inspect_parquet()`.

**Effort:** 5 minutes

**Risk:** None

## Recommended Action

**Add validate_path().** Call `validate_path(path)` in `inspect_file()` before passing to `inspect_parquet()`. Return error message to MCP client on traversal attempts.

## Acceptance Criteria

- [ ] `inspect_file()` validates path before reading
- [ ] Path traversal attempts return error message
- [ ] Tests verify path validation

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (security-sentinel agent)
