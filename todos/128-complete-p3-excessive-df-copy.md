---
status: complete
priority: p3
issue_id: "128"
tags: [performance, pandas, code-review]
dependencies: []
---

# Excessive DataFrame .copy() Calls (9-10 per Pipeline Run)

## Problem Statement

A single scan pipeline triggers 9-10 full DataFrame copies. Most filter functions copy twice: once to add a temp column, once to filter. Boolean indexing already returns new DataFrames, making many `.copy()` calls redundant.

## Findings

- `tvscreener/score.py:290` — 1 copy in rank_opportunities
- `tvscreener/lib/screeners/risk_utils.py:38` — 1 copy in RiskEngine.apply
- `tvscreener/lib/screeners/filter_utils.py:14,26-28,40-42` — 5 copies across filter functions
- `tvscreener/lib/screeners/base.py:70` — 1 copy in _prepare_enriched_data
- `tvscreener/lib/screeners/forex_strategy.py:559-566` — 3 `.copy()` after boolean indexing

## Proposed Solutions

### Option 1: Copy-on-Entry Convention

**Approach:** Only the top-level public method copies. Internal methods use `copy=False`. Remove `.copy()` after boolean indexing.

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

**Copy-on-entry convention.** Only top-level public methods copy. Remove `.copy()` after boolean indexing. Target 2-3 copies per pipeline run.

## Acceptance Criteria

- [ ] No more than 2-3 copies per pipeline run
- [ ] Filter functions use boolean masks without intermediate copies
- [ ] All tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (performance-oracle)
