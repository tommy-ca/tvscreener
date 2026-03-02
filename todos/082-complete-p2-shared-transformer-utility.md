---
status: completed
priority: p2
issue_id: "082"
tags: [architecture, refactoring, normalization]
dependencies: []
---

# Duplicated enrichment and renaming logic

Extract shared data normalization and renaming logic into a dedicated transformer utility.

## Problem Statement

Renaming TradingView technical factors (e.g., `Recommend All|15` to `TREND_15`) and normalizing symbol/exchange metadata is currently scattered across multiple classes. `ExportMixin` has one implementation, while `ForexOpportunityScreener` and potentially others have their own overrides or additional logic. This duplication makes it difficult to maintain consistent column names and logic across different asset types and export formats.

## Findings

- `tvscreener/lib/screeners/base.py:54-103` (`_prepare_enriched_data`) contains hardcoded renaming for technical factors.
- `tvscreener/lib/screeners/forex_opportunity.py:199-249` (`_merge_duplicates`) contains complex regex-based symbol extraction and exchange prioritization.
- `tvscreener/lib/screeners/forex_opportunity.py:289-301` overrides enrichment to add strength signs.
- Similar patterns likely exist in strategy classes and other opportunity screeners.

## Proposed Solutions

### Option 1: Shared Transformer Utility

**Approach:** Create `tvscreener/lib/screeners/transformer.py` containing a `DataTransformer` class or a set of pure functions that handle:
1. Column renaming (Standard factors, ATR, RSI).
2. Symbol/Pair normalization.
3. Feature enrichment (Grade calculation, strength signs).
4. Metadata injection.

**Pros:**
- Single source of truth for data representation.
- Easier to test in isolation.
- Decouples screener logic from data presentation/export logic.

**Cons:**
- Requires refactoring multiple classes to use the new utility.

**Effort:** 4-6 hours

**Risk:** Low

---

### Option 2: Enhanced Mixin

**Approach:** Move more logic into `ExportMixin` and use hooks for subclass-specific behavior.

**Pros:**
- Keeps logic within the screener hierarchy.

**Cons:**
- Still leads to "fat" base classes/mixins.
- Harder to reuse logic outside of the screener context.

**Effort:** 2-3 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/base.py`
- `tvscreener/lib/screeners/forex_opportunity.py`
- `tvscreener/lib/screeners/forex_strategy.py`

## Acceptance Criteria

- [x] `tvscreener/lib/screeners/transformer.py` created.
- [x] Technical factor renaming moved to the transformer.
- [x] Symbol/Pair normalization logic moved to the transformer.
- [x] Duplicate logic removed from `base.py` and `forex_opportunity.py`.
- [x] All export formats (CSV, JSON, Excel) use the same transformed data.

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Antigravity

**Actions:**
- Identified fragmented renaming logic across `ExportMixin` and `ForexOpportunityScreener`.
- Noticed complex regex in `_merge_duplicates` that should be shared.
- Drafted proposal for a dedicated transformer utility.

## Notes

- The transformer should be configurable with timeframe lists and asset-specific rules.
