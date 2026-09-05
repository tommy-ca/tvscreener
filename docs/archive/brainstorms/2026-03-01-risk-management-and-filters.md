# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
date: 2026-03-01
topic: risk-management-and-enhanced-filters
---

# Risk Management Metadata and Enhanced Filters

## What We're Building

Enhancing the forex signals with actionable risk management data (Stop Loss, Take Profit, Risk/Reward ratio, Position Sizing) and more robust filtering (ATR-based volatility filtering and Relative Volume/RVOL).

## Why This Approach

### 1. Risk Management in Displays
Currently, risk management data is calculated but only exported to parquet. To make the CLI truly useful for traders, this information must be visible in the console.

**Pros:**
- Immediate actionable signals.
- Transparent risk/reward calculation.
- Contextual position sizing based on account balance.

**Cons:**
- Tables get wider.
- Might require a dedicated "Risk" view or toggling flags.

### 2. Enhanced Filters (ATR & RVOL)
Volatility (ATR) and Volume (RVOL) are critical for signal quality. High RVOL often confirms a breakout or trend continuation, while ATR helps filter out low-volatility environments where strategies underperform.

**Pros:**
- Higher quality signals (alpha).
- Filtering out "noise" in low liquidity/volume periods.

**Cons:**
- Fewer signals.
- RVOL calculation might differ between brokers.

## Key Decisions

- **Display Strategy**: Add risk management columns to the `detailed` view by default, and optionally to the `summary` view via a CLI flag (e.g., `--show-risk`).
- **RVOL Implementation**: Use TradingView's `relative_volume_10d_calc` field as the default RVOL source.
- **ATR Integration**: Expose ATR values in the `detailed` view to help users understand the volatility context of the signal.

## Scope — Individual Work Items

### P1 — Critical (Functional gaps)

1. **Include risk management in displays**:
   - Update `ForexStrategyScanner.print_summary` to show SL/TP/RR/Size if a flag is set.
   - Update `ForexStrategyScanner._render_detailed` to include a "Risk Management" section in each pair's panel.

2. **Implement RVOL filter**:
   - Add `min_rvol` to `ForexScreenerConfig`.
   - Update `AssetScreenerFactory` to handle RVOL filtering.
   - Update `ForexScreener` (or base `Screener`) to include the RVOL field in the API request if the filter is active.

### P2 — Important (Consistency)

3. **Detailed view enhancements**:
   - Show ATR and RVOL values in the `detailed` view header for each pair.
   - Format values consistently (e.g., RVOL as a multiplier like `2.1x`).

### P3 — Nice-to-have (Polish)

4. **CLI Flags**:
   - Add `--min-rvol` to the CLI.
   - Add `--show-risk` to toggle risk management columns in summary.

## Open Questions

- Should we show risk management for the `Opportunity` scanner as well? (Currently it only calculates scores, not entries).
- Which timeframe's ATR/RVOL should we use as the "primary" one? (Defaulting to HTF or the first timeframe in the list).
