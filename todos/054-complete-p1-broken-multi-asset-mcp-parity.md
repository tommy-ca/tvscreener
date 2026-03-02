---
status: completed
priority: p1
issue_id: "054"
tags: [mcp, agent, bug, code-review]
dependencies: []
---

# Problem Statement
The MCP tools `scanner_opportunities` and `scanner_strategies` advertised support for multiple asset types (Stocks, Crypto, Commodities), but the underlying implementation was hardcoded to always use Forex scanners.

# Findings
- **File**: `tvscreener/mcp/tools.py`
- **Evidence**: Hardcoded `ForexOpportunityScreener` and `ForexStrategyScanner` calls.

# Solutions Implemented
1. **Implemented `BaseOpportunityScreener`**: Created a unified abstract base class in `tvscreener/lib/screeners/base.py` that handles generic multi-timeframe data fetching and scoring.
2. **Created `AssetScreenerFactory`**: Implemented a factory in `tvscreener/lib/screeners/factory.py` to route to the correct screener implementation based on `asset_type`.
3. **Refactored Forex Implementation**: Updated `ForexOpportunityScreener` to inherit from `BaseOpportunityScreener`.
4. **Generalized MCP Tools**: Updated `scan_opportunities` and `scan_strategies` in `mcp/tools.py` and the `ScreenerController` in `orchestrator.py` to use the unified factory.

# Acceptance Criteria
- [x] `scanner_opportunities(asset_type="stocks")` returns stock results.
- [x] `scanner_strategies` supports multiple asset types.
- [x] Clear error message if an unsupported asset type is requested.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Agent-Native Reviewer)
- Identified broken multi-asset promise in MCP layer.

### 2026-02-28 - Resolution
**By:** Claude Code
- Implemented `BaseOpportunityScreener` and `AssetScreenerFactory`.
- Refactored `ForexOpportunityScreener` and `ForexStrategyScanner`.
- Updated MCP layer to route requests to appropriate asset screeners.
- Verified Stock and Crypto scans work via MCP-bound tools.
