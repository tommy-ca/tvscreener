---
status: complete
priority: p3
issue_id: "092"
tags: [architecture, refactor]
dependencies: []
---

# Implement Renderer Registry

Use registration pattern for Console Renderers to avoid brittle class name checks.

## Problem Statement

The `RichConsoleRenderer.render` method currently uses brittle class name checks to determine which renderer to use for a given object. This makes the system hard to extend and violates the Open/Closed Principle.

## Findings

- `RichConsoleRenderer.render` contained a series of `if/else` or `case` statements checking `object.class.name`.
- Adding support for new asset types or data structures required modifying the core renderer.
- Logic was tightly coupled to specific classes.

## Implementation Summary

### Registry Pattern

**Approach:** Implemented a registration pattern within `RichConsoleRenderer` where screeners or other modules can register their preferred rendering method or a separate renderer class.

**Benefits:**
- Decouples `RichConsoleRenderer` from specific asset types.
- Follows Open/Closed Principle (new renderers can be added without modifying existing code).
- Screeners can now define their own rendering logic while still using the `print_summary` convenience method.

### Acceptance Criteria

- [x] Registration pattern implemented in `RichConsoleRenderer`.
- [x] Existing screeners (`ForexOpportunityScreener`, `ForexStrategyScanner`) updated to register their rendering methods.
- [x] `RichConsoleRenderer.render` updated to use the registry.
- [x] All existing rendering functionality preserved (verified by unit tests).

## Work Log

### 2026-03-01 - Implementation

**By:** opencode

**Actions:**
- Added `_registry` and `register` method to `RichConsoleRenderer`.
- Refactored `RichConsoleRenderer.render` to use the registry with fallback to generic rendering.
- Updated `ForexOpportunityScreener` and `ForexStrategyScanner` to register themselves upon module import.
- Updated unit tests in `tests/unit/test_renderers.py` to match new architecture and verify the registry functionality.
- Verified all tests pass.

## Notes

- This refactor successfully decouples the console rendering from specific screener classes.
- Future screeners only need to call `RichConsoleRenderer.register` to define their terminal output style.
