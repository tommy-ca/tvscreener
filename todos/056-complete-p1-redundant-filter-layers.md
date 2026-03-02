---
status: completed
priority: p1
issue_id: "056"
tags: [architecture, logic, code-review]
dependencies: []
---

# Problem Statement
Filtering logic is fragmented across multiple layers of the application, leading to redundant passes over the same data and confusing exclusion behavior. Filters are applied in `ForexOpportunityScreener`, then again in `ForexStrategyScanner`, and potentially once more in the CLI.

# Findings
- **Redundancy**:
  1. `ForexOpportunityScreener` filters by Rating/ROC.
  2. `ForexStrategyScanner` re-filters by Volume, ATR, and Rating after concatenating results.
  3. `cli.py` filters by Confluence Grade at the very end.
- **Impact**: Inefficient processing and difficulty debugging why a pair was dropped.

# Proposed Solutions
1. **Upstream Filtering**: Move all shared filters (Volume, ATR) to the very beginning of the pipeline (before strategies are evaluated).
2. **Unified Filter Pipeline**: Define a single `filter_pipeline` that both scanners use consistently.

# Recommended Action
Apply shared filters (Volume/ATR) to the raw data *before* passing it to strategy detection methods. This reduces the size of data processed in specialized loops.

# Acceptance Criteria
- [x] Volume/ATR filters are applied once per scan.
- [x] Consistent results between individual strategy scans and unified scans.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Pattern Recognition Specialist)
- Identified fragmented and redundant filtering layers.

### 2026-02-28 - Resolved
**By:** Antigravity
- Added `AtrFilter` to `tvscreener/filter.py`.
- Updated `ForexOpportunityScreener` to support unified Volume, ATR, and Rating filtering using shared utils.
- Updated `ForexStrategyScanner` to pass Volume/ATR filters upstream to `ForexOpportunityScreener`.
- Removed redundant filter applications in `ForexStrategyScanner.scan()`.
- Updated `ScreenerController` in `tvscreener/lib/orchestrator.py` to handle `AtrFilter`.
