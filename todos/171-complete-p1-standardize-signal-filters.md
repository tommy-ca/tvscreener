---
status: complete
priority: p1
issue_id: "171"
tags: [architecture, filtering, narwhals, quant]
dependencies: ["135", "143"]
---

# Standardize ATR and Volume Filters for Signals

## Problem Statement
Filters for ATR (volatility) and Volume are currently applied at different stages of the pipeline (some in Silver, some in Strategy detection), and they often rely on raw API column names. To support the Medallion architecture and reliable signal generation, these filters must be standardized, layer-agnostic, and applied to the final "Gold" signals.

## Findings
- `filter_utils.py` uses hardcoded raw column names like `"Average Volume (10 day Calc)"`.
- `ForexOpportunityScreener` applies filters in `_apply_asset_filters` (Silver layer).
- `ForexStrategyScanner` has a `require_volume_spike` flag that isn't fully enforced at the signal level.

## Proposed Solutions
1. **Universal Filter Helpers**: Update `apply_volume_filter`, `apply_atr_filter`, and `apply_rvol_filter` in `filter_utils.py` to check for both raw names and canonical names (`AVG_VOLUME`, `ATR_{tf}`).
2. **Implement Volatility Percentage**: Add `apply_volatility_pct_filter` to filter based on `(ATR / Price) * 100`.
3. **Gold-Layer Enforcement**: In `ScreenerController.run_scan`, ensure these filters are applied to the final result DataFrame after scoring/detection.

## Recommended Action
Refactor `filter_utils.py` and update the `ScreenerController` to use these helpers at the end of the scan lifecycle.

## Acceptance Criteria
- [ ] `filter_utils.py` helpers are robust to column naming.
- [ ] `require_volume_spike` correctly filters for `RVOL > 1.5`.
- [ ] New `--min-vol-pct` CLI flag (via `AssetSelection.min_volatility_pct`) works correctly.
- [ ] Filters correctly restrict the final signals shown in Matrix/Detailed views.

## Work Log
### 2026-03-02 - Initial Creation
- Part of "Apply ATR/Volatility and Volume Filters" plan.
