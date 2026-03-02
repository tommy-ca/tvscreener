---
status: complete
priority: p2
issue_id: "154"
tags: [performance, medallion, memory, pandas]
dependencies: []
---

# Optimize Medallion Memory Pressure

`rank_opportunities` triggers a full `df.copy()`, doubling memory during the Gold stage.

## Problem Statement

The `rank_opportunities` function in the Medallion architecture (Gold stage) currently performs a full dataframe copy (`df.copy()`). For large datasets, this effectively doubles the memory pressure, which can lead to Out-Of-Memory (OOM) errors or significant performance degradation due to swapping.

## Findings

- `rank_opportunities` calls `df.copy()`.
- This occurs during the Gold stage of the Medallion pipeline.
- Impact: High memory overhead, potentially limiting the scale of data that can be processed.

## Proposed Solutions

### Option 1: Use `copy=False` where possible

**Approach:** Audit the internal pipeline calls within `rank_opportunities` and use `copy=False` if the operations are safe or if the original dataframe is no longer needed.

**Pros:**
- Direct reduction in memory overhead.
- Relatively simple to implement.

**Cons:**
- Requires careful verification to ensure that in-place operations don't lead to unintended side effects if the original dataframe is used elsewhere.

**Effort:** 1-2 hours

**Risk:** Medium (potential for side effects)

---

### Option 2: In-place Operations

**Approach:** Refactor the ranking logic to use in-place operations (`inplace=True`) where supported by Pandas/Arrow.

**Pros:**
- Minimal memory footprint.

**Cons:**
- Some Pandas methods are deprecating `inplace=True`.
- Can make debugging more difficult as the state is modified directly.

**Effort:** 2-3 hours

**Risk:** Medium

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- (Identify the file containing `rank_opportunities`) - Likely in a Gold stage processor or a utilities file.

## Acceptance Criteria

- [ ] `df.copy()` removed or replaced with `copy=False` in `rank_opportunities`.
- [ ] Memory profiling confirms a reduction in peak memory usage during the Gold stage.
- [ ] All ranking and Gold stage tests pass.
- [ ] Verified no side effects on other parts of the pipeline that might use the original dataframe.

## Work Log

### 2026-03-02 - Initial Entry

**By:** Antigravity

**Actions:**
- Created todo for optimizing Medallion memory pressure.
- Identified `df.copy()` in `rank_opportunities` as the primary source of memory pressure.
- Proposed `copy=False` and in-place operations as potential fixes.

## Notes

- This is a critical performance fix for scaling the data pipeline.
