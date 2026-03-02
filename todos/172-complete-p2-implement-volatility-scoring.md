---
status: complete
priority: p2
issue_id: "172"
tags: [quant, scoring, risk]
dependencies: ["171"]
---

# Implement Volatility-Adjusted Signal Strength

## Problem Statement
Currently, signal strength is primarily based on trend and momentum confluence. However, a strong trend in a low-volatility environment may be less actionable than a moderate trend in a high-volatility environment.

## Findings
- ATR is fetched but not used as a primary weight in the `ENSEMBLE_SCORE`.
- `RiskEngine` uses ATR for stop-loss, but doesn't influence the signal's "Grade".

## Proposed Solutions
1. **Volatility Scaling**: Modify `ScoringEngine` to optionally scale the `ENSEMBLE_SCORE` by a volatility factor (e.g., multiplying by `RVOL` or a normalized `ATR_PCT`).
2. **Grade Penalties**: Automatically downgrade signals (e.g., A+ to B) if volatility is below a certain percentile of the historical average.

## Recommended Action
Add a `volatility_weight` to `ScoringConfig` and incorporate it into the final `Gold` signal generation.

## Acceptance Criteria
- [ ] `ENSEMBLE_SCORE` can be configured to consider relative volatility.
- [ ] Signals with extremely low ATR are automatically flagged or filtered.

## Work Log
### 2026-03-02 - Initial Creation
- Part of "Apply ATR/Volatility and Volume Filters" plan.
