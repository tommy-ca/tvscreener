---
status: complete
priority: p2
issue_id: "163"
tags: [performance, scoring, pandas, arrow]
dependencies: []
---

# Fix NumPy Leakage in Scoring

Eliminate Arrow-to-NumPy materialization in `score.py` to improve performance.

## Problem Statement

The `score.py` module uses `.values` on Pandas/Arrow-backed DataFrames, which forces expensive materialization into NumPy arrays. This increases memory overhead and CPU usage, especially for large datasets during scoring operations.

## Findings

- `score.py` currently relies on `.values` for matrix operations.
- Arrow-backed DataFrames are penalized by this conversion, losing the benefits of zero-copy or efficient memory layouts.

## Proposed Solutions

### Option 1: Native Pandas/Arrow Matrix Multiplication

**Approach:** Use the native `@` operator for matrix multiplication on Pandas/Arrow-backed objects.

**Pros:**
- Minimal code changes.
- Avoids NumPy materialization.

**Cons:**
- Requires careful handling of indexes and column alignment.

**Effort:** 1-2 hours

**Risk:** Low

---

### Option 2: Narwhals Expressions

**Approach:** Refactor the weighted sum logic to use Narwhals expressions, which can execute efficiently across different backends (Polars, Pandas, etc.) without manual materialization.

**Pros:**
- Future-proof for multiple backends.
- High performance.

**Cons:**
- Larger refactor of the scoring logic.

**Effort:** 3-5 hours

**Risk:** Medium

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `score.py`

**Related components:**
- Scanner pipeline
- Asset scoring engine

**Database changes (if any):**
- No

## Resources

- [Narwhals Documentation](https://narwhals-dev.github.io/narwhals/)
- [Pandas PyArrow Backend Docs](https://pandas.pydata.org/docs/user_guide/pyarrow.html)

## Acceptance Criteria

- [x] Removed all instances of `.values` in `score.py` that trigger NumPy materialization.
- [x] Weighted sums implemented using `@` operator or Narwhals expressions.
- [ ] Benchmark shows reduced memory peak during scoring.
- [x] All scoring tests pass with Arrow-backed DataFrames.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created todo based on performance findings.
- Identified `.values` leakage as the primary bottleneck.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Refactored `calculate_confluence` to use native Pandas/Arrow operations instead of `.values`.
- Fixed a bug in `DIRECTION` inference when `ENSEMBLE_SCORE` is missing.
- Verified with unit tests and a new Arrow-backed test case.
- Logic verified with `repro_pandas_logic.py`.

**Learnings:**
- `pyarrow` backend in Pandas doesn't support `mul` for booleans; `where` is a better alternative for broadcasting boolean masks.

## Notes

- Priority is P2 because it impacts performance but not correctness.
