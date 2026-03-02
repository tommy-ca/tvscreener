---
status: complete
priority: p2
issue_id: "119"
tags: [performance, renderer, code-review]
dependencies: []
---

# Redundant _prepare_enriched_data() Call in Strategy Detailed Renderer

## Problem Statement

`_render_strategy_detailed()` calls `screener._prepare_enriched_data()` a second time (line 464), even though it was already called via the `print_summary` -> `df_getter()` pipeline. The enriched `df` parameter is the correct data. This doubles the computation.

## Findings

- `tvscreener/lib/screeners/renderers/rich_console.py:464` — Second call to `_prepare_enriched_data()`
- `tvscreener/lib/screeners/export_helpers.py:70` — First call via `df = df_getter()`
- The `df` parameter passed to the render callback IS the enriched data

## Proposed Solutions

### Option 1: Use the Already-Enriched df Parameter

**Approach:** Replace `enriched_df = screener._prepare_enriched_data()` with `enriched_df = df`.

**Effort:** 2 minutes
**Risk:** None

## Recommended Action

**Use the already-enriched df parameter.** Replace `enriched_df = screener._prepare_enriched_data()` with `enriched_df = df` at line 464.

## Acceptance Criteria

- [ ] `_prepare_enriched_data()` called exactly once per render cycle
- [ ] Detailed strategy view renders correctly

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (performance-oracle)
