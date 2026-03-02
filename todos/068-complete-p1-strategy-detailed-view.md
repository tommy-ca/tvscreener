---
status: completed
priority: p1
issue_id: "068"
tags: [strategy, display, detailed-view]
dependencies: []
---

# Add --detailed view to strategy scanner

## Problem Statement

The strategy scanner only has a summary view. When using `--detailed`, the orchestrator doesn't pass the flag to the strategy scanner, so users see the same summary output. The opportunity scanner has a rich detailed view showing per-pair TF×Factor grids with `value emoji` cells — the strategy scanner needs the same.

## Findings

- `ForexStrategyScanner.print_summary()` accepts only `limit: int` — no `detailed` or `matrix` kwargs
- `ScreenerController.run_strategy_scan()` (orchestrator.py:314) calls `scanner.print_summary()` without passing `request.detailed` or `request.matrix`
- The strategy scanner has access to underlying opportunity data via `self._screener.get_opportunities()` which contains all the TF×Factor columns needed
- The opportunity scanner's `_render_detailed()` (forex_opportunity.py:346-395) is the pattern to replicate

## Proposed Solutions

### Option 1: Add _render_detailed() to ForexStrategyScanner (Recommended)

**Approach:** Add a `_render_detailed()` method to `ForexStrategyScanner` that shows per-pair TF×Factor grids. Group by strategy type (matching current summary behavior). Include strategy-specific fields (strategy name, confluence pattern) in the header.

**Pros:**
- Mirrors opportunity scanner's detailed view
- Strategy-specific context preserved in header
- Minimal changes to existing code

**Cons:**
- Duplicates rendering logic (addressed by todo 071)

**Effort:** 1-2 hours

**Risk:** Low

## Recommended Action

Implement Option 1. Add `_render_detailed()` to `ForexStrategyScanner`. Update `print_summary()` to accept `detailed` and `matrix` kwargs. Wire the orchestrator to pass these through.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_strategy.py` — add `_render_detailed()`, update `print_summary()` signature
- `tvscreener/lib/orchestrator.py:314` — pass `detailed` and `matrix` to strategy scanner

**Pattern to follow:**
- `tvscreener/lib/screeners/forex_opportunity.py:346-395` — `_render_detailed()` reference implementation

## Acceptance Criteria

- [x] `uv run python -m tvscreener.cli -s strategy -u majors --detailed` shows per-pair TF×Factor grids
- [x] Each pair shows TF rows with TREND/MA/OSC/ROC columns and `value emoji` cells
- [x] Pairs are grouped by strategy type
- [x] Strategy name and confluence score shown in pair header
- [x] All existing tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Audited strategy scanner output across all views
- Identified missing `--detailed` view
- Documented pattern from opportunity scanner's `_render_detailed()`

**Learnings:**
- Strategy scanner has access to all TF×Factor data through underlying opportunity screener
- `print_summary()` signature mismatch is the root cause (also tracked in 070)

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Implemented `_render_detailed()` in `ForexStrategyScanner`.
- Updated `print_summary()` to support `detailed` and `matrix` flags.
- Verified output with `uv run python -m tvscreener.cli -s strategy -u majors --detailed`.
- Fixed `ModuleNotFoundError` for `rich.group` by importing from `rich.console`.
