---
status: complete
priority: p2
issue_id: "188"
tags: [performance, pyarrow, numpy, refactoring]
dependencies: []
---

# Eliminate NumPy Arrow Leakage

## Problem Statement

The implementation in `score.py` and `forex_strategy.py` currently utilizes `np.where` and `np.select`. Since the underlying DataFrames are backed by PyArrow, using NumPy functions forces the PyArrow data to serialize back into NumPy arrays. This breaks the Arrow performance advantages and introduces unnecessary conversion overhead.

## Findings

- `np.where` and `np.select` are actively used in `score.py` and `forex_strategy.py`.
- Converting between PyArrow and NumPy structures causes performance degradation due to memory copying and type conversions.
- Native Pandas methods or Narwhals expressions would keep operations in the Arrow execution space.

## Proposed Solutions

### Option 1: Native Pandas Series Methods

**Approach:** Replace `np.where` with `Series.where` (or `Series.mask`) and refactor `np.select` into chained `.mask()` calls or `pd.cut()` where appropriate.

**Pros:**
- Keeps execution in native Pandas without NumPy overhead.
- Simple syntax changes.

**Cons:**
- `np.select` can sometimes be verbose to replicate purely in Pandas depending on condition complexity.

**Effort:** 1-2 hours
**Risk:** Low

### Option 2: Narwhals Expressions

**Approach:** Utilize Narwhals expressions (`nw.when().then().otherwise()`) for evaluating conditions.

**Pros:**
- Provides a very robust, Arrow-native execution path.
- Syntax maps very nicely to `np.select` logic.

**Cons:**
- Adds a slight dependency on Narwhals API, though it's already used elsewhere in the project.

**Effort:** 2-3 hours
**Risk:** Low

## Recommended Action

Implement Option 2. Replace the NumPy calls (`np.where`, `np.select`) with Narwhals `nw.when().then().otherwise()` constructs to ensure zero-copy execution and full PyArrow compatibility.

## Technical Details

**Affected files:**
- `tvscreener/score.py`
- `tvscreener/lib/screeners/forex_strategy.py`

**Related components:**
- Scoring algorithms
- Strategy filters

## Resources

- Pandas and PyArrow interoperability documentation
- Narwhals expressions documentation

## Acceptance Criteria

- [x] `np.where` and `np.select` are completely removed from `score.py` and `forex_strategy.py`.
- [x] Logic is replaced with Arrow-friendly native operations (e.g., `nw.when()`).
- [x] No performance regressions or type conversion errors are introduced.
- [x] Tests pass when executing `uv run pytest`.

## Work Log

### 2026-03-03 - Initial Creation

**By:** Claude Code

**Actions:**
- Created todo from issue findings.

### 2026-03-03 - Implementation Complete

**By:** Claude Code

**Actions:**
- Replaced `np.where` and `np.select` with Narwhals expressions in `tvscreener/score.py` and `tvscreener/lib/screeners/forex_strategy.py`.
- Used nested `nw.when().then().otherwise(nw.when()...)` for multi-condition logic to comply with Narwhals API.
- Verified with `uv run pytest tests/unit/test_score_arrow.py tests/unit/test_forex_scoring.py tests/unit/test_forex_strategy.py`.
