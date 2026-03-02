---
status: pending
priority: p3
issue_id: "159"
tags: [hygiene, time, narwhals, base-py]
dependencies: []
---

# Standardize Time and Backend Casting

Ensure consistent use of UTC datetimes and Narwhals `.to_native()` for backend casting in `base.py`.

## Problem Statement

The `base.py` file has mixed usage of `time.time()` and inconsistent casting to native backends (e.g., `.cast(pd.DataFrame)` vs Narwhals' native methods). This lack of standardization can lead to subtle bugs in time-sensitive logic and makes the code less portable across different data backends.

## Findings

- `base.py` uses `time.time()` in some places, which returns local-dependent epoch seconds.
- There's inconsistent use of `.cast(pd.DataFrame)` which bypasses Narwhals' backend-agnostic advantages.
- Mixed patterns for converting between Narwhals-wrapped objects and native objects (pandas/polars) exist.

## Proposed Solutions

### Option 1: Standardize on UTC and .to_native()

**Approach:** 
1. Replace all `time.time()` calls with `datetime.now(timezone.utc).timestamp()` or similar UTC-aware methods.
2. Replace `.cast(pd.DataFrame)` (and similar hardcoded casts) with Narwhals' `.to_native()` or appropriate Narwhals-native casting methods where applicable.

**Pros:**
- Improved portability and consistency.
- Better handling of timezones, reducing potential for "off-by-N-hours" bugs.
- Leverages Narwhals' abstraction layer more effectively.

**Cons:**
- Requires careful auditing of all time-related and casting-related lines.

**Effort:** 2-4 hours

**Risk:** Low/Medium (Time handling changes always carry a small risk of breaking time-dependent logic)

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/base.py` - Primary location for these inconsistencies.

## Acceptance Criteria

- [ ] All instances of `time.time()` in `base.py` are replaced with UTC-aware alternatives.
- [ ] Hardcoded `.cast(pd.DataFrame)` or similar calls are reviewed and replaced with Narwhals-idiomatic `.to_native()` where possible.
- [ ] Time-related logic is verified to work across different timezones.
- [ ] Tests confirm that backend-switching (if supported) still works correctly after standardization.

## Work Log

### 2026-03-02 - Task Creation

**By:** Antigravity

**Actions:**
- Identified inconsistent time and casting patterns in `base.py`.
- Proposed standardization on UTC and Narwhals `.to_native()`.
- Created P3 todo.

## Notes

- Hygiene task to improve code quality and robustness.
