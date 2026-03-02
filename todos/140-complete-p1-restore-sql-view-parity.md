---
status: complete
priority: p1
issue_id: "140"
tags: [architecture, ui, feature-parity]
dependencies: ["134"]
---

# Restore Specialized Views for SQL Results (Feature Parity)

## Problem Statement
The recent architectural shift to Edge DuckDB moved SQL execution outside the core pipeline. However, the current implementation in `ScreenerController` bypasses the specialized Rich renderers (Matrix/Detailed) when `--sql` is used, falling back to a generic string table. This breaks feature parity with the original implementation where SQL results still looked like beautiful ASCII matrices.

## Findings
- `ScreenerController.run_opportunity_scan` prints a generic table for SQL results.
- `BaseOpportunityScreener.print_summary` is hardcoded to use `_prepare_enriched_data()` from its own internal state.
- `RichConsoleRenderer.render` doesn't currently allow passing an external DataFrame.

## Proposed Solutions
1. **Refactor Renderer**: Modify `RichConsoleRenderer.render` to accept an optional `df` argument. If provided, use it instead of calling `screener._prepare_enriched_data()`.
2. **Refactor Screener**: Update `BaseOpportunityScreener.print_summary` to accept `df: pd.DataFrame | None = None`.
3. **Narwhals Enrichment**: In the output stage, if we have a SQL result, run it through `DataTransformer` (via Narwhals) to ensure column names are standardized before rendering.

## Recommended Action
Implement an "External Data" path for the renderer. When `--sql` is used, the orchestrator should:
1. Get the SQL results from `EdgeQueryClient`.
2. Pass these results back to `screener.print_summary(results=results, ...)`.
3. The renderer will automatically fall back to the generic view if the user's SQL query changed the schema too much to fit the Matrix/Detailed views.

## Acceptance Criteria
- [ ] `tvscreener-scan --sql "SELECT * FROM df" --matrix` produces a beautiful matrix, not a generic table.
- [ ] `tvscreener-scan --sql "SELECT pair FROM df"` correctly falls back to a generic table because technical columns are missing.
- [ ] `RichConsoleRenderer` handles both internal state and external dataframes identically.

## Work Log
### 2026-03-02 - Task Created
- Part of "Screener Output Stage" audit for feature parity.
