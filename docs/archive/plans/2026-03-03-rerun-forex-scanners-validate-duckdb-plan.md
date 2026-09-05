# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
title: Rerun Forex Scanners and Validate EdgeQuery
type: runbook
date: 2026-03-03
---

# Rerun Forex Scanners and Validate EdgeQuery

## Purpose

Rerun forex opportunity/strategy scanners for majors and minors using the matrix view, then validate that DuckDB `EdgeQueryClient` can query Iceberg tables correctly.

## Commands (direct CLI)

```bash
# (Recommended) Split mode: run data pipelines, then rerun analytics from Iceberg.

# 1) Data pipelines (fetch + persist to Iceberg)
uv run tvscreener-scan --scanner opportunity --pipeline data --asset-type forex --universe majors --config tvscreener.yaml
uv run tvscreener-scan --scanner opportunity --pipeline data --asset-type forex --universe minors --config tvscreener.yaml

# 2) Analytics pipelines (query Iceberg + render the same matrix view)
uv run tvscreener-scan --runner local --scanner opportunity --pipeline analytics --asset-type forex --universe majors --matrix --limit 100 --config tvscreener.yaml
uv run tvscreener-scan --runner local --scanner opportunity --pipeline analytics --asset-type forex --universe minors --matrix --limit 100 --config tvscreener.yaml

# Strategy is an analytics pipeline over Iceberg-backed Gold rows
uv run tvscreener-scan --runner local --scanner strategy --pipeline analytics --asset-type forex --universe majors --matrix --limit 100 --config tvscreener.yaml
uv run tvscreener-scan --runner local --scanner strategy --pipeline analytics --asset-type forex --universe minors --matrix --limit 100 --config tvscreener.yaml

# (Optional) One-shot mode: data then analytics in one command
uv run tvscreener-scan --runner local --scanner opportunity --pipeline both --asset-type forex --universe majors --matrix --limit 100 --config tvscreener.yaml
uv run tvscreener-scan --runner local --scanner opportunity --pipeline both --asset-type forex --universe minors --matrix --limit 100 --config tvscreener.yaml
```

### Forex all-universe (matrix view)

```bash
# Data refresh (opportunity only; strategy data would duplicate upstream fetch)
uv run tvscreener-scan --scanner opportunity --pipeline data --asset-type forex --universe all --config tvscreener.yaml

# Analytics replays (matrix view) from Iceberg
uv run tvscreener-scan --runner local --scanner opportunity --pipeline analytics --asset-type forex --universe all --matrix --limit 100 --config tvscreener.yaml
uv run tvscreener-scan --runner local --scanner strategy --pipeline analytics --asset-type forex --universe all --matrix --limit 100 --config tvscreener.yaml
```

## Commands (Prefect batch reruns)

Use Prefect for deterministic artifacts keyed by `params_hash`, plus safe fan-out/sharding.

```bash
cp .env.example .env
uv sync --extra prefect

# Prefect local runtime (recommended for stable local runs)
export PREFECT_HOME="$PWD/.prefect-home"
export PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180

# For parity with production (avoid ephemeral server), start a local Prefect server:
#   uv run prefect server start --host 127.0.0.1 --port 4200 --background
#   export PREFECT_API_URL="http://127.0.0.1:4200/api"

# If you copy `.env.example` to `.env`, the CLI will best-effort load it and Prefect can read
# `PREFECT_API_URL` and `PREFECT_HOME` without manual exports.

# If Prefect fails to start with an Alembic error like:
#   "Can't locate revision identified by ..."
# reset local Prefect state and retry:
#   mv .prefect-home .prefect-home.bak-$(date +%Y%m%d-%H%M%S)
#   mkdir .prefect-home

# Full refresh: data then analytics (majors+minors, opportunity+strategy)
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_majors_minors_both.json \
  --data-concurrency 1 \
  --analytics-concurrency 8 \
  --rate-limit-min-interval 1.0 \
  --rate-limit-jitter 0.25

# Analytics-only replay (no upstream calls)
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_majors_minors_analytics.json \
  --concurrency 12 \
  --skip-existing
```

Artifacts are written under `artifacts/runs/<params_hash>/` (plus `artifacts/runs/batch/<batch_id>/`).

Legacy compatibility: `--artifacts-dir artifacts/prefect` continues to work during migration.

### Prefect: forex all-universe

Batch templates:
- `workflows/prefect/batches/forex_all_refresh.json` (opportunity both + strategy analytics)
- `workflows/prefect/batches/forex_all_analytics.json` (analytics-only replay)

```bash
uv sync --extra prefect
export PREFECT_HOME="$PWD/.prefect-home"
export PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180

# Full refresh
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_all_refresh.json \
  --data-concurrency 1 \
  --analytics-concurrency 8 \
  --rate-limit-min-interval 1.0 \
  --rate-limit-jitter 0.25 \
  --skip-existing

# Analytics-only replay
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_all_analytics.json \
  --concurrency 12 \
  --skip-existing
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
uv run pytest -q
```

## Notes

- Iceberg tables are queried through `EdgeQueryClient.get_relation()` using `table.scan().to_arrow()` (not `table.to_arrow()`).
