---
status: completed
priority: p3
issue_id: "088"
tags: [simplification, DRY]
dependencies: []
---

# Simplification: _scalar helper duplication

Centralize the `_scalar` helper function into `to_scalar` in `tvscreener/util.py`.

## Problem Statement

The `_scalar` helper function, which handles conversion of numpy/pandas scalars to standard Python floats, is duplicated in multiple screener classes. This violates DRY and makes it harder to update the conversion logic if needed.

## Findings

- **Duplicate 1:** `tvscreener/lib/screeners/base.py:147`
- **Duplicate 2:** `tvscreener/lib/screeners/forex_strategy.py:662`
- Both implementations are essentially `float(val)` but some include extra checks for numpy types.

## Proposed Solutions

### Option 1: Move to util.py (Recommended)

**Approach:** Extract the logic into `tvscreener/util.py` and import it where needed.

**Pros:**
- Single source of truth for type conversion
- Reduces boilerplate in screener classes
- Easier to test in isolation

**Cons:**
- None

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Centralize in `tvscreener/util.py` as `to_scalar`.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/base.py`
- `tvscreener/lib/screeners/forex_strategy.py`
- `tvscreener/util.py`

## Acceptance Criteria

- [x] `_scalar` removed from screener classes
- [x] `to_scalar` exists in `util.py`
- [x] All consumers updated to use the centralized version

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Grepped codebase for `def _scalar`
- Found two identical/near-identical definitions

### 2026-03-01 - Implementation

**By:** Antigravity (Claude)

**Actions:**
- Added `to_scalar` to `tvscreener/util.py`.
- Removed `_scalar` from `ExportMixin` in `base.py`.
- Replaced all usages of `_scalar` with `to_scalar` in `forex_opportunity.py` and `forex_strategy.py`.
- Updated all relevant files to import `to_scalar`.

---
