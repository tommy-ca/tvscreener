---
status: complete
priority: p3
issue_id: "093"
tags: [architecture, refactor]
dependencies: []
---

# Extract RiskEngine

Extract risk calculation logic from ExportMixin into a dedicated RiskEngine module.

## Problem Statement

Risk logic (stop loss, take profit, risk/reward ratio calculations) is currently mixed into `ExportMixin`. This makes the code harder to maintain and limits the ability to provide specialized risk logic for different asset classes (multi-asset support).

## Findings

- `ExportMixin` contains methods like `calculate_stop_loss`, `calculate_take_profit`, and `calculate_risk_reward_ratio`.
- These methods are frequently used but are not strictly related to "exporting" data.
- The logic is currently tailored to specific assumptions that may not hold for all asset types.

## Proposed Solutions

### Option 1: Dedicated RiskEngine Module

**Approach:** Create a `RiskEngine` class or module and move all risk-related calculations there.

**Pros:**
- Better separation of concerns.
- Facilitates multi-asset support by allowing specialized engines or configurations.
- Easier to test risk logic in isolation.
- Cleaner `ExportMixin`.

**Cons:**
- Requires updating all call sites (though likely limited to screener classes).

**Effort:** 3-4 hours

**Risk:** Low

## Recommended Action

**Extract to RiskEngine class in `risk_utils.py`.**

## Acceptance Criteria

- [x] `RiskEngine` module created in `lib/`.
- [x] Risk calculation methods moved from `ExportMixin` to `RiskEngine`.
- [x] Screener classes updated to use `RiskEngine`.
- [x] `ExportMixin` cleaned up of non-export logic.
- [x] Unit tests for `RiskEngine` implemented.

## Work Log

### 2026-03-01 - Initial Creation

**By:** opencode

**Actions:**
- Created todo file 093 for RiskEngine extraction.
- Defined problem statement and proposed solution.
- Set priority to P3 as requested.

### 2026-03-01 - Extraction Completed

**By:** opencode

**Actions:**
- Created `RiskEngine` and `RiskConfig` in `tvscreener/lib/screeners/risk_utils.py`.
- Moved application logic from `ExportMixin._apply_risk_management` to `RiskEngine.apply`.
- Updated `ExportMixin` in `base.py` to remove `_apply_risk_management`.
- Updated `BaseOpportunityScreener` and `ForexStrategyScanner` to use `RiskEngine`.
- Added unit tests for `RiskEngine` in `tests/unit/test_risk_utils.py`.
- Verified all risk-related tests pass.

## Notes

- This refactor is essential for future multi-asset support (e.g., different risk models for Crypto vs Forex).
- The extraction follows the unified risk management plan.
