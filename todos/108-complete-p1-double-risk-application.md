---
status: complete
priority: p1
issue_id: "108"
tags: [architecture, correctness, risk, code-review]
dependencies: []
---

# Double Risk Application in ForexStrategyScanner

## Problem Statement

`ForexStrategyScanner` creates its own `RiskEngine` (line 109) AND the inner `ForexOpportunityScreener` also creates one (via `BaseOpportunityScreener.__post_init__()` at base.py:166). When `show_risk=True`, `_rank_opportunities()` applies SL/TP/position sizing on the inner screener's data, and then `ForexStrategyScanner.scan()` applies it AGAIN on line 212. This corrupts position sizing calculations.

## Findings

- `tvscreener/lib/screeners/forex_strategy.py:109` — Creates `RiskEngine(self.config.to_risk_config())`
- `tvscreener/lib/screeners/forex_strategy.py:212` — Calls `self._risk_engine.apply(combined)`
- `tvscreener/lib/screeners/base.py:166` — Inner screener creates its own RiskEngine
- `tvscreener/lib/screeners/base.py:354-355` — Inner screener applies risk in `_rank_opportunities()`
- `tvscreener/lib/screeners/forex_strategy.py:94-107` — Inner ForexScreenerConfig may have `show_risk=True`
- Result: SL calculated twice = double ATR distance, TP calculated twice = quadrupled reward

## Proposed Solutions

### Option 1: Disable Risk on Inner Screener (Quick Fix)

**Approach:** Set `show_risk=False` on the `ForexScreenerConfig` passed to the inner screener at line 94-107. Let the strategy scanner own risk application.

**Pros:**
- Minimal change (1 line)
- Correctly separates concerns

**Cons:**
- Fragile — someone could re-enable it later

**Effort:** 5 minutes

**Risk:** Low

---

### Option 2: Remove RiskEngine from Strategy Scanner, Let Inner Own It

**Approach:** Remove `self._risk_engine` from `ForexStrategyScanner` and don't call `apply()` at line 212. Let the inner screener handle all risk via `_rank_opportunities()`.

**Pros:**
- Single risk application point

**Cons:**
- Risk is applied before strategy filtering, so filtered-out pairs waste computation
- Strategy-specific risk logic can't be added later

**Effort:** 10 minutes

**Risk:** Low

## Recommended Action

**Option 2 — Remove RiskEngine from ForexStrategyScanner, let inner own it.** Delete `self._risk_engine` creation at line 109 and the `self._risk_engine.apply(combined)` call at line 212. The inner `ForexOpportunityScreener` will apply risk exactly once in `_rank_opportunities()`. Single risk application point, no duplication.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_strategy.py:72-109` — __post_init__
- `tvscreener/lib/screeners/forex_strategy.py:212` — risk application
- `tvscreener/lib/screeners/base.py:348-355` — _rank_opportunities

## Acceptance Criteria

- [ ] Risk (SL/TP/RR/Size) is applied exactly once in the pipeline
- [ ] Position sizing is correct (verified against manual calculation)
- [ ] `show_risk=True` produces same SL/TP whether using opportunity or strategy scanner

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (architecture-strategist agent)

**Actions:**
- Traced RiskEngine instantiation in both strategy scanner and inner opportunity screener
- Confirmed double application when show_risk=True
- Identified that inner ForexScreenerConfig receives show_risk from the strategy config
