# Change: Add CLI pipeline modes (data vs analytics)

## Why
The project’s architecture requires a hard separation between:
- **Data pipelines**: fetch + persist canonical Iceberg tables (Bronze/Silver/Gold).
- **Analytics pipelines**: query Iceberg + compute decision products (ranking/filters/strategy logic) using a pluggable backend.

Today, `tvscreener-scan --scanner opportunity|strategy` interleaves both concerns in one execution path, which makes it hard to:
- rerun analytics (matrix view) **without refetching** from TradingView
- validate that the matrix view is reproducible from the **Iceberg lakehouse** (source of truth)
- scale toward multiple analytics backends without changing ingestion semantics

## What changes
- Add a CLI flag `--pipeline {data,analytics,both}` (default: `both`) to run:
  - **data**: fetch → persist to Iceberg (no Iceberg query dependency)
  - **analytics**: query Iceberg → render the same matrix view (no TradingView fetch)
  - **both**: run data pipeline then run analytics pipeline on the lakehouse outputs
- Provide an analytics path for both:
  - opportunity matrix view (read from `tvscreener.signals_latest`)
  - strategy matrix view (compute strategy signals from Iceberg-backed data, then render)

## Impact
- CLI behavior: new flag and new execution paths (non-breaking default).
- Orchestrator: adds an Iceberg-read path for analytics.
- Strategy scanner: adds a “scan from data” path so strategy is an analytics pipeline (no lakehouse writes required).

