---
status: complete
priority: p1
issue_id: "135"
tags: [architecture, narwhals, polars, pandas]
dependencies: ["133"]
---

# Refactor Scoring and Filters to Narwhals API

## Problem Statement
The current pipeline uses raw Pandas `.apply()` and boolean masks for calculating the `ENSEMBLE_SCORE` and applying filters. To support a modern DataOps compute layer that is dataframe-agnostic (allowing both PyArrow-backed Pandas and GPU-accelerated Polars execution), we need to abstract the mathematical compute layer.

## Findings
- `score.py` relies heavily on Pandas operations.
- `filter_utils.py` uses Pandas `.loc` and boolean masks.
- Narwhals (`narwhals-dev/narwhals`) allows us to write Polars-like expression syntax that natively executes on both Pandas and Polars without copying data.

## Proposed Solutions
1. **Adopt `narwhals`**: Add `narwhals` to the dependencies.
2. **Refactor `score.py`**: Wrap methods like `calculate_ensemble_score`, `calculate_confluence`, and `calculate_grades` with `@nw.narwhalify` and rewrite inner math to use `nw.col()`.
3. **Refactor `filter_utils.py`**: Update the strategy masks to use Narwhals expressions.

## Recommended Action
Incrementally refactor the core TA and scoring engines to use the Narwhals syntax bridge, keeping tests green.

## Acceptance Criteria
- [ ] `narwhals` added to dependencies.
- [ ] `score.py` logic rewritten with `nw.narwhalify` and Polars-style expressions.
- [ ] `filter_utils.py` logic rewritten.
- [ ] Unit tests still pass when providing native Pandas DataFrames to the modified functions.

## Work Log
### 2026-03-02 - Task Created
- Created as part of the Medallion Architecture modernization plan.
