# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
title: "feat: Implement DuckDB MTF Filter Pipeline"
type: feat
date: 2026-03-01
---

> Status note (as of 2026-03-04): DuckDB is now positioned primarily as an **edge analytics engine**
> (`EdgeQueryClient`) querying **Iceberg identifiers** (materialized to Arrow) with hardened config.
> This plan remains useful for the *MTF shorthand parser / composition model*, but “in-flight SQL
> filtering during scans” should be treated as optional and must not be required for producing
> canonical Iceberg medallion outputs.

## Enhancement Summary

**Deepened on:** 2026-03-01
**Sections enhanced:** 4
**Research agents used:** framework-docs-researcher, best-practices-researcher, performance-oracle, architecture-strategist, security-sentinel, kieran-python-reviewer

### Key Improvements
1. **Security Sandboxing:** Configured DuckDB with strict limits (`enable_external_access=False`, memory limits) to prevent local system compromise or DoS via arbitrary SQL.
2. **Performance Optimization:** Prevented materialization overhead by either combining SQL strings or using DuckDB's Relational API instead of executing sequential Pandas copies.
3. **Robust Expression Parsing:** Replaced naive regex ideas with `pyparsing` to correctly handle nested boolean logic (AND/OR) and parentheses.
4. **Strict Typing & Architecture:** Moved the filter pipeline to `BaseOpportunityScreener.get_opportunities()` to avoid state inconsistencies, and defined a strict `DataFrameFilter` Protocol.

### New Considerations Discovered
- Placing filters in `ExportMixin` causes a "leaky abstraction" where `get_opportunities()` returns unfiltered data while exports/UI return filtered data. Filters must apply earlier in the lifecycle.
- Implicit `duckdb.query(df)` creates significant overhead via replacement scans; explicitly registering views is required for pipelines.
- Raw SQL execution introduces severe local system risks (like `read_csv('/etc/passwd')`) that must be disabled at the connection level.

# Implement DuckDB MTF Filter Pipeline

## Overview

We are building a robust, flexible engine that allows users to define custom filtering logic across multiple timeframes simultaneously. Powering this is a high-performance **DuckDB** backend that enables complex relational querying on top of live TradingView data. To avoid the "Inheritance Trap" (creating brittle `MTFScanner` or `SQLScanner` subclasses), we will implement DuckDB as a composable **Post-Fetch Filter Pipeline** integrated directly into the `BaseOpportunityScreener`.

### Research Insights

**Best Practices:**
- Use a `Protocol` instead of raw `Callable` for the pipeline filters to ensure strict type boundaries.
- The `DuckDBFilter` should be a Callable class (Strategy pattern) that encapsulates the connection lifecycle.

**Architecture Considerations:**
- Avoid the "Mixin Trap" by properly annotating `_post_filters` in the base class and applying it in `get_opportunities()` rather than `_prepare_enriched_data()`. This ensures programmatic users and CLI users get the exact same dataset.

**Implementation Details:**
```python
from typing import Protocol
import pandas as pd

class DataFrameFilter(Protocol):
    """Protocol for post-fetch data filters."""
    def __call__(self, df: pd.DataFrame) -> pd.DataFrame: ...
```

## Problem Statement / Motivation

Professional traders often use "Waterfall" or "Triple Screen" logic (e.g., Daily trend + Hourly momentum + 15m entry). Currently, our system requires writing custom Python logic for every new strategy. 

Furthermore, our codebase research revealed a disconnect bug: existing filters in `ScreenerController` (like `_filter_by_confluence`) filter the DataFrame returned to the orchestrator, but the terminal UI renderer (`print_summary`) and exporters fetch their data from `screener._prepare_enriched_data()`, effectively bypassing the controller's filters. 

We need a unified way to filter the enriched data *before* it hits the UI or exporters, and we need that filter to be powerful enough to handle cross-timeframe conditions.

## Proposed Solution

