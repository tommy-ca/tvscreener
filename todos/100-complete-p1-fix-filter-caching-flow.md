---
status: complete
priority: p1
issue_id: "100"
tags: [architecture, bug, mtf]
dependencies: []
---

# Fix Data Flow: Move Filter Pipeline AFTER Caching

## Problem Statement
The current architectural plan places the DuckDB filter pipeline *before* the data caching mechanism in `BaseOpportunityScreener.get_opportunities()`. This means the cache will store volatile, user-filtered state rather than the expensive, standardized base dataset. If a user runs a scan with `RSI < 30`, caches it, and then runs `RSI < 40`, they will suffer a cache miss and wait for network I/O again.

## Findings
- Architecture Strategist identified this severe data flow integrity violation.
- The pipeline flow must be: `Raw TV Data` -> `Ranking` -> `DataTransformer` -> **`Cache`** -> **`DuckDBFilter`**.

## Proposed Solutions

### Option 1: Apply Filters on Cache Retrieval
**Approach:** Refactor `get_opportunities` to save `self._cached_data` immediately after the `DataTransformer` step. Apply the `_post_filters` pipeline to a copy of the cached data *right before* returning it.
**Pros:** Ensures the cache always holds the full universe of fetched pairs.

## Acceptance Criteria
- [ ] Base dataset is fully cached before any `_post_filters` are applied.
- [ ] Changing `--sql` or `--filter` flags while using `--use-cache` results in instantaneous filtering without network requests.