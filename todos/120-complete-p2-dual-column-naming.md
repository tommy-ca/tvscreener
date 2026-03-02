---
status: complete
priority: p2
issue_id: "120"
tags: [patterns, naming, code-review]
dependencies: []
---

# Dual Column Naming Regime Requires Fallback Lookups

## Problem Statement

Raw API columns (`Recommend All|240`) and canonical names (`TREND_240`) coexist at runtime. Strategy detection uses raw names, renderers need dual-lookup fallbacks (`row.get(f"TREND_{tf}", row.get(f"Recommend All|{tf}", 0))`), appearing 6+ times.

## Findings

- `tvscreener/lib/screeners/forex_strategy.py:287-289` — Uses raw column names for strategy detection
- `tvscreener/lib/screeners/renderers/rich_console.py:209-212,244-245,294-297,495-498` — 6 dual-lookup fallbacks
- `tvscreener/lib/screeners/transformer.py` — Renames columns, but only in `_prepare_enriched_data()`

## Proposed Solutions

### Option 1: Normalize Columns Immediately After Fetch

**Approach:** Apply `DataTransformer.rename_technical_columns()` right after `_fetch_all_data()` returns, before scoring. Then all downstream code uses canonical names only.

**Effort:** 1-2 hours (must update strategy detection column references)
**Risk:** Medium (many column name references to update)

### Option 2: Keep Dual Names, Extract Lookup Helper

**Approach:** Create `get_col(row, canonical, raw)` helper to eliminate the repetitive fallback pattern.

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

**Option 2 — Extract lookup helper.** Create `get_col(row, canonical, raw)` helper to eliminate the 6 repetitive dual-lookup fallback patterns. Lower risk than full normalization; can be upgraded later.

## Acceptance Criteria

- [ ] No dual-lookup fallback patterns in renderers
- [ ] Column naming is consistent throughout pipeline

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (pattern-recognition-specialist)
