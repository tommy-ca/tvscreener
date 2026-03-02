---
status: complete
priority: p1
issue_id: "133"
tags: [architecture, pandas, pyarrow, medallion]
dependencies: ["132"]
---

# Enforce PyArrow Backend Early in Pipeline

## Problem Statement
The pipeline currently casts the DataFrame to `dtype_backend="pyarrow"` at the very end of the Opportunity scan (in `base.py`), after all Native Pandas deduplication and scoring math is complete. This means intermediate processing consumes more memory than necessary and does not take advantage of zero-copy optimizations early on, which is critical for our new Narwhals abstraction layer.

## Findings
- PyArrow backend conversion happens at `base.py:224`.
- TradingView API fetch happens earlier in `_fetch_all_data`.

## Proposed Solutions
1. **Early Conversion**: Move the `df.convert_dtypes(dtype_backend="pyarrow")` call into `_fetch_all_data` immediately after the raw JSON is loaded into a DataFrame.

## Recommended Action
Implement early PyArrow conversion to keep memory footprint minimal across all transformations before Narwhals takes over.

## Acceptance Criteria
- [ ] `convert_dtypes(dtype_backend="pyarrow")` moved to immediately follow API ingestion.
- [ ] All scoring math and filters continue to work correctly with PyArrow dtypes.
- [ ] Strict dtype validation enforced at the Silver layer boundary.

## Work Log
### 2026-03-02 - Task Created
- Created as part of the Medallion Architecture modernization plan.
