---
status: completed
priority: p1
issue_id: "042"
tags: [performance, pandas, code-review]
dependencies: []
---

# Problem Statement
`_apply_roc_filter` used `df = df[...].copy()` inside a `for tf in self.timeframes:` loop. This created complete physical copies of the DataFrame in memory $O(N)$ times. For a 10-timeframe scan, the entire dataset was duplicated 10 times in RAM, leading to memory pressure and slow execution.

# Findings
- **File:** `tvscreener/lib/screeners/forex_opportunity.py`
- **Location:** `_apply_roc_filter`
- **Evidence:**
  ```python
  for tf in self.timeframes:
      # ...
      if roc.min_roc is not None:
          df = df[df[col] >= roc.min_roc].copy()
  ```

# Proposed Solutions
1. **Boolean Masking (Recommended)**: Accumulate a single boolean mask across all timeframes and perform a single slice/copy at the end.
2. **In-place Filtering**: Use `df.query` or similar, though mask accumulation is generally cleaner in pandas.

# Recommended Action
Implement Solution 1: Refactor to use a unified mask.

# Acceptance Criteria
- [x] DataFrame is copied exactly once during the ROC filtering process.
- [x] Filtering logic remains correct for multi-timeframe requirements.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified O(N) memory allocation bottleneck in filter loop.

### 2026-02-28 - Refactoring Complete
**By:** Antigravity
- Refactored `_apply_roc_filter` to use a unified boolean mask.
- Added `test_roc_filter_multi_timeframe` to `tests/unit/test_forex_opportunity.py`.
- Verified correctness with all 18 tests passing.
