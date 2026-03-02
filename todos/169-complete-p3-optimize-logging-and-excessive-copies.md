---
status: complete
priority: p3
issue_id: "169"
tags: [perf, logging, memory]
dependencies: []
---

# Optimize Logging and Excessive Copies

Improve performance by reducing F-string logging overhead and eliminating redundant `df.copy()` calls in strategy detection.

## Problem Statement

F-string logging (evaluated even when log level is high) and redundant `df.copy()` calls in internal scoring loops are creating unnecessary overhead and memory pressure during strategy detection.

## Findings

- Strategy detection calls scoring functions frequently.
- Each call currently performs a `df.copy()`, which is expensive for large dataframes.
- F-strings in logging calls are interpolated even if the logging level is not met.

## Proposed Solutions

### Option 1: Lazy logging and copy=False

**Approach:** Switch to lazy logging (passing arguments to the logger instead of using f-strings directly) and use `copy=False` in internal scoring calls where data is not being modified.

**Pros:**
- Reduced CPU overhead from string interpolation.
- Reduced memory usage and GC pressure from fewer dataframe copies.
- Significant performance boost for large-scale screenings.

**Cons:**
- Requires careful verification that `copy=False` doesn't lead to accidental data mutation.

**Effort:** 2-3 hours

**Risk:** Medium (due to potential side effects of avoiding copies)

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- Various files implementing strategy detection and scoring.
- Logging calls across the performance-critical paths.

## Acceptance Criteria

- [ ] Critical logging calls switched to lazy evaluation.
- [ ] `df.copy()` calls analyzed and replaced with views or `copy=False` where safe.
- [ ] Benchmark showing performance improvement (optional but recommended).
- [ ] Verification that data integrity is maintained (no accidental mutations).

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created P3 todo for logging and copy optimization.

