---
status: complete
priority: p3
issue_id: "168"
tags: [ui, refactor, beauty]
dependencies: []
---

# Consolidate Visual Styler Logic

Move all emoji, sign, and formatting logic from screeners to a centralized `VisualStyler` class in `beauty.py`.

## Problem Statement

Emoji and sign logic (e.g., green/red arrows, success/failure icons) is currently scattered across various screener files. This makes it difficult to maintain a consistent visual style and reuse formatting logic.

## Findings

- Screeners often define their own small helpers for adding emojis or coloring output.
- Logic for "positive" vs "negative" visual indicators is duplicated.

## Proposed Solutions

### Option 1: Centralize in VisualStyler

**Approach:** Move all formatting logic to a `VisualStyler` class in `beauty.py`. Use this class across all screeners for UI output.

**Pros:**
- Consistent UI/UX across all screeners.
- Single source of truth for visual indicators.
- Simplifies screener implementations.

**Cons:**
- Requires updating multiple screener files to use the new styler.

**Effort:** 2-3 hours

**Risk:** Low

## Recommended Action

Centralize in `VisualStyler` and provide both scalar and Narwhals expression helpers for consistency.

## Technical Details

**Affected files:**
- `beauty.py`: New or updated `VisualStyler` class.
- Various screener files (e.g., `screeners/*.py`).

## Acceptance Criteria

- [x] `VisualStyler` class in `beauty.py` contains all emoji and sign logic.
- [x] Screeners updated to use `VisualStyler` for visual formatting.
- [x] No visual logic (emojis, color strings) hardcoded in screeners.
- [x] Visual output remains identical or improved in consistency.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created P3 todo for Visual Styler consolidation.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Consolidated all emoji constants and logic in `VisualStyler`.
- Added `get_strength_expression` and `get_strategy_strength_expression` for vectorized Narwhals support.
- Updated `ForexOpportunityScreener` and `ForexStrategyScanner` to use centralized logic.
- Updated `RichConsoleRenderer` to use `VisualStyler` constants and legend.
- Removed duplicated methods from `ExportMixin`.
- Verified with unit tests.

