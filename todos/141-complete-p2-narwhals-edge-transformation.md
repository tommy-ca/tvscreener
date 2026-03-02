---
status: complete
priority: p2
issue_id: "141"
tags: [architecture, narwhals, duckdb]
dependencies: ["140", "135"]
---

# Use Narwhals for Universal Edge Transformation

## Problem Statement
When data is queried from DuckDB at the edge, it may lose some metadata or requires re-enrichment (renaming columns, adding STRENGTH_SIGN) before it can be rendered by the specialized views. We currently duplicate some logic for this.

## Findings
- `EdgeQueryClient.query_expr` exists but isn't used in the main CLI path.
- The "Screener Output Stage" needs a way to standardize different backends (Pandas result vs DuckDB relation) before rendering.

## Proposed Solutions
1. **Narwhalify the Output Stage**: Refactor the `enrich_screener_data` and `DataTransformer` calls to accept Narwhals frames.
2. **Universal Pre-render**: In the orchestrator, ensure every result (SQL or Scan) goes through a final Narwhals-based normalization step.

## Recommended Action
Refactor `_prepare_enriched_data` in `ExportMixin` to be a pure function that takes a Narwhals frame. Use this function in both the scan path and the SQL path.

## Acceptance Criteria
- [ ] `DataTransformer` methods are fully decorated with `@nw.narwhalify`.
- [ ] The output stage is agnostic to whether the source was a DuckDB relation or a Pandas DataFrame.
- [ ] Duplicate enrichment logic in `forex_strategy.py` and `base.py` is consolidated into `DataTransformer`.

## Work Log
### 2026-03-02 - Task Created
- Part of "Screener Output Stage" audit for feature parity.
