---
status: completed
priority: p2
issue_id: "072"
tags: [strategy, scoring, confluence]
dependencies: []
---

# Add grid confluence to strategy results

## Problem Statement

The strategy scanner uses a simple integer CONFLUENCE_SCORE (1-5) that counts how many strategy conditions passed. The opportunity scanner uses a grid-based TF×Factor confluence (GRID_ALIGNED 0-12, GRID_PCT, GRADE). Users can't compare quality across scanners because the scoring systems are incompatible.

## Findings

- Strategy scanner already has access to underlying opportunity data: `self._screener.get_opportunities()` returns a DataFrame with all TF×Factor columns and grid confluence data (GRID_ALIGNED, GRID_PCT, GRADE, TF_CONFLUENCE, FACTOR_CONFLUENCE)
- The strategy results DataFrame contains the raw TF columns (`Recommend All|240`, etc.) from the opportunity data
- Grid confluence could be calculated from the strategy results' raw columns, or passed through from the underlying opportunity data
- Both CONFLUENCE_SCORE (strategy-specific) and GRID_ALIGNED (cross-scanner) are useful — they measure different things

## Proposed Solutions

### Option 1: Pass through grid confluence from underlying opportunity data (Recommended)

**Approach:** After strategy detection, join back to the opportunity results on PAIR to get GRID_ALIGNED, GRID_PCT, GRADE, TF_CONFLUENCE, FACTOR_CONFLUENCE.

**Pros:**
- Reuses existing scoring (DRY)
- Grid confluence already calculated by opportunity scanner
- No new scoring logic needed

**Cons:**
- Dependency on opportunity scorer running first (already happens)
- Join may fail if PAIR column missing (defensive coding needed)

**Effort:** 1-2 hours

**Risk:** Low

## Acceptance Criteria

- [x] Strategy results include GRID_ALIGNED, GRID_PCT, GRADE, TF_CONFLUENCE, FACTOR_CONFLUENCE
- [x] Strategy-specific CONFLUENCE_SCORE preserved alongside grid confluence
- [x] Summary view shows both scores
- [x] All existing tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Analyzed strategy scanner's data flow: calls `self._screener.get_opportunities()` which returns grid-scored data
- Confirmed grid columns available in raw_data passed to each strategy detector

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Modified `ForexStrategyScanner.scan` to explicitly join back grid confluence columns from `raw_data` on `PAIR`.
- Updated `ForexStrategyScanner.print_summary` to include `Grid` and `Grade` columns in the rich table output.
- Verified both strategy-specific scores and cross-scanner grid scores are displayed.
