---
status: complete
priority: p2
issue_id: "180"
tags: [architecture, duckdb, quantitative]
dependencies: ["138"]
---

# Implement Advanced DuckDB TA Macros

## Problem Statement
We have basic SMA macros. To enable complex edge analytics (e.g. signal quality auditing), we need more powerful in-database indicators like RSI and Z-Score.

## Findings
- RSI calculation involves recursive smoothing (Wilder's), which is complex in pure SQL but doable via DuckDB window functions.
- Z-Score is native relational algebra.

## Proposed Solutions
1. **Register Macros**: Add `rsi(v, p)`, `atr(h, l, c, p)`, and `z_score(v, p)` to `EdgeQueryClient`.
2. **Analytics Use Case**: Allow users to run `SELECT PAIR FROM df WHERE rsi(price, 14) < 30`.

## Recommended Action
Expand the DuckDB macro library to support standard technical indicators.

## Acceptance Criteria
- [ ] RSI and ATR macros registered in the edge connection.
- [ ] Macros match Narwhals/Pandas output precision.

## Work Log
### 2026-03-02 - Initial Creation
- Part of "Edge Analytics" audit.