1.  **DuckDB Filter Step**: Create a `DuckDBFilter` class that accepts a SQL string, registers the enriched Pandas DataFrame as an in-memory view, and executes the query.
2.  **Filter Pipeline**: Introduce a `_post_filters` list on `BaseOpportunityScreener`. Update the execution lifecycle to sequentially apply these filters.
3.  **Expression Parser**: Build a translator using `pyparsing` that converts user-friendly shorthand (e.g., `1D:RSI < 30 AND (1H:RSI < 40 OR 4H:TREND > 0)`) into valid DuckDB SQL.
4.  **UI Resilience**: Catch `duckdb.BinderException` (e.g., querying a column that wasn't fetched) and gracefully degrade the UI if a complex SQL query alters the expected schema (e.g., `GROUP BY`).

### Research Insights

**Best Practices:**
- For building the DSL parser, avoid Regular Expressions as they cannot handle nested logic or parentheses. Use `pyparsing` for a lightweight, dependency-free-like implementation.

**Implementation Details:**
```python
from pyparsing import Word, alphas, nums, Combine, Literal, infixNotation, opAssoc, pyparsing_common

# Example Pyparsing setup for nested MTF logic
timeframe = Combine(Word(nums) + Word(alphas))
indicator = Word(alphas)
operator = Literal("<") | Literal(">") | Literal("=")
```

## Technical Approach

### Architecture

The architecture will leverage DuckDB's zero-copy integration with Pandas. 
The filter will hook into the existing lifecycle:
`Raw TV Data` -> `Ranking` -> `DataTransformer (Standardized Columns)` -> `DuckDBFilter (SQL Evaluation)` -> `Cache`.

### Implementation Phases

#### Phase 1: Foundation (Pipeline & Engine)

- **Tasks**:
  - Add `_post_filters: list[DataFrameFilter]` to `BaseOpportunityScreener`.
  - Update `BaseOpportunityScreener.get_opportunities()` to loop through `_post_filters` (after enforcing standard column names via `DataTransformer`).
  - Create `tvscreener/lib/screeners/filters.py` with a `DuckDBFilter` class.
- **Success criteria**:
  - A dummy filter can be appended to a screener and correctly modifies the terminal output and CSV exports.

#### Phase 2: Timeframe Mapping & Expression Parser

- **Tasks**:
  - Create a mapping dictionary for shorthand timeframes (e.g., `1D` -> `1440`, `4H` -> `240`).
  - Implement `MTFExpressionParser` using `pyparsing` to compile strings into standard SQL clauses like `TREND_1440 > 0`.
  - Wire `--filter` and `--sql` CLI arguments in `cli.py` and `orchestrator.py` to append a `DuckDBFilter` to the screener.
- **Success criteria**:
  - CLI shorthand correctly filters the resulting table based on actual DataFrame columns.

#### Phase 3: Resilience & Polish

- **Tasks**:
  - Wrap DuckDB executions in `try/except` blocks. If `duckdb.BinderException` occurs, raise a `FilterExecutionError` with a friendly CLI error.
  - Update `RichConsoleRenderer.render()`. If the filtered DataFrame is missing required canonical columns (`PAIR`, `DIRECTION`), fallback to `self._render_generic()`.
- **Success criteria**:
  - Aggregation queries (`SELECT EXCHANGE, COUNT(*)`) render cleanly as a generic table.

### Research Insights

**Security Considerations:**
- Arbitrary SQL execution is dangerous. DuckDB must be initialized as an untrusted sandbox.
- **Required mitigations:**
  ```python
  con = duckdb.connect(':memory:', config={
      'enable_external_access': False,
      'allow_unsigned_extensions': False,
      'autoinstall_known_extensions': False
  })
  con.execute("PRAGMA memory_limit='1GB'")
  ```

**Performance Considerations:**
- Avoid sequential Pandas materialization (`.df()`) if multiple filters exist.
- Always use explicit `con.register("signals", df)` instead of implicit `duckdb.query()` to eliminate replacement scan overhead.

**Edge Cases:**
- Schema mutations (like `GROUP BY`) will drop canonical columns. `RichConsoleRenderer` must use `df.get("PAIR")` safely to avoid `KeyError` crashes.

## Alternative Approaches Considered

- **Subclassing (`MTFScanner`)**: Rejected. Creating a separate scanner class duplicates fetching logic and violates the Single Responsibility Principle. Composition allows *any* existing scanner to benefit from SQL filtering.
- **Pandas `query()`**: Rejected. Pandas `query` is powerful but lacks the full relational capabilities of DuckDB (e.g., window functions, complex CASE statements).
- **Regex Parsing**: Rejected. Regex cannot handle nested boolean conditions. Replaced with `pyparsing`.

## Acceptance Criteria

### Functional Requirements

- [ ] Users can filter any scan using raw SQL via `--sql "SELECT * FROM signals WHERE ..."`
- [ ] Users can filter using MTF shorthand via `--filter "1D:RSI < 30 AND 4H:TREND > 0"`
- [ ] Filtered data is correctly reflected in the terminal UI, Parquet, and CSV exports.

### Non-Functional Requirements

- [ ] DuckDB executes queries on Pandas DataFrames without copying memory (zero-copy).
- [ ] DuckDB connection is sandboxed (no external file access).
- [ ] UI does not crash if a SQL query changes the DataFrame schema.

### Quality Gates

- [ ] Unit tests for `MTFExpressionParser` cover complex AND/OR logic.
- [ ] Unit tests for `DuckDBFilter` verify SQL execution and sandboxing.
- [ ] The existing confluence disconnect bug is fixed.

## Success Metrics

- Users can execute complex cross-timeframe filters via CLI without writing Python code.
- Zero increase in API fetching latency.

## Dependencies & Risks

- **Dependency**: `duckdb` (already added), `pyparsing` (needs to be added).
- **Risk**: DuckDB is a C++ bound library. Unhandled memory issues in raw SQL could cause segfaults. Mitigation: Enforce strict connection sandboxing and memory limits.

## References & Research

### Internal References
- Architecture pivot decision: `docs/brainstorms/2026-03-01-mtf-generic-screener-requirements.md`
- Disconnect bug in filtering: `tvscreener/lib/orchestrator.py:320` and `tvscreener/lib/screeners/base.py:65`

### External References
- DuckDB Python API: [SQL on Pandas](https://duckdb.org/docs/guides/python/sql_on_pandas.html)
- Pyparsing Docs: [Pyparsing Github](https://github.com/pyparsing/pyparsing)
