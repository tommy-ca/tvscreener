---
status: complete
priority: p1
issue_id: "069"
tags: [strategy, display, matrix-view]
dependencies: []
---

# Add --matrix view to strategy scanner

## Problem Statement

The strategy scanner lacks a `--matrix` view. The opportunity scanner has a compact TF×Factor emoji grid (single emojis per cell) that provides at-a-glance confluence visibility. The strategy scanner should have the same view, grouped by strategy type.

## Findings

- The opportunity scanner's `_render_matrix()` (forex_opportunity.py:397-458) renders a compact table with single emoji cells
- The strategy scanner's underlying data contains all the TF×Factor columns (from `self._screener.get_opportunities()`)
- Matrix view uses `_matrix_sign()` for single emojis (prevents column truncation)
- Strategy results need grouping by strategy type (unlike opportunity which shows all pairs in one table)

## Proposed Solutions

### Option 1: Add _render_matrix() to ForexStrategyScanner (Recommended)

**Approach:** Add a `_render_matrix()` method showing a compact emoji grid per strategy group. Each group gets its own table (matching current summary grouping).

**Pros:**
- Consistent with opportunity scanner's matrix view
- Strategy grouping preserved
- Quick visual scan of TF×Factor alignment

**Cons:**
- Multiple small tables may be harder to scan than one big one

**Effort:** 1-2 hours

**Risk:** Low

## Recommended Action

Implement Option 1. Add `_render_matrix()` to `ForexStrategyScanner`. Use the `_matrix_sign()` helper (from todo 071, or copy locally for now).

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_strategy.py` — add `_render_matrix()`
- Pattern: `tvscreener/lib/screeners/forex_opportunity.py:397-458`

## Acceptance Criteria

- [x] `uv run python -m tvscreener.cli -s strategy -u majors --matrix` shows TF×Factor emoji grid
- [x] Each cell is a single emoji (🟢/🔴/⚪)
- [x] Pairs grouped by strategy type
- [x] Grid, Grade columns shown alongside emoji grid
- [x] Legend footer displayed
- [x] All existing tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Identified missing matrix view in strategy scanner
- Documented reference pattern from opportunity scanner

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Implemented `_render_matrix()` in `ForexStrategyScanner`.
- Updated `print_summary()` to support `matrix=True`.
- Fixed bug where `itertuples()` was used instead of `iterrows()`, preventing access to columns with special characters.
- Verified implementation with `uv run python -m tvscreener.cli -s strategy -u majors --matrix`.
