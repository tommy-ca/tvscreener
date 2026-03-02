---
status: complete
priority: p2
issue_id: "090"
tags: [refactor, ui, dry]
dependencies: []
---

# Consolidate RichConsoleRenderer Matrix and Emoji logic

Consolidate duplicated matrix rendering logic and centralize emoji/sign logic.

## Problem Statement

Significant code duplication exists in `RichConsoleRenderer` (~90% identical matrix logic). Specifically, `_render_opportunity_matrix` and `_render_strategy_matrix` are nearly identical. Furthermore, emoji/sign logic is scattered across 3 different files, making maintenance difficult.

## Findings

- `_render_opportunity_matrix` and `_render_strategy_matrix` in `RichConsoleRenderer` share approximately 90% of their logic.
- Emoji and sign logic is scattered across 3 separate files.
- Refactoring can reduce the codebase by approximately 100-150 lines while maintaining identical visual output.

## Proposed Solutions

### Option 1: Extract generic logic and centralize signs

**Approach:** 
1. Extract the shared matrix rendering logic into a generic private method `_render_confluence_matrix` within `RichConsoleRenderer`.
2. Centralize all emoji and sign logic into `VisualStyler`.

**Pros:**
- Eliminates ~90% duplication in matrix rendering.
- Centralizes UI visual elements in one place (`VisualStyler`).
- Significant code reduction (~100-150 lines).

**Cons:**
- Requires careful testing to ensure visual output remains identical.

**Effort:** 3-4 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.** 
Implement Option 1: Extract `_render_confluence_matrix` and move sign logic to `VisualStyler`.

## Technical Details

**Affected files:**
- `RichConsoleRenderer` (likely in `src/tvscreener/renderers/rich_console.py` or similar)
- `VisualStyler` (likely in `src/tvscreener/styles/visual.py` or similar)

## Acceptance Criteria

- [ ] Generic `_render_confluence_matrix` extracted.
- [ ] Sign/Emoji logic centralized in `VisualStyler`.
- [ ] Code reduced by 100-150 lines.
- [ ] Visual output remains identical to current implementation.
- [ ] All tests pass.

## Work Log

### 2026-03-01 - Todo Creation

**By:** opencode

**Actions:**
- Created initial todo file for consolidating RichConsoleRenderer logic.
- Identified problem areas (duplicated matrix logic, scattered emoji logic).
- Proposed consolidation into `_render_confluence_matrix` and `VisualStyler`.

**Learnings:**
- Duplication is high (~90%) in matrix rendering.
- Visual output must remain consistent after refactor.

## Notes

- Aim for identical visual output.
- Target code reduction: 100-150 lines.
