---
status: complete
priority: p1
issue_id: "107"
tags: [architecture, correctness, duckdb, code-review]
dependencies: []
---

# post_filters Not Applied in Data Pipeline (Leaky Abstraction)

## Problem Statement

The DuckDB `post_filters` pipeline (set via `--filter` or `--sql`) only runs inside `_prepare_enriched_data()`, which is called during **export and print_summary**. The `get_opportunities()` and `ForexStrategyScanner.scan()` methods return **unfiltered data**. This means API/MCP consumers see different data than what appears on screen.

This was identified as a known risk in the plan document but was implemented incorrectly.

## Findings

- `tvscreener/lib/screeners/base.py:86-91` — post_filters applied in `_prepare_enriched_data()` (export/render path)
- `tvscreener/lib/screeners/base.py:206-232` — `get_opportunities()` does NOT apply post_filters
- `tvscreener/lib/orchestrator.py:329` — `results` variable holds unfiltered data
- `tvscreener/lib/orchestrator.py:331-336` — confluence filtering operates on unfiltered results
- MCP `scan_opportunities()` returns `results` directly — always unfiltered
- Terminal output and file exports show filtered data (via `_prepare_enriched_data()`)

## Proposed Solutions

### Option 1: Apply post_filters in get_opportunities() (Recommended)

**Approach:** Move the post_filters loop from `_prepare_enriched_data()` into `get_opportunities()`, after scoring but before caching. Do the same for `ForexStrategyScanner.scan()`.

**Pros:**
- All consumers (CLI, MCP, Python API) get the same filtered data
- Eliminates the "leaky abstraction" bug
- `_prepare_enriched_data()` focuses only on column renaming/visual enrichment

**Cons:**
- Post-filter results are cached, so changing filters requires a new scan
- Must handle DuckDB relation → DataFrame materialization at the pipeline boundary

**Effort:** 1 hour

**Risk:** Medium (requires testing all downstream paths)

---

### Option 2: Keep post_filters in _prepare_enriched_data() but Cache the Filtered Result

**Approach:** Have `_prepare_enriched_data()` cache its result and have `get_opportunities()` return the enriched/filtered data.

**Pros:**
- Less structural change

**Cons:**
- Still mixes filtering and presentation concerns in one method
- Doesn't cleanly solve the API return value issue

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

**Option 1 — Move post_filters into get_opportunities() / scan().** Move the post_filters loop from `_prepare_enriched_data()` into `get_opportunities()` (after scoring, before caching) and mirror in `ForexStrategyScanner.scan()`. `_prepare_enriched_data()` should only handle column renaming and visual enrichment. All consumers (CLI, MCP, Python API) will get identically filtered data.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/base.py:68-95` — _prepare_enriched_data
- `tvscreener/lib/screeners/base.py:206-232` — get_opportunities
- `tvscreener/lib/screeners/forex_strategy.py:130-236` — scan()

## Resources

- **PR:** #49
- **Plan:** `docs/plans/2026-03-01-feat-duckdb-mtf-filter-pipeline-plan.md` (lines 19-22)

## Acceptance Criteria

- [ ] `get_opportunities()` returns filtered data when post_filters are set
- [ ] `ForexStrategyScanner.scan()` returns filtered data when post_filters are set
- [ ] MCP scanner tools return filtered data
- [ ] Terminal output and API return identical results
- [ ] `_prepare_enriched_data()` only handles column renaming/visual enrichment

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (architecture-strategist agent)

**Actions:**
- Traced data flow from CLI through orchestrator to screener to renderer
- Confirmed post_filters only run in the export/render path
- Verified MCP returns unfiltered data
- Cross-referenced with plan document which identified this exact risk

**Learnings:**
- The plan warned about "leaky abstraction" but the fix was placed in the wrong method
- ExportMixin._prepare_enriched_data() is doing too much (filtering + renaming)
