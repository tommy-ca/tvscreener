---
status: complete
priority: p1
issue_id: "106"
tags: [security, mcp, code-review]
dependencies: []
---

# MCP Server Arbitrary File Write Without Path Validation

## Problem Statement

The MCP tools `scanner_opportunities` and `scanner_strategies` in `server.py` accept an `output` parameter and write directly to disk using `df.to_csv(output)`, `df.to_parquet(output)`, etc. **without calling `validate_path()`**. The CLI path correctly validates paths via `ScreenerController._export_results()`, but the MCP tools bypass this entirely.

## Findings

- `tvscreener/mcp/server.py:152-167` — `scanner_opportunities` writes to arbitrary paths
- `tvscreener/mcp/server.py:309-324` — `scanner_strategies` has identical unvalidated writes
- Both blocks are copy-pasted inline export logic, not using the `ExportMixin` pipeline
- `orchestrator.py:432` correctly calls `self._validate_path(output)` before writing
- A malicious MCP client can write to paths like `../../etc/cron.d/evil.csv`

## Proposed Solutions

### Option 1: Add validate_path() to MCP Export (Quick Fix)

**Approach:** Add `validate_path()` call before file writes in both MCP tools.

**Pros:**
- Minimal change (4 lines per tool)
- Consistent with CLI security model

**Cons:**
- Still duplicates export logic from orchestrator

**Effort:** 15 minutes

**Risk:** Low

---

### Option 2: Delegate to Orchestrator Export Pipeline (Better)

**Approach:** Remove inline export code from MCP tools. Instead, call `scanner.export()` from `ExportMixin` or `controller._export_results()`, which already validates paths and embeds metadata.

**Pros:**
- Single export code path for all interfaces
- Gets metadata embedding for free
- Eliminates 30 lines of duplicated code

**Cons:**
- Slightly more refactoring

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

**Option 2 — Refactor to ExportMixin.** Remove inline export code from both MCP tools. Delegate to `ExportMixin._export_results()` or `controller._export_results()` which already validates paths and embeds metadata. Eliminates ~30 lines of duplicated code.

## Technical Details

**Affected files:**
- `tvscreener/mcp/server.py:152-167` — scanner_opportunities export block
- `tvscreener/mcp/server.py:309-324` — scanner_strategies export block

## Resources

- **PR:** #49

## Acceptance Criteria

- [ ] All MCP file writes go through `validate_path()` 
- [ ] Path traversal attempts return error message to MCP client
- [ ] Export produces same output as CLI (with metadata)
- [ ] Tests verify path validation on MCP export paths

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (security-sentinel agent)

**Actions:**
- Identified missing path validation in MCP export blocks
- Confirmed CLI path correctly validates via orchestrator
- Found duplicated export logic (DRY violation + security gap)

**Learnings:**
- MCP tools were implemented as a separate code path from the CLI, bypassing the security layer
