---
status: complete
priority: p2
issue_id: "123"
tags: [dead-code, simplicity, code-review]
dependencies: []
---

# Dead Standalone Risk Utility Functions (~120 Lines)

## Problem Statement

Five standalone functions in `risk_utils.py` have zero production callers: `check_risk_limits()`, `check_signal_quality()`, `calculate_volume_roc()`, `check_volume_spike()`, `calculate_drawdown()`. They are only referenced in their own test file. The `RiskEngine.apply()` method and vectorized calculation functions ARE used.

## Findings

- `tvscreener/lib/screeners/risk_utils.py:258-379` — 5 unused functions (~120 lines)
- `tests/unit/test_risk_utils.py` — Tests for unused functions (~50 lines)
- `RiskConfig.max_daily_loss_pct` and `max_drawdown_pct` only used by dead `check_risk_limits()`
- The vectorized functions (calculate_stop_loss, calculate_take_profit, etc.) ARE used

## Proposed Solutions

### Option 1: Delete Dead Functions + Tests

**Approach:** Remove 5 functions and their tests. Remove unused RiskConfig fields.

**Effort:** 15 minutes
**Risk:** None (YAGNI — can be re-added if needed)

## Recommended Action

**Delete dead functions + tests.** Remove 5 unused functions from `risk_utils.py` and their tests. Remove unused `max_daily_loss_pct` and `max_drawdown_pct` from `RiskConfig`. ~170 lines removed.

## Acceptance Criteria

- [ ] No unused functions in risk_utils.py
- [ ] All remaining tests pass
- [ ] ~170 lines removed (code + tests)

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (code-simplicity-reviewer)
