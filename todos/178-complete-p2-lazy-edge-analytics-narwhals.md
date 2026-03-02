---
status: complete
priority: p2
issue_id: "178"
tags: [architecture, narwhals, duckdb, analytics]
dependencies: ["170", "177"]
---

# Implement Lazy Edge Analytics with Narwhals

## Problem Statement
The `AnalyticsPipeline` should maintain laziness even when interleaving Python logic. We want to avoid materializing data to Pandas if the next step is another SQL query.

## Findings
- Narwhals can wrap `duckdb.Relation` objects lazily.
- Transformations are translated into SQL under the hood.

## Proposed Solutions
1. **Narwhals-DuckDB Bridge**: In `AnalyticsPipeline.transform()`, if the current relation is DuckDB, wrap it in Narwhals and return the resulting relation.
2. **Deferred Materialization**: Only call `.collect()` or `.df()` at the very end of the CLI output stage.

## Recommended Action
Ensure the analytics pipeline remains lazy through SQL -> Python -> SQL transitions.

## Acceptance Criteria
- [ ] `transform()` steps don't trigger immediate computation.
- [ ] Chained operations execute as a single optimized DuckDB plan.

## Work Log
### 2026-03-02 - Initial Creation
- Part of "Edge Analytics" audit.
