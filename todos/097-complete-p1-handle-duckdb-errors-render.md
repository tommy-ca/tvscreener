---
status: complete
priority: p1
issue_id: "097"
tags: [duckdb, error-handling, rendering, ui]
dependencies: ["095"]
---

# Handle DuckDB Error Scenarios & Renderer Fallbacks

## Problem Statement

When using `SQLScanner` or `MTFScanner` with DuckDB, users can input complex or invalid SQL queries. If a query fails (e.g., syntax error, missing column because a timeframe wasn't fetched), it will throw raw `duckdb` exceptions. Furthermore, if a valid SQL query changes the DataFrame schema (e.g., aggregating rows or aliasing columns), it might break `RichConsoleRenderer._render_opportunity` which expects canonical columns like `PAIR` and `ENSEMBLE_SCORE`.

## Findings

- DuckDB throws `duckdb.ParserException` for bad syntax and `duckdb.BinderException` for missing columns.
- `RichConsoleRenderer._render_opportunity` blindly looks for specific keys. If missing, it uses defaults, but a `GROUP BY` query might completely alter the structure, making the output confusing or causing a crash elsewhere.
- `RichConsoleRenderer._render_generic` gracefully handles arbitrary schemas (up to 10 columns) and is ideal for custom SQL outputs.

## Proposed Solutions

### Option 1: Try/Catch wrappers and Smart Renderer Selection
1. Catch `duckdb.Error` in `DuckDBEngine.query()` or the scanner, and raise a custom `ScreenerFilterError` with a user-friendly CLI message (e.g., "Column TREND_1D not found. Did you include the 1D timeframe?").
2. In `SQLScanner` and `MTFScanner`, inspect the resulting DataFrame columns. If canonical columns (`PAIR`, `GRADE`, etc.) are missing, dynamically instruct `RichConsoleRenderer` to fallback to `_render_generic`.

**Effort:** 1-2 hours
**Risk:** Low (improves stability)

## Acceptance Criteria

- [ ] Invalid SQL syntax returns a clean, user-friendly CLI error.
- [ ] Querying a non-existent column clearly explains which column is missing.
- [ ] Arbitrary SQL aggregations (e.g., `SELECT EXCHANGE, COUNT(*)`) render correctly using the generic table format without crashing the application.
