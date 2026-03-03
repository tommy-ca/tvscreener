---
title: Rerun Forex Scanners and Validate EdgeQuery
type: runbook
date: 2026-03-03
---

# Rerun Forex Scanners and Validate EdgeQuery

## Purpose

Rerun forex opportunity/strategy scanners for majors and minors using the matrix view, then validate that DuckDB `EdgeQueryClient` can query Iceberg tables correctly.

## Commands

```bash
uv run tvscreener-scan --scanner opportunity --universe majors --matrix
uv run tvscreener-scan --scanner opportunity --universe minors --matrix
uv run tvscreener-scan --scanner strategy --universe majors --matrix
uv run tvscreener-scan --scanner strategy --universe minors --matrix
```

## Validate Iceberg via EdgeQueryClient

```bash
uv run tvscreener-scan query tvscreener.gold --sql "SELECT signal_date, PAIR, DIRECTION, ENSEMBLE_SCORE, TOTAL_CONFLUENCE, GRID_ALIGNED, GRID_TOTAL, TF_CONFLUENCE_LONG, TF_CONFLUENCE_SHORT FROM df ORDER BY signal_date DESC LIMIT 25" --head 25
```

Key expectations:

- Queries against Iceberg identifiers like `tvscreener.gold` work without requiring `exports/*.parquet`.
- The matrix output can be reproduced from `tvscreener.gold` (direction, confluence counters, ensemble score).

## Tests

```bash
uv run pytest tests/test_analytics_pipeline.py -v
uv run pytest tests/unit/test_forex_opportunity.py tests/unit/test_forex_strategy.py -v
```

## Notes

- Iceberg tables are queried through `EdgeQueryClient.get_relation()` using `table.scan().to_arrow()` (not `table.to_arrow()`).
