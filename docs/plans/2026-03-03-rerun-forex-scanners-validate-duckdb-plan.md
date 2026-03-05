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
# (Recommended) Split mode: run data pipelines, then rerun analytics from Iceberg.

# 1) Data pipelines (fetch + persist to Iceberg)
uv run tvscreener-scan --scanner opportunity --pipeline data --universe majors
uv run tvscreener-scan --scanner opportunity --pipeline data --universe minors

# 2) Analytics pipelines (query Iceberg + render the same matrix view)
uv run tvscreener-scan --scanner opportunity --pipeline analytics --universe majors --matrix --limit 100
uv run tvscreener-scan --scanner opportunity --pipeline analytics --universe minors --matrix --limit 100

# Strategy is an analytics pipeline over Iceberg-backed Gold rows
uv run tvscreener-scan --scanner strategy --pipeline analytics --universe majors --matrix --limit 100
uv run tvscreener-scan --scanner strategy --pipeline analytics --universe minors --matrix --limit 100

# (Optional) One-shot mode: data then analytics in one command
uv run tvscreener-scan --scanner opportunity --pipeline both --universe majors --matrix --limit 100
uv run tvscreener-scan --scanner opportunity --pipeline both --universe minors --matrix --limit 100
```

## Validate Iceberg via EdgeQueryClient

```bash
# NOTE: `query` must be the first token after `tvscreener-scan`.
# If you pass `--config`, place it at the end.
uv run tvscreener-scan query tvscreener.gold --sql "SELECT signal_date, PAIR, DIRECTION, ENSEMBLE_SCORE, TOTAL_CONFLUENCE, GRID_ALIGNED, GRID_TOTAL, TF_CONFLUENCE_LONG, TF_CONFLUENCE_SHORT FROM df ORDER BY signal_date DESC LIMIT 25" --head 25 --config tvscreener.yaml
```

Key expectations:

- Queries against Iceberg identifiers like `tvscreener.gold` work without requiring any repository-local parquet snapshots.
- The matrix output can be reproduced from `tvscreener.gold` (direction, confluence counters, ensemble score).

## Optional: write a local snapshot (non-canonical)

If you need an on-disk artifact for debugging, write it explicitly via `--output`:

```bash
uv run tvscreener-scan --scanner opportunity --universe majors --matrix --output ./snapshots/majors_opportunity.parquet
```

This snapshot is not required for the validation steps above and must not be treated as the source of truth.

## Tests

```bash
uv run pytest tests/test_analytics_pipeline.py -v
uv run pytest tests/unit/test_forex_opportunity.py tests/unit/test_forex_strategy.py -v
```

## Notes

- Iceberg tables are queried through `EdgeQueryClient.get_relation()` using `table.scan().to_arrow()` (not `table.to_arrow()`).
