---
status: complete
priority: p2
issue_id: "050"
tags: [architecture, dry, code-review]
dependencies: []
---

# Problem Statement
Filtering logic is fragmented across two paradigms. `ForexOpportunityScreener` uses an OOP approach with `VolumeFilter` and `RatingFilter` classes, while `ForexStrategyScanner` bypasses these entirely and uses independent functions in `filter_utils.py`. This leads to duplication and inconsistent behavior between scanners.

# Findings
- **Files:** `forex_opportunity.py`, `forex_strategy.py`, `filter_utils.py`

# Proposed Solutions
1. **Unify Filter Config**: Make `ForexStrategyScanner` use the same filter classes/config as the opportunity screener.
2. **Functional Unification**: Move all logic to `filter_utils.py` and have both screeners call them.

# Recommended Action
Unify the filtering interface so all scanners handle volume and rating filters consistently.

# Acceptance Criteria
- [x] No duplicated filtering logic between scanners.
- [x] Consistent filter configuration across all Forex scan types.
- [x] Data enrichment logic is unified in `filter_utils.py`.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified architectural fragmentation in filtering logic.

### 2026-02-28 - Implemented
- Moved `apply_contract_type_filter` to `filter_utils.py`.
- Unified data enrichment in `enrich_screener_data` in `filter_utils.py`.
- Refactored both `ForexOpportunityScreener` and `ForexStrategyScanner` to use these shared utilities.
- Ensured `ForexStrategyScanner` uses the same underlying `AssetScreenerFactory` as the opportunity scanner.
