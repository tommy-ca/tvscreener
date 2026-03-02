---
status: completed
priority: p3
issue_id: "086"
tags: [performance, regex]
dependencies: []
---

# Optimization: Regex backtracking with large pair lists

Replace large OR-joined regex patterns with hash-map or string slicing in _merge_duplicates.

## Problem Statement

`_merge_duplicates` uses a massive OR-joined regex pattern to extract currency pairs from symbol names. As `VALID_PAIRS` (currently ~45 items) grows, this can lead to catastrophic backtracking or high memory usage during regex compilation/execution. It is also inherently slower than direct string operations.

## Findings

- **File:** `tvscreener/lib/screeners/forex_opportunity.py` (lines 210-214)
- **Current implementation:**
  ```python
  pairs_alt = "|".join(re.escape(p) for p in VALID_PAIRS)
  base_pair_match = names.str.extract(
      rf"^(?P<p1>{pairs_alt})(?=$|[._])|_(?P<p2>{pairs_alt})\.",
      expand=True,
  )
  ```
- Large regex patterns are fragile and hard to debug.

## Proposed Solutions

### Option 1: Hash-map (Dict) Lookup

**Approach:** Pre-process names (e.g., take first 6 characters or split by `.` or `_`) and look up in a `set` or `dict` of valid pairs.

**Pros:**
- O(1) lookup time instead of O(N) regex matching
- Easier to maintain and extend
- Avoids regex compilation overhead

**Cons:**
- Requires careful handling of different naming formats (e.g., `EURUSD`, `OANDA:EUR_USD`)

**Effort:** 1 hour

**Risk:** Medium (must ensure all edge cases for symbol formats are covered)

---

### Option 2: Trie-based Regex

**Approach:** Use a library like `backtracking-free-regex` or manually build a trie-based regex to optimize the search.

**Pros:**
- Keeps the regex interface but optimizes execution

**Cons:**
- Overkill for simple string matching

**Effort:** 2 hours

**Risk:** Low

## Recommended Action

**Completed by Antigravity (Claude) on 2026-03-01.**

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_opportunity.py:210`

## Acceptance Criteria

- [x] Large OR-joined regex removed
- [x] New implementation handles `EURUSD`, `EUR_USD`, `OANDA:EURUSD`, etc.
- [x] Performance improved for large pair lists
- [x] No regression in pair identification

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Identified performance risk in `_merge_duplicates` regex logic
- Verified current `VALID_PAIRS` size

### 2026-03-01 - Implementation

**By:** Antigravity (Claude)

**Actions:**
- Replaced large OR-joined regex with vectorized string slicing and hash-map (set) lookup.
- Handled multiple formats: OANDA:EURUSD, EURUSD.CFD, EUR_USD.CFD, FX_EURUSD.GR.
- Used simple regex `r"_([A-Z]{6})\."` for suffix matching to avoid backtracking issues.
- Verified logic covers all original patterns and improves robustness for exchange prefixes.

---
