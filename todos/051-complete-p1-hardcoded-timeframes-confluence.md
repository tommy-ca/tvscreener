---
status: completed
priority: p1
issue_id: "051"
tags: [forex, strategy, bug, code-review]
dependencies: []
---

# Problem Statement
In `tvscreener/lib/screeners/forex_strategy.py`, the `_detect_confluence` method hardcodes timeframes `"240"`, `"60"`, and `"15"`. If a user specifies custom timeframes via the CLI or config, this method will attempt to access non-existent columns (e.g., `Recommend All|240` when only `60` and `15` were requested), potentially causing a crash or incorrect signals.

# Findings
- **File**: `tvscreener/lib/screeners/forex_strategy.py`
- **Lines**: 62362–62367 (approx)
- **Evidence**:
  ```python
  htf = _col("Recommend All|240")
  stf = _col("Recommend All|60")
  ltf = _col("Recommend All|15")
  ```

# Proposed Solutions
1. **Dynamic Resolution**: Use `self.timeframes` to determine which columns to use for HTF/STF/LTF logic. If more than 3 timeframes exist, pick the largest/middle/smallest. If fewer than 3 exist, adapt the logic to only use available data.
2. **Validation**: Add a check to ensure that the required timeframes for confluence detection are present in the dataset before proceeding.

# Recommended Action
Implement Solution 1: Map `self.timeframes` (sorted descending) to HTF, STF, and LTF variables dynamically.

# Acceptance Criteria
- [x] Confluence scanner works with custom `--timeframes`.
- [x] No hardcoded timeframe strings in `_detect_confluence`.
- [x] Graceful handling when fewer than 3 timeframes are provided.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Review Architect)
- Identified hardcoded timeframes in confluence logic.

### 2026-02-28 - Fixed
**By:** Antigravity
- Implemented `_get_htf_stf_ltf()` helper to dynamically resolve timeframes.
- Updated `_detect_confluence`, `_detect_trend_following`, `_detect_mean_reversion`, and `_detect_hybrid` to use dynamic timeframes.
- Updated ROC momentum confirmation to use `self.timeframes`.
