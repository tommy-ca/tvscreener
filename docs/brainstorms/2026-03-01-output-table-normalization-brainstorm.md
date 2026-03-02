---
date: 2026-03-01
topic: output-table-normalization
---

# Cleanup, Normalize, and Prettify Output Signal Tables

## What We're Building

A unified, consistent output system across both the opportunity and strategy scanners so that all views (summary, detailed, matrix) share the same visual language, column conventions, and emoji system — regardless of which scanner produced the results.

Currently the two scanners evolved independently and their output tables have diverged in structure, column naming, emoji usage, and available views. This brainstorm identifies all the gaps and proposes a phased approach to normalize them.

## Current State Audit

### Opportunity Scanner — 3 views

| View | Columns | Notes |
|------|---------|-------|
| **Summary** | Rank, Pair, Direction(🟢), Ensemble, Confluence(n/12), TF(n/3), Factor(n/4), Grade | Clean and complete |
| **Detailed** | Per-pair TF×Factor grid, `value emoji` cells, footer stats | Clean and complete |
| **Matrix** | Pair, Dir(🟢), TREND/MA/OSC/ROC single-emoji grids, Grid(n/12), Grade | Clean and complete |

### Strategy Scanner — 1 view only

| View | Columns | Notes |
|------|---------|-------|
| **Summary** | Pair, Direction(🟢🟢), Confluence(int) | Grouped by strategy type |
| **Detailed** | ❌ Not implemented | |
| **Matrix** | ❌ Not implemented | |

### Inconsistencies Identified

| # | Issue | Opportunity | Strategy | Impact |
|---|-------|-------------|----------|--------|
| 1 | **Missing views** | summary + detailed + matrix | summary only | Strategy can't show per-TF factor breakdown |
| 2 | **Confluence scoring** | Grid-based 0-12 (TF×Factor) | Simple integer (1-5) | Can't compare across scanners |
| 3 | **Column structure varies by strategy** | Fixed columns | Confluence strategy shows Pattern/Score/MR; others just Confluence | Inconsistent mental model |
| 4 | **No Rank column** | Has Rank | No rank | Strategy results lack ordering signal |
| 5 | **No Ensemble score** | Has Ensemble | N/A | Strategy doesn't produce an ensemble score |
| 6 | **No Grade** | Has Grade (A+ → F) | N/A | Strategy lacks quality tier |
| 7 | **`print_summary()` signature mismatch** | `(detailed, matrix)` kwargs | `(limit)` kwarg only | Orchestrator can't pass `--detailed`/`--matrix` to strategy |
| 8 | **Direction emoji logic split** | `_direction_emoji()` + `_get_strength_sign()` + `_matrix_sign()` in opportunity | `_get_strength_sign()` only in strategy | Strategy lacks `_direction_emoji()` and `_matrix_sign()` |
| 9 | **`_get_strength_sign()` semantics differ** | Threshold-based (value magnitude) | Score-based (integer 1-3) | Same method name, different behavior |
| 10 | **No TF/Factor confluence in strategy** | TF_CONFLUENCE, FACTOR_CONFLUENCE | N/A | Missing supplementary confluence info |
| 11 | **Strategy table title** | `"Forex Opportunities"` | `"Strategy: {name}"` per group | Different title pattern |
| 12 | **Limit defaults differ** | head(20) for summary, head(10) for detailed, head(15) for matrix | configurable `limit` (default 20) | Inconsistent truncation |

## Why This Approach

### Approach A: Normalize Strategy Views to Match Opportunity (Recommended)

Add `--detailed` and `--matrix` support to the strategy scanner, reusing as much rendering logic as possible from opportunity. Keep the strategy-specific grouping (by strategy type) but add the same TF×Factor grid infrastructure.

**Pros:**
- Users get consistent visual language across both scanners
- Grid confluence (0-12) replaces opaque integer scores
- Same emoji system everywhere
- `--matrix` becomes the universal "at a glance" view

**Cons:**
- Strategy confluence scoring needs rethinking — current integer is simple but useful
- Some strategy views (like confluence pattern names) are strategy-specific and don't map to opportunity

