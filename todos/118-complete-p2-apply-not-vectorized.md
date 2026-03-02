---
status: complete
priority: p2
issue_id: "118"
tags: [performance, pandas, code-review]
dependencies: []
---

# .apply() in Hot Path Should Be Vectorized

## Problem Statement

`forex_opportunity.py:204` uses `.apply(lambda x: self._direction_emoji(x))` for row-by-row Python execution. The sister class `ForexStrategyScanner` already uses vectorized `np.select()` for the same logic.

## Findings

- `tvscreener/lib/screeners/forex_opportunity.py:204` — `.apply(lambda x: ...)`
- `tvscreener/lib/screeners/forex_strategy.py:592-604` — Vectorized `np.select()` equivalent

## Proposed Solutions

### Option 1: Replace with np.select()

**Approach:** Use `np.select()` matching the strategy scanner pattern.

**Effort:** 5 minutes
**Risk:** None

## Recommended Action

**Replace with np.select().** Copy the vectorized pattern from `forex_strategy.py:592-604` into `forex_opportunity.py:204`.

## Acceptance Criteria

- [ ] No `.apply()` on hot path for strength signs
- [ ] Output identical to current behavior

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (performance-oracle)
