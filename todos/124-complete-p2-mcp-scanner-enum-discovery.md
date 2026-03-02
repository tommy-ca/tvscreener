---
status: complete
priority: p2
issue_id: "124"
tags: [agent-native, mcp, code-review]
dependencies: []
---

# No MCP Tool for Scanner Enum Discovery

## Problem Statement

The MCP server has no tool for listing valid scanner enums (strategies, universes, directions, contract types, asset types, confluence grades). Agents must guess values or hard-code them. The CLI has implicit discoverability via `--help` choices, but agents don't see argparse help.

## Findings

- MCP has `list_sectors`, `list_filter_operators` for generic tools
- No equivalent for scanner domain: strategies, universes, directions, contract_types, asset_types, grades, timeframes
- If enums change (new strategy type added), agents fail silently

## Proposed Solutions

### Option 1: Add list_scanner_options Tool

**Approach:** Create MCP tool returning JSON of all valid enum values.

**Effort:** 15 minutes
**Risk:** None

## Recommended Action

**Add `list_scanner_options` MCP tool.** Return JSON with all valid enum values (strategies, universes, directions, contract_types, asset_types, grades, timeframes).

## Acceptance Criteria

- [ ] Agents can discover all valid enum values programmatically
- [ ] Tool returns structured JSON

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (agent-native-reviewer)
