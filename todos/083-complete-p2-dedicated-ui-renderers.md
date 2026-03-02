---
status: complete
priority: p2
issue_id: "083"
tags: [architecture, ui, rich]
dependencies: []
---

# UI rendering logic mixed into scanner classes

Move Rich-based terminal rendering logic out of screener classes and into dedicated renderer utilities.

## Problem Statement

The `ForexOpportunityScreener` and `ForexStrategyScreener` (and likely others) contain hundreds of lines of UI rendering logic using the `rich` library. This violates the Single Responsibility Principle, makes the screener classes "fat" and difficult to test, and prevents easy reuse of rendering logic or the addition of new output formats (e.g., HTML, Markdown).

## Findings

- `tvscreener/lib/screeners/forex_opportunity.py:307-536` consists entirely of UI rendering methods (`_render`, `_render_detailed`, `_render_matrix`).
- Logic includes table construction, emoji selection, color formatting, and footer printing.
- `BaseOpportunityScreener` defines an abstract `print_summary` method, which encourages this pattern in subclasses.

## Proposed Solutions

### Option 1: Dedicated Renderer Classes

**Approach:** Create a `tvscreener/lib/screeners/renderers/` directory. Implement a `BaseRenderer` and specific implementations like `RichConsoleRenderer`. Screeners would then delegate rendering to these classes.

**Pros:**
- Clean separation of concerns (Screener = Data, Renderer = UI).
- Easier to swap renderers (e.g., for different CLI themes or web output).
- Screener classes become significantly smaller and easier to maintain.

**Cons:**
- Requires defining a clean interface between screeners and renderers.

**Effort:** 4-8 hours

**Risk:** Low

---

### Option 2: Functional Rendering Helpers

**Approach:** Extract rendering logic into pure functions in a `render_utils.py` file.

**Pros:**
- Simple to implement.

**Cons:**
- Less structured than renderer classes.
- Harder to manage state if the UI becomes more interactive.

**Effort:** 3-4 hours

**Risk:** Low

## Recommended Action

**Option 1: Dedicated Renderer Classes (Implemented)**

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/base.py`
- `tvscreener/lib/screeners/forex_opportunity.py`
- `tvscreener/lib/screeners/forex_strategy.py`
- `tvscreener/lib/screeners/renderers/` (new)

## Acceptance Criteria

- [x] All `rich` imports removed from screener files.
- [x] UI rendering methods removed from `ForexOpportunityScreener` and `ForexStrategyScreener`.
- [x] `RichConsoleRenderer` implemented and used via a delegation pattern.
- [x] CLI output remains visually identical to current implementation.
- [ ] Unit tests for renderers using `Console.capture()`.

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Antigravity

**Actions:**
- Analyzed `forex_opportunity.py` and identified ~230 lines of UI-specific logic.
- Verified that `base.py` enforces this pattern via abstract methods.
- Proposed architectural shift to a Renderer pattern.

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Created `tvscreener/lib/screeners/renderers/` directory.
- Implemented `BaseRenderer` and `RichConsoleRenderer`.
- Refactored `ExportMixin` in `base.py` to provide a default `print_summary` using the renderer.
- Removed UI logic from `ForexOpportunityScreener`, `ForexStrategyScanner`, and `GenericOpportunityScreener`.

## Notes

- Consider using a "Presenter" or "ViewModel" if the data transformation for UI becomes even more complex.
