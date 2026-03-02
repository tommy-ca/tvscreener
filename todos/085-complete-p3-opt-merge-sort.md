---
status: completed
priority: p3
issue_id: "085"
tags: [performance, pandas]
dependencies: []
---

# Optimization: Duplicate merging sorting efficiency

Use multi-column sort_values instead of zip tuples in _merge_duplicates.

## Problem Statement

In `_merge_duplicates`, we currently use a `zip` of columns to create a `_priority` tuple-like column, which is then used for sorting. This is less efficient than using pandas' built-in multi-column sorting capabilities and can be slow for large DataFrames because it involves Python-level iteration and list creation.

## Findings

- **File:** `tvscreener/lib/screeners/forex_opportunity.py` (lines 231-233)
- **Current implementation:**
  ```python
  df["_priority"] = list(
      zip(df["_is_canonical"], df["_exchange_score"], -df["_volume"], strict=False)
  )
  df = df.sort_values(by="_priority")
  ```
- This approach forces pandas to use Python objects for sorting instead of optimized C/vectorized operations.

## Proposed Solutions

### Option 1: Multi-column sort_values (Recommended)

**Approach:** Use `df.sort_values` with a list of columns and corresponding `ascending` flags.

**Pros:**
- Vectorized sorting (significantly faster for large DataFrames)
- More readable and idiomatic pandas code
- Avoids creating an intermediate temporary column

**Cons:**
- None identified

**Effort:** < 15 minutes

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_opportunity.py:231`

## Acceptance Criteria

- [ ] `zip` and `_priority` column creation removed
- [ ] `sort_values` uses multiple columns (`_is_canonical`, `_exchange_score`, `_volume`)
- [ ] Correct `ascending` flags used (Volume should be descending)
- [ ] Unit tests for `_merge_duplicates` still pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Identified inefficient sorting pattern in `forex_opportunity.py`
- Benchmarked (conceptually) against multi-column sort_values

---
