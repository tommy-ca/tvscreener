---
status: complete
priority: p2
issue_id: "114"
tags: [patterns, duplication, code-review]
dependencies: []
---

# Risk Management Defaults Repeated in 7+ Locations

## Problem Statement

The values `risk_per_trade=1.0, atr_multiplier=2.0, min_risk_reward=1.5, account_balance=10000.0, pip_value=10.0` are hardcoded as defaults in 7+ separate locations. Changing a default requires updating all locations.

## Findings

- `tvscreener/lib/screeners/base.py:36-40` — ScreenerConfig defaults
- `tvscreener/lib/screeners/risk_utils.py:18-24` — RiskConfig defaults
- `tvscreener/config/settings.py:41-48` — RiskSettings defaults
- `tvscreener/lib/orchestrator.py:500-506` — _build_opportunity_config fallbacks
- `tvscreener/lib/orchestrator.py:549-555` — _build_strategy_config fallbacks
- `tvscreener/lib/screeners/factory.py:105-109` — getattr fallbacks

## Proposed Solutions

### Option 1: Create RISK_DEFAULTS Constant

**Approach:** Define `RISK_DEFAULTS = RiskConfig()` in `risk_utils.py` and reference everywhere.

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

**Create RISK_DEFAULTS constant.** Define `RISK_DEFAULTS = RiskConfig()` in `risk_utils.py` and reference from all 7 locations instead of repeating values.

## Acceptance Criteria

- [ ] Risk defaults defined in exactly one location
- [ ] All consumers reference the canonical defaults
- [ ] No hardcoded risk values in config builders

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (pattern-recognition-specialist)
