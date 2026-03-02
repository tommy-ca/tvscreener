---
status: complete
priority: p2
issue_id: "063"
tags: [architecture, technical-debt, code-review]
dependencies: []
---

# Problem Statement
The codebase lacks a unified representation for trade direction. The `ScoringEngine` uses `"bullish"`/`"bearish"`/`"neutral"`, while the rest of the pipeline uses `"long"`/`"short"`/`"all"`. This inconsistency leads to frequent internal mapping, boilerplate code, and potential comparison bugs.

# Findings
- **Inconsistency**:
  - `ScoringEngine.calculate_direction`: `bullish/bearish`
  - `ForexStrategyScanner`: `long/short`
  - CLI: `long/short/all`
- **Impact**: Increased mental overhead and risk of logical errors during refactors.

# Proposed Solutions
1. **Unified Direction Enum**: Create a `Direction` enum (e.g., `LONG`, `SHORT`, `NEUTRAL`) and use it throughout the library.
2. **Standardize on one string set**: Pick one and enforce it via typing.

# Recommended Action
Implement a `Direction` Enum and refactor all components to use it.

# Acceptance Criteria
- [x] Single source of truth for direction values.
- [x] No manual string comparisons for "bullish" vs "long" in the same pipeline.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Architecture Strategist)
- Identified inconsistent direction value schemas across modules.

### 2026-02-28 - Implemented
- Refactored `ScoringEngine` to use `Direction` enum.
- Standardized `ForexStrategyScanner` and `ForexOpportunityScreener` on the `Direction` enum.
- Removed manual `.value` access where possible, relying on the enum's string behavior.
