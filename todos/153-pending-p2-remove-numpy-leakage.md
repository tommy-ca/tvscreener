---
status: pending
priority: p2
issue_id: "153"
tags: [performance, score, pandas, arrow]
dependencies: []
---

# Remove NumPy Leakage in Scoring

`score.py` uses `.values`, forcing Arrow-to-NumPy materialization, which is inefficient.

## Problem Statement

The scoring logic in `score.py` currently relies on `.values` when interacting with Pandas/Arrow dataframes. This triggers a materialization process where data is converted from the memory-efficient Arrow format to NumPy arrays. This conversion is a performance bottleneck, especially for large datasets.

## Findings

- `score.py` uses `.values` for matrix operations.
- This forces Arrow-to-NumPy materialization.
- Impact: Increased memory usage and processing time during the scoring stage.

## Proposed Solutions

### Option 1: Native Pandas/Arrow Matrix Multiplication

**Approach:** Replace `.values` and NumPy-based multiplication with the native Pandas/Arrow matrix multiplication operator (`@`).

**Pros:**
- Avoids unnecessary data conversion.
- Leverages optimized underlying libraries (Arrow/Pandas).
- Cleaner code.

**Cons:**
- Requires ensuring both operands are compatible Pandas/Arrow objects.

**Effort:** 1-2 hours

**Risk:** Low

---

### Option 2: Narwhals Expressions

**Approach:** Use Narwhals expressions for weighted sums, which can be executed efficiently across different backends (Pandas, Polars, etc.) without manual materialization.

**Pros:**
- Backend-agnostic efficiency.
- Highly expressive for weighted sums and aggregations.

**Cons:**
- Adds a dependency on Narwhals if not already present.
- Slightly steeper learning curve for developers unfamiliar with Narwhals.

**Effort:** 2-3 hours

**Risk:** Medium (due to new dependency)

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `score.py` (Identify specific lines where `.values` is used for scoring)

## Acceptance Criteria

- [ ] `.values` usage removed from scoring logic in `score.py`.
- [ ] Native `@` operator or Narwhals expressions implemented.
- [ ] Performance benchmark shows reduction in Arrow-to-NumPy materialization overhead.
- [ ] All existing scoring tests pass.

## Work Log

### 2026-03-02 - Initial Entry

**By:** Antigravity

**Actions:**
- Created todo for removing NumPy leakage in scoring.
- Identified `.values` as the root cause of inefficient materialization.
- Proposed native `@` and Narwhals as alternatives.

## Notes

- Priority is P2 because this is a significant performance optimization for the scoring pipeline.
