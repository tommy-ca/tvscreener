# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
date: 2026-03-01
topic: confluence-strategy-audit
---

# Confluence Strategy Scanners Audit

## What We're Building
A comprehensive audit and validation of the "Confluence" strategy detection logic in `ForexStrategyScanner`. This strategy identifies high-probability trading setups based on multi-timeframe (HTF, STF, LTF) alignment of trends and oscillators.

## Why This Approach
The "Confluence" strategy is the most complex detection path in the system. It uses `np.select` to categorize pairs into patterns like `trend_mr_entry`, `trend_continuation`, and `trend_pullback`. Ensuring the logic correctly identifies these patterns across 12 cells (3 TFs × 4 factors) is critical for signal reliability.

## Key Decisions
- **Validate Pattern Priority**: Verify that the `np.select` order correctly prioritizes `trend_mr_entry` (Score 4) over others.
- **Cross-Reference Scores**: Audit how `CONFLUENCE_SCORE` (1-5 strategy specific) relates to `GRID_ALIGNED` (0-12 cross-scanner).
- **Extremity Check**: Validate `MR_EXTREMITY` calculation (max absolute oscillator value) as a tie-breaker for ranking.

## Audit Plan

### 1. Logic Verification (Mental/Code Audit)
- **Trend Threshold**: Currently `trend_threshold: float = 0.0`. Does this allow too much noise?
- **MR Threshold**: Currently `mr_threshold: float = 0.2`.
- **Pattern Definitions**:
    - `trend_mr_entry`: HTF trend + STF mean-reversion + LTF mean-reversion.
    - `trend_continuation`: HTF trend + STF trend + LTF trend.
    - `trend_pullback`: HTF trend + STF trend + LTF mean-reversion.
    - `mr_reversal`: HTF MR + STF MR + LTF MR.

### 2. Execution Audit
Run confluence strategy specifically for both universes:
```bash
uv run python -m tvscreener.cli -s strategy -u majors --strategy confluence --detailed
uv run python -m tvscreener.cli -s strategy -u minors --strategy confluence --matrix
```

### 3. Data Integrity
- Check for `NaN` handling in `_col` helper (currently fills with 0).
- Verify `roc_bonus` logic (+1 if ROC aligns across ALL timeframes).

## Open Questions
- Is `base_score` of 3 for `trend_continuation` too low compared to 4 for `trend_mr_entry`?
- Should `roc_bonus` require alignment on all 3 TFs, or is 2/3 sufficient?

## Next Steps
1. Run the targeted confluence scans.
2. Compare a few "Grade A+" signals from Opportunity scanner with their "Confluence" score.
3. Adjust thresholds in `StrategyConfig` if noise is too high.
