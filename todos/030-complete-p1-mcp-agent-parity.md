---
status: completed
priority: p1
issue_id: "030"
tags: [mcp, agent, cli-parity]
dependencies: []
---

# Add MCP Agent Tools for Opportunity/Strategy Scanners

## Problem Statement

PR #48 adds substantial new CLI functionality (filters, scoring weights, config management, export formats), but NONE of these features are exposed via MCP agent tools. Agents cannot access the opportunity scanner, strategy scanner, or any new CLI arguments. This is a complete action parity failure.

## Findings

- **Location:** `mcp/tools.py` (entire file)
- **Issue:** MCP server only exposes generic stock/crypto/forex screeners - zero parity with CLI's opportunity and strategy modes
- **Missing capabilities (18 total):**
  - Opportunity scanner tool (Added: `scanner_opportunities`)
  - Strategy scanner tool (Added: `scanner_strategies`)
  - --save-config / --load-config tools (Added: `config_save`, `config_load`)
  - Export tools (CSV, JSON, Parquet, XML) (Added to scanner tools via `output` parameter)
  - All filter arguments (--min-volume, --max-atr, --min-ma-rating) (Added as parameters to scanner tools)
  - All scoring weight arguments (Added as parameters to scanner tools)

## Proposed Solutions

### Option 1: Add Dedicated MCP Tools for Each Scanner [SELECTED]

**Approach:** Create new MCP tools: `scan_opportunities`, `scan_strategies`, `save_config`, `load_config`, `export_results`.

**Pros:**
- Full feature parity
- Clear agent interface

**Cons:**
- More code to maintain
- May have overlapping functionality

**Effort:** 4-6 hours

**Risk:** Low

---

### Option 2: Extend Existing Tools with Mode Parameter

**Approach:** Add `mode` parameter to existing tools to switch between generic and opportunity/strategy modes.

**Pros:**
- Less code duplication

**Cons:**
- More complex tool signatures
- Harder to document

**Effort:** 3-4 hours

**Risk:** Medium

---

## Recommended Action

Implemented Option 1 by adding dedicated scanner tools and configuration tools. Added support for all CLI flags as tool parameters.

## Technical Details

**Affected files:**
- `tvscreener/mcp/tools.py` - added implementation logic for new tools
- `tvscreener/mcp/server.py` - registered new tools and added export/config handling
- `tvscreener/cli.py` - existing logic used as reference

## Acceptance Criteria

- [x] Opportunity scanner accessible via MCP
- [x] Strategy scanner accessible via MCP
- [x] Config save/load accessible via MCP
- [x] All export formats accessible via MCP
- [x] All CLI arguments accessible via MCP
- [x] Documentation updated

## Work Log

### 2026-02-25 - Agent-Native Review Discovery

**By:** Claude Code (Agent-Native Reviewer)

**Actions:**
- Mapped all 18 CLI capabilities to agent tools
- Found zero parity between CLI and MCP

**Learnings:**
- This is a systemic issue - future CLI features must include MCP parity

### 2026-02-28 - Implementation and Verification

**By:** Antigravity (Google DeepMind)

**Actions:**
- Created `scanner_opportunities` and `scanner_strategies` tools in `mcp/server.py`
- Added underlying implementation in `mcp/tools.py`
- Added `config_save` and `config_load` tools
- Added support for all CLI filters and scoring weights
- Verified with unit tests in `tests/test_mcp_parity_v2.py`
- Updated README.md with new tools