**Best when:** Building a consistent multi-scanner tool where users switch between scanners frequently.

### Approach B: Extract Shared Rendering into Base Class

Pull all shared rendering (emoji methods, table builders, column definitions) into `base.py` or a new `rendering.py` module. Each scanner overrides only what's specific.

**Pros:**
- DRY — no duplicated emoji/rendering code
- Single source of truth for column styles, widths, emoji thresholds
- Easier to add new scanners in future

**Cons:**
- More complex class hierarchy
- Rendering code mixed with data logic in base class
- Requires careful design to avoid over-abstraction

**Best when:** Planning to add more asset-type scanners (crypto, stocks, commodities).

### Approach C: Combined A + B (Full Normalization)

Normalize strategy views (A) by extracting shared rendering into base (B). This is the most thorough but largest change.

**Best when:** Willing to invest the time for a clean architecture that scales.

## Key Decisions

- **Approach A (Recommended)**: Normalize strategy output to match opportunity, keeping extraction (B) as a follow-up if more scanners are added
- **Grid confluence for strategy**: The strategy scanner's integer CONFLUENCE_SCORE (1-5) serves a different purpose than the grid — it measures how many strategy conditions passed, not TF×Factor alignment. Keep both: show the strategy-specific score AND add grid confluence from the underlying opportunity data
- **`print_summary()` unification**: Strategy's `print_summary()` should accept `detailed` and `matrix` kwargs to match opportunity
- **Emoji methods**: Copy `_direction_emoji()` and `_matrix_sign()` to strategy (or better: move to base class)
- **Limit defaults**: Standardize to head(20) for summary, head(15) for matrix, head(10) for detailed across both scanners

## Scope — Individual Work Items

### P1 — Critical (Functional gaps)

1. **068**: Add `--detailed` view to strategy scanner
   - Show per-pair TF×Factor grid (reuse opportunity's detailed rendering pattern)
   - Show strategy-specific fields (strategy name, confluence pattern) in header

2. **069**: Add `--matrix` view to strategy scanner
   - Show TF×Factor emoji grid per pair
   - Group by strategy type (as current summary does)

3. **070**: Unify `print_summary()` signature
   - Strategy scanner accepts `detailed` and `matrix` kwargs
   - Orchestrator passes them through in `run_strategy_scan()`

### P2 — Important (Consistency)

4. **071**: Extract shared emoji methods to base class
   - Move `_direction_emoji()`, `_matrix_sign()`, `_get_strength_sign()` to `BaseOpportunityScreener` or `ExportMixin`
   - Strategy and opportunity both inherit, override only when semantics differ

5. **072**: Add grid confluence to strategy results
   - Strategy scanner already has access to underlying opportunity data (`raw_data` from `_screener.get_opportunities()`)
   - Calculate GRID_ALIGNED, GRID_PCT, GRADE, TF_CONFLUENCE, FACTOR_CONFLUENCE
   - Display alongside strategy-specific CONFLUENCE_SCORE

6. **073**: Normalize summary table columns
   - Add Rank column to strategy summary
   - Add Grade column to strategy summary
   - Standardize column widths and styles across both scanners

### P3 — Nice-to-have (Polish)

7. **074**: Standardize truncation limits
   - summary: head(20), detailed: head(10), matrix: head(15) for both scanners
   - Add `--limit` CLI arg to override

8. **075**: Add legend/footer consistency
   - Matrix view: both scanners show `Legend: 🟢=Bullish 🔴=Bearish ⚪=Neutral`
   - Summary view: both show total count footer

## Open Questions

- Should strategy's `--detailed` view show risk management fields (SL/TP/RR/Position Size)? Currently those are computed but only exported to parquet.
- Should the confluence strategy's Pattern and MR_EXTREMITY columns appear in the detailed view or remain summary-only?
- When showing grid confluence for strategy results, should we recalculate from the underlying data or just pass through from the opportunity scanner?

## Next Steps

→ Create file-todos 068-075 from the scope items above
→ Implement P1 items first (068-070), then P2 (071-073), then P3 (074-075)
