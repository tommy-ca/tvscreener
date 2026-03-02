---
status: complete
priority: p2
issue_id: "061"
tags: [mcp, agent, code-review]
dependencies: ["030"]
---

# Problem Statement
The `scanner_strategies` MCP tool is missing parameters for scoring weights (e.g., `trend_weight`, `ma_weight`) and timeframe weights, which are present in the `scanner_opportunities` tool. This prevents agents from fine-tuning strategy detection results based on user preferences.

# Findings
- **File**: `tvscreener/mcp/server.py` and `mcp/tools.py`
- **Gap**: `scanner_strategies` tool signature lacks weighting parameters.

# Proposed Solutions
1. **Harmonize Parameters**: Update the tool signature to include the full set of scoring and timeframe weights.
2. **Config Pass-through**: Ensure `StrategyConfig` supports these overrides.

# Recommended Action
Update the `scanner_strategies` MCP tool to match the configuration flexibility of the opportunity scanner.

# Acceptance Criteria
- [x] Agents can pass weights to the strategy scanner tool.
- [x] Tool signature is consistent across all scanner tools.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Agent-Native Reviewer)
- Identified configuration inflexibility in strategy MCP tools.

### 2026-02-28 - Implemented
- Updated `scan_strategies` in `tvscreener/mcp/tools.py` to include weighting parameters and RSI thresholds.
- Updated `ScanRequest` in `tvscreener/lib/orchestrator.py` to support these parameters.
- Updated `tvscreener/mcp/server.py` to expose these parameters in the `scan_strategies` tool definition.
- Harmonized tool signatures between opportunity and strategy scanners.
