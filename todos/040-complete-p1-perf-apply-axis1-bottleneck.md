---
status: completed
priority: p1
issue_id: "040"
tags: [performance, pandas, code-review]
dependencies: []
---

# Problem Statement
`_prepare_enriched_data` uses `df.apply(..., axis=1)` to generate the `STRENGTH_SIGN` column. This iteration breaks C-level vectorization in pandas and will severely bottleneck performance on large asset universes (e.g., scanning thousands of stocks or crypto pairs).

# Findings
- **File:** `tvscreener/lib/screeners/forex_strategy.py`
- **Location:** `_prepare_enriched_data` (Line 2200)
- **Evidence:**
  ```python
  df["STRENGTH_SIGN"] = df.apply(
      lambda row: self._get_strength_sign(
          float(row.get("CONFLUENCE_SCORE", 0)), row["DIRECTION"]
      ),
      axis=1,
  )
  ```

# Proposed Solutions
1. **Vectorized numpy.select (Recommended)**: Use `np.select` with boolean masks for direction and score to assign symbols at C-speed.
2. **Series Map**: If logic is too complex for select, use vectorized series operations where possible.

# Recommended Action
Implement Solution 1: Replace row-wise apply with a vectorized `np.select` block.

# Acceptance Criteria
- [x] `STRENGTH_SIGN` column generated without using `axis=1` apply.
- [x] Column values remain identical to previous implementation.
- [x] Verified performance improvement on large DataFrames.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified pandas anti-pattern bottleneck in data enrichment.

### 2026-02-28 - Resolution
**By:** Antigravity
- Replaced `df.apply(axis=1)` with vectorized `np.select` in `_prepare_enriched_data`.
- Verified 30x performance improvement (0.17s vs 5.04s for 100k rows).
- Verified correctness against original implementation.
