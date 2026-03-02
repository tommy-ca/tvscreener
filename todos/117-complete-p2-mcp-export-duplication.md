---
status: complete
priority: p2
issue_id: "117"
tags: [patterns, mcp, duplication, code-review]
dependencies: ["106"]
---

# MCP Export Logic Duplicates Orchestrator Pipeline

## Problem Statement

`mcp/server.py` contains two identical 12-line export blocks (lines 152-167 and 309-324) that duplicate the proper export pipeline in `ScreenerController._export_results()`. The MCP versions skip metadata embedding and path validation.

## Findings

- `tvscreener/mcp/server.py:152-167` — Inline export in scanner_opportunities
- `tvscreener/mcp/server.py:309-324` — Identical inline export in scanner_strategies
- `tvscreener/lib/orchestrator.py:429-454` — Proper export with validation + metadata
- MCP export produces raw DataFrames without enrichment metadata

## Proposed Solutions

### Option 1: Delegate to ExportMixin/Orchestrator

**Approach:** Have MCP tools call `scanner.export()` or `controller._export_results()`.

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

**Delegate to ExportMixin/Orchestrator.** This is resolved naturally when implementing #106. MCP tools should call `scanner.export()` or `controller._export_results()` instead of inline code.

## Acceptance Criteria

- [ ] Single export code path for all interfaces
- [ ] MCP exports include metadata
- [ ] Path validation applied uniformly
- [ ] ~30 lines of duplicated code removed

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (pattern-recognition-specialist, agent-native-reviewer)
