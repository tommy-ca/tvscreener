---
status: completed
priority: p1
issue_id: "041"
tags: [performance, rich, code-review]
dependencies: []
---

# Problem Statement
`ForexStrategyScanner.print_summary` uses `.iterrows()` on the entire dataset without a `.head()` boundary. Rendering thousands of rows via Rich tables in a CLI is slow, and `.iterrows()` is the slowest way to access pandas data. This can cause the CLI to appear "frozen" for several seconds or minutes.

# Findings
- **File:** `tvscreener/lib/screeners/forex_strategy.py`
- **Location:** `print_summary`
- **Evidence:**
  ```python
  for _, row in strategy_df.iterrows():
      # ... rich table row creation ...
  ```

# Proposed Solutions
1. **Limit Output (Recommended)**: Add a default limit (e.g., top 20-50 signals) to the summary table, similar to the opportunity scanner.
2. **Switch to itertuples**: If all rows must be shown, use `.itertuples(index=False)` which is 10-50x faster than `.iterrows()`.

# Recommended Action
Implement Solution 1: Add a `.head(20)` limit to the summary rendering loop and provide a total count message.

# Acceptance Criteria
- [x] Strategy summary rendering time is consistent regardless of dataset size.
- [x] Uses `.itertuples()` for faster iteration.
- [x] Displays a message if results are truncated.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified potential CLI hang due to unbounded slow iteration.

### 2026-02-28 - Performance Fix
**By:** Antigravity
- Replaced `.iterrows()` with `.itertuples()` for faster row iteration.
- Added a default `limit=20` to `print_summary` to prevent CLI freeze on large datasets.
- Added truncation message when results exceed the limit.
- Verified changes via syntax check and code review.
