# Project Context (project-local OpenSpec)

## Purpose
`tvscreener` is a Python library + CLI that queries TradingView screener endpoints and produces
actionable screening outputs. The project includes an **Iceberg lakehouse** (Bronze/Silver/Gold)
to support replayable pipelines, auditable signals, and fast edge analytics.

## Tech Stack
- Python (library + CLI)
- `uv` for dependency management and running commands
- Apache Iceberg via `pyiceberg` + `pyarrow`
- DuckDB for edge analytics (`EdgeQueryClient`)
- Narwhals for backend-agnostic dataframe transforms
- Pandas as the primary dataframe interchange
- `pytest` for tests
- `rich` for CLI rendering

## Architecture Patterns
- Medallion architecture: **Bronze** (raw ingestion) → **Silver** (standardization + identity) → **Gold**
  (features for serving).
- Multi-timeframe focus:
  - `timeframes` and `timeframe_set_id` are first-class keys for wide-form outputs.
  - long-form tables with a `timeframe` column are the preferred long-term representation.
- Separation of concerns:
  - **Data pipelines** produce canonical Iceberg tables and must not depend on a query engine.
  - **Analytics pipelines** consume Iceberg snapshots and may use pluggable query backends.

## Conventions
- Favor canonical columns in persisted tables: `asset_type`, `entity_id`, `signal_date`,
  `run_id`, `fetched_at_utc`, `timeframes`, `timeframe_set_id`, `source`, `scanner_family`.
- Iceberg tables are canonical; on-disk snapshots are optional debug artifacts only.

