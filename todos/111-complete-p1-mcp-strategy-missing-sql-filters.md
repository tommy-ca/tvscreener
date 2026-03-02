---
status: complete
priority: p1
issue_id: "111"
tags: [agent-native, mcp, parity, code-review]
dependencies: []
---

# MCP scanner_strategies Missing sql and filters Parameters

## Problem Statement

The MCP `scanner_strategies` tool does not expose `sql` or `filters` parameters, even though the underlying `scan_strategies()` helper already accepts them and the CLI `--sql`/`--filter` flags work for strategy scans. This is the most powerful analytical capability and agents cannot use it.

## Findings

- `tvscreener/mcp/server.py:174-328` — `scanner_strategies()` signature lacks `sql` and `filters`
- `tvscreener/mcp/tools.py:472-473` — `scan_strategies()` helper already accepts `sql` and `filters`
- `tvscreener/mcp/tools.py:525-526` — Helper wires them into ScanRequest
- `tvscreener/mcp/server.py:74` — `scanner_opportunities` correctly exposes both params
- 4-line fix: add params to signature + pass through

## Proposed Solutions

### Option 1: Add Parameters (Trivial Fix)

**Approach:** Add `sql: str | None = None` and `filters: list[str] | None = None` to `scanner_strategies()` signature and pass through.

**Effort:** 5 minutes

**Risk:** None

## Recommended Action

**Add parameters.** Add `sql: str | None = None` and `filters: list[str] | None = None` to `scanner_strategies()` signature and pass through to `scan_strategies()` helper. Trivial 4-line fix.

## Acceptance Criteria

- [ ] `scanner_strategies` accepts `sql` parameter
- [ ] `scanner_strategies` accepts `filters` parameter
- [ ] Agent can apply MTF expressions to strategy scans
- [ ] Agent can apply raw SQL to strategy scans

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (agent-native-reviewer)
