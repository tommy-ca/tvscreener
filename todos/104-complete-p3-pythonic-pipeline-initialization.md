---
status: complete
priority: p3
issue_id: "104"
tags: [python, patterns, refactor]
dependencies: []
---

# Implement Pythonic Pipeline Initialization

## Problem Statement
The current plan proposes holding DuckDB connections as instance state and initializing the `_post_filters` list as an empty mutable array that is populated later. This violates Pythonic lifecycle management and dependency injection principles.

## Findings
- Kieran (Python Reviewer) noted that `DuckDBFilter` should use a context manager inside `__call__` rather than holding an open connection on the instance.
- The pipeline should be injected via `__init__` rather than appended to later.

## Proposed Solutions

### Option 1: Dependency Injection and Context Managers
**Approach:** 
1. Use `with duckdb.connect(...) as con:` strictly within the `DuckDBFilter.__call__` method.
2. Update `BaseOpportunityScreener` to accept `post_filters: list[DataFrameFilter] | None = None` in its constructor.

## Acceptance Criteria
- [ ] `DuckDBFilter` manages its connection lifecycle explicitly with a context manager.
- [ ] Filters are injected via the screener's constructor.