---
status: complete
priority: p2
issue_id: "080"
tags: [performance, pandas, risk-management]
dependencies: []
---

# Row-by-row risk management using .apply()

Optimize risk management calculations by moving from row-by-row `.apply()` to vectorized Pandas operations.

## Problem Statement

The risk management calculation in the base screener class uses `df.apply(axis=1)`, which is a known performance bottleneck in Pandas. For large dataframes (e.g., scanning hundreds of symbols), this row-by-row iteration significantly slows down the final ranking and processing phase.

## Findings

- `tvscreener/lib/screeners/base.py:217` uses `df.apply(_calc_row_risk, axis=1)` to compute stop loss, take profit, and position sizing.
- The `_calc_row_risk` function (lines 185-215) performs scalar calculations for each row.
- `risk_utils.py` contains the underlying calculation functions which currently expect scalar inputs.

## Proposed Solutions

### Option 1: Vectorize Risk Utilities

**Approach:** Modify the functions in `tvscreener/lib/screeners/risk_utils.py` to support both scalar and array-like (Pandas Series) inputs. Then replace the `.apply()` call with direct column-wise operations.

**Pros:**
- Maximum performance gain (often 10x-100x faster than `.apply()`).
- Cleaner code in the base screener.
- Benefits all subclasses automatically.

**Cons:**
- Requires careful handling of `None` or `NaN` values in the series.
- Potential impact on existing callers of `risk_utils.py`.

**Effort:** 2-3 hours

**Risk:** Low

---

### Option 2: Use `np.vectorize`

**Approach:** Use `numpy.vectorize` to wrap the existing risk functions.

**Pros:**
- Minimal changes to existing risk utility logic.

**Cons:**
- Often less performant than native Pandas/NumPy vectorization (it's essentially a hidden loop).
- Still slower than Option 1.

**Effort:** 1 hour

**Risk:** Very Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/base.py:156` - `_apply_risk_management`
- `tvscreener/lib/screeners/risk_utils.py` - calculation functions

## Acceptance Criteria

- [ ] `.apply(axis=1)` removed from `_apply_risk_management`
- [ ] Risk calculations produce identical results to current implementation
- [ ] Performance benchmarks show improvement for datasets > 500 rows
- [ ] Unit tests for vectorized risk utilities

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Antigravity

**Actions:**
- Identified performance bottleneck in `base.py`.
- Analyzed `_apply_risk_management` logic.
- Verified `risk_utils.py` functions are currently scalar-only.
- Drafted vectorized solution approach.

## Notes

- Ensure `DIRECTION` column is handled correctly in vectorized form (e.g., using `np.where`).
- ATR column lookup should also be vectorized if possible.
